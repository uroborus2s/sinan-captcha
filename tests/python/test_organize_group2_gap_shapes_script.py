from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "organize_group2_gap_shapes.py"
MODULE_NAME = "tests._organize_group2_gap_shapes_script"

MODULE_SPEC = importlib.util.spec_from_file_location(MODULE_NAME, MODULE_PATH)
assert MODULE_SPEC is not None
assert MODULE_SPEC.loader is not None
gap_shapes = importlib.util.module_from_spec(MODULE_SPEC)
sys.modules[MODULE_NAME] = gap_shapes
MODULE_SPEC.loader.exec_module(gap_shapes)


def _mask_from_rows(rows: list[str]) -> tuple[tuple[bool, ...], ...]:
    return tuple(tuple(cell == "#" for cell in row) for row in rows)


class OrganizeGroup2GapShapesScriptTests(unittest.TestCase):
    def test_extract_shape_features_on_heart_like_mask(self) -> None:
        mask = _mask_from_rows(
            [
                "..##..##..",
                ".########.",
                "##########",
                ".########.",
                "..######..",
                "...####...",
                "...####...",
                "....##....",
            ]
        )

        features = gap_shapes.extract_shape_features(mask)

        self.assertGreaterEqual(features.vertical_symmetry, 0.80)
        self.assertGreaterEqual(features.upper_max_segments, 2)
        self.assertLessEqual(features.bottom_width_ratio, 0.45)

    def test_suggest_shape_family_returns_heart_sticker_for_heart_like_mask(self) -> None:
        mask = _mask_from_rows(
            [
                "..##..##..",
                ".########.",
                "##########",
                ".########.",
                "..######..",
                "...####...",
                "...####...",
                "....##....",
            ]
        )

        features = gap_shapes.extract_shape_features(mask)

        self.assertEqual(gap_shapes.suggest_shape_family(features), "heart_sticker")

    def test_build_semantic_name_returns_compact_name_within_20_chars(self) -> None:
        mask = _mask_from_rows(
            [
                "..###..",
                ".#####.",
                "######.",
                "#######",
                ".#####.",
                "..###..",
            ]
        )

        features = gap_shapes.extract_shape_features(mask)
        fingerprint = gap_shapes.build_shape_fingerprint(features)
        name = gap_shapes.build_semantic_name("rounded_badge", fingerprint)

        self.assertTrue(name.startswith("badge_"))
        self.assertLessEqual(len(name), 20)
        self.assertNotRegex(name, r"\d")

    def test_build_output_plan_uses_compact_names_without_numeric_suffix(self) -> None:
        wide_features = gap_shapes.ShapeFeatures(
            width=10,
            height=8,
            aspect_ratio=1.25,
            fill_ratio=0.6,
            vertical_symmetry=0.9,
            horizontal_symmetry=0.8,
            compactness=0.7,
            top_width_ratio=0.5,
            middle_width_ratio=0.8,
            bottom_width_ratio=0.4,
            upper_max_segments=1,
            center_top_fill_ratio=0.9,
            row_profile=(1, 2, 3),
            column_profile=(3, 2, 1),
        )
        tall_features = gap_shapes.ShapeFeatures(
            width=8,
            height=10,
            aspect_ratio=0.80,
            fill_ratio=0.6,
            vertical_symmetry=0.9,
            horizontal_symmetry=0.8,
            compactness=0.55,
            top_width_ratio=0.35,
            middle_width_ratio=0.65,
            bottom_width_ratio=0.18,
            upper_max_segments=1,
            center_top_fill_ratio=0.45,
            row_profile=(1, 2, 3),
            column_profile=(1, 3, 5),
        )
        candidate_a = gap_shapes.ShapeCandidate(
            source_path=Path("/tmp/a/gap.jpg"),
            shape_family="rounded_badge",
            semantic_name=gap_shapes.build_semantic_name(
                "rounded_badge",
                gap_shapes.build_shape_fingerprint(wide_features),
            ),
            fingerprint="fp_a",
            features=wide_features,
            mask=((True,),),
        )
        candidate_b = gap_shapes.ShapeCandidate(
            source_path=Path("/tmp/b/gap.jpg"),
            shape_family="rounded_badge",
            semantic_name=gap_shapes.build_semantic_name(
                "rounded_badge",
                gap_shapes.build_shape_fingerprint(tall_features),
            ),
            fingerprint="fp_b",
            features=tall_features,
            mask=((True,),),
        )

        records = gap_shapes.build_output_plan(
            [candidate_a, candidate_b],
            {"fp_a": ["/tmp/a2/gap.jpg"], "fp_b": []},
        )

        self.assertEqual(
            records[0].output_name,
            f"{gap_shapes.build_semantic_name(candidate_a.shape_family, candidate_a.fingerprint)}.png",
        )
        self.assertEqual(
            records[1].output_name,
            f"{gap_shapes.build_semantic_name(candidate_b.shape_family, candidate_b.fingerprint)}.png",
        )
        self.assertNotEqual(records[0].output_name, records[1].output_name)
        self.assertLessEqual(len(Path(records[0].output_name).stem), 20)
        self.assertLessEqual(len(Path(records[1].output_name).stem), 20)
        self.assertNotRegex(records[0].output_name, r"\d")
        self.assertNotRegex(records[1].output_name, r"\d")
        self.assertEqual(records[0].duplicate_sources, ["/tmp/a2/gap.jpg"])

    def test_build_output_plan_resolves_short_name_collision_without_digits(self) -> None:
        shared_name = "badge_abcdefgh"
        features_a = gap_shapes.ShapeFeatures(
            width=10,
            height=10,
            aspect_ratio=1.0,
            fill_ratio=0.6,
            vertical_symmetry=0.9,
            horizontal_symmetry=0.82,
            compactness=0.65,
            top_width_ratio=0.5,
            middle_width_ratio=0.7,
            bottom_width_ratio=0.2,
            upper_max_segments=1,
            center_top_fill_ratio=0.7,
            row_profile=(1, 2, 3),
            column_profile=(3, 2, 1),
        )
        features_b = gap_shapes.ShapeFeatures(
            width=10,
            height=10,
            aspect_ratio=1.0,
            fill_ratio=0.6,
            vertical_symmetry=0.9,
            horizontal_symmetry=0.82,
            compactness=0.65,
            top_width_ratio=0.5,
            middle_width_ratio=0.7,
            bottom_width_ratio=0.2,
            upper_max_segments=1,
            center_top_fill_ratio=0.7,
            row_profile=(1, 3, 4),
            column_profile=(4, 3, 1),
        )
        candidate_a = gap_shapes.ShapeCandidate(
            source_path=Path("/tmp/c/gap.jpg"),
            shape_family="rounded_badge",
            semantic_name=shared_name,
            fingerprint="fp_c",
            features=features_a,
            mask=((True,),),
        )
        candidate_b = gap_shapes.ShapeCandidate(
            source_path=Path("/tmp/d/gap.jpg"),
            shape_family="rounded_badge",
            semantic_name=shared_name,
            fingerprint="fp_d",
            features=features_b,
            mask=((True,),),
        )

        def _fake_build_semantic_name(shape_family: str, fingerprint: str, *, code_length: int = 8) -> str:
            if code_length == gap_shapes.SHORT_CODE_LENGTH:
                return "badge_abcdefgh"
            if fingerprint == "fp_c":
                return "badge_abcdefghijk"
            return "badge_abcdefgjklm"

        with patch.object(gap_shapes, "build_semantic_name", side_effect=_fake_build_semantic_name):
            records = gap_shapes.build_output_plan(
                [candidate_a, candidate_b],
                {"fp_c": [], "fp_d": []},
            )

        self.assertTrue(Path(records[0].output_name).stem.startswith("badge_"))
        self.assertTrue(Path(records[1].output_name).stem.startswith("badge_"))
        self.assertNotEqual(records[0].output_name, records[1].output_name)
        self.assertLessEqual(len(Path(records[0].output_name).stem), 20)
        self.assertLessEqual(len(Path(records[1].output_name).stem), 20)
        self.assertNotRegex(records[0].output_name, r"\d")
        self.assertNotRegex(records[1].output_name, r"\d")

    def test_build_shape_fingerprint_is_stable_for_same_features(self) -> None:
        mask = _mask_from_rows(
            [
                "..##..##..",
                ".########.",
                "##########",
                ".########.",
                "..######..",
                "...####...",
                "...####...",
                "....##....",
            ]
        )
        features = gap_shapes.extract_shape_features(mask)

        self.assertEqual(
            gap_shapes.build_shape_fingerprint(features),
            gap_shapes.build_shape_fingerprint(features),
        )


if __name__ == "__main__":
    unittest.main()
