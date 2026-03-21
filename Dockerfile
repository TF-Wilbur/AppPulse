FROM python:3.12-slim

WORKDIR /app

# 先复制依赖声明，利用 layer 缓存
COPY pyproject.toml .

# 安装依赖（创建临时包目录让 pip 能解析 pyproject.toml）
RUN mkdir -p review_radar && \
    touch review_radar/__init__.py && \
    pip install --no-cache-dir ".[web]" && \
    rm -rf review_radar review_radar.egg-info

# 复制实际源码
COPY review_radar/ review_radar/
COPY web/ web/

# 确保 Python 能找到 /app 下的包
ENV PYTHONPATH=/app

# Streamlit 配置
RUN mkdir -p /root/.streamlit
COPY .streamlit/config.toml /root/.streamlit/config.toml

EXPOSE 8080

CMD ["streamlit", "run", "web/app.py", "--server.port=8080", "--server.address=0.0.0.0"]
