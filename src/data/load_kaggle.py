"""YAML 驱动列映射：把任意 JD CSV 读成规范 DataFrame。

设计目标：不硬编码任何列名，适配未知结构的 Kaggle/爬虫数据集。
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd

CANONICAL = ["job_id", "company", "title", "location", "salary",
             "experience", "education", "jd_text"]


def resolve_column(mapping: dict, base: str, columns: Iterable[str]):
    """在 mapping 中查找 canonical 字段对应的实际列名（含别名）。"""
    candidates = []
    primary = mapping.get(base)
    if primary:
        candidates.append(primary)
    for a in (mapping.get(base + "_aliases") or []):
        if a:
            candidates.append(a)
    for c in candidates:
        if c in columns:
            return c
    return None


def load_dataframe(path: str, column_mapping: dict) -> pd.DataFrame:
    """读取 CSV，按映射重命名为规范列名（dtype=str，避免空值 NaN 干扰）。"""
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    rename = {}
    for canon in CANONICAL:
        c = resolve_column(column_mapping, canon, df.columns)
        if c is not None and c != canon:
            rename[c] = canon
    if rename:
        df = df.rename(columns=rename)
    return df
