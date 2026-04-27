FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖（Chroma 和网页抓取需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码和数据
COPY src/ ./src/
COPY data/ ./data/
COPY recipe_db/ ./recipe_db/

# 创建用户记忆存储目录（用 volume 挂载覆盖）
RUN mkdir -p /app/users_history

# .env 由 docker-compose 的环境变量或 volume 挂载提供
ENV PYTHONPATH=/app/src
