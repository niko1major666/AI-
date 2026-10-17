from src.data.resume_parser import (ats_suggestions, llm_parse_resume,
                                    parse_resume, parse_resume_full)


def test_parse_email_phone():
    p = parse_resume("张三 13800138000 zhangsan@example.com 本科 清华大学")
    assert p.email == "zhangsan@example.com"
    assert p.phone == "13800138000"


def test_parse_education_highest_degree():
    p = parse_resume("硕士 本科 吉林大学 道路桥梁与渡河工程")
    assert p.highest_degree == "硕士"
    assert "吉林大学" in p.schools
    assert any("道路" in m for m in p.majors)


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
    p = parse_resume_full("张三 13800138000 a@b.com 本科 吉林大学 道路桥梁与渡河工程")
    # 正则兜底：基础字段仍能识别
    assert p.email == "a@b.com"
    assert p.phone == "13800138000"
    assert p.highest_degree == "本科"
    assert "吉林大学" in p.schools
    # LLM 增强字段（姓名/经历）无 key 时为空
    assert p.name == ""
    assert p.experiences == []
