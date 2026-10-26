"""哔哩哔哩招聘爬虫（requests 版，社招 + 校招）。

接口是公开的（**无需登录**），但要过 CSRF 校验：

    GET  /api/auth/v1/csrf/token          -> {"code":0,"data":"<uuid>"}
    POST /api/srs/position/positionList   社招，body {"pageNum":1,"pageSize":100}
    POST /api/campus/position/positionList 校招，同上

固定请求头：``X-AppKey: ops.ehr-api.auth``、``X-UserType: 2``、``X-CSRF: <token>``
（对应前端 ``app.js`` 里 ``defaults.headers.common`` 的三行）。

返回 ``data.list[]`` 已自带 ``positionDescription``（完整 JD）与
``total/pages/size`` 分页信息，因此不需要再逐条打 detail 接口。
"""
from __future__ import annotations

import argparse
import time

import pandas as pd
import requests

BASE = "https://jobs.bilibili.com"
CSRF_PATH = "/api/auth/v1/csrf/token"
SOURCES = (
    ("/api/srs/position/positionList", "bili", "社招"),
    ("/api/campus/position/positionList", "bilic", "校招"),
)
CSV = "data/raw/bilibili_ai_jobs.csv"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": BASE + "/social/position",
    "Origin": BASE,
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "X-AppKey": "ops.ehr-api.auth",
    "X-UserType": "2",
}
PAGE_SIZE = 100
# 默认只入「技术类 + AI类」：全站岗位里运营/内容/设计岗 40%~80% 抽不到技能，
# 全量（876 条）会把语料零技能率从 25.4% 顶到 28.1%，越过 28% 护栏。
KEEP_DEPARTMENTS = ("技术类", "AI类")
_COLS = ["job_id", "company", "title", "location", "salary", "experience",
         "education", "jd_text", "department", "publish_time"]


def new_session() -> requests.Session:
    """建会话并取一次 CSRF token（缺失时服务端报「csrf不能为空」）。"""
    s = requests.Session()
    s.headers.update(HEADERS)
    token = (s.get(BASE + CSRF_PATH, timeout=20).json() or {}).get("data")
    if not token:
        raise RuntimeError("取 CSRF token 失败，接口可能改版")
    s.headers["X-CSRF"] = token
    return s


def _post(s: requests.Session, path: str, body: dict) -> dict:
    """POST 一次；token 过期（-3 / -101 / -403）时刷新后重试一次。"""
    r = s.post(BASE + path, json=body, timeout=30)
    payload = r.json() or {}
    if payload.get("code") in (-3, -101, -403):
        token = (s.get(BASE + CSRF_PATH, timeout=20).json() or {}).get("data")
        if token:
            s.headers["X-CSRF"] = token
            payload = s.post(BASE + path, json=body, timeout=30).json() or {}
    if payload.get("code") != 0:
        raise RuntimeError(f"{path} 返回异常：{payload.get('code')} {payload.get('message')}")
    return payload.get("data") or {}


def fetch_page(s: requests.Session, path: str, page_num: int, page_size: int = PAGE_SIZE):
    """返回 (list, pages, total)。"""
    data = _post(s, path, {"pageNum": page_num, "pageSize": page_size})
    return (data.get("list") or [], int(data.get("pages") or 0), int(data.get("total") or 0))


def to_rows(batch: list, prefix: str) -> list[dict]:
    """把接口返回的岗位列表转换为统一 schema。"""
    rows = []
    for p in batch:
        rows.append({
            "job_id": f"{prefix}_{p.get('id')}",
            "company": "哔哩哔哩",
            "title": p.get("positionName") or "",
            "location": p.get("workLocation") or "",
            "salary": "",
            "experience": "",
            "education": "",
            "jd_text": (p.get("positionDescription") or "").strip(),
            "department": p.get("postCodeName") or "",
            "publish_time": (p.get("pushTime") or "")[:10],
        })
    return rows


def crawl_source(s: requests.Session, path: str, prefix: str, label: str) -> list[dict]:
    """按总页数翻完某一类（社招/校招），按 job_id 去重。"""
    rows: list[dict] = []
    seen: set[str] = set()
    total = pages = 0
    page = 1
    while True:
        batch, pages, total = fetch_page(s, path, page)
        if not batch:
            break
        for row in to_rows(batch, prefix):
            if row["job_id"] in seen:
                continue
            seen.add(row["job_id"])
            rows.append(row)
        print(f"  {label}第 {page}/{pages} 页 +{len(batch)}，累计 {len(rows)} / {total}")
        if page >= pages:
            break
        page += 1
        time.sleep(0.3)
    return rows


def filter_rows(rows: list[dict], departments=KEEP_DEPARTMENTS) -> list[dict]:
    """按岗位类别保留（空元组表示不过滤）。"""
    if not departments:
        return rows
    return [r for r in rows if r["department"] in departments]


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="哔哩哔哩招聘爬虫（社招 + 校招）")
    parser.add_argument("--all", action="store_true",
                        help="保留全站岗位（默认只留 技术类 + AI类）")
    parser.add_argument("--out", default=CSV, help=f"输出 CSV，默认 {CSV}")
    args = parser.parse_args(argv)

    s = new_session()
    rows: list[dict] = []
    for path, prefix, label in SOURCES:
        print(f"===== 哔哩哔哩 {label} =====")
        rows.extend(crawl_source(s, path, prefix, label))

    kept = rows if args.all else filter_rows(rows)
    df = pd.DataFrame(kept)[_COLS]
    df.to_csv(args.out, index=False, encoding="utf-8-sig")
    scope = "全站" if args.all else "、".join(KEEP_DEPARTMENTS)
    print(f"哔哩哔哩共抓取 {len(rows)} 条，按「{scope}」保留 {len(kept)} 条 → {args.out}")


if __name__ == "__main__":
    main()
