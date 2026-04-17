from __future__ import annotations

import unittest

from auto_train import contracts, embedder_review_protocol


def _context(
    *,
    stage: str = "TRAIN_EMBEDDER_BASE",
    epoch: int = 8,
    rebuild_count: int = 0,
    best_epoch: int | None = 7,
    best_embedding_recall_at_1: float | None = 0.047,
    metrics: dict[str, contracts.JsonValue] | None = None,
    recent_history: list[dict[str, contracts.JsonValue]] | None = None,
    review_history: list[dict[str, contracts.JsonValue]] | None = None,
) -> embedder_review_protocol.EmbedderReviewContext:
    return embedder_review_protocol.EmbedderReviewContext(
        study_name="study_001",
        task="group1",
        trial_id="trial_0001",
        train_name="trial_0001",
        stage=stage,
        epoch=epoch,
        review_window=3,
        rebuild_count=rebuild_count,
        dataset_config="datasets/group1/v1/dataset.json",
        image_size=96,
        batch_size=32,
        best_epoch=best_epoch,
        best_embedding_recall_at_1=best_embedding_recall_at_1,
        current_metrics={
            "embedding_recall_at_1": 0.047,
            "embedding_recall_at_3": 0.149,
            "embedding_identity_recall_at_1": 0.934,
            "embedding_positive_rank_mean": 35.8,
            "embedding_same_template_top1_error_rate": 0.1,
            "embedding_top1_error_scene_target_rate": 0.1,
            "embedding_top1_error_false_positive_rate": 0.05,
            **({} if metrics is None else metrics),
        },
        recent_history=[
            {"embedding_recall_at_1": 0.047, "embedding_positive_rank_mean": 36.0},
            {"embedding_recall_at_1": 0.047, "embedding_positive_rank_mean": 35.9},
            {"embedding_recall_at_1": 0.047, "embedding_positive_rank_mean": 35.8},
        ]
        if recent_history is None
        else recent_history,
        review_history=[] if review_history is None else review_history,
    )


class EmbedderReviewProtocolTests(unittest.TestCase):
    def test_valid_embedder_review_json_is_parsed(self) -> None:
        outcome = embedder_review_protocol.parse_or_fallback_review(
            raw_output=(
                '{"decision":"STOP_AND_ADVANCE","reason":"base_plateau","confidence":0.82,'
                '"next_action":{"train_action":"stop_and_advance","target_stage":"EMBEDDER_GATE"},'
                '"evidence":["plateau"]}'
            ),
            context=_context(),
            agent=contracts.AgentRef(provider="opencode", name="review-embedder", model="qwen"),
        )

        self.assertFalse(outcome.used_fallback)
        self.assertEqual(outcome.record.decision, "STOP_AND_ADVANCE")
        self.assertEqual(outcome.record.stage, "TRAIN_EMBEDDER_BASE")

    def test_primary_recall_prefers_scene_metric_even_when_zero(self) -> None:
        metrics: dict[str, contracts.JsonValue] = {
            "embedding_recall_at_1": 0.12,
            "embedding_recall_at_3": 0.36,
            "embedding_scene_recall_at_1": 0.0,
            "embedding_scene_recall_at_3": 0.0,
        }

        self.assertEqual(embedder_review_protocol._primary_recall_at_1(metrics), 0.0)
        self.assertEqual(embedder_review_protocol._primary_recall_at_3(metrics), 0.0)

    def test_metrics_snapshot_keeps_scene_metrics_for_future_reviews(self) -> None:
        snapshot = embedder_review_protocol._metrics_snapshot(
            {
                "embedding_recall_at_1": 0.12,
                "embedding_recall_at_3": 0.36,
                "embedding_scene_recall_at_1": 0.0,
                "embedding_scene_recall_at_3": 0.5,
                "embedding_scene_positive_rank_mean": 2.0,
            }
        )

        self.assertEqual(snapshot["embedding_scene_recall_at_1"], 0.0)
        self.assertEqual(snapshot["embedding_scene_recall_at_3"], 0.5)
        self.assertEqual(snapshot["embedding_scene_positive_rank_mean"], 2.0)

    def test_hard_stage_fallback_prefers_rebuild_on_same_template_confusion(self) -> None:
        outcome = embedder_review_protocol.fallback_review(
            context=_context(
                stage="TRAIN_EMBEDDER_HARD",
                metrics={
                    "embedding_same_template_top1_error_rate": 0.42,
                    "embedding_top1_error_scene_target_rate": 0.08,
                    "embedding_top1_error_false_positive_rate": 0.04,
                },
            ),
            agent=contracts.AgentRef(provider="opencode", name="review-embedder", model="qwen"),
            reason_code="runtime_error",
        )

        self.assertTrue(outcome.used_fallback)
        self.assertEqual(outcome.record.decision, "REBUILD_HARDSET")
        self.assertEqual(outcome.record.next_action["target_stage"], "BUILD_EMBEDDER_HARDSET")

    def test_base_stage_force_stops_when_exact_recall_remains_low_after_epoch_20(self) -> None:
        outcome = embedder_review_protocol.fallback_review(
            context=_context(
                epoch=20,
                metrics={
                    "embedding_recall_at_1": 0.056,
                    "embedding_recall_at_3": 0.1616,
                    "embedding_identity_recall_at_1": 0.922,
                    "embedding_positive_rank_mean": 84.6,
                },
                recent_history=[
                    {"embedding_recall_at_1": 0.052, "embedding_positive_rank_mean": 88.0},
                    {"embedding_recall_at_1": 0.054, "embedding_positive_rank_mean": 86.0},
                    {"embedding_recall_at_1": 0.056, "embedding_positive_rank_mean": 84.6},
                ],
            ),
            agent=contracts.AgentRef(provider="opencode", name="review-embedder", model="qwen"),
            reason_code="runtime_error",
        )

        self.assertEqual(outcome.record.decision, "STOP_AND_ADVANCE")
        self.assertEqual(outcome.record.reason, "base_low_exact_recall_force_hardset")
        self.assertEqual(outcome.record.next_action["target_stage"], "EMBEDDER_GATE")

    def test_parsed_continue_remains_continue_in_llm_first_mode_even_when_base_guardrail_matches(self) -> None:
        outcome = embedder_review_protocol.parse_or_fallback_review(
            raw_output=(
                '{"decision":"CONTINUE","reason":"recent_progress_observed","confidence":0.71,'
                '"next_action":{"train_action":"continue","target_stage":"TRAIN_EMBEDDER_BASE"},'
                '"evidence":["recent_window=improving"]}'
            ),
            context=_context(
                epoch=20,
                metrics={
                    "embedding_recall_at_1": 0.056,
                    "embedding_recall_at_3": 0.1616,
                    "embedding_identity_recall_at_1": 0.922,
                    "embedding_positive_rank_mean": 84.6,
                },
                recent_history=[
                    {"embedding_recall_at_1": 0.052, "embedding_positive_rank_mean": 88.0},
                    {"embedding_recall_at_1": 0.054, "embedding_positive_rank_mean": 86.0},
                    {"embedding_recall_at_1": 0.056, "embedding_positive_rank_mean": 84.6},
                ],
            ),
            agent=contracts.AgentRef(provider="opencode", name="review-embedder", model="qwen"),
        )

        self.assertFalse(outcome.used_fallback)
        self.assertEqual(outcome.record.decision, "CONTINUE")
        self.assertEqual(outcome.record.reason, "recent_progress_observed")
        self.assertIn("recent_window=improving", outcome.record.evidence)

    def test_parsed_continue_remains_continue_in_llm_first_mode_when_best_epoch_is_stale(self) -> None:
        outcome = embedder_review_protocol.parse_or_fallback_review(
            raw_output=(
                '{"decision":"CONTINUE","reason":"weak_exact_retrieval_base_stage_no_clear_progress","confidence":0.68,'
                '"next_action":{"train_action":"continue","target_stage":"TRAIN_EMBEDDER_BASE"},'
                '"evidence":["embedding_scene_recall_at_1=0.896179","embedding_same_template_top1_error_rate=0.636766"]}'
            ),
            context=_context(
                epoch=17,
                best_epoch=11,
                best_embedding_recall_at_1=0.986333,
                metrics={
                    "embedding_recall_at_1": 0.023256,
                    "embedding_recall_at_3": 0.061185,
                    "embedding_scene_recall_at_1": 0.896179,
                    "embedding_scene_recall_at_3": 0.972038,
                    "embedding_identity_recall_at_1": 0.622924,
                    "embedding_identity_recall_at_3": 0.715947,
                    "embedding_positive_rank_mean": 317.182171,
                    "embedding_same_template_top1_error_rate": 0.636766,
                    "embedding_top1_error_scene_target_rate": 0.213455,
                    "embedding_top1_error_false_positive_rate": 0.0,
                },
                recent_history=[
                    {"embedding_scene_recall_at_1": 0.896170, "embedding_recall_at_1": 0.023250},
                    {"embedding_scene_recall_at_1": 0.896175, "embedding_recall_at_1": 0.023252},
                    {"embedding_scene_recall_at_1": 0.896179, "embedding_recall_at_1": 0.023256},
                ],
            ),
            agent=contracts.AgentRef(provider="opencode", name="review-embedder", model="gpt-5-nano"),
        )

        self.assertFalse(outcome.used_fallback)
        self.assertEqual(outcome.record.decision, "CONTINUE")
        self.assertEqual(outcome.record.reason, "weak_exact_retrieval_base_stage_no_clear_progress")
        self.assertEqual(outcome.record.next_action["target_stage"], "TRAIN_EMBEDDER_BASE")

    def test_hard_stage_low_exact_recall_does_not_override_llm_continue_in_llm_first_mode(self) -> None:
        outcome = embedder_review_protocol.parse_or_fallback_review(
            raw_output=(
                '{"decision":"CONTINUE","reason":"recent_progress_observed","confidence":0.74,'
                '"next_action":{"train_action":"continue","target_stage":"TRAIN_EMBEDDER_HARD"},'
                '"evidence":["recent_window=improving"]}'
            ),
            context=_context(
                stage="TRAIN_EMBEDDER_HARD",
                epoch=14,
                metrics={
                    "embedding_recall_at_1": 0.0183,
                    "embedding_recall_at_3": 0.0497,
                    "embedding_identity_recall_at_1": 0.9283,
                    "embedding_identity_recall_at_3": 0.9283,
                    "embedding_positive_rank_mean": 101.8,
                },
                recent_history=[
                    {"embedding_recall_at_1": 0.0166, "embedding_positive_rank_mean": 185.9},
                    {"embedding_recall_at_1": 0.0174, "embedding_positive_rank_mean": 141.2},
                    {"embedding_recall_at_1": 0.0183, "embedding_positive_rank_mean": 101.8},
                ],
            ),
            agent=contracts.AgentRef(provider="opencode", name="review-embedder", model="qwen"),
        )

        self.assertFalse(outcome.used_fallback)
        self.assertEqual(outcome.record.decision, "CONTINUE")
        self.assertEqual(outcome.record.reason, "recent_progress_observed")
        self.assertEqual(outcome.record.next_action["target_stage"], "TRAIN_EMBEDDER_HARD")

    def test_hard_stage_repeated_low_exact_reviews_escalate_detector_after_rebuild(self) -> None:
        outcome = embedder_review_protocol.fallback_review(
            context=_context(
                stage="TRAIN_EMBEDDER_HARD",
                epoch=17,
                rebuild_count=1,
                metrics={
                    "embedding_recall_at_1": 0.0179,
                    "embedding_recall_at_3": 0.0512,
                    "embedding_identity_recall_at_1": 0.9150,
                    "embedding_top1_error_scene_target_rate": 0.28,
                    "embedding_top1_error_false_positive_rate": 0.19,
                },
                recent_history=[
                    {"embedding_recall_at_1": 0.0171, "embedding_positive_rank_mean": 124.0},
                    {"embedding_recall_at_1": 0.0175, "embedding_positive_rank_mean": 119.0},
                    {"embedding_recall_at_1": 0.0179, "embedding_positive_rank_mean": 117.0},
                ],
                review_history=[
                    {
                        "stage": "TRAIN_EMBEDDER_HARD",
                        "epoch": 14,
                        "decision": "REBUILD_HARDSET",
                        "confidence": 0.8,
                        "reason": "hard_low_exact_force_rebuild_hardset",
                        "next_action": {
                            "train_action": "rebuild_hardset",
                            "target_stage": "BUILD_EMBEDDER_HARDSET",
                        },
                        "evidence": ["guardrail=hard_force_rebuild_low_exact_recall"],
                        "metrics_snapshot": {
                            "embedding_recall_at_1": 0.0183,
                            "embedding_identity_recall_at_1": 0.9283,
                        },
                        "agent": {
                            "provider": "opencode",
                            "name": "review-embedder",
                            "model": "qwen",
                        },
                    }
                ],
            ),
            agent=contracts.AgentRef(provider="opencode", name="review-embedder", model="qwen"),
            reason_code="runtime_error",
        )

        self.assertTrue(outcome.used_fallback)
        self.assertEqual(outcome.record.decision, "ESCALATE_DETECTOR")
        self.assertEqual(outcome.record.reason, "hard_low_exact_persisted_escalate_detector")
        self.assertEqual(outcome.record.next_action["target_stage"], "JUDGE")


if __name__ == "__main__":
    unittest.main()
