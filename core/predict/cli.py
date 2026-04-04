"""CLI for prediction commands with Sinan defaults."""

from __future__ import annotations

import argparse
from pathlib import Path

from core.predict.service import PredictionJob, execute_prediction_job
from core.train.base import (
    default_best_weights,
    default_dataset_config,
    default_predict_source,
    default_report_dir,
)
from core.train.group2.service import build_group2_prediction_job, run_group2_prediction_job


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run YOLO detect predict with Sinan default model/source/project paths."
    )
    subparsers = parser.add_subparsers(dest="task", required=True)
    for task in ("group1", "group2"):
        task_parser = subparsers.add_parser(task, help=f"run {task} prediction")
        if task == "group2":
            task_parser.add_argument(
                "--dataset-config",
                type=Path,
                required=False,
                help="optional; defaults to <cwd>/datasets/group2/<dataset-version>/dataset.json",
            )
        task_parser.add_argument(
            "--model",
            type=Path,
            required=False,
            help=f"optional; defaults to <cwd>/runs/{task}/<train-name>/weights/best.pt",
        )
        task_parser.add_argument("--train-name", default="v1")
        task_parser.add_argument(
            "--source",
            type=Path,
            required=False,
            help=(
                f"optional; defaults to <cwd>/datasets/{task}/<dataset-version>/yolo/images/val"
                if task == "group1"
                else f"optional; defaults to <cwd>/datasets/{task}/<dataset-version>/splits/val.jsonl"
            ),
        )
        task_parser.add_argument("--dataset-version", default="v1")
        task_parser.add_argument(
            "--project",
            type=Path,
            required=False,
            help=f"optional; defaults to <cwd>/reports/{task}",
        )
        task_parser.add_argument("--name", default=None)
        task_parser.add_argument("--conf", type=float, default=0.25)
        task_parser.add_argument("--device", default="0")
        task_parser.add_argument("--imgsz", type=int, default=640)
        task_parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    train_root = Path.cwd()
    task = str(args.task)
    model_path = args.model or default_best_weights(train_root, task, args.train_name)
    source = args.source or default_predict_source(train_root, task, args.dataset_version)
    project_dir = args.project or default_report_dir(train_root, task)
    run_name = args.name or f"predict_{args.train_name}"
    if task == "group2":
        dataset_config = args.dataset_config or default_dataset_config(train_root, task, args.dataset_version)
        job = build_group2_prediction_job(
            dataset_config=dataset_config,
            model_path=model_path,
            source=source,
            project_dir=project_dir,
            run_name=run_name,
            imgsz=args.imgsz,
            device=args.device,
        )
        if args.dry_run:
            print(job.command_string())
            return 0
        try:
            run_group2_prediction_job(job)
            return 0
        except RuntimeError as err:
            parser.exit(1, f"{err}\n")

    job = PredictionJob(
        task=task,
        model_path=model_path,
        source=source,
        project_dir=project_dir,
        run_name=run_name,
        conf=args.conf,
        device=args.device,
        imgsz=args.imgsz,
    )

    if args.dry_run:
        print(job.command_string())
        return 0

    try:
        return execute_prediction_job(job)
    except RuntimeError as err:
        parser.exit(1, f"{err}\n")


if __name__ == "__main__":
    raise SystemExit(main())
