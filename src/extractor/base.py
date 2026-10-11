"""抽取器抽象接口。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from src.data.schema import SkillSpan


class Extractor(ABC):
    """所有技能抽取器需实现 extract，返回每篇文本对应的 SkillSpan 列表。"""

    @abstractmethod
    def extract(self, texts: Iterable[str], **kwargs) -> list[list[SkillSpan]]:
        raise NotImplementedError
