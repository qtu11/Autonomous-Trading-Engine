#!/bin/bash
# Reset and redeploy Docker backend

echo "=========================================="
echo "  ATE Trading System - Docker Reset"
echo "=========================================="

# Stop and remove existing container
echo "[1/4] Stopping existing container..."
docker stop ate-trading-backend 2>/dev/null || true
docker rm ate-trading-backend 2>/dev/null || true

# Remove old image
echo "[2/4] Removing old image..."
docker rmi ate-trading-backend:latest 2>/dev/null || true

# Build new image
echo "[3/4] Building new image..."
docker build -t ate-trading-backend:latest .

# Run new container
echo "[4/4] Starting new container..."
docker run -d \
  --name ate-trading-backend \
  -p 8848:8000 \
  -e PYTHONUNBUFFERED=1 \
  -e TRADING_MODE=paper \
  --restart unless-stopped \
  --health-cmd="curl -f http://localhost:8000/api/health || exit 1" \
  ate-trading-backend:latest

echo ""
echo "=========================================="
echo "  Deployment Complete!"
echo "=========================================="
echo ""
echo "Container: ate-trading-backend"
echo "Port: 8848 → 8000"
echo ""
echo "Commands:"
echo "  docker logs -f ate-trading-backend"
echo "  docker exec -it ate-trading-backend /bin/sh"
echo "  ./reset_docker.sh  # to redeploy"
echo ""
echo "Test API:"
echo "  curl http://localhost:8848/api/health"
echo "  curl http://localhost:8848/api/analyze/BTCUSDT"
echo ""
echo "Vercel Endpoints (after Docker is running):"
echo "  https://autonomous-trading-engine.vercel.app/backend/api/health"
echo "  https://autonomous-trading-engine.vercel.app/backend/api/analyze/BTCUSDT"
echo "=========================================="
