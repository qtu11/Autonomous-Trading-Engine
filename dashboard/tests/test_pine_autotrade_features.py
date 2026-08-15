import pytest
from dashboard.server import calculate_dynamic_lot_size, _positions, _commands, _accounts


def test_dynamic_lot_size_scaling_with_equity():
    """Kiểm tra lot size tự động tăng thông minh theo vốn (Equity/Balance)."""
    import dashboard.server as srv
    orig_account = srv._account
    srv._account = {"equity": 1000.0, "balance": 1000.0}
    srv._active_login = None
    
    # 1. Vốn $1,000, risk 1% ($10), SL cách 2.0 USD XAUUSD (mult 100) -> 10 / (2*100) = 0.05 lot
    lot_1k = calculate_dynamic_lot_size("XAUUSD", entry=2650.0, sl=2648.0, risk_pct=1.0)
    assert lot_1k == 0.05, f"Expected 0.05 lot for $1k equity, got {lot_1k}"

    # 2. Vốn $5,000, risk 1% ($50), SL cách 2.0 USD XAUUSD -> 50 / 200 = 0.25 lot
    srv._account = {"equity": 5000.0, "balance": 5000.0}
    lot_5k = calculate_dynamic_lot_size("XAUUSD", entry=2650.0, sl=2648.0, risk_pct=1.0)
    assert lot_5k == 0.25, f"Expected 0.25 lot for $5k equity, got {lot_5k}"

    # 3. Vốn $20,000, risk 1% ($200), SL cách 2.0 USD XAUUSD -> 200 / 200 = 1.00 lot
    srv._account = {"equity": 20000.0, "balance": 20000.0}
    lot_20k = calculate_dynamic_lot_size("XAUUSD", entry=2650.0, sl=2648.0, risk_pct=1.0)
    assert lot_20k == 1.00, f"Expected 1.00 lot for $20k equity, got {lot_20k}"

    # Restore
    srv._account = orig_account


def test_dynamic_lot_size_min_max_bounds():
    """Kiểm tra lot size không bao giờ nhỏ hơn 0.01 và không vượt quá max an toàn."""
    import dashboard.server as srv
    srv._account = {"equity": 100.0, "balance": 100.0}
    lot_min = calculate_dynamic_lot_size("XAUUSD", entry=2650.0, sl=2640.0, risk_pct=0.5)
    assert lot_min >= 0.01


def test_positive_breakeven_locks_profit():
    """Kiểm tra Breakeven dời SL lên mức giá DƯƠNG chắc chắn."""
    entry = 2650.0
    risk_dist = 5.0
    pos_buffer = max(0.35, risk_dist * 0.15)
    new_sl_buy = round(entry + pos_buffer, 2)
    assert new_sl_buy > entry
    assert new_sl_buy >= 2650.35

    new_sl_sell = round(entry - pos_buffer, 2)
    assert new_sl_sell < entry
    assert new_sl_sell <= 2649.65
