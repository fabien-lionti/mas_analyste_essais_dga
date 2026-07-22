from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from mas_essais.domain.dxd_schema import get_resampled_channels, get_time_values


# =============================================================================
# CONFIG SIMPLE
# =============================================================================

INPUT_DIR = Path("selected_dxd_json_resampled")
OUTPUT_DIR = Path("simple_maneuver_segments")

MIN_SEGMENT_SEC = 3.0          # segments plus courts fusionnés/ignorés
SMOOTH_SEC = 1.0               # lissage pour éviter les labels qui clignotent
EXPORT_SEGMENT_JSON = False    # True = écrit un JSON par segment
EXPORT_PLOTS = True            # export des graphes de contrôle

# Seuils métier simples
LOW_SPEED_MPS = 5.0 / 3.6
STOP_SPEED_MPS = 1.0 / 3.6
YAW_THR = 0.03
AY_THR = 0.50
AX_THR = 0.30
STEER_THR = 0.02


STEER_CHANNELS = [
    "WheelSteer_S1 (_)",
    "WheelSteer_S2 (_)",
    "WhlDirFl_D_Actl (-)",
    "WhlDirFr_D_Actl (-)",
]


# =============================================================================
# UTILS
# =============================================================================

def load_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


def safe_stem(path: Path | str) -> str:
    stem = Path(path).stem
    return "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in stem)


def arr(values: Any, n: int | None = None) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    if n is None:
        return x
    out = np.full(n, np.nan, dtype=float)
    m = min(n, len(x))
    if m:
        out[:m] = x[:m]
    return out


def mean(x: np.ndarray) -> float | None:
    m = np.isfinite(x)
    return float(np.mean(x[m])) if np.any(m) else None


def rms(x: np.ndarray) -> float | None:
    m = np.isfinite(x)
    return float(np.sqrt(np.mean(x[m] ** 2))) if np.any(m) else None


def q95_abs(x: np.ndarray) -> float | None:
    m = np.isfinite(x)
    return float(np.quantile(np.abs(x[m]), 0.95)) if np.any(m) else None


def moving_average(x: np.ndarray, n: int) -> np.ndarray:
    if n <= 1:
        return x.copy()
    valid = np.isfinite(x)
    filled = np.where(valid, x, 0.0)
    k = np.ones(n)
    s = np.convolve(filled, k, mode="same")
    c = np.convolve(valid.astype(float), k, mode="same")
    out = np.full_like(x, np.nan, dtype=float)
    np.divide(s, c, out=out, where=c > 0)
    return out


def derivative(x: np.ndarray, dt: float) -> np.ndarray:
    out = np.full_like(x, np.nan)
    valid = np.isfinite(x)
    if np.sum(valid) < 2:
        return out
    idx = np.where(valid)[0]
    out[idx] = np.gradient(x[idx], dt)
    return out


def first_present(channels: dict[str, np.ndarray], names: list[str]) -> np.ndarray | None:
    for name in names:
        if name in channels:
            return channels[name]
    return None


# =============================================================================
# LECTURE JSON RESAMPLÉ
# =============================================================================

def read_resampled_json(path: Path) -> tuple[dict[str, Any], np.ndarray, dict[str, np.ndarray]]:
    raw = load_json(path)
    time = arr(get_time_values(raw))
    n = len(time)

    channels: dict[str, np.ndarray] = {}
    for name, payload in get_resampled_channels(raw).items():
        if not isinstance(payload, dict) or "values" not in payload:
            continue

        canonical = payload.get("canonical_name") or name
        values = arr(payload["values"], n)

        channels[canonical] = values
        channels[name] = values  # garde aussi le nom source pour steer etc.

    return raw, time, channels


# =============================================================================
# GPS LOCAL SIMPLE
# =============================================================================

def gps_local_xy(lat_deg: np.ndarray, lon_deg: np.ndarray) -> tuple[np.ndarray, np.ndarray, str]:
    lat = np.asarray(lat_deg, dtype=float)
    lon = np.asarray(lon_deg, dtype=float)

    valid = (
        np.isfinite(lat)
        & np.isfinite(lon)
        & (np.abs(lat) <= 90)
        & (np.abs(lon) <= 180)
        & ~((np.abs(lat) < 1e-8) & (np.abs(lon) < 1e-8))
    )

    x = np.full_like(lat, np.nan)
    y = np.full_like(lon, np.nan)

    if np.sum(valid) < 2:
        return x, y, "no_gps"

    idx0 = np.where(valid)[0][0]
    lat0 = np.deg2rad(lat[idx0])
    lon0 = np.deg2rad(lon[idx0])
    r = 6_371_000.0

    x[valid] = r * np.cos(lat0) * (np.deg2rad(lon[valid]) - lon0)
    y[valid] = r * (np.deg2rad(lat[valid]) - lat0)

    return x, y, "ok"


# =============================================================================
# LABEL MÉTIER
# =============================================================================

def label_at(vx: float, ax: float, ay_abs: float, yaw: float, steer_abs: float) -> str:
    # vitesses
    stopped = np.isfinite(vx) and abs(vx) < STOP_SPEED_MPS
    low_speed = np.isfinite(vx) and abs(vx) < LOW_SPEED_MPS

    # excitations
    longitudinal = np.isfinite(ax) and abs(ax) >= AX_THR
    lateral = (
        (np.isfinite(ay_abs) and ay_abs >= AY_THR)
        or (np.isfinite(yaw) and abs(yaw) >= YAW_THR)
        or (np.isfinite(steer_abs) and steer_abs >= STEER_THR)
    )

    if stopped:
        return "standstill"

    if low_speed and lateral:
        return "low_speed_maneuver"

    if lateral and longitudinal:
        return "combined_longitudinal_lateral"

    if lateral:
        if np.isfinite(yaw) and yaw > YAW_THR:
            return "cornering_left"
        if np.isfinite(yaw) and yaw < -YAW_THR:
            return "cornering_right"
        return "mixed_or_unknown"

    if longitudinal:
        if ax > AX_THR:
            return "straight_acceleration"
        if ax < -AX_THR:
            return "straight_braking"
        return "mixed_or_unknown"

    return "straight_constant_speed"


def compute_labels(time: np.ndarray, channels: dict[str, np.ndarray]) -> np.ndarray:
    n = len(time)
    if n < 2:
        return np.array([], dtype=object)

    dt = float(np.nanmedian(np.diff(time)))
    smooth_n = max(1, int(round(SMOOTH_SEC / dt)))

    vx = channels.get("vehicle.vx", np.full(n, np.nan))
    ax = channels.get("vehicle.ax", np.full(n, np.nan))
    ay = channels.get("vehicle.ay", np.full(n, np.nan))
    yaw = channels.get("vehicle.yaw_rate", np.full(n, np.nan))
    steer = first_present(channels, STEER_CHANNELS)
    if steer is None:
        steer = np.full(n, np.nan)

    vx_s = moving_average(vx, smooth_n)
    ax_s = moving_average(ax, smooth_n)
    ay_abs_s = moving_average(np.abs(ay), smooth_n)
    yaw_s = moving_average(yaw, smooth_n)
    steer_abs_s = moving_average(np.abs(steer), smooth_n)

    labels = np.empty(n, dtype=object)
    for i in range(n):
        labels[i] = label_at(vx_s[i], ax_s[i], ay_abs_s[i], yaw_s[i], steer_abs_s[i])

    return labels


# =============================================================================
# SEGMENTATION VARIABLE
# =============================================================================

def run_length_segments(labels: np.ndarray) -> list[tuple[int, int, str]]:
    if len(labels) == 0:
        return []

    segments = []
    start = 0
    current = str(labels[0])

    for i in range(1, len(labels)):
        label = str(labels[i])
        if label != current:
            segments.append((start, i, current))
            start = i
            current = label

    segments.append((start, len(labels), current))
    return segments


def merge_short_segments(segments: list[tuple[int, int, str]], dt: float) -> list[tuple[int, int, str]]:
    if not segments:
        return []

    min_n = max(1, int(round(MIN_SEGMENT_SEC / dt)))
    out: list[tuple[int, int, str]] = []

    for start, end, label in segments:
        if end - start >= min_n:
            out.append((start, end, label))
            continue

        # Segment trop court : on le fusionne avec le précédent si possible.
        if out:
            p0, p1, plabel = out[-1]
            out[-1] = (p0, end, plabel)
        # Sinon il sera absorbé par le suivant.
        else:
            out.append((start, end, label))

    # Fusionne les labels consécutifs identiques.
    merged: list[tuple[int, int, str]] = []
    for start, end, label in out:
        if merged and merged[-1][2] == label:
            merged[-1] = (merged[-1][0], end, label)
        else:
            merged.append((start, end, label))

    # Enlève les segments encore trop courts en fin de traitement.
    return [(s, e, l) for s, e, l in merged if e - s >= min_n]


def make_segments(time: np.ndarray, channels: dict[str, np.ndarray]) -> list[tuple[int, int, str]]:
    if len(time) < 2:
        return []
    dt = float(np.nanmedian(np.diff(time)))
    labels = compute_labels(time, channels)
    raw_segments = run_length_segments(labels)
    return merge_short_segments(raw_segments, dt)


# =============================================================================
# FEATURES PAR SEGMENT
# =============================================================================

def residuals(time: np.ndarray, channels: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    n = len(time)
    if n < 2:
        return {}

    dt = float(np.nanmedian(np.diff(time)))

    vx = channels.get("vehicle.vx")
    vy = channels.get("vehicle.vy")
    ax = channels.get("vehicle.ax")
    ay = channels.get("vehicle.ay")
    yaw = channels.get("vehicle.yaw_rate")
    speed = channels.get("vehicle.speed")
    dist = channels.get("gps.distance")

    out: dict[str, np.ndarray] = {}
    nan = np.full(n, np.nan)

    if ax is not None and vx is not None:
        out["r_ax"] = ax - derivative(vx, dt)
    else:
        out["r_ax"] = nan.copy()

    if ay is not None and vx is not None and yaw is not None:
        out["r_ay_simple"] = ay - vx * yaw
    else:
        out["r_ay_simple"] = nan.copy()

    if ay is not None and vy is not None and vx is not None and yaw is not None:
        out["r_ay"] = ay - (derivative(vy, dt) + vx * yaw)
    else:
        out["r_ay"] = nan.copy()

    if dist is not None and (speed is not None or vx is not None):
        ref = speed if speed is not None else vx
        out["r_dist"] = derivative(dist, dt) - ref
    else:
        out["r_dist"] = nan.copy()

    wheels = [
        channels.get("wheel.fl.omega"),
        channels.get("wheel.fr.omega"),
        channels.get("wheel.rl.omega"),
        channels.get("wheel.rr.omega"),
    ]
    if all(w is not None for w in wheels):
        out["r_wheel"] = np.nanstd(np.column_stack(wheels), axis=1)
    else:
        out["r_wheel"] = nan.copy()

    lat = channels.get("gps.latitude")
    lon = channels.get("gps.longitude")
    if lat is not None and lon is not None and vx is not None:
        gps_x, gps_y, status = gps_local_xy(lat, lon)
        if status == "ok":
            gps_speed = np.sqrt(derivative(gps_x, dt) ** 2 + derivative(gps_y, dt) ** 2)
            out["r_gps_speed"] = gps_speed - np.abs(vx)
        else:
            out["r_gps_speed"] = nan.copy()
    else:
        out["r_gps_speed"] = nan.copy()

    return out


def direction_from_yaw(yaw: np.ndarray) -> str:
    y = yaw[np.isfinite(yaw)]
    if len(y) == 0:
        return "unknown"
    m = float(np.mean(y))
    if m > YAW_THR:
        return "left"
    if m < -YAW_THR:
        return "right"
    return "straight"


def segment_row(
    raw: dict[str, Any],
    json_path: Path,
    time: np.ndarray,
    channels: dict[str, np.ndarray],
    res: dict[str, np.ndarray],
    segment_id: int,
    start: int,
    end: int,
    family: str,
) -> dict[str, Any]:
    vx = channels.get("vehicle.vx", np.full(end - start, np.nan))[start:end]
    ax = channels.get("vehicle.ax", np.full(end - start, np.nan))[start:end]
    ay = channels.get("vehicle.ay", np.full(end - start, np.nan))[start:end]
    yaw = channels.get("vehicle.yaw_rate", np.full(end - start, np.nan))[start:end]
    steer_full = first_present(channels, STEER_CHANNELS)
    steer = steer_full[start:end] if steer_full is not None else np.full(end - start, np.nan)

    mean_vx = mean(vx)
    mean_vx_kmh = mean_vx * 3.6 if mean_vx is not None else None
    rms_ax = rms(ax)
    rms_ay = rms(ay)
    rms_yaw = rms(yaw)
    rms_steer = rms(steer)

    row: dict[str, Any] = {
        "file": raw.get("file"),
        "file_id": raw.get("file_id"),
        "json_name": json_path.name,
        "date": raw.get("date"),
        "modified_at": raw.get("modified_at"),
        "segment_id": segment_id,
        "segment_uid": f"{safe_stem(json_path)}__seg_{segment_id:05d}",
        "maneuver_family": family,
        "start_idx": int(start),
        "end_idx": int(end),
        "start_sec": float(time[start]),
        "end_sec": float(time[end - 1]),
        "duration_sec": float(time[end - 1] - time[start]),
        "n_samples": int(end - start),
        "mean_vx": mean_vx,
        "mean_vx_kmh": mean_vx_kmh,
        "mean_ax": mean(ax),
        "mean_ay": mean(ay),
        "mean_yaw_rate": mean(yaw),
        "rms_ax": rms_ax,
        "rms_ay": rms_ay,
        "rms_yaw_rate": rms_yaw,
        "rms_steer": rms_steer,
        "maneuver_direction": direction_from_yaw(yaw),
    }

    # bins simples pour regrouper plus tard
    row["speed_bin"] = "unknown" if mean_vx_kmh is None else f"{int(mean_vx_kmh // 20) * 20}_{int(mean_vx_kmh // 20) * 20 + 20}"
    row["lat_acc_bin"] = "unknown" if rms_ay is None else "low" if rms_ay < 1 else "medium" if rms_ay < 3 else "high"
    row["long_acc_bin"] = "unknown" if rms_ax is None else "low" if rms_ax < 0.5 else "medium" if rms_ax < 2 else "high"
    row["similarity_group_id"] = (
        f"{row['maneuver_family']}__v_{row['speed_bin']}__"
        f"ay_{row['lat_acc_bin']}__ax_{row['long_acc_bin']}__dir_{row['maneuver_direction']}"
    )

    # résidus
    for name, values in res.items():
        w = values[start:end]
        row[f"{name}_mean"] = mean(w)
        row[f"{name}_rms"] = rms(w)
        row[f"{name}_q95_abs"] = q95_abs(w)

    return row


def segment_json(
    raw: dict[str, Any],
    row: dict[str, Any],
    time: np.ndarray,
    channels: dict[str, np.ndarray],
    start: int,
    end: int,
) -> dict[str, Any]:
    keep_channels = [
        "vehicle.vx",
        "vehicle.vy",
        "vehicle.speed",
        "vehicle.ax",
        "vehicle.ay",
        "vehicle.yaw_rate",
        "gps.latitude",
        "gps.longitude",
        "gps.distance",
        "gps.radius",
        "gps.track",
    ]

    data = {
        "source": {
            "file": raw.get("file"),
            "file_id": raw.get("file_id"),
            "date": raw.get("date"),
            "modified_at": raw.get("modified_at"),
        },
        "segment": row,
        "time": [float(v) if np.isfinite(v) else None for v in time[start:end]],
        "channels": {},
    }

    for name in keep_channels:
        if name in channels:
            data["channels"][name] = [
                float(v) if np.isfinite(v) else None
                for v in channels[name][start:end]
            ]

    return data


# =============================================================================
# PLOTS
# =============================================================================

def import_plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def plot_counts(df: pd.DataFrame) -> None:
    if df.empty:
        return
    plt = import_plt()
    out = OUTPUT_DIR / "plots"
    out.mkdir(parents=True, exist_ok=True)

    counts = df["maneuver_family"].value_counts().sort_values(ascending=True)
    fig, ax = plt.subplots(figsize=(10, 5))
    counts.plot(kind="barh", ax=ax)
    ax.set_title("Segments par catégorie métier")
    ax.set_xlabel("Nombre de segments")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out / "maneuver_family_counts.png", dpi=160)
    plt.close(fig)


def plot_file_vx_and_gps(json_path: Path, file_df: pd.DataFrame) -> None:
    plt = import_plt()
    out = OUTPUT_DIR / "plots" / "files"
    out.mkdir(parents=True, exist_ok=True)

    raw, time, channels = read_resampled_json(json_path)

    # vx(t)
    vx = channels.get("vehicle.vx")
    if vx is not None:
        fig, ax = plt.subplots(figsize=(12, 4))
        ax.plot(time, vx * 3.6, linewidth=0.9)

        for _, r in file_df.iterrows():
            ax.axvspan(float(r["start_sec"]), float(r["end_sec"]), alpha=0.15)

        ax.set_title(f"vx(t) + segments — {json_path.name}")
        ax.set_xlabel("temps (s)")
        ax.set_ylabel("vx (km/h)")
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(out / f"vx__{safe_stem(json_path)}.png", dpi=160)
        plt.close(fig)

    # GPS trace
    lat = channels.get("gps.latitude")
    lon = channels.get("gps.longitude")
    if lat is not None and lon is not None:
        gps_x, gps_y, status = gps_local_xy(lat, lon)
        if status == "ok":
            fig, ax = plt.subplots(figsize=(8, 8))
            ax.plot(gps_x, gps_y, linewidth=0.8, alpha=0.4)

            for _, r in file_df.iterrows():
                s = int(r["start_idx"])
                e = int(r["end_idx"])
                ax.plot(gps_x[s:e], gps_y[s:e], linewidth=2.0, label=str(r["maneuver_family"]))

            ax.set_title(f"trace GPS + segments — {json_path.name}")
            ax.set_xlabel("x local (m)")
            ax.set_ylabel("y local (m)")
            ax.axis("equal")
            ax.grid(alpha=0.3)

            handles, labels = ax.get_legend_handles_labels()
            unique = {}
            for h, l in zip(handles, labels):
                unique.setdefault(l, h)
            if 1 < len(unique) <= 12:
                ax.legend(unique.values(), unique.keys(), fontsize="small")

            fig.tight_layout()
            fig.savefig(out / f"gps__{safe_stem(json_path)}.png", dpi=160)
            plt.close(fig)


def export_plots(df: pd.DataFrame) -> None:
    plot_counts(df)

    for json_name, file_df in df.groupby("json_name"):
        json_path = INPUT_DIR / str(json_name)
        if json_path.exists():
            plot_file_vx_and_gps(json_path, file_df)


# =============================================================================
# MAIN
# =============================================================================

def process_one_file(path: Path) -> list[dict[str, Any]]:
    raw, time, channels = read_resampled_json(path)

    if len(time) < 2:
        return []

    segments = make_segments(time, channels)
    res = residuals(time, channels)

    rows = []

    for segment_id, (start, end, family) in enumerate(segments):
        row = segment_row(
            raw=raw,
            json_path=path,
            time=time,
            channels=channels,
            res=res,
            segment_id=segment_id,
            start=start,
            end=end,
            family=family,
        )

        if EXPORT_SEGMENT_JSON:
            seg_dir = OUTPUT_DIR / family
            seg_path = seg_dir / f"{row['segment_uid']}.json"
            dump_json(seg_path, segment_json(raw, row, time, channels, start, end))
            row["segment_json"] = str(seg_path)
        else:
            row["segment_json"] = ""

        rows.append(row)

    return rows


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    paths = sorted(INPUT_DIR.glob("*.json"))
    print(f"Input dir: {INPUT_DIR.resolve()}")
    print(f"JSON files found: {len(paths)}")

    if not paths:
        raise FileNotFoundError(f"No JSON found in {INPUT_DIR}")

    all_rows = []
    errors = []

    for i, path in enumerate(paths, start=1):
        print(f"[{i}/{len(paths)}] {path.name}", flush=True)
        try:
            all_rows.extend(process_one_file(path))
        except Exception as exc:
            errors.append({"json_name": path.name, "error": str(exc)})

    if not all_rows:
        raise RuntimeError("No segments generated")

    df = pd.DataFrame(all_rows)
    df.to_csv(OUTPUT_DIR / "segment_index.csv", index=False)

    summary = {
        "n_files": len(paths),
        "n_segments": int(len(df)),
        "maneuver_family_counts": {
            str(k): int(v)
            for k, v in df["maneuver_family"].value_counts().items()
        },
        "errors": errors,
    }
    dump_json(OUTPUT_DIR / "dataset_index.json", summary)

    if EXPORT_PLOTS:
        export_plots(df)

    print()
    print(f"Wrote: {OUTPUT_DIR / 'segment_index.csv'}")
    print(f"Wrote: {OUTPUT_DIR / 'dataset_index.json'}")
    if EXPORT_PLOTS:
        print(f"Wrote plots in: {OUTPUT_DIR / 'plots'}")
    print(f"Segments: {len(df)}")
    print("Counts:")
    print(df["maneuver_family"].value_counts())


if __name__ == "__main__":
    main()
