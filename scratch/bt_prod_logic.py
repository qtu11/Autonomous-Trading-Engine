"""Backtest PRODUCTION logic (build_chart_markup + compute_confluence_score).

This is exactly what the AI auto-trade loop uses: markup -> confluence
{signal, score, entry, sl, tp, rrr} -> trade if signal in (BUY/SELL),
abs(score) >= 45, rrr >= 1.0 (same thresholds as _ai_trade_loop).

NOTE: synthetic XAUUSD data (random-walk with regimes). No real historical
data is available on this machine (bridge offline, EA cache only ~1.6h).
Treat numbers as relative comparison of methods, NOT live winrate proof.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "dashboard"))

from chart_markup import build_chart_markup
from method_overlays import compute_confluence_score


def gen_xauusd(bars: int = 12000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    base = 3370.0
    returns = []
    trend = 1
    for i in range(bars):
        if i > 0 and i % rng.randint(60, 140) == 0:
            trend *= -1
        if rng.random() < 0.7:
            r = trend * abs(rng.normal(0.0003, 0.0018))
        else:
            r = rng.normal(0.0, 0.001)
        returns.append(r)
    close = base * np.exp(np.cumsum(returns))
    n = bars
    opens = close * (1 + rng.normal(0, 0.0004, n))
    highs = np.maximum(opens, close) * (1 + np.abs(rng.normal(0, 0.0006, n)))
    lows = np.minimum(opens, close) * (1 - np.abs(rng.normal(0, 0.0006, n)))
    vols = rng.randint(100, 2000, n)
    t = pd.date_range(end=pd.Timestamp.now(tz="UTC"), periods=n, freq="15min")
    df = pd.DataFrame({
        "time": t, "open": opens, "high": highs, "low": lows,
        "close": close, "tick_volume": vols,
    })
    return df


def resample(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    out = df.set_index("time").resample(freq).agg(
        {"open": "first", "high": "max", "low": "min", "close": "last",
         "tick_volume": "sum"}
    ).dropna().reset_index()
    out = out.rename(columns={"index": "time"})
    return out


def simulate(df_m15: pd.DataFrame, mtf: Dict[str, pd.DataFrame], method: str,
             step: int = 16, start: int = 400, horizon: int = 24) -> Dict[str, Any]:
    """Walk forward: at bar i compute markup from data[:i], if signal -> simulate
    SL/TP hit over next `horizon` M15 bars. Reuses production thresholds."""
    wins = losses = breaks = 0
    pnl = 0.0
    trades = []
    eq = 10000.0
    peak = eq
    maxdd = 0.0
    COMMISSION = 7.0
    raw_signals = 0
    filtered_out = 0
    rr_samples = []
    for i in range(start, len(df_m15) - horizon, step):
        sub = {k: v.iloc[max(0, i - 600): i]
               for k, v in mtf.items()}
        sub["M15"] = df_m15.iloc[max(0, i - 600): i]
        try:
            mk = build_chart_markup("XAUUSDm", sub, broker_utc_offset_hours=2.0,
                                    method=method, primary_tf="M15")
            cf = mk.get("confluence") or {}
        except Exception:
            continue
        score = int(cf.get("score", 0) or 0)
        signal = cf.get("signal", "WAIT")
        entry = cf.get("entry")
        sl = cf.get("sl")
        tp = cf.get("tp")
        rrr = cf.get("rrr")
        if signal not in ("BUY", "SELL"):
            continue
        raw_signals += 1
        if rrr is not None and 0.5 < rrr < 20:
            rr_samples.append(rrr)
        if abs(score) < 45 or not sl or not tp:
            filtered_out += 1
            continue
        if rrr is None or rrr < 1.0:
            filtered_out += 1
            continue
        # spread ~ $0.4 on gold (400 points) — conservative
        spread_pts = 40.0 if "XAU" in "XAUUSDm" else 2.0
        # pyrefly: ignore [unsupported-operation]
        entry_eff = entry + spread_pts / 100.0 if signal == "BUY" else entry - spread_pts / 100.0
        fut = df_m15.iloc[i + 1: i + 1 + horizon]
        out = None
        for _, row in fut.iterrows():
            h, l = row["high"], row["low"]
            if signal == "BUY":
                if h >= tp:
                    out = (tp - entry_eff) * 100 - COMMISSION
                    break
                if l <= sl:
                    out = (sl - entry_eff) * 100 - COMMISSION
                    break
            else:
                if l <= tp:
                    out = (entry_eff - tp) * 100 - COMMISSION
                    break
                if h >= sl:
                    out = (entry_eff - sl) * 100 - COMMISSION
                    break
        if out is None:
            last = fut["close"].iloc[-1]
            out = ((last - entry_eff) * 100 - COMMISSION) if signal == "BUY" else (
                (entry_eff - last) * 100 - COMMISSION)
        if out > 0:
            wins += 1
        elif out < 0:
            losses += 1
        else:
            breaks += 1
        pnl += out
        eq += out
        peak = max(peak, eq)
        maxdd = max(maxdd, (peak - eq) / peak * 100 if peak > 0 else 0)
        trades.append({"i": i, "signal": signal, "score": score, "rrr": rrr, "pnl": round(out, 2)})
    tot = wins + losses + breaks
    wr = round(wins / tot * 100, 1) if tot else 0.0
    pf = round(max(pnl, 0.001) / max(abs(pnl), 0.001), 2) if pnl else 0.0
    return {"method": method, "trades": tot, "wins": wins, "losses": losses,
            "winrate": wr, "pnl": round(pnl, 2), "maxdd": round(maxdd, 2),
            # pyrefly: ignore [no-matching-overload]
            "pf": pf, "avg_rr": round(np.mean([t["rrr"] for t in trades]), 2) if trades else 0,
            "raw_signals": raw_signals, "filtered": filtered_out,
            "med_rr": round(float(np.median(rr_samples)), 2) if rr_samples else 0}


def main():
    print("=" * 78)
    print(" BACKTEST PRODUCTION LOGIC (build_chart_markup -> confluence -> trade)")
    print(" Synthetic XAUUSD M15 12000 bars (~125 days). Thresholds = production.")
    print("=" * 78)
    df15 = gen_xauusd(4000)
    mtf = {
        "M1": df15, "M5": resample(df15, "5min"),
        "M15": df15, "H1": resample(df15, "1h"), "H4": resample(df15, "4h"),
    }
    for m in ["PRICE_ACTION", "SMC", "ICT", "SNIPER", "ULTRA_CONFLUENCE"]:
        r = simulate(df15, mtf, m)
        print(f" [{m:<16}] RawSig:{r['raw_signals']:>4} Filtered:{r['filtered']:>3} "
              f"Trades:{r['trades']:>4} Win:{r['wins']:>3} Loss:{r['losses']:>3} "
              f"| WR:{r['winrate']:>5}% PnL:${r['pnl']:>8} PF:{r['pf']:>4} "
              f"MaxDD:{r['maxdd']:>5}% MedRR:{r['med_rr']}")


if __name__ == "__main__":
    main()
