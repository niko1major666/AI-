"""BGE 语义匹配器（sentence-transformers，余弦相似度）。"""
from __future__ import annotations

import numpy as np


class BgeMatcher:
    def __init__(self, model_id: str = "BAAI/bge-base-zh-v1.5", device: str = "cpu",
                 query_instruction: str = "", normalize: bool = True):
        self.model_id = model_id
        self.device = device
        self.query_instruction = query_instruction
        self.normalize = normalize
        self._model = None
        self.corpus: list[str] = []
        self.corpus_embeddings = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_id, device=self.device)
        return self._model

    def fit(self, corpus: list[str]) -> "BgeMatcher":
        self.corpus = list(corpus)
        self.corpus_embeddings = self._load().encode(
            self.corpus, normalize_embeddings=self.normalize, show_progress_bar=False)
        return self

    def search(self, query: str, top_k: int = 5) -> list[tuple[str, float]]:
        if self.corpus_embeddings is None:
            raise RuntimeError("请先调用 fit() 索引语料")
        qtext = (self.query_instruction + query) if self.query_instruction else query
        q = self._load().encode([qtext], normalize_embeddings=self.normalize)
        scores = (q @ self.corpus_embeddings.T)[0]
        order = np.argsort(-scores)[:top_k]
        return [(self.corpus[i], float(scores[i])) for i in order]
