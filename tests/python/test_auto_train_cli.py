from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.auto_train import cli, contracts, storage


class AutoTrainCliTests(unittest.TestCase):
    def test_run_command_uses_updated_business_eval_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            business_cases = root / "business-cases"
            for path in (train_root, generator_workspace, business_cases):
                path.mkdir(parents=True, exist_ok=True)

            captured_request = None

            class FakeController:
                max_steps = None

                def __init__(self, *, request: object) -> None:
                    nonlocal captured_request
                    captured_request = request
                    self.paths = type(
                        "Paths",
                        (),
                        {
                            "study_status_file": root / "studies" / "group2" / "study_001" / "study_status.json",
                        },
                    )()

                def run(self, *, max_steps: int) -> object:
                    type(self).max_steps = max_steps
                    self.paths.study_status_file.parent.mkdir(parents=True, exist_ok=True)
                    storage.write_study_status_record(
                        self.paths.study_status_file,
                        contracts.StudyStatusRecord(
                            study_name="study_001",
                            task="group2",
                            status="completed",
                            current_trial_id="trial_0001",
                            best_trial_id="trial_0001",
                            latest_decision="PROMOTE_BRANCH",
                            best_primary_score=1.0,
                            budget_pressure="low",
                            summary_cn="当前候选已达到商用门。",
                            next_actions_cn=["停止自动训练并固化报告。"],
                            evidence=["commercial_ready=true"],
                            business_success_rate=0.98,
                            business_success_threshold=0.98,
                            commercial_ready=True,
                            latest_gate_status="passed",
                            final_reason="commercial_gate_passed",
                            final_detail="0.9800/0.9800",
                        ),
                    )
                    return type(
                        "Result",
                        (),
                        {
                            "executed": [],
                            "final_stage": "STOP",
                        },
                    )()

            with patch("core.auto_train.cli.controller.AutoTrainController", FakeController):
                code = cli.main(
                    [
                        "run",
                        "group2",
                        "--study-name",
                        "study_001",
                        "--train-root",
                        str(train_root),
                        "--generator-workspace",
                        str(generator_workspace),
                        "--business-eval-dir",
                        str(business_cases),
                    ]
                )

            self.assertEqual(code, 0)
            assert captured_request is not None
            self.assertTrue(captured_request.goal_only_stop)
            self.assertEqual(captured_request.business_eval_dir, business_cases)
            self.assertEqual(captured_request.business_eval_success_threshold, 0.95)
            self.assertEqual(captured_request.business_eval_min_cases, 50)
            self.assertEqual(captured_request.business_eval_sample_size, 50)
            self.assertEqual(captured_request.point_tolerance_px, 5)
            self.assertEqual(FakeController.max_steps, 0)

    def test_run_command_forwards_explicit_goal_only_stop_without_business_eval(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            for path in (train_root, generator_workspace):
                path.mkdir(parents=True, exist_ok=True)

            captured_request = None

            class FakeController:
                max_steps = None

                def __init__(self, *, request: object) -> None:
                    nonlocal captured_request
                    captured_request = request
                    self.paths = type("Paths", (), {"study_status_file": root / "study_status.json"})()

                def run(self, *, max_steps: int) -> object:
                    type(self).max_steps = max_steps
                    return type("Result", (), {"executed": [], "final_stage": "PLAN"})()

            with patch("core.auto_train.cli.controller.AutoTrainController", FakeController):
                code = cli.main(
                    [
                        "run",
                        "group1",
                        "--study-name",
                        "study_001",
                        "--train-root",
                        str(train_root),
                        "--generator-workspace",
                        str(generator_workspace),
                        "--goal-only-stop",
                    ]
                )

            self.assertEqual(code, 0)
            assert captured_request is not None
            self.assertTrue(captured_request.goal_only_stop)
            self.assertEqual(FakeController.max_steps, 0)

    def test_run_command_returns_nonzero_when_stopped_without_commercial_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            for path in (train_root, generator_workspace):
                path.mkdir(parents=True, exist_ok=True)

            class FakeController:
                def __init__(self, *, request: object) -> None:
                    self.paths = type(
                        "Paths",
                        (),
                        {
                            "study_status_file": root / "studies" / "group2" / "study_001" / "study_status.json",
                        },
                    )()

                def run(self, *, max_steps: int) -> object:
                    self.paths.study_status_file.parent.mkdir(parents=True, exist_ok=True)
                    storage.write_study_status_record(
                        self.paths.study_status_file,
                        contracts.StudyStatusRecord(
                            study_name="study_001",
                            task="group2",
                            status="stopped",
                            current_trial_id="trial_0017",
                            best_trial_id="trial_0001",
                            latest_decision="REGENERATE_DATA",
                            best_primary_score=1.0,
                            budget_pressure="high",
                            summary_cn="未达到商用门，本次自动训练已停止。",
                            next_actions_cn=["如需继续，请扩大预算后重新启动。"],
                            evidence=["commercial_ready=false"],
                            business_success_rate=0.0,
                            business_success_threshold=0.98,
                            commercial_ready=False,
                            latest_gate_status="failed",
                            final_reason="max_trials_reached",
                            final_detail="20/20",
                        ),
                    )
                    return type(
                        "Result",
                        (),
                        {
                            "executed": [],
                            "final_stage": "STOP",
                        },
                    )()

            with patch("core.auto_train.cli.controller.AutoTrainController", FakeController):
                code = cli.main(
                    [
                        "run",
                        "group2",
                        "--study-name",
                        "study_001",
                        "--train-root",
                        str(train_root),
                        "--generator-workspace",
                        str(generator_workspace),
                    ]
                )

            self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
