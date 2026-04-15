"""Deterministic trial-level diagnostics for judge and retune planning."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from auto_train import contracts, layout, storage
from common.jsonl import read_jsonl

_GROUP1_COMPONENT_RECORDS = {
    "query-detector": "query_train",
    "proposal-detector": "scene_train",
    "icon-embedder": "embedder_train",
}
_EMBEDDER_ALERT_KEYS = (
    "embedding_top1_error_scene_target_rate",
    "embedding_top1_error_distractor_rate",
    "embedding_top1_error_false_positive_rate",
    "embedding_top1_error_other_rate",
    "embedding_same_template_top1_error_rate",
)


@dataclass(frozen=True)
class TrialAnalysisRequest:
    paths: layout.StudyPaths
    trial_id: str
    trial_input: contracts.TrialInputRecord
    summary_record: contracts.ResultSummaryRecord
    sample_limit: int = 3

    def __post_init__(self) -> None:
        if self.sample_limit <= 0:
            raise ValueError("sample_limit must be greater than 0")


def build_trial_analysis(request: TrialAnalysisRequest) -> contracts.TrialAnalysisRecord:
    evaluation_failures = _build_evaluation_failures(request)
    component_diagnostics = (
        _build_group1_component_diagnostics(request)
        if request.summary_record.task == "group1"
        else {}
    )
    evidence = [
        f"trend={request.summary_record.trend}",
        f"failure_patterns={', '.join(request.summary_record.failure_patterns)}"
        if request.summary_record.failure_patterns
        else "failure_patterns=(none)",
    ]
    if evaluation_failures is not None:
        evidence.append(
            "evaluation_failure_reasons="
            + ", ".join(f"{key}:{value}" for key, value in sorted(_reason_counts(evaluation_failures).items()))
        )
    return contracts.TrialAnalysisRecord(
        study_name=request.summary_record.study_name,
        task=request.summary_record.task,
        trial_id=request.summary_record.trial_id,
        dataset_version=request.summary_record.dataset_version,
        train_name=request.summary_record.train_name,
        current_params=dict(request.trial_input.params),
        evaluation_failures=evaluation_failures,
        component_diagnostics=component_diagnostics,
        evidence=evidence,
    )


def _build_evaluation_failures(request: TrialAnalysisRequest) -> dict[str, contracts.JsonValue] | None:
    evaluate_path = request.paths.evaluate_file(request.trial_id)
    if not evaluate_path.exists():
        return None
    evaluate_record = storage.read_evaluate_record(evaluate_path)
    report_dir = Path(evaluate_record.report_dir)
    failure_file = report_dir / "failures.jsonl"
    failures = _read_jsonl_records(failure_file, sample_limit=request.sample_limit)
    return {
        "report_dir": str(report_dir),
        "failure_file": str(failure_file) if failure_file.exists() else None,
        "failure_count": evaluate_record.failure_count,
        "reason_counts": _count_reasons(failures["rows"]),
        "examples": failures["examples"],
    }


def _build_group1_component_diagnostics(
    request: TrialAnalysisRequest,
) -> dict[str, contracts.JsonValue]:
    diagnostics: dict[str, contracts.JsonValue] = {}
    for component in contracts.ALLOWED_GROUP1_COMPONENTS:
        gate_path = _component_gate_path(request.paths, request.trial_id, component)
        if not gate_path.exists():
            continue
        gate_payload = storage._read_json(gate_path)  # type: ignore[attr-defined]
        diagnostic: dict[str, contracts.JsonValue] = {
            "status": _string_or_none(gate_payload.get("status")),
            "failed_checks": _string_list_or_empty(gate_payload.get("gate"), "failed_checks"),
            "metrics": _mapping_or_empty(gate_payload.get("metrics")),
            "current_params": _load_component_current_params(request.paths, request.trial_id, component),
        }
        error_file = _string_or_none(gate_payload.get("error_file"))
        if error_file:
            parsed = _read_jsonl_records(Path(error_file), sample_limit=request.sample_limit)
            diagnostic["error_file"] = error_file
            diagnostic["error_reason_counts"] = _count_reasons(parsed["rows"])
            diagnostic["error_examples"] = parsed["examples"]
        else:
            diagnostic["error_file"] = None
            diagnostic["error_reason_counts"] = {}
            diagnostic["error_examples"] = []
        if component == "icon-embedder":
            review = gate_payload.get("review")
            diagnostic["review"] = review if isinstance(review, dict) else None
            diagnostic["signal_summary"] = _embedder_signal_summary(_mapping_or_empty(gate_payload.get("metrics")))
        diagnostics[component] = diagnostic
    return diagnostics


def _component_gate_path(paths: layout.StudyPaths, trial_id: str, component: str) -> Path:
    if component == "query-detector":
        return paths.query_gate_file(trial_id)
    if component == "proposal-detector":
        return paths.scene_gate_file(trial_id)
    return paths.embedder_gate_file(trial_id)


def _load_component_current_params(
    paths: layout.StudyPaths,
    trial_id: str,
    component: str,
) -> dict[str, contracts.JsonValue]:
    record_path = {
        "query-detector": paths.query_train_file(trial_id),
        "proposal-detector": paths.scene_train_file(trial_id),
        "icon-embedder": paths.embedder_train_file(trial_id),
    }[component]
    if not record_path.exists():
        return {}
    record = storage.read_train_record(record_path)
    return dict(record.params)


def _read_jsonl_records(path: Path, *, sample_limit: int) -> dict[str, object]:
    if not path.exists():
        return {"rows": [], "examples": []}
    rows = read_jsonl(path)
    examples = [row for row in rows[:sample_limit] if isinstance(row, dict)]
    return {"rows": [row for row in rows if isinstance(row, dict)], "examples": examples}


def _count_reasons(rows: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        reason = row.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            continue
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def _embedder_signal_summary(metrics: dict[str, contracts.JsonValue]) -> list[str]:
    summary: list[str] = []
    for key in _EMBEDDER_ALERT_KEYS:
        value = metrics.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        if float(value) <= 0:
            continue
        summary.append(f"{key}={float(value):.6f}")
    return summary


def _mapping_or_empty(value: object) -> dict[str, contracts.JsonValue]:
    return value if isinstance(value, dict) else {}


def _string_or_none(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _string_list_or_empty(value: object, key: str) -> list[str]:
    if not isinstance(value, dict):
        return []
    raw = value.get(key)
    if not isinstance(raw, list):
        return []
    result: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            result.append(item)
    return result


def _reason_counts(payload: dict[str, contracts.JsonValue]) -> dict[str, int]:
    raw = payload.get("reason_counts")
    if not isinstance(raw, dict):
        return {}
    counts: dict[str, int] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            continue
        if isinstance(value, int) and not isinstance(value, bool):
            counts[key] = value
    return counts
