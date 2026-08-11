#!/bin/bash
# Deploy Trading System to Docker

set -e

echo "=============================================="
echo "  Trading System Docker Deployment"
echo "=============================================="

# Build Docker image
echo "[1/3] Building Docker image..."
docker build -t trading-backend:latest .

# Stop existing container (if any)
echo "[2/3] Stopping existing container..."
docker stop trading-backend || true
docker rm trading-backend || true

# Run new container
echo "[3/3] Starting new container..."
docker run -d \
  --name trading-backend \
  -p 8848:8000 \
  -e PYTHONUNBUFFERED=1 \
  -e TRADING_MODE=paper \
  --restart unless-stopped \
  --health-cmd="curl -f http://localhost:8000/api/health || exit 1" \
  --health-interval=30s \
  --health-timeout=10s \
  --health-retries=3 \
  trading-backend:latest

echo ""
echo "=============================================="
echo "  Deployment Complete!"
echo "=============================================="
echo ""
echo "Backend running at: http://0.0.0.0:8848"
echo "Health check: http://0.0.0.0:8848/api/health"
echo ""
echo "Useful commands:"
echo "  docker logs -f trading-backend   # View logs"
echo "  docker exec -it trading-backend sh  # Shell into container"
echo "  docker stop trading-backend       # Stop"
echo "=============================================="
