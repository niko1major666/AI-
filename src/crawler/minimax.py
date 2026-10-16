"""MiniMax 招聘爬虫（飞书招聘平台，Playwright 拦截 search/job/posts）。

说明：MiniMax 用飞书招聘（vrfi1sk8a0.jobs.feishu.cn），
接口 POST search/job/posts 带签名，用 Playwright 拦截 + 搜索框交互（同字节/小米校招）。
"""
from __future__ import annotations

import pandas as pd
from playwright.sync_api import sync_playwright

from src.crawler.util import fmt_publish_time

AI_KEYWORDS = ["AI", "算法", "大模型", "机器学习", "深度学习", "NLP", "数据",
               "模型", "语音", "多模态", "Agent", "强化学习", "推荐", "计算机视觉"]

URL = "https://vrfi1sk8a0.jobs.feishu.cn/379481/"


def crawl(keywords=AI_KEYWORDS, scroll_times: int = 10, max_posts: int = 500) -> list[dict]:
    rows = []
    seen = set()
    captured: list = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()

        def on_response(resp):
            if "search/job/posts" in resp.url:
                try:
                    captured.append(resp.json())
                except Exception:  # noqa: BLE001
                    pass

        page.on("response", on_response)

        for kw in keywords:
            captured.clear()
            page.goto(URL, wait_until="domcontentloaded", timeout=40000)
            page.wait_for_timeout(3000)
            try:
                box = page.locator("input[placeholder*='职位'],input[placeholder*='搜索']").first
                box.fill(kw)
                box.press("Enter")
            except Exception:  # noqa: BLE001
                pass
            page.wait_for_timeout(3000)
            for _ in range(scroll_times):
                page.evaluate("""() => {
                  const el = document.querySelector('.isInVisualWebsiteUIFeat')
                          || document.querySelector('main') || document.scrollingElement;
                  if (el) el.scrollTop = el.scrollHeight;
                }""")
                page.wait_for_timeout(1000)

            cnt = 0
            for d in captured:
                posts = (d.get("data") or {}).get("job_post_list") or []
                for p in posts:
                    pid = str(p.get("id") or "")
                    if not pid or pid in seen:
                        continue
                    seen.add(pid)
                    jd_text = f"{p.get('description') or ''}\n{p.get('requirement') or ''}".strip()
                    if len(jd_text) < 20:
                        continue
                    city = (p.get("city_info") or {}).get("name") or ""
                    jf = p.get("job_category") or p.get("job_function") or {}
                    dept = jf.get("name") if isinstance(jf, dict) else str(jf or "")
                    if isinstance(dept, dict):
                        dept = dept.get("zh_cn") or dept.get("i18n") or ""
                    rows.append({
                        "job_id": pid,
                        "company": "MiniMax",
                        "title": p.get("title") or "",
                        "location": city,
                        "salary": "",
                        "experience": "",
                        "education": "",
                        "jd_text": jd_text,
                        "department": dept or "",
                        "publish_time": fmt_publish_time(p.get("publish_time")),
                    })
                    cnt += 1
                    if len(rows) >= max_posts:
                        browser.close()
                        return rows
            print(f"关键词[{kw}] 新增 {cnt} 条（累计 {len(rows)}）")
        browser.close()
    return rows


def main():
    rows = crawl()
    out = "data/raw/minimax_ai_jobs.csv"
    pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")
    print(f"MiniMax AI 岗位 {len(rows)} 条 → {out}")


if __name__ == "__main__":
    main()
