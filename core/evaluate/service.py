"""Evaluation helpers for comparing prediction JSONL files against gold labels."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
from typing import Any

from core.common.jsonl import read_jsonl, write_jsonl
from core.dataset.validation import get_group2_target, validate_group1_row, validate_group2_row


@dataclass(frozen=True)
class EvaluationRequest:
    task: str
    gold_dir: Path
    prediction_dir: Path
    report_dir: Path
    point_tolerance_px: int = 12
    iou_threshold: float = 0.5


@dataclass(frozen=True)
class EvaluationResult:
    task: str
    sample_count: int
    failure_count: int
    metrics: dict[str, float | None]
    report_dir: Path

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["report_dir"] = str(self.report_dir)
        return payload


def evaluate_model(request: EvaluationRequest) -> EvaluationResult:
    gold_rows = _load_rows(request.gold_dir / "labels.jsonl", request.task)
    prediction_rows = _load_rows(request.prediction_dir / "labels.jsonl", request.task)
    prediction_by_id = {str(row["sample_id"]): row for row in prediction_rows}

    if request.task == "group1":
        result = _evaluate_group1(gold_rows, prediction_by_id, request)
    elif request.task == "group2":
        result = _evaluate_group2(gold_rows, prediction_by_id, request)
    else:
        raise ValueError(f"unsupported evaluation task: {request.task}")
    return result


def _load_rows(path: Path, task: str) -> list[dict[str, Any]]:
    rows = read_jsonl(path)
    if task == "group1":
        return [validate_group1_row(row) for row in rows]
    if task == "group2":
        return [validate_group2_row(row) for row in rows]
    raise ValueError(f"unsupported evaluation task: {task}")


def _evaluate_group1(
    gold_rows: list[dict[str, Any]],
    prediction_by_id: dict[str, dict[str, Any]],
    request: EvaluationRequest,
) -> EvaluationResult:
    failures: list[dict[str, object]] = []
    center_errors: list[float] = []
    total_targets = 0
    hit_targets = 0
    full_sequence_hits = 0
    order_errors = 0

    for gold in sorted(gold_rows, key=lambda row: str(row["sample_id"])):
        sample_id = str(gold["sample_id"])
        prediction = prediction_by_id.get(sample_id)
        if prediction is None:
            failures.append({"sample_id": sample_id, "reason": "missing_prediction"})
            order_errors += 1
            total_targets += len(gold["targets"])
            continue

        gold_targets = list(gold["targets"])
        predicted_targets = list(prediction["targets"])
        total_targets += len(gold_targets)
        sample_hits = 0
        sequence_ok = len(gold_targets) == len(predicted_targets)
        order_ok = sequence_ok
        sample_errors: list[float] = []

        for index, gold_target in enumerate(gold_targets):
            if index >= len(predicted_targets):
                sequence_ok = False
                continue

            predicted_target = predicted_targets[index]
            if predicted_target.get("order") != gold_target.get("order"):
                order_ok = False
            if predicted_target.get("class_id") != gold_target.get("class_id"):
                sequence_ok = False
                order_ok = False
                continue

            center_error = _distance(gold_target["center"], predicted_target["center"])
            sample_errors.append(center_error)
            center_errors.append(center_error)
            if center_error <= request.point_tolerance_px:
                hit_targets += 1
                sample_hits += 1
            else:
                sequence_ok = False

        if not order_ok:
            order_errors += 1
        if sequence_ok and sample_hits == len(gold_targets):
            full_sequence_hits += 1
        else:
            failures.append(
                {
                    "sample_id": sample_id,
                    "reason": "sequence_mismatch" if order_ok else "order_mismatch",
                    "target_count": len(gold_targets),
                    "predicted_target_count": len(predicted_targets),
                    "mean_center_error_px": _mean(sample_errors),
                }
            )

    metrics: dict[str, float | None] = {
        "single_target_hit_rate": _safe_ratio(hit_targets, total_targets),
        "full_sequence_hit_rate": _safe_ratio(full_sequence_hits, len(gold_rows)),
        "mean_center_error_px": _mean(center_errors),
        "order_error_rate": _safe_ratio(order_errors, len(gold_rows)),
    }
    return _finalize_result("group1", gold_rows, failures, metrics, request.report_dir)


def _evaluate_group2(
    gold_rows: list[dict[str, Any]],
    prediction_by_id: dict[str, dict[str, Any]],
    request: EvaluationRequest,
) -> EvaluationResult:
    failures: list[dict[str, object]] = []
    center_errors: list[float] = []
    ious: list[float] = []
    inference_times: list[float] = []
    hits = 0

    for gold in sorted(gold_rows, key=lambda row: str(row["sample_id"])):
        sample_id = str(gold["sample_id"])
        prediction = prediction_by_id.get(sample_id)
        if prediction is None:
            failures.append({"sample_id": sample_id, "reason": "missing_prediction"})
            continue

        gold_target = get_group2_target(gold)
        predicted_target = get_group2_target(prediction)
        center_error = _distance(gold_target["center"], predicted_target["center"])
        iou = _iou(gold_target["bbox"], predicted_target["bbox"])
        center_errors.append(center_error)
        ious.append(iou)
        if "inference_ms" in prediction:
            inference_times.append(float(prediction["inference_ms"]))

        point_hit = center_error <= request.point_tolerance_px
        if point_hit:
            hits += 1
        if not point_hit or iou < request.iou_threshold:
            failures.append(
                {
                    "sample_id": sample_id,
                    "reason": "point_miss" if not point_hit else "low_iou",
                    "center_error_px": round(center_error, 4),
                    "iou": round(iou, 6),
                }
            )

    metrics: dict[str, float | None] = {
        "point_hit_rate": _safe_ratio(hits, len(gold_rows)),
        "mean_center_error_px": _mean(center_errors),
        "mean_iou": _mean(ious),
        "mean_inference_ms": _mean(inference_times),
    }
    return _finalize_result("group2", gold_rows, failures, metrics, request.report_dir)


def _finalize_result(
    task: str,
    gold_rows: list[dict[str, Any]],
    failures: list[dict[str, object]],
    metrics: dict[str, float | None],
    report_dir: Path,
) -> EvaluationResult:
    report_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(report_dir / "failures.jsonl", failures)
    summary = {
        "task": task,
        "sample_count": len(gold_rows),
        "failure_count": len(failures),
        "metrics": metrics,
    }
    (report_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (report_dir / "summary.md").write_text(_render_markdown(summary), encoding="utf-8")
    return EvaluationResult(
        task=task,
        sample_count=len(gold_rows),
        failure_count=len(failures),
        metrics=metrics,
        report_dir=report_dir,
    )


def _render_markdown(summary: dict[str, object]) -> str:
    metrics = summary["metrics"]
    assert isinstance(metrics, dict)
    lines = [
        f"# {summary['task']} Evaluation Summary",
        "",
        f"- Sample count: {summary['sample_count']}",
        f"- Failure count: {summary['failure_count']}",
        "",
        "## Metrics",
    ]
    for key, value in metrics.items():
        rendered = "n/a" if value is None else f"{value:.6f}"
        lines.append(f"- {key}: {rendered}")
    lines.append("")
    return "\n".join(lines)


def _distance(left: list[int], right: list[int]) -> float:
    return math.hypot(int(left[0]) - int(right[0]), int(left[1]) - int(right[1]))


def _iou(left: list[int], right: list[int]) -> float:
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
    union = left_area + right_area - intersection
    return intersection / union


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
