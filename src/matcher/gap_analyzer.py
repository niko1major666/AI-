"""技能差距诊断：匹配度打分 + 缺失技能 + 优先级 + 学习资源。"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from src.skillkb.loader import Taxonomy


@dataclass
class GapItem:
    skill_id: str
    name: str
    category: str
    is_must: bool
    difficulty: int
    importance: int
    priority: str          # P0 / P1 / P2
    priority_score: float
    why: str
    resources: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GapReport:
    match_score: float
    matched_skill_ids: list
    matched_total: int
    missing_total: int
    missing: list          # list[GapItem]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["missing"] = [m.to_dict() for m in self.missing]
        return d


class SkillGapAnalyzer:
    def __init__(self, taxonomy: Taxonomy, resources=None,
                 matcher=None, must_weight: float = 2.0, nice_weight: float = 1.0):
        self.taxonomy = taxonomy
        self.must_weight = must_weight
        self.nice_weight = nice_weight
        self.matcher = matcher
        self._resources = self._index_resources(resources)

    # ---- 索引 ----
    @staticmethod
    def _index_resources(resources) -> dict:
        return {r["skill_id"]: r.get("items", [])
                for r in (resources or {}).get("resources", [])}

    # ---- 用户技能 -> 词表 ----
    def resolve_user_skill(self, text: str):
        """返回 (skill_id, name, method)。method: exact | tfidf | unresolved。"""
        sk = self.taxonomy.resolve(text)
        if sk is not None:
            return sk.id, sk.name, "exact"
        if self.matcher is not None:
            for corpus_item, score in self.matcher.search(text, top_k=3):
                if score < 0.25:
                    break
                cand = self.taxonomy.resolve(corpus_item)
                if cand is not None:
                    return cand.id, cand.name, "tfidf"
        return None, text, "unresolved"

    def match_user_skills(self, user_skills: list[str]) -> dict:
        matched = {}
        for t in user_skills:
            sid, name, method = self.resolve_user_skill(t)
            if sid:
                matched.setdefault(sid, {"name": name, "method": method, "raw": t})
        return matched

    # ---- 主分析 ----
    def weight(self, skill: dict, use_tf: bool = True) -> float:
        """技能权重：must/nice 基础权重 × JD 内强调度（1 + ln tf）。

        tf > 1 表示该技能在本岗位 JD 中被多次提及（岗位自己更看重它），
        没有 tf 信息时（旧调用方/纯集合场景）退化为 1.0，保持历史行为不变。
        """
        base = self.must_weight if skill.get("is_must") else self.nice_weight
        if not use_tf:
            return base
        tf = float(skill.get("tf", 1) or 1)
        return base * (1.0 + math.log(max(tf, 1.0)))

    def analyze(self, user_skills: list[str], jd_skills: list[dict],
                demand: Optional[dict] = None, use_tf: bool = True) -> GapReport:
        """jd_skills: [{'skill_id','name','is_must','tf','must_evidence'}]；
        demand: {skill_id: 需求占比}，用于优先级与兜底说明。"""
        matched = self.match_user_skills(user_skills)
        matched_ids = set(matched)

        total_w = 0.0
        got_w = 0.0
        for s in jd_skills:
            w = self.weight(s, use_tf=use_tf)
            total_w += w
            if s["skill_id"] in matched_ids:
                got_w += w
        match_score = round(got_w / total_w * 100, 1) if total_w else 0.0

        missing = []
        for s in jd_skills:
            if s["skill_id"] in matched_ids:
                continue
            sk = self.taxonomy.by_id(s["skill_id"])
            ratio = float((demand or {}).get(s["skill_id"], 0.0))
            prio, pscore, why = self._priority(s, sk, ratio)
            missing.append(GapItem(
                skill_id=s["skill_id"],
                name=s.get("name") or (sk.name if sk else s["skill_id"]),
                category=sk.category if sk else "",
                is_must=bool(s.get("is_must")),
                difficulty=sk.difficulty if sk else 3,
                importance=sk.importance if sk else 3,
                priority=prio, priority_score=pscore, why=why,
                resources=self._resources.get(s["skill_id"], []),
            ))
        _prio_order = {"P0": 0, "P1": 1, "P2": 2}
        missing.sort(key=lambda x: (_prio_order[x.priority], -x.priority_score))
        return GapReport(
            match_score=match_score,
            matched_skill_ids=sorted(matched_ids),
            matched_total=len(matched_ids),
            missing_total=len(missing),
            missing=missing,
        )

    @staticmethod
    def _priority(s: dict, sk, ratio: float):
        score = ratio * 100
        if s.get("is_must"):
            score += 40
        if sk is not None:
            # 行业重要度越高越优先（高于基准 3 的每档 +8 分）
            score += (sk.importance - 3) * 8
            # 越容易上手性价比越高
            if sk.difficulty <= 2:
                score += 10
            elif sk.difficulty >= 4:
                score -= 5
        if s.get("is_must"):
            prio = "P0"
        elif ratio >= 0.3:
            prio = "P1"
        else:
            prio = "P2"
        if s.get("is_must"):
            ev = str(s.get("must_evidence") or "").strip()
            why = (f"硬性要求（{ev}），需求占比 {ratio:.0%}" if ev
                   else f"硬性要求，需求占比 {ratio:.0%}")
        elif ratio >= 0.3:
            why = f"高频需求（占比 {ratio:.0%}），多数岗位需要"
        else:
            why = f"加分项（占比 {ratio:.0%}），可后续补充"
        return prio, round(score, 1), why
def _demo() -> int:
    import yaml

    from src.matcher.tfidf_matcher import TfidfMatcher

    root = Path(__file__).resolve().parents[2]
    taxonomy = Taxonomy(str(root / "data" / "kb" / "skill_taxonomy.yaml"))
    resources = yaml.safe_load((root / "data" / "kb" / "learning_resources.yaml").read_text(encoding="utf-8"))
    matcher = TfidfMatcher().fit([s.name for s in taxonomy.all_skills()])
    analyzer = SkillGapAnalyzer(taxonomy, resources=resources, matcher=matcher)

    user_skills = ["Python", "Pandas", "数据结构", "Linux"]
    jd_skills = [
        {"skill_id": "PROG.PYTHON", "name": "Python", "is_must": True},
        {"skill_id": "FRAMEWORK.PYTORCH", "name": "PyTorch", "is_must": True},
        {"skill_id": "ML.TRANSFORMER", "name": "Transformer", "is_must": True},
        {"skill_id": "AITECH.DISTRIBUTED", "name": "分布式训练", "is_must": False},
        {"skill_id": "AITECH.RAG", "name": "RAG", "is_must": False},
        {"skill_id": "AITECH.VECTORDB", "name": "向量数据库", "is_must": False},
    ]
    demand = {"PROG.PYTHON": .9, "FRAMEWORK.PYTORCH": .85, "ML.TRANSFORMER": .8,
              "AITECH.DISTRIBUTED": .55, "AITECH.RAG": .6, "AITECH.VECTORDB": .5}

    rep = analyzer.analyze(user_skills, jd_skills, demand=demand)
    print(f"匹配度 {rep.match_score}%  命中 {rep.matched_total}  缺失 {rep.missing_total}")
    for m in rep.missing:
        print(f"  [{m.priority}] {m.name:<12} score={m.priority_score}  {m.why}")
        for r in m.resources[:2]:
            print(f"        资源: {r.get('title')}  {r.get('url')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_demo())