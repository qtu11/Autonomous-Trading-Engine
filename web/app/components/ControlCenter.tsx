'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  fetchControlCenterStatus, updateControlMode, updateControlKillSwitch,
  updateControlDemoArm, updateAiAutoLoop, loginMT5Account,
  fetchAIConfig, updateTradingMethod, testAIConnection,
} from '../../lib/api';

const C = {
  gold: '#D4B483',
  goldDim: 'rgba(212,175,55,0.12)',
  green: '#22d3a0',
  greenDim: 'rgba(34,211,160,0.12)',
  red: '#f43f5e',
  redDim: 'rgba(244,63,94,0.12)',
  blue: '#38bdf8',
  blueDim: 'rgba(56,189,248,0.12)',
  cyan: '#06b6d4',
  text: '#e2e8f0',
  dim: '#cbd5e1',
  muted: '#64748b',
  border: 'rgba(255,255,255,0.06)',
  mono: '"JetBrains Mono", monospace',
  sans: '"Inter", -apple-system, sans-serif',
};

function Toggle({ checked, onChange, label, sublabel, color = 'green' }: {
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
      padding: '10px 12px', background: 'rgba(5,7,12,0.9)', border: `1px solid ${C.border}`, borderRadius: 8, marginBottom: 6,
    }}>
      <div>
        <div style={{ fontSize: 9, fontFamily: C.mono, fontWeight: 700, color: C.text, textTransform: 'uppercase' }}>{label}</div>
        {sublabel && <div style={{ fontSize: 7, fontFamily: C.mono, color: C.muted, marginTop: 2 }}>{sublabel}</div>}
      </div>
      <button onClick={() => onChange(!checked)} style={{
        width: 44, height: 24, borderRadius: 12,
        background: checked ? col : 'rgba(30,41,59,0.8)',
        border: `1px solid ${checked ? col : C.border}`,
        cursor: 'pointer', position: 'relative',
      }}>
        <div style={{
          position: 'absolute', top: 3, left: checked ? 22 : 3, width: 16, height: 16, borderRadius: '50%',
          background: checked ? '#fff' : C.muted, transition: 'all 0.25s ease',
        }} />
      </button>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ padding: '0 12px 12px' }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0',
        borderBottom: `1px solid ${C.border}`, marginBottom: 8,
      }}>
        <span style={{ fontSize: 8, fontFamily: C.mono, fontWeight: 800, color: C.gold, letterSpacing: '0.12em', textTransform: 'uppercase' }}>{title}</span>
      </div>
      {children}
    </div>
  );
}

export default function ControlCenter() {
  const [status, setStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [aiConfig, setAiConfig] = useState<any>(null);
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
      else if (key === 'kill') await updateControlKillSwitch(value);
      else if (key === 'demo') await updateControlDemoArm(value);
      else if (key === 'ai') await updateAiAutoLoop(value);
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

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: C.muted, fontFamily: C.mono, fontSize: 10 }}>
        LOADING...
      </div>
    );
  }

  const isConnected = status?.account?.mt5_connected || false;
  const mode = status?.safeguards?.kill_switch_active ? 'KILLED' : status?.execution?.mode === 'ACTIVE' ? 'ACTIVE' : 'IDLE';
  const aiLoop = status?.safeguards?.ai_auto_loop || false;

  return (
    <div style={{ fontFamily: C.sans, height: '100%', overflow: 'auto', background: 'rgba(5,7,12,0.95)' }}>
      {/* MT5 STATUS */}
      <div style={{ padding: 12, borderBottom: `1px solid ${C.border}` }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: isConnected ? C.green : C.red, boxShadow: isConnected ? `0 0 10px ${C.green}` : `0 0 10px ${C.red}` }} />
            <span style={{ fontSize: 9, fontFamily: C.mono, fontWeight: 800, color: C.text }}>MT5</span>
          </div>
          <span style={{ fontSize: 8, fontFamily: C.mono, color: isConnected ? C.green : C.red, fontWeight: 700 }}>
            {isConnected ? 'CONNECTED' : 'OFFLINE'}
          </span>
        </div>

        {isConnected ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6 }}>
            <div style={{ padding: '8px 10px', background: 'rgba(0,0,0,0.3)', borderRadius: 6, border: `1px solid ${C.border}`, textAlign: 'center' }}>
              <div style={{ fontSize: 7, color: C.muted, marginBottom: 4 }}>ACCOUNT</div>
              <div style={{ fontSize: 14, fontFamily: C.mono, fontWeight: 800, color: C.gold }}>{status.account?.login || '---'}</div>
            </div>
            <div style={{ padding: '8px 10px', background: 'rgba(0,0,0,0.3)', borderRadius: 6, border: `1px solid ${C.border}`, textAlign: 'center' }}>
              <div style={{ fontSize: 7, color: C.muted, marginBottom: 4 }}>BALANCE</div>
              <div style={{ fontSize: 14, fontFamily: C.mono, fontWeight: 800, color: C.green }}>${(status.account?.balance || 0).toFixed(2)}</div>
            </div>
            <div style={{ padding: '8px 10px', background: 'rgba(0,0,0,0.3)', borderRadius: 6, border: `1px solid ${C.border}`, textAlign: 'center' }}>
              <div style={{ fontSize: 7, color: C.muted, marginBottom: 4 }}>EQUITY</div>
              <div style={{ fontSize: 14, fontFamily: C.mono, fontWeight: 800, color: C.cyan }}>${(status.account?.equity || 0).toFixed(2)}</div>
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <input type="text" placeholder="MT5 Login" value={mt5Login} onChange={e => setMt5Login(e.target.value)}
              style={{ padding: '8px 10px', background: 'rgba(0,0,0,0.5)', border: `1px solid ${C.border}`, borderRadius: 6, color: C.text, fontSize: 10, fontFamily: C.mono, outline: 'none', boxSizing: 'border-box' }} />
            <input type="password" placeholder="Password" value={mt5Password} onChange={e => setMt5Password(e.target.value)}
              style={{ padding: '8px 10px', background: 'rgba(0,0,0,0.5)', border: `1px solid ${C.border}`, borderRadius: 6, color: C.text, fontSize: 10, fontFamily: C.mono, outline: 'none', boxSizing: 'border-box' }} />
            <input type="text" placeholder="Server" value={mt5Server} onChange={e => setMt5Server(e.target.value)}
              style={{ padding: '8px 10px', background: 'rgba(0,0,0,0.5)', border: `1px solid ${C.border}`, borderRadius: 6, color: C.text, fontSize: 10, fontFamily: C.mono, outline: 'none', boxSizing: 'border-box' }} />
            <button onClick={handleMT5Login} style={{
              padding: '8px 14px', background: C.goldDim, border: `1px solid ${C.gold}`, borderRadius: 6,
              color: C.gold, fontSize: 9, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer', textTransform: 'uppercase',
            }}>Connect</button>
          </div>
        )}
      </div>

      {/* CONTROLS */}
      <Section title="Controls">
        <Toggle checked={mode === 'ACTIVE'} onChange={v => handleToggle('mode', v)} label="Trading Mode" sublabel={mode} color="green" />
        <Toggle checked={status?.safeguards?.kill_switch_active || false} onChange={v => handleToggle('kill', v)} label="Kill Switch" color="red" />
        <Toggle checked={status?.safeguards?.demo_armed || false} onChange={v => handleToggle('demo', v)} label="Demo Mode" color="gold" />
        <Toggle checked={aiLoop} onChange={v => handleToggle('ai', v)} label="AI Auto Loop" color="blue" />
      </Section>

      {/* METHOD */}
      <Section title="Trading Method">
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {['SNIPER', 'SMC', 'ICT', 'PRICE ACTION'].map(method => {
            const isActive = (aiConfig?.trading_method || status?.safeguards?.trading_method) === method;
            return (
              <button key={method} onClick={async () => { try { await updateTradingMethod(method); await loadAIConfig(); } catch { /* silent */ } }}
                style={{
                  padding: '5px 10px', background: isActive ? C.goldDim : 'rgba(0,0,0,0.3)',
                  border: `1px solid ${isActive ? C.gold : C.border}`, borderRadius: 4, color: isActive ? C.gold : C.muted,
                  fontSize: 8, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer',
                }}>
                {method}
              </button>
            );
          })}
        </div>
      </Section>

      {/* QUICK ACTIONS */}
      <Section title="Quick Actions">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
          <button onClick={async () => { try { await fetch('/api/order/close_all', { method: 'POST' }); await loadStatus(); } catch { /* silent */ } }}
            style={{ padding: '8px', background: C.redDim, border: `1px solid ${C.red}`, borderRadius: 6, color: C.red, fontSize: 8, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer' }}>Close All</button>
          <button onClick={async () => { try { await fetch('/api/reset_all', { method: 'POST' }); await loadStatus(); } catch { /* silent */ } }}
            style={{ padding: '8px', background: 'rgba(0,0,0,0.3)', border: `1px solid ${C.border}`, borderRadius: 6, color: C.dim, fontSize: 8, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer' }}>Reset</button>
          <button onClick={async () => { try { await fetch('/api/orders/close-profitable', { method: 'POST' }); await loadStatus(); } catch { /* silent */ } }}
            style={{ padding: '8px', background: C.greenDim, border: `1px solid ${C.green}`, borderRadius: 6, color: C.green, fontSize: 8, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer' }}>Close Profit</button>
          <button onClick={handleMT5Login}
            style={{ padding: '8px', background: C.blueDim, border: `1px solid ${C.blue}`, borderRadius: 6, color: C.blue, fontSize: 8, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer' }}>Test AI</button>
        </div>
      </Section>

      {/* STATUS */}
      <Section title="System">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 4 }}>
          {[
            { label: 'Backend', ok: !!status },
            { label: 'Bridge', ok: status?.bridge?.mt5_connected },
            { label: 'AI', ok: !!aiConfig },
            { label: 'MT5', ok: isConnected },
          ].map(item => (
            <div key={item.label} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 8px', background: 'rgba(0,0,0,0.3)', borderRadius: 4, border: `1px solid ${C.border}` }}>
              <span style={{ fontSize: 7, fontFamily: C.mono, color: C.muted }}>{item.label}</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <div style={{ width: 4, height: 4, borderRadius: '50%', background: item.ok ? C.green : C.red }} />
                <span style={{ fontSize: 7, fontFamily: C.mono, fontWeight: 700, color: item.ok ? C.green : C.red }}>{item.ok ? 'ON' : 'OFF'}</span>
              </div>
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}
