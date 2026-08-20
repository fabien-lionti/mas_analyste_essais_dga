from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlite3 import Connection

from app_v2.app.config import get_settings
from app_v2.app.db.repositories.analyses import get_analysis
from app_v2.app.dependencies import get_db
from app_v2.app.services.resampling_tasks import resampling_tasks


router = APIRouter(prefix="/api/analyses/{analysis_id}/resampling", tags=["resampling"])


class ExportJsonRequest(BaseModel):
    target_frequency_hz: float = Field(gt=0, le=1000)
    interpolation_method: str = Field(default="linear")
    output_dir: Optional[str] = None


def require_analysis(conn: Connection, analysis_id: str) -> None:
    if get_analysis(conn, analysis_id) is None:
        raise HTTPException(status_code=404, detail="Analysis not found")


@router.post("/export-json")
def export_json_endpoint(
    analysis_id: str,
    payload: ExportJsonRequest,
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    if payload.interpolation_method not in {"linear", "nearest", "zero_order_hold"}:
        raise HTTPException(status_code=400, detail="Invalid interpolation method")
    task = resampling_tasks.start(
        db_path=get_settings().db_path,
        analysis_id=analysis_id,
        options={
            "target_frequency_hz": payload.target_frequency_hz,
            "interpolation_method": payload.interpolation_method,
            "output_dir": Path(payload.output_dir).expanduser() if payload.output_dir else None,
        },
    )
    return task.snapshot()


@router.get("/tasks/current")
def current_resampling_task_endpoint(analysis_id: str):
    task = resampling_tasks.latest_for_analysis(analysis_id)
    return {"task": task.snapshot() if task is not None else None}


@router.get("/tasks/{task_id}")
def resampling_task_status_endpoint(analysis_id: str, task_id: str):
    task = resampling_tasks.get(task_id)
    if task is None or task.analysis_id != analysis_id:
        raise HTTPException(status_code=404, detail="Resampling task not found")
    return task.snapshot()


@router.post("/tasks/{task_id}/cancel")
def cancel_resampling_task_endpoint(analysis_id: str, task_id: str):
    task = resampling_tasks.cancel(task_id)
    if task is None or task.analysis_id != analysis_id:
        raise HTTPException(status_code=404, detail="Resampling task not found")
    return task.snapshot()
