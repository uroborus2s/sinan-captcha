from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core.modeltest.service import ModelTestRequest, run_model_test
from core.predict import cli as predict_cli
from core.train.group1.service import Group1PredictionResult
from core.train.group2.service import Group2PredictionResult


class PredictionCliTests(unittest.TestCase):
    def test_group1_predict_cli_uses_default_paths_from_training_root(self) -> None:
        buffer = io.StringIO()
        with patch("core.predict.cli.Path.cwd", return_value=Path("D:/sinan-captcha-work")):
            with redirect_stdout(buffer):
                code = predict_cli.main(
                    [
                        "group1",
                        "--dataset-version",
                        "firstpass",
                        "--train-name",
                        "firstpass",
                        "--dry-run",
                    ]
                )
        self.assertEqual(code, 0)
        output = buffer.getvalue()
        self.assertIn("uv run python -m core.train.group1.runner predict", output)
        self.assertIn("--dataset-config D:/sinan-captcha-work/datasets/group1/firstpass/dataset.json", output)
        self.assertIn("--proposal-model D:/sinan-captcha-work/runs/group1/firstpass/proposal-detector/weights/best.pt", output)
        self.assertIn("--query-model D:/sinan-captcha-work/runs/group1/firstpass/query-parser/weights/best.pt", output)
        self.assertIn("--source D:/sinan-captcha-work/datasets/group1/firstpass/splits/val.jsonl", output)
        self.assertIn("--project D:/sinan-captcha-work/reports/group1", output)
        self.assertIn("--name predict_firstpass", output)

    def test_group2_predict_cli_uses_paired_dataset_defaults(self) -> None:
        buffer = io.StringIO()
        with patch("core.predict.cli.Path.cwd", return_value=Path("D:/sinan-captcha-work")):
            with redirect_stdout(buffer):
                code = predict_cli.main(
                    [
                        "group2",
                        "--dataset-version",
                        "firstpass",
                        "--train-name",
                        "firstpass",
                        "--dry-run",
                    ]
                )
        self.assertEqual(code, 0)
        output = buffer.getvalue()
        self.assertIn("uv run python -m core.train.group2.runner predict", output)
        self.assertIn("--dataset-config D:/sinan-captcha-work/datasets/group2/firstpass/dataset.json", output)
        self.assertIn("--source D:/sinan-captcha-work/datasets/group2/firstpass/splits/val.jsonl", output)
        self.assertIn("--model D:/sinan-captcha-work/runs/group2/firstpass/weights/best.pt", output)
        self.assertIn("--project D:/sinan-captcha-work/reports/group2", output)
        self.assertIn("--name predict_firstpass", output)


class ModelTestServiceTests(unittest.TestCase):
    def test_group1_model_test_runs_predict_and_evaluate_and_writes_beginner_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dataset_dir = root / "datasets" / "group1" / "firstpass"
            (dataset_dir / "splits").mkdir(parents=True)
            dataset_config = dataset_dir / "dataset.json"
            dataset_config.write_text(
                (
                    "{\n"
                    '  "task": "group1",\n'
                    '  "format": "sinan.group1.instance_matching.v1",\n'
                    '  "splits": {\n'
                    '    "train": "splits/train.jsonl",\n'
                    '    "val": "splits/val.jsonl",\n'
                    '    "test": "splits/test.jsonl"\n'
                    "  },\n"
                    '  "proposal_detector": {"format":"yolo.detect.v1","dataset_yaml":"proposal-yolo/dataset.yaml"},\n'
                    '  "embedding": {"format":"sinan.group1.embedding.v1","queries_dir":"embedding/queries","candidates_dir":"embedding/candidates","pairs_jsonl":"embedding/pairs.jsonl","triplets_jsonl":"embedding/triplets.jsonl"},\n'
                    '  "eval": {"format":"sinan.group1.eval.v1","labels_jsonl":"eval/labels.jsonl"}\n'
                    "}\n"
                ),
                encoding="utf-8",
            )
            source = dataset_dir / "splits" / "val.jsonl"
            source.write_text(
                (
                    '{"sample_id":"g1_000001","query_image":"eval/query/val/g1_000001.png",'
                    '"scene_image":"eval/scene/val/g1_000001.png","query_items":[{"order":1,"asset_id":"asset_house","template_id":"tpl_house","variant_id":"var_outline",'
                    '"bbox":[8,8,28,28],"center":[18,18]}],"scene_targets":[{"order":1,"asset_id":"asset_house","template_id":"tpl_house",'
                    '"variant_id":"var_outline","bbox":[80,32,120,72],"center":[100,52]}],"distractors":[],"label_source":"gold",'
                    '"source_batch":"batch_0001"}\n'
                ),
                encoding="utf-8",
            )
            proposal_model_path = root / "runs" / "group1" / "firstpass" / "proposal-detector" / "weights" / "best.pt"
            query_model_path = root / "runs" / "group1" / "firstpass" / "query-parser" / "weights" / "best.pt"
            proposal_model_path.parent.mkdir(parents=True)
            query_model_path.parent.mkdir(parents=True)
            proposal_model_path.write_bytes(b"pt")
            query_model_path.write_bytes(b"pt")

            project_dir = root / "reports" / "group1"
            report_dir = project_dir / "test_firstpass"
            with patch("core.modeltest.service._ensure_training_dependencies") as ensure_deps:
                with patch("core.modeltest.service.run_group1_prediction_job") as run_predict:
                    with patch("core.modeltest.service.evaluate_model") as evaluate_model:
                        ensure_deps.return_value = None
                        run_predict.return_value = Group1PredictionResult(
                            output_dir=project_dir / "predict_firstpass",
                            labels_path=project_dir / "predict_firstpass" / "labels.jsonl",
                            sample_count=1,
                            command="uv run python -m core.train.group1.runner predict ...",
                        )
                        evaluate_model.return_value = type("EvalResult", (), {
                            "task": "group1",
                            "sample_count": 1,
                            "failure_count": 0,
                            "metrics": {
                                "single_target_hit_rate": 1.0,
                                "full_sequence_hit_rate": 1.0,
                                "mean_center_error_px": 0.0,
                                "order_error_rate": 0.0,
                            },
                            "report_dir": project_dir / "val_firstpass",
                        })()

                        result = run_model_test(
                            ModelTestRequest(
                                task="group1",
                                dataset_version="firstpass",
                                train_name="firstpass",
                                dataset_config=dataset_config,
                                model_path=proposal_model_path,
                                query_model_path=query_model_path,
                                source=source,
                                project_dir=project_dir,
                                report_dir=report_dir,
                                predict_name="predict_firstpass",
                                val_name="val_firstpass",
                            )
                        )

            self.assertEqual(result.task, "group1")
            self.assertEqual(result.source_image_count, 1)
            self.assertAlmostEqual(result.metrics["full_sequence_hit_rate"], 1.0)
            summary_md = (report_dir / "summary.md").read_text(encoding="utf-8")
            self.assertIn("初学者结论", summary_md)
            self.assertIn("这轮双模型点击流水线已经比较稳", summary_md)
            self.assertIn("位置挑选", summary_md)
            self.assertIn("整组命中率", summary_md)
            self.assertIn("顺序错误率", summary_md)
            self.assertIn(str(project_dir / "predict_firstpass"), summary_md)
            console_report = result.render_console_report()
            self.assertIn("模型测试完成", console_report)
            self.assertIn("位置挑选", console_report)
            self.assertIn("下一步建议", console_report)

    def test_group2_model_test_runs_predict_and_evaluate_and_writes_beginner_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dataset_dir = root / "datasets" / "group2" / "firstpass"
            (dataset_dir / "splits").mkdir(parents=True)
            dataset_config = dataset_dir / "dataset.json"
            dataset_config.write_text(
                (
                    "{\n"
                    '  "task": "group2",\n'
                    '  "format": "sinan.group2.paired.v1",\n'
                    '  "splits": {\n'
                    '    "train": "splits/train.jsonl",\n'
                    '    "val": "splits/val.jsonl",\n'
                    '    "test": "splits/test.jsonl"\n'
                    "  }\n"
                    "}\n"
                ),
                encoding="utf-8",
            )
            source = dataset_dir / "splits" / "val.jsonl"
            source.write_text(
                (
                    '{"sample_id":"g2_000001","master_image":"master/val/g2_000001.png",'
                    '"tile_image":"tile/val/g2_000001.png","target_gap":{"class":"slider_gap","class_id":0,'
                    '"bbox":[80,24,120,64],"center":[100,44]},"tile_bbox":[0,24,40,64],'
                    '"offset_x":80,"offset_y":0,"label_source":"gold","source_batch":"batch_0001"}\n'
                ),
                encoding="utf-8",
            )
            model_path = root / "runs" / "group2" / "firstpass" / "weights" / "best.pt"
            model_path.parent.mkdir(parents=True)
            model_path.write_bytes(b"pt")
            project_dir = root / "reports" / "group2"
            report_dir = project_dir / "test_firstpass"

            with patch("core.modeltest.service._ensure_training_dependencies") as ensure_deps:
                with patch("core.modeltest.service.run_group2_prediction_job") as run_predict:
                    with patch("core.modeltest.service.evaluate_model") as evaluate_model:
                        ensure_deps.return_value = None
                        run_predict.return_value = Group2PredictionResult(
                            output_dir=project_dir / "predict_firstpass",
                            labels_path=project_dir / "predict_firstpass" / "labels.jsonl",
                            sample_count=1,
                            command="uv run python -m core.train.group2.runner predict ...",
                        )
                        evaluate_model.return_value = type("EvalResult", (), {
                            "task": "group2",
                            "sample_count": 1,
                            "failure_count": 0,
                            "metrics": {
                                "point_hit_rate": 1.0,
                                "mean_center_error_px": 2.0,
                                "mean_iou": 0.91,
                                "mean_inference_ms": 12.0,
                            },
                            "report_dir": project_dir / "val_firstpass",
                        })()

                        result = run_model_test(
                            ModelTestRequest(
                                task="group2",
                                dataset_version="firstpass",
                                train_name="firstpass",
                                dataset_config=dataset_config,
                                model_path=model_path,
                                query_model_path=None,
                                source=source,
                                project_dir=project_dir,
                                report_dir=report_dir,
                                predict_name="predict_firstpass",
                                val_name="val_firstpass",
                            )
                        )

            self.assertEqual(result.task, "group2")
            self.assertEqual(result.source_image_count, 1)
            self.assertAlmostEqual(result.metrics["point_hit_rate"], 1.0)
            self.assertAlmostEqual(result.metrics["mean_iou"], 0.91)
            summary_md = (report_dir / "summary.md").read_text(encoding="utf-8")
            self.assertIn("点位命中率", summary_md)
            self.assertIn("mean_iou", summary_md)
            self.assertIn("predict", result.predict_command)
            self.assertIn("evaluate", result.val_command)


if __name__ == "__main__":
    unittest.main()
