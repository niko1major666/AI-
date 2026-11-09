"""华为校园招聘爬虫（新官网，`jobType=CR`，公开接口，**无需登录**）。

复用 `src/crawler/huawei.py` 的请求头与解析：同一网关、同一 `getJobPage` 接口，
只是 `jobType` 从 `SR`（社招）换成 `CR`（校招）。实测 2026-11：
- `SR` → 578 条 / 58 页（社招，见 huawei.py）
- `CR` → **109 条 / 11 页**（校招）
- `TR` / `1` / `2` 会回落成社招全量，别用

校招页面虽然提示“登录后查看”，但接口匿名可访问；用账号 cookie 不是必需的。

    python -m src.crawler.huawei_campus            # 只入技术族
    python -m src.crawler.huawei_campus --all      # 全量
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

from src.crawler.huawei import _COLS, TECH_FAMILIES, crawl

JOB_TYPE = "CR"
CSV = "data/raw/huawei_campus_jobs.csv"
PREFIX = "hwc_"


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="华为校招爬虫（jobType=CR，公开接口）")
    parser.add_argument("--all", action="store_true", help="不做岗位族过滤")
    parser.add_argument("--stats", action="store_true", help="只打印岗位族分布")
    args = parser.parse_args(argv)

    if args.stats:
        from collections import Counter

        from src.crawler.huawei import _clean, fetch_page

        _, page_vo = fetch_page(1, job_type=JOB_TYPE)
        total_pages = int(page_vo.get("totalPages") or 1)
        counter: Counter = Counter()
        total = 0
        for page in range(1, total_pages + 1):
            items, _ = fetch_page(page, job_type=JOB_TYPE)
            total += len(items)
            for item in items:
                counter[_clean(item.get("jobFamilyName")) or "(空)"] += 1
        print(f"华为校招：总岗位 {total} 条 / {total_pages} 页")
        for family, n in counter.most_common():
            print(f"  {family}: {n}")
        return

    families = None if args.all else TECH_FAMILIES
    rows = crawl(families, job_type=JOB_TYPE, prefix=PREFIX)
    if not rows:
        raise SystemExit("没有可用岗位（JD 过短或族过滤过严）")
    pd.DataFrame(rows, columns=_COLS).to_csv(CSV, index=False, encoding="utf-8-sig")
    print(f"写入 {CSV}：{len(rows)} 条")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
