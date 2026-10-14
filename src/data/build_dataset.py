"""CLI：raw CSV -> 清洗 -> 归一 -> 去重 -> jobs.jsonl + 统计。

用法：
    python -m src.data.build_dataset --stats
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from . import load_kaggle, normalize, schema

CANON_COLS = ["job_id", "company", "title", "location", "salary",
              "experience", "education", "jd_text", "department", "publish_time"]


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(root: Path, p: str) -> Path:
    return (root / p).resolve()


def _to_float(v: Any):
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _to_int(v: Any):
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def build(config_path, out_dir=None) -> dict:
    """执行构建，返回 stats 字典。out_dir 用于测试时覆盖输出位置。"""
    cfg_path = Path(config_path).resolve()
    root = _root()
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))

    src_cfg = cfg["source"]
    mapping = cfg.get("column_mapping", {})
    cleaning = cfg.get("cleaning", {})
    out_cfg = cfg.get("output", {})

    df = load_kaggle.load_dataframe(str(_resolve(root, src_cfg["path"])), mapping)
    stats: dict = {"raw_rows": int(len(df))}

    for c in CANON_COLS:
        if c not in df.columns:
            df[c] = ""

    prefix = src_cfg.get("job_prefix", "jd")
    df["job_id"] = [str(v).strip() or f"{prefix}_{i + 1:04d}" for i, v in enumerate(df["job_id"])]

    df["jd_clean"] = df["jd_text"].map(normalize.clean_text)
    df["text_hash"] = df["jd_clean"].map(normalize.sha1_text)

    min_chars = int(cleaning.get("min_jd_chars", 30))
    before = len(df)
    df = df[df["jd_clean"].str.len() >= min_chars]
    stats["dropped_short"] = before - len(df)

    if cleaning.get("normalize_company", True):
        df["company_norm"] = df["company"].map(normalize.normalize_company)
    else:
        df["company_norm"] = df["company"].str.lower()

    sal = df["salary"].map(normalize.parse_salary)
    df["salary_min_k"] = sal.map(lambda x: x[0])
    df["salary_max_k"] = sal.map(lambda x: x[1])
    df["salary_months"] = sal.map(lambda x: x[2])

    before = len(df)
    df = df.drop_duplicates(subset="text_hash", keep="first")
    stats["deduped_rows"] = before - len(df)

    crawl_time = datetime.now(timezone.utc).isoformat()
    records = []
    for _, row in df.iterrows():
        records.append(schema.JobPosting(
            job_id=str(row["job_id"]),
            source=str(src_cfg.get("type", "local_csv")),
            company=str(row.get("company", "") or ""),
            company_norm=str(row.get("company_norm", "") or ""),
            title=str(row.get("title", "") or ""),
            location=str(row.get("location", "") or ""),
            salary_raw=str(row.get("salary", "") or ""),
            salary_min_k=_to_float(row.get("salary_min_k")),
            salary_max_k=_to_float(row.get("salary_max_k")),
            salary_months=_to_int(row.get("salary_months")),
            experience=str(row.get("experience", "") or ""),
            education=str(row.get("education", "") or ""),
            jd_text=str(row.get("jd_text", "") or ""),
            jd_clean=str(row.get("jd_clean", "") or ""),
            crawl_time=crawl_time,
            text_hash=str(row.get("text_hash", "") or ""),
            department=str(row.get("department", "") or ""),
            publish_time=str(row.get("publish_time", "") or ""),
        ).to_dict())

    out = _resolve(root, out_cfg["jobs_jsonl"]) if out_dir is None else Path(out_dir) / "jobs.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    stats["cleaned_rows"] = len(records)
    stats["company_count"] = int(df["company_norm"].nunique())
    stats["companies"] = sorted(set(df["company_norm"].astype(str).tolist()))
    stats["output"] = str(out)

    if out_dir is None and out_cfg.get("stats_path"):
        sp = _resolve(root, out_cfg["stats_path"])
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="构建结构化 JD 数据集")
    ap.add_argument("--config", default=None, help="dataset.yaml 路径（默认 configs/dataset.yaml）")
    ap.add_argument("--out-dir", default=None, help="输出目录覆盖（测试用）")
    ap.add_argument("--stats", action="store_true", help="构建后打印统计（默认始终打印）")
    args = ap.parse_args(argv)

    cfg_path = Path(args.config) if args.config else _root() / "configs" / "dataset.yaml"
    stats = build(cfg_path, out_dir=args.out_dir)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
