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
  amber: '#f59e0b',
  text: '#f8fafc',
  dim: '#cbd5e1',
  muted: '#64748b',
  border: 'rgba(255,255,255,0.06)',
  mono: '"JetBrains Mono", monospace',
};

// Pip values per standard lot for different instruments
const PIP_VALUES: Record<string, { pipValue: number; minMove: number; name: string }> = {
  XAUUSD: { pipValue: 0.5, minMove: 0.01, name: 'Gold' },
  EURUSD: { pipValue: 10, minMove: 0.0001, name: 'Euro' },
  GBPUSD: { pipValue: 10, minMove: 0.0001, name: 'Pound' },
  USDJPY: { pipValue: 9, minMove: 0.01, name: 'Yen' },
  AUDUSD: { pipValue: 10, minMove: 0.0001, name: 'Aussie' },
  USDCAD: { pipValue: 10, minMove: 0.0001, name: 'Loonie' },
};

interface RiskCalculatorProps {
  accountBalance?: number;
  currentPrice?: number;
  onQuickTrade?: (params: { type: 'BUY' | 'SELL'; volume: number; sl: number; tp: number; symbol: string }) => void;
}

export default function RiskCalculator({ accountBalance = 10000, currentPrice = 2850, onQuickTrade }: RiskCalculatorProps) {
  const [symbol, setSymbol] = useState('XAUUSD');
  const [balance, setBalance] = useState(accountBalance.toString());
  const [riskPercent, setRiskPercent] = useState('2.0');
  const [stopLoss, setStopLoss] = useState('50'); // in pips
  const [takeProfit, setTakeProfit] = useState('100'); // in pips
  const [showPipValues, setShowPipValues] = useState(false);

  const pipInfo = PIP_VALUES[symbol] || PIP_VALUES.XAUUSD;

  // Calculate position size
  const riskAmount = (parseFloat(balance) * parseFloat(riskPercent)) / 100;
  const pipValuePerLot = pipInfo.pipValue;
  const positionSize = stopLoss && parseFloat(stopLoss) > 0 ? riskAmount / (parseFloat(stopLoss) * pipValuePerLot) : 0;
  const rewardAmount = positionSize * parseFloat(takeProfit || '0') * pipValuePerLot;
  const rrr = stopLoss && takeProfit && parseFloat(stopLoss) > 0 ? parseFloat(takeProfit) / parseFloat(stopLoss) : 0;

  const handleExecute = useCallback((type: 'BUY' | 'SELL') => {
    if (onQuickTrade && positionSize > 0) {
      onQuickTrade({
        type,
        volume: Math.round(positionSize * 100) / 100,
        sl: parseFloat(stopLoss) || 50,
        tp: parseFloat(takeProfit) || 100,
        symbol,
      });
    }
  }, [onQuickTrade, positionSize, stopLoss, takeProfit, symbol]);

  const InputField = ({ label, value, onChange, suffix, max }: { label: string; value: string; onChange: (v: string) => void; suffix?: string; max?: number }) => (
    <div style={{ marginBottom: 8 }}>
      <div style={{ fontSize: 7, color: C.muted, fontFamily: C.mono, marginBottom: 2 }}>{label}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <input
          type="number"
          value={value}
          onChange={e => onChange(e.target.value)}
          max={max}
          style={{
            flex: 1, padding: '6px 8px', background: 'rgba(0,0,0,0.5)',
            border: `1px solid ${C.border}`, borderRadius: 4, color: C.text,
            fontSize: 10, fontFamily: C.mono, outline: 'none',
          }}
        />
        {suffix && <span style={{ fontSize: 8, color: C.muted, fontFamily: C.mono }}>{suffix}</span>}
      </div>
    </div>
  );

  return (
    <div style={{ padding: '0 12px 12px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0', borderBottom: `1px solid ${C.border}`, marginBottom: 8 }}>
        <span style={{ fontSize: 8, fontFamily: C.mono, fontWeight: 800, color: C.gold, letterSpacing: '0.1em' }}>RISK CALCULATOR</span>
        <button onClick={() => setShowPipValues(!showPipValues)} style={{
          fontSize: 7, fontFamily: C.mono, padding: '2px 6px', background: 'transparent',
          border: `1px solid ${C.border}`, borderRadius: 3, color: C.muted, cursor: 'pointer',
        }}>PIPs</button>
      </div>

      {/* Pip Values Table */}
      {showPipValues && (
        <div style={{ background: 'rgba(0,0,0,0.3)', borderRadius: 6, padding: 8, marginBottom: 8, border: `1px solid ${C.border}` }}>
          <div style={{ fontSize: 7, color: C.muted, fontFamily: C.mono, marginBottom: 4 }}>PIP VALUES (per standard lot)</div>
          {Object.entries(PIP_VALUES).map(([sym, info]) => (
            <div key={sym} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 8, fontFamily: C.mono, padding: '2px 0', borderBottom: `1px solid rgba(255,255,255,0.03)` }}>
              <span style={{ color: C.text }}>{sym} ({info.name})</span>
              <span style={{ color: C.cyan }}>${info.pipValue}/pip</span>
            </div>
          ))}
        </div>
      )}

      {/* Symbol Selector */}
      <div style={{ marginBottom: 8 }}>
        <div style={{ fontSize: 7, color: C.muted, fontFamily: C.mono, marginBottom: 2 }}>SYMBOL</div>
        <select
          value={symbol}
          onChange={e => setSymbol(e.target.value)}
          style={{
            width: '100%', padding: '6px 8px', background: 'rgba(0,0,0,0.5)',
            border: `1px solid ${C.border}`, borderRadius: 4, color: C.text,
            fontSize: 10, fontFamily: C.mono, outline: 'none', cursor: 'pointer',
          }}
        >
          {Object.entries(PIP_VALUES).map(([sym, info]) => (
            <option key={sym} value={sym}>{sym} - {info.name}</option>
          ))}
        </select>
      </div>

      <InputField label="ACCOUNT BALANCE" value={balance} onChange={setBalance} suffix="$" />
      <InputField label="RISK PERCENT" value={riskPercent} onChange={setRiskPercent} suffix="%" max={5} />
      <InputField label="STOP LOSS" value={stopLoss} onChange={setStopLoss} suffix="pips" />
      <InputField label="TAKE PROFIT" value={takeProfit} onChange={setTakeProfit} suffix="pips" />

      {/* Results */}
      <div style={{ background: 'rgba(0,0,0,0.4)', borderRadius: 6, padding: 10, marginTop: 8, border: `1px solid ${C.border}` }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
          <div>
            <div style={{ fontSize: 7, color: C.muted, marginBottom: 2 }}>POSITION SIZE</div>
            <div style={{ fontSize: 14, fontFamily: C.mono, fontWeight: 800, color: C.gold }}>{positionSize.toFixed(2)} lots</div>
          </div>
          <div>
            <div style={{ fontSize: 7, color: C.muted, marginBottom: 2 }}>RISK AMOUNT</div>
            <div style={{ fontSize: 14, fontFamily: C.mono, fontWeight: 800, color: C.red }}>${riskAmount.toFixed(2)}</div>
          </div>
          <div>
            <div style={{ fontSize: 7, color: C.muted, marginBottom: 2 }}>REWARD</div>
            <div style={{ fontSize: 14, fontFamily: C.mono, fontWeight: 800, color: C.green }}>${rewardAmount.toFixed(2)}</div>
          </div>
          <div>
            <div style={{ fontSize: 7, color: C.muted, marginBottom: 2 }}>RISK:REWARD</div>
            <div style={{ fontSize: 14, fontFamily: C.mono, fontWeight: 800, color: C.cyan }}>{rrr.toFixed(1)}:1</div>
          </div>
        </div>
      </div>

      {/* Quick Trade Buttons */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginTop: 8 }}>
        <button onClick={() => handleExecute('BUY')} style={{
          padding: '8px', background: C.greenDim, border: `1px solid ${C.green}`, borderRadius: 6,
          color: C.green, fontSize: 9, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer',
        }}>BUY {positionSize.toFixed(2)}</button>
        <button onClick={() => handleExecute('SELL')} style={{
          padding: '8px', background: C.redDim, border: `1px solid ${C.red}`, borderRadius: 6,
          color: C.red, fontSize: 9, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer',
        }}>SELL {positionSize.toFixed(2)}</button>
      </div>
    </div>
  );
}
