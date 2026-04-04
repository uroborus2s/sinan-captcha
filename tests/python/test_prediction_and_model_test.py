from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from core.modeltest.service import ModelTestRequest, run_model_test
from core.predict import cli as predict_cli


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

            def fake_run(command: list[str], check: bool) -> SimpleNamespace:
                self.assertTrue(check)
                if "predict" in command:
                    predict_output = project_dir / "predict_firstpass"
                    predict_output.mkdir(parents=True, exist_ok=True)
                    (predict_output / "sample_0001.png").write_bytes(b"png")
                elif "val" in command:
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
                return SimpleNamespace(returncode=0)

            with patch("core.modeltest.service._ensure_training_dependencies") as ensure_deps:
                with patch("core.modeltest.service.subprocess.run", side_effect=fake_run) as subprocess_run:
                    ensure_deps.return_value = None
                    result = run_model_test(
                        ModelTestRequest(
                            task="group1",
                            dataset_version="firstpass",
                            train_name="firstpass",
                            dataset_yaml=dataset_yaml,
                            model_path=model_path,
                            source=source_dir,
                            project_dir=project_dir,
                            report_dir=report_dir,
                            predict_name="predict_firstpass",
                            val_name="val_firstpass",
                        )
                    )

            self.assertEqual(subprocess_run.call_count, 2)
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


if __name__ == "__main__":
    unittest.main()
