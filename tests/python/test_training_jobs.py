import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
from unittest.mock import patch

from core.train.base import prepare_dataset_yaml_for_ultralytics
from core.train.group1 import cli as group1_cli
from core.train.group1.service import build_group1_training_job
from core.train.group2 import cli as group2_cli
from core.train.group2.service import build_group2_training_job


class TrainingJobTests(unittest.TestCase):
    def test_group1_uses_expected_defaults(self) -> None:
        job = build_group1_training_job(Path("datasets/group1/v1/yolo/dataset.yaml"), Path("runs/group1"))
        command = job.command()
        self.assertIn("model=yolo26n.pt", command)
        self.assertIn("epochs=120", command)

    def test_group2_uses_expected_defaults(self) -> None:
        job = build_group2_training_job(Path("datasets/group2/v1/yolo/dataset.yaml"), Path("runs/group2"))
        command = job.command()
        self.assertIn("model=yolo26n.pt", command)
        self.assertIn("epochs=100", command)

    def test_group1_allows_runtime_overrides(self) -> None:
        job = build_group1_training_job(
            Path("datasets/group1/v1/yolo/dataset.yaml"),
            Path("runs/group1"),
            model="yolo26s.pt",
            run_name="firstpass",
            epochs=12,
            batch=8,
            imgsz=512,
            device="cpu",
        )
        command = job.command()
        self.assertIn("model=yolo26s.pt", command)
        self.assertIn("epochs=12", command)
        self.assertIn("batch=8", command)
        self.assertIn("imgsz=512", command)
        self.assertIn("device=cpu", command)

    def test_group1_cli_dry_run_prints_command(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = group1_cli.main(
                [
                    "--dataset-yaml",
                    "datasets/group1/v1/yolo/dataset.yaml",
                    "--project",
                    "runs/group1",
                    "--dry-run",
                    "--batch",
                    "8",
                ]
            )
        self.assertEqual(code, 0)
        output = buffer.getvalue()
        self.assertIn("uv run yolo detect train", output)
        self.assertIn("batch=8", output)
        self.assertIn("data=datasets/group1/v1/yolo/dataset.yaml", output)

    def test_group1_cli_uses_default_paths_from_training_root(self) -> None:
        buffer = io.StringIO()
        with patch("core.train.group1.cli.Path.cwd", return_value=Path("D:/sinan-captcha-work")):
            with redirect_stdout(buffer):
                code = group1_cli.main(
                    [
                        "--dataset-version",
                        "firstpass",
                        "--name",
                        "smoke",
                        "--dry-run",
                    ]
                )
        self.assertEqual(code, 0)
        output = buffer.getvalue()
        self.assertIn("data=D:/sinan-captcha-work/datasets/group1/firstpass/yolo/dataset.yaml", output)
        self.assertIn("project=D:/sinan-captcha-work/runs/group1", output)
        self.assertIn("name=smoke", output)

    def test_group1_cli_uses_previous_best_checkpoint_from_training_root(self) -> None:
        buffer = io.StringIO()
        with patch("core.train.group1.cli.Path.cwd", return_value=Path("D:/sinan-captcha-work")):
            with redirect_stdout(buffer):
                code = group1_cli.main(
                    [
                        "--dataset-version",
                        "firstpass_v2",
                        "--name",
                        "round2",
                        "--from-run",
                        "firstpass",
                        "--dry-run",
                    ]
                )
        self.assertEqual(code, 0)
        output = buffer.getvalue()
        self.assertIn("data=D:/sinan-captcha-work/datasets/group1/firstpass_v2/yolo/dataset.yaml", output)
        self.assertIn("model=D:/sinan-captcha-work/runs/group1/firstpass/weights/best.pt", output)
        self.assertIn("name=round2", output)

    def test_group1_cli_resumes_same_run_from_last_checkpoint(self) -> None:
        buffer = io.StringIO()
        with patch("core.train.group1.cli.Path.cwd", return_value=Path("D:/sinan-captcha-work")):
            with redirect_stdout(buffer):
                code = group1_cli.main(
                    [
                        "--name",
                        "firstpass",
                        "--resume",
                        "--dry-run",
                    ]
                )
        self.assertEqual(code, 0)
        output = buffer.getvalue()
        self.assertIn("uv run yolo detect train resume", output)
        self.assertIn("model=D:/sinan-captcha-work/runs/group1/firstpass/weights/last.pt", output)

    def test_group2_cli_executes_training_command(self) -> None:
        with patch("core.train.base._ensure_training_dependencies") as ensure_deps:
            with patch("core.train.base.prepare_dataset_yaml_for_ultralytics") as normalize_dataset:
                with patch("core.train.base.subprocess.run") as subprocess_run:
                    ensure_deps.return_value = None
                    normalize_dataset.return_value = Path("datasets/group2/v1/yolo/.sinan/dataset.ultralytics.yaml")
                    subprocess_run.return_value.returncode = 0
                    code = group2_cli.main(
                        [
                            "--dataset-yaml",
                            "datasets/group2/v1/yolo/dataset.yaml",
                            "--project",
                            "runs/group2",
                            "--name",
                            "firstpass",
                        ]
                    )
        self.assertEqual(code, 0)
        subprocess_run.assert_called_once()
        command = subprocess_run.call_args.args[0]
        self.assertEqual(command[0], "uv")
        self.assertEqual(command[1], "run")
        self.assertEqual(command[2], "yolo")
        self.assertIn("data=datasets/group2/v1/yolo/.sinan/dataset.ultralytics.yaml", command)
        self.assertIn("epochs=100", command)
        self.assertIn("name=firstpass", command)

    def test_group2_cli_uses_default_paths_from_training_root(self) -> None:
        buffer = io.StringIO()
        with patch("core.train.group2.cli.Path.cwd", return_value=Path("D:/sinan-captcha-work")):
            with redirect_stdout(buffer):
                code = group2_cli.main(
                    [
                        "--dataset-version",
                        "firstpass",
                        "--name",
                        "smoke",
                        "--dry-run",
                    ]
                )
        self.assertEqual(code, 0)
        output = buffer.getvalue()
        self.assertIn("data=D:/sinan-captcha-work/datasets/group2/firstpass/yolo/dataset.yaml", output)
        self.assertIn("project=D:/sinan-captcha-work/runs/group2", output)
        self.assertIn("name=smoke", output)

    def test_prepare_dataset_yaml_rewrites_relative_path_for_ultralytics(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_dir = Path(tmpdir) / "datasets" / "group1" / "firstpass" / "yolo"
            dataset_dir.mkdir(parents=True)
            dataset_yaml = dataset_dir / "dataset.yaml"
            dataset_yaml.write_text(
                "path: .\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: icon_house\n",
                encoding="utf-8",
            )

            normalized = prepare_dataset_yaml_for_ultralytics(dataset_yaml)

            self.assertEqual(normalized.name, "dataset.ultralytics.yaml")
            self.assertTrue(normalized.exists())
            normalized_content = normalized.read_text(encoding="utf-8")
            self.assertIn(f"path: {dataset_dir.resolve().as_posix()}", normalized_content)
            self.assertIn("train: images/train", normalized_content)

    def test_prepare_dataset_yaml_keeps_yaml_without_path_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_dir = Path(tmpdir) / "datasets" / "group1" / "firstpass" / "yolo"
            dataset_dir.mkdir(parents=True)
            dataset_yaml = dataset_dir / "dataset.yaml"
            dataset_yaml.write_text(
                "train: images/train\nval: images/val\ntest: images/test\nnames:\n  0: icon_house\n",
                encoding="utf-8",
            )

            normalized = prepare_dataset_yaml_for_ultralytics(dataset_yaml)

            self.assertEqual(normalized, dataset_yaml)


if __name__ == "__main__":
    unittest.main()
