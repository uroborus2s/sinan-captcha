from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from sinanz_group2_service import solve_slider_gap

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x04\x00\x00\x00\xb5\x1c\x0c\x02\x00\x00\x00\x0bIDATx\xdac\xfc\xff\x1f\x00\x03\x03\x02\x00"
    b"\xee\xd8\xda*\x00\x00\x00\x00IEND\xaeB`\x82"
)


class Group2ServiceTest(unittest.TestCase):
    def test_solve_slider_gap_uses_python_runtime_and_maps_business_result(self) -> None:
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

            runtime_result = Mock()
            runtime_result.target_bbox = (80, 24, 120, 64)
            runtime_result.execution_provider = "CPUExecutionProvider"
            runtime_result.runtime_target = "python-onnxruntime"

            with patch(
                "sinanz_group2_service.group2_runtime.match_slider_gap",
                return_value=runtime_result,
            ) as match_mock:
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
            self.assertIn("runtime=python-onnxruntime", result.debug.notes)
            self.assertIn("model=slider_gap_locator.onnx", result.debug.notes)

    def test_solve_slider_gap_accepts_binary_image_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            asset_root = root / "assets"
            model_path = asset_root / "slider_gap_locator.onnx"
            model_path.parent.mkdir(parents=True, exist_ok=True)
            model_path.write_bytes(b"onnx")

            runtime_result = Mock()
            runtime_result.target_bbox = (80, 24, 120, 64)
            runtime_result.execution_provider = "CPUExecutionProvider"
            runtime_result.runtime_target = "python-onnxruntime"

            def _assert_temp_inputs(**kwargs):  # type: ignore[no-untyped-def]
                background_path = kwargs["background_image_path"]
                tile_path = kwargs["puzzle_piece_image_path"]
                self.assertTrue(background_path.exists())
                self.assertTrue(tile_path.exists())
                return runtime_result

            with patch(
                "sinanz_group2_service.group2_runtime.match_slider_gap",
                side_effect=_assert_temp_inputs,
            ):
                result = solve_slider_gap(
                    background_image=PNG_BYTES,
                    puzzle_piece_image=PNG_BYTES,
                    puzzle_piece_start_bbox=None,
                    device="auto",
                    asset_root=asset_root,
                    return_debug=False,
                )

            self.assertEqual(result.target_center, (100, 44))


if __name__ == "__main__":
    unittest.main()
