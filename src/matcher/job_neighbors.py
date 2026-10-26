"""零技能岗位的技能代理：用同公司相似岗位的技能集合推断要求。

背景（实测）：5163 条 JD 中 1212 条（23.5%）抽不到任何技能（快手 32.5% / 小红书 37.4%
等列表式短 JD），此时直接生成报告会得到「匹配度 0% + 已覆盖目标岗位的全部技能」这种
自相矛盾的结论。这里用「同公司 + 标题相近」的邻居岗位技能并集做代理，并在页面上明确
标注来源，避免把推断结果伪装成该 JD 的原始要求。实测 98.0% 的零技能岗位（1188/1212）
可用代理补齐。
"""
from __future__ import annotations

import difflib
from collections import Counter


def title_similarity(a: str, b: str) -> float:
    """标题相似度（字符级，对中文无需分词）。"""
    return difflib.SequenceMatcher(None, str(a or ""), str(b or "")).ratio()


def proxy_skills(rows, target, k: int = 5, top_n: int = 20,
                 min_similarity: float = 0.34) -> tuple[list[str], list[str]]:
    """用邻居岗位的技能推断目标岗位要求。

    rows: 全量岗位行 [{'job_id','title','company','skills'}]。
    target: 目标岗位行（其 skills 为空）。
    返回 (skill_ids, source_titles)：技能按被邻居提及次数降序；无可用邻居时返回 ([], [])。
    """
    job_id = target.get("job_id")
    company = target.get("company")
    title = target.get("title") or ""
    cands = [
        r for r in rows
        if r.get("job_id") != job_id
        and r.get("company") == company
        and r.get("skills")
    ]
    if not cands:
        return [], []

    scored = sorted(cands, key=lambda r: -title_similarity(title, r.get("title") or ""))
    picked = [r for r in scored
              if title_similarity(title, r.get("title") or "") >= min_similarity][:k]
    if not picked:                      # 标题差异大时退化为「同公司最近 k 个岗位」
        picked = scored[:k]

    counter: Counter = Counter()
    for r in picked:
        for sid in set(r["skills"]):
            counter[sid] += 1
    need = 2 if len(picked) >= 3 else 1  # 邻居足够多时要求至少 2 个邻居都提到
    ids = [sid for sid, c in counter.most_common(top_n) if c >= need]
    return ids, [str(r.get("title") or "") for r in picked]
