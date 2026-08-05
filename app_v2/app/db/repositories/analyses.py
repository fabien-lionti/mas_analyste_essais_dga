from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from app_v2.app.db.connection import init_db, now_iso


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    return json.loads(value)


def row_to_analysis(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "analysis_id": row["analysis_id"],
        "name": row["name"],
        "kind": row["kind"],
        "status": row["status"],
        "source_dxd_dir": row["source_dxd_dir"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "config": _json_loads(row["config_json"], {}),
        "summary": _json_loads(row["summary_json"], {}),
    }


def create_analysis(
    conn: sqlite3.Connection,
    *,
    name: str,
    kind: str = "campaign",
    source_dxd_dir: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    init_db(conn)
    analysis_id = uuid.uuid4().hex
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO analyses(
          analysis_id, name, kind, status, source_dxd_dir,
          created_at, updated_at, config_json, summary_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            analysis_id,
            name,
            kind,
            "active",
            source_dxd_dir,
            ts,
            ts,
            json.dumps(config or {}, ensure_ascii=False),
            json.dumps({}, ensure_ascii=False),
        ),
    )
    return get_analysis(conn, analysis_id)


def get_analysis(conn: sqlite3.Connection, analysis_id: str) -> dict[str, Any] | None:
    init_db(conn)
    row = conn.execute(
        "SELECT * FROM analyses WHERE analysis_id = ?",
        (analysis_id,),
    ).fetchone()
    return row_to_analysis(row) if row else None


def list_analyses(conn: sqlite3.Connection, limit: int = 100) -> list[dict[str, Any]]:
    init_db(conn)
    rows = conn.execute(
        """
        SELECT * FROM analyses
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (max(1, min(int(limit), 1000)),),
    ).fetchall()
    return [row_to_analysis(row) for row in rows]


def update_analysis_summary(conn: sqlite3.Connection, analysis_id: str, summary: dict[str, Any]) -> None:
    init_db(conn)
    conn.execute(
        """
        UPDATE analyses
        SET summary_json = ?, updated_at = ?
        WHERE analysis_id = ?
        """,
        (json.dumps(summary, ensure_ascii=False), now_iso(), analysis_id),
    )


def update_analysis_config(conn: sqlite3.Connection, analysis_id: str, config: dict[str, Any]) -> dict[str, Any] | None:
    init_db(conn)
    analysis = get_analysis(conn, analysis_id)
    if analysis is None:
        return None
    merged = {**analysis["config"], **config}
    conn.execute(
        """
        UPDATE analyses
        SET config_json = ?, updated_at = ?
        WHERE analysis_id = ?
        """,
        (json.dumps(merged, ensure_ascii=False), now_iso(), analysis_id),
    )
    return get_analysis(conn, analysis_id)


def delete_analysis(conn: sqlite3.Connection, analysis_id: str) -> bool:
    init_db(conn)
    cursor = conn.execute("DELETE FROM analyses WHERE analysis_id = ?", (analysis_id,))
    return cursor.rowcount > 0
