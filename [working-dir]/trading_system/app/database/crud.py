"""
CRUD Operations for Trading System
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from .models import Candle, Signal, Position, Trade, Account, Settings, AuditLog
import json
import uuid


# ─── SIGNAL CRUD ───

def create_signal(
    db: Session,
    symbol: str,
    timeframe: str,
    direction: str,
    signal_type: str,
    current_price: float,
    entry_price: float,
    stop_loss: float,
    take_profit_1: float,
    take_profit_2: float,
    take_profit_3: float,
    risk_amount: float,
    risk_reward: float,
    total_score: int,
    confluence_count: int,
    score_details: dict,
    patterns: List[str],
    confidence: float,
    signal_id: str = None
) -> Signal:
    """Create a new signal"""
    if signal_id is None:
        signal_id = f"SIG-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
    
    db_signal = Signal(
        signal_id=signal_id,
        symbol=symbol,
        timeframe=timeframe,
        direction=direction,
        signal_type=signal_type,
        current_price=current_price,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit_1=take_profit_1,
        take_profit_2=take_profit_2,
        take_profit_3=take_profit_3,
        risk_amount=risk_amount,
        risk_reward=risk_reward,
        total_score=total_score,
        confluence_count=confluence_count,
        score_details=score_details,
        patterns=patterns,
        confidence=confidence
    )
    db.add(db_signal)
    db.commit()
    db.refresh(db_signal)
    return db_signal


def get_signals(
    db: Session,
    symbol: str = None,
    timeframe: str = None,
    direction: str = None,
    is_active: bool = None,
    limit: int = 100,
    offset: int = 0
) -> List[Signal]:
    """Get signals with filters"""
    query = db.query(Signal)
    
    if symbol:
        query = query.filter(Signal.symbol == symbol)
    if timeframe:
        query = query.filter(Signal.timeframe == timeframe)
    if direction:
        query = query.filter(Signal.direction == direction)
    if is_active is not None:
        query = query.filter(Signal.is_active == is_active)
    
    return query.order_by(desc(Signal.created_at)).offset(offset).limit(limit).all()


def get_signal(db: Session, signal_id: str) -> Optional[Signal]:
    """Get a signal by ID"""
    return db.query(Signal).filter(Signal.signal_id == signal_id).first()


def update_signal(db: Session, signal_id: str, **kwargs) -> Optional[Signal]:
    """Update a signal"""
    db_signal = get_signal(db, signal_id)
    if db_signal:
        for key, value in kwargs.items():
            if hasattr(db_signal, key):
                setattr(db_signal, key, value)
        db_signal.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_signal)
    return db_signal


# ─── POSITION CRUD ───

def create_position(
    db: Session,
    position_id: str,
    signal_id: str,
    symbol: str,
    direction: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    quantity: float,
    leverage: int = 1,
    current_price: float = None
) -> Position:
    """Create a new position"""
    if current_price is None:
        current_price = entry_price
    
    db_position = Position(
        position_id=position_id,
        signal_id=signal_id,
        symbol=symbol,
        direction=direction,
        entry_price=entry_price,
        current_price=current_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        quantity=quantity,
        leverage=leverage
    )
    db.add(db_position)
    db.commit()
    db.refresh(db_position)
    return db_position


def get_positions(
    db: Session,
    symbol: str = None,
    direction: str = None,
    is_closed: bool = False,
    limit: int = 100
) -> List[Position]:
    """Get positions"""
    query = db.query(Position)
    
    if symbol:
        query = query.filter(Position.symbol == symbol)
    if direction:
        query = query.filter(Position.direction == direction)
    
    if is_closed:
        query = query.filter(Position.closed_at.isnot(None))
    else:
        query = query.filter(Position.closed_at.is_(None))
    
    return query.order_by(desc(Position.opened_at)).limit(limit).all()


def update_position(db: Session, position_id: str, **kwargs) -> Optional[Position]:
    """Update a position"""
    db_position = db.query(Position).filter(Position.position_id == position_id).first()
    if db_position:
        for key, value in kwargs.items():
            if hasattr(db_position, key):
                setattr(db_position, key, value)
        db_position.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_position)
    return db_position


def close_position(db: Session, position_id: str, exit_price: float) -> Optional[Position]:
    """Close a position"""
    db_position = db.query(Position).filter(Position.position_id == position_id).first()
    if db_position:
        db_position.closed_at = datetime.utcnow()
        db_position.current_price = exit_price
        db.commit()
        db.refresh(db_position)
    return db_position


# ─── TRADE CRUD ───

def create_trade(
    db: Session,
    trade_id: str,
    signal_id: str,
    symbol: str,
    direction: str,
    entry_price: float,
    exit_price: float,
    stop_loss: float,
    quantity: float,
    leverage: int,
    pnl: float,
    pnl_pct: float,
    risk_reward: float,
    exit_reason: str,
    total_score: int,
    opened_at: datetime
) -> Trade:
    """Create a closed trade"""
    db_trade = Trade(
        trade_id=trade_id,
        signal_id=signal_id,
        symbol=symbol,
        direction=direction,
        entry_price=entry_price,
        exit_price=exit_price,
        stop_loss=stop_loss,
        quantity=quantity,
        leverage=leverage,
        pnl=pnl,
        pnl_pct=pnl_pct,
        risk_reward=risk_reward,
        exit_reason=exit_reason,
        total_score=total_score,
        opened_at=opened_at
    )
    db.add(db_trade)
    db.commit()
    db.refresh(db_trade)
    return db_trade


def get_trades(
    db: Session,
    symbol: str = None,
    direction: str = None,
    exit_reason: str = None,
    limit: int = 100
) -> List[Trade]:
    """Get closed trades"""
    query = db.query(Trade)
    
    if symbol:
        query = query.filter(Trade.symbol == symbol)
    if direction:
        query = query.filter(Trade.direction == direction)
    if exit_reason:
        query = query.filter(Trade.exit_reason == exit_reason)
    
    return query.order_by(desc(Trade.closed_at)).limit(limit).all()


def get_trade(db: Session, trade_id: str) -> Optional[Trade]:
    """Get a trade by ID"""
    return db.query(Trade).filter(Trade.trade_id == trade_id).first()


# ─── ACCOUNT CRUD ───

def get_account(db: Session) -> Account:
    """Get or create account"""
    account = db.query(Account).first()
    if not account:
        account = Account(
            balance=10000.0,
            equity=10000.0,
            available_balance=10000.0
        )
        db.add(account)
        db.commit()
        db.refresh(account)
    return account


def update_account(db: Session, **kwargs) -> Account:
    """Update account"""
    account = get_account(db)
    for key, value in kwargs.items():
        if hasattr(account, key):
            setattr(account, key, value)
    account.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(account)
    return account


# ─── CANDLE CRUD ───

def save_candles(db: Session, symbol: str, timeframe: str, candles: List[dict]) -> int:
    """Save candles to database"""
    count = 0
    for candle in candles:
        existing = db.query(Candle).filter(
            Candle.symbol == symbol,
            Candle.timeframe == timeframe,
            Candle.timestamp == candle['timestamp']
        ).first()
        
        if existing:
            # Update
            for key in ['open', 'high', 'low', 'close', 'volume']:
                if key in candle:
                    setattr(existing, key, candle[key])
        else:
            # Insert
            db_candle = Candle(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=candle['timestamp'],
                open=candle.get('open', 0),
                high=candle.get('high', 0),
                low=candle.get('low', 0),
                close=candle.get('close', 0),
                volume=candle.get('volume', 0)
            )
            db.add(db_candle)
        count += 1
    
    db.commit()
    return count


def get_candles(
    db: Session,
    symbol: str,
    timeframe: str,
    start_time: datetime = None,
    end_time: datetime = None,
    limit: int = 2000
) -> List[Candle]:
    """Get candles from database"""
    query = db.query(Candle).filter(
        Candle.symbol == symbol,
        Candle.timeframe == timeframe
    )
    
    if start_time:
        query = query.filter(Candle.timestamp >= start_time)
    if end_time:
        query = query.filter(Candle.timestamp <= end_time)
    
    return query.order_by(desc(Candle.timestamp)).limit(limit).all()


# ─── AUDIT LOG ───

def log_action(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: str,
    old_value: dict = None,
    new_value: dict = None,
    user: str = None,
    details: str = None
) -> AuditLog:
    """Log an action"""
    log = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
        user=user,
        details=details
    )
    db.add(log)
    db.commit()
    return log
