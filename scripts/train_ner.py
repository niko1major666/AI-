"""微调 bert-base-chinese 做技能 NER（BIO 标注），保存到 models/bert_ner/。

用法：python scripts/train_ner.py [epochs]
"""
import json
import os
import sys
from pathlib import Path

import torch
from torch.optim import AdamW
from transformers import AutoModelForTokenClassification, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# 复用项目内缓存（避免联网下载）
os.environ.setdefault("HF_HOME", str(ROOT / "models" / "hf_cache"))
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

LABELS = ["O", "B-SKILL", "I-SKILL"]
LABEL2ID = {l: i for i, l in enumerate(LABELS)}


def load_gold(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines()]


def align_labels(offsets, spans):
    """把 token 字符偏移对齐到 BIO 标签。"""
    labels = []
    cur = -1
    for (s, e) in offsets:
        if s == e:  # 特殊 token，loss 忽略
            labels.append(-100)
            cur = -1
            continue
        hit = -1
        for i, (gs, ge) in enumerate(spans):
            if s >= gs and e <= ge:
                hit = i
                break
        if hit == -1:
            labels.append(LABEL2ID["O"])
            cur = -1
        elif hit == cur:
            labels.append(LABEL2ID["I-SKILL"])
        else:
            labels.append(LABEL2ID["B-SKILL"])
            cur = hit
    return labels


def main():
    epochs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    train = load_gold(ROOT / "data" / "gold" / "jd_skills_gold_train.jsonl")
    # 追加弱标注（规则基线自动标注的真实 JD）
    weak_path = ROOT / "data" / "gold" / "weak_train.jsonl"
    if weak_path.exists():
        n_manual = len(train)
        train += load_gold(weak_path)
        print(f"训练样本 {len(train)}（人工 {n_manual} + 弱标注 {len(train) - n_manual}），epochs={epochs}")
    else:
        print(f"训练样本 {len(train)}，epochs={epochs}")

    # 从现有已训练模型继续微调（基础模型 bert-base-chinese 不在缓存，但 models/bert_ner 含完整权重）
    base = str(ROOT / "models" / "bert_ner")
    tokenizer = AutoTokenizer.from_pretrained(base, use_fast=True)
    model = AutoModelForTokenClassification.from_pretrained(base, num_labels=len(LABELS))
    optimizer = AdamW(model.parameters(), lr=5e-5)

    model.train()
    for ep in range(epochs):
        total = 0.0
        for row in train:
            enc = tokenizer(row["text"], return_offsets_mapping=True, return_tensors="pt", truncation=True)
            offsets = enc["offset_mapping"][0].tolist()
            labels = align_labels(offsets, [(s["start"], s["end"]) for s in row["spans"]])
            label_tensor = torch.tensor([labels])
            optimizer.zero_grad()
            outputs = model(input_ids=enc["input_ids"], attention_mask=enc["attention_mask"],
                            labels=label_tensor)
            outputs.loss.backward()
            optimizer.step()
            total += outputs.loss.item()
        print(f"epoch {ep + 1}/{epochs}  avg_loss={total / len(train):.4f}")

    out_dir = ROOT / "models" / "bert_ner"
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))
    print("saved to", out_dir)


if __name__ == "__main__":
    main()
