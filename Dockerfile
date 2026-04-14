# AutoRecon v3.2
FROM python:3.12-slim

LABEL maintainer="AutoRecon Team"
LABEL version="3.2.0"
LABEL description="异步信息收集框架 - 高性能安全侦察工具"

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libssl-dev \
    libffi-dev \
    dnsutils \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 创建工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt pyproject.toml ./

# 安装 Python 依赖
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install aiohttp dnspython beautifulsoup4 lxml jinja2 aiohttp-socks tqdm pyyaml

# 复制项目文件
COPY . .

# 创建非 root 用户
RUN useradd -m -u 1000 autorecon && \
    chown -R autorecon:autorecon /app

USER autorecon

# 创建必要目录
RUN mkdir -p reports logs cache

# 默认命令
ENTRYPOINT ["python", "recon_v3.py"]
CMD ["--help"]

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 0
