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
