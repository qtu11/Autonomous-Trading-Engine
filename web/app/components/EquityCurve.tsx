'use client';

import { useMemo, useRef, useEffect, useState } from 'react';

const C = {
  gold: '#D4B483',
  goldDim: 'rgba(212,175,55,0.12)',
  green: '#22d3a0',
  greenDim: 'rgba(34,211,160,0.15)',
  red: '#f43f5e',
  redDim: 'rgba(244,63,94,0.15)',
  cyan: '#06b6d4',
  text: '#f8fafc',
  dim: '#cbd5e1',
  muted: '#64748b',
  border: 'rgba(255,255,255,0.06)',
  mono: '"JetBrains Mono", monospace',
};

// Generate sample equity curve data
function generateEquityCurve(period: '1D' | '1W' | '1M' | '3M' | 'ALL') {
  const points: Array<{ time: string; value: number }> = [];
  let value = 10000;
  const now = new Date();
  
  let days = period === '1D' ? 1 : period === '1W' ? 7 : period === '1M' ? 30 : period === '3M' ? 90 : 365;
  
  for (let i = days; i >= 0; i--) {
    const date = new Date(now);
    date.setDate(date.getDate() - i);
    value += (Math.random() - 0.45) * 100;
    value = Math.max(value, 9000);
    points.push({
      time: date.toISOString().split('T')[0],
      value: Math.round(value * 100) / 100,
    });
  }
  return points;
}

interface EquityCurveProps {
  initialBalance?: number;
  currentEquity?: number;
  period?: '1D' | '1W' | '1M' | '3M' | 'ALL';
  onPeriodChange?: (period: '1D' | '1W' | '1M' | '3M' | 'ALL') => void;
}

export default function EquityCurve({ initialBalance = 10000, currentEquity = 10500, period = '1M', onPeriodChange }: EquityCurveProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<'1D' | '1W' | '1M' | '3M' | 'ALL'>(period);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const data = useMemo(() => generateEquityCurve(selectedPeriod), [selectedPeriod]);

  const handlePeriodChange = (p: '1D' | '1W' | '1M' | '3M' | 'ALL') => {
    setSelectedPeriod(p);
    onPeriodChange?.(p);
  };

  // Draw chart
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * 2;
    canvas.height = rect.height * 2;
    ctx.scale(2, 2);

    const width = rect.width;
    const height = rect.height;
    const padding = { top: 10, right: 10, bottom: 20, left: 10 };

    // Clear
    ctx.clearRect(0, 0, width, height);

    if (data.length < 2) return;

    const min = Math.min(...data.map(d => d.value)) * 0.995;
    const max = Math.max(...data.map(d => d.value)) * 1.005;
    const range = max - min || 1;

    const xScale = (width - padding.left - padding.right) / (data.length - 1);
    const yScale = (height - padding.top - padding.bottom) / range;

    const getX = (i: number) => padding.left + i * xScale;
    const getY = (v: number) => height - padding.bottom - (v - min) * yScale;

    // Draw grid lines
    ctx.strokeStyle = 'rgba(255,255,255,0.03)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = padding.top + (height - padding.top - padding.bottom) * (i / 4);
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();
    }

    // Draw gradient fill
    const gradient = ctx.createLinearGradient(0, padding.top, 0, height - padding.bottom);
    const isProfit = data[data.length - 1].value >= data[0].value;
    gradient.addColorStop(0, isProfit ? 'rgba(34,211,160,0.3)' : 'rgba(244,63,94,0.3)');
    gradient.addColorStop(1, 'rgba(0,0,0,0)');

    ctx.beginPath();
    ctx.moveTo(getX(0), getY(data[0].value));
    data.forEach((d, i) => ctx.lineTo(getX(i), getY(d.value)));
    ctx.lineTo(getX(data.length - 1), height - padding.bottom);
    ctx.lineTo(getX(0), height - padding.bottom);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // Draw line
    ctx.beginPath();
    ctx.moveTo(getX(0), getY(data[0].value));
    data.forEach((d, i) => ctx.lineTo(getX(i), getY(d.value)));
    ctx.strokeStyle = isProfit ? C.green : C.red;
    ctx.lineWidth = 2;
    ctx.stroke();

    // Draw current point
    const lastX = getX(data.length - 1);
    const lastY = getY(data[data.length - 1].value);
    ctx.beginPath();
    ctx.arc(lastX, lastY, 4, 0, Math.PI * 2);
    ctx.fillStyle = isProfit ? C.green : C.red;
    ctx.fill();
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Draw start point
    ctx.beginPath();
    ctx.arc(getX(0), getY(data[0].value), 3, 0, Math.PI * 2);
    ctx.fillStyle = C.gold;
    ctx.fill();

    // Labels
    ctx.font = '8px "JetBrains Mono", monospace';
    ctx.fillStyle = C.muted;
    ctx.textAlign = 'left';
    ctx.fillText(`$${max.toLocaleString()}`, padding.left, padding.top - 2);
    ctx.textAlign = 'left';
    ctx.fillText(`$${min.toLocaleString()}`, padding.left, height - padding.bottom + 12);

  }, [data]);

  const change = currentEquity - initialBalance;
  const changePercent = ((change / initialBalance) * 100).toFixed(2);
  const isProfit = change >= 0;

  return (
    <div style={{ padding: '0 12px 12px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0', borderBottom: `1px solid ${C.border}`, marginBottom: 8 }}>
        <span style={{ fontSize: 8, fontFamily: C.mono, fontWeight: 800, color: C.gold, letterSpacing: '0.1em' }}>EQUITY CURVE</span>
        <div style={{ display: 'flex', gap: 4 }}>
          {(['1D', '1W', '1M', '3M', 'ALL'] as const).map(p => (
            <button
              key={p}
              onClick={() => handlePeriodChange(p)}
              style={{
                padding: '2px 6px', fontSize: 7, fontFamily: C.mono, cursor: 'pointer',
                background: selectedPeriod === p ? C.goldDim : 'transparent',
                border: `1px solid ${selectedPeriod === p ? C.gold : C.border}`,
                borderRadius: 3, color: selectedPeriod === p ? C.gold : C.muted,
              }}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Stats */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 7, color: C.muted, fontFamily: C.mono, marginBottom: 2 }}>CURRENT</div>
          <div style={{ fontSize: 14, fontFamily: C.mono, fontWeight: 800, color: C.text }}>${currentEquity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>

        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 7, color: C.muted, fontFamily: C.mono, marginBottom: 2 }}>CHANGE</div>
          <div style={{ fontSize: 14, fontFamily: C.mono, fontWeight: 800, color: isProfit ? C.green : C.red }}>
            {isProfit ? '+' : ''}{change.toFixed(2)} ({isProfit ? '+' : ''}{changePercent}%)
          </div>
        </div>
      </div>

      {/* Chart */}
      <canvas
        ref={canvasRef}
        style={{ width: '100%', height: 120, background: 'rgba(0,0,0,0.2)', borderRadius: 6, border: `1px solid ${C.border}` }}
      />

      {/* Period label */}
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 7, fontFamily: C.mono, color: C.muted, marginTop: 4 }}>
        <span>{data[0]?.time}</span>
        <span>{data[data.length - 1]?.time}</span>
      </div>
    </div>
  );
}
