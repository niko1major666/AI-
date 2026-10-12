"""BERT-NER 技能抽取器（基于 HF token classification 模型）。"""
from __future__ import annotations

import torch

LABELS = ["O", "B-SKILL", "I-SKILL"]
ID2LABEL = {i: l for i, l in enumerate(LABELS)}


class BertNerExtractor:
    def __init__(self, model_dir: str, device: str = "cpu"):
        from transformers import AutoModelForTokenClassification, AutoTokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir, use_fast=True)
        self.model = AutoModelForTokenClassification.from_pretrained(model_dir)
        self.model.eval()
        self.device = device
        try:
            self.model.to(device)
        except Exception:  # noqa: BLE001
            pass

    def extract_char_spans(self, text: str) -> list:
        """预测 BIO 标签并转成 (start, end) 字符区间（半开）。"""
        enc = self.tokenizer(text, return_offsets_mapping=True, return_tensors="pt",
                             truncation=True, max_length=512)
        offsets = enc["offset_mapping"][0].tolist()
        inputs = {k: v.to(self.device) for k, v in enc.items() if k != "offset_mapping"}
        with torch.no_grad():
            logits = self.model(**inputs).logits
        preds = logits[0].argmax(-1).tolist()

        spans = []
        cur = None
        for pid, (s, e) in zip(preds, offsets):
            if s == e:  # 特殊 token
                if cur is not None:
                    spans.append(tuple(cur))
                    cur = None
                continue
            label = ID2LABEL.get(pid, "O")
            if label == "B-SKILL":
                if cur is not None:
                    spans.append(tuple(cur))
                cur = [s, e]
            elif label == "I-SKILL":
                if cur is not None:
                    cur[1] = e
            else:
                if cur is not None:
                    spans.append(tuple(cur))
                    cur = None
        if cur is not None:
            spans.append(tuple(cur))
        return spans

    def extract_spans(self, job_id: str, text: str):
        from src.data.schema import SkillSpan
        out = []
        for s, e in self.extract_char_spans(text):
            out.append(SkillSpan(
                job_id=job_id, skill_text=text[s:e],
                skill_text_norm=text[s:e].lower(), skill_id="",
                category="", start=s, end=e, score=1.0, method="bert_ner"))
        return out
