from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "src" / "app" / "app.py"


def test_app_runs_without_exception():
    # 首屏要读 14MB 语料并跑一次规则抽取（冷缓存），慢 runner 上留足余量
    at = AppTest.from_file(str(APP), default_timeout=240)
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
    next(b for b in at.button if b.label == "生成差距报告").click().run()
    assert not at.exception, f"app exceptions: {at.exception}"

    # 抽到技能的岗位应给出匹配度，并展示 JD 硬性要求数量
    if at.metric:
        assert "匹配度" in at.metric[0].label
        assert any("硬性要求" in m.value for m in at.markdown)
        # C2：报告生成后应出现导出按钮（Markdown / Word）
        downloads = at.get("download_button")
        labels = [d.proto.label for d in downloads]
        assert any("Markdown" in lb for lb in labels), labels
        assert any("Word" in lb for lb in labels), labels

        # 「已学进度」联动（迭代 6）：勾选已掌握技能 → 路径重排，报告不消失、不报错
        if at.multiselect:
            first = list(at.multiselect[0].options)[0]
            at.multiselect[0].set_value([first]).run()
            assert not at.exception, f"app exceptions: {at.exception}"
            assert at.metric, "勾选已学进度后报告不应消失（session 渲染）"
            assert any("已学进度" in md.value for md in at.markdown)

        # 岗位收藏：点击后按钮变「已收藏」，报告仍在（rerun 不丢）
        fav_btn = next((b for b in at.button if "收藏该岗位" in b.label), None)
        if fav_btn is not None:
            fav_btn.click().run()
            assert not at.exception, f"app exceptions: {at.exception}"
            assert any("已收藏" in b.label for b in at.button)
            assert at.metric, "收藏触发的 rerun 不应让报告消失"


def test_gap_compare_mode_has_no_exception():
    """多岗位对比（C3）：切模式 → 选公司 → 输技能 → 对比，不抛异常且有匹配度指标。"""
    at = AppTest.from_file(str(APP), default_timeout=180)
    at.run()
    at.sidebar.radio[0].set_value("差距报告").run()
    assert not at.exception, f"app exceptions: {at.exception}"

    mode = next(r for r in at.radio if r.label == "分析模式")
    mode.set_value("多岗位对比").run()
    assert not at.exception, f"app exceptions: {at.exception}"

    company = next(s for s in at.selectbox if "选择公司" in s.label)
    company.set_value("腾讯").run()
    assert not at.exception, f"app exceptions: {at.exception}"

    skills = next(t for t in at.text_input if "逗号分隔" in t.label)
    skills.set_value("Python, PyTorch").run()
    run_btn = next(b for b in at.button if b.label == "开始对比")
    run_btn.click().run()
    assert not at.exception, f"app exceptions: {at.exception}"
    assert at.metric, "对比结果应有每个岗位的匹配度指标"
    assert any("%" in m.value for m in at.metric)
    assert at.dataframe, "对比结果应有明细表"


@pytest.mark.slow
def test_resume_page_strength_and_recommendations(monkeypatch):
    """简历页 C6/C7：上传 → 提取技能 → 技能画像 + 反向岗位推荐（全语料扫描，slow）。"""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    import streamlit as st

    class _FakeUpload:
        name = "resume.txt"

        def getvalue(self):
            return "熟悉 Python、PyTorch，做过 Transformer 项目".encode("utf-8")

    monkeypatch.setattr(st, "file_uploader", lambda *a, **k: _FakeUpload())

    at = AppTest.from_file(str(APP), default_timeout=180)
    at.run()
    at.sidebar.radio[0].set_value("简历匹配").run()
    assert not at.exception, f"app exceptions: {at.exception}"

    extract_btn = next(b for b in at.button if b.label == "提取技能")
    extract_btn.click().run()
    assert not at.exception, f"app exceptions: {at.exception}"

    assert any("技能画像" in s.value for s in at.subheader)
    assert any("适合我的岗位" in s.value for s in at.subheader)
    assert any("覆盖率" in m.label for m in at.metric)
    assert at.dataframe, "岗位推荐应有表格"
