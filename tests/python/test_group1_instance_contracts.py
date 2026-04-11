from __future__ import annotations

import unittest

from dataset.contracts import BoundingBox, Group1OrderedItem, Group1Sample, Group1SceneObject
from dataset.validation import DatasetValidationError, validate_group1_row


class Group1InstanceContractsTests(unittest.TestCase):
    def test_group1_sample_serializes_query_items_with_material_identity(self) -> None:
        sample = Group1Sample(
            sample_id="g1_000001",
            query_image="query/g1_000001.png",
            scene_image="scene/g1_000001.png",
            query_items=[
                Group1OrderedItem(
                    order=1,
                    asset_id="asset_house_main",
                    template_id="tpl_house",
                    variant_id="var_outline",
                    bbox=BoundingBox(8, 8, 28, 28),
                    center=(18, 18),
                )
            ],
            scene_targets=[
                Group1OrderedItem(
                    order=1,
                    asset_id="asset_house_main",
                    template_id="tpl_house",
                    variant_id="var_outline",
                    bbox=BoundingBox(80, 32, 120, 72),
                    center=(100, 52),
                )
            ],
            distractors=[
                Group1SceneObject(
                    asset_id="asset_leaf_alt",
                    template_id="tpl_leaf",
                    variant_id="var_fill",
                    bbox=BoundingBox(140, 36, 180, 76),
                    center=(160, 56),
                )
            ],
            label_source="gold",
            source_batch="batch_0001",
            seed=1,
        )

        payload = sample.to_dict()

        self.assertIn("query_items", payload)
        self.assertNotIn("query_targets", payload)
        self.assertEqual(payload["query_items"][0]["asset_id"], "asset_house_main")
        self.assertEqual(payload["query_items"][0]["template_id"], "tpl_house")
        self.assertEqual(payload["query_items"][0]["variant_id"], "var_outline")
        self.assertEqual(payload["scene_targets"][0]["center"], [100, 52])
        self.assertEqual(payload["distractors"][0]["asset_id"], "asset_leaf_alt")

    def test_validate_group1_row_accepts_new_query_items_shape(self) -> None:
        row = {
            "sample_id": "g1_000001",
            "query_image": "query/g1_000001.png",
            "scene_image": "scene/g1_000001.png",
            "query_items": [
                {
                    "order": 1,
                    "asset_id": "asset_house_main",
                    "template_id": "tpl_house",
                    "variant_id": "var_outline",
                    "bbox": [8, 8, 28, 28],
                    "center": [18, 18],
                }
            ],
            "scene_targets": [
                {
                    "order": 1,
                    "asset_id": "asset_house_main",
                    "template_id": "tpl_house",
                    "variant_id": "var_outline",
                    "bbox": [80, 32, 120, 72],
                    "center": [100, 52],
                }
            ],
            "distractors": [],
            "label_source": "gold",
            "source_batch": "batch_0001",
        }

        normalized = validate_group1_row(row)

        self.assertEqual(normalized["query_items"][0]["asset_id"], "asset_house_main")
        self.assertEqual(normalized["scene_targets"][0]["template_id"], "tpl_house")

    def test_validate_group1_row_rejects_legacy_query_targets_alias(self) -> None:
        row = {
            "sample_id": "g1_000001",
            "query_image": "query/g1_000001.png",
            "scene_image": "scene/g1_000001.png",
            "query_targets": [
                {
                    "order": 1,
                    "asset_id": "asset_house_main",
                    "template_id": "tpl_house",
                    "variant_id": "var_outline",
                    "bbox": [8, 8, 28, 28],
                    "center": [18, 18],
                }
            ],
            "scene_targets": [
                {
                    "order": 1,
                    "asset_id": "asset_house_main",
                    "template_id": "tpl_house",
                    "variant_id": "var_outline",
                    "bbox": [80, 32, 120, 72],
                    "center": [100, 52],
                }
            ],
            "distractors": [],
            "label_source": "gold",
            "source_batch": "batch_0001",
        }

        with self.assertRaisesRegex(DatasetValidationError, "missing required field: query_items"):
            validate_group1_row(row)

    def test_validate_group1_row_accepts_reviewed_order_and_bbox_without_identity_or_class(self) -> None:
        row = {
            "sample_id": "exam_0001",
            "query_image": "query/exam_0001.png",
            "scene_image": "scene/exam_0001.png",
            "query_items": [
                {
                    "order": 1,
                    "bbox": [8, 8, 28, 28],
                    "center": [18, 18],
                }
            ],
            "scene_targets": [
                {
                    "order": 1,
                    "bbox": [80, 32, 120, 72],
                    "center": [100, 52],
                }
            ],
            "distractors": [],
            "label_source": "reviewed",
            "source_batch": "reviewed-v2",
        }

        normalized = validate_group1_row(row)

        self.assertEqual(normalized["query_items"][0]["center"], [18, 18])
        self.assertNotIn("class", normalized["query_items"][0])
        self.assertNotIn("asset_id", normalized["scene_targets"][0])

    def test_validate_group1_row_accepts_predicted_sparse_query_items_with_identity_scene_targets(self) -> None:
        row = {
            "sample_id": "pred_0001",
            "query_image": "query/pred_0001.png",
            "scene_image": "scene/pred_0001.png",
            "query_items": [
                {
                    "order": 1,
                    "bbox": [8, 8, 28, 28],
                    "center": [18, 18],
                    "class_guess": "icon_lock",
                }
            ],
            "scene_targets": [
                {
                    "order": 1,
                    "asset_id": "pred_asset_01",
                    "template_id": "pred_tpl_01",
                    "variant_id": "pred_var_01",
                    "bbox": [80, 32, 120, 72],
                    "center": [100, 52],
                }
            ],
            "distractors": [],
            "label_source": "pred",
            "source_batch": "predict",
        }

        normalized = validate_group1_row(row)

        self.assertEqual(normalized["query_items"][0]["class_guess"], "icon_lock")
        self.assertEqual(normalized["scene_targets"][0]["asset_id"], "pred_asset_01")


if __name__ == "__main__":
    unittest.main()
