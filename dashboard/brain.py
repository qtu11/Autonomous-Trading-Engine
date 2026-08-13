"""AI Central Brain: persistent decision memory, self-evaluation, and strategy stats.

Every AI decision (trade or abstain) is recorded here with its full reasoning
context. Closed positions are matched back to the originating decision and
evaluated (net PnL, R-multiple, win/loss). Rolling strategy statistics feed an
optional auto-adjust engine that proposes parameter changes instead of
silently mutating live configuration.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BrainStore:
    """SQLite-backed memory for the AI decision lifecycle."""

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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS brain_decisions (
                    decision_id TEXT PRIMARY KEY,
                    ts TEXT NOT NULL,
                    strategy_version TEXT NOT NULL,
                    trading_method TEXT NOT NULL DEFAULT 'INDICATOR',
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    action TEXT NOT NULL,
                    confidence INTEGER NOT NULL,
                    entry REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    volume REAL,
                    reason_codes_json TEXT NOT NULL,
                    indicators_json TEXT NOT NULL,
                    account_json TEXT NOT NULL,
                    context_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    command_id TEXT,
                    order_ticket INTEGER,
                    decision_detail TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS brain_evaluations (
                    evaluation_id TEXT PRIMARY KEY,
                    decision_id TEXT NOT NULL,
                    order_ticket INTEGER NOT NULL,
                    closed_at TEXT NOT NULL,
                    exit_price REAL NOT NULL,
                    net_profit REAL NOT NULL,
                    r_multiple REAL NOT NULL,
                    outcome TEXT NOT NULL,
                    exit_reason TEXT NOT NULL,
                    lesson TEXT,
                    UNIQUE(decision_id, order_ticket)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS strategy_stats (
                    strategy_version TEXT NOT NULL,
                    trading_method TEXT NOT NULL DEFAULT 'INDICATOR',
                    status TEXT NOT NULL,
                    params_json TEXT NOT NULL,
                    sample_size INTEGER NOT NULL DEFAULT 0,
                    wins INTEGER NOT NULL DEFAULT 0,
                    losses INTEGER NOT NULL DEFAULT 0,
                    breakevens INTEGER NOT NULL DEFAULT 0,
                    win_rate REAL,
                    profit_factor REAL,
                    total_pnl REAL NOT NULL DEFAULT 0,
                    avg_r REAL,
                    updated_at TEXT NOT NULL,
                    notes TEXT,
                    PRIMARY KEY (strategy_version, trading_method)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS brain_adjustments (
                    adjustment_id TEXT PRIMARY KEY,
                    ts TEXT NOT NULL,
                    strategy_version TEXT NOT NULL,
                    window_json TEXT NOT NULL,
                    proposed_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    applied_at TEXT,
                    result TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_decisions_ts ON brain_decisions (ts)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_decisions_ticket ON brain_decisions (order_ticket)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_decisions_status ON brain_decisions (status)"
            )

    # ── Record ────────────────────────────────────────────────────────────────

    def record_decision(
        self,
        *,
        strategy_version: str,
        trading_method: str = "INDICATOR",
        symbol: str,
        timeframe: str,
        action: str,
        confidence: int,
        entry: float | None,
        stop_loss: float | None,
        take_profit: float | None,
        volume: float | None,
        reason_codes: list[str],
        indicators: dict[str, Any],
        account: dict[str, Any],
        context: dict[str, Any],
        status: str,
        command_id: str | None = None,
        order_ticket: int | None = None,
        decision_detail: str = "",
    ) -> str:
        decision_id = "dec-" + uuid.uuid4().hex[:12]
        with self._lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO brain_decisions (
                    decision_id, ts, strategy_version, trading_method, symbol, timeframe, action,
                    confidence, entry, stop_loss, take_profit, volume,
                    reason_codes_json, indicators_json, account_json, context_json,
                    status, command_id, order_ticket, decision_detail
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision_id, _now_iso(), strategy_version, trading_method, symbol, timeframe, action,
                    int(confidence), entry, stop_loss, take_profit, volume,
                    json.dumps(reason_codes, ensure_ascii=False),
                    json.dumps(indicators, ensure_ascii=False, default=str),
                    json.dumps(account, ensure_ascii=False, default=str),
                    json.dumps(context, ensure_ascii=False, default=str),
                    status, command_id, order_ticket, decision_detail,
                ),
            )
        return decision_id

    def link_execution(self, *, command_id: str, order_ticket: int | None) -> None:
        with self._lock, self._connection() as connection:
            connection.execute(
                "UPDATE brain_decisions SET status='EXECUTED', order_ticket=? WHERE command_id=? AND status IN ('ISSUED','EXECUTED')",
                (order_ticket, command_id),
            )

    def mark_closed(self, decision_id: str, status: str = "CLOSED") -> None:
        with self._lock, self._connection() as connection:
            connection.execute(
                "UPDATE brain_decisions SET status=? WHERE decision_id=?",
                (status, decision_id),
            )

    # ── Self-evaluation ───────────────────────────────────────────────────────

    def pending_executed_decisions(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                """
                SELECT decision_id, order_ticket, entry, stop_loss, volume, action
                FROM brain_decisions
                WHERE status = 'EXECUTED' AND order_ticket IS NOT NULL
                ORDER BY ts DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def evaluate(
        self,
        *,
        decision_id: str,
        order_ticket: int,
        closed_at: str,
        exit_price: float,
        net_profit: float,
        r_multiple: float,
        outcome: str,
        exit_reason: str,
        lesson: str,
    ) -> str | None:
        if outcome == "WIN":
            delta_wins, delta_losses, delta_be = 1, 0, 0
        elif outcome == "LOSS":
            delta_wins, delta_losses, delta_be = 0, 1, 0
        else:
            delta_wins, delta_losses, delta_be = 0, 0, 1
        evaluation_id = "ev-" + uuid.uuid4().hex[:12]
        with self._lock, self._connection() as connection:
            try:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO brain_evaluations (
                        evaluation_id, decision_id, order_ticket, closed_at,
                        exit_price, net_profit, r_multiple, outcome, exit_reason, lesson
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        evaluation_id, decision_id, order_ticket, closed_at,
                        exit_price, net_profit, r_multiple, outcome, exit_reason, lesson,
                    ),
                )
            except sqlite3.Error:
                return None
            if connection.total_changes == 0:
                return None
            connection.execute(
                "UPDATE brain_decisions SET status='CLOSED' WHERE decision_id=?",
                (decision_id,),
            )
            row = connection.execute(
                "SELECT strategy_version, trading_method FROM brain_decisions WHERE decision_id=?",
                (decision_id,),
            ).fetchone()
        if row is not None:
            self._roll_strategy_stats(
                row["strategy_version"],
                row["trading_method"] if "trading_method" in row.keys() else "INDICATOR",
                net_profit,
                delta_wins,
                delta_losses,
                delta_be
            )
        return evaluation_id

    def _roll_strategy_stats(
        self,
        strategy_version: str,
        trading_method: str = "INDICATOR",
        net_profit: float = 0.0,
        delta_wins: int = 0,
        delta_losses: int = 0,
        delta_be: int = 0,
    ) -> None:
        with self._lock, self._connection() as connection:
            existing = connection.execute(
                "SELECT * FROM strategy_stats WHERE strategy_version=? AND trading_method=?",
                (strategy_version, trading_method),
            ).fetchone()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO strategy_stats (
                        strategy_version, trading_method, status, params_json, sample_size, wins,
                        losses, breakevens, win_rate, profit_factor, total_pnl,
                        avg_r, updated_at, notes
                    ) VALUES (?, ?, 'ACTIVE', '{}', 0, 0, 0, 0, NULL, NULL, 0, NULL, ?, 'auto-created')
                    """,
                    (strategy_version, trading_method, _now_iso()),
                )
            stats = connection.execute(
                "SELECT * FROM strategy_stats WHERE strategy_version=? AND trading_method=?",
                (strategy_version, trading_method),
            ).fetchone()
            # BUG FIX: stats có thể là None (schema migration giữa phiên) hoặc cột
            # NULL -> int(None) ném TypeError làm chết vòng AI loop. Fail-closed:
            # không ghi nhận kết quả trade này, log cảnh báo rồi bỏ qua.
            if stats is None or stats["sample_size"] is None or stats["wins"] is None \
                    or stats["losses"] is None or stats["breakevens"] is None:
                logging.getLogger("brain").warning(
                    "strategy_stats row missing/invalid for %s/%s — skipping update",
                    strategy_version, trading_method,
                )
                return
            sample_size = int(stats["sample_size"]) + 1
            wins = int(stats["wins"]) + delta_wins
            losses = int(stats["losses"]) + delta_losses
            breakevens = int(stats["breakevens"]) + delta_be
            total_pnl = float(stats["total_pnl"] or 0) + net_profit
            win_rate = round((wins / sample_size) * 100.0, 2) if sample_size else None
            gross_profit = max(0.0, total_pnl) if total_pnl > 0 else 0.0
            gross_loss = max(0.0, -total_pnl)
            profit_factor = round(gross_profit / gross_loss, 4) if gross_loss else None
            avg_r_row = connection.execute(
                "SELECT AVG(r_multiple) AS avg_r FROM brain_evaluations WHERE decision_id IN (SELECT decision_id FROM brain_decisions WHERE strategy_version=? AND trading_method=?)",
                (strategy_version, trading_method),
            ).fetchone()
            avg_r = round(float(avg_r_row["avg_r"]), 4) if avg_r_row and avg_r_row["avg_r"] is not None else None
            connection.execute(
                """
                UPDATE strategy_stats SET sample_size=?, wins=?, losses=?, breakevens=?,
                    win_rate=?, profit_factor=?, total_pnl=?, avg_r=?, updated_at=?
                WHERE strategy_version=? AND trading_method=?
                """,
                (sample_size, wins, losses, breakevens, win_rate, profit_factor, total_pnl, avg_r, _now_iso(), strategy_version, trading_method),
            )

    def strategy_summary(self) -> list[dict[str, Any]]:
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM strategy_stats ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def recent_decisions(self, limit: int = 30) -> list[dict[str, Any]]:
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                """
                SELECT decision_id, ts, strategy_version, trading_method, action, confidence, entry,
                       stop_loss, take_profit, volume, reason_codes_json, context_json,
                       status, order_ticket, decision_detail
                FROM brain_decisions ORDER BY ts DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            try:
                item["reason_codes"] = json.loads(item.pop("reason_codes_json"))
            except (json.JSONDecodeError, TypeError):
                item["reason_codes"] = []
            try:
                item["context"] = json.loads(item.pop("context_json"))
            except (json.JSONDecodeError, TypeError):
                item["context"] = {}
            out.append(item)
        return out

    def recent_evaluations(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                """
                SELECT e.*, d.action, d.entry, d.strategy_version
                FROM brain_evaluations e
                LEFT JOIN brain_decisions d ON d.decision_id = e.decision_id
                ORDER BY e.closed_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def latest_adjustments(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM brain_adjustments ORDER BY ts DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    # ── Auto-adjust proposals (PENDING until operator applies them) ───────────

    def propose_adjustment(
        self,
        *,
        strategy_version: str,
        window: dict[str, Any],
        proposed: dict[str, Any],
        result: str = "",
    ) -> str:
        adjustment_id = "adj-" + uuid.uuid4().hex[:10]
        with self._lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO brain_adjustments (
                    adjustment_id, ts, strategy_version, window_json,
                    proposed_json, status, applied_at, result
                ) VALUES (?, ?, ?, ?, ?, 'PENDING', NULL, ?)
                """,
                (
                    adjustment_id, _now_iso(), strategy_version,
                    json.dumps(window, ensure_ascii=False),
                    json.dumps(proposed, ensure_ascii=False),
                    result,
                ),
            )
        return adjustment_id

    def mark_adjustment_applied(self, adjustment_id: str, result: str) -> None:
        with self._lock, self._connection() as connection:
            connection.execute(
                """
                UPDATE brain_adjustments SET status='APPLIED', applied_at=?, result=?
                WHERE adjustment_id=?
                """,
                (_now_iso(), result, adjustment_id),
            )

    def reject_adjustment(self, adjustment_id: str, reason: str = "") -> None:
        with self._lock, self._connection() as connection:
            connection.execute(
                """
                UPDATE brain_adjustments SET status='REJECTED', applied_at=?, result=?
                WHERE adjustment_id=?
                """,
                (_now_iso(), reason or "Operator rejected", adjustment_id),
            )
