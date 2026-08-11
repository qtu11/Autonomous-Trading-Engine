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

  // FIX: Correct needle angle calculation
  // 0% = -90 degrees (left, bearish)
  // 50% = 0 degrees (center, neutral)
  // 100% = +90 degrees (right, bullish)
  // Angle = (bullishPercent / 100) * 180 - 90
  const angle = (bullPct / 100) * 180 - 90;

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

  // SVG arc parameters
  const radius = 50;
  const cx = 60;
  const cy = 55;
  const startAngle = -90;
  const endAngle = 90;
  const startRad = (startAngle * Math.PI) / 180;
  const endRad = (endAngle * Math.PI) / 180;

  // Arc path
  const x1 = cx + radius * Math.cos(startRad);
  const y1 = cy + radius * Math.sin(startRad);
  const x2 = cx + radius * Math.cos(endRad);
  const y2 = cy + radius * Math.sin(endRad);
  const largeArc = 1; // > 180 degrees

  const arcPath = `M ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2}`;

  // Needle calculation
  const needleRad = ((angle + 90) * Math.PI) / 180;
  const needleLength = radius - 12;
  const needleX = cx + needleLength * Math.cos(needleRad);
  const needleY = cy + needleLength * Math.sin(needleRad);

  // Color segments calculation
  const bullLength = (bullPct / 100) * Math.PI;
  const bullArc = bullPct > 0 ? `M ${cx} ${cy} L ${cx + radius * Math.cos(startRad)} ${cy + radius * Math.sin(startRad)} A ${radius} ${radius} 0 ${bullPct > 50 ? 1 : 0} 1 ${cx + radius * Math.cos(startRad + bullLength)} ${cy + radius * Math.sin(startRad + bullLength)} Z` : '';

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

        {/* Red (bearish) segment - left side */}
        <path d={arcPath} fill="none" stroke={C.red} strokeWidth="8" strokeLinecap="round"
          opacity="0.5"
          strokeDasharray={`${(bearPct / 100) * Math.PI * radius * 1.1} ${Math.PI * radius * 2}`}
          strokeDashoffset={`${(bullPct / 100) * Math.PI * radius * 1.1}`}
        />

        {/* Green (bullish) segment - right side */}
        <path d={arcPath} fill="none" stroke={C.green} strokeWidth="8" strokeLinecap="round"
          opacity="0.7"
          strokeDasharray={`${(bullPct / 100) * Math.PI * radius * 1.1} ${Math.PI * radius * 2}`}
          strokeDashoffset="0"
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
        <text x={cx} y={cy - 8} textAnchor="middle" fill={sentimentColor} fontSize="13" fontFamily="JetBrains Mono" fontWeight="800">
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
