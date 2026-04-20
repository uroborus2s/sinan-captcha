from __future__ import annotations

import unittest

from auto_train import quality_gate


class AutoTrainQualityGateTests(unittest.TestCase):
    def test_mild_proposal_gate_failure_does_not_interrupt_downstream_training(self) -> None:
        intervention = quality_gate.assess_group1_gate(
            stage="SCENE_GATE",
            component="proposal-detector",
            gate_payload={
                "status": "failed",
                "metrics": {
                    "proposal_object_recall": 0.997,
                    "proposal_full_recall_rate": 0.979,
                    "proposal_strict_hit_rate": 0.945,
                    "proposal_false_positive_per_sample": 0.08,
                },
            },
        )

        self.assertIsNone(intervention)

    def test_severe_proposal_recall_gap_triggers_intervention(self) -> None:
        intervention = quality_gate.assess_group1_gate(
            stage="SCENE_GATE",
            component="proposal-detector",
            gate_payload={
                "status": "failed",
                "metrics": {
                    "proposal_object_recall": 0.990899,
                    "proposal_full_recall_rate": 0.938,
                    "proposal_strict_hit_rate": 0.884,
                    "proposal_false_positive_per_sample": 0.082,
                },
            },
        )

        self.assertIsNotNone(intervention)
        assert intervention is not None
        self.assertEqual(intervention.component, "proposal-detector")
        self.assertIn("detection_recall", intervention.failure_patterns)
        self.assertIn("strict_localization", intervention.failure_patterns)
        self.assertIn("proposal_full_recall_rate=0.938000", intervention.evidence)

    def test_query_exact_count_near_miss_does_not_interrupt(self) -> None:
        intervention = quality_gate.assess_group1_gate(
            stage="QUERY_GATE",
            component="query-detector",
            gate_payload={
                "status": "failed",
                "metrics": {
                    "query_item_recall": 1.0,
                    "query_exact_count_rate": 0.992,
                    "query_strict_hit_rate": 0.995,
                },
            },
        )

        self.assertIsNone(intervention)

    def test_severe_embedder_scene_recall_gap_triggers_intervention(self) -> None:
        intervention = quality_gate.assess_group1_gate(
            stage="EMBEDDER_GATE",
            component="icon-embedder",
            gate_payload={
                "status": "failed",
                "metrics": {
                    "embedding_scene_recall_at_1": 0.88289,
                    "embedding_scene_recall_at_3": 0.961,
                    "embedding_identity_recall_at_1": 0.624,
                },
            },
        )

        self.assertIsNotNone(intervention)
        assert intervention is not None
        self.assertEqual(intervention.reason, "embedder_gate_severe_scene_recall_gap")
        self.assertIn("embedding_recall", intervention.failure_patterns)
        self.assertIn("embedding_identity", intervention.failure_patterns)


if __name__ == "__main__":
    unittest.main()
