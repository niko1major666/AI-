"""字节跳动招聘爬虫（Playwright 拦截 POST 接口 + 滚动加载）。

说明：字节岗位接口 POST /api/v1/search/job/posts 带 _signature 签名，
需用 Playwright 让页面自行发起请求并拦截响应；仅抓取官网公开岗位。
"""
from __future__ import annotations

import pandas as pd
from playwright.sync_api import sync_playwright

from src.crawler.util import fmt_publish_time

AI_KEYWORDS = ["AI", "算法", "大模型", "机器学习", "深度学习", "自然语言处理",
               "计算机视觉", "数据挖掘", "推荐", "强化学习", "语音识别", "NLP", "CV",
               "LLM", "AIGC", "多模态", "知识图谱", "数据科学", "数据分析", "数据工程",
               "推理", "训练", "Agent", "机器人", "搜索", "广告", "风控", "智能"]


def crawl(keyword: str, scroll_times: int = 15, max_posts: int = 500) -> list[dict]:
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
            # 滚动字节的自定义滚动容器（.isInVisualWebsiteUIFeat），触发懒加载
            page.evaluate("""
            () => {
              const el = document.querySelector('.isInVisualWebsiteUIFeat')
                      || document.querySelector('main')
                      || document.scrollingElement;
              if (el) el.scrollTop = el.scrollHeight;
            }
            """)
            page.wait_for_timeout(1500)
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
            dept = (p.get("job_category") or {}).get("name") or ""
            rows.append({
                "job_id": pid,
                "company": "字节跳动",
                "title": p.get("title") or "",
                "location": city,
                "salary": "",
                "experience": "",
                "education": "",
                "jd_text": jd_text,
                "department": dept,
                "publish_time": fmt_publish_time(p.get("publish_time")),
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
