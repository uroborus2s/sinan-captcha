from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from auto_train import analysis, contracts, layout, storage
from common.jsonl import write_jsonl


class AutoTrainAnalysisTests(unittest.TestCase):
    def test_build_trial_analysis_collects_group1_component_errors_and_params(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = layout.StudyPaths(
                studies_root=root / "studies",
                task="group1",
                study_name="study_001",
            )
            paths.ensure_layout()

            trial_id = "trial_0004"
            trial_dir = paths.ensure_trial_dir(trial_id)
            report_dir = trial_dir / "evaluation"
            report_dir.mkdir(parents=True, exist_ok=True)
            failures_path = report_dir / "failures.jsonl"
            write_jsonl(
                failures_path,
                [
                    {"sample_id": "case_001", "reason": "order_mismatch", "target_count": 3},
                    {"sample_id": "case_002", "reason": "order_mismatch", "target_count": 3},
                    {"sample_id": "case_003", "reason": "sequence_mismatch", "target_count": 3},
                ],
            )

            query_failcases = trial_dir / "query_failcases.jsonl"
            proposal_failcases = trial_dir / "proposal_failcases.jsonl"
            write_jsonl(
                query_failcases,
                [
                    {"sample_id": "query_001", "reason": "count_mismatch"},
                    {"sample_id": "query_002", "reason": "count_mismatch"},
                    {"sample_id": "query_003", "reason": "location_mismatch"},
                ],
            )
            write_jsonl(
                proposal_failcases,
                [
                    {"sample_id": "scene_001", "reason": "recall_miss"},
                    {"sample_id": "scene_002", "reason": "precision_fp"},
                ],
            )

            trial_input = contracts.TrialInputRecord(
                trial_id=trial_id,
                task="group1",
                dataset_version="v1",
                train_name="trial_0004",
                train_mode="from_run",
                base_run="trial_0003",
                params={
                    "model": "yolo26n.pt",
                    "epochs": 120,
                    "batch": 16,
                    "imgsz": 640,
                    "device": "0",
                },
            )
            storage.write_trial_input_record(paths.input_file(trial_id), trial_input)
            storage.write_train_record(
                paths.query_train_file(trial_id),
                contracts.TrainRecord(
                    task="group1",
                    train_name="trial_0004",
                    run_dir=str(root / "runs" / "group1" / "trial_0004"),
                    params={
                        "component": "query-detector",
                        "model": "yolo26n.pt",
                        "epochs": 120,
                        "batch": 16,
                        "imgsz": 640,
                        "device": "0",
                    },
                    best_weights=str(root / "runs" / "group1" / "trial_0004" / "query-detector" / "weights" / "best.pt"),
                    last_weights=str(root / "runs" / "group1" / "trial_0004" / "query-detector" / "weights" / "last.pt"),
                ),
            )
            storage.write_train_record(
                paths.scene_train_file(trial_id),
                contracts.TrainRecord(
                    task="group1",
                    train_name="trial_0004",
                    run_dir=str(root / "runs" / "group1" / "trial_0004"),
                    params={
                        "component": "proposal-detector",
                        "model": "yolo26s.pt",
                        "epochs": 140,
                        "batch": 8,
                        "imgsz": 640,
                        "device": "0",
                    },
                    best_weights=str(root / "runs" / "group1" / "trial_0004" / "proposal-detector" / "weights" / "best.pt"),
                    last_weights=str(root / "runs" / "group1" / "trial_0004" / "proposal-detector" / "weights" / "last.pt"),
                ),
            )
            storage.write_train_record(
                paths.embedder_train_file(trial_id),
                contracts.TrainRecord(
                    task="group1",
                    train_name="trial_0004",
                    run_dir=str(root / "runs" / "group1" / "trial_0004"),
                    params={
                        "component": "icon-embedder",
                        "epochs": 160,
                        "batch": 32,
                        "imgsz": 96,
                        "device": "0",
                    },
                    best_weights=str(root / "runs" / "group1" / "trial_0004" / "icon-embedder" / "weights" / "best.pt"),
                    last_weights=str(root / "runs" / "group1" / "trial_0004" / "icon-embedder" / "weights" / "last.pt"),
                ),
            )
            storage.write_json_payload(
                paths.query_gate_file(trial_id),
                {
                    "component": "query-detector",
                    "status": "failed",
                    "metrics": {"query_strict_hit_rate": 0.81},
                    "gate": {"status": "failed", "failed_checks": ["query_exact_count_rate"]},
                    "error_file": str(query_failcases),
                    "weights": {"best": "best", "last": "last"},
                },
            )
            storage.write_json_payload(
                paths.scene_gate_file(trial_id),
                {
                    "component": "proposal-detector",
                    "status": "failed",
                    "metrics": {"proposal_recall": 0.74},
                    "gate": {"status": "failed", "failed_checks": ["proposal_object_recall"]},
                    "error_file": str(proposal_failcases),
                    "weights": {"best": "best", "last": "last"},
                },
            )
            storage.write_json_payload(
                paths.embedder_gate_file(trial_id),
                {
                    "component": "icon-embedder",
                    "status": "failed",
                    "metrics": {
                        "embedding_recall_at_1": 0.91,
                        "embedding_recall_at_3": 0.98,
                        "embedding_top1_error_scene_target_rate": 0.18,
                        "embedding_top1_error_false_positive_rate": 0.07,
                        "embedding_same_template_top1_error_rate": 0.11,
                    },
                    "gate": {"status": "failed", "failed_checks": ["embedding_recall_at_1"]},
                    "review": {"decision": "CONTINUE", "reason": "scene_target_confusion"},
                    "failure_audit": {
                        "failure_count": 3,
                        "reason_counts": {"same_template_confusion": 2, "scene_target_confusion": 1},
                        "recommended_focus": ["shift_gate_to_scene_and_business", "increase_same_template_hard_negatives"],
                    },
                    "weights": {"best": "best", "last": "last"},
                },
            )

            summary_record = contracts.ResultSummaryRecord(
                study_name="study_001",
                task="group1",
                trial_id=trial_id,
                dataset_version="v1",
                train_name="trial_0004",
                primary_metric="map50_95",
                primary_score=0.82,
                test_metrics={"map50_95": 0.82, "recall": 0.86},
                evaluation_available=True,
                evaluation_metrics={"full_sequence_hit_rate": 0.79},
                failure_count=3,
                trend="plateau",
                delta_vs_previous=0.0,
                delta_vs_best=-0.01,
                weak_classes=[],
                failure_patterns=["order_errors", "sequence_consistency"],
                recent_trials=[],
                best_trial=None,
                evidence=["summary"],
            )
            storage.write_evaluate_record(
                paths.evaluate_file(trial_id),
                contracts.EvaluateRecord(
                    available=True,
                    task="group1",
                    metrics={"full_sequence_hit_rate": 0.79, "order_error_rate": 0.12},
                    failure_count=3,
                    report_dir=str(report_dir),
                ),
            )

            record = analysis.build_trial_analysis(
                analysis.TrialAnalysisRequest(
                    paths=paths,
                    trial_id=trial_id,
                    trial_input=trial_input,
                    summary_record=summary_record,
                    sample_limit=2,
                )
            )

            self.assertEqual(record.current_params["imgsz"], 640)
            self.assertEqual(record.evaluation_failures["reason_counts"]["order_mismatch"], 2)
            self.assertEqual(len(record.evaluation_failures["examples"]), 2)
            query_diagnostic = record.component_diagnostics["query-detector"]
            self.assertEqual(query_diagnostic["current_params"]["model"], "yolo26n.pt")
            self.assertEqual(query_diagnostic["error_reason_counts"]["count_mismatch"], 2)
            proposal_diagnostic = record.component_diagnostics["proposal-detector"]
            self.assertEqual(proposal_diagnostic["current_params"]["model"], "yolo26s.pt")
            self.assertEqual(proposal_diagnostic["error_reason_counts"]["precision_fp"], 1)
            embedder_diagnostic = record.component_diagnostics["icon-embedder"]
            self.assertEqual(embedder_diagnostic["current_params"]["imgsz"], 96)
            self.assertIn("embedding_top1_error_scene_target_rate=0.180000", embedder_diagnostic["signal_summary"])
            self.assertEqual(embedder_diagnostic["review"]["reason"], "scene_target_confusion")
            self.assertEqual(embedder_diagnostic["failure_audit"]["reason_counts"]["same_template_confusion"], 2)
            self.assertEqual(embedder_diagnostic["failure_audit"]["recommended_focus"][0], "shift_gate_to_scene_and_business")


if __name__ == "__main__":
    unittest.main()
