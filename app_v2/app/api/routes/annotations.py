from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlite3 import Connection

from app_v2.app.db.repositories.analyses import get_analysis
from app_v2.app.db.repositories.annotations import (
    create_annotation,
    create_annotation_set,
    delete_annotation,
    get_annotation,
    list_annotation_labels,
    list_annotation_sets,
    list_annotation_versions,
    list_annotations,
    update_annotation,
)
from app_v2.app.db.repositories.files import get_analysis_file
from app_v2.app.dependencies import get_db


router = APIRouter(prefix="/api/analyses/{analysis_id}", tags=["annotations"])


class CreateAnnotationSetRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: Optional[str] = None


class AnnotationWriteRequest(BaseModel):
    file_id: str = Field(min_length=1)
    start_time_sec: float = Field(ge=0)
    end_time_sec: float = Field(ge=0)
    label: str = Field(min_length=1, max_length=160)
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    comment: Optional[str] = None
    annotation_set_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AnnotationUpdateRequest(BaseModel):
    start_time_sec: float = Field(ge=0)
    end_time_sec: float = Field(ge=0)
    label: str = Field(min_length=1, max_length=160)
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    comment: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


def require_analysis(conn: Connection, analysis_id: str) -> None:
    if get_analysis(conn, analysis_id) is None:
        raise HTTPException(status_code=404, detail="Analysis not found")


def require_analysis_file(conn: Connection, analysis_id: str, file_id: str) -> None:
    if get_analysis_file(conn, analysis_id, file_id) is None:
        raise HTTPException(status_code=404, detail="File not found")


@router.get("/annotation-sets")
def list_annotation_sets_endpoint(analysis_id: str, conn: Connection = Depends(get_db)):
    require_analysis(conn, analysis_id)
    return {"items": list_annotation_sets(conn, analysis_id)}


@router.post("/annotation-sets")
def create_annotation_set_endpoint(
    analysis_id: str,
    payload: CreateAnnotationSetRequest,
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    return create_annotation_set(
        conn,
        analysis_id=analysis_id,
        name=payload.name.strip(),
        description=payload.description,
    )


@router.get("/annotations")
def list_annotations_endpoint(
    analysis_id: str,
    file_id: Optional[str] = None,
    label: Optional[str] = None,
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    if file_id:
        require_analysis_file(conn, analysis_id, file_id)
    return {"items": list_annotations(conn, analysis_id, file_id=file_id, label=label)}


@router.post("/annotations")
def create_annotation_endpoint(
    analysis_id: str,
    payload: AnnotationWriteRequest,
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    require_analysis_file(conn, analysis_id, payload.file_id)
    if payload.end_time_sec <= payload.start_time_sec:
        raise HTTPException(status_code=400, detail="end_time_sec must be greater than start_time_sec")
    return create_annotation(
        conn,
        analysis_id=analysis_id,
        file_id=payload.file_id,
        start_time_sec=payload.start_time_sec,
        end_time_sec=payload.end_time_sec,
        label=payload.label.strip(),
        confidence=payload.confidence,
        comment=payload.comment,
        annotation_set_id=payload.annotation_set_id,
        metadata=payload.metadata,
    )


@router.get("/annotations/labels")
def list_annotation_labels_endpoint(analysis_id: str, conn: Connection = Depends(get_db)):
    require_analysis(conn, analysis_id)
    return {"items": list_annotation_labels(conn, analysis_id)}


@router.get("/annotations/{annotation_id}")
def get_annotation_endpoint(
    analysis_id: str,
    annotation_id: str,
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    annotation = get_annotation(conn, analysis_id, annotation_id)
    if annotation is None:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return annotation


@router.patch("/annotations/{annotation_id}")
def update_annotation_endpoint(
    analysis_id: str,
    annotation_id: str,
    payload: AnnotationUpdateRequest,
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    if payload.end_time_sec <= payload.start_time_sec:
        raise HTTPException(status_code=400, detail="end_time_sec must be greater than start_time_sec")
    annotation = update_annotation(
        conn,
        analysis_id=analysis_id,
        annotation_id=annotation_id,
        start_time_sec=payload.start_time_sec,
        end_time_sec=payload.end_time_sec,
        label=payload.label.strip(),
        confidence=payload.confidence,
        comment=payload.comment,
        metadata=payload.metadata,
    )
    if annotation is None:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return annotation


@router.delete("/annotations/{annotation_id}")
def delete_annotation_endpoint(
    analysis_id: str,
    annotation_id: str,
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    if not delete_annotation(conn, analysis_id, annotation_id):
        raise HTTPException(status_code=404, detail="Annotation not found")
    return {"status": "ok", "deleted": annotation_id}


@router.get("/annotations/{annotation_id}/versions")
def list_annotation_versions_endpoint(
    analysis_id: str,
    annotation_id: str,
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    versions = list_annotation_versions(conn, analysis_id, annotation_id)
    if versions is None:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return {"items": versions}
