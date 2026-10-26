from src.data.resume_parser import (ats_suggestions, llm_parse_resume,
                                    parse_resume, parse_resume_full,
                                    _extract_experiences_regex,
                                    _normalize_experience_kind)


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
    # 经历类型：公司岗位=工作，含「实习」=实习
    assert exps[0]["kind"] == "work"
    assert exps[1]["kind"] == "internship"


def test_normalize_experience_kind_aliases():
    assert _normalize_experience_kind("work") == "work"
    assert _normalize_experience_kind("全职工作") == "work"
    assert _normalize_experience_kind("实习") == "internship"
    assert _normalize_experience_kind("科研项目") == "project"
    assert _normalize_experience_kind("unexpected") == "other"


def test_infer_experience_kind_from_title_and_org():
    # LLM 没给 kind：按角色/组织关键词推断
    assert _normalize_experience_kind("", {"company": "腾讯", "title": "算法工程师"}) == "work"
    assert _normalize_experience_kind(None, {"company": "清华大学 实验室", "title": "研究助理"}) == "project"
    # 「项目经理」是岗位，不是项目经历
    assert _normalize_experience_kind("", {"company": "某集团", "title": "项目经理"}) == "work"
    assert _normalize_experience_kind("", {"company": "", "title": "志愿者"}) == "other"


def test_experiences_regex_uses_section_headings():
    text = (
        "工作经历\n2023.06-至今 腾讯科技有限公司 算法工程师\n"
        "项目经历\n2022.07-2023.05 清华大学 实验室 研究助理\n"
    )
    exps = _extract_experiences_regex(text)
    kinds = {e["company"]: e["kind"] for e in exps}
    assert kinds["腾讯科技有限公司"] == "work"
    assert kinds["清华大学"] == "project"


def test_experiences_regex_skips_education_section():
    # 教育经历里的时间范围不算工作/项目经历
    text = (
        "教育经历\n2019.09-2023.06 吉林大学 本科\n"
        "项目经历\n2022.09-2023.01 吉林大学 实验室 科研项目\n"
    )
    exps = _extract_experiences_regex(text)
    assert len(exps) == 1
    assert exps[0]["kind"] == "project"


def test_profile_groups_work_internship_and_project(monkeypatch):
    fake = {
        "name": "张三",
        "experiences": [
            {"kind": "work", "company": "腾讯", "title": "算法工程师"},
            {"kind": "internship", "company": "字节跳动", "title": "算法实习生"},
            {"kind": "project", "company": "清华大学实验室", "title": "RAG 项目"},
            {"company": "", "title": "志愿者"},
        ],
    }
    monkeypatch.setattr("src.data.resume_parser.llm_parse_resume", lambda text: fake)
    p = parse_resume_full("张三")
    assert [e["title"] for e in p.work_experiences] == ["算法工程师", "算法实习生"]
    assert [e["title"] for e in p.project_experiences] == ["RAG 项目"]
    assert [e["title"] for e in p.other_experiences] == ["志愿者"]
    # 分类结果写回 experiences，供 to_dict / 导出使用
    assert [e["kind"] for e in p.experiences] == ["work", "internship", "project", "other"]


def test_ats_suggests_project_experience_when_only_work():
    p = parse_resume("张三 13800138000 a@b.com 本科 清华大学 3年经验")
    p.experiences = [{"kind": "work", "company": "腾讯", "title": "算法工程师"}]
    tips = ats_suggestions(p, "负责开发工作 提升 15%", ["Python"])
    texts = {t["tip"] for t in tips}
    assert any("未识别到项目经历" in t for t in texts)
    assert not any("未识别到工作/实习经历" in t for t in texts)


def test_ats_suggests_work_when_only_project():
    p = parse_resume("张三 13800138000 a@b.com 本科 清华大学 3年经验")
    p.experiences = [{"kind": "project", "company": "清华大学实验室", "title": "RAG 项目"}]
    tips = ats_suggestions(p, "负责开发工作 提升 15%", ["Python"])
    texts = {t["tip"] for t in tips}
    assert any("未识别到工作/实习经历" in t for t in texts)
    assert not any("未识别到项目经历" in t for t in texts)


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
