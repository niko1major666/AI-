"""滴滴招聘爬虫（社招，requests 版）。

列表接口公开（**无需登录 / 无 token / 无签名校验**）：

    GET /recruit-portal-service/api/job/front/list?page=1&size=100
    -> {"meta": {"code": 0, "message": ""},
        "data": {"total": 1081, "page": 1, "size": 100, "items": [...]}}

`items[]` 已自带 ``jobDuty``（岗位职责）与 ``jobQualification``（任职资格）全文，
因此不用再逐条打 detail 接口。``size`` 上限 100：传 200 会被网关拦截，返回
``{"meta": {"code": 10039, "message": "拦截返回"}, "data": null}``（HTTP 仍是 200，
只看状态码会误以为「没有岗位」），所以分页固定 100 并校验 ``meta.code``；另外对
「空页但只拿到 N/total」显式抛错，防止服务端静默截断。

校招不在本站：``talent.didiglobal.com/campus/`` 只是跳转页，校招投递走 Moka
（``campus.didiglobal.com`` / ``app.mokahr.com``），没有公开列表接口，因此本爬虫
只覆盖社招。
"""
from __future__ import annotations

import argparse
import time

import pandas as pd
import requests

BASE = "https://talent.didiglobal.com"
LIST_PATH = "/recruit-portal-service/api/job/front/list"
CSV = "data/raw/didi_ai_jobs.csv"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": BASE + "/social",
    "Accept": "application/json, text/plain, */*",
}
PAGE_SIZE = 100
# 默认只入「技术」：全站 1081 条里运营 53.7% / 产品 65.6% / 安全 75.0% 抽不到技能，
# 技术类只 11.8%（423 条，平均 5.3 项技能）；全量入语料会把零技能率顶向 28% 护栏。
KEEP_JOB_TYPES = ("技术",)
_COLS = ["job_id", "company", "title", "location", "salary", "experience",
         "education", "jd_text", "department", "publish_time"]


def fetch_page(s: requests.Session, page: int, page_size: int = PAGE_SIZE):
    """返回 (items, total)。"""
    r = s.get(BASE + LIST_PATH, params={"page": page, "size": page_size}, timeout=30)
    payload = r.json() or {}
    meta = payload.get("meta") or {}
    if meta.get("code") != 0:
        raise RuntimeError(f"{LIST_PATH} 返回异常：{meta.get('code')} {meta.get('message')}")
    data = payload.get("data") or {}
    return (data.get("items") or [], int(data.get("total") or 0))


def to_rows(batch: list) -> list[dict]:
    """把接口返回的岗位列表转换为统一 schema（正文 = 职责 + 任职资格）。"""
    rows = []
    for p in batch:
        jd = "\n".join(x.strip() for x in
                       [p.get("jobDuty") or "", p.get("jobQualification") or ""] if x.strip())
        rows.append({
            "job_id": f"didi_{p.get('jdNo')}",
            "company": "滴滴",
            "title": p.get("jobName") or "",
            "location": p.get("workArea") or "",
            "salary": "",
            "experience": "",
            "education": "",
            "jd_text": jd,
            "department": p.get("jobTypeName") or "",
            "publish_time": (p.get("refreshTime") or p.get("createTime") or "")[:10],
        })
    return rows


def crawl_all(s: requests.Session) -> list[dict]:
    """按总数翻完社招，按 job_id 去重。"""
    rows: list[dict] = []
    seen: set[str] = set()
    page = 1
    total = 0
    while True:
        batch, total = fetch_page(s, page)
        if not batch:
            if total > len(rows):
                raise RuntimeError(f"第 {page} 页为空但只拿到 {len(rows)}/{total} 条，"
                                   "size 上限可能被改小")
            break
        for row in to_rows(batch):
            if row["job_id"] in seen:
                continue
            seen.add(row["job_id"])
            rows.append(row)
        print(f"  第 {page} 页 +{len(batch)}，累计 {len(rows)} / {total}")
        if len(rows) >= total:
            break
        page += 1
        time.sleep(0.3)
    return rows


def filter_rows(rows: list[dict], job_types=KEEP_JOB_TYPES) -> list[dict]:
    """按职位类型保留（空元组表示不过滤）。"""
    if not job_types:
        return rows
    return [r for r in rows if r["department"] in job_types]


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="滴滴招聘爬虫（社招）")
    parser.add_argument("--all", action="store_true",
                        help="保留全站岗位（默认只留 技术）")
    parser.add_argument("--out", default=CSV, help=f"输出 CSV，默认 {CSV}")
    args = parser.parse_args(argv)

    s = requests.Session()
    s.headers.update(HEADERS)
    rows = crawl_all(s)

    kept = rows if args.all else filter_rows(rows)
    df = pd.DataFrame(kept)[_COLS]
    df.to_csv(args.out, index=False, encoding="utf-8-sig")
    scope = "全站" if args.all else "、".join(KEEP_JOB_TYPES)
    print(f"滴滴共抓取 {len(rows)} 条，按「{scope}」保留 {len(kept)} 条 → {args.out}")


if __name__ == "__main__":
    main()
