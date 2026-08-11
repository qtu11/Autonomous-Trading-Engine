"""
Database Module
SQLite with SQLAlchemy for Trading System
"""
from .connection import engine, SessionLocal, Base, get_db
from .models import (
    Signal, Position, Trade, Account, 
    Candle, Settings, AuditLog
)
from .crud import (
    create_signal, get_signals, get_signal,
    create_position, update_position, get_positions,
    create_trade, get_trades, get_trade,
    update_account, get_account
)

__all__ = [
    'engine', 'SessionLocal', 'Base', 'get_db',
    'Signal', 'Position', 'Trade', 'Account', 'Candle', 'Settings', 'AuditLog',
    'create_signal', 'get_signals', 'get_signal',
    'create_position', 'update_position', 'get_positions',
    'create_trade', 'get_trades', 'get_trade',
    'update_account', 'get_account'
]
