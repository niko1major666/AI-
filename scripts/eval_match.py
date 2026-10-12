"""对比 TF-IDF vs BGE 的 Recall@5 / MRR / Hit@1。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.matcher.bge_matcher import BgeMatcher
from src.matcher.evaluate import compute_retrieval_metrics
from src.matcher.tfidf_matcher import TfidfMatcher
from src.skillkb.loader import Taxonomy


def main():
    taxonomy = Taxonomy(str(ROOT / "data" / "kb" / "skill_taxonomy.yaml"))
    names = [s.name for s in taxonomy.all_skills()]
    name2id = {s.name: s.id for s in taxonomy.all_skills()}

    pairs = [json.loads(x) for x in (ROOT / "data" / "gold" / "skill_pair_gold.jsonl").read_text(encoding="utf-8").splitlines()]
    queries = [(p["query"], p["skill_id"]) for p in pairs]
    print(f"匹配样本 {len(queries)}，语料技能 {len(names)}")

    tfidf = TfidfMatcher().fit(names)
    def tfidf_fn(q, top_k=5):
        return [name2id[n] for n, _ in tfidf.search(q, top_k=top_k)]

    bge = BgeMatcher(query_instruction="")
    bge.fit(names)
    def bge_fn(q, top_k=5):
        return [name2id[n] for n, _ in bge.search(q, top_k=top_k)]

    print(f"\n{'方法':<10}{'Recall@5':>10}{'MRR':>10}{'Hit@1':>10}{'Hits':>7}")
    for name, fn in [("tfidf", tfidf_fn), ("bge", bge_fn)]:
        m = compute_retrieval_metrics(queries, fn, k=5)
        print(f"{name:<10}{m.recall_at_k:>10.4f}{m.mrr:>10.4f}{m.hit_at_1:>10.4f}"
              f"{str(m.hits)+'/'+str(m.total):>7}")


if __name__ == "__main__":
    main()
