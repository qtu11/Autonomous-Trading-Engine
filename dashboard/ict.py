"""
Inner Circle Trader (ICT) — ghép các hàm lõi từ structure.py + thêm phần
RIÊNG của ICT: Killzones, Judas Swing, Silver Bullet, SMT Divergence,
Turtle Soup, AMD/PO3, Session & H/W/M High/Lows.

Hàm run_ict_analysis() ở cuối file là điểm vào chính — trả về TOÀN BỘ
khái niệm ICT mà người dùng liệt kê, đóng gói sẵn cho main.py serve qua API.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from datetime import time as dtime
try:
    from .models import Candle, df_to_candles, Direction, PDBox, BoxType, PriceLevel, LevelType
    from . import structure as S
except ImportError:
    from models import Candle, df_to_candles, Direction, PDBox, BoxType, PriceLevel, LevelType
    import structure as S


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════

def _obj(
    type_name: str,
    direction: str,
    candles: list[Candle],
    index: int,
    top: float = 0.0,
    bottom: float = 0.0,
    price: float = 0.0,
    label: str = "",
    status: str = "",
    **extra: any,
) -> dict[str, any]:
    c = candles[index]
    obj: dict[str, any] = {
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


# ══════════════════════════════════════════════════════════════════
# ICT SPECIFIC DETECTORS
# ══════════════════════════════════════════════════════════════════

def get_previous_day_high_low(
    df_d1: pd.DataFrame,
    broker_utc_offset_hours: float = 2.0,
) -> dict[str, any]:
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
) -> dict[str, any]:
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
    candles: list[Candle],
    df_d1: pd.DataFrame,
    broker_utc_offset_hours: float = 2.0,
    lookback: int = 3,
) -> list[dict[str, any]]:
    """(11) Turtle Soup: false breakout of PDH/PDL + fast reversal."""
    pdl_hld = get_previous_day_high_low(df_d1, broker_utc_offset_hours)
    if not pdl_hld:
        return []
    pdh, pdl = pdl_hld["pdh"], pdl_hld["pdl"]
    out: list[dict[str, any]] = []
    for i in range(max(1, len(candles) - lookback), len(candles)):
        c = candles[i]
        if c.high > pdh and c.close < pdh:
            out.append(_obj("TURTLE_SOUP", "BEARISH", candles, i, price=c.close,
                            label="TURTLE_SOUP_PDH", status="ACTIVE", level=round(pdh, 2)))
        if c.low < pdl and c.close > pdl:
            out.append(_obj("TURTLE_SOUP", "BULLISH", candles, i, price=c.close,
                            label="TURTLE_SOUP_PDL", status="ACTIVE", level=round(pdl, 2)))
    return out


def detect_judas_swing(
    candles: list[Candle],
    broker_utc_offset_hours: float = 2.0,
    lookback: int = 48,
) -> list[dict[str, any]]:
    """(12) Judas Swing: fake move inside London Kill Zone before the real reversal."""
    out: list[dict[str, any]] = []
    for i in range(max(1, len(candles) - lookback), len(candles)):
        c = candles[i]
        utc = c.time - pd.Timedelta(hours=broker_utc_offset_hours)
        t = utc.time()
        in_london = dtime(7, 0) <= t <= dtime(10, 0)
        if not in_london:
            continue
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
) -> list[dict[str, any]]:
    """(13) SMT Divergence: primary makes a new swing, correlation does not."""
    out: list[dict[str, any]] = []
    if df_correlation is None or df_correlation.empty:
        return out
    try:
        pri = df_primary.tail(lookback).reset_index(drop=True)
        cor = df_correlation.tail(lookback).reset_index(drop=True)
        pri_sw = S.find_swing_points(pri, swing_window)
        cor_sw = S.find_swing_points(cor, swing_window)
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
) -> list[dict[str, any]]:
    """(14)(15) AMD/PO3: Accumulation (range) -> Manipulation (sweep) -> Distribution."""
    df = df.copy()
    df["utc"] = df["time"] - pd.Timedelta(hours=broker_utc_offset_hours)
    df["utc_date"] = df["utc"].dt.date
    today = df["utc_date"].iloc[-1]
    seg = df[df["utc_date"] == today]
    if len(seg) < 10:
        return []

    out: list[dict[str, any]] = []
    n = len(seg)

    def _phase_bounds(a: int, b: int) -> tuple[float, float]:
        part = seg.iloc[a:b]
        return float(part["high"].max()), float(part["low"].min())

    h_acc, l_acc = _phase_bounds(0, max(1, n // 3))
    h_man, l_man = _phase_bounds(max(1, n // 3), max(2, 2 * n // 3))
    h_dis, l_dis = _phase_bounds(max(2, 2 * n // 3), n)

    acc_range = h_acc - l_acc
    dis_range = h_dis - l_dis
    if acc_range > 0 and dis_range > 1.5 * acc_range:
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
    candles: list[Candle],
    broker_utc_offset_hours: float = 2.0,
    lookback: int = 24,
) -> list[dict[str, any]]:
    """(17) Silver Bullet: 10-11am NY window entry setup (14-15 UTC)."""
    out: list[dict[str, any]] = []
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
) -> dict[str, any]:
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


# ══════════════════════════════════════════════════════════════════
# MAIN ENTRY: run_ict_analysis
# ══════════════════════════════════════════════════════════════════

def run_ict_analysis(
    mtf_data: dict[str, pd.DataFrame],
    broker_utc_offset_hours: float = 2.0,
) -> dict[str, any]:
    """
    Chạy toàn bộ quy trình phát hiện ICT cho biểu đồ.
    Trả về {"objects": [...], "counts": {...}} sẵn sàng để dùng ở server/chart_markup.
    """
    m15 = mtf_data.get("M15")
    d1 = mtf_data.get("D1")
    dxy = mtf_data.get("DXY")

    if m15 is None or m15.empty:
        return {"objects": [], "counts": {}}

    m15 = m15.copy()
    candles = df_to_candles(m15)
    objects = []
    counts = {}

    def _add(items: list[dict[str, any]], key: str) -> None:
        clean = [it for it in items if isinstance(it, dict) and it and it.get("type")]
        objects.extend(clean)
        counts[key] = len(clean)

    def _daily_level(obj: dict[str, any]) -> dict[str, any]:
        if not obj:
            return obj
        obj["index"] = 0
        obj["time_start"] = str(candles[0].time)
        obj["time_end"] = str(candles[-1].time)
        return obj

    # SMT Divergence
    if dxy is not None and not dxy.empty:
        _add(detect_smt_divergence(m15, dxy), "SMT_DIVERGENCE")

    # D1 Levels
    if d1 is not None and not d1.empty:
        pdhl = get_previous_day_high_low(d1, broker_utc_offset_hours)
        if pdhl:
            _add([_daily_level(pdhl)], "PDH_PDL")
        
        w_hl = get_weekly_monthly_high_low(d1, "WEEKLY")
        if w_hl:
            _add([_daily_level(w_hl)], "WEEKLY_HL")

        m_hl = get_weekly_monthly_high_low(d1, "MONTHLY")
        if m_hl:
            _add([_daily_level(m_hl)], "MONTHLY_HL")
            
        _add(detect_turtle_soup(candles, d1, broker_utc_offset_hours), "TURTLE_SOUP")

    # Session High/Low
    for session in ("LONDON", "NY", "ASIA"):
        shl = get_session_high_low(m15, session, broker_utc_offset_hours)
        if shl:
            _add([_daily_level(shl)], f"SESSION_{session}")

    # Session indicators
    _add(detect_judas_swing(candles, broker_utc_offset_hours), "JUDAS_SWING")
    _add(detect_silver_bullet(candles, broker_utc_offset_hours), "SILVER_BULLET")
    _add(detect_amd_po3(m15, broker_utc_offset_hours), "AMD")

    return {"objects": objects, "counts": counts}
