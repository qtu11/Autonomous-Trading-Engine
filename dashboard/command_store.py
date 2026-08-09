"""Persistent, idempotent command ledger for the local ATE bridge."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

TERMINAL_STATES = {"EXECUTED", "REJECTED", "FAILED", "EXPIRED"}


class CommandStore:
    """SQLite-backed command lifecycle with atomic claims and receipts."""

    def __init__(self, database_path: str) -> None:
        self._database_path = Path(database_path)
        self._lock = threading.RLock()
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._database_path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._lock, self._connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS execution_commands (
                    command_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    action TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    magic INTEGER NOT NULL,
                    volume REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    reason TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    claimed_by TEXT,
                    claimed_at TEXT,
                    lease_expires_at TEXT,
                    executed_at TEXT,
                    order_ticket INTEGER,
                    deal_ticket INTEGER,
                    retcode INTEGER,
                    result_message TEXT,
                    receipt_id TEXT UNIQUE
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS execution_events (
                    event_id TEXT PRIMARY KEY,
                    command_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY(command_id) REFERENCES execution_commands(command_id)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_commands_claim ON execution_commands (state, symbol, magic, expires_at)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_commands_idempotency ON execution_commands (idempotency_key)"
            )

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _timestamp(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _row_to_command(row: sqlite3.Row) -> dict[str, Any]:
        command = dict(row)
        for field in ("volume", "stop_loss", "take_profit"):
            if command[field] is not None:
                command[field] = float(command[field])
        return command

    @staticmethod
    def _record_event(
        connection: sqlite3.Connection,
        command_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT INTO execution_events (event_id, command_id, event_type, created_at, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                command_id,
                event_type,
                CommandStore._timestamp(CommandStore._utc_now()),
                json.dumps(payload, separators=(",", ":"), sort_keys=True),
            ),
        )

    def create_command(
        self,
        *,
        idempotency_key: str,
        action: str,
        symbol: str,
        magic: int,
        volume: float | None,
        stop_loss: float | None,
        take_profit: float | None,
        reason: str,
        ttl_seconds: int = 30,
    ) -> dict[str, Any]:
        """Create a command once; retries with the same key return the original."""
        now = self._utc_now()
        command_id = str(uuid.uuid4())
        expires_at = now + timedelta(seconds=ttl_seconds)
        with self._lock, self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM execution_commands WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing is not None:
                connection.execute("COMMIT")
                return self._row_to_command(existing)
            connection.execute(
                """
                INSERT INTO execution_commands (
                    command_id, idempotency_key, action, symbol, magic, volume,
                    stop_loss, take_profit, reason, state, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
                """,
                (
                    command_id,
                    idempotency_key,
                    action,
                    symbol,
                    magic,
                    volume,
                    stop_loss,
                    take_profit,
                    reason,
                    self._timestamp(now),
                    self._timestamp(expires_at),
                ),
            )
            self._record_event(
                connection,
                command_id,
                "CREATED",
                {"idempotency_key": idempotency_key, "action": action},
            )
            row = connection.execute(
                "SELECT * FROM execution_commands WHERE command_id = ?", (command_id,)
            ).fetchone()
            connection.execute("COMMIT")
            return self._row_to_command(row)

    def claim_next(
        self,
        *,
        executor_id: str,
        symbol: str,
        magic: int,
        lease_seconds: int = 15,
    ) -> dict[str, Any] | None:
        """Atomically lease one pending command for a matching EA executor."""
        now = self._utc_now()
        now_text = self._timestamp(now)
        lease_text = self._timestamp(now + timedelta(seconds=lease_seconds))
        with self._lock, self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE execution_commands
                SET state = 'PENDING', claimed_by = NULL, claimed_at = NULL, lease_expires_at = NULL
                WHERE state = 'CLAIMED' AND lease_expires_at < ?
                """,
                (now_text,),
            )
            connection.execute(
                """
                UPDATE execution_commands SET state = 'EXPIRED'
                WHERE state = 'PENDING' AND expires_at < ?
                """,
                (now_text,),
            )
            row = connection.execute(
                """
                SELECT * FROM execution_commands
                WHERE state = 'PENDING' AND symbol = ? AND magic = ? AND expires_at >= ?
                ORDER BY created_at ASC LIMIT 1
                """,
                (symbol, magic, now_text),
            ).fetchone()
            if row is None:
                connection.execute("COMMIT")
                return None
            connection.execute(
                """
                UPDATE execution_commands
                SET state = 'CLAIMED', claimed_by = ?, claimed_at = ?, lease_expires_at = ?
                WHERE command_id = ? AND state = 'PENDING'
                """,
                (executor_id, now_text, lease_text, row["command_id"]),
            )
            claimed = connection.execute(
                "SELECT * FROM execution_commands WHERE command_id = ?", (row["command_id"],)
            ).fetchone()
            self._record_event(
                connection,
                row["command_id"],
                "CLAIMED",
                {"executor_id": executor_id, "lease_expires_at": lease_text},
            )
            connection.execute("COMMIT")
            return self._row_to_command(claimed)

    def record_receipt(
        self,
        *,
        command_id: str,
        executor_id: str,
        receipt_id: str,
        status: str,
        retcode: int | None,
        result_message: str,
        order_ticket: int | None = None,
        deal_ticket: int | None = None,
    ) -> dict[str, Any] | None:
        """Store an EA receipt once; terminal receipts are safe to retry."""
        if status not in {"EXECUTED", "REJECTED", "FAILED"}:
            raise ValueError("Unsupported receipt status")
        now_text = self._timestamp(self._utc_now())
        with self._lock, self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM execution_commands WHERE command_id = ?", (command_id,)
            ).fetchone()
            if row is None:
                connection.execute("COMMIT")
                return None
            if row["receipt_id"] == receipt_id or row["state"] in TERMINAL_STATES:
                connection.execute("COMMIT")
                return self._row_to_command(row)
            if row["claimed_by"] != executor_id:
                connection.execute("ROLLBACK")
                raise PermissionError("Receipt executor does not own this command")
            connection.execute(
                """
                UPDATE execution_commands
                SET state = ?, executed_at = ?, order_ticket = ?, deal_ticket = ?,
                    retcode = ?, result_message = ?, receipt_id = ?
                WHERE command_id = ?
                """,
                (
                    status,
                    now_text,
                    order_ticket,
                    deal_ticket,
                    retcode,
                    result_message,
                    receipt_id,
                    command_id,
                ),
            )
            self._record_event(
                connection,
                command_id,
                "RECEIPT",
                {
                    "executor_id": executor_id,
                    "receipt_id": receipt_id,
                    "status": status,
                    "retcode": retcode,
                },
            )
            updated = connection.execute(
                "SELECT * FROM execution_commands WHERE command_id = ?", (command_id,)
            ).fetchone()
            connection.execute("COMMIT")
            return self._row_to_command(updated)

    def get_command(self, command_id: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM execution_commands WHERE command_id = ?", (command_id,)
            ).fetchone()
            return self._row_to_command(row) if row else None

    def diagnostic_summary(self) -> dict[str, Any]:
        """Return aggregate lifecycle data without command payloads or identifiers."""
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT state, COUNT(*) AS count FROM execution_commands GROUP BY state"
            ).fetchall()
            latest = connection.execute(
                "SELECT state, created_at, claimed_at, executed_at, retcode FROM execution_commands "
                "ORDER BY COALESCE(executed_at, claimed_at, created_at) DESC LIMIT 1"
            ).fetchone()
        counts = {row["state"]: int(row["count"]) for row in rows}
        return {
            "available": True,
            "counts": counts,
            "last_command": dict(latest) if latest else None,
        }
