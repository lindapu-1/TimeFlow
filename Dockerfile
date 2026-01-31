FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖（用于音频处理）
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建数据目录
RUN mkdir -p data && chmod 755 data

# 暴露端口（PORT 环境变量由 Koyeb 设置）
EXPOSE 8000

# 启动应用（使用 shell 形式以支持环境变量扩展）
CMD sh -c "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"
