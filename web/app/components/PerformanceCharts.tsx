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
  liveStats?: null | { wins: number; losses: number; total_pl: number; best_trade: number; max_drawdown: number; };
}

// Pie Chart Component
function PieChart({ wins = 0, losses = 0 }: { wins?: number; losses?: number }) {
  const total = wins + losses;
  const winPercent = total > 0 ? (wins / total) * 100 : 0;
  if (total === 0) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: 8 }}>
        <div style={{ width: 100, height: 100, borderRadius: '50%', background: 'rgba(0,0,0,0.3)', border: `3px dashed ${C.border}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ fontSize: 8, color: C.muted, fontFamily: C.mono }}>NO DATA</span>
        </div>
        <div style={{ flex: 1, fontSize: 8, color: C.muted, fontFamily: C.mono }}>
          Close trades to see win rate.
        </div>
      </div>
    );
  }
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
// BUG FIX: trước đây tự sinh đường drawdown giả bằng Math.random() — đồ thị không
// liên quan dữ liệu thật. Giờ vẽ đường determinist từ maxDD thật; khi không có dữ
// liệu thì hiện NO DATA thay vì đường ngẫu nhiên.
function DrawdownChart({ maxDD = 0, currentDD = 0 }: { maxDD?: number; currentDD?: number }) {
  const absMax = Math.abs(Number(maxDD) || 0);
  const ddPoints = useMemo(() => {
    if (absMax <= 0) return [] as number[];
    const pts: number[] = [];
    // Đường cong determinist tới độ sâu maxDD (không dùng Math.random)
    for (let i = 0; i < 30; i++) {
      const depth = absMax * (0.3 + 0.7 * Math.abs(Math.sin((i / 29) * Math.PI * 0.85 + 0.5)));
      pts.push(-Math.min(depth, absMax));
    }
    return pts;
  }, [absMax]);

  const minDD = ddPoints.length ? Math.min(...ddPoints) : -1;

  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ fontSize: 8, fontFamily: C.mono, color: C.muted }}>MAX DRAWDOWN</span>
        <span style={{ fontSize: 8, fontFamily: C.mono, color: C.red }}>{absMax > 0 ? `$${absMax.toFixed(1)}` : 'NO DATA'}</span>
      </div>
      <div style={{ height: 60, background: 'rgba(0,0,0,0.3)', borderRadius: 4, border: `1px solid ${C.border}`, position: 'relative', overflow: 'hidden' }}>
        {/* Zero line */}
        <div style={{ position: 'absolute', top: '60%', left: 0, right: 0, height: 1, background: 'rgba(255,255,255,0.1)' }} />
        {ddPoints.length === 0 ? (
          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 8, fontFamily: C.mono, color: C.muted }}>
            Close losing trades to see drawdown
          </div>
        ) : (
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
        )}
      </div>
    </div>
  );
}

// Monthly Returns Bar Chart
// BUG FIX: trước đây hiện 5 tháng dữ liệu FAKE (Aug/Jul/Jun...) khi không có props
// — giờ hiện NO DATA khi chưa có lịch sử thật.
function MonthlyReturns({ returns }: { returns?: Array<{ month: string; pnl: number }> }) {
  const data = (returns || []).filter(d => d && typeof d.pnl === 'number');
  if (data.length === 0) {
    return (
      <div style={{ marginTop: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
          <span style={{ fontSize: 8, fontFamily: C.mono, color: C.muted }}>MONTHLY RETURNS</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 60, background: 'rgba(0,0,0,0.3)', borderRadius: 4, border: `1px solid ${C.border}`, fontSize: 8, fontFamily: C.mono, color: C.muted }}>
          NO DATA
        </div>
      </div>
    );
  }

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
export default function PerformanceCharts({ winRate, wins, losses, maxDrawdown, currentDrawdown, monthlyReturns, liveStats }: PerformanceChartsProps) {
  // Prefer live data over mocks
  const _wins = liveStats?.wins ?? wins ?? 0;
  const _losses = liveStats?.losses ?? losses ?? 0;
  const _maxDD = liveStats?.max_drawdown ?? maxDrawdown ?? 0;
  const _best = liveStats?.best_trade ?? (monthlyReturns ? Math.max(...monthlyReturns.map(r => r.pnl)) : 0);
  const _total = liveStats?.total_pl ?? (monthlyReturns ? monthlyReturns.reduce((s, d) => s + d.pnl, 0) : 0);
  // BUG FIX: profit factor = wins/losses; khi chưa có lệnh thua hiển thị ∞ thay vì wins
  const _profFactor = _losses > 0 ? (_wins / _losses).toFixed(2) : '∞';
  return (
    <div style={{ padding: '0 12px 12px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0', borderBottom: `1px solid ${C.border}`, marginBottom: 8 }}>
        <span style={{ fontSize: 8, fontFamily: C.mono, fontWeight: 800, color: C.gold, letterSpacing: '0.1em' }}>PERFORMANCE</span>
      </div>

      {/* Win Rate Pie */}
      <PieChart wins={_wins} losses={_losses} />

      {/* Drawdown */}
      <DrawdownChart maxDD={_maxDD} currentDD={currentDrawdown || 0} />

      {/* Monthly Returns */}
      <MonthlyReturns returns={monthlyReturns} />

      {/* Quick Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginTop: 12 }}>
        <div style={{ padding: '6px 8px', background: 'rgba(0,0,0,0.3)', borderRadius: 4, border: `1px solid ${C.border}`, textAlign: 'center' }}>
          <div style={{ fontSize: 7, color: C.muted }}>Profit Factor</div>
          <div style={{ fontSize: 12, fontFamily: C.mono, fontWeight: 800, color: C.cyan }}>{_profFactor}</div>
        </div>
        <div style={{ padding: '6px 8px', background: 'rgba(0,0,0,0.3)', borderRadius: 4, border: `1px solid ${C.border}`, textAlign: 'center' }}>
          <div style={{ fontSize: 7, color: C.muted }}>Best Trade</div>
          <div style={{ fontSize: 12, fontFamily: C.mono, fontWeight: 800, color: C.green }}>{_best > 0 ? `+$${_best.toFixed(0)}` : '—'}</div>
        </div>
      </div>
    </div>
  );
}
