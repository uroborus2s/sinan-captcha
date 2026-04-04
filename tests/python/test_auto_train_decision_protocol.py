from __future__ import annotations

import unittest

from core.auto_train import contracts, decision_protocol


def _summary(
    *,
    trend: str = "plateau",
    weak_classes: list[str] | None = None,
    failure_patterns: list[str] | None = None,
    failure_count: int | None = 4,
    primary_score: float | None = 0.82,
    delta_vs_best: float | None = -0.01,
) -> contracts.ResultSummaryRecord:
    return contracts.ResultSummaryRecord(
        study_name="study_001",
        task="group1",
        trial_id="trial_0004",
        dataset_version="v4",
        train_name="trial_0004",
        primary_metric="map50_95",
        primary_score=primary_score,
        test_metrics={"map50_95": 0.82, "recall": 0.86},
        evaluation_available=True,
        evaluation_metrics={"full_sequence_hit_rate": 0.78},
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


class AutoTrainDecisionProtocolTests(unittest.TestCase):
    def test_valid_judge_json_is_parsed_into_decision_record(self) -> None:
        outcome = decision_protocol.parse_or_fallback_decision(
            raw_output=(
                '{"decision":"RETUNE","reason":"plateau","confidence":0.82,'
                '"next_action":{"dataset_action":"reuse","train_action":"from_run"},'
                '"evidence":["plateau for 3 trials"]}'
            ),
            trial_id="trial_0004",
            agent=contracts.AgentRef(provider="opencode", name="judge-trial", model="gemma4"),
            summary=_summary(),
        )

        self.assertFalse(outcome.used_fallback)
        self.assertEqual(outcome.record.decision, "RETUNE")
        self.assertEqual(outcome.record.trial_id, "trial_0004")
        self.assertEqual(outcome.record.agent.provider, "opencode")
        self.assertEqual(outcome.record.agent.name, "judge-trial")

    def test_invalid_json_falls_back_to_rule_based_decision(self) -> None:
        outcome = decision_protocol.parse_or_fallback_decision(
            raw_output='{"decision": "RETUNE"',
            trial_id="trial_0004",
            agent=contracts.AgentRef(provider="opencode", name="judge-trial", model="gemma4"),
            summary=_summary(
                weak_classes=["icon_camera", "icon_leaf"],
                failure_patterns=["sequence_consistency", "order_errors"],
                failure_count=5,
            ),
        )

        self.assertTrue(outcome.used_fallback)
        self.assertEqual(outcome.fallback_reason, "invalid_json")
        self.assertEqual(outcome.record.decision, "REGENERATE_DATA")
        self.assertEqual(outcome.record.reason, "fallback_invalid_json")
        self.assertIn("weak_classes", " ".join(outcome.record.evidence))

    def test_invalid_action_falls_back_without_accepting_unknown_decision(self) -> None:
        outcome = decision_protocol.parse_or_fallback_decision(
            raw_output=(
                '{"decision":"SHIP_IT","reason":"unknown","confidence":0.9,'
                '"next_action":{"dataset_action":"reuse"},"evidence":["bad action"]}'
            ),
            trial_id="trial_0004",
            agent=contracts.AgentRef(provider="opencode", name="judge-trial", model="gemma4"),
            summary=_summary(
                trend="declining",
                weak_classes=[],
                failure_patterns=[],
                failure_count=0,
                primary_score=0.74,
                delta_vs_best=-0.08,
            ),
        )

        self.assertTrue(outcome.used_fallback)
        self.assertEqual(outcome.fallback_reason, "invalid_payload")
        self.assertEqual(outcome.record.decision, "ABANDON_BRANCH")
        self.assertEqual(outcome.record.reason, "fallback_invalid_payload")


if __name__ == "__main__":
    unittest.main()
