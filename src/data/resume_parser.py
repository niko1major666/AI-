"""简历结构化解析（中文简历启发式规则 + DeepSeek LLM 增强）+ ATS 视角改进建议。"""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field

import requests

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
DEGREE_RE = re.compile(r"(博士|硕士|研究生|本科|学士|大专|专科)")
SCHOOL_RE = re.compile(r"[\u4e00-\u9fa5]{2,20}(?:大学|学院)")
MAJOR_RE = re.compile(
    r"(计算机科学与技术|软件工程|人工智能|数据科学|大数据|电子信息|通信工程|机械工程|"
    r"土木工程|道路桥梁|道路与桥梁|桥梁工程|数学与应用数学|应用数学|统计学|自动化|电子工程)"
)
# 工作年限：数字前加负向断言，避免把「2023 年毕业」误识别成「23 年经验」
YEARS_RE = re.compile(r"(?<!\d)(\d{1,2})\s*年(?:以上|及|余|工作经验|相关经验|经验)?")
YEARS_RANGE_RE = re.compile(r"(?<!\d)(\d{1,2})\s*[-~至到]\s*(\d{1,2})\s*年")

# 工作/项目经历粗提取（正则兜底，无 LLM 时用）
TIME_RANGE_RE = re.compile(
    r"(20\d{2})[.\-/年]\s*(\d{1,2})[.\-/月]?\s*[-~至到—]+\s*"
    r"((?:20\d{2})[.\-/年]\s*\d{1,2}[.\-/月]?|至今|现在)"
)
COMPANY_RE = re.compile(
    r"[\u4e00-\u9fa5A-Za-z0-9]{2,30}(?:公司|集团|大学|学院|实验室|研究院|研究所|中心|工作室|事务所)"
)
TITLE_RE = re.compile(
    r"[\u4e00-\u9fa5A-Za-z0-9]{2,20}(?:算法工程师|架构师|工程师|科学家|研究员|实习生|负责人|经理|总监|专员|主管|讲师|教师|顾问|分析师)"
)

_DEGREE_RANK = {"博士": 5, "硕士": 4, "研究生": 4, "本科": 3, "学士": 3, "大专": 2, "专科": 2}


@dataclass
class ResumeProfile:
    email: str = ""
    phone: str = ""
    name: str = ""
    degrees: list = field(default_factory=list)
    highest_degree: str = ""
    schools: list = field(default_factory=list)
    majors: list = field(default_factory=list)
    work_years: str = ""
    experiences: list = field(default_factory=list)
    skills: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _extract_work_years(text: str) -> str:
    """提取工作年限：优先「N-M 年」范围（取下限），其次「N 年（以上/经验）」。"""
    m = YEARS_RANGE_RE.search(text)
    if m:
        return m.group(1)
    m = YEARS_RE.search(text)
    if m:
        return m.group(1)
    return ""


def parse_resume(text: str) -> ResumeProfile:
    email = EMAIL_RE.search(text)
    phone = PHONE_RE.search(text)
    degrees = list(dict.fromkeys(DEGREE_RE.findall(text)))
    highest = ""
    if degrees:
        highest = max(degrees, key=lambda d: _DEGREE_RANK.get(d, 0))
    schools = list(dict.fromkeys(SCHOOL_RE.findall(text)))
    majors = list(dict.fromkeys(MAJOR_RE.findall(text)))
    return ResumeProfile(
        email=email.group(0) if email else "",
        phone=phone.group(0) if phone else "",
        degrees=degrees,
        highest_degree=highest,
        schools=schools,
        majors=majors,
        work_years=_extract_work_years(text),
    )


_DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
_DEEPSEEK_MODEL = "deepseek-chat"

_LLM_PROMPT = """你是专业的简历解析助手。从下面的简历文本提取结构化信息，严格输出一个 JSON 对象。

字段（没有就填空值 / 空数组）：
- name: 姓名（字符串）
- email: 邮箱（字符串）
- phone: 手机号（字符串）
- highest_degree: 最高学历（博士/硕士/本科/大专/其他 之一）
- school: 毕业院校（字符串）
- major: 所学专业（字符串）
- work_years: 工作年限数字（整数，没有则 0；只填数字，不要带「年」字）
- experiences: 工作/项目经历数组，每项含：
    company(组织名称)、title(角色/职位)、duration(时间段，如「2023.06-至今」)、
    description(一句话职责概述，30 字以内)、achievements(量化成果字符串数组)、
    tech_stack(用到的技术栈字符串数组)
- skills: 技能字符串数组（编程语言/框架/算法/工具，尽量用标准名称）

简历文本：
{text}

只输出 JSON 对象，不要 markdown 代码块或解释。"""


def _get_api_key() -> str:
    """获取 DeepSeek key：环境变量优先（本地），Streamlit secrets 兜底（云端）。过滤占位符/非 ASCII 值。"""
    def _valid(k: str) -> bool:
        if not k:
            return False
        if "在此填入" in k or "密钥" in k or "你的" in k:
            return False
        try:
            k.encode("ascii")
            return True
        except UnicodeEncodeError:
            return False

    env = os.environ.get("DEEPSEEK_API_KEY") or ""
    if _valid(env):
        return env
    try:
        import streamlit as st
        skey = st.secrets.get("DEEPSEEK_API_KEY")
        if skey and _valid(str(skey)):
            return str(skey)
    except Exception:  # noqa: BLE001
        pass
    return ""


def llm_parse_resume(text: str) -> dict | None:
    """用 DeepSeek LLM 增强解析（姓名/工作经历等正则难做的字段）。无 key/失败返回 None。"""
    api_key = _get_api_key()
    if not api_key:
        return None
    try:
        resp = requests.post(
            _DEEPSEEK_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": _DEEPSEEK_MODEL,
                "messages": [{"role": "user", "content": _LLM_PROMPT.format(text=text[:6000])}],
                "response_format": {"type": "json_object"},
                "temperature": 0,
                "max_tokens": 1500,
            },
            timeout=90,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.M)
        return json.loads(content)
    except Exception:  # noqa: BLE001
        return None


def _normalize_experiences(exps: list) -> list:
    """把 LLM 返回的经历统一为 dict，补齐细粒度字段（职责/量化成果/技术栈）。"""
    out = []
    for e in exps:
        if not isinstance(e, dict):
            continue
        item = {}
        for k in ("company", "title", "duration", "description"):
            v = e.get(k)
            item[k] = str(v).strip() if v else ""
        for k in ("achievements", "tech_stack"):
            v = e.get(k)
            item[k] = [str(x).strip() for x in v if str(x).strip()] if isinstance(v, list) else []
        # 只要有一个非空字段就保留
        if any(item.values()):
            out.append(item)
    return out


def _extract_experiences_regex(text: str) -> list:
    """无 LLM 时按时间段粗切工作/项目经历，提取组织 + 角色 + 时间段。"""
    spans = list(TIME_RANGE_RE.finditer(text))
    if not spans:
        return []
    exps = []
    for i, m in enumerate(spans):
        end = spans[i + 1].start() if i + 1 < len(spans) else len(text)
        seg = text[m.start():end]
        comp = COMPANY_RE.search(seg)
        title = TITLE_RE.search(seg)
        item = {
            "company": comp.group(0) if comp else "",
            "title": title.group(0) if title else "",
            "duration": m.group(0),
            "description": "",
            "achievements": [],
            "tech_stack": [],
        }
        if item["company"] or item["title"]:
            exps.append(item)
    return exps


def parse_resume_full(text: str) -> ResumeProfile:
    """正则 + LLM 合并解析：LLM 优先（更准确完整），正则兜底（无 key/失败时）。"""
    profile = parse_resume(text)
    llm = llm_parse_resume(text)
    if llm:
        if llm.get("name"):
            profile.name = str(llm["name"])
        if llm.get("email"):
            profile.email = str(llm["email"])
        if llm.get("phone"):
            profile.phone = str(llm["phone"])
        if llm.get("highest_degree"):
            profile.highest_degree = str(llm["highest_degree"])
        if llm.get("school"):
            profile.schools = [str(llm["school"])]
        if llm.get("major"):
            profile.majors = [str(llm["major"])]
        if llm.get("work_years"):
            # LLM 可能返回 "3" 或 "3年"，统一只保留数字
            wy = str(llm["work_years"]).strip().rstrip("年").strip()
            if wy.isdigit():
                profile.work_years = wy
        exps = llm.get("experiences")
        if isinstance(exps, list):
            profile.experiences = _normalize_experiences(exps)
        skills = llm.get("skills")
        if isinstance(skills, list):
            profile.skills = [str(s).strip() for s in skills if str(s).strip()]
    else:
        # 正则兜底：LLM 不可用时仍尽量粗提取工作/项目经历
        profile.experiences = _extract_experiences_regex(text)
    return profile


def ats_suggestions(profile: ResumeProfile, text: str, user_skills: list[str]) -> list[dict]:
    """ATS 视角的简历改进建议，返回 [{'level': 'critical'|'suggest', 'tip': str}]。"""
    tips = []

    # 1) 信息完整性（critical = 影响投递/联系）
    if not profile.email:
        tips.append({"level": "critical", "tip": "缺少邮箱：ATS 关联投递记录、HR 联系都依赖邮箱，建议在简历顶部补充"})
    if not profile.phone:
        tips.append({"level": "critical", "tip": "缺少手机号：HR 无法快速联系，建议补充"})
    if not profile.name:
        tips.append({"level": "critical", "tip": "未识别到姓名：建议在简历顶部写明姓名，方便 HR 定位与称呼"})
    if not profile.degrees:
        tips.append({"level": "suggest", "tip": "未识别到学历（本科/硕士等）：很多岗位学历是硬门槛，建议明确标注"})
    if not profile.schools:
        tips.append({"level": "suggest", "tip": "未识别到毕业院校：建议标注学校全称"})
    if not profile.work_years:
        tips.append({"level": "suggest", "tip": "未标注工作年限：建议明确写「N 年经验」，ATS 会按年限做初筛"})

    # 2) 经历完整性
    if not profile.experiences:
        tips.append({"level": "suggest",
                     "tip": "未识别到工作/项目经历：建议按「时间段 + 组织 + 角色 + 职责」清晰分段，ATS 与 HR 都看重经历结构化"})

    # 3) 成果量化（优先看经历里的 achievements，再看全文量化数字）
    has_quant_achievement = any(
        (e.get("achievements") if isinstance(e, dict) else None) for e in profile.experiences
    )
    if not has_quant_achievement and not re.search(r"\d+(\.\d+)?%|\d+\s*倍|\d+\s*万|\d+\s*人团队|\d+\s*个", text):
        tips.append({"level": "suggest",
                     "tip": "成果缺乏量化：建议用数字体现亮点（如「准确率提升 15%」「负责 5 人团队」），ATS 和 HR 更易识别"})

    # 4) 技能关键词密度
    if not user_skills:
        tips.append({"level": "suggest",
                     "tip": "未识别到 AI 相关技能关键词：建议把技能词（Python/PyTorch/大模型 等）显式写进简历，ATS 关键词匹配才能命中"})

    return tips
