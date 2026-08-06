# AI Engine Dockerfile
FROM python:3.11-slim AS base

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt || true

# Install AI/ML dependencies
RUN pip install --no-cache-dir \
    openai \
    google-generativeai \
    anthropic \
    redis \
    httpx \
    aiofiles \
    pydantic \
    pydantic-settings

# Copy application code
COPY . .

# Create non-root user
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --gid 1001 appuser && \
    chown -R appuser:appgroup /app

USER appuser

EXPOSE 8006

ENV PYTHONUNBUFFERED=1
ENV AI_ENGINE_PORT=8006

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8006/health || exit 1

CMD ["python", "-m", "ai_engine.main"]