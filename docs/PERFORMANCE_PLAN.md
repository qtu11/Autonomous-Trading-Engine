# QuantAI - Kế Hoạch Tối Ưu Hiệu Năng (Performance Optimization Plan)

## Mục Tiêu Độ Trễ & Thông Lượng

| Chỉ số | Mục tiêu |
|--------|----------|
| Tick Ingestion -> Quyết định AI | < 15ms |
| FastAPI Command Issuance | < 5ms |
| MQL5 EA Poll Cycle | 1000ms (timer 1s) |
| WebSocket Broadcast Cadence | 1000ms |
| Next.js Rendering | 60 FPS SVG chart, không block main thread |
| Server -> EA command propagation | <= 1s (trong TTL 10s) |

## Chiến Lược Tối Ưu Backend (Python/FastAPI)

1. **SQLite WAL Mode**: đọc không cạnh tranh với ghi; mọi ghi nằm trong `BEGIN IMMEDIATE`.
2. **In-Memory Caching**: chỉ báo & telemetry tính 1 lần / tick rồi broadcast WebSocket, tránh lặp truy vấn DB/MT5.
3. **AsyncIO Non-blocking I/O**: background tasks (broadcast & decision loop) trong lifespan.
4. **Multi-AI fast path**: miễn phí chạy Zen Free; tránh retry kéo dài bằng cooldown 300s mỗi model.
5. **Đo lường**: log JSON kèm timestamp mỗi sự kiện để truy vết nếu vượt ngưỡng.

## Chiến Lược Tối Ưu Frontend (Next.js)

1. **WebSocket Telemetry**: thay HTTP polling 1s bằng 1 kết nối WS liên tục.
2. **SVG Chart nhẹ**: component canvas tùy chỉnh, xử lý tới 2000 cây nến, zoom bằng wheel + drag pan.
3. **React `memo` & `useCallback`**: ngăn re-render không cần thiết các panel Control Center & status.
4. **Lazy loading**: component nặng (chart, backup) chỉ tải khi cần.

## Giám Sát Hiệu Năng

| Metric | Nguồn | Cảnh báo |
|--------|-------|----------|
| EA heartbeat age | `/api/telemetry` | > 10s -> STALE |
| Command pending age | SQLite | > TTL -> EXPIRED |
| AI call duration | Log JSON | > 10s -> cảnh báo |
| WebSocket lag | `/ws/stream` | > 1.5s -> cảnh báo |
| MT5 connection | `symbol_info_tick` | fail -> cảnh báo |

---

*Tài liệu thuộc dự án QuantAI - Nguyễn Quang Tú (QTusdev) | MIT License.*