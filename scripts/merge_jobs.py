"""合并多个数据源 CSV 为 all_jobs.csv。

合并时补两个原始文件没有的字段（供构建与来源健康使用）：

- ``source``：该行来自哪个数据源（文件名映射，稳定英文标识）。
- ``crawl_time``：该源 CSV 的抓取时间。原始 CSV 不含抓取时间，这里用文件 mtime
  （爬虫每次落盘都会更新 mtime）；已存在的非空 ``crawl_time`` 优先保留。

注意：``all_jobs.csv`` 会被覆盖，但 ``data/processed/job_freshness.json`` 会跨构建
保留 first_seen_at，因此重新合并不会丢失“首次发现时间”。
"""
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FILES = ["tech_jobs.csv", "tencent_ai_jobs.csv", "bytedance_ai_jobs.csv",
         "huawei_ai_jobs.csv", "xiaomi_ai_jobs.csv", "xiaomi_campus_jobs.csv",
         "deepseek_ai_jobs.csv", "kimi_ai_jobs.csv", "minimax_ai_jobs.csv",
         "kuaishou_ai_jobs.csv", "xiaohongshu_ai_jobs.csv", "bilibili_ai_jobs.csv",
         "didi_ai_jobs.csv", "meituan_ai_jobs.csv"]

SOURCE_BY_FILE = {
    "tech_jobs.csv": "tech_kaggle",
    "tencent_ai_jobs.csv": "tencent",
    "bytedance_ai_jobs.csv": "bytedance",
    "huawei_ai_jobs.csv": "huawei",
    "xiaomi_ai_jobs.csv": "xiaomi",
    "xiaomi_campus_jobs.csv": "xiaomi_campus",
    "deepseek_ai_jobs.csv": "deepseek",
    "kimi_ai_jobs.csv": "kimi",
    "minimax_ai_jobs.csv": "minimax",
    "kuaishou_ai_jobs.csv": "kuaishou",
    "xiaohongshu_ai_jobs.csv": "xiaohongshu",
    "bilibili_ai_jobs.csv": "bilibili",
    "didi_ai_jobs.csv": "didi",
    "meituan_ai_jobs.csv": "meituan",
}


def _crawl_time(path: Path) -> str:
    """源文件最近一次落盘时间（UTC ISO）。"""
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _with_source_meta(part: pd.DataFrame, path: Path, source: str) -> pd.DataFrame:
    """补 source / crawl_time，保留已有非空值（便于重跑与手工修正）。"""
    part = part.copy()
    fallback_time = _crawl_time(path)
    if "source" not in part.columns:
        part["source"] = source
    else:
        part["source"] = part["source"].fillna("").astype(str).str.strip()
        part.loc[part["source"] == "", "source"] = source
    if "crawl_time" not in part.columns:
        part["crawl_time"] = fallback_time
    else:
        part["crawl_time"] = part["crawl_time"].fillna("").astype(str).str.strip()
        part.loc[part["crawl_time"] == "", "crawl_time"] = fallback_time
    return part


def main():
    parts = []
    for f in FILES:
        p = ROOT / "data" / "raw" / f
        if p.exists():
            parts.append(_with_source_meta(
                pd.read_csv(p), p, SOURCE_BY_FILE.get(f, Path(f).stem)))
    if not parts:
        raise SystemExit("data/raw 下没有可合并的源 CSV")
    out = pd.concat(parts, ignore_index=True)
    out.drop_duplicates(subset="job_id", keep="first", inplace=True)
    out.to_csv(ROOT / "data" / "raw" / "all_jobs.csv", index=False, encoding="utf-8-sig")
    print(f"合并 {len(parts)} 个文件 -> {len(out)} 条 → data/raw/all_jobs.csv")


if __name__ == "__main__":
    main()
