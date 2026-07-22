from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from mas_essais.domain.dxd_schema import get_resampled_channels, get_time_values
from mas_essais.paths import PROJECT_ROOT


BASE_DIR = PROJECT_ROOT
RAW_JSON_DIR = BASE_DIR / "selected_dxd_json_resampled"
ANNOTATION_CSV = BASE_DIR / "manual_segment_annotations" / "segments_annotations.csv"
MODEL_DIR = BASE_DIR / "manual_segment_annotations" / "segment_cnn"
MODEL_WEIGHTS_PATH = MODEL_DIR / "model_weights.npz"
MODEL_METADATA_PATH = MODEL_DIR / "model_metadata.json"
MODEL_SUMMARY_PATH = MODEL_DIR / "model_summary.json"
MODEL_PROGRESS_PATH = MODEL_DIR / "model_training_progress.json"

DEFAULT_CHANNELS = (
    "vehicle.ax",
    "vehicle.ay",
    "vehicle.yaw_rate",
)

STANDSTILL_VX_THRESHOLD_MPS = 2.0


def load_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json_atomic(path: Path, data: dict[str, Any], *, indent: int | None = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
        f.write("\n")
    tmp_path.replace(path)


def as_array(values: Any, n: Optional[int] = None) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if n is None:
        return arr
    out = np.full(n, np.nan, dtype=float)
    m = min(len(arr), n)
    if m:
        out[:m] = arr[:m]
    return out


def load_annotation_frame() -> pd.DataFrame:
    if not ANNOTATION_CSV.exists():
        return pd.DataFrame()
    return pd.read_csv(ANNOTATION_CSV)


def load_raw_file(json_name: str) -> dict[str, Any]:
    path = RAW_JSON_DIR / json_name
    if not path.exists():
        raise FileNotFoundError(f"Missing raw file: {path}")
    return load_json(path)


def extract_series(raw: dict[str, Any], channels: Sequence[str] = DEFAULT_CHANNELS) -> tuple[np.ndarray, dict[str, np.ndarray], float]:
    time = as_array(get_time_values(raw))
    n = len(time)
    raw_channels = get_resampled_channels(raw)
    out: dict[str, np.ndarray] = {}
    for name in channels:
        payload = raw_channels.get(name)
        if not isinstance(payload, dict) or "values" not in payload:
            out[name] = np.zeros(n, dtype=float)
            continue
        out[name] = as_array(payload["values"], n)
    target_hz = float(raw.get("pipeline", {}).get("target_hz") or 20.0)
    return time, out, target_hz


def window_median_series(time: np.ndarray, values: np.ndarray, start_sec: float, end_sec: float, window_samples: int) -> float:
    grid = np.linspace(start_sec, end_sec, window_samples, endpoint=False)
    window = finite_interp(time, values, grid)
    if len(window) == 0:
        return float("nan")
    return float(np.nanmedian(window))


def finite_interp(x: np.ndarray, y: np.ndarray, grid: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    if np.sum(mask) < 2:
        return np.zeros(len(grid), dtype=float)
    xp = x[mask]
    yp = y[mask]
    return np.interp(grid, xp, yp, left=yp[0], right=yp[-1])


def extract_window(
    time: np.ndarray,
    channels: dict[str, np.ndarray],
    start_sec: float,
    end_sec: float,
    window_samples: int,
    channel_order: Sequence[str],
) -> np.ndarray:
    grid = np.linspace(start_sec, end_sec, window_samples, endpoint=False)
    rows = []
    for name in channel_order:
        rows.append(finite_interp(time, channels[name], grid))
    return np.asarray(rows, dtype=np.float32)


def sliding_window_starts(segment_start: float, segment_end: float, window_sec: float, stride_sec: float) -> list[float]:
    if segment_end <= segment_start:
        return [segment_start]
    duration = segment_end - segment_start
    if duration <= window_sec:
        center = 0.5 * (segment_start + segment_end)
        return [center - 0.5 * window_sec]

    starts = list(np.arange(segment_start, segment_end - window_sec + 1e-9, stride_sec, dtype=float))
    if not starts:
        starts = [segment_start]
    return [float(s) for s in starts]


def split_files(json_names: Sequence[str], seed: int = 42, test_ratio: float = 0.2, val_ratio: float = 0.2) -> dict[str, set[str]]:
    names = list(dict.fromkeys(json_names))
    rng = np.random.default_rng(seed)
    rng.shuffle(names)

    n = len(names)
    if n == 0:
        return {"train": set(), "val": set(), "test": set()}

    n_test = max(1 if n >= 3 else 0, int(round(n * test_ratio)))
    n_val = max(1 if n >= 4 else 0, int(round(n * val_ratio)))
    if n_test + n_val >= n:
        n_test = 1 if n >= 3 else 0
        n_val = 1 if n >= 4 else 0
    n_train = max(1, n - n_test - n_val)
    if n_train + n_val + n_test > n:
        n_train = n - n_val - n_test

    train = set(names[:n_train])
    val = set(names[n_train:n_train + n_val])
    test = set(names[n_train + n_val:n_train + n_val + n_test])
    leftover = set(names) - train - val - test
    for name in leftover:
        train.add(name)
    return {"train": train, "val": val, "test": test}


def compute_scaler(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    flat = x.transpose(1, 0, 2).reshape(x.shape[1], -1)
    mean = flat.mean(axis=1)
    std = flat.std(axis=1)
    std = np.where(std < 1e-6, 1.0, std)
    return mean.astype(np.float32), std.astype(np.float32)


def apply_scaler(x: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return (x - mean[:, None]) / std[:, None]


def softmax(logits: np.ndarray) -> np.ndarray:
    z = logits - np.max(logits, axis=1, keepdims=True)
    exp = np.exp(z)
    return exp / np.sum(exp, axis=1, keepdims=True)


def cross_entropy_with_grad(logits: np.ndarray, y: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
    probs = softmax(logits)
    n = len(y)
    loss = -np.log(np.clip(probs[np.arange(n), y], 1e-12, 1.0)).mean()
    preds = np.argmax(probs, axis=1)
    grad = probs.copy()
    grad[np.arange(n), y] -= 1.0
    grad /= max(1, n)
    return float(loss), grad.astype(np.float32), preds.astype(int)


def accuracy_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if len(y_true) == 0:
        return 0.0
    return float(np.mean(y_true == y_pred))


def macro_f1(y_true: np.ndarray, y_pred: np.ndarray, n_classes: int) -> float:
    scores = []
    for c in range(n_classes):
        tp = float(np.sum((y_true == c) & (y_pred == c)))
        fp = float(np.sum((y_true != c) & (y_pred == c)))
        fn = float(np.sum((y_true == c) & (y_pred != c)))
        precision = tp / (tp + fp) if tp + fp > 0 else 0.0
        recall = tp / (tp + fn) if tp + fn > 0 else 0.0
        if precision + recall == 0:
            scores.append(0.0)
        else:
            scores.append(2.0 * precision * recall / (precision + recall))
    return float(np.mean(scores)) if scores else 0.0


def confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray, n_classes: int) -> np.ndarray:
    mat = np.zeros((n_classes, n_classes), dtype=int)
    for a, b in zip(y_true, y_pred):
        mat[int(a), int(b)] += 1
    return mat


def time_step_from_time(time: np.ndarray) -> float:
    diffs = np.diff(time[np.isfinite(time)])
    diffs = diffs[diffs > 0]
    if len(diffs) == 0:
        return 0.05
    return float(np.median(diffs))


def build_dataset(
    annotations: pd.DataFrame,
    window_sec: float = 4.0,
    stride_sec: float = 1.0,
    channels: Sequence[str] = DEFAULT_CHANNELS,
    standstill_vx_threshold_mps: float = STANDSTILL_VX_THRESHOLD_MPS,
    seed: int = 42,
) -> dict[str, Any]:
    if annotations.empty:
        raise RuntimeError("No annotations available")

    annotations = annotations.copy()
    annotations = annotations[annotations["label"].notna()]
    annotations = annotations[annotations["json_name"].notna()]
    if annotations.empty:
        raise RuntimeError("No labeled annotations available")

    json_names = sorted(str(v) for v in annotations["json_name"].unique())
    splits = split_files(json_names, seed=seed)
    label_names = sorted(str(v) for v in annotations["label"].astype(str).unique())
    if "standstill" not in label_names:
        label_names = ["standstill"] + label_names
    label_to_idx = {name: idx for idx, name in enumerate(label_names)}

    samples: list[np.ndarray] = []
    labels: list[int] = []
    sample_meta: list[dict[str, Any]] = []
    file_cache: dict[str, tuple[np.ndarray, dict[str, np.ndarray], float]] = {}

    for _, row in annotations.iterrows():
        json_name = str(row["json_name"])
        label = str(row["label"])
        if json_name not in file_cache:
            raw = load_raw_file(json_name)
            requested_channels = tuple(dict.fromkeys((*channels, "vehicle.vx")))
            file_cache[json_name] = extract_series(raw, requested_channels)
        time, series, target_hz = file_cache[json_name]
        window_samples = max(8, int(round(window_sec * target_hz)))
        segment_start = float(row["start_sec"])
        segment_end = float(row["end_sec"])
        starts = sliding_window_starts(segment_start, segment_end, window_sec, stride_sec)
        for start in starts:
            end = start + window_sec
            x = extract_window(time, series, start, end, window_samples, channels)
            vx_median_mps = window_median_series(time, series["vehicle.vx"], start, end, window_samples)
            effective_label = label
            standstill_bypass = False
            if np.isfinite(vx_median_mps) and vx_median_mps < float(standstill_vx_threshold_mps) and "standstill" in label_to_idx:
                effective_label = "standstill"
                standstill_bypass = label != "standstill"
            samples.append(x)
            labels.append(label_to_idx[effective_label])
            sample_meta.append(
                {
                    "json_name": json_name,
                    "label": label,
                    "effective_label": effective_label,
                    "start_sec": float(start),
                    "end_sec": float(end),
                    "segment_start_sec": segment_start,
                    "segment_end_sec": segment_end,
                    "vx_median_mps": vx_median_mps,
                    "standstill_bypass": standstill_bypass,
                    "split": "train" if json_name in splits["train"] else "val" if json_name in splits["val"] else "test",
                }
            )

    if not samples:
        raise RuntimeError("No training windows could be built")

    x = np.stack(samples, axis=0).astype(np.float32)
    y = np.asarray(labels, dtype=int)
    meta = pd.DataFrame(sample_meta)
    train_mask = meta["split"].astype(str) == "train"
    val_mask = meta["split"].astype(str) == "val"
    test_mask = meta["split"].astype(str) == "test"

    x_train = x[train_mask.to_numpy()]
    y_train = y[train_mask.to_numpy()]
    x_val = x[val_mask.to_numpy()]
    y_val = y[val_mask.to_numpy()]
    x_test = x[test_mask.to_numpy()]
    y_test = y[test_mask.to_numpy()]

    if len(x_val) == 0 and len(x_train) > 1:
        x_val = x_train[-1:]
        y_val = y_train[-1:]
        x_train = x_train[:-1]
        y_train = y_train[:-1]
    if len(x_test) == 0 and len(x_train) > 1:
        x_test = x_train[-1:]
        y_test = y_train[-1:]
        x_train = x_train[:-1]
        y_train = y_train[:-1]

    mean, std = compute_scaler(x_train)
    x_train = apply_scaler(x_train, mean, std)
    x_val = apply_scaler(x_val, mean, std) if len(x_val) else x_val
    x_test = apply_scaler(x_test, mean, std) if len(x_test) else x_test
    x_all = apply_scaler(x, mean, std)

    return {
        "x_all": x_all,
        "y_all": y,
        "x_train": x_train,
        "y_train": y_train,
        "x_val": x_val,
        "y_val": y_val,
        "x_test": x_test,
        "y_test": y_test,
        "meta": meta,
        "label_names": label_names,
        "label_to_idx": label_to_idx,
        "splits": {k: sorted(v) for k, v in splits.items()},
        "channels": list(channels),
        "window_sec": float(window_sec),
        "stride_sec": float(stride_sec),
        "standstill_vx_threshold_mps": float(standstill_vx_threshold_mps),
        "window_samples": int(x.shape[2]),
        "mean": mean,
        "std": std,
    }


def pad_to_length(x: np.ndarray, target_len: int) -> np.ndarray:
    if x.shape[-1] >= target_len:
        return x[..., :target_len]
    pad = target_len - x.shape[-1]
    return np.pad(x, ((0, 0), (0, 0), (0, pad)), mode="constant")


def conv1d_forward(x: np.ndarray, w: np.ndarray, b: np.ndarray, pad: int) -> tuple[np.ndarray, dict[str, Any]]:
    xpad = np.pad(x, ((0, 0), (0, 0), (pad, pad)), mode="constant")
    windows = np.lib.stride_tricks.sliding_window_view(xpad, window_shape=w.shape[-1], axis=2)
    out = np.tensordot(windows, w, axes=([1, 3], [1, 2])) + b[None, None, :]
    out = np.transpose(out, (0, 2, 1)).astype(np.float32)
    cache = {"xpad": xpad, "windows": windows, "w": w, "pad": pad}
    return out, cache


def conv1d_backward(dout: np.ndarray, cache: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    xpad = cache["xpad"]
    windows = cache["windows"]
    w = cache["w"]
    pad = int(cache["pad"])
    dout_t = np.transpose(dout, (0, 2, 1))
    db = np.sum(dout_t, axis=(0, 1))
    dw = np.tensordot(dout_t, windows, axes=([0, 1], [0, 2])).astype(np.float32)
    dwindows = np.tensordot(dout_t, w, axes=([2], [0]))
    dwindows = np.transpose(dwindows, (0, 2, 1, 3))
    dxpad = np.zeros_like(xpad, dtype=np.float32)
    k = w.shape[-1]
    for i in range(k):
        dxpad[:, :, i:i + dwindows.shape[2]] += dwindows[:, :, :, i]
    if pad > 0:
        dx = dxpad[:, :, pad:-pad]
    else:
        dx = dxpad
    return dx.astype(np.float32), dw.astype(np.float32), db.astype(np.float32)


def relu_forward(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return np.maximum(x, 0.0), x


def relu_backward(dout: np.ndarray, cache: np.ndarray) -> np.ndarray:
    return dout * (cache > 0.0)


def avgpool1d_forward(x: np.ndarray, pool_size: int = 2) -> tuple[np.ndarray, dict[str, Any]]:
    b, c, t = x.shape
    pad = (pool_size - (t % pool_size)) % pool_size
    xpad = np.pad(x, ((0, 0), (0, 0), (0, pad)), mode="constant")
    t2 = xpad.shape[2] // pool_size
    out = xpad.reshape(b, c, t2, pool_size).mean(axis=-1)
    cache = {"input_len": t, "pool_size": pool_size, "pad": pad}
    return out.astype(np.float32), cache


def avgpool1d_backward(dout: np.ndarray, cache: dict[str, Any]) -> np.ndarray:
    input_len = int(cache["input_len"])
    pool_size = int(cache["pool_size"])
    pad = int(cache["pad"])
    b, c, t2 = dout.shape
    dxpad = np.repeat(dout[:, :, :, None] / float(pool_size), pool_size, axis=-1).reshape(b, c, t2 * pool_size)
    if pad > 0:
        dxpad = dxpad[:, :, :input_len + pad]
    return dxpad[:, :, :input_len].astype(np.float32)


def dense_forward(x: np.ndarray, w: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    out = x @ w + b
    return out.astype(np.float32), {"x": x, "w": w}


def dense_backward(dout: np.ndarray, cache: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x = cache["x"]
    w = cache["w"]
    dx = dout @ w.T
    dw = x.T @ dout
    db = np.sum(dout, axis=0)
    return dx.astype(np.float32), dw.astype(np.float32), db.astype(np.float32)


@dataclass
class TrainingConfig:
    window_sec: float = 4.0
    stride_sec: float = 1.0
    epochs: int = 40
    batch_size: int = 32
    learning_rate: float = 1e-3
    patience: Optional[int] = None
    standstill_vx_threshold_mps: float = STANDSTILL_VX_THRESHOLD_MPS
    seed: int = 42
    channels: Tuple[str, ...] = DEFAULT_CHANNELS


class Simple1DCNN:
    def __init__(self, n_channels: int, n_classes: int, seed: int = 42):
        self.n_channels = int(n_channels)
        self.n_classes = int(n_classes)
        self.rng = np.random.default_rng(seed)
        self.params: dict[str, np.ndarray] = {}
        self.opt_m: dict[str, np.ndarray] = {}
        self.opt_v: dict[str, np.ndarray] = {}
        self.opt_t = 0
        self._init_params()

    def _init_params(self) -> None:
        def he(shape: tuple[int, ...], fan_in: int) -> np.ndarray:
            return self.rng.normal(0.0, math.sqrt(2.0 / fan_in), size=shape).astype(np.float32)

        self.params = {
            "conv1_w": he((16, self.n_channels, 5), self.n_channels * 5),
            "conv1_b": np.zeros(16, dtype=np.float32),
            "conv2_w": he((32, 16, 5), 16 * 5),
            "conv2_b": np.zeros(32, dtype=np.float32),
            "conv3_w": he((64, 32, 3), 32 * 3),
            "conv3_b": np.zeros(64, dtype=np.float32),
            "dense1_w": he((64, 64), 64),
            "dense1_b": np.zeros(64, dtype=np.float32),
            "dense2_w": he((64, self.n_classes), 64),
            "dense2_b": np.zeros(self.n_classes, dtype=np.float32),
        }
        self.opt_m = {k: np.zeros_like(v) for k, v in self.params.items()}
        self.opt_v = {k: np.zeros_like(v) for k, v in self.params.items()}

    def forward(self, x: np.ndarray, training: bool = False) -> tuple[np.ndarray, dict[str, Any]]:
        cache: dict[str, Any] = {}
        z1, c1 = conv1d_forward(x, self.params["conv1_w"], self.params["conv1_b"], pad=2)
        a1, r1 = relu_forward(z1)
        p1, p1c = avgpool1d_forward(a1, pool_size=2)
        z2, c2 = conv1d_forward(p1, self.params["conv2_w"], self.params["conv2_b"], pad=2)
        a2, r2 = relu_forward(z2)
        p2, p2c = avgpool1d_forward(a2, pool_size=2)
        z3, c3 = conv1d_forward(p2, self.params["conv3_w"], self.params["conv3_b"], pad=1)
        a3, r3 = relu_forward(z3)
        gap = a3.mean(axis=2)
        z4, c4 = dense_forward(gap, self.params["dense1_w"], self.params["dense1_b"])
        a4, r4 = relu_forward(z4)
        logits, c5 = dense_forward(a4, self.params["dense2_w"], self.params["dense2_b"])
        cache.update(
            {
                "conv1": c1,
                "relu1": r1,
                "pool1": p1c,
                "conv2": c2,
                "relu2": r2,
                "pool2": p2c,
                "conv3": c3,
                "relu3": r3,
                "gap_shape": a3.shape,
                "dense1": c4,
                "relu4": r4,
                "dense2": c5,
            }
        )
        return logits.astype(np.float32), cache

    def backward(self, dlogits: np.ndarray, cache: dict[str, Any]) -> dict[str, np.ndarray]:
        grads: dict[str, np.ndarray] = {}
        da4, grads["dense2_w"], grads["dense2_b"] = dense_backward(dlogits, cache["dense2"])
        dz4 = relu_backward(da4, cache["relu4"])
        dgap, grads["dense1_w"], grads["dense1_b"] = dense_backward(dz4, cache["dense1"])
        a3_shape = cache["gap_shape"]
        da3 = np.repeat(dgap[:, :, None] / float(a3_shape[2]), a3_shape[2], axis=2)
        dz3 = relu_backward(da3, cache["relu3"])
        dp2, grads["conv3_w"], grads["conv3_b"] = conv1d_backward(dz3, cache["conv3"])
        da2 = avgpool1d_backward(dp2, cache["pool2"])
        dz2 = relu_backward(da2, cache["relu2"])
        dp1, grads["conv2_w"], grads["conv2_b"] = conv1d_backward(dz2, cache["conv2"])
        da1 = avgpool1d_backward(dp1, cache["pool1"])
        dz1 = relu_backward(da1, cache["relu1"])
        dx, grads["conv1_w"], grads["conv1_b"] = conv1d_backward(dz1, cache["conv1"])
        grads["input"] = dx
        return grads

    def _adam_update(self, grads: dict[str, np.ndarray], lr: float, weight_decay: float = 0.0) -> None:
        self.opt_t += 1
        beta1 = 0.9
        beta2 = 0.999
        eps = 1e-8
        for name, param in self.params.items():
            grad = grads[name]
            if weight_decay > 0.0:
                grad = grad + weight_decay * param
            m = self.opt_m[name] = beta1 * self.opt_m[name] + (1.0 - beta1) * grad
            v = self.opt_v[name] = beta2 * self.opt_v[name] + (1.0 - beta2) * (grad * grad)
            mhat = m / (1.0 - beta1 ** self.opt_t)
            vhat = v / (1.0 - beta2 ** self.opt_t)
            self.params[name] = param - lr * mhat / (np.sqrt(vhat) + eps)

    def predict_proba(self, x: np.ndarray, batch_size: int = 128) -> np.ndarray:
        probs: list[np.ndarray] = []
        for i in range(0, len(x), batch_size):
            logits, _ = self.forward(x[i:i + batch_size], training=False)
            probs.append(softmax(logits))
        if not probs:
            return np.zeros((0, self.n_classes), dtype=np.float32)
        return np.concatenate(probs, axis=0)

    def predict(self, x: np.ndarray, batch_size: int = 128) -> np.ndarray:
        probs = self.predict_proba(x, batch_size=batch_size)
        return np.argmax(probs, axis=1)

    def evaluate(self, x: np.ndarray, y: np.ndarray, batch_size: int = 128) -> dict[str, Any]:
        if len(x) == 0:
            return {"loss": None, "accuracy": None, "macro_f1": None, "n_samples": 0}
        losses = []
        preds = []
        for i in range(0, len(x), batch_size):
            logits, _ = self.forward(x[i:i + batch_size], training=False)
            loss, _, batch_preds = cross_entropy_with_grad(logits.copy(), y[i:i + batch_size].copy())
            losses.append(loss)
            preds.append(batch_preds)
        pred = np.concatenate(preds, axis=0)
        return {
            "loss": float(np.mean(losses)),
            "accuracy": accuracy_score(y, pred),
            "macro_f1": macro_f1(y, pred, self.n_classes),
            "n_samples": int(len(x)),
            "confusion_matrix": confusion_matrix(y, pred, self.n_classes).tolist(),
        }

    def fit(
        self,
        x_train: np.ndarray,
        y_train: np.ndarray,
        x_val: np.ndarray,
        y_val: np.ndarray,
        epochs: int = 40,
        batch_size: int = 32,
        learning_rate: float = 1e-3,
        patience: Optional[int] = None,
        weight_decay: float = 1e-4,
    ) -> dict[str, Any]:
        best_state = {k: v.copy() for k, v in self.params.items()}
        best_val = float("inf")
        best_epoch = -1
        history: list[dict[str, Any]] = []
        bad_epochs = 0
        use_early_stopping = patience is not None and patience > 0
        idx = np.arange(len(x_train))
        for epoch in range(1, epochs + 1):
            self.rng.shuffle(idx)
            x_epoch = x_train[idx]
            y_epoch = y_train[idx]
            losses = []
            preds = []
            for i in range(0, len(x_epoch), batch_size):
                xb = x_epoch[i:i + batch_size]
                yb = y_epoch[i:i + batch_size]
                logits, cache = self.forward(xb, training=True)
                loss, dlogits, batch_preds = cross_entropy_with_grad(logits.copy(), yb.copy())
                grads = self.backward(dlogits, cache)
                self._adam_update(grads, learning_rate, weight_decay=weight_decay)
                losses.append(loss)
                preds.append(batch_preds)
            train_pred = np.concatenate(preds, axis=0) if preds else np.zeros((0,), dtype=int)
            train_loss = float(np.mean(losses)) if losses else None
            train_acc = accuracy_score(y_epoch, train_pred) if len(train_pred) else None
            val_eval = self.evaluate(x_val, y_val, batch_size=batch_size)
            history.append(
                {
                    "epoch": epoch,
                    "train_loss": train_loss,
                    "train_accuracy": train_acc,
                    "val_loss": val_eval["loss"],
                    "val_accuracy": val_eval["accuracy"],
                    "val_macro_f1": val_eval["macro_f1"],
                }
            )
            progress = {
                "status": "running",
                "epoch": epoch,
                "epochs": epochs,
                "patience": patience,
                "early_stopping": use_early_stopping,
                "bad_epochs": bad_epochs,
                "best_epoch": best_epoch,
                "best_val_loss": best_val,
                "latest": history[-1],
                "history": history,
            }
            write_json_atomic(MODEL_PROGRESS_PATH, progress)
            print(
                f"[epoch {epoch:03d}/{epochs:03d}] "
                f"train_loss={train_loss:.4f} train_acc={train_acc:.3f} "
                f"val_loss={val_eval['loss']:.4f} val_acc={val_eval['accuracy']:.3f} "
                f"val_macro_f1={val_eval['macro_f1']:.3f} "
                f"best_epoch={best_epoch} bad_epochs={bad_epochs}/{patience if use_early_stopping else 'off'}",
                flush=True,
            )
            if val_eval["loss"] is not None and val_eval["loss"] < best_val - 1e-6:
                best_val = float(val_eval["loss"])
                best_state = {k: v.copy() for k, v in self.params.items()}
                best_epoch = epoch
                bad_epochs = 0
            else:
                bad_epochs += 1
            if use_early_stopping and bad_epochs >= int(patience):
                break
        self.params = best_state
        final_progress = {
            "status": "finished",
            "best_epoch": best_epoch,
            "best_val_loss": best_val,
            "history": history,
        }
        write_json_atomic(MODEL_PROGRESS_PATH, final_progress)
        return {"history": history, "best_epoch": best_epoch, "best_val_loss": best_val}

    def save(self, path: Path, metadata: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, **self.params)
        with open(MODEL_METADATA_PATH, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, weights_path: Path, metadata_path: Path = MODEL_METADATA_PATH) -> tuple["Simple1DCNN", dict[str, Any]]:
        if not weights_path.exists() or not metadata_path.exists():
            raise FileNotFoundError("Missing model artifact")
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        model = cls(
            n_channels=int(metadata["n_channels"]),
            n_classes=int(metadata["n_classes"]),
            seed=int(metadata.get("seed", 42)),
        )
        weights = np.load(weights_path)
        for k in model.params:
            model.params[k] = weights[k]
        return model, metadata


def train_from_annotations(config: Optional[TrainingConfig] = None) -> dict[str, Any]:
    cfg = config or TrainingConfig()
    annotations = load_annotation_frame()
    if annotations.empty:
        raise RuntimeError("No annotations found")
    dataset = build_dataset(
        annotations,
        window_sec=cfg.window_sec,
        stride_sec=cfg.stride_sec,
        channels=cfg.channels,
        standstill_vx_threshold_mps=cfg.standstill_vx_threshold_mps,
        seed=cfg.seed,
    )

    model = Simple1DCNN(n_channels=len(dataset["channels"]), n_classes=len(dataset["label_names"]), seed=cfg.seed)
    fit_info = model.fit(
        dataset["x_train"],
        dataset["y_train"],
        dataset["x_val"],
        dataset["y_val"],
        epochs=cfg.epochs,
        batch_size=cfg.batch_size,
        learning_rate=cfg.learning_rate,
        patience=cfg.patience,
    )

    train_metrics = model.evaluate(dataset["x_train"], dataset["y_train"], batch_size=cfg.batch_size)
    val_metrics = model.evaluate(dataset["x_val"], dataset["y_val"], batch_size=cfg.batch_size)
    test_metrics = model.evaluate(dataset["x_test"], dataset["y_test"], batch_size=cfg.batch_size)

    metadata = {
        "schema_version": "segment_cnn_model.v1",
        "seed": cfg.seed,
        "n_channels": int(len(dataset["channels"])),
        "n_classes": int(len(dataset["label_names"])),
        "channels": dataset["channels"],
        "label_names": dataset["label_names"],
        "label_to_idx": dataset["label_to_idx"],
        "window_sec": dataset["window_sec"],
        "stride_sec": dataset["stride_sec"],
        "standstill_vx_threshold_mps": dataset["standstill_vx_threshold_mps"],
        "window_samples": dataset["window_samples"],
        "mean": dataset["mean"].tolist(),
        "std": dataset["std"].tolist(),
        "splits": dataset["splits"],
        "train_metrics": train_metrics,
        "val_metrics": val_metrics,
        "test_metrics": test_metrics,
        "fit_info": fit_info,
        "n_samples": int(len(dataset["x_all"])),
        "n_train": int(len(dataset["x_train"])),
        "n_val": int(len(dataset["x_val"])),
        "n_test": int(len(dataset["x_test"])),
    }

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model.save(MODEL_WEIGHTS_PATH, metadata)
    with open(MODEL_SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    return metadata


def load_model_summary() -> dict[str, Any]:
    if not MODEL_SUMMARY_PATH.exists():
        return {
            "status": "missing",
            "message": "Run scripts/train_segment_cnn.py to build the baseline 1D-CNN.",
            "model_path": str(MODEL_WEIGHTS_PATH),
            "summary_path": str(MODEL_SUMMARY_PATH),
            "progress_path": str(MODEL_PROGRESS_PATH),
        }
    with open(MODEL_SUMMARY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["status"] = "ok"
    data["model_path"] = str(MODEL_WEIGHTS_PATH)
    data["summary_path"] = str(MODEL_SUMMARY_PATH)
    data["progress_path"] = str(MODEL_PROGRESS_PATH)
    return data


def _smooth_probabilities(probs: np.ndarray, radius: int = 2) -> np.ndarray:
    if len(probs) == 0:
        return probs
    out = np.zeros_like(probs)
    for i in range(len(probs)):
        a = max(0, i - radius)
        b = min(len(probs), i + radius + 1)
        out[i] = probs[a:b].mean(axis=0)
    return out


def _merge_runs(labels: Sequence[str], starts: Sequence[float], ends: Sequence[float], confs: Sequence[float]) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    if not labels:
        return runs
    cur_label = labels[0]
    cur_start = starts[0]
    cur_end = ends[0]
    cur_confs = [confs[0]]
    for i in range(1, len(labels)):
        if labels[i] == cur_label and abs(starts[i] - cur_end) <= 1e-6:
            cur_end = ends[i]
            cur_confs.append(confs[i])
        else:
            runs.append(
                {
                    "label": cur_label,
                    "start_sec": float(cur_start),
                    "end_sec": float(cur_end),
                    "duration_sec": float(cur_end - cur_start),
                    "confidence": float(np.mean(cur_confs)),
                }
            )
            cur_label = labels[i]
            cur_start = starts[i]
            cur_end = ends[i]
            cur_confs = [confs[i]]
    runs.append(
        {
            "label": cur_label,
            "start_sec": float(cur_start),
            "end_sec": float(cur_end),
            "duration_sec": float(cur_end - cur_start),
            "confidence": float(np.mean(cur_confs)),
        }
    )
    return runs


def _merge_overlapping_predictions(
    windows: Sequence[dict[str, Any]],
    probs: np.ndarray,
    label_names: Sequence[str],
    min_duration_sec: float,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    if len(windows) == 0 or len(probs) == 0:
        return []

    bounds = sorted({float(w["start_sec"]) for w in windows} | {float(w["end_sec"]) for w in windows})
    if len(bounds) < 2:
        return []

    interval_segments: list[dict[str, Any]] = []
    for left, right in zip(bounds[:-1], bounds[1:]):
        if right <= left:
            continue
        active = [
            i for i, w in enumerate(windows)
            if float(w["start_sec"]) < right and float(w["end_sec"]) > left
        ]
        if not active:
            continue

        weights = np.array(
            [
                max(0.0, min(float(windows[i]["end_sec"]), right) - max(float(windows[i]["start_sec"]), left))
                for i in active
            ],
            dtype=np.float32,
        )
        weights = np.where(weights > 0, weights, 0.0)
        if float(np.sum(weights)) <= 0:
            continue

        scores = np.zeros(len(label_names), dtype=np.float32)
        for weight, idx in zip(weights, active):
            scores += probs[idx] * float(weight)

        label_idx = int(np.argmax(scores))
        label = label_names[label_idx]
        confidence = float(scores[label_idx] / max(1e-12, float(np.sum(scores))))
        interval_segments.append(
            {
                "label": label,
                "start_sec": float(left),
                "end_sec": float(right),
                "duration_sec": float(right - left),
                "confidence": confidence,
            }
        )

    merged: list[dict[str, Any]] = []
    for seg in interval_segments:
        if seg["duration_sec"] < min_duration_sec:
            continue
        if merged and seg["label"] == merged[-1]["label"] and abs(seg["start_sec"] - merged[-1]["end_sec"]) <= 1e-6:
            merged[-1]["end_sec"] = seg["end_sec"]
            merged[-1]["duration_sec"] = float(merged[-1]["end_sec"] - merged[-1]["start_sec"])
            merged[-1]["confidence"] = float((merged[-1]["confidence"] + seg["confidence"]) / 2.0)
        else:
            merged.append(seg)

    for seg in merged:
        seg["top_k"] = {}
    for seg in merged:
        a = seg["start_sec"]
        b = seg["end_sec"]
        active = [
            i for i, w in enumerate(windows)
            if float(w["start_sec"]) < b and float(w["end_sec"]) > a
        ]
        if not active:
            continue
        weighted = np.zeros(len(label_names), dtype=np.float32)
        for idx in active:
            weighted += probs[idx]
        top = np.argsort(weighted)[::-1][:top_k]
        seg["top_k"] = {label_names[int(i)]: float(weighted[int(i)] / max(1e-12, float(np.sum(weighted)))) for i in top}
    return merged


def _merge_adjacent_same_label(
    segments: Sequence[dict[str, Any]],
    gap_sec: float,
) -> list[dict[str, Any]]:
    if not segments:
        return []

    ordered = sorted(segments, key=lambda r: (float(r["start_sec"]), float(r["end_sec"])))
    merged: list[dict[str, Any]] = [dict(ordered[0])]
    for seg in ordered[1:]:
        prev = merged[-1]
        gap = float(seg["start_sec"]) - float(prev["end_sec"])
        if seg["label"] == prev["label"] and gap <= gap_sec:
            prev["end_sec"] = max(float(prev["end_sec"]), float(seg["end_sec"]))
            prev["duration_sec"] = float(prev["end_sec"] - prev["start_sec"])
            prev["confidence"] = float((float(prev["confidence"]) + float(seg["confidence"])) / 2.0)
            if "top_k" in prev and "top_k" in seg:
                combined = dict(prev["top_k"])
                for label, value in seg["top_k"].items():
                    combined[label] = float((combined.get(label, 0.0) + float(value)) / 2.0)
                prev["top_k"] = combined
        else:
            merged.append(dict(seg))
    return merged


def _load_existing_segments_for_file(json_name: str) -> list[tuple[float, float, str, str]]:
    df = load_annotation_frame()
    if df.empty or "json_name" not in df.columns:
        return []
    df = df[df["json_name"].astype(str) == str(json_name)]
    out: list[tuple[float, float, str, str]] = []
    for _, row in df.iterrows():
        out.append(
            (
                float(row.get("start_sec", 0.0)),
                float(row.get("end_sec", 0.0)),
                str(row.get("label", "")),
                str(row.get("annotation_id", "")),
            )
        )
    return out

def export_predictions(output_csv: Path | str = MODEL_DIR / "cnn_predictions.csv", stride_sec: float = 1.0) -> pd.DataFrame:
    model, metadata = Simple1DCNN.load(MODEL_WEIGHTS_PATH, MODEL_METADATA_PATH)

    annotations = load_annotation_frame()
    if annotations.empty:
        raise RuntimeError("No annotations available")

    json_names = sorted(str(v) for v in annotations["json_name"].dropna().unique())

    rows = []
    for json_name in json_names:
        result = predict_file(
            json_name=json_name,
            model=model,
            metadata=metadata,
            stride_sec=stride_sec,
        )

        for w in result["windows"]:
            rows.append({
                "json_name": json_name,
                "start_sec": w["start_sec"],
                "end_sec": w["end_sec"],
                "label": w["label"],
                "confidence": w["confidence"],
                "source": w["source"],
                "vx_median_mps": w["vx_median_mps"],
                "proba": json.dumps(w.get("proba", {}), ensure_ascii=False),
            })

    df = pd.DataFrame(rows)
    output_csv = Path(output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv, index=False)
    return df
def predict_file(
    json_name: str,
    model: Simple1DCNN,
    metadata: dict[str, Any],
    stride_sec: float = 1.0,
    smooth_radius: int = 2,
    top_k: int = 3,
) -> dict[str, Any]:
    raw = load_raw_file(json_name)
    requested_channels = tuple(dict.fromkeys((*metadata["channels"], "vehicle.vx")))
    time, series, _ = extract_series(raw, requested_channels)
    window_sec = float(metadata["window_sec"])
    standstill_vx_threshold_mps = float(metadata.get("standstill_vx_threshold_mps", STANDSTILL_VX_THRESHOLD_MPS))
    target_hz = float(raw.get("pipeline", {}).get("target_hz") or 20.0)
    window_samples = max(8, int(round(window_sec * target_hz)))
    file_start = float(np.nanmin(time))
    file_end = float(np.nanmax(time))
    starts = list(np.arange(file_start, max(file_start, file_end - window_sec + 1e-9), stride_sec, dtype=float))
    if not starts:
        starts = [file_start]

    windows = []
    window_x = []
    window_vx = []
    heuristic_mask = []
    for start in starts:
        end = start + window_sec
        x = extract_window(time, series, start, end, window_samples, metadata["channels"])
        windows.append({"start_sec": float(start), "end_sec": float(end)})
        vx_median_mps = window_median_series(time, series["vehicle.vx"], start, end, window_samples)
        is_standstill = np.isfinite(vx_median_mps) and vx_median_mps < standstill_vx_threshold_mps
        window_vx.append(vx_median_mps)
        heuristic_mask.append(bool(is_standstill))
        window_x.append(x)

    if not window_x:
        return {"windows": [], "suggestions": [], "class_names": metadata["label_names"]}

    x = np.stack(window_x, axis=0).astype(np.float32)
    mean = np.asarray(metadata["mean"], dtype=np.float32)
    std = np.asarray(metadata["std"], dtype=np.float32)
    x = apply_scaler(x, mean, std)
    probs = np.zeros((len(x), len(metadata["label_names"])), dtype=np.float32)
    model_indices = [i for i, bypass in enumerate(heuristic_mask) if not bypass]
    if model_indices:
        model_probs = model.predict_proba(x[model_indices])
        model_probs = _smooth_probabilities(model_probs, radius=smooth_radius)
        for j, i in enumerate(model_indices):
            probs[i] = model_probs[j]
    standstill_idx = metadata["label_names"].index("standstill") if "standstill" in metadata["label_names"] else None
    pred_idx = np.argmax(probs, axis=1)
    pred_labels = [metadata["label_names"][int(i)] for i in pred_idx]
    pred_conf = [float(probs[i, pred_idx[i]]) for i in range(len(pred_idx))]
    for i, bypass in enumerate(heuristic_mask):
        if bypass:
            if standstill_idx is not None:
                probs[i, standstill_idx] = 1.0
            pred_labels[i] = "standstill"
            pred_conf[i] = 1.0

    for i, w in enumerate(windows):
        if heuristic_mask[i]:
            w["label"] = "standstill"
            w["confidence"] = 1.0
            w["proba"] = {"standstill": 1.0}
            w["source"] = "rule:vx<threshold"
            w["vx_median_mps"] = float(window_vx[i])
            continue
        top = np.argsort(probs[i])[::-1][:top_k]
        w["label"] = pred_labels[i]
        w["confidence"] = pred_conf[i]
        w["proba"] = {metadata["label_names"][int(j)]: float(probs[i, j]) for j in top}
        w["source"] = "cnn"
        w["vx_median_mps"] = float(window_vx[i])

    runs = _merge_runs(
        pred_labels,
        [w["start_sec"] for w in windows],
        [w["end_sec"] for w in windows],
        pred_conf,
    )
    merged_runs = _merge_overlapping_predictions(
        windows=windows,
        probs=probs,
        label_names=metadata["label_names"],
        min_duration_sec=max(0.5, float(stride_sec) * 0.5),
        top_k=top_k,
    )
    merged_runs = _merge_adjacent_same_label(
        merged_runs,
        gap_sec=max(float(stride_sec), 0.5),
    )
    existing = _load_existing_segments_for_file(json_name)
    suggestions = []
    for run in merged_runs:
        if run["label"] == "mixed_or_unknown":
            continue
        overlap = None
        for start, end, label, annotation_id in existing:
            inter = max(0.0, min(end, run["end_sec"]) - max(start, run["start_sec"]))
            union = max(end, run["end_sec"]) - min(start, run["start_sec"])
            if union > 0 and inter / union >= 0.5:
                overlap = {
                    "annotation_id": annotation_id,
                    "label": label,
                    "start_sec": start,
                    "end_sec": end,
                }
                break
        suggestions.append({**run, "existing_annotation": overlap})

    suggestions = sorted(suggestions, key=lambda r: (float(r["start_sec"]), float(r["end_sec"])))
    return {
        "json_name": json_name,
        "window_sec": window_sec,
        "stride_sec": float(stride_sec),
        "standstill_vx_threshold_mps": standstill_vx_threshold_mps,
        "class_names": metadata["label_names"],
        "windows": windows,
        "suggestions": suggestions,
        "merged_runs": merged_runs,
        "n_windows": len(windows),
        "n_rule_windows": int(sum(heuristic_mask)),
    }


ACTIVE_LEARNING_CACHE_PATH = BASE_DIR / "manual_segment_annotations" / "active_learning_cache.json"

def generate_active_learning_cache(metadata: dict[str, Any]) -> None:
    try:
        from mas_essais.ml.segment_cnn.model import Simple1DCNN, predict_file
        model, meta = Simple1DCNN.load(MODEL_WEIGHTS_PATH, MODEL_METADATA_PATH)
        
        json_names = sorted(p.name for p in RAW_JSON_DIR.glob("*.json"))
        
        cache = {}
        for i, name in enumerate(json_names):
            try:
                write_json_atomic(MODEL_PROGRESS_PATH, {
                    "status": "calculating_uncertainty",
                    "current": i,
                    "total": len(json_names),
                    "file": name
                })
                
                res = predict_file(json_name=name, model=model, metadata=meta, stride_sec=2.0)
                windows = res.get("windows", [])
                cnn_windows = [w for w in windows if w.get("source") == "cnn"]
                
                if cnn_windows:
                    entropies = []
                    for w in cnn_windows:
                        probs = w.get("proba", {})
                        ent = 0.0
                        for p in probs.values():
                            if p > 0:
                                ent -= p * math.log(p)
                        entropies.append(ent)
                    uncertainty = float(np.mean(entropies))
                else:
                    uncertainty = 0.0
                    
                cache[name] = {
                    "uncertainty": uncertainty,
                    "n_windows": len(cnn_windows)
                }
            except Exception:
                cache[name] = {
                    "uncertainty": 0.0,
                    "n_windows": 0
                }
                
        ACTIVE_LEARNING_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(ACTIVE_LEARNING_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "model_summary_sha256": str(metadata.get("fit_info", {}).get("best_val_loss")),
                "files": cache
            }, f, indent=2)
            
        write_json_atomic(MODEL_PROGRESS_PATH, {
            "status": "finished",
            "best_epoch": metadata.get("fit_info", {}).get("best_epoch"),
            "best_val_loss": metadata.get("fit_info", {}).get("best_val_loss")
        })
            
    except Exception as e:
        print(f"Error generating active learning cache: {e}")
