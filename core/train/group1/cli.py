"""CLI for group1 training command generation."""

from __future__ import annotations

import argparse
from pathlib import Path

from core.train.group1.service import build_group1_training_job


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Print the group1 YOLO training command.")
    parser.add_argument("--dataset-yaml", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--name", default="v1")
    parser.add_argument("--model", default="yolo26n.pt")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    job = build_group1_training_job(
        dataset_yaml=args.dataset_yaml,
        project_dir=args.project,
        model=args.model,
        run_name=args.name,
    )
    print(" ".join(str(part) for part in job.command()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
