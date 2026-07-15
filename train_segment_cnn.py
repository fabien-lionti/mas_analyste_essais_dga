from __future__ import annotations

import argparse
import json
from pathlib import Path

from segment_cnn_model import MODEL_PROGRESS_PATH, MODEL_SUMMARY_PATH, TrainingConfig, train_from_annotations


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the baseline 1D-CNN on segment annotations.")
    parser.add_argument("--window-sec", type=float, default=4.0)
    parser.add_argument("--stride-sec", type=float, default=1.0)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--patience", type=int, default=None, help="Active l'arrêt anticipé après N époques sans amélioration. Par défaut, désactivé.")
    parser.add_argument("--standstill-vx-threshold", type=float, default=2.0, help="Seuil vx en m/s au-dessous duquel une fenêtre est forcée en standstill.")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = TrainingConfig(
        window_sec=args.window_sec,
        stride_sec=args.stride_sec,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        patience=args.patience,
        standstill_vx_threshold_mps=args.standstill_vx_threshold,
        seed=args.seed,
    )
    summary = train_from_annotations(cfg)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Wrote: {MODEL_SUMMARY_PATH}")
    print(f"Progress: {MODEL_PROGRESS_PATH}")


if __name__ == "__main__":
    main()
