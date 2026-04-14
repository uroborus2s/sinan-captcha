from __future__ import annotations

import unittest

from auto_train import contracts, dataset_plan


def _summary(*, dataset_version: str, task: str = "group1") -> contracts.ResultSummaryRecord:
    return contracts.ResultSummaryRecord(
        study_name="study_001",
        task=task,
        trial_id="trial_0001",
        dataset_version=dataset_version,
        train_name="trial_0001",
        primary_metric="full_sequence_hit_rate" if task == "group1" else "point_hit_rate",
        primary_score=0.8,
        test_metrics={"full_sequence_hit_rate": 0.8} if task == "group1" else {"point_hit_rate": 0.8},
        evaluation_available=False,
        evaluation_metrics={},
        failure_count=None,
        trend="baseline",
        delta_vs_previous=None,
        delta_vs_best=None,
        weak_classes=[],
        failure_patterns=[],
        recent_trials=[],
        best_trial=None,
        evidence=["test"],
    )


def _decision() -> contracts.DecisionRecord:
    return contracts.DecisionRecord(
        trial_id="trial_0001",
        decision="REGENERATE_DATA",
        confidence=0.8,
        reason="need_more_data",
        next_action={"dataset_action": "new_version", "train_action": "fresh"},
        evidence=["test"],
        agent=contracts.AgentRef(provider="rules", name="policy-judge", model="policy-v1"),
    )


class DatasetPlanTests(unittest.TestCase):
    def test_smoke_regeneration_promotes_to_v1_preset(self) -> None:
        plan = dataset_plan.build_dataset_plan(summary=_summary(dataset_version="smoke"), decision=_decision())

        self.assertEqual(plan.generator_preset, "v1")
        self.assertEqual(plan.generator_overrides["project"]["sample_count"], 10000)

    def test_group1_v1_plan_keeps_fixed_three_targets(self) -> None:
        plan = dataset_plan.build_dataset_plan(summary=_summary(dataset_version="v1"), decision=_decision())

        self.assertEqual(plan.generator_preset, "v1")
        self.assertEqual(plan.generator_overrides["project"]["sample_count"], 10000)
        self.assertEqual(plan.generator_overrides["sampling"]["target_count_min"], 3)
        self.assertEqual(plan.generator_overrides["sampling"]["target_count_max"], 3)


if __name__ == "__main__":
    unittest.main()
