"""Stage-driven autonomous-training controller skeleton."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import os
from pathlib import Path

from core.auto_train import (
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
from core.train.base import default_dataset_config, default_report_dir

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
    point_tolerance_px: int = 12
    iou_threshold: float = 0.5

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
        if max_steps <= 0:
            raise ValueError("max_steps must be greater than 0")

        study = self._load_or_create_study()
        trial_id = self._ensure_current_trial(study)
        current_stage = normalize_stage_name(force_stage) if force_stage is not None else self._current_stage(trial_id)
        executed: list[StageExecution] = []

        for _ in range(max_steps):
            if current_stage == "STOP":
                break
            execution = self._run_stage(current_stage)
            executed.append(execution)
            current_stage = execution.next_stage

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
        result = self.dependencies.test_runner(
            runners.test.TestRunnerRequest(
                task=self.request.task,
                train_root=self.request.train_root,
                dataset_version=input_record.dataset_version,
                train_name=input_record.train_name,
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
        leaderboard = self._update_leaderboard(summary_record, decision)
        plan_record = self._dataset_plan_record(summary_record=summary_record, decision=decision, leaderboard=leaderboard)
        if plan_record is not None:
            storage.write_dataset_plan_record(self.paths.dataset_plan_file(trial_id), plan_record)
        storage.append_decision_history(self.paths.decisions_file, decision)
        self._write_study_summary(study, leaderboard, decision)

        if decision.decision in {"PROMOTE_BRANCH", "ABANDON_BRANCH"}:
            updated = self._with_study_updates(
                study,
                status="completed",
                current_trial_id=trial_id,
                best_trial_id=leaderboard.best_entry.trial_id if leaderboard.best_entry is not None else study.best_trial_id,
            )
            storage.write_study_record(self.paths.study_file, updated)
            return StageExecution(trial_id=trial_id, stage="NEXT_ACTION", next_stage="STOP", detail=decision.decision)

        dataset_action = plan_record.dataset_action if plan_record is not None else _string_action(
            decision.next_action,
            "dataset_action",
            "reuse",
        )
        stop_decision = self._evaluate_stop(
            study,
            leaderboard,
            pending_new_dataset=(dataset_action == "new_version"),
        )
        if stop_decision.should_stop:
            updated = self._with_study_updates(
                study,
                status="stopped",
                current_trial_id=trial_id,
                best_trial_id=leaderboard.best_entry.trial_id if leaderboard.best_entry is not None else study.best_trial_id,
            )
            storage.write_study_record(self.paths.study_file, updated)
            return StageExecution(
                trial_id=trial_id,
                stage="NEXT_ACTION",
                next_stage="STOP",
                detail=stop_decision.reason,
            )

        next_trial = self._prepare_next_trial(summary_record, decision, plan_record)
        storage.write_trial_input_record(self.paths.input_file(next_trial.trial_id), next_trial)
        storage.append_trial_history(self.paths.trial_history_file, next_trial)
        updated = self._with_study_updates(
            study,
            status="running",
            current_trial_id=next_trial.trial_id,
            best_trial_id=leaderboard.best_entry.trial_id if leaderboard.best_entry is not None else study.best_trial_id,
        )
        storage.write_study_record(self.paths.study_file, updated)
        return StageExecution(
            trial_id=trial_id,
            stage="NEXT_ACTION",
            next_stage="PLAN",
            detail=next_trial.trial_id,
        )

    def _load_or_create_study(self) -> contracts.StudyRecord:
        if self.paths.study_file.exists():
            record = storage.read_study_record(self.paths.study_file)
            if record.started_at is None:
                record = self._with_study_updates(record)
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
            started_at=self._now_utc().isoformat(),
            current_trial_id=None,
            best_trial_id=None,
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

    def _current_stage(self, trial_id: str) -> str:
        trial_dir = self.paths.ensure_trial_dir(trial_id)
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
        next_index = layout.parse_trial_id(next_trial_id)
        dataset_action = plan_record.dataset_action if plan_record is not None else _string_action(decision.next_action, "dataset_action", "reuse")
        train_action = _string_action(decision.next_action, "train_action", "from_run")
        if dataset_action == "new_version":
            dataset_version = f"{previous_input.dataset_version}_r{next_index:04d}"
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
        elif train_action == "fresh":
            train_mode = "fresh"
            train_name = next_trial_id
            base_run = None
        else:
            train_mode = "from_run"
            train_name = next_trial_id
            base_run = _string_action(decision.next_action, "base_run", previous_input.train_name)

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
    ) -> contracts.LeaderboardRecord:
        metrics = dict(summary_record.test_metrics)
        for key, value in summary_record.evaluation_metrics.items():
            metrics[key] = value
        entry = contracts.LeaderboardEntry(
            trial_id=summary_record.trial_id,
            dataset_version=summary_record.dataset_version,
            train_name=summary_record.train_name,
            primary_score=summary_record.primary_score or 0.0,
            metrics=metrics,
            decision=decision.decision,
        )
        if self.paths.leaderboard_file.exists():
            leaderboard = storage.read_leaderboard_record(self.paths.leaderboard_file)
            entries = [item for item in leaderboard.entries if item.trial_id != entry.trial_id]
            entries.append(entry)
        else:
            entries = [entry]
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
        return record

    def _evaluate_stop(
        self,
        study: contracts.StudyRecord,
        leaderboard: contracts.LeaderboardRecord,
        *,
        pending_new_dataset: bool,
    ) -> stop_rules.StopDecision:
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
            plateau_window=policy.plateau_window,
            min_delta=policy.min_delta,
            max_no_improve_trials=self.request.max_no_improve_trials,
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
    ) -> None:
        record = self._study_status_record(study=study, leaderboard=leaderboard, decision=decision)
        storage.write_study_status_record(self.paths.study_status_file, record)
        self.paths.summary_file.write_text(study_status.markdown_from_study_status(record), encoding="utf-8")

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
            return contracts.ResultSummaryRecord.from_dict(payload)
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
    ) -> contracts.StudyStatusRecord:
        fallback_record = study_status.build_study_status(study=study, leaderboard=leaderboard, decision=decision)
        if self.request.judge_provider != "opencode":
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
        trace_path = trace_root / f"{sequence:04d}_{trace.command_name}.json"
        storage.write_json_payload(trace_path, trace.to_dict())
        rendered = _render_opencode_trace(trace=trace, trace_path=trace_path)
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


def _trace_trial_id(trace: opencode_runtime.OpenCodeTraceRecord) -> str | None:
    if trace.command_name in {"judge-trial", "result-read", "plan-dataset"} and len(trace.arguments) >= 3:
        return trace.arguments[2]
    return None


def _render_opencode_trace(
    *,
    trace: opencode_runtime.OpenCodeTraceRecord,
    trace_path: Path,
) -> str:
    trial_id = _trace_trial_id(trace)
    scope = trial_id or "study"
    lines = [
        f"=== OpenCode Trace: {trace.command_name} [{scope}] ===",
        f"time: {trace.created_at}",
        f"trace_file: {trace_path}",
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
    lines.append("--- stdout ---")
    lines.append(stdout_text if stdout_text.strip() else "(empty)")
    lines.append("--- stderr ---")
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
