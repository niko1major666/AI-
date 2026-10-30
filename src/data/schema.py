"""数据契约：JobPosting / SkillSpan 及其序列化。"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional


@dataclass
class JobPosting:
    job_id: str
    source: str
    company: str
    company_norm: str
    title: str
    location: str
    salary_raw: str
    salary_min_k: Optional[float]
    salary_max_k: Optional[float]
    salary_months: Optional[int]
    experience: str
    education: str
    jd_text: str
    jd_clean: str
    crawl_time: str
    text_hash: str
    department: str = ""
    publish_time: str = ""
    first_seen_at: str = ""
    last_seen_at: str = ""
    is_active: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SkillSpan:
    job_id: str
    skill_text: str
    skill_text_norm: str
    skill_id: str
    category: str
    start: Optional[int]
    end: Optional[int]
    score: float
    method: str
    is_must: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BuildStats:
    raw_rows: int
    cleaned_rows: int
    dropped_short: int
    deduped_rows: int
    company_count: int
    companies: list

    def to_dict(self) -> dict:
        return asdict(self)
