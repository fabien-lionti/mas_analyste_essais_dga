from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from app_v2.app.db.connection import init_db, now_iso
from app_v2.app.db.repositories.analyses import update_analysis_summary
from app_v2.app.db.repositories.events import add_event


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    return json.loads(value)


def file_id_for_path(path: Path) -> str:
    digest = hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()
    return f"file_{digest[:24]}"


def row_to_file(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "file_id": row["file_id"],
        "analysis_id": row["analysis_id"],
        "source_dxd_path": row["source_dxd_path"],
        "source_dxd_name": row["source_dxd_name"],
        "resampled_json_path": row["resampled_json_path"],
        "resampled_json_name": row["resampled_json_name"],
        "status": row["status"],
        "metadata": _json_loads(row["metadata_json"], {}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def discover_dxd_files(
    conn: sqlite3.Connection,
    *,
    analysis_id: str,
    dxd_dir: Path,
    recursive: bool = False,
) -> dict[str, Any]:
    init_db(conn)
    candidates = dxd_dir.rglob("*") if recursive else dxd_dir.iterdir()
    files = sorted(
        path for path in candidates if path.is_file() and path.suffix.lower() == ".dxd"
    )
    ts = now_iso()
    inserted = 0
    updated = 0

    for path in files:
        stat = path.stat()
        file_id = file_id_for_path(path)
        metadata = {
            "size_bytes": stat.st_size,
            "modified_at": ts_from_stat(stat.st_mtime),
            "recursive": recursive,
        }
        existing = conn.execute(
            """
            SELECT file_id FROM analysis_files
            WHERE analysis_id = ? AND source_dxd_path = ?
            """,
            (analysis_id, str(path)),
        ).fetchone()
        if existing:
            updated += 1
        else:
            inserted += 1
        conn.execute(
            """
            INSERT INTO analysis_files(
              file_id, analysis_id, source_dxd_path, source_dxd_name,
              resampled_json_path, resampled_json_name, status, metadata_json,
              created_at, updated_at
            )
            VALUES (?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?)
            ON CONFLICT(analysis_id, source_dxd_path) DO UPDATE SET
              source_dxd_name = excluded.source_dxd_name,
              status = excluded.status,
              metadata_json = excluded.metadata_json,
              updated_at = excluded.updated_at
            """,
            (
                file_id,
                analysis_id,
                str(path),
                path.name,
                "discovered",
                json.dumps(metadata, ensure_ascii=False),
                ts,
                ts,
            ),
        )

    summary = {
        "dxd_dir": str(dxd_dir),
        "recursive": recursive,
        "discovered_files": len(files),
        "inserted_files": inserted,
        "updated_files": updated,
    }
    update_analysis_summary(conn, analysis_id, summary)
    add_event(
        conn,
        analysis_id,
        level="info",
        event_type="dxd_discovery_finished",
        message=f"{len(files)} fichier(s) DXD decouvert(s)",
        payload=summary,
    )
    return summary


def ts_from_stat(value: float) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def list_analysis_files(conn: sqlite3.Connection, analysis_id: str, limit: int = 1000) -> list[dict[str, Any]]:
    init_db(conn)
    rows = conn.execute(
        """
        SELECT * FROM analysis_files
        WHERE analysis_id = ?
        ORDER BY source_dxd_name ASC
        LIMIT ?
        """,
        (analysis_id, max(1, min(int(limit), 10000))),
    ).fetchall()
    return [row_to_file(row) for row in rows]


def get_analysis_file(conn: sqlite3.Connection, analysis_id: str, file_id: str) -> dict[str, Any] | None:
    init_db(conn)
    row = conn.execute(
        """
        SELECT * FROM analysis_files
        WHERE analysis_id = ? AND file_id = ?
        """,
        (analysis_id, file_id),
    ).fetchone()
    return row_to_file(row) if row else None


def update_file_resampled_json(
    conn: sqlite3.Connection,
    *,
    analysis_id: str,
    file_id: str,
    json_path: Path,
    metadata: dict[str, Any] | None = None,
    status: str = "resampled",
) -> None:
    init_db(conn)
    existing = get_analysis_file(conn, analysis_id, file_id)
    merged_metadata = {**(existing["metadata"] if existing else {}), **(metadata or {})}
    conn.execute(
        """
        UPDATE analysis_files
        SET resampled_json_path = ?,
            resampled_json_name = ?,
            status = ?,
            metadata_json = ?,
            updated_at = ?
        WHERE analysis_id = ? AND file_id = ?
        """,
        (
            str(json_path),
            json_path.name,
            status,
            json.dumps(merged_metadata, ensure_ascii=False),
            now_iso(),
            analysis_id,
            file_id,
        ),
    )
