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
                                              user_skills=["Python"], user_majors=["统计学"])
    assert out["overview"]
    assert "40.0" in out["overview"]
    assert isinstance(out["plan"], list) and out["plan"]
    # 分阶段计划应包含 P0 阶段（硬门槛）
    phases = [p["phase"] for p in out["plan"]]
    assert any("1-2" in p or "1-2" in p for p in phases) or any("攻克" in p for p in phases)
    # tips 由简历专业驱动，且不含任何预设专业背景
    assert out["tips"] and "统计学" in out["tips"]
    assert "道桥" not in out["tips"]


def test_tips_hidden_without_major(monkeypatch):
    """未从简历解析到专业时，不展示专业迁移建议。"""
    monkeypatch.setattr(report_interpreter, "_get_api_key", lambda: "")
    out = report_interpreter.interpret_report(_make_report(), target_job="AI工程师",
                                              user_skills=["Python"])
    assert out["tips"] == ""


def test_major_hint_mapping():
    assert "会计学" in report_interpreter._major_hint(["会计学"])
    assert "土木工程" in report_interpreter._major_hint(["土木工程"])
    assert "计算机" in report_interpreter._major_hint(["计算机科学与技术"])
    assert report_interpreter._major_hint([]) == ""
    assert report_interpreter._major_hint(None) == ""
    # 未收录专业走通用兜底，仍以专业名开头
    assert "茶学" in report_interpreter._major_hint(["茶学"])


def test_llm_prompt_carries_major(monkeypatch):
    captured = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": '{"overview":"ok","plan":[],"tips":"t"}'}}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["prompt"] = json["messages"][1]["content"]
        return _Resp()

    monkeypatch.setattr(report_interpreter, "_get_api_key", lambda: "k")
    monkeypatch.setattr(report_interpreter.requests, "post", fake_post)

    out = report_interpreter.interpret_report(_make_report(), target_job="AI工程师",
                                              user_majors=["统计学"])
    assert "## 用户专业\n统计学" in captured["prompt"]
    assert out["tips"] == "t"

    report_interpreter.interpret_report(_make_report(), target_job="AI工程师")
    assert "## 用户专业\n（未提供）" in captured["prompt"]


def test_interpret_report_no_missing(monkeypatch):
    monkeypatch.setattr(report_interpreter, "_get_api_key", lambda: "")
    rep = GapReport(match_score=100.0, matched_skill_ids=["a"], matched_total=1,
                    missing_total=0, missing=[])
    out = report_interpreter.interpret_report(rep, target_job="AI工程师")
    assert out["overview"]
    assert out["plan"] == []
