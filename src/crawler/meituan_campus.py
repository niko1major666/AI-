"""美团校招 / 实习爬虫（PC 版 jobType 过滤）。

社招走移动端 SPA 的 `jobShareType=1`（见 `src/crawler/meituan.py`）；
**校招 / 实习不在那套参数里**，只能走 PC 版同一个后端、用 `jobType` 过滤：

    POST https://zhaopin.meituan.com/api/official/job/getJobList
    {"page": {"pageNo": 1, "pageSize": 100}, "jobShareType": "1",
     "jobType": [{"code": "1", "subCode": []}],   # 1=校招, 2=实习
     "u_query_id": "...", "r_query_id": "..."}

2026-11 实测：**无需登录 / cookie / 签名**，与社招一致。
校招 198 条、实习 381 条；`jobDuty` + `jobRequirement` 与 `refreshTime` 均 100% 覆盖。

口径：默认只入「技术类」（校招 120 条 / 实习 191 条），与社招的
`KEEP_JOB_FAMILIES = ("技术类",)` 保持一致——其余是运营/产品/职能岗，
抽不到技术技能，收进来只会把零技能率抬高（见 docs/source-triage-v1.7.md）。`--all` 可放开。

**本爬虫尚未注册进构建流水线（刻意为之）**：实测这 311 条技术岗的 JD 与社招
重叠 301 条（98.4%），并入语料净增仅 5 条，却要让 `jobs.jsonl`、`job_freshness.json`、
`metrics.md`、`source_health.md` 与快照常量一起变。因此先只保留爬虫与解析，
产物写 `data/raw/meituan_campus_jobs.csv`（已被 .gitignore 覆盖），不参与构建。

启用（产品决定并入时）只需三处注册 + 同步常量：
1. `scripts/merge_jobs.py` 的 `FILES` 末尾加 `"meituan_campus_jobs.csv"`
2. 同文件 `SOURCE_BY_FILE` 加 `"meituan_campus_jobs.csv": "meituan_campus"`
3. `scripts/recrawl_all.py` 的 `CRAWLERS` 加 `"meituan_campus"`
   然后按 `scripts/preflight_new_source.py` 输出的 5 步清单同步 `tests/test_dataset_snapshot.py`
   常量、`docs/metrics.md`、`docs/source_health.md` 与 README / memory-bank 数字。

坑（与社招相同，已实测）：`u_query_id` / `r_query_id` 是「本次查询」的 token，
**整轮翻页必须复用**；每页换新 token 会一直返回第 1 页。
"""
from __future__ import annotations

import argparse
import hashlib
import secrets
import time
import uuid

import pandas as pd
import requests

from src.crawler.util import fmt_publish_time

BASE = "https://zhaopin.meituan.com"
PATH = "/api/official/job/getJobList"
CSV = "data/raw/meituan_campus_jobs.csv"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": BASE + "/web/campus",
    "Origin": BASE,
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
}
PAGE_SIZE = 100
JOB_TYPES = {"1": "校招", "2": "实习"}
KEEP_JOB_FAMILIES = ("技术类",)
# jobFamily 为空时（接口对部分岗位不给该字段）用标题兜底判断是否为技术岗
TECH_TITLE_HINTS = (
    "工程师", "开发", "算法", "后端", "前端", "服务端", "客户端", "全栈", "数据", "架构",
    "测试", "运维", "技术", "研发", "安全", "机器学习", "深度学习", "nlp", "cv", "infra",
    "android", "ios", "java", "python", "golang", "c++",
)
_COLS = ["job_id", "company", "title", "location", "salary", "experience",
         "education", "jd_text", "department", "publish_time"]


def new_token() -> dict:
    """一轮抓取用的查询 token（整轮复用，换新会让分页退回第 1 页）。"""
    return {
        "u_query_id": uuid.uuid4().hex,
        "r_query_id": f"{int(time.time() * 1000)}{secrets.randbelow(10 ** 8):08d}",
    }


def fetch_page(session: requests.Session, job_type: str, page_no: int, token: dict) -> tuple[list, dict]:
    body = {
        "page": {"pageNo": page_no, "pageSize": PAGE_SIZE},
        "jobShareType": "1",
        "keywords": "",
        "cityList": [],
        "department": [],
        "jfJgList": [],
        "jobType": [{"code": job_type, "subCode": []}],
        "typeCode": [],
        "specialCode": [],
        **token,
    }
    resp = session.post(BASE + PATH, headers=HEADERS, json=body, timeout=40)
    payload = resp.json()
    data = payload.get("data") or {}
    return data.get("list") or [], data.get("page") or {}


def _city(item: dict) -> str:
    parts = []
    for city in item.get("cityList") or []:
        if isinstance(city, dict):
            parts.append(str(city.get("name") or city.get("cityName") or "").strip())
        else:
            parts.append(str(city).strip())
    if not parts:
        for key in ("city", "workCity", "jobCity"):
            if item.get(key):
                return str(item[key])
    return "、".join(p for p in parts if p)


def _job_id(item: dict) -> str:
    raw = item.get("jobUnionId") or item.get("projectId")
    if raw:
        return f"mtc_{raw}"
    # 兜底：接口不给 id 时用「标题+城市」哈希，避免整批丢失
    seed = f"{item.get('name') or ''}|{_city(item)}|{item.get('refreshTime') or ''}"
    return "mtc_h" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def _is_tech(item: dict) -> bool:
    """有 jobFamily 就按它判；为空才用标题技术词兜底（并如实记录）。"""
    family = str(item.get("jobFamily") or "").strip()
    if family:
        return family in KEEP_JOB_FAMILIES
    title = str(item.get("name") or "").lower()
    return any(hint.lower() in title for hint in TECH_TITLE_HINTS)


def to_rows(items: list[dict], keep_all: bool = False, stats: dict | None = None) -> list[dict]:
    rows = []
    for item in items:
        if not keep_all and not _is_tech(item):
            if stats is not None:
                family = str(item.get("jobFamily") or "").strip() or "(empty)"
                stats[family] = stats.get(family, 0) + 1
            continue
        jd = "\n".join(
            part for part in (str(item.get("jobDuty") or ""), str(item.get("jobRequirement") or ""))
            if part.strip()
        )
        rows.append({
            "job_id": _job_id(item),
            "company": "美团",
            "title": str(item.get("name") or "").strip(),
            "location": _city(item),
            "salary": "",
            "experience": str(item.get("workYear") or ""),
            "education": "",
            "jd_text": jd.strip(),
            "department": str(item.get("department") or item.get("projectName") or ""),
            "publish_time": fmt_publish_time(item.get("refreshTime") or item.get("firstPostTime") or ""),
        })
    return rows


def crawl(keep_all: bool = False) -> list[dict]:
    session = requests.Session()
    rows, seen = [], set()
    dropped: dict[str, int] = {}
    for job_type, label in JOB_TYPES.items():
        token = new_token()
        page_no = 1
        while page_no <= 10:
            items, page = fetch_page(session, job_type, page_no, token)
            if not items:
                break
            for row in to_rows(items, keep_all=keep_all, stats=dropped):
                if row["job_id"] in seen:
                    continue
                seen.add(row["job_id"])
                rows.append(row)
            total_pages = int(page.get("totalPage") or 1)
            print(f"  {label} 第 {page_no}/{total_pages} 页 +{len(items)}，累计 {len(rows)}", flush=True)
            if page_no >= total_pages:
                break
            page_no += 1
            time.sleep(0.5)
    if dropped and not keep_all:
        kept_desc = "、".join(f"{k} {v}" for k, v in sorted(dropped.items(), key=lambda kv: -kv[1])[:6])
        print(f"  已丢弃非技术岗 {sum(dropped.values())} 条（{kept_desc}）", flush=True)
    return rows


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="美团校招/实习爬虫（PC 版 jobType 过滤，匿名）")
    parser.add_argument("--all", action="store_true", help="包含非技术类岗位（默认只入技术类）")
    args = parser.parse_args(argv)

    rows = crawl(keep_all=args.all)
    if not rows:
        raise SystemExit("没有抓到任何岗位，接口或参数可能变了（见 scripts/probe_meituan.py --campus）")
    pd.DataFrame(rows, columns=_COLS).to_csv(CSV, index=False, encoding="utf-8-sig")
    print(f"写入 {CSV}：{len(rows)} 条")


if __name__ == "__main__":
    main()
