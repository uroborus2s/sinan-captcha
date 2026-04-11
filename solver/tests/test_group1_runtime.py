from __future__ import annotations

import unittest

from sinanz_group1_runtime import DetectedTarget, assign_ordered_targets


class Group1RuntimeTest(unittest.TestCase):
    def test_assign_ordered_targets_uses_global_embedding_match(self) -> None:
        query_detections = [
            DetectedTarget(order=1, bbox=(0, 0, 10, 10), center=(5, 5), score=0.9),
            DetectedTarget(order=2, bbox=(20, 0, 30, 10), center=(25, 5), score=0.9),
        ]
        scene_detections = [
            DetectedTarget(order=1, bbox=(100, 0, 120, 20), center=(110, 10), score=0.8),
            DetectedTarget(order=2, bbox=(40, 0, 60, 20), center=(50, 10), score=0.8),
        ]

        result = assign_ordered_targets(
            query_detections=query_detections,
            scene_detections=scene_detections,
            query_embeddings=[[1.0, 0.0], [0.0, 1.0]],
            scene_embeddings=[[0.0, 1.0], [1.0, 0.0]],
            similarity_threshold=0.8,
            ambiguity_margin=0.05,
        )

        self.assertEqual([target.center for target in result.ordered_targets], [(50, 10), (110, 10)])
        self.assertEqual(result.missing_orders, [])
        self.assertEqual(result.ambiguous_orders, [])

    def test_assign_ordered_targets_marks_low_confidence_and_ambiguous_matches(self) -> None:
        query_detections = [
            DetectedTarget(order=1, bbox=(0, 0, 10, 10), center=(5, 5), score=0.9),
            DetectedTarget(order=2, bbox=(20, 0, 30, 10), center=(25, 5), score=0.9),
        ]
        scene_detections = [
            DetectedTarget(order=1, bbox=(100, 0, 120, 20), center=(110, 10), score=0.8),
            DetectedTarget(order=2, bbox=(40, 0, 60, 20), center=(50, 10), score=0.8),
        ]

        result = assign_ordered_targets(
            query_detections=query_detections,
            scene_detections=scene_detections,
            query_embeddings=[[1.0, 0.0], [0.0, 1.0]],
            scene_embeddings=[[0.99, 0.01], [0.98, 0.02]],
            similarity_threshold=0.8,
            ambiguity_margin=0.05,
        )

        self.assertEqual(result.missing_orders, [2])
        self.assertEqual(result.ambiguous_orders, [1])
        self.assertEqual([target.query_order for target in result.ordered_targets], [1])


if __name__ == "__main__":
    unittest.main()
