from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from solve import bundle, contracts, service
from inference.service import ClickPoint, Group1ClickTarget, Group1MappingResult


class SolveContractsTests(unittest.TestCase):
    def test_group2_request_accepts_optional_tile_start_bbox(self) -> None:
        request = contracts.SolveRequest.from_dict(
            {
                "request_id": "req_group2_001",
                "task_hint": "group2",
                "inputs": {
                    "master_image": "master.png",
                    "tile_image": "tile.png",
                },
            },
            base_dir=Path("/tmp"),
        )

        self.assertEqual(request.input_task, "group2")
        self.assertIsNone(request.inputs.tile_start_bbox)

    def test_group2_request_rejects_conflicting_input_shapes(self) -> None:
        with self.assertRaises(contracts.SolveContractError):
            contracts.SolveRequest.from_dict(
                {
                    "request_id": "req_bad",
                    "inputs": {
                        "query_image": "query.png",
                        "scene_image": "scene.png",
                        "master_image": "master.png",
                        "tile_image": "tile.png",
                    },
                },
                base_dir=Path("/tmp"),
            )


class SolveBundleTests(unittest.TestCase):
    def test_build_and_load_solver_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            proposal_weight = train_root / "runs" / "group1" / "firstpass" / "proposal-detector" / "weights" / "best.pt"
            query_weight = train_root / "runs" / "group1" / "firstpass" / "query-parser" / "weights" / "best.pt"
            embedder_weight = train_root / "runs" / "group1" / "firstpass" / "icon-embedder" / "weights" / "best.pt"
            group2_weight = train_root / "runs" / "group2" / "firstpass" / "weights" / "best.pt"
            for path in (proposal_weight, query_weight, embedder_weight, group2_weight):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("weights", encoding="utf-8")

            built = bundle.build_solver_bundle(
                bundle_dir=root / "bundles" / "solver" / "current",
                train_root=train_root,
                group1_run="firstpass",
                group2_run="firstpass",
            )

            loaded = bundle.load_solver_bundle(built.root)
            self.assertEqual(loaded.bundle_version, "current")
            self.assertTrue(loaded.manifest_path.exists())
            self.assertTrue(loaded.proposal_model_path.exists())
            self.assertTrue(loaded.query_model_path.exists())
            self.assertIsNotNone(loaded.icon_embedder_model_path)
            self.assertTrue(loaded.icon_embedder_model_path.exists())
            self.assertTrue(loaded.group2_model_path.exists())


class UnifiedSolverServiceTests(unittest.TestCase):
    def test_group1_solver_routes_to_instance_matcher(self) -> None:
        solver = service.UnifiedSolverService(_fake_bundle())
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            query = root / "query.png"
            scene = root / "scene.png"
            query.write_text("query", encoding="utf-8")
            scene.write_text("scene", encoding="utf-8")

            request = contracts.SolveRequest(
                request_id="req_group1_001",
                task_hint="group1",
                inputs=contracts.Group1SolveInputs(
                    query_image=query,
                    scene_image=scene,
                ),
            )

            fake_query_items = [
                {
                    "order": 1,
                    "bbox": [8, 8, 28, 28],
                    "center": [18, 18],
                    "score": 0.99,
                    "class_guess": "icon_lock",
                }
            ]
            fake_scene_targets = [
                {
                    "order": 1,
                    "bbox": [80, 32, 120, 72],
                    "center": [100, 52],
                    "score": 0.98,
                }
            ]
            fake_mapping = Group1MappingResult(
                status="ok",
                ordered_targets=[
                    Group1ClickTarget(
                        order=1,
                        bbox=[80, 32, 120, 72],
                        center=[100, 52],
                        score=1.0,
                    )
                ],
                ordered_clicks=[ClickPoint(x=100, y=52)],
                missing_orders=[],
                ambiguous_orders=[],
            )

            with (
                patch.object(service.UnifiedSolverService, "_load_group1_models", return_value=(_FakeGroup1Model(), _FakeGroup1Model())),
                patch.object(service.UnifiedSolverService, "_load_group1_embedder", return_value=None),
                patch("solve.service._serialize_yolo_detections", side_effect=[fake_query_items, fake_scene_targets]),
                patch("solve.service.map_group1_instances", return_value=fake_mapping) as matcher,
            ):
                response = solver.solve(request)

            self.assertEqual(response.status, "ok")
            self.assertEqual(response.result["matcher_status"], "ok")
            self.assertEqual(response.result["ordered_clicks"], [{"order": 1, "x": 100, "y": 52, "score": 1.0}])
            matcher.assert_called_once_with(
                fake_query_items,
                fake_scene_targets,
                query_image_path=query,
                scene_image_path=scene,
            )

    def test_group1_solver_passes_bundle_icon_embedder_to_instance_matcher(self) -> None:
        fake_embedder = object()
        solver = service.UnifiedSolverService(_fake_bundle(icon_embedder=True))
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            query = root / "query.png"
            scene = root / "scene.png"
            query.write_text("query", encoding="utf-8")
            scene.write_text("scene", encoding="utf-8")

            request = contracts.SolveRequest(
                request_id="req_group1_embedder_001",
                task_hint="group1",
                inputs=contracts.Group1SolveInputs(
                    query_image=query,
                    scene_image=scene,
                ),
            )
            fake_mapping = Group1MappingResult(
                status="ok",
                ordered_targets=[],
                ordered_clicks=[],
                missing_orders=[],
                ambiguous_orders=[],
            )

            with (
                patch.object(service.UnifiedSolverService, "_load_group1_models", return_value=(_FakeGroup1Model(), _FakeGroup1Model())),
                patch.object(service.UnifiedSolverService, "_load_group1_embedder", return_value=fake_embedder),
                patch("solve.service._serialize_yolo_detections", side_effect=[[], []]),
                patch("solve.service.map_group1_instances", return_value=fake_mapping) as matcher,
            ):
                response = solver.solve(request)

            self.assertEqual(response.status, "ok")
            matcher.assert_called_once_with(
                [],
                [],
                query_image_path=query,
                scene_image_path=scene,
                embedding_provider=fake_embedder,
            )

    def test_group2_solver_returns_center_without_offsets_when_tile_start_bbox_missing(self) -> None:
        solver = service.UnifiedSolverService(_fake_bundle())
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            master = root / "master.png"
            tile = root / "tile.png"
            master.write_text("master", encoding="utf-8")
            tile.write_text("tile", encoding="utf-8")

            request = contracts.SolveRequest(
                request_id="req_group2_001",
                task_hint="group2",
                inputs=contracts.Group2SolveInputs(
                    master_image=master,
                    tile_image=tile,
                    tile_start_bbox=None,
                ),
            )

            with (
                patch.object(service.UnifiedSolverService, "_load_group2_model", return_value=(_FakeGroup2Model(), 192, "cpu")),
                patch(
                    "solve.service.group2_runtime.prepare_inputs",
                    return_value=(_FakeTensor(), _FakeTensor(), {"meta": 1}),
                ),
                patch("solve.service.group2_runtime.torch_no_grad", return_value=_null_context()),
                patch("solve.service.group2_runtime.decode_bbox", return_value=[80, 24, 120, 64]),
                patch("solve.service.group2_runtime.bbox_center", return_value=[100, 44]),
            ):
                response = solver.solve(request)

            self.assertEqual(response.status, "ok")
            self.assertEqual(response.result["target_center"], [100, 44])
            self.assertNotIn("offset_x", response.result)
            self.assertNotIn("offset_y", response.result)

    def test_group2_solver_returns_offsets_when_tile_start_bbox_present(self) -> None:
        solver = service.UnifiedSolverService(_fake_bundle())
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            master = root / "master.png"
            tile = root / "tile.png"
            master.write_text("master", encoding="utf-8")
            tile.write_text("tile", encoding="utf-8")

            request = contracts.SolveRequest(
                request_id="req_group2_002",
                task_hint="group2",
                inputs=contracts.Group2SolveInputs(
                    master_image=master,
                    tile_image=tile,
                    tile_start_bbox=[10, 20, 50, 60],
                ),
            )

            with (
                patch.object(service.UnifiedSolverService, "_load_group2_model", return_value=(_FakeGroup2Model(), 192, "cpu")),
                patch(
                    "solve.service.group2_runtime.prepare_inputs",
                    return_value=(_FakeTensor(), _FakeTensor(), {"meta": 1}),
                ),
                patch("solve.service.group2_runtime.torch_no_grad", return_value=_null_context()),
                patch("solve.service.group2_runtime.decode_bbox", return_value=[80, 24, 120, 64]),
                patch("solve.service.group2_runtime.bbox_center", return_value=[100, 44]),
            ):
                response = solver.solve(request)

            self.assertEqual(response.status, "ok")
            self.assertEqual(response.result["offset_x"], 70)
            self.assertEqual(response.result["offset_y"], 4)


class _NullContext:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def _null_context() -> _NullContext:
    return _NullContext()


class _FakeGroup2Model:
    def __call__(self, master_tensor: object, tile_tensor: object) -> list[object]:
        return [object()]


class _FakeGroup1Model:
    def predict(self, *, source: str, imgsz: int, conf: float, device: str, verbose: bool) -> list[object]:
        return [object()]


class _FakeTensor:
    def to(self, device: object) -> "_FakeTensor":
        return self


def _fake_bundle(*, icon_embedder: bool = False) -> bundle.SolverBundle:
    fake_root = Path("/tmp/fake-bundle")
    return bundle.SolverBundle(
        root=fake_root,
        bundle_version="bundle_20260405",
        manifest_path=fake_root / "manifest.json",
        proposal_model_path=fake_root / "models" / "group1" / "proposal-detector" / "model.pt",
        query_model_path=fake_root / "models" / "group1" / "query-parser" / "model.pt",
        icon_embedder_model_path=fake_root / "models" / "group1" / "icon-embedder" / "model.pt",
        matcher_config_path=fake_root / "models" / "group1" / "matcher" / "config.json",
        group2_model_path=fake_root / "models" / "group2" / "locator" / "model.pt",
        router_strategy=bundle.ROUTER_STRATEGY,
    )
