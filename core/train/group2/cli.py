"""CLI for group2 training command generation."""

from __future__ import annotations

import argparse
from pathlib import Path

from core.train.base import (
    default_best_weights,
    default_dataset_config,
    default_last_weights,
    default_project_dir,
)
from core.train.group2.service import build_group2_training_job, execute_group2_training_job


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the group2 paired-input training command.")
    parser.add_argument(
        "--dataset-config",
        type=Path,
        required=False,
        help="optional; defaults to <cwd>/datasets/group2/<dataset-version>/dataset.json",
    )
    parser.add_argument("--dataset-version", default="v1")
    parser.add_argument(
        "--project",
        type=Path,
        required=False,
        help="optional; defaults to <cwd>/runs/group2",
    )
    parser.add_argument("--name", default="v1")
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--from-run",
        default=None,
        help="optional; defaults model to <cwd>/runs/group2/<from-run>/weights/best.pt",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="resume the current run from <cwd>/runs/group2/<name>/weights/last.pt",
    )
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--batch", type=int, default=None)
    parser.add_argument("--imgsz", type=int, default=192)
    parser.add_argument("--device", default="0")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.resume and args.from_run:
        parser.error("不能同时传 --resume 和 --from-run。")
    if args.from_run and args.model is not None:
        parser.error("传入 --from-run 时不要再同时传 --model。")

    train_root = Path.cwd()
    dataset_config = args.dataset_config or default_dataset_config(train_root, "group2", args.dataset_version)
    project_dir = args.project or default_project_dir(train_root, "group2")
    model = args.model or "paired_cnn_v1"
    if args.resume and args.model is None:
        model = str(default_last_weights(train_root, "group2", args.name))
    elif args.from_run is not None:
        model = str(default_best_weights(train_root, "group2", args.from_run))
    job = build_group2_training_job(
        dataset_config=dataset_config,
        project_dir=project_dir,
        model=model,
        run_name=args.name,
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        device=args.device,
        resume=args.resume,
    )
    if args.dry_run:
        print(job.command_string())
        return 0
    try:
        return execute_group2_training_job(job)
    except RuntimeError as err:
        parser.exit(1, f"{err}\n")


if __name__ == "__main__":
    raise SystemExit(main())
