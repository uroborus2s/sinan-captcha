"""CLI for group2 training command generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.train.base import (
    default_best_weights,
    default_dataset_config,
    default_last_weights,
    default_project_dir,
)
from core.train.group2.service import build_group2_training_job, execute_group2_training_job
from core.train.prelabel import Group2PrelabelRequest, build_group2_prelabel_plan, run_group2_prelabel


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


def build_prelabel_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prelabel a group2 reviewed exam workspace for X-AnyLabeling.")
    parser.add_argument("--exam-root", type=Path, required=True)
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
        help="optional; defaults to <exam-root>/.sinan/prelabel/group2/predict",
    )
    parser.add_argument("--train-name", default="v1")
    parser.add_argument("--model", type=Path, required=False)
    parser.add_argument("--name", default="prelabel")
    parser.add_argument("--imgsz", type=int, default=192)
    parser.add_argument("--device", default="0")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args_list = list(argv or [])
    if args_list and args_list[0] == "prelabel":
        return _run_prelabel_cli(args_list[1:])

    parser = build_parser()
    args = parser.parse_args(args_list)
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


def _run_prelabel_cli(argv: list[str]) -> int:
    parser = build_prelabel_parser()
    args = parser.parse_args(argv)

    train_root = Path.cwd()
    exam_root = args.exam_root
    dataset_config = args.dataset_config or default_dataset_config(train_root, "group2", args.dataset_version)
    model = args.model or default_best_weights(train_root, "group2", args.train_name)
    project_dir = args.project or (exam_root / ".sinan" / "prelabel" / "group2" / "predict")
    request = Group2PrelabelRequest(
        exam_root=exam_root,
        dataset_config=dataset_config,
        model_path=model,
        project_dir=project_dir,
        run_name=args.name,
        imgsz=args.imgsz,
        device=args.device,
        limit=args.limit,
        overwrite=args.overwrite,
    )
    if args.dry_run:
        print(build_group2_prelabel_plan(request).prediction_job.command_string())
        return 0

    try:
        result = run_group2_prelabel(request)
    except RuntimeError as err:
        parser.exit(1, f"{err}\n")
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
