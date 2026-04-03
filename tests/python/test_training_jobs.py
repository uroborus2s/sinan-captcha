import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

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

    def test_group2_cli_executes_training_command(self) -> None:
        with patch("core.train.base._ensure_training_dependencies") as ensure_deps:
            with patch("core.train.base.subprocess.run") as subprocess_run:
                ensure_deps.return_value = None
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
        self.assertIn("epochs=100", command)
        self.assertIn("name=firstpass", command)


if __name__ == "__main__":
    unittest.main()
