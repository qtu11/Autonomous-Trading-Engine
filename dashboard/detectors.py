"""Market Structure and PD Array Detectors for Autonomous Trading Engine (ATE).

Implements geometry detectors for 9 ICT PD Array types, Swing Points,
BOS/CHoCH, Liquidity Sweeps, Killzones, OTE Fibonacci, and Premium/Discount Zones.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time as dtime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


@dataclass
class Candle:
    index: int
    time: pd.Timestamp
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)

    @property
    def range_size(self) -> float:
        return self.high - self.low

    @property
    def body_ratio(self) -> float:
        if self.range_size == 0:
            return 0.0
        return self.body_size / self.range_size

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low


def df_to_candles(df: pd.DataFrame) -> List[Candle]:
    candles: List[Candle] = []
    for i, row in df.iterrows():
        candles.append(
            Candle(
                index=i,
                time=pd.to_datetime(row["time"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row.get("tick_volume", row.get("real_volume", 0.0))),
            )
        )
    return candles


class PDArrayType(Enum):
    ORDER_BLOCK = "OB"
    FVG = "FVG"
    BREAKER_BLOCK = "BREAKER"
    MITIGATION_BLOCK = "MITIGATION"
    REJECTION_BLOCK = "REJECTION"
    LIQUIDITY_VOID = "VOID"
    INVERSION_FVG = "iFVG"
    PROPULSION_BLOCK = "PROPULSION"
    LIQUIDITY = "LIQUIDITY"


class PDArrayDirection(Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


@dataclass
class PDArray:
    type: PDArrayType
    direction: PDArrayDirection
    top: float
    bottom: float
    formed_at_index: int
    formed_at_time: pd.Timestamp
    mitigated: bool = False
    has_fvg_confluence: bool = False
    ce: Optional[float] = None
    strength_score: float = 1.0

    @property
    def mid(self) -> float:
        return (self.top + self.bottom) / 2.0

    def contains_price(self, price: float) -> bool:
        return self.bottom <= price <= self.top


# ── Swing Points & Market Trend Structure ────────────────────────────────────

def find_swing_points(df: pd.DataFrame, window: int = 2) -> pd.DataFrame:
    df = df.copy()
    df["swing_high"] = False
    df["swing_low"] = False

    highs = df["high"].values
    lows = df["low"].values
    n = len(df)

    for i in range(window, n - window):
        left_h = highs[i - window:i]
        right_h = highs[i + 1:i + window + 1]
        if highs[i] > left_h.max() and highs[i] > right_h.max():
            df.at[i, "swing_high"] = True

        left_l = lows[i - window:i]
        right_l = lows[i + 1:i + window + 1]
        if lows[i] < left_l.min() and lows[i] < right_l.min():
            df.at[i, "swing_low"] = True

    return df


def get_last_swing_points(df: pd.DataFrame, n: int = 5) -> Dict[str, List[Dict[str, Any]]]:
    swing_highs = df[df["swing_high"]].tail(n)[["time", "high"]].to_dict("records")
    swing_lows = df[df["swing_low"]].tail(n)[["time", "low"]].to_dict("records")
    return {"swing_highs": swing_highs, "swing_lows": swing_lows}


def classify_trend_structure(df: pd.DataFrame) -> str:
    swings = get_last_swing_points(df, n=3)
    highs = [s["high"] for s in swings["swing_highs"]]
    lows = [s["low"] for s in swings["swing_lows"]]

    if len(highs) < 2 or len(lows) < 2:
        return "INSUFFICIENT_DATA"

    higher_highs = all(highs[i] < highs[i + 1] for i in range(len(highs) - 1))
    higher_lows = all(lows[i] < lows[i + 1] for i in range(len(lows) - 1))
    lower_highs = all(highs[i] > highs[i + 1] for i in range(len(highs) - 1))
    lower_lows = all(lows[i] > lows[i + 1] for i in range(len(lows) - 1))

    if higher_highs and higher_lows:
        return "UPTREND"
    if lower_highs and lower_lows:
        return "DOWNTREND"
    return "RANGE"


# ── Order Blocks & Rejection Blocks ──────────────────────────────────────────

def _find_nearest_swing_before(swing_idx_set: set, current_index: int, candles: List[Candle], field_name: str) -> Optional[float]:
    candidates = [idx for idx in swing_idx_set if idx < current_index]
    if not candidates:
        return None
    nearest_idx = max(candidates)
    return getattr(candles[nearest_idx], field_name)


def detect_order_blocks(
    candles: List[Candle],
    swing_df: pd.DataFrame,
    displacement_atr_multiplier: float = 1.5,
    atr_series: Optional[pd.Series] = None,
) -> List[PDArray]:
    order_blocks: List[PDArray] = []
    n = len(candles)

    swing_highs_idx = set(swing_df[swing_df["swing_high"]].index) if "swing_high" in swing_df.columns else set()
    swing_lows_idx = set(swing_df[swing_df["swing_low"]].index) if "swing_low" in swing_df.columns else set()

    for i in range(1, n - 1):
        current = candles[i]
        prev = candles[i - 1]

        atr_now = atr_series.iloc[i] if atr_series is not None and i < len(atr_series) else None

        # Bullish OB: prev is bearish, current is bullish displacement breaking swing high
        if prev.is_bearish and current.is_bullish:
            recent_swing_high = _find_nearest_swing_before(swing_highs_idx, i, candles, "high")
            if recent_swing_high is not None and current.close > recent_swing_high:
                strong_displacement = (
                    current.body_ratio >= 0.55 and
                    (atr_now is None or current.body_size >= displacement_atr_multiplier * atr_now)
                )
                if strong_displacement:
                    order_blocks.append(
                        PDArray(
                            type=PDArrayType.ORDER_BLOCK,
                            direction=PDArrayDirection.BULLISH,
                            top=prev.high,
                            bottom=prev.low,
                            formed_at_index=i - 1,
                            formed_at_time=prev.time,
                        )
                    )

        # Bearish OB: prev is bullish, current is bearish displacement breaking swing low
        if prev.is_bullish and current.is_bearish:
            recent_swing_low = _find_nearest_swing_before(swing_lows_idx, i, candles, "low")
            if recent_swing_low is not None and current.close < recent_swing_low:
                strong_displacement = (
                    current.body_ratio >= 0.55 and
                    (atr_now is None or current.body_size >= displacement_atr_multiplier * atr_now)
                )
                if strong_displacement:
                    order_blocks.append(
                        PDArray(
                            type=PDArrayType.ORDER_BLOCK,
                            direction=PDArrayDirection.BEARISH,
                            top=prev.high,
                            bottom=prev.low,
                            formed_at_index=i - 1,
                            formed_at_time=prev.time,
                        )
                    )

    return order_blocks


def detect_rejection_blocks(candles: List[Candle], swing_df: pd.DataFrame, cluster_size: int = 3) -> List[PDArray]:
    rejection_blocks: List[PDArray] = []
    n = len(candles)

    for i in range(cluster_size, n - 1):
        if swing_df["swing_high"].iloc[i]:
            cluster = candles[i - cluster_size + 1 : i + 1]
            body_extreme = max(max(c.open, c.close) for c in cluster)
            wick_extreme = max(c.high for c in cluster)
            if wick_extreme > body_extreme:
                rejection_blocks.append(
                    PDArray(
                        type=PDArrayType.REJECTION_BLOCK,
                        direction=PDArrayDirection.BEARISH,
                        top=wick_extreme,
                        bottom=body_extreme,
                        formed_at_index=i,
                        formed_at_time=candles[i].time,
                    )
                )

        if swing_df["swing_low"].iloc[i]:
            cluster = candles[i - cluster_size + 1 : i + 1]
            body_extreme = min(min(c.open, c.close) for c in cluster)
            wick_extreme = min(c.low for c in cluster)
            if wick_extreme < body_extreme:
                rejection_blocks.append(
                    PDArray(
                        type=PDArrayType.REJECTION_BLOCK,
                        direction=PDArrayDirection.BULLISH,
                        top=body_extreme,
                        bottom=wick_extreme,
                        formed_at_index=i,
                        formed_at_time=candles[i].time,
                    )
                )

    return rejection_blocks


def mark_ob_mitigated(order_blocks: List[PDArray], candles: List[Candle]) -> None:
    for ob in order_blocks:
        if ob.mitigated:
            continue
        for c in candles[ob.formed_at_index + 1 :]:
            if ob.direction == PDArrayDirection.BULLISH and c.close < ob.bottom:
                ob.mitigated = True
                break
            if ob.direction == PDArrayDirection.BEARISH and c.close > ob.top:
                ob.mitigated = True
                break


def detect_breaker_and_mitigation_blocks(
    order_blocks: List[PDArray], candles: List[Candle]
) -> List[PDArray]:
    results: List[PDArray] = []

    for ob in order_blocks:
        if not ob.mitigated:
            continue

        failure_index = None
        failed_by_close = False

        for idx in range(ob.formed_at_index + 1, len(candles)):
            c = candles[idx]
            if ob.direction == PDArrayDirection.BULLISH:
                wick_breach = c.low < ob.bottom
                close_breach = c.close < ob.bottom
            else:
                wick_breach = c.high > ob.top
                close_breach = c.close > ob.top

            if close_breach:
                failure_index = idx
                failed_by_close = True
                break
            if wick_breach and failure_index is None:
                failure_index = idx
                failed_by_close = False

        if failure_index is None:
            continue

        new_direction = (
            PDArrayDirection.BEARISH if ob.direction == PDArrayDirection.BULLISH
            else PDArrayDirection.BULLISH
        )
        new_type = PDArrayType.BREAKER_BLOCK if failed_by_close else PDArrayType.MITIGATION_BLOCK

        results.append(
            PDArray(
                type=new_type,
                direction=new_direction,
                top=ob.top,
                bottom=ob.bottom,
                formed_at_index=failure_index,
                formed_at_time=candles[failure_index].time,
            )
        )

    return results


# ── FVG & Inversion FVG ───────────────────────────────────────────────────────

def detect_fvg(candles: List[Candle]) -> List[PDArray]:
    fvg_list: List[PDArray] = []

    for i in range(2, len(candles)):
        c0, c1, c2 = candles[i - 2], candles[i - 1], candles[i]

        if c2.low > c0.high:
            top, bottom = c2.low, c0.high
            fvg_list.append(
                PDArray(
                    type=PDArrayType.FVG,
                    direction=PDArrayDirection.BULLISH,
                    top=top,
                    bottom=bottom,
                    formed_at_index=i,
                    formed_at_time=c2.time,
                    ce=(top + bottom) / 2.0,
                )
            )

        if c2.high < c0.low:
            top, bottom = c0.low, c2.high
            fvg_list.append(
                PDArray(
                    type=PDArrayType.FVG,
                    direction=PDArrayDirection.BEARISH,
                    top=top,
                    bottom=bottom,
                    formed_at_index=i,
                    formed_at_time=c2.time,
                    ce=(top + bottom) / 2.0,
                )
            )

    return fvg_list


def link_fvg_to_order_blocks(
    order_blocks: List[PDArray], fvg_list: List[PDArray], max_gap_bars: int = 3
) -> None:
    for ob in order_blocks:
        for fvg in fvg_list:
            same_direction = fvg.direction == ob.direction
            close_in_time = 0 <= (fvg.formed_at_index - ob.formed_at_index) <= max_gap_bars
            if same_direction and close_in_time:
                ob.has_fvg_confluence = True
                break


def get_fvg_fill_state(fvg: PDArray, candles: List[Candle]) -> str:
    touched, ce_touched, fully_filled = False, False, False

    for c in candles[fvg.formed_at_index + 1 :]:
        if fvg.direction == PDArrayDirection.BULLISH:
            if c.low <= fvg.top:
                touched = True
            if fvg.ce is not None and c.low <= fvg.ce:
                ce_touched = True
            if c.low <= fvg.bottom:
                fully_filled = True
        else:
            if c.high >= fvg.bottom:
                touched = True
            if fvg.ce is not None and c.high >= fvg.ce:
                ce_touched = True
            if c.high >= fvg.top:
                fully_filled = True

    if fully_filled:
        return "FULLY_FILLED"
    if ce_touched:
        return "CE_FILLED"
    if touched:
        return "PARTIAL"
    return "VIRGIN"


# ── Liquidity Sweeps & EQH/EQL ───────────────────────────────────────────────

def detect_liquidity_sweep(
    candles: List[Candle],
    swing_df: pd.DataFrame,
    current_index: int,
) -> Optional[str]:
    if current_index >= len(candles):
        return None
    current = candles[current_index]

    swing_highs_idx = [idx for idx in swing_df[swing_df["swing_high"]].index if idx < current_index]
    swing_lows_idx = [idx for idx in swing_df[swing_df["swing_low"]].index if idx < current_index]

    if swing_highs_idx:
        bsl_target = candles[max(swing_highs_idx)].high
        if current.high > bsl_target and current.close < bsl_target:
            return "BEARISH_SWEEP"

    if swing_lows_idx:
        ssl_target = candles[max(swing_lows_idx)].low
        if current.low < ssl_target and current.close > ssl_target:
            return "BULLISH_SWEEP"

    return None


def detect_equal_highs_lows(
    swing_df: pd.DataFrame, tolerance_pct: float = 0.0005
) -> Dict[str, List[Tuple[int, int, float]]]:
    highs = swing_df[swing_df["swing_high"]][["high"]].reset_index()
    lows = swing_df[swing_df["swing_low"]][["low"]].reset_index()

    eqh_pairs, eql_pairs = [], []

    for i in range(len(highs) - 1):
        for j in range(i + 1, len(highs)):
            h1, h2 = highs.iloc[i]["high"], highs.iloc[j]["high"]
            if abs(h1 - h2) / h1 <= tolerance_pct:
                eqh_pairs.append((int(highs.iloc[i]["index"]), int(highs.iloc[j]["index"]), float((h1 + h2) / 2.0)))

    for i in range(len(lows) - 1):
        for j in range(i + 1, len(lows)):
            l1, l2 = lows.iloc[i]["low"], lows.iloc[j]["low"]
            if abs(l1 - l2) / l1 <= tolerance_pct:
                eql_pairs.append((int(lows.iloc[i]["index"]), int(lows.iloc[j]["index"]), float((l1 + l2) / 2.0)))

    return {"eqh": eqh_pairs, "eql": eql_pairs}


# ── Killzone Filter & Asian Range ───────────────────────────────────────────

def get_killzone_status(candle_time: pd.Timestamp, broker_utc_offset_hours: float = 2.0) -> Dict[str, Any]:
    utc_time = candle_time - pd.Timedelta(hours=broker_utc_offset_hours)
    vn_time = utc_time + pd.Timedelta(hours=7)
    t = vn_time.time()

    asian_range = dtime(6, 0) <= t <= dtime(12, 0)
    london_kz = dtime(14, 0) <= t <= dtime(17, 0)
    ny_kz = dtime(19, 30) <= t <= dtime(22, 30)

    return {
        "vn_time": vn_time,
        "is_asian_range": asian_range,
        "is_london_kz": london_kz,
        "is_ny_kz": ny_kz,
        "is_any_killzone": london_kz or ny_kz,
    }


def get_asian_range(df_m15: pd.DataFrame, broker_utc_offset_hours: float = 2.0) -> Dict[str, Optional[float]]:
    df = df_m15.copy()
    df["vn_time"] = df["time"] - pd.Timedelta(hours=broker_utc_offset_hours) + pd.Timedelta(hours=7)
    df["vn_date"] = df["vn_time"].dt.date
    df["vn_hour_float"] = df["vn_time"].dt.hour + df["vn_time"].dt.minute / 60.0

    if df.empty:
        return {"asian_high": None, "asian_low": None}

    today = df["vn_date"].iloc[-1]
    mask = (df["vn_date"] == today) & (df["vn_hour_float"] >= 6.0) & (df["vn_hour_float"] <= 12.0)
    session_df = df[mask]

    if session_df.empty:
        return {"asian_high": None, "asian_low": None}

    return {
        "asian_high": float(session_df["high"].max()),
        "asian_low": float(session_df["low"].min()),
    }


# ── OTE (Optimal Trade Entry) & Premium/Discount ────────────────────────────

def calculate_ote_zone(swing_low: float, swing_high: float, direction: str) -> Dict[str, float]:
    range_size = swing_high - swing_low
    if direction == "BUY":
        level_618 = swing_high - range_size * 0.618
        level_790 = swing_high - range_size * 0.790
        return {"zone_top": level_618, "zone_bottom": level_790}
    else:
        level_618 = swing_low + range_size * 0.618
        level_790 = swing_low + range_size * 0.790
        return {"zone_top": level_790, "zone_bottom": level_618}


def is_price_in_ote(price: float, ote_zone: Dict[str, float]) -> bool:
    return ote_zone["zone_bottom"] <= price <= ote_zone["zone_top"]


def check_fvg_ote_confluence(fvg: PDArray, ote_zone: Dict[str, float]) -> bool:
    if fvg.ce is None:
        return False
    return is_price_in_ote(fvg.ce, ote_zone)


def get_premium_discount_zone(swing_low: float, swing_high: float) -> Dict[str, float]:
    fib_50 = swing_low + (swing_high - swing_low) * 0.5
    return {"swing_low": swing_low, "swing_high": swing_high, "fib_50": fib_50}


def classify_pd_array_zone(pd_array: PDArray, pd_zone: Dict[str, float]) -> str:
    fib_50 = pd_zone["fib_50"]
    if pd_array.top < fib_50:
        return "DISCOUNT"
    if pd_array.bottom > fib_50:
        return "PREMIUM"
    return "MIXED"


def get_htf_bias_from_pd_zone(current_price: float, pd_zone: Dict[str, float]) -> str:
    fib_50 = pd_zone["fib_50"]
    if current_price < fib_50:
        return "DISCOUNT_BUY_ONLY"
    elif current_price > fib_50:
        return "PREMIUM_SELL_ONLY"
    return "NEUTRAL"


# ── BOS / CHoCH & Market Structure Labels ────────────────────────────────────

def detect_market_structure(df: pd.DataFrame, window: int = 2, n: int = 6) -> Dict[str, Any]:
    """Gán nhãn HH/HL/LH/LL cho các swing gần nhất và phân loại cấu trúc hiện tại."""
    swings = find_swing_points(df, window)
    h_map = {int(idx): float(row["high"]) for idx, row in swings[swings["swing_high"]].tail(n).iterrows()}
    l_map = {int(idx): float(row["low"]) for idx, row in swings[swings["swing_low"]].tail(n).iterrows()}

    events = sorted(set(h_map) | set(l_map))
    labeled: List[Dict[str, Any]] = []
    prev_high: Optional[float] = None
    prev_low: Optional[float] = None

    for idx in events:
        if idx in h_map:
            tag = "HH" if (prev_high is not None and h_map[idx] > prev_high) else ("LH" if prev_high is not None else "H")
            labeled.append({"index": idx, "type": "SWING_HIGH", "price": h_map[idx], "label": tag})
            prev_high = h_map[idx]
        if idx in l_map:
            tag = "HL" if (prev_low is not None and l_map[idx] > prev_low) else ("LL" if prev_low is not None else "L")
            labeled.append({"index": idx, "type": "SWING_LOW", "price": l_map[idx], "label": tag})
            prev_low = l_map[idx]

    tags = [e["label"] for e in labeled if e["label"] not in ("H", "L")]
    bull = sum(1 for t in tags if t in ("HH", "HL"))
    bear = sum(1 for t in tags if t in ("LH", "LL"))
    if bull > bear:
        structure = "UPTREND"
    elif bear > bull:
        structure = "DOWNTREND"
    else:
        structure = "RANGE"

    return {"labels": labeled, "structure": structure}


def detect_bos_choch(candles: List[Candle], swing_df: pd.DataFrame, current_index: int) -> Dict[str, Any]:
    """Phát hiện Break of Structure (BOS) và Change of Character (CHoCH).

    - BOS: phá vỡ swing cao/thấp CÙNG hướng cấu trúc (tiếp diễn xu hướng).
    - CHoCH: phá vỡ swing NGƯỢC cấu trúc trước đó (dấu hiệu đảo chiều).
    Trả về dict chứa kiểu, giá phá vỡ, index và hướng dự kiến tiếp theo.
    """
    if current_index >= len(candles):
        return {}
    current = candles[current_index]

    swing_highs = [(int(idx), float(row["high"])) for idx, row in swing_df[swing_df["swing_high"]].iterrows()]
    swing_lows = [(int(idx), float(row["low"])) for idx, row in swing_df[swing_df["swing_low"]].iterrows()]

    highs_before = [h for i, h in swing_highs if i < current_index]
    lows_before = [l for i, l in swing_lows if i < current_index]
    if len(highs_before) < 2 or len(lows_before) < 2:
        return {}

    recent_high = highs_before[-1]
    recent_low = lows_before[-1]
    prior_high = highs_before[-2]
    prior_low = lows_before[-2]

    was_uptrend = prior_high < recent_high and prior_low < recent_low
    was_downtrend = prior_high > recent_high and prior_low > recent_low

    if current.close > recent_high:
        kind = "BOS" if was_uptrend else "CHoCH"
        return {"kind": kind, "direction": "BULLISH", "break_price": recent_high, "index": current_index}
    if current.close < recent_low:
        kind = "BOS" if was_downtrend else "CHoCH"
        return {"kind": kind, "direction": "BEARISH", "break_price": recent_low, "index": current_index}

    return {}


# ── Trendline Detection ───────────────────────────────────────────────────────

def detect_trendlines(
    candles: List[Candle],
    swing_df: pd.DataFrame,
    n: int = 8,
    touch_tolerance_atr: float = 0.20,
    atr_series: Optional[pd.Series] = None,
) -> List[Dict[str, Any]]:
    """Vẽ trendline hỗ trợ (support) qua swing lows và kháng cự (resistance) qua swing highs.

    Mỗi đường cần >= 2 điểm chạm. Trả về [{'kind': 'SUPPORT'|'RESISTANCE', 'p1': {index, price, time},
    'p2': {...}, 'touches': int, 'slope': float}].
    """
    atr_now = float(atr_series.iloc[-1]) if atr_series is not None and len(atr_series) else 1.0
    tol = max(touch_tolerance_atr * atr_now, 1e-9)

    highs = [(int(idx), float(row["high"])) for idx, row in swing_df[swing_df["swing_high"]].tail(n).iterrows()]
    lows = [(int(idx), float(row["low"])) for idx, row in swing_df[swing_df["swing_low"]].tail(n).iterrows()]

    def _fit(points: List[Tuple[int, float]], kind: str) -> Optional[Dict[str, Any]]:
        if len(points) < 2:
            return None
        (i1, p1), (i2, p2) = points[0], points[-1]
        if i2 == i1:
            return None
        slope = (p2 - p1) / (i2 - i1)
        # dự đoán giá của đường tại mọi index, đếm điểm chạm trong tolerance
        touches = 0
        for i, p in points:
            expected = p1 + slope * (i - i1)
            if abs(expected - p) <= tol:
                touches += 1
        if touches < 2:
            return None
        t1, t2 = candles[i1].time, candles[i2].time
        return {
            "kind": kind,
            "index1": i1, "price1": p1, "time1": t1,
            "index2": i2, "price2": p2, "time2": t2,
            "touches": touches, "slope": slope,
        }

    results: List[Dict[str, Any]] = []
    if len(lows) >= 2:
        support = _fit(lows, "SUPPORT")
        if support:
            results.append(support)
    if len(highs) >= 2:
        resistance = _fit(highs, "RESISTANCE")
        if resistance:
            results.append(resistance)
    return results
