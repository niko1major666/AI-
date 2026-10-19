"""DeepSeek 招聘爬虫：列表 + 详情 JD。

用法：
  python -m src.crawler.deepseek --list                 # 抓列表 → data/raw/deepseek_ai_jobs.csv
  python -m src.crawler.deepseek --details 0 8          # 抓第 0~7 个详情（分批，增量存 JSON）
  python -m src.crawler.deepseek --details 8 8          # 抓第 8~15 个详情
  python -m src.crawler.deepseek --final                # 合并列表 + 详情 → 最终 CSV

说明：DeepSeek 用 Moka 平台，列表/详情接口加密（necromancer），
故用 Playwright 渲染后 DOM 抓取；详情页渲染后 JD 是明文。
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright

URL = "https://talent.deepseek.com/"
LIST_CSV = "data/raw/deepseek_ai_jobs.csv"
DETAILS_JSON = "data/raw/_deepseek_details.json"


def _grab_list(page) -> list[dict]:
    for _ in range(8):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(800)
    items = page.evaluate("""() => Array.from(document.querySelectorAll('a[href*="mokahr"]'))
        .map(a => ({href: a.href, text: (a.innerText||'').trim().replace(/\\s+/g,' ')}))
        .filter(x => x.text && x.href)""")
    rows, seen = [], set()
    for it in items:
        m = re.search(r"/job/([0-9a-f-]+)", it["href"])
        jid = m.group(1) if m else it["href"][-20:]
        if jid in seen:
            continue
        seen.add(jid)
        rows.append({
            "job_id": jid[:20], "company": "DeepSeek",
            "title": it["text"][:40], "location": "", "salary": "",
            "experience": "", "education": "", "jd_text": it["text"],
            "department": "", "publish_time": "", "_href": it["href"],
        })
    return rows


def _load_details() -> dict:
    p = Path(DETAILS_JSON)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _save_details(details: dict) -> None:
    Path(DETAILS_JSON).write_text(json.dumps(details, ensure_ascii=False, indent=1), encoding="utf-8")


def _extract_jd(body: str) -> str:
    """从详情页正文里截取 JD 主体（职位描述之后）。"""
    m = re.search(r"(职位描述|岗位职责|工作职责|职位要求|Responsibilities|岗位描述)", body)
    if m:
        body = body[m.start():]
    return re.sub(r"\s+", " ", body).strip()[:2000]


def cmd_list() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=40000)
        page.wait_for_timeout(6000)
        rows = _grab_list(page)
        browser.close()
    pd.DataFrame(rows).to_csv(LIST_CSV, index=False, encoding="utf-8-sig")
    print(f"列表 {len(rows)} 条 → {LIST_CSV}")


def cmd_details(start: int, count: int) -> None:
    rows = _grab_list_cached()
    details = _load_details()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        end = min(start + count, len(rows))
        for r in rows[start:end]:
            jid = r["job_id"]
            if jid in details and len(details[jid]) > 30:
                continue
            try:
                page.goto(r["_href"], wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2200)
                details[jid] = _extract_jd(page.inner_text("body"))
            except Exception:
                details[jid] = r["jd_text"]
            time.sleep(0.3)
        browser.close()
    _save_details(details)
    print(f"详情进度 {start}~{end}/{len(rows)}，累计 {len(details)} 条")


def _grab_list_cached() -> list[dict]:
    if not Path(LIST_CSV).exists():
        cmd_list()
    return pd.read_csv(LIST_CSV).to_dict("records")


def cmd_final() -> None:
    rows = _grab_list_cached()
    details = _load_details()
    for r in rows:
        jd = details.get(r["job_id"], "")
        if jd and len(jd) > len(r.get("jd_text", "")):
            r["jd_text"] = jd
        r.pop("_href", None)
    pd.DataFrame(rows).to_csv(LIST_CSV, index=False, encoding="utf-8-sig")
    print(f"合并完成，{len(rows)} 条 → {LIST_CSV}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "--list":
        cmd_list()
    elif args[0] == "--details" and len(args) >= 3:
        cmd_details(int(args[1]), int(args[2]))
    elif args[0] == "--final":
        cmd_final()
    else:
        print(__doc__)


