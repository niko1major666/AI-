"""Kimi（月之暗面 Moonshot AI）招聘爬虫。

说明：Kimi 用 Moka 平台（app.mokahr.com/apply/moonshot/148506），
岗位列表/详情接口响应被加密（necromancer），故用 Playwright 渲染后 DOM 抓取。
岗位详情需点击，本次先抓列表（标题+类别+地点+日期）。
"""
from __future__ import annotations

import re

import pandas as pd
from playwright.sync_api import sync_playwright

URL = "https://app.mokahr.com/apply/moonshot/148506#/jobs"

# 技术类岗位关键词（Kimi 的 AI 岗集中在 Technical 类）
TECH_KEYWORDS = ["Technical", "技术类", "Engineer", "算法", "AI", "大模型", "机器学习",
                 "深度学习", "Research", "Infra", "模型", "训练", "推理", "Agent",
                 "研发", "数据", "算力", "软件", "Compute"]


def crawl() -> list[dict]:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(12000)
        cards = page.evaluate("""() => Array.from(document.querySelectorAll('a[href*="#/job/"]'))
            .map(a => ({href: a.getAttribute('href')||'', text: (a.innerText||'').trim().replace(/\\s+/g,' ')}))
            .filter(x => x.text && x.href)""")
        browser.close()

    rows = []
    seen = set()
    for c in cards:
        jid = c["href"].split("/")[-1]
        if not jid or jid in seen:
            continue
        text = c["text"]
        # 标题：发布于之前，去掉"急"等标签
        title = re.sub(r"^急", "", text.split("发布于")[0]).strip()
        if not any(k.lower() in text.lower() for k in TECH_KEYWORDS):
            continue
        seen.add(jid)
        pub = ""
        m = re.search(r"发布于\s*([\d\-]+)", text)
        if m:
            pub = m.group(1)
        # 地点：优先"工作地点：X"，否则"| X市"
        loc = ""
        ml = re.search(r"工作地点[：:]\s*([^\s（(，,]+)", text)
        if ml:
            loc = ml.group(1)
        else:
            ml2 = re.search(r"\|\s*(\S*市|\S*国|\S*加坡)\s*\1", text)
            if ml2:
                loc = ml2.group(1)
        # 清理尾部固定文案
        jd = re.sub(r"允许\d+个月内投递\d+个职位[，,]请选择适合的职位进行投递\s*立即投递", "", text).strip()
        rows.append({
            "job_id": f"kimi_{jid[:16]}",
            "company": "月之暗面",
            "title": title,
            "location": loc,
            "salary": "",
            "experience": "",
            "education": "",
            "jd_text": jd,
            "department": "",
            "publish_time": pub,
        })
    return rows


def main():
    rows = crawl()
    out = "data/raw/kimi_ai_jobs.csv"
    pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")
    print(f"Kimi AI 岗位 {len(rows)} 条 → {out}")


if __name__ == "__main__":
    main()
