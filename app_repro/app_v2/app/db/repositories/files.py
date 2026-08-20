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


def file_id_for_path(path: Path, analysis_id: str) -> str:
    digest = hashlib.sha1(f"{analysis_id}:{path.resolve()}".encode("utf-8")).hexdigest()
    return f"file_{digest[:24]}"


def row_to_file(row: sqlite3.Row) -> dict[str, Any]:
    keys = set(row.keys())
    recorded_at = row["effective_recorded_at"] if "effective_recorded_at" in keys else row["recorded_at"]
    return {
        "file_id": row["file_id"],
        "analysis_id": row["analysis_id"],
        "source_dxd_path": row["source_dxd_path"],
        "source_dxd_name": row["source_dxd_name"],
        "resampled_json_path": row["resampled_json_path"],
        "resampled_json_name": row["resampled_json_name"],
        "status": row["status"],
        "recorded_at": recorded_at,
        "duration_sec": row["duration_sec"],
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
        file_id = file_id_for_path(path, analysis_id)
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
              resampled_json_path, resampled_json_name, status, recorded_at,
              duration_sec, metadata_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, NULL, NULL, ?, ?, NULL, ?, ?, ?)
            ON CONFLICT(analysis_id, source_dxd_path) DO UPDATE SET
              source_dxd_name = excluded.source_dxd_name,
              status = excluded.status,
              recorded_at = COALESCE(analysis_files.recorded_at, excluded.recorded_at),
              metadata_json = excluded.metadata_json,
              updated_at = excluded.updated_at
            """,
            (
                file_id,
                analysis_id,
                str(path),
                path.name,
                "discovered",
                metadata["modified_at"],
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


def list_analysis_files(
    conn: sqlite3.Connection,
    analysis_id: str,
    limit: int = 1000,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    init_db(conn)
    effective_recorded_at = "COALESCE(recorded_at, json_extract(metadata_json, '$.modified_at'))"
    filters = ["analysis_id = ?"]
    params: list[Any] = [analysis_id]
    if date_from:
        filters.append(f"{effective_recorded_at} IS NOT NULL AND date({effective_recorded_at}) >= date(?)")
        params.append(date_from)
    if date_to:
        filters.append(f"{effective_recorded_at} IS NOT NULL AND date({effective_recorded_at}) <= date(?)")
        params.append(date_to)
    params.append(max(1, min(int(limit), 10000)))
    rows = conn.execute(
        f"""
        SELECT *, {effective_recorded_at} AS effective_recorded_at
        FROM analysis_files
        WHERE {" AND ".join(filters)}
        ORDER BY effective_recorded_at ASC, source_dxd_name ASC
        LIMIT ?
        """,
        params,
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


def get_recorded_at_range(conn: sqlite3.Connection, analysis_id: str) -> dict[str, Any]:
    init_db(conn)
    effective_recorded_at = "COALESCE(recorded_at, json_extract(metadata_json, '$.modified_at'))"
    row = conn.execute(
        f"""
        SELECT
          MIN(date({effective_recorded_at})) AS date_min,
          MAX(date({effective_recorded_at})) AS date_max,
          COUNT({effective_recorded_at}) AS dated_file_count,
          COUNT(*) AS file_count
        FROM analysis_files
        WHERE analysis_id = ? AND resampled_json_path IS NOT NULL
        """,
        (analysis_id,),
    ).fetchone()
    date_rows = conn.execute(
        f"""
        SELECT DISTINCT date({effective_recorded_at}) AS recorded_date
        FROM analysis_files
        WHERE analysis_id = ?
          AND resampled_json_path IS NOT NULL
          AND {effective_recorded_at} IS NOT NULL
        ORDER BY recorded_date ASC
        """,
        (analysis_id,),
    ).fetchall()
    return {
        "date_min": row["date_min"] if row else None,
        "date_max": row["date_max"] if row else None,
        "dated_file_count": row["dated_file_count"] if row else 0,
        "file_count": row["file_count"] if row else 0,
        "dates": [item["recorded_date"] for item in date_rows],
    }


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
    resampling_metadata = merged_metadata.get("resampling")
    duration_sec = resampling_metadata.get("duration_sec") if isinstance(resampling_metadata, dict) else None
    if duration_sec is None and existing:
        duration_sec = existing.get("duration_sec")
    conn.execute(
        """
        UPDATE analysis_files
        SET resampled_json_path = ?,
            resampled_json_name = ?,
            status = ?,
            duration_sec = ?,
            metadata_json = ?,
            updated_at = ?
        WHERE analysis_id = ? AND file_id = ?
        """,
        (
            str(json_path),
            json_path.name,
            status,
            duration_sec,
            json.dumps(merged_metadata, ensure_ascii=False),
            now_iso(),
            analysis_id,
            file_id,
        ),
    )
