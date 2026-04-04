"""Build compact result summaries for downstream agent commands and skills."""

from __future__ import annotations

from dataclasses import dataclass

from core.auto_train import contracts, layout, storage


@dataclass(frozen=True)
class ResultSummaryRequest:
    study_name: str
    paths: layout.StudyPaths
    trial_id: str
    dataset_version: str
    train_name: str
    primary_metric: str
    test_record: contracts.TestRecord
    evaluate_record: contracts.EvaluateRecord | None = None
    recent_window: int = 3
    min_delta: float = 0.005


def build_result_summary(request: ResultSummaryRequest) -> contracts.ResultSummaryRecord:
    """Compress one trial into a judge-friendly summary record."""

    if request.recent_window <= 0:
        raise ValueError("recent_window must be greater than 0")
    if request.min_delta < 0:
        raise ValueError("min_delta must not be negative")

    recent_trials = _load_recent_trials(request.paths, request.trial_id, request.recent_window)
    best_trial = _load_best_trial_snapshot(request.paths)
    primary_score = _extract_primary_score(
        request.primary_metric,
        test_metrics=request.test_record.metrics,
        evaluation_metrics=request.evaluate_record.metrics if request.evaluate_record is not None else {},
    )
    previous_primary = recent_trials[0].primary_score if recent_trials else None
    best_primary = best_trial.primary_score if best_trial is not None else None
    delta_vs_previous = _delta(primary_score, previous_primary)
    delta_vs_best = _delta(primary_score, best_primary)
    trend = _classify_trend(delta_vs_previous, min_delta=request.min_delta)
    weak_classes = _infer_weak_classes(request.test_record.metrics, request.evaluate_record)
    failure_patterns = _infer_failure_patterns(request.test_record.metrics, request.evaluate_record)
    evidence = _build_evidence(
        primary_metric=request.primary_metric,
        primary_score=primary_score,
        previous_primary=previous_primary,
        best_primary=best_primary,
        recent_trials=recent_trials,
        weak_classes=weak_classes,
        failure_patterns=failure_patterns,
        evaluation_available=request.evaluate_record.available if request.evaluate_record is not None else False,
    )

    return contracts.ResultSummaryRecord(
        study_name=request.study_name,
        task=request.test_record.task,
        trial_id=request.trial_id,
        dataset_version=request.dataset_version,
        train_name=request.train_name,
        primary_metric=request.primary_metric,
        primary_score=primary_score,
        test_metrics=request.test_record.metrics,
        evaluation_available=request.evaluate_record.available if request.evaluate_record is not None else False,
        evaluation_metrics={} if request.evaluate_record is None else request.evaluate_record.metrics,
        failure_count=None if request.evaluate_record is None else request.evaluate_record.failure_count,
        trend=trend,
        delta_vs_previous=delta_vs_previous,
        delta_vs_best=delta_vs_best,
        weak_classes=weak_classes,
        failure_patterns=failure_patterns,
        recent_trials=recent_trials,
        best_trial=best_trial,
        evidence=evidence,
    )


def _load_recent_trials(
    paths: layout.StudyPaths,
    current_trial_id: str,
    recent_window: int,
) -> list[contracts.ResultSummarySnapshot]:
    current_index = layout.parse_trial_id(current_trial_id)
    trial_ids = sorted(
        (
            candidate.name
            for candidate in paths.trials_root.glob("trial_*")
            if candidate.is_dir()
            and candidate.name != current_trial_id
            and layout.parse_trial_id(candidate.name) < current_index
            and paths.result_summary_file(candidate.name).exists()
        ),
        key=layout.parse_trial_id,
        reverse=True,
    )

    snapshots: list[contracts.ResultSummarySnapshot] = []
    for trial_id in trial_ids[:recent_window]:
        historical = storage.read_result_summary_record(paths.result_summary_file(trial_id))
        snapshots.append(
            contracts.ResultSummarySnapshot(
                trial_id=historical.trial_id,
                dataset_version=historical.dataset_version,
                train_name=historical.train_name,
                primary_score=historical.primary_score,
                metrics=_snapshot_metrics(historical),
            )
        )
    return snapshots


def _load_best_trial_snapshot(paths: layout.StudyPaths) -> contracts.ResultSummarySnapshot | None:
    if not paths.best_trial_file.exists():
        return None
    best_trial = storage.read_best_trial_record(paths.best_trial_file)
    return contracts.ResultSummarySnapshot(
        trial_id=best_trial.trial_id,
        dataset_version=best_trial.dataset_version,
        train_name=best_trial.train_name,
        primary_score=best_trial.primary_score,
        metrics=best_trial.metrics,
        decision=best_trial.decision,
    )


def _extract_primary_score(
    primary_metric: str,
    *,
    test_metrics: dict[str, contracts.JsonValue],
    evaluation_metrics: dict[str, contracts.JsonValue],
) -> float | None:
    for source in (evaluation_metrics, test_metrics):
        value = source.get(primary_metric)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _delta(current: float | None, baseline: float | None) -> float | None:
    if current is None or baseline is None:
        return None
    return round(current - baseline, 6)


def _classify_trend(delta_vs_previous: float | None, *, min_delta: float) -> str:
    if delta_vs_previous is None:
        return "baseline"
    if delta_vs_previous >= min_delta:
        return "improving"
    if delta_vs_previous <= -min_delta:
        return "declining"
    return "plateau"


def _infer_weak_classes(
    test_metrics: dict[str, contracts.JsonValue],
    evaluate_record: contracts.EvaluateRecord | None,
) -> list[str]:
    weak_classes: set[str] = set()
    for metrics in (test_metrics, {} if evaluate_record is None else evaluate_record.metrics):
        per_class = metrics.get("per_class_metrics")
        if not isinstance(per_class, dict):
            continue
        for class_name, class_metrics in per_class.items():
            if not isinstance(class_name, str) or not isinstance(class_metrics, dict):
                continue
            numeric_values = [
                float(value)
                for value in class_metrics.values()
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            ]
            if numeric_values and min(numeric_values) < 0.8:
                weak_classes.add(class_name)
    return sorted(weak_classes)


def _infer_failure_patterns(
    test_metrics: dict[str, contracts.JsonValue],
    evaluate_record: contracts.EvaluateRecord | None,
) -> list[str]:
    patterns: list[str] = []
    precision = _metric_value(test_metrics, "precision")
    recall = _metric_value(test_metrics, "recall")
    map50_95 = _metric_value(test_metrics, "map50_95")
    if precision is not None and precision < 0.85:
        patterns.append("detection_precision")
    if recall is not None and recall < 0.88:
        patterns.append("detection_recall")
    if map50_95 is not None and map50_95 < 0.8:
        patterns.append("strict_localization")

    if evaluate_record is None or not evaluate_record.available:
        return patterns

    metrics = evaluate_record.metrics
    if evaluate_record.task == "group1":
        if (_metric_value(metrics, "full_sequence_hit_rate") or 0.0) < 0.8:
            patterns.append("sequence_consistency")
        if (_metric_value(metrics, "order_error_rate") or 0.0) > 0.08:
            patterns.append("order_errors")
    if evaluate_record.task == "group2":
        if (_metric_value(metrics, "point_hit_rate") or 0.0) < 0.9:
            patterns.append("point_hits")
        if (_metric_value(metrics, "mean_center_error_px") or 0.0) > 12.0:
            patterns.append("center_offset")
        mean_iou = _metric_value(metrics, "mean_iou")
        if mean_iou is not None and mean_iou < 0.8:
            patterns.append("low_iou")

    return sorted(set(patterns))


def _build_evidence(
    *,
    primary_metric: str,
    primary_score: float | None,
    previous_primary: float | None,
    best_primary: float | None,
    recent_trials: list[contracts.ResultSummarySnapshot],
    weak_classes: list[str],
    failure_patterns: list[str],
    evaluation_available: bool,
) -> list[str]:
    evidence: list[str] = []
    if primary_score is not None:
        evidence.append(f"{primary_metric}={primary_score:.6f}")
    if previous_primary is not None:
        evidence.append(f"delta_vs_previous={primary_score - previous_primary:+.6f}")
    if best_primary is not None:
        evidence.append(f"delta_vs_best={primary_score - best_primary:+.6f}")
    if recent_trials:
        evidence.append(f"recent_window={len(recent_trials)}")
    if weak_classes:
        evidence.append(f"weak_classes={', '.join(weak_classes)}")
    if failure_patterns:
        evidence.append(f"failure_patterns={', '.join(failure_patterns)}")
    if not evaluation_available:
        evidence.append("evaluation_unavailable")
    return evidence


def _snapshot_metrics(record: contracts.ResultSummaryRecord) -> dict[str, contracts.JsonValue]:
    metrics: dict[str, contracts.JsonValue] = dict(record.test_metrics)
    for key, value in record.evaluation_metrics.items():
        metrics[key] = value
    return metrics


def _metric_value(metrics: dict[str, contracts.JsonValue], key: str) -> float | None:
    value = metrics.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)
