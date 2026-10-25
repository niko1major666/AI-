"""截取 Streamlit 界面预览图（README / docs 用）。

脚本会自行启动一个 headless 服务、截图、再关闭，无需手动 `streamlit run`：

    python scripts/capture_screenshots.py                 # 截技能图谱
    python scripts/capture_screenshots.py --page all      # 三页整屏 + 两个重点区域
    python scripts/capture_screenshots.py --page company_matrix    # 公司 × Top 12 技能矩阵（区域）
    python scripts/capture_screenshots.py --page gap_compare       # 多岗位对比初始界面（区域）
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

# 区域截图：只截「标题/控件 → 组件」这一块，比整屏图更适合在 README 里单点介绍
# top_last：侧栏导航本身也是 radio，取最后一个才是主区域的单选框
SECTIONS = {
    "company_matrix": {
        "nav": "技能图谱",
        "file": "company_skill_matrix.png",
        "ready": '[data-testid="stDataFrame"]',
        "top": 'text=公司 × Top 12 技能',
        "bottom": '[data-testid="stDataFrame"]',
        "top_last": False,
    },
    "gap_compare": {
        "nav": "差距报告",
        "file": "gap_compare.png",
        "ready": '[data-testid="stSelectbox"]',
        "top": '[data-testid="stRadio"]',
        "bottom": '[data-testid="stButton"]',
        "top_last": True,
        "mode": "多岗位对比",     # 先切到「多岗位对比」模式
        "company": "DeepSeek",    # 示例公司，与 gap_report.png 保持一致（默认是字母序第一家）
    },
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


def _scroll_main_to(page, locator, offset: int = 72) -> None:
    """Streamlit 的滚动发生在内层 `stMain` 容器里（window 不滚），按元素位置滚到离顶部 offset 处。"""
    locator.evaluate(
        """(el, offset) => {
            const main = document.querySelector('[data-testid="stMain"]')
                      || document.querySelector('section.main')
                      || document.querySelector('[data-testid="stAppViewContainer"]');
            if (!main) return;
            const delta = el.getBoundingClientRect().top - main.getBoundingClientRect().top;
            main.scrollTo(0, Math.max(0, main.scrollTop + delta - offset));
        }""",
        offset,
    )
    page.wait_for_timeout(1200)


def _clip_between(page, out: Path, top: dict, bottom: dict, viewport_h: int,
                  frame: dict | None = None, pad: int = 14) -> tuple:
    """截图区域 = top 元素上沿 → bottom 元素下沿；横向取主内容列（frame）以免截到控件之间被裁掉。

    Streamlit 的滚动与布局都在内层容器里，`top`/`bottom` 的 bounding_box 是视口坐标；
    超出视口的部分截到视口底（调用方需先把目标滚进视口）。
    """
    if frame:
        # 左侧从「主内容列左沿」与控件左沿的较大者开始，避免把侧栏边缘带进来
        left = max(frame["x"], min(top["x"], bottom["x"])) - pad
        right = max(frame["x"] + frame["width"],
                    top["x"] + top["width"], bottom["x"] + bottom["width"]) + pad
    else:
        left = max(0, min(top["x"], bottom["x"]) - pad)
        right = max(top["x"] + top["width"], bottom["x"] + bottom["width"]) + pad
    y = max(0, top["y"] - pad)
    height = min(bottom["y"] + bottom["height"] + pad, viewport_h) - y
    page.screenshot(path=str(out), clip={"x": left, "y": y, "width": right - left, "height": height})
    return right - left, height


def _pick_option(page, selectbox_sel: str, label: str) -> None:
    """在 Streamlit 下拉框里选中指定选项（截图用；Streamlit 的选项在 popover 里，不是原生 select）。"""
    page.locator(selectbox_sel).last.click()
    page.wait_for_timeout(800)
    option = page.get_by_role("option", name=label, exact=True)
    if option.count():
        option.first.click()
    else:                                   # 旧版 Streamlit 的选项没有 role=option
        page.get_by_text(label, exact=True).last.click()
    page.wait_for_timeout(2500)               # 选项变更触发 rerun


def _main_frame(page) -> dict | None:
    """主内容列的视口坐标（Streamlit 居中布局下即内容宽度，比逐个控件取并集更稳）。"""
    return page.evaluate(
        """() => {
            const el = document.querySelector('[data-testid="stMainBlockContainer"]')
                    || document.querySelector('.block-container')
                    || document.querySelector('[data-testid="stMain"]');
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return {x: r.x, y: r.y, width: r.width, height: r.height};
        }"""
    )


def capture_section(base: str, page_key: str, height: int, width: int, scale: float) -> Path:
    from playwright.sync_api import sync_playwright

    spec = SECTIONS[page_key]
    out = OUT_DIR / spec["file"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height},
                                device_scale_factor=scale)
        page.goto(base, wait_until="domcontentloaded", timeout=180_000)
        page.add_style_tag(content=_HIDE_CSS)
        if spec["nav"] != "技能图谱":           # 技能图谱是默认页，无需点击
            page.get_by_text(spec["nav"], exact=True).first.click()
        page.wait_for_selector(spec["ready"], timeout=180_000)
        if spec.get("mode"):                   # 差距报告页的「单岗位报告 / 多岗位对比」切换
            page.get_by_text(spec["mode"], exact=True).first.click()
            page.wait_for_timeout(3000)
        if spec.get("company"):                # 选示例公司，避免落到字母序第一家（岗位名不易读）
            _pick_option(page, '[data-testid="stSelectbox"]', spec["company"])
        top = page.locator(spec["top"]).last if spec["top_last"] else page.locator(spec["top"]).first
        bottom = page.locator(spec["bottom"]).last
        top.wait_for(timeout=180_000)
        bottom.wait_for(timeout=180_000)
        _scroll_main_to(page, top, offset=24)
        page.wait_for_timeout(1000)            # 等滚动后的图表/表格重绘
        _clip_between(page, out, top.bounding_box(), bottom.bounding_box(),
                      viewport_h=height, frame=_main_frame(page), pad=14)
        browser.close()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="截取 Streamlit 界面预览图")
    ap.add_argument("--page", default="skill_graph", choices=[*PAGES, *SECTIONS, "all"])
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
        if args.page == "all":
            keys += list(SECTIONS)
        for key in keys:
            if key in SECTIONS:
                out = capture_section(base, key, args.height, args.width, args.scale)
            else:
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
