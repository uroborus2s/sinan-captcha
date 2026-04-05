"""CLI for group1 two-model training command generation."""

from __future__ import annotations

import argparse
from pathlib import Path

from core.train.base import default_project_dir
from core.train.group1.service import (
    QUERY_COMPONENT,
    SCENE_COMPONENT,
    build_group1_training_job,
    execute_group1_training_job,
    group1_component_best_weights,
    group1_component_last_weights,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the group1 two-model training command.")
    parser.add_argument(
        "--dataset-config",
        type=Path,
        required=False,
        help="optional; defaults to <cwd>/datasets/group1/<dataset-version>/dataset.json",
    )
    parser.add_argument("--dataset-version", default="v1")
    parser.add_argument(
        "--project",
        type=Path,
        required=False,
        help="optional; defaults to <cwd>/runs/group1",
    )
    parser.add_argument("--name", default="v1")
    parser.add_argument("--model", default=None, help="shared base model/checkpoint for both sub-models")
    parser.add_argument("--scene-model", default=None, help="optional override for the scene detector")
    parser.add_argument("--query-model", default=None, help="optional override for the query parser")
    parser.add_argument(
        "--from-run",
        default=None,
        help="optional; defaults sub-model checkpoints to <cwd>/runs/group1/<from-run>/*/weights/best.pt",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="resume the current run from <cwd>/runs/group1/<name>/*/weights/last.pt",
    )
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--batch", type=int, default=None)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="0")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.resume and args.from_run:
        parser.error("不能同时传 --resume 和 --from-run。")
    if args.from_run and any(value is not None for value in (args.model, args.scene_model, args.query_model)):
        parser.error("传入 --from-run 时不要再同时传 --model / --scene-model / --query-model。")

    train_root = Path.cwd()
    dataset_config = args.dataset_config or (train_root / "datasets" / "group1" / args.dataset_version / "dataset.json")
    project_dir = args.project or default_project_dir(train_root, "group1")

    shared_model = args.model or "yolo26n.pt"
    scene_model = args.scene_model or shared_model
    query_model = args.query_model or shared_model
    if args.resume:
        scene_model = str(group1_component_last_weights(train_root, args.name, SCENE_COMPONENT))
        query_model = str(group1_component_last_weights(train_root, args.name, QUERY_COMPONENT))
    elif args.from_run is not None:
        scene_model = str(group1_component_best_weights(train_root, args.from_run, SCENE_COMPONENT))
        query_model = str(group1_component_best_weights(train_root, args.from_run, QUERY_COMPONENT))

    job = build_group1_training_job(
        dataset_config=dataset_config,
        project_dir=project_dir,
        model=shared_model,
        scene_model=scene_model,
        query_model=query_model,
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
        return execute_group1_training_job(job)
    except RuntimeError as err:
        parser.exit(1, f"{err}\n")


if __name__ == "__main__":
    raise SystemExit(main())
