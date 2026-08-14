# ĐẶC TẢ CHI TIẾT PHƯƠNG PHÁP 4: PRICE ACTION & CANDLE DYNAMICS

## 1. Tổng Quan Kiến Trúc
Phương pháp **Price Action & Candle Dynamics** trong TradeAI ATE tập trung vào việc giải mã tâm lý thị trường thông qua hình thái nến (Candlestick Geometry), tỷ lệ thân/râu nến, cây nến dịch chuyển mạnh (Displacement) và các vùng cản động (Dynamic S&R), chuyển hóa từ mã nguồn `priceaction.pine` sang module Python `dashboard/aether_smc.py`.

---

## 2. Hệ Thống 14 Mẫu Hình Nến Cốt Lõi

Hệ thống sử dụng các công thức đo lường chính xác thay vì quy tắc trực quan cảm tính:

### 2.1. Nhóm Nến Đảo Chiều Đơn (Single Candle Reversals)
- **Pin Bar / Hammer (Búa Mua)**:
  - Râu nến dưới dài ít nhất gấp đôi thân nến: $\text{Lower Wick} \ge 2.0 \times \text{Body}$.
  - Râu nến trên cực ngắn: $\text{Upper Wick} \le 0.5 \times \text{Body}$.
  - Ý nghĩa: Phe Bán cố gắng đạp giá xuống nhưng bị lực Mua mạnh mẽ đẩy ngược lên.
- **Shooting Star (Bắn Sao Bán)**:
  - Râu nến trên dài ít nhất gấp đôi thân nến: $\text{Upper Wick} \ge 2.0 \times \text{Body}$.
  - Râu nến dưới cực ngắn: $\text{Lower Wick} \le 0.5 \times \text{Body}$.
  - Ý nghĩa: Phe Mua bị từ chối giá tại vùng cản trên.
- **Doji (Dragonfly / Gravestone / Long-legged)**:
  - Thân nến cực nhỏ: $\text{Body} \le 0.1 \times \text{Total Range}$.
  - Thể hiện sự lưỡng lự và cân bằng tuyệt đối giữa 2 phe.

### 2.2. Nhóm Nến Đảo Chiều Đôi & Ba (Multi-Candle Reversals)
- **Bullish / Bearish Engulfing (Nhấn Chìm)**:
  - Thân nến sau bao trọn toàn bộ thân nến trước: $\text{Body}[i] > 1.1 \times \text{Body}[i-1]$.
  - Nến sau đóng cửa vượt qua giá mở cửa của nến trước.
- **Morning Star / Evening Star (Sao Mai / Sao Hôm)**:
  - Bộ 3 nến: Nến 1 giảm mạnh $\rightarrow$ Nến 2 thân nhỏ (Doji/Spinning Top) $\rightarrow$ Nến 3 tăng mạnh vượt quá 50% thân nến 1.
- **Three White Soldiers / Three Black Crows (Ba Chàng Lính Ngự Lâm / Ba Con Quạ Đen)**:
  - Chuỗi 3 nến liên tiếp cùng màu, thân nến lớn, đóng cửa gần đỉnh/đáy, xác nhận sóng đẩy mạnh.
- **Tweezer Top / Tweezer Bottom (Đỉnh/Đáy Nhíp)**:
  - Hai nến liên tiếp có cùng mức High hoặc cùng mức Low (chênh lệch $\le 0.1$ pips).

### 2.3. Nhóm Nến Tích Lũy & Tiếp Diễn
- **Inside Bar (Harami)**:
  - Toàn bộ biên độ nến con nằm gọn bên trong biên độ của nến mẹ (Mother Bar). Báo hiệu sự nén giá chuẩn bị bùng nổ.
- **Marubozu / Displacement Candle**:
  - Nến thân đặc, hầu như không có râu ($\text{Body Ratio} \ge 0.9$).
  - Biên độ vượt $1.5 \times \text{ATR}$, thể hiện sự xuất hiện của dòng tiền lớn (Smart Money Impulse).

---

## 3. Kháng Cự & Hỗ Trợ Động (Dynamic Support & Resistance)
- Nhận diện các vùng đỉnh đáy có ít nhất 2 đến 3 lần chạm (Touches) mà không bị phá vỡ.
- Đánh giá sức mạnh của vùng cản dựa trên:
  $$\text{Strength} = \text{Touches} \times \text{Timeframe Weight} \times \text{Volume At Pivot}$$
- **Breakout & Retest**:
  - Khi nến đóng cửa vượt qua vùng cản kèm Volume lớn $\rightarrow$ Xác nhận Breakout.
  - Chờ nhịp hồi (Retest) quay lại chạm kiểm tra vùng cản cũ $\rightarrow$ Kích hoạt điểm vào lệnh an toàn.

---

## 4. Trực Quan Hóa Trên Chart (SVG Overlay)
- Các mẫu hình nến Price Action được đánh dấu bằng **Marker tròn nhỏ gọn** màu Cyan `#00e5ff` (Bullish) hoặc Hồng tím `#ff4081` (Bearish) đặt trên/dưới nến.
- Tuyệt đối không kẻ các đường ray ngang vô tận làm che nến, giữ chart luôn sạch đẹp.
