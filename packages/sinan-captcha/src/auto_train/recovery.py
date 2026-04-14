"""Recovery planning helpers based on sequential study artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

_LEGACY_RECOVERY_RULES: tuple[tuple[str, str, str], ...] = (
    ("input.json", "PLAN", "PLAN"),
    ("dataset.json", "BUILD_DATASET", "BUILD_DATASET"),
    ("train.json", "TRAIN", "TRAIN"),
    ("test.json", "TEST", "TEST"),
    ("evaluate.json", "EVALUATE", "EVALUATE"),
    ("result_summary.json", "SUMMARIZE", "SUMMARIZE"),
    ("decision.json", "NEXT_ACTION", "JUDGE"),
)

_GROUP1_RECOVERY_RULES: tuple[tuple[str, str, str], ...] = (
    ("input.json", "PLAN", "PLAN"),
    ("dataset.json", "BUILD_DATASET", "BUILD_DATASET"),
    ("query_train.json", "TRAIN_QUERY", "TRAIN_QUERY"),
    ("query_gate.json", "QUERY_GATE", "QUERY_GATE"),
    ("scene_train.json", "TRAIN_SCENE", "TRAIN_SCENE"),
    ("scene_gate.json", "SCENE_GATE", "SCENE_GATE"),
    ("embedder_train.json", "TRAIN_EMBEDDER_BASE", "TRAIN_EMBEDDER_BASE"),
    ("embedder_gate.json", "EMBEDDER_GATE", "EMBEDDER_GATE"),
    ("embedder_hardset.json", "BUILD_EMBEDDER_HARDSET", "BUILD_EMBEDDER_HARDSET"),
    ("embedder_hard_train.json", "TRAIN_EMBEDDER_HARD", "TRAIN_EMBEDDER_HARD"),
    ("matcher_config.json", "CALIBRATE_MATCHER", "CALIBRATE_MATCHER"),
    ("offline_eval.json", "OFFLINE_EVAL", "OFFLINE_EVAL"),
    ("business_stage.json", "BUSINESS_EVAL", "BUSINESS_EVAL"),
    ("result_summary.json", "SUMMARIZE", "SUMMARIZE"),
    ("decision.json", "NEXT_ACTION", "JUDGE"),
)

_GROUP1_GATE_ARTIFACT_VERSION = 2


@dataclass(frozen=True)
class RecoveryPlan:
    resume_stage: str
    last_completed_stage: str | None
    completed_stages: tuple[str, ...]
    missing_artifacts: list[str]
    trial_complete: bool


def build_recovery_plan(
    trial_dir: Path,
    *,
    task: str | None = None,
    stop_file: Path | None = None,
) -> RecoveryPlan:
    """Return the earliest safe resume boundary for a trial directory."""

    if stop_file is not None and stop_file.exists():
        return RecoveryPlan(
            resume_stage="STOP",
            last_completed_stage=None,
            completed_stages=(),
            missing_artifacts=[],
            trial_complete=False,
        )

    completed_stages: list[str] = []
    rules = _GROUP1_RECOVERY_RULES if task == "group1" else _LEGACY_RECOVERY_RULES
    for artifact_name, completed_stage, resume_stage in rules:
        artifact_path = trial_dir / artifact_name
        if not artifact_path.exists() or (task == "group1" and not _validate_group1_artifact(trial_dir, artifact_name)):
            last_completed = completed_stages[-1] if completed_stages else None
            return RecoveryPlan(
                resume_stage=resume_stage,
                last_completed_stage=last_completed,
                completed_stages=tuple(completed_stages),
                missing_artifacts=[artifact_name],
                trial_complete=False,
            )
        completed_stages.append(completed_stage)

    return RecoveryPlan(
        resume_stage="NEXT_ACTION",
        last_completed_stage="NEXT_ACTION",
        completed_stages=tuple(completed_stages),
        missing_artifacts=[],
        trial_complete=True,
    )


def _validate_group1_artifact(trial_dir: Path, artifact_name: str) -> bool:
    if artifact_name == "query_gate.json":
        return _validate_group1_gate_artifact(
            trial_dir,
            artifact_name=artifact_name,
            train_record_name="query_train.json",
            component="query-detector",
        )
    if artifact_name == "scene_gate.json":
        return _validate_group1_gate_artifact(
            trial_dir,
            artifact_name=artifact_name,
            train_record_name="scene_train.json",
            component="proposal-detector",
        )
    if artifact_name == "embedder_gate.json":
        return _validate_group1_gate_artifact(
            trial_dir,
            artifact_name=artifact_name,
            train_record_name="embedder_train.json",
            component="icon-embedder",
        )
    return True


def _validate_group1_gate_artifact(
    trial_dir: Path,
    *,
    artifact_name: str,
    train_record_name: str,
    component: str,
) -> bool:
    gate_payload = _read_json_object(trial_dir / artifact_name)
    train_payload = _read_json_object(trial_dir / train_record_name)
    if gate_payload is None or train_payload is None:
        return False
    params = train_payload.get("params")
    if not isinstance(params, dict):
        return False
    weights = gate_payload.get("weights")
    gate = gate_payload.get("gate")
    if not isinstance(weights, dict) or not isinstance(gate, dict):
        return False
    if gate_payload.get("gate_version") != _GROUP1_GATE_ARTIFACT_VERSION:
        return False
    if gate_payload.get("component") != component:
        return False
    if gate_payload.get("dataset_config") != params.get("dataset_config"):
        return False
    if gate_payload.get("imgsz") != params.get("imgsz"):
        return False
    if gate_payload.get("device") != params.get("device"):
        return False
    if weights.get("best") != train_payload.get("best_weights"):
        return False
    if weights.get("last") != train_payload.get("last_weights"):
        return False
    status = gate_payload.get("status")
    summary_path = gate_payload.get("summary_path")
    return isinstance(status, str) and bool(status.strip()) and isinstance(summary_path, str) and bool(summary_path.strip())


def _read_json_object(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None
