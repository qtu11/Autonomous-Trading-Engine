# ĐẶC TẢ CHI TIẾT PHƯƠNG PHÁP 1: SMC (SMART MONEY CONCEPTS)

## 1. Tổng Quan Kiến Trúc
Phương pháp **Smart Money Concepts (SMC)** trong TradeAI ATE được xây dựng dựa trên sự kết hợp giữa **Mxwll Suite**, **LuxAlgo Volume Pivot Order Blocks** và **BigBeluga Structure Engine**, chuyển hóa từ mã nguồn `smc.pine` và `structureengine.pine` sang module Python hiệu năng cao `dashboard/aether_smc.py`.

---

## 2. Cấu Trúc Thị Trường (Market Structure)

### 2.1. Phân Tách Đa Tầng Cấu Trúc
- **External Structure (Major Swings - Độ nhạy 25 nến)**:
  - Xác định cấu trúc khung lớn để tìm xu hướng chủ đạo (HTF Trend).
  - Điểm đỉnh cao hơn (`HH` - Higher High) và đáy cao hơn (`HL` - Higher Low) cho xu hướng Tăng (Bullish).
  - Điểm đỉnh thấp hơn (`LH` - Lower High) và đáy thấp hơn (`LL` - Lower Low) cho xu hướng Giảm (Bearish).
- **Internal Structure (Minor Swings - Độ nhạy 5 nến)**:
  - Bắt các nhịp sóng hồi nội tại để tìm điểm vào lệnh với tỷ lệ R:R cao nhất.

### 2.2. Sự Kiện Phá Vỡ Cấu Trúc
- **BoS (Break of Structure - Phá Vỡ Tiếp Diễn)**:
  - Xảy ra khi nến đóng cửa vượt qua đỉnh `HH` gần nhất trong xu hướng tăng, hoặc phá thủng đáy `LL` gần nhất trong xu hướng giảm.
  - Tọa độ hiển thị: Đoạn thẳng nét đứt nối từ đỉnh/đáy cũ tới nến phá vỡ kèm nhãn `BoS`.
- **CHoCH (Change of Character - Đảo Chiều Xu Hướng)**:
  - Xảy ra khi giá phá vỡ đáy `HL` quan trọng trong xu hướng tăng (báo hiệu chuyển sang giảm), hoặc phá đỉnh `LH` quan trọng trong xu hướng giảm (báo hiệu chuyển sang tăng).
  - Tọa độ hiển thị: Đoạn thẳng nét đứt màu đỏ/xanh kèm nhãn `CHoCH`.
- **MSS (Market Structure Shift)**:
  - Xác nhận bước ngoặt cấu trúc khi có thêm nến thứ 2 đóng cửa xác nhận sau CHoCH.

---

## 3. Khối Lệnh Tổ Chức (Order Blocks - LuxAlgo Volume Pivot Edition)

### 3.1. Thuật Toán Nhận Diện
- **Bullish Order Block (OB Demand)**: Nến giảm cuối cùng trước khi xuất hiện chuỗi nến tăng mạnh kèm khối lượng vượt 1.2x SMA Volume(20).
- **Bearish Order Block (OB Supply)**: Nến tăng cuối cùng trước khi xuất hiện chuỗi nến giảm mạnh kèm khối lượng đột biến.
- Biên độ vùng OB:
  $$\text{Top} = \max(\text{Open}, \text{Close}), \quad \text{Bottom} = \text{Low}, \quad \text{Midline (Mean Threshold)} = \frac{\text{Top} + \text{Bottom}}{2}$$

### 3.2. Cơ Chế Lọc & Kiểm Tra Giảm Thiểu (Mitigation Tracking)
- Quét toàn bộ nến sau khi hình thành OB:
  - Nếu giá đóng cửa hoặc râu nến xuyên qua `Bottom` của Bullish OB $\rightarrow$ Đánh dấu **Mitigated (Đã thanh khoản)**.
  - Nếu giá đóng cửa hoặc râu nến vượt qua `Top` của Bearish OB $\rightarrow$ Đánh dấu **Mitigated**.
- **Nguyên tắc Declutter**: Hệ thống chỉ giữ tối đa **3-5 khối Order Block CHƯA BỊ XUYÊN THỦNG (Unmitigated)** gần giá hiện tại nhất để tránh làm rối biểu đồ.

---

## 4. Khoảng Trống Giá Trị Hợp Lý (Fair Value Gaps - FVG)

### 4.1. Công Thức 3 Nến (3-Candle Imbalance)
- **Bullish FVG**: $\text{Low}[i] > \text{High}[i-2]$
  - Khoảng trống: Từ $\text{High}[i-2]$ đến $\text{Low}[i]$.
- **Bearish FVG**: $\text{High}[i] < \text{Low}[i-2]$
  - Khoảng trống: Từ $\text{High}[i]$ đến $\text{Low}[i-2]$.

### 4.2. Bộ Lọc Ngưỡng & Tự Động Ẩn Khi Fill
- **Threshold Filter**: $\frac{|\text{Gap}|}{\text{Price}} \ge \text{Threshold}$ (loại bỏ các gap quá bé gây nhiễu).
- **Fill State**: Khi các nến tiếp theo di chuyển lấp đầy vùng FVG, hệ thống tự động ẩn FVG khỏi biểu đồ và giải phóng bộ nhớ.

---

## 5. Thanh Khoản & Các Vùng Giá (Liquidity Pools & Premium/Discount)
- **BSL (Buy-Side Liquidity)**: Thanh khoản nằm phía trên các đỉnh bằng nhau (`EQH` - Equal Highs), nơi tập trung Stop Loss của phe Bán.
- **SSL (Sell-Side Liquidity)**: Thanh khoản nằm phía dưới các đáy bằng nhau (`EQL` - Equal Lows), nơi tập trung Stop Loss của phe Mua.
- **Premium Zone**: Vùng giá nằm từ mức cân bằng Equilibrium (50%) đến Đỉnh Swing High (Ưu tiên tìm setup SELL).
- **Discount Zone**: Vùng giá nằm từ mức cân bằng Equilibrium (50%) đến Đáy Swing Low (Ưu tiên tìm setup BUY).

---

## 6. Trực Quan Hóa Trên Chart (SVG Overlay Engine)
- **Hộp Order Block**: Rectangular SVG với màu xanh `#14D990` (Demand) / đỏ `#F24968` (Supply), opacity 16%, viền mỏng bo góc 2px kèm chữ `OB Demand` / `OB Supply`.
- **Hộp FVG**: Màu Cyan `#00e5ff` (Bull) / Magenta `#e91e63` (Bear) trong suốt.
- **Đường BoS/CHoCH**: Đoạn line nét đứt 4-3 có badge khung nền xám ở giữa.
- **Markers Swings**: `HH`, `HL`, `LH`, `LL` gắn ngay trên đỉnh hoặc dưới đáy nến.
