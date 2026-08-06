# FastAPI Backend Dockerfile
FROM python:3.11-slim AS base

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt || true

# Install additional dependencies for production
RUN pip install --no-cache-dir \
    psycopg2-binary \
    redis \
    python-multipart \
    python-jose[cryptography] \
    passlib[bcrypt] \
    httpx \
    aiofiles

# Copy application code
COPY . .

# Create non-root user
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --gid 1001 appuser && \
    chown -R appuser:appgroup /app

USER appuser

EXPOSE 8005

ENV PYTHONUNBUFFERED=1
ENV QUANTAI_DASHBOARD_PORT=8005
ENV QUANTAI_DASHBOARD_HOST=0.0.0.0

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8005/health || exit 1

CMD ["python", "server.py"]