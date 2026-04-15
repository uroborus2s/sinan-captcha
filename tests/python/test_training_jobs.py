import io
import importlib
import json
import struct
import unittest
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
from unittest.mock import patch
import zlib

from common.paths import default_work_root
from common.jsonl import read_jsonl
from inference.service import ClickPoint, Group1ClickTarget, Group1MappingResult
from train.base import (
    is_resumable_yolo_checkpoint,
    preferred_checkpoint_path,
    preferred_run_checkpoint,
    prepare_dataset_yaml_for_ultralytics,
)
from train.group1 import cli as group1_cli
from train.group1.dataset import load_group1_dataset_config
from train.group1.runner import _build_prediction_row, _build_train_command
from train.group1.service import EmbedderReviewConfig, build_group1_training_job
from train.group2 import cli as group2_cli
from train.group2.service import build_group2_prediction_job, build_group2_training_job, run_group2_prediction_job


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
    def test_is_resumable_yolo_checkpoint_rejects_plain_text_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint_path = Path(tmpdir) / "weights" / "last.pt"
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            checkpoint_path.write_text("not-a-checkpoint", encoding="utf-8")

            self.assertFalse(is_resumable_yolo_checkpoint(checkpoint_path))

    def test_is_resumable_yolo_checkpoint_accepts_checkpoint_with_epoch_and_optimizer(self) -> None:
        torch = importlib.import_module("torch")

        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint_path = Path(tmpdir) / "weights" / "last.pt"
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            torch.save(
                {
                    "epoch": 11,
                    "optimizer": {
                        "state": {},
                        "param_groups": [],
                    },
                },
                checkpoint_path,
            )

            self.assertTrue(is_resumable_yolo_checkpoint(checkpoint_path))

    def test_group1_instance_matching_prediction_row_copies_query_identity(self) -> None:
        row = {
            "sample_id": "g1_000001",
            "query_image": "query/g1_000001.png",
            "scene_image": "scene/g1_000001.png",
            "query_items": [
                {
                    "order": 1,
                    "asset_id": "asset_house",
                    "template_id": "tpl_house",
                    "variant_id": "var_outline",
                    "bbox": [8, 8, 28, 28],
                    "center": [18, 18],
                }
            ],
            "scene_targets": [],
            "distractors": [],
            "source_batch": "batch_0001",
        }
        prediction = _build_prediction_row(
            row,
            predicted_query_items=[
                {
                    "order": 1,
                    "bbox": [8, 8, 28, 28],
                    "center": [18, 18],
                    "score": 0.99,
                    "class_guess": "icon_house",
                }
            ],
            mapping=Group1MappingResult(
                status="ok",
                ordered_targets=[
                    Group1ClickTarget(
                        order=1,
                        bbox=[80, 32, 120, 72],
                        center=[100, 52],
                        score=0.97,
                    )
                ],
                ordered_clicks=[ClickPoint(x=100, y=52)],
                missing_orders=[],
                ambiguous_orders=[],
            ),
            elapsed_ms=7.5,
        )

        scene_target = prediction["scene_targets"][0]
        self.assertEqual(scene_target["asset_id"], "asset_house")
        self.assertEqual(scene_target["template_id"], "tpl_house")
        self.assertEqual(scene_target["variant_id"], "var_outline")
        self.assertEqual(prediction["query_items"][0]["class_guess"], "icon_house")
        self.assertEqual(prediction["missing_orders"], [])
        self.assertEqual(prediction["ambiguous_orders"], [])
        self.assertNotIn("class_id", scene_target)
        self.assertNotIn("class", scene_target)

    def test_group1_dataset_loader_accepts_instance_matching_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_dir = Path(tmpdir) / "datasets" / "group1" / "v2"
            dataset_dir.mkdir(parents=True)
            dataset_config_path = dataset_dir / "dataset.json"
            dataset_config_path.write_text(
                json.dumps(
                    {
                        "task": "group1",
                        "format": "sinan.group1.instance_matching.v1",
                        "splits": {
                            "train": "splits/train.jsonl",
                            "val": "splits/val.jsonl",
                            "test": "splits/test.jsonl",
                        },
                        "query_detector": {
                            "format": "yolo.detect.v1",
                            "dataset_yaml": "query-yolo/dataset.yaml",
                        },
                        "proposal_detector": {
                            "format": "yolo.detect.v1",
                            "dataset_yaml": "proposal-yolo/dataset.yaml",
                        },
                        "embedding": {
                            "format": "sinan.group1.embedding.v1",
                            "queries_dir": "embedding/queries",
                            "candidates_dir": "embedding/candidates",
                            "pairs_jsonl": "embedding/pairs.jsonl",
                            "triplets_jsonl": "embedding/triplets.jsonl",
                        },
                        "eval": {
                            "format": "sinan.group1.eval.v1",
                            "labels_jsonl": "eval/labels.jsonl",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            config = load_group1_dataset_config(dataset_config_path)

            self.assertEqual(config.format, "sinan.group1.instance_matching.v1")
            self.assertIsNotNone(config.query_component)
            self.assertEqual(config.query_component.dataset_yaml, (dataset_dir / "query-yolo" / "dataset.yaml").resolve())
            self.assertEqual(config.proposal_component.dataset_yaml, (dataset_dir / "proposal-yolo" / "dataset.yaml").resolve())
            self.assertEqual(config.embedding_pairs_path, (dataset_dir / "embedding" / "pairs.jsonl").resolve())
            self.assertEqual(config.eval_labels_path, (dataset_dir / "eval" / "labels.jsonl").resolve())

    def test_preferred_checkpoint_path_returns_best_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            best = root / "weights" / "best.pt"
            last = root / "weights" / "last.pt"
            best.parent.mkdir(parents=True, exist_ok=True)
            best.write_text("best", encoding="utf-8")
            last.write_text("last", encoding="utf-8")

            self.assertEqual(preferred_checkpoint_path(best, last), best)

    def test_preferred_run_checkpoint_falls_back_to_last_when_best_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            train_root = Path(tmpdir)
            last = train_root / "runs" / "group2" / "trial_0001" / "weights" / "last.pt"
            last.parent.mkdir(parents=True, exist_ok=True)
            last.write_text("last", encoding="utf-8")

            resolved = preferred_run_checkpoint(train_root, "group2", "trial_0001")

            self.assertEqual(resolved, last)

    def test_group1_uses_expected_defaults(self) -> None:
        job = build_group1_training_job(Path("datasets/group1/v1/dataset.json"), Path("runs/group1"))
        command = job.command()
        self.assertEqual(command[:5], ["uv", "run", "python", "-m", "train.group1.runner"])
        self.assertIn("--dataset-config", command)
        self.assertIn("datasets/group1/v1/dataset.json", command)
        self.assertIn("--proposal-model", command)
        self.assertIn("yolo26n.pt", command)
        self.assertIn("--epochs", command)
        self.assertIn("120", command)
        self.assertNotIn("--embedder-model", command)

    def test_group2_uses_expected_defaults(self) -> None:
        job = build_group2_training_job(Path("datasets/group2/v1/dataset.json"), Path("runs/group2"))
        command = job.command()
        self.assertEqual(command[:5], ["uv", "run", "python", "-m", "train.group2.runner"])
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
        self.assertIn("--query-model", command)
        self.assertIn("yolo26s.pt", command)
        self.assertIn("--proposal-model", command)
        self.assertIn("yolo26s.pt", command)
        self.assertIn("--epochs", command)
        self.assertIn("12", command)
        self.assertIn("--batch", command)
        self.assertIn("8", command)
        self.assertIn("--imgsz", command)
        self.assertIn("512", command)
        self.assertIn("--device", command)
        self.assertIn("cpu", command)
        self.assertNotIn("--embedder-model", command)

    def test_group1_query_component_builds_dedicated_training_command(self) -> None:
        job = build_group1_training_job(
            Path("datasets/group1/v2/dataset.json"),
            Path("runs/group1"),
            run_name="query_v2",
            component="query-detector",
            epochs=5,
            batch=4,
            imgsz=256,
            device="cpu",
        )

        command = job.command()
        self.assertEqual(command[:5], ["uv", "run", "python", "-m", "train.group1.runner"])
        self.assertIn("--component", command)
        self.assertIn("query-detector", command)
        self.assertIn("--query-model", command)
        self.assertNotIn("--proposal-model", command)
        self.assertNotIn("--embedder-model", command)

    def test_group1_embedder_component_builds_dedicated_training_command(self) -> None:
        job = build_group1_training_job(
            Path("datasets/group1/v2/dataset.json"),
            Path("runs/group1"),
            run_name="instance_v2",
            component="icon-embedder",
            epochs=3,
            batch=4,
            imgsz=64,
            device="cpu",
        )

        command = job.command()
        self.assertEqual(command[:5], ["uv", "run", "python", "-m", "train.group1.runner"])
        self.assertIn("--component", command)
        self.assertIn("icon-embedder", command)
        self.assertIn("--epochs", command)
        self.assertIn("3", command)
        self.assertIn("--batch", command)
        self.assertIn("4", command)
        self.assertIn("--imgsz", command)
        self.assertIn("64", command)
        self.assertNotIn("--proposal-model", command)
        self.assertFalse(any(part.startswith("--query-") for part in command))

    def test_group1_embedder_component_uses_retrieval_friendly_defaults(self) -> None:
        job = build_group1_training_job(
            Path("datasets/group1/v2/dataset.json"),
            Path("runs/group1"),
            run_name="instance_v2",
            component="icon-embedder",
        )

        command = job.command()
        self.assertIn("--batch", command)
        self.assertIn("32", command)
        self.assertIn("--imgsz", command)
        self.assertIn("96", command)
        self.assertNotIn("--proposal-model", command)
        self.assertFalse(any(part.startswith("--query-") for part in command))

    def test_group1_embedder_component_passes_embedder_review_runtime_flags(self) -> None:
        job = build_group1_training_job(
            Path("datasets/group1/v2/dataset.json"),
            Path("runs/group1"),
            run_name="instance_v2",
            component="icon-embedder",
            embedder_review=EmbedderReviewConfig(
                provider="opencode",
                model="local/qwen",
                project_root=Path("C:/sinan-captcha-work"),
                study_name="study_group1_v1",
                task="group1",
                trial_id="trial_0001",
                stage="TRAIN_EMBEDDER_BASE",
                attach_url="http://127.0.0.1:4096",
                binary="opencode",
                timeout_seconds=120.0,
                min_epochs=8,
                window=3,
                rebuild_count=0,
            ),
        )

        command = job.command()
        self.assertIn("--review-provider", command)
        self.assertIn("opencode", command)
        self.assertIn("--review-model", command)
        self.assertIn("local/qwen", command)
        self.assertIn("--review-stage", command)
        self.assertIn("TRAIN_EMBEDDER_BASE", command)

    def test_group1_detector_train_command_sets_exist_ok_to_prevent_renamed_output_dirs(self) -> None:
        command = _build_train_command(
            dataset_yaml=Path("datasets/group1/v1/proposal-yolo/dataset.yaml"),
            project_dir=Path("runs/group1/trial_0002"),
            run_name="proposal-detector",
            model="yolo26n.pt",
            epochs=120,
            batch=16,
            imgsz=640,
            device="0",
            resume=False,
        )

        self.assertIn("exist_ok=True", command)

    def test_group1_prediction_job_includes_icon_embedder_model(self) -> None:
        from train.group1.service import build_group1_prediction_job

        job = build_group1_prediction_job(
            dataset_config=Path("datasets/group1/v2/dataset.json"),
            proposal_model_path=Path("runs/group1/v2/proposal-detector/weights/best.pt"),
            embedder_model_path=Path("runs/group1/v2/icon-embedder/weights/best.pt"),
            source=Path("datasets/group1/v2/splits/val.jsonl"),
            project_dir=Path("reports/group1"),
            run_name="predict_v2",
        )

        command = job.command()
        self.assertIn("--embedder-model", command)
        self.assertIn("runs/group1/v2/icon-embedder/weights/best.pt", command)
        self.assertFalse(any(part.startswith("--query-") for part in command))

    def test_group1_prediction_job_includes_query_detector_model_when_provided(self) -> None:
        from train.group1.service import build_group1_prediction_job

        job = build_group1_prediction_job(
            dataset_config=Path("datasets/group1/v2/dataset.json"),
            query_detector_model_path=Path("runs/group1/v2/query-detector/weights/best.pt"),
            proposal_model_path=Path("runs/group1/v2/proposal-detector/weights/best.pt"),
            embedder_model_path=Path("runs/group1/v2/icon-embedder/weights/best.pt"),
            source=Path("datasets/group1/v2/splits/val.jsonl"),
            project_dir=Path("reports/group1"),
            run_name="predict_v2",
        )

        command = job.command()
        self.assertIn("--query-model", command)
        self.assertIn("runs/group1/v2/query-detector/weights/best.pt", command)

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
        self.assertIn("uv run python -m train.group1.runner train", output)
        self.assertIn("--query-model yolo26n.pt", output)
        self.assertIn("--proposal-model yolo26n.pt", output)
        self.assertIn("--batch 8", output)
        self.assertIn("--dataset-config datasets/group1/v1/dataset.json", output)

    def test_group1_cli_dry_run_supports_icon_embedder_component(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = group1_cli.main(
                [
                    "--dataset-config",
                    "datasets/group1/v2/dataset.json",
                    "--project",
                    "runs/group1",
                    "--name",
                    "g1_embed",
                    "--component",
                    "icon-embedder",
                    "--dry-run",
                ]
            )
        self.assertEqual(code, 0)
        output = buffer.getvalue()
        self.assertIn("--component icon-embedder", output)
        self.assertNotIn("--proposal-model", output)
        self.assertNotIn("--query-", output)

    def test_group1_cli_uses_default_paths_from_training_root(self) -> None:
        buffer = io.StringIO()
        expected_root = default_work_root()
        with patch("train.group1.cli.Path.cwd", return_value=Path("D:/sinan-captcha-work")):
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
        self.assertIn(f"--dataset-config {expected_root / 'datasets/group1/firstpass/dataset.json'}", output)
        self.assertIn(f"--project {expected_root / 'runs/group1'}", output)
        self.assertIn("--name smoke", output)

    def test_group1_cli_uses_previous_best_checkpoint_from_training_root(self) -> None:
        buffer = io.StringIO()
        expected_root = default_work_root()
        with patch("train.group1.cli.Path.cwd", return_value=Path("D:/sinan-captcha-work")):
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
        self.assertIn("--query-model", output)
        self.assertIn(f"{expected_root / 'runs/group1/firstpass/query-detector/weights/best.pt'}", output)
        self.assertIn(f"--dataset-config {expected_root / 'datasets/group1/firstpass_v2/dataset.json'}", output)
        self.assertIn(f"--proposal-model {expected_root / 'runs/group1/firstpass/proposal-detector/weights/best.pt'}", output)
        self.assertIn(f"--embedder-model {expected_root / 'runs/group1/firstpass/icon-embedder/weights/best.pt'}", output)
        self.assertIn("--name round2", output)

    def test_group1_cli_resumes_same_run_from_last_checkpoint(self) -> None:
        buffer = io.StringIO()
        expected_root = default_work_root()
        with patch("train.group1.cli.Path.cwd", return_value=Path("D:/sinan-captcha-work")):
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
        self.assertIn("uv run python -m train.group1.runner train", output)
        self.assertIn(f"--query-model {expected_root / 'runs/group1/firstpass/query-detector/weights/last.pt'}", output)
        self.assertIn(f"--proposal-model {expected_root / 'runs/group1/firstpass/proposal-detector/weights/last.pt'}", output)
        self.assertIn(f"--embedder-model {expected_root / 'runs/group1/firstpass/icon-embedder/weights/last.pt'}", output)
        self.assertIn("--resume", output)

    def test_group1_cli_can_train_only_proposal_detector_from_previous_run(self) -> None:
        buffer = io.StringIO()
        expected_root = default_work_root()
        with patch("train.group1.cli.Path.cwd", return_value=Path("D:/sinan-captcha-work")):
            with redirect_stdout(buffer):
                code = group1_cli.main(
                    [
                        "--dataset-version",
                        "firstpass_v2",
                        "--name",
                        "proposal_only",
                        "--component",
                        "proposal-detector",
                        "--from-run",
                        "firstpass",
                        "--dry-run",
                    ]
                )
        self.assertEqual(code, 0)
        output = buffer.getvalue()
        self.assertIn("--component proposal-detector", output)
        self.assertIn(f"--proposal-model {expected_root / 'runs/group1/firstpass/proposal-detector/weights/best.pt'}", output)
        self.assertNotIn("--query-", output)

    def test_group1_cli_can_train_only_query_detector_from_previous_run(self) -> None:
        buffer = io.StringIO()
        expected_root = default_work_root()
        with patch("train.group1.cli.Path.cwd", return_value=Path("D:/sinan-captcha-work")):
            with redirect_stdout(buffer):
                code = group1_cli.main(
                    [
                        "--dataset-version",
                        "firstpass_v2",
                        "--name",
                        "query_only",
                        "--component",
                        "query-detector",
                        "--from-run",
                        "firstpass",
                        "--dry-run",
                    ]
                )
        self.assertEqual(code, 0)
        output = buffer.getvalue()
        self.assertIn("--component query-detector", output)
        self.assertIn(f"--query-model {expected_root / 'runs/group1/firstpass/query-detector/weights/best.pt'}", output)
        self.assertNotIn("--proposal-model", output)

    def test_group1_prelabel_cli_dry_run_uses_reviewed_exam_and_trained_weights(self) -> None:
        buffer = io.StringIO()
        expected_root = default_work_root()
        with patch("train.group1.cli.Path.cwd", return_value=Path("D:/sinan-captcha-work")):
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
        self.assertIn("uv run python -m train.group1.runner predict", output)
        self.assertIn(f"--dataset-config {expected_root / 'datasets/group1/firstpass/dataset.json'}", output)
        self.assertIn(f"--proposal-model {expected_root / 'runs/group1/round1/proposal-detector/weights/best.pt'}", output)
        self.assertNotIn("--query-", output)
        self.assertIn("--source materials/business_exams/group1/reviewed-v1/.sinan/prelabel/group1/source.jsonl", output)

    def test_group1_query_directory_prelabel_cli_dry_run_emits_rule_based_splitter_plan(self) -> None:
        buffer = io.StringIO()
        with patch("train.group1.cli.Path.cwd", return_value=Path("D:/sinan-captcha-work")):
            with redirect_stdout(buffer):
                code = group1_cli.main(
                    [
                        "prelabel-query-dir",
                        "--input-dir",
                        "materials/test/group1/query",
                        "--dry-run",
                    ]
                )
        self.assertEqual(code, 0)
        output = buffer.getvalue()
        self.assertIn('"input_dir": "materials/test/group1/query"', output)
        self.assertIn('"query_splitter_strategy": "rule_based_v1"', output)
        self.assertIn('"project_dir": "materials/test/group1/query/.sinan/prelabel/group1/query"', output)
        self.assertIn('"run_name": "prelabel-query"', output)

    def test_group1_vlm_prelabel_cli_dry_run_uses_pair_root_and_local_model(self) -> None:
        buffer = io.StringIO()
        with patch("train.group1.cli.Path.cwd", return_value=Path("D:/sinan-captcha-work")):
            with redirect_stdout(buffer):
                code = group1_cli.main(
                    [
                        "prelabel-vlm",
                        "--pair-root",
                        "materials/validation/group1",
                        "--model",
                        "qwen2.5vl:7b",
                        "--dry-run",
                    ]
                )
        self.assertEqual(code, 0)
        output = buffer.getvalue()
        self.assertIn('"pair_root": "materials/validation/group1"', output)
        self.assertIn('"model": "qwen2.5vl:7b"', output)
        self.assertIn('"project_dir": "materials/validation/group1/.sinan/prelabel/group1/vlm"', output)
        self.assertIn('"review_dir": "materials/validation/group1/.sinan/prelabel/group1/vlm/reviewed"', output)

    def test_group2_cli_executes_training_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dataset_config = root / "datasets" / "group2" / "v1" / "dataset.json"
            dataset_config.parent.mkdir(parents=True)
            dataset_config.write_text(
                '{"task":"group2","format":"sinan.group2.paired.v1","splits":{"train":"splits/train.jsonl","val":"splits/val.jsonl","test":"splits/test.jsonl"}}',
                encoding="utf-8",
            )
            with patch("train.group2.service._ensure_group2_training_dependencies") as ensure_deps:
                with patch("train.group2.service.subprocess.run") as subprocess_run:
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
        self.assertEqual(command[4], "train.group2.runner")
        self.assertIn("--dataset-config", command)
        self.assertIn(str(dataset_config), command)
        self.assertIn("--epochs", command)
        self.assertIn("100", command)
        self.assertIn("--name", command)
        self.assertIn("firstpass", command)

    def test_group2_cli_uses_default_paths_from_training_root(self) -> None:
        buffer = io.StringIO()
        expected_root = default_work_root()
        with patch("train.group2.cli.Path.cwd", return_value=Path("D:/sinan-captcha-work")):
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
        self.assertIn(f"--dataset-config {expected_root / 'datasets/group2/firstpass/dataset.json'}", output)
        self.assertIn(f"--project {expected_root / 'runs/group2'}", output)
        self.assertIn("--name smoke", output)

    def test_group2_prelabel_cli_dry_run_uses_reviewed_exam_and_trained_weights(self) -> None:
        buffer = io.StringIO()
        expected_root = default_work_root()
        with patch("train.group2.cli.Path.cwd", return_value=Path("D:/sinan-captcha-work")):
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
        self.assertIn("uv run python -m train.group2.runner predict", output)
        self.assertIn(f"--dataset-config {expected_root / 'datasets/group2/firstpass/dataset.json'}", output)
        self.assertIn(f"--model {expected_root / 'runs/group2/round2/weights/best.pt'}", output)
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

            with patch("train.group2.service._ensure_group2_training_dependencies") as ensure_deps:
                with patch("train.group2.service.subprocess.run", side_effect=_fake_run) as subprocess_run:
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
