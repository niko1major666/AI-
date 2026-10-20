from pathlib import Path

from src.skillkb.loader import Taxonomy

TAX = Path(__file__).resolve().parents[1] / "data" / "kb" / "skill_taxonomy.yaml"


def _tax() -> Taxonomy:
    return Taxonomy(str(TAX))


def test_load_counts():
    t = _tax()
    assert len(t.all_skills()) == 147
    assert len(t.categories) == 6


def test_resolve_exact_name():
    t = _tax()
    assert t.resolve("Python").id == "PROG.PYTHON"
    assert t.resolve("pytorch").id == "FRAMEWORK.PYTORCH"
    assert t.resolve("向量数据库").id == "AITECH.VECTORDB"
    assert t.resolve("分布式训练").id == "AITECH.DISTRIBUTED"


def test_resolve_alias():
    t = _tax()
    assert t.resolve("多卡训练").id == "AITECH.DISTRIBUTED"
    assert t.resolve("飞桨").id == "FRAMEWORK.PADDLE"


def test_resolve_fuzzy():
    t = _tax()
    assert t.resolve("pytho").id == "PROG.PYTHON"


def test_resolve_unknown_none():
    t = _tax()
    assert t.resolve("zzzzz不存在的技能") is None


def test_by_id():
    t = _tax()
    assert t.by_id("AITECH.RAG").name == "RAG"
    assert t.by_id("NOPE") is None


def test_importance_field():
    t = _tax()
    # 高频技能重要度高（数据驱动：按 JD 需求占比，当前语料 4582 条 / 78 家）
    assert t.by_id("PROG.PYTHON").importance == 5
    assert t.by_id("FRAMEWORK.PYTORCH").importance == 5
    assert t.by_id("AITECH.LLM").importance == 5
    assert t.by_id("AITECH.AGENT").importance == 5
    # 中高频技能
    assert t.by_id("AITECH.RAG").importance == 4
    assert t.by_id("ML.RL").importance == 4
    # 低频技能重要度低（占比 <1% → 1）
    assert t.by_id("PROG.SCALA").importance == 1
    # 中等频次（2%~5% → 3）
    assert t.by_id("BIGDATA.FLINK").importance == 3
    # 数据标注：高频但低门槛（难度低），importance 反映需求频率
    assert t.by_id("AITECH.ANNOTATE").importance == 3
