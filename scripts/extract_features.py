# from __future__ import annotations

# import os
# import json
# import glob
# from dataclasses import dataclass, asdict, field

# import numpy as np
# import pandas as pd
# from tqdm import tqdm

# from dxd_schema import get_resampled_channels, get_time_values, normalize_raw_json_schema


# @dataclass
# class Cfg:
#     input_dir: str = "selected_dxd_json_resampled"

#     # sortie principale : une ligne = une fenêtre
#     output_windows_csv: str = "window_univariate_features.csv"
#     output_summary_json: str = "window_univariate_summary.json"

#     # Fenêtrage
#     window_sec: float = 1.0
#     stride_sec: float = 1.0
#     drop_last_incomplete_window: bool = True

#     # Sélection initiale candidate
#     use_channels: list[str] | None = field(default_factory=lambda: [
#         "vehicle.vx",
#         "vehicle.vy",
#         "vehicle.yaw_rate",
#         "vehicle.ay",
#         "vehicle.ax",
#         "wheel.fl.omega",
#         "wheel.fr.omega",
#         "wheel.rl.omega",
#         "wheel.rr.omega",
#         "STR_WHL_ANGLE (Degrees)",
#     ])

#     # Qualité données
#     min_global_finite_ratio: float = 0.90
#     min_channels_required: int = 3

#     # Debug / logs
#     verbose_per_file: bool = True


# def to_float_array(x):
#     arr = np.asarray(x, dtype=np.float64)
#     if arr.ndim == 0:
#         arr = arr.reshape(1)
#     return arr


# def safe_float(v, default=np.nan):
#     try:
#         return float(v)
#     except Exception:
#         return default


# def load_json_file(path):
#     with open(path, "r") as f:
#         data = json.load(f)
#     return normalize_raw_json_schema(data)


# def build_window_index(time, cfg: Cfg):
#     time = to_float_array(time)
#     if len(time) < 2:
#         return None

#     dt = np.mean(np.diff(time))
#     if not np.isfinite(dt) or dt <= 0:
#         return None

#     hz = 1.0 / dt
#     win_len = max(2, int(round(cfg.window_sec * hz)))
#     stride_len = max(1, int(round(cfg.stride_sec * hz)))

#     starts = list(range(0, len(time), stride_len))
#     out = []

#     for start in starts:
#         end = start + win_len

#         if end > len(time):
#             if cfg.drop_last_incomplete_window:
#                 break
#             end = len(time)

#         if end - start < 2:
#             continue

#         out.append((start, end))

#     return {
#         "dt": float(dt),
#         "effective_hz": float(hz),
#         "win_len": int(win_len),
#         "stride_len": int(stride_len),
#         "windows": out,
#     }


# def impute_window_columns(Xw):
#     Xw = np.asarray(Xw, dtype=np.float64).copy()

#     for j in range(Xw.shape[1]):
#         col = Xw[:, j]
#         mask = np.isfinite(col)

#         if mask.sum() == 0:
#             return None

#         if mask.sum() == len(col):
#             continue

#         idx = np.arange(len(col), dtype=np.float64)

#         if mask.sum() == 1:
#             col[~mask] = col[mask][0]
#         else:
#             col[~mask] = np.interp(idx[~mask], idx[mask], col[mask])

#         Xw[:, j] = col

#     return Xw


# def linear_slope(y):
#     y = to_float_array(y)
#     if len(y) < 2:
#         return np.nan

#     x = np.arange(len(y), dtype=np.float64)
#     x_mean = x.mean()
#     y_mean = y.mean()

#     denom = np.sum((x - x_mean) ** 2)
#     if denom <= 0:
#         return 0.0

#     num = np.sum((x - x_mean) * (y - y_mean))
#     return float(num / denom)


# def zero_crossing_rate(y):
#     y = to_float_array(y)
#     if len(y) < 2:
#         return np.nan

#     s = np.sign(y)
#     return float(np.mean(s[1:] != s[:-1]))


# def autocorr_lag1(y):
#     y = to_float_array(y)
#     if len(y) < 2:
#         return np.nan

#     y0 = y[:-1]
#     y1 = y[1:]

#     y0c = y0 - np.mean(y0)
#     y1c = y1 - np.mean(y1)

#     denom = np.sqrt(np.sum(y0c ** 2) * np.sum(y1c ** 2))
#     if denom <= 0:
#         return 0.0

#     return float(np.sum(y0c * y1c) / denom)


# def build_candidate_matrix_for_file(data, cfg: Cfg):
#     file_name = data.get("file", "")
#     filepath = data.get("filepath", "")
#     file_date = data.get("date", None)
#     target_hz = safe_float(data.get("pipeline", {}).get("target_hz", np.nan))
#     time = to_float_array(get_time_values(data))
#     channels = get_resampled_channels(data)

#     if len(time) < 2:
#         return None

#     if cfg.use_channels is None:
#         candidate_channels = list(channels.keys())
#     else:
#         candidate_channels = [ch for ch in cfg.use_channels if ch in channels]

#     if len(candidate_channels) == 0:
#         return None

#     arrays = []
#     kept_names = []
#     for ch in candidate_channels:
#         values = channels[ch].get("values", [])
#         arr = to_float_array(values)
#         arrays.append(arr)
#         kept_names.append(ch)

#     min_len = min(len(a) for a in arrays + [time])
#     if min_len < 2:
#         return None

#     time = time[:min_len]
#     arrays = [a[:min_len] for a in arrays]
#     X = np.column_stack(arrays)

#     return {
#         "file": file_name,
#         "filepath": filepath,
#         "date": file_date,
#         "target_hz": target_hz,
#         "time": time,
#         "X": X,
#         "channel_names": kept_names,
#     }


# def compute_global_channel_finite_ratios(file_mats):
#     channel_sum = {}
#     channel_count = {}

#     for item in file_mats:
#         X = item["X"]
#         channel_names = item["channel_names"]

#         for j, ch in enumerate(channel_names):
#             finite = np.isfinite(X[:, j])
#             channel_sum[ch] = channel_sum.get(ch, 0.0) + float(finite.sum())
#             channel_count[ch] = channel_count.get(ch, 0) + int(len(finite))

#     ratios = {}
#     for ch in channel_sum:
#         ratios[ch] = channel_sum[ch] / channel_count[ch] if channel_count[ch] > 0 else 0.0

#     return ratios


# def print_channel_finite_ratios(file_mats, max_files=10):
#     print("\n=== Finite ratios by channel (sample) ===")
#     for item in file_mats[:max_files]:
#         print(f"\n[FILE] {item['file']}")
#         X = item["X"]
#         channel_names = item["channel_names"]
#         for j, ch in enumerate(channel_names):
#             ratio = float(np.mean(np.isfinite(X[:, j])))
#             print(f"  {ch}: finite_ratio={ratio:.4f}")


# def restrict_file_mats_to_channels(file_mats, selected_channels):
#     out = []
#     for item in file_mats:
#         name_to_idx = {ch: j for j, ch in enumerate(item["channel_names"])}
#         present = [ch for ch in selected_channels if ch in name_to_idx]

#         if len(present) != len(selected_channels):
#             continue

#         idxs = [name_to_idx[ch] for ch in selected_channels]
#         X = item["X"][:, idxs]

#         out.append({
#             "file": item["file"],
#             "filepath": item["filepath"],
#             "date": item["date"],
#             "target_hz": item["target_hz"],
#             "time": item["time"],
#             "X": X,
#             "channel_names": list(selected_channels),
#         })
#     return out


# def make_feature_names(channel_names):
#     prefixes = [
#         "mean",
#         "std",
#         "min",
#         "max",
#         "range",
#         "median",
#         "q25",
#         "q75",
#         "iqr",
#         "mean_abs",
#         "rms",
#         "slope",
#         "diff_std",
#         "max_abs_diff",
#         "zero_crossing_rate",
#         "autocorr_1",
#     ]
#     out = []
#     for prefix in prefixes:
#         out.extend([f"{prefix}__{ch}" for ch in channel_names])
#     return out


# def compute_univariate_features(Xwf):
#     Xwf = np.asarray(Xwf, dtype=np.float64)

#     mean_feat = np.mean(Xwf, axis=0)
#     std_feat = np.std(Xwf, axis=0, ddof=1)
#     min_feat = np.min(Xwf, axis=0)
#     max_feat = np.max(Xwf, axis=0)
#     range_feat = max_feat - min_feat
#     median_feat = np.median(Xwf, axis=0)
#     q25_feat = np.percentile(Xwf, 25, axis=0)
#     q75_feat = np.percentile(Xwf, 75, axis=0)
#     iqr_feat = q75_feat - q25_feat
#     mean_abs_feat = np.mean(np.abs(Xwf), axis=0)
#     rms_feat = np.sqrt(np.mean(Xwf ** 2, axis=0))

#     diff = np.diff(Xwf, axis=0) if len(Xwf) >= 2 else np.zeros((0, Xwf.shape[1]))
#     diff_std_feat = np.std(diff, axis=0, ddof=1) if len(diff) >= 2 else np.zeros(Xwf.shape[1])
#     max_abs_diff_feat = np.max(np.abs(diff), axis=0) if len(diff) >= 1 else np.zeros(Xwf.shape[1])

#     slope_feat = np.array([linear_slope(Xwf[:, j]) for j in range(Xwf.shape[1])], dtype=np.float64)
#     zcr_feat = np.array([zero_crossing_rate(Xwf[:, j]) for j in range(Xwf.shape[1])], dtype=np.float64)
#     autocorr1_feat = np.array([autocorr_lag1(Xwf[:, j]) for j in range(Xwf.shape[1])], dtype=np.float64)

#     return {
#         "mean": mean_feat,
#         "std": std_feat,
#         "min": min_feat,
#         "max": max_feat,
#         "range": range_feat,
#         "median": median_feat,
#         "q25": q25_feat,
#         "q75": q75_feat,
#         "iqr": iqr_feat,
#         "mean_abs": mean_abs_feat,
#         "rms": rms_feat,
#         "slope": slope_feat,
#         "diff_std": diff_std_feat,
#         "max_abs_diff": max_abs_diff_feat,
#         "zero_crossing_rate": zcr_feat,
#         "autocorr_1": autocorr1_feat,
#     }


# def build_univariate_rows_for_file(item, cfg: Cfg):
#     file_name = item["file"]
#     filepath = item["filepath"]
#     file_date = item["date"]
#     target_hz = item["target_hz"]
#     time = item["time"]
#     X = item["X"]
#     channel_names = item["channel_names"]

#     index_info = build_window_index(time, cfg)
#     if index_info is None:
#         return [], channel_names

#     windows = index_info["windows"]
#     effective_hz = index_info["effective_hz"]

#     rows = []
#     n_total = 0
#     n_kept = 0

#     for win_id, (start, end) in enumerate(windows):
#         n_total += 1

#         Xw = X[start:end].copy()
#         tw = time[start:end]

#         Xwf = impute_window_columns(Xw)
#         if Xwf is None or len(Xwf) < 2:
#             continue

#         feats = compute_univariate_features(Xwf)

#         row = {
#             "file": file_name,
#             "filepath": filepath,
#             "date": file_date,
#             "target_hz": target_hz,
#             "effective_hz": effective_hz,
#             "window_id": int(win_id),
#             "window_start_idx": int(start),
#             "window_end_idx": int(end - 1),
#             "window_start_sec": float(tw[0]),
#             "window_end_sec": float(tw[-1]),
#             "window_duration_sec": float(tw[-1] - tw[0]),
#             "n_samples_window": int(len(Xwf)),
#             "n_channels_used": int(len(channel_names)),
#         }

#         for feat_name, feat_values in feats.items():
#             for ch, v in zip(channel_names, feat_values):
#                 row[f"{feat_name}__{ch}"] = float(v)

#         rows.append(row)
#         n_kept += 1

#     if cfg.verbose_per_file:
#         print(f"[INFO] {file_name}: kept {n_kept}/{n_total} windows")

#     return rows, channel_names


# def main():
#     cfg = Cfg()

#     json_files = sorted(glob.glob(os.path.join(cfg.input_dir, "*.json")))
#     if not json_files:
#         raise FileNotFoundError(f"No JSON files found in: {cfg.input_dir}")

#     # 1) Charger tous les fichiers avec les canaux candidats
#     file_mats_raw = []
#     for path in tqdm(json_files, desc="Loading JSON files"):
#         data = load_json_file(path)
#         item = build_candidate_matrix_for_file(data, cfg)
#         if item is not None:
#             file_mats_raw.append(item)

#     if len(file_mats_raw) == 0:
#         raise RuntimeError("No valid multivariate files could be loaded")

#     print_channel_finite_ratios(file_mats_raw, max_files=10)

#     # 2) Choix automatique des canaux suffisamment renseignés
#     ratios = compute_global_channel_finite_ratios(file_mats_raw)
#     ratios_sorted = sorted(ratios.items(), key=lambda x: x[1], reverse=True)

#     print("\n=== Global finite ratios ===")
#     for ch, r in ratios_sorted:
#         print(f"{ch}: {r:.4f}")

#     selected_channels = [ch for ch, r in ratios_sorted if r >= cfg.min_global_finite_ratio]

#     if cfg.use_channels is not None:
#         selected_channels = [ch for ch in cfg.use_channels if ch in selected_channels]

#     print("\n=== Selected channels ===")
#     for ch in selected_channels:
#         print(ch)

#     if len(selected_channels) < cfg.min_channels_required:
#         raise RuntimeError(
#             f"Too few usable channels after filtering: {len(selected_channels)} "
#             f"(min required: {cfg.min_channels_required})"
#         )

#     # 3) Restreindre tous les fichiers à ces canaux communs
#     file_mats = restrict_file_mats_to_channels(file_mats_raw, selected_channels)

#     if len(file_mats) == 0:
#         raise RuntimeError("No files remain after channel restriction")

#     # 4) Fenêtres -> features univariées
#     all_rows = []
#     final_channel_names = list(selected_channels)

#     for item in tqdm(file_mats, desc="Building univariate windows"):
#         rows, _ = build_univariate_rows_for_file(item, cfg)
#         all_rows.extend(rows)

#     if len(all_rows) == 0:
#         raise RuntimeError("No valid windows could be extracted")

#     df = pd.DataFrame(all_rows)

#     feature_cols = [
#         c for c in df.columns
#         if c.startswith((
#             "mean__",
#             "std__",
#             "min__",
#             "max__",
#             "range__",
#             "median__",
#             "q25__",
#             "q75__",
#             "iqr__",
#             "mean_abs__",
#             "rms__",
#             "slope__",
#             "diff_std__",
#             "max_abs_diff__",
#             "zero_crossing_rate__",
#             "autocorr_1__",
#         ))
#     ]

#     summary = {
#         "config": asdict(cfg),
#         "n_json_files": int(len(json_files)),
#         "n_valid_files_raw": int(len(file_mats_raw)),
#         "n_valid_files_final": int(len(file_mats)),
#         "selected_channels": final_channel_names,
#         "n_windows": int(len(df)),
#         "n_channels": int(len(final_channel_names)),
#         "n_features": int(len(feature_cols)),
#         "feature_columns": feature_cols,
#     }

#     df.to_csv(cfg.output_windows_csv, index=False)

#     with open(cfg.output_summary_json, "w") as f:
#         json.dump(summary, f, indent=2)

#     print("\nDone")
#     print("JSON files found:", len(json_files))
#     print("Raw valid files:", len(file_mats_raw))
#     print("Final valid files:", len(file_mats))
#     print("Selected channels:", final_channel_names)
#     print("Windows:", len(df))
#     print("Features:", len(feature_cols))
#     print("Windows CSV:", cfg.output_windows_csv)
#     print("Summary JSON:", cfg.output_summary_json)


# if __name__ == "__main__":
#     main()

# from __future__ import annotations

# import os
# import json
# import glob
# import re
# from dataclasses import dataclass, asdict, field
# from typing import Any

# import numpy as np
# import pandas as pd
# from tqdm import tqdm

# import matplotlib

# matplotlib.use("Agg")
# import matplotlib.pyplot as plt

# from dxd_schema import get_resampled_channels, get_time_values, normalize_raw_json_schema


# # =============================================================================
# # Configuration
# # =============================================================================

# @dataclass
# class Cfg:
#     input_dir: str = "selected_dxd_json_resampled"

#     # Sortie features : une ligne = une fenêtre
#     output_windows_csv: str = "window_univariate_features.csv"
#     output_summary_json: str = "window_univariate_summary.json"

#     # Sorties résidus temporels + visualisations
#     output_residual_root_dir: str = "trajectory_residual_outputs"
#     output_residual_timeseries_dirname: str = "timeseries"
#     output_residual_plots_dirname: str = "plots"

#     # Fenêtrage pour les features univariées aval
#     window_sec: float = 4.0
#     stride_sec: float = 1.0
#     drop_last_incomplete_window: bool = True

#     # True : features uniquement sur les résidus
#     # False : features sur signaux sources + résidus
#     features_on_residuals_only: bool = True

#     # Canaux sources utiles pour calculer/exporter les résidus
#     source_channels: list[str] | None = field(default_factory=lambda: [
#         "vehicle.vx",
#         "vehicle.vy",
#         "vehicle.speed",
#         "vehicle.yaw_rate",
#         "vehicle.ax",
#         "vehicle.ay",
#         "vehicle.az",
#         "imu.ax_body",
#         "imu.ay_body",
#         "imu.az_body",
#         "wheel.fl.omega",
#         "wheel.fr.omega",
#         "wheel.rl.omega",
#         "wheel.rr.omega",
#         "gps.distance",
#         "gps.radius",
#         "gps.latitude",
#         "gps.longitude",
#         "gps.track",
#         "STR_WHL_ANGLE (Degrees)",
#         "WheelSteer_S1 (_)",
#         "WheelSteer_S2 (_)",
#         "WhlDirFl_D_Actl (-)",
#         "WhlDirFr_D_Actl (-)",
#         "WhlDirRl_D_Actl (-)",
#         "WhlDirRr_D_Actl (-)",
#     ])

#     # Qualité données pour les features
#     min_global_finite_ratio: float = 0.10
#     min_channels_required: int = 1

#     # Seuils numériques
#     low_speed_mps: float = 5.0 / 3.6

#     # Visualisation
#     max_plot_points: int = 100_000
#     plot_dpi: int = 130
#     plot_zero_line: bool = True

#     # Debug / logs
#     verbose_per_file: bool = True


# # =============================================================================
# # Utilitaires généraux
# # =============================================================================

# def to_float_array(x: Any) -> np.ndarray:
#     arr = np.asarray(x, dtype=np.float64)
#     if arr.ndim == 0:
#         arr = arr.reshape(1)
#     return arr


# def safe_float(v: Any, default=np.nan) -> float:
#     try:
#         return float(v)
#     except Exception:
#         return default


# def safe_stem(filename: str) -> str:
#     stem = os.path.splitext(os.path.basename(str(filename)))[0]
#     stem = stem.strip() or "unknown_file"
#     return re.sub(r"[^A-Za-z0-9_\-]+", "_", stem)


# def json_safe_scalar(v: Any):
#     try:
#         vf = float(v)
#     except Exception:
#         return None
#     if np.isfinite(vf):
#         return vf
#     return None


# def load_json_file(path: str) -> dict:
#     with open(path, "r", encoding="utf-8") as f:
#         data = json.load(f)
#     return normalize_raw_json_schema(data)


# def finite_array(values: Any, n: int | None = None) -> np.ndarray:
#     arr = np.asarray(values, dtype=np.float64)
#     if arr.ndim == 0:
#         arr = arr.reshape(1)

#     if n is None:
#         return arr

#     out = np.full(n, np.nan, dtype=np.float64)
#     m = min(n, len(arr))
#     if m > 0:
#         out[:m] = arr[:m]
#     return out


# def safe_mean(values: np.ndarray) -> float | None:
#     values = np.asarray(values, dtype=np.float64)
#     mask = np.isfinite(values)
#     if not np.any(mask):
#         return None
#     return float(np.mean(values[mask]))


# def safe_std(values: np.ndarray) -> float | None:
#     values = np.asarray(values, dtype=np.float64)
#     mask = np.isfinite(values)
#     if np.sum(mask) < 2:
#         return None
#     return float(np.std(values[mask], ddof=1))


# def safe_rms(values: np.ndarray) -> float | None:
#     values = np.asarray(values, dtype=np.float64)
#     mask = np.isfinite(values)
#     if not np.any(mask):
#         return None
#     return float(np.sqrt(np.mean(values[mask] ** 2)))


# def safe_max_abs(values: np.ndarray) -> float | None:
#     values = np.asarray(values, dtype=np.float64)
#     mask = np.isfinite(values)
#     if not np.any(mask):
#         return None
#     return float(np.max(np.abs(values[mask])))


# def safe_q95_abs(values: np.ndarray) -> float | None:
#     values = np.asarray(values, dtype=np.float64)
#     mask = np.isfinite(values)
#     if not np.any(mask):
#         return None
#     return float(np.quantile(np.abs(values[mask]), 0.95))


# # =============================================================================
# # Calculs temporels
# # =============================================================================

# def estimate_dt(time: np.ndarray) -> float:
#     time = to_float_array(time)

#     if len(time) < 2:
#         return np.nan

#     diff = np.diff(time)
#     diff = diff[np.isfinite(diff) & (diff > 0)]

#     if len(diff) == 0:
#         return np.nan

#     return float(np.nanmedian(diff))


# def derivative(values: np.ndarray, time: np.ndarray) -> np.ndarray:
#     values = to_float_array(values)
#     time = to_float_array(time)

#     n = min(len(values), len(time))
#     values = values[:n]
#     time = time[:n]

#     out = np.full(n, np.nan, dtype=np.float64)
#     mask = np.isfinite(values) & np.isfinite(time)

#     if np.sum(mask) < 2:
#         return out

#     idx = np.where(mask)[0]
#     t_valid = time[idx]
#     y_valid = values[idx]

#     order = np.argsort(t_valid)
#     idx = idx[order]
#     t_valid = t_valid[order]
#     y_valid = y_valid[order]

#     unique_t, unique_pos = np.unique(t_valid, return_index=True)
#     idx = idx[unique_pos]
#     y_valid = y_valid[unique_pos]
#     t_valid = unique_t

#     if len(t_valid) < 2:
#         return out

#     out[idx] = np.gradient(y_valid, t_valid)
#     return out


# def moving_average_nan(values: np.ndarray, window_n: int) -> np.ndarray:
#     arr = np.asarray(values, dtype=np.float64)

#     if window_n <= 1:
#         return arr.copy()

#     finite = np.isfinite(arr)
#     filled = np.where(finite, arr, 0.0)

#     kernel = np.ones(window_n, dtype=np.float64)
#     sums = np.convolve(filled, kernel, mode="same")
#     counts = np.convolve(finite.astype(np.float64), kernel, mode="same")

#     out = np.full_like(arr, np.nan, dtype=np.float64)
#     np.divide(sums, counts, out=out, where=counts > 0)

#     return out


# def infer_angle_radians(values: np.ndarray) -> tuple[np.ndarray, str]:
#     out = np.asarray(values, dtype=np.float64)
#     finite = out[np.isfinite(out)]

#     if len(finite) == 0:
#         return out, "unknown"

#     # Heuristique : si les angles dépassent largement 2π, on suppose degrés.
#     if np.nanpercentile(np.abs(finite), 95) > 2.5 * np.pi:
#         return np.deg2rad(out), "degrees"

#     return out, "radians"


# def infer_rate_radians_per_sec(values: np.ndarray) -> tuple[np.ndarray, str]:
#     out = np.asarray(values, dtype=np.float64)
#     finite = out[np.isfinite(out)]

#     if len(finite) == 0:
#         return out, "unknown"

#     # Heuristique : au-delà de 3 en valeur typique, possible degrés/s.
#     if np.nanpercentile(np.abs(finite), 95) > 3.0:
#         return np.deg2rad(out), "degrees_per_second"

#     return out, "radians_per_second"


# # =============================================================================
# # GPS / trajectoire
# # =============================================================================

# def local_enu_from_latlon(
#     latitude_deg: np.ndarray,
#     longitude_deg: np.ndarray,
# ) -> tuple[np.ndarray, np.ndarray, str]:
#     lat = np.asarray(latitude_deg, dtype=np.float64)
#     lon = np.asarray(longitude_deg, dtype=np.float64)

#     n = min(len(lat), len(lon))
#     lat = lat[:n]
#     lon = lon[:n]

#     x = np.full(n, np.nan, dtype=np.float64)
#     y = np.full(n, np.nan, dtype=np.float64)

#     mask = (
#         np.isfinite(lat)
#         & np.isfinite(lon)
#         & (np.abs(lat) <= 90.0)
#         & (np.abs(lon) <= 180.0)
#         & ~((np.abs(lat) < 1e-6) & (np.abs(lon) < 1e-6))
#     )

#     if np.sum(mask) < 2:
#         return x, y, "not_computable_missing_or_invalid_gps"

#     med_lat = float(np.nanmedian(lat[mask]))
#     med_lon = float(np.nanmedian(lon[mask]))

#     if abs(med_lat) < 1.0 and abs(med_lon) < 1.0:
#         return x, y, "not_computable_invalid_gps_origin"

#     # Élimination grossière de points GPS absurdes très loin du paquet principal
#     mask = mask & (np.abs(lat - med_lat) < 0.10) & (np.abs(lon - med_lon) < 0.10)

#     if np.sum(mask) < 2:
#         return x, y, "not_computable_gps_outliers"

#     first = np.where(mask)[0][0]
#     lat0 = np.deg2rad(lat[first])
#     lon0 = np.deg2rad(lon[first])

#     earth_radius_m = 6_371_000.0
#     x[mask] = earth_radius_m * np.cos(lat0) * (np.deg2rad(lon[mask]) - lon0)
#     y[mask] = earth_radius_m * (np.deg2rad(lat[mask]) - lat0)

#     return x, y, "computed"


# def integrate_vehicle_trajectory(
#     vx: np.ndarray,
#     vy: np.ndarray,
#     yaw_rate: np.ndarray,
#     time: np.ndarray,
#     initial_heading_rad: float,
# ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
#     vx = to_float_array(vx)
#     vy = to_float_array(vy)
#     yaw_rate = to_float_array(yaw_rate)
#     time = to_float_array(time)

#     n = min(len(vx), len(vy), len(yaw_rate), len(time))
#     vx = vx[:n]
#     vy = vy[:n]
#     yaw_rate = yaw_rate[:n]
#     time = time[:n]

#     x = np.zeros(n, dtype=np.float64)
#     y = np.zeros(n, dtype=np.float64)
#     psi = np.full(n, np.nan, dtype=np.float64)

#     if n < 2:
#         return x, y, psi

#     yaw_rate_rad, _ = infer_rate_radians_per_sec(yaw_rate)
#     yaw_rate_rad = yaw_rate_rad[:n]

#     dt_vec = np.diff(time)
#     dt_vec = np.where(np.isfinite(dt_vec) & (dt_vec > 0), dt_vec, 0.0)

#     yaw_filled = np.where(np.isfinite(yaw_rate_rad), yaw_rate_rad, 0.0)
#     psi[0] = initial_heading_rad

#     for k in range(1, n):
#         psi[k] = psi[k - 1] + yaw_filled[k] * dt_vec[k - 1]

#     vx_filled = np.where(np.isfinite(vx), vx, 0.0)
#     vy_filled = np.where(np.isfinite(vy), vy, 0.0)

#     dx = vx_filled * np.cos(psi) - vy_filled * np.sin(psi)
#     dy = vx_filled * np.sin(psi) + vy_filled * np.cos(psi)

#     for k in range(1, n):
#         x[k] = x[k - 1] + dx[k] * dt_vec[k - 1]
#         y[k] = y[k - 1] + dy[k] * dt_vec[k - 1]

#     return x, y, psi


# def heading_from_gps_track_or_path(
#     gps_track: np.ndarray | None,
#     gps_x: np.ndarray,
#     gps_y: np.ndarray,
#     time: np.ndarray,
#     speed_threshold: float,
# ) -> tuple[float, np.ndarray | None, str]:
#     track_rad = None

#     if gps_track is not None:
#         track_rad, unit = infer_angle_radians(gps_track)
#         # Convention fréquente GPS : 0 = nord.
#         # Convention math : 0 = axe x est.
#         track_rad = (np.pi / 2.0) - track_rad
#     else:
#         unit = "missing"

#     valid_path = np.isfinite(gps_x) & np.isfinite(gps_y)

#     if np.sum(valid_path) >= 2:
#         idx = np.where(valid_path)[0]
#         first = idx[0]
#         last = idx[-1]

#         dx_total = float(gps_x[last] - gps_x[first])
#         dy_total = float(gps_y[last] - gps_y[first])

#         if np.hypot(dx_total, dy_total) > 5.0:
#             return float(np.arctan2(dy_total, dx_total)), track_rad, "gps_path_window"

#     if track_rad is not None:
#         mask = np.isfinite(track_rad)
#         if np.any(mask):
#             first_heading = float(np.unwrap(track_rad[mask])[0])
#             return first_heading, track_rad, f"gps_track_{unit}"

#     dx = derivative(gps_x, time)
#     dy = derivative(gps_y, time)
#     speed = np.sqrt(dx ** 2 + dy ** 2)
#     mask = np.isfinite(dx) & np.isfinite(dy) & (speed > speed_threshold)

#     if np.any(mask):
#         first = np.where(mask)[0][0]
#         return float(np.arctan2(dy[first], dx[first])), None, "gps_path_derivative"

#     return 0.0, None, "fallback_zero"


# def aligned_position_error(
#     gps_x: np.ndarray,
#     gps_y: np.ndarray,
#     int_x: np.ndarray,
#     int_y: np.ndarray,
# ) -> np.ndarray:
#     n = min(len(gps_x), len(gps_y), len(int_x), len(int_y))

#     gps_x = gps_x[:n]
#     gps_y = gps_y[:n]
#     int_x = int_x[:n]
#     int_y = int_y[:n]

#     error = np.full(n, np.nan, dtype=np.float64)
#     valid = np.isfinite(gps_x) & np.isfinite(gps_y) & np.isfinite(int_x) & np.isfinite(int_y)

#     if np.sum(valid) < 2:
#         return error

#     gps = np.column_stack([gps_x[valid], gps_y[valid]])
#     integ = np.column_stack([int_x[valid], int_y[valid]])

#     gps_center = gps.mean(axis=0)
#     int_center = integ.mean(axis=0)

#     gps_c = gps - gps_center
#     int_c = integ - int_center

#     dot = float(np.sum(int_c[:, 0] * gps_c[:, 0] + int_c[:, 1] * gps_c[:, 1]))
#     cross = float(np.sum(int_c[:, 0] * gps_c[:, 1] - int_c[:, 1] * gps_c[:, 0]))

#     angle = np.arctan2(cross, dot)

#     cos_a = np.cos(angle)
#     sin_a = np.sin(angle)

#     rot = np.array([[cos_a, -sin_a], [sin_a, cos_a]])
#     aligned = int_c @ rot.T + gps_center

#     err_valid = np.sqrt(np.sum((gps - aligned) ** 2, axis=1))
#     error[valid] = err_valid

#     return error


# # =============================================================================
# # Résidus
# # =============================================================================

# def make_residual(
#     values: np.ndarray,
#     status: str,
#     formula: str,
#     unit: str,
#     description: str,
# ) -> dict[str, Any]:
#     values = np.asarray(values, dtype=np.float64)

#     return {
#         "values": values,
#         "status": status,
#         "formula": formula,
#         "unit": unit,
#         "description": description,
#         "mean": safe_mean(values),
#         "std": safe_std(values),
#         "rms": safe_rms(values),
#         "max_abs": safe_max_abs(values),
#         "q95_abs": safe_q95_abs(values),
#         "finite_ratio": float(np.mean(np.isfinite(values))) if len(values) else 0.0,
#     }


# def compute_residual_timeseries(
#     arrays: dict[str, np.ndarray],
#     time: np.ndarray,
#     cfg: Cfg,
# ) -> dict[str, dict[str, Any]]:
#     n = len(time)
#     nan = np.full(n, np.nan, dtype=np.float64)

#     residuals: dict[str, dict[str, Any]] = {}

#     vx = arrays.get("vehicle.vx")
#     vy = arrays.get("vehicle.vy")
#     speed = arrays.get("vehicle.speed")
#     yaw = arrays.get("vehicle.yaw_rate")
#     ax = arrays.get("vehicle.ax")
#     ay = arrays.get("vehicle.ay")
#     az = arrays.get("vehicle.az")

#     # Vitesse scalaire véhicule.
#     # Elle sert à comparer avec les vitesses GPS, qui sont positives.
#     if speed is not None:
#         vehicle_speed_norm = speed
#     elif vx is not None and vy is not None:
#         vehicle_speed_norm = np.sqrt(vx ** 2 + vy ** 2)
#     elif vx is not None:
#         vehicle_speed_norm = np.abs(vx)
#     else:
#         vehicle_speed_norm = None
#     # -------------------------------------------------------------------------
#     # Résidu longitudinal : ax - d(vx)/dt
#     # -------------------------------------------------------------------------
#     if ax is not None and vx is not None:
#         dvx_dt = derivative(vx, time)
#         values = ax - dvx_dt
#         residuals["r_ax"] = make_residual(
#             values=values,
#             status="computed",
#             formula="vehicle.ax - d(vehicle.vx)/dt",
#             unit="m/s^2",
#             description="Cohérence longitudinale entre accélération mesurée et dérivée de vx.",
#         )
#     else:
#         residuals["r_ax"] = make_residual(
#             values=nan.copy(),
#             status="not_computable_missing_vehicle_ax_or_vehicle_vx",
#             formula="vehicle.ax - d(vehicle.vx)/dt",
#             unit="m/s^2",
#             description="Cohérence longitudinale entre accélération mesurée et dérivée de vx.",
#         )

#     # -------------------------------------------------------------------------
#     # Résidu latéral simple : ay - vx * yaw_rate
#     # -------------------------------------------------------------------------
#     if ay is not None and vx is not None and yaw is not None:
#         yaw_rad, yaw_unit = infer_rate_radians_per_sec(yaw)
#         values = ay - vx * yaw_rad
#         residuals["r_ay_simple"] = make_residual(
#             values=values,
#             status=f"computed_yaw_unit_{yaw_unit}",
#             formula="vehicle.ay - vehicle.vx * vehicle.yaw_rate",
#             unit="m/s^2",
#             description="Cohérence latérale simplifiée sans dérivée de vy.",
#         )
#     else:
#         residuals["r_ay_simple"] = make_residual(
#             values=nan.copy(),
#             status="not_computable_missing_vehicle_ay_or_vehicle_vx_or_yaw_rate",
#             formula="vehicle.ay - vehicle.vx * vehicle.yaw_rate",
#             unit="m/s^2",
#             description="Cohérence latérale simplifiée sans dérivée de vy.",
#         )

#     # -------------------------------------------------------------------------
#     # Résidu latéral complet : ay - (d(vy)/dt + vx*yaw_rate)
#     # -------------------------------------------------------------------------
#     if ay is not None and vy is not None and vx is not None and yaw is not None:
#         yaw_rad, yaw_unit = infer_rate_radians_per_sec(yaw)
#         dvy_dt = derivative(vy, time)
#         values = ay - (dvy_dt + vx * yaw_rad)
#         residuals["r_ay"] = make_residual(
#             values=values,
#             status=f"computed_yaw_unit_{yaw_unit}",
#             formula="vehicle.ay - (d(vehicle.vy)/dt + vehicle.vx * vehicle.yaw_rate)",
#             unit="m/s^2",
#             description="Cohérence latérale complète dans le repère véhicule.",
#         )
#     else:
#         residuals["r_ay"] = make_residual(
#             values=nan.copy(),
#             status="not_computable_missing_vehicle_ay_or_vehicle_vy_or_vehicle_vx_or_yaw_rate",
#             formula="vehicle.ay - (d(vehicle.vy)/dt + vehicle.vx * vehicle.yaw_rate)",
#             unit="m/s^2",
#             description="Cohérence latérale complète dans le repère véhicule.",
#         )

#     # -------------------------------------------------------------------------
#     # Résidu distance GPS : d(distance)/dt - vitesse véhicule
#     # -------------------------------------------------------------------------
#     distance = arrays.get("gps.distance")
#     if distance is not None and vehicle_speed_norm is not None:
#         ddist_dt = derivative(distance, time)
#         values = ddist_dt - vehicle_speed_norm

#         residuals["r_dist"] = make_residual(
#             values=values,
#             status="computed",
#             formula="d(gps.distance)/dt - vehicle_speed_norm",
#             unit="m/s",
#             description="Cohérence entre distance GPS cumulée et vitesse scalaire véhicule.",
#         )
#     else:
#         residuals["r_dist"] = make_residual(
#             values=nan.copy(),
#             status="not_computable_missing_gps_distance_or_vehicle_speed_norm",
#             formula="d(gps.distance)/dt - vehicle_speed_norm",
#             unit="m/s",
#             description="Cohérence entre distance GPS cumulée et vitesse scalaire véhicule.",
#         )

#     # -------------------------------------------------------------------------
#     # Résidu courbure : 1/radius - yaw_rate/abs(vx)
#     # -------------------------------------------------------------------------
#     radius = arrays.get("gps.radius")

#     if radius is not None and vx is not None and yaw is not None:
#         yaw_rad, yaw_unit = infer_rate_radians_per_sec(yaw)

#         k_veh = np.full(n, np.nan, dtype=np.float64)
#         valid_v = np.isfinite(vx) & (np.abs(vx) >= cfg.low_speed_mps)
#         k_veh[valid_v] = yaw_rad[valid_v] / np.abs(vx[valid_v])

#         k_gps = np.full(n, np.nan, dtype=np.float64)
#         valid_r = np.isfinite(radius) & (np.abs(radius) > 1e-6)
#         k_gps[valid_r] = 1.0 / radius[valid_r]

#         values = k_gps - k_veh

#         residuals["r_kappa"] = make_residual(
#             values=values,
#             status=f"computed_yaw_unit_{yaw_unit}",
#             formula="1/gps.radius - vehicle.yaw_rate / abs(vehicle.vx)",
#             unit="1/m",
#             description="Cohérence entre courbure GPS et courbure cinématique véhicule.",
#         )
#     else:
#         residuals["r_kappa"] = make_residual(
#             values=nan.copy(),
#             status="not_computable_missing_gps_radius_or_vehicle_vx_or_yaw_rate",
#             formula="1/gps.radius - vehicle.yaw_rate / abs(vehicle.vx)",
#             unit="1/m",
#             description="Cohérence entre courbure GPS et courbure cinématique véhicule.",
#         )

#     # -------------------------------------------------------------------------
#     # Résidu roues : écart-type entre les quatre vitesses de roue
#     # -------------------------------------------------------------------------
#     wheels = [
#         arrays.get("wheel.fl.omega"),
#         arrays.get("wheel.fr.omega"),
#         arrays.get("wheel.rl.omega"),
#         arrays.get("wheel.rr.omega"),
#     ]

#     if all(w is not None for w in wheels):
#         wheel_matrix = np.column_stack(wheels)
#         values = np.nanstd(wheel_matrix, axis=1)
#         residuals["r_wheel_std"] = make_residual(
#             values=values,
#             status="computed",
#             formula="std(wheel.fl.omega, wheel.fr.omega, wheel.rl.omega, wheel.rr.omega)",
#             unit="rad/s",
#             description="Dispersion instantanée entre les quatre vitesses de roue.",
#         )
#     else:
#         residuals["r_wheel_std"] = make_residual(
#             values=nan.copy(),
#             status="not_computable_missing_one_or_more_wheel_speed_channels",
#             formula="std(wheel.fl.omega, wheel.fr.omega, wheel.rl.omega, wheel.rr.omega)",
#             unit="rad/s",
#             description="Dispersion instantanée entre les quatre vitesses de roue.",
#         )

#     # -------------------------------------------------------------------------
#     # Résidus WheelSteer / Steering
#     # -------------------------------------------------------------------------
#     steer_s1 = arrays.get("WheelSteer_S1 (_)")
#     steer_s2 = arrays.get("WheelSteer_S2 (_)")
#     str_whl = arrays.get("STR_WHL_ANGLE (Degrees)")

#     steer_s1_rad = None
#     steer_s2_rad = None
#     str_whl_rad = None

#     if steer_s1 is not None:
#         steer_s1_rad, steer_s1_unit = infer_angle_radians(steer_s1)
#     else:
#         steer_s1_unit = "missing"

#     if steer_s2 is not None:
#         steer_s2_rad, steer_s2_unit = infer_angle_radians(steer_s2)
#     else:
#         steer_s2_unit = "missing"

#     if str_whl is not None:
#         str_whl_rad = np.deg2rad(str_whl)
#         str_whl_unit = "degrees_forced"
#     else:
#         str_whl_unit = "missing"

#     if steer_s1_rad is not None and steer_s2_rad is not None:
#         values = steer_s1_rad - steer_s2_rad
#         residuals["r_wheelsteer_s1_minus_s2"] = make_residual(
#             values=values,
#             status=f"computed_s1_{steer_s1_unit}_s2_{steer_s2_unit}",
#             formula="WheelSteer_S1 - WheelSteer_S2",
#             unit="rad",
#             description="Différence directe entre les deux mesures WheelSteer S1 et S2.",
#         )
#     else:
#         residuals["r_wheelsteer_s1_minus_s2"] = make_residual(
#             values=nan.copy(),
#             status="not_computable_missing_wheelsteer_s1_or_s2",
#             formula="WheelSteer_S1 - WheelSteer_S2",
#             unit="rad",
#             description="Différence directe entre les deux mesures WheelSteer S1 et S2.",
#         )

#     if steer_s1_rad is not None and str_whl_rad is not None:
#         values = steer_s1_rad - str_whl_rad
#         residuals["r_wheelsteer_s1_minus_str"] = make_residual(
#             values=values,
#             status=f"computed_s1_{steer_s1_unit}_str_{str_whl_unit}",
#             formula="WheelSteer_S1 - STR_WHL_ANGLE",
#             unit="rad",
#             description="Écart exploratoire entre WheelSteer S1 et angle volant/steer global.",
#         )
#     else:
#         residuals["r_wheelsteer_s1_minus_str"] = make_residual(
#             values=nan.copy(),
#             status="not_computable_missing_wheelsteer_s1_or_str_whl_angle",
#             formula="WheelSteer_S1 - STR_WHL_ANGLE",
#             unit="rad",
#             description="Écart exploratoire entre WheelSteer S1 et angle volant/steer global.",
#         )

#     if steer_s2_rad is not None and str_whl_rad is not None:
#         values = steer_s2_rad - str_whl_rad
#         residuals["r_wheelsteer_s2_minus_str"] = make_residual(
#             values=values,
#             status=f"computed_s2_{steer_s2_unit}_str_{str_whl_unit}",
#             formula="WheelSteer_S2 - STR_WHL_ANGLE",
#             unit="rad",
#             description="Écart exploratoire entre WheelSteer S2 et angle volant/steer global.",
#         )
#     else:
#         residuals["r_wheelsteer_s2_minus_str"] = make_residual(
#             values=nan.copy(),
#             status="not_computable_missing_wheelsteer_s2_or_str_whl_angle",
#             formula="WheelSteer_S2 - STR_WHL_ANGLE",
#             unit="rad",
#             description="Écart exploratoire entre WheelSteer S2 et angle volant/steer global.",
#         )

#     if steer_s1_rad is not None and steer_s2_rad is not None and str_whl_rad is not None:
#         steer_mean = 0.5 * (steer_s1_rad + steer_s2_rad)
#         values = steer_mean - str_whl_rad
#         residuals["r_wheelsteer_mean_minus_str"] = make_residual(
#             values=values,
#             status=f"computed_s1_{steer_s1_unit}_s2_{steer_s2_unit}_str_{str_whl_unit}",
#             formula="0.5 * (WheelSteer_S1 + WheelSteer_S2) - STR_WHL_ANGLE",
#             unit="rad",
#             description="Écart exploratoire entre moyenne S1/S2 et angle volant/steer global.",
#         )
#     else:
#         residuals["r_wheelsteer_mean_minus_str"] = make_residual(
#             values=nan.copy(),
#             status="not_computable_missing_wheelsteer_s1_or_s2_or_str_whl_angle",
#             formula="0.5 * (WheelSteer_S1 + WheelSteer_S2) - STR_WHL_ANGLE",
#             unit="rad",
#             description="Écart exploratoire entre moyenne S1/S2 et angle volant/steer global.",
#         )

#     # -------------------------------------------------------------------------
#     # Résidus IMU
#     # -------------------------------------------------------------------------
#     imu_ax = arrays.get("imu.ax_body")
#     imu_ay = arrays.get("imu.ay_body")
#     imu_az = arrays.get("imu.az_body")

#     if imu_ax is not None and ax is not None:
#         values = imu_ax - ax
#         residuals["r_imu_x"] = make_residual(
#             values=values,
#             status="computed",
#             formula="imu.ax_body - vehicle.ax",
#             unit="m/s^2",
#             description="Écart entre accélération IMU X corps et accélération véhicule ax.",
#         )
#     else:
#         residuals["r_imu_x"] = make_residual(
#             values=nan.copy(),
#             status="not_computable_missing_imu_ax_body_or_vehicle_ax",
#             formula="imu.ax_body - vehicle.ax",
#             unit="m/s^2",
#             description="Écart entre accélération IMU X corps et accélération véhicule ax.",
#         )

#     if imu_ay is not None and ay is not None:
#         values = imu_ay - ay
#         residuals["r_imu_y"] = make_residual(
#             values=values,
#             status="computed",
#             formula="imu.ay_body - vehicle.ay",
#             unit="m/s^2",
#             description="Écart entre accélération IMU Y corps et accélération véhicule ay.",
#         )
#     else:
#         residuals["r_imu_y"] = make_residual(
#             values=nan.copy(),
#             status="not_computable_missing_imu_ay_body_or_vehicle_ay",
#             formula="imu.ay_body - vehicle.ay",
#             unit="m/s^2",
#             description="Écart entre accélération IMU Y corps et accélération véhicule ay.",
#         )

#     if imu_az is not None and az is not None:
#         values = imu_az - az
#         residuals["r_imu_z"] = make_residual(
#             values=values,
#             status="computed",
#             formula="imu.az_body - vehicle.az",
#             unit="m/s^2",
#             description="Écart entre accélération IMU Z corps et accélération véhicule az.",
#         )
#     else:
#         residuals["r_imu_z"] = make_residual(
#             values=nan.copy(),
#             status="not_computable_missing_imu_az_body_or_vehicle_az",
#             formula="imu.az_body - vehicle.az",
#             unit="m/s^2",
#             description="Écart entre accélération IMU Z corps et accélération véhicule az.",
#         )

#     # -------------------------------------------------------------------------
#     # Résidus GPS avancés : vitesse GPS, position intégrée, yaw GPS
#     # -------------------------------------------------------------------------
#     lat = arrays.get("gps.latitude")
#     lon = arrays.get("gps.longitude")
#     track = arrays.get("gps.track")

#     if lat is not None and lon is not None:
#         gps_x, gps_y, gps_status = local_enu_from_latlon(lat, lon)

#         dt = estimate_dt(time)
#         smooth_n = 3
#         if np.isfinite(dt) and dt > 0:
#             smooth_n = max(3, int(round(0.5 / dt)))

#         gps_x_smooth = moving_average_nan(gps_x, smooth_n)
#         gps_y_smooth = moving_average_nan(gps_y, smooth_n)

#         gps_vx = derivative(gps_x_smooth, time)
#         gps_vy = derivative(gps_y_smooth, time)
#         gps_speed = np.sqrt(gps_vx ** 2 + gps_vy ** 2)

#         if vehicle_speed_norm is not None and gps_status == "computed":
#             values = gps_speed - vehicle_speed_norm
#             status = "computed"
#         else:
#             values = nan.copy()
#             status = "not_computable_missing_vehicle_speed_norm_or_invalid_gps"

#         residuals["r_gps_speed"] = make_residual(
#             values=values,
#             status=status,
#             formula="gps_speed_from_latlon - vehicle_speed_norm",
#             unit="m/s",
#             description="Écart entre vitesse dérivée GPS et vitesse scalaire véhicule.",
#         )

#         if vx is not None and vy is not None and gps_status == "computed":
#             body_speed = np.sqrt(vx ** 2 + vy ** 2)
#             values = gps_speed - body_speed
#             status = "computed"
#         elif vx is not None and gps_status == "computed":
#             body_speed = np.abs(vx)
#             values = gps_speed - body_speed
#             status = "computed_without_vy"
#         else:
#             values = nan.copy()
#             status = "not_computable_missing_vehicle_vx_or_invalid_gps"

#         residuals["r_gps_body_speed"] = make_residual(
#             values=values,
#             status=status,
#             formula="gps_speed_from_latlon - sqrt(vehicle.vx^2 + vehicle.vy^2)",
#             unit="m/s",
#             description="Écart entre vitesse GPS et norme de vitesse dans le repère véhicule.",
#         )

#         if vx is not None and yaw is not None and gps_status == "computed":
#             vy_for_int = vy if vy is not None else np.zeros_like(vx)

#             initial_heading, track_rad, heading_source = heading_from_gps_track_or_path(
#                 gps_track=track,
#                 gps_x=gps_x,
#                 gps_y=gps_y,
#                 time=time,
#                 speed_threshold=cfg.low_speed_mps,
#             )

#             int_x, int_y, _ = integrate_vehicle_trajectory(
#                 vx=vx,
#                 vy=vy_for_int,
#                 yaw_rate=yaw,
#                 time=time,
#                 initial_heading_rad=initial_heading,
#             )

#             valid_gps = np.isfinite(gps_x) & np.isfinite(gps_y)
#             first = np.where(valid_gps)[0][0] if np.any(valid_gps) else 0

#             if np.isfinite(gps_x[first]):
#                 int_x = int_x + gps_x[first]
#             if np.isfinite(gps_y[first]):
#                 int_y = int_y + gps_y[first]

#             pos_error = np.sqrt((gps_x - int_x) ** 2 + (gps_y - int_y) ** 2)
#             aligned_error = aligned_position_error(gps_x, gps_y, int_x, int_y)

#             residuals["r_gps_pos"] = make_residual(
#                 values=pos_error,
#                 status=f"computed_{heading_source}",
#                 formula="norm(gps_position - integrated_vehicle_position)",
#                 unit="m",
#                 description="Erreur de position entre GPS local et trajectoire intégrée vx/vy/yaw_rate.",
#             )

#             residuals["r_gps_pos_aligned"] = make_residual(
#                 values=aligned_error,
#                 status=f"computed_aligned_{heading_source}",
#                 formula="aligned_norm(gps_position - integrated_vehicle_position)",
#                 unit="m",
#                 description="Erreur de position après alignement rigide 2D de la trajectoire intégrée sur le GPS.",
#             )

#             if track_rad is not None:
#                 track_unwrapped = np.full_like(track_rad, np.nan, dtype=np.float64)
#                 valid_track = np.isfinite(track_rad)

#                 if np.sum(valid_track) >= 2:
#                     track_unwrapped[valid_track] = np.unwrap(track_rad[valid_track])
#                     gps_yaw_rate = derivative(track_unwrapped, time)
#                     yaw_rad, yaw_unit = infer_rate_radians_per_sec(yaw)

#                     speed_base = np.abs(vx)
#                     if vy is not None:
#                         speed_base = np.sqrt(vx ** 2 + vy ** 2)

#                     speed_mask = np.isfinite(speed_base) & (speed_base > cfg.low_speed_mps)

#                     values = np.full(n, np.nan, dtype=np.float64)
#                     values[speed_mask] = gps_yaw_rate[speed_mask] - yaw_rad[speed_mask]

#                     residuals["r_gps_yaw"] = make_residual(
#                         values=values,
#                         status=f"computed_track_yaw_unit_{yaw_unit}",
#                         formula="d(gps.track)/dt - vehicle.yaw_rate",
#                         unit="rad/s",
#                         description="Écart entre yaw rate dérivé du cap GPS et yaw rate véhicule.",
#                     )
#                 else:
#                     residuals["r_gps_yaw"] = make_residual(
#                         values=nan.copy(),
#                         status="not_computable_invalid_gps_track",
#                         formula="d(gps.track)/dt - vehicle.yaw_rate",
#                         unit="rad/s",
#                         description="Écart entre yaw rate dérivé du cap GPS et yaw rate véhicule.",
#                     )
#             else:
#                 residuals["r_gps_yaw"] = make_residual(
#                     values=nan.copy(),
#                     status="not_computable_missing_gps_track",
#                     formula="d(gps.track)/dt - vehicle.yaw_rate",
#                     unit="rad/s",
#                     description="Écart entre yaw rate dérivé du cap GPS et yaw rate véhicule.",
#                 )
#         else:
#             residuals["r_gps_pos"] = make_residual(
#                 values=nan.copy(),
#                 status="not_computable_missing_vehicle_vx_or_yaw_rate_or_invalid_gps",
#                 formula="norm(gps_position - integrated_vehicle_position)",
#                 unit="m",
#                 description="Erreur de position entre GPS local et trajectoire intégrée vx/vy/yaw_rate.",
#             )
#             residuals["r_gps_pos_aligned"] = make_residual(
#                 values=nan.copy(),
#                 status="not_computable_missing_vehicle_vx_or_yaw_rate_or_invalid_gps",
#                 formula="aligned_norm(gps_position - integrated_vehicle_position)",
#                 unit="m",
#                 description="Erreur de position après alignement rigide 2D de la trajectoire intégrée sur le GPS.",
#             )
#             residuals["r_gps_yaw"] = make_residual(
#                 values=nan.copy(),
#                 status="not_computable_missing_vehicle_vx_or_yaw_rate_or_invalid_gps",
#                 formula="d(gps.track)/dt - vehicle.yaw_rate",
#                 unit="rad/s",
#                 description="Écart entre yaw rate dérivé du cap GPS et yaw rate véhicule.",
#             )
#     else:
#         residuals["r_gps_speed"] = make_residual(
#             values=nan.copy(),
#             status="not_computable_missing_gps_latitude_or_longitude",
#             formula="gps_speed_from_latlon - vehicle.speed",
#             unit="m/s",
#             description="Écart entre vitesse dérivée GPS et vitesse véhicule.",
#         )
#         residuals["r_gps_body_speed"] = make_residual(
#             values=nan.copy(),
#             status="not_computable_missing_gps_latitude_or_longitude",
#             formula="gps_speed_from_latlon - sqrt(vehicle.vx^2 + vehicle.vy^2)",
#             unit="m/s",
#             description="Écart entre vitesse GPS et norme de vitesse dans le repère véhicule.",
#         )
#         residuals["r_gps_pos"] = make_residual(
#             values=nan.copy(),
#             status="not_computable_missing_gps_latitude_or_longitude",
#             formula="norm(gps_position - integrated_vehicle_position)",
#             unit="m",
#             description="Erreur de position entre GPS local et trajectoire intégrée vx/vy/yaw_rate.",
#         )
#         residuals["r_gps_pos_aligned"] = make_residual(
#             values=nan.copy(),
#             status="not_computable_missing_gps_latitude_or_longitude",
#             formula="aligned_norm(gps_position - integrated_vehicle_position)",
#             unit="m",
#             description="Erreur de position après alignement rigide 2D de la trajectoire intégrée sur le GPS.",
#         )
#         residuals["r_gps_yaw"] = make_residual(
#             values=nan.copy(),
#             status="not_computable_missing_gps_latitude_or_longitude",
#             formula="d(gps.track)/dt - vehicle.yaw_rate",
#             unit="rad/s",
#             description="Écart entre yaw rate dérivé du cap GPS et yaw rate véhicule.",
#         )

#     return residuals


# # =============================================================================
# # Export résidus par trajectoire
# # =============================================================================

# def make_trajectory_output_dirs(cfg: Cfg, file_name: str) -> dict[str, str]:
#     stem = safe_stem(file_name)

#     root = os.path.join(cfg.output_residual_root_dir, stem)
#     ts_dir = os.path.join(root, cfg.output_residual_timeseries_dirname)
#     plot_dir = os.path.join(root, cfg.output_residual_plots_dirname)

#     os.makedirs(root, exist_ok=True)
#     os.makedirs(ts_dir, exist_ok=True)
#     os.makedirs(plot_dir, exist_ok=True)

#     return {
#         "root": root,
#         "timeseries": ts_dir,
#         "plots": plot_dir,
#     }


# def downsample_for_plot(
#     time: np.ndarray,
#     values: np.ndarray,
#     max_points: int,
# ) -> tuple[np.ndarray, np.ndarray]:
#     time = np.asarray(time, dtype=np.float64)
#     values = np.asarray(values, dtype=np.float64)

#     n = min(len(time), len(values))
#     time = time[:n]
#     values = values[:n]

#     if n <= max_points:
#         return time, values

#     idx = np.linspace(0, n - 1, max_points).astype(int)
#     return time[idx], values[idx]


# def plot_single_residual(
#     time: np.ndarray,
#     residual_name: str,
#     residual_payload: dict[str, Any],
#     output_path: str,
#     cfg: Cfg,
# ) -> None:
#     values = np.asarray(residual_payload["values"], dtype=np.float64)
#     t_plot, y_plot = downsample_for_plot(time, values, cfg.max_plot_points)

#     fig, ax = plt.subplots(figsize=(14, 5))

#     ax.plot(t_plot, y_plot, linewidth=0.9)

#     if cfg.plot_zero_line:
#         ax.axhline(0.0, linestyle="--", linewidth=0.8)

#     unit = residual_payload.get("unit", "")
#     status = residual_payload.get("status", "")
#     formula = residual_payload.get("formula", "")

#     ax.set_title(f"{residual_name} — {status}")
#     ax.set_xlabel("Time [s]")
#     ax.set_ylabel(f"{residual_name} [{unit}]")
#     ax.grid(True, alpha=0.3)

#     text = (
#         f"formula: {formula}\n"
#         f"rms: {json_safe_scalar(residual_payload.get('rms'))}\n"
#         f"q95_abs: {json_safe_scalar(residual_payload.get('q95_abs'))}\n"
#         f"finite_ratio: {json_safe_scalar(residual_payload.get('finite_ratio'))}"
#     )

#     ax.text(
#         0.01,
#         0.99,
#         text,
#         transform=ax.transAxes,
#         va="top",
#         ha="left",
#         fontsize=9,
#         bbox=dict(boxstyle="round", alpha=0.15),
#     )

#     fig.tight_layout()
#     fig.savefig(output_path, dpi=cfg.plot_dpi)
#     plt.close(fig)


# def plot_all_residuals_overview(
#     time: np.ndarray,
#     residuals: dict[str, dict[str, Any]],
#     output_path: str,
#     cfg: Cfg,
# ) -> None:
#     names = list(residuals.keys())

#     if not names:
#         return

#     n = len(names)
#     fig_height = max(3.0, 2.2 * n)

#     fig, axes = plt.subplots(n, 1, figsize=(14, fig_height), sharex=True)

#     if n == 1:
#         axes = [axes]

#     for ax, name in zip(axes, names):
#         values = np.asarray(residuals[name]["values"], dtype=np.float64)
#         t_plot, y_plot = downsample_for_plot(time, values, cfg.max_plot_points)

#         ax.plot(t_plot, y_plot, linewidth=0.8)

#         if cfg.plot_zero_line:
#             ax.axhline(0.0, linestyle="--", linewidth=0.7)

#         unit = residuals[name].get("unit", "")
#         status = residuals[name].get("status", "")

#         ax.set_ylabel(f"{name}\n[{unit}]")
#         ax.set_title(status, fontsize=9)
#         ax.grid(True, alpha=0.3)

#     axes[-1].set_xlabel("Time [s]")

#     fig.suptitle("All residuals over time", fontsize=14)
#     fig.tight_layout(rect=[0, 0, 1, 0.995])
#     fig.savefig(output_path, dpi=cfg.plot_dpi)
#     plt.close(fig)


# def export_residuals_for_trajectory(
#     raw: dict,
#     time: np.ndarray,
#     arrays: dict[str, np.ndarray],
#     residuals: dict[str, dict[str, Any]],
#     source_json_path: str,
#     cfg: Cfg,
# ) -> dict[str, Any]:
#     file_name = raw.get("file") or os.path.basename(source_json_path)
#     out_dirs = make_trajectory_output_dirs(cfg, file_name)

#     # -------------------------------------------------------------------------
#     # CSV temporel
#     # -------------------------------------------------------------------------
#     ts_data = {
#         "time": np.asarray(time, dtype=np.float64),
#     }

#     useful_source_channels = [
#         "vehicle.vx",
#         "vehicle.vy",
#         "vehicle.speed",
#         "vehicle.ax",
#         "vehicle.ay",
#         "vehicle.az",
#         "vehicle.yaw_rate",
#         "imu.ax_body",
#         "imu.ay_body",
#         "imu.az_body",
#         "gps.distance",
#         "gps.radius",
#         "gps.latitude",
#         "gps.longitude",
#         "gps.track",
#         "wheel.fl.omega",
#         "wheel.fr.omega",
#         "wheel.rl.omega",
#         "wheel.rr.omega",
#         "STR_WHL_ANGLE (Degrees)",
#         "WheelSteer_S1 (_)",
#         "WheelSteer_S2 (_)",
#         "WhlDirFl_D_Actl (-)",
#         "WhlDirFr_D_Actl (-)",
#         "WhlDirRl_D_Actl (-)",
#         "WhlDirRr_D_Actl (-)",
#     ]

#     for ch in useful_source_channels:
#         if ch in arrays:
#             values = np.asarray(arrays[ch], dtype=np.float64)
#             n = min(len(time), len(values))
#             col = np.full(len(time), np.nan, dtype=np.float64)
#             col[:n] = values[:n]
#             ts_data[f"source__{ch}"] = col

#     for name, payload in residuals.items():
#         values = np.asarray(payload["values"], dtype=np.float64)
#         n = min(len(time), len(values))
#         col = np.full(len(time), np.nan, dtype=np.float64)
#         col[:n] = values[:n]
#         ts_data[f"residual__{name}"] = col

#     df_ts = pd.DataFrame(ts_data)
#     residual_csv_path = os.path.join(out_dirs["timeseries"], "residual_timeseries.csv")
#     df_ts.to_csv(residual_csv_path, index=False)

#     # -------------------------------------------------------------------------
#     # JSON metadata
#     # -------------------------------------------------------------------------
#     residual_summary = {}

#     for name, payload in residuals.items():
#         residual_summary[name] = {
#             "status": payload.get("status"),
#             "formula": payload.get("formula"),
#             "unit": payload.get("unit"),
#             "description": payload.get("description"),
#             "mean": payload.get("mean"),
#             "std": payload.get("std"),
#             "rms": payload.get("rms"),
#             "max_abs": payload.get("max_abs"),
#             "q95_abs": payload.get("q95_abs"),
#             "finite_ratio": payload.get("finite_ratio"),
#         }

#     metadata = {
#         "schema_version": "trajectory_residual_outputs.v1",
#         "file": raw.get("file"),
#         "filepath": raw.get("filepath"),
#         "date": raw.get("date"),
#         "source_json_path": source_json_path,
#         "n_samples": int(len(time)),
#         "time_start_sec": json_safe_scalar(time[0]) if len(time) else None,
#         "time_end_sec": json_safe_scalar(time[-1]) if len(time) else None,
#         "dt_median_sec": json_safe_scalar(estimate_dt(time)),
#         "residual_csv": residual_csv_path,
#         "residuals": residual_summary,
#     }

#     metadata_path = os.path.join(out_dirs["root"], "residual_summary.json")
#     with open(metadata_path, "w", encoding="utf-8") as f:
#         json.dump(metadata, f, indent=2, ensure_ascii=False)

#     # -------------------------------------------------------------------------
#     # PNG : un plot par résidu
#     # -------------------------------------------------------------------------
#     plot_paths = {}

#     for name, payload in residuals.items():
#         plot_path = os.path.join(out_dirs["plots"], f"{name}.png")
#         plot_single_residual(
#             time=time,
#             residual_name=name,
#             residual_payload=payload,
#             output_path=plot_path,
#             cfg=cfg,
#         )
#         plot_paths[name] = plot_path

#     overview_path = os.path.join(out_dirs["plots"], "overview_all_residuals.png")
#     plot_all_residuals_overview(
#         time=time,
#         residuals=residuals,
#         output_path=overview_path,
#         cfg=cfg,
#     )

#     return {
#         "trajectory_dir": out_dirs["root"],
#         "timeseries_csv": residual_csv_path,
#         "metadata_json": metadata_path,
#         "overview_plot": overview_path,
#         "plot_paths": plot_paths,
#     }


# # =============================================================================
# # Construction arrays depuis JSON resampled
# # =============================================================================

# def build_channel_arrays_from_json(data: dict, time: np.ndarray) -> dict[str, np.ndarray]:
#     channels = get_resampled_channels(data)
#     n = len(time)

#     arrays: dict[str, np.ndarray] = {}

#     for name, payload in channels.items():
#         if not isinstance(payload, dict):
#             continue

#         if "values" not in payload:
#             continue

#         arr = finite_array(payload.get("values", []), n)

#         # Les JSON de ton pipeline sont normalement déjà canoniques.
#         arrays[name] = arr

#         # Si le payload contient explicitement un canonical_name différent,
#         # on ajoute aussi cette clé pour maximiser la compatibilité.
#         canonical_name = payload.get("canonical_name")
#         if isinstance(canonical_name, str) and canonical_name:
#             arrays[canonical_name] = arr

#     return arrays


# # =============================================================================
# # Fenêtrage + features univariées
# # =============================================================================

# def build_window_index(time: np.ndarray, cfg: Cfg):
#     time = to_float_array(time)

#     if len(time) < 2:
#         return None

#     dt = estimate_dt(time)

#     if not np.isfinite(dt) or dt <= 0:
#         return None

#     hz = 1.0 / dt
#     win_len = max(2, int(round(cfg.window_sec * hz)))
#     stride_len = max(1, int(round(cfg.stride_sec * hz)))

#     starts = list(range(0, len(time), stride_len))
#     out = []

#     for start in starts:
#         end = start + win_len

#         if end > len(time):
#             if cfg.drop_last_incomplete_window:
#                 break
#             end = len(time)

#         if end - start < 2:
#             continue

#         out.append((start, end))

#     return {
#         "dt": float(dt),
#         "effective_hz": float(hz),
#         "win_len": int(win_len),
#         "stride_len": int(stride_len),
#         "windows": out,
#     }


# def impute_window_columns(Xw: np.ndarray):
#     Xw = np.asarray(Xw, dtype=np.float64).copy()

#     for j in range(Xw.shape[1]):
#         col = Xw[:, j]
#         mask = np.isfinite(col)

#         if mask.sum() == 0:
#             return None

#         if mask.sum() == len(col):
#             continue

#         idx = np.arange(len(col), dtype=np.float64)

#         if mask.sum() == 1:
#             col[~mask] = col[mask][0]
#         else:
#             col[~mask] = np.interp(idx[~mask], idx[mask], col[mask])

#         Xw[:, j] = col

#     return Xw


# def linear_slope(y: np.ndarray) -> float:
#     y = to_float_array(y)

#     if len(y) < 2:
#         return np.nan

#     x = np.arange(len(y), dtype=np.float64)
#     x_mean = x.mean()
#     y_mean = y.mean()

#     denom = np.sum((x - x_mean) ** 2)

#     if denom <= 0:
#         return 0.0

#     num = np.sum((x - x_mean) * (y - y_mean))
#     return float(num / denom)


# def zero_crossing_rate(y: np.ndarray) -> float:
#     y = to_float_array(y)

#     if len(y) < 2:
#         return np.nan

#     s = np.sign(y)
#     return float(np.mean(s[1:] != s[:-1]))


# def autocorr_lag1(y: np.ndarray) -> float:
#     y = to_float_array(y)

#     if len(y) < 2:
#         return np.nan

#     y0 = y[:-1]
#     y1 = y[1:]

#     y0c = y0 - np.mean(y0)
#     y1c = y1 - np.mean(y1)

#     denom = np.sqrt(np.sum(y0c ** 2) * np.sum(y1c ** 2))

#     if denom <= 0:
#         return 0.0

#     return float(np.sum(y0c * y1c) / denom)


# def compute_univariate_features(Xwf: np.ndarray) -> dict[str, np.ndarray]:
#     Xwf = np.asarray(Xwf, dtype=np.float64)

#     mean_feat = np.mean(Xwf, axis=0)
#     std_feat = np.std(Xwf, axis=0, ddof=1)
#     min_feat = np.min(Xwf, axis=0)
#     max_feat = np.max(Xwf, axis=0)
#     range_feat = max_feat - min_feat
#     median_feat = np.median(Xwf, axis=0)
#     q25_feat = np.percentile(Xwf, 25, axis=0)
#     q75_feat = np.percentile(Xwf, 75, axis=0)
#     iqr_feat = q75_feat - q25_feat
#     mean_abs_feat = np.mean(np.abs(Xwf), axis=0)
#     rms_feat = np.sqrt(np.mean(Xwf ** 2, axis=0))

#     diff = np.diff(Xwf, axis=0) if len(Xwf) >= 2 else np.zeros((0, Xwf.shape[1]))
#     diff_std_feat = np.std(diff, axis=0, ddof=1) if len(diff) >= 2 else np.zeros(Xwf.shape[1])
#     max_abs_diff_feat = np.max(np.abs(diff), axis=0) if len(diff) >= 1 else np.zeros(Xwf.shape[1])

#     slope_feat = np.array([linear_slope(Xwf[:, j]) for j in range(Xwf.shape[1])], dtype=np.float64)
#     zcr_feat = np.array([zero_crossing_rate(Xwf[:, j]) for j in range(Xwf.shape[1])], dtype=np.float64)
#     autocorr1_feat = np.array([autocorr_lag1(Xwf[:, j]) for j in range(Xwf.shape[1])], dtype=np.float64)

#     return {
#         "mean": mean_feat,
#         "std": std_feat,
#         "min": min_feat,
#         "max": max_feat,
#         "range": range_feat,
#         "median": median_feat,
#         "q25": q25_feat,
#         "q75": q75_feat,
#         "iqr": iqr_feat,
#         "mean_abs": mean_abs_feat,
#         "rms": rms_feat,
#         "slope": slope_feat,
#         "diff_std": diff_std_feat,
#         "max_abs_diff": max_abs_diff_feat,
#         "zero_crossing_rate": zcr_feat,
#         "autocorr_1": autocorr1_feat,
#     }


# def build_univariate_rows_for_file(item: dict, cfg: Cfg):
#     file_name = item["file"]
#     filepath = item["filepath"]
#     file_date = item["date"]
#     target_hz = item["target_hz"]
#     time = item["time"]
#     X = item["X"]
#     channel_names = item["channel_names"]

#     index_info = build_window_index(time, cfg)

#     if index_info is None:
#         return [], channel_names

#     windows = index_info["windows"]
#     effective_hz = index_info["effective_hz"]

#     rows = []
#     n_total = 0
#     n_kept = 0

#     for win_id, (start, end) in enumerate(windows):
#         n_total += 1

#         Xw = X[start:end].copy()
#         tw = time[start:end]

#         Xwf = impute_window_columns(Xw)

#         if Xwf is None or len(Xwf) < 2:
#             continue

#         feats = compute_univariate_features(Xwf)

#         row = {
#             "file": file_name,
#             "filepath": filepath,
#             "date": file_date,
#             "target_hz": target_hz,
#             "effective_hz": effective_hz,
#             "window_id": int(win_id),
#             "window_start_idx": int(start),
#             "window_end_idx": int(end - 1),
#             "window_start_sec": float(tw[0]),
#             "window_end_sec": float(tw[-1]),
#             "window_duration_sec": float(tw[-1] - tw[0]),
#             "n_samples_window": int(len(Xwf)),
#             "n_channels_used": int(len(channel_names)),
#         }

#         for feat_name, feat_values in feats.items():
#             for ch, v in zip(channel_names, feat_values):
#                 row[f"{feat_name}__{ch}"] = float(v)

#         rows.append(row)
#         n_kept += 1

#     if cfg.verbose_per_file:
#         print(f"[INFO] {file_name}: kept {n_kept}/{n_total} windows")

#     return rows, channel_names


# # =============================================================================
# # Préparation par fichier
# # =============================================================================

# def build_matrix_with_residuals_for_file(path: str, cfg: Cfg):
#     data = load_json_file(path)

#     file_name = data.get("file", os.path.basename(path))
#     filepath = data.get("filepath", "")
#     file_date = data.get("date", None)
#     target_hz = safe_float(data.get("pipeline", {}).get("target_hz", np.nan))

#     time = to_float_array(get_time_values(data))

#     if len(time) < 2:
#         return None

#     arrays = build_channel_arrays_from_json(data, time)

#     if not arrays:
#         return None

#     min_len = min([len(time)] + [len(v) for v in arrays.values()])

#     if min_len < 2:
#         return None

#     time = time[:min_len]
#     arrays = {k: v[:min_len] for k, v in arrays.items()}

#     residuals = compute_residual_timeseries(arrays, time, cfg)

#     export_info = export_residuals_for_trajectory(
#         raw=data,
#         time=time,
#         arrays=arrays,
#         residuals=residuals,
#         source_json_path=path,
#         cfg=cfg,
#     )

#     residual_arrays = {
#         f"residual.{name}": payload["values"]
#         for name, payload in residuals.items()
#     }

#     if cfg.features_on_residuals_only:
#         selected = residual_arrays
#     else:
#         selected = {}

#         if cfg.source_channels is None:
#             for name, values in arrays.items():
#                 selected[f"source.{name}"] = values
#         else:
#             for name in cfg.source_channels:
#                 if name in arrays:
#                     selected[f"source.{name}"] = arrays[name]

#         selected.update(residual_arrays)

#     kept_names = []
#     kept_arrays = []

#     for name, arr in selected.items():
#         arr = np.asarray(arr, dtype=np.float64)

#         if len(arr) != len(time):
#             arr_fixed = np.full(len(time), np.nan, dtype=np.float64)
#             m = min(len(time), len(arr))
#             arr_fixed[:m] = arr[:m]
#             arr = arr_fixed

#         kept_names.append(name)
#         kept_arrays.append(arr)

#     if not kept_arrays:
#         return None

#     X = np.column_stack(kept_arrays)

#     return {
#         "file": file_name,
#         "filepath": filepath,
#         "date": file_date,
#         "target_hz": target_hz,
#         "time": time,
#         "X": X,
#         "channel_names": kept_names,
#         "export_info": export_info,
#     }


# def compute_global_channel_finite_ratios(file_mats: list[dict]) -> dict[str, float]:
#     channel_sum = {}
#     channel_count = {}

#     for item in file_mats:
#         X = item["X"]
#         channel_names = item["channel_names"]

#         for j, ch in enumerate(channel_names):
#             finite = np.isfinite(X[:, j])
#             channel_sum[ch] = channel_sum.get(ch, 0.0) + float(finite.sum())
#             channel_count[ch] = channel_count.get(ch, 0) + int(len(finite))

#     ratios = {}

#     for ch in channel_sum:
#         ratios[ch] = channel_sum[ch] / channel_count[ch] if channel_count[ch] > 0 else 0.0

#     return ratios


# def print_channel_finite_ratios(file_mats: list[dict], max_files: int = 10) -> None:
#     print("\n=== Finite ratios by channel/residual sample ===")

#     for item in file_mats[:max_files]:
#         print(f"\n[FILE] {item['file']}")

#         X = item["X"]
#         channel_names = item["channel_names"]

#         for j, ch in enumerate(channel_names):
#             ratio = float(np.mean(np.isfinite(X[:, j])))
#             print(f"  {ch}: finite_ratio={ratio:.4f}")


# def restrict_file_mats_to_channels(
#     file_mats: list[dict],
#     selected_channels: list[str],
# ) -> list[dict]:
#     out = []

#     for item in file_mats:
#         name_to_idx = {ch: j for j, ch in enumerate(item["channel_names"])}
#         present = [ch for ch in selected_channels if ch in name_to_idx]

#         if len(present) != len(selected_channels):
#             continue

#         idxs = [name_to_idx[ch] for ch in selected_channels]
#         X = item["X"][:, idxs]

#         out.append({
#             "file": item["file"],
#             "filepath": item["filepath"],
#             "date": item["date"],
#             "target_hz": item["target_hz"],
#             "time": item["time"],
#             "X": X,
#             "channel_names": list(selected_channels),
#             "export_info": item.get("export_info", {}),
#         })

#     return out


# # =============================================================================
# # Main
# # =============================================================================

# def main() -> None:
#     cfg = Cfg()

#     json_files = sorted(glob.glob(os.path.join(cfg.input_dir, "*.json")))

#     if not json_files:
#         raise FileNotFoundError(f"No JSON files found in: {cfg.input_dir}")

#     os.makedirs(cfg.output_residual_root_dir, exist_ok=True)

#     # 1) Charger les fichiers, calculer les résidus temporels et exporter les PNG
#     file_mats_raw = []

#     for path in tqdm(json_files, desc="Computing residuals and plots"):
#         item = build_matrix_with_residuals_for_file(path, cfg)

#         if item is not None:
#             file_mats_raw.append(item)

#     if len(file_mats_raw) == 0:
#         raise RuntimeError("No valid files could be loaded")

#     print_channel_finite_ratios(file_mats_raw, max_files=10)

#     # 2) Sélectionner les résidus/canaux suffisamment renseignés globalement
#     ratios = compute_global_channel_finite_ratios(file_mats_raw)
#     ratios_sorted = sorted(ratios.items(), key=lambda x: x[1], reverse=True)

#     print("\n=== Global finite ratios ===")
#     for ch, r in ratios_sorted:
#         print(f"{ch}: {r:.4f}")

#     selected_channels = [
#         ch for ch, r in ratios_sorted
#         if r >= cfg.min_global_finite_ratio
#     ]

#     print("\n=== Selected channels for window features ===")
#     for ch in selected_channels:
#         print(ch)

#     if len(selected_channels) < cfg.min_channels_required:
#         raise RuntimeError(
#             f"Too few usable channels after filtering: {len(selected_channels)} "
#             f"(min required: {cfg.min_channels_required})"
#         )

#     # 3) Restreindre tous les fichiers à ces résidus/canaux communs
#     file_mats = restrict_file_mats_to_channels(file_mats_raw, selected_channels)

#     if len(file_mats) == 0:
#         raise RuntimeError("No files remain after channel restriction")

#     # 4) Fenêtres -> features univariées
#     all_rows = []
#     final_channel_names = list(selected_channels)

#     for item in tqdm(file_mats, desc="Building univariate windows"):
#         rows, _ = build_univariate_rows_for_file(item, cfg)
#         all_rows.extend(rows)

#     if len(all_rows) == 0:
#         raise RuntimeError("No valid windows could be extracted")

#     df = pd.DataFrame(all_rows)

#     feature_cols = [
#         c for c in df.columns
#         if c.startswith((
#             "mean__",
#             "std__",
#             "min__",
#             "max__",
#             "range__",
#             "median__",
#             "q25__",
#             "q75__",
#             "iqr__",
#             "mean_abs__",
#             "rms__",
#             "slope__",
#             "diff_std__",
#             "max_abs_diff__",
#             "zero_crossing_rate__",
#             "autocorr_1__",
#         ))
#     ]

#     trajectory_exports = [
#         item.get("export_info", {})
#         for item in file_mats_raw
#     ]

#     summary = {
#         "config": asdict(cfg),
#         "n_json_files": int(len(json_files)),
#         "n_valid_files_raw": int(len(file_mats_raw)),
#         "n_valid_files_final": int(len(file_mats)),
#         "selected_channels": final_channel_names,
#         "n_windows": int(len(df)),
#         "n_channels": int(len(final_channel_names)),
#         "n_features": int(len(feature_cols)),
#         "feature_columns": feature_cols,
#         "trajectory_exports": trajectory_exports,
#     }

#     df.to_csv(cfg.output_windows_csv, index=False)

#     with open(cfg.output_summary_json, "w", encoding="utf-8") as f:
#         json.dump(summary, f, indent=2, ensure_ascii=False)

#     print("\nDone")
#     print("JSON files found:", len(json_files))
#     print("Raw valid files:", len(file_mats_raw))
#     print("Final valid files:", len(file_mats))
#     print("Selected channels:", final_channel_names)
#     print("Windows:", len(df))
#     print("Features:", len(feature_cols))
#     print("Windows CSV:", cfg.output_windows_csv)
#     print("Summary JSON:", cfg.output_summary_json)
#     print("Residual output root:", cfg.output_residual_root_dir)


# if __name__ == "__main__":
#     main()
from __future__ import annotations

import os
import json
import glob
import re
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from tqdm import tqdm

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from scipy.signal import savgol_filter
except Exception:
    savgol_filter = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from mas_essais.domain.dxd_schema import get_resampled_channels, get_time_values, normalize_raw_json_schema


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class Cfg:
    input_dir: str = "selected_dxd_json_resampled"

    # Sortie principale continue
    output_root_dir: str = "trajectory_continuous_outputs"
    output_timeseries_dirname: str = "timeseries"
    output_plots_dirname: str = "plots"

    # Seuils numériques
    low_speed_mps: float = 5.0 / 3.6

    # Filtrage interne utilisé uniquement pour calculer les résidus.
    # Les signaux sources exportés/tracés restent bruts.
    residual_filter_sec: float = 0.50
    gps_filter_sec: float = 1.00
    savgol_polyorder: int = 2

    # Visualisation
    max_plot_points: int = 100_000
    plot_dpi: int = 130
    plot_zero_line: bool = True

    # Signaux sources que l'on veut exporter et tracer.
    # NE PAS toucher : les sources restent comme demandé.
    source_channels_to_export: list[str] = field(default_factory=lambda: [
        "vehicle.vx",
        "vehicle.vy",
        "vehicle.speed",
        "vehicle.ax",
        "vehicle.ay",
        "vehicle.az",
        "vehicle.yaw_rate",

        "imu.ax_body",
        "imu.ay_body",
        "imu.az_body",

        "wheel.fl.omega",
        "wheel.fr.omega",
        "wheel.rl.omega",
        "wheel.rr.omega",

        "gps.distance",
        "gps.radius",
        "gps.latitude",
        "gps.longitude",
        "gps.track",

        "STR_WHL_ANGLE (Degrees)",
        "WheelSteer_S1 (_)",
        "WheelSteer_S2 (_)",
        "WhlDirFl_D_Actl (-)",
        "WhlDirFr_D_Actl (-)",
        "WhlDirRl_D_Actl (-)",
        "WhlDirRr_D_Actl (-)",
    ])

    # Signaux dérivés sources, tracés/exportés en plus des sources brutes.
    # Ce ne sont pas des résidus.
    export_derived_source_signals: bool = True

    # Debug
    verbose: bool = True


# =============================================================================
# Utilitaires généraux
# =============================================================================

def to_float_array(x: Any) -> np.ndarray:
    arr = np.asarray(x, dtype=np.float64)
    if arr.ndim == 0:
        arr = arr.reshape(1)
    return arr


def safe_stem(filename: str) -> str:
    stem = os.path.splitext(os.path.basename(str(filename)))[0]
    stem = stem.strip() or "unknown_file"
    return re.sub(r"[^A-Za-z0-9_\-]+", "_", stem)


def safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_\-.]+", "_", name)


def json_safe_scalar(v: Any):
    try:
        vf = float(v)
    except Exception:
        return None
    if np.isfinite(vf):
        return vf
    return None


def finite_array(values: Any, n: int | None = None) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)

    if arr.ndim == 0:
        arr = arr.reshape(1)

    if n is None:
        return arr

    out = np.full(n, np.nan, dtype=np.float64)
    m = min(n, len(arr))

    if m > 0:
        out[:m] = arr[:m]

    return out


def load_json_file(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return normalize_raw_json_schema(data)


def safe_mean(values: np.ndarray) -> float | None:
    values = np.asarray(values, dtype=np.float64)
    mask = np.isfinite(values)

    if not np.any(mask):
        return None

    return float(np.mean(values[mask]))


def safe_std(values: np.ndarray) -> float | None:
    values = np.asarray(values, dtype=np.float64)
    mask = np.isfinite(values)

    if np.sum(mask) < 2:
        return None

    return float(np.std(values[mask], ddof=1))


def safe_rms(values: np.ndarray) -> float | None:
    values = np.asarray(values, dtype=np.float64)
    mask = np.isfinite(values)

    if not np.any(mask):
        return None

    return float(np.sqrt(np.mean(values[mask] ** 2)))


def safe_max_abs(values: np.ndarray) -> float | None:
    values = np.asarray(values, dtype=np.float64)
    mask = np.isfinite(values)

    if not np.any(mask):
        return None

    return float(np.max(np.abs(values[mask])))


def safe_q95_abs(values: np.ndarray) -> float | None:
    values = np.asarray(values, dtype=np.float64)
    mask = np.isfinite(values)

    if not np.any(mask):
        return None

    return float(np.quantile(np.abs(values[mask]), 0.95))


def signal_summary(values: np.ndarray) -> dict[str, Any]:
    values = np.asarray(values, dtype=np.float64)
    finite = np.isfinite(values)

    return {
        "finite_ratio": float(np.mean(finite)) if len(values) else 0.0,
        "mean": safe_mean(values),
        "std": safe_std(values),
        "rms": safe_rms(values),
        "max_abs": safe_max_abs(values),
        "q95_abs": safe_q95_abs(values),
    }


# =============================================================================
# Calculs temporels
# =============================================================================

def estimate_dt(time: np.ndarray) -> float:
    time = to_float_array(time)

    if len(time) < 2:
        return np.nan

    diff = np.diff(time)
    diff = diff[np.isfinite(diff) & (diff > 0)]

    if len(diff) == 0:
        return np.nan

    return float(np.nanmedian(diff))


def derivative(values: np.ndarray, time: np.ndarray) -> np.ndarray:
    values = to_float_array(values)
    time = to_float_array(time)

    n = min(len(values), len(time))
    values = values[:n]
    time = time[:n]

    out = np.full(n, np.nan, dtype=np.float64)
    mask = np.isfinite(values) & np.isfinite(time)

    if np.sum(mask) < 2:
        return out

    idx = np.where(mask)[0]
    t_valid = time[idx]
    y_valid = values[idx]

    order = np.argsort(t_valid)
    idx = idx[order]
    t_valid = t_valid[order]
    y_valid = y_valid[order]

    unique_t, unique_pos = np.unique(t_valid, return_index=True)
    idx = idx[unique_pos]
    y_valid = y_valid[unique_pos]
    t_valid = unique_t

    if len(t_valid) < 2:
        return out

    out[idx] = np.gradient(y_valid, t_valid)
    return out


def moving_average_nan(values: np.ndarray, window_n: int) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)

    if window_n <= 1:
        return arr.copy()

    finite = np.isfinite(arr)
    filled = np.where(finite, arr, 0.0)

    kernel = np.ones(window_n, dtype=np.float64)
    sums = np.convolve(filled, kernel, mode="same")
    counts = np.convolve(finite.astype(np.float64), kernel, mode="same")

    out = np.full_like(arr, np.nan, dtype=np.float64)
    np.divide(sums, counts, out=out, where=counts > 0)

    return out


def interpolate_nans_for_filter(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(values, dtype=np.float64)
    finite = np.isfinite(values)

    if finite.sum() == 0:
        return values.copy(), finite

    if finite.sum() == len(values):
        return values.copy(), finite

    idx = np.arange(len(values), dtype=np.float64)
    filled = values.copy()

    if finite.sum() == 1:
        filled[~finite] = values[finite][0]
    else:
        filled[~finite] = np.interp(idx[~finite], idx[finite], values[finite])

    return filled, finite


def restore_large_nan_gaps(
    filtered: np.ndarray,
    finite_mask: np.ndarray,
    max_gap_samples: int,
) -> np.ndarray:
    out = np.asarray(filtered, dtype=np.float64).copy()

    missing = ~finite_mask
    if not np.any(missing):
        return out

    n = len(missing)
    i = 0

    while i < n:
        if not missing[i]:
            i += 1
            continue

        j = i
        while j < n and missing[j]:
            j += 1

        gap_len = j - i

        if gap_len > max_gap_samples:
            out[i:j] = np.nan

        i = j

    return out


def compute_filter_window_n(
    time: np.ndarray,
    filter_sec: float,
    polyorder: int,
) -> int | None:
    dt = estimate_dt(time)

    if not np.isfinite(dt) or dt <= 0:
        return None

    window_n = max(3, int(round(filter_sec / dt)))

    if window_n % 2 == 0:
        window_n += 1

    if window_n <= polyorder:
        window_n = polyorder + 3
        if window_n % 2 == 0:
            window_n += 1

    return int(window_n)


def filter_for_residual(
    values: np.ndarray | None,
    time: np.ndarray,
    filter_sec: float,
    polyorder: int = 2,
) -> np.ndarray | None:
    """
    Filtrage utilisé uniquement pour les résidus.

    Priorité :
    - Savitzky-Golay si scipy est disponible
    - moving average sinon

    Les grands trous de NaN sont restaurés après filtrage.
    """
    if values is None:
        return None

    values = np.asarray(values, dtype=np.float64)

    window_n = compute_filter_window_n(time, filter_sec, polyorder)

    if window_n is None:
        return values.copy()

    if len(values) < window_n:
        return values.copy()

    filled, finite_mask = interpolate_nans_for_filter(values)

    if savgol_filter is not None:
        try:
            filtered = savgol_filter(
                filled,
                window_length=window_n,
                polyorder=polyorder,
                mode="interp",
            )
        except Exception:
            filtered = moving_average_nan(values, window_n)
    else:
        filtered = moving_average_nan(values, window_n)

    dt = estimate_dt(time)
    max_gap_samples = max(1, int(round(filter_sec / dt))) if np.isfinite(dt) and dt > 0 else 1
    filtered = restore_large_nan_gaps(filtered, finite_mask, max_gap_samples)

    return filtered


def smooth_derivative_for_residual(
    values: np.ndarray | None,
    time: np.ndarray,
    filter_sec: float,
    polyorder: int = 2,
) -> np.ndarray | None:
    """
    Dérivée lissée pour les résidus.

    Si scipy est disponible :
        dérivée Savitzky-Golay directe.

    Sinon :
        filtrage puis gradient numérique.
    """
    if values is None:
        return None

    values = np.asarray(values, dtype=np.float64)
    dt = estimate_dt(time)

    if not np.isfinite(dt) or dt <= 0:
        return derivative(values, time)

    window_n = compute_filter_window_n(time, filter_sec, polyorder)

    if window_n is None or len(values) < window_n:
        return derivative(values, time)

    filled, finite_mask = interpolate_nans_for_filter(values)

    if savgol_filter is not None:
        try:
            deriv = savgol_filter(
                filled,
                window_length=window_n,
                polyorder=polyorder,
                deriv=1,
                delta=dt,
                mode="interp",
            )
        except Exception:
            filtered = filter_for_residual(values, time, filter_sec, polyorder)
            deriv = derivative(filtered, time)
    else:
        filtered = filter_for_residual(values, time, filter_sec, polyorder)
        deriv = derivative(filtered, time)

    max_gap_samples = max(1, int(round(filter_sec / dt)))
    deriv = restore_large_nan_gaps(deriv, finite_mask, max_gap_samples)

    return deriv


def infer_angle_radians(values: np.ndarray) -> tuple[np.ndarray, str]:
    out = np.asarray(values, dtype=np.float64)
    finite = out[np.isfinite(out)]

    if len(finite) == 0:
        return out, "unknown"

    # Heuristique : si les angles dépassent largement 2π, on suppose degrés.
    if np.nanpercentile(np.abs(finite), 95) > 2.5 * np.pi:
        return np.deg2rad(out), "degrees"

    return out, "radians"


def infer_rate_radians_per_sec(values: np.ndarray) -> tuple[np.ndarray, str]:
    out = np.asarray(values, dtype=np.float64)
    finite = out[np.isfinite(out)]

    if len(finite) == 0:
        return out, "unknown"

    # Heuristique : au-delà de 3 en valeur typique, possible degrés/s.
    if np.nanpercentile(np.abs(finite), 95) > 3.0:
        return np.deg2rad(out), "degrees_per_second"

    return out, "radians_per_second"


# =============================================================================
# GPS
# =============================================================================

def local_enu_from_latlon(
    latitude_deg: np.ndarray,
    longitude_deg: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, str]:
    lat = np.asarray(latitude_deg, dtype=np.float64)
    lon = np.asarray(longitude_deg, dtype=np.float64)

    n = min(len(lat), len(lon))
    lat = lat[:n]
    lon = lon[:n]

    x = np.full(n, np.nan, dtype=np.float64)
    y = np.full(n, np.nan, dtype=np.float64)

    mask = (
        np.isfinite(lat)
        & np.isfinite(lon)
        & (np.abs(lat) <= 90.0)
        & (np.abs(lon) <= 180.0)
        & ~((np.abs(lat) < 1e-6) & (np.abs(lon) < 1e-6))
    )

    if np.sum(mask) < 2:
        return x, y, "not_computable_missing_or_invalid_gps"

    med_lat = float(np.nanmedian(lat[mask]))
    med_lon = float(np.nanmedian(lon[mask]))

    if abs(med_lat) < 1.0 and abs(med_lon) < 1.0:
        return x, y, "not_computable_invalid_gps_origin"

    mask = mask & (np.abs(lat - med_lat) < 0.10) & (np.abs(lon - med_lon) < 0.10)

    if np.sum(mask) < 2:
        return x, y, "not_computable_gps_outliers"

    first = np.where(mask)[0][0]
    lat0 = np.deg2rad(lat[first])
    lon0 = np.deg2rad(lon[first])

    earth_radius_m = 6_371_000.0

    x[mask] = earth_radius_m * np.cos(lat0) * (np.deg2rad(lon[mask]) - lon0)
    y[mask] = earth_radius_m * (np.deg2rad(lat[mask]) - lat0)

    return x, y, "computed"


# =============================================================================
# Construction arrays depuis JSON resampled
# =============================================================================

def build_channel_arrays_from_json(data: dict, time: np.ndarray) -> dict[str, np.ndarray]:
    channels = get_resampled_channels(data)
    n = len(time)

    arrays: dict[str, np.ndarray] = {}

    for name, payload in channels.items():
        if not isinstance(payload, dict):
            continue

        if "values" not in payload:
            continue

        arr = finite_array(payload.get("values", []), n)

        arrays[name] = arr

        canonical_name = payload.get("canonical_name")
        if isinstance(canonical_name, str) and canonical_name:
            arrays[canonical_name] = arr

    return arrays


def add_derived_source_signals(
    arrays: dict[str, np.ndarray],
    time: np.ndarray,
) -> dict[str, np.ndarray]:
    """
    Ajoute des signaux dérivés côté sources.
    Ce ne sont PAS des résidus.
    Ils sont exportés/tracés pour aider l'interprétation.
    Les signaux sources restent bruts.
    """
    out = dict(arrays)

    vx = arrays.get("vehicle.vx")
    vy = arrays.get("vehicle.vy")
    ax = arrays.get("vehicle.ax")
    ay = arrays.get("vehicle.ay")
    yaw = arrays.get("vehicle.yaw_rate")

    if vx is not None and vy is not None:
        out["vehicle.v_xy_norm"] = np.sqrt(vx ** 2 + vy ** 2)
    elif vx is not None:
        out["vehicle.v_xy_norm"] = np.abs(vx)

    if ax is not None and ay is not None:
        out["vehicle.a_xy_norm"] = np.sqrt(ax ** 2 + ay ** 2)

    if vx is not None:
        out["derived.dvx_dt"] = derivative(vx, time)

    if vy is not None:
        out["derived.dvy_dt"] = derivative(vy, time)

    if yaw is not None:
        yaw_rad, _ = infer_rate_radians_per_sec(yaw)
        out["vehicle.yaw_rate_rad_s"] = yaw_rad

    return out


# =============================================================================
# Résidus continus filtrés
# =============================================================================

def make_residual(
    values: np.ndarray,
    status: str,
    formula: str,
    unit: str,
    description: str,
) -> dict[str, Any]:
    values = np.asarray(values, dtype=np.float64)

    return {
        "values": values,
        "status": status,
        "formula": formula,
        "unit": unit,
        "description": description,
        **signal_summary(values),
    }


def compute_residual_timeseries(
    arrays: dict[str, np.ndarray],
    time: np.ndarray,
    cfg: Cfg,
) -> dict[str, dict[str, Any]]:
    """
    Résidus gardés uniquement :
    - r_ax
    - r_ay_simple
    - r_wheelsteer_s1_minus_s2
    - r_imu_x
    - r_imu_y
    - r_gps_speed

    Les résidus sont calculés sur signaux filtrés.
    Les sources exportées restent brutes.
    """
    n = len(time)
    nan = np.full(n, np.nan, dtype=np.float64)

    residuals: dict[str, dict[str, Any]] = {}

    # -------------------------------------------------------------------------
    # Signaux bruts
    # -------------------------------------------------------------------------
    vx_raw = arrays.get("vehicle.vx")
    vy_raw = arrays.get("vehicle.vy")
    speed_raw = arrays.get("vehicle.speed")
    yaw_raw = arrays.get("vehicle.yaw_rate")
    ax_raw = arrays.get("vehicle.ax")
    ay_raw = arrays.get("vehicle.ay")

    imu_ax_raw = arrays.get("imu.ax_body")
    imu_ay_raw = arrays.get("imu.ay_body")

    steer_s1_raw = arrays.get("WheelSteer_S1 (_)")
    steer_s2_raw = arrays.get("WheelSteer_S2 (_)")

    lat = arrays.get("gps.latitude")
    lon = arrays.get("gps.longitude")

    # -------------------------------------------------------------------------
    # Signaux filtrés pour calcul des résidus
    # -------------------------------------------------------------------------
    vx = filter_for_residual(
        vx_raw,
        time,
        cfg.residual_filter_sec,
        cfg.savgol_polyorder,
    )
    vy = filter_for_residual(
        vy_raw,
        time,
        cfg.residual_filter_sec,
        cfg.savgol_polyorder,
    )
    speed = filter_for_residual(
        speed_raw,
        time,
        cfg.residual_filter_sec,
        cfg.savgol_polyorder,
    )
    yaw = filter_for_residual(
        yaw_raw,
        time,
        cfg.residual_filter_sec,
        cfg.savgol_polyorder,
    )
    ax = filter_for_residual(
        ax_raw,
        time,
        cfg.residual_filter_sec,
        cfg.savgol_polyorder,
    )
    ay = filter_for_residual(
        ay_raw,
        time,
        cfg.residual_filter_sec,
        cfg.savgol_polyorder,
    )

    imu_ax = filter_for_residual(
        imu_ax_raw,
        time,
        cfg.residual_filter_sec,
        cfg.savgol_polyorder,
    )
    imu_ay = filter_for_residual(
        imu_ay_raw,
        time,
        cfg.residual_filter_sec,
        cfg.savgol_polyorder,
    )

    steer_s1 = filter_for_residual(
        steer_s1_raw,
        time,
        cfg.residual_filter_sec,
        cfg.savgol_polyorder,
    )
    steer_s2 = filter_for_residual(
        steer_s2_raw,
        time,
        cfg.residual_filter_sec,
        cfg.savgol_polyorder,
    )

    # Vitesse scalaire véhicule pour comparaison avec GPS.
    if speed is not None:
        vehicle_speed_norm = speed
    elif vx is not None and vy is not None:
        vehicle_speed_norm = np.sqrt(vx ** 2 + vy ** 2)
    elif vx is not None:
        vehicle_speed_norm = np.abs(vx)
    else:
        vehicle_speed_norm = None

    # =========================================================================
    # 1. r_ax = ax - d(vx)/dt
    # =========================================================================
    if ax is not None and vx_raw is not None:
        dvx_dt = smooth_derivative_for_residual(
            vx_raw,
            time,
            cfg.residual_filter_sec,
            cfg.savgol_polyorder,
        )

        if dvx_dt is not None:
            values = ax - dvx_dt
        else:
            values = nan.copy()

        residuals["r_ax"] = make_residual(
            values=values,
            status=f"computed_savgol_filtered_{cfg.residual_filter_sec}s"
            if savgol_filter is not None
            else f"computed_moving_average_filtered_{cfg.residual_filter_sec}s",
            formula="filtered(vehicle.ax) - d_smooth(vehicle.vx)/dt",
            unit="m/s^2",
            description="Cohérence longitudinale filtrée entre ax et la dérivée lissée de vx.",
        )
    else:
        residuals["r_ax"] = make_residual(
            values=nan.copy(),
            status="not_computable_missing_vehicle_ax_or_vehicle_vx",
            formula="filtered(vehicle.ax) - d_smooth(vehicle.vx)/dt",
            unit="m/s^2",
            description="Cohérence longitudinale filtrée entre ax et la dérivée lissée de vx.",
        )

    # =========================================================================
    # 2. r_ay_simple = ay - vx * yaw_rate
    # =========================================================================
    if ay is not None and vx is not None and yaw is not None:
        yaw_rad, yaw_unit = infer_rate_radians_per_sec(yaw)
        values = ay - vx * yaw_rad

        residuals["r_ay_simple"] = make_residual(
            values=values,
            status=f"computed_filtered_{cfg.residual_filter_sec}s_yaw_unit_{yaw_unit}",
            formula="filtered(vehicle.ay) - filtered(vehicle.vx) * filtered(vehicle.yaw_rate)",
            unit="m/s^2",
            description="Cohérence latérale simple filtrée entre ay, vx et yaw_rate.",
        )
    else:
        residuals["r_ay_simple"] = make_residual(
            values=nan.copy(),
            status="not_computable_missing_vehicle_ay_or_vehicle_vx_or_yaw_rate",
            formula="filtered(vehicle.ay) - filtered(vehicle.vx) * filtered(vehicle.yaw_rate)",
            unit="m/s^2",
            description="Cohérence latérale simple filtrée entre ay, vx et yaw_rate.",
        )

    # =========================================================================
    # 3. r_wheelsteer_s1_minus_s2
    # =========================================================================
    steer_s1_rad = None
    steer_s2_rad = None

    if steer_s1 is not None:
        steer_s1_rad, steer_s1_unit = infer_angle_radians(steer_s1)
    else:
        steer_s1_unit = "missing"

    if steer_s2 is not None:
        steer_s2_rad, steer_s2_unit = infer_angle_radians(steer_s2)
    else:
        steer_s2_unit = "missing"

    if steer_s1_rad is not None and steer_s2_rad is not None:
        values = steer_s1_rad - steer_s2_rad

        residuals["r_wheelsteer_s1_minus_s2"] = make_residual(
            values=values,
            status=f"computed_filtered_{cfg.residual_filter_sec}s_s1_{steer_s1_unit}_s2_{steer_s2_unit}",
            formula="filtered(WheelSteer_S1) - filtered(WheelSteer_S2)",
            unit="rad",
            description="Différence filtrée entre les deux mesures WheelSteer S1 et S2.",
        )
    else:
        residuals["r_wheelsteer_s1_minus_s2"] = make_residual(
            values=nan.copy(),
            status="not_computable_missing_wheelsteer_s1_or_s2",
            formula="filtered(WheelSteer_S1) - filtered(WheelSteer_S2)",
            unit="rad",
            description="Différence filtrée entre les deux mesures WheelSteer S1 et S2.",
        )

    # =========================================================================
    # 4. r_imu_x = imu.ax_body - vehicle.ax
    # =========================================================================
    if imu_ax is not None and ax is not None:
        values = imu_ax - ax

        residuals["r_imu_x"] = make_residual(
            values=values,
            status=f"computed_filtered_{cfg.residual_filter_sec}s",
            formula="filtered(imu.ax_body) - filtered(vehicle.ax)",
            unit="m/s^2",
            description="Écart filtré entre accélération IMU X corps et vehicle.ax.",
        )
    else:
        residuals["r_imu_x"] = make_residual(
            values=nan.copy(),
            status="not_computable_missing_imu_ax_body_or_vehicle_ax",
            formula="filtered(imu.ax_body) - filtered(vehicle.ax)",
            unit="m/s^2",
            description="Écart filtré entre accélération IMU X corps et vehicle.ax.",
        )

    # =========================================================================
    # 5. r_imu_y = imu.ay_body - vehicle.ay
    # =========================================================================
    if imu_ay is not None and ay is not None:
        values = imu_ay - ay

        residuals["r_imu_y"] = make_residual(
            values=values,
            status=f"computed_filtered_{cfg.residual_filter_sec}s",
            formula="filtered(imu.ay_body) - filtered(vehicle.ay)",
            unit="m/s^2",
            description="Écart filtré entre accélération IMU Y corps et vehicle.ay.",
        )
    else:
        residuals["r_imu_y"] = make_residual(
            values=nan.copy(),
            status="not_computable_missing_imu_ay_body_or_vehicle_ay",
            formula="filtered(imu.ay_body) - filtered(vehicle.ay)",
            unit="m/s^2",
            description="Écart filtré entre accélération IMU Y corps et vehicle.ay.",
        )

    # =========================================================================
    # 6. r_gps_speed = gps_speed_from_latlon - vehicle_speed_norm
    # =========================================================================
    if lat is not None and lon is not None:
        gps_x, gps_y, gps_status = local_enu_from_latlon(lat, lon)

        gps_x_smooth = filter_for_residual(
            gps_x,
            time,
            cfg.gps_filter_sec,
            cfg.savgol_polyorder,
        )
        gps_y_smooth = filter_for_residual(
            gps_y,
            time,
            cfg.gps_filter_sec,
            cfg.savgol_polyorder,
        )

        gps_vx = smooth_derivative_for_residual(
            gps_x_smooth,
            time,
            cfg.gps_filter_sec,
            cfg.savgol_polyorder,
        )
        gps_vy = smooth_derivative_for_residual(
            gps_y_smooth,
            time,
            cfg.gps_filter_sec,
            cfg.savgol_polyorder,
        )

        if gps_vx is not None and gps_vy is not None:
            gps_speed = np.sqrt(gps_vx ** 2 + gps_vy ** 2)
        else:
            gps_speed = None

        if gps_speed is not None and vehicle_speed_norm is not None and gps_status == "computed":
            vehicle_speed_norm_f = filter_for_residual(
                vehicle_speed_norm,
                time,
                cfg.gps_filter_sec,
                cfg.savgol_polyorder,
            )

            values = gps_speed - vehicle_speed_norm_f
            status = f"computed_gps_filtered_{cfg.gps_filter_sec}s_vehicle_filtered_{cfg.gps_filter_sec}s"
        else:
            values = nan.copy()
            status = "not_computable_missing_vehicle_speed_norm_or_invalid_gps"

        residuals["r_gps_speed"] = make_residual(
            values=values,
            status=status,
            formula="filtered(gps_speed_from_latlon) - filtered(vehicle_speed_norm)",
            unit="m/s",
            description="Écart filtré entre vitesse dérivée GPS et vitesse scalaire véhicule.",
        )
    else:
        residuals["r_gps_speed"] = make_residual(
            values=nan.copy(),
            status="not_computable_missing_gps_latitude_or_longitude",
            formula="filtered(gps_speed_from_latlon) - filtered(vehicle_speed_norm)",
            unit="m/s",
            description="Écart filtré entre vitesse dérivée GPS et vitesse scalaire véhicule.",
        )

    return residuals


# =============================================================================
# Plots
# =============================================================================

def make_output_dirs(cfg: Cfg, file_name: str) -> dict[str, str]:
    stem = safe_stem(file_name)

    root = os.path.join(cfg.output_root_dir, stem)
    ts_dir = os.path.join(root, cfg.output_timeseries_dirname)
    plots_dir = os.path.join(root, cfg.output_plots_dirname)
    source_plots_dir = os.path.join(plots_dir, "sources")
    residual_plots_dir = os.path.join(plots_dir, "residuals")

    os.makedirs(root, exist_ok=True)
    os.makedirs(ts_dir, exist_ok=True)
    os.makedirs(plots_dir, exist_ok=True)
    os.makedirs(source_plots_dir, exist_ok=True)
    os.makedirs(residual_plots_dir, exist_ok=True)

    return {
        "root": root,
        "timeseries": ts_dir,
        "plots": plots_dir,
        "source_plots": source_plots_dir,
        "residual_plots": residual_plots_dir,
    }


def downsample_for_plot(
    time: np.ndarray,
    values: np.ndarray,
    max_points: int,
) -> tuple[np.ndarray, np.ndarray]:
    time = np.asarray(time, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)

    n = min(len(time), len(values))
    time = time[:n]
    values = values[:n]

    if n <= max_points:
        return time, values

    idx = np.linspace(0, n - 1, max_points).astype(int)
    return time[idx], values[idx]


def plot_single_timeseries(
    time: np.ndarray,
    values: np.ndarray,
    name: str,
    output_path: str,
    ylabel: str,
    title_extra: str,
    cfg: Cfg,
    zero_line: bool = False,
) -> None:
    values = np.asarray(values, dtype=np.float64)
    t_plot, y_plot = downsample_for_plot(time, values, cfg.max_plot_points)

    fig, ax = plt.subplots(figsize=(14, 5))

    ax.plot(t_plot, y_plot, linewidth=0.9)

    if zero_line:
        ax.axhline(0.0, linestyle="--", linewidth=0.8)

    ax.set_title(f"{name} — {title_extra}")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)

    summary = signal_summary(values)

    text = (
        f"mean: {json_safe_scalar(summary.get('mean'))}\n"
        f"rms: {json_safe_scalar(summary.get('rms'))}\n"
        f"q95_abs: {json_safe_scalar(summary.get('q95_abs'))}\n"
        f"finite_ratio: {json_safe_scalar(summary.get('finite_ratio'))}"
    )

    ax.text(
        0.01,
        0.99,
        text,
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=9,
        bbox=dict(boxstyle="round", alpha=0.15),
    )

    fig.tight_layout()
    fig.savefig(output_path, dpi=cfg.plot_dpi)
    plt.close(fig)


def plot_overview(
    time: np.ndarray,
    series: dict[str, np.ndarray],
    output_path: str,
    title: str,
    cfg: Cfg,
    zero_line: bool,
) -> None:
    names = list(series.keys())

    if not names:
        return

    n = len(names)
    fig_height = max(3.0, 2.0 * n)

    fig, axes = plt.subplots(n, 1, figsize=(14, fig_height), sharex=True)

    if n == 1:
        axes = [axes]

    for ax, name in zip(axes, names):
        values = np.asarray(series[name], dtype=np.float64)
        t_plot, y_plot = downsample_for_plot(time, values, cfg.max_plot_points)

        ax.plot(t_plot, y_plot, linewidth=0.8)

        if zero_line:
            ax.axhline(0.0, linestyle="--", linewidth=0.7)

        ax.set_ylabel(name)
        ax.grid(True, alpha=0.3)

    axes[-1].set_xlabel("Time [s]")

    fig.suptitle(title, fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.995])
    fig.savefig(output_path, dpi=cfg.plot_dpi)
    plt.close(fig)


# =============================================================================
# Export continu par trajectoire
# =============================================================================

def export_continuous_for_trajectory(
    raw: dict,
    time: np.ndarray,
    arrays: dict[str, np.ndarray],
    residuals: dict[str, dict[str, Any]],
    source_json_path: str,
    cfg: Cfg,
) -> dict[str, Any]:
    file_name = raw.get("file") or os.path.basename(source_json_path)
    out_dirs = make_output_dirs(cfg, file_name)

    # -------------------------------------------------------------------------
    # Sélection des signaux sources à exporter/tracer
    # -------------------------------------------------------------------------
    source_series: dict[str, np.ndarray] = {}

    for name in cfg.source_channels_to_export:
        if name in arrays:
            source_series[name] = arrays[name]

    if cfg.export_derived_source_signals:
        for name in [
            "vehicle.v_xy_norm",
            "vehicle.a_xy_norm",
            "derived.dvx_dt",
            "derived.dvy_dt",
            "vehicle.yaw_rate_rad_s",
        ]:
            if name in arrays:
                source_series[name] = arrays[name]

    # -------------------------------------------------------------------------
    # CSV temporel complet : sources brutes + résidus filtrés
    # -------------------------------------------------------------------------
    ts_data: dict[str, np.ndarray] = {
        "time": np.asarray(time, dtype=np.float64),
    }

    for name, values in source_series.items():
        col = np.full(len(time), np.nan, dtype=np.float64)
        values = np.asarray(values, dtype=np.float64)
        m = min(len(time), len(values))
        col[:m] = values[:m]
        ts_data[f"source__{name}"] = col

    for name, payload in residuals.items():
        values = np.asarray(payload["values"], dtype=np.float64)
        col = np.full(len(time), np.nan, dtype=np.float64)
        m = min(len(time), len(values))
        col[:m] = values[:m]
        ts_data[f"residual__{name}"] = col

    df_ts = pd.DataFrame(ts_data)

    csv_path = os.path.join(out_dirs["timeseries"], "continuous_signals_and_residuals.csv")
    df_ts.to_csv(csv_path, index=False)

    # -------------------------------------------------------------------------
    # Plots sources brutes
    # -------------------------------------------------------------------------
    source_plot_paths = {}

    for name, values in source_series.items():
        plot_path = os.path.join(out_dirs["source_plots"], f"{safe_filename(name)}.png")

        plot_single_timeseries(
            time=time,
            values=values,
            name=name,
            output_path=plot_path,
            ylabel=name,
            title_extra="source signal raw",
            cfg=cfg,
            zero_line=False,
        )

        source_plot_paths[name] = plot_path

    # -------------------------------------------------------------------------
    # Plots résidus filtrés
    # -------------------------------------------------------------------------
    residual_plot_paths = {}

    for name, payload in residuals.items():
        plot_path = os.path.join(out_dirs["residual_plots"], f"{safe_filename(name)}.png")

        plot_single_timeseries(
            time=time,
            values=payload["values"],
            name=name,
            output_path=plot_path,
            ylabel=f"{name} [{payload.get('unit', '')}]",
            title_extra=payload.get("status", ""),
            cfg=cfg,
            zero_line=cfg.plot_zero_line,
        )

        residual_plot_paths[name] = plot_path

    # -------------------------------------------------------------------------
    # Overview sources
    # -------------------------------------------------------------------------
    overview_sources_names = [
        "vehicle.vx",
        "vehicle.vy",
        "vehicle.v_xy_norm",
        "vehicle.speed",
        "vehicle.ax",
        "vehicle.ay",
        "vehicle.a_xy_norm",
        "vehicle.yaw_rate",
        "vehicle.yaw_rate_rad_s",
        "derived.dvx_dt",
        "derived.dvy_dt",
        "imu.ax_body",
        "imu.ay_body",
        "STR_WHL_ANGLE (Degrees)",
        "WheelSteer_S1 (_)",
        "WheelSteer_S2 (_)",
    ]

    overview_sources = {
        name: arrays[name]
        for name in overview_sources_names
        if name in arrays
    }

    overview_sources_path = os.path.join(out_dirs["plots"], "overview_sources.png")

    plot_overview(
        time=time,
        series=overview_sources,
        output_path=overview_sources_path,
        title="Source signals over time",
        cfg=cfg,
        zero_line=False,
    )

    # -------------------------------------------------------------------------
    # Overview résidus
    # -------------------------------------------------------------------------
    overview_residuals = {
        name: payload["values"]
        for name, payload in residuals.items()
    }

    overview_residuals_path = os.path.join(out_dirs["plots"], "overview_residuals.png")

    plot_overview(
        time=time,
        series=overview_residuals,
        output_path=overview_residuals_path,
        title="Filtered residuals over time",
        cfg=cfg,
        zero_line=True,
    )

    # -------------------------------------------------------------------------
    # JSON résumé
    # -------------------------------------------------------------------------
    source_summary = {
        name: signal_summary(values)
        for name, values in source_series.items()
    }

    residual_summary = {
        name: {
            "status": payload.get("status"),
            "formula": payload.get("formula"),
            "unit": payload.get("unit"),
            "description": payload.get("description"),
            "finite_ratio": payload.get("finite_ratio"),
            "mean": payload.get("mean"),
            "std": payload.get("std"),
            "rms": payload.get("rms"),
            "max_abs": payload.get("max_abs"),
            "q95_abs": payload.get("q95_abs"),
        }
        for name, payload in residuals.items()
    }

    summary = {
        "schema_version": "continuous_signals_and_filtered_residuals.v2",
        "file": raw.get("file"),
        "filepath": raw.get("filepath"),
        "date": raw.get("date"),
        "source_json_path": source_json_path,
        "n_samples": int(len(time)),
        "time_start_sec": json_safe_scalar(time[0]) if len(time) else None,
        "time_end_sec": json_safe_scalar(time[-1]) if len(time) else None,
        "dt_median_sec": json_safe_scalar(estimate_dt(time)),
        "filtering": {
            "method": "savgol" if savgol_filter is not None else "moving_average_fallback",
            "residual_filter_sec": cfg.residual_filter_sec,
            "gps_filter_sec": cfg.gps_filter_sec,
            "savgol_polyorder": cfg.savgol_polyorder,
            "sources_are_raw": True,
        },
        "csv_path": csv_path,
        "overview_sources_plot": overview_sources_path,
        "overview_residuals_plot": overview_residuals_path,
        "source_plots": source_plot_paths,
        "residual_plots": residual_plot_paths,
        "source_summary": source_summary,
        "residual_summary": residual_summary,
    }

    summary_path = os.path.join(out_dirs["root"], "continuous_summary.json")

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    return {
        "trajectory_dir": out_dirs["root"],
        "csv_path": csv_path,
        "summary_path": summary_path,
        "overview_sources_plot": overview_sources_path,
        "overview_residuals_plot": overview_residuals_path,
        "n_source_series": len(source_series),
        "n_residuals": len(residuals),
    }


# =============================================================================
# Traitement fichier
# =============================================================================

def process_file(path: str, cfg: Cfg) -> dict[str, Any] | None:
    data = load_json_file(path)

    file_name = data.get("file", os.path.basename(path))
    time = to_float_array(get_time_values(data))

    if len(time) < 2:
        return None

    arrays = build_channel_arrays_from_json(data, time)

    if not arrays:
        return None

    min_len = min([len(time)] + [len(v) for v in arrays.values()])

    if min_len < 2:
        return None

    time = time[:min_len]
    arrays = {k: v[:min_len] for k, v in arrays.items()}

    if cfg.export_derived_source_signals:
        arrays = add_derived_source_signals(arrays, time)

    residuals = compute_residual_timeseries(arrays, time, cfg)

    export_info = export_continuous_for_trajectory(
        raw=data,
        time=time,
        arrays=arrays,
        residuals=residuals,
        source_json_path=path,
        cfg=cfg,
    )

    if cfg.verbose:
        print(
            f"[OK] {file_name}: "
            f"{export_info['n_source_series']} source series, "
            f"{export_info['n_residuals']} residuals"
        )

    return export_info


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    cfg = Cfg()

    json_files = sorted(glob.glob(os.path.join(cfg.input_dir, "*.json")))

    if not json_files:
        raise FileNotFoundError(f"No JSON files found in: {cfg.input_dir}")

    os.makedirs(cfg.output_root_dir, exist_ok=True)

    exports = []
    skipped = []

    for path in tqdm(json_files, desc="Exporting continuous sources and filtered residuals"):
        try:
            out = process_file(path, cfg)

            if out is not None:
                exports.append(out)
            else:
                skipped.append({
                    "path": path,
                    "reason": "process_file_returned_none",
                })

        except Exception as exc:
            skipped.append({
                "path": path,
                "reason": str(exc),
            })
            print(f"[SKIP] {path}: {exc}")

    global_summary = {
        "schema_version": "continuous_batch_summary.v2",
        "config": asdict(cfg),
        "filtering": {
            "method": "savgol" if savgol_filter is not None else "moving_average_fallback",
            "sources_are_raw": True,
        },
        "n_json_files": len(json_files),
        "n_exported": len(exports),
        "n_skipped": len(skipped),
        "exports": exports,
        "skipped": skipped,
    }

    global_summary_path = os.path.join(cfg.output_root_dir, "batch_summary.json")

    with open(global_summary_path, "w", encoding="utf-8") as f:
        json.dump(global_summary, f, indent=2, ensure_ascii=False)

    print("\nDone")
    print("JSON files found:", len(json_files))
    print("Exported trajectories:", len(exports))
    print("Skipped trajectories:", len(skipped))
    print("Output root:", cfg.output_root_dir)
    print("Batch summary:", global_summary_path)

    if savgol_filter is None:
        print("\n[WARN] scipy.signal.savgol_filter not available.")
        print("       Fallback used: moving average.")
        print("       To enable Savitzky-Golay filtering:")
        print("       pip install scipy")


if __name__ == "__main__":
    main()
