'use client';

import { useState, useCallback } from 'react';

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

interface QuickTradePanelProps {
  isOpen: boolean;
  onClose: () => void;
  onExecute?: (order: { symbol: string; type: 'BUY' | 'SELL'; volume: number; sl: number; tp: number; price?: number }) => void;
  currentPrice?: number;
}

export default function QuickTradePanel({ isOpen, onClose, onExecute, currentPrice = 2850 }: QuickTradePanelProps) {
  const [symbol, setSymbol] = useState('XAUUSD');
  const [type, setType] = useState<'BUY' | 'SELL'>('BUY');
  const [volume, setVolume] = useState('0.10');
  const [sl, setSl] = useState('50');
  const [tp, setTp] = useState('100');
  const [useMarketPrice, setUseMarketPrice] = useState(true);
  const [price, setPrice] = useState(currentPrice.toString());
  const [showConfirm, setShowConfirm] = useState(false);

  const pipValue = 0.5; // XAUUSD
  const riskAmount = (parseFloat(volume) * parseFloat(sl) * pipValue);
  const rewardAmount = (parseFloat(volume) * parseFloat(tp) * pipValue);
  const rrr = parseFloat(sl) > 0 ? parseFloat(tp) / parseFloat(sl) : 0;

  const handleExecute = useCallback(() => {
    setShowConfirm(true);
  }, []);

  const confirmExecute = useCallback(() => {
    onExecute?.({
      symbol,
      type,
      volume: parseFloat(volume),
      sl: parseFloat(sl),
      tp: parseFloat(tp),
      price: useMarketPrice ? undefined : parseFloat(price),
    });
    setShowConfirm(false);
    onClose();
  }, [symbol, type, volume, sl, tp, price, useMarketPrice, onExecute, onClose]);

  if (!isOpen) return null;

  const InputRow = ({ label, value, onChange, suffix, ...props }: { label: string; value: string; onChange: (v: string) => void; suffix?: string } & any) => (
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: 7, color: C.muted, fontFamily: C.mono, marginBottom: 4 }}>{label}</div>
      <input
        type="number"
        value={value}
        onChange={e => onChange(e.target.value)}
        {...props}
        style={{
          width: '100%', padding: '8px 10px', background: 'rgba(0,0,0,0.5)',
          border: `1px solid ${C.border}`, borderRadius: 6, color: C.text,
          fontSize: 12, fontFamily: C.mono, outline: 'none', boxSizing: 'border-box',
          ...props.style,
        }}
      />
      {suffix && <div style={{ fontSize: 7, color: C.muted, marginTop: 2, fontFamily: C.mono }}>{suffix}</div>}
    </div>
  );

  return (
    <div style={{ position: 'fixed', bottom: 20, right: 20, width: 320, zIndex: 1000 }}>
      {/* Panel */}
      <div style={{
        background: 'rgba(8,12,22,0.98)',
        border: `1px solid ${C.gold}`,
        borderRadius: 12,
        boxShadow: '0 20px 60px rgba(0,0,0,0.8), 0 0 40px rgba(212,175,55,0.15)',
        overflow: 'hidden',
        animation: 'slideUp 0.3s ease',
      }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderBottom: `1px solid ${C.border}`, background: 'rgba(212,175,55,0.05)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: C.green, boxShadow: `0 0 8px ${C.green}` }} />
            <span style={{ fontSize: 10, fontFamily: C.mono, fontWeight: 800, color: C.gold }}>QUICK TRADE</span>
          </div>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: C.muted, cursor: 'pointer', fontSize: 16 }}>×</button>
        </div>

        <div style={{ padding: 16 }}>
          {/* Symbol */}
          <div style={{ marginBottom: 10 }}>
            <div style={{ fontSize: 7, color: C.muted, fontFamily: C.mono, marginBottom: 4 }}>SYMBOL</div>
            <select
              value={symbol}
              onChange={e => setSymbol(e.target.value)}
              style={{ width: '100%', padding: '8px 10px', background: 'rgba(0,0,0,0.5)', border: `1px solid ${C.border}`, borderRadius: 6, color: C.text, fontSize: 12, fontFamily: C.mono, outline: 'none' }}
            >
              <option value="XAUUSD">XAUUSD - Gold</option>
              <option value="EURUSD">EURUSD - Euro</option>
              <option value="GBPUSD">GBPUSD - Pound</option>
            </select>
          </div>

          {/* BUY/SELL Toggle */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 }}>
            <button onClick={() => setType('BUY')} style={{
              padding: '12px', borderRadius: 8, cursor: 'pointer', fontSize: 11, fontFamily: C.mono, fontWeight: 800,
              background: type === 'BUY' ? C.greenDim : 'rgba(0,0,0,0.5)',
              border: `2px solid ${type === 'BUY' ? C.green : C.border}`,
              color: type === 'BUY' ? C.green : C.muted,
              transition: 'all 0.2s ease',
            }}>
              ▲ BUY
            </button>
            <button onClick={() => setType('SELL')} style={{
              padding: '12px', borderRadius: 8, cursor: 'pointer', fontSize: 11, fontFamily: C.mono, fontWeight: 800,
              background: type === 'SELL' ? C.redDim : 'rgba(0,0,0,0.5)',
              border: `2px solid ${type === 'SELL' ? C.red : C.border}`,
              color: type === 'SELL' ? C.red : C.muted,
              transition: 'all 0.2s ease',
            }}>
              ▼ SELL
            </button>
          </div>

          {/* Volume */}
          <InputRow label="VOLUME (LOTS)" value={volume} onChange={setVolume} suffix="Standard lots" />

          {/* Entry Price */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <input type="checkbox" checked={useMarketPrice} onChange={e => setUseMarketPrice(e.target.checked)} />
            <span style={{ fontSize: 8, fontFamily: C.mono, color: C.muted }}>Use Market Price</span>
          </div>
          {!useMarketPrice && <InputRow label="ENTRY PRICE" value={price} onChange={setPrice} />}

          {/* SL/TP */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <InputRow label="STOP LOSS (PIPS)" value={sl} onChange={setSl} />
            <InputRow label="TAKE PROFIT (PIPS)" value={tp} onChange={setTp} />
          </div>

          {/* Risk Preview */}
          <div style={{ background: 'rgba(0,0,0,0.4)', borderRadius: 8, padding: 12, marginTop: 12, border: `1px solid ${C.border}` }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, textAlign: 'center' }}>
              <div>
                <div style={{ fontSize: 7, color: C.muted, fontFamily: C.mono }}>RISK</div>
                <div style={{ fontSize: 14, fontFamily: C.mono, fontWeight: 800, color: C.red }}>${riskAmount.toFixed(2)}</div>
              </div>
              <div>
                <div style={{ fontSize: 7, color: C.muted, fontFamily: C.mono }}>REWARD</div>
                <div style={{ fontSize: 14, fontFamily: C.mono, fontWeight: 800, color: C.green }}>${rewardAmount.toFixed(2)}</div>
              </div>
              <div>
                <div style={{ fontSize: 7, color: C.muted, fontFamily: C.mono }}>R:R</div>
                <div style={{ fontSize: 14, fontFamily: C.mono, fontWeight: 800, color: C.cyan }}>{rrr.toFixed(1)}:1</div>
              </div>
            </div>
          </div>

          {/* Execute Button */}
          <button onClick={handleExecute} style={{
            width: '100%', padding: '14px', marginTop: 12,
            background: type === 'BUY' ? `linear-gradient(135deg, ${C.green} 0%, rgba(16,185,129,0.8) 100%)` : `linear-gradient(135deg, ${C.red} 0%, rgba(239,68,68,0.8) 100%)`,
            border: 'none', borderRadius: 8, color: '#fff', fontSize: 12, fontFamily: C.mono, fontWeight: 800,
            cursor: 'pointer', letterSpacing: '0.05em',
            boxShadow: `0 4px 16px ${type === 'BUY' ? C.green : C.red}40`,
          }}>
            EXECUTE {type} ORDER
          </button>
        </div>
      </div>

      {/* Confirmation Modal */}
      {showConfirm && (
        <div onClick={() => setShowConfirm(false)} style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', backdropFilter: 'blur(8px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1001,
        }}>
          <div onClick={e => e.stopPropagation()} style={{
            background: 'rgba(8,12,22,0.98)', border: `1px solid ${C.gold}`, borderRadius: 12,
            padding: 24, maxWidth: 320, textAlign: 'center',
          }}>
            <div style={{ fontSize: 12, fontFamily: C.mono, fontWeight: 800, color: C.gold, marginBottom: 12 }}>
              CONFIRM ORDER
            </div>
            <div style={{ fontSize: 11, fontFamily: C.mono, color: C.dim, marginBottom: 16, lineHeight: 1.6 }}>
              {type} {volume} lots {symbol}<br />
              SL: {sl} pips | TP: {tp} pips
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => setShowConfirm(false)} style={{
                flex: 1, padding: '10px', background: 'transparent', border: `1px solid ${C.border}`,
                borderRadius: 6, color: C.muted, fontSize: 10, fontFamily: C.mono, cursor: 'pointer',
              }}>CANCEL</button>
              <button onClick={confirmExecute} style={{
                flex: 1, padding: '10px', background: type === 'BUY' ? C.green : C.red,
                border: 'none', borderRadius: 6, color: '#fff', fontSize: 10, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer',
              }}>CONFIRM</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
