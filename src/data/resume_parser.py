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
YEARS_RE = re.compile(r"(\d{1,2})\s*年(?:以上|及|工作经验|相关经验|经验)?")

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

    def to_dict(self) -> dict:
        return asdict(self)


def parse_resume(text: str) -> ResumeProfile:
    email = EMAIL_RE.search(text)
    phone = PHONE_RE.search(text)
    degrees = list(dict.fromkeys(DEGREE_RE.findall(text)))
    highest = ""
    if degrees:
        highest = max(degrees, key=lambda d: _DEGREE_RANK.get(d, 0))
    schools = list(dict.fromkeys(SCHOOL_RE.findall(text)))
    majors = list(dict.fromkeys(MAJOR_RE.findall(text)))
    ym = YEARS_RE.search(text)
    return ResumeProfile(
        email=email.group(0) if email else "",
        phone=phone.group(0) if phone else "",
        degrees=degrees,
        highest_degree=highest,
        schools=schools,
        majors=majors,
        work_years=ym.group(1) if ym else "",
    )


_DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
_DEEPSEEK_MODEL = "deepseek-chat"

_LLM_PROMPT = """你是专业的简历解析助手。从下面的简历文本提取结构化信息，严格输出一个 JSON 对象。

字段（没有就填空值）：
- name: 姓名（字符串）
- email: 邮箱（字符串）
- phone: 手机号（字符串）
- highest_degree: 最高学历（博士/硕士/本科/大专/其他 之一）
- school: 毕业院校（字符串）
- major: 所学专业（字符串）
- work_years: 工作年限数字（整数，没有则 0）
- experiences: 工作/项目经历数组，每项含 company(组织)、title(角色)、duration(时间段)
- skills: 技能字符串数组

简历文本：
{text}

只输出 JSON 对象，不要 markdown 代码块或解释。"""


def llm_parse_resume(text: str) -> dict | None:
    """用 DeepSeek LLM 增强解析（姓名/工作经历等正则难做的字段）。无 key/失败返回 None。"""
    api_key = os.environ.get("DEEPSEEK_API_KEY")
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


def parse_resume_full(text: str) -> ResumeProfile:
    """正则 + LLM 合并解析：正则保证基础字段，LLM 补充姓名/工作经历等。"""
    profile = parse_resume(text)
    llm = llm_parse_resume(text)
    if llm:
        if not profile.name and llm.get("name"):
            profile.name = str(llm["name"])
        if not profile.highest_degree and llm.get("highest_degree"):
            profile.highest_degree = str(llm["highest_degree"])
        if not profile.schools and llm.get("school"):
            profile.schools = [str(llm["school"])]
        if not profile.majors and llm.get("major"):
            profile.majors = [str(llm["major"])]
        if not profile.work_years and llm.get("work_years"):
            profile.work_years = str(llm["work_years"])
        exps = llm.get("experiences")
        if isinstance(exps, list):
            profile.experiences = exps
        if not profile.email and llm.get("email"):
            profile.email = str(llm["email"])
        if not profile.phone and llm.get("phone"):
            profile.phone = str(llm["phone"])
    return profile


def ats_suggestions(profile: ResumeProfile, text: str, user_skills: list[str]) -> list[dict]:
    """ATS 视角的简历改进建议，返回 [{'level': 'critical'|'suggest', 'tip': str}]。"""
    tips = []

    # 1) 信息完整性（critical = 影响投递/联系）
    if not profile.email:
        tips.append({"level": "critical", "tip": "缺少邮箱：ATS 关联投递记录、HR 联系都依赖邮箱，建议在简历顶部补充"})
    if not profile.phone:
        tips.append({"level": "critical", "tip": "缺少手机号：HR 无法快速联系，建议补充"})
    if not profile.degrees:
        tips.append({"level": "suggest", "tip": "未识别到学历（本科/硕士等）：很多岗位学历是硬门槛，建议明确标注"})
    if not profile.schools:
        tips.append({"level": "suggest", "tip": "未识别到毕业院校：建议标注学校全称"})
    if not profile.work_years:
        tips.append({"level": "suggest", "tip": "未标注工作年限：建议明确写「N 年经验」，ATS 会按年限做初筛"})

    # 2) 成果量化
    if not re.search(r"\d+(\.\d+)?%|\d+\s*倍|\d+\s*万|\d+\s*人团队|\d+\s*个", text):
        tips.append({"level": "suggest",
                     "tip": "成果缺乏量化：建议用数字体现亮点（如「准确率提升 15%」「负责 5 人团队」），ATS 和 HR 更易识别"})

    # 3) 技能关键词密度
    if not user_skills:
        tips.append({"level": "suggest",
                     "tip": "未识别到 AI 相关技能关键词：建议把技能词（Python/PyTorch/大模型 等）显式写进简历，ATS 关键词匹配才能命中"})

    return tips
