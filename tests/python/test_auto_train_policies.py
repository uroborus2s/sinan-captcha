from __future__ import annotations

import unittest

from core.auto_train import contracts, policies


def _group1_summary(
    *,
    primary_score: float = 0.83,
    recall: float = 0.89,
    full_sequence_hit_rate: float = 0.86,
    trend: str = "improving",
    delta_vs_best: float | None = -0.01,
    weak_classes: list[str] | None = None,
    failure_patterns: list[str] | None = None,
    failure_count: int | None = 2,
) -> contracts.ResultSummaryRecord:
    return contracts.ResultSummaryRecord(
        study_name="study_001",
        task="group1",
        trial_id="trial_0004",
        dataset_version="v4",
        train_name="trial_0004",
        primary_metric="map50_95",
        primary_score=primary_score,
        test_metrics={
            "precision": 0.91,
            "recall": recall,
            "map50_95": primary_score,
        },
        evaluation_available=True,
        evaluation_metrics={
            "single_target_hit_rate": 0.94,
            "full_sequence_hit_rate": full_sequence_hit_rate,
            "mean_center_error_px": 6.8,
            "order_error_rate": 0.04,
        },
        failure_count=failure_count,
        trend=trend,
        delta_vs_previous=0.01,
        delta_vs_best=delta_vs_best,
        weak_classes=[] if weak_classes is None else weak_classes,
        failure_patterns=[] if failure_patterns is None else failure_patterns,
        recent_trials=[],
        best_trial=None,
        evidence=["summary"],
    )


def _group2_summary(
    *,
    point_hit_rate: float = 0.94,
    mean_iou: float = 0.86,
    center_error_px: float = 7.5,
    trend: str = "improving",
    delta_vs_best: float | None = -0.01,
    failure_patterns: list[str] | None = None,
    failure_count: int | None = 1,
) -> contracts.ResultSummaryRecord:
    return contracts.ResultSummaryRecord(
        study_name="study_001",
        task="group2",
        trial_id="trial_0004",
        dataset_version="v4",
        train_name="trial_0004",
        primary_metric="point_hit_rate",
        primary_score=point_hit_rate,
        test_metrics={
            "precision": 0.9,
            "recall": 0.88,
            "map50_95": 0.81,
        },
        evaluation_available=True,
        evaluation_metrics={
            "point_hit_rate": point_hit_rate,
            "mean_center_error_px": center_error_px,
            "mean_iou": mean_iou,
        },
        failure_count=failure_count,
        trend=trend,
        delta_vs_previous=0.01,
        delta_vs_best=delta_vs_best,
        weak_classes=[],
        failure_patterns=[] if failure_patterns is None else failure_patterns,
        recent_trials=[],
        best_trial=None,
        evidence=["summary"],
    )


class AutoTrainPoliciesTests(unittest.TestCase):
    def test_group1_policy_freezes_primary_secondary_and_business_metrics(self) -> None:
        policy = policies.policy_for_task("group1")

        self.assertEqual(policy.primary_metric, "map50_95")
        self.assertEqual(policy.secondary_metric, "recall")
        self.assertEqual(policy.business_metric, "full_sequence_hit_rate")
        self.assertIsNone(policy.penalty_metric)
        self.assertEqual(policy.plateau_window, 3)
        self.assertAlmostEqual(policy.min_delta, 0.005)

    def test_group1_promotes_only_when_detection_and_sequence_metrics_both_pass(self) -> None:
        recommendation = policies.evaluate_summary(_group1_summary())

        self.assertEqual(recommendation.decision, "PROMOTE_BRANCH")
        self.assertEqual(recommendation.reason, "group1_targets_met")

    def test_group1_regenerates_data_when_weak_classes_or_sequence_failures_persist(self) -> None:
        recommendation = policies.evaluate_summary(
            _group1_summary(
                primary_score=0.81,
                recall=0.87,
                full_sequence_hit_rate=0.78,
                weak_classes=["icon_camera", "icon_leaf"],
                failure_patterns=["sequence_consistency", "order_errors"],
                failure_count=6,
                trend="plateau",
            )
        )

        self.assertEqual(recommendation.decision, "REGENERATE_DATA")
        self.assertEqual(recommendation.reason, "group1_data_quality_gap")

    def test_group1_abandons_branch_after_clear_decline_from_best_run(self) -> None:
        recommendation = policies.evaluate_summary(
            _group1_summary(
                primary_score=0.72,
                recall=0.8,
                full_sequence_hit_rate=0.7,
                trend="declining",
                delta_vs_best=-0.08,
                failure_patterns=["detection_recall", "strict_localization"],
                failure_count=8,
            )
        )

        self.assertEqual(recommendation.decision, "ABANDON_BRANCH")
        self.assertEqual(recommendation.reason, "group1_regressed_branch")

    def test_group2_policy_freezes_primary_secondary_and_penalty_metrics(self) -> None:
        policy = policies.policy_for_task("group2")

        self.assertEqual(policy.primary_metric, "point_hit_rate")
        self.assertEqual(policy.secondary_metric, "mean_iou")
        self.assertIsNone(policy.business_metric)
        self.assertEqual(policy.penalty_metric, "mean_center_error_px")
        self.assertEqual(policy.plateau_window, 3)
        self.assertAlmostEqual(policy.min_delta, 0.01)

    def test_group2_promotes_when_hit_rate_iou_and_center_error_all_pass(self) -> None:
        recommendation = policies.evaluate_summary(_group2_summary())

        self.assertEqual(recommendation.decision, "PROMOTE_BRANCH")
        self.assertEqual(recommendation.reason, "group2_targets_met")

    def test_group2_regenerates_data_when_hit_rate_or_iou_show_dataset_contract_risk(self) -> None:
        recommendation = policies.evaluate_summary(
            _group2_summary(
                point_hit_rate=0.78,
                mean_iou=0.71,
                center_error_px=13.4,
                trend="plateau",
                failure_patterns=["point_hits", "low_iou"],
                failure_count=9,
            )
        )

        self.assertEqual(recommendation.decision, "REGENERATE_DATA")
        self.assertEqual(recommendation.reason, "group2_dataset_contract_gap")

    def test_group2_prefers_retune_when_main_gap_is_center_offset(self) -> None:
        recommendation = policies.evaluate_summary(
            _group2_summary(
                point_hit_rate=0.9,
                mean_iou=0.84,
                center_error_px=14.5,
                trend="plateau",
                failure_patterns=["center_offset"],
                failure_count=4,
            )
        )

        self.assertEqual(recommendation.decision, "RETUNE")
        self.assertEqual(recommendation.reason, "group2_localization_offset")


if __name__ == "__main__":
    unittest.main()
