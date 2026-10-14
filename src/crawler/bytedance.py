"""字节跳动招聘爬虫（Playwright 拦截 POST 接口 + 滚动加载）。

说明：字节岗位接口 POST /api/v1/search/job/posts 带 _signature 签名，
需用 Playwright 让页面自行发起请求并拦截响应；仅抓取官网公开岗位。
"""
from __future__ import annotations

import pandas as pd
from playwright.sync_api import sync_playwright

AI_KEYWORDS = ["AI", "算法", "大模型", "机器学习"]


def crawl(keyword: str, scroll_times: int = 60, max_posts: int = 300) -> list[dict]:
    captured = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()

        def on_response(resp):
            if "/api/v1/search/job/posts" in resp.url:
                try:
                    captured.append(resp.json())
                except Exception:  # noqa: BLE001
                    pass

        page.on("response", on_response)
        page.goto(f"https://jobs.bytedance.com/experienced/position?keywords={keyword}",
                  wait_until="domcontentloaded", timeout=40000)
        page.wait_for_timeout(3000)
        for _ in range(scroll_times):
            # 用 JS 滚动到底部，触发虚拟列表懒加载
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1200)
        browser.close()

    rows = []
    seen = set()
    for d in captured:
        posts = (d.get("data") or {}).get("job_post_list") or []
        for p in posts:
            pid = str(p.get("id") or "")
            if not pid or pid in seen:
                continue
            seen.add(pid)
            desc = p.get("description") or ""
            req = p.get("requirement") or ""
            jd_text = f"{desc}\n{req}".strip()
            if len(jd_text) < 20:
                continue
            city = (p.get("city_info") or {}).get("name") or ""
            rows.append({
                "job_id": pid,
                "company": "字节跳动",
                "title": p.get("title") or "",
                "location": city,
                "salary": "",
                "experience": "",
                "education": "",
                "jd_text": jd_text,
            })
            if len(rows) >= max_posts:
                return rows
    return rows


def main():
    all_rows = []
    for kw in AI_KEYWORDS:
        rows = crawl(kw)
        all_rows.extend(rows)
        print(f"关键词[{kw}] 抓取 {len(rows)} 条")
    # 去重
    df = pd.DataFrame(all_rows).drop_duplicates(subset="job_id")
    out = "data/raw/bytedance_ai_jobs.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"字节跳动共 {len(df)} 条 AI 岗位 → {out}")


if __name__ == "__main__":
    main()
