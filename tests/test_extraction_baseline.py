"""抽取指标回归：改词表 / 抽取规则后，规则基线在 gold 上的 F1 不得明显退化。

基线由 `scripts/eval_all.py` 生成（2026-10 迭代 3 实测）：
- test  (10 条): P=0.9167 R=1.0000 F1(exact)=0.9565
- 全部  (40 条): P=0.8966 R=0.9286 F1(exact)=0.9123 / F1(overlap)=0.9298
阈值取「基线 - 1pt」，既能拦住明显退化，又不会因个别样本边界抖动而误报。
"""
import json
from pathlib import Path

import pytest

from src.extractor.evaluate import compute_span_f1, micro_average
from src.extractor.rule_baseline import RuleBaselineExtractor
from src.skillkb.loader import Taxonomy

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "data" / "gold"
TOLERANCE = 0.01
BASELINE = {
    "jd_skills_gold_test.jsonl": {"n": 10, "f1_exact": 0.9565, "recall": 1.0},
    "jd_skills_gold.jsonl": {"n": 40, "f1_exact": 0.9123, "f1_overlap": 0.9298},
}


def _rule():
    return RuleBaselineExtractor(Taxonomy(str(ROOT / "data" / "kb" / "skill_taxonomy.yaml")))


def _load(name):
    text = (GOLD / name).read_text(encoding="utf-8")
    return [json.loads(x) for x in text.splitlines() if x.strip()]


def _evaluate(name, mode="exact"):
    rule = _rule()
    results = []
    for i, row in enumerate(_load(name)):
        gold = [(s["start"], s["end"]) for s in row["spans"]]
        pred = [(s.start, s.end) for s in
                rule.extract_spans(row.get("job_id") or f"gold-{i}", row["text"])
                if s.start is not None]
        results.append(compute_span_f1(gold, pred, mode=mode))
    return micro_average(results)


@pytest.mark.parametrize("name", list(BASELINE))
def test_rule_baseline_f1_not_regressed(name):
    base = BASELINE[name]
    m = _evaluate(name, "exact")
    assert m.f1 >= base["f1_exact"] - TOLERANCE, (
        f"{name} 抽取 F1 退化：{m.f1:.4f} < 基线 {base['f1_exact']:.4f} - {TOLERANCE}"
    )


def test_rule_baseline_test_split_recall():
    base = BASELINE["jd_skills_gold_test.jsonl"]
    m = _evaluate("jd_skills_gold_test.jsonl", "exact")
    assert m.recall >= base["recall"] - TOLERANCE


def test_rule_baseline_overlap_not_worse_than_exact():
    """overlap 口径只应不低于 exact（边界错位在 overlap 下仍算命中）。"""
    exact = _evaluate("jd_skills_gold.jsonl", "exact")
    overlap = _evaluate("jd_skills_gold.jsonl", "overlap")
    assert overlap.f1 >= exact.f1 - 1e-9
    assert overlap.f1 >= BASELINE["jd_skills_gold.jsonl"]["f1_overlap"] - TOLERANCE


def test_gold_splits_are_disjoint_and_cover_all_rows():
    train = {r["text"] for r in _load("jd_skills_gold_train.jsonl")}
    test = {r["text"] for r in _load("jd_skills_gold_test.jsonl")}
    full = _load("jd_skills_gold.jsonl")
    assert not (train & test), "train/test 有重叠样本"
    assert len(train) + len(test) == len(full)
