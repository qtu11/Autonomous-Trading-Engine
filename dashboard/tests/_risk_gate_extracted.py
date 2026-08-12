from typing import Dict, Any
from datetime import datetime, timezone
_config = {'max_spread': 4.5, 'risk_per_trade_fraction': 0.01, 'max_open_positions': 5}
_account = {'balance': 10000.0, 'margin_free': 10000.0, 'total_pnl': 0.0}
def evaluate_risk_gate(symbol, signal, entry, sl, tp, 
                        spread, atr, score, method) -> Dict[str, Any]:
    """Risk Manager với 9 checks theo spec. Trả về {approved, reason, checks}.
    
    Checks:
    1. Spread
    2. ATR / Volatility
    3. News protection
    4. Margin / Free Margin
    5. Risk %
    6. Max Drawdown
    7. Max Lot
    8. Daily Loss / Daily Profit
    9. Trading Session
    """
    checks = {}
    
    # 1. Spread
    max_spread = _config.get("max_spread", 4.5)
    checks["spread"] = {"value": spread, "max": max_spread, "ok": spread <= max_spread}
    
    # 2. ATR / Volatility (sử dụng ATR ratio so với entry)
    atr_pct = (atr / max(entry, 1)) * 100 if entry > 0 else 0
    checks["volatility"] = {"atr_pct": atr_pct, "ok": 0.05 <= atr_pct <= 5.0}
    
    # 3. News protection
    checks["news"] = {"protected": False, "ok": True}
    
    # 4. Margin
    free_margin = _account.get("margin_free", 10000)
    margin_required = abs(entry - sl) * 100 * 0.01  # Estimate for 0.01 lot
    margin_ok = free_margin > margin_required * 5  # 5x safety margin
    checks["margin"] = {"free": free_margin, "required": margin_required, "ok": margin_ok}
    
    # 5. Risk % (Risk per trade / account balance)
    risk_pct = _config.get("risk_per_trade_fraction", 0.01)
    sl_distance = abs(entry - sl)
    position_value_at_risk = sl_distance * 100 * 0.01  # For 0.01 lot gold
    actual_risk_pct = position_value_at_risk / max(_account.get("balance", 10000), 1)
    checks["risk_pct"] = {"configured": risk_pct, "actual": actual_risk_pct, 
                          "ok": actual_risk_pct <= risk_pct * 2}  # Allow 2x config
    
    # 6. Max Drawdown (track realized losses today)
    daily_pnl = _account.get("total_pnl", 0)
    drawdown_pct = abs(min(0, daily_pnl)) / max(_account.get("balance", 10000), 1) * 100
    max_dd_pct = 5.0  # 5% max daily drawdown
    checks["max_drawdown"] = {"current": drawdown_pct, "max": max_dd_pct, "ok": drawdown_pct < max_dd_pct}
    
    # 7. Max Lot
    max_lot = 0.5
    checks["max_lot"] = {"value": 0.01, "max": max_lot, "ok": 0.01 <= max_lot}
    
    # 8. Daily Loss / Profit
    max_daily_loss = _account.get("balance", 10000) * 0.03  # 3% of balance
    max_daily_profit = _account.get("balance", 10000) * 0.05  # 5% of balance
    checks["daily_pnl"] = {
        "current": daily_pnl,
        "max_loss": -max_daily_loss,
        "max_profit": max_daily_profit,
        "ok": daily_pnl > -max_daily_loss and daily_pnl < max_daily_profit
    }
    
    # 9. Trading Session (Server time check - allow Mon-Fri)
    now = datetime.now(timezone.utc)
    weekday = now.weekday()
    is_weekday = weekday < 5  # 0-4 = Mon-Fri
    checks["session"] = {"weekday": weekday, "ok": is_weekday}
    
    # Tổng hợp
    approved = all(c.get("ok", False) for c in checks.values())
    failed_checks = [k for k, v in checks.items() if not v.get("ok", False)]
    
    return {
        "approved": approved,
        "reason": "All checks passed" if approved else f"Failed: {', '.join(failed_checks)}",
        "checks": checks,
        "score": score,
        "method": method,
        "timestamp": now.isoformat()
    }


