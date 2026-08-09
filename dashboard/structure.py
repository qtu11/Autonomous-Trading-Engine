"""
Module LÕI dùng chung cho cả SMC (smc.py) và ICT (ict.py) — vì 2 phương pháp này
chia sẻ phần lớn nền tảng cấu trúc thị trường (Market Structure): swing point,
BOS/CHoCH/MSS, Order Block, Breaker/Mitigation Block, FVG/Inversion FVG,
Liquidity (BSL/SSL/EQH/EQL), Premium/Discount/Equilibrium/Dealing Range.

Viết 1 lần ở đây, smc.py và ict.py cùng import — tránh 2 định nghĩa lệch nhau
cho cùng 1 khái niệm (rủi ro lớn nhất khi code 2 phương pháp gần giống nhau).
"""
from __future__ import annotations

from typing import Any, cast

import pandas as pd
from models import (
    BoxType,
    Candle,
    Direction,
    LevelType,
    PDBox,
    PriceLevel,
    StructureEvent,
)

# ══════════════════════════════════════════════════════════════════
# 1. SWING POINTS (Fractal) — nền tảng của mọi thứ khác
# ══════════════════════════════════════════════════════════════════

def find_swing_points(df: pd.DataFrame, window: int = 2) -> pd.DataFrame:
    """Đánh dấu swing_high/swing_low bằng thuật toán Fractal window-nến 2 bên."""
    df = df.copy()
    df["swing_high"] = False
    df["swing_low"] = False
    highs, lows = df["high"].to_numpy(), df["low"].to_numpy()
    n = len(df)
    for i in range(window, n - window):
        if highs[i] > highs[i - window:i].max() and highs[i] > highs[i + 1:i + window + 1].max():
            df.at[i, "swing_high"] = True
        if lows[i] < lows[i - window:i].min() and lows[i] < lows[i + 1:i + window + 1].min():
            df.at[i, "swing_low"] = True
    return df


def get_swing_series(swing_df: pd.DataFrame) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Trả về [(index, price), ...] cho swing highs và swing lows, sắp theo thời gian."""
    highs = [(int(cast(Any, i)), float(row["high"])) for i, row in swing_df[swing_df["swing_high"]].iterrows()]
    lows = [(int(cast(Any, i)), float(row["low"])) for i, row in swing_df[swing_df["swing_low"]].iterrows()]
    return highs, lows


def label_swing_sequence(swing_df: pd.DataFrame) -> list[dict]:
    """
    Gán nhãn HH/HL/LH/LL cho từng swing point theo thứ tự thời gian (Price Action mục HH/HL/LH/LL).
    Trả về list các dict {index, price, kind: "high"/"low", label: "HH"/"HL"/"LH"/"LL"}.
    """
    highs, lows = get_swing_series(swing_df)
    events = sorted(
        [(i, p, "high") for i, p in highs] + [(i, p, "low") for i, p in lows],
        key=lambda x: x[0]
    )
    result = []
    last_high, last_low = None, None
    for idx, price, kind in events:
        if kind == "high":
            label = "HH" if (last_high is not None and price > last_high) else \
                    ("LH" if last_high is not None else "H")
            last_high = price
        else:
            label = "HL" if (last_low is not None and price > last_low) else \
                    ("LL" if last_low is not None else "L")
            last_low = price
        result.append({"index": idx, "price": price, "kind": kind, "label": label})
    return result


def classify_trend_structure(swing_df: pd.DataFrame, lookback_swings: int = 3) -> str:
    """UPTREND (HH+HL liên tiếp) / DOWNTREND (LH+LL liên tiếp) / RANGE."""
    labels = label_swing_sequence(swing_df)[-lookback_swings * 2:]
    if len(labels) < 4:
        return "INSUFFICIENT_DATA"
    kinds = [e["label"] for e in labels]
    if kinds.count("HH") + kinds.count("HL") >= len(kinds) - 1 and "LL" not in kinds and "LH" not in kinds:
        return "UPTREND"
    if kinds.count("LH") + kinds.count("LL") >= len(kinds) - 1 and "HH" not in kinds and "HL" not in kinds:
        return "DOWNTREND"
    return "RANGE"


# ══════════════════════════════════════════════════════════════════
# 2. BOS / CHoCH / MSS — phân biệt chính xác theo trend hiện tại
# ══════════════════════════════════════════════════════════════════

def detect_structure_events(candles: list[Candle], swing_df: pd.DataFrame) -> list[StructureEvent]:
    """
    Quét toàn bộ chuỗi nến, phân loại mỗi lần giá đóng cửa phá 1 swing point
    thành BOS (tiếp diễn, phá swing CÙNG hướng trend) hay CHoCH (đảo chiều,
    phá swing NGƯỢC hướng trend). MSS được gán cho CHoCH xảy ra ở khung nội bộ
    (áp dụng identical logic, phân biệt bằng context gọi ở smc.py/ict.py).

    Look-ahead-safe: mọi swing tham chiếu đều lấy từ TRƯỚC index hiện tại.
    """
    events: list[StructureEvent] = []
    highs, lows = get_swing_series(swing_df)
    trend = "RANGE"
    last_broken_high_idx, last_broken_low_idx = -1, -1

    for i, c in enumerate(candles):
        past_highs = [(idx, p) for idx, p in highs if idx < i]
        past_lows = [(idx, p) for idx, p in lows if idx < i]
        if not past_highs or not past_lows:
            continue

        nearest_high_idx, nearest_high = past_highs[-1]
        nearest_low_idx, nearest_low = past_lows[-1]

        broke_up = c.close > nearest_high and nearest_high_idx != last_broken_high_idx
        broke_down = c.close < nearest_low and nearest_low_idx != last_broken_low_idx

        if broke_up:
            ev_type = "BOS" if trend == "UPTREND" else "CHOCH"
            events.append(StructureEvent(ev_type, Direction.BULLISH, i, c.time, nearest_high, nearest_high_idx))
            trend = "UPTREND"
            last_broken_high_idx = nearest_high_idx
        elif broke_down:
            ev_type = "BOS" if trend == "DOWNTREND" else "CHOCH"
            events.append(StructureEvent(ev_type, Direction.BEARISH, i, c.time, nearest_low, nearest_low_idx))
            trend = "DOWNTREND"
            last_broken_low_idx = nearest_low_idx

    return events


def get_current_trend_at(events: list[StructureEvent], up_to_index: int) -> str:
    """Trend hiện tại (theo BOS/CHoCH gần nhất) tính tới 1 index cụ thể — dùng cho backtest walk-forward."""
    relevant = [e for e in events if e.index <= up_to_index]
    if not relevant:
        return "RANGE"
    return "UPTREND" if relevant[-1].direction == Direction.BULLISH else "DOWNTREND"


# ══════════════════════════════════════════════════════════════════
# 3. ORDER BLOCK, BREAKER BLOCK, MITIGATION BLOCK
# ══════════════════════════════════════════════════════════════════

def detect_order_blocks(
    candles: list[Candle], swing_df: pd.DataFrame,
    atr_series: pd.Series | None = None, displacement_atr_mult: float = 2.0,
    min_body_ratio: float = 0.55,
) -> list[PDBox]:
    """Nến đối lập cuối cùng trước displacement phá swing point gần nhất (Chương I mục 3)."""
    boxes: list[PDBox] = []
    highs, lows = get_swing_series(swing_df)

    for i in range(1, len(candles) - 1):
        cur, prev = candles[i], candles[i - 1]
        atr_now = atr_series.iloc[i] if atr_series is not None else None
        strong = cur.body_ratio >= min_body_ratio and (
            atr_now is None or cur.body_size >= displacement_atr_mult * atr_now
        )
        if not strong:
            continue

        if prev.is_bearish and cur.is_bullish:
            past_highs = [p for idx, p in highs if idx < i]
            if past_highs and cur.close > past_highs[-1]:
                boxes.append(PDBox(BoxType.ORDER_BLOCK, Direction.BULLISH, prev.high, prev.low,
                                    i - 1, prev.time, meta={"displacement_index": i}))

        if prev.is_bullish and cur.is_bearish:
            past_lows = [p for idx, p in lows if idx < i]
            if past_lows and cur.close < past_lows[-1]:
                boxes.append(PDBox(BoxType.ORDER_BLOCK, Direction.BEARISH, prev.high, prev.low,
                                    i - 1, prev.time, meta={"displacement_index": i}))
    return boxes


def mark_boxes_mitigated(boxes: list[PDBox], candles: list[Candle], close_based: bool = True) -> None:
    """Cập nhật mitigated=True nếu giá sau đó xuyên qua toàn bộ box. close_based=False dùng cho Mitigation Block (wick)."""
    for box in boxes:
        if box.mitigated:
            continue
        for c in candles[box.start_index + 1:]:
            ref_bull = c.close if close_based else c.low
            ref_bear = c.close if close_based else c.high
            if box.direction == Direction.BULLISH and ref_bull < box.bottom:
                box.mitigated = True
                box.mitigated_at_index = c.index
                box.end_index = c.index
                break
            if box.direction == Direction.BEARISH and ref_bear > box.top:
                box.mitigated = True
                box.mitigated_at_index = c.index
                box.end_index = c.index
                break


def detect_breaker_and_mitigation_blocks(
    order_blocks: list[PDBox], candles: list[Candle], liquidity_levels: list[PriceLevel] | None = None,
) -> list[PDBox]:
    """
    Với mỗi OB đã mitigated: nếu phá bằng CLOSE → Breaker Block; nếu chỉ phá bằng WICK → Mitigation Block.
    Nếu có liquidity_levels: Breaker chỉ hợp lệ khi TRƯỚC đó đã có 1 lần sweep BSL/SSL tương ứng
    (đúng định nghĩa ICT — Chương I mục 6, khác Mitigation Block ở việc THIẾU bước sweep này — mục 7).
    """
    results: list[PDBox] = []
    for ob in order_blocks:
        if not ob.mitigated:
            continue
        failure_idx, failed_by_close = None, False
        for idx in range(ob.start_index + 1, len(candles)):
            c = candles[idx]
            if ob.direction == Direction.BULLISH:
                wick_breach, close_breach = c.low < ob.bottom, c.close < ob.bottom
            else:
                wick_breach, close_breach = c.high > ob.top, c.close > ob.top
            if close_breach:
                failure_idx, failed_by_close = idx, True
                break
            if wick_breach and failure_idx is None:
                failure_idx, failed_by_close = idx, False

        if failure_idx is None:
            continue

        new_dir = Direction.BEARISH if ob.direction == Direction.BULLISH else Direction.BULLISH

        swept_before = False
        if liquidity_levels:
            target_type = LevelType.BSL if ob.direction == Direction.BULLISH else LevelType.SSL
            swept_before = any(
                lvl.type == target_type and lvl.swept and lvl.swept_at_index is not None
                and lvl.swept_at_index < failure_idx
                for lvl in liquidity_levels
            )

        if failed_by_close:
            box_type = BoxType.BREAKER_BLOCK if (liquidity_levels is None or swept_before) else BoxType.MITIGATION_BLOCK
        else:
            box_type = BoxType.MITIGATION_BLOCK

        results.append(PDBox(box_type, new_dir, ob.top, ob.bottom, failure_idx, candles[failure_idx].time,
                              meta={"origin_ob_index": ob.start_index, "swept_liquidity_before": swept_before}))
    return results


def detect_rejection_blocks(swing_df: pd.DataFrame, candles: list[Candle], cluster_size: int = 3) -> list[PDBox]:
    """
    Rejection Block (Chương I mục 2): vùng wick tổng hợp của 1 CỤM nến quanh swing point,
    KHÁC Order Block ở chỗ dùng phần râu (wick) thay vì toàn bộ range nến.
    top/bottom lấy từ max(Open,Close) và max(High) của cụm (đỉnh), hoặc đối xứng cho đáy.
    """
    boxes: list[PDBox] = []
    highs, lows = get_swing_series(swing_df)

    for idx, _ in highs:
        lo = max(0, idx - cluster_size // 2)
        hi = min(len(candles), idx + cluster_size // 2 + 1)
        cluster = candles[lo:hi]
        if not cluster:
            continue
        body_extreme = max(max(c.open, c.close) for c in cluster)
        wick_extreme = max(c.high for c in cluster)
        if wick_extreme > body_extreme:
            boxes.append(PDBox(BoxType.REJECTION_BLOCK, Direction.BEARISH, wick_extreme, body_extreme,
                                idx, candles[idx].time))

    for idx, _ in lows:
        lo = max(0, idx - cluster_size // 2)
        hi = min(len(candles), idx + cluster_size // 2 + 1)
        cluster = candles[lo:hi]
        if not cluster:
            continue
        body_extreme = min(min(c.open, c.close) for c in cluster)
        wick_extreme = min(c.low for c in cluster)
        if wick_extreme < body_extreme:
            boxes.append(PDBox(BoxType.REJECTION_BLOCK, Direction.BULLISH, body_extreme, wick_extreme,
                                idx, candles[idx].time))
    return boxes


# ══════════════════════════════════════════════════════════════════
# 4. FVG / INVERSION FVG / BPR
# ══════════════════════════════════════════════════════════════════

def detect_fvg(candles: list[Candle]) -> list[PDBox]:
    """FVG chuẩn ICT/SMC: 3-candle wick gap (Chương I mục 4). BISI=Bullish, SIBI=Bearish."""
    boxes: list[PDBox] = []
    for i in range(2, len(candles)):
        c0, c2 = candles[i - 2], candles[i]
        if c2.low > c0.high:
            top, bottom = c2.low, c0.high
            boxes.append(PDBox(BoxType.FVG, Direction.BULLISH, top, bottom, i, c2.time,
                                meta={"ce": (top + bottom) / 2, "name": "BISI"}))
        if c2.high < c0.low:
            top, bottom = c0.low, c2.high
            boxes.append(PDBox(BoxType.FVG, Direction.BEARISH, top, bottom, i, c2.time,
                                meta={"ce": (top + bottom) / 2, "name": "SIBI"}))
    return boxes


def get_fvg_fill_state(fvg: PDBox, candles: list[Candle]) -> str:
    """VIRGIN / PARTIAL / CE_FILLED / FULLY_FILLED."""
    touched = ce_touched = fully_filled = False
    ce = fvg.meta["ce"]
    for c in candles[fvg.start_index + 1:]:
        if fvg.direction == Direction.BULLISH:
            if c.low <= fvg.top: touched = True
            if c.low <= ce: ce_touched = True
            if c.low <= fvg.bottom: fully_filled = True
        else:
            if c.high >= fvg.bottom: touched = True
            if c.high >= ce: ce_touched = True
            if c.high >= fvg.top: fully_filled = True
    if fully_filled: return "FULLY_FILLED"
    if ce_touched: return "CE_FILLED"
    if touched: return "PARTIAL"
    return "VIRGIN"


def detect_inversion_fvg(fvg_list: list[PDBox], candles: list[Candle]) -> list[PDBox]:
    """iFVG (Chương I mục 8): FVG bị Fully Filled → đổi vai trò, đảo direction."""
    results: list[PDBox] = []
    for fvg in fvg_list:
        state = get_fvg_fill_state(fvg, candles)
        if state != "FULLY_FILLED":
            continue
        # tìm index nến gây fully-filled để đặt mốc thời gian cho iFVG
        fill_idx = None
        for c in candles[fvg.start_index + 1:]:
            if fvg.direction == Direction.BULLISH and c.low <= fvg.bottom:
                fill_idx = c.index; break
            if fvg.direction == Direction.BEARISH and c.high >= fvg.top:
                fill_idx = c.index; break
        if fill_idx is None:
            continue
        new_dir = Direction.BEARISH if fvg.direction == Direction.BULLISH else Direction.BULLISH
        results.append(PDBox(BoxType.INVERSION_FVG, new_dir, fvg.top, fvg.bottom, fill_idx, candles[fill_idx].time,
                              meta={"origin_fvg_index": fvg.start_index, "ce": fvg.meta["ce"]}))
    return results


def detect_bpr(fvg_list: list[PDBox]) -> list[PDBox]:
    """
    BPR - Balanced Price Range (ICT, đã verify qua search): vùng chồng lấp của 2 FVG ĐỐI HƯỚNG
    (1 Bullish FVG + 1 Bearish FVG) tại cùng 1 vùng giá. CE của BPR = trung điểm vùng chồng lấp.
    """
    boxes: list[PDBox] = []
    bulls = [f for f in fvg_list if f.direction == Direction.BULLISH]
    bears = [f for f in fvg_list if f.direction == Direction.BEARISH]
    for b in bulls:
        for s in bears:
            overlap = b.overlaps(s)
            if overlap is None:
                continue
            top, bottom = overlap
            later = max(b.start_index, s.start_index)
            later_time = b.start_time if b.start_index > s.start_index else s.start_time
            direction = Direction.BULLISH if b.start_index > s.start_index else Direction.BEARISH
            boxes.append(PDBox(BoxType.BPR, direction, top, bottom, later, later_time,
                                meta={"ce": (top + bottom) / 2,
                                      "bullish_fvg_index": b.start_index, "bearish_fvg_index": s.start_index}))
    return boxes


def detect_volume_imbalance(candles: list[Candle]) -> list[PDBox]:
    """
    Volume Imbalance (đã verify qua search — KHÁC FVG): gap thân nến 2-CANDLE
    (close nến 1 → open nến 2), wick 2 nến có thể vẫn chồng lấp. "Micro FVG".
    """
    boxes: list[PDBox] = []
    for i in range(1, len(candles)):
        c0, c1 = candles[i - 1], candles[i]
        if c1.open > c0.close and min(c0.high, c1.high) >= max(c0.low, c1.low):
            # thân nến tách rời nhưng wick vẫn overlap -> volume imbalance (không phải gap tuyệt đối)
            boxes.append(PDBox(BoxType.VOLUME_IMBALANCE, Direction.BULLISH, c1.open, c0.close, i, c1.time))
        if c1.open < c0.close and min(c0.high, c1.high) >= max(c0.low, c1.low):
            boxes.append(PDBox(BoxType.VOLUME_IMBALANCE, Direction.BEARISH, c0.close, c1.open, i, c1.time))
    return boxes


def detect_liquidity_void(candles: list[Candle], min_run: int = 3, min_body_ratio: float = 0.7) -> list[PDBox]:
    """Liquidity Void (Chương I mục 5): chuỗi N nến thân dài liên tiếp cùng hướng, wick đối ứng rất nhỏ."""
    boxes: list[PDBox] = []
    i = 0
    while i < len(candles) - min_run + 1:
        run = [candles[i]]
        j = i + 1
        direction = Direction.BULLISH if candles[i].is_bullish else (Direction.BEARISH if candles[i].is_bearish else None)
        if direction is None or candles[i].body_ratio < min_body_ratio:
            i += 1
            continue
        while j < len(candles):
            c = candles[j]
            same_dir = (c.is_bullish and direction == Direction.BULLISH) or (c.is_bearish and direction == Direction.BEARISH)
            opposite_wick = c.upper_wick_ratio if direction == Direction.BULLISH else c.lower_wick_ratio
            if same_dir and c.body_ratio >= min_body_ratio and opposite_wick < 0.15:
                run.append(c); j += 1
            else:
                break
        if len(run) >= min_run:
            top = max(c.high for c in run)
            bottom = min(c.low for c in run)
            boxes.append(PDBox(BoxType.LIQUIDITY_VOID, direction, top, bottom, run[0].index, run[0].time,
                                end_index=run[-1].index, meta={"candle_count": len(run)}))
            i = j
        else:
            i += 1
    return boxes


# ══════════════════════════════════════════════════════════════════
# 5. LIQUIDITY: BSL/SSL, EQH/EQL, Internal/External, Sweep
# ══════════════════════════════════════════════════════════════════

def build_liquidity_levels(swing_df: pd.DataFrame, candles: list[Candle]) -> list[PriceLevel]:
    """Tạo PriceLevel BSL (tại mỗi swing high) / SSL (tại mỗi swing low)."""
    highs, lows = get_swing_series(swing_df)
    levels = []
    for idx, price in highs:
        levels.append(PriceLevel(LevelType.BSL, price, idx, candles[idx].time, label=f"BSL@{idx}"))
    for idx, price in lows:
        levels.append(PriceLevel(LevelType.SSL, price, idx, candles[idx].time, label=f"SSL@{idx}"))
    return levels


def mark_liquidity_swept(levels: list[PriceLevel], candles: list[Candle]) -> None:
    """Đánh dấu swept=True nếu có nến sau đó xuyên wick qua mức, rồi đóng cửa rút lại (Liquidity Sweep)."""
    for lvl in levels:
        for c in candles[lvl.formed_at_index + 1:]:
            if lvl.type == LevelType.BSL and c.high > lvl.price and c.close < lvl.price:
                lvl.swept, lvl.swept_at_index = True, c.index
                break
            if lvl.type == LevelType.SSL and c.low < lvl.price and c.close > lvl.price:
                lvl.swept, lvl.swept_at_index = True, c.index
                break


def detect_equal_highs_lows(swing_df: pd.DataFrame, candles: list[Candle], tolerance_pct: float = 0.0005) -> list[PriceLevel]:
    """EQH/EQL: 2+ đỉnh/đáy có sai số tương đối <= tolerance_pct. Trả về PriceLevel tại giá trung bình cụm."""
    highs, lows = get_swing_series(swing_df)
    levels = []

    def cluster(points, level_type):
        used = set()
        for i in range(len(points)):
            if i in used:
                continue
            group = [points[i]]
            for j in range(i + 1, len(points)):
                if j in used:
                    continue
                if abs(points[j][1] - points[i][1]) / points[i][1] <= tolerance_pct:
                    group.append(points[j])
                    used.add(j)
            if len(group) >= 2:
                avg_price = sum(p for _, p in group) / len(group)
                last_idx = max(idx for idx, _ in group)
                levels.append(PriceLevel(level_type, avg_price, last_idx, candles[last_idx].time,
                                          label=f"{level_type.value} x{len(group)}", touch_count=len(group)))
        return levels

    cluster(highs, LevelType.EQH)
    cluster(lows, LevelType.EQL)
    return levels


def classify_internal_external_liquidity(
    levels: list[PriceLevel], dealing_range: dict,
) -> dict[str, list[PriceLevel]]:
    """
    Internal Liquidity (nằm TRONG dealing range hiện tại, thường quanh FVG nội bộ)
    vs External Liquidity (nằm NGOÀI biên dealing range, tại BSL/SSL chính) — đã verify qua search.
    """
    internal, external = [], []
    for lvl in levels:
        if dealing_range["low"] < lvl.price < dealing_range["high"]:
            internal.append(lvl)
        else:
            external.append(lvl)
    return {"internal": internal, "external": external}


def detect_inducement(
    swing_df: pd.DataFrame, candles: list[Candle], main_swing_index: int, direction: Direction,
) -> PriceLevel | None:
    """
    Inducement (IDM): swing nhỏ hình thành TRƯỚC main_swing_index cùng hướng, bị quét TRƯỚC khi
    main swing bị quét — dùng để lọc OB chất lượng cao (Chương I, mục Inducement).
    """
    highs, lows = get_swing_series(swing_df)
    candidates = [(idx, p) for idx, p in (lows if direction == Direction.BULLISH else highs) if idx < main_swing_index]
    if not candidates:
        return None
    idx, price = candidates[-1]
    lvl = PriceLevel(LevelType.SSL if direction == Direction.BULLISH else LevelType.BSL,
                      price, idx, candles[idx].time, label="IDM")
    mark_liquidity_swept([lvl], candles)
    return lvl


# ══════════════════════════════════════════════════════════════════
# 6. PREMIUM / DISCOUNT / EQUILIBRIUM / DEALING RANGE / DEALING CURVE
# ══════════════════════════════════════════════════════════════════

def get_dealing_range(swing_df: pd.DataFrame, candles: list[Candle]) -> dict:
    """
    Dealing Range (đã verify qua search): vùng giữa swing high & swing low GẦN NHẤT
    đang "active" — container cho mọi phân tích Premium/Discount/Equilibrium.
    """
    highs, lows = get_swing_series(swing_df)
    if not highs or not lows:
        return {"high": None, "low": None, "equilibrium": None}
    high_idx, high_price = highs[-1]
    low_idx, low_price = lows[-1]
    return {
        "high": high_price, "low": low_price,
        "high_index": high_idx, "low_index": low_idx,
        "equilibrium": (high_price + low_price) / 2,
    }


def classify_premium_discount(price: float, dealing_range: dict) -> str:
    """PREMIUM / DISCOUNT / EQUILIBRIUM (chính xác tại eq) theo Dealing Range hiện tại."""
    if dealing_range["high"] is None:
        return "UNKNOWN"
    eq = dealing_range["equilibrium"]
    if price > eq:
        return "PREMIUM"
    if price < eq:
        return "DISCOUNT"
    return "EQUILIBRIUM"


def get_dealing_curve_position(price: float, dealing_range: dict) -> float | None:
    """
    Dealing Curve (đã verify qua search — là PHIÊN BẢN LIÊN TỤC của Premium/Discount):
    vị trí chuẩn hoá 0.0 (đáy dealing range) -> 1.0 (đỉnh dealing range), thay vì chỉ
    phân loại nhị phân Premium/Discount. 0.5 = Equilibrium chính xác.
    """
    if dealing_range["high"] is None or dealing_range["high"] == dealing_range["low"]:
        return None
    return (price - dealing_range["low"]) / (dealing_range["high"] - dealing_range["low"])


def classify_pd_box_zone(box: PDBox, dealing_range: dict) -> str:
    """Phân loại 1 PDBox nằm Premium/Discount/Mixed so với Dealing Range (áp dụng LỚP 1 Ultra Confluence)."""
    if dealing_range["high"] is None:
        return "UNKNOWN"
    eq = dealing_range["equilibrium"]
    if box.top < eq:
        return "DISCOUNT"
    if box.bottom > eq:
        return "PREMIUM"
    return "MIXED"


def calculate_ote_zone(swing_low: float, swing_high: float, direction: Direction) -> dict:
    """OTE / Fibonacci 62-79% (Chương IV mục 3 bước 3)."""
    rng = swing_high - swing_low
    if direction == Direction.BULLISH:
        return {"zone_top": swing_high - rng * 0.618, "zone_bottom": swing_high - rng * 0.790}
    return {"zone_top": swing_low + rng * 0.790, "zone_bottom": swing_low + rng * 0.618}


def is_price_in_ote(price: float, ote_zone: dict) -> bool:
    return ote_zone["zone_bottom"] <= price <= ote_zone["zone_top"]
