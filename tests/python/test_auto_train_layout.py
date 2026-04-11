from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from auto_train import contracts, layout, recovery, storage


class AutoTrainLayoutTests(unittest.TestCase):
    def test_study_layout_freezes_group_scoped_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            studies_root = Path(tmpdir) / "studies"

            group1_paths = layout.StudyPaths(studies_root=studies_root, task="group1", study_name="study_001")
            group2_paths = layout.StudyPaths(studies_root=studies_root, task="group2", study_name="study_001")

            self.assertEqual(group1_paths.study_root, studies_root / "group1" / "study_001")
            self.assertEqual(group1_paths.study_file, studies_root / "group1" / "study_001" / "study.json")
            self.assertEqual(
                group1_paths.leaderboard_file,
                studies_root / "group1" / "study_001" / "leaderboard.json",
            )
            self.assertEqual(group1_paths.summary_file, studies_root / "group1" / "study_001" / "summary.md")
            self.assertEqual(group1_paths.best_trial_file, studies_root / "group1" / "study_001" / "best_trial.json")
            self.assertEqual(group1_paths.trial_dir("trial_0001"), studies_root / "group1" / "study_001" / "trials" / "trial_0001")
            self.assertNotEqual(group1_paths.study_root, group2_paths.study_root)

    def test_trial_identifier_format_is_stable(self) -> None:
        self.assertEqual(layout.format_trial_id(1), "trial_0001")
        self.assertEqual(layout.format_trial_id(27), "trial_0027")
        self.assertEqual(layout.parse_trial_id("trial_0042"), 42)
        self.assertEqual(
            layout.format_generated_dataset_version("study_001", "trial_0002"),
            "study_001_trial_0002",
        )

        with self.assertRaises(ValueError):
            layout.parse_trial_id("trial_42")

    def test_leaderboard_round_trips_sorted_entries_and_best_trial(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = layout.StudyPaths(
                studies_root=Path(tmpdir) / "studies",
                task="group1",
                study_name="study_001",
            )
            leaderboard = contracts.LeaderboardRecord(
                study_name="study_001",
                task="group1",
                primary_metric="map50_95",
                entries=[
                    contracts.LeaderboardEntry(
                        trial_id="trial_0002",
                        dataset_version="v2",
                        train_name="trial_0002",
                        primary_score=0.81,
                        metrics={"map50_95": 0.81, "recall": 0.86},
                    ),
                    contracts.LeaderboardEntry(
                        trial_id="trial_0001",
                        dataset_version="v1",
                        train_name="trial_0001",
                        primary_score=0.84,
                        metrics={"map50_95": 0.84, "recall": 0.88},
                    ),
                ],
            )

            storage.write_leaderboard_record(paths.leaderboard_file, leaderboard)
            storage.write_best_trial_record(
                paths.best_trial_file,
                contracts.BestTrialRecord.from_leaderboard_entry(
                    study_name="study_001",
                    task="group1",
                    primary_metric="map50_95",
                    entry=leaderboard.entries[0],
                ),
            )

            loaded = storage.read_leaderboard_record(paths.leaderboard_file)
            best = storage.read_best_trial_record(paths.best_trial_file)

            self.assertEqual([entry.trial_id for entry in loaded.entries], ["trial_0001", "trial_0002"])
            self.assertEqual(best.trial_id, "trial_0001")
            self.assertEqual(best.primary_score, 0.84)

    def test_leaderboard_prefers_composite_ranking_score_over_primary_score(self) -> None:
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
                    metrics={"point_hit_rate": 1.0, "ranking_score": 0.98},
                ),
                contracts.LeaderboardEntry(
                    trial_id="trial_0002",
                    dataset_version="study_001_trial_0002",
                    train_name="trial_0002",
                    primary_score=0.99,
                    metrics={"point_hit_rate": 0.99, "ranking_score": 1.06},
                ),
            ],
        )

        self.assertEqual([entry.trial_id for entry in leaderboard.entries], ["trial_0002", "trial_0001"])
        self.assertEqual(leaderboard.best_entry.trial_id if leaderboard.best_entry is not None else None, "trial_0002")


class AutoTrainRecoveryTests(unittest.TestCase):
    def test_recovery_plan_uses_first_missing_artifact_as_rerun_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = layout.StudyPaths(
                studies_root=Path(tmpdir) / "studies",
                task="group1",
                study_name="study_001",
            )
            trial_dir = paths.trial_dir("trial_0001")
            trial_dir.mkdir(parents=True)

            storage.write_trial_input_record(
                paths.input_file("trial_0001"),
                contracts.TrialInputRecord(
                    trial_id="trial_0001",
                    task="group1",
                    dataset_version="firstpass",
                    train_name="trial_0001",
                    train_mode="fresh",
                    base_run=None,
                    params={"epochs": 100},
                ),
            )
            storage.write_train_record(
                paths.train_file("trial_0001"),
                contracts.TrainRecord(
                    task="group1",
                    train_name="trial_0001",
                    run_dir="D:/runs/group1/trial_0001",
                    params={"epochs": 100},
                ),
            )

            plan = recovery.build_recovery_plan(trial_dir)

            self.assertEqual(plan.resume_stage, "BUILD_DATASET")
            self.assertEqual(plan.last_completed_stage, "PLAN")
            self.assertEqual(plan.missing_artifacts, ["dataset.json"])
            self.assertEqual(plan.completed_stages, ("PLAN",))

    def test_recovery_plan_marks_trial_complete_after_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = layout.StudyPaths(
                studies_root=Path(tmpdir) / "studies",
                task="group2",
                study_name="study_001",
            )
            trial_id = "trial_0003"
            trial_dir = paths.trial_dir(trial_id)
            trial_dir.mkdir(parents=True)

            storage.write_trial_input_record(
                paths.input_file(trial_id),
                contracts.TrialInputRecord(
                    trial_id=trial_id,
                    task="group2",
                    dataset_version="v3",
                    train_name=trial_id,
                    train_mode="resume",
                    base_run="trial_0002",
                    params={"epochs": 140},
                ),
            )
            storage.write_dataset_record(
                paths.dataset_file(trial_id),
                contracts.DatasetRecord(
                    task="group2",
                    dataset_version="v3",
                    dataset_root="D:/datasets/group2/v3",
                ),
            )
            storage.write_train_record(
                paths.train_file(trial_id),
                contracts.TrainRecord(
                    task="group2",
                    train_name=trial_id,
                    run_dir="D:/runs/group2/trial_0003",
                    params={"epochs": 140},
                ),
            )
            storage.write_test_record(
                paths.test_file(trial_id),
                contracts.TestRecord(
                    task="group2",
                    dataset_version="v3",
                    train_name=trial_id,
                    metrics={"map50_95": 0.79},
                    predict_output_dir="D:/reports/group2/predict_trial_0003",
                    val_output_dir="D:/reports/group2/val_trial_0003",
                    report_dir="D:/reports/group2/test_trial_0003",
                ),
            )
            storage.write_evaluate_record(
                paths.evaluate_file(trial_id),
                contracts.EvaluateRecord(
                    available=True,
                    task="group2",
                    metrics={"point_hit_rate": 0.91},
                    failure_count=2,
                    report_dir="D:/reports/group2/eval_trial_0003",
                ),
            )
            paths.result_summary_file(trial_id).write_text("{}", encoding="utf-8")
            storage.write_decision_record(
                paths.decision_file(trial_id),
                contracts.DecisionRecord(
                    trial_id=trial_id,
                    decision="PROMOTE_BRANCH",
                    confidence=0.93,
                    reason="targets_met",
                    next_action={"dataset_action": "freeze"},
                    evidence=["point_hit_rate >= 0.91"],
                    agent=contracts.AgentRef(provider="opencode", name="judge-trial"),
                ),
            )

            plan = recovery.build_recovery_plan(trial_dir)

            self.assertEqual(plan.resume_stage, "NEXT_ACTION")
            self.assertEqual(plan.last_completed_stage, "NEXT_ACTION")
            self.assertEqual(plan.missing_artifacts, [])
            self.assertTrue(plan.trial_complete)


if __name__ == "__main__":
    unittest.main()
