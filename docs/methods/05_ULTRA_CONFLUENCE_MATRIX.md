# ĐẶC TẢ CHI TIẾT PHƯƠNG PHÁP 5: ULTRA CONFLUENCE MATRIX (MA TRẬN HỢP LƯU 5 TẦNG)

## 1. Tổng Quan Kiến Trúc
Phương pháp **Ultra Confluence Matrix** là đỉnh cao của hệ thống định lượng TradeAI ATE, kết hợp toàn bộ sức mạnh của 4 trường phái (SMC + ICT + Sniper + Price Action) thành một ma trận 5 tầng tính toán điểm số từ 0 đến 100 điểm, chuyển hóa từ mã nguồn `structureengine.pine` sang module Python `dashboard/aether_smc.py`.

---

## 2. Cấu Trúc Ma Trận 5 Tầng (5-Layer Scoring Matrix)

Tổng điểm tối đa là **100 điểm**, được phân bổ theo tỷ trọng thể chế:

```
┌─────────────────────────────────────────────────────────────┐
│             ULTRA CONFLUENCE MATRIX (100 ĐIỂM)              │
├─────────────────────────────────────────────────────────────┤
│  TẦNG 1 (25%): CẤU TRÚC THỊ TRƯỜNG (Market Structure)      │
│  - Major Trend (HH/HL hoặc LH/LL): 20 điểm                 │
│  - BoS / CHoCH Confirmed: 5 điểm                           │
├─────────────────────────────────────────────────────────────┤
│  TẦNG 2 (25%): VÙNG CUNG CẦU (Supply & Demand / OB / FVG)  │
│  - Active Unmitigated Order Block: 15 điểm                 │
│  - Fair Value Gap Imbalance Confluence: 10 điểm            │
├─────────────────────────────────────────────────────────────┤
│  TẦNG 3 (20%): KỸ THUẬT ĐỘNG (Dynamic EMA & VWAP)          │
│  - Price vs VWAP Institutional Bias: 10 điểm               │
│  - EMA 9/21 Ribbon Alignment: 10 điểm                      │
├─────────────────────────────────────────────────────────────┤
│  TẦNG 4 (15%): ĐỘNG LƯỢNG & KHỐI LƯỢNG (Momentum & Vol)    │
│  - Sniper 7-Factor Dual Score: 10 điểm                     │
│  - ADX Trend Strength & Volume Expansion: 5 điểm           │
├─────────────────────────────────────────────────────────────┤
│  TẦNG 5 (15%): THỜI GIAN & PHIÊN (Time & Killzones)        │
│  - Active London / NY AM / Silver Bullet Window: 10 điểm   │
│  - OTE Fibonacci 61.8% - 78.6% Retracement: 5 điểm         │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Phân Cấp Quyết Định AI & Khớp Lệnh (Execution Gateways)

Dựa trên tổng điểm tính toán thời gian thực của nến:

| Phân Cấp | Ngưỡng Điểm | Trạng Thái AI | Hành Động Tự Động Hóa |
|---|---|---|---|
| **QUALIFIED** | $\ge \mathbf{80}$ **điểm** | **AI Auto-Trade ACTIVE** | Kích hoạt gửi lệnh sang MT5 EA ngay lập tức. Tính toán Lot Size theo hồ sơ rủi ro (Risk Profile 1.0% vốn) và đặt sẵn SL/TP. |
| **CONSIDER** | $\mathbf{65} - \mathbf{79}$ **điểm** | **AI MONITORING** | Chờ thêm 1 cây nến M5/M1 xác nhận (Confirmation Candle). Nếu nến tiếp theo đồng pha sẽ kích hoạt lệnh với 50% khối lượng tiêu chuẩn. |
| **FILTERED** | $< \mathbf{65}$ **điểm** | **AI REJECTED** | Chặn lệnh hoàn toàn theo nguyên tắc **Fail-Closed**. Bảo vệ tài khoản khỏi các pha nhiễu thị trường (Chop/Sideway). |

---

## 4. Cơ Chế Fail-Closed RiskGate 15 Điểm
Trước khi một lệnh được đẩy sang cầu nối MT5 Bridge, hệ thống bắt buộc phải vượt qua 15 chốt kiểm soát rủi ro:
1. `Circuit Breaker Check`: Không có đợt sụt giảm vốn quá mức trong ngày (Max Daily Drawdown < 3.0%).
2. `Spread Filter`: Chênh lệch Bid/Ask < 25 points (2.5 pips vàng).
3. `News Blackout Gate`: Không giao dịch trong phạm vi 15 phút trước và sau tin tức đỏ (High Impact News).
4. `Session Liquidity Gate`: Từ chối vào lệnh ngoài các khung giờ thanh khoản chuẩn.
5. `Max Open Positions Gate`: Không mở quá số lệnh cho phép trên một cặp tiền.
6. `Correlation Exposure Gate`: Kiểm tra mức độ chịu rủi ro chéo giữa các tài sản tương quan.
7. `Idempotency Command Check`: Khóa chống trùng lặp lệnh bằng SQLite WAL Token.

---

## 5. Trực Quan Hóa Trên Chart (SVG Overlay & Toolbar HUD)
- **Badge Confluence Score**: Hiển thị nổi bật trên thanh công cụ góc trái:
  - Màu Xanh sáng khi `BUY | score 85`
  - Màu Đỏ sáng khi `SELL | score 82`
  - Màu Xám khi `NEUTRAL | score 35`
- Phân tích chi tiết 5 tầng lớp được truyền trực tiếp vào AI Copilot Chat để giải thích rõ lý do vào lệnh cho chủ tịch Tú.
