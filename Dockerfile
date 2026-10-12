# AI 岗位技能差距分析系统
# 说明：模型权重（models/）通过 volume 挂载复用宿主，不打进镜像，避免镜像过大
FROM python:3.12-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# 先装依赖（利用 Docker 层缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制代码与数据（不含 models，运行时挂载）
COPY src ./src
COPY configs ./configs
COPY scripts ./scripts
COPY data ./data
COPY README.md .

# 缓存全部落在 /app/models（挂载）
ENV HF_ENDPOINT=https://hf-mirror.com
ENV HF_HOME=/app/models/hf_cache
ENV MODELSCOPE_CACHE=/app/models/ms_cache
ENV TRANSFORMERS_CACHE=/app/models/hf_cache
ENV STREAMLIT_SERVER_HEADLESS=true

EXPOSE 8501

CMD ["streamlit", "run", "src/app/app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
