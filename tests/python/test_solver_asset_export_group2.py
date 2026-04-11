from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.release.solver_export import (
    ExportedOnnxInfo,
    ExportGroup2SolverAssetsRequest,
    ExportSolverAssetsRequest,
    export_group2_solver_assets,
    export_solver_assets,
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

    def test_export_solver_assets_writes_group1_onnx_assets_matcher_metadata_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            group1_run = "g1_instance"
            group2_run = "g2_firstpass"
            proposal_checkpoint = project_dir / "runs" / "group1" / group1_run / "proposal-detector" / "weights" / "best.pt"
            query_checkpoint = project_dir / "runs" / "group1" / group1_run / "query-parser" / "weights" / "best.pt"
            embedder_checkpoint = project_dir / "runs" / "group1" / group1_run / "icon-embedder" / "weights" / "best.pt"
            group2_checkpoint = project_dir / "runs" / "group2" / group2_run / "weights" / "best.pt"
            for path in (proposal_checkpoint, query_checkpoint, embedder_checkpoint, group2_checkpoint):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("checkpoint", encoding="utf-8")
            output_dir = project_dir / "dist" / "solver-assets" / "20260411"

            request = ExportSolverAssetsRequest(
                project_dir=project_dir,
                group2_checkpoint=group2_checkpoint,
                output_dir=output_dir,
                asset_version="20260411",
                group2_run=group2_run,
                group1_run=group1_run,
                group1_proposal_checkpoint=proposal_checkpoint,
                group1_query_checkpoint=query_checkpoint,
                group1_embedder_checkpoint=embedder_checkpoint,
                exported_at="2026-04-11T08:00:00Z",
            )

            with (
                patch("core.release.solver_export._export_yolo_onnx_from_checkpoint") as yolo_export,
                patch("core.release.solver_export._export_icon_embedder_onnx_from_checkpoint") as embedder_export,
                patch("core.release.solver_export._export_group2_onnx_from_checkpoint") as group2_export,
            ):
                yolo_export.side_effect = self._write_fake_yolo_onnx
                embedder_export.side_effect = self._write_fake_embedder_onnx
                group2_export.side_effect = self._write_fake_onnx
                result = export_solver_assets(request)

            manifest_payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            report_payload = json.loads(result.export_report_path.read_text(encoding="utf-8"))
            matcher_payload = json.loads((output_dir / "metadata" / "click_matcher.json").read_text(encoding="utf-8"))
            class_names_payload = json.loads((output_dir / "metadata" / "class_names.json").read_text(encoding="utf-8"))

            self.assertEqual(
                yolo_export.call_args_list[0].kwargs,
                {
                    "checkpoint_path": proposal_checkpoint,
                    "output_path": output_dir / "models" / "click_proposal_detector.onnx",
                    "opset": 17,
                },
            )
            self.assertEqual(
                yolo_export.call_args_list[1].kwargs,
                {
                    "checkpoint_path": query_checkpoint,
                    "output_path": output_dir / "models" / "click_query_parser.onnx",
                    "opset": 17,
                },
            )
            self.assertEqual(
                embedder_export.call_args.kwargs,
                {
                    "checkpoint_path": embedder_checkpoint,
                    "output_path": output_dir / "models" / "click_icon_embedder.onnx",
                    "opset": 17,
                },
            )
            self.assertEqual(
                set(manifest_payload["models"]),
                {
                    "click_proposal_detector",
                    "click_query_parser",
                    "click_icon_embedder",
                    "slider_gap_locator",
                },
            )
            self.assertEqual(
                manifest_payload["models"]["click_icon_embedder"]["path"],
                "models/click_icon_embedder.onnx",
            )
            self.assertEqual(
                manifest_payload["models"]["click_icon_embedder"]["output"]["names"],
                ["embedding"],
            )
            self.assertEqual(matcher_payload["strategy"], "global_assignment_match_v1")
            self.assertEqual(matcher_payload["models"]["proposal_detector"], "click_proposal_detector")
            self.assertEqual(matcher_payload["models"]["query_parser"], "click_query_parser")
            self.assertEqual(matcher_payload["models"]["icon_embedder"], "click_icon_embedder")
            self.assertEqual(matcher_payload["similarity_threshold"], 0.9)
            self.assertEqual(matcher_payload["ambiguity_margin"], 0.015)
            self.assertEqual(class_names_payload["status"], "instance_matching_v1")
            self.assertEqual(report_payload["group1_run"], group1_run)
            self.assertEqual(report_payload["group2_run"], group2_run)
            self.assertEqual(
                [record["model_id"] for record in report_payload["exported_models"]],
                [
                    "click_proposal_detector",
                    "click_query_parser",
                    "click_icon_embedder",
                    "slider_gap_locator",
                ],
            )
            for record in report_payload["exported_models"]:
                self.assertFalse(record["source_checkpoint"].startswith("/"))
                self.assertEqual(len(record["sha256"]), 64)

    @staticmethod
    def _write_fake_onnx(*, checkpoint_path: Path, output_path: Path, opset: int) -> ExportedOnnxInfo:
        del checkpoint_path, opset
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-onnx")
        return ExportedOnnxInfo(image_size=192, opset=17)

    @staticmethod
    def _write_fake_yolo_onnx(*, checkpoint_path: Path, output_path: Path, opset: int) -> ExportedOnnxInfo:
        del checkpoint_path, opset
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-yolo-onnx")
        return ExportedOnnxInfo(image_size=640, opset=17)

    @staticmethod
    def _write_fake_embedder_onnx(*, checkpoint_path: Path, output_path: Path, opset: int) -> ExportedOnnxInfo:
        del checkpoint_path, opset
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-embedder-onnx")
        return ExportedOnnxInfo(image_size=64, opset=17)


if __name__ == "__main__":
    unittest.main()
