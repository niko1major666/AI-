"""分析真实数据的技能分布，找出词表未覆盖的技能（用于扩充词表）。"""
import sys
from collections import Counter
from pathlib import Path

from datasets import load_dataset

ROOT = Path("D:/ai-skill-gap")
sys.path.insert(0, str(ROOT))

from src.skillkb.loader import Taxonomy

tax = Taxonomy(str(ROOT / "data" / "kb" / "skill_taxonomy.yaml"))
alias_set = set()
for s in tax.all_skills():
    for t in [s.name] + s.aliases:
        alias_set.add(str(t).lower().strip())

ds = load_dataset("zalizedata/tech-job-postings-salary-dataset", "S", streaming=True)
split = list(ds.keys())[0]
cnt = Counter()
for row in ds[split]:
    for sk in (row.get("skills") or []):
        cnt[str(sk).lower().strip()] += 1

print(f"数据集技能种类: {len(cnt)}  词表覆盖: {sum(1 for k in cnt if k in alias_set)}")
print("词表未覆盖的技能（Top 60）:")
for k, v in cnt.most_common():
    if k not in alias_set:
        print(f"  {k}: {v}")
