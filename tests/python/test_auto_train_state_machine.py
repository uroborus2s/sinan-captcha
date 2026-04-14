from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from auto_train import contracts, state_machine, stop_rules, storage


def _group1_gate_payload(
    *,
    component: str,
    dataset_config: str,
    best_weights: str,
    last_weights: str,
    imgsz: int = 640,
    device: str = "0",
    status: str = "passed",
) -> dict[str, object]:
    return {
        "gate_version": 2,
        "component": component,
        "status": status,
        "dataset_config": dataset_config,
        "weights": {
            "best": best_weights,
            "last": last_weights,
        },
        "imgsz": imgsz,
        "device": device,
        "gate": {
            "status": status,
            "failed_checks": [],
        },
        "summary_path": "D:/runs/group1/trial_0001/summary.json",
    }


class AutoTrainStateMachineTests(unittest.TestCase):
    def test_stage_sequence_is_fixed_and_stop_is_terminal(self) -> None:
        self.assertEqual(state_machine.next_stage("PLAN"), "BUILD_DATASET")
        self.assertEqual(state_machine.next_stage("SUMMARIZE"), "JUDGE")
        self.assertEqual(state_machine.next_stage("NEXT_ACTION"), "STOP")
        self.assertEqual(state_machine.next_stage("STOP"), "STOP")
        self.assertTrue(state_machine.is_terminal_stage("STOP"))

    def test_group1_stage_sequence_includes_component_gates(self) -> None:
        self.assertEqual(state_machine.next_stage("BUILD_DATASET", task="group1"), "TRAIN_QUERY")
        self.assertEqual(state_machine.next_stage("TRAIN_QUERY", task="group1"), "QUERY_GATE")
        self.assertEqual(state_machine.next_stage("QUERY_GATE", task="group1"), "TRAIN_SCENE")
        self.assertEqual(state_machine.next_stage("TRAIN_SCENE", task="group1"), "SCENE_GATE")
        self.assertEqual(state_machine.next_stage("SCENE_GATE", task="group1"), "TRAIN_EMBEDDER_BASE")
        self.assertEqual(state_machine.next_stage("TRAIN_EMBEDDER_BASE", task="group1"), "EMBEDDER_GATE")
        self.assertEqual(state_machine.next_stage("EMBEDDER_GATE", task="group1"), "BUILD_EMBEDDER_HARDSET")
        self.assertEqual(state_machine.next_stage("BUILD_EMBEDDER_HARDSET", task="group1"), "TRAIN_EMBEDDER_HARD")
        self.assertEqual(state_machine.next_stage("TRAIN_EMBEDDER_HARD", task="group1"), "CALIBRATE_MATCHER")
        self.assertEqual(state_machine.next_stage("CALIBRATE_MATCHER", task="group1"), "OFFLINE_EVAL")
        self.assertEqual(state_machine.next_stage("OFFLINE_EVAL", task="group1"), "BUSINESS_EVAL")
        self.assertEqual(state_machine.next_stage("BUSINESS_EVAL", task="group1"), "SUMMARIZE")

    def test_resume_stage_is_plan_when_trial_dir_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            trial_dir = Path(tmpdir) / "trials" / "trial_0001"
            trial_dir.mkdir(parents=True)

            stage = state_machine.infer_resume_stage(trial_dir)

            self.assertEqual(stage, "PLAN")

    def test_resume_stage_advances_with_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            trial_dir = root / "trials" / "trial_0001"
            trial_dir.mkdir(parents=True)

            storage.write_trial_input_record(
                trial_dir / "input.json",
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
            self.assertEqual(state_machine.infer_resume_stage(trial_dir), "BUILD_DATASET")

            storage.write_dataset_record(
                trial_dir / "dataset.json",
                contracts.DatasetRecord(
                    task="group1",
                    dataset_version="firstpass",
                    dataset_root="D:/datasets/group1/firstpass",
                ),
            )
            self.assertEqual(state_machine.infer_resume_stage(trial_dir), "TRAIN")

            storage.write_train_record(
                trial_dir / "train.json",
                contracts.TrainRecord(
                    task="group1",
                    train_name="trial_0001",
                    run_dir="D:/runs/group1/trial_0001",
                    params={"epochs": 100},
                ),
            )
            self.assertEqual(state_machine.infer_resume_stage(trial_dir), "TEST")

            storage.write_test_record(
                trial_dir / "test.json",
                contracts.TestRecord(
                    task="group1",
                    dataset_version="firstpass",
                    train_name="trial_0001",
                    metrics={"map50_95": 0.81},
                    predict_output_dir="D:/reports/group1/predict_trial_0001",
                    val_output_dir="D:/reports/group1/val_trial_0001",
                    report_dir="D:/reports/group1/test_trial_0001",
                ),
            )
            self.assertEqual(state_machine.infer_resume_stage(trial_dir), "EVALUATE")

            storage.write_evaluate_record(
                trial_dir / "evaluate.json",
                contracts.EvaluateRecord(
                    available=True,
                    task="group1",
                    metrics={"full_sequence_hit_rate": 0.79},
                    failure_count=3,
                    report_dir="D:/reports/group1/eval_trial_0001",
                ),
            )
            self.assertEqual(state_machine.infer_resume_stage(trial_dir), "SUMMARIZE")

            (trial_dir / "result_summary.json").write_text("{}", encoding="utf-8")
            self.assertEqual(state_machine.infer_resume_stage(trial_dir), "JUDGE")

            storage.write_decision_record(
                trial_dir / "decision.json",
                contracts.DecisionRecord(
                    trial_id="trial_0001",
                    decision="RETUNE",
                    confidence=0.8,
                    reason="plateau",
                    next_action={"dataset_action": "reuse"},
                    evidence=["plateau"],
                    agent=contracts.AgentRef(provider="opencode", name="judge-trial"),
                ),
            )
            self.assertEqual(state_machine.infer_resume_stage(trial_dir), "NEXT_ACTION")

    def test_group1_resume_stage_advances_with_component_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            trial_dir = root / "trials" / "trial_0001"
            trial_dir.mkdir(parents=True)
            dataset_config = "D:/datasets/group1/v1/dataset.json"
            query_best = "D:/runs/group1/trial_0001/query-detector/weights/best.pt"
            query_last = "D:/runs/group1/trial_0001/query-detector/weights/last.pt"
            scene_best = "D:/runs/group1/trial_0001/proposal-detector/weights/best.pt"
            scene_last = "D:/runs/group1/trial_0001/proposal-detector/weights/last.pt"

            storage.write_trial_input_record(
                trial_dir / "input.json",
                contracts.TrialInputRecord(
                    trial_id="trial_0001",
                    task="group1",
                    dataset_version="v1",
                    train_name="trial_0001",
                    train_mode="fresh",
                    base_run=None,
                    params={"epochs": 100},
                ),
            )
            self.assertEqual(state_machine.infer_resume_stage(trial_dir, task="group1"), "BUILD_DATASET")

            storage.write_dataset_record(
                trial_dir / "dataset.json",
                contracts.DatasetRecord(task="group1", dataset_version="v1", dataset_root="D:/datasets/group1/v1"),
            )
            self.assertEqual(state_machine.infer_resume_stage(trial_dir, task="group1"), "TRAIN_QUERY")

            storage.write_train_record(
                trial_dir / "query_train.json",
                contracts.TrainRecord(
                    task="group1",
                    train_name="trial_0001",
                    run_dir="D:/runs/group1/trial_0001",
                    params={
                        "component": "query-detector",
                        "dataset_config": dataset_config,
                        "imgsz": 640,
                        "device": "0",
                    },
                    best_weights=query_best,
                    last_weights=query_last,
                ),
            )
            self.assertEqual(state_machine.infer_resume_stage(trial_dir, task="group1"), "QUERY_GATE")

            storage.write_json_payload(
                trial_dir / "query_gate.json",
                _group1_gate_payload(
                    component="query-detector",
                    dataset_config=dataset_config,
                    best_weights=query_best,
                    last_weights=query_last,
                ),
            )
            self.assertEqual(state_machine.infer_resume_stage(trial_dir, task="group1"), "TRAIN_SCENE")

            storage.write_train_record(
                trial_dir / "scene_train.json",
                contracts.TrainRecord(
                    task="group1",
                    train_name="trial_0001",
                    run_dir="D:/runs/group1/trial_0001",
                    params={
                        "component": "proposal-detector",
                        "dataset_config": dataset_config,
                        "imgsz": 640,
                        "device": "0",
                    },
                    best_weights=scene_best,
                    last_weights=scene_last,
                ),
            )
            self.assertEqual(state_machine.infer_resume_stage(trial_dir, task="group1"), "SCENE_GATE")

            storage.write_json_payload(
                trial_dir / "scene_gate.json",
                _group1_gate_payload(
                    component="proposal-detector",
                    dataset_config=dataset_config,
                    best_weights=scene_best,
                    last_weights=scene_last,
                ),
            )
            self.assertEqual(state_machine.infer_resume_stage(trial_dir, task="group1"), "TRAIN_EMBEDDER_BASE")

            storage.write_train_record(
                trial_dir / "embedder_train.json",
                contracts.TrainRecord(
                    task="group1",
                    train_name="trial_0001",
                    run_dir="D:/runs/group1/trial_0001",
                    params={
                        "component": "icon-embedder",
                        "dataset_config": dataset_config,
                        "imgsz": 64,
                        "device": "0",
                    },
                    best_weights="D:/runs/group1/trial_0001/icon-embedder/weights/best.pt",
                    last_weights="D:/runs/group1/trial_0001/icon-embedder/weights/last.pt",
                ),
            )
            self.assertEqual(state_machine.infer_resume_stage(trial_dir, task="group1"), "EMBEDDER_GATE")

            storage.write_json_payload(
                trial_dir / "embedder_gate.json",
                _group1_gate_payload(
                    component="icon-embedder",
                    dataset_config=dataset_config,
                    best_weights="D:/runs/group1/trial_0001/icon-embedder/weights/best.pt",
                    last_weights="D:/runs/group1/trial_0001/icon-embedder/weights/last.pt",
                    imgsz=64,
                ),
            )
            self.assertEqual(state_machine.infer_resume_stage(trial_dir, task="group1"), "BUILD_EMBEDDER_HARDSET")

            storage.write_json_payload(trial_dir / "embedder_hardset.json", {"status": "ready"})
            self.assertEqual(state_machine.infer_resume_stage(trial_dir, task="group1"), "TRAIN_EMBEDDER_HARD")

            storage.write_train_record(
                trial_dir / "embedder_hard_train.json",
                contracts.TrainRecord(task="group1", train_name="trial_0001", run_dir="D:/runs/group1/trial_0001", params={"component": "icon-embedder"}),
            )
            self.assertEqual(state_machine.infer_resume_stage(trial_dir, task="group1"), "CALIBRATE_MATCHER")

            storage.write_json_payload(trial_dir / "matcher_config.json", {"status": "ready"})
            self.assertEqual(state_machine.infer_resume_stage(trial_dir, task="group1"), "OFFLINE_EVAL")

            storage.write_json_payload(trial_dir / "offline_eval.json", {"status": "ready"})
            self.assertEqual(state_machine.infer_resume_stage(trial_dir, task="group1"), "BUSINESS_EVAL")

            storage.write_json_payload(trial_dir / "business_stage.json", {"status": "skipped"})
            self.assertEqual(state_machine.infer_resume_stage(trial_dir, task="group1"), "SUMMARIZE")

    def test_group1_resume_stage_rewinds_to_scene_gate_when_gate_artifact_is_legacy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            trial_dir = root / "trials" / "trial_0001"
            trial_dir.mkdir(parents=True)
            dataset_config = "D:/datasets/group1/v1/dataset.json"

            storage.write_trial_input_record(
                trial_dir / "input.json",
                contracts.TrialInputRecord(
                    trial_id="trial_0001",
                    task="group1",
                    dataset_version="v1",
                    train_name="trial_0001",
                    train_mode="fresh",
                    base_run=None,
                    params={"epochs": 100},
                ),
            )
            storage.write_dataset_record(
                trial_dir / "dataset.json",
                contracts.DatasetRecord(task="group1", dataset_version="v1", dataset_root="D:/datasets/group1/v1"),
            )
            storage.write_train_record(
                trial_dir / "query_train.json",
                contracts.TrainRecord(
                    task="group1",
                    train_name="trial_0001",
                    run_dir="D:/runs/group1/trial_0001",
                    params={
                        "component": "query-detector",
                        "dataset_config": dataset_config,
                        "imgsz": 640,
                        "device": "0",
                    },
                    best_weights="D:/runs/group1/trial_0001/query-detector/weights/best.pt",
                    last_weights="D:/runs/group1/trial_0001/query-detector/weights/last.pt",
                ),
            )
            storage.write_json_payload(
                trial_dir / "query_gate.json",
                _group1_gate_payload(
                    component="query-detector",
                    dataset_config=dataset_config,
                    best_weights="D:/runs/group1/trial_0001/query-detector/weights/best.pt",
                    last_weights="D:/runs/group1/trial_0001/query-detector/weights/last.pt",
                ),
            )
            storage.write_train_record(
                trial_dir / "scene_train.json",
                contracts.TrainRecord(
                    task="group1",
                    train_name="trial_0001",
                    run_dir="D:/runs/group1/trial_0001",
                    params={
                        "component": "proposal-detector",
                        "dataset_config": dataset_config,
                        "imgsz": 640,
                        "device": "0",
                    },
                    best_weights="D:/runs/group1/trial_0001/proposal-detector/weights/best.pt",
                    last_weights="D:/runs/group1/trial_0001/proposal-detector/weights/last.pt",
                ),
            )
            storage.write_json_payload(
                trial_dir / "scene_gate.json",
                {
                    "trial_id": "trial_0001",
                    "component": "proposal-detector",
                    "status": "passed",
                },
            )

            self.assertEqual(state_machine.infer_resume_stage(trial_dir, task="group1"), "SCENE_GATE")

    def test_stop_file_forces_stop_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            trial_dir = Path(tmpdir) / "trials" / "trial_0001"
            trial_dir.mkdir(parents=True)
            stop_file = trial_dir.parent.parent / "STOP"
            stop_file.write_text("stop", encoding="utf-8")

            stage = state_machine.infer_resume_stage(trial_dir, stop_file=stop_file)

            self.assertEqual(stage, "STOP")


class AutoTrainStopRulesTests(unittest.TestCase):
    def test_stops_when_budget_max_trials_is_reached(self) -> None:
        policy = stop_rules.StopPolicy(max_trials=3, max_hours=48.0)
        snapshot = stop_rules.StopSnapshot(
            completed_trials=3,
            elapsed_hours=12.0,
            recent_primary_scores=[0.80, 0.81, 0.82],
        )

        result = stop_rules.evaluate_stop(policy, snapshot)

        self.assertTrue(result.should_stop)
        self.assertEqual(result.reason, "max_trials_reached")

    def test_stops_when_stop_file_exists(self) -> None:
        policy = stop_rules.StopPolicy(max_trials=10, max_hours=48.0)
        snapshot = stop_rules.StopSnapshot(
            completed_trials=1,
            elapsed_hours=1.0,
            recent_primary_scores=[0.80],
            stop_file_present=True,
        )

        result = stop_rules.evaluate_stop(policy, snapshot)

        self.assertTrue(result.should_stop)
        self.assertEqual(result.reason, "stop_file_detected")

    def test_stops_when_plateau_window_has_no_meaningful_improvement(self) -> None:
        policy = stop_rules.StopPolicy(
            max_trials=10,
            max_hours=48.0,
            plateau_window=3,
            min_delta=0.005,
        )
        snapshot = stop_rules.StopSnapshot(
            completed_trials=4,
            elapsed_hours=5.0,
            recent_primary_scores=[0.800, 0.802, 0.803],
        )

        result = stop_rules.evaluate_stop(policy, snapshot)

        self.assertTrue(result.should_stop)
        self.assertEqual(result.reason, "plateau_detected")

    def test_continues_when_thresholds_are_not_hit(self) -> None:
        policy = stop_rules.StopPolicy(
            max_trials=10,
            max_hours=48.0,
            plateau_window=3,
            min_delta=0.005,
        )
        snapshot = stop_rules.StopSnapshot(
            completed_trials=2,
            elapsed_hours=3.0,
            recent_primary_scores=[0.80, 0.82, 0.85],
            no_improve_trials=1,
        )

        result = stop_rules.evaluate_stop(policy, snapshot)

        self.assertFalse(result.should_stop)
        self.assertEqual(result.reason, "continue")

    def test_stops_when_new_dataset_budget_is_reached_for_pending_regeneration(self) -> None:
        policy = stop_rules.StopPolicy(
            max_trials=10,
            max_hours=48.0,
            max_new_datasets=1,
        )
        snapshot = stop_rules.StopSnapshot(
            completed_trials=2,
            elapsed_hours=3.0,
            recent_primary_scores=[0.8, 0.82],
            new_datasets_used=1,
            pending_new_dataset=True,
        )

        result = stop_rules.evaluate_stop(policy, snapshot)

        self.assertTrue(result.should_stop)
        self.assertEqual(result.reason, "max_new_datasets_reached")


if __name__ == "__main__":
    unittest.main()
