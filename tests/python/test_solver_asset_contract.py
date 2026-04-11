from __future__ import annotations

import unittest

from release import solver_asset_contract as contract


class SolverAssetContractTests(unittest.TestCase):
    def test_named_onnx_assets_are_stable(self) -> None:
        self.assertEqual(contract.SOLVER_ASSET_FORMAT, "sinan.solver.assets.v1")
        self.assertEqual(contract.RUNTIME_TARGET, "python-onnxruntime")
        self.assertEqual(
            contract.MODEL_FILENAMES,
            {
                "click_proposal_detector": "click_proposal_detector.onnx",
                "click_query_parser": "click_query_parser.onnx",
                "click_icon_embedder": "click_icon_embedder.onnx",
                "slider_gap_locator": "slider_gap_locator.onnx",
            },
        )

    def test_manifest_payload_contains_runtime_and_relative_paths(self) -> None:
        scene = contract.SolverOnnxModelAsset(
            model_id="click_proposal_detector",
            task="group1",
            component="proposal_detector",
            opset=17,
            input_names=("images",),
            output_names=("predictions",),
            image_size=(640, 640),
            postprocess="yolo_detect_v1",
        )
        query = contract.SolverOnnxModelAsset(
            model_id="click_query_parser",
            task="group1",
            component="query_parser",
            opset=17,
            input_names=("images",),
            output_names=("predictions",),
            image_size=(320, 320),
            postprocess="yolo_detect_v1",
        )
        embedder = contract.SolverOnnxModelAsset(
            model_id="click_icon_embedder",
            task="group1",
            component="icon_embedder",
            opset=17,
            input_names=("icon_crop",),
            output_names=("embedding",),
            image_size=(64, 64),
            postprocess="normalized_embedding_v1",
        )
        gap = contract.SolverOnnxModelAsset(
            model_id="slider_gap_locator",
            task="group2",
            component="locator",
            opset=17,
            input_names=("master_image", "tile_image"),
            output_names=("bbox",),
            image_size=(192, 192),
            postprocess="paired_gap_bbox_v1",
        )

        manifest = contract.SolverAssetManifest(
            asset_version="20260405",
            exported_at="2026-04-05T12:00:00Z",
            model_assets=(scene, query, embedder, gap),
        )
        payload = manifest.to_dict()

        self.assertEqual(payload["asset_format"], "sinan.solver.assets.v1")
        self.assertEqual(payload["runtime"]["target"], "python-onnxruntime")
        self.assertEqual(
            payload["runtime"]["preferred_execution_providers"],
            ["CUDAExecutionProvider", "CPUExecutionProvider"],
        )
        self.assertEqual(
            payload["models"]["slider_gap_locator"]["path"],
            "models/slider_gap_locator.onnx",
        )
        self.assertEqual(
            payload["models"]["click_proposal_detector"]["metadata"],
            "metadata/click_proposal_detector.json",
        )
        self.assertEqual(
            payload["models"]["click_icon_embedder"]["output"]["postprocess"],
            "normalized_embedding_v1",
        )
        self.assertEqual(
            payload["models"]["slider_gap_locator"]["input"]["image_size"],
            [192, 192],
        )
        self.assertEqual(
            payload["metadata_files"]["export_report"],
            "metadata/export_report.json",
        )

    def test_export_report_payload_tracks_runs_and_artifacts_without_absolute_paths(self) -> None:
        report = contract.SolverAssetExportReport(
            asset_version="20260405",
            group1_run="g1_firstpass",
            group2_run="g2_firstpass",
            exported_at="2026-04-05T12:00:00Z",
            exported_models=(
                contract.ExportedModelRecord(
                    model_id="click_proposal_detector",
                    source_checkpoint="runs/group1/g1_firstpass/proposal-detector/weights/best.pt",
                    exported_model_path="models/click_proposal_detector.onnx",
                    exported_metadata_path="metadata/click_proposal_detector.json",
                    sha256="abc123",
                ),
                contract.ExportedModelRecord(
                    model_id="slider_gap_locator",
                    source_checkpoint="runs/group2/g2_firstpass/weights/best.pt",
                    exported_model_path="models/slider_gap_locator.onnx",
                    exported_metadata_path="metadata/slider_gap_locator.json",
                    sha256="def456",
                ),
            ),
        )

        payload = report.to_dict()

        self.assertEqual(payload["group1_run"], "g1_firstpass")
        self.assertEqual(payload["group2_run"], "g2_firstpass")
        self.assertEqual(payload["exported_models"][0]["model_id"], "click_proposal_detector")
        self.assertFalse(payload["exported_models"][0]["source_checkpoint"].startswith("/"))
        self.assertFalse(payload["exported_models"][0]["exported_model_path"].startswith("/"))


if __name__ == "__main__":
    unittest.main()
