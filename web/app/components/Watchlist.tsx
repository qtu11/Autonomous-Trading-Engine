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

// Default watchlist data
const DEFAULT_SYMBOLS = [
  { symbol: 'XAUUSD', name: 'Gold', price: 2845.50, change: 0.85, type: 'CRYPTO' },
  { symbol: 'EURUSD', name: 'Euro', price: 1.0845, change: 0.12, type: 'FOREX' },
  { symbol: 'GBPUSD', name: 'Pound', price: 1.2650, change: -0.05, type: 'FOREX' },
  { symbol: 'USDJPY', name: 'Yen', price: 149.80, change: 0.15, type: 'FOREX' },
  { symbol: 'AUDUSD', name: 'Aussie', price: 0.6540, change: 0.08, type: 'FOREX' },
  { symbol: 'USDCAD', name: 'Loonie', price: 1.3650, change: -0.02, type: 'FOREX' },
];

// Correlation data (simplified)
const CORRELATION_MATRIX = [
  ['XAUUSD', 1.0, 0.2, 0.3, 0.1, 0.4],
  ['EURUSD', 0.2, 1.0, 0.9, -0.8, -0.3],
  ['GBPUSD', 0.3, 0.9, 1.0, -0.7, -0.2],
  ['USDJPY', 0.1, -0.8, -0.7, 1.0, 0.5],
  ['AUDUSD', 0.4, -0.3, -0.2, 0.5, 1.0],
];

interface WatchlistProps {
  onSymbolSelect?: (symbol: string) => void;
  selectedSymbol?: string;
}

export default function Watchlist({ onSymbolSelect, selectedSymbol = 'XAUUSD' }: WatchlistProps) {
  const [filter, setFilter] = useState('');
  const [showCorrelation, setShowCorrelation] = useState(false);

  const filteredSymbols = useMemo(() => {
    if (!filter) return DEFAULT_SYMBOLS;
    return DEFAULT_SYMBOLS.filter(s =>
      s.symbol.toLowerCase().includes(filter.toLowerCase()) ||
      s.name.toLowerCase().includes(filter.toLowerCase())
    );
  }, [filter]);

  const getCorrelationColor = (value: number) => {
    if (value >= 0.7) return C.green;
    if (value >= 0.3) return 'rgba(34,211,160,0.5)';
    if (value >= -0.3) return C.muted;
    if (value >= -0.7) return 'rgba(244,63,94,0.5)';
    return C.red;
  };

  return (
    <div style={{ padding: '0 12px 12px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0', borderBottom: `1px solid ${C.border}`, marginBottom: 8 }}>
        <span style={{ fontSize: 8, fontFamily: C.mono, fontWeight: 800, color: C.gold, letterSpacing: '0.1em' }}>WATCHLIST</span>
        <button onClick={() => setShowCorrelation(!showCorrelation)} style={{
          fontSize: 7, fontFamily: C.mono, padding: '2px 6px', background: showCorrelation ? C.goldDim : 'transparent',
          border: `1px solid ${showCorrelation ? C.gold : C.border}`, borderRadius: 3, color: showCorrelation ? C.gold : C.muted, cursor: 'pointer',
        }}>CORR</button>
      </div>

      {/* Filter */}
      <div style={{ marginBottom: 8 }}>
        <input
          type="text"
          placeholder="Search symbol..."
          value={filter}
          onChange={e => setFilter(e.target.value)}
          style={{
            width: '100%', padding: '6px 8px', background: 'rgba(0,0,0,0.5)',
            border: `1px solid ${C.border}`, borderRadius: 4, color: C.text,
            fontSize: 9, fontFamily: C.mono, outline: 'none',
          }}
        />
      </div>

      {/* Correlation Matrix */}
      {showCorrelation && (
        <div style={{ background: 'rgba(0,0,0,0.3)', borderRadius: 6, padding: 8, marginBottom: 8, border: `1px solid ${C.border}`, overflowX: 'auto' }}>
          <div style={{ fontSize: 7, color: C.muted, fontFamily: C.mono, marginBottom: 6 }}>CORRELATION MATRIX</div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 8, fontFamily: C.mono }}>
            <thead>
              <tr>
                <th style={{ color: C.muted, textAlign: 'left', padding: '2px 4px' }}></th>
                {CORRELATION_MATRIX.map((row, i) => (
                  <th key={i} style={{ color: C.gold, textAlign: 'center', padding: '2px 4px' }}>{row[0]}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {CORRELATION_MATRIX.map((row, i) => (
                <tr key={i}>
                  <td style={{ color: C.gold, padding: '2px 4px' }}>{row[0]}</td>
                  {row.slice(1).map((val, j) => (
                    <td key={j} style={{ textAlign: 'center', padding: '2px 4px' }}>
                      <div style={{
                        display: 'inline-block', width: 24, height: 24, borderRadius: 4,
                        background: getCorrelationColor(val as number),
                        color: Math.abs(val as number) > 0.3 ? '#fff' : C.muted,
                        fontWeight: 700, lineHeight: '24px', fontSize: 7,
                      }}>
                        {(val as number).toFixed(1)}
                      </div>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ display: 'flex', gap: 8, marginTop: 6, fontSize: 7, fontFamily: C.mono }}>
            <span style={{ color: C.green }}>■ Positive</span>
            <span style={{ color: C.red }}>■ Negative</span>
          </div>
        </div>
      )}

      {/* Symbol List */}
      <div style={{ maxHeight: 200, overflowY: 'auto' }}>
        {filteredSymbols.map((sym) => {
          const isUp = sym.change >= 0;
          const isSelected = sym.symbol === selectedSymbol;
          return (
            <div
              key={sym.symbol}
              onClick={() => onSymbolSelect?.(sym.symbol)}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '8px 10px', marginBottom: 4, borderRadius: 6, cursor: 'pointer',
                background: isSelected ? C.goldDim : 'rgba(0,0,0,0.3)',
                border: `1px solid ${isSelected ? C.gold : C.border}`,
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={e => { if (!isSelected) { (e.currentTarget as HTMLDivElement).style.borderColor = isUp ? C.green : C.red; } }}
              onMouseLeave={e => { if (!isSelected) { (e.currentTarget as HTMLDivElement).style.borderColor = C.border; } }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 10, fontFamily: C.mono, fontWeight: 800, color: isSelected ? C.gold : C.text }}>{sym.symbol}</span>
                <span style={{ fontSize: 7, color: C.muted }}>{sym.name}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 10, fontFamily: C.mono, fontWeight: 700, color: C.text }}>
                  {sym.price.toLocaleString('en-US', { minimumFractionDigits: sym.price < 10 ? 4 : 2, maximumFractionDigits: sym.price < 10 ? 4 : 2 })}
                </span>
                <span style={{
                  fontSize: 9, fontFamily: C.mono, fontWeight: 700,
                  color: isUp ? C.green : C.red,
                  background: isUp ? C.greenDim : C.redDim,
                  padding: '2px 6px', borderRadius: 4,
                }}>
                  {isUp ? '▲' : '▼'} {Math.abs(sym.change).toFixed(2)}%
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {filteredSymbols.length === 0 && (
        <div style={{ textAlign: 'center', color: C.muted, fontSize: 9, fontFamily: C.mono, padding: 20 }}>No symbols found</div>
      )}
    </div>
  );
}
