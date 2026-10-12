from pathlib import Path

import yaml

from src.matcher.gap_analyzer import SkillGapAnalyzer
from src.skillkb.loader import Taxonomy

ROOT = Path(__file__).resolve().parents[1]
TAX = ROOT / "data" / "kb" / "skill_taxonomy.yaml"


def _tax() -> Taxonomy:
    return Taxonomy(str(TAX))


def test_match_user_skills_exact():
    analyzer = SkillGapAnalyzer(_tax())
    m = analyzer.match_user_skills(["Python", "向量数据库", "不会的东西xyz"])
    assert "PROG.PYTHON" in m
    assert "AITECH.VECTORDB" in m
    assert m["PROG.PYTHON"]["method"] == "exact"


def test_analyze_score_and_priority():
    analyzer = SkillGapAnalyzer(_tax())
    jd = [
        {"skill_id": "PROG.PYTHON", "name": "Python", "is_must": True},
        {"skill_id": "FRAMEWORK.PYTORCH", "name": "PyTorch", "is_must": True},
        {"skill_id": "AITECH.RAG", "name": "RAG", "is_must": False},
    ]
    demand = {"PROG.PYTHON": 0.8, "FRAMEWORK.PYTORCH": 0.7, "AITECH.RAG": 0.4}
    rep = analyzer.analyze(["Python"], jd, demand=demand)

    # 命中 Python(must=2)；缺失 PyTorch(must=2)、RAG(nice=1) => 2/5*100
    assert rep.match_score == 40.0
    assert rep.matched_total == 1
    assert rep.missing_total == 2

    prios = {m.skill_id: m.priority for m in rep.missing}
    assert prios["FRAMEWORK.PYTORCH"] == "P0"   # 硬性缺失
    assert prios["AITECH.RAG"] == "P1"          # 需求 0.4 >= 0.3


def test_transfer_hint_and_resources():
    tm = yaml.safe_load((ROOT / "data" / "kb" / "transfer_map.yaml").read_text(encoding="utf-8"))
    res = yaml.safe_load((ROOT / "data" / "kb" / "learning_resources.yaml").read_text(encoding="utf-8"))
    analyzer = SkillGapAnalyzer(_tax(), transfer_map=tm, resources=res)
    jd = [{"skill_id": "AITECH.DISTRIBUTED", "name": "分布式训练", "is_must": True}]
    rep = analyzer.analyze([], jd)
    assert rep.missing_total == 1
    assert rep.missing[0].transfer_hint != ""          # 分布式训练在道桥迁移映射中
    assert len(rep.missing[0].resources) > 0           # 有学习资源
