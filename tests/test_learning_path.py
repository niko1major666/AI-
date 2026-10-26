from pathlib import Path
from types import SimpleNamespace

from src.matcher.learning_path import (
    SKILL_PREREQS,
    build_learning_path,
    format_path_markdown,
    hours_for,
)
from src.skillkb.loader import Taxonomy

ROOT = Path(__file__).resolve().parents[1]
TAX = ROOT / "data" / "kb" / "skill_taxonomy.yaml"


def _gap(sid, name, priority, diff=3, score=0.0, resources=None):
    return SimpleNamespace(skill_id=sid, name=name, priority=priority,
                           difficulty=diff, priority_score=score,
                           resources=resources or [])


def test_prereq_ids_exist_in_taxonomy():
    """先修表里出现的每个 id 都必须是词表里真实存在的技能（防止改名后静默失效）。"""
    tax = Taxonomy(str(TAX))
    for sid, pres in SKILL_PREREQS.items():
        assert tax.by_id(sid) is not None, f"未知技能 id: {sid}"
        for p in pres:
            assert tax.by_id(p) is not None, f"{sid} 的前置技能不存在: {p}"


def test_p0_is_always_placed_in_first_stage():
    path = build_learning_path([
        _gap("PROG.SCALA", "Scala", "P2"),
        _gap("PROG.PYTHON", "Python", "P0", diff=1, score=50),
    ])
    assert path.stages[0].phase.startswith("阶段 1")
    assert [s.skill_id for s in path.stages[0].steps] == ["PROG.PYTHON"]
    assert [s.skill_id for s in path.stages[1].steps] == ["PROG.SCALA"]


def test_prereq_order_within_stage():
    """同一阶段内，先修技能必须排在依赖它的技能之前（即使后者优先级分更高）。"""
    path = build_learning_path([
        _gap("AITECH.RAG", "RAG", "P0", score=99),
        _gap("AITECH.LLM", "大模型", "P0", score=1),
    ])
    ids = [s.skill_id for s in path.stages[0].steps]
    assert ids.index("AITECH.LLM") < ids.index("AITECH.RAG")


def test_cross_stage_prereq_pulled_forward():
    """P0 技能依赖的 P2 技能会被提到第一阶段，并给出前置提示。"""
    path = build_learning_path([
        _gap("AITECH.RAG", "RAG", "P0", score=99),
        _gap("AITECH.EMBEDDING", "Embedding", "P2", score=1),
    ], taxonomy=Taxonomy(str(TAX)))
    first = [s.skill_id for s in path.stages[0].steps]
    assert "AITECH.EMBEDDING" in first and "AITECH.RAG" in first
    rag = next(s for s in path.stages[0].steps if s.skill_id == "AITECH.RAG")
    # 大模型不在缺口内 → 提示先补前置
    assert "大模型" in rag.prereq_note


def test_hours_follow_difficulty_and_week_rounding():
    assert [hours_for(d) for d in range(1, 6)] == [2, 4, 8, 16, 24]
    assert hours_for(0) == 2 and hours_for(99) == 24   # 越界夹到 1~5
    path = build_learning_path([
        _gap("PROG.PYTHON", "Python", "P0", diff=1),
        _gap("FRAMEWORK.PYTORCH", "PyTorch", "P0", diff=3),
        _gap("ML.TRANSFORMER", "Transformer", "P0", diff=3),
    ], hours_per_week=10)
    stage = path.stages[0]
    assert stage.hours == 2 + 8 + 8
    assert stage.weeks == 2       # 18 学时 / 每周 10 → ceil(1.8)=2
    assert path.total_weeks == stage.weeks


def test_actions_have_generic_fallback():
    path = build_learning_path([_gap("PROG.PYTHON", "Python", "P0", diff=1)])
    actions = path.stages[0].steps[0].actions
    assert actions and any("最小项目" in a for a in actions)


def test_actions_follow_resource_type():
    res = [{"type": "paper", "title": "Attention Is All You Need", "url": "https://arxiv.org/abs/1706.03762"}]
    path = build_learning_path([_gap("ML.TRANSFORMER", "Transformer", "P0", resources=res)])
    actions = path.stages[0].steps[0].actions
    assert any("论文" in a for a in actions)


def test_empty_missing_returns_empty_path():
    path = build_learning_path([])
    assert path.stages == [] and path.total_hours == 0 and path.total_weeks == 0
    assert "无需学习路径" in format_path_markdown(path)


def test_markdown_contains_totals_and_skills():
    path = build_learning_path([_gap("PROG.PYTHON", "Python", "P0", diff=1)])
    md = format_path_markdown(path, hours_per_week=5)
    assert "Python" in md and "阶段 1" in md and "每周 5 小时" in md
    assert path.total_hours == 2


def test_learned_skills_are_skipped_and_recorded():
    """标记「已学完」的技能不再进入路径，并计入 skipped（保持缺口原顺序）。"""
    path = build_learning_path([
        _gap("PROG.PYTHON", "Python", "P0", diff=1),
        _gap("AITECH.RAG", "RAG", "P1", diff=3),
    ], learned={"PROG.PYTHON"})
    assert [s.skill_id for st in path.stages for s in st.steps] == ["AITECH.RAG"]
    assert path.skipped == ["Python"]
    assert path.total_hours == 8               # 2 + 8 → 只剩 RAG 的 8 学时
    assert path.to_dict()["skipped"] == ["Python"]
    assert "已学进度" in format_path_markdown(path)


def test_learned_prereq_no_longer_hints_extra_prep():
    """已学完的先修视为已具备：不再提示「前置技能不在缺口内」。"""
    path = build_learning_path([
        _gap("AITECH.RAG", "RAG", "P0", score=99),
        _gap("AITECH.EMBEDDING", "Embedding", "P2", score=1),
    ], taxonomy=Taxonomy(str(TAX)), learned={"AITECH.LLM"})
    rag = next(s for s in path.stages[0].steps if s.skill_id == "AITECH.RAG")
    assert rag.prereq_note == ""
    assert [s.skill_id for s in path.stages[0].steps] == ["AITECH.EMBEDDING", "AITECH.RAG"]


def test_all_missing_learned_returns_empty_path_with_note():
    path = build_learning_path([_gap("PROG.PYTHON", "Python", "P0", diff=1)],
                               learned={"PROG.PYTHON"})
    assert path.stages == [] and path.total_hours == 0 and path.total_weeks == 0
    assert path.skipped == ["Python"]
    md = format_path_markdown(path)
    assert "已学进度" in md and "Python" in md


def test_learned_unknown_or_blank_ids_are_ignored():
    path = build_learning_path([_gap("PROG.PYTHON", "Python", "P0", diff=1)],
                               learned={"NOPE.X", "  ", None})
    assert [s.skill_id for s in path.stages[0].steps] == ["PROG.PYTHON"]
    assert path.skipped == []
