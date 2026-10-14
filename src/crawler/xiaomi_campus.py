"""小米校招爬虫（搜索框交互 + Playwright 拦截，多 AI 关键词）。"""
from __future__ import annotations

import pandas as pd
from playwright.sync_api import sync_playwright

from src.crawler.util import fmt_publish_time

AI_KEYWORDS = ["AI", "算法", "大模型", "机器学习", "深度学习", "自动驾驶", "数据",
               "软件", "芯片", "智能", "语音", "图像", "机器人", "自然语言处理"]


def crawl(keywords=AI_KEYWORDS, scroll_times: int = 15, max_posts: int = 500) -> list[dict]:
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
            page.goto("https://xiaomi.jobs.f.mioffice.cn/campus/",
                      wait_until="domcontentloaded", timeout=40000)
            page.wait_for_timeout(3000)
            try:
                box = page.locator("input[placeholder='搜索职位']").first
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
                    jf = p.get("job_function") or {}
                    dept = jf.get("name") if isinstance(jf, dict) else str(jf or "")
                    if isinstance(dept, dict):
                        dept = dept.get("zh_cn") or dept.get("i18n") or ""
                    rows.append({
                        "job_id": pid,
                        "company": "小米",
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
    out = "data/raw/xiaomi_campus_jobs.csv"
    pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")
    print(f"小米校招抓取 {len(rows)} 条岗位 → {out}")


if __name__ == "__main__":
    main()
