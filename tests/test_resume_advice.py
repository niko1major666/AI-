from pathlib import Path
from types import SimpleNamespace

from src.data.resume_advice import build_advice, find_evidence, skill_tokens
from src.skillkb.loader import Taxonomy

ROOT = Path(__file__).resolve().parents[1]
TAX = ROOT / "data" / "kb" / "skill_taxonomy.yaml"


def _tax():
    return Taxonomy(str(TAX))


def _gap(sid, name, priority="P0", resources=None):
    return SimpleNamespace(skill_id=sid, name=name, priority=priority,
                           resources=resources or [])


def test_skill_tokens_include_alias_and_skip_extract():
    sk = _tax().by_id("ML.QUANT")
    toks = [t.lower() for t in skill_tokens(sk)]
    assert "模型量化" in toks
    assert "量化" in toks          # skip_extract 也用于简历侧识别


def test_find_evidence_matches_alias_case_insensitive():
    sk = _tax().by_id("ML.TRANSFORMER")
    hits = find_evidence(sk, "用 PyTorch 复现了 Transformer 的注意力机制")
    assert hits


def test_advice_existing_experience_status():
    tax = _tax()
    adv = build_advice([_gap("ML.TRANSFORMER", "Transformer")], tax,
                       "用 PyTorch 复现了 Transformer 的注意力机制")
    assert adv[0]["status"] == "已有相关经历"
    assert adv[0]["evidence"]
    assert "XXX" in adv[0]["suggestion"]           # 数字用占位符，不编造


def test_advice_missing_experience_status():
    tax = _tax()
    adv = build_advice([_gap("AITECH.RAG", "RAG")], tax, "我是应届生，做过课程作业")
    assert adv[0]["status"] == "需补充项目"
    assert adv[0]["evidence"] == []
    assert "RAG" in adv[0]["suggestion"]


def test_project_idea_from_resources_or_category():
    tax = _tax()
    with_res = build_advice([_gap("AITECH.RAG", "RAG",
                                  resources=[{"title": "LangChain RAG 教程", "url": "u"}])], tax, "")
    assert "LangChain RAG 教程" in with_res[0]["project_idea"]

    no_res = build_advice([_gap("PROG.PYTHON", "Python")], tax, "")
    assert no_res[0]["project_idea"]       # 有兜底建议


def test_limit_respected():
    tax = _tax()
    gaps = [_gap(f"PROG.PYTHON", f"技能{i}", resources=[]) for i in range(10)]
    assert len(build_advice(gaps, tax, "", limit=3)) == 3
    assert build_advice(gaps, tax, "", limit=0) == []


def test_empty_input():
    assert build_advice([], _tax(), "随便写") == []
