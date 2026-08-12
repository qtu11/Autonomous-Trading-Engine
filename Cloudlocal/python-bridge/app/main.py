"""
Python Bridge Service - Direct MT5 Communication
Handles bidirectional communication between FastAPI backend and MetaTrader 5
"""
import os
import asyncio
import json
import logging
import signal
import sys
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
import redis.asyncio as redis
import httpx

# Try to import MetaTrader5
try:
    import MetaTrader5 as mt5
    HAS_MT5 = True
except ImportError:
    mt5 = None
    HAS_MT5 = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
MT5_LOGIN = int(os.getenv("MT5_LOGIN") or "0")
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")
MT5_PATH = os.getenv("MT5_PATH", "C:/Program Files/MetaTrader 5/terminal64.exe")
BRIDGE_PORT = int(os.getenv("BRIDGE_PORT", "8007"))
FASTAPI_URL = os.getenv("FASTAPI_URL", "http://localhost:8005")
QUANTAI_BRIDGE_TOKEN = os.getenv("QUANTAI_BRIDGE_TOKEN", "")
PUBLIC_IP = os.getenv("PUBLIC_IP", "localhost")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# Global state
redis_client: Optional[redis.Redis] = None
mt5_connected = False
mt5_lock = asyncio.Lock()
active_websockets: List[WebSocket] = []

# Symbol mapping
SYMBOL_MAP = {
    "XAUUSD": "XAUUSDm",
    "XAUUSDm": "XAUUSDm",
    "GOLD": "XAUUSDm",
}

# Timeframe mapping (string -> MT5 enum)
TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1 if HAS_MT5 else 1,
    "M5": mt5.TIMEFRAME_M5 if HAS_MT5 else 5,
    "M15": mt5.TIMEFRAME_M15 if HAS_MT5 else 15,
    "M30": mt5.TIMEFRAME_M30 if HAS_MT5 else 30,
    "H1": mt5.TIMEFRAME_H1 if HAS_MT5 else 60,
    "H4": mt5.TIMEFRAME_H4 if HAS_MT5 else 240,
    "D1": mt5.TIMEFRAME_D1 if HAS_MT5 else 1440,
    "W1": mt5.TIMEFRAME_W1 if HAS_MT5 else 10080,
    "MN1": mt5.TIMEFRAME_MN1 if HAS_MT5 else 43200,
}


class OrderRequest(BaseModel):
    symbol: str = Field(default="XAUUSDm")
    action: str = Field(..., pattern="^(BUY|SELL|CLOSE|CLOSE_ALL|MODIFY)$")
    volume: float = Field(default=0.01, gt=0)
    price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    magic: int = Field(default=888999)
    comment: str = Field(default="GoldQuant AI")
    ticket: Optional[int] = None


class OrderResponse(BaseModel):
    success: bool
    ticket: Optional[int] = None
    price: Optional[float] = None
    message: str
    timestamp: str


class MarketDataResponse(BaseModel):
    symbol: str
    bid: float
    ask: float
    spread: float
    time: str
    volume: int


class AccountResponse(BaseModel):
    login: int
    server: str
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level: float
    currency: str
    leverage: int


class PositionResponse(BaseModel):
    ticket: int
    symbol: str
    type: str
    volume: float
    price_open: float
    sl: float
    tp: float
    profit: float
    swap: float
    comment: str
    magic: int


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client, mt5_connected
    
    # Initialize Redis
    try:
        redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        await redis_client.ping()
        logger.info("Bridge connected to Redis")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}")
        redis_client = None

    # Initialize MT5 connection
    mt5_connected = await initialize_mt5()
    
    # Start background tasks
    broadcast_task = asyncio.create_task(broadcast_market_data())
    sync_task = asyncio.create_task(sync_with_fastapi())
    
    yield
    
    # Cleanup
    broadcast_task.cancel()
    sync_task.cancel()
    if redis_client:
        await redis_client.close()
    if mt5_connected and HAS_MT5:
        mt5.shutdown()
    logger.info("Bridge shutdown complete")


app = FastAPI(title="GoldQuant MT5 Bridge", version="1.0.0", lifespan=lifespan)


async def initialize_mt5() -> bool:
    """Initialize MT5 connection with retry logic"""
    if not HAS_MT5:
        logger.warning("MetaTrader5 module not available")
        return False

    for attempt in range(3):
        try:
            if mt5.initialize(path=MT5_PATH):
                if MT5_LOGIN and MT5_PASSWORD and MT5_SERVER:
                    authorized = mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
                    if authorized:
                        logger.info(f"MT5 connected: {MT5_LOGIN} @ {MT5_SERVER}")
                        return True
                    else:
                        logger.error(f"MT5 login failed: {mt5.last_error()}")
                else:
                    logger.info("MT5 initialized (no login credentials)")
                    return True
            else:
                logger.error(f"MT5 init failed: {mt5.last_error()}")
        except Exception as e:
            logger.error(f"MT5 init attempt {attempt + 1} failed: {e}")
        
        if attempt < 2:
            await asyncio.sleep(5)
    
    return False


async def ensure_mt5() -> bool:
    """Ensure MT5 is connected, reconnect if needed"""
    global mt5_connected
    async with mt5_lock:
        if not HAS_MT5:
            return False
        if not mt5_connected or mt5.terminal_info() is None:
            mt5_connected = await initialize_mt5()
        return mt5_connected


def resolve_symbol(symbol: str) -> str:
    """Resolve symbol to broker-specific name"""
    return SYMBOL_MAP.get(symbol.upper(), symbol)


async def broadcast_market_data():
    """Broadcast real-time market data to WebSocket clients and Redis"""
    while True:
        try:
            if await ensure_mt5():
                symbol = resolve_symbol("XAUUSDm")
                tick = mt5.symbol_info_tick(symbol)
                if tick:
                    data = {
                        "symbol": symbol,
                        "bid": tick.bid,
                        "ask": tick.ask,
                        "spread": (tick.ask - tick.bid) * 10000,
                        "time": datetime.fromtimestamp(tick.time, tz=timezone.utc).isoformat(),
                        "volume": tick.volume,
                        "source": "mt5_bridge"
                    }
                    
                    # Broadcast to WebSocket clients
                    for ws in active_websockets[:]:
                        try:
                            await ws.send_json({"type": "tick", "data": data})
                        except Exception:
                            active_websockets.remove(ws)
                    
                    # Publish to Redis for other services
                    if redis_client:
                        await redis_client.publish("market:ticks", json.dumps(data))
                        await redis_client.set("market:latest_tick", json.dumps(data), ex=5)
        except Exception as e:
            logger.error(f"Broadcast error: {e}")
        await asyncio.sleep(1)


async def sync_with_fastapi():
    """Sync account and position data with FastAPI backend"""
    while True:
        try:
            if await ensure_mt5():
                # Get account info
                account = mt5.account_info()
                if account:
                    acc_data = {
                        "login": account.login,
                        "server": account.server,
                        "balance": account.balance,
                        "equity": account.equity,
                        "margin": account.margin,
                        "free_margin": account.margin_free,
                        "margin_level": account.margin_level if account.margin_level > 0 else 0,
                        "currency": account.currency,
                        "leverage": account.leverage,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    
                    if redis_client:
                        await redis_client.set("mt5:account", json.dumps(acc_data), ex=10)
                    
                    # Sync to FastAPI
                    async with httpx.AsyncClient() as client:
                        try:
                            await client.post(
                                f"{FASTAPI_URL}/api/v1/bridge/account_sync",
                                json=acc_data,
                                headers={"Authorization": f"Bearer {QUANTAI_BRIDGE_TOKEN}"},
                                timeout=5
                            )
                        except Exception:
                            pass
                
                # Get positions
                positions = mt5.positions_get()
                if positions is not None:
                    pos_data = []
                    for pos in positions:
                        if pos.magic == 888999:  # Only our magic number
                            pos_data.append({
                                "ticket": pos.ticket,
                                "symbol": pos.symbol,
                                "type": "BUY" if pos.type == 0 else "SELL",
                                "volume": pos.volume,
                                "price_open": pos.price_open,
                                "sl": pos.sl,
                                "tp": pos.tp,
                                "profit": pos.profit,
                                "swap": pos.swap,
                                "comment": pos.comment,
                                "magic": pos.magic
                            })
                    
                    if redis_client:
                        await redis_client.set("mt5:positions", json.dumps(pos_data), ex=10)
                        
        except Exception as e:
            logger.error(f"Sync error: {e}")
        await asyncio.sleep(5)


@app.get("/health")
async def health_check():
    return {
        "status": "UP",
        "service": "GoldQuant MT5 Bridge",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mt5_connected": mt5_connected,
        "redis_connected": redis_client is not None,
        "public_ip": PUBLIC_IP
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time market data"""
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        # Send initial data
        if redis_client:
            tick = await redis_client.get("market:latest_tick")
            if tick:
                await websocket.send_json({"type": "tick", "data": json.loads(tick)})
        
        while True:
            # Keep alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in active_websockets:
            active_websockets.remove(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in active_websockets:
            active_websockets.remove(websocket)


@app.get("/api/v1/market/tick", response_model=MarketDataResponse)
async def get_tick(symbol: str = "XAUUSDm"):
    """Get latest tick data"""
    if not await ensure_mt5():
        raise HTTPException(status_code=503, detail="MT5 not connected")
    
    resolved = resolve_symbol(symbol)
    tick = mt5.symbol_info_tick(resolved)
    if not tick:
        raise HTTPException(status_code=404, detail=f"Symbol {resolved} not found")
    
    return MarketDataResponse(
        symbol=resolved,
        bid=tick.bid,
        ask=tick.ask,
        spread=round((tick.ask - tick.bid) * 10000, 1),
        time=datetime.fromtimestamp(tick.time, tz=timezone.utc).isoformat(),
        volume=tick.volume
    )


@app.get("/api/v1/market/candles")
async def get_candles(symbol: str = "XAUUSDm", tf: str = "M15", count: int = 1000):
    """Get REAL MT5 candles via copy_rates_from_pos.
    BUG FIX: endpoint này KHÔNG tồn tại trước đây — dashboard gọi
    {BRIDGE_URL}/api/candles (404) nên luôn rơi vào dữ liệu giả."""
    if not await ensure_mt5():
        raise HTTPException(status_code=503, detail="MT5 not connected")

    resolved = resolve_symbol(symbol)
    tf_enum = TIMEFRAME_MAP.get(tf.upper(), mt5.TIMEFRAME_M15 if HAS_MT5 else 15)
    count = max(1, min(int(count), 200000))
    rates = mt5.copy_rates_from_pos(resolved, tf_enum, 0, count)
    if rates is None or len(rates) == 0:
        raise HTTPException(status_code=404, detail=f"No candles for {resolved} on {tf}")

    candles = []
    for r in rates:
        candles.append({
            "time": datetime.fromtimestamp(int(r["time"]), tz=timezone.utc).isoformat(),
            "ts": datetime.fromtimestamp(int(r["time"]), tz=timezone.utc).isoformat(),
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "tick_volume": int(r["tick_volume"]),
            "volume": int(r["tick_volume"]),
            "spread": int(r["spread"]),
            "real_volume": int(r["real_volume"]),
        })
    return {"symbol": resolved, "timeframe": tf.upper(), "count": len(candles), "candles": candles}


# Aliases cho dashboard cũ gọi {BRIDGE_URL}/api/candles & /api/tick (backward-compat)
@app.get("/api/candles")
async def api_candles_alias(symbol: str = "XAUUSDm", tf: str = "M15", count: int = 1000):
    return await get_candles(symbol, tf, count)

@app.get("/api/tick")
async def api_tick_alias(symbol: str = "XAUUSDm"):
    return await get_tick(symbol)


@app.get("/api/v1/account", response_model=AccountResponse)
async def get_account():
    """Get account information"""
    if not await ensure_mt5():
        raise HTTPException(status_code=503, detail="MT5 not connected")
    
    account = mt5.account_info()
    if not account:
        raise HTTPException(status_code=503, detail="Failed to get account info")
    
    return AccountResponse(
        login=account.login,
        server=account.server,
        balance=account.balance,
        equity=account.equity,
        margin=account.margin,
        free_margin=account.margin_free,
        margin_level=account.margin_level if account.margin_level > 0 else 0,
        currency=account.currency,
        leverage=account.leverage
    )


@app.get("/api/v1/positions", response_model=List[PositionResponse])
async def get_positions(symbol: Optional[str] = None):
    """Get open positions"""
    if not await ensure_mt5():
        raise HTTPException(status_code=503, detail="MT5 not connected")
    
    positions = mt5.positions_get(symbol=resolve_symbol(symbol) if symbol else None)
    if positions is None:
        return []
    
    result = []
    for pos in positions:
        if pos.magic == 888999 or not symbol:  # Filter by magic or show all
            result.append(PositionResponse(
                ticket=pos.ticket,
                symbol=pos.symbol,
                type="BUY" if pos.type == 0 else "SELL",
                volume=pos.volume,
                price_open=pos.price_open,
                sl=pos.sl,
                tp=pos.tp,
                profit=pos.profit,
                swap=pos.swap,
                comment=pos.comment,
                magic=pos.magic
            ))
    return result


@app.post("/api/v1/order", response_model=OrderResponse)
async def execute_order(order: OrderRequest, authorization: Optional[str] = Header(default=None)):
    """Execute trading order"""
    # Verify bridge token
    if QUANTAI_BRIDGE_TOKEN and (not authorization or authorization != f"Bearer {QUANTAI_BRIDGE_TOKEN}"):
        raise HTTPException(status_code=401, detail="Invalid bridge token")
    
    if not await ensure_mt5():
        raise HTTPException(status_code=503, detail="MT5 not connected")
    
    resolved = resolve_symbol(order.symbol)
    
    try:
        if order.action == "BUY":
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": resolved,
                "volume": order.volume,
                "type": mt5.ORDER_TYPE_BUY,
                "price": mt5.symbol_info_tick(resolved).ask,
                "sl": order.sl,
                "tp": order.tp,
                "magic": order.magic,
                "comment": order.comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_RETURN,
            }
        elif order.action == "SELL":
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": resolved,
                "volume": order.volume,
                "type": mt5.ORDER_TYPE_SELL,
                "price": mt5.symbol_info_tick(resolved).bid,
                "sl": order.sl,
                "tp": order.tp,
                "magic": order.magic,
                "comment": order.comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_RETURN,
            }
        elif order.action == "CLOSE" and order.ticket:
            positions = mt5.positions_get(ticket=order.ticket)
            if not positions:
                raise HTTPException(status_code=404, detail="Position not found")
            pos = positions[0]
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY,
                "position": pos.ticket,
                "price": mt5.symbol_info_tick(pos.symbol).bid if pos.type == 0 else mt5.symbol_info_tick(pos.symbol).ask,
                "magic": order.magic,
                "comment": "Close by bridge",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_RETURN,
            }
        elif order.action == "CLOSE_ALL":
            closed = 0
            positions = mt5.positions_get()
            if positions:
                for pos in positions:
                    if pos.magic == order.magic:
                        close_req = {
                            "action": mt5.TRADE_ACTION_DEAL,
                            "symbol": pos.symbol,
                            "volume": pos.volume,
                            "type": mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY,
                            "position": pos.ticket,
                            "price": mt5.symbol_info_tick(pos.symbol).bid if pos.type == 0 else mt5.symbol_info_tick(pos.symbol).ask,
                            "magic": order.magic,
                            "comment": "Close all by bridge",
                            "type_time": mt5.ORDER_TIME_GTC,
                            "type_filling": mt5.ORDER_FILLING_RETURN,
                        }
                        result = mt5.order_send(close_req)
                        if result.retcode == mt5.TRADE_RETCODE_DONE:
                            closed += 1
            return OrderResponse(
                success=True,
                message=f"Closed {closed} positions",
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        elif order.action == "MODIFY" and order.ticket:
            positions = mt5.positions_get(ticket=order.ticket)
            if not positions:
                raise HTTPException(status_code=404, detail="Position not found")
            pos = positions[0]
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": pos.symbol,
                "position": pos.ticket,
                "sl": order.sl if order.sl else pos.sl,
                "tp": order.tp if order.tp else pos.tp,
            }
        else:
            raise HTTPException(status_code=400, detail="Invalid action or missing parameters")
        
        result = mt5.order_send(request)
        
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            return OrderResponse(
                success=True,
                ticket=result.order,
                price=result.price,
                message="Order executed successfully",
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        else:
            return OrderResponse(
                success=False,
                message=f"Order failed: {result.retcode} - {result.comment}",
                timestamp=datetime.now(timezone.utc).isoformat()
            )
    
    except Exception as e:
        logger.error(f"Order execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/symbols")
async def get_symbols():
    """Get available symbols"""
    if not await ensure_mt5():
        raise HTTPException(status_code=503, detail="MT5 not connected")
    
    symbols = mt5.symbols_get()
    if symbols is None:
        return []
    
    gold_symbols = []
    for s in symbols:
        if "gold" in s.name.lower() or "xau" in s.name.lower() or s.name in ["XAUUSD", "XAUUSDm", "GOLD"]:
            gold_symbols.append({
                "name": s.name,
                "description": s.description,
                "point": s.point,
                "digits": s.digits,
                "spread": s.spread,
                "trade_mode": s.trade_mode
            })
    return gold_symbols


@app.post("/api/v1/bridge/reconnect")
async def reconnect_mt5(authorization: Optional[str] = Header(default=None)):
    """Force MT5 reconnection"""
    if QUANTAI_BRIDGE_TOKEN and (not authorization or authorization != f"Bearer {QUANTAI_BRIDGE_TOKEN}"):
        raise HTTPException(status_code=401, detail="Invalid bridge token")
    
    global mt5_connected
    if HAS_MT5:
        mt5.shutdown()
    mt5_connected = await initialize_mt5()
    
    return {
        "success": mt5_connected,
        "message": "MT5 reconnected" if mt5_connected else "MT5 reconnection failed",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=BRIDGE_PORT)