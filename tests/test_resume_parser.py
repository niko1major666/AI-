from src.data.resume_parser import (ats_suggestions, llm_parse_resume,
                                    parse_resume, parse_resume_full,
                                    _extract_experiences_regex)


def test_parse_email_phone():
    p = parse_resume("张三 13800138000 zhangsan@example.com 本科 清华大学")
    assert p.email == "zhangsan@example.com"
    assert p.phone == "13800138000"


def test_parse_education_highest_degree():
    p = parse_resume("硕士 本科 吉林大学 土木工程")
    assert p.highest_degree == "硕士"
    assert "吉林大学" in p.schools
    assert any("土木" in m for m in p.majors)


def test_parse_work_years():
    p = parse_resume("5年以上工作经验，熟悉Python和PyTorch")
    assert p.work_years == "5"


def test_parse_empty():
    p = parse_resume("热爱编程，性格开朗")
    assert p.email == "" and p.phone == ""
    assert p.degrees == [] and p.schools == []


def test_ats_missing_critical_info():
    p = parse_resume("热爱编程")
    tips = ats_suggestions(p, "热爱编程", [])
    texts = {t["tip"] for t in tips}
    assert any("邮箱" in t for t in texts)
    assert any("手机号" in t for t in texts)
    assert any("学历" in t for t in texts)


def test_ats_quantify_suggestion():
    p = parse_resume("13800138000 a@b.com 本科 清华大学 3年经验")
    # 无量化数字 + 无技能
    tips = ats_suggestions(p, "负责开发工作", [])
    texts = {t["tip"] for t in tips}
    assert any("量化" in t for t in texts)
    assert any("技能" in t for t in texts)


def test_llm_no_key_returns_none(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert llm_parse_resume("张三 本科 清华大学") is None


def test_parse_full_fallback_without_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    p = parse_resume_full("张三 13800138000 a@b.com 本科 吉林大学 土木工程")
    # 正则兜底：基础字段仍能识别
    assert p.email == "a@b.com"
    assert p.phone == "13800138000"
    assert p.highest_degree == "本科"
    assert "吉林大学" in p.schools
    # LLM 增强字段（姓名/经历）无 key 时为空
    assert p.name == ""
    assert p.experiences == []


def test_work_years_ignores_graduation_year():
    # 「2023 年毕业」不应被识别成「23 年经验」
    p = parse_resume("张三 本科 清华大学 2023年6月毕业")
    assert p.work_years == ""


def test_work_years_range():
    p = parse_resume("3-5年工作经验，熟悉Python")
    assert p.work_years == "3"


def test_extract_experiences_regex():
    text = (
        "2023.06-至今 腾讯科技有限公司 算法工程师\n"
        "2022.07-2023.05 清华大学 实验室 研究实习生"
    )
    exps = _extract_experiences_regex(text)
    assert len(exps) == 2
    assert exps[0]["company"] == "腾讯科技有限公司"
    assert exps[0]["title"] == "算法工程师"
    assert exps[1]["company"] == "清华大学"


def test_parse_full_uses_llm_skills_and_experiences(monkeypatch):
    fake = {
        "name": "张三",
        "email": "z@example.com",
        "phone": "13800138000",
        "highest_degree": "硕士",
        "school": "吉林大学",
        "major": "土木工程",
        "work_years": 3,
        "experiences": [
            {
                "company": "腾讯",
                "title": "算法工程师",
                "duration": "2023.06-至今",
                "description": "负责推荐系统模型",
                "achievements": ["准确率提升 15%"],
                "tech_stack": ["Python", "PyTorch"],
            }
        ],
        "skills": ["Python", "PyTorch", "机器学习"],
    }
    monkeypatch.setattr("src.data.resume_parser.llm_parse_resume", lambda text: fake)
    p = parse_resume_full("张三 硕士 吉林大学 土木工程")
    assert p.name == "张三"
    assert p.work_years == "3"
    assert p.skills == ["Python", "PyTorch", "机器学习"]
    assert len(p.experiences) == 1
    e = p.experiences[0]
    assert e["company"] == "腾讯"
    assert e["description"] == "负责推荐系统模型"
    assert e["achievements"] == ["准确率提升 15%"]
    assert e["tech_stack"] == ["Python", "PyTorch"]


def test_ats_suggest_name_and_experience():
    p = parse_resume("热爱编程")
    tips = ats_suggestions(p, "热爱编程", [])
    texts = {t["tip"] for t in tips}
    assert any("姓名" in t for t in texts)
    assert any("经历" in t for t in texts)


def test_ats_no_quantify_when_achievements_present():
    # 经历里已有量化成果时，不应再提示「成果缺乏量化」
    p = parse_resume("张三 13800138000 a@b.com 本科 清华大学 3年经验")
    p.experiences = [{"achievements": ["准确率提升 15%"]}]
    tips = ats_suggestions(p, "负责开发工作", ["Python"])
    texts = {t["tip"] for t in tips}
    assert not any("量化" in t for t in texts)
