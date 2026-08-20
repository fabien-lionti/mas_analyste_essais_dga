from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlite3 import Connection

from app_v2.app.db.repositories.analyses import (
    create_analysis,
    delete_analysis,
    get_analysis,
    list_analyses,
    update_analysis_config,
)
from app_v2.app.db.repositories.events import list_events
from app_v2.app.dependencies import get_db


router = APIRouter(prefix="/api/analyses", tags=["analyses"])


class CreateAnalysisRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    source_dxd_dir: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)


class UpdateAnalysisConfigRequest(BaseModel):
    config: Dict[str, Any] = Field(default_factory=dict)


@router.post("")
def create_analysis_endpoint(payload: CreateAnalysisRequest, conn: Connection = Depends(get_db)):
    return create_analysis(
        conn,
        name=payload.name.strip(),
        source_dxd_dir=payload.source_dxd_dir,
        config=payload.config,
    )


@router.get("")
def list_analyses_endpoint(
    limit: int = Query(100, ge=1, le=1000),
    conn: Connection = Depends(get_db),
):
    return {"items": list_analyses(conn, limit=limit)}


@router.get("/{analysis_id}")
def get_analysis_endpoint(analysis_id: str, conn: Connection = Depends(get_db)):
    analysis = get_analysis(conn, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


@router.patch("/{analysis_id}/config")
def update_analysis_config_endpoint(
    analysis_id: str,
    payload: UpdateAnalysisConfigRequest,
    conn: Connection = Depends(get_db),
):
    analysis = update_analysis_config(conn, analysis_id, payload.config)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


@router.delete("/{analysis_id}")
def delete_analysis_endpoint(analysis_id: str, conn: Connection = Depends(get_db)):
    deleted = delete_analysis(conn, analysis_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"status": "ok", "deleted": analysis_id}


@router.get("/{analysis_id}/events")
def list_analysis_events_endpoint(
    analysis_id: str,
    limit: int = Query(200, ge=1, le=1000),
    conn: Connection = Depends(get_db),
):
    if get_analysis(conn, analysis_id) is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"items": list_events(conn, analysis_id, limit=limit)}
