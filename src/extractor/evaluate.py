"""span 级抽取评估：精确匹配 + 重叠匹配的 P / R / F1。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EvalResult:
    precision: float
    recall: float
    f1: float
    tp: int
    fp: int
    fn: int

    def to_dict(self) -> dict:
        return {"precision": self.precision, "recall": self.recall, "f1": self.f1,
                "tp": self.tp, "fp": self.fp, "fn": self.fn}


def _overlap(a, b) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def compute_span_f1(gold_spans, pred_spans, mode: str = "exact") -> EvalResult:
    """计算单条文本的 span 级 F1。

    gold_spans / pred_spans: [(start, end), ...]（半开区间）
    mode: exact（完全一致才算命中）| overlap（有重叠即算命中）
    """
    gold = [tuple(sorted(s)) for s in gold_spans]
    pred = [tuple(sorted(s)) for s in pred_spans]

    if mode == "exact":
        gs, ps = set(gold), set(pred)
        tp = len(gs & ps)
        fp = len(ps - gs)
        fn = len(gs - ps)
    elif mode == "overlap":
        tp = 0
        matched_pred = set()
        for g in gold:
            for i, p in enumerate(pred):
                if i in matched_pred:
                    continue
                if _overlap(g, p):
                    tp += 1
                    matched_pred.add(i)
                    break
        fp = len(pred) - tp
        fn = len(gold) - tp
    else:
        raise ValueError(f"未知模式：{mode}")

    precision = tp / len(pred) if pred else 0.0
    recall = tp / len(gold) if gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return EvalResult(round(precision, 4), round(recall, 4), round(f1, 4), tp, fp, fn)


def micro_average(results: list[EvalResult]) -> EvalResult:
    """跨多条文本的 micro 平均（按 tp/fp/fn 汇总）。"""
    tp = sum(r.tp for r in results)
    fp = sum(r.fp for r in results)
    fn = sum(r.fn for r in results)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return EvalResult(round(precision, 4), round(recall, 4), round(f1, 4), tp, fp, fn)
