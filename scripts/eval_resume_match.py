"""语义匹配评测（口语化简历句子 → 技能）。

对比 TF-IDF vs BGE 在真实简历场景（口语化句子，不含技能词）下的匹配能力，
比旧评测（短技能名）更能体现语义模型的优势。
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
# 复用项目内缓存（避免联网下载）
os.environ.setdefault("HF_HOME", str(ROOT / "models" / "hf_cache"))
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from src.skillkb.loader import Taxonomy  # noqa: E402
from src.matcher.tfidf_matcher import TfidfMatcher  # noqa: E402
from src.matcher.bge_matcher import BgeMatcher  # noqa: E402
from src.matcher.evaluate import compute_retrieval_metrics  # noqa: E402


def main():
    taxonomy = Taxonomy(str(ROOT / "data" / "kb" / "skill_taxonomy.yaml"))
    name_to_id = {s.name: s.id for s in taxonomy.all_skills()}
    corpus = list(name_to_id.keys())

    gold = [json.loads(x) for x in
            (ROOT / "data" / "gold" / "resume_sentence_gold.jsonl").read_text(encoding="utf-8").splitlines()]
    pairs = []
    for g in gold:
        sk = taxonomy.by_id(g["skill_id"])
        if sk:
            pairs.append((g["query"], sk.name))
    print(f"评测样本: {len(pairs)} 条（语料 {len(corpus)} 技能）\n", flush=True)

    tfidf = TfidfMatcher().fit(corpus)

    def tfidf_search(q, top_k=5):
        return [name for name, _ in tfidf.search(q, top_k)]

    m_tfidf = compute_retrieval_metrics(pairs, tfidf_search)
    print("TF-IDF 评测完成", flush=True)

    bge = BgeMatcher().fit(corpus)

    def bge_search(q, top_k=5):
        return [name for name, _ in bge.search(q, top_k)]

    m_bge = compute_retrieval_metrics(pairs, bge_search)
    print("BGE 评测完成\n", flush=True)

    print("=== 口语化简历句子 → 技能 匹配 ===")
    print(f"TF-IDF(char n-gram):  Recall@5={m_tfidf.recall_at_k}  MRR={m_tfidf.mrr}  Hit@1={m_tfidf.hit_at_1}")
    print(f"BGE-base-zh-v1.5:     Recall@5={m_bge.recall_at_k}  MRR={m_bge.mrr}  Hit@1={m_bge.hit_at_1}")

    print("\n=== BGE 命中但 TF-IDF 未命中（语义优势样本）===")
    diff = 0
    for q, correct in pairs:
        if correct in bge_search(q) and correct not in tfidf_search(q):
            diff += 1
            if diff <= 20:
                print(f"  {q}  →  {correct}")
    print(f"  共 {diff} 条")

    print("\n=== TF-IDF 命中但 BGE 未命中（BGE 短板）===")
    diff2 = 0
    for q, correct in pairs:
        if correct in tfidf_search(q) and correct not in bge_search(q):
            diff2 += 1
            if diff2 <= 20:
                print(f"  {q}  →  {correct}")
    print(f"  共 {diff2} 条")


if __name__ == "__main__":
    main()
