"""
Price Action thuần tuý: KHÔNG dùng khái niệm SMC/ICT (OB/FVG/CHoCH...).
Trend/Swing/HH-HL-LH-LL đã có sẵn trong structure.py (dùng chung) — module này
chỉ thêm phần price-action-riêng: S/R, Trendline, Channel, Range,
Breakout/Pullback/Retest/Fake Breakout, và 15 mẫu hình nến cổ điển
(Pin Bar, Engulfing, Inside/Outside Bar, Doji, Morning/Evening Star, Hammer,
Shooting Star, Tweezer Top/Bottom, Marubozu, Three White Soldiers, Three Black Crows).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from models import Candle, Direction, LevelType, PatternMarker, PriceLevel
from structure import get_swing_series


# ══════════════════════════════════════════════════════════════════
# 1. SUPPORT / RESISTANCE — cluster các swing points gần nhau thành 1 vùng
# ══════════════════════════════════════════════════════════════════

def find_support_resistance_zones(
    swing_df: pd.DataFrame, candles: list[Candle], tolerance_pct: float = 0.0015, min_touches: int = 2,
) -> list[PriceLevel]:
    """Gom các swing high/low có giá gần nhau (trong tolerance_pct) thành 1 vùng S/R, đếm số lần chạm."""
    highs, lows = get_swing_series(swing_df)
    levels: list[PriceLevel] = []

    def cluster(points: list[tuple[int, float]], level_type: LevelType):
        used = set()
        for i in range(len(points)):
            if i in used:
                continue
            group = [points[i]]
            for j in range(i + 1, len(points)):
                if j in used:
                    continue
                if abs(points[j][1] - points[i][1]) / points[i][1] <= tolerance_pct:
                    group.append(points[j]); used.add(j)
            if len(group) >= min_touches:
                avg_price = sum(p for _, p in group) / len(group)
                last_idx = max(idx for idx, _ in group)
                levels.append(PriceLevel(level_type, avg_price, last_idx, candles[last_idx].time,
                                          label=f"{level_type.value} ({len(group)} touches)", touch_count=len(group)))

    cluster(highs, LevelType.RESISTANCE)
    cluster(lows, LevelType.SUPPORT)
    return levels


# ══════════════════════════════════════════════════════════════════
# 2. TRENDLINE & CHANNEL — fit đường thẳng qua các swing cùng loại
# ══════════════════════════════════════════════════════════════════

def fit_trendline(points: list[tuple[int, float]]) -> dict | None:
    """Hồi quy tuyến tính đơn giản qua các điểm (index, price). Trả về {slope, intercept, r_squared}."""
    if len(points) < 2:
        return None
    xs = np.array([p[0] for p in points], dtype=float)
    ys = np.array([p[1] for p in points], dtype=float)
    slope, intercept = np.polyfit(xs, ys, 1)
    y_pred = slope * xs + intercept
    ss_res = np.sum((ys - y_pred) ** 2)
    ss_tot = np.sum((ys - ys.mean()) ** 2)
    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return {"slope": float(slope), "intercept": float(intercept), "r_squared": float(r_squared),
            "point_indices": [p[0] for p in points]}


def detect_trendlines(swing_df: pd.DataFrame, lookback_swings: int = 4, min_r_squared: float = 0.6) -> dict:
    """Fit trendline tăng (qua các swing low gần nhất) và trendline giảm (qua các swing high gần nhất)."""
    highs, lows = get_swing_series(swing_df)
    up_line = fit_trendline(lows[-lookback_swings:]) if len(lows) >= lookback_swings else None
    down_line = fit_trendline(highs[-lookback_swings:]) if len(highs) >= lookback_swings else None
    return {
        "support_trendline": up_line if (up_line and up_line["r_squared"] >= min_r_squared) else None,
        "resistance_trendline": down_line if (down_line and down_line["r_squared"] >= min_r_squared) else None,
    }


def detect_price_channel(trendlines: dict, max_width_ratio: float = 0.15) -> dict | None:
    """
    Channel = 2 trendline gần như song song (slope lệch nhau ít) kẹp giá ở giữa.
    Trả về None nếu không đủ 2 đường hoặc độ dốc lệch quá nhiều (không coi là song song).
    """
    up, down = trendlines.get("support_trendline"), trendlines.get("resistance_trendline")
    if not up or not down:
        return None
    slope_diff_ratio = abs(up["slope"] - down["slope"]) / (abs(up["slope"]) + abs(down["slope"]) + 1e-9)
    if slope_diff_ratio > max_width_ratio:
        return None
    return {"upper": down, "lower": up, "is_parallel": True, "slope_diff_ratio": round(slope_diff_ratio, 4)}


# ══════════════════════════════════════════════════════════════════
# 3. RANGE / SIDEWAY — vùng tích luỹ, biến động thấp
# ══════════════════════════════════════════════════════════════════

def detect_range(candles: list[Candle], atr_series: pd.Series, lookback: int = 20, max_range_atr_mult: float = 3.0) -> dict | None:
    """
    Range: N nến gần nhất có toàn bộ biên độ (max High - min Low) nhỏ hơn
    max_range_atr_mult * ATR trung bình đoạn đó -> coi là đang tích luỹ, không trend rõ.
    """
    if len(candles) < lookback:
        return None
    window = candles[-lookback:]
    atr_window = atr_series.iloc[-lookback:]
    range_high = max(c.high for c in window)
    range_low = min(c.low for c in window)
    avg_atr = atr_window.mean()
    if avg_atr <= 0:
        return None
    is_range = (range_high - range_low) <= max_range_atr_mult * avg_atr
    return {
        "is_range": is_range, "range_high": range_high, "range_low": range_low,
        "width": range_high - range_low, "avg_atr": avg_atr,
        "start_index": window[0].index, "end_index": window[-1].index,
    }


# ══════════════════════════════════════════════════════════════════
# 4. BREAKOUT / PULLBACK / RETEST / FAKE BREAKOUT
# ══════════════════════════════════════════════════════════════════

def detect_breakout(candles: list[Candle], level: float, direction: Direction, confirm_index: int,
                     min_body_ratio: float = 0.5) -> PatternMarker | None:
    """Breakout: nến đóng cửa vượt qua 1 mức S/R/range-boundary với thân nến đủ lớn (không phải doji yếu)."""
    c = candles[confirm_index]
    if direction == Direction.BULLISH and c.close > level and c.body_ratio >= min_body_ratio and c.is_bullish:
        return PatternMarker("BREAKOUT", Direction.BULLISH, c.index, c.time, c.close, {"level": level})
    if direction == Direction.BEARISH and c.close < level and c.body_ratio >= min_body_ratio and c.is_bearish:
        return PatternMarker("BREAKOUT", Direction.BEARISH, c.index, c.time, c.close, {"level": level})
    return None


def detect_pullback(candles: list[Candle], breakout: PatternMarker, max_pullback_pct: float = 0.5) -> PatternMarker | None:
    """
    Pullback: sau breakout, giá hồi về NHƯNG không vượt qua lại điểm breakout gốc quá max_pullback_pct
    (đo theo % khoảng cách đã đi được kể từ breakout tới đỉnh/đáy tiếp theo).
    """
    level = breakout.meta["level"]
    start_idx = breakout.index
    after = candles[start_idx + 1:]
    if not after:
        return None

    if breakout.direction == Direction.BULLISH:
        peak = max((c.high for c in after), default=level)
        pullback_low = min((c.low for c in after), default=peak)
        traveled = peak - level
        retraced = peak - pullback_low
        if traveled > 0 and retraced / traveled <= max_pullback_pct and pullback_low > level:
            idx = next(c.index for c in after if c.low == pullback_low)
            return PatternMarker("PULLBACK", Direction.BULLISH, idx, candles[idx].time, pullback_low,
                                  {"retrace_ratio": round(retraced / traveled, 3)})
    else:
        trough = min((c.low for c in after), default=level)
        pullback_high = max((c.high for c in after), default=trough)
        traveled = level - trough
        retraced = pullback_high - trough
        if traveled > 0 and retraced / traveled <= max_pullback_pct and pullback_high < level:
            idx = next(c.index for c in after if c.high == pullback_high)
            return PatternMarker("PULLBACK", Direction.BEARISH, idx, candles[idx].time, pullback_high,
                                  {"retrace_ratio": round(retraced / traveled, 3)})
    return None


def detect_retest(candles: list[Candle], breakout: PatternMarker, touch_tolerance_pct: float = 0.001) -> PatternMarker | None:
    """Retest: giá quay lại chạm ĐÚNG mức breakout gốc (không xuyên qua đáng kể) rồi tiếp tục đi đúng hướng breakout."""
    level = breakout.meta["level"]
    after = candles[breakout.index + 1:]
    for i, c in enumerate(after):
        touched = abs(c.low - level) / level <= touch_tolerance_pct if breakout.direction == Direction.BULLISH \
            else abs(c.high - level) / level <= touch_tolerance_pct
        if touched:
            # xác nhận tiếp diễn: nến ngay sau đó đóng cửa đúng hướng breakout
            if i + 1 < len(after):
                nxt = after[i + 1]
                continued = nxt.close > level if breakout.direction == Direction.BULLISH else nxt.close < level
                if continued:
                    return PatternMarker("RETEST", breakout.direction, c.index, c.time, level, {"confirmed": True})
    return None


def detect_fake_breakout(candles: list[Candle], breakout: PatternMarker, reversal_window: int = 5) -> PatternMarker | None:
    """Fake Breakout: giá breakout nhưng đóng cửa quay lại TRONG vùng cũ trong vòng reversal_window nến kế tiếp."""
    level = breakout.meta["level"]
    after = candles[breakout.index + 1: breakout.index + 1 + reversal_window]
    for c in after:
        if breakout.direction == Direction.BULLISH and c.close < level:
            return PatternMarker("FAKE_BREAKOUT", Direction.BEARISH, c.index, c.time, c.close,
                                  {"original_breakout_index": breakout.index})
        if breakout.direction == Direction.BEARISH and c.close > level:
            return PatternMarker("FAKE_BREAKOUT", Direction.BULLISH, c.index, c.time, c.close,
                                  {"original_breakout_index": breakout.index})
    return None


def scan_breakout_lifecycle(candles: list[Candle], levels: list[PriceLevel]) -> list[PatternMarker]:
    """Quét toàn bộ chuỗi nến, với mỗi PriceLevel (S/R) tìm breakout -> rồi pullback/retest/fake breakout đi kèm."""
    markers: list[PatternMarker] = []
    for lvl in levels:
        direction = Direction.BULLISH if lvl.type == LevelType.RESISTANCE else Direction.BEARISH
        for i in range(lvl.formed_at_index + 1, len(candles)):
            bo = detect_breakout(candles, lvl.price, direction, i)
            if bo:
                markers.append(bo)
                fake = detect_fake_breakout(candles, bo)
                if fake:
                    markers.append(fake)
                else:
                    pb = detect_pullback(candles, bo)
                    if pb:
                        markers.append(pb)
                    rt = detect_retest(candles, bo)
                    if rt:
                        markers.append(rt)
                break  # chỉ lấy breakout đầu tiên của mỗi level để tránh trùng lặp
    return markers


# ══════════════════════════════════════════════════════════════════
# 5. CANDLESTICK PATTERNS — 15 mẫu hình cổ điển (Nison)
# ══════════════════════════════════════════════════════════════════

def is_doji(c: Candle, max_body_ratio: float = 0.1) -> bool:
    return c.body_ratio <= max_body_ratio


def is_marubozu(c: Candle, min_body_ratio: float = 0.95) -> bool:
    return c.body_ratio >= min_body_ratio


def is_hammer(c: Candle, min_lower_wick_ratio: float = 0.6, max_upper_wick_ratio: float = 0.1) -> bool:
    """Hammer: thân nhỏ ở nửa trên range, râu dưới rất dài, râu trên rất ngắn (tín hiệu đảo chiều TẠI ĐÁY)."""
    return (c.lower_wick_ratio >= min_lower_wick_ratio and c.upper_wick_ratio <= max_upper_wick_ratio
            and c.body_ratio <= 0.35)


def is_shooting_star(c: Candle, min_upper_wick_ratio: float = 0.6, max_lower_wick_ratio: float = 0.1) -> bool:
    """Shooting Star: đối xứng Hammer, râu trên rất dài, tại ĐỈNH."""
    return (c.upper_wick_ratio >= min_upper_wick_ratio and c.lower_wick_ratio <= max_lower_wick_ratio
            and c.body_ratio <= 0.35)


def is_pin_bar(c: Candle, min_wick_ratio: float = 0.66) -> str | None:
    """Pin Bar tổng quát (không phân biệt vị trí đỉnh/đáy như Hammer/Shooting Star): trả về 'BULLISH'/'BEARISH'/None."""
    if c.lower_wick_ratio >= min_wick_ratio and c.body_ratio <= 0.25:
        return "BULLISH"
    if c.upper_wick_ratio >= min_wick_ratio and c.body_ratio <= 0.25:
        return "BEARISH"
    return None


def is_engulfing(prev: Candle, cur: Candle) -> str | None:
    """Engulfing: thân nến sau bao trọn thân nến trước, ngược hướng. Trả về 'BULLISH'/'BEARISH'/None."""
    if prev.is_bearish and cur.is_bullish and cur.close >= prev.open and cur.open <= prev.close:
        return "BULLISH"
    if prev.is_bullish and cur.is_bearish and cur.close <= prev.open and cur.open >= prev.close:
        return "BEARISH"
    return None


def is_inside_bar(prev: Candle, cur: Candle) -> bool:
    return cur.high <= prev.high and cur.low >= prev.low


def is_outside_bar(prev: Candle, cur: Candle) -> bool:
    return cur.high >= prev.high and cur.low <= prev.low


def is_tweezer_top(prev: Candle, cur: Candle, tolerance_pct: float = 0.0008) -> bool:
    return (prev.is_bullish and cur.is_bearish and abs(prev.high - cur.high) / prev.high <= tolerance_pct)


def is_tweezer_bottom(prev: Candle, cur: Candle, tolerance_pct: float = 0.0008) -> bool:
    return (prev.is_bearish and cur.is_bullish and abs(prev.low - cur.low) / prev.low <= tolerance_pct)


def is_morning_star(c1: Candle, c2: Candle, c3: Candle) -> bool:
    """3 nến: giảm mạnh -> doji/thân nhỏ (gap xuống) -> tăng mạnh đóng cửa sâu vào thân nến 1."""
    return (c1.is_bearish and c1.body_ratio > 0.5
            and c2.body_ratio < 0.35 and max(c2.open, c2.close) < c1.close
            and c3.is_bullish and c3.body_ratio > 0.5 and c3.close > (c1.open + c1.close) / 2)


def is_evening_star(c1: Candle, c2: Candle, c3: Candle) -> bool:
    """Đối xứng Morning Star, tại đỉnh."""
    return (c1.is_bullish and c1.body_ratio > 0.5
            and c2.body_ratio < 0.35 and min(c2.open, c2.close) > c1.close
            and c3.is_bearish and c3.body_ratio > 0.5 and c3.close < (c1.open + c1.close) / 2)


def is_three_white_soldiers(c1: Candle, c2: Candle, c3: Candle, min_body_ratio: float = 0.6) -> bool:
    """3 nến tăng liên tiếp, thân lớn, mỗi nến đóng cửa cao hơn nến trước, mở cửa trong thân nến trước."""
    candles = [c1, c2, c3]
    if not all(c.is_bullish and c.body_ratio >= min_body_ratio for c in candles):
        return False
    return (c2.close > c1.close and c3.close > c2.close
            and c1.open < c2.open < c2.close and c2.open < c3.open < c3.close)


def is_three_black_crows(c1: Candle, c2: Candle, c3: Candle, min_body_ratio: float = 0.6) -> bool:
    """Đối xứng Three White Soldiers, giảm."""
    candles = [c1, c2, c3]
    if not all(c.is_bearish and c.body_ratio >= min_body_ratio for c in candles):
        return False
    return (c2.close < c1.close and c3.close < c2.close
            and c1.open > c2.open > c2.close and c2.open > c3.open > c3.close)


def scan_candlestick_patterns(candles: list[Candle]) -> list[PatternMarker]:
    """Quét toàn bộ chuỗi nến, trả về list PatternMarker cho mọi mẫu hình phát hiện được."""
    markers: list[PatternMarker] = []

    for i, c in enumerate(candles):
        if is_doji(c):
            markers.append(PatternMarker("DOJI", Direction.NEUTRAL, i, c.time, c.mid))
        if is_marubozu(c):
            d = Direction.BULLISH if c.is_bullish else Direction.BEARISH
            markers.append(PatternMarker("MARUBOZU", d, i, c.time, c.mid))
        if is_hammer(c):
            markers.append(PatternMarker("HAMMER", Direction.BULLISH, i, c.time, c.low))
        if is_shooting_star(c):
            markers.append(PatternMarker("SHOOTING_STAR", Direction.BEARISH, i, c.time, c.high))
        pin = is_pin_bar(c)
        if pin:
            price = c.low if pin == "BULLISH" else c.high
            markers.append(PatternMarker("PIN_BAR", Direction(pin), i, c.time, price))

        if i >= 1:
            prev = candles[i - 1]
            eng = is_engulfing(prev, c)
            if eng:
                markers.append(PatternMarker("ENGULFING", Direction(eng), i, c.time, c.mid))
            if is_inside_bar(prev, c):
                markers.append(PatternMarker("INSIDE_BAR", Direction.NEUTRAL, i, c.time, c.mid))
            if is_outside_bar(prev, c):
                markers.append(PatternMarker("OUTSIDE_BAR", Direction.NEUTRAL, i, c.time, c.mid))
            if is_tweezer_top(prev, c):
                markers.append(PatternMarker("TWEEZER_TOP", Direction.BEARISH, i, c.time, c.high))
            if is_tweezer_bottom(prev, c):
                markers.append(PatternMarker("TWEEZER_BOTTOM", Direction.BULLISH, i, c.time, c.low))

        if i >= 2:
            c1, c2, c3 = candles[i - 2], candles[i - 1], c
            if is_morning_star(c1, c2, c3):
                markers.append(PatternMarker("MORNING_STAR", Direction.BULLISH, i, c.time, c3.low))
            if is_evening_star(c1, c2, c3):
                markers.append(PatternMarker("EVENING_STAR", Direction.BEARISH, i, c.time, c3.high))
            if is_three_white_soldiers(c1, c2, c3):
                markers.append(PatternMarker("THREE_WHITE_SOLDIERS", Direction.BULLISH, i, c.time, c3.close))
            if is_three_black_crows(c1, c2, c3):
                markers.append(PatternMarker("THREE_BLACK_CROWS", Direction.BEARISH, i, c.time, c3.close))

    return markers
