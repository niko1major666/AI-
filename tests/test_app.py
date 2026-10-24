from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "src" / "app" / "app.py"


def test_app_runs_without_exception():
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    assert not at.exception, f"app exceptions: {at.exception}"


def test_gap_page_interaction_has_no_exception(monkeypatch):
    """差距报告页交互回归：选公司 → 选岗位 → 输入技能 → 生成报告，不应抛异常。

    must/nice 判定与零技能兜底都在这一页，改抽取结构后必须有集成保护。
    """
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    import src.matcher.report_interpreter as ri
    monkeypatch.setattr(ri, "interpret_report",
                        lambda *a, **k: {"overview": "", "plan": [], "tips": ""})

    at = AppTest.from_file(str(APP), default_timeout=180)
    at.run()
    at.sidebar.radio[0].set_value("差距报告").run()
    assert not at.exception, f"app exceptions: {at.exception}"

    at.selectbox[0].set_value("腾讯").run()
    assert not at.exception, f"app exceptions: {at.exception}"
    # 有些岗位抽不到技能且无可用邻居（按钮前会提前返回），逐个试探直到能出报告
    picked = False
    for job in list(at.selectbox[1].options)[:15]:
        at.selectbox[1].set_value(job).run()
        if at.button:
            picked = True
            break
    assert picked, "前 15 个岗位都无法生成报告"
    # 注意：页面还有一个「搜索岗位」输入框，这里必须按 label 精确定位技能输入框
    skill_input = next(t for t in at.text_input if "直接输入技能" in t.label)
    skill_input.set_value("Python, PyTorch").run()
    at.button[0].click().run()
    assert not at.exception, f"app exceptions: {at.exception}"

    # 抽到技能的岗位应给出匹配度，并展示 JD 硬性要求数量
    if at.metric:
        assert "匹配度" in at.metric[0].label
        assert any("硬性要求" in m.value for m in at.markdown)
