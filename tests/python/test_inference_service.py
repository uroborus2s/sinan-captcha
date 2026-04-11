from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from inference.service import map_group1_instances


class InferenceServiceTests(unittest.TestCase):
    def test_map_group1_instances_matches_by_visual_similarity(self) -> None:
        query_items = [
            {
                "order": 1,
                "bbox": [0, 0, 20, 20],
                "center": [10, 10],
                "image_path": "query_red",
            },
            {
                "order": 2,
                "bbox": [0, 0, 20, 20],
                "center": [10, 10],
                "image_path": "query_blue",
            },
        ]
        scene_detections = [
            {
                "order": 1,
                "bbox": [0, 0, 20, 20],
                "center": [10, 10],
                "score": 0.98,
                "image_path": "scene_blue",
            },
            {
                "order": 2,
                "bbox": [0, 0, 20, 20],
                "center": [10, 10],
                "score": 0.97,
                "image_path": "scene_green",
            },
            {
                "order": 3,
                "bbox": [0, 0, 20, 20],
                "center": [10, 10],
                "score": 0.96,
                "image_path": "scene_red",
            },
        ]
        vectors = {
            "query_red": [1.0, 0.0, 0.0],
            "query_blue": [0.0, 0.0, 1.0],
            "scene_blue": [0.0, 0.0, 1.0],
            "scene_green": [0.0, 1.0, 0.0],
            "scene_red": [1.0, 0.0, 0.0],
        }

        def fake_embedding_vector(target, *, fallback_image_path, embedding_provider):
            del fallback_image_path, embedding_provider
            return vectors[str(target["image_path"])]

        with patch("inference.service._embedding_vector", side_effect=fake_embedding_vector):
            result = map_group1_instances(query_items, scene_detections)

        self.assertEqual(result.status, "ok")
        self.assertEqual([target.order for target in result.ordered_targets], [1, 2])
        self.assertEqual([target.center for target in result.ordered_targets], [[10, 10], [10, 10]])
        self.assertEqual([target.score for target in result.ordered_targets], [1.0, 1.0])
        self.assertEqual(result.missing_orders, [])
        self.assertEqual(result.ambiguous_orders, [])

    def test_map_group1_instances_can_use_embedding_provider_for_crops(self) -> None:
        query_items = [
            {
                "order": 1,
                "bbox": [0, 0, 20, 20],
                "center": [10, 10],
                "embed_id": "query_red",
            }
        ]
        scene_detections = [
            {
                "order": 1,
                "bbox": [20, 0, 40, 20],
                "center": [30, 10],
                "score": 0.98,
                "embed_id": "scene_blue",
            },
            {
                "order": 2,
                "bbox": [40, 0, 60, 20],
                "center": [50, 10],
                "score": 0.97,
                "embed_id": "scene_red",
            },
        ]
        provider = _FakeEmbeddingProvider(
            {
                "query_red": [1.0, 0.0],
                "scene_blue": [0.0, 1.0],
                "scene_red": [1.0, 0.0],
            }
        )

        result = map_group1_instances(
            query_items,
            scene_detections,
            query_image_path=Path("/tmp/query.png"),
            scene_image_path=Path("/tmp/scene.png"),
            embedding_provider=provider,
        )

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.ordered_targets[0].center, [50, 10])
        self.assertEqual(
            provider.calls,
            [
                (Path("/tmp/query.png"), "query_red"),
                (Path("/tmp/scene.png"), "scene_blue"),
                (Path("/tmp/scene.png"), "scene_red"),
            ],
        )


class _FakeEmbeddingProvider:
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self.vectors = vectors
        self.calls: list[tuple[Path, str]] = []

    def embed_crop(self, image_path: Path, target: dict[str, object]) -> list[float]:
        embed_id = str(target["embed_id"])
        self.calls.append((image_path, embed_id))
        return self.vectors[embed_id]


if __name__ == "__main__":
    unittest.main()
