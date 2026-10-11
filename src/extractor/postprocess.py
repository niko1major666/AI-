"""抽取结果后处理：版本剥离、归一、词表映射、去重。"""
from __future__ import annotations

import re
from typing import Iterable

from src.data.schema import SkillSpan

# SiameseUIE schema 类型名 -> 词表类别 ID
SCHEMA_TYPE_TO_CATEGORY = {
    "编程语言": "PROG",
    "深度学习框架": "FRAMEWORK",
    "机器学习算法": "ML",
    "AI专有技术": "AITECH",
    "大数据与数据处理": "BIGDATA",
    "工程工具与平台": "ENGINEERING",
}

_VERSION_RE = re.compile(r"\s*\d+(?:\.\d+)*[xX]?\s*$")


def strip_version(s: str) -> str:
    """'Python 3.8' -> 'Python'；'PyTorch 2.0' -> 'PyTorch'。"""
    return _VERSION_RE.sub("", s).strip()


def normalize_skill(s: str) -> str:
    """小写 + 去空白（用于 skill_text_norm）。"""
    return re.sub(r"\s+", "", str(s).strip().lower())


def _unwrap(item):
    """把 SiameseUIE 返回的实体统一成 (text, score, start, end)。"""
    if isinstance(item, str):
        return item, 1.0, None, None
    if isinstance(item, dict):
        text = item.get("text") or item.get("span") or item.get("name") or ""
        try:
            score = float(item.get("score", item.get("prob", 1.0)))
        except (TypeError, ValueError):
            score = 1.0
        return text, score, item.get("start"), item.get("end")
    return "", 0.0, None, None


def to_skill_spans(job_id: str, typed_entities: dict, taxonomy, method: str,
                   conf_threshold: float = 0.0) -> list[SkillSpan]:
    """把 {类型: [实体...]} 映射为 SkillSpan 列表（含未命中词表的 UNRESOLVED 占位）。"""
    spans: list[SkillSpan] = []
    for type_name, items in typed_entities.items():
        cat = SCHEMA_TYPE_TO_CATEGORY.get(type_name, type_name)
        for item in items or []:
            text, score, start, end = _unwrap(item)
            if not text or score < conf_threshold:
                continue
            cleaned = strip_version(str(text).strip())
            norm = normalize_skill(cleaned)
            if not norm:
                continue
            sk = taxonomy.resolve(cleaned, category=cat)
            if sk is not None:
                skill_id, name, cat2 = sk.id, sk.name, sk.category
            else:
                skill_id, name, cat2 = f"UNRESOLVED.{norm}", cleaned, cat
            spans.append(SkillSpan(
                job_id=job_id, skill_text=str(text).strip(), skill_text_norm=norm,
                skill_id=skill_id, category=cat2, start=start, end=end,
                score=round(score, 4), method=method,
            ))
    return _dedup(spans)


def _dedup(spans: Iterable[SkillSpan]) -> list[SkillSpan]:
    seen: set[str] = set()
    out: list[SkillSpan] = []
    for s in spans:
        key = s.skill_id or s.skill_text_norm
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out
