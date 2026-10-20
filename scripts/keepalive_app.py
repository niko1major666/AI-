"""Streamlit 云端应用保活：定时探测，必要时用真实浏览器唤醒休眠实例。

Streamlit Community Cloud 的应用在长时间无人访问后会进入休眠（sleep），
再次访问需要等待冷启动。本脚本通过「HTTP 探测 + 浏览器唤醒」让应用保持在线。

用法：
    python scripts/keepalive_app.py              # 探测（必要时自动用浏览器唤醒）
    python scripts/keepalive_app.py --browser    # 强制用浏览器访问（真正建立 websocket）
    python scripts/keepalive_app.py --url https://xxx.streamlit.app/ --timeout 90

退出码：0 = 在线或唤醒成功；1 = 失败（便于 CI 告警）
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from typing import Any

import requests

DEFAULT_URL = os.environ.get(
    "STREAMLIT_APP_URL", "https://hdwqwu3howppf2z2xv9i2q.streamlit.app/"
)
# Streamlit Cloud 的就绪探针（返回纯文本 ok 时说明实例已启动）
HEALTH_PATH = "/~/+/_stcore/health"
# Streamlit Cloud 休眠页 / 唤醒页的特征文案
SLEEP_MARKERS = (
    "gone to sleep",
    "is sleeping",
    "get this app back up",
    "zzz",
)


def looks_sleeping(html: str) -> bool:
    """判断返回的 HTML 是否为 Streamlit Cloud 的休眠/唤醒页。"""
    low = (html or "").lower()
    return any(marker in low for marker in SLEEP_MARKERS)


def looks_healthy(status: int, body: str) -> bool:
    """判断 health 端点响应是否表明应用已就绪。"""
    return status == 200 and "ok" in (body or "").lower()


def probe_http(url: str, timeout: int = 60) -> dict[str, Any]:
    """轻量 HTTP 探测：主页可访问且 health 端点返回 ok 视为在线。"""
    base = url.rstrip("/")
    home = requests.get(base + "/", timeout=timeout)
    health = requests.get(base + HEALTH_PATH, timeout=timeout)
    return {
        "home_status": home.status_code,
        "sleeping": looks_sleeping(home.text),
        "health_status": health.status_code,
        "healthy": looks_healthy(health.status_code, health.text),
        "html_len": len(home.text),
    }


def wake_with_browser(url: str, timeout: int = 90) -> int:
    """用 Playwright 真实访问页面：建立 websocket 唤醒应用，返回渲染文本长度。"""
    from playwright.sync_api import sync_playwright

    ms = timeout * 1000
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=ms)

        # 若落在唤醒页，点一下「Yes, get this app back up!」
        for pattern in (r"get this app back up", r"back up", r"wake"):
            try:
                btn = page.get_by_role("button", name=re.compile(pattern, re.I))
                if btn.count() > 0:
                    btn.first.click(timeout=5000)
                    print(f"[browser] 点击唤醒按钮：{pattern}")
                    break
            except Exception:  # noqa: BLE001
                continue

        # 等应用真正渲染出内容（冷启动可能较慢）
        try:
            page.wait_for_function(
                "() => document.body && document.body.innerText.trim().length > 50",
                timeout=ms,
            )
        except Exception:  # noqa: BLE001
            page.wait_for_timeout(15000)

        text = page.inner_text("body")
        browser.close()
        return len(text)


def main() -> int:
    parser = argparse.ArgumentParser(description="Streamlit 云端应用保活")
    parser.add_argument("--url", default=DEFAULT_URL, help="应用地址")
    parser.add_argument("--timeout", type=int, default=60, help="单次请求/等待超时（秒）")
    parser.add_argument("--retries", type=int, default=3, help="重试次数")
    parser.add_argument("--browser", action="store_true", help="强制用浏览器真实访问")
    args = parser.parse_args()

    for attempt in range(1, args.retries + 1):
        try:
            info = probe_http(args.url, args.timeout)
            print(f"[{attempt}/{args.retries}] HTTP 探测: {info}")

            if info["healthy"] and not info["sleeping"] and not args.browser:
                print("应用在线，无需唤醒")
                return 0

            reason = "强制浏览器模式" if args.browser else "检测到休眠/未就绪"
            print(f"{reason}，启动无头浏览器访问 ...")
            rendered = wake_with_browser(args.url, args.timeout)
            print(f"[browser] 页面渲染文本 {rendered} 字")

            recheck = probe_http(args.url, args.timeout)
            print(f"[{attempt}/{args.retries}] 唤醒后复检: {recheck}")
            if recheck["healthy"] and not recheck["sleeping"]:
                print("唤醒成功，应用已在线")
                return 0
        except Exception as exc:  # noqa: BLE001
            print(f"[{attempt}/{args.retries}] 失败: {type(exc).__name__}: {exc}")

        if attempt < args.retries:
            time.sleep(15)

    print("保活失败：应用仍未就绪")
    return 1


if __name__ == "__main__":
    sys.exit(main())
