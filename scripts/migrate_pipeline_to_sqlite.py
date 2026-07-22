from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from mas_essais.domain.dxd_schema import normalize_raw_json_schema
from mas_essais.db.sqlite import (
    DEFAULT_DB_PATH,
    connect,
    init_db,
    refresh_file_catalog,
    write_dataframe_table,
    write_json_artifact,
    write_resampled_json_export,
)
from mas_essais.paths import PROJECT_ROOT


BASE_DIR = PROJECT_ROOT


JSON_ARTIFACTS = {
    "dataset_index": BASE_DIR / "dataset_index.json",
    "correlation_anomaly_index": BASE_DIR / "correlation_anomaly_index.json",
    "window_quality_summary": BASE_DIR / "window_quality_summary.json",
    "window_cluster_summary": BASE_DIR / "window_cluster_summary.json",
    "speed_day_summary": BASE_DIR / "speed_day_summary.json",
    "segment_dataset_index": BASE_DIR / "simple_maneuver_segments" / "dataset_index.json",
    "continuous_batch_summary": BASE_DIR / "trajectory_continuous_outputs" / "batch_summary.json",
}

CSV_TABLES = {
    "window_quality_index": BASE_DIR / "window_quality_index.csv",
    "window_cluster_index": BASE_DIR / "window_cluster_index.csv",
    "speed_day_summary_rows": BASE_DIR / "speed_day_summary.csv",
    "segment_annotations": BASE_DIR / "manual_segment_annotations" / "segments_annotations.csv",
    "simple_maneuver_segments": BASE_DIR / "simple_maneuver_segments" / "segment_index.csv",
}


def load_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def migrate_json_artifacts(conn, verbose: bool) -> dict[str, Any]:
    imported: list[str] = []
    missing: list[str] = []
    dataset_index: dict[str, Any] | None = None

    for name, path in JSON_ARTIFACTS.items():
        if not path.exists():
            missing.append(str(path))
            continue
        payload = load_json(path)
        write_json_artifact(conn, name, path, payload)
        imported.append(name)
        if name == "dataset_index":
            dataset_index = payload
        if verbose:
            print(f"[JSON] {name}: {path}")

    refresh_file_catalog(conn, dataset_index)
    return {"imported": imported, "missing": missing}


def migrate_csv_tables(conn, verbose: bool) -> dict[str, Any]:
    imported: list[str] = []
    missing: list[str] = []

    for table_name, path in CSV_TABLES.items():
        if not path.exists():
            missing.append(str(path))
            continue
        df = pd.read_csv(path)
        write_dataframe_table(conn, table_name, df)
        imported.append(table_name)
        if verbose:
            print(f"[CSV] {table_name}: {path} ({len(df)} rows)")

    return {"imported": imported, "missing": missing}


def migrate_resampled_json(conn, input_dir: Path, verbose: bool) -> dict[str, Any]:
    imported: list[str] = []
    errors: list[dict[str, str]] = []

    for path in sorted(input_dir.glob("*.json")):
        try:
            payload = normalize_raw_json_schema(load_json(path))
            write_resampled_json_export(conn, path.name, payload)
            imported.append(path.name)
            if verbose:
                print(f"[RESAMPLED] {path.name}")
        except Exception as exc:
            errors.append({"path": str(path), "error": str(exc)})

    return {"imported": imported, "errors": errors}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migre les artefacts du pipeline DXD vers une base SQLite."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Chemin de la base SQLite.")
    parser.add_argument(
        "--resampled-json-dir",
        type=Path,
        default=BASE_DIR / "selected_dxd_json_resampled",
        help="Dossier des JSON re-echantillonnes.",
    )
    parser.add_argument(
        "--skip-resampled-json",
        action="store_true",
        help="Ne migre pas les exports JSON re-echantillonnes, qui peuvent etre volumineux.",
    )
    parser.add_argument("--quiet", action="store_true", help="Reduit la sortie console.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    verbose = not args.quiet
    args.db.parent.mkdir(parents=True, exist_ok=True)

    with connect(args.db) as conn:
        init_db(conn)
        json_result = migrate_json_artifacts(conn, verbose)
        csv_result = migrate_csv_tables(conn, verbose)
        resampled_result = {"imported": [], "errors": []}
        if not args.skip_resampled_json:
            resampled_result = migrate_resampled_json(conn, args.resampled_json_dir, verbose)
        conn.commit()

    summary = {
        "database": str(args.db),
        "json_artifacts": {
            "imported": len(json_result["imported"]),
            "missing": len(json_result["missing"]),
        },
        "csv_tables": {
            "imported": len(csv_result["imported"]),
            "missing": len(csv_result["missing"]),
        },
        "resampled_json_exports": {
            "imported": len(resampled_result["imported"]),
            "errors": len(resampled_result["errors"]),
        },
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
