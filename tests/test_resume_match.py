import json
from pathlib import Path

from src.matcher.evaluate import compute_retrieval_metrics
from src.matcher.tfidf_matcher import TfidfMatcher
from src.skillkb.loader import Taxonomy

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "data" / "gold" / "resume_sentence_gold.jsonl"


def _load():
    tax = Taxonomy(str(ROOT / "data" / "kb" / "skill_taxonomy.yaml"))
    gold = [json.loads(x) for x in GOLD.read_text(encoding="utf-8").splitlines()]
    return tax, gold


def test_resume_sentence_gold_valid():
    tax, gold = _load()
    assert len(gold) == 50
    for g in gold:
        assert g["query"].strip()          # query 非空
        assert tax.by_id(g["skill_id"]) is not None  # skill_id 有效


def test_resume_sentence_task_is_hard():
    """口语化句子不含技能词，TF-IDF 字符匹配应显著低于满分（证明任务比旧评测难）。"""
    tax, gold = _load()
    names = [s.name for s in tax.all_skills()]
    pairs = [(g["query"], tax.by_id(g["skill_id"]).name) for g in gold]

    tfidf = TfidfMatcher().fit(names)

    def fn(q, top_k=5):
        return [name for name, _ in tfidf.search(q, top_k)]

    m = compute_retrieval_metrics(pairs, fn, k=5)
    # 旧评测（短技能名）0.975；口语化句子应远低于此
    assert m.recall_at_k < 0.5
