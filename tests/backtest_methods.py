"""Walk-Forward Backtesting Engine for 5 Trading Methods.

Runs historical simulation without look-ahead bias for:
1. INDICATOR
2. SMC
3. ICT
4. PRICE_ACTION
5. ULTRA_CONFLUENCE
"""

from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd

# Add dashboard directory to import path
sys.path.insert(0, str(Path(__file__).parent.parent / "dashboard"))

from detectors import df_to_candles, find_swing_points
from signal_engines import run_signal_engine, SignalResult


def generate_synthetic_ohlcv(bars: int = 1500, symbol: str = "XAUUSDm") -> Dict[str, pd.DataFrame]:
    """Generates synthetic multi-timeframe candle data for validation."""
    np.random.seed(42)
    base_price = 2700.0
    returns = np.random.normal(0.0001, 0.002, bars)
    price_path = base_price * np.exp(np.cumsum(returns))

    dates_m15 = pd.date_range(end=pd.Timestamp.now(), periods=bars, freq="15min")

    df_m15 = pd.DataFrame({
        "time": dates_m15,
        "open": price_path - np.random.uniform(0.1, 0.5, bars),
        "high": price_path + np.random.uniform(0.5, 2.0, bars),
        "low": price_path - np.random.uniform(0.5, 2.0, bars),
        "close": price_path,
        "tick_volume": np.random.randint(100, 1000, bars),
    })

    # Resample H1 and H4
    df_h1 = df_m15.resample("1h", on="time").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"
    }).dropna().reset_index()

    df_h4 = df_m15.resample("4h", on="time").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"
    }).dropna().reset_index()

    df_m5 = df_m15.copy()
    df_m1 = df_m15.copy()

    return {"M1": df_m1, "M5": df_m5, "M15": df_m15, "H1": df_h1, "H4": df_h4}


def run_backtest_for_method(mtf_data: Dict[str, pd.DataFrame], method: str) -> Dict[str, Any]:
    df_m15 = mtf_data["M15"]
    n_bars = len(df_m15)
    step = 5
    start_bar = 200

    trades = []
    equity = 10000.0
    peak_equity = 10000.0
    max_drawdown_pct = 0.0

    wins, losses, breakevens = 0, 0, 0
    total_pnl = 0.0

    for i in range(start_bar, n_bars, step):
        sub_mtf = {
            "M1": mtf_data["M1"].iloc[:i],
            "M5": mtf_data["M5"].iloc[:i],
            "M15": mtf_data["M15"].iloc[:i],
            "H1": mtf_data["H1"].iloc[:max(10, i // 4)],
            "H4": mtf_data["H4"].iloc[:max(10, i // 16)],
        }

        res: SignalResult = run_signal_engine("XAUUSDm", sub_mtf, broker_utc_offset_hours=2.0, method=method)

        if res.status == "APPROVED" and res.entry_price and res.sl and res.tp:
            # Simulate trade outcome over next 10 candles
            future_candles = df_m15.iloc[i:min(i + 15, n_bars)]
            pnl = 0.0
            outcome = "LOSS"

            for _, row in future_candles.iterrows():
                high, low = row["high"], row["low"]
                if res.direction == "BUY":
                    if high >= res.tp:
                        pnl = (res.tp - res.entry_price) * 100.0
                        outcome = "WIN"
                        break
                    elif low <= res.sl:
                        pnl = (res.sl - res.entry_price) * 100.0
                        outcome = "LOSS"
                        break
                elif res.direction == "SELL":
                    if low <= res.tp:
                        pnl = (res.entry_price - res.tp) * 100.0
                        outcome = "WIN"
                        break
                    elif high >= res.sl:
                        pnl = (res.entry_price - res.sl) * 100.0
                        outcome = "LOSS"
                        break

            if outcome == "WIN":
                wins += 1
            else:
                losses += 1

            total_pnl += pnl
            equity += pnl
            if equity > peak_equity:
                peak_equity = equity
            dd = (peak_equity - equity) / peak_equity * 100.0
            if dd > max_drawdown_pct:
                max_drawdown_pct = dd

            trades.append({"bar": i, "method": method, "direction": res.direction, "pnl": pnl, "outcome": outcome})

    total_trades = wins + losses
    winrate = round((wins / total_trades) * 100.0, 2) if total_trades > 0 else 0.0
    profit_factor = round(max(0.0, total_pnl) / max(1.0, abs(total_pnl)), 2)

    return {
        "method": method,
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "winrate_pct": winrate,
        "total_pnl": round(total_pnl, 2),
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "profit_factor": profit_factor,
    }


def main():
    print("=" * 60)
    print("      ATE MULTI-METHOD BACKTEST ENGINE (WALK-FORWARD)")
    print("=" * 60)

    data = generate_synthetic_ohlcv(bars=1500)
    methods = ["INDICATOR", "SMC", "ICT", "PRICE_ACTION", "SNIPER", "ULTRA_CONFLUENCE"]

    results = []
    for m in methods:
        res = run_backtest_for_method(data, m)
        results.append(res)
        print(f"[{res['method']:<18}] Trades: {res['total_trades']:<4} | Winrate: {res['winrate_pct']:<5}% | PnL: ${res['total_pnl']:<8} | MaxDD: {res['max_drawdown_pct']}%")

    print("=" * 60)
    print("Backtest simulation completed successfully.")


if __name__ == "__main__":
    main()
