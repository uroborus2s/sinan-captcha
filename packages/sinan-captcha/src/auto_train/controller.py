"""Stage-driven autonomous-training controller skeleton."""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from auto_train import (
    analysis,
    business_eval,
    contracts,
    dataset_plan,
    decision_protocol,
    embedder_review_protocol,
    group1_pipeline,
    json_extract,
    layout,
    opencode_assets,
    opencode_runtime,
    optimize,
    optuna_runtime,
    policies,
    retune_plan,
    runners,
    state_machine,
    stop_rules,
    storage,
    study_status,
    summary,
)
from common.jsonl import write_jsonl
from group2_semantics import GROUP2_LOCALIZATION_ALERT_CENTER_ERROR_PX
from solve.bundle import (
    GROUP1_MATCHER_AMBIGUITY_MARGIN,
    GROUP1_MATCHER_SIMILARITY_THRESHOLD,
    MATCHER_STRATEGY,
)
from train.base import (
    default_dataset_config,
    default_report_dir,
    default_run_dir,
    is_resumable_yolo_checkpoint,
    preferred_checkpoint_path,
)
from train.group1.dataset import load_group1_dataset_config
from train.group1.service import (
    DEFAULT_ICON_EMBEDDER_IMGSZ,
    EMBEDDER_COMPONENT,
    PROPOSAL_COMPONENT,
    QUERY_COMPONENT,
    resolve_group1_component_best_weights,
    resolve_group1_component_last_weights,
)

DEFAULT_JUDGE_PROVIDER = "rules"
DEFAULT_JUDGE_MODEL = "policy-v1"
GROUP1_GATE_ARTIFACT_VERSION = 2
GROUP1_EMBEDDER_GATE_RECALL_AT_1_MIN = 0.97
GROUP1_EMBEDDER_GATE_RECALL_AT_3_MIN = 0.995
GROUP1_EMBEDDER_GATE_SCENE_RECALL_AT_1_MIN = 0.97
GROUP1_EMBEDDER_GATE_SCENE_RECALL_AT_3_MIN = 0.995
GROUP1_EMBEDDER_GATE_IDENTITY_RECALL_AT_1_MIN = 0.85
GROUP1_COMPONENT_PLAN_PARAM = "group1_component_plan"
GROUP1_COMPONENT_PARAMS_PARAM = "group1_component_params"
GROUP1_COMPONENT_PLAN_TRAIN = "train"
GROUP1_COMPONENT_PLAN_REUSE = "reuse"
GROUP1_EMBEDDER_HARDSET_REBUILD_COUNT_PARAM = "embedder_hardset_rebuild_count"


def default_generator_executable() -> str:
    if os.name == "nt":
        return "sinan-generator.exe"
    return "sinan-generator"

STAGE_ALIASES = {
    "plan": "PLAN",
    "build-dataset": "BUILD_DATASET",
    "train": "TRAIN",
    "train-query": "TRAIN_QUERY",
    "query-gate": "QUERY_GATE",
    "train-scene": "TRAIN_SCENE",
    "scene-gate": "SCENE_GATE",
    "train-embedder-base": "TRAIN_EMBEDDER_BASE",
    "embedder-gate": "EMBEDDER_GATE",
    "build-embedder-hardset": "BUILD_EMBEDDER_HARDSET",
    "train-embedder-hard": "TRAIN_EMBEDDER_HARD",
    "calibrate-matcher": "CALIBRATE_MATCHER",
    "offline-eval": "OFFLINE_EVAL",
    "business-eval": "BUSINESS_EVAL",
    "test": "TEST",
    "evaluate": "EVALUATE",
    "summarize": "SUMMARIZE",
    "judge": "JUDGE",
    "next-action": "NEXT_ACTION",
    "stop": "STOP",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _console_timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _evaluate_query_detector_for_recovery(
    *,
    dataset_config_path: Path,
    model_path: Path,
    imgsz: int,
    device: str,
) -> tuple[dict[str, float | int | None], dict[str, object], list[dict[str, object]]]:
    from train.group1.runner import _evaluate_query_detector_component

    return _evaluate_query_detector_component(
        dataset_config=load_group1_dataset_config(dataset_config_path),
        model_path=model_path,
        imgsz=imgsz,
        device=device,
    )


def _evaluate_proposal_detector_for_recovery(
    *,
    dataset_config_path: Path,
    model_path: Path,
    imgsz: int,
    device: str,
) -> tuple[dict[str, float | int | None], dict[str, object], list[dict[str, object]]]:
    from train.group1.runner import _evaluate_proposal_detector_component

    return _evaluate_proposal_detector_component(
        dataset_config=load_group1_dataset_config(dataset_config_path),
        model_path=model_path,
        imgsz=imgsz,
        device=device,
    )


@dataclass(frozen=True)
class AutoTrainRequest:
    task: str
    study_name: str
    train_root: Path
    generator_workspace: Path
    studies_root: Path
    generator_executable: str = default_generator_executable()
    mode: str = "full_auto"
    judge_provider: str = DEFAULT_JUDGE_PROVIDER
    judge_model: str = DEFAULT_JUDGE_MODEL
    opencode_attach_url: str | None = None
    opencode_binary: str = opencode_runtime.DEFAULT_OPENCODE_BINARY
    opencode_timeout_seconds: float = opencode_runtime.DEFAULT_TIMEOUT_SECONDS
    max_trials: int = 20
    max_hours: float = 24.0
    max_new_datasets: int | None = None
    max_no_improve_trials: int | None = 4
    dataset_version: str = "v1"
    train_name: str | None = None
    train_mode: str = "fresh"
    base_run: str | None = None
    model: str | None = None
    epochs: int | None = None
    batch: int | None = None
    imgsz: int | None = None
    device: str = "0"
    gold_dir: Path | None = None
    prediction_dir: Path | None = None
    point_tolerance_px: int = 5
    iou_threshold: float = 0.5
    business_eval_dir: Path | None = None
    business_eval_success_threshold: float = 0.90
    business_eval_min_cases: int = 50
    business_eval_sample_size: int = 50
    goal_only_stop: bool = False

    def __post_init__(self) -> None:
        if self.task not in contracts.ALLOWED_TASKS:
            raise ValueError(f"unsupported task: {self.task}")
        if self.mode not in contracts.ALLOWED_STUDY_MODES:
            raise ValueError(f"unsupported mode: {self.mode}")
        if self.train_mode not in contracts.ALLOWED_TRAIN_MODES:
            raise ValueError(f"unsupported train_mode: {self.train_mode}")
        if self.max_trials <= 0:
            raise ValueError("max_trials must be greater than 0")
        if self.max_hours <= 0:
            raise ValueError("max_hours must be greater than 0")
        if self.max_no_improve_trials is not None and self.max_no_improve_trials <= 0:
            raise ValueError("max_no_improve_trials must be greater than 0")
        if self.opencode_timeout_seconds <= 0:
            raise ValueError("opencode_timeout_seconds must be greater than 0")
        if self.business_eval_dir is not None:
            if not 0.0 <= self.business_eval_success_threshold <= 1.0:
                raise ValueError("business_eval_success_threshold must be between 0.0 and 1.0")
            if self.business_eval_min_cases <= 0:
                raise ValueError("business_eval_min_cases must be greater than 0")
            if self.business_eval_sample_size <= 0:
                raise ValueError("business_eval_sample_size must be greater than 0")
            if self.business_eval_min_cases < self.business_eval_sample_size:
                raise ValueError("business_eval_min_cases must be greater than or equal to business_eval_sample_size")

    @property
    def effective_imgsz(self) -> int:
        if self.imgsz is not None:
            return self.imgsz
        return 192 if self.task == "group2" else 640


@dataclass(frozen=True)
class StageExecution:
    trial_id: str
    stage: str
    next_stage: str
    detail: str


@dataclass(frozen=True)
class AutoTrainRunResult:
    study_name: str
    task: str
    executed: list[StageExecution]
    final_stage: str


@dataclass(frozen=True)
class ControllerDependencies:
    dataset_runner: object = runners.dataset.run_dataset_request
    train_runner: object = runners.train.run_training_request
    test_runner: object = runners.test.run_test_request
    evaluate_runner: object = runners.evaluate.run_evaluation_request
    business_eval_runner: object = runners.business_eval.run_business_eval_request
    summary_builder: object = summary.build_result_summary
    opencode_runtime: object | None = None
    optuna_runtime: object | None = None
    now_provider: object = _utc_now
    query_detector_evaluator: object = _evaluate_query_detector_for_recovery
    proposal_detector_evaluator: object = _evaluate_proposal_detector_for_recovery
    console_writer: object = print


class AutoTrainController:
    def __init__(
        self,
        *,
        request: AutoTrainRequest,
        dependencies: ControllerDependencies | None = None,
    ) -> None:
        self.request = request
        self.dependencies = dependencies or ControllerDependencies()
        self.paths = layout.StudyPaths(
            studies_root=request.studies_root,
            task=request.task,
            study_name=request.study_name,
        )
        self.paths.ensure_layout()

    def _write_console(self, message: str) -> None:
        writer = self.dependencies.console_writer
        if writer is not None:
            writer(f"{_console_timestamp()} {message}")

    def _backup_timestamp_parts(self) -> tuple[str, str]:
        current = self.dependencies.now_provider()
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        current_utc = current.astimezone(timezone.utc)
        return current_utc.strftime("%Y%m%dT%H%M%S%fZ"), current_utc.isoformat(timespec="seconds")

    def _reserve_backup_dir(self, root: Path, *, prefix: str) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        candidate = root / prefix
        suffix = 1
        while candidate.exists():
            candidate = root / f"{prefix}_{suffix:02d}"
            suffix += 1
        candidate.mkdir(parents=True, exist_ok=False)
        return candidate

    def _backup_embedder_base_artifacts_for_hard_stage(
        self,
        *,
        trial_id: str,
        embedder_record: contracts.TrainRecord,
    ) -> Path | None:
        source_files: dict[str, Path] = {}
        best_path = _optional_path(embedder_record.best_weights)
        last_path = _optional_path(embedder_record.last_weights)
        if best_path is not None and best_path.exists():
            source_files["best_weights"] = best_path
        if last_path is not None and last_path.exists():
            source_files["last_weights"] = last_path

        train_record_path = self.paths.embedder_train_file(trial_id)
        if train_record_path.exists():
            source_files["train_record"] = train_record_path

        run_dir_text = embedder_record.run_dir.strip()
        if run_dir_text:
            summary_path = Path(run_dir_text) / EMBEDDER_COMPONENT / "summary.json"
            if summary_path.exists():
                source_files["summary"] = summary_path

        if not source_files:
            self._write_console(
                "embedder_checkpoint_backup "
                f"trial={trial_id} "
                "stage=TRAIN_EMBEDDER_HARD "
                "status=skipped "
                "reason=no_base_artifacts"
            )
            return None

        stamp, backup_created_at = self._backup_timestamp_parts()
        backup_dir = self._reserve_backup_dir(
            self.paths.embedder_backup_root(trial_id),
            prefix=f"pre_hard_{stamp}",
        )
        file_names = {
            "best_weights": "best.pt",
            "last_weights": "last.pt",
            "train_record": "embedder_train.json",
            "summary": "summary.json",
        }
        copied_files: dict[str, str] = {}
        source_map: dict[str, str] = {}
        for key, source_path in source_files.items():
            destination = backup_dir / file_names[key]
            shutil.copy2(source_path, destination)
            copied_files[key] = str(destination)
            source_map[key] = str(source_path)
        storage.write_json_payload(
            backup_dir / "metadata.json",
            {
                "trial_id": trial_id,
                "stage": "TRAIN_EMBEDDER_HARD",
                "created_at": backup_created_at,
                "source_files": source_map,
                "copied_files": copied_files,
            },
        )
        copied_labels = ",".join(sorted(copied_files))
        self._write_console(
            "embedder_checkpoint_backup "
            f"trial={trial_id} "
            "stage=TRAIN_EMBEDDER_HARD "
            "status=ready "
            f"backup_dir={backup_dir} "
            f"copied={copied_labels}"
        )
        return backup_dir

    def run(self, *, max_steps: int = 1, force_stage: str | None = None) -> AutoTrainRunResult:
        if max_steps < 0:
            raise ValueError("max_steps must not be negative")

        study = self._load_or_create_study()
        trial_id = self._ensure_current_trial(study)
        current_stage = self._normalize_stage_name_for_task(force_stage) if force_stage is not None else self._current_stage(study, trial_id)
        self._write_console(
            "controller_run "
            f"study={self.request.study_name} "
            f"task={self.request.task} "
            f"trial={trial_id} "
            f"current_stage={current_stage}"
        )
        executed: list[StageExecution] = []

        steps_run = 0
        while True:
            if current_stage == "STOP":
                break
            if max_steps > 0 and steps_run >= max_steps:
                break
            execution = self._run_stage(current_stage)
            executed.append(execution)
            current_stage = execution.next_stage
            steps_run += 1

        return AutoTrainRunResult(
            study_name=self.request.study_name,
            task=self.request.task,
            executed=executed,
            final_stage=current_stage,
        )

    def run_stage(self, stage: str) -> StageExecution:
        return self._run_stage(self._normalize_stage_name_for_task(stage))

    def _run_stage(self, stage: str) -> StageExecution:
        study = self._load_or_create_study()
        trial_id = self._ensure_current_trial(study)
        self._write_console(
            "controller_stage_start "
            f"study={self.request.study_name} "
            f"task={self.request.task} "
            f"trial={trial_id} "
            f"stage={stage}"
        )
        if stage == "PLAN":
            return self._stage_plan(trial_id)
        if stage == "BUILD_DATASET":
            return self._stage_build_dataset(trial_id)
        if stage == "TRAIN":
            if self.request.task == "group1":
                return self._stage_train_query(trial_id)
            return self._stage_train(trial_id)
        if stage == "TRAIN_QUERY":
            return self._stage_train_query(trial_id)
        if stage == "QUERY_GATE":
            return self._stage_query_gate(trial_id)
        if stage == "TRAIN_SCENE":
            return self._stage_train_scene(trial_id)
        if stage == "SCENE_GATE":
            return self._stage_scene_gate(trial_id)
        if stage == "TRAIN_EMBEDDER_BASE":
            return self._stage_train_embedder_base(trial_id)
        if stage == "EMBEDDER_GATE":
            return self._stage_embedder_gate(trial_id)
        if stage == "BUILD_EMBEDDER_HARDSET":
            return self._stage_build_embedder_hardset(trial_id)
        if stage == "TRAIN_EMBEDDER_HARD":
            return self._stage_train_embedder_hard(trial_id)
        if stage == "CALIBRATE_MATCHER":
            return self._stage_calibrate_matcher(trial_id)
        if stage == "OFFLINE_EVAL":
            return self._stage_offline_eval(trial_id)
        if stage == "BUSINESS_EVAL":
            return self._stage_business_eval(trial_id)
        if stage == "TEST":
            return self._stage_test(trial_id)
        if stage == "EVALUATE":
            return self._stage_evaluate(trial_id)
        if stage == "SUMMARIZE":
            return self._stage_summarize(trial_id)
        if stage == "JUDGE":
            return self._stage_judge(trial_id)
        if stage == "NEXT_ACTION":
            return self._stage_next_action(trial_id)
        if stage == "STOP":
            return StageExecution(trial_id=trial_id, stage="STOP", next_stage="STOP", detail="stop")
        raise ValueError(f"unsupported stage: {stage}")

    def _stage_plan(self, trial_id: str) -> StageExecution:
        input_path = self.paths.input_file(trial_id)
        if not input_path.exists():
            record = self._build_initial_trial_input(trial_id)
            storage.write_trial_input_record(input_path, record)
            storage.append_trial_history(self.paths.trial_history_file, record)
        return StageExecution(
            trial_id=trial_id,
            stage="PLAN",
            next_stage=state_machine.next_stage("PLAN", task=self.request.task),
            detail=str(input_path),
        )

    def _stage_build_dataset(self, trial_id: str) -> StageExecution:
        input_record = storage.read_trial_input_record(self.paths.input_file(trial_id))
        dataset_path = self.paths.dataset_file(trial_id)
        dataset_dir = self.request.train_root / "datasets" / self.request.task / input_record.dataset_version
        dataset_config = default_dataset_config(self.request.train_root, self.request.task, input_record.dataset_version)
        if dataset_dir.exists() and dataset_config.exists():
            record = contracts.DatasetRecord(
                task=self.request.task,
                dataset_version=input_record.dataset_version,
                dataset_root=str(dataset_dir),
                label_source="existing_dataset",
            )
            storage.write_dataset_record(dataset_path, record)
        else:
            override_file = self._materialize_generator_override_file(
                trial_id=trial_id,
                override_payload=input_record.dataset_override,
            )
            result = self.dependencies.dataset_runner(
                runners.dataset.DatasetRunnerRequest(
                    task=self.request.task,
                    dataset_version=input_record.dataset_version,
                    generator_workspace=self.request.generator_workspace,
                    dataset_dir=dataset_dir,
                    preset=input_record.dataset_preset or _infer_dataset_preset(input_record.dataset_version),
                    override_file=override_file,
                    generator_executable=self.request.generator_executable,
                    force=dataset_dir.exists(),
                )
            )
            storage.write_dataset_record(dataset_path, result.record)
        return StageExecution(
            trial_id=trial_id,
            stage="BUILD_DATASET",
            next_stage=state_machine.next_stage("BUILD_DATASET", task=self.request.task),
            detail=str(dataset_path),
        )

    def _stage_train(self, trial_id: str) -> StageExecution:
        input_record = storage.read_trial_input_record(self.paths.input_file(trial_id))
        result = self.dependencies.train_runner(
            runners.train.TrainRunnerRequest(
                task=self.request.task,
                train_root=self.request.train_root,
                dataset_version=input_record.dataset_version,
                train_name=input_record.train_name,
                train_mode=input_record.train_mode,
                base_run=input_record.base_run,
                model=_string_value(input_record.params, "model"),
                epochs=_int_value(input_record.params, "epochs"),
                batch=_int_value(input_record.params, "batch"),
                imgsz=_int_value(input_record.params, "imgsz", default=self.request.effective_imgsz),
                device=_string_value(input_record.params, "device", default=self.request.device) or self.request.device,
            )
        )
        storage.write_train_record(self.paths.train_file(trial_id), result.record)
        return StageExecution(
            trial_id=trial_id,
            stage="TRAIN",
            next_stage=state_machine.next_stage("TRAIN", task=self.request.task),
            detail=result.command,
        )

    def _stage_train_query(self, trial_id: str) -> StageExecution:
        return self._stage_train_group1_component(
            trial_id=trial_id,
            stage="TRAIN_QUERY",
            component=QUERY_COMPONENT,
            record_path=self.paths.query_train_file(trial_id),
            write_legacy_train=False,
        )

    def _stage_query_gate(self, trial_id: str) -> StageExecution:
        gate_path = self.paths.query_gate_file(trial_id)
        train_record = storage.read_train_record(self.paths.query_train_file(trial_id))
        component_summary = self._read_group1_component_summary(train_record, QUERY_COMPONENT)
        best_path = _optional_path(component_summary.get("weights", {}).get("best", train_record.best_weights or ""))
        last_path = _optional_path(component_summary.get("weights", {}).get("last", train_record.last_weights or ""))
        gate = component_summary.get("gate", {})
        gate_status = _gate_status(gate)
        dataset_config_path, imgsz, device = self._resolve_group1_component_runtime_context(
            trial_id=trial_id,
            train_record=train_record,
        )
        recomputed = False
        if gate_status == "missing":
            model_path = _preferred_existing_checkpoint(best_path, last_path)
            if model_path is not None:
                metrics, gate, failcases = self.dependencies.query_detector_evaluator(
                    dataset_config_path=dataset_config_path,
                    model_path=model_path,
                    imgsz=imgsz,
                    device=device,
                )
                failcases_path = Path(train_record.run_dir) / QUERY_COMPONENT / "failcases.jsonl"
                write_jsonl(failcases_path, failcases)
                component_summary = {
                    **component_summary,
                    "metrics": metrics,
                    "gate": gate,
                    "failcases": str(failcases_path),
                }
                self._patch_group1_component_summary(
                    train_record=train_record,
                    component=QUERY_COMPONENT,
                    component_summary=component_summary,
                    dataset_config_path=dataset_config_path,
                )
                gate_status = _gate_status(gate)
                recomputed = True
        gate_payload = self._build_group1_gate_payload(
            trial_id=trial_id,
            component=QUERY_COMPONENT,
            train_record=train_record,
            dataset_config_path=dataset_config_path,
            imgsz=imgsz,
            device=device,
            best_path=best_path,
            last_path=last_path,
            component_summary=component_summary,
            gate=gate,
            gate_status=gate_status,
        )
        storage.write_json_payload(gate_path, gate_payload)
        self._write_console(
            "group1_gate "
            f"trial={trial_id} "
            f"stage=QUERY_GATE "
            f"component={QUERY_COMPONENT} "
            f"action={'recompute_missing_gate' if recomputed else 'reuse_summary'} "
            f"status={gate_status} "
            f"dataset_config={dataset_config_path} "
            f"checkpoint={_checkpoint_text(_preferred_existing_checkpoint(best_path, last_path))}"
        )
        return StageExecution(
            trial_id=trial_id,
            stage="QUERY_GATE",
            next_stage=state_machine.next_stage("QUERY_GATE", task=self.request.task),
            detail=str(gate_path),
        )

    def _stage_train_scene(self, trial_id: str) -> StageExecution:
        return self._stage_train_group1_component(
            trial_id=trial_id,
            stage="TRAIN_SCENE",
            component=PROPOSAL_COMPONENT,
            record_path=self.paths.scene_train_file(trial_id),
            write_legacy_train=True,
        )

    def _stage_scene_gate(self, trial_id: str) -> StageExecution:
        gate_path = self.paths.scene_gate_file(trial_id)
        train_record = storage.read_train_record(self.paths.scene_train_file(trial_id))
        component_summary = self._read_group1_component_summary(train_record, PROPOSAL_COMPONENT)
        best_path = _optional_path(component_summary.get("weights", {}).get("best", train_record.best_weights or ""))
        last_path = _optional_path(component_summary.get("weights", {}).get("last", train_record.last_weights or ""))
        gate = component_summary.get("gate", {})
        gate_status = _gate_status(gate)
        dataset_config_path, imgsz, device = self._resolve_group1_component_runtime_context(
            trial_id=trial_id,
            train_record=train_record,
        )
        recomputed = False
        model_path = _preferred_existing_checkpoint(best_path, last_path)
        if gate_status == "missing" and model_path is not None:
            metrics, gate, failcases = self.dependencies.proposal_detector_evaluator(
                dataset_config_path=dataset_config_path,
                model_path=model_path,
                imgsz=imgsz,
                device=device,
            )
            failcases_path = Path(train_record.run_dir) / PROPOSAL_COMPONENT / "failcases.jsonl"
            write_jsonl(failcases_path, failcases)
            component_summary = {
                **component_summary,
                "metrics": metrics,
                "gate": gate,
                "failcases": str(failcases_path),
            }
            self._patch_group1_component_summary(
                train_record=train_record,
                component=PROPOSAL_COMPONENT,
                component_summary=component_summary,
                dataset_config_path=dataset_config_path,
            )
            gate_status = _gate_status(gate)
            recomputed = True
        gate_payload = self._build_group1_gate_payload(
            trial_id=trial_id,
            component=PROPOSAL_COMPONENT,
            train_record=train_record,
            dataset_config_path=dataset_config_path,
            imgsz=imgsz,
            device=device,
            best_path=best_path,
            last_path=last_path,
            component_summary=component_summary,
            gate=gate,
            gate_status=gate_status,
        )
        storage.write_json_payload(gate_path, gate_payload)
        self._write_console(
            "group1_gate "
            f"trial={trial_id} "
            f"stage=SCENE_GATE "
            f"component={PROPOSAL_COMPONENT} "
            f"action={'recompute_missing_gate' if recomputed else 'reuse_summary'} "
            f"status={gate_status} "
            f"dataset_config={dataset_config_path} "
            f"checkpoint={_checkpoint_text(model_path)}"
        )
        return StageExecution(
            trial_id=trial_id,
            stage="SCENE_GATE",
            next_stage=state_machine.next_stage("SCENE_GATE", task=self.request.task),
            detail=str(gate_path),
        )

    def _stage_train_embedder_base(self, trial_id: str) -> StageExecution:
        return self._stage_train_group1_component(
            trial_id=trial_id,
            stage="TRAIN_EMBEDDER_BASE",
            component=EMBEDDER_COMPONENT,
            record_path=self.paths.embedder_train_file(trial_id),
            write_legacy_train=False,
            imgsz_override=DEFAULT_ICON_EMBEDDER_IMGSZ,
        )

    def _stage_embedder_gate(self, trial_id: str) -> StageExecution:
        gate_path = self.paths.embedder_gate_file(trial_id)
        train_record = storage.read_train_record(self.paths.embedder_train_file(trial_id))
        component_summary = self._read_group1_component_summary(train_record, EMBEDDER_COMPONENT)
        best_path = _optional_path(component_summary.get("weights", {}).get("best", train_record.best_weights or ""))
        last_path = _optional_path(component_summary.get("weights", {}).get("last", train_record.last_weights or ""))
        dataset_config_path, imgsz, device = self._resolve_group1_component_runtime_context(
            trial_id=trial_id,
            train_record=train_record,
        )
        metrics = component_summary.get("metrics")
        if not isinstance(metrics, dict) or not metrics:
            metrics = self._load_group1_embedder_metrics(train_record)
            component_summary = {
                **component_summary,
                "metrics": metrics,
            }
        gate = self._build_group1_embedder_gate(metrics)
        gate_status = _gate_status(gate)
        component_summary = {
            **component_summary,
            "gate": gate,
        }
        self._patch_group1_component_summary(
            train_record=train_record,
            component=EMBEDDER_COMPONENT,
            component_summary=component_summary,
            dataset_config_path=dataset_config_path,
        )
        gate_payload = self._build_group1_gate_payload(
            trial_id=trial_id,
            component=EMBEDDER_COMPONENT,
            train_record=train_record,
            dataset_config_path=dataset_config_path,
            imgsz=imgsz,
            device=device,
            best_path=best_path,
            last_path=last_path,
            component_summary=component_summary,
            gate=gate,
            gate_status=gate_status,
        )
        storage.write_json_payload(gate_path, gate_payload)
        self._write_console(
            "group1_gate "
            f"trial={trial_id} "
            f"stage=EMBEDDER_GATE "
            f"component={EMBEDDER_COMPONENT} "
            "action=evaluate_summary "
            f"status={gate_status} "
            f"dataset_config={dataset_config_path} "
            f"checkpoint={_checkpoint_text(_preferred_existing_checkpoint(best_path, last_path))}"
        )
        next_stage = (
            state_machine.next_stage("EMBEDDER_GATE", task=self.request.task)
            if self._group1_component_action(
                storage.read_trial_input_record(self.paths.input_file(trial_id)),
                component=EMBEDDER_COMPONENT,
            )
            == GROUP1_COMPONENT_PLAN_TRAIN
            else "CALIBRATE_MATCHER"
        )
        return StageExecution(
            trial_id=trial_id,
            stage="EMBEDDER_GATE",
            next_stage=next_stage,
            detail=str(gate_path),
        )

    def _stage_build_embedder_hardset(self, trial_id: str) -> StageExecution:
        input_record = storage.read_trial_input_record(self.paths.input_file(trial_id))
        if self._group1_component_action(input_record, component=EMBEDDER_COMPONENT) == GROUP1_COMPONENT_PLAN_REUSE:
            return StageExecution(
                trial_id=trial_id,
                stage="BUILD_EMBEDDER_HARDSET",
                next_stage="CALIBRATE_MATCHER",
                detail="skip_embedder_hardset_reuse",
            )
        dataset_config = load_group1_dataset_config(
            default_dataset_config(self.request.train_root, self.request.task, input_record.dataset_version)
        )
        query_record = storage.read_train_record(self.paths.query_train_file(trial_id))
        scene_record = storage.read_train_record(self.paths.scene_train_file(trial_id))
        embedder_record = storage.read_train_record(self.paths.embedder_train_file(trial_id))
        hardset_root = self.paths.trial_dir(trial_id) / "embedder_hardset"
        query_model_path = preferred_checkpoint_path(Path(query_record.best_weights), Path(query_record.last_weights))
        scene_model_path = preferred_checkpoint_path(Path(scene_record.best_weights), Path(scene_record.last_weights))
        embedder_model_path = preferred_checkpoint_path(Path(embedder_record.best_weights), Path(embedder_record.last_weights))
        notes: list[str] = []
        if query_model_path.exists() and scene_model_path.exists():
            try:
                result = group1_pipeline.build_detector_aware_hardset(
                    dataset_config=dataset_config,
                    output_root=hardset_root,
                    query_model_path=query_model_path,
                    proposal_model_path=scene_model_path,
                    embedder_model_path=embedder_model_path if embedder_model_path.exists() else None,
                    imgsz=_int_value(input_record.params, "imgsz", default=self.request.effective_imgsz),
                    device=_string_value(input_record.params, "device", default=self.request.device) or self.request.device,
                    progress_callback=self._write_console,
                )
                strategy = "detector_aware_hardset_v1"
                dataset_config_path = result.dataset_config_path
                result_payload = result.to_dict()
            except RuntimeError as exc:
                strategy = "fallback_base_triplets_v1"
                dataset_config_path = dataset_config.path
                result_payload = {
                    "output_root": str(hardset_root),
                    "dataset_config_path": str(dataset_config.path),
                    "pair_count": 0,
                    "triplet_count": 0,
                    "anchor_fallback_count": 0,
                    "positive_fallback_count": 0,
                    "false_positive_negative_count": 0,
                    "split_stats": {},
                }
                notes.append(f"hardset_builder_fallback={exc}")
        else:
            strategy = "fallback_base_triplets_v1"
            dataset_config_path = dataset_config.path
            result_payload = {
                "output_root": str(hardset_root),
                "dataset_config_path": str(dataset_config.path),
                "pair_count": 0,
                "triplet_count": 0,
                "anchor_fallback_count": 0,
                "positive_fallback_count": 0,
                "false_positive_negative_count": 0,
                "split_stats": {},
            }
            notes.append("hardset_builder_fallback=missing_detector_checkpoints")
        payload = {
            "trial_id": trial_id,
            "dataset_version": input_record.dataset_version,
            "status": "ready",
            "strategy": strategy,
            "dataset_config_path": str(dataset_config_path),
            "source_triplets_jsonl": None if dataset_config.embedding is None else str(dataset_config.embedding.triplets_jsonl),
            "query_detector_weights": {
                "best": query_record.best_weights,
                "last": query_record.last_weights,
            },
            "scene_detector_weights": {
                "best": scene_record.best_weights,
                "last": scene_record.last_weights,
            },
            "embedder_base_weights": {
                "best": embedder_record.best_weights,
                "last": embedder_record.last_weights,
            },
            "notes": notes,
            **result_payload,
        }
        storage.write_json_payload(self.paths.embedder_hardset_file(trial_id), payload)
        return StageExecution(
            trial_id=trial_id,
            stage="BUILD_EMBEDDER_HARDSET",
            next_stage=state_machine.next_stage("BUILD_EMBEDDER_HARDSET", task=self.request.task),
            detail=str(self.paths.embedder_hardset_file(trial_id)),
        )

    def _stage_train_embedder_hard(self, trial_id: str) -> StageExecution:
        input_record = storage.read_trial_input_record(self.paths.input_file(trial_id))
        if self._group1_component_action(input_record, component=EMBEDDER_COMPONENT) == GROUP1_COMPONENT_PLAN_REUSE:
            return StageExecution(
                trial_id=trial_id,
                stage="TRAIN_EMBEDDER_HARD",
                next_stage="CALIBRATE_MATCHER",
                detail="skip_embedder_hard_train_reuse",
            )
        hardset_payload = self._read_json_payload(self.paths.embedder_hardset_file(trial_id))
        embedder_record = storage.read_train_record(self.paths.embedder_train_file(trial_id))
        self._backup_embedder_base_artifacts_for_hard_stage(
            trial_id=trial_id,
            embedder_record=embedder_record,
        )
        embedder_checkpoint = preferred_checkpoint_path(
            Path(embedder_record.best_weights),
            Path(embedder_record.last_weights),
        )
        execution = self._stage_train_group1_component(
            trial_id=trial_id,
            stage="TRAIN_EMBEDDER_HARD",
            component=EMBEDDER_COMPONENT,
            record_path=self.paths.embedder_hard_train_file(trial_id),
            write_legacy_train=False,
            train_mode_override="fresh",
            dataset_config_override=Path(str(hardset_payload["dataset_config_path"])),
            model_override=str(embedder_checkpoint) if embedder_checkpoint.exists() else None,
            imgsz_override=DEFAULT_ICON_EMBEDDER_IMGSZ,
        )
        train_record = storage.read_train_record(self.paths.embedder_hard_train_file(trial_id))
        review_decision = _string_value(train_record.params, "review_decision")
        if review_decision == embedder_review_protocol.EMBEDDER_REVIEW_DECISION_REBUILD_HARDSET:
            rebuild_count = self._increment_embedder_hardset_rebuild_count(trial_id)
            if rebuild_count <= embedder_review_protocol.MAX_EMBEDDER_HARDSET_REBUILDS_PER_TRIAL:
                self._write_console(
                    "embedder_review_action "
                    f"trial={trial_id} "
                    "stage=TRAIN_EMBEDDER_HARD "
                    "decision=REBUILD_HARDSET "
                    f"rebuild_count={rebuild_count}"
                )
                return StageExecution(
                    trial_id=execution.trial_id,
                    stage=execution.stage,
                    next_stage="BUILD_EMBEDDER_HARDSET",
                    detail=f"{execution.detail} review_decision=REBUILD_HARDSET",
                )
            self._write_console(
                "embedder_review_action "
                f"trial={trial_id} "
                "stage=TRAIN_EMBEDDER_HARD "
                "decision=REBUILD_HARDSET_IGNORED "
                f"rebuild_count={rebuild_count}"
            )
        return execution

    def _stage_calibrate_matcher(self, trial_id: str) -> StageExecution:
        input_record = storage.read_trial_input_record(self.paths.input_file(trial_id))
        dataset_config = load_group1_dataset_config(
            default_dataset_config(self.request.train_root, self.request.task, input_record.dataset_version)
        )
        query_record = storage.read_train_record(self.paths.query_train_file(trial_id))
        scene_record = storage.read_train_record(self.paths.scene_train_file(trial_id))
        embedder_path = (
            self.paths.embedder_hard_train_file(trial_id)
            if self.paths.embedder_hard_train_file(trial_id).exists()
            else self.paths.embedder_train_file(trial_id)
        )
        embedder_record = storage.read_train_record(embedder_path)
        query_model_path = preferred_checkpoint_path(Path(query_record.best_weights), Path(query_record.last_weights))
        scene_model_path = preferred_checkpoint_path(Path(scene_record.best_weights), Path(scene_record.last_weights))
        embedder_model_path = preferred_checkpoint_path(Path(embedder_record.best_weights), Path(embedder_record.last_weights))
        calibration_mode = "grid_search_v1"
        sample_count = 0
        best_metrics: dict[str, float | None] = {}
        candidate_metrics: list[dict[str, object]] = []
        if query_model_path.exists() and scene_model_path.exists() and embedder_model_path.exists():
            try:
                result = group1_pipeline.calibrate_matcher(
                    dataset_config=dataset_config,
                    query_model_path=query_model_path,
                    proposal_model_path=scene_model_path,
                    embedder_model_path=embedder_model_path,
                    imgsz=_int_value(input_record.params, "imgsz", default=self.request.effective_imgsz),
                    device=_string_value(input_record.params, "device", default=self.request.device) or self.request.device,
                    point_tolerance_px=self.request.point_tolerance_px,
                )
                similarity_threshold = result.selected_similarity_threshold
                ambiguity_margin = result.selected_ambiguity_margin
                sample_count = result.sample_count
                best_metrics = result.best_metrics
                candidate_metrics = result.candidate_metrics
            except RuntimeError as exc:
                calibration_mode = "fallback_static_defaults_v1"
                similarity_threshold = GROUP1_MATCHER_SIMILARITY_THRESHOLD
                ambiguity_margin = GROUP1_MATCHER_AMBIGUITY_MARGIN
                best_metrics = {}
                candidate_metrics = [{"warning": f"matcher_calibration_fallback={exc}"}]
        else:
            calibration_mode = "fallback_static_defaults_v1"
            similarity_threshold = GROUP1_MATCHER_SIMILARITY_THRESHOLD
            ambiguity_margin = GROUP1_MATCHER_AMBIGUITY_MARGIN
            candidate_metrics = [{"warning": "matcher_calibration_fallback=missing_component_checkpoints"}]
        payload = {
            "trial_id": trial_id,
            "status": "ready",
            "strategy": MATCHER_STRATEGY,
            "similarity_threshold": similarity_threshold,
            "ambiguity_margin": ambiguity_margin,
            "query_detector_weights": {
                "best": query_record.best_weights,
                "last": query_record.last_weights,
            },
            "scene_detector_weights": {
                "best": scene_record.best_weights,
                "last": scene_record.last_weights,
            },
            "embedder_weights": {
                "best": embedder_record.best_weights,
                "last": embedder_record.last_weights,
            },
            "calibration_mode": calibration_mode,
            "sample_count": sample_count,
            "best_metrics": best_metrics,
            "candidate_metrics": candidate_metrics,
        }
        storage.write_json_payload(self.paths.matcher_config_file(trial_id), payload)
        return StageExecution(
            trial_id=trial_id,
            stage="CALIBRATE_MATCHER",
            next_stage=state_machine.next_stage("CALIBRATE_MATCHER", task=self.request.task),
            detail=str(self.paths.matcher_config_file(trial_id)),
        )

    def _stage_offline_eval(self, trial_id: str) -> StageExecution:
        test_execution = self._stage_test(trial_id)
        evaluate_execution = self._stage_evaluate(trial_id)
        payload = {
            "trial_id": trial_id,
            "status": "ready",
            "test_record": str(self.paths.test_file(trial_id)),
            "evaluate_record": str(self.paths.evaluate_file(trial_id)),
            "test_detail": test_execution.detail,
            "evaluate_detail": evaluate_execution.detail,
        }
        storage.write_json_payload(self.paths.offline_eval_file(trial_id), payload)
        return StageExecution(
            trial_id=trial_id,
            stage="OFFLINE_EVAL",
            next_stage=state_machine.next_stage("OFFLINE_EVAL", task=self.request.task),
            detail=str(self.paths.offline_eval_file(trial_id)),
        )

    def _stage_business_eval(self, trial_id: str) -> StageExecution:
        study = self._load_or_create_study()
        marker_path = self.paths.business_stage_file(trial_id)
        if study.business_eval is None:
            storage.write_json_payload(
                marker_path,
                {
                    "trial_id": trial_id,
                    "status": "skipped",
                    "reason": "business_eval_disabled",
                },
            )
            return StageExecution(
                trial_id=trial_id,
                stage="BUSINESS_EVAL",
                next_stage=state_machine.next_stage("BUSINESS_EVAL", task=self.request.task),
                detail=str(marker_path),
            )

        input_record = storage.read_trial_input_record(self.paths.input_file(trial_id))
        config = study.business_eval
        request = self._build_business_eval_request(
            trial_id=trial_id,
            dataset_version=input_record.dataset_version,
            train_name=input_record.train_name,
            config=config,
        )
        record = self._execute_business_eval_request(request=request)
        self._write_business_eval_artifacts(trial_id=trial_id, record=record)
        storage.write_json_payload(
            marker_path,
            {
                "trial_id": trial_id,
                "status": "ready",
                "business_eval_file": str(self.paths.business_eval_file(trial_id)),
                "commercial_ready": record.commercial_ready,
                "success_rate": record.success_rate,
            },
        )
        return StageExecution(
            trial_id=trial_id,
            stage="BUSINESS_EVAL",
            next_stage=state_machine.next_stage("BUSINESS_EVAL", task=self.request.task),
            detail=str(marker_path),
        )

    def _stage_train_group1_component(
        self,
        *,
        trial_id: str,
        stage: str,
        component: str,
        record_path: Path,
        write_legacy_train: bool,
        train_mode_override: str | None = None,
        dataset_config_override: Path | None = None,
        model_override: str | None = None,
        imgsz_override: int | None = None,
    ) -> StageExecution:
        input_record = storage.read_trial_input_record(self.paths.input_file(trial_id))
        requested_train_mode = input_record.train_mode
        preflight_recovered_record = self._maybe_preflight_group1_embedder_resume_review(
            trial_id=trial_id,
            stage=stage,
            component=component,
            record_path=record_path,
            input_record=input_record,
            dataset_config_override=dataset_config_override,
            model_override=model_override,
        )
        if preflight_recovered_record is not None:
            storage.write_train_record(record_path, preflight_recovered_record)
            if write_legacy_train:
                storage.write_train_record(self.paths.train_file(trial_id), preflight_recovered_record)
            self._write_console(
                "stage_train_component "
                f"trial={trial_id} "
                f"stage={stage} "
                f"component={component} "
                "effective_train_mode=skip "
                "reason=preflight_review_advanced_existing_component "
                f"checkpoint={_checkpoint_text(_preferred_existing_checkpoint(_optional_path(preflight_recovered_record.best_weights), _optional_path(preflight_recovered_record.last_weights)))}"
            )
            return StageExecution(
                trial_id=trial_id,
                stage=stage,
                next_stage=state_machine.next_stage(stage, task=self.request.task),
                detail=f"recovered_existing_group1_component:{component}",
            )
        recovered_record = self._recover_existing_group1_component_record(
            trial_id=trial_id,
            stage=stage,
            component=component,
            record_path=record_path,
            input_record=input_record,
            dataset_config_override=dataset_config_override,
            model_override=model_override,
        )
        if recovered_record is not None:
            storage.write_train_record(record_path, recovered_record)
            if write_legacy_train:
                storage.write_train_record(self.paths.train_file(trial_id), recovered_record)
            self._write_console(
                "stage_train_component "
                f"trial={trial_id} "
                f"stage={stage} "
                f"component={component} "
                "effective_train_mode=skip "
                "reason=recovered_existing_component "
                f"checkpoint={_checkpoint_text(_preferred_existing_checkpoint(_optional_path(recovered_record.best_weights), _optional_path(recovered_record.last_weights)))}"
            )
            return StageExecution(
                trial_id=trial_id,
                stage=stage,
                next_stage=state_machine.next_stage(stage, task=self.request.task),
                detail=f"recovered_existing_group1_component:{component}",
            )

        effective_train_mode = train_mode_override or requested_train_mode
        train_mode_reason = (
            f"stage_override_{effective_train_mode}"
            if train_mode_override is not None
            else f"requested_{effective_train_mode}"
        )
        checkpoint_for_log: Path | None = _optional_path(model_override)
        if stage == "TRAIN_SCENE":
            effective_train_mode, train_mode_reason, checkpoint_for_log = self._resolve_group1_scene_train_mode(
                input_record=input_record,
                requested_train_mode=effective_train_mode,
            )
        elif stage == "TRAIN_EMBEDDER_BASE":
            effective_train_mode, train_mode_reason, checkpoint_for_log = self._resolve_group1_embedder_base_train_mode(
                input_record=input_record,
                requested_train_mode=effective_train_mode,
            )
        elif effective_train_mode == "resume":
            checkpoint_for_log = resolve_group1_component_last_weights(
                self.request.train_root,
                input_record.train_name,
                component,
            )
        elif effective_train_mode == "from_run" and input_record.base_run is not None:
            checkpoint_for_log = resolve_group1_component_best_weights(
                self.request.train_root,
                input_record.base_run,
                component,
            )

        dataset_config_for_log = dataset_config_override or default_dataset_config(
            self.request.train_root,
            self.request.task,
            input_record.dataset_version,
        )
        component_params = self._group1_component_params(input_record, component=component)
        imgsz = imgsz_override or _int_value(component_params, "imgsz", default=_int_value(input_record.params, "imgsz", default=self.request.effective_imgsz))
        device = _string_value(component_params, "device", default=_string_value(input_record.params, "device", default=self.request.device)) or self.request.device
        self._write_console(
            "stage_train_component "
            f"trial={trial_id} "
            f"stage={stage} "
            f"component={component} "
            f"requested_train_mode={requested_train_mode} "
            f"effective_train_mode={effective_train_mode} "
            f"reason={train_mode_reason} "
            f"dataset_config={dataset_config_for_log} "
            f"imgsz={imgsz} "
            f"device={device} "
            f"checkpoint={_checkpoint_text(checkpoint_for_log)}"
        )

        review_kwargs: dict[str, object] = {}
        if component == EMBEDDER_COMPONENT and self.request.judge_provider == "opencode":
            review_kwargs = {
                "review_provider": self.request.judge_provider,
                "review_model": self.request.judge_model,
                "review_project_root": self.request.train_root,
                "review_study_name": self.request.study_name,
                "review_task": self.request.task,
                "review_trial_id": trial_id,
                "review_stage": stage,
                "review_attach_url": self.request.opencode_attach_url,
                "review_binary": self.request.opencode_binary,
                "review_timeout_seconds": self.request.opencode_timeout_seconds,
                "review_min_epochs": embedder_review_protocol.DEFAULT_EMBEDDER_REVIEW_MIN_EPOCHS,
                "review_window": embedder_review_protocol.DEFAULT_EMBEDDER_REVIEW_WINDOW,
                "review_rebuild_count": _int_value(
                    input_record.params,
                    GROUP1_EMBEDDER_HARDSET_REBUILD_COUNT_PARAM,
                    default=0,
                ),
            }

        result = self.dependencies.train_runner(
            runners.train.TrainRunnerRequest(
                task=self.request.task,
                train_root=self.request.train_root,
                dataset_version=input_record.dataset_version,
                train_name=input_record.train_name,
                train_mode=effective_train_mode,
                base_run=input_record.base_run,
                model=model_override or _string_value(component_params, "model", default=_string_value(input_record.params, "model")),
                epochs=_int_value(component_params, "epochs", default=_int_value(input_record.params, "epochs")),
                batch=_int_value(component_params, "batch", default=_int_value(input_record.params, "batch")),
                imgsz=imgsz,
                device=device,
                component=component,
                dataset_config_override=dataset_config_override,
                interim_trial_dir=(
                    self.paths.trial_dir(trial_id)
                    if self.request.task == "group1" and component == EMBEDDER_COMPONENT
                    else None
                ),
                interim_primary_metric=(
                    policies.policy_for_task(self.request.task).primary_metric
                    if self.request.task == "group1" and component == EMBEDDER_COMPONENT
                    else None
                ),
                **review_kwargs,
            )
        )
        storage.write_train_record(record_path, result.record)
        if write_legacy_train:
            storage.write_train_record(self.paths.train_file(trial_id), result.record)
        return StageExecution(
            trial_id=trial_id,
            stage=stage,
            next_stage=state_machine.next_stage(stage, task=self.request.task),
            detail=result.command,
        )

    def _recover_existing_group1_component_record(
        self,
        *,
        trial_id: str,
        stage: str,
        component: str,
        record_path: Path,
        input_record: contracts.TrialInputRecord,
        dataset_config_override: Path | None,
        model_override: str | None,
    ) -> contracts.TrainRecord | None:
        if record_path.exists() or stage == "TRAIN_EMBEDDER_HARD":
            return None
        source_train_name = input_record.train_name
        best_path = resolve_group1_component_best_weights(self.request.train_root, source_train_name, component)
        last_path = resolve_group1_component_last_weights(self.request.train_root, source_train_name, component)
        source_reason = "current_run"
        if not self._group1_component_can_recover_from_run(source_train_name, component=component):
            should_reuse_base_run = (
                self._group1_component_action(input_record, component=component) == GROUP1_COMPONENT_PLAN_REUSE
                and input_record.base_run is not None
            )
            if not should_reuse_base_run:
                return None
            source_train_name = input_record.base_run
            best_path = resolve_group1_component_best_weights(self.request.train_root, source_train_name, component)
            last_path = resolve_group1_component_last_weights(self.request.train_root, source_train_name, component)
            if not self._group1_component_can_recover_from_run(source_train_name, component=component):
                return None
            source_reason = "base_run"

        dataset_config_path = dataset_config_override or default_dataset_config(
            self.request.train_root,
            self.request.task,
            input_record.dataset_version,
        )
        params: dict[str, contracts.JsonValue] = {
            "dataset_version": input_record.dataset_version,
            "dataset_config": str(dataset_config_path),
            "train_mode": input_record.train_mode,
            "model": model_override or _string_value(input_record.params, "model"),
            "epochs": _int_value(input_record.params, "epochs"),
            "batch": _int_value(input_record.params, "batch"),
            "imgsz": _int_value(input_record.params, "imgsz", default=self.request.effective_imgsz),
            "device": _string_value(input_record.params, "device", default=self.request.device) or self.request.device,
            "component": component,
            "recovered_existing_weights": True,
            "recovery_source": source_reason,
        }
        resumed_from = source_train_name if source_train_name != input_record.train_name else (
            input_record.base_run
            if input_record.train_mode == "from_run"
            else input_record.train_name
            if input_record.train_mode == "resume"
            else None
        )
        record = contracts.TrainRecord(
            task=self.request.task,
            train_name=input_record.train_name,
            run_dir=str(default_run_dir(self.request.train_root, self.request.task, input_record.train_name)),
            params=params,
            best_weights=str(best_path),
            last_weights=str(last_path),
            resumed_from=resumed_from,
        )
        self._write_recovered_group1_component_summary(
            trial_id=trial_id,
            component=component,
            record=record,
            dataset_config_path=dataset_config_path,
            model_path=preferred_checkpoint_path(best_path, last_path),
            imgsz=int(params["imgsz"]),
            device=str(params["device"]),
            source_train_name=source_train_name,
        )
        return record

    def _resolve_group1_embedder_base_train_mode(
        self,
        *,
        input_record: contracts.TrialInputRecord,
        requested_train_mode: str,
    ) -> tuple[str, str, Path | None]:
        last_path = resolve_group1_component_last_weights(
            self.request.train_root,
            input_record.train_name,
            EMBEDDER_COMPONENT,
        )
        if last_path.exists() and not self._is_group1_embedder_component_complete(input_record.train_name):
            return "resume", "resume_incomplete_current_run", last_path
        if requested_train_mode == "resume":
            return requested_train_mode, "requested_resume", last_path if last_path.exists() else None
        if requested_train_mode == "from_run" and input_record.base_run is not None:
            return (
                requested_train_mode,
                "requested_from_run",
                resolve_group1_component_best_weights(
                    self.request.train_root,
                    input_record.base_run,
                    EMBEDDER_COMPONENT,
                ),
            )
        return requested_train_mode, f"requested_{requested_train_mode}", None

    def _maybe_preflight_group1_embedder_resume_review(
        self,
        *,
        trial_id: str,
        stage: str,
        component: str,
        record_path: Path,
        input_record: contracts.TrialInputRecord,
        dataset_config_override: Path | None,
        model_override: str | None,
    ) -> contracts.TrainRecord | None:
        if (
            stage != "TRAIN_EMBEDDER_BASE"
            or component != EMBEDDER_COMPONENT
            or record_path.exists()
            or self.request.judge_provider != "opencode"
        ):
            return None
        effective_train_mode, train_mode_reason, checkpoint_path = self._resolve_group1_embedder_base_train_mode(
            input_record=input_record,
            requested_train_mode=input_record.train_mode,
        )
        if effective_train_mode != "resume" or train_mode_reason != "resume_incomplete_current_run" or checkpoint_path is None:
            return None
        summary_path = (
            default_run_dir(self.request.train_root, self.request.task, input_record.train_name)
            / EMBEDDER_COMPONENT
            / "summary.json"
        )
        if not summary_path.exists():
            return None
        try:
            payload = self._read_json_payload(summary_path)
        except (OSError, RuntimeError, json.JSONDecodeError):
            return None
        if payload.get("component") != EMBEDDER_COMPONENT or payload.get("finalized") is True:
            return None
        history = payload.get("history")
        if not isinstance(history, list) or not history:
            return None
        latest_epoch = _embedder_summary_epoch(history[-1])
        if latest_epoch is None:
            return None
        review_settings = payload.get("review_settings")
        review_min_epochs = (
            _int_value(review_settings, "min_epochs", default=embedder_review_protocol.DEFAULT_EMBEDDER_REVIEW_MIN_EPOCHS)
            if isinstance(review_settings, dict)
            else embedder_review_protocol.DEFAULT_EMBEDDER_REVIEW_MIN_EPOCHS
        )
        review_window = (
            _int_value(review_settings, "window", default=embedder_review_protocol.DEFAULT_EMBEDDER_REVIEW_WINDOW)
            if isinstance(review_settings, dict)
            else embedder_review_protocol.DEFAULT_EMBEDDER_REVIEW_WINDOW
        )
        if not embedder_review_protocol.should_run_embedder_review(
            epoch=latest_epoch,
            min_epochs=review_min_epochs,
            window=review_window,
        ):
            return None
        review_context = self._build_group1_embedder_preflight_review_context(
            trial_id=trial_id,
            input_record=input_record,
            payload=payload,
            latest_epoch=latest_epoch,
            review_window=review_window,
            review_history=[],
        )
        review_history = payload.get("review_history")
        normalized_review_history = review_history if isinstance(review_history, list) else []
        review_record_payload = _embedder_review_for_epoch(normalized_review_history, latest_epoch)
        if review_record_payload is None:
            review_record = self._run_group1_embedder_preflight_review(
                trial_id=trial_id,
                summary_path=summary_path,
                context=self._build_group1_embedder_preflight_review_context(
                    trial_id=trial_id,
                    input_record=input_record,
                    payload=payload,
                    latest_epoch=latest_epoch,
                    review_window=review_window,
                    review_history=normalized_review_history,
                ),
            )
            review_record_payload = review_record.to_dict()
            normalized_review_history.append(review_record_payload)
            payload["review"] = review_record_payload
            payload["review_history"] = normalized_review_history
            storage.write_json_payload(summary_path, payload)
            self._write_console(
                "embedder_preflight_review "
                f"trial={trial_id} "
                f"stage={stage} "
                f"epoch={latest_epoch} "
                f"decision={review_record.decision} "
                f"reason={review_record.reason} "
                "source=new_review"
            )
        else:
            existing_record = _embedder_review_record_from_payload(
                review_record_payload,
                default_stage=stage,
                default_epoch=latest_epoch,
            )
            normalized_record = embedder_review_protocol.apply_review_guardrails(
                context=self._build_group1_embedder_preflight_review_context(
                    trial_id=trial_id,
                    input_record=input_record,
                    payload=payload,
                    latest_epoch=latest_epoch,
                    review_window=review_window,
                    review_history=normalized_review_history,
                ),
                record=existing_record,
            )
            review_record_payload = normalized_record.to_dict()
            payload["review"] = review_record_payload
            payload["review_history"] = _replace_embedder_review_for_epoch(
                normalized_review_history,
                latest_epoch,
                review_record_payload,
            )
            normalized_review_history = payload["review_history"]
            storage.write_json_payload(summary_path, payload)
            self._write_console(
                "embedder_preflight_review "
                f"trial={trial_id} "
                f"stage={stage} "
                f"epoch={latest_epoch} "
                f"decision={review_record_payload.get('decision')} "
                f"reason={review_record_payload.get('reason')} "
                "source=existing_review"
            )
        if review_record_payload.get("decision") != embedder_review_protocol.EMBEDDER_REVIEW_DECISION_STOP_AND_ADVANCE:
            return None
        payload["finalized"] = True
        payload["training_stop"] = {
            "reason": "preflight_review:STOP_AND_ADVANCE",
            "stopped_epoch": latest_epoch,
        }
        payload["review"] = review_record_payload
        payload["review_history"] = normalized_review_history
        storage.write_json_payload(summary_path, payload)
        return self._recover_existing_group1_component_record(
            trial_id=trial_id,
            stage=stage,
            component=component,
            record_path=record_path,
            input_record=input_record,
            dataset_config_override=dataset_config_override,
            model_override=model_override,
        )

    def _run_group1_embedder_preflight_review(
        self,
        *,
        trial_id: str,
        summary_path: Path,
        context: embedder_review_protocol.EmbedderReviewContext,
    ) -> embedder_review_protocol.EmbedderReviewRecord:
        runtime = self._opencode_runtime()
        reviewer = embedder_review_protocol.build_opencode_embedder_reviewer(
            runtime=runtime,
            run_dir=summary_path.parent.parent,
        )
        return reviewer(context)

    def _build_group1_embedder_preflight_review_context(
        self,
        *,
        trial_id: str,
        input_record: contracts.TrialInputRecord,
        payload: dict[str, object],
        latest_epoch: int,
        review_window: int,
        review_history: list[dict[str, object]],
    ) -> embedder_review_protocol.EmbedderReviewContext:
        metrics = payload.get("metrics")
        if not isinstance(metrics, dict):
            metrics = {}
        history = payload.get("history")
        if not isinstance(history, list):
            history = []
        rebuild_count = _int_value(
            input_record.params,
            GROUP1_EMBEDDER_HARDSET_REBUILD_COUNT_PARAM,
            default=0,
        )
        best_epoch, best_score = _best_embedder_epoch_from_history(history)
        return embedder_review_protocol.EmbedderReviewContext(
            study_name=self.request.study_name,
            task=self.request.task,
            trial_id=trial_id,
            train_name=input_record.train_name,
            stage="TRAIN_EMBEDDER_BASE",
            epoch=latest_epoch,
            review_window=review_window,
            rebuild_count=rebuild_count,
            dataset_config=str(
                payload.get("dataset_config")
                or default_dataset_config(
                    self.request.train_root,
                    self.request.task,
                    input_record.dataset_version,
                )
            ),
            image_size=_summary_int(payload.get("image_size"), DEFAULT_ICON_EMBEDDER_IMGSZ),
            batch_size=_int_value(input_record.params, "batch", default=32) or 32,
            best_epoch=best_epoch,
            best_embedding_recall_at_1=best_score,
            current_metrics=_json_object(metrics),
            recent_history=_recent_embedder_history(history, review_window),
            review_history=[_json_object(item) for item in review_history if isinstance(item, dict)],
            decision_mode=embedder_review_protocol.EMBEDDER_REVIEW_DECISION_MODE_LLM_FIRST,
        )

    def _resolve_group1_scene_train_mode(
        self,
        *,
        input_record: contracts.TrialInputRecord,
        requested_train_mode: str,
    ) -> tuple[str, str, Path | None]:
        last_path = resolve_group1_component_last_weights(
            self.request.train_root,
            input_record.train_name,
            PROPOSAL_COMPONENT,
        )
        if last_path.exists() and not self._is_group1_detector_component_complete(
            input_record.train_name,
            component=PROPOSAL_COMPONENT,
        ):
            if is_resumable_yolo_checkpoint(last_path):
                return "resume", "resume_incomplete_current_run", last_path
            if requested_train_mode == "from_run" and input_record.base_run is not None:
                return (
                    requested_train_mode,
                    "requested_from_run_non_resumable_current_run",
                    resolve_group1_component_best_weights(
                        self.request.train_root,
                        input_record.base_run,
                        PROPOSAL_COMPONENT,
                    ),
                )
        if requested_train_mode == "resume":
            return requested_train_mode, "requested_resume", last_path if last_path.exists() else None
        if requested_train_mode == "from_run" and input_record.base_run is not None:
            return (
                requested_train_mode,
                "requested_from_run",
                resolve_group1_component_best_weights(
                    self.request.train_root,
                    input_record.base_run,
                    PROPOSAL_COMPONENT,
                ),
            )
        return requested_train_mode, f"requested_{requested_train_mode}", None

    def _is_group1_embedder_component_complete(self, train_name: str) -> bool:
        summary_path = default_run_dir(self.request.train_root, self.request.task, train_name) / EMBEDDER_COMPONENT / "summary.json"
        if not summary_path.exists():
            return False
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        if not isinstance(payload, dict):
            return False
        if payload.get("finalized") is False:
            return False
        return (
            payload.get("component") == EMBEDDER_COMPONENT
            and isinstance(payload.get("metrics"), dict)
            and isinstance(payload.get("history"), list)
        )

    def _is_group1_detector_component_complete(self, train_name: str, *, component: str) -> bool:
        summary_path = default_run_dir(self.request.train_root, self.request.task, train_name) / "summary.json"
        if not summary_path.exists():
            return False
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        if not isinstance(payload, dict):
            return False
        components = payload.get("components")
        if not isinstance(components, dict):
            return False
        component_payload = components.get(component)
        if not isinstance(component_payload, dict):
            return False
        gate = component_payload.get("gate")
        metrics = component_payload.get("metrics")
        return isinstance(gate, dict) and isinstance(metrics, dict)

    def _group1_component_can_recover_from_run(self, train_name: str, *, component: str) -> bool:
        best_path = resolve_group1_component_best_weights(self.request.train_root, train_name, component)
        last_path = resolve_group1_component_last_weights(self.request.train_root, train_name, component)
        if not best_path.exists() and not last_path.exists():
            return False
        if component == QUERY_COMPONENT:
            return True
        if component == PROPOSAL_COMPONENT:
            return best_path.exists() or self._is_group1_detector_component_complete(train_name, component=component)
        if component == EMBEDDER_COMPONENT:
            return self._is_group1_embedder_component_complete(train_name)
        return False

    def _group1_component_action(
        self,
        input_record: contracts.TrialInputRecord,
        *,
        component: str,
    ) -> str:
        plan = input_record.params.get(GROUP1_COMPONENT_PLAN_PARAM)
        if not isinstance(plan, dict):
            return GROUP1_COMPONENT_PLAN_TRAIN
        raw_action = plan.get(component)
        if raw_action in {GROUP1_COMPONENT_PLAN_TRAIN, GROUP1_COMPONENT_PLAN_REUSE}:
            return str(raw_action)
        return GROUP1_COMPONENT_PLAN_TRAIN

    def _group1_component_params(
        self,
        input_record: contracts.TrialInputRecord,
        *,
        component: str,
    ) -> dict[str, contracts.JsonValue]:
        payload = input_record.params.get(GROUP1_COMPONENT_PARAMS_PARAM)
        if not isinstance(payload, dict):
            return {}
        component_payload = payload.get(component)
        if not isinstance(component_payload, dict):
            return {}
        return component_payload

    def _increment_embedder_hardset_rebuild_count(self, trial_id: str) -> int:
        input_path = self.paths.input_file(trial_id)
        input_record = storage.read_trial_input_record(input_path)
        current_count = _int_value(
            input_record.params,
            GROUP1_EMBEDDER_HARDSET_REBUILD_COUNT_PARAM,
            default=0,
        )
        next_count = current_count + 1
        updated_params = dict(input_record.params)
        updated_params[GROUP1_EMBEDDER_HARDSET_REBUILD_COUNT_PARAM] = next_count
        storage.write_trial_input_record(
            input_path,
            contracts.TrialInputRecord(
                trial_id=input_record.trial_id,
                task=input_record.task,
                dataset_version=input_record.dataset_version,
                train_name=input_record.train_name,
                train_mode=input_record.train_mode,
                base_run=input_record.base_run,
                params=updated_params,
                dataset_preset=input_record.dataset_preset,
                dataset_override=input_record.dataset_override,
            ),
        )
        return next_count

    def _group1_component_plan_for_next_trial(
        self,
        *,
        trial_id: str,
        regenerate_all: bool,
    ) -> dict[str, str]:
        if regenerate_all:
            return {
                QUERY_COMPONENT: GROUP1_COMPONENT_PLAN_TRAIN,
                PROPOSAL_COMPONENT: GROUP1_COMPONENT_PLAN_TRAIN,
                EMBEDDER_COMPONENT: GROUP1_COMPONENT_PLAN_TRAIN,
            }
        return {
            QUERY_COMPONENT: self._group1_gate_status_for_retry(self.paths.query_gate_file(trial_id)),
            PROPOSAL_COMPONENT: self._group1_gate_status_for_retry(self.paths.scene_gate_file(trial_id)),
            EMBEDDER_COMPONENT: self._group1_gate_status_for_retry(self.paths.embedder_gate_file(trial_id)),
        }

    def _group1_gate_status_for_retry(self, path: Path) -> str:
        try:
            payload = self._read_json_payload(path)
        except (OSError, RuntimeError, json.JSONDecodeError):
            return GROUP1_COMPONENT_PLAN_TRAIN
        status = payload.get("status")
        if isinstance(status, str) and status.strip() == "passed":
            return GROUP1_COMPONENT_PLAN_REUSE
        return GROUP1_COMPONENT_PLAN_TRAIN

    def _load_group1_embedder_summary(
        self,
        *,
        train_name: str,
        default_weights: dict[str, object],
    ) -> dict[str, object]:
        summary_path = default_run_dir(self.request.train_root, self.request.task, train_name) / EMBEDDER_COMPONENT / "summary.json"
        if not summary_path.exists():
            return {
                "component": EMBEDDER_COMPONENT,
                "weights": default_weights,
                "metrics": {},
                "history": [],
            }
        try:
            payload = self._read_json_payload(summary_path)
        except (OSError, RuntimeError, json.JSONDecodeError):
            return {
                "component": EMBEDDER_COMPONENT,
                "weights": default_weights,
                "metrics": {},
                "history": [],
            }
        if "weights" not in payload:
            payload["weights"] = default_weights
        return payload

    def _load_group1_embedder_metrics(self, train_record: contracts.TrainRecord) -> dict[str, object]:
        summary = self._load_group1_embedder_summary(
            train_name=train_record.resumed_from or train_record.train_name,
            default_weights={
                "best": train_record.best_weights,
                "last": train_record.last_weights,
            },
        )
        metrics = summary.get("metrics")
        return metrics if isinstance(metrics, dict) else {}

    def _build_group1_embedder_gate(self, metrics: dict[str, object]) -> dict[str, object]:
        scene_recall_at_1_raw = metrics.get("embedding_scene_recall_at_1")
        scene_recall_at_3_raw = metrics.get("embedding_scene_recall_at_3")
        has_scene_metrics = all(
            isinstance(value, (int, float))
            for value in (scene_recall_at_1_raw, scene_recall_at_3_raw)
        )
        identity_recall_at_1_raw = metrics.get("embedding_identity_recall_at_1")
        has_identity_metric = isinstance(identity_recall_at_1_raw, (int, float)) and not isinstance(identity_recall_at_1_raw, bool)
        if has_scene_metrics:
            recall_at_1 = _float_like(scene_recall_at_1_raw, 0.0)
            recall_at_3 = _float_like(scene_recall_at_3_raw, 0.0)
            recall_at_1_field = "embedding_scene_recall_at_1"
            recall_at_3_field = "embedding_scene_recall_at_3"
            recall_at_1_threshold = GROUP1_EMBEDDER_GATE_SCENE_RECALL_AT_1_MIN
            recall_at_3_threshold = GROUP1_EMBEDDER_GATE_SCENE_RECALL_AT_3_MIN
        else:
            recall_at_1 = _float_like(metrics.get("embedding_recall_at_1"), 0.0)
            recall_at_3 = _float_like(metrics.get("embedding_recall_at_3"), 0.0)
            recall_at_1_field = "embedding_recall_at_1"
            recall_at_3_field = "embedding_recall_at_3"
            recall_at_1_threshold = GROUP1_EMBEDDER_GATE_RECALL_AT_1_MIN
            recall_at_3_threshold = GROUP1_EMBEDDER_GATE_RECALL_AT_3_MIN
        failed_checks: list[str] = []
        if recall_at_1 < recall_at_1_threshold:
            failed_checks.append(recall_at_1_field)
        if recall_at_3 < recall_at_3_threshold:
            failed_checks.append(recall_at_3_field)
        identity_recall_at_1 = _float_like(identity_recall_at_1_raw, 0.0) if has_identity_metric else None
        if identity_recall_at_1 is not None and identity_recall_at_1 < GROUP1_EMBEDDER_GATE_IDENTITY_RECALL_AT_1_MIN:
            failed_checks.append("embedding_identity_recall_at_1")
        return {
            "status": "passed" if not failed_checks else "failed",
            "failed_checks": failed_checks,
            "thresholds": {
                f"{recall_at_1_field}_min": recall_at_1_threshold,
                f"{recall_at_3_field}_min": recall_at_3_threshold,
                "embedding_identity_recall_at_1_min": (
                    GROUP1_EMBEDDER_GATE_IDENTITY_RECALL_AT_1_MIN if has_identity_metric else None
                ),
            },
            "observed": {
                recall_at_1_field: recall_at_1,
                recall_at_3_field: recall_at_3,
                "embedding_identity_recall_at_1": identity_recall_at_1,
                "embedding_recall_at_1": _float_like(metrics.get("embedding_recall_at_1"), 0.0),
                "embedding_recall_at_3": _float_like(metrics.get("embedding_recall_at_3"), 0.0),
                "embedding_scene_recall_at_1": _float_like(scene_recall_at_1_raw, 0.0) if has_scene_metrics else None,
                "embedding_scene_recall_at_3": _float_like(scene_recall_at_3_raw, 0.0) if has_scene_metrics else None,
            },
            "diagnostics": {
                "priority": "scene_identity_first",
                "global_exact_is_diagnostic_only": True,
            },
        }

    def _write_recovered_group1_component_summary(
        self,
        *,
        trial_id: str,
        component: str,
        record: contracts.TrainRecord,
        dataset_config_path: Path,
        model_path: Path,
        imgsz: int,
        device: str,
        source_train_name: str,
    ) -> None:
        run_dir = Path(record.run_dir)
        summary_path = run_dir / "summary.json"
        if summary_path.exists():
            try:
                payload = self._read_json_payload(summary_path)
            except (OSError, json.JSONDecodeError, RuntimeError):
                payload = {}
        else:
            payload = {}
        components = payload.get("components")
        if not isinstance(components, dict):
            components = {}
        payload.update(
            {
                "task": "group1",
                "dataset_config": str(dataset_config_path),
                "run_dir": str(run_dir),
                "requested_component": component,
                "components": components,
            }
        )
        component_summary: dict[str, object] = {
            "role": _group1_component_role(component),
            "weights": {
                "best": record.best_weights,
                "last": record.last_weights,
            },
            "recovered_existing_weights": True,
        }
        if component in {QUERY_COMPONENT, PROPOSAL_COMPONENT}:
            evaluator = (
                self.dependencies.query_detector_evaluator
                if component == QUERY_COMPONENT
                else self.dependencies.proposal_detector_evaluator
            )
            metrics, gate, failcases = evaluator(
                dataset_config_path=dataset_config_path,
                model_path=model_path,
                imgsz=imgsz,
                device=device,
            )
            failcases_path = run_dir / component / "failcases.jsonl"
            write_jsonl(failcases_path, failcases)
            component_summary.update(
                {
                    "metrics": metrics,
                    "gate": gate,
                    "failcases": str(failcases_path),
                }
            )
        elif component == EMBEDDER_COMPONENT:
            embedder_summary = self._load_group1_embedder_summary(
                train_name=source_train_name,
                default_weights={
                    "best": record.best_weights,
                    "last": record.last_weights,
                },
            )
            component_summary.update(
                {
                    "metrics": embedder_summary.get("metrics", {}),
                    "summary": str(
                        default_run_dir(self.request.train_root, self.request.task, source_train_name)
                        / EMBEDDER_COMPONENT
                        / "summary.json"
                    ),
                    "review": embedder_summary.get("review"),
                }
            )
        components[component] = component_summary
        storage.write_json_payload(summary_path, payload)

    def _patch_group1_component_summary(
        self,
        *,
        train_record: contracts.TrainRecord,
        component: str,
        component_summary: dict[str, object],
        dataset_config_path: Path,
    ) -> None:
        run_dir = Path(train_record.run_dir)
        summary_path = run_dir / "summary.json"
        if summary_path.exists():
            try:
                payload = self._read_json_payload(summary_path)
            except (OSError, json.JSONDecodeError, RuntimeError):
                payload = {}
        else:
            payload = {}
        components = payload.get("components")
        if not isinstance(components, dict):
            components = {}
        components[component] = component_summary
        payload.update(
            {
                "task": "group1",
                "dataset_config": str(dataset_config_path),
                "run_dir": str(run_dir),
                "components": components,
            }
        )
        storage.write_json_payload(summary_path, payload)

    def _resolve_group1_component_runtime_context(
        self,
        *,
        trial_id: str,
        train_record: contracts.TrainRecord,
    ) -> tuple[Path, int, str]:
        input_record = storage.read_trial_input_record(self.paths.input_file(trial_id))
        fallback_dataset_config = default_dataset_config(
            self.request.train_root,
            self.request.task,
            input_record.dataset_version,
        )
        dataset_config_path = Path(
            _string_value(train_record.params, "dataset_config", default=str(fallback_dataset_config))
            or str(fallback_dataset_config)
        )
        fallback_imgsz = _int_value(input_record.params, "imgsz", default=self.request.effective_imgsz)
        fallback_device = _string_value(input_record.params, "device", default=self.request.device) or self.request.device
        imgsz = _int_value(train_record.params, "imgsz", default=fallback_imgsz) or fallback_imgsz or self.request.effective_imgsz
        device = _string_value(train_record.params, "device", default=fallback_device) or fallback_device
        return dataset_config_path, imgsz, device

    def _build_group1_gate_payload(
        self,
        *,
        trial_id: str,
        component: str,
        train_record: contracts.TrainRecord,
        dataset_config_path: Path,
        imgsz: int,
        device: str,
        best_path: Path | None,
        last_path: Path | None,
        component_summary: dict[str, object],
        gate: object,
        gate_status: str,
    ) -> dict[str, object]:
        return {
            "trial_id": trial_id,
            "component": component,
            "gate_version": GROUP1_GATE_ARTIFACT_VERSION,
            "status": gate_status,
            "dataset_config": str(dataset_config_path),
            "weights": {
                "best": train_record.best_weights if best_path is None else str(best_path),
                "last": train_record.last_weights if last_path is None else str(last_path),
            },
            "imgsz": imgsz,
            "device": device,
            "metrics": component_summary.get("metrics", {}),
            "gate": gate if isinstance(gate, dict) else {},
            "error_file": component_summary.get("failcases"),
            "review": component_summary.get("review"),
            "failure_audit": component_summary.get("failure_audit"),
            "checks": {
                "best_exists": bool(best_path and best_path.exists()),
                "last_exists": bool(last_path and last_path.exists()),
            },
            "summary_path": str(Path(train_record.run_dir) / "summary.json"),
        }

    def _stage_test(self, trial_id: str) -> StageExecution:
        input_record = storage.read_trial_input_record(self.paths.input_file(trial_id))
        model_path = self._resolve_test_model_path(trial_id)
        matcher_settings = self._load_group1_matcher_settings(trial_id)
        result = self.dependencies.test_runner(
            runners.test.TestRunnerRequest(
                task=self.request.task,
                train_root=self.request.train_root,
                dataset_version=input_record.dataset_version,
                train_name=input_record.train_name,
                model_path=model_path,
                imgsz=_int_value(input_record.params, "imgsz", default=self.request.effective_imgsz),
                device=_string_value(input_record.params, "device", default=self.request.device) or self.request.device,
                similarity_threshold=matcher_settings["similarity_threshold"],
                ambiguity_margin=matcher_settings["ambiguity_margin"],
            )
        )
        storage.write_test_record(self.paths.test_file(trial_id), result.record)
        next_stage = "EVALUATE" if self.request.task == "group1" else state_machine.next_stage("TEST", task=self.request.task)
        return StageExecution(
            trial_id=trial_id,
            stage="TEST",
            next_stage=next_stage,
            detail=result.predict_command,
        )

    def _stage_evaluate(self, trial_id: str) -> StageExecution:
        evaluate_path = self.paths.evaluate_file(trial_id)
        trial_input = storage.read_trial_input_record(self.paths.input_file(trial_id))
        evaluate_request = self._resolve_evaluation_request(trial_id=trial_id, train_name=trial_input.train_name)
        if evaluate_request is not None:
            result = self.dependencies.evaluate_runner(evaluate_request)
            storage.write_evaluate_record(evaluate_path, result.record)
            detail = result.command
        else:
            storage.write_evaluate_record(
                evaluate_path,
                contracts.EvaluateRecord(
                    available=False,
                    task=self.request.task,
                    metrics={},
                    failure_count=0,
                    report_dir=str(default_report_dir(self.request.train_root, self.request.task) / f"eval_{trial_input.train_name}"),
                ),
            )
            detail = "evaluation_skipped"
        next_stage = "SUMMARIZE" if self.request.task == "group1" else state_machine.next_stage("EVALUATE", task=self.request.task)
        return StageExecution(
            trial_id=trial_id,
            stage="EVALUATE",
            next_stage=next_stage,
            detail=detail,
        )

    def _stage_summarize(self, trial_id: str) -> StageExecution:
        trial_input = storage.read_trial_input_record(self.paths.input_file(trial_id))
        test_record = storage.read_test_record(self.paths.test_file(trial_id))
        evaluate_record = storage.read_evaluate_record(self.paths.evaluate_file(trial_id))
        policy = policies.policy_for_task(self.request.task)
        fallback_record = self.dependencies.summary_builder(
            summary.ResultSummaryRequest(
                study_name=self.request.study_name,
                paths=self.paths,
                trial_id=trial_id,
                dataset_version=trial_input.dataset_version,
                train_name=trial_input.train_name,
                primary_metric=policy.primary_metric,
                test_record=test_record,
                evaluate_record=evaluate_record,
                recent_window=policy.plateau_window,
                min_delta=policy.min_delta,
            )
        )
        if self.request.judge_provider == "opencode":
            record = self._summarize_trial_with_runtime(
                trial_id=trial_id,
                primary_metric=policy.primary_metric,
                recent_window=policy.plateau_window,
                fallback_record=fallback_record,
            )
        else:
            record = fallback_record
        storage.write_result_summary_record(self.paths.result_summary_file(trial_id), record)
        trial_analysis_record = analysis.build_trial_analysis(
            analysis.TrialAnalysisRequest(
                paths=self.paths,
                trial_id=trial_id,
                trial_input=trial_input,
                summary_record=record,
            )
        )
        storage.write_trial_analysis_record(self.paths.trial_analysis_file(trial_id), trial_analysis_record)
        self._write_trial_summary(record, None)
        return StageExecution(
            trial_id=trial_id,
            stage="SUMMARIZE",
            next_stage=state_machine.next_stage("SUMMARIZE", task=self.request.task),
            detail=str(self.paths.result_summary_file(trial_id)),
        )

    def _stage_judge(self, trial_id: str) -> StageExecution:
        summary_record = storage.read_result_summary_record(self.paths.result_summary_file(trial_id))
        decision = self._judge_trial(trial_id, summary_record)
        storage.write_decision_record(self.paths.decision_file(trial_id), decision)
        self._write_trial_summary(summary_record, decision)
        return StageExecution(
            trial_id=trial_id,
            stage="JUDGE",
            next_stage=state_machine.next_stage("JUDGE", task=self.request.task),
            detail=decision.decision,
        )

    def _stage_next_action(self, trial_id: str) -> StageExecution:
        summary_record = storage.read_result_summary_record(self.paths.result_summary_file(trial_id))
        decision = storage.read_decision_record(self.paths.decision_file(trial_id))
        study = self._load_or_create_study()

        business_record = self._load_or_run_business_eval_if_needed(
            trial_id=trial_id,
            summary_record=summary_record,
            decision=decision,
            study=study,
        )
        leaderboard = self._update_leaderboard(summary_record, decision, business_record)
        self._promote_current_trial_last_weights_if_selected(trial_id=trial_id, leaderboard=leaderboard)
        if business_record is not None and business_record.commercial_ready:
            updated = self._with_study_updates(
                study,
                status="completed",
                current_trial_id=trial_id,
                best_trial_id=leaderboard.best_entry.trial_id if leaderboard.best_entry is not None else study.best_trial_id,
                final_reason="commercial_gate_passed",
                final_detail=f"{business_record.success_rate:.4f}/{business_record.success_threshold:.4f}",
            )
            storage.write_study_record(self.paths.study_file, updated)
            self._write_business_eval_artifacts(trial_id=trial_id, record=business_record)
            self._write_study_summary(updated, leaderboard, decision, business_record)
            self._write_commercial_report(
                study=updated,
                leaderboard=leaderboard,
                summary_record=summary_record,
                raw_decision=decision,
                effective_decision=decision,
                business_eval_record=business_record,
            )
            return StageExecution(trial_id=trial_id, stage="NEXT_ACTION", next_stage="STOP", detail=decision.decision)

        effective_decision = self._effective_next_action_decision(
            study=study,
            summary_record=summary_record,
            decision=decision,
            business_record=business_record,
            leaderboard=leaderboard,
        )
        plan_record = self._dataset_plan_record(
            summary_record=summary_record,
            decision=effective_decision,
            leaderboard=leaderboard,
        )
        retune_plan_record = self._retune_plan_record(
            summary_record=summary_record,
            decision=effective_decision,
            leaderboard=leaderboard,
        )
        if plan_record is not None:
            storage.write_dataset_plan_record(self.paths.dataset_plan_file(trial_id), plan_record)
        if retune_plan_record is not None:
            storage.write_retune_plan_record(self.paths.retune_plan_file(trial_id), retune_plan_record)
        storage.append_decision_history(self.paths.decisions_file, effective_decision)

        if effective_decision.decision == "ABANDON_BRANCH":
            updated = self._with_study_updates(
                study,
                status="completed",
                current_trial_id=trial_id,
                best_trial_id=leaderboard.best_entry.trial_id if leaderboard.best_entry is not None else study.best_trial_id,
                final_reason="abandon_branch",
                final_detail=effective_decision.reason,
            )
            storage.write_study_record(self.paths.study_file, updated)
            self._write_study_summary(updated, leaderboard, effective_decision, business_record)
            if business_record is not None:
                self._write_business_eval_artifacts(trial_id=trial_id, record=business_record)
                self._write_commercial_report(
                    study=updated,
                    leaderboard=leaderboard,
                    summary_record=summary_record,
                    raw_decision=decision,
                    effective_decision=effective_decision,
                    business_eval_record=business_record,
                )
            return StageExecution(
                trial_id=trial_id,
                stage="NEXT_ACTION",
                next_stage="STOP",
                detail=effective_decision.decision,
            )

        if effective_decision.decision == "PROMOTE_BRANCH" and business_record is None:
            updated = self._with_study_updates(
                study,
                status="completed",
                current_trial_id=trial_id,
                best_trial_id=leaderboard.best_entry.trial_id if leaderboard.best_entry is not None else study.best_trial_id,
                final_reason="offline_promotion_ready",
                final_detail=effective_decision.reason,
            )
            storage.write_study_record(self.paths.study_file, updated)
            self._write_study_summary(updated, leaderboard, effective_decision, None)
            return StageExecution(
                trial_id=trial_id,
                stage="NEXT_ACTION",
                next_stage="STOP",
                detail=effective_decision.decision,
            )

        dataset_action = plan_record.dataset_action if plan_record is not None else _string_action(
            effective_decision.next_action,
            "dataset_action",
            "reuse",
        )
        stop_decision = self._evaluate_stop(
            study,
            leaderboard,
            pending_new_dataset=(dataset_action == "new_version"),
            ignore_adaptive_limits=self._business_eval_enabled(study),
        )
        if stop_decision.should_stop:
            updated = self._with_study_updates(
                study,
                status="stopped",
                current_trial_id=trial_id,
                best_trial_id=leaderboard.best_entry.trial_id if leaderboard.best_entry is not None else study.best_trial_id,
                final_reason=stop_decision.reason,
                final_detail=stop_decision.detail,
            )
            storage.write_study_record(self.paths.study_file, updated)
            if business_record is not None:
                self._write_business_eval_artifacts(trial_id=trial_id, record=business_record)
                self._write_commercial_report(
                    study=updated,
                    leaderboard=leaderboard,
                    summary_record=summary_record,
                    raw_decision=decision,
                    effective_decision=effective_decision,
                    business_eval_record=business_record,
                )
            self._write_study_summary(updated, leaderboard, effective_decision, business_record)
            return StageExecution(
                trial_id=trial_id,
                stage="NEXT_ACTION",
                next_stage="STOP",
                detail=stop_decision.reason,
            )

        next_trial = self._prepare_next_trial(summary_record, effective_decision, plan_record, retune_plan_record)
        storage.write_trial_input_record(self.paths.input_file(next_trial.trial_id), next_trial)
        storage.append_trial_history(self.paths.trial_history_file, next_trial)
        updated = self._with_study_updates(
            study,
            status="running",
            current_trial_id=next_trial.trial_id,
            best_trial_id=leaderboard.best_entry.trial_id if leaderboard.best_entry is not None else study.best_trial_id,
            final_reason=None,
            final_detail=None,
        )
        storage.write_study_record(self.paths.study_file, updated)
        if business_record is not None:
            self._write_business_eval_artifacts(trial_id=trial_id, record=business_record)
            self._write_commercial_report(
                study=updated,
                leaderboard=leaderboard,
                summary_record=summary_record,
                raw_decision=decision,
                effective_decision=effective_decision,
                business_eval_record=business_record,
            )
        self._write_study_summary(updated, leaderboard, effective_decision, business_record)
        return StageExecution(
            trial_id=trial_id,
            stage="NEXT_ACTION",
            next_stage="PLAN",
            detail=next_trial.trial_id,
        )

    def _load_or_create_study(self) -> contracts.StudyRecord:
        requested_business_eval = self._requested_business_eval_config()
        if self.paths.study_file.exists():
            record = storage.read_study_record(self.paths.study_file)
            changes: dict[str, object] = {}
            if record.started_at is None:
                changes["started_at"] = self._now_utc().isoformat()
            if requested_business_eval is not None:
                if record.business_eval is None:
                    changes["business_eval"] = requested_business_eval
                elif record.business_eval != requested_business_eval:
                    changes["business_eval"] = requested_business_eval
                    if record.current_trial_id is not None:
                        changes["status"] = "running"
                        changes["final_reason"] = "business_eval_rerun_pending"
                        changes["final_detail"] = None
            if not record.goal_only_stop and self.request.goal_only_stop:
                changes["goal_only_stop"] = True
            if changes:
                record = replace(record, **changes)
                storage.write_study_record(self.paths.study_file, record)
            return record
        record = contracts.StudyRecord(
            study_name=self.request.study_name,
            task=self.request.task,
            status="running",
            mode=self.request.mode,
            train_root=str(self.request.train_root),
            generator_workspace=str(self.request.generator_workspace),
            judge=contracts.JudgeConfig(provider=self.request.judge_provider, model=self.request.judge_model),
            budget=contracts.StudyBudget(
                max_trials=self.request.max_trials,
                max_hours=self.request.max_hours,
                max_new_datasets=self.request.max_new_datasets,
                max_no_improve_trials=self.request.max_no_improve_trials,
            ),
            business_eval=requested_business_eval,
            started_at=self._now_utc().isoformat(),
            current_trial_id=None,
            best_trial_id=None,
            goal_only_stop=self.request.goal_only_stop,
        )
        storage.write_study_record(self.paths.study_file, record)
        return record

    def _ensure_current_trial(self, study: contracts.StudyRecord) -> str:
        if study.current_trial_id is not None:
            self.paths.ensure_trial_dir(study.current_trial_id)
            return study.current_trial_id
        trial_id = self._next_trial_id()
        self.paths.ensure_trial_dir(trial_id)
        updated = self._with_study_updates(study, current_trial_id=trial_id)
        storage.write_study_record(self.paths.study_file, updated)
        return trial_id

    def _current_stage(self, study: contracts.StudyRecord, trial_id: str) -> str:
        trial_dir = self.paths.ensure_trial_dir(trial_id)
        if study.status == "running" and study.final_reason == "business_eval_rerun_pending":
            return "NEXT_ACTION"
        stage = state_machine.infer_resume_stage(trial_dir, task=self.request.task, stop_file=self.paths.stop_file)
        if stage in {
            "TRAIN",
            "TRAIN_QUERY",
            "QUERY_GATE",
            "TRAIN_SCENE",
            "SCENE_GATE",
            "TRAIN_EMBEDDER_BASE",
            "EMBEDDER_GATE",
            "BUILD_EMBEDDER_HARDSET",
            "TRAIN_EMBEDDER_HARD",
            "CALIBRATE_MATCHER",
            "OFFLINE_EVAL",
            "TEST",
        }:
            input_path = self.paths.input_file(trial_id)
            if input_path.exists():
                trial_input = storage.read_trial_input_record(input_path)
                dataset_config = default_dataset_config(
                    self.request.train_root,
                    self.request.task,
                    trial_input.dataset_version,
                )
                if not dataset_config.exists():
                    return "BUILD_DATASET"
        return stage

    def _normalize_stage_name_for_task(self, stage: str) -> str:
        normalized = normalize_stage_name(stage)
        if self.request.task == "group1" and normalized == "TRAIN":
            return "TRAIN_QUERY"
        return normalized

    def _next_trial_id(self) -> str:
        trial_dirs = [candidate.name for candidate in self.paths.trials_root.glob("trial_*") if candidate.is_dir()]
        if not trial_dirs:
            return layout.format_trial_id(1)
        return layout.format_trial_id(max(layout.parse_trial_id(item) for item in trial_dirs) + 1)

    def _build_initial_trial_input(self, trial_id: str) -> contracts.TrialInputRecord:
        return contracts.TrialInputRecord(
            trial_id=trial_id,
            task=self.request.task,
            dataset_version=self.request.dataset_version,
            train_name=self.request.train_name or trial_id,
            train_mode=self.request.train_mode,
            base_run=self.request.base_run,
            params={
                "model": self.request.model,
                "epochs": self.request.epochs,
                "batch": self.request.batch,
                "imgsz": self.request.effective_imgsz,
                "device": self.request.device,
            },
            dataset_preset=_infer_dataset_preset(self.request.dataset_version),
            dataset_override=None,
        )

    def _prepare_next_trial(
        self,
        summary_record: contracts.ResultSummaryRecord,
        decision: contracts.DecisionRecord,
        plan_record: contracts.DatasetPlanRecord | None = None,
        retune_plan_record: contracts.RetunePlanRecord | None = None,
    ) -> contracts.TrialInputRecord:
        previous_input = storage.read_trial_input_record(self.paths.input_file(summary_record.trial_id))
        next_trial_id = self._next_trial_id()
        dataset_action = plan_record.dataset_action if plan_record is not None else _string_action(decision.next_action, "dataset_action", "reuse")
        train_action = _string_action(decision.next_action, "train_action", "from_run")
        if dataset_action == "new_version":
            dataset_version = layout.format_generated_dataset_version(summary_record.study_name, next_trial_id)
        else:
            dataset_version = previous_input.dataset_version
        dataset_preset = previous_input.dataset_preset or _infer_dataset_preset(previous_input.dataset_version)
        if plan_record is not None and plan_record.generator_preset:
            dataset_preset = plan_record.generator_preset
        dataset_override = plan_record.generator_overrides if dataset_action == "new_version" else None

        next_params = dict(previous_input.params)
        for internal_key in optuna_runtime.INTERNAL_PARAM_KEYS:
            next_params.pop(internal_key, None)
        next_params.pop(GROUP1_EMBEDDER_HARDSET_REBUILD_COUNT_PARAM, None)
        next_params.pop(GROUP1_COMPONENT_PARAMS_PARAM, None)
        if decision.decision == "RETUNE":
            if retune_plan_record is not None:
                next_params.update(retune_plan_record.parameter_updates)
            else:
                plan = optimize.build_optimization_plan(
                    summary=summary_record,
                    decision=decision,
                    optuna_available=self._optuna_available(),
                )
                if plan.use_optuna:
                    try:
                        suggestion = self._optuna_runtime().suggest_next_parameters(
                            plan=plan,
                            completed_input=previous_input,
                            summary=summary_record,
                            next_trial_id=next_trial_id,
                        )
                    except optuna_runtime.OptunaRuntimeError:
                        next_params.update(plan.fallback_parameters)
                    else:
                        next_params.update(suggestion.params)
                        next_params[optuna_runtime.OPTUNA_TRIAL_NUMBER_KEY] = suggestion.trial_number
                        next_params[optuna_runtime.OPTUNA_ENGINE_KEY] = "optuna"
                else:
                    next_params.update(plan.fallback_parameters)

        if train_action == "resume":
            train_mode = "resume"
            train_name = previous_input.train_name
            base_run = None
            next_params.pop("model", None)
        elif train_action == "fresh":
            train_mode = "fresh"
            train_name = next_trial_id
            base_run = None
        else:
            train_mode = "from_run"
            train_name = next_trial_id
            base_run = _string_action(decision.next_action, "base_run", previous_input.train_name)
            next_params.pop("model", None)

        if self.request.task == "group1":
            regenerate_all_components = dataset_action == "new_version"
            component_plan = self._group1_component_plan_for_next_trial(
                trial_id=summary_record.trial_id,
                regenerate_all=regenerate_all_components,
            )
            if not regenerate_all_components and retune_plan_record is not None and retune_plan_record.component_actions is not None:
                component_plan.update(retune_plan_record.component_actions)
            next_params[GROUP1_COMPONENT_PLAN_PARAM] = component_plan
            if retune_plan_record is not None and retune_plan_record.component_parameter_updates is not None:
                next_params[GROUP1_COMPONENT_PARAMS_PARAM] = retune_plan_record.component_parameter_updates

        return contracts.TrialInputRecord(
            trial_id=next_trial_id,
            task=self.request.task,
            dataset_version=dataset_version,
            train_name=train_name,
            train_mode=train_mode,
            base_run=base_run,
            params=next_params,
            dataset_preset=dataset_preset,
            dataset_override=dataset_override,
        )

    def _update_leaderboard(
        self,
        summary_record: contracts.ResultSummaryRecord,
        decision: contracts.DecisionRecord,
        business_record: contracts.BusinessEvalRecord | None = None,
    ) -> contracts.LeaderboardRecord:
        existing_entries: dict[str, contracts.LeaderboardEntry] = {}
        if self.paths.leaderboard_file.exists():
            leaderboard = storage.read_leaderboard_record(self.paths.leaderboard_file)
            existing_entries = {item.trial_id: item for item in leaderboard.entries}

        trial_ids = sorted({*existing_entries.keys(), summary_record.trial_id}, key=layout.parse_trial_id)
        entries: list[contracts.LeaderboardEntry] = []
        for candidate_trial_id in trial_ids:
            if candidate_trial_id == summary_record.trial_id:
                entry = self._build_leaderboard_entry(
                    summary_record=summary_record,
                    decision=decision,
                    business_record=business_record,
                )
            else:
                candidate_summary_path = self.paths.result_summary_file(candidate_trial_id)
                if not candidate_summary_path.exists():
                    fallback_entry = existing_entries.get(candidate_trial_id)
                    if fallback_entry is None:
                        continue
                    entries.append(fallback_entry)
                    continue
                candidate_summary = storage.read_result_summary_record(candidate_summary_path)
                candidate_decision_path = self.paths.decision_file(candidate_trial_id)
                fallback_decision_name = "RETUNE"
                existing_entry = existing_entries.get(candidate_trial_id)
                if existing_entry is not None and existing_entry.decision is not None:
                    fallback_decision_name = existing_entry.decision
                candidate_decision = (
                    storage.read_decision_record(candidate_decision_path)
                    if candidate_decision_path.exists()
                    else contracts.DecisionRecord(
                        trial_id=candidate_trial_id,
                        decision=fallback_decision_name,
                        confidence=0.0,
                        reason="leaderboard_rehydrated",
                        next_action={"dataset_action": "reuse", "train_action": "from_run"},
                        evidence=["leaderboard_rehydrated"],
                        agent=contracts.AgentRef(provider="system", name="leaderboard"),
                    )
                )
                candidate_business = self._safe_read_business_eval_record(candidate_trial_id)
                entry = self._build_leaderboard_entry(
                    summary_record=candidate_summary,
                    decision=candidate_decision,
                    business_record=candidate_business,
                )
            entries.append(entry)

        record = contracts.LeaderboardRecord(
            study_name=self.request.study_name,
            task=self.request.task,
            primary_metric=policies.policy_for_task(self.request.task).primary_metric,
            entries=entries,
        )
        storage.write_leaderboard_record(self.paths.leaderboard_file, record)
        if record.best_entry is not None:
            storage.write_best_trial_record(
                self.paths.best_trial_file,
                contracts.BestTrialRecord.from_leaderboard_entry(
                    study_name=self.request.study_name,
                    task=self.request.task,
                    primary_metric=record.primary_metric,
                    entry=record.best_entry,
                ),
            )
        self._prune_model_runs(record)
        return record

    def _resolve_test_model_path(self, trial_id: str) -> Path | None:
        train_path = self.paths.train_file(trial_id)
        if self.request.task == "group1" and self.paths.scene_train_file(trial_id).exists():
            train_path = self.paths.scene_train_file(trial_id)
        if not train_path.exists():
            return None
        train_record = storage.read_train_record(train_path)
        return preferred_checkpoint_path(
            Path(train_record.best_weights),
            Path(train_record.last_weights),
        )

    def _load_group1_matcher_settings(self, trial_id: str) -> dict[str, float | None]:
        if self.request.task != "group1":
            return {
                "similarity_threshold": None,
                "ambiguity_margin": None,
            }
        path = self.paths.matcher_config_file(trial_id)
        if not path.exists():
            return {
                "similarity_threshold": GROUP1_MATCHER_SIMILARITY_THRESHOLD,
                "ambiguity_margin": GROUP1_MATCHER_AMBIGUITY_MARGIN,
            }
        payload = self._read_json_payload(path)
        return {
            "similarity_threshold": _float_like(payload.get("similarity_threshold"), GROUP1_MATCHER_SIMILARITY_THRESHOLD),
            "ambiguity_margin": _float_like(payload.get("ambiguity_margin"), GROUP1_MATCHER_AMBIGUITY_MARGIN),
        }

    def _read_json_payload(self, path: Path) -> dict[str, object]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError(f"JSON 工件格式非法：{path}")
        return payload

    def _read_group1_component_summary(self, train_record: contracts.TrainRecord, component: str) -> dict[str, object]:
        summary_path = Path(train_record.run_dir) / "summary.json"
        if not summary_path.exists():
            return {
                "weights": {
                    "best": train_record.best_weights,
                    "last": train_record.last_weights,
                },
                "metrics": {},
                "gate": {
                    "status": "missing",
                    "failed_checks": ["summary_missing"],
                },
                "summary_path": str(summary_path),
            }
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {
                "weights": {
                    "best": train_record.best_weights,
                    "last": train_record.last_weights,
                },
                "metrics": {},
                "gate": {
                    "status": "missing",
                    "failed_checks": ["summary_invalid"],
                },
                "summary_path": str(summary_path),
            }
        components = payload.get("components")
        if not isinstance(components, dict):
            return {
                "weights": {
                    "best": train_record.best_weights,
                    "last": train_record.last_weights,
                },
                "metrics": {},
                "gate": {
                    "status": "missing",
                    "failed_checks": ["components_missing"],
                },
                "summary_path": str(summary_path),
            }
        component_summary = components.get(component)
        if not isinstance(component_summary, dict):
            return {
                "weights": {
                    "best": train_record.best_weights,
                    "last": train_record.last_weights,
                },
                "metrics": {},
                "gate": {
                    "status": "missing",
                    "failed_checks": [f"{component}_missing"],
                },
                "summary_path": str(summary_path),
            }
        return component_summary

    def _promote_current_trial_last_weights_if_selected(
        self,
        *,
        trial_id: str,
        leaderboard: contracts.LeaderboardRecord,
    ) -> None:
        if self.request.task != "group2":
            return
        best_entry = leaderboard.best_entry
        if best_entry is None or best_entry.trial_id != trial_id:
            return
        train_path = self.paths.train_file(trial_id)
        if not train_path.exists():
            return
        train_record = storage.read_train_record(train_path)
        best_path = Path(train_record.best_weights)
        last_path = Path(train_record.last_weights)
        if best_path.exists() or not last_path.exists():
            return
        best_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(last_path, best_path)

    def _safe_read_business_eval_record(self, trial_id: str) -> contracts.BusinessEvalRecord | None:
        path = self.paths.business_eval_file(trial_id)
        if not path.exists():
            return None
        try:
            return storage.read_business_eval_record(path)
        except (OSError, ValueError):
            return None

    def _prune_model_runs(self, leaderboard: contracts.LeaderboardRecord) -> None:
        prune_names = {
            entry.train_name
            for entry in leaderboard.entries[3:]
            if entry.train_name
        }
        for train_name in sorted(prune_names):
            run_dir = default_run_dir(self.request.train_root, self.request.task, train_name)
            if run_dir.exists():
                shutil.rmtree(run_dir)

    def _build_leaderboard_entry(
        self,
        *,
        summary_record: contracts.ResultSummaryRecord,
        decision: contracts.DecisionRecord,
        business_record: contracts.BusinessEvalRecord | None,
    ) -> contracts.LeaderboardEntry:
        metrics = dict(summary_record.test_metrics)
        for key, value in summary_record.evaluation_metrics.items():
            metrics[key] = value

        input_record = None
        input_path = self.paths.input_file(summary_record.trial_id)
        if input_path.exists():
            input_record = storage.read_trial_input_record(input_path)

        difficulty_score = _difficulty_score_for_trial(
            dataset_version=summary_record.dataset_version,
            dataset_preset=None if input_record is None else input_record.dataset_preset,
        )
        offline_score = _offline_ranking_score(summary_record)
        business_success_rate = None if business_record is None else business_record.success_rate
        commercial_ready = None if business_record is None else business_record.commercial_ready
        ranking_score = _composite_ranking_score(
            offline_score=offline_score,
            difficulty_score=difficulty_score,
            business_success_rate=business_success_rate,
            commercial_ready=commercial_ready,
        )
        metrics.update(
            {
                "offline_score": round(offline_score, 6),
                "difficulty_score": round(difficulty_score, 6),
                "ranking_score": round(ranking_score, 6),
                "business_success_rate": None if business_success_rate is None else round(business_success_rate, 6),
                "commercial_ready": commercial_ready,
                "dataset_preset": None if input_record is None else input_record.dataset_preset,
            }
        )
        return contracts.LeaderboardEntry(
            trial_id=summary_record.trial_id,
            dataset_version=summary_record.dataset_version,
            train_name=summary_record.train_name,
            primary_score=summary_record.primary_score or 0.0,
            metrics=metrics,
            decision=decision.decision,
        )

    def _evaluate_stop(
        self,
        study: contracts.StudyRecord,
        leaderboard: contracts.LeaderboardRecord,
        *,
        pending_new_dataset: bool,
        ignore_adaptive_limits: bool = False,
    ) -> stop_rules.StopDecision:
        if study.goal_only_stop:
            if self.paths.stop_file.exists():
                return stop_rules.StopDecision(True, "stop_file_detected", "STOP file is present")
            return stop_rules.StopDecision(False, "continue")
        scores_by_trial: list[float] = []
        for trial_dir in sorted(self.paths.trials_root.glob("trial_*"), key=lambda item: layout.parse_trial_id(item.name)):
            summary_path = self.paths.result_summary_file(trial_dir.name)
            if not summary_path.exists():
                continue
            record = storage.read_result_summary_record(summary_path)
            if record.primary_score is not None:
                scores_by_trial.append(record.primary_score)
        policy = policies.policy_for_task(self.request.task)
        stop_policy = stop_rules.StopPolicy(
            max_trials=self.request.max_trials,
            max_hours=self.request.max_hours,
            max_new_datasets=self.request.max_new_datasets,
            plateau_window=None if ignore_adaptive_limits else policy.plateau_window,
            min_delta=policy.min_delta,
            max_no_improve_trials=None if ignore_adaptive_limits else self.request.max_no_improve_trials,
        )
        snapshot = stop_rules.StopSnapshot(
            completed_trials=len(scores_by_trial),
            elapsed_hours=self._elapsed_hours(study),
            recent_primary_scores=scores_by_trial,
            new_datasets_used=self._count_new_dataset_versions(),
            pending_new_dataset=pending_new_dataset,
            no_improve_trials=_count_no_improve_trials(scores_by_trial, policy.min_delta),
            stop_file_present=self.paths.stop_file.exists(),
        )
        return stop_rules.evaluate_stop(stop_policy, snapshot)

    def _resolve_evaluation_request(
        self,
        *,
        trial_id: str,
        train_name: str,
    ) -> runners.evaluate.EvaluateRunnerRequest | None:
        explicit = self._explicit_evaluation_request(train_name)
        if explicit is not None:
            return explicit
        if not self.paths.test_file(trial_id).exists():
            return None
        test_record = storage.read_test_record(self.paths.test_file(trial_id))
        gold_dir = Path(test_record.report_dir) / "_gold"
        prediction_dir = Path(test_record.predict_output_dir)
        report_dir = Path(test_record.val_output_dir)
        if not self._evaluation_inputs_exist(gold_dir=gold_dir, prediction_dir=prediction_dir):
            return None
        return runners.evaluate.EvaluateRunnerRequest(
            task=self.request.task,
            gold_dir=gold_dir,
            prediction_dir=prediction_dir,
            report_dir=report_dir,
            point_tolerance_px=self.request.point_tolerance_px,
            iou_threshold=self.request.iou_threshold,
        )

    def _explicit_evaluation_request(self, train_name: str) -> runners.evaluate.EvaluateRunnerRequest | None:
        if self.request.gold_dir is None or self.request.prediction_dir is None:
            return None
        if not self._evaluation_inputs_exist(gold_dir=self.request.gold_dir, prediction_dir=self.request.prediction_dir):
            return None
        return runners.evaluate.EvaluateRunnerRequest(
            task=self.request.task,
            gold_dir=self.request.gold_dir,
            prediction_dir=self.request.prediction_dir,
            report_dir=default_report_dir(self.request.train_root, self.request.task) / f"eval_{train_name}",
            point_tolerance_px=self.request.point_tolerance_px,
            iou_threshold=self.request.iou_threshold,
        )

    def _evaluation_inputs_exist(self, *, gold_dir: Path, prediction_dir: Path) -> bool:
        return (gold_dir / "labels.jsonl").exists() and (prediction_dir / "labels.jsonl").exists()

    def _elapsed_hours(self, study: contracts.StudyRecord) -> float:
        if study.started_at is None:
            return 0.0
        started_at = _parse_timestamp(study.started_at)
        elapsed = self._now_utc() - started_at
        return max(elapsed.total_seconds() / 3600.0, 0.0)

    def _count_new_dataset_versions(self) -> int:
        dataset_versions: list[str] = []
        for trial_dir in sorted(self.paths.trials_root.glob("trial_*"), key=lambda item: layout.parse_trial_id(item.name)):
            input_path = self.paths.input_file(trial_dir.name)
            if not input_path.exists():
                continue
            record = storage.read_trial_input_record(input_path)
            dataset_versions.append(record.dataset_version)
        if not dataset_versions:
            return 0
        baseline = dataset_versions[0]
        return len({version for version in dataset_versions if version != baseline})

    def _with_study_updates(self, study: contracts.StudyRecord, **changes: object) -> contracts.StudyRecord:
        started_at = study.started_at or self._now_utc().isoformat()
        return replace(study, started_at=started_at, **changes)

    def _now_utc(self) -> datetime:
        value = self.dependencies.now_provider()
        if not isinstance(value, datetime):
            raise TypeError("now_provider must return datetime")
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _write_trial_summary(
        self,
        summary_record: contracts.ResultSummaryRecord,
        decision: contracts.DecisionRecord | None,
    ) -> None:
        lines = [
            f"# {summary_record.trial_id}",
            "",
            f"- task: {summary_record.task}",
            f"- dataset_version: {summary_record.dataset_version}",
            f"- train_name: {summary_record.train_name}",
            f"- primary_metric: {summary_record.primary_metric}",
            f"- primary_score: {summary_record.primary_score}",
            f"- trend: {summary_record.trend}",
        ]
        if decision is not None:
            lines.extend(["", "## Decision", "", f"- decision: {decision.decision}", f"- reason: {decision.reason}"])
        self.paths.trial_summary_file(summary_record.trial_id).write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_study_summary(
        self,
        study: contracts.StudyRecord,
        leaderboard: contracts.LeaderboardRecord,
        decision: contracts.DecisionRecord,
        business_eval_record: contracts.BusinessEvalRecord | None = None,
    ) -> None:
        record = self._study_status_record(
            study=study,
            leaderboard=leaderboard,
            decision=decision,
            business_eval_record=business_eval_record,
        )
        storage.write_study_status_record(self.paths.study_status_file, record)
        self.paths.summary_file.write_text(study_status.markdown_from_study_status(record), encoding="utf-8")

    def _requested_business_eval_config(self) -> contracts.BusinessEvalConfig | None:
        if self.request.business_eval_dir is None:
            return None
        return contracts.BusinessEvalConfig(
            cases_root=str(self.request.business_eval_dir),
            success_threshold=self.request.business_eval_success_threshold,
            min_cases=self.request.business_eval_min_cases,
            sample_size=self.request.business_eval_sample_size,
            point_tolerance_px=self.request.point_tolerance_px,
            iou_threshold=self.request.iou_threshold,
        )

    def _business_eval_enabled(self, study: contracts.StudyRecord) -> bool:
        return study.business_eval is not None

    def _effective_next_action_decision(
        self,
        *,
        study: contracts.StudyRecord,
        summary_record: contracts.ResultSummaryRecord,
        decision: contracts.DecisionRecord,
        business_record: contracts.BusinessEvalRecord | None,
        leaderboard: contracts.LeaderboardRecord,
    ) -> contracts.DecisionRecord:
        if self.request.task == "group1":
            if business_record is not None and not business_record.commercial_ready:
                return self._regenerate_decision_for_business_goal(
                    summary_record=summary_record,
                    decision=decision,
                    business_record=business_record,
                    leaderboard=leaderboard,
                )
            if decision.decision == "REGENERATE_DATA":
                return contracts.DecisionRecord(
                    trial_id=decision.trial_id,
                    decision="RETUNE",
                    confidence=decision.confidence,
                    reason="group1_regenerate_deferred_until_business_gate",
                    next_action={
                        "dataset_action": "reuse",
                        "train_action": "from_run",
                        "base_run": summary_record.train_name,
                    },
                    evidence=[
                        *decision.evidence,
                        f"offline_regenerate_deferred={summary_record.train_name}",
                    ],
                    agent=decision.agent,
                )
            return decision
        if (
            self._business_eval_enabled(study)
            and not (business_record is not None and business_record.commercial_ready)
        ):
            return self._regenerate_decision_for_business_goal(
                summary_record=summary_record,
                decision=decision,
                business_record=business_record,
                leaderboard=leaderboard,
            )
        if business_record is not None:
            return self._retry_decision_after_failed_business_gate(
                summary_record=summary_record,
                decision=decision,
                business_record=business_record,
            )
        return decision

    def _run_business_eval_if_needed(
        self,
        *,
        trial_id: str,
        summary_record: contracts.ResultSummaryRecord,
        decision: contracts.DecisionRecord,
        study: contracts.StudyRecord,
    ) -> contracts.BusinessEvalRecord | None:
        config = study.business_eval
        if config is None or decision.decision != "PROMOTE_BRANCH":
            return None

        request = self._build_business_eval_request(
            trial_id=trial_id,
            dataset_version=summary_record.dataset_version,
            train_name=summary_record.train_name,
            config=config,
        )
        return self._execute_business_eval_request(request=request)

    def _load_or_run_business_eval_if_needed(
        self,
        *,
        trial_id: str,
        summary_record: contracts.ResultSummaryRecord,
        decision: contracts.DecisionRecord,
        study: contracts.StudyRecord,
    ) -> contracts.BusinessEvalRecord | None:
        existing = self._safe_read_business_eval_record(trial_id)
        if existing is not None:
            return existing
        marker_path = self.paths.business_stage_file(trial_id)
        if marker_path.exists():
            try:
                payload = json.loads(marker_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = None
            if isinstance(payload, dict) and payload.get("status") == "skipped":
                return None
        return self._run_business_eval_if_needed(
            trial_id=trial_id,
            summary_record=summary_record,
            decision=decision,
            study=study,
        )

    def _build_business_eval_request(
        self,
        *,
        trial_id: str,
        dataset_version: str,
        train_name: str,
        config: contracts.BusinessEvalConfig,
    ) -> runners.business_eval.BusinessEvalRunnerRequest:
        matcher_settings = self._load_group1_matcher_settings(trial_id)
        return runners.business_eval.BusinessEvalRunnerRequest(
            trial_id=trial_id,
            task=self.request.task,
            train_root=self.request.train_root,
            dataset_version=dataset_version,
            train_name=train_name,
            cases_root=Path(config.cases_root),
            report_dir=self.paths.business_eval_root(trial_id),
            device=self.request.device,
            imgsz=self.request.effective_imgsz,
            success_threshold=config.success_threshold,
            min_cases=config.min_cases,
            sample_size=config.sample_size,
            point_tolerance_px=config.point_tolerance_px,
            iou_threshold=config.iou_threshold,
            similarity_threshold=matcher_settings["similarity_threshold"],
            ambiguity_margin=matcher_settings["ambiguity_margin"],
        )

    def _execute_business_eval_request(
        self,
        *,
        request: runners.business_eval.BusinessEvalRunnerRequest,
    ) -> contracts.BusinessEvalRecord:
        try:
            result = self.dependencies.business_eval_runner(request)
        except runners.RunnerExecutionError as exc:
            return contracts.BusinessEvalRecord(
                trial_id=request.trial_id,
                task=request.task,
                train_name=request.train_name,
                cases_root=str(request.cases_root),
                available_cases=0,
                total_cases=0,
                passed_cases=0,
                success_rate=0.0,
                success_threshold=request.success_threshold,
                min_cases=request.min_cases,
                sample_size=request.sample_size,
                commercial_ready=False,
                point_tolerance_px=request.point_tolerance_px,
                iou_threshold=request.iou_threshold,
                sampled_source=str(request.report_dir / "_sampled_source" / "labels.jsonl"),
                report_dir=str(request.report_dir),
                prediction_dir=str(request.report_dir / "modeltest"),
                evaluation_report_dir=str(request.report_dir / "evaluation"),
                case_results=[],
                evidence=[f"runner_error={exc.reason}", str(exc)],
            )
        return result.record

    def _write_business_eval_artifacts(
        self,
        *,
        trial_id: str,
        record: contracts.BusinessEvalRecord,
    ) -> None:
        storage.write_business_eval_record(self.paths.business_eval_file(trial_id), record)
        storage.write_text(self.paths.business_eval_markdown_file(trial_id), business_eval.markdown_from_business_eval(record))
        storage.write_text(self.paths.business_eval_log_file(trial_id), business_eval.log_from_business_eval(record))

    def _write_commercial_report(
        self,
        *,
        study: contracts.StudyRecord,
        leaderboard: contracts.LeaderboardRecord,
        summary_record: contracts.ResultSummaryRecord,
        raw_decision: contracts.DecisionRecord,
        effective_decision: contracts.DecisionRecord,
        business_eval_record: contracts.BusinessEvalRecord,
    ) -> None:
        storage.write_text(
            self.paths.commercial_report_file,
            business_eval.commercial_report_markdown(
                study=study,
                leaderboard=leaderboard,
                summary_record=summary_record,
                raw_decision=raw_decision,
                effective_decision=effective_decision,
                business_record=business_eval_record,
            ),
        )

    def _retry_decision_after_failed_business_gate(
        self,
        *,
        summary_record: contracts.ResultSummaryRecord,
        decision: contracts.DecisionRecord,
        business_record: contracts.BusinessEvalRecord,
    ) -> contracts.DecisionRecord:
        return contracts.DecisionRecord(
            trial_id=decision.trial_id,
            decision="REGENERATE_DATA",
            confidence=decision.confidence,
            reason="business_gate_blocked",
            next_action={
                "dataset_action": "new_version",
                "train_action": "from_run",
                "base_run": summary_record.train_name,
            },
            evidence=[
                *decision.evidence,
                f"business_success_rate={business_record.success_rate:.4f}",
                f"business_success_threshold={business_record.success_threshold:.4f}",
                "business_gate_blocked",
            ],
            agent=decision.agent,
        )

    def _regenerate_decision_for_business_goal(
        self,
        *,
        summary_record: contracts.ResultSummaryRecord,
        decision: contracts.DecisionRecord,
        business_record: contracts.BusinessEvalRecord | None,
        leaderboard: contracts.LeaderboardRecord,
    ) -> contracts.DecisionRecord:
        if decision.decision == "PROMOTE_BRANCH" and business_record is None:
            return decision

        best_train_name = (
            leaderboard.best_entry.train_name
            if leaderboard.best_entry is not None and leaderboard.best_entry.train_name
            else summary_record.train_name
        )
        evidence = [
            *decision.evidence,
            f"business_goal_original_decision={decision.decision}",
            f"business_goal_base_run={best_train_name}",
        ]
        reason = "candidate_not_promoted_regenerate"
        if business_record is not None:
            evidence.extend(
                [
                    f"business_success_rate={business_record.success_rate:.4f}",
                    f"business_success_threshold={business_record.success_threshold:.4f}",
                ]
            )
            reason = "business_gate_blocked"
        return contracts.DecisionRecord(
            trial_id=decision.trial_id,
            decision="REGENERATE_DATA",
            confidence=decision.confidence,
            reason=reason,
            next_action={
                "dataset_action": "new_version",
                "train_action": "from_run",
                "base_run": best_train_name,
            },
            evidence=evidence,
            agent=decision.agent,
        )

    def _summarize_trial_with_runtime(
        self,
        *,
        trial_id: str,
        primary_metric: str,
        recent_window: int,
        fallback_record: contracts.ResultSummaryRecord,
    ) -> contracts.ResultSummaryRecord:
        runtime = self._opencode_runtime()
        files = [self.paths.test_file(trial_id)]
        files.extend(path for path in (self.paths.evaluate_file(trial_id), self.paths.best_trial_file) if path.exists())
        files.extend(self._recent_result_summary_files(trial_id, recent_window))
        try:
            result = runtime.result_read(
                study_name=self.request.study_name,
                task=self.request.task,
                trial_id=trial_id,
                dataset_version=fallback_record.dataset_version,
                train_name=fallback_record.train_name,
                primary_metric=primary_metric,
                files=files,
            )
        except opencode_runtime.OpenCodeRuntimeError as exc:
            return _summary_with_extra_evidence(
                fallback_record,
                [f"result_read_fallback=runtime_error", str(exc)],
            )

        try:
            payload = json_extract.extract_json_object_from_opencode_output(
                result.stdout,
                required_keys={"study_name", "task", "trial_id"},
            )
            hydrated_payload = _hydrate_result_summary_payload(payload, fallback_record=fallback_record)
            return contracts.ResultSummaryRecord.from_dict(hydrated_payload)
        except ValueError as exc:
            return _summary_with_extra_evidence(
                fallback_record,
                [f"result_read_fallback=invalid_payload", str(exc)],
            )

    def _study_status_record(
        self,
        *,
        study: contracts.StudyRecord,
        leaderboard: contracts.LeaderboardRecord,
        decision: contracts.DecisionRecord,
        business_eval_record: contracts.BusinessEvalRecord | None,
    ) -> contracts.StudyStatusRecord:
        fallback_record = study_status.build_study_status(
            study=study,
            leaderboard=leaderboard,
            decision=decision,
            business_eval=business_eval_record,
        )
        if self.request.judge_provider != "opencode" or business_eval_record is not None:
            return fallback_record

        runtime = self._opencode_runtime()
        files = [self.paths.study_file, self.paths.leaderboard_file]
        files.extend(path for path in (self.paths.best_trial_file, self.paths.decisions_file) if path.exists())
        try:
            result = runtime.study_status(
                study_name=self.request.study_name,
                task=self.request.task,
                files=files,
            )
        except opencode_runtime.OpenCodeRuntimeError as exc:
            return _study_status_with_extra_evidence(
                fallback_record,
                [f"study_status_fallback=runtime_error", str(exc)],
            )

        try:
            payload = json_extract.extract_json_object_from_opencode_output(
                result.stdout,
                required_keys={
                    "study_name",
                    "task",
                    "status",
                    "budget_pressure",
                    "summary_cn",
                    "next_actions_cn",
                    "evidence",
                },
            )
            return contracts.StudyStatusRecord.from_dict(payload)
        except ValueError as exc:
            return _study_status_with_extra_evidence(
                fallback_record,
                [f"study_status_fallback=invalid_payload", str(exc)],
            )

    def _dataset_plan_record(
        self,
        *,
        summary_record: contracts.ResultSummaryRecord,
        decision: contracts.DecisionRecord,
        leaderboard: contracts.LeaderboardRecord,
    ) -> contracts.DatasetPlanRecord | None:
        if decision.decision != "REGENERATE_DATA":
            return None

        fallback_record = dataset_plan.build_dataset_plan(summary=summary_record, decision=decision)
        if self.request.judge_provider != "opencode":
            return fallback_record

        runtime = self._opencode_runtime()
        files = [self.paths.result_summary_file(summary_record.trial_id)]
        files.extend(path for path in (self.paths.leaderboard_file, self.paths.best_trial_file) if path.exists())
        try:
            result = runtime.plan_dataset(
                study_name=self.request.study_name,
                task=self.request.task,
                trial_id=summary_record.trial_id,
                files=files,
            )
        except opencode_runtime.OpenCodeRuntimeError as exc:
            return _dataset_plan_with_extra_evidence(
                fallback_record,
                [f"dataset_plan_fallback=runtime_error", str(exc)],
            )

        try:
            payload = json_extract.extract_json_object_from_opencode_output(
                result.stdout,
                required_keys={
                    "study_name",
                    "task",
                    "trial_id",
                    "dataset_action",
                    "boost_classes",
                    "focus_failure_patterns",
                    "rationale_cn",
                    "evidence",
                },
            )
            return contracts.DatasetPlanRecord.from_dict(payload)
        except ValueError as exc:
            return _dataset_plan_with_extra_evidence(
                fallback_record,
                [f"dataset_plan_fallback=invalid_payload", str(exc)],
            )

    def _retune_plan_record(
        self,
        *,
        summary_record: contracts.ResultSummaryRecord,
        decision: contracts.DecisionRecord,
        leaderboard: contracts.LeaderboardRecord,
    ) -> contracts.RetunePlanRecord | None:
        if decision.decision != "RETUNE":
            return None
        if not self.paths.trial_analysis_file(summary_record.trial_id).exists():
            return None
        analysis_record = storage.read_trial_analysis_record(self.paths.trial_analysis_file(summary_record.trial_id))
        fallback_record = retune_plan.build_retune_plan(
            summary=summary_record,
            analysis=analysis_record,
            decision=decision,
        )
        if self.request.judge_provider != "opencode":
            return None

        runtime = self._opencode_runtime()
        if not hasattr(runtime, "plan_retune"):
            return _retune_plan_with_extra_evidence(
                fallback_record,
                ["retune_plan_fallback=runtime_missing", "runtime_missing_plan_retune"],
            )
        files = [
            self.paths.result_summary_file(summary_record.trial_id),
            self.paths.trial_analysis_file(summary_record.trial_id),
        ]
        files.extend(path for path in (self.paths.leaderboard_file, self.paths.best_trial_file) if path.exists())
        try:
            result = runtime.plan_retune(
                study_name=self.request.study_name,
                task=self.request.task,
                trial_id=summary_record.trial_id,
                files=files,
            )
        except opencode_runtime.OpenCodeRuntimeError as exc:
            return _retune_plan_with_extra_evidence(
                fallback_record,
                [f"retune_plan_fallback=runtime_error", str(exc)],
            )

        try:
            payload = json_extract.extract_json_object_from_opencode_output(
                result.stdout,
                required_keys={
                    "study_name",
                    "task",
                    "trial_id",
                    "parameter_updates",
                    "rationale_cn",
                    "evidence",
                },
            )
            return contracts.RetunePlanRecord.from_dict(payload)
        except ValueError as exc:
            return _retune_plan_with_extra_evidence(
                fallback_record,
                [f"retune_plan_fallback=invalid_payload", str(exc)],
            )

    def _judge_trial(
        self,
        trial_id: str,
        summary_record: contracts.ResultSummaryRecord,
    ) -> contracts.DecisionRecord:
        if self.request.judge_provider == "opencode":
            agent = contracts.AgentRef(
                provider="opencode",
                name="judge-trial",
                model=self.request.judge_model,
            )
            runtime = self._opencode_runtime()
            files = [self.paths.study_file, self.paths.result_summary_file(trial_id)]
            files.extend(
                path
                for path in (
                    self.paths.leaderboard_file,
                    self.paths.decisions_file,
                    self.paths.trial_analysis_file(trial_id),
                    self.paths.offline_eval_file(trial_id),
                    self.paths.business_eval_file(trial_id),
                )
                if path.exists()
            )
            try:
                result = runtime.judge_trial(
                    study_name=self.request.study_name,
                    task=self.request.task,
                    trial_id=trial_id,
                    files=files,
                )
            except opencode_runtime.OpenCodeRuntimeError as exc:
                return decision_protocol.fallback_decision(
                    trial_id=trial_id,
                    agent=agent,
                    summary=summary_record,
                    reason_code="runtime_error",
                    extra_evidence=[str(exc)],
                ).record
            return decision_protocol.parse_or_fallback_decision(
                raw_output=result.stdout,
                trial_id=trial_id,
                agent=agent,
                summary=summary_record,
            ).record

        recommendation = policies.evaluate_summary(summary_record)
        return contracts.DecisionRecord(
            trial_id=trial_id,
            decision=recommendation.decision,
            confidence=0.75,
            reason=recommendation.reason,
            next_action=_decision_next_action(summary_record, recommendation.decision),
            evidence=recommendation.evidence,
            agent=contracts.AgentRef(
                provider=self.request.judge_provider,
                name="policy-judge",
                model=self.request.judge_model,
            ),
        )

    def _opencode_runtime(self) -> opencode_runtime.OpenCodeRuntimeAdapter:
        if self.dependencies.opencode_runtime is not None:
            return self.dependencies.opencode_runtime
        opencode_assets.copy_opencode_assets(self.request.train_root)
        return opencode_runtime.OpenCodeRuntimeAdapter(
            config=opencode_runtime.OpenCodeRuntimeConfig(
                project_root=self.request.train_root,
                attach_url=self.request.opencode_attach_url,
                binary=self.request.opencode_binary,
                model=self.request.judge_model,
                timeout_seconds=self.request.opencode_timeout_seconds,
                trace_sink=self._record_opencode_trace,
            )
        )

    def _record_opencode_trace(self, trace: opencode_runtime.OpenCodeTraceRecord) -> None:
        trace_root = self._opencode_trace_root(trace)
        trace_root.mkdir(parents=True, exist_ok=True)
        sequence = len(list(trace_root.glob("*.json"))) + 1
        stem = f"{sequence:04d}_{trace.command_name}"
        trace_path = trace_root / f"{stem}.json"
        raw_stdout_path = trace_root / f"{stem}.stdout.txt"
        raw_stderr_path = trace_root / f"{stem}.stderr.txt"
        storage.write_json_payload(trace_path, trace.to_dict())
        storage.write_text(raw_stdout_path, trace.stdout or "")
        storage.write_text(raw_stderr_path, trace.stderr or "")
        rendered = _render_opencode_trace(
            trace=trace,
            trace_path=trace_path,
            raw_stdout_path=raw_stdout_path,
            raw_stderr_path=raw_stderr_path,
        )
        storage.append_text(self.paths.opencode_log_file, rendered)
        writer = self.dependencies.console_writer
        if writer is not None:
            writer(rendered.rstrip())

    def _opencode_trace_root(self, trace: opencode_runtime.OpenCodeTraceRecord) -> Path:
        trial_id = _trace_trial_id(trace)
        if trial_id is None:
            return self.paths.study_opencode_trace_root
        return self.paths.trial_opencode_trace_root(trial_id)

    def _optuna_runtime(self) -> optuna_runtime.OptunaRuntimeAdapter:
        if self.dependencies.optuna_runtime is not None:
            return self.dependencies.optuna_runtime
        return optuna_runtime.OptunaRuntimeAdapter(
            config=optuna_runtime.OptunaRuntimeConfig(
                study_name=self.request.study_name,
                storage_path=self.paths.optuna_storage_file,
            )
        )

    def _optuna_available(self) -> bool:
        if self.dependencies.optuna_runtime is not None:
            return True
        return optimize.is_optuna_available()

    def _recent_result_summary_files(self, trial_id: str, recent_window: int) -> list[Path]:
        current_index = layout.parse_trial_id(trial_id)
        candidates = sorted(
            (
                trial_dir.name
                for trial_dir in self.paths.trials_root.glob("trial_*")
                if trial_dir.is_dir()
                and trial_dir.name != trial_id
                and layout.parse_trial_id(trial_dir.name) < current_index
                and self.paths.result_summary_file(trial_dir.name).exists()
            ),
            key=layout.parse_trial_id,
            reverse=True,
        )
        return [self.paths.result_summary_file(item) for item in candidates[:recent_window]]

    def _materialize_generator_override_file(
        self,
        *,
        trial_id: str,
        override_payload: dict[str, contracts.JsonValue] | None,
    ) -> Path | None:
        if not override_payload:
            return None
        path = self.paths.generator_override_file(trial_id)
        path.write_text(json.dumps(override_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path


def normalize_stage_name(stage: str) -> str:
    normalized = stage.strip().lower()
    if normalized in STAGE_ALIASES:
        return STAGE_ALIASES[normalized]
    upper = stage.strip().upper()
    if upper in state_machine.STAGES:
        return upper
    raise ValueError(f"unsupported stage: {stage}")


def _decision_next_action(summary_record: contracts.ResultSummaryRecord, decision: str) -> dict[str, contracts.JsonValue]:
    if decision == "REGENERATE_DATA":
        return {
            "dataset_action": "new_version",
            "train_action": "from_run",
            "base_run": summary_record.train_name,
        }
    if decision == "PROMOTE_BRANCH":
        return {"dataset_action": "freeze", "train_action": "promote"}
    if decision == "ABANDON_BRANCH":
        return {"dataset_action": "freeze", "train_action": "stop"}
    if decision == "RESUME":
        return {"dataset_action": "reuse", "train_action": "resume"}
    return {
        "dataset_action": "reuse",
        "train_action": "from_run",
        "base_run": summary_record.train_name,
    }


def _summary_with_extra_evidence(
    record: contracts.ResultSummaryRecord,
    extra_evidence: list[str],
) -> contracts.ResultSummaryRecord:
    return contracts.ResultSummaryRecord(
        study_name=record.study_name,
        task=record.task,
        trial_id=record.trial_id,
        dataset_version=record.dataset_version,
        train_name=record.train_name,
        primary_metric=record.primary_metric,
        primary_score=record.primary_score,
        test_metrics=record.test_metrics,
        evaluation_available=record.evaluation_available,
        evaluation_metrics=record.evaluation_metrics,
        failure_count=record.failure_count,
        trend=record.trend,
        delta_vs_previous=record.delta_vs_previous,
        delta_vs_best=record.delta_vs_best,
        weak_classes=record.weak_classes,
        failure_patterns=record.failure_patterns,
        recent_trials=record.recent_trials,
        best_trial=record.best_trial,
        evidence=[*record.evidence, *[item for item in extra_evidence if item.strip()]],
    )


def _study_status_with_extra_evidence(
    record: contracts.StudyStatusRecord,
    extra_evidence: list[str],
) -> contracts.StudyStatusRecord:
    return contracts.StudyStatusRecord(
        study_name=record.study_name,
        task=record.task,
        status=record.status,
        current_trial_id=record.current_trial_id,
        best_trial_id=record.best_trial_id,
        latest_decision=record.latest_decision,
        best_primary_score=record.best_primary_score,
        budget_pressure=record.budget_pressure,
        summary_cn=record.summary_cn,
        next_actions_cn=record.next_actions_cn,
        evidence=[*record.evidence, *[item for item in extra_evidence if item.strip()]],
        business_success_rate=record.business_success_rate,
        business_success_threshold=record.business_success_threshold,
        commercial_ready=record.commercial_ready,
        latest_gate_status=record.latest_gate_status,
        final_reason=record.final_reason,
        final_detail=record.final_detail,
    )


def _dataset_plan_with_extra_evidence(
    record: contracts.DatasetPlanRecord,
    extra_evidence: list[str],
) -> contracts.DatasetPlanRecord:
    return contracts.DatasetPlanRecord(
        study_name=record.study_name,
        task=record.task,
        trial_id=record.trial_id,
        dataset_action=record.dataset_action,
        boost_classes=record.boost_classes,
        focus_failure_patterns=record.focus_failure_patterns,
        rationale_cn=record.rationale_cn,
        evidence=[*record.evidence, *[item for item in extra_evidence if item.strip()]],
        generator_preset=record.generator_preset,
        generator_overrides=record.generator_overrides,
    )


def _retune_plan_with_extra_evidence(
    record: contracts.RetunePlanRecord,
    extra_evidence: list[str],
) -> contracts.RetunePlanRecord:
    return contracts.RetunePlanRecord(
        study_name=record.study_name,
        task=record.task,
        trial_id=record.trial_id,
        parameter_updates=record.parameter_updates,
        component_actions=record.component_actions,
        component_parameter_updates=record.component_parameter_updates,
        rationale_cn=record.rationale_cn,
        evidence=[*record.evidence, *[item for item in extra_evidence if item.strip()]],
    )


def _hydrate_result_summary_payload(
    payload: dict[str, contracts.JsonValue],
    *,
    fallback_record: contracts.ResultSummaryRecord,
) -> dict[str, contracts.JsonValue]:
    hydrated = dict(payload)
    fallback_payload = fallback_record.to_dict()
    for key in (
        "study_name",
        "task",
        "trial_id",
        "dataset_version",
        "train_name",
        "primary_metric",
        "primary_score",
        "test_metrics",
        "evaluation_available",
        "evaluation_metrics",
        "failure_count",
        "trend",
        "delta_vs_previous",
        "delta_vs_best",
        "weak_classes",
        "failure_patterns",
        "evidence",
    ):
        hydrated.setdefault(key, fallback_payload[key])

    hydrated["recent_trials"] = _hydrate_result_summary_snapshots(
        _as_mapping_list(hydrated.get("recent_trials")),
        fallback_record.recent_trials,
    )
    hydrated["best_trial"] = _hydrate_result_summary_snapshot(
        _as_optional_mapping(hydrated.get("best_trial")),
        fallback_record.best_trial,
    )
    return hydrated


def _hydrate_result_summary_snapshots(
    payload_items: list[dict[str, contracts.JsonValue]] | None,
    fallback_items: list[contracts.ResultSummarySnapshot],
) -> list[dict[str, contracts.JsonValue]]:
    if payload_items is None:
        return [item.to_dict() for item in fallback_items]
    fallback_by_trial = {item.trial_id: item for item in fallback_items}
    hydrated: list[dict[str, contracts.JsonValue]] = []
    for index, item in enumerate(payload_items):
        trial_id_value = item.get("trial_id")
        fallback_snapshot = None
        if isinstance(trial_id_value, str):
            fallback_snapshot = fallback_by_trial.get(trial_id_value)
        if fallback_snapshot is None and index < len(fallback_items):
            fallback_snapshot = fallback_items[index]
        hydrated.append(_hydrate_result_summary_snapshot(item, fallback_snapshot))
    return hydrated


def _hydrate_result_summary_snapshot(
    payload: dict[str, contracts.JsonValue] | None,
    fallback_snapshot: contracts.ResultSummarySnapshot | None,
) -> dict[str, contracts.JsonValue] | None:
    if payload is None:
        return None if fallback_snapshot is None else fallback_snapshot.to_dict()
    hydrated = dict(payload)
    if fallback_snapshot is None:
        return hydrated
    fallback_payload = fallback_snapshot.to_dict()
    for key in ("trial_id", "dataset_version", "train_name", "primary_score", "metrics", "decision"):
        hydrated.setdefault(key, fallback_payload[key])
    return hydrated


def _as_mapping_list(value: object) -> list[dict[str, contracts.JsonValue]] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        return None
    mappings: list[dict[str, contracts.JsonValue]] = []
    for item in value:
        if not isinstance(item, dict):
            return None
        mappings.append(item)
    return mappings


def _as_optional_mapping(value: object) -> dict[str, contracts.JsonValue] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        return None
    return value


def _trace_trial_id(trace: opencode_runtime.OpenCodeTraceRecord) -> str | None:
    if trace.command_name in {"judge-trial", "result-read", "plan-dataset", "plan-retune"} and len(trace.arguments) >= 3:
        return trace.arguments[2]
    return None


def _render_opencode_trace(
    *,
    trace: opencode_runtime.OpenCodeTraceRecord,
    trace_path: Path,
    raw_stdout_path: Path,
    raw_stderr_path: Path,
) -> str:
    trial_id = _trace_trial_id(trace)
    scope = trial_id or "study"
    lines = [
        f"=== OpenCode Trace: {trace.command_name} [{scope}] ===",
        f"time: {trace.created_at}",
        f"trace_file: {trace_path}",
        f"raw_stdout_file: {raw_stdout_path}",
        f"raw_stderr_file: {raw_stderr_path}",
        f"project_root: {trace.project_root}",
        f"model: {trace.model or '(default)'}",
        f"attach_url: {trace.attach_url or '(none)'}",
        f"arguments: {list(trace.arguments)}",
        f"command: {' '.join(trace.command)}",
        f"success: {trace.success}",
        f"returncode: {trace.returncode}",
    ]
    if trace.error_message:
        lines.append(f"error_message: {trace.error_message}")
    lines.append(f"--- command markdown: {trace.command_markdown_path} ---")
    if trace.command_markdown_error is not None:
        lines.append(f"(read_error: {trace.command_markdown_error})")
    elif trace.command_markdown_text is None:
        lines.append("(empty)")
    else:
        lines.append(trace.command_markdown_text)
        if trace.command_markdown_truncated:
            lines.append("(command markdown truncated)")
    if trace.skill_markdown_path is not None:
        lines.append(f"--- skill markdown: {trace.skill_markdown_path} ---")
        if trace.skill_markdown_error is not None:
            lines.append(f"(read_error: {trace.skill_markdown_error})")
        elif trace.skill_markdown_text is None:
            lines.append("(empty)")
        else:
            lines.append(trace.skill_markdown_text)
            if trace.skill_markdown_truncated:
                lines.append("(skill markdown truncated)")
    for attached in trace.attached_files:
        lines.append(f"--- attached file: {attached.path} ---")
        lines.append(f"exists: {attached.exists}")
        lines.append(f"size_bytes: {attached.size_bytes}")
        if attached.read_error is not None:
            lines.append(f"read_error: {attached.read_error}")
        elif attached.content_text is None:
            lines.append("(empty)")
        else:
            lines.append(attached.content_text)
            if attached.truncated:
                lines.append("(attached file content truncated)")
    stdout_text = trace.stdout or ""
    stderr_text = trace.stderr or ""
    lines.append("--- raw stdout ---")
    lines.append(stdout_text if stdout_text.strip() else "(empty)")
    lines.append("--- raw stderr ---")
    lines.append(stderr_text if stderr_text.strip() else "(empty)")
    lines.append("")
    return "\n".join(lines)


def _count_no_improve_trials(scores: list[float], min_delta: float) -> int:
    best_so_far: float | None = None
    no_improve = 0
    for score in scores:
        if best_so_far is None or score > best_so_far + min_delta:
            best_so_far = score
            no_improve = 0
        else:
            no_improve += 1
    return no_improve


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _string_value(payload: dict[str, contracts.JsonValue], key: str, default: str | None = None) -> str | None:
    value = payload.get(key, default)
    return value if isinstance(value, str) else default


def _optional_path(value: object) -> Path | None:
    if isinstance(value, str) and value.strip():
        return Path(value)
    return None


def _preferred_existing_checkpoint(best_path: Path | None, last_path: Path | None) -> Path | None:
    if best_path is not None and best_path.exists():
        return best_path
    if last_path is not None and last_path.exists():
        return last_path
    return None


def _checkpoint_text(path: Path | None) -> str:
    return str(path) if path is not None else "none"


def _gate_status(gate: object) -> str:
    if isinstance(gate, dict):
        raw_status = gate.get("status")
        if isinstance(raw_status, str) and raw_status.strip():
            return raw_status.strip()
    return "missing"


def _string_action(payload: dict[str, contracts.JsonValue], key: str, default: str) -> str:
    value = payload.get(key)
    if isinstance(value, str) and value.strip():
        return value
    return default


def _int_value(payload: dict[str, contracts.JsonValue], key: str, default: int | None = None) -> int | None:
    value = payload.get(key, default)
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return default


def _float_like(value: object, default: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _string_like(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _summary_int(value: object, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return default


def _embedder_summary_epoch(value: object) -> int | None:
    if not isinstance(value, dict):
        return None
    epoch = value.get("epoch")
    if isinstance(epoch, bool):
        return None
    if isinstance(epoch, int):
        return epoch
    if isinstance(epoch, float):
        return int(epoch)
    return None


def _embedder_review_for_epoch(review_history: list[object], epoch: int) -> dict[str, object] | None:
    for item in reversed(review_history):
        if not isinstance(item, dict):
            continue
        if _embedder_summary_epoch(item) == epoch:
            return item
    return None


def _replace_embedder_review_for_epoch(
    review_history: list[object],
    epoch: int,
    replacement: dict[str, object],
) -> list[dict[str, object]]:
    updated: list[dict[str, object]] = []
    replaced = False
    for item in review_history:
        if not isinstance(item, dict):
            continue
        if _embedder_summary_epoch(item) == epoch:
            updated.append(replacement)
            replaced = True
        else:
            updated.append(item)
    if not replaced:
        updated.append(replacement)
    return updated


def _embedder_review_record_from_payload(
    payload: dict[str, object],
    *,
    default_stage: str,
    default_epoch: int,
) -> embedder_review_protocol.EmbedderReviewRecord:
    agent_payload = payload.get("agent")
    if isinstance(agent_payload, dict):
        agent = contracts.AgentRef.from_dict(_json_object(agent_payload))
    else:
        agent = contracts.AgentRef(provider="opencode", name="review-embedder", model=None)
    next_action = payload.get("next_action")
    evidence = payload.get("evidence")
    return embedder_review_protocol.EmbedderReviewRecord(
        stage=str(payload.get("stage") or default_stage),
        epoch=_summary_int(payload.get("epoch"), default_epoch),
        decision=str(payload.get("decision") or embedder_review_protocol.EMBEDDER_REVIEW_DECISION_CONTINUE),
        confidence=_float_like(payload.get("confidence"), 0.0),
        reason=str(payload.get("reason") or "existing_review"),
        next_action=_json_object(next_action) if isinstance(next_action, dict) else {},
        evidence=[str(item) for item in evidence] if isinstance(evidence, list) else [],
        agent=agent,
        used_fallback=bool(payload.get("used_fallback", False)),
        fallback_reason=_string_like(payload.get("fallback_reason")),
    )


def _json_object(payload: dict[str, object]) -> dict[str, contracts.JsonValue]:
    return {str(key): value for key, value in payload.items()}


def _recent_embedder_history(history: list[object], window: int) -> list[dict[str, contracts.JsonValue]]:
    recent: list[dict[str, contracts.JsonValue]] = []
    for item in history[-max(1, window) :]:
        if isinstance(item, dict):
            recent.append(_json_object(item))
    return recent


def _best_embedder_epoch_from_history(history: list[object]) -> tuple[int | None, float | None]:
    best_epoch: int | None = None
    best_score: float | None = None
    for item in history:
        if not isinstance(item, dict):
            continue
        epoch = _embedder_summary_epoch(item)
        if epoch is None:
            continue
        score = _float_like(
            item.get("embedding_scene_recall_at_1"),
            default=_float_like(
                item.get("embedding_identity_recall_at_1"),
                default=_float_like(item.get("embedding_recall_at_1"), default=-1.0),
            ),
        )
        if best_score is None or score > best_score:
            best_epoch = epoch
            best_score = score
    return best_epoch, best_score


def _infer_dataset_preset(dataset_version: str) -> str:
    version = dataset_version.strip()
    if "_r" in version:
        version = version.split("_r", 1)[0]
    if version in {"smoke", "firstpass", "v1", "hard"}:
        return version
    return "firstpass"


def _group1_component_role(component: str) -> str:
    return {
        QUERY_COMPONENT: "query_detector",
        PROPOSAL_COMPONENT: "proposal_detector",
        EMBEDDER_COMPONENT: "icon_embedder",
    }.get(component, component)


def _summary_metric(summary_record: contracts.ResultSummaryRecord, key: str) -> float | None:
    for metrics in (summary_record.evaluation_metrics, summary_record.test_metrics):
        value = metrics.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _offline_ranking_score(summary_record: contracts.ResultSummaryRecord) -> float:
    if summary_record.task == "group1":
        full_sequence_hit_rate = _summary_metric(summary_record, "full_sequence_hit_rate") or 0.0
        single_target_hit_rate = _summary_metric(summary_record, "single_target_hit_rate") or 0.0
        order_error_rate = _summary_metric(summary_record, "order_error_rate")
        order_quality = 0.0 if order_error_rate is None else max(0.0, min(1.0, 1.0 - order_error_rate))
        center_error = _summary_metric(summary_record, "mean_center_error_px")
        center_quality = 1.0 if center_error is None else max(0.0, min(1.0, 1.0 - (center_error / 20.0)))
        return (
            (full_sequence_hit_rate * 0.55)
            + (single_target_hit_rate * 0.25)
            + (order_quality * 0.15)
            + (center_quality * 0.05)
        )
    point_hit_rate = _summary_metric(summary_record, "point_hit_rate") or 0.0
    mean_iou = _summary_metric(summary_record, "mean_iou") or 0.0
    center_error = _summary_metric(summary_record, "mean_center_error_px")
    center_quality = 0.0 if center_error is None else max(
        0.0,
        min(1.0, 1.0 - (center_error / GROUP2_LOCALIZATION_ALERT_CENTER_ERROR_PX)),
    )
    return (point_hit_rate * 0.50) + (mean_iou * 0.30) + (center_quality * 0.20)


def _difficulty_score_for_trial(*, dataset_version: str, dataset_preset: str | None) -> float:
    preset = dataset_preset or _infer_dataset_preset(dataset_version)
    preset_weight = {
        "smoke": 0.85,
        "firstpass": 1.0,
        "v1": 1.0,
        "hard": 1.12,
    }.get(preset, 1.0)
    retune_depth = len(re.findall(r"_r\d+", dataset_version))
    return preset_weight + min(retune_depth * 0.02, 0.08)


def _composite_ranking_score(
    *,
    offline_score: float,
    difficulty_score: float,
    business_success_rate: float | None,
    commercial_ready: bool | None,
) -> float:
    business_component = 0.0
    if business_success_rate is not None:
        business_component = business_success_rate * 0.75
    if commercial_ready:
        business_component += 0.25
    return (offline_score * difficulty_score * 0.8) + (business_component * 2.0)
