"""
SQLAlchemy Models for Trading System
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from .connection import Base


class Candle(Base):
    """Candlestick data"""
    __tablename__ = "candles"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), index=True)
    timeframe = Column(String(10))
    timestamp = Column(DateTime, index=True)
    
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)


class Signal(Base):
    """Trading signals"""
    __tablename__ = "signals"
    
    id = Column(Integer, primary_key=True, index=True)
    signal_id = Column(String(50), unique=True, index=True)
    
    symbol = Column(String(20), index=True)
    timeframe = Column(String(10))
    direction = Column(String(10))  # LONG, SHORT
    signal_type = Column(String(20))  # STRONG_BUY, BUY, NEUTRAL, SELL, STRONG_SELL
    
    # Price levels
    current_price = Column(Float)
    entry_price = Column(Float)
    stop_loss = Column(Float)
    take_profit_1 = Column(Float)
    take_profit_2 = Column(Float)
    take_profit_3 = Column(Float)
    
    # Risk
    risk_amount = Column(Float)
    risk_reward = Column(Float)
    
    # Score
    total_score = Column(Integer)
    confluence_count = Column(Integer)
    score_details = Column(JSON)
    
    # Patterns
    patterns = Column(JSON)
    
    # Confidence
    confidence = Column(Float)
    
    # Status
    is_active = Column(Boolean, default=True)
    triggered_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    positions = relationship("Position", back_populates="signal")
    trades = relationship("Trade", back_populates="signal")


class Position(Base):
    """Open positions"""
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True, index=True)
    position_id = Column(String(50), unique=True, index=True)
    signal_id = Column(String(50), ForeignKey("signals.signal_id"))
    
    symbol = Column(String(20), index=True)
    direction = Column(String(10))  # LONG, SHORT
    
    entry_price = Column(Float)
    current_price = Column(Float)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    
    quantity = Column(Float)
    leverage = Column(Integer, default=1)
    
    # P&L
    unrealized_pnl = Column(Float, default=0)
    unrealized_pnl_pct = Column(Float, default=0)
    
    # Status
    tp1_hit = Column(Boolean, default=False)
    tp2_hit = Column(Boolean, default=False)
    tp3_hit = Column(Boolean, default=False)
    sl_hit = Column(Boolean, default=False)
    
    # Timestamps
    opened_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    
    # Relationships
    signal = relationship("Signal", back_populates="positions")


class Trade(Base):
    """Closed trades"""
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    trade_id = Column(String(50), unique=True, index=True)
    signal_id = Column(String(50), ForeignKey("signals.signal_id"))
    
    symbol = Column(String(20), index=True)
    direction = Column(String(10))  # LONG, SHORT
    
    entry_price = Column(Float)
    exit_price = Column(Float)
    stop_loss = Column(Float)
    
    quantity = Column(Float)
    leverage = Column(Integer, default=1)
    
    # P&L
    pnl = Column(Float)
    pnl_pct = Column(Float)
    risk_reward = Column(Float)
    
    # Exit
    exit_reason = Column(String(20))  # tp_hit, sl_hit, manual, trailing
    total_score = Column(Integer)
    
    # Timestamps
    opened_at = Column(DateTime)
    closed_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    signal = relationship("Signal", back_populates="trades")


class Account(Base):
    """Trading account snapshot"""
    __tablename__ = "accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    
    balance = Column(Float)
    equity = Column(Float)
    available_balance = Column(Float)
    
    open_positions_count = Column(Integer, default=0)
    total_pnl = Column(Float, default=0)
    total_pnl_pct = Column(Float, default=0)
    
    daily_pnl = Column(Float, default=0)
    daily_pnl_pct = Column(Float, default=0)
    
    win_rate = Column(Float, default=0)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    
    max_drawdown = Column(Float, default=0)
    max_drawdown_pct = Column(Float, default=0)
    
    consecutive_wins = Column(Integer, default=0)
    consecutive_losses = Column(Integer, default=0)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Settings(Base):
    """User settings"""
    __tablename__ = "settings"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True)
    value = Column(Text)
    value_type = Column(String(20))  # string, int, float, bool, json
    
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditLog(Base):
    """Audit log for all operations"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    action = Column(String(50), index=True)
    entity_type = Column(String(50))  # signal, position, trade, account
    entity_id = Column(String(50))
    
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)
    
    user = Column(String(50), nullable=True)
    ip_address = Column(String(50), nullable=True)
    
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    details = Column(Text, nullable=True)
