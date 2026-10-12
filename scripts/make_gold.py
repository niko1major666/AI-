"""生成技能抽取金标准：人工标注「句子 -> 技能列表」，自动计算字符偏移。

产出：
  data/gold/jd_skills_gold_train.jsonl   (训练 BERT-NER 用)
  data/gold/jd_skills_gold_test.jsonl    (评估 F1 用)
"""
import json
from pathlib import Path

# (句子, [技能...]) —— 人工标注（技能来自词表，偏移由脚本计算）
SENTENCES = [
    ("熟悉Python编程语言", ["Python"]),
    ("掌握PyTorch和TensorFlow深度学习框架", ["PyTorch", "TensorFlow"]),
    ("了解Transformer与注意力机制", ["Transformer", "注意力机制"]),
    ("有分布式训练经验者优先", ["分布式训练"]),
    ("熟悉向量数据库如Milvus", ["向量数据库"]),
    ("掌握RAG检索增强生成技术", ["RAG"]),
    ("了解LoRA低秩适配微调", ["LoRA", "微调"]),
    ("熟悉大模型预训练与微调", ["大模型", "微调"]),
    ("掌握SQL数据库操作", ["SQL"]),
    ("熟悉Linux操作系统和Git版本管理", ["Linux", "Git"]),
    ("掌握Docker容器化部署", ["Docker"]),
    ("了解Kubernetes集群管理", ["Kubernetes"]),
    ("熟悉Spark大数据处理", ["Spark"]),
    ("掌握Pandas和NumPy数据处理", ["Pandas", "NumPy"]),
    ("了解机器学习与深度学习基础", ["机器学习", "深度学习"]),
    ("掌握CNN卷积神经网络", ["CNN"]),
    ("了解RNN和LSTM序列模型", ["RNN", "LSTM"]),
    ("熟悉目标检测与图像分割", ["目标检测", "图像分割"]),
    ("掌握计算机视觉算法", ["计算机视觉"]),
    ("了解自然语言处理NLP技术", ["NLP"]),
    ("熟悉推荐系统算法", ["推荐系统"]),
    ("掌握图神经网络GNN", ["图神经网络"]),
    ("了解强化学习RL", ["强化学习"]),
    ("熟悉模型部署与推理加速", ["模型部署", "推理加速"]),
    ("掌握模型量化与模型压缩", ["量化", "模型压缩"]),
    ("了解知识蒸馏技术", ["知识蒸馏"]),
    ("熟悉特征工程与特征选择", ["特征工程", "特征选择"]),
    ("掌握数据清洗与数据挖掘", ["数据清洗", "数据挖掘"]),
    ("了解实时计算与数据管道", ["实时计算", "数据管道"]),
    ("熟悉CUDA并行计算", ["CUDA", "并行计算"]),
    ("掌握gRPC接口开发", ["gRPC"]),
    ("熟悉RESTful API设计", ["RESTful API"]),
    ("了解微服务架构", ["微服务"]),
    ("掌握单元测试与CI/CD", ["单元测试", "CI/CD"]),
    ("熟悉AWS云计算平台", ["AWS"]),
    ("掌握Redis缓存", ["Redis"]),
    ("了解Elasticsearch搜索", ["Elasticsearch"]),
    ("熟悉MySQL数据库", ["MySQL"]),
    ("掌握知识图谱构建", ["知识图谱"]),
    ("了解多模态学习", ["多模态"]),
]


def _locate(text, skill):
    """在文本中定位技能（大小写不敏感），返回 (start, end)。"""
    idx = text.find(skill)
    if idx >= 0:
        return idx, idx + len(skill)
    idx = text.lower().find(skill.lower())
    if idx >= 0:
        return idx, idx + len(skill)
    raise ValueError(f"技能「{skill}」不在句子「{text}」中")


def make_gold(root: Path, split_ratio: float = 0.75):
    rows = []
    for text, skills in SENTENCES:
        spans = []
        for sk in skills:
            s, e = _locate(text, sk)
            spans.append({"start": s, "end": e, "skill": text[s:e]})
        spans.sort(key=lambda x: x["start"])
        rows.append({"text": text, "spans": spans})

    n_train = int(len(rows) * split_ratio)
    out_dir = root / "data" / "gold"
    out_dir.mkdir(parents=True, exist_ok=True)
    _write(out_dir / "jd_skills_gold_train.jsonl", rows[:n_train])
    _write(out_dir / "jd_skills_gold_test.jsonl", rows[n_train:])
    _write(out_dir / "jd_skills_gold.jsonl", rows)
    print(f"gold 生成：train={n_train} test={len(rows) - n_train} total={len(rows)}")


def _write(path, rows):
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    make_gold(Path(__file__).resolve().parents[1])
