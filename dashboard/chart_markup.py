"""Chart Markup Builder for Autonomous Trading Engine (ATE).

AI Engine computes ICT / SMC / Price Action structures (Order Blocks, FVGs,
BOS/CHoCH, swing labels HH/HL/LH/LL, trendlines, OTE, Premium/Discount, Asian
Range, Liquidity Sweeps, Killzones) and serializes them into a JSON "markup"
contract. The MQL5 execution bridge (ATE_XAUUSD.mq5) only RENDERS these objects
on the chart; every decision lives here, server-side.

Markup object contract (all price/times in broker terms, index is the candle
offset from the newest candle, 0 = latest):
    {"type": "OB"|"FVG"|"BREAKER"|"REJECTION"|"MITIGATION"|"iFVG"|"LIQUIDITY"|"SWING"|"TRENDLINE"|"BOS"|"CHoCH"|"OTE"|"PD"|"ASIAN"|"KILLZONE"|"SIGNAL",
     "direction": "BULLISH"|"BEARISH"|"NEUTRAL",
     "top": price, "bottom": price, "time_start": ISO, "time_end": ISO,
     "index": int (candle offset of formation), "price": float (anchor for lines/arrows),
     "label": "HH"|"HL"|"LH"|"LL"|..., "touches": int, "status": "VIRGIN"|"PARTIAL"|...,
     "ce": float, "confluence": bool, "strength": float}
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
from aether_smc import build_aether_flow_payload
from advanced_detectors import build_advanced_markup
from detectors import (
    calculate_ote_zone,
    detect_bos_choch,
    detect_breaker_and_mitigation_blocks,
    detect_fvg,
    detect_liquidity_sweep,
    detect_market_structure,
    detect_order_blocks,
    detect_rejection_blocks,
    detect_trendlines,
    df_to_candles,
    find_swing_points,
    get_asian_range,
    get_fvg_fill_state,
    get_killzone_status,
    get_last_swing_points,
    get_premium_discount_zone,
    link_fvg_to_order_blocks,
    mark_ob_mitigated,
)
from method_overlays import (
    METHOD_OBJECT_GROUPS,
    compute_confluence_score,
    compute_ict_overlay,
    compute_pa_overlay,
    compute_smc_overlay,
    compute_sniper_overlay,
    compute_structure_engine_overlay,
)


def _dt(ts: pd.Timestamp) -> str:
    if ts is None:
        return ""
    return str(ts)


def _safe_time(df, idx, col='time'):
    try:
        i = int(idx)
        if 0 <= i < len(df):
            return _dt(df.iloc[i][col])
        if len(df) > 0:
            return _dt(df.iloc[-1][col])
    except Exception:
        pass
    return ""


def _time_col(df: pd.DataFrame) -> str:
    return 'time' if 'time' in df.columns else 'timestamp' if 'timestamp' in df.columns else 'time'


def _norm_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize a candle frame: canonical `time` column (datetime) + volume
    alias so every detector can rely on one naming convention. The MT5 bridge
    returns `timestamp`, stub data uses `timestamp` too, and unit tests use
    `time` — this unifies all three."""
    df = df.copy()
    tc = _time_col(df)
    if tc not in df.columns:
        return df  # no usable time column — leave as-is, detectors will skip it
    if tc != "time":
        df = df.rename(columns={tc: "time"})
    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    df = df.dropna(subset=["time"])
    if "volume" not in df.columns:
        for alias in ("tick_volume", "real_volume"):
            if alias in df.columns:
                df["volume"] = df[alias]
                break
    return df


# ── Trading-method → allowed markup object types ─────────────────────────────
# NOTE: The authoritative per-method filter lives in method_overlays.
# METHOD_OBJECT_GROUPS (kept in sync with the user's concept checklist). This
# legacy map is retained for documentation/back-compat only and is no longer
# applied during markup building (it disagreed with the overlay groups and
# silently dropped valid objects like SUPPORT/RESISTANCE/CHANNEL for PA).
METHOD_ALLOWED_TYPES: dict[str, set | None] = {
    "PRICE_ACTION": {
        "SWING", "TRENDLINE", "SR", "CHANNEL", "RANGE",
        "BREAKOUT", "PULLBACK", "RETEST", "FAKE_BREAKOUT", "PATTERN",
    },
    "SMC": {
        "SWING", "BOS", "CHoCH", "MSS", "LIQUIDITY", "LIQUIDITY_POOL",
        "OB", "BREAKER", "MITIGATION", "REJECTION", "FVG", "iFVG",
        "PD", "DEALING_RANGE", "DEALING_CURVE", "INDUCEMENT", "SUPPLY_DEMAND",
        "VOLUME_IMBALANCE", "VOID",
    },
    "ICT": {
        "SWING", "BOS", "CHoCH", "MSS", "LIQUIDITY", "LIQUIDITY_POOL",
        "OB", "BREAKER", "MITIGATION", "REJECTION", "FVG", "iFVG",
        "PD", "DEALING_RANGE", "DEALING_CURVE", "INDUCEMENT", "SUPPLY_DEMAND",
        "VOLUME_IMBALANCE", "VOID", "BPR", "UNICORN", "OTE", "ASIAN",
        "KILLZONE", "TURTLE_SOUP", "JUDAS_SWING", "SMT_DIVERGENCE",
        "SILVER_BULLET", "AMD", "SESSION_HL", "PDH_PDL", "WEEKLY_MONTHLY_HL",
    },
    "SNIPER": {
        "EMA", "EMA_RIBBON", "VWAP", "ADX", "MACD_LINE", "RSI_LEVEL",
        "SNIPER_SIGNAL", "SNIPER_SL",
        "SNIPER_TP1", "SNIPER_TP2", "SNIPER_TP3", "SNIPER_TP4", "SNIPER_TP5",
        "SNIPER_SCORE", "SNIPER_DASH",
        "SWING", "BOS", "CHoCH",
    },
    "ULTRA_CONFLUENCE": None,  # everything
    "INDICATOR": set(),        # indicators only — no markup objects
}


def _zone(
    type_name: str,
    direction: str,
    top: float,
    bottom: float,
    formed_at: pd.Timestamp,
    index: int | None = None,
    **extra: Any,
) -> dict[str, Any]:
    obj: dict[str, Any] = {
        "type": type_name,
        "direction": direction,
        "top": round(float(top), 2),
        "bottom": round(float(bottom), 2),
        "time_start": _dt(formed_at),
        "time_end": "",
        "index": int(index) if index is not None else 0,
    }
    obj.update(extra)
    return obj


def build_chart_markup(
    symbol: str,
    mtf_data: dict[str, pd.DataFrame],
    broker_utc_offset_hours: float = 2.0,
    method: str = "ULTRA_CONFLUENCE",
    primary_tf: str = "M15",
) -> dict[str, Any]:
    """Tính toàn bộ cấu trúc ICT/SMC/PA từ dữ liệu đa khung thời gian.

    Trả về dict chuẩn: {"symbol", "method", "generated_at", "objects": [...]}.
    `primary_tf` chọn khung giờ dùng để phân tích cấu trúc (mặc định M15).
    Nếu thiếu khung giờ yêu cầu, tự rơi vào khung giờ đầu tiên có dữ liệu —
    nên markup hiển thị được trên MỌI timeframe, không chỉ M15.
    Chỉ dùng dữ liệu có sẵn; nếu thiếu khung giờ, bỏ qua nhóm tương ứng.
    """
    objects: list[dict[str, Any]] = []
    method_upper = method.upper()
    if method_upper in ("PA", "PRICE_ACTION"):
        method_upper = "PRICE_ACTION"
        include_pa, include_smc, include_ict = True, False, False
    elif method_upper in ("ISE", "STRUCTURE", "STRUCTURE_ENGINE"):
        method_upper = "STRUCTURE_ENGINE"
        include_pa, include_smc, include_ict = False, False, False
    elif method_upper == "SNIPER":
        include_pa, include_smc, include_ict = False, False, False
    elif method_upper == "SMC":
        include_pa, include_smc, include_ict = False, True, False
    elif method_upper == "ICT":
        include_pa, include_smc, include_ict = False, True, True
    elif method_upper in ("ULTRA", "ULTRA_CONFLUENCE"):
        method_upper = "ULTRA_CONFLUENCE"
        include_pa = include_smc = include_ict = True
    elif method_upper == "INDICATOR":
        include_pa = include_smc = include_ict = False

    # Normalize every provided frame once (canonical `time` column).
    mtf_data = {k: _norm_df(v) for k, v in mtf_data.items() if v is not None and not v.empty}

    # Pick the analysis frame: the requested primary TF, else any available one.
    m15 = mtf_data.get(primary_tf)
    if m15 is None or m15.empty:
        m15 = next((v for v in mtf_data.values() if not v.empty), None)
    if m15 is None:
        return {"symbol": symbol, "method": method_upper, "generated_at": datetime.now(timezone.utc).isoformat(), "objects": []}

    m15 = m15.copy()
    # Cap the detection window so huge frames (e.g. 72k M1 bars) stay fast.
    if len(m15) > 2000:
        m15 = m15.tail(2000)
        # BUG FIX (CRITICAL - web chart 500): sau tail(), index vẫn là label gốc
        # (vd 38000..39999) nhưng mọi detector + chart_markup dùng .iloc[vị trí]
        # và int(idx) — label 38000+ với df 2000 dòng -> "single positional indexer
        # is out-of-bounds" IndexError trên /api/market M1/M5. Reset index để
        # label == vị trí 0..n-1, nhất quán với mọi nhánh.
        m15 = m15.reset_index(drop=True)
    time_col = 'time'
    m15_candles = df_to_candles(m15)
    m15_swings = find_swing_points(m15, window=2)
    last_candle = m15_candles[-1]

    # 1. Swing structure labels (HH/HL/LH/LL) — Price Action + SMC + ICT
    struct = detect_market_structure(m15, window=2, n=6)
    for entry in struct["labels"]:
        objects.append({
            "type": "SWING",
            "direction": "BULLISH" if entry["type"] == "SWING_HIGH" else "BEARISH",
            "label": entry["label"],
            "price": round(float(entry["price"]), 2),
            "index": int(entry["index"]),
            "time_start": _safe_time(m15, entry["index"], time_col),
            "top": 0.0,
            "bottom": 0.0,
        })

    # 2. Order Blocks + Breaker/Mitigation blocks
    atr_series = (m15["high"] - m15["low"]).rolling(14).mean()
    obs = detect_order_blocks(m15_candles, m15_swings, atr_series=atr_series)
    mark_ob_mitigated(obs, m15_candles)
    fvgs = detect_fvg(m15_candles)
    link_fvg_to_order_blocks(obs, fvgs)

    for ob in obs[-24:]:
        objects.append(_zone(
            ob.type.value, ob.direction.value, ob.top, ob.bottom, ob.formed_at_time, ob.formed_at_index,
            status="MITIGATED" if ob.mitigated else "VIRGIN",
            ce=round(ob.ce, 2) if ob.ce else None,
            confluence=ob.has_fvg_confluence,
            strength=round(ob.strength_score, 2),
        ))

    for extra in detect_breaker_and_mitigation_blocks(obs, m15_candles)[-12:]:
        objects.append(_zone(
            extra.type.value, extra.direction.value, extra.top, extra.bottom, extra.formed_at_time, extra.formed_at_index,
            status="ACTIVE",
        ))

    # 3. FVGs with fill status (cap for readability; full list feeds BPR/OTE)
    for fvg in fvgs[-24:]:
        objects.append(_zone(
            fvg.type.value, fvg.direction.value, fvg.top, fvg.bottom, fvg.formed_at_time, fvg.formed_at_index,
            status=get_fvg_fill_state(fvg, m15_candles),
            ce=round(fvg.ce, 2) if fvg.ce else None,
        ))

    # 4. Rejection blocks
    for rb in detect_rejection_blocks(m15_candles, m15_swings)[-16:]:
        objects.append(_zone(
            rb.type.value, rb.direction.value, rb.top, rb.bottom, rb.formed_at_time, rb.formed_at_index,
            status="ACTIVE",
        ))

    # 5. Liquidity sweep (last candle)
    sweep = detect_liquidity_sweep(m15_candles, m15_swings, len(m15_candles) - 1)
    if sweep:
        objects.append({
            "type": "LIQUIDITY",
            "direction": "BULLISH" if sweep == "BULLISH_SWEEP" else "BEARISH",
            "label": sweep,
            "price": round(float(last_candle.close), 2),
            "index": len(m15_candles) - 1,
            "time_start": _dt(last_candle.time),
            "top": 0.0,
            "bottom": 0.0,
        })

    # 6. BOS / CHoCH / MSS (most recent confirmed event over the last few
    # candles — previously it only checked the very last bar, so markers were
    # almost never shown)
    bos_choch = {}
    for probe in range(len(m15_candles) - 1, max(-1, len(m15_candles) - 7), -1):
        evt = detect_bos_choch(m15_candles, m15_swings, probe)
        if evt:
            # MSS = CHoCH followed by a 2nd close beyond the broken level
            if evt["kind"] == "CHoCH" and probe - 1 >= 0:
                if (evt["direction"] == "BULLISH" and m15_candles[probe - 1].close > evt["break_price"]) or \
                   (evt["direction"] == "BEARISH" and m15_candles[probe - 1].close < evt["break_price"]):
                    evt["kind"] = "MSS"
            bos_choch = evt
            break
    if bos_choch:
        objects.append({
            "type": bos_choch["kind"],
            "direction": bos_choch["direction"],
            "label": f"{bos_choch['kind']}_{bos_choch['direction']}",
            "price": round(float(bos_choch["break_price"]), 2),
            "index": int(bos_choch["index"]),
            "time_start": _safe_time(m15, bos_choch["index"], time_col),
            "top": 0.0,
            "bottom": 0.0,
        })

    # 7. Trendlines (support/resistance)
    for tl in detect_trendlines(m15_candles, m15_swings, atr_series=atr_series):
        objects.append({
            "type": "TRENDLINE",
            "direction": "NEUTRAL",
            "label": tl["kind"],
            "top": round(float(tl["price1"]), 2),
            "bottom": round(float(tl["price2"]), 2),
            "index": 0,
            "time_start": _dt(tl["time1"]),
            "time_end": _dt(tl["time2"]),
            "touches": int(tl["touches"]),
            "slope": round(float(tl["slope"]), 6),
        })

    # 8. HTF Premium/Discount + OTE (from H1 when available)
    h1 = mtf_data.get("H1")
    if h1 is not None and not h1.empty and len(h1) >= 20:
        h1_swings = find_swing_points(h1.copy(), window=3)
        last_htf = get_last_swing_points(h1_swings, n=2)
        if last_htf["swing_highs"] and last_htf["swing_lows"]:
            h_high = last_htf["swing_highs"][-1]["high"]
            h_low = last_htf["swing_lows"][-1]["low"]
            pd_zone = get_premium_discount_zone(float(h_low), float(h_high))
            objects.append({
                "type": "PD",
                "direction": "NEUTRAL",
                "label": "PREMIUM",
                "top": float(pd_zone["swing_high"]),
                "bottom": float(pd_zone["fib_50"]),
                "index": 0,
                "time_start": _dt(h1.iloc[-1]["time"]),
            })
            objects.append({
                "type": "PD",
                "direction": "NEUTRAL",
                "label": "DISCOUNT",
                "top": float(pd_zone["fib_50"]),
                "bottom": float(pd_zone["swing_low"]),
                "index": 0,
                "time_start": _dt(h1.iloc[-1]["time"]),
            })
            # OTE zone from last H1 swing range
            m5_highs = [c.high for c in m15_candles[-15:]]
            m5_lows = [c.low for c in m15_candles[-15:]]
            swing_h, swing_l = max(m5_highs), min(m5_lows)
            ote_buy = calculate_ote_zone(float(swing_l), float(swing_h), "BUY")
            ote_sell = calculate_ote_zone(float(swing_l), float(swing_h), "SELL")
            objects.append(_zone("OTE", "BULLISH", ote_buy["zone_top"], ote_buy["zone_bottom"], m15.iloc[-1][time_col], len(m15_candles) - 1))
            objects.append(_zone("OTE", "BEARISH", ote_sell["zone_top"], ote_sell["zone_bottom"], m15.iloc[-1][time_col], len(m15_candles) - 1))

    # 9. Asian Range (ICT)
    asian = get_asian_range(m15, broker_utc_offset_hours)
    if asian["asian_high"] is not None and asian["asian_low"] is not None:
        objects.append(_zone("ASIAN", "NEUTRAL", asian["asian_high"], asian["asian_low"], m15.iloc[-1][time_col], len(m15_candles) - 1))

    # 10. Killzone status (ICT)
    kz = get_killzone_status(m15.iloc[-1][time_col], broker_utc_offset_hours)
    objects.append({
        "type": "KILLZONE",
        "direction": "NEUTRAL",
        "label": "KILLZONE",
        "top": 0.0,
        "bottom": 0.0,
        "index": 0,
        "time_start": _dt(m15.iloc[-1][time_col]),
        "is_london": bool(kz["is_london_kz"]),
        "is_ny": bool(kz["is_ny_kz"]),
        "is_asian": bool(kz["is_asian_range"]),
    })

    # 11. Advanced detectors: Price Action patterns, S/R, Channel, Range,
    #     Breakout/Pullback/Retest/FakeBreakout, Supply/Demand, Volume Imbalance,
    #     Liquidity Void, Inducement, MSS, Liquidity Pools, Dealing Range, BPR,
    #     Unicorn, Turtle Soup, Judas Swing, Silver Bullet, AMD/PO3, Session HL,
    #     PDH/PDL, Weekly/Monthly HL. Merged after the core ICT/SMC objects.
    advanced = build_advanced_markup(
        mtf_data,
        broker_utc_offset_hours=broker_utc_offset_hours,
        include_pa=include_pa,
        include_smc=include_smc,
        include_ict=include_ict,
        primary_tf=primary_tf,
    )
    objects.extend(advanced["objects"])

    # 12. Per-method overlays — Sniper / SMC / ICT / Price Action. Each method
    # exposes its own object types; ULTRA_CONFLUENCE merges all four.
    method_specific_objects: list[dict[str, Any]] = []
    if method_upper in ("SNIPER", "ULTRA_CONFLUENCE"):
        method_specific_objects.extend(compute_sniper_overlay(
            symbol, m15, mtf_data.get("M5"), broker_utc_offset_hours=broker_utc_offset_hours,
        ))
    if method_upper in ("SMC", "ICT", "ULTRA_CONFLUENCE"):
        method_specific_objects.extend(compute_smc_overlay(m15))
    if method_upper in ("ICT", "ULTRA_CONFLUENCE"):
        method_specific_objects.extend(compute_ict_overlay(
            m15, broker_utc_offset_hours=broker_utc_offset_hours,
        ))
    if method_upper in ("PRICE_ACTION", "ULTRA_CONFLUENCE"):
        method_specific_objects.extend(compute_pa_overlay(m15))
    if method_upper in ("STRUCTURE_ENGINE", "ULTRA_CONFLUENCE"):
        method_specific_objects.extend(compute_structure_engine_overlay(mtf_data, primary_tf=primary_tf))

    # Filter by METHOD_OBJECT_GROUPS if method-specific (so e.g. SNIPER shows
    # sniper objects + a few core SMC confluence ones, but not all ICT zones).
    allowed_method_types = METHOD_OBJECT_GROUPS.get(method_upper)
    if method_upper == "INDICATOR":
        # BUG FIX: INDICATOR = chỉ hiện chỉ báo, KHÔNG vẽ markup & KHÔNG có
        # confluence vote. Trước đây METHOD_OBJECT_GROUPS thiếu key INDICATOR →
        # allowed_types=None → filter bị bỏ qua → chart hiện đầy OB/FVG/BOS/PD
        # và AI auto-trade có thể trade theo tín hiệu của phương pháp khác dù
        # user đang chọn INDICATOR.
        objects = []
        method_specific_objects = []
    elif allowed_method_types:
        objects = [obj for obj in objects if obj.get("type") in allowed_method_types]
        method_specific_objects = [obj for obj in method_specific_objects if obj.get("type") in allowed_method_types]

    objects.extend(method_specific_objects)

    # Cap to InpMarkupMaxObjects (default 120) but keep highest-priority types
    # (signals, score, TP/SL) at the end so they survive truncation.
    priority_types = {"SNIPER_SIGNAL", "SNIPER_SL", "SNIPER_TP1", "SNIPER_TP2",
                      "SNIPER_TP3", "SNIPER_TP4", "SNIPER_TP5", "SNIPER_SCORE",
                      "SNIPER_DASH", "JUDAS_SWING", "UNICORN", "PO3"}
    try:
        max_objects = 240  # server-side cap, frontend/EA can re-cap further
    except Exception:
        max_objects = 240
    if len(objects) > max_objects:
        priority = [o for o in objects if o.get("type") in priority_types]
        non_priority = [o for o in objects if o.get("type") not in priority_types]
        keep_count = max_objects - len(priority)
        if keep_count < 0:
            priority = priority[:max_objects]
            non_priority = []
        else:
            non_priority = non_priority[-keep_count:]
        objects = non_priority + priority

    # 13. Confluence score (signal action + confidence + RRR) for AI / auto-trade.
    last_close = float(m15["close"].iloc[-1])
    confluence = compute_confluence_score(objects, method_upper, last_close)

    # 14. Aether Flow Engine (TradingView Pine Script parity for LuxAlgo OB, FVG, Swings, UT Bot, Auto Fibs, Sniper)
    try:
        aether_payload = build_aether_flow_payload(
            symbol=symbol,
            df=m15,
            htf_h1_df=mtf_data.get("H1"),
            m5_df=mtf_data.get("M5"),
            method=method_upper,
        )
    except Exception:
        aether_payload = {
            "swings": [],
            "segments": [],
            "order_blocks": [],
            "fvgs": [],
            "auto_fibs": None,
            "ut_signals": [],
            "sniper": {},
            "indicators": {},
        }

    return {
        "symbol": symbol,
        "method": method_upper,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "objects": objects,
        "advanced_counts": advanced["counts"],
        "confluence": confluence,
        "aether": aether_payload,
    }
