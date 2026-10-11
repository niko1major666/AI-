from pathlib import Path

from src.extractor.rule_baseline import RuleBaselineExtractor
from src.skillkb.loader import Taxonomy

TAX = Path(__file__).resolve().parents[1] / "data" / "kb" / "skill_taxonomy.yaml"


def _extractor() -> RuleBaselineExtractor:
    return RuleBaselineExtractor(Taxonomy(str(TAX)))


def test_rule_baseline_extracts_known_skills():
    ex = _extractor()
    text = "熟悉Python、PyTorch、DeepSpeed；了解RAG检索增强、向量数据库、LoRA微调；掌握Transformer与注意力机制。"
    spans = ex.extract_spans("j1", text)
    ids = {s.skill_id for s in spans}
    assert "PROG.PYTHON" in ids
    assert "FRAMEWORK.PYTORCH" in ids
    assert "FRAMEWORK.DEEPSPEED" in ids
    assert "AITECH.RAG" in ids
    assert "AITECH.VECTORDB" in ids
    assert "AITECH.LORA" in ids
    assert "ML.TRANSFORMER" in ids
    assert "ML.ATTENTION" in ids


def test_rule_baseline_ascii_word_boundary():
    ex = _extractor()
    # "go" 不应匹配 "Google"（词边界保护）
    spans = ex.extract_spans("j2", "使用Google搜索")
    assert all(s.skill_id != "PROG.GO" for s in spans)


def test_rule_baseline_no_overlap_dup():
    ex = _extractor()
    spans = ex.extract_spans("j3", "熟悉PyTorch")
    ids = [s.skill_id for s in spans]
    # PyTorch 只出现一次，不因别名 torch 重复
    assert ids.count("FRAMEWORK.PYTORCH") == 1
