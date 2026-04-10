from __future__ import annotations

import asyncio
import base64
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "crawl" / "ctrip_login.py"
MODULE_NAME = "tests._ctrip_login_script"

MODULE_SPEC = importlib.util.spec_from_file_location(MODULE_NAME, MODULE_PATH)
assert MODULE_SPEC is not None
assert MODULE_SPEC.loader is not None
ctrip_login = importlib.util.module_from_spec(MODULE_SPEC)
sys.modules[MODULE_NAME] = ctrip_login
MODULE_SPEC.loader.exec_module(ctrip_login)


class CtripLoginScriptTests(unittest.TestCase):
    def test_parse_capture_mode_supports_click_slider_and_both_aliases(self) -> None:
        self.assertEqual(ctrip_login.parse_capture_mode("1"), ctrip_login.CaptureMode.CLICK)
        self.assertEqual(ctrip_login.parse_capture_mode("滑块"), ctrip_login.CaptureMode.SLIDER)
        self.assertEqual(ctrip_login.parse_capture_mode("both"), ctrip_login.CaptureMode.BOTH)
        self.assertEqual(ctrip_login.parse_capture_mode("4"), ctrip_login.CaptureMode.TEST_SLIDER)

    def test_parse_capture_mode_rejects_unknown_value(self) -> None:
        with self.assertRaises(ValueError):
            ctrip_login.parse_capture_mode("unknown")

    def test_decode_data_image_url_returns_payload_and_jpg_extension(self) -> None:
        payload = b"fake-jpeg"
        src = "data:image/jpeg;base64," + base64.b64encode(payload).decode("ascii")

        image = ctrip_login.decode_data_image_url(src)

        self.assertEqual(image.media_type, "image/jpeg")
        self.assertEqual(image.extension, "jpg")
        self.assertEqual(image.payload, payload)

    def test_decode_data_image_url_rejects_non_image_data_urls(self) -> None:
        with self.assertRaises(ValueError):
            ctrip_login.decode_data_image_url("data:text/plain;base64,Zm9v")

    def test_ensure_group1_dir_creates_materials_group1_under_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = ctrip_login.ensure_group1_dir(Path(tmpdir))

            self.assertEqual(base_dir, Path(tmpdir) / "materials" / "group1")
            self.assertTrue(base_dir.is_dir())

    def test_ensure_slider_result_dir_creates_slider_output_dir_under_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = ctrip_login.ensure_slider_result_dir(Path(tmpdir))

            self.assertEqual(base_dir, Path(tmpdir) / "materials" / "result")
            self.assertTrue(base_dir.is_dir())

    def test_build_group_folder_uses_batch_id_and_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = ctrip_login.build_group_folder(Path(tmpdir), "20260408193000", 3)

            self.assertEqual(folder, Path(tmpdir) / "20260408193000_3")
            self.assertTrue(folder.is_dir())

    def test_save_inline_image_writes_expected_file(self) -> None:
        payload = b"png-bits"
        src = "data:image/png;base64," + base64.b64encode(payload).decode("ascii")

        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            path = ctrip_login.save_inline_image(src, folder, "icon")

            self.assertEqual(path, folder / "icon.png")
            self.assertIsNotNone(path)
            assert path is not None
            self.assertEqual(path.read_bytes(), payload)

    def test_save_slider_captcha_images_uses_bg_and_gap_file_names(self) -> None:
        payload = b"fake-jpeg"
        src = "data:image/jpeg;base64," + base64.b64encode(payload).decode("ascii")

        class _FakeLocator:
            def __init__(self, value: str) -> None:
                self._value = value

            async def get_attribute(self, name: str) -> str:
                self.last_name = name
                return self._value

        class _FakePage:
            def __init__(self, bg_value: str, tile_value: str) -> None:
                self.wait_for_timeout = AsyncMock()
                self._locators = {
                    ctrip_login.SLIDER_BG_SELECTOR: _FakeLocator(bg_value),
                    ctrip_login.SLIDER_TILE_SELECTOR: _FakeLocator(tile_value),
                }

            def locator(self, selector: str) -> _FakeLocator:
                return self._locators[selector]

        page = _FakePage(src, src)

        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            bg_path, gap_path = asyncio.run(ctrip_login.save_slider_captcha_images(page, folder))

            self.assertEqual(bg_path, folder / "bg.jpg")
            self.assertEqual(gap_path, folder / "gap.jpg")
            self.assertEqual(bg_path.read_bytes(), payload)
            self.assertEqual(gap_path.read_bytes(), payload)

    def test_solve_slider_drag_distance_scales_solver_offset_and_clamps(self) -> None:
        context = ctrip_login.SliderSolveContext(
            background_size=(300, 150),
            background_box={"x": 0.0, "y": 0.0, "width": 288.0, "height": 144.0},
            tile_box={"x": 24.0, "y": 30.0, "width": 38.0, "height": 42.0},
            button_box={"x": 24.0, "y": 180.0, "width": 44.0, "height": 44.0},
            track_box={"x": 0.0, "y": 180.0, "width": 288.0, "height": 44.0},
        )

        class _FakeResult:
            puzzle_piece_offset = (150, 0)

        class _FakeSolver:
            def sn_match_slider(self, **_: object) -> _FakeResult:
                return _FakeResult()

        with patch.object(ctrip_login, "_get_slider_solver", return_value=_FakeSolver()):
            distance = ctrip_login.solve_slider_drag_distance(
                context,
                background_path=Path("bg.jpg"),
                gap_path=Path("gap.jpg"),
            )

        self.assertAlmostEqual(distance, 144.0)

    def test_build_verify_jigsaw_verdict_uses_process_type_and_risk_level(self) -> None:
        success_payload = {
            "code": 0,
            "message": "Success",
            "result": {
                "risk_info": {
                    "risk_level": 0,
                    "process_type": "NONE",
                }
            },
        }
        failure_payload = {
            "code": 0,
            "message": "Success",
            "result": {
                "risk_info": {
                    "risk_level": 1,
                    "process_type": "JIGSAW",
                }
            },
        }

        success = ctrip_login._build_verify_jigsaw_verdict(
            success_payload,
            url="https://ic.ctrip.com/captcha/v4/verify_jigsaw",
            status=200,
        )
        failure = ctrip_login._build_verify_jigsaw_verdict(
            failure_payload,
            url="https://ic.ctrip.com/captcha/v4/verify_jigsaw",
            status=200,
        )

        self.assertTrue(success["passed"])
        self.assertEqual(success["process_type"], "NONE")
        self.assertEqual(success["risk_level"], 0)
        self.assertFalse(failure["passed"])
        self.assertEqual(failure["process_type"], "JIGSAW")
        self.assertEqual(failure["risk_level"], 1)

    def test_capture_both_mode_saves_slider_until_click_mode_appears(self) -> None:
        class _FakePage:
            def __init__(self) -> None:
                self.wait_for_timeout = AsyncMock()

        page = _FakePage()

        with tempfile.TemporaryDirectory() as tmpdir:
            slider_dir = Path(tmpdir) / "result"
            click_dir = Path(tmpdir) / "group1"
            slider_dir.mkdir(parents=True, exist_ok=True)
            click_dir.mkdir(parents=True, exist_ok=True)

            with (
                patch.object(
                    ctrip_login,
                    "is_click_mode",
                    AsyncMock(side_effect=[False, False, True]),
                ) as is_click_mode_mock,
                patch.object(
                    ctrip_login,
                    "save_slider_captcha_images",
                    AsyncMock(side_effect=[
                        (slider_dir / "20260409000100_1" / "bg.jpg", slider_dir / "20260409000100_1" / "gap.jpg"),
                        (slider_dir / "20260409000100_2" / "bg.jpg", slider_dir / "20260409000100_2" / "gap.jpg"),
                    ]),
                ) as save_slider_mock,
                patch.object(
                    ctrip_login,
                    "drag_slider_with_solver",
                    AsyncMock(side_effect=[81.0, 95.0]),
                ) as drag_mock,
                patch.object(
                    ctrip_login,
                    "save_click_captcha_images",
                    AsyncMock(),
                ) as save_click_mock,
            ):
                slider_index, click_index, drag_attempts = asyncio.run(
                    ctrip_login.capture_both_mode(
                        page=page,
                        slider_base_dir=slider_dir,
                        click_base_dir=click_dir,
                        batch_id="20260409000100",
                        next_slider_index=0,
                        next_click_index=0,
                        max_drag_attempts=5,
                    )
                )

        self.assertEqual((slider_index, click_index, drag_attempts), (2, 1, 2))
        self.assertEqual(is_click_mode_mock.await_count, 3)
        self.assertEqual(save_slider_mock.await_count, 2)
        self.assertEqual(drag_mock.await_count, 2)
        self.assertEqual(save_click_mock.await_count, 1)
        self.assertEqual(page.wait_for_timeout.await_count, 4)

    def test_run_slider_drag_test_returns_true_when_verify_jigsaw_passes(self) -> None:
        class _FakePage:
            def __init__(self) -> None:
                self.wait_for_timeout = AsyncMock()

        page = _FakePage()
        folder = Path("/tmp/slider-test")

        with (
            patch.object(
                ctrip_login,
                "save_slider_captcha_images",
                AsyncMock(return_value=(folder / "bg.jpg", folder / "gap.jpg")),
            ) as save_mock,
            patch.object(
                ctrip_login,
                "drag_slider_with_solver_and_verify",
                AsyncMock(
                    return_value={
                        "passed": True,
                        "distance": 88.0,
                        "process_type": "NONE",
                        "risk_level": 0,
                    }
                ),
            ) as drag_mock,
            patch.object(
                ctrip_login,
                "is_click_mode",
                AsyncMock(return_value=False),
            ) as click_mock,
            patch.object(
                ctrip_login,
                "print_slider_failure_response",
                AsyncMock(),
            ) as failure_mock,
        ):
            success = asyncio.run(ctrip_login.run_slider_drag_test(page, folder))

        self.assertTrue(success)
        save_mock.assert_awaited_once()
        drag_mock.assert_awaited_once()
        click_mock.assert_awaited_once()
        failure_mock.assert_not_awaited()

    def test_run_slider_drag_test_prints_response_when_verify_jigsaw_fails(self) -> None:
        class _FakePage:
            def __init__(self) -> None:
                self.wait_for_timeout = AsyncMock()

        page = _FakePage()
        folder = Path("/tmp/slider-test")

        with (
            patch.object(
                ctrip_login,
                "save_slider_captcha_images",
                AsyncMock(return_value=(folder / "bg.jpg", folder / "gap.jpg")),
            ),
            patch.object(
                ctrip_login,
                "drag_slider_with_solver_and_verify",
                AsyncMock(
                    return_value={
                        "passed": False,
                        "distance": 91.0,
                        "process_type": "JIGSAW",
                        "risk_level": 1,
                    }
                ),
            ),
            patch.object(
                ctrip_login,
                "print_slider_failure_response",
                AsyncMock(),
            ) as failure_mock,
        ):
            success = asyncio.run(ctrip_login.run_slider_drag_test(page, folder))

        self.assertFalse(success)
        failure_mock.assert_awaited_once()

    def test_run_slider_drag_test_prints_response_when_verify_request_errors(self) -> None:
        class _FakePage:
            def __init__(self) -> None:
                self.wait_for_timeout = AsyncMock()

        page = _FakePage()
        folder = Path("/tmp/slider-test")

        with (
            patch.object(
                ctrip_login,
                "save_slider_captcha_images",
                AsyncMock(return_value=(folder / "bg.jpg", folder / "gap.jpg")),
            ),
            patch.object(
                ctrip_login,
                "drag_slider_with_solver_and_verify",
                AsyncMock(side_effect=RuntimeError("verify timeout")),
            ),
            patch.object(
                ctrip_login,
                "print_slider_failure_response",
                AsyncMock(),
            ) as failure_mock,
        ):
            success = asyncio.run(ctrip_login.run_slider_drag_test(page, folder))

        self.assertFalse(success)
        failure_mock.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
