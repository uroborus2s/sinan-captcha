from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.release.solver_export import (
    ExportedOnnxInfo,
    ExportGroup2SolverAssetsRequest,
    export_group2_solver_assets,
)


class Group2SolverAssetExportTests(unittest.TestCase):
    def test_export_group2_solver_assets_writes_manifest_metadata_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            checkpoint_path = project_dir / "runs" / "group2" / "firstpass" / "weights" / "best.pt"
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            checkpoint_path.write_text("checkpoint", encoding="utf-8")
            output_dir = project_dir / "dist" / "solver-assets" / "20260405"

            request = ExportGroup2SolverAssetsRequest(
                project_dir=project_dir,
                group2_checkpoint=checkpoint_path,
                output_dir=output_dir,
                asset_version="20260405",
                group2_run="firstpass",
                exported_at="2026-04-05T12:00:00Z",
            )

            with patch("core.release.solver_export._export_group2_onnx_from_checkpoint") as export_mock:
                export_mock.side_effect = self._write_fake_onnx
                result = export_group2_solver_assets(request)

            manifest_payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            model_metadata = json.loads(result.model_metadata_path.read_text(encoding="utf-8"))
            report_payload = json.loads(result.export_report_path.read_text(encoding="utf-8"))
            click_matcher_payload = json.loads((output_dir / "metadata" / "click_matcher.json").read_text(encoding="utf-8"))
            class_names_payload = json.loads((output_dir / "metadata" / "class_names.json").read_text(encoding="utf-8"))

            self.assertEqual(
                export_mock.call_args.kwargs,
                {
                    "checkpoint_path": checkpoint_path,
                    "output_path": output_dir / "models" / "slider_gap_locator.onnx",
                    "opset": 17,
                },
            )
            self.assertEqual(manifest_payload["asset_version"], "20260405")
            self.assertEqual(manifest_payload["runtime"]["target"], "python-onnxruntime")
            self.assertEqual(
                manifest_payload["models"]["slider_gap_locator"]["path"],
                "models/slider_gap_locator.onnx",
            )
            self.assertEqual(
                manifest_payload["models"]["slider_gap_locator"]["input"]["names"],
                ["master_image", "tile_image"],
            )
            self.assertEqual(
                manifest_payload["models"]["slider_gap_locator"]["output"]["names"],
                ["response_map"],
            )
            self.assertEqual(
                model_metadata["preferred_execution_providers"],
                ["CUDAExecutionProvider", "CPUExecutionProvider"],
            )
            self.assertEqual(model_metadata["input"]["image_size"], [192, 192])
            self.assertEqual(report_payload["group1_run"], "")
            self.assertEqual(report_payload["group2_run"], "firstpass")
            self.assertEqual(
                report_payload["exported_models"][0]["source_checkpoint"],
                "runs/group2/firstpass/weights/best.pt",
            )
            self.assertEqual(
                report_payload["exported_models"][0]["exported_model_path"],
                "models/slider_gap_locator.onnx",
            )
            self.assertEqual(
                report_payload["exported_models"][0]["exported_metadata_path"],
                "metadata/slider_gap_locator.json",
            )
            self.assertEqual(len(report_payload["exported_models"][0]["sha256"]), 64)
            self.assertEqual(
                click_matcher_payload["status"],
                "pending_TASK-SOLVER-MIG-009",
            )
            self.assertEqual(
                class_names_payload["status"],
                "pending_TASK-SOLVER-MIG-009",
            )

    @staticmethod
    def _write_fake_onnx(*, checkpoint_path: Path, output_path: Path, opset: int) -> ExportedOnnxInfo:
        del checkpoint_path, opset
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-onnx")
        return ExportedOnnxInfo(image_size=192, opset=17)


if __name__ == "__main__":
    unittest.main()
