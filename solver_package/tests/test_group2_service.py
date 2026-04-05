from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from sinanz.group2.service import solve_slider_gap


class Group2ServiceTest(unittest.TestCase):
    def test_solve_slider_gap_uses_native_bridge_and_maps_business_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            background = root / "background.png"
            tile = root / "tile.png"
            asset_root = root / "assets"
            model_path = asset_root / "slider_gap_locator.onnx"
            background.write_bytes(b"background")
            tile.write_bytes(b"tile")
            model_path.parent.mkdir(parents=True, exist_ok=True)
            model_path.write_bytes(b"onnx")

            native_result = Mock()
            native_result.target_bbox = (80, 24, 120, 64)
            native_result.execution_provider = "CPUExecutionProvider"

            with patch("sinanz.group2.service.native_bridge.match_slider_gap", return_value=native_result) as match_mock:
                result = solve_slider_gap(
                    background_image=background,
                    puzzle_piece_image=tile,
                    puzzle_piece_start_bbox=(8, 12, 48, 52),
                    device="auto",
                    asset_root=asset_root,
                    return_debug=True,
                )

            match_mock.assert_called_once_with(
                model_path=model_path,
                background_image_path=background,
                puzzle_piece_image_path=tile,
                device="auto",
            )
            self.assertEqual(result.target_center, (100, 44))
            self.assertEqual(result.target_bbox, (80, 24, 120, 64))
            self.assertEqual(result.puzzle_piece_offset, (72, 12))
            self.assertIsNotNone(result.debug)
            self.assertIn("provider=CPUExecutionProvider", result.debug.notes)
            self.assertIn("model=slider_gap_locator.onnx", result.debug.notes)


if __name__ == "__main__":
    unittest.main()
