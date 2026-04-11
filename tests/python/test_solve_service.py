from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.solve import bundle, contracts, service


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
            group2_weight = train_root / "runs" / "group2" / "firstpass" / "weights" / "best.pt"
            for path in (proposal_weight, query_weight, group2_weight):
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
            self.assertTrue(loaded.group2_model_path.exists())


class UnifiedSolverServiceTests(unittest.TestCase):
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
                    "core.solve.service.group2_runtime.prepare_inputs",
                    return_value=(_FakeTensor(), _FakeTensor(), {"meta": 1}),
                ),
                patch("core.solve.service.group2_runtime.torch_no_grad", return_value=_null_context()),
                patch("core.solve.service.group2_runtime.decode_bbox", return_value=[80, 24, 120, 64]),
                patch("core.solve.service.group2_runtime.bbox_center", return_value=[100, 44]),
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
                    "core.solve.service.group2_runtime.prepare_inputs",
                    return_value=(_FakeTensor(), _FakeTensor(), {"meta": 1}),
                ),
                patch("core.solve.service.group2_runtime.torch_no_grad", return_value=_null_context()),
                patch("core.solve.service.group2_runtime.decode_bbox", return_value=[80, 24, 120, 64]),
                patch("core.solve.service.group2_runtime.bbox_center", return_value=[100, 44]),
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


class _FakeTensor:
    def to(self, device: object) -> "_FakeTensor":
        return self


def _fake_bundle() -> bundle.SolverBundle:
    fake_root = Path("/tmp/fake-bundle")
    return bundle.SolverBundle(
        root=fake_root,
        bundle_version="bundle_20260405",
        manifest_path=fake_root / "manifest.json",
        proposal_model_path=fake_root / "models" / "group1" / "proposal-detector" / "model.pt",
        query_model_path=fake_root / "models" / "group1" / "query-parser" / "model.pt",
        matcher_config_path=fake_root / "models" / "group1" / "matcher" / "config.json",
        group2_model_path=fake_root / "models" / "group2" / "locator" / "model.pt",
        router_strategy=bundle.ROUTER_STRATEGY,
    )
