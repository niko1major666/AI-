"""岗位相关性判定：这条 JD 是否属于「AI / 软件技术研发」目标范围。

两层判定：
1. `job_family.classify_title`（中文标题：技术标记 / 职能词 / 未知）
2. 未知桶（多为英文标题）用英文规则判定，**顺序敏感**：
   先看「角色类型词」与「非软件域」，再看技术词。否则 `AI Operations Lead`
   会因为含 "AI" 被误判成技术岗，`Tech Lead, Autonomy Systems` 会因为 "lead" 被误杀。

规则经过抽样验证：用千问（qwen3.8-flash）对 300 条未知岗位做独立判定，
规则与 LLM 在 131 条"keep/drop 明确"的样本上**一致率 100%**
（见 `docs/source-triage-v1.7.md` 与 release notes v1.10.0）。
"""
from __future__ import annotations

import re

from .job_family import classify_title

# 强技术信号：出现即视为技术岗，即使标题里也有职能词
_STRONG_TECH = re.compile(
    r"software|backend|frontend|machine learning|data engineer|data scien|algorithm|"
    r"devops|\bsre\b|platform engineer|security engineer|embedded|firmware|"
    r"\bai engineer|technology engineer", re.I)
# 角色类型词：出现即判非目标（运营 / 产品 / 销售 / 职能）
_ROLE_DROP = re.compile(
    r"product manager|program manager|project manager|\bpm\b|operations|marketing|sales|"
    r"recruit|finance|financial|legal|\bhr\b|human resources|admin|designer|content|"
    r"editor|brand|consult|account manager|specialist|coordinator|assistant|\bgtm\b|"
    r"business development|partnership|customer success|supply chain|procurement", re.I)
# 非软件域：生物 / 电池 / 电子 / 机械 / 材料 / 光学 / 射频 / 制造
_DOMAIN_DROP = re.compile(
    r"biomechanic|bioengineer|biomedical|molecular|protein|batter|electronic|mechanic|"
    r"chemical|material|optic|\brf\b|antenna|thermal|hardware|structural|civil|"
    r"technician|fabrication|manufactur", re.I)
_TECH = re.compile(
    r"software|backend|frontend|full.?stack|machine learning|\bml\b|\bai\b|algorithm|"
    r"data engineer|data scien|data platform|analytics engineer|devops|\bsre\b|"
    r"android|\bios\b|cloud|database|\bdba\b|platform engineer|infra|security|"
    r"architecture|compiler|embedded|firmware|autonomy|robotics|systems engineer|"
    r"engineer|developer|scientist|architect|programmer|researcher|analyst|\bqa\b", re.I)


def decide(title) -> str:
    """返回 `target`（保留）/ `non_target`（剔除）/ `uncertain`（需人工看）。"""
    kind = classify_title(title)
    if kind == "tech":
        return "target"
    if kind == "non_tech":
        return "non_target"

    text = str(title or "").strip()
    if not text:
        return "uncertain"
    if _STRONG_TECH.search(text):
        return "target"
    if _ROLE_DROP.search(text) or _DOMAIN_DROP.search(text):
        return "non_target"
    if _TECH.search(text):
        return "target"
    return "uncertain"


def is_target(title) -> bool:
    """未知桶一律按"保留"处理——宁可留下噪音，也不误删真实技术岗。"""
    return decide(title) != "non_target"
