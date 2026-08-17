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


def row_to_prompt(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "prompt_id": row["prompt_id"],
        "analysis_id": row["analysis_id"],
        "name": row["name"],
        "description": row["description"],
        "system_prompt": row["system_prompt"],
        "user_prompt": row["user_prompt"],
        "required_channels": _json_loads(row["required_channels_json"], []),
        "output_schema": _json_loads(row["output_schema_json"], {}),
        "version_number": row["version_number"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def row_to_run(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "run_id": row["run_id"],
        "analysis_id": row["analysis_id"],
        "prompt_id": row["prompt_id"],
        "name": row["name"],
        "provider": row["provider"],
        "model": row["model"],
        "status": row["status"],
        "request": _json_loads(row["request_json"], {}),
        "context": _json_loads(row["context_json"], {}),
        "response_markdown": row["response_markdown"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_prompts(conn: sqlite3.Connection, analysis_id: str) -> list[dict[str, Any]]:
    init_db(conn)
    rows = conn.execute(
        """
        SELECT * FROM dynamic_analysis_prompts
        WHERE analysis_id = ?
        ORDER BY updated_at DESC
        """,
        (analysis_id,),
    ).fetchall()
    return [row_to_prompt(row) for row in rows]


def get_prompt(conn: sqlite3.Connection, analysis_id: str, prompt_id: str) -> dict[str, Any] | None:
    init_db(conn)
    row = conn.execute(
        """
        SELECT * FROM dynamic_analysis_prompts
        WHERE analysis_id = ? AND prompt_id = ?
        """,
        (analysis_id, prompt_id),
    ).fetchone()
    return row_to_prompt(row) if row else None


def create_prompt(
    conn: sqlite3.Connection,
    *,
    analysis_id: str,
    name: str,
    description: str | None = None,
    system_prompt: str,
    user_prompt: str,
    required_channels: list[str] | None = None,
    output_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    init_db(conn)
    ts = now_iso()
    prompt_id = f"dynprompt_{uuid.uuid4().hex}"
    conn.execute(
        """
        INSERT INTO dynamic_analysis_prompts(
          prompt_id, analysis_id, name, description, system_prompt, user_prompt,
          required_channels_json, output_schema_json, version_number, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        """,
        (
            prompt_id,
            analysis_id,
            name,
            description,
            system_prompt,
            user_prompt,
            json.dumps(required_channels or [], ensure_ascii=False),
            json.dumps(output_schema or {}, ensure_ascii=False),
            ts,
            ts,
        ),
    )
    conn.commit()
    created = get_prompt(conn, analysis_id, prompt_id)
    if created is None:
        raise RuntimeError("Dynamic analysis prompt creation failed")
    return created


def list_runs(conn: sqlite3.Connection, analysis_id: str) -> list[dict[str, Any]]:
    init_db(conn)
    rows = conn.execute(
        """
        SELECT * FROM dynamic_analysis_runs
        WHERE analysis_id = ?
        ORDER BY created_at DESC
        """,
        (analysis_id,),
    ).fetchall()
    return [row_to_run(row) for row in rows]


def get_run(conn: sqlite3.Connection, analysis_id: str, run_id: str) -> dict[str, Any] | None:
    init_db(conn)
    row = conn.execute(
        """
        SELECT * FROM dynamic_analysis_runs
        WHERE analysis_id = ? AND run_id = ?
        """,
        (analysis_id, run_id),
    ).fetchone()
    return row_to_run(row) if row else None


def create_run(
    conn: sqlite3.Connection,
    *,
    analysis_id: str,
    prompt_id: str | None,
    name: str,
    provider: str,
    model: str | None,
    request: dict[str, Any],
    context: dict[str, Any],
    response_markdown: str,
    status: str = "dry_run",
) -> dict[str, Any]:
    init_db(conn)
    ts = now_iso()
    run_id = f"dynrun_{uuid.uuid4().hex}"
    conn.execute(
        """
        INSERT INTO dynamic_analysis_runs(
          run_id, analysis_id, prompt_id, name, provider, model, status,
          request_json, context_json, response_markdown, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            analysis_id,
            prompt_id,
            name,
            provider,
            model,
            status,
            json.dumps(request, ensure_ascii=False),
            json.dumps(context, ensure_ascii=False),
            response_markdown,
            ts,
            ts,
        ),
    )
    conn.execute(
        """
        INSERT INTO dynamic_analysis_versions(
          version_id, run_id, version_number, response_markdown, confidence,
          note, validated_for_dataset, created_at
        )
        VALUES (?, ?, 1, ?, NULL, 'Réponse initiale', 0, ?)
        """,
        (f"dynver_{uuid.uuid4().hex}", run_id, response_markdown, ts),
    )
    conn.commit()
    created = get_run(conn, analysis_id, run_id)
    if created is None:
        raise RuntimeError("Dynamic analysis run creation failed")
    return created


def delete_run(conn: sqlite3.Connection, analysis_id: str, run_id: str) -> bool:
    init_db(conn)
    cursor = conn.execute(
        """
        DELETE FROM dynamic_analysis_runs
        WHERE analysis_id = ? AND run_id = ?
        """,
        (analysis_id, run_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def list_run_versions(conn: sqlite3.Connection, analysis_id: str, run_id: str) -> list[dict[str, Any]] | None:
    init_db(conn)
    if get_run(conn, analysis_id, run_id) is None:
        return None
    rows = conn.execute(
        """
        SELECT * FROM dynamic_analysis_versions
        WHERE run_id = ?
        ORDER BY version_number ASC
        """,
        (run_id,),
    ).fetchall()
    return [
        {
            "version_id": row["version_id"],
            "run_id": row["run_id"],
            "version_number": row["version_number"],
            "response_markdown": row["response_markdown"],
            "confidence": row["confidence"],
            "note": row["note"],
            "validated_for_dataset": bool(row["validated_for_dataset"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def create_run_version(
    conn: sqlite3.Connection,
    *,
    analysis_id: str,
    run_id: str,
    response_markdown: str,
    confidence: str | None = None,
    note: str | None = None,
    validated_for_dataset: bool = False,
) -> dict[str, Any] | None:
    init_db(conn)
    if get_run(conn, analysis_id, run_id) is None:
        return None
    row = conn.execute(
        """
        SELECT COALESCE(MAX(version_number), 0) AS max_version
        FROM dynamic_analysis_versions
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    version_number = int(row["max_version"] or 0) + 1
    version_id = f"dynver_{uuid.uuid4().hex}"
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO dynamic_analysis_versions(
          version_id, run_id, version_number, response_markdown, confidence,
          note, validated_for_dataset, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            version_id,
            run_id,
            version_number,
            response_markdown,
            confidence,
            note,
            1 if validated_for_dataset else 0,
            ts,
        ),
    )
    conn.execute(
        """
        UPDATE dynamic_analysis_runs
        SET response_markdown = ?, updated_at = ?
        WHERE analysis_id = ? AND run_id = ?
        """,
        (response_markdown, ts, analysis_id, run_id),
    )
    conn.commit()
    versions = list_run_versions(conn, analysis_id, run_id)
    if not versions:
        return None
    return versions[-1]


def row_to_dynamic_analysis(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "dynamic_analysis_id": row["dynamic_analysis_id"],
        "analysis_id": row["analysis_id"],
        "name": row["name"],
        "protocol_name": row["protocol_name"],
        "description": row["description"],
        "system_prompt": row["system_prompt"],
        "selected_channels": _json_loads(row["selected_channels_json"], []),
        "selected_labels": _json_loads(row["selected_labels_json"], []),
        "indicators": _json_loads(row["indicators_json"], []),
        "label_category": row["label_category"],
        "output_schema": _json_loads(row["output_schema_json"], {}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_dynamic_analyses(conn: sqlite3.Connection, analysis_id: str) -> list[dict[str, Any]]:
    init_db(conn)
    rows = conn.execute(
        """
        SELECT * FROM dynamic_analyses
        WHERE analysis_id = ?
        ORDER BY updated_at DESC
        """,
        (analysis_id,),
    ).fetchall()
    return [row_to_dynamic_analysis(row) for row in rows]


def get_dynamic_analysis(
    conn: sqlite3.Connection,
    analysis_id: str,
    dynamic_analysis_id: str,
) -> dict[str, Any] | None:
    init_db(conn)
    row = conn.execute(
        """
        SELECT * FROM dynamic_analyses
        WHERE analysis_id = ? AND dynamic_analysis_id = ?
        """,
        (analysis_id, dynamic_analysis_id),
    ).fetchone()
    return row_to_dynamic_analysis(row) if row else None


def get_dynamic_analysis_by_name(
    conn: sqlite3.Connection,
    analysis_id: str,
    name: str,
) -> dict[str, Any] | None:
    init_db(conn)
    row = conn.execute(
        """
        SELECT * FROM dynamic_analyses
        WHERE analysis_id = ? AND lower(trim(name)) = lower(trim(?))
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (analysis_id, name),
    ).fetchone()
    return row_to_dynamic_analysis(row) if row else None


def create_dynamic_analysis(
    conn: sqlite3.Connection,
    *,
    analysis_id: str,
    name: str,
    protocol_name: str,
    description: str | None,
    system_prompt: str,
    selected_channels: list[str],
    selected_labels: list[str] | None = None,
    indicators: list[dict[str, Any]] | list[str],
    label_category: str,
    output_schema: dict[str, Any],
) -> dict[str, Any]:
    init_db(conn)
    ts = now_iso()
    dynamic_analysis_id = f"dynanalysis_{uuid.uuid4().hex}"
    conn.execute(
        """
        INSERT INTO dynamic_analyses(
          dynamic_analysis_id, analysis_id, name, protocol_name, description, system_prompt,
          selected_channels_json, selected_labels_json, indicators_json, label_category,
          output_schema_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            dynamic_analysis_id,
            analysis_id,
            name,
            protocol_name,
            description,
            system_prompt,
            json.dumps(selected_channels, ensure_ascii=False),
            json.dumps(selected_labels or [], ensure_ascii=False),
            json.dumps(indicators, ensure_ascii=False),
            label_category,
            json.dumps(output_schema, ensure_ascii=False),
            ts,
            ts,
        ),
    )
    conn.commit()
    created = get_dynamic_analysis(conn, analysis_id, dynamic_analysis_id)
    if created is None:
        raise RuntimeError("Dynamic analysis creation failed")
    return created


def update_dynamic_analysis(
    conn: sqlite3.Connection,
    *,
    analysis_id: str,
    dynamic_analysis_id: str,
    name: str,
    protocol_name: str,
    description: str | None,
    system_prompt: str,
    selected_channels: list[str],
    selected_labels: list[str] | None = None,
    indicators: list[dict[str, Any]] | list[str],
    label_category: str,
    output_schema: dict[str, Any],
) -> dict[str, Any] | None:
    init_db(conn)
    ts = now_iso()
    cursor = conn.execute(
        """
        UPDATE dynamic_analyses
        SET name = ?, protocol_name = ?, description = ?, system_prompt = ?, selected_channels_json = ?,
            selected_labels_json = ?, indicators_json = ?, label_category = ?, output_schema_json = ?,
            updated_at = ?
        WHERE analysis_id = ? AND dynamic_analysis_id = ?
        """,
        (
            name,
            protocol_name,
            description,
            system_prompt,
            json.dumps(selected_channels, ensure_ascii=False),
            json.dumps(selected_labels or [], ensure_ascii=False),
            json.dumps(indicators, ensure_ascii=False),
            label_category,
            json.dumps(output_schema, ensure_ascii=False),
            ts,
            analysis_id,
            dynamic_analysis_id,
        ),
    )
    conn.commit()
    if cursor.rowcount == 0:
        return None
    return get_dynamic_analysis(conn, analysis_id, dynamic_analysis_id)


def delete_dynamic_analysis(
    conn: sqlite3.Connection,
    analysis_id: str,
    dynamic_analysis_id: str,
) -> bool:
    init_db(conn)
    cursor = conn.execute(
        """
        DELETE FROM dynamic_analyses
        WHERE analysis_id = ? AND dynamic_analysis_id = ?
        """,
        (analysis_id, dynamic_analysis_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def row_to_prediction(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "prediction_id": row["prediction_id"],
        "dynamic_analysis_id": row["dynamic_analysis_id"],
        "annotation_id": row["annotation_id"],
        "provider": row["provider"],
        "model": row["model"],
        "status": row["status"],
        "input_context": _json_loads(row["input_context_json"], {}),
        "input_artifact_path": row["input_artifact_path"],
        "response_json": _json_loads(row["response_json"], {}),
        "response_markdown": row["response_markdown"],
        "analysis_text": row["analysis_text"],
        "analysis_note": row["analysis_note"],
        "summary_text": row["summary_text"],
        "confidence": row["confidence"],
        "error_message": row["error_message"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_predictions(
    conn: sqlite3.Connection,
    dynamic_analysis_id: str,
) -> list[dict[str, Any]]:
    init_db(conn)
    rows = conn.execute(
        """
        SELECT p.*
        FROM dynamic_annotation_predictions p
        JOIN annotations a ON a.annotation_id = p.annotation_id
        WHERE p.dynamic_analysis_id = ?
        ORDER BY p.created_at DESC
        """,
        (dynamic_analysis_id,),
    ).fetchall()
    return [row_to_prediction(row) for row in rows]


def get_prediction(
    conn: sqlite3.Connection,
    prediction_id: str,
) -> dict[str, Any] | None:
    init_db(conn)
    row = conn.execute(
        """
        SELECT * FROM dynamic_annotation_predictions
        WHERE prediction_id = ?
        """,
        (prediction_id,),
    ).fetchone()
    return row_to_prediction(row) if row else None


def create_or_replace_prediction(
    conn: sqlite3.Connection,
    *,
    dynamic_analysis_id: str,
    annotation_id: str,
    provider: str,
    model: str | None,
    status: str,
    input_context: dict[str, Any],
    input_artifact_path: str | None,
    response_json: dict[str, Any],
    response_markdown: str,
    analysis_text: str = "",
    analysis_note: str = "",
    summary_text: str = "",
    confidence: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    init_db(conn)
    ts = now_iso()
    existing = conn.execute(
        """
        SELECT prediction_id FROM dynamic_annotation_predictions
        WHERE dynamic_analysis_id = ? AND annotation_id = ?
        """,
        (dynamic_analysis_id, annotation_id),
    ).fetchone()
    if existing:
        prediction_id = existing["prediction_id"]
        conn.execute(
            """
            UPDATE dynamic_annotation_predictions
            SET provider = ?, model = ?, status = ?, input_context_json = ?,
                input_artifact_path = ?, response_json = ?, response_markdown = ?,
                analysis_text = ?, analysis_note = ?, summary_text = ?,
                confidence = ?, error_message = ?, updated_at = ?
            WHERE prediction_id = ?
            """,
            (
                provider,
                model,
                status,
                json.dumps(input_context, ensure_ascii=False),
                input_artifact_path,
                json.dumps(response_json, ensure_ascii=False),
                response_markdown,
                analysis_text,
                analysis_note,
                summary_text,
                confidence,
                error_message,
                ts,
                prediction_id,
            ),
        )
    else:
        prediction_id = f"dynpred_{uuid.uuid4().hex}"
        conn.execute(
            """
            INSERT INTO dynamic_annotation_predictions(
              prediction_id, dynamic_analysis_id, annotation_id, provider, model, status,
              input_context_json, input_artifact_path, response_json, response_markdown,
              analysis_text, analysis_note, summary_text, confidence, error_message,
              created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                prediction_id,
                dynamic_analysis_id,
                annotation_id,
                provider,
                model,
                status,
                json.dumps(input_context, ensure_ascii=False),
                input_artifact_path,
                json.dumps(response_json, ensure_ascii=False),
                response_markdown,
                analysis_text,
                analysis_note,
                summary_text,
                confidence,
                error_message,
                ts,
                ts,
            ),
        )
    conn.commit()
    created = get_prediction(conn, prediction_id)
    if created is None:
        raise RuntimeError("Dynamic prediction creation failed")
    return created


def row_to_correction(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "correction_id": row["correction_id"],
        "prediction_id": row["prediction_id"],
        "corrected_response_json": _json_loads(row["corrected_response_json"], {}),
        "corrected_response_markdown": row["corrected_response_markdown"],
        "corrected_analysis_text": row["corrected_analysis_text"],
        "corrected_analysis_note": row["corrected_analysis_note"],
        "corrected_summary_text": row["corrected_summary_text"],
        "corrected_confidence": row["corrected_confidence"],
        "note": row["note"],
        "validated_for_dataset": bool(row["validated_for_dataset"]),
        "created_at": row["created_at"],
    }


def list_prediction_corrections(conn: sqlite3.Connection, prediction_id: str) -> list[dict[str, Any]]:
    init_db(conn)
    rows = conn.execute(
        """
        SELECT * FROM dynamic_prediction_corrections
        WHERE prediction_id = ?
        ORDER BY created_at ASC
        """,
        (prediction_id,),
    ).fetchall()
    return [row_to_correction(row) for row in rows]


def create_prediction_correction(
    conn: sqlite3.Connection,
    *,
    prediction_id: str,
    corrected_response_json: dict[str, Any],
    corrected_response_markdown: str,
    corrected_analysis_text: str = "",
    corrected_analysis_note: str = "",
    corrected_summary_text: str = "",
    corrected_confidence: str | None = None,
    note: str | None = None,
    validated_for_dataset: bool = False,
) -> dict[str, Any] | None:
    init_db(conn)
    if get_prediction(conn, prediction_id) is None:
        return None
    correction_id = f"dyncorr_{uuid.uuid4().hex}"
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO dynamic_prediction_corrections(
          correction_id, prediction_id, corrected_response_json, corrected_response_markdown,
          corrected_analysis_text, corrected_analysis_note, corrected_summary_text,
          corrected_confidence, note, validated_for_dataset, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            correction_id,
            prediction_id,
            json.dumps(corrected_response_json, ensure_ascii=False),
            corrected_response_markdown,
            corrected_analysis_text,
            corrected_analysis_note,
            corrected_summary_text,
            corrected_confidence,
            note,
            1 if validated_for_dataset else 0,
            ts,
        ),
    )
    conn.commit()
    corrections = list_prediction_corrections(conn, prediction_id)
    return corrections[-1] if corrections else None
