from src.matcher import report_interpreter
from src.matcher.gap_analyzer import GapItem, GapReport


def _make_report() -> GapReport:
    missing = [
        GapItem(skill_id="ML.TRANSFORMER", name="Transformer", category="机器学习",
                is_must=True, difficulty=4, importance=5, priority="P0",
                priority_score=90.0, why="硬性要求", resources=[]),
        GapItem(skill_id="AITECH.RAG", name="RAG", category="AI技术",
                is_must=False, difficulty=2, importance=4, priority="P1",
                priority_score=50.0, why="高频需求", resources=[]),
    ]
    return GapReport(match_score=40.0, matched_skill_ids=["PROG.PYTHON"],
                     matched_total=1, missing_total=2, missing=missing)


def test_interpret_report_fallback(monkeypatch):
    monkeypatch.setattr(report_interpreter, "_get_api_key", lambda: "")
    out = report_interpreter.interpret_report(_make_report(), target_job="AI工程师",
                                              user_skills=["Python"])
    assert out["overview"]
    assert "40.0" in out["overview"]
    assert isinstance(out["plan"], list) and out["plan"]
    # 分阶段计划应包含 P0 阶段（硬门槛）
    phases = [p["phase"] for p in out["plan"]]
    assert any("1-2" in p or "1-2" in p for p in phases) or any("攻克" in p for p in phases)
    assert out["tips"]


def test_interpret_report_no_missing(monkeypatch):
    monkeypatch.setattr(report_interpreter, "_get_api_key", lambda: "")
    rep = GapReport(match_score=100.0, matched_skill_ids=["a"], matched_total=1,
                    missing_total=0, missing=[])
    out = report_interpreter.interpret_report(rep, target_job="AI工程师")
    assert out["overview"]
    assert out["plan"] == []
