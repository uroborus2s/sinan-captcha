"""Current group1 training/prediction runner."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import time
from typing import Any

from core.common.jsonl import write_jsonl
from core.inference.service import map_group1_clicks, map_group1_instances
from core.train.base import prepare_dataset_yaml_for_ultralytics
from core.train.group1.dataset import load_group1_dataset_config, load_group1_rows, resolve_group1_path
from core.train.group1.embedder import load_icon_embedder_runtime, train_icon_embedder
from core.train.group1.service import (
    ALL_COMPONENTS,
    EMBEDDER_COMPONENT,
    PROPOSAL_COMPONENT,
    QUERY_COMPONENT,
    normalize_group1_component,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run current group1 train/predict flows.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    train_parser = subparsers.add_parser("train", help="train current group1 components from dataset.json")
    train_parser.add_argument("--dataset-config", type=Path, required=True)
    train_parser.add_argument("--project", type=Path, required=True)
    train_parser.add_argument("--name", required=True)
    train_parser.add_argument("--component", default=ALL_COMPONENTS, help="all | proposal-detector | query-parser | icon-embedder")
    train_parser.add_argument("--proposal-model", dest="proposal_model", default=None)
    train_parser.add_argument("--scene-model", dest="proposal_model", default=None, help=argparse.SUPPRESS)
    train_parser.add_argument("--query-model", default=None)
    train_parser.add_argument("--embedder-model", default=None)
    train_parser.add_argument("--epochs", type=int, default=120)
    train_parser.add_argument("--batch", type=int, default=16)
    train_parser.add_argument("--imgsz", type=int, default=640)
    train_parser.add_argument("--device", default="0")
    train_parser.add_argument("--resume", action="store_true")

    predict_parser = subparsers.add_parser("predict", help="run group1 pipeline prediction")
    predict_parser.add_argument("--dataset-config", type=Path, required=True)
    predict_parser.add_argument("--proposal-model", "--scene-model", dest="proposal_model", type=Path, required=True)
    predict_parser.add_argument("--query-model", type=Path, required=True)
    predict_parser.add_argument("--embedder-model", type=Path, default=None)
    predict_parser.add_argument("--source", type=Path, required=True)
    predict_parser.add_argument("--project", type=Path, required=True)
    predict_parser.add_argument("--name", required=True)
    predict_parser.add_argument("--conf", type=float, default=0.25)
    predict_parser.add_argument("--imgsz", type=int, default=640)
    predict_parser.add_argument("--device", default="0")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "train":
            _run_train(args)
        elif args.command == "predict":
            _run_predict(args)
        else:  # pragma: no cover - argparse guards
            raise RuntimeError(f"unsupported command: {args.command}")
    except RuntimeError as exc:
        parser.exit(1, f"{exc}\n")
    return 0


def _run_train(args: argparse.Namespace) -> None:
    dataset_config = load_group1_dataset_config(args.dataset_config)
    run_dir = args.project / args.name
    run_dir.mkdir(parents=True, exist_ok=True)
    component = normalize_group1_component(args.component)

    commands: dict[str, list[str]] = {}
    component_summaries: dict[str, dict[str, Any]] = {}

    if component in {ALL_COMPONENTS, PROPOSAL_COMPONENT}:
        proposal_model = _resolve_component_model(
            component=PROPOSAL_COMPONENT,
            model=args.proposal_model,
            resume=args.resume,
        )
        proposal_yaml = prepare_dataset_yaml_for_ultralytics(dataset_config.proposal_dataset_yaml)
        commands[PROPOSAL_COMPONENT] = _build_train_command(
            dataset_yaml=proposal_yaml,
            project_dir=run_dir,
            run_name=PROPOSAL_COMPONENT,
            model=proposal_model,
            epochs=args.epochs,
            batch=args.batch,
            imgsz=args.imgsz,
            device=args.device,
            resume=args.resume,
        )
        component_summaries[PROPOSAL_COMPONENT] = {
            "role": "proposal_detector" if dataset_config.is_instance_matching else "scene_detector",
            "dataset_yaml": str(proposal_yaml),
            "weights": {
                "best": str(run_dir / PROPOSAL_COMPONENT / "weights" / "best.pt"),
                "last": str(run_dir / PROPOSAL_COMPONENT / "weights" / "last.pt"),
            },
            "command": " ".join(commands[PROPOSAL_COMPONENT]),
        }

    if component in {ALL_COMPONENTS, QUERY_COMPONENT}:
        if dataset_config.query_component is None:
            if component == QUERY_COMPONENT:
                raise RuntimeError(
                    "当前 group1 dataset.json 未提供 query_parser 数据集。"
                    "请先完成 query splitter / embedder 主线，再显式训练该组件。"
                )
        else:
            query_model = _resolve_component_model(
                component=QUERY_COMPONENT,
                model=args.query_model,
                resume=args.resume,
            )
            query_yaml = prepare_dataset_yaml_for_ultralytics(dataset_config.query_component.dataset_yaml)
            commands[QUERY_COMPONENT] = _build_train_command(
                dataset_yaml=query_yaml,
                project_dir=run_dir,
                run_name=QUERY_COMPONENT,
                model=query_model,
                epochs=args.epochs,
                batch=args.batch,
                imgsz=args.imgsz,
                device=args.device,
                resume=args.resume,
            )
            component_summaries[QUERY_COMPONENT] = {
                "role": "query_parser",
                "dataset_yaml": str(query_yaml),
                "weights": {
                    "best": str(run_dir / QUERY_COMPONENT / "weights" / "best.pt"),
                    "last": str(run_dir / QUERY_COMPONENT / "weights" / "last.pt"),
                },
                "command": " ".join(commands[QUERY_COMPONENT]),
            }

    should_train_embedder = component == EMBEDDER_COMPONENT or (
        component == ALL_COMPONENTS and dataset_config.is_instance_matching
    )
    if should_train_embedder:
        if not dataset_config.is_instance_matching or dataset_config.embedding is None:
            if component == EMBEDDER_COMPONENT:
                raise RuntimeError("当前 group1 dataset.json 未提供 embedding 数据，无法训练 icon-embedder。")
        else:
            component_summaries[EMBEDDER_COMPONENT] = {
                "role": "icon_embedder",
                "triplets_jsonl": str(dataset_config.embedding.triplets_jsonl),
                "weights": {
                    "best": str(run_dir / EMBEDDER_COMPONENT / "weights" / "best.pt"),
                    "last": str(run_dir / EMBEDDER_COMPONENT / "weights" / "last.pt"),
                },
            }

    for command in commands.values():
        subprocess.run(command, check=True)

    if should_train_embedder and dataset_config.is_instance_matching and dataset_config.embedding is not None:
        embedder_model_path = Path(args.embedder_model) if args.embedder_model is not None else None
        if args.resume and embedder_model_path is None:
            embedder_model_path = run_dir / EMBEDDER_COMPONENT / "weights" / "last.pt"
        embedder_result = train_icon_embedder(
            dataset_config=dataset_config,
            run_dir=run_dir,
            model_path=embedder_model_path,
            epochs=args.epochs,
            batch_size=args.batch,
            image_size=args.imgsz,
            device_name=args.device,
            resume=args.resume,
        )
        component_summaries[EMBEDDER_COMPONENT] = {
            **component_summaries[EMBEDDER_COMPONENT],
            "metrics": embedder_result.metrics,
            "summary": str(embedder_result.summary_path),
        }

    summary = {
        "task": "group1",
        "dataset_config": str(args.dataset_config),
        "run_dir": str(run_dir),
        "requested_component": component,
        "components": component_summaries,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_predict(args: argparse.Namespace) -> None:
    try:
        from ultralytics import YOLO
    except Exception as exc:  # pragma: no cover - import error depends on host env
        raise RuntimeError(
            "当前环境缺少 `ultralytics`，无法执行 group1 proposal-detector/query-parser 预测。"
            "请先完成训练环境安装后再重试。"
        ) from exc

    dataset_config = load_group1_dataset_config(args.dataset_config)
    rows = load_group1_rows(dataset_config, args.source)
    if not rows:
        raise RuntimeError("group1 预测输入为空。")

    proposal_model = YOLO(str(args.proposal_model))
    query_model = YOLO(str(args.query_model))
    embedding_provider = None
    if dataset_config.is_instance_matching and args.embedder_model is not None:
        embedding_provider = load_icon_embedder_runtime(args.embedder_model, device_name=args.device)
    output_dir = args.project / args.name
    output_dir.mkdir(parents=True, exist_ok=True)
    predictions: list[dict[str, Any]] = []

    for row in rows:
        query_path = resolve_group1_path(dataset_config.root, Path(str(row["query_image"])))
        scene_path = resolve_group1_path(dataset_config.root, Path(str(row["scene_image"])))
        started = time.perf_counter()
        query_result = query_model.predict(
            source=str(query_path),
            imgsz=args.imgsz,
            conf=args.conf,
            device=args.device,
            verbose=False,
        )[0]
        proposal_result = proposal_model.predict(
            source=str(scene_path),
            imgsz=args.imgsz,
            conf=args.conf,
            device=args.device,
            verbose=False,
        )[0]
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        predicted_query_targets = _serialize_detections(query_result, ordered=True)
        predicted_scene_targets = _serialize_detections(proposal_result, ordered=False)
        if dataset_config.is_instance_matching:
            mapping = map_group1_instances(
                predicted_query_targets,
                predicted_scene_targets,
                query_image_path=query_path,
                scene_image_path=scene_path,
                embedding_provider=embedding_provider,
            )
        else:
            mapping = map_group1_clicks(predicted_query_targets, predicted_scene_targets)
        predictions.append(
            _build_prediction_row(
                row,
                predicted_query_targets,
                mapping,
                elapsed_ms,
                instance_matching=dataset_config.is_instance_matching,
            )
        )

    write_jsonl(output_dir / "labels.jsonl", predictions)
    (output_dir / "summary.json").write_text(
        json.dumps(
            {
                "task": "group1",
                "dataset_config": str(args.dataset_config),
                "source": str(args.source),
                "proposal_model": str(args.proposal_model),
                "query_model": str(args.query_model),
                "embedder_model": str(args.embedder_model) if args.embedder_model is not None else None,
                "sample_count": len(predictions),
                "labels_path": str(output_dir / "labels.jsonl"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _build_train_command(
    *,
    dataset_yaml: Path,
    project_dir: Path,
    run_name: str,
    model: str,
    epochs: int,
    batch: int,
    imgsz: int,
    device: str,
    resume: bool,
) -> list[str]:
    if resume:
        command = [
            "uv",
            "run",
            "yolo",
            "detect",
            "train",
            "resume",
            f"model={model}",
        ]
        if device:
            command.append(f"device={device}")
        return command
    return [
        "uv",
        "run",
        "yolo",
        "detect",
        "train",
        f"data={dataset_yaml}",
        f"model={model}",
        f"imgsz={imgsz}",
        f"epochs={epochs}",
        f"batch={batch}",
        f"device={device}",
        f"project={project_dir}",
        f"name={run_name}",
    ]


def _resolve_component_model(*, component: str, model: str | None, resume: bool) -> str:
    if model is not None:
        return model
    if resume:
        raise RuntimeError(f"{component} 恢复训练缺少对应检查点。")
    return "yolo26n.pt"


def _serialize_detections(result: Any, *, ordered: bool) -> list[dict[str, Any]]:
    boxes = result.boxes
    if boxes is None:
        return []
    names = result.names if isinstance(result.names, dict) else {}
    detections: list[dict[str, Any]] = []
    xyxy = boxes.xyxy.tolist()
    cls_ids = boxes.cls.tolist()
    confidences = boxes.conf.tolist()
    for index, (bbox, class_id, score) in enumerate(zip(xyxy, cls_ids, confidences, strict=False), start=1):
        x1, y1, x2, y2 = [int(round(value)) for value in bbox]
        center_x = int(round((x1 + x2) / 2))
        center_y = int(round((y1 + y2) / 2))
        numeric_class_id = int(class_id)
        class_name = str(names.get(numeric_class_id, numeric_class_id))
        detection = {
            "order": index,
            "class": class_name,
            "class_id": numeric_class_id,
            "bbox": [x1, y1, x2, y2],
            "center": [center_x, center_y],
            "score": float(score),
        }
        detections.append(detection)

    if not ordered:
        return detections
    detections.sort(key=lambda item: (int(item["center"][0]), int(item["center"][1])))
    for order, detection in enumerate(detections, start=1):
        detection["order"] = order
    return detections


def _build_prediction_row(
    row: dict[str, Any],
    predicted_query_targets: list[dict[str, Any]],
    mapping: Any,
    elapsed_ms: float,
    *,
    instance_matching: bool,
) -> dict[str, Any]:
    if instance_matching:
        scene_targets = _build_instance_matching_scene_targets(row, mapping)
    else:
        scene_targets = [
            {
                "order": target.order,
                "class": target.class_name,
                "class_id": target.class_id,
                "bbox": target.bbox,
                "center": target.center,
                "score": target.score,
            }
            for target in mapping.ordered_targets
        ]
    return {
        "sample_id": row["sample_id"],
        "query_image": row["query_image"],
        "scene_image": row["scene_image"],
        "query_targets": predicted_query_targets,
        "scene_targets": scene_targets,
        "distractors": [],
        "label_source": "pred",
        "source_batch": row.get("source_batch", "prediction"),
        "status": mapping.status,
        "inference_ms": round(elapsed_ms, 4),
    }


def _build_instance_matching_scene_targets(row: dict[str, Any], mapping: Any) -> list[dict[str, Any]]:
    query_items = row.get("query_items", [])
    identity_by_order: dict[int, dict[str, str]] = {}
    if isinstance(query_items, list):
        for item in query_items:
            if not isinstance(item, dict):
                continue
            order = item.get("order")
            if not isinstance(order, int):
                continue
            if all(isinstance(item.get(field), str) and str(item.get(field)).strip() for field in ("asset_id", "template_id", "variant_id")):
                identity_by_order[order] = {
                    "asset_id": str(item["asset_id"]),
                    "template_id": str(item["template_id"]),
                    "variant_id": str(item["variant_id"]),
                }

    scene_targets: list[dict[str, Any]] = []
    for target in mapping.ordered_targets:
        payload = {
            "order": target.order,
            "bbox": target.bbox,
            "center": target.center,
            "score": target.score,
        }
        payload.update(identity_by_order.get(target.order, _synthetic_identity(target.order)))
        scene_targets.append(payload)
    return scene_targets


def _synthetic_identity(order: int) -> dict[str, str]:
    return {
        "asset_id": f"pred_asset_{order:02d}",
        "template_id": f"pred_tpl_{order:02d}",
        "variant_id": f"pred_var_{order:02d}",
    }


if __name__ == "__main__":
    raise SystemExit(main())
