"""简历补强建议：针对缺失技能，判断简历里是否已有可复用的相关经历。

原则：**不编造经历**。只在简历原文里已有相关关键词时给出「改写要点」，
否则给出「补一个小项目」的具体建议，所有数字都用占位符（XXX / X%）。
"""
from __future__ import annotations

import re

_CATEGORY_IDEA = {
    "编程语言": "用这门语言重写一个已有练手项目，突出性能/可维护性改进",
    "深度学习框架": "用该框架复现一个公开 baseline（如 CIFAR-10 分类），记录训练曲线与调参过程",
    "机器学习算法": "在公开数据集上做一个端到端实验：对比 2 个基线 + 你的改进，报告指标",
    "AI专有技术": "做一个最小可运行 demo（输入 → 输出可演示），并压测/评估效果",
    "大数据与数据处理": "搭一条小型数据管道（采集 → 清洗 → 入库 → 查询），说明数据量与耗时",
    "工程工具与平台": "把已有项目容器化/自动化部署，记录部署前后耗时与稳定性差异",
}

_ACTION_VERBS = ("负责", "参与", "搭建", "实现", "优化", "设计", "复现", "部署")


def _norm_text(text: str) -> str:
    """去空白 + 小写，便于中文子串匹配（简历里常有「机 器 学 习」这类排版空格）。"""
    return re.sub(r"\s+", "", str(text or "")).lower()


def skill_tokens(skill) -> list[str]:
    """技能的可匹配写法（名称 + 别名 + skip_extract），用于判断简历是否提到过。"""
    if skill is None:
        return []
    raw = [skill.name] + list(skill.aliases or []) + list(skill.skip_extract or [])
    out, seen = [], set()
    for t in raw:
        k = _norm_text(t)
        if len(k) >= 2 and k not in seen:
            seen.add(k)
            out.append(str(t).strip())
    return out


def find_evidence(skill, resume_text: str) -> list[str]:
    """简历原文里出现的技能写法（按原文顺序去重）。"""
    text = _norm_text(resume_text)
    if not text:
        return []
    hits = [t for t in skill_tokens(skill) if _norm_text(t) in text]
    return hits


def build_advice(gaps, taxonomy, resume_text: str, *, limit: int = 5) -> list[dict]:
    """为缺失技能生成补强建议（按 gaps 原有优先级顺序，最多 limit 条）。

    返回 [{'skill_id','name','priority','status','evidence','suggestion','project_idea'}]
    status: '已有相关经历' | '需补充项目'
    """
    out = []
    for g in list(gaps or [])[:max(0, limit)]:
        sid = getattr(g, "skill_id", "")
        name = getattr(g, "name", sid) or sid
        sk = taxonomy.by_id(sid) if taxonomy is not None else None
        evidence = find_evidence(sk, resume_text)
        if evidence:
            status = "已有相关经历"
            suggestion = (
                f"简历里已出现「{evidence[0]}」，但缺少可验证的成果表达。"
                f"建议改写成：用 {name} {_ACTION_VERBS[3]} XXX 功能，"
                f"使 X 指标从 A 提升到 B（如准确率 +X%、耗时 -X%）。"
            )
        else:
            status = "需补充项目"
            suggestion = (
                f"简历里没有与「{name}」相关的经历。建议先补一个最小项目，"
                f"再用「{_ACTION_VERBS[2]} + {name} + 量化结果」的句式写进简历。"
            )
        resources = list(getattr(g, "resources", []) or [])
        project_idea = ""
        if resources:
            first = resources[0] or {}
            title = str(first.get("title") or "").strip()
            if title:
                project_idea = f"按《{title}》入门，做一个可演示的小项目（输入/输出明确，附指标对比）"
        if not project_idea:
            cat = getattr(sk, "category_name", "") if sk is not None else ""
            project_idea = _CATEGORY_IDEA.get(cat, "做一个最小可运行 demo，并记录效果指标")
        out.append({
            "skill_id": sid,
            "name": name,
            "priority": getattr(g, "priority", "P2"),
            "status": status,
            "evidence": evidence,
            "suggestion": suggestion,
            "project_idea": project_idea,
        })
    return out
