from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlite3 import Connection

from app_v2.app.db.repositories.analyses import get_analysis
from app_v2.app.db.repositories.annotations import (
    create_annotation,
    create_annotation_set,
    create_managed_annotation_label,
    delete_annotation,
    delete_annotations_by_label,
    delete_managed_annotation_label,
    get_annotation,
    get_managed_annotation_label_by_name,
    list_annotation_labels,
    list_annotation_sets,
    list_annotation_versions,
    list_annotations,
    list_managed_annotation_labels,
    rename_annotation_label,
    summarize_annotation_labels,
    update_annotation,
    update_managed_annotation_label,
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


class RenameAnnotationLabelRequest(BaseModel):
    new_label: str = Field(min_length=1, max_length=160)


class ManagedAnnotationLabelRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: Optional[str] = None
    color: Optional[str] = None


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
    label = payload.label.strip()
    if get_managed_annotation_label_by_name(conn, analysis_id, label) is None:
        raise HTTPException(status_code=400, detail="Label must be created before annotation")
    return create_annotation(
        conn,
        analysis_id=analysis_id,
        file_id=payload.file_id,
        start_time_sec=payload.start_time_sec,
        end_time_sec=payload.end_time_sec,
        label=label,
        confidence=payload.confidence,
        comment=payload.comment,
        annotation_set_id=payload.annotation_set_id,
        metadata=payload.metadata,
    )


@router.get("/annotations/labels")
def list_annotation_labels_endpoint(analysis_id: str, conn: Connection = Depends(get_db)):
    require_analysis(conn, analysis_id)
    return {"items": list_annotation_labels(conn, analysis_id)}


@router.get("/annotation-labels")
def list_managed_annotation_labels_endpoint(analysis_id: str, conn: Connection = Depends(get_db)):
    require_analysis(conn, analysis_id)
    return {"items": list_managed_annotation_labels(conn, analysis_id)}


@router.post("/annotation-labels")
def create_managed_annotation_label_endpoint(
    analysis_id: str,
    payload: ManagedAnnotationLabelRequest,
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    try:
        return create_managed_annotation_label(
            conn,
            analysis_id=analysis_id,
            name=name,
            description=payload.description,
            color=payload.color,
        )
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            raise HTTPException(status_code=409, detail="Label already exists")
        raise


@router.patch("/annotation-labels/{label_id}")
def update_managed_annotation_label_endpoint(
    analysis_id: str,
    label_id: str,
    payload: ManagedAnnotationLabelRequest,
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    try:
        label = update_managed_annotation_label(
            conn,
            analysis_id=analysis_id,
            label_id=label_id,
            name=name,
            description=payload.description,
            color=payload.color,
        )
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            raise HTTPException(status_code=409, detail="Label already exists")
        raise
    if label is None:
        raise HTTPException(status_code=404, detail="Label not found")
    return label


@router.delete("/annotation-labels/{label_id}")
def delete_managed_annotation_label_endpoint(
    analysis_id: str,
    label_id: str,
    delete_annotations: bool = False,
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    deleted, usage_count = delete_managed_annotation_label(
        conn,
        analysis_id,
        label_id,
        delete_annotations=delete_annotations,
    )
    if not deleted and usage_count:
        raise HTTPException(status_code=409, detail={"message": "Label is used", "usage_count": usage_count})
    if not deleted:
        raise HTTPException(status_code=404, detail="Label not found")
    return {"status": "ok", "deleted": label_id, "deleted_annotations": usage_count}


@router.get("/annotations/summary")
def summarize_annotation_labels_endpoint(analysis_id: str, conn: Connection = Depends(get_db)):
    require_analysis(conn, analysis_id)
    return {"items": summarize_annotation_labels(conn, analysis_id)}


@router.patch("/annotations/labels/{label}")
def rename_annotation_label_endpoint(
    analysis_id: str,
    label: str,
    payload: RenameAnnotationLabelRequest,
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    new_label = payload.new_label.strip()
    if not new_label:
        raise HTTPException(status_code=400, detail="new_label is required")
    updated = rename_annotation_label(conn, analysis_id, label, new_label)
    if not updated:
        raise HTTPException(status_code=404, detail="Label not found")
    return {"status": "ok", "updated": updated, "old_label": label, "new_label": new_label}


@router.delete("/annotations/labels/{label}")
def delete_annotation_label_endpoint(
    analysis_id: str,
    label: str,
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    deleted = delete_annotations_by_label(conn, analysis_id, label)
    if not deleted:
        raise HTTPException(status_code=404, detail="Label not found")
    return {"status": "ok", "deleted": deleted, "label": label}


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
    label = payload.label.strip()
    if get_managed_annotation_label_by_name(conn, analysis_id, label) is None:
        raise HTTPException(status_code=400, detail="Label must be created before annotation")
    annotation = update_annotation(
        conn,
        analysis_id=analysis_id,
        annotation_id=annotation_id,
        start_time_sec=payload.start_time_sec,
        end_time_sec=payload.end_time_sec,
        label=label,
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
