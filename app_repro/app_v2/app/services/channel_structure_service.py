from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Callable, ContextManager, Dict

from mas_essais.domain.dxd_schema import canonical_name_for, source_name_for
from mas_essais.io.dxd_reader import open as open_dxd

from app_v2.app.db.repositories.analyses import update_analysis_summary
from app_v2.app.db.repositories.channels import (
    recurrent_channels_from_inventory,
    replace_channel_inventory,
    replace_channel_structure,
)
from app_v2.app.db.repositories.events import add_event
from app_v2.app.db.repositories.files import list_analysis_files
from app_v2.app.domain.channels import channels_for_preset


DxdReaderFactory = Callable[[Path], ContextManager[Any]]
ProgressCallback = Callable[[Dict[str, Any]], None]
CancelCheck = Callable[[], bool]


def analyze_channel_structure(
    conn: sqlite3.Connection,
    *,
    analysis_id: str,
    preset_name: str = "app_default",
    normalize_names: bool = True,
    min_frequency: float = 0.8,
    target_channels: list[str] | None = None,
    max_files: int | None = None,
    progress_callback: ProgressCallback | None = None,
    should_cancel: CancelCheck | None = None,
    reader_factory: DxdReaderFactory = open_dxd,
) -> dict[str, Any]:
    files = list_analysis_files(conn, analysis_id)
    if max_files is not None:
        files = files[: max(1, int(max_files))]
    selected_channels = (
        list(dict.fromkeys(str(channel).strip() for channel in target_channels if str(channel).strip()))
        if target_channels is not None
        else []
    )
    inventory_rows: list[dict[str, Any]] = []
    file_summaries: list[dict[str, Any]] = []
    ok_files = 0
    error_files = 0
    cancelled = False

    add_event(
        conn,
        analysis_id,
        level="info",
        event_type="channel_analysis_started",
        message="Analyse structure canaux demarree",
        payload={
            "preset_name": preset_name,
            "normalize_names": normalize_names,
            "min_frequency": min_frequency,
            "file_count": len(files),
            "max_files": max_files,
        },
    )
    conn.commit()

    if progress_callback:
        progress_callback(
            {
                "status": "running",
                "phase": "initializing",
                "processed_files": 0,
                "total_files": len(files),
                "percent": 0 if files else 100,
                "message": "Préparation de l'analyse",
            }
        )

    for index, item in enumerate(files, start=1):
        if should_cancel and should_cancel():
            cancelled = True
            break
        file_id = item["file_id"]
        path = Path(item["source_dxd_path"])
        if progress_callback:
            progress_callback(
                {
                    "status": "running",
                    "phase": "reading_file",
                    "processed_files": index - 1,
                    "total_files": len(files),
                    "percent": round(((index - 1) / len(files)) * 100, 1) if files else 100,
                    "current_file": item["source_dxd_name"],
                    "message": f"Lecture {index}/{len(files)}",
                }
            )
        try:
            summary = inspect_dxd_file_channels(
                path,
                normalize_names=normalize_names,
                reader_factory=reader_factory,
            )
            ok_files += 1
        except Exception as exc:
            summary = {
                "status": "error",
                "sample_rate": None,
                "channels": [],
                "error": str(exc),
            }
            error_files += 1

        file_summaries.append(
            {
                "file_id": file_id,
                "source_dxd_name": item["source_dxd_name"],
                "status": summary["status"],
                "sample_rate": summary.get("sample_rate"),
                "n_channels": len(summary.get("channels") or []),
                "error": summary.get("error"),
            }
        )

        for channel in summary.get("channels") or []:
            inventory_rows.append(
                {
                    "file_id": file_id,
                    "channel_name": channel["source_name"],
                    "canonical_name": channel["canonical_name"] if normalize_names else channel["source_name"],
                    "unit": channel.get("unit"),
                    "sample_rate": summary.get("sample_rate"),
                    "metadata": {
                        "source_dxd_name": item["source_dxd_name"],
                        "status": summary["status"],
                        "raw_name": channel.get("name"),
                        "display_name": channel.get("display_name"),
                    },
                }
            )
        if progress_callback:
            progress_callback(
                {
                    "status": "running",
                    "phase": "file_done",
                    "processed_files": index,
                    "total_files": len(files),
                    "percent": round((index / len(files)) * 100, 1) if files else 100,
                    "current_file": item["source_dxd_name"],
                    "message": f"{index}/{len(files)} fichier(s) traités",
                }
            )

    status = "cancelled" if cancelled else "finished"
    recurrent = []
    if not cancelled:
        replace_channel_inventory(conn, analysis_id=analysis_id, rows=inventory_rows)
        recurrent = recurrent_channels_from_inventory(conn, analysis_id)
    result = {
        "analysis_id": analysis_id,
        "status": status,
        "preset_name": preset_name,
        "normalize_names": normalize_names,
        "min_frequency": min_frequency,
        "total_files": len(files),
        "processed_files": len(file_summaries),
        "ok_files": ok_files,
        "error_files": error_files,
        "inventory_channel_count": len(inventory_rows),
        "recurrent_channel_count": len(recurrent),
        "files": file_summaries,
    }
    if not cancelled:
        replace_channel_structure(
            conn,
            analysis_id=analysis_id,
            preset_name=preset_name,
            normalize_names=normalize_names,
            min_frequency=min_frequency,
            target_channels=[],
            recurrent_channels=recurrent,
            summary=result,
            status=status,
        )
        update_analysis_summary(conn, analysis_id, {"channel_structure": result})
    if progress_callback:
        progress_callback(
            {
                "status": status,
                "phase": status,
                "processed_files": len(file_summaries),
                "total_files": len(files),
                "percent": 100 if not files or not cancelled else round((len(file_summaries) / len(files)) * 100, 1),
                "message": "Analyse interrompue" if cancelled else "Analyse terminée",
            }
        )
    add_event(
        conn,
        analysis_id,
        level="warn" if cancelled else "info",
        event_type="channel_analysis_cancelled" if cancelled else "channel_analysis_finished",
        message="Analyse structure canaux interrompue" if cancelled else "Analyse structure canaux terminee",
        payload=result,
    )
    return result


def inspect_dxd_file_channels(
    path: Path,
    *,
    normalize_names: bool,
    reader_factory: DxdReaderFactory = open_dxd,
) -> dict[str, Any]:
    with reader_factory(path) as reader:
        channels = list(reader)
        rows = []
        for channel in channels:
            display_name = str(channel)
            raw_name = str(getattr(channel, "name", display_name))
            source_name = display_name or raw_name
            canonical_name = canonical_name_for(source_name)
            row = {
                "name": raw_name,
                "unit": getattr(channel, "unit", None),
                "display_name": display_name,
                "source_name": source_name,
                "canonical_name": canonical_name,
                "array_size": getattr(channel, "array_size", None),
            }
            rows.append(row)

        return {
            "status": "ok",
            "sample_rate": getattr(reader, "sample_rate", None),
            "channels": rows,
        }
