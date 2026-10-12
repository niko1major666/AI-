"""TF-IDF 字符 n-gram 匹配器（中文检索基线，作为 BGE 的对照组）。"""
from __future__ import annotations

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class TfidfMatcher:
    def __init__(self, analyzer: str = "char_wb", ngram_range=(2, 4),
                 max_features: int = 20000):
        self.vectorizer = TfidfVectorizer(
            analyzer=analyzer,
            ngram_range=tuple(ngram_range),
            max_features=max_features,
        )
        self.corpus: list[str] = []
        self.matrix = None

    def fit(self, corpus: list[str]) -> "TfidfMatcher":
        self.corpus = list(corpus)
        self.matrix = self.vectorizer.fit_transform(self.corpus)
        return self

    def search(self, query: str, top_k: int = 5) -> list[tuple[str, float]]:
        if self.matrix is None:
            raise RuntimeError("请先调用 fit() 索引语料")
        q = self.vectorizer.transform([query])
        scores = cosine_similarity(q, self.matrix)[0]
        order = np.argsort(-scores)[:top_k]
        return [(self.corpus[i], float(scores[i])) for i in order]
