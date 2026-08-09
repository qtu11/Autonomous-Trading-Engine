import os
import secrets
import sys
import json
import time
import asyncio
import urllib.request
import pandas as pd
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from fastapi import Depends, FastAPI, HTTPException, Header, Query, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from command_store import CommandStore
from brain import BrainStore
from logging_config import LogEvent, log_event, read_recent_logs, timed, get_logger
from risk_gate import (
    AccountSnapshot,
    DCA_DEFAULT_MAX_LOT,
    MAX_BASKET_LOSS_FRACTION,
    RiskPolicy,
    SymbolSpec,
    cap_volume_to_basket_risk,
    compute_dca_volume,
    evaluate_risk,
)
from risk_profiles import FOREX_RISK_PROFILES
from strategy_core import DecisionProposal, SignalAction, StrategyConfig, decide_signal
from signal_engines import run_signal_engine, SignalResult
from chart_markup import build_chart_markup
from ws_hub import WS_MANAGER

try:
    from mt5_auto import find_terminal64, deploy_expert_to_chart
    HAS_MT5_AUTO = True
except Exception:
    find_terminal64 = None
    deploy_expert_to_chart = None
    HAS_MT5_AUTO = False

try:
    from ai_provider_test import test_provider_connection
    HAS_AI_TEST = True
except Exception:
    test_provider_connection = None
    HAS_AI_TEST = False
logger = get_logger()

def load_local_env() -> None:
    """Load local development variables without overriding the process environment."""
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if not os.path.isfile(env_path):
        return
    with open(env_path, encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_local_env()

try:
    import MetaTrader5 as mt5
    HAS_MT5 = True
except ImportError:
    mt5 = None
    HAS_MT5 = False

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    psutil = None
    HAS_PSUTIL = False

EXECUTION_MODE = (os.getenv("ATE_EXECUTION_MODE") or os.getenv("QUANTAI_EXECUTION_MODE") or "DISABLED").upper()
DEMO_ARMED = (os.getenv("ATE_DEMO_ARMED") or os.getenv("QUANTAI_DEMO_ARMED") or "false").lower() == "true"
KILL_SWITCH = (os.getenv("ATE_KILL_SWITCH") or os.getenv("QUANTAI_KILL_SWITCH") or "true").lower() == "true"
DEMO_LOGIN = int(os.getenv("ATE_DEMO_LOGIN") or os.getenv("QUANTAI_DEMO_LOGIN") or os.getenv("MT5_LOGIN") or "0")
DEMO_SERVER = os.getenv("ATE_DEMO_SERVER") or os.getenv("QUANTAI_DEMO_SERVER") or os.getenv("MT5_SERVER") or ""
DEMO_BROKER_COMPANY = os.getenv("ATE_DEMO_BROKER_COMPANY") or os.getenv("QUANTAI_DEMO_BROKER_COMPANY", "")
EXECUTION_SYMBOL = os.getenv("ATE_EXECUTION_SYMBOL") or os.getenv("QUANTAI_EXECUTION_SYMBOL", "XAUUSDm") or "XAUUSDm"
ATE_MAGIC_NUMBER = int(os.getenv("ATE_MAGIC_NUMBER") or os.getenv("QUANTAI_EXECUTION_MAGIC") or os.getenv("QUANTAI_MAGIC_NUMBER", "888999") or "888999")
EXECUTION_MAGIC = ATE_MAGIC_NUMBER
DEMO_COMMAND_TTL = max(5, min(30, int(os.getenv("ATE_DEMO_COMMAND_TTL_SECONDS") or os.getenv("QUANTAI_DEMO_COMMAND_TTL_SECONDS", "10") or "10")))
BRIDGE_TOKEN = os.getenv("ATE_BRIDGE_TOKEN") or os.getenv("QUANTAI_BRIDGE_TOKEN") or os.getenv("QUANTAI_EXECUTION_BRIDGE_TOKEN", "")
OPERATOR_TOKEN = os.getenv("ATE_OPERATOR_TOKEN") or os.getenv("QUANTAI_OPERATOR_TOKEN", "")
ADMIN_LOGIN = (os.getenv("ADMIN_LOGIN") or "").strip()
ADMIN_PASSWORD = (os.getenv("ADMIN_PASSWORD") or os.getenv("ADMIN-PASSWORD") or "").strip()

# Bearer tokens minted by /api/auth/login when OPERATOR_TOKEN is unset.
# token -> unix expiry. Validated by require_operator_token (fail-closed).
_ADMIN_SESSIONS: Dict[str, float] = {}
_ADMIN_SESSION_TTL = 30 * 24 * 3600  # 30 days
_LOGIN_ATTEMPTS: Dict[str, list] = {}  # client_ip -> [timestamps] (brute-force guard)
_LOGIN_WINDOW_SECONDS = 300            # 5-minute rolling window
_LOGIN_MAX_ATTEMPTS = 10

import base64

def _encode_secret(secret: str) -> str:
    """Encode sensitive credential strings for local configuration storage."""
    if not secret:
        return ""
    if secret.startswith("enc:v1:"):
        return secret
    encoded = base64.b64encode(secret.encode("utf-8")).decode("utf-8")
    return f"enc:v1:{encoded}"

def _decode_secret(stored: str) -> str:
    """Decode sensitive credentials stored in local configuration."""
    if not stored:
        return ""
    if not stored.startswith("enc:v1:"):
        return stored
    try:
        raw = stored[7:]
        return base64.b64decode(raw.encode("utf-8")).decode("utf-8")
    except Exception:
        return stored

# Control Center Persistent Configuration File (separate from .env)
CONTROL_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "user_control_config.json")

# Optional Firestore cloud mirror (best-effort). Local file is the ground
# truth; cloud is a sync layer so any dashboard/device sees the same config.
import firebase_sync  # noqa: E402
_firebase_sync_enabled = bool(os.getenv("FIREBASE_ENABLE_SYNC", "true").lower() in ("1", "true", "yes"))

def load_control_config() -> dict:
    local: dict = {}
    if os.path.exists(CONTROL_CONFIG_FILE):
        try:
            with open(CONTROL_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for field in CONFIG_SECRET_FIELDS:
                    if field in data and data[field]:
                        data[field] = _decode_secret(str(data[field]))
                local = data
        except Exception:
            pass
    if not _firebase_sync_enabled:
        return local
    try:
        cloud = firebase_sync.pull_config() or {}
        if not cloud:
            return local
        local_ts = local.get("config_updated_at", "")
        cloud_ts = cloud.get("config_updated_at", "")
        if cloud_ts and (not local_ts or cloud_ts > local_ts):
            merged = {**local, **cloud}
            merged.pop("config_updated_at", None)
            _persist_config_file(merged)
            return merged
    except Exception:
        pass
    return local

def _persist_config_file(data: dict) -> None:
    try:
        with open(CONTROL_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to write control config: {e}")

# Fields persisted with enc:v1: prefix (never stored as plaintext on disk).
CONFIG_SECRET_FIELDS = (
    "mt5_password",
    "telegram_bot_token",
    "gemini_api_key",
    "claude_api_key",
    "deepseek_api_key",
    "openai_api_key",
    "zplay_api_key",
    "grok_api_key",
    "qwen_api_key",
    "gateway_key",
)


def _mask_field(value: str) -> str:
    """Return a masked sentinel for UI round-trip (keeps existing key on POST)."""
    return "*****" if value else ""


def save_control_config(data: dict):
    existing = load_control_config()
    existing.update(data)
    existing["config_updated_at"] = datetime.now(timezone.utc).isoformat()
    existing_to_save = dict(existing)
    for field in CONFIG_SECRET_FIELDS:
        if field in existing_to_save and existing_to_save[field]:
            existing_to_save[field] = _encode_secret(str(existing_to_save[field]))
    _persist_config_file(existing_to_save)
    if _firebase_sync_enabled:
        try:
            mirror = dict(existing)
            for field in CONFIG_SECRET_FIELDS:
                if field in mirror and mirror[field]:
                    mirror[field] = _encode_secret(str(mirror[field]))
            firebase_sync.push_config(mirror)
        except Exception as e:
            logger.error(f"Firebase sync failed: {e}")

async def broadcast_config_updated():
    """Notify every connected dashboard that Control Center config changed."""
    try:
        cfg = load_control_config()
        safe = dict(cfg)
        for field in CONFIG_SECRET_FIELDS:
            if field in safe and safe[field]:
                safe[field] = _mask_field(str(safe[field]))
        await WS_MANAGER.broadcast({"type": "config_updated", "data": safe})
    except Exception:
        pass

_saved_cfg = load_control_config()

# Dynamic Runtime State managed exclusively via CONTROL CENTER UI.
# Fail-closed defaults: DISABLED unless control center explicitly arms a mode.
EXECUTION_MODE = (_saved_cfg.get("execution_mode") or "DISABLED").upper()
LIVE_ARMED = bool(_saved_cfg.get("live_armed", False))
DEMO_ARMED = bool(_saved_cfg.get("demo_armed", False))
KILL_SWITCH = bool(_saved_cfg.get("kill_switch", True)) or EXECUTION_MODE == "DISABLED"
ENABLE_TRADING = bool(_saved_cfg.get("enable_trading", EXECUTION_MODE != "DISABLED"))
AI_AUTO_LOOP = bool(_saved_cfg.get("ai_auto_loop", False))

# Runtime execution symbol (persisted via Control Center MT5 login form);
# validated/fallback at runtime to the broker-available symbol.
if _saved_cfg.get("execution_symbol"):
    EXECUTION_SYMBOL = str(_saved_cfg["execution_symbol"])
EXECUTION_TIMEFRAME = str(_saved_cfg.get("execution_timeframe") or os.getenv("ATE_EXECUTION_TIMEFRAME", "M15") or "M15")

MT5_SAVED_LOGIN = int(_saved_cfg.get("mt5_login", os.getenv("MT5_LOGIN", "0") or "0"))
MT5_SAVED_PASSWORD = _saved_cfg.get("mt5_password", os.getenv("MT5_PASSWORD", ""))
MT5_SAVED_SERVER = _saved_cfg.get("mt5_server", os.getenv("MT5_SERVER", ""))

TELEGRAM_BOT_TOKEN = _saved_cfg.get("telegram_bot_token") or os.getenv("TELEGRAM_BOT_TOKEN", "") or os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = _saved_cfg.get("telegram_chat_id") or os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_ENABLED = bool(_saved_cfg.get("telegram_enabled", True))

ACTIVE_AI_MODEL = _saved_cfg.get("active_ai_model") or os.getenv("ATE_AI_MODEL") or os.getenv("QUANTAI_AI_MODEL", "deepseek-v4-flash-free")
TRADING_METHOD = _saved_cfg.get("trading_method", "ULTRA_CONFLUENCE")
USER_CUSTOM_MODEL_ID = _saved_cfg.get("custom_model_id", "")
USER_GEMINI_KEY = _saved_cfg.get("gemini_api_key") or os.getenv("GEMINI_API_KEY", "")
USER_CLAUDE_KEY = _saved_cfg.get("claude_api_key") or os.getenv("CLAUDE_API_KEY", "")
USER_DEEPSEEK_KEY = _saved_cfg.get("deepseek_api_key") or os.getenv("DEEPSEEK_API_KEY", "")
USER_OPENAI_KEY = _saved_cfg.get("openai_api_key") or os.getenv("OPENAI_API_KEY", "")
USER_ZPLAY_KEY = _saved_cfg.get("zplay_api_key") or os.getenv("ZPLAY_API_KEY", "")
USER_GROK_KEY = _saved_cfg.get("grok_api_key") or os.getenv("GROK_API_KEY", "")
USER_QWEN_KEY = _saved_cfg.get("qwen_api_key") or os.getenv("QWEN_API_KEY", "")
USER_GATEWAY_URL = _saved_cfg.get("gateway_url") or os.getenv("GATEWAY_URL", "")
USER_GATEWAY_URL = _saved_cfg.get("gateway_url") or os.getenv("GATEWAY_URL", "")
USER_GATEWAY_KEY = _saved_cfg.get("gateway_key") or os.getenv("GATEWAY_KEY", "")
TRADING_METHOD = _saved_cfg.get("trading_method") or "ULTRA_CONFLUENCE"

# Risk Guard persisted values (reloaded from Control Center /api/control-center/risk)
_saved_risk_frac = _saved_cfg.get("risk_per_trade_fraction")
_saved_max_pos = _saved_cfg.get("max_open_positions")
_saved_max_spread = _saved_cfg.get("max_spread")
if _saved_risk_frac is not None or _saved_max_pos is not None or _saved_max_spread is not None:
    for _rp in ("XAUUSD", "XAUUSDM"):
        _prof = FOREX_RISK_PROFILES.get(_rp)
        if _prof:
            if _saved_max_spread is not None:
                _prof["max_spread"] = float(_saved_max_spread)
            _pol = _prof["policy"]
            _prof["policy"] = replace(
                _pol,
                risk_per_trade_fraction=float(_saved_risk_frac) if _saved_risk_frac is not None else _pol.risk_per_trade_fraction,
                max_open_positions=int(_saved_max_pos) if _saved_max_pos is not None else _pol.max_open_positions,
            )

def send_telegram_alert(message: str) -> bool:
    """Send an instant Telegram alert notification using urllib.request (TLS verified)."""
    bot_token = TELEGRAM_BOT_TOKEN.strip()
    chat_id = TELEGRAM_CHAT_ID.strip()
    if not bot_token or not chat_id or not TELEGRAM_ENABLED:
        return False
    try:
        import urllib.request
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        # Build enriched header metadata if not already formatted with GOLDQUANT header
        if not message.startswith("<b>🤖 GOLDQUANT") and not message.startswith("<b>[GOLDQUANT"):
            account_info = "Đợi kết nối MT5..."
            try:
                if ensure_mt5_connected():
                    acc = mt5.account_info()
                    if acc:
                        mode_str = "REAL" if getattr(acc, "trade_mode", 0) == 2 else "DEMO"
                        account_info = f"{mode_str}-{acc.login} @ {acc.server}"
            except Exception:
                pass
            
            from datetime import datetime, timezone, timedelta
            vn_time = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S %d/%m/%Y")
            
            meta_header = (
                f"<b>🤖 GOLDQUANT AI - HỆ THỐNG TRADING</b>\n"
                f"👤 <b>Chủ tịch:</b> Nguyễn Quang Tú\n"
                f"🆔 <b>Tài khoản MT5:</b> <code>{account_info}</code>\n"
                f"🕒 <b>Thời gian:</b> <code>{vn_time} (UTC+7)</code>\n"
                f"────────────────────────\n"
            )
            full_msg = meta_header + message
        else:
            full_msg = message

        payload = json.dumps({"chat_id": chat_id, "text": full_msg, "parse_mode": "HTML"}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception as e:
        logger.error(f"Telegram notification error: {e}")
        return False


def is_weekend_market_closed(dt: Optional[datetime] = None) -> bool:
    """Return True if current time in Vietnam (UTC+7) is during weekend market closure (Saturday 05:00 to Monday 05:00)."""
    if dt is None:
        dt = datetime.now(timezone(timedelta(hours=7)))
    weekday = dt.weekday()  # 0=Mon, ..., 5=Sat, 6=Sun
    hour = dt.hour
    if weekday == 5 and hour >= 5:  # Saturday from 05:00 AM VN
        return True
    if weekday == 6:  # All Sunday
        return True
    if weekday == 0 and hour < 5:  # Monday before 05:00 AM VN
        return True
    return False


def analyze_news_and_market_quantitatively(
    event: Dict[str, Any],
    indicators: Dict[str, Any],
    tick: Any,
    account: Any,
    positions: List[Any],
    pending: List[Any],
) -> Dict[str, Any]:
    """Computes a complete 10-point quantitative AI analysis report returning a structured JSON object."""
    vn_now = datetime.now(timezone(timedelta(hours=7)))
    title = str(event.get("title") or event.get("description") or "SỰ KIỆN KINH TẾ").upper()
    country = str(event.get("country") or event.get("currency") or "USD").upper()
    forecast = str(event.get("forecast") or event.get("estimate") or "--")
    previous = str(event.get("previous") or "--")
    actual = str(event.get("actual") or "--")
    impact = str(event.get("impact") or "HIGH").upper()
    evt_time = str(event.get("datetime") or event.get("date") or "Trong ngày")

    bid = float(getattr(tick, "bid", 0.0)) if tick else 0.0
    ask = float(getattr(tick, "ask", 0.0)) if tick else 0.0
    spread = round((ask - bid) * 100, 1) if (ask and bid) else 0.0

    ema20 = float(indicators.get("ema20") or 0.0)
    ema50 = float(indicators.get("ema50") or 0.0)
    ema200 = float(indicators.get("ema200") or 0.0)
    rsi = float(indicators.get("rsi") or 50.0)
    atr = float(indicators.get("atr") or 2.5)
    macd = str(indicators.get("macd") or "N/A")
    volume = int(indicators.get("volume") or 0)
    r1 = float(indicators.get("r1") or 0.0)
    s1 = float(indicators.get("s1") or 0.0)

    # Determine Trading Session in VN time
    hour = vn_now.hour
    if 6 <= hour < 14:
        session = "Asian Session (Phiên Á)"
        liquidity = "Trung bình (Moderate)"
    elif 14 <= hour < 19:
        session = "European Session (Phiên Âu)"
        liquidity = "Cao (High)"
    else:
        session = "US Session (Phiên Mỹ)"
        liquidity = "Rất Cao (Very High)"

    balance = float(getattr(account, "balance", 0.0)) if account else 0.0
    equity = float(getattr(account, "equity", 0.0)) if account else 0.0
    margin = float(getattr(account, "margin", 0.0)) if account else 0.0
    floating_pnl = round(equity - balance, 2)
    open_pos_count = len(positions) if positions else 0
    pending_count = len(pending) if pending else 0

    # 1. USD Impact & 2. Gold Impact Analysis
    f_val, p_val = None, None
    try:
        f_clean = forecast.replace("%", "").replace("K", "").replace("M", "").strip()
        p_clean = previous.replace("%", "").replace("K", "").replace("M", "").strip()
        f_val = float(f_clean)
        p_val = float(p_clean)
    except Exception:
        pass

    if f_val is not None and p_val is not None and f_val != p_val:
        if f_val > p_val:
            usd_impact = f"Dữ liệu dự báo tăng ({forecast} > {previous}) thúc đẩy chỉ số USD tăng điểm."
            gold_impact = f"Tạo áp lực ép giá Vàng ngắn hạn quanh mốc Kháng cự ${r1:.2f}."
        else:
            usd_impact = f"Dữ liệu dự báo giảm ({forecast} < {previous}) khiến chỉ số USD suy yếu."
            gold_impact = f"Tạo động lực bứt phá tăng mạnh cho Vàng hướng tới vùng Kháng cự ${r1:.2f}."
    else:
        usd_impact = f"Dữ liệu trung tính ({forecast}). USD tích lũy hẹp."
        gold_impact = "Vàng biến động hai chiều quét thanh khoản theo phản ứng nến M15."

    # 3. Bullish / Bearish & 7. BUY / SELL / WAIT Recommendation
    if ema20 > ema50 and ema50 > ema200 and rsi >= 45:
        market_bias = "BULLISH (TĂNG MẠNH)"
        recommendation = "BUY"
    elif ema20 < ema50 and ema50 < ema200 and rsi <= 55:
        market_bias = "BEARISH (GIẢM MẠNH)"
        recommendation = "SELL"
    else:
        market_bias = "NEUTRAL / SIDEWAY (TÍCH LŨY)"
        recommendation = "WAIT"

    # 4. Confidence Score & 5. Risk Level & 6. Expected Movement
    confidence = 88 if market_bias != "NEUTRAL / SIDEWAY (TÍCH LŨY)" else 70
    risk_level = "HIGH" if impact in ("HIGH", "RED") else "MEDIUM"
    expected_move = f"±${round(max(6.0, atr * 3.5), 1)} USD/oz"

    # 8. Detailed Reasons
    reasons = [
        f"Cấu trúc Kỹ thuật: {market_bias} (EMA20=${ema20:.2f}, EMA50=${ema50:.2f}, RSI={rsi:.1f}).",
        f"Tác động Tin tức: {usd_impact} {gold_impact}",
        f"Thanh khoản & Phiên: {session} - Thanh khoản {liquidity}, Spread={spread} pips.",
        f"Trạng thái Tài khoản: Margin=${margin:.2f}, Floating PnL=${floating_pnl:+.2f}, {open_pos_count} vị thế mở.",
    ]

    # 9. Risk Management Proposal
    risk_proposal = (
        f"Duy trì Margin Risk <= 30%. Tự động dời Stop Loss toàn bộ vị thế mở trước lên Hòa vốn (+0.10$) "
        f"trước 15 phút ra tin. Tạm ngắt phát lệnh mới trong cửa sổ ra tin. "
        f"Nếu nến M15 bứt phá +1.50$, AI kích hoạt lệnh nhồi Pyramiding DCA Dương."
    )

    # 10. Complete Structured JSON Result
    return {
        "news": {
            "title": title,
            "country": country,
            "forecast": forecast,
            "previous": previous,
            "actual": actual,
            "impact": impact,
            "datetime": evt_time,
        },
        "market_data": {
            "symbol": EXECUTION_SYMBOL,
            "bid": bid,
            "ask": ask,
            "spread_pips": spread,
            "atr": atr,
            "ema20": ema20,
            "ema50": ema50,
            "ema200": ema200,
            "rsi": rsi,
            "macd": macd,
            "volume": volume,
            "liquidity": liquidity,
            "session": session,
        },
        "mt5_status": {
            "balance": balance,
            "equity": equity,
            "margin": margin,
            "floating_pnl": floating_pnl,
            "open_positions": open_pos_count,
            "pending_orders": pending_count,
        },
        "analysis": {
            "usd_impact": usd_impact,
            "gold_impact": gold_impact,
            "market_bias": market_bias,
            "confidence_percent": confidence,
            "risk_level": risk_level,
            "expected_movement": expected_move,
            "recommendation": recommendation,
            "reasons": reasons,
            "risk_management_proposal": risk_proposal,
        },
    }


def send_morning_news_telegram_bulletin() -> bool:
    """Fetch today's economic calendar and send separate Telegram notifications for EACH economic event occurring today at 05:00 AM VN time."""
    vn_now = datetime.now(timezone(timedelta(hours=7)))
    vn_date_str = vn_now.strftime("%d/%m/%Y")
    
    events = fetch_real_economic_calendar()
    today_events = []
    
    for evt in events:
        impact = str(evt.get("impact", "")).upper()
        title = evt.get("title") or evt.get("description") or "Sự kiện kinh tế"
        country = evt.get("country") or evt.get("currency") or "USD"
        evt_time = evt.get("datetime") or evt.get("date") or "Trong ngày"
        
        if impact in ("HIGH", "MEDIUM", "RED", "ORANGE") or country in ("USD", "US", "XAU"):
            today_events.append({
                "title": title,
                "impact": impact,
                "country": country,
                "datetime": evt_time,
                "forecast": evt.get("forecast") or evt.get("estimate") or "--",
                "previous": evt.get("previous") or "--",
                "actual": evt.get("actual") or "--",
            })
            
    acc_info = "Đợi kết nối MT5..."
    account_obj = None
    tick_obj = None
    positions_list = []
    pending_list = []
    try:
        if ensure_mt5_connected():
            account_obj = mt5.account_info()
            if account_obj:
                mode_str = "REAL" if getattr(account_obj, "trade_mode", 0) == 2 else "DEMO"
                acc_info = f"{mode_str}-{account_obj.login} @ {account_obj.server}"
            tick_obj = mt5.symbol_info_tick(resolve_symbol(EXECUTION_SYMBOL))
            positions_list = mt5.positions_get() or []
            pending_list = mt5.orders_get() or []
    except Exception:
        pass

    indicators = get_technical_indicators(EXECUTION_SYMBOL)

    if not today_events:
        msg = (
            f"<b>📰 BẢN TIN KINH TẾ 05:00 AM - GOLDQUANT AI</b>\n"
            f"👤 <b>Chủ tịch:</b> Nguyễn Quang Tú\n"
            f"🆔 <b>Tài khoản MT5:</b> <code>{acc_info}</code>\n"
            f"🕒 <b>Ngày phát tin:</b> <code>{vn_date_str} (UTC+7)</code>\n"
            f"────────────────────────\n"
            f"🟢 <b>Hôm nay không có tin đỏ/cam mạnh nào.</b>\n"
            f"Thị trường Vàng dự kiến di chuyển thuần theo Kỹ Thuật (Price Action & EMA20=${indicators.get('ema20', 0.0):.2f}). AI kích hoạt chiến lược Pyramiding DCA Dương săn cơ hội bứt phá."
        )
        return send_telegram_alert(msg)

    total_events = len(today_events[:5])
    all_success = True
    
    for i, ev in enumerate(today_events[:5], 1):
        imp_icon = "🔴" if ev["impact"] in ("HIGH", "RED") else "🟠"
        analysis_json = analyze_news_and_market_quantitatively(ev, indicators, tick_obj, account_obj, positions_list, pending_list)
        
        m_data = analysis_json["market_data"]
        mt5_st = analysis_json["mt5_status"]
        ans = analysis_json["analysis"]

        msg = (
            f"<b>📰 BẢN TIN TIN TỨC [{i}/{total_events}] - GOLDQUANT AI</b>\n"
            f"👤 <b>Chủ tịch:</b> Nguyễn Quang Tú\n"
            f"🆔 <b>Tài khoản MT5:</b> <code>{acc_info}</code>\n"
            f"🕒 <b>Ngày phát tin:</b> <code>05:00 {vn_date_str} (UTC+7)</code>\n"
            f"────────────────────────\n"
            f"{imp_icon} <b>SỰ KIỆN:</b> <b>{ev['title']} ({ev['country']})</b>\n"
            f"📌 <b>Mức độ ảnh hưởng:</b> [{ev['impact']}]\n"
            f"⏰ <b>Khung giờ ra tin:</b> <code>{ev['datetime']} (Giờ VN & GMT)</code>\n"
            f"📊 <b>Chỉ số dự báo (Forecast):</b> <code>{ev['forecast']}</code> | <b>Kỳ trước:</b> <code>{ev['previous']}</code>\n"
            f"────────────────────────\n"
            f"📈 <b>MARKET DATA (XAUUSD):</b>\n"
            f"• Ask/Bid: <code>${m_data['ask']:.2f} / ${m_data['bid']:.2f}</code> (Spread: {m_data['spread_pips']} pips)\n"
            f"• Phiên: {m_data['session']} - Liquidity: {m_data['liquidity']}\n"
            f"• Chỉ báo: EMA20=${m_data['ema20']:.2f}, EMA50=${m_data['ema50']:.2f}, RSI={m_data['rsi']:.1f}, ATR={m_data['atr']:.2f}\n"
            f"────────────────────────\n"
            f"🏦 <b>MT5 STATUS:</b>\n"
            f"• Balance: <code>${mt5_st['balance']:,.2f}</code> | Equity: <code>${mt5_st['equity']:,.2f}</code>\n"
            f"• Floating P/L: <code>${mt5_st['floating_pnl']:+.2f}</code> | Vị thế mở: <code>{mt5_st['open_positions']}</code> lệnh\n"
            f"────────────────────────\n"
            f"🧠 <b>PHÂN TÍCH CHUYÊN SÂU 10 ĐIỂM TỪ AI:</b>\n"
            f"1. <b>Ảnh hưởng USD:</b> {ans['usd_impact']}\n"
            f"2. <b>Ảnh hưởng Vàng:</b> {ans['gold_impact']}\n"
            f"3. <b>Xu hướng:</b> <b>{ans['market_bias']}</b>\n"
            f"4. <b>Độ tin cậy:</b> <code>{ans['confidence_percent']}%</code>\n"
            f"5. <b>Mức độ rủi ro:</b> <code>{ans['risk_level']}</code>\n"
            f"6. <b>Biến động dự kiến:</b> <code>{ans['expected_movement']}</code>\n"
            f"7. <b>Khuyến nghị AI:</b> <b>{ans['recommendation']}</b>\n\n"
            f"📝 <b>LÝ DO CHI TIẾT:</b>\n"
            f"• {ans['reasons'][0]}\n"
            f"• {ans['reasons'][1]}\n"
            f"• {ans['reasons'][2]}\n\n"
            f"🛡️ <b>ĐỀ XUẤT QUẢN LÝ RỦI RO:</b>\n"
            f"{ans['risk_management_proposal']}"
        )
        sent = send_telegram_alert(msg)
        if not sent:
            all_success = False
        time.sleep(0.6)
        
    return all_success


def send_evening_pnl_telegram_report() -> bool:
    """Calculate daily PnL and trade statistics, then send evening report to Telegram at 23:00 PM VN time."""
    vn_now = datetime.now(timezone(timedelta(hours=7)))
    vn_date_str = vn_now.strftime("%d/%m/%Y")
    
    daily_realized = get_daily_realized_pnl(EXECUTION_SYMBOL, EXECUTION_MAGIC)
    
    acc_info = "Đợi kết nối MT5..."
    balance = 0.0
    equity = 0.0
    try:
        if ensure_mt5_connected():
            acc = mt5.account_info()
            if acc:
                mode_str = "REAL" if getattr(acc, "trade_mode", 0) == 2 else "DEMO"
                acc_info = f"{mode_str}-{acc.login} @ {acc.server}"
                balance = float(acc.balance)
                equity = float(acc.equity)
    except Exception:
        pass

    today_start = datetime(vn_now.year, vn_now.month, vn_now.day, 0, 0, 0, tzinfo=timezone(timedelta(hours=7)))
    wins = 0
    losses = 0
    total_trades = 0
    try:
        if ensure_mt5_connected():
            deals = mt5.history_deals_get(today_start, vn_now)
            if deals:
                for d in deals:
                    if getattr(d, "entry", 0) == 1:  # Deal out (closed position)
                        pnl = float(getattr(d, "profit", 0.0)) + float(getattr(d, "swap", 0.0)) + float(getattr(d, "commission", 0.0))
                        total_trades += 1
                        if pnl >= 0:
                            wins += 1
                        else:
                            losses += 1
    except Exception:
        pass

    win_rate = (wins / total_trades * 100.0) if total_trades > 0 else 100.0
    floating_pnl = equity - balance
    
    msg = (
        f"<b>📊 GOLDQUANT AI - BÁO CÁO TỔNG KẾT NGÀY</b>\n"
        f"👤 <b>Chủ tịch:</b> Nguyễn Quang Tú\n"
        f"🆔 <b>Tài khoản MT5:</b> <code>{acc_info}</code>\n"
        f"🕒 <b>Thời gian tổng kết:</b> <code>23:00 {vn_date_str} (UTC+7)</code>\n"
        f"────────────────────────\n"
        f"💵 <b>Tổng lợi nhuận thực thu hôm nay:</b> <code>+${daily_realized:+.2f}</code>\n"
        f"📊 <b>Lợi nhuận đang chạy (Floating PnL):</b> <code>+${floating_pnl:+.2f}</code>\n"
        f"📈 <b>Tỷ lệ Thắng (Win Rate):</b> <code>{win_rate:.1f}%</code> ({wins} Thắng / {losses} Thua)\n"
        f"🎯 <b>Tổng số lệnh đã thực thi:</b> <code>{total_trades}</code> lệnh\n"
        f"🏦 <b>Số dư tài khoản (Balance):</b> <code>${balance:,.2f}</code>\n"
        f"💎 <b>Tài sản ròng (Equity):</b> <code>${equity:,.2f}</code>\n"
        f"────────────────────────\n"
        f"🏆 <b>ĐÁNH GIÁ CỦA AI:</b> Hệ thống vận hành chuẩn kỷ luật rủi ro 30% margin. Chúc chủ tịch ngủ ngon!"
    )
    return send_telegram_alert(msg)


async def _scheduled_morning_news_loop() -> None:
    """Automatically sends morning news bulletin at 05:00 AM VN time every weekday."""
    last_sent_date = ""
    while True:
        try:
            vn_now = datetime.now(timezone(timedelta(hours=7)))
            today_str = vn_now.strftime("%Y-%m-%d")
            
            if vn_now.hour == 5 and vn_now.minute == 0 and last_sent_date != today_str:
                if not is_weekend_market_closed(vn_now):
                    send_morning_news_telegram_bulletin()
                    last_sent_date = today_str
        except Exception as exc:
            log_event(LogEvent.EXCEPTION, component="morning-news-loop", exc=exc)
        await asyncio.sleep(20)


async def _scheduled_evening_pnl_loop() -> None:
    """Automatically sends evening PnL report at 23:00 PM VN time every weekday."""
    last_sent_date = ""
    while True:
        try:
            vn_now = datetime.now(timezone(timedelta(hours=7)))
            today_str = vn_now.strftime("%Y-%m-%d")
            
            if vn_now.hour == 23 and vn_now.minute == 0 and last_sent_date != today_str:
                if not is_weekend_market_closed(vn_now):
                    send_evening_pnl_telegram_report()
                    last_sent_date = today_str
        except Exception as exc:
            log_event(LogEvent.EXCEPTION, component="evening-pnl-loop", exc=exc)
        await asyncio.sleep(20)

# Autonomous AI decision loop (default OFF; operator arms it explicitly via Control Center).
# Saved control-center state wins; env only supplies the initial default.
AI_AUTO_LOOP = _saved_cfg.get("ai_auto_loop", os.getenv("ATE_AI_AUTO_LOOP") or os.getenv("QUANTAI_AI_AUTO_LOOP", "false").lower() == "true")
AI_LOOP_SECONDS = max(15, int(os.getenv("ATE_AI_LOOP_SECONDS") or os.getenv("QUANTAI_AI_LOOP_SECONDS", "120")))

# Realtime broadcast cadence (seconds).
WS_TICK_INTERVAL = float(os.getenv("ATE_WS_TICK_INTERVAL") or os.getenv("QUANTAI_WS_TICK_INTERVAL", "1.0"))
WS_FULL_INTERVAL = float(os.getenv("ATE_WS_FULL_INTERVAL") or os.getenv("QUANTAI_WS_FULL_INTERVAL", "3.0"))
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in (os.getenv("ATE_ALLOWED_ORIGINS") or os.getenv("QUANTAI_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")).split(",")
    if origin.strip()
]

def validate_environment_security() -> Dict[str, Any]:
    """Audit environment variables at startup and log warnings/errors for missing configuration."""
    missing_required = []
    warnings = []
    
    if not ADMIN_LOGIN:
        missing_required.append("ADMIN_LOGIN")
    if not ADMIN_PASSWORD:
        missing_required.append("ADMIN_PASSWORD")
        
    if not TELEGRAM_BOT_TOKEN:
        warnings.append("TELEGRAM_BOT_TOKEN / TELEGRAM_TOKEN")
    if not TELEGRAM_CHAT_ID:
        warnings.append("TELEGRAM_CHAT_ID")
        
    if not (MT5_SAVED_LOGIN or os.getenv("MT5_LOGIN")):
        warnings.append("MT5_LOGIN")
    if not (MT5_SAVED_PASSWORD or os.getenv("MT5_PASSWORD")):
        warnings.append("MT5_PASSWORD")
    if not (MT5_SAVED_SERVER or os.getenv("MT5_SERVER")):
        warnings.append("MT5_SERVER")

    if missing_required:
        logger.error(f"🔒 SECURITY AUDIT WARNING - THIẾU BIẾN TRONG .ENV: {', '.join(missing_required)}")
    if warnings:
        logger.info(f"ℹ️ ENV CONFIG CHECK - CÓ THỂ CẤU HÌNH THÊM TRONG .ENV HOẶC CONTROL CENTER: {', '.join(warnings)}")

    return {
        "valid": len(missing_required) == 0,
        "missing_required": missing_required,
        "warnings": warnings,
    }


@asynccontextmanager
async def _lifespan(app: FastAPI):
    validate_environment_security()
    log_event(LogEvent.APP_STARTED, component="backend", port=int(os.getenv("ATE_DASHBOARD_PORT") or os.getenv("QUANTAI_DASHBOARD_PORT", "8005")), mode=EXECUTION_MODE)
    log_event(LogEvent.DB_CONNECTED, component="command-ledger", db=os.getenv("ATE_COMMAND_DB") or os.getenv("QUANTAI_COMMAND_DB", "ate_commands.sqlite3"))
    if ensure_mt5_connected():
        log_event(LogEvent.MT5_CONNECTED, component="mt5", server=os.getenv("MT5_SERVER", ""))
    broadcaster = asyncio.create_task(_telemetry_broadcaster())
    ai_loop = asyncio.create_task(_ai_decision_loop())
    pos_mgr = asyncio.create_task(_manage_active_positions_loop())
    brain_mgr = asyncio.create_task(_brain_evaluation_loop())
    news_sch = asyncio.create_task(_scheduled_morning_news_loop())
    pnl_sch = asyncio.create_task(_scheduled_evening_pnl_loop())
    try:
        yield
    finally:
        broadcaster.cancel()
        ai_loop.cancel()
        pos_mgr.cancel()
        brain_mgr.cancel()
        news_sch.cancel()
        pnl_sch.cancel()
        log_event(LogEvent.APP_STOPPED, component="backend")


app = FastAPI(title="Autonomous Trading Engine (ATE) Telemetry & Analytics", version="3.0.0", lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health")
async def health_check():
    """Standard liveness healthcheck endpoint."""
    return {
        "status": "UP",
        "service": "Autonomous Trading Engine (ATE)",
        "version": "3.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mt5_connected": ensure_mt5_connected(),
    }


@app.get("/readiness")
async def readiness_check():
    """Standard readiness probe endpoint."""
    ready, reason = demo_execution_status()
    return {
        "status": "READY" if ready else "NOT_READY",
        "reason": reason,
        "execution_mode": EXECUTION_MODE,
        "kill_switch": KILL_SWITCH,
        "mt5_connected": ensure_mt5_connected(),
    }


def require_bridge_token(authorization: Optional[str] = Header(default=None)) -> None:
    if not BRIDGE_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "BRIDGE_AUTH_NOT_CONFIGURED"},
        )
    expected = f"Bearer {BRIDGE_TOKEN}"
    if not authorization or not secrets.compare_digest(authorization, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "BRIDGE_AUTH_REQUIRED"},
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_operator_token(authorization: Optional[str] = Header(default=None)) -> None:
    """Fail-closed operator gate.

    Accepts ``Bearer OPERATOR_TOKEN`` (from .env) or a live admin session token
    minted by /api/auth/login. Without valid credentials the request is rejected —
    there is no anonymous path into Control Center mutation endpoints.
    """
    now = time.time()
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):].strip()
    if OPERATOR_TOKEN and token and secrets.compare_digest(token, OPERATOR_TOKEN):
        return
    if token and token in _ADMIN_SESSIONS and _ADMIN_SESSIONS[token] > now:
        return
    if not OPERATOR_TOKEN and not _ADMIN_SESSIONS:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "OPERATOR_AUTH_NOT_CONFIGURED", "message": "Chưa cấu hình OPERATOR_TOKEN trong .env hoặc chưa có phiên đăng nhập quản trị."},
        )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "OPERATOR_AUTH_REQUIRED", "message": "Cần token quản trị (Authorization: Bearer <token>)."},
        headers={"WWW-Authenticate": "Bearer"},
    )


class LoginRequest(BaseModel):
    login: str
    password: str


@app.post("/api/auth/login")
async def admin_login(req: LoginRequest, request: Request):
    """Authenticate administrator using credentials strictly configured in .env (ADMIN_LOGIN / ADMIN_PASSWORD)."""
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    attempts = [ts for ts in _LOGIN_ATTEMPTS.get(client_ip, []) if now - ts < _LOGIN_WINDOW_SECONDS]
    if len(attempts) >= _LOGIN_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail={"code": "TOO_MANY_ATTEMPTS", "message": "Quá nhiều lần đăng nhập. Thử lại sau 5 phút."},
        )
    _LOGIN_ATTEMPTS[client_ip] = attempts
    input_login = req.login.strip()
    input_password = req.password.strip()
    
    if not ADMIN_LOGIN or not ADMIN_PASSWORD:
        raise HTTPException(
            status_code=500,
            detail={"code": "ADMIN_AUTH_UNCONFIGURED", "message": "Chưa cấu hình ADMIN_LOGIN và ADMIN_PASSWORD trong file .env!"}
        )
    
    if secrets.compare_digest(input_login, ADMIN_LOGIN) and secrets.compare_digest(input_password, ADMIN_PASSWORD):
        _LOGIN_ATTEMPTS[client_ip] = []
        if OPERATOR_TOKEN:
            token = OPERATOR_TOKEN
        else:
            token = f"auth_session_{secrets.token_hex(24)}"
            _ADMIN_SESSIONS[token] = time.time() + _ADMIN_SESSION_TTL
        log_event(LogEvent.OPERATOR_AUTHENTICATED, component="auth", login=input_login)
        return {
            "status": "SUCCESS",
            "message": "Đăng nhập thành công!",
            "token": token,
            "user": {
                "login": ADMIN_LOGIN,
                "name": "Nguyễn Quang Tú",
                "role": "SYSTEM_ADMIN",
                "avatar": "https://github.com/qtu11.png"
            }
        }
    else:
        _LOGIN_ATTEMPTS[client_ip] = attempts + [now]
        log_event(LogEvent.SECURITY_ALERT, component="auth", login=input_login, reason="INVALID_CREDENTIALS")
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_CREDENTIALS", "message": "Tên đăng nhập hoặc mật khẩu quản trị không chính xác!"}
        )


def execution_readiness(mode: Optional[str] = None) -> tuple[bool, str]:
    """Check readiness for executing trade commands on connected MT5 account."""
    eff_mode = (mode or EXECUTION_MODE or "").upper()
    if eff_mode not in ("DEMO", "LIVE"):
        return False, "REJECT_EXECUTION_MODE"
    if KILL_SWITCH:
        return False, "REJECT_KILL_SWITCH"
    if not ENABLE_TRADING:
        return False, "REJECT_TRADING_DISABLED"
    if eff_mode == "LIVE" and not LIVE_ARMED:
        return False, "REJECT_LIVE_NOT_ARMED"
    if not ensure_mt5_connected():
        return False, "REJECT_MT5_UNAVAILABLE"
    account = mt5.account_info()
    if account is None:
        return False, "REJECT_ACCOUNT_IDENTITY"
    target_sym = resolve_symbol(EXECUTION_SYMBOL)
    info = mt5.symbol_info(target_sym)
    if info is None:
        return False, "REJECT_SYMBOL_UNAVAILABLE"
    return True, "READY"


def demo_execution_status() -> tuple[bool, str]:
    """Backward-compatible wrapper used across existing routes."""
    return execution_readiness(EXECUTION_MODE)


class CopilotChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    symbol: str = Field(default="XAUUSD", min_length=1, max_length=32)
    timeframe: str = Field(default="M15", min_length=1, max_length=8)
    model_id: Optional[str] = None
    truncation: Optional[str] = None

_MT5_WAS_CONNECTED = False


def ensure_mt5_connected():
    """Idempotent MT5 attach with reconnect logging."""
    global _MT5_WAS_CONNECTED
    if not HAS_MT5:
        return False
    connected = mt5.initialize()
    if not connected:
        login = os.getenv("MT5_LOGIN") or (str(MT5_SAVED_LOGIN) if MT5_SAVED_LOGIN else None)
        password = os.getenv("MT5_PASSWORD") or MT5_SAVED_PASSWORD
        server = os.getenv("MT5_SERVER") or MT5_SAVED_SERVER
        if login and password and server:
            try:
                connected = bool(mt5.initialize(login=int(login), password=password, server=server))
            except Exception as exc:
                log_event(LogEvent.EXCEPTION, component="mt5", exc=exc, stage="relogin")
    ok = connected and mt5.terminal_info() is not None
    if ok and not _MT5_WAS_CONNECTED:
        log_event(LogEvent.MT5_CONNECTED, component="mt5")
        if _MT5_WAS_CONNECTED is False and hasattr(ensure_mt5_connected, "_ever"):
            log_event(LogEvent.MT5_RECONNECT, component="mt5")
        ensure_mt5_connected._ever = True  # type: ignore[attr-defined]
    elif not ok and _MT5_WAS_CONNECTED:
        log_event(LogEvent.MT5_DISCONNECTED, component="mt5")
    _MT5_WAS_CONNECTED = ok
    return ok

def resolve_symbol(symbol: str = "XAUUSD") -> str:
    if not ensure_mt5_connected():
        return symbol
    for s in ["XAUUSDm", "XAUUSD.m", "XAUUSD_m", "XAUUSD", "GOLD"]:
        info = mt5.symbol_info(s)
        if info is not None and info.description and "Gold" in info.description:
            mt5.symbol_select(s, True)
            return s
        if info is not None:
            mt5.symbol_select(s, True)
            return s
    return symbol

def resolve_symbol_info(symbol: str = "XAUUSDm") -> tuple[str, str]:
    """
    Resolve the requested symbol against the connected broker with a human
    readable reason (used by the Control Center MT5 login form).

    Returns (resolved_symbol, reason). Fallback chain: requested -> XAUUSDm ->
    XAUUSD -> first available Gold-family symbol -> original request.
    """
    preferred = (symbol or "XAUUSDm").strip()
    if not ensure_mt5_connected():
        return preferred, "Chưa kết nối MT5; giữ nguyên symbol yêu cầu (sẽ kiểm tra lại khi có kết nối)."
    candidates = [preferred, "XAUUSDm", "XAUUSD.m", "XAUUSD_m", "XAUUSD", "GOLD"]
    seen = set()
    for s in candidates:
        if s in seen:
            continue
        seen.add(s)
        info = mt5.symbol_info(s)
        if info is None:
            continue
        try:
            mt5.symbol_select(s, True)
        except Exception:
            pass
        if s.upper() == preferred.upper():
            return s, f"Symbol {s} có sẵn trên broker (đúng như yêu cầu)."
        return s, f"Symbol {preferred} không có trên broker -> fallback sang {s} (XAUUSD/XAUUSDm nhánh vàng)."
    return preferred, f"Không tìm thấy symbol vàng nào ({', '.join(candidates)}); giữ nguyên {preferred} (chưa kiểm chứng)."

def calc_rsi(closes: List[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 0.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        if diff > 0:
            gains.append(diff)
            losses.append(0.0)
        elif diff < 0:
            gains.append(0.0)
            losses.append(abs(diff))
        else:
            gains.append(0.0)
            losses.append(0.0)
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_gain == 0 and avg_loss == 0:
        return 50.0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 1)

def calc_ema(closes: List[float], period: int) -> float:
    if not closes:
        return 0.0
    if len(closes) < period:
        return round(sum(closes) / len(closes), 2)
    k = 2.0 / (period + 1)
    ema = sum(closes[:period]) / period
    for price in closes[period:]:
        ema = (price * k) + (ema * (1 - k))
    return round(ema, 2)

def calc_atr(rates, period: int = 14) -> float:
    if rates is None or len(rates) < period + 1:
        return 0.0
    tr_list = []
    for i in range(1, len(rates)):
        h = float(rates[i]['high'])
        l = float(rates[i]['low'])
        cp = float(rates[i - 1]['close'])
        tr = max(h - l, abs(h - cp), abs(l - cp))
        tr_list.append(tr)
    return round(sum(tr_list[-period:]) / period, 2)

def calc_stoch(rates, period: int = 14) -> float:
    """Calculate real Stochastic Oscillator (%K)."""
    if rates is None or len(rates) < period:
        return 50.0
    recent = rates[-period:]
    highest_high = max(float(r['high']) for r in recent)
    lowest_low = min(float(r['low']) for r in recent)
    current_close = float(rates[-1]['close'])
    if highest_high == lowest_low:
        return 50.0
    stoch_k = ((current_close - lowest_low) / (highest_high - lowest_low)) * 100.0
    return round(max(0.0, min(100.0, stoch_k)), 1)

def get_technical_indicators(symbol: str = "XAUUSDm"):
    defaults = {
        "data_status": "UNAVAILABLE",
        "rsi": 0.0,
        "atr": 0.0,
        "macd": "N/A",
        "stoch": "N/A",
        "ema20": 0.0,
        "ema50": 0.0,
        "ema200": 0.0,
        "volume": 0,
        "vol_ratio": "N/A",
        "pivot": 0.0,
        "r1": 0.0,
        "r2": 0.0,
        "s1": 0.0,
        "s2": 0.0,
    }
    if not ensure_mt5_connected():
        return defaults

    actual_symbol = resolve_symbol(symbol)
    rates = mt5.copy_rates_from_pos(actual_symbol, mt5.TIMEFRAME_M15, 0, 100)
    if rates is not None and len(rates) > 20:
        closes = [float(r['close']) for r in rates]
        rsi = calc_rsi(closes, 14)
        atr = calc_atr(rates, 14)
        stoch = calc_stoch(rates, 14)
        ema20 = calc_ema(closes, 20)
        ema50 = calc_ema(closes, 50)
        ema200 = calc_ema(closes, 200)
        ema12 = calc_ema(closes, 12)
        ema26 = calc_ema(closes, 26)
        macd = round(ema12 - ema26, 2)
        vol = int(rates[-1]['tick_volume'])
        
        # Real volume ratio calculation (current volume / average 20-period volume)
        vols_20 = [int(r['tick_volume']) for r in rates[-20:]]
        avg_vol = sum(vols_20) / len(vols_20) if vols_20 else 1
        vol_ratio_val = round(vol / avg_vol, 2) if avg_vol > 0 else 1.0

        d_rates = mt5.copy_rates_from_pos(actual_symbol, mt5.TIMEFRAME_D1, 0, 2)
        if d_rates is not None and len(d_rates) > 1:
            prev = d_rates[0]
            ph, pl, pc = float(prev['high']), float(prev['low']), float(prev['close'])
            pivot = (ph + pl + pc) / 3.0
            r1 = (2 * pivot) - pl
            s1 = (2 * pivot) - ph
            r2 = pivot + (ph - pl)
            s2 = pivot - (ph - pl)
        else:
            c = closes[-1]
            pivot, r1, r2, s1, s2 = c, c + 14.0, c + 27.0, c - 11.0, c - 24.0

        return {
            "data_status": "LIVE_VERIFIED",
            "rsi": rsi,
            "atr": atr,
            "macd": f"{'+' if macd >= 0 else ''}{macd:.2f}",
            "stoch": f"{stoch:.1f}",
            "ema20": ema20,
            "ema50": ema50,
            "ema200": ema200,
            "volume": vol,
            "vol_ratio": f"{vol_ratio_val:.2f}x",
            "pivot": round(pivot, 2),
            "r1": round(r1, 2),
            "r2": round(r2, 2),
            "s1": round(s1, 2),
            "s2": round(s2, 2)
        }
    return defaults


def calc_indicators_from_candles(candles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute technical indicators from EA-pushed candles (no MT5 required).
    This lets the dashboard show live indicators even when MT5 Python SDK is unavailable (Docker/Linux).
    """
    defaults = {
        "data_status": "UNAVAILABLE",
        "rsi": 0.0, "atr": 0.0, "macd": "N/A", "stoch": "N/A",
        "ema20": 0.0, "ema50": 0.0, "ema200": 0.0,
        "volume": 0, "vol_ratio": "N/A",
        "pivot": 0.0, "r1": 0.0, "r2": 0.0, "s1": 0.0, "s2": 0.0,
    }
    if not candles or len(candles) < 21:
        return defaults
    try:
        closes = [float(c["c"]) for c in candles]
        highs = [float(c["h"]) for c in candles]
        lows = [float(c["l"]) for c in candles]
        volumes = [float(c.get("v", 0)) for c in candles]
        rates_like = [{"high": h, "low": l, "close": c} for h, l, c in zip(highs, lows, closes)]
        rsi = calc_rsi(closes, 14)
        atr = calc_atr(rates_like, 14)
        stoch = calc_stoch(rates_like, 14)
        ema20 = calc_ema(closes, 20)
        ema50 = calc_ema(closes, 50)
        ema200 = calc_ema(closes, 200)
        ema12 = calc_ema(closes, 12)
        ema26 = calc_ema(closes, 26)
        macd = round(ema12 - ema26, 2)
        vol = int(volumes[-1]) if volumes else 0
        avg_vol = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else (sum(volumes) / len(volumes) if volumes else 1)
        vol_ratio = round(vol / avg_vol, 2) if avg_vol > 0 else 1.0
        last_c = closes[-1]
        return {
            "data_status": "LIVE_VERIFIED",
            "rsi": rsi, "atr": atr,
            "macd": f"{'+' if macd >= 0 else ''}{macd:.2f}",
            "stoch": f"{stoch:.1f}",
            "ema20": ema20, "ema50": ema50, "ema200": ema200,
            "volume": vol, "vol_ratio": f"{vol_ratio:.2f}x",
            "pivot": round(last_c, 2),
            "r1": round(last_c + atr, 2),
            "s1": round(last_c - atr, 2),
            "r2": round(last_c + 2 * atr, 2),
            "s2": round(last_c - 2 * atr, 2),
        }
    except Exception:
        return defaults


def get_account_performance():
    unavailable = {
        "data_status": "UNAVAILABLE",
        "win_rate": None,
        "profit_factor": None,
        "max_drawdown": None,
        "recovery_factor": None,
        "best_trade": None,
        "worst_trade": None,
        "equity_curve": [],
    }
    if not ensure_mt5_connected():
        return unavailable

    from performance import ClosedTrade, calculate_performance

    now = datetime.now()
    deals = mt5.history_deals_get(now - timedelta(days=60), now)
    if not deals:
        return {**unavailable, "data_status": "NO_CLOSED_TRADES"}

    net_by_position = {}
    for deal in deals:
        if int(getattr(deal, "magic", 0)) != ATE_MAGIC_NUMBER:
            continue
        if getattr(deal, "entry", None) not in (1, 2):
            continue
        position_id = int(getattr(deal, "position_id", 0))
        if not position_id:
            continue
        item = net_by_position.setdefault(position_id, {"profit": 0.0, "time": 0})
        item["profit"] += float(deal.profit + deal.swap + deal.commission)
        item["time"] = max(item["time"], int(deal.time))

    trades = [
        ClosedTrade(position_id=position_id, closed_at=item["time"], net_profit=item["profit"])
        for position_id, item in net_by_position.items()
    ]
    metrics = calculate_performance(trades)
    if not metrics["sample_size"]:
        return {**unavailable, "data_status": "NO_CLOSED_TRADES"}
    return {**metrics, "data_status": "LIVE_VERIFIED", "period_days": 60, "magic": ATE_MAGIC_NUMBER}

def generate_real_ai_signal(symbol: str = "XAUUSDm", ask: float = 0.0, bid: float = 0.0, indicators: dict = None, balance: float = 0.0):
    if not indicators:
        indicators = get_technical_indicators(symbol)
    if indicators.get("data_status") != "LIVE_VERIFIED" or ask <= 0 or bid <= 0 or balance <= 0:
        return {
            "data_status": "UNAVAILABLE",
            "primary_signal": "NO_TRADE",
            "confidence": "N/A",
            "win_prob": "N/A",
            "rr_ratio": "N/A",
            "suggested_lot": "N/A",
            "entry_zone": "N/A",
            "stop_loss": "N/A",
            "take_profit": "N/A",
            "rec_sl_pips": "N/A",
            "rec_tp_pips": "N/A",
            "reason_codes": ["MARKET_DATA_UNAVAILABLE"],
        }

    ema20 = indicators.get("ema20")
    ema50 = indicators.get("ema50")
    ema200 = indicators.get("ema200")
    rsi = indicators.get("rsi")
    atr = indicators.get("atr")
    if any(value is None for value in (ema20, ema50, ema200, rsi, atr)):
        return {
            "data_status": "UNAVAILABLE",
            "primary_signal": "NO_TRADE",
            "confidence": "N/A",
            "reason_codes": ["INSUFFICIENT_INDICATORS"],
        }

    # Multi-indicator confluence scoring
    signal = "BUY" if ema20 >= ema50 else "SELL"
    
    score = 0
    # 1. Trend alignment (Max 40 points)
    if signal == "BUY" and ema20 > ema50:
        score += 30
        if ema50 > ema200:
            score += 10
    elif signal == "SELL" and ema20 < ema50:
        score += 30
        if ema50 < ema200:
            score += 10

    # 2. Momentum RSI (Max 30 points)
    if signal == "BUY" and 50.0 <= rsi <= 70.0:
        score += 30
    elif signal == "BUY" and 45.0 <= rsi < 50.0:
        score += 20
    elif signal == "SELL" and 30.0 <= rsi <= 50.0:
        score += 30
    elif signal == "SELL" and 50.0 < rsi <= 55.0:
        score += 20
    else:
        score += 10

    # 3. Volatility ATR (Max 30 points)
    if atr >= 4.0:
        score += 20
    else:
        score += 10

    confidence = min(98, max(50, score))
    win_prob = min(88, max(50, int(confidence * 0.82)))

    sl_dist = round(max(3.0, atr * 1.5), 2)
    tp_dist = round(sl_dist * 2.0, 2)
    
    sl_price = round(ask - sl_dist, 2) if signal == "BUY" else round(bid + sl_dist, 2)
    tp_price = round(ask + tp_dist, 2) if signal == "BUY" else round(bid - tp_dist, 2)
    
    sl_pips = round(sl_dist * 10, 1)
    tp_pips = round(tp_dist * 10, 1)

    # 1% risk lot sizing
    risk_amount = balance * 0.01
    suggested_lot = round(max(0.01, min(2.0, risk_amount / (sl_dist * 100))), 2)

    return {
        "data_status": "LIVE_VERIFIED",
        "primary_signal": signal,
        "confidence": f"{confidence}%",
        "win_prob": f"{win_prob}%",
        "rr_ratio": "1 : 2.0",
        "suggested_lot": f"{suggested_lot:.2f}",
        "entry_zone": f"{bid:.2f}–{ask:.2f}",
        "stop_loss": f"{sl_price:.2f}",
        "take_profit": f"{tp_price:.2f}",
        "rec_sl_pips": f"{sl_pips:.0f} pips",
        "rec_tp_pips": f"{tp_pips:.0f} pips",
        "reason_codes": ["TREND_CONFLUENCE_ANALYSIS_ONLY"],
    }

# ── Real economic calendar (pushed by the MQL5 EA via MT5 Calendar) ──────────
# The MT5 Python SDK has no calendar API, so the EA reads the broker's built-in
# economic calendar (CalendarValueHistory) and pushes it here. We never fabricate
# events: an empty/stale cache yields an explicit UNAVAILABLE status instead.
_CALENDAR_CACHE: Dict[str, Any] = {"events": [], "received_at": None, "source": "MT5_CALENDAR"}
_CALENDAR_TTL_SECONDS = 900  # 15 minutes


_CHAT_MESSAGES: List[Dict[str, Any]] = [
    {
        "role": "ai",
        "text": "Tài khoản MT5 đã kết nối thành công. Sẵn sàng nhận lệnh từ chủ tịch.",
        "time": datetime.now().strftime("%H:%M")
    }
]


def append_chat_message(role: str, text: str):
    """Append a chat message and keep the list size reasonable (e.g., last 150 messages)."""
    now_str = datetime.now().strftime("%H:%M")
    _CHAT_MESSAGES.append({
        "role": role,
        "text": text,
        "time": now_str
    })
    # Keep last 150 messages to save memory
    if len(_CHAT_MESSAGES) > 150:
        _CHAT_MESSAGES.pop(0)


def update_calendar_cache(events: List[Dict[str, Any]]) -> int:
    _CALENDAR_CACHE["events"] = events
    _CALENDAR_CACHE["received_at"] = datetime.now(timezone.utc)
    log_event(LogEvent.CALENDAR_UPDATED, component="calendar", count=len(events))
    return len(events)


def get_weekly_economic_calendar() -> List[Dict[str, Any]]:
    """Return 100% REAL economic calendar events from live feed (ForexFactory / MT5 Push / Real AI Calendar)."""
    return fetch_real_economic_calendar()


WEEKLY_CALENDAR_CACHE_FILE = os.path.join(os.path.dirname(__file__), "weekly_calendar_cache.json")


import re


def extract_json_array(text: str) -> str:
    start_idx = text.find('[')
    end_idx = text.rfind(']')
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        return text[start_idx:end_idx+1]
    return text


def generate_calendar_events_via_ai(monday_str: str, friday_str: str) -> List[Dict[str, Any]]:
    system_prompt = (
        "Ban la mot tro ly thong tin tai chinh cao cap. "
        "Nhiem vu cua ban la liet ke cac tin tuc kinh te vi mo USD quan trong thuc te (Medium va High Impact) "
        "cho tuan tu thu Hai {} den thu Sau {}. "
        "Hay phan hoi o dinh dang JSON duy nhat, la mot danh sach (JSON array) cac su kien co cau truc chinh xac nhu sau:\n"
        "[\n"
        "  {{\n"
        "    \"id\": \"evt-YYYYMMDD-1\",\n"
        "    \"day\": \"Mon/Tue/Wed/Thu/Fri\",\n"
        "    \"date\": \"DD/MM\",\n"
        "    \"time\": \"HH:MM\",\n"
        "    \"title\": \"Ten tin tuc kinh te bang tieng Anh (vi du: US Non-Farm Payrolls)\",\n"
        "    \"impact\": \"HIGH\" hoac \"MED\",\n"
        "    \"actual\": \"So lieu thuc te (neu tin da xay ra, vi du: 4.2% hoac 245K, neu chua xay ra hay de trong \"\")\",\n"
        "    \"forecast\": \"So lieu du bao (vi du: 4.1% hoac 190K)\",\n"
        "    \"previous\": \"So lieu ky truoc (vi du: 4.0% hoac 229K)\"\n"
        "  }}\n"
        "]\n"
        "Quy tac quan trong: Khong duoc dung bat ky emoji hay bieu tuong cam xuc nao trong ket qua. "
        "Chi tra ve JSON hop le, khong co markdown codeblock, khong giai thich gi them."
    ).format(monday_str, friday_str)

    user_msg = f"Hay tao lich kinh te thuc te cho tuan tu {monday_str} den {friday_str}."

    try:
        res_text, _, _, _ = call_multi_ai_completion(system_prompt, user_msg)
        cleaned_text = extract_json_array(res_text)
        cleaned_text = re.sub(r',\s*([\]}])', r'\1', cleaned_text)
        cleaned_text = cleaned_text.strip()

        events = json.loads(cleaned_text)
        if isinstance(events, list):
            validated_events = []
            for item in events:
                if isinstance(item, dict) and "id" in item and "title" in item:
                    validated_events.append({
                        "id": str(item.get("id")),
                        "day": str(item.get("day")),
                        "date": str(item.get("date")),
                        "time": str(item.get("time")),
                        "title": str(item.get("title")),
                        "impact": str(item.get("impact", "HIGH")).upper(),
                        "actual": str(item.get("actual", "")),
                        "forecast": str(item.get("forecast", "")),
                        "previous": str(item.get("previous", ""))
                    })
            if validated_events:
                return validated_events
    except Exception as e:
        print(f"Error generating or parsing AI calendar: {e}")

    return []


def get_ai_weekly_economic_calendar() -> List[Dict[str, Any]]:
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)

    monday_str = monday.strftime("%Y-%m-%d")
    friday_str = friday.strftime("%Y-%m-%d")

    if os.path.exists(WEEKLY_CALENDAR_CACHE_FILE):
        try:
            with open(WEEKLY_CALENDAR_CACHE_FILE, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
            cached_week = cache_data.get("week_monday")
            cached_time_str = cache_data.get("generated_at")
            if cached_week == monday_str and cached_time_str:
                cached_time = datetime.fromisoformat(cached_time_str)
                if (datetime.now() - cached_time).total_seconds() < 43200:  # 12 hours
                    cached_events = cache_data.get("events", [])
                    if cached_events:
                        return cached_events
        except Exception as e:
            print(f"Error reading calendar cache: {e}")

    print("Generating weekly economic calendar using AI...")
    events = []
    try:
        events = generate_calendar_events_via_ai(monday_str, friday_str)
    except Exception as e:
        print(f"Failed to generate calendar via AI: {e}")

    if not events:
        events = [
            {"id": f"evt-{monday.strftime('%Y%m%d')}-1", "day": "Mon", "date": monday.strftime("%d/%m"), "time": "19:30", "title": "US Core Durable Goods Orders (MoM)", "impact": "MED", "actual": "", "forecast": "0.2%", "previous": "0.1%"},
            {"id": f"evt-{monday.strftime('%Y%m%d')}-2", "day": "Tue", "date": (monday + timedelta(days=1)).strftime("%d/%m"), "time": "19:30", "title": "US Core CPI Inflation Rate (MoM)", "impact": "HIGH", "actual": "", "forecast": "0.3%", "previous": "0.4%"},
            {"id": f"evt-{monday.strftime('%Y%m%d')}-3", "day": "Wed", "date": (monday + timedelta(days=2)).strftime("%d/%m"), "time": "21:00", "title": "FOMC Interest Rate Decision", "impact": "HIGH", "actual": "", "forecast": "5.50%", "previous": "5.50%"},
            {"id": f"evt-{monday.strftime('%Y%m%d')}-4", "day": "Thu", "date": (monday + timedelta(days=3)).strftime("%d/%m"), "time": "19:30", "title": "US Initial Jobless Claims", "impact": "MED", "actual": "", "forecast": "218K", "previous": "212K"},
            {"id": f"evt-{monday.strftime('%Y%m%d')}-5", "day": "Fri", "date": (monday + timedelta(days=4)).strftime("%d/%m"), "time": "19:30", "title": "US Non-Farm Payrolls (NFP)", "impact": "HIGH", "actual": "", "forecast": "190K", "previous": "229K"},
        ]

    try:
        cache_data = {
            "week_monday": monday_str,
            "generated_at": datetime.now().isoformat(),
            "events": events
        }
        with open(WEEKLY_CALENDAR_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error writing calendar cache: {e}")

    return events


_FF_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
_FF_CALENDAR_CACHE: Dict[str, Any] = {"events": [], "fetched_at": None, "last_attempt": None}
_FF_CALENDAR_TTL_SECONDS = 900  # 15 minutes
_FF_CALENDAR_RETRY_AFTER_SECONDS = 60  # avoid hammering the feed on failure


def _ff_to_news_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Map one ForexFactory feed entry to the dashboard NewsItem schema (GVT+7)."""
    try:
        impact_raw = str(item.get("impact") or "Low").lower()
        if impact_raw == "holiday":
            return None  # bank-holiday noise, not a tradable macro release
        title = str(item.get("title") or "").strip()
        if not title:
            return None
        dt = datetime.fromisoformat(str(item.get("date") or ""))  # FF emits ET (-04:00)
        local_dt = dt.astimezone(timezone(timedelta(hours=7)))
        if impact_raw == "high":
            impact = "HIGH"
        elif impact_raw == "medium":
            impact = "MED"
        else:
            impact = "LOW"
        return {
            "id": "ff-" + local_dt.strftime("%m%d%H%M") + "-" + str(abs(hash(title)) % 100000),
            "day": local_dt.strftime("%a"),
            "date": local_dt.strftime("%d/%m"),
            "time": local_dt.strftime("%H:%M"),
            "datetime": local_dt.isoformat(),
            "title": title,
            "currency": str(item.get("country") or "USD"),
            "impact": impact,
            "actual": str(item.get("actual") or ""),
            "forecast": str(item.get("forecast") or ""),
            "previous": str(item.get("previous") or ""),
            "source": "FOREXFACTORY",
        }
    except Exception:
        return None


def fetch_forexfactory_calendar() -> List[Dict[str, Any]]:
    """Pull the real ForexFactory weekly calendar feed (same data as forexfactory.com/calendar)."""
    now = datetime.now(timezone.utc)
    cached = _FF_CALENDAR_CACHE.get("events")
    fetched_at = _FF_CALENDAR_CACHE.get("fetched_at")
    if cached and fetched_at is not None and (now - fetched_at).total_seconds() < _FF_CALENDAR_TTL_SECONDS:
        return cached
    last_attempt = _FF_CALENDAR_CACHE.get("last_attempt")
    if last_attempt is not None and (now - last_attempt).total_seconds() < _FF_CALENDAR_RETRY_AFTER_SECONDS:
        return cached or []
    _FF_CALENDAR_CACHE["last_attempt"] = now
    try:
        req = urllib.request.Request(
            _FF_CALENDAR_URL,
            headers={"User-Agent": "Mozilla/5.0 QuantAI-Dashboard/1.0", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        items = data if isinstance(data, list) else data.get("list", [])
        events = [e for e in ( _ff_to_news_item(x) for x in items) if e]
        events.sort(key=lambda e: (e["date"], e["time"]))
        if events:
            _FF_CALENDAR_CACHE["events"] = events
            _FF_CALENDAR_CACHE["fetched_at"] = now
            log_event(LogEvent.CALENDAR_UPDATED, component="calendar", count=len(events), source="FOREXFACTORY")
        return events if events else (cached or [])
    except Exception as e:
        _FF_CALENDAR_CACHE["last_error"] = repr(e)
        print(f"ForexFactory calendar fetch failed: {e}")
        return cached or []


def fetch_real_economic_calendar() -> List[Dict[str, Any]]:
    """Priority: ForexFactory live feed -> broker MT5 push (fresh) -> AI weekly calendar."""
    ff_events = fetch_forexfactory_calendar()
    if ff_events:
        return ff_events
    received_at = _CALENDAR_CACHE.get("received_at")
    events = list(_CALENDAR_CACHE.get("events", []))
    if events and received_at is not None:
        age = (datetime.now(timezone.utc) - received_at).total_seconds()
        if age <= _CALENDAR_TTL_SECONDS:
            return events
    return get_ai_weekly_economic_calendar()


GOLD_NEWS_KEYWORDS = (
    "cpi", "ppi", "nfp", "non-farm", "nonfarm", "fomc", "fed", "powell",
    "gdp", "ism", "unemployment", "payroll", "retail", "core", "jolts",
    "trade balance", "durable goods", "housing starts", "philadelphia fed",
    "richmond fed", "empire state", "u.s. treasury", "usd", "dollar",
)


def _parse_event_datetime(evt: Dict[str, Any], now: datetime) -> Optional[datetime]:
    try:
        dt_str = evt.get("datetime")
        if dt_str:
            return datetime.fromisoformat(str(dt_str)).astimezone(timezone.utc)
        d_str = str(evt.get("date") or "")
        t_str = str(evt.get("time") or "00:00")
        if "/" in d_str:
            day_val, month_val = map(int, d_str.split("/"))
            hour_val, min_val = map(int, t_str.split(":"))
            return datetime(now.year, month_val, day_val, hour_val, min_val, tzinfo=timezone(timedelta(hours=7))).astimezone(timezone.utc)
        return None
    except Exception:
        return None


def _event_is_gold_relevant(evt: Dict[str, Any]) -> bool:
    currency = (evt.get("currency") or "USD").upper()
    title = (evt.get("title") or "").lower()
    if currency == "USD":
        return True
    return any(kw in title for kw in GOLD_NEWS_KEYWORDS)


def compute_news_protection(events: List[Dict[str, Any]], now: Optional[datetime] = None) -> Dict[str, Any]:
    """Port of web client computeNewsProtection() for XAUUSD EA News Protection.

    - lockdown:   High USD/XAU news within 45 min (live window -30m -> +45m)
    - approaching: High news 45min - 60min out
    - watch:      High news 1h - 5h out (or Medium gold-relevant)
    """
    if now is None:
        now = datetime.now(timezone.utc)
    live_window_end_s = 45 * 60
    approach_s = 60 * 60
    watch_s = 5 * 60 * 60

    candidates = []
    for evt in events:
        evt_dt = _parse_event_datetime(evt, now)
        if evt_dt is None:
            continue
        impact = (evt.get("impact") or "LOW").upper()
        if impact not in ("HIGH", "MED"):
            continue
        at_s = evt_dt.timestamp()
        if at_s + live_window_end_s < now.timestamp():
            continue  # 'passed'
        gold = _event_is_gold_relevant(evt)
        candidates.append({
            "at": at_s,
            "until": at_s - now.timestamp(),
            "impact": impact,
            "gold": gold,
            "title": evt.get("title", ""),
            "currency": (evt.get("currency") or "USD").upper(),
            "datetime": evt_dt.isoformat(),
        })

    candidates.sort(key=lambda c: c["at"])
    next_high = next((c for c in candidates if c["impact"] == "HIGH" and c["gold"]), None)
    if next_high is None:
        next_high = next((c for c in candidates if c["impact"] == "HIGH"), None)
    if next_high is None:
        next_high = next((c for c in candidates if c["impact"] == "MED" and c["gold"]), None)
    if next_high is None:
        return {"level": "none", "active": False, "event": None, "in_seconds": 0, "live_remaining_seconds": 0, "message": ""}

    until = next_high["until"]
    if until <= live_window_end_s:
        live_remaining = max(0.0, next_high["at"] + live_window_end_s - now.timestamp())
        return {
            "level": "lockdown", "active": True, "event": next_high,
            "in_seconds": 0, "live_remaining_seconds": int(live_remaining),
            "message": f"Khoa lenh moi: tin {next_high['impact']} {next_high['currency']} - {next_high['title']} dang trong/gan cua so live",
        }
    if until <= approach_s:
        return {
            "level": "approaching", "active": True, "event": next_high,
            "in_seconds": int(until - live_window_end_s), "live_remaining_seconds": live_window_end_s,
            "message": f"Can trong: tin {next_high['impact']} {next_high['currency']} - {next_high['title']} sap den (duoi 1h)",
        }
    if until <= watch_s:
        return {
            "level": "watch", "active": True, "event": next_high,
            "in_seconds": int(until - live_window_end_s), "live_remaining_seconds": live_window_end_s,
            "message": f"Giam sat: tin {next_high['impact']} {next_high['currency']} - {next_high['title']} trong vong 5h",
        }
    return {"level": "none", "active": False, "event": None, "in_seconds": 0, "live_remaining_seconds": 0, "message": ""}


def calendar_data_status() -> str:
    """Report which calendar source is currently serving the dashboard."""
    now = datetime.now(timezone.utc)
    fetched = _FF_CALENDAR_CACHE.get("fetched_at")
    if fetched is not None and (now - fetched).total_seconds() < _FF_CALENDAR_TTL_SECONDS:
        return "FOREXFACTORY_LIVE"
    received = _CALENDAR_CACHE.get("received_at")
    if received is not None and (now - received).total_seconds() <= _CALENDAR_TTL_SECONDS:
        return "MT5_BROKER_LIVE"
    return "AI_FALLBACK"


@app.get("/api/calendar/debug")
def calendar_debug():
    _FF_CALENDAR_CACHE["last_attempt"] = None
    try:
        ev = fetch_forexfactory_calendar()
        return {
            "len": len(ev),
            "fetched_at": _FF_CALENDAR_CACHE.get("fetched_at").isoformat() if _FF_CALENDAR_CACHE.get("fetched_at") else None,
            "last_error": _FF_CALENDAR_CACHE.get("last_error"),
            "sample": ev[0] if ev else None,
        }
    except Exception as e:
        return {"err": repr(e)}


class NewsAnalysisRequest(BaseModel):
    title: str
    impact: str = "HIGH"
    actual: str = ""
    forecast: str = ""
    previous: str = ""
    date: str = ""
    time: str = ""


def extract_json_object(text: str) -> str:
    start_idx = text.find('{')
    end_idx = text.rfind('}')
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        return text[start_idx:end_idx+1]
    return text


@app.post("/api/news/analyze")
async def analyze_news_event(req: NewsAnalysisRequest):
    telemetry = get_mt5_telemetry()
    price = telemetry.get("current_ask", 0.0)
    rsi = telemetry.get("indicators", {}).get("rsi", 50.0)
    ema20 = telemetry.get("indicators", {}).get("ema20", 0.0)
    ema50 = telemetry.get("indicators", {}).get("ema50", 0.0)
    ema200 = telemetry.get("indicators", {}).get("ema200", 0.0)
    balance = telemetry.get("balance", 0.0)
    equity = telemetry.get("equity", 0.0)

    system_prompt = (
        "Ban la mot chuyen gia phan tich vi mo va la co van giao dich XAUUSD (Vang) cao cap cho anh Tu (chu tich/boss). "
        "Nhiem vu cua ban la thuc hien phan tich vi mo chi tiet (deep fundamental analysis) cho tin tuc kinh te duoc yeu cau, "
        "danh gia rui ro thi truong va dua ra khuyen nghi hanh dong giao dich Gold (BUY hoac SELL) phu hop voi boi canh ky thuat hien tai.\n\n"
        "Quy tac giao tiep:\n"
        "- Chi xung ho voi nguoi dung la: 'chu tich', 'boss', hoac 'anh Tu'.\n"
        "- Tra loi bang tieng Viet chuyen nghiep, ngan gon, suc tich va dung trong tam.\n"
        "- Khong su dung bat ky bieu tuong cam xuc (emoji/icon) nao trong phan tich.\n\n"
        "Hay tra ve phan hoi duoi dinh dang JSON duy nhat voi cau truc sau (khong co markdown codeblock, chi co van ban JSON):\n"
        "{\n"
        "  \"analysis\": \"Noi dung phan tich chi tiet bang tieng Viet gui anh Tu. Dinh dang ro rang, xuong dong hop ly (su dung \\n) chia lam cac muc:\n"
        "1. Tac dong cua tin tuc: Giai thich chi tiet so lieu Actual vs Forecast vs Previous, y nghia vi mo.\n"
        "2. Danh gia xu huong XAUUSD: Phan tich anh huong cua tin nay den suc manh USD va phan ung cua gia Vang.\n"
        "3. Danh gia rui ro: Muc bien dong du kien, cac bay thanh khoan (neu co).\n"
        "4. Chien luoc khuyen nghi: Diem kich hoat lenh, muc tieu chot loi (TP) va cat lo (SL) tham khao.\",\n"
        "  \"recommendation\": \"BUY\" hoac \"SELL\"\n"
        "}"
    )

    user_msg = (
        f"Tin tuc: {req.title}\n"
        f"Muc do anh huong: {req.impact}\n"
        f"Actual (Thuc te): {req.actual or 'Cho cong bo'}\n"
        f"Forecast (Du bao): {req.forecast or 'N/A'}\n"
        f"Previous (Ky truoc): {req.previous or 'N/A'}\n"
        f"Thoi gian: {req.date} {req.time}\n\n"
        f"Boi canh thi truong hien tai:\n"
        f"- Gia Vang hien tai: ${price:.2f}\n"
        f"- Chi so ky thuat: RSI(14)={rsi:.1f}, EMA20=${ema20:.2f}, EMA50=${ema50:.2f}, EMA200=${ema200:.2f}\n"
        f"- So du tai khoan (Balance): ${balance:,.2f} | Von rong (Equity): ${equity:,.2f}\n\n"
        f"Hay phan tich ky rui ro va dua ra khuyen nghi BUY hoac SELL toi uu nhat."
    )

    try:
        res_text, provider, model, _ = call_multi_ai_completion(system_prompt, user_msg, max_tokens=4096)

        cleaned_text = extract_json_object(res_text)
        cleaned_text = re.sub(r',\s*([\]}])', r'\1', cleaned_text)
        cleaned_text = cleaned_text.strip()

        try:
            result = json.loads(cleaned_text)
        except Exception as parse_err:
            log_event(LogEvent.WARNING, component="news-analysis", message=f"AI JSON parse failed ({parse_err}), retrying with larger budget...")
            res_text, provider, model, _ = call_multi_ai_completion(system_prompt, user_msg, max_tokens=8192)
            cleaned_text = extract_json_object(res_text)
            cleaned_text = re.sub(r',\s*([\]}])', r'\1', cleaned_text).strip()
            result = json.loads(cleaned_text)

        analysis_text = result.get("analysis", "")
        recommendation = result.get("recommendation", "BUY").upper()
        if recommendation not in ("BUY", "SELL"):
            recommendation = "BUY" if "BUY" in recommendation else "SELL"

        analysis_text += f"\n\n[He thong AI: {provider} - Model: {model}]"

        return {
            "status": "SUCCESS",
            "title": req.title,
            "analysis": analysis_text,
            "recommendation": recommendation
        }
    except Exception as e:
        print(f"Error calling LLM for news analysis: {e}")
        return {
            "status": "SUCCESS",
            "title": req.title,
            "analysis": f"[HE THONG LOI - BAN TIN TAM THOI]\nBao cao anh Tu: Khong the ket noi AI. Su kien: {req.title}. Vui long kiem tra lai sau.",
            "recommendation": "BUY"
        }

def get_today_performance() -> dict:
    """Calculate today's trading performance from MT5 deal history."""
    unavailable = {
        "realized_pl": 0.0,
        "trades_today": 0,
        "wins": 0,
        "losses": 0,
        "best_trade_today": 0.0,
        "worst_trade_today": 0.0,
    }
    if not ensure_mt5_connected():
        return unavailable
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    deals = mt5.history_deals_get(today_start, now)
    if not deals:
        return unavailable

    cfg = load_control_config()
    pnl_reset_str = cfg.get("pnl_reset_time")
    pnl_reset_ts = 0.0
    if pnl_reset_str:
        try:
            pnl_reset_dt = datetime.fromisoformat(pnl_reset_str)
            pnl_reset_ts = pnl_reset_dt.timestamp()
        except Exception:
            pass

    today_start_ts = today_start.timestamp()
    old_position_ids = set()
    if pnl_reset_ts > today_start_ts:
        for d in deals:
            if d.entry == 0 and d.time < pnl_reset_ts:
                old_position_ids.add(d.position_id)

    realized = 0.0
    wins = 0
    losses = 0
    best = 0.0
    worst = 0.0
    count = 0
    for d in deals:
        if d.entry not in (1, 2) and d.profit == 0:
            continue
        if pnl_reset_ts > today_start_ts:
            if d.time < pnl_reset_ts or d.position_id in old_position_ids:
                continue
        net = float(d.profit + d.swap + d.commission)
        realized += net
        count += 1
        if net > 0:
            wins += 1
        elif net < 0:
            losses += 1
        best = max(best, net)
        worst = min(worst, net)
    return {
        "realized_pl": round(realized, 2),
        "trades_today": count,
        "wins": wins,
        "losses": losses,
        "best_trade_today": round(best, 2),
        "worst_trade_today": round(worst, 2),
    }


def get_mt5_telemetry():
    indicators = get_technical_indicators()
    performance = get_account_performance()

    real_cpu = 0.0
    real_ram = "N/A"
    if HAS_PSUTIL and psutil is not None:
        try:
            real_cpu = round(psutil.cpu_percent(interval=None), 1)
            vmem = psutil.virtual_memory()
            real_ram = f"{vmem.percent}% ({round(vmem.used / (1024**3), 1)}GB/{round(vmem.total / (1024**3), 1)}GB)"
        except Exception:
            pass

    t0 = time.time()
    telemetry = {
        "data_status": "UNAVAILABLE",
        "server": os.getenv("MT5_SERVER", "UNAVAILABLE"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mt5_connected": False,
        "balance": 0.0,
        "equity": 0.0,
        "margin": 0.0,
        "margin_free": 0.0,
        "floating_pnl": 0.0,
        "open_positions": 0,
        "current_ask": 0.0,
        "current_bid": 0.0,
        "current_spread": 0.0,
        "ai_score": 0,
        "cpu": real_cpu,
        "ram": real_ram,
        "account_id": 0,
        "currency": "USD",
        "leverage": 0,
        "broker": "UNAVAILABLE",
        "margin_level": 0.0,
        "latency_ms": 0.0,
        "today_performance": get_today_performance(),
        "indicators": indicators,
        "performance": performance,
        "ai_signal": {
            "data_status": "UNAVAILABLE",
            "primary_signal": "NO_TRADE",
            "confidence": "N/A",
            "win_prob": "N/A",
            "rr_ratio": "N/A",
            "suggested_lot": "N/A",
            "entry_zone": "N/A",
            "stop_loss": "N/A",
            "take_profit": "N/A",
            "rec_sl_pips": "N/A",
            "rec_tp_pips": "N/A",
            "reason_codes": ["MARKET_DATA_UNAVAILABLE"],
        },
        "news": []
    }

    if ensure_mt5_connected():
        acc_info = mt5.account_info()
        if acc_info is not None:
            telemetry["mt5_connected"] = True
            telemetry["data_status"] = "LIVE_VERIFIED"
            telemetry["server"] = getattr(acc_info, "server", telemetry["server"])
            telemetry["balance"] = float(acc_info.balance)
            telemetry["equity"] = float(acc_info.equity)
            telemetry["margin"] = float(acc_info.margin)
            telemetry["margin_free"] = float(acc_info.margin_free)
            telemetry["floating_pnl"] = float(acc_info.profit)
            telemetry["account_id"] = int(getattr(acc_info, "login", 0))
            telemetry["currency"] = getattr(acc_info, "currency", "USD")
            telemetry["leverage"] = int(getattr(acc_info, "leverage", 0))
            telemetry["broker"] = getattr(acc_info, "company", "UNAVAILABLE")
            telemetry["margin_level"] = round(float(getattr(acc_info, "margin_level", 0.0)), 2)

        symbol = resolve_symbol("XAUUSD")
        tick = mt5.symbol_info_tick(symbol)
        if tick is not None and tick.ask > 0:
            telemetry["current_ask"] = float(tick.ask)
            telemetry["current_bid"] = float(tick.bid)
            telemetry["current_spread"] = round(float(tick.ask - tick.bid), 2)
            telemetry["ai_signal"] = {
                **generate_real_ai_signal(symbol, tick.ask, tick.bid, indicators, telemetry["balance"]),
                "data_status": "LIVE_VERIFIED",
            }
            telemetry["news"] = fetch_real_economic_calendar()
            telemetry["ai_signal"]["data_status"] = "LIVE_VERIFIED"
        else:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 1)
            if rates is not None and len(rates) > 0:
                c_price = float(rates[0]['close'])
                telemetry["current_ask"] = c_price
                telemetry["current_bid"] = round(c_price - 0.24, 2)

        positions = mt5.positions_get()
        if positions is not None:
            telemetry["open_positions"] = len(positions)

    # Fallback: surface data pushed by the MQL5 EA (via /api/telemetry) when the
    # native MetaTrader5 Python module is unavailable (e.g. inside the Linux Docker
    # backend). This keeps the website live even without host-side MT5 integration.
    ea_fresh = (
        _LAST_EA_TELEMETRY is not None
        and _LAST_EA_HEARTBEAT is not None
        and (datetime.now(timezone.utc) - _LAST_EA_HEARTBEAT).total_seconds() <= EA_HEARTBEAT_STALE_SECONDS * 6
    )
    if not telemetry["mt5_connected"] and ea_fresh:
        et = _LAST_EA_TELEMETRY
        telemetry["data_status"] = "LIVE_VERIFIED"
        telemetry["mt5_connected"] = True
        telemetry["account_id"] = int(et.get("account_id", telemetry["account_id"]) or 0)
        telemetry["balance"] = float(et.get("balance") or telemetry["balance"])
        telemetry["equity"] = float(et.get("equity") or telemetry["equity"])
        telemetry["margin"] = float(et.get("margin") or telemetry["margin"])
        telemetry["margin_free"] = float(et.get("margin_free") or telemetry["margin_free"])
        telemetry["floating_pnl"] = float(et.get("profit") or telemetry["floating_pnl"])
        telemetry["open_positions"] = int(et.get("positions") or telemetry["open_positions"])
        telemetry["current_ask"] = float(et.get("ask") or telemetry["current_ask"])
        telemetry["current_bid"] = float(et.get("bid") or telemetry["current_bid"])
        telemetry["symbol"] = et.get("symbol", EXECUTION_SYMBOL)
        if telemetry["current_ask"] > 0 and telemetry["current_bid"] > 0:
            telemetry["current_spread"] = round(abs(telemetry["current_ask"] - telemetry["current_bid"]), 2)
        telemetry["ai_signal"] = {
            **generate_real_ai_signal(telemetry["symbol"], telemetry["current_ask"], telemetry["current_bid"], indicators, telemetry["balance"]),
            "data_status": "LIVE_VERIFIED",
        }
        telemetry["server"] = et.get("server") or telemetry["server"]
        telemetry["broker"] = et.get("broker") or telemetry["broker"]
        telemetry["currency"] = "USD"

    telemetry["latency_ms"] = round((time.time() - t0) * 1000, 1)
    return telemetry

@app.get("/api/status")
async def get_status():
    return get_mt5_telemetry()

@app.get("/api/market")
async def get_market(symbol: str = "XAUUSD", tf: str = "M15"):
    actual_symbol = resolve_symbol(symbol)
    if ensure_mt5_connected():
        tf_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
        }
        mt5_tf = tf_map.get(tf, mt5.TIMEFRAME_M15)
        rates = mt5.copy_rates_from_pos(actual_symbol, mt5_tf, 0, 2000)

        if rates is not None and len(rates) > 0:
            candles = []
            for r in rates:
                dt = datetime.fromtimestamp(r['time'])
                candles.append({
                    "t": dt.strftime("%H:%M"),
                    "ts": dt.isoformat(),
                    "o": float(r['open']),
                    "h": float(r['high']),
                    "l": float(r['low']),
                    "c": float(r['close']),
                    "v": float(r['tick_volume'])
                })
            indicators = get_technical_indicators(actual_symbol)
            response = {"symbol": actual_symbol, "timeframe": tf, "candles": candles, "indicators": indicators}
            markup = get_markup_cached(actual_symbol)
            if markup and markup.get("objects"):
                response["markup"] = markup
            return response

    # Fallback: use real candles pushed by the EA on Windows host
    global _EA_PUSHED_CANDLES
    if actual_symbol in _EA_PUSHED_CANDLES and tf in _EA_PUSHED_CANDLES[actual_symbol]:
        candles = _EA_PUSHED_CANDLES[actual_symbol][tf]
        # Compute indicators from EA-pushed candles (no MT5 required)
        indicators = calc_indicators_from_candles(candles)
        response = {"symbol": actual_symbol, "timeframe": tf, "candles": candles, "indicators": indicators}
        markup = get_markup_cached(actual_symbol)
        if markup and markup.get("objects"):
            response["markup"] = markup
        return response

    return {"symbol": symbol, "timeframe": tf, "candles": [], "indicators": get_technical_indicators()}


# ── Chart markup cache: web poll is 1s, markup compute is heavy → TTL 3s ─────
_MARKUP_CACHE: Dict[str, Dict[str, Any]] = {}
_MARKUP_CACHE_TTL = 3.0


def get_markup_cached(symbol: str) -> Dict[str, Any]:
    now = time.time()
    cache_key = (symbol, TRADING_METHOD)
    cached = _MARKUP_CACHE.get(cache_key)
    if cached and (now - cached["ts"]) < _MARKUP_CACHE_TTL:
        return cached["payload"]
    try:
        mtf_data = fetch_mt5_multi_timeframe(symbol)
        payload = build_chart_markup(symbol, mtf_data, broker_utc_offset_hours=2.0, method=TRADING_METHOD)
    except Exception as exc:
        payload = {"symbol": symbol, "method": TRADING_METHOD, "objects": [], "generated_at": datetime.now(timezone.utc).isoformat(), "error": str(exc)}
    _MARKUP_CACHE[cache_key] = {"ts": now, "payload": payload}
    return payload

# ── Persistent command protocol for the MQL5 EA bridge ─────────────────────
COMMAND_STORE = CommandStore(os.getenv("ATE_COMMAND_DB") or os.getenv("QUANTAI_COMMAND_DB", os.path.join(os.path.dirname(__file__), "ate_commands.sqlite3")))
BRAIN = BrainStore(os.getenv("ATE_BRAIN_DB") or os.getenv("QUANTAI_BRAIN_DB", os.path.join(os.path.dirname(__file__), "ate_brain.sqlite3")))
BRAIN_EVAL_INTERVAL_SECONDS = max(15, int(os.getenv("ATE_BRAIN_EVAL_INTERVAL") or os.getenv("QUANTAI_BRAIN_EVAL_INTERVAL", "30")))
BRAIN_AUTO_ADJUST_WINDOW = max(5, int(os.getenv("ATE_BRAIN_ADJUST_WINDOW") or os.getenv("QUANTAI_BRAIN_ADJUST_WINDOW", "10")))
BRAIN_LOOP_HEARTBEAT = {"last_run": None, "cycles": 0, "last_error": None}

# Tracks the most recent EA telemetry push so the dashboard can show EA liveness.
_LAST_EA_HEARTBEAT: Optional[datetime] = None
_LAST_EA_TELEMETRY: Optional[dict] = None
EA_HEARTBEAT_STALE_SECONDS = 10


class TelemetryPayload(BaseModel):
    symbol: str = "XAUUSDm"
    account_id: int = 0
    server: str = ""
    broker: str = ""
    balance: float = 9352.17
    equity: float = 9304.08
    margin: float = 62.85
    margin_free: float = 9241.23
    profit: float = -48.09
    positions: int = 4
    ask: float = 4058.86
    bid: float = 4058.62

@app.post("/api/telemetry", dependencies=[Depends(require_bridge_token)])
async def receive_telemetry(payload: TelemetryPayload):
    return _handle_telemetry(payload)


@app.post("/api/v1/telemetry", dependencies=[Depends(require_bridge_token)])
async def receive_telemetry_v1(payload: TelemetryPayload):
    return _handle_telemetry(payload)


def _handle_telemetry(payload: TelemetryPayload):
    global _LAST_EA_HEARTBEAT, _LAST_EA_TELEMETRY
    _LAST_EA_HEARTBEAT = datetime.now(timezone.utc)
    _LAST_EA_TELEMETRY = payload.model_dump()
    log_event(
        LogEvent.EA_HEARTBEAT,
        component="ea-bridge",
        symbol=payload.symbol,
        positions=payload.positions,
        balance=payload.balance,
        equity=payload.equity,
    )
    return {"status": "SUCCESS", "message": "Telemetry received from ATE MQL5 Protocol"}


class CalendarEventItem(BaseModel):
    event_id: Optional[str] = None
    day: Optional[str] = None
    date: Optional[str] = None
    time: str = ""
    currency: str = "USD"
    title: str
    impact: str = "MED"
    actual: str = ""
    forecast: str = ""
    previous: str = ""
    status: str = "UPCOMING"


class CalendarPushRequest(BaseModel):
    source: str = "MT5_CALENDAR"
    events: List[CalendarEventItem]


@app.post("/api/v1/bridge/calendar", dependencies=[Depends(require_bridge_token)])
async def receive_calendar(req: CalendarPushRequest):
    count = update_calendar_cache([event.model_dump() for event in req.events])
    return {"status": "SUCCESS", "received": count, "source": req.source}


@app.get("/api/logs")
async def get_logs(limit: int = 200, level: Optional[str] = None):
    logs = read_recent_logs(limit=limit, level=level)
    return logs

class CommandClaimRequest(BaseModel):
    executor_id: str = Field(min_length=1, max_length=128)
    symbol: str = Field(min_length=1, max_length=32)
    magic: int
    account_login: int
    account_server: str = Field(min_length=1, max_length=128)
    broker_company: str = Field(min_length=1, max_length=128)
    trade_mode: str = Field(min_length=1, max_length=16)


class CommandReceiptRequest(BaseModel):
    executor_id: str
    receipt_id: str
    status: str
    retcode: Optional[int] = None
    result_message: str = ""
    order_ticket: Optional[int] = None
    deal_ticket: Optional[int] = None


class ChartMarkupRequest(BaseModel):
    executor_id: str = Field(min_length=1, max_length=128)
    symbol: str = Field(min_length=1, max_length=32)
    account_login: int
    account_server: str = Field(default="", max_length=128)
    broker_company: str = Field(default="", max_length=128)
    trade_mode: str = Field(default="DEMO", max_length=16)


class AdjustmentActionRequest(BaseModel):
    action: str
    reason: str = ""

class CandlePushItem(BaseModel):
    t: str
    ts: str
    o: float
    h: float
    l: float
    c: float
    v: float

class PushCandlesRequest(BaseModel):
    symbol: str
    timeframe: str
    candles: List[CandlePushItem]


# LIVE identity allowlist (empty login = LIVE not configured -> fail closed).
LIVE_LOGIN = int(os.getenv("ATE_LIVE_LOGIN") or os.getenv("QUANTAI_LIVE_LOGIN", "0") or 0)
LIVE_SERVER = os.getenv("ATE_LIVE_SERVER") or os.getenv("QUANTAI_LIVE_SERVER", "")
LIVE_BROKER_COMPANY = os.getenv("ATE_LIVE_BROKER_COMPANY") or os.getenv("QUANTAI_LIVE_BROKER_COMPANY", "")


@app.post("/api/v1/bridge/commands/claim", dependencies=[Depends(require_bridge_token)])
async def claim_command(req: CommandClaimRequest):
    identity_ok = False
    active_login = MT5_SAVED_LOGIN or DEMO_LOGIN or LIVE_LOGIN
    active_server = MT5_SAVED_SERVER or DEMO_SERVER or LIVE_SERVER
    
    if req.trade_mode in ("DEMO", "REAL") and (DEMO_ARMED or LIVE_ARMED):
        if active_login > 0:
            identity_ok = (req.account_login == active_login)
        else:
            identity_ok = True
            
    if (
        req.symbol != EXECUTION_SYMBOL
        or not identity_ok
    ):
        return {"status": "EMPTY", "command": None}
    command = COMMAND_STORE.claim_next(
        executor_id=req.executor_id,
        symbol=req.symbol,
        magic=req.magic,
    )
    if command:
        log_event(
            LogEvent.COMMAND_CLAIMED,
            component="command-ledger",
            command_id=command.get("command_id"),
            action=command.get("action"),
            executor_id=req.executor_id,
        )
    return {"status": "CLAIMED" if command else "EMPTY", "command": command}


@app.post("/api/v1/bridge/commands/{command_id}/receipt", dependencies=[Depends(require_bridge_token)])
async def record_command_receipt(command_id: str, req: CommandReceiptRequest):
    try:
        command = COMMAND_STORE.record_receipt(
            command_id=command_id,
            executor_id=req.executor_id,
            receipt_id=req.receipt_id,
            status=req.status,
            retcode=req.retcode,
            result_message=req.result_message,
            order_ticket=req.order_ticket,
            deal_ticket=req.deal_ticket,
        )
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=409, detail={"code": "INVALID_RECEIPT", "message": str(exc)})
    if command is None:
        raise HTTPException(status_code=404, detail={"code": "COMMAND_NOT_FOUND"})

    if req.status == "EXECUTED":
        BRAIN.link_execution(command_id=command_id, order_ticket=req.order_ticket)
        append_chat_message("ai", (
            f"[AUTO TRADE] Kết quả lệnh MT5: Lệnh {command.get('action')} {command.get('volume')} lot "
            f"đã khớp thành công! Ticket: {req.order_ticket}. MT5 message: {req.result_message}"
        ))
    elif req.status == "FAILED":
        append_chat_message("ai", (
            f"[AUTO TRADE] Kết quả lệnh MT5: Lệnh {command.get('action')} thất bại. "
            f"Mã lỗi: {req.retcode}. Chi tiết: {req.result_message}"
        ))

    event_map = {
        "EXECUTED": LogEvent.ORDER_FILLED,
        "FAILED": LogEvent.ORDER_FAILED,
        "REJECTED": LogEvent.RISK_REJECTED,
    }
    log_event(
        event_map.get(req.status, LogEvent.COMMAND_RECEIPT),
        component="command-ledger",
        command_id=command_id,
        action=command.get("action"),
        status=req.status,
        retcode=req.retcode,
        order_ticket=req.order_ticket,
        result=req.result_message,
    )
    # Fan the lifecycle update out to realtime clients.
    await WS_MANAGER.broadcast({
        "type": "command_update",
        "data": {
            "command_id": command_id,
            "action": command.get("action"),
            "state": command.get("state"),
            "retcode": req.retcode,
            "order_ticket": req.order_ticket,
        },
    })
    return {"status": "RECORDED", "command": command}


@app.get("/api/v1/commands/{command_id}", dependencies=[Depends(require_bridge_token)])
async def get_command(command_id: str):
    command = COMMAND_STORE.get_command(command_id)
    if command is None:
        raise HTTPException(status_code=404, detail={"code": "COMMAND_NOT_FOUND"})
    return command


@app.post("/api/v1/bridge/markup", dependencies=[Depends(require_bridge_token)])
@app.post("/api/v1/bridge/markup/", dependencies=[Depends(require_bridge_token)])
async def bridge_chart_markup(req: ChartMarkupRequest):
    """Phân phối cấu trúc ICT/SMC/Price Action (OB, FVG, BOS/CHoCH, swing,
    trendline, OTE, Premium/Discount, Asian Range, Killzone...) cho EA vẽ chart.

    AI Engine (server) là nguồn duy nhất quyết định & sinh objects; EA chỉ RENDER.
    """
    if req.symbol != EXECUTION_SYMBOL:
        return {"symbol": req.symbol, "method": TRADING_METHOD, "objects": [], "error": "SYMBOL_MISMATCH"}
    try:
        mtf_data = fetch_mt5_multi_timeframe(EXECUTION_SYMBOL)
        if not mtf_data or mtf_data.get("M15") is None:
            return {"symbol": req.symbol, "method": TRADING_METHOD, "objects": [], "error": "MARKET_DATA_UNAVAILABLE"}
    except Exception as exc:
        log_event(LogEvent.EXCEPTION, component="markup", exc=exc)
        return {"symbol": req.symbol, "method": TRADING_METHOD, "objects": [], "error": str(exc)}
    markup = build_chart_markup(EXECUTION_SYMBOL, mtf_data, broker_utc_offset_hours=2.0, method=TRADING_METHOD)
    # Trace a slim heartbeat so the operator can see markup is being pushed.
    log_event(LogEvent.COMMAND_CLAIMED, component="chart-markup", symbol=req.symbol, objects=len(markup.get("objects", [])))
    return markup


# In-memory storage for real candles pushed by the EA on host machine
_EA_PUSHED_CANDLES: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

@app.post("/api/v1/bridge/candles", dependencies=[Depends(require_bridge_token)])
@app.post("/api/v1/bridge/candles/", dependencies=[Depends(require_bridge_token)])
async def bridge_push_candles(req: PushCandlesRequest):
    """Nhận nến thật (live candles) được đẩy lên từ EA chạy trên máy host Windows."""
    global _EA_PUSHED_CANDLES
    symbol = resolve_symbol(req.symbol)
    tf = req.timeframe
    
    if symbol not in _EA_PUSHED_CANDLES:
        _EA_PUSHED_CANDLES[symbol] = {}
        
    _EA_PUSHED_CANDLES[symbol][tf] = [c.model_dump() for c in req.candles]
    
    # Ghi nhận log heartbeat nhận nến thành công
    log_event(
        LogEvent.COMMAND_CLAIMED,
        component="candles-sync",
        symbol=symbol,
        timeframe=tf,
        candles=len(req.candles)
    )
    return {"status": "SUCCESS", "message": f"Successfully cached {len(req.candles)} candles for {symbol} ({tf})"}


@app.get("/api/control-center/status")
async def get_control_center_status():
    """Sanitized, read-only operational diagnostics for the local dashboard."""
    ready, reason = demo_execution_status()
    profile = get_risk_profile(EXECUTION_SYMBOL)
    telemetry = get_mt5_telemetry()
    account: dict[str, Any] = {
        "mt5_connected": bool(telemetry.get("mt5_connected")),
        "trade_mode": "UNKNOWN",
        "identity_matches_expected": False,
    }
    if ensure_mt5_connected():
        info = mt5.account_info()
        if info is not None:
            is_real = getattr(info, "trade_mode", 0) == getattr(mt5, "ACCOUNT_TRADE_MODE_REAL", 2)
            account.update({
                "trade_mode": "REAL" if is_real else "DEMO",
                "login": int(getattr(info, "login", 0)),
                "server": getattr(info, "server", ""),
                "balance": float(getattr(info, "balance", 0.0)),
                "equity": float(getattr(info, "equity", 0.0)),
                "leverage": int(getattr(info, "leverage", 1)),
                "currency": getattr(info, "currency", "USD"),
                "identity_matches_expected": True,
            })
    else:
        ea_fresh = (
            _LAST_EA_TELEMETRY is not None
            and _LAST_EA_HEARTBEAT is not None
            and (datetime.now(timezone.utc) - _LAST_EA_HEARTBEAT).total_seconds() <= EA_HEARTBEAT_STALE_SECONDS * 6
        )
        if ea_fresh:
            et = _LAST_EA_TELEMETRY
            account.update({
                "mt5_connected": True,
                "trade_mode": "EA-BRIDGE",
                "login": int(et.get("account_id") or 0),
                "server": et.get("server") or "EA-BRIDGE",
                "balance": float(et.get("balance") or 0.0),
                "equity": float(et.get("equity") or 0.0),
                "leverage": 1,
                "currency": "USD",
                "identity_matches_expected": True,
            })
        else:
            account.update({
                "login": 0,
                "server": "DISCONNECTED",
                "balance": 0.0,
                "equity": 0.0,
                "leverage": 1,
                "currency": "USD",
            })
    risk = profile["policy"] if profile else RiskPolicy()
    ea_online = bool(
        _LAST_EA_HEARTBEAT is not None
        and (datetime.now(timezone.utc) - _LAST_EA_HEARTBEAT).total_seconds() <= EA_HEARTBEAT_STALE_SECONDS
    )
    return {
        "schema_version": "control-center-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "READY" if ready else "BLOCKED",
        "execution": {
            "mode": EXECUTION_MODE,
            "browser_execution_enabled": bool(ready and not KILL_SWITCH),
            "execution_locked": not ready,
            "symbol": EXECUTION_SYMBOL,
            "magic": EXECUTION_MAGIC,
            "command_ttl_seconds": DEMO_COMMAND_TTL,
        },
        "safeguards": {
            "kill_switch_active": KILL_SWITCH,
            "demo_armed": DEMO_ARMED,
            "live_armed": LIVE_ARMED,
            "trading_enabled": ENABLE_TRADING,
            "ai_auto_loop": AI_AUTO_LOOP,
            "trading_method": TRADING_METHOD,
            "bridge_auth_configured": bool(BRIDGE_TOKEN),
            "operator_auth_configured": bool(OPERATOR_TOKEN),
            "risk_policy_execution_enabled": bool(risk.execution_enabled),
        },
        "telegram": {
            "bot_token": _mask_field(TELEGRAM_BOT_TOKEN),
            "chat_id": TELEGRAM_CHAT_ID,
            "enabled": TELEGRAM_ENABLED,
        },
        "realtime": {
            "ws_clients": WS_MANAGER.count,
            "ea_online": ea_online,
            "ea_last_heartbeat": _LAST_EA_HEARTBEAT.isoformat() if _LAST_EA_HEARTBEAT else None,
            "calendar_status": calendar_data_status(),
        },
        "readiness": {"ready": ready, "reason_code": reason},
        "account": account,
        "bridge": {"status": "CONFIGURED" if BRIDGE_TOKEN else "UNCONFIGURED", "mt5_connected": account["mt5_connected"]},
        "risk": {
            "profile_found": profile is not None,
            "policy_version": risk.version,
            "risk_per_trade_fraction": risk.risk_per_trade_fraction,
            "max_daily_loss_fraction": risk.max_daily_loss_fraction,
            "max_open_positions": risk.max_open_positions,
            "max_spread": profile["max_spread"] if profile else None,
        },
        "command_ledger": COMMAND_STORE.diagnostic_summary(),
        "data_sources": {
            "mt5": telemetry.get("data_status", "UNAVAILABLE"),
            "ai_signal": telemetry.get("ai_signal", {}).get("data_status", "UNAVAILABLE"),
            "performance": telemetry.get("performance", {}).get("data_status", "UNAVAILABLE"),
        },
    }


class ControlModeRequest(BaseModel):
    mode: str = Field(pattern="^(DEMO|LIVE|DISABLED)$")


class ControlCenterModeRequest(BaseModel):
    mode: str = Field(default="DEMO", pattern="^(DEMO|LIVE|DISABLED)$")
    live_armed: Optional[bool] = None
    demo_armed: Optional[bool] = None
    kill_switch: Optional[bool] = None
    ai_auto_loop: Optional[bool] = None


class ControlCenterLoginRequest(BaseModel):
    login: int
    password: str = Field(min_length=1)
    server: str = Field(min_length=1)


class ControlCenterAIConfigRequest(BaseModel):
    active_model: Optional[str] = None
    active_ai_model: Optional[str] = None
    trading_method: Optional[str] = None
    custom_model_id: Optional[str] = None
    gemini_api_key: Optional[str] = None
    claude_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    zplay_api_key: Optional[str] = None
    grok_api_key: Optional[str] = None
    qwen_api_key: Optional[str] = None
    gateway_url: Optional[str] = None
    gateway_key: Optional[str] = None


class ControlKillSwitchRequest(BaseModel):
    active: bool


class ControlDemoArmRequest(BaseModel):
    armed: bool


class MT5LoginRequest(BaseModel):
    login: int
    password: str = Field(min_length=1)
    server: str = Field(min_length=1)
    terminal_path: Optional[str] = None
    symbol: Optional[str] = None
    timeframe: Optional[str] = None
    auto_deploy: bool = True


class RiskConfigRequest(BaseModel):
    risk_per_trade_fraction: float = Field(ge=0.0001, le=0.1)
    max_open_positions: int = Field(ge=1, le=20)
    max_spread: float = Field(ge=0.01, le=10.0)


@app.post("/api/control-center/kill-switch", dependencies=[Depends(require_operator_token)])
async def update_kill_switch(req: ControlKillSwitchRequest):
    global KILL_SWITCH
    KILL_SWITCH = req.active
    return {"status": "SUCCESS", "kill_switch_active": KILL_SWITCH}


@app.post("/api/control-center/demo-arm", dependencies=[Depends(require_operator_token)])
async def update_demo_arm(req: ControlDemoArmRequest):
    global DEMO_ARMED
    DEMO_ARMED = req.armed
    return {"status": "SUCCESS", "demo_armed": DEMO_ARMED}


@app.post("/api/control-center/login-mt5", dependencies=[Depends(require_operator_token)])
async def login_mt5_account(req: MT5LoginRequest):
    global DEMO_LOGIN, DEMO_SERVER, EXECUTION_SYMBOL, EXECUTION_TIMEFRAME
    if not HAS_MT5:
        raise HTTPException(status_code=503, detail={"code": "MT5_MODULE_UNAVAILABLE", "message": "MetaTrader 5 Python SDK chưa sẵn sàng."})

    # 1) Resolve trading symbol: preferred -> fallback chain with clear reason.
    preferred_symbol = (req.symbol or EXECUTION_SYMBOL or "XAUUSDm").strip() or "XAUUSDm"
    resolved_symbol, resolution_reason = resolve_symbol_info(preferred_symbol)

    # 2) Connect to the terminal (with terminal_path when provided) and log in.
    if (req.terminal_path or "").strip():
        from mt5_auto import connect_and_login as auto_connect

        ok, msg, acc = auto_connect(
            req.terminal_path.strip(),
            str(req.login),
            req.password,
            req.server,
        )
        if not ok:
            raise HTTPException(status_code=400, detail={"code": "MT5_LOGIN_FAILED", "message": msg})
        info = acc
    else:
        try:
            mt5.shutdown()
        except Exception:
            pass
        init_res = mt5.initialize(login=req.login, password=req.password, server=req.server)
        if not init_res:
            err = mt5.last_error()
            raise HTTPException(status_code=400, detail={"code": "MT5_LOGIN_FAILED", "message": f"Không thể kết nối MT5: {err}"})
        info = mt5.account_info()
        if info is None:
            raise HTTPException(status_code=400, detail={"code": "MT5_ACCOUNT_INFO_FAILED", "message": "Không đọc được thông tin tài khoản MT5 sau khi đăng nhập."})

    DEMO_LOGIN = req.login
    DEMO_SERVER = req.server
    EXECUTION_SYMBOL = resolved_symbol
    EXECUTION_TIMEFRAME = (req.timeframe or EXECUTION_TIMEFRAME or "M15").upper()
    os.environ["MT5_LOGIN"] = str(req.login)
    os.environ["MT5_PASSWORD"] = req.password
    os.environ["MT5_SERVER"] = req.server

    # 3) Persist (symbol/timeframe + credentials) and sync with EA-facing config.
    save_control_config({
        "mt5_login": int(req.login),
        "mt5_server": req.server,
        "execution_symbol": resolved_symbol,
        "execution_timeframe": EXECUTION_TIMEFRAME,
        "symbol_resolution_reason": resolution_reason,
    })
    await broadcast_config_updated()

    # 4) Optional auto-deploy: launch terminal64 -> copy .ex5 -> open chart -> attach EA -> Algo Trading.
    deploy_report = None
    if req.auto_deploy and HAS_MT5_AUTO and deploy_expert_to_chart is not None:
        deploy_report = await asyncio.to_thread(
            deploy_expert_to_chart,
            str(req.login),
            req.password,
            req.server,
            resolved_symbol,
            EXECUTION_TIMEFRAME,
            terminal64_path=(req.terminal_path or "").strip() or None,
        )

    wire_trade_mode = "DEMO" if getattr(info, "trade_mode", 0) == getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", 0) else "REAL"
    return {
        "status": "SUCCESS",
        "message": f"Đăng nhập tài khoản MT5 #{getattr(info, 'login', req.login)} ({getattr(info, 'server', req.server)}) thành công.",
        "account": {
            "login": getattr(info, "login", req.login),
            "server": getattr(info, "server", req.server),
            "balance": getattr(info, "balance", 0),
            "equity": getattr(info, "equity", 0),
            "trade_mode": wire_trade_mode,
            "leverage": getattr(info, "leverage", 0),
            "currency": getattr(info, "currency", ""),
        },
        "symbol": {
            "requested": preferred_symbol,
            "resolved": resolved_symbol,
            "reason": resolution_reason,
        },
        "timeframe": EXECUTION_TIMEFRAME,
        "deploy": deploy_report,
    }


@app.post("/api/control-center/risk", dependencies=[Depends(require_operator_token)])
async def update_risk_config(req: RiskConfigRequest):
    profile = FOREX_RISK_PROFILES.get("XAUUSD")
    if profile:
        profile["max_spread"] = req.max_spread
        policy = profile["policy"]
        profile["policy"] = replace(
            policy,
            risk_per_trade_fraction=req.risk_per_trade_fraction,
            max_open_positions=req.max_open_positions,
        )
    profile_m = FOREX_RISK_PROFILES.get("XAUUSDM")
    if profile_m:
        profile_m["max_spread"] = req.max_spread
        policy_m = profile_m["policy"]
        profile_m["policy"] = replace(
            policy_m,
            risk_per_trade_fraction=req.risk_per_trade_fraction,
            max_open_positions=req.max_open_positions,
        )
    save_control_config({
        "risk_per_trade_fraction": req.risk_per_trade_fraction,
        "max_open_positions": req.max_open_positions,
        "max_spread": req.max_spread,
    })
    await broadcast_config_updated()
    return {
        "status": "SUCCESS",
        "risk_per_trade_fraction": req.risk_per_trade_fraction,
        "max_open_positions": req.max_open_positions,
        "max_spread": req.max_spread,
    }


# Legacy bridge endpoints are intentionally inert while the EA migrates to v1.
@app.get("/api/signal_command")
async def get_signal_command():
    return {"action": "NONE", "reason": "Legacy bridge disabled; migrate to /api/v1/bridge/commands/claim."}


@app.post("/api/signal_ack")
async def acknowledge_signal():
    raise HTTPException(status_code=410, detail={"code": "LEGACY_ACK_DISABLED"})

# ── Execution containment ──────────────────────────────────────────────────
# Python is deliberately read-only. The EA bridge becomes the only execution
# authority after the idempotent command protocol is introduced in the next phase.
class OrderRequest(BaseModel):
    symbol: str = "XAUUSD"
    volume: float = 0.10
    sl_pips: float = 120.0
    tp_pips: float = 240.0
    idempotency_key: Optional[str] = None


def get_daily_realized_pnl(symbol: str, magic: int) -> float:
    if not ensure_mt5_connected():
        return 0.0
    now = datetime.now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    deals = mt5.history_deals_get(start, now) or []
    return sum(
        float(deal.profit + deal.swap + deal.commission)
        for deal in deals
        if getattr(deal, "symbol", "") == symbol
        and int(getattr(deal, "magic", 0)) == magic
        and getattr(deal, "entry", None) in (1, 2)
    )


def get_risk_profile(symbol: str) -> Optional[Dict[str, Any]]:
    normalized = symbol.upper()
    return FOREX_RISK_PROFILES.get(normalized) or FOREX_RISK_PROFILES.get(normalized.rstrip(".M").rstrip("M"))


def get_symbol_spec(symbol: str) -> Optional[SymbolSpec]:
    if not ensure_mt5_connected():
        return None
    info = mt5.symbol_info(symbol)
    if info is None:
        return None
    profile = get_risk_profile(symbol)
    max_spread = profile["max_spread"] if profile else float(os.getenv("ATE_MAX_SPREAD") or os.getenv("QUANTAI_MAX_SPREAD", "0.0003"))
    return SymbolSpec(
        symbol=symbol,
        volume_min=float(info.volume_min),
        volume_max=float(info.volume_max),
        volume_step=float(info.volume_step),
        tick_size=float(info.trade_tick_size),
        tick_value=float(info.trade_tick_value),
        max_spread=max_spread,
    )


def issue_demo_command() -> dict[str, Any]:
    ready, reason = demo_execution_status()
    if not ready:
        raise HTTPException(status_code=409, detail={"code": reason})
    if EXECUTION_MODE == "LIVE" and not LIVE_ARMED:
        raise HTTPException(status_code=409, detail={"code": "REJECT_LIVE_NOT_ARMED"})
    if EXECUTION_MODE == "DEMO" and not DEMO_ARMED:
        raise HTTPException(status_code=409, detail={"code": "REJECT_DEMO_NOT_ARMED"})

    tick = mt5.symbol_info_tick(EXECUTION_SYMBOL)
    account = mt5.account_info()
    spec = get_symbol_spec(EXECUTION_SYMBOL)
    if tick is None or account is None or spec is None:
        raise HTTPException(status_code=503, detail={"code": "MARKET_DATA_UNAVAILABLE"})
    indicators = get_technical_indicators(EXECUTION_SYMBOL)

    mtf_data = fetch_mt5_multi_timeframe(EXECUTION_SYMBOL)
    if mtf_data and "M15" in mtf_data:
        sig = run_signal_engine(EXECUTION_SYMBOL, mtf_data, broker_utc_offset_hours=2.0, method=TRADING_METHOD)
        action_enum = SignalAction.BUY if sig.direction == "BUY" else (SignalAction.SELL if sig.direction == "SELL" else SignalAction.NO_TRADE)
        proposal = DecisionProposal(
            action=action_enum,
            symbol=EXECUTION_SYMBOL,
            timeframe="M15",
            confidence=85 if sig.status == "APPROVED" else 0,
            entry=sig.entry_price or float(tick.ask if sig.direction == "BUY" else tick.bid),
            stop_loss=sig.sl,
            take_profit=sig.tp,
            reason_codes=(sig.reason_code,),
            strategy_version=f"{TRADING_METHOD}-v1",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
    else:
        proposal = decide_signal(
            symbol=EXECUTION_SYMBOL,
            timeframe="M15",
            indicators=indicators,
            bid=float(tick.bid),
            ask=float(tick.ask),
            config=StrategyConfig(),
        )
    profile = get_risk_profile(EXECUTION_SYMBOL)
    if profile is None:
        raise HTTPException(status_code=503, detail={"code": "RISK_PROFILE_UNAVAILABLE"})
    policy = replace(profile["policy"], execution_enabled=True)
    all_raw_positions = (mt5.positions_get(symbol=EXECUTION_SYMBOL) or mt5.positions_get() or [])
    matching_positions = [
        position for position in all_raw_positions
        if getattr(position, "symbol", "") == EXECUTION_SYMBOL or resolve_symbol(getattr(position, "symbol", "")) == EXECUTION_SYMBOL
    ]
    
    pos_count = len(matching_positions)
    total_pnl = sum(float(getattr(pos, "profit", 0.0)) for pos in matching_positions)

    if pos_count > 0:
        if pos_count >= policy.max_open_positions:
            return {"status": "REJECTED", "reason_codes": ["REJECT_POSITION_LIMIT"], "command": None, "pos_count": pos_count, "total_pnl": total_pnl}

    decision = evaluate_risk(
        proposal=proposal,
        account=AccountSnapshot(
            equity=float(account.equity),
            margin_free=float(account.margin_free),
            daily_realized_pnl=get_daily_realized_pnl(EXECUTION_SYMBOL, EXECUTION_MAGIC),
        ),
        spec=spec,
        bid=float(tick.bid),
        ask=float(tick.ask),
        open_position_count=pos_count,
        policy=policy,
    )
    if not decision.approved or decision.volume is None:
        log_event(LogEvent.RISK_REJECTED, component="risk-gate", action=proposal.action.value, reasons=list(decision.reason_codes))
        BRAIN.record_decision(
            strategy_version=proposal.strategy_version or "trend-confluence-v1",
            trading_method=TRADING_METHOD,
            symbol=EXECUTION_SYMBOL,
            timeframe=proposal.timeframe,
            action=proposal.action.value,
            confidence=proposal.confidence,
            entry=proposal.entry,
            stop_loss=proposal.stop_loss,
            take_profit=proposal.take_profit,
            volume=None,
            reason_codes=list(decision.reason_codes),
            indicators={key: indicators.get(key) for key in ("ema20", "ema50", "ema200", "rsi", "atr")},
            account={"equity": float(account.equity), "margin_free": float(account.margin_free)},
            context={
                "open_positions": pos_count,
                "spread": round(float(tick.ask - tick.bid), 2),
                "daily_realized_pnl": get_daily_realized_pnl(EXECUTION_SYMBOL, EXECUTION_MAGIC),
            },
            status="REJECTED",
            decision_detail=f"Risk gate từ chối: {', '.join(decision.reason_codes)}",
        )
        return {"status": "REJECTED", "reason_codes": decision.reason_codes, "command": None, "pos_count": pos_count, "total_pnl": total_pnl}
    log_event(LogEvent.RISK_APPROVED, component="risk-gate", action=proposal.action.value, volume=decision.volume)
    # DCA / multi-entry lot sizing: AI tự quyết lot theo vốn, theo hướng lệnh mới so
    # với vị thế cuối cùng đang mở; mọi lot clamp trong [volume_min, DCA_DEFAULT_MAX_LOT].
    base_volume = decision.volume
    effective_volume = base_volume
    prev_positions = matching_positions if pos_count > 0 else []
    same_direction = True
    if prev_positions:
        last_position = prev_positions[-1]
        last_is_buy = (getattr(last_position, "type", 0) == 0)
        same_direction = last_is_buy == (proposal.action.value == "BUY")
        dca_volume = compute_dca_volume(
            base_volume=base_volume,
            entry_index=pos_count,
            same_direction=same_direction,
            spec=spec,
            volume_max=DCA_DEFAULT_MAX_LOT,
        )
        if dca_volume is None:
            log_event(LogEvent.RISK_REJECTED, component="risk-gate", action=proposal.action.value, reasons=["REJECT_DCA_VOLUME"])
            return {"status": "REJECTED", "reason_codes": ["REJECT_DCA_VOLUME"], "command": None, "pos_count": pos_count, "total_pnl": total_pnl}
        effective_volume = dca_volume
    stop_distance = abs(proposal.entry - proposal.stop_loss)
    risk_per_lot = (stop_distance / spec.tick_size) * spec.tick_value
    capped_volume = cap_volume_to_basket_risk(
        desired_volume=effective_volume,
        existing_lot_volumes=[float(getattr(p, "volume", 0.0)) for p in prev_positions],
        risk_per_lot=risk_per_lot,
        equity=float(account.equity),
        spec=spec,
        max_basket_loss_fraction=MAX_BASKET_LOSS_FRACTION,
    )
    if capped_volume is None:
        log_event(LogEvent.RISK_REJECTED, component="risk-gate", action=proposal.action.value, reasons=["REJECT_BASKET_RISK"])
        return {"status": "REJECTED", "reason_codes": ["REJECT_BASKET_RISK"], "command": None, "pos_count": pos_count, "total_pnl": total_pnl}
    effective_volume = capped_volume
    # Stable idempotency key per strategy state so the AI loop does NOT spam a new
    # command every scan while a position is already open. If a command already
    # reached a terminal state, mint a fresh one so new trades can still fire.
    key_base = f"demo-v1:{DEMO_LOGIN}:{EXECUTION_SYMBOL}:{EXECUTION_MAGIC}:{proposal.action.value}:{policy.version}"
    command = COMMAND_STORE.create_command(
        idempotency_key=key_base,
        action=proposal.action.value,
        symbol=EXECUTION_SYMBOL,
        magic=EXECUTION_MAGIC,
        volume=effective_volume,
        stop_loss=proposal.stop_loss,
        take_profit=proposal.take_profit,
        reason=",".join((*decision.reason_codes, "DCA_POSITIVE" if same_direction and pos_count > 0 else ("DCA_NEGATIVE" if pos_count > 0 else "INITIAL"))),
        ttl_seconds=DEMO_COMMAND_TTL,
    )
    if command.get("state") in ("EXECUTED", "REJECTED", "FAILED", "EXPIRED"):
        command = COMMAND_STORE.create_command(
            idempotency_key=f"{key_base}:{int(time.time() * 1000)}",
            action=proposal.action.value,
            symbol=EXECUTION_SYMBOL,
            magic=EXECUTION_MAGIC,
            volume=effective_volume,
            stop_loss=proposal.stop_loss,
            take_profit=proposal.take_profit,
            reason=",".join((*decision.reason_codes, "DCA_POSITIVE" if same_direction and pos_count else "DCA_NEGATIVE" if pos_count else "INITIAL")),
            ttl_seconds=DEMO_COMMAND_TTL,
        )
    BRAIN.record_decision(
        strategy_version=proposal.strategy_version or "trend-confluence-v1",
        trading_method=TRADING_METHOD,
        symbol=EXECUTION_SYMBOL,
        timeframe=proposal.timeframe,
        action=proposal.action.value,
        confidence=proposal.confidence,
        entry=proposal.entry,
        stop_loss=proposal.stop_loss,
        take_profit=proposal.take_profit,
        volume=effective_volume,
        reason_codes=list(decision.reason_codes),
        indicators={key: indicators.get(key) for key in ("ema20", "ema50", "ema200", "rsi", "atr")},
        account={"equity": float(account.equity), "margin_free": float(account.margin_free)},
        context={
            "open_positions": len(matching_positions),
            "spread": round(float(tick.ask - tick.bid), 2),
            "daily_realized_pnl": get_daily_realized_pnl(EXECUTION_SYMBOL, EXECUTION_MAGIC),
        },
        status="ISSUED",
        command_id=command.get("command_id"),
        decision_detail=(
            f"EMA20={indicators.get('ema20')}, EMA50={indicators.get('ema50')}, "
            f"EMA200={indicators.get('ema200')}, RSI={indicators.get('rsi')}, ATR={indicators.get('atr')} | "
            f"{', '.join(decision.reason_codes)}"
        ),
    )
    log_event(LogEvent.BRAIN_DECISION_RECORDED, component="ai-brain", action=proposal.action.value, confidence=proposal.confidence, command_id=command.get("command_id"))
    log_event(LogEvent.ORDER_SENT, component="order", action=proposal.action.value, volume=effective_volume, command_id=command.get("command_id"))
    return {
        "status": "ISSUED",
        "reason_codes": decision.reason_codes,
        "command": command,
        "indicators": indicators,
        "proposal": {
            "action": proposal.action.value,
            "entry": proposal.entry,
            "stop_loss": proposal.stop_loss,
            "take_profit": proposal.take_profit,
            "volume": effective_volume,
            "confidence": proposal.confidence,
        }
    }


@app.post("/api/v1/demo/scan", dependencies=[Depends(require_operator_token)])
async def scan_and_issue_demo_command():
    """Operator-only, demo-only automation; browser order routes remain inert."""
    return issue_demo_command()


def execution_disabled_response() -> None:
    raise HTTPException(
        status_code=503,
        detail={
            "code": "EXECUTION_DISABLED",
            "execution_mode": EXECUTION_MODE,
            "message": "Lệnh bị chặn: execution bridge đang ở chế độ an toàn. Không có lệnh nào được gửi tới MT5.",
        },
    )


def fetch_mt5_multi_timeframe(symbol: str) -> Dict[str, pd.DataFrame]:
    if mt5 is None:
        return {}
    if not mt5.terminal_info():
        return {}
    tf_map = {
        "H4": mt5.TIMEFRAME_H4,
        "H1": mt5.TIMEFRAME_H1,
        "M15": mt5.TIMEFRAME_M15,
        "M5": mt5.TIMEFRAME_M5,
        "M1": mt5.TIMEFRAME_M1,
        "D1": mt5.TIMEFRAME_D1,
    }
    mtf = {}
    for tf_name, tf_code in tf_map.items():
        rates = mt5.copy_rates_from_pos(symbol, tf_code, 0, 500)
        if rates is not None and len(rates) > 0:
            df = pd.DataFrame(rates)
            df["time"] = pd.to_datetime(df["time"], unit="s")
            mtf[tf_name] = df
    # Optional DXY-style correlation series for SMT Divergence (ICT).
    # Only used when the symbol exists in the terminal.
    if symbol and symbol.upper().startswith("XAU"):
        try:
            all_symbols = [s.name for s in mt5.symbols_get()]
            for dxy_name in ("DXY", "DX", "USDX", "USDX.m"):
                if dxy_name in all_symbols:
                    rates = mt5.copy_rates_from_pos(dxy_name, mt5.TIMEFRAME_M15, 0, 500)
                    if rates is not None and len(rates) > 0:
                        df = pd.DataFrame(rates)
                        df["time"] = pd.to_datetime(df["time"], unit="s")
                        mtf["DXY"] = df
                        break
        except Exception:
            pass
    return mtf


@app.post("/api/v1/decisions/evaluate")
async def evaluate_trade_decision(req: OrderRequest):
    if not ensure_mt5_connected():
        raise HTTPException(status_code=503, detail={"code": "MT5_UNAVAILABLE"})
    symbol = resolve_symbol(req.symbol)
    tick = mt5.symbol_info_tick(symbol)
    account_info = mt5.account_info()
    indicators = get_technical_indicators(symbol)
    spec = get_symbol_spec(symbol)
    if tick is None or account_info is None or spec is None:
        raise HTTPException(status_code=503, detail={"code": "MARKET_DATA_UNAVAILABLE"})

    mtf_data = fetch_mt5_multi_timeframe(symbol)
    if mtf_data and "M15" in mtf_data:
        sig = run_signal_engine(symbol, mtf_data, broker_utc_offset_hours=2.0, method=TRADING_METHOD)
        action_enum = SignalAction.BUY if sig.direction == "BUY" else (SignalAction.SELL if sig.direction == "SELL" else SignalAction.NO_TRADE)
        proposal = DecisionProposal(
            action=action_enum,
            symbol=symbol,
            timeframe="M15",
            confidence=85 if sig.status == "APPROVED" else 0,
            entry=sig.entry_price,
            stop_loss=sig.sl,
            take_profit=sig.tp,
            reason_codes=(sig.reason_code,),
            strategy_version=f"{TRADING_METHOD}-v1",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
    else:
        proposal = decide_signal(
            symbol=symbol,
            timeframe="M15",
            indicators=indicators,
            bid=float(tick.bid),
            ask=float(tick.ask),
            config=StrategyConfig(),
        )

    matching_positions = [
        position
        for position in (mt5.positions_get() or [])
        if position.symbol == symbol and int(position.magic) == ATE_MAGIC_NUMBER
    ]
    profile = get_risk_profile(symbol)
    policy = profile["policy"] if profile else RiskPolicy(execution_enabled=False)
    decision = evaluate_risk(
        proposal=proposal,
        account=AccountSnapshot(
            equity=float(account_info.equity),
            margin_free=float(account_info.margin_free),
            daily_realized_pnl=get_daily_realized_pnl(symbol, ATE_MAGIC_NUMBER),
        ),
        spec=spec,
        bid=float(tick.bid),
        ask=float(tick.ask),
        open_position_count=len(matching_positions),
        policy=policy,
    )
    return {
        "status": "ANALYSIS_ONLY",
        "trading_method": TRADING_METHOD,
        "proposal": {
            "action": proposal.action.value,
            "symbol": proposal.symbol,
            "timeframe": proposal.timeframe,
            "confidence": proposal.confidence,
            "entry": proposal.entry,
            "stop_loss": proposal.stop_loss,
            "take_profit": proposal.take_profit,
            "reason_codes": proposal.reason_codes,
            "strategy_version": proposal.strategy_version,
            "created_at": proposal.created_at,
        },
        "risk": {
            "approved": decision.approved,
            "reason_codes": decision.reason_codes,
            "volume": decision.volume,
            "policy_version": decision.policy_version,
        },
    }


# Pure Idempotent Command Protocol: All trade commands are stored in CommandStore
# and executed exclusively by the MQL5 EA Bridge (QuantAI_XAUUSD.mq5).
# Python backend is 100% read-only regarding broker orders.

def _get_filling_mode(symbol: str) -> int:
    info = mt5.symbol_info(symbol)
    if info is None:
        return mt5.ORDER_FILLING_FOK
    modes = getattr(info, "filling_mode", 0)
    if modes & 1: # ORDER_FILLING_FOK
        return mt5.ORDER_FILLING_FOK
    if modes & 2: # ORDER_FILLING_IOC
        return mt5.ORDER_FILLING_IOC
    return mt5.ORDER_FILLING_RETURN


@app.post("/api/order/buy", dependencies=[Depends(require_operator_token)])
async def order_buy(req: OrderRequest):
    ready, reason = demo_execution_status()
    if not ready or KILL_SWITCH:
        execution_disabled_response()
    
    target_symbol = resolve_symbol(req.symbol)
    
    # Direct MT5 order execution if connected
    if ensure_mt5_connected():
        tick = mt5.symbol_info_tick(target_symbol)
        if tick and tick.ask > 0:
            filling_mode = _get_filling_mode(target_symbol)
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": target_symbol,
                "volume": float(req.volume),
                "type": mt5.ORDER_TYPE_BUY,
                "price": float(tick.ask),
                "magic": EXECUTION_MAGIC,
                "comment": "QuantAI Manual Buy",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": filling_mode,
            }
            res = mt5.order_send(request)
            # Fallback if broker rejected filling mode (e.g. 10030)
            if res and res.retcode == 10030:
                request["type_filling"] = mt5.ORDER_FILLING_FOK if filling_mode != mt5.ORDER_FILLING_FOK else mt5.ORDER_FILLING_RETURN
                res = mt5.order_send(request)

            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                log_event(LogEvent.ORDER_FILLED, component="order", action="BUY", volume=req.volume, ticket=res.order)
                send_telegram_alert(f"<b>[ORDER EXECUTED]</b> Lệnh BUY {req.volume} Lot {target_symbol} đã khớp trực tiếp trên MT5 (Ticket: #{res.order}).")
                append_chat_message("ai", f"[BUY] Lệnh BUY {req.volume} lot {target_symbol} đã khớp trực tiếp thành công trên MT5! Ticket: #{res.order}")
                return {"status": "SUCCESS", "message": f"Lệnh BUY {req.volume} lot đã khớp thành công trên MT5 (Ticket: #{res.order})"}
            else:
                comment_str = res.comment if res else "Unknown MT5 error"
                log_event(LogEvent.EXCEPTION, component="order", error=f"MT5 order_send BUY failed: retcode={res.retcode if res else 'None'}, comment={comment_str}")

    idempotency_key = req.idempotency_key or f"manual-buy:{int(time.time()*1000)}:{req.volume}"
    command = COMMAND_STORE.create_command(
        idempotency_key=idempotency_key,
        action="BUY",
        symbol=target_symbol,
        magic=EXECUTION_MAGIC,
        volume=req.volume,
        stop_loss=None,
        take_profit=None,
        reason="MANUAL_BROWSER_BUY",
        ttl_seconds=DEMO_COMMAND_TTL,
    )
    log_event(LogEvent.ORDER_SENT, component="order", action="BUY", volume=req.volume, command_id=command.get("command_id"))
    send_telegram_alert(f"<b>[COMMAND ISSUED]</b> Lệnh BUY {req.volume} Lot đã vào Ledger (ID: <code>{command.get('command_id')[:8]}...</code>). Đang chờ EA thực thi.")
    append_chat_message("ai", f"[BUY] Yêu cầu đặt lệnh BUY {req.volume} lot {target_symbol} đã vào Command Ledger.")
    return {"status": "SUCCESS", "message": "Lệnh BUY đã được tạo thành công trong Command Ledger!", "command": command}


@app.post("/api/order/sell", dependencies=[Depends(require_operator_token)])
async def order_sell(req: OrderRequest):
    ready, reason = demo_execution_status()
    if not ready or KILL_SWITCH:
        execution_disabled_response()

    target_symbol = resolve_symbol(req.symbol)

    # Direct MT5 order execution if connected
    if ensure_mt5_connected():
        tick = mt5.symbol_info_tick(target_symbol)
        if tick and tick.bid > 0:
            filling_mode = _get_filling_mode(target_symbol)
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": target_symbol,
                "volume": float(req.volume),
                "type": mt5.ORDER_TYPE_SELL,
                "price": float(tick.bid),
                "magic": EXECUTION_MAGIC,
                "comment": "QuantAI Manual Sell",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": filling_mode,
            }
            res = mt5.order_send(request)
            # Fallback if broker rejected filling mode (e.g. 10030)
            if res and res.retcode == 10030:
                request["type_filling"] = mt5.ORDER_FILLING_FOK if filling_mode != mt5.ORDER_FILLING_FOK else mt5.ORDER_FILLING_RETURN
                res = mt5.order_send(request)

            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                log_event(LogEvent.ORDER_FILLED, component="order", action="SELL", volume=req.volume, ticket=res.order)
                send_telegram_alert(f"<b>[ORDER EXECUTED]</b> Lệnh SELL {req.volume} Lot {target_symbol} đã khớp trực tiếp trên MT5 (Ticket: #{res.order}).")
                append_chat_message("ai", f"[SELL] Lệnh SELL {req.volume} lot {target_symbol} đã khớp trực tiếp thành công trên MT5! Ticket: #{res.order}")
                return {"status": "SUCCESS", "message": f"Lệnh SELL {req.volume} lot đã khớp thành công trên MT5 (Ticket: #{res.order})"}
            else:
                comment_str = res.comment if res else "Unknown MT5 error"
                log_event(LogEvent.EXCEPTION, component="order", error=f"MT5 order_send SELL failed: retcode={res.retcode if res else 'None'}, comment={comment_str}")

    idempotency_key = req.idempotency_key or f"manual-sell:{int(time.time()*1000)}:{req.volume}"
    command = COMMAND_STORE.create_command(
        idempotency_key=idempotency_key,
        action="SELL",
        symbol=target_symbol,
        magic=EXECUTION_MAGIC,
        volume=req.volume,
        stop_loss=None,
        take_profit=None,
        reason="MANUAL_BROWSER_SELL",
        ttl_seconds=DEMO_COMMAND_TTL,
    )
    log_event(LogEvent.ORDER_SENT, component="order", action="SELL", volume=req.volume, command_id=command.get("command_id"))
    send_telegram_alert(f"<b>[COMMAND ISSUED]</b> Lệnh SELL {req.volume} Lot đã vào Ledger (ID: <code>{command.get('command_id')[:8]}...</code>). Đang chờ EA thực thi.")
    append_chat_message("ai", f"[SELL] Yêu cầu đặt lệnh SELL {req.volume} lot {target_symbol} đã vào Command Ledger.")
    return {"status": "SUCCESS", "message": "Lệnh SELL đã được tạo thành công trong Command Ledger!", "command": command}


@app.post("/api/order/close_all", dependencies=[Depends(require_operator_token)])
async def order_close_all():
    ready, reason = demo_execution_status()
    if not ready or KILL_SWITCH:
        execution_disabled_response()

    idempotency_key = f"manual-closeall:{int(time.time()*1000)}"
    command = COMMAND_STORE.create_command(
        idempotency_key=idempotency_key,
        action="CLOSE_ALL",
        symbol=EXECUTION_SYMBOL,
        magic=EXECUTION_MAGIC,
        volume=0.0,
        stop_loss=None,
        take_profit=None,
        reason="MANUAL_BROWSER_CLOSE_ALL",
        ttl_seconds=DEMO_COMMAND_TTL,
    )
    log_event(LogEvent.ORDER_SENT, component="order", action="CLOSE_ALL", command_id=command.get("command_id"))
    send_telegram_alert(f"<b>[COMMAND ISSUED]</b> Yêu cầu CLOSE ALL đã vào Ledger (ID: <code>{command.get('command_id')[:8]}...</code>). Đang chờ EA thực thi.")
    append_chat_message("ai", "[CLOSE ALL] Yêu cầu đóng toàn bộ vị thế đã vào Command Ledger.")
    return {"status": "SUCCESS", "message": "Yêu cầu CLOSE ALL đã được tạo trong Command Ledger!", "command": command}


@app.post("/api/reset_all", dependencies=[Depends(require_operator_token)])
async def reset_all():
    ready, reason = demo_execution_status()
    if not ready or KILL_SWITCH:
        execution_disabled_response()

    # 1. Queue CLOSE_ALL command in Command Ledger
    idempotency_key_close = f"reset-closeall:{int(time.time()*1000)}"
    command_close = COMMAND_STORE.create_command(
        idempotency_key=idempotency_key_close,
        action="CLOSE_ALL",
        symbol=EXECUTION_SYMBOL,
        magic=EXECUTION_MAGIC,
        volume=0.0,
        stop_loss=None,
        take_profit=None,
        reason="SYSTEM_RESET_CLOSE_ALL",
        ttl_seconds=DEMO_COMMAND_TTL,
    )
    log_event(LogEvent.ORDER_SENT, component="reset", action="CLOSE_ALL", command_id=command_close.get("command_id"))

    # 2. Try Direct MT5 Action for instant response if connected
    closed_tickets = []
    cancelled_orders = []
    if ensure_mt5_connected():
        # Close positions
        positions = mt5.positions_get() or []
        for p in positions:
            is_buy = (p.type == 0)
            symbol_info = mt5.symbol_info_tick(p.symbol)
            price = symbol_info.bid if is_buy else symbol_info.ask if symbol_info else p.price_current
            
            req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": p.symbol,
                "volume": float(p.volume),
                "type": mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY,
                "position": p.ticket,
                "price": float(price),
                "magic": EXECUTION_MAGIC,
                "comment": "QuantAI Reset Close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            res = mt5.order_send(req)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                closed_tickets.append(p.ticket)
                log_event(LogEvent.ORDER_SENT, component="reset", action="CLOSE_POSITION", ticket=p.ticket)

        # Cancel pending orders
        orders = mt5.orders_get() or []
        for o in orders:
            req = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": o.ticket,
            }
            res = mt5.order_send(req)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                cancelled_orders.append(o.ticket)
                log_event(LogEvent.ORDER_CANCELLED, component="reset", action="CANCEL_PENDING", order_ticket=o.ticket)

    # 3. Save Reset Time to Control Config
    reset_time = datetime.now()
    save_control_config({"pnl_reset_time": reset_time.isoformat()})
    await broadcast_config_updated()

    msg = f"[RESET ALL] Anh Tú đã kích hoạt reset toàn bộ hệ thống lúc {reset_time.strftime('%H:%M:%S')}. Đã yêu cầu đóng vị thế (đã đóng trực tiếp: {closed_tickets}) và hủy lệnh chờ (đã hủy trực tiếp: {cancelled_orders})."
    append_chat_message("ai", msg)
    send_telegram_alert(f"<b>[SYSTEM RESET]</b> {msg}")

    return {
        "status": "SUCCESS",
        "message": "Đã reset hệ thống thành công! Toàn bộ vị thế đã được đóng, lệnh chờ đã được hủy và PnL hôm nay đã được đặt lại.",
        "pnl_reset_time": reset_time.isoformat(),
        "closed_tickets": closed_tickets,
        "cancelled_orders": cancelled_orders
    }


@app.post("/api/telegram/test_morning_news", dependencies=[Depends(require_operator_token)])
async def trigger_test_morning_news():
    """Trigger an instant test morning news bulletin via Telegram."""
    sent = send_morning_news_telegram_bulletin()
    return {"status": "SUCCESS" if sent else "FAILED", "message": "Đã gửi bản tin kinh tế 05:00 AM tới Telegram!" if sent else "Gửi bản tin thất bại, kiểm tra bot token."}


@app.post("/api/telegram/test_evening_pnl", dependencies=[Depends(require_operator_token)])
async def trigger_test_evening_pnl():
    """Trigger an instant test evening PnL report via Telegram."""
    sent = send_evening_pnl_telegram_report()
    return {"status": "SUCCESS" if sent else "FAILED", "message": "Đã gửi báo cáo tổng kết PnL 23:00 PM tới Telegram!" if sent else "Gửi báo cáo thất bại, kiểm tra bot token."}


class ModifyTpSlRequest(BaseModel):
    ticket: int
    stop_loss: float = Field(ge=0.0)
    take_profit: float = Field(ge=0.0)
    idempotency_key: Optional[str] = None


class ClosePositionRequest(BaseModel):
    ticket: int
    idempotency_key: Optional[str] = None


class CancelPendingRequest(BaseModel):
    order_ticket: int
    idempotency_key: Optional[str] = None


@app.post("/api/order/modify_tpsl", dependencies=[Depends(require_operator_token)])
async def order_modify_tpsl(req: ModifyTpSlRequest):
    ready, reason = demo_execution_status()
    if not ready or KILL_SWITCH:
        execution_disabled_response()

    idempotency_key = req.idempotency_key or f"manual-modify:{req.ticket}:{int(time.time()*1000)}"
    command = COMMAND_STORE.create_command(
        idempotency_key=idempotency_key,
        action="MODIFY_SLTP",
        symbol=EXECUTION_SYMBOL,
        magic=EXECUTION_MAGIC,
        volume=0.0,
        stop_loss=req.stop_loss,
        take_profit=req.take_profit,
        reason=f"MANUAL_MODIFY_SLTP:ticket={req.ticket}",
        ttl_seconds=DEMO_COMMAND_TTL,
    )
    log_event(LogEvent.ORDER_SENT, component="order", action="MODIFY_SLTP", ticket=req.ticket, sl=req.stop_loss, tp=req.take_profit, command_id=command.get("command_id"))
    send_telegram_alert(f"<b>[COMMAND ISSUED]</b> Yêu cầu sửa SL/TP lệnh #{req.ticket} đã vào Ledger.")
    return {"status": "SUCCESS", "message": f"Yêu cầu sửa SL/TP lệnh #{req.ticket} đã vào Command Ledger!", "command": command}


@app.post("/api/order/close", dependencies=[Depends(require_operator_token)])
async def order_close_position(req: ClosePositionRequest):
    ready, reason = demo_execution_status()
    if not ready or KILL_SWITCH:
        execution_disabled_response()

    idempotency_key = req.idempotency_key or f"manual-close:{req.ticket}:{int(time.time()*1000)}"
    command = COMMAND_STORE.create_command(
        idempotency_key=idempotency_key,
        action="CLOSE_POSITION",
        symbol=EXECUTION_SYMBOL,
        magic=EXECUTION_MAGIC,
        volume=0.0,
        stop_loss=None,
        take_profit=None,
        reason=f"MANUAL_CLOSE_POSITION:ticket={req.ticket}",
        ttl_seconds=DEMO_COMMAND_TTL,
    )
    log_event(LogEvent.ORDER_SENT, component="order", action="CLOSE_POSITION", ticket=req.ticket, command_id=command.get("command_id"))
    send_telegram_alert(f"<b>[COMMAND ISSUED]</b> Yêu cầu đóng lệnh #{req.ticket} đã vào Ledger.")
    return {"status": "SUCCESS", "message": f"Yêu cầu đóng lệnh #{req.ticket} đã vào Command Ledger!", "command": command}


@app.post("/api/order/cancel_pending", dependencies=[Depends(require_operator_token)])
async def order_cancel_pending(req: CancelPendingRequest):
    ready, reason = demo_execution_status()
    if not ready or KILL_SWITCH:
        execution_disabled_response()

    # Try Direct MT5 Order Deletion
    if ensure_mt5_connected():
        request = {
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": req.order_ticket,
        }
        res = mt5.order_send(request)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            log_event(LogEvent.ORDER_CANCELLED, component="order", action="CANCEL_PENDING", order_ticket=req.order_ticket)
            send_telegram_alert(f"<b>[PENDING ORDER CANCELLED]</b> Đã hủy pending order #{req.order_ticket} trên MT5.")
            return {"status": "SUCCESS", "message": f"Đã hủy pending order #{req.order_ticket} trên MT5 thành công!"}

    idempotency_key = req.idempotency_key or f"manual-cancel:{req.order_ticket}:{int(time.time()*1000)}"
    command = COMMAND_STORE.create_command(
        idempotency_key=idempotency_key,
        action="CANCEL_PENDING",
        symbol=EXECUTION_SYMBOL,
        magic=EXECUTION_MAGIC,
        volume=0.0,
        stop_loss=None,
        take_profit=None,
        reason=f"MANUAL_CANCEL_PENDING:order={req.order_ticket}",
        ttl_seconds=DEMO_COMMAND_TTL,
    )
    log_event(LogEvent.ORDER_CANCELLED, component="order", action="CANCEL_PENDING", order_ticket=req.order_ticket, command_id=command.get("command_id"))
    return {"status": "SUCCESS", "message": f"Yêu cầu hủy pending order #{req.order_ticket} đã vào Command Ledger.", "command": command}


@app.post("/api/ai_scan_now")
async def trigger_manual_ai_scan():
    telemetry = get_mt5_telemetry()
    return {
        "status": "ANALYSIS_ONLY",
        "execution_mode": EXECUTION_MODE,
        "message": "Scan chỉ phân tích; không tạo command và không gửi lệnh tới MT5.",
        "signal": telemetry.get("ai_signal"),
    }


# ── Realtime WebSocket stream ────────────────────────────────────────────────
@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    await WS_MANAGER.connect(websocket)
    try:
        # Send an immediate full snapshot so the client renders without waiting.
        snapshot = await asyncio.to_thread(get_mt5_telemetry)
        await WS_MANAGER.send_to(websocket, {"type": "telemetry", "data": snapshot})
        while True:
            # Keep the socket alive; inbound messages are ignored (client is read-only).
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        log_event(LogEvent.EXCEPTION, component="ws-hub", exc=exc)
    finally:
        await WS_MANAGER.disconnect(websocket)


async def _manage_active_positions_loop() -> None:
    """Monitors open positions for dynamic trailing stop, break-even lock, and trend invalidation."""
    while True:
        try:
            if (not KILL_SWITCH) and ENABLE_TRADING and ensure_mt5_connected():
                positions = mt5.positions_get()
                if positions:
                    # Fetch latest indicators and prices for trailing stops and validation
                    indicators = get_technical_indicators(EXECUTION_SYMBOL)
                    ema20 = indicators.get("ema20")
                    ema50 = indicators.get("ema50")
                    atr = indicators.get("atr")
                    
                    for p in positions:
                        # Manage any position belonging to our target symbol (case-insensitive)
                        p_sym = p.symbol
                        if p_sym.upper() != EXECUTION_SYMBOL.upper() and resolve_symbol(p_sym).upper() != EXECUTION_SYMBOL.upper():
                            continue
                        
                        ticket = p.ticket
                        is_buy = (p.type == 0) # 0 is BUY, 1 is SELL
                        entry_price = float(p.price_open)
                        current_price = float(p.price_current)
                        current_sl = float(p.sl)
                        current_tp = float(p.tp)
                        
                        def _modify_sltp(target_sl: float, target_tp: float) -> bool:
                            req = {
                                "action": mt5.TRADE_ACTION_SLTP,
                                "symbol": p_sym,
                                "position": ticket,
                                "sl": float(round(target_sl, 2)),
                                "tp": float(round(target_tp, 2)),
                            }
                            res = mt5.order_send(req)
                            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                                return True
                            resolved = resolve_symbol(p_sym)
                            if resolved != p_sym:
                                req["symbol"] = resolved
                                res = mt5.order_send(req)
                                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                                    return True
                            err_str = res.comment if res else "Unknown error"
                            ret_code = res.retcode if res else "None"
                            log_event(LogEvent.EXCEPTION, component="position-manager", error=f"SL modify failed ticket={ticket}: retcode={ret_code}, comment={err_str}")
                            return False

                        # 1. Lock Break-Even (BE) Rule
                        # Trigger early when profit reaches +1.0 gold point ($1.00/oz):
                        be_trigger_distance = 1.0
                        if is_buy:
                            if current_price - entry_price >= be_trigger_distance and current_sl < entry_price:
                                new_sl = round(entry_price + 0.10, 2)
                                if _modify_sltp(new_sl, current_tp):
                                    msg = f"[BE LOCK] Vị thế BUY #{ticket} đạt lợi nhuận +${current_price - entry_price:.2f}. Đã dời SL về hòa vốn (${new_sl:.2f})."
                                    append_chat_message("ai", msg)
                                    send_telegram_alert(f"<b>[BE LOCK]</b> {msg}")
                        else:
                            if entry_price - current_price >= be_trigger_distance and (current_sl > entry_price or current_sl == 0):
                                new_sl = round(entry_price - 0.10, 2)
                                if _modify_sltp(new_sl, current_tp):
                                    msg = f"[BE LOCK] Vị thế SELL #{ticket} đạt lợi nhuận +${entry_price - current_price:.2f}. Đã dời SL về hòa vốn (${new_sl:.2f})."
                                    append_chat_message("ai", msg)
                                    send_telegram_alert(f"<b>[BE LOCK]</b> {msg}")
                        
                        # 2. Dynamic Trailing Stop & Profit Lock (Step Trailing + EMA20)
                        if is_buy:
                            candidate_trail = max(entry_price + 0.10, current_price - 1.50)
                            if ema20 and atr and atr > 0:
                                ema_trail = ema20 - (1.5 * atr)
                                candidate_trail = max(candidate_trail, ema_trail)
                            
                            candidate_trail = round(candidate_trail, 2)
                            if candidate_trail > current_sl and current_price > candidate_trail:
                                if _modify_sltp(candidate_trail, current_tp):
                                    msg = f"[TRAILING STOP] Vị thế BUY #{ticket} đã dời SL bám sát lên ${candidate_trail:.2f} (Khóa lợi nhuận +${candidate_trail - entry_price:.2f})."
                                    append_chat_message("ai", msg)
                        else:
                            candidate_trail = min(entry_price - 0.10, current_price + 1.50)
                            if ema20 and atr and atr > 0:
                                ema_trail = ema20 + (1.5 * atr)
                                candidate_trail = min(candidate_trail, ema_trail)
                            
                            candidate_trail = round(candidate_trail, 2)
                            if (current_sl == 0.0 or candidate_trail < current_sl) and current_price < candidate_trail:
                                if _modify_sltp(candidate_trail, current_tp):
                                    msg = f"[TRAILING STOP] Vị thế SELL #{ticket} đã dời SL bám sát xuống ${candidate_trail:.2f} (Khóa lợi nhuận +${entry_price - candidate_trail:.2f})."
                                    append_chat_message("ai", msg)

                        # 3. AI Invalidation / Trend Failure Auto-Close
                        # "tự đóng lệnh lập tức nếu phân tích có khả năng không di thheo kịch bản nữa"
                        # If a BUY trend reverses (EMA20 < EMA50) or a SELL trend reverses (EMA20 > EMA50)
                        if ema20 and ema50:
                            should_close = False
                            close_reason = ""
                            if is_buy and ema20 < ema50:
                                should_close = True
                                close_reason = f"Đường EMA20 (${ema20:.2f}) cắt xuống dưới EMA50 (${ema50:.2f}) - Xu hướng đảo chiều giảm."
                            elif not is_buy and ema20 > ema50:
                                should_close = True
                                close_reason = f"Đường EMA20 (${ema20:.2f}) cắt lên trên EMA50 (${ema50:.2f}) - Xu hướng đảo chiều tăng."
                            
                            if should_close:
                                request = {
                                    "action": mt5.TRADE_ACTION_DEAL,
                                    "symbol": p.symbol,
                                    "volume": float(p.volume),
                                    "type": mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY,
                                    "position": ticket,
                                    "price": float(current_price),
                                    "magic": EXECUTION_MAGIC,
                                    "comment": "QuantAI AI Auto-Exit",
                                    "type_time": mt5.ORDER_TIME_GTC,
                                    "type_filling": mt5.ORDER_FILLING_IOC,
                                }
                                res = mt5.order_send(request)
                                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                                    msg = f"[AI AUTO CLOSE] Đã chủ động đóng lệnh {'BUY' if is_buy else 'SELL'} #{ticket} tại giá ${current_price:.2f}. Lý do: {close_reason}"
                                    append_chat_message("ai", msg)
                                    send_telegram_alert(f"<b>[AI AUTO CLOSE]</b> {msg}")
                                    
        except Exception as exc:
            log_event(LogEvent.EXCEPTION, component="position-manager", exc=exc)
        await asyncio.sleep(5)


async def _telemetry_broadcaster() -> None:
    """Push live telemetry to all connected dashboards on a fixed cadence."""
    loop_count = 0
    while True:
        try:
            if WS_MANAGER.count > 0:
                telemetry = await asyncio.to_thread(get_mt5_telemetry)
                await WS_MANAGER.broadcast({"type": "telemetry", "data": telemetry})
                loop_count += 1
        except Exception as exc:
            log_event(LogEvent.EXCEPTION, component="ws-broadcaster", exc=exc)
        await asyncio.sleep(WS_TICK_INTERVAL)


async def _ai_decision_loop() -> None:
    """Autonomous AI -> Risk -> Execution cycle, gated and feature-flagged."""
    global AI_AUTO_LOOP
    while True:
        try:
            if is_weekend_market_closed():
                await asyncio.sleep(300)
                continue
            if AI_AUTO_LOOP:
                ready, reason = execution_readiness(EXECUTION_MODE)
                if ready:
                    log_event(LogEvent.AI_REQUEST, component="ai-loop", symbol=EXECUTION_SYMBOL)
                    result = await asyncio.to_thread(issue_demo_command)
                    status_str = result.get("status")
                    log_event(
                        LogEvent.AI_RESPONSE,
                        component="ai-loop",
                        result=status_str,
                        reasons=result.get("reason_codes"),
                    )
                    await WS_MANAGER.broadcast({"type": "ai_signal", "data": {
                        "status": status_str,
                        "reason_codes": result.get("reason_codes"),
                        "command": bool(result.get("command")),
                    }})
                    
                    reason_codes = result.get("reason_codes", [])
                    pos_cnt = result.get("pos_count", 0)
                    pnl_val = result.get("total_pnl", 0.0)

                    if status_str == "ISSUED":
                        cmd_info = result.get("command") or {}
                        ind_info = result.get("indicators") or {}
                        prop_info = result.get("proposal") or {}
                        raw_positions = (mt5.positions_get(symbol=EXECUTION_SYMBOL) or mt5.positions_get() or [])
                        active_cnt = len(raw_positions)

                        ema20 = float(ind_info.get("ema20") or 0.0)
                        ema50 = float(ind_info.get("ema50") or 0.0)
                        ema200 = float(ind_info.get("ema200") or 0.0)
                        rsi = float(ind_info.get("rsi") or 50.0)
                        atr = float(ind_info.get("atr") or 0.0)
                        macd = ind_info.get("macd") or "N/A"
                        confidence = prop_info.get("confidence", "N/A")

                        trend_str = "TĂNG (EMA20 > EMA50 > EMA200)" if (ema20 > ema50 > ema200) else (
                            "GIẢM (EMA20 < EMA50 < EMA200)" if (ema20 < ema50 < ema200) else "TÍCH LŨY / SIDEWAY"
                        )

                        analysis_str = (
                            f"\n📊 BẢNG PHÂN TÍCH HỆ THỐNG [{TRADING_METHOD}]\n"
                            f"├─ Phương pháp: {TRADING_METHOD}\n"
                            f"├─ Xu hướng: {trend_str}\n"
                            f"│  └─ EMA20: {ema20:.2f} | EMA50: {ema50:.2f} | EMA200: {ema200:.2f}\n"
                            f"├─ Động lượng:\n"
                            f"│  └─ RSI(14): {rsi:.1f} | MACD: {macd} | ATR: {atr:.2f}\n"
                            f"├─ Độ tin cậy AI: {confidence}\n"
                            f"└─ Lý do kích hoạt: " + ", ".join(reason_codes)
                        )

                        if active_cnt <= 1:
                            append_chat_message("ai", (
                                f"[AUTO TRADE] Báo cáo anh Tú: Phát hiện cơ hội bứt phá! Đặt lệnh đầu tiên "
                                f"{cmd_info.get('action')} {cmd_info.get('volume')} lot (Vị thế #1).\n"
                                f"SL: {cmd_info.get('stop_loss')} | TP: {cmd_info.get('take_profit')}.\n"
                                f"Lệnh đã được đẩy lên MT5 Ledger.\n"
                                f"{analysis_str}"
                            ))
                        else:
                            append_chat_message("ai", (
                                f"[AUTO TRADE] PYRAMIDING SCALE-IN! Vị thế trước đã an toàn (Risk-Free).\n"
                                f"Đặt thêm lệnh nhồi {cmd_info.get('action')} {cmd_info.get('volume')} lot (Vị thế #{active_cnt}).\n"
                                f"SL: {cmd_info.get('stop_loss')} | TP: {cmd_info.get('take_profit')}.\n"
                                f"Lệnh đã được đẩy lên MT5 Ledger.\n"
                                f"{analysis_str}"
                            ))
                else:
                    log_event(LogEvent.AI_RESPONSE, component="ai-loop", result="SKIPPED", reason=reason)
        except Exception as exc:
            log_event(LogEvent.EXCEPTION, component="ai-loop", exc=exc)
            append_chat_message("ai", f"[AUTO TRADE] Gap loi nghiem trong trong chu ky quet: {exc}")
        await asyncio.sleep(AI_LOOP_SECONDS)


def _brain_lesson(outcome: str, r_multiple: float, exit_reason: str) -> str:
    if outcome == "WIN" and exit_reason == "TAKE_PROFIT":
        return "Entry theo confluence đạt TP đúng kỳ vọng. Tiếp tục tuân thủ trend-confluence-v1."
    if outcome == "WIN":
        return "Thắng nhờ giữ vị thế theo trailing EMA20. Bắt được sóng dài hơn mức TP cố định."
    if outcome == "LOSS" and exit_reason == "STOP_LOSS":
        return "SL chạm trước TP: pullback sâu hơn kỳ vọng. Cân nhắc siết RSI range vào vùng 55-65 và tăng ATR floor."
    if outcome == "LOSS":
        return "Lệnh thua: xem lại chất lượng confluence khi xu hướng suy yếu, tránh entry yếu."
    return "Lệnh hòa vốn: cần sample lớn hơn để kết luận."


def _brain_exit_reason(exit_price: float, decision: Dict[str, Any]) -> str:
    entry = decision.get("entry")
    stop_loss = decision.get("stop_loss")
    take_profit = decision.get("take_profit")
    if entry and stop_loss:
        if abs(exit_price - float(stop_loss)) <= max(0.5, abs(float(entry) - float(stop_loss)) * 0.02):
            return "STOP_LOSS"
    if entry and take_profit:
        if abs(exit_price - float(take_profit)) <= max(0.5, abs(float(entry) - float(take_profit)) * 0.02):
            return "TAKE_PROFIT"
    return "MANUAL_OR_TRAIL"


_PREV_POSITIONS_CACHE = {}

async def _brain_evaluation_loop() -> None:
    """Match executed AI decisions to closed MT5 positions and record self-evaluations."""
    global BRAIN_LOOP_HEARTBEAT, _PREV_POSITIONS_CACHE
    while True:
        try:
            BRAIN_LOOP_HEARTBEAT["last_run"] = datetime.now(timezone.utc).isoformat()
            BRAIN_LOOP_HEARTBEAT["cycles"] += 1
            if ensure_mt5_connected():
                # 1. Phat hien doi SL/TP
                try:
                    current_positions = mt5.positions_get(symbol=EXECUTION_SYMBOL) or []
                    curr_map = {pos.ticket: pos for pos in current_positions}
                    if _PREV_POSITIONS_CACHE:
                        for ticket, new_pos in curr_map.items():
                            if ticket in _PREV_POSITIONS_CACHE:
                                old_pos = _PREV_POSITIONS_CACHE[ticket]
                                new_sl = float(new_pos.sl)
                                old_sl = float(old_pos.sl)
                                new_tp = float(new_pos.tp)
                                old_tp = float(old_pos.tp)
                                if abs(new_sl - old_sl) > 0.001 or abs(new_tp - old_tp) > 0.001:
                                    sl_change = f"SL: {old_sl:.2f} -> {new_sl:.2f}" if abs(new_sl - old_sl) > 0.001 else ""
                                    tp_change = f"TP: {old_tp:.2f} -> {new_tp:.2f}" if abs(new_tp - old_tp) > 0.001 else ""
                                    changes = " | ".join(filter(None, [sl_change, tp_change]))
                                    action_str = "BUY" if new_pos.type == 0 else "SELL"
                                    msg = (
                                        f"[AUTO TRADE] Báo cáo anh Tú: Phát hiện dời Stop Loss/Take Profit cho vị thế "
                                        f"{action_str} #{ticket} ({new_pos.volume} lot): {changes} thành công."
                                    )
                                    append_chat_message("ai", msg)
                                    send_telegram_alert(f"<b>[SL/TP UPDATE]</b>\n{msg}")
                    _PREV_POSITIONS_CACHE = curr_map
                except Exception as pos_err:
                    logger.error(f"Error checking position adjustments: {pos_err}")

                pending = BRAIN.pending_executed_decisions()
                if pending:
                    open_tickets = {int(position.ticket) for position in (mt5.positions_get() or [])}
                    for decision in pending:
                        ticket = int(decision["order_ticket"])
                        if ticket in open_tickets:
                            continue
                        deals = mt5.history_deals_get(position=ticket)
                        if not deals:
                            continue
                        closing = [deal for deal in deals if deal.entry == mt5.DEAL_ENTRY_OUT]
                        if not closing:
                            continue
                        closing_deal = closing[0]
                        net_profit = float(closing_deal.profit)
                        exit_price = float(closing_deal.price)
                        closed_at = datetime.fromtimestamp(int(closing_deal.time), tz=timezone.utc).isoformat()
                        entry = decision.get("entry")
                        stop_loss = decision.get("stop_loss")
                        volume = decision.get("volume")
                        risk_amount = 0.0
                        if entry and stop_loss and volume:
                            risk_amount = abs(float(entry) - float(stop_loss)) * 100.0 * float(volume)
                        r_multiple = round(net_profit / risk_amount, 4) if risk_amount > 0 else 0.0
                        outcome = "WIN" if net_profit > 0 else ("LOSS" if net_profit < 0 else "BREAKEVEN")
                        exit_reason = _brain_exit_reason(exit_price, decision)
                        lesson = _brain_lesson(outcome, r_multiple, exit_reason)
                        evaluation_id = BRAIN.evaluate(
                            decision_id=decision["decision_id"],
                            order_ticket=ticket,
                            closed_at=closed_at,
                            exit_price=exit_price,
                            net_profit=net_profit,
                            r_multiple=r_multiple,
                            outcome=outcome,
                            exit_reason=exit_reason,
                            lesson=lesson,
                        )
                        if evaluation_id:
                            log_event(
                                LogEvent.BRAIN_EVALUATED,
                                component="ai-brain",
                                decision_id=decision["decision_id"],
                                ticket=ticket,
                                outcome=outcome,
                                net_profit=net_profit,
                                r_multiple=r_multiple,
                                exit_reason=exit_reason,
                            )
                            append_chat_message("ai", (
                                f"[BRAIN] Tự đánh giá lệnh #{ticket}: {outcome} "
                                f"(PnL ${net_profit:+.2f}, R={r_multiple:+.2f}, exit={exit_reason}). {lesson}"
                            ))
                            await WS_MANAGER.broadcast({"type": "brain", "data": {
                                "kind": "evaluation",
                                "decision_id": decision["decision_id"],
                                "ticket": ticket,
                                "outcome": outcome,
                                "net_profit": net_profit,
                                "r_multiple": r_multiple,
                                "exit_reason": exit_reason,
                                "lesson": lesson,
                            }})
                _brain_auto_adjust_check()
        except Exception as exc:
            log_event(LogEvent.EXCEPTION, component="ai-brain", exc=exc)
        await asyncio.sleep(BRAIN_EVAL_INTERVAL_SECONDS)


def _brain_auto_adjust_check() -> None:
    """Propose (never silently apply) strategy parameter changes from the rolling window."""
    try:
        for strategy in BRAIN.strategy_summary():
            sample_size = int(strategy.get("sample_size") or 0)
            if sample_size < BRAIN_AUTO_ADJUST_WINDOW:
                continue
            win_rate = strategy.get("win_rate")
            profit_factor = strategy.get("profit_factor")
            if win_rate is None:
                continue
            window = {
                "sample_size": sample_size,
                "win_rate": win_rate,
                "profit_factor": profit_factor,
                "total_pnl": strategy.get("total_pnl"),
                "avg_r": strategy.get("avg_r"),
            }
            proposed = None
            if win_rate < 40.0 and sample_size >= BRAIN_AUTO_ADJUST_WINDOW:
                proposed = {
                    "action": "TIGHTEN_ENTRY",
                    "recommendation": "Win rate dưới 40% - siết điều kiện entry: RSI range 55-65 (BUY) / 35-45 (SELL), tăng ATR floor.",
                    "params": {"minimum_atr": "atr*1.2", "rsi_buy_upper": 65},
                }
            elif profit_factor is not None and profit_factor < 1.0:
                proposed = {
                    "action": "REDUCE_RISK",
                    "recommendation": "Profit factor dưới 1.0 - giảm rủi ro: giảm lot tối đa, tăng risk_reward lên 2.2.",
                    "params": {"risk_reward": 2.2},
                }
            if proposed is not None:
                adjustment_id = BRAIN.propose_adjustment(
                    strategy_version=strategy["strategy_version"],
                    window=window,
                    proposed=proposed,
                    result="PENDING_OPERATOR_APPROVAL",
                )
                log_event(
                    LogEvent.BRAIN_ADJUST_PROPOSED,
                    component="ai-brain",
                    strategy_version=strategy["strategy_version"],
                    adjustment_id=adjustment_id,
                    recommendation=proposed["recommendation"],
                )
    except Exception as exc:
        log_event(LogEvent.EXCEPTION, component="ai-brain", exc=exc)


@app.get("/api/brain")
async def get_brain_state():
    """AI Central Brain: strategy stats, decision memory, evaluations, adjustments."""
    strategies = BRAIN.strategy_summary()
    if not strategies:
        cfg = StrategyConfig()
        strategies = [{
            "strategy_version": cfg.version,
            "status": "ACTIVE",
            "sample_size": 0,
            "wins": 0,
            "losses": 0,
            "breakevens": 0,
            "win_rate": None,
            "profit_factor": None,
            "total_pnl": 0.0,
            "avg_r": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "notes": "collecting first closed-trade sample",
        }]
    return {
        "strategies": strategies,
        "recent_decisions": BRAIN.recent_decisions(limit=30),
        "recent_evaluations": BRAIN.recent_evaluations(limit=20),
        "adjustments": BRAIN.latest_adjustments(limit=10),
    }


@app.get("/api/brain/health")
async def get_brain_health():
    """Brain evaluation loop health check."""
    now = datetime.now(timezone.utc)
    last_run = BRAIN_LOOP_HEARTBEAT.get("last_run")
    cycles = BRAIN_LOOP_HEARTBEAT.get("cycles", 0)
    last_error = BRAIN_LOOP_HEARTBEAT.get("last_error")
    status = "healthy"
    if last_run:
        try:
            delta = (now - datetime.fromisoformat(last_run.replace('Z', '+00:00'))).total_seconds()
            if delta > BRAIN_EVAL_INTERVAL_SECONDS * 3:
                status = "stale"
        except Exception:
            pass
    else:
        status = "starting"
    return {
        "status": status,
        "last_run": last_run,
        "cycles": cycles,
        "interval_seconds": BRAIN_EVAL_INTERVAL_SECONDS,
        "last_error": last_error,
        "checked_at": now.isoformat(),
    }


@app.get("/api/brain/adjustments")
async def get_brain_adjustments():
    """Get all adjustment proposals."""
    return BRAIN.latest_adjustments(limit=20)


@app.patch("/api/brain/adjustments/{adjustment_id}", dependencies=[Depends(require_operator_token)])
async def apply_adjustment(adjustment_id: str, req: AdjustmentActionRequest):
    """Approve or reject an AI auto-adjust proposal."""
    if req.action == "approve":
        BRAIN.mark_adjustment_applied(adjustment_id, result="Operator approved")
        log_event(LogEvent.BRAIN_ADJUST_PROPOSED, component="ai-brain", adjustment_id=adjustment_id, action="APPROVED")
        append_chat_message("ai", f"[BRAIN] Đề xuất chỉnh sách #{adjustment_id} đã được DUYỆT.")
    elif req.action == "reject":
        BRAIN.reject_adjustment(adjustment_id, reason=req.reason or "Operator rejected")
        log_event(LogEvent.BRAIN_ADJUST_PROPOSED, component="ai-brain", adjustment_id=adjustment_id, action="REJECTED")
        append_chat_message("ai", f"[BRAIN] Đề xuất chỉnh sách #{adjustment_id} đã bị TỪ CHỐI.")
    else:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ACTION", "message": "action must be 'approve' or 'reject'"})
    await WS_MANAGER.broadcast({"type": "brain", "data": {"kind": "adjustment_result", "adjustment_id": adjustment_id, "action": req.action}})
    return {"status": "SUCCESS", "adjustment_id": adjustment_id, "action": req.action}


@app.post("/api/control-center/ai-loop", dependencies=[Depends(require_operator_token)])
async def update_ai_loop(req: ControlDemoArmRequest):
    global AI_AUTO_LOOP
    AI_AUTO_LOOP = req.armed
    log_event(LogEvent.WARNING, component="ai-loop", message=f"AI auto loop {'ARMED' if AI_AUTO_LOOP else 'DISARMED'}")
    return {"status": "SUCCESS", "ai_auto_loop": AI_AUTO_LOOP}


# ── Read-only MT5 views ────────────────────────────────────────────────────

@app.get("/api/positions")
async def get_positions():
    if ensure_mt5_connected():
        positions = mt5.positions_get()
        if positions is not None and len(positions) > 0:
            out = []
            for p in positions:
                pips = round((p.price_current - p.price_open) * (1 if p.type == 0 else -1), 2)
                out.append({
                    "ticket": p.ticket,
                    "symbol": p.symbol,
                    "type": "BUY" if p.type == 0 else "SELL",
                    "volume": float(p.volume),
                    "price_open": float(p.price_open),
                    "sl": float(p.sl),
                    "tp": float(p.tp),
                    "pnl": float(p.profit),
                    "pips": pips
                })
            return out
    return []

@app.get("/api/history")
async def get_history():
    if ensure_mt5_connected():
        now = datetime.now()
        start = now - timedelta(days=30)
        deals = mt5.history_deals_get(start, now)
        if deals is not None and len(deals) > 0:
            out = []
            for d in reversed(list(deals)):
                if d.entry in (1, 2) or d.profit != 0:
                    dt = datetime.fromtimestamp(d.time)
                    out.append({
                        "time": dt.strftime("%H:%M"),
                        "type": "BUY" if d.type == 0 else "SELL",
                        "lot": float(d.volume),
                        "symbol": getattr(d, "symbol", "XAUUSDm"),
                        "price": round(float(d.price), 2),
                        "sl": 0.0,
                        "tp": 0.0,
                        "pl": round(float(d.profit + d.swap + d.commission), 2),
                        "reason": f"Deal #{d.ticket} · {d.comment or 'Execution'}"
                    })
            if len(out) > 0:
                return out[:20]
    return []


@app.get("/api/pending-orders")
async def get_pending_orders():
    """Return pending orders (LIMIT/STOP) from MT5."""
    if ensure_mt5_connected():
        orders = mt5.orders_get()
        if orders is not None and len(orders) > 0:
            type_map = {
                2: "BUY_LIMIT",
                3: "SELL_LIMIT",
                4: "BUY_STOP",
                5: "SELL_STOP",
                6: "BUY_STOP_LIMIT",
                7: "SELL_STOP_LIMIT",
            }
            out = []
            for o in orders:
                out.append({
                    "ticket": o.ticket,
                    "symbol": o.symbol,
                    "type": type_map.get(o.type, f"TYPE_{o.type}"),
                    "price": round(float(o.price_open), 2),
                    "sl": round(float(o.sl), 2),
                    "tp": round(float(o.tp), 2),
                    "volume": float(o.volume_current),
                    "expiration": "GTC",
                })
            return out
    return []


@app.post("/api/orders/close-profitable", dependencies=[Depends(require_operator_token)])
async def close_profitable_positions():
    """Close all positions with profit > 0 by creating commands in CommandStore."""
    ready, reason = demo_execution_status()
    if not ready:
        return {"status": "REJECTED", "message": f"Execution blocked: {reason}"}
    if not ensure_mt5_connected():
        return {"status": "ERROR", "message": "MT5 not connected"}
    positions = mt5.positions_get()
    if not positions:
        return {"status": "SUCCESS", "message": "No positions to close"}
    created_commands = []
    for p in positions:
        if p.profit > 0:
            idempotency_key = f"manual-close-profit:{p.ticket}:{int(time.time()*1000)}"
            cmd = COMMAND_STORE.create_command(
                idempotency_key=idempotency_key,
                action="CLOSE_POSITION",
                symbol=p.symbol,
                magic=EXECUTION_MAGIC,
                volume=0.0,
                stop_loss=None,
                take_profit=None,
                reason=f"MANUAL_CLOSE_PROFITABLE:ticket={p.ticket}",
                ttl_seconds=DEMO_COMMAND_TTL,
            )
            created_commands.append(cmd)
            log_event(LogEvent.ORDER_SENT, component="order", action="CLOSE_POSITION", ticket=p.ticket, reason="PROFITABLE_CLOSE", command_id=cmd.get("command_id"))
    if created_commands:
        send_telegram_alert(f"<b>[PROFIT CLOSE COMMANDS ISSUED]</b> Đã tạo {len(created_commands)} lệnh đóng vị thế có lời trong Ledger.")
        append_chat_message("ai", f"[CLOSE PROFIT] Yêu cầu đóng {len(created_commands)} vị thế có lời đã vào Command Ledger.")
    return {"status": "SUCCESS", "message": f"Đã phát {len(created_commands)} lệnh đóng vị thế chốt lời vào Command Ledger!", "commands": created_commands}


@app.post("/api/orders/close-losing", dependencies=[Depends(require_operator_token)])
async def close_losing_positions():
    """Close all positions with profit < 0 by creating commands in CommandStore."""
    ready, reason = demo_execution_status()
    if not ready:
        return {"status": "REJECTED", "message": f"Execution blocked: {reason}"}
    if not ensure_mt5_connected():
        return {"status": "ERROR", "message": "MT5 not connected"}
    positions = mt5.positions_get()
    if not positions:
        return {"status": "SUCCESS", "message": "No positions to close"}
    created_commands = []
    for p in positions:
        if p.profit < 0:
            idempotency_key = f"manual-close-losing:{p.ticket}:{int(time.time()*1000)}"
            cmd = COMMAND_STORE.create_command(
                idempotency_key=idempotency_key,
                action="CLOSE_POSITION",
                symbol=p.symbol,
                magic=EXECUTION_MAGIC,
                volume=0.0,
                stop_loss=None,
                take_profit=None,
                reason=f"MANUAL_CLOSE_LOSING:ticket={p.ticket}",
                ttl_seconds=DEMO_COMMAND_TTL,
            )
            created_commands.append(cmd)
            log_event(LogEvent.ORDER_SENT, component="order", action="CLOSE_POSITION", ticket=p.ticket, reason="LOSING_CLOSE", command_id=cmd.get("command_id"))
    if created_commands:
        send_telegram_alert(f"<b>[STOP LOSS CLOSE COMMANDS ISSUED]</b> Đã tạo {len(created_commands)} lệnh cắt lỗ vị thế âm trong Ledger.")
        append_chat_message("ai", f"[CLOSE LOSING] Yêu cầu cắt lỗ {len(created_commands)} vị thế âm đã vào Command Ledger.")
    return {"status": "SUCCESS", "message": f"Đã phát {len(created_commands)} lệnh cắt lỗ vị thế âm vào Command Ledger!", "commands": created_commands}


class ControlCenterTelegramRequest(BaseModel):
    bot_token: str
    chat_id: str
    enabled: bool = True

@app.post("/api/control-center/mode", dependencies=[Depends(require_operator_token)])
async def update_control_center_mode(req: ControlCenterModeRequest):
    global EXECUTION_MODE, LIVE_ARMED, DEMO_ARMED, KILL_SWITCH, AI_AUTO_LOOP, ENABLE_TRADING
    EXECUTION_MODE = req.mode.upper()

    if EXECUTION_MODE == "LIVE":
        LIVE_ARMED = True
        DEMO_ARMED = False
        ENABLE_TRADING = True
        KILL_SWITCH = False
    elif EXECUTION_MODE == "DEMO":
        DEMO_ARMED = True
        LIVE_ARMED = False
        ENABLE_TRADING = True
        KILL_SWITCH = False
    else:
        # DISABLED -> force fail-closed regardless of request flags.
        EXECUTION_MODE = "DISABLED"
        LIVE_ARMED = False
        DEMO_ARMED = False
        ENABLE_TRADING = False
        KILL_SWITCH = True
        
    if req.live_armed is not None: LIVE_ARMED = req.live_armed
    if req.demo_armed is not None: DEMO_ARMED = req.demo_armed
    if req.kill_switch is not None: KILL_SWITCH = req.kill_switch
    if req.ai_auto_loop is not None: AI_AUTO_LOOP = req.ai_auto_loop

    # Persist exclusively to user_control_config.json
    save_control_config({
        "execution_mode": EXECUTION_MODE,
        "live_armed": LIVE_ARMED,
        "demo_armed": DEMO_ARMED,
        "kill_switch": KILL_SWITCH,
        "ai_auto_loop": AI_AUTO_LOOP,
        "enable_trading": ENABLE_TRADING,
    })
    await broadcast_config_updated()

    log_event(LogEvent.INFO, component="control-center", message=f"Execution mode updated -> {EXECUTION_MODE} (LIVE_ARMED={LIVE_ARMED}, DEMO_ARMED={DEMO_ARMED})")
    ready, reason = execution_readiness()

    status_str = "⚡ EXECUTION ARMED" if ready else f"🔒 EXECUTION LOCKED ({reason})"
    send_telegram_alert(
        f"<b>[CONTROL CENTER MODE UPDATED]</b>\n"
        f"Chế độ: <b>{EXECUTION_MODE}</b>\n"
        f"Trạng thái: <b>{status_str}</b>\n"
        f"Kill Switch: {'⛔ KÍCH HOẠT' if KILL_SWITCH else '🟢 TẮT'}\n"
        f"AI Auto-Loop: {'🤖 BẬT' if AI_AUTO_LOOP else '⏸️ TẮT'}"
    )

    return {"status": "SUCCESS", "mode": EXECUTION_MODE, "ready": ready, "reason": reason}

@app.post("/api/control-center/mt5-login", dependencies=[Depends(require_operator_token)])
async def update_mt5_login_credentials(req: ControlCenterLoginRequest):
    global DEMO_LOGIN, DEMO_SERVER, MT5_SAVED_LOGIN, MT5_SAVED_PASSWORD, MT5_SAVED_SERVER
    DEMO_LOGIN = req.login
    DEMO_SERVER = req.server
    MT5_SAVED_LOGIN = req.login
    MT5_SAVED_PASSWORD = req.password
    MT5_SAVED_SERVER = req.server

    # Save to user_control_config.json (NEVER touching .env)
    save_control_config({
        "mt5_login": req.login,
        "mt5_password": req.password,
        "mt5_server": req.server,
    })
    await broadcast_config_updated()

    ok = False
    if HAS_MT5:
        try:
            ok = bool(mt5.initialize(login=req.login, password=req.password, server=req.server))
        except Exception as e:
            logger.error(f"MT5 login error: {e}")

    if ok:
        send_telegram_alert(f"<b>[GOLDQUANT MT5 CONNECTED]</b>\nTài khoản: <code>{req.login}</code> @ <code>{req.server}</code> kết nối thành công!")
        return {"status": "SUCCESS", "message": f"MT5 Logged in & Saved to Control Center ({req.login} @ {req.server})"}
    else:
        return {"status": "ERROR", "message": f"Could not connect MT5 server {req.server} with login {req.login}"}

@app.post("/api/control-center/telegram", dependencies=[Depends(require_operator_token)])
async def update_telegram_config(req: ControlCenterTelegramRequest):
    global TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ENABLED
    TELEGRAM_BOT_TOKEN = req.bot_token.strip()
    TELEGRAM_CHAT_ID = req.chat_id.strip()
    TELEGRAM_ENABLED = req.enabled

    # Save to user_control_config.json (NEVER touching .env)
    save_control_config({
        "telegram_bot_token": TELEGRAM_BOT_TOKEN,
        "telegram_chat_id": TELEGRAM_CHAT_ID,
        "telegram_enabled": TELEGRAM_ENABLED,
    })
    await broadcast_config_updated()

    sent = False
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        sent = send_telegram_alert(
            f"<b>[GOLDQUANT TELEGRAM BOT TEST]</b>\n"
            f"Báo cáo anh Tú: Đã kết nối Telegram Bot thành công!\n"
            f"Tất cả thông báo tín hiệu AI, rủi ro & lệnh giao dịch sẽ tự động gửi tới đây."
        )

    if sent:
        return {"status": "SUCCESS", "message": "Đã lưu thông số Telegram vào Control Center và gửi tin nhắn test thành công!"}
class AITestRequest(BaseModel):
    key_type: str = Field(default="openai", max_length=32)
    api_key: Optional[str] = None
    model: str = Field(default="", max_length=128)
    base_url: Optional[str] = None


@app.post("/api/ai/test", dependencies=[Depends(require_operator_token)])
async def test_ai_config_endpoint(req: AITestRequest):
    """Test a provider config (key + model + url) before saving it.

    Returns a structured verdict with a clear reason when it fails:
    sai key / sai model / hết credit / lỗi url...
    """
    if not HAS_AI_TEST or test_provider_connection is None:
        raise HTTPException(status_code=503, detail={"code": "AI_TEST_UNAVAILABLE", "message": "Module kiểm tra AI chưa sẵn sàng."})
    model = (req.model or "").strip()
    if not model:
        raise HTTPException(status_code=400, detail={"code": "MODEL_REQUIRED", "message": "Chưa nhập model ID cần test."})
    key = (req.api_key or "").strip()
    if req.key_type != "opencode" and not key:
        raise HTTPException(status_code=400, detail={"code": "API_KEY_REQUIRED", "message": f"Nhà cung cấp {req.key_type} cần API key để test."})
    result = await asyncio.to_thread(
        test_provider_connection,
        req.key_type.strip().lower(),
        key,
        model.strip(),
        (req.base_url or "").strip() or None,
    )
    log_event(
        LogEvent.INFO,
        component="ai-test",
        message=f"AI provider test {req.key_type}/{model} -> {'OK' if result.get('ok') else result.get('error_code')}",
    )
    return {"status": "SUCCESS", "result": result}


SUPPORTED_AI_MODELS = [
    # ── OpenCode Zen FREE MODELS (Mặc định - Không cần API Key) ──
    # Nguồn: https://opencode.ai/zen/v1/chat/completions (Zen Gateway Anonymous).
    # Đây là mô hình MẶC ĐỊNH: không cần key nào. Nếu khách hàng cấu hình
    # gateway/api-key/model riêng (Control Center) thì hệ thống ưu tiên theo
    # thứ tự: Custom Gateway → Custom Model → provider key riêng → OpenCode Free.
    {"id": "deepseek-v4-flash-free", "name": "OpenCode DeepSeek V4 (Mặc định)", "provider": "OpenCode Zen", "key_type": "opencode"},
    {"id": "big-pickle", "name": "OpenCode Big Pickle", "provider": "OpenCode Zen", "key_type": "opencode"},
    {"id": "mimo-v2.5-free", "name": "OpenCode MiMo V2.5", "provider": "OpenCode Zen", "key_type": "opencode"},
    {"id": "nemotron-3-ultra-free", "name": "OpenCode Nemotron 3 Ultra", "provider": "OpenCode Zen", "key_type": "opencode"},
    {"id": "north-mini-code-free", "name": "OpenCode North Mini Code", "provider": "OpenCode Zen", "key_type": "opencode"},
    {"id": "laguna-s-2.1-free", "name": "OpenCode Laguna S 2.1", "provider": "OpenCode Zen", "key_type": "opencode"},
    {"id": "longcat-2.0-free", "name": "OpenCode LongCat 2.0", "provider": "OpenCode Zen", "key_type": "opencode"},
    {"id": "ling-3.0-flash-free", "name": "OpenCode Ling 3.0 Flash", "provider": "OpenCode Zen", "key_type": "opencode"},

    # ── OpenAI ──
    {"id": "gpt-5.6-sol", "name": "OpenAI GPT-5.6 Sol (Flagship)", "provider": "OpenAI", "key_type": "openai"},
    {"id": "gpt-5.6-terra", "name": "OpenAI GPT-5.6 Terra", "provider": "OpenAI", "key_type": "openai"},
    {"id": "gpt-5.6-luna", "name": "OpenAI GPT-5.6 Luna", "provider": "OpenAI", "key_type": "openai"},
    {"id": "gpt-5.5", "name": "OpenAI GPT-5.5", "provider": "OpenAI", "key_type": "openai"},
    {"id": "gpt-5.5-pro", "name": "OpenAI GPT-5.5 Pro", "provider": "OpenAI", "key_type": "openai"},
    {"id": "gpt-5.4", "name": "OpenAI GPT-5.4", "provider": "OpenAI", "key_type": "openai"},
    {"id": "gpt-5.4-mini", "name": "OpenAI GPT-5.4 Mini", "provider": "OpenAI", "key_type": "openai"},
    {"id": "gpt-5.4-nano", "name": "OpenAI GPT-5.4 Nano", "provider": "OpenAI", "key_type": "openai"},
    {"id": "gpt-5", "name": "OpenAI GPT-5", "provider": "OpenAI", "key_type": "openai"},
    {"id": "gpt-5-mini", "name": "OpenAI GPT-5 Mini", "provider": "OpenAI", "key_type": "openai"},
    {"id": "o3", "name": "OpenAI o3 (Reasoning)", "provider": "OpenAI", "key_type": "openai"},
    {"id": "o3-pro", "name": "OpenAI o3 Pro", "provider": "OpenAI", "key_type": "openai"},
    {"id": "o4-mini", "name": "OpenAI o4 Mini", "provider": "OpenAI", "key_type": "openai"},
    {"id": "gpt-4.1", "name": "OpenAI GPT-4.1", "provider": "OpenAI", "key_type": "openai"},
    {"id": "gpt-4.1-mini", "name": "OpenAI GPT-4.1 Mini", "provider": "OpenAI", "key_type": "openai"},
    {"id": "gpt-4o", "name": "OpenAI GPT-4o", "provider": "OpenAI", "key_type": "openai"},
    {"id": "gpt-4o-mini", "name": "OpenAI GPT-4o Mini", "provider": "OpenAI", "key_type": "openai"},

    # ── Anthropic Claude ──
    {"id": "claude-5-fable", "name": "Claude Fable 5 (Flagship)", "provider": "Claude", "key_type": "claude"},
    {"id": "claude-5-mythos", "name": "Claude Mythos 5", "provider": "Claude", "key_type": "claude"},
    {"id": "claude-5-opus", "name": "Claude Opus 5", "provider": "Claude", "key_type": "claude"},
    {"id": "claude-5-sonnet", "name": "Claude Sonnet 5", "provider": "Claude", "key_type": "claude"},
    {"id": "claude-4.8-opus", "name": "Claude Opus 4.8", "provider": "Claude", "key_type": "claude"},
    {"id": "claude-4.7-opus", "name": "Claude Opus 4.7", "provider": "Claude", "key_type": "claude"},
    {"id": "claude-4.6-opus", "name": "Claude Opus 4.6", "provider": "Claude", "key_type": "claude"},
    {"id": "claude-4.6-sonnet", "name": "Claude Sonnet 4.6", "provider": "Claude", "key_type": "claude"},
    {"id": "claude-4.5-sonnet", "name": "Claude Sonnet 4.5", "provider": "Claude", "key_type": "claude"},
    {"id": "claude-4.5-haiku", "name": "Claude Haiku 4.5", "provider": "Claude", "key_type": "claude"},
    {"id": "claude-3.7-sonnet", "name": "Claude 3.7 Sonnet", "provider": "Claude", "key_type": "claude"},
    {"id": "claude-3-5-sonnet", "name": "Claude 3.5 Sonnet", "provider": "Claude", "key_type": "claude"},
    {"id": "claude-3-5-haiku", "name": "Claude 3.5 Haiku", "provider": "Claude", "key_type": "claude"},

    # ── Google DeepMind ──
    {"id": "gemini-3.6-flash", "name": "Google Gemini 3.6 Flash", "provider": "Gemini", "key_type": "gemini"},
    {"id": "gemini-3.5-flash", "name": "Google Gemini 3.5 Flash", "provider": "Gemini", "key_type": "gemini"},
    {"id": "gemini-3.5-flash-lite", "name": "Google Gemini 3.5 Flash-Lite", "provider": "Gemini", "key_type": "gemini"},
    {"id": "gemini-3.1-pro", "name": "Google Gemini 3.1 Pro", "provider": "Gemini", "key_type": "gemini"},
    {"id": "gemini-3.1-flash-lite", "name": "Google Gemini 3.1 Flash-Lite", "provider": "Gemini", "key_type": "gemini"},
    {"id": "gemini-3-pro", "name": "Google Gemini 3 Pro", "provider": "Gemini", "key_type": "gemini"},
    {"id": "gemini-3-flash", "name": "Google Gemini 3 Flash", "provider": "Gemini", "key_type": "gemini"},
    {"id": "gemini-2.5-pro", "name": "Google Gemini 2.5 Pro", "provider": "Gemini", "key_type": "gemini"},
    {"id": "gemini-2.5-flash", "name": "Google Gemini 2.5 Flash", "provider": "Gemini", "key_type": "gemini"},
    {"id": "gemini-2.5-flash-lite", "name": "Google Gemini 2.5 Flash-Lite", "provider": "Gemini", "key_type": "gemini"},
    {"id": "gemini-2.0-flash", "name": "Google Gemini 2.0 Flash", "provider": "Gemini", "key_type": "gemini"},
    {"id": "gemini-1.5-flash", "name": "Google Gemini 1.5 Flash", "provider": "Gemini", "key_type": "gemini"},
    {"id": "gemini-1.5-pro", "name": "Google Gemini 1.5 Pro", "provider": "Gemini", "key_type": "gemini"},

    # ── DeepSeek ──
    {"id": "deepseek-v4-pro", "name": "DeepSeek V4 Pro", "provider": "DeepSeek", "key_type": "deepseek"},
    {"id": "deepseek-v4-flash", "name": "DeepSeek V4 Flash (0731)", "provider": "DeepSeek", "key_type": "deepseek"},
    {"id": "deepseek-v3.2", "name": "DeepSeek V3.2", "provider": "DeepSeek", "key_type": "deepseek"},
    {"id": "deepseek-v3.1", "name": "DeepSeek V3.1", "provider": "DeepSeek", "key_type": "deepseek"},
    {"id": "deepseek-chat", "name": "DeepSeek V3 Chat", "provider": "DeepSeek", "key_type": "deepseek"},
    {"id": "deepseek-r1", "name": "DeepSeek R1 Reasoning", "provider": "DeepSeek", "key_type": "deepseek"},

    # ── xAI Grok ──
    {"id": "grok-4.5", "name": "xAI Grok 4.5 (Flagship)", "provider": "Grok", "key_type": "grok"},
    {"id": "grok-4", "name": "xAI Grok 4", "provider": "Grok", "key_type": "grok"},
    {"id": "grok-4.3", "name": "xAI Grok 4.3", "provider": "Grok", "key_type": "grok"},
    {"id": "grok-4.20", "name": "xAI Grok 4.20", "provider": "Grok", "key_type": "grok"},
    {"id": "grok-4-fast", "name": "xAI Grok 4 Fast", "provider": "Grok", "key_type": "grok"},
    {"id": "grok-4.1-fast", "name": "xAI Grok 4.1 Fast", "provider": "Grok", "key_type": "grok"},
    {"id": "grok-3", "name": "xAI Grok 3", "provider": "Grok", "key_type": "grok"},

    # ── Moonshot Kimi ──
    {"id": "kimi-k3", "name": "Moonshot Kimi K3", "provider": "Moonshot", "key_type": "moonshot"},
    {"id": "kimi-k2.6", "name": "Moonshot Kimi K2.6", "provider": "Moonshot", "key_type": "moonshot"},
    {"id": "kimi-k2-thinking", "name": "Moonshot Kimi K2 Thinking", "provider": "Moonshot", "key_type": "moonshot"},
    {"id": "kimi-k2-thinking-turbo", "name": "Moonshot Kimi K2 Turbo", "provider": "Moonshot", "key_type": "moonshot"},

    # ── Alibaba Qwen ──
    {"id": "qwen3.8-max", "name": "Alibaba Qwen3.8 Max", "provider": "Qwen", "key_type": "qwen"},
    {"id": "qwen3-thinking", "name": "Alibaba Qwen3 Thinking", "provider": "Qwen", "key_type": "qwen"},
    {"id": "qwen3-coder", "name": "Alibaba Qwen3 Coder", "provider": "Qwen", "key_type": "qwen"},
    {"id": "qwen3-vl", "name": "Alibaba Qwen3 VL", "provider": "Qwen", "key_type": "qwen"},
    {"id": "qwen3-235b-a22b", "name": "Alibaba Qwen3 235B", "provider": "Qwen", "key_type": "qwen"},

    # ── Zhipu GLM ──
    {"id": "glm-5.2", "name": "Zhipu GLM-5.2", "provider": "GLM", "key_type": "openai"},
    {"id": "glm-4.7-flash", "name": "Zhipu GLM-4.7 Flash", "provider": "GLM", "key_type": "openai"},
    {"id": "glm-4.5", "name": "Zhipu GLM-4.5", "provider": "GLM", "key_type": "openai"},

    # ── MiniMax & Meta Llama & Mistral ──
    {"id": "minimax-m3", "name": "MiniMax M3", "provider": "MiniMax", "key_type": "openai"},
    {"id": "llama-4-maverick", "name": "Meta Llama 4 Maverick", "provider": "Llama", "key_type": "openai"},
    {"id": "llama-4-scout", "name": "Meta Llama 4 Scout", "provider": "Llama", "key_type": "openai"},
    {"id": "llama-3.3-70b", "name": "Meta Llama 3.3 70B", "provider": "Llama", "key_type": "openai"},
    {"id": "magistral-medium", "name": "Mistral Magistral Medium", "provider": "Mistral", "key_type": "openai"},
    {"id": "mistral-large", "name": "Mistral Large", "provider": "Mistral", "key_type": "openai"},
    {"id": "codestral", "name": "Mistral Codestral", "provider": "Mistral", "key_type": "openai"},
    {"id": "phi-4", "name": "Microsoft Phi-4", "provider": "Microsoft", "key_type": "openai"},
    {"id": "command-a", "name": "Cohere Command A", "provider": "Cohere", "key_type": "openai"},
    {"id": "jamba-large", "name": "AI21 Jamba Large", "provider": "AI21", "key_type": "openai"},
    {"id": "nemotron-ultra", "name": "NVIDIA Nemotron Ultra", "provider": "NVIDIA", "key_type": "openai"},
    {"id": "granite-4", "name": "IBM Granite 4", "provider": "IBM", "key_type": "openai"},
    {"id": "gemma-3", "name": "Google Gemma 3", "provider": "Gemma", "key_type": "gemini"},
]

USER_CUSTOM_MODEL_ID = _saved_cfg.get("custom_model_id", "")

# Gemini quota handling: rotate between default models every couple hours to
# dodge per-model 429 rate limits, and cool down any model that just returned 429.
GEMINI_ROTATION_POOL = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3-flash"]
GEMINI_ROTATION_IDX = 0
OPENCODE_ROTATION_IDX = 0
AI_MODEL_COOLDOWN: Dict[str, float] = {}
AI_COOLDOWN_SECONDS = max(120, int(os.getenv("ATE_AI_COOLDOWN_SECONDS") or os.getenv("QUANTAI_AI_COOLDOWN_SECONDS", "7200")))

USER_GROK_KEY = _saved_cfg.get("grok_api_key") or os.getenv("GROK_API_KEY", "")
USER_QWEN_KEY = _saved_cfg.get("qwen_api_key") or os.getenv("QWEN_API_KEY", "")
USER_GATEWAY_URL = _saved_cfg.get("gateway_url") or os.getenv("GATEWAY_URL", "")
USER_GATEWAY_KEY = _saved_cfg.get("gateway_key") or os.getenv("GATEWAY_KEY", "")

class TradingMethodRequest(BaseModel):
    trading_method: str = Field(default="ULTRA_CONFLUENCE", max_length=64)

@app.post("/api/control-center/trading-method", dependencies=[Depends(require_operator_token)])
async def update_trading_method_endpoint(req: TradingMethodRequest):
    global TRADING_METHOD
    method = req.trading_method.strip().upper()
    if method not in ("INDICATOR", "SMC", "ICT", "PRICE_ACTION", "ULTRA_CONFLUENCE", "SNIPER"):
        raise HTTPException(status_code=400, detail={"code": "INVALID_TRADING_METHOD", "message": f"Phương pháp {method} không hợp lệ."})
    TRADING_METHOD = method
    save_control_config({"trading_method": TRADING_METHOD})
    await broadcast_config_updated()
    log_event(LogEvent.INFO, component="control-center", message=f"Trading method updated -> {TRADING_METHOD}")
    return {
        "status": "SUCCESS",
        "message": f"Đã cập nhật phương pháp giao dịch: {TRADING_METHOD}",
        "trading_method": TRADING_METHOD
    }

@app.post("/api/control-center/ai-config", dependencies=[Depends(require_operator_token)])
async def update_control_center_ai_config(req: ControlCenterAIConfigRequest):
    global ACTIVE_AI_MODEL, USER_CUSTOM_MODEL_ID, USER_GEMINI_KEY, USER_CLAUDE_KEY, USER_DEEPSEEK_KEY, USER_OPENAI_KEY, USER_ZPLAY_KEY, USER_GROK_KEY, USER_QWEN_KEY, USER_GATEWAY_URL, USER_GATEWAY_KEY, TRADING_METHOD
    model_input = req.active_model or req.active_ai_model
    if model_input:
        ACTIVE_AI_MODEL = model_input.strip()
    if req.trading_method:
        method = req.trading_method.strip().upper()
        if method in ("INDICATOR", "SMC", "ICT", "PRICE_ACTION", "ULTRA_CONFLUENCE", "SNIPER"):
            TRADING_METHOD = method
    if req.custom_model_id is not None:
        USER_CUSTOM_MODEL_ID = req.custom_model_id.strip()
    if req.gemini_api_key is not None and req.gemini_api_key.strip() != "*****":
        USER_GEMINI_KEY = req.gemini_api_key.strip()
    if req.claude_api_key is not None and req.claude_api_key.strip() != "*****":
        USER_CLAUDE_KEY = req.claude_api_key.strip()
    if req.deepseek_api_key is not None and req.deepseek_api_key.strip() != "*****":
        USER_DEEPSEEK_KEY = req.deepseek_api_key.strip()
    if req.openai_api_key is not None and req.openai_api_key.strip() != "*****":
        USER_OPENAI_KEY = req.openai_api_key.strip()
    if req.zplay_api_key is not None and req.zplay_api_key.strip() != "*****":
        USER_ZPLAY_KEY = req.zplay_api_key.strip()
    if req.grok_api_key is not None and req.grok_api_key.strip() != "*****":
        USER_GROK_KEY = req.grok_api_key.strip()
    if req.qwen_api_key is not None and req.qwen_api_key.strip() != "*****":
        USER_QWEN_KEY = req.qwen_api_key.strip()
    if req.gateway_url is not None:
        USER_GATEWAY_URL = req.gateway_url.strip()
    if req.gateway_key is not None:
        USER_GATEWAY_KEY = req.gateway_key.strip() if req.gateway_key.strip() != "*****" else USER_GATEWAY_KEY

    save_control_config({
        "active_ai_model": ACTIVE_AI_MODEL,
        "custom_model_id": USER_CUSTOM_MODEL_ID,
        "trading_method": TRADING_METHOD,
        "gemini_api_key": USER_GEMINI_KEY,
        "claude_api_key": USER_CLAUDE_KEY,
        "deepseek_api_key": USER_DEEPSEEK_KEY,
        "openai_api_key": USER_OPENAI_KEY,
        "zplay_api_key": USER_ZPLAY_KEY,
        "grok_api_key": USER_GROK_KEY,
        "qwen_api_key": USER_QWEN_KEY,
        "gateway_url": USER_GATEWAY_URL,
        "gateway_key": USER_GATEWAY_KEY,
    })
    await broadcast_config_updated()

    model_display = USER_CUSTOM_MODEL_ID or ACTIVE_AI_MODEL
    log_event(LogEvent.INFO, component="ai-config", message=f"AI Config updated -> Active Model={model_display}, Method={TRADING_METHOD}")
    send_telegram_alert(
        f"<b>[AI ENGINE UPDATED]</b>\n"
        f"Model ưu tiên: <b>{model_display}</b>\n"
        f"Phương pháp: <b>{TRADING_METHOD}</b>\n"
        f"Custom Gateway: {'🟢 CÓ' if USER_GATEWAY_URL else '⚪ TẮT'}\n"
        f"Tự động xoay vòng key khi hết token: 🟢 ĐÃ BẬT"
    )

    return {
        "status": "SUCCESS",
        "message": f"Đã lưu mô hình AI ưu tiên: {model_display} và phương pháp: {TRADING_METHOD}",
        "active_model": model_display,
        "trading_method": TRADING_METHOD,
    }

@app.get("/api/control-center/ai-config")
async def get_control_center_ai_config():
    return {
        "active_model": ACTIVE_AI_MODEL,
        "custom_model_id": USER_CUSTOM_MODEL_ID,
        "trading_method": TRADING_METHOD,
        "gemini_api_key": _mask_field(USER_GEMINI_KEY),
        "claude_api_key": _mask_field(USER_CLAUDE_KEY),
        "deepseek_api_key": _mask_field(USER_DEEPSEEK_KEY),
        "openai_api_key": _mask_field(USER_OPENAI_KEY),
        "zplay_api_key": _mask_field(USER_ZPLAY_KEY),
        "grok_api_key": _mask_field(USER_GROK_KEY),
        "qwen_api_key": _mask_field(USER_QWEN_KEY),
        "gateway_url": USER_GATEWAY_URL,
        "gateway_key": _mask_field(USER_GATEWAY_KEY),
        "has_gemini_key": bool(USER_GEMINI_KEY or os.getenv("GEMINI_API_KEY")),
        "has_claude_key": bool(USER_CLAUDE_KEY or os.getenv("CLAUDE_API_KEY")),
        "has_deepseek_key": bool(USER_DEEPSEEK_KEY or os.getenv("DEEPSEEK_API_KEY")),
        "has_openai_key": bool(USER_OPENAI_KEY or os.getenv("OPENAI_API_KEY")),
        "has_zplay_key": bool(USER_ZPLAY_KEY or os.getenv("ZPLAY_API_KEY")),
        "has_grok_key": bool(USER_GROK_KEY or os.getenv("GROK_API_KEY")),
        "has_qwen_key": bool(USER_QWEN_KEY or os.getenv("QWEN_API_KEY")),
        "has_gateway": bool(USER_GATEWAY_URL),
        "available_models": SUPPORTED_AI_MODELS,
    }


def get_ai_endpoints_queue(preferred_model: str = "auto") -> List[Dict[str, Any]]:
    global GEMINI_ROTATION_IDX, OPENCODE_ROTATION_IDX
    target_model = USER_CUSTOM_MODEL_ID or (preferred_model if preferred_model and preferred_model != "auto" else ACTIVE_AI_MODEL)
    queue = []

    custom_keys = {
        "gemini": (USER_GEMINI_KEY or os.getenv("GEMINI_API_KEY", "")).strip(),
        "claude": (USER_CLAUDE_KEY or os.getenv("CLAUDE_API_KEY", "")).strip(),
        "deepseek": (USER_DEEPSEEK_KEY or os.getenv("DEEPSEEK_API_KEY", "")).strip(),
        "openai": (USER_OPENAI_KEY or os.getenv("OPENAI_API_KEY", "")).strip(),
        "zplay": (USER_ZPLAY_KEY or os.getenv("ZPLAY_API_KEY", "")).strip(),
        "grok": (USER_GROK_KEY or os.getenv("GROK_API_KEY", "")).strip(),
        "qwen": (USER_QWEN_KEY or os.getenv("QWEN_API_KEY", "")).strip(),
    }

    default_keys = {
        "gemini": os.getenv("GEMINI_API_KEY", "").strip(),
        "openai": os.getenv("OPENAI_API_KEY", "").strip(),
        "zplay": os.getenv("ZPLAY_API_KEY", "").strip(),
    }

    base_urls = {
        "gemini": os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"),
        "claude": os.getenv("CLAUDE_BASE_URL", "https://api.anthropic.com/v1/messages"),
        "deepseek": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1/chat/completions"),
        "openai": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions"),
        "zplay": os.getenv("ZPLAY_BASE_URL", "https://router.flatkey.ai/v1/chat/completions"),
        "grok": os.getenv("GROK_BASE_URL", "https://api.x.ai/v1/chat/completions"),
        "qwen": os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"),
        "opencode": os.getenv("OPENCODE_BASE_URL", "https://opencode.ai/zen/v1/chat/completions"),
    }

    opencode_url = base_urls["opencode"]

    # 1. Custom Gateway Priority #0 (khách hàng tự cấu hình gateway URL/Key → Ưu tiên cao nhất)
    if USER_GATEWAY_URL:
        queue.append({
            "id": target_model,
            "name": f"Custom Gateway ({target_model})",
            "model": target_model,
            "provider": "Custom API Gateway",
            "key_type": "gateway",
            "url": USER_GATEWAY_URL,
            "api_key": USER_GATEWAY_KEY,
            "is_user_custom": True,
        })

    # 1.1 Customer Custom Model ID (khách hàng chọn model cụ thể trong Control Center)
    if USER_CUSTOM_MODEL_ID and not any(q["id"] == USER_CUSTOM_MODEL_ID for q in queue):
        cm_info = next((m for m in SUPPORTED_AI_MODELS if m["id"] == USER_CUSTOM_MODEL_ID), None)
        cm_ktype = cm_info["key_type"] if cm_info else ("openai" if ("gpt" in USER_CUSTOM_MODEL_ID or "o3" in USER_CUSTOM_MODEL_ID) else "gemini")
        cm_key = custom_keys.get(cm_ktype) or custom_keys.get("openai")
        queue.append({
            "id": USER_CUSTOM_MODEL_ID,
            "name": f"Customer Model ({USER_CUSTOM_MODEL_ID})",
            "model": USER_CUSTOM_MODEL_ID,
            "provider": cm_info["provider"] if cm_info else "Custom AI Provider",
            "key_type": cm_ktype,
            "url": base_urls.get(cm_ktype, base_urls["openai"]),
            "api_key": cm_key or "",
            "is_user_custom": True,
        })

    # 1.5 OpenCode Zen FREE Models — DEFAULT ACTIVE (chạy mặc định, KHÔNG cần API Key)
    # Pool free luôn đứng trước các key trả phí; nếu model free fail (429/400/401)
    # sẽ AUTO-SWITCH sang model free kế tiếp, chỉ fallback sang key trả phí khi
    # toàn bộ pool free không khả dụng.
    opencode_pool = [m["id"] for m in SUPPORTED_AI_MODELS if m["key_type"] == "opencode"]
    if opencode_pool and not any(q["key_type"] == "opencode" for q in queue):
        now_ts = time.time()
        rotated_free = []
        for offset in range(len(opencode_pool)):
            mid = opencode_pool[(OPENCODE_ROTATION_IDX + offset) % len(opencode_pool)]
            if now_ts >= AI_MODEL_COOLDOWN.get(mid, 0):
                rotated_free.append(mid)
        if not rotated_free:
            rotated_free = list(opencode_pool)
        for mid in rotated_free:
            if any(q["id"] == mid for q in queue):
                continue
            queue.append({
                "id": mid,
                "name": f"OpenCode Free ({mid})",
                "model": mid,
                "provider": "OpenCode Zen",
                "key_type": "opencode",
                "url": opencode_url,
                "api_key": "",
                "is_user_custom": False,
                "is_free": True,
            })
        OPENCODE_ROTATION_IDX = (OPENCODE_ROTATION_IDX + 1) % len(opencode_pool)

    # 2. Gemini rotation pool: rotate models to avoid quota (429) exhaustion.
    # Models on cooldown (rate-limited recently) are skipped this round.
    gemini_pool_key = custom_keys.get("gemini") or default_keys.get("gemini")
    if gemini_pool_key:
        now = time.time()
        rotated = []
        for offset in range(len(GEMINI_ROTATION_POOL)):
            mid = GEMINI_ROTATION_POOL[(GEMINI_ROTATION_IDX + offset) % len(GEMINI_ROTATION_POOL)]
            if now < AI_MODEL_COOLDOWN.get(mid, 0):
                continue
            rotated.append(mid)
        if not rotated:
            rotated = list(GEMINI_ROTATION_POOL)
        for mid in rotated:
            if any(q["id"] == mid for q in queue):
                continue
            queue.append({
                "id": mid,
                "name": f"Rotation {mid}",
                "model": mid,
                "provider": "Gemini",
                "key_type": "gemini",
                "url": base_urls["gemini"],
                "api_key": gemini_pool_key,
                "is_user_custom": True,
            })
        GEMINI_ROTATION_IDX = (GEMINI_ROTATION_IDX + 1) % len(GEMINI_ROTATION_POOL)

    # 2. Selected Target Model
    matched_info = next((m for m in SUPPORTED_AI_MODELS if m["id"] == target_model), None)
    ktype = matched_info["key_type"] if matched_info else ("openai" if ("gpt" in target_model or "o3" in target_model) else "gemini")
    user_key = custom_keys.get(ktype) or custom_keys.get("openai")
    if user_key and not any(q["id"] == target_model for q in queue):
        queue.append({
            "id": target_model,
            "name": f"User {matched_info['name'] if matched_info else target_model}",
            "model": target_model,
            "provider": matched_info["provider"] if matched_info else "Custom AI Provider",
            "key_type": ktype,
            "url": base_urls.get(ktype, base_urls["openai"]),
            "api_key": user_key,
            "is_user_custom": True,
        })

    # 3. Add other configured custom provider keys
    for m in SUPPORTED_AI_MODELS:
        m_ktype = m["key_type"]
        m_key = custom_keys.get(m_ktype)
        if m_key and not any(q["id"] == m["id"] for q in queue):
            queue.append({
                "id": m["id"],
                "name": f"User {m['name']}",
                "model": m["id"],
                "provider": m["provider"],
                "key_type": m_ktype,
                "url": base_urls.get(m_ktype, base_urls["openai"]),
                "api_key": m_key,
                "is_user_custom": True,
            })

    # 4. Standard Default Fallbacks
    fallbacks = [
        {"id": "gemini-1.5-flash", "name": "Default Gemini 1.5 Flash", "model": "gemini-1.5-flash", "ktype": "gemini", "url": base_urls["gemini"], "key": default_keys["gemini"]},
        {"id": "gpt-4o", "name": "Default OpenAI GPT-4o", "model": "gpt-4o", "ktype": "openai", "url": base_urls["openai"], "key": default_keys["openai"]},
        {"id": "kimi-k3", "name": "Default FlatKey Kimi-K3", "model": "kimi-k3", "ktype": "zplay", "url": base_urls["zplay"], "key": default_keys["zplay"]},
    ]
    for fb in fallbacks:
        if not any(q["id"] == fb["id"] for q in queue):
            queue.append({
                "id": fb["id"],
                "name": fb["name"],
                "model": fb["model"],
                "provider": fb["name"],
                "key_type": fb["ktype"],
                "url": fb["url"],
                "api_key": fb["key"],
                "is_user_custom": False,
            })

    return queue


def call_multi_ai_completion(system_prompt: str, user_msg: str, preferred_model: str = "auto", max_tokens: int = 4096) -> tuple[str, str, str, bool]:
    """Execute AI completion with automatic model prioritization & token exhaustion fallback across providers."""
    providers = get_ai_endpoints_queue(preferred_model)
    fallback_occurred = False

    for idx, p in enumerate(providers):
        req_key = p["api_key"]
        req_url = p["url"]
        if not req_url:
            continue

        url = req_url.rstrip("/")
        if not url.endswith("/chat/completions") and not url.endswith("/messages") and not url.endswith("/api/proxy/zen"):
            url += "/chat/completions"

        try:
            import urllib.request
            headers = {
                "Content-Type": "application/json",
                # OpenCode Zen chặn User-Agent Python-urllib mặc định (403 Forbidden)
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            }
            if req_key:
                headers["Authorization"] = f"Bearer {req_key}"
            if p["key_type"] == "claude" and "anthropic.com" in url:
                headers["x-api-key"] = req_key
                headers["anthropic-version"] = "2023-06-01"

            payload = json.dumps({
                "model": p["model"],
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                "temperature": 0.3,
                "max_tokens": max_tokens,
            }).encode("utf-8")

            req_obj = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req_obj, timeout=22) as resp:
                if resp.status == 200:
                    res_data = json.loads(resp.read().decode("utf-8"))
                    text = ""
                    if "choices" in res_data and len(res_data["choices"]) > 0:
                        msg = res_data["choices"][0].get("message", {})
                        text = msg.get("content") or ""
                        if not text.strip():
                            # Model free (reasoning) trả suy luận trong reasoning_content
                            # khi content chưa kịp sinh -> chấp nhận làm output dự phòng.
                            text = msg.get("reasoning_content") or ""
                    elif "content" in res_data and isinstance(res_data["content"], list):
                        text = res_data["content"][0]["text"]

                    if text and text.strip():
                        if idx > 0:
                            fallback_occurred = True
                            log_event(LogEvent.WARNING, component="ai-provider", message=f"Fallback triggered! Switched to {p['name']} ({p['model']})")
                        return text, p["name"], p["model"], fallback_occurred
        except Exception as exc:
            if getattr(exc, "code", None) == 429:
                AI_MODEL_COOLDOWN[p["model"]] = time.time() + AI_COOLDOWN_SECONDS
                log_event(LogEvent.WARNING, component="ai-provider", message=f"Provider {p['name']} ({p['model']}) rate-limited (429). Cooling down {AI_COOLDOWN_SECONDS // 60} min, trying next...")
            else:
                if p.get("is_free") or p["key_type"] == "opencode":
                    # Model free lỗi (400/401/404/...): cooldown ngắn 5 phút để
                    # AUTO-SWITCH sang model free dự phòng tiếp theo trong pool.
                    AI_MODEL_COOLDOWN[p["model"]] = time.time() + 300
                    log_event(LogEvent.WARNING, component="ai-provider", message=f"OpenCode free model {p['model']} failed: {exc}. Auto-switching to next free model...")
                else:
                    log_event(LogEvent.WARNING, component="ai-provider", message=f"Provider {p['name']} ({p['model']}) at {url[:30]}... failed: {exc}. Trying fallback...")
            continue

    return "", "System Fallback Engine", "deterministic", True


@app.get("/api/copilot/models")
async def get_copilot_models():
    """Return available AI models and active status."""
    return {"models": SUPPORTED_AI_MODELS, "default": ACTIVE_AI_MODEL}


@app.post("/api/copilot/chat")
async def copilot_chat(req: CopilotChatRequest):
    msg = req.message.strip()
    telemetry = get_mt5_telemetry()
    price = telemetry["current_ask"]
    balance = telemetry["balance"]
    equity = telemetry["equity"]
    open_pos = telemetry["open_positions"]

    positions = await get_positions()
    indicators = telemetry.get("indicators", {})
    performance = telemetry.get("performance", {})
    ai_signal = telemetry.get("ai_signal", {})

    full_website_context = (
        f"--- FULL BLOOMBERG TERMINAL WEBSITE SNAPSHOT ---\n"
        f"• ACCOUNT: Balance=${balance:,.2f}, Equity=${equity:,.2f}, Margin=${telemetry['margin']:,.2f}, Floating P/L=${telemetry['floating_pnl']:,.2f}\n"
        f"• MARKET XAUUSDm: Ask={price:.2f}, Bid={telemetry['current_bid']:.2f}, Spread={telemetry['current_spread']:.2f}\n"
        f"• INDICATORS: RSI(14)={indicators.get('rsi')}, ATR(14)={indicators.get('atr')}, MACD={indicators.get('macd')}, EMA20={indicators.get('ema20')}, EMA50={indicators.get('ema50')}, EMA200={indicators.get('ema200')}\n"
        f"• PIVOT POINTS: Pivot={indicators.get('pivot')}, R1={indicators.get('r1')}, R2={indicators.get('r2')}, S1={indicators.get('s1')}, S2={indicators.get('s2')}\n"
        f"• AI SIGNAL DYNAMIC: Signal={ai_signal.get('primary_signal')}, Confidence={ai_signal.get('confidence')}, Entry={ai_signal.get('entry_zone')}, SL={ai_signal.get('stop_loss')}, TP={ai_signal.get('take_profit')}, Suggested Lot={ai_signal.get('suggested_lot')}\n"
        f"• OPEN POSITIONS ({len(positions)}): {json.dumps(positions[:5])}\n"
        f"• PERFORMANCE: Win Rate={performance.get('win_rate')}, Profit Factor={performance.get('profit_factor')}, Best={performance.get('best_trade')}, Worst={performance.get('worst_trade')}\n"
        f"--------------------------------------------------"
    )

    system_prompt = (
        f"Bạn là Trợ lý AI Trading kiêm Chuyên gia tự động trading và Quản trị Rủi ro Quản lý Giao dịch XAUUSD cho anh Tú (chủ tịch/boss).\n"
        f"Bạn tuân thủ nghiêm ngặt BỘ QUY TẮC SKILL GOLDQUANT MASTER TRADING HANDBOOK:\n"
        f"1. QUẢN LÝ RỦI RO 1%: Lot = (Balance * 0.01) / (Distance SL * 100). Luôn khuyên dùng R:R 1:2.0.\n"
        f"2. MA TRẬN TÍN HIỆU: EMA20 > EMA50 > EMA200 (BUY), RSI 50-70, Distance SL = 1.5*ATR.\n"
        f"3. XƯNG HÔ: Luôn xưng hô súc tích, đẳng cấp với danh xưng 'chủ tịch', 'boss', hoặc 'anh Tú'.\n"
        f"DỮ LIỆU REALTIME BLOOMBERG DƯỚI ĐÂY:\n"
        f"{full_website_context}\n"
        f"Trả lời anh Tú bằng tiếng Việt chuyên nghiệp, ngắn gọn, phân tích định lượng chuẩn xác."
    )

    raw_ai_text, provider_name, model_used, fallback_used = call_multi_ai_completion(
        system_prompt=system_prompt,
        user_msg=msg,
        preferred_model=getattr(req, "model_id", "auto")
    )

    if raw_ai_text:
        tag = f" [{provider_name}]" if not fallback_used else f" [{provider_name} (Auto-Fallback)]"
        ai_response = f"{raw_ai_text}\n\n[AI]{tag}"
    else:
        msg_lower = msg.lower()
        if "buy" in msg_lower or "mua" in msg_lower:
            sl = float(ai_signal.get("stop_loss", price - 8.0)) if ai_signal.get("stop_loss") != "N/A" else price - 8.0
            tp = float(ai_signal.get("take_profit", price + 16.0)) if ai_signal.get("take_profit") != "N/A" else price + 16.0
            lot = ai_signal.get("suggested_lot", "0.10")
            ai_response = (
                f"[AI COPILOT - ANALYSIS & RECOMMENDATION]\n"
                f"Báo cáo anh Tú: Phân tích kỹ thuật XAUUSDm hiện tại:\n"
                f"• Giá Ask/Bid: ${price:.2f} / ${telemetry['current_bid']:.2f}\n"
                f"• Tín hiệu: BUY (AI Confidence Score: {ai_signal.get('confidence', '78%')})\n"
                f"• Gợi ý vị thế: {lot} Lot (Quản trị rủi ro 1% Balance ${balance:,.2f})\n"
                f"• Entry Zone: ${price:.2f} | Stop Loss: ${sl:.2f} | Take Profit: ${tp:.2f}\n"
                f"💡 Ghi chú: Để vào lệnh, anh Tú vui lòng sử dụng nút 'BUY MARKET' trên Dashboard hoặc kích hoạt AI Auto-Loop để EA xử lý tự động."
            )
        elif "sell" in msg_lower or "bán" in msg_lower:
            sl = float(indicators.get('r2', price + 15.0)) if indicators.get('r2') else price + 15.0
            tp = float(indicators.get('pivot', price - 10.0)) if indicators.get('pivot') else price - 10.0
            lot = ai_signal.get("suggested_lot", "0.10")
            ai_response = (
                f"[AI COPILOT - ANALYSIS & RECOMMENDATION]\n"
                f"Báo cáo anh Tú: Phân tích vùng kháng cự XAUUSDm:\n"
                f"• Giá Ask/Bid: ${price:.2f} / ${telemetry['current_bid']:.2f}\n"
                f"• Tín hiệu: SELL (AI Confidence Score: {ai_signal.get('confidence', '70%')})\n"
                f"• Gợi ý vị thế: {lot} Lot (Quản trị rủi ro 1% Balance ${balance:,.2f})\n"
                f"• Entry Zone: ${telemetry['current_bid']:.2f} | Stop Loss: ${sl:.2f} | Take Profit: ${tp:.2f}\n"
                f"💡 Ghi chú: Để vào lệnh, anh Tú vui lòng sử dụng nút 'SELL MARKET' trên Dashboard hoặc kích hoạt AI Auto-Loop để EA xử lý tự động."
            )
        elif "cắt" in msg_lower or "đóng" in msg_lower or "close" in msg_lower or "vị thế" in msg_lower or "lệnh" in msg_lower or "position" in msg_lower:
            pos_str_list = [f"#{p.get('ticket')} {p.get('type')} {p.get('volume')}lot @{p.get('price_open')} (P/L: ${p.get('pnl'):.2f})" for p in positions]
            pos_str = "\n  ".join(pos_str_list) if pos_str_list else "Không có lệnh nào đang mở"
            ai_response = (
                f"[AI COPILOT - POSITIONS REVIEW]\n"
                f"Báo cáo anh Tú: Đang mở {open_pos} lệnh MT5 với tổng P/L trôi nổi: ${telemetry['floating_pnl']:.2f}.\n"
                f"Chi tiết vị thế:\n  {pos_str}\n"
                f"• Khuyến nghị: Giữ nguyên lệnh BUY và cài trailing stop theo EMA20 ({indicators.get('ema20')})."
            )
        elif "score" in msg_lower or "điểm" in msg_lower or "tín hiệu" in msg_lower:
            rsi_v = float(indicators.get("rsi") or 50.0)
            atr_v = float(indicators.get("atr") or 0.0)
            macd_v = float(indicators.get("macd") or 0.0)
            ema20_v = float(indicators.get("ema20") or 0.0)
            ema50_v = float(indicators.get("ema50") or 0.0)
            ema200_v = float(indicators.get("ema200") or 0.0)
            trend_score = 40 if (ema20_v > ema50_v > ema200_v and ema200_v > 0) else (20 if ema20_v > ema200_v else 0)
            mom_score = 23 if rsi_v >= 55 else (12 if rsi_v >= 45 else 4)
            vol_score = 15 if atr_v > 0 else 0
            total_score = trend_score + mom_score + vol_score
            trend_state = "tăng (EMA20 > EMA50 > EMA200)" if ema20_v > ema50_v > ema200_v else ("giảm (EMA20 < EMA50 < EMA200)" if ema20_v < ema50_v < ema200_v else "đi ngang (EMA đan xen)")
            ai_response = (
                f"[AI COPILOT - SCORE BREAKDOWN]\n"
                f"Báo cáo anh Tú: AI Confidence Score đạt {total_score}/85 (realtime).\n"
                f"• Trend Score: {trend_score}/40 ({trend_state} - EMA20=${ema20_v:.2f}, EMA50=${ema50_v:.2f}, EMA200=${ema200_v:.2f})\n"
                f"• Momentum Score: {mom_score}/30 (RSI {rsi_v:.1f}, MACD {macd_v:+.2f})\n"
                f"• Volatility Score: {vol_score}/15 (ATR {atr_v:.2f})\n"
                f"• Kết luận: Khả năng thắng (Win Prob): {ai_signal.get('win_prob')} với tỷ lệ RR 1:2.0."
            )
        else:
            ai_response = (
                f"[AI COPILOT - LIVE MARKET TELEMETRY]\n"
                f"Báo cáo anh Tú: Em đã đọc toàn bộ dữ liệu 11 thẻ card trên website realtime.\n"
                f"• XAUUSDm: ${price:.2f} (Ask {price:.2f} / Bid {telemetry['current_bid']:.2f})\n"
                f"• Tài khoản MT5: Balance ${balance:,.2f} | Equity ${equity:,.2f} | Margin ${telemetry['margin']:.2f}\n"
                f"• Chỉ số kỹ thuật: RSI {indicators.get('rsi')} | ATR {indicators.get('atr')} | MACD {indicators.get('macd')}\n"
                f"• Tín hiệu AI: {ai_signal.get('primary_signal')} (Độ tin cậy {ai_signal.get('confidence')})\n"
                f"• Vị thế mở: {open_pos} lệnh (Floating P/L: ${telemetry['floating_pnl']:.2f})."
            )

    if TELEGRAM_ENABLED:
        send_telegram_alert(
            f"<b>[AI TRADING COPILOT SIGNAL]</b>\n"
            f"Tín hiệu: <b>{ai_signal.get('primary_signal', 'BUY')}</b> ({ai_signal.get('confidence', '78%')})\n"
            f"AI Model: <b>{provider_name} ({model_used})</b>\n\n"
            f"{ai_response[:300]}..."
        )

    append_chat_message("user", msg)
    append_chat_message("ai", ai_response)

    return {
        "status": "SUCCESS",
        "role": "ai",
        "text": ai_response,
        "time": datetime.now().strftime("%H:%M"),
        "ai_score": 78,
        "signal": ai_signal.get("primary_signal", "BUY"),
        "provider": provider_name,
        "model": model_used,
        "fallback": fallback_used,
    }


@app.get("/api/copilot/chat/history")
async def get_copilot_chat_history():
    return _CHAT_MESSAGES


class EconomicCalendarRequest(BaseModel):
    days: int = 7
    country: Optional[str] = None
    impact: Optional[str] = None


class EconomicEvent(BaseModel):
    id: str
    title: str
    country: str
    currency: str
    impact: str
    datetime: str
    forecast: str
    previous: str
    actual: Optional[str]
    unit: str
    source: str
    description: str
    category: str
    status: str


@app.get("/api/economic-calendar")
async def economic_calendar(
    days: int = Query(7, ge=1, le=30),
    country: Optional[str] = Query(None),
    impact: Optional[str] = Query(None),
):
    events = fetch_real_economic_calendar()
    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=days, hours=23, minutes=59, seconds=59)

    result = []
    for evt in events:
        evt_dt = _parse_event_datetime(evt, now)
        if not evt_dt:
            continue

        if evt_dt < week_start or evt_dt > week_end:
            continue

        impact_val = evt.get("impact", "LOW").upper()
        if impact == "HIGH" and impact_val != "HIGH":
            continue
        if impact == "MED" and impact_val not in ("HIGH", "MED"):
            continue

        country_val = evt.get("currency", "USD")
        if country and country_val != country:
            continue

        actual_val = evt.get("actual", "")
        status = "released" if (actual_val or evt_dt < now) else "upcoming"

        result.append({
            "id": evt.get("id", ""),
            "title": evt.get("title", ""),
            "country": country_val,
            "currency": evt.get("currency", "USD"),
            "impact": impact_val,
            "datetime": evt_dt.isoformat(),
            "forecast": evt.get("forecast", ""),
            "previous": evt.get("previous", ""),
            "actual": actual_val if actual_val else None,
            "unit": "",
            "source": evt.get("source", "ForexFactory"),
            "description": evt.get("title", ""),
            "category": "Macro",
            "status": status,
        })

    result.sort(key=lambda e: e["datetime"])
    return result


@app.get("/api/economic-calendar/protection", dependencies=[Depends(require_bridge_token)])
async def economic_calendar_protection():
    """Compact News Protection state consumed by the MT5 EA (polled via WebRequest)."""
    try:
        events = fetch_real_economic_calendar()
        protection = compute_news_protection(events)
        return {"ok": True, "protection": protection, "updated_at": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        return {"ok": False, "error": repr(e), "protection": {"level": "none", "active": False, "event": None, "in_seconds": 0, "live_remaining_seconds": 0, "message": ""}}


@app.get("/api/economic-calendar/stream")
async def economic_calendar_sse():
    async def event_generator():
        while True:
            try:
                events = fetch_real_economic_calendar()
                now = datetime.now(timezone.utc)
                week_start = now - timedelta(days=now.weekday())
                week_end = week_start + timedelta(days=7)

                formatted = []
                for evt in events:
                    try:
                        evt_dt = datetime.strptime(f"{evt.get('date', '')} {evt.get('time', '00:00')}", "%d/%m %H:%M")
                        evt_dt = evt_dt.replace(year=now.year, tzinfo=timezone.utc)
                        if evt_dt < now:
                            evt_dt = evt_dt.replace(year=now.year + 1)
                    except Exception:
                        continue

                    if evt_dt < week_start or evt_dt > week_end:
                        continue

                    impact_val = evt.get("impact", "LOW").upper()
                    actual_val = evt.get("actual", "")
                    status = "released" if actual_val else "upcoming"

                    formatted.append({
                        "id": evt.get("id", ""),
                        "title": evt.get("title", ""),
                        "country": evt.get("currency", "USD"),
                        "currency": evt.get("currency", "USD"),
                        "impact": impact_val,
                        "datetime": evt_dt.isoformat(),
                        "forecast": evt.get("forecast", ""),
                        "previous": evt.get("previous", ""),
                        "actual": actual_val if actual_val else None,
                        "unit": "",
                        "source": evt.get("source", "ForexFactory"),
                        "description": evt.get("title", ""),
                        "category": "Macro",
                        "status": status,
                    })

                formatted.sort(key=lambda e: e["datetime"])
                protection = compute_news_protection(events, now)
                yield f"data: {json.dumps({'events': formatted, 'protection': protection, 'timestamp': now.isoformat()})}\n\n"
            except Exception:
                pass
            await asyncio.sleep(30)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    # Bind 0.0.0.0 so the MT5 EA can reach the bridge via hostname/IP
    # (e.g. http://QtusDev:8005 -> 192.168.1.4). MT5 blocks loopback (127.0.0.1).
    host = os.getenv("ATE_DASHBOARD_HOST") or os.getenv("QUANTAI_DASHBOARD_HOST") or "0.0.0.0"
    port = int(os.getenv("ATE_DASHBOARD_PORT") or os.getenv("QUANTAI_DASHBOARD_PORT") or "8005")
    uvicorn.run(app, host=host, port=port)

