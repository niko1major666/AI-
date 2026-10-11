"""基于词表的规则抽取基线（字典匹配）。

实测发现：SiameseUIE 零样本对抽象技能类别（"编程语言"等）召回极低且不稳定，
而词表（128 技能 + 别名）是高精度字典——直接匹配即可高召回地抽出已知技能。
与 SiameseUIE 互补：词表覆盖已知技能，零样本负责发现词表外新技能。
"""
from __future__ import annotations

import re

from src.data.schema import SkillSpan
from src.extractor.postprocess import normalize_skill
from src.skillkb.loader import Taxonomy


class RuleBaselineExtractor:
    def __init__(self, taxonomy: Taxonomy):
        self.taxonomy = taxonomy
        self._tokens = self._build_tokens(taxonomy)

    @staticmethod
    def _build_tokens(taxonomy):
        tokens = []
        seen = set()
        for sk in taxonomy.all_skills():
            for raw in [sk.name] + sk.aliases:
                t = str(raw).strip().lower()
                if not t or t in seen:
                    continue
                seen.add(t)
                tokens.append((t, sk))
        # 最长优先，避免 "Transformer" 与 "HuggingFace Transformers" 部分重叠
        tokens.sort(key=lambda x: -len(x[0]))
        return tokens

    @staticmethod
    def _iter_matches(text_lower, token):
        # 英文 token 用词边界，避免 "go" 误匹配 "google"
        if token.isascii():
            pat = r"(?<![a-zA-Z0-9])" + re.escape(token) + r"(?![a-zA-Z0-9])"
        else:
            pat = re.escape(token)
        return [(m.start(), m.end()) for m in re.finditer(pat, text_lower)]

    def extract_spans(self, job_id, text, method="rule_baseline", conf=1.0):
        text_lower = text.lower()
        spans = []
        occupied = []  # 已占用区间（避免重叠重复）
        for token, sk in self._tokens:
            if len(token) < 2:
                continue
            for s, e in self._iter_matches(text_lower, token):
                if any(not (e <= a or s >= b) for a, b in occupied):
                    continue
                occupied.append((s, e))
                spans.append(SkillSpan(
                    job_id=job_id,
                    skill_text=text[s:e],
                    skill_text_norm=normalize_skill(text[s:e]),
                    skill_id=sk.id,
                    category=sk.category,
                    start=s, end=e,
                    score=conf, method=method,
                ))
        # 去重：同一 job 内同一 skill_id 只保留一次（"RAG检索增强"里 RAG/检索增强 同属一个技能）
        deduped = []
        seen_ids = set()
        for s in spans:
            if s.skill_id in seen_ids:
                continue
            seen_ids.add(s.skill_id)
            deduped.append(s)
        return deduped
