"""岗位收藏（求职短名单）：纯函数实现去重、上限与 URL 编解码。

Streamlit Community Cloud 没有持久化后端，因此收藏只把 `job_id` 列表写进
页面链接参数 `?fav=id1,id2`：刷新页面、收藏链接、分享给同学都不会丢；
换设备或清空链接会丢（导出 JSON 可备份）。收藏项按「公司 + 归一化标题」
去重，同一岗位的多渠道重复不会占两个位置。
"""
from __future__ import annotations

import re

FAVORITE_LIMIT = 20


def _norm_title(title: str) -> str:
    """标题归一化（去空白/标点，小写）：与 job_recommender 的去重口径一致。"""
    return re.sub(r"[\s\-_/·,，、（）()【】\[\]]+", "", str(title or "")).lower()


def job_key(job: dict) -> str:
    """收藏去重键：公司（原文）+ 归一化标题。"""
    company = str(job.get("company") or "").strip()
    return f"{company}|{_norm_title(job.get('title'))}"


def make_favorite(job: dict) -> dict:
    """从岗位记录里取出收藏所需字段（只留可序列化、可展示的字段）。"""
    return {
        "job_id": str(job.get("job_id") or "").strip(),
        "company": str(job.get("company") or "").strip(),
        "title": str(job.get("title") or "").strip(),
        "location": str(job.get("location") or "").strip(),
    }


def is_favorited(favorites, job: dict) -> bool:
    key = job_key(job)
    return any(isinstance(f, dict) and job_key(f) == key for f in favorites or [])


def toggle_favorite(favorites, job: dict) -> tuple[list, str]:
    """收藏/取消收藏。返回 (新列表, 动作)，动作为 added / removed / full。"""
    current = [dict(f) for f in (favorites or []) if isinstance(f, dict)]
    key = job_key(job)
    kept = [f for f in current if job_key(f) != key]
    if len(kept) != len(current):
        return kept, "removed"
    if len(current) >= FAVORITE_LIMIT:
        return current, "full"
    return current + [make_favorite(job)], "added"


def remove_favorite(favorites, job: dict) -> list:
    key = job_key(job)
    return [f for f in (favorites or []) if isinstance(f, dict) and job_key(f) != key]


def encode_favorites(favorites) -> str:
    """收藏 → URL 参数值（job_id 逗号分隔，去重、保持顺序、按上限截断）。"""
    ids = []
    for f in favorites or []:
        jid = str(f.get("job_id") or "").strip() if isinstance(f, dict) else ""
        if jid and jid not in ids:
            ids.append(jid)
    return ",".join(ids[:FAVORITE_LIMIT])


def decode_favorites(raw) -> list[str]:
    """URL 参数值 → job_id 列表（兼容逗号/竖线分隔，去重并截断）。"""
    if not raw:
        return []
    text = raw if isinstance(raw, str) else ",".join(str(x) for x in raw)
    out = []
    for part in re.split(r"[,|]+", text):
        jid = part.strip()
        if jid and jid not in out:
            out.append(jid)
    return out[:FAVORITE_LIMIT]


def hydrate_favorites(job_ids, rows) -> list[dict]:
    """按 job_id 从语料还原收藏（语料重建后消失的 job_id 自动跳过）。"""
    index = {str(r.get("job_id") or ""): r for r in rows or [] if isinstance(r, dict)}
    out = []
    for jid in job_ids or []:
        r = index.get(str(jid))
        if r is not None:
            out.append(make_favorite(r))
    return out
