from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from mas_essais.paths import PROJECT_ROOT

BASE_DIR = PROJECT_ROOT
DEFAULT_DB_PATH = BASE_DIR / "pipeline.sqlite"
RAW_JSON_DIR = BASE_DIR / "selected_dxd_json_resampled"
SCHEMA_VERSION = "pipeline_sqlite.v1"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS pipeline_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS json_artifacts (
            name TEXT PRIMARY KEY,
            path TEXT,
            schema_version TEXT,
            payload_json TEXT NOT NULL,
            loaded_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS resampled_json_exports (
            json_name TEXT PRIMARY KEY,
            file TEXT,
            file_id TEXT,
            date TEXT,
            modified_at TEXT,
            payload_json TEXT NOT NULL,
            loaded_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS file_catalog (
            json_name TEXT PRIMARY KEY,
            file_id TEXT,
            file TEXT,
            date TEXT,
            modified_at TEXT,
            can_open INTEGER,
            has_all_target_channels INTEGER,
            has_resampled_data INTEGER,
            has_features INTEGER,
            target_missing_count INTEGER,
            open_error TEXT,
            json_path TEXT,
            loaded_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS pipeline_analyses (
            analysis_id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            config_json TEXT NOT NULL,
            summary_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS pipeline_analysis_files (
            analysis_id TEXT NOT NULL,
            json_name TEXT NOT NULL,
            file TEXT,
            file_id TEXT,
            date TEXT,
            modified_at TEXT,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (analysis_id, json_name),
            FOREIGN KEY (analysis_id) REFERENCES pipeline_analyses(analysis_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS pipeline_analysis_artifacts (
            analysis_id TEXT NOT NULL,
            artifact_name TEXT NOT NULL,
            artifact_type TEXT NOT NULL,
            path TEXT,
            payload_json TEXT,
            created_at TEXT NOT NULL,
            PRIMARY KEY (analysis_id, artifact_name),
            FOREIGN KEY (analysis_id) REFERENCES pipeline_analyses(analysis_id) ON DELETE CASCADE
        );
        """
    )
    conn.execute(
        """
        INSERT INTO pipeline_metadata(key, value, updated_at)
        VALUES ('schema_version', ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        (SCHEMA_VERSION, now_iso()),
    )
    conn.commit()


def ensure_analysis_tables(conn: sqlite3.Connection) -> None:
    init_db(conn)
    cols = table_columns(conn, "resampled_json_exports")
    if "analysis_id" not in cols:
        conn.execute('ALTER TABLE resampled_json_exports ADD COLUMN analysis_id TEXT')
    conn.execute(
        'CREATE INDEX IF NOT EXISTS idx_resampled_json_exports_analysis_id '
        'ON resampled_json_exports(analysis_id)'
    )
    conn.execute(
        'CREATE INDEX IF NOT EXISTS idx_pipeline_analysis_files_json_name '
        'ON pipeline_analysis_files(json_name)'
    )


def create_pipeline_analysis(
    conn: sqlite3.Connection,
    *,
    kind: str,
    title: str,
    config: dict[str, Any],
    status: str = "running",
) -> str:
    ensure_analysis_tables(conn)
    analysis_id = uuid.uuid4().hex
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO pipeline_analyses(
            analysis_id, kind, title, status, created_at, updated_at, config_json, summary_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            analysis_id,
            kind,
            title,
            status,
            ts,
            ts,
            json.dumps(config, ensure_ascii=False),
            json.dumps({}, ensure_ascii=False),
        ),
    )
    return analysis_id


def update_pipeline_analysis(
    conn: sqlite3.Connection,
    analysis_id: str,
    *,
    status: str | None = None,
    summary: dict[str, Any] | None = None,
) -> None:
    ensure_analysis_tables(conn)
    updates = ["updated_at = ?"]
    params: list[Any] = [now_iso()]
    if status is not None:
        updates.append("status = ?")
        params.append(status)
    if summary is not None:
        updates.append("summary_json = ?")
        params.append(json.dumps(summary, ensure_ascii=False))
    params.append(analysis_id)
    conn.execute(
        f"UPDATE pipeline_analyses SET {', '.join(updates)} WHERE analysis_id = ?",
        params,
    )


def link_analysis_file(
    conn: sqlite3.Connection,
    analysis_id: str,
    json_name: str,
    payload: dict[str, Any],
    *,
    role: str = "resampled_json",
) -> None:
    ensure_analysis_tables(conn)
    conn.execute(
        """
        INSERT INTO pipeline_analysis_files(
            analysis_id, json_name, file, file_id, date, modified_at, role, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(analysis_id, json_name) DO UPDATE SET
            file = excluded.file,
            file_id = excluded.file_id,
            date = excluded.date,
            modified_at = excluded.modified_at,
            role = excluded.role
        """,
        (
            analysis_id,
            json_name,
            payload.get("file"),
            payload.get("file_id"),
            payload.get("date"),
            payload.get("modified_at"),
            role,
            now_iso(),
        ),
    )


def write_analysis_artifact(
    conn: sqlite3.Connection,
    analysis_id: str,
    artifact_name: str,
    artifact_type: str,
    *,
    path: Path | str | None = None,
    payload: dict[str, Any] | list[Any] | None = None,
) -> None:
    ensure_analysis_tables(conn)
    conn.execute(
        """
        INSERT INTO pipeline_analysis_artifacts(
            analysis_id, artifact_name, artifact_type, path, payload_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(analysis_id, artifact_name) DO UPDATE SET
            artifact_type = excluded.artifact_type,
            path = excluded.path,
            payload_json = excluded.payload_json,
            created_at = excluded.created_at
        """,
        (
            analysis_id,
            artifact_name,
            artifact_type,
            str(path) if path is not None else None,
            json.dumps(payload, ensure_ascii=False) if payload is not None else None,
            now_iso(),
        ),
    )


def list_pipeline_analyses(
    db_path: Path | str = DEFAULT_DB_PATH,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    if not database_ready(db_path):
        return []
    with connect(db_path) as conn:
        ensure_analysis_tables(conn)
        rows = conn.execute(
            """
            SELECT analysis_id, kind, title, status, created_at, updated_at, config_json, summary_json
            FROM pipeline_analyses
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (max(1, min(int(limit), 1000)),),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["config"] = json.loads(item.pop("config_json") or "{}")
        item["summary"] = json.loads(item.pop("summary_json") or "{}")
        out.append(item)
    return out


def get_pipeline_analysis(
    analysis_id: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> dict[str, Any] | None:
    if not database_ready(db_path):
        return None
    with connect(db_path) as conn:
        ensure_analysis_tables(conn)
        row = conn.execute(
            """
            SELECT analysis_id, kind, title, status, created_at, updated_at, config_json, summary_json
            FROM pipeline_analyses
            WHERE analysis_id = ?
            """,
            (analysis_id,),
        ).fetchone()
        if row is None:
            return None
        files = conn.execute(
            """
            SELECT json_name, file, file_id, date, modified_at, role, created_at
            FROM pipeline_analysis_files
            WHERE analysis_id = ?
            ORDER BY json_name
            """,
            (analysis_id,),
        ).fetchall()
        artifacts = conn.execute(
            """
            SELECT artifact_name, artifact_type, path, payload_json, created_at
            FROM pipeline_analysis_artifacts
            WHERE analysis_id = ?
            ORDER BY artifact_name
            """,
            (analysis_id,),
        ).fetchall()
    item = dict(row)
    item["config"] = json.loads(item.pop("config_json") or "{}")
    item["summary"] = json.loads(item.pop("summary_json") or "{}")
    item["files"] = [dict(file_row) for file_row in files]
    item["artifacts"] = []
    for artifact_row in artifacts:
        artifact = dict(artifact_row)
        payload_json = artifact.pop("payload_json")
        artifact["payload"] = json.loads(payload_json) if payload_json else None
        item["artifacts"].append(artifact)
    return item


def database_ready(db_path: Path | str = DEFAULT_DB_PATH) -> bool:
    path = Path(db_path)
    if not path.exists():
        return False
    try:
        with connect(path) as conn:
            row = conn.execute(
                "SELECT value FROM pipeline_metadata WHERE key = 'schema_version'"
            ).fetchone()
            return bool(row and row["value"] == SCHEMA_VERSION)
    except sqlite3.Error:
        return False


def read_json_artifact(name: str, db_path: Path | str = DEFAULT_DB_PATH) -> dict[str, Any] | None:
    if not database_ready(db_path):
        return None
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT payload_json FROM json_artifacts WHERE name = ?",
            (name,),
        ).fetchone()
    if row is None:
        return None
    return json.loads(row["payload_json"])


def write_json_artifact(
    conn: sqlite3.Connection,
    name: str,
    path: Path,
    payload: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO json_artifacts(name, path, schema_version, payload_json, loaded_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            path = excluded.path,
            schema_version = excluded.schema_version,
            payload_json = excluded.payload_json,
            loaded_at = excluded.loaded_at
        """,
        (
            name,
            str(path),
            str(payload.get("schema_version") or ""),
            json.dumps(payload, ensure_ascii=False),
            now_iso(),
        ),
    )


def read_resampled_json(json_name: str, db_path: Path | str = DEFAULT_DB_PATH) -> dict[str, Any] | None:
    if not database_ready(db_path):
        return None
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT payload_json FROM resampled_json_exports WHERE json_name = ?",
            (json_name,),
        ).fetchone()
    if row is None:
        return None
    return json.loads(row["payload_json"])


def write_resampled_json_export(
    conn: sqlite3.Connection,
    json_name: str,
    payload: dict[str, Any],
    analysis_id: str | None = None,
) -> None:
    ensure_analysis_tables(conn)
    conn.execute(
        """
        INSERT INTO resampled_json_exports(
            json_name, file, file_id, date, modified_at, payload_json, loaded_at, analysis_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(json_name) DO UPDATE SET
            file = excluded.file,
            file_id = excluded.file_id,
            date = excluded.date,
            modified_at = excluded.modified_at,
            payload_json = excluded.payload_json,
            loaded_at = excluded.loaded_at,
            analysis_id = excluded.analysis_id
        """,
        (
            json_name,
            payload.get("file"),
            payload.get("file_id"),
            payload.get("date"),
            payload.get("modified_at"),
            json.dumps(payload, ensure_ascii=False),
            now_iso(),
            analysis_id,
        ),
    )
    if analysis_id:
        link_analysis_file(conn, analysis_id, json_name, payload)
    upsert_file_catalog_from_export(conn, json_name, payload)


def upsert_file_catalog_from_export(
    conn: sqlite3.Connection,
    json_name: str,
    payload: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO file_catalog(
            json_name, file_id, file, date, modified_at, can_open,
            has_all_target_channels, has_resampled_data, has_features,
            target_missing_count, open_error, json_path, loaded_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(json_name) DO UPDATE SET
            file_id = excluded.file_id,
            file = excluded.file,
            date = excluded.date,
            modified_at = excluded.modified_at,
            can_open = excluded.can_open,
            has_all_target_channels = excluded.has_all_target_channels,
            has_resampled_data = excluded.has_resampled_data,
            has_features = excluded.has_features,
            target_missing_count = excluded.target_missing_count,
            open_error = excluded.open_error,
            json_path = excluded.json_path,
            loaded_at = excluded.loaded_at
        """,
        (
            json_name,
            payload.get("file_id"),
            payload.get("file"),
            payload.get("date"),
            payload.get("modified_at"),
            1,
            None,
            1,
            1 if payload.get("features") else 0,
            len((payload.get("pipeline") or {}).get("missing_requested_channels") or []),
            "",
            str(RAW_JSON_DIR / json_name),
            now_iso(),
        ),
    )


def refresh_file_catalog(conn: sqlite3.Connection, dataset_index: dict[str, Any] | None) -> None:
    conn.execute("DELETE FROM file_catalog")
    loaded_at = now_iso()
    files = (dataset_index or {}).get("files") or []
    for item in files:
        json_path = item.get("json_path")
        json_name = Path(json_path).name if json_path else f"{item.get('file', 'unknown')}.json"
        conn.execute(
            """
            INSERT INTO file_catalog(
                json_name, file_id, file, date, modified_at, can_open,
                has_all_target_channels, has_resampled_data, has_features,
                target_missing_count, open_error, json_path, loaded_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                json_name,
                item.get("file_id"),
                item.get("file"),
                item.get("date"),
                item.get("modified_at"),
                _bool_to_int(item.get("can_open")),
                _bool_to_int(item.get("has_all_target_channels")),
                _bool_to_int(item.get("has_resampled_data")),
                _bool_to_int(item.get("has_features")),
                item.get("target_missing_count"),
                item.get("open_error", ""),
                json_path,
                loaded_at,
            ),
        )


def list_file_catalog(db_path: Path | str = DEFAULT_DB_PATH) -> list[dict[str, Any]]:
    if not database_ready(db_path):
        return []
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT file_id, file, json_name, date, modified_at, can_open,
                   has_all_target_channels, has_resampled_data, has_features,
                   target_missing_count, open_error
            FROM file_catalog
            ORDER BY date, file, json_name
            """
        ).fetchall()
    return [_row_to_json_dict(row) for row in rows]


def write_dataframe_table(conn: sqlite3.Connection, table_name: str, df: pd.DataFrame) -> None:
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    create_common_indexes(conn, table_name, df.columns)


def read_dataframe_table(
    table_name: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> pd.DataFrame | None:
    if not database_ready(db_path):
        return None
    with connect(db_path) as conn:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        if exists is None:
            return None
        return pd.read_sql_query(f'SELECT * FROM "{table_name}"', conn)


def read_segment_annotations_filtered(
    db_path: Path | str = DEFAULT_DB_PATH,
    *,
    json_name: str | None = None,
    label: str | None = None,
    limit: int | None = None,
) -> pd.DataFrame | None:
    if not database_ready(db_path):
        return None
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'segment_annotations'"
        ).fetchone()
        if row is None:
            return None
        available_cols = table_columns(conn, "segment_annotations")
        where: list[str] = []
        params: list[Any] = []
        if json_name and "json_name" in available_cols:
            where.append('"json_name" = ?')
            params.append(json_name)
        if label and "label" in available_cols:
            where.append('"label" = ?')
            params.append(label)
        sql = 'SELECT * FROM "segment_annotations"'
        if where:
            sql += " WHERE " + " AND ".join(where)
        order_cols = [c for c in ["json_name", "start_sec", "end_sec"] if c in available_cols]
        if order_cols:
            sql += " ORDER BY " + ", ".join(f"{_quote(c)} ASC" for c in order_cols)
        if limit is not None:
            sql += " LIMIT ?"
            params.append(max(1, int(limit)))
        return pd.read_sql_query(sql, conn, params=params)


def read_segment_annotation_label_counts(
    db_path: Path | str = DEFAULT_DB_PATH,
) -> list[dict[str, Any]] | None:
    if not database_ready(db_path):
        return None
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'segment_annotations'"
        ).fetchone()
        if row is None:
            return None
        available_cols = table_columns(conn, "segment_annotations")
        if "label" not in available_cols:
            return []
        rows = conn.execute(
            """
            SELECT "label" AS label, COUNT(*) AS count
            FROM "segment_annotations"
            WHERE "label" IS NOT NULL AND CAST("label" AS TEXT) != ''
            GROUP BY "label"
            ORDER BY "label"
            """
        ).fetchall()
        return [{"label": row["label"], "count": int(row["count"])} for row in rows]


def table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    return {str(row["name"]) for row in rows}


def read_window_quality_filtered(
    db_path: Path | str = DEFAULT_DB_PATH,
    *,
    json_name: str | None = None,
    maneuver_family: str | None = None,
    cluster_id: str | None = None,
    usable_for_regression: bool | None = None,
    min_global_quality: float | None = None,
    limit: int = 200,
    sort: str = "quality",
    columns: list[str] | None = None,
) -> pd.DataFrame | None:
    if not database_ready(db_path):
        return None

    with connect(db_path) as conn:
        table_name = _first_existing_table(conn, ["window_cluster_index", "window_quality_index"])
        if table_name is None:
            return None

        available_cols = table_columns(conn, table_name)
        selected_cols = [c for c in (columns or sorted(available_cols)) if c in available_cols]
        if not selected_cols:
            selected_cols = sorted(available_cols)

        where: list[str] = []
        params: list[Any] = []
        if json_name and "json_name" in available_cols:
            where.append('"json_name" = ?')
            params.append(json_name)
        if maneuver_family and "maneuver_family" in available_cols:
            where.append('"maneuver_family" = ?')
            params.append(maneuver_family)
        if cluster_id and "cluster_id" in available_cols:
            if cluster_id == "noise" and "cluster_is_noise" in available_cols:
                where.append('("cluster_is_noise" IN (1, "1", "True", "true"))')
            else:
                where.append('"cluster_id" = ?')
                params.append(cluster_id)
        if usable_for_regression is not None and "usable_for_regression" in available_cols:
            if usable_for_regression:
                where.append('("usable_for_regression" IN (1, "1", "True", "true"))')
            else:
                where.append('("usable_for_regression" IN (0, "0", "False", "false"))')
        if min_global_quality is not None and "global_quality_score" in available_cols:
            where.append('CAST("global_quality_score" AS REAL) >= ?')
            params.append(float(min_global_quality))

        order_by = _window_quality_order_by(sort, available_cols, bool(json_name))
        sql = f'SELECT {", ".join(_quote(c) for c in selected_cols)} FROM "{table_name}"'
        if where:
            sql += " WHERE " + " AND ".join(where)
        if order_by:
            sql += " ORDER BY " + order_by
        sql += " LIMIT ?"
        params.append(max(1, min(int(limit), 50000)))
        return pd.read_sql_query(sql, conn, params=params)


def read_window_quality_series(
    json_name: str,
    db_path: Path | str = DEFAULT_DB_PATH,
    *,
    columns: list[str] | None = None,
) -> pd.DataFrame | None:
    if not database_ready(db_path):
        return None
    with connect(db_path) as conn:
        table_name = _first_existing_table(conn, ["window_cluster_index", "window_quality_index"])
        if table_name is None:
            return None
        available_cols = table_columns(conn, table_name)
        if "json_name" not in available_cols:
            return None
        selected_cols = [c for c in (columns or sorted(available_cols)) if c in available_cols]
        if not selected_cols:
            selected_cols = sorted(available_cols)
        order_by = '"window_start_sec" ASC' if "window_start_sec" in available_cols else '"json_name" ASC'
        sql = (
            f'SELECT {", ".join(_quote(c) for c in selected_cols)} '
            f'FROM "{table_name}" WHERE "json_name" = ? ORDER BY {order_by}'
        )
        return pd.read_sql_query(sql, conn, params=[json_name])


def create_common_indexes(conn: sqlite3.Connection, table_name: str, columns: Any) -> None:
    available = {str(c) for c in columns}
    indexed_columns = [
        "json_name",
        "annotation_id",
        "label",
        "date",
        "maneuver_family",
        "cluster_id",
        "cluster_is_noise",
        "usable_for_regression",
        "global_quality_score",
        "window_start_sec",
        "speed_bin",
    ]
    for col in indexed_columns:
        if col not in available:
            continue
        index_name = f"idx_{table_name}_{col}".replace(".", "_").replace("-", "_")
        conn.execute(f'CREATE INDEX IF NOT EXISTS "{index_name}" ON "{table_name}"("{col}")')


def _first_existing_table(conn: sqlite3.Connection, table_names: list[str]) -> str | None:
    for table_name in table_names:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        if row is not None:
            return table_name
    return None


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _window_quality_order_by(sort: str, available_cols: set[str], has_json_filter: bool) -> str:
    if sort == "time" and "window_start_sec" in available_cols:
        cols = [c for c in ["date", "json_name", "window_start_sec"] if c in available_cols]
        return ", ".join(f"{_quote(c)} ASC" for c in cols)
    if sort == "speed_bin" and "speed_bin" in available_cols:
        order = [
            """CASE "speed_bin"
                WHEN '0_20' THEN 0
                WHEN '20_40' THEN 1
                WHEN '40_60' THEN 2
                WHEN '60_80' THEN 3
                WHEN '80_100' THEN 4
                WHEN '100_120' THEN 5
                WHEN 'out_of_range' THEN 6
                WHEN 'unknown' THEN 7
                ELSE 99
            END ASC"""
        ]
        order.extend(f"{_quote(c)} ASC" for c in ["date", "json_name", "window_start_sec"] if c in available_cols)
        return ", ".join(order)
    if has_json_filter and "window_start_sec" in available_cols:
        return '"window_start_sec" ASC'
    cols = [c for c in ["global_quality_score", "signal_quality_score"] if c in available_cols]
    return ", ".join(f'CAST({_quote(c)} AS REAL) DESC' for c in cols)


def _bool_to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return 1 if bool(value) else 0


def _row_to_json_dict(row: sqlite3.Row) -> dict[str, Any]:
    out = dict(row)
    for key in (
        "can_open",
        "has_all_target_channels",
        "has_resampled_data",
        "has_features",
    ):
        if out.get(key) is not None:
            out[key] = bool(out[key])
    return out
