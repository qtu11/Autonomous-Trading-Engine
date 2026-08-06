# QuantAI UI Guidelines & Design System

## Core Design Philosophy: Bloomberg Trading Desk Aesthetic
- **Single-Screen Density**: Designed for full 1080p/4K PC monitors without vertical page scrolling.
- **Dark Glassmorphism**: Ultra-dark background `#05070c` with frosted glass container backdrop (`rgba(10, 14, 24, 0.96)`, `backdrop-filter: blur(16px)`).
- **Color Palette**:
  - Primary Accent: Gold (`#D4B483`)
  - Long / Bullish: Emerald Green (`#22d3a0`)
  - Short / Bearish / Alert: Rose Red (`#f43f5e`)
  - Informational / System: Cyan (`#06b6d4`) / Blue (`#38bdf8`)
  - Warning: Amber (`#f59e0b`)
  - Text Hierarchy: Primary (`#f8fafc`), Dim (`#cbd5e1`), Muted (`#64748b`), Faint (`#475569`)
- **Typography**:
  - Monospace (Data / Rates / Metrics / Timestamps): `"JetBrains Mono", monospace`
  - Sans-serif (Headers / UI Labels / Buttons): `"Inter", sans-serif`

## Component Grid Layout (Single Monitor)
```text
┌─────────────────────────────────────────────────────────────────────────────────┐
│ HEADER: Logo | Symbol Selector | Live Ticker | Balance | Equity | Margin | Status │
├──────────────────────────┬────────────────────────────┬─────────────────────────┤
│                          │                            │                         │
│   TRADINGVIEW / MT5 SVG  │   AI SIGNAL INTELLIGENCE   │   CONTROL CENTER &      │
│   CANDLESTICK CHART      │   & CONFLUENCE MATRIX      │   ORDER DESK CONTROLS   │
│                          │                            │                         │
├──────────────────────────┴────────────────────────────┴─────────────────────────┤
│ FOOTER PANELS: Active Positions | Trade History | Economic Calendar | Live Logs │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## UI & Visual Accessibility Standards
1. **No Static Placeholders**: All numbers are live values or explicit `N/A` / `UNAVAILABLE` badges when offline.
2. **Micro-Animations & Hover Effects**: Smooth 0.2s cubic-bezier transitions on cards, buttons, and switches.
3. **Information Density**: Compact padding (4px - 12px) with crisp 1px borders (`rgba(255, 255, 255, 0.08)`).
4. **Prettier & JSX Formatting**: Standardized multi-line JSX props and clean responsive CSS.
