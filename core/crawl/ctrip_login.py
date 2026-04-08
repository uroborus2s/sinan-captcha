import asyncio
import base64
import random
import os
import time
from datetime import datetime
from playwright.async_api import async_playwright


def generate_phone():
    prefixes = [
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
    prefix = random.choice(prefixes)
    suffix = "".join([str(random.randint(0, 9)) for _ in range(8)])
    return prefix + suffix


async def save_captcha_images(page, group_folder):
    await page.wait_for_timeout(2000)

    advise = await page.locator(".advise").get_attribute("src")
    if advise and advise.startswith("data:image"):
        img_data = advise.split(",")[1]
        img_bytes = base64.b64decode(img_data)
        filepath = os.path.join(group_folder, "bg.jpg")
        with open(filepath, "wb") as f:
            f.write(img_bytes)
        print(f"背景图已保存到: {filepath}")

    image_left = await page.locator(".image-left").get_attribute("src")
    if image_left and image_left.startswith("data:image"):
        img_data = image_left.split(",")[1]
        img_bytes = base64.b64decode(img_data)
        filepath = os.path.join(group_folder, "gap.jpg")
        with open(filepath, "wb") as f:
            f.write(img_bytes)
        print(f"缺口图已保存到: {filepath}")


async def login_with_sms():
    phone_number = generate_phone()
    print(f"随机生成手机号: {phone_number}")

    count = input("请输入要采集的图片组数: ")
    count = int(count)

    base_dir = os.path.join(os.path.dirname(__file__), "..", "..", "materials", "result")
    os.makedirs(base_dir, exist_ok=True)

    start_timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    for i in range(count):
        group_folder = os.path.join(base_dir, f"{start_timestamp}_{i + 1}")
        os.makedirs(group_folder, exist_ok=True)
        print(f"\n===== 第 {i + 1}/{count} 组 =====")

        async with async_playwright() as p:
            browser = await p.chromium.launch(channel="chrome", headless=False)
            page = await browser.new_page()

            await page.goto("https://passport.ctrip.com/user/login")
            await page.wait_for_load_state("networkidle")

            code_login_tab = page.locator('a[data-testid="commonEntry"]:has-text("验证码登录")')
            await code_login_tab.click()

            await page.wait_for_timeout(1000)

            phone_input = page.locator('[data-testid="dynamicPanel"] input[data-testid="telInput"]')
            await phone_input.wait_for(timeout=3000)
            await phone_input.fill(phone_number)

            await page.wait_for_timeout(500)

            send_code_btn = page.locator(
                '[data-testid="dynamicCodeInput"] a:has-text("发送验证码")'
            )
            await send_code_btn.click()

            print(f"验证码已发送到手机号: {phone_number}")

            await save_captcha_images(page, group_folder)

            await browser.close()

        print(f"第 {i + 1} 组完成")

        if i < count - 1:
            delay = random.randint(2, 10)
            print(f"等待 {delay} 秒后继续...")
            time.sleep(delay)

    print(f"\n全部 {count} 组完成！")


if __name__ == "__main__":
    asyncio.run(login_with_sms())
