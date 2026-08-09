"""Structured, JSON-per-line logging for the GoldQuant AI platform.

Every operational event across the system (app lifecycle, MT5 bridge, AI
decisions, risk gate, order execution, latency) is emitted as a single JSON
object per line so logs can be tailed, grepped, and shipped to a log aggregator
without parsing ambiguity.

Usage:
    from logging_config import log_event, LogEvent, timed

    log_event(LogEvent.APP_STARTED, component="backend", port=8005)
    with timed(LogEvent.TRADE_LATENCY, component="ea-bridge"):
        ...  # block whose duration is recorded as latency_ms
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


class LogEvent:
    """Canonical event names required by the product requirements."""

    # Lifecycle
    APP_STARTED = "APP_STARTED"
    APP_STOPPED = "APP_STOPPED"
    API_CONNECTED = "API_CONNECTED"
    DB_CONNECTED = "DB_CONNECTED"

    # WebSocket
    WS_CONNECTED = "WS_CONNECTED"
    WS_DISCONNECTED = "WS_DISCONNECTED"
    WS_BROADCAST = "WS_BROADCAST"

    # MT5 / EA bridge
    MT5_CONNECTED = "MT5_CONNECTED"
    MT5_DISCONNECTED = "MT5_DISCONNECTED"
    MT5_RECONNECT = "MT5_RECONNECT"
    EA_LOADED = "EA_LOADED"
    EA_HEARTBEAT = "EA_HEARTBEAT"
    RECONNECT = "RECONNECT"
    TIMEOUT = "TIMEOUT"

    # AI decision pipeline
    AI_REQUEST = "AI_REQUEST"
    AI_RESPONSE = "AI_RESPONSE"
    SIGNAL_GENERATED = "SIGNAL_GENERATED"

    # Risk gate
    RISK_APPROVED = "RISK_APPROVED"
    RISK_REJECTED = "RISK_REJECTED"

    # Order lifecycle
    ORDER_SENT = "ORDER_SENT"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_FAILED = "ORDER_FAILED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    SL_MODIFIED = "SL_MODIFIED"
    TP_MODIFIED = "TP_MODIFIED"
    POSITION_CLOSED = "POSITION_CLOSED"
    COMMAND_CLAIMED = "COMMAND_CLAIMED"
    COMMAND_RECEIPT = "COMMAND_RECEIPT"

    # News / calendar
    CALENDAR_UPDATED = "CALENDAR_UPDATED"

    # AI brain (decision memory + self-evaluation)
    BRAIN_DECISION_RECORDED = "BRAIN_DECISION_RECORDED"
    BRAIN_EVALUATED = "BRAIN_EVALUATED"
    BRAIN_ADJUST_PROPOSED = "BRAIN_ADJUST_PROPOSED"

    # Diagnostics
    EXCEPTION = "EXCEPTION"
    WARNING = "WARNING"
    INFO = "INFO"
    PERF_CPU = "PERF_CPU"
    PERF_MEM = "PERF_MEM"
    PERF_NET = "PERF_NET"
    TRADE_LATENCY = "TRADE_LATENCY"

    # Authentication / security
    OPERATOR_AUTHENTICATED = "OPERATOR_AUTHENTICATED"
    SECURITY_ALERT = "SECURITY_ALERT"


_LOGGER_NAME = "ate"
_DEFAULT_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_configured = False


def _log_directory() -> Path:
    override = os.getenv("ATE_LOG_DIR")
    directory = Path(override) if override else _DEFAULT_LOG_DIR
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime,)):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    if isinstance(value, BaseException):
        return f"{type(value).__name__}: {value}"
    try:
        return str(value)
    except Exception:  # pragma: no cover - defensive
        return "<unserializable>"


class _JsonFormatter(logging.Formatter):
    """Render each record as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "event": getattr(record, "event", record.getMessage()),
            "component": getattr(record, "component", record.name),
        }
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=_json_default, ensure_ascii=False)


def get_logger() -> logging.Logger:
    """Return the shared configured logger (idempotent setup)."""
    global _configured
    logger = logging.getLogger(_LOGGER_NAME)
    if _configured:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    formatter = _JsonFormatter()

    log_file = _log_directory() / f"ate_{datetime.now(timezone.utc):%Y%m%d}.log"
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=7, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    _configured = True
    return logger


def log_event(
    event: str,
    *,
    component: str = "backend",
    level: int = logging.INFO,
    exc: BaseException | None = None,
    **fields: Any,
) -> None:
    """Emit one structured event line."""
    logger = get_logger()
    record_extra = {"event": event, "component": component, "fields": fields}
    logger.log(level, event, extra=record_extra, exc_info=exc)


@contextmanager
def timed(event: str, *, component: str = "backend", **fields: Any) -> Iterator[None]:
    """Measure a block and emit its duration as latency_ms on exit."""
    start = time.perf_counter()
    try:
        yield
    finally:
        latency_ms = round((time.perf_counter() - start) * 1000.0, 3)
        log_event(event, component=component, latency_ms=latency_ms, **fields)


def read_recent_logs(limit: int = 200, level: str | None = None) -> list[dict[str, Any]]:
    """Tail the current day's log file, newest last, optionally filtered by level."""
    log_file = _log_directory() / f"ate_{datetime.now(timezone.utc):%Y%m%d}.log"
    if not log_file.is_file():
        return []
    limit = max(1, min(limit, 2000))
    try:
        with open(log_file, encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError:
        return []

    wanted = level.upper() if level else None
    parsed: list[dict[str, Any]] = []
    for raw in lines[-limit * 4 :]:  # over-read to survive filter shrinkage
        raw = raw.strip()
        if not raw:
            continue
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if wanted and str(entry.get("level", "")).upper() != wanted:
            continue
        parsed.append(entry)
    return parsed[-limit:]
