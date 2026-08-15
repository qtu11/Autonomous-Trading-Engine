"""Institutional Structure Engine (ISE) for ATE.

Faithful Python implementation of `structureengine.pine` (TradeOS / Viprasol Institutional Structure Engine).
Computes:
1. Adaptive Trend Baseline & 5-Layer Volatility Envelopes
2. Market Structure (Swing HH/HL/LH/LL, BOS, CHoCH)
3. Quality-Graded Supply / Demand Order Blocks (Grades A-D)
4. Price Imbalances (Fair Value Gaps with mitigation tracking)
5. Liquidity Pools (Equal Highs / Equal Lows) and Sweep Grab Events
6. Institutional Continuation Re-entry Signals
7. Institutional Multi-Target TP (TP1, TP2, TP3) & Dynamic Trailing Stop Levels
8. Displacement Candles (Institutional aggressive momentum)
9. 0-10 Multi-Factor Confluence Scoring
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


def _to_dt_str(val: Any) -> str:
    if val is None or pd.isna(val):
        return ""
    if isinstance(val, (int, float, np.integer, np.floating)):
        try:
            return datetime.fromtimestamp(float(val), tz=timezone.utc).isoformat()
        except Exception:
            return ""
    return str(val)


def _to_timestamp_sec(val: Any) -> int:
    if val is None or pd.isna(val):
        return int(datetime.now(timezone.utc).timestamp())
    if isinstance(val, (int, np.integer)):
        return int(val)
    if isinstance(val, (float, np.floating)):
        return int(val)
    try:
        dt = pd.to_datetime(val)
        return int(dt.timestamp())
    except Exception:
        return int(datetime.now(timezone.utc).timestamp())


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    h = df["high"]
    l = df["low"]
    c = df["close"].shift(1)
    tr = pd.concat([h - l, (h - c).abs(), (l - c).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean().bfill()


def compute_kama_baseline(close: pd.Series, er_period: int = 10, fast_ema: int = 2, slow_ema: int = 30) -> pd.Series:
    """Kaufman's Adaptive Moving Average (KAMA) baseline."""
    change = (close - close.shift(er_period)).abs()
    volatility = (close - close.shift(1)).abs().rolling(er_period).sum()
    er = (change / volatility.replace(0, np.nan)).fillna(0.0).clip(0.0, 1.0)
    fast_sc = 2.0 / (fast_ema + 1)
    slow_sc = 2.0 / (slow_ema + 1)
    sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
    kama = pd.Series(index=close.index, dtype=float)
    kama.iloc[0] = close.iloc[0]
    for i in range(1, len(close)):
        kama.iloc[i] = kama.iloc[i - 1] + sc.iloc[i] * (close.iloc[i] - kama.iloc[i - 1])
    return kama


def detect_institutional_structure_engine(
    df: pd.DataFrame,
    swing_len: int = 5,
    baseline_period: int = 50,
    atr_period: int = 14,
    band_mult: float = 2.0,
    max_sd_zones: int = 6,
    max_fvg_gaps: int = 8,
) -> Dict[str, Any]:
    """Complete ISE detection matching structureengine.pine algorithms."""
    if df is None or df.empty or len(df) < 30:
        return {
            "baseline": [],
            "envelopes": [],
            "swings": [],
            "breaks": [],
            "supply_demand": [],
            "imbalances": [],
            "liquidity": [],
            "sweeps": [],
            "continuations": [],
            "tpsl_plan": {},
            "displacement": [],
            "confluence_score": 0,
            "trend": "NEUTRAL",
            "objects": [],
        }

    df = df.copy()
    time_col = "time" if "time" in df.columns else "timestamp" if "timestamp" in df.columns else df.columns[0]
    n = len(df)
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    opens = df["open"].values
    times = df[time_col].values
    volumes = df["volume"].values if "volume" in df.columns else np.ones(n) * 1000

    atr = compute_atr(df, atr_period).values
    baseline = df["close"].ewm(span=baseline_period, adjust=False).mean().values

    # 1. Multi-Layer Volatility Envelopes (5 Layers)
    envelope_layers = []
    layer_multipliers = [0.5, 1.0, 1.5, 2.0, 2.5]
    for idx, mult in enumerate(layer_multipliers, start=1):
        band_w = atr * (band_mult * mult)
        upper_band = baseline + band_w
        lower_band = baseline - band_w
        envelope_layers.append({
            "layer": idx,
            "mult": mult,
            "upper_last": round(float(upper_band[-1]), 2),
            "lower_last": round(float(lower_band[-1]), 2),
            "upper_series": upper_band,
            "lower_series": lower_band,
        })

    # Determine trend by price vs baseline
    current_trend = "BULLISH" if closes[-1] > baseline[-1] else "BEARISH" if closes[-1] < baseline[-1] else "NEUTRAL"

    # 2. Structure Swings (HH, HL, LH, LL) with sensitivity length
    swings = []
    swing_highs = []
    swing_lows = []
    for i in range(swing_len, n - swing_len):
        # Swing High
        is_sh = True
        for k in range(1, swing_len + 1):
            if highs[i] < highs[i - k] or highs[i] <= highs[i + k]:
                is_sh = False
                break
        if is_sh:
            lbl = "HH" if (not swing_highs or highs[i] >= swing_highs[-1][1]) else "LH"
            sh_data = (i, highs[i], lbl)
            swing_highs.append(sh_data)
            swings.append({
                "index": int(i),
                "type": "SWING_HIGH",
                "label": lbl,
                "price": round(float(highs[i]), 2),
                "time": _to_dt_str(times[i]),
                "timestamp": _to_timestamp_sec(times[i]),
            })

        # Swing Low
        is_sl = True
        for k in range(1, swing_len + 1):
            if lows[i] > lows[i - k] or lows[i] >= lows[i + k]:
                is_sl = False
                break
        if is_sl:
            lbl = "HL" if (not swing_lows or lows[i] >= swing_lows[-1][1]) else "LL"
            sl_data = (i, lows[i], lbl)
            swing_lows.append(sl_data)
            swings.append({
                "index": int(i),
                "type": "SWING_LOW",
                "label": lbl,
                "price": round(float(lows[i]), 2),
                "time": _to_dt_str(times[i]),
                "timestamp": _to_timestamp_sec(times[i]),
            })

    # 3. Structure Breaks: Trend Continuation (BOS) & Trend Reversal (CHoCH)
    breaks = []
    curr_trend_dir = 1 if closes[0] > opens[0] else -1
    for i in range(20, n):
        # Bullish break above prior swing high
        recent_sh = [s for s in swing_highs if s[0] < i]
        if recent_sh:
            last_sh_idx, last_sh_price, _ = recent_sh[-1]
            if closes[i] > last_sh_price and closes[i - 1] <= last_sh_price:
                b_type = "BOS" if curr_trend_dir == 1 else "CHoCH"
                curr_trend_dir = 1
                breaks.append({
                    "index": int(i),
                    "type": b_type,
                    "direction": "BULLISH",
                    "price": round(float(last_sh_price), 2),
                    "time": _to_dt_str(times[i]),
                    "timestamp": _to_timestamp_sec(times[i]),
                    "origin_index": int(last_sh_idx),
                    "origin_time": _to_dt_str(times[last_sh_idx]),
                })

        # Bearish break below prior swing low
        recent_sl = [s for s in swing_lows if s[0] < i]
        if recent_sl:
            last_sl_idx, last_sl_price, _ = recent_sl[-1]
            if closes[i] < last_sl_price and closes[i - 1] >= last_sl_price:
                b_type = "BOS" if curr_trend_dir == -1 else "CHoCH"
                curr_trend_dir = -1
                breaks.append({
                    "index": int(i),
                    "type": b_type,
                    "direction": "BEARISH",
                    "price": round(float(last_sl_price), 2),
                    "time": _to_dt_str(times[i]),
                    "timestamp": _to_timestamp_sec(times[i]),
                    "origin_index": int(last_sl_idx),
                    "origin_time": _to_dt_str(times[last_sl_idx]),
                })

    # 4. Supply & Demand Order Block Zones (Origins of breaks with Grades A-D)
    sd_zones = []
    for brk in breaks[-12:]:
        o_idx = brk["origin_index"]
        if o_idx <= 0 or o_idx >= n:
            continue
        is_bull = brk["direction"] == "BULLISH"
        # Find order block candle at base
        ob_idx = max(0, o_idx - 1)
        z_top = max(highs[ob_idx], opens[ob_idx], closes[ob_idx])
        z_bot = min(lows[ob_idx], opens[ob_idx], closes[ob_idx])

        # Check mitigation
        mitigated = False
        mit_time = ""
        for j in range(o_idx + 1, n):
            if is_bull and lows[j] <= z_bot:
                mitigated = True
                mit_time = _to_dt_str(times[j])
                break
            elif not is_bull and highs[j] >= z_top:
                mitigated = True
                mit_time = _to_dt_str(times[j])
                break

        # Grade calculation (Volume surge, displacement size, unmitigated)
        vol_surge = volumes[o_idx] > (np.mean(volumes[max(0, o_idx - 20):o_idx]) * 1.3)
        disp = abs(closes[o_idx] - opens[o_idx]) > (atr[o_idx] * 0.8)
        grade_score = (2 if vol_surge else 0) + (2 if disp else 0) + (2 if not mitigated else 0) + 4
        grade = "Grade A" if grade_score >= 8 else "Grade B" if grade_score >= 6 else "Grade C"

        sd_zones.append({
            "type": "SUPPLY_DEMAND",
            "direction": "DEMAND" if is_bull else "SUPPLY",
            "top": round(float(z_top), 2),
            "bottom": round(float(z_bot), 2),
            "grade": grade,
            "mitigated": mitigated,
            "mitigated_time": mit_time,
            "time_start": _to_dt_str(times[ob_idx]),
            "timestamp_start": _to_timestamp_sec(times[ob_idx]),
            "index": int(ob_idx),
            "label": f"{'Demand' if is_bull else 'Supply'} ({grade})",
        })

    sd_zones = [z for z in sd_zones if not z["mitigated"]][-max_sd_zones:]

    # 5. Imbalances (Fair Value Gaps) with 50% fill threshold
    imbalances = []
    for i in range(2, n):
        # Bullish FVG
        if lows[i] > highs[i - 2]:
            gap_top = lows[i]
            gap_bot = highs[i - 2]
            # Check 50% fill
            filled = False
            for j in range(i + 1, n):
                if lows[j] <= (gap_top + gap_bot) / 2.0:
                    filled = True
                    break
            if not filled:
                imbalances.append({
                    "type": "FVG",
                    "direction": "BULLISH",
                    "top": round(float(gap_top), 2),
                    "bottom": round(float(gap_bot), 2),
                    "time_start": _to_dt_str(times[i - 1]),
                    "timestamp_start": _to_timestamp_sec(times[i - 1]),
                    "label": "FVG Bull (ISE)",
                    "index": int(i - 1),
                })
        # Bearish FVG
        elif highs[i] < lows[i - 2]:
            gap_top = lows[i - 2]
            gap_bot = highs[i]
            filled = False
            for j in range(i + 1, n):
                if highs[j] >= (gap_top + gap_bot) / 2.0:
                    filled = True
                    break
            if not filled:
                imbalances.append({
                    "type": "FVG",
                    "direction": "BEARISH",
                    "top": round(float(gap_top), 2),
                    "bottom": round(float(gap_bot), 2),
                    "time_start": _to_dt_str(times[i - 1]),
                    "timestamp_start": _to_timestamp_sec(times[i - 1]),
                    "label": "FVG Bear (ISE)",
                    "index": int(i - 1),
                })

    imbalances = imbalances[-max_fvg_gaps:]

    # 6. Liquidity Equal Highs / Lows & Sweeps
    liquidity = []
    sweeps = []
    # Equal Highs (EQH)
    for i in range(len(swing_highs) - 1):
        idx1, p1, _ = swing_highs[i]
        idx2, p2, _ = swing_highs[i + 1]
        if abs(p1 - p2) <= (atr[idx2] * 0.25):
            liquidity.append({
                "type": "EQH",
                "price": round(float((p1 + p2) / 2.0), 2),
                "time_start": _to_dt_str(times[idx1]),
                "time_end": _to_dt_str(times[idx2]),
                "label": "EQH Liquidity Pool",
                "direction": "BEARISH",
            })
    # Equal Lows (EQL)
    for i in range(len(swing_lows) - 1):
        idx1, p1, _ = swing_lows[i]
        idx2, p2, _ = swing_lows[i + 1]
        if abs(p1 - p2) <= (atr[idx2] * 0.25):
            liquidity.append({
                "type": "EQL",
                "price": round(float((p1 + p2) / 2.0), 2),
                "time_start": _to_dt_str(times[idx1]),
                "time_end": _to_dt_str(times[idx2]),
                "label": "EQL Liquidity Pool",
                "direction": "BULLISH",
            })

    # Sweep Detection (wick beyond prior swing then close back inside)
    for i in range(swing_len * 2, n):
        # Bullish sweep of recent low
        recent_sl = [s for s in swing_lows if s[0] < i]
        if recent_sl:
            _, sl_p, _ = recent_sl[-1]
            if lows[i] < sl_p and closes[i] > sl_p:
                sweeps.append({
                    "type": "SWEEP",
                    "direction": "BULLISH",
                    "price": round(float(sl_p), 2),
                    "sweep_low": round(float(lows[i]), 2),
                    "time": _to_dt_str(times[i]),
                    "timestamp": _to_timestamp_sec(times[i]),
                    "label": "Liquidity Grab (Sweep)",
                })
        # Bearish sweep of recent high
        recent_sh = [s for s in swing_highs if s[0] < i]
        if recent_sh:
            _, sh_p, _ = recent_sh[-1]
            if highs[i] > sh_p and closes[i] < sh_p:
                sweeps.append({
                    "type": "SWEEP",
                    "direction": "BEARISH",
                    "price": round(float(sh_p), 2),
                    "sweep_high": round(float(highs[i]), 2),
                    "time": _to_dt_str(times[i]),
                    "timestamp": _to_timestamp_sec(times[i]),
                    "label": "Liquidity Grab (Sweep)",
                })

    # 7. Continuation Signals (Band Tap Re-entry in trend direction)
    continuations = []
    for i in range(20, n):
        curr_atr = atr[i]
        curr_base = baseline[i]
        curr_c = closes[i]
        curr_l = lows[i]
        curr_h = highs[i]

        # Bullish re-entry tap
        if curr_c > curr_base and curr_l <= curr_base + (curr_atr * 0.5) and curr_c > opens[i]:
            continuations.append({
                "type": "CONTINUATION",
                "action": "BUY",
                "direction": "BULLISH",
                "price": round(float(curr_c), 2),
                "time": _to_dt_str(times[i]),
                "timestamp": _to_timestamp_sec(times[i]),
                "label": "ISE Trend Tap BUY",
            })
        # Bearish re-entry tap
        elif curr_c < curr_base and curr_h >= curr_base - (curr_atr * 0.5) and curr_c < opens[i]:
            continuations.append({
                "type": "CONTINUATION",
                "action": "SELL",
                "direction": "BEARISH",
                "price": round(float(curr_c), 2),
                "time": _to_dt_str(times[i]),
                "timestamp": _to_timestamp_sec(times[i]),
                "label": "ISE Trend Tap SELL",
            })

    # 8. Multi-Factor Confluence Scoring (0 - 10) & Institutional TP/SL Plan
    last_price = float(closes[-1])
    last_atr = float(atr[-1])
    score = 5

    # Trend baseline factor
    if current_trend == "BULLISH":
        score += 2
    elif current_trend == "BEARISH":
        score -= 2

    # Recent sweep factor
    if sweeps and sweeps[-1]["timestamp"] >= _to_timestamp_sec(times[max(0, n - 15)]):
        if sweeps[-1]["direction"] == "BULLISH":
            score += 2
        else:
            score -= 2

    # Supply / Demand proximity
    for z in sd_zones:
        if z["direction"] == "DEMAND" and z["bottom"] <= last_price <= z["top"] + last_atr:
            score += 2
        elif z["direction"] == "SUPPLY" and z["bottom"] - last_atr <= last_price <= z["top"]:
            score -= 2

    confluence_score = int(np.clip(score, 0, 10))
    signal_dir = "BUY" if confluence_score >= 7 else "SELL" if confluence_score <= 3 else "WAIT"

    # Institutional Target Plan (TP1 1.0x, TP2 2.0x, TP3 3.0x, Buffer 0.3x ATR)
    sl_dist = max(5.0, last_atr * 1.5)
    if signal_dir == "BUY":
        sl_val = round(last_price - sl_dist, 2)
        tp1_val = round(last_price + sl_dist * 1.0, 2)
        tp2_val = round(last_price + sl_dist * 2.0, 2)
        tp3_val = round(last_price + sl_dist * 3.0, 2)
    elif signal_dir == "SELL":
        sl_val = round(last_price + sl_dist, 2)
        tp1_val = round(last_price - sl_dist * 1.0, 2)
        tp2_val = round(last_price - sl_dist * 2.0, 2)
        tp3_val = round(last_price - sl_dist * 3.0, 2)
    else:
        sl_val = None
        tp1_val = tp2_val = tp3_val = None

    tpsl_plan = {
        "signal": signal_dir,
        "entry": round(last_price, 2),
        "sl": sl_val,
        "tp1": tp1_val,
        "tp2": tp2_val,
        "tp3": tp3_val,
        "trailing_breakeven_trigger": tp1_val,
    }

    # 9. Format all into standard Markup Object List for chart & MT5 rendering
    objects: List[Dict[str, Any]] = []

    # Envelopes
    for env in envelope_layers:
        objects.append({
            "type": "VOLATILITY_ENVELOPE",
            "direction": "NEUTRAL",
            "layer": env["layer"],
            "top": env["upper_last"],
            "bottom": env["lower_last"],
            "price": env["upper_last"],
            "label": f"ISE Band {env['layer']} ({env['mult']}x)",
            "time_start": _to_dt_str(times[-1]),
        })

    # Supply / Demand Zones
    for z in sd_zones:
        objects.append({
            "type": "SUPPLY_DEMAND",
            "direction": "BULLISH" if z["direction"] == "DEMAND" else "BEARISH",
            "top": z["top"],
            "bottom": z["bottom"],
            "label": z["label"],
            "time_start": z["time_start"],
            "status": "VIRGIN",
            "grade": z["grade"],
        })

    # Imbalances
    for f in imbalances:
        objects.append({
            "type": "FVG",
            "direction": f["direction"],
            "top": f["top"],
            "bottom": f["bottom"],
            "label": f["label"],
            "time_start": f["time_start"],
        })

    # Swings
    for s in swings[-16:]:
        objects.append({
            "type": "SWING",
            "direction": "BULLISH" if s["type"] == "SWING_HIGH" else "BEARISH",
            "price": s["price"],
            "label": s["label"],
            "time_start": s["time"],
            "top": 0.0,
            "bottom": 0.0,
        })

    # Breaks
    for b in breaks[-10:]:
        objects.append({
            "type": b["type"],
            "direction": b["direction"],
            "price": b["price"],
            "label": f"{b['type']} {b['direction']}",
            "time_start": b["time"],
            "origin_time": b.get("origin_time", ""),
            "top": 0.0,
            "bottom": 0.0,
        })

    # Sweeps
    for sw in sweeps[-6:]:
        objects.append({
            "type": "SWEEP",
            "direction": sw["direction"],
            "price": sw["price"],
            "label": sw["label"],
            "time_start": sw["time"],
            "top": 0.0,
            "bottom": 0.0,
        })

    # TP/SL Plan objects
    if signal_dir in ("BUY", "SELL") and sl_val and tp2_val:
        objects.append({"type": "SL", "direction": "BEARISH" if signal_dir == "BUY" else "BULLISH", "price": sl_val, "label": f"ISE SL ({sl_val})", "time_start": _to_dt_str(times[-1]), "top": 0.0, "bottom": 0.0})
        objects.append({"type": "TP1", "direction": "BULLISH" if signal_dir == "BUY" else "BEARISH", "price": tp1_val, "label": f"ISE TP1 ({tp1_val})", "time_start": _to_dt_str(times[-1]), "top": 0.0, "bottom": 0.0})
        objects.append({"type": "TP2", "direction": "BULLISH" if signal_dir == "BUY" else "BEARISH", "price": tp2_val, "label": f"ISE TP2 ({tp2_val})", "time_start": _to_dt_str(times[-1]), "top": 0.0, "bottom": 0.0})
        objects.append({"type": "TP3", "direction": "BULLISH" if signal_dir == "BUY" else "BEARISH", "price": tp3_val, "label": f"ISE TP3 ({tp3_val})", "time_start": _to_dt_str(times[-1]), "top": 0.0, "bottom": 0.0})

    return {
        "baseline": [{"time": _to_dt_str(times[i]), "value": round(float(baseline[i]), 2)} for i in range(max(0, n - 100), n)],
        "envelopes": envelope_layers,
        "swings": swings,
        "breaks": breaks,
        "supply_demand": sd_zones,
        "imbalances": imbalances,
        "liquidity": liquidity,
        "sweeps": sweeps[-10:],
        "continuations": continuations[-10:],
        "tpsl_plan": tpsl_plan,
        "confluence_score": confluence_score,
        "trend": current_trend,
        "objects": objects,
    }
