"""技能画像：按技能类别计算「需求加权覆盖率」，找出优势类别与短板类别。"""
from __future__ import annotations

# 极低频技能（需求占比 0 或缺失）仍计入分母，避免「类别里只有冷门技能 → 覆盖率虚高」
_FLOOR_WEIGHT = 0.001


def _weight(demand: dict, skill_id: str) -> float:
    return max(float((demand or {}).get(skill_id, 0.0) or 0.0), _FLOOR_WEIGHT)


def category_profile(user_skill_ids, taxonomy, demand=None, *,
                     top_missing: int = 2) -> list[dict]:
    """每个技能类别的覆盖情况。

    返回（按词表类别顺序）：
    [{'category','name','coverage','owned','total','top_missing':[技能名]}]

    coverage = 已掌握技能的需求权重之和 / 该类别全部技能需求权重之和。
    """
    owned = {str(s) for s in (user_skill_ids or [])}
    buckets: dict[str, dict] = {}
    for sk in taxonomy.all_skills():
        w = _weight(demand, sk.id)
        b = buckets.setdefault(sk.category, {
            "category": sk.category, "name": sk.category_name,
            "owned_w": 0.0, "total_w": 0.0, "owned": 0, "total": 0, "missing": [],
        })
        b["total_w"] += w
        b["total"] += 1
        if sk.id in owned:
            b["owned_w"] += w
            b["owned"] += 1
        else:
            b["missing"].append((w, sk.name))

    out = []
    for cat_id, _cat_name in getattr(taxonomy, "categories", []):
        b = buckets.get(cat_id)
        if not b:
            continue
        coverage = b["owned_w"] / b["total_w"] if b["total_w"] else 0.0
        missing = [name for _w, name in
                   sorted(b["missing"], key=lambda x: -x[0])[:max(0, top_missing)]]
        out.append({
            "category": b["category"],
            "name": b["name"],
            "coverage": round(coverage, 4),
            "owned": b["owned"],
            "total": b["total"],
            "top_missing": missing,
        })
    return out


def overall_coverage(user_skill_ids, taxonomy, demand=None) -> float:
    """全词表的需求加权覆盖率（0~1）。"""
    owned = {str(s) for s in (user_skill_ids or [])}
    total_w = got_w = 0.0
    for sk in taxonomy.all_skills():
        w = _weight(demand, sk.id)
        total_w += w
        if sk.id in owned:
            got_w += w
    return round(got_w / total_w, 4) if total_w else 0.0


def weakest_categories(profile: list[dict], *, limit: int = 3) -> list[dict]:
    """覆盖率最低、且该类别至少掌握 0 项的类别（短板）。"""
    return sorted(profile, key=lambda x: (x["coverage"], -x["total"]))[:limit]
