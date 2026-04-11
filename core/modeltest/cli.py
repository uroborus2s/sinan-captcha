"""CLI for novice-friendly end-to-end model test flows."""

from __future__ import annotations

import argparse
from pathlib import Path

from core.modeltest.service import ModelTestRequest, build_model_test_jobs, run_model_test
from core.train.base import default_best_weights, default_dataset_config, default_predict_source, default_report_dir
from core.train.group1.service import (
    PROPOSAL_COMPONENT,
    QUERY_COMPONENT,
    resolve_group1_component_best_weights,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run predict + evaluate together and export a beginner-friendly Chinese report."
    )
    subparsers = parser.add_subparsers(dest="task", required=True)

    group1_parser = subparsers.add_parser("group1", help="test group1 model")
    group1_parser.add_argument(
        "--dataset-config",
        type=Path,
        required=False,
        help="optional; defaults to <cwd>/datasets/group1/<dataset-version>/dataset.json",
    )
    group1_parser.add_argument("--dataset-version", default="v1")
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
    group1_parser.add_argument("--project", type=Path, required=False, help="optional; defaults to <cwd>/reports/group1")
    group1_parser.add_argument("--predict-name", default=None)
    group1_parser.add_argument("--val-name", default=None)
    group1_parser.add_argument(
        "--report-dir",
        type=Path,
        required=False,
        help="optional; defaults to <cwd>/reports/group1/test_<train-name>",
    )
    group1_parser.add_argument("--conf", type=float, default=0.25)
    group1_parser.add_argument("--device", default="0")
    group1_parser.add_argument("--imgsz", type=int, default=640)
    group1_parser.add_argument("--dry-run", action="store_true")

    group2_parser = subparsers.add_parser("group2", help="test group2 model")
    group2_parser.add_argument(
        "--dataset-config",
        type=Path,
        required=False,
        help="optional; defaults to <cwd>/datasets/group2/<dataset-version>/dataset.json",
    )
    group2_parser.add_argument("--dataset-version", default="v1")
    group2_parser.add_argument("--model", type=Path, required=False)
    group2_parser.add_argument("--train-name", default="v1")
    group2_parser.add_argument(
        "--source",
        type=Path,
        required=False,
        help="optional; defaults to <cwd>/datasets/group2/<dataset-version>/splits/val.jsonl",
    )
    group2_parser.add_argument("--project", type=Path, required=False, help="optional; defaults to <cwd>/reports/group2")
    group2_parser.add_argument("--predict-name", default=None)
    group2_parser.add_argument("--val-name", default=None)
    group2_parser.add_argument(
        "--report-dir",
        type=Path,
        required=False,
        help="optional; defaults to <cwd>/reports/group2/test_<train-name>",
    )
    group2_parser.add_argument("--conf", type=float, default=0.25)
    group2_parser.add_argument("--device", default="0")
    group2_parser.add_argument("--imgsz", type=int, default=640)
    group2_parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    train_root = Path.cwd()
    task = str(args.task)
    dataset_config = args.dataset_config or default_dataset_config(train_root, task, args.dataset_version)
    source = args.source or default_predict_source(train_root, task, args.dataset_version)
    project_dir = args.project or default_report_dir(train_root, task)
    predict_name = args.predict_name or f"predict_{args.train_name}"
    val_name = args.val_name or f"val_{args.train_name}"
    report_dir = args.report_dir or (project_dir / f"test_{args.train_name}")

    if task == "group1":
        proposal_model = args.proposal_model or resolve_group1_component_best_weights(train_root, args.train_name, PROPOSAL_COMPONENT)
        query_model = args.query_model or resolve_group1_component_best_weights(train_root, args.train_name, QUERY_COMPONENT)
        request = ModelTestRequest(
            task=task,
            dataset_version=args.dataset_version,
            train_name=args.train_name,
            dataset_config=dataset_config,
            model_path=proposal_model,
            query_model_path=query_model,
            source=source,
            project_dir=project_dir,
            report_dir=report_dir,
            predict_name=predict_name,
            val_name=val_name,
            conf=args.conf,
            device=args.device,
            imgsz=args.imgsz,
        )
    else:
        model_path = args.model or default_best_weights(train_root, task, args.train_name)
        request = ModelTestRequest(
            task=task,
            dataset_version=args.dataset_version,
            train_name=args.train_name,
            dataset_config=dataset_config,
            model_path=model_path,
            query_model_path=None,
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
