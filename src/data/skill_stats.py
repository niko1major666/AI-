"""技能需求统计：Top 技能、公司 × 技能需求矩阵（供图谱页热力图使用）。"""
from __future__ import annotations

from collections import Counter


def demand_by_skill(rows) -> dict:
    """全语料技能需求占比：{skill_id: 0~1}。分母是所有 JD（含零技能岗位）。"""
    total = len(rows or [])
    if not total:
        return {}
    cnt = Counter()
    for r in rows:
        cnt.update(set(r.get("skills") or []))
    return {sid: c / total for sid, c in cnt.items()}


def top_skill_ids(rows, top_n: int = 15) -> list[str]:
    """按需求占比排序的 Top N 技能 id（同占比按 id 稳定排序）。"""
    demand = demand_by_skill(rows)
    return [sid for sid, _ in sorted(demand.items(), key=lambda x: (-x[1], x[0]))[:max(0, top_n)]]


def demand_matrix(rows, top_n: int = 15) -> dict:
    """公司 × Top 技能需求矩阵。

    返回 {'skills': [skill_id], 'companies': [...], 'values': [[占比]]}，
    values 与 companies/skills 对齐；占比按「该公司 JD 数」为分母。
    公司按 JD 数降序（同数量按名称升序）：1~2 条 JD 的公司容易出现 0% / 100%
    的极端值，排在后面可避免干扰读者对「行业趋势」的判断。
    """
    rows = list(rows or [])
    skills = top_skill_ids(rows, top_n)
    by_company: dict[str, list] = {}
    for r in rows:
        by_company.setdefault(str(r.get("company") or ""), []).append(r)

    companies = sorted(by_company, key=lambda c: (-len(by_company[c]), c))
    values = []
    for c in companies:
        group = by_company[c]
        n = len(group) or 1
        cnt = Counter()
        for r in group:
            cnt.update(set(r.get("skills") or []))
        values.append([round(cnt.get(sid, 0) / n, 4) for sid in skills])
    return {"skills": skills, "companies": companies, "values": values}
