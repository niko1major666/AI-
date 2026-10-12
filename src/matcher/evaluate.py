"""语义匹配评估：Recall@K / MRR / Hit@1。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RetrievalMetrics:
    recall_at_k: float
    mrr: float
    hit_at_1: float
    hits: int
    total: int

    def to_dict(self) -> dict:
        return {"recall_at_k": self.recall_at_k, "mrr": self.mrr,
                "hit_at_1": self.hit_at_1, "hits": self.hits, "total": self.total}


def compute_retrieval_metrics(pairs, search_fn, k: int = 5) -> RetrievalMetrics:
    """计算检索指标。

    pairs: [(query, correct_id), ...]
    search_fn: (query, top_k) -> [id, ...]（按分数降序）
    """
    hits = 0
    mrr = 0.0
    hit1 = 0
    for query, correct in pairs:
        ids = search_fn(query, top_k=k)
        if correct in ids:
            hits += 1
            rank = ids.index(correct) + 1
            mrr += 1.0 / rank
            if rank == 1:
                hit1 += 1
    total = len(pairs)
    return RetrievalMetrics(
        recall_at_k=round(hits / total, 4) if total else 0.0,
        mrr=round(mrr / total, 4) if total else 0.0,
        hit_at_1=round(hit1 / total, 4) if total else 0.0,
        hits=hits, total=total,
    )
