from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core.modeltest.service import ModelTestRequest, run_model_test
from core.predict import cli as predict_cli
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
        self.assertIn("uv run yolo detect predict", output)
        self.assertIn("model=D:/sinan-captcha-work/runs/group1/firstpass/weights/best.pt", output)
        self.assertIn("source=D:/sinan-captcha-work/datasets/group1/firstpass/yolo/images/val", output)
        self.assertIn("project=D:/sinan-captcha-work/reports/group1", output)
        self.assertIn("name=predict_firstpass", output)

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
    def test_group1_model_test_runs_predict_and_val_and_writes_beginner_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dataset_dir = root / "datasets" / "group1" / "firstpass" / "yolo"
            source_dir = dataset_dir / "images" / "val"
            source_dir.mkdir(parents=True)
            (source_dir / "sample_0001.png").write_bytes(b"png")
            dataset_yaml = dataset_dir / "dataset.yaml"
            dataset_yaml.write_text(
                "train: images/train\nval: images/val\ntest: images/test\nnames:\n  0: icon_house\n",
                encoding="utf-8",
            )
            model_path = root / "runs" / "group1" / "firstpass" / "weights" / "best.pt"
            model_path.parent.mkdir(parents=True)
            model_path.write_bytes(b"pt")

            project_dir = root / "reports" / "group1"
            report_dir = project_dir / "test_firstpass"

            def fake_exec(command: list[str]) -> str:
                if "predict" in command:
                    predict_output = project_dir / "predict_firstpass"
                    predict_output.mkdir(parents=True, exist_ok=True)
                    (predict_output / "sample_0001.png").write_bytes(b"png")
                    return "Results saved"
                if "val" in command:
                    val_output = project_dir / "val_firstpass"
                    val_output.mkdir(parents=True, exist_ok=True)
                    (val_output / "results.csv").write_text(
                        (
                            "epoch,metrics/precision(B),metrics/recall(B),"
                            "metrics/mAP50(B),metrics/mAP50-95(B),fitness\n"
                            "1,0.910000,0.860000,0.880000,0.710000,0.800000\n"
                        ),
                        encoding="utf-8",
                    )
                    return "Results saved"
                return ""

            with patch("core.modeltest.service._ensure_training_dependencies") as ensure_deps:
                with patch("core.modeltest.service._execute_and_capture_output", side_effect=fake_exec) as executor:
                    ensure_deps.return_value = None
                    result = run_model_test(
                        ModelTestRequest(
                            task="group1",
                            dataset_version="firstpass",
                            train_name="firstpass",
                            dataset_config=dataset_yaml,
                            model_path=model_path,
                            source=source_dir,
                            project_dir=project_dir,
                            report_dir=report_dir,
                            predict_name="predict_firstpass",
                            val_name="val_firstpass",
                        )
                    )

            self.assertEqual(executor.call_count, 2)
            self.assertEqual(result.task, "group1")
            self.assertEqual(result.source_image_count, 1)
            self.assertAlmostEqual(result.metrics["map50"], 0.88)
            summary_md = (report_dir / "summary.md").read_text(encoding="utf-8")
            self.assertIn("初学者结论", summary_md)
            self.assertIn("这轮模型已经比较稳", summary_md)
            self.assertIn("精确率", summary_md)
            self.assertIn("mAP50", summary_md)
            self.assertIn(str(project_dir / "predict_firstpass"), summary_md)
            console_report = result.render_console_report()
            self.assertIn("模型测试完成", console_report)
            self.assertIn("下一步建议", console_report)

    def test_group1_model_test_falls_back_to_parsing_val_stdout_when_results_csv_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dataset_dir = root / "datasets" / "group1" / "firstpass" / "yolo"
            source_dir = dataset_dir / "images" / "val"
            source_dir.mkdir(parents=True)
            (source_dir / "sample_0001.png").write_bytes(b"png")
            dataset_yaml = dataset_dir / "dataset.yaml"
            dataset_yaml.write_text(
                "train: images/train\nval: images/val\ntest: images/test\nnames:\n  0: icon_house\n",
                encoding="utf-8",
            )
            model_path = root / "runs" / "group1" / "firstpass" / "weights" / "best.pt"
            model_path.parent.mkdir(parents=True)
            model_path.write_bytes(b"pt")

            project_dir = root / "reports" / "group1"
            report_dir = project_dir / "test_firstpass"
            fake_val_output = "\n".join(
                [
                    "Ultralytics 8.3.43",
                    "                   all         20        160      0.905      0.876      0.971      0.827",
                    f"Results saved to {project_dir / 'val_firstpass'}",
                ]
            )

            def fake_exec(command: list[str]) -> str:
                if "predict" in command:
                    predict_output = project_dir / "predict_firstpass"
                    predict_output.mkdir(parents=True, exist_ok=True)
                    (predict_output / "sample_0001.png").write_bytes(b"png")
                    return "Results saved"
                val_output = project_dir / "val_firstpass"
                val_output.mkdir(parents=True, exist_ok=True)
                return fake_val_output

            with patch("core.modeltest.service._ensure_training_dependencies") as ensure_deps:
                with patch("core.modeltest.service._execute_and_capture_output", side_effect=fake_exec):
                    ensure_deps.return_value = None
                    result = run_model_test(
                        ModelTestRequest(
                            task="group1",
                            dataset_version="firstpass",
                            train_name="firstpass",
                            dataset_config=dataset_yaml,
                            model_path=model_path,
                            source=source_dir,
                            project_dir=project_dir,
                            report_dir=report_dir,
                            predict_name="predict_firstpass",
                            val_name="val_firstpass",
                        )
                    )

            self.assertAlmostEqual(result.metrics["precision"], 0.905)
            self.assertAlmostEqual(result.metrics["recall"], 0.876)
            self.assertAlmostEqual(result.metrics["map50"], 0.971)
            self.assertAlmostEqual(result.metrics["map50_95"], 0.827)
            self.assertTrue((report_dir / "summary.md").exists())

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
