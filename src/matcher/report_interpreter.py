"""LLM 生成式报告解读 + 分阶段学习计划（DeepSeek，LLM 优先、模板兜底）。"""
from __future__ import annotations

import json
import os
import re

import requests

from src.matcher.gap_analyzer import GapReport

_DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
_DEEPSEEK_MODEL = "deepseek-chat"

_SYSTEM = "你是资深 AI 岗位求职导师，擅长为非科班转行者（尤其传统工科背景）制定可落地的学习计划。"

_PROMPT = """根据下面的技能差距分析结果，输出一份「报告解读 + 分阶段学习计划」。

## 目标岗位
{job}

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
  "tips": "一条额外建议（结合道桥工程背景的迁移优势，可空）"
}}

要求：
- 学习计划分 2~4 个阶段，由易到难；优先补齐 P0（硬门槛），再 P1（高频），后 P2（加分项）。
- 结合「行业重要度」和「学习难度」排序；充分利用用户已有的道桥工程背景做迁移。"""


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
        if m.transfer_hint:
            line += f"；道桥迁移：{m.transfer_hint}"
        lines.append(line)
    return "\n".join(lines) or "（无）"


def _fallback(report: GapReport, job: str) -> dict:
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
            if m.transfer_hint:
                act += f"，结合道桥背景：{m.transfer_hint}"
            actions.append(act)
        plan.append({
            "phase": phase,
            "goal": f"掌握 {len(items)} 项技能",
            "skills": skills,
            "actions": actions,
        })
    tips = "建议优先从与道桥工程最接近的领域（数值计算、数据分析、信号处理）切入，降低转行门槛。"
    return {"overview": overview, "plan": plan, "tips": tips}


def interpret_report(report: GapReport, target_job: str = "",
                     user_skills: list[str] | None = None) -> dict:
    """生成「报告解读 + 学习计划」。LLM 优先，无 key / 失败返回规则兜底。"""
    job = target_job or "目标岗位"
    api_key = _get_api_key()
    if not api_key:
        return _fallback(report, job)

    prompt = _PROMPT.format(
        job=job,
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
        return _fallback(report, job)
