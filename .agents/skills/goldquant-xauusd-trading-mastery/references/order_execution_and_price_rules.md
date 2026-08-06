# QUY TẮC ĐẶT LỆNH VÀ THỰC THI GIÁ (ORDER PLACEMENT & PRICE EXECUTION PROTOCOL)

Dành cho **Bộ não AI** & **Chủ tịch anh Tú**.

---

## I. QUY TẮC PHÂN LOẠI LỆNH VÀ THỰC THI (ORDER TYPES)

### 1. Lệnh Khớp Ngay (Market Order - Instant Deal)
- **Cơ chế**: Phát lệnh mua/bán tại giá Ask/Bid tốt nhất thị trường thời điểm hiện tại.
- **Ứng dụng**: Áp dụng khi AI Confidence Score $\ge 75\%$ và xu hướng nến bứt phá (Breakout confirmation).
- **Tham số quy chuẩn**:
  - `Symbol`: `XAUUSDm` (Sàn Exness)
  - `Deviation`: `20 points` (Cho phép chênh lệch giá tối đa $0.20)
  - `Filling Type`: `ORDER_FILLING_IOC` (Immediate Or Cancel)

### 2. Lệnh Chờ (Pending Orders - Limit & Stop)
- **BUY LIMIT**: Đặt tại các vùng hỗ trợ mạnh **Pivot Point (S1, S2)** hoặc khi giá điều chỉnh về `EMA20 / EMA50`.
- **SELL LIMIT**: Đặt tại các vùng kháng cự mạnh **Pivot Point (R1, R2)**.
- **BUY STOP / SELL STOP**: Đặt phía trên/dưới đỉnh/đáy nến M15 gần nhất để đón sóng tin tức mạnh (High Impact News like NFP, CPI, FOMC).

---

## II. QUY TẮC PHÂN TÍCH GIÁ VA CHÊNH LỆCH SPREAD / SLIPPAGE

1. **Kiểm soát Spread Sàn Exness**:
   - **Spread chuẩn Vàng (Standard Spread)**: Từ $0.15 - $0.35 ($15 - $35 / Lot).
   - **Cảnh báo Spread cao**: Nếu Spread $> 0.50$ (50 points) vào giờ giao phiên hoặc khi ra tin, AI Copilot **TẠM DỪNG MỞ LỆNH MỚI** để bảo vệ tài sản cho anh Tú.

2. **Quy tắc Trượt giá (Slippage Filter)**:
   - Nếu chênh lệch giữa giá yêu cầu mở lệnh và giá khớp thực tế lớn hơn $0.30$, lệnh sẽ bị hủy bỏ tự động bởi MQL5 Protocol Bridge.

---

## III. CHỐT LỜI TỪNG PHẦN VÀ THOÁT LỆNH TOÀN BỘ (PARTIAL TP & CLOSE ALL)

1. **Quy tắc Chốt lời từng phần (Scale-Out Strategy)**:
   - **Mốc TP1 (Tỷ lệ R:R = 1 : 1.0)**: Chốt `50%` khối lượng Lot (Ví dụ: Đóng 0.05 Lot trong lệnh 0.10 Lot), đồng thời đưa Stop Loss về Break-Even.
   - **Mốc TP2 (Tỷ lệ R:R = 1 : 2.0)**: Chốt `30%` khối lượng Lot tiếp theo.
   - **Mốc TP3 (Runner)**: Giữ `20%` khối lượng Lot còn lại để gồng lời theo đường xu hướng `EMA50`.

2. **Thoát lệnh Khẩn cấp (Emergency Close All)**:
   - Khi anh Tú nhấn nút `[ 🛡️ CLOSE ALL ]` trên Web Terminal hoặc phát lệnh chát *"cắt hết lệnh"*, AI Engine lập tức đẩy lệnh đóng 100% các vị thế trên MT5 trong thời gian $< 500\text{ms}$.
