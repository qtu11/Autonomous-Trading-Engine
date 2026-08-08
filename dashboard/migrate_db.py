"""Database migration script for Autonomous Trading Engine (ATE).

Migrates quantai_brain.sqlite3 to support multi-trading-method analytics.
- Adds trading_method column to brain_decisions table (default 'INDICATOR').
- Recreates strategy_stats table with composite primary key (strategy_version, trading_method).
- Adds index idx_decisions_method on brain_decisions (trading_method).
"""

from __future__ import annotations

import sqlite3
import shutil
from pathlib import Path

DB_PATH = Path(__file__).parent / "quantai_brain.sqlite3"
BAK_PATH = Path(__file__).parent / "quantai_brain.sqlite3.bak"


def migrate_database(db_file: Path = DB_PATH) -> bool:
    if not db_file.exists():
        print(f"[Migration] Database file {db_file} does not exist. Initializing fresh schema.")

    # Create backup
    if db_file.exists():
        shutil.copy2(db_file, db_file.with_suffix(".sqlite3.bak"))
        print(f"[Migration] Created backup at {db_file.with_suffix('.sqlite3.bak')}")

    conn = sqlite3.connect(db_file, timeout=10)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("BEGIN TRANSACTION")

        # 1. Check & Update brain_decisions table
        cursor.execute("PRAGMA table_info(brain_decisions)")
        columns = [row["name"] for row in cursor.fetchall()]

        if "trading_method" not in columns:
            print("[Migration] Adding column 'trading_method' to 'brain_decisions'...")
            cursor.execute(
                "ALTER TABLE brain_decisions ADD COLUMN trading_method TEXT DEFAULT 'INDICATOR'"
            )

        # Create index on trading_method
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_decisions_method ON brain_decisions (trading_method)"
        )

        # 2. Check & Recreate strategy_stats table
        cursor.execute("PRAGMA table_info(strategy_stats)")
        stats_cols = [row["name"] for row in cursor.fetchall()]

        needs_recreate = False
        if stats_cols and "trading_method" not in stats_cols:
            needs_recreate = True

        if needs_recreate:
            print("[Migration] Migrating 'strategy_stats' to Composite Key (strategy_version, trading_method)...")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS strategy_stats_backup AS 
                SELECT *, 'INDICATOR' AS trading_method FROM strategy_stats
                """
            )
            cursor.execute("DROP TABLE strategy_stats")
            cursor.execute(
                """
                CREATE TABLE strategy_stats (
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
            cursor.execute(
                """
                INSERT OR IGNORE INTO strategy_stats (
                    strategy_version, trading_method, status, params_json,
                    sample_size, wins, losses, breakevens, win_rate,
                    profit_factor, total_pnl, avg_r, updated_at, notes
                )
                SELECT 
                    strategy_version, trading_method, status, params_json,
                    sample_size, wins, losses, breakevens, win_rate,
                    profit_factor, total_pnl, avg_r, updated_at, notes
                FROM strategy_stats_backup
                """
            )
            cursor.execute("DROP TABLE strategy_stats_backup")
        else:
            cursor.execute(
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

        conn.commit()
        print("[Migration] Database migration completed successfully.")
        return True

    except Exception as e:
        conn.rollback()
        print(f"[Migration ERROR] Migration failed: {e}")
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    migrate_database()
