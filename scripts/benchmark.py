"""延迟 benchmark：技能抽取与语义匹配的单次推理延迟（mean / p50 / p95）。"""
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _percentile(xs, p):
    xs = sorted(xs)
    k = (len(xs) - 1) * p
    f = int(k)
    c = f + 1 if f + 1 < len(xs) else f
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def benchmark(fn, warmup=3, runs=10):
    for _ in range(warmup):
        fn()
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t0)
    return {"mean_ms": round(statistics.mean(times) * 1000, 2),
            "p50_ms": round(statistics.median(times) * 1000, 2),
            "p95_ms": round(_percentile(times, 0.95) * 1000, 2)}


def main():
    text = "负责大模型预训练与微调。熟悉Python、PyTorch、DeepSpeed；了解RAG、向量数据库、LoRA微调；深入理解Transformer与注意力机制。"
    query = "写Python脚本做深度学习"

    from src.extractor.rule_baseline import RuleBaselineExtractor
    from src.skillkb.loader import Taxonomy
    taxonomy = Taxonomy(str(ROOT / "data" / "kb" / "skill_taxonomy.yaml"))
    rule = RuleBaselineExtractor(taxonomy)

    print("=== 技能抽取延迟（单条 JD 文本）===")
    print(f"rule_baseline : {benchmark(lambda: rule.extract_spans('x', text), runs=20)}")

    from src.extractor.bert_ner import BertNerExtractor
    bert = BertNerExtractor(str(ROOT / "models" / "bert_ner"))
    print(f"bert_ner      : {benchmark(lambda: bert.extract_char_spans(text), warmup=2, runs=5)}")

    from src.extractor.siamese_uie import SiameseUIEExtractor
    uie = SiameseUIEExtractor(device="cpu")
    schema = {"软件": None, "AI专有技术": None}
    print(f"siamese_uie   : {benchmark(lambda: uie.extract_raw(text, schema), warmup=1, runs=3)}")

    print("\n=== 语义匹配延迟（单条 query → 128 技能）===")
    from src.matcher.tfidf_matcher import TfidfMatcher
    names = [s.name for s in taxonomy.all_skills()]
    tfidf = TfidfMatcher().fit(names)
    print(f"tfidf         : {benchmark(lambda: tfidf.search(query, top_k=5), runs=20)}")

    from src.matcher.bge_matcher import BgeMatcher
    bge = BgeMatcher()
    bge.fit(names)
    print(f"bge           : {benchmark(lambda: bge.search(query, top_k=5), warmup=2, runs=10)}")


if __name__ == "__main__":
    main()
