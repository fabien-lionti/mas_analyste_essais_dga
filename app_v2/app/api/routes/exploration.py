from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlite3 import Connection

from app_v2.app.db.repositories.analyses import get_analysis
from app_v2.app.db.repositories.files import get_analysis_file, get_recorded_at_range, list_analysis_files
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


def values_for_channel(resampled: dict[str, Any], channel: str) -> list[Any]:
    payload = resampled.get(channel)
    if not isinstance(payload, dict):
        return []
    values = payload.get("values")
    return values if isinstance(values, list) else []


def append_parametric_points(
    *,
    out: list[dict[str, Any]],
    file_row: dict[str, Any],
    x_channel: str,
    y_channel: str,
    max_points: int,
) -> int:
    payload = load_resampled_payload(file_row)
    resampled = get_resampled_channels(payload)
    x_values = values_for_channel(resampled, x_channel)
    y_values = values_for_channel(resampled, y_channel)
    count = min(len(x_values), len(y_values))
    if count <= 0:
        return 0
    indices = downsample_indices(count, max_points)
    added = 0
    for index in indices:
        x = numeric_or_none(x_values[index])
        y = numeric_or_none(y_values[index])
        if x is None or y is None:
            continue
        out.append(
            {
                "x": x,
                "y": y,
                "file_id": file_row["file_id"],
                "file_name": file_row.get("resampled_json_name") or file_row["source_dxd_name"],
            }
        )
        added += 1
    return count


@router.get("/files")
def exploration_files_endpoint(
    analysis_id: str,
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    files = list_analysis_files(
        conn,
        analysis_id,
        limit=10000,
        date_from=date_from,
        date_to=date_to,
    )
    return {
        "items": [
            {
                "file_id": item["file_id"],
                "source_dxd_name": item["source_dxd_name"],
                "resampled_json_name": item["resampled_json_name"],
                "has_resampled_json": bool(item["resampled_json_path"]),
                "recorded_at": item["recorded_at"],
                "duration_sec": item["duration_sec"],
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


@router.get("/date-range")
def exploration_date_range_endpoint(analysis_id: str, conn: Connection = Depends(get_db)):
    require_analysis(conn, analysis_id)
    return get_recorded_at_range(conn, analysis_id)


@router.get("/parametric")
def exploration_parametric_endpoint(
    analysis_id: str,
    x_channel: str,
    y_channel: str,
    scope: str = Query("current", pattern="^(current|filtered)$"),
    file_id: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    max_points: int = Query(8000, ge=100, le=50000),
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    if scope == "current":
        if not file_id:
            raise HTTPException(status_code=400, detail="file_id is required for current scope")
        file_row = get_analysis_file(conn, analysis_id, file_id)
        if file_row is None:
            raise HTTPException(status_code=404, detail="File not found")
        files = [file_row]
    else:
        files = [
            item
            for item in list_analysis_files(
                conn,
                analysis_id,
                limit=10000,
                date_from=date_from,
                date_to=date_to,
            )
            if item.get("resampled_json_path")
        ]

    points: list[dict[str, Any]] = []
    skipped_files: list[dict[str, str]] = []
    point_count = 0
    per_file_limit = max(1, min(int(max_points), 50000))
    if scope == "filtered" and files:
        per_file_limit = max(1, min(per_file_limit, int(max_points) // len(files) or 1))
    for file_row in files:
        try:
            point_count += append_parametric_points(
                out=points,
                file_row=file_row,
                x_channel=x_channel,
                y_channel=y_channel,
                max_points=per_file_limit,
            )
        except HTTPException as exc:
            skipped_files.append(
                {
                    "file_id": file_row["file_id"],
                    "file_name": file_row.get("resampled_json_name") or file_row["source_dxd_name"],
                    "reason": str(exc.detail),
                }
            )

    return {
        "scope": scope,
        "x_channel": x_channel,
        "y_channel": y_channel,
        "file_count": len(files),
        "point_count": point_count,
        "returned_point_count": len(points),
        "items": points,
        "skipped_files": skipped_files,
    }


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
