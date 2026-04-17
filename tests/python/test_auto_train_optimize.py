from __future__ import annotations

import unittest

from auto_train import contracts, optimize


def _decision(decision: str = "RETUNE", *, base_run: str = "trial_0003") -> contracts.DecisionRecord:
    return contracts.DecisionRecord(
        trial_id="trial_0004",
        decision=decision,
        confidence=0.82,
        reason="judge_output",
        next_action={
            "dataset_action": "reuse",
            "train_action": "from_run",
            "base_run": base_run,
        },
        evidence=["judge"],
        agent=contracts.AgentRef(provider="opencode", name="judge-trial", model="gemma4"),
    )


def _group1_summary(
    *,
    primary_score: float = 0.81,
    single_target_hit_rate: float = 0.92,
    full_sequence_hit_rate: float = 0.82,
    trend: str = "plateau",
    delta_vs_best: float | None = -0.01,
    weak_classes: list[str] | None = None,
    failure_patterns: list[str] | None = None,
    failure_count: int | None = 3,
) -> contracts.ResultSummaryRecord:
    return contracts.ResultSummaryRecord(
        study_name="study_001",
        task="group1",
        trial_id="trial_0004",
        dataset_version="v4",
        train_name="trial_0004",
        primary_metric="full_sequence_hit_rate",
        primary_score=primary_score,
        test_metrics={
            "single_target_hit_rate": single_target_hit_rate,
            "full_sequence_hit_rate": full_sequence_hit_rate,
        },
        evaluation_available=True,
        evaluation_metrics={
            "single_target_hit_rate": single_target_hit_rate,
            "full_sequence_hit_rate": full_sequence_hit_rate,
        },
        failure_count=failure_count,
        trend=trend,
        delta_vs_previous=0.0,
        delta_vs_best=delta_vs_best,
        weak_classes=[] if weak_classes is None else weak_classes,
        failure_patterns=[] if failure_patterns is None else failure_patterns,
        recent_trials=[],
        best_trial=None,
        evidence=["summary"],
    )


def _group2_summary(
    *,
    point_hit_rate: float = 0.89,
    mean_iou: float = 0.82,
    center_error_px: float = 13.5,
    trend: str = "plateau",
    delta_vs_best: float | None = -0.02,
    failure_patterns: list[str] | None = None,
    failure_count: int | None = 4,
) -> contracts.ResultSummaryRecord:
    return contracts.ResultSummaryRecord(
        study_name="study_001",
        task="group2",
        trial_id="trial_0004",
        dataset_version="v4",
        train_name="trial_0004",
        primary_metric="point_hit_rate",
        primary_score=point_hit_rate,
        test_metrics={"map50_95": 0.8},
        evaluation_available=True,
        evaluation_metrics={
            "point_hit_rate": point_hit_rate,
            "mean_iou": mean_iou,
            "mean_center_error_px": center_error_px,
        },
        failure_count=failure_count,
        trend=trend,
        delta_vs_previous=0.0,
        delta_vs_best=delta_vs_best,
        weak_classes=[],
        failure_patterns=[] if failure_patterns is None else failure_patterns,
        recent_trials=[],
        best_trial=None,
        evidence=["summary"],
    )


class AutoTrainOptimizeTests(unittest.TestCase):
    def test_builds_group1_optuna_plan_only_for_retune(self) -> None:
        plan = optimize.build_optimization_plan(
            summary=_group1_summary(),
            decision=_decision("RETUNE"),
            optuna_available=True,
        )

        self.assertTrue(plan.use_optuna)
        self.assertEqual(plan.engine, "optuna")
        self.assertEqual(plan.base_run, "trial_0003")
        self.assertEqual(plan.search_space.parameters["model"], ("yolo26n.pt", "yolo26s.pt"))
        self.assertEqual(plan.search_space.parameters["epochs"], (100, 120, 140, 160))
        self.assertEqual(plan.search_space.parameters["batch"], (8, 16))
        self.assertEqual(plan.search_space.parameters["imgsz"], (512, 640))

    def test_non_retune_decisions_skip_optuna(self) -> None:
        plan = optimize.build_optimization_plan(
            summary=_group1_summary(),
            decision=_decision("REGENERATE_DATA"),
            optuna_available=True,
        )

        self.assertFalse(plan.use_optuna)
        self.assertEqual(plan.reason, "decision_not_retune")
        self.assertEqual(plan.search_space.parameters, {})

    def test_optuna_unavailable_falls_back_to_deterministic_rule_parameters(self) -> None:
        plan = optimize.build_optimization_plan(
            summary=_group2_summary(failure_patterns=["center_offset"]),
            decision=_decision("RETUNE"),
            optuna_available=False,
        )

        self.assertFalse(plan.use_optuna)
        self.assertEqual(plan.engine, "rules")
        self.assertEqual(plan.reason, "optuna_unavailable")
        self.assertEqual(plan.fallback_parameters["model"], "paired_cnn_v1")
        self.assertEqual(plan.fallback_parameters["imgsz"], 224)

    def test_plateau_prunes_current_candidate_before_no_improve_limit(self) -> None:
        pruning = optimize.assess_pruning(
            optimize.PruningRequest(
                summary=_group1_summary(),
                decision=_decision("RETUNE"),
                plateau_detected=True,
                no_improve_trials=2,
                max_no_improve_trials=4,
            )
        )

        self.assertTrue(pruning.should_prune)
        self.assertFalse(pruning.should_stop_search)
        self.assertFalse(pruning.fallback_to_rules)
        self.assertEqual(pruning.reason, "plateau_prune_candidate")

    def test_no_improve_limit_stops_optuna_and_falls_back_to_rules(self) -> None:
        pruning = optimize.assess_pruning(
            optimize.PruningRequest(
                summary=_group1_summary(
                    weak_classes=["icon_camera"],
                    failure_patterns=["sequence_consistency"],
                    failure_count=7,
                ),
                decision=_decision("RETUNE"),
                plateau_detected=True,
                no_improve_trials=4,
                max_no_improve_trials=4,
            )
        )

        self.assertTrue(pruning.should_stop_search)
        self.assertTrue(pruning.fallback_to_rules)
        self.assertEqual(pruning.fallback_decision, "REGENERATE_DATA")
        self.assertEqual(pruning.reason, "no_improve_limit_reached")

    def test_rule_boundary_can_override_retune_when_summary_already_reaches_promote(self) -> None:
        pruning = optimize.assess_pruning(
            optimize.PruningRequest(
                summary=_group1_summary(
                    primary_score=0.86,
                    single_target_hit_rate=0.94,
                    full_sequence_hit_rate=0.86,
                    trend="improving",
                    delta_vs_best=0.0,
                    failure_count=0,
                ),
                decision=_decision("RETUNE"),
                plateau_detected=False,
                no_improve_trials=0,
                max_no_improve_trials=4,
            )
        )

        self.assertTrue(pruning.should_stop_search)
        self.assertTrue(pruning.fallback_to_rules)
        self.assertEqual(pruning.fallback_decision, "PROMOTE_BRANCH")
        self.assertEqual(pruning.reason, "rule_boundary_override")


if __name__ == "__main__":
    unittest.main()
