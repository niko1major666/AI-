"""简历结构化解析（中文简历启发式规则 + DeepSeek LLM 增强）+ ATS 视角改进建议。

经历按 `kind` 区分工作 / 实习 / 项目：LLM 优先给出类型，正则兜底用
「章节标题 → 组织/角色关键词」推断，便于区分「工作经历」与「项目经历」。
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field

import requests

from .privacy import LLM_RESUME_CHARS, mask_pii

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
DEGREE_RE = re.compile(r"(博士|硕士|研究生|本科|学士|大专|专科)")
SCHOOL_RE = re.compile(r"[\u4e00-\u9fa5]{2,20}(?:大学|学院)")
MAJOR_RE = re.compile(
    r"(计算机科学与技术|软件工程|人工智能|数据科学|大数据|电子信息|通信工程|机械工程|"
    r"土木工程|数学与应用数学|应用数学|统计学|自动化|电子工程)"
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

# ---- 经历类型（工作 / 实习 / 项目）----
EXPERIENCE_KINDS = ("work", "internship", "project", "other")
EXPERIENCE_KIND_LABELS = {"work": "工作", "internship": "实习", "project": "项目", "other": "其他"}
_KIND_ALIASES = {
    "work": "work", "工作": "work", "全职": "work", "正式": "work", "在职": "work",
    "internship": "internship", "intern": "internship", "实习": "internship",
    "project": "project", "项目": "project", "科研": "project", "研究": "project",
    "other": "other", "其他": "other",
}
# 章节标题 → 经历类型（教育经历不作为工作/项目，value 用 None 表示跳过）
_SECTION_HEADING_RE = re.compile(
    r"(实习经历|实习经验|工作经历|工作经验|职业经历|项目经历|项目经验|科研经历|科研项目|"
    r"研究经历|研究项目|实践经历|校园经历|教育经历|教育背景)"
)
_SECTION_KIND = {
    "实习经历": "internship", "实习经验": "internship",
    "工作经历": "work", "工作经验": "work", "职业经历": "work",
    "项目经历": "project", "项目经验": "project", "科研经历": "project",
    "科研项目": "project", "研究经历": "project", "研究项目": "project",
    "实践经历": "project", "校园经历": "project",
    "教育经历": None, "教育背景": None,
}
_INTERN_TITLE_RE = re.compile(r"(实习|intern)", re.I)
_PROJECT_TITLE_RE = re.compile(r"(项目|科研|课题|竞赛|比赛)")
_MANAGER_TITLE_RE = re.compile(r"(经理|总监|主管)")
_WORK_TITLE_RE = re.compile(r"(工程师|架构师|科学家|经理|总监|专员|主管|分析师|顾问|讲师|教师)")
_WORK_ORG_RE = re.compile(r"(公司|集团|有限公司|事务所|银行|医院)")
_PROJECT_ORG_RE = re.compile(r"(实验室|大学|学院|研究院|研究所|研究中心|课题组|工作室)")


def _infer_experience_kind(item: dict) -> str:
    """按角色/组织关键词推断经历类型（LLM 缺字段或纯正则兜底时用）。"""
    title = str(item.get("title") or "")
    company = str(item.get("company") or "")
    if _INTERN_TITLE_RE.search(title):
        return "internship"
    if _PROJECT_TITLE_RE.search(title) and not _MANAGER_TITLE_RE.search(title):
        return "project"
    if _WORK_TITLE_RE.search(title):
        return "work"
    if _WORK_ORG_RE.search(company):
        return "work"
    if _PROJECT_ORG_RE.search(company):
        return "project"
    return "other"


def _normalize_experience_kind(value, item: dict | None = None) -> str:
    """把 LLM / 旧数据里的类型写法归一；缺省时按角色/组织推断。"""
    raw = str(value or "").strip().lower()
    if raw in _KIND_ALIASES:
        return _KIND_ALIASES[raw]
    for key, kind in _KIND_ALIASES.items():
        if key and key in raw:
            return kind
    return _infer_experience_kind(item or {})


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

    @property
    def work_experiences(self) -> list:
        """工作 + 实习经历（实习归入「工作侧」，页面用 kind 标签区分）。"""
        return [e for e in self.experiences if isinstance(e, dict)
                and _normalize_experience_kind(e.get("kind"), e) in ("work", "internship")]

    @property
    def project_experiences(self) -> list:
        return [e for e in self.experiences if isinstance(e, dict)
                and _normalize_experience_kind(e.get("kind"), e) == "project"]

    @property
    def other_experiences(self) -> list:
        """未分类经历（LLM/正则都没给出类型且关键词也推断不出）。"""
        return [e for e in self.experiences if isinstance(e, dict)
                and _normalize_experience_kind(e.get("kind"), e) == "other"]


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
- highest_degree: 最高学历（博士/硕士/本科/大专/其他 之一）
- school: 毕业院校（字符串）
- major: 所学专业（字符串）
- work_years: 工作年限数字（整数，没有则 0；只填数字，不要带「年」字）
- experiences: 工作/实习/项目经历数组，每项含：
    kind(类型：work=全职工作、internship=实习、project=项目或科研、other=其他)、
    company(组织名称)、title(角色/职位)、duration(时间段，如「2023.06-至今」)、
    description(一句话职责概述，30 字以内)、achievements(量化成果字符串数组)、
    tech_stack(用到的技术栈字符串数组)
    （同一段经历只出现一次；不要把教育经历写进 experiences）
- skills: 技能字符串数组（编程语言/框架/算法/工具，尽量用标准名称）

注意：邮箱、手机号、身份证号、银行卡号、微信/QQ、详细住址已替换为「[xx已隐藏]」，
不要猜测或补全这些内容，也不要输出 email / phone 字段。

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


def has_llm_api_key() -> bool:
    """是否配置了可用的 DeepSeek key（页面用于展示 AI 增强是否真正可用）。"""
    return bool(_get_api_key())


def llm_parse_resume(text: str) -> dict | None:
    """用 DeepSeek LLM 增强解析（姓名/工作经历等正则难做的字段）。无 key/失败返回 None。

    隐私边界：发送前强制用 `mask_pii` 替换直接联系方式，并只截取前
    `LLM_RESUME_CHARS` 字。超时从 90s 收紧到 25s 并重试一次：原值在网络抖动时
    会把页面卡住一分半，而解析失败已有正则兜底，宁可快速降级。
    """
    api_key = _get_api_key()
    if not api_key:
        return None
    safe_text = mask_pii(text).text[:LLM_RESUME_CHARS]
    payload = {
        "model": _DEEPSEEK_MODEL,
        "messages": [{"role": "user", "content": _LLM_PROMPT.format(text=safe_text)}],
        "response_format": {"type": "json_object"},
        "temperature": 0,
        "max_tokens": 1500,
    }
    for attempt in range(2):
        try:
            resp = requests.post(
                _DEEPSEEK_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=25,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.M)
            return json.loads(content)
        except Exception:  # noqa: BLE001
            if attempt == 0:
                time.sleep(0.6)
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
        item["kind"] = _normalize_experience_kind(e.get("kind"), item)
        # 只要有一个非空字段就保留（kind 一定有值，不能参与判空）
        if any(item.get(k) for k in ("company", "title", "duration", "description",
                                     "achievements", "tech_stack")):
            out.append(item)
    return out


def _section_kind_at(text: str, pos: int) -> tuple[bool, str | None]:
    """返回 (是否找到章节标题, 章节类型)。

    章节类型为 None 表示该段属于「教育经历」等非工作/项目章节，调用方应跳过。
    """
    found = False
    kind = None
    for m in _SECTION_HEADING_RE.finditer(text, 0, pos):
        found = True
        kind = _SECTION_KIND.get(m.group(1))
    return found, kind


def _extract_experiences_regex(text: str) -> list:
    """无 LLM 时按时间段粗切经历，并按章节标题/关键词标注工作、实习或项目。"""
    spans = list(TIME_RANGE_RE.finditer(text))
    if not spans:
        return []
    exps = []
    for i, m in enumerate(spans):
        # 教育经历里的时间范围（2019.09-2023.06 某大学）不算工作/项目经历
        found, section_kind = _section_kind_at(text, m.start())
        if found and section_kind is None:
            continue
        end = spans[i + 1].start() if i + 1 < len(spans) else len(text)
        seg = text[m.start():end]
        comp = COMPANY_RE.search(seg)
        title = TITLE_RE.search(seg)
        item = {
            "kind": "",
            "company": comp.group(0) if comp else "",
            "title": title.group(0) if title else "",
            "duration": m.group(0),
            "description": "",
            "achievements": [],
            "tech_stack": [],
        }
        item["kind"] = section_kind or _infer_experience_kind(item)
        if item["company"] or item["title"]:
            exps.append(item)
    return exps


def parse_resume_full(text: str, *, allow_llm: bool = True) -> ResumeProfile:
    """正则 + LLM 合并解析：LLM 优先（更准确完整），正则兜底（无 key/失败时）。

    allow_llm=False 用于用户未授权外发简历的场景：完全不调用 LLM，只跑本地正则。
    联系方式（email / phone）只认本地正则结果，**不接受 LLM 返回值**——LLM 收到的
    文本已经脱敏，返回联系方式只可能是猜测。
    """
    profile = parse_resume(text)
    llm = llm_parse_resume(text) if allow_llm else None
    if llm:
        name = str(llm.get("name") or "").strip()
        if name and "已隐藏" not in name and not profile.name:
            profile.name = name
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

    # 2) 经历完整性（工作/实习 vs 项目分开看：非科班/应届更依赖项目经历）
    if not profile.experiences:
        tips.append({"level": "suggest",
                     "tip": "未识别到工作/项目经历：建议按「时间段 + 组织 + 角色 + 职责」清晰分段，ATS 与 HR 都看重经历结构化"})
    else:
        # 类型未识别（全是 other）时不做工作/项目二选一的判断，避免重复打扰
        has_work = bool(profile.work_experiences)
        has_project = bool(profile.project_experiences)
        if has_work or has_project:
            if not has_work:
                tips.append({"level": "suggest",
                             "tip": "未识别到工作/实习经历：建议补充实习、开源贡献或竞赛等能证明工程能力的经历"})
            if not has_project:
                tips.append({"level": "suggest",
                             "tip": "未识别到项目经历：建议至少写 1~2 个项目（问题背景 → 你的方案 → 技术栈 → 量化结果），这是非科班/应届最有力的能力证明"})

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
