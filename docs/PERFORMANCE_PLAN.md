# QuantAI Performance Optimization Plan

## Latency & Throughput Targets

- **MT5 Tick Ingestion to AI Decision Latency**: `< 15ms`
- **FastAPI Command Issuance Latency**: `< 5ms`
- **MQL5 EA Poll Cycle**: `1000ms` (1 second timer)
- **WebSocket Broadcast Cadence**: `1000ms`
- **Next.js Dashboard Re-render Efficiency**: `60 FPS` SVG chart rendering with zero main thread blocking.

## Backend Optimization Strategies
1. **SQLite WAL Mode**: Ensures non-blocking concurrent reads while commands/events are written under `BEGIN IMMEDIATE` locks.
2. **In-Memory Caching**: Market indicators and telemetry computed once per tick/request and broadcasted over WebSocket to avoid redundant DB or MT5 queries.
3. **AsyncIO Non-blocking I/O**: Lifespan managed background tasks for broadcasting and decision loops.

## Frontend Optimization Strategies
1. **WebSocket Telemetry Stream**: Reduces HTTP polling overhead from 1s fetch intervals to single persistent WS connection.
2. **Lightweight SVG Chart Canvas**: Custom optimized SVG chart component handling up to 2000 candles with mouse wheel zoom and drag panning.
3. **React `memo` & `useCallback`**: Prevents unnecessary re-renders of control center panels and status indicators.
