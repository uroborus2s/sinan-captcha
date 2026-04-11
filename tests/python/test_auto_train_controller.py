from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import tempfile
import unittest
from pathlib import Path

from auto_train import controller, contracts, storage


def _train_result(task: str, train_root: Path, train_name: str) -> controller.runners.train.TrainRunnerResult:
    return controller.runners.train.TrainRunnerResult(
        record=contracts.TrainRecord(
            task=task,
            train_name=train_name,
            run_dir=str(train_root / "runs" / task / train_name),
            params={"epochs": 120, "batch": 16, "imgsz": 640, "model": "yolo26n.pt"},
            best_weights=str(train_root / "runs" / task / train_name / "weights" / "best.pt"),
            last_weights=str(train_root / "runs" / task / train_name / "weights" / "last.pt"),
        ),
        command="uv run sinan train",
    )


def _write_dataset_config(train_root: Path, task: str, dataset_version: str) -> None:
    dataset_dir = train_root / "datasets" / task / dataset_version
    dataset_dir.mkdir(parents=True, exist_ok=True)
    if task == "group1":
        payload = {
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
        }
    else:
        payload = {
            "task": "group2",
            "format": "sinan.group2.paired.v1",
            "splits": {
                "train": "splits/train.jsonl",
                "val": "splits/val.jsonl",
                "test": "splits/test.jsonl",
            },
            "images": {
                "master_dir": "master",
                "tile_dir": "tile",
            },
        }
    (dataset_dir / "dataset.json").write_text(json.dumps(payload), encoding="utf-8")


def _group2_trial_summary(trial_id: str, *, score: float, trend: str = "baseline") -> contracts.ResultSummaryRecord:
    return contracts.ResultSummaryRecord(
        study_name="study_001",
        task="group2",
        trial_id=trial_id,
        dataset_version="firstpass",
        train_name=trial_id,
        primary_metric="point_hit_rate",
        primary_score=score,
        test_metrics={"point_hit_rate": score, "mean_iou": 0.9, "mean_center_error_px": 6.0},
        evaluation_available=True,
        evaluation_metrics={"point_hit_rate": score, "mean_iou": 0.9, "mean_center_error_px": 6.0},
        failure_count=0,
        trend=trend,
        delta_vs_previous=0.0,
        delta_vs_best=0.0,
        weak_classes=[],
        failure_patterns=[],
        recent_trials=[],
        best_trial=None,
        evidence=["test"],
    )


class AutoTrainControllerTests(unittest.TestCase):
    def test_composite_ranking_score_prioritizes_business_eval_result(self) -> None:
        offline_heavier = controller._composite_ranking_score(
            offline_score=0.99,
            difficulty_score=1.12,
            business_success_rate=0.60,
            commercial_ready=False,
        )
        business_heavier = controller._composite_ranking_score(
            offline_score=0.93,
            difficulty_score=1.0,
            business_success_rate=0.90,
            commercial_ready=True,
        )

        self.assertGreater(business_heavier, offline_heavier)
        self.assertAlmostEqual(offline_heavier, 1.78704, places=5)
        self.assertAlmostEqual(business_heavier, 2.594, places=5)

    def test_build_leaderboard_entry_uses_composite_ranking_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            train_root.mkdir(parents=True, exist_ok=True)
            generator_workspace.mkdir(parents=True, exist_ok=True)

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group2",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="v1",
                ),
            )

            storage.write_trial_input_record(
                ctrl.paths.input_file("trial_0002"),
                contracts.TrialInputRecord(
                    trial_id="trial_0002",
                    task="group2",
                    dataset_version="study_001_trial_0002",
                    train_name="trial_0002",
                    train_mode="from_run",
                    base_run="trial_0001",
                    params={"epochs": 120, "batch": 16, "imgsz": 192, "device": "0"},
                    dataset_preset="hard",
                ),
            )

            summary = contracts.ResultSummaryRecord(
                study_name="study_001",
                task="group2",
                trial_id="trial_0002",
                dataset_version="study_001_trial_0002",
                train_name="trial_0002",
                primary_metric="point_hit_rate",
                primary_score=0.99,
                test_metrics={"point_hit_rate": 0.99, "mean_iou": 0.91, "mean_center_error_px": 4.0},
                evaluation_available=True,
                evaluation_metrics={"point_hit_rate": 0.99, "mean_iou": 0.91, "mean_center_error_px": 4.0},
                failure_count=0,
                trend="improving",
                delta_vs_previous=0.01,
                delta_vs_best=0.0,
                weak_classes=[],
                failure_patterns=[],
                recent_trials=[],
                best_trial=None,
                evidence=["test"],
            )
            decision = contracts.DecisionRecord(
                trial_id="trial_0002",
                decision="PROMOTE_BRANCH",
                confidence=0.95,
                reason="group2_targets_met",
                next_action={"dataset_action": "freeze", "train_action": "promote"},
                evidence=["targets_met"],
                agent=contracts.AgentRef(provider="rules", name="policy-judge", model="policy-v1"),
            )
            business_record = contracts.BusinessEvalRecord(
                trial_id="trial_0002",
                task="group2",
                train_name="trial_0002",
                cases_root=str(root / "business-cases"),
                available_cases=120,
                total_cases=30,
                passed_cases=25,
                success_rate=0.82,
                success_threshold=0.95,
                min_cases=30,
                sample_size=30,
                commercial_ready=False,
                point_tolerance_px=12,
                iou_threshold=0.5,
                sampled_source=str(root / "reports" / "trial_0002" / "_sampled_source" / "labels.jsonl"),
                report_dir=str(root / "reports" / "trial_0002"),
                prediction_dir=str(root / "reports" / "trial_0002" / "modeltest" / "predict"),
                evaluation_report_dir=str(root / "reports" / "trial_0002" / "evaluation"),
                case_results=[],
                evidence=["business_success_rate=0.82"],
            )

            entry = ctrl._build_leaderboard_entry(
                summary_record=summary,
                decision=decision,
                business_record=business_record,
            )

            self.assertEqual(entry.metrics["dataset_preset"], "hard")
            self.assertGreater(float(entry.metrics["difficulty_score"]), 1.0)
            self.assertAlmostEqual(float(entry.metrics["business_success_rate"]), 0.82, places=6)
            self.assertGreater(float(entry.metrics["ranking_score"]), float(entry.metrics["offline_score"]))

    def test_business_goal_regenerate_uses_composite_best_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            train_root.mkdir(parents=True, exist_ok=True)
            generator_workspace.mkdir(parents=True, exist_ok=True)

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group2",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="v1",
                ),
            )

            leaderboard = contracts.LeaderboardRecord(
                study_name="study_001",
                task="group2",
                primary_metric="point_hit_rate",
                entries=[
                    contracts.LeaderboardEntry(
                        trial_id="trial_0001",
                        dataset_version="v1",
                        train_name="trial_0001",
                        primary_score=1.0,
                        metrics={"ranking_score": 0.98},
                    ),
                    contracts.LeaderboardEntry(
                        trial_id="trial_0002",
                        dataset_version="study_001_trial_0002",
                        train_name="trial_0002",
                        primary_score=0.99,
                        metrics={"ranking_score": 1.06},
                    ),
                ],
            )
            summary = contracts.ResultSummaryRecord(
                study_name="study_001",
                task="group2",
                trial_id="trial_0003",
                dataset_version="study_001_trial_0003",
                train_name="trial_0003",
                primary_metric="point_hit_rate",
                primary_score=0.97,
                test_metrics={"point_hit_rate": 0.97},
                evaluation_available=True,
                evaluation_metrics={"point_hit_rate": 0.97},
                failure_count=0,
                trend="plateau",
                delta_vs_previous=0.0,
                delta_vs_best=-0.02,
                weak_classes=[],
                failure_patterns=[],
                recent_trials=[],
                best_trial=None,
                evidence=["plateau"],
            )
            decision = contracts.DecisionRecord(
                trial_id="trial_0003",
                decision="REGENERATE_DATA",
                confidence=0.9,
                reason="business_gate_blocked",
                next_action={"dataset_action": "new_version", "train_action": "from_run", "base_run": "trial_0003"},
                evidence=["business_gate_blocked"],
                agent=contracts.AgentRef(provider="rules", name="policy-judge", model="policy-v1"),
            )

            regenerated = ctrl._regenerate_decision_for_business_goal(
                summary_record=summary,
                decision=decision,
                business_record=None,
                leaderboard=leaderboard,
            )

            self.assertEqual(regenerated.next_action["base_run"], "trial_0002")

    def test_prune_model_runs_keeps_only_top_three_train_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            runs_root = train_root / "runs" / "group2"
            generator_workspace.mkdir(parents=True, exist_ok=True)
            for train_name in ("trial_0001", "trial_0002", "trial_0003", "trial_0004"):
                weights_dir = runs_root / train_name / "weights"
                weights_dir.mkdir(parents=True, exist_ok=True)
                (weights_dir / "best.pt").write_text("best", encoding="utf-8")

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group2",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="v1",
                ),
            )
            leaderboard = contracts.LeaderboardRecord(
                study_name="study_001",
                task="group2",
                primary_metric="point_hit_rate",
                entries=[
                    contracts.LeaderboardEntry(
                        trial_id="trial_0002",
                        dataset_version="v2",
                        train_name="trial_0002",
                        primary_score=0.99,
                        metrics={"ranking_score": 1.08},
                    ),
                    contracts.LeaderboardEntry(
                        trial_id="trial_0003",
                        dataset_version="v3",
                        train_name="trial_0003",
                        primary_score=0.98,
                        metrics={"ranking_score": 1.05},
                    ),
                    contracts.LeaderboardEntry(
                        trial_id="trial_0004",
                        dataset_version="v4",
                        train_name="trial_0004",
                        primary_score=0.97,
                        metrics={"ranking_score": 1.03},
                    ),
                    contracts.LeaderboardEntry(
                        trial_id="trial_0001",
                        dataset_version="v1",
                        train_name="trial_0001",
                        primary_score=1.0,
                        metrics={"ranking_score": 0.96},
                    ),
                ],
            )

            ctrl._prune_model_runs(leaderboard)

            self.assertFalse((runs_root / "trial_0001").exists())
            self.assertTrue((runs_root / "trial_0002").exists())
            self.assertTrue((runs_root / "trial_0003").exists())
            self.assertTrue((runs_root / "trial_0004").exists())

    def test_hydrate_result_summary_payload_restores_missing_deterministic_fields(self) -> None:
        fallback = contracts.ResultSummaryRecord(
            study_name="study_001",
            task="group1",
            trial_id="trial_0002",
            dataset_version="study_001_trial_0002",
            train_name="trial_0002",
            primary_metric="map50_95",
            primary_score=0.79,
            test_metrics={"map50_95": 0.79},
            evaluation_available=True,
            evaluation_metrics={"map50_95": 0.79},
            failure_count=7,
            trend="baseline",
            delta_vs_previous=None,
            delta_vs_best=None,
            weak_classes=[],
            failure_patterns=["order_errors"],
            recent_trials=[
                contracts.ResultSummarySnapshot(
                    trial_id="trial_0001",
                    dataset_version="firstpass",
                    train_name="trial_0001",
                    primary_score=0.85,
                    metrics={"map50_95": 0.85},
                    decision="REGENERATE_DATA",
                )
            ],
            best_trial=contracts.ResultSummarySnapshot(
                trial_id="trial_0001",
                dataset_version="firstpass",
                train_name="trial_0001",
                primary_score=0.85,
                metrics={"map50_95": 0.85},
                decision="REGENERATE_DATA",
            ),
            evidence=["fallback"],
        )

        payload = {
            "study_name": "study_001",
            "task": "group1",
            "trial_id": "trial_0002",
            "primary_metric": "map50_95",
            "primary_score": 0.79,
            "test_metrics": {"map50_95": 0.79},
            "evaluation_available": True,
            "evaluation_metrics": {"map50_95": 0.79},
            "failure_count": 7,
            "trend": "baseline",
            "delta_vs_previous": None,
            "delta_vs_best": None,
            "weak_classes": [],
            "failure_patterns": ["order_errors"],
            "recent_trials": [{"trial_id": "trial_0001", "metrics": {"map50_95": 0.85}}],
            "best_trial": {"trial_id": "trial_0001", "metrics": {"map50_95": 0.85}},
            "evidence": ["model"],
        }

        hydrated = controller._hydrate_result_summary_payload(payload, fallback_record=fallback)
        record = contracts.ResultSummaryRecord.from_dict(hydrated)

        self.assertEqual(record.dataset_version, "study_001_trial_0002")
        self.assertEqual(record.train_name, "trial_0002")
        self.assertIsNotNone(record.best_trial)
        assert record.best_trial is not None
        self.assertEqual(record.best_trial.dataset_version, "firstpass")
        self.assertEqual(record.best_trial.train_name, "trial_0001")
        self.assertEqual(record.recent_trials[0].dataset_version, "firstpass")
        self.assertEqual(record.recent_trials[0].train_name, "trial_0001")

    def test_record_opencode_trace_writes_log_json_and_terminal_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            train_root.mkdir(parents=True, exist_ok=True)
            generator_workspace.mkdir(parents=True, exist_ok=True)
            terminal_lines: list[str] = []

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group1",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                    judge_provider="opencode",
                ),
                dependencies=controller.ControllerDependencies(
                    console_writer=terminal_lines.append,
                ),
            )

            trace = controller.opencode_runtime.OpenCodeTraceRecord(
                created_at="2026-04-05T10:00:00+00:00",
                command_name="judge-trial",
                arguments=("study_001", "group1", "trial_0001"),
                project_root=str(train_root),
                attach_url="http://127.0.0.1:4096",
                model="gemma4",
                command=("opencode", "run", "--command", "judge-trial"),
                command_markdown_path=str(train_root / ".opencode" / "commands" / "judge-trial.md"),
                command_markdown_text="judge markdown body",
                command_markdown_truncated=False,
                command_markdown_error=None,
                skill_markdown_path=str(train_root / ".opencode" / "skills" / "training-judge" / "SKILL.md"),
                skill_markdown_text="training judge skill body",
                skill_markdown_truncated=False,
                skill_markdown_error=None,
                attached_files=(
                    controller.opencode_runtime.OpenCodeAttachedFileTrace(
                        path=str(ctrl.paths.result_summary_file("trial_0001")),
                        exists=True,
                        size_bytes=12,
                        content_text='{"metric": 0.85}',
                        truncated=False,
                        read_error=None,
                    ),
                ),
                stdout='{"decision":"REGENERATE_DATA"}',
                stderr="",
                returncode=0,
                success=True,
                error_message=None,
            )

            ctrl._record_opencode_trace(trace)

            log_text = ctrl.paths.opencode_log_file.read_text(encoding="utf-8")
            self.assertIn("OpenCode Trace: judge-trial [trial_0001]", log_text)
            self.assertIn('{"decision":"REGENERATE_DATA"}', log_text)
            self.assertIn("raw_stdout_file:", log_text)
            self.assertIn("raw_stderr_file:", log_text)

            trace_files = list(ctrl.paths.trial_opencode_trace_root("trial_0001").glob("*.json"))
            self.assertEqual(len(trace_files), 1)
            payload = json.loads(trace_files[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["command_name"], "judge-trial")
            self.assertEqual(payload["arguments"], ["study_001", "group1", "trial_0001"])
            stdout_files = list(ctrl.paths.trial_opencode_trace_root("trial_0001").glob("*.stdout.txt"))
            stderr_files = list(ctrl.paths.trial_opencode_trace_root("trial_0001").glob("*.stderr.txt"))
            self.assertEqual(len(stdout_files), 1)
            self.assertEqual(len(stderr_files), 1)
            self.assertEqual(stdout_files[0].read_text(encoding="utf-8"), '{"decision":"REGENERATE_DATA"}')
            self.assertEqual(stderr_files[0].read_text(encoding="utf-8"), "")
            self.assertEqual(len(terminal_lines), 1)
            self.assertIn("trace_file:", terminal_lines[0])
            self.assertIn("raw_stdout_file:", terminal_lines[0])
            self.assertIn("judge markdown body", terminal_lines[0])
            self.assertIn("training judge skill body", terminal_lines[0])

    def test_record_opencode_trace_handles_none_stdout_and_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            train_root.mkdir(parents=True, exist_ok=True)
            generator_workspace.mkdir(parents=True, exist_ok=True)
            terminal_lines: list[str] = []

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group1",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                    judge_provider="opencode",
                ),
                dependencies=controller.ControllerDependencies(
                    console_writer=terminal_lines.append,
                ),
            )

            trace = controller.opencode_runtime.OpenCodeTraceRecord(
                created_at="2026-04-05T10:00:00+00:00",
                command_name="plan-dataset",
                arguments=("study_001", "group1", "trial_0001"),
                project_root=str(train_root),
                attach_url="http://127.0.0.1:4096",
                model="ollama/gemma4:26b",
                command=("opencode", "run", "--command", "plan-dataset"),
                command_markdown_path=str(train_root / ".opencode" / "commands" / "plan-dataset.md"),
                command_markdown_text="plan markdown body",
                command_markdown_truncated=False,
                command_markdown_error=None,
                skill_markdown_path=str(train_root / ".opencode" / "skills" / "dataset-planner" / "SKILL.md"),
                skill_markdown_text="dataset planner skill body",
                skill_markdown_truncated=False,
                skill_markdown_error=None,
                attached_files=(),
                stdout=None,  # type: ignore[arg-type]
                stderr=None,  # type: ignore[arg-type]
                returncode=0,
                success=False,
                error_message="opencode_empty_stdout",
            )

            ctrl._record_opencode_trace(trace)

            stdout_files = list(ctrl.paths.trial_opencode_trace_root("trial_0001").glob("*.stdout.txt"))
            stderr_files = list(ctrl.paths.trial_opencode_trace_root("trial_0001").glob("*.stderr.txt"))
            self.assertEqual(len(stdout_files), 1)
            self.assertEqual(len(stderr_files), 1)
            self.assertEqual(stdout_files[0].read_text(encoding="utf-8"), "")
            self.assertEqual(stderr_files[0].read_text(encoding="utf-8"), "")
            self.assertEqual(len(terminal_lines), 1)
            self.assertIn("raw_stdout_file:", terminal_lines[0])
            self.assertIn("raw_stderr_file:", terminal_lines[0])
            self.assertIn("--- raw stdout ---", terminal_lines[0])
            self.assertIn("(empty)", terminal_lines[0])

    def test_default_opencode_runtime_uses_train_root_as_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            train_root.mkdir(parents=True, exist_ok=True)
            generator_workspace.mkdir(parents=True, exist_ok=True)

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group1",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                    judge_provider="opencode",
                )
            )

            runtime = ctrl._opencode_runtime()

            self.assertEqual(runtime.config.project_root, train_root)

    def test_default_generator_executable_uses_windows_name_on_nt(self) -> None:
        from unittest.mock import patch

        with patch("auto_train.controller.os.name", "nt"):
            self.assertEqual(controller.default_generator_executable(), "sinan-generator.exe")

    def test_evaluate_stage_uses_test_outputs_when_request_dirs_are_not_supplied(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            generator_workspace.mkdir(parents=True, exist_ok=True)

            test_report_dir = train_root / "reports" / "group1" / "test_trial_0001"
            gold_dir = test_report_dir / "_gold"
            prediction_dir = train_root / "reports" / "group1" / "predict_trial_0001"
            val_dir = train_root / "reports" / "group1" / "val_trial_0001"
            gold_dir.mkdir(parents=True, exist_ok=True)
            prediction_dir.mkdir(parents=True, exist_ok=True)
            val_dir.mkdir(parents=True, exist_ok=True)
            (gold_dir / "labels.jsonl").write_text("{}\n", encoding="utf-8")
            (prediction_dir / "labels.jsonl").write_text("{}\n", encoding="utf-8")

            captured_requests: list[controller.runners.evaluate.EvaluateRunnerRequest] = []

            def fake_evaluate(
                request: controller.runners.evaluate.EvaluateRunnerRequest,
            ) -> controller.runners.evaluate.EvaluateRunnerResult:
                captured_requests.append(request)
                return controller.runners.evaluate.EvaluateRunnerResult(
                    record=contracts.EvaluateRecord(
                        available=True,
                        task="group1",
                        metrics={"full_sequence_hit_rate": 0.85},
                        failure_count=1,
                        report_dir=str(request.report_dir),
                    ),
                    command="uv run sinan evaluate",
                )

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group1",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                ),
                dependencies=controller.ControllerDependencies(
                    evaluate_runner=fake_evaluate,
                ),
            )

            storage.write_study_record(
                ctrl.paths.study_file,
                contracts.StudyRecord(
                    study_name="study_001",
                    task="group1",
                    status="running",
                    mode="full_auto",
                    train_root=str(train_root),
                    generator_workspace=str(generator_workspace),
                    judge=contracts.JudgeConfig(provider="rules", model="policy-v1"),
                    budget=contracts.StudyBudget(max_trials=20, max_hours=24.0, max_no_improve_trials=4),
                    current_trial_id="trial_0001",
                    best_trial_id=None,
                ),
            )
            storage.write_trial_input_record(
                ctrl.paths.input_file("trial_0001"),
                contracts.TrialInputRecord(
                    trial_id="trial_0001",
                    task="group1",
                    dataset_version="firstpass",
                    train_name="trial_0001",
                    train_mode="fresh",
                    base_run=None,
                    params={"epochs": 120, "batch": 16, "imgsz": 640, "device": "0"},
                ),
            )
            storage.write_test_record(
                ctrl.paths.test_file("trial_0001"),
                contracts.TestRecord(
                    task="group1",
                    dataset_version="firstpass",
                    train_name="trial_0001",
                    metrics={"full_sequence_hit_rate": 0.82},
                    predict_output_dir=str(prediction_dir),
                    val_output_dir=str(val_dir),
                    report_dir=str(test_report_dir),
                ),
            )

            execution = ctrl.run_stage("EVALUATE")

            self.assertEqual(execution.next_stage, "SUMMARIZE")
            self.assertEqual(len(captured_requests), 1)
            request = captured_requests[0]
            self.assertEqual(request.gold_dir, gold_dir)
            self.assertEqual(request.prediction_dir, prediction_dir)
            self.assertEqual(request.report_dir, val_dir)
            evaluate_record = storage.read_evaluate_record(ctrl.paths.evaluate_file("trial_0001"))
            self.assertTrue(evaluate_record.available)

    def test_update_leaderboard_ignores_malformed_business_eval_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            train_root.mkdir(parents=True, exist_ok=True)
            generator_workspace.mkdir(parents=True, exist_ok=True)

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group2",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                )
            )

            storage.write_trial_input_record(
                ctrl.paths.input_file("trial_0001"),
                contracts.TrialInputRecord(
                    trial_id="trial_0001",
                    task="group2",
                    dataset_version="firstpass",
                    train_name="trial_0001",
                    train_mode="fresh",
                    base_run=None,
                    params={"epochs": 100, "batch": 16, "imgsz": 192, "device": "0"},
                ),
            )
            storage.write_trial_input_record(
                ctrl.paths.input_file("trial_0002"),
                contracts.TrialInputRecord(
                    trial_id="trial_0002",
                    task="group2",
                    dataset_version="firstpass",
                    train_name="trial_0002",
                    train_mode="fresh",
                    base_run=None,
                    params={"epochs": 100, "batch": 16, "imgsz": 192, "device": "0"},
                ),
            )
            storage.write_result_summary_record(
                ctrl.paths.result_summary_file("trial_0001"),
                _group2_trial_summary("trial_0001", score=0.98, trend="plateau"),
            )
            storage.write_decision_record(
                ctrl.paths.decision_file("trial_0001"),
                contracts.DecisionRecord(
                    trial_id="trial_0001",
                    decision="PROMOTE_BRANCH",
                    confidence=0.95,
                    reason="group2_targets_met",
                    next_action={"dataset_action": "freeze", "train_action": "promote"},
                    evidence=["targets_met"],
                    agent=contracts.AgentRef(provider="rules", name="policy-judge", model="policy-v1"),
                ),
            )
            ctrl.paths.business_eval_file("trial_0001").write_text("{\n", encoding="utf-8")
            storage.write_leaderboard_record(
                ctrl.paths.leaderboard_file,
                contracts.LeaderboardRecord(
                    study_name="study_001",
                    task="group2",
                    primary_metric="point_hit_rate",
                    entries=[
                        contracts.LeaderboardEntry(
                            trial_id="trial_0001",
                            dataset_version="firstpass",
                            train_name="trial_0001",
                            primary_score=0.98,
                            metrics={"point_hit_rate": 0.98, "ranking_score": 0.98},
                            decision="PROMOTE_BRANCH",
                        )
                    ],
                ),
            )

            updated = ctrl._update_leaderboard(
                _group2_trial_summary("trial_0002", score=1.0, trend="plateau"),
                contracts.DecisionRecord(
                    trial_id="trial_0002",
                    decision="PROMOTE_BRANCH",
                    confidence=0.95,
                    reason="group2_targets_met",
                    next_action={"dataset_action": "freeze", "train_action": "promote"},
                    evidence=["targets_met"],
                    agent=contracts.AgentRef(provider="rules", name="policy-judge", model="policy-v1"),
                ),
                None,
            )

            self.assertEqual([entry.trial_id for entry in updated.entries], ["trial_0002", "trial_0001"])

    def test_stage_test_falls_back_to_last_weights_when_best_weights_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            train_root.mkdir(parents=True, exist_ok=True)
            generator_workspace.mkdir(parents=True, exist_ok=True)
            _write_dataset_config(train_root, "group2", "firstpass")
            predict_source = train_root / "datasets" / "group2" / "firstpass" / "splits" / "val.jsonl"
            predict_source.parent.mkdir(parents=True, exist_ok=True)
            predict_source.write_text("{}\n", encoding="utf-8")

            captured_requests: list[controller.runners.test.TestRunnerRequest] = []

            def fake_test_runner(
                request: controller.runners.test.TestRunnerRequest,
            ) -> controller.runners.test.TestRunnerResult:
                captured_requests.append(request)
                return controller.runners.test.TestRunnerResult(
                    record=contracts.TestRecord(
                        task="group2",
                        dataset_version="firstpass",
                        train_name="trial_0006",
                        metrics={"point_hit_rate": 1.0, "mean_iou": 0.9},
                        predict_output_dir=str(train_root / "reports" / "group2" / "predict_trial_0006"),
                        val_output_dir=str(train_root / "reports" / "group2" / "val_trial_0006"),
                        report_dir=str(train_root / "reports" / "group2" / "test_trial_0006"),
                    ),
                    predict_command="uv run sinan predict group2",
                    val_command="uv run sinan test group2",
                )

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group2",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                ),
                dependencies=controller.ControllerDependencies(test_runner=fake_test_runner),
            )

            best_path = train_root / "runs" / "group2" / "trial_0006" / "weights" / "best.pt"
            last_path = train_root / "runs" / "group2" / "trial_0006" / "weights" / "last.pt"
            last_path.parent.mkdir(parents=True, exist_ok=True)
            last_path.write_bytes(b"checkpoint")

            storage.write_trial_input_record(
                ctrl.paths.input_file("trial_0006"),
                contracts.TrialInputRecord(
                    trial_id="trial_0006",
                    task="group2",
                    dataset_version="firstpass",
                    train_name="trial_0006",
                    train_mode="fresh",
                    base_run=None,
                    params={"epochs": 100, "batch": 16, "imgsz": 192, "device": "0"},
                ),
            )
            storage.write_train_record(
                ctrl.paths.train_file("trial_0006"),
                contracts.TrainRecord(
                    task="group2",
                    train_name="trial_0006",
                    run_dir=str(best_path.parent.parent),
                    params={"epochs": 100, "batch": 16, "imgsz": 192, "device": "0"},
                    best_weights=str(best_path),
                    last_weights=str(last_path),
                ),
            )
            storage.write_study_record(
                ctrl.paths.study_file,
                contracts.StudyRecord(
                    study_name="study_001",
                    task="group2",
                    status="running",
                    mode="full_auto",
                    train_root=str(train_root),
                    generator_workspace=str(generator_workspace),
                    judge=contracts.JudgeConfig(provider="rules", model="policy-v1"),
                    budget=contracts.StudyBudget(max_trials=20, max_hours=24.0, max_no_improve_trials=4),
                    current_trial_id="trial_0006",
                    best_trial_id=None,
                ),
            )

            execution = ctrl.run_stage("TEST")

            self.assertEqual(execution.next_stage, "EVALUATE")
            self.assertEqual(len(captured_requests), 1)
            self.assertEqual(captured_requests[0].model_path, last_path)

    def test_selected_group2_trial_promotes_last_weights_to_best_when_best_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            train_root.mkdir(parents=True, exist_ok=True)
            generator_workspace.mkdir(parents=True, exist_ok=True)

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group2",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                ),
            )

            best_path = train_root / "runs" / "group2" / "trial_0007" / "weights" / "best.pt"
            last_path = train_root / "runs" / "group2" / "trial_0007" / "weights" / "last.pt"
            last_path.parent.mkdir(parents=True, exist_ok=True)
            last_path.write_bytes(b"checkpoint-last")

            storage.write_train_record(
                ctrl.paths.train_file("trial_0007"),
                contracts.TrainRecord(
                    task="group2",
                    train_name="trial_0007",
                    run_dir=str(best_path.parent.parent),
                    params={"epochs": 100, "batch": 16, "imgsz": 192, "device": "0"},
                    best_weights=str(best_path),
                    last_weights=str(last_path),
                ),
            )

            leaderboard = contracts.LeaderboardRecord(
                study_name="study_001",
                task="group2",
                primary_metric="point_hit_rate",
                entries=[
                    contracts.LeaderboardEntry(
                        trial_id="trial_0007",
                        dataset_version="firstpass",
                        train_name="trial_0007",
                        primary_score=0.98,
                        metrics={"ranking_score": 2.45},
                    ),
                    contracts.LeaderboardEntry(
                        trial_id="trial_0006",
                        dataset_version="firstpass",
                        train_name="trial_0006",
                        primary_score=0.99,
                        metrics={"ranking_score": 2.12},
                    ),
                ],
            )

            ctrl._promote_current_trial_last_weights_if_selected(trial_id="trial_0007", leaderboard=leaderboard)

            self.assertTrue(best_path.exists())
            self.assertEqual(best_path.read_bytes(), b"checkpoint-last")

    def test_resume_stage_falls_back_to_build_dataset_when_dataset_config_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            train_root.mkdir(parents=True, exist_ok=True)
            generator_workspace.mkdir(parents=True, exist_ok=True)

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group1",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                )
            )

            storage.write_study_record(
                ctrl.paths.study_file,
                contracts.StudyRecord(
                    study_name="study_001",
                    task="group1",
                    status="running",
                    mode="full_auto",
                    train_root=str(train_root),
                    generator_workspace=str(generator_workspace),
                    judge=contracts.JudgeConfig(provider="rules", model="policy-v1"),
                    budget=contracts.StudyBudget(max_trials=20, max_hours=24.0, max_no_improve_trials=4),
                    current_trial_id="trial_0001",
                    best_trial_id=None,
                ),
            )
            storage.write_trial_input_record(
                ctrl.paths.input_file("trial_0001"),
                contracts.TrialInputRecord(
                    trial_id="trial_0001",
                    task="group1",
                    dataset_version="firstpass",
                    train_name="trial_0001",
                    train_mode="fresh",
                    base_run=None,
                    params={"epochs": 120, "batch": 16, "imgsz": 640, "device": "0"},
                ),
            )
            storage.write_dataset_record(
                ctrl.paths.dataset_file("trial_0001"),
                contracts.DatasetRecord(
                    task="group1",
                    dataset_version="firstpass",
                    dataset_root=str(train_root / "datasets" / "group1" / "firstpass"),
                    label_source="existing_dataset",
                ),
            )

            study = storage.read_study_record(ctrl.paths.study_file)
            self.assertEqual(ctrl._current_stage(study, "trial_0001"), "BUILD_DATASET")

    def test_build_dataset_rebuilds_when_dataset_dir_exists_but_dataset_config_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            dataset_dir = train_root / "datasets" / "group1" / "firstpass"
            dataset_dir.mkdir(parents=True, exist_ok=True)
            generator_workspace.mkdir(parents=True, exist_ok=True)

            captured_requests: list[controller.runners.dataset.DatasetRunnerRequest] = []

            def fake_dataset_runner(
                request: controller.runners.dataset.DatasetRunnerRequest,
            ) -> controller.runners.dataset.DatasetRunnerResult:
                captured_requests.append(request)
                return controller.runners.dataset.DatasetRunnerResult(
                    record=contracts.DatasetRecord(
                        task="group1",
                        dataset_version="firstpass",
                        dataset_root=str(request.dataset_dir),
                        label_source=str(request.generator_workspace),
                    ),
                    command="sinan-generator make-dataset",
                )

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group1",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                ),
                dependencies=controller.ControllerDependencies(dataset_runner=fake_dataset_runner),
            )

            storage.write_study_record(
                ctrl.paths.study_file,
                contracts.StudyRecord(
                    study_name="study_001",
                    task="group1",
                    status="running",
                    mode="full_auto",
                    train_root=str(train_root),
                    generator_workspace=str(generator_workspace),
                    judge=contracts.JudgeConfig(provider="rules", model="policy-v1"),
                    budget=contracts.StudyBudget(max_trials=20, max_hours=24.0, max_no_improve_trials=4),
                    current_trial_id="trial_0001",
                    best_trial_id=None,
                ),
            )
            storage.write_trial_input_record(
                ctrl.paths.input_file("trial_0001"),
                contracts.TrialInputRecord(
                    trial_id="trial_0001",
                    task="group1",
                    dataset_version="firstpass",
                    train_name="trial_0001",
                    train_mode="fresh",
                    base_run=None,
                    params={"epochs": 120, "batch": 16, "imgsz": 640, "device": "0"},
                ),
            )

            execution = ctrl.run_stage("BUILD_DATASET")

            self.assertEqual(execution.next_stage, "TRAIN")
            self.assertEqual(len(captured_requests), 1)
            self.assertTrue(captured_requests[0].force)

    def test_build_dataset_forwards_generator_executable_from_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            generator_workspace.mkdir(parents=True, exist_ok=True)

            captured_requests: list[controller.runners.dataset.DatasetRunnerRequest] = []

            def fake_dataset_runner(
                request: controller.runners.dataset.DatasetRunnerRequest,
            ) -> controller.runners.dataset.DatasetRunnerResult:
                captured_requests.append(request)
                return controller.runners.dataset.DatasetRunnerResult(
                    record=contracts.DatasetRecord(
                        task="group1",
                        dataset_version="firstpass",
                        dataset_root=str(request.dataset_dir),
                        label_source=str(request.generator_workspace),
                    ),
                    command="sinan-generator make-dataset",
                )

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group1",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    generator_executable=r"C:\tools\sinan-generator.exe",
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                ),
                dependencies=controller.ControllerDependencies(dataset_runner=fake_dataset_runner),
            )

            storage.write_study_record(
                ctrl.paths.study_file,
                contracts.StudyRecord(
                    study_name="study_001",
                    task="group1",
                    status="running",
                    mode="full_auto",
                    train_root=str(train_root),
                    generator_workspace=str(generator_workspace),
                    judge=contracts.JudgeConfig(provider="rules", model="policy-v1"),
                    budget=contracts.StudyBudget(max_trials=20, max_hours=24.0, max_no_improve_trials=4),
                    current_trial_id="trial_0001",
                    best_trial_id=None,
                ),
            )
            storage.write_trial_input_record(
                ctrl.paths.input_file("trial_0001"),
                contracts.TrialInputRecord(
                    trial_id="trial_0001",
                    task="group1",
                    dataset_version="firstpass",
                    train_name="trial_0001",
                    train_mode="fresh",
                    base_run=None,
                    params={"epochs": 120, "batch": 16, "imgsz": 640, "device": "0"},
                ),
            )

            ctrl.run_stage("BUILD_DATASET")

            self.assertEqual(len(captured_requests), 1)
            self.assertEqual(captured_requests[0].generator_executable, r"C:\tools\sinan-generator.exe")

    def test_run_uses_opencode_judge_output_when_provider_is_opencode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            dataset_dir = train_root / "datasets" / "group1" / "firstpass"
            for path in (generator_workspace, dataset_dir):
                path.mkdir(parents=True, exist_ok=True)
            _write_dataset_config(train_root, "group1", "firstpass")

            def fake_train(_: object) -> controller.runners.train.TrainRunnerResult:
                return _train_result("group1", train_root, "trial_0001")

            def fake_test(_: object) -> controller.runners.test.TestRunnerResult:
                return controller.runners.test.TestRunnerResult(
                    record=contracts.TestRecord(
                        task="group1",
                        dataset_version="firstpass",
                        train_name="trial_0001",
                        metrics={"precision": 0.91, "recall": 0.89, "map50_95": 0.84},
                        predict_output_dir=str(train_root / "reports" / "group1" / "predict_trial_0001"),
                        val_output_dir=str(train_root / "reports" / "group1" / "val_trial_0001"),
                        report_dir=str(train_root / "reports" / "group1" / "test_trial_0001"),
                    ),
                    predict_command="uv run sinan predict",
                    val_command="uv run sinan test",
                )

            class FakeRuntime:
                def result_read(
                    self,
                    *,
                    study_name: str,
                    task: str,
                    trial_id: str,
                    dataset_version: str,
                    train_name: str,
                    primary_metric: str,
                    files: list[Path],
                ) -> controller.opencode_runtime.OpenCodeInvocationResult:
                    record = contracts.ResultSummaryRecord(
                        study_name=study_name,
                        task=task,
                        trial_id=trial_id,
                        dataset_version=dataset_version,
                        train_name=train_name,
                        primary_metric=primary_metric,
                        primary_score=0.84,
                        test_metrics={"precision": 0.91, "recall": 0.89, "map50_95": 0.84},
                        evaluation_available=False,
                        evaluation_metrics={},
                        failure_count=None,
                        trend="baseline",
                        delta_vs_previous=None,
                        delta_vs_best=None,
                        weak_classes=[],
                        failure_patterns=[],
                        recent_trials=[],
                        best_trial=None,
                        evidence=["opencode_summary"],
                    )
                    return controller.opencode_runtime.OpenCodeInvocationResult(
                        stdout=json.dumps(record.to_dict()),
                        stderr="",
                        command=("opencode", "run"),
                        returncode=0,
                    )

                def judge_trial(
                    self,
                    *,
                    study_name: str,
                    task: str,
                    trial_id: str,
                    files: list[Path],
                ) -> controller.opencode_runtime.OpenCodeInvocationResult:
                    self.study_name = study_name
                    self.task = task
                    self.trial_id = trial_id
                    self.files = files
                    return controller.opencode_runtime.OpenCodeInvocationResult(
                        stdout=(
                            '{"decision":"PROMOTE_BRANCH","reason":"opencode_accept",'
                            '"confidence":0.92,"next_action":{"dataset_action":"freeze","train_action":"promote"},'
                            '"evidence":["llm judged study as ready"]}'
                        ),
                        stderr="",
                        command=("opencode", "run"),
                        returncode=0,
                    )

                def study_status(
                    self,
                    *,
                    study_name: str,
                    task: str,
                    files: list[Path],
                ) -> controller.opencode_runtime.OpenCodeInvocationResult:
                    payload = contracts.StudyStatusRecord(
                        study_name=study_name,
                        task=task,
                        status="running",
                        current_trial_id="trial_0001",
                        best_trial_id="trial_0001",
                        latest_decision="PROMOTE_BRANCH",
                        best_primary_score=0.84,
                        budget_pressure="low",
                        summary_cn="这是 OpenCode 生成的中文 study 摘要。",
                        next_actions_cn=["冻结当前最佳分支并进入人工验收。"],
                        evidence=["opencode_study_status"],
                    )
                    return controller.opencode_runtime.OpenCodeInvocationResult(
                        stdout=json.dumps(payload.to_dict()),
                        stderr="",
                        command=("opencode", "run"),
                        returncode=0,
                    )

            runtime = FakeRuntime()
            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group1",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                    judge_provider="opencode",
                    judge_model="gemma4",
                ),
                dependencies=controller.ControllerDependencies(
                    train_runner=fake_train,
                    test_runner=fake_test,
                    opencode_runtime=runtime,
                ),
            )

            result = ctrl.run(max_steps=8)

            self.assertEqual(result.final_stage, "STOP")
            decision = storage.read_decision_record(ctrl.paths.decision_file("trial_0001"))
            self.assertEqual(decision.decision, "PROMOTE_BRANCH")
            self.assertEqual(decision.reason, "opencode_accept")
            self.assertEqual(decision.agent.provider, "opencode")
            self.assertEqual(decision.agent.model, "gemma4")
            summary_record = storage.read_result_summary_record(ctrl.paths.result_summary_file("trial_0001"))
            self.assertIn("opencode_summary", summary_record.evidence)
            self.assertEqual(runtime.study_name, "study_001")
            self.assertEqual(runtime.task, "group1")
            self.assertEqual(runtime.trial_id, "trial_0001")
            self.assertIn(ctrl.paths.study_file, runtime.files)
            self.assertIn(ctrl.paths.result_summary_file("trial_0001"), runtime.files)
            self.assertIn("OpenCode 生成的中文 study 摘要", ctrl.paths.summary_file.read_text(encoding="utf-8"))

    def test_run_falls_back_when_opencode_runtime_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            dataset_dir = train_root / "datasets" / "group1" / "firstpass"
            for path in (generator_workspace, dataset_dir):
                path.mkdir(parents=True, exist_ok=True)
            _write_dataset_config(train_root, "group1", "firstpass")

            def fake_train(_: object) -> controller.runners.train.TrainRunnerResult:
                return _train_result("group1", train_root, "trial_0001")

            def fake_test(_: object) -> controller.runners.test.TestRunnerResult:
                return controller.runners.test.TestRunnerResult(
                    record=contracts.TestRecord(
                        task="group1",
                        dataset_version="firstpass",
                        train_name="trial_0001",
                        metrics={"precision": 0.84, "recall": 0.79, "map50_95": 0.76},
                        predict_output_dir=str(train_root / "reports" / "group1" / "predict_trial_0001"),
                        val_output_dir=str(train_root / "reports" / "group1" / "val_trial_0001"),
                        report_dir=str(train_root / "reports" / "group1" / "test_trial_0001"),
                    ),
                    predict_command="uv run sinan predict",
                    val_command="uv run sinan test",
                )

            class FailingRuntime:
                def result_read(
                    self,
                    *,
                    study_name: str,
                    task: str,
                    trial_id: str,
                    dataset_version: str,
                    train_name: str,
                    primary_metric: str,
                    files: list[Path],
                ) -> controller.opencode_runtime.OpenCodeInvocationResult:
                    record = contracts.ResultSummaryRecord(
                        study_name=study_name,
                        task=task,
                        trial_id=trial_id,
                        dataset_version=dataset_version,
                        train_name=train_name,
                        primary_metric=primary_metric,
                        primary_score=0.76,
                        test_metrics={"precision": 0.84, "recall": 0.79, "map50_95": 0.76},
                        evaluation_available=False,
                        evaluation_metrics={},
                        failure_count=None,
                        trend="baseline",
                        delta_vs_previous=None,
                        delta_vs_best=None,
                        weak_classes=[],
                        failure_patterns=["strict_localization"],
                        recent_trials=[],
                        best_trial=None,
                        evidence=["opencode_summary"],
                    )
                    return controller.opencode_runtime.OpenCodeInvocationResult(
                        stdout=json.dumps(record.to_dict()),
                        stderr="",
                        command=("opencode", "run"),
                        returncode=0,
                    )

                def judge_trial(
                    self,
                    *,
                    study_name: str,
                    task: str,
                    trial_id: str,
                    files: list[Path],
                ) -> controller.opencode_runtime.OpenCodeInvocationResult:
                    raise controller.opencode_runtime.OpenCodeRuntimeError(
                        command_name="judge-trial",
                        message="opencode_command_failed: unavailable",
                        command=["opencode", "run"],
                        returncode=1,
                    )

                def study_status(
                    self,
                    *,
                    study_name: str,
                    task: str,
                    files: list[Path],
                ) -> controller.opencode_runtime.OpenCodeInvocationResult:
                    payload = contracts.StudyStatusRecord(
                        study_name=study_name,
                        task=task,
                        status="running",
                        current_trial_id="trial_0002",
                        best_trial_id="trial_0001",
                        latest_decision="RETUNE",
                        best_primary_score=0.76,
                        budget_pressure="low",
                        summary_cn="OpenCode study-status 可用。",
                        next_actions_cn=["继续下一轮调参。"],
                        evidence=["opencode_study_status"],
                    )
                    return controller.opencode_runtime.OpenCodeInvocationResult(
                        stdout=json.dumps(payload.to_dict()),
                        stderr="",
                        command=("opencode", "run"),
                        returncode=0,
                    )

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group1",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                    judge_provider="opencode",
                    judge_model="gemma4",
                ),
                dependencies=controller.ControllerDependencies(
                    train_runner=fake_train,
                    test_runner=fake_test,
                    opencode_runtime=FailingRuntime(),
                ),
            )

            result = ctrl.run(max_steps=8)

            self.assertEqual(result.final_stage, "PLAN")
            decision = storage.read_decision_record(ctrl.paths.decision_file("trial_0001"))
            self.assertEqual(decision.reason, "fallback_runtime_error")
            self.assertEqual(decision.agent.provider, "opencode")
            self.assertTrue(any("opencode_command_failed" in item for item in decision.evidence))

    def test_run_falls_back_to_local_summary_when_result_read_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            dataset_dir = train_root / "datasets" / "group1" / "firstpass"
            for path in (generator_workspace, dataset_dir):
                path.mkdir(parents=True, exist_ok=True)
            _write_dataset_config(train_root, "group1", "firstpass")

            def fake_train(_: object) -> controller.runners.train.TrainRunnerResult:
                return _train_result("group1", train_root, "trial_0001")

            def fake_test(_: object) -> controller.runners.test.TestRunnerResult:
                return controller.runners.test.TestRunnerResult(
                    record=contracts.TestRecord(
                        task="group1",
                        dataset_version="firstpass",
                        train_name="trial_0001",
                        metrics={"precision": 0.9, "recall": 0.88, "map50_95": 0.81},
                        predict_output_dir=str(train_root / "reports" / "group1" / "predict_trial_0001"),
                        val_output_dir=str(train_root / "reports" / "group1" / "val_trial_0001"),
                        report_dir=str(train_root / "reports" / "group1" / "test_trial_0001"),
                    ),
                    predict_command="uv run sinan predict group1",
                    val_command="uv run sinan test group1",
                )

            class RuntimeWithBrokenResultRead:
                def result_read(
                    self,
                    *,
                    study_name: str,
                    task: str,
                    trial_id: str,
                    dataset_version: str,
                    train_name: str,
                    primary_metric: str,
                    files: list[Path],
                ) -> controller.opencode_runtime.OpenCodeInvocationResult:
                    raise controller.opencode_runtime.OpenCodeRuntimeError(
                        command_name="result-read",
                        message="opencode_command_failed: bad summary",
                        command=["opencode", "run"],
                        returncode=1,
                    )

                def judge_trial(
                    self,
                    *,
                    study_name: str,
                    task: str,
                    trial_id: str,
                    files: list[Path],
                ) -> controller.opencode_runtime.OpenCodeInvocationResult:
                    return controller.opencode_runtime.OpenCodeInvocationResult(
                        stdout=(
                            '{"decision":"RETUNE","reason":"continue","confidence":0.77,'
                            '"next_action":{"dataset_action":"reuse","train_action":"from_run","base_run":"trial_0001"},'
                            '"evidence":["fallback summary still usable"]}'
                        ),
                        stderr="",
                        command=("opencode", "run"),
                        returncode=0,
                    )

                def study_status(
                    self,
                    *,
                    study_name: str,
                    task: str,
                    files: list[Path],
                ) -> controller.opencode_runtime.OpenCodeInvocationResult:
                    payload = contracts.StudyStatusRecord(
                        study_name=study_name,
                        task=task,
                        status="running",
                        current_trial_id="trial_0002",
                        best_trial_id="trial_0001",
                        latest_decision="RETUNE",
                        best_primary_score=0.89,
                        budget_pressure="low",
                        summary_cn="本轮继续调参。",
                        next_actions_cn=["继续下一轮调参。"],
                        evidence=["opencode_study_status"],
                    )
                    return controller.opencode_runtime.OpenCodeInvocationResult(
                        stdout=json.dumps(payload.to_dict()),
                        stderr="",
                        command=("opencode", "run"),
                        returncode=0,
                    )

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group1",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                    judge_provider="opencode",
                    judge_model="gemma4",
                ),
                dependencies=controller.ControllerDependencies(
                    train_runner=fake_train,
                    test_runner=fake_test,
                    opencode_runtime=RuntimeWithBrokenResultRead(),
                ),
            )

            result = ctrl.run(max_steps=8)

            self.assertEqual(result.final_stage, "PLAN")
            summary_record = storage.read_result_summary_record(ctrl.paths.result_summary_file("trial_0001"))
            self.assertEqual(summary_record.primary_score, 0.81)
            self.assertTrue(any("result_read_fallback=runtime_error" in item for item in summary_record.evidence))

    def test_run_writes_opencode_dataset_plan_when_regeneration_is_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            dataset_dir = train_root / "datasets" / "group1" / "firstpass"
            for path in (generator_workspace, dataset_dir):
                path.mkdir(parents=True, exist_ok=True)
            _write_dataset_config(train_root, "group1", "firstpass")

            def fake_train(_: object) -> controller.runners.train.TrainRunnerResult:
                return _train_result("group1", train_root, "trial_0001")

            def fake_test(_: object) -> controller.runners.test.TestRunnerResult:
                return controller.runners.test.TestRunnerResult(
                    record=contracts.TestRecord(
                        task="group1",
                        dataset_version="firstpass",
                        train_name="trial_0001",
                        metrics={"precision": 0.88, "recall": 0.83, "map50_95": 0.79},
                        predict_output_dir=str(train_root / "reports" / "group1" / "predict_trial_0001"),
                        val_output_dir=str(train_root / "reports" / "group1" / "val_trial_0001"),
                        report_dir=str(train_root / "reports" / "group1" / "test_trial_0001"),
                    ),
                    predict_command="uv run sinan predict",
                    val_command="uv run sinan test",
                )

            class RuntimeWithDatasetPlan:
                def result_read(
                    self,
                    *,
                    study_name: str,
                    task: str,
                    trial_id: str,
                    dataset_version: str,
                    train_name: str,
                    primary_metric: str,
                    files: list[Path],
                ) -> controller.opencode_runtime.OpenCodeInvocationResult:
                    record = contracts.ResultSummaryRecord(
                        study_name=study_name,
                        task=task,
                        trial_id=trial_id,
                        dataset_version=dataset_version,
                        train_name=train_name,
                        primary_metric=primary_metric,
                        primary_score=0.79,
                        test_metrics={"precision": 0.88, "recall": 0.83, "map50_95": 0.79},
                        evaluation_available=False,
                        evaluation_metrics={},
                        failure_count=None,
                        trend="plateau",
                        delta_vs_previous=None,
                        delta_vs_best=None,
                        weak_classes=["icon_camera", "icon_leaf"],
                        failure_patterns=["sequence_consistency"],
                        recent_trials=[],
                        best_trial=None,
                        evidence=["opencode_summary"],
                    )
                    return controller.opencode_runtime.OpenCodeInvocationResult(
                        stdout=json.dumps(record.to_dict()),
                        stderr="",
                        command=("opencode", "run"),
                        returncode=0,
                    )

                def judge_trial(
                    self,
                    *,
                    study_name: str,
                    task: str,
                    trial_id: str,
                    files: list[Path],
                ) -> controller.opencode_runtime.OpenCodeInvocationResult:
                    return controller.opencode_runtime.OpenCodeInvocationResult(
                        stdout=(
                            '{"decision":"REGENERATE_DATA","reason":"weak_classes","confidence":0.81,'
                            '"next_action":{"dataset_action":"new_version","train_action":"from_run","base_run":"trial_0001"},'
                            '"evidence":["need more hard samples"]}'
                        ),
                        stderr="",
                        command=("opencode", "run"),
                        returncode=0,
                    )

                def plan_dataset(
                    self,
                    *,
                    study_name: str,
                    task: str,
                    trial_id: str,
                    files: list[Path],
                ) -> controller.opencode_runtime.OpenCodeInvocationResult:
                    payload = contracts.DatasetPlanRecord(
                        study_name=study_name,
                        task=task,
                        trial_id=trial_id,
                        dataset_action="new_version",
                        generator_preset="hard",
                        generator_overrides={
                            "project": {"sample_count": 320},
                            "sampling": {
                                "target_count_min": 3,
                                "target_count_max": 5,
                                "distractor_count_min": 5,
                                "distractor_count_max": 8,
                            },
                            "effects": {
                                "common": {
                                    "scene_veil_strength": 1.45,
                                    "background_blur_radius_min": 1,
                                    "background_blur_radius_max": 2,
                                },
                                "click": {
                                    "icon_shadow_alpha_min": 0.28,
                                    "icon_shadow_alpha_max": 0.36,
                                    "icon_shadow_offset_x_min": 2,
                                    "icon_shadow_offset_x_max": 3,
                                    "icon_shadow_offset_y_min": 3,
                                    "icon_shadow_offset_y_max": 4,
                                    "icon_edge_blur_radius_min": 1,
                                    "icon_edge_blur_radius_max": 2,
                                },
                            },
                        },
                        boost_classes=["icon_camera", "icon_leaf"],
                        focus_failure_patterns=["sequence_consistency"],
                        rationale_cn="增加弱类和顺序错误样本。",
                        evidence=["opencode_dataset_plan"],
                    )
                    return controller.opencode_runtime.OpenCodeInvocationResult(
                        stdout=json.dumps(payload.to_dict()),
                        stderr="",
                        command=("opencode", "run"),
                        returncode=0,
                    )

                def study_status(
                    self,
                    *,
                    study_name: str,
                    task: str,
                    files: list[Path],
                ) -> controller.opencode_runtime.OpenCodeInvocationResult:
                    payload = contracts.StudyStatusRecord(
                        study_name=study_name,
                        task=task,
                        status="running",
                        current_trial_id="trial_0002",
                        best_trial_id="trial_0001",
                        latest_decision="REGENERATE_DATA",
                        best_primary_score=0.79,
                        budget_pressure="low",
                        summary_cn="需要先补数据再继续。",
                        next_actions_cn=["生成新数据版本。"],
                        evidence=["opencode_study_status"],
                    )
                    return controller.opencode_runtime.OpenCodeInvocationResult(
                        stdout=json.dumps(payload.to_dict()),
                        stderr="",
                        command=("opencode", "run"),
                        returncode=0,
                    )

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group1",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                    judge_provider="opencode",
                    judge_model="gemma4",
                ),
                dependencies=controller.ControllerDependencies(
                    train_runner=fake_train,
                    test_runner=fake_test,
                    opencode_runtime=RuntimeWithDatasetPlan(),
                ),
            )

            result = ctrl.run(max_steps=8)

            self.assertEqual(result.final_stage, "PLAN")
            plan_record = storage.read_dataset_plan_record(ctrl.paths.dataset_plan_file("trial_0001"))
            self.assertEqual(plan_record.dataset_action, "new_version")
            self.assertIn("opencode_dataset_plan", plan_record.evidence)
            next_input = storage.read_trial_input_record(ctrl.paths.input_file("trial_0002"))
            self.assertEqual(next_input.dataset_version, "study_001_trial_0002")
            self.assertEqual(next_input.dataset_preset, "hard")
            self.assertEqual(next_input.dataset_override, plan_record.generator_overrides)

    def test_run_falls_back_to_local_dataset_plan_when_planner_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            dataset_dir = train_root / "datasets" / "group1" / "firstpass"
            for path in (generator_workspace, dataset_dir):
                path.mkdir(parents=True, exist_ok=True)
            _write_dataset_config(train_root, "group1", "firstpass")

            def fake_train(_: object) -> controller.runners.train.TrainRunnerResult:
                return _train_result("group1", train_root, "trial_0001")

            def fake_test(_: object) -> controller.runners.test.TestRunnerResult:
                return controller.runners.test.TestRunnerResult(
                    record=contracts.TestRecord(
                        task="group1",
                        dataset_version="firstpass",
                        train_name="trial_0001",
                        metrics={"precision": 0.88, "recall": 0.83, "map50_95": 0.79},
                        predict_output_dir=str(train_root / "reports" / "group1" / "predict_trial_0001"),
                        val_output_dir=str(train_root / "reports" / "group1" / "val_trial_0001"),
                        report_dir=str(train_root / "reports" / "group1" / "test_trial_0001"),
                    ),
                    predict_command="uv run sinan predict",
                    val_command="uv run sinan test",
                )

            class RuntimeWithBrokenPlanner:
                def result_read(
                    self,
                    *,
                    study_name: str,
                    task: str,
                    trial_id: str,
                    dataset_version: str,
                    train_name: str,
                    primary_metric: str,
                    files: list[Path],
                ) -> controller.opencode_runtime.OpenCodeInvocationResult:
                    record = contracts.ResultSummaryRecord(
                        study_name=study_name,
                        task=task,
                        trial_id=trial_id,
                        dataset_version=dataset_version,
                        train_name=train_name,
                        primary_metric=primary_metric,
                        primary_score=0.79,
                        test_metrics={"precision": 0.88, "recall": 0.83, "map50_95": 0.79},
                        evaluation_available=False,
                        evaluation_metrics={},
                        failure_count=None,
                        trend="plateau",
                        delta_vs_previous=None,
                        delta_vs_best=None,
                        weak_classes=["icon_camera"],
                        failure_patterns=["sequence_consistency"],
                        recent_trials=[],
                        best_trial=None,
                        evidence=["opencode_summary"],
                    )
                    return controller.opencode_runtime.OpenCodeInvocationResult(
                        stdout=json.dumps(record.to_dict()),
                        stderr="",
                        command=("opencode", "run"),
                        returncode=0,
                    )

                def judge_trial(
                    self,
                    *,
                    study_name: str,
                    task: str,
                    trial_id: str,
                    files: list[Path],
                ) -> controller.opencode_runtime.OpenCodeInvocationResult:
                    return controller.opencode_runtime.OpenCodeInvocationResult(
                        stdout=(
                            '{"decision":"REGENERATE_DATA","reason":"weak_classes","confidence":0.81,'
                            '"next_action":{"dataset_action":"new_version","train_action":"from_run","base_run":"trial_0001"},'
                            '"evidence":["need more hard samples"]}'
                        ),
                        stderr="",
                        command=("opencode", "run"),
                        returncode=0,
                    )

                def plan_dataset(
                    self,
                    *,
                    study_name: str,
                    task: str,
                    trial_id: str,
                    files: list[Path],
                ) -> controller.opencode_runtime.OpenCodeInvocationResult:
                    raise controller.opencode_runtime.OpenCodeRuntimeError(
                        command_name="plan-dataset",
                        message="opencode_command_failed: planner unavailable",
                        command=["opencode", "run"],
                        returncode=1,
                    )

                def study_status(
                    self,
                    *,
                    study_name: str,
                    task: str,
                    files: list[Path],
                ) -> controller.opencode_runtime.OpenCodeInvocationResult:
                    payload = contracts.StudyStatusRecord(
                        study_name=study_name,
                        task=task,
                        status="running",
                        current_trial_id="trial_0002",
                        best_trial_id="trial_0001",
                        latest_decision="REGENERATE_DATA",
                        best_primary_score=0.79,
                        budget_pressure="low",
                        summary_cn="需要先补数据再继续。",
                        next_actions_cn=["生成新数据版本。"],
                        evidence=["opencode_study_status"],
                    )
                    return controller.opencode_runtime.OpenCodeInvocationResult(
                        stdout=json.dumps(payload.to_dict()),
                        stderr="",
                        command=("opencode", "run"),
                        returncode=0,
                    )

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group1",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                    judge_provider="opencode",
                    judge_model="gemma4",
                ),
                dependencies=controller.ControllerDependencies(
                    train_runner=fake_train,
                    test_runner=fake_test,
                    opencode_runtime=RuntimeWithBrokenPlanner(),
                ),
            )

            result = ctrl.run(max_steps=8)

            self.assertEqual(result.final_stage, "PLAN")
            plan_record = storage.read_dataset_plan_record(ctrl.paths.dataset_plan_file("trial_0001"))
            self.assertEqual(plan_record.dataset_action, "new_version")
            self.assertEqual(plan_record.generator_preset, "hard")
            self.assertIn("project", plan_record.generator_overrides or {})
            self.assertTrue(any("dataset_plan_fallback=runtime_error" in item for item in plan_record.evidence))

    def test_build_dataset_stage_materializes_generator_override_file_and_passes_preset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            generator_workspace.mkdir(parents=True, exist_ok=True)
            captured_requests: list[controller.runners.dataset.DatasetRunnerRequest] = []

            def fake_dataset_runner(
                request: controller.runners.dataset.DatasetRunnerRequest,
            ) -> controller.runners.dataset.DatasetRunnerResult:
                captured_requests.append(request)
                return controller.runners.dataset.DatasetRunnerResult(
                    record=contracts.DatasetRecord(
                        task=request.task,
                        dataset_version=request.dataset_version,
                        dataset_root=str(request.dataset_dir),
                        label_source=str(request.generator_workspace),
                    ),
                    command="sinan-generator make-dataset",
                )

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group1",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                ),
                dependencies=controller.ControllerDependencies(
                    dataset_runner=fake_dataset_runner,
                ),
            )

            storage.write_study_record(
                ctrl.paths.study_file,
                contracts.StudyRecord(
                    study_name="study_001",
                    task="group1",
                    status="running",
                    mode="full_auto",
                    train_root=str(train_root),
                    generator_workspace=str(generator_workspace),
                    judge=contracts.JudgeConfig(provider="rules", model="policy-v1"),
                    budget=contracts.StudyBudget(max_trials=20, max_hours=24.0, max_no_improve_trials=4),
                    current_trial_id="trial_0002",
                    best_trial_id=None,
                ),
            )
            storage.write_trial_input_record(
                ctrl.paths.input_file("trial_0002"),
                contracts.TrialInputRecord(
                    trial_id="trial_0002",
                    task="group1",
                    dataset_version="study_001_trial_0002",
                    dataset_preset="hard",
                    dataset_override={
                        "project": {"sample_count": 320},
                        "sampling": {
                            "target_count_min": 3,
                            "target_count_max": 5,
                            "distractor_count_min": 5,
                            "distractor_count_max": 8,
                        },
                        "effects": {
                            "common": {
                                "scene_veil_strength": 1.45,
                                "background_blur_radius_min": 1,
                                "background_blur_radius_max": 2,
                            },
                            "click": {
                                "icon_shadow_alpha_min": 0.28,
                                "icon_shadow_alpha_max": 0.36,
                                "icon_shadow_offset_x_min": 2,
                                "icon_shadow_offset_x_max": 3,
                                "icon_shadow_offset_y_min": 3,
                                "icon_shadow_offset_y_max": 4,
                                "icon_edge_blur_radius_min": 1,
                                "icon_edge_blur_radius_max": 2,
                            },
                        },
                    },
                    train_name="trial_0002",
                    train_mode="fresh",
                    base_run=None,
                    params={"epochs": 120, "batch": 16, "imgsz": 640, "device": "0"},
                ),
            )

            execution = ctrl.run_stage("BUILD_DATASET")

            self.assertEqual(execution.next_stage, "TRAIN")
            self.assertEqual(len(captured_requests), 1)
            request = captured_requests[0]
            self.assertEqual(request.preset, "hard")
            self.assertEqual(request.override_file, ctrl.paths.generator_override_file("trial_0002"))
            self.assertTrue(request.override_file.exists())
            payload = json.loads(request.override_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["project"]["sample_count"], 320)

    def test_next_action_stops_when_elapsed_hours_budget_is_reached(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            generator_workspace.mkdir(parents=True, exist_ok=True)
            now = datetime(2026, 4, 5, 12, 0, tzinfo=timezone.utc)

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group1",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                    max_hours=1.0,
                ),
                dependencies=controller.ControllerDependencies(
                    now_provider=lambda: now,
                ),
            )

            storage.write_study_record(
                ctrl.paths.study_file,
                contracts.StudyRecord(
                    study_name="study_001",
                    task="group1",
                    status="running",
                    mode="full_auto",
                    train_root=str(train_root),
                    generator_workspace=str(generator_workspace),
                    judge=contracts.JudgeConfig(provider="rules", model="policy-v1"),
                    budget=contracts.StudyBudget(max_trials=20, max_hours=1.0, max_no_improve_trials=4),
                    current_trial_id="trial_0001",
                    best_trial_id=None,
                    started_at=(now - timedelta(hours=2)).isoformat(),
                ),
            )
            storage.write_trial_input_record(
                ctrl.paths.input_file("trial_0001"),
                contracts.TrialInputRecord(
                    trial_id="trial_0001",
                    task="group1",
                    dataset_version="firstpass",
                    train_name="trial_0001",
                    train_mode="fresh",
                    base_run=None,
                    params={"epochs": 120, "batch": 16, "imgsz": 640, "device": "0"},
                ),
            )
            storage.write_result_summary_record(
                ctrl.paths.result_summary_file("trial_0001"),
                contracts.ResultSummaryRecord(
                    study_name="study_001",
                    task="group1",
                    trial_id="trial_0001",
                    dataset_version="firstpass",
                    train_name="trial_0001",
                    primary_metric="map50_95",
                    primary_score=0.81,
                    test_metrics={"map50_95": 0.81, "recall": 0.87},
                    evaluation_available=False,
                    evaluation_metrics={},
                    failure_count=None,
                    trend="baseline",
                    delta_vs_previous=None,
                    delta_vs_best=None,
                    weak_classes=[],
                    failure_patterns=[],
                    recent_trials=[],
                    best_trial=None,
                    evidence=["baseline"],
                ),
            )
            storage.write_decision_record(
                ctrl.paths.decision_file("trial_0001"),
                contracts.DecisionRecord(
                    trial_id="trial_0001",
                    decision="RETUNE",
                    confidence=0.74,
                    reason="continue",
                    next_action={"dataset_action": "reuse", "train_action": "from_run", "base_run": "trial_0001"},
                    evidence=["continue"],
                    agent=contracts.AgentRef(provider="rules", name="policy-judge", model="policy-v1"),
                ),
            )

            execution = ctrl.run_stage("NEXT_ACTION")

            self.assertEqual(execution.next_stage, "STOP")
            self.assertEqual(execution.detail, "max_hours_reached")
            study = storage.read_study_record(ctrl.paths.study_file)
            self.assertEqual(study.status, "stopped")

    def test_next_action_stops_when_new_dataset_budget_is_exhausted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            generator_workspace.mkdir(parents=True, exist_ok=True)
            now = datetime(2026, 4, 5, 12, 0, tzinfo=timezone.utc)

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group1",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                    max_new_datasets=1,
                ),
                dependencies=controller.ControllerDependencies(
                    now_provider=lambda: now,
                ),
            )

            storage.write_study_record(
                ctrl.paths.study_file,
                contracts.StudyRecord(
                    study_name="study_001",
                    task="group1",
                    status="running",
                    mode="full_auto",
                    train_root=str(train_root),
                    generator_workspace=str(generator_workspace),
                    judge=contracts.JudgeConfig(provider="rules", model="policy-v1"),
                    budget=contracts.StudyBudget(
                        max_trials=20,
                        max_hours=24.0,
                        max_new_datasets=1,
                        max_no_improve_trials=4,
                    ),
                    current_trial_id="trial_0002",
                    best_trial_id="trial_0001",
                    started_at=(now - timedelta(minutes=30)).isoformat(),
                ),
            )
            storage.write_trial_input_record(
                ctrl.paths.input_file("trial_0001"),
                contracts.TrialInputRecord(
                    trial_id="trial_0001",
                    task="group1",
                    dataset_version="firstpass",
                    train_name="trial_0001",
                    train_mode="fresh",
                    base_run=None,
                    params={"epochs": 120, "batch": 16, "imgsz": 640, "device": "0"},
                ),
            )
            storage.write_trial_input_record(
                ctrl.paths.input_file("trial_0002"),
                contracts.TrialInputRecord(
                    trial_id="trial_0002",
                    task="group1",
                    dataset_version="study_001_trial_0002",
                    dataset_preset="hard",
                    dataset_override={"project": {"sample_count": 320}},
                    train_name="trial_0002",
                    train_mode="from_run",
                    base_run="trial_0001",
                    params={"epochs": 120, "batch": 16, "imgsz": 640, "device": "0"},
                ),
            )
            storage.write_result_summary_record(
                ctrl.paths.result_summary_file("trial_0002"),
                contracts.ResultSummaryRecord(
                    study_name="study_001",
                    task="group1",
                    trial_id="trial_0002",
                    dataset_version="study_001_trial_0002",
                    train_name="trial_0002",
                    primary_metric="map50_95",
                    primary_score=0.78,
                    test_metrics={"map50_95": 0.78, "recall": 0.84},
                    evaluation_available=True,
                    evaluation_metrics={"full_sequence_hit_rate": 0.71, "order_error_rate": 0.09},
                    failure_count=5,
                    trend="plateau",
                    delta_vs_previous=-0.01,
                    delta_vs_best=-0.03,
                    weak_classes=["icon_camera"],
                    failure_patterns=["sequence_consistency"],
                    recent_trials=[],
                    best_trial=None,
                    evidence=["sequence_consistency"],
                ),
            )
            storage.write_decision_record(
                ctrl.paths.decision_file("trial_0002"),
                contracts.DecisionRecord(
                    trial_id="trial_0002",
                    decision="REGENERATE_DATA",
                    confidence=0.8,
                    reason="group1_data_quality_gap",
                    next_action={"dataset_action": "new_version", "train_action": "from_run", "base_run": "trial_0002"},
                    evidence=["need more hard samples"],
                    agent=contracts.AgentRef(provider="rules", name="policy-judge", model="policy-v1"),
                ),
            )

            execution = ctrl.run_stage("NEXT_ACTION")

            self.assertEqual(execution.next_stage, "STOP")
            self.assertEqual(execution.detail, "max_new_datasets_reached")
            self.assertFalse(ctrl.paths.input_file("trial_0003").exists())
            study = storage.read_study_record(ctrl.paths.study_file)
            self.assertEqual(study.status, "stopped")

    def test_goal_only_stop_ignores_budget_limits_for_business_goal_study(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            dataset_dir = train_root / "datasets" / "group2" / "firstpass"
            gold_dir = root / "gold"
            prediction_dir = root / "predictions"
            business_cases = root / "business-cases"
            for path in (generator_workspace, dataset_dir, gold_dir, prediction_dir, business_cases):
                path.mkdir(parents=True, exist_ok=True)
            (gold_dir / "labels.jsonl").write_text("", encoding="utf-8")
            (prediction_dir / "labels.jsonl").write_text("", encoding="utf-8")
            _write_dataset_config(train_root, "group2", "firstpass")

            def fake_train(_: object) -> controller.runners.train.TrainRunnerResult:
                return controller.runners.train.TrainRunnerResult(
                    record=contracts.TrainRecord(
                        task="group2",
                        train_name="trial_0001",
                        run_dir=str(train_root / "runs" / "group2" / "trial_0001"),
                        params={"epochs": 100, "batch": 16, "imgsz": 192},
                        best_weights=str(train_root / "runs" / "group2" / "trial_0001" / "weights" / "best.pt"),
                        last_weights=str(train_root / "runs" / "group2" / "trial_0001" / "weights" / "last.pt"),
                    ),
                    command="uv run sinan train group2",
                )

            def fake_test(_: object) -> controller.runners.test.TestRunnerResult:
                return controller.runners.test.TestRunnerResult(
                    record=contracts.TestRecord(
                        task="group2",
                        dataset_version="firstpass",
                        train_name="trial_0001",
                        metrics={"point_hit_rate": 1.0},
                        predict_output_dir=str(prediction_dir),
                        val_output_dir=str(train_root / "reports" / "group2" / "val_trial_0001"),
                        report_dir=str(train_root / "reports" / "group2" / "test_trial_0001"),
                    ),
                    predict_command="uv run sinan predict group2",
                    val_command="uv run sinan test group2",
                )

            def fake_evaluate(_: object) -> controller.runners.evaluate.EvaluateRunnerResult:
                return controller.runners.evaluate.EvaluateRunnerResult(
                    record=contracts.EvaluateRecord(
                        available=True,
                        task="group2",
                        metrics={"point_hit_rate": 1.0, "mean_iou": 0.91, "mean_center_error_px": 3.0},
                        failure_count=0,
                        report_dir=str(train_root / "reports" / "group2" / "eval_trial_0001"),
                    ),
                    command="uv run sinan evaluate group2",
                )

            def fake_business_eval(_: object) -> controller.runners.business_eval.BusinessEvalRunnerResult:
                return controller.runners.business_eval.BusinessEvalRunnerResult(
                    record=contracts.BusinessEvalRecord(
                        trial_id="trial_0001",
                        task="group2",
                        train_name="trial_0001",
                        cases_root=str(business_cases),
                        available_cases=100,
                        total_cases=30,
                        passed_cases=0,
                        success_rate=0.0,
                        success_threshold=0.95,
                        min_cases=30,
                        sample_size=30,
                        commercial_ready=False,
                        point_tolerance_px=12,
                        iou_threshold=0.5,
                        sampled_source=str(root / "reports" / "business_eval_trial_0001" / "_sampled_source" / "labels.jsonl"),
                        report_dir=str(root / "reports" / "business_eval_trial_0001"),
                        prediction_dir=str(root / "reports" / "business_eval_trial_0001" / "modeltest" / "predict"),
                        evaluation_report_dir=str(root / "reports" / "business_eval_trial_0001" / "evaluation"),
                        case_results=[],
                        evidence=["commercial_ready=false"],
                    ),
                    command="uv run sinan business-eval group2",
                )

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group2",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                    gold_dir=gold_dir,
                    prediction_dir=prediction_dir,
                    business_eval_dir=business_cases,
                    goal_only_stop=True,
                    max_trials=1,
                    max_hours=0.001,
                    max_new_datasets=1,
                    max_no_improve_trials=1,
                ),
                dependencies=controller.ControllerDependencies(
                    train_runner=fake_train,
                    test_runner=fake_test,
                    evaluate_runner=fake_evaluate,
                    business_eval_runner=fake_business_eval,
                ),
            )

            result = ctrl.run(max_steps=8)

            self.assertEqual(result.final_stage, "PLAN")
            study = storage.read_study_record(ctrl.paths.study_file)
            self.assertTrue(study.goal_only_stop)
            self.assertEqual(study.status, "running")
            self.assertEqual(study.current_trial_id, "trial_0002")
            next_input = storage.read_trial_input_record(ctrl.paths.input_file("trial_0002"))
            self.assertEqual(next_input.dataset_version, "study_001_trial_0002")

    def test_run_with_zero_max_steps_continues_until_commercial_stop(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            dataset_dir = train_root / "datasets" / "group2" / "firstpass"
            gold_dir = root / "gold"
            prediction_dir = root / "predictions"
            business_cases = root / "business-cases"
            for path in (generator_workspace, dataset_dir, gold_dir, prediction_dir, business_cases):
                path.mkdir(parents=True, exist_ok=True)
            (gold_dir / "labels.jsonl").write_text("", encoding="utf-8")
            (prediction_dir / "labels.jsonl").write_text("", encoding="utf-8")
            _write_dataset_config(train_root, "group2", "firstpass")

            def fake_train(_: object) -> controller.runners.train.TrainRunnerResult:
                return controller.runners.train.TrainRunnerResult(
                    record=contracts.TrainRecord(
                        task="group2",
                        train_name="trial_0001",
                        run_dir=str(train_root / "runs" / "group2" / "trial_0001"),
                        params={"epochs": 100, "batch": 16, "imgsz": 192},
                        best_weights=str(train_root / "runs" / "group2" / "trial_0001" / "weights" / "best.pt"),
                        last_weights=str(train_root / "runs" / "group2" / "trial_0001" / "weights" / "last.pt"),
                    ),
                    command="uv run sinan train group2",
                )

            def fake_test(_: object) -> controller.runners.test.TestRunnerResult:
                return controller.runners.test.TestRunnerResult(
                    record=contracts.TestRecord(
                        task="group2",
                        dataset_version="firstpass",
                        train_name="trial_0001",
                        metrics={"point_hit_rate": 1.0},
                        predict_output_dir=str(prediction_dir),
                        val_output_dir=str(train_root / "reports" / "group2" / "val_trial_0001"),
                        report_dir=str(train_root / "reports" / "group2" / "test_trial_0001"),
                    ),
                    predict_command="uv run sinan predict group2",
                    val_command="uv run sinan test group2",
                )

            def fake_evaluate(_: object) -> controller.runners.evaluate.EvaluateRunnerResult:
                return controller.runners.evaluate.EvaluateRunnerResult(
                    record=contracts.EvaluateRecord(
                        available=True,
                        task="group2",
                        metrics={"point_hit_rate": 1.0, "mean_iou": 0.91, "mean_center_error_px": 3.0},
                        failure_count=0,
                        report_dir=str(train_root / "reports" / "group2" / "eval_trial_0001"),
                    ),
                    command="uv run sinan evaluate group2",
                )

            def fake_business_eval(_: object) -> controller.runners.business_eval.BusinessEvalRunnerResult:
                return controller.runners.business_eval.BusinessEvalRunnerResult(
                    record=contracts.BusinessEvalRecord(
                        trial_id="trial_0001",
                        task="group2",
                        train_name="trial_0001",
                        cases_root=str(business_cases),
                        available_cases=100,
                        total_cases=30,
                        passed_cases=29,
                        success_rate=0.99,
                        success_threshold=0.95,
                        min_cases=30,
                        sample_size=30,
                        commercial_ready=True,
                        point_tolerance_px=12,
                        iou_threshold=0.5,
                        sampled_source=str(root / "reports" / "business_eval_trial_0001" / "_sampled_source" / "labels.jsonl"),
                        report_dir=str(root / "reports" / "business_eval_trial_0001"),
                        prediction_dir=str(root / "reports" / "business_eval_trial_0001" / "modeltest" / "predict"),
                        evaluation_report_dir=str(root / "reports" / "business_eval_trial_0001" / "evaluation"),
                        case_results=[],
                        evidence=["commercial_ready=true"],
                    ),
                    command="uv run sinan business-eval group2",
                )

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group2",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                    gold_dir=gold_dir,
                    prediction_dir=prediction_dir,
                    business_eval_dir=business_cases,
                    goal_only_stop=True,
                ),
                dependencies=controller.ControllerDependencies(
                    train_runner=fake_train,
                    test_runner=fake_test,
                    evaluate_runner=fake_evaluate,
                    business_eval_runner=fake_business_eval,
                ),
            )

            result = ctrl.run(max_steps=0)

            self.assertEqual(result.final_stage, "STOP")
            study = storage.read_study_record(ctrl.paths.study_file)
            self.assertEqual(study.status, "completed")
            self.assertEqual(study.final_reason, "commercial_gate_passed")
            self.assertTrue(study.goal_only_stop)

    def test_completed_study_reruns_business_eval_when_business_threshold_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            dataset_dir = train_root / "datasets" / "group2" / "firstpass"
            gold_dir = root / "gold"
            prediction_dir = root / "predictions"
            business_cases = root / "business-cases"
            for path in (generator_workspace, dataset_dir, gold_dir, prediction_dir, business_cases):
                path.mkdir(parents=True, exist_ok=True)
            (gold_dir / "labels.jsonl").write_text("", encoding="utf-8")
            (prediction_dir / "labels.jsonl").write_text("", encoding="utf-8")
            _write_dataset_config(train_root, "group2", "firstpass")

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group2",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                    gold_dir=gold_dir,
                    prediction_dir=prediction_dir,
                    business_eval_dir=business_cases,
                    business_eval_sample_size=50,
                    business_eval_min_cases=50,
                    point_tolerance_px=3,
                    goal_only_stop=True,
                )
            )

            study = contracts.StudyRecord(
                study_name="study_001",
                task="group2",
                status="completed",
                mode="full_auto",
                train_root=str(train_root),
                generator_workspace=str(generator_workspace),
                    judge=contracts.JudgeConfig(provider="rules", model="policy-v1"),
                budget=contracts.StudyBudget(max_trials=20, max_hours=24.0, max_new_datasets=None, max_no_improve_trials=4),
                business_eval=contracts.BusinessEvalConfig(
                    cases_root=str(business_cases),
                    success_threshold=0.95,
                    min_cases=30,
                    sample_size=30,
                    point_tolerance_px=12,
                    iou_threshold=0.5,
                ),
                started_at="2026-04-10T00:00:00+00:00",
                current_trial_id="trial_0008",
                best_trial_id="trial_0008",
                final_reason="commercial_gate_passed",
                final_detail="1.0000/0.9500",
                goal_only_stop=True,
            )
            storage.write_study_record(ctrl.paths.study_file, study)
            trial_dir = ctrl.paths.ensure_trial_dir("trial_0008")
            storage.write_trial_input_record(
                ctrl.paths.input_file("trial_0008"),
                contracts.TrialInputRecord(
                    trial_id="trial_0008",
                    task="group2",
                    dataset_version="firstpass",
                    train_name="trial_0008",
                    train_mode="from_run",
                    base_run="prelabel_g2_v1",
                    params={"epochs": 100, "batch": 16, "imgsz": 192, "device": "0"},
                ),
            )
            storage.write_result_summary_record(
                ctrl.paths.result_summary_file("trial_0008"),
                _group2_trial_summary("trial_0008", score=1.0),
            )
            storage.write_decision_record(
                ctrl.paths.decision_file("trial_0008"),
                contracts.DecisionRecord(
                    trial_id="trial_0008",
                    decision="PROMOTE_BRANCH",
                    confidence=0.95,
                    reason="good_metrics",
                    next_action={"dataset_action": "reuse", "train_action": "from_run", "base_run": "trial_0008"},
                    evidence=["good_metrics"],
                    agent=contracts.AgentRef(provider="rules", name="policy-judge", model="policy-v1"),
                ),
            )
            (trial_dir / "STOP.ok").write_text("stop\n", encoding="utf-8")

            observed_requests: list[controller.runners.business_eval.BusinessEvalRunnerRequest] = []

            def fake_business_eval(
                request: controller.runners.business_eval.BusinessEvalRunnerRequest,
            ) -> controller.runners.business_eval.BusinessEvalRunnerResult:
                observed_requests.append(request)
                return controller.runners.business_eval.BusinessEvalRunnerResult(
                    record=contracts.BusinessEvalRecord(
                        trial_id="trial_0008",
                        task="group2",
                        train_name="trial_0008",
                        cases_root=str(business_cases),
                        available_cases=257,
                        total_cases=50,
                        passed_cases=40,
                        success_rate=0.8,
                        success_threshold=0.95,
                        min_cases=50,
                        sample_size=50,
                        commercial_ready=False,
                        point_tolerance_px=3,
                        iou_threshold=0.5,
                        sampled_source=str(ctrl.paths.business_eval_root("trial_0008") / "_sampled_source" / "labels.jsonl"),
                        report_dir=str(ctrl.paths.business_eval_root("trial_0008")),
                        prediction_dir=str(ctrl.paths.business_eval_root("trial_0008") / "modeltest"),
                        evaluation_report_dir=str(ctrl.paths.business_eval_root("trial_0008") / "evaluation"),
                        case_results=[],
                        evidence=["commercial_ready=false"],
                    ),
                    command="uv run sinan business-eval group2",
                )

            ctrl.dependencies = replace(ctrl.dependencies, business_eval_runner=fake_business_eval)

            result = ctrl.run(max_steps=1)

            self.assertEqual(result.final_stage, "PLAN")
            self.assertEqual(len(observed_requests), 1)
            self.assertEqual(observed_requests[0].sample_size, 50)
            self.assertEqual(observed_requests[0].point_tolerance_px, 3)
            updated_study = storage.read_study_record(ctrl.paths.study_file)
            self.assertEqual(updated_study.status, "running")
            self.assertEqual(updated_study.current_trial_id, "trial_0009")
            business_record = storage.read_business_eval_record(ctrl.paths.business_eval_file("trial_0008"))
            self.assertEqual(business_record.sample_size, 50)
            self.assertEqual(business_record.point_tolerance_px, 3)

    def test_run_completes_one_trial_when_rule_judge_promotes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            dataset_dir = train_root / "datasets" / "group1" / "firstpass"
            gold_dir = root / "gold"
            prediction_dir = root / "predictions"
            for path in (generator_workspace, dataset_dir, gold_dir, prediction_dir):
                path.mkdir(parents=True, exist_ok=True)
            (gold_dir / "labels.jsonl").write_text("", encoding="utf-8")
            (prediction_dir / "labels.jsonl").write_text("", encoding="utf-8")
            _write_dataset_config(train_root, "group1", "firstpass")

            def fake_train(_: object) -> controller.runners.train.TrainRunnerResult:
                return _train_result("group1", train_root, "trial_0001")

            def fake_test(_: object) -> controller.runners.test.TestRunnerResult:
                return controller.runners.test.TestRunnerResult(
                    record=contracts.TestRecord(
                        task="group1",
                        dataset_version="firstpass",
                        train_name="trial_0001",
                        metrics={"precision": 0.91, "recall": 0.89, "map50_95": 0.84},
                        predict_output_dir=str(train_root / "reports" / "group1" / "predict_trial_0001"),
                        val_output_dir=str(train_root / "reports" / "group1" / "val_trial_0001"),
                        report_dir=str(train_root / "reports" / "group1" / "test_trial_0001"),
                    ),
                    predict_command="uv run sinan predict",
                    val_command="uv run sinan test",
                )

            def fake_evaluate(_: object) -> controller.runners.evaluate.EvaluateRunnerResult:
                return controller.runners.evaluate.EvaluateRunnerResult(
                    record=contracts.EvaluateRecord(
                        available=True,
                        task="group1",
                        metrics={"full_sequence_hit_rate": 0.86, "order_error_rate": 0.03},
                        failure_count=0,
                        report_dir=str(train_root / "reports" / "group1" / "eval_trial_0001"),
                    ),
                    command="uv run sinan evaluate",
                )

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group1",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                    gold_dir=gold_dir,
                    prediction_dir=prediction_dir,
                ),
                dependencies=controller.ControllerDependencies(
                    train_runner=fake_train,
                    test_runner=fake_test,
                    evaluate_runner=fake_evaluate,
                ),
            )

            result = ctrl.run(max_steps=20)

            self.assertEqual(result.final_stage, "STOP")
            study = storage.read_study_record(ctrl.paths.study_file)
            self.assertEqual(study.status, "completed")
            self.assertEqual(study.best_trial_id, "trial_0001")
            self.assertTrue(ctrl.paths.decision_file("trial_0001").exists())
            leaderboard = storage.read_leaderboard_record(ctrl.paths.leaderboard_file)
            self.assertEqual(len(leaderboard.entries), 1)
            self.assertEqual(leaderboard.entries[0].trial_id, "trial_0001")

    def test_run_allocates_next_trial_input_after_retune_without_carrying_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            dataset_dir = train_root / "datasets" / "group2" / "firstpass"
            gold_dir = root / "gold"
            prediction_dir = root / "predictions"
            for path in (generator_workspace, dataset_dir, gold_dir, prediction_dir):
                path.mkdir(parents=True, exist_ok=True)
            (gold_dir / "labels.jsonl").write_text("", encoding="utf-8")
            (prediction_dir / "labels.jsonl").write_text("", encoding="utf-8")
            _write_dataset_config(train_root, "group2", "firstpass")

            def fake_train(_: object) -> controller.runners.train.TrainRunnerResult:
                return controller.runners.train.TrainRunnerResult(
                    record=contracts.TrainRecord(
                        task="group2",
                        train_name="trial_0001",
                        run_dir=str(train_root / "runs" / "group2" / "trial_0001"),
                        params={"epochs": 100, "batch": 16, "imgsz": 192, "model": "paired_cnn_v1"},
                        best_weights=str(train_root / "runs" / "group2" / "trial_0001" / "weights" / "best.pt"),
                        last_weights=str(train_root / "runs" / "group2" / "trial_0001" / "weights" / "last.pt"),
                    ),
                    command="uv run sinan train group2",
                )

            def fake_test(_: object) -> controller.runners.test.TestRunnerResult:
                return controller.runners.test.TestRunnerResult(
                    record=contracts.TestRecord(
                        task="group2",
                        dataset_version="firstpass",
                        train_name="trial_0001",
                        metrics={"precision": 0.9, "recall": 0.88, "map50_95": 0.81},
                        predict_output_dir=str(train_root / "reports" / "group2" / "predict_trial_0001"),
                        val_output_dir=str(train_root / "reports" / "group2" / "val_trial_0001"),
                        report_dir=str(train_root / "reports" / "group2" / "test_trial_0001"),
                    ),
                    predict_command="uv run sinan predict group2",
                    val_command="uv run sinan test group2",
                )

            def fake_evaluate(_: object) -> controller.runners.evaluate.EvaluateRunnerResult:
                return controller.runners.evaluate.EvaluateRunnerResult(
                    record=contracts.EvaluateRecord(
                        available=True,
                        task="group2",
                        metrics={
                            "point_hit_rate": 0.89,
                            "mean_iou": 0.82,
                            "mean_center_error_px": 14.0,
                        },
                        failure_count=4,
                        report_dir=str(train_root / "reports" / "group2" / "eval_trial_0001"),
                    ),
                    command="uv run sinan evaluate",
                )

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group2",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                    gold_dir=gold_dir,
                    prediction_dir=prediction_dir,
                ),
                dependencies=controller.ControllerDependencies(
                    train_runner=fake_train,
                    test_runner=fake_test,
                    evaluate_runner=fake_evaluate,
                ),
            )

            result = ctrl.run(max_steps=8)

            self.assertEqual(result.final_stage, "PLAN")
            study = storage.read_study_record(ctrl.paths.study_file)
            self.assertEqual(study.status, "running")
            self.assertEqual(study.current_trial_id, "trial_0002")
            next_input = storage.read_trial_input_record(ctrl.paths.input_file("trial_0002"))
            self.assertEqual(next_input.trial_id, "trial_0002")
            self.assertEqual(next_input.train_mode, "from_run")
            self.assertEqual(next_input.base_run, "trial_0001")
            self.assertEqual(next_input.params["imgsz"], 224)
            self.assertNotIn("model", next_input.params)

    def test_run_uses_optuna_suggestion_for_retune_when_runtime_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            dataset_dir = train_root / "datasets" / "group1" / "firstpass"
            for path in (generator_workspace, dataset_dir):
                path.mkdir(parents=True, exist_ok=True)
            _write_dataset_config(train_root, "group1", "firstpass")

            def fake_train(_: object) -> controller.runners.train.TrainRunnerResult:
                return _train_result("group1", train_root, "trial_0001")

            def fake_test(_: object) -> controller.runners.test.TestRunnerResult:
                return controller.runners.test.TestRunnerResult(
                    record=contracts.TestRecord(
                        task="group1",
                        dataset_version="firstpass",
                        train_name="trial_0001",
                        metrics={"precision": 0.84, "recall": 0.79, "map50_95": 0.76},
                        predict_output_dir=str(train_root / "reports" / "group1" / "predict_trial_0001"),
                        val_output_dir=str(train_root / "reports" / "group1" / "val_trial_0001"),
                        report_dir=str(train_root / "reports" / "group1" / "test_trial_0001"),
                    ),
                    predict_command="uv run sinan predict",
                    val_command="uv run sinan test",
                )

            class FakeOptunaRuntime:
                def suggest_next_parameters(
                    self,
                    *,
                    plan: controller.optimize.OptimizationPlan,
                    completed_input: contracts.TrialInputRecord,
                    summary: contracts.ResultSummaryRecord,
                    next_trial_id: str,
                ) -> controller.optuna_runtime.OptunaSuggestion:
                    self.plan = plan
                    self.completed_input = completed_input
                    self.summary = summary
                    self.next_trial_id = next_trial_id
                    return controller.optuna_runtime.OptunaSuggestion(
                        study_name="study_001",
                        trial_number=7,
                        params={
                            "model": "yolo26s.pt",
                            "epochs": 160,
                            "batch": 8,
                            "imgsz": 512,
                        },
                        reused_existing=False,
                    )

            optuna_dep = FakeOptunaRuntime()
            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group1",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                ),
                dependencies=controller.ControllerDependencies(
                    train_runner=fake_train,
                    test_runner=fake_test,
                    optuna_runtime=optuna_dep,
                ),
            )

            result = ctrl.run(max_steps=8)

            self.assertEqual(result.final_stage, "PLAN")
            next_input = storage.read_trial_input_record(ctrl.paths.input_file("trial_0002"))
            self.assertNotIn("model", next_input.params)
            self.assertEqual(next_input.params["epochs"], 160)
            self.assertEqual(next_input.params["batch"], 8)
            self.assertEqual(next_input.params["imgsz"], 512)
            self.assertEqual(next_input.params[controller.optuna_runtime.OPTUNA_TRIAL_NUMBER_KEY], 7)
            self.assertEqual(next_input.params[controller.optuna_runtime.OPTUNA_ENGINE_KEY], "optuna")
            self.assertTrue(optuna_dep.plan.use_optuna)
            self.assertEqual(optuna_dep.completed_input.trial_id, "trial_0001")
            self.assertEqual(optuna_dep.next_trial_id, "trial_0002")

    def test_run_falls_back_to_rule_parameters_when_optuna_runtime_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            dataset_dir = train_root / "datasets" / "group1" / "firstpass"
            for path in (generator_workspace, dataset_dir):
                path.mkdir(parents=True, exist_ok=True)
            _write_dataset_config(train_root, "group1", "firstpass")

            def fake_train(_: object) -> controller.runners.train.TrainRunnerResult:
                return _train_result("group1", train_root, "trial_0001")

            def fake_test(_: object) -> controller.runners.test.TestRunnerResult:
                return controller.runners.test.TestRunnerResult(
                    record=contracts.TestRecord(
                        task="group1",
                        dataset_version="firstpass",
                        train_name="trial_0001",
                        metrics={"precision": 0.84, "recall": 0.79, "map50_95": 0.76},
                        predict_output_dir=str(train_root / "reports" / "group1" / "predict_trial_0001"),
                        val_output_dir=str(train_root / "reports" / "group1" / "val_trial_0001"),
                        report_dir=str(train_root / "reports" / "group1" / "test_trial_0001"),
                    ),
                    predict_command="uv run sinan predict",
                    val_command="uv run sinan test",
                )

            class FailingOptunaRuntime:
                def suggest_next_parameters(
                    self,
                    *,
                    plan: controller.optimize.OptimizationPlan,
                    completed_input: contracts.TrialInputRecord,
                    summary: contracts.ResultSummaryRecord,
                    next_trial_id: str,
                ) -> controller.optuna_runtime.OptunaSuggestion:
                    del plan, completed_input, summary, next_trial_id
                    raise controller.optuna_runtime.OptunaRuntimeError("optuna_runtime_failed")

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group1",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                ),
                dependencies=controller.ControllerDependencies(
                    train_runner=fake_train,
                    test_runner=fake_test,
                    optuna_runtime=FailingOptunaRuntime(),
                ),
            )

            result = ctrl.run(max_steps=8)

            self.assertEqual(result.final_stage, "PLAN")
            next_input = storage.read_trial_input_record(ctrl.paths.input_file("trial_0002"))
            self.assertNotIn("model", next_input.params)
            self.assertEqual(next_input.params["epochs"], 140)
            self.assertEqual(next_input.params["batch"], 8)
            self.assertEqual(next_input.params["imgsz"], 640)
            self.assertNotIn(controller.optuna_runtime.OPTUNA_TRIAL_NUMBER_KEY, next_input.params)


if __name__ == "__main__":
    unittest.main()
