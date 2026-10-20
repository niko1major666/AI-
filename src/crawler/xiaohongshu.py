"""小红书招聘爬虫（requests 版，社招 + 校招）。

接口：POST https://job.xiaohongshu.com/websiterecruit/position/pageQueryPosition
实测无需签名（页面虽有 x-s 安全 SDK，但该接口未强制校验），body:
    {"positionName": "", "pageNum": 1, "pageSize": 100, "recruitType": "social"|"campus"}
返回含 duty（职责）+ qualification（要求），可作为完整 JD。
"""
from __future__ import annotations

import time

import pandas as pd
import requests

API = "https://job.xiaohongshu.com/websiterecruit/position/pageQueryPosition"
CSV = "data/raw/xiaohongshu_ai_jobs.csv"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://job.xiaohongshu.com/social/position",
    "Origin": "https://job.xiaohongshu.com",
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
}

PAGE_PATH = {"social": "social/position", "campus": "campus/position"}

AI_KEYWORDS = ["算法", "AI", "大模型", "机器学习", "深度学习", "NLP", "CV", "推荐",
               "数据", "模型", "推理", "训练", "Agent", "智能", "多模态", "LLM"]


def fetch_page(recruit_type: str, page_num: int, page_size: int = 100) -> tuple[list, int, int]:
    """返回 (list, total, totalPage)。"""
    body = {"positionName": "", "pageNum": page_num,
            "pageSize": page_size, "recruitType": recruit_type}
    headers = dict(HEADERS)
    headers["Referer"] = f"https://job.xiaohongshu.com/{PAGE_PATH.get(recruit_type, 'social/position')}"
    r = requests.post(API, json=body, headers=headers, timeout=30)
    data = r.json().get("data") or {}
    return data.get("list") or [], int(data.get("total") or 0), int(data.get("totalPage") or 0)


def to_rows(batch: list, recruit_type: str = "social") -> list[dict]:
    """把接口返回的岗位列表转换为统一 schema。"""
    prefix = "xhs" if recruit_type == "social" else "xhsc"
    rows = []
    for p in batch:
        jd = "\n".join(x for x in [p.get("duty") or "", p.get("qualification") or ""] if x)
        rows.append({
            "job_id": f"{prefix}_{p.get('positionId')}",
            "company": "小红书",
            "title": p.get("positionName") or "",
            "location": p.get("workplace") or "",
            "salary": "",
            "experience": "",
            "education": "",
            "jd_text": jd.strip(),
            "department": p.get("jobType") or "",
            "publish_time": p.get("publishTime") or "",
        })
    return rows


def crawl_type(recruit_type: str) -> list[dict]:
    """翻页抓取某一类（社招/校招）。"""
    rows, seen = [], set()
    page = 1
    while True:
        batch, total, total_page = fetch_page(recruit_type, page)
        if not batch:
            break
        for r in to_rows(batch, recruit_type):
            if r["job_id"] in seen:
                continue
            seen.add(r["job_id"])
            rows.append(r)
        print(f"  {recruit_type} 第 {page}/{total_page} 页 +{len(batch)}，累计 {len(rows)}/{total}")
        if page >= total_page or len(rows) >= total:
            break
        page += 1
        time.sleep(0.4)
    return rows


def main() -> None:
    rows = crawl_type("social") + crawl_type("campus")
    pd.DataFrame(rows).to_csv(CSV, index=False, encoding="utf-8-sig")
    ai = [r for r in rows if any(k in (r["title"] + r["jd_text"]) for k in AI_KEYWORDS)]
    print(f"小红书共抓取 {len(rows)} 条（社招+校招，AI 相关约 {len(ai)} 条）→ {CSV}")


if __name__ == "__main__":
    main()
