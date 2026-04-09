from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "organize_group1_query_icons.py"
MODULE_NAME = "tests._organize_group1_query_icons_script"

MODULE_SPEC = importlib.util.spec_from_file_location(MODULE_NAME, MODULE_PATH)
assert MODULE_SPEC is not None
assert MODULE_SPEC.loader is not None
query_icons = importlib.util.module_from_spec(MODULE_SPEC)
sys.modules[MODULE_NAME] = query_icons
MODULE_SPEC.loader.exec_module(query_icons)


def _mask_from_rows(rows: list[str]) -> tuple[tuple[bool, ...], ...]:
    return tuple(tuple(cell == "#" for cell in row) for row in rows)


class OrganizeGroup1QueryIconsScriptTests(unittest.TestCase):
    def test_extract_query_icon_components_finds_three_icons(self) -> None:
        mask = _mask_from_rows(
            [
                "....................",
                ".###....####....###.",
                ".###....####....###.",
                ".###....####....###.",
                "....................",
            ]
        )

        components = query_icons.extract_query_icon_components(mask, min_pixels=4)

        self.assertEqual(components, [(1, 1, 4, 4), (8, 1, 12, 4), (16, 1, 19, 4)])

    def test_extract_query_icon_features_captures_shape_statistics(self) -> None:
        mask = _mask_from_rows(
            [
                ".###.",
                "#####",
                "#####",
                ".###.",
                "..#..",
            ]
        )

        features = query_icons.extract_query_icon_features(mask)

        self.assertEqual(features.width, 5)
        self.assertEqual(features.height, 5)
        self.assertGreater(features.fill_ratio, 0.6)
        self.assertGreater(features.vertical_symmetry, 0.8)

    def test_build_query_icon_fingerprint_is_stable(self) -> None:
        mask = _mask_from_rows(
            [
                ".###.",
                "#####",
                "#####",
                ".###.",
                "..#..",
            ]
        )
        features = query_icons.extract_query_icon_features(mask)
        normalized = query_icons._resize_mask(mask, 24, 24)
        bits = query_icons._mask_bits(normalized)

        self.assertEqual(
            query_icons.build_query_icon_fingerprint(features, bits),
            query_icons.build_query_icon_fingerprint(features, bits),
        )

    def test_cluster_query_icon_candidates_groups_similar_masks(self) -> None:
        mask_a = _mask_from_rows(
            [
                ".###.",
                "#####",
                "#####",
                ".###.",
                "..#..",
            ]
        )
        mask_b = _mask_from_rows(
            [
                ".###.",
                "#####",
                ".####",
                ".###.",
                "..#..",
            ]
        )
        mask_c = _mask_from_rows(
            [
                "..#..",
                ".###.",
                "#####",
                ".###.",
                "..#..",
            ]
        )

        def _candidate(name: str, order: int, mask: tuple[tuple[bool, ...], ...]) -> query_icons.QueryIconCandidate:
            normalized = query_icons._resize_mask(mask, 24, 24)
            bits = query_icons._mask_bits(normalized)
            features = query_icons.extract_query_icon_features(mask)
            return query_icons.QueryIconCandidate(
                source_path=Path(f"/tmp/{name}.png"),
                sample_id=name,
                order=order,
                bbox=(0, 0, len(mask[0]), len(mask)),
                features=features,
                normalized_bits=bits,
                fingerprint=query_icons.build_query_icon_fingerprint(features, bits),
                mask=mask,
            )

        clusters = query_icons.cluster_query_icon_candidates(
            [
                _candidate("a", 1, mask_a),
                _candidate("b", 1, mask_b),
                _candidate("c", 1, mask_c),
            ],
            max_hamming_distance=60,
        )

        self.assertEqual(len(clusters), 2)
        self.assertEqual(len(clusters[0].members), 2)
        self.assertEqual(len(clusters[1].members), 1)


if __name__ == "__main__":
    unittest.main()
