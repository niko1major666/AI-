"""对比 SiameseUIE / 规则基线 / BERT-NER 在测试集上的 span 级 F1。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.extractor.evaluate import compute_span_f1, micro_average


def load_gold(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines()]


def spans_to_offsets(spans):
    return [(s.start, s.end) for s in spans if s.start is not None and s.end is not None]


def evaluate(extractor_fn, test_rows, mode="exact"):
    results = []
    for row in test_rows:
        gold = [(s["start"], s["end"]) for s in row["spans"]]
        pred = extractor_fn(row["text"])
        results.append(compute_span_f1(gold, pred, mode=mode))
    return micro_average(results)


def build_extractors():
    from src.extractor.rule_baseline import RuleBaselineExtractor
    from src.skillkb.loader import Taxonomy

    taxonomy = Taxonomy(str(ROOT / "data" / "kb" / "skill_taxonomy.yaml"))
    rule = RuleBaselineExtractor(taxonomy)

    def rule_fn(text):
        return spans_to_offsets(rule.extract_spans("x", text))

    from src.extractor.siamese_uie import SiameseUIEExtractor, _flatten
    uie = SiameseUIEExtractor(device="cpu")
    schema = {"软件": None, "AI专有技术": None, "编程语言": None, "深度学习框架": None,
              "机器学习算法": None, "大数据与数据处理": None, "工程工具与平台": None}

    def uie_fn(text):
        flat = _flatten(uie.extract_raw(text, schema))
        offsets = []
        for items in flat.values():
            for it in items:
                if isinstance(it, dict) and it.get("start") is not None:
                    offsets.append((it["start"], it["end"]))
        return offsets

    from src.extractor.bert_ner import BertNerExtractor
    bert = BertNerExtractor(str(ROOT / "models" / "bert_ner"))

    def bert_fn(text):
        return bert.extract_char_spans(text)

    return [("rule_baseline", rule_fn), ("siamese_uie", uie_fn), ("bert_ner", bert_fn)]


def main():
    test_rows = load_gold(ROOT / "data" / "gold" / "jd_skills_gold_test.jsonl")
    print(f"测试样本 {len(test_rows)}")
    for mode in ("exact", "overlap"):
        print(f"\n=== {mode} 匹配 ===")
        print(f"{'方法':<16}{'Precision':>10}{'Recall':>10}{'F1':>10}{'TP':>5}{'FP':>5}{'FN':>5}")
        for name, fn in build_extractors():
            r = evaluate(fn, test_rows, mode=mode)
            print(f"{name:<16}{r.precision:>10.4f}{r.recall:>10.4f}{r.f1:>10.4f}"
                  f"{r.tp:>5}{r.fp:>5}{r.fn:>5}")


if __name__ == "__main__":
    main()
