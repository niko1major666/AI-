"""LLM 生成式报告解读 + 分阶段学习计划（DeepSeek，LLM 优先、模板兜底）。"""
from __future__ import annotations

import json
import os
import re

import requests

from src.matcher.gap_analyzer import GapReport

_DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
_DEEPSEEK_MODEL = "deepseek-chat"

_SYSTEM = "你是资深 AI 岗位求职导师，擅长为转行与非科班背景的求职者制定可落地的学习计划。"

# 专业 → 可迁移能力提示（按专业关键词匹配，通用规则，不预设具体某一种背景）
_MAJOR_HINT_RULES = [
    (("计算机", "软件", "人工智能", "数据科学", "大数据", "电子信息", "信息安全"),
     "专业与 AI 岗位直接相关，建议把课程/项目整理成作品集，重点补工程化、部署与业务落地能力"),
    (("数学", "统计", "应用数学", "物理"),
     "把数学与统计基础迁移到建模上：先用 Python 复现经典模型与评估流程，再补深度学习框架和工程实践"),
    (("自动化", "电子", "通信", "电气", "机械", "控制", "仪器"),
     "从信号处理、控制与设备数据分析切入：把已有的传感器/仿真数据处理经验改写成 Python 实现"),
    (("土木", "建筑", "交通", "水利", "测绘", "材料", "环境", "能源", "力学"),
     "把工程中的数值计算、实验数据分析与监测信号处理经验迁移到 AI：先做一个数据建模小项目验证迁移"),
    (("经济", "金融", "管理", "会计", "工商", "市场", "审计", "统计"),
     "从业务数据分析切入：用 Pandas 重做一次本专业的报表或建模作业，再补机器学习与可视化"),
    (("生物", "医学", "药学", "化学", "农业", "食品", "心理"),
     "从实验数据分析与图像识别切入：把本专业的实验数据用 Python 做一次完整分析并沉淀成项目"),
    (("新闻", "英语", "文学", "历史", "法学", "教育", "哲学", "社会", "传播", "外语"),
     "从文本处理与信息抽取切入：用 NLP 工具做一次本专业的语料分析，再补模型训练与评测"),
]


def _major_hint(majors) -> str:
    """根据简历解析出的专业名生成一条迁移建议；没有专业则返回空串（前端不展示）。"""
    major = next((str(m).strip() for m in (majors or []) if str(m).strip()), "")
    if not major:
        return ""
    for keys, hint in _MAJOR_HINT_RULES:
        if any(k in major for k in keys):
            return f"结合你在「{major}」专业的背景：{hint}。"
    return (f"结合你在「{major}」专业的背景：先梳理该专业中与数据处理、定量分析或编程相关的经历，"
            f"选一个小问题用 Python 做成可展示的项目，作为转入 AI 的切入点。")


_PROMPT = """根据下面的技能差距分析结果，输出一份「报告解读 + 分阶段学习计划」。

## 目标岗位
{job}

## 用户专业
{majors}

## 用户已有技能
{user_skills}

## 差距分析结果
- 匹配度：{match_score}%
- 已命中技能：{matched_total} 项
- 缺失技能：{missing_total} 项

缺失技能清单（按优先级排序）：
{missing_list}

## 输出要求
严格输出一个 JSON 对象，不要 markdown 代码块或解释：
{{
  "overview": "一段 80 字以内的整体解读，说明差距程度与主攻方向",
  "plan": [
    {{"phase": "阶段名（如 第1-2周）", "goal": "阶段目标", "skills": ["技能1", "技能2"], "actions": ["具体行动1", "具体行动2"]}}
  ],
  "tips": "一条额外建议：仅在「用户专业」不是（未提供）时，结合该专业给出可迁移的切入路径；否则输出空字符串"
}}

要求：
- 学习计划分 2~4 个阶段，由易到难；优先补齐 P0（硬门槛），再 P1（高频），后 P2（加分项）。
- 结合「行业重要度」和「学习难度」排序；如用户已有相关技能，可给出可迁移的切入路径。
- 「用户专业」为（未提供）时，不要假设或编造用户专业背景，tips 必须为空字符串。"""


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


def _missing_lines(report: GapReport) -> str:
    lines = []
    for m in report.missing[:15]:
        line = f"- {m.name}（{m.priority}，重要度 {m.importance}/5，难度 {m.difficulty}/4）：{m.why}"
        lines.append(line)
    return "\n".join(lines) or "（无）"


def _fallback(report: GapReport, job: str, majors: list[str] | None = None) -> dict:
    """无 key / 调用失败时的规则版解读与学习计划。"""
    overview = (
        f"你的技能与「{job}」的匹配度为 {report.match_score}%，"
        f"已覆盖 {report.matched_total} 项技能，仍有 {report.missing_total} 项需要补齐。"
    )
    groups = [
        ("P0", "第 1-2 周 · 攻克硬门槛", [m for m in report.missing if m.priority == "P0"]),
        ("P1", "第 3-4 周 · 补强高频技能", [m for m in report.missing if m.priority == "P1"]),
        ("P2", "第 5 周起 · 锦上添花", [m for m in report.missing if m.priority == "P2"]),
    ]
    plan = []
    for _prio, phase, items in groups:
        if not items:
            continue
        skills = [m.name for m in items]
        actions = []
        for m in items[:3]:
            act = f"学习 {m.name}"
            if m.resources:
                act += f"（参考 {m.resources[0].get('title', '')}）"
            actions.append(act)
        plan.append({
            "phase": phase,
            "goal": f"掌握 {len(items)} 项技能",
            "skills": skills,
            "actions": actions,
        })
    tips = _major_hint(majors)
    return {"overview": overview, "plan": plan, "tips": tips}


def interpret_report(report: GapReport, target_job: str = "",
                     user_skills: list[str] | None = None,
                     user_majors: list[str] | None = None) -> dict:
    """生成「报告解读 + 学习计划」。LLM 优先，无 key / 失败返回规则兜底。

    user_majors 来自「简历匹配」页解析出的专业名；为空时不给专业迁移建议。
    """
    job = target_job or "目标岗位"
    majors = [str(m).strip() for m in (user_majors or []) if str(m).strip()]
    api_key = _get_api_key()
    if not api_key:
        return _fallback(report, job, majors)

    prompt = _PROMPT.format(
        job=job,
        majors="、".join(majors) if majors else "（未提供）",
        user_skills="、".join(user_skills) if user_skills else "（未提供）",
        match_score=report.match_score,
        matched_total=report.matched_total,
        missing_total=report.missing_total,
        missing_list=_missing_lines(report),
    )
    try:
        resp = requests.post(
            _DEEPSEEK_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": _DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.4,
                "max_tokens": 2000,
            },
            timeout=90,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.M)
        data = json.loads(content)
        return {
            "overview": str(data.get("overview", "")),
            "plan": data.get("plan", []) or [],
            "tips": str(data.get("tips", "")),
        }
    except Exception:  # noqa: BLE001
        return _fallback(report, job, majors)
