from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Sequence
import re
import io
import sqlite3
import subprocess
import sys
from datetime import datetime
from functools import lru_cache

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Body
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from mas_essais.domain.dxd_schema import (
    channel_sort_key,
    get_resampled_channels,
    get_time_values,
    normalize_feature_schema,
    normalize_raw_json_schema,
)
from mas_essais.db.sqlite import (
    DEFAULT_DB_PATH,
    connect as connect_pipeline_db,
    database_ready,
    list_file_catalog,
    read_dataframe_table,
    read_json_artifact,
    read_resampled_json,
    read_segment_annotation_label_counts,
    read_segment_annotations_filtered,
    read_window_quality_filtered,
    read_window_quality_series,
    write_dataframe_table,
)
from mas_essais.analysis.retournement import (
    ProviderRateLimitError,
    RolloverAnalysisError,
    analyze_curve,
    check_quota,
    compute_segment_metrics,
    crop_segment_image,
    create_analyse_retournement_version,
    delete_analyse_retournement,
    format_analysis_markdown,
    get_analyse_retournement,
    get_dernieres_analyses,
    save_analyse_retournement,
)
from mas_essais.ml.segment_cnn.model import MODEL_METADATA_PATH, MODEL_SUMMARY_PATH, MODEL_WEIGHTS_PATH, Simple1DCNN, load_model_summary, predict_file, generate_active_learning_cache, MODEL_PROGRESS_PATH, MODEL_DIR, write_json_atomic
from mas_essais.paths import PROJECT_ROOT

BASE_DIR = PROJECT_ROOT
load_dotenv(BASE_DIR / ".env")
RAW_JSON_DIR = BASE_DIR / "selected_dxd_json_resampled"
ANNOTATION_DIR = BASE_DIR / "manual_segment_annotations"
SEGMENT_ANNOTATION_CSV = ANNOTATION_DIR / "segments_annotations.csv"
SEGMENT_ANNOTATION_JSONL = ANNOTATION_DIR / "segments_annotations.jsonl"
DRIFT_INDEX_PATH = BASE_DIR / "drift_index.json"
STATIC_DIR = BASE_DIR / "static"
DXD_DATA_DIR = BASE_DIR / "data"
DATASET_INDEX_PATH = BASE_DIR / "dataset_index.json"
PIPELINE_DB_PATH = DEFAULT_DB_PATH
CORRELATION_ANOMALY_INDEX_PATH = BASE_DIR / "correlation_anomaly_index.json"
WINDOW_QUALITY_INDEX_PATH = BASE_DIR / "window_quality_index.csv"
WINDOW_QUALITY_SUMMARY_PATH = BASE_DIR / "window_quality_summary.json"
WINDOW_CLUSTER_INDEX_PATH = BASE_DIR / "window_cluster_index.csv"
WINDOW_CLUSTER_SUMMARY_PATH = BASE_DIR / "window_cluster_summary.json"
SPEED_DAY_SUMMARY_PATH = BASE_DIR / "speed_day_summary.csv"
SPEED_DAY_SUMMARY_JSON_PATH = BASE_DIR / "speed_day_summary.json"
DRIFT_COHERENCE_TRAIN_PROGRESS_PATH = ANNOTATION_DIR / "drift_coherence_training_progress.json"
DRIFT_COHERENCE_TRAIN_LOG_PATH = ANNOTATION_DIR / "drift_coherence_training.log"
DRIFT_RUN_PREFIXES = ("dynamic_channel_coherence",)

RESIDUAL_DRIFT_FAMILIES = {
    "accel_kinematic": {
        "label": "Accélération / cinématique",
        "metrics": ["r_ax_rms", "r_ay_rms", "r_ay_simple_rms"],
    },
    "distance_curvature": {
        "label": "Distance / courbure",
        "metrics": ["r_dist_rms", "r_kappa_rms"],
    },
    "gps": {
        "label": "GPS",
        "metrics": [
            "r_gps_pos_rmse",
            "r_gps_pos_aligned_rmse",
            "r_gps_speed_rms",
            "r_gps_body_speed_rms",
            "r_gps_yaw_rms",
        ],
    },
    "wheel_imu": {
        "label": "Roues / IMU",
        "metrics": ["r_wheel_rms", "r_imu_x_rms", "r_imu_y_rms", "r_imu_z_rms"],
    },
}

SEGMENT_CNN_MODEL_SUMMARY_PATH = MODEL_SUMMARY_PATH
SEGMENT_CNN_MODEL_WEIGHTS_PATH = MODEL_WEIGHTS_PATH
SEGMENT_CNN_MODEL_METADATA_PATH = MODEL_METADATA_PATH

_SEGMENT_CNN_CACHE: tuple[Simple1DCNN, dict[str, Any]] | None = None
_SEGMENT_CNN_CACHE_SIGNATURE: tuple[int, int] | None = None

EXPLORATION_SIGNALS = [
    {"value": "vehicle.vx", "label": "vx"},
    {"value": "vehicle.vy", "label": "vy"},
    {"value": "vehicle.ax", "label": "ax"},
    {"value": "vehicle.ay", "label": "ay"},
    {"value": "vehicle.axy", "label": "axy"},
    {"value": "WheelSteer_S1 (_)", "label": "steer S1"},
    {"value": "WheelSteer_S2 (_)", "label": "steer S2"},
]


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def json_safe_value(v: Any):
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        if not np.isfinite(v):
            return None
        return float(v)
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    return v


def deep_json_safe(obj: Any):
    if isinstance(obj, dict):
        return {k: deep_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [deep_json_safe(v) for v in obj]
    return json_safe_value(obj)


def records_json_safe(df: pd.DataFrame) -> list[dict]:
    records = df.to_dict(orient="records")
    return [deep_json_safe(r) for r in records]


@lru_cache(maxsize=1)
def load_segment_annotations_frame() -> pd.DataFrame:
    db_df = read_dataframe_table("segment_annotations", PIPELINE_DB_PATH)
    if db_df is not None:
        return db_df
    if SEGMENT_ANNOTATION_CSV.exists():
        return pd.read_csv(SEGMENT_ANNOTATION_CSV)
    return pd.DataFrame()


def write_segment_annotations_frame(df: pd.DataFrame) -> None:
    ANNOTATION_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(SEGMENT_ANNOTATION_CSV, index=False)
    with open(SEGMENT_ANNOTATION_JSONL, "w", encoding="utf-8") as f:
        for row in records_json_safe(df):
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    if database_ready(PIPELINE_DB_PATH):
        with connect_pipeline_db(PIPELINE_DB_PATH) as conn:
            write_dataframe_table(conn, "segment_annotations", df)
            conn.commit()
    load_segment_annotations_frame.cache_clear()
    compute_exploration_boxplot_cached.cache_clear()


def append_segment_annotation(row: dict[str, Any]) -> dict[str, Any]:
    ANNOTATION_DIR.mkdir(parents=True, exist_ok=True)
    row = deep_json_safe(row)
    existing = load_segment_annotations_frame()
    new_df = pd.DataFrame([row])
    if existing.empty or "annotation_id" not in existing.columns:
        out = new_df
    else:
        annotation_id = str(row.get("annotation_id", ""))
        previous_annotation_id = row.get("previous_annotation_id")
        if previous_annotation_id:
            existing = existing[existing["annotation_id"].astype(str) != str(previous_annotation_id)]
        existing = existing[existing["annotation_id"].astype(str) != annotation_id]
        out = pd.concat([existing, new_df], ignore_index=True)
    write_segment_annotations_frame(out)
    return row


@lru_cache(maxsize=32)
def load_raw_json(json_name: str) -> dict:
    db_payload = read_resampled_json(json_name, PIPELINE_DB_PATH)
    if db_payload is not None:
        return normalize_raw_json_schema(db_payload)
    path = RAW_JSON_DIR / json_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="JSON file not found")
    return normalize_raw_json_schema(load_json(path))


def load_dataset_index() -> dict | None:
    db_payload = read_json_artifact("dataset_index", PIPELINE_DB_PATH)
    if db_payload is not None:
        return db_payload
    if not DATASET_INDEX_PATH.exists():
        return None
    return load_json(DATASET_INDEX_PATH)


def extract_date_from_name(name: str) -> str | None:
    m = re.search(r"(\d{4})_(\d{2})_(\d{2})", name)
    if m:
        yyyy, mm, dd = m.groups()
        return f"{yyyy}_{mm}_{dd}"
    return None


def load_correlation_anomaly_index() -> dict:
    db_payload = read_json_artifact("correlation_anomaly_index", PIPELINE_DB_PATH)
    if db_payload is not None:
        db_payload["status"] = "ok"
        db_payload["path"] = str(PIPELINE_DB_PATH)
        return db_payload
    if not CORRELATION_ANOMALY_INDEX_PATH.exists():
        return {
            "schema_version": "correlation_anomaly_index.v1",
            "status": "missing",
            "path": str(CORRELATION_ANOMALY_INDEX_PATH),
            "summary": {
                "n_files": 0,
                "n_tracks": 0,
                "n_baseline_pairs": 0,
                "n_anomalies": 0,
            },
            "baselines_by_track": {},
            "file_summaries": [],
            "anomalies": [],
        }
    data = load_json(CORRELATION_ANOMALY_INDEX_PATH)
    data["status"] = "ok"
    data["path"] = str(CORRELATION_ANOMALY_INDEX_PATH)
    return data


def load_window_quality_summary() -> dict:
    db_payload = read_json_artifact("window_quality_summary", PIPELINE_DB_PATH)
    if db_payload is not None:
        db_payload["status"] = "ok"
        db_payload["path"] = str(PIPELINE_DB_PATH)
        return db_payload
    if not WINDOW_QUALITY_SUMMARY_PATH.exists():
        return {
            "schema_version": "window_quality_index.v1",
            "status": "missing",
            "path": str(WINDOW_QUALITY_SUMMARY_PATH),
            "message": "Run build_window_quality_index.py first.",
            "n_windows": 0,
        }
    data = load_json(WINDOW_QUALITY_SUMMARY_PATH)
    data["status"] = "ok"
    data["path"] = str(WINDOW_QUALITY_SUMMARY_PATH)
    return data


def load_window_quality_frame() -> pd.DataFrame:
    db_table = "window_cluster_index"
    db_df = read_dataframe_table(db_table, PIPELINE_DB_PATH)
    if db_df is None:
        db_table = "window_quality_index"
        db_df = read_dataframe_table(db_table, PIPELINE_DB_PATH)
    if db_df is not None:
        return db_df
    path = WINDOW_CLUSTER_INDEX_PATH if WINDOW_CLUSTER_INDEX_PATH.exists() else WINDOW_QUALITY_INDEX_PATH
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Missing file: {WINDOW_QUALITY_INDEX_PATH.name}. Run build_window_quality_index.py first.",
        )
    return pd.read_csv(path)


def parse_acquisition_timestamp(row: pd.Series) -> pd.Timestamp | None:
    modified_at = row.get("modified_at")
    if modified_at is not None and str(modified_at).strip():
        ts = pd.to_datetime(modified_at, errors="coerce", utc=True)
        if pd.notna(ts):
            return ts

    date_value = row.get("date")
    if date_value is not None and str(date_value).strip():
        text = str(date_value).strip()
        text = text.replace("_", "-")
        ts = pd.to_datetime(text, errors="coerce", utc=True)
        if pd.notna(ts):
            return ts

    return None


def aggregate_series(values: pd.Series, aggregation: str) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    if numeric.empty:
        return None
    if aggregation == "mean":
        return float(numeric.mean())
    if aggregation == "p95":
        return float(numeric.quantile(0.95))
    return float(numeric.median())





def load_speed_day_summary_json() -> dict:
    db_payload = read_json_artifact("speed_day_summary", PIPELINE_DB_PATH)
    if db_payload is not None:
        db_payload["status"] = "ok"
        db_payload["path"] = str(PIPELINE_DB_PATH)
        return db_payload
    if not SPEED_DAY_SUMMARY_JSON_PATH.exists():
        return {
            "schema_version": "speed_day_summary.v1",
            "status": "missing",
            "path": str(SPEED_DAY_SUMMARY_JSON_PATH),
            "message": "Run build_speed_day_summary.py first.",
            "n_rows": 0,
        }
    data = load_json(SPEED_DAY_SUMMARY_JSON_PATH)
    data["status"] = "ok"
    data["path"] = str(SPEED_DAY_SUMMARY_JSON_PATH)
    return data


def load_speed_day_summary_frame() -> pd.DataFrame:
    db_df = read_dataframe_table("speed_day_summary_rows", PIPELINE_DB_PATH)
    if db_df is not None:
        return db_df
    if not SPEED_DAY_SUMMARY_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Missing file: {SPEED_DAY_SUMMARY_PATH.name}. Run build_speed_day_summary.py first.",
        )
    return pd.read_csv(SPEED_DAY_SUMMARY_PATH)


def list_json_files() -> list[dict]:
    db_items = list_file_catalog(PIPELINE_DB_PATH)
    if db_items:
        return db_items
    dataset_index = load_dataset_index()

    if dataset_index is not None:
        items = []
        for item in dataset_index.get("files", []):
            json_path = item.get("json_path")
            json_name = Path(json_path).name if json_path else f"{item.get('file', 'unknown')}.json"
            items.append(
                {
                    "file_id": item.get("file_id"),
                    "file": item.get("file"),
                    "json_name": json_name,
                    "date": item.get("date"),
                    "modified_at": item.get("modified_at"),
                    "can_open": item.get("can_open"),
                    "has_all_target_channels": item.get("has_all_target_channels"),
                    "has_resampled_data": item.get("has_resampled_data"),
                    "has_features": item.get("has_features"),
                    "target_missing_count": item.get("target_missing_count"),
                    "open_error": item.get("open_error", ""),
                }
            )
        return items

    if not RAW_JSON_DIR.exists():
        return [
            {
                "file_id": None,
                "file": path.name,
                "json_name": f"{path.stem}.json",
                "date": extract_date_from_name(path.name),
                "modified_at": None,
                "can_open": None,
                "has_all_target_channels": None,
                "has_resampled_data": False,
                "has_features": False,
                "target_missing_count": None,
                "open_error": "DXD brut present, JSON resample manquant. Lancer scripts/scan_dxd_channel_presence.py.",
            }
            for path in sorted(DXD_DATA_DIR.glob("*.dxd"))
        ]

    items = []
    for path in sorted(RAW_JSON_DIR.glob("*.json")):
        items.append(
            {
                "file_id": None,
                "file": f"{path.stem}.dxd",
                "json_name": path.name,
                "date": extract_date_from_name(path.name),
                "modified_at": None,
                "can_open": None,
                "has_all_target_channels": None,
                "has_resampled_data": None,
                "has_features": None,
                "target_missing_count": None,
                "open_error": "",
            }
        )
    if items:
        return items

    return [
        {
            "file_id": None,
            "file": path.name,
            "json_name": f"{path.stem}.json",
            "date": extract_date_from_name(path.name),
            "modified_at": None,
            "can_open": None,
            "has_all_target_channels": None,
            "has_resampled_data": False,
            "has_features": False,
            "target_missing_count": None,
            "open_error": "DXD brut present, JSON resample manquant. Lancer scripts/scan_dxd_channel_presence.py.",
        }
        for path in sorted(DXD_DATA_DIR.glob("*.dxd"))
    ]


def raw_json_to_dataframe(raw_data: dict) -> pd.DataFrame:
    time = get_time_values(raw_data)
    channels = get_resampled_channels(raw_data)

    if len(time) == 0:
        raise ValueError("Empty time array")

    df = pd.DataFrame({"time": pd.to_numeric(pd.Series(time), errors="coerce")})

    for ch_name, payload in channels.items():
        vals = payload.get("values", [])
        s = pd.to_numeric(pd.Series(vals), errors="coerce")
        n = min(len(df), len(s))
        if n > 0:
            df.loc[: n - 1, ch_name] = s.iloc[:n].to_numpy()

    return df


@lru_cache(maxsize=512)
def load_signal_series_frame(json_name: str, channel_names_key: tuple[str, ...]) -> pd.DataFrame:
    raw = load_raw_json(json_name)
    time = pd.to_numeric(pd.Series(get_time_values(raw)), errors="coerce")
    if len(time) == 0:
        raise ValueError("Empty time array")

    df = pd.DataFrame({"time": time})
    channels = get_resampled_channels(raw)
    for ch_name in channel_names_key:
        payload = channels.get(ch_name)
        if not isinstance(payload, dict) or "values" not in payload:
            continue
        values = pd.to_numeric(pd.Series(payload.get("values", [])), errors="coerce")
        n = min(len(df), len(values))
        if n > 0:
            df.loc[: n - 1, ch_name] = values.iloc[:n].to_numpy()
    return df


def downsample_frame(df: pd.DataFrame, max_points: int) -> pd.DataFrame:
    if len(df) > max_points:
        idx = np.linspace(0, len(df) - 1, max_points).astype(int)
        return df.iloc[idx]
    return df


def classify_ltr_risk(abs_ltr: float | None, warning_threshold: float, high_threshold: float, critical_threshold: float) -> str:
    if abs_ltr is None or not np.isfinite(abs_ltr):
        return "indisponible"
    if abs_ltr >= critical_threshold:
        return "critique"
    if abs_ltr >= high_threshold:
        return "eleve"
    if abs_ltr >= warning_threshold:
        return "surveillance"
    return "faible"



def get_available_resampled_channels(raw: dict) -> list[str]:
    return sorted(list(get_resampled_channels(raw).keys()), key=channel_sort_key)


def get_global_feature_columns(raw: dict) -> list[str]:
    by_channel = raw.get("features", {}).get("global", {}).get("by_channel", {})
    if not by_channel:
        return []

    first_channel = next(iter(by_channel.values()), {})
    return list(first_channel.keys())


def build_sliding_features_dataframe(raw: dict, requested_features: list[str]) -> pd.DataFrame:
    sliding = raw.get("features", {}).get("sliding", {})
    by_channel = sliding.get("by_channel", {})
    time = sliding.get("time", [])

    if len(time) == 0:
        raise ValueError("Empty sliding feature time array")

    df = pd.DataFrame({"time": pd.to_numeric(pd.Series(time), errors="coerce")})

    for channel_name, payload in by_channel.items():
        for feature_name, values in payload.items():
            col_name = f"{channel_name}::{feature_name}"
            if requested_features and col_name not in requested_features:
                continue

            s = pd.to_numeric(pd.Series(values), errors="coerce")
            n = min(len(df), len(s))
            if n > 0:
                df.loc[: n - 1, col_name] = s.iloc[:n].to_numpy()

    return df


def list_sliding_feature_columns(raw: dict) -> list[str]:
    sliding = raw.get("features", {}).get("sliding", {})
    by_channel = sliding.get("by_channel", {})

    cols = []
    for channel_name, payload in by_channel.items():
        for feature_name in payload.keys():
            cols.append(f"{channel_name}::{feature_name}")
    return sorted(cols, key=lambda col: (*channel_sort_key(col.split("::", 1)[0]), col))


# ------------------------------------------------------------------
# Drift cache helpers
# ------------------------------------------------------------------




def compute_segment_cnn_signature() -> tuple[int, int]:
    if not SEGMENT_CNN_MODEL_WEIGHTS_PATH.exists():
        return (0, 0)
    try:
        weight_mtime = SEGMENT_CNN_MODEL_WEIGHTS_PATH.stat().st_mtime_ns
    except Exception:
        weight_mtime = 0
    try:
        meta_mtime = SEGMENT_CNN_MODEL_METADATA_PATH.stat().st_mtime_ns
    except Exception:
        meta_mtime = 0
    return (int(weight_mtime), int(meta_mtime))


def load_segment_cnn_model(force_refresh: bool = False) -> tuple[Simple1DCNN, dict[str, Any]]:
    global _SEGMENT_CNN_CACHE, _SEGMENT_CNN_CACHE_SIGNATURE
    signature = compute_segment_cnn_signature()
    if force_refresh or _SEGMENT_CNN_CACHE is None or _SEGMENT_CNN_CACHE_SIGNATURE != signature:
        model, metadata = Simple1DCNN.load(SEGMENT_CNN_MODEL_WEIGHTS_PATH, SEGMENT_CNN_MODEL_METADATA_PATH)
        _SEGMENT_CNN_CACHE = (model, metadata)
        _SEGMENT_CNN_CACHE_SIGNATURE = signature
    return _SEGMENT_CNN_CACHE


# ------------------------------------------------------------------
# App
# ------------------------------------------------------------------

app = FastAPI(title="DXD Viewer API")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ------------------------------------------------------------------
# Root
# ------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index():
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="static/index.html not found")
    return HTMLResponse(
        index_path.read_text(encoding="utf-8"),
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


@app.get("/explorer", response_class=HTMLResponse)
def explorer():
    return index()


@app.get("/annotator", response_class=HTMLResponse)
def vehicle_segment_annotator():
    annotator_path = STATIC_DIR / "vehicle_segment_annotator.html"
    if not annotator_path.exists():
        raise HTTPException(status_code=404, detail="static/vehicle_segment_annotator.html not found")
    return HTMLResponse(
        annotator_path.read_text(encoding="utf-8"),
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


@app.get("/drift-coherence", response_class=HTMLResponse)
def drift_coherence_page():
    page_path = STATIC_DIR / "drift_coherence.html"
    if not page_path.exists():
        raise HTTPException(status_code=404, detail="static/drift_coherence.html not found")
    return HTMLResponse(
        page_path.read_text(encoding="utf-8"),
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


def list_drift_coherence_runs() -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    candidates: list[Path] = []
    for prefix in DRIFT_RUN_PREFIXES:
        candidates.extend(BASE_DIR.glob(f"{prefix}*"))
    for path in sorted(set(candidates)):
        if not path.is_dir():
            continue
        summary_path = path / "summary.json"
        batch_metrics_path = path / "batch_metrics.csv"
        if not summary_path.exists() and not batch_metrics_path.exists():
            continue
        summary = {}
        if summary_path.exists():
            try:
                summary = load_json(summary_path)
            except Exception:
                summary = {}
        runs.append(
            {
                "id": path.name,
                "path": str(path),
                "has_summary": summary_path.exists(),
                "has_batch_metrics": batch_metrics_path.exists(),
                "has_metrics_by_file": (path / "metrics_by_file.csv").exists(),
                "has_metrics_by_timebin": (path / "metrics_by_timebin.csv").exists(),
                "has_file_channel_summary": (path / "file_channel_summary.csv").exists(),
                "n_files": summary.get("n_files"),
                "n_batches": summary.get("n_batches"),
                "targets": summary.get("targets", []),
                "model_family": summary.get("model_family", "tcn_ensemble"),
                "ensemble_size": summary.get("ensemble_size"),
                "history_sec": summary.get("history_sec"),
                "horizon_sec": summary.get("horizon_sec"),
                "window_sec": summary.get("window_sec"),
                "sample_hz": (summary.get("ode") or {}).get("sample_hz"),
                "stride_sec": summary.get("stride_sec"),
            }
        )
    return runs


def get_drift_coherence_run_dir(run_id: str) -> Path:
    run_dir = (BASE_DIR / run_id).resolve()
    if run_dir.parent != BASE_DIR or not run_dir.name.startswith(DRIFT_RUN_PREFIXES):
        raise HTTPException(status_code=400, detail="Invalid run id")
    if not run_dir.exists() or not run_dir.is_dir():
        raise HTTPException(status_code=404, detail="Drift coherence run not found")
    return run_dir


def read_run_csv(run_id: str, filename: str) -> pd.DataFrame:
    run_dir = get_drift_coherence_run_dir(run_id)
    path = run_dir / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Missing file: {filename}")
    return pd.read_csv(path)


def read_prediction_rows_for_files(run_id: str, json_names: Sequence[str], usecols: Sequence[str]) -> pd.DataFrame:
    path = get_drift_coherence_run_dir(run_id) / "predictions.csv"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Missing file: predictions.csv")

    header = pd.read_csv(path, nrows=0)
    cols = [c for c in usecols if c in header.columns]
    if not cols:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    seen = set()
    for json_name in json_names:
        name = str(json_name)
        if not name or name in seen:
            continue
        seen.add(name)
        try:
            result = subprocess.run(
                ["rg", "-F", name, str(path)],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode in (0, 1) and result.stdout:
                text = ",".join(header.columns) + "\n" + result.stdout
                df = pd.read_csv(io.StringIO(text), usecols=cols)
                frames.append(df[df["json_name"].astype(str) == name])
        except Exception:
            chunks = []
            for chunk in pd.read_csv(path, usecols=cols, chunksize=250_000):
                mask = chunk["json_name"].astype(str) == name
                if mask.any():
                    chunks.append(chunk.loc[mask])
            if chunks:
                frames.append(pd.concat(chunks, ignore_index=True))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=cols)


def q95_abs_values(values: pd.Series) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").dropna().abs()
    if numeric.empty:
        return None
    return float(numeric.quantile(0.95))


def q95_values(values: pd.Series) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    if numeric.empty:
        return None
    return float(numeric.quantile(0.95))


def prepare_segment_annotations(label: Optional[str] = None, min_confidence: int = 0) -> pd.DataFrame:
    annotations = read_segment_annotations_filtered(PIPELINE_DB_PATH, label=label)
    if annotations is None:
        annotations = load_segment_annotations_frame()
    required_ann_cols = {"json_name", "label", "start_sec", "end_sec"}
    if annotations.empty or not required_ann_cols.issubset(annotations.columns):
        return pd.DataFrame(columns=["json_name", "label", "start_sec", "end_sec"])

    annotations = annotations.copy()
    annotations["start_sec"] = pd.to_numeric(annotations["start_sec"], errors="coerce")
    annotations["end_sec"] = pd.to_numeric(annotations["end_sec"], errors="coerce")
    annotations = annotations.dropna(subset=["json_name", "label", "start_sec", "end_sec"])
    annotations = annotations[annotations["end_sec"] > annotations["start_sec"]]
    if "confidence" in annotations.columns and min_confidence > 0:
        annotations["confidence"] = pd.to_numeric(annotations["confidence"], errors="coerce").fillna(0)
        annotations = annotations[annotations["confidence"] >= int(min_confidence)]
    if label:
        annotations = annotations[annotations["label"].astype(str) == str(label)]
    return annotations


def annotation_labels() -> list[str]:
    annotations = prepare_segment_annotations()
    if annotations.empty or "label" not in annotations.columns:
        return []
    return sorted(annotations["label"].dropna().astype(str).unique())


def load_cnn_segments_for_file(json_name: str, label: Optional[str] = None) -> pd.DataFrame:
    summary = load_model_summary()
    if summary.get("status") != "ok":
        return pd.DataFrame(columns=["json_name", "label", "start_sec", "end_sec", "confidence", "label_source"])
    try:
        model, metadata = load_segment_cnn_model()
        result = predict_file(
            json_name=json_name,
            model=model,
            metadata=metadata,
            stride_sec=1.0,
            smooth_radius=2,
        )
    except Exception:
        return pd.DataFrame(columns=["json_name", "label", "start_sec", "end_sec", "confidence", "label_source"])
    rows = result.get("suggestions") or result.get("merged_runs") or []
    df = pd.DataFrame(rows)
    required = {"label", "start_sec", "end_sec"}
    if df.empty or not required.issubset(df.columns):
        return pd.DataFrame(columns=["json_name", "label", "start_sec", "end_sec", "confidence", "label_source"])
    df = df.copy()
    df["json_name"] = json_name
    df["label_source"] = "cnn_predicted"
    df["start_sec"] = pd.to_numeric(df["start_sec"], errors="coerce")
    df["end_sec"] = pd.to_numeric(df["end_sec"], errors="coerce")
    if "confidence" in df.columns:
        df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce")
    else:
        df["confidence"] = None
    df = df.dropna(subset=["json_name", "label", "start_sec", "end_sec"])
    df = df[df["end_sec"] > df["start_sec"]]
    if label:
        df = df[df["label"].astype(str) == str(label)]
    return df[["json_name", "label", "start_sec", "end_sec", "confidence", "label_source"]]


def exploration_segments_frame(
    label: Optional[str] = None,
    label_source: str = "annotated",
    json_name: Optional[str] = None,
    limit: int = 1000,
) -> pd.DataFrame:
    source = str(label_source or "annotated")
    frames: list[pd.DataFrame] = []

    if source in {"annotated", "both"}:
        ann = prepare_segment_annotations(label)
        if json_name and not ann.empty:
            ann = ann[ann["json_name"].astype(str) == str(json_name)]
        if not ann.empty:
            ann = ann.copy()
            ann["label_source"] = "annotated"
            if "confidence" in ann.columns:
                ann["confidence"] = pd.to_numeric(ann["confidence"], errors="coerce")
            else:
                ann["confidence"] = None
            frames.append(ann[["json_name", "label", "start_sec", "end_sec", "confidence", "label_source"]])

    if source in {"cnn_predicted", "both"} and json_name:
        cnn = load_cnn_segments_for_file(json_name, label)
        if not cnn.empty:
            frames.append(cnn)

    if not frames:
        return pd.DataFrame(columns=["json_name", "label", "start_sec", "end_sec", "confidence", "label_source"])

    df = pd.concat(frames, ignore_index=True)
    df["start_sec"] = pd.to_numeric(df["start_sec"], errors="coerce")
    df["end_sec"] = pd.to_numeric(df["end_sec"], errors="coerce")
    df = df.dropna(subset=["json_name", "label", "start_sec", "end_sec"])
    df = df[df["end_sec"] > df["start_sec"]]
    df = df.sort_values(["json_name", "start_sec", "end_sec", "label_source"], na_position="last")
    return df.head(max(1, min(int(limit), 20000)))


def file_base_timestamp(raw: dict) -> pd.Timestamp | None:
    for value in (raw.get("modified_at"), raw.get("date")):
        if value is None or not str(value).strip():
            continue
        text = str(value).strip().replace("_", "-")
        ts = pd.to_datetime(text, errors="coerce", utc=False)
        if pd.notna(ts):
            return ts
    return None


def time_bucket_for_value(raw: dict, seconds: float, grouping: str) -> tuple[str | None, int | None, str]:
    base = file_base_timestamp(raw)
    if base is not None:
        ts = base + pd.to_timedelta(float(seconds), unit="s")
        date_value = ts.strftime("%Y-%m-%d")
        hour_value = int(ts.hour)
        if grouping == "day":
            return date_value, None, date_value
        if grouping == "hour":
            return None, hour_value, f"{hour_value:02d}:00"
        return date_value, hour_value, ts.floor("h").strftime("%Y-%m-%dT%H:%M:%S")

    date_value = str(raw.get("date") or "unknown").replace("_", "-")
    hour_value = int(max(0, float(seconds)) // 3600)
    if grouping == "day":
        return date_value, None, date_value
    if grouping == "hour":
        return None, hour_value, f"{hour_value:02d}:00"
    return date_value, hour_value, f"{date_value}T{hour_value:02d}:00:00"


def time_buckets_for_series(raw: dict, seconds: pd.Series, grouping: str) -> pd.DataFrame:
    numeric_seconds = pd.to_numeric(seconds, errors="coerce").fillna(0.0)
    base = file_base_timestamp(raw)
    if base is not None:
        ts = base + pd.to_timedelta(numeric_seconds, unit="s")
        date_values = ts.dt.strftime("%Y-%m-%d")
        hour_values = ts.dt.hour.astype(int)
        if grouping == "day":
            return pd.DataFrame({"date": date_values, "hour": None, "time_bucket": date_values})
        if grouping == "hour":
            return pd.DataFrame({
                "date": None,
                "hour": hour_values,
                "time_bucket": hour_values.map(lambda h: f"{int(h):02d}:00"),
            })
        return pd.DataFrame({
            "date": date_values,
            "hour": hour_values,
            "time_bucket": ts.dt.floor("h").dt.strftime("%Y-%m-%dT%H:%M:%S"),
        })

    date_value = str(raw.get("date") or "unknown").replace("_", "-")
    hour_values = (numeric_seconds.clip(lower=0.0) // 3600).astype(int)
    if grouping == "day":
        return pd.DataFrame({"date": date_value, "hour": None, "time_bucket": date_value})
    if grouping == "hour":
        return pd.DataFrame({
            "date": None,
            "hour": hour_values,
            "time_bucket": hour_values.map(lambda h: f"{int(h):02d}:00"),
        })
    return pd.DataFrame({
        "date": date_value,
        "hour": hour_values,
        "time_bucket": hour_values.map(lambda h: f"{date_value}T{int(h):02d}:00:00"),
    })


def quantile_row(values: pd.Series) -> dict[str, Any]:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    if numeric.empty:
        return {}
    qs = numeric.quantile([0.05, 0.25, 0.5, 0.75, 0.95])
    return {
        "n_points": int(len(numeric)),
        "mean": float(numeric.mean()),
        "std": json_safe_value(numeric.std()),
        "min": float(numeric.min()),
        "q05": float(qs.loc[0.05]),
        "q25": float(qs.loc[0.25]),
        "q50": float(qs.loc[0.5]),
        "q75": float(qs.loc[0.75]),
        "q95": float(qs.loc[0.95]),
        "max": float(numeric.max()),
    }


def annotation_filtered_predictions(
    run_id: str,
    label: Optional[str] = None,
    target_name: Optional[str] = None,
    phase: Optional[str] = None,
    min_confidence: int = 0,
    extra_usecols: Sequence[str] = (),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    annotations = prepare_segment_annotations(label, min_confidence)
    if annotations.empty:
        return annotations, pd.DataFrame()

    usecols = [
        "json_name",
        "date",
        "date_bin",
        "time_bin",
        "target_name",
        "phase",
        "time",
        "error",
        "abs_error",
        "score",
        "ensemble_std",
        "disagreement_score",
        "batch_id",
    ]
    usecols.extend([c for c in extra_usecols if c not in usecols])
    pred = read_prediction_rows_for_files(run_id, annotations["json_name"].dropna().astype(str).unique(), usecols)
    if pred.empty:
        return annotations, pred
    if target_name and "target_name" in pred.columns:
        pred = pred[pred["target_name"].astype(str) == str(target_name)]
    if phase and "phase" in pred.columns:
        pred = pred[pred["phase"].astype(str) == str(phase)]
    if pred.empty:
        return annotations, pred

    rows: list[pd.DataFrame] = []
    ann_keep = annotations[["json_name", "label", "start_sec", "end_sec"]].copy()
    for json_name, pred_file in pred.groupby("json_name", sort=False):
        ann_file = ann_keep[ann_keep["json_name"].astype(str) == str(json_name)]
        if ann_file.empty:
            continue
        pred_file = pred_file.copy()
        pred_file["time"] = pd.to_numeric(pred_file["time"], errors="coerce")
        pred_file = pred_file.dropna(subset=["time"])
        for ann in ann_file.itertuples(index=False):
            mask = (pred_file["time"] >= float(ann.start_sec)) & (pred_file["time"] <= float(ann.end_sec))
            if mask.any():
                matched = pred_file.loc[mask].copy()
                matched["annotation_label"] = str(ann.label)
                rows.append(matched)
    if not rows:
        return annotations, pd.DataFrame(columns=list(pred.columns) + ["annotation_label"])
    return annotations, pd.concat(rows, ignore_index=True)


def aggregate_prediction_metrics(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=group_cols)
    out_rows = []
    for keys, df_g in df.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = {col: val for col, val in zip(group_cols, keys)}
        abs_error = pd.to_numeric(df_g.get("abs_error"), errors="coerce") if "abs_error" in df_g.columns else pd.Series(dtype=float)
        error = pd.to_numeric(df_g.get("error"), errors="coerce") if "error" in df_g.columns else pd.Series(dtype=float)
        score = pd.to_numeric(df_g.get("score"), errors="coerce") if "score" in df_g.columns else pd.Series(dtype=float)
        ensemble_std = pd.to_numeric(df_g.get("ensemble_std"), errors="coerce") if "ensemble_std" in df_g.columns else pd.Series(dtype=float)
        disagreement = pd.to_numeric(df_g.get("disagreement_score"), errors="coerce") if "disagreement_score" in df_g.columns else pd.Series(dtype=float)
        y_abs = None
        if "y_true" in df_g.columns:
            y_abs = q95_abs_values(df_g["y_true"])
        q95_abs = q95_abs_values(error) if not error.empty else None
        row.update(
            {
                "n_points": int(len(df_g)),
                "n_windows": int(len(df_g)),
                "n_files": int(df_g["json_name"].nunique()) if "json_name" in df_g.columns else None,
                "mae": json_safe_value(abs_error.mean()) if not abs_error.empty else None,
                "q95_abs_error": q95_abs,
                "mean_score": json_safe_value(score.mean()) if not score.empty else None,
                "q95_score": q95_values(score) if not score.empty else None,
                "q95_y_abs": y_abs,
                "relative_q95_error": json_safe_value(q95_abs / y_abs) if q95_abs is not None and y_abs not in (None, 0) else None,
                "ensemble_std_mean": json_safe_value(ensemble_std.mean()) if not ensemble_std.empty else None,
                "ensemble_std_q95": q95_abs_values(ensemble_std) if not ensemble_std.empty else None,
                "disagreement_score_mean": json_safe_value(disagreement.mean()) if not disagreement.empty else None,
                "disagreement_score_q95": q95_values(disagreement) if not disagreement.empty else None,
            }
        )
        out_rows.append(row)
    return pd.DataFrame(out_rows)


def batch_metrics_from_annotation_predictions(pred: pd.DataFrame, limit: int = 5000) -> pd.DataFrame:
    if pred.empty:
        return pd.DataFrame()
    group_cols = [c for c in ["batch_id", "target_name", "phase"] if c in pred.columns]
    out = aggregate_prediction_metrics(pred, group_cols)
    if out.empty:
        return out
    source_cols = [c for c in ["batch_id", "target_name", "phase", "n_files", "n_windows"] if c in out.columns]
    result = out[source_cols].copy()
    if "batch_id" in result.columns:
        result["batch_id"] = pd.to_numeric(result["batch_id"], errors="coerce")
    for col in ["date_min", "date_max"]:
        result[col] = None
    if "date" in pred.columns and "batch_id" in pred.columns:
        dates = pred.groupby("batch_id")["date"].agg(date_min="min", date_max="max").reset_index()
        result = result.merge(dates, on="batch_id", how="left", suffixes=("", "_ann"))
        for col in ["date_min", "date_max"]:
            ann_col = f"{col}_ann"
            if ann_col in result.columns:
                result[col] = result[ann_col].fillna(result[col])
                result = result.drop(columns=[ann_col])

    metric_map = {
        "mae": "mae",
        "q95_abs_error": "q95_abs_error",
        "relative_q95_error": "relative_q95_error",
        "ensemble_std_mean": "ensemble_std_mean",
        "ensemble_std_q95": "ensemble_std_q95",
    }
    for base in ["new_pre", "new_post", "memory_pre", "memory_post"]:
        for suffix in metric_map:
            result[f"{base}_{suffix}"] = None

    for idx, row in out.iterrows():
        phase_value = str(row.get("phase", ""))
        prefixes = ["new_pre", "memory_pre"] if phase_value in {"pre", "initial"} else ["new_post", "memory_post"]
        for prefix in prefixes:
            for suffix, src in metric_map.items():
                if src in out.columns:
                    result.loc[idx, f"{prefix}_{suffix}"] = row.get(src)

    pivot = out.pivot_table(index="batch_id", columns="phase", values="q95_abs_error", aggfunc="mean") if {"batch_id", "phase", "q95_abs_error"}.issubset(out.columns) else pd.DataFrame()
    result["generalization_gap_q95"] = None
    result["generalization_ratio_q95"] = None
    result["adaptation_gain_q95"] = None
    result["forgetting_q95"] = None
    if not pivot.empty:
        for idx, row in result.iterrows():
            batch_id = row.get("batch_id")
            if batch_id in pivot.index:
                pre = pivot.loc[batch_id].get("pre") if "pre" in pivot.columns else None
                post = pivot.loc[batch_id].get("post") if "post" in pivot.columns else None
                if pd.notna(pre) and pd.notna(post):
                    result.loc[idx, "generalization_gap_q95"] = float(pre - post)
                    result.loc[idx, "generalization_ratio_q95"] = float(pre / post) if post else None
                    result.loc[idx, "adaptation_gain_q95"] = float(pre - post)
    sort_cols = [c for c in ["batch_id", "target_name", "phase"] if c in result.columns]
    if sort_cols:
        result = result.sort_values(sort_cols)
    return result.head(max(1, min(int(limit), 20000)))


def safe_drift_output_dir(name: str) -> Path:
    clean = str(name or "").strip()
    if not clean:
        raise HTTPException(status_code=400, detail="Missing output_dir")
    if "/" in clean or "\\" in clean or clean in {".", ".."}:
        raise HTTPException(status_code=400, detail="output_dir must be a directory name, not a path")
    if not clean.startswith("dynamic_channel_coherence"):
        raise HTTPException(status_code=400, detail="output_dir must start with dynamic_channel_coherence")
    return BASE_DIR / clean


def numeric_payload_value(payload: dict[str, Any], key: str, default: float, min_value: float, max_value: float) -> float:
    try:
        value = float(payload.get(key, default))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"{key} must be numeric")
    if not min_value <= value <= max_value:
        raise HTTPException(status_code=400, detail=f"{key} must be between {min_value} and {max_value}")
    return value


def integer_payload_value(payload: dict[str, Any], key: str, default: int, min_value: int, max_value: int) -> int:
    try:
        value = int(payload.get(key, default))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"{key} must be an integer")
    if not min_value <= value <= max_value:
        raise HTTPException(status_code=400, detail=f"{key} must be between {min_value} and {max_value}")
    return value


def filter_drift_frame(
    df: pd.DataFrame,
    target_name: Optional[str] = None,
    phase: Optional[str] = None,
    limit: int = 5000,
) -> pd.DataFrame:
    out = df.copy()
    if target_name and "target_name" in out.columns:
        out = out[out["target_name"].astype(str) == str(target_name)]
    if phase and "phase" in out.columns:
        out = out[out["phase"].astype(str) == str(phase)]
    return out.head(max(1, min(int(limit), 20000)))


@app.get("/api/drift-coherence/runs")
def api_drift_coherence_runs():
    runs = list_drift_coherence_runs()
    return {"items": runs, "default_run": runs[0]["id"] if runs else None}


@app.post("/api/drift-coherence/train")
def api_drift_coherence_train(background_tasks: BackgroundTasks, payload: Dict[str, Any]):
    if DRIFT_COHERENCE_TRAIN_PROGRESS_PATH.exists():
        try:
            current = load_json(DRIFT_COHERENCE_TRAIN_PROGRESS_PATH)
            if current.get("status") == "running":
                return {"status": "already_running", "message": "Une analyse drift TCN est déjà en cours."}
        except Exception:
            pass

    output_dir = safe_drift_output_dir(str(payload.get("output_dir", "dynamic_channel_coherence_app_run")))
    targets = payload.get("targets") or ["vehicle.ay", "vehicle.yaw_rate", "steer_s1", "steer_s2"]
    if isinstance(targets, str):
        targets = [t.strip() for t in targets.split(",") if t.strip()]
    if not isinstance(targets, list) or not targets:
        raise HTTPException(status_code=400, detail="targets must be a non-empty list")
    allowed_targets = {"vehicle.vx", "vehicle.ax", "vehicle.ay", "vehicle.yaw_rate", "gps_speed", "steer", "steer_s1", "steer_s2"}
    targets = [str(t) for t in targets if str(t) in allowed_targets]
    if not targets:
        raise HTTPException(status_code=400, detail="No valid target selected")

    history_sec = numeric_payload_value(payload, "history_sec", 4.0, 0.5, 30.0)
    horizon_sec = numeric_payload_value(payload, "horizon_sec", 1.0, 0.1, 10.0)
    stride_sec = numeric_payload_value(payload, "stride_sec", 0.5, 0.05, 10.0)
    initial_fraction = numeric_payload_value(payload, "initial_fraction", 0.2, 0.05, 0.9)
    holdout_fraction = numeric_payload_value(payload, "holdout_fraction", 0.2, 0.0, 0.8)
    batch_size_files = integer_payload_value(payload, "batch_size_files", 10, 1, 200)
    epochs_initial = integer_payload_value(payload, "epochs_initial", 20, 1, 500)
    epochs_update = integer_payload_value(payload, "epochs_update", 5, 1, 200)
    ensemble_size = integer_payload_value(payload, "ensemble_size", 3, 1, 20)
    time_bin_minutes = integer_payload_value(payload, "time_bin_minutes", 60, 5, 1440)
    max_windows_per_file = payload.get("max_windows_per_file")
    if max_windows_per_file in ("", None):
        max_windows_per_file = None
    else:
        max_windows_per_file = integer_payload_value(payload, "max_windows_per_file", 2000, 1, 200000)

    cmd = [
        sys.executable,
        str(BASE_DIR / "scripts" / "train_drift_coherence.py"),
        "--input-dir",
        str(RAW_JSON_DIR),
        "--output-dir",
        str(output_dir),
        "--history-sec",
        str(history_sec),
        "--horizon-sec",
        str(horizon_sec),
        "--stride-sec",
        str(stride_sec),
        "--initial-fraction",
        str(initial_fraction),
        "--holdout-fraction",
        str(holdout_fraction),
        "--batch-size-files",
        str(batch_size_files),
        "--epochs-initial",
        str(epochs_initial),
        "--epochs-update",
        str(epochs_update),
        "--ensemble-size",
        str(ensemble_size),
        "--time-bin-minutes",
        str(time_bin_minutes),
        "--targets",
        *targets,
    ]
    if max_windows_per_file is not None:
        cmd.extend(["--max-windows-per-file", str(max_windows_per_file)])

    started_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    write_json_atomic(
        DRIFT_COHERENCE_TRAIN_PROGRESS_PATH,
        {
            "status": "running",
            "started_at": started_at,
            "output_dir": output_dir.name,
            "targets": targets,
            "command": cmd,
            "log_path": str(DRIFT_COHERENCE_TRAIN_LOG_PATH),
        },
    )
    ANNOTATION_DIR.mkdir(parents=True, exist_ok=True)
    DRIFT_COHERENCE_TRAIN_LOG_PATH.write_text(
        f"[{started_at}] Starting drift coherence analysis\n" + " ".join(cmd) + "\n\n",
        encoding="utf-8",
    )

    def run_analysis():
        try:
            with open(DRIFT_COHERENCE_TRAIN_LOG_PATH, "a", encoding="utf-8") as log:
                proc = subprocess.run(
                    cmd,
                    cwd=str(BASE_DIR),
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    text=True,
                    check=False,
                )
            finished_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
            status = "finished" if proc.returncode == 0 else "error"
            write_json_atomic(
                DRIFT_COHERENCE_TRAIN_PROGRESS_PATH,
                {
                    "status": status,
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "returncode": proc.returncode,
                    "output_dir": output_dir.name,
                    "targets": targets,
                    "command": cmd,
                    "log_path": str(DRIFT_COHERENCE_TRAIN_LOG_PATH),
                },
            )
        except Exception as e:
            write_json_atomic(
                DRIFT_COHERENCE_TRAIN_PROGRESS_PATH,
                {
                    "status": "error",
                    "started_at": started_at,
                    "finished_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                    "output_dir": output_dir.name,
                    "targets": targets,
                    "message": str(e),
                    "command": cmd,
                    "log_path": str(DRIFT_COHERENCE_TRAIN_LOG_PATH),
                },
            )

    background_tasks.add_task(run_analysis)
    return {"status": "started", "output_dir": output_dir.name, "targets": targets}


@app.get("/api/drift-coherence/train/progress")
def api_drift_coherence_train_progress(tail_lines: int = 80):
    if DRIFT_COHERENCE_TRAIN_PROGRESS_PATH.exists():
        try:
            progress = load_json(DRIFT_COHERENCE_TRAIN_PROGRESS_PATH)
        except Exception as e:
            progress = {"status": "unknown", "message": str(e)}
    else:
        progress = {"status": "not_started"}
    if DRIFT_COHERENCE_TRAIN_LOG_PATH.exists():
        try:
            lines = DRIFT_COHERENCE_TRAIN_LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
            progress["log_tail"] = "\n".join(lines[-max(1, min(int(tail_lines), 500)):])
        except Exception as e:
            progress["log_tail"] = f"Unable to read log: {e}"
    else:
        progress["log_tail"] = ""
    return deep_json_safe(progress)


@app.get("/api/drift-coherence/{run_id}/summary")
def api_drift_coherence_summary(run_id: str):
    run_dir = get_drift_coherence_run_dir(run_id)
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        return {"status": "missing", "run_id": run_id, "path": str(summary_path)}
    data = load_json(summary_path)
    data["status"] = "ok"
    data["run_id"] = run_id
    return deep_json_safe(data)


@app.get("/api/drift-coherence/{run_id}/batch-metrics")
def api_drift_coherence_batch_metrics(
    run_id: str,
    target_name: Optional[str] = None,
    phase: Optional[str] = None,
    label: Optional[str] = None,
    limit: int = 5000,
):
    if label:
        _, pred = annotation_filtered_predictions(
            run_id,
            label=label,
            target_name=target_name,
            phase=phase,
            extra_usecols=["y_true"],
        )
        df = batch_metrics_from_annotation_predictions(pred, limit)
        return deep_json_safe({"items": records_json_safe(df), "columns": list(df.columns), "filtered_by_label": label})
    df = filter_drift_frame(read_run_csv(run_id, "batch_metrics.csv"), target_name, phase, limit)
    return deep_json_safe({"items": records_json_safe(df), "columns": list(df.columns)})


@app.get("/api/drift-coherence/{run_id}/metrics-by-file")
def api_drift_coherence_metrics_by_file(
    run_id: str,
    target_name: Optional[str] = None,
    phase: Optional[str] = None,
    label: Optional[str] = None,
    sort_by: str = "q95_abs_error",
    order: str = "desc",
    limit: int = 200,
):
    if label:
        _, pred = annotation_filtered_predictions(
            run_id,
            label=label,
            target_name=target_name,
            phase=phase,
            extra_usecols=["y_true"],
        )
        df = aggregate_prediction_metrics(pred, [c for c in ["json_name", "target_name", "phase"] if c in pred.columns])
    else:
        df = filter_drift_frame(read_run_csv(run_id, "metrics_by_file.csv"), target_name, phase, 20000)
    if sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=(order != "desc"), na_position="last")
    df = df.head(max(1, min(int(limit), 1000)))
    return deep_json_safe({"items": records_json_safe(df), "columns": list(df.columns), "filtered_by_label": label or None})


@app.get("/api/drift-coherence/{run_id}/metrics-by-timebin")
def api_drift_coherence_metrics_by_timebin(
    run_id: str,
    target_name: Optional[str] = None,
    phase: Optional[str] = None,
    label: Optional[str] = None,
    limit: int = 5000,
):
    if label:
        _, pred = annotation_filtered_predictions(
            run_id,
            label=label,
            target_name=target_name,
            phase=phase,
            extra_usecols=["y_true"],
        )
        group_cols = [c for c in ["date_bin", "time_bin", "target_name", "phase"] if c in pred.columns]
        df = aggregate_prediction_metrics(pred, group_cols).head(max(1, min(int(limit), 20000)))
    else:
        df = filter_drift_frame(read_run_csv(run_id, "metrics_by_timebin.csv"), target_name, phase, limit)
    if {"date_bin", "time_bin"}.issubset(df.columns):
        df = df.sort_values(["date_bin", "time_bin"])
    return deep_json_safe({"items": records_json_safe(df), "columns": list(df.columns), "filtered_by_label": label or None})


@app.get("/api/drift-coherence/{run_id}/prediction-files")
def api_drift_coherence_prediction_files(
    run_id: str,
    target_name: Optional[str] = None,
    phase: Optional[str] = None,
    limit: int = 1000,
):
    df = read_run_csv(run_id, "metrics_by_file.csv")
    if target_name and "target_name" in df.columns:
        df = df[df["target_name"].astype(str) == str(target_name)]
    if phase and "phase" in df.columns:
        df = df[df["phase"].astype(str) == str(phase)]
    if df.empty or "json_name" not in df.columns:
        return {"items": []}
    agg_spec: dict[str, tuple[str, str]] = {"n_points": ("n_points", "sum") if "n_points" in df.columns else ("json_name", "size")}
    for col in ["date", "batch_id", "mae", "q95_abs_error", "relative_q95_error", "ensemble_std_q95"]:
        if col in df.columns:
            agg_spec[col] = (col, "max" if col in {"mae", "q95_abs_error", "relative_q95_error", "ensemble_std_q95"} else "first")
    out = df.groupby("json_name", as_index=False).agg(**agg_spec)
    if "mae" in out.columns:
        out = out.sort_values("mae", ascending=False, na_position="last")
    out = out.head(max(1, min(int(limit), 5000)))
    return deep_json_safe({"items": records_json_safe(out), "columns": list(out.columns)})


@app.get("/api/drift-coherence/{run_id}/prediction-series")
def api_drift_coherence_prediction_series(
    run_id: str,
    target_name: str,
    json_name: str,
    limit: int = 12000,
):
    usecols = [
        "json_name",
        "target_name",
        "phase",
        "time",
        "y_true",
        "y_pred",
        "abs_error",
        "ensemble_std",
        "score",
        "disagreement_score",
    ]
    df = read_prediction_rows_for_files(run_id, [json_name], usecols)
    required = {"json_name", "target_name", "phase", "time", "y_true", "y_pred"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing prediction columns: {', '.join(missing)}")

    df = df[
        (df["json_name"].astype(str) == str(json_name))
        & (df["target_name"].astype(str) == str(target_name))
    ].copy()
    if df.empty:
        return {"items": [], "columns": [], "json_name": json_name, "target_name": target_name}
    agg_spec: dict[str, tuple[str, str]] = {
        "y_true": ("y_true", "mean"),
        "y_pred": ("y_pred", "mean"),
        "abs_error": ("abs_error", "mean") if "abs_error" in df.columns else ("y_pred", "size"),
    }
    if "ensemble_std" in df.columns:
        agg_spec["ensemble_std"] = ("ensemble_std", "mean")
    if "score" in df.columns:
        agg_spec["score"] = ("score", "mean")
    if "disagreement_score" in df.columns:
        agg_spec["disagreement_score"] = ("disagreement_score", "mean")
    out = (
        df.groupby(["phase", "time"], as_index=False)
        .agg(**agg_spec)
        .sort_values(["phase", "time"])
    )
    if len(out) > limit:
        idx = np.linspace(0, len(out) - 1, max(1, min(int(limit), 50000))).astype(int)
        out = out.iloc[idx]
    return deep_json_safe(
        {
            "items": records_json_safe(out),
            "columns": list(out.columns),
            "json_name": json_name,
            "target_name": target_name,
        }
    )


@app.get("/api/drift-coherence/{run_id}/annotation-label-metrics")
def api_drift_coherence_annotation_label_metrics(
    run_id: str,
    target_name: Optional[str] = None,
    phase: Optional[str] = None,
    label: Optional[str] = None,
    min_confidence: int = 0,
):
    all_labels = annotation_labels()
    annotations, matched = annotation_filtered_predictions(
        run_id,
        label=label,
        target_name=target_name,
        phase=phase,
        min_confidence=min_confidence,
    )
    if annotations.empty:
        return {"items": [], "labels": all_labels, "n_annotations": 0}
    if matched.empty:
        return {"items": [], "labels": all_labels, "n_annotations": int(len(annotations))}
    group_cols = ["annotation_label"]
    if "target_name" in matched.columns:
        group_cols.append("target_name")
    if "phase" in matched.columns:
        group_cols.append("phase")

    out_rows = []
    for keys, df_g in matched.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = {col: val for col, val in zip(group_cols, keys)}
        row.update(
            {
                "n_points": int(len(df_g)),
                "n_files": int(df_g["json_name"].nunique()) if "json_name" in df_g.columns else None,
                "mae": json_safe_value(pd.to_numeric(df_g.get("abs_error"), errors="coerce").mean()) if "abs_error" in df_g.columns else None,
                "q95_abs_error": q95_abs_values(df_g["error"]) if "error" in df_g.columns else None,
                "mean_score": json_safe_value(pd.to_numeric(df_g.get("score"), errors="coerce").mean()) if "score" in df_g.columns else None,
                "ensemble_std_mean": json_safe_value(pd.to_numeric(df_g.get("ensemble_std"), errors="coerce").mean()) if "ensemble_std" in df_g.columns else None,
                "ensemble_std_q95": q95_abs_values(df_g["ensemble_std"]) if "ensemble_std" in df_g.columns else None,
                "disagreement_score_mean": json_safe_value(pd.to_numeric(df_g.get("disagreement_score"), errors="coerce").mean()) if "disagreement_score" in df_g.columns else None,
            }
        )
        out_rows.append(row)

    out = pd.DataFrame(out_rows).sort_values(["annotation_label"] + [c for c in ["target_name", "phase"] if c in group_cols])
    return deep_json_safe(
        {
            "items": records_json_safe(out),
            "labels": all_labels,
            "n_annotations": int(len(annotations)),
            "n_points_matched": int(len(matched)),
        }
    )


@app.get("/api/drift-coherence/{run_id}/file-channel-summary")
def api_drift_coherence_file_channel_summary(run_id: str, limit: int = 5000):
    df = read_run_csv(run_id, "file_channel_summary.csv")
    df = df.head(max(1, min(int(limit), 20000)))
    return deep_json_safe({"items": records_json_safe(df), "columns": list(df.columns)})


@app.get("/api/drift-coherence/{run_id}/plots")
def api_drift_coherence_plots(run_id: str):
    run_dir = get_drift_coherence_run_dir(run_id)
    plots_dir = run_dir / "plots"
    if not plots_dir.exists():
        return {"items": []}
    items = []
    for path in sorted(plots_dir.rglob("*.png")):
        rel = path.relative_to(plots_dir).as_posix()
        items.append(
            {
                "name": path.stem,
                "category": path.parent.name,
                "relative_path": rel,
                "url": f"/api/drift-coherence/{run_id}/plot/{rel}",
            }
        )
    return {"items": items}


@app.get("/api/drift-coherence/{run_id}/plot/{plot_path:path}")
def api_drift_coherence_plot(run_id: str, plot_path: str):
    run_dir = get_drift_coherence_run_dir(run_id)
    plots_dir = (run_dir / "plots").resolve()
    path = (plots_dir / plot_path).resolve()
    if plots_dir not in path.parents or path.suffix.lower() != ".png" or not path.exists():
        raise HTTPException(status_code=404, detail="Plot not found")
    return FileResponse(path)


@app.get("/api/health")
def api_health():
    sqlite_ready = database_ready(PIPELINE_DB_PATH)
    return {
        "base_dir": str(BASE_DIR),
        "raw_json_dir": str(RAW_JSON_DIR),
        "raw_json_dir_exists": RAW_JSON_DIR.exists(),
        "n_json_files": len(list(RAW_JSON_DIR.glob("*.json"))) if RAW_JSON_DIR.exists() else 0,
        "dataset_index_path": str(DATASET_INDEX_PATH),
        "dataset_index_exists": DATASET_INDEX_PATH.exists(),
        "sqlite_path": str(PIPELINE_DB_PATH),
        "sqlite_ready": sqlite_ready,
    }


@app.get("/api/correlation-anomalies")
def api_correlation_anomalies(
    track_id: Optional[str] = None,
    json_name: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
):
    index_data = load_correlation_anomaly_index()
    anomalies = index_data.get("anomalies", [])

    if track_id:
        anomalies = [a for a in anomalies if a.get("track_id") == track_id]
    if json_name:
        anomalies = [a for a in anomalies if a.get("json_name") == json_name]
    if severity:
        anomalies = [a for a in anomalies if a.get("severity") == severity]

    return deep_json_safe(
        {
            "schema_version": index_data.get("schema_version"),
            "status": index_data.get("status", "ok"),
            "path": index_data.get("path"),
            "summary": index_data.get("summary", {}),
            "filters": {
                "track_id": track_id,
                "json_name": json_name,
                "severity": severity,
                "limit": limit,
            },
            "n_items": len(anomalies[:limit]),
            "items": anomalies[:limit],
        }
    )


@app.get("/api/correlation-anomalies/summary")
def api_correlation_anomalies_summary():
    index_data = load_correlation_anomaly_index()
    return deep_json_safe(
        {
            "schema_version": index_data.get("schema_version"),
            "status": index_data.get("status", "ok"),
            "path": index_data.get("path"),
            "config": index_data.get("config", {}),
            "summary": index_data.get("summary", {}),
            "file_summaries": index_data.get("file_summaries", []),
            "skipped_files": index_data.get("skipped_files", []),
        }
    )


@app.get("/api/correlation-baseline/{track_id}")
def api_correlation_baseline(track_id: str):
    index_data = load_correlation_anomaly_index()
    baseline = index_data.get("baselines_by_track", {}).get(track_id)
    if baseline is None:
        raise HTTPException(status_code=404, detail="Track baseline not found")
    return deep_json_safe(
        {
            "schema_version": index_data.get("schema_version"),
            "status": index_data.get("status", "ok"),
            "track_id": track_id,
            "baseline_pairs": baseline,
        }
    )


@app.get("/api/window-quality/summary")
def api_window_quality_summary():
    return deep_json_safe(load_window_quality_summary())


@app.get("/api/window-quality")
def api_window_quality(
    json_name: Optional[str] = None,
    maneuver_family: Optional[str] = None,
    cluster_id: Optional[str] = None,
    usable_for_regression: Optional[bool] = None,
    min_global_quality: Optional[float] = Query(None, ge=0.0, le=1.0),
    limit: int = Query(200, ge=1, le=50000),
    sort: str = Query("quality", pattern="^(quality|time|speed_bin)$"),
):
    preferred_cols = [
        "file",
        "json_name",
        "date",
        "modified_at",
        "window_id",
        "window_start_sec",
        "window_end_sec",
        "mean_vx_kmh",
        "rms_ax",
        "rms_ay",
        "rms_yaw_rate",
        "speed_bin",
        "lat_acc_bin",
        "long_acc_bin",
        "steer_bin",
        "maneuver_direction",
        "maneuver_family",
        "similarity_group_id",
        "cluster_id",
        "cluster_label",
        "cluster_is_noise",
        "cluster_size",
        "cluster_distance_to_center",
        "r_ax_rms",
        "r_ay_rms",
        "r_ay_simple_rms",
        "r_dist_rms",
        "r_kappa_rms",
        "r_gps_pos_rmse",
        "r_gps_pos_aligned_rmse",
        "r_gps_speed_rms",
        "r_gps_body_speed_rms",
        "r_gps_yaw_rms",
        "r_wheel_rms",
        "signal_quality_score",
        "physical_consistency_score",
        "gps_score",
        "global_quality_score",
        "lateral_excitation_score",
        "longitudinal_excitation_score",
        "usable_for_regression",
        "usable_for_lateral_identification",
        "usable_for_longitudinal_identification",
        "usable_for_tire_parameter_estimation",
        "usable_for_indicator_computation",
    ]
    df = read_window_quality_filtered(
        PIPELINE_DB_PATH,
        json_name=json_name,
        maneuver_family=maneuver_family,
        cluster_id=cluster_id,
        usable_for_regression=usable_for_regression,
        min_global_quality=min_global_quality,
        limit=limit,
        sort=sort,
        columns=preferred_cols,
    )
    if df is None:
        df = load_window_quality_frame()

        if json_name:
            df = df[df["json_name"] == json_name]
        if maneuver_family:
            df = df[df["maneuver_family"] == maneuver_family]
        if cluster_id:
            if cluster_id == "noise" and "cluster_is_noise" in df.columns:
                df = df[df["cluster_is_noise"].astype(bool)]
            elif "cluster_id" in df.columns:
                df = df[df["cluster_id"] == cluster_id]
        if usable_for_regression is not None and "usable_for_regression" in df.columns:
            df = df[df["usable_for_regression"].astype(bool) == usable_for_regression]
        if min_global_quality is not None and "global_quality_score" in df.columns:
            df = df[pd.to_numeric(df["global_quality_score"], errors="coerce") >= min_global_quality]

        if sort == "time" and "window_start_sec" in df.columns:
            sort_cols = [c for c in ["date", "json_name", "window_start_sec"] if c in df.columns]
            df = df.sort_values(sort_cols, ascending=True, na_position="last")
        elif sort == "speed_bin" and "speed_bin" in df.columns:
            speed_order = {
                "0_20": 0,
                "20_40": 1,
                "40_60": 2,
                "60_80": 3,
                "80_100": 4,
                "100_120": 5,
                "out_of_range": 6,
                "unknown": 7,
            }
            df = df.assign(_speed_bin_order=df["speed_bin"].map(speed_order).fillna(99))
            sort_cols = ["_speed_bin_order"] + [c for c in ["date", "json_name", "window_start_sec"] if c in df.columns]
            df = df.sort_values(sort_cols, ascending=True, na_position="last")
        elif json_name and "window_start_sec" in df.columns:
            df = df.sort_values("window_start_sec", ascending=True, na_position="last")
        else:
            sort_cols = [c for c in ["global_quality_score", "signal_quality_score"] if c in df.columns]
            if sort_cols:
                df = df.sort_values(sort_cols, ascending=False, na_position="last")

        df = df.head(limit)

    cols = [c for c in preferred_cols if c in df.columns]
    return deep_json_safe(
        {
            "status": "ok",
            "path": str(PIPELINE_DB_PATH) if database_ready(PIPELINE_DB_PATH) else str(WINDOW_QUALITY_INDEX_PATH),
            "filters": {
                "json_name": json_name,
                "maneuver_family": maneuver_family,
                "cluster_id": cluster_id,
                "usable_for_regression": usable_for_regression,
                "min_global_quality": min_global_quality,
                "limit": limit,
            },
            "n_items": int(len(df)),
            "items": records_json_safe(df[cols]),
        }
    )





@app.get("/api/window-quality/file/{json_name}/series")
def api_window_quality_file_series(json_name: str):
    preferred_cols = [
        "json_name",
        "file",
        "window_id",
        "window_start_sec",
        "window_end_sec",
        "mean_vx_kmh",
        "rms_ax",
        "rms_ay",
        "rms_yaw_rate",
        "zero_speed_ratio",
        "low_speed_ratio",
        "signal_quality_score",
        "physical_consistency_score",
        "gps_score",
        "global_quality_score",
        "r_ax_rms",
        "r_ay_rms",
        "r_ay_simple_rms",
        "r_dist_rms",
        "r_kappa_rms",
        "r_gps_pos_rmse",
        "r_gps_pos_aligned_rmse",
        "r_gps_speed_rms",
        "r_gps_body_speed_rms",
        "r_gps_yaw_rms",
        "r_wheel_rms",
        "lateral_excitation_score",
        "longitudinal_excitation_score",
        "speed_bin",
        "maneuver_family",
        "maneuver_direction",
        "similarity_group_id",
        "usable_for_regression",
        "usable_for_lateral_identification",
        "usable_for_longitudinal_identification",
    ]
    df = read_window_quality_series(
        json_name,
        PIPELINE_DB_PATH,
        columns=preferred_cols,
    )
    if df is None:
        df = load_window_quality_frame()
        df = df[df["json_name"] == json_name].copy()
        if not df.empty:
            df = df.sort_values("window_start_sec", na_position="last")
    if df.empty:
        raise HTTPException(status_code=404, detail="No quality windows found for this file")

    cols = [c for c in preferred_cols if c in df.columns]
    return deep_json_safe(
        {
            "status": "ok",
            "json_name": json_name,
            "file": df["file"].iloc[0] if "file" in df.columns else json_name,
            "n_windows": int(len(df)),
            "items": records_json_safe(df[cols]),
        }
    )





@app.get("/api/speed-day-summary/summary")
def api_speed_day_summary_summary():
    return deep_json_safe(load_speed_day_summary_json())


@app.get("/api/speed-day-summary")
def api_speed_day_summary(
    metric: str = Query("global_quality_score_mean", description="Column to visualize, e.g. gps_score_mean"),
    date: Optional[str] = None,
):
    df = load_speed_day_summary_frame()
    if date:
        df = df[df["date"] == date]
    if metric not in df.columns:
        raise HTTPException(status_code=400, detail=f"Unknown metric: {metric}")

    keep = [
        "date",
        "speed_bin",
        "speed_bin_order",
        "n_windows",
        "n_files",
        "top_maneuver_family",
        metric,
    ]
    keep = [c for c in keep if c in df.columns]
    df = df.sort_values(["date", "speed_bin_order"], na_position="last")
    return deep_json_safe(
        {
            "status": "ok",
            "path": str(SPEED_DAY_SUMMARY_PATH),
            "metric": metric,
            "date": date,
            "available_metrics": [
                c for c in df.columns
                if c.endswith("_mean") or c.endswith("_median") or c.endswith("_p95") or c.endswith("_ratio")
            ],
            "n_items": int(len(df)),
            "items": records_json_safe(df[keep]),
        }
    )


# ------------------------------------------------------------------
# Files / catalog
# ------------------------------------------------------------------

@app.get("/api/files")
def api_files():
    return {"items": list_json_files()}


@app.get("/api/annotator/file/{json_name}")
def api_annotator_file(json_name: str):
    raw = load_raw_json(json_name)
    time_values = get_time_values(raw)
    channels = get_resampled_channels(raw)

    preferred = [
        "vehicle.vx",
        "vehicle.speed",
        "vehicle.ax",
        "vehicle.ay",
        "vehicle.yaw_rate",
        "gps.latitude",
        "gps.longitude",
        "WheelSteer_S1 (_)",
        "WheelSteer_S2 (_)",
        "WhlDirFl_D_Actl (-)",
        "WhlDirFr_D_Actl (-)",
    ]

    out_channels: dict[str, Any] = {}
    for name in preferred:
        payload = channels.get(name)
        if not isinstance(payload, dict) or "values" not in payload:
            continue
        out_channels[name] = {
            "canonical_name": payload.get("canonical_name") or name,
            "source_name": payload.get("source_name") or name,
            "unit": payload.get("unit"),
            "values": payload.get("values", []),
        }

    return deep_json_safe(
        {
            "file_id": raw.get("file_id"),
            "file": raw.get("file"),
            "json_name": json_name,
            "date": raw.get("date"),
            "modified_at": raw.get("modified_at"),
            "pipeline": raw.get("pipeline", {}),
            "time": time_values,
            "channels": out_channels,
            "available_channels": sorted(list(channels.keys()), key=channel_sort_key),
        }
    )


@app.get("/api/annotations/segments")
def api_list_segment_annotations(json_name: Optional[str] = None):
    df = read_segment_annotations_filtered(PIPELINE_DB_PATH, json_name=json_name)
    if df is None:
        df = load_segment_annotations_frame()
        if json_name and not df.empty and "json_name" in df.columns:
            df = df[df["json_name"].astype(str) == json_name]
    return {
        "path": str(SEGMENT_ANNOTATION_CSV),
        "n_items": int(len(df)),
        "items": records_json_safe(df),
    }


@app.get("/api/annotations/segments/labels")
def api_list_segment_annotation_labels():
    db_counts = read_segment_annotation_label_counts(PIPELINE_DB_PATH)
    if db_counts is not None:
        return {"items": db_counts}
    df = load_segment_annotations_frame()
    if df.empty or "label" not in df.columns:
        return {"items": []}
    counts = df["label"].dropna().astype(str).value_counts()
    return {
        "items": [
            {"label": label, "count": int(count)}
            for label, count in counts.sort_index().items()
        ]
    }


@app.get("/api/exploration/signals/options")
def api_exploration_signal_options(json_name: Optional[str] = None):
    available: set[str] | None = None
    if json_name:
        raw = load_raw_json(json_name)
        available = set(get_available_resampled_channels(raw))
    items = []
    for item in EXPLORATION_SIGNALS:
        signal = item["value"]
        is_available = available is None or signal in available
        items.append({**item, "available": bool(is_available)})
    return {"items": items}


@app.get("/api/exploration/files")
def api_exploration_files(
    label: Optional[str] = None,
    label_source: str = Query("annotated", pattern="^(annotated|cnn_predicted|both)$"),
    limit: int = Query(5000, ge=1, le=20000),
):
    if not label:
        return {"items": list_json_files()[:limit], "filters": {"label": label, "label_source": label_source}}

    allowed: set[str] = set()
    if label_source in {"annotated", "both"}:
        segments = exploration_segments_frame(label=label, label_source="annotated", json_name=None, limit=20000)
        if not segments.empty:
            allowed.update(segments["json_name"].dropna().astype(str).unique())

    scanned_cnn_files = 0
    if label_source in {"cnn_predicted", "both"}:
        for item in list_json_files():
            name = str(item.get("json_name") or "")
            if not name:
                continue
            if name in allowed:
                continue
            scanned_cnn_files += 1
            cnn_segments = load_cnn_segments_for_file(name, label)
            if not cnn_segments.empty:
                allowed.add(name)

    if not allowed:
        return {
            "items": [],
            "filters": {"label": label, "label_source": label_source},
            "n_matching_files": 0,
            "n_scanned_cnn_files": scanned_cnn_files,
        }

    items = [item for item in list_json_files() if str(item.get("json_name")) in allowed]
    return {
        "items": items[:limit],
        "filters": {"label": label, "label_source": label_source},
        "n_matching_files": len(items),
        "n_scanned_cnn_files": scanned_cnn_files,
    }


@app.get("/api/exploration/segments")
def api_exploration_segments(
    label: Optional[str] = None,
    label_source: str = Query("annotated", pattern="^(annotated|cnn_predicted|both)$"),
    json_name: Optional[str] = None,
    limit: int = Query(500, ge=1, le=5000),
):
    segments = exploration_segments_frame(label, label_source, json_name, limit)
    trajectory: dict[str, Any] | None = None
    if json_name:
        raw = load_raw_json(json_name)
        try:
            df = load_signal_series_frame(json_name, ("gps.latitude", "gps.longitude"))
            lat_col = "gps.latitude" if "gps.latitude" in df.columns else None
            lon_col = "gps.longitude" if "gps.longitude" in df.columns else None
            if lat_col and lon_col:
                out = df[["time", lat_col, lon_col]].dropna().copy()
                out = downsample_frame(out, 6000)
                trajectory = {
                    "json_name": json_name,
                    "latitude_channel": lat_col,
                    "longitude_channel": lon_col,
                    "items": records_json_safe(out.rename(columns={lat_col: "lat", lon_col: "lon"})),
                }
        except Exception:
            trajectory = None
    return deep_json_safe(
        {
            "items": records_json_safe(segments),
            "trajectory": trajectory,
            "filters": {
                "label": label,
                "label_source": label_source,
                "json_name": json_name,
            },
        }
    )


@app.get("/api/exploration/signals/series")
def api_exploration_signal_series(
    signal: str = Query(...),
    label: Optional[str] = None,
    label_source: str = Query("annotated", pattern="^(annotated|cnn_predicted|both)$"),
    json_name: str = Query(...),
    context_sec: float = Query(5.0, ge=0.0, le=120.0),
    max_points: int = Query(10000, ge=100, le=50000),
):
    raw = load_raw_json(json_name)
    try:
        df = load_signal_series_frame(json_name, (signal,))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if signal not in df.columns:
        raise HTTPException(status_code=400, detail=f"Signal not available: {signal}")

    segments = exploration_segments_frame(label, label_source, json_name, 5000)
    out = df[["time", signal]].copy()
    if not segments.empty:
        start = max(float(out["time"].min()), float(segments["start_sec"].min()) - float(context_sec))
        end = min(float(out["time"].max()), float(segments["end_sec"].max()) + float(context_sec))
        out = out[(out["time"] >= start) & (out["time"] <= end)]
    out = downsample_frame(out, max_points)
    return deep_json_safe(
        {
            "json_name": json_name,
            "signal": signal,
            "date": raw.get("date"),
            "items": records_json_safe(out.rename(columns={signal: "value"})),
            "segments": records_json_safe(segments),
            "filters": {
                "label": label,
                "label_source": label_source,
                "json_name": json_name,
            },
        }
    )


@lru_cache(maxsize=64)
def compute_exploration_boxplot_cached(
    signal: str,
    label: str | None,
    label_source: str,
    json_name: str | None,
    time_grouping: str,
    min_points: int,
    max_segments: int,
    max_points: int,
) -> dict[str, Any]:
    return compute_exploration_boxplot(
        signal=signal,
        label=label,
        label_source=label_source,
        json_name=json_name,
        time_grouping=time_grouping,
        min_points=min_points,
        max_segments=max_segments,
        max_points=max_points,
    )


def compute_exploration_boxplot(
    signal: str = Query(...),
    label: str | None = None,
    label_source: str = "annotated",
    json_name: str | None = None,
    time_grouping: str = "day_hour",
    min_points: int = 10,
    max_segments: int = 1500,
    max_points: int = 250000,
) -> dict[str, Any]:
    segments = exploration_segments_frame(label, label_source, json_name, max_segments)
    if segments.empty:
        return {
            "items": [],
            "coverage": {"n_files": 0, "n_segments": 0, "n_points": 0, "duration_sec": 0},
            "filters": {"label": label, "label_source": label_source, "signal": signal, "time_grouping": time_grouping},
        }

    frames: list[pd.DataFrame] = []
    total_points = 0
    duration_sec = 0.0
    for file_name, file_segments in segments.groupby("json_name", sort=False):
        raw = load_raw_json(str(file_name))
        try:
            df = load_signal_series_frame(str(file_name), (signal,))
        except ValueError:
            continue
        if signal not in df.columns:
            continue
        file_df = df[["time", signal]].dropna().sort_values("time")
        if file_df.empty:
            continue
        times = file_df["time"].to_numpy(dtype=float)
        values = file_df[signal].to_numpy(dtype=float)
        for seg in file_segments.itertuples(index=False):
            if total_points >= max_points:
                break
            start = float(seg.start_sec)
            end = float(seg.end_sec)
            left = int(np.searchsorted(times, start, side="left"))
            right = int(np.searchsorted(times, end, side="right"))
            if right <= left:
                continue
            remaining = max(0, int(max_points) - total_points)
            right = min(right, left + remaining)
            if right <= left:
                break
            chunk = pd.DataFrame({"time": times[left:right], "value": values[left:right]})
            buckets = time_buckets_for_series(raw, chunk["time"], time_grouping)
            chunk = pd.concat([buckets.reset_index(drop=True), chunk[["value"]].reset_index(drop=True)], axis=1)
            chunk["json_name"] = str(file_name)
            chunk["label"] = str(seg.label)
            chunk["label_source"] = str(seg.label_source)
            chunk["signal"] = signal
            frames.append(chunk)
            total_points += int(len(chunk))
            duration_sec += max(0.0, end - start)
            if total_points >= max_points:
                break

    if not frames:
        return {
            "items": [],
            "coverage": {
                "n_files": int(segments["json_name"].nunique()),
                "n_segments": int(len(segments)),
                "n_points": 0,
                "duration_sec": json_safe_value(duration_sec),
            },
            "filters": {"label": label, "label_source": label_source, "signal": signal, "time_grouping": time_grouping},
        }

    values_df = pd.concat(frames, ignore_index=True)
    group_cols = ["time_bucket", "date", "hour", "label", "label_source", "signal"]
    grouped = values_df.groupby(group_cols, dropna=False, sort=True)
    stats_df = grouped["value"].agg(
        n_points="count",
        mean="mean",
        std="std",
        min="min",
        q05=lambda s: s.quantile(0.05),
        q25=lambda s: s.quantile(0.25),
        q50=lambda s: s.quantile(0.50),
        q75=lambda s: s.quantile(0.75),
        q95=lambda s: s.quantile(0.95),
        max="max",
    )
    stats_df["n_files"] = grouped["json_name"].nunique()
    stats_df = stats_df.reset_index()
    stats_df = stats_df[stats_df["n_points"] >= int(min_points)].copy()

    out_rows = records_json_safe(stats_df)
    for row in out_rows:
        sort_ts = pd.to_datetime(row.get("time_bucket"), errors="coerce")
        if pd.notna(sort_ts):
            row["time_order"] = sort_ts.isoformat()
        elif row.get("date") is not None:
            row["time_order"] = f"{row.get('date')}T{int(row.get('hour') or 0):02d}:00:00"
        else:
            row["time_order"] = f"{int(row.get('hour') or 0):02d}:00:00"

    out_rows = sorted(
        out_rows,
        key=lambda r: (
            str(r.get("time_order") or r.get("time_bucket") or ""),
            str(r.get("label_source") or ""),
            str(r.get("label") or ""),
        ),
    )

    return deep_json_safe(
        {
            "items": out_rows,
            "coverage": {
                "n_files": int(segments["json_name"].nunique()),
                "n_segments": int(len(segments)),
                "n_points": int(total_points),
                "duration_sec": json_safe_value(duration_sec),
                "label_sources": sorted(segments["label_source"].dropna().astype(str).unique()),
            },
            "filters": {
                "label": label,
                "label_source": label_source,
                "signal": signal,
                "json_name": json_name,
                "time_grouping": time_grouping,
                "min_points": min_points,
            },
        }
    )


@app.get("/api/exploration/signals/boxplot")
def api_exploration_signal_boxplot(
    signal: str = Query(...),
    label: Optional[str] = None,
    label_source: str = Query("annotated", pattern="^(annotated|cnn_predicted|both)$"),
    json_name: Optional[str] = None,
    time_grouping: str = Query("day_hour", pattern="^(hour|day|day_hour)$"),
    min_points: int = Query(10, ge=1, le=10000),
    max_segments: int = Query(1500, ge=1, le=10000),
    max_points: int = Query(250000, ge=1000, le=1000000),
):
    if label_source == "annotated":
        payload = compute_exploration_boxplot_cached(
            signal,
            label,
            label_source,
            json_name,
            time_grouping,
            int(min_points),
            int(max_segments),
            int(max_points),
        )
    else:
        payload = compute_exploration_boxplot(
            signal=signal,
            label=label,
            label_source=label_source,
            json_name=json_name,
            time_grouping=time_grouping,
            min_points=int(min_points),
            max_segments=int(max_segments),
            max_points=int(max_points),
        )
    return deep_json_safe(payload)


@app.post("/api/annotations/segments")
def api_save_segment_annotation(row: Dict[str, Any]):
    required = ["annotation_id", "json_name", "label", "start_sec", "end_sec"]
    missing = [key for key in required if row.get(key) in (None, "")]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing annotation fields: {', '.join(missing)}")

    try:
        start_sec = float(row["start_sec"])
        end_sec = float(row["end_sec"])
    except Exception:
        raise HTTPException(status_code=400, detail="start_sec and end_sec must be numeric")

    if start_sec >= end_sec:
        raise HTTPException(status_code=400, detail="start_sec must be lower than end_sec")

    saved = append_segment_annotation(row)
    return {"status": "ok", "item": saved, "path": str(SEGMENT_ANNOTATION_CSV)}


@app.delete("/api/annotations/labels/{label}")
@app.delete("/api/annotations/segments/label")
def api_delete_segment_label(label: str):
    if not str(label).strip():
        raise HTTPException(status_code=400, detail="Missing label")
    df = load_segment_annotations_frame()
    if df.empty or "label" not in df.columns:
        return {"status": "ok", "deleted": label, "n_deleted": 0, "n_items": int(len(df))}

    mask = df["label"].astype(str) == str(label)
    n_deleted = int(mask.sum())
    if n_deleted > 0:
        df = df[~mask]
        write_segment_annotations_frame(df)

    return {"status": "ok", "deleted": label, "n_deleted": n_deleted, "n_items": int(len(df))}


@app.delete("/api/annotations/segments/{annotation_id}")
def api_delete_segment_annotation(annotation_id: str):
    df = load_segment_annotations_frame()
    if df.empty or "annotation_id" not in df.columns:
        raise HTTPException(status_code=404, detail="Annotation not found")

    before = len(df)
    df = df[df["annotation_id"].astype(str) != str(annotation_id)]
    if len(df) == before:
        raise HTTPException(status_code=404, detail="Annotation not found")

    write_segment_annotations_frame(df)
    return {"status": "ok", "deleted": annotation_id, "n_items": int(len(df))}


@app.post("/api/annotations/segments/rename-label")
def api_rename_segment_label(payload: Dict[str, str]):
    old_name = payload.get("old_name")
    new_name = payload.get("new_name")
    if not old_name or not new_name:
        raise HTTPException(status_code=400, detail="Missing old_name or new_name")
    df = load_segment_annotations_frame()
    if df.empty or "label" not in df.columns:
        return {"status": "ok", "n_updated": 0}

    mask = df["label"].astype(str) == str(old_name)
    n_updated = int(mask.sum())
    if n_updated > 0:
        df.loc[mask, "label"] = new_name
        
        def rename_id(ann_id):
            ann_str = str(ann_id)
            suffix = f"__{old_name}"
            if ann_str.endswith(suffix):
                return ann_str[:-len(suffix)] + f"__{new_name}"
            return ann_str
            
        df.loc[mask, "annotation_id"] = df.loc[mask, "annotation_id"].apply(rename_id)
        write_segment_annotations_frame(df)

    return {"status": "ok", "n_updated": n_updated}


@app.get("/api/segment-model/summary")
def api_segment_model_summary():
    return load_model_summary()


@app.get("/api/segment-model/file/{json_name}")
def api_segment_model_file(
    json_name: str,
    stride_sec: float = Query(1.0, ge=0.2, le=10.0),
    smooth_radius: int = Query(2, ge=0, le=10),
):
    summary = load_model_summary()
    if summary.get("status") != "ok":
        return summary

    model, metadata = load_segment_cnn_model()
    return predict_file(
        json_name=json_name,
        model=model,
        metadata=metadata,
        stride_sec=stride_sec,
        smooth_radius=smooth_radius,
    )


@app.get("/api/file/{json_name}/summary")
def api_file_summary(json_name: str):
    raw = load_raw_json(json_name)

    return {
        "file_id": raw.get("file_id"),
        "file": raw.get("file"),
        "json_name": json_name,
        "date": raw.get("date"),
        "modified_at": raw.get("modified_at"),
        "pipeline": deep_json_safe(raw.get("pipeline", {})),
        "status": deep_json_safe(raw.get("status", {})),
        "n_available_channels": len(raw.get("channels", {}).get("available", [])),
        "n_found_target_channels": len(raw.get("channels", {}).get("target_found", [])),
        "n_missing_target_channels": len(raw.get("channels", {}).get("target_missing", [])),
    }


@app.get("/api/file/{json_name}/channels")
def api_channels(json_name: str):
    raw = load_raw_json(json_name)
    channels_block = raw.get("channels", {})

    time_values = get_time_values(raw)
    time_start_sec = None
    time_end_sec = None
    if time_values:
        try:
            time_start_sec = json_safe_value(time_values[0])
            time_end_sec = json_safe_value(time_values[-1])
        except Exception:
            pass

    return {
        "file": raw.get("file"),
        "json_name": json_name,
        "date": raw.get("date"),
        "modified_at": raw.get("modified_at"),
        "target_hz": json_safe_value(raw.get("pipeline", {}).get("target_hz")),
        "time_start_sec": time_start_sec,
        "time_end_sec": time_end_sec,
        "available_channels": channels_block.get("available", []),
        "target_found": channels_block.get("target_found", []),
        "target_missing": channels_block.get("target_missing", []),
        "target_channel_map": channels_block.get("target_channel_map", {}),
        "source_to_canonical": channels_block.get("source_to_canonical", {}),
        "canonical_to_source": channels_block.get("canonical_to_source", {}),
        "resampled_channels": get_available_resampled_channels(raw),
    }


# ------------------------------------------------------------------
# Raw resampled series
# ------------------------------------------------------------------

@app.get("/api/file/{json_name}/series")
def api_series(
    json_name: str,
    channels: str = Query(..., description="Comma-separated channel names"),
    max_points: int = 8000,
):
    raw = load_raw_json(json_name)
    requested = [c.strip() for c in channels.split(",") if c.strip()]
    try:
        df = load_signal_series_frame(json_name, tuple(requested))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    keep = ["time"] + [c for c in requested if c in df.columns]

    if len(keep) <= 1:
        raise HTTPException(status_code=400, detail="No valid channels requested")

    out = df[keep].copy()

    out = downsample_frame(out, max_points)

    return {
        "file": raw.get("file"),
        "json_name": json_name,
        "date": raw.get("date"),
        "modified_at": raw.get("modified_at"),
        "items": records_json_safe(out),
    }


@app.get("/api/file/{json_name}/rollover-ltr")
def api_rollover_ltr(
    json_name: str,
    max_points: int = Query(8000, ge=100, le=50000),
    warning_threshold: float = Query(0.60, ge=0.0, le=1.0),
    high_threshold: float = Query(0.80, ge=0.0, le=1.0),
    critical_threshold: float = Query(0.90, gt=0.0, le=1.5),
):
    raw = load_raw_json(json_name)
    fz_channels = ["wheel.fl.fz", "wheel.fr.fz", "wheel.rl.fz", "wheel.rr.fz"]
    raw_channels = get_resampled_channels(raw)
    missing = [ch for ch in fz_channels if ch not in raw_channels]
    if missing:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Missing vertical wheel force channels for LTR computation",
                "missing_channels": missing,
                "required_channels": fz_channels,
            },
        )
    try:
        df = load_signal_series_frame(json_name, tuple(fz_channels))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    out = df[["time", *fz_channels]].copy()
    fl = pd.to_numeric(out["wheel.fl.fz"], errors="coerce")
    fr = pd.to_numeric(out["wheel.fr.fz"], errors="coerce")
    rl = pd.to_numeric(out["wheel.rl.fz"], errors="coerce")
    rr = pd.to_numeric(out["wheel.rr.fz"], errors="coerce")

    total_fz = fl + fr + rl + rr
    left_fz = fl + rl
    right_fz = fr + rr
    front_fz = fl + fr
    rear_fz = rl + rr

    out["ltr_total"] = np.where(total_fz.abs() > 1e-9, (right_fz - left_fz) / total_fz, np.nan)
    out["ltr_front"] = np.where(front_fz.abs() > 1e-9, (fr - fl) / front_fz, np.nan)
    out["ltr_rear"] = np.where(rear_fz.abs() > 1e-9, (rr - rl) / rear_fz, np.nan)
    out["abs_ltr_total"] = pd.to_numeric(out["ltr_total"], errors="coerce").abs()
    out["risk_score"] = (out["abs_ltr_total"] / critical_threshold).clip(lower=0.0, upper=1.0)
    out["risk_label"] = [
        classify_ltr_risk(v, warning_threshold, high_threshold, critical_threshold)
        for v in out["abs_ltr_total"]
    ]

    valid_abs = pd.to_numeric(out["abs_ltr_total"], errors="coerce").dropna()
    max_abs_ltr = float(valid_abs.max()) if not valid_abs.empty else None
    p95_abs_ltr = float(valid_abs.quantile(0.95)) if not valid_abs.empty else None
    peak_risk_label = classify_ltr_risk(max_abs_ltr, warning_threshold, high_threshold, critical_threshold)
    sample_hz = raw.get("pipeline", {}).get("target_hz")
    try:
        sample_hz_value = float(sample_hz)
    except (TypeError, ValueError):
        sample_hz_value = None
    sample_period_sec = 1.0 / sample_hz_value if sample_hz_value and sample_hz_value > 0 else None

    risk_counts = out["risk_label"].value_counts(dropna=False).to_dict()
    duration_above_warning_sec = None
    duration_above_high_sec = None
    duration_above_critical_sec = None
    if sample_period_sec is not None:
        duration_above_warning_sec = float((out["abs_ltr_total"] >= warning_threshold).sum() * sample_period_sec)
        duration_above_high_sec = float((out["abs_ltr_total"] >= high_threshold).sum() * sample_period_sec)
        duration_above_critical_sec = float((out["abs_ltr_total"] >= critical_threshold).sum() * sample_period_sec)

    out = downsample_frame(out, max_points)
    keep_cols = [
        "time",
        "ltr_total",
        "ltr_front",
        "ltr_rear",
        "abs_ltr_total",
        "risk_score",
        "risk_label",
        *fz_channels,
    ]

    return deep_json_safe(
        {
            "status": "ok",
            "file": raw.get("file"),
            "json_name": json_name,
            "date": raw.get("date"),
            "modified_at": raw.get("modified_at"),
            "formula": {
                "ltr_total": "((wheel.fr.fz + wheel.rr.fz) - (wheel.fl.fz + wheel.rl.fz)) / total_fz",
                "sign": "positive = charge vertical transfer toward right wheels",
            },
            "thresholds": {
                "warning": warning_threshold,
                "high": high_threshold,
                "critical": critical_threshold,
            },
            "summary": {
                "n_samples": int(len(df)),
                "max_abs_ltr": max_abs_ltr,
                "p95_abs_ltr": p95_abs_ltr,
                "peak_risk_label": peak_risk_label,
                "risk_counts": {str(k): int(v) for k, v in risk_counts.items()},
                "duration_above_warning_sec": duration_above_warning_sec,
                "duration_above_high_sec": duration_above_high_sec,
                "duration_above_critical_sec": duration_above_critical_sec,
            },
            "required_channels": fz_channels,
            "items": records_json_safe(out[keep_cols]),
        }
    )


def build_rollover_groq_context(payload: Dict[str, Any], json_name: str) -> dict[str, Any]:
    raw_segments = payload.get("segments") or []
    labels = []
    if isinstance(raw_segments, list):
        for seg in raw_segments:
            if isinstance(seg, dict) and seg.get("label"):
                labels.append(str(seg.get("label")))
    return {
        "json_name": json_name,
        "segment_filter": payload.get("segment_filter") or {},
        "segment_labels": sorted(set(labels))[:12],
        "signals": ["LTR", "vehicle.vx"],
    }


def build_rollover_analysis_frame(json_name: str) -> pd.DataFrame:
    fz_channels = ["wheel.fl.fz", "wheel.fr.fz", "wheel.rl.fz", "wheel.rr.fz"]
    optional_channels = ["vehicle.vx", "vehicle.roll_angle"]
    try:
        df = load_signal_series_frame(json_name, tuple([*fz_channels, *optional_channels]))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    missing = [ch for ch in fz_channels if ch not in df.columns]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing channels for LTR computation: {', '.join(missing)}")

    out = df[["time", *fz_channels]].copy()
    fl = pd.to_numeric(out["wheel.fl.fz"], errors="coerce")
    fr = pd.to_numeric(out["wheel.fr.fz"], errors="coerce")
    rl = pd.to_numeric(out["wheel.rl.fz"], errors="coerce")
    rr = pd.to_numeric(out["wheel.rr.fz"], errors="coerce")
    total_fz = fl + fr + rl + rr
    out["ltr_total"] = np.where(total_fz.abs() > 1e-9, ((fr + rr) - (fl + rl)) / total_fz, np.nan)
    for ch in optional_channels:
        if ch in df.columns:
            out[ch] = pd.to_numeric(df[ch], errors="coerce")
    if "vehicle.vx" not in out.columns:
        raise HTTPException(status_code=400, detail="Missing vehicle.vx for rollover analysis")
    if "vehicle.roll_angle" not in out.columns:
        raise HTTPException(status_code=400, detail="Missing vehicle.roll_angle for rollover analysis")
    return out


def choose_rollover_segment(payload: Dict[str, Any], rollover_rows: list[dict[str, Any]]) -> dict[str, Any]:
    raw_segments = payload.get("segments") or []
    candidates: list[dict[str, Any]] = []
    if isinstance(raw_segments, list):
        for seg in raw_segments:
            if not isinstance(seg, dict):
                continue
            try:
                start = float(seg.get("start_s"))
                end = float(seg.get("end_s"))
            except (TypeError, ValueError):
                continue
            if end > start:
                item = dict(seg)
                item["start_s"] = start
                item["end_s"] = end
                candidates.append(item)

    if not candidates:
        raise HTTPException(status_code=400, detail="No annotated segment selected for rollover analysis")

    def segment_peak(seg: dict[str, Any]) -> float:
        start = float(seg["start_s"])
        end = float(seg["end_s"])
        values = []
        for row in rollover_rows:
            try:
                time_value = float(row.get("time"))
                ltr_value = float(row.get("ltr_total"))
            except (TypeError, ValueError):
                continue
            if start <= time_value <= end and np.isfinite(ltr_value):
                values.append(abs(ltr_value))
        return max(values) if values else -1.0

    return max(candidates, key=segment_peak)


@app.post("/api/rollover/analyze")
def api_rollover_analyze(payload: Dict[str, Any] = Body(...)):
    json_name = str(payload.get("json_name") or "")
    provider = str(payload.get("provider") or "groq").strip().lower()
    prompt = payload.get("prompt")
    thresholds = payload.get("thresholds") or {}

    df = build_rollover_analysis_frame(json_name)
    rollover_rows = records_json_safe(df[["time", "ltr_total"]])
    vx_rows = records_json_safe(df[["time", "vehicle.vx"]])
    roll_rows = records_json_safe(df[["time", "vehicle.roll_angle"]])
    segment = choose_rollover_segment(payload, rollover_rows)
    segment_start_s = float(segment["start_s"])
    segment_end_s = float(segment["end_s"])

    metrics = compute_segment_metrics(
        rollover_rows,
        vx_rows,
        roll_rows,
        segment_start_s,
        segment_end_s,
        thresholds,
    )
    image_path = crop_segment_image(
        {"ltr": rollover_rows, "vx": vx_rows, "roll": roll_rows},
        segment_start_s,
        segment_end_s,
    )
    try:
        if prompt:
            interpretation = analyze_curve(image_path, provider=provider, segment_metrics=metrics, prompt=str(prompt))
        else:
            interpretation = analyze_curve(image_path, provider=provider, segment_metrics=metrics)
        result = {
            **metrics,
            **interpretation,
            "segment": segment,
            "source_segment_annotation_id": segment.get("annotation_id") or segment.get("id") or "",
            "source_segment_label": segment.get("label") or "",
            "source_segment_source": segment.get("source") or str((payload.get("segment_filter") or {}).get("source") or ""),
            "seuil_critique_approche": metrics.get("seuil_ltr_franchi") in {"warning", "critical"},
            "oscillations_detectees": interpretation.get("oscillations_non_capturees"),
            "correlation_vx_ltr": interpretation.get("coherence_ltr_roulis"),
            "notes": interpretation.get("nuance_seuil"),
        }
        result["date_analyse"] = datetime.utcnow().isoformat() + "Z"
        analysis_id = save_analyse_retournement(json_name, result, PIPELINE_DB_PATH)
        history = get_dernieres_analyses(json_name, PIPELINE_DB_PATH)
    except ProviderRateLimitError as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "message": str(exc),
                "provider": exc.provider,
                "retry_after": exc.retry_after,
                "quota": check_quota(provider),
            },
        ) from exc
    except (RolloverAnalysisError, ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        try:
            image_path.unlink(missing_ok=True)
        except OSError:
            pass

    analysis = format_analysis_markdown(result)
    return deep_json_safe(
        {
            "status": "ok",
            "provider": result.get("provider"),
            "model": result.get("model"),
            "json_name": json_name,
            "analysis_id": analysis_id,
            "analysis": analysis,
            "resultat": result,
            "history": history,
            "ltr_max_abs": result.get("ltr_max_abs"),
            "instant_ltr_max_s": result.get("instant_ltr_max_s"),
            "vx_a_ltr_max_kmh": result.get("vx_a_ltr_max_kmh"),
            "seuil_critique_approche": result.get("seuil_critique_approche"),
            "oscillations_detectees": result.get("oscillations_detectees"),
            "correlation_vx_ltr": result.get("correlation_vx_ltr"),
            "confiance": result.get("confiance"),
            "notes": result.get("notes"),
            "synthese": result.get("synthese"),
            "source_segment_annotation_id": result.get("source_segment_annotation_id"),
            "source_segment_label": result.get("source_segment_label"),
            "source_segment_source": result.get("source_segment_source"),
            "finish_reason": result.get("finish_reason"),
            "raw_usage": result.get("raw_usage"),
            "rate_limit": result.get("rate_limit"),
        }
    )


@app.get("/api/rollover/quota/{provider}")
def api_rollover_quota(provider: str):
    try:
        return deep_json_safe(check_quota(provider))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/rollover/analyses/{essai_id}")
def api_rollover_analysis_history(essai_id: str):
    return {"items": deep_json_safe(get_dernieres_analyses(essai_id, PIPELINE_DB_PATH))}


@app.delete("/api/rollover/analyses/{analysis_id}")
def api_delete_rollover_analysis(analysis_id: int):
    try:
        deleted = delete_analyse_retournement(analysis_id, PIPELINE_DB_PATH)
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"SQLite temporarily unavailable: {exc}") from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Rollover analysis not found")
    return {"status": "deleted", "analysis_id": analysis_id}


@app.post("/api/rollover/analyses/{analysis_id}/versions")
def api_create_rollover_analysis_version(analysis_id: int, payload: Dict[str, Any] = Body(...)):
    try:
        new_id = create_analyse_retournement_version(analysis_id, payload, PIPELINE_DB_PATH)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"SQLite temporarily unavailable: {exc}") from exc
    item = get_analyse_retournement(new_id, PIPELINE_DB_PATH)
    return {"status": "created", "analysis_id": new_id, "item": deep_json_safe(item)}


# ------------------------------------------------------------------
# Global features
# ------------------------------------------------------------------

@app.get("/api/file/{json_name}/features/global")
def api_global_features(json_name: str):
    raw = load_raw_json(json_name)

    return {
        "file": raw.get("file"),
        "json_name": json_name,
        "date": raw.get("date"),
        "modified_at": raw.get("modified_at"),
        "by_channel": deep_json_safe(
            raw.get("features", {}).get("global", {}).get("by_channel", {})
        ),
        "multivariate": deep_json_safe(
            raw.get("features", {}).get("global", {}).get("multivariate", {})
        ),
    }


@app.get("/api/file/{json_name}/features/global/channels")
def api_global_feature_channels(json_name: str):
    raw = load_raw_json(json_name)
    by_channel = raw.get("features", {}).get("global", {}).get("by_channel", {})

    return {
        "file": raw.get("file"),
        "json_name": json_name,
        "channels": sorted(list(by_channel.keys()), key=channel_sort_key),
        "feature_columns": get_global_feature_columns(raw),
    }


# ------------------------------------------------------------------
# Sliding features
# ------------------------------------------------------------------

@app.get("/api/file/{json_name}/features/sliding/columns")
def api_sliding_feature_columns(json_name: str):
    raw = load_raw_json(json_name)

    return {
        "file": raw.get("file"),
        "json_name": json_name,
        "columns": list_sliding_feature_columns(raw),
        "time_points": len(raw.get("features", {}).get("sliding", {}).get("time", [])),
    }


@app.get("/api/file/{json_name}/features/sliding")
def api_sliding_feature_series(
    json_name: str,
    features: str = Query(..., description="Comma-separated feature names, e.g. VelX (km/h)::mean"),
    max_points: int = 8000,
):
    raw = load_raw_json(json_name)

    requested = [f.strip() for f in features.split(",") if f.strip()]

    try:
        df = build_sliding_features_dataframe(raw, requested)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    keep = ["time"] + [c for c in requested if c in df.columns]
    if len(keep) <= 1:
        raise HTTPException(status_code=400, detail="No valid sliding features requested")

    out = df[keep].copy()

    if len(out) > max_points:
        idx = np.linspace(0, len(out) - 1, max_points).astype(int)
        out = out.iloc[idx]

    return {
        "file": raw.get("file"),
        "json_name": json_name,
        "items": records_json_safe(out),
    }


# ------------------------------------------------------------------
# Model Training & Active Learning
# ------------------------------------------------------------------

@app.post("/api/segment-model/train")
def api_train_segment_model(background_tasks: BackgroundTasks, payload: Optional[Dict[str, Any]] = None):
    df = load_segment_annotations_frame()
    if df.empty or "label" not in df.columns or "json_name" not in df.columns:
        raise HTTPException(status_code=400, detail="Aucune annotation disponible pour l'entraînement.")

    payload = payload or {}
    try:
        window_sec = float(payload.get("window_sec", 4.0))
        stride_sec = float(payload.get("stride_sec", 1.0))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="window_sec et stride_sec doivent être numériques.")
    if not 0.5 <= window_sec <= 30.0:
        raise HTTPException(status_code=400, detail="window_sec doit être entre 0.5 et 30.0 secondes.")
    if not 0.1 <= stride_sec <= 10.0:
        raise HTTPException(status_code=400, detail="stride_sec doit être entre 0.1 et 10.0 secondes.")
    if stride_sec > window_sec:
        raise HTTPException(status_code=400, detail="stride_sec doit être inférieur ou égal à window_sec.")
    
    progress_file = MODEL_PROGRESS_PATH
    if progress_file.exists():
        try:
            with open(progress_file, "r") as f:
                progress = json.load(f)
            if progress.get("status") in ("running", "calculating_uncertainty"):
                return {"status": "already_running", "message": "L'entraînement est déjà en cours."}
        except Exception:
            pass
            
    write_json_atomic(MODEL_PROGRESS_PATH, {
        "status": "running",
        "epoch": 0,
        "epochs": 40,
        "window_sec": window_sec,
        "stride_sec": stride_sec,
    })
        
    def run_training():
        try:
            from mas_essais.ml.segment_cnn.model import train_from_annotations, TrainingConfig
            cfg = TrainingConfig(epochs=40, window_sec=window_sec, stride_sec=stride_sec)
            metadata = train_from_annotations(cfg)
            generate_active_learning_cache(metadata)
        except Exception as e:
            write_json_atomic(MODEL_PROGRESS_PATH, {"status": "error", "message": str(e)})
                
    background_tasks.add_task(run_training)
    return {
        "status": "started",
        "message": "Entraînement démarré en arrière-plan.",
        "window_sec": window_sec,
        "stride_sec": stride_sec,
    }


@app.get("/api/segment-model/train/progress")
def api_train_segment_model_progress():
    progress_file = MODEL_PROGRESS_PATH
    if not progress_file.exists():
        return {"status": "not_started"}
    try:
        with open(progress_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"status": "running", "message": "Mise à jour du statut en cours..."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/annotator/active-learning-files")
def api_active_learning_files():
    files = list_json_files()
    annotations_df = load_segment_annotations_frame()
    ann_counts = {}
    if not annotations_df.empty and "json_name" in annotations_df.columns:
        ann_counts = annotations_df["json_name"].value_counts().to_dict()
        
    cache_data = {}
    cache_path = Path("manual_segment_annotations/active_learning_cache.json")
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache_data = json.load(f).get("files", {})
        except Exception:
            pass
            
    ranked_items = []
    for item in files:
        json_name = item["json_name"]
        n_annotations = ann_counts.get(json_name, 0)
        
        cached_info = cache_data.get(json_name, {})
        uncertainty = cached_info.get("uncertainty", 0.0)
        
        if n_annotations == 0:
            priority = 10.0 + uncertainty
        else:
            priority = max(0.0, 5.0 - n_annotations) + uncertainty
            
        ranked_items.append({
            **item,
            "n_annotations": n_annotations,
            "uncertainty": uncertainty,
            "priority": priority,
        })
        
    ranked_items.sort(key=lambda x: x["priority"], reverse=True)
    return {"items": ranked_items}
