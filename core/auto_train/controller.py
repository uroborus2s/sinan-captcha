"""Stage-driven autonomous-training controller skeleton."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil

from core.auto_train import (
    business_eval,
    contracts,
    dataset_plan,
    decision_protocol,
    json_extract,
    layout,
    opencode_runtime,
    optimize,
    optuna_runtime,
    policies,
    runners,
    state_machine,
    stop_rules,
    storage,
    study_status,
    summary,
)
from core.train.base import default_dataset_config, default_report_dir, default_run_dir

DEFAULT_JUDGE_PROVIDER = "rules"
DEFAULT_JUDGE_MODEL = "policy-v1"


def default_generator_executable() -> str:
    if os.name == "nt":
        return "sinan-generator.exe"
    return "sinan-generator"

STAGE_ALIASES = {
    "plan": "PLAN",
    "build-dataset": "BUILD_DATASET",
    "train": "TRAIN",
    "test": "TEST",
    "evaluate": "EVALUATE",
    "summarize": "SUMMARIZE",
    "judge": "JUDGE",
    "next-action": "NEXT_ACTION",
    "stop": "STOP",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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

    def run(self, *, max_steps: int = 1, force_stage: str | None = None) -> AutoTrainRunResult:
        if max_steps < 0:
            raise ValueError("max_steps must not be negative")

        study = self._load_or_create_study()
        trial_id = self._ensure_current_trial(study)
        current_stage = normalize_stage_name(force_stage) if force_stage is not None else self._current_stage(study, trial_id)
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
        return self._run_stage(normalize_stage_name(stage))

    def _run_stage(self, stage: str) -> StageExecution:
        study = self._load_or_create_study()
        trial_id = self._ensure_current_trial(study)
        if stage == "PLAN":
            return self._stage_plan(trial_id)
        if stage == "BUILD_DATASET":
            return self._stage_build_dataset(trial_id)
        if stage == "TRAIN":
            return self._stage_train(trial_id)
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
            next_stage=state_machine.next_stage("PLAN"),
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
            next_stage=state_machine.next_stage("BUILD_DATASET"),
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
            next_stage=state_machine.next_stage("TRAIN"),
            detail=result.command,
        )

    def _stage_test(self, trial_id: str) -> StageExecution:
        input_record = storage.read_trial_input_record(self.paths.input_file(trial_id))
        model_path = self._resolve_test_model_path(trial_id, input_record.train_name)
        result = self.dependencies.test_runner(
            runners.test.TestRunnerRequest(
                task=self.request.task,
                train_root=self.request.train_root,
                dataset_version=input_record.dataset_version,
                train_name=input_record.train_name,
                model_path=model_path,
                imgsz=_int_value(input_record.params, "imgsz", default=self.request.effective_imgsz),
                device=_string_value(input_record.params, "device", default=self.request.device) or self.request.device,
            )
        )
        storage.write_test_record(self.paths.test_file(trial_id), result.record)
        return StageExecution(
            trial_id=trial_id,
            stage="TEST",
            next_stage=state_machine.next_stage("TEST"),
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
        return StageExecution(
            trial_id=trial_id,
            stage="EVALUATE",
            next_stage=state_machine.next_stage("EVALUATE"),
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
        self._write_trial_summary(record, None)
        return StageExecution(
            trial_id=trial_id,
            stage="SUMMARIZE",
            next_stage=state_machine.next_stage("SUMMARIZE"),
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
            next_stage=state_machine.next_stage("JUDGE"),
            detail=decision.decision,
        )

    def _stage_next_action(self, trial_id: str) -> StageExecution:
        summary_record = storage.read_result_summary_record(self.paths.result_summary_file(trial_id))
        decision = storage.read_decision_record(self.paths.decision_file(trial_id))
        study = self._load_or_create_study()

        business_record = self._run_business_eval_if_needed(
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
        if plan_record is not None:
            storage.write_dataset_plan_record(self.paths.dataset_plan_file(trial_id), plan_record)
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

        next_trial = self._prepare_next_trial(summary_record, effective_decision, plan_record)
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
        stage = state_machine.infer_resume_stage(trial_dir, stop_file=self.paths.stop_file)
        if stage in {"TRAIN", "TEST"}:
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
        if decision.decision == "RETUNE":
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

    def _resolve_test_model_path(self, trial_id: str, train_name: str) -> Path | None:
        train_path = self.paths.train_file(trial_id)
        if not train_path.exists():
            return None
        train_record = storage.read_train_record(train_path)
        best_path = Path(train_record.best_weights)
        if best_path.exists():
            return best_path
        last_path = Path(train_record.last_weights)
        if last_path.exists():
            return last_path
        return best_path

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

        request = runners.business_eval.BusinessEvalRunnerRequest(
            trial_id=trial_id,
            task=self.request.task,
            train_root=self.request.train_root,
            dataset_version=summary_record.dataset_version,
            train_name=summary_record.train_name,
            cases_root=Path(config.cases_root),
            report_dir=self.paths.business_eval_root(trial_id),
            device=self.request.device,
            imgsz=self.request.effective_imgsz,
            success_threshold=config.success_threshold,
            min_cases=config.min_cases,
            sample_size=config.sample_size,
            point_tolerance_px=config.point_tolerance_px,
            iou_threshold=config.iou_threshold,
        )
        try:
            result = self.dependencies.business_eval_runner(request)
        except runners.RunnerExecutionError as exc:
            return contracts.BusinessEvalRecord(
                trial_id=trial_id,
                task=self.request.task,
                train_name=summary_record.train_name,
                cases_root=config.cases_root,
                available_cases=0,
                total_cases=0,
                passed_cases=0,
                success_rate=0.0,
                success_threshold=config.success_threshold,
                min_cases=config.min_cases,
                sample_size=config.sample_size,
                commercial_ready=False,
                point_tolerance_px=config.point_tolerance_px,
                iou_threshold=config.iou_threshold,
                sampled_source=str(self.paths.business_eval_root(trial_id) / "_sampled_source" / "labels.jsonl"),
                report_dir=str(self.paths.business_eval_root(trial_id)),
                prediction_dir=str(self.paths.business_eval_root(trial_id) / "modeltest"),
                evaluation_report_dir=str(self.paths.business_eval_root(trial_id) / "evaluation"),
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
            files.extend(path for path in (self.paths.leaderboard_file, self.paths.decisions_file) if path.exists())
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
    if trace.command_name in {"judge-trial", "result-read", "plan-dataset"} and len(trace.arguments) >= 3:
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


def _infer_dataset_preset(dataset_version: str) -> str:
    version = dataset_version.strip()
    if "_r" in version:
        version = version.split("_r", 1)[0]
    if version in {"smoke", "firstpass", "hard"}:
        return version
    return "firstpass"


def _summary_metric(summary_record: contracts.ResultSummaryRecord, key: str) -> float | None:
    for metrics in (summary_record.evaluation_metrics, summary_record.test_metrics):
        value = metrics.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _offline_ranking_score(summary_record: contracts.ResultSummaryRecord) -> float:
    point_hit_rate = _summary_metric(summary_record, "point_hit_rate") or 0.0
    mean_iou = _summary_metric(summary_record, "mean_iou") or 0.0
    center_error = _summary_metric(summary_record, "mean_center_error_px")
    center_quality = 0.0 if center_error is None else max(0.0, min(1.0, 1.0 - (center_error / 12.0)))
    return (point_hit_rate * 0.50) + (mean_iou * 0.30) + (center_quality * 0.20)


def _difficulty_score_for_trial(*, dataset_version: str, dataset_preset: str | None) -> float:
    preset = dataset_preset or _infer_dataset_preset(dataset_version)
    preset_weight = {
        "smoke": 0.85,
        "firstpass": 1.0,
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
