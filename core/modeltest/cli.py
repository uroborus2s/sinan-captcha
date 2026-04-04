"""CLI for novice-friendly end-to-end model test flows."""

from __future__ import annotations

import argparse
from pathlib import Path

from core.modeltest.service import ModelTestRequest, build_model_test_jobs, run_model_test
from core.train.base import (
    default_best_weights,
    default_dataset_yaml,
    default_predict_source,
    default_report_dir,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run predict + val together and export a beginner-friendly Chinese report."
    )
    subparsers = parser.add_subparsers(dest="task", required=True)
    for task in ("group1", "group2"):
        task_parser = subparsers.add_parser(task, help=f"test {task} model")
        task_parser.add_argument(
            "--dataset-yaml",
            type=Path,
            required=False,
            help=f"optional; defaults to <cwd>/datasets/{task}/<dataset-version>/yolo/dataset.yaml",
        )
        task_parser.add_argument("--dataset-version", default="v1")
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
            help=f"optional; defaults to <cwd>/datasets/{task}/<dataset-version>/yolo/images/val",
        )
        task_parser.add_argument(
            "--project",
            type=Path,
            required=False,
            help=f"optional; defaults to <cwd>/reports/{task}",
        )
        task_parser.add_argument("--predict-name", default=None)
        task_parser.add_argument("--val-name", default=None)
        task_parser.add_argument(
            "--report-dir",
            type=Path,
            required=False,
            help=f"optional; defaults to <cwd>/reports/{task}/test_<train-name>",
        )
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
    dataset_yaml = args.dataset_yaml or default_dataset_yaml(train_root, task, args.dataset_version)
    model_path = args.model or default_best_weights(train_root, task, args.train_name)
    source = args.source or default_predict_source(train_root, task, args.dataset_version)
    project_dir = args.project or default_report_dir(train_root, task)
    predict_name = args.predict_name or f"predict_{args.train_name}"
    val_name = args.val_name or f"val_{args.train_name}"
    report_dir = args.report_dir or (project_dir / f"test_{args.train_name}")

    request = ModelTestRequest(
        task=task,
        dataset_version=args.dataset_version,
        train_name=args.train_name,
        dataset_yaml=dataset_yaml,
        model_path=model_path,
        source=source,
        project_dir=project_dir,
        report_dir=report_dir,
        predict_name=predict_name,
        val_name=val_name,
        conf=args.conf,
        device=args.device,
        imgsz=args.imgsz,
    )

    if args.dry_run:
        predict_job, val_job = build_model_test_jobs(request)
        print(predict_job.command_string())
        print(val_job.command_string())
        print(f"report={report_dir}")
        return 0

    try:
        result = run_model_test(request)
    except RuntimeError as err:
        parser.exit(1, f"{err}\n")

    print(result.render_console_report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
