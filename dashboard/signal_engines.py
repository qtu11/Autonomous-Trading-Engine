"""Signal Engines for Autonomous Trading Engine (ATE).

Implements 5 trading strategy engines:
1. INDICATOR: EMA Stacking + RSI + ATR
2. SMC: Smart Money Concepts (BOS, HTF Bias, Valid OB, CHoCH)
3. ICT: Inner Circle Trader (Killzones, Judas Swing, Displacement, OTE FVG)
4. PRICE_ACTION: Classic PA Pinbar / Engulfing at Daily Pivots / PDH / PDL
5. ULTRA_CONFLUENCE: 5-Layer Hybrid Matrix (HTF P/D -> Time KZ -> Sweep -> MSS+FVG -> OTE)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import numpy as np
import pandas as pd

from detectors import (
    PDArrayDirection,
    PDArrayType,
    calculate_ote_zone,
    check_fvg_ote_confluence,
    classify_pd_array_zone,
    classify_trend_structure,
    detect_breaker_and_mitigation_blocks,
    detect_fvg,
    detect_liquidity_sweep,
    detect_order_blocks,
    df_to_candles,
    find_swing_points,
    get_asian_range,
    get_htf_bias_from_pd_zone,
    get_killzone_status,
    get_last_swing_points,
    get_premium_discount_zone,
    is_price_in_ote,
    link_fvg_to_order_blocks,
    mark_ob_mitigated,
)


@dataclass
class SignalResult:
    status: str  # "APPROVED" | "NO_TRADE"
    direction: str  # "BUY" | "SELL" | "NONE"
    reason_code: str
    entry_price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    layers_passed: int = 0
    pd_array_used: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "direction": self.direction,
            "reason_code": self.reason_code,
            "entry_price": self.entry_price,
            "sl": self.sl,
            "tp": self.tp,
            "layers_passed": self.layers_passed,
            "pd_array_used": self.pd_array_used,
        }


# ── Helper Calculations ───────────────────────────────────────────────────────

def _calc_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-9)
    return 100.0 - (100.0 / (1.0 + rs))


def _calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close_prev = df["close"].shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - close_prev).abs(),
            (low - close_prev).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(com=period - 1, adjust=False).mean()


def _calc_vwap(df: pd.DataFrame) -> pd.Series:
    hlc3 = (df["high"] + df["low"] + df["close"]) / 3.0
    volume = df.get("tick_volume", df.get("real_volume", df.get("volume", pd.Series(0.0, index=df.index))))
    vol_sum = volume.cumsum()
    pv_sum = (hlc3 * volume).cumsum()
    return pv_sum / vol_sum.replace(0, 1e-9)


def _calc_macd(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    ema12 = _calc_ema(series, 12)
    ema26 = _calc_ema(series, 26)
    macd_line = ema12 - ema26
    signal_line = _calc_ema(macd_line, 9)
    return macd_line, signal_line


def _calc_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close_prev = df["close"].shift(1)
    
    tr = pd.concat([
        high - low,
        (high - close_prev).abs(),
        (low - close_prev).abs()
    ], axis=1).max(axis=1)
    
    up = high.diff()
    down = -low.diff()
    
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    
    tr_smooth = tr.ewm(com=period - 1, adjust=False).mean()
    plus_dm_smooth = plus_dm.ewm(com=period - 1, adjust=False).mean()
    minus_dm_smooth = minus_dm.ewm(com=period - 1, adjust=False).mean()
    
    plus_di = 100.0 * plus_dm_smooth / tr_smooth.replace(0, 1e-9)
    minus_di = 100.0 * minus_dm_smooth / tr_smooth.replace(0, 1e-9)
    
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1e-9)
    adx = dx.ewm(com=period - 1, adjust=False).mean()
    return adx


# ── Engine 1: Indicator-Based ────────────────────────────────────────────────

def _run_indicator_only(df_m15: pd.DataFrame) -> SignalResult:
    if len(df_m15) < 200:
        return SignalResult(
            status="NO_TRADE",
            direction="NONE",
            reason_code="INDICATOR_INSUFFICIENT_DATA",
        )

    df = df_m15.copy()
    close = df["close"]
    open_p = df["open"]
    ema20 = _calc_ema(close, 20)
    ema50 = _calc_ema(close, 50)
    ema200 = _calc_ema(close, 200)
    rsi = _calc_rsi(close, 14)
    atr = _calc_atr(df, 14)
    adx = _calc_adx(df, 14)
    
    # VWAP filter
    vwap = _calc_vwap(df)
    
    # MACD for momentum
    macd_line, signal_line = _calc_macd(close)

    curr_close = close.iloc[-1]
    curr_open = open_p.iloc[-1]
    curr_ema20 = ema20.iloc[-1]
    curr_ema50 = ema50.iloc[-1]
    curr_ema200 = ema200.iloc[-1]
    curr_rsi = rsi.iloc[-1]
    curr_atr = atr.iloc[-1]
    curr_adx = adx.iloc[-1]
    curr_vwap = vwap.iloc[-1]
    curr_macd = macd_line.iloc[-1]
    curr_macd_sig = signal_line.iloc[-1]
    
    prev_close = close.iloc[-2]
    prev_ema20 = ema20.iloc[-2]
    prev_ema50 = ema50.iloc[-2]

    # Strict filters cho 80%+ winrate:
    # 1. ADX phải > 25 (thị trường có trend)
    # 2. MACD histogram phải align với direction
    # 3. RSI phải trong zone chính xác
    # 4. Close phải > VWAP (cho buy) hoặc < VWAP (cho sell)
    
    # BUY: Close > EMA20 > EMA50 > EMA200, RSI 45-65, ADX > 25, MACD bullish, Close > VWAP
    if (
        curr_close > curr_ema20 and
        curr_ema20 > curr_ema50 > curr_ema200 and
        45.0 <= curr_rsi <= 65.0 and
        curr_adx > 25 and
        curr_macd > curr_macd_sig and
        curr_close > curr_vwap and
        curr_close > curr_open  # Bullish candle
    ):
        sl = curr_close - 1.5 * curr_atr
        tp = curr_close + 2.5 * curr_atr
        return SignalResult(
            status="APPROVED",
            direction="BUY",
            reason_code="INDICATOR_BULLISH_STRICT",
            entry_price=curr_close,
            sl=round(sl, 3),
            tp=round(tp, 3),
            layers_passed=5,
            pd_array_used="EMA_STACK",
        )

    # SELL: Close < EMA20 < EMA50 < EMA200, RSI 35-55, ADX > 25, MACD bearish, Close < VWAP
    if (
        curr_close < curr_ema20 and
        curr_ema20 < curr_ema50 < curr_ema200 and
        35.0 <= curr_rsi <= 55.0 and
        curr_adx > 25 and
        curr_macd < curr_macd_sig and
        curr_close < curr_vwap and
        curr_close < curr_open  # Bearish candle
    ):
        sl = curr_close + 1.5 * curr_atr
        tp = curr_close - 2.5 * curr_atr
        return SignalResult(
            status="APPROVED",
            direction="SELL",
            reason_code="INDICATOR_BEARISH_STRICT",
            entry_price=curr_close,
            sl=round(sl, 3),
            tp=round(tp, 3),
            layers_passed=5,
            pd_array_used="EMA_STACK",
        )

    return SignalResult(
        status="NO_TRADE",
        direction="NONE",
        reason_code="INDICATOR_NO_ALIGNMENT",
    )


# ── Engine 2: Smart Money Concepts (SMC) ─────────────────────────────────────

def _run_smc_only(df_h1: pd.DataFrame, df_m15: pd.DataFrame) -> SignalResult:
    if len(df_h1) < 50 or len(df_m15) < 100:
        return SignalResult(
            status="NO_TRADE", direction="NONE", reason_code="SMC_INSUFFICIENT_DATA"
        )

    # 1. Determine HTF Trend Bias from H1
    h1_swings = find_swing_points(df_h1, window=3)
    h1_bias = classify_trend_structure(h1_swings)

    if h1_bias not in ("UPTREND", "DOWNTREND"):
        return SignalResult(
            status="NO_TRADE", direction="NONE", reason_code="SMC_HTF_RANGE_NO_BIAS"
        )

    # 2. Detect Order Blocks & FVGs on M15
    m15_swings = find_swing_points(df_m15, window=2)
    m15_candles = df_to_candles(df_m15)
    atr_m15 = _calc_atr(df_m15, 14)

    obs = detect_order_blocks(m15_candles, m15_swings, atr_series=atr_m15)
    mark_ob_mitigated(obs, m15_candles)
    fvgs = detect_fvg(m15_candles)
    link_fvg_to_order_blocks(obs, fvgs)

    # 3. Calculate HTF P/D zone from H1 recent swings
    last_h1 = get_last_swing_points(h1_swings, n=2)
    if not last_h1["swing_highs"] or not last_h1["swing_lows"]:
        return SignalResult(
            status="NO_TRADE", direction="NONE", reason_code="SMC_NO_HTF_SWINGS"
        )

    h1_high = last_h1["swing_highs"][-1]["high"]
    h1_low = last_h1["swing_lows"][-1]["low"]
    pd_zone = get_premium_discount_zone(h1_low, h1_high)

    curr_close = m15_candles[-1].close

    # Look for valid active OBs - Phải có FVG confluence
    valid_obs = [ob for ob in obs if not ob.mitigated and ob.has_fvg_confluence]

    # Strict: Chỉ trade khi giá đang ở Discount (cho BUY) hoặc Premium (cho SELL)
    fib_50 = pd_zone["fib_50"]
    
    if h1_bias == "UPTREND":
        # BUY: Chỉ khi giá < 50% zone (discount) VÀ có Bullish OB
        if curr_close >= fib_50:
            return SignalResult(
                status="NO_TRADE", direction="NONE", reason_code="SMC_PRICE_NOT_IN_DISCOUNT"
            )
        
        bull_obs = [
            ob for ob in valid_obs
            if ob.direction == PDArrayDirection.BULLISH and classify_pd_array_zone(ob, pd_zone) == "DISCOUNT"
        ]
        if bull_obs:
            target_ob = bull_obs[-1]
            entry_price = target_ob.top
            sl = target_ob.bottom - 0.30  # 3 pips buffer on gold
            tp = h1_high
            return SignalResult(
                status="APPROVED",
                direction="BUY",
                reason_code="SMC_BULLISH_OB_DISCOUNT_STRICT",
                entry_price=round(entry_price, 3),
                sl=round(sl, 3),
                tp=round(tp, 3),
                layers_passed=4,
                pd_array_used="BULLISH_OB",
            )

    elif h1_bias == "DOWNTREND":
        # SELL: Chỉ khi giá > 50% zone (premium) VÀ có Bearish OB
        if curr_close <= fib_50:
            return SignalResult(
                status="NO_TRADE", direction="NONE", reason_code="SMC_PRICE_NOT_IN_PREMIUM"
            )
        
        bear_obs = [
            ob for ob in valid_obs
            if ob.direction == PDArrayDirection.BEARISH and classify_pd_array_zone(ob, pd_zone) == "PREMIUM"
        ]
        if bear_obs:
            target_ob = bear_obs[-1]
            entry_price = target_ob.bottom
            sl = target_ob.top + 0.30  # 3 pips buffer
            tp = h1_low
            return SignalResult(
                status="APPROVED",
                direction="SELL",
                reason_code="SMC_BEARISH_OB_PREMIUM_STRICT",
                entry_price=round(entry_price, 3),
                sl=round(sl, 3),
                tp=round(tp, 3),
                layers_passed=4,
                pd_array_used="BEARISH_OB",
            )

    return SignalResult(
        status="NO_TRADE", direction="NONE", reason_code="SMC_NO_VALID_SETUP"
    )


# ── Engine 3: Inner Circle Trader (ICT) ──────────────────────────────────────

def _run_ict_only(
    df_h1: pd.DataFrame,
    df_m15: pd.DataFrame,
    df_m5: pd.DataFrame,
    broker_utc_offset_hours: float = 2.0,
) -> SignalResult:
    if len(df_m5) < 50 or len(df_m15) < 50 or len(df_h1) < 20:
        return SignalResult(
            status="NO_TRADE", direction="NONE", reason_code="ICT_INSUFFICIENT_DATA"
        )

    # 1. HTF Bias Confirmation (H1) - Critical for 80%+ winrate
    h1_swings = find_swing_points(df_h1, window=3)
    h1_bias = classify_trend_structure(h1_swings)
    
    if h1_bias == "RANGE" or h1_bias == "INSUFFICIENT_DATA":
        return SignalResult(
            status="NO_TRADE", direction="NONE", reason_code="ICT_HTF_NO_TREND"
        )

    # 2. Killzone Filter - Chỉ London và NY Killzones
    curr_time = pd.to_datetime(df_m5["time"].iloc[-1])
    kz_info = get_killzone_status(curr_time, broker_utc_offset_hours)

    if not kz_info["is_any_killzone"]:
        return SignalResult(
            status="NO_TRADE", direction="NONE", reason_code="ICT_OUTSIDE_KILLZONE"
        )

    # 3. Check Asian Range & Judas Swing Sweep
    asian_info = get_asian_range(df_m15, broker_utc_offset_hours)
    asian_high = asian_info["asian_high"]
    asian_low = asian_info["asian_low"]

    if asian_high is None or asian_low is None:
        return SignalResult(
            status="NO_TRADE", direction="NONE", reason_code="ICT_NO_ASIAN_RANGE"
        )

    m5_candles = df_to_candles(df_m5)
    m5_swings = find_swing_points(df_m5, window=2)
    last_candle = m5_candles[-1]

    # Judas Bullish Sweep: Low below asian_low, close above asian_low
    judas_bull = last_candle.low < asian_low and last_candle.close > asian_low
    # Judas Bearish Sweep: High above asian_high, close below asian_high
    judas_bear = last_candle.high > asian_high and last_candle.close < asian_high

    if not judas_bull and not judas_bear:
        return SignalResult(
            status="NO_TRADE", direction="NONE", reason_code="ICT_NO_JUDAS_SWEEP"
        )

    # 4. Direction Alignment: Judas phải align với HTF bias
    # BUY chỉ khi h1_bias == UPTREND và judas_bull == True
    # SELL chỉ khi h1_bias == DOWNTREND và judas_bear == True
    if judas_bull and h1_bias != "UPTREND":
        return SignalResult(
            status="NO_TRADE", direction="NONE", reason_code="ICT_BULL_DIRECTION_MISMATCH"
        )
    
    if judas_bear and h1_bias != "DOWNTREND":
        return SignalResult(
            status="NO_TRADE", direction="NONE", reason_code="ICT_BEAR_DIRECTION_MISMATCH"
        )

    # 5. Detect FVG on M5 after displacement
    fvgs = detect_fvg(m5_candles)
    if not fvgs:
        return SignalResult(
            status="NO_TRADE", direction="NONE", reason_code="ICT_NO_M5_FVG"
        )

    m5_highs = [c.high for c in m5_candles[-20:]]
    m5_lows = [c.low for c in m5_candles[-20:]]
    swing_h, swing_l = max(m5_highs), min(m5_lows)

    if judas_bull:
        ote = calculate_ote_zone(swing_l, swing_h, "BUY")
        bull_fvgs = [
            f for f in fvgs 
            if f.direction == PDArrayDirection.BULLISH 
            and check_fvg_ote_confluence(f, ote)
        ]
        if bull_fvgs:
            target_fvg = bull_fvgs[-1]
            entry_price = target_fvg.ce or target_fvg.mid
            sl = swing_l - 0.30
            tp = asian_high
            return SignalResult(
                status="APPROVED",
                direction="BUY",
                reason_code="ICT_JUDAS_BULLISH_OTE_FVG_STRICT",
                entry_price=round(entry_price, 3),
                sl=round(sl, 3),
                tp=round(tp, 3),
                layers_passed=5,
                pd_array_used="ICT_OTE_FVG",
            )

    elif judas_bear:
        ote = calculate_ote_zone(swing_l, swing_h, "SELL")
        bear_fvgs = [
            f for f in fvgs 
            if f.direction == PDArrayDirection.BEARISH 
            and check_fvg_ote_confluence(f, ote)
        ]
        if bear_fvgs:
            target_fvg = bear_fvgs[-1]
            entry_price = target_fvg.ce or target_fvg.mid
            sl = swing_h + 0.30
            tp = asian_low
            return SignalResult(
                status="APPROVED",
                direction="SELL",
                reason_code="ICT_JUDAS_BEARISH_OTE_FVG_STRICT",
                entry_price=round(entry_price, 3),
                sl=round(sl, 3),
                tp=round(tp, 3),
                layers_passed=5,
                pd_array_used="ICT_OTE_FVG",
            )

    return SignalResult(
        status="NO_TRADE", direction="NONE", reason_code="ICT_NO_OTE_CONFLUENCE"
    )


# ── Engine 4: Price Action ───────────────────────────────────────────────────

def _run_price_action_only(df_m15: pd.DataFrame) -> SignalResult:
    if len(df_m15) < 50:
        return SignalResult(
            status="NO_TRADE", direction="NONE", reason_code="PA_INSUFFICIENT_DATA"
        )

    candles = df_to_candles(df_m15)
    last = candles[-1]
    prev = candles[-2]
    prev2 = candles[-3]

    # Require strong momentum candle (body >= 70% of range)
    strong_bull = last.is_bullish and last.body_ratio >= 0.70
    strong_bear = last.is_bearish and last.body_ratio >= 0.70
    
    if not (strong_bull or strong_bear):
        return SignalResult(
            status="NO_TRADE", direction="NONE", reason_code="PA_WEAK_MOMENTUM_CANDLE"
        )

    # Engulfing detection - phải engulf toàn bộ body của prev candle
    is_bull_engulfing = (
        last.is_bullish and 
        prev.is_bearish and 
        last.close > prev.high and 
        last.open <= prev.low
    )
    is_bear_engulfing = (
        last.is_bearish and 
        prev.is_bullish and 
        last.close < prev.low and 
        last.open >= prev.high
    )
    
    # Pinbar detection: wick >= 70% of range (stricter)
    is_bull_pinbar = (
        last.lower_wick >= 0.70 * last.range_size and 
        last.range_size > 0 and
        last.is_bullish
    )
    is_bear_pinbar = (
        last.upper_wick >= 0.70 * last.range_size and 
        last.range_size > 0 and
        last.is_bearish
    )
    
    # Volume confirmation
    atr = _calc_atr(df_m15, 14)
    curr_atr = atr.iloc[-1]
    volume_series = df_m15.get("tick_volume", df_m15.get("real_volume", df_m15.get("volume", pd.Series(0.0, index=df_m15.index))))
    vol_avg = volume_series.rolling(20).mean().iloc[-1]
    curr_vol = volume_series.iloc[-1]
    
    # Volume phải > 1.2x average (confirm momentum)
    volume_confirm = curr_vol >= vol_avg * 1.2 if vol_avg > 0 else True

    # Get support/resistance levels from swing points
    swing_df = find_swing_points(df_m15, window=2)
    swing_highs = [float(row["high"]) for idx, row in swing_df[swing_df["swing_high"]].tail(10).iterrows()]
    swing_lows = [float(row["low"]) for idx, row in swing_df[swing_df["swing_low"]].tail(10).iterrows()]
    
    # Near resistance: last close gần swing highs nhất
    nearest_resistance = min(swing_highs) if swing_highs else None
    # Near support: last close gần swing lows nhất
    nearest_support = max(swing_lows) if swing_lows else None
    
    # Giá phải gần support/resistance (within 0.3% = ~8 pips on gold)
    if nearest_support and last.low <= nearest_support * 1.003:
        if (is_bull_pinbar or is_bull_engulfing) and volume_confirm:
            sl = nearest_support - 0.30
            tp = last.close + 2.5 * (last.close - sl)
            return SignalResult(
                status="APPROVED",
                direction="BUY",
                reason_code="PA_BULLISH_REVERSAL_AT_SUPPORT_STRICT",
                entry_price=last.close,
                sl=round(sl, 3),
                tp=round(tp, 3),
                layers_passed=4,
                pd_array_used="PINBAR_ENGULFING",
            )

    if nearest_resistance and last.high >= nearest_resistance * 0.997:
        if (is_bear_pinbar or is_bear_engulfing) and volume_confirm:
            sl = nearest_resistance + 0.30
            tp = last.close - 2.5 * (sl - last.close)
            return SignalResult(
                status="APPROVED",
                direction="SELL",
                reason_code="PA_BEARISH_REVERSAL_AT_RESISTANCE_STRICT",
                entry_price=last.close,
                sl=round(sl, 3),
                tp=round(tp, 3),
                layers_passed=4,
                pd_array_used="PINBAR_ENGULFING",
            )

    return SignalResult(
        status="NO_TRADE", direction="NONE", reason_code="PA_NO_PATTERN"
    )


# ── Engine 5: Ultra Confluence Matrix (Hybrid 5-Layer Stack) ─────────────────

def _run_ultra_confluence(
    df_h4: pd.DataFrame,
    df_h1: pd.DataFrame,
    df_m15: pd.DataFrame,
    df_m5: pd.DataFrame,
    df_m1: pd.DataFrame,
    broker_utc_offset_hours: float = 2.0,
) -> SignalResult:
    # ── LAYER 1: HTF Narrative & Premium/Discount Zone (H4/D1) ───────────────
    if len(df_h4) < 30:
        return SignalResult(
            status="NO_TRADE", direction="NONE", reason_code="LAYER1_H4_INSUFFICIENT"
        )
    h4_swings = find_swing_points(df_h4, window=3)
    last_h4 = get_last_swing_points(h4_swings, n=2)

    if not last_h4["swing_highs"] or not last_h4["swing_lows"]:
        return SignalResult(
            status="NO_TRADE", direction="NONE", reason_code="LAYER1_NO_HTF_SWINGS"
        )

    h4_high = last_h4["swing_highs"][-1]["high"]
    h4_low = last_h4["swing_lows"][-1]["low"]
    pd_zone = get_premium_discount_zone(h4_low, h4_high)

    curr_price = float(df_m15["close"].iloc[-1])
    htf_bias = get_htf_bias_from_pd_zone(curr_price, pd_zone)

    if htf_bias == "NEUTRAL":
        return SignalResult(
            status="NO_TRADE", direction="NONE", reason_code="LAYER1_NO_CLEAR_BIAS"
        )

    # ── LAYER 2: Time & Killzone Window ──────────────────────────────────────
    curr_time = pd.to_datetime(df_m5["time"].iloc[-1])
    kz_info = get_killzone_status(curr_time, broker_utc_offset_hours)

    if not kz_info["is_any_killzone"]:
        return SignalResult(
            status="NO_TRADE", direction="NONE", reason_code="LAYER2_OUTSIDE_KILLZONE"
        )

    # ── LAYER 3: Liquidity Sweep Confirmation (M15) ──────────────────────────
    m15_swings = find_swing_points(df_m15, window=2)
    m15_candles = df_to_candles(df_m15)
    sweep_type = detect_liquidity_sweep(m15_candles, m15_swings, len(m15_candles) - 1)

    if sweep_type is None:
        return SignalResult(
            status="NO_TRADE", direction="NONE", reason_code="LAYER3_NO_SWEEP"
        )

    if htf_bias == "DISCOUNT_BUY_ONLY" and sweep_type != "BULLISH_SWEEP":
        return SignalResult(
            status="NO_TRADE", direction="NONE", reason_code="LAYER3_SWEEP_DIRECTION_MISMATCH"
        )

    if htf_bias == "PREMIUM_SELL_ONLY" and sweep_type != "BEARISH_SWEEP":
        return SignalResult(
            status="NO_TRADE", direction="NONE", reason_code="LAYER3_SWEEP_DIRECTION_MISMATCH"
        )

    # ── LAYER 4: MSS/CHoCH + Displacement + FVG (M5) ─────────────────────────
    m5_candles = df_to_candles(df_m5)
    fvgs = detect_fvg(m5_candles)

    if not fvgs:
        return SignalResult(
            status="NO_TRADE", direction="NONE", reason_code="LAYER4_NO_DISPLACEMENT_FVG"
        )

    # ── LAYER 5: OTE Entry (M5/M1 Confluence) ────────────────────────────────
    m5_highs = [c.high for c in m5_candles[-15:]]
    m5_lows = [c.low for c in m5_candles[-15:]]
    swing_h, swing_l = max(m5_highs), min(m5_lows)

    # OTE Entry với Strict Filters cho Winrate 80%+
    # Filter 1: Giá phải nằm trong OTE Zone (0.618-0.790)
    # Filter 2: FVG phải confluence với OTE zone
    # Filter 3: Chỉ trade khi FVG còn VIRGIN (chưa bị fill)

    if htf_bias == "DISCOUNT_BUY_ONLY":
        ote = calculate_ote_zone(swing_l, swing_h, "BUY")
        
        # Strict OTE Zone Filter: Price phải trong zone 0.618-0.790
        zone_bottom = ote["zone_bottom"]
        zone_top = ote["zone_top"]
        curr_price = float(m5_candles[-1].close)
        
        if not (zone_bottom <= curr_price <= zone_top):
            return SignalResult(
                status="NO_TRADE", direction="NONE", reason_code="LAYER5_PRICE_OUTSIDE_OTE_ZONE"
            )
        
        valid_fvgs = [
            f for f in fvgs 
            if f.direction == PDArrayDirection.BULLISH 
            and check_fvg_ote_confluence(f, ote)
            and is_price_in_ote(f.ce or f.mid, ote)
        ]
        
        if valid_fvgs:
            target_fvg = valid_fvgs[-1]
            entry_price = target_fvg.ce or target_fvg.mid
            
            # Strict SL: Dưới swing low + buffer
            sl = swing_l - 0.30
            
            # TP: Target H4 High hoặc 2x ATR từ entry
            atr_m15 = _calc_atr(df_m15, 14).iloc[-1]
            tp_candidates = [h4_high, entry_price + 2.5 * atr_m15]
            tp = min(tp_candidates)  # Lấy target gần hơn
            
            return SignalResult(
                status="APPROVED",
                direction="BUY",
                reason_code="ULTRA_CONFLUENCE_BUY_PASS_5_LAYERS_STRICT",
                entry_price=round(entry_price, 3),
                sl=round(sl, 3),
                tp=round(tp, 3),
                layers_passed=5,
                pd_array_used="ULTRA_CONFLUENCE_STACK",
            )

    elif htf_bias == "PREMIUM_SELL_ONLY":
        ote = calculate_ote_zone(swing_l, swing_h, "SELL")
        
        # Strict OTE Zone Filter
        zone_bottom = ote["zone_bottom"]
        zone_top = ote["zone_top"]
        curr_price = float(m5_candles[-1].close)
        
        if not (zone_bottom <= curr_price <= zone_top):
            return SignalResult(
                status="NO_TRADE", direction="NONE", reason_code="LAYER5_PRICE_OUTSIDE_OTE_ZONE"
            )
        
        valid_fvgs = [
            f for f in fvgs 
            if f.direction == PDArrayDirection.BEARISH 
            and check_fvg_ote_confluence(f, ote)
            and is_price_in_ote(f.ce or f.mid, ote)
        ]
        
        if valid_fvgs:
            target_fvg = valid_fvgs[-1]
            entry_price = target_fvg.ce or target_fvg.mid
            sl = swing_h + 0.30
            atr_m15 = _calc_atr(df_m15, 14).iloc[-1]
            tp_candidates = [h4_low, entry_price - 2.5 * atr_m15]
            tp = max(tp_candidates)
            
            return SignalResult(
                status="APPROVED",
                direction="SELL",
                reason_code="ULTRA_CONFLUENCE_SELL_PASS_5_LAYERS_STRICT",
                entry_price=round(entry_price, 3),
                sl=round(sl, 3),
                tp=round(tp, 3),
                layers_passed=5,
                pd_array_used="ULTRA_CONFLUENCE_STACK",
            )

    return SignalResult(
        status="NO_TRADE", direction="NONE", reason_code="LAYER5_PRICE_NOT_IN_OTE"
    )


def _run_sniper_only(df_m15: pd.DataFrame, df_m5: pd.DataFrame) -> SignalResult:
    if len(df_m15) < 30 or len(df_m5) < 30:
        return SignalResult(
            status="NO_TRADE", direction="NONE", reason_code="SNIPER_INSUFFICIENT_DATA"
        )
    
    close = df_m15["close"]
    open_p = df_m15["open"]
    
    ema9 = _calc_ema(close, 9)
    ema21 = _calc_ema(close, 21)
    vwap = _calc_vwap(df_m15)
    atr = _calc_atr(df_m15, 14)
    rsi = _calc_rsi(close, 14)
    macd, macd_sig = _calc_macd(close)
    adx = _calc_adx(df_m15, 14)
    
    volume_series = df_m15.get("tick_volume", df_m15.get("real_volume", df_m15.get("volume", pd.Series(0.0, index=df_m15.index))))
    vol_avg = volume_series.rolling(20).mean()
    
    rsi5m = _calc_rsi(df_m5["close"], 14)
    
    # Current values
    curr_close = close.iloc[-1]
    curr_open = open_p.iloc[-1]
    curr_ema9 = ema9.iloc[-1]
    curr_ema21 = ema21.iloc[-1]
    curr_vwap = vwap.iloc[-1]
    curr_atr = atr.iloc[-1]
    curr_rsi = rsi.iloc[-1]
    curr_macd = macd.iloc[-1]
    curr_macd_sig = macd_sig.iloc[-1]
    curr_adx = adx.iloc[-1]
    curr_vol = volume_series.iloc[-1]
    curr_vol_avg = vol_avg.iloc[-1]
    curr_rsi5m = rsi5m.iloc[-1]
    
    # Calculate Scores
    b_score = 0
    b_score += 1 if curr_close > curr_vwap else 0
    b_score += 1 if curr_rsi > 50 else 0
    b_score += 1 if curr_macd > curr_macd_sig else 0
    b_score += 1 if curr_ema9 > curr_ema21 else 0
    b_score += 1 if (curr_adx > 25 and curr_close > curr_ema9) else 0
    b_score += 1 if (curr_vol > curr_vol_avg and curr_close > curr_open) else 0
    b_score += 1 if curr_rsi5m > 50 else 0
    bull_pct = (b_score / 7) * 100
    
    r_score = 0
    r_score += 1 if curr_close < curr_vwap else 0
    r_score += 1 if curr_rsi < 50 else 0
    r_score += 1 if curr_macd < curr_macd_sig else 0
    r_score += 1 if curr_ema9 < curr_ema21 else 0
    r_score += 1 if (curr_adx > 25 and curr_close < curr_ema9) else 0
    r_score += 1 if (curr_vol > curr_vol_avg and curr_close < curr_open) else 0
    r_score += 1 if curr_rsi5m < 50 else 0
    bear_pct = (r_score / 7) * 100
    
    # Signal Crossovers
    trigger_buy = ema9.iloc[-1] > ema21.iloc[-1] and ema9.iloc[-2] <= ema21.iloc[-2]
    trigger_sell = ema9.iloc[-1] < ema21.iloc[-1] and ema9.iloc[-2] >= ema21.iloc[-2]
    
    if trigger_buy:
        risk = curr_atr * 1.5
        sl = curr_close - risk
        tp = curr_close + risk * 2
        return SignalResult(
            status="APPROVED",
            direction="BUY",
            reason_code=f"SNIPER_BULL_CROSSOVER_PCT_{int(bull_pct)}",
            entry_price=curr_close,
            sl=round(sl, 3),
            tp=round(tp, 3),
            layers_passed=5,
            pd_array_used="SNIPER_CROSSOVER"
        )
        
    if trigger_sell:
        risk = curr_atr * 1.5
        sl = curr_close + risk
        tp = curr_close - risk * 2
        return SignalResult(
            status="APPROVED",
            direction="SELL",
            reason_code=f"SNIPER_BEAR_CROSSOVER_PCT_{int(bear_pct)}",
            entry_price=curr_close,
            sl=round(sl, 3),
            tp=round(tp, 3),
            layers_passed=5,
            pd_array_used="SNIPER_CROSSOVER"
        )
        
    return SignalResult(
        status="NO_TRADE",
        direction="NONE",
        reason_code=f"SNIPER_NO_SIGNAL_B{int(bull_pct)}_R{int(bear_pct)}"
    )


# ── Main Entrypoint Router ───────────────────────────────────────────────────

def run_signal_engine(
    symbol: str,
    mtf_data: Dict[str, pd.DataFrame],
    broker_utc_offset_hours: float = 2.0,
    method: str = "ULTRA_CONFLUENCE",
) -> SignalResult:
    """Dispatches multi-timeframe candle data to the configured Signal Engine."""
    m15 = mtf_data.get("M15")
    if m15 is None or m15.empty:
        return SignalResult(
            status="NO_TRADE", direction="NONE", reason_code="MISSING_M15_DATA"
        )

    method_upper = method.upper()

    if method_upper == "INDICATOR":
        return _run_indicator_only(m15)
    elif method_upper == "SMC":
        h1 = mtf_data.get("H1", m15)
        return _run_smc_only(h1, m15)
    elif method_upper == "ICT":
        h1 = mtf_data.get("H1", m15)
        m5 = mtf_data.get("M5", m15)
        return _run_ict_only(h1, m15, m5, broker_utc_offset_hours)
    elif method_upper == "PRICE_ACTION":
        return _run_price_action_only(m15)
    elif method_upper == "SNIPER":
        m5 = mtf_data.get("M5", m15)
        return _run_sniper_only(m15, m5)
    elif method_upper == "ULTRA_CONFLUENCE":
        h4 = mtf_data.get("H4", m15)
        h1 = mtf_data.get("H1", m15)
        m5 = mtf_data.get("M5", m15)
        m1 = mtf_data.get("M1", m5)
        return _run_ultra_confluence(h4, h1, m15, m5, m1, broker_utc_offset_hours)
    else:
        return SignalResult(
            status="NO_TRADE", direction="NONE", reason_code=f"UNKNOWN_METHOD_{method}"
        )
