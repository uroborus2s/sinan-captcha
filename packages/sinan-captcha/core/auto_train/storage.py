"""JSON and JSONL persistence helpers for autonomous training state."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from core.auto_train import contracts
from core.common.jsonl import read_jsonl


def write_study_record(path: Path, record: contracts.StudyRecord) -> None:
    _write_json(path, record.to_dict())


def read_study_record(path: Path) -> contracts.StudyRecord:
    return contracts.StudyRecord.from_dict(_read_json(path))


def write_trial_input_record(path: Path, record: contracts.TrialInputRecord) -> None:
    _write_json(path, record.to_dict())


def read_trial_input_record(path: Path) -> contracts.TrialInputRecord:
    return contracts.TrialInputRecord.from_dict(_read_json(path))


def write_dataset_record(path: Path, record: contracts.DatasetRecord) -> None:
    _write_json(path, record.to_dict())


def read_dataset_record(path: Path) -> contracts.DatasetRecord:
    return contracts.DatasetRecord.from_dict(_read_json(path))


def write_train_record(path: Path, record: contracts.TrainRecord) -> None:
    _write_json(path, record.to_dict())


def read_train_record(path: Path) -> contracts.TrainRecord:
    return contracts.TrainRecord.from_dict(_read_json(path))


def write_test_record(path: Path, record: contracts.TestRecord) -> None:
    _write_json(path, record.to_dict())


def read_test_record(path: Path) -> contracts.TestRecord:
    return contracts.TestRecord.from_dict(_read_json(path))


def write_evaluate_record(path: Path, record: contracts.EvaluateRecord) -> None:
    _write_json(path, record.to_dict())


def read_evaluate_record(path: Path) -> contracts.EvaluateRecord:
    return contracts.EvaluateRecord.from_dict(_read_json(path))


def write_decision_record(path: Path, record: contracts.DecisionRecord) -> None:
    _write_json(path, record.to_dict())


def read_decision_record(path: Path) -> contracts.DecisionRecord:
    return contracts.DecisionRecord.from_dict(_read_json(path))


def write_leaderboard_record(path: Path, record: contracts.LeaderboardRecord) -> None:
    _write_json(path, record.to_dict())


def read_leaderboard_record(path: Path) -> contracts.LeaderboardRecord:
    return contracts.LeaderboardRecord.from_dict(_read_json(path))


def write_best_trial_record(path: Path, record: contracts.BestTrialRecord) -> None:
    _write_json(path, record.to_dict())


def read_best_trial_record(path: Path) -> contracts.BestTrialRecord:
    return contracts.BestTrialRecord.from_dict(_read_json(path))


def write_result_summary_record(path: Path, record: contracts.ResultSummaryRecord) -> None:
    _write_json(path, record.to_dict())


def read_result_summary_record(path: Path) -> contracts.ResultSummaryRecord:
    return contracts.ResultSummaryRecord.from_dict(_read_json(path))


def write_business_eval_record(path: Path, record: contracts.BusinessEvalRecord) -> None:
    _write_json(path, record.to_dict())


def read_business_eval_record(path: Path) -> contracts.BusinessEvalRecord:
    return contracts.BusinessEvalRecord.from_dict(_read_json(path))


def write_study_status_record(path: Path, record: contracts.StudyStatusRecord) -> None:
    _write_json(path, record.to_dict())


def read_study_status_record(path: Path) -> contracts.StudyStatusRecord:
    return contracts.StudyStatusRecord.from_dict(_read_json(path))


def write_dataset_plan_record(path: Path, record: contracts.DatasetPlanRecord) -> None:
    _write_json(path, record.to_dict())


def read_dataset_plan_record(path: Path) -> contracts.DatasetPlanRecord:
    return contracts.DatasetPlanRecord.from_dict(_read_json(path))


def append_trial_history(path: Path, record: contracts.TrialInputRecord) -> None:
    _append_jsonl(path, record.to_dict())


def append_decision_history(path: Path, record: contracts.DecisionRecord) -> None:
    _append_jsonl(path, record.to_dict())


def read_jsonl_records(path: Path) -> list[dict[str, contracts.JsonValue]]:
    return read_jsonl(path)


def write_json_payload(path: Path, payload: dict[str, object]) -> None:
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def append_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)


def write_text(path: Path, text: str) -> None:
    _atomic_write_text(path, text)


def _write_json(path: Path, payload: dict[str, contracts.JsonValue]) -> None:
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def _read_json(path: Path) -> dict[str, contracts.JsonValue]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON at {path}: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON at {path}")
    return payload


def _append_jsonl(path: Path, payload: dict[str, contracts.JsonValue]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)
