from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.auto_train import business_eval, controller, contracts, storage


def _gradient_grid(width: int, height: int) -> list[list[float]]:
    return [[float((x * 7 + y * 3) % 256) for x in range(width)] for y in range(height)]


def _dark_textured_grid(width: int, height: int) -> list[list[float]]:
    return [[float(28 + ((x * 5 + y * 7) % 24)) for x in range(width)] for y in range(height)]


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


def _outline_mask(width: int, height: int, *, thickness: int = 1) -> list[list[float]]:
    output: list[list[float]] = []
    for y in range(height):
        row: list[float] = []
        for x in range(width):
            is_edge = (
                x < thickness
                or x >= width - thickness
                or y < thickness
                or y >= height - thickness
            )
            row.append(1.0 if is_edge else 0.0)
        output.append(row)
    return output


def _outlined_tile(width: int, height: int, *, border_value: float = 255.0) -> list[list[float]]:
    alpha = _outline_mask(width, height)
    return [[border_value if alpha[y][x] > 0.0 else 0.0 for x in range(width)] for y in range(height)]


def _stamp_mask(
    grid: list[list[float]],
    *,
    mask: list[list[float]],
    x: int,
    y: int,
    value: float,
) -> list[list[float]]:
    output = [list(row) for row in grid]
    for mask_y, row in enumerate(mask):
        for mask_x, alpha in enumerate(row):
            if alpha <= 0.0:
                continue
            output[y + mask_y][x + mask_x] = value
    return output


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
    def test_overlay_gate_allows_visually_aligned_case_when_only_clean_score_is_slightly_low(self) -> None:
        metrics = business_eval.OverlayArtifactMetrics(
            contour_overlap_ratio=0.605263,
            exposed_gap_edge_ratio=0.180000,
            double_contour_ratio=0.120000,
            tile_residue_ratio=0.280000,
            double_edge_score=0.120000,
            overflow_edge_score=0.110000,
            artifact_score=0.233018,
            clean_score=0.766982,
        )

        verdict = business_eval._overlay_gate_verdict(
            local_metrics=metrics,
            best_local_offset_px=1.0,
            success_threshold=0.78,
        )

        self.assertTrue(verdict.success)
        self.assertEqual(verdict.failed_checks_cn, [])

    def test_overlay_artifact_score_prefers_aligned_position(self) -> None:
        base = _dark_textured_grid(64, 64)
        alpha = _outline_mask(12, 12)
        tile = _outlined_tile(12, 12)
        master = _stamp_mask(base, mask=alpha, x=22, y=18, value=255.0)

        correct = business_eval.score_occlusion_overlay(
            master_luma=master,
            tile_luma=tile,
            tile_alpha=alpha,
            x=22,
            y=18,
        )
        wrong = business_eval.score_occlusion_overlay(
            master_luma=master,
            tile_luma=tile,
            tile_alpha=alpha,
            x=8,
            y=9,
        )

        self.assertGreater(correct.occlusion_score, wrong.occlusion_score)
        self.assertGreater(correct.contour_overlap_ratio, wrong.contour_overlap_ratio)
        self.assertLessEqual(correct.best_local_offset_px, 1.0)
        self.assertEqual(correct.best_local_bbox[1], 18)
        self.assertEqual(correct.best_local_bbox[3], 30)
        self.assertGreaterEqual(correct.best_local_clean_score, 0.80)
        self.assertGreater(correct.contour_overlap_ratio, 0.70)
        self.assertTrue(correct.success)
        self.assertFalse(wrong.success)
        self.assertGreater(wrong.best_local_offset_px, 5.0)

    def test_local_best_offset_within_ten_pixels_counts_as_success(self) -> None:
        base = _dark_textured_grid(72, 72)
        alpha = _outline_mask(14, 14)
        tile = _outlined_tile(14, 14)
        master = _stamp_mask(base, mask=alpha, x=24, y=20, value=255.0)

        near = business_eval.score_occlusion_overlay(
            master_luma=master,
            tile_luma=tile,
            tile_alpha=alpha,
            x=32,
            y=28,
        )

        self.assertLessEqual(near.best_local_offset_px, 10.0)
        self.assertEqual(near.best_local_bbox[1], 20)
        self.assertEqual(near.best_local_bbox[3], 34)
        self.assertGreaterEqual(near.best_local_clean_score, 0.80)
        self.assertTrue(near.success)

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
                    boundary_before=0.1200,
                    boundary_after=0.0900,
                    fill_score=0.8800,
                    seam_score=0.9100,
                    occlusion_score=0.9020,
                    success=True,
                    reason_cn="模型输出位置与附近最干净贴合位置的边框偏差在 5px 以内，且局部 overlay 痕迹检测达标，判定通过。",
                    result_cn="成功",
                    final_score=0.9470,
                    required_score=0.7800,
                    failed_checks_cn=[],
                    overlay_path="/tmp/business-eval/case_0001/overlay.png",
                    diff_path="/tmp/business-eval/case_0001/diff.png",
                    best_local_bbox=[14, 18, 38, 42],
                    best_local_offset_px=2.0,
                    best_local_clean_score=0.9470,
                    contour_overlap_ratio=0.9200,
                    exposed_gap_edge_ratio=0.0800,
                    double_contour_ratio=0.0700,
                    tile_residue_ratio=0.1200,
                    double_edge_score=0.0700,
                    overflow_edge_score=0.0900,
                )
            ],
            evidence=["business_success_rate=0.6667"],
        )

        rendered = business_eval.log_from_business_eval(record)

        self.assertIn("# 字段说明", rendered)
        self.assertIn("predicted_bbox: 模型输出的背景图坐标框", rendered)
        self.assertIn("best_local_bbox: 在模型输出位置附近做局部搜索后，痕迹最干净的候选框", rendered)
        self.assertIn("predicted_bbox=[12, 18, 36, 42]", rendered)
        self.assertIn("best_local_bbox=[14, 18, 38, 42]", rendered)
        self.assertIn("predicted_center=[24, 30]", rendered)
        self.assertIn("best_local_offset_px=2.0000", rendered)
        self.assertIn("best_local_clean_score=0.9470", rendered)
        self.assertIn("contour_overlap_ratio=0.9200", rendered)
        self.assertIn("exposed_gap_edge_ratio=0.0800", rendered)
        self.assertIn("double_contour_ratio=0.0700", rendered)
        self.assertIn("result_cn=成功", rendered)
        self.assertIn("final_score=0.9470", rendered)
        self.assertIn("required_score=0.7800", rendered)
        self.assertIn("failed_checks_cn=无", rendered)
        self.assertIn("clean_score=0.9020", rendered)
        self.assertIn("tile_residue_ratio=0.1200", rendered)
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
                boundary_before=0.12,
                boundary_after=0.09,
                fill_score=0.88,
                seam_score=0.91,
                occlusion_score=0.902,
                success=True,
                reason_cn="模型输出位置与附近最干净贴合位置的边框偏差在 5px 以内，且局部 overlay 痕迹检测达标，判定通过。",
                result_cn="成功",
                final_score=0.947,
                required_score=0.78,
                failed_checks_cn=[],
                overlay_path=str(root / "reports" / "business_eval_trial_0001" / "case_0001" / "overlay.png"),
                diff_path=str(root / "reports" / "business_eval_trial_0001" / "case_0001" / "diff.png"),
                best_local_bbox=[14, 18, 38, 42],
                best_local_offset_px=2.0,
                best_local_clean_score=0.947,
                contour_overlap_ratio=0.92,
                exposed_gap_edge_ratio=0.08,
                double_contour_ratio=0.07,
                tile_residue_ratio=0.12,
                double_edge_score=0.07,
                overflow_edge_score=0.09,
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
            self.assertIn("best_local_bbox=[14, 18, 38, 42]", log_text)
            self.assertIn("best_local_offset_px=2.0000", log_text)
            self.assertIn("contour_overlap_ratio=0.9200", log_text)
            self.assertIn("tile_residue_ratio=0.1200", log_text)

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
            self.assertEqual(next_input.dataset_version, "study_001_trial_0002")
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

    def test_failed_business_gate_stop_report_explains_workflow_and_stop_reason(self) -> None:
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
                    business_eval_success_threshold=0.98,
                    business_eval_min_cases=3,
                    max_trials=1,
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
                            passed_cases=0,
                            success_rate=0.0,
                            success_threshold=0.98,
                            min_cases=3,
                            sample_size=100,
                            commercial_ready=False,
                            occlusion_threshold=0.78,
                            report_dir=str(root / "reports" / "business_eval_trial_0001"),
                            case_results=[],
                            evidence=["business_success_rate=0.0", "commercial_ready=false"],
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
                    budget=contracts.StudyBudget(max_trials=1, max_hours=24.0, max_no_improve_trials=4),
                    current_trial_id="trial_0001",
                    best_trial_id=None,
                    business_eval=contracts.BusinessEvalConfig(
                        cases_root=str(business_cases),
                        success_threshold=0.98,
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
            self.assertEqual(execution.detail, "max_trials_reached")
            study = storage.read_study_record(ctrl.paths.study_file)
            self.assertEqual(study.status, "stopped")
            self.assertEqual(study.final_reason, "max_trials_reached")
            self.assertEqual(study.final_detail, "1/1")
            study_status = storage.read_study_status_record(ctrl.paths.study_status_file)
            self.assertEqual(study_status.final_reason, "max_trials_reached")
            self.assertEqual(study_status.final_detail, "1/1")
            self.assertIn("未达到商用门", study_status.summary_cn)
            self.assertNotIn("将继续训练", study_status.summary_cn)
            self.assertIn("max_trials_reached", ctrl.paths.commercial_report_file.read_text(encoding="utf-8"))
            self.assertIn("流程状态", ctrl.paths.commercial_report_file.read_text(encoding="utf-8"))
            self.assertIn("晋级结论", ctrl.paths.commercial_report_file.read_text(encoding="utf-8"))

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
            self.assertEqual(next_input.dataset_version, "study_001_trial_0004")
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
            self.assertEqual(next_input.dataset_version, "study_001_trial_0002")
            self.assertEqual(next_input.base_run, "trial_0001")
            self.assertIsNotNone(next_input.dataset_override)
            study_status = storage.read_study_status_record(ctrl.paths.study_status_file)
            self.assertEqual(study_status.latest_decision, "REGENERATE_DATA")
