# ĐẶC TẢ CHI TIẾT PHƯƠNG PHÁP 2: ICT (INNER CIRCLE TRADER)

## 1. Tổng Quan Kiến Trúc
Phương pháp **Inner Circle Trader (ICT)** trong TradeAI ATE tập trung vào tính chu kỳ thời gian (Time-Based Liquidity), vùng giá tối ưu (Optimal Trade Entry) và bẫy săn thanh khoản (Turtle Soup / Judas Swing / Silver Bullet / Unicorn), chuyển hóa từ mã nguồn `ict.pine` sang module Python `dashboard/aether_smc.py`.

---

## 2. Khung Giờ Thanh Khoản (ICT Killzones & Daily Cycles)

Hệ thống tự động chuyển đổi múi giờ broker sang giờ chuẩn UTC để xác định chính xác các phiên giao dịch:

| Killzone | Khung Giờ (UTC) | Ý Nghĩa Chiến Thuật & Đặc Điểm |
|---|---|---|
| **Asian Range (Midnight-Midnight)** | `00:00 - 08:00 UTC` | Phiên Á tích lũy biên độ hẹp, tạo ra đỉnh Asian High và đáy Asian Low làm mồi câu thanh khoản cho phiên Âu. |
| **London Killzone (Open Session)** | `08:00 - 11:00 UTC` | Phiên Luân Đôn mở cửa, thường xuất hiện **Judas Swing** (bẫy giá giả quét đỉnh/đáy phiên Á) trước khi hình thành xu hướng thật trong ngày (True Daily Trend). |
| **New York AM Killzone** | `13:30 - 16:00 UTC` | Phiên Mỹ buổi sáng mở cửa cùng tin tức kinh tế quan trọng (CPI, NFP, PPI). Giai đoạn thanh khoản và biên độ cao nhất trong ngày. |
| **Silver Bullet Window** | `14:00 - 15:00 UTC` *(10:00 - 11:00 AM EST)* | Khung giờ vàng của ICT, giá tìm về lấp các vùng FVG mới tạo ra sau khi quét thanh khoản phiên sáng. |
| **New York PM Killzone** | `17:00 - 21:00 UTC` | Phiên Mỹ buổi chiều, phân phối và hoàn tất mô hình AMD (Distribution). |

---

## 3. Điểm Vào Lệnh Tối Ưu (Optimal Trade Entry - OTE)

### 3.1. Tỷ Lệ Fibonacci Hoàng Gia
Khi xuất hiện cấu trúc phá vỡ (BoS/CHoCH) trên khung chính, hệ thống tự động kéo Fibonacci từ Đỉnh $\rightarrow$ Đáy (hoặc ngược lại) để xác định vùng OTE:
- **Mức 0.618 (Golden Ratio)**: Vùng bắt đầu giải ngân.
- **Mức 0.705 (Institutional Sweet Spot)**: Mức giá vào lệnh đẹp nhất với xác suất thắng cao nhất và R:R tối ưu.
- **Mức 0.786 (Deep Retracement)**: Mức cản cuối cùng trước khi vô hiệu hóa mô hình.
- **Mức 0.500 (Equilibrium)**: Ngưỡng cân bằng phân định Premium và Discount.

---

## 4. Các Mô Hình Vào Lệnh ICT Đặc Quyền

### 4.1. ICT Turtle Soup (Săn Thanh Khoản Đỉnh/Đáy)
- **Cơ chế**:
  1. Giá tạo một cú quét râu (Wick Sweep) vượt qua Đỉnh/Đáy của khung lớn (H1 High/Low hoặc Previous Day High/Low - PDH/PDL).
  2. Nến không thể đóng cửa bên ngoài mà lập tức rút râu đóng ngược trở lại vào bên trong biên độ $\rightarrow$ Bẫy thanh khoản (Liquidity Grab).
  3. Xuất hiện tín hiệu đảo chiều MSS $\rightarrow$ AI kích hoạt lệnh đối nghịch với phe bị quét.
- **Quản lý rủi ro**:
  - Entry: Tại giá đóng cửa nến xác nhận rút râu.
  - SL: Cách điểm râu quét 1.5 - 2.0 pips.
  - TP: Đỉnh/Đáy đối diện của biên độ.

### 4.2. ICT Unicorn Model
- Sự kết hợp đồng pha giữa **Breaker Block** (Khối Order Block cũ bị phá vỡ và chuyển thành hỗ trợ/kháng cự mới) nằm trùng khớp bên trong một vùng **Fair Value Gap (FVG)**.

### 4.3. Mô Hình Tích Lũy - Thao Túng - Phân Phối (AMD / Power of Three - PO3)
- **Accumulation (Tích lũy)**: Phiên Á đi ngang tạo range hẹp.
- **Manipulation (Thao túng)**: Đầu phiên Âu hoặc trước giờ ra tin quét râu giả tạo fake breakout.
- **Distribution (Phân phối)**: Phiên Mỹ đẩy giá mạnh mẽ theo xu hướng thật.

---

## 5. Trực Quan Hóa Trên Biểu Đồ (SVG Overlay)
- **Dải OTE Box Zone**: Vùng hộp màu vàng cam trong suốt `rgba(255, 165, 0, 0.12)` với viền `#FFA500` và nhãn `ICT OTE (0.705)`.
- **Badge Killzone**: Hiển thị trạng thái phiên đang hoạt động (`LONDON_KILLZONE`, `NY_AM_KILLZONE`, `ASIAN_RANGE`) trên toolbar.
- **Marker Turtle Soup**: Marker tam giác màu vàng ánh kim `#FFD700` kèm chữ `SOUP BUY` / `SOUP SELL` ngay dưới chân nến kích hoạt.
