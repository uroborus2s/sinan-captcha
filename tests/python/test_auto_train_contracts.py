from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.auto_train import contracts, storage


class AutoTrainContractsTests(unittest.TestCase):
    def test_study_record_round_trips_with_nested_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            study = contracts.StudyRecord(
                study_name="study_001",
                task="group1",
                status="running",
                mode="full_auto",
                train_root="D:/sinan-captcha-work",
                generator_workspace="D:/sinan-generator-workspace",
                judge=contracts.JudgeConfig(provider="opencode", model="gemma4"),
                budget=contracts.StudyBudget(
                    max_trials=20,
                    max_hours=36.0,
                    max_new_datasets=6,
                    max_no_improve_trials=4,
                ),
                current_trial_id="trial_0002",
                best_trial_id="trial_0001",
            )

            path = Path(tmpdir) / "study.json"
            storage.write_study_record(path, study)
            loaded = storage.read_study_record(path)

            self.assertEqual(loaded, study)

    def test_trial_records_write_json_and_jsonl_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            trial_dir = root / "trials" / "trial_0001"

            trial_input = contracts.TrialInputRecord(
                trial_id="trial_0001",
                task="group2",
                dataset_version="firstpass_v2",
                dataset_preset="firstpass",
                dataset_override={
                    "project": {"sample_count": 240},
                    "effects": {
                        "common": {
                            "scene_veil_strength": 1.25,
                            "background_blur_radius_min": 1,
                            "background_blur_radius_max": 2,
                        },
                        "slide": {
                            "gap_shadow_alpha_min": 0.16,
                            "gap_shadow_alpha_max": 0.24,
                            "gap_shadow_offset_x_min": 1,
                            "gap_shadow_offset_x_max": 2,
                            "gap_shadow_offset_y_min": 1,
                            "gap_shadow_offset_y_max": 2,
                            "tile_edge_blur_radius_min": 1,
                            "tile_edge_blur_radius_max": 2,
                        },
                    },
                },
                train_name="trial_0001",
                train_mode="from_run",
                base_run="trial_0000",
                params={
                    "model": "yolo26n.pt",
                    "epochs": 140,
                    "batch": 8,
                    "imgsz": 640,
                },
            )
            decision = contracts.DecisionRecord(
                trial_id="trial_0001",
                decision="RETUNE",
                confidence=0.82,
                reason="recall_is_bottleneck",
                next_action={
                    "dataset_action": "reuse",
                    "train_action": "from_run",
                    "base_run": "trial_0001",
                },
                evidence=["map50_95 plateau", "weak classes: icon_leaf"],
                agent=contracts.AgentRef(provider="opencode", name="judge-trial", model="gemma4"),
            )

            storage.write_trial_input_record(trial_dir / "input.json", trial_input)
            storage.write_decision_record(trial_dir / "decision.json", decision)
            storage.append_trial_history(root / "trial_history.jsonl", trial_input)
            storage.append_decision_history(root / "decisions.jsonl", decision)

            loaded_input = storage.read_trial_input_record(trial_dir / "input.json")
            loaded_decision = storage.read_decision_record(trial_dir / "decision.json")
            history = storage.read_jsonl_records(root / "trial_history.jsonl")
            decisions = storage.read_jsonl_records(root / "decisions.jsonl")

            self.assertEqual(loaded_input, trial_input)
            self.assertEqual(loaded_decision, decision)
            self.assertEqual(history[0]["trial_id"], "trial_0001")
            self.assertEqual(decisions[0]["decision"], "RETUNE")

    def test_dataset_plan_and_study_status_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dataset_plan_record = contracts.DatasetPlanRecord(
                study_name="study_001",
                task="group1",
                trial_id="trial_0003",
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
                rationale_cn="建议围绕弱类和顺序错误扩充样本。",
                evidence=["decision=REGENERATE_DATA"],
            )
            study_status_record = contracts.StudyStatusRecord(
                study_name="study_001",
                task="group1",
                status="running",
                current_trial_id="trial_0003",
                best_trial_id="trial_0002",
                latest_decision="REGENERATE_DATA",
                best_primary_score=0.84,
                budget_pressure="medium",
                summary_cn="当前应补数据再继续训练。",
                next_actions_cn=["先生成新数据版本。"],
                evidence=["budget_pressure=medium"],
            )

            storage.write_dataset_plan_record(root / "dataset_plan.json", dataset_plan_record)
            storage.write_study_status_record(root / "study_status.json", study_status_record)

            self.assertEqual(storage.read_dataset_plan_record(root / "dataset_plan.json"), dataset_plan_record)
            self.assertEqual(storage.read_study_status_record(root / "study_status.json"), study_status_record)

    def test_invalid_decision_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            contracts.DecisionRecord(
                trial_id="trial_0001",
                decision="SHIP_IT",
                confidence=0.9,
                reason="invalid",
                next_action={},
                evidence=[],
                agent=contracts.AgentRef(provider="opencode", name="judge-trial"),
            )

    def test_from_run_mode_requires_base_run(self) -> None:
        with self.assertRaises(ValueError):
            contracts.TrialInputRecord(
                trial_id="trial_0001",
                task="group1",
                dataset_version="firstpass",
                train_name="trial_0001",
                train_mode="from_run",
                base_run=None,
                params={"epochs": 100},
            )


if __name__ == "__main__":
    unittest.main()
