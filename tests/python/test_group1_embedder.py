from __future__ import annotations

import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from core.train.group1.embedder import (
    Group1TripletDataset,
    IconEmbedder,
    evaluate_retrieval,
    load_embedding_triplets,
    load_icon_embedder_runtime,
    train_icon_embedder,
)
from core.train.group1.dataset import load_group1_dataset_config
from core.train.group1 import runner as group1_runner


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
