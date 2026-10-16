"""importance 数据化：用真实 JD 需求频率替换人工标定。

占比 → importance 阈值（基于分位数）：
  >=10% → 5（核心必备）  >=5% → 4（高频）  >=2% → 3（中等）
  >=1%  → 2（低频）       <1%  → 1（罕见/未出现）
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
TAX = ROOT / "data" / "kb" / "skill_taxonomy.yaml"

from src.skillkb.loader import Taxonomy  # noqa: E402
from src.extractor.rule_baseline import RuleBaselineExtractor  # noqa: E402


def ratio_to_importance(r: float) -> int:
    if r >= 0.10:
        return 5
    if r >= 0.05:
        return 4
    if r >= 0.02:
        return 3
    if r >= 0.01:
        return 2
    return 1


def main():
    taxonomy = Taxonomy(str(TAX))
    rule = RuleBaselineExtractor(taxonomy)

    jobs = [json.loads(x) for x in
            (ROOT / "data" / "processed" / "jobs.jsonl").read_text(encoding="utf-8").splitlines()]
    total = len(jobs)

    cnt = Counter()
    for j in jobs:
        spans = rule.extract_spans(j["job_id"], j.get("jd_clean") or j.get("jd_text", ""))
        for sid in {s.skill_id for s in spans}:
            cnt[sid] += 1
    demand = {sid: c / total for sid, c in cnt.items()}

    # 更新 taxonomy.yaml
    text = TAX.read_text(encoding="utf-8")
    lines = text.splitlines()
    out = []
    changed = 0
    for line in lines:
        m = re.search(r"id:\s*([A-Z]+\.[A-Z_0-9]+)", line)
        if m and "importance:" in line:
            sid = m.group(1)
            new_imp = ratio_to_importance(demand.get(sid, 0.0))
            line = re.sub(r"importance:\s*\d+", f"importance: {new_imp}", line)
            changed += 1
        out.append(line)
    TAX.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"已按需求占比更新 {changed} 个技能的 importance\n")

    # 输出 Top 40 对比（新 importance + 占比）
    ranked = sorted(demand.items(), key=lambda x: -x[1])
    print("=== Top 40 技能（占比 → importance）===")
    for sid, r in ranked[:40]:
        sk = taxonomy.by_id(sid)
        name = sk.name if sk else sid
        print(f"  {name:<16} {r:6.1%}  →  {ratio_to_importance(r)}")
    print(f"\n（未出现在 JD 的技能 importance 均为 1）")


if __name__ == "__main__":
    main()
