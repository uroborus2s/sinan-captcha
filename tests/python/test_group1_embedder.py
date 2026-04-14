from __future__ import annotations

import io
import json
import struct
import sys
import tempfile
import types
import unittest
import zlib
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import torch

from auto_train import contracts, embedder_review_protocol
from train.group1.embedder import (
    Group1TripletDataset,
    IconEmbedder,
    ICON_EMBEDDER_ARCHITECTURE_VERSION,
    _in_batch_contrastive_loss,
    evaluate_retrieval,
    load_embedding_triplets,
    load_icon_embedder_runtime,
    train_icon_embedder,
)
from train.group1.dataset import load_group1_dataset_config
from train.group1 import runner as group1_runner


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


class Group1EmbedderTests(unittest.TestCase):
    def test_triplet_dataset_loads_generator_embedding_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            anchor = root / "embedding" / "queries" / "train" / "g1_000001_01.png"
            positive = root / "embedding" / "candidates" / "train" / "g1_000001_01.png"
            negative = root / "embedding" / "candidates" / "train" / "g1_000001_neg.png"
            _write_png(anchor, 16, 16, (255, 0, 0))
            _write_png(positive, 16, 16, (255, 0, 0))
            _write_png(negative, 16, 16, (0, 0, 255))
            triplets_path = root / "embedding" / "triplets.jsonl"
            triplets_path.write_text(
                json.dumps(
                    {
                        "split": "train",
                        "sample_id": "g1_000001",
                        "anchor_image": "embedding/queries/train/g1_000001_01.png",
                        "positive_image": "embedding/candidates/train/g1_000001_01.png",
                        "negative_image": "embedding/candidates/train/g1_000001_neg.png",
                        "anchor": {
                            "order": 1,
                            "bbox": [0, 0, 16, 16],
                            "center": [8, 8],
                            "asset_id": "asset_red",
                            "template_id": "tpl_red",
                            "variant_id": "var_red",
                        },
                        "positive": {
                            "order": 1,
                            "bbox": [0, 0, 16, 16],
                            "center": [8, 8],
                            "asset_id": "asset_red",
                            "template_id": "tpl_red",
                            "variant_id": "var_red",
                        },
                        "negative": {
                            "bbox": [0, 0, 16, 16],
                            "center": [8, 8],
                            "asset_id": "asset_blue",
                            "template_id": "tpl_blue",
                            "variant_id": "var_blue",
                        },
                        "negative_role": "distractor",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            records = load_embedding_triplets(triplets_path)
            dataset = Group1TripletDataset(root, records, image_size=32)
            item = dataset[0]

            self.assertEqual(len(dataset), 1)
            self.assertEqual(tuple(item["anchor"].shape), (3, 32, 32))
            self.assertEqual(tuple(item["positive"].shape), (3, 32, 32))
            self.assertEqual(tuple(item["negative"].shape), (3, 32, 32))
            self.assertEqual(item["metadata"]["sample_id"], "g1_000001")
            self.assertEqual(item["metadata"]["anchor_identity"], "asset_red")
            self.assertEqual(item["metadata"]["positive_identity"], "asset_red")
            self.assertEqual(item["metadata"]["negative_identity"], "asset_blue")

    def test_evaluate_retrieval_reports_recall_at_1_and_3(self) -> None:
        metrics = evaluate_retrieval(
            query_embeddings={
                "q_red": [1.0, 0.0, 0.0],
                "q_blue": [0.0, 0.0, 1.0],
            },
            candidate_embeddings={
                "red": [0.95, 0.05, 0.0],
                "blue": [0.0, 0.0, 1.0],
                "green": [0.0, 1.0, 0.0],
            },
            positives={
                "q_red": "red",
                "q_blue": "blue",
            },
            k_values=(1, 3),
        )

        self.assertEqual(metrics["embedding_recall_at_1"], 1.0)
        self.assertEqual(metrics["embedding_recall_at_3"], 1.0)

    def test_evaluate_retrieval_reports_identity_diagnostics_and_error_breakdown(self) -> None:
        metrics = evaluate_retrieval(
            query_embeddings={
                "q_red": [1.0, 0.0, 0.0],
                "q_blue": [0.0, 0.0, 1.0],
            },
            candidate_embeddings={
                "red_exact": [0.90, 0.10, 0.0],
                "red_variant": [0.95, 0.05, 0.0],
                "blue_exact": [0.0, 0.0, 1.0],
                "green": [0.0, 1.0, 0.0],
            },
            positives={
                "q_red": "red_exact",
                "q_blue": "blue_exact",
            },
            query_metadata={
                "q_red": {"identity": "asset_red", "template_id": "tpl_red"},
                "q_blue": {"identity": "asset_blue", "template_id": "tpl_blue"},
            },
            candidate_metadata={
                "red_exact": {"identity": "asset_red", "template_id": "tpl_red", "role": "positive"},
                "red_variant": {"identity": "asset_red", "template_id": "tpl_red", "role": "scene_target_pred"},
                "blue_exact": {"identity": "asset_blue", "template_id": "tpl_blue", "role": "positive"},
                "green": {"identity": "asset_green", "template_id": "tpl_green", "role": "distractor_pred"},
            },
            k_values=(1, 3),
        )

        self.assertEqual(metrics["embedding_recall_at_1"], 0.5)
        self.assertEqual(metrics["embedding_identity_recall_at_1"], 1.0)
        self.assertEqual(metrics["embedding_recall_at_3"], 1.0)
        self.assertEqual(metrics["embedding_identity_recall_at_3"], 1.0)
        self.assertEqual(metrics["embedding_positive_rank_mean"], 1.5)
        self.assertEqual(metrics["embedding_positive_rank_median"], 1.5)
        self.assertEqual(metrics["embedding_top1_error_scene_target_rate"], 0.5)
        self.assertEqual(metrics["embedding_top1_error_false_positive_rate"], 0.0)
        self.assertEqual(metrics["embedding_same_template_top1_error_rate"], 0.5)

    def test_evaluate_retrieval_reports_scene_scoped_recall_separately_from_global_exact_recall(self) -> None:
        metrics = evaluate_retrieval(
            query_embeddings={
                "q_red": [1.0, 0.0, 0.0],
                "q_blue": [0.0, 0.0, 1.0],
            },
            candidate_embeddings={
                "red_exact": [0.90, 0.10, 0.0],
                "red_variant": [0.95, 0.05, 0.0],
                "blue_exact": [0.0, 0.0, 1.0],
                "green": [0.0, 1.0, 0.0],
            },
            positives={
                "q_red": "red_exact",
                "q_blue": "blue_exact",
            },
            scene_candidates_by_query={
                "q_red": ["red_exact", "green"],
                "q_blue": ["blue_exact", "green"],
            },
            query_metadata={
                "q_red": {"identity": "asset_red", "template_id": "tpl_red"},
                "q_blue": {"identity": "asset_blue", "template_id": "tpl_blue"},
            },
            candidate_metadata={
                "red_exact": {"identity": "asset_red", "template_id": "tpl_red", "role": "positive"},
                "red_variant": {"identity": "asset_red", "template_id": "tpl_red", "role": "scene_target_pred"},
                "blue_exact": {"identity": "asset_blue", "template_id": "tpl_blue", "role": "positive"},
                "green": {"identity": "asset_green", "template_id": "tpl_green", "role": "distractor_pred"},
            },
            k_values=(1, 3),
        )

        self.assertEqual(metrics["embedding_recall_at_1"], 0.5)
        self.assertEqual(metrics["embedding_scene_recall_at_1"], 1.0)
        self.assertEqual(metrics["embedding_scene_recall_at_3"], 1.0)
        self.assertEqual(metrics["embedding_scene_positive_rank_mean"], 1.0)

    def test_in_batch_contrastive_loss_treats_same_identity_as_positive_pool(self) -> None:
        anchor = torch.tensor([[1.0, 0.0], [1.0, 0.0]], dtype=torch.float32)
        positive = torch.tensor([[1.0, 0.0], [1.0, 0.0]], dtype=torch.float32)
        negative = torch.tensor([[0.0, 1.0], [0.0, 1.0]], dtype=torch.float32)

        same_identity_loss = _in_batch_contrastive_loss(
            anchor=anchor,
            positive=positive,
            negative=negative,
            metadata=[
                {"anchor_identity": "asset_a", "positive_identity": "asset_a", "negative_identity": "asset_b"},
                {"anchor_identity": "asset_a", "positive_identity": "asset_a", "negative_identity": "asset_c"},
            ],
            temperature=0.1,
        )
        different_identity_loss = _in_batch_contrastive_loss(
            anchor=anchor,
            positive=positive,
            negative=negative,
            metadata=[
                {"anchor_identity": "asset_a", "positive_identity": "asset_a", "negative_identity": "asset_b"},
                {"anchor_identity": "asset_d", "positive_identity": "asset_d", "negative_identity": "asset_c"},
            ],
            temperature=0.1,
        )

        self.assertLess(float(same_identity_loss), float(different_identity_loss))

    def test_train_icon_embedder_writes_checkpoints_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_dataset_config(root)
            anchor = root / "embedding" / "queries" / "train" / "g1_000001_01.png"
            positive = root / "embedding" / "candidates" / "train" / "g1_000001_01.png"
            negative = root / "embedding" / "candidates" / "train" / "g1_000001_neg.png"
            _write_png(anchor, 16, 16, (255, 0, 0))
            _write_png(positive, 16, 16, (255, 0, 0))
            _write_png(negative, 16, 16, (0, 0, 255))
            _write_triplets_jsonl(root / "embedding" / "triplets.jsonl")
            dataset_config = load_group1_dataset_config(root / "dataset.json")
            run_dir = root / "runs" / "group1" / "smoke"

            result = train_icon_embedder(
                dataset_config=dataset_config,
                run_dir=run_dir,
                model_path=None,
                epochs=1,
                batch_size=1,
                image_size=16,
                device_name="cpu",
                resume=False,
            )

            self.assertTrue(result.best_checkpoint.exists())
            self.assertTrue(result.last_checkpoint.exists())
            self.assertTrue(result.summary_path.exists())
            summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["component"], "icon-embedder")
            self.assertEqual(summary["sample_count"], 1)
            self.assertIn("embedding_recall_at_1", summary["metrics"])
            self.assertEqual(summary["training"]["embedding_dim"], 128)
            self.assertEqual(summary["training"]["learning_rate"], 3e-4)
            self.assertEqual(summary["training"]["loss"]["contrastive_weight"], 1.0)
            self.assertEqual(summary["training"]["architecture_version"], 2)

    def test_train_icon_embedder_stops_when_review_requests_advance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_dataset_config(root)
            anchor = root / "embedding" / "queries" / "train" / "g1_000001_01.png"
            positive = root / "embedding" / "candidates" / "train" / "g1_000001_01.png"
            negative = root / "embedding" / "candidates" / "train" / "g1_000001_neg.png"
            _write_png(anchor, 16, 16, (255, 0, 0))
            _write_png(positive, 16, 16, (255, 0, 0))
            _write_png(negative, 16, 16, (0, 0, 255))
            _write_triplets_jsonl(root / "embedding" / "triplets.jsonl")
            dataset_config = load_group1_dataset_config(root / "dataset.json")
            run_dir = root / "runs" / "group1" / "smoke"

            def reviewer(
                context: embedder_review_protocol.EmbedderReviewContext,
            ) -> embedder_review_protocol.EmbedderReviewRecord:
                return embedder_review_protocol.EmbedderReviewRecord(
                    stage=context.stage,
                    epoch=context.epoch,
                    decision=embedder_review_protocol.EMBEDDER_REVIEW_DECISION_STOP_AND_ADVANCE,
                    confidence=0.9,
                    reason="base_plateau_switch_to_hardset",
                    next_action={"train_action": "stop_and_advance", "target_stage": "EMBEDDER_GATE"},
                    evidence=["plateau"],
                    agent=contracts.AgentRef(provider="test", name="embedder-review", model="stub"),
                )

            with patch("train.group1.embedder._train_one_epoch", return_value=0.2):
                with patch("train.group1.embedder._evaluate_triplet_loss", return_value=0.1):
                    with patch(
                        "train.group1.embedder._evaluate_model_retrieval",
                        side_effect=[
                            {"embedding_recall_at_1": 0.10, "embedding_recall_at_3": 0.20},
                            {"embedding_recall_at_1": 0.101, "embedding_recall_at_3": 0.20},
                        ],
                    ):
                        result = train_icon_embedder(
                            dataset_config=dataset_config,
                            run_dir=run_dir,
                            model_path=None,
                            epochs=10,
                            batch_size=1,
                            image_size=16,
                            device_name="cpu",
                            resume=False,
                            review_callback=reviewer,
                            review_stage="TRAIN_EMBEDDER_BASE",
                            review_study_name="study_001",
                            review_trial_id="trial_0001",
                            review_min_epochs=2,
                            review_window=1,
                        )

            summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["review"]["decision"], "STOP_AND_ADVANCE")
            self.assertEqual(summary["training_stop"]["reason"], "review:STOP_AND_ADVANCE")
            self.assertEqual(summary["training_stop"]["stopped_epoch"], 2)
            self.assertEqual(len(summary["review_history"]), 1)

    def test_icon_embedder_default_forward_returns_128d_normalized_embeddings(self) -> None:
        model = IconEmbedder()
        outputs = model(torch.rand(2, 3, 32, 32))

        self.assertEqual(tuple(outputs.shape), (2, 128))
        self.assertAlmostEqual(float(outputs[0].norm().item()), 1.0, places=5)

    def test_train_icon_embedder_emits_progress_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_dataset_config(root)
            anchor = root / "embedding" / "queries" / "train" / "g1_000001_01.png"
            positive = root / "embedding" / "candidates" / "train" / "g1_000001_01.png"
            negative = root / "embedding" / "candidates" / "train" / "g1_000001_neg.png"
            _write_png(anchor, 16, 16, (255, 0, 0))
            _write_png(positive, 16, 16, (255, 0, 0))
            _write_png(negative, 16, 16, (0, 0, 255))
            _write_triplets_jsonl(root / "embedding" / "triplets.jsonl")
            dataset_config = load_group1_dataset_config(root / "dataset.json")
            run_dir = root / "runs" / "group1" / "smoke"
            buffer = io.StringIO()

            with redirect_stdout(buffer):
                train_icon_embedder(
                    dataset_config=dataset_config,
                    run_dir=run_dir,
                    model_path=None,
                    epochs=1,
                    batch_size=1,
                    image_size=16,
                    device_name="cpu",
                    resume=False,
                )

            output = buffer.getvalue()
            self.assertRegex(output, r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
            self.assertIn("icon-embedder start", output)
            self.assertIn("epoch 1/1", output)
            self.assertIn("validation-triplet-loss", output)
            self.assertIn("retrieval-query-embeddings", output)
            self.assertIn("retrieval-candidate-embeddings", output)
            self.assertIn("embedding_recall_at_1", output)

    def test_train_icon_embedder_logs_checkpoint_load_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_dataset_config(root)
            anchor = root / "embedding" / "queries" / "train" / "g1_000001_01.png"
            positive = root / "embedding" / "candidates" / "train" / "g1_000001_01.png"
            negative = root / "embedding" / "candidates" / "train" / "g1_000001_neg.png"
            _write_png(anchor, 16, 16, (255, 0, 0))
            _write_png(positive, 16, 16, (255, 0, 0))
            _write_png(negative, 16, 16, (0, 0, 255))
            _write_triplets_jsonl(root / "embedding" / "triplets.jsonl")
            dataset_config = load_group1_dataset_config(root / "dataset.json")
            run_dir = root / "runs" / "group1" / "smoke"
            checkpoint_path = root / "checkpoint.pt"
            model = IconEmbedder()
            torch.save(
                {
                    "architecture_version": ICON_EMBEDDER_ARCHITECTURE_VERSION,
                    "model_state": model.state_dict(),
                    "optimizer_state": None,
                    "epoch": 3,
                    "imgsz": 16,
                    "embedding_dim": model.embedding_dim,
                    "best_score": 0.42,
                    "best_epoch": 3,
                    "metrics": {},
                },
                checkpoint_path,
            )
            buffer = io.StringIO()

            with redirect_stdout(buffer):
                train_icon_embedder(
                    dataset_config=dataset_config,
                    run_dir=run_dir,
                    model_path=checkpoint_path,
                    epochs=1,
                    batch_size=1,
                    image_size=16,
                    device_name="cpu",
                    resume=False,
                )

            output = buffer.getvalue()
            self.assertIn("icon-embedder init", output)
            self.assertIn(f"checkpoint={checkpoint_path}", output)
            self.assertIn("restore_optimizer=False", output)

    def test_train_icon_embedder_stops_early_when_recall_plateaus(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_dataset_config(root)
            anchor = root / "embedding" / "queries" / "train" / "g1_000001_01.png"
            positive = root / "embedding" / "candidates" / "train" / "g1_000001_01.png"
            negative = root / "embedding" / "candidates" / "train" / "g1_000001_neg.png"
            _write_png(anchor, 16, 16, (255, 0, 0))
            _write_png(positive, 16, 16, (255, 0, 0))
            _write_png(negative, 16, 16, (0, 0, 255))
            _write_triplets_jsonl(root / "embedding" / "triplets.jsonl")
            dataset_config = load_group1_dataset_config(root / "dataset.json")
            run_dir = root / "runs" / "group1" / "smoke"

            with patch("train.group1.embedder._train_one_epoch", return_value=0.2):
                with patch("train.group1.embedder._evaluate_triplet_loss", return_value=0.1):
                    with patch(
                        "train.group1.embedder._evaluate_model_retrieval",
                        side_effect=[
                            {"embedding_recall_at_1": 0.10, "embedding_recall_at_3": 0.25},
                            {"embedding_recall_at_1": 0.11, "embedding_recall_at_3": 0.26},
                            {"embedding_recall_at_1": 0.109, "embedding_recall_at_3": 0.27},
                            {"embedding_recall_at_1": 0.108, "embedding_recall_at_3": 0.28},
                        ],
                    ):
                        train_icon_embedder(
                            dataset_config=dataset_config,
                            run_dir=run_dir,
                            model_path=None,
                            epochs=10,
                            batch_size=1,
                            image_size=16,
                            device_name="cpu",
                            resume=False,
                            early_stopping_min_epochs=2,
                            early_stopping_patience=2,
                            early_stopping_min_delta=0.01,
                        )

            summary = json.loads((run_dir / "icon-embedder" / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(len(summary["history"]), 4)
            self.assertEqual(summary["early_stopping"]["best_epoch"], 2)
            self.assertEqual(summary["early_stopping"]["stopped_epoch"], 4)
            self.assertTrue(summary["early_stopping"]["triggered"])

    def test_train_icon_embedder_writes_partial_summary_before_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_dataset_config(root)
            anchor = root / "embedding" / "queries" / "train" / "g1_000001_01.png"
            positive = root / "embedding" / "candidates" / "train" / "g1_000001_01.png"
            negative = root / "embedding" / "candidates" / "train" / "g1_000001_neg.png"
            _write_png(anchor, 16, 16, (255, 0, 0))
            _write_png(positive, 16, 16, (255, 0, 0))
            _write_png(negative, 16, 16, (0, 0, 255))
            _write_triplets_jsonl(root / "embedding" / "triplets.jsonl")
            dataset_config = load_group1_dataset_config(root / "dataset.json")
            run_dir = root / "runs" / "group1" / "smoke"

            with patch(
                "train.group1.embedder._train_one_epoch",
                side_effect=[0.2, RuntimeError("interrupt-after-epoch-1")],
            ):
                with patch("train.group1.embedder._evaluate_triplet_loss", return_value=0.1):
                    with patch(
                        "train.group1.embedder._evaluate_model_retrieval",
                        return_value={"embedding_recall_at_1": 0.10, "embedding_recall_at_3": 0.25},
                    ):
                        with self.assertRaisesRegex(RuntimeError, "interrupt-after-epoch-1"):
                            train_icon_embedder(
                                dataset_config=dataset_config,
                                run_dir=run_dir,
                                model_path=None,
                                epochs=10,
                                batch_size=1,
                                image_size=16,
                                device_name="cpu",
                                resume=False,
                            )

            summary = json.loads((run_dir / "icon-embedder" / "summary.json").read_text(encoding="utf-8"))
            self.assertFalse(summary["finalized"])
            self.assertEqual(len(summary["history"]), 1)
            self.assertEqual(summary["history"][0]["epoch"], 1)
            self.assertEqual(summary["training_stop"]["reason"], "in_progress")
            self.assertEqual(summary["training_stop"]["stopped_epoch"], 1)

    def test_icon_embedder_runtime_loads_checkpoint_and_embeds_bbox_crop(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            checkpoint_path = root / "runs" / "group1" / "smoke" / "icon-embedder" / "weights" / "best.pt"
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            _write_icon_embedder_checkpoint(checkpoint_path, embedding_dim=4, image_size=16)
            image_path = root / "scene.png"
            _write_png(image_path, 32, 32, (255, 0, 0))

            runtime = load_icon_embedder_runtime(checkpoint_path, device_name="cpu")
            vector = runtime.embed_crop(image_path, {"bbox": [0, 0, 16, 16]})

            self.assertEqual(len(vector), 4)
            self.assertAlmostEqual(sum(value * value for value in vector), 1.0, places=5)

    def test_runner_trains_icon_embedder_component_from_dataset_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_dataset_config(root)
            _write_png(root / "embedding" / "queries" / "train" / "g1_000001_01.png", 16, 16, (255, 0, 0))
            _write_png(root / "embedding" / "candidates" / "train" / "g1_000001_01.png", 16, 16, (255, 0, 0))
            _write_png(root / "embedding" / "candidates" / "train" / "g1_000001_neg.png", 16, 16, (0, 0, 255))
            _write_triplets_jsonl(root / "embedding" / "triplets.jsonl")

            exit_code = group1_runner.main(
                [
                    "train",
                    "--dataset-config",
                    str(root / "dataset.json"),
                    "--project",
                    str(root / "runs" / "group1"),
                    "--name",
                    "smoke",
                    "--component",
                    "icon-embedder",
                    "--epochs",
                    "1",
                    "--batch",
                    "1",
                    "--imgsz",
                    "16",
                    "--device",
                    "cpu",
                ]
            )

            summary_path = root / "runs" / "group1" / "smoke" / "summary.json"
            self.assertEqual(exit_code, 0)
            self.assertTrue((root / "runs" / "group1" / "smoke" / "icon-embedder" / "weights" / "best.pt").exists())
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertIn("icon-embedder", summary["components"])
            self.assertIn("metrics", summary["components"]["icon-embedder"])

    def test_evaluate_query_detector_rows_reports_passed_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_png(root / "eval" / "query" / "val" / "g1_000001.png", 64, 24, (255, 255, 255))
            rows = [
                {
                    "sample_id": "g1_000001",
                    "query_image": "eval/query/val/g1_000001.png",
                    "query_items": [
                        {"order": 1, "bbox": [0, 0, 10, 10], "center": [5, 5]},
                        {"order": 2, "bbox": [20, 0, 30, 10], "center": [25, 5]},
                        {"order": 3, "bbox": [40, 0, 50, 10], "center": [45, 5]},
                    ],
                }
            ]

            metrics, gate, failcases = group1_runner._evaluate_query_detector_rows(
                rows,
                dataset_root=root,
                predict_query_items=lambda path: [
                    {"order": 1, "bbox": [0, 0, 10, 10], "center": [5, 5]},
                    {"order": 2, "bbox": [20, 0, 30, 10], "center": [25, 5]},
                    {"order": 3, "bbox": [40, 0, 50, 10], "center": [45, 5]},
                ],
            )

            self.assertEqual(metrics["query_item_recall"], 1.0)
            self.assertEqual(metrics["query_exact_count_rate"], 1.0)
            self.assertEqual(metrics["query_strict_hit_rate"], 1.0)
            self.assertEqual(gate["status"], "passed")
            self.assertEqual(failcases, [])

    def test_evaluate_query_detector_rows_records_count_mismatch_failcase(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_png(root / "eval" / "query" / "val" / "g1_000001.png", 64, 24, (255, 255, 255))
            rows = [
                {
                    "sample_id": "g1_000001",
                    "query_image": "eval/query/val/g1_000001.png",
                    "query_items": [
                        {"order": 1, "bbox": [0, 0, 10, 10], "center": [5, 5]},
                        {"order": 2, "bbox": [20, 0, 30, 10], "center": [25, 5]},
                        {"order": 3, "bbox": [40, 0, 50, 10], "center": [45, 5]},
                    ],
                }
            ]

            metrics, gate, failcases = group1_runner._evaluate_query_detector_rows(
                rows,
                dataset_root=root,
                predict_query_items=lambda path: [
                    {"order": 1, "bbox": [0, 0, 10, 10], "center": [5, 5]},
                    {"order": 2, "bbox": [20, 0, 30, 10], "center": [25, 5]},
                    {"order": 3, "bbox": [40, 0, 50, 10], "center": [45, 5]},
                    {"order": 4, "bbox": [52, 0, 58, 10], "center": [55, 5]},
                ],
            )

            self.assertEqual(metrics["query_item_recall"], 1.0)
            self.assertEqual(metrics["query_exact_count_rate"], 0.0)
            self.assertEqual(metrics["query_strict_hit_rate"], 0.0)
            self.assertEqual(gate["status"], "failed")
            self.assertIn("query_exact_count_rate", gate["failed_checks"])
            self.assertEqual(len(failcases), 1)
            self.assertEqual(failcases[0]["reason"], "count_mismatch")

    def test_evaluate_proposal_detector_rows_reports_passed_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_png(root / "eval" / "scene" / "val" / "g1_000001.png", 160, 80, (255, 255, 255))
            rows = [
                {
                    "sample_id": "g1_000001",
                    "query_image": "eval/query/val/g1_000001.png",
                    "scene_image": "eval/scene/val/g1_000001.png",
                    "query_items": [],
                    "scene_targets": [
                        {"order": 1, "bbox": [10, 10, 30, 30], "center": [20, 20]},
                        {"order": 2, "bbox": [50, 10, 70, 30], "center": [60, 20]},
                    ],
                    "distractors": [
                        {"bbox": [90, 10, 110, 30], "center": [100, 20]},
                    ],
                }
            ]

            metrics, gate, failcases = group1_runner._evaluate_proposal_detector_rows(
                rows,
                dataset_root=root,
                predict_scene_objects=lambda path: [
                    {"bbox": [10, 10, 30, 30], "center": [20, 20]},
                    {"bbox": [50, 10, 70, 30], "center": [60, 20]},
                    {"bbox": [90, 10, 110, 30], "center": [100, 20]},
                ],
            )

            self.assertEqual(metrics["proposal_object_recall"], 1.0)
            self.assertEqual(metrics["proposal_full_recall_rate"], 1.0)
            self.assertEqual(metrics["proposal_false_positive_per_sample"], 0.0)
            self.assertEqual(gate["status"], "passed")
            self.assertEqual(failcases, [])

    def test_evaluate_proposal_detector_rows_fails_on_missing_objects_and_false_positives(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_png(root / "eval" / "scene" / "val" / "g1_000001.png", 160, 80, (255, 255, 255))
            rows = [
                {
                    "sample_id": "g1_000001",
                    "query_image": "eval/query/val/g1_000001.png",
                    "scene_image": "eval/scene/val/g1_000001.png",
                    "query_items": [],
                    "scene_targets": [
                        {"order": 1, "bbox": [10, 10, 30, 30], "center": [20, 20]},
                        {"order": 2, "bbox": [50, 10, 70, 30], "center": [60, 20]},
                    ],
                    "distractors": [],
                }
            ]

            metrics, gate, failcases = group1_runner._evaluate_proposal_detector_rows(
                rows,
                dataset_root=root,
                predict_scene_objects=lambda path: [
                    {"bbox": [10, 10, 30, 30], "center": [20, 20]},
                    {"bbox": [120, 10, 140, 30], "center": [130, 20]},
                ],
            )

            self.assertEqual(metrics["proposal_object_recall"], 0.5)
            self.assertEqual(metrics["proposal_false_positive_per_sample"], 1.0)
            self.assertEqual(gate["status"], "failed")
            self.assertIn("proposal_object_recall", gate["failed_checks"])
            self.assertIn("proposal_false_positive_per_sample", gate["failed_checks"])
            self.assertEqual(len(failcases), 1)
            self.assertEqual(failcases[0]["reason"], "missing_and_false_positive")

    def test_runner_trains_query_detector_component_and_writes_gate_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_dataset_config(root)
            (root / "query-yolo").mkdir(parents=True, exist_ok=True)
            (root / "query-yolo" / "dataset.yaml").write_text(
                "path: .\ntrain: images/train\nval: images/val\nnames:\n  0: query_item\n",
                encoding="utf-8",
            )
            (root / "splits" / "val.jsonl").write_text(
                json.dumps(
                    {
                        "sample_id": "g1_000001",
                        "query_image": "eval/query/val/g1_000001.png",
                        "scene_image": "eval/scene/val/g1_000001.png",
                        "query_items": [
                            {"order": 1, "bbox": [0, 0, 10, 10], "center": [5, 5]},
                            {"order": 2, "bbox": [20, 0, 30, 10], "center": [25, 5]},
                            {"order": 3, "bbox": [40, 0, 50, 10], "center": [45, 5]},
                        ],
                        "scene_targets": [],
                        "distractors": [],
                        "label_source": "gold",
                        "source_batch": "batch_0001",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            _write_png(root / "eval" / "query" / "val" / "g1_000001.png", 64, 24, (255, 255, 255))

            def _fake_run(command: list[str], check: bool) -> None:
                del check
                if "query-detector" in command:
                    weights_dir = root / "runs" / "group1" / "smoke" / "query-detector" / "weights"
                    weights_dir.mkdir(parents=True, exist_ok=True)
                    (weights_dir / "best.pt").write_bytes(b"pt")
                    (weights_dir / "last.pt").write_bytes(b"pt")

            with patch("train.group1.runner.subprocess.run", side_effect=_fake_run):
                with patch(
                    "train.group1.runner._evaluate_query_detector_component",
                    return_value=(
                        {
                            "query_sample_count": 1,
                            "query_item_recall": 1.0,
                            "query_exact_count_rate": 1.0,
                            "query_full_recall_rate": 1.0,
                            "query_strict_hit_rate": 1.0,
                            "query_mean_iou": 1.0,
                        },
                        {
                            "status": "passed",
                            "thresholds": {"query_item_recall": 0.995},
                            "failed_checks": [],
                        },
                        [],
                    ),
                ):
                    exit_code = group1_runner.main(
                        [
                            "train",
                            "--dataset-config",
                            str(root / "dataset.json"),
                            "--project",
                            str(root / "runs" / "group1"),
                            "--name",
                            "smoke",
                            "--component",
                            "query-detector",
                            "--epochs",
                            "1",
                            "--batch",
                            "1",
                            "--imgsz",
                            "32",
                            "--device",
                            "cpu",
                        ]
                    )

            summary_path = root / "runs" / "group1" / "smoke" / "summary.json"
            self.assertEqual(exit_code, 0)
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertIn("query-detector", summary["components"])
            self.assertEqual(summary["components"]["query-detector"]["gate"]["status"], "passed")
            self.assertTrue((root / "runs" / "group1" / "smoke" / "query-detector" / "failcases.jsonl").exists())

    def test_runner_trains_proposal_detector_component_and_writes_gate_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_dataset_config(root)
            (root / "proposal-yolo").mkdir(parents=True, exist_ok=True)
            (root / "proposal-yolo" / "dataset.yaml").write_text(
                "path: .\ntrain: images/train\nval: images/val\nnames:\n  0: icon_object\n",
                encoding="utf-8",
            )
            (root / "splits" / "val.jsonl").write_text(
                json.dumps(
                    {
                        "sample_id": "g1_000001",
                        "query_image": "eval/query/val/g1_000001.png",
                        "scene_image": "eval/scene/val/g1_000001.png",
                        "query_items": [],
                        "scene_targets": [
                            {"order": 1, "bbox": [10, 10, 30, 30], "center": [20, 20]},
                        ],
                        "distractors": [],
                        "label_source": "gold",
                        "source_batch": "batch_0001",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            _write_png(root / "eval" / "scene" / "val" / "g1_000001.png", 160, 80, (255, 255, 255))

            def _fake_run(command: list[str], check: bool) -> None:
                del check
                if "proposal-detector" in command:
                    weights_dir = root / "runs" / "group1" / "smoke" / "proposal-detector" / "weights"
                    weights_dir.mkdir(parents=True, exist_ok=True)
                    (weights_dir / "best.pt").write_bytes(b"pt")
                    (weights_dir / "last.pt").write_bytes(b"pt")

            with patch("train.group1.runner.subprocess.run", side_effect=_fake_run):
                with patch(
                    "train.group1.runner._evaluate_proposal_detector_component",
                    return_value=(
                        {
                            "proposal_sample_count": 1,
                            "proposal_object_recall": 1.0,
                            "proposal_full_recall_rate": 1.0,
                            "proposal_false_positive_per_sample": 0.0,
                            "proposal_mean_iou": 1.0,
                        },
                        {
                            "status": "passed",
                            "thresholds": {"min": {"proposal_object_recall": 0.995}, "max": {}},
                            "failed_checks": [],
                        },
                        [],
                    ),
                ):
                    exit_code = group1_runner.main(
                        [
                            "train",
                            "--dataset-config",
                            str(root / "dataset.json"),
                            "--project",
                            str(root / "runs" / "group1"),
                            "--name",
                            "smoke",
                            "--component",
                            "proposal-detector",
                            "--epochs",
                            "1",
                            "--batch",
                            "1",
                            "--imgsz",
                            "32",
                            "--device",
                            "cpu",
                        ]
                    )

            summary_path = root / "runs" / "group1" / "smoke" / "summary.json"
            self.assertEqual(exit_code, 0)
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertIn("proposal-detector", summary["components"])
            self.assertEqual(summary["components"]["proposal-detector"]["gate"]["status"], "passed")
            self.assertTrue((root / "runs" / "group1" / "smoke" / "proposal-detector" / "failcases.jsonl").exists())

    def test_runner_predict_uses_query_detector_when_query_model_is_provided(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_dataset_config(root)
            source = root / "source.jsonl"
            source.write_text(
                json.dumps(
                    {
                        "sample_id": "g1_000001",
                        "query_image": "eval/query/val/g1_000001.png",
                        "scene_image": "eval/scene/val/g1_000001.png",
                        "query_items": [
                            {"order": 1, "asset_id": "asset_a", "template_id": "tpl_a", "variant_id": "var_a", "bbox": [0, 0, 10, 10], "center": [5, 5]},
                            {"order": 2, "asset_id": "asset_b", "template_id": "tpl_b", "variant_id": "var_b", "bbox": [20, 0, 30, 10], "center": [25, 5]},
                            {"order": 3, "asset_id": "asset_c", "template_id": "tpl_c", "variant_id": "var_c", "bbox": [40, 0, 50, 10], "center": [45, 5]},
                        ],
                        "scene_targets": [
                            {"order": 1, "asset_id": "asset_a", "template_id": "tpl_a", "variant_id": "var_a", "bbox": [80, 32, 120, 72], "center": [100, 52]},
                            {"order": 2, "asset_id": "asset_b", "template_id": "tpl_b", "variant_id": "var_b", "bbox": [126, 32, 146, 52], "center": [136, 42]},
                            {"order": 3, "asset_id": "asset_c", "template_id": "tpl_c", "variant_id": "var_c", "bbox": [20, 32, 40, 52], "center": [30, 42]},
                        ],
                        "distractors": [],
                        "label_source": "gold",
                        "source_batch": "batch_0001",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            _write_png(root / "eval" / "query" / "val" / "g1_000001.png", 64, 24, (255, 255, 255))
            _write_png(root / "eval" / "scene" / "val" / "g1_000001.png", 160, 80, (255, 255, 255))

            class _FakeTensor:
                def __init__(self, values):
                    self._values = values

                def tolist(self):
                    return self._values

            class _FakeBoxes:
                def __init__(self, xyxy, cls_ids, confs):
                    self.xyxy = _FakeTensor(xyxy)
                    self.cls = _FakeTensor(cls_ids)
                    self.conf = _FakeTensor(confs)

            class _FakeResult:
                def __init__(self, xyxy, cls_ids, confs):
                    self.boxes = _FakeBoxes(xyxy, cls_ids, confs)
                    self.names = {0: "icon_object"}

            class _FakeYOLO:
                def __init__(self, model_path: str):
                    self.model_path = model_path

                def predict(self, *, source: str, imgsz: int, conf: float, device: str, verbose: bool):
                    del source, imgsz, conf, device, verbose
                    if "query-detector" in self.model_path:
                        return [_FakeResult([[0, 0, 10, 10], [20, 0, 30, 10], [40, 0, 50, 10]], [0, 0, 0], [0.91, 0.89, 0.87])]
                    return [_FakeResult([[80, 32, 120, 72]], [0], [0.95])]

            fake_mapping = type(
                "Mapping",
                (),
                {
                    "status": "matched",
                    "ordered_targets": [
                        type("Target", (), {"order": 1, "bbox": [80, 32, 120, 72], "center": [100, 52], "score": 0.95})()
                    ],
                },
            )()

            with patch.dict(sys.modules, {"ultralytics": types.SimpleNamespace(YOLO=_FakeYOLO)}):
                with patch("train.group1.runner.load_icon_embedder_runtime", return_value=object()):
                    with patch("train.group1.runner.map_group1_instances", return_value=fake_mapping) as map_instances:
                        with patch(
                            "train.group1.runner.split_group1_query_image",
                            side_effect=AssertionError("query splitter should not run when query detector is provided"),
                        ):
                            exit_code = group1_runner.main(
                                [
                                    "predict",
                                    "--dataset-config",
                                    str(root / "dataset.json"),
                                    "--query-model",
                                    str(root / "runs" / "group1" / "smoke" / "query-detector" / "weights" / "best.pt"),
                                    "--proposal-model",
                                    str(root / "runs" / "group1" / "smoke" / "proposal-detector" / "weights" / "best.pt"),
                                    "--embedder-model",
                                    str(root / "runs" / "group1" / "smoke" / "icon-embedder" / "weights" / "best.pt"),
                                    "--source",
                                    str(source),
                                    "--project",
                                    str(root / "reports" / "group1"),
                                    "--name",
                                    "predict_smoke",
                                    "--imgsz",
                                    "32",
                                    "--device",
                                    "cpu",
                                ]
                            )

            self.assertEqual(exit_code, 0)
            predicted_query_items = map_instances.call_args.args[0]
            self.assertEqual(len(predicted_query_items), 3)
            self.assertEqual(predicted_query_items[0]["order"], 1)
            labels_path = root / "reports" / "group1" / "predict_smoke" / "labels.jsonl"
            self.assertTrue(labels_path.exists())


def _write_minimal_dataset_config(root: Path) -> None:
    (root / "splits").mkdir(parents=True, exist_ok=True)
    (root / "dataset.json").write_text(
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


def _write_triplets_jsonl(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "split": "train",
                "sample_id": "g1_000001",
                "anchor_image": "embedding/queries/train/g1_000001_01.png",
                "positive_image": "embedding/candidates/train/g1_000001_01.png",
                "negative_image": "embedding/candidates/train/g1_000001_neg.png",
                "anchor": {
                    "order": 1,
                    "bbox": [0, 0, 16, 16],
                    "center": [8, 8],
                    "asset_id": "asset_red",
                    "template_id": "tpl_red",
                    "variant_id": "var_red",
                },
                "positive": {
                    "order": 1,
                    "bbox": [0, 0, 16, 16],
                    "center": [8, 8],
                    "asset_id": "asset_red",
                    "template_id": "tpl_red",
                    "variant_id": "var_red",
                },
                "negative": {
                    "bbox": [0, 0, 16, 16],
                    "center": [8, 8],
                    "asset_id": "asset_blue",
                    "template_id": "tpl_blue",
                    "variant_id": "var_blue",
                },
                "negative_role": "distractor",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_icon_embedder_checkpoint(path: Path, *, embedding_dim: int, image_size: int) -> None:
    import torch

    model = IconEmbedder(embedding_dim=embedding_dim)
    torch.save(
        {
            "model_state": model.state_dict(),
            "imgsz": image_size,
            "embedding_dim": embedding_dim,
            "best_score": 1.0,
            "metrics": {"embedding_recall_at_1": 1.0},
        },
        path,
    )


if __name__ == "__main__":
    unittest.main()
