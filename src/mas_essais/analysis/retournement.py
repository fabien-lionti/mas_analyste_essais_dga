from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import sqlite3
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mas_essais.db.sqlite import DEFAULT_DB_PATH, connect as connect_pipeline_db

DEFAULT_ANALYSIS_PROMPT = (
    "Tu es un ingénieur essais spécialisé en dynamique véhicule et stabilité au retournement.\n\n"
    "Voici les mesures déjà calculées par notre système pour ce segment d'essai :\n"
    "{segment_metrics_json}\n\n"
    "Le graphique fourni montre le segment correspondant (LTR, vx, angle de roulis en fonction du temps). "
    "Ces valeurs numériques sont des mesures fiables, ne les recalcule pas et ne les remets pas en question "
    "sauf incohérence flagrante avec l'image.\n\n"
    "À partir de ces éléments, analyse : (1) la cohérence entre le pic de LTR et le pic d'angle de roulis - "
    "sont-ils simultanés ou décalés dans le temps, et qu'est-ce que cela suggère sur la dynamique du véhicule, "
    "(2) la présence d'oscillations ou d'un comportement instable visible sur le graphique mais non résumé par "
    "les seuls maximums fournis, (3) toute anomalie visuelle (bruit, rupture brutale, asymétrie) qui mériterait "
    "une vérification humaine, (4) si le seuil franchi indiqué est cohérent avec le comportement global observé "
    "sur le segment, ou si le contexte suggère de nuancer cette lecture. Ne recalcule aucune valeur numérique "
    "fournie. Ne conclus jamais à un risque de retournement avéré sans indiquer clairement le niveau d'incertitude "
    "de ta conclusion. Termine par une synthèse en une ou deux phrases en langage clair."
)

ANALYSIS_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "coherence_ltr_roulis": {"type": "string"},
        "oscillations_non_capturees": {"type": "boolean"},
        "anomalie_detectee": {"type": "string"},
        "nuance_seuil": {"type": "string"},
        "confiance": {"type": "string", "enum": ["haute", "moyenne", "basse"]},
        "synthese": {"type": "string"},
    },
    "required": [
        "coherence_ltr_roulis",
        "oscillations_non_capturees",
        "anomalie_detectee",
        "nuance_seuil",
        "confiance",
        "synthese",
    ],
}

ANALYSES_RETOURNEMENT_COLUMNS = {
    "essai_id": "TEXT",
    "provider": "TEXT",
    "date_analyse": "TEXT",
    "ltr_max_abs": "REAL",
    "instant_ltr_max_s": "REAL",
    "vx_a_ltr_max_kmh": "REAL",
    "roll_angle_max_deg": "REAL",
    "instant_roll_max_s": "REAL",
    "roll_angle_a_ltr_max_deg": "REAL",
    "seuil_ltr_franchi": "TEXT",
    "seuil_critique_approche": "INTEGER",
    "oscillations_detectees": "INTEGER",
    "oscillations_non_capturees": "INTEGER",
    "correlation_vx_ltr": "TEXT",
    "coherence_ltr_roulis": "TEXT",
    "anomalie_detectee": "TEXT",
    "nuance_seuil": "TEXT",
    "confiance": "TEXT",
    "notes": "TEXT",
    "synthese": "TEXT",
    "segment_start_s": "REAL",
    "segment_end_s": "REAL",
    "echantillon_points_json": "TEXT",
    "version_parent_id": "INTEGER",
    "version_note": "TEXT",
    "is_user_version": "INTEGER",
    "source_segment_annotation_id": "TEXT",
    "source_segment_label": "TEXT",
    "source_segment_source": "TEXT",
}

_LOCAL_QUOTA: dict[str, dict[str, Any]] = {
    "groq": {"requests_sent": 0, "last_headers": {}, "last_status": None},
    "gemini": {"requests_sent": 0, "last_headers": {}, "last_status": None},
}


class RolloverAnalysisError(RuntimeError):
    pass


class ProviderRateLimitError(RolloverAnalysisError):
    def __init__(self, provider: str, message: str, retry_after: str | None = None):
        self.provider = provider
        self.retry_after = retry_after
        suffix = f" Retry-After: {retry_after}." if retry_after else ""
        super().__init__(f"Rate limit {provider}: {message}.{suffix}")


def analyze_curve(
    image_path: str | Path,
    provider: str = "groq",
    segment_metrics: dict[str, Any] | None = None,
    prompt: str = DEFAULT_ANALYSIS_PROMPT,
) -> dict[str, Any]:
    normalized_provider = _normalize_provider(provider)
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    if segment_metrics is None:
        raise ValueError("segment_metrics is required")
    rendered_prompt = _build_analysis_prompt(prompt, segment_metrics)
    if normalized_provider == "groq":
        result = _analyze_curve_groq(path, rendered_prompt)
    elif normalized_provider == "gemini":
        result = _analyze_curve_gemini(path, rendered_prompt)
    else:
        raise ValueError(f"Unsupported provider: {provider}")
    parsed = _parse_model_json(result["text"])
    validated = _validate_analysis_result(parsed)
    validated["provider"] = normalized_provider
    validated["model"] = result.get("model")
    validated["raw_usage"] = result.get("raw_usage")
    validated["rate_limit"] = result.get("rate_limit")
    validated["finish_reason"] = result.get("finish_reason")
    return validated


def compute_segment_metrics(
    data_ltr: Any,
    data_vx: Any,
    data_roll: Any,
    segment_start_s: float,
    segment_end_s: float,
    seuils: dict[str, Any],
    sample_points: int = 25,
) -> dict[str, Any]:
    start = float(segment_start_s)
    end = float(segment_end_s)
    if not end > start:
        raise ValueError("segment_end_s must be greater than segment_start_s")

    ltr_t, ltr_y = _series_arrays(data_ltr, ("ltr_total", "ltr", "value"))
    vx_t, vx_mps = _series_arrays(data_vx, ("vehicle.vx", "vx", "value"))
    roll_t, roll_deg = _series_arrays(data_roll, ("vehicle.roll_angle", "roll_angle", "Roll (_)", "value"))

    mask = (ltr_t >= start) & (ltr_t <= end) & _is_finite(ltr_t) & _is_finite(ltr_y)
    if not mask.any():
        raise ValueError("No LTR points available inside selected segment")

    seg_ltr_t = ltr_t[mask]
    seg_ltr_y = ltr_y[mask]
    peak_idx = int(_nanargmax_abs(seg_ltr_y))
    instant_ltr_max_s = float(seg_ltr_t[peak_idx])
    ltr_max_abs = float(abs(seg_ltr_y[peak_idx]))
    vx_a_ltr_max_kmh = _interp_or_none(instant_ltr_max_s, vx_t, vx_mps, scale=3.6)
    roll_angle_a_ltr_max_deg = _interp_or_none(instant_ltr_max_s, roll_t, roll_deg)

    roll_mask = (roll_t >= start) & (roll_t <= end) & _is_finite(roll_t) & _is_finite(roll_deg)
    if roll_mask.any():
        seg_roll_t = roll_t[roll_mask]
        seg_roll_y = roll_deg[roll_mask]
        roll_peak_idx = int(_nanargmax_abs(seg_roll_y))
        instant_roll_max_s = float(seg_roll_t[roll_peak_idx])
        roll_angle_max_deg = float(seg_roll_y[roll_peak_idx])
    else:
        instant_roll_max_s = None
        roll_angle_max_deg = None

    warning = _optional_float(seuils.get("warning")) if isinstance(seuils, dict) else None
    critical = _optional_float(seuils.get("critical")) if isinstance(seuils, dict) else None
    if critical is not None and ltr_max_abs >= critical:
        seuil_ltr_franchi = "critical"
    elif warning is not None and ltr_max_abs >= warning:
        seuil_ltr_franchi = "warning"
    else:
        seuil_ltr_franchi = "aucun"

    sample_count = max(20, min(30, int(sample_points)))
    sample_times = _regular_sample_times(start, end, sample_count)
    echantillon_points = [
        {
            "time_s": _round_or_none(t, 4),
            "ltr": _round_or_none(_interp_or_none(t, ltr_t, ltr_y), 5),
            "vx_kmh": _round_or_none(_interp_or_none(t, vx_t, vx_mps, scale=3.6), 3),
            "roll_angle_deg": _round_or_none(_interp_or_none(t, roll_t, roll_deg), 4),
        }
        for t in sample_times
    ]

    return {
        "segment_start_s": start,
        "segment_end_s": end,
        "ltr_max_abs": ltr_max_abs,
        "instant_ltr_max_s": instant_ltr_max_s,
        "vx_a_ltr_max_kmh": vx_a_ltr_max_kmh,
        "roll_angle_max_deg": roll_angle_max_deg,
        "instant_roll_max_s": instant_roll_max_s,
        "roll_angle_a_ltr_max_deg": roll_angle_a_ltr_max_deg,
        "seuil_ltr_franchi": seuil_ltr_franchi,
        "echantillon_points": echantillon_points,
    }


def crop_segment_image(
    image_source_data: dict[str, Any],
    segment_start_s: float,
    segment_end_s: float,
    output_path: str | Path | None = None,
    context_ratio: float = 0.10,
) -> Path:
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    start = float(segment_start_s)
    end = float(segment_end_s)
    if not end > start:
        raise ValueError("segment_end_s must be greater than segment_start_s")

    duration = end - start
    margin = max(0.0, duration * float(context_ratio))
    x0 = start - margin
    x1 = end + margin

    ltr_t, ltr_y = _series_arrays(image_source_data.get("ltr"), ("ltr_total", "ltr", "value"))
    vx_t, vx_mps = _series_arrays(image_source_data.get("vx"), ("vehicle.vx", "vx", "value"))
    roll_t, roll_deg = _series_arrays(image_source_data.get("roll"), ("vehicle.roll_angle", "roll_angle", "Roll (_)", "value"))

    if output_path is None:
        import tempfile

        tmp = tempfile.NamedTemporaryFile(prefix="rollover_segment_", suffix=".jpg", delete=False)
        tmp.close()
        out_path = Path(tmp.name)
    else:
        out_path = Path(output_path)

    width = 10.0 if duration >= 5.0 else 11.5
    height = 6.6 if duration >= 5.0 else 7.4
    fig, (ax_ltr, ax_roll) = plt.subplots(
        2,
        1,
        figsize=(width, height),
        dpi=110,
        sharex=True,
        gridspec_kw={"height_ratios": [2, 1]},
    )
    fig.patch.set_facecolor("#171b22")
    for ax in (ax_ltr, ax_roll):
        ax.set_facecolor("#171b22")
        ax.grid(True, color="#2c3444", linewidth=0.7)
        ax.tick_params(colors="#e6edf3")
        for spine in ax.spines.values():
            spine.set_color("#2c3444")

    ax_vx = ax_ltr.twinx()
    ax_vx.tick_params(colors="#f2cc60")
    for spine in ax_vx.spines.values():
        spine.set_color("#2c3444")

    ax_ltr.plot(ltr_t, ltr_y, color="#4ea1ff", linewidth=2.0, label="LTR total")
    ax_ltr.set_ylabel("LTR total", color="#e6edf3")
    ax_ltr.set_ylim(-1.05, 1.05)
    ax_ltr.axhline(0, color="#8b949e", linewidth=0.8)
    ax_ltr.axvspan(start, end, color="#4ea1ff", alpha=0.08)

    ax_vx.plot(vx_t, vx_mps * 3.6, color="#f2cc60", linewidth=1.8, label="vx (km/h)")
    ax_vx.set_ylabel("vx (km/h)", color="#f2cc60")

    ax_roll.plot(roll_t, roll_deg, color="#7ee787", linewidth=1.8, label="roll angle (deg)")
    ax_roll.axvspan(start, end, color="#7ee787", alpha=0.08)
    ax_roll.axhline(0, color="#8b949e", linewidth=0.8)
    ax_roll.set_ylabel("roll angle (deg)", color="#e6edf3")
    ax_roll.set_xlabel("time (s)", color="#e6edf3")
    ax_roll.set_xlim(x0, x1)

    ax_ltr.set_title("Segment retournement - LTR, vx, roll angle", color="#e6edf3")
    lines = [
        line
        for line in ax_ltr.get_lines() + ax_vx.get_lines() + ax_roll.get_lines()
        if not line.get_label().startswith("_")
    ]
    labels = [line.get_label() for line in lines]
    fig.legend(lines, labels, loc="upper center", ncol=3, frameon=False, labelcolor="#e6edf3")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out_path, format="jpg", facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return out_path


def check_quota(provider: str) -> dict[str, Any]:
    normalized_provider = _normalize_provider(provider)
    state = _LOCAL_QUOTA.setdefault(normalized_provider, {"requests_sent": 0, "last_headers": {}, "last_status": None})
    return {
        "provider": normalized_provider,
        "requests_sent_local": int(state.get("requests_sent") or 0),
        "last_status": state.get("last_status"),
        "last_headers": dict(state.get("last_headers") or {}),
        "rate_limit": _extract_rate_limit_headers(state.get("last_headers") or {}),
    }


def save_analyse_retournement(
    essai_id: str,
    resultat: dict[str, Any],
    db_path: Path | str = DEFAULT_DB_PATH,
    retries: int = 3,
    retry_delay_sec: float = 0.25,
) -> int:
    if not essai_id:
        raise ValueError("essai_id is required")
    last_error: sqlite3.OperationalError | None = None
    for attempt in range(max(1, retries)):
        try:
            with connect_pipeline_db(db_path) as conn:
                ensure_analyses_retournement_table(conn)
                cur = conn.cursor()
                cur.execute("BEGIN")
                cur.execute(
                    """
                    INSERT INTO analyses_retournement(
                        essai_id, provider, date_analyse, ltr_max_abs, instant_ltr_max_s,
                        vx_a_ltr_max_kmh, roll_angle_max_deg, instant_roll_max_s,
                        roll_angle_a_ltr_max_deg, seuil_ltr_franchi, seuil_critique_approche,
                        oscillations_detectees, oscillations_non_capturees, correlation_vx_ltr,
                        coherence_ltr_roulis, anomalie_detectee, nuance_seuil, confiance,
                        notes, synthese, segment_start_s, segment_end_s, echantillon_points_json,
                        version_parent_id, version_note, is_user_version, source_segment_annotation_id,
                        source_segment_label, source_segment_source
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        essai_id,
                        str(resultat.get("provider") or ""),
                        str(resultat.get("date_analyse") or _now_iso()),
                        _optional_float(resultat.get("ltr_max_abs")),
                        _optional_float(resultat.get("instant_ltr_max_s")),
                        _optional_float(resultat.get("vx_a_ltr_max_kmh")),
                        _optional_float(resultat.get("roll_angle_max_deg")),
                        _optional_float(resultat.get("instant_roll_max_s")),
                        _optional_float(resultat.get("roll_angle_a_ltr_max_deg")),
                        str(resultat.get("seuil_ltr_franchi") or ""),
                        _bool_to_int(resultat.get("seuil_critique_approche")),
                        _bool_to_int(resultat.get("oscillations_detectees")),
                        _bool_to_int(resultat.get("oscillations_non_capturees")),
                        str(resultat.get("correlation_vx_ltr") or ""),
                        str(resultat.get("coherence_ltr_roulis") or ""),
                        str(resultat.get("anomalie_detectee") or ""),
                        str(resultat.get("nuance_seuil") or ""),
                        str(resultat.get("confiance") or ""),
                        str(resultat.get("notes") or ""),
                        str(resultat.get("synthese") or ""),
                        _optional_float(resultat.get("segment_start_s")),
                        _optional_float(resultat.get("segment_end_s")),
                        json.dumps(resultat.get("echantillon_points") or [], ensure_ascii=False),
                        _optional_int(resultat.get("version_parent_id")),
                        str(resultat.get("version_note") or ""),
                        _bool_to_int(resultat.get("is_user_version")),
                        str(resultat.get("source_segment_annotation_id") or ""),
                        str(resultat.get("source_segment_label") or ""),
                        str(resultat.get("source_segment_source") or ""),
                    ),
                )
                conn.commit()
                return int(cur.lastrowid)
        except sqlite3.OperationalError as exc:
            last_error = exc
            if "locked" not in str(exc).lower() or attempt >= retries - 1:
                raise
            time.sleep(retry_delay_sec * (attempt + 1))
    if last_error is not None:
        raise last_error
    raise RolloverAnalysisError("Failed to save rollover analysis")


def get_analyse_retournement(
    analysis_id: int,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> dict[str, Any] | None:
    with connect_pipeline_db(db_path) as conn:
        ensure_analyses_retournement_table(conn)
        row = conn.execute(
            """
            SELECT id, essai_id, provider, date_analyse, ltr_max_abs, instant_ltr_max_s,
                   vx_a_ltr_max_kmh, roll_angle_max_deg, instant_roll_max_s,
                   roll_angle_a_ltr_max_deg, seuil_ltr_franchi, seuil_critique_approche,
                   oscillations_detectees, oscillations_non_capturees, correlation_vx_ltr,
                   coherence_ltr_roulis, anomalie_detectee, nuance_seuil, confiance, notes,
                   synthese, segment_start_s, segment_end_s, echantillon_points_json,
                   version_parent_id, version_note, is_user_version, source_segment_annotation_id,
                   source_segment_label, source_segment_source
            FROM analyses_retournement
            WHERE id = ?
            """,
            (int(analysis_id),),
        ).fetchone()
    return _row_to_analysis_dict(row) if row else None


def delete_analyse_retournement(
    analysis_id: int,
    db_path: Path | str = DEFAULT_DB_PATH,
    retries: int = 3,
    retry_delay_sec: float = 0.25,
) -> bool:
    last_error: sqlite3.OperationalError | None = None
    for attempt in range(max(1, retries)):
        try:
            with connect_pipeline_db(db_path) as conn:
                ensure_analyses_retournement_table(conn)
                cur = conn.cursor()
                cur.execute("BEGIN")
                cur.execute("DELETE FROM analyses_retournement WHERE id = ?", (int(analysis_id),))
                conn.commit()
                return cur.rowcount > 0
        except sqlite3.OperationalError as exc:
            last_error = exc
            if "locked" not in str(exc).lower() or attempt >= retries - 1:
                raise
            time.sleep(retry_delay_sec * (attempt + 1))
    if last_error is not None:
        raise last_error
    return False


def create_analyse_retournement_version(
    source_analysis_id: int,
    updates: dict[str, Any],
    db_path: Path | str = DEFAULT_DB_PATH,
) -> int:
    source = get_analyse_retournement(source_analysis_id, db_path)
    if source is None:
        raise KeyError(f"Rollover analysis not found: {source_analysis_id}")
    editable_keys = {
        "coherence_ltr_roulis",
        "oscillations_non_capturees",
        "anomalie_detectee",
        "nuance_seuil",
        "confiance",
        "synthese",
        "notes",
    }
    version = dict(source)
    for key in editable_keys:
        if key in updates:
            version[key] = updates[key]
    if str(version.get("confiance") or "").lower() not in {"haute", "moyenne", "basse"}:
        raise ValueError("confiance must be 'haute', 'moyenne' or 'basse'")
    if "oscillations_non_capturees" in updates and "oscillations_detectees" not in updates:
        version["oscillations_detectees"] = updates["oscillations_non_capturees"]
    version["version_parent_id"] = int(source_analysis_id)
    version["version_note"] = str(updates.get("version_note") or "")
    version["is_user_version"] = True
    version["date_analyse"] = _now_iso()
    version["provider"] = str(source.get("provider") or "")
    return save_analyse_retournement(str(source["essai_id"]), version, db_path=db_path)


def get_dernieres_analyses(
    essai_id: str,
    db_path: Path | str = DEFAULT_DB_PATH,
    limit: int = 20,
) -> list[dict[str, Any]]:
    with connect_pipeline_db(db_path) as conn:
        ensure_analyses_retournement_table(conn)
        rows = conn.execute(
            """
            SELECT id, essai_id, provider, date_analyse, ltr_max_abs, instant_ltr_max_s,
                   vx_a_ltr_max_kmh, roll_angle_max_deg, instant_roll_max_s,
                   roll_angle_a_ltr_max_deg, seuil_ltr_franchi, seuil_critique_approche,
                   oscillations_detectees, oscillations_non_capturees, correlation_vx_ltr,
                   coherence_ltr_roulis, anomalie_detectee, nuance_seuil, confiance, notes,
                   synthese, segment_start_s, segment_end_s, echantillon_points_json,
                   version_parent_id, version_note, is_user_version, source_segment_annotation_id,
                   source_segment_label, source_segment_source
            FROM analyses_retournement
            WHERE essai_id = ?
            ORDER BY date_analyse DESC, id DESC
            LIMIT ?
            """,
            (essai_id, max(1, int(limit))),
        ).fetchall()
    return [_row_to_analysis_dict(row) for row in rows]


def ensure_analyses_retournement_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analyses_retournement (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            essai_id TEXT,
            provider TEXT,
            date_analyse TEXT,
            ltr_max_abs REAL,
            instant_ltr_max_s REAL,
            vx_a_ltr_max_kmh REAL,
            roll_angle_max_deg REAL,
            instant_roll_max_s REAL,
            roll_angle_a_ltr_max_deg REAL,
            seuil_ltr_franchi TEXT,
            seuil_critique_approche INTEGER,
            oscillations_detectees INTEGER,
            oscillations_non_capturees INTEGER,
            correlation_vx_ltr TEXT,
            coherence_ltr_roulis TEXT,
            anomalie_detectee TEXT,
            nuance_seuil TEXT,
            confiance TEXT,
            notes TEXT,
            synthese TEXT,
            segment_start_s REAL,
            segment_end_s REAL,
            echantillon_points_json TEXT,
            version_parent_id INTEGER,
            version_note TEXT,
            is_user_version INTEGER,
            source_segment_annotation_id TEXT,
            source_segment_label TEXT,
            source_segment_source TEXT
        )
        """
    )
    existing = {str(row["name"]) for row in conn.execute('PRAGMA table_info("analyses_retournement")').fetchall()}
    for column, column_type in ANALYSES_RETOURNEMENT_COLUMNS.items():
        if column not in existing:
            conn.execute(f'ALTER TABLE analyses_retournement ADD COLUMN "{column}" {column_type}')
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_analyses_retournement_essai_date
        ON analyses_retournement(essai_id, date_analyse DESC)
        """
    )
    conn.commit()


def format_analysis_markdown(resultat: dict[str, Any]) -> str:
    provider = str(resultat.get("provider") or "n/a")
    model = str(resultat.get("model") or "n/a")
    return "\n".join(
        [
            f"## Synthèse {provider}",
            str(resultat.get("synthese") or "Analyse vide."),
            "",
            "## Détails",
            f"- LTR max abs: {_format_value(resultat.get('ltr_max_abs'))}",
            f"- Instant LTR max: {_format_value(resultat.get('instant_ltr_max_s'))} s",
            f"- vx au LTR max: {_format_value(resultat.get('vx_a_ltr_max_kmh'))} km/h",
            f"- Roll max: {_format_value(resultat.get('roll_angle_max_deg'))} deg à {_format_value(resultat.get('instant_roll_max_s'))} s",
            f"- Roll au pic LTR: {_format_value(resultat.get('roll_angle_a_ltr_max_deg'))} deg",
            f"- Seuil LTR franchi: {resultat.get('seuil_ltr_franchi') or 'n/a'}",
            f"- Cohérence LTR/roulis: {resultat.get('coherence_ltr_roulis') or 'n/a'}",
            f"- Oscillations non capturées: {_format_bool(resultat.get('oscillations_non_capturees'))}",
            f"- Anomalie: {resultat.get('anomalie_detectee') or 'n/a'}",
            f"- Nuance seuil: {resultat.get('nuance_seuil') or 'n/a'}",
            f"- Confiance: {resultat.get('confiance') or 'n/a'}",
            f"- Modèle: {model}",
        ]
    )


def _analyze_curve_groq(image_path: Path, prompt: str) -> dict[str, Any]:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RolloverAnalysisError("GROQ_API_KEY is not configured")
    model = (
        os.environ.get("GROQ_ROLLOVER_VISION_MODEL")
        or os.environ.get("GROQ_ROLLOVER_MODEL")
        or "qwen/qwen3.6-27b"
    )
    data_url = _image_to_data_url(image_path)
    request_body = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _json_prompt(prompt)},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "temperature": 0.1,
        "max_completion_tokens": 2048,
    }
    response_data, headers = _post_json(
        provider="groq",
        url="https://api.groq.com/openai/v1/chat/completions",
        body=request_body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "mas-analyste-essais-dga/0.1",
            "Accept": "application/json",
        },
    )
    try:
        choice = response_data["choices"][0]
        message = choice["message"]
        text = message.get("content") or message.get("reasoning") or ""
    except Exception as exc:
        raise RolloverAnalysisError(f"Malformed Groq response: {exc}") from exc
    return {
        "text": text,
        "model": response_data.get("model") or model,
        "raw_usage": response_data.get("usage"),
        "rate_limit": _extract_rate_limit_headers(headers),
        "finish_reason": choice.get("finish_reason"),
    }


def _analyze_curve_gemini(image_path: Path, prompt: str) -> dict[str, Any]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RolloverAnalysisError("GEMINI_API_KEY is not configured")
    model = os.environ.get("GEMINI_ROLLOVER_MODEL", "gemini-3-flash-preview")
    mime_type, image_b64 = _image_to_inline_data(image_path)
    request_body = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"inline_data": {"mime_type": mime_type, "data": image_b64}},
                    {"text": _json_prompt(prompt)},
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
            "responseSchema": ANALYSIS_RESULT_SCHEMA,
        },
    }
    response_data, headers = _post_json(
        provider="gemini",
        url=f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        body=request_body,
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
            "User-Agent": "mas-analyste-essais-dga/0.1",
            "Accept": "application/json",
        },
    )
    try:
        candidate = response_data["candidates"][0]
        parts = candidate["content"]["parts"]
        text = "".join(str(part.get("text") or "") for part in parts)
    except Exception as exc:
        raise RolloverAnalysisError(f"Malformed Gemini response: {exc}") from exc
    return {
        "text": text,
        "model": model,
        "raw_usage": response_data.get("usageMetadata"),
        "rate_limit": _extract_rate_limit_headers(headers),
        "finish_reason": candidate.get("finishReason"),
    }


def _post_json(
    *,
    provider: str,
    url: str,
    body: dict[str, Any],
    headers: dict[str, str],
    timeout: int = 90,
) -> tuple[dict[str, Any], dict[str, str]]:
    _LOCAL_QUOTA.setdefault(provider, {"requests_sent": 0, "last_headers": {}, "last_status": None})
    _LOCAL_QUOTA[provider]["requests_sent"] = int(_LOCAL_QUOTA[provider].get("requests_sent") or 0) + 1
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            response_headers = dict(response.headers.items())
            _LOCAL_QUOTA[provider]["last_headers"] = response_headers
            _LOCAL_QUOTA[provider]["last_status"] = response.status
            return json.loads(response.read().decode("utf-8")), response_headers
    except urllib.error.HTTPError as exc:
        response_headers = dict(exc.headers.items()) if exc.headers else {}
        _LOCAL_QUOTA[provider]["last_headers"] = response_headers
        _LOCAL_QUOTA[provider]["last_status"] = exc.code
        detail = exc.read().decode("utf-8", errors="replace")
        retry_after = response_headers.get("Retry-After") or response_headers.get("retry-after")
        if exc.code == 429:
            raise ProviderRateLimitError(provider, detail or "quota exceeded", retry_after) from exc
        raise RolloverAnalysisError(f"{provider} API HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RolloverAnalysisError(f"{provider} API request failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RolloverAnalysisError(f"{provider} API request timed out") from exc


def _parse_model_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        raise RolloverAnalysisError("Empty model response")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.DOTALL)
        if not match:
            match = re.search(r"(\{.*\})", raw, flags=re.DOTALL)
        if not match:
            raise RolloverAnalysisError(f"Malformed model JSON response: {raw[:300]}")
        try:
            value = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            raise RolloverAnalysisError(f"Malformed model JSON response: {exc}") from exc
    if not isinstance(value, dict):
        raise RolloverAnalysisError("Model JSON response is not an object")
    return value


def _validate_analysis_result(value: dict[str, Any]) -> dict[str, Any]:
    out = {
        "coherence_ltr_roulis": str(value.get("coherence_ltr_roulis") or ""),
        "oscillations_non_capturees": _required_bool(value, "oscillations_non_capturees"),
        "anomalie_detectee": str(value.get("anomalie_detectee") or ""),
        "nuance_seuil": str(value.get("nuance_seuil") or ""),
        "confiance": str(value.get("confiance") or "").lower(),
        "synthese": str(value.get("synthese") or ""),
    }
    if out["confiance"] not in {"haute", "moyenne", "basse"}:
        raise RolloverAnalysisError("Malformed model JSON response: invalid confiance")
    return out


def _required_float(value: dict[str, Any], key: str) -> float:
    try:
        return float(value[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise RolloverAnalysisError(f"Malformed model JSON response: {key} must be a float") from exc


def _required_bool(value: dict[str, Any], key: str) -> bool:
    raw = value.get(key)
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)) and raw in (0, 1):
        return bool(raw)
    if isinstance(raw, str) and raw.lower() in {"true", "false", "0", "1"}:
        return raw.lower() in {"true", "1"}
    raise RolloverAnalysisError(f"Malformed model JSON response: {key} must be a bool")


def _json_prompt(prompt: str) -> str:
    return (
        f"{prompt}\n\n"
        "Réponds uniquement avec un objet JSON valide, sans Markdown, sans texte hors JSON, "
        "en respectant exactement ce schéma: "
        f"{json.dumps(ANALYSIS_RESULT_SCHEMA, ensure_ascii=False)}"
    )


def _build_analysis_prompt(prompt: str, segment_metrics: dict[str, Any]) -> str:
    prompt_metrics = {
        key: segment_metrics.get(key)
        for key in (
            "ltr_max_abs",
            "instant_ltr_max_s",
            "vx_a_ltr_max_kmh",
            "roll_angle_max_deg",
            "instant_roll_max_s",
            "roll_angle_a_ltr_max_deg",
            "seuil_ltr_franchi",
            "echantillon_points",
        )
    }
    return prompt.format(
        segment_metrics_json=json.dumps(prompt_metrics, ensure_ascii=False, separators=(",", ":"))
    )


def _series_arrays(data: Any, value_keys: tuple[str, ...]) -> tuple[Any, Any]:
    import numpy as np

    if isinstance(data, dict) and "items" in data:
        data = data.get("items")
    if isinstance(data, dict):
        time_values = data.get("time") or data.get("times")
        value_values = None
        for key in value_keys:
            if key in data:
                value_values = data.get(key)
                break
        if time_values is not None and value_values is not None:
            return np.asarray(time_values, dtype=float), np.asarray(value_values, dtype=float)
    if isinstance(data, list):
        times: list[Any] = []
        values: list[Any] = []
        for row in data:
            if not isinstance(row, dict):
                continue
            value = None
            for key in value_keys:
                if key in row:
                    value = row.get(key)
                    break
            times.append(row.get("time"))
            values.append(value)
        return np.asarray(times, dtype=float), np.asarray(values, dtype=float)
    raise ValueError(f"Unsupported series payload for keys {value_keys}")


def _is_finite(values: Any) -> Any:
    import numpy as np

    return np.isfinite(values)


def _nanargmax_abs(values: Any) -> int:
    import numpy as np

    arr = np.asarray(values, dtype=float)
    if not np.isfinite(arr).any():
        raise ValueError("No finite values available")
    return int(np.nanargmax(np.abs(arr)))


def _interp_or_none(time_s: float, times: Any, values: Any, scale: float = 1.0) -> float | None:
    import numpy as np

    t = np.asarray(times, dtype=float)
    y = np.asarray(values, dtype=float)
    mask = np.isfinite(t) & np.isfinite(y)
    if mask.sum() == 0:
        return None
    t = t[mask]
    y = y[mask]
    order = np.argsort(t)
    t = t[order]
    y = y[order]
    if float(time_s) < float(t[0]) or float(time_s) > float(t[-1]):
        return None
    return float(np.interp(float(time_s), t, y) * scale)


def _regular_sample_times(start: float, end: float, count: int) -> list[float]:
    import numpy as np

    if count <= 1:
        return [float(start)]
    return [float(v) for v in np.linspace(float(start), float(end), int(count))]


def _round_or_none(value: Any, ndigits: int) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), ndigits)
    except (TypeError, ValueError):
        return None


def _image_to_data_url(path: Path) -> str:
    mime_type, image_b64 = _image_to_inline_data(path)
    return f"data:{mime_type};base64,{image_b64}"


def _image_to_inline_data(path: Path) -> tuple[str, str]:
    mime_type = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    if not mime_type.startswith("image/"):
        mime_type = "image/jpeg"
    return mime_type, base64.b64encode(path.read_bytes()).decode("ascii")


def _extract_rate_limit_headers(headers: dict[str, Any]) -> dict[str, Any]:
    interesting = {
        "retry-after",
        "x-ratelimit-limit-requests",
        "x-ratelimit-limit-tokens",
        "x-ratelimit-remaining-requests",
        "x-ratelimit-remaining-tokens",
        "x-ratelimit-reset-requests",
        "x-ratelimit-reset-tokens",
    }
    return {key.lower(): value for key, value in headers.items() if key.lower() in interesting}


def _normalize_provider(provider: str) -> str:
    normalized = str(provider or "").strip().lower()
    if normalized not in {"groq", "gemini"}:
        raise ValueError("provider must be 'groq' or 'gemini'")
    return normalized


def _row_to_analysis_dict(row: sqlite3.Row) -> dict[str, Any]:
    out = dict(row)
    for key in (
        "seuil_critique_approche",
        "oscillations_detectees",
        "oscillations_non_capturees",
        "is_user_version",
    ):
        if out.get(key) is not None:
            out[key] = bool(out[key])
    raw_points = out.pop("echantillon_points_json", None)
    if raw_points:
        try:
            out["echantillon_points"] = json.loads(raw_points)
        except json.JSONDecodeError:
            out["echantillon_points"] = []
    return out


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _bool_to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return 1 if bool(value) else 0


def _format_value(value: Any) -> str:
    if value is None or value == "":
        return "n/a"
    try:
        return f"{float(value):.4g}"
    except (TypeError, ValueError):
        return str(value)


def _format_bool(value: Any) -> str:
    if value is None:
        return "n/a"
    return "oui" if bool(value) else "non"


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyse vision d'un segment LTR/vx/roll et sauvegarde SQLite.")
    parser.add_argument(
        "series_json",
        help="JSON contenant {'ltr': [...], 'vx': [...], 'roll': [...]} avec des points {'time': ..., ...}.",
    )
    parser.add_argument("--provider", required=True, choices=["groq", "gemini"], help="Provider vision à utiliser")
    parser.add_argument("--essai-id", required=True, help="Identifiant essai à stocker en base")
    parser.add_argument("--segment-start", type=float, required=True, help="Début du segment en secondes")
    parser.add_argument("--segment-end", type=float, required=True, help="Fin du segment en secondes")
    parser.add_argument("--warning-threshold", type=float, default=0.60)
    parser.add_argument("--critical-threshold", type=float, default=0.90)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Chemin SQLite")
    args = parser.parse_args()

    payload = json.loads(Path(args.series_json).read_text(encoding="utf-8"))
    thresholds = {"warning": args.warning_threshold, "critical": args.critical_threshold}
    metrics = compute_segment_metrics(
        payload["ltr"],
        payload["vx"],
        payload["roll"],
        args.segment_start,
        args.segment_end,
        thresholds,
    )
    image_path = crop_segment_image(payload, args.segment_start, args.segment_end)
    print(json.dumps(check_quota(args.provider), ensure_ascii=False, indent=2))
    interpretation = analyze_curve(image_path, provider=args.provider, segment_metrics=metrics)
    resultat = {**metrics, **interpretation}
    analysis_id = save_analyse_retournement(args.essai_id, resultat, db_path=args.db)
    print(f"Analyse #{analysis_id} sauvegardée.")
    print(resultat["synthese"])


if __name__ == "__main__":
    main()
