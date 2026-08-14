# =======================================================================
# Dockerfile for ATE FastAPI Backend (VPS Linux deployment)
# Python 3.11 + FastAPI + Gunicorn/Uvicorn
# Works on: Ubuntu 22.04, Debian 12, CentOS Stream 9, Alpine 3.18
# =======================================================================

FROM python:3.11-slim AS base

# Environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8848

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      curl \
      ca-certificates \
      libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies first (cache layer)
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Non-root user for safety
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --gid 1001 appuser && \
    chown -R appuser:appgroup /app
USER appuser

EXPOSE 8848

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -fsS http://localhost:8848/health || exit 1

# Run gunicorn with uvicorn workers
# workers = 2 (each 4 threads) — fits small VPS, scales up to 4 on 2GB+ RAM
CMD ["gunicorn", "server:app", \
     "--bind", "0.0.0.0:8848", \
     "--workers", "2", \
     "--threads", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--timeout", "60", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]