from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.auto_train import contracts, layout, storage, summary
from core.group2_semantics import GROUP2_LOCALIZATION_ALERT_CENTER_ERROR_PX


class AutoTrainSummaryTests(unittest.TestCase):
    def test_build_result_summary_keeps_current_metrics_recent_window_and_best_trial(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = layout.StudyPaths(
                studies_root=Path(tmpdir) / "studies",
                task="group1",
                study_name="study_001",
            )
            paths.ensure_layout()

            storage.write_result_summary_record(
                paths.result_summary_file("trial_0001"),
                contracts.ResultSummaryRecord(
                    study_name="study_001",
                    task="group1",
                    trial_id="trial_0001",
                    dataset_version="v1",
                    train_name="trial_0001",
                    primary_metric="map50_95",
                    primary_score=0.79,
                    test_metrics={"map50_95": 0.79, "recall": 0.84},
                    evaluation_available=True,
                    evaluation_metrics={"full_sequence_hit_rate": 0.70},
                    failure_count=6,
                    trend="baseline",
                    delta_vs_previous=None,
                    delta_vs_best=None,
                    weak_classes=[],
                    failure_patterns=["sequence_consistency"],
                    recent_trials=[],
                    best_trial=None,
                    evidence=["baseline trial"],
                ),
            )
            storage.write_result_summary_record(
                paths.result_summary_file("trial_0002"),
                contracts.ResultSummaryRecord(
                    study_name="study_001",
                    task="group1",
                    trial_id="trial_0002",
                    dataset_version="v2",
                    train_name="trial_0002",
                    primary_metric="map50_95",
                    primary_score=0.84,
                    test_metrics={"map50_95": 0.84, "recall": 0.88},
                    evaluation_available=True,
                    evaluation_metrics={"full_sequence_hit_rate": 0.81},
                    failure_count=3,
                    trend="improving",
                    delta_vs_previous=0.05,
                    delta_vs_best=0.0,
                    weak_classes=[],
                    failure_patterns=[],
                    recent_trials=[],
                    best_trial=None,
                    evidence=["new best"],
                ),
            )
            storage.write_result_summary_record(
                paths.result_summary_file("trial_0003"),
                contracts.ResultSummaryRecord(
                    study_name="study_001",
                    task="group1",
                    trial_id="trial_0003",
                    dataset_version="v3",
                    train_name="trial_0003",
                    primary_metric="map50_95",
                    primary_score=0.81,
                    test_metrics={"map50_95": 0.81, "recall": 0.86},
                    evaluation_available=True,
                    evaluation_metrics={"full_sequence_hit_rate": 0.76},
                    failure_count=4,
                    trend="declining",
                    delta_vs_previous=-0.03,
                    delta_vs_best=-0.03,
                    weak_classes=[],
                    failure_patterns=["order_errors"],
                    recent_trials=[],
                    best_trial=None,
                    evidence=["order issue"],
                ),
            )
            storage.write_best_trial_record(
                paths.best_trial_file,
                contracts.BestTrialRecord(
                    study_name="study_001",
                    task="group1",
                    trial_id="trial_0002",
                    primary_metric="map50_95",
                    primary_score=0.84,
                    dataset_version="v2",
                    train_name="trial_0002",
                    metrics={"map50_95": 0.84, "recall": 0.88},
                    decision="PROMOTE_BRANCH",
                ),
            )

            record = summary.build_result_summary(
                summary.ResultSummaryRequest(
                    study_name="study_001",
                    paths=paths,
                    trial_id="trial_0004",
                    dataset_version="v4",
                    train_name="trial_0004",
                    primary_metric="map50_95",
                    test_record=contracts.TestRecord(
                        task="group1",
                        dataset_version="v4",
                        train_name="trial_0004",
                        metrics={
                            "precision": 0.91,
                            "recall": 0.89,
                            "map50": 0.97,
                            "map50_95": 0.83,
                            "per_class_metrics": {
                                "icon_camera": {"recall": 0.68, "map50_95": 0.73},
                                "icon_leaf": {"recall": 0.77},
                                "icon_gift": {"recall": 0.91, "map50_95": 0.84},
                            },
                        },
                        predict_output_dir="D:/reports/group1/predict_trial_0004",
                        val_output_dir="D:/reports/group1/val_trial_0004",
                        report_dir="D:/reports/group1/test_trial_0004",
                    ),
                    evaluate_record=contracts.EvaluateRecord(
                        available=True,
                        task="group1",
                        metrics={
                            "single_target_hit_rate": 0.92,
                            "full_sequence_hit_rate": 0.78,
                            "mean_center_error_px": 7.4,
                            "order_error_rate": 0.11,
                        },
                        failure_count=5,
                        report_dir="D:/reports/group1/eval_trial_0004",
                    ),
                    recent_window=2,
                    min_delta=0.005,
                )
            )

            self.assertEqual(record.primary_score, 0.83)
            self.assertEqual(record.trend, "improving")
            self.assertAlmostEqual(record.delta_vs_previous or 0.0, 0.02, places=6)
            self.assertAlmostEqual(record.delta_vs_best or 0.0, -0.01, places=6)
            self.assertEqual([item.trial_id for item in record.recent_trials], ["trial_0003", "trial_0002"])
            self.assertEqual(record.best_trial.trial_id if record.best_trial else None, "trial_0002")
            self.assertEqual(record.weak_classes, ["icon_camera", "icon_leaf"])
            self.assertIn("order_errors", record.failure_patterns)
            self.assertIn("sequence_consistency", record.failure_patterns)

    def test_build_result_summary_handles_missing_primary_score_when_best_trial_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = layout.StudyPaths(
                studies_root=Path(tmpdir) / "studies",
                task="group1",
                study_name="study_001",
            )
            paths.ensure_layout()

            storage.write_best_trial_record(
                paths.best_trial_file,
                contracts.BestTrialRecord(
                    study_name="study_001",
                    task="group1",
                    trial_id="trial_0002",
                    primary_metric="map50_95",
                    primary_score=0.84,
                    dataset_version="v2",
                    train_name="trial_0002",
                    metrics={"map50_95": 0.84, "recall": 0.88},
                    decision="PROMOTE_BRANCH",
                ),
            )

            record = summary.build_result_summary(
                summary.ResultSummaryRequest(
                    study_name="study_001",
                    paths=paths,
                    trial_id="trial_0003",
                    dataset_version="v3",
                    train_name="trial_0003",
                    primary_metric="map50_95",
                    test_record=contracts.TestRecord(
                        task="group1",
                        dataset_version="v3",
                        train_name="trial_0003",
                        metrics={"precision": 0.91, "recall": 0.89},
                        predict_output_dir="D:/reports/group1/predict_trial_0003",
                        val_output_dir="D:/reports/group1/val_trial_0003",
                        report_dir="D:/reports/group1/test_trial_0003",
                    ),
                    evaluate_record=contracts.EvaluateRecord(
                        available=True,
                        task="group1",
                        metrics={"full_sequence_hit_rate": 0.83, "order_error_rate": 0.03},
                        failure_count=1,
                        report_dir="D:/reports/group1/eval_trial_0003",
                    ),
                )
            )

            self.assertIsNone(record.primary_score)
            self.assertIsNone(record.delta_vs_best)
            self.assertNotIn("delta_vs_best=", "\n".join(record.evidence))
            self.assertEqual(record.best_trial.trial_id if record.best_trial else None, "trial_0002")

    def test_build_result_summary_for_group2_extracts_failure_patterns_without_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = layout.StudyPaths(
                studies_root=Path(tmpdir) / "studies",
                task="group2",
                study_name="study_001",
            )
            paths.ensure_layout()

            record = summary.build_result_summary(
                summary.ResultSummaryRequest(
                    study_name="study_001",
                    paths=paths,
                    trial_id="trial_0001",
                    dataset_version="v1",
                    train_name="trial_0001",
                    primary_metric="point_hit_rate",
                    test_record=contracts.TestRecord(
                        task="group2",
                        dataset_version="v1",
                        train_name="trial_0001",
                        metrics={"precision": 0.9, "recall": 0.86, "map50_95": 0.77},
                        predict_output_dir="D:/reports/group2/predict_trial_0001",
                        val_output_dir="D:/reports/group2/val_trial_0001",
                        report_dir="D:/reports/group2/test_trial_0001",
                    ),
                    evaluate_record=contracts.EvaluateRecord(
                        available=True,
                        task="group2",
                        metrics={
                            "point_hit_rate": 0.86,
                            "mean_center_error_px": 15.2,
                            "mean_iou": 0.74,
                        },
                        failure_count=7,
                        report_dir="D:/reports/group2/eval_trial_0001",
                    ),
                )
            )

            self.assertEqual(record.trend, "baseline")
            self.assertEqual(record.recent_trials, [])
            self.assertEqual(record.weak_classes, [])
            self.assertIn("point_hits", record.failure_patterns)
            self.assertIn("center_offset", record.failure_patterns)
            self.assertIn("low_iou", record.failure_patterns)

    def test_build_result_summary_for_group2_does_not_flag_center_offset_at_exact_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = layout.StudyPaths(
                studies_root=Path(tmpdir) / "studies",
                task="group2",
                study_name="study_001",
            )
            paths.ensure_layout()

            record = summary.build_result_summary(
                summary.ResultSummaryRequest(
                    study_name="study_001",
                    paths=paths,
                    trial_id="trial_0001",
                    dataset_version="v1",
                    train_name="trial_0001",
                    primary_metric="point_hit_rate",
                    test_record=contracts.TestRecord(
                        task="group2",
                        dataset_version="v1",
                        train_name="trial_0001",
                        metrics={"precision": 0.9, "recall": 0.86, "map50_95": 0.77},
                        predict_output_dir="D:/reports/group2/predict_trial_0001",
                        val_output_dir="D:/reports/group2/val_trial_0001",
                        report_dir="D:/reports/group2/test_trial_0001",
                    ),
                    evaluate_record=contracts.EvaluateRecord(
                        available=True,
                        task="group2",
                        metrics={
                            "point_hit_rate": 0.91,
                            "mean_center_error_px": GROUP2_LOCALIZATION_ALERT_CENTER_ERROR_PX,
                            "mean_iou": 0.81,
                        },
                        failure_count=1,
                        report_dir="D:/reports/group2/eval_trial_0001",
                    ),
                )
            )

            self.assertNotIn("center_offset", record.failure_patterns)

    def test_result_summary_round_trips_via_storage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "result_summary.json"
            record = contracts.ResultSummaryRecord(
                study_name="study_001",
                task="group1",
                trial_id="trial_0005",
                dataset_version="v5",
                train_name="trial_0005",
                primary_metric="map50_95",
                primary_score=0.85,
                test_metrics={"map50_95": 0.85},
                evaluation_available=False,
                evaluation_metrics={},
                failure_count=None,
                trend="baseline",
                delta_vs_previous=None,
                delta_vs_best=None,
                weak_classes=[],
                failure_patterns=[],
                recent_trials=[
                    contracts.ResultSummarySnapshot(
                        trial_id="trial_0004",
                        dataset_version="v4",
                        train_name="trial_0004",
                        primary_score=0.83,
                        metrics={"map50_95": 0.83},
                    )
                ],
                best_trial=contracts.ResultSummarySnapshot(
                    trial_id="trial_0005",
                    dataset_version="v5",
                    train_name="trial_0005",
                    primary_score=0.85,
                    metrics={"map50_95": 0.85},
                ),
                evidence=["latest best"],
            )

            storage.write_result_summary_record(path, record)
            loaded = storage.read_result_summary_record(path)

            self.assertEqual(loaded, record)


if __name__ == "__main__":
    unittest.main()
