from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlite3 import Connection

from app_v2.app.config import get_settings
from app_v2.app.db.repositories.analyses import get_analysis
from app_v2.app.db.repositories.channels import (
    get_validated_channel_structure,
    get_channel_structure,
    list_channel_anomalies,
    list_channel_anomaly_files,
    list_channel_inventory,
    list_channel_presence,
    recurrent_channels_from_inventory,
    recurrent_channels_from_presence,
)
from app_v2.app.db.repositories.files import discover_dxd_files, list_analysis_files
from app_v2.app.dependencies import get_db
from app_v2.app.domain.channels import channel_presets
from app_v2.app.services.channel_analysis_tasks import channel_analysis_tasks
from app_v2.app.services.channel_validation_service import save_validated_channel_structure


router = APIRouter(prefix="/api/analyses/{analysis_id}/channels", tags=["channels"])


class AnalyzeChannelsRequest(BaseModel):
    preset_name: str = Field(default="app_default", min_length=1, max_length=80)
    normalize_names: bool = True
    min_frequency: float = Field(default=0.8, ge=0.0, le=1.0)
    target_channels: Optional[List[str]] = None
    max_files: Optional[int] = Field(default=None, ge=1)


class SaveValidatedStructureRequest(BaseModel):
    selected_channels: List[str] = Field(default_factory=list)
    normalize_names: bool = True


def require_analysis(conn: Connection, analysis_id: str) -> None:
    if get_analysis(conn, analysis_id) is None:
        raise HTTPException(status_code=404, detail="Analysis not found")


@router.get("/presets")
def channel_presets_endpoint(analysis_id: str, conn: Connection = Depends(get_db)):
    require_analysis(conn, analysis_id)
    return {"items": channel_presets()}


@router.post("/analyze")
def analyze_channels_endpoint(
    analysis_id: str,
    payload: AnalyzeChannelsRequest,
    conn: Connection = Depends(get_db),
):
    analysis = get_analysis(conn, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if not list_analysis_files(conn, analysis_id, limit=1) and analysis.get("source_dxd_dir"):
        dxd_dir = Path(analysis["source_dxd_dir"]).expanduser()
        if not dxd_dir.exists() or not dxd_dir.is_dir():
            raise HTTPException(status_code=400, detail="DXD directory does not exist")
        discover_dxd_files(conn, analysis_id=analysis_id, dxd_dir=dxd_dir)
        conn.commit()
    task = channel_analysis_tasks.start(
        db_path=get_settings().db_path,
        analysis_id=analysis_id,
        options={
            "preset_name": payload.preset_name,
            "normalize_names": payload.normalize_names,
            "min_frequency": payload.min_frequency,
            "target_channels": payload.target_channels,
            "max_files": payload.max_files,
        },
    )
    return task.snapshot()


@router.get("/tasks/current")
def current_channel_task_endpoint(analysis_id: str):
    task = channel_analysis_tasks.latest_for_analysis(analysis_id)
    return {"task": task.snapshot() if task is not None else None}


@router.get("/tasks/{task_id}")
def channel_task_status_endpoint(analysis_id: str, task_id: str):
    task = channel_analysis_tasks.get(task_id)
    if task is None or task.analysis_id != analysis_id:
        raise HTTPException(status_code=404, detail="Channel analysis task not found")
    return task.snapshot()


@router.post("/tasks/{task_id}/cancel")
def cancel_channel_task_endpoint(analysis_id: str, task_id: str):
    task = channel_analysis_tasks.cancel(task_id)
    if task is None or task.analysis_id != analysis_id:
        raise HTTPException(status_code=404, detail="Channel analysis task not found")
    return task.snapshot()


@router.get("/status")
def channel_status_endpoint(analysis_id: str, conn: Connection = Depends(get_db)):
    require_analysis(conn, analysis_id)
    structure = get_channel_structure(conn, analysis_id)
    if structure is None:
        return {"status": "not_started"}
    return structure


@router.get("/presence")
def channel_presence_endpoint(
    analysis_id: str,
    file_id: Optional[str] = None,
    present: Optional[bool] = None,
    limit: int = Query(50000, ge=1, le=200000),
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    return {
        "items": list_channel_presence(
            conn,
            analysis_id,
            file_id=file_id,
            present=present,
            limit=limit,
        )
    }


@router.get("/recurrent")
def recurrent_channels_endpoint(
    analysis_id: str,
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    return {"items": recurrent_channels_from_inventory(conn, analysis_id)}


@router.get("/inventory")
def channel_inventory_endpoint(
    analysis_id: str,
    file_id: Optional[str] = None,
    limit: int = Query(50000, ge=1, le=200000),
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    return {"items": list_channel_inventory(conn, analysis_id, file_id=file_id, limit=limit)}


@router.get("/validated-structure")
def validated_channel_structure_endpoint(analysis_id: str, conn: Connection = Depends(get_db)):
    require_analysis(conn, analysis_id)
    structure = get_validated_channel_structure(conn, analysis_id)
    return {"structure": structure}


@router.post("/validated-structure")
def save_validated_channel_structure_endpoint(
    analysis_id: str,
    payload: SaveValidatedStructureRequest,
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    try:
        result = save_validated_channel_structure(
            conn,
            analysis_id=analysis_id,
            selected_channels=payload.selected_channels,
            normalize_names=payload.normalize_names,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.get("/anomalies/files")
def channel_anomaly_files_endpoint(analysis_id: str, conn: Connection = Depends(get_db)):
    require_analysis(conn, analysis_id)
    return {"items": list_channel_anomaly_files(conn, analysis_id)}


@router.get("/anomalies")
def channel_anomalies_endpoint(
    analysis_id: str,
    file_id: Optional[str] = None,
    limit: int = Query(50000, ge=1, le=200000),
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    return {"items": list_channel_anomalies(conn, analysis_id, file_id=file_id, limit=limit)}
