"""Current group1 training/prediction runner."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import time
from typing import Any, Callable

from auto_train import embedder_review_protocol, opencode_assets, opencode_runtime
from common.jsonl import write_jsonl
from inference.query_splitter import split_group1_query_image
from inference.service import map_group1_instances
from train.base import preferred_checkpoint_path, prepare_dataset_yaml_for_ultralytics
from train.group1.dataset import load_group1_dataset_config, load_group1_rows, resolve_group1_path
from train.group1.embedder import load_icon_embedder_runtime, train_icon_embedder
from train.group1.service import (
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
    train_parser.add_argument("--component", default=ALL_COMPONENTS, help="all | query-detector | proposal-detector | icon-embedder")
    train_parser.add_argument("--query-model", dest="query_model", default=None)
    train_parser.add_argument("--proposal-model", dest="proposal_model", default=None)
    train_parser.add_argument("--embedder-model", default=None)
    train_parser.add_argument("--epochs", type=int, default=120)
    train_parser.add_argument("--batch", type=int, default=16)
    train_parser.add_argument("--imgsz", type=int, default=640)
    train_parser.add_argument("--device", default="0")
    train_parser.add_argument("--resume", action="store_true")
    train_parser.add_argument("--review-provider", default=None)
    train_parser.add_argument("--review-model", default=None)
    train_parser.add_argument("--review-project-root", type=Path, default=None)
    train_parser.add_argument("--review-study-name", default=None)
    train_parser.add_argument("--review-task", default=None)
    train_parser.add_argument("--review-trial-id", default=None)
    train_parser.add_argument("--review-stage", default=None)
    train_parser.add_argument("--review-attach-url", default=None)
    train_parser.add_argument("--review-binary", default=opencode_runtime.DEFAULT_OPENCODE_BINARY)
    train_parser.add_argument("--review-timeout-seconds", type=float, default=opencode_runtime.DEFAULT_TIMEOUT_SECONDS)
    train_parser.add_argument("--review-min-epochs", type=int, default=embedder_review_protocol.DEFAULT_EMBEDDER_REVIEW_MIN_EPOCHS)
    train_parser.add_argument("--review-window", type=int, default=embedder_review_protocol.DEFAULT_EMBEDDER_REVIEW_WINDOW)
    train_parser.add_argument("--review-rebuild-count", type=int, default=0)

    predict_parser = subparsers.add_parser("predict", help="run group1 pipeline prediction")
    predict_parser.add_argument("--dataset-config", type=Path, required=True)
    predict_parser.add_argument("--query-model", dest="query_model", type=Path, required=False)
    predict_parser.add_argument("--proposal-model", dest="proposal_model", type=Path, required=True)
    predict_parser.add_argument("--embedder-model", type=Path, required=True)
    predict_parser.add_argument("--source", type=Path, required=True)
    predict_parser.add_argument("--project", type=Path, required=True)
    predict_parser.add_argument("--name", required=True)
    predict_parser.add_argument("--conf", type=float, default=0.25)
    predict_parser.add_argument("--similarity-threshold", type=float, default=None)
    predict_parser.add_argument("--ambiguity-margin", type=float, default=None)
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

    if component in {ALL_COMPONENTS, QUERY_COMPONENT}:
        if dataset_config.query_dataset_yaml is None:
            raise RuntimeError("当前 group1 dataset.json 未提供 query_detector 数据，无法训练 query-detector。")
        query_model = _resolve_component_model(
            component=QUERY_COMPONENT,
            model=args.query_model,
            resume=args.resume,
        )
        query_yaml = prepare_dataset_yaml_for_ultralytics(dataset_config.query_dataset_yaml)
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
            "role": "query_detector",
            "dataset_yaml": str(query_yaml),
            "weights": {
                "best": str(run_dir / QUERY_COMPONENT / "weights" / "best.pt"),
                "last": str(run_dir / QUERY_COMPONENT / "weights" / "last.pt"),
            },
            "command": " ".join(commands[QUERY_COMPONENT]),
        }

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
            "role": "proposal_detector",
            "dataset_yaml": str(proposal_yaml),
            "weights": {
                "best": str(run_dir / PROPOSAL_COMPONENT / "weights" / "best.pt"),
                "last": str(run_dir / PROPOSAL_COMPONENT / "weights" / "last.pt"),
            },
            "command": " ".join(commands[PROPOSAL_COMPONENT]),
        }

    should_train_embedder = component in {ALL_COMPONENTS, EMBEDDER_COMPONENT}
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

    if component in {ALL_COMPONENTS, QUERY_COMPONENT}:
        query_component_dir = run_dir / QUERY_COMPONENT
        query_component_dir.mkdir(parents=True, exist_ok=True)
        query_metrics, query_gate, query_failcases = _evaluate_query_detector_component(
            dataset_config=dataset_config,
            model_path=preferred_checkpoint_path(
                query_component_dir / "weights" / "best.pt",
                query_component_dir / "weights" / "last.pt",
            ),
            imgsz=args.imgsz,
            device=args.device,
        )
        query_failcases_path = query_component_dir / "failcases.jsonl"
        write_jsonl(query_failcases_path, query_failcases)
        component_summaries[QUERY_COMPONENT] = {
            **component_summaries[QUERY_COMPONENT],
            "metrics": query_metrics,
            "gate": query_gate,
            "failcases": str(query_failcases_path),
        }

    if component in {ALL_COMPONENTS, PROPOSAL_COMPONENT}:
        proposal_component_dir = run_dir / PROPOSAL_COMPONENT
        proposal_component_dir.mkdir(parents=True, exist_ok=True)
        proposal_metrics, proposal_gate, proposal_failcases = _evaluate_proposal_detector_component(
            dataset_config=dataset_config,
            model_path=preferred_checkpoint_path(
                proposal_component_dir / "weights" / "best.pt",
                proposal_component_dir / "weights" / "last.pt",
            ),
            imgsz=args.imgsz,
            device=args.device,
        )
        proposal_failcases_path = proposal_component_dir / "failcases.jsonl"
        write_jsonl(proposal_failcases_path, proposal_failcases)
        component_summaries[PROPOSAL_COMPONENT] = {
            **component_summaries[PROPOSAL_COMPONENT],
            "metrics": proposal_metrics,
            "gate": proposal_gate,
            "failcases": str(proposal_failcases_path),
        }

    if should_train_embedder and dataset_config.is_instance_matching and dataset_config.embedding is not None:
        embedder_model_path = Path(args.embedder_model) if args.embedder_model is not None else None
        if args.resume and embedder_model_path is None:
            embedder_model_path = run_dir / EMBEDDER_COMPONENT / "weights" / "last.pt"
        review_callback = _build_embedder_review_callback(args=args, run_dir=run_dir)
        embedder_result = train_icon_embedder(
            dataset_config=dataset_config,
            run_dir=run_dir,
            model_path=embedder_model_path,
            epochs=args.epochs,
            batch_size=args.batch,
            image_size=args.imgsz,
            device_name=args.device,
            resume=args.resume,
            review_callback=review_callback,
            review_stage=args.review_stage or "TRAIN_EMBEDDER_BASE",
            review_study_name=args.review_study_name or "standalone",
            review_task=args.review_task or "group1",
            review_trial_id=args.review_trial_id or args.name,
            review_train_name=args.name,
            review_min_epochs=args.review_min_epochs,
            review_window=args.review_window,
            review_rebuild_count=args.review_rebuild_count,
        )
        component_summaries[EMBEDDER_COMPONENT] = {
            **component_summaries[EMBEDDER_COMPONENT],
            "metrics": embedder_result.metrics,
            "summary": str(embedder_result.summary_path),
            "review": embedder_result.review,
        }

    summary = {
        "task": "group1",
        "dataset_config": str(args.dataset_config),
        "run_dir": str(run_dir),
        "requested_component": component,
        "components": component_summaries,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_embedder_review_callback(
    *,
    args: argparse.Namespace,
    run_dir: Path,
) -> Callable[[embedder_review_protocol.EmbedderReviewContext], embedder_review_protocol.EmbedderReviewRecord] | None:
    if args.review_provider != "opencode":
        return None
    if args.review_model is None or args.review_project_root is None:
        return None
    opencode_assets.copy_opencode_assets(args.review_project_root)
    runtime = opencode_runtime.OpenCodeRuntimeAdapter(
        config=opencode_runtime.OpenCodeRuntimeConfig(
            project_root=args.review_project_root,
            binary=args.review_binary,
            attach_url=args.review_attach_url,
            model=args.review_model,
            timeout_seconds=args.review_timeout_seconds,
        )
    )
    return embedder_review_protocol.build_opencode_embedder_reviewer(runtime=runtime, run_dir=run_dir)


def _run_predict(args: argparse.Namespace) -> None:
    try:
        from ultralytics import YOLO
    except Exception as exc:  # pragma: no cover - import error depends on host env
        raise RuntimeError(
            "当前环境缺少 `ultralytics`，无法执行 group1 proposal-detector 预测。"
            "请先完成训练环境安装后再重试。"
        ) from exc

    dataset_config = load_group1_dataset_config(args.dataset_config)
    rows = load_group1_rows(dataset_config, args.source)
    if not rows:
        raise RuntimeError("group1 预测输入为空。")
    if args.embedder_model is None:
        raise RuntimeError("group1 预测必须显式传入 --embedder-model。")

    query_model = YOLO(str(args.query_model)) if args.query_model is not None else None
    proposal_model = YOLO(str(args.proposal_model))
    embedding_provider = load_icon_embedder_runtime(args.embedder_model, device_name=args.device)
    output_dir = args.project / args.name
    output_dir.mkdir(parents=True, exist_ok=True)
    predictions: list[dict[str, Any]] = []

    for row in rows:
        query_path = resolve_group1_path(dataset_config.root, Path(str(row["query_image"])))
        scene_path = resolve_group1_path(dataset_config.root, Path(str(row["scene_image"])))
        started = time.perf_counter()
        proposal_result = proposal_model.predict(
            source=str(scene_path),
            imgsz=args.imgsz,
            conf=args.conf,
            device=args.device,
            verbose=False,
        )[0]
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        if query_model is not None:
            predicted_query_items = _predict_query_items_with_detector(
                query_model,
                query_path,
                imgsz=args.imgsz,
                conf=args.conf,
                device=args.device,
            )
        else:
            predicted_query_items = split_group1_query_image(query_path)
        predicted_scene_targets = _serialize_detections(proposal_result, ordered=False)
        mapping = map_group1_instances(
            predicted_query_items,
            predicted_scene_targets,
            query_image_path=query_path,
            scene_image_path=scene_path,
            embedding_provider=embedding_provider,
            similarity_threshold=args.similarity_threshold if args.similarity_threshold is not None else 0.9,
            ambiguity_margin=args.ambiguity_margin if args.ambiguity_margin is not None else 0.015,
        )
        predictions.append(
            _build_prediction_row(
                row,
                predicted_query_items,
                mapping,
                elapsed_ms,
            )
        )

    write_jsonl(output_dir / "labels.jsonl", predictions)
    (output_dir / "summary.json").write_text(
        json.dumps(
            {
                "task": "group1",
                "dataset_config": str(args.dataset_config),
                "source": str(args.source),
                "query_model": str(args.query_model) if args.query_model is not None else None,
                "proposal_model": str(args.proposal_model),
                "embedder_model": str(args.embedder_model) if args.embedder_model is not None else None,
                "similarity_threshold": args.similarity_threshold,
                "ambiguity_margin": args.ambiguity_margin,
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
        detection = {
            "order": index,
            "bbox": [x1, y1, x2, y2],
            "center": [center_x, center_y],
            "score": float(score),
        }
        raw_name = names.get(int(class_id))
        if isinstance(raw_name, str) and raw_name.strip():
            detection["class_guess"] = raw_name.strip()
        detections.append(detection)

    if not ordered:
        return detections
    detections.sort(key=lambda item: (int(item["center"][0]), int(item["center"][1])))
    for order, detection in enumerate(detections, start=1):
        detection["order"] = order
    return detections


def _predict_query_items_with_detector(
    model: Any,
    query_path: Path,
    *,
    imgsz: int,
    conf: float,
    device: str,
) -> list[dict[str, Any]]:
    result = model.predict(
        source=str(query_path),
        imgsz=imgsz,
        conf=conf,
        device=device,
        verbose=False,
    )[0]
    return _serialize_detections(result, ordered=True)


def _build_prediction_row(
    row: dict[str, Any],
    predicted_query_items: list[dict[str, Any]],
    mapping: Any,
    elapsed_ms: float,
) -> dict[str, Any]:
    scene_targets = _build_instance_matching_scene_targets(row, mapping)
    return {
        "sample_id": row["sample_id"],
        "query_image": row["query_image"],
        "scene_image": row["scene_image"],
        "query_items": predicted_query_items,
        "scene_targets": scene_targets,
        "distractors": [],
        "label_source": "pred",
        "source_batch": row.get("source_batch", "prediction"),
        "status": mapping.status,
        "inference_ms": round(elapsed_ms, 4),
    }


def _evaluate_query_detector_component(
    *,
    dataset_config: Any,
    model_path: Path,
    imgsz: int,
    device: str,
    conf: float = 0.25,
    iou_threshold: float = 0.5,
) -> tuple[dict[str, float | int | None], dict[str, Any], list[dict[str, Any]]]:
    try:
        from ultralytics import YOLO
    except Exception as exc:  # pragma: no cover - import error depends on host env
        raise RuntimeError(
            "当前环境缺少 `ultralytics`，无法执行 group1 query-detector 评估。"
            "请先完成训练环境安装后再重试。"
        ) from exc

    if not model_path.exists():
        raise RuntimeError(f"未找到 group1 query-detector 权重：{model_path}")

    rows = load_group1_rows(dataset_config, None, split="val")
    model = YOLO(str(model_path))

    def _predict_query_items(query_path: Path) -> list[dict[str, Any]]:
        return _predict_query_items_with_detector(
            model,
            query_path,
            imgsz=imgsz,
            conf=conf,
            device=device,
        )

    return _evaluate_query_detector_rows(
        rows,
        dataset_root=dataset_config.root,
        predict_query_items=_predict_query_items,
        iou_threshold=iou_threshold,
    )


def _evaluate_query_detector_rows(
    rows: list[dict[str, Any]],
    *,
    dataset_root: Path,
    predict_query_items: Callable[[Path], list[dict[str, Any]]],
    iou_threshold: float = 0.5,
) -> tuple[dict[str, float | int | None], dict[str, Any], list[dict[str, Any]]]:
    total_gold = 0
    total_matched = 0
    exact_count_hits = 0
    full_recall_hits = 0
    strict_hit_hits = 0
    matched_ious: list[float] = []
    failcases: list[dict[str, Any]] = []

    for row in rows:
        query_path = resolve_group1_path(dataset_root, Path(str(row["query_image"])))
        gold_items = [dict(item) for item in row.get("query_items", []) if isinstance(item, dict)]
        predicted_items = predict_query_items(query_path)
        matches = _match_query_items(gold_items, predicted_items, iou_threshold=iou_threshold)
        matched_count = len(matches)
        exact_count = len(predicted_items) == len(gold_items)
        full_recall = matched_count == len(gold_items)
        strict_hit = exact_count and full_recall

        total_gold += len(gold_items)
        total_matched += matched_count
        exact_count_hits += 1 if exact_count else 0
        full_recall_hits += 1 if full_recall else 0
        strict_hit_hits += 1 if strict_hit else 0
        matched_ious.extend(match["iou"] for match in matches)

        if not strict_hit:
            failcases.append(
                {
                    "sample_id": row["sample_id"],
                    "query_image": str(query_path),
                    "expected_count": len(gold_items),
                    "predicted_count": len(predicted_items),
                    "matched_count": matched_count,
                    "reason": _query_failcase_reason(
                        expected_count=len(gold_items),
                        predicted_count=len(predicted_items),
                        matched_count=matched_count,
                    ),
                    "gold_items": gold_items,
                    "predicted_items": predicted_items,
                    "matches": matches,
                }
            )

    sample_count = len(rows)
    metrics: dict[str, float | int | None] = {
        "query_sample_count": sample_count,
        "query_item_recall": None if total_gold == 0 else total_matched / total_gold,
        "query_exact_count_rate": None if sample_count == 0 else exact_count_hits / sample_count,
        "query_full_recall_rate": None if sample_count == 0 else full_recall_hits / sample_count,
        "query_strict_hit_rate": None if sample_count == 0 else strict_hit_hits / sample_count,
        "query_mean_iou": None if not matched_ious else sum(matched_ious) / len(matched_ious),
    }
    gate = _build_query_detector_gate(metrics)
    return metrics, gate, failcases


def _evaluate_proposal_detector_component(
    *,
    dataset_config: Any,
    model_path: Path,
    imgsz: int,
    device: str,
    conf: float = 0.25,
    iou_threshold: float = 0.5,
) -> tuple[dict[str, float | int | None], dict[str, Any], list[dict[str, Any]]]:
    try:
        from ultralytics import YOLO
    except Exception as exc:  # pragma: no cover - import error depends on host env
        raise RuntimeError(
            "当前环境缺少 `ultralytics`，无法执行 group1 proposal-detector 评估。"
            "请先完成训练环境安装后再重试。"
        ) from exc

    if not model_path.exists():
        raise RuntimeError(f"未找到 group1 proposal-detector 权重：{model_path}")

    rows = load_group1_rows(dataset_config, None, split="val")
    model = YOLO(str(model_path))

    def _predict_scene_objects(scene_path: Path) -> list[dict[str, Any]]:
        result = model.predict(
            source=str(scene_path),
            imgsz=imgsz,
            conf=conf,
            device=device,
            verbose=False,
        )[0]
        return _serialize_detections(result, ordered=False)

    return _evaluate_proposal_detector_rows(
        rows,
        dataset_root=dataset_config.root,
        predict_scene_objects=_predict_scene_objects,
        iou_threshold=iou_threshold,
    )


def _evaluate_proposal_detector_rows(
    rows: list[dict[str, Any]],
    *,
    dataset_root: Path,
    predict_scene_objects: Callable[[Path], list[dict[str, Any]]],
    iou_threshold: float = 0.5,
) -> tuple[dict[str, float | int | None], dict[str, Any], list[dict[str, Any]]]:
    total_gold = 0
    total_predicted = 0
    total_matched = 0
    full_recall_hits = 0
    strict_hit_hits = 0
    false_positive_count = 0
    matched_ious: list[float] = []
    failcases: list[dict[str, Any]] = []

    for row in rows:
        scene_path = resolve_group1_path(dataset_root, Path(str(row["scene_image"])))
        gold_objects = _gold_scene_objects(row)
        predicted_objects = predict_scene_objects(scene_path)
        matches = _match_query_items(gold_objects, predicted_objects, iou_threshold=iou_threshold)
        matched_count = len(matches)
        unmatched_predicted_count = max(0, len(predicted_objects) - matched_count)
        full_recall = matched_count == len(gold_objects)
        strict_hit = full_recall and unmatched_predicted_count == 0

        total_gold += len(gold_objects)
        total_predicted += len(predicted_objects)
        total_matched += matched_count
        false_positive_count += unmatched_predicted_count
        full_recall_hits += 1 if full_recall else 0
        strict_hit_hits += 1 if strict_hit else 0
        matched_ious.extend(match["iou"] for match in matches)

        if not strict_hit:
            failcases.append(
                {
                    "sample_id": row["sample_id"],
                    "scene_image": str(scene_path),
                    "expected_count": len(gold_objects),
                    "predicted_count": len(predicted_objects),
                    "matched_count": matched_count,
                    "false_positive_count": unmatched_predicted_count,
                    "reason": _proposal_failcase_reason(
                        expected_count=len(gold_objects),
                        predicted_count=len(predicted_objects),
                        matched_count=matched_count,
                        false_positive_count=unmatched_predicted_count,
                    ),
                    "gold_objects": gold_objects,
                    "predicted_objects": predicted_objects,
                    "matches": matches,
                }
            )

    sample_count = len(rows)
    metrics: dict[str, float | int | None] = {
        "proposal_sample_count": sample_count,
        "proposal_object_count": total_gold,
        "proposal_predicted_object_count": total_predicted,
        "proposal_object_recall": None if total_gold == 0 else total_matched / total_gold,
        "proposal_full_recall_rate": None if sample_count == 0 else full_recall_hits / sample_count,
        "proposal_strict_hit_rate": None if sample_count == 0 else strict_hit_hits / sample_count,
        "proposal_false_positive_count": false_positive_count,
        "proposal_false_positive_per_sample": None if sample_count == 0 else false_positive_count / sample_count,
        "proposal_false_positive_rate": None if total_predicted == 0 else false_positive_count / total_predicted,
        "proposal_mean_iou": None if not matched_ious else sum(matched_ious) / len(matched_ious),
    }
    gate = _build_proposal_detector_gate(metrics)
    return metrics, gate, failcases


def _build_query_detector_gate(metrics: dict[str, float | int | None]) -> dict[str, Any]:
    thresholds = {
        "query_item_recall": 0.995,
        "query_exact_count_rate": 0.995,
        "query_strict_hit_rate": 0.99,
    }
    failed_checks: list[str] = []
    for key, threshold in thresholds.items():
        value = metrics.get(key)
        if value is None or not isinstance(value, (int, float)) or float(value) < threshold:
            failed_checks.append(key)
    return {
        "status": "passed" if not failed_checks else "failed",
        "thresholds": thresholds,
        "failed_checks": failed_checks,
    }


def _build_proposal_detector_gate(metrics: dict[str, float | int | None]) -> dict[str, Any]:
    min_thresholds = {
        "proposal_object_recall": 0.995,
        "proposal_full_recall_rate": 0.99,
        "proposal_mean_iou": 0.75,
    }
    max_thresholds = {
        "proposal_false_positive_per_sample": 0.25,
    }
    failed_checks: list[str] = []
    for key, threshold in min_thresholds.items():
        value = metrics.get(key)
        if value is None or not isinstance(value, (int, float)) or float(value) < threshold:
            failed_checks.append(key)
    for key, threshold in max_thresholds.items():
        value = metrics.get(key)
        if value is None or not isinstance(value, (int, float)) or float(value) > threshold:
            failed_checks.append(key)
    return {
        "status": "passed" if not failed_checks else "failed",
        "thresholds": {
            "min": min_thresholds,
            "max": max_thresholds,
        },
        "failed_checks": failed_checks,
    }


def _query_failcase_reason(*, expected_count: int, predicted_count: int, matched_count: int) -> str:
    if predicted_count != expected_count and matched_count == expected_count:
        return "count_mismatch"
    if predicted_count == expected_count and matched_count < expected_count:
        return "recall_shortfall"
    if predicted_count != expected_count and matched_count < expected_count:
        return "count_and_recall"
    return "strict_gate_failed"


def _proposal_failcase_reason(
    *,
    expected_count: int,
    predicted_count: int,
    matched_count: int,
    false_positive_count: int,
) -> str:
    has_missing = matched_count < expected_count
    has_false_positive = false_positive_count > 0
    if has_missing and has_false_positive:
        return "missing_and_false_positive"
    if has_missing:
        return "missing_objects"
    if has_false_positive:
        return "false_positives"
    if predicted_count != expected_count:
        return "count_mismatch"
    return "strict_gate_failed"


def _gold_scene_objects(row: dict[str, Any]) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for source_key in ("scene_targets", "distractors"):
        raw_items = row.get(source_key, [])
        if not isinstance(raw_items, list):
            continue
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            payload = dict(item)
            if "order" not in payload:
                payload["order"] = len(objects) + 1
            objects.append(payload)
    return objects


def _match_query_items(
    gold_items: list[dict[str, Any]],
    predicted_items: list[dict[str, Any]],
    *,
    iou_threshold: float,
) -> list[dict[str, Any]]:
    candidates: list[tuple[float, int, int]] = []
    for gold_index, gold_item in enumerate(gold_items):
        gold_bbox = gold_item.get("bbox")
        if not isinstance(gold_bbox, list) or len(gold_bbox) != 4:
            continue
        for predicted_index, predicted_item in enumerate(predicted_items):
            predicted_bbox = predicted_item.get("bbox")
            if not isinstance(predicted_bbox, list) or len(predicted_bbox) != 4:
                continue
            iou = _bbox_iou(gold_bbox, predicted_bbox)
            if iou >= iou_threshold:
                candidates.append((iou, gold_index, predicted_index))

    candidates.sort(key=lambda item: item[0], reverse=True)
    used_gold: set[int] = set()
    used_predicted: set[int] = set()
    matches: list[dict[str, Any]] = []
    for iou, gold_index, predicted_index in candidates:
        if gold_index in used_gold or predicted_index in used_predicted:
            continue
        used_gold.add(gold_index)
        used_predicted.add(predicted_index)
        matches.append(
            {
                "gold_order": gold_items[gold_index].get("order"),
                "predicted_order": predicted_items[predicted_index].get("order"),
                "iou": round(iou, 6),
            }
        )
    matches.sort(key=lambda item: (int(item.get("gold_order") or 0), int(item.get("predicted_order") or 0)))
    return matches


def _bbox_iou(left: list[Any], right: list[Any]) -> float:
    lx1, ly1, lx2, ly2 = [float(value) for value in left]
    rx1, ry1, rx2, ry2 = [float(value) for value in right]
    inter_x1 = max(lx1, rx1)
    inter_y1 = max(ly1, ry1)
    inter_x2 = min(lx2, rx2)
    inter_y2 = min(ly2, ry2)
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    if inter_area <= 0.0:
        return 0.0
    left_area = max(0.0, lx2 - lx1) * max(0.0, ly2 - ly1)
    right_area = max(0.0, rx2 - rx1) * max(0.0, ry2 - ry1)
    union = left_area + right_area - inter_area
    if union <= 0.0:
        return 0.0
    return inter_area / union


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
