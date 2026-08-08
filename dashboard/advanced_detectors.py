"""Advanced detectors: Price Action (25), SMC (26), ICT (21) concepts for ATE.

Complements dashboard/detectors.py. Every function returns plain dicts / lists
of dicts (no ORM), ready for chart_markup serialization. Coordinates are candle
indices (0 = oldest) and ISO timestamps for time anchors.

Contract shared with dashboard/chart_markup.py and ATE_XAUUSD.mq5:
    {"type": str, "direction": "BULLISH"|"BEARISH"|"NEUTRAL",
     "top": float, "bottom": float, "price": float,
     "time_start": str, "time_end": str, "index": int,
     "label": str, "status": str, "strength": float}
"""

from __future__ import annotations

from datetime import time as dtime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from detectors import (
    PDArray,
    PDArrayDirection,
    PDArrayType,
    Candle,
    detect_breaker_and_mitigation_blocks,
    detect_fvg,
    detect_order_blocks,
    df_to_candles,
    find_swing_points,
)

# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────


def _atr_series(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    tr = pd.concat(
        [high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period).mean()


def _obj(
    type_name: str,
    direction: str,
    candles: List[Candle],
    index: int,
    top: float = 0.0,
    bottom: float = 0.0,
    price: float = 0.0,
    label: str = "",
    status: str = "",
    **extra: Any,
) -> Dict[str, Any]:
    c = candles[index]
    obj: Dict[str, Any] = {
        "type": type_name,
        "direction": direction,
        "top": round(float(top), 2),
        "bottom": round(float(bottom), 2),
        "price": round(float(price), 2) if price else 0.0,
        "time_start": str(c.time),
        "time_end": "",
        "index": int(index),
        "label": label,
        "status": status,
    }
    obj.update(extra)
    return obj


# ────────────────────────────────────────────────────────────────────────────
# 1. PRICE ACTION (25 concepts)
# ────────────────────────────────────────────────────────────────────────────

# 1-3. Trend / Swing / HH-HL-LH-LL  → detectors.py (classify_trend_structure,
#      find_swing_points, detect_market_structure). Re-used by chart_markup.


def detect_support_resistance(
    candles: List[Candle],
    swing_df: pd.DataFrame,
    lookback: int = 80,
    tolerance_pct: float = 0.0005,
    min_touches: int = 2,
) -> List[Dict[str, Any]]:
    """(4) Support/Resistance zones via cluster density of swing points."""
    zones: List[Dict[str, Any]] = []
    window = swing_df.tail(lookback)
    points = []  # (index, price, is_support_swing)
    for idx, row in window.iterrows():
        if row["swing_high"]:
            points.append((int(idx), float(row["high"]), False))
        if row["swing_low"]:
            points.append((int(idx), float(row["low"]), True))
    if len(points) < 2:
        return zones

    used = set()
    for i, (i1, p1, s1) in enumerate(points):
        if i in used:
            continue
        cluster = [p1]
        cluster_idx = [i1]
        is_support = s1
        for j, (i2, p2, s2) in enumerate(points):
            if j == i or j in used:
                continue
            if abs(p2 - p1) / max(p1, 1e-9) <= tolerance_pct:
                cluster.append(p2)
                cluster_idx.append(i2)
                is_support = is_support and s2
                used.add(j)
        if len(cluster_idx) >= min_touches:
            level = float(np.mean(cluster))
            tol = tolerance_pct * max(level, 1e-9)
            kind = "SUPPORT" if is_support else "RESISTANCE"
            zones.append(
                {
                    "type": "SR",
                    "direction": "NEUTRAL",
                    "top": level + tol,
                    "bottom": level - tol,
                    "price": level,
                    "label": kind,
                    "index": min(cluster_idx),
                    "time_start": str(candles[min(cluster_idx)].time),
                    "touches": len(cluster_idx),
                }
            )
    zones.sort(key=lambda z: z["touches"], reverse=True)
    return zones[:6]


def detect_channels(
    candles: List[Candle],
    swing_df: pd.DataFrame,
    n: int = 10,
    max_slope_diff: float = 0.25,
) -> List[Dict[str, Any]]:
    """(6) Channel: parallel upper (swing highs) + lower (swing lows) trendlines."""
    highs = [(int(idx), float(row["high"])) for idx, row in swing_df[swing_df["swing_high"]].tail(n).iterrows()]
    lows = [(int(idx), float(row["low"])) for idx, row in swing_df[swing_df["swing_low"]].tail(n).iterrows()]
    if len(highs) < 2 or len(lows) < 2:
        return []

    def _line(pts: List[Tuple[int, float]]) -> Optional[Tuple[float, float, int, int, float, float]]:
        if len(pts) < 2:
            return None
        (i1, p1), (i2, p2) = pts[0], pts[-1]
        if i2 == i1:
            return None
        slope = (p2 - p1) / (i2 - i1)
        # value of the line extrapolated to the newest candle in the window
        end_price = p1 + slope * (i2 - i1)
        return slope, p1, i1, i2, end_price, end_price

    up = _line(lows)
    down = _line(highs)
    if up is None or down is None:
        return []
    slope_diff = abs(up[0] - down[0])
    if slope_diff > max_slope_diff:
        return []
    i_start = min(up[2], down[2])
    i_end = max(up[3], down[3])
    # parallel channel: upper bound from highs line, lower bound from lows line,
    # both evaluated at the newest window index so the zone tracks price now.
    top_here = down[4] + down[0] * (i_end - down[3])
    bot_here = up[4] + up[0] * (i_end - up[3])
    return [
        {
            "type": "CHANNEL",
            "direction": "BULLISH" if up[0] > 0 else "BEARISH",
            "top": round(top_here, 2),
            "bottom": round(bot_here, 2),
            "price": 0.0,
            "label": "CHANNEL",
            "index": i_start,
            "time_start": str(candles[i_start].time),
            "time_end": str(candles[i_end].time),
            "slope": round(up[0], 6),
        }
    ]


def detect_range_state(df: pd.DataFrame, lookback: int = 60) -> Dict[str, Any]:
    """(7) Range: ADX < 20 or bounded swing oscillation over N candles."""
    window = df.tail(lookback)
    if len(window) < 20:
        return {"type": "RANGE", "direction": "NEUTRAL", "top": 0.0, "bottom": 0.0, "status": "NO_DATA"}

    up = window["high"].diff().clip(lower=0)
    down = -window["low"].diff().clip(upper=0)
    n = 14
    atr = _atr_series(window).iloc[-1]
    if atr is None or atr == 0 or np.isnan(atr):
        return {"type": "RANGE", "direction": "NEUTRAL", "top": 0.0, "bottom": 0.0, "status": "NO_ATR"}
    adx = 100.0 * abs(up.rolling(n).mean() - down.rolling(n).mean()) / (up.rolling(n).mean() + down.rolling(n).mean()).replace(0, np.nan)
    adx_now = float(adx.iloc[-1]) if not np.isnan(adx.iloc[-1]) else 50.0

    highs = window["high"].tail(6).max()
    lows = window["low"].tail(6).min()
    bounded = (highs - lows) / atr <= 4.0

    if adx_now < 20.0 or bounded:
        last_pos = len(window) - 1
        return {
            "type": "RANGE",
            "direction": "NEUTRAL",
            "top": float(highs),
            "bottom": float(lows),
            "price": 0.0,
            "label": "RANGE",
            "status": "ACTIVE",
            "adx": round(adx_now, 1),
            "index": int(window.index[last_pos]),
            "time_start": str(window.index[0] if "time" not in window.columns else window["time"].iloc[0]),
        }
    return {"type": "RANGE", "direction": "NEUTRAL", "top": 0.0, "bottom": 0.0, "status": "TRENDING"}


def detect_breakouts(
    candles: List[Candle],
    swing_df: pd.DataFrame,
    sr_zones: List[Dict[str, Any]],
    volume_ma_period: int = 20,
    atr_mult: float = 0.75,
) -> List[Dict[str, Any]]:
    """(8) Breakout: close beyond S/R zone with volume above volume MA."""
    results: List[Dict[str, Any]] = []
    if len(candles) < volume_ma_period + 2:
        return results
    vol_ma = float(np.mean([c.volume for c in candles[-volume_ma_period:-1]])) + 1e-9

    for zone in sr_zones:
        idx = int(zone.get("index", 0))
        for i in range(idx, len(candles) - 1):
            c = candles[i]
            kind = zone.get("label", "SUPPORT")
            if kind == "SUPPORT" and c.close < zone["bottom"] and c.volume > vol_ma:
                results.append(
                    _obj(
                        "BREAKOUT", "BEARISH", candles, i,
                        price=c.close, label="BREAKOUT_SUPPORT",
                        status="ACTIVE", zone_level=round(zone["bottom"], 2),
                    )
                )
                break
            if kind == "RESISTANCE" and c.close > zone["top"] and c.volume > vol_ma:
                results.append(
                    _obj(
                        "BREAKOUT", "BULLISH", candles, i,
                        price=c.close, label="BREAKOUT_RESISTANCE",
                        status="ACTIVE", zone_level=round(zone["top"], 2),
                    )
                )
                break
    return results


def detect_pullback_retest_fake(
    candles: List[Candle],
    swing_df: pd.DataFrame,
    breakouts: List[Dict[str, Any]],
    atr: float = 0.0,
    fake_window: int = 5,
) -> List[Dict[str, Any]]:
    """(9)(10)(11) Pullback, Retest, Fake Breakout combined pass."""
    results: List[Dict[str, Any]] = []
    if not breakouts:
        return results

    for b in breakouts:
        idx = int(b["index"])
        level = float(b.get("zone_level", b.get("price", 0.0)))
        if level <= 0 or idx + 1 >= len(candles):
            continue
        direction = b["direction"]
        # (9) Pullback: retrace toward the zone without breaking nearest swing
        for j in range(idx + 1, min(idx + 8, len(candles))):
            c = candles[j]
            if direction == "BULLISH" and c.low <= level and c.close > level:
                results.append(_obj("PULLBACK", "BULLISH", candles, j, price=c.close, label="PULLBACK"))
                break
            if direction == "BEARISH" and c.high >= level and c.close < level:
                results.append(_obj("PULLBACK", "BEARISH", candles, j, price=c.close, label="PULLBACK"))
                break
        # (10) Retest: candle touches exactly the breakout level (±atr*0.25)
        for j in range(idx + 1, min(idx + 8, len(candles))):
            c = candles[j]
            tol = max(atr * 0.25, 1e-9)
            if direction == "BULLISH" and abs(c.low - level) <= tol:
                results.append(_obj("RETEST", "BULLISH", candles, j, price=c.low, label="RETEST"))
                break
            if direction == "BEARISH" and abs(c.high - level) <= tol:
                results.append(_obj("RETEST", "BEARISH", candles, j, price=c.high, label="RETEST"))
                break
        # (11) Fake breakout: close re-enters the range within N bars
        if atr <= 0:
            continue
        for j in range(idx + 1, min(idx + fake_window, len(candles))):
            c = candles[j]
            if direction == "BULLISH" and c.close < level:
                results.append(_obj("FAKE_BREAKOUT", "BEARISH", candles, j, price=c.close, label="FAKE_BREAKOUT", status="INVALIDATED"))
                break
            if direction == "BEARISH" and c.close > level:
                results.append(_obj("FAKE_BREAKOUT", "BULLISH", candles, j, price=c.close, label="FAKE_BREAKOUT", status="INVALIDATED"))
                break
    return results


def detect_candle_patterns(candles: List[Candle]) -> List[Dict[str, Any]]:
    """(12-25) 14 single/multi-candle Price Action patterns.

    Emits PATTERN objects with labels:
    PIN_BAR, ENGULFING_BULLISH/BEARISH, INSIDE_BAR, OUTSIDE_BAR, DOJI,
    MORNING_STAR, EVENING_STAR, HAMMER, SHOOTING_STAR, TWEEZER_TOP,
    TWEEZER_BOTTOM, MARUBOZU, THREE_WHITE_SOLDIERS, THREE_BLACK_CROWS.
    """
    out: List[Dict[str, Any]] = []
    n = len(candles)
    for i in range(1, n):
        c, prev = candles[i], candles[i - 1]
        prev2 = candles[i - 2] if i >= 2 else None
        rng = max(c.range_size, 1e-9)
        body = c.body_size
        up_w = c.upper_wick
        lo_w = c.lower_wick

        # (12) Pin Bar: opposite wick >= 2x body, same-direction wick < body
        if up_w >= 2.0 * body and lo_w < body and body > 0:
            out.append(_obj("PATTERN", "BEARISH", candles, i, price=c.high, label="PIN_BAR"))
        if lo_w >= 2.0 * body and up_w < body and body > 0:
            out.append(_obj("PATTERN", "BULLISH", candles, i, price=c.low, label="PIN_BAR"))

        # (13) Engulfing
        if prev.is_bearish and c.is_bullish and c.close > prev.open and c.open < prev.close and c.body_size > prev.body_size:
            out.append(_obj("PATTERN", "BULLISH", candles, i, price=c.close, label="ENGULFING_BULLISH"))
        if prev.is_bullish and c.is_bearish and c.close < prev.open and c.open > prev.close and c.body_size > prev.body_size:
            out.append(_obj("PATTERN", "BEARISH", candles, i, price=c.close, label="ENGULFING_BEARISH"))

        # (14) Inside Bar
        if c.high < prev.high and c.low > prev.low:
            out.append(_obj("PATTERN", "NEUTRAL", candles, i, price=c.close, label="INSIDE_BAR"))
        # (15) Outside Bar
        if c.high > prev.high and c.low < prev.low:
            out.append(_obj("PATTERN", "NEUTRAL", candles, i, price=c.close, label="OUTSIDE_BAR"))

        # (16) Doji
        if body / rng < 0.10:
            out.append(_obj("PATTERN", "NEUTRAL", candles, i, price=c.close, label="DOJI"))

        # (17) Morning Star / (18) Evening Star
        if (
            i >= 2
            and prev2.is_bearish and prev2.body_size > 0.5 * prev2.range_size
            and prev.body_size / max(prev.range_size, 1e-9) < 0.3
            and c.is_bullish and c.close > prev2.open + 0.5 * prev2.body_size
        ):
            out.append(_obj("PATTERN", "BULLISH", candles, i, price=c.close, label="MORNING_STAR"))
        if (
            i >= 2
            and prev2.is_bullish and prev2.body_size > 0.5 * prev2.range_size
            and prev.body_size / max(prev.range_size, 1e-9) < 0.3
            and c.is_bearish and c.close < prev2.open - 0.5 * prev2.body_size
        ):
            out.append(_obj("PATTERN", "BEARISH", candles, i, price=c.close, label="EVENING_STAR"))

        # (19) Hammer / (20) Shooting Star (context handled by chart_markup via trend)
        if lo_w >= 2.0 * body and up_w <= 0.3 * body and body > 0 and c.is_bullish:
            out.append(_obj("PATTERN", "BULLISH", candles, i, price=c.low, label="HAMMER"))
        if up_w >= 2.0 * body and lo_w <= 0.3 * body and body > 0 and c.is_bearish:
            out.append(_obj("PATTERN", "BEARISH", candles, i, price=c.high, label="SHOOTING_STAR"))

        # (21) Tweezer Top / (22) Tweezer Bottom
        tol = 0.0005 * max(c.high, 1e-9)
        if abs(c.high - prev.high) <= tol and c.is_bearish:
            out.append(_obj("PATTERN", "BEARISH", candles, i, price=c.high, label="TWEEZER_TOP"))
        if abs(c.low - prev.low) <= tol and c.is_bullish:
            out.append(_obj("PATTERN", "BULLISH", candles, i, price=c.low, label="TWEEZER_BOTTOM"))

        # (23) Marubozu
        if up_w / rng < 0.05 and lo_w / rng < 0.05 and body / rng > 0.9:
            out.append(_obj("PATTERN", "BULLISH" if c.is_bullish else "BEARISH", candles, i, price=c.close, label="MARUBOZU"))

        # (24) Three White Soldiers / (25) Three Black Crows
        if (
            i >= 3
            and candles[i - 3].is_bearish
            and prev2.is_bullish and prev.is_bullish and c.is_bullish
            and c.close > prev.close > prev2.close
            and prev.open > prev2.close and c.open > prev.close
        ):
            out.append(_obj("PATTERN", "BULLISH", candles, i, price=c.close, label="THREE_WHITE_SOLDIERS"))
        if (
            i >= 3
            and candles[i - 3].is_bullish
            and prev2.is_bearish and prev.is_bearish and c.is_bearish
            and c.close < prev.close < prev2.close
            and prev.open < prev2.close and c.open < prev.close
        ):
            out.append(_obj("PATTERN", "BEARISH", candles, i, price=c.close, label="THREE_BLACK_CROWS"))

    return out


# ────────────────────────────────────────────────────────────────────────────
# 2. SMC (26 concepts)
# ────────────────────────────────────────────────────────────────────────────

# 1-4. Market Structure / BOS / CHoCH / MSS → detectors.py (detect_market_structure,
#      detect_bos_choch). MSS = CHoCH confirmed by an extra structure break.


def detect_mss(
    candles: List[Candle],
    swing_df: pd.DataFrame,
    current_index: int,
) -> Dict[str, Any]:
    """(4) MSS: CHoCH + confirmation — price breaks the CHoCH swing then closes
    beyond it on a follow-through candle (used on lower TFs).
    """
    if current_index < 2 or current_index >= len(candles):
        return {}
    current = candles[current_index]

    swing_highs = [(int(idx), float(row["high"])) for idx, row in swing_df[swing_df["swing_high"]].iterrows()]
    swing_lows = [(int(idx), float(row["low"])) for idx, row in swing_df[swing_df["swing_low"]].iterrows()]
    highs_before = [h for i, h in swing_highs if i < current_index]
    lows_before = [l for i, l in swing_lows if i < current_index]
    if len(highs_before) < 2 or len(lows_before) < 2:
        return {}

    prior_high, recent_high = highs_before[-2], highs_before[-1]
    prior_low, recent_low = lows_before[-2], lows_before[-1]

    # CHoCH bearish: HH + HL (uptrend) breaks recent low; MSS = 2 closes beyond
    if prior_high > recent_high and prior_low < recent_low and current.close < recent_low:
        if candles[current_index - 1].close < recent_low:
            return {"kind": "MSS", "direction": "BEARISH", "break_price": recent_low, "index": current_index}
    # CHoCH bullish: LH + LL (downtrend) breaks recent high; MSS = 2 closes beyond
    if prior_high > recent_high and prior_low > recent_low and current.close > recent_high:
        if candles[current_index - 1].close > recent_high:
            return {"kind": "MSS", "direction": "BULLISH", "break_price": recent_high, "index": current_index}
    return {}


def detect_liquidity_zones(
    candles: List[Candle],
    swing_df: pd.DataFrame,
    lookback: int = 60,
) -> List[Dict[str, Any]]:
    """(5) Liquidity: clusters of stops above swing highs / below swing lows.

    Clusters of >=2 swing points at nearly the same price are flagged as
    Equal Highs (EQH, above price / buy-side) or Equal Lows (EQL, below price /
    sell-side) liquidity. Each pool is also classified Internal (inside the
    current dealing range) or External (outside it).
    """
    zones: List[Dict[str, Any]] = []
    window = swing_df.tail(lookback)
    highs = [(int(idx), float(row["high"])) for idx, row in window[window["swing_high"]].iterrows()]
    lows = [(int(idx), float(row["low"])) for idx, row in window[window["swing_low"]].iterrows()]

    def _extreme(pts: List[Tuple[int, float]], side: str) -> Optional[Tuple[int, float]]:
        if not pts:
            return None
        return max(pts, key=lambda t: t[1]) if side == "high" else min(pts, key=lambda t: t[1])

    ext_high = _extreme(highs, "high")
    ext_low = _extreme(lows, "low")

    def _classify(mid: float) -> str:
        if ext_high is None or ext_low is None:
            return "EXTERNAL"
        if ext_low[1] <= mid <= ext_high[1]:
            return "INTERNAL"
        return "EXTERNAL"

    def _cluster(points: List[Tuple[int, float]], side: str) -> List[Dict[str, Any]]:
        if len(points) < 2:
            return []
        points = sorted(points, key=lambda p: p[1])
        groups: List[Tuple[int, float, float, float]] = []  # (count, mid, span, std)
        cur = [points[0]]
        for p in points[1:]:
            if abs(p[1] - cur[-1][1]) / max(cur[-1][1], 1e-9) <= 0.0006:
                cur.append(p)
            else:
                groups.append((len(cur), float(np.mean([x[1] for x in cur])),
                               max([x[1] for x in cur]) - min([x[1] for x in cur]),
                               float(np.std([x[1] for x in cur]))))
                cur = [p]
        groups.append((len(cur), float(np.mean([x[1] for x in cur])),
                       max([x[1] for x in cur]) - min([x[1] for x in cur]),
                       float(np.std([x[1] for x in cur]))))
        out = []
        for count, mid, span, std in groups:
            if count >= 2:
                idx = min(points, key=lambda t: abs(t[1] - mid))[0]
                equal = count >= 3 or (count >= 2 and std / max(mid, 1e-9) <= 0.00007)
                base_label = "EQH" if side == "BSL" else "EQL"
                label = f"{base_label}_{_classify(mid)}" if equal else ("BSL" if side == "BSL" else "SSL")
                direction = "BEARISH" if side == "BSL" else "BULLISH"
                out.append({
                    "type": "LIQUIDITY_POOL", "direction": direction,
                    "top": mid + span / 2, "bottom": mid - span / 2, "price": mid,
                    "label": label, "liquidity_kind": "EQUAL" if equal else "CLUSTER",
                    "liquidity_side": _classify(mid), "index": idx,
                    "time_start": str(candles[idx].time), "touches": count,
                })
        return out

    zones += _cluster(highs, "BSL")
    zones += _cluster(lows, "SSL")
    zones = sorted(zones, key=lambda z: z["touches"], reverse=True)
    return zones[:8]


def detect_dealing_range(
    candles: List[Candle],
    swing_df: pd.DataFrame,
    lookback: int = 40,
) -> Dict[str, Any]:
    """(21) Dealing Range: band between the nearest external swing high and low."""
    window = swing_df.tail(lookback)
    highs = [(int(idx), float(row["high"])) for idx, row in window[window["swing_high"]].iterrows()]
    lows = [(int(idx), float(row["low"])) for idx, row in window[window["swing_low"]].iterrows()]
    if not highs or not lows:
        return {}
    ext_high = max(highs, key=lambda t: t[1])
    ext_low = min(lows, key=lambda t: t[1])
    eq = (ext_high[1] + ext_low[1]) / 2.0
    idx = min(ext_high[0], ext_low[0])
    return {
        "type": "DEALING_RANGE",
        "direction": "NEUTRAL",
        "price": round(eq, 2),
        "label": "DEALING_RANGE",
        "index": int(idx),
        "time_start": str(candles[idx].time),
    }


def detect_dealing_curve(
    candles: List[Candle],
    swing_df: pd.DataFrame,
    lookback: int = 40,
    max_points: int = 6,
) -> List[Dict[str, Any]]:
    """(ICT) Dealing Curve — the median/eatl curve that connects the equilibrium
    point (midpoint) of consecutive swing highs/lows inside the dealing range.

    Produces a lightweight line object (type DEALING_CURVE, TRENDLINE-like shape)
    that spans the whole visible window: `top` = equilibrium at time_start,
    `bottom` = equilibrium at time_end, and `points` carries every intermediate
    (timestamp, price) pair so the web/EA can render a polyline when wanted.
    """
    window = swing_df.tail(lookback)
    highs = [(int(idx), float(row["high"])) for idx, row in window[window["swing_high"]].iterrows()]
    lows = [(int(idx), float(row["low"])) for idx, row in window[window["swing_low"]].iterrows()]
    if not highs or not lows:
        return []

    ext_high = max(highs, key=lambda t: t[1])
    ext_low = min(lows, key=lambda t: t[1])
    eq = (ext_high[1] + ext_low[1]) / 2.0

    # Equilibrium through the range — build a price series with a mid-weighted EMA
    # of (high + low)/2 per swing point, then downsample to <= max_points.
    pts = [(h[0], (h[1] + lows[0][1]) / 2.0) for h in highs]
    samples: List[Dict[str, Any]] = []
    step = max(len(pts) // max_points, 1)
    for i in range(0, len(pts), step):
        idx, p = pts[i]
        samples.append({"t": str(candles[idx].time), "p": round(float(p), 2)})
    if samples and samples[-1]["p"] != eq:
        samples.append({"t": str(candles[-1].time), "p": round(eq, 2)})
    if not samples:
        return []

    obj = {
        "type": "DEALING_CURVE",
        "direction": "NEUTRAL",
        "top": samples[-1]["p"],
        "bottom": samples[0]["p"],
        "price": round(eq, 2),
        "label": "DEALING_CURVE",
        "status": "ACTIVE",
        "index": int(ext_high[0] if ext_high[0] < ext_low[0] else ext_low[0]),
        "time_start": samples[0]["t"],
        "time_end": samples[-1]["t"],
        "points": samples,
    }
    return [obj]


def detect_supply_demand(
    candles: List[Candle],
    atr_mult: float = 1.2,
    min_strength: float = 1.2,
) -> List[Dict[str, Any]]:
    """(24) Supply/Demand: base candle + strong move away (no BOS needed)."""
    zones: List[Dict[str, Any]] = []
    n = len(candles)
    atr = float(np.mean([c.range_size for c in candles[-14:]])) + 1e-9

    for i in range(1, n - 1):
        base, move = candles[i - 1], candles[i]
        if move.body_size <= min_strength * atr:
            continue
        if move.is_bullish and base.is_bearish:
            zones.append(_obj("SUPPLY_DEMAND", "BULLISH", candles, i - 1,
                              top=base.high, bottom=base.low, label="DEMAND", status="ACTIVE"))
        if move.is_bearish and base.is_bullish:
            zones.append(_obj("SUPPLY_DEMAND", "BEARISH", candles, i - 1,
                              top=base.high, bottom=base.low, label="SUPPLY", status="ACTIVE"))
    return zones[-6:]


def detect_volume_imbalance(
    candles: List[Candle],
    volume_mult: float = 1.5,
) -> List[Dict[str, Any]]:
    """(25) Volume Imbalance: price gap with no volume between two candles."""
    out: List[Dict[str, Any]] = []
    for i in range(1, len(candles)):
        prev, cur = candles[i - 1], candles[i]
        gap = 0.0
        if cur.low > prev.high:  # bullish gap
            gap = cur.low - prev.high
        elif cur.high < prev.low:  # bearish gap
            gap = prev.low - cur.high
        if gap > 0 and cur.volume > volume_mult * max(prev.volume, 1e-9):
            out.append(_obj(
                "VOLUME_IMBALANCE",
                "BULLISH" if cur.low > prev.high else "BEARISH",
                candles, i,
                top=cur.low if cur.low > prev.high else prev.low,
                bottom=prev.high if cur.low > prev.high else cur.high,
                label="VOLUME_IMBALANCE", status="ACTIVE", gap=round(gap, 2),
            ))
    return out[-8:]


def detect_liquidity_voids(
    candles: List[Candle],
    void_atr_mult: float = 2.0,
    min_consecutive: int = 3,
) -> List[Dict[str, Any]]:
    """(26) Liquidity Void: fast one-directional consecutive move, thin bodies."""
    out: List[Dict[str, Any]] = []
    n = len(candles)
    atr = float(np.mean([c.range_size for c in candles[-20:]])) + 1e-9

    run: List[int] = []
    run_dir: Optional[str] = None
    for i in range(1, n):
        c = candles[i]
        body_dir = "UP" if c.is_bullish else ("DOWN" if c.is_bearish else None)
        if body_dir is not None and body_dir == run_dir and c.body_size >= void_atr_mult * atr:
            run.append(i)
            continue
        if run_dir is not None and len(run) >= min_consecutive:
            run_body = sum(candles[j].body_size for j in run)
            if run_body >= void_atr_mult * atr * 2:
                out.append(_obj(
                    "VOID", "BULLISH" if run_dir == "UP" else "BEARISH", candles, run[0],
                    top=max(candles[j].high for j in run),
                    bottom=min(candles[j].low for j in run),
                    label="VOID", status="ACTIVE",
                ))
        run_dir = body_dir
        run = [i] if body_dir is not None and c.body_size >= void_atr_mult * atr else []
    return out[-6:]


def detect_inducement(
    candles: List[Candle],
    swing_df: pd.DataFrame,
    lookback: int = 40,
) -> List[Dict[str, Any]]:
    """(22) Inducement: small swing that traps retail before the real move."""
    out: List[Dict[str, Any]] = []
    swings = swing_df.tail(lookback)
    events = []
    for idx, row in swings.iterrows():
        if row["swing_high"]:
            events.append((int(idx), "HIGH", float(row["high"])))
        if row["swing_low"]:
            events.append((int(idx), "LOW", float(row["low"])))
    events.sort()
    for i in range(2, len(events) - 1):
        e_prev2, e_prev, e_cur, e_next = events[i - 2], events[i - 1], events[i], events[i + 1]
        # small range swing (inducement) between two bigger swings
        if e_cur[1] != e_prev[1]:
            continue
        spread = abs(e_cur[2] - e_prev[2])
        if spread <= 0:
            continue
        # amplitude of neighbors larger than the inducement itself
        big_amp = max(abs(e_prev2[2] - e_prev[2]), abs(e_cur[2] - e_next[2]))
        if big_amp > 1.5 * spread:
            out.append(_obj(
                "INDUCEMENT", "BULLISH" if e_cur[1] == "LOW" else "BEARISH",
                candles, e_cur[0], price=e_cur[2], label="INDUCEMENT", status="ACTIVE",
            ))
    return out[-8:]


def detect_bpr(
    fvg_list: List[PDArray],
    overlap_pct: float = 0.5,
) -> List[Dict[str, Any]]:
    """ICT (2) BPR: two opposite FVGs overlapping (Balanced Price Range)."""
    out: List[Dict[str, Any]] = []
    bull = [f for f in fvg_list if f.direction == PDArrayDirection.BULLISH]
    bear = [f for f in fvg_list if f.direction == PDArrayDirection.BEARISH]
    for b in bull:
        for s in bear:
            overlap = min(b.top, s.top) - max(b.bottom, s.bottom)
            if overlap <= 0:
                continue
            span = min(b.top - b.bottom, s.top - s.bottom) or 1e-9
            if overlap / span >= overlap_pct:
                out.append({
                    "type": "BPR",
                    "direction": "NEUTRAL",
                    "top": round(min(b.top, s.top), 2),
                    "bottom": round(max(b.bottom, s.bottom), 2),
                    "price": round((min(b.top, s.top) + max(b.bottom, s.bottom)) / 2.0, 2),
                    "label": "BPR",
                    "index": min(b.formed_at_index, s.formed_at_index),
                    "time_start": str(min(b.formed_at_time, s.formed_at_time)),
                    "status": "ACTIVE",
                })
    return out[-8:]


def detect_unicorn(
    order_blocks: List[PDArray],
    breaker_blocks: List[PDArray],
    overlap_pct: float = 0.6,
) -> List[Dict[str, Any]]:
    """ICT (18) Unicorn: OB overlapping a Breaker Block at the same zone."""
    out: List[Dict[str, Any]] = []
    for ob in order_blocks:
        for bb in breaker_blocks:
            overlap = min(ob.top, bb.top) - max(ob.bottom, bb.bottom)
            if overlap <= 0:
                continue
            span = min(ob.top - ob.bottom, bb.top - bb.bottom) or 1e-9
            if overlap / span >= overlap_pct:
                out.append({
                    "type": "UNICORN",
                    "direction": bb.direction.value,
                    "top": round(min(ob.top, bb.top), 2),
                    "bottom": round(max(ob.bottom, bb.bottom), 2),
                    "price": round(bb.mid, 2),
                    "label": "UNICORN",
                    "index": min(ob.formed_at_index, bb.formed_at_index),
                    "time_start": str(min(ob.formed_at_time, bb.formed_at_time)),
                    "status": "ACTIVE",
                })
    return out[:6]


# ────────────────────────────────────────────────────────────────────────────
# 3. ICT (21 concepts)
# ────────────────────────────────────────────────────────────────────────────

# 1,3,5,6,7,10 → SMC sections (OB/FVG/iFVG, PD Array pool, Premium/Discount,
#                Dealing Range, Liquidity Pool, Liquidity Void).


def get_previous_day_high_low(
    df_d1: pd.DataFrame,
    broker_utc_offset_hours: float = 2.0,
) -> Dict[str, Any]:
    """(20) PDH/PDL from the previous trading day's D1 candle."""
    if df_d1 is None or df_d1.empty:
        return {}
    df = df_d1.copy()
    df["vn_date"] = df["time"] - pd.Timedelta(hours=broker_utc_offset_hours) + pd.Timedelta(hours=7)
    today = df["vn_date"].iloc[-1].date()
    prev = df[df["vn_date"].dt.date < today]
    if prev.empty:
        return {}
    row = prev.iloc[-1]
    return {
        "type": "PDH_PDL",
        "direction": "NEUTRAL",
        "top": float(row["high"]),
        "bottom": float(row["low"]),
        "price": float(row["close"]),
        "label": "PDH_PDL",
        "index": 0,
        "time_start": str(row["time"]),
        "pdh": float(row["high"]),
        "pdl": float(row["low"]),
    }


def get_session_high_low(
    df: pd.DataFrame,
    session: str = "LONDON",
    broker_utc_offset_hours: float = 2.0,
) -> Dict[str, Any]:
    """(19) Session High/Low for LONDON / NY / ASIA sessions today."""
    df = df.copy()
    df["utc"] = df["time"] - pd.Timedelta(hours=broker_utc_offset_hours)
    df["utc_date"] = df["utc"].dt.date
    today = df["utc_date"].iloc[-1]
    mask = df["utc_date"] == today
    df_today = df[mask]
    if df_today.empty:
        return {}

    hour = df_today["utc"].dt.hour + df_today["utc"].dt.minute / 60.0
    if session == "LONDON":
        seg = (hour >= 7) & (hour <= 10)
    elif session == "NY":
        seg = (hour >= 12) & (hour <= 15)
    elif session == "ASIA":
        seg = (hour >= 0) & (hour <= 5)
    else:
        seg = pd.Series(True, index=df_today.index)
    seg_df = df_today[seg]
    if seg_df.empty:
        return {}
    idx = int(seg_df.index[-1])
    return {
        "type": "SESSION_HL",
        "direction": "NEUTRAL",
        "top": float(seg_df["high"].max()),
        "bottom": float(seg_df["low"].min()),
        "price": float(seg_df["close"].iloc[-1]),
        "label": f"{session}_SESSION",
        "index": idx,
        "time_start": str(df.loc[idx, "time"]) if idx in df.index else str(seg_df["time"].iloc[-1]),
        "session": session,
    }


def detect_turtle_soup(
    candles: List[Candle],
    df_d1: pd.DataFrame,
    broker_utc_offset_hours: float = 2.0,
    lookback: int = 3,
) -> List[Dict[str, Any]]:
    """(11) Turtle Soup: false breakout of PDH/PDL + fast reversal."""
    pdl_hld = get_previous_day_high_low(df_d1, broker_utc_offset_hours)
    if not pdl_hld:
        return []
    pdh, pdl = pdl_hld["pdh"], pdl_hld["pdl"]
    out: List[Dict[str, Any]] = []
    for i in range(max(1, len(candles) - lookback), len(candles)):
        c = candles[i]
        # break above PDH then close back below = bearish soup
        if c.high > pdh and c.close < pdh:
            out.append(_obj("TURTLE_SOUP", "BEARISH", candles, i, price=c.close,
                            label="TURTLE_SOUP_PDH", status="ACTIVE", level=round(pdh, 2)))
        if c.low < pdl and c.close > pdl:
            out.append(_obj("TURTLE_SOUP", "BULLISH", candles, i, price=c.close,
                            label="TURTLE_SOUP_PDL", status="ACTIVE", level=round(pdl, 2)))
    return out


def detect_judas_swing(
    candles: List[Candle],
    broker_utc_offset_hours: float = 2.0,
    lookback: int = 48,
) -> List[Dict[str, Any]]:
    """(12) Judas Swing: fake move inside London Kill Zone before the real reversal."""
    out: List[Dict[str, Any]] = []
    for i in range(max(1, len(candles) - lookback), len(candles)):
        c = candles[i]
        utc = c.time - pd.Timedelta(hours=broker_utc_offset_hours)
        t = utc.time()
        in_london = dtime(7, 0) <= t <= dtime(10, 0)
        if not in_london:
            continue
        # large single-candle move (fake) followed by immediate counter close
        atr = float(np.mean([candles[j].range_size for j in range(max(0, i - 14), i)])) + 1e-9
        if c.body_size >= 1.8 * atr and i + 1 < len(candles):
            nxt = candles[i + 1]
            if (c.is_bullish and nxt.is_bearish and nxt.close < c.open) or (
                c.is_bearish and nxt.is_bullish and nxt.close > c.open
            ):
                out.append(_obj("JUDAS_SWING", "BEARISH" if c.is_bullish else "BULLISH",
                                candles, i, price=c.close, label="JUDAS_SWING", status="ACTIVE"))
    return out


def detect_smt_divergence(
    df_primary: pd.DataFrame,
    df_correlation: pd.DataFrame,
    swing_window: int = 2,
    lookback: int = 30,
) -> List[Dict[str, Any]]:
    """(13) SMT Divergence: primary makes a new swing, correlation does not.

    df_primary = XAUUSD, df_correlation = DXY-style index.
    """
    out: List[Dict[str, Any]] = []
    if df_correlation is None or df_correlation.empty:
        return out
    try:
        pri = df_primary.tail(lookback).reset_index(drop=True)
        cor = df_correlation.tail(lookback).reset_index(drop=True)
        pri_sw = find_swing_points(pri, swing_window)
        cor_sw = find_swing_points(cor, swing_window)
        pri_candles = df_to_candles(pri)
    except Exception:
        return out

    pri_highs = [(int(idx), float(row["high"])) for idx, row in pri_sw[pri_sw["swing_high"]].iterrows()]
    cor_highs = [(int(idx), float(row["high"])) for idx, row in cor_sw[cor_sw["swing_high"]].iterrows()]
    pri_lows = [(int(idx), float(row["low"])) for idx, row in pri_sw[pri_sw["swing_low"]].iterrows()]
    cor_lows = [(int(idx), float(row["low"])) for idx, row in cor_sw[cor_sw["swing_low"]].iterrows()]

    if len(pri_highs) >= 2 and len(cor_highs) >= 2:
        if pri_highs[-1][1] > pri_highs[-2][1] and cor_highs[-1][1] < cor_highs[-2][1]:
            idx = pri_highs[-1][0]
            out.append(_obj("SMT_DIVERGENCE", "BEARISH", pri_candles, idx,
                            price=float(pri_highs[-1][1]), label="SMT_BEARISH", status="ACTIVE"))
    if len(pri_lows) >= 2 and len(cor_lows) >= 2:
        if pri_lows[-1][1] < pri_lows[-2][1] and cor_lows[-1][1] > cor_lows[-2][1]:
            idx = pri_lows[-1][0]
            out.append(_obj("SMT_DIVERGENCE", "BULLISH", pri_candles, idx,
                            price=float(pri_lows[-1][1]), label="SMT_BULLISH", status="ACTIVE"))
    return out


def detect_amd_po3(
    df: pd.DataFrame,
    broker_utc_offset_hours: float = 2.0,
) -> List[Dict[str, Any]]:
    """(14)(15) AMD/PO3: Accumulation (range) -> Manipulation (sweep) -> Distribution."""
    df = df.copy()
    df["utc"] = df["time"] - pd.Timedelta(hours=broker_utc_offset_hours)
    df["utc_date"] = df["utc"].dt.date
    today = df["utc_date"].iloc[-1]
    seg = df[df["utc_date"] == today]
    if len(seg) < 10:
        return {}

    out: List[Dict[str, Any]] = []
    n = len(seg)

    def _phase_bounds(a: int, b: int) -> Tuple[float, float]:
        part = seg.iloc[a:b]
        return float(part["high"].max()), float(part["low"].min())

    # Accumulation: first third range is tight
    h_acc, l_acc = _phase_bounds(0, max(1, n // 3))
    h_man, l_man = _phase_bounds(max(1, n // 3), max(2, 2 * n // 3))
    h_dis, l_dis = _phase_bounds(max(2, 2 * n // 3), n)

    acc_range = h_acc - l_acc
    dis_range = h_dis - l_dis
    if acc_range > 0 and dis_range > 1.5 * acc_range:
        # sweep during manipulation phase beyond accumulation high/low
        swept = (h_man > h_acc and l_dis >= l_acc) or (l_man < l_acc and h_dis <= h_acc)
        if swept:
            last_idx = int(seg.index[-1])
            out.append({
                "type": "AMD",
                "direction": "BULLISH" if h_dis >= h_acc else "BEARISH",
                "top": h_dis,
                "bottom": l_dis,
                "price": float(seg["close"].iloc[-1]),
                "label": "AMD_PO3",
                "index": last_idx,
                "time_start": str(seg["time"].iloc[0]),
                "time_end": str(seg["time"].iloc[-1]),
                "status": "ACTIVE",
            })
    return out


def detect_silver_bullet(
    candles: List[Candle],
    broker_utc_offset_hours: float = 2.0,
    lookback: int = 24,
) -> List[Dict[str, Any]]:
    """(17) Silver Bullet: 10-11am NY window entry setup (14-15 UTC)."""
    out: List[Dict[str, Any]] = []
    for i in range(max(1, len(candles) - lookback), len(candles)):
        c = candles[i]
        utc = c.time - pd.Timedelta(hours=broker_utc_offset_hours)
        t = utc.time()
        if dtime(14, 0) <= t <= dtime(15, 0):
            atr = float(np.mean([candles[j].range_size for j in range(max(0, i - 14), i)])) + 1e-9
            if c.body_size >= 1.5 * atr:
                out.append(_obj("SILVER_BULLET", "BULLISH" if c.is_bullish else "BEARISH",
                                candles, i, price=c.close, label="SILVER_BULLET", status="ACTIVE"))
    return out


def get_weekly_monthly_high_low(
    df_d1: pd.DataFrame,
    period: str = "WEEKLY",
) -> Dict[str, Any]:
    """(21) Weekly/Monthly High/Low from D1 data."""
    if df_d1 is None or df_d1.empty:
        return {}
    df = df_d1.copy()
    df["time"] = pd.to_datetime(df["time"])
    ref = df["time"].iloc[-1]
    if period == "WEEKLY":
        start = ref - pd.Timedelta(days=ref.weekday())
        prev = df[df["time"] < start]
        label = "WEEKLY_HL"
    else:
        prev = df[df["time"].dt.to_period("M") < ref.to_period("M")]
        label = "MONTHLY_HL"
    if prev.empty:
        return {}
    row = prev.iloc[-1]
    return {
        "type": "WEEKLY_MONTHLY_HL",
        "direction": "NEUTRAL",
        "top": float(row["high"]),
        "bottom": float(row["low"]),
        "price": float(row["close"]),
        "label": label,
        "index": 0,
        "time_start": str(row["time"]),
        "period": period,
    }


# ────────────────────────────────────────────────────────────────────────────
# Aggregator — one call for the full concept inventory
# ────────────────────────────────────────────────────────────────────────────


def build_advanced_markup(
    mtf_data: Dict[str, pd.DataFrame],
    broker_utc_offset_hours: float = 2.0,
    include_pa: bool = True,
    include_smc: bool = True,
    include_ict: bool = True,
) -> Dict[str, List[Dict[str, Any]]]:
    """Run every advanced detector and return {"objects": [...]} additions.

    Only appends objects NOT already produced by dashboard/chart_markup.py
    (SWING, OB, FVG, BREAKER, MITIGATION, REJECTION, LIQUIDITY, BOS, CHoCH,
    TRENDLINE, PD, OTE, ASIAN, KILLZONE live in the base builder).
    """
    objects: List[Dict[str, Any]] = []
    m15 = mtf_data.get("M15")
    m5 = mtf_data.get("M5")
    h1 = mtf_data.get("H1")
    d1 = mtf_data.get("D1")

    if m15 is None or m15.empty:
        return {"objects": objects, "counts": {}}

    m15 = m15.copy()
    candles = df_to_candles(m15)
    swing_df = find_swing_points(m15, window=2)
    atr = _atr_series(m15).iloc[-1] if len(m15) >= 15 else 0.0
    atr = 0.0 if atr is None or np.isnan(atr) else float(atr)

    counts: Dict[str, int] = {}

    def _add(items: List[Dict[str, Any]], key: str) -> None:
        clean = [it for it in items if isinstance(it, dict) and it and it.get("type")]
        capped = clean[-20:] if len(clean) > 20 else clean
        objects.extend(capped)
        counts[key] = len(capped)

    def _daily_level(obj: Dict[str, Any]) -> Dict[str, Any]:
        """Daily/session levels are horizontal bands — span the whole visible window
        so they render as full-width rectangles instead of a single-candle notch."""
        if not obj:
            return obj
        obj["index"] = 0
        obj["time_start"] = str(candles[0].time)
        obj["time_end"] = str(candles[-1].time)
        return obj

    if include_pa:
        sr_zones = detect_support_resistance(candles, swing_df)
        _add(sr_zones, "SR")
        _add(detect_channels(candles, swing_df), "CHANNEL")
        range_state = detect_range_state(m15)
        if range_state.get("status") == "ACTIVE":
            _add([range_state], "RANGE")
        breakouts = detect_breakouts(candles, swing_df, sr_zones)
        _add(breakouts, "BREAKOUT")
        _add(detect_pullback_retest_fake(candles, swing_df, breakouts, atr=atr), "PULLBACK")
        _add(detect_candle_patterns(candles), "PATTERN")

    if include_smc:
        mss = detect_mss(candles, swing_df, len(candles) - 1)
        if mss:
            _add([_obj("MSS", mss["direction"], candles, int(mss["index"]),
                       price=mss["break_price"], label=f"MSS_{mss['direction']}", status="ACTIVE")], "MSS")
        _add(detect_liquidity_zones(candles, swing_df), "LIQUIDITY_POOL")
        dr = detect_dealing_range(candles, swing_df)
        if dr:
            _add([dr], "DEALING_RANGE")
        _add(detect_dealing_curve(candles, swing_df), "DEALING_CURVE")
        _add(detect_supply_demand(candles, atr_mult=1.2), "SUPPLY_DEMAND")
        _add(detect_volume_imbalance(candles), "VOLUME_IMBALANCE")
        _add(detect_liquidity_voids(candles), "VOID")
        _add(detect_inducement(candles, swing_df), "INDUCEMENT")

        fvgs = detect_fvg(candles)
        obs = detect_order_blocks(candles, swing_df, atr_series=_atr_series(m15))
        breakers = detect_breaker_and_mitigation_blocks(obs, candles)
        _add(detect_bpr(fvgs), "BPR")
        _add(detect_unicorn(obs, breakers), "UNICORN")

    if include_ict:
        smt_corr = mtf_data.get("DXY")
        if smt_corr is not None and not smt_corr.empty:
            _add(detect_smt_divergence(m15, smt_corr), "SMT_DIVERGENCE")
        if d1 is not None and not d1.empty:
            _add([_daily_level(get_previous_day_high_low(d1, broker_utc_offset_hours))], "PDH_PDL")
            _add([_daily_level(get_weekly_monthly_high_low(d1, "WEEKLY"))], "WEEKLY_HL")
            _add([_daily_level(get_weekly_monthly_high_low(d1, "MONTHLY"))], "MONTHLY_HL")
            _add(detect_turtle_soup(candles, d1, broker_utc_offset_hours), "TURTLE_SOUP")
        _add(detect_judas_swing(candles, broker_utc_offset_hours), "JUDAS_SWING")
        _add(detect_silver_bullet(candles, broker_utc_offset_hours), "SILVER_BULLET")
        _add(detect_amd_po3(m15, broker_utc_offset_hours), "AMD")
        for session in ("LONDON", "NY", "ASIA"):
            _add([_daily_level(get_session_high_low(m15, session, broker_utc_offset_hours))], f"SESSION_{session}")

    return {"objects": objects, "counts": counts}
