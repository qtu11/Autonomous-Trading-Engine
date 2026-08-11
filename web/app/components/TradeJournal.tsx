'use client';

import { useState, useMemo } from 'react';

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
  text: '#f8fafc',
  dim: '#cbd5e1',
  muted: '#64748b',
  border: 'rgba(255,255,255,0.06)',
  mono: '"JetBrains Mono", monospace',
};

interface JournalEntry {
  id: string;
  symbol: string;
  type: 'BUY' | 'SELL';
  entryPrice: number;
  exitPrice: number;
  sl: number;
  tp: number;
  volume: number;
  pnl: number;
  pips: number;
  duration: string;
  timestamp: string;
  aiNotes?: string;
  tags: string[];
}

interface TradeJournalProps {
  entries?: JournalEntry[];
}

const DEMO_ENTRIES: JournalEntry[] = [
  {
    id: '1',
    symbol: 'XAUUSD',
    type: 'BUY',
    entryPrice: 2835.50,
    exitPrice: 2860.00,
    sl: 2825.00,
    tp: 2860.00,
    volume: 0.20,
    pnl: 490,
    pips: 245,
    duration: '4h 23m',
    timestamp: '2024-01-15 14:30',
    aiNotes: 'Break of structure bullish confirmed. RSI showing bullish divergence on H4. Risk:Reward 2.3:1 achieved.',
    tags: ['BOS', 'RSI_DIVERGENCE', 'H4'],
  },
  {
    id: '2',
    symbol: 'XAUUSD',
    type: 'SELL',
    entryPrice: 2865.00,
    exitPrice: 2850.00,
    sl: 2875.00,
    tp: 2845.00,
    volume: 0.15,
    pnl: 225,
    pips: 150,
    duration: '2h 45m',
    timestamp: '2024-01-15 09:15',
    aiNotes: 'Rejection from EMA200 resistance. FVG bearish detected on M15. Quick scalp targeting previous support.',
    tags: ['EMA_REJECTION', 'FVG', 'M15'],
  },
  {
    id: '3',
    symbol: 'EURUSD',
    type: 'BUY',
    entryPrice: 1.0820,
    exitPrice: 1.0780,
    sl: 1.0800,
    tp: 1.0860,
    volume: 0.50,
    pnl: -200,
    pips: -40,
    duration: '1h 10m',
    timestamp: '2024-01-14 16:45',
    aiNotes: 'Trade stopped out. Market moved against initial bias. News impact from NFP stronger than expected.',
    tags: ['STOP_LOSS', 'NFP'],
  },
];

export default function TradeJournal({ entries = DEMO_ENTRIES }: TradeJournalProps) {
  const [filterTag, setFilterTag] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Get all unique tags
  const allTags = useMemo(() => {
    const tags = new Set<string>();
    entries.forEach(e => e.tags.forEach(t => tags.add(t)));
    return Array.from(tags);
  }, [entries]);

  // Filter entries
  const filteredEntries = useMemo(() => {
    if (!filterTag) return entries;
    return entries.filter(e => e.tags.includes(filterTag!));
  }, [entries, filterTag]);

  // Stats
  const stats = useMemo(() => {
    const wins = entries.filter(e => e.pnl > 0).length;
    const losses = entries.filter(e => e.pnl < 0).length;
    const total = entries.reduce((s, e) => s + e.pnl, 0);
    return { wins, losses, total };
  }, [entries]);

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{ padding: '10px 12px', borderBottom: `1px solid ${C.border}` }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <span style={{ fontSize: 8, fontFamily: C.mono, fontWeight: 800, color: C.gold, letterSpacing: '0.1em' }}>TRADE JOURNAL</span>
          <div style={{ display: 'flex', gap: 8, fontSize: 8, fontFamily: C.mono }}>
            <span style={{ color: C.green }}>W: {stats.wins}</span>
            <span style={{ color: C.red }}>L: {stats.losses}</span>
            <span style={{ color: stats.total >= 0 ? C.green : C.red }}>P&L: ${stats.total}</span>
          </div>
        </div>

        {/* Tags Filter */}
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          <button
            onClick={() => setFilterTag(null)}
            style={{
              padding: '2px 6px', fontSize: 7, fontFamily: C.mono, cursor: 'pointer',
              background: !filterTag ? C.goldDim : 'transparent',
              border: `1px solid ${!filterTag ? C.gold : C.border}`, borderRadius: 3,
              color: !filterTag ? C.gold : C.muted,
            }}
          >
            ALL
          </button>
          {allTags.map(tag => (
            <button
              key={tag}
              onClick={() => setFilterTag(tag === filterTag ? null : tag)}
              style={{
                padding: '2px 6px', fontSize: 7, fontFamily: C.mono, cursor: 'pointer',
                background: filterTag === tag ? C.blueDim : 'transparent',
                border: `1px solid ${filterTag === tag ? C.blue : C.border}`, borderRadius: 3,
                color: filterTag === tag ? C.blue : C.muted,
              }}
            >
              #{tag}
            </button>
          ))}
        </div>
      </div>

      {/* Entries List */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 8 }}>
        {filteredEntries.length === 0 ? (
          <div style={{ textAlign: 'center', color: C.muted, fontSize: 9, fontFamily: C.mono, padding: 20 }}>
            No trades found
          </div>
        ) : (
          filteredEntries.map(entry => {
            const isProfit = entry.pnl >= 0;
            const isExpanded = expandedId === entry.id;
            return (
              <div
                key={entry.id}
                style={{
                  background: 'rgba(0,0,0,0.3)', border: `1px solid ${C.border}`, borderRadius: 8,
                  marginBottom: 8, overflow: 'hidden',
                }}
              >
                {/* Entry Header */}
                <div
                  onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                  style={{
                    padding: '10px 12px', cursor: 'pointer',
                    background: isExpanded ? 'rgba(0,0,0,0.5)' : 'transparent',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{
                        fontSize: 8, fontFamily: C.mono, fontWeight: 700,
                        color: entry.type === 'BUY' ? C.green : C.red,
                      }}>
                        {entry.type === 'BUY' ? '▲' : '▼'} {entry.symbol}
                      </span>
                      <span style={{ fontSize: 7, fontFamily: C.mono, color: C.muted }}>
                        {entry.volume} lots
                      </span>
                    </div>
                    <span style={{
                      fontSize: 12, fontFamily: C.mono, fontWeight: 800,
                      color: isProfit ? C.green : C.red,
                    }}>
                      {isProfit ? '+' : ''}${entry.pnl}
                    </span>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 8, fontFamily: C.mono }}>
                    <span style={{ color: C.muted }}>
                      {entry.entryPrice.toFixed(2)} → {entry.exitPrice.toFixed(2)}
                    </span>
                    <span style={{ color: C.cyan }}>{isProfit ? '+' : ''}{entry.pips} pips</span>
                    <span style={{ color: C.muted }}>{entry.duration}</span>
                  </div>
                </div>

                {/* Expanded Details */}
                {isExpanded && (
                  <div style={{ padding: '0 12px 12px', borderTop: `1px solid ${C.border}` }}>
                    {/* AI Notes */}
                    {entry.aiNotes && (
                      <div style={{ marginTop: 10 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke={C.cyan} strokeWidth="2">
                            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
                          </svg>
                          <span style={{ fontSize: 7, fontFamily: C.mono, color: C.cyan, fontWeight: 700 }}>AI ANALYSIS</span>
                        </div>
                        <div style={{
                          background: 'rgba(6,182,212,0.1)', borderRadius: 6, padding: 10,
                          border: `1px solid rgba(6,182,212,0.2)`,
                        }}>
                          <span style={{ fontSize: 9, fontFamily: C.mono, color: C.dim, lineHeight: 1.5 }}>
                            {entry.aiNotes}
                          </span>
                        </div>
                      </div>
                    )}

                    {/* Entry Details */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6, marginTop: 10 }}>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: 7, color: C.muted, fontFamily: C.mono }}>Entry</div>
                        <div style={{ fontSize: 10, fontFamily: C.mono, fontWeight: 700, color: C.text }}>{entry.entryPrice.toFixed(2)}</div>
                      </div>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: 7, color: C.muted, fontFamily: C.mono }}>Exit</div>
                        <div style={{ fontSize: 10, fontFamily: C.mono, fontWeight: 700, color: C.text }}>{entry.exitPrice.toFixed(2)}</div>
                      </div>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: 7, color: C.muted, fontFamily: C.mono }}>SL</div>
                        <div style={{ fontSize: 10, fontFamily: C.mono, fontWeight: 700, color: C.red }}>{entry.sl.toFixed(2)}</div>
                      </div>
                    </div>

                    {/* Tags */}
                    <div style={{ display: 'flex', gap: 4, marginTop: 10, flexWrap: 'wrap' }}>
                      {entry.tags.map(tag => (
                        <span
                          key={tag}
                          onClick={() => setFilterTag(tag)}
                          style={{
                            fontSize: 7, fontFamily: C.mono, padding: '2px 8px',
                            background: C.blueDim, border: `1px solid ${C.blue}`, borderRadius: 10,
                            color: C.blue, cursor: 'pointer',
                          }}
                        >
                          #{tag}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
