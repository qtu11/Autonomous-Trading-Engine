"""
Smart Money Concepts (SMC) — ghép các hàm lõi từ structure.py + thêm phần
RIÊNG của SMC không có trong ICT: IFC (Institutional Funded Candle),
Trendline Liquidity, Supply/Demand Zone (khác OB ở cách hình thành),
Stop Hunt (alias có ngữ cảnh rộng hơn Liquidity Sweep thuần).

Hàm run_smc_analysis() ở cuối file là điểm vào chính — trả về TOÀN BỘ
khái niệm SMC mà người dùng liệt kê, đóng gói sẵn cho main.py serve qua API.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from typing import Any
import structure as S
from models import (
    BoxType,
    Candle,
    Direction,
    LevelType,
    PDBox,
    PriceLevel,
    StructureEvent,
    df_to_candles,
)


# ══════════════════════════════════════════════════════════════════
# SMC-ONLY: IFC (Institutional Funded Candle)
# ══════════════════════════════════════════════════════════════════

def detect_ifc(candles: list[Candle], liquidity_levels: list[PriceLevel]) -> list[PriceLevel]:
    """
    IFC (Chương III mục 3.4): sweep BSL/SSL đạt CHUẨN CAO — không chỉ rút lại vào range
    mà đóng cửa dứt khoát về phía đối diện điểm quét (close_position >= 0.7 hoặc <= 0.3)
    VÀ body_ratio đủ lớn (không phải doji yếu). Lọc ra subset "IFC-grade" từ liquidity_levels đã swept.
    """
    ifc_levels = []
    for lvl in liquidity_levels:
        if not lvl.swept or lvl.swept_at_index is None:
            continue
        c = candles[lvl.swept_at_index]
        if lvl.type == LevelType.SSL and c.close_position >= 0.7 and c.body_ratio >= 0.4 or lvl.type == LevelType.BSL and c.close_position <= 0.3 and c.body_ratio >= 0.4:
            ifc_levels.append(lvl)
    return ifc_levels


# ══════════════════════════════════════════════════════════════════
# SMC-ONLY: Trendline Liquidity
# ══════════════════════════════════════════════════════════════════

def detect_trendline_liquidity(swing_df: pd.DataFrame, candles: list[Candle]) -> list[PriceLevel]:
    """
    Trendline Liquidity (TLL): fit trendlines through swing points,
    and identify them as liquidity zones.
    """
    from price_action import detect_trendlines
    lines = detect_trendlines(swing_df)
    levels = []
    n = len(candles)
    for key, line in lines.items():
        if line is None:
            continue
        slope, intercept = line["slope"], line["intercept"]
        current_level = slope * (n - 1) + intercept
        lvl_type = LevelType.SSL if key == "support_trendline" else LevelType.BSL
        idx = line["point_indices"][-1]
        levels.append(PriceLevel(lvl_type, current_level, idx, candles[idx].time, label="TLL"))
    return levels


# ══════════════════════════════════════════════════════════════════
# SMC-ONLY: Supply/Demand Zone
# ══════════════════════════════════════════════════════════════════

def detect_supply_demand(
    candles: list[Candle],
    min_strength: float = 1.2,
) -> list[PDBox]:
    """Supply/Demand: base candle + strong move away (no BOS needed)."""
    zones: list[PDBox] = []
    n = len(candles)
    if n < 15:
        return zones
    atr = float(np.mean([c.range_size for c in candles[-14:]])) + 1e-9

    for i in range(1, n - 1):
        base, move = candles[i - 1], candles[i]
        if move.body_size <= min_strength * atr:
            continue
        if move.is_bullish and base.is_bearish:
            zones.append(PDBox(BoxType.REJECTION_BLOCK, Direction.BULLISH, base.high, base.low, i - 1, base.time, meta={"label": "DEMAND"}))
        if move.is_bearish and base.is_bullish:
            zones.append(PDBox(BoxType.REJECTION_BLOCK, Direction.BEARISH, base.high, base.low, i - 1, base.time, meta={"label": "SUPPLY"}))
    return zones[-6:]


# ══════════════════════════════════════════════════════════════════
# SMC-ONLY: Unicorn & BPR & Volume Imbalance & Liquidity Void
# ══════════════════════════════════════════════════════════════════

def detect_unicorn(
    order_blocks: list[PDBox],
    breaker_blocks: list[PDBox],
    candles: list[Candle],
    overlap_pct: float = 0.6,
) -> list[PDBox]:
    """SMC (Unicorn): OB overlapping a Breaker Block at the same zone."""
    out: list[PDBox] = []
    for ob in order_blocks:
        for bb in breaker_blocks:
            overlap = ob.overlaps(bb)
            if overlap is None:
                continue
            top, bottom = overlap
            span = min(ob.top - ob.bottom, bb.top - bb.bottom) or 1e-9
            if (top - bottom) / span >= overlap_pct:
                later = max(ob.start_index, bb.start_index)
                out.append(PDBox(BoxType.BREAKER_BLOCK, bb.direction, top, bottom, later, candles[later].time,
                                  meta={"label": "UNICORN", "origin_ob_index": ob.start_index, "origin_bb_index": bb.start_index}))
    return out


# ══════════════════════════════════════════════════════════════════
# MAIN ENTRY: run_smc_analysis
# ══════════════════════════════════════════════════════════════════

def run_smc_analysis(mtf_data: dict[str, pd.DataFrame], broker_utc_offset_hours: float = 2.0) -> dict[str, Any]:
    """
    Chạy toàn bộ quy trình phát hiện SMC cho biểu đồ M15 (Primary).
    Trả về {"objects": [...], "counts": {...}} sẵn sàng để dùng ở server/chart_markup.
    """
    m15 = mtf_data.get("M15")
    if m15 is None or m15.empty:
        return {"objects": [], "counts": {}}

    m15 = m15.copy()
    candles = df_to_candles(m15)
    swing_df = S.find_swing_points(m15, window=2)

    # 1. Trend & Events
    events = S.detect_structure_events(candles, swing_df)
    trend = S.classify_trend_structure(swing_df)

    # 2. Equal Highs / Equal Lows (Liquidity Pools)
    eqh_eql = S.detect_equal_highs_lows(swing_df, candles)
    liquidity_levels = S.build_liquidity_levels(swing_df, candles)
    S.mark_liquidity_swept(liquidity_levels, candles)

    # 3. Order Blocks & Breakers/Mitigations
    high, low, close = m15["high"], m15["low"], m15["close"]
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr_series = tr.rolling(14).mean()

    obs = S.detect_order_blocks(candles, swing_df, atr_series=atr_series)
    S.mark_boxes_mitigated(obs, candles)
    breakers = S.detect_breaker_and_mitigation_blocks(obs, candles, liquidity_levels)
    rejections = S.detect_rejection_blocks(swing_df, candles)

    # 4. FVG & Inversion FVG
    fvgs = S.detect_fvg(candles)
    inversions = S.detect_inversion_fvg(fvgs, candles)

    # 5. SMC Specfic
    ifc = detect_ifc(candles, liquidity_levels)
    tll = detect_trendline_liquidity(swing_df, candles)
    sup_dem = detect_supply_demand(candles)
    vol_imbalance = S.detect_volume_imbalance(candles)
    voids = S.detect_liquidity_void(candles)

    # 6. Dealing Range & Curve
    dr = S.get_dealing_range(swing_df, candles)
    bpr = S.detect_bpr(fvgs)
    unicorn = detect_unicorn(obs, breakers, candles)

    # Convert objects to API format
    objects = []
    counts = {}

    def _add_level(lvl: PriceLevel, type_name: str, label_override: str | None = None):
        key = type_name
        counts[key] = counts.get(key, 0) + 1
        objects.append({
            "type": type_name,
            "direction": "BULLISH" if lvl.type in (LevelType.SSL, LevelType.EQL, LevelType.SUPPORT) else "BEARISH",
            "top": round(lvl.price, 2),
            "bottom": round(lvl.price, 2),
            "price": round(lvl.price, 2),
            "time_start": str(lvl.formed_at_time),
            "time_end": "",
            "index": lvl.formed_at_index,
            "label": label_override or lvl.label or lvl.type.name,
            "status": "SWEPT" if lvl.swept else "ACTIVE"
        })

    def _add_box(box: PDBox, type_name: str):
        key = type_name
        counts[key] = counts.get(key, 0) + 1
        objects.append({
            "type": type_name,
            "direction": box.direction.value,
            "top": round(box.top, 2),
            "bottom": round(box.bottom, 2),
            "price": round(box.mid, 2),
            "time_start": str(box.start_time),
            "time_end": "",
            "index": box.start_index,
            "label": box.meta.get("label", box.type.name),
            "status": "MITIGATED" if box.mitigated else "ACTIVE"
        })

    # Add all SMC concepts
    for lvl in eqh_eql:
        _add_level(lvl, "EQUAL_HL")
    for lvl in liquidity_levels:
        _add_level(lvl, "LIQUIDITY_POOL")
    for lvl in ifc:
        _add_level(lvl, "IFC")
    for lvl in tll:
        _add_level(lvl, "TLL")
    
    for box in obs:
        _add_box(box, "OB")
    for box in breakers:
        _add_box(box, "BREAKER")
    for box in rejections:
        _add_box(box, "REJECTION")
    for box in fvgs:
        _add_box(box, "FVG")
    for box in inversions:
        _add_box(box, "iFVG")
    for box in sup_dem:
        _add_box(box, "SUPPLY_DEMAND")
    for box in vol_imbalance:
        _add_box(box, "VOLUME_IMBALANCE")
    for box in voids:
        _add_box(box, "VOID")
    for box in bpr:
        _add_box(box, "BPR")
    for box in unicorn:
        _add_box(box, "UNICORN")

    # Add Dealing Range
    if dr.get("high") is not None:
        counts["DEALING_RANGE"] = 1
        objects.append({
            "type": "DEALING_RANGE",
            "direction": "NEUTRAL",
            "top": round(dr["high"], 2),
            "bottom": round(dr["low"], 2),
            "price": round(dr["equilibrium"], 2),
            "time_start": str(candles[dr["low_index"]].time if dr["low_index"] < dr["high_index"] else candles[dr["high_index"]].time),
            "time_end": "",
            "index": min(dr["high_index"], dr["low_index"]),
            "label": "DEALING_RANGE",
            "status": "ACTIVE"
        })

    return {"objects": objects, "counts": counts}
