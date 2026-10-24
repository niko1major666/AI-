"""一键评测：技能抽取 F1 / 语义匹配 Recall / 知识库与资源覆盖，生成 docs/metrics.md。

用法：`python scripts/eval_all.py`
- 只依赖本地数据（gold jsonl + jobs.jsonl + 词表），不联网、不下载模型
- 结果确定性（无时间戳），可直接提交到 docs/metrics.md 作为版本基线
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

import yaml  # noqa: E402

from src.extractor.evaluate import compute_span_f1, micro_average  # noqa: E402
from src.extractor.rule_baseline import RuleBaselineExtractor  # noqa: E402
from src.matcher.evaluate import compute_retrieval_metrics  # noqa: E402
from src.matcher.tfidf_matcher import TfidfMatcher  # noqa: E402
from src.skillkb.loader import Taxonomy  # noqa: E402

KB = ROOT / "data" / "kb"
GOLD = ROOT / "data" / "gold"
PROCESSED = ROOT / "data" / "processed"
EXTRACTION_SPLITS = ("jd_skills_gold_test.jsonl", "jd_skills_gold_train.jsonl", "jd_skills_gold.jsonl")
MATCHING_SPLITS = ("skill_pair_gold.jsonl", "resume_sentence_gold.jsonl")


def _jsonl(path: Path) -> list:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def eval_extraction(tax: Taxonomy) -> list[dict]:
    rule = RuleBaselineExtractor(tax)
    out = []
    for name in EXTRACTION_SPLITS:
        rows = _jsonl(GOLD / name)
        results = {"exact": [], "overlap": []}
        for i, row in enumerate(rows):
            gold = [(s["start"], s["end"]) for s in row["spans"]]
            pred = [(s.start, s.end) for s in
                    rule.extract_spans(row.get("job_id") or f"gold-{i}", row["text"])
                    if s.start is not None]
            for mode in results:
                results[mode].append(compute_span_f1(gold, pred, mode=mode))
        exact, overlap = micro_average(results["exact"]), micro_average(results["overlap"])
        out.append({
            "dataset": name, "n": len(rows),
            "precision": exact.precision, "recall": exact.recall,
            "f1_exact": exact.f1, "f1_overlap": overlap.f1,
        })
    return out


def eval_matching(tax: Taxonomy) -> list[dict]:
    matcher = TfidfMatcher().fit([s.name for s in tax.all_skills()])

    def search(q, top_k=5):
        return [name for name, _ in matcher.search(q, top_k)]

    out = []
    for name in MATCHING_SPLITS:
        rows = _jsonl(GOLD / name)
        pairs = [(r["query"], tax.by_id(r["skill_id"]).name) for r in rows
                 if tax.by_id(r.get("skill_id"))]
        m = compute_retrieval_metrics(pairs, search)
        out.append({"dataset": name, "n": len(pairs), "recall_at_5": m.recall_at_k,
                    "mrr": m.mrr, "hit_at_1": m.hit_at_1})
    return out


def eval_corpus(tax: Taxonomy) -> dict:
    jobs = _jsonl(PROCESSED / "jobs.jsonl")
    rule = RuleBaselineExtractor(tax)
    hit, zero = set(), 0
    for j in jobs:
        ids = {s.skill_id for s in rule.extract_spans(
            j["job_id"], j.get("jd_clean") or j.get("jd_text", ""))}
        if not ids:
            zero += 1
        hit |= ids
    all_ids = {s.id for s in tax.all_skills()}
    return {
        "jobs": len(jobs),
        "companies": len({j.get("company") for j in jobs}),
        "zero_skill": zero,
        "zero_skill_ratio": zero / len(jobs) if jobs else 0.0,
        "skills_total": len(all_ids),
        "skills_hit": len(hit),
        "skills_missing": sorted(all_ids - hit),
    }


def eval_resources(tax: Taxonomy) -> dict:
    res = yaml.safe_load((KB / "learning_resources.yaml").read_text(encoding="utf-8"))
    blocks = res.get("resources") or []
    total = len(tax.all_skills())
    return {"skills_total": total, "skills_covered": len(blocks),
            "coverage": len(blocks) / total if total else 0.0,
            "items": sum(len(b.get("items") or []) for b in blocks)}


def render_markdown(extraction, matching, corpus, resources) -> str:
    lines = [
        "# 评测指标（自动生成）",
        "",
        "> 由 `python scripts/eval_all.py` 生成；改动词表 / 抽取规则 / 匹配策略后请重跑并提交。",
        "> 结果不含时间戳，便于在 diff 中直接看到指标变化。",
        "",
        "## 1. 技能抽取（规则基线 RuleBaselineExtractor）",
        "",
        "| 数据集 | 样本 | Precision | Recall | F1 (exact) | F1 (overlap) |",
        "|---|---|---|---|---|---|",
    ]
    for r in extraction:
        lines.append(f"| {r['dataset']} | {r['n']} | {r['precision']:.4f} | {r['recall']:.4f} | "
                     f"{r['f1_exact']:.4f} | {r['f1_overlap']:.4f} |")
    lines += [
        "",
        "## 2. 语义匹配（TF-IDF 字符 n-gram 基线）",
        "",
        "| 数据集 | 样本 | Recall@5 | MRR | Hit@1 |",
        "|---|---|---|---|---|",
    ]
    for r in matching:
        lines.append(f"| {r['dataset']} | {r['n']} | {r['recall_at_5']:.4f} | "
                     f"{r['mrr']:.4f} | {r['hit_at_1']:.4f} |")
    lines += [
        "",
        "> BGE 语义模型需要本地权重，不在自动评测内；对比结果见 `python scripts/eval_resume_match.py`。",
        "",
        "## 3. 语料与知识库覆盖",
        "",
        f"- 语料规模：**{corpus['jobs']}** 条 JD / **{corpus['companies']}** 家公司",
        f"- 零技能岗位：**{corpus['zero_skill']}** 条（{corpus['zero_skill_ratio']:.1%}，"
        "差距报告会用同公司相似岗位兜底）",
        f"- 技能命中：**{corpus['skills_hit']}/{corpus['skills_total']}**"
        f"（{corpus['skills_hit'] / corpus['skills_total']:.1%}）",
    ]
    if corpus["skills_missing"]:
        lines.append(f"- 语料未出现：{'、'.join(corpus['skills_missing'])}（保留词条，属于语料缺口而非词表缺口）")
    lines += [
        f"- 学习资源覆盖：**{resources['skills_covered']}/{resources['skills_total']}** 个技能"
        f"（{resources['coverage']:.1%}），共 {resources['items']} 条资源",
        "",
        "## 4. 回归阈值（测试中固化）",
        "",
        "| 指标 | 基线 | 允许退化 | 测试 |",
        "|---|---|---|---|",
        f"| 抽取 F1 (test, exact) | {extraction[0]['f1_exact']:.4f} | 1pt | "
        "`tests/test_extraction_baseline.py` |",
        f"| 抽取 F1 (all, exact) | {extraction[-1]['f1_exact']:.4f} | 1pt | "
        "`tests/test_extraction_baseline.py` |",
        f"| skill_pair Recall@5 | {matching[0]['recall_at_5']:.4f} | 2pt | "
        "`tests/test_matcher_baseline.py` |",
        f"| resume_sentence Recall@5 | {matching[1]['recall_at_5']:.4f} | 2pt | "
        "`tests/test_matcher_baseline.py` |",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    tax = Taxonomy(str(KB / "skill_taxonomy.yaml"))
    print("评测抽取 F1 …", flush=True)
    extraction = eval_extraction(tax)
    print("评测 TF-IDF 匹配 …", flush=True)
    matching = eval_matching(tax)
    print("统计语料覆盖（约 10s）…", flush=True)
    corpus = eval_corpus(tax)
    resources = eval_resources(tax)

    md = render_markdown(extraction, matching, corpus, resources)
    out = ROOT / "docs" / "metrics.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    # 显式 LF：跨平台生成同一份字节，CI 的 git diff --exit-code 才有意义
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(md + "\n")

    print("\n=== 抽取（exact F1）===")
    for r in extraction:
        print(f"  {r['dataset']:<28} n={r['n']:<3} F1={r['f1_exact']:.4f} (overlap {r['f1_overlap']:.4f})")
    print("=== 匹配（Recall@5）===")
    for r in matching:
        print(f"  {r['dataset']:<28} n={r['n']:<3} Recall@5={r['recall_at_5']:.4f} MRR={r['mrr']:.4f}")
    print(f"=== 覆盖 ===\n  语料 {corpus['jobs']} 条 / 技能 {corpus['skills_hit']}/{corpus['skills_total']}"
          f" / 资源 {resources['skills_covered']}/{resources['skills_total']}")
    print(f"\n已写入 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

