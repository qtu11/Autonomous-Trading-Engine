# PHÂN TÍCH KỸ THUẬT VÀ MA TRẬN TÍN HIỆU ĐỊNH LƯỢNG (TECHNICAL ANALYSIS & SIGNAL CONFLUENCE MATRIX)

Dành cho **Bộ não AI** & **Chủ tịch anh Tú**.

---

## I. HỆ THỐNG CHỈ BÁO KỸ THUẬT NÂNG CAO (INDICATOR SUITE)

### 1. Bộ Đường Trung Bình Động Lũy Thừa (EMA Stack)
- **EMA20 (Sóng ngắn - Dynamic Support/Resistance)**: Xác định lực đẩy giá ngắn hạn.
- **EMA50 (Sóng trung - Trend Filter)**: Xác định ranh giới xu hướng chủ đạo.
- **EMA200 (Sóng dài - Major Baseline)**: Ranh giới phân định thị trường Bullish hay Bearish.

**Quy tắc Xếp tầng Xu hướng (Trend Hierarchy Rules)**:
- **Tín hiệu BUY mạnh**: $\text{Price} > \text{EMA20} > \text{EMA50} > \text{EMA200}$.
- **Tín hiệu SELL mạnh**: $\text{Price} < \text{EMA20} < \text{EMA50} < \text{EMA200}$.

### 2. Chỉ số Sức mạnh Tương đối (RSI 14)
- **Vùng Mua thuận xu hướng (Bullish Zone)**: RSI nằm trong khoảng `50.0 – 70.0`.
- **Vùng Bán thuận xu hướng (Bearish Zone)**: RSI nằm trong khoảng `30.0 – 50.0`.
- **Vùng Quá Mua (Overbought)**: RSI $> 75.0 \rightarrow$ Tạm dừng mở lệnh BUY mới.
- **Vùng Quá Bán (Oversold)**: RSI $< 25.0 \rightarrow$ Tạm dừng mở lệnh SELL mới.

### 3. Chỉ số Biến động Trung bình Thực tế (ATR 14)
- ATR đo lường mức độ dao động trung bình của nến Vàng (tính theo USD/oz).
- **Thiết lập Stop Loss (SL)**: $\text{Distance SL} = \text{ATR} \times 1.5$.
- **Thiết lập Take Profit (TP)**: $\text{Distance TP} = \text{Distance SL} \times 2.0 = \text{ATR} \times 3.0$.

---

## II. ĐIỂM XOAY VÙNG GIÁ PIVOT POINTS (PIVOT BOUNDARIES)

Sử dụng công thức **Classic Pivot Points (Khung Daily)**:
$$\text{Pivot (P)} = \frac{\text{High} + \text{Low} + \text{Close}}{3}$$
$$\text{Resistance 1 (R1)} = (2 \times P) - \text{Low}$$
$$\text{Support 1 (S1)} = (2 \times P) - \text{High}$$
$$\text{Resistance 2 (R2)} = P + (\text{High} - \text{Low})$$
$$\text{Support 2 (S2)} = P - (\text{High} - \text{Low})$$

**Quy tắc Hành động Giá tại Điểm Xoay**:
- **Trường hợp bứt phá (Breakout)**: Giá vượt hẳn R1 với khối lượng Volume $> 1.3\times$ trung bình $\rightarrow$ Kích hoạt lệnh BUY bám sóng lên R2.
- **Trường hợp từ chối (Rejection)**: Giá chạm R1 xuất hiện nến Pinbar đảo chiều $\rightarrow$ Kích hoạt lệnh SELL ngắn chốt lời tại Pivot P.
