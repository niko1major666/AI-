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


def test_detect_background():
    tm = yaml.safe_load((ROOT / "data" / "kb" / "transfer_map.yaml").read_text(encoding="utf-8"))
    analyzer = SkillGapAnalyzer(_tax(), transfer_map=tm)
    text = "熟练使用AutoCAD、sketchup等建模软件；掌握BIM技术；开展桥梁检测与道路勘测；"
    text += "进行定性分析和实验数据分析；完成地质勘察报告撰写"
    bg = analyzer.detect_background(text)
    sources = {b["source_skill"] for b in bg}
    assert any("CAD" in s or "BIM" in s for s in sources)          # T3
    assert any("桥梁" in s for s in sources)                        # T2
    assert any("数据分析" in s or "地质" in s for s in sources)     # T4
    for b in bg:
        assert b["targets"]                                        # 有目标技能
        assert b["keywords"]                                       # 有关键词


def test_importance_weighted_priority():
    analyzer = SkillGapAnalyzer(_tax())
    jd = [
        {"skill_id": "AITECH.LLM", "name": "大模型", "is_must": False},
        {"skill_id": "PROG.SCALA", "name": "Scala", "is_must": False},
    ]
    demand = {"AITECH.LLM": 0.3, "PROG.SCALA": 0.3}
    rep = analyzer.analyze([], jd, demand=demand)
    by_id = {m.skill_id: m for m in rep.missing}

    # 每个缺失项都带 importance 字段
    assert by_id["AITECH.LLM"].importance == 5
    assert by_id["PROG.SCALA"].importance == 2
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
