"""小米招聘爬虫（hr.xiaomi.com 公开 GET 接口）。"""
from __future__ import annotations

import time

import pandas as pd
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://hr.xiaomi.com/website/opportunities.html",
}

URL = "https://hr.xiaomi.com/website/api/agent/searchJobPage"

AI_KEYWORDS = ["AI", "算法", "大模型", "机器学习", "深度学习", "自动驾驶", "数据",
               "软件", "芯片", "智能", "语音", "图像", "自然语言处理", "计算机视觉"]


class XiaomiCrawler:
    def __init__(self, delay: float = 0.2):
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def search(self, keyword: str, page_size: int = 20) -> list:
        jobs = []
        page = 1
        while True:
            params = {"keyword": keyword, "cityZhNames": "", "pageSize": page_size, "pageNum": page}
            try:
                data = self.session.get(URL, params=params, timeout=20).json().get("data") or {}
            except Exception:  # noqa: BLE001
                break
            batch = data.get("list") or []
            if not batch:
                break
            jobs.extend(batch)
            page_total = data.get("pageTotal") or 1
            if page >= page_total:
                break
            page += 1
            time.sleep(self.delay)
        return jobs

    def crawl(self, keywords=AI_KEYWORDS, limit: int = 600) -> list[dict]:
        rows = []
        seen = set()
        for kw in keywords:
            posts = self.search(kw)
            print(f"关键词[{kw}] 命中 {len(posts)} 条")
            for p in posts:
                jid = str(p.get("jobId") or "")
                if not jid or jid in seen:
                    continue
                seen.add(jid)
                jd_text = f"{p.get('description') or ''}\n{p.get('requirement') or ''}".strip()
                if len(jd_text) < 20:
                    continue
                city = " ".join(p.get("cityZhNames") or [])
                rows.append({
                    "job_id": jid,
                    "company": "小米",
                    "title": p.get("title") or "",
                    "location": city,
                    "salary": "",
                    "experience": "",
                    "education": "",
                    "jd_text": jd_text,
                })
                if len(rows) >= limit:
                    return rows
        return rows


def main():
    crawler = XiaomiCrawler()
    rows = crawler.crawl()
    out = "data/raw/xiaomi_ai_jobs.csv"
    pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")
    print(f"小米爬取 {len(rows)} 条岗位 → {out}")


if __name__ == "__main__":
    main()
