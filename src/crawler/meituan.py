"""美团招聘爬虫（社招，requests 版）。

站点是移动端 SPA（``job.meituan.com/m/position``，与 ``zhaopin.meituan.com`` 同一套后端）。
列表接口公开，**无需登录 / 无签名 / 无 cookie**：

    POST /api/official/mobile/job/getJobList
    {"page": {"pageSize": 200, "pageNo": 1}, "jobShareType": "1",
     "u_query_id": "<32 位 hex>", "r_query_id": "<毫秒时间戳 + 8 位随机数字>"}
    -> {"status": 1, "message": "成功",
        "data": {"list": [...], "page": {"pageNo": 1, "pageSize": 200,
                                         "totalPage": 17, "totalCount": 3231}}}

``list[]`` 自带 ``jobDuty``（岗位职责）与 ``jobRequirement``（岗位要求）全文，
不用再逐条打 detail 接口。

三个容易踩的点（都已实测）：

1. **分页参数必须嵌在 ``page`` 对象里**。PC 端那版 ``/api/official/job/getJobList``
   收顶层 ``pageNo``/``pageSize``，传嵌套结构时会被忽略，永远返回同一批 20 条；
   反过来移动端这版只认嵌套结构。
2. ``u_query_id`` / ``r_query_id`` 不是鉴权，而是「本次查询」的 token：**整轮翻页必须
   复用同一个**。每页换新 token 会被当成一次新搜索，服务端始终返回第 1 页——17 页
   抓下来只有 200 条唯一岗位，而 ``totalCount`` 一直是 3231，看起来「抓满了」其实是
   重复。因此本爬虫按 job_id 边抓边去重，并在结尾核对「唯一条数 == total」。
   ``jobShareType=1`` 缺这两个字段时直接返回 0 条。
3. ``jobShareType=2``（2326 条）不需要 token，但返回的 item 里 ``jobDuty`` /
   ``jobRequirement`` **全为空**，只有标题和城市，不能用于技能抽取，故固定用 ``1``。

分页 ``pageSize`` 实测上限 1000（传 2000 会被截到 1000，`totalPage` 变成 4）；爬虫固定用
200（17 页抓完 3231 条），比默认的 10 快 20 倍，也比 1000 更抗单页超时。
"""
from __future__ import annotations

import argparse
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

BASE = "https://job.meituan.com"
LIST_PATH = "/api/official/mobile/job/getJobList"
CSV = "data/raw/meituan_ai_jobs.csv"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                  "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                  "Mobile/15E148 Safari/604.1",
    "Referer": BASE + "/m/position",
    "Origin": BASE,
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
}
PAGE_SIZE = 200
JOB_SHARE_TYPE = "1"
# 默认只入「技术类」：全站 3231 条里零售 90.6% / 销售客服 97.0% / 职能 71.1% /
# 运营 48.1% / 产品 37.0% 抽不到技能；技术类只 6.0%（681 条，平均 6.7 项技能）。
KEEP_JOB_FAMILIES = ("技术类",)
_BJ = timezone(timedelta(hours=8))
_COLS = ["job_id", "company", "title", "location", "salary", "experience",
         "education", "jd_text", "department", "publish_time"]


def new_token() -> dict:
    """生成一轮抓取用的查询 token（整轮复用；换新 token 会让分页退回第 1 页）。"""
    return {
        "u_query_id": uuid.uuid4().hex,
        "r_query_id": f"{int(time.time() * 1000)}{secrets.randbelow(10 ** 8):08d}",
    }


def fetch_page(s: requests.Session, page: int, token: dict,
               page_size: int = PAGE_SIZE):
    """返回 (items, total)。"""
    body = {"page": {"pageSize": page_size, "pageNo": page},
            "jobShareType": JOB_SHARE_TYPE, **token}
    r = s.post(BASE + LIST_PATH, json=body, timeout=60)
    payload = r.json() or {}
    if payload.get("status") != 1:
        raise RuntimeError(f"{LIST_PATH} 返回异常：{payload.get('status')} "
                           f"{payload.get('message')}")
    data = payload.get("data") or {}
    page_info = data.get("page") or {}
    return (data.get("list") or [], int(page_info.get("totalCount") or 0))


def _epoch_ms_to_date(value) -> str:
    """毫秒时间戳 → 北京时间日期；空值/异常返回空串。"""
    if not value:
        return ""
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=_BJ).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        return ""


def to_rows(batch: list) -> list[dict]:
    """把接口返回的岗位列表转换为统一 schema（正文 = 职责 + 要求）。"""
    rows = []
    for p in batch:
        jd = "\n".join(x.strip() for x in
                       [p.get("jobDuty") or "", p.get("jobRequirement") or ""] if x.strip())
        cities = "、".join(c.get("name") or "" for c in (p.get("cityList") or [])
                          if (c.get("name") or "").strip())
        rows.append({
            "job_id": f"meituan_{p.get('jobUnionId')}",
            "company": "美团",
            "title": p.get("name") or "",
            "location": cities,
            "salary": "",
            "experience": p.get("workYear") or "",
            "education": "",
            "jd_text": jd,
            "department": p.get("jobFamily") or "",
            "publish_time": _epoch_ms_to_date(p.get("refreshTime") or p.get("firstPostTime")),
        })
    return rows


def crawl_all(s: requests.Session) -> list[dict]:
    """按总数翻完社招，按 job_id 去重（重复即说明分页 token 失效）。"""
    rows: list[dict] = []
    seen: set[str] = set()
    token = new_token()
    page = 1
    total = 0
    while True:
        batch, total = fetch_page(s, page, token)
        if not batch:
            break
        before = len(rows)
        for row in to_rows(batch):
            if row["job_id"] in seen:
                continue
            seen.add(row["job_id"])
            rows.append(row)
        print(f"  第 {page} 页 +{len(batch)}，去重后累计 {len(rows)} / {total}")
        if len(rows) >= total:
            break
        if len(rows) == before:
            # 整页都是已见过的岗位：分页没生效（最常见原因：每页换了新的 u_query_id）。
            break
        page += 1
        time.sleep(0.4)
    if total and len(rows) < total:
        raise RuntimeError(f"只拿到 {len(rows)}/{total} 条唯一岗位，"
                           "分页可能失效（u_query_id 是否整轮复用？）")
    return rows


def filter_rows(rows: list[dict], families=KEEP_JOB_FAMILIES) -> list[dict]:
    """按职位大类保留（空元组表示不过滤）。"""
    if not families:
        return rows
    return [r for r in rows if r["department"] in families]


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="美团招聘爬虫（社招）")
    parser.add_argument("--all", action="store_true",
                        help="保留全站岗位（默认只留 技术类）")
    parser.add_argument("--out", default=CSV, help=f"输出 CSV，默认 {CSV}")
    args = parser.parse_args(argv)

    s = requests.Session()
    s.headers.update(HEADERS)
    rows = crawl_all(s)

    kept = rows if args.all else filter_rows(rows)
    df = pd.DataFrame(kept)[_COLS]
    df.to_csv(args.out, index=False, encoding="utf-8-sig")
    scope = "全站" if args.all else "、".join(KEEP_JOB_FAMILIES)
    print(f"美团共抓取 {len(rows)} 条，按「{scope}」保留 {len(kept)} 条 → {args.out}")


if __name__ == "__main__":
    main()

