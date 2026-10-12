"""匹配器抽象接口。"""
from __future__ import annotations

from abc import ABC, abstractmethod


class Matcher(ABC):
    @abstractmethod
    def fit(self, corpus: list[str]) -> None:
        """索引语料（如技能标准词表）。"""

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> list[tuple[str, float]]:
        """检索，返回 [(corpus_item, score)] 按分数降序。"""
