from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlite3 import Connection

from app_v2.app.db.repositories.analyses import get_analysis
from app_v2.app.db.repositories.files import get_analysis_file, list_analysis_files
from app_v2.app.dependencies import get_db
from mas_essais.domain.dxd_schema import get_resampled_channels, get_time_values


router = APIRouter(prefix="/api/analyses/{analysis_id}/exploration", tags=["exploration"])


def require_analysis(conn: Connection, analysis_id: str) -> None:
    if get_analysis(conn, analysis_id) is None:
        raise HTTPException(status_code=404, detail="Analysis not found")


def load_resampled_payload(file_row: dict[str, Any]) -> dict[str, Any]:
    path_value = file_row.get("resampled_json_path")
    if not path_value:
        raise HTTPException(status_code=404, detail="Resampled JSON not found for file")
    path = Path(path_value)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Resampled JSON file missing on disk")
    return json.loads(path.read_text(encoding="utf-8"))


def numeric_or_none(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out:
        return None
    return out


def downsample_indices(length: int, max_points: int) -> list[int]:
    if length <= 0:
        return []
    limit = max(1, min(int(max_points), 50000))
    if length <= limit:
        return list(range(length))
    step = max(1, length // limit)
    return list(range(0, length, step))[:limit]


def normalize_requested_channels(channels: list[str] | None) -> list[str]:
    out: list[str] = []
    for item in channels or []:
        out.extend(part.strip() for part in item.split(",") if part.strip())
    return out


@router.get("/files")
def exploration_files_endpoint(analysis_id: str, conn: Connection = Depends(get_db)):
    require_analysis(conn, analysis_id)
    files = list_analysis_files(conn, analysis_id, limit=10000)
    return {
        "items": [
            {
                "file_id": item["file_id"],
                "source_dxd_name": item["source_dxd_name"],
                "resampled_json_name": item["resampled_json_name"],
                "has_resampled_json": bool(item["resampled_json_path"]),
                "status": item["status"],
            }
            for item in files
            if item.get("resampled_json_path")
        ]
    }


@router.get("/labels")
def exploration_labels_endpoint(analysis_id: str, conn: Connection = Depends(get_db)):
    require_analysis(conn, analysis_id)
    return {"items": []}


@router.get("/files/{file_id}/signals/options")
def exploration_signal_options_endpoint(
    analysis_id: str,
    file_id: str,
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    file_row = get_analysis_file(conn, analysis_id, file_id)
    if file_row is None:
        raise HTTPException(status_code=404, detail="File not found")
    payload = load_resampled_payload(file_row)
    channels = get_resampled_channels(payload)
    items = []
    for name, meta in sorted(channels.items()):
        if not isinstance(meta, dict):
            continue
        unit = meta.get("unit")
        items.append(
            {
                "value": name,
                "label": f"{name} ({unit})" if unit else name,
                "unit": unit,
                "available": isinstance(meta.get("values"), list),
            }
        )
    return {"items": items}


@router.get("/files/{file_id}/series")
def exploration_series_endpoint(
    analysis_id: str,
    file_id: str,
    channels: Optional[List[str]] = Query(default=None),
    max_points: int = Query(8000, ge=100, le=50000),
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    file_row = get_analysis_file(conn, analysis_id, file_id)
    if file_row is None:
        raise HTTPException(status_code=404, detail="File not found")
    payload = load_resampled_payload(file_row)
    time_values = get_time_values(payload)
    resampled = get_resampled_channels(payload)
    requested = [item for item in normalize_requested_channels(channels) if item in resampled][:2]
    if not requested:
        requested = [name for name, meta in resampled.items() if isinstance(meta, dict) and isinstance(meta.get("values"), list)][:2]
    indices = downsample_indices(len(time_values), max_points)
    return {
        "file_id": file_id,
        "time": [numeric_or_none(time_values[index]) for index in indices],
        "channels": [
            {
                "name": name,
                "unit": resampled[name].get("unit") if isinstance(resampled[name], dict) else None,
                "values": [
                    numeric_or_none((resampled[name].get("values") or [])[index])
                    if index < len(resampled[name].get("values") or [])
                    else None
                    for index in indices
                ],
            }
            for name in requested
            if isinstance(resampled.get(name), dict)
        ],
    }


@router.get("/files/{file_id}/trajectory")
def exploration_trajectory_endpoint(
    analysis_id: str,
    file_id: str,
    max_points: int = Query(8000, ge=100, le=50000),
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    file_row = get_analysis_file(conn, analysis_id, file_id)
    if file_row is None:
        raise HTTPException(status_code=404, detail="File not found")
    payload = load_resampled_payload(file_row)
    time_values = get_time_values(payload)
    resampled = get_resampled_channels(payload)
    lat = (resampled.get("gps.latitude") or {}).get("values") if isinstance(resampled.get("gps.latitude"), dict) else None
    lon = (resampled.get("gps.longitude") or {}).get("values") if isinstance(resampled.get("gps.longitude"), dict) else None
    if not isinstance(lat, list) or not isinstance(lon, list):
        return {"items": []}
    indices = downsample_indices(min(len(time_values), len(lat), len(lon)), max_points)
    return {
        "items": [
            {
                "time": numeric_or_none(time_values[index]),
                "lat": numeric_or_none(lat[index]),
                "lon": numeric_or_none(lon[index]),
            }
            for index in indices
            if numeric_or_none(lat[index]) is not None and numeric_or_none(lon[index]) is not None
        ]
    }
