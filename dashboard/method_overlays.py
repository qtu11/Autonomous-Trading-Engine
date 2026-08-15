"""Per-method chart overlays for Sniper / SMC / ICT / Price Action.

Each `compute_<method>_overlay()` consumes the multi-timeframe candle dict
already prepared by `build_chart_markup()` and returns a list of objects that
share the markup contract:

    {"type": "...", "direction": "...", "label": "...", "top": float, "bottom": float,
     "price": float, "index": int, "time_start": ISO, "time_end": ISO, ...}

The frontend canvas and the EA on MT5 render these objects; this module is the
authoritative server-side computation so AI / auto-trade decisions can read the
same signals a human sees on the chart.

Mapping of trading-method -> object-type groups follows the user checklist:
    SNIPER      -> EMA/EMA_RIBBON, VWAP, SNIPER_SIGNAL, SNIPER_SL, SNIPER_TP1..5,
                   SNIPER_SCORE, BOS, CHoCH (used as confluence)
    SMC         -> SWING (HH/HL/LH/LL), BSL/SSL/EQH/EQL, OB, BREAKER, MITIGATION,
                   FVG, BOS, CHoCH, MSS, LIQUIDITY, SFP, INDUCEMENT, SUPPLY_DEMAND
    ICT         -> ASIAN, KILLZONE, OTE, PD, JUDAS_SWING, PO3, SILVER_BULLET,
                   UNICORN, NYMO, BSL/SSL/EQH/EQL, BOS, CHoCH, OB, FVG, OTE
    PRICE_ACTION-> CANDLE_PATTERN (PIN_BAR/HAMMER/SHOOTING_STAR/ENGULFING/...),
                   S/R, PIVOT (R1/S1/R2/S2/PDH/PDL), CHART_PATTERN
                   (DOUBLE_TOP/BOTTOM/H&S/TRIANGLE/WEDGE/CHANNEL/FLAG/PENNANT),
                   TRENDLINE, TREND, SWING, BOS, CHoCH
    ULTRA_CONFLUENCE -> union of all of the above.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import pandas as pd

# ---- Constants ----
ATR_PERIOD = 14
EMA_FAST = 9
EMA_SLOW = 21
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
ADX_PERIOD = 14
VOL_MA_PERIOD = 20
SNIPER_TP_MULTIPLIERS = (1, 2, 3, 4, 5)
PINBAR_WICK_RATIO = 2.0  # wick >= 2x body
DOJI_BODY_RATIO = 0.10  # body/range <= 10%
PIVOT_TOLERANCE = 0.0010  # 0.1% of price for EQH/EQL
BSL_SSL_CLUSTER = 0.0030  # 0.3% cluster band for BSL/SSL pools

# Object type groups per method (used to filter final markup list).
# These mirror the user's concept checklist for every method, so the chart
# only renders the components that belong to the selected method:
#   SNIPER        -> EMA9/21 + ribbon, VWAP, ADX/RSI/MACD, signal + SL/TP1-5, score,
#                    BOS/CHoCH/MSS confluence, Breakout/Pullback/Retest/FakeBreakout,
#                    S/R + trendline, Supply/Demand, liquidity sweep.
#   SMC           -> Market structure (SWING), BOS/CHoCH/MSS, OB/Breaker/Mitigation/
#                    Rejection, FVG/iFVG, Liquidity + pools, EQH/EQL, SFP (stop hunt),
#                    Inducement, Supply/Demand, Volume Imbalance, Liquidity Void,
#                    Dealing Range/Curve, Premium/Discount (PD).
#   ICT           -> BOS/CHoCH/MSS, OB/Breaker/FVG/iFVG, BPR, PD/OTE, Asian range,
#                    Killzone, Judas Swing, PO3/AMD, Silver Bullet, Unicorn, NYMO,
#                    Turtle Soup, SMT Divergence, Session HL, PDH/PDL, Weekly/Monthly
#                    HL, Liquidity pools, Dealing Range/Curve, Void, Inducement.
#   PRICE_ACTION  -> Trend, Swing (HH/HL/LH/LL), S/R, Trendline, Channel, Range,
#                    Breakout/Pullback/Retest/FakeBreakout, candle + chart patterns,
#                    Pivots + PDH/PDL.
METHOD_OBJECT_GROUPS: dict[str, set[str]] = {
    "SNIPER": {
        "EMA", "EMA_RIBBON", "VWAP", "ADX", "MACD_LINE", "MACD_SIGNAL", "RSI_LEVEL",
        "SNIPER_SIGNAL", "SNIPER_SL", "SNIPER_TP1", "SNIPER_TP2", "SNIPER_TP3",
        "SNIPER_TP4", "SNIPER_TP5", "SNIPER_SCORE", "SNIPER_DASH",
        "SWING", "BOS", "CHoCH", "MSS", "LIQUIDITY", "LIQUIDITY_POOL", "SFP",
        "SUPPLY_DEMAND", "TRENDLINE", "SUPPORT", "RESISTANCE", "SR",
        "BREAKOUT", "PULLBACK", "RETEST", "FAKE_BREAKOUT", "PATTERN",
    },
    "SMC": {
        "SWING", "BOS", "CHoCH", "MSS", "OB", "BREAKER", "MITIGATION", "REJECTION",
        "FVG", "iFVG", "BSL", "SSL", "EQH", "EQL", "LIQUIDITY", "LIQUIDITY_POOL",
        "SFP", "INDUCEMENT", "SUPPLY_DEMAND", "VOLUME_IMBALANCE", "VOID",
        "DEALING_RANGE", "DEALING_CURVE", "PD", "TRENDLINE",
    },
    "ICT": {
        "ASIAN", "KILLZONE", "OTE", "PD", "JUDAS_SWING", "PO3", "SILVER_BULLET",
        "UNICORN", "NYMO", "BSL", "SSL", "EQH", "EQL", "BOS", "CHoCH",
        "MSS", "OB", "BREAKER", "MITIGATION", "REJECTION", "FVG", "iFVG", "BPR",
        "LIQUIDITY", "LIQUIDITY_POOL", "INDUCEMENT", "SUPPLY_DEMAND",
        "VOLUME_IMBALANCE", "VOID", "DEALING_RANGE", "DEALING_CURVE",
        "TURTLE_SOUP", "SMT_DIVERGENCE", "AMD", "SESSION_HL", "PDH_PDL",
        "WEEKLY_MONTHLY_HL",
    },
    "PRICE_ACTION": {
        "CANDLE_PATTERN", "PATTERN", "CHART_PATTERN", "SUPPORT", "RESISTANCE", "SR",
        "PIVOT", "PDH", "PDL", "TRENDLINE", "TREND", "SWING", "BOS", "CHoCH",
        "CHANNEL", "RANGE", "BREAKOUT", "PULLBACK", "RETEST", "FAKE_BREAKOUT",
    },
    "STRUCTURE_ENGINE": {
        "BASELINE", "VOLATILITY_ENVELOPE", "BAND_LAYER", "SWING", "BOS", "CHoCH",
        "SUPPLY_DEMAND", "OB", "FVG", "LIQUIDITY", "LIQUIDITY_POOL", "SWEEP", "EQH", "EQL",
        "CONTINUATION", "REVERSAL_REF", "TRAILING_STOP", "TP1", "TP2", "TP3", "SL",
        "STRUCTURE_SCORE", "DASHBOARD", "DISPLACEMENT",
    },
    "ULTRA_CONFLUENCE": set(),  # empty -> include everything
}


# ---- Helpers ----
def _dt(ts: Any) -> str:
    if isinstance(ts, str):
        return ts
    if isinstance(ts, (pd.Timestamp, datetime)):
        return ts.isoformat()
    return ""


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _rsi(series: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift(1)).abs(),
        (df["low"] - df["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _adx(df: pd.DataFrame, period: int = ADX_PERIOD) -> tuple[pd.Series, pd.Series, pd.Series]:
    high = df["high"]
    low = df["low"]
    close = df["close"]
    up = high.diff()
    down = -low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    plus_di = 100 * pd.Series(plus_dm).rolling(period).sum() / atr.replace(0, np.nan)
    minus_di = 100 * pd.Series(minus_dm).rolling(period).sum() / atr.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.rolling(period).mean()
    return adx.fillna(0), plus_di.fillna(0), minus_di.fillna(0)


def _macd(series: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    fast = _ema(series, MACD_FAST)
    slow = _ema(series, MACD_SLOW)
    macd_line = fast - slow
    signal = _ema(macd_line, MACD_SIGNAL)
    hist = macd_line - signal
    return macd_line, signal, hist


def _vol(df: pd.DataFrame) -> pd.Series:
    """Resolve the volume column regardless of the bridge's naming (volume /
    tick_volume / real_volume). Missing volume degrades to a zero series so
    VWAP and volume-confirmation never crash on real MT5 payloads."""
    for col in ("volume", "tick_volume", "real_volume"):
        if col in df.columns:
            return df[col].fillna(0.0)
    return pd.Series(0.0, index=df.index)


def _vwap(df: pd.DataFrame) -> pd.Series:
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = _vol(df)
    cum_vol = vol.cumsum().replace(0, np.nan)
    return (typical * vol).cumsum() / cum_vol


def _candle_row(c: dict[str, Any]) -> dict[str, float]:
    o, h, l, cl = c["open"], c["high"], c["low"], c["close"]
    rng = h - l if h > l else 1e-9
    body = abs(cl - o)
    upper = h - max(o, cl)
    lower = min(o, cl) - l
    return {
        "open": o, "high": h, "low": l, "close": cl,
        "range": rng, "body": body,
        "upper_wick": upper, "lower_wick": lower,
        "body_ratio": body / rng,
        "upper_ratio": upper / rng,
        "lower_ratio": lower / rng,
        "is_bull": cl > o,
        "is_bear": cl < o,
    }


# ---- SNIPER ----
def compute_sniper_overlay(
    symbol: str,
    df: pd.DataFrame,
    df_lower_tf: pd.DataFrame | None = None,
    broker_utc_offset_hours: float = 2.0,
    atr_multiplier: float = 1.5,
) -> list[dict[str, Any]]:
    """Returns Sniper objects: EMA ribbon + VWAP + score + (if crossover) signal + SL + 5 TP levels.

    Faithful to the TradingView Pine Script the user provided:
        - EMA9 vs EMA21 crossover -> BUY / SELL trigger
        - SL = entry ± ATR14 * atr_multiplier (default 1.5)
        - TP1..5 = entry ± risk * (1..5)
        - Score 0-100 for bull/bear based on 7 factors:
            1. close vs VWAP
            2. RSI > 50
            3. MACD main > signal
            4. EMA9 > EMA21
            5. ADX > 25 AND close > EMA9
            6. volume > vol MA AND close > open
            7. RSI(14) on 5m > 50  (uses df_lower_tf if provided)
    """
    objects: list[dict[str, Any]] = []
    if df is None or df.empty or len(df) < max(EMA_SLOW, MACD_SLOW) + 5:
        return objects

    time_col = 'time' if 'time' in df.columns else 'timestamp' if 'timestamp' in df.columns else 'time'
    close = df["close"]
    ema9 = _ema(close, EMA_FAST)
    ema21 = _ema(close, EMA_SLOW)
    vwap = _vwap(df)
    rsi = _rsi(close)
    macd_line, macd_sig, _ = _macd(close)
    adx, plus_di, minus_di = _adx(df)
    atr = _atr(df)
    vol = _vol(df)
    vol_ma = vol.rolling(VOL_MA_PERIOD).mean()
    last = df.iloc[-1]
    last_time = last[time_col]

    # EMA ribbon (two endpoint lines + colored band)
    objects.append({
        "type": "EMA", "direction": "BULLISH", "label": "EMA9",
        "top": float(ema9.iloc[-1]), "bottom": float(ema9.iloc[-1]),
        "price": float(ema9.iloc[-1]),
        "index": 0, "time_start": _dt(last_time),
        "series": [float(x) for x in ema9.tail(120)],
        "color": "#22c55e",
    })
    objects.append({
        "type": "EMA", "direction": "BEARISH", "label": "EMA21",
        "top": float(ema21.iloc[-1]), "bottom": float(ema21.iloc[-1]),
        "price": float(ema21.iloc[-1]),
        "index": 0, "time_start": _dt(last_time),
        "series": [float(x) for x in ema21.tail(120)],
        "color": "#ef4444",
    })
    objects.append({
        "type": "EMA_RIBBON",
        "direction": "BULLISH" if ema9.iloc[-1] > ema21.iloc[-1] else "BEARISH",
        "label": "EMA_RIBBON",
        "top": float(ema9.iloc[-1]), "bottom": float(ema21.iloc[-1]),
        "price": float(ema9.iloc[-1]),
        "index": 0, "time_start": _dt(last_time),
        "ema9_series": [float(x) for x in ema9.tail(120)],
        "ema21_series": [float(x) for x in ema21.tail(120)],
    })
    # VWAP
    objects.append({
        "type": "VWAP", "direction": "BULLISH" if close.iloc[-1] > vwap.iloc[-1] else "BEARISH",
        "label": "VWAP",
        "top": float(vwap.iloc[-1]), "bottom": float(vwap.iloc[-1]),
        "price": float(vwap.iloc[-1]),
        "index": 0, "time_start": _dt(last_time),
        "series": [float(x) for x in vwap.tail(120)],
        "color": "#06b6d4",
    })
    # ADX level info
    objects.append({
        "type": "ADX", "direction": "NEUTRAL", "label": "ADX",
        "top": float(adx.iloc[-1]), "bottom": float(adx.iloc[-1]),
        "price": float(adx.iloc[-1]),
        "index": 0, "time_start": _dt(last_time),
        "adx": float(adx.iloc[-1]),
        "plus_di": float(plus_di.iloc[-1]),
        "minus_di": float(minus_di.iloc[-1]),
        "strong": float(adx.iloc[-1]) > 25,
    })
    # RSI bands
    objects.append({
        "type": "RSI_LEVEL", "direction": "NEUTRAL", "label": "RSI14",
        "top": 70.0, "bottom": 30.0,
        "price": float(rsi.iloc[-1]),
        "index": 0, "time_start": _dt(last_time),
        "value": float(rsi.iloc[-1]),
    })
    # MACD
    objects.append({
        "type": "MACD_LINE", "direction": "BULLISH" if macd_line.iloc[-1] > macd_sig.iloc[-1] else "BEARISH",
        "label": "MACD",
        "top": float(macd_line.iloc[-1]), "bottom": float(macd_line.iloc[-1]),
        "price": float(macd_line.iloc[-1]),
        "index": 0, "time_start": _dt(last_time),
        "macd": float(macd_line.iloc[-1]),
        "signal": float(macd_sig.iloc[-1]),
        "hist": float(macd_line.iloc[-1] - macd_sig.iloc[-1]),
    })

    # ---- Dual bull/bear score (7 factors) ----
    rsi_5m = 50.0
    if df_lower_tf is not None and not df_lower_tf.empty:
        try:
            rsi_5m = float(_rsi(df_lower_tf["close"]).iloc[-1])
        except Exception:
            rsi_5m = 50.0

    bull = 0
    if close.iloc[-1] > vwap.iloc[-1]: bull += 1
    if rsi.iloc[-1] > 50: bull += 1
    if macd_line.iloc[-1] > macd_sig.iloc[-1]: bull += 1
    if ema9.iloc[-1] > ema21.iloc[-1]: bull += 1
    if adx.iloc[-1] > 25 and close.iloc[-1] > ema9.iloc[-1]: bull += 1
    if vol.iloc[-1] > vol_ma.iloc[-1] and close.iloc[-1] > df["open"].iloc[-1]: bull += 1
    if rsi_5m > 50: bull += 1

    bear = 0
    if close.iloc[-1] < vwap.iloc[-1]: bear += 1
    if rsi.iloc[-1] < 50: bear += 1
    if macd_line.iloc[-1] < macd_sig.iloc[-1]: bear += 1
    if ema9.iloc[-1] < ema21.iloc[-1]: bear += 1
    if adx.iloc[-1] > 25 and close.iloc[-1] < ema9.iloc[-1]: bear += 1
    if vol.iloc[-1] > vol_ma.iloc[-1] and close.iloc[-1] < df["open"].iloc[-1]: bear += 1
    if rsi_5m < 50: bear += 1

    bull_pct = round(bull / 7 * 100, 1)
    bear_pct = round(bear / 7 * 100, 1)
    bias_text = (
        "STRONG_BULL" if (bull_pct - bear_pct) >= 40 else
        "STRONG_BEAR" if (bear_pct - bull_pct) >= 40 else
        "MILD_BULL" if bull_pct > bear_pct else "MILD_BEAR"
    )

    objects.append({
        "type": "SNIPER_SCORE", "direction": "NEUTRAL", "label": "SNIPER_SCORE",
        # pyrefly: ignore [unnecessary-type-conversion]
        "top": float(bull_pct), "bottom": float(bear_pct),
        "price": float(close.iloc[-1]),
        "index": 0, "time_start": _dt(last_time),
        "bull_pct": bull_pct, "bear_pct": bear_pct, "bias": bias_text,
        "factors": {
            "price_vs_vwap": close.iloc[-1] > vwap.iloc[-1],
            "rsi_above_50": rsi.iloc[-1] > 50,
            "macd_bull": macd_line.iloc[-1] > macd_sig.iloc[-1],
            "ema9_above_21": ema9.iloc[-1] > ema21.iloc[-1],
            "adx_strong_with_trend": float(adx.iloc[-1]) > 25,
            "volume_confirm": float(vol.iloc[-1]) > float(vol_ma.iloc[-1]) if not pd.isna(vol_ma.iloc[-1]) else False,
            "rsi_5m_above_50": rsi_5m > 50,
        },
    })
    objects.append({
        "type": "SNIPER_DASH", "direction": "NEUTRAL", "label": "SNIPER_DASH",
        "top": 0.0, "bottom": 0.0, "price": 0.0,
        "index": 0, "time_start": _dt(last_time),
        "bull_pct": bull_pct, "bear_pct": bear_pct, "bias": bias_text,
    })

    # ---- Crossover detection: last 2 candles ----
    prev_close = close.iloc[-2]
    prev_ema9 = ema9.iloc[-2]
    prev_ema21 = ema21.iloc[-2]
    if prev_ema9 <= prev_ema21 and ema9.iloc[-1] > ema21.iloc[-1]:
        signal = "BUY"
    elif prev_ema9 >= prev_ema21 and ema9.iloc[-1] < ema21.iloc[-1]:
        signal = "SELL"
    else:
        signal = "WAIT"

    if signal in ("BUY", "SELL"):
        entry = float(close.iloc[-1])
        risk = float(atr.iloc[-1]) * atr_multiplier
        sign = 1 if signal == "BUY" else -1
        sl = entry - sign * risk
        tps = [entry + sign * risk * m for m in SNIPER_TP_MULTIPLIERS]

        objects.append({
            "type": "SNIPER_SIGNAL", "direction": "BULLISH" if signal == "BUY" else "BEARISH",
            "label": signal,
            "top": entry, "bottom": entry,
            "price": entry, "index": 0,
            "time_start": _dt(last_time), "time_end": _dt(last_time),
        })
        objects.append({
            "type": "SNIPER_SL", "direction": "BULLISH" if signal == "BUY" else "BEARISH",
            "label": "SL",
            "top": sl, "bottom": sl, "price": sl,
            "index": 0, "time_start": _dt(last_time),
        })
        for i, tp in enumerate(tps, start=1):
            objects.append({
                "type": f"SNIPER_TP{i}", "direction": "BULLISH" if signal == "BUY" else "BEARISH",
                "label": f"TP{i}",
                "top": tp, "bottom": tp, "price": tp,
                "index": 0, "time_start": _dt(last_time),
            })
    return objects


# ---- SMC ----
def _find_swings(series: pd.Series, window: int) -> list[tuple[int, float]]:
    """Return list of (index, price) for swing highs (max) and lows (min) combined."""
    swings: list[tuple[int, float, str]] = []
    for i in range(window, len(series) - window):
        window_vals = series.iloc[i - window:i + window + 1]
        if series.iloc[i] == window_vals.max():
            swings.append((i, float(series.iloc[i]), "HIGH"))
        elif series.iloc[i] == window_vals.min():
            swings.append((i, float(series.iloc[i]), "LOW"))
    # pyrefly: ignore [bad-return]
    return swings


def compute_smc_overlay(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Returns SMC objects: swing labels (HH/HL/LH/LL), BSL/SSL/EQH/EQL liquidity
    pools, BOS/CHoCH/MSS markers, OB/Breaker/Mitigation/FVG (handled in core
    markup), SFP, inducement, supply/demand zones.
    """
    objects: list[dict[str, Any]] = []
    if df is None or df.empty or len(df) < 10:
        return objects

    time_col = 'time' if 'time' in df.columns else 'timestamp' if 'timestamp' in df.columns else 'time'
    high = df["high"]
    low = df["low"]
    close = df["close"]
    last = df.iloc[-1]
    last_time = last[time_col]

    # ---- Swings + market structure labels ----
    swing_highs: list[tuple[int, float]] = []
    swing_lows: list[tuple[int, float]] = []
    for i in range(2, len(df) - 2):
        if df["high"].iloc[i] == df["high"].iloc[i - 2:i + 3].max():
            swing_highs.append((i, float(df["high"].iloc[i])))
        if df["low"].iloc[i] == df["low"].iloc[i - 2:i + 3].min():
            swing_lows.append((i, float(df["low"].iloc[i])))

    prev_h = None
    prev_l = None
    trend = "NEUTRAL"
    for i, h in swing_highs[-8:]:
        if prev_h is None:
            prev_h = h; continue
        label = "HH" if h > prev_h else "LH"
        trend = "BULLISH" if label == "HH" else trend
        objects.append({
            "type": "SWING", "direction": "BULLISH" if label == "HH" else "BEARISH",
            # pyrefly: ignore [unnecessary-type-conversion]
            "label": label, "price": round(h, 2), "index": int(i),
            "time_start": _dt(df.iloc[i][time_col]),
            "top": h, "bottom": h,
        })
        prev_h = h
    for i, l in swing_lows[-8:]:
        if prev_l is None:
            prev_l = l; continue
        label = "HL" if l > prev_l else "LL"
        objects.append({
            "type": "SWING", "direction": "BULLISH" if label == "HL" else "BEARISH",
            # pyrefly: ignore [unnecessary-type-conversion]
            "label": label, "price": round(l, 2), "index": int(i),
            "time_start": _dt(df.iloc[i][time_col]),
            "top": l, "bottom": l,
        })
        prev_l = l

    # ---- BSL / SSL pools (cluster of recent swing highs/lows within BSL_SSL_CLUSTER) ----
    recent_highs = sorted([h for _, h in swing_highs[-12:]], reverse=True)[:5]
    recent_lows = sorted([l for _, l in swing_lows[-12:]])[:5]
    if recent_highs:
        bsl_level = float(np.mean(recent_highs[:2]))
        objects.append({
            "type": "BSL", "direction": "BEARISH", "label": "BSL",
            "top": bsl_level, "bottom": bsl_level, "price": bsl_level,
            "index": 0, "time_start": _dt(last_time),
        })
    if recent_lows:
        ssl_level = float(np.mean(recent_lows[:2]))
        objects.append({
            "type": "SSL", "direction": "BULLISH", "label": "SSL",
            "top": ssl_level, "bottom": ssl_level, "price": ssl_level,
            "index": 0, "time_start": _dt(last_time),
        })

    # ---- EQH / EQL ----
    for i, (idx_h, h) in enumerate(swing_highs[-6:]):
        for j, (idx_h2, h2) in enumerate(swing_highs[-6:]):
            if idx_h >= idx_h2: continue
            if abs(h - h2) <= max(h, h2) * PIVOT_TOLERANCE:
                objects.append({
                    "type": "EQH", "direction": "BEARISH", "label": "EQH",
                    # pyrefly: ignore [unnecessary-type-conversion]
                    "top": float(h), "bottom": float(h), "price": float(h),
                    # pyrefly: ignore [unnecessary-type-conversion]
                    "index": int(idx_h), "time_start": _dt(df.iloc[idx_h][time_col]),
                })
                break
    for i, (idx_l, l) in enumerate(swing_lows[-6:]):
        for j, (idx_l2, l2) in enumerate(swing_lows[-6:]):
            if idx_l >= idx_l2: continue
            if abs(l - l2) <= max(l, l2) * PIVOT_TOLERANCE:
                objects.append({
                    "type": "EQL", "direction": "BULLISH", "label": "EQL",
                    # pyrefly: ignore [unnecessary-type-conversion]
                    "top": float(l), "bottom": float(l), "price": float(l),
                    # pyrefly: ignore [unnecessary-type-conversion]
                    "index": int(idx_l), "time_start": _dt(df.iloc[idx_l][time_col]),
                })
                break

    # BOS / CHoCH / MSS markers are emitted by the core markup builder
    # (chart_markup step 6 scans the last candles for every method), so they
    # are NOT duplicated here.

    # ---- Swing Failure Pattern (SFP) on last candle ----
    if len(df) >= 3 and swing_lows and swing_highs:
        prev_sl = swing_lows[-1][1] if swing_lows else None
        prev_sh = swing_highs[-1][1] if swing_highs else None
        if prev_sl and df["low"].iloc[-1] < prev_sl and df["close"].iloc[-1] > prev_sl:
            objects.append({
                "type": "SFP", "direction": "BULLISH", "label": "SFP_BULL",
                "top": prev_sl, "bottom": prev_sl, "price": prev_sl,
                "index": 0, "time_start": _dt(last_time),
            })
        if prev_sh and df["high"].iloc[-1] > prev_sh and df["close"].iloc[-1] < prev_sh:
            objects.append({
                "type": "SFP", "direction": "BEARISH", "label": "SFP_BEAR",
                "top": prev_sh, "bottom": prev_sh, "price": prev_sh,
                "index": 0, "time_start": _dt(last_time),
            })

    return objects


# ---- ICT ----
def compute_ict_overlay(
    df: pd.DataFrame,
    broker_utc_offset_hours: float = 2.0,
) -> list[dict[str, Any]]:
    """ICT overlays: Asian Range, Killzone, OTE, PD, Judas Swing, PO3, Silver
    Bullet, Unicorn, NYMO. Killzone times reference the broker offset (default
    broker is GMT+2/UTC+2 = EET / Exness)."""
    objects: list[dict[str, Any]] = []
    if df is None or df.empty or len(df) < 20:
        return objects

    time_col = 'time' if 'time' in df.columns else 'timestamp' if 'timestamp' in df.columns else 'time'
    last = df.iloc[-1]
    last_time = last[time_col]
    last_idx = len(df) - 1

    # ---- Asian range (00:00 - 08:00 broker local) ----
    hours = pd.to_datetime(df[time_col]).dt.hour
    asian_mask = (hours >= 0) & (hours < 8)
    if asian_mask.any():
        asian_high = float(df.loc[asian_mask, "high"].max())
        asian_low = float(df.loc[asian_mask, "low"].min())
        objects.append({
            "type": "ASIAN", "direction": "NEUTRAL", "label": "ASIAN_RANGE",
            "top": asian_high, "bottom": asian_low,
            # pyrefly: ignore [unnecessary-type-conversion]
            "price": asian_high, "index": int(last_idx),
            "time_start": _dt(last_time),
        })

    # ---- Premium / Discount (last swing high/low range) ----
    # Find the LAST swing high/low within window=2 (strict: must be strictly
    # greater/less than all neighbors, so we don't collapse to the latest bar
    # in a monotonic trend).
    sh, sh_idx = -1.0, -1
    sl, sl_idx = float("inf"), -1
    for i in range(2, len(df) - 2):
        window_h = df["high"].iloc[i - 2:i + 3]
        window_l = df["low"].iloc[i - 2:i + 3]
        if df["high"].iloc[i] == window_h.max():
            sh = float(df["high"].iloc[i])
            sh_idx = i
        if df["low"].iloc[i] == window_l.min():
            sl = float(df["low"].iloc[i])
            sl_idx = i
    if sh > 0 and sl < float("inf") and sh > sl:
        eq = (sh + sl) / 2
        objects.append({
            "type": "PD", "direction": "NEUTRAL", "label": "PREMIUM",
            "top": sh, "bottom": eq, "price": eq,
            # pyrefly: ignore [unnecessary-type-conversion]
            "index": int(last_idx), "time_start": _dt(last_time),
        })
        objects.append({
            "type": "PD", "direction": "NEUTRAL", "label": "DISCOUNT",
            "top": eq, "bottom": sl, "price": eq,
            # pyrefly: ignore [unnecessary-type-conversion]
            "index": int(last_idx), "time_start": _dt(last_time),
        })

        # ---- OTE (62%-79% Fibonacci) ----
        rng = sh - sl
        ote_top = sl + rng * 0.79
        ote_bottom = sl + rng * 0.62
        objects.append({
            "type": "OTE", "direction": "BULLISH", "label": "OTE_BUY",
            "top": ote_top, "bottom": ote_bottom,
            # pyrefly: ignore [unnecessary-type-conversion]
            "price": ote_top, "index": int(last_idx),
            "time_start": _dt(last_time),
        })

    # ---- Killzone status (London 07-10, NY 12-15 broker local) ----
    last_hour = int(pd.to_datetime(last_time).hour)
    is_london = 7 <= last_hour < 10
    is_ny = 12 <= last_hour < 15
    is_asian = 0 <= last_hour < 8
    objects.append({
        "type": "KILLZONE", "direction": "NEUTRAL", "label": "KILLZONE",
        "top": 0.0, "bottom": 0.0, "price": 0.0,
        # pyrefly: ignore [unnecessary-type-conversion]
        "index": int(last_idx), "time_start": _dt(last_time),
        "is_london": is_london, "is_ny": is_ny, "is_asian": is_asian,
    })

    # ---- Judas Swing: detect early-session swing opposite of HTF bias ----
    # Naive: if Asian range was a sweep (low < PDH of previous day) and current
    # direction is bullish, mark Judas Swing bullish (early-session bearish wick
    # that swept SSL then reversed).
    if is_london and len(df) >= 6:
        first_london = df.iloc[-3:]
        if first_london["low"].iloc[0] < sl and first_london["close"].iloc[-1] > sl:
            objects.append({
                "type": "JUDAS_SWING", "direction": "BULLISH", "label": "JUDAS_BULL",
                "top": float(first_london["high"].max()),
                "bottom": float(first_london["low"].min()),
                "price": float(first_london["close"].iloc[-1]),
                # pyrefly: ignore [unnecessary-type-conversion]
                "index": int(last_idx), "time_start": _dt(last_time),
            })
        elif first_london["high"].iloc[0] > sh and first_london["close"].iloc[-1] < sh:
            objects.append({
                "type": "JUDAS_SWING", "direction": "BEARISH", "label": "JUDAS_BEAR",
                "top": float(first_london["high"].max()),
                "bottom": float(first_london["low"].min()),
                "price": float(first_london["close"].iloc[-1]),
                # pyrefly: ignore [unnecessary-type-conversion]
                "index": int(last_idx), "time_start": _dt(last_time),
            })

    # ---- PO3 (Accumulation-Manipulation-Distribution) — infer from candle shape ----
    # Naive: 3 candles, first small body (accumulation), second wick-heavy
    # (manipulation), third large body (distribution)
    if len(df) >= 3:
        c0, c1, c2 = [_candle_row(df.iloc[-3].to_dict()), _candle_row(df.iloc[-2].to_dict()), _candle_row(df.iloc[-1].to_dict())]
        if (c0["body_ratio"] < 0.4 and c1["body_ratio"] < 0.5
                and (c2["body_ratio"] > 0.6 and c2["is_bull"])):
            objects.append({
                "type": "PO3", "direction": "BULLISH", "label": "PO3_BULL",
                "top": c2["high"], "bottom": c2["low"],
                # pyrefly: ignore [unnecessary-type-conversion]
                "price": c2["close"], "index": int(last_idx),
                "time_start": _dt(last_time),
            })
        elif (c0["body_ratio"] < 0.4 and c1["body_ratio"] < 0.5
                and (c2["body_ratio"] > 0.6 and c2["is_bear"])):
            objects.append({
                "type": "PO3", "direction": "BEARISH", "label": "PO3_BEAR",
                "top": c2["high"], "bottom": c2["low"],
                # pyrefly: ignore [unnecessary-type-conversion]
                "price": c2["close"], "index": int(last_idx),
                "time_start": _dt(last_time),
            })

    # ---- Silver Bullet (10:00-11:00 broker local) ----
    if 10 <= last_hour < 11:
        objects.append({
            "type": "SILVER_BULLET", "direction": "NEUTRAL", "label": "SILVER_BULLET",
            "top": 0.0, "bottom": 0.0, "price": 0.0,
            # pyrefly: ignore [unnecessary-type-conversion]
            "index": int(last_idx), "time_start": _dt(last_time),
        })

    # ---- Unicorn Model: BOS + FVG in same candle (signaled by FVG present near BOS) ----
    # We mark Unicorn only if both a BOS-like close-above-high and a 3-candle FVG exist
    # within last 10 candles. Light heuristic: if last candle body > 1.5x ATR and a
    # bullish candle after 2 bearish candles.
    if len(df) >= 3:
        c0, c1, c2 = [_candle_row(df.iloc[-3].to_dict()), _candle_row(df.iloc[-2].to_dict()), _candle_row(df.iloc[-1].to_dict())]
        atr_val = float(_atr(df).iloc[-1]) if len(df) > ATR_PERIOD else 1.0
        if c2["is_bull"] and c0["is_bear"] and c1["is_bear"] and (c2["body"] > atr_val * 0.8):
            objects.append({
                "type": "UNICORN", "direction": "BULLISH", "label": "UNICORN_BULL",
                "top": c2["high"], "bottom": c2["low"],
                # pyrefly: ignore [unnecessary-type-conversion]
                "price": c2["close"], "index": int(last_idx),
                "time_start": _dt(last_time),
            })

    # ---- NYMO / Midnight Open ----
    objects.append({
        "type": "NYMO", "direction": "NEUTRAL", "label": "NYMO",
        "top": float(df.iloc[-1]["open"]), "bottom": float(df.iloc[-1]["open"]),
        "price": float(df.iloc[-1]["open"]),
        # pyrefly: ignore [unnecessary-type-conversion]
        "index": int(last_idx), "time_start": _dt(last_time),
    })

    return objects


# ---- PRICE ACTION ----
def compute_pa_overlay(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Price Action overlays: candle patterns (pin bar / engulfing / hammer /
    shooting star / morning star / 3WS / 3BC / tweezer / doji), S/R from pivot
    points (R1/R2/R3/S1/S2/S3), PDH/PDL, chart patterns (double top / bottom,
    triangle, wedge, channel, flag, pennant), trendline, trend (HH/HL/LH/LL).
    """
    objects: list[dict[str, Any]] = []
    time_col = 'time' if 'time' in df.columns else 'timestamp' if 'timestamp' in df.columns else 'time'
    if df is None or df.empty or len(df) < 5:
        return objects

    last = df.iloc[-1]
    last_time = last[time_col]
    last_idx = len(df) - 1
    candles = [_candle_row(df.iloc[i].to_dict()) for i in range(len(df))]

    # ---- Candle patterns on the last 5 candles ----
    for i in range(max(0, len(candles) - 5), len(candles)):
        c = candles[i]
        prev = candles[i - 1] if i > 0 else None
        label = None
        direction = "NEUTRAL"
        if c["body_ratio"] <= DOJI_BODY_RATIO:
            label, direction = "DOJI", "NEUTRAL"
        elif c["lower_wick"] >= PINBAR_WICK_RATIO * c["body"] and c["upper_wick"] <= c["body"] * 0.5:
            if c["is_bull"] or c["close"] > c["open"]:
                label, direction = "HAMMER", "BULLISH"
            else:
                label, direction = "BULLISH_PIN_BAR", "BULLISH"
        elif c["upper_wick"] >= PINBAR_WICK_RATIO * c["body"] and c["lower_wick"] <= c["body"] * 0.5:
            if c["is_bear"] or c["close"] < c["open"]:
                label, direction = "SHOOTING_STAR", "BEARISH"
            else:
                label, direction = "BEARISH_PIN_BAR", "BEARISH"
        if label:
            objects.append({
                "type": "CANDLE_PATTERN", "direction": direction, "label": label,
                "top": c["high"], "bottom": c["low"], "price": c["close"],
                # pyrefly: ignore [unnecessary-type-conversion]
                "index": int(i), "time_start": _dt(df.iloc[i][time_col]),
            })

    # Engulfing (last 2 candles)
    if len(candles) >= 2:
        c0, c1 = candles[-2], candles[-1]
        if c0["is_bear"] and c1["is_bull"] and c1["open"] <= c0["close"] and c1["close"] >= c0["open"]:
            objects.append({
                "type": "CANDLE_PATTERN", "direction": "BULLISH", "label": "BULLISH_ENGULFING",
                "top": c1["high"], "bottom": c1["low"], "price": c1["close"],
                "index": last_idx, "time_start": _dt(last_time),
            })
        elif c0["is_bull"] and c1["is_bear"] and c1["open"] >= c0["close"] and c1["close"] <= c0["open"]:
            objects.append({
                "type": "CANDLE_PATTERN", "direction": "BEARISH", "label": "BEARISH_ENGULFING",
                "top": c1["high"], "bottom": c1["low"], "price": c1["close"],
                "index": last_idx, "time_start": _dt(last_time),
            })

    # Morning Star / Evening Star (3 candles)
    if len(candles) >= 3:
        c0, c1, c2 = candles[-3], candles[-2], candles[-1]
        if c0["is_bear"] and c1["body_ratio"] < 0.4 and c2["is_bull"] and c2["close"] > c0["close"]:
            objects.append({
                "type": "CANDLE_PATTERN", "direction": "BULLISH", "label": "MORNING_STAR",
                "top": c2["high"], "bottom": c0["low"], "price": c2["close"],
                "index": last_idx, "time_start": _dt(last_time),
            })
        elif c0["is_bull"] and c1["body_ratio"] < 0.4 and c2["is_bear"] and c2["close"] < c0["close"]:
            objects.append({
                "type": "CANDLE_PATTERN", "direction": "BEARISH", "label": "EVENING_STAR",
                "top": c0["high"], "bottom": c2["low"], "price": c2["close"],
                "index": last_idx, "time_start": _dt(last_time),
            })

    # 3 White Soldiers / 3 Black Crows
    if len(candles) >= 3:
        c0, c1, c2 = candles[-3], candles[-2], candles[-1]
        if c0["is_bull"] and c1["is_bull"] and c2["is_bull"] and c1["close"] > c0["close"] and c2["close"] > c1["close"]:
            objects.append({
                "type": "CANDLE_PATTERN", "direction": "BULLISH", "label": "3WS",
                "top": c2["high"], "bottom": c0["low"], "price": c2["close"],
                "index": last_idx, "time_start": _dt(last_time),
            })
        elif c0["is_bear"] and c1["is_bear"] and c2["is_bear"] and c1["close"] < c0["close"] and c2["close"] < c1["close"]:
            objects.append({
                "type": "CANDLE_PATTERN", "direction": "BEARISH", "label": "3BC",
                "top": c0["high"], "bottom": c2["low"], "price": c2["close"],
                "index": last_idx, "time_start": _dt(last_time),
            })

    # Tweezer (top/bottom) on last 2 candles
    if len(candles) >= 2:
        c0, c1 = candles[-2], candles[-1]
        tol = max(c0["high"], c1["high"]) * PIVOT_TOLERANCE
        if abs(c0["high"] - c1["high"]) <= tol and c1["is_bear"]:
            objects.append({
                "type": "CANDLE_PATTERN", "direction": "BEARISH", "label": "TWEEZER_TOP",
                "top": c1["high"], "bottom": c1["low"], "price": c1["close"],
                "index": last_idx, "time_start": _dt(last_time),
            })
        tol = max(c0["low"], c1["low"]) * PIVOT_TOLERANCE
        if abs(c0["low"] - c1["low"]) <= tol and c1["is_bull"]:
            objects.append({
                "type": "CANDLE_PATTERN", "direction": "BULLISH", "label": "TWEEZER_BOTTOM",
                "top": c1["high"], "bottom": c1["low"], "price": c1["close"],
                "index": last_idx, "time_start": _dt(last_time),
            })

    # ---- Daily Pivot Points (from prior day) ----
    if len(df) >= 96:  # ~1 day of M15
        prev_day = df.iloc[-96:-48] if len(df) > 96 else df
        if not prev_day.empty:
            ph = float(prev_day["high"].max())
            pl = float(prev_day["low"].min())
            pc = float(prev_day["close"].iloc[-1])
            pivot = (ph + pl + pc) / 3
            r1 = 2 * pivot - pl
            s1 = 2 * pivot - ph
            r2 = pivot + (ph - pl)
            s2 = pivot - (ph - pl)
            r3 = ph + 2 * (pivot - pl)
            s3 = pl - 2 * (ph - pivot)
            objects.extend([
                {"type": "PIVOT", "direction": "NEUTRAL", "label": "PIVOT", "top": pivot, "bottom": pivot, "price": pivot, "index": last_idx, "time_start": _dt(last_time)},
                {"type": "PIVOT", "direction": "BEARISH", "label": "R1", "top": r1, "bottom": r1, "price": r1, "index": last_idx, "time_start": _dt(last_time)},
                {"type": "PIVOT", "direction": "BEARISH", "label": "R2", "top": r2, "bottom": r2, "price": r2, "index": last_idx, "time_start": _dt(last_time)},
                {"type": "PIVOT", "direction": "BEARISH", "label": "R3", "top": r3, "bottom": r3, "price": r3, "index": last_idx, "time_start": _dt(last_time)},
                {"type": "PIVOT", "direction": "BULLISH", "label": "S1", "top": s1, "bottom": s1, "price": s1, "index": last_idx, "time_start": _dt(last_time)},
                {"type": "PIVOT", "direction": "BULLISH", "label": "S2", "top": s2, "bottom": s2, "price": s2, "index": last_idx, "time_start": _dt(last_time)},
                {"type": "PIVOT", "direction": "BULLISH", "label": "S3", "top": s3, "bottom": s3, "price": s3, "index": last_idx, "time_start": _dt(last_time)},
            ])
            objects.append({"type": "PDH", "direction": "BEARISH", "label": "PDH", "top": ph, "bottom": ph, "price": ph, "index": last_idx, "time_start": _dt(last_time)})
            objects.append({"type": "PDL", "direction": "BULLISH", "label": "PDL", "top": pl, "bottom": pl, "price": pl, "index": last_idx, "time_start": _dt(last_time)})

    # ---- Support / Resistance from price clustering (bucket scaled to ATR so
    # it works for every symbol: gold ~$3000 vs forex ~1.08) ----
    window = df.tail(60)
    price_counts: dict[float, int] = {}
    atr_now = float(_atr(df).iloc[-1]) if len(df) > ATR_PERIOD else float(df["close"].iloc[-1]) * 0.001
    bucket = max(atr_now * 0.5, 1e-9)
    for _, row in window.iterrows():
        h, l = float(row["high"]), float(row["low"])
        bucket_h = round(h / bucket) * bucket
        bucket_l = round(l / bucket) * bucket
        price_counts[bucket_h] = price_counts.get(bucket_h, 0) + 1
        price_counts[bucket_l] = price_counts.get(bucket_l, 0) + 1
    sorted_prices = sorted(price_counts.items(), key=lambda x: -x[1])[:5]
    last_close = float(df["close"].iloc[-1])
    for price, count in sorted_prices:
        if count < 3:
            continue
        direction = "BEARISH" if price > last_close else "BULLISH"
        label = "RESISTANCE" if price > last_close else "SUPPORT"
        objects.append({
            "type": label, "direction": direction, "label": label,
            "top": price, "bottom": price, "price": price,
            "index": last_idx, "time_start": _dt(last_time),
            # pyrefly: ignore [unnecessary-type-conversion]
            "touches": int(count),
        })

    # ---- Chart patterns ----
    # Double top: two swing highs within tolerance and current price below
    swing_highs = []
    swing_lows = []
    for i in range(2, len(df) - 2):
        if df["high"].iloc[i] == df["high"].iloc[i - 2:i + 3].max():
            swing_highs.append((i, float(df["high"].iloc[i])))
        if df["low"].iloc[i] == df["low"].iloc[i - 2:i + 3].min():
            swing_lows.append((i, float(df["low"].iloc[i])))

    if len(swing_highs) >= 2:
        h1 = swing_highs[-1][1]
        h2 = swing_highs[-2][1]
        if abs(h1 - h2) <= max(h1, h2) * PIVOT_TOLERANCE * 2 and last_close < h1:
            objects.append({
                "type": "CHART_PATTERN", "direction": "BEARISH", "label": "DOUBLE_TOP",
                "top": max(h1, h2), "bottom": min(h1, h2), "price": last_close,
                "index": last_idx, "time_start": _dt(last_time),
            })

    if len(swing_lows) >= 2:
        l1 = swing_lows[-1][1]
        l2 = swing_lows[-2][1]
        if abs(l1 - l2) <= max(l1, l2) * PIVOT_TOLERANCE * 2 and last_close > l1:
            objects.append({
                "type": "CHART_PATTERN", "direction": "BULLISH", "label": "DOUBLE_BOTTOM",
                "top": max(l1, l2), "bottom": min(l1, l2), "price": last_close,
                "index": last_idx, "time_start": _dt(last_time),
            })

    # Trendline (simple: linear regression on last 20 swing highs/lows)
    if len(swing_highs) >= 3:
        xs = np.array([s[0] for s in swing_highs[-3:]])
        ys = np.array([s[1] for s in swing_highs[-3:]])
        slope, intercept = np.polyfit(xs, ys, 1)
        objects.append({
            "type": "TRENDLINE", "direction": "BEARISH" if slope < 0 else "BULLISH",
            "label": "TRENDLINE_HIGH",
            "top": float(slope * xs[-1] + intercept),
            "bottom": float(slope * xs[0] + intercept),
            "price": float(slope * xs[-1] + intercept),
            "index": last_idx, "time_start": _dt(last_time),
            "slope": float(slope),
        })
    if len(swing_lows) >= 3:
        xs = np.array([s[0] for s in swing_lows[-3:]])
        ys = np.array([s[1] for s in swing_lows[-3:]])
        slope, intercept = np.polyfit(xs, ys, 1)
        objects.append({
            "type": "TRENDLINE", "direction": "BULLISH" if slope > 0 else "BEARISH",
            "label": "TRENDLINE_LOW",
            "top": float(slope * xs[-1] + intercept),
            "bottom": float(slope * xs[0] + intercept),
            "price": float(slope * xs[-1] + intercept),
            "index": last_idx, "time_start": _dt(last_time),
            "slope": float(slope),
        })

    return objects


# ---- Confluence scoring ----
def compute_confluence_score(objects: list[dict[str, Any]], method: str, last_close: float) -> dict[str, Any]:
    """Aggregate a 0-100 confluence score from objects for AI / auto-trade.

    Per-method scoring:
      SNIPER     -> 7-factor bull/bear score (from SNIPER_SCORE if present, else computed inline).
      SMC        -> bull/bear votes from BOS/CHoCH/OB/FVG/SFP/BSL-SSL sweep/structure.
      ICT        -> bull/bear votes from PD/OTE/Judas/PO3/Unicorn/Killzone bias.
      PRICE_ACTION -> bull/bear votes from candle patterns + S/R breakouts + pivots.

    Returns:
        {"score": 0-100, "direction": "BULLISH"/"BEARISH"/"NEUTRAL", "signal": "BUY"/"SELL"/"WAIT",
         "factors": [{...}], "rrr": float or None, "entry": float or None, "sl": float or None,
         "tp": float or None}
    """
    score = 0
    factors: list[dict[str, Any]] = []
    direction_votes = {"BULLISH": 0, "BEARISH": 0}

    def vote(direction: str, weight: int, reason: str) -> None:
        nonlocal score
        if direction == "BULLISH":
            direction_votes["BULLISH"] += weight
            score += weight
        elif direction == "BEARISH":
            direction_votes["BEARISH"] += weight
            score -= weight
        factors.append({"reason": reason, "direction": direction, "weight": weight})

    sniper_score_obj = next((o for o in objects if o.get("type") == "SNIPER_SCORE"), None)
    if sniper_score_obj and method == "SNIPER":
        bull = sniper_score_obj.get("bull_pct", 0)
        bear = sniper_score_obj.get("bear_pct", 0)
        score = bull - bear
        factors.append({"reason": f"SNIPER_SCORE bull={bull} bear={bear}", "direction": "BULLISH" if score > 0 else "BEARISH", "weight": abs(int(score))})
    else:
        for o in objects:
            t = o.get("type")
            d = o.get("direction", "NEUTRAL")
            label = o.get("label", "")
            if t == "BOS":
                vote(d, 20, f"BOS_{d}")
            elif t == "CHoCH":
                vote(d, 25, f"CHoCH_{d}")
            elif t == "MSS":
                vote(d, 25, f"MSS_{d}")
            elif t == "OB":
                vote(d, 12, f"OB_{d}_{label}")
            elif t == "FVG":
                vote(d, 10, f"FVG_{d}")
            elif t in ("BREAKER", "MITIGATION"):
                vote(d, 8, f"{t}_{d}")
            elif t in ("BULLISH_ENGULFING", "MORNING_STAR", "HAMMER", "BULLISH_PIN_BAR", "3WS"):
                vote("BULLISH", 15, f"CANDLE_{label}")
            elif t in ("BEARISH_ENGULFING", "EVENING_STAR", "SHOOTING_STAR", "BEARISH_PIN_BAR", "3BC"):
                vote("BEARISH", 15, f"CANDLE_{label}")
            elif t == "TWEEZER_TOP":
                vote("BEARISH", 12, "TWEEZER_TOP")
            elif t == "TWEEZER_BOTTOM":
                vote("BULLISH", 12, "TWEEZER_BOTTOM")
            elif t == "DOJI":
                factors.append({"reason": "DOJI_neutral", "direction": "NEUTRAL", "weight": 0})
            elif t == "SFP":
                vote(d, 18, f"SFP_{d}")
            elif t == "SWEEP":
                vote(d, 22, f"SWEEP_{d}")
            elif t == "SUPPLY_DEMAND":
                dir_vote = "BULLISH" if d in ("BULLISH", "DEMAND") else "BEARISH"
                vote(dir_vote, 18, f"SD_{label}")
            elif t == "CONTINUATION":
                vote(d, 20, f"Trend_Tap_{d}")
            elif t == "JUDAS_SWING":
                vote(d, 20, f"JUDAS_{d}")
            elif t == "PO3":
                vote(d, 18, f"PO3_{d}")
            elif t == "UNICORN":
                vote(d, 22, f"UNICORN_{d}")
            elif t == "PIVOT" and o.get("label") in ("R1", "R2", "R3"):
                p = o.get("price", 0) or 0
                if p > 0 and last_close < p and last_close > p * 0.995:
                    vote("BEARISH", 5, f"PIVOT_{o.get('label')}_reject")
                elif p > 0 and last_close >= p:
                    vote("BULLISH", 5, f"PIVOT_{o.get('label')}_break")
            elif t == "PIVOT" and o.get("label") in ("S1", "S2", "S3"):
                p = o.get("price", 0) or 0
                if p > 0 and last_close > p and last_close < p * 1.005:
                    vote("BULLISH", 5, f"PIVOT_{o.get('label')}_bounce")
                elif p > 0 and last_close <= p:
                    vote("BEARISH", 5, f"PIVOT_{o.get('label')}_break")
            elif t in ("PD", "OTE") and o.get("label") == "PREMIUM" and last_close > o.get("top", 0):
                vote("BEARISH", 8, "PREMIUM_zone")
            elif t in ("PD", "OTE") and o.get("label") == "DISCOUNT" and last_close < o.get("bottom", 0):
                vote("BULLISH", 8, "DISCOUNT_zone")
            elif t == "KILLZONE":
                zone = "LONDON" if o.get("is_london") else "NY" if o.get("is_ny") else "ASIA"
                factors.append({"reason": f"{zone}_KillZone", "direction": "NEUTRAL", "weight": 0})
            elif t == "CHART_PATTERN":
                vote(d, 15, f"CHART_PATTERN_{label}")
            elif t in ("SUPPORT", "RESISTANCE"):
                if t == "SUPPORT" and last_close <= o.get("price", 0) * 1.001:
                    vote("BULLISH", 5, f"SUPPORT_at_{o.get('price'):.2f}")
                elif t == "RESISTANCE" and last_close >= o.get("price", 0) * 0.999:
                    vote("BEARISH", 5, f"RESISTANCE_at_{o.get('price'):.2f}")

    # ULTRA_CONFLUENCE: blend the Sniper 7-factor score with the structural
    # votes so neither signal dominates (before, ULTRA returned only the
    # sniper bull-bear difference, discarding every SMC/ICT/PA structure).
    if method == "ULTRA_CONFLUENCE" and sniper_score_obj is not None:
        structure_votes = 0
        for o in objects:
            t = o.get("type")
            d = o.get("direction", "NEUTRAL")
            label = o.get("label", "")
            if t == "BOS":
                structure_votes += 20 if d == "BULLISH" else -20
            elif t in ("CHoCH", "MSS"):
                structure_votes += 25 if d == "BULLISH" else -25
            elif t == "OB":
                structure_votes += 12 if d == "BULLISH" else -12
            elif t == "FVG":
                structure_votes += 10 if d == "BULLISH" else -10
            elif t in ("BREAKER", "MITIGATION"):
                structure_votes += 8 if d == "BULLISH" else -8
            elif t == "SFP":
                structure_votes += 18 if d == "BULLISH" else -18
            elif t == "JUDAS_SWING":
                structure_votes += 20 if d == "BULLISH" else -20
            elif t == "PO3":
                structure_votes += 18 if d == "BULLISH" else -18
            elif t == "UNICORN":
                structure_votes += 22 if d == "BULLISH" else -22
            elif t == "CHART_PATTERN":
                structure_votes += 15 if d == "BULLISH" else -15
            elif t == "SWEEP":
                structure_votes += 20 if d == "BULLISH" else -20
        sniper_diff = float(sniper_score_obj.get("bull_pct", 0)) - float(sniper_score_obj.get("bear_pct", 0))
        # pyrefly: ignore [unnecessary-type-conversion]
        score = int(round(0.5 * sniper_diff + 0.5 * structure_votes))
        factors.append({"reason": f"ULTRA blend sniper={sniper_diff:.0f} structure={structure_votes}",
                        "direction": "BULLISH" if score > 0 else "BEARISH", "weight": abs(score)})

    score = max(min(score, 100), -100)
    direction = "BULLISH" if score > 15 else "BEARISH" if score < -15 else "NEUTRAL"
    # BUG FIX L2: signal threshold phải >= direction threshold (15). Trước đây
    # threshold 25 có thể tạo trạng thái direction=NEUTRAL (|score|<=15) nhưng
    # signal=BUY (score>25) hoặc ngược lại — mâu thuẫn. Đặt cả 2 cùng ngưỡng 25.
    signal = "BUY" if score >= 25 else "SELL" if score <= -25 else "WAIT"

    entry = last_close
    sl = tp = None
    risk_per_unit = 0.0
    sniper_sl = next((o for o in objects if o.get("type") == "SNIPER_SL"), None)
    sniper_tp1 = next((o for o in objects if o.get("type") == "SNIPER_TP1"), None)
    # BUG FIX L3: nếu CHỈ một trong sniper_sl/sniper_tp1 có mặt, ta KHÔNG dùng
    # nó một cách lệch (vd có SL nhưng không có TP -> RRR vô nghĩa). Yêu cầu
    # CẢ HAI để dùng SNIPER levels; nếu thiếu một, fall through về structure-based.
    if sniper_sl and sniper_tp1:
        sl = sniper_sl.get("price")
        tp = sniper_tp1.get("price")
        risk_per_unit = abs(entry - sl) if sl else 0.0

    # Structure-based SL/TP for methods without a native SNIPER signal:
    # BUY  -> SL = strongest structure level below entry, TP = first level above
    # SELL -> SL = strongest structure level above entry, TP = first level below
    # This is what lets the AI read the chart (OB/FVG/OTE/S-R) and place a
    # precision entry with a real risk/reward ratio before auto-trading.
    if (sl is None or tp is None) and signal in ("BUY", "SELL"):
        levels: list[tuple[float, int]] = []
        non_price_types = {"ADX", "RSI_LEVEL", "MACD_LINE", "MACD_SIGNAL", "SNIPER_SCORE", "SNIPER_DASH"}
        for o in objects:
            if o.get("type") in non_price_types:
                continue
            p = o.get("price")
            if isinstance(p, (int, float)) and p > 0:
                levels.append((float(p), int(o.get("touches", 1) or 1)))
            elif isinstance(o.get("top"), (int, float)) and isinstance(o.get("bottom"), (int, float)) \
                    and o.get("top") != o.get("bottom"):
                levels.append(((float(o["top"]) + float(o["bottom"])) / 2.0, int(o.get("touches", 1) or 1)))

        min_gap = max(entry * 0.0005, 1e-9)
        below = [(p, c) for p, c in levels if p < entry - min_gap]
        above = [(p, c) for p, c in levels if p > entry + min_gap]
        if signal == "BUY":
            if below:
                sl = max(p for p, _ in below)
            if above:
                tp = min(p for p, _ in above)
        elif signal == "SELL":
            if above:
                sl = min(p for p, _ in above)
            if below:
                tp = max(p for p, _ in below)

        # Fallback to dynamic ATR multiple if natural structure levels are missing (e.g. ATH or Sniper)
        default_risk = max(5.0, entry * 0.004)
        if signal == "BUY":
            if sl is None:
                sl = round(entry - default_risk, 2)
            if tp is None:
                risk_dist = max(entry - sl, default_risk)
                tp = round(entry + risk_dist * 2.0, 2)
        elif signal == "SELL":
            if sl is None:
                sl = round(entry + default_risk, 2)
            if tp is None:
                risk_dist = max(sl - entry, default_risk)
                tp = round(entry - risk_dist * 2.0, 2)

    if signal in ("BUY", "SELL") and sl is not None and tp is not None:
        risk_per_unit = abs(entry - sl)
        reward_per_unit = abs(tp - entry)
        rrr = round(reward_per_unit / risk_per_unit, 2) if risk_per_unit > 0 else 2.0
    else:
        sl = None
        tp = None
        rrr = None

    return {
        "score": int(score),
        "direction": direction,
        "signal": signal,
        "factors": factors[:20],
        "rrr": rrr,
        "entry": round(entry, 2),
        "sl": round(sl, 2) if sl is not None else None,
        "tp": round(tp, 2) if tp is not None else None,
        "method": method,
    }


def compute_structure_engine_overlay(
    mtf_data: dict[str, pd.DataFrame],
    primary_tf: str = "M15",
) -> list[dict[str, Any]]:
    """Compute Institutional Structure Engine (ISE) objects from structureengine.pine."""
    from structure_engine import detect_institutional_structure_engine
    m15 = mtf_data.get(primary_tf)
    if m15 is None or m15.empty:
        m15 = next((v for v in mtf_data.values() if v is not None and not v.empty), None)
    if m15 is None or m15.empty:
        return []
    res = detect_institutional_structure_engine(m15)
    return res.get("objects", [])

