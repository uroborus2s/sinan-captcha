from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sinanz import native_bridge
from sinanz.errors import SolverRuntimeError


class NativeBridgeTest(unittest.TestCase):
    def test_native_bridge_exposes_stable_runtime_metadata(self) -> None:
        status = native_bridge.native_runtime_status()

        self.assertEqual(status.module_name, "sinanz_ext")
        self.assertEqual(status.runtime_target, "rust-onnxruntime")
        self.assertEqual(status.bridge_module, "sinanz.native_bridge")
        self.assertEqual(status.stage, "group2-onnx-bridge")
        self.assertEqual(status.feature_flags, ("python-extension", "onnx-runtime"))
        self.assertEqual(status.cargo_workspace_manifest, "Cargo.toml")
        self.assertEqual(status.crate_manifest, "native/sinanz_ext/Cargo.toml")

    def test_load_native_module_raises_clear_placeholder_error_before_pyo3_integration(self) -> None:
        with self.assertRaisesRegex(
            SolverRuntimeError,
            "sinanz_ext.*TASK-SOLVER-MIG-008/009/011",
        ):
            native_bridge.load_native_module()

    def test_match_slider_gap_normalizes_native_response(self) -> None:
        fake_module = SimpleNamespace(
            match_slider_gap=lambda **_: {
                "target_bbox": [80, 24, 120, 64],
                "execution_provider": "CPUExecutionProvider",
            }
        )

        with patch("sinanz.native_bridge.importlib.import_module", return_value=fake_module):
            result = native_bridge.match_slider_gap(
                model_path=Path("/tmp/slider_gap_locator.onnx"),
                background_image_path=Path("/tmp/background.png"),
                puzzle_piece_image_path=Path("/tmp/tile.png"),
                device="cpu",
            )

        self.assertEqual(result.target_bbox, (80, 24, 120, 64))
        self.assertEqual(result.execution_provider, "CPUExecutionProvider")


if __name__ == "__main__":
    unittest.main()
