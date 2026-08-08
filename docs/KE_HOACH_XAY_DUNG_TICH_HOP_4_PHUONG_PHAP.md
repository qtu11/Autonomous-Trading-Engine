# Kế Hoạch Xây Dựng & Tích Hợp Hệ Thống Giao Dịch Đa Phương Pháp

> **Dự án**: Autonomous Trading Engine (ATE) - QuantAI
> **Tác giả / Lead Developer**: Nguyễn Quang Tú (QTusdev)
> **Trạng thái**: Phần lớn các hạng mục đã được triển khai trong mã nguồn hiện tại (xem `dashboard/`, `web/`, `MQL5/`). Tài liệu này giữ lại lịch sử kế hoạch & kiến trúc để tham chiếu và định hướng phát triển tiếp theo.
> **Giấy phép**: MIT License - [COPYRIGHT.md](./COPYRIGHT.md)

---

## 1. Tổng Quan Kế Hoạch

Mục tiêu: xây dựng và tích hợp **4 phương pháp giao dịch cốt lõi** (Indicator/SMA, SMC - Smart Money Concepts, ICT - Inner Circle Trader, Price Action) cùng **Ultra Confluence** (tổ hợp 5 lớp) vào một hệ thống ATE thống nhất, chạy song song trên nền FastAPI + Next.js + MQL5 EA.

### Các lưu ý quan trọng (User Review Required)

1. **Di trừ cơ sở dữ liệu SQLite** (`quantai_brain.sqlite3`): thêm cột `trading_method` vào `brain_decisions` và tái cấu trúc `strategy_stats` với Composite Primary Key `(strategy_version, trading_method)`. Có script backup tự động `.bak` trước khi thực hiện.
2. **Đồng bộ Key Name API**: `user_control_config.json` lưu `active_ai_model`, payload API frontend dùng `active_model` - cần Pydantic Validator alias song song 2 key name để tránh lệch dữ liệu.
3. **Tự động quy đổi Giờ Broker sang UTC+7**: mỗi lần server Exness đổi giờ theo DST (UTC+2/UTC+3), logic Killzone phải lấy dynamic offset từ `mt5.account_info()` / `mt5.terminal_info()` thay vì hardcode.

### Câu hỏi mở (Open Questions)

- **TTL lệnh Pending (Limit)**: với SMC/ICT đặt lệnh Limit tại OB/FVG, lệnh hết hạn sau bao lâu nếu giá không quay lại? (Đề xuất: 30 phút hoặc khi nến M15 tạo BOS mới).
- **Quản trị vốn (Risk Fraction)**: `risk_per_trade_fraction` mặc định 0.02 (2%) - với SMC/ICT râu nến SL ngắn nên giới hạn `max_volume` để bảo vệ tài khoản.

---

## 2. Kiến Trúc Kế Hoạch (Committee & Components)

### Component 1: Database & Infrastructure Migration (Tasks 1-30)
- [x] `dashboard/migrate_db.py`: script di trừ SQLite an toàn (backup `.bak` trước khi ALTER).
- [x] Thêm cột `trading_method TEXT DEFAULT 'INDICATOR'` cho `brain_decisions`.
- [x] Tái lập `strategy_stats` với Composite Primary Key `(strategy_version, trading_method)`.
- [x] `dashboard/brain.py`: `record_decision(...)` nhận `trading_method`, `_roll_strategy_stats()` thống kê Native theo từng phương pháp.
- [x] `dashboard/user_control_config.json`: mặc định `"trading_method": "ULTRA_CONFLUENCE"`.

### Component 2: Core Pipeline & Detectors (Tasks 31-80)
- [x] `docs/detectors.py`: Dataclass `Candle`, `PDArray`, Enum `PDArrayType` (9 loại: OB, FVG, BREAKER, MITIGATION, REJECTION, iFVG, LIQUIDITY, VOID, PROPULSION), `PDArrayDirection`.
- [x] `find_swing_points()` (Fractal 5 nến), `classify_trend_structure()`, `get_last_swing_points()`.
- [x] `detect_order_blocks()` kèm bộ lọc Valid OB (Displacement >= ATR x factor + FVG + Untested).
- [x] `detect_breaker_and_mitigation_blocks()` phân biệt dựa trên Liquidity Sweep trước phá vỡ.
- [x] `detect_fvg()` (BISI/SIBI), `detect_liquidity_sweep()` (BSL/SSL), `detect_equal_highs_lows()` (EQH/EQL tolerance 0.05%).
- [x] `get_killzone_status()` tự quy đổi giờ Broker sang UTC+4; Asian Rage, London KZ, NY KZ.
- [x] `calculate_ote_zone()` (Fibonacci 0.618-0.790) & Premium/Discount Equilibrium.

### Component 3: 5 Signal Engines Riêng Biệt (Tasks 81-120)
- [x] `docs/signal_engines.py`: `run_signal_engine(symbol, mtf_data, broker_utc_offset, method)`.
- [x] `_run_indicator_only()` - EMA20/50/200 + RSI + ATR (BUY khi Close > EMA20 > EMA50 > EMA200 và 50<=RSI<=70; SL=1.5*ATR; TP=3.0*ATR).
- [x] `_run_smc_only()` - Trend H1 Bias qua BOS, OB M15 tại Discount (BUY) / Premium (SELL), xác nhận CHoCH M15, Limit tại đỉnh OB.
- [x] `_run_ict_only()` - Killzone time (London/NY), Judas Swing sweep Asian Range, displacement+FVG M5, OTE 0.618-0.790, Limit tại CE.
- [x] `_run_price_action_only()` - Pinbar/Engulfing, Daily Pivot (PP/R1/S1), PDH/PDL, SL ngoài râu nến.
- [x] `_run_ultra_confluence()` - 5 lớp AND: HTF Bias (Premium/Discount H4/D1) + Time Filter (Killzone) + Liquidity Sweep + Structure Shift MSS/CHoCH + OTE Confluence - sắp xếp theo vòng Early Return.
- [x] Hàm xếp hạng chất lượng entry `score_smc_entry()`.

### Component 4: Risk Gate & Command Queue Protocol (Tasks 121-155)
- [x] `docs/risk_gate.py`: lot dynamic theo SL thực tế từng phương pháp, cap spread, Max Open Positions, Daily Loss Limit (tự khóa giao dịch nếu lỗ quá mức), Hedge Protection.
- [x] `docs/command_store.py`: thêm `trading_method` vào command PENDING; idempotency key; TTL ngắn (15-30 phút cho Limit orders); tự dọn lệnh hết TTL.
- [x] `server.py` tích hợp `run_signal_engine()` vào circus scan; API `POST /api/control-center/trading-method`; `trading_method` trong ai-config.

### Component 5: Frontend Next.js Dashboard (Tasks 156-180)
- [x] `web/lib/api.ts`: thêm `tradingMethod` interfaces & API client `updateTradingMethod()`.
- [x] `web/app/page.tsx`: vvv Selector phương pháp cạnh nút AutoTrade + selector model AI; style Bloomberg (nền tối, viền mỏng, JetBrains Mono); badge phương pháp trên chart.
- [x] Đa ngôn ngữ VI/EN.

### Component 6: AI System Prompt & Training Data (Tasks 181-200)
- [ ] (Có thể triển khai tiếp) `docs/TRAIN_AI_TRADING_METHODS.md`: training context 9 loại PD Arrays, quy tắc 1% vốn, nhận diện Inducement, JSON Output Schema, fallback về Rule-based Signal Engine.

### Component 7: Testing, Backtest & Deploy (Tasks 201-225)
- [ ] (Có thể triển khai tiếp) `tests/backtest_methods.py`: Walk-Forward không look-ahead bias, đo Winrate/PF/MaxDD/R-multiple; integration test Signal Engine → Risk Gate → SQLite → EA.

---

## 3. Verification Plan

### Automated Tests
```bash
python -m unittest discover -s tests -p "test_*.py"
flake8 dashboard/
cd web && npm run lint
```

### Manual Verification
- Chạy migration: `python dashboard/migrate_db.py` và kiểm qua `sqlite3`.
- Khởi động backend + kiểm tra API đổi method: `POST /api/control-center/trading-method`.
- Kiểm tra Next.js Dashboard hiển thị đúng Selector phương pháp và cập nhật realtime.

---

*Kế hoạch vẫn đang được duy trì bởi Đội ngũ QuantAI - Nguyễn Quang Tú (QTusdev) | MIT License.*