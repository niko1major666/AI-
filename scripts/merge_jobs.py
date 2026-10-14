"""合并多个数据源 CSV 为 all_jobs.csv。"""
from pathlib import Path

import pandas as pd

ROOT = Path("D:/ai-skill-gap")
FILES = ["tech_jobs.csv", "tencent_ai_jobs.csv", "bytedance_ai_jobs.csv",
         "huawei_ai_jobs.csv", "xiaomi_ai_jobs.csv", "xiaomi_campus_jobs.csv",
         "deepseek_ai_jobs.csv"]


def main():
    parts = []
    for f in FILES:
        p = ROOT / "data" / "raw" / f
        if p.exists():
            parts.append(pd.read_csv(p))
    out = pd.concat(parts, ignore_index=True)
    out.drop_duplicates(subset="job_id", keep="first", inplace=True)
    out.to_csv(ROOT / "data" / "raw" / "all_jobs.csv", index=False, encoding="utf-8-sig")
    print(f"合并 {len(parts)} 个文件 -> {len(out)} 条 → data/raw/all_jobs.csv")


if __name__ == "__main__":
    main()
