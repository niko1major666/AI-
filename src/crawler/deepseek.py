"""DeepSeek 招聘爬虫（talent.deepseek.com DOM 抓取岗位列表）。

说明：DeepSeek 用 Moka 平台，岗位详情接口响应加密（necromancer），
故抓取 talent.deepseek.com 已渲染的岗位列表（标题+类别+地点，含 AI 技能词）。
"""
from __future__ import annotations

import pandas as pd
from playwright.sync_api import sync_playwright


def crawl() -> list[dict]:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://talent.deepseek.com/", wait_until="domcontentloaded", timeout=40000)
        page.wait_for_timeout(6000)
        jobs = page.evaluate("""() => {
          return Array.from(document.querySelectorAll('a[href*="mokahr"]')).map(a => {
            const t = (a.textContent||'').trim().replace(/\\s+/g, ' ');
            const m = a.href.match(/job\\/([0-9a-f-]+)/i);
            return {text: t, uuid: m ? m[1] : ''};
          }).filter(x => x.uuid);
        }""")
        browser.close()

    rows = []
    seen = set()
    for j in jobs:
        if j["uuid"] in seen:
            continue
        seen.add(j["uuid"])
        text = j["text"]
        rows.append({
            "job_id": j["uuid"][:20],
            "company": "DeepSeek",
            "title": text[:40],
            "location": "",
            "salary": "",
            "experience": "",
            "education": "",
            "jd_text": text,
        })
    return rows


def main():
    rows = crawl()
    out = "data/raw/deepseek_ai_jobs.csv"
    pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")
    print(f"DeepSeek 抓取 {len(rows)} 条岗位 → {out}")


if __name__ == "__main__":
    main()
