from __future__ import annotations

import json
import sqlite3
from typing import Any

from app_v2.app.db.connection import init_db, now_iso


def add_event(
    conn: sqlite3.Connection,
    analysis_id: str,
    *,
    level: str,
    event_type: str,
    message: str | None = None,
    payload: dict[str, Any] | None = None,
    task_id: str | None = None,
) -> None:
    init_db(conn)
    conn.execute(
        """
        INSERT INTO analysis_events(
          analysis_id, task_id, level, event_type, message, payload_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            analysis_id,
            task_id,
            level,
            event_type,
            message,
            json.dumps(payload or {}, ensure_ascii=False),
            now_iso(),
        ),
    )


def list_events(conn: sqlite3.Connection, analysis_id: str, limit: int = 200) -> list[dict[str, Any]]:
    init_db(conn)
    rows = conn.execute(
        """
        SELECT * FROM analysis_events
        WHERE analysis_id = ?
        ORDER BY event_id DESC
        LIMIT ?
        """,
        (analysis_id, max(1, min(int(limit), 1000))),
    ).fetchall()
    return [
        {
            "event_id": row["event_id"],
            "analysis_id": row["analysis_id"],
            "task_id": row["task_id"],
            "level": row["level"],
            "event_type": row["event_type"],
            "message": row["message"],
            "payload": json.loads(row["payload_json"] or "{}"),
            "created_at": row["created_at"],
        }
        for row in rows
    ]
