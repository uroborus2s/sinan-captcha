from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.auto_train import business_eval, controller, contracts, storage


def _gradient_grid(width: int, height: int) -> list[list[float]]:
    return [[float((x * 7 + y * 3) % 256) for x in range(width)] for y in range(height)]


def _copy_patch(
    grid: list[list[float]],
    *,
    x: int,
    y: int,
    width: int,
    height: int,
) -> list[list[float]]:
    return [row[x : x + width] for row in grid[y : y + height]]


def _solid_mask(width: int, height: int, value: float = 1.0) -> list[list[float]]:
    return [[value for _ in range(width)] for _ in range(height)]


def _with_gap(
    grid: list[list[float]],
    *,
    x: int,
    y: int,
    width: int,
    height: int,
    fill: float,
) -> list[list[float]]:
    output = [list(row) for row in grid]
    for row_index in range(y, y + height):
        for col_index in range(x, x + width):
            output[row_index][col_index] = fill
    return output


def _group2_trial_summary(trial_id: str, *, score: float, trend: str = "baseline") -> contracts.ResultSummaryRecord:
    return contracts.ResultSummaryRecord(
        study_name="study_001",
        task="group2",
        trial_id=trial_id,
        dataset_version="firstpass",
        train_name=trial_id,
        primary_metric="point_hit_rate",
        primary_score=score,
        test_metrics={"point_hit_rate": score},
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


def _group2_trial_input(trial_id: str) -> contracts.TrialInputRecord:
    return contracts.TrialInputRecord(
        trial_id=trial_id,
        task="group2",
        dataset_version="firstpass",
        train_name=trial_id,
        train_mode="fresh",
        base_run=None,
        params={"epochs": 100, "batch": 16, "imgsz": 192, "device": "0"},
    )


class BusinessEvalScoringTests(unittest.TestCase):
    def test_occlusion_score_prefers_correct_overlay_position(self) -> None:
        base = _gradient_grid(48, 48)
        tile = _copy_patch(base, x=18, y=16, width=10, height=10)
        alpha = _solid_mask(10, 10)
        master = _with_gap(base, x=18, y=16, width=10, height=10, fill=12.0)

        correct = business_eval.score_occlusion_overlay(
            master_luma=master,
            tile_luma=tile,
            tile_alpha=alpha,
            x=18,
            y=16,
        )
        wrong = business_eval.score_occlusion_overlay(
            master_luma=master,
            tile_luma=tile,
            tile_alpha=alpha,
            x=7,
            y=6,
        )

        self.assertGreater(correct.occlusion_score, wrong.occlusion_score)
        self.assertTrue(correct.success)
        self.assertFalse(wrong.success)

    def test_discover_group2_cases_accepts_bg_and_gap_file_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_a = root / "20260407190052_2"
            case_b = root / "20260407190323_4"
            case_a.mkdir(parents=True, exist_ok=True)
            case_b.mkdir(parents=True, exist_ok=True)
            (case_a / "bg.jpg").write_bytes(b"bg-a")
            (case_a / "gap.jpg").write_bytes(b"gap-a")
            (case_b / "bg.jpg").write_bytes(b"bg-b")
            (case_b / "gap.jpg").write_bytes(b"gap-b")

            cases = business_eval.discover_group2_cases(root)

            self.assertEqual([item.case_id for item in cases], ["20260407190052_2", "20260407190323_4"])
            self.assertEqual(cases[0].master_path.name, "bg.jpg")
            self.assertEqual(cases[0].tile_path.name, "gap.jpg")

    def test_select_case_sample_limits_each_run_to_one_hundred_cases(self) -> None:
        cases = [
            business_eval.CaseSpec(
                case_id=f"case_{index:04d}",
                master_path=Path(f"/tmp/case_{index:04d}/bg.jpg"),
                tile_path=Path(f"/tmp/case_{index:04d}/gap.jpg"),
            )
            for index in range(150)
        ]

        sampled = business_eval.select_case_sample(cases, sample_size=100, sample_key="trial_0007")

        self.assertEqual(len(sampled), 100)
        self.assertEqual(len({item.case_id for item in sampled}), 100)

    def test_business_eval_log_includes_predicted_bbox_and_center(self) -> None:
        record = contracts.BusinessEvalRecord(
            trial_id="trial_0008",
            task="group2",
            train_name="trial_0008",
            cases_root="/tmp/business-cases",
            available_cases=3,
            total_cases=3,
            passed_cases=2,
            success_rate=2 / 3,
            success_threshold=0.98,
            min_cases=3,
            sample_size=3,
            commercial_ready=False,
            occlusion_threshold=0.78,
            report_dir="/tmp/business-eval",
            case_results=[
                contracts.BusinessEvalCaseRecord(
                    case_id="case_0001",
                    master_image="/tmp/case_0001/bg.jpg",
                    tile_image="/tmp/case_0001/gap.jpg",
                    predicted_bbox=[12, 18, 36, 42],
                    predicted_center=[24, 30],
                    inference_ms=8.5321,
                    boundary_before=0.91,
                    boundary_after=0.18,
                    fill_score=0.8022,
                    seam_score=0.9444,
                    occlusion_score=0.8591,
                    success=True,
                    reason_cn="贴回后缺口边界明显收敛，遮挡质量达到阈值。",
                    overlay_path="/tmp/business-eval/case_0001/overlay.png",
                    diff_path="/tmp/business-eval/case_0001/diff.png",
                )
            ],
            evidence=["business_success_rate=0.6667"],
        )

        rendered = business_eval.log_from_business_eval(record)

        self.assertIn("predicted_bbox=[12, 18, 36, 42]", rendered)
        self.assertIn("predicted_center=[24, 30]", rendered)
        self.assertIn("occlusion=0.8591", rendered)
        self.assertIn("PASS", rendered)


class BusinessEvalControllerTests(unittest.TestCase):
    def test_business_eval_artifacts_include_detailed_log_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            business_cases = root / "business-cases"
            for path in (train_root, generator_workspace, business_cases):
                path.mkdir(parents=True, exist_ok=True)

            case_record = contracts.BusinessEvalCaseRecord(
                case_id="case_0001",
                master_image=str(business_cases / "case_0001" / "bg.jpg"),
                tile_image=str(business_cases / "case_0001" / "gap.jpg"),
                predicted_bbox=[12, 18, 36, 42],
                predicted_center=[24, 30],
                inference_ms=8.5321,
                boundary_before=0.91,
                boundary_after=0.18,
                fill_score=0.8022,
                seam_score=0.9444,
                occlusion_score=0.8591,
                success=True,
                reason_cn="贴回后缺口边界明显收敛，遮挡质量达到阈值。",
                overlay_path=str(root / "reports" / "business_eval_trial_0001" / "case_0001" / "overlay.png"),
                diff_path=str(root / "reports" / "business_eval_trial_0001" / "case_0001" / "diff.png"),
            )
            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group2",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                    business_eval_dir=business_cases,
                    business_eval_success_threshold=0.95,
                    business_eval_min_cases=3,
                ),
                dependencies=controller.ControllerDependencies(
                    business_eval_runner=lambda _: controller.runners.business_eval.BusinessEvalRunnerResult(
                        record=contracts.BusinessEvalRecord(
                            trial_id="trial_0001",
                            task="group2",
                            train_name="trial_0001",
                            cases_root=str(business_cases),
                            available_cases=132,
                            total_cases=4,
                            passed_cases=3,
                            success_rate=0.75,
                            success_threshold=0.95,
                            min_cases=3,
                            sample_size=100,
                            commercial_ready=False,
                            occlusion_threshold=0.78,
                            report_dir=str(root / "reports" / "business_eval_trial_0001"),
                            case_results=[case_record],
                            evidence=["business_success_rate=0.75", "commercial_ready=false"],
                        ),
                        command="uv run sinan business-eval group2",
                    )
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
                    current_trial_id="trial_0001",
                    best_trial_id=None,
                    business_eval=contracts.BusinessEvalConfig(
                        cases_root=str(business_cases),
                        success_threshold=0.95,
                        min_cases=3,
                        occlusion_threshold=0.78,
                    ),
                ),
            )
            storage.write_trial_input_record(ctrl.paths.input_file("trial_0001"), _group2_trial_input("trial_0001"))
            storage.write_result_summary_record(
                ctrl.paths.result_summary_file("trial_0001"),
                _group2_trial_summary("trial_0001", score=1.0, trend="plateau"),
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

            ctrl.run_stage("NEXT_ACTION")

            log_text = ctrl.paths.business_eval_log_file("trial_0001").read_text(encoding="utf-8")
            self.assertIn("predicted_bbox=[12, 18, 36, 42]", log_text)
            self.assertIn("predicted_center=[24, 30]", log_text)

    def test_promote_branch_waits_for_business_gate_when_commercial_threshold_not_met(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            business_cases = root / "business-cases"
            for path in (train_root, generator_workspace, business_cases):
                path.mkdir(parents=True, exist_ok=True)

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group2",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                    business_eval_dir=business_cases,
                    business_eval_success_threshold=0.95,
                    business_eval_min_cases=3,
                ),
                dependencies=controller.ControllerDependencies(
                    business_eval_runner=lambda _: controller.runners.business_eval.BusinessEvalRunnerResult(
                        record=contracts.BusinessEvalRecord(
                            trial_id="trial_0001",
                            task="group2",
                            train_name="trial_0001",
                            cases_root=str(business_cases),
                            available_cases=132,
                            total_cases=4,
                            passed_cases=3,
                            success_rate=0.75,
                            success_threshold=0.95,
                            min_cases=3,
                            sample_size=100,
                            commercial_ready=False,
                            occlusion_threshold=0.78,
                            report_dir=str(root / "reports" / "business_eval_trial_0001"),
                            case_results=[],
                            evidence=["business_success_rate=0.75", "commercial_ready=false"],
                        ),
                        command="uv run sinan business-eval group2",
                    )
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
                    current_trial_id="trial_0001",
                    best_trial_id=None,
                    business_eval=contracts.BusinessEvalConfig(
                        cases_root=str(business_cases),
                        success_threshold=0.95,
                        min_cases=3,
                        occlusion_threshold=0.78,
                    ),
                ),
            )
            storage.write_trial_input_record(ctrl.paths.input_file("trial_0001"), _group2_trial_input("trial_0001"))
            storage.write_result_summary_record(
                ctrl.paths.result_summary_file("trial_0001"),
                _group2_trial_summary("trial_0001", score=1.0, trend="plateau"),
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

            execution = ctrl.run_stage("NEXT_ACTION")

            self.assertEqual(execution.next_stage, "PLAN")
            self.assertEqual(execution.detail, "trial_0002")
            study = storage.read_study_record(ctrl.paths.study_file)
            self.assertEqual(study.status, "running")
            self.assertEqual(study.current_trial_id, "trial_0002")
            business_record = storage.read_business_eval_record(ctrl.paths.business_eval_file("trial_0001"))
            self.assertFalse(business_record.commercial_ready)
            next_input = storage.read_trial_input_record(ctrl.paths.input_file("trial_0002"))
            self.assertEqual(next_input.dataset_version, "firstpass_r0002")
            self.assertEqual(next_input.base_run, "trial_0001")
            self.assertIsNotNone(next_input.dataset_override)
            study_status = storage.read_study_status_record(ctrl.paths.study_status_file)
            self.assertFalse(study_status.commercial_ready)
            self.assertEqual(study_status.latest_decision, "REGENERATE_DATA")

    def test_promote_branch_stops_after_business_gate_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            business_cases = root / "business-cases"
            for path in (train_root, generator_workspace, business_cases):
                path.mkdir(parents=True, exist_ok=True)

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group2",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                    business_eval_dir=business_cases,
                    business_eval_success_threshold=0.95,
                    business_eval_min_cases=3,
                ),
                dependencies=controller.ControllerDependencies(
                    business_eval_runner=lambda _: controller.runners.business_eval.BusinessEvalRunnerResult(
                        record=contracts.BusinessEvalRecord(
                            trial_id="trial_0001",
                            task="group2",
                            train_name="trial_0001",
                            cases_root=str(business_cases),
                            available_cases=240,
                            total_cases=20,
                            passed_cases=19,
                            success_rate=0.95,
                            success_threshold=0.95,
                            min_cases=3,
                            sample_size=100,
                            commercial_ready=True,
                            occlusion_threshold=0.78,
                            report_dir=str(root / "reports" / "business_eval_trial_0001"),
                            case_results=[],
                            evidence=["business_success_rate=0.95", "commercial_ready=true"],
                        ),
                        command="uv run sinan business-eval group2",
                    )
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
                    current_trial_id="trial_0001",
                    best_trial_id=None,
                    business_eval=contracts.BusinessEvalConfig(
                        cases_root=str(business_cases),
                        success_threshold=0.95,
                        min_cases=3,
                        occlusion_threshold=0.78,
                    ),
                ),
            )
            storage.write_trial_input_record(ctrl.paths.input_file("trial_0001"), _group2_trial_input("trial_0001"))
            storage.write_result_summary_record(
                ctrl.paths.result_summary_file("trial_0001"),
                _group2_trial_summary("trial_0001", score=1.0, trend="plateau"),
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

            execution = ctrl.run_stage("NEXT_ACTION")

            self.assertEqual(execution.next_stage, "STOP")
            study = storage.read_study_record(ctrl.paths.study_file)
            self.assertEqual(study.status, "completed")
            self.assertEqual(study.best_trial_id, "trial_0001")
            self.assertTrue(ctrl.paths.commercial_report_file.exists())
            self.assertIn("达到商用门", ctrl.paths.commercial_report_file.read_text(encoding="utf-8"))

    def test_plateau_stop_is_disabled_while_business_gate_is_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            business_cases = root / "business-cases"
            for path in (train_root, generator_workspace, business_cases):
                path.mkdir(parents=True, exist_ok=True)

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group2",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                    business_eval_dir=business_cases,
                    max_no_improve_trials=2,
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
                    budget=contracts.StudyBudget(max_trials=20, max_hours=24.0, max_no_improve_trials=2),
                    current_trial_id="trial_0003",
                    best_trial_id="trial_0001",
                    business_eval=contracts.BusinessEvalConfig(
                        cases_root=str(business_cases),
                        success_threshold=0.95,
                        min_cases=5,
                        occlusion_threshold=0.78,
                    ),
                ),
            )
            storage.write_trial_input_record(ctrl.paths.input_file("trial_0001"), _group2_trial_input("trial_0001"))
            storage.write_trial_input_record(ctrl.paths.input_file("trial_0002"), _group2_trial_input("trial_0002"))
            storage.write_trial_input_record(ctrl.paths.input_file("trial_0003"), _group2_trial_input("trial_0003"))
            storage.write_result_summary_record(
                ctrl.paths.result_summary_file("trial_0001"),
                _group2_trial_summary("trial_0001", score=1.0, trend="baseline"),
            )
            storage.write_result_summary_record(
                ctrl.paths.result_summary_file("trial_0002"),
                _group2_trial_summary("trial_0002", score=1.0, trend="plateau"),
            )
            storage.write_result_summary_record(
                ctrl.paths.result_summary_file("trial_0003"),
                _group2_trial_summary("trial_0003", score=1.0, trend="plateau"),
            )
            storage.write_decision_record(
                ctrl.paths.decision_file("trial_0003"),
                contracts.DecisionRecord(
                    trial_id="trial_0003",
                    decision="RESUME",
                    confidence=0.9,
                    reason="continue_study",
                    next_action={"dataset_action": "reuse", "train_action": "resume"},
                    evidence=["continue"],
                    agent=contracts.AgentRef(provider="rules", name="policy-judge", model="policy-v1"),
                ),
            )

            execution = ctrl.run_stage("NEXT_ACTION")

            self.assertEqual(execution.next_stage, "PLAN")
            self.assertEqual(execution.detail, "trial_0004")
            next_input = storage.read_trial_input_record(ctrl.paths.input_file("trial_0004"))
            self.assertEqual(next_input.dataset_version, "firstpass_r0004")
            self.assertIsNotNone(next_input.dataset_override)
            study = storage.read_study_record(ctrl.paths.study_file)
            self.assertEqual(study.status, "running")
            study_status = storage.read_study_status_record(ctrl.paths.study_status_file)
            self.assertEqual(study_status.latest_decision, "REGENERATE_DATA")

    def test_non_promoted_group2_trial_regenerates_data_when_business_goal_is_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            business_cases = root / "business-cases"
            for path in (train_root, generator_workspace, business_cases):
                path.mkdir(parents=True, exist_ok=True)

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group2",
                    study_name="study_001",
                    train_root=train_root,
                    generator_workspace=generator_workspace,
                    studies_root=root / "studies",
                    dataset_version="firstpass",
                    business_eval_dir=business_cases,
                    max_no_improve_trials=2,
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
                    budget=contracts.StudyBudget(max_trials=20, max_hours=24.0, max_no_improve_trials=2),
                    current_trial_id="trial_0001",
                    best_trial_id=None,
                    business_eval=contracts.BusinessEvalConfig(
                        cases_root=str(business_cases),
                        success_threshold=0.98,
                        min_cases=5,
                        occlusion_threshold=0.78,
                    ),
                ),
            )
            storage.write_trial_input_record(ctrl.paths.input_file("trial_0001"), _group2_trial_input("trial_0001"))
            storage.write_result_summary_record(
                ctrl.paths.result_summary_file("trial_0001"),
                _group2_trial_summary("trial_0001", score=0.88, trend="baseline"),
            )
            storage.write_decision_record(
                ctrl.paths.decision_file("trial_0001"),
                contracts.DecisionRecord(
                    trial_id="trial_0001",
                    decision="RETUNE",
                    confidence=0.9,
                    reason="continue_tuning",
                    next_action={"dataset_action": "reuse", "train_action": "from_run", "base_run": "trial_0001"},
                    evidence=["continue"],
                    agent=contracts.AgentRef(provider="rules", name="policy-judge", model="policy-v1"),
                ),
            )

            execution = ctrl.run_stage("NEXT_ACTION")

            self.assertEqual(execution.next_stage, "PLAN")
            next_input = storage.read_trial_input_record(ctrl.paths.input_file("trial_0002"))
            self.assertEqual(next_input.dataset_version, "firstpass_r0002")
            self.assertEqual(next_input.base_run, "trial_0001")
            self.assertIsNotNone(next_input.dataset_override)
            study_status = storage.read_study_status_record(ctrl.paths.study_status_file)
            self.assertEqual(study_status.latest_decision, "REGENERATE_DATA")
