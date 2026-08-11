'use client';

import { useState, useEffect, useCallback, type CSSProperties } from 'react';
import {
  fetchControlCenterStatus, updateControlMode, updateControlKillSwitch,
  updateControlDemoArm, updateAiAutoLoop, loginMT5Account,
  fetchAIConfig, updateTradingMethod, testAIConnection,
} from '../../lib/api';

// ── Premium Design System ────────────────────────────────────────────────────────
const C = {
  gold: '#D4B483',
  goldDim: 'rgba(212,175,55,0.12)',
  goldBright: '#F0D5A0',
  green: '#22d3a0',
  greenBright: '#10b981',
  greenDim: 'rgba(34,211,160,0.12)',
  red: '#f43f5e',
  redBright: '#ef4444',
  redDim: 'rgba(244,63,94,0.12)',
  blue: '#38bdf8',
  blueDim: 'rgba(56,189,248,0.12)',
  cyan: '#06b6d4',
  cyanDim: 'rgba(6,182,212,0.12)',
  amber: '#f59e0b',
  amberDim: 'rgba(245,158,11,0.12)',
  text: '#e2e8f0',
  textBright: '#ffffff',
  dim: '#cbd5e1',
  muted: '#64748b',
  faint: '#475569',
  bg: '#05070c',
  border: 'rgba(255,255,255,0.06)',
  borderLight: 'rgba(255,255,255,0.1)',
  borderGold: 'rgba(212,180,131,0.35)',
  mono: '"JetBrains Mono", monospace',
  sans: '"Inter", -apple-system, BlinkMacSystemFont, sans-serif',
};

// ── Premium Toggle ─────────────────────────────────────────────────────────────
function PremiumToggle({ checked, onChange, label, sublabel, color = 'green' }: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  sublabel?: string;
  color?: 'green' | 'red' | 'gold' | 'blue';
}) {
  const col = { green: C.green, red: C.red, gold: C.gold, blue: C.blue }[color];
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '10px 12px', background: 'linear-gradient(135deg, rgba(5,7,12,0.9) 0%, rgba(3,5,8,0.95) 100%)',
      border: `1px solid ${C.border}`, borderRadius: 8, marginBottom: 6, transition: 'all 0.25s ease',
    }}
      onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.borderColor = C.borderGold; (e.currentTarget as HTMLDivElement).style.boxShadow = '0 4px 16px rgba(0,0,0,0.3)'; }}
      onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.borderColor = C.border; (e.currentTarget as HTMLDivElement).style.boxShadow = 'none'; }}>
      <div>
        <div style={{ fontSize: 9, fontFamily: C.mono, fontWeight: 700, color: C.text, letterSpacing: '0.06em', textTransform: 'uppercase' }}>{label}</div>
        {sublabel && <div style={{ fontSize: 7, fontFamily: C.mono, color: C.muted, marginTop: 2 }}>{sublabel}</div>}
      </div>
      <button onClick={() => onChange(!checked)} style={{
        width: 44, height: 24, borderRadius: 12,
        background: checked ? col : 'rgba(30,41,59,0.8)',
        border: `1px solid ${checked ? col : C.border}`,
        cursor: 'pointer', position: 'relative', transition: 'all 0.25s ease',
        boxShadow: checked ? `0 0 12px ${col}40, inset 0 1px 1px rgba(255,255,255,0.2)` : 'inset 0 1px 2px rgba(0,0,0,0.3)',
      }}>
        <div style={{
          position: 'absolute', top: 3, left: checked ? 22 : 3, width: 16, height: 16, borderRadius: '50%',
          background: checked ? '#fff' : C.muted, transition: 'all 0.25s ease',
          boxShadow: checked ? '0 2px 4px rgba(0,0,0,0.3)' : '0 1px 2px rgba(0,0,0,0.3)',
        }} />
      </button>
    </div>
  );
}

// ── Premium Button ─────────────────────────────────────────────────────────────
function PremiumButton({ children, onClick, variant = 'gold', disabled = false, style = {} }: {
  children: React.ReactNode; onClick?: () => void; variant?: 'gold' | 'green' | 'red' | 'dark'; disabled?: boolean; style?: CSSProperties;
}) {
  const v = {
    gold: { bg: 'linear-gradient(135deg, rgba(212,175,55,0.3) 0%, rgba(153,101,21,0.4) 100%)', border: C.gold, color: C.gold },
    green: { bg: 'linear-gradient(135deg, rgba(34,211,160,0.2) 0%, rgba(16,185,129,0.3) 100%)', border: C.green, color: C.green },
    red: { bg: 'linear-gradient(135deg, rgba(244,63,94,0.2) 0%, rgba(239,68,68,0.3) 100%)', border: C.red, color: C.red },
    dark: { bg: 'linear-gradient(180deg, rgba(30,41,59,0.9) 0%, rgba(15,23,42,0.95) 100%)', border: C.border, color: C.dim },
  }[variant];
  return (
    <button onClick={onClick} disabled={disabled} style={{
      padding: '8px 14px', background: disabled ? 'rgba(255,255,255,0.05)' : v.bg,
      border: `1px solid ${disabled ? C.border : v.border}`, borderRadius: 6,
      color: disabled ? C.muted : v.color, fontSize: 9, fontFamily: C.mono, fontWeight: 700,
      letterSpacing: '0.08em', textTransform: 'uppercase', cursor: disabled ? 'not-allowed' : 'pointer',
      transition: 'all 0.2s ease', ...style,
    }}>
      {children}
    </button>
  );
}

// ── Section Header ─────────────────────────────────────────────────────────────
function SectionHeader({ title }: { title: string }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px',
      background: 'linear-gradient(180deg, rgba(212,175,55,0.06) 0%, transparent 100%)',
      borderBottom: `1px solid ${C.border}`, marginBottom: 8,
    }}>
      <span style={{ fontSize: 8, fontFamily: C.mono, fontWeight: 800, color: C.gold, letterSpacing: '0.12em', textTransform: 'uppercase' }}>{title}</span>
    </div>
  );
}

// ── Metric Display ─────────────────────────────────────────────────────────────
function MetricDisplay({ label, value, accent = 'gold' }: { label: string; value: string | number; accent?: 'gold' | 'green' | 'red' | 'blue' | 'cyan' }) {
  const ac = { gold: C.gold, green: C.green, red: C.red, blue: C.blue, cyan: C.cyan }[accent];
  return (
    <div style={{ padding: '8px 10px', background: 'rgba(0,0,0,0.3)', borderRadius: 6, border: `1px solid ${C.border}` }}>
      <div style={{ fontSize: 7, fontFamily: C.mono, color: C.muted, letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 16, fontFamily: C.mono, fontWeight: 800, color: ac, letterSpacing: '-0.02em' }}>{value}</div>
    </div>
  );
}

// ── Main ControlCenter ──────────────────────────────────────────────────────────
export default function ControlCenter() {
  const [status, setStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [aiConfig, setAiConfig] = useState<any>(null);

  // MT5 Login Form
  const [mt5Login, setMt5Login] = useState('');
  const [mt5Password, setMt5Password] = useState('');
  const [mt5Server, setMt5Server] = useState('');

  const loadStatus = useCallback(async () => {
    try {
      const data = await fetchControlCenterStatus();
      setStatus(data);
    } catch { /* silent */ } finally { setLoading(false); }
  }, []);

  const loadAIConfig = useCallback(async () => {
    try { const data = await fetchAIConfig(); setAiConfig(data); } catch { /* silent */ }
  }, []);

  useEffect(() => {
    loadStatus();
    loadAIConfig();
    const interval = setInterval(loadStatus, 3000);
    return () => clearInterval(interval);
  }, [loadStatus, loadAIConfig]);

  const handleToggle = async (key: string, value: boolean) => {
    try {
      if (key === 'mode') await updateControlMode(value ? 'ACTIVE' : 'IDLE');
      else if (key === 'killSwitch') await updateControlKillSwitch(value);
      else if (key === 'demoArm') await updateControlDemoArm(value);
      else if (key === 'aiLoop') await updateAiAutoLoop(value);
      await loadStatus();
    } catch { /* silent */ }
  };

  const handleMT5Login = async () => {
    if (!mt5Login || !mt5Password) return;
    try {
      await loginMT5Account(Number(mt5Login), mt5Password, mt5Server);
      await loadStatus();
      setMt5Password('');
    } catch { /* silent */ }
  };

  const handleTestAI = async () => {
    try {
      const result = await testAIConnection({ key_type: 'gemini', model: 'gemini-2.0-flash' });
      alert(result?.status === 'success' || result?.result?.ok ? 'AI Connection: OK' : 'AI Connection: FAILED');
    } catch { alert('AI Connection: ERROR'); }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: C.muted, fontFamily: C.mono, fontSize: 10 }}>
        LOADING CONTROL CENTER...
      </div>
    );
  }

  const isConnected = status?.account?.mt5_connected || false;
  const mode = status?.safeguards?.kill_switch_active ? 'KILLED' : status?.execution?.mode === 'ACTIVE' ? 'ACTIVE' : 'IDLE';
  const aiLoop = status?.safeguards?.ai_auto_loop || false;

  return (
    <div style={{ fontFamily: C.sans, height: '100%', overflow: 'auto', background: 'linear-gradient(180deg, rgba(5,7,12,0.95) 0%, rgba(3,5,8,0.98) 100%)' }}>
      {/* MT5 STATUS */}
      <div style={{ padding: '12px', borderBottom: `1px solid ${C.border}` }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: isConnected ? C.green : C.red, boxShadow: isConnected ? `0 0 10px ${C.green}` : `0 0 10px ${C.red}` }} />
            <span style={{ fontSize: 9, fontFamily: C.mono, fontWeight: 800, color: C.text, letterSpacing: '0.08em' }}>MT5 TERMINAL</span>
          </div>
          <span style={{ fontSize: 8, fontFamily: C.mono, color: isConnected ? C.green : C.red, fontWeight: 700 }}>{isConnected ? 'CONNECTED' : 'DISCONNECTED'}</span>
        </div>

        {isConnected ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6 }}>
            <MetricDisplay label="Account" value={status.account?.login?.toString() || '---'} accent="gold" />
            <MetricDisplay label="Balance" value={`$${(status.account?.balance || 0).toFixed(2)}`} accent={(status.account?.balance || 0) >= 0 ? 'green' : 'red'} />
            <MetricDisplay label="Equity" value={`$${(status.account?.equity || 0).toFixed(2)}`} accent="cyan" />
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <input type="text" placeholder="MT5 Login ID" value={mt5Login} onChange={e => setMt5Login(e.target.value)}
              style={{ padding: '8px 10px', background: 'rgba(0,0,0,0.5)', border: `1px solid ${C.border}`, borderRadius: 6, color: C.text, fontSize: 10, fontFamily: C.mono, outline: 'none', boxSizing: 'border-box' }}
              onFocus={e => e.target.style.borderColor = C.gold} onBlur={e => e.target.style.borderColor = C.border} />
            <input type="password" placeholder="Password" value={mt5Password} onChange={e => setMt5Password(e.target.value)}
              style={{ padding: '8px 10px', background: 'rgba(0,0,0,0.5)', border: `1px solid ${C.border}`, borderRadius: 6, color: C.text, fontSize: 10, fontFamily: C.mono, outline: 'none', boxSizing: 'border-box' }}
              onFocus={e => e.target.style.borderColor = C.gold} onBlur={e => e.target.style.borderColor = C.border} />
            <input type="text" placeholder="Server (e.g. ICMarketsSC-Demo)" value={mt5Server} onChange={e => setMt5Server(e.target.value)}
              style={{ padding: '8px 10px', background: 'rgba(0,0,0,0.5)', border: `1px solid ${C.border}`, borderRadius: 6, color: C.text, fontSize: 10, fontFamily: C.mono, outline: 'none', boxSizing: 'border-box' }}
              onFocus={e => e.target.style.borderColor = C.gold} onBlur={e => e.target.style.borderColor = C.border} />
            <PremiumButton variant="gold" onClick={handleMT5Login} style={{ width: '100%' }}>Connect MT5</PremiumButton>
          </div>
        )}
      </div>

      {/* MAIN CONTROLS */}
      <div style={{ padding: 12 }}>
        <SectionHeader title="Main Controls" />
        <PremiumToggle checked={mode === 'ACTIVE'} onChange={v => handleToggle('mode', v)} label="Trading Mode" sublabel={mode === 'ACTIVE' ? 'Actively scanning' : 'Idle mode'} color="green" />
        <PremiumToggle checked={status?.safeguards?.kill_switch_active || false} onChange={v => handleToggle('killSwitch', v)} label="Kill Switch" sublabel="Emergency stop" color="red" />
        <PremiumToggle checked={status?.safeguards?.demo_armed || false} onChange={v => handleToggle('demoArm', v)} label="Demo Mode" sublabel={status?.safeguards?.demo_armed ? 'Paper trading' : 'Live trading'} color="gold" />
        <PremiumToggle checked={aiLoop} onChange={v => handleToggle('aiLoop', v)} label="AI Auto Loop" sublabel="AI manages positions" color="blue" />
      </div>

      {/* RISK MANAGEMENT */}
      <div style={{ padding: '0 12px 12px' }}>
        <SectionHeader title="Risk Management" />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginBottom: 8 }}>
          <MetricDisplay label="Max Risk" value={`${((status?.risk?.risk_per_trade_fraction || 0.01) * 100).toFixed(1)}%`} accent="gold" />
          <MetricDisplay label="Max Positions" value={status?.risk?.max_open_positions?.toString() || '5'} accent="cyan" />
        </div>
        <div style={{ background: 'rgba(0,0,0,0.3)', borderRadius: 6, border: `1px solid ${C.border}`, padding: '8px 10px' }}>
          <div style={{ fontSize: 7, color: C.muted, fontFamily: C.mono, marginBottom: 4 }}>STREAM STATUS</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: status?.bridge?.mt5_connected ? C.green : C.red, boxShadow: status?.bridge?.mt5_connected ? `0 0 6px ${C.green}` : 'none' }} />
            <span style={{ fontSize: 9, fontFamily: C.mono, fontWeight: 700, color: C.text }}>{status?.bridge?.mt5_connected ? 'STREAMING' : 'DISCONNECTED'}</span>
          </div>
        </div>
      </div>

      {/* TRADING METHOD */}
      <div style={{ padding: '0 12px 12px' }}>
        <SectionHeader title="Trading Method" />
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {['SNIPER', 'SMC', 'ICT', 'PRICE ACTION'].map(method => {
            const isActive = (aiConfig?.trading_method || status?.safeguards?.trading_method) === method;
            return (
              <button key={method} onClick={async () => { try { await updateTradingMethod(method); await loadAIConfig(); } catch { /* silent */ } }}
                style={{
                  padding: '5px 10px', background: isActive ? C.goldDim : 'rgba(0,0,0,0.3)',
                  border: `1px solid ${isActive ? C.gold : C.border}`, borderRadius: 4, color: isActive ? C.gold : C.muted,
                  fontSize: 8, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer', transition: 'all 0.2s ease',
                }}>
                {method}
              </button>
            );
          })}
        </div>
      </div>

      {/* QUICK ACTIONS */}
      <div style={{ padding: '0 12px 12px' }}>
        <SectionHeader title="Quick Actions" />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
          <PremiumButton variant="red" onClick={async () => { try { await fetch('/api/order/close_all', { method: 'POST' }); await loadStatus(); } catch { /* silent */ } }}>Close All</PremiumButton>
          <PremiumButton variant="dark" onClick={async () => { try { await fetch('/api/reset_all', { method: 'POST' }); await loadStatus(); } catch { /* silent */ } }}>Reset</PremiumButton>
          <PremiumButton variant="green" onClick={async () => { try { await fetch('/api/orders/close-profitable', { method: 'POST' }); await loadStatus(); } catch { /* silent */ } }}>Close Profit</PremiumButton>
          <PremiumButton variant="dark" onClick={handleTestAI}>Test AI</PremiumButton>
        </div>
      </div>

      {/* SYSTEM STATUS */}
      <div style={{ padding: '0 12px 12px' }}>
        <SectionHeader title="System Status" />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 4 }}>
          {[
            { label: 'Backend', value: status ? 'ONLINE' : 'OFFLINE', ok: !!status },
            { label: 'Bridge', value: status?.bridge?.status || 'UNKNOWN', ok: status?.bridge?.status === 'connected' },
            { label: 'AI Engine', value: aiConfig ? 'ENABLED' : 'DISABLED', ok: !!aiConfig },
            { label: 'MT5', value: isConnected ? 'CONNECTED' : 'OFFLINE', ok: isConnected },
          ].map(item => (
            <div key={item.label} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 8px', background: 'rgba(0,0,0,0.3)', borderRadius: 4, border: `1px solid ${C.border}` }}>
              <span style={{ fontSize: 7, fontFamily: C.mono, color: C.muted }}>{item.label}</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <div style={{ width: 4, height: 4, borderRadius: '50%', background: item.ok ? C.green : C.red, boxShadow: item.ok ? `0 0 4px ${C.green}` : 'none' }} />
                <span style={{ fontSize: 7, fontFamily: C.mono, fontWeight: 700, color: item.ok ? C.green : C.red }}>{item.value}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
