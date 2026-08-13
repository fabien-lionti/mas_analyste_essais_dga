from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import statistics
import urllib.error
import urllib.request
from pathlib import Path
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
    delete_dynamic_analysis,
    delete_run,
    get_dynamic_analysis,
    get_dynamic_analysis_by_name,
    get_prompt,
    get_prediction,
    get_run,
    list_dynamic_analyses,
    list_prediction_corrections,
    list_predictions,
    list_prompts,
    list_run_versions,
    list_runs,
    update_dynamic_analysis,
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
    protocol_name: str = Field(default="", max_length=160)
    description: Optional[str] = None
    system_prompt: str = Field(min_length=1)
    selected_channels: List[str] = Field(default_factory=list)
    selected_labels: List[str] = Field(default_factory=list)
    indicators: List[Dict[str, Any]] = Field(default_factory=list)
    label_category: str = Field(default="", max_length=160)
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
    corrected_analysis_text: str = ""
    corrected_analysis_note: str = ""
    corrected_summary_text: str = ""
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


def _extract_tag(text: str, tag: str) -> str:
    match = re.search(rf"<{tag}>(.*?)</{tag}>", text or "", flags=re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def parse_tagged_prediction(text: str) -> dict[str, str]:
    analysis_text = _extract_tag(text, "analyse")
    analysis_note = _extract_tag(text, "note_analyse")
    summary_text = _extract_tag(text, "synthese")
    if not analysis_text and not summary_text:
        analysis_text = (text or "").strip()
    if not summary_text:
        summary_text = analysis_text.splitlines()[0][:240] if analysis_text else ""
    return {
        "analysis_text": analysis_text,
        "analysis_note": analysis_note,
        "summary_text": summary_text,
    }


def tagged_prediction_markdown(parts: dict[str, str]) -> str:
    return "\n".join(
        [
            "## Synthèse",
            parts.get("summary_text") or "-",
            "",
            "## Analyse",
            parts.get("analysis_text") or "-",
            "",
            "## Note d'analyse",
            parts.get("analysis_note") or "-",
        ]
    )


def dynamic_artifact_dir(analysis_id: str, dynamic_analysis_id: str) -> Path:
    root = Path("app_v2/app/static/generated/dynamic_analysis_artifacts")
    path = root / analysis_id / dynamic_analysis_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def generate_segment_artifact(
    *,
    analysis_id: str,
    dynamic_analysis_id: str,
    segment: dict[str, Any],
) -> str:
    artifact_dir = dynamic_artifact_dir(analysis_id, dynamic_analysis_id)
    output_path = artifact_dir / f"{segment['annotation_id']}.png"
    signal_context = segment.get("signal_context") or {}
    time_values = signal_context.get("time") or []
    channels = signal_context.get("channels") or {}
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(10, 5), dpi=130)
        for channel, payload in channels.items():
            ax.plot(time_values, payload.get("values") or [], label=channel, linewidth=1.2)
        ax.axvspan(float(segment["start_time_sec"]), float(segment["end_time_sec"]), color="#f59e0b", alpha=0.18)
        ax.set_title(f"{segment.get('label') or ''} - {segment.get('file_name') or segment['annotation_id']}")
        ax.set_xlabel("Temps (s)")
        ax.grid(True, alpha=0.25)
        if channels:
            ax.legend(loc="best", fontsize=8)
        fig.tight_layout()
        fig.savefig(output_path)
        plt.close(fig)
    except Exception:
        svg_path = artifact_dir / f"{segment['annotation_id']}.svg"
        svg_path.write_text(
            "\n".join(
                [
                    '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="420">',
                    '<rect width="100%" height="100%" fill="#ffffff"/>',
                    '<text x="24" y="40" font-family="Arial" font-size="18" fill="#17202c">Artefact analyse dynamique</text>',
                    f'<text x="24" y="72" font-family="Arial" font-size="13" fill="#657386">Annotation: {segment["annotation_id"]}</text>',
                    f'<text x="24" y="96" font-family="Arial" font-size="13" fill="#657386">Fichier: {segment.get("file_name") or "-"}</text>',
                    f'<text x="24" y="120" font-family="Arial" font-size="13" fill="#657386">Segment: {segment.get("start_time_sec")} - {segment.get("end_time_sec")} s</text>',
                    "</svg>",
                ]
            ),
            encoding="utf-8",
        )
        return str(svg_path)
    return str(output_path)


def image_inline_data(path: str | Path) -> tuple[str, str]:
    file_path = Path(path)
    mime_type = mimetypes.guess_type(str(file_path))[0] or "image/png"
    if not mime_type.startswith("image/"):
        mime_type = "image/png"
    return mime_type, base64.b64encode(file_path.read_bytes()).decode("ascii")


def call_gemini_multimodal(*, artifact_path: str, prompt: str, model: str | None = None) -> dict[str, Any]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY is not configured")
    resolved_model = model or os.environ.get("GEMINI_DYNAMIC_ANALYSIS_MODEL") or "gemini-3-flash-preview"
    mime_type, image_b64 = image_inline_data(artifact_path)
    body = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"inline_data": {"mime_type": mime_type, "data": image_b64}},
                    {"text": prompt},
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
        },
    }
    request = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{resolved_model}:generateContent",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
            "User-Agent": "mas-analyste-essais-dga/0.1",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=502, detail=f"Gemini API HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise HTTPException(status_code=502, detail=f"Gemini API request failed: {exc.reason}") from exc
    try:
        candidate = response_data["candidates"][0]
        text = "".join(str(part.get("text") or "") for part in candidate["content"]["parts"])
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Malformed Gemini response: {exc}") from exc
    return {"text": text, "model": resolved_model, "raw_response": response_data}


def dynamic_llm_prompt(dynamic_analysis: dict[str, Any], segment: dict[str, Any], user_prompt: str) -> str:
    context = {
        "dynamic_analysis": {
            "name": dynamic_analysis.get("name"),
            "selected_labels": dynamic_analysis.get("selected_labels") or [dynamic_analysis.get("label_category")],
            "selected_channels": dynamic_analysis.get("selected_channels") or [],
            "indicators": dynamic_analysis.get("indicators") or [],
        },
        "segment": {
            "annotation_id": segment.get("annotation_id"),
            "file_name": segment.get("file_name"),
            "label": segment.get("label"),
            "start_time_sec": segment.get("start_time_sec"),
            "end_time_sec": segment.get("end_time_sec"),
            "duration_sec": segment.get("duration_sec"),
        },
        "channel_metrics": {
            name: payload.get("metrics") or {}
            for name, payload in (segment.get("signal_context", {}).get("channels") or {}).items()
        },
    }
    return "\n\n".join(
        [
            dynamic_analysis.get("system_prompt") or "",
            user_prompt,
            "Contexte structure fourni par l'application:",
            json.dumps(context, ensure_ascii=False, indent=2),
            "Réponds uniquement avec ces balises:",
            "<analyse>...</analyse>",
            "<note_analyse>...</note_analyse>",
            "<synthese>...</synthese>",
        ]
    )


def create_prediction_for_segment(
    conn: Connection,
    *,
    analysis_id: str,
    dynamic_analysis: dict[str, Any],
    segment: dict[str, Any],
    payload: DynamicPredictionRequest,
    context: dict[str, Any],
) -> dict[str, Any]:
    artifact_path = generate_segment_artifact(
        analysis_id=analysis_id,
        dynamic_analysis_id=dynamic_analysis["dynamic_analysis_id"],
        segment=segment,
    )
    if payload.provider == "gemini":
        gemini = call_gemini_multimodal(
            artifact_path=artifact_path,
            prompt=dynamic_llm_prompt(dynamic_analysis, segment, payload.user_prompt),
            model=payload.model,
        )
        parts = parse_tagged_prediction(gemini["text"])
        model = gemini["model"]
        status = "finished"
    else:
        analysis_lines = [
            "Dry-run: le provider LLM multimodal n'est pas appele.",
            f"Annotation {segment.get('annotation_id')} sur {segment.get('file_name')}.",
        ]
        for channel, channel_context in (segment.get("signal_context", {}).get("channels") or {}).items():
            metrics = channel_context.get("metrics") or {}
            analysis_lines.append(
                f"{channel}: pic absolu {metrics.get('peak_abs')}, delta {metrics.get('delta')}."
            )
        parts = {
            "analysis_text": "\n".join(analysis_lines),
            "analysis_note": "Artefact visuel genere et contexte segment sauvegarde.",
            "summary_text": "Dry-run: contexte pret pour prediction LLM multimodale.",
        }
        model = payload.model
        status = "dry_run"
    response_json = {
        "analyse": parts["analysis_text"],
        "note_analyse": parts["analysis_note"],
        "synthese": parts["summary_text"],
    }
    return create_or_replace_prediction(
        conn,
        dynamic_analysis_id=dynamic_analysis["dynamic_analysis_id"],
        annotation_id=segment["annotation_id"],
        provider=payload.provider,
        model=model,
        status=status,
        input_context={
            "analysis": context["analysis"],
            "request": context["request"],
            "segment": segment,
        },
        input_artifact_path=artifact_path,
        response_json=response_json,
        response_markdown=tagged_prediction_markdown(parts),
        analysis_text=parts["analysis_text"],
        analysis_note=parts["analysis_note"],
        summary_text=parts["summary_text"],
        confidence=None,
    )


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
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Dynamic analysis name is required")
    if not payload.selected_channels:
        raise HTTPException(status_code=400, detail="At least one channel is required")
    selected_labels = [label for label in payload.selected_labels if label]
    label_category = payload.label_category.strip() or (selected_labels[0] if selected_labels else "")
    if not selected_labels and label_category:
        selected_labels = [label_category]
    if not selected_labels:
        raise HTTPException(status_code=400, detail="At least one segment label is required")
    existing = get_dynamic_analysis_by_name(conn, analysis_id, name)
    if existing is not None:
        return update_dynamic_analysis(
            conn,
            analysis_id=analysis_id,
            dynamic_analysis_id=existing["dynamic_analysis_id"],
            name=name,
            protocol_name=payload.protocol_name.strip(),
            description=(payload.description or "").strip() or None,
            system_prompt=payload.system_prompt,
            selected_channels=payload.selected_channels,
            selected_labels=selected_labels,
            indicators=payload.indicators,
            label_category=label_category,
            output_schema=payload.output_schema,
        )
    return create_dynamic_analysis(
        conn,
        analysis_id=analysis_id,
        name=name,
        protocol_name=payload.protocol_name.strip(),
        description=(payload.description or "").strip() or None,
        system_prompt=payload.system_prompt,
        selected_channels=payload.selected_channels,
        selected_labels=selected_labels,
        indicators=payload.indicators,
        label_category=label_category,
        output_schema=payload.output_schema,
    )


@router.patch("/{dynamic_analysis_id}")
def update_dynamic_analysis_endpoint(
    analysis_id: str,
    dynamic_analysis_id: str,
    payload: DynamicAnalysisDefinitionRequest,
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    if not payload.selected_channels:
        raise HTTPException(status_code=400, detail="At least one channel is required")
    selected_labels = [label for label in payload.selected_labels if label]
    label_category = payload.label_category.strip() or (selected_labels[0] if selected_labels else "")
    if not selected_labels and label_category:
        selected_labels = [label_category]
    if not selected_labels:
        raise HTTPException(status_code=400, detail="At least one segment label is required")
    updated = update_dynamic_analysis(
        conn,
        analysis_id=analysis_id,
        dynamic_analysis_id=dynamic_analysis_id,
        name=payload.name.strip(),
        protocol_name=payload.protocol_name.strip(),
        description=(payload.description or "").strip() or None,
        system_prompt=payload.system_prompt,
        selected_channels=payload.selected_channels,
        selected_labels=selected_labels,
        indicators=payload.indicators,
        label_category=label_category,
        output_schema=payload.output_schema,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Dynamic analysis not found")
    return updated


@router.delete("/{dynamic_analysis_id}")
def delete_dynamic_analysis_endpoint(
    analysis_id: str,
    dynamic_analysis_id: str,
    conn: Connection = Depends(get_db),
):
    require_analysis(conn, analysis_id)
    if not delete_dynamic_analysis(conn, analysis_id, dynamic_analysis_id):
        raise HTTPException(status_code=404, detail="Dynamic analysis not found")
    return {"status": "ok", "deleted": dynamic_analysis_id}


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
        labels=dynamic_analysis.get("selected_labels") or [dynamic_analysis["label_category"]],
        output_schema=dynamic_analysis["output_schema"],
        context_before_sec=payload.context_before_sec,
        context_after_sec=payload.context_after_sec,
        max_segments=payload.max_annotations,
        max_points_per_segment=payload.max_points_per_segment,
    )
    context = build_dynamic_context(conn, analysis_id, context_payload)
    predictions = []
    for segment in context.get("segments", []):
        predictions.append(
            create_prediction_for_segment(
                conn,
                analysis_id=analysis_id,
                dynamic_analysis=dynamic_analysis,
                segment=segment,
                payload=payload,
                context=context,
            )
        )
    return {
        "dynamic_analysis": dynamic_analysis,
        "context_summary": context["summary"],
        "items": predictions,
        "skipped_segments": context.get("skipped_segments", []),
    }


@router.post("/{dynamic_analysis_id}/predictions/{annotation_id}")
def create_dynamic_prediction_for_annotation_endpoint(
    analysis_id: str,
    dynamic_analysis_id: str,
    annotation_id: str,
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
        labels=dynamic_analysis.get("selected_labels") or [dynamic_analysis["label_category"]],
        file_ids=[],
        output_schema=dynamic_analysis["output_schema"],
        context_before_sec=payload.context_before_sec,
        context_after_sec=payload.context_after_sec,
        max_segments=payload.max_annotations,
        max_points_per_segment=payload.max_points_per_segment,
    )
    context = build_dynamic_context(conn, analysis_id, context_payload)
    segment = next((item for item in context.get("segments", []) if item.get("annotation_id") == annotation_id), None)
    if segment is None:
        raise HTTPException(status_code=404, detail="Annotation not found in dynamic analysis scope")
    prediction = create_prediction_for_segment(
        conn,
        analysis_id=analysis_id,
        dynamic_analysis=dynamic_analysis,
        segment=segment,
        payload=payload,
        context=context,
    )
    return {"dynamic_analysis": dynamic_analysis, "item": prediction}


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
        corrected_analysis_text=payload.corrected_analysis_text,
        corrected_analysis_note=payload.corrected_analysis_note,
        corrected_summary_text=payload.corrected_summary_text,
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
