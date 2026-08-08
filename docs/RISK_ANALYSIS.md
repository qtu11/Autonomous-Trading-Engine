# QuantAI - Phân Tích Rủi Ro & Mô Hình Mối Đe Dọa (Risk Analysis & Threat Modeling)

## Ma Trận Rủi Ro Toàn Diện

| ID | Vùng lỗ hổng | Tác động tiềm ẩn | Ưu tiên | Cơ chế giảm thiểu / Interlock |
|----|--------------|------------------|---------|-------------------------------|
| R-001 | Đặt lệnh LIVE trái phép | Tổn thất tài chính | CRITICAL | Arming đa lớp: mode `LIVE` khóa sau `QUANTAI_LIVE_ARMED=true`, `ENABLE_TRADING=true`, `KILL_SWITCH=false`, và tài khoản thực `ACCOUNT_TRADE_MODE_REAL`. |
| R-002 | Lệnh trùng (Race condition) | Lộ double lot | CRITICAL | Sổ cái SQLite atomic + `idempotency_key` UNIQUE + lease claim đơn + `receipt_id` UNIQUE. |
| R-003 | EA mất kết nối / network drop | Telemetry stale / vị thế không xử lý | HIGH | Watchdog kết nối trong EA (backoff); backend đánh dấu EA `STALE` nếu không heartbeat 10s. |
| R-004 | Spread giãn cực mạnh khi tin tức | Slippage / Fill xấu | HIGH | RiskGate từ chối khi `ask - bid > max_spread` (XAUUSD cap 0.50); EA xác minh lại spread trước `CTrade`. |
| R-005 | Flash crash / vượt drawdown | Mất vốn nghiêm trọng | HIGH | RiskGate áp `max_daily_loss_fraction = 0.02` và ngưỡng free margin tối thiểu. |
| R-006 | Lộ token API trên browser | Rò rỉ credential | MEDIUM | Tách token: `QUANTAI_BRIDGE_TOKEN` (EA) và `QUANTAI_OPERATOR_TOKEN` (UI) chỉ ở backend, không trong `NEXT_PUBLIC_*`. |
| R-007 | Tick NaN/Inf | Crash / SL/TP sai | MEDIUM | `isfinite()` nghiêm ngặt ở Python RiskGate và MQL5 price normalization. |

## Chiến Lược Giảm Thiểu Theo Tầng (Defense in Depth)

```text
TẦNG 1: BACKEND
   - Multi-AI Decision Engine (Fail-closed, không lệnh khi AI lỗi)
   - RiskGate 15 điểm (equity, margin, spread, drawdown, position, volume)
TẦNG 2: LEDGER
   - Idempotency + Lease + TTL + Receipt (chống lệnh trùng)
TẦNG 3: EA LOCAL GUARD
   - Verify account login/server/symbol/magic/spread/stop level/volume
TẦNG 4: BROKER
   - SL/TP, Magic Number riêng, execution mode broker

TRẠNG THÁI VẬN HÀNH AN TOÀN: mode DEMO + demo_armed=true + kill_switch=false
```

## Quy Tắc Vận Hành An Toàn Bắt Buộc

1. **KHÔNG BAO GIỜ** bật LIVE trước khi hệ thống chạy DEMO ổn định ít nhất vài tuần.
2. **Luôn giữ** `KILL_SWITCH` dễ tiếp cận trên UI; tắt lập tức khi nghi ngờ.
3. **Xác minh** tài khoản broker (login/server) trước mỗi phiên giao dịch - EA sẽ từ chối nếu sai.
4. **Theo dõi** log `logs/quantai_YYYYMMDD.log` và trạng thái `STALE` của EA.
5. **Backup** file `quantai_commands.sqlite3` định kỳ (audit).

## Những Tình Huống Phải Dừng Bot Ngay

| Tình huống | Hành động |
|------------|-----------|
| Spread > 0.50 liên tục | Bật Kill Switch, kiểm tra thị trường |
| Equity giảm > 2% trong ngày | Tắt AI Auto Loop, rà soát RiskGate |
| Lệnh claim lặp (không receipt) | Kiểm tra EA heartbeat, DB |
| Tin tức đỏ sắp công bố | Tự động khóa lệnh (RiskGate) hoặc thủ công |
| Lỗi API AI liên tục | Kiểm tra failover chain, key |

---

*Tài liệu thuộc dự án QuantAI - Nguyễn Quang Tú (QTusdev) | MIT License.*