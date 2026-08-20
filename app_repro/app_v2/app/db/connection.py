from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "app_v2.v0.analysis_catalog"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(db_path: Path | str) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})")}


def _add_column_if_missing(conn: sqlite3.Connection, table_name: str, column_name: str, ddl: str) -> None:
    if column_name not in _table_columns(conn, table_name):
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {ddl}")


def migrate_db(conn: sqlite3.Connection) -> None:
    _add_column_if_missing(conn, "analysis_files", "recorded_at", "recorded_at TEXT")
    _add_column_if_missing(conn, "analysis_files", "duration_sec", "duration_sec REAL")
    _add_column_if_missing(conn, "dynamic_analysis_prompts", "description", "description TEXT")
    _add_column_if_missing(
        conn,
        "dynamic_analysis_prompts",
        "required_channels_json",
        "required_channels_json TEXT NOT NULL DEFAULT '[]'",
    )
    _add_column_if_missing(
        conn,
        "dynamic_analysis_prompts",
        "output_schema_json",
        "output_schema_json TEXT NOT NULL DEFAULT '{}'",
    )
    _add_column_if_missing(conn, "dynamic_analyses", "protocol_name", "protocol_name TEXT NOT NULL DEFAULT ''")
    _add_column_if_missing(conn, "dynamic_analyses", "description", "description TEXT")
    _add_column_if_missing(conn, "dynamic_analyses", "selected_labels_json", "selected_labels_json TEXT NOT NULL DEFAULT '[]'")
    _add_column_if_missing(conn, "dynamic_annotation_predictions", "analysis_text", "analysis_text TEXT NOT NULL DEFAULT ''")
    _add_column_if_missing(conn, "dynamic_annotation_predictions", "analysis_note", "analysis_note TEXT NOT NULL DEFAULT ''")
    _add_column_if_missing(conn, "dynamic_annotation_predictions", "summary_text", "summary_text TEXT NOT NULL DEFAULT ''")
    _add_column_if_missing(
        conn,
        "dynamic_prediction_corrections",
        "corrected_analysis_text",
        "corrected_analysis_text TEXT NOT NULL DEFAULT ''",
    )
    _add_column_if_missing(
        conn,
        "dynamic_prediction_corrections",
        "corrected_analysis_note",
        "corrected_analysis_note TEXT NOT NULL DEFAULT ''",
    )
    _add_column_if_missing(
        conn,
        "dynamic_prediction_corrections",
        "corrected_summary_text",
        "corrected_summary_text TEXT NOT NULL DEFAULT ''",
    )


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    migrate_db(conn)
    conn.execute(
        """
        INSERT OR IGNORE INTO schema_metadata(key, value, updated_at)
        VALUES ('schema_version', ?, ?)
        """,
        (SCHEMA_VERSION, now_iso()),
    )
    conn.commit()
