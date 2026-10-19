"""从 bert-base-chinese 重新训练 BERT-NER（仅 30 条人工标注，恢复旧模型 exact 0.636）。

用法：python scripts/restore_ner.py [epochs]
与 train_ner.py 的区别：从基础模型从头训练，且不追加弱标注数据。
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
os.environ.setdefault("HF_HOME", str(ROOT / "models" / "hf_cache"))
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

LABELS = ["O", "B-SKILL", "I-SKILL"]
LABEL2ID = {l: i for i, l in enumerate(LABELS)}


def load_gold(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines()]


def align_labels(offsets, spans):
    labels = []
    cur = -1
    for (s, e) in offsets:
        if s == e:
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
    print(f"训练样本 {len(train)}（仅人工标注），epochs={epochs}", flush=True)

    base = "bert-base-chinese"
    # 优先用本地缓存 snapshot 路径（避免联网 / 缓存路径不匹配）
    snap_dir = ROOT / "models" / "hf_cache" / "models--bert-base-chinese" / "snapshots"
    if snap_dir.exists():
        snaps = sorted(p for p in snap_dir.iterdir() if p.is_dir())
        if snaps:
            base = str(snaps[0])
            print(f"使用本地缓存：{base}", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(base, use_fast=True, local_files_only=True)
    model = AutoModelForTokenClassification.from_pretrained(base, num_labels=len(LABELS), local_files_only=True)
    optimizer = AdamW(model.parameters(), lr=5e-5)

    model.train()
    for ep in range(epochs):
        total = 0.0
        for i, row in enumerate(train):
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
            if (i + 1) % 10 == 0 or i == len(train) - 1:
                print(f"  epoch {ep + 1} 样本 {i + 1}/{len(train)} loss={outputs.loss.item():.4f}", flush=True)
        print(f"epoch {ep + 1}/{epochs} avg_loss={total / len(train):.4f}", flush=True)

    out_dir = ROOT / "models" / "bert_ner"
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))
    print("saved to", out_dir, flush=True)


if __name__ == "__main__":
    main()
