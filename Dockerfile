# 量化轮动系统 Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libblas-dev \
    liblapack-dev \
    libatlas-base-dev \
    gfortran \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements-lock.txt requirements.txt ./

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements-lock.txt

# 复制源代码
COPY . .

# 安装项目本身
RUN pip install -e .

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 默认命令
CMD ["python", "scripts/daily_run_baostock.py"]
