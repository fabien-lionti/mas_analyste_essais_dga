from __future__ import annotations

import sqlite3
from typing import Any

from app_v2.app.db.repositories.analyses import update_analysis_summary
from app_v2.app.db.repositories.channels import (
    get_validated_channel_structure,
    list_channel_inventory,
    recurrent_channels_from_inventory,
    replace_channel_anomalies,
    replace_validated_channel_structure,
)
from app_v2.app.db.repositories.events import add_event
from app_v2.app.db.repositories.files import list_analysis_files


def save_validated_channel_structure(
    conn: sqlite3.Connection,
    *,
    analysis_id: str,
    selected_channels: list[str],
    normalize_names: bool = True,
) -> dict[str, Any]:
    recurrent = recurrent_channels_from_inventory(conn, analysis_id)
    recurrent_channels = {row["channel"] for row in recurrent}
    selected = list(dict.fromkeys(channel.strip() for channel in selected_channels if channel.strip()))
    unknown = [channel for channel in selected if channel not in recurrent_channels]
    if unknown:
        raise ValueError(f"Canaux inconnus dans le scan: {', '.join(unknown)}")

    source_summary = {
        "recurrent_channel_count": len(recurrent),
        "selected_channel_count": len(selected),
    }
    structure = replace_validated_channel_structure(
        conn,
        analysis_id=analysis_id,
        normalize_names=normalize_names,
        selected_channels=selected,
        source_summary=source_summary,
    )
    anomalies = compute_missing_recurrent_channel_anomalies(
        conn,
        analysis_id=analysis_id,
        selected_channels=selected,
    )
    replace_channel_anomalies(conn, analysis_id=analysis_id, rows=anomalies)
    payload = {
        "validated_structure": structure,
        "anomaly_count": len(anomalies),
        "anomaly_file_count": len({row["file_id"] for row in anomalies}),
    }
    update_analysis_summary(conn, analysis_id, {"validated_channel_structure": payload})
    add_event(
        conn,
        analysis_id,
        level="info",
        event_type="channel_structure_validated",
        message="Structure canaux sauvegardee",
        payload=payload,
    )
    return payload


def compute_missing_recurrent_channel_anomalies(
    conn: sqlite3.Connection,
    *,
    analysis_id: str,
    selected_channels: list[str] | None = None,
) -> list[dict[str, Any]]:
    structure = get_validated_channel_structure(conn, analysis_id)
    channels = (
        list(dict.fromkeys(selected_channels or []))
        if selected_channels is not None
        else list(structure["selected_channels"] if structure else [])
    )
    if not channels:
        return []
    files = list_analysis_files(conn, analysis_id, limit=10000)
    inventory = list_channel_inventory(conn, analysis_id, limit=200000)
    present_by_file: dict[str, set[str]] = {}
    for row in inventory:
        present_by_file.setdefault(row["file_id"], set()).add(row["canonical_name"])

    rows = []
    for item in files:
        present = present_by_file.get(item["file_id"], set())
        for channel in channels:
            if channel in present:
                continue
            rows.append(
                {
                    "file_id": item["file_id"],
                    "channel": channel,
                    "details": "canal récurrent sélectionné absent de ce fichier",
                    "metadata": {
                        "source_dxd_name": item["source_dxd_name"],
                    },
                }
            )
    return rows
