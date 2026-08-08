# QuantAI - Luồng Dữ Liệu & Vòng Đời Lệnh (Data Flow Specification)

## 1. Chu Trình Thực Thi Tổng Thể (End-to-End Execution Sequence)

```text
[ Market Tick / Candle ]
          |
          v
   (MT5 Terminal)
          |
          v  Python: mt5.copy_rates_from_pos() / symbol_info_tick()
   (FastAPI Backend)
          |
          +-- 1. Tính toán chỉ báo kỹ thuật (EMA20/50/200, RSI, ATR, MACD, Pivot)
          +-- 2. Đánh giá Pattern Engine (72+ mẫu hình) -> Strategy Proposal (BUY/SELL/NO_TRADE)
          +-- 3. AI Confluence & Multi-Source Fundamental Sentiment
          |
          v
    (RiskGate Engine)
          |
          +-- KHÔNG ĐẠT?  ---> Trả về REJECT_* kèm lý do, ghi log → kết thúc chu kỳ
          |
          v ĐẠT
   (CommandStore Ledger)
          |
          +-- Tạo command PENDING với idempotency key + TTL (10s)
          |
          v
    (MQL5 EA Bridge)  <-- WebRequest POST /api/v1/bridge/commands/claim (Bearer Token)
          |
          +-- Claim: chuyển trạng thái CLAIMED
          +-- Validate local guards (account login/server, spread, stop level, position limit)
          |
          +-- KHÔNG ĐẠT? --> Gửi receipt REJECTED
          |
          v ĐẠT
   (CTrade Execution)
          |
          +-- Mở / Sửa / Đóng lệnh trên broker (Buy/Sell/Modify/Close/Delete)
          |
          v
    (Receipt Posting) ---> POST /api/v1/bridge/commands/{id}/receipt
          |
          v
   (CommandStore Ledger)
          |
          +-- Cập nhật atomic: EXECUTED / FAILED / REJECTED kèm order_ticket & retcode
          |
          v  WebSocket push ~1s
   (Next.js Dashboard) ---> Render: positions, equity, logs, execution toast
```

## 2. Các Trạng Thái Lệnh (Command State Machine)

```text
                +-----------------+
                |  CREATED          |
                |  (PENDING)        |
                +--------+---------+
                         |
                         | claim (hết TTL 10s)
                         v
                +-----------------+
                |  CLAIMED          |
                +--------+---------+
                         |
        +----------------+----------------+
        |                |                |
        v                v                v
   +----------+    +----------+    +----------+
   |EXECUTED   |    |REJECTED   |    |  FAILED    |
   |(retcode   |    |(local     |    |(broker     |
   | 10009)    |    | guard)    |    | lỗi)       |
   +----------+    +----------+    +----------+
```

Sự kiện ghi vào bảng `execution_events`: `CREATED`, `CLAIMED`, `RECEIPT`, `EXPIRED` - giữ lịch sử bất biến (immutable audit).

## 3. Luồng Dữ Liệu Thời Gian Thực (Realtime Telemetry Flow)

1. **Heartbeat & Telemetry**:
   - EA gửi `POST /api/telemetry` mỗi 1 giây -> Backend cập nhật `_LAST_EA_HEARTBEAT`.
   - Nếu không có heartbeat trong 10 giây, EA bị đánh dấu `STALE`.
   - `_telemetry_broadcaster` push telemetry JSON qua WebSocket `ws://127.0.0.1:8005/ws/stream` cho các client mỗi 1 giây.

2. **Lịch Kinh Tế (Economic Calendar)**:
   - EA query `CalendarValueHistory` từ database tích hợp trong MT5.
   - Push các sự kiện USD macro qua `POST /api/v1/bridge/calendar`.
   - Backend cache trong 15 phút, phục vụ UI qua status endpoints.

## 4. Nguyên Tắc Đảm Bảo Toàn Vẹn

1. **Idempotency**: mỗi command có `idempotency_key` UNIQUE - nếu nó gửi cùng đề xuất 2 lần sẽ từ chối kẻ thứ 2 gây lệnh trùng.
2. **Lease**: command chỉ được claim EXACTLY bởi một EA trong thời gian lease (TTL); hết hạn tự `EXPIRED` và có thể claim lại.
3. **Receipt**: receipt_id duy nhất → mỗi kết quả lệnh chỉ ghi 1 lần.
4. **Atomic transitions**: mọi chuyển trạng thái dùng `BEGIN IMMEDIATE` (SQLite WAL).

## 5. Tương Tác Với AI Pipeline

Toàn bộ quyết định lệnh đi qua AI Pipeline `server.py -> call_multi_ai_completion`:

```text
Technical Layer (1) → Fundamental Layer (2) → Risk Sizing (3) → RiskGate (4) → CommandStore
```

Chi tiết xem [AI_PIPELINE.md](./AI_PIPELINE.md).

---

*Tài liệu thuộc dự án QuantAI - Nguyễn Quang Tú (QTusdev) | MIT License.*