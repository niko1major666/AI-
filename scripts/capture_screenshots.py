"""截取 Streamlit 界面预览图（README / docs 用）。

脚本会自行启动一个 headless 服务、截图、再关闭，无需手动 `streamlit run`：

    python scripts/capture_screenshots.py                 # 截技能图谱
    python scripts/capture_screenshots.py --page all      # 截三页
    python scripts/capture_screenshots.py --page skill_graph --height 1000

依赖：playwright（已装 chromium）、Pillow。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "images"

# 隐藏 Streamlit 自带的 Deploy 工具栏 / 主菜单 / 页脚，让截图更干净
_HIDE_CSS = """
[data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer { display: none !important; }
header[data-testid="stHeader"] { background: transparent !important; }
"""

# page_key -> (侧栏导航文字, 输出文件名, 就绪选择器)
PAGES = {
    "skill_graph": ("技能图谱", "skill_graph.png", '[data-testid="stVegaLiteChart"]'),
    "resume_match": ("简历匹配", "resume_match.png", '[data-testid="stFileUploader"]'),
    "gap_report": ("差距报告", "gap_report.png", '[data-testid="stSelectbox"]'),
}


def _wait_health(base: str, timeout: int = 120) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base}/_stcore/health", timeout=3) as r:
                if r.read().decode().strip() == "ok":
                    return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1)
    return False


def _start_server(port: int) -> subprocess.Popen:
    cmd = [sys.executable, "-m", "streamlit", "run", str(ROOT / "src" / "app" / "app.py"),
           "--server.port", str(port), "--server.headless", "true",
           "--browser.gatherUsageStats", "false"]
    return subprocess.Popen(cmd, cwd=str(ROOT),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def capture(base: str, page_key: str, height: int, width: int, scale: float) -> Path:
    from playwright.sync_api import sync_playwright

    label, filename, ready = PAGES[page_key]
    out = OUT_DIR / filename
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height},
                                device_scale_factor=scale)
        page.goto(base, wait_until="domcontentloaded", timeout=180_000)
        page.add_style_tag(content=_HIDE_CSS)
        if page_key != "skill_graph":
            page.get_by_text(label, exact=True).first.click()
        page.wait_for_selector(ready, timeout=180_000)
        page.wait_for_timeout(3000)          # 等 plotly / 图表动画收尾
        page.screenshot(path=str(out), full_page=False)
        browser.close()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="截取 Streamlit 界面预览图")
    ap.add_argument("--page", default="skill_graph", choices=[*PAGES, "all"])
    ap.add_argument("--port", type=int, default=8599)
    ap.add_argument("--width", type=int, default=1257)
    ap.add_argument("--height", type=int, default=1000)
    ap.add_argument("--scale", type=float, default=2.0, help="device_scale_factor（2 = 高清）")
    args = ap.parse_args(argv)

    base = f"http://localhost:{args.port}"
    proc = _start_server(args.port)
    try:
        if not _wait_health(base):
            print("Streamlit 启动超时，请检查端口占用或依赖")
            return 1
        keys = list(PAGES) if args.page == "all" else [args.page]
        for key in keys:
            out = capture(base, key, args.height, args.width, args.scale)
            from PIL import Image
            print(f"{key}: {out} {Image.open(out).size}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
