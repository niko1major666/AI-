"""快手招聘爬虫（requests 版，已逆向 sign 签名）。

sign = HMAC_SHA256(secret, str(timestamp) + canonicalize(query) + secret).hexdigest()
secret = "652f962a-0575-4575-98d2-f04e2291bee2"
"""
from __future__ import annotations

import hashlib
import hmac
import sys
import time
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests

SECRET = "652f962a-0575-4575-98d2-f04e2291bee2"
BASE = "https://zhaopin.kuaishou.cn/recruit/e/api/v1/open/positions/simple"
CSV = "data/raw/kuaishou_ai_jobs.csv"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://zhaopin.kuaishou.cn/",
    "Accept": "application/json, text/plain, */*",
}

CITY = {"Beijing": "北京", "Shanghai": "上海", "Hangzhou": "杭州", "Shenzhen": "深圳",
        "Guangzhou": "广州", "Chengdu": "成都", "Nanjing": "南京", "Wuhan": "武汉",
        "Suzhou": "苏州", "Xian": "西安", "Hefei": "合肥", "Chongqing": "重庆",
        "Tianjin": "天津", "Qingdao": "青岛", "Changsha": "长沙", "Fuzhou": "福州",
        "Xiamen": "厦门", "Dalian": "大连", "Jinan": "济南", "Zhengzhou": "郑州"}

AI_KEYWORDS = ["算法", "AI", "大模型", "机器学习", "深度学习", "NLP", "CV", "推荐",
               "数据", "模型", "推理", "训练", "Agent", "智能", "多模态", "LLM"]


def canonicalize(query: dict) -> str:
    if not query:
        return ""
    parts = []
    for k in sorted(query):
        v = query[k]
        if not isinstance(v, list):
            v = [v]
        v = [x for x in v if x not in (None, "")]
        v.sort()
        if v:
            encoded = [quote(str(x), safe="").replace("%20", "+") for x in v]
            parts.append(f"{k}={','.join(encoded)}")
    return "&".join(parts)


def make_sign(query: dict, ts: int) -> str:
    message = str(ts) + canonicalize(query) + SECRET
    return hmac.new(SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()


def fetch_page(page_num: int, page_size: int = 100) -> list:
    query = {"pageNum": str(page_num), "pageSize": str(page_size),
             "positionNatureCode": "C001", "recruitProject": "socialr"}
    ts = int(time.time() * 1000)
    headers = dict(HEADERS)
    headers["sign"] = make_sign(query, ts)
    headers["signtimestamp"] = str(ts)
    r = requests.get(BASE, params=query, headers=headers, timeout=30)
    data = r.json()
    return (data.get("result") or {}).get("list") or []


def to_rows(batch: list) -> list[dict]:
    rows = []
    for p in batch:
        title = p.get("name") or ""
        jd = "\n".join(x for x in [p.get("description") or "", p.get("positionDemand") or ""] if x)
        rows.append({
            "job_id": f"ks_{p.get('id')}",
            "company": "快手",
            "title": title,
            "location": CITY.get(p.get("workLocationCode") or "", p.get("workLocationCode") or ""),
            "salary": "",
            "experience": p.get("workExperienceCode") or "",
            "education": p.get("educationLimitCode") or "",
            "jd_text": jd.strip(),
            "department": p.get("departmentCode") or "",
            "publish_time": "",
        })
    return rows


def crawl() -> list[dict]:
    rows, seen = [], set()
    for page in range(1, 20):
        batch = fetch_page(page)
        if not batch:
            break
        for r in to_rows(batch):
            if r["job_id"] in seen:
                continue
            seen.add(r["job_id"])
            rows.append(r)
        print(f"  第 {page} 页 +{len(batch)}，累计 {len(rows)}")
        time.sleep(0.4)
    return rows


def main() -> None:
    rows = crawl()
    pd.DataFrame(rows).to_csv(CSV, index=False, encoding="utf-8-sig")
    ai = [r for r in rows if any(k in (r["title"] + r["jd_text"]) for k in AI_KEYWORDS)]
    print(f"快手共抓取 {len(rows)} 条（AI 相关约 {len(ai)} 条）→ {CSV}")


if __name__ == "__main__":
    main()

