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
            # skip_extract：只在「用户输入解析」时使用，JD 抽取忽略（避免“可量化”这类噪声）
            skip = {str(x).strip().lower() for x in getattr(sk, "skip_extract", [])}
            for raw in [sk.name] + sk.aliases:
                t = str(raw).strip().lower()
                if not t or t in seen or t in skip:
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

    def extract(self, job_id, text, method="rule_baseline", conf=1.0):
        """一次扫描同时产出技能 span 与「每技能提及次数」。

        拆成 extract_spans + count_mentions 会把全文正则扫描跑两遍，
        实测 4582 条 JD 冷启动从 9s 变成 18s，故合并为单次扫描。
        返回 (去重后的 spans, {skill_id: 提及次数})。
        """
        text_lower = text.lower()
        spans = []
        counts = {}
        occupied = []  # 已占用区间（避免重叠重复）
        for token, sk in self._tokens:
            if len(token) < 2:
                continue
            for s, e in self._iter_matches(text_lower, token):
                if any(not (e <= a or s >= b) for a, b in occupied):
                    continue
                occupied.append((s, e))
                counts[sk.id] = counts.get(sk.id, 0) + 1
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
        return deduped, counts

    def extract_spans(self, job_id, text, method="rule_baseline", conf=1.0):
        """只取技能 span（兼容旧调用方）。"""
        return self.extract(job_id, text, method=method, conf=conf)[0]

    def count_mentions(self, text: str) -> dict[str, int]:
        """只取每技能提及次数（JD 内强调度加权用；不需要 span 时避免构造对象）。"""
        return self.extract("", text or "")[1]
