"""华为招聘爬虫（career.huawei.com 公开 GET 接口，无需签名）。"""
from __future__ import annotations

import time

import pandas as pd
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://career.huawei.com/reccampportal/portal5/social-recruitment.html",
}

URL = "https://career.huawei.com/reccampportal/services/portal/portalpub/getJob/newHr/page/10/1"

AI_KEYWORDS = ["", "AI", "算法", "人工智能", "大模型", "机器学习", "深度学习", "软件",
               "云计算", "自动驾驶", "自然语言处理", "计算机视觉", "数据", "昇腾"]


class HuaweiCrawler:
    def __init__(self, delay: float = 0.3):
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def search(self, keyword: str, page_size: int = 20) -> list:
        posts = []
        page = 1
        while True:
            params = {"curPage": page, "pageSize": page_size, "jobFamilyCode": "", "deptCode": "",
                      "keywords": keyword, "searchType": 1, "orderBy": "P_COUNT_DESC", "jobType": 1}
            try:
                data = self.session.get(URL, params=params, timeout=20).json()
            except Exception:  # noqa: BLE001
                break
            batch = data.get("result") or []
            if not batch:
                break
            posts.extend(batch)
            total_pages = (data.get("pageVO") or {}).get("totalPages") or 1
            if page >= total_pages:
                break
            page += 1
            time.sleep(self.delay)
        return posts

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
                jd_text = f"{p.get('mainBusiness') or ''}\n{p.get('jobRequire') or ''}".strip()
                if len(jd_text) < 20:
                    continue
                addr = (p.get("jobAddress") or "").replace("China\\", "").replace("\\", " ")
                rows.append({
                    "job_id": jid,
                    "company": "华为",
                    "title": p.get("nameCn") or p.get("jobname") or "",
                    "location": addr,
                    "salary": "",
                    "experience": "",
                    "education": "",
                    "jd_text": jd_text,
                })
                if len(rows) >= limit:
                    return rows
        return rows


def main():
    crawler = HuaweiCrawler()
    rows = crawler.crawl()
    out = "data/raw/huawei_ai_jobs.csv"
    pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")
    print(f"华为爬取 {len(rows)} 条岗位 → {out}")


if __name__ == "__main__":
    main()
