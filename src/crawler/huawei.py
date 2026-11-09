"""华为社招爬虫（新官网 `career.huawei.com/cn`，公开网关接口，**无需登录**）。

老门户 portal5 的 `portalpub/getJob/newHr` 已枯竭（2026-11 实测全站 2 条），华为迁站后
岗位列表改走网关：

    POST https://apigw-dgg-b0.huawei.com/api/apig/channelhw/recruitmentPosition/pub/getJobPage
        ?X-HW-ID=app_000000035886
    headers: x-jalor-tenantalias: hcm / x-referer / x-alb-gray: prod / x-language: zh_CN
    body:    {"curPage": 1, "pageSize": 10, "jobType": "SR"}
    ->       data.pageVO {totalRows, totalPages} + data.result[]

实测（2026-11）：`totalRows=578`，58 页 × 10 条，单页约 0.6s。

字段映射与坑：
- `jobId` → job_id（加前缀 `hw_`）
- `jobName` → 标题；`jobFamilyName` → 岗位族；`deptName` → 部门
- `workPlace` → 城市（`cityName` 常为字面 "None"，别用）
- `lastUpdateDate` → 发布时间（YYYY-MM-DD）
- **`jobDesc` 常为 "None"**，完整 JD 要拼 `mainBusiness`（标准职责）+ `jobRequire`（要求）
- `degree` / `releaseDate` 也常为 "None"，需过滤后留空

口径：只入技术族（`TECH_FAMILIES`），与其它数据源一致；`--all` 可放开全站。
`--stats` 只打印岗位族分布，不写文件。
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import Counter

import pandas as pd
import requests

API = ("https://apigw-dgg-b0.huawei.com/api/apig/channelhw/recruitmentPosition/pub/getJobPage"
       "?X-HW-ID=app_000000035886")
CSV = "data/raw/huawei_ai_jobs.csv"
HEADERS = {
    "x-hw-id": "app_000000035886",
    "x-jalor-tenantalias": "hcm",
    "x-referer": "https://career.huawei.com/cn",
    "x-alb-gray": "prod",
    "x-language": "zh_CN",
    "x-csrf-token": "",
    "Content-Type": "application/json",
    "Origin": "https://career.huawei.com",
    "Referer": "https://career.huawei.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
}
PAGE_SIZE = 10
JOB_TYPE = "SR"  # 社招
# 技术族：与其它源「只入技术类」的口径一致
TECH_FAMILIES = ("研发族", "云服务族", "质量与流程IT族", "2012实验室")
_COLS = ["job_id", "company", "title", "location", "salary", "experience",
         "education", "jd_text", "department", "publish_time"]

_session = requests.Session()
_session.headers.update(HEADERS)


def _clean(value) -> str:
    """接口用字面字符串 "None" 表示空值，统一清掉。"""
    text = "" if value is None else str(value).strip()
    return "" if text in ("None", "null") else text


def fetch_page(page: int, page_size: int = PAGE_SIZE) -> tuple[list[dict], dict]:
    resp = _session.post(API, json={"curPage": page, "pageSize": page_size, "jobType": JOB_TYPE},
                         timeout=30)
    payload = resp.json()
    data = payload.get("data") or {}
    return data.get("result") or [], data.get("pageVO") or {}


def to_rows(items: list[dict], families: tuple[str, ...] | None = TECH_FAMILIES) -> list[dict]:
    rows = []
    for item in items:
        family = _clean(item.get("jobFamilyName"))
        if families is not None and family and family not in families:
            continue
        jd = "\n".join(part for part in (_clean(item.get("mainBusiness")),
                                         _clean(item.get("jobRequire"))) if part)
        job_id = _clean(item.get("jobId"))
        if not job_id or len(jd) < 20:
            continue
        rows.append({
            "job_id": f"hw_{job_id}",
            "company": "华为",
            "title": _clean(item.get("jobName")) or _clean(item.get("jobNameNew")),
            "location": _clean(item.get("workPlace")) or _clean(item.get("cityName")),
            "salary": "",
            "experience": _clean(item.get("workYear")),
            "education": _clean(item.get("degree")),
            "jd_text": jd,
            "department": _clean(item.get("deptName")),
            "publish_time": _clean(item.get("lastUpdateDate")),
        })
    return rows


def crawl(families: tuple[str, ...] | None = TECH_FAMILIES, delay: float = 0.25) -> list[dict]:
    rows, seen = [], set()
    first, page_vo = fetch_page(1)
    if not first:
        raise SystemExit("getJobPage 返回空：接口参数或请求头可能变了（见 docs/source-triage-v1.7.md §7）")
    total_pages = int(page_vo.get("totalPages") or 1)
    total_rows = page_vo.get("totalRows")
    print(f"华为社招：共 {total_rows} 条 / {total_pages} 页，pageSize={PAGE_SIZE}", flush=True)

    batches = [first]
    for page in range(2, total_pages + 1):
        time.sleep(delay)
        items, _ = fetch_page(page)
        batches.append(items)
        print(f"  第 {page}/{total_pages} 页 +{len(items)}", flush=True)

    for items in batches:
        for row in to_rows(items, families):
            if row["job_id"] in seen:
                continue
            seen.add(row["job_id"])
            rows.append(row)
    return rows


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="华为社招爬虫（新站 getJobPage，无需登录）")
    parser.add_argument("--all", action="store_true", help="不做岗位族过滤，全站入库")
    parser.add_argument("--stats", action="store_true", help="只打印岗位族分布，不写 CSV")
    args = parser.parse_args(argv)

    if args.stats:
        _, page_vo = fetch_page(1)
        total_pages = int(page_vo.get("totalPages") or 1)
        counter: Counter = Counter()
        total = 0
        for page in range(1, total_pages + 1):
            items, _ = fetch_page(page)
            total += len(items)
            for item in items:
                counter[_clean(item.get("jobFamilyName")) or "(空)"] += 1
            time.sleep(0.2)
        print(f"总岗位 {total} 条 / {total_pages} 页")
        for family, n in counter.most_common():
            print(f"  {family}: {n}")
        return

    families = None if args.all else TECH_FAMILIES
    rows = crawl(families)
    if not rows:
        raise SystemExit("没有可用岗位（JD 过短或族过滤过严），检查 TECH_FAMILIES")
    pd.DataFrame(rows, columns=_COLS).to_csv(CSV, index=False, encoding="utf-8-sig")
    print(f"写入 {CSV}：{len(rows)} 条（岗位族过滤：{'关闭' if families is None else '、'.join(families)}）")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
