"""冷启动抽取 benchmark：全语料 JD 的规则抽取耗时（首屏冷启动的主要开销）。

用法：
    python scripts/bench_extract.py            # 全部 4582 条
    python scripts/bench_extract.py --limit 500

参照数据（同一台机器 / 同一 Python）：
- v1.3.0：每个 token 一次 `re.finditer`，全语料 24.3s
- v1.3.1：`str.find` 替代正则（语义逐条一致），1.5s
快照见 memory-bank/progress.md。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    ap = argparse.ArgumentParser(description="全语料规则抽取耗时")
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 条（0 = 全部）")
    args = ap.parse_args()

    from src.extractor.rule_baseline import RuleBaselineExtractor
    from src.skillkb.loader import Taxonomy

    taxonomy = Taxonomy(str(ROOT / "data" / "kb" / "skill_taxonomy.yaml"))
    rule = RuleBaselineExtractor(taxonomy)
    path = ROOT / "data" / "processed" / "jobs.jsonl"
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    if args.limit:
        rows = rows[: args.limit]
    if not rows:
        print("没有语料可跑（data/processed/jobs.jsonl 为空）")
        return

    texts = [(r.get("jd_clean") or r.get("jd_text") or "") for r in rows]
    rule.extract("warmup", texts[0])  # 预热：排除首次构造/正则缓存的影响

    t0 = time.perf_counter()
    spans_total = 0
    for row, text in zip(rows, texts):
        spans, _counts = rule.extract(row["job_id"], text)
        spans_total += len(spans)
    elapsed = time.perf_counter() - t0

    print(f"jobs={len(rows)} chars={sum(len(t) for t in texts)} "
          f"tokens={sum(1 for t, _ in rule._tokens if len(t) >= 2)}")
    print(f"extract total={elapsed:.2f}s  per_jd={elapsed / len(rows) * 1000:.2f}ms  "
          f"spans={spans_total}")


if __name__ == "__main__":
    main()
