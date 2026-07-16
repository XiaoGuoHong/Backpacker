# SmartVoyage Dockerfile
# 多阶段构建：构建前端 → Python 后端

# ── 阶段 1: 前端构建 ──
FROM node:22-alpine AS web-builder
WORKDIR /app/web
COPY web/package.json web/package-lock.json* ./
RUN npm install
COPY web/ ./
RUN npm run build

# ── 阶段 2: 后端运行 ──
FROM python:3.12-slim
WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码
COPY app/ ./app/
COPY tests/ ./tests/

# 前端构建产物
COPY --from=web-builder /app/web/dist ./web/dist

# 环境变量默认值
ENV WEATHER_SOURCE=demo
ENV MCP_TRANSPORT=in-process
ENV ENV=production

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
