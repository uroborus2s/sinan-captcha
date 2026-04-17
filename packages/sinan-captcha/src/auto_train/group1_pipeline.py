"""Group1 auto-train helpers for detector-aware hardset building and matcher calibration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
from typing import Any, Callable

from PIL import Image

from common.jsonl import write_jsonl
from train.group1.dataset import Group1DatasetConfig, load_group1_rows, resolve_group1_path
from train.group1.embedder import load_icon_embedder_runtime

DEFAULT_IOU_THRESHOLD = 0.5
DEFAULT_HARDSET_NEGATIVES = 8
DEFAULT_MATCHER_SIMILARITY_GRID = (0.8, 0.85, 0.875, 0.9, 0.925, 0.95)
DEFAULT_MATCHER_AMBIGUITY_GRID = (0.0, 0.005, 0.01, 0.015, 0.02, 0.03)

DetectionPredictor = Callable[[Path], list[dict[str, Any]]]
EmbeddingEncoder = Callable[[Path, dict[str, Any]], list[float]]
ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class DetectorAwareHardsetResult:
    output_root: Path
    dataset_config_path: Path
    pair_count: int
    triplet_count: int
    anchor_fallback_count: int
    positive_fallback_count: int
    false_positive_negative_count: int
    split_stats: dict[str, dict[str, int]]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["output_root"] = str(self.output_root)
        payload["dataset_config_path"] = str(self.dataset_config_path)
        return payload


@dataclass(frozen=True)
class MatcherCalibrationCase:
    sample_id: str
    gold_targets: list[dict[str, Any]]
    query_items: list[dict[str, Any]]
    scene_candidates: list[dict[str, Any]]
    similarity_matrix: list[list[float]]


@dataclass(frozen=True)
class MatcherCalibrationResult:
    sample_count: int
    selected_similarity_threshold: float
    selected_ambiguity_margin: float
    best_metrics: dict[str, float | None]
    candidate_metrics: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_detector_aware_hardset(
    *,
    dataset_config: Group1DatasetConfig,
    output_root: Path,
    query_model_path: Path | None,
    proposal_model_path: Path,
    embedder_model_path: Path | None = None,
    imgsz: int,
    device: str,
    conf: float = 0.25,
    iou_threshold: float = DEFAULT_IOU_THRESHOLD,
    max_negatives_per_query: int = DEFAULT_HARDSET_NEGATIVES,
    progress_callback: ProgressCallback | None = None,
) -> DetectorAwareHardsetResult:
    query_predictor, scene_predictor = _build_detection_predictors(
        query_model_path=query_model_path,
        proposal_model_path=proposal_model_path,
        imgsz=imgsz,
        device=device,
        conf=conf,
    )
    split_rows = {
        "train": load_group1_rows(dataset_config, None, split="train"),
        "val": load_group1_rows(dataset_config, None, split="val"),
    }
    embedding_encoder = None
    if embedder_model_path is not None:
        embedding_runtime = load_icon_embedder_runtime(embedder_model_path, device_name=device)
        embedding_encoder = embedding_runtime.embed_crop
    return build_detector_aware_hardset_from_rows(
        split_rows=split_rows,
        dataset_root=dataset_config.root,
        output_root=output_root,
        query_predictor=query_predictor,
        scene_predictor=scene_predictor,
        embedding_encoder=embedding_encoder,
        base_dataset_config_path=dataset_config.path,
        iou_threshold=iou_threshold,
        max_negatives_per_query=max_negatives_per_query,
        progress_callback=progress_callback,
    )


def build_detector_aware_hardset_from_rows(
    *,
    split_rows: dict[str, list[dict[str, Any]]],
    dataset_root: Path,
    output_root: Path,
    query_predictor: DetectionPredictor,
    scene_predictor: DetectionPredictor,
    embedding_encoder: EmbeddingEncoder | None = None,
    base_dataset_config_path: Path | None = None,
    iou_threshold: float = DEFAULT_IOU_THRESHOLD,
    max_negatives_per_query: int = DEFAULT_HARDSET_NEGATIVES,
    progress_callback: ProgressCallback | None = None,
) -> DetectorAwareHardsetResult:
    output_root.mkdir(parents=True, exist_ok=True)
    pair_records: list[dict[str, Any]] = []
    triplet_records: list[dict[str, Any]] = []
    anchor_fallback_count = 0
    positive_fallback_count = 0
    false_positive_negative_count = 0
    split_stats: dict[str, dict[str, int]] = {}
    written_crops: set[Path] = set()
    total_samples = sum(len(rows) for rows in split_rows.values())
    _emit_progress(
        progress_callback,
        "hardset_build_start "
        f"output_root={output_root} "
        f"total_samples={total_samples} "
        f"splits={','.join(sorted(split_rows))}",
    )

    for split, rows in split_rows.items():
        queries_dir = output_root / "queries" / split
        candidates_dir = output_root / "candidates" / split
        queries_dir.mkdir(parents=True, exist_ok=True)
        candidates_dir.mkdir(parents=True, exist_ok=True)
        split_pair_count = 0
        split_triplet_count = 0
        split_false_positive_count = 0
        progress_interval = max(1, len(rows) // 10) if rows else 1
        _emit_progress(
            progress_callback,
            "hardset_build_split_start "
            f"split={split} "
            f"samples={len(rows)}",
        )

        for row_index, row in enumerate(rows, start=1):
            sample_id = str(row["sample_id"])
            query_path = resolve_group1_path(dataset_root, Path(str(row["query_image"])))
            scene_path = resolve_group1_path(dataset_root, Path(str(row["scene_image"])))
            gold_queries = [dict(item) for item in row.get("query_items", []) if isinstance(item, dict)]
            gold_targets = [dict(item) for item in row.get("scene_targets", []) if isinstance(item, dict)]
            gold_distractors = [dict(item) for item in row.get("distractors", []) if isinstance(item, dict)]
            predicted_queries = query_predictor(query_path)
            predicted_scene = scene_predictor(scene_path)

            for query_index, gold_query in enumerate(sorted(gold_queries, key=_query_sort_key), start=1):
                gold_positive = _find_matching_scene_target(gold_query, gold_targets)
                if gold_positive is None:
                    continue

                anchor_target, anchor_source = _select_detection_or_fallback(
                    gold_object=gold_query,
                    detections=predicted_queries,
                    iou_threshold=iou_threshold,
                )
                if anchor_source != "predicted":
                    anchor_fallback_count += 1

                positive_target, positive_source, positive_index = _select_detection_or_fallback(
                    gold_object=gold_positive,
                    detections=predicted_scene,
                    iou_threshold=iou_threshold,
                    return_index=True,
                )
                if positive_source != "predicted":
                    positive_fallback_count += 1

                negative_targets = _select_negative_targets(
                    predicted_scene=predicted_scene,
                    positive_index=positive_index,
                    gold_positive=gold_positive,
                    gold_targets=gold_targets,
                    gold_distractors=gold_distractors,
                    iou_threshold=iou_threshold,
                )
                negative_targets = _rank_negative_targets(
                    query_path=query_path,
                    scene_path=scene_path,
                    anchor_target=anchor_target,
                    positive_target=positive_target,
                    negative_targets=negative_targets,
                    embedding_encoder=embedding_encoder,
                    max_negatives=max_negatives_per_query,
                )
                if not negative_targets:
                    continue

                anchor_rel_path = Path("queries") / split / f"{sample_id}__anchor_{query_index:02d}.png"
                positive_rel_path = Path("candidates") / split / f"{sample_id}__positive_{query_index:02d}.png"
                _write_crop_once(
                    image_path=query_path,
                    bbox=_require_bbox(anchor_target),
                    output_path=output_root / anchor_rel_path,
                    written_crops=written_crops,
                )
                _write_crop_once(
                    image_path=scene_path,
                    bbox=_require_bbox(positive_target),
                    output_path=output_root / positive_rel_path,
                    written_crops=written_crops,
                )

                pair_records.append(
                    {
                        "split": split,
                        "sample_id": sample_id,
                        "label": 1,
                        "query_image": anchor_rel_path.as_posix(),
                        "candidate_image": positive_rel_path.as_posix(),
                        "query_item": anchor_target,
                        "candidate": positive_target,
                        "candidate_role": f"positive_{positive_source}",
                    }
                )
                split_pair_count += 1

                for negative_index, negative_target in enumerate(negative_targets, start=1):
                    if str(negative_target.get("negative_role", "")).startswith("false_positive"):
                        false_positive_negative_count += 1
                        split_false_positive_count += 1
                    negative_rel_path = Path("candidates") / split / f"{sample_id}__negative_{query_index:02d}_{negative_index:02d}.png"
                    _write_crop_once(
                        image_path=scene_path,
                        bbox=_require_bbox(negative_target),
                        output_path=output_root / negative_rel_path,
                        written_crops=written_crops,
                    )
                    pair_records.append(
                        {
                            "split": split,
                            "sample_id": sample_id,
                            "label": 0,
                            "query_image": anchor_rel_path.as_posix(),
                            "candidate_image": negative_rel_path.as_posix(),
                            "query_item": anchor_target,
                            "candidate": negative_target,
                            "candidate_role": negative_target["negative_role"],
                            "candidate_bucket": negative_target.get("negative_bucket"),
                            "candidate_similarity": negative_target.get("negative_similarity"),
                        }
                    )
                    triplet_records.append(
                        {
                            "split": split,
                            "sample_id": sample_id,
                            "anchor_image": anchor_rel_path.as_posix(),
                            "positive_image": positive_rel_path.as_posix(),
                            "negative_image": negative_rel_path.as_posix(),
                            "anchor": anchor_target,
                            "positive": positive_target,
                            "negative": negative_target,
                            "negative_role": negative_target["negative_role"],
                            "negative_bucket": negative_target.get("negative_bucket"),
                            "negative_similarity": negative_target.get("negative_similarity"),
                        }
                    )
                    split_pair_count += 1
                    split_triplet_count += 1

            if row_index == 1 or row_index == len(rows) or row_index % progress_interval == 0:
                _emit_progress(
                    progress_callback,
                    "hardset_build_progress "
                    f"split={split} "
                    f"processed={row_index}/{len(rows)} "
                    f"pair_count={split_pair_count} "
                    f"triplet_count={split_triplet_count} "
                    f"false_positive_negative_count={split_false_positive_count}",
                )

        split_stats[split] = {
            "sample_count": len(rows),
            "pair_count": split_pair_count,
            "triplet_count": split_triplet_count,
            "false_positive_negative_count": split_false_positive_count,
        }
        _emit_progress(
            progress_callback,
            "hardset_build_split_done "
            f"split={split} "
            f"sample_count={len(rows)} "
            f"pair_count={split_pair_count} "
            f"triplet_count={split_triplet_count} "
            f"false_positive_negative_count={split_false_positive_count}",
        )

    write_jsonl(output_root / "pairs.jsonl", pair_records)
    write_jsonl(output_root / "triplets.jsonl", triplet_records)
    dataset_config_path = output_root / "dataset.json"
    if base_dataset_config_path is not None:
        write_detector_aware_dataset_config(
            base_dataset_config_path=base_dataset_config_path,
            output_root=output_root,
            output_path=dataset_config_path,
        )

    result = DetectorAwareHardsetResult(
        output_root=output_root,
        dataset_config_path=dataset_config_path,
        pair_count=len(pair_records),
        triplet_count=len(triplet_records),
        anchor_fallback_count=anchor_fallback_count,
        positive_fallback_count=positive_fallback_count,
        false_positive_negative_count=false_positive_negative_count,
        split_stats=split_stats,
    )
    _emit_progress(
        progress_callback,
        "hardset_build_done "
        f"output_root={output_root} "
        f"pair_count={result.pair_count} "
        f"triplet_count={result.triplet_count} "
        f"anchor_fallback_count={result.anchor_fallback_count} "
        f"positive_fallback_count={result.positive_fallback_count} "
        f"false_positive_negative_count={result.false_positive_negative_count}",
    )
    return result


def _emit_progress(callback: ProgressCallback | None, message: str) -> None:
    if callback is not None:
        callback(message)


def write_detector_aware_dataset_config(
    *,
    base_dataset_config_path: Path,
    output_root: Path,
    output_path: Path,
) -> Path:
    payload = json.loads(base_dataset_config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"group1 数据集配置文件格式非法：{base_dataset_config_path}")
    payload["embedding"] = {
        "format": "sinan.group1.embedding.v1",
        "queries_dir": str((output_root / "queries").absolute()),
        "candidates_dir": str((output_root / "candidates").absolute()),
        "pairs_jsonl": str((output_root / "pairs.jsonl").absolute()),
        "triplets_jsonl": str((output_root / "triplets.jsonl").absolute()),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


def prepare_matcher_cases(
    *,
    dataset_config: Group1DatasetConfig,
    query_model_path: Path | None,
    proposal_model_path: Path,
    embedder_model_path: Path,
    imgsz: int,
    device: str,
    conf: float = 0.25,
    split: str = "val",
) -> list[MatcherCalibrationCase]:
    query_predictor, scene_predictor = _build_detection_predictors(
        query_model_path=query_model_path,
        proposal_model_path=proposal_model_path,
        imgsz=imgsz,
        device=device,
        conf=conf,
    )
    embedding_runtime = load_icon_embedder_runtime(embedder_model_path, device_name=device)
    rows = load_group1_rows(dataset_config, None, split=split)
    return prepare_matcher_cases_from_rows(
        rows=rows,
        dataset_root=dataset_config.root,
        query_predictor=query_predictor,
        scene_predictor=scene_predictor,
        embedding_encoder=embedding_runtime.embed_crop,
    )


def prepare_matcher_cases_from_rows(
    *,
    rows: list[dict[str, Any]],
    dataset_root: Path,
    query_predictor: DetectionPredictor,
    scene_predictor: DetectionPredictor,
    embedding_encoder: EmbeddingEncoder,
) -> list[MatcherCalibrationCase]:
    cases: list[MatcherCalibrationCase] = []
    for row in rows:
        query_path = resolve_group1_path(dataset_root, Path(str(row["query_image"])))
        scene_path = resolve_group1_path(dataset_root, Path(str(row["scene_image"])))
        query_items = query_predictor(query_path)
        scene_candidates = scene_predictor(scene_path)
        similarity_matrix: list[list[float]] = []
        if query_items and scene_candidates:
            query_vectors = [embedding_encoder(query_path, item) for item in query_items]
            scene_vectors = [embedding_encoder(scene_path, item) for item in scene_candidates]
            similarity_matrix = [
                [_cosine_similarity(query_vector, scene_vector) for scene_vector in scene_vectors]
                for query_vector in query_vectors
            ]
        cases.append(
            MatcherCalibrationCase(
                sample_id=str(row["sample_id"]),
                gold_targets=[dict(item) for item in row.get("scene_targets", []) if isinstance(item, dict)],
                query_items=[dict(item) for item in query_items],
                scene_candidates=[dict(item) for item in scene_candidates],
                similarity_matrix=similarity_matrix,
            )
        )
    return cases


def calibrate_matcher(
    *,
    dataset_config: Group1DatasetConfig,
    query_model_path: Path | None,
    proposal_model_path: Path,
    embedder_model_path: Path,
    imgsz: int,
    device: str,
    point_tolerance_px: int,
    conf: float = 0.25,
    split: str = "val",
    similarity_thresholds: tuple[float, ...] = DEFAULT_MATCHER_SIMILARITY_GRID,
    ambiguity_margins: tuple[float, ...] = DEFAULT_MATCHER_AMBIGUITY_GRID,
) -> MatcherCalibrationResult:
    cases = prepare_matcher_cases(
        dataset_config=dataset_config,
        query_model_path=query_model_path,
        proposal_model_path=proposal_model_path,
        embedder_model_path=embedder_model_path,
        imgsz=imgsz,
        device=device,
        conf=conf,
        split=split,
    )
    return calibrate_matcher_from_cases(
        cases,
        point_tolerance_px=point_tolerance_px,
        similarity_thresholds=similarity_thresholds,
        ambiguity_margins=ambiguity_margins,
    )


def calibrate_matcher_from_cases(
    cases: list[MatcherCalibrationCase],
    *,
    point_tolerance_px: int,
    similarity_thresholds: tuple[float, ...] = DEFAULT_MATCHER_SIMILARITY_GRID,
    ambiguity_margins: tuple[float, ...] = DEFAULT_MATCHER_AMBIGUITY_GRID,
) -> MatcherCalibrationResult:
    candidate_metrics: list[dict[str, Any]] = []
    best_payload: dict[str, Any] | None = None
    best_rank: tuple[float, float, float, float, float] | None = None
    for similarity_threshold in similarity_thresholds:
        for ambiguity_margin in ambiguity_margins:
            metrics = _evaluate_matcher_candidate(
                cases=cases,
                point_tolerance_px=point_tolerance_px,
                similarity_threshold=similarity_threshold,
                ambiguity_margin=ambiguity_margin,
            )
            payload = {
                "similarity_threshold": similarity_threshold,
                "ambiguity_margin": ambiguity_margin,
                **metrics,
            }
            candidate_metrics.append(payload)
            mean_center_error = metrics["mean_center_error_px"]
            rank = (
                float(metrics["full_sequence_hit_rate"] or 0.0),
                float(metrics["single_target_hit_rate"] or 0.0),
                -float(metrics["order_error_rate"] or 0.0),
                -(float(mean_center_error) if mean_center_error is not None else 1e9),
                -float(metrics["ambiguity_flag_rate"] or 0.0),
            )
            if best_rank is None or rank > best_rank:
                best_rank = rank
                best_payload = payload

    selected = best_payload or {
        "similarity_threshold": similarity_thresholds[0],
        "ambiguity_margin": ambiguity_margins[0],
        "single_target_hit_rate": 0.0,
        "full_sequence_hit_rate": 0.0,
        "mean_center_error_px": None,
        "order_error_rate": 1.0,
        "ambiguity_flag_rate": 0.0,
        "missing_order_rate": 1.0,
    }
    best_metrics = {
        key: selected[key]
        for key in (
            "single_target_hit_rate",
            "full_sequence_hit_rate",
            "mean_center_error_px",
            "order_error_rate",
            "ambiguity_flag_rate",
            "missing_order_rate",
        )
    }
    return MatcherCalibrationResult(
        sample_count=len(cases),
        selected_similarity_threshold=float(selected["similarity_threshold"]),
        selected_ambiguity_margin=float(selected["ambiguity_margin"]),
        best_metrics=best_metrics,
        candidate_metrics=candidate_metrics,
    )


def _build_detection_predictors(
    *,
    query_model_path: Path | None,
    proposal_model_path: Path,
    imgsz: int,
    device: str,
    conf: float,
) -> tuple[DetectionPredictor, DetectionPredictor]:
    try:
        from ultralytics import YOLO
    except Exception as exc:  # pragma: no cover - depends on host env
        raise RuntimeError(
            "当前环境缺少 `ultralytics`，无法构建 group1 detector-aware hardset / matcher calibration。"
        ) from exc

    query_model = YOLO(str(query_model_path)) if query_model_path is not None else None
    scene_model = YOLO(str(proposal_model_path))

    def _predict_query(image_path: Path) -> list[dict[str, Any]]:
        if query_model is None:
            raise RuntimeError("group1 matcher calibration 缺少 query detector 权重。")
        result = query_model.predict(
            source=str(image_path),
            imgsz=imgsz,
            conf=conf,
            device=device,
            verbose=False,
        )[0]
        return _serialize_detections(result, ordered=True)

    def _predict_scene(image_path: Path) -> list[dict[str, Any]]:
        result = scene_model.predict(
            source=str(image_path),
            imgsz=imgsz,
            conf=conf,
            device=device,
            verbose=False,
        )[0]
        return _serialize_detections(result, ordered=False)

    return _predict_query, _predict_scene


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
        detection = {
            "order": index,
            "bbox": [x1, y1, x2, y2],
            "center": [int(round((x1 + x2) / 2)), int(round((y1 + y2) / 2))],
            "score": float(score),
        }
        raw_name = names.get(int(class_id))
        if isinstance(raw_name, str) and raw_name.strip():
            detection["class_guess"] = raw_name.strip()
        detections.append(detection)

    if ordered:
        detections.sort(key=_query_sort_key)
        for order, detection in enumerate(detections, start=1):
            detection["order"] = order
    return detections


def _query_sort_key(target: dict[str, Any]) -> tuple[int, float, float]:
    if isinstance(target.get("order"), int):
        return int(target["order"]), float(target["center"][0]), float(target["center"][1])
    center = target.get("center", [0, 0])
    return 10**9, float(center[0]), float(center[1])


def _find_matching_scene_target(query_target: dict[str, Any], gold_targets: list[dict[str, Any]]) -> dict[str, Any] | None:
    query_order = query_target.get("order")
    if isinstance(query_order, int):
        for gold_target in gold_targets:
            if int(gold_target.get("order", -1)) == query_order:
                return dict(gold_target)
    query_identity = _object_identity(query_target)
    for gold_target in gold_targets:
        if _object_identity(gold_target) == query_identity and query_identity:
            return dict(gold_target)
    return None


def _select_detection_or_fallback(
    *,
    gold_object: dict[str, Any],
    detections: list[dict[str, Any]],
    iou_threshold: float,
    return_index: bool = False,
) -> tuple[dict[str, Any], str, int | None] | tuple[dict[str, Any], str]:
    best_index = None
    best_iou = 0.0
    for index, detection in enumerate(detections):
        iou = _bbox_iou(_require_bbox(gold_object), _require_bbox(detection))
        if iou >= iou_threshold and iou > best_iou:
            best_iou = iou
            best_index = index

    if best_index is None:
        fallback = dict(gold_object)
        if return_index:
            return fallback, "gold_fallback", None
        return fallback, "gold_fallback"

    enriched = dict(detections[best_index])
    for field in ("order", "asset_id", "template_id", "variant_id"):
        if field in gold_object and gold_object[field] not in (None, ""):
            enriched[field] = gold_object[field]
    if return_index:
        return enriched, "predicted", best_index
    return enriched, "predicted"


def _select_negative_targets(
    *,
    predicted_scene: list[dict[str, Any]],
    positive_index: int | None,
    gold_positive: dict[str, Any],
    gold_targets: list[dict[str, Any]],
    gold_distractors: list[dict[str, Any]],
    iou_threshold: float,
) -> list[dict[str, Any]]:
    negatives: list[dict[str, Any]] = []
    for index, detection in enumerate(predicted_scene):
        if positive_index is not None and index == positive_index:
            continue
        matched_target = _best_gold_match(detection, gold_targets, iou_threshold=iou_threshold)
        matched_distractor = _best_gold_match(detection, gold_distractors, iou_threshold=iou_threshold)
        enriched = dict(detection)
        if matched_target is not None:
            for field in ("asset_id", "template_id", "variant_id", "order"):
                if field in matched_target and matched_target[field] not in (None, ""):
                    enriched[field] = matched_target[field]
            negative_role = "scene_target_pred"
            if _object_identity(matched_target) == _object_identity(gold_positive) and _object_identity(gold_positive):
                continue
            if int(matched_target.get("order", -1)) == int(gold_positive.get("order", -999)):
                continue
        elif matched_distractor is not None:
            for field in ("asset_id", "template_id", "variant_id"):
                if field in matched_distractor and matched_distractor[field] not in (None, ""):
                    enriched[field] = matched_distractor[field]
            negative_role = "distractor_pred"
        else:
            negative_role = "false_positive_pred"
        enriched["negative_role"] = negative_role
        negatives.append(enriched)

    supplemented = _supplement_same_template_gold_negatives(
        negatives=negatives,
        gold_positive=gold_positive,
        gold_targets=gold_targets,
        gold_distractors=gold_distractors,
    )
    if supplemented:
        return supplemented

    fallback_targets: list[dict[str, Any]] = []
    for candidate in gold_targets:
        if int(candidate.get("order", -1)) == int(gold_positive.get("order", -999)):
            continue
        enriched = dict(candidate)
        enriched["negative_role"] = "scene_target_gold"
        fallback_targets.append(enriched)
    for candidate in gold_distractors:
        enriched = dict(candidate)
        enriched["negative_role"] = "distractor_gold"
        fallback_targets.append(enriched)
    return fallback_targets


def _supplement_same_template_gold_negatives(
    *,
    negatives: list[dict[str, Any]],
    gold_positive: dict[str, Any],
    gold_targets: list[dict[str, Any]],
    gold_distractors: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    supplemented = [dict(item) for item in negatives]
    positive_identity = _object_identity(gold_positive)
    positive_template = str(gold_positive.get("template_id", "")).strip()
    if not positive_template:
        return supplemented

    seen_identities = {
        identity
        for identity in (_object_identity(item) for item in supplemented)
        if identity
    }

    def _append_if_same_template(candidate: dict[str, Any], role: str) -> None:
        candidate_identity = _object_identity(candidate)
        candidate_template = str(candidate.get("template_id", "")).strip()
        if not candidate_template or candidate_template != positive_template:
            return
        if candidate_identity and candidate_identity == positive_identity:
            return
        if candidate_identity and candidate_identity in seen_identities:
            return
        enriched = dict(candidate)
        enriched["negative_role"] = role
        supplemented.append(enriched)
        if candidate_identity:
            seen_identities.add(candidate_identity)

    for candidate in gold_targets:
        if int(candidate.get("order", -1)) == int(gold_positive.get("order", -999)):
            continue
        _append_if_same_template(candidate, "scene_target_gold_same_template")
    for candidate in gold_distractors:
        _append_if_same_template(candidate, "distractor_gold_same_template")
    return supplemented


def _rank_negative_targets(
    *,
    query_path: Path,
    scene_path: Path,
    anchor_target: dict[str, Any],
    positive_target: dict[str, Any],
    negative_targets: list[dict[str, Any]],
    embedding_encoder: EmbeddingEncoder | None,
    max_negatives: int,
) -> list[dict[str, Any]]:
    if not negative_targets or max_negatives <= 0:
        return []
    anchor_vector = embedding_encoder(query_path, anchor_target) if embedding_encoder is not None else None
    ranked: list[dict[str, Any]] = []
    for negative_target in negative_targets:
        enriched = dict(negative_target)
        bucket = _negative_bucket(positive_target, enriched)
        enriched["negative_bucket"] = bucket
        if anchor_vector is not None and embedding_encoder is not None:
            similarity = _cosine_similarity(anchor_vector, embedding_encoder(scene_path, enriched))
            enriched["negative_similarity"] = round(float(similarity), 6)
        ranked.append(enriched)
    ranked.sort(
        key=lambda item: (
            _negative_bucket_priority(str(item.get("negative_bucket", ""))),
            -(float(item.get("negative_similarity", -1.0))),
            -float(item.get("score", 0.0)),
        )
    )
    return ranked[:max_negatives]


def _negative_bucket(positive_target: dict[str, Any], negative_target: dict[str, Any]) -> str:
    positive_identity = _object_identity(positive_target)
    negative_identity = _object_identity(negative_target)
    positive_template = str(positive_target.get("template_id", "")).strip()
    negative_template = str(negative_target.get("template_id", "")).strip()
    positive_variant = str(positive_target.get("variant_id", "")).strip()
    negative_variant = str(negative_target.get("variant_id", "")).strip()
    if (
        positive_template
        and negative_template == positive_template
        and negative_identity
        and negative_identity != positive_identity
    ):
        if positive_variant and negative_variant and negative_variant != positive_variant:
            return "same_template_variant"
        return "same_template_other"
    negative_role = str(negative_target.get("negative_role", ""))
    if negative_role.startswith("scene_target"):
        return "scene_target"
    if negative_role.startswith("distractor"):
        return "distractor"
    if negative_role.startswith("false_positive"):
        return "false_positive"
    return "other"


def _negative_bucket_priority(bucket: str) -> int:
    priorities = {
        "same_template_variant": 0,
        "same_template_other": 1,
        "scene_target": 2,
        "distractor": 3,
        "false_positive": 4,
        "other": 5,
    }
    return priorities.get(bucket, priorities["other"])


def _best_gold_match(
    detection: dict[str, Any],
    gold_objects: list[dict[str, Any]],
    *,
    iou_threshold: float,
) -> dict[str, Any] | None:
    best_object = None
    best_iou = 0.0
    for gold_object in gold_objects:
        iou = _bbox_iou(_require_bbox(detection), _require_bbox(gold_object))
        if iou >= iou_threshold and iou > best_iou:
            best_iou = iou
            best_object = gold_object
    return None if best_object is None else dict(best_object)


def _write_crop_once(
    *,
    image_path: Path,
    bbox: list[int],
    output_path: Path,
    written_crops: set[Path],
) -> None:
    if output_path in written_crops and output_path.exists():
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        x1 = max(0, min(width, int(bbox[0])))
        y1 = max(0, min(height, int(bbox[1])))
        x2 = max(x1 + 1, min(width, int(bbox[2])))
        y2 = max(y1 + 1, min(height, int(bbox[3])))
        rgb.crop((x1, y1, x2, y2)).save(output_path)
    written_crops.add(output_path)


def _require_bbox(target: dict[str, Any]) -> list[int]:
    bbox = target.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise RuntimeError("group1 detector-aware hardset 需要合法 bbox。")
    return [int(value) for value in bbox]


def _bbox_iou(left: list[int], right: list[int]) -> float:
    left_x1, left_y1, left_x2, left_y2 = [int(value) for value in left]
    right_x1, right_y1, right_x2, right_y2 = [int(value) for value in right]
    inter_x1 = max(left_x1, right_x1)
    inter_y1 = max(left_y1, right_y1)
    inter_x2 = min(left_x2, right_x2)
    inter_y2 = min(left_y2, right_y2)
    inter_width = max(0, inter_x2 - inter_x1)
    inter_height = max(0, inter_y2 - inter_y1)
    if inter_width == 0 or inter_height == 0:
        return 0.0
    intersection = inter_width * inter_height
    left_area = max(1, (left_x2 - left_x1) * (left_y2 - left_y1))
    right_area = max(1, (right_x2 - right_x1) * (right_y2 - right_y1))
    return intersection / (left_area + right_area - intersection)


def _evaluate_matcher_candidate(
    *,
    cases: list[MatcherCalibrationCase],
    point_tolerance_px: int,
    similarity_threshold: float,
    ambiguity_margin: float,
) -> dict[str, float | None]:
    total_targets = 0
    hit_targets = 0
    full_sequence_hits = 0
    order_errors = 0
    ambiguous_samples = 0
    total_missing_orders = 0
    center_errors: list[float] = []
    for case in cases:
        mapping = _apply_matcher_to_case(
            case=case,
            similarity_threshold=similarity_threshold,
            ambiguity_margin=ambiguity_margin,
        )
        gold_targets = sorted(case.gold_targets, key=lambda item: int(item.get("order", 0)))
        predicted_targets = mapping["ordered_targets"]
        total_targets += len(gold_targets)
        if mapping["ambiguous_orders"]:
            ambiguous_samples += 1
        total_missing_orders += len(mapping["missing_orders"])
        predicted_by_order = {int(item["order"]): item for item in predicted_targets if isinstance(item.get("order"), int)}
        expected_orders = [int(item["order"]) for item in gold_targets]
        predicted_orders = sorted(predicted_by_order)
        order_ok = len(predicted_targets) == len(gold_targets) and predicted_orders == expected_orders
        sequence_ok = order_ok
        sample_hits = 0
        for gold_target in gold_targets:
            predicted_target = predicted_by_order.get(int(gold_target["order"]))
            if predicted_target is None:
                sequence_ok = False
                continue
            center_error = _distance(gold_target["center"], predicted_target["center"])
            center_errors.append(center_error)
            if center_error <= point_tolerance_px:
                hit_targets += 1
                sample_hits += 1
            else:
                sequence_ok = False
        if not order_ok:
            order_errors += 1
        if sequence_ok and sample_hits == len(gold_targets):
            full_sequence_hits += 1

    sample_count = len(cases)
    return {
        "single_target_hit_rate": _safe_ratio(hit_targets, total_targets),
        "full_sequence_hit_rate": _safe_ratio(full_sequence_hits, sample_count),
        "mean_center_error_px": _mean(center_errors),
        "order_error_rate": _safe_ratio(order_errors, sample_count),
        "ambiguity_flag_rate": _safe_ratio(ambiguous_samples, sample_count),
        "missing_order_rate": _safe_ratio(total_missing_orders, total_targets),
    }


def _apply_matcher_to_case(
    *,
    case: MatcherCalibrationCase,
    similarity_threshold: float,
    ambiguity_margin: float,
) -> dict[str, Any]:
    query_items = sorted(case.query_items, key=_query_sort_key)
    scene_candidates = case.scene_candidates
    if not query_items or not scene_candidates:
        return {
            "ordered_targets": [],
            "missing_orders": [int(item.get("order", index)) for index, item in enumerate(query_items, start=1)],
            "ambiguous_orders": [],
        }
    assignment = _best_global_assignment(case.similarity_matrix)
    ordered_targets: list[dict[str, Any]] = []
    missing_orders: list[int] = []
    ambiguous_orders: list[int] = []
    for expected_order, assigned_index in enumerate(assignment, start=1):
        if assigned_index is None:
            missing_orders.append(expected_order)
            continue
        similarities = case.similarity_matrix[expected_order - 1]
        assigned_score = similarities[assigned_index]
        alternative_scores = [score for candidate_index, score in enumerate(similarities) if candidate_index != assigned_index]
        next_best_score = max(alternative_scores) if alternative_scores else None
        if assigned_score < similarity_threshold:
            missing_orders.append(expected_order)
            continue
        if next_best_score is not None and (assigned_score - next_best_score) < ambiguity_margin:
            ambiguous_orders.append(expected_order)
        chosen = dict(scene_candidates[assigned_index])
        chosen["order"] = expected_order
        ordered_targets.append(chosen)
    return {
        "ordered_targets": ordered_targets,
        "missing_orders": missing_orders,
        "ambiguous_orders": ambiguous_orders,
    }


def _best_global_assignment(similarity_matrix: list[list[float]]) -> list[int | None]:
    query_count = len(similarity_matrix)
    candidate_count = len(similarity_matrix[0]) if similarity_matrix else 0
    best_score = float("-inf")
    best_assignment: list[int | None] = [None] * query_count

    def backtrack(query_index: int, used_candidates: set[int], current_assignment: list[int | None], current_score: float) -> None:
        nonlocal best_score, best_assignment
        if query_index >= query_count:
            if current_score > best_score:
                best_score = current_score
                best_assignment = list(current_assignment)
            return

        current_assignment.append(None)
        backtrack(query_index + 1, used_candidates, current_assignment, current_score)
        current_assignment.pop()

        for candidate_index in range(candidate_count):
            if candidate_index in used_candidates:
                continue
            current_assignment.append(candidate_index)
            used_candidates.add(candidate_index)
            backtrack(
                query_index + 1,
                used_candidates,
                current_assignment,
                current_score + similarity_matrix[query_index][candidate_index],
            )
            used_candidates.remove(candidate_index)
            current_assignment.pop()

    backtrack(0, set(), [], 0.0)
    return best_assignment


def _object_identity(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    raw_asset_id = value.get("asset_id")
    if isinstance(raw_asset_id, str) and raw_asset_id.strip():
        return raw_asset_id
    raw_template_id = value.get("template_id")
    raw_variant_id = value.get("variant_id")
    if isinstance(raw_template_id, str) and raw_template_id.strip() and isinstance(raw_variant_id, str) and raw_variant_id.strip():
        return f"{raw_template_id}:{raw_variant_id}"
    return ""


def _distance(left: list[int], right: list[int]) -> float:
    return math.hypot(int(left[0]) - int(right[0]), int(left[1]) - int(right[1]))


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return sum(left_value * right_value for left_value, right_value in zip(left, right)) / (left_norm * right_norm)
