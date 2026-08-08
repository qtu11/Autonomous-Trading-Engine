# =======================================================================
# Dockerfile - Trading System (Dockerlocal)
# 
# This is the MAIN Dockerfile for deploying the Trading System
# Usage: docker build -t trading-system -f Dockerfile .
#        docker run -p 8005:8005 --env-file .env trading-system
#
# URL Structure (Dockerlocal):
#   Website : http://localhost/
#   Backend : http://localhost/backend
#   API/v1  : http://localhost/api/v1
# =======================================================================

FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    QUANTAI_DASHBOARD_PORT=8005 \
    QUANTAI_DASHBOARD_HOST=0.0.0.0

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt || true

# Install additional production dependencies
RUN pip install --no-cache-dir \
    psycopg2-binary \
    redis \
    python-multipart \
    python-jose[cryptography] \
    passlib[bcrypt] \
    httpx \
    aiofiles \
    gunicorn

# Copy application code
COPY . .

# Create non-root user for security
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --gid 1001 appuser && \
    chown -R appuser:appgroup /app

USER appuser

# Expose port
EXPOSE 8005

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8005/health || exit 1

# Default command - run with uvicorn
CMD ["python", "server.py"]
