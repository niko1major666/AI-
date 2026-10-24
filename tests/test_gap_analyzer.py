import math
from pathlib import Path

import pytest
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


def test_resources_attached():
    res = yaml.safe_load((ROOT / "data" / "kb" / "learning_resources.yaml").read_text(encoding="utf-8"))
    analyzer = SkillGapAnalyzer(_tax(), resources=res)
    jd = [{"skill_id": "AITECH.DISTRIBUTED", "name": "分布式训练", "is_must": True}]
    rep = analyzer.analyze([], jd)
    assert rep.missing_total == 1
    assert len(rep.missing[0].resources) > 0           # 有学习资源
    assert not hasattr(rep.missing[0], "transfer_hint")  # 迁移建议已移除


def test_analyzer_signature_has_no_transfer_map():
    """回归：背景迁移能力已从分析器移除。"""
    analyzer = SkillGapAnalyzer(_tax())
    assert not hasattr(analyzer, "detect_background")
    assert not hasattr(analyzer, "_transfer")
    assert not hasattr(analyzer, "_transfer_keywords")


def test_importance_weighted_priority():
    analyzer = SkillGapAnalyzer(_tax())
    jd = [
        {"skill_id": "AITECH.LLM", "name": "大模型", "is_must": False},
        {"skill_id": "PROG.SCALA", "name": "Scala", "is_must": False},
    ]
    demand = {"AITECH.LLM": 0.3, "PROG.SCALA": 0.3}
    rep = analyzer.analyze([], jd, demand=demand)
    by_id = {m.skill_id: m for m in rep.missing}

    # 每个缺失项都带 importance 字段（数据驱动：SCALA 占比 <1% → 1）
    assert by_id["AITECH.LLM"].importance == 5
    assert by_id["PROG.SCALA"].importance == 1
    # 同样需求占比下，重要度高的技能优先级分更高
    assert by_id["AITECH.LLM"].priority_score > by_id["PROG.SCALA"].priority_score


def test_priority_order_p0_first():
    analyzer = SkillGapAnalyzer(_tax())
    jd = [
        {"skill_id": "PROG.SCALA", "name": "Scala", "is_must": False},
        {"skill_id": "AITECH.LLM", "name": "大模型", "is_must": True},
        {"skill_id": "AITECH.RAG", "name": "RAG", "is_must": False},
    ]
    demand = {"PROG.SCALA": 0.1, "AITECH.LLM": 0.2, "AITECH.RAG": 0.9}
    rep = analyzer.analyze([], jd, demand=demand)
    # P0（硬性缺失）恒排在缺失清单最前，即使需求占比低
    assert rep.missing[0].priority == "P0"
    assert rep.missing[0].skill_id == "AITECH.LLM"


def test_tf_emphasis_increases_weight():
    """JD 内多次提及的技能权重更高（1 + ln tf），命中/缺失都按强调度计分。"""
    analyzer = SkillGapAnalyzer(_tax())
    jd = [
        {"skill_id": "PROG.PYTHON", "name": "Python", "is_must": True, "tf": 1},
        {"skill_id": "FRAMEWORK.PYTORCH", "name": "PyTorch", "is_must": True, "tf": 5},
    ]
    rep = analyzer.analyze(["Python"], jd)
    # Python 权重 2.0（must）；PyTorch 权重 2.0 × (1 + ln5) = 5.219 → 2 / 7.219
    assert analyzer.weight({"is_must": True, "tf": 5}) == pytest.approx(2.0 * (1 + math.log(5)))
    assert rep.match_score == 27.7


def test_must_evidence_appears_in_reason():
    analyzer = SkillGapAnalyzer(_tax())
    jd = [{
        "skill_id": "PROG.PYTHON", "name": "Python", "is_must": True,
        "must_evidence": "句内含「必须」", "tf": 1,
    }]
    rep = analyzer.analyze([], jd, demand={"PROG.PYTHON": 0.2})
    assert rep.missing[0].priority == "P0"
    assert "必须" in rep.missing[0].why

