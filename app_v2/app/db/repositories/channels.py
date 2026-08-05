from __future__ import annotations

import json
import sqlite3
from typing import Any, Iterable

from app_v2.app.db.connection import init_db, now_iso


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    return json.loads(value)


def replace_channel_structure(
    conn: sqlite3.Connection,
    *,
    analysis_id: str,
    preset_name: str,
    normalize_names: bool,
    min_frequency: float,
    target_channels: list[str],
    recurrent_channels: list[dict[str, Any]],
    summary: dict[str, Any],
    status: str = "finished",
) -> None:
    init_db(conn)
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO channel_structures(
          analysis_id, preset_name, normalize_names, min_frequency,
          target_channels_json, recurrent_channels_json, summary_json,
          status, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(analysis_id) DO UPDATE SET
          preset_name = excluded.preset_name,
          normalize_names = excluded.normalize_names,
          min_frequency = excluded.min_frequency,
          target_channels_json = excluded.target_channels_json,
          recurrent_channels_json = excluded.recurrent_channels_json,
          summary_json = excluded.summary_json,
          status = excluded.status,
          updated_at = excluded.updated_at
        """,
        (
            analysis_id,
            preset_name,
            1 if normalize_names else 0,
            float(min_frequency),
            json.dumps(target_channels, ensure_ascii=False),
            json.dumps(recurrent_channels, ensure_ascii=False),
            json.dumps(summary, ensure_ascii=False),
            status,
            ts,
            ts,
        ),
    )


def get_channel_structure(conn: sqlite3.Connection, analysis_id: str) -> dict[str, Any] | None:
    init_db(conn)
    row = conn.execute(
        "SELECT * FROM channel_structures WHERE analysis_id = ?",
        (analysis_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "analysis_id": row["analysis_id"],
        "preset_name": row["preset_name"],
        "normalize_names": bool(row["normalize_names"]),
        "min_frequency": row["min_frequency"],
        "target_channels": _json_loads(row["target_channels_json"], []),
        "recurrent_channels": _json_loads(row["recurrent_channels_json"], []),
        "summary": _json_loads(row["summary_json"], {}),
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def replace_channel_presence(
    conn: sqlite3.Connection,
    *,
    analysis_id: str,
    rows: Iterable[dict[str, Any]],
) -> None:
    init_db(conn)
    conn.execute("DELETE FROM channel_presence WHERE analysis_id = ?", (analysis_id,))
    ts = now_iso()
    conn.executemany(
        """
        INSERT INTO channel_presence(
          analysis_id, file_id, channel_name, canonical_name, present,
          sample_rate, metadata_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                analysis_id,
                row["file_id"],
                row["channel_name"],
                row["canonical_name"],
                1 if row.get("present") else 0,
                row.get("sample_rate"),
                json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                ts,
            )
            for row in rows
        ],
    )


def list_channel_presence(
    conn: sqlite3.Connection,
    analysis_id: str,
    *,
    file_id: str | None = None,
    present: bool | None = None,
    limit: int = 50000,
) -> list[dict[str, Any]]:
    init_db(conn)
    where = ["analysis_id = ?"]
    params: list[Any] = [analysis_id]
    if file_id:
        where.append("file_id = ?")
        params.append(file_id)
    if present is not None:
        where.append("present = ?")
        params.append(1 if present else 0)
    params.append(max(1, min(int(limit), 200000)))
    rows = conn.execute(
        f"""
        SELECT * FROM channel_presence
        WHERE {' AND '.join(where)}
        ORDER BY canonical_name ASC, file_id ASC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [
        {
            "analysis_id": row["analysis_id"],
            "file_id": row["file_id"],
            "channel_name": row["channel_name"],
            "canonical_name": row["canonical_name"],
            "present": bool(row["present"]),
            "sample_rate": row["sample_rate"],
            "metadata": _json_loads(row["metadata_json"], {}),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def recurrent_channels_from_presence(
    conn: sqlite3.Connection,
    analysis_id: str,
    *,
    min_frequency: float = 0.8,
) -> list[dict[str, Any]]:
    init_db(conn)
    total_row = conn.execute(
        "SELECT COUNT(DISTINCT file_id) AS n FROM channel_presence WHERE analysis_id = ?",
        (analysis_id,),
    ).fetchone()
    total_files = int(total_row["n"] or 0)
    if total_files <= 0:
        return []
    threshold = max(0.0, min(float(min_frequency), 1.0))
    rows = conn.execute(
        """
        SELECT canonical_name, channel_name, SUM(present) AS present_count, COUNT(*) AS row_count
        FROM channel_presence
        WHERE analysis_id = ?
        GROUP BY canonical_name
        ORDER BY canonical_name ASC
        """,
        (analysis_id,),
    ).fetchall()
    out = []
    for row in rows:
        present_count = int(row["present_count"] or 0)
        frequency = present_count / total_files if total_files else 0.0
        if frequency >= threshold:
            out.append(
                {
                    "channel": row["canonical_name"],
                    "source_name": row["channel_name"],
                    "present_count": present_count,
                    "total_files": total_files,
                    "frequency": frequency,
                }
            )
    return out


def replace_channel_inventory(
    conn: sqlite3.Connection,
    *,
    analysis_id: str,
    rows: Iterable[dict[str, Any]],
) -> None:
    init_db(conn)
    conn.execute("DELETE FROM channel_inventory WHERE analysis_id = ?", (analysis_id,))
    ts = now_iso()
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["file_id"], row["canonical_name"])
        if key not in deduped:
            deduped[key] = row
            continue
        existing = deduped[key]
        metadata = dict(existing.get("metadata") or {})
        aliases = metadata.setdefault("source_aliases", [])
        if row["channel_name"] not in aliases and row["channel_name"] != existing["channel_name"]:
            aliases.append(row["channel_name"])
        existing["metadata"] = metadata
    conn.executemany(
        """
        INSERT INTO channel_inventory(
          analysis_id, file_id, channel_name, canonical_name, unit,
          sample_rate, metadata_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                analysis_id,
                row["file_id"],
                row["channel_name"],
                row["canonical_name"],
                row.get("unit"),
                row.get("sample_rate"),
                json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                ts,
            )
            for row in deduped.values()
        ],
    )


def list_channel_inventory(
    conn: sqlite3.Connection,
    analysis_id: str,
    *,
    file_id: str | None = None,
    channel: str | None = None,
    limit: int = 50000,
) -> list[dict[str, Any]]:
    init_db(conn)
    where = ["analysis_id = ?"]
    params: list[Any] = [analysis_id]
    if file_id:
        where.append("file_id = ?")
        params.append(file_id)
    if channel:
        where.append("canonical_name = ?")
        params.append(channel)
    params.append(max(1, min(int(limit), 200000)))
    rows = conn.execute(
        f"""
        SELECT * FROM channel_inventory
        WHERE {' AND '.join(where)}
        ORDER BY file_id ASC, canonical_name ASC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [
        {
            "analysis_id": row["analysis_id"],
            "file_id": row["file_id"],
            "channel_name": row["channel_name"],
            "canonical_name": row["canonical_name"],
            "unit": row["unit"],
            "sample_rate": row["sample_rate"],
            "metadata": _json_loads(row["metadata_json"], {}),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def recurrent_channels_from_inventory(conn: sqlite3.Connection, analysis_id: str) -> list[dict[str, Any]]:
    init_db(conn)
    total_row = conn.execute(
        "SELECT COUNT(DISTINCT file_id) AS n FROM channel_inventory WHERE analysis_id = ?",
        (analysis_id,),
    ).fetchone()
    total_files = int(total_row["n"] or 0)
    if total_files <= 0:
        return []
    rows = conn.execute(
        """
        SELECT canonical_name, MIN(channel_name) AS channel_name, COUNT(DISTINCT file_id) AS file_count
        FROM channel_inventory
        WHERE analysis_id = ?
        GROUP BY canonical_name
        ORDER BY file_count DESC, canonical_name ASC
        """,
        (analysis_id,),
    ).fetchall()
    return [
        {
            "channel": row["canonical_name"],
            "source_name": row["channel_name"],
            "file_count": int(row["file_count"] or 0),
            "total_files": total_files,
        }
        for row in rows
    ]


def replace_validated_channel_structure(
    conn: sqlite3.Connection,
    *,
    analysis_id: str,
    normalize_names: bool,
    selected_channels: list[str],
    source_summary: dict[str, Any],
) -> dict[str, Any]:
    init_db(conn)
    ts = now_iso()
    channels = list(dict.fromkeys(str(channel).strip() for channel in selected_channels if str(channel).strip()))
    conn.execute(
        """
        INSERT INTO channel_validated_structures(
          analysis_id, normalize_names, selected_channels_json,
          source_summary_json, status, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, 'active', ?, ?)
        ON CONFLICT(analysis_id) DO UPDATE SET
          normalize_names = excluded.normalize_names,
          selected_channels_json = excluded.selected_channels_json,
          source_summary_json = excluded.source_summary_json,
          status = excluded.status,
          updated_at = excluded.updated_at
        """,
        (
            analysis_id,
            1 if normalize_names else 0,
            json.dumps(channels, ensure_ascii=False),
            json.dumps(source_summary, ensure_ascii=False),
            ts,
            ts,
        ),
    )
    return {
        "analysis_id": analysis_id,
        "normalize_names": normalize_names,
        "selected_channels": channels,
        "source_summary": source_summary,
        "status": "active",
        "created_at": ts,
        "updated_at": ts,
    }


def get_validated_channel_structure(conn: sqlite3.Connection, analysis_id: str) -> dict[str, Any] | None:
    init_db(conn)
    row = conn.execute(
        "SELECT * FROM channel_validated_structures WHERE analysis_id = ?",
        (analysis_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "analysis_id": row["analysis_id"],
        "normalize_names": bool(row["normalize_names"]),
        "selected_channels": _json_loads(row["selected_channels_json"], []),
        "source_summary": _json_loads(row["source_summary_json"], {}),
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def replace_channel_anomalies(
    conn: sqlite3.Connection,
    *,
    analysis_id: str,
    rows: Iterable[dict[str, Any]],
) -> None:
    init_db(conn)
    conn.execute("DELETE FROM channel_anomalies WHERE analysis_id = ?", (analysis_id,))
    ts = now_iso()
    conn.executemany(
        """
        INSERT INTO channel_anomalies(
          analysis_id, file_id, channel, details, metadata_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                analysis_id,
                row["file_id"],
                row["channel"],
                row["details"],
                json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                ts,
            )
            for row in rows
        ],
    )


def list_channel_anomalies(
    conn: sqlite3.Connection,
    analysis_id: str,
    *,
    file_id: str | None = None,
    limit: int = 50000,
) -> list[dict[str, Any]]:
    init_db(conn)
    where = ["a.analysis_id = ?"]
    params: list[Any] = [analysis_id]
    if file_id:
        where.append("a.file_id = ?")
        params.append(file_id)
    params.append(max(1, min(int(limit), 200000)))
    rows = conn.execute(
        f"""
        SELECT a.*, f.source_dxd_name
        FROM channel_anomalies a
        JOIN analysis_files f ON f.analysis_id = a.analysis_id AND f.file_id = a.file_id
        WHERE {' AND '.join(where)}
        ORDER BY f.source_dxd_name ASC, a.channel ASC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [
        {
            "analysis_id": row["analysis_id"],
            "file_id": row["file_id"],
            "source_dxd_name": row["source_dxd_name"],
            "channel": row["channel"],
            "details": row["details"],
            "metadata": _json_loads(row["metadata_json"], {}),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def list_channel_anomaly_files(conn: sqlite3.Connection, analysis_id: str) -> list[dict[str, Any]]:
    init_db(conn)
    rows = conn.execute(
        """
        SELECT a.file_id, f.source_dxd_name, COUNT(*) AS anomaly_count
        FROM channel_anomalies a
        JOIN analysis_files f ON f.analysis_id = a.analysis_id AND f.file_id = a.file_id
        WHERE a.analysis_id = ?
        GROUP BY a.file_id, f.source_dxd_name
        ORDER BY f.source_dxd_name ASC
        """,
        (analysis_id,),
    ).fetchall()
    return [
        {
            "file_id": row["file_id"],
            "source_dxd_name": row["source_dxd_name"],
            "anomaly_count": int(row["anomaly_count"] or 0),
            "status": "anomaly",
        }
        for row in rows
    ]
