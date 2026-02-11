FROM python:3.11-slim

WORKDIR /app

# 使用阿里云 pip 镜像加速
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip config set global.trusted-host mirrors.aliyun.com

# 安装依赖
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn[standard] \
    tortoise-orm \
    aiosqlite \
    passlib[bcrypt] \
    python-jose[cryptography] \
    python-multipart \
    openpyxl \
    pandas \
    httpx

# 复制应用文件
COPY main.py .
COPY index.html .

# 创建数据目录
RUN mkdir -p /app/data

# 暴露端口
EXPOSE 8000

# 设置环境变量
ENV DATABASE_URL=sqlite:///app/data/erp.db
ENV SECRET_KEY=

# 直接用 uvicorn 启动，模块名固定为 main
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
