"""CLI for group1 proposal-detector/query-parser training command generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.train.base import default_project_dir, default_train_root
from core.train.group1.dataset import load_group1_dataset_config
from core.train.group1.service import (
    ALL_COMPONENTS,
    EMBEDDER_COMPONENT,
    PROPOSAL_COMPONENT,
    QUERY_COMPONENT,
    build_group1_training_job,
    execute_group1_training_job,
    normalize_group1_component,
    resolve_group1_component_best_weights,
    resolve_group1_component_last_weights,
)
from core.train.prelabel import (
    Group1PrelabelRequest,
    Group1QueryDirectoryPrelabelRequest,
    build_group1_prelabel_plan,
    build_group1_query_directory_prelabel_plan,
    run_group1_prelabel,
    run_group1_query_directory_prelabel,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the group1 proposal-detector/query-parser training command.")
    parser.add_argument(
        "--dataset-config",
        type=Path,
        required=False,
        help="optional; defaults to <repo>/work_home/datasets/group1/<dataset-version>/dataset.json",
    )
    parser.add_argument("--dataset-version", default="v1")
    parser.add_argument(
        "--project",
        type=Path,
        required=False,
        help="optional; defaults to <repo>/work_home/runs/group1",
    )
    parser.add_argument("--name", default="v1")
    parser.add_argument("--component", default=ALL_COMPONENTS, help="all | proposal-detector | query-parser | icon-embedder")
    parser.add_argument("--model", default=None, help="shared base model/checkpoint for both sub-models")
    parser.add_argument("--proposal-model", dest="proposal_model", default=None, help="optional override for the proposal detector")
    parser.add_argument("--scene-model", dest="proposal_model", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--query-model", default=None, help="optional override for the query parser")
    parser.add_argument("--embedder-model", default=None, help="optional checkpoint for the icon embedder")
    parser.add_argument(
        "--from-run",
        default=None,
        help="optional; defaults sub-model checkpoints to <repo>/work_home/runs/group1/<from-run>/*/weights/best.pt",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="resume the current run from <repo>/work_home/runs/group1/<name>/*/weights/last.pt",
    )
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--batch", type=int, default=None)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="0")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def build_prelabel_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prelabel a group1 reviewed exam workspace for X-AnyLabeling.")
    parser.add_argument("--exam-root", type=Path, required=True)
    parser.add_argument(
        "--dataset-config",
        type=Path,
        required=False,
        help="optional; defaults to <repo>/work_home/datasets/group1/<dataset-version>/dataset.json",
    )
    parser.add_argument("--dataset-version", default="v1")
    parser.add_argument(
        "--project",
        type=Path,
        required=False,
        help="optional; defaults to <exam-root>/.sinan/prelabel/group1/predict",
    )
    parser.add_argument("--train-name", default="v1")
    parser.add_argument("--proposal-model", dest="proposal_model", type=Path, required=False)
    parser.add_argument("--scene-model", dest="proposal_model", type=Path, required=False, help=argparse.SUPPRESS)
    parser.add_argument("--query-model", type=Path, required=False)
    parser.add_argument("--embedder-model", type=Path, required=False)
    parser.add_argument("--name", default="prelabel")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="0")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def build_prelabel_query_dir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prelabel a directory of group1 query images for X-AnyLabeling.")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument(
        "--project",
        type=Path,
        required=False,
        help="optional; defaults to <input-dir>/.sinan/prelabel/group1/query",
    )
    parser.add_argument("--train-name", default="v1")
    parser.add_argument("--query-model", type=Path, required=False)
    parser.add_argument("--name", default="prelabel-query")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="0")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args_list = list(argv or [])
    if args_list and args_list[0] == "prelabel":
        return _run_prelabel_cli(args_list[1:])
    if args_list and args_list[0] == "prelabel-query-dir":
        return _run_prelabel_query_dir_cli(args_list[1:])

    parser = build_parser()
    args = parser.parse_args(args_list)
    if args.resume and args.from_run:
        parser.error("不能同时传 --resume 和 --from-run。")
    if args.from_run and any(value is not None for value in (args.model, args.proposal_model, args.query_model, args.embedder_model)):
        parser.error("传入 --from-run 时不要再同时传 --model / --proposal-model / --query-model / --embedder-model。")

    train_root = default_train_root(Path.cwd())
    dataset_config = args.dataset_config or (train_root / "datasets" / "group1" / args.dataset_version / "dataset.json")
    project_dir = args.project or default_project_dir(train_root, "group1")
    component = normalize_group1_component(args.component)

    shared_model = args.model or "yolo26n.pt"
    proposal_model: str | None = None
    query_model: str | None = None
    embedder_model: str | None = args.embedder_model if component in {ALL_COMPONENTS, EMBEDDER_COMPONENT} else None
    if component in {ALL_COMPONENTS, PROPOSAL_COMPONENT}:
        proposal_model = args.proposal_model or shared_model
    if component in {ALL_COMPONENTS, QUERY_COMPONENT}:
        query_model = args.query_model or shared_model
    if args.resume:
        if component in {ALL_COMPONENTS, PROPOSAL_COMPONENT}:
            proposal_model = str(resolve_group1_component_last_weights(train_root, args.name, PROPOSAL_COMPONENT))
        if component in {ALL_COMPONENTS, QUERY_COMPONENT}:
            query_model = str(resolve_group1_component_last_weights(train_root, args.name, QUERY_COMPONENT))
        if component in {ALL_COMPONENTS, EMBEDDER_COMPONENT}:
            embedder_model = str(resolve_group1_component_last_weights(train_root, args.name, EMBEDDER_COMPONENT))
    elif args.from_run is not None:
        if component in {ALL_COMPONENTS, PROPOSAL_COMPONENT}:
            proposal_model = str(resolve_group1_component_best_weights(train_root, args.from_run, PROPOSAL_COMPONENT))
        if component in {ALL_COMPONENTS, QUERY_COMPONENT}:
            query_model = str(resolve_group1_component_best_weights(train_root, args.from_run, QUERY_COMPONENT))
        if component in {ALL_COMPONENTS, EMBEDDER_COMPONENT}:
            embedder_model = str(resolve_group1_component_best_weights(train_root, args.from_run, EMBEDDER_COMPONENT))

    job = build_group1_training_job(
        dataset_config=dataset_config,
        project_dir=project_dir,
        model=shared_model,
        proposal_model=proposal_model,
        query_model=query_model,
        embedder_model=embedder_model,
        run_name=args.name,
        epochs=args.epochs,
        batch=args.batch,
        component=component,
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


def _run_prelabel_cli(argv: list[str]) -> int:
    parser = build_prelabel_parser()
    args = parser.parse_args(argv)

    train_root = default_train_root(Path.cwd())
    exam_root = args.exam_root
    dataset_config = args.dataset_config or (train_root / "datasets" / "group1" / args.dataset_version / "dataset.json")
    proposal_model = args.proposal_model or resolve_group1_component_best_weights(train_root, args.train_name, PROPOSAL_COMPONENT)
    query_model = args.query_model or resolve_group1_component_best_weights(train_root, args.train_name, QUERY_COMPONENT)
    embedder_model = args.embedder_model
    if embedder_model is None and dataset_config.exists():
        group1_dataset = load_group1_dataset_config(dataset_config)
        if group1_dataset.is_instance_matching:
            embedder_model = resolve_group1_component_best_weights(train_root, args.train_name, EMBEDDER_COMPONENT)
    project_dir = args.project or (exam_root / ".sinan" / "prelabel" / "group1" / "predict")
    request = Group1PrelabelRequest(
        exam_root=exam_root,
        dataset_config=dataset_config,
        proposal_model_path=proposal_model,
        query_model_path=query_model,
        project_dir=project_dir,
        embedder_model_path=embedder_model,
        run_name=args.name,
        conf=args.conf,
        imgsz=args.imgsz,
        device=args.device,
        limit=args.limit,
        overwrite=args.overwrite,
    )
    if args.dry_run:
        print(build_group1_prelabel_plan(request).prediction_job.command_string())
        return 0

    try:
        result = run_group1_prelabel(request)
    except RuntimeError as err:
        parser.exit(1, f"{err}\n")
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def _run_prelabel_query_dir_cli(argv: list[str]) -> int:
    parser = build_prelabel_query_dir_parser()
    args = parser.parse_args(argv)

    train_root = default_train_root(Path.cwd())
    input_dir = args.input_dir
    query_model = args.query_model or resolve_group1_component_best_weights(train_root, args.train_name, QUERY_COMPONENT)
    project_dir = args.project or (input_dir / ".sinan" / "prelabel" / "group1" / "query")
    request = Group1QueryDirectoryPrelabelRequest(
        input_dir=input_dir,
        query_model_path=query_model,
        project_dir=project_dir,
        run_name=args.name,
        conf=args.conf,
        imgsz=args.imgsz,
        device=args.device,
        limit=args.limit,
        overwrite=args.overwrite,
    )
    if args.dry_run:
        print(json.dumps(build_group1_query_directory_prelabel_plan(request).to_dict(), ensure_ascii=False, indent=2))
        return 0

    try:
        result = run_group1_query_directory_prelabel(request)
    except RuntimeError as err:
        parser.exit(1, f"{err}\n")
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
