"""技能词表加载与别名解析。"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class Skill:
    id: str
    name: str
    category: str
    category_name: str
    aliases: list = field(default_factory=list)
    difficulty: int = 3
    importance: int = 3


def _norm(s) -> str:
    """归一化：小写 + 去空白/连接符/括号。用于别名索引与查询。"""
    t = str(s).strip().lower()
    t = re.sub(r"[\s·_\-/（）()【】\[\]]+", "", t)
    return t


class Taxonomy:
    """从 skill_taxonomy.yaml 加载，提供别名->技能解析与模糊回退。"""

    def __init__(self, path: str):
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        cat_names = {c["id"]: c["name"] for c in data["categories"]}
        self.categories = [(c["id"], c["name"]) for c in data["categories"]]

        self.skills: list[Skill] = []
        self._by_id: dict[str, Skill] = {}
        self._alias_index: dict[str, Skill] = {}
        for s in data["skills"]:
            sk = Skill(
                id=s["id"],
                name=s["name"],
                category=s["id"].split(".")[0],
                category_name=cat_names.get(s["category"], s["category"]),
                aliases=list(s.get("aliases", [])),
                difficulty=int(s.get("difficulty", 3)),
                importance=int(s.get("importance", 3)),
            )
            self.skills.append(sk)
            self._by_id[sk.id] = sk
            for token in [sk.name] + sk.aliases:
                self._alias_index[_norm(token)] = sk
        self._keys = sorted(self._alias_index.keys())

    def resolve(self, text: str, category: Optional[str] = None) -> Optional[Skill]:
        """先精确匹配（名字/别名），失败则模糊匹配。category 作为后续消歧用。"""
        key = _norm(text)
        if not key:
            return None
        if key in self._alias_index:
            return self._alias_index[key]
        m = difflib.get_close_matches(key, self._keys, n=1, cutoff=0.86)
        if m:
            return self._alias_index[m[0]]
        return None

    def by_id(self, skill_id: str) -> Optional[Skill]:
        return self._by_id.get(skill_id)

    def all_skills(self) -> list[Skill]:
        return list(self.skills)
