"""CLI for group2 training command generation."""

from __future__ import annotations

import argparse
from pathlib import Path

from core.train.base import default_dataset_yaml, default_project_dir, execute_training_job
from core.train.group2.service import build_group2_training_job


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the group2 YOLO training command.")
    parser.add_argument(
        "--dataset-yaml",
        type=Path,
        required=False,
        help="optional; defaults to <cwd>/datasets/group2/<dataset-version>/yolo/dataset.yaml",
    )
    parser.add_argument("--dataset-version", default="v1")
    parser.add_argument(
        "--project",
        type=Path,
        required=False,
        help="optional; defaults to <cwd>/runs/group2",
    )
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
    train_root = Path.cwd()
    dataset_yaml = args.dataset_yaml or default_dataset_yaml(train_root, "group2", args.dataset_version)
    project_dir = args.project or default_project_dir(train_root, "group2")
    job = build_group2_training_job(
        dataset_yaml=dataset_yaml,
        project_dir=project_dir,
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
