from __future__ import annotations

import json
import statistics
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlite3 import Connection

from app_v2.app.api.routes.exploration import load_resampled_payload, numeric_or_none, values_for_channel
from app_v2.app.db.repositories.analyses import get_analysis
from app_v2.app.db.repositories.annotations import list_annotations
from app_v2.app.db.repositories.dynamic_analysis import (
    create_dynamic_analysis,
    create_or_replace_prediction,
    create_prediction_correction,
    create_prompt,
    create_run,
    create_run_version,
    delete_run,
    get_dynamic_analysis,
    get_prompt,
    get_prediction,
    get_run,
    list_dynamic_analyses,
    list_prediction_corrections,
    list_predictions,
    list_prompts,
    list_run_versions,
    list_runs,
)
from app_v2.app.db.repositories.files import get_analysis_file, list_analysis_files
from app_v2.app.dependencies import get_db
from mas_essais.domain.dxd_schema import get_resampled_channels, get_time_values


router = APIRouter(prefix="/api/analyses/{analysis_id}/dynamic-analysis", tags=["dynamic-analysis"])


class DynamicPromptRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: Optional[str] = None
    system_prompt: str = Field(min_length=1)
    user_prompt: str = Field(min_length=1)
    required_channels: List[str] = Field(default_factory=list)
    output_schema: Dict[str, Any] = Field(default_factory=dict)


class DynamicContextRequest(BaseModel):
    name: str = Field(default="Analyse dynamique", min_length=1, max_length=160)
    provider: str = Field(default="dry_run", min_length=1, max_length=80)
    model: Optional[str] = None
    prompt_id: Optional[str] = None
    system_prompt: str = ""
    user_prompt: str = Field(default="", min_length=1)
    channels: List[str] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)
    file_ids: List[str] = Field(default_factory=list)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    context_before_sec: float = Field(default=5, ge=0, le=120)
    context_after_sec: float = Field(default=10, ge=0, le=120)
    max_segments: int = Field(default=25, ge=1, le=200)
    max_points_per_segment: int = Field(default=250, ge=20, le=2000)


class DynamicRunVersionRequest(BaseModel):
    response_markdown: str = Field(min_length=1)
    confidence: Optional[str] = None
    note: Optional[str] = None
    validated_for_dataset: bool = False


class DynamicAnalysisDefinitionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    system_prompt: str = Field(min_length=1)
    selected_channels: List[str] = Field(default_factory=list)
    indicators: List[Dict[str, Any]] = Field(default_factory=list)
    label_category: str = Field(min_length=1, max_length=160)
    output_schema: Dict[str, Any] = Field(default_factory=dict)


class DynamicPredictionRequest(BaseModel):
    user_prompt: str = Field(default="", min_length=1)
    context_before_sec: float = Field(default=5, ge=0, le=120)
    context_after_sec: float = Field(default=10, ge=0, le=120)
    max_annotations: int = Field(default=25, ge=1, le=200)
    max_points_per_segment: int = Field(default=250, ge=20, le=2000)
    provider: str = Field(default="dry_run", min_length=1, max_length=80)
    model: Optional[str] = None


class DynamicPredictionCorrectionRequest(BaseModel):
    corrected_response_markdown: str = Field(min_length=1)
    corrected_response_json: Dict[str, Any] = Field(default_factory=dict)
    corrected_confidence: Optional[str] = None
    note: Optional[str] = None
    validated_for_dataset: bool = False


def require_analysis(conn: Connection, analysis_id: str) -> dict[str, Any]:
    analysis = get_analysis(conn, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


def _downsample(values: list[Any], max_points: int) -> list[Any]:
    if len(values) <= max_points:
        return values
    step = max(1, len(values) // max_points)
    return values[::step][:max_points]


def _channel_stats(values: list[float]) -> dict[str, Any]:
    finite = [value for value in values if value == value]
    if not finite:
        return {"count": 0}
    return {
        "count": len(finite),
        "min": min(finite),
        "max": max(finite),
        "mean": statistics.fmean(finite),
        "stdev": statistics.pstdev(finite) if len(finite) > 1 else 0,
        "first": finite[0],
        "last": finite[-1],
        "amplitude": max(finite) - min(finite),
    }


def _channel_metrics(time_values: list[Any], values: list[Optional[float]]) -> dict[str, Any]:
    pairs = [
        (float(time_value), float(value))
        for time_value, value in zip(time_values, values)
        if time_value is not None and value is not None and value == value
    ]
    if not pairs:
        return {}
    peak_time, peak_value = max(pairs, key=lambda item: abs(item[1]))
    first_time, first_value = pairs[0]
    last_time, last_value = pairs[-1]
    elapsed = last_time - first_time
    return {
        "peak_abs": abs(peak_value),
        "peak_abs_value": peak_value,
        "peak_abs_time_sec": peak_time,
        "delta": last_value - first_value,
        "slope_per_sec": (last_value - first_value) / elapsed if elapsed else None,
    }


def model_payload(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _segment_signal_context(
    file_row: dict[str, Any],
    annotation: dict[str, Any],
    channels: list[str],
    before_sec: float,
    after_sec: float,
    max_points: int,
) -> dict[str, Any]:
    payload = load_resampled_payload(file_row)
    time_values = [numeric_or_none(value) for value in get_time_values(payload)]
    resampled = get_resampled_channels(payload)
    start = max(0, float(annotation["start_time_sec"]) - before_sec)
    end = float(annotation["end_time_sec"]) + after_sec
    indices = [
        index
        for index, value in enumerate(time_values)
        if value is not None and start <= value <= end
    ]
    indices = _downsample(indices, max_points)
    time_slice = [time_values[index] for index in indices]
    channel_payload = {}
    for channel in channels:
        values = values_for_channel(resampled, channel)
        numeric_values = [
            numeric_or_none(values[index]) if index < len(values) else None
            for index in indices
        ]
        finite_values = [value for value in numeric_values if value is not None]
        channel_payload[channel] = {
            "unit": resampled.get(channel, {}).get("unit") if isinstance(resampled.get(channel), dict) else None,
            "stats": _channel_stats(finite_values),
            "metrics": _channel_metrics(time_slice, numeric_values),
            "values": numeric_values,
        }
    return {
        "time": time_slice,
        "channels": channel_payload,
    }


def build_dynamic_context(
    conn: Connection,
    analysis_id: str,
    payload: DynamicContextRequest,
) -> dict[str, Any]:
    analysis = require_analysis(conn, analysis_id)
    annotations = list_annotations(conn, analysis_id)
    if payload.labels:
        labels = set(payload.labels)
        annotations = [item for item in annotations if item["label"] in labels]
    if payload.file_ids:
        file_ids = set(payload.file_ids)
        annotations = [item for item in annotations if item["file_id"] in file_ids]
    annotations = annotations[: payload.max_segments]
    files = {
        item["file_id"]: item
        for item in list_analysis_files(conn, analysis_id, limit=10000)
        if item.get("resampled_json_path")
    }
    segments = []
    skipped_segments = []
    for annotation in annotations:
        file_row = files.get(annotation["file_id"]) or get_analysis_file(conn, analysis_id, annotation["file_id"])
        if not file_row or not file_row.get("resampled_json_path"):
            skipped_segments.append({"annotation_id": annotation["annotation_id"], "reason": "resampled JSON missing"})
            continue
        try:
            signal_context = _segment_signal_context(
                file_row,
                annotation,
                payload.channels,
                payload.context_before_sec,
                payload.context_after_sec,
                payload.max_points_per_segment,
            )
        except HTTPException as exc:
            skipped_segments.append({"annotation_id": annotation["annotation_id"], "reason": str(exc.detail)})
            continue
        segments.append(
            {
                "annotation_id": annotation["annotation_id"],
                "file_id": annotation["file_id"],
                "file_name": annotation["resampled_json_name"] or annotation["source_dxd_name"],
                "recorded_at": annotation.get("recorded_at"),
                "label": annotation["label"],
                "start_time_sec": annotation["start_time_sec"],
                "end_time_sec": annotation["end_time_sec"],
                "duration_sec": annotation["duration_sec"],
                "comment": annotation.get("comment"),
                "signal_context": signal_context,
            }
        )
    return {
        "analysis": {
            "analysis_id": analysis_id,
            "name": analysis["name"],
            "kind": analysis["kind"],
        },
            "request": model_payload(payload),
        "summary": {
            "file_count": len({item["file_id"] for item in segments}),
            "segment_count": len(segments),
            "skipped_segment_count": len(skipped_segments),
            "channels": payload.channels,
            "labels": sorted({item["label"] for item in segments}),
        },
        "segments": segments,
        "skipped_segments": skipped_segments,
    }


def dry_run_markdown(context: dict[str, Any], payload: DynamicContextRequest) -> str:
    summary = context["summary"]
    remarkable_segments = []
    for segment in context.get("segments", [])[:5]:
        channel_summaries = []
        channels = segment.get("signal_context", {}).get("channels", {})
        for channel, channel_context in channels.items():
            stats = channel_context.get("stats", {})
            metrics = channel_context.get("metrics", {})
            channel_summaries.append(
                f"{channel}: min={stats.get('min')}, max={stats.get('max')}, "
                f"amplitude={stats.get('amplitude')}, pic_abs={metrics.get('peak_abs')}"
            )
        remarkable_segments.append(
            {
                "annotation_id": segment.get("annotation_id"),
                "file_name": segment.get("file_name"),
                "label": segment.get("label"),
                "time_window_sec": [segment.get("start_time_sec"), segment.get("end_time_sec")],
                "channel_summary": channel_summaries,
            }
        )
    structured_preview = {
        "synthese": "Dry-run: contexte construit, aucun provider LLM reel appele.",
        "segments_remarquables": remarkable_segments,
        "incoherences": [],
        "niveau_confiance": "non_evalue",
        "points_a_verifier": [
            "Verifier que les canaux selectionnes couvrent bien le protocole.",
            "Verifier les segments ignores avant tout appel LLM reel.",
        ],
    }
    return "\n".join(
        [
            "## Analyse dynamique - dry run",
            "",
            "Aucun provider LLM reel n'est appele dans cette V1. Cette sortie valide le protocole, le perimetre et le contexte structure.",
            "",
            f"- Segments: {summary['segment_count']}",
            f"- Fichiers: {summary['file_count']}",
            f"- Canaux: {', '.join(summary['channels']) if summary['channels'] else '-'}",
            f"- Labels: {', '.join(summary['labels']) if summary['labels'] else '-'}",
            "",
            "### Prompt opératoire",
            payload.user_prompt,
            "",
            "### Sortie structurée prévue",
            "```json",
            json.dumps(structured_preview, ensure_ascii=False, indent=2),
            "```",
        ]
    )


def prediction_response_for_segment(
    dynamic_analysis: dict[str, Any],
    segment: dict[str, Any],
    user_prompt: str,
) -> dict[str, Any]:
    channels = segment.get("signal_context", {}).get("channels", {})
    channel_summaries = []
    for channel, channel_context in channels.items():
        stats = channel_context.get("stats", {})
        metrics = channel_context.get("metrics", {})
        channel_summaries.append(
            {
                "channel": channel,
                "unit": channel_context.get("unit"),
                "count": stats.get("count"),
                "min": stats.get("min"),
                "max": stats.get("max"),
                "mean": stats.get("mean"),
                "amplitude": stats.get("amplitude"),
                "peak_abs": metrics.get("peak_abs"),
                "peak_abs_time_sec": metrics.get("peak_abs_time_sec"),
                "delta": metrics.get("delta"),
                "slope_per_sec": metrics.get("slope_per_sec"),
            }
        )
    return {
        "synthese": "Dry-run: prediction multimodale non appelee, contexte annotation pret.",
        "annotation_id": segment.get("annotation_id"),
        "label_category": dynamic_analysis.get("label_category"),
        "segment": {
            "file_name": segment.get("file_name"),
            "start_time_sec": segment.get("start_time_sec"),
            "end_time_sec": segment.get("end_time_sec"),
            "duration_sec": segment.get("duration_sec"),
        },
        "channels": channel_summaries,
        "indicators": dynamic_analysis.get("indicators") or [],
        "incoherences": [],
        "niveau_confiance": "non_evalue",
        "points_a_verifier": [
            "Brancher le provider LLM multimodal pour produire l'interpretation finale.",
            "Ajouter l'artefact image du segment quand le pipeline multimodal sera actif.",
        ],
        "prompt_operatoire": user_prompt,
    }


def prediction_markdown(response: dict[str, Any]) -> str:
    lines = [
        "## Prediction annotation - dry run",
        "",
        response.get("synthese") or "",
        "",
        f"- Annotation: {response.get('annotation_id') or '-'}",
        f"- Categorie label: {response.get('label_category') or '-'}",
    ]
    for channel in response.get("channels") or []:
        lines.append(
            "- "
            + str(channel.get("channel") or "-")
            + f": amplitude={channel.get('amplitude')}, pic_abs={channel.get('peak_abs')}"
        )
    return "\n".join(lines)


@router.get("/prompts")
def list_prompts_endpoint(analysis_id: str, conn: Connection = Depends(get_db)):
    require_analysis(conn, analysis_id)
    return {"items": list_prompts(conn, analysis_id)}


@router.post("/prompts")
def create_prompt_endpoint(
    analysis_id: str,
    payload: DynamicPromptRequest,
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    return create_prompt(
        conn,
        analysis_id=analysis_id,
        name=payload.name.strip(),
        description=(payload.description or "").strip() or None,
        system_prompt=payload.system_prompt,
        user_prompt=payload.user_prompt,
        required_channels=payload.required_channels,
        output_schema=payload.output_schema,
    )


@router.get("")
def list_dynamic_analyses_endpoint(analysis_id: str, conn: Connection = Depends(get_db)):
    require_analysis(conn, analysis_id)
    return {"items": list_dynamic_analyses(conn, analysis_id)}


@router.post("")
def create_dynamic_analysis_endpoint(
    analysis_id: str,
    payload: DynamicAnalysisDefinitionRequest,
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    if not payload.selected_channels:
        raise HTTPException(status_code=400, detail="At least one channel is required")
    return create_dynamic_analysis(
        conn,
        analysis_id=analysis_id,
        name=payload.name.strip(),
        system_prompt=payload.system_prompt,
        selected_channels=payload.selected_channels,
        indicators=payload.indicators,
        label_category=payload.label_category.strip(),
        output_schema=payload.output_schema,
    )


@router.get("/{dynamic_analysis_id}/predictions")
def list_dynamic_predictions_endpoint(
    analysis_id: str,
    dynamic_analysis_id: str,
    conn: Connection = Depends(get_db),
):
    if get_dynamic_analysis(conn, analysis_id, dynamic_analysis_id) is None:
        raise HTTPException(status_code=404, detail="Dynamic analysis not found")
    return {"items": list_predictions(conn, dynamic_analysis_id)}


@router.post("/{dynamic_analysis_id}/predictions")
def create_dynamic_predictions_endpoint(
    analysis_id: str,
    dynamic_analysis_id: str,
    payload: DynamicPredictionRequest,
    conn: Connection = Depends(get_db),
):
    dynamic_analysis = get_dynamic_analysis(conn, analysis_id, dynamic_analysis_id)
    if dynamic_analysis is None:
        raise HTTPException(status_code=404, detail="Dynamic analysis not found")
    context_payload = DynamicContextRequest(
        name=dynamic_analysis["name"],
        provider=payload.provider,
        model=payload.model,
        system_prompt=dynamic_analysis["system_prompt"],
        user_prompt=payload.user_prompt,
        channels=dynamic_analysis["selected_channels"],
        labels=[dynamic_analysis["label_category"]],
        output_schema=dynamic_analysis["output_schema"],
        context_before_sec=payload.context_before_sec,
        context_after_sec=payload.context_after_sec,
        max_segments=payload.max_annotations,
        max_points_per_segment=payload.max_points_per_segment,
    )
    context = build_dynamic_context(conn, analysis_id, context_payload)
    predictions = []
    for segment in context.get("segments", []):
        response = prediction_response_for_segment(dynamic_analysis, segment, payload.user_prompt)
        predictions.append(
            create_or_replace_prediction(
                conn,
                dynamic_analysis_id=dynamic_analysis_id,
                annotation_id=segment["annotation_id"],
                provider=payload.provider,
                model=payload.model,
                status="dry_run",
                input_context={
                    "analysis": context["analysis"],
                    "request": context["request"],
                    "segment": segment,
                },
                input_artifact_path=None,
                response_json=response,
                response_markdown=prediction_markdown(response),
                confidence=response.get("niveau_confiance"),
            )
        )
    return {
        "dynamic_analysis": dynamic_analysis,
        "context_summary": context["summary"],
        "items": predictions,
        "skipped_segments": context.get("skipped_segments", []),
    }


@router.get("/predictions/{prediction_id}/corrections")
def list_dynamic_prediction_corrections_endpoint(
    analysis_id: str,
    prediction_id: str,
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    prediction = get_prediction(conn, prediction_id)
    if prediction is None:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return {"items": list_prediction_corrections(conn, prediction_id)}


@router.post("/predictions/{prediction_id}/corrections")
def create_dynamic_prediction_correction_endpoint(
    analysis_id: str,
    prediction_id: str,
    payload: DynamicPredictionCorrectionRequest,
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    correction = create_prediction_correction(
        conn,
        prediction_id=prediction_id,
        corrected_response_json=payload.corrected_response_json,
        corrected_response_markdown=payload.corrected_response_markdown,
        corrected_confidence=payload.corrected_confidence,
        note=payload.note,
        validated_for_dataset=payload.validated_for_dataset,
    )
    if correction is None:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return correction


@router.post("/context")
def build_context_endpoint(
    analysis_id: str,
    payload: DynamicContextRequest,
    conn: Connection = Depends(get_db),
):
    return build_dynamic_context(conn, analysis_id, payload)


@router.post("/run")
def create_run_endpoint(
    analysis_id: str,
    payload: DynamicContextRequest,
    conn: Connection = Depends(get_db),
):
    context = build_dynamic_context(conn, analysis_id, payload)
    prompt_id = payload.prompt_id
    if prompt_id and get_prompt(conn, analysis_id, prompt_id) is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    response = dry_run_markdown(context, payload)
    return create_run(
        conn,
        analysis_id=analysis_id,
        prompt_id=prompt_id,
        name=payload.name.strip(),
        provider=payload.provider,
        model=payload.model,
        request=model_payload(payload),
        context=context,
        response_markdown=response,
        status="dry_run" if payload.provider == "dry_run" else "queued_provider_not_configured",
    )


@router.get("/runs")
def list_runs_endpoint(analysis_id: str, conn: Connection = Depends(get_db)):
    require_analysis(conn, analysis_id)
    return {"items": list_runs(conn, analysis_id)}


@router.get("/runs/{run_id}")
def get_run_endpoint(analysis_id: str, run_id: str, conn: Connection = Depends(get_db)):
    require_analysis(conn, analysis_id)
    run = get_run(conn, analysis_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Dynamic analysis run not found")
    return run


@router.delete("/runs/{run_id}")
def delete_run_endpoint(analysis_id: str, run_id: str, conn: Connection = Depends(get_db)):
    require_analysis(conn, analysis_id)
    if not delete_run(conn, analysis_id, run_id):
        raise HTTPException(status_code=404, detail="Dynamic analysis run not found")
    return {"status": "ok", "deleted": run_id}


@router.get("/runs/{run_id}/versions")
def list_run_versions_endpoint(analysis_id: str, run_id: str, conn: Connection = Depends(get_db)):
    require_analysis(conn, analysis_id)
    versions = list_run_versions(conn, analysis_id, run_id)
    if versions is None:
        raise HTTPException(status_code=404, detail="Dynamic analysis run not found")
    return {"items": versions}


@router.post("/runs/{run_id}/versions")
def create_run_version_endpoint(
    analysis_id: str,
    run_id: str,
    payload: DynamicRunVersionRequest,
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    version = create_run_version(
        conn,
        analysis_id=analysis_id,
        run_id=run_id,
        response_markdown=payload.response_markdown,
        confidence=payload.confidence,
        note=payload.note,
        validated_for_dataset=payload.validated_for_dataset,
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Dynamic analysis run not found")
    return version
