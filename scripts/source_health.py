"""生成数据源健康报告：`docs/source_health.md`。

用法：
    python scripts/source_health.py                 # 含零技能抽取（约 2s）
    python scripts/source_health.py --skip-extract  # 只统计规模 / 新鲜度 / 发布时间覆盖
    python scripts/source_health.py --stale-days 14

CI 在 main 上重跑并 `git diff --exit-code docs/source_health.md`，防止报告陈旧。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data import freshness, source_health  # noqa: E402
from src.extractor.rule_baseline import RuleBaselineExtractor  # noqa: E402
from src.skillkb.loader import Taxonomy  # noqa: E402

DEFAULT_JOBS = ROOT / "data" / "processed" / "jobs.jsonl"
DEFAULT_STATE = ROOT / "data" / "processed" / "job_freshness.json"
DEFAULT_OUT = ROOT / "docs" / "source_health.md"
DEFAULT_TAXONOMY = ROOT / "data" / "kb" / "skill_taxonomy.yaml"


def load_jobs(path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"找不到语料：{p}（先运行 python -m src.data.build_dataset）")
    return [json.loads(x) for x in p.read_text(encoding="utf-8").split("\n") if x.strip()]


def zero_skill_job_ids(jobs, taxonomy_path=DEFAULT_TAXONOMY) -> set:
    tax = Taxonomy(str(taxonomy_path))
    rule = RuleBaselineExtractor(tax)
    zero = set()
    for j in jobs:
        text = j.get("jd_clean") or j.get("jd_text", "")
        spans, _ = rule.extract(str(j.get("job_id") or ""), text)
        if not spans:
            zero.add(str(j.get("job_id") or ""))
    return zero


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="生成数据源健康报告")
    ap.add_argument("--jobs", default=str(DEFAULT_JOBS))
    ap.add_argument("--state", default=str(DEFAULT_STATE))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--taxonomy", default=str(DEFAULT_TAXONOMY))
    ap.add_argument("--stale-days", type=int, default=freshness.DEFAULT_STALE_DAYS)
    ap.add_argument("--as-of", default=None, help="基准时间（默认取语料最新 last_seen_at）")
    ap.add_argument("--skip-extract", action="store_true", help="跳过零技能统计")
    args = ap.parse_args(argv)

    jobs = load_jobs(args.jobs)
    state = freshness.load_state(args.state)
    zero_ids = None if args.skip_extract else zero_skill_job_ids(jobs, args.taxonomy)
    report = source_health.build_report(
        jobs, state=state, zero_skill_ids=zero_ids,
        as_of=args.as_of, stale_days=args.stale_days,
    )
    md = source_health.render_markdown(report)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as f:
        f.write(md)

    t = report["totals"]
    print(f"来源健康报告 -> {out}")
    print(f"岗位 {t['jobs']} / 来源 {t['sources']} / 超期未更新 {t['stale_jobs']}"
          f" / 已消失 {t['inactive_history_jobs']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
