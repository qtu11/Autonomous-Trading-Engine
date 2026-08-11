'use client';

import { useMemo } from 'react';

const C = {
  gold: '#D4B483',
  goldDim: 'rgba(212,175,55,0.12)',
  green: '#22d3a0',
  greenDim: 'rgba(34,211,160,0.15)',
  red: '#f43f5e',
  redDim: 'rgba(244,63,94,0.15)',
  cyan: '#06b6d4',
  cyanDim: 'rgba(6,182,212,0.15)',
  amber: '#f59e0b',
  amberDim: 'rgba(245,158,11,0.15)',
  text: '#f8fafc',
  dim: '#cbd5e1',
  muted: '#64748b',
  border: 'rgba(255,255,255,0.06)',
  mono: '"JetBrains Mono", monospace',
};

interface PerformanceChartsProps {
  winRate?: number; // 0-1
  wins?: number;
  losses?: number;
  maxDrawdown?: number;
  currentDrawdown?: number;
  monthlyReturns?: Array<{ month: string; pnl: number }>;
}

// Pie Chart Component
function PieChart({ wins = 13, losses = 7 }: { wins?: number; losses?: number }) {
  const total = wins + losses;
  const winPercent = total > 0 ? (wins / total) * 100 : 0;
  const lossPercent = 100 - winPercent;

  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference * (1 - winPercent / 100);

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <div style={{ position: 'relative', width: 100, height: 100 }}>
        <svg width="100" height="100" viewBox="0 0 100 100">
          {/* Background circle */}
          <circle cx="50" cy="50" r={radius} fill="none" stroke="rgba(244,63,94,0.3)" strokeWidth="12" />
          {/* Win arc */}
          <circle
            cx="50" cy="50" r={radius}
            fill="none"
            stroke={C.green}
            strokeWidth="12"
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
            strokeLinecap="round"
            transform="rotate(-90 50 50)"
            style={{ transition: 'stroke-dashoffset 0.5s ease' }}
          />
          {/* Center text */}
          <text x="50" y="47" textAnchor="middle" fill={C.text} fontSize="16" fontWeight="800" fontFamily="JetBrains Mono">
            {winPercent.toFixed(0)}%
          </text>
          <text x="50" y="58" textAnchor="middle" fill={C.muted} fontSize="7" fontFamily="JetBrains Mono">
            WIN RATE
          </text>
        </svg>
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
          <div style={{ width: 8, height: 8, borderRadius: 2, background: C.green }} />
          <span style={{ fontSize: 8, fontFamily: C.mono, color: C.muted }}>Wins</span>
          <span style={{ fontSize: 10, fontFamily: C.mono, fontWeight: 700, color: C.green, flex: 1, textAlign: 'right' }}>{wins}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
          <div style={{ width: 8, height: 8, borderRadius: 2, background: C.red }} />
          <span style={{ fontSize: 8, fontFamily: C.mono, color: C.muted }}>Losses</span>
          <span style={{ fontSize: 10, fontFamily: C.mono, fontWeight: 700, color: C.red, flex: 1, textAlign: 'right' }}>{losses}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 8, height: 8, borderRadius: 2, background: C.amber }} />
          <span style={{ fontSize: 8, fontFamily: C.mono, color: C.muted }}>Breakeven</span>
          <span style={{ fontSize: 10, fontFamily: C.mono, fontWeight: 700, color: C.amber, flex: 1, textAlign: 'right' }}>0</span>
        </div>
      </div>
    </div>
  );
}

// Drawdown Chart Component
function DrawdownChart({ maxDD = 12.3, currentDD = 3.2 }: { maxDD?: number; currentDD?: number }) {
  const ddPoints = useMemo(() => {
    const points: number[] = [];
    let dd = 0;
    for (let i = 0; i < 30; i++) {
      dd = Math.min(dd - Math.random() * 2, -0.5);
      if (Math.random() > 0.7) dd = Math.min(dd + Math.random() * 3, 0);
      points.push(dd);
    }
    return points;
  }, []);

  const minDD = Math.min(...ddPoints);

  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ fontSize: 8, fontFamily: C.mono, color: C.muted }}>DRAWDOWN</span>
        <span style={{ fontSize: 8, fontFamily: C.mono, color: C.red }}>Max: -{maxDD?.toFixed(1)}%</span>
      </div>
      <div style={{ height: 60, background: 'rgba(0,0,0,0.3)', borderRadius: 4, border: `1px solid ${C.border}`, position: 'relative', overflow: 'hidden' }}>
        {/* Zero line */}
        <div style={{ position: 'absolute', top: '60%', left: 0, right: 0, height: 1, background: 'rgba(255,255,255,0.1)' }} />
        {/* Area */}
        <svg width="100%" height="100%" preserveAspectRatio="none" viewBox="0 0 100 60">
          <defs>
            <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={C.red} stopOpacity="0.5" />
              <stop offset="100%" stopColor={C.red} stopOpacity="0" />
            </linearGradient>
          </defs>
          <path
            d={ddPoints.reduce((acc, val, i) => {
              const x = (i / (ddPoints.length - 1)) * 100;
              const y = 50 - ((Math.abs(val) / Math.abs(minDD)) * 40);
              return acc + (i === 0 ? `M ${x},${y}` : ` L ${x},${y}`);
            }, '') + ` L 100,50 L 0,50 Z`}
            fill="url(#ddGrad)"
          />
          <path
            d={ddPoints.reduce((acc, val, i) => {
              const x = (i / (ddPoints.length - 1)) * 100;
              const y = 50 - ((Math.abs(val) / Math.abs(minDD)) * 40);
              return acc + (i === 0 ? `M ${x},${y}` : ` L ${x},${y}`);
            }, '')}
            fill="none"
            stroke={C.red}
            strokeWidth="1.5"
          />
        </svg>
      </div>
    </div>
  );
}

// Monthly Returns Bar Chart
function MonthlyReturns({ returns }: { returns?: Array<{ month: string; pnl: number }> }) {
  const data = returns || [
    { month: 'Aug', pnl: 523 },
    { month: 'Jul', pnl: 1245 },
    { month: 'Jun', pnl: -320 },
    { month: 'May', pnl: 892 },
    { month: 'Apr', pnl: 1102 },
  ];

  const maxPnl = Math.max(...data.map(d => Math.abs(d.pnl)), 1);
  const total = data.reduce((s, d) => s + d.pnl, 0);

  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ fontSize: 8, fontFamily: C.mono, color: C.muted }}>MONTHLY RETURNS</span>
        <span style={{ fontSize: 8, fontFamily: C.mono, color: total >= 0 ? C.green : C.red }}>Total: {total >= 0 ? '+' : ''}${total.toFixed(0)}</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height: 60 }}>
        {data.map((item, i) => {
          const height = Math.abs(item.pnl) / maxPnl * 50;
          const isProfit = item.pnl >= 0;
          return (
            <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
              <div style={{ fontSize: 6, fontFamily: C.mono, color: C.muted }}>{item.pnl > 0 ? `+$${item.pnl}` : `-$${Math.abs(item.pnl)}`}</div>
              <div style={{
                width: '100%', height: height + 2, background: isProfit ? C.green : C.red,
                borderRadius: 2, opacity: 0.8,
              }} />
              <div style={{ fontSize: 6, fontFamily: C.mono, color: C.muted }}>{item.month}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Main Component
export default function PerformanceCharts({ winRate = 0.65, wins = 13, losses = 7, maxDrawdown = 12.3, currentDrawdown = 3.2, monthlyReturns }: PerformanceChartsProps) {
  return (
    <div style={{ padding: '0 12px 12px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0', borderBottom: `1px solid ${C.border}`, marginBottom: 8 }}>
        <span style={{ fontSize: 8, fontFamily: C.mono, fontWeight: 800, color: C.gold, letterSpacing: '0.1em' }}>PERFORMANCE</span>
      </div>

      {/* Win Rate Pie */}
      <PieChart wins={wins} losses={losses} />

      {/* Drawdown */}
      <DrawdownChart maxDD={maxDrawdown} currentDD={currentDrawdown} />

      {/* Monthly Returns */}
      <MonthlyReturns returns={monthlyReturns} />

      {/* Quick Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginTop: 12 }}>
        <div style={{ padding: '6px 8px', background: 'rgba(0,0,0,0.3)', borderRadius: 4, border: `1px solid ${C.border}`, textAlign: 'center' }}>
          <div style={{ fontSize: 7, color: C.muted }}>Profit Factor</div>
          <div style={{ fontSize: 12, fontFamily: C.mono, fontWeight: 800, color: C.cyan }}>{(wins / Math.max(losses, 1)).toFixed(2)}</div>
        </div>
        <div style={{ padding: '6px 8px', background: 'rgba(0,0,0,0.3)', borderRadius: 4, border: `1px solid ${C.border}`, textAlign: 'center' }}>
          <div style={{ fontSize: 7, color: C.muted }}>Best Trade</div>
          <div style={{ fontSize: 12, fontFamily: C.mono, fontWeight: 800, color: C.green }}>+${(monthlyReturns ? Math.max(...monthlyReturns.map(r => r.pnl)) : 1245).toFixed(0)}</div>
        </div>
      </div>
    </div>
  );
}
