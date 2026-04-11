from __future__ import annotations

import unittest
from unittest.mock import patch

from sinanz import (
    CaptchaSolver,
    sn_match_slider,
    sn_match_targets,
)
from sinanz_resources import metadata_root, models_root, resource_root


class PublicApiTest(unittest.TestCase):
    def test_public_api_exports_business_named_entrypoints(self) -> None:
        self.assertTrue(callable(sn_match_slider))
        self.assertTrue(callable(sn_match_targets))
        self.assertTrue(hasattr(CaptchaSolver, "sn_match_slider"))
        self.assertTrue(hasattr(CaptchaSolver, "sn_match_targets"))
        self.assertFalse(hasattr(CaptchaSolver, "locate_slider_gap_target_center"))
        self.assertFalse(hasattr(CaptchaSolver, "locate_click_targets_in_query_order"))

    def test_resource_roots_are_part_of_the_package_layout(self) -> None:
        self.assertEqual(models_root().name, "models")
        self.assertEqual(metadata_root().name, "metadata")

    def test_group2_embedded_assets_are_packaged(self) -> None:
        self.assertTrue((models_root() / "slider_gap_locator.onnx").is_file())
        self.assertTrue((resource_root() / "manifest.json").is_file())

    def test_group1_entrypoint_dispatches_to_group1_service(self) -> None:
        solver = CaptchaSolver(device="cpu", asset_root="/tmp/assets")
        with patch("sinanz.solve_click_targets") as solve_mock:
            solve_mock.return_value = object()
            result = solver.sn_match_targets(
                query_icons_image="query.png",
                background_image="scene.png",
                return_debug=True,
            )

        self.assertIs(result, solve_mock.return_value)
        solve_mock.assert_called_once_with(
            query_icons_image="query.png",
            background_image="scene.png",
            device="cpu",
            asset_root=solver.asset_root,
            return_debug=True,
        )

    def test_module_level_group2_function_uses_same_default_solver(self) -> None:
        with patch.object(CaptchaSolver, "sn_match_slider") as locate_mock:
            locate_mock.return_value = object()
            result = sn_match_slider(
                background_image="master.png",
                puzzle_piece_image="tile.png",
            )

        self.assertIs(result, locate_mock.return_value)

    def test_module_level_group1_function_uses_same_default_solver(self) -> None:
        with patch.object(CaptchaSolver, "sn_match_targets") as locate_mock:
            locate_mock.return_value = object()
            result = sn_match_targets(
                query_icons_image="query.png",
                background_image="scene.png",
            )

        self.assertIs(result, locate_mock.return_value)


if __name__ == "__main__":
    unittest.main()
