"""匹配指标回归：TF-IDF 检索基线在 gold 上的 Recall@5 不得退化。

基线（2026-10 迭代 3 实测）：
- skill_pair_gold（40 条短技能查询）: Recall@5=0.9750 MRR=0.9229 Hit@1=0.9000
- resume_sentence_gold（50 条口语化简历句）: Recall@5=0.2200
BGE 需要加载模型，不进 CI；其对比结果见 `python scripts/eval_resume_match.py`。
"""
import json
from pathlib import Path

import pytest

from src.matcher.evaluate import compute_retrieval_metrics
from src.matcher.tfidf_matcher import TfidfMatcher
from src.skillkb.loader import Taxonomy

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "data" / "gold"
TOLERANCE = 0.02
BASELINE = {"skill_pair_gold.jsonl": 0.9750, "resume_sentence_gold.jsonl": 0.2200}


def _pairs(gold_name):
    tax = Taxonomy(str(ROOT / "data" / "kb" / "skill_taxonomy.yaml"))
    gold = [json.loads(x) for x in
            (GOLD / gold_name).read_text(encoding="utf-8").splitlines() if x.strip()]
    pairs = []
    for g in gold:
        sk = tax.by_id(g.get("skill_id"))
        if sk is not None:
            pairs.append((g["query"], sk.name))
    return tax, pairs


def _tfidf(tax):
    matcher = TfidfMatcher().fit([s.name for s in tax.all_skills()])

    def search(q, top_k=5):
        return [name for name, _ in matcher.search(q, top_k)]

    return search


@pytest.mark.parametrize("gold_name", list(BASELINE))
def test_tfidf_recall_at_5_not_regressed(gold_name):
    tax, pairs = _pairs(gold_name)
    assert len(pairs) >= 40
    m = compute_retrieval_metrics(pairs, _tfidf(tax))
    base = BASELINE[gold_name]
    assert m.recall_at_k >= base - TOLERANCE, (
        f"{gold_name} Recall@5 退化：{m.recall_at_k:.4f} < 基线 {base:.4f} - {TOLERANCE}"
    )


def test_short_skill_queries_still_strong():
    """短技能名查询必须保持较高命中（改分词/别名后最先坏的就是这一档）。"""
    tax, pairs = _pairs("skill_pair_gold.jsonl")
    m = compute_retrieval_metrics(pairs, _tfidf(tax))
    assert m.hit_at_1 >= 0.85
    assert m.mrr >= 0.88


def test_gold_skill_ids_all_exist_in_taxonomy():
    """gold 里引用的技能 id 必须都在词表里（词表改名会让评测样本静默丢失）。"""
    tax = Taxonomy(str(ROOT / "data" / "kb" / "skill_taxonomy.yaml"))
    for gold_name in BASELINE:
        _tax, pairs = _pairs(gold_name)
        gold = [json.loads(x) for x in
                (GOLD / gold_name).read_text(encoding="utf-8").splitlines() if x.strip()]
        assert len(pairs) == len(gold)
        assert all(tax.by_id(g["skill_id"]) for g in gold)
