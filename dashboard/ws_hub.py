"""WebSocket connection manager for realtime dashboard streaming.

A single process-local hub tracks every connected dashboard client and fans out
telemetry, log, command, and AI-signal events. The broadcaster lives in
``server.py``; this module only owns the connection set and safe send logic.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Set

from fastapi import WebSocket

from logging_config import LogEvent, log_event


class ConnectionManager:
    """Track active WebSocket clients and broadcast JSON events to them."""

    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    @property
    def count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)
        log_event(LogEvent.WS_CONNECTED, component="ws-hub", clients=self.count)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)
        log_event(LogEvent.WS_DISCONNECTED, component="ws-hub", clients=self.count)

    async def send_to(self, websocket: WebSocket, message: dict[str, Any]) -> bool:
        try:
            await websocket.send_text(json.dumps(message, default=str))
            return True
        except Exception:
            return False

    async def broadcast(self, message: dict[str, Any]) -> int:
        """Send to all clients; prune dead ones. Returns number of live clients."""
        if not self._connections:
            return 0
        text = json.dumps(message, default=str)
        async with self._lock:
            targets = list(self._connections)
        delivered = 0
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_text(text)
                delivered += 1
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections.discard(ws)
        return delivered


# Shared singleton used by the FastAPI app.
WS_MANAGER = ConnectionManager()
