FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt-get/lists/*

# Copy requirements and install Python dependencies.
# BUG FIX 1: dùng dashboard/requirements.txt (đủ fastapi/httpx/pandas/numpy/uvicorn)
#   — trước đây copy requirements.txt gốc THIẾU httpx nên server.py crash khi import.
# BUG FIX 2: MetaTrader5 đã có platform marker Windows trong requirements nên pip
#   cài trên Linux (Docker) không fail — bỏ hẳn fallback "||" che lỗi thật.
COPY dashboard/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY dashboard/ ./dashboard/

EXPOSE 8005

ENV ATE_DASHBOARD_PORT=8005
ENV BRIDGE_URL=http://host.docker.internal:8007

CMD ["python", "dashboard/server.py"]
