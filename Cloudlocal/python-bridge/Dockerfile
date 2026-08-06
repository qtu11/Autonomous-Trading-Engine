# Python Bridge to MT5 Dockerfile
FROM python:3.11-slim AS base

# Gateway container: serves /health + bridge HTTP API only.
# Actual MT5 execution is done by the MQL5 EA (QuantAI_XAUUSD.mq5) on Windows host,
# so wine is not needed here (and wine32 is unavailable on bookworm/trixie).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt || true

# Install bridge dependencies
# NOTE: MetaTrader5 pip package is Windows-only and cannot build on Linux;
# bridge/main.py already falls back to HAS_MT5=False and runs as HTTP/health gateway.
RUN pip install --no-cache-dir \
    redis \
    httpx \
    aiofiles \
    pydantic \
    python-dotenv

# Copy application code
COPY . .

# Create non-root user
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --gid 1001 appuser && \
    chown -R appuser:appgroup /app

USER appuser

EXPOSE 8007

ENV PYTHONUNBUFFERED=1
ENV BRIDGE_PORT=8007

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8007/health || exit 1

CMD ["python", "-m", "bridge.main"]