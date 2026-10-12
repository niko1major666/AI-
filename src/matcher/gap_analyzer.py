"""技能差距诊断：匹配度打分 + 缺失技能 + 优先级 + 学习建议 + 道桥迁移。"""
from __future__ import annotations

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
    priority: str          # P0 / P1 / P2
    priority_score: float
    why: str
    transfer_hint: str = ""
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
    def __init__(self, taxonomy: Taxonomy, transfer_map=None, resources=None,
                 matcher=None, must_weight: float = 2.0, nice_weight: float = 1.0):
        self.taxonomy = taxonomy
        self.must_weight = must_weight
        self.nice_weight = nice_weight
        self.matcher = matcher
        self._transfer = self._index_transfer(transfer_map)
        self._resources = self._index_resources(resources)

    # ---- 索引 ----
    @staticmethod
    def _index_transfer(transfer_map) -> dict:
        out = {}
        for t in (transfer_map or {}).get("transfers", []):
            hint = f"{t.get('rationale', '')} 建议：{t.get('action', '')}"
            for sid in t.get("target_skills", []):
                out[sid] = hint
        return out

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
    def analyze(self, user_skills: list[str], jd_skills: list[dict],
                demand: Optional[dict] = None) -> GapReport:
        """jd_skills: [{'skill_id','name','is_must'}]；demand: {skill_id: 需求占比}。"""
        matched = self.match_user_skills(user_skills)
        matched_ids = set(matched)

        total_w = 0.0
        got_w = 0.0
        for s in jd_skills:
            w = self.must_weight if s.get("is_must") else self.nice_weight
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
                priority=prio, priority_score=pscore, why=why,
                transfer_hint=self._transfer.get(s["skill_id"], ""),
                resources=self._resources.get(s["skill_id"], []),
            ))
        missing.sort(key=lambda x: -x.priority_score)
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
        if sk is not None and sk.difficulty <= 2:
            score += 10
        if s.get("is_must"):
            prio = "P0"
        elif ratio >= 0.3:
            prio = "P1"
        else:
            prio = "P2"
        why = f"需求占比 {ratio:.0%}；{'硬性要求' if s.get('is_must') else '加分项'}"
        return prio, round(score, 1), why
def _demo() -> int:
    import yaml

    from src.matcher.tfidf_matcher import TfidfMatcher

    root = Path(__file__).resolve().parents[2]
    taxonomy = Taxonomy(str(root / "data" / "kb" / "skill_taxonomy.yaml"))
    transfer = yaml.safe_load((root / "data" / "kb" / "transfer_map.yaml").read_text(encoding="utf-8"))
    resources = yaml.safe_load((root / "data" / "kb" / "learning_resources.yaml").read_text(encoding="utf-8"))
    matcher = TfidfMatcher().fit([s.name for s in taxonomy.all_skills()])
    analyzer = SkillGapAnalyzer(taxonomy, transfer_map=transfer, resources=resources, matcher=matcher)

    user_skills = ["Python", "Pandas", "桥梁结构有限元分析", "AutoCAD"]
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
        if m.transfer_hint:
            print(f"        道桥迁移: {m.transfer_hint}")
        for r in m.resources[:2]:
            print(f"        资源: {r.get('title')}  {r.get('url')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_demo())