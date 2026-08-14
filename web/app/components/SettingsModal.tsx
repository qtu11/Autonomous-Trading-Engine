'use client';

import { useEffect, useState, useCallback } from 'react';
import { fetchSettings, updateSettings, loginMT5Account } from '@/lib/api';

const C = {
  gold: '#D4B483',
  goldDim: 'rgba(212,175,55,0.12)',
  green: '#22d3a0', greenDim: 'rgba(34,211,160,0.12)',
  red: '#f43f5e', redDim: 'rgba(244,63,94,0.12)',
  blue: '#38bdf8', blueDim: 'rgba(56,189,248,0.12)',
  cyan: '#06b6d4', amber: '#f59e0b',
  text: '#f8fafc', dim: '#cbd5e1', muted: '#64748b',
  border: 'rgba(255,255,255,0.06)',
  panelBg: 'rgba(8,12,22,0.96)',
  mono: '"JetBrains Mono", monospace',
};

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
  onUpdated?: (settings: any) => void;
}

export default function SettingsModal({ open, onClose, onUpdated }: SettingsModalProps) {
  const [data, setData] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [savedAt, setSavedAt] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'account' | 'ai' | 'risk' | 'telegram' | 'shortcuts'>('account');

  // Input states for interactive configuration
  const [telegramToken, setTelegramToken] = useState('');
  const [telegramChatId, setTelegramChatId] = useState('');
  const [mt5Login, setMt5Login] = useState('');
  const [mt5Pass, setMt5Pass] = useState('');
  const [mt5Server, setMt5Server] = useState('');
  const [customApiKey, setCustomApiKey] = useState('');
  const [customGatewayUrl, setCustomGatewayUrl] = useState('');

  const load = useCallback(async () => {
    try {
      const s = await fetchSettings();
      setData(s);
      const cfg = s?.runtime_config || {};
      setTelegramToken(s?.telegram_bot_token || cfg.telegram_bot_token || '');
      setTelegramChatId(s?.telegram_chat_id || cfg.telegram_chat_id || '');
      setMt5Login(String(s?.account?.login || cfg.mt5_login || ''));
      setMt5Server(s?.account?.server || cfg.mt5_server || '');
      setCustomApiKey(cfg.gateway_key || cfg.api_key || '');
      setCustomGatewayUrl(cfg.gateway_url || '');
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  if (!open) return null;

  const cfg = data?.runtime_config || {};
  const acc = data?.account || {};
  const models = data?.available_models || [
    { id: 'deepseek-v4-flash-free', name: 'DeepSeek V4 Flash (Free)', provider: 'OpenCode Zen' },
    { id: 'gpt-4o', name: 'GPT-4o', provider: 'OpenAI' },
    { id: 'gemini-1.5-pro', name: 'Gemini 1.5 Pro', provider: 'Google' },
    { id: 'claude-3-opus', name: 'Claude 3 Opus', provider: 'Anthropic' },
  ];

  const update = async (patch: Record<string, unknown>) => {
    setBusy(true);
    try {
      const res = await updateSettings(patch);
      if (res?.status === 'SUCCESS') {
        setSavedAt(new Date().toLocaleTimeString('en-US', { hour12: false }));
        await load();
        onUpdated?.(patch);
      }
    } catch { /* silent */ }
    finally { setBusy(false); }
  };

  const handleSaveTelegram = async () => {
    await update({
      telegram_bot_token: telegramToken,
      telegram_chat_id: telegramChatId,
      telegram_enabled: Boolean(telegramToken && telegramChatId),
    });
  };

  const handleConnectMT5 = async () => {
    setBusy(true);
    try {
      if (mt5Login) {
        await loginMT5Account(Number(mt5Login), mt5Pass, mt5Server);
      }

      await update({
        mt5_login: mt5Login,
        mt5_server: mt5Server,
      });
    } catch { /* silent */ }
    finally { setBusy(false); }
  };

  const handleSaveAIConfig = async () => {
    await update({
      gateway_key: customApiKey,
      gateway_url: customGatewayUrl,
    });
  };

  const tabs = [
    { id: 'account' as const, label: 'ACCOUNT' },
    { id: 'ai' as const, label: 'AI MODEL' },
    { id: 'risk' as const, label: 'RISK' },
    { id: 'telegram' as const, label: 'TELEGRAM' },
    { id: 'shortcuts' as const, label: 'SHORTCUTS' },
  ];

  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(10px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1100, padding: 16,
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        background: C.panelBg, border: `1px solid ${C.gold}`, borderRadius: 14,
        width: 'min(920px, 96vw)', maxHeight: '88vh', overflow: 'hidden',
        boxShadow: `0 20px 60px rgba(0,0,0,0.7), 0 0 30px ${C.gold}30`,
        display: 'flex', flexDirection: 'column', margin: 'auto',
      }}>
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '16px 20px', borderBottom: `1px solid ${C.border}`,
          background: `linear-gradient(180deg, ${C.goldDim} 0%, transparent 100%)`,
          flexShrink: 0,
        }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 800, color: C.gold, letterSpacing: '0.05em' }}>SETTINGS</div>
            <div style={{ fontSize: 9, color: C.muted, marginTop: 2 }}>Account · AI Model · Risk · Telegram · Shortcuts</div>
          </div>
          <button onClick={onClose} style={{ background: 'transparent', border: `1px solid ${C.border}`, color: C.dim, padding: '6px 12px', borderRadius: 6, fontSize: 10, cursor: 'pointer', fontFamily: C.mono }}>ESC · CLOSE</button>
        </div>

        {/* Tab bar */}
        <div style={{ display: 'flex', gap: 4, padding: '12px 20px', borderBottom: `1px solid ${C.border}`, flexShrink: 0, background: 'rgba(0,0,0,0.3)' }}>
          {tabs.map(tab => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)} style={{
              padding: '6px 14px',
              background: activeTab === tab.id ? C.goldDim : 'transparent',
              border: `1px solid ${activeTab === tab.id ? C.gold : C.border}`,
              borderRadius: 6, color: activeTab === tab.id ? C.gold : C.muted,
              fontSize: 9, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer',
            }}>
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content - auto scrolling */}
        <div style={{ flex: 1, overflow: 'auto', padding: 20 }}>
          {activeTab === 'account' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              {/* MT5 Account Info */}
              <Card title="MT5 ACCOUNT STATUS">
                <Row label="Login" value={String(acc.login || cfg.mt5_login || '---')} />
                <Row label="Server" value={acc.server || cfg.mt5_server || '---'} />
                <Row label="Balance" value={`$${Number(acc.balance || 0).toFixed(2)}`} />
                <Row label="Equity" value={`$${Number(acc.equity || 0).toFixed(2)}`} />
                <Row label="MT5 Connected" value={acc.mt5_connected ? 'YES' : 'NO'} valueColor={acc.mt5_connected ? C.green : C.red} />
                <Row label="EA Telemetry" value={acc.ea_connected ? 'ONLINE' : 'NO SIGNAL'} valueColor={acc.ea_connected ? C.green : C.red} />
                <Row label="Data Status" value={(acc.data_status || 'STUB') === 'LIVE' ? 'LIVE (MT5)' : 'STUB (fake)'} valueColor={acc.data_status === 'LIVE' ? C.green : C.gold} />
                <Row label="Last Telemetry" value={acc.last_ea_telemetry_at ? new Date(acc.last_ea_telemetry_at).toLocaleTimeString('en-US', { hour12: false }) : 'NEVER'} valueColor={acc.last_ea_telemetry_at ? C.dim : C.red} />
                <Row label="Execution Mode" value={cfg.execution_mode || 'DEMO'} />
                <Row label="Active Symbol" value={cfg.symbol || 'XAUUSD'} />
                <Row label="Timeframe" value={cfg.timeframe || 'M15'} />
                <Row label="EA Executor ID" value={acc.ea_executor_id || 'ate-ea-local'} valueColor={C.gold} />
                {!acc.ea_connected && (
                  <div style={{ marginTop: 8, padding: '8px 10px', background: 'rgba(244,63,94,0.06)', border: `1px solid rgba(244,63,94,0.25)`, borderRadius: 6, fontSize: 8, fontFamily: C.mono, color: C.dim, lineHeight: '15px' }}>
                    ⚠ EA CHƯA KẾT NỐI VỚI VERCEL WEB BACKEND PROXY:
                    <br />• Cần cấu hình biến môi trường <b>ATE_BACKEND_URL</b> trong Vercel Project Settings trỏ về Public IP / Cloudflare Tunnel của PC (ví dụ: <code>https://xxxx.trycloudflare.com</code> hoặc <code>http://&lt;PUBLIC_IP&gt;:8848</code>).
                    <br />• Trong MT5 EA cài <b>InpApiUrl = https://autonomous-trading-engine.vercel.app/api/v1/</b>
                    <br />• MT5 WebRequest Allowlist bắt buộc thêm <b>https://autonomous-trading-engine.vercel.app</b>
                    <br />• Đảm bảo nút <b>Algo Trading</b> trong MT5 đã bật (màu xanh).
                  </div>
                )}
              </Card>

              {/* CONNECT MT5 credentials */}
              <Card title="CONNECT MT5 ACCOUNT">
                <Field label="MT5 Login Account">
                  <input type="text" value={mt5Login} onChange={e => setMt5Login(e.target.value)} placeholder="Nhap so tk MT5..." style={inputStyle} />
                </Field>
                <Field label="MT5 Password">
                  <input type="password" value={mt5Pass} onChange={e => setMt5Pass(e.target.value)} placeholder="Nhap mat khau MT5..." style={inputStyle} />
                </Field>
                <Field label="MT5 Server">
                  <input type="text" value={mt5Server} onChange={e => setMt5Server(e.target.value)} placeholder="Ex: Exness-Real10" style={inputStyle} />
                </Field>
                <button onClick={handleConnectMT5} disabled={busy} style={{
                  width: '100%', padding: '10px', background: C.blueDim, border: `1px solid ${C.blue}`,
                  borderRadius: 6, color: C.blue, fontSize: 10, fontFamily: C.mono, fontWeight: 800, cursor: 'pointer', marginTop: 4,
                }}>
                  {busy ? 'CONNECTING...' : 'SAVE & CONNECT MT5'}
                </button>
              </Card>
            </div>
          )}

          {activeTab === 'ai' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <Card title="AI MODEL CONFIGURATION">
                <Field label="Active Model Provider">
                  <select value={cfg.active_ai_model || data?.active_ai_model || 'deepseek-v4-flash-free'}
                    onChange={e => update({ active_ai_model: e.target.value })}
                    style={selectStyle}>
                    {models.map((m: any) => (
                      <option key={m.id} value={m.id}>{m.name} — {m.provider}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Trading Method Strategy">
                  <select value={cfg.trading_method || 'SMC'} onChange={e => update({ trading_method: e.target.value })} style={selectStyle}>
                    {['SNIPER','SMC','ICT','PA','ULTRA'].map(m => <option key={m} value={m}>{m}</option>)}
                  </select>
                </Field>
                <Field label="AI Auto Loop Mode">
                  <Toggle on={!!cfg.ai_auto_loop} onChange={(v: boolean) => update({ ai_auto_loop: v })} />
                </Field>
                <Field label="Custom API Gateway Key (Optional)">
                  <input type="password" value={customApiKey} onChange={e => setCustomApiKey(e.target.value)} placeholder="sk-..." style={inputStyle} />
                </Field>
                <Field label="Custom Gateway URL (Optional)">
                  <input type="text" value={customGatewayUrl} onChange={e => setCustomGatewayUrl(e.target.value)} placeholder="https://api.openai.com/v1" style={inputStyle} />
                </Field>
                <button onClick={handleSaveAIConfig} disabled={busy} style={{
                  width: '100%', padding: '8px', background: C.goldDim, border: `1px solid ${C.gold}`,
                  borderRadius: 6, color: C.gold, fontSize: 9, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer', marginTop: 4,
                }}>
                  SAVE AI CONFIGURATION
                </button>
              </Card>

              <Card title="AVAILABLE AI PROVIDERS">
                {models.map((m: any) => (
                  <div key={m.id} style={{ padding: '8px 0', borderBottom: `1px solid ${C.border}` }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: 10, fontWeight: 700, color: C.text }}>{m.name}</span>
                      <span style={{ fontSize: 8, color: C.gold, background: C.goldDim, padding: '2px 6px', borderRadius: 3 }}>{m.provider}</span>
                    </div>
                    <div style={{ fontSize: 8, color: C.muted, marginTop: 2 }}>{m.id}</div>
                  </div>
                ))}
              </Card>
            </div>
          )}

          {activeTab === 'risk' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <Card title="RISK MANAGEMENT RULES">
                <Field label="Risk per Trade (%)">
                  <NumInput value={cfg.risk_per_trade_fraction ?? 0.01} step={0.005} min={0.001} max={0.10}
                    onCommit={(v: number) => update({ risk_per_trade_fraction: v })} />
                </Field>
                <Field label="Max Open Positions">
                  <NumInput value={cfg.max_open_positions ?? 5} step={1} min={1} max={20} int
                    onCommit={(v: number) => update({ max_open_positions: v })} />
                </Field>
                <Field label="Max Spread (pips)">
                  <NumInput value={cfg.max_spread ?? 4.5} step={0.5} min={0.5} max={50}
                    onCommit={(v: number) => update({ max_spread: v })} />
                </Field>
              </Card>

              <Card title="DCA — NHỒI LỆNH TRUNG BÌNH GIÁ">
                <div style={{ fontSize: 9, color: C.muted, marginBottom: 10 }}>
                  Tự thêm lệnh cùng hướng khi vị thế đang lỗ &gt;= N x ATR (luôn qua RiskGate + news protection)
                </div>
                <Field label="DCA Enabled">
                  <Toggle on={!!cfg.dca_enabled} onChange={(v: boolean) => update({ dca_enabled: v })} />
                </Field>
                <Field label="Max DCA Levels">
                  <NumInput value={cfg.dca_max_levels ?? 2} step={1} min={1} max={5} int
                    onCommit={(v: number) => update({ dca_max_levels: v })} />
                </Field>
                <Field label="Distance (x ATR)">
                  <NumInput value={cfg.dca_distance_atr ?? 1.5} step={0.5} min={0.5} max={10}
                    onCommit={(v: number) => update({ dca_distance_atr: v })} />
                </Field>
                <Field label="Volume Multiplier / Level">
                  <NumInput value={cfg.dca_volume_multiplier ?? 1.0} step={0.5} min={0.5} max={3}
                    onCommit={(v: number) => update({ dca_volume_multiplier: v })} />
                </Field>
                <Field label="Min Interval (s)">
                  <NumInput value={cfg.dca_interval_sec ?? 300} step={60} min={60} max={3600} int
                    onCommit={(v: number) => update({ dca_interval_sec: v })} />
                </Field>
                <Field label="Max Risk / Balance">
                  <NumInput value={cfg.dca_max_risk_balance_pct ?? 0.01} step={0.005} min={0.001} max={0.05}
                    onCommit={(v: number) => update({ dca_max_risk_balance_pct: v })} />
                </Field>
              </Card>

              <Card title="EMERGENCY CONTROLS" highlight>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                  <div>
                    <div style={{ fontSize: 11, color: C.red, fontWeight: 800 }}>KILL SWITCH</div>
                    <div style={{ fontSize: 9, color: C.muted, marginTop: 2 }}>Immediately closes all positions</div>
                  </div>
                  <Toggle on={!!cfg.kill_switch} onChange={(v: boolean) => update({ kill_switch: v })} color="red" />
                </div>
                <button onClick={() => {
                  const token = localStorage.getItem('quantai_auth_token') || '';
                  const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
                  fetch('/api/order/close_all', { method: 'POST', headers, credentials: 'include' }).then(onClose);
                }} style={{
                  width: '100%', padding: '10px', background: C.redDim, border: `1px solid ${C.red}`,
                  borderRadius: 6, color: C.red, fontSize: 9, fontFamily: C.mono, fontWeight: 800, cursor: 'pointer',
                }}>CLOSE ALL POSITIONS NOW</button>

              </Card>
            </div>
          )}

          {activeTab === 'telegram' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <Card title="TELEGRAM BOT CREDENTIALS">
                <Field label="Telegram Bot Token">
                  <input type="text" value={telegramToken} onChange={e => setTelegramToken(e.target.value)} placeholder="Ex: 123456789:ABCdef..." style={inputStyle} />
                </Field>
                <Field label="Telegram Chat ID">
                  <input type="text" value={telegramChatId} onChange={e => setTelegramChatId(e.target.value)} placeholder="Ex: -100123456789" style={inputStyle} />
                </Field>
                <button onClick={handleSaveTelegram} disabled={busy} style={{
                  width: '100%', padding: '10px', background: C.goldDim, border: `1px solid ${C.gold}`,
                  borderRadius: 6, color: C.gold, fontSize: 10, fontFamily: C.mono, fontWeight: 800, cursor: 'pointer', marginTop: 4,
                }}>
                  {busy ? 'SAVING...' : 'SAVE TELEGRAM CONFIG'}
                </button>
              </Card>

              <Card title="NOTIFICATION EVENT TOGGLES">
                <Field label="Notify on Open Position">
                  <Toggle on={data?.notify_on_open ?? true} onChange={(v: boolean) => update({ notify_on_open: v })} />
                </Field>
                <Field label="Notify on Close Position">
                  <Toggle on={data?.notify_on_close ?? true} onChange={(v: boolean) => update({ notify_on_close: v })} />
                </Field>
                <Field label="Notify on New Signal">
                  <Toggle on={data?.notify_on_signal ?? true} onChange={(v: boolean) => update({ notify_on_signal: v })} />
                </Field>
              </Card>
            </div>
          )}

          {activeTab === 'shortcuts' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <Card title="KEYBOARD SHORTCUTS">
                <Kbd k="Shift + C" desc="Close first position" />
                <Kbd k="Shift + A" desc="Toggle AI Auto Loop" />
                <Kbd k="Shift + K" desc="Kill Switch info" warn />
                <Kbd k="Shift + E" desc="Toggle Chart" />
                <Kbd k="Shift + M" desc="Toggle Compact Mode" />
                <Kbd k="Shift + Q" desc="Quick Trade Panel" />
                <Kbd k="Shift + 1" desc="Timeframe M1" />
                <Kbd k="Shift + 2" desc="Timeframe M5" />
                <Kbd k="Shift + 3" desc="Timeframe M15" />
                <Kbd k="Shift + 4" desc="Timeframe H1" />
                <Kbd k="Shift + 5" desc="Timeframe H4" />
                <Kbd k="Shift + /" desc="Show shortcuts" />
                <Kbd k="Esc" desc="Close modal" />
              </Card>

              <Card title="ABOUT SYSTEM">
                <Row label="Version" value="2.4.0" />
                <Row label="Build" value="ATE FINANCIAL DESK" valueColor={C.gold} />
                <Row label="Framework" value="Next.js + FastAPI" />
                <Row label="AI Engine" value="Multi-AI Provider Engine" />
                <div style={{ marginTop: 16, fontSize: 8, color: C.muted }}>
                  ATE — Autonomous Trading Engine<br/>
                  Institutional-grade trading terminal with AI-powered signal generation and MT5 execution bridge.
                </div>
              </Card>
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '10px 20px', borderTop: `1px solid ${C.border}`, fontSize: 9, color: C.muted, fontFamily: C.mono, flexShrink: 0,
        }}>
          <span>{busy ? 'Saving...' : savedAt ? `Saved at ${savedAt}` : 'Ready'}</span>
          <span>v2.4 · ATE DESK</span>
        </div>
      </div>
    </div>
  );
}

const Card = ({ title, children, highlight }: any) => (
  <div style={{
    background: highlight ? `linear-gradient(180deg, ${C.redDim} 0%, rgba(0,0,0,0.3) 100%)` : 'rgba(0,0,0,0.4)',
    border: `1px solid ${highlight ? C.red : C.border}`, borderRadius: 10, padding: 14,
  }}>
    <div style={{ fontSize: 10, fontWeight: 800, color: C.gold, letterSpacing: '0.08em', marginBottom: 10 }}>{title}</div>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>{children}</div>
  </div>
);

const Row = ({ label, value, valueColor }: any) => (
  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 0', borderBottom: `1px dashed ${C.border}` }}>
    <span style={{ fontSize: 9, color: C.muted, fontFamily: C.mono }}>{label}</span>
    <span style={{ fontSize: 10, color: valueColor || C.text, fontFamily: C.mono, fontWeight: 700 }}>{value}</span>
  </div>
);

const Field = ({ label, children }: any) => (
  <div>
    <div style={{ fontSize: 8, color: C.muted, fontFamily: C.mono, marginBottom: 4, textTransform: 'uppercase' }}>{label}</div>
    {children}
  </div>
);

const selectStyle = {
  width: '100%', padding: '8px 10px', background: 'rgba(0,0,0,0.5)',
  border: `1px solid ${C.border}`, borderRadius: 6, color: C.text,
  fontSize: 10, fontFamily: C.mono, outline: 'none', boxSizing: 'border-box' as any,
};

const inputStyle = {
  width: '100%', padding: '8px 10px', background: 'rgba(0,0,0,0.5)',
  border: `1px solid ${C.border}`, borderRadius: 6, color: C.text,
  fontSize: 10, fontFamily: C.mono, outline: 'none', boxSizing: 'border-box' as any,
};

const Toggle = ({ on, onChange, color = 'blue' }: any) => {
  const col = color === 'red' ? C.red : C.blue;
  return (
    <button onClick={() => onChange(!on)} style={{
      width: 50, height: 26, borderRadius: 13,
      background: on ? col : 'rgba(30,41,59,0.8)',
      border: `1px solid ${on ? col : C.border}`, cursor: 'pointer', position: 'relative',
    }}>
      <div style={{
        position: 'absolute', top: 2, left: on ? 26 : 2, width: 20, height: 20, borderRadius: '50%',
        background: '#fff', transition: 'all 0.25s ease',
      }} />
    </button>
  );
};

const NumInput = ({ value, step, min, max, int, onCommit }: any) => {
  const [local, setLocal] = useState(String(value));
  useEffect(() => { setLocal(String(value)); }, [value]);
  return (
    <input type="number" value={local} step={step} min={min} max={max}
      onChange={e => setLocal(e.target.value)}
      onBlur={() => { const n = int ? parseInt(local, 10) : parseFloat(local); if (!isNaN(n)) onCommit(n); }}
      onKeyDown={e => { if (e.key === 'Enter') (e.target as any).blur(); }}
      style={selectStyle} />
  );
};

const Kbd = ({ k, desc, warn }: any) => (
  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '5px 0', borderBottom: `1px solid ${C.border}` }}>
    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
      <span style={{ fontSize: 9, fontFamily: C.mono, fontWeight: 800, color: C.gold, background: C.goldDim, padding: '2px 8px', borderRadius: 4, minWidth: 80, textAlign: 'center' }}>{k}</span>
      <span style={{ fontSize: 10, color: C.dim, fontFamily: C.mono }}>{desc}</span>
    </div>
    {warn && <span style={{ fontSize: 9, color: C.amber }}>⚠</span>}
  </div>
);
