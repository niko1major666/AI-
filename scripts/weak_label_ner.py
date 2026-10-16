"""弱标注：用规则基线自动标注大量 JD，扩充 BERT-NER 训练集（裁剪版）。

关键：真实 JD 技能词稀疏（O 标签占 95%+），整段训练会让模型倾向预测 O、recall 崩溃。
故改为「围绕每个技能 span 裁剪短上下文」（前后各 ctx 字符），生成接近人工短句的训练样本，
技能词占比高，BERT-NER 才能学到技能词的上下文模式。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]

from src.skillkb.loader import Taxonomy  # noqa: E402
from src.extractor.rule_baseline import RuleBaselineExtractor  # noqa: E402


def main(limit: int = 400, ctx: int = 18):
    taxonomy = Taxonomy(str(ROOT / "data" / "kb" / "skill_taxonomy.yaml"))
    rule = RuleBaselineExtractor(taxonomy)

    jobs = [json.loads(x) for x in
            (ROOT / "data" / "processed" / "jobs.jsonl").read_text(encoding="utf-8").splitlines()]

    rows = []
    for j in jobs:
        text = j.get("jd_clean") or j.get("jd_text", "")
        spans = rule.extract_spans(j["job_id"], text)
        if not spans:
            continue
        for s in spans:
            lo = max(0, s.start - ctx)
            hi = min(len(text), s.end + ctx)
            snippet = text[lo:hi]
            if len(snippet) < 10:
                continue
            rows.append({
                "text": snippet,
                "spans": [{"start": s.start - lo, "end": s.end - lo, "skill": s.skill_text}],
            })
            if len(rows) >= limit:
                break
        if len(rows) >= limit:
            break

    out = ROOT / "data" / "gold" / "weak_train.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    avg_len = sum(len(r["text"]) for r in rows) / len(rows)
    print(f"弱标注 {len(rows)} 条（平均句长 {avg_len:.0f} 字符）→ {out}")


if __name__ == "__main__":
    main()
