# ĐẶC TẢ CHI TIẾT PHƯƠNG PHÁP 3: SNIPER MOMENTUM FLOW

## 1. Tổng Quan Kiến Trúc
Phương pháp **Sniper Momentum Flow** được phát triển nhằm nắm bắt các xung lực bứt phá (Momentum Breakout) và sóng hồi động (Dynamic Pullback) với độ trễ cực thấp, chuyển hóa từ mã nguồn `sniper.pine` sang module Python `dashboard/aether_smc.py`.

---

## 2. Các Chỉ Báo Động Lượng Cốt Lõi

### 2.1. Dải EMA Ribbon 9 / 21
- **EMA 9 (Fast)**: Đường trung bình động hàm mũ 9 chu kỳ, phản ánh động lượng siêu ngắn hạn.
- **EMA 21 (Slow)**: Đường trung bình động hàm mũ 21 chu kỳ, đóng vai trò là dải hỗ trợ/kháng cự động (Dynamic Support/Resistance).
- **Trạng thái Ribbon**:
  - `Ribbon Bullish`: EMA 9 > EMA 21 (dải xanh).
  - `Ribbon Bearish`: EMA 9 < EMA 21 (dải đỏ).
  - Khoảng cách giữa 2 đường càng rộng thể hiện xu hướng càng mạnh mẽ.

### 2.2. Khối Lượng Định Giá VWAP (Volume Weighted Average Price)
- Tính toán mức giá trung bình theo khối lượng giao dịch từ đầu ngày:
  $$\text{VWAP} = \frac{\sum (\text{HLC3} \times \text{Volume})}{\sum \text{Volume}}$$
- Khi giá nằm trên VWAP $\rightarrow$ Phe Mua chiếm ưu thế thể chế (Institutional Long Bias).
- Khi giá nằm dưới VWAP $\rightarrow$ Phe Bán chiếm ưu thế thể chế (Institutional Short Bias).

---

## 3. Hệ Thống Chấm Điểm Sniper Dual Score (7 Yếu Tố)

AI tính toán đồng thời 7 yếu tố để đưa ra **Bull Score (%)** và **Bear Score (%)**:

| Yếu Tố | Điều Kiện Phe Bò (Bull Point +1) | Điều Kiện Phe Gấu (Bear Point +1) |
|---|---|---|
| **1. Định Giá VWAP** | $\text{Close} > \text{VWAP}$ | $\text{Close} < \text{VWAP}$ |
| **2. Động Lượng RSI(14)** | $\text{RSI}(14) > 50$ | $\text{RSI}(14) < 50$ |
| **3. MACD Crossover** | $\text{MACD Line} > \text{Signal Line}$ | $\text{MACD Line} < \text{Signal Line}$ |
| **4. EMA Ribbon** | $\text{EMA 9} > \text{EMA 21}$ | $\text{EMA 9} < \text{EMA 21}$ |
| **5. Sức Mạnh Xu Hướng ADX** | $\text{ADX}(14) > 25 \text{ và } \text{Close} > \text{EMA 9}$ | $\text{ADX}(14) > 25 \text{ và } \text{Close} < \text{EMA 9}$ |
| **6. Xác Nhận Khối Lượng** | $\text{Volume} > \text{SMA}(20) \text{ và } \text{Nến Xanh}$ | $\text{Volume} > \text{SMA}(20) \text{ và } \text{Nến Đỏ}$ |
| **7. Đa Khung Thời Gian (MTF)** | $\text{RSI khung M5} > 50$ | $\text{RSI khung M5} < 50$ |

- **Công thức phần trăm**:
  $$\text{Bull Score \%} = \frac{\text{Bull Points}}{7} \times 100\%, \quad \text{Bear Score \%} = \frac{\text{Bear Points}}{7} \times 100\%$$
- **Phân loại xu hướng (Bias)**:
  - $\Delta \ge 40\%$: `STRONG BULL` hoặc `STRONG BEAR` (Ưu tiên vào lệnh tối đa khối lượng).
  - $\Delta < 40\%$: `MILD BULL` hoặc `MILD BEAR`.

---

## 4. Mục Tiêu Chốt Lời Động (Dynamic ATR TP1 - TP5 & SL)

Sử dụng biến động thực tế của thị trường qua chỉ số **Average True Range (ATR 14)**:
- **Khoảng Rủi Ro (Risk Unit)**: $\text{Risk} = \text{ATR} \times 1.5$
- **Điểm Cắt Lỗ (Stop Loss)**:
  - Buy: $\text{Entry} - \text{Risk}$
  - Sell: $\text{Entry} + \text{Risk}$
- **Chuỗi Mục Tiêu Chốt Lời (Take Profit Scale)**:
  - **TP1 (1.0 R)**: $\text{Entry} \pm (1.0 \times \text{Risk})$ $\rightarrow$ Đóng 50% khối lượng, dời SL về Hòa Vốn (BE).
  - **TP2 (2.0 R)**: $\text{Entry} \pm (2.0 \times \text{Risk})$ $\rightarrow$ Đóng tiếp 20% khối lượng.
  - **TP3 (3.0 R)**: $\text{Entry} \pm (3.0 \times \text{Risk})$ $\rightarrow$ Đóng tiếp 15% khối lượng.
  - **TP4 (4.0 R)**: $\text{Entry} \pm (4.0 \times \text{Risk})$ $\rightarrow$ Đóng tiếp 10% khối lượng.
  - **TP5 (5.0 R Runner)**: $\text{Entry} \pm (5.0 \times \text{Risk})$ $\rightarrow$ Giữ 5% trailing stop theo EMA 21.

---

## 5. Tín Hiệu UT Bot Momentum Reversal
- Sử dụng dải trượt động **Adaptive ATR Trailing Stop** với hệ số `Key = 2.0`, `Period = 6`.
- Tín hiệu `BUY`: Khi nến vượt lên trên dải trailing stop và EMA 1 cắt lên.
- Tín hiệu `SELL`: Khi nến cắt xuống dưới dải trailing stop và EMA 1 cắt xuống.
- Trực quan: Mũi tên xanh/đỏ kèm chữ `BUY` / `SELL` kích thước lớn ngay chân nến.
