from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.auto_train import business_eval, controller, contracts, storage
from core.common.jsonl import write_jsonl


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


def _group2_business_case(*, success: bool) -> contracts.BusinessEvalCaseRecord:
    return contracts.BusinessEvalCaseRecord(
        case_id="case_0001",
        sample_id="case_0001",
        success=success,
        reason_code="pass" if success else "low_iou",
        reason_cn="中心点误差和 IoU 均达标。" if success else "预测框与标准答案重合度不足。",
        input_images={
            "master_image": "/tmp/business-cases/case_0001/bg.jpg",
            "tile_image": "/tmp/business-cases/case_0001/gap.jpg",
        },
        metrics={
            "point_tolerance_px": 12,
            "iou_threshold": 0.5,
            "center_error_px": 3.0,
            "iou": 0.82 if success else 0.31,
            "point_hit": True,
            "inference_ms": 8.5321,
        },
        prediction={"target_gap": {"bbox": [12, 18, 36, 42], "center": [24, 30]}},
        reference={"target_gap": {"bbox": [10, 18, 34, 42], "center": [22, 30]}},
        evidence=[],
    )


class BusinessEvalExamTests(unittest.TestCase):
    def test_select_exam_sample_limits_each_run_to_requested_size(self) -> None:
        rows = [
            {"sample_id": f"case_{index:04d}", "master_image": "master/a.jpg", "tile_image": "tile/a.jpg", "target_gap": {"bbox": [0, 0, 1, 1], "center": [0, 0]}, "tile_bbox": [0, 0, 1, 1], "offset_x": 0, "offset_y": 0, "label_source": "reviewed", "source_batch": "batch"}
            for index in range(80)
        ]

        sampled_a = business_eval.select_exam_sample(rows, sample_size=50, sample_key="trial_0007")
        sampled_b = business_eval.select_exam_sample(rows, sample_size=50, sample_key="trial_0007")

        self.assertEqual(len(sampled_a), 50)
        self.assertEqual([item["sample_id"] for item in sampled_a], [item["sample_id"] for item in sampled_b])

    def test_materialize_sampled_source_rewrites_group2_relative_paths_to_absolute(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            cases_root = root / "business-exams" / "group2" / "reviewed"
            master_dir = cases_root / "master"
            tile_dir = cases_root / "tile"
            master_dir.mkdir(parents=True, exist_ok=True)
            tile_dir.mkdir(parents=True, exist_ok=True)
            (master_dir / "case_0001.jpg").write_bytes(b"master")
            (tile_dir / "case_0001.jpg").write_bytes(b"tile")
            sampled_source = business_eval.materialize_sampled_source(
                task="group2",
                cases_root=cases_root,
                sampled_rows=[
                    {
                        "sample_id": "case_0001",
                        "master_image": "master/case_0001.jpg",
                        "tile_image": "tile/case_0001.jpg",
                        "target_gap": {"class": "slider_gap", "class_id": 0, "bbox": [10, 18, 34, 42], "center": [22, 30]},
                        "tile_bbox": [0, 0, 24, 24],
                        "offset_x": 10,
                        "offset_y": 18,
                        "label_source": "reviewed",
                        "source_batch": "batch",
                    }
                ],
                output_dir=root / "sampled",
            )

            self.assertTrue(sampled_source.exists())
            row = business_eval.load_reviewed_exam_rows("group2", sampled_source.parent)[0]
            self.assertTrue(Path(str(row["master_image"])).is_absolute())
            self.assertTrue(Path(str(row["tile_image"])).is_absolute())

    def test_build_group2_case_results_records_detailed_deviation_and_failed_checks(self) -> None:
        gold_rows = [
            {
                "sample_id": "case_0001",
                "master_image": "/tmp/master/case_0001.jpg",
                "tile_image": "/tmp/tile/case_0001.jpg",
                "target_gap": {"class": "slider_gap", "class_id": 0, "bbox": [10, 18, 34, 42], "center": [22, 30]},
                "tile_bbox": [0, 0, 24, 24],
                "offset_x": 10,
                "offset_y": 18,
                "label_source": "reviewed",
                "source_batch": "batch",
            }
        ]
        prediction_rows = [
            {
                "sample_id": "case_0001",
                "master_image": "/tmp/master/case_0001.jpg",
                "tile_image": "/tmp/tile/case_0001.jpg",
                "target_gap": {"class": "slider_gap", "class_id": 0, "bbox": [14, 22, 54, 62], "center": [34, 42]},
                "tile_bbox": [0, 0, 24, 24],
                "offset_x": 10,
                "offset_y": 18,
                "label_source": "predicted",
                "source_batch": "batch",
                "inference_ms": 6.2,
            }
        ]

        cases = business_eval.build_case_results(
            task="group2",
            gold_rows=gold_rows,
            prediction_rows=prediction_rows,
            point_tolerance_px=5,
            iou_threshold=0.5,
        )

        self.assertEqual(len(cases), 1)
        self.assertFalse(cases[0].success)
        self.assertEqual(cases[0].reason_code, "point_miss_and_low_iou")
        self.assertIn("iou", cases[0].metrics)
        self.assertEqual(cases[0].metrics["delta_x_px"], 12.0)
        self.assertEqual(cases[0].metrics["delta_y_px"], 12.0)
        self.assertEqual(cases[0].metrics["failed_checks"], ["point_tolerance", "iou"])
        self.assertFalse(cases[0].metrics["point_hit"])
        self.assertFalse(cases[0].metrics["iou_hit"])

    def test_run_reviewed_business_eval_group2_falls_back_to_last_weights_when_best_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            cases_root = root / "business-exams" / "group2" / "reviewed"
            report_dir = root / "reports" / "business-eval"
            weights_dir = train_root / "runs" / "group2" / "trial_0001" / "weights"
            master_dir = cases_root / "master"
            tile_dir = cases_root / "tile"
            for path in (weights_dir, master_dir, tile_dir):
                path.mkdir(parents=True, exist_ok=True)
            (weights_dir / "last.pt").write_bytes(b"pt")
            (master_dir / "case_0001.png").write_bytes(b"master")
            (tile_dir / "case_0001.png").write_bytes(b"tile")
            write_jsonl(
                cases_root / "labels.jsonl",
                [
                    {
                        "sample_id": "case_0001",
                        "master_image": "master/case_0001.png",
                        "tile_image": "tile/case_0001.png",
                        "target_gap": {"class": "slider_gap", "class_id": 0, "bbox": [10, 18, 34, 42], "center": [22, 30]},
                        "tile_bbox": [0, 0, 24, 24],
                        "offset_x": 10,
                        "offset_y": 18,
                        "label_source": "reviewed",
                        "source_batch": "batch",
                    }
                ],
            )

            observed_model_path: Path | None = None

            def _fake_modeltest(request):
                nonlocal observed_model_path
                observed_model_path = request.model_path
                predict_dir = report_dir / "modeltest" / request.predict_name
                predict_dir.mkdir(parents=True, exist_ok=True)
                write_jsonl(
                    predict_dir / "labels.jsonl",
                    [
                        {
                            "sample_id": "case_0001",
                            "master_image": str(master_dir / "case_0001.png"),
                            "tile_image": str(tile_dir / "case_0001.png"),
                            "target_gap": {"class": "slider_gap", "class_id": 0, "bbox": [10, 18, 34, 42], "center": [22, 30]},
                            "tile_bbox": [0, 0, 24, 24],
                            "offset_x": 10,
                            "offset_y": 18,
                            "label_source": "predicted",
                            "source_batch": "batch",
                        }
                    ],
                )
                return type(
                    "Result",
                    (),
                    {
                        "predict_output_dir": predict_dir,
                    },
                )()

            with patch("core.auto_train.business_eval.evaluate_model") as evaluate_model:
                evaluate_model.return_value = type(
                    "EvalResult",
                    (),
                    {
                        "failure_count": 0,
                        "report_dir": report_dir / "evaluation",
                    },
                )()
                record = business_eval.run_reviewed_business_eval(
                    trial_id="trial_0001",
                    task="group2",
                    train_root=train_root,
                    dataset_version="firstpass",
                    train_name="trial_0001",
                    cases_root=cases_root,
                    report_dir=report_dir,
                    device="0",
                    imgsz=192,
                    success_threshold=0.95,
                    min_cases=1,
                    sample_size=1,
                    point_tolerance_px=5,
                    iou_threshold=0.5,
                    modeltest_runner=_fake_modeltest,
                )

            self.assertEqual(observed_model_path, weights_dir / "last.pt")
            self.assertEqual(record.total_cases, 1)
            self.assertEqual(record.passed_cases, 1)
            self.assertTrue(record.commercial_ready)

    def test_business_eval_log_includes_group1_sequence_details(self) -> None:
        record = contracts.BusinessEvalRecord(
            trial_id="trial_0008",
            task="group1",
            train_name="trial_0008",
            cases_root="/tmp/business-cases",
            available_cases=30,
            total_cases=30,
            passed_cases=28,
            success_rate=28 / 30,
            success_threshold=0.95,
            min_cases=30,
            sample_size=30,
            commercial_ready=False,
            point_tolerance_px=12,
            iou_threshold=0.5,
            sampled_source="/tmp/business-eval/_sampled_source/labels.jsonl",
            report_dir="/tmp/business-eval",
            prediction_dir="/tmp/business-eval/modeltest/predict",
            evaluation_report_dir="/tmp/business-eval/evaluation",
            case_results=[
                contracts.BusinessEvalCaseRecord(
                    case_id="case_0001",
                    sample_id="case_0001",
                    success=True,
                    reason_code="pass",
                    reason_cn="点击序列、类别和中心点误差均达标。",
                    input_images={"query_image": "/tmp/query/case_0001.jpg", "scene_image": "/tmp/scene/case_0001.jpg"},
                    metrics={"target_count": 2, "predicted_target_count": 2, "matched_target_count": 2, "order_ok": True},
                    prediction={"scene_targets": [{"order": 1, "center": [20, 20]}, {"order": 2, "center": [60, 20]}]},
                    reference={"scene_targets": [{"order": 1, "center": [20, 20]}, {"order": 2, "center": [60, 20]}]},
                    evidence=["status=matched"],
                )
            ],
            evidence=["business_success_rate=0.9333"],
        )

        rendered = business_eval.log_from_business_eval(record)

        self.assertIn("task=group1", rendered)
        self.assertIn("reason_code=pass", rendered)
        self.assertIn("\"matched_target_count\": 2", rendered)
        self.assertIn("\"scene_targets\"", rendered)
        self.assertIn("status=PASS", rendered)

    def test_business_eval_markdown_lists_group2_case_deviation_and_failed_checks(self) -> None:
        record = contracts.BusinessEvalRecord(
            trial_id="trial_0009",
            task="group2",
            train_name="trial_0009",
            cases_root="/tmp/business-cases",
            available_cases=50,
            total_cases=50,
            passed_cases=49,
            success_rate=49 / 50,
            success_threshold=0.95,
            min_cases=50,
            sample_size=50,
            commercial_ready=True,
            point_tolerance_px=5,
            iou_threshold=0.5,
            sampled_source="/tmp/business-eval/_sampled_source/labels.jsonl",
            report_dir="/tmp/business-eval",
            prediction_dir="/tmp/business-eval/modeltest/predict",
            evaluation_report_dir="/tmp/business-eval/evaluation",
            case_results=[
                contracts.BusinessEvalCaseRecord(
                    case_id="case_0007",
                    sample_id="case_0007",
                    success=False,
                    reason_code="point_miss_and_low_iou",
                    reason_cn="预测中心点超出允许像素容差，且预测框与标准答案重合度不足。",
                    input_images={"master_image": "/tmp/master/case_0007.png", "tile_image": "/tmp/tile/case_0007.png"},
                    metrics={
                        "point_tolerance_px": 5,
                        "iou_threshold": 0.5,
                        "center_error_px": 7.2111,
                        "delta_x_px": 6.0,
                        "delta_y_px": -4.0,
                        "iou": 0.31,
                        "point_hit": False,
                        "iou_hit": False,
                        "failed_checks": ["point_tolerance", "iou"],
                    },
                    prediction={"target_gap": {"bbox": [16, 12, 40, 36], "center": [28, 24]}},
                    reference={"target_gap": {"bbox": [10, 16, 34, 40], "center": [22, 28]}},
                    evidence=[],
                )
            ],
            evidence=["commercial_ready=true"],
        )

        rendered = business_eval.markdown_from_business_eval(record)

        self.assertIn("### case_0007", rendered)
        self.assertIn("delta_x_px", rendered)
        self.assertIn("delta_y_px", rendered)
        self.assertIn("failed_checks", rendered)
        self.assertIn("point_miss_and_low_iou", rendered)


class BusinessEvalControllerTests(unittest.TestCase):
    def test_business_eval_artifacts_include_detailed_log_file(self) -> None:
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
                    business_eval_min_cases=30,
                    business_eval_sample_size=30,
                ),
                dependencies=controller.ControllerDependencies(
                    business_eval_runner=lambda _: controller.runners.business_eval.BusinessEvalRunnerResult(
                        record=contracts.BusinessEvalRecord(
                            trial_id="trial_0001",
                            task="group2",
                            train_name="trial_0001",
                            cases_root=str(business_cases),
                            available_cases=132,
                            total_cases=30,
                            passed_cases=25,
                            success_rate=25 / 30,
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
                            case_results=[_group2_business_case(success=True)],
                            evidence=["business_success_rate=0.8333", "commercial_ready=false"],
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
                        min_cases=30,
                        sample_size=30,
                        point_tolerance_px=12,
                        iou_threshold=0.5,
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
            self.assertIn("reason_code=pass", log_text)
            self.assertIn("\"center_error_px\": 3.0", log_text)
            self.assertIn("\"target_gap\"", log_text)

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
                    business_eval_min_cases=30,
                    business_eval_sample_size=30,
                ),
                dependencies=controller.ControllerDependencies(
                    business_eval_runner=lambda _: controller.runners.business_eval.BusinessEvalRunnerResult(
                        record=contracts.BusinessEvalRecord(
                            trial_id="trial_0001",
                            task="group2",
                            train_name="trial_0001",
                            cases_root=str(business_cases),
                            available_cases=132,
                            total_cases=30,
                            passed_cases=25,
                            success_rate=25 / 30,
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
                            evidence=["business_success_rate=0.8333", "commercial_ready=false"],
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
                        min_cases=30,
                        sample_size=30,
                        point_tolerance_px=12,
                        iou_threshold=0.5,
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
                    business_eval_min_cases=30,
                    business_eval_sample_size=30,
                ),
                dependencies=controller.ControllerDependencies(
                    business_eval_runner=lambda _: controller.runners.business_eval.BusinessEvalRunnerResult(
                        record=contracts.BusinessEvalRecord(
                            trial_id="trial_0001",
                            task="group2",
                            train_name="trial_0001",
                            cases_root=str(business_cases),
                            available_cases=240,
                            total_cases=30,
                            passed_cases=29,
                            success_rate=29 / 30,
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
                            evidence=["business_success_rate=0.9667", "commercial_ready=true"],
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
                        min_cases=30,
                        sample_size=30,
                        point_tolerance_px=12,
                        iou_threshold=0.5,
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

    def test_non_promoted_trial_regenerates_data_when_business_goal_is_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            business_cases = root / "business-cases"
            for path in (train_root, generator_workspace, business_cases):
                path.mkdir(parents=True, exist_ok=True)

            ctrl = controller.AutoTrainController(
                request=controller.AutoTrainRequest(
                    task="group1",
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
                    task="group1",
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
                        success_threshold=0.95,
                        min_cases=30,
                        sample_size=30,
                        point_tolerance_px=12,
                        iou_threshold=0.5,
                    ),
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
                    params={"epochs": 100, "batch": 16, "imgsz": 640, "device": "0"},
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
                    primary_metric="full_sequence_hit_rate",
                    primary_score=0.88,
                    test_metrics={"full_sequence_hit_rate": 0.88},
                    evaluation_available=True,
                    evaluation_metrics={"full_sequence_hit_rate": 0.88},
                    failure_count=0,
                    trend="baseline",
                    delta_vs_previous=0.0,
                    delta_vs_best=0.0,
                    weak_classes=[],
                    failure_patterns=[],
                    recent_trials=[],
                    best_trial=None,
                    evidence=["test"],
                ),
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


if __name__ == "__main__":
    unittest.main()
