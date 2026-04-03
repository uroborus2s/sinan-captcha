"""CLI for group1 training command generation."""

from __future__ import annotations

import argparse
from pathlib import Path

from core.train.base import execute_training_job
from core.train.group1.service import build_group1_training_job


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the group1 YOLO training command.")
    parser.add_argument("--dataset-yaml", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--name", default="v1")
    parser.add_argument("--model", default="yolo26n.pt")
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--batch", type=int, default=None)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="0")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    job = build_group1_training_job(
        dataset_yaml=args.dataset_yaml,
        project_dir=args.project,
        model=args.model,
        run_name=args.name,
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        device=args.device,
    )
    if args.dry_run:
        print(job.command_string())
        return 0
    try:
        return execute_training_job(job)
    except RuntimeError as err:
        parser.exit(1, f"{err}\n")


if __name__ == "__main__":
    raise SystemExit(main())
