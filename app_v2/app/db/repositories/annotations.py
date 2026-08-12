from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from app_v2.app.db.connection import init_db, now_iso


DEFAULT_SET_NAME = "Annotations manuelles"


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    return json.loads(value)


def row_to_annotation_set(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "annotation_set_id": row["annotation_set_id"],
        "analysis_id": row["analysis_id"],
        "name": row["name"],
        "description": row["description"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def row_to_annotation(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "annotation_id": row["annotation_id"],
        "analysis_id": row["analysis_id"],
        "file_id": row["file_id"],
        "source_dxd_name": row["source_dxd_name"],
        "resampled_json_name": row["resampled_json_name"],
        "recorded_at": row["recorded_at"],
        "annotation_set_id": row["annotation_set_id"],
        "annotation_set_name": row["annotation_set_name"],
        "start_time_sec": row["start_time_sec"],
        "end_time_sec": row["end_time_sec"],
        "current_version_id": row["current_version_id"],
        "version_number": row["version_number"],
        "label": row["label"],
        "confidence": row["confidence"],
        "comment": row["comment"],
        "metadata": _json_loads(row["metadata_json"], {}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "version_created_at": row["version_created_at"],
        "duration_sec": float(row["end_time_sec"]) - float(row["start_time_sec"]),
    }


def row_to_annotation_label(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "label_id": row["label_id"],
        "analysis_id": row["analysis_id"],
        "name": row["name"],
        "description": row["description"],
        "color": row["color"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def ensure_annotation_labels_from_annotations(conn: sqlite3.Connection, analysis_id: str) -> None:
    init_db(conn)
    rows = conn.execute(
        """
        SELECT DISTINCT v.label
        FROM annotations a
        JOIN annotation_versions v ON v.annotation_version_id = a.current_version_id
        WHERE a.analysis_id = ? AND v.label IS NOT NULL AND TRIM(v.label) != ''
        ORDER BY v.label ASC
        """,
        (analysis_id,),
    ).fetchall()
    ts = now_iso()
    for row in rows:
        conn.execute(
            """
            INSERT OR IGNORE INTO annotation_labels(
              label_id, analysis_id, name, description, color, created_at, updated_at
            )
            VALUES (?, ?, ?, NULL, NULL, ?, ?)
            """,
            (f"label_{uuid.uuid4().hex}", analysis_id, row["label"], ts, ts),
        )
    conn.commit()


def ensure_default_annotation_set(conn: sqlite3.Connection, analysis_id: str) -> dict[str, Any]:
    init_db(conn)
    existing = conn.execute(
        """
        SELECT * FROM annotation_sets
        WHERE analysis_id = ? AND name = ?
        """,
        (analysis_id, DEFAULT_SET_NAME),
    ).fetchone()
    if existing:
        return row_to_annotation_set(existing)
    ts = now_iso()
    annotation_set_id = f"aset_{uuid.uuid4().hex}"
    conn.execute(
        """
        INSERT INTO annotation_sets(
          annotation_set_id, analysis_id, name, description, status, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, 'active', ?, ?)
        """,
        (annotation_set_id, analysis_id, DEFAULT_SET_NAME, "Annotations creees depuis l'UI", ts, ts),
    )
    conn.commit()
    return get_annotation_set(conn, analysis_id, annotation_set_id)  # type: ignore[return-value]


def get_annotation_set(
    conn: sqlite3.Connection,
    analysis_id: str,
    annotation_set_id: str,
) -> dict[str, Any] | None:
    init_db(conn)
    row = conn.execute(
        """
        SELECT * FROM annotation_sets
        WHERE analysis_id = ? AND annotation_set_id = ?
        """,
        (analysis_id, annotation_set_id),
    ).fetchone()
    return row_to_annotation_set(row) if row else None


def list_annotation_sets(conn: sqlite3.Connection, analysis_id: str) -> list[dict[str, Any]]:
    init_db(conn)
    rows = conn.execute(
        """
        SELECT * FROM annotation_sets
        WHERE analysis_id = ?
        ORDER BY created_at ASC
        """,
        (analysis_id,),
    ).fetchall()
    if not rows:
        return [ensure_default_annotation_set(conn, analysis_id)]
    return [row_to_annotation_set(row) for row in rows]


def create_annotation_set(
    conn: sqlite3.Connection,
    *,
    analysis_id: str,
    name: str,
    description: str | None = None,
) -> dict[str, Any]:
    init_db(conn)
    ts = now_iso()
    annotation_set_id = f"aset_{uuid.uuid4().hex}"
    conn.execute(
        """
        INSERT INTO annotation_sets(
          annotation_set_id, analysis_id, name, description, status, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, 'active', ?, ?)
        """,
        (annotation_set_id, analysis_id, name, description, ts, ts),
    )
    conn.commit()
    created = get_annotation_set(conn, analysis_id, annotation_set_id)
    if created is None:
        raise RuntimeError("Annotation set creation failed")
    return created


def list_managed_annotation_labels(conn: sqlite3.Connection, analysis_id: str) -> list[dict[str, Any]]:
    init_db(conn)
    ensure_annotation_labels_from_annotations(conn, analysis_id)
    rows = conn.execute(
        """
        SELECT * FROM annotation_labels
        WHERE analysis_id = ?
        ORDER BY name ASC
        """,
        (analysis_id,),
    ).fetchall()
    return [row_to_annotation_label(row) for row in rows]


def get_managed_annotation_label(
    conn: sqlite3.Connection,
    analysis_id: str,
    label_id: str,
) -> dict[str, Any] | None:
    init_db(conn)
    row = conn.execute(
        """
        SELECT * FROM annotation_labels
        WHERE analysis_id = ? AND label_id = ?
        """,
        (analysis_id, label_id),
    ).fetchone()
    return row_to_annotation_label(row) if row else None


def get_managed_annotation_label_by_name(
    conn: sqlite3.Connection,
    analysis_id: str,
    name: str,
) -> dict[str, Any] | None:
    init_db(conn)
    row = conn.execute(
        """
        SELECT * FROM annotation_labels
        WHERE analysis_id = ? AND name = ?
        """,
        (analysis_id, name),
    ).fetchone()
    return row_to_annotation_label(row) if row else None


def create_managed_annotation_label(
    conn: sqlite3.Connection,
    *,
    analysis_id: str,
    name: str,
    description: str | None = None,
    color: str | None = None,
) -> dict[str, Any]:
    init_db(conn)
    ts = now_iso()
    label_id = f"label_{uuid.uuid4().hex}"
    conn.execute(
        """
        INSERT INTO annotation_labels(
          label_id, analysis_id, name, description, color, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (label_id, analysis_id, name, description, color, ts, ts),
    )
    conn.commit()
    created = get_managed_annotation_label(conn, analysis_id, label_id)
    if created is None:
        raise RuntimeError("Annotation label creation failed")
    return created


def update_managed_annotation_label(
    conn: sqlite3.Connection,
    *,
    analysis_id: str,
    label_id: str,
    name: str,
    description: str | None = None,
    color: str | None = None,
    rename_existing_annotations: bool = True,
) -> dict[str, Any] | None:
    init_db(conn)
    existing = get_managed_annotation_label(conn, analysis_id, label_id)
    if existing is None:
        return None
    ts = now_iso()
    conn.execute(
        """
        UPDATE annotation_labels
        SET name = ?, description = ?, color = ?, updated_at = ?
        WHERE analysis_id = ? AND label_id = ?
        """,
        (name, description, color, ts, analysis_id, label_id),
    )
    conn.commit()
    if rename_existing_annotations and existing["name"] != name:
        rename_annotation_label(conn, analysis_id, existing["name"], name, sync_managed_label=False)
    return get_managed_annotation_label(conn, analysis_id, label_id)


def delete_managed_annotation_label(
    conn: sqlite3.Connection,
    analysis_id: str,
    label_id: str,
    *,
    delete_annotations: bool = False,
) -> tuple[bool, int]:
    init_db(conn)
    existing = get_managed_annotation_label(conn, analysis_id, label_id)
    if existing is None:
        return False, 0
    usage_count = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM annotations a
        JOIN annotation_versions v ON v.annotation_version_id = a.current_version_id
        WHERE a.analysis_id = ? AND v.label = ?
        """,
        (analysis_id, existing["name"]),
    ).fetchone()["count"]
    if usage_count and not delete_annotations:
        return False, int(usage_count)
    if usage_count and delete_annotations:
        delete_annotations_by_label(conn, analysis_id, existing["name"])
    conn.execute(
        """
        DELETE FROM annotation_labels
        WHERE analysis_id = ? AND label_id = ?
        """,
        (analysis_id, label_id),
    )
    conn.commit()
    return True, int(usage_count)


def _annotation_select_sql() -> str:
    return """
      SELECT
        a.annotation_id,
        a.analysis_id,
        a.file_id,
        f.source_dxd_name,
        f.resampled_json_name,
        COALESCE(f.recorded_at, json_extract(f.metadata_json, '$.modified_at')) AS recorded_at,
        a.annotation_set_id,
        s.name AS annotation_set_name,
        a.start_time_sec,
        a.end_time_sec,
        a.current_version_id,
        v.version_number,
        v.label,
        v.confidence,
        v.comment,
        v.metadata_json,
        a.created_at,
        a.updated_at,
        v.created_at AS version_created_at
      FROM annotations a
      JOIN annotation_sets s ON s.annotation_set_id = a.annotation_set_id
      JOIN analysis_files f ON f.file_id = a.file_id
      JOIN annotation_versions v ON v.annotation_version_id = a.current_version_id
    """


def list_annotations(
    conn: sqlite3.Connection,
    analysis_id: str,
    *,
    file_id: str | None = None,
    label: str | None = None,
) -> list[dict[str, Any]]:
    init_db(conn)
    filters = ["a.analysis_id = ?"]
    params: list[Any] = [analysis_id]
    if file_id:
        filters.append("a.file_id = ?")
        params.append(file_id)
    if label:
        filters.append("v.label = ?")
        params.append(label)
    rows = conn.execute(
        f"""
        {_annotation_select_sql()}
        WHERE {" AND ".join(filters)}
        ORDER BY f.source_dxd_name ASC, a.start_time_sec ASC
        """,
        params,
    ).fetchall()
    return [row_to_annotation(row) for row in rows]


def get_annotation(
    conn: sqlite3.Connection,
    analysis_id: str,
    annotation_id: str,
) -> dict[str, Any] | None:
    init_db(conn)
    row = conn.execute(
        f"""
        {_annotation_select_sql()}
        WHERE a.analysis_id = ? AND a.annotation_id = ?
        """,
        (analysis_id, annotation_id),
    ).fetchone()
    return row_to_annotation(row) if row else None


def create_annotation(
    conn: sqlite3.Connection,
    *,
    analysis_id: str,
    file_id: str,
    start_time_sec: float,
    end_time_sec: float,
    label: str,
    confidence: float | None = None,
    comment: str | None = None,
    annotation_set_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    init_db(conn)
    if annotation_set_id is None:
        annotation_set_id = ensure_default_annotation_set(conn, analysis_id)["annotation_set_id"]
    ts = now_iso()
    annotation_id = f"ann_{uuid.uuid4().hex}"
    version_id = f"annv_{uuid.uuid4().hex}"
    conn.execute(
        """
        INSERT INTO annotations(
          annotation_id, analysis_id, file_id, annotation_set_id, start_time_sec,
          end_time_sec, current_version_id, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            annotation_id,
            analysis_id,
            file_id,
            annotation_set_id,
            start_time_sec,
            end_time_sec,
            version_id,
            ts,
            ts,
        ),
    )
    conn.execute(
        """
        INSERT INTO annotation_versions(
          annotation_version_id, annotation_id, version_number, label, confidence,
          comment, metadata_json, created_at
        )
        VALUES (?, ?, 1, ?, ?, ?, ?, ?)
        """,
        (version_id, annotation_id, label, confidence, comment, json.dumps(metadata or {}, ensure_ascii=False), ts),
    )
    conn.commit()
    created = get_annotation(conn, analysis_id, annotation_id)
    if created is None:
        raise RuntimeError("Annotation creation failed")
    return created


def update_annotation(
    conn: sqlite3.Connection,
    *,
    analysis_id: str,
    annotation_id: str,
    start_time_sec: float,
    end_time_sec: float,
    label: str,
    confidence: float | None = None,
    comment: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    init_db(conn)
    existing = get_annotation(conn, analysis_id, annotation_id)
    if existing is None:
        return None
    row = conn.execute(
        """
        SELECT COALESCE(MAX(version_number), 0) AS max_version
        FROM annotation_versions
        WHERE annotation_id = ?
        """,
        (annotation_id,),
    ).fetchone()
    version_number = int(row["max_version"] or 0) + 1
    version_id = f"annv_{uuid.uuid4().hex}"
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO annotation_versions(
          annotation_version_id, annotation_id, version_number, label, confidence,
          comment, metadata_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            version_id,
            annotation_id,
            version_number,
            label,
            confidence,
            comment,
            json.dumps(metadata or {}, ensure_ascii=False),
            ts,
        ),
    )
    conn.execute(
        """
        UPDATE annotations
        SET start_time_sec = ?, end_time_sec = ?, current_version_id = ?, updated_at = ?
        WHERE analysis_id = ? AND annotation_id = ?
        """,
        (start_time_sec, end_time_sec, version_id, ts, analysis_id, annotation_id),
    )
    conn.commit()
    return get_annotation(conn, analysis_id, annotation_id)


def delete_annotation(conn: sqlite3.Connection, analysis_id: str, annotation_id: str) -> bool:
    init_db(conn)
    cursor = conn.execute(
        """
        DELETE FROM annotations
        WHERE analysis_id = ? AND annotation_id = ?
        """,
        (analysis_id, annotation_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def list_annotation_versions(
    conn: sqlite3.Connection,
    analysis_id: str,
    annotation_id: str,
) -> list[dict[str, Any]] | None:
    init_db(conn)
    if get_annotation(conn, analysis_id, annotation_id) is None:
        return None
    rows = conn.execute(
        """
        SELECT * FROM annotation_versions
        WHERE annotation_id = ?
        ORDER BY version_number ASC
        """,
        (annotation_id,),
    ).fetchall()
    return [
        {
            "annotation_version_id": row["annotation_version_id"],
            "annotation_id": row["annotation_id"],
            "version_number": row["version_number"],
            "label": row["label"],
            "confidence": row["confidence"],
            "comment": row["comment"],
            "metadata": _json_loads(row["metadata_json"], {}),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def list_annotation_labels(conn: sqlite3.Connection, analysis_id: str) -> list[str]:
    init_db(conn)
    ensure_annotation_labels_from_annotations(conn, analysis_id)
    rows = conn.execute(
        """
        SELECT name
        FROM annotation_labels
        WHERE analysis_id = ?
        ORDER BY name ASC
        """,
        (analysis_id,),
    ).fetchall()
    return [row["name"] for row in rows]


def summarize_annotation_labels(conn: sqlite3.Connection, analysis_id: str) -> list[dict[str, Any]]:
    init_db(conn)
    rows = conn.execute(
        """
        SELECT
          v.label,
          COUNT(*) AS annotation_count,
          COUNT(DISTINCT a.file_id) AS file_count,
          SUM(a.end_time_sec - a.start_time_sec) AS total_duration_sec,
          MAX(a.updated_at) AS last_used_at
        FROM annotations a
        JOIN annotation_versions v ON v.annotation_version_id = a.current_version_id
        WHERE a.analysis_id = ?
        GROUP BY v.label
        ORDER BY annotation_count DESC, v.label ASC
        """,
        (analysis_id,),
    ).fetchall()
    return [
        {
            "label": row["label"],
            "annotation_count": row["annotation_count"],
            "file_count": row["file_count"],
            "total_duration_sec": row["total_duration_sec"] or 0,
            "last_used_at": row["last_used_at"],
        }
        for row in rows
    ]


def rename_annotation_label(
    conn: sqlite3.Connection,
    analysis_id: str,
    old_label: str,
    new_label: str,
    *,
    sync_managed_label: bool = True,
) -> int:
    init_db(conn)
    if sync_managed_label:
        ensure_annotation_labels_from_annotations(conn, analysis_id)
        existing_label = get_managed_annotation_label_by_name(conn, analysis_id, old_label)
        if existing_label is not None:
            conn.execute(
                """
                UPDATE annotation_labels
                SET name = ?, updated_at = ?
                WHERE analysis_id = ? AND label_id = ?
                """,
                (new_label, now_iso(), analysis_id, existing_label["label_id"]),
            )
            conn.commit()
    rows = conn.execute(
        f"""
        {_annotation_select_sql()}
        WHERE a.analysis_id = ? AND v.label = ?
        """,
        (analysis_id, old_label),
    ).fetchall()
    count = 0
    for row in rows:
        annotation = row_to_annotation(row)
        update_annotation(
            conn,
            analysis_id=analysis_id,
            annotation_id=annotation["annotation_id"],
            start_time_sec=annotation["start_time_sec"],
            end_time_sec=annotation["end_time_sec"],
            label=new_label,
            confidence=annotation["confidence"],
            comment=annotation["comment"],
            metadata={
                **annotation["metadata"],
                "rename_from": old_label,
                "source": "label_catalog",
            },
        )
        count += 1
    return count


def delete_annotations_by_label(conn: sqlite3.Connection, analysis_id: str, label: str) -> int:
    init_db(conn)
    rows = conn.execute(
        """
        SELECT a.annotation_id
        FROM annotations a
        JOIN annotation_versions v ON v.annotation_version_id = a.current_version_id
        WHERE a.analysis_id = ? AND v.label = ?
        """,
        (analysis_id, label),
    ).fetchall()
    ids = [row["annotation_id"] for row in rows]
    for annotation_id in ids:
        conn.execute(
            """
            DELETE FROM annotations
            WHERE analysis_id = ? AND annotation_id = ?
            """,
            (analysis_id, annotation_id),
        )
    conn.execute(
        """
        DELETE FROM annotation_labels
        WHERE analysis_id = ? AND name = ?
        """,
        (analysis_id, label),
    )
    conn.commit()
    return len(ids)
