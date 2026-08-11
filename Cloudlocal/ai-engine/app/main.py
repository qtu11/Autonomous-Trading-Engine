"""
AI Engine Service - Handles AI model inference and analysis
FIXED: ATR calculation, confidence bounds
"""
import os
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
import redis.asyncio as redis
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
AI_ENGINE_PORT = int(os.getenv("AI_ENGINE_PORT", "8006"))

redis_client: Optional[redis.Redis] = None


class AnalysisRequest(BaseModel):
    symbol: str = Field(default="XAUUSDm")
    indicators: Dict[str, Any] = Field(default_factory=dict)
    market_data: Dict[str, Any] = Field(default_factory=dict)
    account_info: Dict[str, Any] = Field(default_factory=dict)
    positions: List[Dict[str, Any]] = Field(default_factory=list)
    news_events: List[Dict[str, Any]] = Field(default_factory=list)


class AnalysisResponse(BaseModel):
    signal: str
    confidence: float
    reasoning: str
    risk_level: str
    suggested_lot: float
    entry_price: float
    stop_loss: float
    take_profit: float
    timestamp: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    try:
        redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        await redis_client.ping()
        logger.info("AI Engine connected to Redis")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}")
        redis_client = None
    yield
    if redis_client:
        await redis_client.close()
    logger.info("AI Engine shutdown")


app = FastAPI(title="GoldQuant AI Engine", version="1.0.1", lifespan=lifespan)


@app.get("/health")
async def health_check():
    return {
        "status": "UP",
        "service": "GoldQuant AI Engine",
        "version": "1.0.1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "redis_connected": redis_client is not None
    }


@app.post("/api/v1/analyze", response_model=AnalysisResponse)
async def analyze_market(request: AnalysisRequest):
    """
    Perform AI-powered market analysis and generate trading signals
    """
    try:
        indicators = request.indicators
        market_data = request.market_data
        account_info = request.account_info

        ema20 = indicators.get("ema20", 0)
        ema50 = indicators.get("ema50", 0)
        ema200 = indicators.get("ema200", 0)
        rsi = indicators.get("rsi", 50)
        atr = indicators.get("atr", 2.5)
        bid = market_data.get("bid", 0)
        ask = market_data.get("ask", 0)
        balance = account_info.get("balance", 10000)

        if bid <= 0 or ask <= 0:
            return AnalysisResponse(
                signal="WAIT",
                confidence=0,
                reasoning="Invalid market data",
                risk_level="HIGH",
                suggested_lot=0,
                entry_price=0,
                stop_loss=0,
                take_profit=0,
                timestamp=datetime.now(timezone.utc).isoformat()
            )

        signal = "BUY" if ema20 > ema50 else "SELL" if ema20 < ema50 else "WAIT"

        if signal == "BUY" and ema50 > ema200:
            confidence = 85
        elif signal == "SELL" and ema50 < ema200:
            confidence = 85
        elif signal == "WAIT":
            confidence = 40
        else:
            confidence = 60

        if 45 <= rsi <= 55:
            confidence += 5
        elif (signal == "BUY" and rsi > 70) or (signal == "SELL" and rsi < 30):
            confidence -= 15

        # FIX: ATR threshold for XAUUSD (around $2-4 is typical)
        if atr >= 3.0:
            confidence += 5

        # FIX: Clamp confidence between 0 and 100
        confidence = max(0, min(100, confidence))

        # FIX: Use ATR value directly if provided, otherwise calculate
        atr_value = float(atr) if atr else 2.5
        sl_dist = max(3.0, atr_value * 1.5)
        tp_dist = sl_dist * 2.0

        if signal == "BUY":
            entry_price = ask
            stop_loss = round(ask - sl_dist, 2)
            take_profit = round(ask + tp_dist, 2)
        elif signal == "SELL":
            entry_price = bid
            stop_loss = round(bid + sl_dist, 2)
            take_profit = round(bid - tp_dist, 2)
        else:
            entry_price = (bid + ask) / 2
            stop_loss = 0
            take_profit = 0

        # FIX: Safe risk calculation
        risk_amount = balance * 0.01 if balance > 0 else 100
        risk_per_pip = sl_dist if sl_dist > 0 else 3.0
        suggested_lot = round(max(0.01, min(2.0, risk_amount / (risk_per_pip * 100))), 2)

        risk_level = "LOW" if confidence > 80 else "MEDIUM" if confidence > 60 else "HIGH"

        reasoning_parts = []
        if signal == "BUY":
            reasoning_parts.append(f"EMA20({ema20:.2f}) > EMA50({ema50:.2f}) - Uptrend confirmed")
        elif signal == "SELL":
            reasoning_parts.append(f"EMA20({ema20:.2f}) < EMA50({ema50:.2f}) - Downtrend confirmed")
        else:
            reasoning_parts.append("EMA crossover neutral - No clear trend")

        reasoning_parts.append(f"RSI: {rsi:.1f}")
        reasoning_parts.append(f"ATR: {atr_value:.2f} (volatility {'high' if atr_value >= 3 else 'normal'})")

        floating_pnl = account_info.get("floating_pnl", 0) or 0
        if floating_pnl < -100:
            reasoning_parts.append("WARNING: Significant floating loss detected")

        reasoning = ". ".join(reasoning_parts)

        return AnalysisResponse(
            signal=signal,
            confidence=confidence,
            reasoning=reasoning,
            risk_level=risk_level,
            suggested_lot=suggested_lot,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/analyze/news")
async def analyze_news_impact(news_event: Dict[str, Any], indicators: Dict[str, Any]):
    """
    Analyze economic news impact on gold price
    """
    try:
        title = news_event.get("title", "").upper()
        forecast = news_event.get("forecast", "")
        previous = news_event.get("previous", "")
        impact = news_event.get("impact", "MEDIUM").upper()

        f_val, p_val = None, None
        try:
            f_clean = str(forecast).replace("%", "").replace("K", "").replace("M", "").strip()
            p_clean = str(previous).replace("%", "").replace("K", "").replace("M", "").strip()
            f_val = float(f_clean) if f_clean else None
            p_val = float(p_clean) if p_clean else None
        except Exception:
            pass

        if f_val is not None and p_val is not None and f_val != p_val:
            if f_val > p_val:
                usd_impact = "BULLISH" if "NFP" in title or "CPI" in title or "PPI" in title else "BEARISH"
                gold_impact = "BEARISH" if usd_impact == "BULLISH" else "BULLISH"
            else:
                usd_impact = "BEARISH" if "NFP" in title or "CPI" in title or "PPI" in title else "BULLISH"
                gold_impact = "BULLISH" if usd_impact == "BEARISH" else "BEARISH"
        else:
            usd_impact = "NEUTRAL"
            gold_impact = "NEUTRAL"

        return {
            "news_title": title,
            "impact_level": impact,
            "usd_impact": usd_impact,
            "gold_impact": gold_impact,
            "forecast": forecast,
            "previous": previous,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"News analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/models/status")
async def models_status():
    return {
        "active_model": os.getenv("QUANTAI_AI_MODEL", "deepseek-v4-flash-free"),
        "available_models": [
            "deepseek-v4-flash-free", "big-pickle", "mimo-v2.5-free",
            "nemotron-3-ultra-free", "north-mini-code-free", "laguna-s-2.1-free",
            "longcat-2.0-free", "ling-3.0-flash-free",
            "kimi-k3", "gemini-2.0-flash", "gpt-4o", "claude-3.5-sonnet"
        ],
        "default_free_gateway": os.getenv("OPENCODE_BASE_URL", "https://opencode.ai/zen/v1/chat/completions"),
        "requires_api_key": False,
        "redis_connected": redis_client is not None,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=AI_ENGINE_PORT)
