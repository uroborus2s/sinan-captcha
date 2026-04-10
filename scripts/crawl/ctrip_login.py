"""Development-only helper for collecting Ctrip captcha images."""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import json
from pathlib import Path
import random
import sys
import tempfile
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
GROUP1_DIR = ROOT_DIR / "materials" / "group1"
SLIDER_RESULT_DIR = ROOT_DIR / "materials" / "result"
SOLVER_SRC_DIR = ROOT_DIR / "solver" / "src"

CTRIP_LOGIN_URL = "https://passport.ctrip.com/user/login"
CODE_LOGIN_TAB_SELECTOR = 'a[data-testid="commonEntry"]:has-text("验证码登录")'
PHONE_INPUT_SELECTOR = '[data-testid="dynamicPanel"] input[data-testid="telInput"]'
SEND_CODE_BUTTON_SELECTOR = '[data-testid="dynamicCodeInput"] a:has-text("发送验证码")'
SLIDER_BUTTON_SELECTOR = ".cpt-drop-btn"
SLIDER_TRACK_SELECTOR = ".cpt-bg-bar"
CLICK_MODE_CONTAINER_SELECTOR = ".icon-image-container"
CLICK_MODE_BIG_IMAGE_SELECTOR = ".big-icon-image"
CLICK_MODE_SMALL_IMAGE_SELECTOR = ".small-icon-img"
CAPTCHA_RESPONSE_SELECTOR = ".cpt-drop-box"
SLIDER_BG_SELECTOR = ".advise"
SLIDER_TILE_SELECTOR = ".image-left"
VERIFY_JIGSAW_PATH_FRAGMENT = "/captcha/v4/verify_jigsaw"

PHONE_PREFIXES = [
    "130",
    "131",
    "132",
    "133",
    "134",
    "135",
    "136",
    "137",
    "138",
    "139",
    "150",
    "151",
    "152",
    "153",
    "155",
    "156",
    "157",
    "158",
    "159",
    "180",
    "181",
    "182",
    "183",
    "184",
    "185",
    "186",
    "187",
    "188",
    "189",
]


@dataclass(frozen=True)
class InlineImage:
    media_type: str
    extension: str
    payload: bytes


@dataclass(frozen=True)
class SliderSolveContext:
    background_size: tuple[int, int]
    background_box: dict[str, float]
    tile_box: dict[str, float]
    button_box: dict[str, float]
    track_box: dict[str, float]


class CaptureMode(StrEnum):
    CLICK = "click"
    SLIDER = "slider"
    BOTH = "both"
    TEST_SLIDER = "test_slider"


def _get_async_playwright() -> Any:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:  # pragma: no cover - depends on local dev environment
        raise RuntimeError("Playwright 未安装，请先执行 `uv sync`。") from exc
    return async_playwright


def _get_pillow_image() -> Any:
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - depends on local dev environment
        raise RuntimeError("Pillow 未安装，请先执行 `uv sync --extra train`。") from exc
    return Image


def _get_slider_solver() -> Any:
    if str(SOLVER_SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SOLVER_SRC_DIR))
    try:
        from sinanz import CaptchaSolver
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on local dev environment
        raise RuntimeError(
            "未找到本地 solver 运行依赖，请先安装 `solver` wheel，或在仓库根执行 `uv sync --extra train`。"
        ) from exc
    return CaptchaSolver(device="cpu")


def generate_phone() -> str:
    prefix = random.choice(PHONE_PREFIXES)
    suffix = "".join(str(random.randint(0, 9)) for _ in range(8))
    return prefix + suffix


def is_data_image_url(src: str | None) -> bool:
    return bool(src and src.startswith("data:image") and "," in src)


def _image_extension_from_media_type(media_type: str) -> str:
    subtype = media_type.split("/", 1)[1].lower()
    subtype = subtype.split("+", 1)[0]
    if subtype in {"jpeg", "pjpeg"}:
        return "jpg"
    return subtype


def decode_data_image_url(src: str) -> InlineImage:
    if not is_data_image_url(src):
        raise ValueError("只支持 data:image base64 URL。")

    header, encoded = src.split(",", 1)
    media_type = header.removeprefix("data:").split(";", 1)[0].lower()
    if ";base64" not in header:
        raise ValueError("当前只支持 base64 编码图片。")

    return InlineImage(
        media_type=media_type,
        extension=_image_extension_from_media_type(media_type),
        payload=base64.b64decode(encoded.strip(), validate=True),
    )


def ensure_group1_dir(root_dir: Path = ROOT_DIR) -> Path:
    base_dir = root_dir / "materials" / "group1"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def ensure_slider_result_dir(root_dir: Path = ROOT_DIR) -> Path:
    base_dir = root_dir / "materials" / "result"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def build_group_folder(base_dir: Path, batch_id: str, index: int) -> Path:
    group_folder = base_dir / f"{batch_id}_{index}"
    group_folder.mkdir(parents=True, exist_ok=True)
    return group_folder


def save_inline_image(src: str | None, group_folder: Path, stem: str) -> Path | None:
    if not is_data_image_url(src):
        return None

    image = decode_data_image_url(src)
    path = group_folder / f"{stem}.{image.extension}"
    path.write_bytes(image.payload)
    return path


def parse_capture_mode(raw: str) -> CaptureMode:
    normalized = raw.strip().lower()
    aliases = {
        "1": CaptureMode.CLICK,
        "点选": CaptureMode.CLICK,
        "click": CaptureMode.CLICK,
        "2": CaptureMode.SLIDER,
        "滑块": CaptureMode.SLIDER,
        "slider": CaptureMode.SLIDER,
        "3": CaptureMode.BOTH,
        "两者都保存": CaptureMode.BOTH,
        "都保存": CaptureMode.BOTH,
        "both": CaptureMode.BOTH,
        "4": CaptureMode.TEST_SLIDER,
        "测试滑动": CaptureMode.TEST_SLIDER,
        "测试拖动": CaptureMode.TEST_SLIDER,
        "test": CaptureMode.TEST_SLIDER,
        "test_slider": CaptureMode.TEST_SLIDER,
    }
    try:
        return aliases[normalized]
    except KeyError as exc:
        raise ValueError("采集模式只支持：1/点选、2/滑块、3/两者都保存、4/测试滑动。") from exc


def prompt_capture_mode() -> CaptureMode:
    prompt = "请选择采集模式：1=点选 2=滑块 3=两者都保存 4=测试滑动: "
    while True:
        try:
            return parse_capture_mode(input(prompt))
        except ValueError as exc:
            print(exc)


async def open_sms_login(page: Any, phone_number: str) -> None:
    await page.goto(CTRIP_LOGIN_URL)
    await page.wait_for_load_state("networkidle")

    code_login_tab = page.locator(CODE_LOGIN_TAB_SELECTOR)
    await code_login_tab.click()
    await page.wait_for_timeout(1000)

    phone_input = page.locator(PHONE_INPUT_SELECTOR)
    await phone_input.wait_for(timeout=3000)
    await phone_input.fill(phone_number)
    await page.wait_for_timeout(500)

    send_code_btn = page.locator(SEND_CODE_BUTTON_SELECTOR)
    await send_code_btn.click()
    print(f"验证码已发送到手机号: {phone_number}")


async def save_slider_captcha_images(page: Any, group_folder: Path) -> tuple[Path, Path]:
    await page.wait_for_timeout(2000)

    bg_src = await page.locator(SLIDER_BG_SELECTOR).get_attribute("src")
    tile_src = await page.locator(SLIDER_TILE_SELECTOR).get_attribute("src")
    bg_path = save_inline_image(bg_src, group_folder, "bg")
    tile_path = save_inline_image(tile_src, group_folder, "gap")

    if bg_path is None or tile_path is None:
        raise RuntimeError("滑块模式图片不存在或不是 data:image。")

    print(f"滑块背景图已保存到: {bg_path}")
    print(f"滑块拼图块已保存到: {tile_path}")
    return bg_path, tile_path


async def is_click_mode(page: Any) -> bool:
    container = page.locator(CLICK_MODE_CONTAINER_SELECTOR)
    if not await container.is_visible():
        return False

    bg_src = await page.locator(CLICK_MODE_BIG_IMAGE_SELECTOR).get_attribute("src")
    icon_src = await page.locator(CLICK_MODE_SMALL_IMAGE_SELECTOR).get_attribute("src")
    return is_data_image_url(bg_src) and is_data_image_url(icon_src)


async def _safe_get_attribute(page: Any, selector: str, attribute: str) -> str | None:
    try:
        return await page.locator(selector).get_attribute(attribute)
    except Exception:
        return None


async def _safe_outer_html(page: Any, selector: str) -> str | None:
    try:
        return await page.locator(selector).evaluate("node => node.outerHTML")
    except Exception:
        return None


async def collect_slider_response(page: Any) -> dict[str, Any]:
    response = {
        "page_url": getattr(page, "url", None),
        "is_click_mode": await is_click_mode(page),
        "slider_bg_src": await _safe_get_attribute(page, SLIDER_BG_SELECTOR, "src"),
        "slider_tile_src": await _safe_get_attribute(page, SLIDER_TILE_SELECTOR, "src"),
        "slider_tile_style": await _safe_get_attribute(page, SLIDER_TILE_SELECTOR, "style"),
        "slider_button_style": await _safe_get_attribute(page, SLIDER_BUTTON_SELECTOR, "style"),
        "slider_track_style": await _safe_get_attribute(page, SLIDER_TRACK_SELECTOR, "style"),
        "captcha_response_html": await _safe_outer_html(page, CAPTCHA_RESPONSE_SELECTOR),
    }
    html = response["captcha_response_html"]
    if isinstance(html, str) and len(html) > 1600:
        response["captcha_response_html"] = html[:1600] + "...(truncated)"
    return response


async def save_slider_failure_screenshot(page: Any, group_folder: Path) -> Path | None:
    screenshot_path = group_folder / "failure.png"
    try:
        await page.screenshot(path=str(screenshot_path), full_page=True)
    except Exception:
        return None
    return screenshot_path


async def print_slider_failure_response(
    page: Any,
    *,
    reason: str,
    group_folder: Path | None = None,
    verify_jigsaw: dict[str, Any] | None = None,
) -> None:
    response = await collect_slider_response(page)
    screenshot_path = None
    if group_folder is not None:
        screenshot_path = await save_slider_failure_screenshot(page, group_folder)
    payload = {
        "reason": reason,
        "failure_screenshot": str(screenshot_path) if screenshot_path is not None else None,
        "verify_jigsaw": verify_jigsaw,
        "response": response,
    }
    print("滑动失败，当前页面响应：")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _require_bounding_box(box: dict[str, float] | None, *, field: str) -> dict[str, float]:
    if box is None:
        raise RuntimeError(f"未找到 `{field}` 的可见区域。")
    return box


def _display_box_to_image_bbox(
    box: dict[str, float],
    *,
    container_box: dict[str, float],
    image_size: tuple[int, int],
) -> tuple[int, int, int, int]:
    image_width, image_height = image_size
    scale_x = image_width / max(container_box["width"], 1.0)
    scale_y = image_height / max(container_box["height"], 1.0)
    relative_x = max(0.0, box["x"] - container_box["x"])
    relative_y = max(0.0, box["y"] - container_box["y"])
    x1 = int(round(relative_x * scale_x))
    y1 = int(round(relative_y * scale_y))
    width = max(1, int(round(box["width"] * scale_x)))
    height = max(1, int(round(box["height"] * scale_y)))
    return (x1, y1, x1 + width, y1 + height)


def solve_slider_drag_distance(
    context: SliderSolveContext,
    *,
    background_path: Path,
    gap_path: Path,
) -> float:
    solver = _get_slider_solver()
    start_bbox = _display_box_to_image_bbox(
        context.tile_box,
        container_box=context.background_box,
        image_size=context.background_size,
    )
    result = solver.sn_match_slider(
        background_image=background_path,
        puzzle_piece_image=gap_path,
        puzzle_piece_start_bbox=start_bbox,
    )
    if result.puzzle_piece_offset is None:
        raise RuntimeError("solver 未返回滑块偏移量。")

    display_scale_x = context.background_box["width"] / max(context.background_size[0], 1)
    desired_distance = float(result.puzzle_piece_offset[0]) * display_scale_x
    button_center_x = context.button_box["x"] + context.button_box["width"] / 2
    min_center_x = context.track_box["x"] + context.button_box["width"] / 2
    max_center_x = (
        context.track_box["x"] + context.track_box["width"] - context.button_box["width"] / 2 - 2.0
    )
    min_distance = min_center_x - button_center_x
    max_distance = max_center_x - button_center_x
    return max(min(desired_distance, max_distance), min_distance)


async def _read_slider_solve_context(page: Any, background_path: Path) -> SliderSolveContext:
    image_cls = _get_pillow_image()
    with image_cls.open(background_path) as image:
        background_size = image.size

    background = page.locator(SLIDER_BG_SELECTOR)
    tile = page.locator(SLIDER_TILE_SELECTOR)
    button = page.locator(SLIDER_BUTTON_SELECTOR)
    track = page.locator(SLIDER_TRACK_SELECTOR)
    await button.wait_for(timeout=5000)
    await track.wait_for(timeout=5000)
    background_box = _require_bounding_box(await background.bounding_box(), field="slider background")
    tile_box = _require_bounding_box(await tile.bounding_box(), field="slider tile")
    button_box = _require_bounding_box(await button.bounding_box(), field="slider button")
    track_box = _require_bounding_box(await track.bounding_box(), field="slider track")
    return SliderSolveContext(
        background_size=background_size,
        background_box=background_box,
        tile_box=tile_box,
        button_box=button_box,
        track_box=track_box,
    )


async def _perform_human_drag(page: Any, context: SliderSolveContext, distance: float) -> float:
    start_x = context.button_box["x"] + context.button_box["width"] / 2
    start_y = context.button_box["y"] + context.button_box["height"] / 2
    overshoot = min(8.0, max(2.0, abs(distance) * 0.04))
    if distance >= 0:
        targets = [
            start_x + distance * 0.55,
            start_x + distance * 0.9 + overshoot,
            start_x + distance,
        ]
    else:
        targets = [
            start_x + distance * 0.55,
            start_x + distance * 0.9 - overshoot,
            start_x + distance,
        ]

    await page.mouse.move(start_x, start_y)
    await page.mouse.down()
    current_x = start_x
    for target_x in targets:
        steps = max(4, int(abs(target_x - current_x) / 8.0))
        await page.mouse.move(target_x, start_y + random.uniform(-1.5, 1.5), steps=steps)
        current_x = target_x
    await page.wait_for_timeout(random.randint(120, 220))
    await page.mouse.up()
    return distance


async def drag_slider_with_solver(page: Any, background_path: Path, gap_path: Path) -> float:
    context = await _read_slider_solve_context(page, background_path)
    distance = solve_slider_drag_distance(
        context,
        background_path=background_path,
        gap_path=gap_path,
    )
    await _perform_human_drag(page, context, distance)
    return distance


def _build_verify_jigsaw_verdict(
    payload: dict[str, Any],
    *,
    url: str | None = None,
    status: int | None = None,
) -> dict[str, Any]:
    result = payload.get("result")
    result_dict = result if isinstance(result, dict) else {}
    risk_info = result_dict.get("risk_info")
    risk_info_dict = risk_info if isinstance(risk_info, dict) else {}
    process_type = risk_info_dict.get("process_type")
    risk_level = risk_info_dict.get("risk_level")
    code = payload.get("code")
    message = payload.get("message")
    passed = code == 0 and risk_level == 0 and process_type == "NONE"
    return {
        "passed": passed,
        "code": code,
        "message": message,
        "url": url,
        "status": status,
        "risk_level": risk_level,
        "process_type": process_type,
        "token": result_dict.get("token"),
        "payload": payload,
    }


async def drag_slider_with_solver_and_verify(
    page: Any,
    background_path: Path,
    gap_path: Path,
) -> dict[str, Any]:
    try:
        async with page.expect_response(
            lambda response: VERIFY_JIGSAW_PATH_FRAGMENT in getattr(response, "url", "")
            and getattr(getattr(response, "request", None), "method", None) == "POST",
            timeout=8_000,
        ) as response_info:
            distance = await drag_slider_with_solver(page, background_path, gap_path)
        response = await response_info.value
    except Exception as exc:
        raise RuntimeError("等待 verify_jigsaw 响应失败。") from exc

    try:
        payload = await response.json()
    except Exception as exc:
        raise RuntimeError("verify_jigsaw 响应不是可解析的 JSON。") from exc

    verdict = _build_verify_jigsaw_verdict(
        payload,
        url=getattr(response, "url", None),
        status=getattr(response, "status", None),
    )
    verdict["distance"] = distance
    return verdict


async def run_slider_drag_test(page: Any, group_folder: Path) -> bool:
    bg_path, gap_path = await save_slider_captcha_images(page, group_folder)
    try:
        verdict = await drag_slider_with_solver_and_verify(page, bg_path, gap_path)
    except Exception as exc:
        await print_slider_failure_response(
            page,
            reason=f"slider_verify_exception: {exc}",
            group_folder=group_folder,
        )
        return False

    distance = float(verdict["distance"])
    process_type = verdict.get("process_type")
    risk_level = verdict.get("risk_level")
    await page.wait_for_timeout(random.randint(600, 1100))
    if verdict.get("passed"):
        click_mode = await is_click_mode(page)
        if click_mode:
            print(
                f"测试滑动成功，距离约 {distance:.1f}px，"
                f"verify_jigsaw={process_type}/{risk_level}，已切换到点选模式。"
            )
        else:
            print(
                f"测试滑动成功，距离约 {distance:.1f}px，"
                f"verify_jigsaw={process_type}/{risk_level}，"
                "服务端已通过但页面未切到点选模式。"
            )
        return True

    await print_slider_failure_response(
        page,
        reason=(
            "verify_jigsaw_failed: "
            f"distance={distance:.1f}, process_type={process_type}, risk_level={risk_level}"
        ),
        group_folder=group_folder,
        verify_jigsaw=verdict,
    )
    return False


async def drag_until_click_mode(page: Any, max_attempts: int = 12) -> int:
    if await is_click_mode(page):
        return 0

    for attempt in range(1, max_attempts + 1):
        with tempfile.TemporaryDirectory(prefix="ctrip-slider-") as tmpdir:
            temp_dir = Path(tmpdir)
            bg_path, gap_path = await save_slider_captcha_images(page, temp_dir)
            distance = await drag_slider_with_solver(page, bg_path, gap_path)
        print(f"第 {attempt} 次模型拖动，距离约 {distance:.1f}px")
        await page.wait_for_timeout(random.randint(600, 1100))
        if await is_click_mode(page):
            return attempt
        await page.wait_for_timeout(random.randint(300, 700))

    raise RuntimeError("模型拖动后仍未切换到点选模式。")


async def save_click_captcha_images(page: Any, group_folder: Path) -> tuple[Path, Path]:
    await page.wait_for_timeout(500)

    bg_src = await page.locator(CLICK_MODE_BIG_IMAGE_SELECTOR).get_attribute("src")
    icon_src = await page.locator(CLICK_MODE_SMALL_IMAGE_SELECTOR).get_attribute("src")
    bg_path = save_inline_image(bg_src, group_folder, "bg")
    icon_path = save_inline_image(icon_src, group_folder, "icon")

    if bg_path is None or icon_path is None:
        raise RuntimeError("点选模式图片不存在或不是 data:image。")

    print(f"点选背景图已保存到: {bg_path}")
    print(f"点选小图已保存到: {icon_path}")
    return bg_path, icon_path


async def capture_both_mode(
    page: Any,
    slider_base_dir: Path,
    click_base_dir: Path,
    batch_id: str,
    next_slider_index: int,
    next_click_index: int,
    max_drag_attempts: int = 12,
) -> tuple[int, int, int]:
    drag_attempts = 0

    while True:
        if await is_click_mode(page):
            next_click_index += 1
            click_group_folder = build_group_folder(click_base_dir, batch_id, next_click_index)
            await save_click_captcha_images(page, click_group_folder)
            return next_slider_index, next_click_index, drag_attempts

        next_slider_index += 1
        slider_group_folder = build_group_folder(slider_base_dir, batch_id, next_slider_index)
        bg_path, gap_path = await save_slider_captcha_images(page, slider_group_folder)

        if drag_attempts >= max_drag_attempts:
            raise RuntimeError("连续模型拖动后仍未切换到点选模式。")

        distance = await drag_slider_with_solver(page, bg_path, gap_path)
        drag_attempts += 1
        print(f"第 {drag_attempts} 次模型拖动，距离约 {distance:.1f}px")
        await page.wait_for_timeout(random.randint(600, 1100))
        await page.wait_for_timeout(random.randint(300, 700))


async def login_with_sms() -> None:
    count = int(input("请输入要采集的图片组数: ").strip())
    capture_mode = prompt_capture_mode()
    click_base_dir = ensure_group1_dir() if capture_mode in {CaptureMode.CLICK, CaptureMode.BOTH} else None
    slider_base_dir = (
        ensure_slider_result_dir()
        if capture_mode in {CaptureMode.SLIDER, CaptureMode.BOTH, CaptureMode.TEST_SLIDER}
        else None
    )
    batch_id = datetime.now().strftime("%Y%m%d%H%M%S")
    async_playwright = _get_async_playwright()
    slider_group_index = 0
    click_group_index = 0

    for index in range(1, count + 1):
        phone_number = generate_phone()
        print(f"\n===== 第 {index}/{count} 组 =====")
        print(f"随机生成手机号: {phone_number}")
        if capture_mode is CaptureMode.CLICK:
            print("当前模式：点选")
        elif capture_mode is CaptureMode.SLIDER:
            print("当前模式：滑块")
        elif capture_mode is CaptureMode.TEST_SLIDER:
            print("当前模式：测试滑动")
        else:
            print("当前模式：两者都保存")

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(channel="chrome", headless=False)
            page = await browser.new_page()

            try:
                await open_sms_login(page, phone_number)
                attempts = 0
                if capture_mode is CaptureMode.SLIDER:
                    assert slider_base_dir is not None
                    slider_group_index += 1
                    slider_group_folder = build_group_folder(
                        slider_base_dir,
                        batch_id,
                        slider_group_index,
                    )
                    await save_slider_captcha_images(page, slider_group_folder)
                elif capture_mode is CaptureMode.TEST_SLIDER:
                    assert slider_base_dir is not None
                    slider_group_index += 1
                    slider_group_folder = build_group_folder(
                        slider_base_dir,
                        batch_id,
                        slider_group_index,
                    )
                    success = await run_slider_drag_test(page, slider_group_folder)
                    print(f"第 {index} 组测试滑动结果：{'成功' if success else '失败'}")
                elif capture_mode is CaptureMode.CLICK:
                    assert click_base_dir is not None
                    click_group_index += 1
                    click_group_folder = build_group_folder(
                        click_base_dir,
                        batch_id,
                        click_group_index,
                    )
                    attempts = await drag_until_click_mode(page)
                    await save_click_captcha_images(page, click_group_folder)
                else:
                    assert slider_base_dir is not None
                    assert click_base_dir is not None
                    slider_group_index, click_group_index, attempts = await capture_both_mode(
                        page=page,
                        slider_base_dir=slider_base_dir,
                        click_base_dir=click_base_dir,
                        batch_id=batch_id,
                        next_slider_index=slider_group_index,
                        next_click_index=click_group_index,
                    )

                print(f"第 {index} 组完成，本次共模型拖动 {attempts} 次")
            finally:
                await browser.close()

        if index < count:
            delay = random.randint(2, 10)
            print(f"等待 {delay} 秒后继续...")
            await asyncio.sleep(delay)

    print(f"\n全部 {count} 组完成！")


if __name__ == "__main__":
    asyncio.run(login_with_sms())
