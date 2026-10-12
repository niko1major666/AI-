import json
import sys
from pathlib import Path

ROOT = Path("D:/ai-skill-gap")
sys.path.insert(0, str(ROOT))

from src.extractor.rule_baseline import RuleBaselineExtractor
from src.skillkb.loader import Taxonomy

tax = Taxonomy(str(ROOT / "data" / "kb" / "skill_taxonomy.yaml"))
rule = RuleBaselineExtractor(tax)
jobs = [json.loads(x) for x in (ROOT / "data" / "processed" / "jobs.jsonl").read_text(encoding="utf-8").splitlines()]
print("总 JD 数:", len(jobs))
for j in jobs[:4]:
    spans = rule.extract_spans(j["job_id"], j.get("jd_clean") or j.get("jd_text", ""))
    print(f"{j['company']} | {j['title']} -> {[s.skill_text for s in spans]}")
