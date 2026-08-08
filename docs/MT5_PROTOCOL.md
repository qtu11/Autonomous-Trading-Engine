# QuantAI - Giao Thức Thực Thi MT5 / MQL5 (Execution Protocol Specification)

## Tổng Quan

`QuantAI_XAUUSD.mq5` là **đơn vị thực thi lệnh duy nhất (Sole Broker Execution Authority)** của toàn hệ thống. Không có bất kỳ script Python, trình duyệt hay process bên thứ ba nào gọi lệnh giao dịch trực tiếp lên broker. Tất cả lệnh đều phải đi qua: backend tạo Command → EA claim → EA verify → EA thực thi → EA gửi receipt.

## Giao Thức Liên Lạc

### 1. Telemetry & Heartbeat (`POST /api/telemetry`)
- Gửi mỗi 1 giây qua MQL5 `WebRequest()`.
- Header: `Authorization: Bearer <QUANTAI_BRIDGE_TOKEN>`.
- Payload: balance, equity, margin, margin_free, profit, số vị thế mở, ask, bid.
- Backend cập nhật `_LAST_EA_HEARTBEAT`; EA mất heartbeat > 10s bị đánh dấu `STALE`.

### 2. Command Claim (`POST /api/v1/bridge/commands/claim`)
- EA poll mỗi 1 giây.
- Submit định danh: executor_id, symbol, magic, account_login, account_server, broker_company, trade_mode.
- Nếu backend trả `"status": "CLAIMED"` → EA parse command fields (`action`, `volume`, `stop_loss`, `take_profit`, `reason`).
- Nếu không có lệnh → trả `"status": "EMPTY"`.

### 3. Local Guard Verification (Fail-Closed tại EA)
Trước khi gọi `CTrade`, EA kiểm tra toàn bộ:
1. `InpExecutionEnabled == true` và môi trường demo được phép (`IsAuthorizedDemoEnvironment()`).
2. Symbol == `InpSymbol` ("XAUUSDm") và Magic == `InpMagicNumber` (888999).
3. Spread hiện tại <= `InpMaxSpread` (0.50).
4. `MatchingPositionCount() < InpMaxPositions` (mặc định 1).
5. Khoảng cách SL/TP >= `SYMBOL_TRADE_STOPS_LEVEL` và `SYMBOL_TRADE_FREEZE_LEVEL`.
6. Volume nằm trong giới hạn broker: `SYMBOL_VOLUME_MIN`, `SYMBOL_VOLUME_MAX`, `SYMBOL_VOLUME_STEP`.

Bất kỳ guard nào fail → gửi receipt `REJECTED` kèm lý do.

### 4. Thực Thi Lệnh qua MQL5 CTrade
- `m_trade.SetTypeFillingBySymbol(InpSymbol)` - tự động chọn mode khớp lệnh broker (`ORDER_FILLING_FOK` / `ORDER_FILLING_IOC` / `ORDER_FILLING_RETURN`).
- `m_trade.Buy()` / `m_trade.Sell()` / `PositionModify()` / `PositionClose()` / `OrderDelete()`.
- Giá được chuẩn hóa về `_Digits`.

### 5. Execution Receipt Posting (`POST /api/v1/bridge/commands/{command_id}/receipt`)
- Receipt ID duy nhất: `{InpExecutorId}-{TimeLocal()}-{GetTickCount()}`.
- Status: `EXECUTED` (retcode 10009 TRADE_RETCODE_DONE / 10008 DONE_PARTIAL), `REJECTED`, hoặc `FAILED`.
- Payload: retcode, result_message, order_ticket, deal_ticket.

## Bảng Tổng Hợp Các Endpoint EA Dùng

| Endpoint | Method | Tần suất | Mục đích |
|----------|--------|----------|----------|
| `/api/telemetry` | POST | 1s | Gửi trạng thái tài khoản + heartbeat |
| `/api/v1/bridge/commands/claim` | POST | 1s | Nhận lệnh PENDING cần thực thi |
| `/api/v1/bridge/commands/{id}/receipt` | POST | sự kiện | Báo kết quả thực thi |
| `/api/v1/bridge/calendar` | POST | sự kiện | Đẩy lịch kinh tế từ MT5 |

## Điều Kiện An Toàn Bắt Buộc

1. **Không bao giờ đặt `InpExecutionEnabled=false` khi có lệnh đang chạy**: EA sẽ bỏ qua claim.
2. **Chỉ vận hành LIVE sau khi**: bật `QUANTAI_LIVE_ARMED=true`, `ENABLE_TRADING=true`, `KILL_SWITCH=false`, và tài khoản broker là REAL mode.
3. **Account login/server phải khớp**: EA xác minh từng lệnh với account hiện tại, chống lệnh nhầm tài khoản.
4. **Spread/Stops level**: mọi điều kiện broker phải được kiểm tra lại tại thời điểm thực thi (không chỉ tin tưởng backend).

---

*Tài liệu thuộc dự án QuantAI - Nguyễn Quang Tú (QTusdev) | MIT License.*