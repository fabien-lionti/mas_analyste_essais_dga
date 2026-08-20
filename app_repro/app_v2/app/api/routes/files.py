from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlite3 import Connection

from app_v2.app.db.repositories.analyses import get_analysis
from app_v2.app.db.repositories.files import (
    discover_dxd_files,
    get_analysis_file,
    list_analysis_files,
)
from app_v2.app.dependencies import get_db


router = APIRouter(prefix="/api/analyses/{analysis_id}/files", tags=["files"])


class DiscoverDxdRequest(BaseModel):
    dxd_dir: str = Field(min_length=1)
    recursive: bool = False


@router.post("/discover-dxd")
def discover_dxd_endpoint(
    analysis_id: str,
    payload: DiscoverDxdRequest,
    conn: Connection = Depends(get_db),
):
    if get_analysis(conn, analysis_id) is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    dxd_dir = Path(payload.dxd_dir).expanduser()
    if not dxd_dir.exists() or not dxd_dir.is_dir():
        raise HTTPException(status_code=400, detail="DXD directory does not exist")
    return discover_dxd_files(
        conn,
        analysis_id=analysis_id,
        dxd_dir=dxd_dir,
        recursive=payload.recursive,
    )


@router.get("")
def list_files_endpoint(
    analysis_id: str,
    limit: int = Query(1000, ge=1, le=10000),
    conn: Connection = Depends(get_db),
):
    if get_analysis(conn, analysis_id) is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"items": list_analysis_files(conn, analysis_id, limit=limit)}


@router.get("/{file_id}")
def get_file_endpoint(analysis_id: str, file_id: str, conn: Connection = Depends(get_db)):
    if get_analysis(conn, analysis_id) is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    item = get_analysis_file(conn, analysis_id, file_id)
    if item is None:
        raise HTTPException(status_code=404, detail="File not found")
    return item
