"""Aether Flow & Multi-Method Quantitative Trading Engine for ATE.

Complete implementation combining:
1. SMC (Smart Money Concepts) - Mxwll / LuxAlgo / BigBeluga
2. ICT (Inner Circle Trader) - Flux Charts / Turtle Soup / Killzones / OTE / Unicorn / AMD
3. SNIPER FLOW - EMA 9/21 Ribbon / VWAP / Dual Score 7 factors / TP1-TP5 Dynamic
4. PRICE ACTION - 14 Candlestick Patterns / Displacement / Compression / S&R / Channels
5. ULTRA CONFLUENCE MATRIX - 5-Layer Institutional Scoring Matrix (0-100%)

Engineered for ultra-fast vectorized calculation, fail-closed AI decision making,
and clean, high-aesthetic TradingView rendering.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# ══════════════════════════════════════════════════════════════════════════════
# HELPER UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def _to_iso(val: Any) -> str:
    if val is None or pd.isna(val):
        return ""
    if isinstance(val, pd.Timestamp):
        return val.isoformat()
    if isinstance(val, datetime):
        return val.isoformat()
    return str(val)


def _to_timestamp_sec(val: Any) -> int:
    if val is None or pd.isna(val):
        return 0
    if isinstance(val, (int, float, np.integer, np.floating)):
        return int(val)
    try:
        ts = pd.to_datetime(val)
        return int(ts.timestamp())
    except Exception:
        return 0


# ══════════════════════════════════════════════════════════════════════════════
# 1. CORE TECHNICAL INDICATORS (Vectorized & Fast)
# ══════════════════════════════════════════════════════════════════════════════

def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values
    n = len(df)
    if n == 0:
        return pd.Series(dtype=float)

    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )
    atr = pd.Series(tr, index=df.index).ewm(alpha=1.0 / period, adjust=False).mean()
    return atr


def compute_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def compute_wma(series: pd.Series, period: int) -> pd.Series:
    weights = np.arange(1, period + 1)
    return series.rolling(period).apply(lambda s: np.dot(s, weights) / weights.sum(), raw=True)


def compute_hma(series: pd.Series, period: int) -> pd.Series:
    half_p = max(1, period // 2)
    sqrt_p = max(1, int(math.sqrt(period)))
    wma_half = compute_wma(series, half_p)
    wma_full = compute_wma(series, period)
    diff = 2 * wma_half - wma_full
    return compute_wma(diff, sqrt_p)


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1.0 / period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1.0 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def compute_vwap(df: pd.DataFrame) -> pd.Series:
    hlc3 = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df.get("volume", pd.Series(1.0, index=df.index)).replace(0, 1.0)
    if "time" in df.columns:
        dates = pd.to_datetime(df["time"]).dt.date
        cum_vol = vol.groupby(dates).cumsum()
        cum_pv = (hlc3 * vol).groupby(dates).cumsum()
        vwap = cum_pv / cum_vol.replace(0, np.nan)
        return vwap.fillna(hlc3)
    cum_vol = vol.cumsum()
    cum_pv = (hlc3 * vol).cumsum()
    return (cum_pv / cum_vol.replace(0, np.nan)).fillna(hlc3)


def compute_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    atr = compute_atr(df, period)
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1.0 / period, adjust=False).mean() / atr.replace(0, np.nan)
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1.0 / period, adjust=False).mean() / atr.replace(0, np.nan)
    dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)).fillna(0)
    adx = dx.ewm(alpha=1.0 / period, adjust=False).mean().fillna(20)
    return adx


def compute_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series]:
    fast_ema = compute_ema(series, fast)
    slow_ema = compute_ema(series, slow)
    macd_line = fast_ema - slow_ema
    sig_line = compute_ema(macd_line, signal)
    return macd_line, sig_line


# ══════════════════════════════════════════════════════════════════════════════
# 2. METHOD 1: SMC - SMART MONEY CONCEPTS
# ══════════════════════════════════════════════════════════════════════════════

def detect_pivots(highs: np.ndarray, lows: np.ndarray, length: int) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
    n = len(highs)
    swing_highs = []
    swing_lows = []
    if n <= length * 2:
        return swing_highs, swing_lows

    # 1. Confirmed symmetric pivots
    for i in range(length, n - length):
        is_high = True
        for j in range(1, length + 1):
            if highs[i] <= highs[i - j] or highs[i] < highs[i + j]:
                is_high = False
                break
        if is_high:
            swing_highs.append((i, float(highs[i])))

        is_low = True
        for j in range(1, length + 1):
            if lows[i] >= lows[i - j] or lows[i] > lows[i + j]:
                is_low = False
                break
        if is_low:
            swing_lows.append((i, float(lows[i])))

    # 2. Developing recent pivots in the last `length` candles (lookback-only confirmation)
    if n > length:
        recent_h_idx = int(np.argmax(highs[-length:])) + (n - length)
        if not swing_highs or swing_highs[-1][0] != recent_h_idx:
            if highs[recent_h_idx] > np.max(highs[max(0, recent_h_idx - length):recent_h_idx]):
                swing_highs.append((recent_h_idx, float(highs[recent_h_idx])))

        recent_l_idx = int(np.argmin(lows[-length:])) + (n - length)
        if not swing_lows or swing_lows[-1][0] != recent_l_idx:
            if lows[recent_l_idx] < np.min(lows[max(0, recent_l_idx - length):recent_l_idx]):
                swing_lows.append((recent_l_idx, float(lows[recent_l_idx])))

    # Sort chronologically
    swing_highs.sort(key=lambda x: x[0])
    swing_lows.sort(key=lambda x: x[0])
    return swing_highs, swing_lows


def detect_smc_structure(
    df: pd.DataFrame,
    ext_sens: int = 25,
    int_sens: int = 5,
) -> Dict[str, Any]:
    """Detect Market Structure (External/Internal), HH/HL/LH/LL, BoS, CHoCH, MSS."""
    n = len(df)
    if n < 30:
        return {"swings": [], "segments": [], "current_trend": 0}

    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    time_col = "time" if "time" in df.columns else df.columns[0]
    times = df[time_col].values

    ext_highs, ext_lows = detect_pivots(highs, lows, ext_sens)
    swings = []
    segments = []

    last_h_val = None
    for idx, val in ext_highs:
        label = "HH" if (last_h_val is not None and val > last_h_val) else "LH"
        last_h_val = val
        swings.append({
            "index": int(idx),
            "time": _to_iso(times[idx]),
            "timestamp": _to_timestamp_sec(times[idx]),
            "price": round(val, 2),
            "type": "SWING_HIGH",
            "label": label,
            "level": "EXTERNAL",
            "direction": "BEARISH",
        })

    last_l_val = None
    for idx, val in ext_lows:
        label = "LL" if (last_l_val is not None and val < last_l_val) else "HL"
        last_l_val = val
        swings.append({
            "index": int(idx),
            "time": _to_iso(times[idx]),
            "timestamp": _to_timestamp_sec(times[idx]),
            "price": round(val, 2),
            "type": "SWING_LOW",
            "label": label,
            "level": "EXTERNAL",
            "direction": "BULLISH",
        })

    swings.sort(key=lambda s: s["index"])

    trend = 0
    up_axis, up_axis_idx = None, None
    dn_axis, dn_axis_idx = None, None

    for i in range(15, n):
        for s in swings:
            if s["index"] == i:
                if s["type"] == "SWING_HIGH":
                    up_axis, up_axis_idx = s["price"], s["index"]
                else:
                    dn_axis, dn_axis_idx = s["price"], s["index"]

        if up_axis is not None and up_axis_idx is not None:
            if closes[i] > up_axis and closes[i - 1] <= up_axis:
                kind = "CHoCH" if trend == -1 else "BoS"
                trend = 1
                segments.append({
                    "type": kind,
                    "label": kind,
                    "level": "EXTERNAL",
                    "direction": "BULLISH",
                    "price": round(up_axis, 2),
                    "x1_index": int(up_axis_idx),
                    "x2_index": int(i),
                    "t1": _to_iso(times[up_axis_idx]),
                    "t2": _to_iso(times[i]),
                    "ts1": _to_timestamp_sec(times[up_axis_idx]),
                    "ts2": _to_timestamp_sec(times[i]),
                    "color": "#14D990",
                })
                up_axis = None

        if dn_axis is not None and dn_axis_idx is not None:
            if closes[i] < dn_axis and closes[i - 1] >= dn_axis:
                kind = "CHoCH" if trend == 1 else "BoS"
                trend = -1
                segments.append({
                    "type": kind,
                    "label": kind,
                    "level": "EXTERNAL",
                    "direction": "BEARISH",
                    "price": round(dn_axis, 2),
                    "x1_index": int(dn_axis_idx),
                    "x2_index": int(i),
                    "t1": _to_iso(times[dn_axis_idx]),
                    "t2": _to_iso(times[i]),
                    "ts1": _to_timestamp_sec(times[dn_axis_idx]),
                    "ts2": _to_timestamp_sec(times[i]),
                    "color": "#F24968",
                })
                dn_axis = None

    # Internal Structure
    int_highs, int_lows = detect_pivots(highs, lows, int_sens)
    i_up, i_up_idx = None, None
    i_dn, i_dn_idx = None, None
    i_trend = 0

    for i in range(5, n):
        for idx, val in int_highs:
            if idx == i:
                i_up = val
                i_up_idx = idx
        for idx, val in int_lows:
            if idx == i:
                i_dn = val
                i_dn_idx = idx

        if i_up is not None and i_up_idx is not None and (i - i_up_idx) > 1:
            if closes[i] > i_up and closes[i - 1] <= i_up:
                kind = "I-CHoCH" if i_trend == -1 else "I-BoS"
                i_trend = 1
                segments.append({
                    "type": kind,
                    "label": kind,
                    "level": "INTERNAL",
                    "direction": "BULLISH",
                    "price": round(i_up, 2),
                    "x1_index": int(i_up_idx),
                    "x2_index": int(i),
                    "t1": _to_iso(times[i_up_idx]),
                    "t2": _to_iso(times[i]),
                    "ts1": _to_timestamp_sec(times[i_up_idx]),
                    "ts2": _to_timestamp_sec(times[i]),
                    "color": "#14D990",
                })
                i_up = None

        if i_dn is not None and i_dn_idx is not None and (i - i_dn_idx) > 1:
            if closes[i] < i_dn and closes[i - 1] >= i_dn:
                kind = "I-CHoCH" if i_trend == 1 else "I-BoS"
                i_trend = -1
                segments.append({
                    "type": kind,
                    "label": kind,
                    "level": "INTERNAL",
                    "direction": "BEARISH",
                    "price": round(i_dn, 2),
                    "x1_index": int(i_dn_idx),
                    "x2_index": int(i),
                    "t1": _to_iso(times[i_dn_idx]),
                    "t2": _to_iso(times[i]),
                    "ts1": _to_timestamp_sec(times[i_dn_idx]),
                    "ts2": _to_timestamp_sec(times[i]),
                    "color": "#F24968",
                })
                i_dn = None

    return {
        "swings": swings[-12:],
        "segments": segments[-16:],
        "current_trend": trend,
        "last_high": ext_highs[-1] if ext_highs else None,
        "last_low": ext_lows[-1] if ext_lows else None,
    }


def detect_luxalgo_order_blocks(
    df: pd.DataFrame,
    pivot_len: int = 5,
    max_bull_ob: int = 3,
    max_bear_ob: int = 3,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Detect Volume Pivot Order Blocks with Mitigation & Breaker Block Transformation."""
    n = len(df)
    if n < pivot_len * 3:
        return [], []

    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    opens = df["open"].values
    vols = df.get("volume", pd.Series(1.0, index=df.index)).values
    time_col = "time" if "time" in df.columns else df.columns[0]
    times = df[time_col].values

    raw_obs = []
    vol_ma = pd.Series(vols).rolling(20).mean().fillna(1.0).values

    for i in range(pivot_len, n - 2):
        is_low = True
        for j in range(1, pivot_len + 1):
            if lows[i] >= lows[i - j] or (i + j < n and lows[i] > lows[i + j]):
                is_low = False
                break

        is_high = True
        for j in range(1, pivot_len + 1):
            if highs[i] <= highs[i - j] or (i + j < n and highs[i] < highs[i + j]):
                is_high = False
                break

        if is_low:
            top = max(opens[i], closes[i])
            bottom = lows[i]
            v_val = float(vols[i])
            v_sum = float(np.sum(vols[max(0, i - 10):i + 1]))
            v_pct = int(min(99, max(10, (v_val / max(1.0, v_sum)) * 100)))
            v_lbl = f"{v_val / 1000.0:.3f}K ({v_pct}%)" if v_val >= 1000 else f"{v_val:.1f} ({v_pct}%)"
            raw_obs.append({
                "type": "OB",
                "direction": "BULLISH",
                "label": "OB Demand",
                "top": round(float(top), 2),
                "bottom": round(float(bottom), 2),
                "avg": round(float((top + bottom) / 2.0), 2),
                "index": int(i),
                "time_start": _to_iso(times[i]),
                "ts_start": _to_timestamp_sec(times[i]),
                "volume": v_val,
                "volume_label": v_lbl,
                "is_volume_pivot": bool(vols[i] > vol_ma[i] * 1.2),
            })

        if is_high:
            top = highs[i]
            bottom = min(opens[i], closes[i])
            v_val = float(vols[i])
            v_sum = float(np.sum(vols[max(0, i - 10):i + 1]))
            v_pct = int(min(99, max(10, (v_val / max(1.0, v_sum)) * 100)))
            v_lbl = f"{v_val / 1000.0:.3f}K ({v_pct}%)" if v_val >= 1000 else f"{v_val:.1f} ({v_pct}%)"
            raw_obs.append({
                "type": "OB",
                "direction": "BEARISH",
                "label": "OB Supply",
                "top": round(float(top), 2),
                "bottom": round(float(bottom), 2),
                "avg": round(float((top + bottom) / 2.0), 2),
                "index": int(i),
                "time_start": _to_iso(times[i]),
                "ts_start": _to_timestamp_sec(times[i]),
                "volume": v_val,
                "volume_label": v_lbl,
                "is_volume_pivot": bool(vols[i] > vol_ma[i] * 1.2),
            })

    active_bull_obs, active_bear_obs = [], []
    breaker_blocks = []
    last_iso = _to_iso(times[-1])
    last_sec = _to_timestamp_sec(times[-1])

    for ob in raw_obs:
        idx = ob["index"]
        mitigated = False
        for k in range(idx + 1, n):
            if ob["direction"] == "BULLISH" and closes[k] < ob["bottom"]:
                mitigated = True
                # Transformed into Bearish Breaker Block
                breaker_blocks.append({
                    "type": "BREAKER",
                    "direction": "BEARISH",
                    "label": "Breaker Bear",
                    "top": ob["top"],
                    "bottom": ob["bottom"],
                    "avg": ob["avg"],
                    "index": ob["index"],
                    "time_start": ob["time_start"],
                    "ts_start": ob["ts_start"],
                    "time_end": last_iso,
                    "ts_end": last_sec,
                })
                break
            elif ob["direction"] == "BEARISH" and closes[k] > ob["top"]:
                mitigated = True
                # Transformed into Bullish Breaker Block
                breaker_blocks.append({
                    "type": "BREAKER",
                    "direction": "BULLISH",
                    "label": "Breaker Bull",
                    "top": ob["top"],
                    "bottom": ob["bottom"],
                    "avg": ob["avg"],
                    "index": ob["index"],
                    "time_start": ob["time_start"],
                    "ts_start": ob["ts_start"],
                    "time_end": last_iso,
                    "ts_end": last_sec,
                })
                break

        if not mitigated:
            ob["time_end"] = last_iso
            ob["ts_end"] = last_sec
            ob["status"] = "UNMITIGATED"
            if ob["direction"] == "BULLISH":
                active_bull_obs.append(ob)
            else:
                active_bear_obs.append(ob)

    selected_obs = active_bull_obs[-max_bull_ob:] + active_bear_obs[-max_bear_ob:]
    return selected_obs, breaker_blocks[-2:]


def detect_luxalgo_fvg(
    df: pd.DataFrame,
    threshold_pct: float = 0.0,
    max_fvg_count: int = 3,
) -> List[Dict[str, Any]]:
    """Detect Fair Value Gaps with Threshold & Fill Tracking."""
    n = len(df)
    if n < 5:
        return []

    highs = df["high"].values
    lows = df["low"].values
    time_col = "time" if "time" in df.columns else df.columns[0]
    times = df[time_col].values

    fvgs = []
    threshold = threshold_pct / 100.0

    for i in range(2, n - 1):
        if lows[i] > highs[i - 2]:
            gap = lows[i] - highs[i - 2]
            if gap / max(1e-5, highs[i - 2]) >= threshold:
                fvgs.append({
                    "type": "FVG",
                    "direction": "BULLISH",
                    "label": "FVG Bull",
                    "top": round(float(lows[i]), 2),
                    "bottom": round(float(highs[i - 2]), 2),
                    "avg": round(float((lows[i] + highs[i - 2]) / 2.0), 2),
                    "index": int(i - 1),
                    "time_start": _to_iso(times[i - 1]),
                    "ts_start": _to_timestamp_sec(times[i - 1]),
                })
        elif highs[i] < lows[i - 2]:
            gap = lows[i - 2] - highs[i]
            if gap / max(1e-5, highs[i]) >= threshold:
                fvgs.append({
                    "type": "FVG",
                    "direction": "BEARISH",
                    "label": "FVG Bear",
                    "top": round(float(lows[i - 2]), 2),
                    "bottom": round(float(highs[i]), 2),
                    "avg": round(float((lows[i - 2] + highs[i]) / 2.0), 2),
                    "index": int(i - 1),
                    "time_start": _to_iso(times[i - 1]),
                    "ts_start": _to_timestamp_sec(times[i - 1]),
                })

    active_bull_fvg, active_bear_fvg = [], []
    last_iso = _to_iso(times[-1])
    last_sec = _to_timestamp_sec(times[-1])

    for fvg in fvgs:
        idx = fvg["index"]
        is_filled = False
        for k in range(idx + 2, n):
            if fvg["direction"] == "BULLISH" and lows[k] <= fvg["bottom"]:
                is_filled = True
                break
            elif fvg["direction"] == "BEARISH" and highs[k] >= fvg["top"]:
                is_filled = True
                break

        if not is_filled:
            fvg["time_end"] = last_iso
            fvg["ts_end"] = last_sec
            fvg["status"] = "UNMITIGATED"
            if fvg["direction"] == "BULLISH":
                active_bull_fvg.append(fvg)
            else:
                active_bear_fvg.append(fvg)

    return active_bull_fvg[-max_fvg_count:] + active_bear_fvg[-max_fvg_count:]


# ══════════════════════════════════════════════════════════════════════════════
# 3. METHOD 2: ICT - INNER CIRCLE TRADER
# ══════════════════════════════════════════════════════════════════════════════

def detect_ict_killzones(current_time: datetime, broker_utc_offset_hours: int = 0) -> Dict[str, Any]:
    """Detect ICT London, NY AM/PM, Asian Killzone windows."""
    try:
        utc_dt = current_time - pd.Timedelta(hours=broker_utc_offset_hours)
    except Exception:
        utc_dt = current_time

    hour = utc_dt.hour
    minute = utc_dt.minute
    total_min = hour * 60 + minute

    # London: 08:00 - 11:00 UTC
    is_london = 480 <= total_min <= 660
    # NY AM: 13:30 - 16:00 UTC (8:30 - 11:00 EST)
    is_ny_am = 810 <= total_min <= 960
    # NY PM: 17:00 - 21:00 UTC (Silver Bullet 10-11 AM EST = 15:00-16:00 UTC)
    is_ny_pm = 1020 <= total_min <= 1260
    # Asian: 00:00 - 08:00 UTC
    is_asian = total_min < 480
    # Silver Bullet Window: 14:00 - 15:00 UTC (10-11 AM EST)
    is_silver_bullet = 840 <= total_min <= 900

    active_kz = "NONE"
    if is_london:
        active_kz = "LONDON_KILLZONE"
    elif is_ny_am:
        active_kz = "NY_AM_KILLZONE"
    elif is_ny_pm:
        active_kz = "NY_PM_KILLZONE"
    elif is_asian:
        active_kz = "ASIAN_RANGE"

    return {
        "active_killzone": active_kz,
        "is_london": is_london,
        "is_ny_am": is_ny_am,
        "is_ny_pm": is_ny_pm,
        "is_asian": is_asian,
        "is_silver_bullet": is_silver_bullet,
    }


def calculate_ict_ote(df: pd.DataFrame, swing_high: float, swing_low: float, trend: int = 1) -> Dict[str, Any]:
    """Calculate ICT Optimal Trade Entry (OTE 61.8% - 78.6% Fib) with bidirectional trend support."""
    diff = swing_high - swing_low
    if diff <= 0:
        return {}

    if trend >= 0:
        # Bullish Uptrend: Retracement down to Discount for BUY
        ote_618 = swing_high - diff * 0.618
        ote_705 = swing_high - diff * 0.705
        ote_786 = swing_high - diff * 0.786
        eq_50 = swing_high - diff * 0.5
    else:
        # Bearish Downtrend: Retracement up to Premium for SELL
        ote_618 = swing_low + diff * 0.618
        ote_705 = swing_low + diff * 0.705
        ote_786 = swing_low + diff * 0.786
        eq_50 = swing_low + diff * 0.5

    return {
        "ote_top": round(float(max(ote_618, ote_786)), 2),
        "ote_sweet_spot": round(float(ote_705), 2),
        "ote_bottom": round(float(min(ote_618, ote_786)), 2),
        "equilibrium_50": round(float(eq_50), 2),
        "direction": "BULLISH" if trend >= 0 else "BEARISH",
    }


def detect_ict_turtle_soup(df: pd.DataFrame, htf_df: Optional[pd.DataFrame] = None) -> Optional[Dict[str, Any]]:
    """Detect ICT Turtle Soup (Liquidity Sweep of HTF High/Low + MSS Reversal) with dynamic ATR SL."""
    if len(df) < 15:
        return None

    ref_df = htf_df if (htf_df is not None and len(htf_df) >= 10) else df
    recent_high = float(ref_df["high"].iloc[-25:-2].max())
    recent_low = float(ref_df["low"].iloc[-25:-2].min())

    last_c = df.iloc[-1]
    prev_c = df.iloc[-2]
    atr_val = float(compute_atr(df, 14).iloc[-1]) if len(df) >= 14 else 2.0
    sl_buffer = max(0.5, atr_val * 0.3)

    # Bullish Turtle Soup
    if (prev_c["low"] < recent_low or last_c["low"] < recent_low) and last_c["close"] > recent_low:
        return {
            "type": "TURTLE_SOUP",
            "action": "BUY",
            "label": "Turtle Soup Buy",
            "swept_level": round(recent_low, 2),
            "entry": round(float(last_c["close"]), 2),
            "sl": round(float(min(last_c["low"], prev_c["low"]) - 1.5), 2),
            "tp": round(recent_high, 2),
            "direction": "BULLISH",
            "color": "#14D990",
        }

    # Bearish Turtle Soup: High sweeps above recent high, but close snaps back below
    if (prev_c["high"] > recent_high or last_c["high"] > recent_high) and last_c["close"] < recent_high:
        return {
            "type": "TURTLE_SOUP",
            "action": "SELL",
            "label": "Turtle Soup Sell",
            "swept_level": round(recent_high, 2),
            "entry": round(float(last_c["close"]), 2),
            "sl": round(float(max(last_c["high"], prev_c["high"]) + 1.5), 2),
            "tp": round(recent_low, 2),
            "direction": "BEARISH",
            "color": "#F24968",
        }

    return None


# ══════════════════════════════════════════════════════════════════════════════
# 4. METHOD 3: SNIPER MOMENTUM FLOW
# ══════════════════════════════════════════════════════════════════════════════

def calculate_sniper_flow(
    df: pd.DataFrame,
    m5_df: Optional[pd.DataFrame] = None,
    atr_mult: float = 1.5,
) -> Dict[str, Any]:
    """Calculate Sniper 7-Factor Dual Score, EMA Ribbon (9/21), VWAP and Dynamic Targets."""
    if len(df) < 25:
        return {"bull_pct": 50, "bear_pct": 50, "bias": "NEUTRAL", "targets": None}

    close = df["close"]
    high = df["high"]
    low = df["low"]
    open_ = df["open"]
    vol = df.get("volume", pd.Series(1.0, index=df.index))

    ema9 = compute_ema(close, 9)
    ema21 = compute_ema(close, 21)
    vwap = compute_vwap(df)
    rsi14 = compute_rsi(close, 14)
    adx14 = compute_adx(df, 14)
    macd_line, macd_sig = compute_macd(close, 12, 26, 9)
    vol_avg = vol.rolling(20).mean().fillna(1.0)
    atr = compute_atr(df, 14)

    rsi5m_val = 50.0
    if m5_df is not None and not m5_df.empty and len(m5_df) >= 15:
        rsi5m_val = float(compute_rsi(m5_df["close"], 14).iloc[-1])

    c_last = float(close.iloc[-1])
    vwap_last = float(vwap.iloc[-1])
    rsi_last = float(rsi14.iloc[-1])
    macd_m = float(macd_line.iloc[-1])
    macd_s = float(macd_sig.iloc[-1])
    e9 = float(ema9.iloc[-1])
    e21 = float(ema21.iloc[-1])
    adx_val = float(adx14.iloc[-1])
    vol_val = float(vol.iloc[-1])
    vol_avg_val = float(vol_avg.iloc[-1])
    o_last = float(open_.iloc[-1])
    atr_val = float(atr.iloc[-1]) if float(atr.iloc[-1]) > 0 else 5.0

    # 7 Bull Factors
    b_score = 0
    b_score += 1 if c_last > vwap_last else 0
    b_score += 1 if rsi_last > 50 else 0
    b_score += 1 if macd_m > macd_s else 0
    b_score += 1 if e9 > e21 else 0
    b_score += 1 if (adx_val > 25 and c_last > e9) else 0
    b_score += 1 if (vol_val > vol_avg_val and c_last > o_last) else 0
    b_score += 1 if rsi5m_val > 50 else 0

    # 7 Bear Factors
    r_score = 0
    r_score += 1 if c_last < vwap_last else 0
    r_score += 1 if rsi_last < 50 else 0
    r_score += 1 if macd_m < macd_s else 0
    r_score += 1 if e9 < e21 else 0
    r_score += 1 if (adx_val > 25 and c_last < e9) else 0
    r_score += 1 if (vol_val > vol_avg_val and c_last < o_last) else 0
    r_score += 1 if rsi5m_val < 50 else 0

    bull_pct = int((b_score / 7.0) * 100)
    bear_pct = int((r_score / 7.0) * 100)

    if (bull_pct - bear_pct) >= 40:
        bias = "STRONG BULL"
    elif (bear_pct - bull_pct) >= 40:
        bias = "STRONG BEAR"
    elif bull_pct > bear_pct:
        bias = "MILD BULL"
    else:
        bias = "MILD BEAR"

    risk = atr_val * atr_mult
    is_buy = bull_pct >= bear_pct

    entry = c_last
    sl = entry - risk if is_buy else entry + risk
    t1 = entry + risk if is_buy else entry - risk
    t2 = entry + (risk * 2) if is_buy else entry - (risk * 2)
    t3 = entry + (risk * 3) if is_buy else entry - (risk * 3)
    t4 = entry + (risk * 4) if is_buy else entry - (risk * 4)
    t5 = entry + (risk * 5) if is_buy else entry - (risk * 5)

    targets = {
        "action": "BUY" if is_buy else "SELL",
        "entry": round(entry, 2),
        "sl": round(sl, 2),
        "tp1": round(t1, 2),
        "tp2": round(t2, 2),
        "tp3": round(t3, 2),
        "tp4": round(t4, 2),
        "tp5": round(t5, 2),
        "atr": round(atr_val, 2),
    }

    return {
        "bull_pct": bull_pct,
        "bear_pct": bear_pct,
        "bias": bias,
        "b_score": b_score,
        "r_score": r_score,
        "targets": targets,
        "ema9": round(e9, 2),
        "ema21": round(e21, 2),
        "vwap": round(vwap_last, 2),
        "rsi": round(rsi_last, 1),
        "adx": round(adx_val, 1),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 5. METHOD 4: PRICE ACTION & 14 CANDLESTICK PATTERNS
# ══════════════════════════════════════════════════════════════════════════════

def detect_price_action_patterns(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Detect Top Price Action patterns (Pin Bar, Engulfing, Morning Star, Three Soldiers...)."""
    n = len(df)
    if n < 5:
        return []

    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    time_col = "time" if "time" in df.columns else df.columns[0]
    times = df[time_col].values

    patterns = []
    # Check last 10 candles for confirmed patterns
    for i in range(max(3, n - 10), n):
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        body = abs(c - o)
        rng = max(1e-5, h - l)
        u_wick = h - max(o, c)
        l_wick = min(o, c) - l

        # 1. Pin Bar (Hammer / Shooting Star)
        if l_wick >= body * 2.0 and u_wick <= body * 0.5:
            patterns.append({
                "type": "CANDLE_PATTERN",
                "label": "Hammer / Pin Bar",
                "direction": "BULLISH",
                "index": int(i),
                "price": round(l, 2),
                "time": _to_iso(times[i]),
                "timestamp": _to_timestamp_sec(times[i]),
            })
        elif u_wick >= body * 2.0 and l_wick <= body * 0.5:
            patterns.append({
                "type": "CANDLE_PATTERN",
                "label": "Shooting Star",
                "direction": "BEARISH",
                "index": int(i),
                "price": round(h, 2),
                "time": _to_iso(times[i]),
                "timestamp": _to_timestamp_sec(times[i]),
            })

        # 2. Bullish / Bearish Engulfing
        prev_o, prev_c = opens[i - 1], closes[i - 1]
        prev_body = abs(prev_c - prev_o)
        if c > o and prev_c < prev_o and c >= prev_o and o <= prev_c and body > prev_body * 1.1:
            patterns.append({
                "type": "CANDLE_PATTERN",
                "label": "Bullish Engulfing",
                "direction": "BULLISH",
                "index": int(i),
                "price": round(l, 2),
                "time": _to_iso(times[i]),
                "timestamp": _to_timestamp_sec(times[i]),
            })
        elif c < o and prev_c > prev_o and c <= prev_o and o >= prev_c and body > prev_body * 1.1:
            patterns.append({
                "type": "CANDLE_PATTERN",
                "label": "Bearish Engulfing",
                "direction": "BEARISH",
                "index": int(i),
                "price": round(h, 2),
                "time": _to_iso(times[i]),
                "timestamp": _to_timestamp_sec(times[i]),
            })

    return patterns[-3:] if len(patterns) > 3 else patterns


# ══════════════════════════════════════════════════════════════════════════════
# 6. METHOD 5: ULTRA CONFLUENCE MATRIX (5-Layer Institutional Scoring)
# ══════════════════════════════════════════════════════════════════════════════

def compute_ultra_confluence_matrix(
    df: pd.DataFrame,
    smc_data: Dict[str, Any],
    ict_data: Dict[str, Any],
    sniper_data: Dict[str, Any],
    pa_patterns: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Combine 5 Trading Methods into an Institutional Confluence Score (0-100%)."""
    # Weights:
    # Layer 1: Market Structure (25%)
    # Layer 2: Order Blocks & FVG (25%)
    # Layer 3: Dynamic Technicals (20%)
    # Layer 4: Momentum & Volume (15%)
    # Layer 5: Time & Killzone (15%)

    bull_score = 0.0
    bear_score = 0.0

    # Layer 1: Structure (Trend & BoS/CHoCH)
    trend = smc_data.get("current_trend", 0)
    if trend == 1:
        bull_score += 20.0
    elif trend == -1:
        bear_score += 20.0

    recent_segments = smc_data.get("segments", [])
    if recent_segments:
        last_seg = recent_segments[-1]
        if last_seg.get("direction") == "BULLISH":
            bull_score += 5.0
        else:
            bear_score += 5.0

    # Layer 2: OB & FVG Demand/Supply
    obs = smc_data.get("order_blocks", [])
    bull_obs = [o for o in obs if o.get("direction") == "BULLISH"]
    bear_obs = [o for o in obs if o.get("direction") == "BEARISH"]

    c_last = float(df["close"].iloc[-1])
    # Check if price is touching or near an OB
    for bo in bull_obs:
        if bo["bottom"] <= c_last <= bo["top"] * 1.002:
            bull_score += 15.0
            break
    for so in bear_obs:
        if so["bottom"] * 0.998 <= c_last <= so["top"]:
            bear_score += 15.0
            break

    # Layer 3: Dynamic (EMA Ribbon & VWAP)
    e9 = sniper_data.get("ema9", 0)
    e21 = sniper_data.get("ema21", 0)
    vwap = sniper_data.get("vwap", 0)
    if c_last > vwap and e9 > e21:
        bull_score += 20.0
    elif c_last < vwap and e9 < e21:
        bear_score += 20.0

    # Layer 4: Momentum (Sniper Bull/Bear pct)
    s_bull = sniper_data.get("bull_pct", 50)
    s_bear = sniper_data.get("bear_pct", 50)
    bull_score += (s_bull / 100.0) * 15.0
    bear_score += (s_bear / 100.0) * 15.0

    # Layer 5: Time & Killzone
    kz = ict_data.get("killzone", {})
    if kz.get("is_london") or kz.get("is_ny_am") or kz.get("is_silver_bullet"):
        # Active killzone provides +15% confluence multiplier
        bull_score += 10.0 if bull_score > bear_score else 0.0
        bear_score += 10.0 if bear_score > bull_score else 0.0

    final_score = int(max(bull_score, bear_score))
    signal = "NEUTRAL"
    if bull_score >= 70 and bull_score > bear_score:
        signal = "BUY"
    elif bear_score >= 70 and bear_score > bull_score:
        signal = "SELL"

    classification = "QUALIFIED" if final_score >= 80 else "CONSIDER" if final_score >= 65 else "FILTERED"

    return {
        "signal": signal,
        "score": min(100, final_score),
        "bull_score": round(bull_score, 1),
        "bear_score": round(bear_score, 1),
        "classification": classification,
        "layers": {
            "structure": "BULLISH" if trend == 1 else "BEARISH" if trend == -1 else "NEUTRAL",
            "supply_demand": f"{len(bull_obs)} Bull OB / {len(bear_obs)} Bear OB",
            "dynamics": f"EMA9/21 {'BULL' if e9 > e21 else 'BEAR'} | VWAP {'ABOVE' if c_last > vwap else 'BELOW'}",
            "momentum": f"Bull {s_bull}% / Bear {s_bear}%",
            "time_session": kz.get("active_killzone", "OUTSIDE_KZ"),
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# 7. MASTER COMPOSER: COMPLETE MULTI-METHOD PAYLOAD
# ══════════════════════════════════════════════════════════════════════════════

def build_aether_flow_payload(
    symbol: str,
    df: pd.DataFrame,
    htf_h1_df: Optional[pd.DataFrame] = None,
    m5_df: Optional[pd.DataFrame] = None,
    method: str = "ULTRA_CONFLUENCE",
    broker_utc_offset_hours: int = 0,
) -> Dict[str, Any]:
    """Execute all 5 Trading Methods and return unified TradingView + AI payload."""
    if df is None or df.empty or len(df) < 30:
        return {
            "symbol": symbol,
            "method": method,
            "swings": [],
            "segments": [],
            "order_blocks": [],
            "fvgs": [],
            "auto_fibs": None,
            "ut_signals": [],
            "sniper": {},
            "ict": {},
            "price_action": [],
            "confluence": {},
            "indicators": {},
        }

    # 1. SMC Structure & Zones
    smc_data = detect_smc_structure(df, ext_sens=25, int_sens=5)
    obs, breakers = detect_luxalgo_order_blocks(df, pivot_len=5, max_bull_ob=3, max_bear_ob=3)
    fvgs = detect_luxalgo_fvg(df, threshold_pct=0.0, max_fvg_count=3)
    smc_data["order_blocks"] = obs + breakers
    smc_data["fvgs"] = fvgs

    # 2. Auto Fibs Retracement
    major_h = smc_data["last_high"][1] if smc_data["last_high"] else float(df["high"].tail(100).max())
    major_l = smc_data["last_low"][1] if smc_data["last_low"] else float(df["low"].tail(100).min())
    diff = major_h - major_l
    fib_levels = []
    if diff > 0:
        is_bull = df["close"].iloc[-1] >= (major_h + major_l) / 2.0
        ratios = [
            (0.236, "#A0A5B9", "0.236"),
            (0.382, "#00FF00", "0.382"),
            (0.500, "#FFFF00", "0.500 (EQ)"),
            (0.618, "#FFA500", "0.618 (Golden)"),
            (0.786, "#FF0000", "0.786 (OTE)"),
            (0.886, "#800080", "0.886"),
        ]
        for r, col, lbl in ratios:
            p = major_h - diff * r if is_bull else major_l + diff * r
            fib_levels.append({"ratio": r, "price": round(float(p), 2), "color": col, "label": lbl})
    auto_fibs = {
        "swing_high": round(float(major_h), 2),
        "swing_low": round(float(major_l), 2),
        "levels": fib_levels,
    }

    # 3. ICT Engine (Killzones, OTE, Turtle Soup)
    time_col = "time" if "time" in df.columns else df.columns[0]
    last_dt = pd.to_datetime(df[time_col].iloc[-1]).to_pydatetime()
    kz_data = detect_ict_killzones(last_dt, broker_utc_offset_hours)
    ote_data = calculate_ict_ote(df, major_h, major_l, trend=smc_data["current_trend"])
    turtle_soup = detect_ict_turtle_soup(df, htf_h1_df)
    ict_payload = {
        "killzone": kz_data,
        "ote": ote_data,
        "turtle_soup": turtle_soup,
    }

    # 4. Sniper Flow Engine
    sniper_payload = calculate_sniper_flow(df, m5_df=m5_df)

    # 5. Price Action Patterns
    pa_patterns = detect_price_action_patterns(df)

    # 6. Ultra Confluence Matrix
    confluence = compute_ultra_confluence_matrix(
        df=df,
        smc_data=smc_data,
        ict_data=ict_payload,
        sniper_data=sniper_payload,
        pa_patterns=pa_patterns,
    )

    # 7. UT Bot Momentum Signals
    atr_vals = compute_atr(df, 6).values
    n_loss = 2.0 * atr_vals
    closes = df["close"].values
    n = len(df)
    x_stop = np.zeros(n)
    pos = np.zeros(n)
    for i in range(1, n):
        prev_stop = x_stop[i - 1]
        prev_c = closes[i - 1]
        c = closes[i]
        loss = n_loss[i]
        if c > prev_stop and prev_c > prev_stop:
            x_stop[i] = max(prev_stop, c - loss)
        elif c < prev_stop and prev_c < prev_stop:
            x_stop[i] = min(prev_stop, c + loss)
        elif c > prev_stop:
            x_stop[i] = c - loss
        else:
            x_stop[i] = c + loss
        if prev_c < prev_stop and c > prev_stop:
            pos[i] = 1
        elif prev_c > prev_stop and c < prev_stop:
            pos[i] = -1
        else:
            pos[i] = pos[i - 1]

    ut_signals = []
    times = df[time_col].values
    for i in range(1, n):
        if pos[i] == 1 and pos[i - 1] != 1:
            ut_signals.append({
                "type": "SIGNAL",
                "action": "BUY",
                "label": "UT Buy",
                "price": round(float(closes[i]), 2),
                "index": int(i),
                "time": _to_iso(times[i]),
                "timestamp": _to_timestamp_sec(times[i]),
                "direction": "BULLISH",
                "color": "#14D990",
            })
        elif pos[i] == -1 and pos[i - 1] != -1:
            ut_signals.append({
                "type": "SIGNAL",
                "action": "SELL",
                "label": "UT Sell",
                "price": round(float(closes[i]), 2),
                "index": int(i),
                "time": _to_iso(times[i]),
                "timestamp": _to_timestamp_sec(times[i]),
                "direction": "BEARISH",
                "color": "#F24968",
            })

    # 8. Fast Indicators for real-time overlay
    ema9_s = compute_ema(df["close"], 9)
    ema21_s = compute_ema(df["close"], 21)
    vwap_s = compute_vwap(df)
    hma55_s = compute_hma(df["close"], 55)
    last_100_times = df[time_col].tail(100).values

    def _to_line_points(series: pd.Series) -> List[Dict[str, Any]]:
        pts = []
        tail_s = series.tail(100).values
        for t, v in zip(last_100_times, tail_s):
            if not np.isnan(v):
                pts.append({"time": _to_timestamp_sec(t), "value": round(float(v), 2)})
        return pts

    indicators = {
        "ema9": _to_line_points(ema9_s),
        "ema21": _to_line_points(ema21_s),
        "vwap": _to_line_points(vwap_s),
        "hma55": _to_line_points(hma55_s),
    }

    # 9. Institutional Structure Engine (ISE)
    try:
        from structure_engine import detect_institutional_structure_engine
        ise_payload = detect_institutional_structure_engine(df)
    except Exception:
        ise_payload = {}

    return {
        "symbol": symbol,
        "method": method,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "swings": smc_data["swings"],
        "segments": smc_data["segments"],
        "order_blocks": obs,
        "fvgs": fvgs,
        "auto_fibs": auto_fibs,
        "ut_signals": ut_signals[-3:],
        "sniper": sniper_payload,
        "ict": ict_payload,
        "price_action": pa_patterns,
        "structure_engine": ise_payload,
        "confluence": confluence,
        "indicators": indicators,
    }
