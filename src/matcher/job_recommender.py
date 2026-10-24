"""反向岗位推荐：给定简历技能，从全语料里找出匹配度最高的岗位。

与「选岗位 → 出差距报告」相反：这里先用简历扫全语料，回答「我更适合投哪些岗」。
按（公司 + 标题）去重，避免同一岗位的多条渠道重复占榜；只用已抽到技能的岗位。
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field


@dataclass
class JobSuggestion:
    company: str
    title: str
    location: str
    match_score: float
    matched_total: int
    missing_total: int
    top_missing: list = field(default_factory=list)


def _norm_title(title: str) -> str:
    """标题归一化（用于去重）：去空白/标点，小写。"""
    return re.sub(r"[\s\-_/·,，、（）()【】\[\]]+", "", str(title or "")).lower()


def _skill_weight(analyzer, is_must: bool, tf) -> float:
    base = analyzer.must_weight if is_must else analyzer.nice_weight
    try:
        tf = float(tf or 1)
    except (TypeError, ValueError):
        tf = 1.0
    return base * (1.0 + math.log(max(tf, 1.0)))


def recommend_jobs(user_skills, rows, analyzer, *, top_k: int = 10,
                   min_score: float = 1.0) -> list[JobSuggestion]:
    """返回匹配度最高的 top_k 个岗位（去重后）。

    min_score: 匹配度阈值（百分比），用于过滤「几乎不匹配」的岗位。
    """
    matched = set(analyzer.match_user_skills(list(user_skills or [])))
    if not matched:
        return []

    # 去重：同一 (公司, 归一化标题) 只保留技能数最多的一条
    best: dict[tuple, dict] = {}
    for r in rows or []:
        skills = set(r.get("skills") or [])
        if not skills:
            continue
        key = (str(r.get("company") or ""), _norm_title(r.get("title")))
        cur = best.get(key)
        if cur is None or len(skills) > len(cur.get("skills") or []):
            best[key] = r

    out = []
    for r in best.values():
        skills = sorted(set(r.get("skills") or []))
        must_ids = set(r.get("must_skills") or [])
        tf_map = r.get("skill_tf") or {}
        total_w = got_w = 0.0
        missing = []
        for sid in skills:
            w = _skill_weight(analyzer, sid in must_ids, tf_map.get(sid, 1))
            total_w += w
            if sid in matched:
                got_w += w
            else:
                missing.append((w, sid))
        if not total_w:
            continue
        score = round(got_w / total_w * 100, 1)
        if score < min_score:
            continue
        missing.sort(key=lambda x: -x[0])
        out.append(JobSuggestion(
            company=str(r.get("company") or ""),
            title=str(r.get("title") or ""),
            location=str(r.get("location") or ""),
            match_score=score,
            matched_total=len(matched & set(skills)),
            missing_total=len(missing),
            top_missing=[analyzer.taxonomy.by_id(sid).name
                         if analyzer.taxonomy.by_id(sid) else sid
                         for _w, sid in missing[:3]],
        ))

    out.sort(key=lambda j: (-j.match_score, j.missing_total, j.company, j.title))
    return out[:max(0, top_k)]
