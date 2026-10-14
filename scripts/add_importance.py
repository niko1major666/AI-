"""给 skill_taxonomy.yaml 批量补充 importance（行业重要程度 1-5）。

依据：
- Stack Overflow 2025 开发者调查（语言热度：Python 57.9%、SQL 58.6%、C++ 23.5% 等）
- 2025-2026 AI 大模型岗位需求共识（LLM/RAG/Agent/微调为最热方向）

importance 语义：5=行业核心必备，4=热门，3=一般，2=较冷门，1=小众/过时。
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "kb" / "skill_taxonomy.yaml"

# 类别默认重要度
CAT_DEFAULT = {"PROG": 3, "FRAMEWORK": 4, "ML": 3, "AITECH": 4, "BIGDATA": 3, "ENGINEERING": 3}

# 覆盖映射（热点上调、冷门下调）
IMPORTANCE = {
    # 编程语言
    "PROG.PYTHON": 5, "PROG.SQL": 4, "PROG.CPP": 3, "PROG.SHELL": 3,
    "PROG.GO": 2, "PROG.C": 2, "PROG.JAVA": 2, "PROG.JS": 2, "PROG.RUST": 2,
    "PROG.R": 2, "PROG.MATLAB": 1, "PROG.SCALA": 1, "PROG.CSHARP": 1,
    # 深度学习框架
    "FRAMEWORK.PYTORCH": 5, "FRAMEWORK.HF": 4, "FRAMEWORK.SKLEARN": 4,
    "FRAMEWORK.LANGCHAIN": 4, "FRAMEWORK.TENSORFLOW": 3, "FRAMEWORK.LLAMAINDEX": 3,
    "FRAMEWORK.DEEPSPEED": 3, "FRAMEWORK.VLLM": 3, "FRAMEWORK.KERAS": 2,
    "FRAMEWORK.PADDLE": 2, "FRAMEWORK.MINDSPORE": 2, "FRAMEWORK.JAX": 2,
    "FRAMEWORK.MEGATRON": 2, "FRAMEWORK.TENSORRT": 2, "FRAMEWORK.ONNX": 2,
    # 机器学习算法
    "ML.DL": 5, "ML.TRANSFORMER": 5, "ML.CORE": 4, "ML.ATTENTION": 4,
    "ML.MULTIMODAL": 4, "ML.NLP": 4, "ML.CV": 3, "ML.RL": 3, "ML.REC": 3,
    "ML.ASR": 3, "ML.NN": 3, "ML.CNN": 3, "ML.QUANT": 3, "ML.COMPRESS": 3,
    "ML.RNN": 2, "ML.LSTM": 2, "ML.GAN": 2, "ML.TRANSFER": 2, "ML.SELFSUP": 2,
    "ML.CONTRAST": 2, "ML.GNN": 2, "ML.OD": 2, "ML.SEG": 2, "ML.TS": 2,
    "ML.ANOMALY": 2, "ML.FED": 1, "ML.DISTILL": 2, "ML.HPT": 2,
    # AI 专有技术
    "AITECH.LLM": 5, "AITECH.RAG": 5, "AITECH.AGENT": 5,
    "AITECH.VECTORDB": 4, "AITECH.FINETUNE": 4, "AITECH.LORA": 4,
    "AITECH.PROMPT": 4, "AITECH.DISTRIBUTED": 4, "AITECH.EMBEDDING": 4,
    "AITECH.AIGC": 4, "AITECH.INFER_ACC": 3, "AITECH.DEPLOY": 3,
    "AITECH.T2I": 3, "AITECH.RLHF": 3, "AITECH.ICL": 3, "AITECH.COT": 3,
    "AITECH.MOE": 3, "AITECH.SEMSEARCH": 3, "AITECH.TEXTVEC": 3, "AITECH.SERVING": 3,
    "AITECH.KG": 2, "AITECH.ANNOTATE": 1, "AITECH.TOKENIZER": 2, "AITECH.DIALOG": 2,
    "AITECH.MONITOR": 2, "AITECH.AUG": 2, "AITECH.ZEROSHOT": 2, "AITECH.FEWSHOT": 2,
    # 大数据
    "BIGDATA.PANDAS": 4, "BIGDATA.NUMPY": 4, "BIGDATA.CLEAN": 4, "BIGDATA.FE": 4,
    "BIGDATA.DATASCIENCE": 4, "BIGDATA.DATAENG": 4,
    "BIGDATA.SPARK": 3, "BIGDATA.FLINK": 3, "BIGDATA.KAFKA": 3, "BIGDATA.DW": 3,
    "BIGDATA.ETL": 3, "BIGDATA.SQLTUNE": 3, "BIGDATA.MINING": 3, "BIGDATA.VIZ": 3,
    "BIGDATA.AIRFLOW": 3, "BIGDATA.PIPELINE": 3,
    "BIGDATA.HADOOP": 2, "BIGDATA.HIVE": 2, "BIGDATA.LAKE": 2, "BIGDATA.FS": 2,
    "BIGDATA.STREAM": 2, "BIGDATA.DBT": 2, "BIGDATA.DATABRICKS": 2, "BIGDATA.SNOWFLAKE": 2,
    "BIGDATA.BIGQUERY": 2, "BIGDATA.NOSQL": 2,
    # 工程
    "ENGINEERING.LINUX": 4, "ENGINEERING.DOCKER": 4, "ENGINEERING.GIT": 4,
    "ENGINEERING.CLOUD": 4, "ENGINEERING.MLOPS": 4,
    "ENGINEERING.K8S": 3, "ENGINEERING.CICD": 3, "ENGINEERING.AWS": 3,
    "ENGINEERING.CUDA": 3, "ENGINEERING.REDIS": 3, "ENGINEERING.MYSQL": 3,
    "ENGINEERING.DEVOPS": 3, "ENGINEERING.FASTAPI": 3, "ENGINEERING.FLASK": 3, "ENGINEERING.DJANGO": 3,
    "ENGINEERING.ALIYUN": 2, "ENGINEERING.HUAWEICLOUD": 2, "ENGINEERING.MLFLOW": 2,
    "ENGINEERING.DVC": 2, "ENGINEERING.EXPTRACK": 2, "ENGINEERING.GRPC": 2, "ENGINEERING.REST": 2,
    "ENGINEERING.MICROSVC": 2, "ENGINEERING.UNITTEST": 2, "ENGINEERING.HPC": 2,
    "ENGINEERING.PARALLEL": 2, "ENGINEERING.MEMOPT": 2, "ENGINEERING.DISTSTORAGE": 2,
    "ENGINEERING.ES": 2, "ENGINEERING.GRAPHDB": 2, "ENGINEERING.TERRAFORM": 2,
    "ENGINEERING.AZURE": 2, "ENGINEERING.GCP": 2, "ENGINEERING.SERVERLESS": 1,
    "ENGINEERING.REACT": 1, "ENGINEERING.VUE": 1, "ENGINEERING.NODEJS": 1,
}


def main() -> int:
    text = PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    out = []
    changed = 0
    for line in lines:
        if "difficulty:" in line and ", importance:" not in line:
            m = re.search(r"id:\s*([A-Z]+\.[A-Z_0-9]+)", line)
            if m:
                sid = m.group(1)
                cat = sid.split(".")[0]
                imp = IMPORTANCE.get(sid, CAT_DEFAULT.get(cat, 3))
                line = re.sub(
                    r"difficulty:\s*(\d)(\s*\})",
                    lambda mm: f"difficulty: {mm.group(1)}, importance: {imp}{mm.group(2)}",
                    line,
                )
                changed += 1
        out.append(line)
    PATH.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"已为 {changed} 个技能补充 importance → {PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
