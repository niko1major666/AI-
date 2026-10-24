"""多岗位对比：同一份简历对多个目标岗位的匹配度、共性缺口与差异缺口。"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ComparedJob:
    label: str
    company: str
    title: str
    match_score: float
    matched_total: int
    missing_total: int
    p0_total: int
    missing_ids: list = field(default_factory=list)


@dataclass
class CompareResult:
    jobs: list = field(default_factory=list)          # list[ComparedJob]
    common_missing: list = field(default_factory=list)  # 所有岗位都缺的技能名
    unique_missing: dict = field(default_factory=dict)  # label -> 只有该岗位缺的技能名
    best_label: str = ""                                 # 匹配度最高（同分时缺口最少）

    def to_dict(self) -> dict:
        return {
            "best_label": self.best_label,
            "common_missing": list(self.common_missing),
            "unique_missing": {k: list(v) for k, v in self.unique_missing.items()},
            "jobs": [
                {
                    "label": j.label, "company": j.company, "title": j.title,
                    "match_score": j.match_score, "matched_total": j.matched_total,
                    "missing_total": j.missing_total, "p0_total": j.p0_total,
                    "missing_ids": list(j.missing_ids),
                }
                for j in self.jobs
            ],
        }


def compare_jobs(analyzer, user_skills, targets: list, *, unique_limit: int = 8) -> CompareResult:
    """targets: [{'label','company','title','jd_skills','demand'}]（jd_skills 同 analyzer.analyze）。

    少于 1 个目标时返回空结果；1 个目标时 unique_missing 为空（没有对比对象）。
    """
    if not targets:
        return CompareResult()

    reports = []
    for t in targets:
        rep = analyzer.analyze(
            user_skills or [],
            t.get("jd_skills") or [],
            demand=t.get("demand"),
        )
        reports.append((t, rep))

    jobs = []
    for t, rep in reports:
        jobs.append(ComparedJob(
            label=str(t.get("label") or t.get("title") or ""),
            company=str(t.get("company") or ""),
            title=str(t.get("title") or ""),
            match_score=float(rep.match_score),
            matched_total=int(rep.matched_total),
            missing_total=int(rep.missing_total),
            p0_total=sum(1 for m in rep.missing if m.priority == "P0"),
            missing_ids=[m.skill_id for m in rep.missing],
        ))

    names = {}
    for _t, rep in reports:
        for m in rep.missing:
            names.setdefault(m.skill_id, m.name)

    id_sets = [set(j.missing_ids) for j in jobs]
    common = set.intersection(*id_sets) if id_sets else set()
    result = CompareResult(
        jobs=jobs,
        common_missing=[names[sid] for sid in sorted(common, key=lambda x: names[x])],
        best_label=max(jobs, key=lambda j: (j.match_score, -j.missing_total)).label,
    )

    if len(id_sets) > 1:
        for idx, job in enumerate(jobs):
            others = set().union(*(id_sets[i] for i in range(len(id_sets)) if i != idx))
            only_here = [sid for sid in job.missing_ids if sid not in others]
            result.unique_missing[job.label] = [names[sid] for sid in only_here][:unique_limit]
    else:
        result.unique_missing = {jobs[0].label: []}
    return result
