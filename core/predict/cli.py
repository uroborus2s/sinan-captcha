"""CLI for prediction commands with Sinan defaults."""

from __future__ import annotations

import argparse
from pathlib import Path

from core.predict.service import PredictionJob, execute_prediction_job
from core.train.base import default_best_weights, default_dataset_config, default_predict_source, default_report_dir
from core.train.group1.service import (
    PROPOSAL_COMPONENT,
    QUERY_COMPONENT,
    build_group1_prediction_job,
    resolve_group1_component_best_weights,
    run_group1_prediction_job,
)
from core.train.group2.service import build_group2_prediction_job, run_group2_prediction_job


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run task-specific prediction with Sinan default model/source/project paths."
    )
    subparsers = parser.add_subparsers(dest="task", required=True)

    group1_parser = subparsers.add_parser("group1", help="run group1 pipeline prediction")
    group1_parser.add_argument(
        "--dataset-config",
        type=Path,
        required=False,
        help="optional; defaults to <cwd>/datasets/group1/<dataset-version>/dataset.json",
    )
    group1_parser.add_argument("--proposal-model", dest="proposal_model", type=Path, required=False)
    group1_parser.add_argument("--scene-model", dest="proposal_model", type=Path, required=False, help=argparse.SUPPRESS)
    group1_parser.add_argument("--query-model", type=Path, required=False)
    group1_parser.add_argument("--train-name", default="v1")
    group1_parser.add_argument(
        "--source",
        type=Path,
        required=False,
        help="optional; defaults to <cwd>/datasets/group1/<dataset-version>/splits/val.jsonl",
    )
    group1_parser.add_argument("--dataset-version", default="v1")
    group1_parser.add_argument("--project", type=Path, required=False, help="optional; defaults to <cwd>/reports/group1")
    group1_parser.add_argument("--name", default=None)
    group1_parser.add_argument("--conf", type=float, default=0.25)
    group1_parser.add_argument("--device", default="0")
    group1_parser.add_argument("--imgsz", type=int, default=640)
    group1_parser.add_argument("--dry-run", action="store_true")

    group2_parser = subparsers.add_parser("group2", help="run group2 prediction")
    group2_parser.add_argument(
        "--dataset-config",
        type=Path,
        required=False,
        help="optional; defaults to <cwd>/datasets/group2/<dataset-version>/dataset.json",
    )
    group2_parser.add_argument("--model", type=Path, required=False)
    group2_parser.add_argument("--train-name", default="v1")
    group2_parser.add_argument(
        "--source",
        type=Path,
        required=False,
        help="optional; defaults to <cwd>/datasets/group2/<dataset-version>/splits/val.jsonl",
    )
    group2_parser.add_argument("--dataset-version", default="v1")
    group2_parser.add_argument("--project", type=Path, required=False, help="optional; defaults to <cwd>/reports/group2")
    group2_parser.add_argument("--name", default=None)
    group2_parser.add_argument("--conf", type=float, default=0.25)
    group2_parser.add_argument("--device", default="0")
    group2_parser.add_argument("--imgsz", type=int, default=192)
    group2_parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    train_root = Path.cwd()
    task = str(args.task)
    project_dir = args.project or default_report_dir(train_root, task)
    run_name = args.name or f"predict_{args.train_name}"

    if task == "group1":
        dataset_config = args.dataset_config or default_dataset_config(train_root, task, args.dataset_version)
        source = args.source or default_predict_source(train_root, task, args.dataset_version)
        proposal_model = args.proposal_model or resolve_group1_component_best_weights(train_root, args.train_name, PROPOSAL_COMPONENT)
        query_model = args.query_model or resolve_group1_component_best_weights(train_root, args.train_name, QUERY_COMPONENT)
        job = build_group1_prediction_job(
            dataset_config=dataset_config,
            proposal_model_path=proposal_model,
            query_model_path=query_model,
            source=source,
            project_dir=project_dir,
            run_name=run_name,
            conf=args.conf,
            imgsz=args.imgsz,
            device=args.device,
        )
        if args.dry_run:
            print(job.command_string())
            return 0
        try:
            run_group1_prediction_job(job)
            return 0
        except RuntimeError as err:
            parser.exit(1, f"{err}\n")

    model_path = args.model or default_best_weights(train_root, task, args.train_name)
    source = args.source or default_predict_source(train_root, task, args.dataset_version)
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
