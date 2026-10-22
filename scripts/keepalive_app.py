"""Streamlit 云端应用保活：health 探测 + 真实浏览器会话（休眠时点按钮唤醒）。

Streamlit Community Cloud 的应用在长时间无人访问后会休眠（sleep），
再次访问需要等待冷启动。本脚本通过「health 探测 + 浏览器会话」避免休眠。

2026-10 实测行为（决定了本实现的判定方式）：

- 应用就绪：``GET /~/+/_stcore/health`` → 200 ``text/plain`` 正文 ``ok``
- 应用休眠：``GET /~/+/_stcore/health`` → **400 且 body 为空**（网关拦截）
- 主页无论醒着还是休眠都是同一份前端 HTML 壳（约 9.7 KB），
  ``This app has gone to sleep`` 只由 JS 渲染 → **不能靠 HTTP 返回的 HTML 判断休眠**
- 点击 ``Yes, get this app back up!`` 后冷启动约 **2~5 分钟**，
  期间页面可能整页白屏（``body.innerText`` 为空），所以唤醒后必须轮询 health
  而不是等页面文本长度

用法：
    python scripts/keepalive_app.py               # 探测 + 建立一次真实会话（必要时唤醒）
    python scripts/keepalive_app.py --browser     # 强制走浏览器流程
    python scripts/keepalive_app.py --no-browser  # 只做 health 探测（快速自检）
    python scripts/keepalive_app.py --url https://xxx.streamlit.app/ --timeout 300

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
# Streamlit Cloud 的就绪探针：纯文本 ok = 实例已启动；休眠时网关返回 400
HEALTH_PATH = "/~/+/_stcore/health"
# 休眠页 / 唤醒页的特征文案（仅对浏览器渲染后的文本有效）
SLEEP_MARKERS = (
    "gone to sleep",
    "is sleeping",
    "get this app back up",
    "zzz",
)
# 唤醒按钮文案
WAKE_BUTTON_PATTERNS = (r"back this app up", r"back up", r"wake")
# 浏览器里判定「应用已渲染」的最小正文长度
MIN_RENDERED_CHARS = 80


def looks_sleeping(text: str) -> bool:
    """判断浏览器渲染出的页面文本是否仍是 Streamlit Cloud 的休眠/唤醒页。"""
    low = (text or "").lower()
    return any(marker in low for marker in SLEEP_MARKERS)


def looks_healthy(status: int, body: str) -> bool:
    """health 端点响应是否表明实例已就绪：200 且正文就是 ``ok``。

    主页/静态路由也会返回 200，但内容是 HTML，必须排除掉。
    """
    return status == 200 and (body or "").strip().lower() == "ok"


def probe_http(url: str, timeout: int = 30) -> dict[str, Any]:
    """探测 health 端点，返回是否就绪及原始状态（不抛异常）。"""
    base = (url or DEFAULT_URL).rstrip("/")
    try:
        resp = requests.get(base + HEALTH_PATH, timeout=timeout)
    except requests.RequestException as exc:
        return {
            "healthy": False,
            "status": 0,
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "healthy": looks_healthy(resp.status_code, resp.text),
        "status": resp.status_code,
        "content_type": resp.headers.get("content-type", ""),
        "body": (resp.text or "")[:16],
    }


def wait_until_healthy(url: str, timeout: int, interval: float = 5.0) -> bool:
    """轮询 health 直到就绪或超时（冷启动可能 2~5 分钟）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if probe_http(url, timeout=20)["healthy"]:
            return True
        time.sleep(interval)
    return False



def wake_with_browser(url: str, timeout: int = 300, keep: int = 8) -> dict[str, Any]:
    """用 Playwright 真实访问：建立 websocket 会话，休眠时点按钮并等待就绪。

    返回 ``{"clicked", "ready", "text"}``；就绪判据是 health 重新返回 ok，
    而不是页面文本长度（休眠页本身就有近 200 字）。
    """
    from playwright.sync_api import sync_playwright

    base = url.rstrip("/")
    result: dict[str, Any] = {"clicked": False, "ready": False, "text": ""}

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        try:
            page.goto(
                base + "/",
                wait_until="domcontentloaded",
                timeout=min(timeout, 120) * 1000,
            )
            page.wait_for_timeout(3000)
            first_text = page.inner_text("body")
            print(f"[browser] 首屏文本 {len(first_text)} 字：{first_text[:60]!r}")

            if looks_sleeping(first_text) or not probe_http(base)["healthy"]:
                for pattern in WAKE_BUTTON_PATTERNS:
                    try:
                        btn = page.get_by_role("button", name=re.compile(pattern, re.I))
                        if btn.count() > 0:
                            btn.first.click(timeout=8000)
                            result["clicked"] = True
                            print(f"[browser] 已点击唤醒按钮：{pattern}")
                            break
                    except Exception:  # noqa: BLE001
                        continue
            else:
                print("[browser] 应用已就绪，直接建立会话")

            # 冷启动期间页面可能白屏，用 health 轮询作为唯一可靠判据
            deadline = time.time() + timeout
            while time.time() < deadline:
                if probe_http(base, timeout=20)["healthy"]:
                    result["ready"] = True
                    break
                page.wait_for_timeout(5000)

            if result["ready"]:
                try:  # 等前端真正渲染出内容，确保 websocket 有往返
                    page.wait_for_function(
                        f"() => document.body && "
                        f"document.body.innerText.trim().length > {MIN_RENDERED_CHARS}",
                        timeout=60000,
                    )
                except Exception:  # noqa: BLE001
                    pass
                page.wait_for_timeout(keep * 1000)

            result["text"] = page.inner_text("body").strip()[:120]
        finally:
            browser.close()

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Streamlit 云端应用保活")
    parser.add_argument("--url", default=DEFAULT_URL, help="应用地址")
    parser.add_argument(
        "--timeout", type=int, default=300, help="唤醒等待上限（秒，冷启动可长达 5 分钟）"
    )
    parser.add_argument("--retries", type=int, default=2, help="重试次数")
    parser.add_argument(
        "--keep", type=int, default=8, help="会话停留秒数（确保 websocket 往返）"
    )
    parser.add_argument("--browser", action="store_true", help="强制走浏览器流程")
    parser.add_argument("--no-browser", action="store_true", help="只做 health 探测，不开浏览器")
    args = parser.parse_args()

    for attempt in range(1, args.retries + 1):
        try:
            info = probe_http(args.url, timeout=min(args.timeout, 30))
            print(f"[{attempt}/{args.retries}] health 探测: {info}")

            if args.no_browser:
                if info["healthy"]:
                    print("应用在线（仅探测，未建立会话）")
                    return 0
                print("应用休眠/未就绪（--no-browser 不做唤醒）")
                return 1

            if info["healthy"] and not args.browser:
                print("实例已就绪，建立一次真实会话以重置闲置计时 ...")
                session = wake_with_browser(args.url, timeout=60, keep=args.keep)
                print(
                    f"[browser] 会话结束: clicked={session['clicked']} "
                    f"ready={session['ready']}"
                )
                if session["ready"]:
                    print("保活成功：应用在线")
                    return 0
                print("会话后未确认就绪，转为唤醒流程")
            else:
                print("应用休眠/未就绪，启动浏览器唤醒 ...")

            session = wake_with_browser(args.url, timeout=args.timeout, keep=args.keep)
            print(
                f"[browser] clicked={session['clicked']} ready={session['ready']} "
                f"text={session['text']!r}"
            )
            if session["ready"]:
                print("唤醒成功，应用已在线")
                return 0
        except Exception as exc:  # noqa: BLE001
            print(f"[{attempt}/{args.retries}] 失败: {type(exc).__name__}: {exc}")

        if attempt < args.retries:
            time.sleep(10)

    print("保活失败：应用仍未就绪")
    return 1


if __name__ == "__main__":
    sys.exit(main())
