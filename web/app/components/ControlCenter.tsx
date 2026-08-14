'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  fetchControlCenterStatus,
  updateAiAutoLoop, loginMT5Account,
  fetchAIConfig, updateTradingMethod,
  fetchMT5Diagnostics,
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

interface ControlCenterProps {
  onMethodChange?: (method: string) => void;
}

export default function ControlCenter({ onMethodChange }: ControlCenterProps = {}) {
  const [status, setStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [aiConfig, setAiConfig] = useState<any>(null);
  const [mt5Login, setMt5Login] = useState('');
  const [mt5Password, setMt5Password] = useState('');
  const [mt5Server, setMt5Server] = useState('');
  const [diag, setDiag] = useState<any>(null);
  const [loginResult, setLoginResult] = useState<any>(null);

  // BUG FIX: tải chẩn đoán MT5 (LAN IP, checklist allowlist/firewall, lần cuối EA
  // gửi telemetry) để hiển thị ngay lý do "MT5 Connected NO" khi EA chưa kết nối.
  const loadDiag = useCallback(async () => {
    try { const d = await fetchMT5Diagnostics(); setDiag(d); } catch { /* silent */ }
  }, []);

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
    loadDiag();
    const interval = setInterval(loadStatus, 3000);
    const diagInterval = setInterval(loadDiag, 10000);
    return () => { clearInterval(interval); clearInterval(diagInterval); };
  }, [loadStatus, loadAIConfig, loadDiag]);

  const handleToggleAI = async () => {
    try {
      const next = !(status?.safeguards?.ai_auto_loop ?? false);
      await updateAiAutoLoop(next);
      await loadStatus();
    } catch { /* silent */ }
  };

  const handleMT5Login = async () => {
    if (!mt5Login || !mt5Password) return;
    setLoginResult(null);
    try {
      // BUG FIX: trả về báo cáo từng bước (locate/login/copy/attach/algo) để hiển
      // thị lỗi chính xác — trước đây bỏ qua kết quả, chỉ refresh status.
      const result = await loginMT5Account(Number(mt5Login), mt5Password, mt5Server);
      setLoginResult(result);
      await loadStatus();
      await loadDiag();
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
  const aiLoop = status?.safeguards?.ai_auto_loop || false;
  const currentMethod = aiConfig?.trading_method || status?.safeguards?.trading_method || 'SMC';

  // All trading methods supported - SNIPER, SMC, ICT, PRICE_ACTION, ULTRA_CONFLUENCE
  const methods = ['SNIPER', 'SMC', 'ICT', 'PRICE_ACTION', 'ULTRA_CONFLUENCE'];
  const methodLabels: Record<string, string> = {
    'SNIPER': 'SNIPER',
    'SMC': 'SMC',
    'ICT': 'ICT',
    'PRICE_ACTION': 'PA',
    'ULTRA_CONFLUENCE': 'ULTRA',
  };


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
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 4 }}>
            <div style={{ padding: '6px 4px', background: 'rgba(0,0,0,0.3)', borderRadius: 6, border: `1px solid ${C.border}`, textAlign: 'center', overflow: 'hidden' }}>
              <div style={{ fontSize: 7, color: C.muted, marginBottom: 2 }}>ACCOUNT</div>
              <div style={{ fontSize: 11, fontFamily: C.mono, fontWeight: 800, color: C.gold, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{status.account?.login || '---'}</div>
            </div>
            <div style={{ padding: '6px 4px', background: 'rgba(0,0,0,0.3)', borderRadius: 6, border: `1px solid ${C.border}`, textAlign: 'center', overflow: 'hidden' }}>
              <div style={{ fontSize: 7, color: C.muted, marginBottom: 2 }}>BALANCE</div>
              <div style={{ fontSize: 11, fontFamily: C.mono, fontWeight: 800, color: C.green, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>${(status.account?.balance || 0).toFixed(2)}</div>
            </div>
            <div style={{ padding: '6px 4px', background: 'rgba(0,0,0,0.3)', borderRadius: 6, border: `1px solid ${C.border}`, textAlign: 'center', overflow: 'hidden' }}>
              <div style={{ fontSize: 7, color: C.muted, marginBottom: 2 }}>EQUITY</div>
              <div style={{ fontSize: 11, fontFamily: C.mono, fontWeight: 800, color: C.cyan, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>${(status.account?.equity || 0).toFixed(2)}</div>
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

            {/* BUG FIX: hiển thị chẩn đoán — lý do EA chưa kết nối (allowlist/URL) */}
            <div style={{ marginTop: 6, padding: '8px 10px', background: 'rgba(244,63,94,0.06)', border: `1px solid ${C.redDim}`, borderRadius: 6 }}>
              <div style={{ fontSize: 7, fontFamily: C.mono, color: C.muted, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                MT5 Diagnostics
              </div>
              <div style={{ fontSize: 8, fontFamily: C.mono, color: C.text, lineHeight: '16px' }}>
                <div>EA TELEMETRY: <span style={{ color: diag?.ea_connected ? C.green : C.red, fontWeight: 800 }}>{diag?.ea_connected ? 'ONLINE' : 'CHƯA CÓ'}</span></div>
                <div>DATA: <span style={{ color: diag?.data_status === 'LIVE' ? C.green : C.gold }}>{diag?.data_status || status?.account?.data_status || 'STUB'}</span> · LAST: {diag?.last_ea_telemetry_at ? new Date(diag.last_ea_telemetry_at).toLocaleTimeString() : '—'}</div>
                <div style={{ color: C.muted, marginTop: 4 }}>EA URL (InpApiUrl): <span style={{ color: C.cyan }}>{diag?.ea_url_hint || '...'}</span></div>
                <div style={{ color: C.muted }}>⚠ Không dùng localhost — MT5 chặn. Thêm URL vào allowlist MT5.</div>
              </div>
            </div>

            {/* Kết quả đăng nhập MT5 (từng bước) */}
            {loginResult && (
              <div style={{ marginTop: 6, padding: '8px 10px', background: 'rgba(0,0,0,0.4)', border: `1px solid ${loginResult.status === 'SUCCESS' ? C.greenDim : C.redDim}`, borderRadius: 6 }}>
                <div style={{ fontSize: 7, fontFamily: C.mono, color: loginResult.status === 'SUCCESS' ? C.green : C.red, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                  {loginResult.status === 'SUCCESS' ? '✓ Connected' : '✗ Failed — ' + (loginResult.message || '')}
                </div>
                {(loginResult.steps || []).map((s: any, i: number) => (
                  <div key={i} style={{ fontSize: 8, fontFamily: C.mono, color: s.ok ? C.green : C.red, lineHeight: '15px' }}>
                    {s.ok ? '✓' : '✗'} {s.name}: {s.message}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* FIX LỖI 6: AI Auto Trade - single dot toggle only */}
      <Section title="AI Auto Trade">
        <div
          onClick={handleToggleAI}
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '14px 16px',
            background: aiLoop ? `linear-gradient(135deg, ${C.blueDim} 0%, rgba(5,7,12,0.9) 100%)` : 'rgba(5,7,12,0.9)',
            border: `1px solid ${aiLoop ? C.blue : C.border}`,
            borderRadius: 10, marginBottom: 8,
            cursor: 'pointer',
            boxShadow: aiLoop ? `0 0 20px ${C.blue}30` : 'none',
            transition: 'all 0.25s ease',
          }}
        >
          <div>
            <div style={{ fontSize: 10, fontFamily: C.mono, fontWeight: 800, color: C.text, textTransform: 'uppercase' }}>
              AI Auto Trade {aiLoop && <span style={{ marginLeft: 6, color: C.blue, fontSize: 8 }}>● RUNNING</span>}
            </div>
            <div style={{ fontSize: 8, fontFamily: C.mono, color: C.muted, marginTop: 3 }}>
              {aiLoop ? 'Bot scanning & auto-executing signals' : 'Manual mode — no auto entries'}
            </div>
          </div>
          {/* Pill toggle dot */}
          <div style={{
            width: 52, height: 28, borderRadius: 14,
            background: aiLoop ? C.blue : 'rgba(30,41,59,0.8)',
            border: `1px solid ${aiLoop ? C.blue : C.border}`,
            position: 'relative', flexShrink: 0,
            transition: 'all 0.25s ease',
          }}>
            <div style={{
              position: 'absolute', top: 2, left: aiLoop ? 26 : 2, width: 22, height: 22, borderRadius: '50%',
              background: '#fff',
              boxShadow: aiLoop ? `0 0 12px ${C.blue}` : 'none',
              transition: 'all 0.25s ease',
            }} />
          </div>
        </div>
      </Section>

      {/* FIX LỖI 5: Trading Method buttons */}
      <Section title="Trading Method">
        <div style={{ fontSize: 8, fontFamily: C.mono, color: aiLoop ? C.green : C.muted, marginBottom: 6 }}>
          ACTIVE: <span style={{ color: C.gold, fontWeight: 800 }}>{currentMethod}</span>
          {aiLoop ? ' · AI trading with this method' : ' · Enable AI Auto Trade to trade'}
        </div>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {methods.map(method => {
            const isActive = currentMethod === method;
            return (
              <button key={method} onClick={async () => { 
                try { 
                  const result = await updateTradingMethod(method); 
                  if (result && result.status === 'SUCCESS') {
                    await loadAIConfig();
                    await loadStatus();
                    onMethodChange?.(method);
                  }
                } catch (e) { console.error('Method change failed:', e); } 
              }}

                style={{
                  padding: '6px 12px', 
                  background: isActive ? C.goldDim : 'rgba(0,0,0,0.3)',
                  border: `1px solid ${isActive ? C.gold : C.border}`, 
                  borderRadius: 4, 
                  color: isActive ? C.gold : C.muted,
                  fontSize: 8, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer',
                  textTransform: 'uppercase',
                }}>
                {methodLabels[method] || method}
              </button>
            );
          })}
        </div>
      </Section>

      {/* QUICK ACTIONS */}
      <Section title="Quick Actions">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
          <button onClick={async () => { try { const token = localStorage.getItem('quantai_auth_token') || ''; const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {}; await fetch('/api/order/close_all', { method: 'POST', headers, credentials: 'include' }); await loadStatus(); } catch { /* silent */ } }}
            style={{ padding: '8px', background: C.redDim, border: `1px solid ${C.red}`, borderRadius: 6, color: C.red, fontSize: 8, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer' }}>Close All</button>
          <button onClick={async () => { try { const token = localStorage.getItem('quantai_auth_token') || ''; const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {}; await fetch('/api/reset_all', { method: 'POST', headers, credentials: 'include' }); await loadStatus(); } catch { /* silent */ } }}
            style={{ padding: '8px', background: 'rgba(0,0,0,0.3)', border: `1px solid ${C.border}`, borderRadius: 6, color: C.dim, fontSize: 8, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer' }}>Reset</button>
          <button onClick={async () => { try { const token = localStorage.getItem('quantai_auth_token') || ''; const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {}; await fetch('/api/orders/close-profitable', { method: 'POST', headers, credentials: 'include' }); await loadStatus(); } catch { /* silent */ } }}
            style={{ padding: '8px', background: C.greenDim, border: `1px solid ${C.green}`, borderRadius: 6, color: C.green, fontSize: 8, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer' }}>Close Profit</button>

          <button onClick={handleMT5Login}
            style={{ padding: '8px', background: C.blueDim, border: `1px solid ${C.blue}`, borderRadius: 6, color: C.blue, fontSize: 8, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer' }}>Test AI</button>
        </div>
      </Section>


      {/* SYSTEM STATUS */}
      <Section title="System">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 4 }}>
          {[
            { label: 'Backend', ok: !!status },
            { label: 'Bridge', ok: status?.bridge?.mt5_connected },
            // BUG FIX: "AI" trước đây sáng khi fetchAIConfig thành công — gây hiểu
            // lầm là bot đang chạy. Giờ phản ánh đúng AI Auto Trade loop.
            { label: 'AI Auto', ok: aiLoop },
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
