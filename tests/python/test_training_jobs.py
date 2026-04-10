import io
import json
import struct
import unittest
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
from unittest.mock import patch
import zlib

from core.common.jsonl import read_jsonl
from core.train.base import prepare_dataset_yaml_for_ultralytics
from core.train.group1 import cli as group1_cli
from core.train.group1.service import build_group1_training_job
from core.train.group2 import cli as group2_cli
from core.train.group2.service import build_group2_prediction_job, build_group2_training_job, run_group2_prediction_job


def _write_png(path: Path, width: int, height: int, color: tuple[int, int, int]) -> None:
    raw_rows = []
    pixel = bytes(color)
    for _ in range(height):
        raw_rows.append(b"\x00" + pixel * width)
    payload = zlib.compress(b"".join(raw_rows))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack("!I", len(data))
            + kind
            + data
            + struct.pack("!I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    png = b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0)),
            chunk(b"IDAT", payload),
            chunk(b"IEND", b""),
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


class TrainingJobTests(unittest.TestCase):
    def test_group1_uses_expected_defaults(self) -> None:
        job = build_group1_training_job(Path("datasets/group1/v1/dataset.json"), Path("runs/group1"))
        command = job.command()
        self.assertEqual(command[:5], ["uv", "run", "python", "-m", "core.train.group1.runner"])
        self.assertIn("--dataset-config", command)
        self.assertIn("datasets/group1/v1/dataset.json", command)
        self.assertIn("--scene-model", command)
        self.assertIn("yolo26n.pt", command)
        self.assertIn("--query-model", command)
        self.assertIn("--epochs", command)
        self.assertIn("120", command)

    def test_group2_uses_expected_defaults(self) -> None:
        job = build_group2_training_job(Path("datasets/group2/v1/dataset.json"), Path("runs/group2"))
        command = job.command()
        self.assertEqual(command[:5], ["uv", "run", "python", "-m", "core.train.group2.runner"])
        self.assertIn("--dataset-config", command)
        self.assertIn("datasets/group2/v1/dataset.json", command)
        self.assertIn("--model", command)
        self.assertIn("paired_cnn_v1", command)
        self.assertIn("--epochs", command)
        self.assertIn("100", command)

    def test_group1_allows_runtime_overrides(self) -> None:
        job = build_group1_training_job(
            Path("datasets/group1/v1/dataset.json"),
            Path("runs/group1"),
            model="yolo26s.pt",
            run_name="firstpass",
            epochs=12,
            batch=8,
            imgsz=512,
            device="cpu",
        )
        command = job.command()
        self.assertIn("--scene-model", command)
        self.assertIn("yolo26s.pt", command)
        self.assertIn("--query-model", command)
        self.assertIn("--epochs", command)
        self.assertIn("12", command)
        self.assertIn("--batch", command)
        self.assertIn("8", command)
        self.assertIn("--imgsz", command)
        self.assertIn("512", command)
        self.assertIn("--device", command)
        self.assertIn("cpu", command)

    def test_group1_cli_dry_run_prints_command(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = group1_cli.main(
                [
                    "--dataset-config",
                    "datasets/group1/v1/dataset.json",
                    "--project",
                    "runs/group1",
                    "--dry-run",
                    "--batch",
                    "8",
                ]
            )
        self.assertEqual(code, 0)
        output = buffer.getvalue()
        self.assertIn("uv run python -m core.train.group1.runner train", output)
        self.assertIn("--batch 8", output)
        self.assertIn("--dataset-config datasets/group1/v1/dataset.json", output)

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
        self.assertIn("--dataset-config D:/sinan-captcha-work/datasets/group1/firstpass/dataset.json", output)
        self.assertIn("--project D:/sinan-captcha-work/runs/group1", output)
        self.assertIn("--name smoke", output)

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
        self.assertIn("--dataset-config D:/sinan-captcha-work/datasets/group1/firstpass_v2/dataset.json", output)
        self.assertIn("--scene-model D:/sinan-captcha-work/runs/group1/firstpass/scene-detector/weights/best.pt", output)
        self.assertIn("--query-model D:/sinan-captcha-work/runs/group1/firstpass/query-parser/weights/best.pt", output)
        self.assertIn("--name round2", output)

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
        self.assertIn("uv run python -m core.train.group1.runner train", output)
        self.assertIn("--scene-model D:/sinan-captcha-work/runs/group1/firstpass/scene-detector/weights/last.pt", output)
        self.assertIn("--query-model D:/sinan-captcha-work/runs/group1/firstpass/query-parser/weights/last.pt", output)
        self.assertIn("--resume", output)

    def test_group1_prelabel_cli_dry_run_uses_reviewed_exam_and_trained_weights(self) -> None:
        buffer = io.StringIO()
        with patch("core.train.group1.cli.Path.cwd", return_value=Path("D:/sinan-captcha-work")):
            with redirect_stdout(buffer):
                code = group1_cli.main(
                    [
                        "prelabel",
                        "--exam-root",
                        "materials/business_exams/group1/reviewed-v1",
                        "--dataset-version",
                        "firstpass",
                        "--train-name",
                        "round1",
                        "--dry-run",
                    ]
                )
        self.assertEqual(code, 0)
        output = buffer.getvalue()
        self.assertIn("uv run python -m core.train.group1.runner predict", output)
        self.assertIn("--dataset-config D:/sinan-captcha-work/datasets/group1/firstpass/dataset.json", output)
        self.assertIn("--scene-model D:/sinan-captcha-work/runs/group1/round1/scene-detector/weights/best.pt", output)
        self.assertIn("--query-model D:/sinan-captcha-work/runs/group1/round1/query-parser/weights/best.pt", output)
        self.assertIn("--source materials/business_exams/group1/reviewed-v1/.sinan/prelabel/group1/source.jsonl", output)

    def test_group2_cli_executes_training_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dataset_config = root / "datasets" / "group2" / "v1" / "dataset.json"
            dataset_config.parent.mkdir(parents=True)
            dataset_config.write_text(
                '{"task":"group2","format":"sinan.group2.paired.v1","splits":{"train":"splits/train.jsonl","val":"splits/val.jsonl","test":"splits/test.jsonl"}}',
                encoding="utf-8",
            )
            with patch("core.train.group2.service._ensure_group2_training_dependencies") as ensure_deps:
                with patch("core.train.group2.service.subprocess.run") as subprocess_run:
                    ensure_deps.return_value = None
                    subprocess_run.return_value.returncode = 0
                    code = group2_cli.main(
                        [
                            "--dataset-config",
                            str(dataset_config),
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
        self.assertEqual(command[2], "python")
        self.assertEqual(command[3], "-m")
        self.assertEqual(command[4], "core.train.group2.runner")
        self.assertIn("--dataset-config", command)
        self.assertIn(str(dataset_config), command)
        self.assertIn("--epochs", command)
        self.assertIn("100", command)
        self.assertIn("--name", command)
        self.assertIn("firstpass", command)

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
        self.assertIn("--dataset-config D:/sinan-captcha-work/datasets/group2/firstpass/dataset.json", output)
        self.assertIn("--project D:/sinan-captcha-work/runs/group2", output)
        self.assertIn("--name smoke", output)

    def test_group2_prelabel_cli_dry_run_uses_reviewed_exam_and_trained_weights(self) -> None:
        buffer = io.StringIO()
        with patch("core.train.group2.cli.Path.cwd", return_value=Path("D:/sinan-captcha-work")):
            with redirect_stdout(buffer):
                code = group2_cli.main(
                    [
                        "prelabel",
                        "--exam-root",
                        "materials/business_exams/group2/reviewed-v1",
                        "--dataset-version",
                        "firstpass",
                        "--train-name",
                        "round2",
                        "--dry-run",
                    ]
                )
        self.assertEqual(code, 0)
        output = buffer.getvalue()
        self.assertIn("uv run python -m core.train.group2.runner predict", output)
        self.assertIn("--dataset-config D:/sinan-captcha-work/datasets/group2/firstpass/dataset.json", output)
        self.assertIn("--model D:/sinan-captcha-work/runs/group2/round2/weights/best.pt", output)
        self.assertIn("--source materials/business_exams/group2/reviewed-v1/.sinan/prelabel/group2/source.jsonl", output)

    def test_group2_prediction_job_runs_per_sample_when_tile_sizes_differ(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dataset_dir = root / "datasets" / "group2" / "reviewed-v1"
            (dataset_dir / "splits").mkdir(parents=True)
            dataset_config = dataset_dir / "dataset.json"
            dataset_config.write_text(
                json.dumps(
                    {
                        "task": "group2",
                        "format": "sinan.group2.paired.v1",
                        "splits": {
                            "train": "splits/train.jsonl",
                            "val": "splits/val.jsonl",
                            "test": "splits/test.jsonl",
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            master_a = dataset_dir / "master" / "sample_0001.png"
            master_b = dataset_dir / "master" / "sample_0002.png"
            tile_a = dataset_dir / "tile" / "sample_0001.png"
            tile_b = dataset_dir / "tile" / "sample_0002.png"
            _write_png(master_a, 320, 160, (220, 220, 220))
            _write_png(master_b, 320, 160, (220, 220, 220))
            _write_png(tile_a, 25, 55, (10, 10, 10))
            _write_png(tile_b, 26, 54, (10, 10, 10))

            source = dataset_dir / "splits" / "val.jsonl"
            source.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "sample_id": "sample_0001",
                                "master_image": "master/sample_0001.png",
                                "tile_image": "tile/sample_0001.png",
                                "target_gap": {
                                    "class": "slider_gap",
                                    "class_id": 0,
                                    "bbox": [100, 40, 125, 95],
                                    "center": [112, 68],
                                },
                                "tile_bbox": [0, 0, 25, 55],
                                "offset_x": 100,
                                "offset_y": 40,
                                "label_source": "reviewed",
                                "source_batch": "reviewed-v1",
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "sample_id": "sample_0002",
                                "master_image": "master/sample_0002.png",
                                "tile_image": "tile/sample_0002.png",
                                "target_gap": {
                                    "class": "slider_gap",
                                    "class_id": 0,
                                    "bbox": [120, 42, 146, 96],
                                    "center": [133, 69],
                                },
                                "tile_bbox": [0, 0, 26, 54],
                                "offset_x": 120,
                                "offset_y": 42,
                                "label_source": "reviewed",
                                "source_batch": "reviewed-v1",
                            },
                            ensure_ascii=False,
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            model_path = root / "runs" / "group2" / "demo" / "weights" / "best.pt"
            model_path.parent.mkdir(parents=True, exist_ok=True)
            model_path.write_bytes(b"pt")
            job = build_group2_prediction_job(
                dataset_config=dataset_config,
                model_path=model_path,
                source=source,
                project_dir=root / "reports" / "group2",
                run_name="predict_demo",
                device="cpu",
            )

            def _fake_run(command: list[str], check: bool) -> object:
                self.assertTrue(check)
                project_dir = Path(command[command.index("--project") + 1])
                run_name = command[command.index("--name") + 1]
                source_path = Path(command[command.index("--source") + 1])
                rows = read_jsonl(source_path)
                output_dir = project_dir / run_name
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / "labels.jsonl").write_text(
                    json.dumps(rows[0], ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                return type("Completed", (), {"returncode": 0})()

            with patch("core.train.group2.service._ensure_group2_training_dependencies") as ensure_deps:
                with patch("core.train.group2.service.subprocess.run", side_effect=_fake_run) as subprocess_run:
                    ensure_deps.return_value = None
                    result = run_group2_prediction_job(job)

            labels = read_jsonl(result.labels_path)
            self.assertEqual(result.sample_count, 2)
            self.assertEqual([row["sample_id"] for row in labels], ["sample_0001", "sample_0002"])
            self.assertIn("per-sample group2 prediction x2", result.command)
            self.assertEqual(subprocess_run.call_count, 2)
            self.assertTrue((job.output_dir() / "_per_sample_source" / "sample_0001.jsonl").exists())
            self.assertTrue((job.output_dir() / "_per_sample_source" / "sample_0002.jsonl").exists())

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
