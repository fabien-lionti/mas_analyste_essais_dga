# # train_incremental_tcn_coherence.py
# from __future__ import annotations

# import argparse
# import json
# import random
# from dataclasses import dataclass
# from pathlib import Path
# from typing import Any

# import numpy as np
# import pandas as pd
# from tqdm.auto import tqdm

# import torch
# from torch import nn
# from torch.utils.data import DataLoader, Dataset

# from dxd_schema import get_resampled_channels, get_time_values


# # =============================================================================
# # CONFIG
# # =============================================================================

# DEFAULT_INPUT_DIR = Path("selected_dxd_json_resampled")
# DEFAULT_OUTPUT_DIR = Path("dynamic_channel_coherence_v1")

# STEER_CHANNELS = [
#     "WheelSteer_S1 (_)",
#     "WheelSteer_S2 (_)",
#     "WhlDirFl_D_Actl (-)",
#     "WhlDirFr_D_Actl (-)",
# ]

# # IMPORTANT :
# # vehicle.speed est volontairement retiré.
# BASE_CHANNELS = [
#     "vehicle.vx",
#     "vehicle.ax",
#     "vehicle.ay",
#     "vehicle.yaw_rate",
#     "gps_speed",
#     "steer",
# ]

# TARGET_CHANNELS = [
#     "vehicle.vx",
#     "vehicle.ax",
#     "vehicle.ay",
#     "vehicle.yaw_rate",
#     "gps_speed",
#     "steer",
# ]


# @dataclass
# class Config:
#     input_dir: Path = DEFAULT_INPUT_DIR
#     output_dir: Path = DEFAULT_OUTPUT_DIR

#     history_sec: float = 4.0
#     horizon_sec: float = 1.0
#     stride_sec: float = 0.5

#     initial_fraction: float = 0.2
#     batch_size_files: int = 10

#     epochs_initial: int = 20
#     epochs_update: int = 5
#     batch_size: int = 64
#     lr: float = 1e-3
#     weight_decay: float = 1e-5

#     hidden_channels: int = 64
#     num_tcn_blocks: int = 5
#     dropout: float = 0.05

#     memory_max_windows_per_target: int = 2000
#     memory_fraction: float = 0.30

#     max_windows_per_file: int | None = None
#     min_valid_ratio: float = 0.95

#     device: str = "cuda" if torch.cuda.is_available() else "cpu"
#     seed: int = 42


# # =============================================================================
# # UTILS
# # =============================================================================

# def set_seed(seed: int) -> None:
#     random.seed(seed)
#     np.random.seed(seed)
#     torch.manual_seed(seed)
#     torch.cuda.manual_seed_all(seed)


# def load_json(path: Path) -> dict[str, Any]:
#     with open(path, "r", encoding="utf-8") as f:
#         return json.load(f)


# def safe_stem(path: Path | str) -> str:
#     stem = Path(path).stem
#     return "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in stem)


# def arr(values: Any, n: int | None = None) -> np.ndarray:
#     x = np.asarray(values, dtype=float)
#     if n is None:
#         return x

#     out = np.full(n, np.nan, dtype=float)
#     m = min(n, len(x))

#     if m > 0:
#         out[:m] = x[:m]

#     return out


# def first_present(channels: dict[str, np.ndarray], names: list[str]) -> np.ndarray | None:
#     for name in names:
#         if name in channels:
#             return channels[name]
#     return None


# def derivative(x: np.ndarray, dt: float) -> np.ndarray:
#     out = np.full_like(x, np.nan, dtype=float)
#     valid = np.isfinite(x)

#     if np.sum(valid) < 2:
#         return out

#     idx = np.where(valid)[0]
#     out[idx] = np.gradient(x[idx], dt)

#     return out


# def gps_local_xy(
#     lat_deg: np.ndarray,
#     lon_deg: np.ndarray,
# ) -> tuple[np.ndarray, np.ndarray, str]:
#     lat = np.asarray(lat_deg, dtype=float)
#     lon = np.asarray(lon_deg, dtype=float)

#     valid = (
#         np.isfinite(lat)
#         & np.isfinite(lon)
#         & (np.abs(lat) <= 90)
#         & (np.abs(lon) <= 180)
#         & ~((np.abs(lat) < 1e-8) & (np.abs(lon) < 1e-8))
#     )

#     x = np.full_like(lat, np.nan, dtype=float)
#     y = np.full_like(lon, np.nan, dtype=float)

#     if np.sum(valid) < 2:
#         return x, y, "no_gps"

#     idx0 = np.where(valid)[0][0]
#     lat0 = np.deg2rad(lat[idx0])
#     lon0 = np.deg2rad(lon[idx0])
#     r = 6_371_000.0

#     x[valid] = r * np.cos(lat0) * (np.deg2rad(lon[valid]) - lon0)
#     y[valid] = r * (np.deg2rad(lat[valid]) - lat0)

#     return x, y, "ok"


# def robust_q95_abs(x: np.ndarray) -> float:
#     x = np.asarray(x, dtype=float)
#     x = x[np.isfinite(x)]

#     if len(x) == 0:
#         return float("nan")

#     return float(np.quantile(np.abs(x), 0.95))


# def robust_mae(x: np.ndarray) -> float:
#     x = np.asarray(x, dtype=float)
#     x = x[np.isfinite(x)]

#     if len(x) == 0:
#         return float("nan")

#     return float(np.mean(np.abs(x)))


# def robust_scale_from_errors(errors: np.ndarray, eps: float = 1e-8) -> float:
#     q95 = robust_q95_abs(errors)

#     if not np.isfinite(q95) or q95 < eps:
#         return 1.0

#     return float(q95 + eps)


# # =============================================================================
# # JSON READING + CANONICAL SIGNALS
# # =============================================================================

# def read_resampled_json(path: Path) -> tuple[dict[str, Any], np.ndarray, dict[str, np.ndarray]]:
#     raw = load_json(path)
#     time = arr(get_time_values(raw))
#     n = len(time)

#     channels: dict[str, np.ndarray] = {}

#     for name, payload in get_resampled_channels(raw).items():
#         if not isinstance(payload, dict) or "values" not in payload:
#             continue

#         canonical = payload.get("canonical_name") or name
#         values = arr(payload["values"], n)

#         channels[canonical] = values
#         channels[name] = values

#     return raw, time, channels


# def build_model_channels(
#     time: np.ndarray,
#     channels: dict[str, np.ndarray],
# ) -> dict[str, np.ndarray]:
#     n = len(time)
#     out: dict[str, np.ndarray] = {}

#     for name in [
#         "vehicle.vx",
#         "vehicle.ax",
#         "vehicle.ay",
#         "vehicle.yaw_rate",
#     ]:
#         if name in channels:
#             out[name] = channels[name].astype(float)
#         else:
#             out[name] = np.full(n, np.nan, dtype=float)

#     steer = first_present(channels, STEER_CHANNELS)
#     if steer is None:
#         steer = np.full(n, np.nan, dtype=float)

#     out["steer"] = steer.astype(float)

#     gps_speed = np.full(n, np.nan, dtype=float)

#     lat = channels.get("gps.latitude")
#     lon = channels.get("gps.longitude")

#     if lat is not None and lon is not None and len(time) >= 2:
#         dt = float(np.nanmedian(np.diff(time)))

#         if np.isfinite(dt) and dt > 0:
#             gx, gy, status = gps_local_xy(lat, lon)

#             if status == "ok":
#                 gps_speed = np.sqrt(
#                     derivative(gx, dt) ** 2
#                     + derivative(gy, dt) ** 2
#                 )

#     out["gps_speed"] = gps_speed

#     return out


# def get_file_date(raw: dict[str, Any], path: Path) -> str:
#     date = raw.get("date") or raw.get("modified_at")

#     if date is None:
#         return path.name

#     return str(date)


# # =============================================================================
# # STANDARDIZATION
# # =============================================================================

# @dataclass
# class Standardizer:
#     mean: dict[str, float]
#     std: dict[str, float]

#     def transform(self, name: str, x: np.ndarray) -> np.ndarray:
#         m = self.mean.get(name, 0.0)
#         s = self.std.get(name, 1.0)
#         return (x - m) / s

#     def inverse(self, name: str, x: np.ndarray) -> np.ndarray:
#         m = self.mean.get(name, 0.0)
#         s = self.std.get(name, 1.0)
#         return x * s + m


# def fit_standardizer(files: list[Path]) -> Standardizer:
#     values: dict[str, list[np.ndarray]] = {name: [] for name in BASE_CHANNELS}

#     for path in tqdm(files, desc="Fitting standardizer", unit="file"):
#         try:
#             _, time, channels = read_resampled_json(path)
#             model_channels = build_model_channels(time, channels)

#             for name in BASE_CHANNELS:
#                 x = model_channels[name]
#                 x = x[np.isfinite(x)]

#                 if len(x) > 0:
#                     values[name].append(x)

#         except Exception as exc:
#             print(f"[WARN] standardizer failed on {path.name}: {exc}")

#     mean: dict[str, float] = {}
#     std: dict[str, float] = {}

#     for name in BASE_CHANNELS:
#         if values[name]:
#             x = np.concatenate(values[name])
#             mean[name] = float(np.mean(x))

#             s = float(np.std(x))
#             std[name] = s if np.isfinite(s) and s > 1e-8 else 1.0
#         else:
#             mean[name] = 0.0
#             std[name] = 1.0

#     return Standardizer(mean=mean, std=std)


# # =============================================================================
# # WINDOW DATASET
# # =============================================================================

# @dataclass
# class WindowRecord:
#     json_name: str
#     date: str
#     start_idx: int
#     input_array: np.ndarray
#     target_array: np.ndarray
#     time_target: np.ndarray


# class CoherenceWindowDataset(Dataset):
#     def __init__(self, records: list[WindowRecord]) -> None:
#         self.records = records

#     def __len__(self) -> int:
#         return len(self.records)

#     def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
#         r = self.records[idx]

#         x = torch.tensor(r.input_array, dtype=torch.float32)
#         y = torch.tensor(r.target_array, dtype=torch.float32)

#         return x, y


# def build_windows_for_file(
#     path: Path,
#     target_name: str,
#     input_names: list[str],
#     standardizer: Standardizer,
#     cfg: Config,
# ) -> list[WindowRecord]:
#     raw, time, channels = read_resampled_json(path)
#     model_channels = build_model_channels(time, channels)

#     if len(time) < 3:
#         return []

#     dt = float(np.nanmedian(np.diff(time)))

#     if not np.isfinite(dt) or dt <= 0:
#         return []

#     history_len = max(2, int(round(cfg.history_sec / dt)))
#     horizon_len = max(1, int(round(cfg.horizon_sec / dt)))
#     stride_len = max(1, int(round(cfg.stride_sec / dt)))

#     n = len(time)
#     total_len = history_len + horizon_len

#     if n < total_len:
#         return []

#     date = get_file_date(raw, path)

#     arrays: dict[str, np.ndarray] = {}
#     for name in BASE_CHANNELS:
#         arrays[name] = standardizer.transform(name, model_channels[name]).astype(np.float32)

#     records: list[WindowRecord] = []

#     starts = list(range(0, n - total_len + 1, stride_len))

#     if cfg.max_windows_per_file is not None and len(starts) > cfg.max_windows_per_file:
#         starts = random.sample(starts, cfg.max_windows_per_file)
#         starts.sort()

#     for s in starts:
#         hist_slice = slice(s, s + history_len)
#         fut_slice = slice(s + history_len, s + history_len + horizon_len)

#         input_mat = np.stack(
#             [arrays[name][hist_slice] for name in input_names],
#             axis=0,
#         )

#         target_vec = arrays[target_name][fut_slice][None, :]

#         valid_ratio = (
#             np.isfinite(input_mat).mean() * 0.5
#             + np.isfinite(target_vec).mean() * 0.5
#         )

#         if valid_ratio < cfg.min_valid_ratio:
#             continue

#         input_mat = np.nan_to_num(input_mat, nan=0.0, posinf=0.0, neginf=0.0)
#         target_vec = np.nan_to_num(target_vec, nan=0.0, posinf=0.0, neginf=0.0)

#         records.append(
#             WindowRecord(
#                 json_name=path.name,
#                 date=date,
#                 start_idx=s,
#                 input_array=input_mat.astype(np.float32),
#                 target_array=target_vec.astype(np.float32),
#                 time_target=time[fut_slice].astype(float),
#             )
#         )

#     return records


# def build_windows_for_files(
#     files: list[Path],
#     target_name: str,
#     standardizer: Standardizer,
#     cfg: Config,
#     desc: str | None = None,
# ) -> list[WindowRecord]:
#     input_names = [name for name in BASE_CHANNELS if name != target_name]
#     records: list[WindowRecord] = []

#     iterator = tqdm(
#         files,
#         desc=desc or f"Building windows {target_name}",
#         unit="file",
#         leave=False,
#     )

#     for path in iterator:
#         try:
#             file_records = build_windows_for_file(
#                 path=path,
#                 target_name=target_name,
#                 input_names=input_names,
#                 standardizer=standardizer,
#                 cfg=cfg,
#             )
#             records.extend(file_records)
#             iterator.set_postfix(windows=len(records))

#         except Exception as exc:
#             print(f"[WARN] windows failed on {path.name} target={target_name}: {exc}")

#     return records


# # =============================================================================
# # TCN MODEL
# # =============================================================================

# class Chomp1d(nn.Module):
#     def __init__(self, chomp_size: int) -> None:
#         super().__init__()
#         self.chomp_size = chomp_size

#     def forward(self, x: torch.Tensor) -> torch.Tensor:
#         if self.chomp_size == 0:
#             return x
#         return x[:, :, :-self.chomp_size]


# class TemporalBlock(nn.Module):
#     def __init__(
#         self,
#         in_channels: int,
#         out_channels: int,
#         kernel_size: int,
#         dilation: int,
#         dropout: float,
#     ) -> None:
#         super().__init__()

#         padding = (kernel_size - 1) * dilation

#         self.net = nn.Sequential(
#             nn.Conv1d(
#                 in_channels,
#                 out_channels,
#                 kernel_size=kernel_size,
#                 padding=padding,
#                 dilation=dilation,
#             ),
#             Chomp1d(padding),
#             nn.GELU(),
#             nn.Dropout(dropout),
#             nn.Conv1d(
#                 out_channels,
#                 out_channels,
#                 kernel_size=kernel_size,
#                 padding=padding,
#                 dilation=dilation,
#             ),
#             Chomp1d(padding),
#             nn.GELU(),
#             nn.Dropout(dropout),
#         )

#         self.downsample = (
#             nn.Conv1d(in_channels, out_channels, kernel_size=1)
#             if in_channels != out_channels
#             else nn.Identity()
#         )

#     def forward(self, x: torch.Tensor) -> torch.Tensor:
#         return self.net(x) + self.downsample(x)


# class TCNForecaster(nn.Module):
#     def __init__(
#         self,
#         input_channels: int,
#         hidden_channels: int,
#         num_blocks: int,
#         horizon_len: int,
#         dropout: float,
#     ) -> None:
#         super().__init__()

#         blocks: list[nn.Module] = []
#         c_in = input_channels

#         for i in range(num_blocks):
#             dilation = 2 ** i
#             blocks.append(
#                 TemporalBlock(
#                     in_channels=c_in,
#                     out_channels=hidden_channels,
#                     kernel_size=3,
#                     dilation=dilation,
#                     dropout=dropout,
#                 )
#             )
#             c_in = hidden_channels

#         self.tcn = nn.Sequential(*blocks)

#         self.head = nn.Sequential(
#             nn.AdaptiveAvgPool1d(1),
#             nn.Flatten(),
#             nn.Linear(hidden_channels, hidden_channels),
#             nn.GELU(),
#             nn.Linear(hidden_channels, horizon_len),
#         )

#     def forward(self, x: torch.Tensor) -> torch.Tensor:
#         h = self.tcn(x)
#         y = self.head(h)
#         return y[:, None, :]


# def infer_horizon_len(records: list[WindowRecord]) -> int:
#     if not records:
#         raise ValueError("Cannot infer horizon length from empty records")

#     return int(records[0].target_array.shape[-1])


# # =============================================================================
# # TRAIN / EVAL
# # =============================================================================

# def train_model(
#     model: nn.Module,
#     records: list[WindowRecord],
#     cfg: Config,
#     epochs: int,
#     desc: str,
# ) -> None:
#     if not records:
#         return

#     dataset = CoherenceWindowDataset(records)

#     loader = DataLoader(
#         dataset,
#         batch_size=cfg.batch_size,
#         shuffle=True,
#         drop_last=False,
#     )

#     model.train()

#     opt = torch.optim.AdamW(
#         model.parameters(),
#         lr=cfg.lr,
#         weight_decay=cfg.weight_decay,
#     )

#     loss_fn = nn.HuberLoss(delta=1.0)

#     epoch_bar = tqdm(range(epochs), desc=desc, unit="epoch", leave=False)

#     for _ in epoch_bar:
#         losses = []

#         batch_bar = tqdm(loader, desc="train batches", unit="batch", leave=False)

#         for xb, yb in batch_bar:
#             xb = xb.to(cfg.device)
#             yb = yb.to(cfg.device)

#             pred = model(xb)
#             loss = loss_fn(pred, yb)

#             opt.zero_grad(set_to_none=True)
#             loss.backward()
#             nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
#             opt.step()

#             loss_value = float(loss.detach().cpu())
#             losses.append(loss_value)

#             batch_bar.set_postfix(loss=f"{loss_value:.4g}")

#         if losses:
#             epoch_bar.set_postfix(loss=f"{np.mean(losses):.4g}")


# @torch.no_grad()
# def predict_records(
#     model: nn.Module,
#     records: list[WindowRecord],
#     target_name: str,
#     standardizer: Standardizer,
#     cfg: Config,
#     phase: str,
#     error_scale: float,
#     desc: str,
# ) -> tuple[pd.DataFrame, dict[str, float]]:
#     if not records:
#         empty = pd.DataFrame()
#         metrics = {
#             "mae": float("nan"),
#             "q95_abs_error": float("nan"),
#             "mean_score": float("nan"),
#             "q95_score": float("nan"),
#         }
#         return empty, metrics

#     dataset = CoherenceWindowDataset(records)

#     loader = DataLoader(
#         dataset,
#         batch_size=cfg.batch_size,
#         shuffle=False,
#         drop_last=False,
#     )

#     model.eval()

#     rows: list[dict[str, Any]] = []
#     all_errors: list[float] = []

#     offset = 0

#     batch_bar = tqdm(loader, desc=desc, unit="batch", leave=False)

#     for xb, yb in batch_bar:
#         xb = xb.to(cfg.device)
#         pred = model(xb).cpu().numpy()
#         true = yb.numpy()

#         bsz = true.shape[0]

#         for i in range(bsz):
#             r = records[offset + i]

#             y_true_std = true[i, 0]
#             y_pred_std = pred[i, 0]

#             y_true = standardizer.inverse(target_name, y_true_std)
#             y_pred = standardizer.inverse(target_name, y_pred_std)

#             err = y_true - y_pred
#             all_errors.extend(err[np.isfinite(err)].tolist())

#             score = np.abs(err) / error_scale

#             for j in range(len(y_true)):
#                 rows.append(
#                     {
#                         "json_name": r.json_name,
#                         "date": r.date,
#                         "start_idx": int(r.start_idx),
#                         "time": float(r.time_target[j]),
#                         "target_name": target_name,
#                         "phase": phase,
#                         "y_true": float(y_true[j]),
#                         "y_pred": float(y_pred[j]),
#                         "error": float(err[j]),
#                         "abs_error": float(abs(err[j])),
#                         "score": float(score[j]),
#                     }
#                 )

#         offset += bsz
#         batch_bar.set_postfix(rows=len(rows))

#     errors = np.asarray(all_errors, dtype=float)

#     metrics = {
#         "mae": robust_mae(errors),
#         "q95_abs_error": robust_q95_abs(errors),
#         "mean_score": float(np.nanmean(np.abs(errors) / error_scale))
#         if np.any(np.isfinite(errors))
#         else float("nan"),
#         "q95_score": robust_q95_abs(errors / error_scale),
#     }

#     return pd.DataFrame(rows), metrics


# def update_memory(
#     memory: list[WindowRecord],
#     new_records: list[WindowRecord],
#     cfg: Config,
# ) -> list[WindowRecord]:
#     if not new_records:
#         return memory

#     memory = list(memory)

#     n_add = min(len(new_records), cfg.memory_max_windows_per_target)
#     selected = random.sample(new_records, n_add) if len(new_records) > n_add else new_records

#     memory.extend(selected)

#     if len(memory) > cfg.memory_max_windows_per_target:
#         memory = random.sample(memory, cfg.memory_max_windows_per_target)

#     return memory


# def mix_current_and_memory(
#     current: list[WindowRecord],
#     memory: list[WindowRecord],
#     cfg: Config,
# ) -> list[WindowRecord]:
#     if not memory or cfg.memory_fraction <= 0:
#         return current

#     n_mem = int(
#         round(
#             len(current)
#             * cfg.memory_fraction
#             / max(1e-8, 1.0 - cfg.memory_fraction)
#         )
#     )

#     n_mem = min(n_mem, len(memory))

#     mem_sample = random.sample(memory, n_mem) if len(memory) > n_mem else memory

#     return list(current) + list(mem_sample)


# # =============================================================================
# # PLOTS
# # =============================================================================

# def import_plt():
#     import matplotlib
#     matplotlib.use("Agg")
#     import matplotlib.pyplot as plt
#     return plt


# def plot_batch_metrics(metrics_df: pd.DataFrame, out_dir: Path) -> None:
#     if metrics_df.empty:
#         return

#     plt = import_plt()
#     out_dir.mkdir(parents=True, exist_ok=True)

#     for target_name, df_t in tqdm(
#         metrics_df.groupby("target_name"),
#         desc="Plot batch metrics",
#         unit="target",
#     ):
#         df_t = df_t.sort_values("batch_id")

#         fig, ax = plt.subplots(figsize=(12, 5))

#         pre = df_t[df_t["phase"] == "pre"]
#         post = df_t[df_t["phase"] == "post"]

#         if not pre.empty:
#             ax.plot(
#                 pre["batch_id"],
#                 pre["q95_abs_error"],
#                 marker="o",
#                 label="pre q95 abs error",
#             )

#         if not post.empty:
#             ax.plot(
#                 post["batch_id"],
#                 post["q95_abs_error"],
#                 marker="o",
#                 label="post q95 abs error",
#             )

#         ax.set_title(f"Erreur q95 pré/post — {target_name}")
#         ax.set_xlabel("batch chronologique")
#         ax.set_ylabel("q95 erreur absolue")
#         ax.grid(alpha=0.3)
#         ax.legend()

#         fig.tight_layout()
#         fig.savefig(out_dir / f"batch_q95__{safe_stem(target_name)}.png", dpi=160)
#         plt.close(fig)


# def plot_prediction_examples(
#     pred_df: pd.DataFrame,
#     out_dir: Path,
#     max_files: int = 5,
# ) -> None:
#     if pred_df.empty:
#         return

#     plt = import_plt()
#     out_dir.mkdir(parents=True, exist_ok=True)

#     grouped = list(pred_df.groupby("target_name"))

#     for target_name, df_t in tqdm(
#         grouped,
#         desc="Plot prediction examples",
#         unit="target",
#     ):
#         json_names = list(df_t["json_name"].dropna().unique())[:max_files]

#         for json_name in json_names:
#             df_f = df_t[df_t["json_name"] == json_name].copy()

#             if df_f.empty:
#                 continue

#             agg = (
#                 df_f.groupby(["phase", "time"], as_index=False)
#                 .agg(
#                     y_true=("y_true", "mean"),
#                     y_pred=("y_pred", "mean"),
#                     score=("score", "mean"),
#                     abs_error=("abs_error", "mean"),
#                 )
#                 .sort_values("time")
#             )

#             fig, ax = plt.subplots(figsize=(12, 5))

#             pre = agg[agg["phase"] == "pre"]
#             post = agg[agg["phase"] == "post"]

#             if not pre.empty:
#                 ax.plot(pre["time"], pre["y_true"], linewidth=1.0, label="true")
#                 ax.plot(pre["time"], pre["y_pred"], linewidth=1.0, label="pred pre")

#             if not post.empty:
#                 ax.plot(post["time"], post["y_pred"], linewidth=1.0, label="pred post")

#             ax.set_title(f"{target_name} — {json_name}")
#             ax.set_xlabel("temps (s)")
#             ax.set_ylabel(target_name)
#             ax.grid(alpha=0.3)
#             ax.legend()

#             fig.tight_layout()
#             fig.savefig(
#                 out_dir / f"pred__{safe_stem(target_name)}__{safe_stem(json_name)}.png",
#                 dpi=160,
#             )
#             plt.close(fig)


# # =============================================================================
# # INCREMENTAL PIPELINE
# # =============================================================================

# def split_chronological_batches(files: list[Path], cfg: Config) -> list[list[Path]]:
#     dated: list[tuple[str, Path]] = []

#     for path in tqdm(files, desc="Sorting files chronologically", unit="file"):
#         try:
#             raw = load_json(path)
#             date = get_file_date(raw, path)
#         except Exception:
#             date = path.name

#         dated.append((date, path))

#     dated.sort(key=lambda x: (x[0], x[1].name))
#     sorted_files = [p for _, p in dated]

#     if len(sorted_files) == 0:
#         return []

#     n_initial = max(1, int(round(len(sorted_files) * cfg.initial_fraction)))

#     initial = sorted_files[:n_initial]
#     rest = sorted_files[n_initial:]

#     batches = [initial]

#     for i in range(0, len(rest), cfg.batch_size_files):
#         batches.append(rest[i : i + cfg.batch_size_files])

#     return [b for b in batches if b]


# def get_date_min_max(files: list[Path]) -> tuple[str, str]:
#     dates = []

#     for p in files:
#         try:
#             dates.append(get_file_date(load_json(p), p))
#         except Exception:
#             dates.append(p.name)

#     return min(dates), max(dates)


# def run_for_target(
#     target_name: str,
#     batches: list[list[Path]],
#     standardizer: Standardizer,
#     cfg: Config,
# ) -> tuple[pd.DataFrame, pd.DataFrame]:
#     print()
#     print("=" * 80)
#     print(f"TARGET: {target_name}")
#     print("=" * 80)

#     input_names = [name for name in BASE_CHANNELS if name != target_name]
#     print(f"Inputs: {input_names}")

#     initial_files = batches[0]

#     initial_records = build_windows_for_files(
#         files=initial_files,
#         target_name=target_name,
#         standardizer=standardizer,
#         cfg=cfg,
#         desc=f"Initial windows {target_name}",
#     )

#     if not initial_records:
#         print(f"[WARN] no initial records for target {target_name}")
#         return pd.DataFrame(), pd.DataFrame()

#     horizon_len = infer_horizon_len(initial_records)

#     model = TCNForecaster(
#         input_channels=len(input_names),
#         hidden_channels=cfg.hidden_channels,
#         num_blocks=cfg.num_tcn_blocks,
#         horizon_len=horizon_len,
#         dropout=cfg.dropout,
#     ).to(cfg.device)

#     print(f"Initial windows: {len(initial_records)}")

#     train_model(
#         model=model,
#         records=initial_records,
#         cfg=cfg,
#         epochs=cfg.epochs_initial,
#         desc=f"Initial train {target_name}",
#     )

#     init_pred_df, init_metrics = predict_records(
#         model=model,
#         records=initial_records,
#         target_name=target_name,
#         standardizer=standardizer,
#         cfg=cfg,
#         phase="initial",
#         error_scale=1.0,
#         desc=f"Initial eval {target_name}",
#     )

#     if not init_pred_df.empty:
#         initial_scale = robust_scale_from_errors(init_pred_df["error"].to_numpy())
#     else:
#         initial_scale = 1.0

#     memory: list[WindowRecord] = update_memory([], initial_records, cfg)

#     all_pred_dfs: list[pd.DataFrame] = []
#     metric_rows: list[dict[str, Any]] = []

#     date_min, date_max = get_date_min_max(initial_files)

#     metric_rows.append(
#         {
#             "batch_id": 0,
#             "target_name": target_name,
#             "phase": "initial",
#             "n_files": len(initial_files),
#             "n_windows": len(initial_records),
#             "date_min": date_min,
#             "date_max": date_max,
#             "mae": init_metrics["mae"],
#             "q95_abs_error": init_metrics["q95_abs_error"],
#             "mean_score": init_metrics["mean_score"],
#             "q95_score": init_metrics["q95_score"],
#             "adaptation_gain_q95": float("nan"),
#             "forgetting_q95": float("nan"),
#         }
#     )

#     batch_iterator = tqdm(
#         list(enumerate(batches[1:], start=1)),
#         desc=f"Incremental batches {target_name}",
#         unit="batch",
#     )

#     for batch_id, files in batch_iterator:
#         records = build_windows_for_files(
#             files=files,
#             target_name=target_name,
#             standardizer=standardizer,
#             cfg=cfg,
#             desc=f"Windows {target_name} batch {batch_id}",
#         )

#         if not records:
#             print(f"[WARN] no records for batch {batch_id}, target={target_name}")
#             continue

#         date_min, date_max = get_date_min_max(files)

#         pre_df, pre_metrics = predict_records(
#             model=model,
#             records=records,
#             target_name=target_name,
#             standardizer=standardizer,
#             cfg=cfg,
#             phase="pre",
#             error_scale=initial_scale,
#             desc=f"Pre eval {target_name} batch {batch_id}",
#         )

#         pre_df["batch_id"] = batch_id
#         all_pred_dfs.append(pre_df)

#         _, mem_before = predict_records(
#             model=model,
#             records=memory,
#             target_name=target_name,
#             standardizer=standardizer,
#             cfg=cfg,
#             phase="memory_before",
#             error_scale=initial_scale,
#             desc=f"Memory before {target_name} batch {batch_id}",
#         )

#         train_records = mix_current_and_memory(records, memory, cfg)

#         train_model(
#             model=model,
#             records=train_records,
#             cfg=cfg,
#             epochs=cfg.epochs_update,
#             desc=f"Update train {target_name} batch {batch_id}",
#         )

#         post_df, post_metrics = predict_records(
#             model=model,
#             records=records,
#             target_name=target_name,
#             standardizer=standardizer,
#             cfg=cfg,
#             phase="post",
#             error_scale=initial_scale,
#             desc=f"Post eval {target_name} batch {batch_id}",
#         )

#         post_df["batch_id"] = batch_id
#         all_pred_dfs.append(post_df)

#         _, mem_after = predict_records(
#             model=model,
#             records=memory,
#             target_name=target_name,
#             standardizer=standardizer,
#             cfg=cfg,
#             phase="memory_after",
#             error_scale=initial_scale,
#             desc=f"Memory after {target_name} batch {batch_id}",
#         )

#         forgetting = mem_after["q95_abs_error"] - mem_before["q95_abs_error"]
#         adaptation_gain = pre_metrics["q95_abs_error"] - post_metrics["q95_abs_error"]

#         metric_rows.append(
#             {
#                 "batch_id": batch_id,
#                 "target_name": target_name,
#                 "phase": "pre",
#                 "n_files": len(files),
#                 "n_windows": len(records),
#                 "date_min": date_min,
#                 "date_max": date_max,
#                 "mae": pre_metrics["mae"],
#                 "q95_abs_error": pre_metrics["q95_abs_error"],
#                 "mean_score": pre_metrics["mean_score"],
#                 "q95_score": pre_metrics["q95_score"],
#                 "adaptation_gain_q95": adaptation_gain,
#                 "forgetting_q95": forgetting,
#             }
#         )

#         metric_rows.append(
#             {
#                 "batch_id": batch_id,
#                 "target_name": target_name,
#                 "phase": "post",
#                 "n_files": len(files),
#                 "n_windows": len(records),
#                 "date_min": date_min,
#                 "date_max": date_max,
#                 "mae": post_metrics["mae"],
#                 "q95_abs_error": post_metrics["q95_abs_error"],
#                 "mean_score": post_metrics["mean_score"],
#                 "q95_score": post_metrics["q95_score"],
#                 "adaptation_gain_q95": adaptation_gain,
#                 "forgetting_q95": forgetting,
#             }
#         )

#         memory = update_memory(memory, records, cfg)

#         batch_iterator.set_postfix(
#             pre=f"{pre_metrics['q95_abs_error']:.4g}",
#             post=f"{post_metrics['q95_abs_error']:.4g}",
#             gain=f"{adaptation_gain:.4g}",
#             forgetting=f"{forgetting:.4g}",
#         )

#     pred_df = pd.concat(all_pred_dfs, ignore_index=True) if all_pred_dfs else pd.DataFrame()
#     metrics_df = pd.DataFrame(metric_rows)

#     return pred_df, metrics_df


# def main() -> None:
#     parser = argparse.ArgumentParser(
#         description="TCN incrémental de cohérence inter-canaux sans CNN, sans vehicle.speed."
#     )

#     parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
#     parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)

#     parser.add_argument("--history-sec", type=float, default=4.0)
#     parser.add_argument("--horizon-sec", type=float, default=1.0)
#     parser.add_argument("--stride-sec", type=float, default=0.5)

#     parser.add_argument("--initial-fraction", type=float, default=0.2)
#     parser.add_argument("--batch-size-files", type=int, default=10)

#     parser.add_argument("--epochs-initial", type=int, default=20)
#     parser.add_argument("--epochs-update", type=int, default=5)
#     parser.add_argument("--batch-size", type=int, default=64)
#     parser.add_argument("--lr", type=float, default=1e-3)

#     parser.add_argument("--hidden-channels", type=int, default=64)
#     parser.add_argument("--num-tcn-blocks", type=int, default=5)
#     parser.add_argument("--dropout", type=float, default=0.05)

#     parser.add_argument("--memory-max-windows", type=int, default=2000)
#     parser.add_argument("--memory-fraction", type=float, default=0.30)

#     parser.add_argument("--max-windows-per-file", type=int, default=None)
#     parser.add_argument("--seed", type=int, default=42)

#     parser.add_argument(
#         "--targets",
#         nargs="*",
#         default=TARGET_CHANNELS,
#         help=f"Cibles à entraîner. Défaut: {TARGET_CHANNELS}",
#     )

#     args = parser.parse_args()

#     cfg = Config(
#         input_dir=args.input_dir,
#         output_dir=args.output_dir,
#         history_sec=args.history_sec,
#         horizon_sec=args.horizon_sec,
#         stride_sec=args.stride_sec,
#         initial_fraction=args.initial_fraction,
#         batch_size_files=args.batch_size_files,
#         epochs_initial=args.epochs_initial,
#         epochs_update=args.epochs_update,
#         batch_size=args.batch_size,
#         lr=args.lr,
#         hidden_channels=args.hidden_channels,
#         num_tcn_blocks=args.num_tcn_blocks,
#         dropout=args.dropout,
#         memory_max_windows_per_target=args.memory_max_windows,
#         memory_fraction=args.memory_fraction,
#         max_windows_per_file=args.max_windows_per_file,
#         seed=args.seed,
#     )

#     set_seed(cfg.seed)

#     cfg.output_dir.mkdir(parents=True, exist_ok=True)
#     (cfg.output_dir / "plots").mkdir(parents=True, exist_ok=True)

#     files = sorted(cfg.input_dir.glob("*.json"))

#     if not files:
#         raise FileNotFoundError(f"No JSON found in {cfg.input_dir}")

#     print(f"Input dir: {cfg.input_dir.resolve()}")
#     print(f"Output dir: {cfg.output_dir.resolve()}")
#     print(f"Files found: {len(files)}")
#     print(f"Device: {cfg.device}")
#     print(f"Channels used: {BASE_CHANNELS}")
#     print("vehicle.speed is NOT used.")

#     batches = split_chronological_batches(files, cfg)

#     print(f"Chronological batches: {len(batches)}")
#     for i, b in enumerate(batches):
#         print(f"  batch {i}: {len(b)} files")

#     print("Fitting global standardizer...")
#     standardizer = fit_standardizer(files)

#     with open(cfg.output_dir / "standardizer.json", "w", encoding="utf-8") as f:
#         json.dump(
#             {
#                 "mean": standardizer.mean,
#                 "std": standardizer.std,
#                 "channels": BASE_CHANNELS,
#                 "note": "vehicle.speed removed",
#             },
#             f,
#             indent=2,
#             ensure_ascii=False,
#         )

#     all_pred_dfs: list[pd.DataFrame] = []
#     all_metrics_dfs: list[pd.DataFrame] = []

#     target_iterator = tqdm(args.targets, desc="Targets", unit="target")

#     for target_name in target_iterator:
#         if target_name not in BASE_CHANNELS:
#             print(f"[WARN] unknown target ignored: {target_name}")
#             continue

#         target_iterator.set_postfix(target=target_name)

#         pred_df, metrics_df = run_for_target(
#             target_name=target_name,
#             batches=batches,
#             standardizer=standardizer,
#             cfg=cfg,
#         )

#         if not pred_df.empty:
#             all_pred_dfs.append(pred_df)

#         if not metrics_df.empty:
#             all_metrics_dfs.append(metrics_df)

#     predictions = (
#         pd.concat(all_pred_dfs, ignore_index=True)
#         if all_pred_dfs
#         else pd.DataFrame()
#     )

#     metrics = (
#         pd.concat(all_metrics_dfs, ignore_index=True)
#         if all_metrics_dfs
#         else pd.DataFrame()
#     )

#     predictions_path = cfg.output_dir / "predictions.csv"
#     metrics_path = cfg.output_dir / "batch_metrics.csv"

#     predictions.to_csv(predictions_path, index=False)
#     metrics.to_csv(metrics_path, index=False)

#     plot_batch_metrics(metrics, cfg.output_dir / "plots" / "batch_metrics")
#     plot_prediction_examples(predictions, cfg.output_dir / "plots" / "predictions")

#     summary = {
#         "n_files": len(files),
#         "n_batches": len(batches),
#         "targets": args.targets,
#         "base_channels": BASE_CHANNELS,
#         "removed_channels": ["vehicle.speed"],
#         "history_sec": cfg.history_sec,
#         "horizon_sec": cfg.horizon_sec,
#         "stride_sec": cfg.stride_sec,
#         "device": cfg.device,
#         "outputs": {
#             "predictions": str(predictions_path),
#             "batch_metrics": str(metrics_path),
#             "plots": str(cfg.output_dir / "plots"),
#             "standardizer": str(cfg.output_dir / "standardizer.json"),
#         },
#     }

#     with open(cfg.output_dir / "summary.json", "w", encoding="utf-8") as f:
#         json.dump(summary, f, indent=2, ensure_ascii=False)

#     print()
#     print("Done.")
#     print(f"Wrote: {predictions_path}")
#     print(f"Wrote: {metrics_path}")
#     print(f"Wrote: {cfg.output_dir / 'summary.json'}")
#     print(f"Wrote plots in: {cfg.output_dir / 'plots'}")


# if __name__ == "__main__":
#     main()

# train_incremental_tcn_ensemble_coherence.py
from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from tqdm.auto import tqdm

import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

from dxd_schema import get_resampled_channels, get_time_values


# =============================================================================
# CONFIG
# =============================================================================

DEFAULT_INPUT_DIR = Path("selected_dxd_json_resampled")
DEFAULT_OUTPUT_DIR = Path("dynamic_channel_coherence_ensemble_v1")

STEER_CHANNELS = [
    "WheelSteer_S1 (_)",
    "WheelSteer_S2 (_)",
    "WhlDirFl_D_Actl (-)",
    "WhlDirFr_D_Actl (-)",
]

# vehicle.speed volontairement supprimé.
BASE_CHANNELS = [
    "vehicle.vx",
    "vehicle.ax",
    "vehicle.ay",
    "vehicle.yaw_rate",
    "gps_speed",
    "steer",
    "steer_s1",
    "steer_s2",
]

# Par défaut, gps_speed n'est pas target, mais reste utilisé comme entrée.
DEFAULT_TARGETS = [
    "vehicle.vx",
    "vehicle.ax",
    "vehicle.ay",
    "vehicle.yaw_rate",
    "steer_s1",
    "steer_s2",
]


def input_channels_for_target(target_name: str) -> list[str]:
    if target_name == "steer":
        excluded = {"steer", "steer_s1", "steer_s2"}
    elif target_name == "steer_s1":
        excluded = {"steer", "steer_s1"}
    elif target_name == "steer_s2":
        excluded = {"steer", "steer_s2"}
    else:
        excluded = {target_name}
    return [name for name in BASE_CHANNELS if name not in excluded]


@dataclass
class Config:
    input_dir: Path = DEFAULT_INPUT_DIR
    output_dir: Path = DEFAULT_OUTPUT_DIR

    history_sec: float = 4.0
    horizon_sec: float = 1.0
    stride_sec: float = 0.5

    initial_fraction: float = 0.2
    holdout_fraction: float = 0.2
    batch_size_files: int = 10

    epochs_initial: int = 20
    epochs_update: int = 5
    batch_size: int = 64
    lr: float = 1e-3
    weight_decay: float = 1e-5

    hidden_channels: int = 64
    num_tcn_blocks: int = 5
    dropout: float = 0.05

    ensemble_size: int = 3

    memory_max_windows_per_target: int = 2000
    memory_fraction: float = 0.30

    max_windows_per_file: int | None = None
    min_valid_ratio: float = 0.95

    time_bin_minutes: int = 60

    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    seed: int = 42


# =============================================================================
# UTILS
# =============================================================================

def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def load_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def safe_stem(path: Path | str) -> str:
    stem = Path(path).stem
    return "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in stem)


def arr(values: Any, n: int | None = None) -> np.ndarray:
    x = np.asarray(values, dtype=float)

    if n is None:
        return x

    out = np.full(n, np.nan, dtype=float)
    m = min(n, len(x))

    if m > 0:
        out[:m] = x[:m]

    return out


def first_present_with_name(
    channels: dict[str, np.ndarray],
    names: list[str],
) -> tuple[str | None, np.ndarray | None]:
    for name in names:
        if name in channels:
            return name, channels[name]
    return None, None


def channel_or_nan(
    channels: dict[str, np.ndarray],
    name: str,
    n: int,
) -> tuple[np.ndarray, bool]:
    values = channels.get(name)
    if values is None:
        return np.full(n, np.nan, dtype=float), False
    return values.astype(float), True


def derivative(x: np.ndarray, dt: float) -> np.ndarray:
    out = np.full_like(x, np.nan, dtype=float)
    valid = np.isfinite(x)

    if np.sum(valid) < 2:
        return out

    idx = np.where(valid)[0]
    out[idx] = np.gradient(x[idx], dt)

    return out


def moving_average_nan(x: np.ndarray, n: int) -> np.ndarray:
    if n <= 1:
        return x.copy()

    valid = np.isfinite(x)
    filled = np.where(valid, x, 0.0)

    k = np.ones(n, dtype=float)
    s = np.convolve(filled, k, mode="same")
    c = np.convolve(valid.astype(float), k, mode="same")

    out = np.full_like(x, np.nan, dtype=float)
    np.divide(s, c, out=out, where=c > 0)

    return out


def gps_local_xy(
    lat_deg: np.ndarray,
    lon_deg: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, str]:
    lat = np.asarray(lat_deg, dtype=float)
    lon = np.asarray(lon_deg, dtype=float)

    valid = (
        np.isfinite(lat)
        & np.isfinite(lon)
        & (np.abs(lat) <= 90)
        & (np.abs(lon) <= 180)
        & ~((np.abs(lat) < 1e-8) & (np.abs(lon) < 1e-8))
    )

    x = np.full_like(lat, np.nan, dtype=float)
    y = np.full_like(lon, np.nan, dtype=float)

    if np.sum(valid) < 2:
        return x, y, "no_gps"

    idx0 = np.where(valid)[0][0]
    lat0 = np.deg2rad(lat[idx0])
    lon0 = np.deg2rad(lon[idx0])
    r = 6_371_000.0

    x[valid] = r * np.cos(lat0) * (np.deg2rad(lon[valid]) - lon0)
    y[valid] = r * (np.deg2rad(lat[valid]) - lat0)

    return x, y, "ok"


def robust_q95_abs(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]

    if len(x) == 0:
        return float("nan")

    return float(np.quantile(np.abs(x), 0.95))


def robust_mae(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]

    if len(x) == 0:
        return float("nan")

    return float(np.mean(np.abs(x)))


def robust_scale_from_errors(errors: np.ndarray, eps: float = 1e-8) -> float:
    q95 = robust_q95_abs(errors)

    if not np.isfinite(q95) or q95 < eps:
        return 1.0

    return float(q95 + eps)


def parse_datetime_any(value: Any) -> datetime | None:
    if value is None:
        return None

    s = str(value).strip()
    if not s:
        return None

    s = s.replace("Z", "+00:00")

    candidates = [
        s,
        s.replace("/", "-"),
    ]

    for c in candidates:
        try:
            return datetime.fromisoformat(c)
        except Exception:
            pass

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d_%H-%M-%S",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
        "%Y%m%d_%H%M%S",
        "%Y%m%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass

    return None


def parse_acquisition_datetime(raw: dict[str, Any]) -> datetime | None:
    keys = [
        "start_datetime",
        "start_time",
        "datetime",
        "timestamp",
        "date",
        "modified_at",
    ]

    for key in keys:
        dt = parse_datetime_any(raw.get(key))
        if dt is not None:
            return dt

    return None


def make_time_bins(
    acquisition_datetime: datetime | None,
    relative_seconds: float,
    time_bin_minutes: int,
) -> tuple[str, str, str | None]:
    if acquisition_datetime is None or not np.isfinite(relative_seconds):
        return "unknown", "unknown", None

    absolute_dt = acquisition_datetime + timedelta(seconds=float(relative_seconds))

    date_bin = absolute_dt.strftime("%Y-%m-%d")

    minutes = absolute_dt.hour * 60 + absolute_dt.minute
    bin_start_min = (minutes // time_bin_minutes) * time_bin_minutes
    bin_end_min = bin_start_min + time_bin_minutes

    h0 = bin_start_min // 60
    m0 = bin_start_min % 60
    h1 = (bin_end_min // 60) % 24
    m1 = bin_end_min % 60

    time_bin = f"{h0:02d}:{m0:02d}-{h1:02d}:{m1:02d}"
    abs_iso = absolute_dt.isoformat()

    return date_bin, time_bin, abs_iso


# =============================================================================
# JSON READING + SIGNALS
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
        channels[name] = values

    return raw, time, channels


def build_model_channels(
    time: np.ndarray,
    channels: dict[str, np.ndarray],
    gps_smooth_sec: float = 0.5,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    n = len(time)
    out: dict[str, np.ndarray] = {}
    meta: dict[str, Any] = {}

    for name in [
        "vehicle.vx",
        "vehicle.ax",
        "vehicle.ay",
        "vehicle.yaw_rate",
    ]:
        if name in channels:
            out[name] = channels[name].astype(float)
            meta[f"has_{safe_stem(name)}"] = True
        else:
            out[name] = np.full(n, np.nan, dtype=float)
            meta[f"has_{safe_stem(name)}"] = False

    steer_source, steer = first_present_with_name(channels, STEER_CHANNELS)
    if steer is None:
        steer = np.full(n, np.nan, dtype=float)

    out["steer"] = steer.astype(float)
    meta["steer_source"] = steer_source or "missing"

    steer_s1, has_steer_s1 = channel_or_nan(channels, "WheelSteer_S1 (_)", n)
    steer_s2, has_steer_s2 = channel_or_nan(channels, "WheelSteer_S2 (_)", n)
    out["steer_s1"] = steer_s1
    out["steer_s2"] = steer_s2
    meta["has_steer_s1"] = has_steer_s1
    meta["has_steer_s2"] = has_steer_s2

    gps_speed = np.full(n, np.nan, dtype=float)

    lat = channels.get("gps.latitude")
    lon = channels.get("gps.longitude")

    meta["has_gps_latlon"] = lat is not None and lon is not None

    if lat is not None and lon is not None and len(time) >= 2:
        dt = float(np.nanmedian(np.diff(time)))

        if np.isfinite(dt) and dt > 0:
            gx, gy, status = gps_local_xy(lat, lon)
            meta["gps_status"] = status

            if status == "ok":
                smooth_n = max(1, int(round(gps_smooth_sec / dt)))
                gx_s = moving_average_nan(gx, smooth_n)
                gy_s = moving_average_nan(gy, smooth_n)

                gps_speed = np.sqrt(
                    derivative(gx_s, dt) ** 2
                    + derivative(gy_s, dt) ** 2
                )

                gps_speed = np.where(
                    np.isfinite(gps_speed),
                    np.clip(gps_speed, 0.0, 100.0),
                    np.nan,
                )
        else:
            meta["gps_status"] = "bad_dt"
    else:
        meta["gps_status"] = "missing"

    out["gps_speed"] = gps_speed

    return out, meta


def get_file_date(raw: dict[str, Any], path: Path) -> str:
    date = raw.get("date") or raw.get("modified_at")

    if date is None:
        return path.name

    return str(date)


# =============================================================================
# STANDARDIZATION
# =============================================================================

@dataclass
class Standardizer:
    mean: dict[str, float]
    std: dict[str, float]

    def transform(self, name: str, x: np.ndarray) -> np.ndarray:
        m = self.mean.get(name, 0.0)
        s = self.std.get(name, 1.0)
        return (x - m) / s

    def inverse(self, name: str, x: np.ndarray) -> np.ndarray:
        m = self.mean.get(name, 0.0)
        s = self.std.get(name, 1.0)
        return x * s + m


def fit_standardizer(files: list[Path]) -> Standardizer:
    values: dict[str, list[np.ndarray]] = {name: [] for name in BASE_CHANNELS}

    for path in tqdm(files, desc="Fitting standardizer", unit="file"):
        try:
            _, time, channels = read_resampled_json(path)
            model_channels, _ = build_model_channels(time, channels)

            for name in BASE_CHANNELS:
                x = model_channels[name]
                x = x[np.isfinite(x)]

                if len(x) > 0:
                    values[name].append(x)

        except Exception as exc:
            print(f"[WARN] standardizer failed on {path.name}: {exc}")

    mean: dict[str, float] = {}
    std: dict[str, float] = {}

    for name in BASE_CHANNELS:
        if values[name]:
            x = np.concatenate(values[name])
            mean[name] = float(np.mean(x))

            s = float(np.std(x))
            std[name] = s if np.isfinite(s) and s > 1e-8 else 1.0
        else:
            mean[name] = 0.0
            std[name] = 1.0

    return Standardizer(mean=mean, std=std)


# =============================================================================
# WINDOW DATASET
# =============================================================================

@dataclass
class WindowRecord:
    json_name: str
    date: str
    acquisition_datetime: datetime | None
    start_idx: int
    input_array: np.ndarray
    target_array: np.ndarray
    time_target: np.ndarray


class CoherenceWindowDataset(Dataset):
    def __init__(self, records: list[WindowRecord]) -> None:
        self.records = records

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        r = self.records[idx]

        x = torch.tensor(r.input_array, dtype=torch.float32)
        y = torch.tensor(r.target_array, dtype=torch.float32)

        return x, y


def build_windows_for_file(
    path: Path,
    target_name: str,
    input_names: list[str],
    standardizer: Standardizer,
    cfg: Config,
) -> list[WindowRecord]:
    raw, time, channels = read_resampled_json(path)
    model_channels, _ = build_model_channels(time, channels)

    if len(time) < 3:
        return []

    dt = float(np.nanmedian(np.diff(time)))

    if not np.isfinite(dt) or dt <= 0:
        return []

    history_len = max(2, int(round(cfg.history_sec / dt)))
    horizon_len = max(1, int(round(cfg.horizon_sec / dt)))
    stride_len = max(1, int(round(cfg.stride_sec / dt)))

    n = len(time)
    total_len = history_len + horizon_len

    if n < total_len:
        return []

    date = get_file_date(raw, path)
    acquisition_datetime = parse_acquisition_datetime(raw)

    arrays: dict[str, np.ndarray] = {}
    for name in BASE_CHANNELS:
        arrays[name] = standardizer.transform(name, model_channels[name]).astype(np.float32)

    records: list[WindowRecord] = []

    starts = list(range(0, n - total_len + 1, stride_len))

    if cfg.max_windows_per_file is not None and len(starts) > cfg.max_windows_per_file:
        starts = random.sample(starts, cfg.max_windows_per_file)
        starts.sort()

    for s in starts:
        hist_slice = slice(s, s + history_len)
        fut_slice = slice(s + history_len, s + history_len + horizon_len)

        input_mat = np.stack(
            [arrays[name][hist_slice] for name in input_names],
            axis=0,
        )

        target_vec = arrays[target_name][fut_slice][None, :]

        valid_ratio = (
            np.isfinite(input_mat).mean() * 0.5
            + np.isfinite(target_vec).mean() * 0.5
        )

        if valid_ratio < cfg.min_valid_ratio:
            continue

        input_mat = np.nan_to_num(input_mat, nan=0.0, posinf=0.0, neginf=0.0)
        target_vec = np.nan_to_num(target_vec, nan=0.0, posinf=0.0, neginf=0.0)

        records.append(
            WindowRecord(
                json_name=path.name,
                date=date,
                acquisition_datetime=acquisition_datetime,
                start_idx=s,
                input_array=input_mat.astype(np.float32),
                target_array=target_vec.astype(np.float32),
                time_target=time[fut_slice].astype(float),
            )
        )

    return records


def build_windows_for_files(
    files: list[Path],
    target_name: str,
    standardizer: Standardizer,
    cfg: Config,
    desc: str | None = None,
) -> list[WindowRecord]:
    input_names = input_channels_for_target(target_name)
    records: list[WindowRecord] = []

    iterator = tqdm(
        files,
        desc=desc or f"Building windows {target_name}",
        unit="file",
        leave=False,
    )

    for path in iterator:
        try:
            file_records = build_windows_for_file(
                path=path,
                target_name=target_name,
                input_names=input_names,
                standardizer=standardizer,
                cfg=cfg,
            )
            records.extend(file_records)
            iterator.set_postfix(windows=len(records))

        except Exception as exc:
            print(f"[WARN] windows failed on {path.name} target={target_name}: {exc}")

    return records


# =============================================================================
# TCN MODEL
# =============================================================================

class Chomp1d(nn.Module):
    def __init__(self, chomp_size: int) -> None:
        super().__init__()
        self.chomp_size = chomp_size

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.chomp_size == 0:
            return x
        return x[:, :, :-self.chomp_size]


class TemporalBlock(nn.Module):
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        dilation: int,
        dropout: float,
    ) -> None:
        super().__init__()

        padding = (kernel_size - 1) * dilation

        self.net = nn.Sequential(
            nn.Conv1d(
                in_channels,
                out_channels,
                kernel_size=kernel_size,
                padding=padding,
                dilation=dilation,
            ),
            Chomp1d(padding),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Conv1d(
                out_channels,
                out_channels,
                kernel_size=kernel_size,
                padding=padding,
                dilation=dilation,
            ),
            Chomp1d(padding),
            nn.GELU(),
            nn.Dropout(dropout),
        )

        self.downsample = (
            nn.Conv1d(in_channels, out_channels, kernel_size=1)
            if in_channels != out_channels
            else nn.Identity()
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x) + self.downsample(x)


class TCNForecaster(nn.Module):
    def __init__(
        self,
        input_channels: int,
        hidden_channels: int,
        num_blocks: int,
        horizon_len: int,
        dropout: float,
    ) -> None:
        super().__init__()

        blocks: list[nn.Module] = []
        c_in = input_channels

        for i in range(num_blocks):
            dilation = 2 ** i
            blocks.append(
                TemporalBlock(
                    in_channels=c_in,
                    out_channels=hidden_channels,
                    kernel_size=3,
                    dilation=dilation,
                    dropout=dropout,
                )
            )
            c_in = hidden_channels

        self.tcn = nn.Sequential(*blocks)

        self.head = nn.Sequential(
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
            nn.Linear(hidden_channels, hidden_channels),
            nn.GELU(),
            nn.Linear(hidden_channels, horizon_len),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.tcn(x)
        y = self.head(h)
        return y[:, None, :]


def infer_horizon_len(records: list[WindowRecord]) -> int:
    if not records:
        raise ValueError("Cannot infer horizon length from empty records")

    return int(records[0].target_array.shape[-1])


def make_model(
    input_channels: int,
    horizon_len: int,
    cfg: Config,
    seed: int,
) -> TCNForecaster:
    set_seed(seed)

    model = TCNForecaster(
        input_channels=input_channels,
        hidden_channels=cfg.hidden_channels,
        num_blocks=cfg.num_tcn_blocks,
        horizon_len=horizon_len,
        dropout=cfg.dropout,
    ).to(cfg.device)

    return model


# =============================================================================
# TRAIN / EVAL
# =============================================================================

def train_model(
    model: nn.Module,
    records: list[WindowRecord],
    cfg: Config,
    epochs: int,
    desc: str,
) -> None:
    if not records:
        return

    dataset = CoherenceWindowDataset(records)

    loader = DataLoader(
        dataset,
        batch_size=cfg.batch_size,
        shuffle=True,
        drop_last=False,
    )

    model.train()

    opt = torch.optim.AdamW(
        model.parameters(),
        lr=cfg.lr,
        weight_decay=cfg.weight_decay,
    )

    loss_fn = nn.HuberLoss(delta=1.0)

    epoch_bar = tqdm(range(epochs), desc=desc, unit="epoch", leave=False)

    for _ in epoch_bar:
        losses = []

        batch_bar = tqdm(loader, desc="train batches", unit="batch", leave=False)

        for xb, yb in batch_bar:
            xb = xb.to(cfg.device)
            yb = yb.to(cfg.device)

            pred = model(xb)
            loss = loss_fn(pred, yb)

            opt.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
            opt.step()

            loss_value = float(loss.detach().cpu())
            losses.append(loss_value)

            batch_bar.set_postfix(loss=f"{loss_value:.4g}")

        if losses:
            epoch_bar.set_postfix(loss=f"{np.mean(losses):.4g}")


@torch.no_grad()
def predict_records_ensemble(
    models: list[nn.Module],
    records: list[WindowRecord],
    target_name: str,
    standardizer: Standardizer,
    cfg: Config,
    phase: str,
    error_scale: float,
    desc: str,
) -> tuple[pd.DataFrame, dict[str, float]]:
    if not records:
        empty = pd.DataFrame()
        metrics = {
            "mae": float("nan"),
            "q95_abs_error": float("nan"),
            "mean_score": float("nan"),
            "q95_score": float("nan"),
            "q95_y_abs": float("nan"),
            "relative_q95_error": float("nan"),
            "ensemble_std_mean": float("nan"),
            "ensemble_std_q95": float("nan"),
            "ensemble_std_score_q95": float("nan"),
            "model_mae_mean": float("nan"),
            "model_mae_std": float("nan"),
            "model_q95_abs_error_mean": float("nan"),
            "model_q95_abs_error_std": float("nan"),
            "model_relative_q95_error_mean": float("nan"),
            "model_relative_q95_error_std": float("nan"),
        }
        return empty, metrics

    dataset = CoherenceWindowDataset(records)

    loader = DataLoader(
        dataset,
        batch_size=cfg.batch_size,
        shuffle=False,
        drop_last=False,
    )

    for model in models:
        model.eval()

    rows: list[dict[str, Any]] = []

    all_errors_mean_pred: list[float] = []
    all_true: list[float] = []
    all_ensemble_std: list[float] = []

    per_model_errors: list[list[float]] = [[] for _ in models]
    per_model_true: list[list[float]] = [[] for _ in models]

    offset = 0

    batch_bar = tqdm(loader, desc=desc, unit="batch", leave=False)

    for xb, yb in batch_bar:
        xb = xb.to(cfg.device)

        preds = []
        for model in models:
            pred_m = model(xb).cpu().numpy()
            preds.append(pred_m)

        preds_np = np.stack(preds, axis=0)

        pred_mean_std_space = np.mean(preds_np, axis=0)
        pred_std_std_space = np.std(preds_np, axis=0)

        true_std_space = yb.numpy()
        bsz = true_std_space.shape[0]

        for i in range(bsz):
            r = records[offset + i]

            y_true_std = true_std_space[i, 0]
            y_true = standardizer.inverse(target_name, y_true_std)

            y_pred_mean_std = pred_mean_std_space[i, 0]
            y_pred_mean = standardizer.inverse(target_name, y_pred_mean_std)

            physical_std_scale = standardizer.std.get(target_name, 1.0)
            ensemble_std = pred_std_std_space[i, 0] * physical_std_scale

            err_mean_pred = y_true - y_pred_mean
            score = np.abs(err_mean_pred) / error_scale
            disagreement_score = ensemble_std / error_scale

            all_errors_mean_pred.extend(err_mean_pred[np.isfinite(err_mean_pred)].tolist())
            all_true.extend(y_true[np.isfinite(y_true)].tolist())
            all_ensemble_std.extend(ensemble_std[np.isfinite(ensemble_std)].tolist())

            for model_idx in range(len(models)):
                y_pred_m_std = preds_np[model_idx, i, 0]
                y_pred_m = standardizer.inverse(target_name, y_pred_m_std)
                err_m = y_true - y_pred_m

                per_model_errors[model_idx].extend(err_m[np.isfinite(err_m)].tolist())
                per_model_true[model_idx].extend(y_true[np.isfinite(y_true)].tolist())

            for j in range(len(y_true)):
                date_bin, time_bin, absolute_datetime = make_time_bins(
                    r.acquisition_datetime,
                    float(r.time_target[j]),
                    cfg.time_bin_minutes,
                )

                rows.append(
                    {
                        "json_name": r.json_name,
                        "date": r.date,
                        "date_bin": date_bin,
                        "time_bin": time_bin,
                        "absolute_datetime": absolute_datetime,
                        "start_idx": int(r.start_idx),
                        "time": float(r.time_target[j]),
                        "target_name": target_name,
                        "phase": phase,
                        "y_true": float(y_true[j]),
                        "y_pred": float(y_pred_mean[j]),
                        "ensemble_std": float(ensemble_std[j]),
                        "error": float(err_mean_pred[j]),
                        "abs_error": float(abs(err_mean_pred[j])),
                        "score": float(score[j]),
                        "disagreement_score": float(disagreement_score[j]),
                    }
                )

        offset += bsz
        batch_bar.set_postfix(rows=len(rows))

    errors = np.asarray(all_errors_mean_pred, dtype=float)
    y_true_values = np.asarray(all_true, dtype=float)
    ensemble_std_values = np.asarray(all_ensemble_std, dtype=float)

    q95_error = robust_q95_abs(errors)
    q95_y_abs = robust_q95_abs(y_true_values)

    relative_q95_error = (
        q95_error / (q95_y_abs + 1e-8)
        if np.isfinite(q95_y_abs)
        else float("nan")
    )

    model_maes = []
    model_q95s = []
    model_rel_q95s = []

    for model_idx in range(len(models)):
        e_m = np.asarray(per_model_errors[model_idx], dtype=float)
        y_m = np.asarray(per_model_true[model_idx], dtype=float)

        mae_m = robust_mae(e_m)
        q95_m = robust_q95_abs(e_m)
        q95_y_m = robust_q95_abs(y_m)

        rel_m = (
            q95_m / (q95_y_m + 1e-8)
            if np.isfinite(q95_y_m)
            else float("nan")
        )

        model_maes.append(mae_m)
        model_q95s.append(q95_m)
        model_rel_q95s.append(rel_m)

    model_maes = np.asarray(model_maes, dtype=float)
    model_q95s = np.asarray(model_q95s, dtype=float)
    model_rel_q95s = np.asarray(model_rel_q95s, dtype=float)

    metrics = {
        "mae": robust_mae(errors),
        "q95_abs_error": q95_error,
        "mean_score": float(np.nanmean(np.abs(errors) / error_scale))
        if np.any(np.isfinite(errors))
        else float("nan"),
        "q95_score": robust_q95_abs(errors / error_scale),
        "q95_y_abs": q95_y_abs,
        "relative_q95_error": relative_q95_error,

        "ensemble_std_mean": float(np.nanmean(ensemble_std_values))
        if np.any(np.isfinite(ensemble_std_values))
        else float("nan"),
        "ensemble_std_q95": robust_q95_abs(ensemble_std_values),
        "ensemble_std_score_q95": robust_q95_abs(ensemble_std_values / error_scale),

        "model_mae_mean": float(np.nanmean(model_maes)),
        "model_mae_std": float(np.nanstd(model_maes)),
        "model_q95_abs_error_mean": float(np.nanmean(model_q95s)),
        "model_q95_abs_error_std": float(np.nanstd(model_q95s)),
        "model_relative_q95_error_mean": float(np.nanmean(model_rel_q95s)),
        "model_relative_q95_error_std": float(np.nanstd(model_rel_q95s)),
    }

    return pd.DataFrame(rows), metrics


def update_memory(
    memory: list[WindowRecord],
    new_records: list[WindowRecord],
    cfg: Config,
) -> list[WindowRecord]:
    if not new_records:
        return memory

    memory = list(memory)

    n_add = min(len(new_records), cfg.memory_max_windows_per_target)
    selected = random.sample(new_records, n_add) if len(new_records) > n_add else new_records

    memory.extend(selected)

    if len(memory) > cfg.memory_max_windows_per_target:
        memory = random.sample(memory, cfg.memory_max_windows_per_target)

    return memory


def mix_current_and_memory(
    current: list[WindowRecord],
    memory: list[WindowRecord],
    cfg: Config,
) -> list[WindowRecord]:
    if not memory or cfg.memory_fraction <= 0:
        return current

    n_mem = int(
        round(
            len(current)
            * cfg.memory_fraction
            / max(1e-8, 1.0 - cfg.memory_fraction)
        )
    )

    n_mem = min(n_mem, len(memory))
    mem_sample = random.sample(memory, n_mem) if len(memory) > n_mem else memory

    return list(current) + list(mem_sample)


# =============================================================================
# METRICS AGGREGATION
# =============================================================================

def q95_abs_series(x: pd.Series) -> float:
    arr_x = x.to_numpy(dtype=float)
    arr_x = arr_x[np.isfinite(arr_x)]

    if len(arr_x) == 0:
        return float("nan")

    return float(np.quantile(np.abs(arr_x), 0.95))


def relative_q95_from_group(df: pd.DataFrame) -> float:
    err_q95 = q95_abs_series(df["error"])
    y_q95 = q95_abs_series(df["y_true"])

    if not np.isfinite(y_q95):
        return float("nan")

    return float(err_q95 / (y_q95 + 1e-8))


def aggregate_prediction_metrics(
    pred_df: pd.DataFrame,
    group_cols: list[str],
) -> pd.DataFrame:
    if pred_df.empty:
        return pd.DataFrame()

    rows = []

    for keys, df_g in pred_df.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)

        row = {col: val for col, val in zip(group_cols, keys)}

        row.update(
            {
                "n_points": int(len(df_g)),
                "n_files": int(df_g["json_name"].nunique()),
                "mae": float(df_g["abs_error"].mean()),
                "q95_abs_error": q95_abs_series(df_g["error"]),
                "mean_score": float(df_g["score"].mean()),
                "q95_score": q95_abs_series(df_g["score"]),
                "q95_y_abs": q95_abs_series(df_g["y_true"]),
                "relative_q95_error": relative_q95_from_group(df_g),
                "ensemble_std_mean": float(df_g["ensemble_std"].mean()),
                "ensemble_std_q95": q95_abs_series(df_g["ensemble_std"]),
                "disagreement_score_mean": float(df_g["disagreement_score"].mean()),
                "disagreement_score_q95": q95_abs_series(df_g["disagreement_score"]),
            }
        )

        rows.append(row)

    return pd.DataFrame(rows)


# =============================================================================
# FILE AND BATCH SUMMARIES
# =============================================================================

def summarize_signal_array(x: np.ndarray) -> dict[str, float]:
    x = np.asarray(x, dtype=float)
    valid = np.isfinite(x)
    xv = x[valid]

    if len(xv) == 0:
        return {
            "valid_ratio": 0.0,
            "mean": float("nan"),
            "std": float("nan"),
            "min": float("nan"),
            "q01": float("nan"),
            "q05": float("nan"),
            "q50": float("nan"),
            "q95": float("nan"),
            "q99": float("nan"),
            "max": float("nan"),
            "q95_abs": float("nan"),
        }

    return {
        "valid_ratio": float(np.mean(valid)),
        "mean": float(np.mean(xv)),
        "std": float(np.std(xv)),
        "min": float(np.min(xv)),
        "q01": float(np.quantile(xv, 0.01)),
        "q05": float(np.quantile(xv, 0.05)),
        "q50": float(np.quantile(xv, 0.50)),
        "q95": float(np.quantile(xv, 0.95)),
        "q99": float(np.quantile(xv, 0.99)),
        "max": float(np.max(xv)),
        "q95_abs": float(np.quantile(np.abs(xv), 0.95)),
    }


def build_file_channel_summary(
    files: list[Path],
    batches: list[list[Path]],
    holdout_files: list[Path] | None = None,
) -> pd.DataFrame:
    file_to_batch = {}
    for batch_id, batch_files in enumerate(batches):
        for p in batch_files:
            file_to_batch[p.name] = batch_id
    holdout_names = {p.name for p in (holdout_files or [])}

    rows = []

    for path in tqdm(files, desc="Building file channel summary", unit="file"):
        try:
            raw, time, channels = read_resampled_json(path)
            model_channels, meta = build_model_channels(time, channels)

            acquisition_dt = parse_acquisition_datetime(raw)

            row: dict[str, Any] = {
                "json_name": path.name,
                "split": "holdout" if path.name in holdout_names else "train_adapt",
                "batch_id": -1 if path.name in holdout_names else file_to_batch.get(path.name, -1),
                "date": get_file_date(raw, path),
                "acquisition_datetime": acquisition_dt.isoformat() if acquisition_dt else None,
                "n_samples": len(time),
                "steer_source": meta.get("steer_source", "unknown"),
                "has_steer_s1": meta.get("has_steer_s1", False),
                "has_steer_s2": meta.get("has_steer_s2", False),
                "gps_status": meta.get("gps_status", "unknown"),
                "has_gps_latlon": meta.get("has_gps_latlon", False),
            }

            for name in BASE_CHANNELS:
                stats = summarize_signal_array(model_channels[name])
                for k, v in stats.items():
                    row[f"{safe_stem(name)}_{k}"] = v

            rows.append(row)

        except Exception as exc:
            rows.append(
                {
                    "json_name": path.name,
                    "split": "holdout" if path.name in holdout_names else "train_adapt",
                    "batch_id": -1 if path.name in holdout_names else file_to_batch.get(path.name, -1),
                    "error": str(exc),
                }
            )

    return pd.DataFrame(rows)


def build_batch_signal_summary(file_summary: pd.DataFrame) -> pd.DataFrame:
    if file_summary.empty:
        return pd.DataFrame()

    rows = []

    for batch_id, df_b in file_summary.groupby("batch_id"):
        for signal in BASE_CHANNELS:
            prefix = safe_stem(signal)
            row = {
                "batch_id": batch_id,
                "signal": signal,
                "n_files": len(df_b),
            }

            for stat in [
                "valid_ratio",
                "mean",
                "std",
                "min",
                "q01",
                "q05",
                "q50",
                "q95",
                "q99",
                "max",
                "q95_abs",
            ]:
                col = f"{prefix}_{stat}"
                if col in df_b:
                    values = pd.to_numeric(df_b[col], errors="coerce")
                    row[f"file_mean_{stat}"] = float(values.mean())
                    row[f"file_median_{stat}"] = float(values.median())
                    row[f"file_max_{stat}"] = float(values.max())

            rows.append(row)

    return pd.DataFrame(rows)


# =============================================================================
# PLOTS
# =============================================================================

def import_plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def plot_with_fill_between(
    ax,
    x: np.ndarray,
    mean: np.ndarray,
    std: np.ndarray,
    label: str,
) -> None:
    x = np.asarray(x, dtype=float)
    mean = np.asarray(mean, dtype=float)
    std = np.asarray(std, dtype=float)

    valid = np.isfinite(x) & np.isfinite(mean) & np.isfinite(std)

    if not np.any(valid):
        return

    x = x[valid]
    mean = mean[valid]
    std = std[valid]

    lower = mean - std
    upper = mean + std

    ax.plot(x, mean, marker="o", linewidth=1.5, label=label)
    ax.fill_between(x, lower, upper, alpha=0.20)


def plot_batch_metrics(metrics_df: pd.DataFrame, out_dir: Path) -> None:
    if metrics_df.empty:
        return

    plt = import_plt()
    out_dir.mkdir(parents=True, exist_ok=True)

    for target_name, df_t in tqdm(
        metrics_df.groupby("target_name"),
        desc="Plot batch metrics",
        unit="target",
    ):
        df_t = df_t.sort_values("batch_id")
        pre = df_t[df_t["phase"] == "pre"].copy()

        if pre.empty:
            continue

        x = pre["batch_id"].to_numpy(dtype=float)

        fig, ax = plt.subplots(figsize=(12, 5))

        plot_with_fill_between(
            ax=ax,
            x=x,
            mean=pre["memory_pre_model_q95_mean"].to_numpy(dtype=float),
            std=pre["memory_pre_model_q95_std"].to_numpy(dtype=float),
            label="memory pre q95 mean ± std",
        )

        plot_with_fill_between(
            ax=ax,
            x=x,
            mean=pre["new_pre_model_q95_mean"].to_numpy(dtype=float),
            std=pre["new_pre_model_q95_std"].to_numpy(dtype=float),
            label="new pre q95 mean ± std",
        )

        plot_with_fill_between(
            ax=ax,
            x=x,
            mean=pre["new_post_model_q95_mean"].to_numpy(dtype=float),
            std=pre["new_post_model_q95_std"].to_numpy(dtype=float),
            label="new post q95 mean ± std",
        )

        ax.set_title(f"Q95 erreur — moyenne ± écart-type ensemble — {target_name}")
        ax.set_xlabel("batch chronologique")
        ax.set_ylabel("q95 erreur absolue")
        ax.grid(alpha=0.3)
        ax.legend()

        fig.tight_layout()
        fig.savefig(
            out_dir / f"q95_mean_std_fillbetween__{safe_stem(target_name)}.png",
            dpi=160,
        )
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(12, 5))

        plot_with_fill_between(
            ax=ax,
            x=x,
            mean=pre["memory_pre_model_mae_mean"].to_numpy(dtype=float),
            std=pre["memory_pre_model_mae_std"].to_numpy(dtype=float),
            label="memory pre MAE mean ± std",
        )

        plot_with_fill_between(
            ax=ax,
            x=x,
            mean=pre["new_pre_model_mae_mean"].to_numpy(dtype=float),
            std=pre["new_pre_model_mae_std"].to_numpy(dtype=float),
            label="new pre MAE mean ± std",
        )

        plot_with_fill_between(
            ax=ax,
            x=x,
            mean=pre["new_post_model_mae_mean"].to_numpy(dtype=float),
            std=pre["new_post_model_mae_std"].to_numpy(dtype=float),
            label="new post MAE mean ± std",
        )

        ax.set_title(f"MAE — moyenne ± écart-type ensemble — {target_name}")
        ax.set_xlabel("batch chronologique")
        ax.set_ylabel("MAE")
        ax.grid(alpha=0.3)
        ax.legend()

        fig.tight_layout()
        fig.savefig(
            out_dir / f"mae_mean_std_fillbetween__{safe_stem(target_name)}.png",
            dpi=160,
        )
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(12, 5))

        plot_with_fill_between(
            ax=ax,
            x=x,
            mean=pre["memory_pre_model_relative_q95_mean"].to_numpy(dtype=float),
            std=pre["memory_pre_model_relative_q95_std"].to_numpy(dtype=float),
            label="memory pre relative q95 mean ± std",
        )

        plot_with_fill_between(
            ax=ax,
            x=x,
            mean=pre["new_pre_model_relative_q95_mean"].to_numpy(dtype=float),
            std=pre["new_pre_model_relative_q95_std"].to_numpy(dtype=float),
            label="new pre relative q95 mean ± std",
        )

        plot_with_fill_between(
            ax=ax,
            x=x,
            mean=pre["new_post_model_relative_q95_mean"].to_numpy(dtype=float),
            std=pre["new_post_model_relative_q95_std"].to_numpy(dtype=float),
            label="new post relative q95 mean ± std",
        )

        ax.set_title(f"Relative Q95 — moyenne ± écart-type ensemble — {target_name}")
        ax.set_xlabel("batch chronologique")
        ax.set_ylabel("relative q95 error")
        ax.grid(alpha=0.3)
        ax.legend()

        fig.tight_layout()
        fig.savefig(
            out_dir / f"relative_q95_mean_std_fillbetween__{safe_stem(target_name)}.png",
            dpi=160,
        )
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(12, 5))

        ax.plot(
            pre["batch_id"],
            pre["generalization_gap_q95"],
            marker="o",
            label="generalization gap q95",
        )

        ax.plot(
            pre["batch_id"],
            pre["adaptation_gain_q95"],
            marker="o",
            label="adaptation gain q95",
        )

        ax.plot(
            pre["batch_id"],
            pre["forgetting_q95"],
            marker="o",
            label="forgetting q95",
        )

        ax.axhline(0.0, linewidth=1.0)

        ax.set_title(f"Gap / adaptation / forgetting — {target_name}")
        ax.set_xlabel("batch chronologique")
        ax.set_ylabel("q95")
        ax.grid(alpha=0.3)
        ax.legend()

        fig.tight_layout()
        fig.savefig(
            out_dir / f"gap_adaptation_forgetting__{safe_stem(target_name)}.png",
            dpi=160,
        )
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(12, 5))

        ax.plot(
            pre["batch_id"],
            pre["new_pre_ensemble_std_q95"],
            marker="o",
            label="new pre ensemble std q95",
        )

        ax.plot(
            pre["batch_id"],
            pre["new_post_ensemble_std_q95"],
            marker="o",
            label="new post ensemble std q95",
        )

        ax.set_title(f"Incertitude prédictive ensemble — {target_name}")
        ax.set_xlabel("batch chronologique")
        ax.set_ylabel("ensemble std q95")
        ax.grid(alpha=0.3)
        ax.legend()

        fig.tight_layout()
        fig.savefig(
            out_dir / f"ensemble_prediction_uncertainty__{safe_stem(target_name)}.png",
            dpi=160,
        )
        plt.close(fig)


def plot_timebin_metrics(timebin_df: pd.DataFrame, out_dir: Path) -> None:
    if timebin_df.empty:
        return

    plt = import_plt()
    out_dir.mkdir(parents=True, exist_ok=True)

    df = timebin_df[timebin_df["phase"] == "pre"].copy()
    if df.empty:
        return

    df["date_time_bin"] = df["date_bin"].astype(str) + " " + df["time_bin"].astype(str)

    for target_name, df_t in tqdm(
        df.groupby("target_name"),
        desc="Plot timebin metrics",
        unit="target",
    ):
        df_t = df_t.sort_values(["date_bin", "time_bin"])

        fig, ax = plt.subplots(figsize=(14, 5))
        ax.plot(df_t["date_time_bin"], df_t["q95_abs_error"], marker="o", label="q95 abs error")
        ax.set_title(f"Erreur par date/tranche horaire — {target_name}")
        ax.set_xlabel("date / tranche horaire")
        ax.set_ylabel("q95 abs error")
        ax.grid(alpha=0.3)
        ax.tick_params(axis="x", rotation=70)
        ax.legend()
        fig.tight_layout()
        fig.savefig(out_dir / f"timebin_q95__{safe_stem(target_name)}.png", dpi=160)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(14, 5))
        ax.plot(df_t["date_time_bin"], df_t["ensemble_std_q95"], marker="o", label="ensemble std q95")
        ax.set_title(f"Incertitude ensemble par date/tranche horaire — {target_name}")
        ax.set_xlabel("date / tranche horaire")
        ax.set_ylabel("ensemble std q95")
        ax.grid(alpha=0.3)
        ax.tick_params(axis="x", rotation=70)
        ax.legend()
        fig.tight_layout()
        fig.savefig(out_dir / f"timebin_uncertainty__{safe_stem(target_name)}.png", dpi=160)
        plt.close(fig)


def plot_prediction_examples(
    pred_df: pd.DataFrame,
    out_dir: Path,
    max_files: int = 5,
) -> None:
    if pred_df.empty:
        return

    plt = import_plt()
    out_dir.mkdir(parents=True, exist_ok=True)

    grouped = list(pred_df.groupby("target_name"))

    for target_name, df_t in tqdm(
        grouped,
        desc="Plot prediction examples",
        unit="target",
    ):
        df_examples = df_t[df_t["phase"].isin(["pre", "post"])].copy()
        if df_examples.empty:
            continue
        json_names = list(df_examples["json_name"].dropna().unique())[:max_files]

        for json_name in json_names:
            df_f = df_examples[df_examples["json_name"] == json_name].copy()

            if df_f.empty:
                continue

            agg = (
                df_f.groupby(["phase", "time"], as_index=False)
                .agg(
                    y_true=("y_true", "mean"),
                    y_pred=("y_pred", "mean"),
                    ensemble_std=("ensemble_std", "mean"),
                    score=("score", "mean"),
                    abs_error=("abs_error", "mean"),
                )
                .sort_values("time")
            )

            fig, ax = plt.subplots(figsize=(12, 5))

            pre = agg[agg["phase"] == "pre"]
            post = agg[agg["phase"] == "post"]

            if not pre.empty:
                ax.plot(pre["time"], pre["y_true"], linewidth=1.0, label="true")
                ax.plot(pre["time"], pre["y_pred"], linewidth=1.0, label="pred pre")

            if not post.empty:
                ax.plot(post["time"], post["y_pred"], linewidth=1.0, label="pred post")

            ax.set_title(f"{target_name} — {json_name}")
            ax.set_xlabel("temps (s)")
            ax.set_ylabel(target_name)
            ax.grid(alpha=0.3)
            ax.legend()

            fig.tight_layout()
            fig.savefig(
                out_dir / f"pred__{safe_stem(target_name)}__{safe_stem(json_name)}.png",
                dpi=160,
            )
            plt.close(fig)


def plot_holdout_generalization_examples(
    pred_df: pd.DataFrame,
    out_dir: Path,
    max_files: int = 10,
) -> None:
    if pred_df.empty or "phase" not in pred_df.columns:
        return

    holdout_df = pred_df[pred_df["phase"].isin(["holdout_pre", "holdout_post", "holdout"])].copy()
    if holdout_df.empty:
        return

    plt = import_plt()
    out_dir.mkdir(parents=True, exist_ok=True)

    grouped = list(holdout_df.groupby("target_name"))

    for target_name, df_t in tqdm(
        grouped,
        desc="Plot holdout generalization examples",
        unit="target",
    ):
        ranked_files = (
            df_t.groupby("json_name")["abs_error"]
            .mean()
            .sort_values(ascending=False, na_position="last")
            .index
            .tolist()
        )
        json_names = ranked_files[:max_files]

        for json_name in json_names:
            df_f = df_t[df_t["json_name"] == json_name].copy()
            if df_f.empty:
                continue

            agg = (
                df_f.groupby(["phase", "time"], as_index=False)
                .agg(
                    y_true=("y_true", "mean"),
                    y_pred=("y_pred", "mean"),
                    ensemble_std=("ensemble_std", "mean"),
                    abs_error=("abs_error", "mean"),
                )
                .sort_values("time")
            )

            fig, ax = plt.subplots(figsize=(12, 5))
            truth = agg[agg["phase"].isin(["holdout_pre", "holdout"])].copy()
            if truth.empty:
                truth = agg.copy()
            truth = truth.sort_values("time")
            ax.plot(truth["time"], truth["y_true"], linewidth=1.0, label="true")

            phase_labels = {
                "holdout_pre": "pred holdout pre",
                "holdout_post": "pred holdout post",
                "holdout": "pred holdout",
            }
            phase_colors = {
                "holdout_pre": "#f59e0b",
                "holdout_post": "#22c55e",
                "holdout": "#a855f7",
            }
            metric_bits = []
            for phase, label in phase_labels.items():
                phase_df = agg[agg["phase"] == phase].sort_values("time")
                if phase_df.empty:
                    continue
                ax.plot(
                    phase_df["time"],
                    phase_df["y_pred"],
                    linewidth=1.0,
                    label=label,
                    color=phase_colors.get(phase),
                )
                mae = float(phase_df["abs_error"].mean())
                q95 = robust_q95_abs(phase_df["y_true"].to_numpy(dtype=float) - phase_df["y_pred"].to_numpy(dtype=float))
                metric_bits.append(f"{label}: MAE={mae:.4g} Q95={q95:.4g}")

            post = agg[agg["phase"] == "holdout_post"].sort_values("time")
            if "ensemble_std" in post.columns and post["ensemble_std"].notna().any():
                y_pred = post["y_pred"].to_numpy(dtype=float)
                std = post["ensemble_std"].to_numpy(dtype=float)
                ax.fill_between(
                    post["time"],
                    y_pred - std,
                    y_pred + std,
                    alpha=0.18,
                    label="holdout post ± ensemble std",
                    color="#22c55e",
                )

            suffix = " | ".join(metric_bits)
            ax.set_title(f"Holdout généralisation — {target_name} — {json_name}" + (f" | {suffix}" if suffix else ""))
            ax.set_xlabel("temps (s)")
            ax.set_ylabel(target_name)
            ax.grid(alpha=0.3)
            ax.legend()

            fig.tight_layout()
            fig.savefig(
                out_dir / f"holdout__{safe_stem(target_name)}__{safe_stem(json_name)}.png",
                dpi=160,
            )
            plt.close(fig)


# =============================================================================
# INCREMENTAL PIPELINE
# =============================================================================

def split_chronological_batches(files: list[Path], cfg: Config) -> list[list[Path]]:
    dated: list[tuple[str, Path]] = []

    for path in tqdm(files, desc="Sorting files chronologically", unit="file"):
        try:
            raw = load_json(path)
            date = get_file_date(raw, path)
        except Exception:
            date = path.name

        dated.append((date, path))

    dated.sort(key=lambda x: (x[0], x[1].name))
    sorted_files = [p for _, p in dated]

    if len(sorted_files) == 0:
        return []

    n_initial = max(1, int(round(len(sorted_files) * cfg.initial_fraction)))

    initial = sorted_files[:n_initial]
    rest = sorted_files[n_initial:]

    batches = [initial]

    for i in range(0, len(rest), cfg.batch_size_files):
        batches.append(rest[i : i + cfg.batch_size_files])

    return [b for b in batches if b]


def split_train_holdout_chronological(files: list[Path], cfg: Config) -> tuple[list[Path], list[Path]]:
    dated: list[tuple[str, Path]] = []

    for path in tqdm(files, desc="Sorting files for holdout split", unit="file"):
        try:
            raw = load_json(path)
            date = get_file_date(raw, path)
        except Exception:
            date = path.name

        dated.append((date, path))

    dated.sort(key=lambda x: (x[0], x[1].name))
    sorted_files = [p for _, p in dated]

    if cfg.holdout_fraction <= 0 or len(sorted_files) < 2:
        return sorted_files, []

    n_holdout = int(round(len(sorted_files) * cfg.holdout_fraction))
    n_holdout = max(1, n_holdout)
    n_holdout = min(n_holdout, len(sorted_files) - 1)

    return sorted_files[:-n_holdout], sorted_files[-n_holdout:]


def get_date_min_max(files: list[Path]) -> tuple[str, str]:
    dates = []

    for p in files:
        try:
            dates.append(get_file_date(load_json(p), p))
        except Exception:
            dates.append(p.name)

    return min(dates), max(dates)


def metrics_row(
    *,
    batch_id: int,
    target_name: str,
    phase: str,
    n_files: int,
    n_windows: int,
    date_min: str,
    date_max: str,
    memory_pre: dict[str, float],
    new_pre: dict[str, float],
    new_post: dict[str, float],
    memory_post: dict[str, float],
) -> dict[str, Any]:
    eps = 1e-8

    memory_pre_q95 = memory_pre["q95_abs_error"]
    new_pre_q95 = new_pre["q95_abs_error"]
    new_post_q95 = new_post["q95_abs_error"]
    memory_post_q95 = memory_post["q95_abs_error"]

    generalization_gap_q95 = new_pre_q95 - memory_pre_q95
    generalization_ratio_q95 = new_pre_q95 / (memory_pre_q95 + eps)

    adaptation_gain_q95 = new_pre_q95 - new_post_q95
    forgetting_q95 = memory_post_q95 - memory_pre_q95

    return {
        "batch_id": batch_id,
        "target_name": target_name,
        "phase": phase,
        "n_files": n_files,
        "n_windows": n_windows,
        "date_min": date_min,
        "date_max": date_max,

        "memory_pre_mae": memory_pre["mae"],
        "memory_pre_q95_abs_error": memory_pre_q95,
        "memory_pre_relative_q95_error": memory_pre["relative_q95_error"],
        "memory_pre_ensemble_std_mean": memory_pre["ensemble_std_mean"],
        "memory_pre_ensemble_std_q95": memory_pre["ensemble_std_q95"],
        "memory_pre_ensemble_std_score_q95": memory_pre["ensemble_std_score_q95"],
        "memory_pre_model_q95_mean": memory_pre["model_q95_abs_error_mean"],
        "memory_pre_model_q95_std": memory_pre["model_q95_abs_error_std"],
        "memory_pre_model_mae_mean": memory_pre["model_mae_mean"],
        "memory_pre_model_mae_std": memory_pre["model_mae_std"],
        "memory_pre_model_relative_q95_mean": memory_pre["model_relative_q95_error_mean"],
        "memory_pre_model_relative_q95_std": memory_pre["model_relative_q95_error_std"],

        "new_pre_mae": new_pre["mae"],
        "new_pre_q95_abs_error": new_pre_q95,
        "new_pre_relative_q95_error": new_pre["relative_q95_error"],
        "new_pre_ensemble_std_mean": new_pre["ensemble_std_mean"],
        "new_pre_ensemble_std_q95": new_pre["ensemble_std_q95"],
        "new_pre_ensemble_std_score_q95": new_pre["ensemble_std_score_q95"],
        "new_pre_model_q95_mean": new_pre["model_q95_abs_error_mean"],
        "new_pre_model_q95_std": new_pre["model_q95_abs_error_std"],
        "new_pre_model_mae_mean": new_pre["model_mae_mean"],
        "new_pre_model_mae_std": new_pre["model_mae_std"],
        "new_pre_model_relative_q95_mean": new_pre["model_relative_q95_error_mean"],
        "new_pre_model_relative_q95_std": new_pre["model_relative_q95_error_std"],

        "generalization_gap_q95": generalization_gap_q95,
        "generalization_ratio_q95": generalization_ratio_q95,

        "new_post_mae": new_post["mae"],
        "new_post_q95_abs_error": new_post_q95,
        "new_post_relative_q95_error": new_post["relative_q95_error"],
        "new_post_ensemble_std_mean": new_post["ensemble_std_mean"],
        "new_post_ensemble_std_q95": new_post["ensemble_std_q95"],
        "new_post_ensemble_std_score_q95": new_post["ensemble_std_score_q95"],
        "new_post_model_q95_mean": new_post["model_q95_abs_error_mean"],
        "new_post_model_q95_std": new_post["model_q95_abs_error_std"],
        "new_post_model_mae_mean": new_post["model_mae_mean"],
        "new_post_model_mae_std": new_post["model_mae_std"],
        "new_post_model_relative_q95_mean": new_post["model_relative_q95_error_mean"],
        "new_post_model_relative_q95_std": new_post["model_relative_q95_error_std"],

        "memory_post_mae": memory_post["mae"],
        "memory_post_q95_abs_error": memory_post_q95,
        "memory_post_relative_q95_error": memory_post["relative_q95_error"],
        "memory_post_ensemble_std_mean": memory_post["ensemble_std_mean"],
        "memory_post_ensemble_std_q95": memory_post["ensemble_std_q95"],
        "memory_post_ensemble_std_score_q95": memory_post["ensemble_std_score_q95"],
        "memory_post_model_q95_mean": memory_post["model_q95_abs_error_mean"],
        "memory_post_model_q95_std": memory_post["model_q95_abs_error_std"],
        "memory_post_model_mae_mean": memory_post["model_mae_mean"],
        "memory_post_model_mae_std": memory_post["model_mae_std"],
        "memory_post_model_relative_q95_mean": memory_post["model_relative_q95_error_mean"],
        "memory_post_model_relative_q95_std": memory_post["model_relative_q95_error_std"],

        "adaptation_gain_q95": adaptation_gain_q95,
        "forgetting_q95": forgetting_q95,
    }


def run_for_target(
    target_name: str,
    batches: list[list[Path]],
    holdout_files: list[Path],
    standardizer: Standardizer,
    cfg: Config,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    print()
    print("=" * 80)
    print(f"TARGET: {target_name}")
    print("=" * 80)

    input_names = input_channels_for_target(target_name)
    print(f"Inputs: {input_names}")

    initial_files = batches[0]

    initial_records = build_windows_for_files(
        files=initial_files,
        target_name=target_name,
        standardizer=standardizer,
        cfg=cfg,
        desc=f"Initial windows {target_name}",
    )

    if not initial_records:
        print(f"[WARN] no initial records for target {target_name}")
        return pd.DataFrame(), pd.DataFrame()

    horizon_len = infer_horizon_len(initial_records)

    ensemble: list[nn.Module] = []
    for m in range(cfg.ensemble_size):
        model_seed = cfg.seed + 1000 * m + 17
        ensemble.append(
            make_model(
                input_channels=len(input_names),
                horizon_len=horizon_len,
                cfg=cfg,
                seed=model_seed,
            )
        )

    print(f"Initial windows: {len(initial_records)}")
    print(f"Ensemble size: {len(ensemble)}")

    for m, model in enumerate(ensemble):
        train_model(
            model=model,
            records=initial_records,
            cfg=cfg,
            epochs=cfg.epochs_initial,
            desc=f"Initial train {target_name} model {m+1}/{cfg.ensemble_size}",
        )

    init_pred_df, init_metrics = predict_records_ensemble(
        models=ensemble,
        records=initial_records,
        target_name=target_name,
        standardizer=standardizer,
        cfg=cfg,
        phase="initial",
        error_scale=1.0,
        desc=f"Initial eval ensemble {target_name}",
    )

    if not init_pred_df.empty:
        initial_scale = robust_scale_from_errors(init_pred_df["error"].to_numpy())
    else:
        initial_scale = 1.0

    memory: list[WindowRecord] = update_memory([], initial_records, cfg)

    all_pred_dfs: list[pd.DataFrame] = []
    metric_rows: list[dict[str, Any]] = []

    date_min, date_max = get_date_min_max(initial_files)

    initial_row = metrics_row(
        batch_id=0,
        target_name=target_name,
        phase="initial",
        n_files=len(initial_files),
        n_windows=len(initial_records),
        date_min=date_min,
        date_max=date_max,
        memory_pre=init_metrics,
        new_pre=init_metrics,
        new_post=init_metrics,
        memory_post=init_metrics,
    )
    initial_row["generalization_gap_q95"] = 0.0
    initial_row["generalization_ratio_q95"] = 1.0
    initial_row["adaptation_gain_q95"] = 0.0
    initial_row["forgetting_q95"] = 0.0
    metric_rows.append(initial_row)

    holdout_records: list[WindowRecord] = []
    if holdout_files:
        holdout_records = build_windows_for_files(
            files=holdout_files,
            target_name=target_name,
            standardizer=standardizer,
            cfg=cfg,
            desc=f"Holdout windows {target_name}",
        )

        if holdout_records:
            holdout_pre_df, holdout_pre_metrics = predict_records_ensemble(
                models=ensemble,
                records=holdout_records,
                target_name=target_name,
                standardizer=standardizer,
                cfg=cfg,
                phase="holdout_pre",
                error_scale=initial_scale,
                desc=f"Holdout pre eval {target_name}",
            )
            holdout_pre_df["batch_id"] = -1
            all_pred_dfs.append(holdout_pre_df)

            holdout_date_min, holdout_date_max = get_date_min_max(holdout_files)
            holdout_pre_row = metrics_row(
                batch_id=-1,
                target_name=target_name,
                phase="holdout_pre",
                n_files=len(holdout_files),
                n_windows=len(holdout_records),
                date_min=holdout_date_min,
                date_max=holdout_date_max,
                memory_pre=holdout_pre_metrics,
                new_pre=holdout_pre_metrics,
                new_post=holdout_pre_metrics,
                memory_post=holdout_pre_metrics,
            )
            holdout_pre_row["generalization_gap_q95"] = float("nan")
            holdout_pre_row["generalization_ratio_q95"] = float("nan")
            holdout_pre_row["adaptation_gain_q95"] = float("nan")
            holdout_pre_row["forgetting_q95"] = float("nan")
            metric_rows.append(holdout_pre_row)
        else:
            print(f"[WARN] no holdout records for target={target_name}")

    batch_iterator = tqdm(
        list(enumerate(batches[1:], start=1)),
        desc=f"Incremental batches {target_name}",
        unit="batch",
    )

    for batch_id, files in batch_iterator:
        records = build_windows_for_files(
            files=files,
            target_name=target_name,
            standardizer=standardizer,
            cfg=cfg,
            desc=f"Windows {target_name} batch {batch_id}",
        )

        if not records:
            print(f"[WARN] no records for batch {batch_id}, target={target_name}")
            continue

        date_min, date_max = get_date_min_max(files)

        _, memory_pre_metrics = predict_records_ensemble(
            models=ensemble,
            records=memory,
            target_name=target_name,
            standardizer=standardizer,
            cfg=cfg,
            phase="memory_pre",
            error_scale=initial_scale,
            desc=f"Memory pre {target_name} batch {batch_id}",
        )

        pre_df, new_pre_metrics = predict_records_ensemble(
            models=ensemble,
            records=records,
            target_name=target_name,
            standardizer=standardizer,
            cfg=cfg,
            phase="pre",
            error_scale=initial_scale,
            desc=f"New pre {target_name} batch {batch_id}",
        )

        pre_df["batch_id"] = batch_id
        all_pred_dfs.append(pre_df)

        train_records = mix_current_and_memory(records, memory, cfg)

        for m, model in enumerate(ensemble):
            train_model(
                model=model,
                records=train_records,
                cfg=cfg,
                epochs=cfg.epochs_update,
                desc=f"Update {target_name} batch {batch_id} model {m+1}/{cfg.ensemble_size}",
            )

        post_df, new_post_metrics = predict_records_ensemble(
            models=ensemble,
            records=records,
            target_name=target_name,
            standardizer=standardizer,
            cfg=cfg,
            phase="post",
            error_scale=initial_scale,
            desc=f"New post {target_name} batch {batch_id}",
        )

        post_df["batch_id"] = batch_id
        all_pred_dfs.append(post_df)

        _, memory_post_metrics = predict_records_ensemble(
            models=ensemble,
            records=memory,
            target_name=target_name,
            standardizer=standardizer,
            cfg=cfg,
            phase="memory_post",
            error_scale=initial_scale,
            desc=f"Memory post {target_name} batch {batch_id}",
        )

        row_pre = metrics_row(
            batch_id=batch_id,
            target_name=target_name,
            phase="pre",
            n_files=len(files),
            n_windows=len(records),
            date_min=date_min,
            date_max=date_max,
            memory_pre=memory_pre_metrics,
            new_pre=new_pre_metrics,
            new_post=new_post_metrics,
            memory_post=memory_post_metrics,
        )

        row_post = dict(row_pre)
        row_post["phase"] = "post"

        metric_rows.append(row_pre)
        metric_rows.append(row_post)

        memory = update_memory(memory, records, cfg)

        batch_iterator.set_postfix(
            mem_pre=f"{memory_pre_metrics['q95_abs_error']:.4g}",
            new_pre=f"{new_pre_metrics['q95_abs_error']:.4g}",
            gap=f"{row_pre['generalization_gap_q95']:.4g}",
            ratio=f"{row_pre['generalization_ratio_q95']:.3g}",
            post=f"{new_post_metrics['q95_abs_error']:.4g}",
            gain=f"{row_pre['adaptation_gain_q95']:.4g}",
            forget=f"{row_pre['forgetting_q95']:.4g}",
            std=f"{new_pre_metrics['model_q95_abs_error_std']:.4g}",
        )

    if holdout_records:
        holdout_post_df, holdout_post_metrics = predict_records_ensemble(
            models=ensemble,
            records=holdout_records,
            target_name=target_name,
            standardizer=standardizer,
            cfg=cfg,
            phase="holdout_post",
            error_scale=initial_scale,
            desc=f"Holdout post eval {target_name}",
        )
        holdout_post_df["batch_id"] = -1
        all_pred_dfs.append(holdout_post_df)

        date_min, date_max = get_date_min_max(holdout_files)
        holdout_post_row = metrics_row(
            batch_id=-1,
            target_name=target_name,
            phase="holdout_post",
            n_files=len(holdout_files),
            n_windows=len(holdout_records),
            date_min=date_min,
            date_max=date_max,
            memory_pre=holdout_post_metrics,
            new_pre=holdout_post_metrics,
            new_post=holdout_post_metrics,
            memory_post=holdout_post_metrics,
        )
        holdout_post_row["generalization_gap_q95"] = float("nan")
        holdout_post_row["generalization_ratio_q95"] = float("nan")
        holdout_post_row["adaptation_gain_q95"] = float("nan")
        holdout_post_row["forgetting_q95"] = float("nan")
        metric_rows.append(holdout_post_row)

    pred_df = pd.concat(all_pred_dfs, ignore_index=True) if all_pred_dfs else pd.DataFrame()
    metrics_df = pd.DataFrame(metric_rows)

    return pred_df, metrics_df


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "TCN incrémental ensemble pour cohérence inter-canaux, "
            "sans vehicle.speed, avec moyenne ± std des métriques et fill_between."
        )
    )

    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)

    parser.add_argument("--history-sec", type=float, default=4.0)
    parser.add_argument("--horizon-sec", type=float, default=1.0)
    parser.add_argument("--stride-sec", type=float, default=0.5)

    parser.add_argument("--initial-fraction", type=float, default=0.2)
    parser.add_argument(
        "--holdout-fraction",
        type=float,
        default=0.2,
        help="Fraction chronologique finale réservée au test holdout, jamais utilisée pour l'entraînement/adaptation. 0 désactive le holdout.",
    )
    parser.add_argument("--batch-size-files", type=int, default=10)

    parser.add_argument("--epochs-initial", type=int, default=20)
    parser.add_argument("--epochs-update", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-3)

    parser.add_argument("--hidden-channels", type=int, default=64)
    parser.add_argument("--num-tcn-blocks", type=int, default=5)
    parser.add_argument("--dropout", type=float, default=0.05)

    parser.add_argument("--ensemble-size", type=int, default=3)

    parser.add_argument("--memory-max-windows", type=int, default=2000)
    parser.add_argument("--memory-fraction", type=float, default=0.30)

    parser.add_argument("--max-windows-per-file", type=int, default=None)
    parser.add_argument("--time-bin-minutes", type=int, default=60)
    parser.add_argument("--seed", type=int, default=42)

    parser.add_argument(
        "--targets",
        nargs="*",
        default=DEFAULT_TARGETS,
        help=f"Cibles à entraîner. Défaut: {DEFAULT_TARGETS}",
    )

    args = parser.parse_args()

    cfg = Config(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        history_sec=args.history_sec,
        horizon_sec=args.horizon_sec,
        stride_sec=args.stride_sec,
        initial_fraction=args.initial_fraction,
        holdout_fraction=args.holdout_fraction,
        batch_size_files=args.batch_size_files,
        epochs_initial=args.epochs_initial,
        epochs_update=args.epochs_update,
        batch_size=args.batch_size,
        lr=args.lr,
        hidden_channels=args.hidden_channels,
        num_tcn_blocks=args.num_tcn_blocks,
        dropout=args.dropout,
        ensemble_size=args.ensemble_size,
        memory_max_windows_per_target=args.memory_max_windows,
        memory_fraction=args.memory_fraction,
        max_windows_per_file=args.max_windows_per_file,
        time_bin_minutes=args.time_bin_minutes,
        seed=args.seed,
    )

    set_seed(cfg.seed)

    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    (cfg.output_dir / "plots").mkdir(parents=True, exist_ok=True)

    files = sorted(cfg.input_dir.glob("*.json"))

    if not files:
        raise FileNotFoundError(f"No JSON found in {cfg.input_dir}")

    print(f"Input dir: {cfg.input_dir.resolve()}")
    print(f"Output dir: {cfg.output_dir.resolve()}")
    print(f"Files found: {len(files)}")
    print(f"Device: {cfg.device}")
    print(f"Channels used: {BASE_CHANNELS}")
    print(f"Targets: {args.targets}")
    print(f"Ensemble size: {cfg.ensemble_size}")
    print(f"Time bin minutes: {cfg.time_bin_minutes}")
    print("vehicle.speed is NOT used.")

    train_files, holdout_files = split_train_holdout_chronological(files, cfg)
    batches = split_chronological_batches(train_files, cfg)

    print(f"Train/adaptation files: {len(train_files)}")
    print(f"Holdout files: {len(holdout_files)}")
    print(f"Holdout fraction: {cfg.holdout_fraction}")
    if holdout_files:
        print("Holdout files are the last chronological files and are never used for training/adaptation.")
    print(f"Chronological train/adaptation batches: {len(batches)}")
    for i, b in enumerate(batches):
        print(f"  batch {i}: {len(b)} files")

    print("Building channel summaries...")
    file_summary = build_file_channel_summary(files, batches, holdout_files)
    batch_signal_summary = build_batch_signal_summary(file_summary)

    file_summary_path = cfg.output_dir / "file_channel_summary.csv"
    batch_signal_summary_path = cfg.output_dir / "batch_signal_summary.csv"

    file_summary.to_csv(file_summary_path, index=False)
    batch_signal_summary.to_csv(batch_signal_summary_path, index=False)

    print("Fitting global standardizer...")
    standardizer = fit_standardizer(train_files)

    with open(cfg.output_dir / "standardizer.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "mean": standardizer.mean,
                "std": standardizer.std,
                "channels": BASE_CHANNELS,
                "note": "vehicle.speed removed; fitted on train/adaptation files only, excluding holdout",
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    all_pred_dfs: list[pd.DataFrame] = []
    all_metrics_dfs: list[pd.DataFrame] = []

    target_iterator = tqdm(args.targets, desc="Targets", unit="target")

    for target_name in target_iterator:
        if target_name not in BASE_CHANNELS:
            print(f"[WARN] unknown target ignored: {target_name}")
            continue

        target_iterator.set_postfix(target=target_name)

        pred_df, metrics_df = run_for_target(
            target_name=target_name,
            batches=batches,
            holdout_files=holdout_files,
            standardizer=standardizer,
            cfg=cfg,
        )

        if not pred_df.empty:
            all_pred_dfs.append(pred_df)

        if not metrics_df.empty:
            all_metrics_dfs.append(metrics_df)

    predictions = (
        pd.concat(all_pred_dfs, ignore_index=True)
        if all_pred_dfs
        else pd.DataFrame()
    )

    batch_metrics = (
        pd.concat(all_metrics_dfs, ignore_index=True)
        if all_metrics_dfs
        else pd.DataFrame()
    )

    predictions_path = cfg.output_dir / "predictions.csv"
    batch_metrics_path = cfg.output_dir / "batch_metrics.csv"

    predictions.to_csv(predictions_path, index=False)
    batch_metrics.to_csv(batch_metrics_path, index=False)

    print("Aggregating metrics by file and time bin...")

    metrics_by_file = aggregate_prediction_metrics(
        predictions,
        group_cols=["json_name", "target_name", "phase"],
    )

    metrics_by_timebin = aggregate_prediction_metrics(
        predictions,
        group_cols=["date_bin", "time_bin", "target_name", "phase"],
    )

    metrics_by_file_path = cfg.output_dir / "metrics_by_file.csv"
    metrics_by_timebin_path = cfg.output_dir / "metrics_by_timebin.csv"

    metrics_by_file.to_csv(metrics_by_file_path, index=False)
    metrics_by_timebin.to_csv(metrics_by_timebin_path, index=False)

    plot_batch_metrics(batch_metrics, cfg.output_dir / "plots" / "batch_metrics")
    plot_timebin_metrics(metrics_by_timebin, cfg.output_dir / "plots" / "timebins")
    plot_prediction_examples(predictions, cfg.output_dir / "plots" / "predictions")
    plot_holdout_generalization_examples(predictions, cfg.output_dir / "plots" / "holdout_generalization")

    summary = {
        "n_files": len(files),
        "n_train_adapt_files": len(train_files),
        "n_holdout_files": len(holdout_files),
        "n_batches": len(batches),
        "targets": args.targets,
        "base_channels": BASE_CHANNELS,
        "removed_channels": ["vehicle.speed"],
        "ensemble_size": cfg.ensemble_size,
        "time_bin_minutes": cfg.time_bin_minutes,
        "holdout_fraction": cfg.holdout_fraction,
        "holdout_policy": "last chronological files; excluded from standardizer fit, initial training, memory and adaptation",
        "holdout_files": [p.name for p in holdout_files],
        "metrics_added": [
            "model_q95_abs_error_mean",
            "model_q95_abs_error_std",
            "model_mae_mean",
            "model_mae_std",
            "model_relative_q95_error_mean",
            "model_relative_q95_error_std",
            "fill_between plots",
            "ensemble_std",
            "disagreement_score",
            "memory_pre_q95_abs_error",
            "new_pre_q95_abs_error",
            "generalization_gap_q95",
            "generalization_ratio_q95",
            "new_post_q95_abs_error",
            "memory_post_q95_abs_error",
            "adaptation_gain_q95",
            "forgetting_q95",
            "metrics_by_file",
            "metrics_by_timebin",
            "file_channel_summary",
            "batch_signal_summary",
            "holdout_predictions",
            "holdout_generalization_plots",
        ],
        "history_sec": cfg.history_sec,
        "horizon_sec": cfg.horizon_sec,
        "stride_sec": cfg.stride_sec,
        "device": cfg.device,
        "outputs": {
            "predictions": str(predictions_path),
            "batch_metrics": str(batch_metrics_path),
            "metrics_by_file": str(metrics_by_file_path),
            "metrics_by_timebin": str(metrics_by_timebin_path),
            "file_channel_summary": str(file_summary_path),
            "batch_signal_summary": str(batch_signal_summary_path),
            "plots": str(cfg.output_dir / "plots"),
            "holdout_generalization_plots": str(cfg.output_dir / "plots" / "holdout_generalization"),
            "standardizer": str(cfg.output_dir / "standardizer.json"),
        },
    }

    with open(cfg.output_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print()
    print("Done.")
    print(f"Wrote: {predictions_path}")
    print(f"Wrote: {batch_metrics_path}")
    print(f"Wrote: {metrics_by_file_path}")
    print(f"Wrote: {metrics_by_timebin_path}")
    print(f"Wrote: {file_summary_path}")
    print(f"Wrote: {batch_signal_summary_path}")
    print(f"Wrote: {cfg.output_dir / 'summary.json'}")
    print(f"Wrote plots in: {cfg.output_dir / 'plots'}")


if __name__ == "__main__":
    main()
