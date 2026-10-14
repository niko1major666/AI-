"""腾讯招聘爬虫（careers.tencent.com 公开 JSON 接口）。

合规说明：仅抓取官网公开的招聘信息，请求带限速；数据仅供个人学习研究。
"""
from __future__ import annotations

import time

import pandas as pd
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://careers.tencent.com/",
}

BASE = "https://careers.tencent.com/tencentcareer/api/post"

AI_KEYWORDS = ["AI", "算法", "大模型", "机器学习", "深度学习"]


class TencentCrawler:
    def __init__(self, delay: float = 0.3):
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def search(self, keyword: str, page_size: int = 50, max_pages: int = 20) -> list:
        """返回岗位列表（含 Responsibility）。"""
        posts = []
        for page in range(1, max_pages + 1):
            try:
                r = self.session.get(f"{BASE}/Query",
                                     params={"keyword": keyword, "pageIndex": page, "pageSize": page_size},
                                     timeout=20)
                data = r.json()
            except Exception:  # noqa: BLE001
                break
            if data.get("Code") != 200 or not data.get("Data"):
                break
            batch = data["Data"]["Posts"] or []
            if not batch:
                break
            posts.extend(batch)
            if len(batch) < page_size:
                break
            time.sleep(self.delay)
        return posts

    def get_detail(self, post_id: str) -> dict:
        """获取 JD 详情（含 Requirement 任职要求）。"""
        try:
            r = self.session.get(f"{BASE}/ByPostId",
                                 params={"postId": post_id, "language": "zh-cn"},
                                 timeout=20)
            return (r.json() or {}).get("Data", {})
        except Exception:  # noqa: BLE001
            return {}

    def crawl(self, keywords=AI_KEYWORDS, limit: int = 500) -> list[dict]:
        """爬取多个关键词的 AI 岗位，返回规范字段列表。"""
        rows = []
        seen = set()
        for kw in keywords:
            for p in self.search(kw):
                pid = p.get("PostId") or ""
                if not pid or pid in seen:
                    continue
                seen.add(pid)
                detail = self.get_detail(pid)
                resp = detail.get("Responsibility") or p.get("Responsibility") or ""
                req = detail.get("Requirement") or ""
                jd_text = f"{resp}\n{req}".strip()
                if len(jd_text) < 20:
                    continue
                rows.append({
                    "job_id": pid,
                    "company": "腾讯",
                    "title": p.get("RecruitPostName") or "",
                    "location": p.get("LocationName") or "",
                    "salary": "",
                    "experience": p.get("RequireWorkYearsName") or "",
                    "education": "",
                    "jd_text": jd_text,
                    "department": p.get("BGName") or p.get("ProductName") or "",
                    "publish_time": p.get("LastUpdateTime") or "",
                })
                time.sleep(self.delay)
                if len(rows) >= limit:
                    return rows
        return rows


def main():
    crawler = TencentCrawler()
    rows = crawler.crawl()
    out = "data/raw/tencent_ai_jobs.csv"
    pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")
    print(f"腾讯爬取 {len(rows)} 条 AI 岗位 → {out}")


if __name__ == "__main__":
    main()
