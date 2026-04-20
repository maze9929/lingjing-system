# 灵境决策系统 - 微信云托管 Dockerfile
FROM python:3.10-slim

ENV APP_HOME /app
WORKDIR $APP_HOME

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 确保数据目录和证书目录存在（云托管需要）
RUN mkdir -p /app/data/ledgers /app/data/cases /app/data/rules /app/cert

# 暴露端口（云托管默认 80）
EXPOSE 80

# 启动服务
CMD exec gunicorn --bind :80 --workers 1 --threads 4 --timeout 120 app:app
