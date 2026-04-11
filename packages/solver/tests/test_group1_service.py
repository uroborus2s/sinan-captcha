from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from sinanz_group1_service import solve_click_targets


class Group1ServiceTest(unittest.TestCase):
    def test_solve_click_targets_uses_python_runtime_and_maps_business_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            query = root / "query.png"
            background = root / "background.png"
            asset_root = root / "assets"
            proposal_model = asset_root / "click_proposal_detector.onnx"
            query_model = asset_root / "click_query_parser.onnx"
            embedder_model = asset_root / "click_icon_embedder.onnx"
            query.write_bytes(b"query")
            background.write_bytes(b"background")
            asset_root.mkdir(parents=True, exist_ok=True)
            proposal_model.write_bytes(b"onnx")
            query_model.write_bytes(b"onnx")
            embedder_model.write_bytes(b"onnx")

            runtime_target = Mock(query_order=1, center=(120, 40), bbox=(100, 20, 140, 60), score=0.97)
            runtime_result = Mock()
            runtime_result.ordered_targets = [runtime_target]
            runtime_result.missing_orders = []
            runtime_result.ambiguous_orders = []
            runtime_result.execution_provider = "CPUExecutionProvider"
            runtime_result.runtime_target = "python-onnxruntime"

            with patch(
                "sinanz_group1_service.group1_runtime.match_click_targets",
                return_value=runtime_result,
            ) as match_mock:
                result = solve_click_targets(
                    query_icons_image=query,
                    background_image=background,
                    device="auto",
                    asset_root=asset_root,
                    return_debug=True,
                )

            match_mock.assert_called_once_with(
                proposal_model_path=proposal_model,
                query_model_path=query_model,
                embedder_model_path=embedder_model,
                query_image_path=query,
                background_image_path=background,
                device="auto",
            )
            self.assertEqual(result.ordered_target_centers, [(120, 40)])
            self.assertEqual(result.ordered_targets[0].query_order, 1)
            self.assertEqual(result.ordered_targets[0].score, 0.97)
            self.assertEqual(result.missing_query_orders, [])
            self.assertEqual(result.ambiguous_query_orders, [])
            self.assertIsNotNone(result.debug)
            self.assertIn("provider=CPUExecutionProvider", result.debug.notes)
            self.assertIn("runtime=python-onnxruntime", result.debug.notes)
            self.assertIn("model=click_proposal_detector.onnx", result.debug.notes)
            self.assertIn("embedder=click_icon_embedder.onnx", result.debug.notes)


if __name__ == "__main__":
    unittest.main()
