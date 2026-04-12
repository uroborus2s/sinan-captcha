from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from auto_train.runners import dataset, evaluate, test, train
from train.group1.service import Group1TrainingJob
from evaluate.service import EvaluationResult
from modeltest.service import ModelTestResult


class AutoTrainDatasetRunnerTests(unittest.TestCase):
    def test_dataset_runner_executes_generator_command_and_returns_dataset_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "generator-workspace"
            dataset_dir = root / "datasets" / "group1" / "firstpass"
            override_file = root / "studies" / "group1" / "study_001" / "trials" / "trial_0002" / "generator_override.json"
            workspace.mkdir(parents=True)
            override_file.parent.mkdir(parents=True)
            override_file.write_text('{"project":{"sample_count":320}}', encoding="utf-8")
            executed: list[list[str]] = []

            result = dataset.run_dataset_request(
                dataset.DatasetRunnerRequest(
                    task="group1",
                    dataset_version="firstpass",
                    generator_workspace=workspace,
                    dataset_dir=dataset_dir,
                    preset="hard",
                    override_file=override_file,
                    generator_executable="sinan-generator.exe",
                    force=True,
                ),
                executor=lambda command: executed.append(command),
            )

            self.assertEqual(result.record.task, "group1")
            self.assertEqual(result.record.dataset_version, "firstpass")
            self.assertEqual(result.record.dataset_root, str(dataset_dir))
            self.assertIn("sinan-generator.exe", result.command)
            self.assertIn("--preset hard", result.command)
            self.assertIn("--override-file", result.command)
            self.assertIn("--force", result.command)
            self.assertEqual(executed[0][0], "sinan-generator.exe")
            self.assertIn("--preset", executed[0])
            self.assertIn("hard", executed[0])
            self.assertIn("--override-file", executed[0])
            self.assertIn(str(override_file), executed[0])

    def test_dataset_runner_rejects_missing_workspace_as_non_retryable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with self.assertRaises(dataset.RunnerExecutionError) as ctx:
                dataset.run_dataset_request(
                    dataset.DatasetRunnerRequest(
                        task="group1",
                        dataset_version="firstpass",
                        generator_workspace=root / "missing-workspace",
                        dataset_dir=root / "datasets" / "group1" / "firstpass",
                    )
                )

            self.assertEqual(ctx.exception.stage, "BUILD_DATASET")
            self.assertEqual(ctx.exception.reason, "missing_input")
            self.assertFalse(ctx.exception.retryable)


class AutoTrainTrainRunnerTests(unittest.TestCase):
    def test_train_runner_uses_group2_architecture_name_for_fresh_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            train_root = Path(tmpdir)
            dataset_config = train_root / "datasets" / "group2" / "firstpass" / "dataset.json"
            dataset_config.parent.mkdir(parents=True)
            dataset_config.write_text(
                '{"task":"group2","format":"sinan.group2.paired.v1","splits":{"train":"splits/train.jsonl","val":"splits/val.jsonl","test":"splits/test.jsonl"}}',
                encoding="utf-8",
            )

            captured_jobs: list[object] = []
            result = train.run_training_request(
                train.TrainRunnerRequest(
                    task="group2",
                    train_root=train_root,
                    dataset_version="firstpass",
                    train_name="trial_0001",
                    train_mode="fresh",
                ),
                executor=lambda job: captured_jobs.append(job) or 0,
            )

            self.assertEqual(result.record.task, "group2")
            self.assertEqual(result.record.params["model"], "paired_cnn_v1")
            self.assertIn("--model", result.command)
            self.assertIn("paired_cnn_v1", result.command)
            self.assertEqual(len(captured_jobs), 1)

    def test_train_runner_builds_group1_job_from_previous_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            train_root = Path(tmpdir)
            dataset_config = train_root / "datasets" / "group1" / "firstpass_v2" / "dataset.json"
            dataset_config.parent.mkdir(parents=True)
            dataset_config.write_text('{"task":"group1","format":"sinan.group1.instance_matching.v1","splits":{"train":"splits/train.jsonl","val":"splits/val.jsonl","test":"splits/test.jsonl"},"query_detector":{"format":"yolo.detect.v1","dataset_yaml":"query-yolo/dataset.yaml"},"proposal_detector":{"format":"yolo.detect.v1","dataset_yaml":"proposal-yolo/dataset.yaml"},"embedding":{"format":"sinan.group1.embedding.v1","queries_dir":"embedding/queries","candidates_dir":"embedding/candidates","pairs_jsonl":"embedding/pairs.jsonl","triplets_jsonl":"embedding/triplets.jsonl"},"eval":{"format":"sinan.group1.eval.v1","labels_jsonl":"eval/labels.jsonl"}}', encoding="utf-8")
            query_best = train_root / "runs" / "group1" / "trial_0001" / "query-detector" / "weights" / "best.pt"
            proposal_best = train_root / "runs" / "group1" / "trial_0001" / "proposal-detector" / "weights" / "best.pt"
            embedder_best = train_root / "runs" / "group1" / "trial_0001" / "icon-embedder" / "weights" / "best.pt"
            query_best.parent.mkdir(parents=True)
            proposal_best.parent.mkdir(parents=True)
            embedder_best.parent.mkdir(parents=True)
            query_best.write_text("weights", encoding="utf-8")
            proposal_best.write_text("weights", encoding="utf-8")
            embedder_best.write_text("weights", encoding="utf-8")

            captured_jobs: list[object] = []
            result = train.run_training_request(
                train.TrainRunnerRequest(
                    task="group1",
                    train_root=train_root,
                    dataset_version="firstpass_v2",
                    train_name="trial_0002",
                    train_mode="from_run",
                    base_run="trial_0001",
                    epochs=140,
                    batch=8,
                ),
                executor=lambda job: captured_jobs.append(job) or 0,
            )

            self.assertEqual(result.record.task, "group1")
            self.assertEqual(result.record.train_name, "trial_0002")
            self.assertEqual(result.record.resumed_from, "trial_0001")
            self.assertEqual(result.record.run_dir, str(train_root / "runs" / "group1" / "trial_0002"))
            self.assertEqual(result.record.best_weights, str(train_root / "runs" / "group1" / "trial_0002" / "proposal-detector" / "weights" / "best.pt"))
            self.assertEqual(result.record.params["query_model_best"], str(train_root / "runs" / "group1" / "trial_0002" / "query-detector" / "weights" / "best.pt"))
            self.assertIn("--query-model", result.command)
            self.assertIn(str(query_best), result.command)
            self.assertEqual(result.record.params["embedder_model_best"], str(train_root / "runs" / "group1" / "trial_0002" / "icon-embedder" / "weights" / "best.pt"))
            self.assertIn("--proposal-model", result.command)
            self.assertIn(str(proposal_best), result.command)
            self.assertIn("--embedder-model", result.command)
            self.assertIn(str(embedder_best), result.command)
            self.assertEqual(len(captured_jobs), 1)
            self.assertIsInstance(captured_jobs[0], Group1TrainingJob)
            self.assertEqual(captured_jobs[0].query_model, str(query_best))
            self.assertEqual(captured_jobs[0].embedder_model, str(embedder_best))

    def test_train_runner_rejects_invalid_request_without_base_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            train_root = Path(tmpdir)

            with self.assertRaises(train.RunnerExecutionError) as ctx:
                train.run_training_request(
                    train.TrainRunnerRequest(
                        task="group2",
                        train_root=train_root,
                        dataset_version="firstpass",
                        train_name="trial_0003",
                        train_mode="from_run",
                        base_run=None,
                    )
                )

            self.assertEqual(ctx.exception.stage, "TRAIN")
            self.assertEqual(ctx.exception.reason, "invalid_request")
            self.assertFalse(ctx.exception.retryable)

    def test_train_runner_group2_from_run_falls_back_to_last_weights_when_best_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            train_root = Path(tmpdir)
            dataset_config = train_root / "datasets" / "group2" / "study_trial_0004" / "dataset.json"
            dataset_config.parent.mkdir(parents=True)
            dataset_config.write_text(
                '{"task":"group2","format":"sinan.group2.paired.v1","splits":{"train":"splits/train.jsonl","val":"splits/val.jsonl","test":"splits/test.jsonl"}}',
                encoding="utf-8",
            )
            last_weights = train_root / "runs" / "group2" / "trial_0003" / "weights" / "last.pt"
            last_weights.parent.mkdir(parents=True)
            last_weights.write_text("weights", encoding="utf-8")

            captured_jobs: list[object] = []
            result = train.run_training_request(
                train.TrainRunnerRequest(
                    task="group2",
                    train_root=train_root,
                    dataset_version="study_trial_0004",
                    train_name="trial_0004",
                    train_mode="from_run",
                    base_run="trial_0003",
                    epochs=120,
                    batch=16,
                ),
                executor=lambda job: captured_jobs.append(job) or 0,
            )

            self.assertEqual(result.record.task, "group2")
            self.assertEqual(result.record.resumed_from, "trial_0003")
            self.assertIn(str(last_weights), result.command)
            self.assertEqual(len(captured_jobs), 1)


class AutoTrainTestRunnerTests(unittest.TestCase):
    def test_test_runner_converts_model_test_result_into_test_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            train_root = Path(tmpdir)
            dataset_config = train_root / "datasets" / "group1" / "firstpass" / "dataset.json"
            source = train_root / "datasets" / "group1" / "firstpass" / "splits" / "val.jsonl"
            proposal_model_path = train_root / "runs" / "group1" / "trial_0001" / "proposal-detector" / "weights" / "best.pt"
            embedder_model_path = train_root / "runs" / "group1" / "trial_0001" / "icon-embedder" / "weights" / "best.pt"
            for path in (dataset_config.parent, source.parent, proposal_model_path.parent, embedder_model_path.parent):
                path.mkdir(parents=True, exist_ok=True)
            dataset_config.write_text('{"task":"group1","format":"sinan.group1.instance_matching.v1","splits":{"train":"splits/train.jsonl","val":"splits/val.jsonl","test":"splits/test.jsonl"},"proposal_detector":{"format":"yolo.detect.v1","dataset_yaml":"proposal-yolo/dataset.yaml"},"embedding":{"format":"sinan.group1.embedding.v1","queries_dir":"embedding/queries","candidates_dir":"embedding/candidates","pairs_jsonl":"embedding/pairs.jsonl","triplets_jsonl":"embedding/triplets.jsonl"},"eval":{"format":"sinan.group1.eval.v1","labels_jsonl":"eval/labels.jsonl"}}', encoding="utf-8")
            source.write_text('{"sample_id":"g1_000001","query_image":"eval/query/val/g1_000001.png","scene_image":"eval/scene/val/g1_000001.png","query_items":[{"order":1,"asset_id":"asset_house","template_id":"tpl_house","variant_id":"var_outline","bbox":[8,8,28,28],"center":[18,18]}],"scene_targets":[{"order":1,"asset_id":"asset_house","template_id":"tpl_house","variant_id":"var_outline","bbox":[80,32,120,72],"center":[100,52]}],"distractors":[],"label_source":"gold","source_batch":"batch_0001"}\n', encoding="utf-8")
            proposal_model_path.write_text("weights", encoding="utf-8")
            embedder_model_path.write_text("weights", encoding="utf-8")

            observed_embedder_path: Path | None = None
            observed_has_legacy_query_path: bool | None = None

            def _fake_runner(_request):
                nonlocal observed_embedder_path, observed_has_legacy_query_path
                observed_embedder_path = _request.embedder_model_path
                observed_has_legacy_query_path = any(name.startswith("query_") for name in vars(_request))
                return ModelTestResult(
                    task="group1",
                    dataset_version="firstpass",
                    train_name="trial_0001",
                    model_path=proposal_model_path,
                    embedder_model_path=embedder_model_path,
                    dataset_config=dataset_config,
                    source=source,
                    project_dir=train_root / "reports" / "group1",
                    report_dir=train_root / "reports" / "group1" / "test_trial_0001",
                    predict_output_dir=train_root / "reports" / "group1" / "predict_trial_0001",
                    val_output_dir=train_root / "reports" / "group1" / "val_trial_0001",
                    source_image_count=20,
                    predicted_image_count=20,
                    metrics={
                        "single_target_hit_rate": 0.91,
                        "full_sequence_hit_rate": 0.88,
                        "mean_center_error_px": 4.0,
                        "order_error_rate": 0.05,
                    },
                    verdict_title="可继续优化",
                    verdict_detail="这轮模型已经比较稳。",
                    next_actions=["继续补弱类"],
                    predict_command="uv run python -m train.group1.runner predict ...",
                    val_command="uv run sinan evaluate --task group1 ...",
                )

            result = test.run_test_request(
                test.TestRunnerRequest(
                    task="group1",
                    train_root=train_root,
                    dataset_version="firstpass",
                    train_name="trial_0001",
                ),
                runner=_fake_runner,
            )

            self.assertEqual(result.record.task, "group1")
            self.assertEqual(result.record.dataset_version, "firstpass")
            self.assertEqual(result.record.metrics["full_sequence_hit_rate"], 0.88)
            self.assertEqual(observed_embedder_path, embedder_model_path)
            self.assertFalse(observed_has_legacy_query_path)
            self.assertIn("predict", result.predict_command)
            self.assertIn("val", result.val_command)


class AutoTrainEvaluateRunnerTests(unittest.TestCase):
    def test_evaluate_runner_converts_evaluation_result_into_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            gold_dir = root / "gold"
            prediction_dir = root / "prediction"
            report_dir = root / "reports" / "group2" / "eval_trial_0001"
            gold_dir.mkdir(parents=True)
            prediction_dir.mkdir(parents=True)
            (gold_dir / "labels.jsonl").write_text("{}\n", encoding="utf-8")
            (prediction_dir / "labels.jsonl").write_text("{}\n", encoding="utf-8")

            result = evaluate.run_evaluation_request(
                evaluate.EvaluateRunnerRequest(
                    task="group2",
                    gold_dir=gold_dir,
                    prediction_dir=prediction_dir,
                    report_dir=report_dir,
                ),
                evaluator=lambda _request: EvaluationResult(
                    task="group2",
                    sample_count=20,
                    failure_count=2,
                    metrics={"point_hit_rate": 0.9, "mean_iou": 0.82},
                    report_dir=report_dir,
                ),
            )

            self.assertEqual(result.record.task, "group2")
            self.assertTrue(result.record.available)
            self.assertEqual(result.record.failure_count, 2)
            self.assertIn("uv run sinan evaluate", result.command)

    def test_evaluate_runner_marks_command_failures_as_retryable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            gold_dir = root / "gold"
            prediction_dir = root / "prediction"
            gold_dir.mkdir(parents=True)
            prediction_dir.mkdir(parents=True)
            (gold_dir / "labels.jsonl").write_text("{}\n", encoding="utf-8")
            (prediction_dir / "labels.jsonl").write_text("{}\n", encoding="utf-8")

            with self.assertRaises(evaluate.RunnerExecutionError) as ctx:
                evaluate.run_evaluation_request(
                    evaluate.EvaluateRunnerRequest(
                        task="group1",
                        gold_dir=gold_dir,
                        prediction_dir=prediction_dir,
                        report_dir=root / "reports" / "group1" / "eval_trial_0001",
                    ),
                    evaluator=lambda _request: (_ for _ in ()).throw(RuntimeError("模型测试失败，请先查看上面的 YOLO 原始输出。")),
                )

            self.assertEqual(ctx.exception.stage, "EVALUATE")
            self.assertEqual(ctx.exception.reason, "command_failed")
            self.assertTrue(ctx.exception.retryable)


if __name__ == "__main__":
    unittest.main()
