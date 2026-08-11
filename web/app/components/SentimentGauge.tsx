'use client';

import { useMemo } from 'react';

const C = {
  gold: '#D4B483',
  green: '#22d3a0',
  greenDim: 'rgba(34,211,160,0.15)',
  red: '#f43f5e',
  redDim: 'rgba(244,63,94,0.15)',
  amber: '#f59e0b',
  amberDim: 'rgba(245,158,11,0.15)',
  text: '#f8fafc',
  dim: '#cbd5e1',
  muted: '#64748b',
  border: 'rgba(255,255,255,0.06)',
  mono: '"JetBrains Mono", monospace',
};

interface SentimentGaugeProps {
  bullishPercent?: number; // 0-100
  bearishPercent?: number; // 0-100
  label?: string;
}

export default function SentimentGauge({ bullishPercent = 65, bearishPercent = 35, label }: SentimentGaugeProps) {
  // Calculate needle angle (0% = left, 100% = right)
  const angle = (bullishPercent / 100) * 180 - 90;
  
  // Color based on sentiment
  const getSentimentColor = (pct: number) => {
    if (pct >= 70) return C.green;
    if (pct >= 50) return '#84cc16'; // lime
    if (pct >= 30) return C.amber;
    return C.red;
  };
  
  const sentimentColor = getSentimentColor(bullishPercent);
  const sentimentLabel = bullishPercent >= 70 ? 'VERY BULLISH' : bullishPercent >= 55 ? 'BULLISH' : bullishPercent >= 45 ? 'NEUTRAL' : bullishPercent >= 30 ? 'BEARISH' : 'VERY BEARISH';

  // Arc path calculation
  const radius = 45;
  const cx = 60;
  const cy = 60;
  
  const startAngle = -90;
  const endAngle = 90;
  const startRad = (startAngle * Math.PI) / 180;
  const endRad = (endAngle * Math.PI) / 180;
  
  const x1 = cx + radius * Math.cos(startRad);
  const y1 = cy + radius * Math.sin(startRad);
  const x2 = cx + radius * Math.cos(endRad);
  const y2 = cy + radius * Math.sin(endRad);
  
  const arcPath = `M ${x1} ${y1} A ${radius} ${radius} 0 1 1 ${x2} ${y2}`;

  // Needle calculation
  const needleRad = ((angle + 90) * Math.PI) / 180;
  const needleLength = radius - 10;
  const needleX = cx + needleLength * Math.cos(needleRad);
  const needleY = cy + needleLength * Math.sin(needleRad);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: 12 }}>
      {/* Label */}
      {label && (
        <div style={{ fontSize: 8, fontFamily: C.mono, fontWeight: 800, color: C.gold, letterSpacing: '0.1em', marginBottom: 8 }}>
          {label}
        </div>
      )}
      
      {/* Gauge */}
      <svg width="120" height="80" viewBox="0 0 120 80">
        {/* Background arc */}
        <path d={arcPath} fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="8" strokeLinecap="round" />
        
        {/* Colored segments */}
        {/* Red segment (bearish) */}
        <path d={arcPath} fill="none" stroke={C.red} strokeWidth="8" strokeLinecap="round" 
          strokeDasharray={`${(endRad - startRad) * radius * (bearishPercent / 100)} ${(endRad - startRad) * radius}`}
          strokeDashoffset="0"
          opacity="0.6"
        />
        
        {/* Green segment (bullish) */}
        <path d={arcPath} fill="none" stroke={C.green} strokeWidth="8" strokeLinecap="round"
          strokeDasharray={`${(endRad - startRad) * radius * (bullishPercent / 100)} ${(endRad - startRad) * radius}`}
          strokeDashoffset={`-${(endRad - startRad) * radius * (bearishPercent / 100)}`}
          opacity="0.8"
        />
        
        {/* Needle */}
        <line 
          x1={cx} y1={cy} 
          x2={needleX} y2={needleY}
          stroke={sentimentColor}
          strokeWidth="2"
          strokeLinecap="round"
        />
        
        {/* Center circle */}
        <circle cx={cx} cy={cy} r={5} fill={sentimentColor} />
        
        {/* Labels */}
        <text x={cx - 35} y={cy + 25} fill={C.muted} fontSize="7" fontFamily="JetBrains Mono" fontWeight="600">BEAR</text>
        <text x={cx + 20} y={cy + 25} fill={C.muted} fontSize="7" fontFamily="JetBrains Mono" fontWeight="600">BULL</text>
        
        {/* Center percentage */}
        <text x={cx} y={cy - 8} textAnchor="middle" fill={sentimentColor} fontSize="12" fontFamily="JetBrains Mono" fontWeight="800">
          {bullishPercent}%
        </text>
      </svg>
      
      {/* Sentiment Label */}
      <div style={{
        marginTop: 4,
        padding: '4px 12px',
        background: `${sentimentColor}20`,
        border: `1px solid ${sentimentColor}`,
        borderRadius: 12,
      }}>
        <span style={{ fontSize: 8, fontFamily: C.mono, fontWeight: 700, color: sentimentColor }}>
          {sentimentLabel}
        </span>
      </div>
      
      {/* Stats */}
      <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: 8, fontFamily: C.mono }}>
        <span style={{ color: C.green }}>▲ {bullishPercent}%</span>
        <span style={{ color: C.red }}>▼ {bearishPercent}%</span>
      </div>
    </div>
  );
}
