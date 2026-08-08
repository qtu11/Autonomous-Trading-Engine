# QuantAI - Thiết Kế Giao Diện & Design System (UI Guidelines)

## Triết Lý Thiết Kế: Bloomberg Trading Desk Aesthetic

- **Mật độ một màn hình**: Thiết kế cho màn hình PC 1080p/4K, không cần cuộn dọc.
- **Dark Glassmorphism**: Nền tối đậm `#05070c`, container kính mờ (`rgba(10, 14, 24, 0.96)`, `backdrop-filter: blur(16px)`).

## Bảng Màu (Color Palette)

| Vai trò | Màu |
|---------|-----|
| Accent chính (Gold) | `#D4B483` |
| Long / Bullish | `#22d3a0` (Emerald) |
| Short / Bearish / Alert | `#f43f5e` (Rose) |
| Informational / System | `#06b6d4` (Cyan) / `#38bdf8` (Blue) |
| Warning | `#f59e0b` (Amber) |
| Text Primary | `#f8fafc` |
| Text Dim | `#cbd5e1` |
| Text Muted | `#64748b` |
| Text Faint | `#475569` |

## Typography

- **Dữ liệu / rate / metrics / timestamp**: `"JetBrains Mono", monospace`
- **Header / UI label / button**: `"Inter", sans-serif`

## Bố Cục Grid (Một Màn Hình)

```text
+--------------------------------------------------------------------+
| HEADER: Logo | Symbol Selector | Live Ticker | Balance | Equity |  |
|          Margin | Status | Kill Switch                              |
+----------------------------------+---------------------------------+
|                                  |                                 |
|   TRADINGVIEW / MT5 SVG          |   AI SIGNAL INTELLIGENCE &      |
|   CANDLESTICK CHART              |   CONFLUENCE MATRIX             |
|   (zoom/pan, markup objects)     |                                 |
|                                  |                                 |
+----------------------------------+---------------------------------+
| FOOTER PANELS: Active Positions | Trade History | Economic Calendar | Live Logs |
+------------------------------------------------------------------------------+
```

## Chuẩn Truy Cập & Thị Giác

1. **Không placeholder tĩnh**: mọi số liệu là giá trị live hoặc badge `N/A` / `UNAVAILABLE` rõ ràng khi offline.
2. **Micro-animation & hover**: chuyển tiếp 0.2s cubic-bezier trên card/button/switch.
3. **Mật độ thông tin**: padding 4-12px, viền 1px `rgba(255, 255, 255, 0.08)`.
4. **Format chuẩn**: JSX props multi-line, responsive CSS sạch.
5. **Responsive**: tối ưu mobile-first khi cần, nhưng giữ trải nghiệm desktop chính yếu.

---

*Tài liệu thuộc dự án QuantAI - Nguyễn Quang Tú (QTusdev) | MIT License.*