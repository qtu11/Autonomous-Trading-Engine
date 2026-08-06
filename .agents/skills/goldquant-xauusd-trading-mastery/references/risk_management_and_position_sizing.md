# QUY TẮC QUẢN LÝ RỦI RO VÀ TÍNH TOÁN KHỐI LƯỢNG LỘT (RISK MANAGEMENT & POSITION SIZING)

Dành cho **Hệ thống Quản trị Tài chính GoldQuant AI** & **Chủ tịch anh Tú**.

---

## I. QUY TẮC BẢO TOÀN VỐN (CAPITAL PRESERVATION LAWS)

### 1. Quy tắc Rủi ro 1% (The 1% Risk Per Trade Rule)
- **Tối đa rủi ro mỗi vị thế**: Không vượt quá `1.0%` tổng số dư tài khoản (`Balance`).
- **Công thức toán học tính số tiền chịu rủi ro (Risk Amount)**:
  $$\text{Risk Amount (\$) } = \text{Balance} \times 0.01$$
  *Ví dụ*: Với Balance = $\$9,417.28$, Risk Amount tối đa cho 1 lệnh là:
  $$\$9,417.28 \times 0.01 = \$94.17$$

### 2. Công thức Toán học Tính Khối lượng Lot Chuẩn (Position Size Equation)
Trên thị trường Vàng (XAUUSD / XAUUSDm trên Exness):
- `1.0 Lot Standard` = 100 Ounces Vàng.
- `1 Pip` (Biến động $0.10 giá Vàng) = $\$10.00$ / Lot Standard.
- `1 Point` (Biến động $0.01 giá Vàng) = $\$1.00$ / Lot Standard.

**Công thức tính Lot chính xác**:
$$\text{Lot Size} = \frac{\text{Risk Amount}}{\text{Distance SL (Points)} \times \text{Tick Value}}$$
Hoặc tính theo khoảng cách giá (USD):
$$\text{Lot Size} = \frac{\text{Balance} \times 0.01}{(\text{Entry Price} - \text{SL Price}) \times 100}$$

*Ví dụ tính toán*:
- Giá Ask Vàng = $4,058.00
- Giá Stop Loss (SL) = $4,048.50 (Khoảng cách $9.50 = 95 pips = 950 points)
- Balance = $\$9,417.28$
$$\text{Lot Size} = \frac{94.17}{9.50 \times 100} = \frac{94.17}{950} = 0.0991 \xrightarrow{\text{Làm tròn}} 0.10 \text{ Lot}$$

---

## II. GIỚI HẠN DRAWDOWN VÀ QUY TẮC CẮT TẢI KHẨN CẤP (CIRCUIT BREAKER)

### 1. Mức Giới hạn Sụt giảm Tài sản (Max Drawdown Limits)
- **Daily Max Drawdown**: `-2.0%` Balance trong ngày.
  - Nếu tổng Floating P/L + Closed P/L trong ngày chạm `-2.0%`, AI tự động khóa tính năng Auto-Trade và gửi thông báo báo động cho anh Tú.
- **Max Account Drawdown**: `-5.0%` Peak Equity.
  - Nếu sụt giảm từ đỉnh Equity chạm `-5.0%`, kích hoạt lệnh `CLOSE ALL` toàn bộ vị thế MT5 ngay lập tức.

### 2. Tỷ lệ Thắng (Win Rate) và Tiêu chuẩn Kelly Criterion
Áp dụng công thức Kelly nâng cao để điều chỉnh tỷ lệ vốn (Kelly Fraction):
$$f^* = \frac{p \cdot b - q}{b}$$
Trong đó:
- $p$: Win Rate lịch sử (Ví dụ: $64\% = 0.64$)
- $q$: Loss Rate ($1 - p = 0.36$)
- $b$: Tỷ lệ Risk / Reward ($2.0$)

$$\text{Kelly Fraction } f^* = \frac{0.64 \times 2.0 - 0.36}{2.0} = \frac{1.28 - 0.36}{2.0} = 0.46$$
Áp dụng **Fractional Kelly (Half Kelly 25%)** để đảm bảo an toàn tối đa:
$$\text{Adjusted Risk} = 0.25 \times 0.46 \approx 1.0\% \text{ Balance}$$

---

## III. QUY TẮC DỜI CẮT LỖ (TRAILING STOP & BREAK-EVEN)

1. **Quy tắc Đưa về Hòa vốn (Lock Break-Even - BE)**:
   - Khi vị thế đạt mức lợi nhuận $+1.0 \times \text{Distance SL}$ (ví dụ +100 pips), AI tự động dời giá Stop Loss về đúng giá vào lệnh (`Entry Price + Spread`).
   - Đảm bảo lệnh trở thành **Free Risk Trade** (Vị thế rủi ro bằng 0).

2. **Quy tắc Trailing Stop theo EMA20**:
   - Trong xu hướng TĂNG mạnh (`BUY`), Stop Loss được dời nối tiếp phía dưới đường `EMA20 (M15)` khoảng 1.5 lần ATR.
   - Khi nến đóng phía dưới EMA20, AI tiến hành chốt lời toàn bộ vị thế.
