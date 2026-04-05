from __future__ import annotations

import tempfile
import types
import unittest
from pathlib import Path

from core.auto_train import contracts, optimize, optuna_runtime


class _FakeDistribution:
    def __init__(self, choices: list[contracts.JsonValue]) -> None:
        self.choices = list(choices)


class _FakeFrozenTrial:
    def __init__(
        self,
        *,
        number: int | None = None,
        params: dict[str, contracts.JsonValue] | None = None,
        distributions: dict[str, object] | None = None,
        value: float | None = None,
        user_attrs: dict[str, contracts.JsonValue] | None = None,
        state: str = "COMPLETE",
    ) -> None:
        self.number = number
        self.params = {} if params is None else dict(params)
        self.distributions = {} if distributions is None else dict(distributions)
        self.value = value
        self.user_attrs = {} if user_attrs is None else dict(user_attrs)
        self.state = state

    def set_user_attr(self, key: str, value: contracts.JsonValue) -> None:
        self.user_attrs[key] = value


class _FakeStudy:
    def __init__(self, *, study_name: str) -> None:
        self.study_name = study_name
        self.trials: list[_FakeFrozenTrial] = []

    def add_trial(self, trial: _FakeFrozenTrial) -> None:
        if trial.number is None:
            trial.number = len(self.trials)
        self.trials.append(trial)

    def ask(self, fixed_distributions: dict[str, object] | None = None) -> _FakeFrozenTrial:
        params: dict[str, contracts.JsonValue] = {}
        distributions = {} if fixed_distributions is None else dict(fixed_distributions)
        for name, distribution in distributions.items():
            params[name] = distribution.choices[-1]
        trial = _FakeFrozenTrial(
            number=len(self.trials),
            params=params,
            distributions=distributions,
            state="RUNNING",
        )
        self.trials.append(trial)
        return trial

    def tell(
        self,
        trial: int | _FakeFrozenTrial,
        values: float | None = None,
        state: str | None = None,
        skip_if_finished: bool = False,
    ) -> _FakeFrozenTrial:
        trial_number = trial if isinstance(trial, int) else trial.number
        if trial_number is None:
            raise AssertionError("trial number missing")
        record = self.trials[trial_number]
        if record.state == "COMPLETE" and skip_if_finished:
            return record
        record.value = values
        record.state = "COMPLETE" if state is None else state
        return record

    def get_trials(
        self,
        deepcopy: bool = True,
        states: object | None = None,
    ) -> list[_FakeFrozenTrial]:
        return list(self.trials)


class _FakeOptunaModule:
    def __init__(self) -> None:
        self._studies: dict[tuple[str, str], _FakeStudy] = {}
        self.distributions = types.SimpleNamespace(CategoricalDistribution=_FakeDistribution)
        self.trial = types.SimpleNamespace(
            create_trial=self._create_trial,
            TrialState=types.SimpleNamespace(COMPLETE="COMPLETE"),
        )

    def create_study(
        self,
        *,
        storage: str,
        study_name: str,
        direction: str,
        load_if_exists: bool,
    ) -> _FakeStudy:
        key = (storage, study_name)
        study = self._studies.get(key)
        if study is None:
            study = _FakeStudy(study_name=study_name)
            self._studies[key] = study
        return study

    @staticmethod
    def _create_trial(
        *,
        state: str = "COMPLETE",
        value: float | None = None,
        values: object | None = None,
        params: dict[str, contracts.JsonValue] | None = None,
        distributions: dict[str, object] | None = None,
        user_attrs: dict[str, contracts.JsonValue] | None = None,
        system_attrs: dict[str, object] | None = None,
        intermediate_values: dict[int, float] | None = None,
    ) -> _FakeFrozenTrial:
        del values, system_attrs, intermediate_values
        return _FakeFrozenTrial(
            params=params,
            distributions=distributions,
            value=value,
            user_attrs=user_attrs,
            state=state,
        )


def _group1_summary(*, trial_id: str, train_name: str, score: float) -> contracts.ResultSummaryRecord:
    return contracts.ResultSummaryRecord(
        study_name="study_001",
        task="group1",
        trial_id=trial_id,
        dataset_version="firstpass",
        train_name=train_name,
        primary_metric="map50_95",
        primary_score=score,
        test_metrics={"map50_95": score, "recall": 0.86},
        evaluation_available=False,
        evaluation_metrics={},
        failure_count=2,
        trend="plateau",
        delta_vs_previous=0.0,
        delta_vs_best=-0.01,
        weak_classes=[],
        failure_patterns=["detection_recall"],
        recent_trials=[],
        best_trial=None,
        evidence=["summary"],
    )


def _trial_input(
    *,
    trial_id: str,
    train_name: str,
    params: dict[str, contracts.JsonValue] | None = None,
) -> contracts.TrialInputRecord:
    return contracts.TrialInputRecord(
        trial_id=trial_id,
        task="group1",
        dataset_version="firstpass",
        train_name=train_name,
        train_mode="from_run",
        base_run="trial_0001",
        params={
            "model": "yolo26n.pt",
            "epochs": 120,
            "batch": 16,
            "imgsz": 640,
            "device": "0",
            **({} if params is None else params),
        },
    )


class OptunaRuntimeAdapterTests(unittest.TestCase):
    def test_suggest_next_parameters_imports_completed_trial_then_asks_new_trial(self) -> None:
        fake_optuna = _FakeOptunaModule()
        runtime = optuna_runtime.OptunaRuntimeAdapter(
            config=optuna_runtime.OptunaRuntimeConfig(
                study_name="study_001",
                storage_path=Path("/tmp/study_001.optuna.sqlite3"),
            ),
            module_loader=lambda _: fake_optuna,
        )
        plan = optimize.build_optimization_plan(
            summary=_group1_summary(trial_id="trial_0001", train_name="trial_0001", score=0.81),
            decision=contracts.DecisionRecord(
                trial_id="trial_0001",
                decision="RETUNE",
                confidence=0.82,
                reason="retune",
                next_action={"dataset_action": "reuse", "train_action": "from_run", "base_run": "trial_0001"},
                evidence=["judge"],
                agent=contracts.AgentRef(provider="opencode", name="judge-trial", model="gemma4"),
            ),
            optuna_available=True,
        )

        suggestion = runtime.suggest_next_parameters(
            plan=plan,
            completed_input=_trial_input(trial_id="trial_0001", train_name="trial_0001"),
            summary=_group1_summary(trial_id="trial_0001", train_name="trial_0001", score=0.81),
            next_trial_id="trial_0002",
        )

        self.assertEqual(
            suggestion.params,
            {"model": "yolo26s.pt", "epochs": 160, "batch": 16, "imgsz": 640},
        )
        self.assertFalse(suggestion.reused_existing)
        study = fake_optuna.create_study(
            storage=runtime.config.storage_url,
            study_name="study_001",
            direction="maximize",
            load_if_exists=True,
        )
        self.assertEqual(len(study.trials), 2)
        self.assertEqual(study.trials[0].user_attrs["sinan_trial_id"], "trial_0001")
        self.assertEqual(study.trials[0].value, 0.81)
        self.assertEqual(study.trials[1].user_attrs["sinan_trial_id"], "trial_0002")
        self.assertEqual(study.trials[1].state, "RUNNING")

    def test_suggest_next_parameters_reuses_existing_pending_trial(self) -> None:
        fake_optuna = _FakeOptunaModule()
        runtime = optuna_runtime.OptunaRuntimeAdapter(
            config=optuna_runtime.OptunaRuntimeConfig(
                study_name="study_001",
                storage_path=Path("/tmp/study_001.optuna.sqlite3"),
            ),
            module_loader=lambda _: fake_optuna,
        )
        plan = optimize.build_optimization_plan(
            summary=_group1_summary(trial_id="trial_0001", train_name="trial_0001", score=0.81),
            decision=contracts.DecisionRecord(
                trial_id="trial_0001",
                decision="RETUNE",
                confidence=0.82,
                reason="retune",
                next_action={"dataset_action": "reuse", "train_action": "from_run", "base_run": "trial_0001"},
                evidence=["judge"],
                agent=contracts.AgentRef(provider="opencode", name="judge-trial", model="gemma4"),
            ),
            optuna_available=True,
        )
        completed = _trial_input(trial_id="trial_0001", train_name="trial_0001")
        summary_record = _group1_summary(trial_id="trial_0001", train_name="trial_0001", score=0.81)

        first = runtime.suggest_next_parameters(
            plan=plan,
            completed_input=completed,
            summary=summary_record,
            next_trial_id="trial_0002",
        )
        second = runtime.suggest_next_parameters(
            plan=plan,
            completed_input=completed,
            summary=summary_record,
            next_trial_id="trial_0002",
        )

        self.assertEqual(first.trial_number, second.trial_number)
        self.assertTrue(second.reused_existing)
        study = fake_optuna.create_study(
            storage=runtime.config.storage_url,
            study_name="study_001",
            direction="maximize",
            load_if_exists=True,
        )
        self.assertEqual(len(study.trials), 2)

    def test_suggest_next_parameters_tells_existing_optuna_trial_before_asking_next(self) -> None:
        fake_optuna = _FakeOptunaModule()
        runtime = optuna_runtime.OptunaRuntimeAdapter(
            config=optuna_runtime.OptunaRuntimeConfig(
                study_name="study_001",
                storage_path=Path("/tmp/study_001.optuna.sqlite3"),
            ),
            module_loader=lambda _: fake_optuna,
        )
        plan = optimize.build_optimization_plan(
            summary=_group1_summary(trial_id="trial_0001", train_name="trial_0001", score=0.81),
            decision=contracts.DecisionRecord(
                trial_id="trial_0001",
                decision="RETUNE",
                confidence=0.82,
                reason="retune",
                next_action={"dataset_action": "reuse", "train_action": "from_run", "base_run": "trial_0001"},
                evidence=["judge"],
                agent=contracts.AgentRef(provider="opencode", name="judge-trial", model="gemma4"),
            ),
            optuna_available=True,
        )

        first = runtime.suggest_next_parameters(
            plan=plan,
            completed_input=_trial_input(trial_id="trial_0001", train_name="trial_0001"),
            summary=_group1_summary(trial_id="trial_0001", train_name="trial_0001", score=0.81),
            next_trial_id="trial_0002",
        )
        second_input = _trial_input(
            trial_id="trial_0002",
            train_name="trial_0002",
            params={optuna_runtime.OPTUNA_TRIAL_NUMBER_KEY: first.trial_number},
        )

        runtime.suggest_next_parameters(
            plan=plan,
            completed_input=second_input,
            summary=_group1_summary(trial_id="trial_0002", train_name="trial_0002", score=0.85),
            next_trial_id="trial_0003",
        )

        study = fake_optuna.create_study(
            storage=runtime.config.storage_url,
            study_name="study_001",
            direction="maximize",
            load_if_exists=True,
        )
        self.assertEqual(study.trials[1].state, "COMPLETE")
        self.assertEqual(study.trials[1].value, 0.85)
        self.assertEqual(study.trials[2].user_attrs["sinan_trial_id"], "trial_0003")


if __name__ == "__main__":
    unittest.main()
