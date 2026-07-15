from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset
from tqdm.auto import tqdm

from train_incremental_tcn_coherence import (
    build_file_channel_summary,
    build_model_channels,
    get_date_min_max,
    get_file_date,
    make_time_bins,
    parse_acquisition_datetime,
    read_resampled_json,
    robust_mae,
    robust_q95_abs,
    split_chronological_batches,
    split_train_holdout_chronological,
)


DEFAULT_INPUT_DIR = Path("selected_dxd_json_resampled")
DEFAULT_OUTPUT_DIR = Path("neural_ode_anomaly_run")

BASE_CHANNELS = [
    "vehicle.vx",
    "vehicle.ax",
    "vehicle.ay",
    "vehicle.yaw_rate",
    "steer_s1",
    "steer_s2",
]

DEFAULT_TARGETS = [
    "vehicle.ay",
    "vehicle.yaw_rate",
    "steer_s1",
    "steer_s2",
]


def input_channels_for_target(target_name: str) -> list[str]:
    return [name for name in BASE_CHANNELS if name != target_name]


def safe_channel_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in str(name))


@dataclass
class Config:
    input_dir: Path = DEFAULT_INPUT_DIR
    output_dir: Path = DEFAULT_OUTPUT_DIR
    window_sec: float = 6.0
    stride_sec: float = 1.0
    sample_hz: float = 20.0
    initial_fraction: float = 0.8
    holdout_fraction: float = 0.2
    batch_size_files: int = 50
    epochs: int = 20
    batch_size: int = 64
    lr: float = 1e-3
    weight_decay: float = 1e-5
    hidden_dim: int = 64
    num_layers: int = 2
    dropout: float = 0.0
    rollout_steps: int = 10
    max_windows_per_file: int | None = None
    min_valid_ratio: float = 0.95
    time_bin_minutes: int = 60
    max_files: int | None = None
    seed: int = 42
    device: str = "cuda" if torch.cuda.is_available() else "cpu"


@dataclass
class Standardizer:
    mean: dict[str, float]
    std: dict[str, float]

    def transform(self, name: str, x: np.ndarray) -> np.ndarray:
        return (x - self.mean.get(name, 0.0)) / self.std.get(name, 1.0)

    def inverse(self, name: str, x: np.ndarray) -> np.ndarray:
        return x * self.std.get(name, 1.0) + self.mean.get(name, 0.0)


@dataclass
class OdeWindowRecord:
    json_name: str
    date: str
    acquisition_datetime: Any
    start_idx: int
    time: np.ndarray
    commands: np.ndarray
    target: np.ndarray


class OdeWindowDataset(Dataset):
    def __init__(self, records: list[OdeWindowRecord]) -> None:
        self.records = records

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        r = self.records[idx]
        return (
            torch.tensor(r.commands, dtype=torch.float32),
            torch.tensor(r.target, dtype=torch.float32),
        )


class NeuralOdeEuler(nn.Module):
    def __init__(
        self,
        command_dim: int,
        hidden_dim: int,
        num_layers: int,
        dropout: float,
        dt: float,
    ) -> None:
        super().__init__()
        self.dt = float(dt)

        layers: list[nn.Module] = []
        in_dim = command_dim + 1
        for _ in range(max(1, num_layers)):
            layers.append(nn.Linear(in_dim, hidden_dim))
            layers.append(nn.Tanh())
            if dropout > 0:
                layers.append(nn.Dropout(dropout))
            in_dim = hidden_dim
        layers.append(nn.Linear(in_dim, 1))
        self.f = nn.Sequential(*layers)

    def forward(self, commands: torch.Tensor, x0: torch.Tensor) -> torch.Tensor:
        # commands: [B, T, C], x0: [B, 1]
        steps = commands.shape[1]
        x = x0
        preds = [x]
        for k in range(steps - 1):
            dx = self.f(torch.cat([x, commands[:, k, :]], dim=1))
            x = x + self.dt * dx
            preds.append(x)
        return torch.stack(preds, dim=1).squeeze(-1)

    def predict_next(self, commands: torch.Tensor, states: torch.Tensor) -> torch.Tensor:
        # commands: [B, T-1, C], states: [B, T-1]
        x = states.unsqueeze(-1)
        dx = self.f(torch.cat([x, commands], dim=-1))
        return (x + self.dt * dx).squeeze(-1)


def rollout_loss(
    model: NeuralOdeEuler,
    commands: torch.Tensor,
    target: torch.Tensor,
    rollout_steps: int,
    loss_fn: nn.Module,
) -> torch.Tensor:
    steps = min(max(1, int(rollout_steps)), target.shape[1] - 1)
    if steps <= 1:
        pred_next = model.predict_next(commands[:, :-1, :], target[:, :-1])
        return loss_fn(pred_next, target[:, 1:])

    max_start = target.shape[1] - steps
    x = target[:, :max_start]
    losses = []
    for h in range(steps):
        u = commands[:, h:h + max_start, :]
        dx = model.f(torch.cat([x.unsqueeze(-1), u], dim=-1)).squeeze(-1)
        x = x + model.dt * dx
        losses.append(loss_fn(x, target[:, h + 1:h + 1 + max_start]))
    return torch.stack(losses).mean()


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def decimate_to_20hz(
    time: np.ndarray,
    arrays: dict[str, np.ndarray],
    sample_hz: float,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    if len(time) < 2:
        return time, arrays

    dt_target = 1.0 / sample_hz
    t0 = float(time[0])
    t1 = float(time[-1])
    grid = np.arange(t0, t1 + 0.5 * dt_target, dt_target)
    idx = np.searchsorted(time, grid)
    idx = np.clip(idx, 0, len(time) - 1)

    prev_idx = np.clip(idx - 1, 0, len(time) - 1)
    use_prev = np.abs(time[prev_idx] - grid) < np.abs(time[idx] - grid)
    idx = np.where(use_prev, prev_idx, idx)
    idx = np.unique(idx)

    out_time = time[idx].astype(float)
    out_arrays = {name: values[idx].astype(float) for name, values in arrays.items()}
    return out_time, out_arrays


def fit_standardizer(files: list[Path], cfg: Config) -> Standardizer:
    values: dict[str, list[np.ndarray]] = {name: [] for name in BASE_CHANNELS}

    for path in tqdm(files, desc="Fitting Neural ODE standardizer", unit="file"):
        try:
            _, time, raw_channels = read_resampled_json(path)
            model_channels, _ = build_model_channels(time, raw_channels)
            _, model_channels = decimate_to_20hz(time, model_channels, cfg.sample_hz)
            for name in BASE_CHANNELS:
                x = model_channels[name]
                x = x[np.isfinite(x)]
                if len(x):
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


def build_windows_for_file(
    path: Path,
    target_name: str,
    command_names: list[str],
    standardizer: Standardizer,
    cfg: Config,
) -> list[OdeWindowRecord]:
    raw, time, raw_channels = read_resampled_json(path)
    model_channels, _ = build_model_channels(time, raw_channels)
    time, model_channels = decimate_to_20hz(time, model_channels, cfg.sample_hz)

    if len(time) < 3:
        return []

    dt = float(np.nanmedian(np.diff(time)))
    expected_dt = 1.0 / cfg.sample_hz
    if not np.isfinite(dt) or abs(dt - expected_dt) > expected_dt * 0.35:
        return []

    window_len = max(3, int(round(cfg.window_sec * cfg.sample_hz)))
    stride_len = max(1, int(round(cfg.stride_sec * cfg.sample_hz)))
    if len(time) < window_len:
        return []

    arrays = {
        name: standardizer.transform(name, model_channels[name]).astype(np.float32)
        for name in BASE_CHANNELS
    }

    starts = list(range(0, len(time) - window_len + 1, stride_len))
    if cfg.max_windows_per_file is not None and len(starts) > cfg.max_windows_per_file:
        starts = random.sample(starts, cfg.max_windows_per_file)
        starts.sort()

    date = get_file_date(raw, path)
    acquisition_datetime = parse_acquisition_datetime(raw)
    records: list[OdeWindowRecord] = []

    for start in starts:
        sl = slice(start, start + window_len)
        commands = np.stack([arrays[name][sl] for name in command_names], axis=1)
        target = arrays[target_name][sl]
        valid_ratio = np.isfinite(commands).mean() * 0.5 + np.isfinite(target).mean() * 0.5
        if valid_ratio < cfg.min_valid_ratio:
            continue
        records.append(
            OdeWindowRecord(
                json_name=path.name,
                date=date,
                acquisition_datetime=acquisition_datetime,
                start_idx=start,
                time=time[sl].astype(float),
                commands=np.nan_to_num(commands, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32),
                target=np.nan_to_num(target, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32),
            )
        )
    return records


def build_windows_for_files(
    files: list[Path],
    target_name: str,
    standardizer: Standardizer,
    cfg: Config,
    desc: str,
) -> list[OdeWindowRecord]:
    command_names = input_channels_for_target(target_name)
    records: list[OdeWindowRecord] = []
    for path in tqdm(files, desc=desc, unit="file", leave=False):
        try:
            records.extend(build_windows_for_file(path, target_name, command_names, standardizer, cfg))
        except Exception as exc:
            print(f"[WARN] windows failed on {path.name} target={target_name}: {exc}")
    return records


def train_model(
    model: NeuralOdeEuler,
    records: list[OdeWindowRecord],
    cfg: Config,
    desc: str,
) -> None:
    dataset = OdeWindowDataset(records)
    loader = DataLoader(dataset, batch_size=cfg.batch_size, shuffle=True, drop_last=False)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    loss_fn = nn.HuberLoss(delta=1.0)
    model.train()

    for _ in tqdm(range(cfg.epochs), desc=desc, unit="epoch", leave=False):
        losses = []
        for commands, target in loader:
            commands = commands.to(cfg.device)
            target = target.to(cfg.device)
            loss = rollout_loss(model, commands, target, cfg.rollout_steps, loss_fn)

            opt.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
            opt.step()
            losses.append(float(loss.detach().cpu()))


def metric_dict(errors: np.ndarray, y_true: np.ndarray, scale: float) -> dict[str, float]:
    q95_error = robust_q95_abs(errors)
    q95_y = robust_q95_abs(y_true)
    return {
        "mae": robust_mae(errors),
        "q95_abs_error": q95_error,
        "mean_score": float(np.nanmean(np.abs(errors) / scale)) if np.any(np.isfinite(errors)) else float("nan"),
        "q95_score": robust_q95_abs(errors / scale),
        "q95_y_abs": q95_y,
        "relative_q95_error": float(q95_error / (q95_y + 1e-8)) if np.isfinite(q95_y) else float("nan"),
        "ensemble_std_mean": 0.0,
        "ensemble_std_q95": 0.0,
        "disagreement_score_mean": 0.0,
        "disagreement_score_q95": 0.0,
    }


@torch.no_grad()
def predict_records(
    model: NeuralOdeEuler,
    records: list[OdeWindowRecord],
    target_name: str,
    standardizer: Standardizer,
    cfg: Config,
    phase: str,
    error_scale: float,
    desc: str,
) -> tuple[pd.DataFrame, dict[str, float]]:
    if not records:
        return pd.DataFrame(), metric_dict(np.asarray([]), np.asarray([]), error_scale)

    dataset = OdeWindowDataset(records)
    loader = DataLoader(dataset, batch_size=cfg.batch_size, shuffle=False, drop_last=False)
    model.eval()

    rows: list[dict[str, Any]] = []
    errors_all: list[float] = []
    true_all: list[float] = []
    offset = 0

    for commands, target in tqdm(loader, desc=desc, unit="batch", leave=False):
        commands = commands.to(cfg.device)
        target_t = target.to(cfg.device)
        pred_t = target_t.clone()
        if target_t.shape[1] > 1:
            pred_t[:, 1:] = model.predict_next(commands[:, :-1, :], target_t[:, :-1])
        pred_t = pred_t.cpu().numpy()
        target_np = target.numpy()
        bsz = target_np.shape[0]

        for i in range(bsz):
            record = records[offset + i]
            y_true = standardizer.inverse(target_name, target_np[i])
            y_pred = standardizer.inverse(target_name, pred_t[i])
            err = y_true - y_pred
            score = np.abs(err) / error_scale
            errors_all.extend(err[1:][np.isfinite(err[1:])].tolist())
            true_all.extend(y_true[1:][np.isfinite(y_true[1:])].tolist())

            for j in range(len(y_true)):
                date_bin, time_bin, absolute_datetime = make_time_bins(
                    record.acquisition_datetime,
                    float(record.time[j]),
                    cfg.time_bin_minutes,
                )
                rows.append(
                    {
                        "json_name": record.json_name,
                        "date": record.date,
                        "date_bin": date_bin,
                        "time_bin": time_bin,
                        "absolute_datetime": absolute_datetime,
                        "start_idx": int(record.start_idx),
                        "time": float(record.time[j]),
                        "target_name": target_name,
                        "phase": phase,
                        "y_true": float(y_true[j]),
                        "y_pred": float(y_pred[j]),
                        "ensemble_std": 0.0,
                        "error": float(err[j]),
                        "abs_error": float(abs(err[j])),
                        "score": float(score[j]),
                        "disagreement_score": 0.0,
                    }
                )
        offset += bsz

    errors = np.asarray(errors_all, dtype=float)
    true = np.asarray(true_all, dtype=float)
    return pd.DataFrame(rows), metric_dict(errors, true, error_scale)


def aggregate_prediction_metrics(pred_df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if pred_df.empty:
        return pd.DataFrame()
    rows = []
    for keys, group in pred_df.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = {col: val for col, val in zip(group_cols, keys)}
        errors = group["error"].to_numpy(dtype=float)
        y_true = group["y_true"].to_numpy(dtype=float)
        scale = 1.0
        row.update(metric_dict(errors, y_true, scale))
        row["n_points"] = int(len(group))
        row["n_files"] = int(group["json_name"].nunique())
        rows.append(row)
    return pd.DataFrame(rows)


def metrics_row(
    batch_id: int,
    target_name: str,
    phase: str,
    n_files: int,
    n_windows: int,
    date_min: str,
    date_max: str,
    metrics: dict[str, float],
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "batch_id": batch_id,
        "target_name": target_name,
        "phase": phase,
        "n_files": n_files,
        "n_windows": n_windows,
        "date_min": date_min,
        "date_max": date_max,
    }
    for key, value in metrics.items():
        row[key] = value
        row[f"new_pre_{key}"] = value
        row[f"new_post_{key}"] = value
        row[f"memory_pre_{key}"] = value
        row[f"memory_post_{key}"] = value
    row["generalization_gap_q95"] = float("nan")
    row["generalization_ratio_q95"] = float("nan")
    row["adaptation_gain_q95"] = float("nan")
    row["forgetting_q95"] = float("nan")
    return row


def run_for_target(
    target_name: str,
    train_files: list[Path],
    holdout_files: list[Path],
    standardizer: Standardizer,
    cfg: Config,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    print(f"\nTARGET: {target_name}")
    command_names = input_channels_for_target(target_name)
    print(f"Commands: {command_names}")

    train_records = build_windows_for_files(
        train_files,
        target_name,
        standardizer,
        cfg,
        desc=f"Train windows {target_name}",
    )
    if not train_records:
        print(f"[WARN] no train records for target={target_name}")
        return pd.DataFrame(), pd.DataFrame()

    model = NeuralOdeEuler(
        command_dim=len(command_names),
        hidden_dim=cfg.hidden_dim,
        num_layers=cfg.num_layers,
        dropout=cfg.dropout,
        dt=1.0 / cfg.sample_hz,
    ).to(cfg.device)
    train_model(model, train_records, cfg, desc=f"Train Neural ODE {target_name}")

    train_pred, train_metrics_tmp = predict_records(
        model,
        train_records,
        target_name,
        standardizer,
        cfg,
        phase="train",
        error_scale=1.0,
        desc=f"Predict train {target_name}",
    )
    error_scale = robust_q95_abs(train_pred["error"].to_numpy(dtype=float)) if not train_pred.empty else 1.0
    if not np.isfinite(error_scale) or error_scale < 1e-8:
        error_scale = 1.0

    train_pred, train_metrics = predict_records(
        model,
        train_records,
        target_name,
        standardizer,
        cfg,
        phase="train",
        error_scale=error_scale,
        desc=f"Score train {target_name}",
    )

    all_pred = [train_pred]
    metric_rows = []
    date_min, date_max = get_date_min_max(train_files)
    metric_rows.append(
        metrics_row(
            batch_id=0,
            target_name=target_name,
            phase="train",
            n_files=len(train_files),
            n_windows=len(train_records),
            date_min=date_min,
            date_max=date_max,
            metrics=train_metrics,
        )
    )

    if holdout_files:
        holdout_records = build_windows_for_files(
            holdout_files,
            target_name,
            standardizer,
            cfg,
            desc=f"Holdout windows {target_name}",
        )
        if holdout_records:
            holdout_pred, holdout_metrics = predict_records(
                model,
                holdout_records,
                target_name,
                standardizer,
                cfg,
                phase="holdout",
                error_scale=error_scale,
                desc=f"Predict holdout {target_name}",
            )
            holdout_pred["batch_id"] = -1
            all_pred.append(holdout_pred)
            date_min, date_max = get_date_min_max(holdout_files)
            metric_rows.append(
                metrics_row(
                    batch_id=-1,
                    target_name=target_name,
                    phase="holdout",
                    n_files=len(holdout_files),
                    n_windows=len(holdout_records),
                    date_min=date_min,
                    date_max=date_max,
                    metrics=holdout_metrics,
                )
            )

    model_dir = cfg.output_dir / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "target_name": target_name,
            "command_names": command_names,
            "dt": 1.0 / cfg.sample_hz,
            "hidden_dim": cfg.hidden_dim,
            "num_layers": cfg.num_layers,
            "dropout": cfg.dropout,
            "training_loss": "multi_step_euler_rollout",
            "rollout_steps": cfg.rollout_steps,
        },
        model_dir / f"neural_ode__{safe_channel_name(target_name)}.pt",
    )

    return pd.concat(all_pred, ignore_index=True), pd.DataFrame(metric_rows)


def write_json(path: Path, data: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Neural ODE commandée pour détection d'anomalies véhicule.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--window-sec", type=float, default=6.0)
    parser.add_argument("--stride-sec", type=float, default=1.0)
    parser.add_argument("--sample-hz", type=float, default=20.0)
    parser.add_argument("--initial-fraction", type=float, default=0.8)
    parser.add_argument("--holdout-fraction", type=float, default=0.2)
    parser.add_argument("--batch-size-files", type=int, default=50)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-5)
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--num-layers", type=int, default=2)
    parser.add_argument("--dropout", type=float, default=0.0)
    parser.add_argument("--rollout-steps", type=int, default=10, help="Nombre de pas Euler déroulés pendant la loss d'entraînement.")
    parser.add_argument("--max-windows-per-file", type=int, default=None)
    parser.add_argument("--max-files", type=int, default=None, help="Limite de debug sur le nombre de fichiers lus.")
    parser.add_argument("--time-bin-minutes", type=int, default=60)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--targets", nargs="*", default=DEFAULT_TARGETS)
    args = parser.parse_args()

    if abs(args.sample_hz - 20.0) > 1e-9:
        raise ValueError("La spec impose sample_hz=20.0 pour cette première version.")

    cfg = Config(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        window_sec=args.window_sec,
        stride_sec=args.stride_sec,
        sample_hz=args.sample_hz,
        initial_fraction=args.initial_fraction,
        holdout_fraction=args.holdout_fraction,
        batch_size_files=args.batch_size_files,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        weight_decay=args.weight_decay,
        hidden_dim=args.hidden_dim,
        num_layers=args.num_layers,
        dropout=args.dropout,
        rollout_steps=args.rollout_steps,
        max_windows_per_file=args.max_windows_per_file,
        max_files=args.max_files,
        time_bin_minutes=args.time_bin_minutes,
        seed=args.seed,
    )
    set_seed(cfg.seed)
    cfg.output_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(cfg.input_dir.glob("*.json"))
    if cfg.max_files is not None:
        files = files[: max(1, int(cfg.max_files))]
    if not files:
        raise FileNotFoundError(f"No JSON found in {cfg.input_dir}")

    train_files, holdout_files = split_train_holdout_chronological(files, cfg)
    batches = split_chronological_batches(train_files, cfg)

    print(f"Input dir: {cfg.input_dir.resolve()}")
    print(f"Output dir: {cfg.output_dir.resolve()}")
    print(f"Device: {cfg.device}")
    print(f"Files: {len(files)} train={len(train_files)} holdout={len(holdout_files)}")
    print(f"Channels: {BASE_CHANNELS}")
    print(f"Targets: {args.targets}")
    print(f"Neural ODE: Euler explicite, dt=0.05s, 20 Hz, tanh, aucune interpolation, rollout_steps={cfg.rollout_steps}.")

    file_summary = build_file_channel_summary(files, batches, holdout_files)
    file_summary.to_csv(cfg.output_dir / "file_channel_summary.csv", index=False)

    standardizer = fit_standardizer(train_files, cfg)
    write_json(
        cfg.output_dir / "standardizer.json",
        {
            "mean": standardizer.mean,
            "std": standardizer.std,
            "channels": BASE_CHANNELS,
            "fit_policy": "train files only; holdout excluded",
        },
    )

    all_predictions: list[pd.DataFrame] = []
    all_batch_metrics: list[pd.DataFrame] = []
    targets = [str(t) for t in args.targets if str(t) in BASE_CHANNELS]
    for target_name in tqdm(targets, desc="Targets", unit="target"):
        pred_df, metrics_df = run_for_target(target_name, train_files, holdout_files, standardizer, cfg)
        if not pred_df.empty:
            all_predictions.append(pred_df)
        if not metrics_df.empty:
            all_batch_metrics.append(metrics_df)

    predictions = pd.concat(all_predictions, ignore_index=True) if all_predictions else pd.DataFrame()
    batch_metrics = pd.concat(all_batch_metrics, ignore_index=True) if all_batch_metrics else pd.DataFrame()

    predictions.to_csv(cfg.output_dir / "predictions.csv", index=False)
    batch_metrics.to_csv(cfg.output_dir / "batch_metrics.csv", index=False)

    metrics_by_file = aggregate_prediction_metrics(predictions, ["json_name", "target_name", "phase"])
    metrics_by_timebin = aggregate_prediction_metrics(predictions, ["date_bin", "time_bin", "target_name", "phase"])
    metrics_by_file.to_csv(cfg.output_dir / "metrics_by_file.csv", index=False)
    metrics_by_timebin.to_csv(cfg.output_dir / "metrics_by_timebin.csv", index=False)

    config = {
        "model_family": "neural_ode_euler",
        "ode": {
            "integration": "explicit_euler",
            "sample_hz": cfg.sample_hz,
            "dt": 1.0 / cfg.sample_hz,
            "command_interpolation": "none",
            "activation": "tanh",
            "training_loss": "multi_step_euler_rollout",
            "rollout_steps": cfg.rollout_steps,
            "rollout_sec": cfg.rollout_steps / cfg.sample_hz,
            "exported_score": "teacher_forced_one_step_residual",
        },
        "n_files": len(files),
        "n_train_adapt_files": len(train_files),
        "n_holdout_files": len(holdout_files),
        "n_batches": len(batches),
        "targets": targets,
        "base_channels": BASE_CHANNELS,
        "holdout_fraction": cfg.holdout_fraction,
        "holdout_policy": "last chronological files; excluded from standardizer and training",
        "holdout_files": [p.name for p in holdout_files],
        "window_sec": cfg.window_sec,
        "stride_sec": cfg.stride_sec,
        "device": cfg.device,
        "outputs": {
            "predictions": str(cfg.output_dir / "predictions.csv"),
            "batch_metrics": str(cfg.output_dir / "batch_metrics.csv"),
            "metrics_by_file": str(cfg.output_dir / "metrics_by_file.csv"),
            "metrics_by_timebin": str(cfg.output_dir / "metrics_by_timebin.csv"),
            "file_channel_summary": str(cfg.output_dir / "file_channel_summary.csv"),
            "standardizer": str(cfg.output_dir / "standardizer.json"),
            "models": str(cfg.output_dir / "models"),
        },
    }
    write_json(cfg.output_dir / "summary.json", config)
    write_json(cfg.output_dir / "config.json", config)
    print("Done.")


if __name__ == "__main__":
    main()
