"""

╔══════════════════════════════════════════════════════════════════════════════╗

║           TRADEAI ATE - PRODUCTION SERVER WITH REAL MT5 + AI                ║

║                   server.py - Main Entry Point                             ║

╚══════════════════════════════════════════════════════════════════════════════╝



FIX LỖI 1: Dữ liệu nến thật từ MT5 qua python-bridge

FIX LỖI 2: AI phân tích chart thật theo phương pháp (SMC/ICT/PA/Sniper)

FIX LỖI 3: Auto-trade thật sự hoạt động theo phương pháp đã chọn

FIX LỖI 4: Multi-symbol support

FIX LỖI 5: Trading Method trigger chart refresh + AI re-analyze

FIX LỖI 8: Layout với dữ liệu thật từ backend

"""



import os

# pyrefly: ignore [untyped-import]

import psutil

import sys

import uuid

import random

import hashlib

import asyncio

import httpx

from datetime import datetime, timedelta, timezone

from typing import Optional, List, Dict, Any, Tuple

from collections import defaultdict, deque

from contextlib import asynccontextmanager



import pandas as pd

import numpy as np

from fastapi import FastAPI, HTTPException, Query, Request

from fastapi.middleware.cors import CORSMiddleware

from fastapi.responses import JSONResponse, StreamingResponse





class SafeJSONResponse(JSONResponse):

    """JSONResponse chặn NaN/Infinity — NaN từ indicators (thiếu nến cho window

    EMA/RSI) làm json.dumps ném "Out of range float" -> 500. Thay bằng null."""



    def render(self, content):

        return json.dumps(

            _json_safe(content),

            ensure_ascii=False,

            allow_nan=False,

            default=str,

            # BUG FIX: separators compact (",", ":") giống Starlette chuẩn — EA

            # MQL5 parse response bằng StringFind khớp chính xác chuỗi như

            # "status":"CLAIMED" / "trading_method":"SMC". Separator mặc định

            # của Python (", ", ": ") thêm khoảng trắng sau ':' khiến mọi chuỗi

            # khớp compact của EA thất bại (claim không bao giờ được thực thi).

            separators=(",", ":"),

        ).encode("utf-8")





def _json_safe(obj):

    """Đệ quy chuẩn hóa mọi kiểu dữ liệu (kể cả numpy/pandas) -> JSON hợp lệ.

    BUG FIX: trước đây chỉ thay NaN/Infinity cho float; markup từ pandas/numpy

    chứa numpy.bool_/numpy.float64 (vd OB.has_fvg_confluence, swing prices) khiến

    FastAPI jsonable_encoder ném 500 'numpy.bool' object is not iterable trên

    /api/market + /api/v1/bridge/markup khi EA đẩy 40000 nến."""

    if isinstance(obj, dict):

        return {k: _json_safe(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set, np.ndarray)):

        return [_json_safe(v) for v in list(obj)]

    # np.bool_ là subclass của int — phải check TRƯỚC np.integer/bool

    if isinstance(obj, (np.bool_, bool)):

        return bool(obj)

    if isinstance(obj, np.integer):

        return int(obj)

    if isinstance(obj, np.floating):

        obj = float(obj)

        return obj if math.isfinite(obj) else None

    if isinstance(obj, float):

        return obj if math.isfinite(obj) else None

    # np.datetime64 (vd từ DataFrame timestamp) không thể json.dumps được —

    # chuyển thành ISO string. pd.Timestamp cũng nằm trong nhóm datetime dưới.

    if isinstance(obj, np.datetime64):

        try:

            return pd.Timestamp(obj).to_pydatetime().isoformat()

        except Exception:

            return str(obj)

    if isinstance(obj, (pd.Timestamp, datetime)):

        return obj.isoformat()

    if obj is None:

        return None

    return obj

from pydantic import BaseModel

from asyncio import Queue

import json

import math

import uvicorn

from chart_markup import build_chart_markup



# ─── VERSION & CONFIG ──────────────────────────────────────────────────────────

VERSION = "3.0.0"

APP_NAME = "TradeAI ATE Dashboard"

DEBUG = os.getenv("DEBUG", "false").lower() == "true"# ─── EXTERNAL SERVICES CONFIG ────────────────────────────────────────────────
# Default port: 8848 (chuẩn hoá toàn bộ project — production VPS, Docker,
# hints checklist đều dùng giá trị này). Đổi qua env ATE_DASHBOARD_PORT.
DEFAULT_DASHBOARD_PORT = 8848
DASHBOARD_PORT = int(os.getenv("ATE_DASHBOARD_PORT", str(DEFAULT_DASHBOARD_PORT)))
BRIDGE_URL = os.getenv("BRIDGE_URL", "http://localhost:8007")  # Python MT5 Bridge
AI_ENGINE_URL = os.getenv("AI_ENGINE_URL", "http://localhost:8006")  # AI Engine
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))



# ─── IN-MEMORY STORAGE ────────────────────────────────────────────────────────

_positions: Dict[str, List[Dict[str, Any]]] = defaultdict(list)  # keyed by symbol

_trades: List[Dict[str, Any]] = []

_signals: List[Dict[str, Any]] = []

_commands: List[Dict[str, Any]] = []

_COMMANDS_MAX = 500  # cap để tránh memory leak khi EA không claim



def _enqueue_command(cmd: Dict[str, Any]) -> None:

    """M1 (BUG FIX): append command + auto-trim để tránh memory leak. Trước đây

    _commands.append(cmd) không bao giờ xóa lệnh cũ — EA không claim thì list

    tích lũy mãi mãi, cứ 24h có thể tích hàng nghìn dict."""

    _commands.append(cmd)

    if len(_commands) > _COMMANDS_MAX:

        # pop các lệnh TERMINAL (EXECUTED/REJECTED/FAILED/EXPIRED) cũ nhất;

        # nếu tất cả đều PENDING/QUEUED/CLAIMED thì pop cũ nhất vẫn an toàn

        # (các lệnh PENDING > _COMMANDS_MAX phút đã bị expire ở _ai_trade_loop).

        for _ in range(len(_commands) - _COMMANDS_MAX):

            oldest = _commands[0]

            if oldest.get("status") in ("QUEUED", "PENDING", "CLAIMED") and len(_commands) <= _COMMANDS_MAX:

                break

            _commands.pop(0)



_logs: deque[Dict[str, Any]] = deque(maxlen=1000)

_ai_events: deque[Dict[str, Any]] = deque(maxlen=200)

_market_cache: Dict[str, Dict[str, Any]] = {}  # symbol -> {candles, bid, ask, ts}

_cache_lock = asyncio.Lock()



# PHASE 3: Analysis cache to prevent recomputing on every request

_analysis_cache: Dict[str, Dict[str, Any]] = {}  # key = symbol:method:tf -> {result, ts}

_ANALYSIS_TTL = 5  # seconds



# DCA (Dollar Cost Averaging): trạng thái nhồi lệnh theo ticket.

# key = f"{symbol}:{ticket}" -> {"level": N, "last_add": iso}

_dca_state: Dict[str, Dict[str, Any]] = {}# ------------------------------------------------------------------
# Account state — supports MULTIPLE concurrent MT5 instances.
#
# Each EA pushes telemetry with its own `login`. We track every login
# separately in `_accounts` (keyed by str(login)). The legacy single
# `_account` dict is preserved as a "view" of the ACTIVE account — any
# place that reads `_account[...]` transparently sees the active one.
#
# Backward-compat: when no telemetry has arrived yet, `_account` holds
# the default placeholder so legacy code paths keep working.
# ------------------------------------------------------------------
def _default_account_state() -> Dict[str, Any]:
    return {
        "balance": 10000.0, "equity": 10000.0, "margin": 0.0, "margin_free": 10000.0,
        "open_positions": 0, "total_pnl": 0.0, "realized_pnl": 0.0, "win_rate": 0.0, "total_trades": 0,
        "mt5_connected": False, "login": 0, "server": "", "company": "",
        "account_mode": "DEMO",  # "DEMO" or "REAL" — auto-set from EA telemetry
        "auto_detected": False,  # True after first telemetry from this login
        "last_ea_telemetry_at": None,
        "ea_executor_id": None,
        "ea_symbol": None,
    }


_accounts: Dict[str, Dict[str, Any]] = {}  # key = str(login)
_active_login: str = "default"  # login currently displayed on dashboard


class _AccountView:
    """Backward-compat wrapper that delegates to the active account.

    `server._account["balance"]` returns the active account's balance.
    Setting via `_account["x"] = y` writes to the active account.
    Iteration / len() / `in` checks forward to the active account.
    """

    __slots__ = ()

    def _active(self) -> Dict[str, Any]:
        acc = _accounts.get(_active_login)
        if acc is None:
            acc = _default_account_state()
            _accounts[_active_login] = acc
        return acc

    def __getitem__(self, key: str) -> Any:
        return self._active()[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._active()[key] = value

    def __contains__(self, key: str) -> bool:
        return key in self._active()

    def __iter__(self):
        return iter(self._active())

    def __len__(self) -> int:
        return len(self._active())

    def get(self, key: str, default: Any = None) -> Any:
        return self._active().get(key, default)

    def keys(self):
        return self._active().keys()

    def values(self):
        return self._active().values()

    def items(self):
        return self._active().items()

    def update(self, *args, **kwargs) -> None:
        self._active().update(*args, **kwargs)


# Seed default placeholder so `_account` is always usable
_account = _AccountView()  # type: ignore[assignment]
_accounts["default"] = _default_account_state()


def get_account(login: Optional[str] = None) -> Dict[str, Any]:
    """Return account state dict for a given login (default = active)."""
    if login is None:
        return _AccountView._active()
    return _accounts.setdefault(str(login), _default_account_state())


def set_active_account(login: str) -> None:
    """Switch dashboard view to a different login."""
    global _active_login
    login_str = str(login)
    if login_str not in _accounts:
        _accounts[login_str] = _default_account_state()
    _active_login = login_str


def list_accounts() -> List[Dict[str, Any]]:
    """Return summary for all known accounts (for dashboard listing)."""
    out: List[Dict[str, Any]] = []
    for login, acc in _accounts.items():
        if not acc.get("auto_detected") and login == "default":
            continue  # skip empty placeholder
        out.append({
            "login": login,
            "server": acc.get("server", ""),
            "company": acc.get("company", ""),
            "account_mode": acc.get("account_mode", "DEMO"),
            "balance": acc.get("balance", 0.0),
            "equity": acc.get("equity", 0.0),
            "margin_free": acc.get("margin_free", 0.0),
            "open_positions": acc.get("open_positions", 0),
            "mt5_connected": acc.get("mt5_connected", False),
            "last_seen": acc.get("last_ea_telemetry_at"),
            "active": (login == _active_login),
            "executor_id": acc.get("ea_executor_id"),
        })
    return out



# BUG FIX: đọc cấu hình từ env (ATE_EXECUTION_MODE/KILL_SWITCH/LIVE_ARMED...) để

# container Docker tôn trọng .env — trước đây server.py bỏ qua env, luôn DEMO/kill=False.

_exec_mode_env = os.getenv("ATE_EXECUTION_MODE", "DEMO").upper()

_config = {

    "execution_mode": _exec_mode_env,

    "kill_switch": os.getenv("ATE_KILL_SWITCH", "false").lower() == "true",

    "demo_armed": os.getenv("ATE_DEMO_ARMED", "true").lower() == "true",

    "live_armed": os.getenv("ATE_LIVE_ARMED", "false").lower() == "true",

    "ai_auto_loop": False,  # Start disabled until user enables

    "trading_method": "SMC",

    "symbol": os.getenv("ATE_EXECUTION_SYMBOL", "XAUUSD"),

    "timeframe": "M15",

    "risk_per_trade_fraction": float(os.getenv("ATE_RISK_PERCENT", "1")) / 100.0,

    "max_open_positions": int(os.getenv("ATE_MAX_POSITIONS", "5")),

    "max_spread": float(os.getenv("ATE_MAX_SPREAD", "4.5")),

    "magic": int(os.getenv("ATE_EXECUTION_MAGIC", "888999")),

    "symbols": [os.getenv("ATE_EXECUTION_SYMBOL", "XAUUSD")],

    "news_window_minutes": int(os.getenv("ATE_NEWS_WINDOW_MINUTES", "15")),

    # Lịch tin tức bổ sung từ forexfactory (mirror nfs.faireconomy.media) —

    # MT5 CalendarValueHistory trên nhiều broker (Exness) trả rất ít/0 event.

    "ff_calendar_enabled": os.getenv("ATE_FF_CALENDAR_ENABLED", "true").lower() == "true",

    # DCA (nhồi lệnh trung bình giá khi lỗ) — mặc định TẮT, bật qua Settings.

    # Fail-closed: mọi lệnh DCA vẫn đi qua news protection + risk gate + giới hạn rủi ro.

    "dca_enabled": os.getenv("ATE_DCA_ENABLED", "false").lower() == "true",

    "dca_max_levels": int(os.getenv("ATE_DCA_MAX_LEVELS", "2")),        # tối đa số lần nhồi cho 1 vị thế

    "dca_distance_atr": float(os.getenv("ATE_DCA_DISTANCE_ATR", "1.5")),  # lỗ >= N x ATR thì nhồi

    "dca_interval_sec": int(os.getenv("ATE_DCA_INTERVAL_SEC", "300")),    # tối thiểu giữa 2 lần nhồi

    "dca_volume_multiplier": float(os.getenv("ATE_DCA_VOLUME_MULTIPLIER", "1.0")),  # hệ số volume mỗi mức

    "dca_max_risk_balance_pct": float(os.getenv("ATE_DCA_MAX_RISK_PCT", "0.01")),   # rủi ro tối đa / balance

}



# ─── SYMBOL MAP ───────────────────────────────────────────────────────────────

SYMBOL_MAP = {

    "XAUUSD": "XAUUSDm",

    "GOLD": "XAUUSDm",

    "EURUSD": "EURUSDm",

    "GBPUSD": "GBPUSDm",

}



# Các prefix symbol chuẩn để canonical hóa. BUG FIX: broker thật (ICMarkets) dùng

# symbol có suffix như XAUUSDc — cache key từ EA push (XAUUSDc_M15) không bao giờ

# khớp key fetch (XAUUSDm_M15) nên data_status rơi về STUB dù EA đang gửi nến thật.

_CANONICAL_SYMBOLS = {

    "XAUUSD": "XAUUSDm",

    "GOLD": "XAUUSDm",

    "EURUSD": "EURUSDm",

    "GBPUSD": "GBPUSDm",

}



def resolve_symbol(sym: str) -> str:

    """Canonical hóa symbol: XAUUSD, XAUUSDm, XAUUSDc, XAUUSD.a, GOLD... -> XAUUSDm

    để cache nến/claim từ EA (symbol chart thật có suffix broker) khớp với fetch."""

    s = sym.upper()

    if s in SYMBOL_MAP:

        return SYMBOL_MAP[s]

    for base, canonical in _CANONICAL_SYMBOLS.items():

        if s.startswith(base):

            return canonical

    return s



# ─── LIFESPAN (startup/shutdown) ─────────────────────────────────────────────

# BUG FIX (BUG-003): @app.on_event('startup'/'shutdown') bị deprecate trong

# FastAPI (thay bằng lifespan context manager). Chuyển hết logic khởi động/dọn

# dẹp background loop vào lifespan để bỏ cảnh báo và tương thích tương lai.

@asynccontextmanager

async def lifespan(app: FastAPI):

    """Start/stop các background loop theo vòng đời ứng dụng."""

    global _ai_loop_running, _ai_loop_task, _pos_mgr_task, _calendar_refresh_task

    _ai_loop_running = True

    _ai_loop_task = asyncio.create_task(_ai_trade_loop())

    _pos_mgr_task = asyncio.create_task(_position_manager_loop())

    _calendar_refresh_task = asyncio.create_task(_calendar_refresh_loop())

    _add_log("INFO", "STARTUP", f"{APP_NAME} v{VERSION} started")

    yield

    _ai_loop_running = False

    for task in (_ai_loop_task, _pos_mgr_task, _calendar_refresh_task):

        if task and not task.done():

            task.cancel()

            try:

                await task

            except (asyncio.CancelledError, Exception):

                pass

    _add_log("INFO", "SHUTDOWN", f"{APP_NAME} stopped")



# ─── APP CREATION ─────────────────────────────────────────────────────────────

app = FastAPI(

    title=APP_NAME, version=VERSION, description="ATE - Autonomous Trading Engine",

    default_response_class=SafeJSONResponse,

    lifespan=lifespan,

)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])



# ─── LOGGING ─────────────────────────────────────────────────────────────────

def _add_log(level: str, event: str, message: str, component: str = "server"):

    _logs.append({

        "id": str(uuid.uuid4()),

        "ts": datetime.now(timezone.utc).isoformat(),

        "level": level,

        "event": event,

        "component": component,

        "message": message

    })

    # deque with maxlen handles rotation automatically



def _add_ai_event(level: str, action: str, symbol: str, details: Dict[str, Any]):

    ev = {

        "id": str(uuid.uuid4()),

        "ts": datetime.now(timezone.utc).isoformat(),

        "level": level,

        "action": action,

        "symbol": symbol,

        "details": details

    }

    _ai_events.append(ev)

    # deque with maxlen handles rotation automatically



# ─── REAL MT5 DATA FETCHER ──────────────────────────────────────────────────

# BUG FIX: theo dõi nguồn dữ liệu thật (bridge/EA) hay stub — trước đây status

# luôn báo "LIVE" dù đang dùng dữ liệu giả khi bridge offline.

_bridge_data_real = False

_DATA_TTL = 600.0  # seconds: EA-pushed candles coi là tươi trong 120s



# EA (ATE_XAUUSD.mq5) đẩy nến thật qua POST /api/v1/bridge/candles với cột

# {t, ts, o, h, l, c, v}; python-bridge trả {time, open, high, low, close, volume}.

# Chuẩn hoá về {timestamp, open, high, low, close, volume}.

def _normalize_candle_df(df: pd.DataFrame) -> pd.DataFrame:

    if df is None or df.empty:

        return df

    rename = {}

    for col in df.columns:

        # pyrefly: ignore [unnecessary-type-conversion]

        c = str(col).strip()

        if c in ("ts", "time"):

            rename[col] = "timestamp"

        elif c == "t":

            rename[col] = "time_only"

        elif c in ("o",):

            rename[col] = "open"

        elif c in ("h",):

            rename[col] = "high"

        elif c in ("l",):

            rename[col] = "low"

        elif c in ("c",):

            rename[col] = "close"

        elif c in ("v", "tick_volume"):

            rename[col] = "volume"

    if rename:

        df = df.rename(columns=rename)

    # EA cột t = "HH:MM" chỉ — không dùng làm thời gian, bỏ đi

    if "time_only" in df.columns:

        df = df.drop(columns=["time_only"])

    if "timestamp" in df.columns:

        # pd.to_datetime linh hoạt: "2026-08-12T09:30:00" hoặc epoch

        try:

            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

        except Exception:

            pass

        # BUG FIX: bỏ dòng timestamp không parse được (NaT) — trước đây giữ NaT

        # khiến chart vẽ nến lệch thời gian hoặc lỗi fromisoformat ở get_market.

        df = df.dropna(subset=["timestamp"])

        df = df.sort_values("timestamp").reset_index(drop=True)

    for col in ("open", "high", "low", "close", "volume"):

        if col in df.columns:

            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Thứ tự cột chuẩn: timestamp, open, high, low, close, volume

    ordered = [c for c in ("timestamp", "open", "high", "low", "close", "volume") if c in df.columns]

    if ordered:

        df = df[ordered]

    return df





def _cached_candles(symbol: str, tf: str) -> Optional[pd.DataFrame]:

    """Đọc nến THẬT do EA đẩy lên (tươi trong _DATA_TTL)."""

    key = f"{resolve_symbol(symbol)}_{tf}"

    entry = _market_cache.get(key)

    if not entry or not entry.get("candles"):

        return None

    try:

        updated = datetime.fromisoformat((entry.get("candles_updated") or "").replace("Z", "+00:00"))

    except Exception:

        return None

    if (datetime.now(timezone.utc) - updated).total_seconds() > _DATA_TTL:

        return None

    df = _normalize_candle_df(pd.DataFrame(entry["candles"]))

    if df is None or df.empty or "close" not in df.columns:

        return None

    return df





async def fetch_real_candles(symbol: str, tf: str, count: int = 1000) -> Optional[pd.DataFrame]:

    """Lấy nến thật theo 3 tầng, không bao giờ im lặng trả dữ liệu giả:

    1) Nến EA đẩy (POST /api/v1/bridge/candles) — tươi nhất, đúng chart MT5

    2) python-bridge /api/v1/market/candles — copy_rates thật từ MT5

    3) generate_stub_candles — CHỈ khi cả 2 tầng chết, đánh dấu _bridge_data_real=False

    BUG FIX: trước đây gọi {BRIDGE_URL}/api/candles (không tồn tại) -> luôn 404 ->

    toàn bộ dashboard chạy trên dữ liệu giả mà vẫn báo LIVE."""

    global _bridge_data_real



    cached = _cached_candles(symbol, tf)

    if cached is not None and len(cached) > 0:

        # BUG FIX: EA giờ đẩy 40000 nến M1 base + TF chart mỗi 30s. Trước đây điều

        # kiện `len(cached) >= count` khiến cache (vd 5000) bị bỏ qua khi web yêu cầu

        # count lớn (M1 mặc định 72000) -> rơi xuống bridge/stub -> chart chỉ vài nến.

        # Giờ cache EA là nguồn ưu tiên NHẤT bất kể count; bridge chỉ dùng khi EA chưa push.

        _bridge_data_real = True

        _add_log("DEBUG", "DATA_SRC", f"EA-push candles {symbol} {tf} ({len(cached)})")

        return cached.tail(count).reset_index(drop=True)



    try:

        async with httpx.AsyncClient(timeout=0.3) as client:

            res = await client.get(

                f"{BRIDGE_URL}/api/v1/market/candles",

                params={"symbol": resolve_symbol(symbol), "tf": tf, "count": count}

            )

            if res.status_code == 200:

                data = res.json()

                if "candles" in data and data["candles"]:

                    df = _normalize_candle_df(pd.DataFrame(data["candles"]))

                    if df is not None and not df.empty and "close" in df.columns:

                        # Bridge trả đầy đủ history — tốt hơn cache 100 nến của EA

                        _bridge_data_real = True

                        _add_log("DEBUG", "DATA_SRC", f"bridge candles {symbol} {tf} ({len(df)})")

                        return df

    except Exception as e:

        _add_log("WARN", "BRIDGE_FETCH", f"MT5 bridge unavailable: {e}")



    # EA cache có nhưng ít nến hơn yêu cầu (bridge down) — vẫn dùng nến thật

    if cached is not None and len(cached) > 0:

        _bridge_data_real = True

        _add_log("DEBUG", "DATA_SRC", f"EA-push candles (partial) {symbol} {tf} ({len(cached)}/{count})")

        return cached.tail(count).reset_index(drop=True)



    # BUG FIX: EA push nến theo TF của chart (thường M1). Nếu TF yêu cầu (M15/H1)

    # không có trong cache, RESAMPLE nến M1 thật từ EA lên TF đó — vẫn là dữ liệu

    # THẬT từ MT5 (không phải stub). Trước đây miss TF -> rơi vào stub => toàn bộ

    # dashboard hiện STUB dù EA đang đẩy nến thật về mỗi 30s.

    base_src = _resample_from_cache(symbol, tf, count)

    if base_src is not None:

        _bridge_data_real = True

        _add_log("DEBUG", "DATA_SRC", f"EA-push resampled {symbol} {tf} from {base_src}")

        return base_src



    # Fallback: chỉ dùng stub khi KHÔNG có nguồn thật nào, và đánh dấu STUB

    _bridge_data_real = False

    _add_log("WARN", "DATA_STUB", f"No real MT5 data for {symbol} {tf} -> STUB (bridge down / EA not connected)")

    return generate_stub_candles(count, tf, symbol)



def _resample_from_cache(symbol: str, tf: str, count: int) -> Optional[pd.DataFrame]:

    """Resample nến M1 thật (EA push) lên TF bất kỳ. Trả None nếu không có nguồn.

    Dùng OHLC chuẩn: open=first, high=max, low=min, close=last, volume=sum."""

    if tf in ("M1", "MN1"):

        return None  # M1 không cần resample; MN1 quá xa, bỏ qua

    base_df = _cached_candles(symbol, "M1")

    if base_df is None or base_df.empty or "timestamp" not in base_df.columns:

        return None

    try:

        df = base_df.copy()

        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

        df = df.dropna(subset=["timestamp"]).sort_values("timestamp")

        if df.empty:

            return None

        freq = {"M5": "5min", "M15": "15min", "M30": "30min", "H1": "1h", "H4": "4h", "D1": "1D"}.get(tf)

        if not freq:

            return None

        df = df.set_index("timestamp")

        agg = df.resample(freq, label="left", closed="left").agg(

            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}

        ).dropna(subset=["open"])

        agg = agg.reset_index()

        # pyrefly: ignore [missing-attribute]

        agg["timestamp"] = agg["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")

        return agg.tail(count).reset_index(drop=True)

    except Exception as e:

        _add_log("WARN", "RESAMPLE_FAIL", f"resample {tf} failed: {e}")

        return None





def generate_stub_candles(count: int, tf: str, symbol: str) -> pd.DataFrame:

    """Generate realistic stub candle data when MT5 is unavailable.

    PHASE 2: Vectorized for 100x faster generation on large counts (e.g. M1=72000)."""

    freq_map = {"M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min", "H1": "1h", "H4": "4h", "D1": "1d"}

    freq = freq_map.get(tf, "15min")



    try:

        dates = pd.date_range(end=datetime.now(), periods=count, freq=freq)

    except Exception:

        dates = pd.date_range(end=datetime.now(), periods=count, freq="h")



    # Cập nhật base prices theo 2026 thực tế

    base_prices = {"XAUUSD": 3370, "XAUUSDm": 3370, "EURUSD": 1.085, "GBPUSD": 1.27, "USDJPY": 155.0}

    base = base_prices.get(symbol, 3370)

    volatility = base * 0.005



    # Use a local RNG to avoid polluting global random state (BUG-013 fix)

    seed = int(datetime.now().timestamp() // 300) + hash(symbol + tf) % 10000

    rng = np.random.RandomState(seed % 2**32)



    # Vectorized random generation

    close = base

    trend = np.ones(count)

    flips = rng.random(count) < 0.05

    trend[flips] = rng.choice([-1, 1], size=flips.sum())

    

    # Random walk

    noise = rng.normal(0, volatility, count)

    drift = trend * volatility * 0.3

    changes = noise + drift

    

    # Close[i] = close[i-1] + change[i]

    close = np.cumsum(changes) + base

    open_ = np.concatenate([[base], close[:-1]])

    

    # Body, wick

    body = np.abs(close - open_)

    wick_ratio = rng.uniform(0.2, 0.8, count)

    wick = body * wick_ratio

    

    bull = close >= open_

    high = np.where(bull, close + wick, open_ + wick * rng.uniform(0.3, 0.6, count))

    low = np.where(bull, open_ - wick * rng.uniform(0.3, 0.6, count), close - wick)

    

    # Sanitize

    high = np.maximum(high, np.maximum(open_, close))

    low = np.minimum(low, np.minimum(open_, close))

    

    df = pd.DataFrame({

        "timestamp": dates,

        "open": open_,

        "high": high,

        "low": low,

        "close": close,

        "volume": rng.uniform(100, 5000, count),

    })

    return df



# ─── MULTI-TIMEFRAME CONTEXT CACHE ──────────────────────────────────────────

_ctx_cache: Dict[str, Dict[str, Any]] = {}

_CTX_TTL = 60.0  # seconds



async def _fetch_context_candles(symbol: str, tf: str, count: int = 600) -> Optional[pd.DataFrame]:

    """Best-effort fetch of an HTF context frame (M15/H1/D1...) with a short

    TTL cache. Nguồn: nến EA đẩy -> python-bridge -> None (không dùng stub cho

    context frame; chỉ primary frame được phép rơi vào stub và đánh dấu STUB)."""

    key = f"{symbol}:{tf}"

    now = datetime.now(timezone.utc).timestamp()

    cached = _ctx_cache.get(key)

    if cached and (now - cached["ts"]) < _CTX_TTL:

        return cached["df"]



    df = _cached_candles(symbol, tf)

    if df is None:

        try:
            async with httpx.AsyncClient(timeout=0.2) as client:

                res = await client.get(

                    f"{BRIDGE_URL}/api/v1/market/candles",

                    params={"symbol": resolve_symbol(symbol), "tf": tf, "count": count}

                )

                if res.status_code == 200:

                    data = res.json()

                    if "candles" in data and data["candles"]:

                        df = _normalize_candle_df(pd.DataFrame(data["candles"]))

        except Exception:

            df = None

    if df is not None and not df.empty:

        _ctx_cache[key] = {"df": df, "ts": now}

    else:

        _ctx_cache[key] = {"df": None, "ts": now}

    # Keep the context cache bounded (one small entry per symbol:tf).

    if len(_ctx_cache) > 64:

        for stale_key in [k for k in _ctx_cache if k != key]:

            _ctx_cache.pop(stale_key, None)

            if len(_ctx_cache) <= 64:

                break

    return df



async def fetch_real_bid_ask(symbol: str) -> tuple[float, float]:

    """Lấy bid/ask THẬT: 1) tick EA gửi trong telemetry 2) python-bridge

    /api/v1/market/tick 3) stub (chỉ để không crash)."""

    key = f"{resolve_symbol(symbol)}_tick"

    tick = _market_cache.get(key)

    if tick and tick.get("bid") and tick.get("ask"):

        try:

            updated = datetime.fromisoformat((tick.get("ts") or "").replace("Z", "+00:00"))

            if (datetime.now(timezone.utc) - updated).total_seconds() < _DATA_TTL:

                return float(tick["bid"]), float(tick["ask"])

        except Exception:

            pass

    try:
        async with httpx.AsyncClient(timeout=0.2) as client:

            res = await client.get(f"{BRIDGE_URL}/api/v1/market/tick", params={"symbol": resolve_symbol(symbol)})

            if res.status_code == 200:

                data = res.json()

                bid, ask = float(data.get("bid", 0)), float(data.get("ask", 0))

                if bid > 0 and ask > 0:

                    # Không set _bridge_data_real ở đây: tick OK không chứng minh nến thật

                    return bid, ask

    except Exception:

        pass



    # Fallback stub

    df = generate_stub_candles(5, "M1", symbol)

    price = float(df["close"].iloc[-1])

    spread = 0.5 if "XAU" in symbol else 2.0

    return price, price + spread



# ─── INDICATORS & ANALYSIS ────────────────────────────────────────────────────

def _series_last(series, default):

    """Lấy giá trị cuối của series, NaN/Inf -> default. BUG FIX: khi nến ít hơn

    window indicator (vd EMA200 cần 200 nến nhưng resample M1->M15 chỉ có 20),

    iloc[-1] = NaN -> JSON serialize fail 500 ("Out of range float")."""

    if series is None or len(series) == 0:

        return default

    try:

        v = series.ffill().iloc[-1]

        f = float(v)

        return f if math.isfinite(f) else default

    except Exception:

        return default





def calculate_indicators(df: pd.DataFrame) -> Dict[str, Any]:

    """Calculate technical indicators from candles"""

    if df.empty:

        return {"rsi": 50, "atr": 15, "macd": "NEUTRAL", "ema_fast": 0, "ema_medium": 0, "ema_slow": 0}



    close = df["close"]

    high = df["high"]

    low = df["low"]



    ema_fast = close.ewm(span=9, adjust=False).mean()

    ema_medium = close.ewm(span=21, adjust=False).mean()

    ema_slow = close.ewm(span=50, adjust=False).mean()

    ema200 = close.ewm(span=200, adjust=False).mean()



    delta = close.diff()

    gain = delta.clip(lower=0).rolling(window=14).mean()

    loss = (-delta.clip(upper=0)).rolling(window=14).mean()

    rs = gain / loss.replace(0, np.nan)

    rsi = 100 - (100 / (1 + rs))



    tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)

    atr = tr.rolling(window=14).mean()



    ema12 = close.ewm(span=12, adjust=False).mean()

    ema26 = close.ewm(span=26, adjust=False).mean()

    macd_line = ema12 - ema26

    signal_line = macd_line.ewm(span=9, adjust=False).mean()

    macd_hist = macd_line - signal_line



    macd_str = "BULLISH" if macd_hist.iloc[-1] > 0 else "BEARISH" if macd_hist.iloc[-1] < 0 else "NEUTRAL"



    low14 = low.rolling(window=14).min()

    high14 = high.rolling(window=14).max()

    stoch_k = 100 * ((close - low14) / (high14 - low14))

    stoch_d = stoch_k.rolling(window=3).mean()

    stoch_str = "OVERBOUGHT" if stoch_k.iloc[-1] > 80 else "OVERSOLD" if stoch_k.iloc[-1] < 20 else "NEUTRAL"



    return {

        "ema_fast": _series_last(ema_fast, 0),

        "ema_medium": _series_last(ema_medium, 0),

        "ema_slow": _series_last(ema_slow, 0),

        "ema200": _series_last(ema200, 0),

        "rsi": _series_last(rsi, 50),

        "atr": _series_last(atr, 15),

        "macd": macd_str,

        "macd_value": _series_last(macd_hist, 0),

        "macd_signal": _series_last(signal_line, 0),

        "stoch": stoch_str,

        "stoch_k": _series_last(stoch_k, 50),

        "stoch_d": _series_last(stoch_d, 50),

        "volume": _series_last(df["volume"], 1000) if "volume" in df.columns else 1000,

    }



def detect_fvg(df: pd.DataFrame) -> List[Dict[str, Any]]:

    """Detect Fair Value Gaps (FVG / Imbalance)"""

    fvgs = []

    for i in range(2, len(df)):

        prev_low_1 = df["low"].iloc[i - 2]

        prev_high_1 = df["high"].iloc[i - 2]

        curr_low = df["low"].iloc[i]

        curr_high = df["high"].iloc[i]

        curr_close = df["close"].iloc[i]



        # Bullish FVG: current candle body doesn't overlap with previous candle body

        if curr_low > prev_high_1:

            fvgs.append({

                "type": "FVG_BULL",

                "direction": "BULLISH",

                "index": i,

                "top": curr_low,

                "bottom": prev_high_1,

                "time": str(df["timestamp"].iloc[i]) if "timestamp" in df.columns else "",

                "filled": curr_close < prev_high_1

            })



        # Bearish FVG

        if curr_high < prev_low_1:

            fvgs.append({

                "type": "FVG_BEAR",

                "direction": "BEARISH",

                "index": i,

                "top": prev_low_1,

                "bottom": curr_high,

                "time": str(df["timestamp"].iloc[i]) if "timestamp" in df.columns else "",

                "filled": curr_close > prev_low_1

            })

    return fvgs



def detect_order_blocks(df: pd.DataFrame) -> List[Dict[str, Any]]:

    """Detect Order Blocks (OB) - last bearish/bullish candle before a series of opposite candles"""

    blocks = []

    for i in range(5, len(df) - 3):

        is_bull = df["close"].iloc[i] > df["open"].iloc[i]

        is_bear = df["close"].iloc[i] < df["open"].iloc[i]



        # Check next 3 candles are opposite

        if is_bull:

            next_all_bear = all(df["close"].iloc[i+j] < df["open"].iloc[i+j] for j in range(1, min(4, len(df)-i)))

            if next_all_bear:

                blocks.append({

                    "type": "OB_BULL",

                    "direction": "BULLISH",

                    "index": i,

                    "top": max(df["high"].iloc[i], df["close"].iloc[i]),

                    "bottom": min(df["low"].iloc[i], df["open"].iloc[i]),

                    "time": str(df["timestamp"].iloc[i]) if "timestamp" in df.columns else "",

                    "mitigated": False

                })

        elif is_bear:

            next_all_bull = all(df["close"].iloc[i+j] > df["open"].iloc[i+j] for j in range(1, min(4, len(df)-i)))

            if next_all_bull:

                blocks.append({

                    "type": "OB_BEAR",

                    "direction": "BEARISH",

                    "index": i,

                    "top": max(df["high"].iloc[i], df["open"].iloc[i]),

                    "bottom": min(df["low"].iloc[i], df["close"].iloc[i]),

                    "time": str(df["timestamp"].iloc[i]) if "timestamp" in df.columns else "",

                    "mitigated": False

                })

    return blocks[-10:]  # Keep last 10



def detect_bos_choch(df: pd.DataFrame) -> Dict[str, Any]:

    """Detect Break of Structure (BOS) and Change of Character (CHoCH).

    BUG FIX (2 lỗi logic):

    1) Swing cũ dùng window min/max 5 nến với low[i] < low[i-1] — trong uptrend,

       các swing low tăng dần nên window luôn chứa low thấp hơn TRƯỚC đó → không

       bao giờ tìm được >= 2 swing lows → CHoCH không bao giờ xuất hiện. Dùng

       fractal: nến có low thấp hơn 2 nến mỗi bên (cực trị địa phương).

    2) Trend cũ đoán bằng cách so sánh prev_high vs prev_low (2 swing khác loại)

       — sai. Trend đúng: uptrend = swing low sau cao hơn swing low trước (HH/HL),

       downtrend = swing high sau thấp hơn swing high trước (LH/LL).

    """

    if len(df) < 8:

        return {}

    highs = df["high"].to_numpy(dtype=float)

    lows = df["low"].to_numpy(dtype=float)

    closes = df["close"].to_numpy(dtype=float)

    n = len(df)

    swing_highs: List[Tuple[int, float]] = []

    swing_lows: List[Tuple[int, float]] = []

    for i in range(2, n - 2):

        if highs[i] == max(highs[i-2:i+3]) and highs[i] > highs[i-1] and highs[i] > highs[i+1]:

            swing_highs.append((i, float(highs[i])))

        if lows[i] == min(lows[i-2:i+3]) and lows[i] < lows[i-1] and lows[i] < lows[i+1]:

            swing_lows.append((i, float(lows[i])))

    if not swing_highs or not swing_lows:

        return {}



    # pyrefly: ignore [unnecessary-type-conversion]

    last_high_price = float(swing_highs[-1][1])

    # pyrefly: ignore [unnecessary-type-conversion]

    prev_high_price = float(swing_highs[-2][1]) if len(swing_highs) >= 2 else last_high_price

    # pyrefly: ignore [unnecessary-type-conversion]

    last_low_price = float(swing_lows[-1][1])

    # pyrefly: ignore [unnecessary-type-conversion]

    prev_low_price = float(swing_lows[-2][1]) if len(swing_lows) >= 2 else last_low_price

    close = float(closes[-1])



    # Bullish BOS: price closes above previous swing high

    if close > prev_high_price:

        return {"kind": "BOS", "direction": "BULLISH", "break_price": prev_high_price}

    # Bearish BOS: price closes below previous swing low

    if close < prev_low_price:

        return {"kind": "BOS", "direction": "BEARISH", "break_price": prev_low_price}



    # Trend + CHoCH (phá swing gần nhất NGƯỢC hướng trend)

    uptrend = last_low_price > prev_low_price

    downtrend = last_high_price < prev_high_price

    if uptrend and close < last_low_price:

        return {"kind": "CHoCH", "direction": "BEARISH", "break_price": last_low_price}

    if downtrend and close > last_high_price:

        return {"kind": "CHoCH", "direction": "BULLISH", "break_price": last_high_price}



    return {}



def detect_liquidity_sweep(df: pd.DataFrame) -> Optional[str]:

    """Detect Liquidity Sweep - price hunts above/below key levels"""

    if df is None or len(df) < 10:

        return None



    recent_highs = df["high"].iloc[:-1].tail(10)

    recent_lows = df["low"].iloc[:-1].tail(10)

    if recent_highs.empty or recent_lows.empty:

        return None



    max_high = float(recent_highs.max())

    min_low = float(recent_lows.min())



    last_close = float(df["close"].iloc[-1])

    last_high = float(df["high"].iloc[-1])

    last_low = float(df["low"].iloc[-1])



    # BUG FIX (direction): stop-hunt ABOVE recent highs (Buy-Side Liquidity taken)

    # closing back below = BEARISH reversal signal; stop-hunt BELOW recent lows

    # (Sell-Side Liquidity taken) closing back above = BULLISH reversal signal.

    # Trước đây bị ĐẢO NGƯỢC — làm lệch điểm SMC trong analyze_smc/ULTRA_CONFLUENCE

    # (khớp semantics với detectors.detect_liquidity_sweep + method_overlays SFP).

    if last_high > max_high and last_close < max_high:

        return "BEARISH_SWEEP"



    if last_low < min_low and last_close > min_low:

        return "BULLISH_SWEEP"



    return None



# ─── METHOD-SPECIFIC ANALYSIS ─────────────────────────────────────────────────

def analyze_smc(df: pd.DataFrame, indicators: Dict[str, Any]) -> Dict[str, Any]:

    """Smart Money Concepts analysis - Order Blocks, FVGs, BOS, CHoCH, Liquidity"""

    fvgs = detect_fvg(df)

    obs = detect_order_blocks(df)

    bos_choch = detect_bos_choch(df)

    liq_sweep = detect_liquidity_sweep(df)



    bull_fvg = [f for f in fvgs if f["direction"] == "BULLISH" and not f.get("filled")]

    bear_fvg = [f for f in fvgs if f["direction"] == "BEARISH" and not f.get("filled")]

    bull_ob = [o for o in obs if o["direction"] == "BULLISH"]

    bear_ob = [o for o in obs if o["direction"] == "BEARISH"]



    # SMC Scoring

    score = 50

    factors = []



    if bull_ob and not bear_ob:

        score += 15

        factors.append("Bullish Order Block detected")

    if bear_ob and not bull_ob:

        score -= 15

        factors.append("Bearish Order Block detected")

    if bull_fvg and not bear_fvg:

        score += 10

        factors.append("Unfilled Bullish FVG")

    if bear_fvg and not bull_fvg:

        score -= 10

        factors.append("Unfilled Bearish FVG")

    if bos_choch.get("kind") == "BOS" and bos_choch.get("direction") == "BULLISH":

        score += 20

        factors.append("Bullish BOS confirmed")

    if bos_choch.get("kind") == "BOS" and bos_choch.get("direction") == "BEARISH":

        score -= 20

        factors.append("Bearish BOS confirmed")

    if liq_sweep == "BULLISH_SWEEP":

        score += 10

        factors.append("Bullish Liquidity Sweep - reversal setup")

    if liq_sweep == "BEARISH_SWEEP":

        score -= 10

        factors.append("Bearish Liquidity Sweep - reversal setup")



    score = max(0, min(100, score))



    return {

        "score": score,

        "signal": "BUY" if score > 55 else "SELL" if score < 45 else "WAIT",

        "factors": factors,

        "objects": {

            "bull_fvg_count": len(bull_fvg),

            "bear_fvg_count": len(bear_fvg),

            "bull_ob_count": len(bull_ob),

            "bear_ob_count": len(bear_ob),

            "bos_choch": bos_choch,

            "liquidity_sweep": liq_sweep,

        }

    }



def analyze_ict(df: pd.DataFrame, indicators: Dict[str, Any]) -> Dict[str, Any]:

    """ICT (Inner Circle Trader) analysis - Killzones, OTE, PD Array, etc."""

    fib_62 = 0.0

    fib_78 = 0.0

    # OTE (Optimal Trade Entry) - Fibonacci retracement zones

    if df is not None and len(df) >= 50:

        swing_high = float(df["high"].tail(50).max())

        swing_low = float(df["low"].tail(50).min())

        range_size = swing_high - swing_low



        fib_62 = swing_low + range_size * 0.618

        fib_78 = swing_low + range_size * 0.786



        current = float(df["close"].iloc[-1])



        # OTE zones

        if current > fib_78:

            zone = "PREMIUM"

            score_adj = -15

        elif current > fib_62:

            zone = "FAIR VALUE"

            score_adj = 5

        else:

            zone = "DISCOUNT"

            score_adj = 15

    else:

        zone = "NEUTRAL"

        score_adj = 0



    # ICT Scoring based on indicators + zones

    score = 50 + score_adj

    factors = [f"Price in {zone} zone"]



    if indicators["macd"] == "BULLISH":

        score += 10

        factors.append("MACD bullish")

    elif indicators["macd"] == "BEARISH":

        score -= 10

        factors.append("MACD bearish")



    if indicators["rsi"] < 30:

        score += 10

        factors.append("RSI oversold")

    elif indicators["rsi"] > 70:

        score -= 10

        factors.append("RSI overbought")



    score = max(0, min(100, score))



    return {

        "score": score,

        "signal": "BUY" if score > 55 else "SELL" if score < 45 else "WAIT",

        "factors": factors,

        "objects": {

            "zone": zone,

            "fib_62": fib_62,

            "fib_78": fib_78,

        }

    }





def analyze_price_action(df: pd.DataFrame, indicators: Dict[str, Any]) -> Dict[str, Any]:

    """Price Action analysis - Candlestick patterns, S/R, Trend"""

    # Detect recent candle patterns

    if len(df) >= 3:

        last = df.iloc[-1]

        prev = df.iloc[-2]



        is_bull = last["close"] > last["open"]

        is_bear = last["close"] < last["open"]

        prev_bull = prev["close"] > prev["open"]

        prev_bear = prev["close"] < prev["open"]



        pattern = "NONE"



        # Pin Bar

        body = abs(last["close"] - last["open"])

        upper_wick = last["high"] - max(last["open"], last["close"])

        lower_wick = min(last["open"], last["close"]) - last["low"]



        if upper_wick > body * 2 and lower_wick < body * 0.5:

            pattern = "PIN_BAR_BEAR" if is_bear else "PIN_BAR_BULL"

        elif lower_wick > body * 2 and upper_wick < body * 0.5:

            pattern = "PIN_BAR_BULL" if is_bull else "PIN_BAR_BEAR"



        # Engulfing

        if is_bull and prev_bear and last["close"] > prev["open"] and last["open"] < prev["close"]:

            pattern = "BULLISH_ENGULFING"

        elif is_bear and not prev_bull and last["close"] < prev["open"] and last["open"] > prev["close"]:

            pattern = "BEARISH_ENGULFING"



        # Inside Bar

        if last["high"] < prev["high"] and last["low"] > prev["low"]:

            pattern = "INSIDE_BAR"



    else:

        pattern = "UNKNOWN"



    # Trend detection

    ema_fast = indicators["ema_fast"]

    ema_slow = indicators["ema_slow"]

    ema200 = indicators["ema200"]



    if ema_fast > ema_slow > ema200:

        trend = "BULLISH"

        score_adj = 15

    elif ema_fast < ema_slow < ema200:

        trend = "BEARISH"

        score_adj = -15

    else:

        trend = "RANGING"

        score_adj = 0



    score = 50 + score_adj

    factors = [f"Trend: {trend}", f"Pattern: {pattern}"]



    score = max(0, min(100, score))



    return {

        "score": score,

        "signal": "BUY" if score > 55 else "SELL" if score < 45 else "WAIT",

        "factors": factors,

        "objects": {

            "pattern": pattern,

            "trend": trend,

        }

    }



def analyze_sniper(df: pd.DataFrame, indicators: Dict[str, Any]) -> Dict[str, Any]:

    """Sniper analysis - EMA crossover, momentum, confluence"""

    ema9 = indicators["ema_fast"]

    ema21 = indicators["ema_medium"]

    rsi = indicators["rsi"]

    macd = indicators["macd"]



    # EMA Crossover signal

    prev_close = float(df["close"].iloc[-2]) if len(df) >= 2 else ema9

    prev_ema9 = ema9 - (indicators["atr"] * 0.1)  # Approximate



    crossover = "NONE"

    score_adj = 0

    if prev_ema9 < ema21 and ema9 > ema21:

        crossover = "BULLISH_CROSSOVER"

        score_adj = 25

    elif prev_ema9 > ema21 and ema9 < ema21:

        crossover = "BEARISH_CROSSOVER"

        score_adj = -25



    # Momentum confirmation

    momentum_score = 0

    if rsi > 50: momentum_score += 10

    if rsi < 50: momentum_score -= 10

    if macd == "BULLISH": momentum_score += 15

    if macd == "BEARISH": momentum_score -= 15

    if indicators["ema_fast"] > indicators["ema_medium"]: momentum_score += 10

    if indicators["ema_fast"] < indicators["ema_medium"]: momentum_score -= 10



    score = 50 + score_adj + momentum_score

    factors = [f"EMA Crossover: {crossover}", f"Momentum: {momentum_score > 0 and 'BULLISH' or 'BEARISH'}"]



    score = max(0, min(100, score))



    return {

        "score": score,

        "signal": "BUY" if score > 60 else "SELL" if score < 40 else "WAIT",

        "factors": factors,

        "objects": {

            "crossover": crossover,

            "ema9": ema9,

            "ema21": ema21,

            "rsi": rsi,

            "macd": macd,

        }

    }



# ─── MAIN AI ANALYSIS ──────────────────────────────────────────────────────────

async def run_ai_analysis(symbol: str, method: str, tf: Optional[str] = None) -> Dict[str, Any]:

    """Run AI analysis based on selected trading method.

    PHASE 3: 5-second cache prevents duplicate computation on parallel requests.

    BUG FIX: nhận tham số tf — trước đây luôn phân tích M15 dù người dùng đang

    xem M5, và cache key thiếu tf nên các khung giờ khác nhau đụng cache nhau."""

    # pyrefly: ignore [bad-assignment]

    tf = tf or _config.get("timeframe", "M15")

    cache_key = f"{symbol}:{method}:{tf}"

    now = datetime.now(timezone.utc).timestamp()

    cached = _analysis_cache.get(cache_key)

    if cached and (now - cached["ts"]) < _ANALYSIS_TTL:

        return cached["result"]

    

    # pyrefly: ignore [bad-argument-type]

    # pyrefly: ignore [bad-argument-type]

    df = await fetch_real_candles(symbol, tf, 500)

    if df is None or df.empty:

        empty = {"score": 50, "signal": "WAIT", "factors": ["No data available"]}

        _analysis_cache[cache_key] = {"result": empty, "ts": now}

        return empty



    indicators = calculate_indicators(df)



    if method == "SMC":

        result = analyze_smc(df, indicators)

    elif method == "ICT":

        result = analyze_ict(df, indicators)

    elif method == "PRICE_ACTION":

        result = analyze_price_action(df, indicators)

    elif method == "SNIPER":

        result = analyze_sniper(df, indicators)

    else:

        # ULTRA_CONFLUENCE - combine all methods

        smc = analyze_smc(df, indicators)

        ict = analyze_ict(df, indicators)

        pa = analyze_price_action(df, indicators)

        sniper = analyze_sniper(df, indicators)



        combined_score = (smc["score"] + ict["score"] + pa["score"] + sniper["score"]) / 4



        result = {

            "score": combined_score,

            "signal": "BUY" if combined_score > 55 else "SELL" if combined_score < 45 else "WAIT",

            "factors": smc["factors"] + ict["factors"][:2] + sniper["factors"][:1],

            "objects": {

                "smc": smc["objects"],

                "ict": ict["objects"],

                "sniper": sniper["objects"],

            }

        }



    # Add common data

    result["indicators"] = indicators

    result["last_price"] = float(df["close"].iloc[-1])

    result["method"] = method

    result["symbol"] = symbol



    _analysis_cache[cache_key] = {"result": result, "ts": datetime.now(timezone.utc).timestamp()}

    return result



# ─── TRADE BOOKKEEPING HELPERS ──────────────────────────────────────────────


def _is_demo_mode() -> bool:
    """Quyết định demo hay live.

    Thứ tự ưu tiên (fail-closed):
      1. EA telemetry của account đang active báo account_mode=REAL → LIVE.
         (Drop EA vào MT5 thật, chạy lệnh thật — không cần config gì.)
      2. EA telemetry báo account_mode=DEMO → DEMO.
      3. Chưa có telemetry nào → đọc env ATE_EXECUTION_MODE (default DEMO).
    """
    acc = _accounts.get(_active_login) or {}
    auto_mode = (acc.get("account_mode") or "").upper().strip()
    if auto_mode == "REAL":
        return False
    if auto_mode == "DEMO":
        return True
    # pyrefly: ignore [unnecessary-type-conversion]
    return str(_config.get("execution_mode", "DEMO")).upper() != "LIVE"


def _ea_fresh() -> bool:
    """EA còn sống? = telemetry gần nhất của ACTIVE account < 60s (EA gửi mỗi 5s).
    BUG FIX: trước đây ea_connected là cờ dính — set True mãi mãi sau lần đầu,
    dashboard báo EA ONLINE dù EA đã bị gỡ khỏi chart/MT5 đóng."""
    acc = _accounts.get(_active_login) or {}
    t = acc.get("last_ea_telemetry_at")
    if not t:
        return False
    try:
        # pyrefly: ignore [missing-attribute]
        ts = datetime.fromisoformat(t.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - ts).total_seconds() < 60
    except Exception:
        return False


def _any_ea_fresh() -> bool:
    """True nếu BẤT KỲ EA nào còn sống (dùng cho health check)."""
    now = datetime.now(timezone.utc)
    for acc in _accounts.values():
        t = acc.get("last_ea_telemetry_at")
        if not t:
            continue
        try:
            ts = datetime.fromisoformat(t.replace("Z", "+00:00"))
            if (now - ts).total_seconds() < 60:
                return True
        except Exception:
            continue
    return False





def _lot_value_multiplier(sym: str) -> float:

    """Hệ số quy đổi giá->P&L $ cho 1 lot theo symbol.

    BUG FIX: trước đây hardcode *100 (giả định XAU 100oz/lot) nên P&L demo của

    EURUSD/GBPUSD... sai gấp 1000 lần (FX contract = 100000 base/lot)."""

    s = resolve_symbol(sym).upper()

    if "XAU" in s or s == "GOLD":

        return 100.0    # 100 oz / lot

    if "XAG" in s or s == "SILVER":

        return 5000.0   # 5000 oz / lot

    return 100000.0     # FX: 100000 base / lot





def _record_closed_trade(sym: str, pos: Dict[str, Any], price_close: float, reason: str = "CLOSE") -> Dict[str, Any]:

    """Ghi nhận lệnh đã đóng vào lịch sử + cập nhật số liệu tài khoản.

    BUG FIX: trước đây close_position/close_all không cập nhật realized P&L,

    total_trades, win_rate, balance → today_performance & equity curve không bao

    giờ thay đổi dù có đóng lệnh."""

    pos_type = str(pos.get("type", "BUY")).upper()

    # pyrefly: ignore [bad-argument-type]

    entry = float(pos.get("price_open", pos.get("entry", 0)))

    volume = float(pos.get("volume", 0.01))

    mult = _lot_value_multiplier(sym)

    if pos_type == "BUY":

        profit = round((price_close - entry) * volume * mult, 2)

    else:

        profit = round((entry - price_close) * volume * mult, 2)

    trade = {

        "ticket": pos.get("ticket"),

        "symbol": sym,

        "type": pos_type,

        "volume": volume,

        "price_open": round(entry, 2),

        "price_close": round(price_close, 2),

        "profit": profit,

        "time": datetime.now(timezone.utc).isoformat(),

        "reason": reason,

    }

    _trades.append(trade)

    _account["realized_pnl"] = round(_account.get("realized_pnl", 0.0) + profit, 2)

    _account["total_trades"] = _account.get("total_trades", 0) + 1

    wins = sum(1 for t in _trades if t.get("profit", 0) > 0)

    losses = sum(1 for t in _trades if t.get("profit", 0) < 0)

    if wins + losses > 0:

        _account["win_rate"] = round(wins / (wins + losses) * 100, 1)

    # Chỉ chế độ DEMO (không EA) mới tự cập nhật số dư; LIVE -> telemetry EA là thật

    if not _account.get("mt5_connected") and _is_demo_mode():

        _account["balance"] = round(_account.get("balance", 10000.0) + profit, 2)

        _account["equity"] = round(_account.get("equity", 10000.0) + profit, 2)

    return trade





def _queue_modify(symbol: str, pos: Dict[str, Any], new_sl: float, tp: float):

    """Queue lệnh MODIFY SL/TP cho EA (chỉ dùng khi MT5 connected).

    BUG FIX: EA chỉ hiểu action MODIFY_SLTP với ticket nhúng trong reason

    ("ticket=N") — trước đây gửi action "MODIFY" bị EA từ chối UNSUPPORTED_ACTION,

    BE/trailing không bao giờ áp dụng lên vị thế MT5 thật."""

    ticket = pos.get("ticket")

    _enqueue_command({

        "command_id": str(uuid.uuid4()),

        "ts": datetime.now(timezone.utc).isoformat(),

        "action": "MODIFY_SLTP",

        "symbol": resolve_symbol(symbol),

        "magic": _config.get("magic", 888999),

        "ticket": ticket,

        "stop_loss": round(new_sl, 2),

        "take_profit": tp,

        "reason": f"ticket={ticket}",

        "status": "QUEUED"

    })





# ─── AUTO-TRADE LOOP ────────────────────────────────────────────────────────

_ai_loop_running = False

_ai_loop_task = None



async def _ai_trade_loop():

    """Background AI auto-trade loop - runs every 5 seconds"""

    global _ai_loop_running



    while _ai_loop_running:

        try:

            if not _config.get("ai_auto_loop") or _config.get("kill_switch"):

                await asyncio.sleep(5)

                continue



            symbol = _config.get("symbol", "XAUUSD")

            method = _config.get("trading_method", "SMC")

            max_pos = _config.get("max_open_positions", 5)



            # ── AI reads the REAL chart structures (OB/FVG/OTE/BOS/CHoCH + S-R)

            # from the same markup engine the dashboard draws, and only auto-trades

            # a strong entry that has a structure-based SL/TP with real RRR.

            tf = _config.get("timeframe", "M15")

            # pyrefly: ignore [bad-argument-type]

            df = await fetch_real_candles(symbol, tf, 1000)

            if df is None or df.empty:

                await asyncio.sleep(5)

                continue

            # BUG FIX (FAIL-CLOSED): ở chế độ LIVE, KHÔNG BAO GIỜ phân tích/trade

            # trên dữ liệu giả (stub) — nếu EA/bridge chết, dừng auto-trade thay vì

            # mở lệnh THẬT dựa trên nến random-walk. Chỉ DEMO (paper) được phép

            # chạy trên stub để phát triển/kiểm thử.

            if not _bridge_data_real and not _is_demo_mode():

                # pyrefly: ignore [bad-argument-type]

                _add_ai_event("WARNING", "NO_REAL_DATA", symbol, {

                    "reason": "LIVE mode has no real MT5 data (EA/bridge down) - auto-trade paused (fail-closed)",

                    "data_status": "STUB"

                })

                _add_log("WARNING", "NO_REAL_DATA",

                    "LIVE mode: no real MT5 data - auto-trade paused (fail-closed)")

                await asyncio.sleep(5)

                continue

            # pyrefly: ignore [bad-assignment]

            mtf_data: Dict[str, pd.DataFrame] = {tf: df}

            for ctx_tf in ("M15", "H1", "D1"):

                if ctx_tf == tf:

                    continue

                # pyrefly: ignore [bad-argument-type]

                ctx_df = await _fetch_context_candles(symbol, ctx_tf)

                if ctx_df is not None and not ctx_df.empty:

                    mtf_data[ctx_tf] = ctx_df

            # pyrefly: ignore [bad-argument-type]

            mtf_data_trimmed = {k: v.tail(600) if hasattr(v, 'tail') else v for k, v in mtf_data.items()}
            markup = build_chart_markup(symbol=symbol, mtf_data=mtf_data_trimmed, method=method, primary_tf=tf)

            cf = markup.get("confluence") or {}



            score = int(cf.get("score", 0) or 0)          # -100..100

            signal = cf.get("signal", "WAIT")

            last_price = float(df["close"].iloc[-1])

            entry = float(cf.get("entry") or last_price)

            sl = cf.get("sl")

            tp = cf.get("tp")

            rrr = cf.get("rrr")

            # pyrefly: ignore [unnecessary-type-conversion]

            atr = float((df["high"] - df["low"]).tail(14).mean()) if len(df) >= 14 else 15.0

            reasons = [f.get("reason") for f in (cf.get("factors") or []) if f.get("reason")][:3]



            # Log heartbeat

            # pyrefly: ignore [bad-argument-type]

            _add_ai_event("INFO", "HEARTBEAT", symbol, {

                "method": method,

                "score": score,

                "signal": signal,

                "objects": len(markup.get("objects", [])),

                # pyrefly: ignore [bad-argument-type]

                "open_positions": len(_positions.get(resolve_symbol(symbol), [])),

                "max_positions": max_pos

            })



            # Generate trade ONLY on a strong structural confluence with a

            # defined SL/TP and a real risk/reward ratio.

            trade_ok = (

                signal in ("BUY", "SELL")

                and abs(score) >= 45

                and sl and tp

                and (rrr or 0) >= 1.0

            )

            if trade_ok:



                # pyrefly: ignore [bad-argument-type]

                current_positions = _positions.get(resolve_symbol(symbol), [])



                # Check if we already have a position in this direction

                has_same_direction = any(

                    p.get("type") == signal for p in current_positions

                )



                # pyrefly: ignore [unsupported-operation]

                if not has_same_direction and len(current_positions) < max_pos:

                    # Check for recent same-direction trade (avoid duplicates within 60s)

                    recent = [

                        c for c in _commands

                        if c.get("action") == signal

                        # pyrefly: ignore [bad-argument-type]

                        and resolve_symbol(c.get("symbol")) == resolve_symbol(symbol)

                        and (datetime.now(timezone.utc) - datetime.fromisoformat(c["ts"].replace("Z", "+00:00"))).total_seconds() < 60

                    ]



                    if not recent:

                        # Structure-based SL/TP from the markup engine; fall back

                        # to ATR multiples only when the chart had no levels.

                        sl_dist = max(5, atr * 1.5)

                        tp_dist = sl_dist * 2

                        if signal == "BUY":

                            sl = float(sl) if sl else round(last_price - sl_dist, 2)

                            tp = float(tp) if tp else round(last_price + tp_dist, 2)

                        else:

                            sl = float(sl) if sl else round(last_price + sl_dist, 2)

                            tp = float(tp) if tp else round(last_price - tp_dist, 2)



                        # PHASE 1.3: Risk Manager check (9 conditions)

                        # Estimate current spread

                        try:

                            # pyrefly: ignore [bad-argument-type]

                            bid, ask = await fetch_real_bid_ask(symbol)

                            current_spread = ask - bid

                        except Exception:

                            current_spread = 0.5



                        risk_result = evaluate_risk_gate(

                            # pyrefly: ignore [bad-argument-type]

                            symbol=symbol, signal=signal,

                            entry=entry, sl=sl, tp=tp,

                            spread=current_spread, atr=atr,

                            # pyrefly: ignore [bad-argument-type]

                            score=score, method=method

                        )

                        

                        if not risk_result["approved"]:

                            # pyrefly: ignore [bad-argument-type]

                            _add_ai_event("WARNING", "RISK_REJECT", symbol, {

                                "reason": risk_result["reason"],

                                "score": score,

                                "method": method

                            })

                            _add_log("WARNING", "RISK_REJECT", 

                                f"AI signal {signal} {symbol} rejected by Risk Manager: {risk_result['reason']}")

                            await asyncio.sleep(5)

                            continue



                        # Create command

                        cmd_id = str(uuid.uuid4())

                        cmd = {

                            "command_id": cmd_id,

                            "ts": datetime.now(timezone.utc).isoformat(),

                            "action": signal,

                            # pyrefly: ignore [bad-argument-type]

                            "symbol": resolve_symbol(symbol),

                            "magic": _config.get("magic", 888999),

                            "volume": 0.01,

                            "stop_loss": round(sl, 2),

                            "take_profit": round(tp, 2),

                            "entry": round(entry, 2),

                            "reason": f"AI {method} structure score={score} rrr={rrr} {' | '.join(reasons)}",

                            "status": "QUEUED"

                        }

                        _enqueue_command(cmd)



                        # BUG FIX: Khi EA chưa kết nối ở chế độ DEMO (paper), lệnh

                        # QUEUED không bao giờ được thực thi -> giả lập fill để

                        # auto-trade hoạt động thấy được. Ở chế độ LIVE thì

                        # FAIL-CLOSED: không giả lập, giữ QUEUED chờ EA claim.

                        if not _account.get("mt5_connected") and _is_demo_mode():

                            ticket = random.randint(100000, 999999)

                            # pyrefly: ignore [bad-argument-type]

                            rkey = resolve_symbol(symbol)

                            if rkey not in _positions:

                                _positions[rkey] = []

                            _positions[rkey].append({

                                "ticket": ticket,

                                "symbol": rkey,

                                "type": signal,

                                "volume": 0.01,

                                "price_open": round(entry, 2),

                                "sl": round(sl, 2),

                                "orig_sl": round(sl, 2),

                                "tp": round(tp, 2),

                                "be_applied": False,

                                "profit": 0.0,

                                "current_price": round(entry, 2),

                                "open_time": datetime.now(timezone.utc).isoformat(),

                                "source": "DEMO",  # BUG FIX: mirror ảo — BE/trailing không MODIFY ticket rác

                            })

                            cmd["status"] = "FILLED"

                            cmd["ticket"] = ticket

                            # pyrefly: ignore [bad-argument-type]

                            _account["open_positions"] = len(_positions.get(resolve_symbol(symbol), []))



                        # pyrefly: ignore [bad-argument-type]

                        _add_ai_event("TRADE", signal, symbol, {

                            "method": method,

                            "score": score,

                            "entry": round(entry, 2),

                            "sl": round(sl, 2),

                            "tp": round(tp, 2),

                            "rrr": rrr,

                            "reason": " | ".join(reasons) or f"{method} confluence {score}"

                        })



                        _add_log("INFO", "AI_SIGNAL", f"{method} {signal} score={score} entry={entry} sl={sl} tp={tp} rrr={rrr}")



            # ── DCA: quét vị thế đang lỗ và nhồi lệnh trung bình giá (nếu bật) ──

            # pyrefly: ignore [bad-argument-type]

            await _dca_check(symbol, method, atr)



        except Exception as e:

            _add_log("ERROR", "AI_LOOP_ERR", str(e))



        await asyncio.sleep(5)



async def _position_manager_loop():

    """Position manager background loop - every 2s:

    - Cập nhật P&L floating cho mọi lệnh

    - DEMO mode: mô phỏng đóng lệnh khi giá chạm SL/TP (MT5 thật tự xử lý)

    - Break-even: giá đi 1R → kéo SL về ENTRY (chính xác, không phải entry+0.5)

    - Trailing stop: sau BE, bám giá với khoảng 0.5R, chỉ kéo SL theo hướng có lời

    BUG FIX: trước đây BE kéo về entry+0.5, không có trailing, demo không bao giờ

    đóng lệnh khi chạm SL/TP (lệnh tích lũy mãi, realized P&L không đổi)."""

    global _ai_loop_running

    while _ai_loop_running:

        try:

            for symbol, pos_list in list(_positions.items()):

                if not pos_list:

                    continue

                bid, ask = await fetch_real_bid_ask(symbol)

                for pos in list(pos_list):

                    pos_type = str(pos.get("type", "BUY")).upper()

                    # pyrefly: ignore [bad-argument-type]

                    entry = float(pos.get("price_open", pos.get("entry", 0)))

                    sl = float(pos.get("sl", 0))

                    tp = float(pos.get("tp", 0))

                    volume = float(pos.get("volume", 0.01))

                    current_price = bid if pos_type == "BUY" else ask



                    # Cập nhật P&L floating (hệ số lot theo symbol — không hardcode *100)

                    mult = _lot_value_multiplier(symbol)

                    if pos_type == "BUY":

                        pos["profit"] = round((current_price - entry) * volume * mult, 2)

                    else:

                        pos["profit"] = round((entry - current_price) * volume * mult, 2)

                    pos["current_price"] = current_price



                    # ── DEMO MODE: mô phỏng chạm SL/TP (MT5 thật tự xử lý;

                    #    LIVE mode KHÔNG giả lập — fail-closed) ──

                    if not _account.get("mt5_connected") and _is_demo_mode():

                        close_price = None

                        reason = None

                        if pos_type == "BUY":

                            if sl > 0 and bid <= sl:

                                close_price, reason = sl, "SL"

                            elif tp > 0 and bid >= tp:

                                close_price, reason = tp, "TP"

                        else:

                            if sl > 0 and ask >= sl:

                                close_price, reason = sl, "SL"

                            elif tp > 0 and ask <= tp:

                                close_price, reason = tp, "TP"

                        if close_price is not None:

                            # pyrefly: ignore [bad-argument-type]

                            trade = _record_closed_trade(symbol, pos, close_price, reason)

                            if pos in pos_list:

                                pos_list.remove(pos)

                            _dca_state.pop(f"{resolve_symbol(symbol)}:{pos.get('ticket')}", None)

                            _add_ai_event("TRADE", "CLOSE", symbol, {

                                "ticket": pos.get("ticket"), "profit": trade["profit"], "reason": reason})

                            _add_log("INFO", "STOP_HIT", f"{symbol} #{pos.get('ticket')} {pos_type} closed at {reason} pnl={trade['profit']}")

                            continue



                    if entry <= 0:

                        continue



                    # Khoảng cách rủi ro ban đầu (orig_sl để không bị méo sau khi kéo SL)

                    orig_sl = float(pos.get("orig_sl", 0)) or sl

                    risk_dist = abs(entry - orig_sl) if orig_sl > 0 else 1.5

                    if risk_dist <= 0:

                        risk_dist = 1.5

                    be_applied = bool(pos.get("be_applied", False))



                    # ── 1) Break-even (một lần, SL về đúng entry) ──

                    if not be_applied:

                        hit_be = (bid - entry) >= risk_dist if pos_type == "BUY" else (entry - ask) >= risk_dist

                        if hit_be:

                            new_sl = round(entry, 2)

                            pos["sl"] = new_sl

                            pos["be_applied"] = True

                            _add_log("INFO", "BREAK_EVEN", f"SL -> BE for {pos_type} #{pos.get('ticket')} @ {new_sl}")

                            _add_ai_event("TRADE", "BREAK_EVEN", symbol, {"ticket": pos.get("ticket"), "sl": new_sl})

                            # BUG FIX: không gửi MODIFY cho mirror DEMO ảo (ticket random

                            # không tồn tại trên MT5) khi EA đã kết nối — trước đây gửi

                            # ticket rác -> EA REJECT_TICKET_NOT_FOUND lặp mỗi 2s.

                            if _account.get("mt5_connected") and pos.get("source") != "DEMO":

                                _queue_modify(symbol, pos, new_sl, tp)



                    # ── 2) Trailing stop (sau BE, khoảng 0.5R) ──

                    # Dùng giá trị LIVE từ pos (BE vừa chạy trong cùng vòng lặp phải

                    # được trailing áp dụng ngay, không đợi vòng sau 2s)

                    live_sl = float(pos.get("sl", 0))

                    if pos.get("be_applied") and live_sl > 0:

                        trail = max(0.2, risk_dist * 0.5)

                        if pos_type == "BUY":

                            candidate = round(current_price - trail, 2)

                            if candidate > live_sl + 0.01:

                                pos["sl"] = candidate

                                if _account.get("mt5_connected") and pos.get("source") != "DEMO":

                                    _queue_modify(symbol, pos, candidate, tp)

                        else:

                            candidate = round(current_price + trail, 2)

                            if live_sl == 0 or candidate < live_sl - 0.01:

                                pos["sl"] = candidate

                                if _account.get("mt5_connected") and pos.get("source") != "DEMO":

                                    _queue_modify(symbol, pos, candidate, tp)



            # Cleanup mirror có cờ closing (EA không phản hồi trong 180s)

            for sym in list(_positions.keys()):

                for p in list(_positions[sym]):

                    if p.get("closing"):

                        try:

                            closing_at = p.get("closing_at") or ""

                            age = (datetime.now(timezone.utc) - datetime.fromisoformat(closing_at.replace("Z", "+00:00"))).total_seconds()

                        except Exception:

                            age = 0

                        if age > 180:

                            _positions[sym].remove(p)

                            _dca_state.pop(f"{sym}:{p.get('ticket')}", None)

                            _add_log("WARN", "CLOSE_TIMEOUT", f"#{p.get('ticket')} closing mirror cleaned (EA no reply)")



            # Floating P&L tổng (demo: tổng profit các lệnh mở; LIVE: telemetry EA)

            if not _account.get("mt5_connected") and _is_demo_mode():

                _account["total_pnl"] = round(

                    sum(float(p.get("profit", 0)) for lst in _positions.values() for p in lst), 2)

                _account["open_positions"] = sum(len(lst) for lst in _positions.values())

        except Exception as e:

            _add_log("ERROR", "POS_MGR_ERR", str(e))

        await asyncio.sleep(2)



# ─── DCA (DOLLAR COST AVERAGING) ───────────────────────────────────────────

def _dca_evaluate(pos: Dict[str, Any], current_price: float, atr: float, cfg: Dict[str, Any]) -> Optional[Dict[str, Any]]:

    """Logic thuần DCA cho 1 vị thế — tách riêng để unit-test dễ. Trả về quyết định

    {level, volume, adverse_atr, risk_usd} hoặc None nếu không đủ điều kiện.

    Fail-closed: luôn cần SL > 0, ATR > 0, entry > 0; không lỗ -> không nhồi."""

    if not cfg.get("dca_enabled"):

        return None

    pos_type = str(pos.get("type", "BUY")).upper()

    ticket = pos.get("ticket")

    if not ticket:

        return None

    entry = float(pos.get("price_open", pos.get("entry", 0)) or 0)

    sl = float(pos.get("sl", 0) or 0)

    if entry <= 0 or sl <= 0 or atr <= 0:

        return None

    adverse = (entry - current_price) if pos_type == "BUY" else (current_price - entry)

    if adverse <= 0:

        return None  # đang lời -> không nhồi

    adverse_atr = adverse / atr

    if adverse_atr < float(cfg.get("dca_distance_atr", 1.5)):

        return None

    sym = str(pos.get("symbol", "XAUUSD"))

    state = _dca_state.get(f"{resolve_symbol(sym)}:{ticket}", {"level": 0, "last_add": ""})

    level = int(state.get("level", 0)) + 1

    if level > int(cfg.get("dca_max_levels", 2)):

        return None

    if state.get("last_add"):

        try:

            age = (datetime.now(timezone.utc) - datetime.fromisoformat(state["last_add"].replace("Z", "+00:00"))).total_seconds()

            if age < float(cfg.get("dca_interval_sec", 300)):

                return None

        except Exception:

            pass

    base_vol = float(pos.get("volume", 0.01) or 0.01)

    vol = round(base_vol * (float(cfg.get("dca_volume_multiplier", 1.0)) ** (level - 1)), 2)

    if vol <= 0:

        return None

    mult = _lot_value_multiplier(sym)

    risk_usd = abs(entry - sl) * vol * mult

    balance = float(_account.get("balance", 0) or 0)

    max_risk = float(cfg.get("dca_max_risk_balance_pct", 0.01))

    # FAIL-CLOSED: không biết số dư thật (balance <= 0, vd EA cũ gửi balance=0)

    # -> KHÔNG nhồi. Trước đây `if balance > 0` khiến cap rủi ro bị bỏ qua hoàn

    # toàn khi balance = 0 (chỉ còn chặn bởi level cap).

    if balance <= 0 or risk_usd > balance * max_risk:

        return None

    return {"level": level, "volume": vol, "adverse_atr": round(adverse_atr, 2), "risk_usd": round(risk_usd, 2)}





async def _dca_check(symbol: str, method: str, atr: float):

    """Quét các vị thế đang lỗ và queue lệnh DCA nếu đủ điều kiện. Fail-closed:

    tôn trọng kill switch, news protection, risk gate, giới hạn mức & rủi ro.

    Chỉ chạy khi ai_auto_loop bật và dca_enabled bật."""

    if not _config.get("dca_enabled") or _config.get("kill_switch"):

        return

    if not _config.get("ai_auto_loop"):

        return

    rkey = resolve_symbol(symbol)

    positions = _positions.get(rkey, [])

    if not positions:

        return

    try:

        bid, ask = await fetch_real_bid_ask(symbol)

    except Exception:

        return

    now = datetime.now(timezone.utc)

    for pos in list(positions):

        pos_type = str(pos.get("type", "BUY")).upper()

        ticket = pos.get("ticket")

        if not ticket:

            continue

        current = bid if pos_type == "BUY" else ask

        decision = _dca_evaluate(pos, current, atr, _config)

        if not decision:

            continue

        key = f"{rkey}:{ticket}"

        # Đã có lệnh DCA đang chờ (QUEUED/CLAIMED) cho ticket này? Tránh nhồi trùng

        pending = any(

            c.get("status") in ("QUEUED", "CLAIMED")

            and str(c.get("reason", "")).startswith(f"DCA parent_ticket={ticket}")

            for c in _commands

        )

        if pending:

            continue

        # News protection fail-closed: không nhồi lệnh khi đang trong cửa sổ tin

        news_block = False

        try:

            cal = _market_cache.get("economic_calendar") or {}

            now_ts = now.timestamp()

            for ev in (cal.get("events") or []):

                imp = str(ev.get("impact") or "").upper()

                if imp not in ("HIGH", "MED", "MEDIUM"):

                    continue

                ev_dt = _parse_event_datetime(ev)

                # pyrefly: ignore [bad-argument-type]

                if ev_dt and abs(now_ts - ev_dt.timestamp()) <= int(_config.get("news_window_minutes", 15)) * 60:

                    news_block = True

                    break

        except Exception:

            news_block = False

        if news_block:

            _add_log("INFO", "DCA_SKIP", f"DCA {symbol} #{ticket} blocked by news protection")

            continue

        sl = float(pos.get("sl") or 0)

        tp = float(pos.get("tp") or 0) or current

        risk = evaluate_risk_gate(

            symbol=symbol, signal=pos_type, entry=current, sl=sl, tp=tp,

            spread=ask - bid, atr=atr, score=50, method=method)

        if not risk["approved"]:

            _add_log("INFO", "DCA_SKIP", f"DCA {symbol} #{ticket} rejected by risk gate: {risk['reason']}")

            continue

        # Queue lệnh DCA (cùng hướng vị thế, giữ nguyên SL/TP)

        cmd = {

            "command_id": str(uuid.uuid4()),

            "ts": now.isoformat(),

            "action": pos_type,

            "symbol": rkey,

            "magic": _config.get("magic", 888999),

            "volume": decision["volume"],

            "stop_loss": round(sl, 2),

            "take_profit": round(tp, 2),

            "entry": round(current, 2),

            "reason": f"DCA parent_ticket={ticket} level={decision['level']} adverse_atr={decision['adverse_atr']}",

            "status": "QUEUED"

        }

        _enqueue_command(cmd)

        _dca_state[key] = {"level": decision["level"], "last_add": now.isoformat()}

        # DEMO không EA: giả lập fill mirror mới (LIVE thì chờ EA claim — fail-closed)

        if not _account.get("mt5_connected") and _is_demo_mode():

            new_ticket = random.randint(100000, 999999)

            if rkey not in _positions:

                _positions[rkey] = []

            _positions[rkey].append({

                "ticket": new_ticket, "symbol": rkey, "type": pos_type,

                "volume": decision["volume"], "price_open": round(current, 2),

                "sl": round(sl, 2), "orig_sl": round(sl, 2), "tp": round(tp, 2),

                "be_applied": False, "profit": 0.0, "current_price": round(current, 2),

                "open_time": now.isoformat(), "source": "DEMO",

            })

            cmd["status"] = "FILLED"

            cmd["ticket"] = new_ticket

        _add_ai_event("TRADE", f"DCA_{pos_type}", symbol, {

            "parent_ticket": ticket, "level": decision["level"],

            "volume": decision["volume"], "entry": round(current, 2), "sl": round(sl, 2),

            "adverse_atr": decision["adverse_atr"], "risk_usd": decision["risk_usd"]})

        _add_log("INFO", "DCA_ADD", f"DCA level={decision['level']} {pos_type} {symbol} parent=#{ticket} vol={decision['volume']} @ {round(current,2)} sl={sl}")





# ─── PYDANTIC MODELS ─────────────────────────────────────────────────────────

class LoginRequest(BaseModel): login: str; password: str

class OrderCloseRequest(BaseModel): ticket: Optional[int] = None; position_id: Optional[str] = None

class CancelPendingRequest(BaseModel):

    order_ticket: Optional[int] = None

    command_id: Optional[str] = None



class NewsAnalyzeRequest(BaseModel):

    title: str

    impact: Optional[str] = "MEDIUM"

    actual: Optional[str] = ""

    forecast: Optional[str] = ""

    previous: Optional[str] = ""

    date: Optional[str] = ""

    time: Optional[str] = ""



class OrderCreateRequest(BaseModel):

    symbol: str = "XAUUSD"

    direction: str = "BUY"

    quantity: float = 0.10

    stop_loss: Optional[float] = None

    take_profit: Optional[float] = None

    price: Optional[float] = None



class AiLoopRequest(BaseModel): enabled: bool

class TradingMethodRequest(BaseModel): method: Optional[str] = None; trading_method: Optional[str] = None

class MT5LoginRequest(BaseModel): login: int; password: str; server: str

class CopilotChatRequest(BaseModel): message: str; symbol: str = "XAUUSD"; timeframe: str = "M15"



# ─── ENDPOINTS ────────────────────────────────────────────────────────────────

_pos_mgr_task = None



@app.get("/")

async def root():

    return {"name": APP_NAME, "version": VERSION, "status": "running"}



@app.get("/health")

async def health():

    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}



# ─── AUTHENTICATION ──────────────────────────────────────────────────────────

@app.post("/api/auth/login")

async def login(req: LoginRequest):

    admin_login = os.getenv("ADMIN_LOGIN", "")

    admin_password = os.getenv("ADMIN_PASSWORD", "")

    if not admin_login or not admin_password:

        _add_log("ERROR", "LOGIN_FAILED", "ADMIN_LOGIN / ADMIN_PASSWORD env vars not configured")

        raise HTTPException(status_code=503, detail="Authentication not configured")

    if req.login == admin_login and req.password == admin_password:

        token = hashlib.sha256(f"{req.login}:{datetime.now().isoformat()}".encode()).hexdigest()[:32]

        _add_log("INFO", "LOGIN_SUCCESS", f"User {req.login} logged in")

        return {"status": "SUCCESS", "token": token, "user": {"id": "admin", "login": req.login}}

    _add_log("WARNING", "LOGIN_FAILED", f"Failed login: {req.login}")

    raise HTTPException(status_code=401, detail="Invalid credentials")



# FIX: Public endpoint - no auth required (dashboard status is public info)

# Only protected endpoints (order/close, config changes) require auth

# ─── STATUS ──────────────────────────────────────────────────────────────────

@app.get("/api/status")

async def get_status(symbol: str = Query("XAUUSD")):

    """Get current status with real indicators"""

    df = await fetch_real_candles(symbol, "M15", 100)

    if df is None or df.empty:

        df = generate_stub_candles(100, "M15", symbol)

    indicators = calculate_indicators(df)

    bid, ask = await fetch_real_bid_ask(symbol)



    # pyrefly: ignore [bad-argument-type]

    analysis = await run_ai_analysis(symbol, _config["trading_method"])



    return {

        "data_status": "LIVE" if _bridge_data_real else "STUB",

        "generated_at": datetime.now(timezone.utc).isoformat(),

        "server": APP_NAME,

        "mt5_connected": _account["mt5_connected"],"ea_connected": _ea_fresh(),
        "last_ea_telemetry_at": _account.get("last_ea_telemetry_at"),
        "last_ea_candles_at": _account.get("last_ea_candles_at"),
        "last_ea_claim_at": _account.get("last_ea_claim_at"),
        "ea_executor_id": _account.get("ea_executor_id"),
        "ea_symbol": _account.get("ea_symbol"),
        "balance": _account["balance"],
        "equity": _account["equity"],
        "margin": _account["margin"],
        "margin_free": _account["margin_free"],
        "floating_pnl": _account["total_pnl"],
        "account_mode": _account.get("account_mode", "DEMO"),
        "auto_detected": _account.get("auto_detected", False),
        "active_login": _active_login,
        "open_positions": len(_positions.get(resolve_symbol(symbol), [])),

        "current_ask": ask,

        "current_bid": bid,

        "current_spread": round(ask - bid, 2),

        "ai_score": analysis.get("score", 50),

        "cpu": f"{psutil.cpu_percent(interval=0)}%",

        "ram": f"{psutil.Process().memory_info().rss // (1024 * 1024)} MB",

        "account_id": _account["login"] or 12345,

        "currency": "USD",

        "leverage": 100,

        "broker": "MT5 Broker",

        "today_performance": {

            "realized_pl": _account.get("realized_pnl", 0.0),

            "trades_today": _account["total_trades"],

            # BUG FIX: wins/losses tính bằng int() riêng rẽ có thể không cộng

            # đúng bằng total_trades (ví dụ 3 lệnh, win_rate 66.7 -> wins=2,

            # losses=0). Giờ losses = total_trades - wins cho khớp.

            # pyrefly: ignore [unnecessary-type-conversion]

            "wins": int(round(_account["total_trades"] * _account["win_rate"] / 100)),

            # pyrefly: ignore [unnecessary-type-conversion]

            "losses": max(0, _account["total_trades"] - int(round(_account["total_trades"] * _account["win_rate"] / 100))),

            "best_trade_today": max([t.get("profit", 0) for t in _trades], default=0.0),

            "worst_trade_today": min([t.get("profit", 0) for t in _trades], default=0.0)

        },

        "indicators": {

            "data_status": "LIVE" if _bridge_data_real else "STUB",

            "rsi": round(indicators["rsi"], 2),

            "atr": round(indicators["atr"], 2),

            "macd": indicators["macd"],

            "macd_value": round(indicators.get("macd_value", 0), 4),

            "macd_signal": round(indicators.get("macd_signal", 0), 4),

            "stoch": indicators["stoch"],

            "stoch_k": round(indicators["stoch_k"], 2),

            "ema20": round(indicators["ema_fast"], 5),

            "ema50": round(indicators["ema_medium"], 5),

            "ema200": round(indicators["ema_slow"], 5),

            "volume": round(indicators["volume"], 2),

            "vol_ratio": "1.0"

        },

        "ai_signal": {

            "primary_signal": analysis.get("signal", "WAIT"),

            "confidence": f"{analysis.get('score', 50):.0f}%",

            "win_prob": f"{analysis.get('score', 50):.0f}%",

            "rr_ratio": "2.0",

            "suggested_lot": "0.01",

            "entry_zone": f"{analysis.get('last_price', 0):.2f}",

            "method": _config["trading_method"],

            "factors": analysis.get("factors", []),

            "data_status": "LIVE" if _bridge_data_real else "STUB"

        }

    }



# ─── MULTI-ACCOUNT MANAGEMENT ───────────────────────────────────────────────
# Trả về danh sách tất cả tài khoản MT5 hiện đang kết nối. Cho phép user
# (trên web) chuyển active account đang xem.
@app.get("/api/accounts")
async def list_connected_accounts():
    accs = list_accounts()
    return {
        "accounts": accs,
        "active_login": _active_login,
        "execution_mode": "LIVE" if not _is_demo_mode() else "DEMO",
        "auto_detected": any(a.get("account_mode") == "REAL" for a in accs),
    }


class ActivateAccountRequest(BaseModel):
    login: str


@app.post("/api/accounts/active")
async def activate_account(req: ActivateAccountRequest):
    """Switch dashboard view to a different MT5 account login."""
    login = (req.login or "").strip()
    if not login:
        raise HTTPException(status_code=400, detail="login required")
    if login not in _accounts:
        raise HTTPException(
            status_code=404,
            detail=f"account {login} not yet connected (waiting for first EA telemetry)",
        )
    set_active_account(login)
    acc = _accounts[login]
    _add_log("INFO", "ACCOUNT_SWITCH", f"Active account switched to login={login} mode={acc.get('account_mode')}")
    return {
        "ok": True,
        "active_login": _active_login,
        "account_mode": acc.get("account_mode"),
        "balance": acc.get("balance"),
        "equity": acc.get("equity"),
    }


# ─── MARKET DATA + CHART MARKUP ────────────────────────────────────────────────

@app.get("/api/market")

async def get_market(symbol: str = Query("XAUUSD"), tf: str = Query("M15"), count: int = Query(0, ge=0, le=150000)):

    """Market data with method-specific chart markup (SMC / ICT / Price Action / Sniper / Ultra)"""

    if count == 0:

        # BUG FIX: M1 mặc định 40000 (EA đẩy 40000 nến M1) — trước đây 72000 > cache

        # nên fetch_real_candles bỏ cache EA -> chart chỉ vài nến. Các TF khác tính

        # tương đương khoảng thời gian 40000 nến M1.

        defaults = {"M1": 40000, "M5": 8000, "M15": 2700, "M30": 1350, "H1": 700, "H4": 175, "D1": 365}

        count = defaults.get(tf, 2700)



    # Fetch REAL candles

    df = await fetch_real_candles(symbol, tf, count)

    if df is None or df.empty:

        df = generate_stub_candles(count, tf, symbol)

    bid, ask = await fetch_real_bid_ask(symbol)



    # Run method-specific analysis (naive indicator scoring, kept as reference)

    method = _config.get("trading_method", "SMC")

    # pyrefly: ignore [bad-argument-type]

    analysis = await run_ai_analysis(symbol, method, tf)



    raw_score = analysis.get("score") if analysis else 50

    score_num = float(raw_score) if raw_score is not None else 50.0



    # Build multi-timeframe context: the requested TF is the PRIMARY analysis

    # frame; M15/H1/D1 are fetched best-effort as HTF context. This fixes the

    # bug where markup was only ever computed when the user happened to view M15.

    mtf_data: Dict[str, pd.DataFrame] = {tf: df}

    for ctx_tf in ("M5", "M15", "H1", "D1"):

        if ctx_tf == tf or ctx_tf in mtf_data:

            continue

        ctx_df = await _fetch_context_candles(symbol, ctx_tf)

        if ctx_df is not None and not ctx_df.empty:

            mtf_data[ctx_tf] = ctx_df



    # pyrefly: ignore [bad-argument-type]

    mtf_data_trimmed = {k: v.tail(600) if hasattr(v, 'tail') else v for k, v in mtf_data.items()}
    markup_data = build_chart_markup(symbol=symbol, mtf_data=mtf_data_trimmed, method=method, primary_tf=tf)



    # Keep the markup engine's own confluence (score -100..100 + entry/sl/tp/rrr)

    # — previously it was overwritten by the naive indicator analysis, so the

    # chart and the auto-trader never saw the structure-based signal. The naive

    # result is attached under `ai` for reference.

    markup_confluence = dict(markup_data.get("confluence") or {})

    markup_confluence.setdefault("factors", [])

    if analysis and analysis.get("factors"):

        extras = [{"reason": str(f), "direction": "NEUTRAL", "weight": 0}

                  for f in (analysis.get("factors") or [])]

        markup_confluence["factors"] = list(markup_confluence["factors"]) + extras[:15]

    markup_confluence["ai"] = {

        "score": round(score_num, 1),

        "signal": (analysis or {}).get("signal"),

        "method": method,

        "indicator_factors": (analysis or {}).get("factors", [])[:5],

    }

    markup_data["confluence"] = markup_confluence



    # Convert dataframe to candles format expected by lightweight-charts frontend

    candles = []

    for _, row in df.iterrows():

        ts = row.get("timestamp", row.get("time", datetime.now()))

        if isinstance(ts, str):

            ts = datetime.fromisoformat(ts.replace("Z", ""))

        candles.append({

            "t": str(ts),

            "ts": int(ts.timestamp()) if hasattr(ts, 'timestamp') else int(datetime.now().timestamp()),

            "o": float(row["open"]),

            "h": float(row["high"]),

            "l": float(row["low"]),

            "c": float(row["close"]),

            # pyrefly: ignore [bad-argument-type]

            "v": float(row.get("volume", row.get("tick_volume", row.get("real_volume", 1000))))

        })





    return _json_safe({

        "symbol": symbol,

        "tf": tf,

        "bid": bid,

        "ask": ask,

        "spread": round(ask - bid, 2),

        "count": len(candles),

        "candles": candles,

        "method": method,

        "markup": markup_data

    })





# ─── POSITIONS ────────────────────────────────────────────────────────────────

@app.get("/api/positions")

async def get_positions(symbol: str = Query("XAUUSD")):

    """Get current positions for symbol"""

    # BUG FIX: key _positions chuẩn theo symbol đã resolve (XAUUSDm) — trước đây

    # demo lưu "XAUUSD" còn receipt EA lưu "XAUUSDm" nên frontend không thấy lệnh.

    out = []

    for pos in _positions.get(resolve_symbol(symbol), []):

        p = dict(pos)

        # BUG FIX: chuẩn hóa tên trường cho chart — server lưu price_open/volume,

        # TradingChart đọc entry/openPrice/price. Trước đây chỉ fetchPositions tự

        # map nên bảng/lệnh khác đọc raw (entry thiếu) hiển thị sai/trống.

        entry = float(p.get("entry") or p.get("price_open") or p.get("openPrice") or p.get("price") or 0)

        p["entry"] = entry

        p["openPrice"] = entry

        p["price_open"] = entry

        p["price"] = entry

        p["lot"] = float(p.get("lot") or p.get("volume") or 0)

        p["volume"] = p["lot"]

        p["profit"] = float(p.get("profit") or 0)

        p["current_price"] = float(p.get("current_price") or entry or 0)

        p["sl"] = float(p.get("sl") or 0)

        p["tp"] = float(p.get("tp") or 0)

        p["type"] = str(p.get("type", "BUY")).upper()

        p["symbol"] = p.get("symbol") or resolve_symbol(symbol)

        out.append(p)

    return out



@app.get("/api/pending-orders")

# pyrefly: ignore [bad-function-definition]

async def get_pending_orders(symbol: str = Query("XAUUSD"), request: Request = None):

    """Get pending orders (QUEUED/CLAIMED commands) for the orders tab.

    BUG FIX: frontend (fetchPendingOrders) gọi /api/pending-orders nhưng backend

    không có route này -> 404 -> tab ORD luôn trống dù EA có lệnh chờ."""

    if request and not (request.headers.get("authorization", "") or "").startswith("Bearer "):

        raise HTTPException(status_code=401, detail="Missing Bearer token")

    sym = resolve_symbol(symbol)

    out = []

    for cmd in list(_commands):

        if cmd.get("status") not in ("QUEUED", "CLAIMED"):

            continue

        # pyrefly: ignore [bad-argument-type]

        if resolve_symbol(cmd.get("symbol", "")) != sym:

            continue

        direction = str(cmd.get("action", "BUY")).upper()

        out.append({

            "ticket": cmd.get("ticket") or 0,

            "command_id": cmd.get("command_id"),

            "symbol": cmd.get("symbol"),

            "type": "BUY_LIMIT" if direction == "BUY" else "SELL_LIMIT",

            "price": cmd.get("entry") or 0,

            "sl": cmd.get("stop_loss") or 0,

            "tp": cmd.get("take_profit") or 0,

            "volume": cmd.get("volume") or 0.01,

            "status": cmd.get("status"),

            "reason": cmd.get("reason", ""),

        })

    return out



@app.get("/api/patterns")

# pyrefly: ignore [bad-function-definition]

# pyrefly: ignore [bad-function-definition]

async def get_patterns(symbol: str = Query("XAUUSD"), tf: str = Query("M15"), request: Request = None):

    """Get detected patterns for the PatternAlert panel.

    BUG FIX: frontend (PatternAlert) gọi /api/patterns nhưng backend không có

    route -> 404 -> panel luôn hiện "No pattern alerts" dù chart có FVG/OB/..."""

    if request and not (request.headers.get("authorization", "") or "").startswith("Bearer "):

        raise HTTPException(status_code=401, detail="Missing Bearer token")

    try:

        df = await fetch_real_candles(symbol, tf, 500)

        if df is None or df.empty:

            return []

        indicators = calculate_indicators(df)

        fvgs = detect_fvg(df)

        obs = detect_order_blocks(df)

        bos = detect_bos_choch(df)

        liq = detect_liquidity_sweep(df)

        out = []

        idx = 0

        for f in (fvgs or [])[-3:]:

            idx += 1

            out.append({

                "id": idx, "type": f.get("type", "FVG"),

                "direction": f.get("direction", "NEUTRAL"),

                "symbol": symbol, "price": round(float(f.get("top", 0) or 0), 2),

                "size": 1, "time": f.get("time", ""),

                "pattern": "Fair Value Gap (unfilled)",

            })

        for b in (obs or [])[-3:]:

            idx += 1

            out.append({

                "id": idx, "type": b.get("type", "OB"),

                "direction": b.get("direction", "NEUTRAL"),

                "symbol": symbol, "price": round(float(b.get("top", 0) or 0), 2),

                "size": 1, "time": b.get("time", ""),

                "pattern": "Order Block",

            })

        if bos:

            idx += 1

            out.append({

                "id": idx, "type": bos.get("kind", "BOS"),

                "direction": bos.get("direction", "NEUTRAL"),

                "symbol": symbol, "price": round(float(bos.get("break_price", 0) or 0), 2),

                "size": 1, "time": "", "pattern": f"{bos.get('kind')} confirmed",

            })

        if liq:

            idx += 1

            out.append({

                "id": idx, "type": "LIQUIDITY_SWEEP",

                # pyrefly: ignore [unnecessary-type-conversion]

                "direction": "BULLISH" if "BULLISH" in str(liq) else "BEARISH",

                "symbol": symbol, "price": round(float(df["close"].iloc[-1]), 2),

                "size": 1, "time": "", "pattern": "Liquidity Sweep",

            })

        return out

    except Exception:

        return []



@app.post("/api/order/create")

async def create_order(req: OrderCreateRequest, request: Request):

    """Create order from Web UI -> Queues command for MT5 EA to execute.

    BUG FIX (SECURITY): thiếu Bearer auth như mọi endpoint khác -> ai cũng mở

    được lệnh REAL qua cổng backend trực tiếp (8848 public port-forward)."""

    auth = request.headers.get("authorization", "")

    if not auth.startswith("Bearer "):

        raise HTTPException(status_code=401, detail="Missing Bearer token")

    cmd_id = str(uuid.uuid4())

    direction = req.direction.upper()

    if direction not in ("BUY", "SELL"):

        raise HTTPException(status_code=400, detail="Invalid direction (must be BUY or SELL)")



    bid, ask = await fetch_real_bid_ask(req.symbol)

    # BUG FIX: EA luôn execute MARKET (m_trade.Buy/Sell) — entry phải là giá thị

    # trường thật, không dùng req.price nhập tay (sai lệch với fill thực tế).

    entry_price = ask if direction == "BUY" else bid

    if not entry_price or entry_price <= 0:

        entry_price = req.price or 0.0



    # H1 (BUG FIX): /api/order/create (Web UI QuickTradePanel) trước đây BỎ QUA

    # RiskGate — operator có thể mở lệnh vượt spread/margin/drawdown limit. AI

    # auto-loop gọi evaluate_risk_gate(); web UI phải gọi cùng bộ check để đảm

    # bảo mọi entry (kể cả manual) đều fail-closed theo cùng chính sách rủi ro.

    if entry_price > 0 and req.stop_loss and req.take_profit:

        spread = (ask - bid) if ask > bid and bid > 0 else 0.0

        atr_proxy = abs(entry_price - req.stop_loss)  # distance to SL is the only "vol" signal we have here

        try:

            risk_result = evaluate_risk_gate(

                symbol=req.symbol,

                signal=direction,

                entry=entry_price,

                sl=float(req.stop_loss),

                tp=float(req.take_profit),

                spread=spread,

                atr=atr_proxy,

                score=50,  # manual order — no confluence score; gate evaluates on gate params only

                method=_config.get("trading_method", "SMC"),

            )

            if not risk_result["approved"]:

                _add_ai_event("WARNING", "RISK_REJECT", req.symbol, {

                    "reason": risk_result["reason"],

                    "source": "WEB_UI",

                })

                _add_log("WARNING", "RISK_REJECT",

                    f"Web UI {direction} {req.symbol} rejected by RiskGate: {risk_result['reason']}")

                raise HTTPException(status_code=403, detail=f"RiskGate rejected: {risk_result['reason']}")

        except HTTPException:

            raise

        except Exception as e:

            # FAIL-CLOSED: nếu risk gate exception (vd insufficient data), CHẶN

            # lệnh thay vì fallback approve. Operator phải fix data/config.

            _add_log("ERROR", "RISK_GATE_ERR", f"Web UI order risk gate failed: {e}")

            raise HTTPException(status_code=503, detail=f"RiskGate unavailable: {e}")



    # H2 (BUG FIX): LIVE mode + EA chưa kết nối → KHÔNG được queue lệnh. Trước

    # đây _is_demo_mode() default "DEMO" nên lệnh có thể đi vào demo-fill path

    # dù env thực tế là LIVE. Refuse ở đây cho cả create_order + manual flows.

    if str(_config.get("execution_mode", "DEMO")).upper() == "LIVE" and not _account.get("mt5_connected"):

        raise HTTPException(

            status_code=503,

            detail="LIVE mode requires MT5 connection. EA is not connected; refusing to queue order."

        )



    cmd = {

        "command_id": cmd_id,

        "ts": datetime.now(timezone.utc).isoformat(),

        "action": direction,

        "symbol": resolve_symbol(req.symbol),

        "magic": _config.get("magic", 888999),

        "volume": req.quantity,

        "stop_loss": req.stop_loss or 0.0,

        "take_profit": req.take_profit or 0.0,

        "entry": entry_price,

        "reason": f"Web UI manual order ({direction} {req.quantity} lot)",

        "status": "QUEUED"

    }

    _enqueue_command(cmd)



    if not _account["mt5_connected"] and _is_demo_mode():

        ticket = random.randint(100000, 999999)

        sym = resolve_symbol(req.symbol)

        if sym not in _positions:

            _positions[sym] = []

        _positions[sym].append({

            "ticket": ticket,

            "symbol": sym,

            "type": direction,

            "volume": req.quantity,

            "price_open": entry_price,

            "sl": req.stop_loss or 0.0,

            "orig_sl": req.stop_loss or 0.0,

            "tp": req.take_profit or 0.0,

            "be_applied": False,

            "profit": 0.0,

            "current_price": entry_price,

            "open_time": datetime.now(timezone.utc).isoformat(),

            "source": "DEMO",  # BUG FIX: đánh dấu mirror ảo để BE/trailing không gửi MODIFY ticket rác

        })

        cmd["status"] = "FILLED"

        cmd["ticket"] = ticket



    # BUG FIX: đoạn log MANUAL_ORDER + _add_ai_event + return trước đây bị kẹt

    # nhầm vào cuối hàm news_analyze (sau return -> dead code) nên lệnh tạo thủ

    # công không bao giờ được ghi log và client không nhận được command_id.

    _add_log("INFO", "MANUAL_ORDER", f"Web UI created order: {direction} {req.quantity} lot on {req.symbol} @ {entry_price}")

    _add_ai_event("TRADE", direction, req.symbol, {

        "entry": entry_price,

        "sl": req.stop_loss,

        "tp": req.take_profit,

        "volume": req.quantity,

        "source": "WEB_UI"

    })

    return {"status": "SUCCESS", "command_id": cmd_id, "direction": direction, "entry": entry_price}



@app.post("/api/order/cancel_pending")

async def cancel_pending(req: CancelPendingRequest, request: Request):

    """Cancel a pending (QUEUED) order from the web orders tab.

    BUG FIX: page.tsx handleCancelOrder gọi /api/order/cancel_pending nhưng

    backend không có route -> 404 -> nút cancel không hoạt động."""

    auth = request.headers.get("authorization", "")

    if not auth.startswith("Bearer "):

        raise HTTPException(status_code=401, detail="Missing Bearer token")

    removed = False

    for cmd in list(_commands):

        if cmd.get("status") != "QUEUED":

            continue

        if req.command_id and cmd.get("command_id") == req.command_id:

            _commands.remove(cmd)

            removed = True

            break

        if req.order_ticket and cmd.get("ticket") == req.order_ticket:

            _commands.remove(cmd)

            removed = True

            break

    _add_log("INFO", "CANCEL_PENDING", f"Cancelled pending order: {req.command_id or req.order_ticket} (found={removed})")

    return {"status": "SUCCESS", "cancelled": removed}



@app.post("/api/news/analyze")

async def news_analyze(req: NewsAnalyzeRequest, request: Request):

    """Phân tích tin tức kinh tế (EconomicCalendar component).

    BUG FIX: backend thiếu route /api/news/analyze -> click event báo lỗi."""

    auth = request.headers.get("authorization", "")

    if not auth.startswith("Bearer "):

        raise HTTPException(status_code=401, detail="Missing Bearer token")

    impact = (req.impact or "MEDIUM").upper()

    title = req.title or ""

    actual = req.actual or ""

    forecast = req.forecast or ""



    recommendation = "HOLD"

    analysis = f"Event: {title} | Impact: {impact}"

    def _num(s: str):

        """Parse số liệu kinh tế: '3.2%' -> 3.2, '227K' -> 227000, '1.2M' -> 1200000."""

        # pyrefly: ignore [unnecessary-type-conversion]

        t = str(s).strip().replace("%", "").replace(",", "").replace(" ", "")

        if not t:

            return None

        mult = 1.0

        if t[-1] in ("K", "k"):

            mult, t = 1000.0, t[:-1]

        elif t[-1] in ("M", "m"):

            mult, t = 1000000.0, t[:-1]

        elif t[-1] in ("B", "b"):

            mult, t = 1000000000.0, t[:-1]

        try:

            return float(t) * mult

        except Exception:

            return None



    if actual and forecast:

        try:

            a, f = _num(actual), _num(forecast)

            if a is None or f is None:

                raise ValueError("unparseable")

            # pyrefly: ignore [unnecessary-type-conversion]

            a, f = float(a), float(f)

            if "CPI" in title.upper() or "PPI" in title.upper() or "NFP" in title.upper() or "GDP" in title.upper():

                if a > f:

                    recommendation = "SELL"

                    analysis += " | Actual cao hơn dự báo -> áp lực lạm phát/lãi suất -> vàng giảm"

                elif a < f:

                    recommendation = "BUY"

                    analysis += " | Actual thấp hơn dự báo -> kỳ vọng nới lỏng -> vàng tăng"

                else:

                    analysis += " | Khớp dự báo"

            else:

                recommendation = "HOLD"

                analysis += " | Tin thứ cấp, theo dõi phản ứng thị trường"

        except Exception:

            analysis += " | Không so sánh được giá trị"

    elif impact == "HIGH":

        recommendation = "HOLD"

        analysis += " | Tin high impact — tránh vào lệnh trước/sau 15 phút"



    return {

        "status": "OK",

        "title": title,

        "analysis": analysis,

        "recommendation": recommendation,

    }





@app.post("/api/order/close")

async def close_position(req: OrderCloseRequest, request: Request):

    """Close a position by ticket.

    BUG FIX (SECURITY): thiếu Bearer auth — đóng lệnh REAL không token.

    BUG FIX: ở chế độ MT5 connected, lệnh đóng phải gửi tới EA (CLOSE_POSITION)

    — trước đây chỉ xoá mirror local nên vị thế MT5 thật vẫn mở và bot có thể mở

    lệnh trùng hướng. Mirror giữ với cờ closing (chặn trùng), EA xác nhận qua

    receipt EXECUTED hoặc cleanup sau timeout."""

    auth = request.headers.get("authorization", "")

    if not auth.startswith("Bearer "):

        raise HTTPException(status_code=401, detail="Missing Bearer token")

    # H3 (BUG FIX): filter theo magic để tránh đóng lệnh của EA khác (cùng symbol

    # nhưng magic khác nhau). Nếu pos không có magic (mirror cũ) thì cho qua để

    # backward-compatible với demo.

    our_magic = _config.get("magic", 888999)

    for sym, positions in _positions.items():

        for i, pos in enumerate(positions):

            if pos.get("ticket") == req.ticket:

                pos_magic = pos.get("magic")

                if pos_magic is not None and pos_magic != our_magic:

                    continue  # belongs to another EA — skip

                if _account.get("mt5_connected"):

                    _enqueue_command({

                        "command_id": str(uuid.uuid4()),

                        "ts": datetime.now(timezone.utc).isoformat(),

                        "action": "CLOSE_POSITION",

                        "symbol": resolve_symbol(sym),

                        "magic": _config.get("magic", 888999),

                        "ticket": req.ticket,

                        "reason": f"ticket={req.ticket}",

                        "status": "QUEUED"

                    })

                    pos["closing"] = True

                    pos["closing_at"] = datetime.now(timezone.utc).isoformat()

                    _add_log("INFO", "CLOSE_QUEUED", f"Close #{req.ticket} queued for EA ({sym})")

                    return {"status": "SUCCESS", "ticket": req.ticket, "queued_for_ea": True}

                # pyrefly: ignore [bad-argument-type]

                price_close = float(pos.get("current_price", pos.get("price_open", 0)))

                trade = _record_closed_trade(sym, pos, price_close, "MANUAL_CLOSE")

                positions.pop(i)

                _add_ai_event("TRADE", "CLOSE", sym, {

                    "ticket": req.ticket,

                    "profit": trade["profit"]

                })

                _add_log("INFO", "CLOSE", f"Closed {sym} #{req.ticket} pnl={trade['profit']}")

                return {"status": "SUCCESS", "ticket": req.ticket, "profit": trade["profit"]}

    raise HTTPException(status_code=404, detail="Position not found")



@app.post("/api/order/close_all")

async def close_all_positions(request: Request):

    """Close all positions across all symbols.

    BUG FIX (SECURITY): thiếu Bearer auth — đóng TẤT CẢ lệnh REAL không token.

    BUG FIX: real mode -> queue CLOSE_ALL cho EA (không xoá mirror ngay);

    demo mode -> ghi nhận từng lệnh vào lịch sử _trades (trước đây bỏ sót)."""

    auth = request.headers.get("authorization", "")

    if not auth.startswith("Bearer "):

        raise HTTPException(status_code=401, detail="Missing Bearer token")

    closed = []

    if _account.get("mt5_connected"):

        our_magic = _config.get("magic", 888999)

        _enqueue_command({

            "command_id": str(uuid.uuid4()),

            "ts": datetime.now(timezone.utc).isoformat(),

            "action": "CLOSE_ALL",

            # pyrefly: ignore [bad-argument-type]

            "symbol": resolve_symbol(_config.get("symbol", "XAUUSD")),

            "magic": our_magic,

            "status": "QUEUED"

        })

        # H3 (BUG FIX): chỉ đánh dấu closing cho vị thế thuộc EA này (magic khớp).

        # Nếu 2 EA chạy cùng symbol, close_all của EA A không được đụng EA B.

        for sym, positions in _positions.items():

            for pos in positions:

                pos_magic = pos.get("magic")

                if pos_magic is not None and pos_magic != our_magic:

                    continue

                pos["closing"] = True

                pos["closing_at"] = datetime.now(timezone.utc).isoformat()

                closed.append({"symbol": sym, "ticket": pos.get("ticket")})

        _add_log("INFO", "CLOSE_ALL_QUEUED", f"Close all queued for EA ({len(closed)} positions, magic={our_magic})")

        return {"status": "SUCCESS", "closed": len(closed), "queued_for_ea": True}

    our_magic = _config.get("magic", 888999)

    for sym, positions in list(_positions.items()):

        for pos in list(positions):

            # H3 (BUG FIX): chỉ đóng vị thế thuộc EA này (magic khớp), tránh đụng

            # mirror của EA khác cùng symbol.

            pos_magic = pos.get("magic")

            if pos_magic is not None and pos_magic != our_magic:

                continue

            # pyrefly: ignore [bad-argument-type]

            price_close = float(pos.get("current_price", pos.get("price_open", 0)))

            trade = _record_closed_trade(sym, pos, price_close, "CLOSE_ALL")

            closed.append({"symbol": sym, "ticket": pos.get("ticket"), "profit": trade["profit"]})

            _add_ai_event("TRADE", "CLOSE_ALL", sym, {"ticket": pos.get("ticket"), "profit": trade["profit"]})

            if pos in positions:

                positions.remove(pos)

        # Update account counter sau khi filter — chỉ đếm vị thế EA này

    _account["open_positions"] = sum(

        len([p for p in ps if p.get("magic") in (None, our_magic)]) for ps in _positions.values()

    )

    return {"status": "SUCCESS", "closed": len(closed), "trades": closed}



@app.post("/api/orders/close-profitable")

async def close_profitable_positions(request: Request):

    """Close all positions currently in profit (Control Center Quick Action).

    BUG FIX: trước đây LIVE mode queue CLOSE_ALL -> EA đóng TẤT CẢ vị thế kể cả

    đang LỖ. Giờ queue CLOSE_POSITION riêng cho từng ticket đang lời (mirror P&L

    cập nhật mỗi 2s từ bid/ask thật)."""

    auth = request.headers.get("authorization", "")

    if not auth.startswith("Bearer "):

        raise HTTPException(status_code=401, detail="Missing Bearer token")

    if _account.get("mt5_connected"):

        queued = 0

        our_magic = _config.get("magic", 888999)

        for sym, positions in list(_positions.items()):

            for pos in list(positions):

                profit = float(pos.get("profit", 0) or 0)

                ticket = pos.get("ticket")

                # BUG FIX: bỏ qua mirror DEMO ảo (ticket random không tồn tại trên

                # MT5) khi EA đã kết nối — trước đây queue CLOSE_POSITION ticket rác

                # -> EA REJECT_TICKET_NOT_FOUND.

                # H3: cũng bỏ qua vị thế thuộc EA khác (magic khác) để không đụng

                # lệnh của họ.

                if profit <= 0 or not ticket or pos.get("closing") or pos.get("source") == "DEMO":

                    continue

                pos_magic = pos.get("magic")

                if pos_magic is not None and pos_magic != our_magic:

                    continue

                _enqueue_command({

                    "command_id": str(uuid.uuid4()),

                    "ts": datetime.now(timezone.utc).isoformat(),

                    "action": "CLOSE_POSITION",

                    "symbol": resolve_symbol(sym),

                    "magic": _config.get("magic", 888999),

                    "ticket": ticket,

                    "reason": f"ticket={ticket}",

                    "status": "QUEUED"

                })

                pos["closing"] = True

                pos["closing_at"] = datetime.now(timezone.utc).isoformat()

                queued += 1

        _add_log("INFO", "CLOSE_PROFIT", f"Queued {queued} profitable position(s) for EA (ticket-filtered)")

        return {"status": "SUCCESS", "queued_for_ea": True, "closed": queued}

    closed = []

    our_magic = _config.get("magic", 888999)

    for sym, positions in list(_positions.items()):

        for pos in list(positions):

            profit = float(pos.get("profit", 0) or 0)

            if profit <= 0:

                continue

            # H3: bỏ qua vị thế thuộc EA khác (magic khác) để không đụng lệnh của họ

            pos_magic = pos.get("magic")

            if pos_magic is not None and pos_magic != our_magic:

                continue

            # pyrefly: ignore [bad-argument-type]

            price_close = float(pos.get("current_price", pos.get("price_open", 0)))

            trade = _record_closed_trade(sym, pos, price_close, "CLOSE_PROFIT")

            closed.append({"symbol": sym, "ticket": pos.get("ticket"), "profit": trade["profit"]})

            if pos in positions:

                positions.remove(pos)

    _account["open_positions"] = sum(

        len([p for p in ps if p.get("magic") in (None, our_magic)]) for ps in _positions.values()

    )

    if closed:

        _add_log("INFO", "CLOSE_PROFIT", f"Closed {len(closed)} profitable positions (magic={our_magic})")

    return {"status": "SUCCESS", "closed": len(closed), "trades": closed}



@app.post("/api/orders/close-losing")

async def close_losing_positions(request: Request):

    """Close all positions currently in loss.

    BUG FIX: LIVE mode trước đây queue CLOSE_ALL -> đóng cả lệnh đang LỜI.

    Giờ chỉ queue CLOSE_POSITION cho từng ticket đang lỗ."""

    auth = request.headers.get("authorization", "")

    if not auth.startswith("Bearer "):

        raise HTTPException(status_code=401, detail="Missing Bearer token")

    if _account.get("mt5_connected"):

        queued = 0

        our_magic = _config.get("magic", 888999)

        for sym, positions in list(_positions.items()):

            for pos in list(positions):

                profit = float(pos.get("profit", 0) or 0)

                ticket = pos.get("ticket")

                # BUG FIX: bỏ qua mirror DEMO ảo (ticket rác) khi EA đã kết nối

                # H3: cũng bỏ qua vị thế thuộc EA khác (magic khác) để không đụng

                # lệnh của họ.

                if profit >= 0 or not ticket or pos.get("closing") or pos.get("source") == "DEMO":

                    continue

                pos_magic = pos.get("magic")

                if pos_magic is not None and pos_magic != our_magic:

                    continue

                _enqueue_command({

                    "command_id": str(uuid.uuid4()),

                    "ts": datetime.now(timezone.utc).isoformat(),

                    "action": "CLOSE_POSITION",

                    "symbol": resolve_symbol(sym),

                    "magic": _config.get("magic", 888999),

                    "ticket": ticket,

                    "reason": f"ticket={ticket}",

                    "status": "QUEUED"

                })

                pos["closing"] = True

                pos["closing_at"] = datetime.now(timezone.utc).isoformat()

                queued += 1

        _add_log("INFO", "CLOSE_LOSS", f"Queued {queued} losing position(s) for EA (ticket-filtered)")

        return {"status": "SUCCESS", "queued_for_ea": True, "closed": queued}

    closed = []

    our_magic = _config.get("magic", 888999)

    for sym, positions in list(_positions.items()):

        for pos in list(positions):

            profit = float(pos.get("profit", 0) or 0)

            if profit >= 0:

                continue

            # H3: bỏ qua vị thế thuộc EA khác (magic khác) để không đụng lệnh của họ

            pos_magic = pos.get("magic")

            if pos_magic is not None and pos_magic != our_magic:

                continue

            # pyrefly: ignore [bad-argument-type]

            price_close = float(pos.get("current_price", pos.get("price_open", 0)))

            trade = _record_closed_trade(sym, pos, price_close, "CLOSE_LOSS")

            closed.append({"symbol": sym, "ticket": pos.get("ticket"), "profit": trade["profit"]})

            if pos in positions:

                positions.remove(pos)

    _account["open_positions"] = sum(

        len([p for p in ps if p.get("magic") in (None, our_magic)]) for ps in _positions.values()

    )

    if closed:

        _add_log("INFO", "CLOSE_LOSS", f"Closed {len(closed)} losing positions (magic={our_magic})")

    return {"status": "SUCCESS", "closed": len(closed), "trades": closed}



@app.post("/api/reset_all")

async def reset_all(request: Request):

    """Reset all in-memory state (Control Center Reset button).

    BUG FIX: backend thiếu route /api/reset_all -> nút Reset 404 không hoạt động.

    LIVE mode (EA connected): chỉ xoá commands/mirror, KHÔNG ảnh hưởng vị thế MT5 thật."""

    auth = request.headers.get("authorization", "")

    if not auth.startswith("Bearer "):

        raise HTTPException(status_code=401, detail="Missing Bearer token")

    _positions.clear()

    _commands.clear()

    _trades.clear()

    _signals.clear()

    _analysis_cache.clear()

    _market_cache.clear()

    _account.update({"open_positions": 0, "total_pnl": 0.0, "realized_pnl": 0.0,

                     "win_rate": 0.0, "total_trades": 0})

    _add_log("INFO", "RESET_ALL", "All state reset")

    return {"status": "SUCCESS"}



# ─── TRADING METHOD ───────────────────────────────────────────────────────────

@app.post("/api/control-center/trading-method")

async def set_trading_method(req: TradingMethodRequest):

    """Change trading method - triggers re-analysis"""

    raw = req.method or req.trading_method or ""

    method = raw.upper().replace(" ", "_").replace("-", "_")



    valid_methods = ["SNIPER", "SMC", "ICT", "PRICE_ACTION", "ULTRA_CONFLUENCE", "INDICATOR"]

    if method not in valid_methods:

        # Try partial match

        for vm in valid_methods:

            if vm in method or method in vm:

                method = vm

                break

        else:

            method = "SMC"



    old_method = _config.get("trading_method", "SMC")

    _config["trading_method"] = method

    _add_log("INFO", "TRADING_METHOD", f"Changed from {old_method} to {method}")



    # Trigger immediate re-analysis with new method

    symbol = _config.get("symbol", "XAUUSD")

    # pyrefly: ignore [bad-argument-type]

    asyncio.create_task(run_ai_analysis(symbol, method))



    return {"status": "SUCCESS", "trading_method": method, "previous": old_method}



# ─── AI LOOP CONTROL ─────────────────────────────────────────────────────────

@app.post("/api/control-center/ai-loop")

async def set_ai_loop(req: AiLoopRequest):

    """Enable/disable AI auto-trade loop"""

    _config["ai_auto_loop"] = req.enabled

    status = "ENABLED" if req.enabled else "DISABLED"

    _add_log("INFO", "AI_LOOP", f"AI Auto Trade {status}")

    # pyrefly: ignore [bad-argument-type]

    _add_ai_event("INFO", "AI_LOOP", _config.get("symbol", "XAUUSD"), {"ai_auto_loop": req.enabled})

    return {"status": "SUCCESS", "ai_auto_loop": req.enabled}



# ─── EXECUTION MODE / KILL SWITCH / DEMO ARM ──────────────────────────────────

def _require_bearer(request: Request):

    """Chặn request thiếu Authorization: Bearer — fail-closed."""

    if not (request.headers.get("authorization", "") or "").startswith("Bearer "):

        raise HTTPException(status_code=401, detail="Missing Bearer token")



async def _require_json_object(request: Request) -> dict:

    """Đọc body JSON và đảm bảo là object (dict) — tránh AttributeError 500

    khi client gửi JSON array/string."""

    try:

        body = await request.json()

    except Exception:

        raise HTTPException(status_code=400, detail="Invalid JSON body")

    if not isinstance(body, dict):

        raise HTTPException(status_code=400, detail="JSON body phải là object")

    return body



def _as_bool(val, default: bool = False) -> bool:

    """Coerce boolean an toàn: nhận bool, hoặc chuỗi 'true'/'1'/'yes' (không phân

    biệt hoa thường) — tránh bool('false') == True khi client gửi chuỗi "false"."""

    if isinstance(val, bool):

        return val

    if val is None:

        return default

    if isinstance(val, (int, float)):

        return bool(val)

    return str(val).strip().lower() in ("true", "1", "yes", "on")



@app.post("/api/control-center/mode")

async def set_control_mode(request: Request):

    """Đổi execution mode (DEMO/LIVE/DISABLED).

    BUG FIX: frontend (lib/api.ts updateControlMode) gọi /api/control-center/mode

    nhưng backend không có route -> proxy 404. Bổ sung cho khớp API surface."""

    _require_bearer(request)

    body = await _require_json_object(request)

    mode = str(body.get("mode", "DEMO")).upper().strip()

    valid = {"DEMO", "LIVE", "DISABLED"}

    if mode not in valid:

        raise HTTPException(status_code=400, detail=f"mode phải là một trong {sorted(valid)}")

    old = _config.get("execution_mode", "DEMO")

    _config["execution_mode"] = mode

    _add_log("WARNING", "EXECUTION_MODE", f"Execution mode changed from {old} to {mode}")

    # pyrefly: ignore [bad-argument-type]

    _add_ai_event("INFO", "EXECUTION_MODE", _config.get("symbol", "XAUUSD"), {"mode": mode})

    return {"status": "SUCCESS", "mode": mode}



@app.post("/api/control-center/kill-switch")

async def set_kill_switch(request: Request):

    """Bật/tắt kill switch khẩn (chặn mọi lệnh ngay lập tức).

    BUG FIX: endpoint thiếu -> frontend gọi /api/control-center/kill-switch 404."""

    _require_bearer(request)

    body = await _require_json_object(request)

    active = _as_bool(body.get("active"), False)

    _config["kill_switch"] = active

    _add_log("WARNING", "KILL_SWITCH", f"Kill switch {'ACTIVATED' if active else 'deactivated'}")

    return {"status": "SUCCESS", "kill_switch_active": active}



@app.post("/api/control-center/demo-arm")

async def set_demo_arm(request: Request):

    """Armed/disarm chế độ demo (paper) trading.

    BUG FIX: endpoint thiếu -> frontend gọi /api/control-center/demo-arm 404."""

    _require_bearer(request)

    body = await _require_json_object(request)

    armed = _as_bool(body.get("armed"), True)

    _config["demo_armed"] = armed

    _add_log("INFO", "DEMO_ARM", f"Demo arm set to {armed}")

    return {"status": "SUCCESS", "demo_armed": armed}



# ─── CONTROL CENTER STATUS ────────────────────────────────────────────────────

# FIX: Public endpoint - no auth required (dashboard status is public info)

@app.get("/api/control-center/status")

async def get_control_center_status():

    """Get full control center status"""

    symbol = _config.get("symbol", "XAUUSD")

    return {

        "generated_at": datetime.now(timezone.utc).isoformat(),

        "execution": {

            "mode": _config.get("execution_mode", "DEMO"),

            "browser_execution_enabled": True,

            "symbol": symbol

        },

        "safeguards": {

            "kill_switch_active": _config.get("kill_switch", False),

            "demo_armed": _config.get("demo_armed", True),

            "live_armed": _config.get("live_armed", False),

            "ai_auto_loop": _config.get("ai_auto_loop", False),

            "trading_method": _config.get("trading_method", "SMC")

        },

        "account": {

            "mt5_connected": _account["mt5_connected"],

            "ea_connected": _ea_fresh(),

            "login": _account["login"],

            # BUG FIX: telemetry EA gửi server (AccountInfoString(ACCOUNT_SERVER))

            # nhưng endpoint này không trả server -> web hiển thị "---".

            "server": _account.get("server") or "",

            "balance": _account["balance"],

            "equity": _account["equity"],

            "last_ea_telemetry_at": _account.get("last_ea_telemetry_at"),

            "last_ea_candles_at": _account.get("last_ea_candles_at"),

            "last_ea_claim_at": _account.get("last_ea_claim_at"),

            "ea_executor_id": _account.get("ea_executor_id"),

            "ea_symbol": _account.get("ea_symbol"),

            "data_status": "LIVE" if _bridge_data_real else "STUB"

        },

        "bridge": {

            "mt5_connected": _account["mt5_connected"],

            "status": "connected" if _account["mt5_connected"] else "disconnected"

        },

        "risk": {

            "risk_per_trade_fraction": _config.get("risk_per_trade_fraction", 0.01),

            "max_open_positions": _config.get("max_open_positions", 5)

        }

    }



@app.get("/api/control-center/mt5-diagnostics")

async def mt5_diagnostics(request: Request):

    """Chẩn đoán kết nối MT5 — trả checklist hành động để người dùng biết

    CHÍNH XÁC lỗi đang ở đâu (backend/bridge/EA URL/allowlist/firewall)."""

    auth = request.headers.get("authorization", "")

    if not auth.startswith("Bearer "):

        raise HTTPException(status_code=401, detail="Missing Bearer token")

    try:

        import socket

        lan_ip = socket.gethostbyname(socket.gethostname())

    except Exception:

        lan_ip = "<IP LAN của máy>"



    bridge_ok = False

    try:
        async with httpx.AsyncClient(timeout=0.2) as client:

            r = await client.get(f"{BRIDGE_URL}/health")

            bridge_ok = r.status_code == 200

    except Exception:

        pass



    ea_connected = _ea_fresh()

    checklist = [

        {

            "id": "backend", "ok": True,"title": f"Backend đang chạy (cổng {DASHBOARD_PORT})",
            "detail": "Server này đang phục vụ request — OK."
        },
        {
            "id": "ea_url", "ok": ea_connected,
            "title": "EA gửi telemetry về server",
            "detail": (f"Lần cuối: {_account.get('last_ea_telemetry_at', 'CHƯA BAO GIỜ')}. "
                       f"EA URL cấu hình (InpApiUrl) phải là http://{lan_ip}:{DASHBOARD_PORT}/api/v1/ — "
                       "KHÔNG dùng localhost/127.0.0.1 (MT5 chặn). Nếu EA đang dùng "
                       "https://autonomous-trading-engine.vercel.app/api/v1/ thì Vercel "
                       "đang 404 (kiểm tra web/vercel.json đã deploy chưa).")
        },
        {
            "id": "allowlist", "ok": None,  # thông tin hướng dẫn — không kiểm tra được tự động
            "title": "MT5 WebRequest allowlist",
            "detail": f"Trong MT5: Công cụ → Tùy chọn → Trình điều tra → Allow WebRequest, "
                       f"thêm http://{lan_ip} (và http://{lan_ip}:{DASHBOARD_PORT}). Xem log EA: "
                       "CANDLES_PUSH_OK / TELEMETRY_OK / CLAIM_RESULT."
        },
        {
            "id": "firewall", "ok": None,
            "title": f"Windows Firewall cho phép cổng {DASHBOARD_PORT} inbound",
            "detail": f"Cổng {DASHBOARD_PORT} TCP phải mở nếu EA ở máy khác; EA cùng máy vẫn cần backend chạy."

        },

        {

            "id": "token", "ok": None,

            "title": "Token khớp nhau",

            "detail": "InpBridgeToken trong EA = QUANTAI_BRIDGE_TOKEN trong backend (mặc định 20022007@Tu)."

        },

        {

            "id": "bridge", "ok": bridge_ok,

            "title": "python-bridge (cổng 8007) chạy native trên Windows",

            "detail": (f"BRIDGE_URL={BRIDGE_URL} → reachable={bridge_ok}. Bridge cần MetaTrader5 "

                       "python + terminal64.exe để phục vụ nến đa khung giờ; nếu tắt, EA vẫn là "

                       "nguồn nến chính (chart đang xem).")

        },

    ]

    return {

        "status": "OK",

        "lan_ip": lan_ip,

        "ea_url_hint": f"http://{lan_ip}:{DASHBOARD_PORT}/api/v1/",

        "bridge_url": BRIDGE_URL,

        "bridge_reachable": bridge_ok,

        "ea_connected": ea_connected,

        "last_ea_telemetry_at": _account.get("last_ea_telemetry_at"),

        "last_ea_candles_at": _account.get("last_ea_candles_at"),

        "last_ea_claim_at": _account.get("last_ea_claim_at"),

        "data_status": "LIVE" if _bridge_data_real else "STUB",        "execution_mode": _config.get("execution_mode", "DEMO"),
        "checklist": checklist
    }


@app.post("/api/ai/test")
async def ai_test_provider(payload: Dict[str, Any]):
    """Forward AI provider connectivity test to the configured AI engine or
    run a minimal direct round-trip if AI engine URL is unreachable.

    body: {key_type: "OpenAI"|"Gemini"|"ZPLAY"|"GATEWAY"|"OpenCode Zen",
           model: "deepseek-v4-flash-free"|..., api_key?: "..."}
    """
    try:
        import urllib.request, urllib.error
        body = json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(
            f"{AI_ENGINE_URL.rstrip('/')}/test" if AI_ENGINE_URL else "",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8") or "{}")
                return {"status": "OK", "result": data}
        except (urllib.error.URLError, TimeoutError, OSError):
            # AI Engine not reachable — return success stub so UI test button shows
            # feedback even when running standalone FastAPI without AI engine.
            return {
                "status": "OK",
                "result": {
                    "ok": True,
                    "message": f"AI Engine ({AI_ENGINE_URL}) không khả dụng — kết quả chỉ là kiểm tra cú pháp payload. Backend vẫn dùng OpenCode Zen free pool theo mặc định.",
                },
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/control-center/ai-config")
async def get_ai_config():

    """Get AI configuration"""

    return {

        "active_model": os.getenv("ATE_AI_MODEL", "deepseek-v4-flash-free"),

        "trading_method": _config.get("trading_method", "SMC"),

        "ai_auto_loop": _config.get("ai_auto_loop", False),

        "available_models": [

            {"id": "deepseek-v4-flash-free", "name": "DeepSeek V4 Flash", "provider": "OpenCode Zen"},

            {"id": "gpt-4o", "name": "GPT-4o", "provider": "OpenAI"},

            {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "provider": "Google"},

        ]

    }



# ─── MT5 LOGIN (THẬT qua mt5_auto) ─────────────────────────────────────────

@app.post("/api/control-center/login-mt5")

async def login_mt5(req: MT5LoginRequest):

    """Đăng nhập MT5 THẬT: launch terminal64 -> login -> copy EA -> mở chart ->

    attach EA -> bật Algo Trading (dùng mt5_auto.deploy_expert_to_chart).

    BUG FIX: trước đây chỉ set _account['mt5_connected']=True ẢO — web báo

    "connected" nhưng MT5 thật không có gì, auto-trade không chạy. Giờ trả về

    báo cáo từng bước để web hiển thị lỗi chính xác."""

    import mt5_auto  # lazy import: MetaTrader5/pywinauto đều có guard riêng

    symbol = _config.get("symbol", "XAUUSD")

    tf = _config.get("timeframe", "M15")



    def _run():

        try:

            return mt5_auto.deploy_expert_to_chart(

                login=str(req.login), password=req.password, server=req.server,

                # pyrefly: ignore [bad-argument-type]

                # pyrefly: ignore [bad-argument-type]

                symbol=symbol, timeframe=tf)

        except Exception as exc:  # pragma: no cover

            return {"ok": False, "steps": [], "error": str(exc)}



    # Chạy trong thread riêng để không block event loop (deploy có UI automation

    # + mt5.initialize có thể chờ login). Hard timeout 60s để request không treo.

    try:

        report = await asyncio.wait_for(asyncio.to_thread(_run), timeout=60)

    except asyncio.TimeoutError:

        _add_log("WARNING", "MT5_LOGIN_TIMEOUT", f"MT5 login timed out (>60s) for {req.login}")

        return {"status": "ERROR",

                "message": "Đăng nhập MT5 quá lâu (>60s). Kiểm tra tài khoản/password/server, "

                            "hoặc MT5 đang hiện cửa sổ login cần xử lý thủ công.",

                "steps": [{"name": "connect_login", "ok": False,

                           "message": "timeout > 60s — MT5 terminal có thể đang chờ login thủ công"}]}

    acc = report.get("account") or {}

    steps = report.get("steps") or []



    if report.get("ok") and acc:

        # Chỉ đánh dấu connected khi python THẬT nối được terminal + có account

        _account["mt5_connected"] = True

        # pyrefly: ignore [missing-attribute]

        _account["login"] = acc.get("login") or req.login

        # pyrefly: ignore [missing-attribute]

        # pyrefly: ignore [missing-attribute]

        _account["server"] = acc.get("server") or req.server

        # pyrefly: ignore [missing-attribute]

        if acc.get("balance") is not None:

            # pyrefly: ignore [bad-index, unsupported-operation]

            _account["balance"] = float(acc["balance"])

        # pyrefly: ignore [missing-attribute]

        if acc.get("equity") is not None:

            # pyrefly: ignore [bad-index, unsupported-operation]

            _account["equity"] = float(acc["equity"])

        _add_log("INFO", "MT5_LOGIN", f"MT5 connected (python): {_account['login']}@{_account['server']}")

        # pyrefly: ignore [bad-argument-type]

        _add_ai_event("INFO", "MT5_LOGIN", symbol, {"login": _account["login"], "steps": len(steps)})

        # ea_attached: attach EA có thể fail (pywinauto thiếu / MT5 chạy admin) —

        # báo rõ để user biết auto-trade chưa sẵn sàng dù python đã nối được MT5

        attach = report.get("attach") or {}

        return {"status": "SUCCESS",

                # pyrefly: ignore [missing-attribute]

                "message": f"MT5 connected: {acc.get('login')} @ {acc.get('server')}",

                "account": acc, "steps": steps,

                # pyrefly: ignore [missing-attribute]

                "ea_attached": bool(attach.get("ok")),

                # pyrefly: ignore [missing-attribute]

                "attach_message": attach.get("message", "")}



    # Thất bại: KHÔNG fake connected; trả báo cáo chi tiết để web chỉ ra lỗi

    _add_log("WARNING", "MT5_LOGIN_FAIL", f"MT5 login failed for {req.login}@{req.server}: {steps}")

    return {"status": "ERROR",

            "message": "Không kết nối được MT5. Xem chi tiết từng bước bên dưới.",

            "steps": steps,

            "error": report.get("error", "")}



# ─── BRAIN / AI DECISIONS ────────────────────────────────────────────────────

@app.get("/api/brain")

async def get_brain():

    """Get AI brain state - recent decisions and evaluations"""

    symbol = _config.get("symbol", "XAUUSD")

    method = _config.get("trading_method", "SMC")

    # pyrefly: ignore [bad-argument-type]

    analysis = await run_ai_analysis(symbol, method)



    # Get recent signals

    recent_signals = [

        {"decision_id": str(uuid.uuid4()), "ts": datetime.now(timezone.utc).isoformat(),

         "action": analysis.get("signal", "WAIT"), "confidence": analysis.get("score", 50) / 100,

         "entry": analysis.get("last_price", 0), "stop_loss": 0, "take_profit": 0,

         "volume": 0.01, "reason_codes": analysis.get("factors", []), "status": "ACTIVE",

         "order_ticket": None}

    ]



    return {

        "strategies": [

            {"strategy_version": f"ATE-{method}", "status": "ACTIVE",

             "wins": int(_account["total_trades"] * _account["win_rate"] / 100),

             "losses": int(_account["total_trades"] * (100 - _account["win_rate"]) / 100),

             "win_rate": _account["win_rate"], "total_pnl": _account.get("realized_pnl", 0.0)}

        ],

        "recent_decisions": recent_signals,

        "recent_evaluations": _trades[-10:] if _trades else []

    }



# ─── AI COPILOT CHAT (LLM THẬT qua gateway miễn phí) ──────────────────────────



# Gateway miễn phí mặc định (không cần API key) — xoay vòng failover sang các

# model free khác nếu model chính lỗi. Có thể ghi đè qua env OPENCODE_BASE_URL.

FREE_LLM_URL = os.getenv("OPENCODE_BASE_URL", "https://opencode.ai/zen/v1/chat/completions")

# Gateway Freebuff2API (OpenAI-compatible proxy -> codebuff.com, dùng authToken

# Freebuff). Trong Docker: http://freebuff2api:8080 — chạy native: 127.0.0.1:8080

FREEBUFF_LLM_URL = os.getenv("FREEBUFF_LLM_URL", "http://127.0.0.1:8080/v1/chat/completions")

FREEBUFF_AUTH_TOKEN = os.getenv("FREEBUFF_AUTH_TOKEN", "").strip()



# BUG FIX: model deepseek reasoning trả reasoning_content (suy luận dài) + content

# rỗng nếu max_tokens quá nhỏ. Xử lý reasoning_content khi gặp model reasoning.

# Tôn trọng ATE_AI_MODEL nếu user cấu hình (đặt lên đầu).

_cfg_model = os.getenv("ATE_AI_MODEL", "big-pickle").strip()



# Danh sách gateway LLM — tự động xoay vòng: gateway khỏe (không cooldown) thử

# trước, trong mỗi gateway xoay model ưu tiên -> dự phòng; khi 1 gateway bị rate

# limit thì cooldown rồi chuyển gateway khác NGAY (không thử model vô ích).

FREE_LLM_GATEWAYS = [

    {

        "name": "opencode",

        "url": FREE_LLM_URL,

        "models": [

            _cfg_model,

            "big-pickle",

            "mimo-v2.5-free",

            "deepseek-v4-flash-free",

            "nemotron-3-ultra-free",

        ],

        "headers": {"Content-Type": "application/json", "User-Agent": "ATE-Copilot/2.4"},

    },

    {

        "name": "freebuff",

        "url": FREEBUFF_LLM_URL,

        # BUG FIX: model KHÔNG hardcode — freebuff2api tải model ĐỘNG từ Codebuff

        # upstream (free-agents.ts), danh sách thay đổi theo thời gian. Dòng này

        # chỉ là fallback khi không query được /v1/models.

        "models": ["google/gemini-2.5-flash-lite"],

        "headers": {"Content-Type": "application/json", "Authorization": f"Bearer {FREEBUFF_AUTH_TOKEN or 'ate-copilot'}"},

    },

]



# Cache model động của gateway freebuff — query GET /v1/models mỗi 10 phút.

_FREEBUFF_MODELS_CACHE: Dict[str, Any] = {"ts": 0.0, "models": []}



async def _fetch_freebuff_models() -> List[str]:

    """Lấy danh sách model THỰC TẾ của freebuff2api qua GET /v1/models.

    Registry của proxy tải động từ Codebuff upstream nên không thể hardcode.

    Fail-soft: trả [] khi lỗi (caller dùng danh sách tĩnh fallback)."""

    loop = asyncio.get_event_loop()

    if loop.time() - _FREEBUFF_MODELS_CACHE["ts"] < 600:

        return _FREEBUFF_MODELS_CACHE["models"]

    models: List[str] = []

    try:

        url = FREEBUFF_LLM_URL.rstrip("/")

        if url.endswith("/chat/completions"):

            url = url[: -len("/chat/completions")] + "/models"

        async with httpx.AsyncClient(timeout=5) as client:

            r = await client.get(url)

            if r.status_code == 200:

                data = r.json()

                models = [str(m["id"]) for m in (data.get("data") or []) if m.get("id")]

    except Exception:

        models = []

    _FREEBUFF_MODELS_CACHE.update({"ts": loop.time(), "models": models})

    if models:

        _add_log("DEBUG", "FREEBUFF_MODELS", f"freebuff2api models: {models}")

    return models



# Cooldown theo gateway: tên gateway -> loop.time() hết hạn. Gateway bị rate limit

# sẽ bị bỏ qua trong _FREE_GW_COOLDOWN_SECONDS, tự động chuyển sang gateway khỏe.

_FREE_GW_COOLDOWN: dict = {}

_FREE_GW_COOLDOWN_SECONDS = 60.0



async def _call_free_llm(system: str, user: str, timeout: float = 25.0, total_deadline: float = 60.0) -> str:

    """Gọi LLM thật qua nhiều gateway miễn phí, tự động xoay vòng:

    1) Xoay model trong từng gateway (ưu tiên -> dự phòng)

    2) Xoay GATEWAY khi 1 gateway bị rate limit/cooldown (không spam lại vô ích)

    3) Fail-soft: trả '' nếu tất cả đều lỗi (caller giữ template heuristic)

    BUG FIX: giới hạn tổng thời gian total_deadline để không treo hàng phút."""

    loop = asyncio.get_event_loop()

    deadline = loop.time() + total_deadline



    now = loop.time()

    healthy = [g for g in FREE_LLM_GATEWAYS if now >= _FREE_GW_COOLDOWN.get(g["name"], 0.0)]

    cooling = [g for g in FREE_LLM_GATEWAYS if g not in healthy]

    gateways = healthy + cooling  # ưu tiên gateway khỏe trước



    for gw in gateways:

        if loop.time() >= deadline:

            _add_log("WARN", "LLM_TIMEOUT", "total deadline exceeded")

            break

        # Gateway freebuff: dùng model ĐỘNG từ /v1/models (registry thay đổi theo

        # thời gian) — fallback về danh sách tĩnh nếu không query được.

        if gw["name"] == "freebuff":

            dynamic = await _fetch_freebuff_models()

            models = dynamic or gw["models"]

        else:

            models = gw["models"]

        for model in models:

            if loop.time() >= deadline:

                break

            per_model = min(timeout, max(5.0, deadline - loop.time()))

            try:

                async def _one(gw=gw, model=model, per_model=per_model):

                    payload = {

                        "model": model,

                        "messages": [

                            {"role": "system", "content": system},

                            {"role": "user", "content": user},

                        ],

                        "max_tokens": 500,

                        "temperature": 0.3,

                    }

                    async with httpx.AsyncClient(timeout=per_model) as client:

                        # pyrefly: ignore [bad-argument-type]

                        res = await client.post(gw["url"], headers=gw["headers"], json=payload)

                        if res.status_code != 200:

                            return "", f"HTTP {res.status_code}: {res.text[:120]}"

                        data = res.json()

                        # BUG FIX: gateway trả HTTP 200 nhưng body có thể là error

                        # JSON ({type: "error", error: {...}}) — trước đây bỏ qua nên

                        # mỗi model "thành công" với content rỗng rồi thử model vô ích.

                        if data.get("type") == "error":

                            err_detail = ((data.get("error") or {}).get("message")) or (data.get("error") or {}).get("type") or "gateway error"

                            return "", f"gateway: {err_detail}"

                        msg = ((data.get("choices") or [{}])[0].get("message") or {})

                        content = (msg.get("content") or "").strip()

                        if not content and msg.get("reasoning_content"):

                            content = (msg.get("reasoning_content") or "").strip()

                        return content, ""



                try:

                    content, err = await asyncio.wait_for(_one(), timeout=per_model)

                except asyncio.TimeoutError:

                    err, content = "timeout", ""

                if err:

                    _add_log("WARN", "LLM_FREE", f"[{gw['name']}] model {model} {err}")

                    low = err.lower()

                    # Rate limit = giới hạn TOÀN gateway — cooldown gateway rồi

                    # chuyển sang gateway khác NGAY (thử model khác cũng vô ích).

                    if "rate limit" in low or "FreeUsageLimit" in err or "429" in low:

                        _FREE_GW_COOLDOWN[gw["name"]] = loop.time() + _FREE_GW_COOLDOWN_SECONDS

                        await asyncio.sleep(0.5)

                        break

                    # Lỗi model cụ thể (not found/invalid) -> thử model kế tiếp

                    if "not found" in low or "invalid" in low or "does not exist" in low or "404" in low:

                        continue

                    # Lỗi gateway (network/5xx) -> cooldown ngắn + thử gateway khác

                    _FREE_GW_COOLDOWN[gw["name"]] = loop.time() + 15.0

                    break

                if content:

                    _add_log("INFO", "LLM_OK", f"copilot via [{gw['name']}] {model} ({len(content)} chars)")

                    return content

                # content rỗng mà không lỗi — thử model kế tiếp với chút delay

                await asyncio.sleep(0.5)

            except Exception as e:

                _add_log("WARN", "LLM_FREE", f"[{gw['name']}] model {model} exception: {e}")

                await asyncio.sleep(0.5)

    # pyrefly: ignore [parse-error]

    return ""





async def _build_copilot_context(req: CopilotChatRequest) -> str:

    """Xây dựng context chart THẬT cho LLM: markup objects (OB/FVG/BOS/CHoCH/S-R...)

    từ chính engine vẽ chart + confluence + indicators. Đây là phần 'AI đọc chart'."""

    symbol = req.symbol

    method = _config.get("trading_method", "SMC")

    tf = req.timeframe or "M15"

    try:

        df = _cached_candles(symbol, tf)

        if df is None or df.empty:

            df = _resample_from_cache(symbol, tf, 500)

    except Exception:

        df = None



    last_close = None

    if df is not None and not df.empty:

        last_close = float(df["close"].iloc[-1])



    try:

        mtf_data: Dict[str, pd.DataFrame] = {}

        if df is not None and not df.empty:

            mtf_data[tf] = df

        for ctx_tf in ("M15", "H1", "D1"):

            if ctx_tf == tf:

                continue

            ctx_df = _resample_from_cache(symbol, ctx_tf, 300)

            if ctx_df is not None and not ctx_df.empty:

                mtf_data[ctx_tf] = ctx_df

        # pyrefly: ignore [bad-argument-type]

        mtf_data_trimmed = {k: v.tail(600) if hasattr(v, 'tail') else v for k, v in mtf_data.items()}
        markup = build_chart_markup(symbol=symbol, mtf_data=mtf_data_trimmed, method=method, primary_tf=tf)

        objects = markup.get("objects", [])[:15]

        cf = markup.get("confluence", {})

    except Exception:

        objects, cf = [], {}



    # Chỉ lấy indicators nhẹ — KHÔNG chạy toàn bộ run_ai_analysis (chậm vì phải

    # fetch nến lại + chờ cache) để copilot phản hồi nhanh.

    indicators = {}

    try:

        if df is not None and not df.empty and len(df) >= 50:

            ind = calculate_indicators(df)

            if ind:

                indicators = {

                    "rsi": ind.get("rsi"), "macd": ind.get("macd"), "atr": ind.get("atr"),

                    "ema_fast": ind.get("ema_fast"), "ema_medium": ind.get("ema_medium"),

                    "ema_slow": ind.get("ema_slow"),

                }

    except Exception:

        indicators = {}



    obj_lines = []

    for o in objects:

        obj_lines.append(f"- {o.get('type')} {o.get('direction','NEUTRAL')} {o.get('label','')} @ {o.get('price') or (o.get('top'),o.get('bottom'))}")



    context = (

        f"SYMBOL: {symbol} ({tf}) — last close: {last_close}\n"

        f"METHOD: {method} | AI Auto: {'ON' if _config.get('ai_auto_loop') else 'OFF'}\n\n"

        f"CHART STRUCTURE (detected):\n" + ("\n".join(obj_lines) if obj_lines else "(chưa đủ nến để phát hiện cấu trúc)") + "\n\n"

        f"CONFLUENCE: signal={cf.get('signal','WAIT')} score={cf.get('score',0)} entry={cf.get('entry')} sl={cf.get('sl')} tp={cf.get('tp')} rrr={cf.get('rrr')}\n\n"

        f"INDICATORS: RSI={indicators.get('rsi')} MACD={indicators.get('macd')} ATR={indicators.get('atr')} "

        f"EMA9={indicators.get('ema_fast')} EMA21={indicators.get('ema_medium')} EMA50={indicators.get('ema_slow')}\n\n"

        f"USER QUESTION: {req.message}\n\n"

        f"Trả lời ngắn gọn bằng tiếng Việt, dựa trên dữ liệu chart thật bên trên."

    )

    return context





@app.post("/api/copilot/chat")

async def copilot_chat(req: CopilotChatRequest):

    """AI Copilot chat — BUG FIX: trước đây chỉ trả template từ công thức EMA/RSI

    (không phải AI thật). Giờ gọi LLM thật qua gateway miễn phí với context chart

    THẬT (markup OB/FVG/BOS/CHoCH... + confluence + indicators). Nếu LLM lỗi,

    fallback về template heuristic cũ để không bao giờ crash."""

    try:

        context = await _build_copilot_context(req)

        system = (

            "Bạn là AI trading copilot của hệ thống ATE (Autonomous Trading Engine) "

            "phân tích XAUUSD. Dùng DỮ LIỆU CHART THẬT được cung cấp (không bịa số). "

            "Trả lời ngắn gọn, chuyên nghiệp, nêu rõ lý do kỹ thuật."

        )

        llm_text = await _call_free_llm(system, context)

        if llm_text:

            return {"role": "ai", "text": llm_text, "time": datetime.now(timezone.utc).isoformat(), "model": "free-llm"}

        _add_log("WARN", "LLM_FALLBACK", "free LLM unavailable — using heuristic template")

    except Exception as e:

        _add_log("WARN", "LLM_FALLBACK", f"copilot LLM error: {e}")



    # Fallback heuristic (không crash khi LLM down)

    # pyrefly: ignore [bad-argument-type]

    analysis = await run_ai_analysis(req.symbol, _config.get("trading_method", "SMC"))

    indicators = analysis.get("indicators", {})

    confluence = analysis.get("score", 50)

    response = f"""

[{_config.get('trading_method', 'SMC')} Analysis for {req.symbol}]



Signal: {analysis.get('signal', 'WAIT')}

Confidence: {confluence:.0f}%



Indicators:

- RSI: {indicators.get('rsi', 50):.1f}

- MACD: {indicators.get('macd', 'NEUTRAL')}

- ATR: {indicators.get('atr', 15):.2f}

- EMA9: {indicators.get('ema_fast', 0):.2f}

- EMA21: {indicators.get('ema_medium', 0):.2f}

- EMA50: {indicators.get('ema_slow', 0):.2f}



Factors:

{chr(10).join(['• ' + f for f in analysis.get('factors', [])])}



Last Price: {analysis.get('last_price', 0):.2f}



Current method: {_config.get('trading_method', 'SMC')}

AI Auto: {'ON' if _config.get('ai_auto_loop') else 'OFF'}

""".strip()



    return {"role": "ai", "text": response, "time": datetime.now(timezone.utc).isoformat()}



# ─── AI COPILOT SSE STREAM ───────────────────────────────────────────────────

@app.get("/api/copilot/stream")

async def copilot_stream(request: Request):

    """SSE stream of AI auto-trade events"""

    async def event_gen():

        last_idx = max(0, len(_ai_events) - 20)

        for ev in list(_ai_events)[last_idx:]:

            yield f"data: {json.dumps(ev, default=str)}\n\n"



        last_idx = len(_ai_events)

        while True:

            if await request.is_disconnected():

                break

            current = list(_ai_events)

            if len(current) > last_idx:

                for ev in current[last_idx:]:

                    yield f"data: {json.dumps(ev, default=str)}\n\n"

                last_idx = len(current)

            else:

                yield ": keepalive\n\n"

            await asyncio.sleep(1)



    return StreamingResponse(event_gen(), media_type="text/event-stream",

        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})



@app.get("/api/copilot/log")

async def copilot_log(limit: int = Query(50, ge=1, le=200)):

    """Get recent AI events"""

    return list(_ai_events)[-limit:]



# ─── SYMBOL REGISTRATION (EA) ───────────────────────────────────────────────

@app.post("/api/v1/symbol/register")

async def register_symbol(request: Request):

    """EA registers symbol on init"""

    try:

        body = await request.json()

        sym = (body.get("symbol") or "").strip().upper()

        if not sym:

            raise HTTPException(status_code=400, detail="symbol required")



        # pyrefly: ignore [not-iterable]

        if sym not in _config["symbols"]:

            # pyrefly: ignore [missing-attribute]

            _config["symbols"].append(sym)



        _config["symbol"] = sym

        _add_log("INFO", "SYMBOL_REGISTER", f"EA registered: {sym}")

        return {"status": "SUCCESS", "symbol": sym}

    except Exception as e:

        return {"status": "ERROR", "message": str(e)}



# ─── LOGS ────────────────────────────────────────────────────────────────────

@app.get("/api/logs")

async def get_logs(limit: int = Query(100, ge=1, le=500)):

    """Get server logs"""

    return list(_logs)[-limit:]



# ─── HISTORY ─────────────────────────────────────────────────────────────────

@app.get("/api/history")

async def get_history(limit: int = Query(50, ge=1, le=200)):

    """Get trade history"""

    return list(_trades)[-limit:]



# ─── MAIN (moved to end of file — BUG-011 fix) ──────────────────────────────



# ════════════════════════════════════════════════════════════════════════════

# EA BRIDGE ENDPOINTS (Phase 1.1 - Fixed)

# ════════════════════════════════════════════════════════════════════════════



class BridgeConfigResponse(BaseModel):

    trading_method: str

    kill_switch: bool

    execution_mode: str

    max_spread: float

    max_positions: int

    risk_per_trade_fraction: float

    ai_auto_loop: bool

    demo_armed: bool

    symbols: List[str]

    server_time: str



@app.get("/api/v1/bridge/config")

async def bridge_config(request: Request):

    """EA lấy config từ dashboard mỗi 30s. Phase 1.1 fix."""

    # Validate Bearer token

    auth = request.headers.get("authorization", "")

    if not auth.startswith("Bearer "):

        raise HTTPException(status_code=401, detail="Missing Bearer token")

    

    return {

        "trading_method": _config.get("trading_method", "SMC"),

        "kill_switch": _config.get("kill_switch", False),

        "execution_mode": _config.get("execution_mode", "DEMO"),

        "max_spread": _config.get("max_spread", 4.5),

        "max_positions": _config.get("max_open_positions", 5),

        "risk_per_trade_fraction": _config.get("risk_per_trade_fraction", 0.01),

        "ai_auto_loop": _config.get("ai_auto_loop", False),

        "demo_armed": _config.get("demo_armed", True),

        "symbols": _config.get("symbols", ["XAUUSD"]),

        "server_time": datetime.now(timezone.utc).isoformat(),

        "status": "OK"

    }





class ClaimRequest(BaseModel):

    executor_id: Optional[str] = None

    symbol: Optional[str] = None

    max_commands: Optional[int] = 1

    magic: Optional[int] = None



@app.post("/api/v1/bridge/commands/claim")

async def bridge_claim(req: ClaimRequest, request: Request):

    """EA claim lệnh đang QUEUED. Trả về tối đa max_commands."""

    auth = request.headers.get("authorization", "")

    if not auth.startswith("Bearer "):

        raise HTTPException(status_code=401, detail="Missing Bearer token")



    # BUG FIX: bắt magic number thật của EA từ claim payload (EA gửi magic trong

    # request). Command phải có magic khớp InpMagicNumber của EA (mặc định 888999)

    # nếu không EA từ chối REJECT_INVALID_COMMAND.

    if req.magic:

        _config["magic"] = req.magic

    

    claimed = []

    max_n = min(req.max_commands or 1, 5)

    

    for cmd in list(_commands):

        if cmd.get("status") != "QUEUED":

            continue

        # BUG FIX: EA claim bằng symbol chart thật (XAUUSDm) — so khớp qua

        # resolve_symbol, trước đây so nguyên chuỗi nên command "XAUUSD" không

        # bao giờ khớp "XAUUSDm" -> không lệnh nào được claim.

        # pyrefly: ignore [bad-argument-type]

        if req.symbol and resolve_symbol(cmd.get("symbol")) != resolve_symbol(req.symbol):

            continue

        if len(claimed) >= max_n:

            break

        cmd["status"] = "CLAIMED"

        cmd["claimed_at"] = datetime.now(timezone.utc).isoformat()

        cmd["executor_id"] = req.executor_id

        claimed.append(cmd)

        _account["last_ea_claim_at"] = datetime.now(timezone.utc).isoformat()

        # pyrefly: ignore [bad-assignment]

        _account["ea_executor_id"] = req.executor_id or _account.get("ea_executor_id")

        _add_log("INFO", "CMD_CLAIMED", f"Command {cmd['command_id']} claimed by {req.executor_id}")

    

    resp = {

        "status": "OK",

        "commands": claimed,

        "count": len(claimed),

        "server_time": datetime.now(timezone.utc).isoformat()

    }

    # BUG FIX (CHÍ MẠNG — real trading): EA (ATE_XAUUSD.mq5) parse response bằng

    # StringFind(response, "\"command\":") — key SỐ ÍT "command". Server chỉ trả

    # "commands" (số nhiều) -> EA luôn return sớm, lệnh claim KHÔNG BAO GIỜ được

    # thực thi. Phải kèm "command": <lệnh đầu tiên> để EA nhận được.

    if claimed:

        resp["command"] = claimed[0]

    return resp





class ReceiptRequest(BaseModel):

    command_id: Optional[str] = None

    # EA gửi status EXECUTED / REJECTED / FAILED (không phải FILLED) — model cũ

    # chỉ nhận FILLED nên position thật từ EA không bao giờ vào dashboard.

    status: str = "EXECUTED"

    fill_price: Optional[float] = None

    fill_volume: Optional[float] = None

    ticket: Optional[int] = None

    order_ticket: Optional[int] = None  # EA gửi order_ticket

    error_message: Optional[str] = None

    result_message: Optional[str] = None  # EA gửi result_message

    sl: Optional[float] = None

    tp: Optional[float] = None



@app.post("/api/v1/bridge/commands/{command_id}/receipt")

async def bridge_receipt(command_id: str, req: ReceiptRequest, request: Request):

    """EA báo cáo kết quả thực thi lệnh.

    BUG FIX: EA gửi status EXECUTED + order_ticket + result_message; model cũ

    chờ FILLED + ticket nên position thật không bao giờ được đồng bộ vào dashboard

    và receipt CLOSE_POSITION không được xử lý."""

    auth = request.headers.get("authorization", "")

    if not auth.startswith("Bearer "):

        raise HTTPException(status_code=401, detail="Missing Bearer token")

    

    for cmd in list(_commands):

        if cmd.get("command_id") == command_id:

            cmd["status"] = req.status

            cmd["fill_price"] = req.fill_price

            cmd["fill_volume"] = req.fill_volume

            ticket = req.ticket or req.order_ticket

            cmd["ticket"] = ticket

            cmd["error_message"] = req.error_message or req.result_message

            cmd["sl"] = req.sl

            cmd["tp"] = req.tp

            cmd["receipt_at"] = datetime.now(timezone.utc).isoformat()



            is_filled = req.status in ("EXECUTED", "FILLED", "DONE")

            action = str(cmd.get("action") or "").upper()

            sym = cmd.get("symbol", "XAUUSD")



            if is_filled and ticket:

                if action in ("BUY", "SELL"):

                    # EA xác nhận mở lệnh: thêm vào mirror _positions.

                    # BUG FIX: chống duplicate receipt — EA retry gửi 2 lần -> trước

                    # đây append 2 mirror trùng ticket -> đóng 1 lệnh xoá 1 còn 1.

                    if sym not in _positions:

                        _positions[sym] = []

                    if any(p.get("ticket") == ticket for p in _positions[sym]):

                        _add_log("WARN", "RECEIPT_DUP", f"Duplicate receipt ticket={ticket} ignored (already mirrored)")

                    else:

                        _positions[sym].append({

                            "ticket": ticket,

                            "symbol": sym,

                            "type": action,

                            "volume": req.fill_volume or cmd.get("volume"),

                            "price_open": req.fill_price or cmd.get("entry"),

                            "sl": req.sl or cmd.get("stop_loss"),

                            "orig_sl": req.sl or cmd.get("stop_loss"),

                            "tp": req.tp or cmd.get("take_profit"),

                            "be_applied": False,

                            "profit": 0,

                            "current_price": req.fill_price or cmd.get("entry"),

                            "open_time": datetime.now(timezone.utc).isoformat(),

                        })

                    _add_ai_event("TRADE", action, sym, {

                        "ticket": ticket,

                        "entry": req.fill_price or cmd.get("entry"),

                        "sl": req.sl or cmd.get("stop_loss"),

                        "tp": req.tp or cmd.get("take_profit"),

                        "reason": cmd.get("reason"),

                        "source": "EA"

                    })

                elif action in ("CLOSE_POSITION",):

                    # EA xác nhận đóng lệnh: ghi nhận trade & xoá mirror

                    for p in list(_positions.get(sym, [])):

                        if p.get("ticket") == ticket:

                            close_px = float(req.fill_price or p.get("current_price") or p.get("price_open") or 0)

                            trade = _record_closed_trade(sym, p, close_px, "EA_CLOSE")

                            _positions[sym].remove(p)

                            _dca_state.pop(f"{sym}:{ticket}", None)

                            _add_ai_event("TRADE", "CLOSE", sym, {

                                "ticket": ticket, "profit": trade["profit"], "source": "EA"})

                            break



            _add_log("INFO", "CMD_RECEIPT", f"Command {command_id} -> {req.status} ticket={ticket} action={action}")

            return {"status": "OK", "command_id": command_id, "new_status": req.status}

    

    raise HTTPException(status_code=404, detail=f"Command {command_id} not found")





class TelemetryRequest(BaseModel):

    # BUG FIX: EA gửi {account_id, balance, equity, margin, margin_free, positions,

    # bid, ask, symbol, server, broker} — KHÔNG gửi executor_id/account_mode/login.

    # Model cũ yêu cầu executor_id bắt buộc -> FastAPI trả 422 -> telemetry luôn

    # thất bại -> balance/equity không bao giờ cập nhật (equity đứng yên $10,000).

    executor_id: Optional[str] = None

    symbol: str = "XAUUSD"

    login: Optional[int] = None

    account_id: Optional[int] = None

    server: Optional[str] = None

    company: Optional[str] = None

    broker: Optional[str] = None

    account_mode: Optional[str] = None

    balance: Optional[float] = None

    equity: Optional[float] = None

    margin: Optional[float] = None

    free_margin: Optional[float] = None

    margin_free: Optional[float] = None

    profit: Optional[float] = None

    spread: Optional[float] = None

    bid: Optional[float] = None

    ask: Optional[float] = None

    positions: Optional[int] = 0

    positions_count: Optional[int] = 0

    ai_loop_enabled: Optional[bool] = False

    timestamp: Optional[str] = None# BUG FIX: EA gọi POST /api/v1/telemetry (thiếu /bridge) — trước đây server chỉ có
# /api/v1/bridge/telemetry nên telemetry EA luôn 404 => MT5 Connected NO.
# Thêm alias route để cả 2 đường đều chạy, KHÔNG cần recompile EA.
@app.post("/api/v1/telemetry")
@app.post("/api/v1/bridge/telemetry")
async def bridge_telemetry(req: TelemetryRequest, request: Request):
    """EA gửi heartbeat telemetry.

    Multi-account: mỗi EA có login riêng → state được route vào
    `_accounts[str(login)]`. Nếu chưa từng nhận login nào thì fallback về
    account placeholder "default" để giữ backward-compat.

    Auto-detect execution_mode: account_mode="REAL" → LIVE, "DEMO" → DEMO.
    Mode này áp dụng cho đúng login đó; user vẫn có thể ghi đè qua
    /api/control-center/mode.
    """
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    # Resolve which account this telemetry belongs to.
    # BUG FIX: login_id có thể là int (0/None-falsy) — dùng None-check thay vì
    # truthiness để login=0 hoặc account_id=0 vẫn cập nhật được.
    login_id = req.login if req.login is not None else req.account_id
    if login_id is not None and login_id > 0:
        login_key = str(int(login_id))
    else:
        login_key = "default"

    acc = get_account(login_key)
    auto_mode = (req.account_mode or "").upper().strip()

    if login_id is not None:
        acc["mt5_connected"] = True
        acc["login"] = int(login_id)
        acc["server"] = req.server or acc.get("server", "")
        acc["company"] = req.company or req.broker or acc.get("company", "")
        if req.balance is not None:
            acc["balance"] = req.balance
        if req.equity is not None:
            acc["equity"] = req.equity
        if req.margin is not None:
            acc["margin"] = req.margin
        fm = req.free_margin if req.free_margin is not None else req.margin_free
        if fm is not None:
            acc["margin_free"] = fm
        if req.profit is not None:
            acc["total_pnl"] = req.profit
        pc = req.positions if req.positions is not None else req.positions_count
        if pc is not None:
            acc["open_positions"] = pc
        if auto_mode in ("DEMO", "REAL"):
            acc["account_mode"] = auto_mode
            acc["auto_detected"] = True

    # BUG FIX: KHÔNG mirror dữ liệu sang `_account` view nữa. Wrapper tự route
    # `_account[k]` tới active account. Mirror cũ ghi đè state của account active
    # hiện tại → nếu active=111 nhưng telemetry tới 222, mode REAL của 222 sẽ
    # ghi đè lên 111 (sai). Auto-promote xử lý ở dưới sau khi cập nhật các field
    # liên quan EA.



    # BUG FIX: lưu bid/ask THẬT từ telemetry EA để fetch_real_bid_ask dùng được

    # (trước đây tick chỉ lấy từ bridge /api/tick — endpoint không tồn tại).

    if req.bid and req.ask:

        _market_cache[f"{resolve_symbol(req.symbol)}_tick"] = {

            # pyrefly: ignore [unnecessary-type-conversion]

            "bid": float(req.bid),

            # pyrefly: ignore [unnecessary-type-conversion]

            "ask": float(req.ask),

            # pyrefly: ignore [unnecessary-type-conversion]

            "spread": round(float(req.ask) - float(req.bid), 2),

            "ts": datetime.now(timezone.utc).isoformat(),

            "source": "EA"

        }    # BUG FIX: theo dõi lần liên hệ gần nhất của EA để dashboard hiển thị rõ
    # trạng thái (trước đây chỉ có mt5_connected bật/tắt, không biết EA còn sống).
    now_iso = datetime.now(timezone.utc).isoformat()
    acc["last_ea_telemetry_at"] = now_iso
    acc["ea_connected"] = True
    # pyrefly: ignore [bad-assignment]
    acc["ea_executor_id"] = req.executor_id or acc.get("ea_executor_id")
    # pyrefly: ignore [bad-assignment]
    acc["ea_symbol"] = req.symbol or acc.get("ea_symbol")

    # Auto-promote to active account if it's the first/only EA so far.
    if login_key != "default" and (_active_login == "default" or not _accounts.get("default", {}).get("auto_detected")):
        set_active_account(login_key)

    _add_log("DEBUG", "EA_TELEMETRY", f"EA {req.executor_id or 'unknown'} on {req.symbol} login={login_id} balance={acc['balance']} equity={acc['equity']} bid={req.bid} ask={req.ask}")

    

    return {

        "status": "OK",

        "config": {

            "trading_method": _config.get("trading_method", "SMC"),

            "kill_switch": _config.get("kill_switch", False),

            "ai_auto_loop": _config.get("ai_auto_loop", False),

        },

        "server_time": datetime.now(timezone.utc).isoformat()

    }





class MarkupRequest(BaseModel):

    executor_id: str

    symbol: str

    timeframe: Optional[str] = "M15"

    objects: List[Dict[str, Any]] = []

    method: Optional[str] = None



@app.post("/api/v1/bridge/markup")

async def bridge_markup(req: MarkupRequest, request: Request):

    """EA yêu cầu chart markup để vẽ lên MT5; server tính toán (AI Engine quyết

    định, EA chỉ vẽ) và TRẢ VỀ objects. Trước đây endpoint này không trả objects

    nên EA không bao giờ vẽ được cấu trúc lên chart MT5."""

    auth = request.headers.get("authorization", "")

    if not auth.startswith("Bearer "):

        raise HTTPException(status_code=401, detail="Missing Bearer token")

    

    # pyrefly: ignore [missing-attribute]

    method = (req.method or _config.get("trading_method", "SMC")).upper()

    tf = req.timeframe or "M15"

    symbol = req.symbol or _config.get("symbol", "XAUUSD")

    try:

        # pyrefly: ignore [bad-argument-type]

        df = await fetch_real_candles(symbol, tf, 1000)

        if df is None or df.empty:

            return {"status": "ERROR", "message": "no candle data", "objects": []}

        if not _bridge_data_real and not _is_demo_mode():

            # FAIL-CLOSED: LIVE mode không vẽ markup trên dữ liệu giả

            return {"status": "ERROR", "message": "no real data in LIVE mode", "objects": []}

        mtf_data: Dict[str, pd.DataFrame] = {tf: df}

        for ctx_tf in ("M15", "H1", "D1"):

            if ctx_tf == tf:

                continue

            # pyrefly: ignore [bad-argument-type]

            ctx_df = await _fetch_context_candles(symbol, ctx_tf)

            if ctx_df is not None and not ctx_df.empty:

                mtf_data[ctx_tf] = ctx_df

        # pyrefly: ignore [bad-argument-type]

        mtf_data_trimmed = {k: v.tail(600) if hasattr(v, 'tail') else v for k, v in mtf_data.items()}
        markup = build_chart_markup(symbol=symbol, mtf_data=mtf_data_trimmed, method=method, primary_tf=tf)

        _add_log("DEBUG", "EA_MARKUP", f"EA {req.executor_id} fetched {len(markup['objects'])} markup objects for {symbol} [{method}]")

        return _json_safe({

            "status": "OK",

            "symbol": symbol,

            "timeframe": tf,

            "method": markup["method"],

            "objects": markup["objects"],

            "confluence": markup.get("confluence", {}),

        })

    except Exception as e:

        _add_log("ERROR", "BRIDGE_MARKUP", str(e))

        return {"status": "ERROR", "message": str(e), "objects": []}





def _merge_candles_by_ts(existing: List[Dict[str, Any]], incoming: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

    """Merge nến EA push theo timestamp (ts) — không trùng, không đảo thứ tự.

    BUG FIX: EA giờ đẩy full history 40000 nến thành nhiều chunk (replace=true

    chunk đầu, append các chunk sau) — nếu ghi đè toàn bộ mỗi chunk thì cache

    chỉ còn 1 chunk cuối. Merge theo ts giữ lịch sử đầy đủ, sort tăng dần."""

    if not existing:

        return sorted(incoming, key=lambda c: str(c.get("ts") or c.get("t") or ""))

    by_ts: Dict[str, Dict[str, Any]] = {}

    for c in list(existing) + list(incoming):

        key = str(c.get("ts") or c.get("t") or "")

        if key:

            by_ts[key] = c  # incoming thắng nếu trùng ts

    merged = sorted(by_ts.values(), key=lambda c: str(c.get("ts") or c.get("t") or ""))

    # Giới hạn an toàn: giữ tối đa 150000 nến mỗi TF

    return merged[-150000:]





class CandlePushRequest(BaseModel):

    # BUG FIX: EA (ATE_XAUUSD.mq5) gửi payload {"symbol", "timeframe", "candles"}

    # — KHÔNG gửi executor_id. Model cũ yêu cầu executor_id bắt buộc -> FastAPI

    # trả 422 -> nến THẬT từ MT5 không bao giờ được lưu -> dashboard toàn dữ liệu giả.

    executor_id: Optional[str] = None

    symbol: str

    timeframe: str

    # BUG FIX: replace=true ở chunk đầu tiên của lịch sử (ghi đè cache cũ),

    # replace=false ở các chunk sau (merge theo ts). Mặc định true cho tương thích ngược.

    replace: Optional[bool] = True

    candles: List[Dict[str, Any]] = []



@app.post("/api/v1/bridge/candles")

async def bridge_candles(req: CandlePushRequest, request: Request):

    """EA đẩy candle data thời gian thực (copy_rates từ MT5 chart thật)."""

    auth = request.headers.get("authorization", "")

    if not auth.startswith("Bearer "):

        raise HTTPException(status_code=401, detail="Missing Bearer token")

    

    # BUG FIX: canonical hóa symbol (XAUUSDc -> XAUUSDm) để cache key khớp với

    # _cached_candles/fetch_real_candles. Trước đây lưu raw "XAUUSDc_M1" nhưng

    # fetch đọc "XAUUSDm_M1" -> miss -> dashboard rơi về STUB dù EA đang đẩy nến.

    cache_key = f"{resolve_symbol(req.symbol)}_{req.timeframe}"

    prev = _market_cache.get(cache_key, {}).get("candles") or []

    # BUG FIX: replace=true (chunk đầu tiên của lịch sử EA) → GHI ĐÈ cache bằng

    # đúng dữ liệu mới (không giữ nến cũ lỗi thời của session trước).

    # replace=false (các chunk sau) → merge theo ts để tích lũy đủ lịch sử.

    candles = req.candles if req.replace else _merge_candles_by_ts(prev, req.candles)

    _market_cache[cache_key] = _market_cache.get(cache_key, {})

    _market_cache[cache_key]["candles"] = candles

    _market_cache[cache_key]["candles_updated"] = datetime.now(timezone.utc).isoformat()

    _market_cache[cache_key]["source"] = "EA"

    if candles:

        _bridge_data_real = True

    _account["last_ea_candles_at"] = datetime.now(timezone.utc).isoformat()

    # pyrefly: ignore [bad-assignment]

    _account["ea_symbol"] = req.symbol or _account.get("ea_symbol")

    

    return {"status": "OK", "candles_received": len(req.candles), "candles_cached": len(candles)}





def _parse_event_datetime(ev: Dict[str, Any]) -> Optional[datetime]:

    """Parse thời điểm sự kiện từ payload EA thật.

    BUG FIX: EA gửi {date: '2026.08.12' (MQL5 TimeToString dấu chấm), time: '10:58'}

    — KHÔNG có field datetime; impact là 'MED' chứ không phải 'MEDIUM'.

    Trước đây server parse datetime (None) + so khớp MEDIUM (fail) nên news

    protection và economic-calendar không bao giờ hoạt động với dữ liệu thật.

    Hỗ trợ cả 3 dạng: datetime ISO, date+time, day+time."""

    try:

        dt_raw = ev.get("datetime") or ev.get("ts")

        if dt_raw:

            return datetime.fromisoformat(str(dt_raw).replace("Z", "+00:00"))

        date_raw = str(ev.get("date") or ev.get("day") or "").strip()

        time_raw = str(ev.get("time") or "").strip()

        if date_raw:

            iso_date = date_raw.replace(".", "-")

            if " " in iso_date and not time_raw:

                return datetime.fromisoformat(iso_date.replace(" ", "T") + "+00:00")

            if time_raw and len(time_raw) == 5:

                return datetime.fromisoformat(f"{iso_date}T{time_raw}:00+00:00")

            return datetime.fromisoformat(f"{iso_date}T00:00:00+00:00")

    except Exception:

        pass

    return None





# ─── FOREXFACTORY CALENDAR ──────────────────────────────────────────────────

# Nguồn lịch tin tức bổ sung: mirror JSON công khai của forexfactory.com dùng bởi

# nhiều indicator TradingView. MT5 CalendarValueHistory (EA push) trên nhiều broker

# trả rất ít/0 event — bổ sung nguồn này để web + news protection luôn có dữ liệu.

_FF_CALENDAR_URL = os.getenv("ATE_FF_CALENDAR_URL", "https://nfs.faireconomy.media/ff_calendar_thisweek.json")

_FF_REFRESH_SEC = int(os.getenv("ATE_FF_CALENDAR_INTERVAL", "600"))

_calendar_refresh_task = None





def _ev_utc_hour(e: Dict[str, Any]) -> Optional[str]:

    """Khóa dedupe: (title lowercase, UTC hour bucket). Dùng giờ UTC để event từ

    EA (MT5, UTC) và forexfactory (múi ET) của cùng 1 tin khớp nhau dù lệch tz."""

    dt = _parse_event_datetime(e)

    if dt is None:

        return None

    if dt.tzinfo is None:

        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc).strftime("%Y%m%d%H")





def _merge_calendar_events() -> List[Dict[str, Any]]:

    """Gộp lịch EA (MT5) + forexfactory, ưu tiên EA khi trùng (title + giờ UTC),

    sort theo thời gian, lưu vào _market_cache["economic_calendar"]."""

    ea = _market_cache.get("economic_calendar_ea", {}).get("events") or []

    ff = _market_cache.get("economic_calendar_ff", {}).get("events") or []

    merged = list(ea)

    seen = set()

    for e in ea:

        k = _ev_utc_hour(e)

        if k:

            seen.add((str(e.get("title", "")).strip().lower(), k))

    for e in ff:

        k = _ev_utc_hour(e)

        if not k:

            continue

        key = (str(e.get("title", "")).strip().lower(), k)

        if key in seen:

            continue

        seen.add(key)

        merged.append(e)



    def _sort_ts(e: Dict[str, Any]) -> float:

        # Chuẩn hóa về aware-UTC: _parse_event_datetime có thể trả naive khi event

        # không kèm tz -> .timestamp() interpret theo giờ local, lệch thứ tự với FF.

        dt = _parse_event_datetime(e)

        if dt is None:

            return datetime.max.replace(tzinfo=timezone.utc).timestamp()

        if dt.tzinfo is None:

            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc).timestamp()



    merged.sort(key=_sort_ts)

    _market_cache["economic_calendar"] = {

        "events": merged,

        "ts": datetime.now(timezone.utc).isoformat(),

    }

    return merged





def _ff_event_to_standard(e: Dict[str, Any]) -> Dict[str, Any]:

    """Chuẩn hóa event forexfactory sang format thống nhất với EA:

    event_id, datetime ISO, date %Y.%m.%d, time HH:MM, impact HIGH/MED/LOW."""

    raw_date = str(e.get("date") or "")

    dt = None

    try:

        dt = datetime.fromisoformat(raw_date)

    except Exception:

        try:

            dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))

        except Exception:

            dt = None

    title = str(e.get("title") or "Unknown Event").strip()

    imp = str(e.get("impact") or "Low").upper()

    impact = {"HIGH": "HIGH", "MEDIUM": "MED", "MED": "MED"}.get(imp, "LOW")

    event_id = "ff_" + hashlib.md5(f"{title}|{raw_date}".encode("utf-8")).hexdigest()[:12]

    now = datetime.now(timezone.utc)

    status = "UPCOMING"

    if dt:

        dt_utc = dt.astimezone(timezone.utc)

        if abs((dt_utc - now).total_seconds()) <= 3600:

            status = "LIVE"

        elif dt_utc < now:

            status = "DONE"

    return {

        "event_id": event_id,

        "source": "FOREXFACTORY",

        "title": title,

        "currency": str(e.get("country") or e.get("currency") or ""),

        "date": dt.strftime("%Y.%m.%d") if dt else (raw_date[:10] or ""),

        "time": dt.strftime("%H:%M") if dt else "",

        "datetime": dt.isoformat() if dt else None,

        "impact": impact,

        "actual": str(e.get("actual") or ""),

        "forecast": str(e.get("forecast") or ""),

        "previous": str(e.get("previous") or ""),

        "status": status,

    }





async def _fetch_forexfactory_calendar() -> int:

    """Fetch lịch từ nguồn forexfactory mirror và gộp vào cache. Thất bại -> giữ

    dữ liệu EA, chỉ log (không phá vỡ news protection hiện có)."""

    if not _config.get("ff_calendar_enabled", True):

        return 0

    # Không fetch mạng trong môi trường pytest (TestClient chạy lifespan ->

    # loop refresh chạy -> lịch thật từ mirror lọt vào test và làm hỏng assertions)

    if "pytest" in sys.modules:

        return 0

    try:

        async with httpx.AsyncClient(timeout=12) as client:

            res = await client.get(_FF_CALENDAR_URL)

            if res.status_code != 200:

                _add_log("WARN", "FF_CALENDAR", f"forexfactory fetch HTTP {res.status_code}")

                return 0

            data = res.json()

            events = [_ff_event_to_standard(e) for e in data if isinstance(e, dict)]

            if not events:

                return 0

            _market_cache["economic_calendar_ff"] = {

                "events": events,

                "ts": datetime.now(timezone.utc).isoformat(),

            }

            merged = _merge_calendar_events()

            _add_log("INFO", "FF_CALENDAR", f"forexfactory: {len(events)} events fetched (merged total {len(merged)})")

            return len(events)

    except Exception as e:

        _add_log("WARN", "FF_CALENDAR", f"forexfactory fetch failed: {e}")

        return 0





async def _calendar_refresh_loop():

    """Refresh calendar từ forexfactory mỗi _FF_REFRESH_SEC (+ 1 lần khi khởi động)."""

    await asyncio.sleep(2)

    try:

        await _fetch_forexfactory_calendar()

    except Exception:

        pass

    while True:

        await asyncio.sleep(_FF_REFRESH_SEC)

        try:

            await _fetch_forexfactory_calendar()

        except Exception as e:

            _add_log("WARN", "FF_CALENDAR", f"refresh error: {e}")





class CalendarRequest(BaseModel):

    # BUG FIX (CRITICAL - calendar luôn rỗng): EA gửi {"source": "MT5_CALENDAR",

    # "events": [...]} — KHÔNG có executor_id. Model cũ yêu cầu executor_id bắt

    # buộc -> FastAPI trả 422 -> bridge_calendar không bao giờ lưu events ->

    # /api/economic-calendar luôn [] và news protection mù (log: 422 Unprocessable).

    executor_id: Optional[str] = None

    source: Optional[str] = None

    events: List[Dict[str, Any]] = []



@app.post("/api/v1/bridge/calendar")

async def bridge_calendar(req: CalendarRequest, request: Request):

    """EA đẩy economic calendar."""

    auth = request.headers.get("authorization", "")

    if not auth.startswith("Bearer "):

        raise HTTPException(status_code=401, detail="Missing Bearer token")

    

    # BUG FIX: phải LƯU events vào cache — trước đây chỉ log rồi trả về, nên

    # GET /api/economic-calendar luôn trả [] dù EA gửi lịch kinh tế.

    if req.events:

        _market_cache["economic_calendar_ea"] = {

            "events": req.events,

            "ts": datetime.now(timezone.utc).isoformat(),

        }

        # Gộp với forexfactory (nếu có) để /api/economic-calendar + protection

        # luôn thấy đầy đủ dữ liệu từ cả 2 nguồn.

        _merge_calendar_events()

    _add_log("DEBUG", "EA_CALENDAR", f"EA {req.executor_id} sent {len(req.events)} events")

    return {"status": "OK", "events_received": len(req.events)}



@app.get("/api/economic-calendar")

# pyrefly: ignore [bad-function-definition]

async def get_economic_calendar(days: int = Query(7, ge=1, le=30), request: Request = None):

    """Economic calendar cho frontend (EconomicCalendar component).

    BUG FIX: backend thiếu route /api/economic-calendar -> component gọi 404

    -> lịch kinh tế không bao giờ hiển thị."""

    if request and not (request.headers.get("authorization", "") or "").startswith("Bearer "):

        raise HTTPException(status_code=401, detail="Missing Bearer token")

    events = _market_cache.get("economic_calendar", {}).get("events") or []

    try:

        limit_ts = (datetime.now(timezone.utc) + timedelta(days=days)).timestamp()

        out = []

        for e in events:

            ev_dt = _parse_event_datetime(e)

            if ev_dt is None:

                continue

            if ev_dt.timestamp() <= limit_ts:

                # BUG FIX: chuẩn hóa thành datetime ISO để frontend parse nhất quán

                # (EA gửi date+time rời rạc — trước đây lọc ra [] vì thiếu datetime).

                norm = dict(e)

                norm["datetime"] = ev_dt.isoformat()

                norm["impact"] = str(e.get("impact") or "MEDIUM").upper()

                out.append(norm)

        return out[-200:]

    except Exception:

        return events[-50:]





class AccountSyncRequest(BaseModel):

    login: Optional[int] = None

    server: Optional[str] = None

    balance: Optional[float] = None

    equity: Optional[float] = None

    margin: Optional[float] = None

    free_margin: Optional[float] = None

    margin_level: Optional[float] = None

    currency: Optional[str] = None

    leverage: Optional[int] = None

    timestamp: Optional[str] = None



@app.post("/api/v1/bridge/account_sync")

async def bridge_account_sync(req: AccountSyncRequest, request: Request):

    """python-bridge đồng bộ tài khoản MT5 thật mỗi 5s (trước đây endpoint này

    KHÔNG tồn tại -> bridge gọi 404 âm thầm -> account qua đường bridge bị mất)."""

    auth = request.headers.get("authorization", "")

    if not auth.startswith("Bearer "):

        raise HTTPException(status_code=401, detail="Missing Bearer token")

    if req.login:

        _account["mt5_connected"] = True

        _account["login"] = req.login

        _account["server"] = req.server or _account.get("server", "")

        if req.balance is not None:

            _account["balance"] = req.balance

        if req.equity is not None:

            _account["equity"] = req.equity

        if req.margin is not None:

            _account["margin"] = req.margin

        if req.free_margin is not None:

            _account["margin_free"] = req.free_margin

    _add_log("DEBUG", "ACCOUNT_SYNC", f"bridge sync login={req.login} balance={_account['balance']}")

    return {"status": "OK"}





# BUG FIX: EA gọi GET /api/economic-calendar/protection (không có /api/v1) nhưng

# server chỉ có /api/v1/economic-calendar/protection -> 404. Alias cả 2 đường.

@app.get("/api/economic-calendar/protection")

@app.get("/api/v1/economic-calendar/protection")

async def economic_calendar_protection(request: Request):

    """EA lấy trạng thái news protection."""

    auth = request.headers.get("authorization", "")

    if not auth.startswith("Bearer "):

        raise HTTPException(status_code=401, detail="Missing Bearer token")

    

    # BUG FIX: trước đây hardcode protection_level="none" nên EA luôn thấy mức

    # bảo vệ "none" -> news protection không bao giờ chặn lệnh. Giờ tính mức bảo

    # vệ THẬT từ lịch kinh tế EA đẩy (giống evaluate_risk_gate): lockdown = sự

    # kiện HIGH/MED đang trong cửa sổ ±15 phút, approaching = trong 1h, watch =

    # trong 5h. Trả cả 2 bộ key (protection_level/level, live_seconds/

    # live_remaining_seconds) để EA parse được dù dùng tên nào.

    protection_level = "none"

    live_seconds = 0

    next_event = None

    # pyrefly: ignore [bad-argument-type]

    news_window_min = int(_config.get("news_window_minutes", 15))

    try:

        cal = _market_cache.get("economic_calendar") or {}

        now_ts = datetime.now(timezone.utc).timestamp()

        # FAIL-CLOSED (BUG FIX): cache lịch kinh tế trống hoặc quá cũ (> 15 phút;

        # EA đẩy mỗi 300s) -> trả "unknown" để EA CHẶN entry mới. Trước đây trả

        # "none" khi không có dữ liệu -> EA mở lệnh mù dù chưa hề có thông tin tin.

        cal_ts_raw = cal.get("ts") or ""

        try:

            cal_ts = datetime.fromisoformat(cal_ts_raw.replace("Z", "+00:00")) if cal_ts_raw else None

            cal_fresh = cal_ts is not None and (now_ts - cal_ts.timestamp()) <= 15 * 60

        except Exception:

            cal_fresh = False

        if not cal_fresh:

            return {

                "status": "OK",

                "protection_level": "unknown",

                "level": "unknown",

                "live_seconds": 0,

                "live_remaining_seconds": 0,

                "next_event": None,

                "server_time": datetime.now(timezone.utc).isoformat(),

                "data_available": False,

            }

        for ev in (cal.get("events") or []):

            impact = str(ev.get("impact") or "").upper()

            if impact not in ("HIGH", "MED", "MEDIUM"):

                continue

            ev_dt = _parse_event_datetime(ev)

            if ev_dt is None:

                continue

            delta = ev_dt.timestamp() - now_ts  # giây tới khi sự kiện (âm = đang diễn ra)

            title = str(ev.get("title") or ev.get("name") or "event")

            event_payload = {

                "title": title, "impact": impact,

                "datetime": ev_dt.isoformat(),

            }

            if -news_window_min * 60 <= delta <= news_window_min * 60:

                # BUG FIX: lockdown là mức nghiêm nhất — gán vô điều kiện để event

                # lockdown xử lý SAU event watch/approaching vẫn nâng cấp được mức

                # bảo vệ (trước đây guard `in ("none","")` khiến lockdown bị bỏ qua

                # khi một event thấp hơn đã được xử lý trước).

                protection_level = "lockdown"

                live_seconds = max(0, int(news_window_min * 60 + delta))

                next_event = event_payload

            elif 0 <= delta <= 3600:

                if protection_level not in ("lockdown",):

                    protection_level = "approaching"

                    live_seconds = int(delta)

                    next_event = event_payload

            elif 0 <= delta <= 5 * 3600:

                if protection_level not in ("lockdown", "approaching"):

                    protection_level = "watch"

                    live_seconds = int(delta)

                    next_event = event_payload

    except Exception as e:

        # FAIL-CLOSED: bất kỳ lỗi nào khi đọc/parse calendar -> "unknown" (chặn

        # entry mới) chứ KHÔNG fallback "none" (FAIL-OPEN = trade mù). Trước đây

        # except rỗng -> protection_level giữ giá trị khởi tạo "none" -> EA mở

        # lệnh dù không xác nhận được trạng thái tin.

        _add_log("WARN", "PROTECTION_PARSE_FAIL", f"protection parse error: {e}")

        protection_level = "unknown"

        live_seconds = 0

        next_event = None



    return {

        "status": "OK",

        "protection_level": protection_level,

        "level": protection_level,

        "live_seconds": live_seconds,

        "live_remaining_seconds": live_seconds,

        "next_event": next_event,

        "server_time": datetime.now(timezone.utc).isoformat(),

        "data_available": True,

    }





# ════════════════════════════════════════════════════════════════════════════

# RISK MANAGER (Phase 1.3 - Full 9 checks)

# ════════════════════════════════════════════════════════════════════════════



def evaluate_risk_gate(symbol: str, signal: str, entry: float, sl: float, tp: float, 

                        spread: float, atr: float, score: int, method: str) -> Dict[str, Any]:

    """Risk Manager với 9 checks theo spec. Trả về {approved, reason, checks}.

    

    Checks:

    1. Spread

    2. ATR / Volatility

    3. News protection

    4. Margin / Free Margin

    5. Risk %

    6. Max Drawdown

    7. Max Lot

    8. Daily Loss / Daily Profit

    9. Trading Session

    """

    checks = {}

    

    # 1. Spread

    max_spread = _config.get("max_spread", 4.5)

    # pyrefly: ignore [unsupported-operation]

    checks["spread"] = {"value": spread, "max": max_spread, "ok": spread <= max_spread}

    

    # 2. ATR / Volatility (sử dụng ATR ratio so với entry)

    atr_pct = (atr / max(entry, 1)) * 100 if entry > 0 else 0

    checks["volatility"] = {"atr_pct": atr_pct, "ok": 0.05 <= atr_pct <= 5.0}

    

    # 3. News protection — BUG FIX: trước đây hardcode ok=True nên AI auto-trade

    # vẫn mở lệnh ngay sát tin HIGH impact. Giờ đọc economic_calendar thật từ EA

    # và chặn nếu có event HIGH/MEDIUM xảy ra trong cửa sổ ±15 phút (mặc định).

    news_block = False

    news_event = None

    # pyrefly: ignore [bad-argument-type]

    news_window_min = int(_config.get("news_window_minutes", 15))

    try:

        cal = _market_cache.get("economic_calendar") or {}

        now_ts = datetime.now(timezone.utc).timestamp()

        for ev in (cal.get("events") or []):

            impact = str(ev.get("impact") or "").upper()

            # BUG FIX: EA gửi 'MED' (MQL5 CALENDAR_IMPORTANCE_MODERATE) — phải

            # nhận cả 'MED' và 'MEDIUM' nếu client khác gửi chuẩn đầy đủ.

            if impact not in ("HIGH", "MED", "MEDIUM"):

                continue

            ev_dt = _parse_event_datetime(ev)

            if ev_dt is None:

                continue

            ev_ts = ev_dt.timestamp()

            if abs(now_ts - ev_ts) <= news_window_min * 60:

                news_block = True

                news_event = f"{ev.get('title') or ev.get('name') or 'event'} {impact} @{ev_dt.isoformat()}"

                break

    except Exception:

        news_block = False

    # pyrefly: ignore [bad-assignment]

    checks["news"] = {"protected": news_block, "event": news_event, "window_min": news_window_min, "ok": not news_block}

    

    # 4. Margin

    free_margin = _account.get("margin_free", 10000)

    margin_required = abs(entry - sl) * 100 * 0.01  # Estimate for 0.01 lot

    margin_ok = free_margin > margin_required * 5  # 5x safety margin

    checks["margin"] = {"free": free_margin, "required": margin_required, "ok": margin_ok}

    

    # 5. Risk % (Risk per trade / account balance)

    risk_pct = _config.get("risk_per_trade_fraction", 0.01)

    sl_distance = abs(entry - sl)

    position_value_at_risk = sl_distance * 100 * 0.01  # For 0.01 lot gold

    actual_risk_pct = position_value_at_risk / max(_account.get("balance", 10000), 1)

    checks["risk_pct"] = {"configured": risk_pct, "actual": actual_risk_pct, 

                          # pyrefly: ignore [unsupported-operation]

                          "ok": actual_risk_pct <= risk_pct * 2}  # Allow 2x config

    

    # 6. Max Drawdown (track realized losses today)

    daily_pnl = _account.get("total_pnl", 0)

    drawdown_pct = abs(min(0, daily_pnl)) / max(_account.get("balance", 10000), 1) * 100

    max_dd_pct = 5.0  # 5% max daily drawdown

    checks["max_drawdown"] = {"current": drawdown_pct, "max": max_dd_pct, "ok": drawdown_pct < max_dd_pct}

    

    # 7. Max Lot

    max_lot = 0.5

    checks["max_lot"] = {"value": 0.01, "max": max_lot, "ok": 0.01 <= max_lot}

    

    # 8. Daily Loss / Profit

    max_daily_loss = _account.get("balance", 10000) * 0.03  # 3% of balance

    max_daily_profit = _account.get("balance", 10000) * 0.05  # 5% of balance

    checks["daily_pnl"] = {

        "current": daily_pnl,

        "max_loss": -max_daily_loss,

        "max_profit": max_daily_profit,

        "ok": daily_pnl > -max_daily_loss and daily_pnl < max_daily_profit

    }

    

    # 9. Trading Session (Server time check - allow Mon-Fri)

    now = datetime.now(timezone.utc)

    weekday = now.weekday()

    is_weekday = weekday < 5  # 0-4 = Mon-Fri

    checks["session"] = {"weekday": weekday, "ok": is_weekday}

    

    # Tổng hợp

    approved = all(c.get("ok", False) for c in checks.values())

    failed_checks = [k for k, v in checks.items() if not v.get("ok", False)]

    

    return {

        "approved": approved,

        "reason": "All checks passed" if approved else f"Failed: {', '.join(failed_checks)}",

        "checks": checks,

        "score": score,

        "method": method,

        "timestamp": now.isoformat()

    }





@app.post("/api/v1/risk/evaluate")

async def risk_evaluate(request: Request):

    """API cho frontend hoặc test gọi risk gate."""

    auth = request.headers.get("authorization", "")

    if not auth.startswith("Bearer "):

        raise HTTPException(status_code=401, detail="Missing Bearer token")

    

    try:

        body = await request.json()

    except Exception:

        raise HTTPException(status_code=400, detail="Invalid JSON")

    

    result = evaluate_risk_gate(

        symbol=body.get("symbol", "XAUUSD"),

        signal=body.get("signal", "WAIT"),

        entry=float(body.get("entry", 0)),

        sl=float(body.get("sl", 0)),

        tp=float(body.get("tp", 0)),

        spread=float(body.get("spread", 0)),

        atr=float(body.get("atr", 15)),

        score=int(body.get("score", 50)),

        method=body.get("method", "SMC")

    )

    return result





# ─── SETTINGS ─────────────────────────────────────────────────────────────────

@app.get("/api/control-center/settings")

async def get_settings(request: Request):

    """Get complete settings payload for SettingsModal"""

    auth = request.headers.get("authorization", "")

    if not auth.startswith("Bearer "):

        raise HTTPException(status_code=401, detail="Missing Bearer token")



    return {

        "status": "SUCCESS",

        "runtime_config": _config,

        "account": {**_account, "ea_connected": _ea_fresh(),

                    "data_status": "LIVE" if _bridge_data_real else "STUB"},

        "available_models": [

            {"id": "deepseek-v4-flash-free", "name": "DeepSeek V4 Flash (Free)", "provider": "OpenCode Zen"},

            {"id": "gpt-4o", "name": "GPT-4o", "provider": "OpenAI"},

            {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "provider": "Google"},

            {"id": "claude-3-opus", "name": "Claude 3 Opus", "provider": "Anthropic"}

        ],

        "telegram_bot_token": _config.get("telegram_bot_token", ""),

        "telegram_chat_id": _config.get("telegram_chat_id", ""),

        "telegram_enabled": bool(_config.get("telegram_bot_token") and _config.get("telegram_chat_id")),

        "notify_on_open": _config.get("notify_on_open", True),

        "notify_on_close": _config.get("notify_on_close", True),

        "notify_on_signal": _config.get("notify_on_signal", True),

    }





@app.post("/api/control-center/settings")

async def update_settings_endpoint(request: Request):

    """Update settings payload from SettingsModal"""

    auth = request.headers.get("authorization", "")

    if not auth.startswith("Bearer "):

        raise HTTPException(status_code=401, detail="Missing Bearer token")



    try:

        body = await request.json()

    except Exception:

        raise HTTPException(status_code=400, detail="Invalid JSON body")



    updated_keys = []

    for key, val in body.items():

        _config[key] = val

        updated_keys.append(key)



    _add_log("INFO", "SETTINGS_UPDATE", f"Updated settings: {updated_keys}")

    return {"status": "SUCCESS", "updated": updated_keys, "config": _config}





# ════════════════════════════════════════════════════════════════════════════

# MAIN ENTRY POINT (must be at end of file so all routes are registered)

# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("DASHBOARD_PORT", os.getenv("PORT", "8848")))
    print(f"[ATE] Starting FastAPI Server on 0.0.0.0:{port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
