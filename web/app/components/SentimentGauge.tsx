'use client';

import { useMemo } from 'react';

const C = {
  gold: '#D4B483',
  green: '#22d3a0',
  greenDim: 'rgba(34,211,160,0.15)',
  red: '#f43f5e',
  redDim: 'rgba(244,63,94,0.15)',
  amber: '#f59e0b',
  text: '#f8fafc',
  dim: '#cbd5e1',
  muted: '#64748b',
  border: 'rgba(255,255,255,0.06)',
  mono: '"JetBrains Mono", monospace',
};

// FIX LỖI 3: Correct needle angle calculation from confluence score
// bullishPercent 0 = fully bearish (needle pointing left), 100 = fully bullish (needle right)

interface SentimentGaugeProps {
  bullishPercent?: number; // 0-100, from confluence score
  bearishPercent?: number; // 0-100
  label?: string;
}

export default function SentimentGauge({ bullishPercent = 50, bearishPercent, label }: SentimentGaugeProps) {
  // Normalize bullish percent to 0-100
  const bullPct = Math.min(100, Math.max(0, Number(bullishPercent) || 50));
  const bearPct = Math.min(100, Math.max(0, Number(bearishPercent) || (100 - bullPct)));

  // Color based on sentiment
  const getSentimentColor = (pct: number) => {
    if (pct >= 70) return C.green;
    if (pct >= 55) return '#84cc16'; // lime
    if (pct >= 45) return C.amber;
    if (pct >= 30) return '#f97316'; // orange
    return C.red;
  };

  const sentimentColor = getSentimentColor(bullPct);
  const sentimentLabel = bullPct >= 70 ? 'VERY BULLISH' : bullPct >= 55 ? 'BULLISH' : bullPct >= 45 ? 'NEUTRAL' : bullPct >= 30 ? 'BEARISH' : 'VERY BEARISH';

  // BUG FIX: Gauge geometry hoàn toàn sai trước đây:
  //  - Arc cũ vẽ nửa bên PHẢI (top->right->bottom) nhưng nhãn BEAR/BULL giả định
  //    nửa TRÁI->TRÊN->PHẢI (speedometer chuẩn).
  //  - Needle cũ: needleRad = bull% * PI đo từ hướng PHẢI -> bull%=35 (BEARISH)
  //    mà kim chỉ sang phía BULL (kim ngược), và sin dương -> kim chỉ xuống dưới.
  //  - Segment màu cũ: xanh (bull) vẽ từ đầu path (phía BEAR).
  //
  // Geometry đúng: cung từ TRÁI (BEAR, 180°) qua TRÊN (90°) tới PHẢI (BULL, 0°).
  // f=0 -> kim trái, f=0.5 -> kim trên, f=1 -> kim phải.
  const radius = 50;
  const cx = 60;
  const cy = 55;
  const bullFrac = bullPct / 100;
  const pathLen = Math.PI * radius; // độ dài nửa cung
  const bullLen = bullFrac * pathLen;
  // bearLen dùng để vẽ hình học khớp khít (bull + bear = full arc), độc lập với
  // bearishPercent chỉ dùng cho nhãn ▲/▼ — tránh hở/đè khi caller truyền cả hai.
  const bearLen = pathLen - bullLen;

  // Semicircle: M (cx-r, cy) -> A -> (cx+r, cy); sweep=1 = clockwise qua đỉnh
  const arcPath = `M ${cx - radius} ${cy} A ${radius} ${radius} 0 1 1 ${cx + radius} ${cy}`;

  // Needle: θ = π - f·π  (π=trái, π/2=trên, 0=phải); y screen lật dấu sin
  const needleRad = Math.PI * (1 - bullFrac);
  const needleLength = radius - 12;
  const needleX = cx + needleLength * Math.cos(needleRad);
  const needleY = cy - needleLength * Math.sin(needleRad);

  // Segments: bear = phần path đầu (trái), bull = phần cuối path (phải)
  // dashoffset dương = dash bắt đầu tại vị trí đó trên path
  const bearDash = `${bearLen} ${pathLen * 2}`;
  const bullDash = `${bullLen} ${pathLen * 2}`;
  const bullDashOffset = bearLen;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: 8 }}>
      {label && (
        <div style={{ fontSize: 8, fontFamily: C.mono, fontWeight: 800, color: C.gold, letterSpacing: '0.1em', marginBottom: 4 }}>
          {label}
        </div>
      )}

      {/* Gauge SVG */}
      <svg width="120" height="75" viewBox="0 0 120 75">
        {/* Background arc */}
        <path d={arcPath} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="8" strokeLinecap="round" />

        {/* Red (bearish) segment - left side (phần path đầu = phía BEAR) */}
        <path d={arcPath} fill="none" stroke={C.red} strokeWidth="8" strokeLinecap="round"
          opacity="0.5"
          strokeDasharray={bearDash}
          strokeDashoffset="0"
        />

        {/* Green (bullish) segment - right side (phần cuối path = phía BULL) */}
        <path d={arcPath} fill="none" stroke={C.green} strokeWidth="8" strokeLinecap="round"
          opacity="0.7"
          strokeDasharray={bullDash}
          strokeDashoffset={bullDashOffset}
        />

        {/* Needle */}
        <line
          x1={cx} y1={cy}
          x2={needleX} y2={needleY}
          stroke={sentimentColor}
          strokeWidth="2.5"
          strokeLinecap="round"
        />

        {/* Center circle */}
        <circle cx={cx} cy={cy} r={5} fill={sentimentColor} />

        {/* Labels */}
        <text x={cx - 38} y={cy + 20} fill={C.muted} fontSize="7" fontFamily="JetBrains Mono" fontWeight="600">BEAR</text>
        <text x={cx + 22} y={cy + 20} fill={C.muted} fontSize="7" fontFamily="JetBrains Mono" fontWeight="600">BULL</text>

        {/* Center percentage */}
        <text x={cx} y={cy - 10} textAnchor="middle" fill={sentimentColor} fontSize="13" fontFamily="JetBrains Mono" fontWeight="800">
          {bullPct}%
        </text>
      </svg>

      {/* Sentiment Label Badge */}
      <div style={{
        marginTop: 2,
        padding: '3px 10px',
        background: `${sentimentColor}20`,
        border: `1px solid ${sentimentColor}`,
        borderRadius: 12,
      }}>
        <span style={{ fontSize: 8, fontFamily: C.mono, fontWeight: 700, color: sentimentColor }}>
          {sentimentLabel}
        </span>
      </div>

      {/* Stats */}
      <div style={{ display: 'flex', gap: 16, marginTop: 6, fontSize: 8, fontFamily: C.mono }}>
        <span style={{ color: C.green }}>▲ {bullPct}%</span>
        <span style={{ color: C.red }}>▼ {bearPct}%</span>
      </div>
    </div>
  );
}
