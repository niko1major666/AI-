from src.matcher.jd_requirements import judge_requirements, must_skills


def test_must_cue_in_sentence():
    text = "岗位职责：负责推荐系统迭代。任职要求：必须熟练掌握 Python，熟悉 PyTorch 框架。"
    judged = judge_requirements(text, [
        ("PROG.PYTHON", text.index("Python")),
        ("FRAMEWORK.PYTORCH", text.index("PyTorch")),
    ])
    assert judged["PROG.PYTHON"]["is_must"] is True
    assert "必须" in judged["PROG.PYTHON"]["evidence"]
    # 「熟悉」不是 must 触发词，但同句/同段落在「任职要求」下 → 仍判为硬性
    assert judged["FRAMEWORK.PYTORCH"]["is_must"] is True


def test_nice_cue_wins_over_must_cue():
    text = "熟悉 Docker 优先；必须掌握 Kubernetes。"
    judged = judge_requirements(text, [
        ("ENV.DOCKER", text.index("Docker")),
        ("ENV.K8S", text.index("Kubernetes")),
    ])
    assert judged["ENV.DOCKER"]["is_must"] is False
    assert "优先" in judged["ENV.DOCKER"]["evidence"]
    assert judged["ENV.K8S"]["is_must"] is True


def test_section_header_decides_when_sentence_has_no_cue():
    text = "加分项：\n有 Rust 项目经验。\n任职要求：\n能独立完成 Go 服务开发。"
    judged = judge_requirements(text, [
        ("PROG.RUST", text.index("Rust")),
        ("PROG.GO", text.index("Go")),
    ])
    assert judged["PROG.RUST"]["is_must"] is False
    assert judged["PROG.GO"]["is_must"] is True


def test_demand_fallback_when_text_has_no_signal():
    text = "负责后端服务开发。"
    judged = judge_requirements(text, [("A", 0), ("B", 0)], demand={"A": 0.35, "B": 0.05})
    assert judged["A"]["is_must"] is True
    assert "需求占比" in judged["A"]["evidence"]
    assert judged["B"]["is_must"] is False


def test_must_appearance_wins_over_nice_appearance():
    text = "任职要求：熟悉 Python。加分项：熟悉 Python 者优先。"
    judged = judge_requirements(text, [
        ("PROG.PYTHON", text.index("Python")),
        ("PROG.PYTHON", text.rindex("Python")),
    ])
    assert judged["PROG.PYTHON"]["is_must"] is True


def test_english_jd_requirements():
    text = "Requirements: strong experience with Python and Kubernetes.\nNice to have: Rust."
    judged = judge_requirements(text, [
        ("A", text.index("Python")),
        ("B", text.index("Rust")),
    ])
    assert judged["A"]["is_must"] is True
    assert judged["B"]["is_must"] is False


def test_must_skills_helper_filters_and_sorts():
    text = "必须掌握 Python；了解 Rust。"
    ids = must_skills(text, [("Z.PY", text.index("Python")), ("A.RUST", text.index("Rust"))])
    assert ids == ["Z.PY"]
