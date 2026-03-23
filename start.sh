#!/bin/bash
# 启动 Streamlit（后台运行，监听 8501，basePath=/app）
streamlit run web/app.py \
  --server.port=8501 \
  --server.address=127.0.0.1 \
  --server.baseUrlPath=/app \
  --server.headless=true &

# 等待 Streamlit 就绪，避免冷启动时 Nginx 代理到未就绪的后端返回 502
echo "Waiting for Streamlit to be ready..."
for i in $(seq 1 30); do
  if curl -s -o /dev/null http://127.0.0.1:8501/app/healthz 2>/dev/null || curl -s -o /dev/null http://127.0.0.1:8501/app 2>/dev/null; then
    echo "Streamlit is ready."
    break
  fi
  sleep 1
done

# 启动 Nginx（前台运行，监听 8080）
nginx -g 'daemon off;'
