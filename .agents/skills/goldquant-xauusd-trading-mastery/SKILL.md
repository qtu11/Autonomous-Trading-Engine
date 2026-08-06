---
name: goldquant-xauusd-trading-mastery
description: Master quantitative trading framework, risk management rules, 1% lot sizing formulas, price execution protocols, order placement rules, and algorithmic trading guidelines for XAUUSD Gold trading.
---

# GoldQuant XAUUSD Master Trading & Quantitative Strategy Handbook

Tài liệu hướng dẫn và quy tắc giao dịch định lượng cao cấp (Master Quantitative Trading Framework) dành riêng cho **chủ tịch anh Tú** và **Bộ não AI Copilot (GoldQuant AI System)**.

---

## I. MỤC TIÊU VÀ NGUYÊN TẮC CỐT LÕI (CORE PRINCIPLES)

1. **Bảo toàn Vốn là Ưu tiên Số 1 (Capital Preservation First)**:
   - Không bao giờ đặt cược rủi ro vượt quá **1% tổng tài khoản (Balance)** cho một giao dịch đơn lẻ.
   - Luôn duy trì tỷ lệ **Risk / Reward (R:R) tối thiểu 1 : 2.0**.

2. **Giao dịch theo Tín hiệu AI & Mô hình Định lượng (Data-Driven & Quant-First)**:
   - Mọi quyết định vào lệnh (`BUY` / `SELL`) phải thỏa mãn ma trận hội tụ (Confluence Matrix) từ 3 chỉ báo kỹ thuật: **EMA Trend**, **RSI Momentum**, và **ATR Volatility**.
   - Tuyệt đối loại bỏ yếu tố cảm xúc (FOMO, Greed, Fear) khỏi hệ thống.

3. **Giao thức Thực thi Chuẩn Bloomberg Desk (Institutional Order Execution)**:
   - Lệnh được đẩy từ AI Engine qua REST API sang MQL5 EA Bridge (`QuantAI_XAUUSD.mq5`) với độ trễ thấp nhất.
   - Luôn tự động gắn **Stop Loss (SL)** và **Take Profit (TP)** ngay tại thời điểm mở lệnh.

---

## II. CẤU TRÚC BỘ TÀI LIỆU CHUYÊN SÂU (SKILL REFERENCES)

Bộ quy tắc đầy đủ được phân tách chi tiết trong các file tài liệu chuyên sâu tại thư mục `references/`:

1. **[Quản lý Rủi ro & Công thức Tính Lot](file:///.agents/skills/goldquant-xauusd-trading-mastery/references/risk_management_and_position_sizing.md)**:
   - Công thức toán học tính Lot chuẩn theo 1% Risk.
   - Quy tắc Kelly Criterion & Max Drawdown Limit (-3%).
   - Trailing Stop & Break-Even rules.

2. **[Quy tắc Đặt lệnh & Thực thi Giá](file:///.agents/skills/goldquant-xauusd-trading-mastery/references/order_execution_and_price_rules.md)**:
   - Các loại lệnh (Market Deal, Pending Limit, Stop Order).
   - Kiểm soát Spread & Slippage trên sàn Exness.
   - Quy tắc chốt lời từng phần (Partial TP) & Cắt lỗ khẩn cấp (Emergency Close).

3. **[Phân tích Kỹ thuật & Ma trận Tín hiệu](file:///.agents/skills/goldquant-xauusd-trading-mastery/references/technical_analysis_and_signal_matrix.md)**:
   - Xếp tầng EMA (EMA20 > EMA50 > EMA200).
   - RSI Momentum & Vùng ép giá Pivot Points (R1, R2, S1, S2).
   - ATR Volatility-Based SL/TP Buffer.

4. **[Quy trình AI Copilot & Giao thức MQL5](file:///.agents/skills/goldquant-xauusd-trading-mastery/references/algorithmic_copilot_protocol.md)**:
   - Luồng dữ liệu Telemetry 1s.
   - Giao thức REST API `/api/signal_command` & `/api/signal_ack`.
   - AI Confidence Scoring & Auto-Trade Control.

---

## III. HƯỚNG DẪN ÁP DỤNG TRONG THỰC THI (ACTIONABLE CHEATSHEET)

```
[BƯỚC 1: XÁC ĐỊNH XU HƯỚNG]
  ↳ Nến M15: EMA20 > EMA50 > EMA200 ──> Ưu tiên tín hiệu BUY

[BƯỚC 2: XÁC NHẬN ĐỘNG LỰC & BIẾN ĐỘNG]
  ↳ RSI(14) nằm trong khoảng 50.0 – 70.0
  ↳ ATR(14) >= 3.50 pips (thị trường đủ biến động)

[BƯỚC 3: TÍNH TOÁN KHỐI LƯỢNG LOT]
  ↳ Distance SL = ATR * 1.5
  ↳ Lot = (Balance * 0.01) / (Distance SL * 100)

[BƯỚC 4: THỰC THI LỆNH QUA AI COPILOT]
  ↳ Phát lệnh BUY 0.10 Lot kèm SL & TP 1:2.0
```
