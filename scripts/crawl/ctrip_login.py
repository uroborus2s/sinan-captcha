"""Development-only helper for collecting Ctrip captcha images."""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
import random
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
GROUP1_DIR = ROOT_DIR / "materials" / "group1"
SLIDER_RESULT_DIR = ROOT_DIR / "materials" / "result"

CTRIP_LOGIN_URL = "https://passport.ctrip.com/user/login"
CODE_LOGIN_TAB_SELECTOR = 'a[data-testid="commonEntry"]:has-text("验证码登录")'
PHONE_INPUT_SELECTOR = '[data-testid="dynamicPanel"] input[data-testid="telInput"]'
SEND_CODE_BUTTON_SELECTOR = '[data-testid="dynamicCodeInput"] a:has-text("发送验证码")'
SLIDER_BUTTON_SELECTOR = ".cpt-drop-btn"
SLIDER_TRACK_SELECTOR = ".cpt-bg-bar"
CLICK_MODE_CONTAINER_SELECTOR = ".icon-image-container"
CLICK_MODE_BIG_IMAGE_SELECTOR = ".big-icon-image"
CLICK_MODE_SMALL_IMAGE_SELECTOR = ".small-icon-img"
SLIDER_BG_SELECTOR = ".advise"
SLIDER_TILE_SELECTOR = ".image-left"

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


class CaptureMode(StrEnum):
    CLICK = "click"
    SLIDER = "slider"
    BOTH = "both"


def _get_async_playwright() -> Any:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:  # pragma: no cover - depends on local dev environment
        raise RuntimeError("Playwright 未安装，请先执行 `uv sync`。") from exc
    return async_playwright


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


def choose_drag_distance(track_width: float, button_width: float) -> float:
    max_distance = max(track_width - button_width - 6.0, 24.0)
    min_distance = min(max(button_width * 0.8, 32.0), max_distance)
    if max_distance <= min_distance:
        return max_distance
    return random.uniform(min_distance, max_distance)


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
    }
    try:
        return aliases[normalized]
    except KeyError as exc:
        raise ValueError("采集模式只支持：1/点选、2/滑块、3/两者都保存。") from exc


def prompt_capture_mode() -> CaptureMode:
    prompt = "请选择采集模式：1=点选 2=滑块 3=两者都保存: "
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


async def random_drag_slider(page: Any) -> float:
    button = page.locator(SLIDER_BUTTON_SELECTOR)
    track = page.locator(SLIDER_TRACK_SELECTOR)
    await button.wait_for(timeout=5000)
    await track.wait_for(timeout=5000)

    button_box = await button.bounding_box()
    track_box = await track.bounding_box()
    if button_box is None or track_box is None:
        raise RuntimeError("未找到滑块或滑轨，无法执行随机拖动。")

    start_x = button_box["x"] + button_box["width"] / 2
    start_y = button_box["y"] + button_box["height"] / 2
    distance = choose_drag_distance(track_box["width"], button_box["width"])
    end_x = min(
        track_box["x"] + track_box["width"] - button_box["width"] / 2 - 2.0,
        start_x + distance,
    )
    end_y = start_y + random.uniform(-2.0, 2.0)

    await page.mouse.move(start_x, start_y)
    await page.mouse.down()
    await page.mouse.move(end_x, end_y, steps=random.randint(10, 24))
    await page.wait_for_timeout(random.randint(120, 260))
    await page.mouse.up()
    return end_x - start_x


async def drag_until_click_mode(page: Any, max_attempts: int = 12) -> int:
    if await is_click_mode(page):
        return 0

    for attempt in range(1, max_attempts + 1):
        distance = await random_drag_slider(page)
        print(f"第 {attempt} 次随机拖动，距离约 {distance:.1f}px")
        await page.wait_for_timeout(random.randint(600, 1100))
        if await is_click_mode(page):
            return attempt
        await page.wait_for_timeout(random.randint(300, 700))

    raise RuntimeError("随机拖动后仍未切换到点选模式。")


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
        await save_slider_captcha_images(page, slider_group_folder)

        if drag_attempts >= max_drag_attempts:
            raise RuntimeError("连续随机拖动后仍未切换到点选模式。")

        distance = await random_drag_slider(page)
        drag_attempts += 1
        print(f"第 {drag_attempts} 次随机拖动，距离约 {distance:.1f}px")
        await page.wait_for_timeout(random.randint(600, 1100))
        await page.wait_for_timeout(random.randint(300, 700))


async def login_with_sms() -> None:
    count = int(input("请输入要采集的图片组数: ").strip())
    capture_mode = prompt_capture_mode()
    click_base_dir = ensure_group1_dir() if capture_mode in {CaptureMode.CLICK, CaptureMode.BOTH} else None
    slider_base_dir = (
        ensure_slider_result_dir() if capture_mode in {CaptureMode.SLIDER, CaptureMode.BOTH} else None
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

                print(f"第 {index} 组完成，本次共随机拖动 {attempts} 次")
            finally:
                await browser.close()

        if index < count:
            delay = random.randint(2, 10)
            print(f"等待 {delay} 秒后继续...")
            await asyncio.sleep(delay)

    print(f"\n全部 {count} 组完成！")


if __name__ == "__main__":
    asyncio.run(login_with_sms())
