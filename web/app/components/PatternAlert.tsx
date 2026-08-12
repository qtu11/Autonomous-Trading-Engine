'use client';

import { useState, useEffect, useCallback } from 'react';

const C = {
  gold: '#D4B483',
  goldDim: 'rgba(212,175,55,0.12)',
  green: '#22d3a0',
  greenDim: 'rgba(34,211,160,0.15)',
  red: '#f43f5e',
  redDim: 'rgba(244,63,94,0.15)',
  blue: '#38bdf8',
  blueDim: 'rgba(56,189,248,0.15)',
  cyan: '#06b6d4',
  amber: '#f59e0b',
  amberDim: 'rgba(245,158,11,0.15)',
  purple: '#a855f7',
  text: '#f8fafc',
  dim: '#cbd5e1',
  muted: '#64748b',
  border: 'rgba(255,255,255,0.06)',
  mono: '"JetBrains Mono", monospace',
};

interface Pattern {
  id: number;
  type: string;
  direction: 'BULLISH' | 'BEARISH';
  symbol: string;
  price: number;
  size: number;
  time: string;
  pattern: string;
}

interface PatternAlertProps {
  patterns?: Pattern[];
  onViewChart?: (pattern: Pattern) => void;
  inlineBelow?: boolean; // when true, position below chart instead of overlay
}

export default function PatternAlert({ patterns = [], onViewChart }: PatternAlertProps) {
  const [alerts, setAlerts] = useState<Pattern[]>([]);
  const [showAll, setShowAll] = useState(false);

  const dismissAlert = useCallback((id: number) => {
    setAlerts(prev => prev.filter(a => a.id !== id));
  }, []);

  // Fetch real patterns from backend every 30s
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const token = localStorage.getItem('quantai_auth_token') || '';
        const headers: Record<string, string> = token && token !== 'authenticated' ? { Authorization: `Bearer ${token}` } : {};
        const res = await fetch('/api/patterns?symbol=XAUUSD&tf=M15', { headers, credentials: 'same-origin' });
        if (!res.ok || cancelled) return;
        const data = await res.json();
        const items = Array.isArray(data) ? data : (Array.isArray(data?.patterns) ? data.patterns : []);
        if (items.length > 0) {
          setAlerts(items.slice(0, 5));
        }

      } catch { /* silent */ }
    };
    load();
    const id = setInterval(load, 30000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  const getPatternColor = (direction: string) => direction === 'BULLISH' ? C.green : C.red;
  const getPatternBg = (direction: string) => direction === 'BULLISH' ? C.greenDim : C.redDim;

  const displayAlerts = showAll ? alerts : alerts.slice(0, 3);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: 8, width: '100%', height: '100%', overflowY: 'auto', boxSizing: 'border-box' }}>
      {displayAlerts.length === 0 && (
        <div style={{
          background: 'rgba(8,12,22,0.95)',
          border: `1px solid ${C.border}`,
          borderRadius: 8, padding: 12, textAlign: 'center',
        }}>
          <span style={{ fontSize: 8, fontFamily: C.mono, color: C.muted }}>No pattern alerts</span>
        </div>
      )}

      {displayAlerts.map(alert => (
        <div
          key={alert.id}
          style={{
            background: 'rgba(8,12,22,0.98)',
            border: `1px solid ${getPatternColor(alert.direction)}`,
            borderRadius: 8,
            padding: 12,
            boxShadow: `0 8px 32px rgba(0,0,0,0.5), 0 0 20px ${getPatternColor(alert.direction)}20`,
            animation: 'slideIn 0.3s ease',
          }}
        >
          {/* Header */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: getPatternColor(alert.direction), boxShadow: `0 0 8px ${getPatternColor(alert.direction)}` }} />
              <span style={{ fontSize: 9, fontFamily: C.mono, fontWeight: 700, color: getPatternColor(alert.direction) }}>
                {alert.direction === 'BULLISH' ? '▲ BULLISH' : '▼ BEARISH'}
              </span>
            </div>
            <div style={{ display: 'flex', gap: 4 }}>
              <span style={{ fontSize: 7, fontFamily: C.mono, color: C.muted, background: 'rgba(0,0,0,0.3)', padding: '2px 6px', borderRadius: 3 }}>{alert.time}</span>
              <button onClick={() => dismissAlert(alert.id)} style={{
                background: 'transparent', border: 'none', color: C.muted, cursor: 'pointer', fontSize: 12, padding: '0 4px',
              }}>×</button>
            </div>
          </div>

          {/* Pattern Info */}
          <div style={{ background: getPatternBg(alert.direction), borderRadius: 6, padding: 8, marginBottom: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span style={{ fontSize: 10, fontFamily: C.mono, fontWeight: 800, color: C.text }}>{alert.pattern}</span>
              <span style={{ fontSize: 7, fontFamily: C.mono, color: C.gold, background: C.goldDim, padding: '2px 6px', borderRadius: 3 }}>{alert.type}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 8, fontFamily: C.mono }}>
              <span style={{ color: C.muted }}>{alert.symbol}</span>
              <span style={{ color: C.text }}>${alert.price.toLocaleString()}</span>
              <span style={{ color: C.muted }}>Size: {alert.size} pips</span>
            </div>
          </div>

          {/* Actions */}
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => onViewChart?.(alert)} style={{
              flex: 1, padding: '6px 10px', background: C.goldDim, border: `1px solid ${C.gold}`,
              borderRadius: 6, color: C.gold, fontSize: 8, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer',
            }}>
              VIEW CHART
            </button>
            <button onClick={() => dismissAlert(alert.id)} style={{
              padding: '6px 10px', background: 'transparent', border: `1px solid ${C.border}`,
              borderRadius: 6, color: C.muted, fontSize: 8, fontFamily: C.mono, cursor: 'pointer',
            }}>
              DISMISS
            </button>
          </div>
        </div>
      ))}

      {/* Show More */}
      {alerts.length > 3 && (
        <button onClick={() => setShowAll(!showAll)} style={{
          background: 'rgba(0,0,0,0.5)', border: `1px solid ${C.border}`, borderRadius: 6,
          color: C.muted, fontSize: 8, fontFamily: C.mono, padding: '6px', cursor: 'pointer',
        }}>
          {showAll ? 'SHOW LESS' : `+${alerts.length - 3} MORE ALERTS`}
        </button>
      )}
    </div>
  );
}
