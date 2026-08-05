from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict

import numpy as np
import pandas as pd

from app_v2.app.db.connection import now_iso
from app_v2.app.db.repositories.analyses import update_analysis_config, update_analysis_summary
from app_v2.app.db.repositories.channels import get_validated_channel_structure
from app_v2.app.db.repositories.events import add_event
from app_v2.app.db.repositories.files import list_analysis_files, update_file_resampled_json
from app_v2.app.config import get_settings
from mas_essais.domain.dxd_schema import (
    SPEC_BY_SOURCE,
    canonical_name_for,
    channel_metadata,
    source_name_for,
    to_json_list,
)
from mas_essais.io.dxd_reader import open as open_dxd


DxdReaderFactory = Callable[[Path], Any]
ProgressCallback = Callable[[Dict[str, Any]], None]
CancelCallback = Callable[[], bool]


def safe_export_json_name(file_name: str) -> str:
    stem = Path(file_name).stem
    safe_stem = "".join(ch if ch.isalnum() or ch in ("_", "-", ".") else "_" for ch in stem).strip("._-")
    return f"{safe_stem or 'export'}.json"


def source_candidates_for_export_name(name: str) -> list[str]:
    raw = str(name or "").strip()
    if not raw:
        return []
    candidates = [raw]
    for candidate in (source_name_for(raw), canonical_name_for(raw)):
        if candidate not in candidates:
            candidates.append(candidate)
    spec = SPEC_BY_SOURCE.get(raw) or SPEC_BY_SOURCE.get(source_name_for(raw))
    if spec is not None:
        for candidate in (spec.source_name, spec.canonical_name):
            if candidate not in candidates:
                candidates.append(candidate)
    return candidates


def build_dxd_channel_lookup(reader: Any) -> dict[str, Any]:
    lookup: dict[str, Any] = {}
    for channel in reader:
        raw_name = str(getattr(channel, "name", ""))
        display_name = str(channel)
        lookup[raw_name] = channel
        lookup[display_name] = channel
    return lookup


def find_dxd_channel(lookup: dict[str, Any], requested_name: str) -> Any | None:
    for candidate in source_candidates_for_export_name(requested_name):
        channel = lookup.get(candidate)
        if channel is not None:
            return channel
    return None


def extract_date_from_name(name: str) -> str | None:
    match = re.search(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})", name)
    if not match:
        return None
    return "-".join(match.groups())


def resample_series_to_grid(series: pd.Series, grid: np.ndarray, method: str) -> np.ndarray:
    if len(series) == 0:
        return np.full(len(grid), np.nan, dtype=np.float64)
    x = pd.to_numeric(pd.Series(series.index), errors="coerce").to_numpy(dtype=np.float64)
    y = pd.to_numeric(pd.Series(series.to_numpy()), errors="coerce").to_numpy(dtype=np.float64)
    mask = np.isfinite(x) & np.isfinite(y)
    if int(mask.sum()) == 0:
        return np.full(len(grid), np.nan, dtype=np.float64)
    x = x[mask]
    y = y[mask]
    order = np.argsort(x, kind="mergesort")
    x = x[order]
    y = y[order]
    x_unique, unique_idx = np.unique(x, return_index=True)
    y_unique = y[unique_idx]
    if len(x_unique) == 1:
        return np.full(len(grid), float(y_unique[0]), dtype=np.float64)
    if method == "nearest":
        positions = np.searchsorted(x_unique, grid, side="left")
        positions = np.clip(positions, 0, len(x_unique) - 1)
        previous = np.clip(positions - 1, 0, len(x_unique) - 1)
        use_previous = np.abs(grid - x_unique[previous]) <= np.abs(grid - x_unique[positions])
        chosen = np.where(use_previous, previous, positions)
        values = y_unique[chosen]
        values[(grid < x_unique[0]) | (grid > x_unique[-1])] = np.nan
        return values
    if method == "zero_order_hold":
        positions = np.searchsorted(x_unique, grid, side="right") - 1
        values = np.full(len(grid), np.nan, dtype=np.float64)
        valid = positions >= 0
        values[valid] = y_unique[positions[valid]]
        values[grid > x_unique[-1]] = np.nan
        return values
    return np.interp(grid, x_unique, y_unique, left=np.nan, right=np.nan)


def export_dxd_file_to_json(
    *,
    path: Path,
    output_dir: Path,
    analysis_id: str,
    selected_channels: list[str],
    target_frequency_hz: float,
    interpolation_method: str,
    reader_factory: DxdReaderFactory = open_dxd,
) -> dict[str, Any]:
    with reader_factory(path) as reader:
        lookup = build_dxd_channel_lookup(reader)
        resolved: list[tuple[str, Any]] = []
        missing: list[str] = []
        for requested in selected_channels:
            channel = find_dxd_channel(lookup, requested)
            if channel is None:
                missing.append(requested)
            else:
                resolved.append((requested, channel))
        if not resolved:
            raise ValueError(f"Aucun canal sélectionné trouvé dans {path.name}")

        source_series: list[tuple[str, str, str, pd.Series]] = []
        min_time: float | None = None
        max_time: float | None = None
        for requested, channel in resolved:
            series = channel.series()
            numeric_index = pd.to_numeric(pd.Series(series.index), errors="coerce").to_numpy(dtype=np.float64)
            finite_index = numeric_index[np.isfinite(numeric_index)]
            if len(finite_index) == 0:
                continue
            min_time = float(np.nanmin(finite_index)) if min_time is None else min(min_time, float(np.nanmin(finite_index)))
            max_time = float(np.nanmax(finite_index)) if max_time is None else max(max_time, float(np.nanmax(finite_index)))
            source_series.append((requested, str(getattr(channel, "name", "")), str(channel), series))

        if not source_series or min_time is None or max_time is None or max_time < min_time:
            raise ValueError(f"Canaux sélectionnés illisibles dans {path.name}")

        step = 1.0 / target_frequency_hz
        n_samples = int(np.floor((max_time - min_time) * target_frequency_hz)) + 1
        if n_samples <= 0:
            raise ValueError(f"Grille de resampling vide pour {path.name}")
        grid = min_time + np.arange(n_samples, dtype=np.float64) * step

        resampled: dict[str, Any] = {}
        source_to_canonical: dict[str, str] = {}
        canonical_to_source: dict[str, str] = {}
        for requested, source_name, display_name, series in source_series:
            values = resample_series_to_grid(series, grid, interpolation_method)
            lookup_name = display_name if display_name in SPEC_BY_SOURCE else source_name
            if lookup_name not in SPEC_BY_SOURCE:
                lookup_name = source_name_for(requested)
            canonical = canonical_name_for(lookup_name)
            if canonical == lookup_name:
                canonical = canonical_name_for(requested)
            if canonical in resampled and source_name != canonical:
                canonical = source_name
            metadata = channel_metadata(canonical, lookup_name if lookup_name in SPEC_BY_SOURCE else source_name)
            metadata["source_name"] = display_name
            metadata["values"] = to_json_list(values)
            resampled[canonical] = metadata
            source_to_canonical[display_name] = canonical
            source_to_canonical[source_name] = canonical
            canonical_to_source[canonical] = display_name

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / safe_export_json_name(path.name)
    stat = path.stat()
    payload = {
        "schema_version": "dxd_resampled_export.v1",
        "analysis_id": analysis_id,
        "file": path.name,
        "source_path": str(path),
        "date": extract_date_from_name(path.name),
        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "time": to_json_list(grid),
        "target_hz": target_frequency_hz,
        "timebase": {
            "time": to_json_list(grid),
            "unit": "s",
            "start": float(min_time),
            "end": float(grid[-1]) if len(grid) else None,
            "sample_count": int(len(grid)),
        },
        "pipeline": {
            "name": "app_v2_dxd_json_export",
            "analysis_id": analysis_id,
            "target_hz": target_frequency_hz,
            "interpolation_method": interpolation_method,
            "created_at": now_iso(),
            "missing_requested_channels": missing,
        },
        "channels": {
            "resampled": resampled,
            "source_to_canonical": source_to_canonical,
            "canonical_to_source": canonical_to_source,
        },
        "features": {},
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return {
        "status": "ok",
        "source_dxd_name": path.name,
        "json_name": output_path.name,
        "json_path": str(output_path),
        "target_frequency_hz": target_frequency_hz,
        "interpolation_method": interpolation_method,
        "n_samples": int(len(grid)),
        "n_channels": len(resampled),
        "exported_channels": list(resampled.keys()),
        "missing_requested_channels": missing,
    }


def export_analysis_resampled_json(
    conn: sqlite3.Connection,
    *,
    analysis_id: str,
    target_frequency_hz: float,
    interpolation_method: str,
    output_dir: Path | None = None,
    progress_callback: ProgressCallback | None = None,
    should_cancel: CancelCallback | None = None,
    reader_factory: DxdReaderFactory = open_dxd,
) -> dict[str, Any]:
    if target_frequency_hz <= 0 or not np.isfinite(target_frequency_hz):
        raise ValueError("Fréquence de sampling invalide")
    if interpolation_method not in {"linear", "nearest", "zero_order_hold"}:
        raise ValueError("Méthode d'interpolation invalide")
    structure = get_validated_channel_structure(conn, analysis_id)
    selected_channels = list(structure["selected_channels"] if structure else [])
    if not selected_channels:
        raise ValueError("Aucune structure canaux sauvegardée")
    files = list_analysis_files(conn, analysis_id, limit=10000)
    if not files:
        raise ValueError("Aucun fichier DXD rattaché")
    target_dir = output_dir or get_settings().resampled_json_dir / analysis_id
    started_at = now_iso()
    update_analysis_config(
        conn,
        analysis_id,
        {
            "sampling": {
                "target_frequency_hz": target_frequency_hz,
                "method": interpolation_method,
                "resampled_json_dir": str(target_dir),
            }
        },
    )

    exported: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    total = len(files)
    if progress_callback:
        progress_callback({"status": "running", "phase": "exporting", "total_files": total, "message": "Export JSON démarré"})
    for index, item in enumerate(files, start=1):
        if should_cancel and should_cancel():
            break
        if progress_callback:
            progress_callback(
                {
                    "status": "running",
                    "phase": "exporting",
                    "processed_files": index - 1,
                    "total_files": total,
                    "percent": ((index - 1) / total) * 100,
                    "current_file": item["source_dxd_name"],
                    "message": f"Export {item['source_dxd_name']}",
                }
            )
        try:
            result = export_dxd_file_to_json(
                path=Path(item["source_dxd_path"]),
                output_dir=target_dir,
                analysis_id=analysis_id,
                selected_channels=selected_channels,
                target_frequency_hz=target_frequency_hz,
                interpolation_method=interpolation_method,
                reader_factory=reader_factory,
            )
            update_file_resampled_json(
                conn,
                analysis_id=analysis_id,
                file_id=item["file_id"],
                json_path=Path(result["json_path"]),
                metadata={"resampling": result},
            )
            exported.append(result)
        except Exception as exc:
            errors.append({"file_id": item["file_id"], "source_dxd_name": item["source_dxd_name"], "error": str(exc)})

    cancelled = bool(should_cancel and should_cancel())
    status = "cancelled" if cancelled else ("finished_with_errors" if errors else "finished")
    result = {
        "status": status,
        "analysis_id": analysis_id,
        "started_at": started_at,
        "finished_at": now_iso(),
        "target_frequency_hz": target_frequency_hz,
        "interpolation_method": interpolation_method,
        "output_dir": str(target_dir),
        "selected_channel_count": len(selected_channels),
        "total_files": total,
        "exported_files": len(exported),
        "error_count": len(errors),
        "exported": exported,
        "errors": errors,
    }
    update_analysis_summary(conn, analysis_id, {"resampling": result})
    add_event(
        conn,
        analysis_id,
        level="warn" if errors or cancelled else "info",
        event_type="resampling_export_finished",
        message="Export JSON interrompu" if cancelled else "Export JSON terminé",
        payload=result,
    )
    if progress_callback:
        progress_callback(
            {
                "status": status,
                "phase": status,
                "processed_files": len(exported) + len(errors),
                "total_files": total,
                "percent": 100 if not cancelled else ((len(exported) + len(errors)) / total) * 100,
                "message": "Export JSON terminé" if not cancelled else "Export JSON interrompu",
            }
        )
    return result
