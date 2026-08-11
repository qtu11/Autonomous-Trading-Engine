'use client';

import { useState, useEffect, useRef, type CSSProperties } from 'react';
import { useRouter } from 'next/navigation';
import {
  fetchStatus, fetchControlCenterStatus, fetchPositions, fetchMarket,
  fetchHistory, fetchPendingOrders, fetchLogs, fetchBrain, fetchAdjustments,
  sendCopilotChat, executeOrderCloseAll, executeResetAll,
  executeCloseProfit, executeCloseLosing, updateAiAutoLoop, updateTradingMethod,
  type Candle, type Position, type TradeHistory,
  type ChatMsg, type TechnicalIndicators, type ControlCenterStatus, type PendingOrder,
  type LogEntry, type TodayPerformance, type BrainState, type BrainAdjustment,
  type MarkupResponse,
} from '../lib/api';
import ControlCenter from './components/ControlCenter';
import EconomicCalendar from './components/EconomicCalendar';

// ── Premium Institutional Design System ────────────────────────────────────────
const C = {
  bgMain: '#020305',
  panelBg: 'rgba(8, 12, 22, 0.92)',
  border: 'rgba(255, 255, 255, 0.06)',
  borderHighlight: 'rgba(212, 180, 131, 0.4)',
  gold: '#D4B483',
  green: '#22d3a0',
  greenBright: '#10b981',
  greenDim: 'rgba(34, 211, 160, 0.15)',
  red: '#f43f5e',
  redBright: '#ef4444',
  redDim: 'rgba(244, 63, 94, 0.15)',
  blue: '#38bdf8',
  cyan: '#06b6d4',
  amber: '#f59e0b',
  text: '#f8fafc',
  textBright: '#ffffff',
  dim: '#cbd5e1',
  muted: '#64748b',
  faint: '#475569',
  mono: '"JetBrains Mono", monospace',
  sans: '"Inter", -apple-system, BlinkMacSystemFont, sans-serif',
};

// ── Panel Component ────────────────────────────────────────────────────────────
interface PanelProps {
  children: React.ReactNode;
  title?: string;
  live?: boolean;
  headerRight?: React.ReactNode;
  style?: CSSProperties;
  className?: string;
}

function Panel({ children, title, live, headerRight, style, className }: PanelProps) {
  return (
    <div
      className={`gradient-border ${className || ''}`}
      style={{
        background: C.panelBg,
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        borderRadius: 10,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        ...style,
      }}
    >
      {title && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 14px',
          borderBottom: `1px solid ${C.border}`,
          background: 'linear-gradient(180deg, rgba(255,255,255,0.02) 0%, transparent 100%)',
          flexShrink: 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {live && <div className="live-indicator" style={{ width: 6, height: 6 }} />}
            <span style={{ fontSize: 9, fontWeight: 700, color: C.gold, letterSpacing: '0.1em', textTransform: 'uppercase', fontFamily: C.mono }}>
              {title}
            </span>
          </div>
          {headerRight}
        </div>
      )}
      <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>{children}</div>
    </div>
  );
}

// ── Mini Chart Component ──────────────────────────────────────────────────────
function MiniChart({ data, isUp }: { data: number[]; isUp: boolean }) {
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const h = 28, w = 80;
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((v - min) / range) * h;
    return `${x},${y}`;
  }).join(' ');

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
      <defs>
        <linearGradient id={`cg-${isUp ? 'up' : 'dn'}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={isUp ? C.green : C.red} stopOpacity="0.4" />
          <stop offset="100%" stopColor={isUp ? C.green : C.red} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={`0,${h} ${points} ${w},${h}`} fill={`url(#cg-${isUp ? 'up' : 'dn'})`} />
      <polyline points={points} fill="none" stroke={isUp ? C.green : C.red} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// ── Status Badge Component ────────────────────────────────────────────────────
function StatusBadge({ status, label }: { status: 'online' | 'offline' | 'warning'; label: string }) {
  const colors = {
    online: { bg: C.greenDim, border: C.green, text: C.green },
    offline: { bg: C.redDim, border: C.red, text: C.red },
    warning: { bg: 'rgba(245,158,11,0.15)', border: C.amber, text: C.amber },
  };
  const c = colors[status];
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 8px', background: c.bg, border: `1px solid ${c.border}`, borderRadius: 4 }}>
      <div style={{ width: 5, height: 5, borderRadius: '50%', background: c.text, boxShadow: status === 'online' ? `0 0 6px ${c.text}` : 'none' }} />
      <span style={{ fontSize: 9, fontFamily: C.mono, fontWeight: 700, color: c.text, letterSpacing: '0.05em' }}>{label}</span>
    </div>
  );
}

// ── Chat Message Type (matching API response) ───────────────────────────────────
interface ChatMessage {
  role: 'user' | 'ai';
  content: string;
  timestamp: string;
}

// ── Main Dashboard ────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const router = useRouter();
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [activeTab, setActiveTab] = useState<'positions' | 'orders' | 'history'>('positions');
  const [expandedSection, setExpandedSection] = useState<string | null>('brain');
  const [copilotInput, setCopilotInput] = useState('');
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [copilotTyping, setCopilotTyping] = useState(false);

  // Data states
  const [status, setStatus] = useState<any>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [market, setMarket] = useState<{ candles?: Candle[]; indicators?: TechnicalIndicators; markup?: MarkupResponse } | null>(null);
  const [history, setHistory] = useState<TradeHistory[]>([]);
  const [pendingOrders, setPendingOrders] = useState<PendingOrder[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [brain, setBrain] = useState<BrainState | null>(null);
  const [adjustments, setAdjustments] = useState<BrainAdjustment[]>([]);
  const [ccStatus, setCcStatus] = useState<ControlCenterStatus | null>(null);

  const chatRef = useRef<HTMLDivElement>(null);
  const logsRef = useRef<HTMLDivElement>(null);

  // Auth check
  useEffect(() => {
    const token = localStorage.getItem('quantai_auth_token');
    if (!token) { router.replace('/login'); return; }
    setIsAuthenticated(true);
  }, [router]);

  // Data polling
  useEffect(() => {
    if (!isAuthenticated) return;

    const loadAll = async () => {
      try {
        const [s, ps, m, h, po, l, b, a, cc] = await Promise.all([
          fetchStatus().catch(() => null),
          fetchPositions().catch(() => []),
          fetchMarket().catch(() => null),
          fetchHistory().catch(() => []),
          fetchPendingOrders().catch(() => []),
          fetchLogs({}).catch(() => []),
          fetchBrain().catch(() => null),
          fetchAdjustments().catch(() => []),
          fetchControlCenterStatus().catch(() => null),
        ]);
        setStatus(s);
        setPositions(ps || []);
        setMarket(m);
        setHistory(h || []);
        setPendingOrders(po || []);
        setLogs(l || []);
        setBrain(b);
        setAdjustments(a || []);
        setCcStatus(cc);
      } catch { /* silent */ }
    };

    loadAll();
    const interval = setInterval(loadAll, 5000);
    return () => clearInterval(interval);
  }, [isAuthenticated]);

  // Auto-scroll refs
  useEffect(() => { if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight; }, [chatHistory]);
  useEffect(() => { if (logsRef.current) logsRef.current.scrollTop = logsRef.current.scrollHeight; }, [logs]);

  // Copilot chat
  const handleCopilot = async () => {
    if (!copilotInput.trim() || copilotTyping) return;
    const userMsg: ChatMessage = { role: 'user', content: copilotInput, timestamp: new Date().toISOString() };
    setChatHistory(prev => [...prev, userMsg]);
    const query = copilotInput;
    setCopilotInput('');
    setCopilotTyping(true);

    try {
      const res = await sendCopilotChat(query);
      if (res) {
        // API returns {role: 'ai', text: string, time: string}
        const aiMsg: ChatMessage = { role: 'ai', content: res.text || 'Da xu ly yeu cau.', timestamp: new Date().toISOString() };
        setChatHistory(prev => [...prev, aiMsg]);
      } else {
        setChatHistory(prev => [...prev, { role: 'ai', content: 'Khong the xu ly yeu cau. Vui long thu lai.', timestamp: new Date().toISOString() }]);
      }
    } catch {
      setChatHistory(prev => [...prev, { role: 'ai', content: 'Khong the xu ly yeu cau. Vui long thu lai.', timestamp: new Date().toISOString() }]);
    } finally {
      setCopilotTyping(false);
    }
  };

  // Calculate metrics
  const openPnl = positions.reduce((s, p) => s + (p.profit || 0), 0);
  const realizedPnl = status?.today_performance?.realized_pl || 0;
  const totalPnl = openPnl + realizedPnl;
  const balance = status?.balance || status?.account?.balance || 0;
  const equity = balance + openPnl + realizedPnl;
  const marginUsed = positions.reduce((s, p) => s + ((p as any).margin || 0), 0);
  const marginLevel = equity > 0 && marginUsed > 0 ? (equity / marginUsed) * 100 : 0;

  // Generate mini chart data
  const generateMiniData = (base: number, len = 12): number[] => {
    const data = [base];
    for (let i = 1; i < len; i++) {
      data.push(data[i - 1] + (Math.random() - 0.48) * base * 0.005);
    }
    return data;
  };

  // Close position handler
  const handleClosePosition = async (ticket?: number) => {
    if (!ticket) return;
    try {
      await fetch('/api/order/close', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticket }),
      });
      setPositions(prev => prev.filter(p => p.ticket !== ticket));
    } catch { /* silent */ }
  };

  // Cancel order handler
  const handleCancelOrder = async (ticket?: number) => {
    if (!ticket) return;
    try {
      await fetch('/api/order/cancel_pending', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ order_ticket: ticket }),
      });
      setPendingOrders(prev => prev.filter(o => o.ticket !== ticket));
    } catch { /* silent */ }
  };

  if (!isAuthenticated) return null;

  // Extract AI bias/signal from brain state
  const aiBias = brain?.strategies?.[0]?.status === 'ACTIVE' 
    ? (brain.recent_decisions?.[0]?.action === 'BUY' ? 'BULLISH' : brain.recent_decisions?.[0]?.action === 'SELL' ? 'BEARISH' : 'NEUTRAL')
    : 'NEUTRAL';
  const aiSignal = brain?.recent_decisions?.[0]?.action || null;
  const aiConfidence = brain?.recent_decisions?.[0]?.confidence ? Math.round(brain.recent_decisions[0].confidence * 100) : 0;

  return (
    <div style={{ height: '100vh', width: '100vw', background: C.bgMain, display: 'flex', flexDirection: 'column', overflow: 'hidden', fontFamily: C.sans }}>
      {/* TOP BAR */}
      <div style={{
        height: 48,
        background: 'linear-gradient(180deg, rgba(10,14,24,0.98) 0%, rgba(5,7,12,0.95) 100%)',
        borderBottom: `1px solid ${C.border}`,
        display: 'flex', alignItems: 'center', padding: '0 16px', gap: 16, flexShrink: 0,
        backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)',
      }}>
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 28, height: 28, borderRadius: 6,
            background: 'linear-gradient(135deg, rgba(212,175,55,0.3) 0%, rgba(10,15,28,0.9) 100%)',
            border: '1px solid rgba(212,175,55,0.4)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={C.gold} strokeWidth="2">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
            </svg>
          </div>
          <div>
            <div style={{ fontSize: 11, fontFamily: C.mono, fontWeight: 800, color: C.gold, letterSpacing: '0.08em' }}>ATE DESK</div>
            <div style={{ fontSize: 7, fontFamily: C.mono, color: C.muted, letterSpacing: '0.05em' }}>INSTITUTIONAL TERMINAL</div>
          </div>
        </div>

        <div style={{ width: 1, height: 24, background: C.border }} />

        {/* Account Metrics */}
        <div style={{ display: 'flex', gap: 20, alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: 7, color: C.muted, fontFamily: C.mono }}>EQUITY</div>
            <div style={{ fontSize: 14, fontFamily: C.mono, fontWeight: 800, color: totalPnl >= 0 ? C.green : C.red }}>
              ${equity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 7, color: C.muted, fontFamily: C.mono }}>P&L TODAY</div>
            <div style={{ fontSize: 12, fontFamily: C.mono, fontWeight: 700, color: totalPnl >= 0 ? C.green : C.red }}>
              {totalPnl >= 0 ? '+' : ''}{totalPnl.toFixed(2)}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 7, color: C.muted, fontFamily: C.mono }}>MARGIN</div>
            <div style={{ fontSize: 11, fontFamily: C.mono, fontWeight: 600, color: C.dim }}>
              ${marginUsed.toFixed(2)} <span style={{ color: C.muted }}>/</span> <span style={{ color: marginLevel < 150 ? C.amber : C.muted }}>{marginLevel.toFixed(0)}%</span>
            </div>
          </div>
        </div>

        <div style={{ flex: 1 }} />

        {/* Status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <StatusBadge status={ccStatus?.account?.mt5_connected ? 'online' : 'offline'} label={ccStatus?.account?.mt5_connected ? 'MT5 CONNECTED' : 'MT5 OFFLINE'} />
          <StatusBadge status={ccStatus?.safeguards?.ai_auto_loop ? 'online' : 'offline'} label={ccStatus?.safeguards?.ai_auto_loop ? 'AI ARMED' : 'AI OFF'} />
        </div>

        {/* Clock */}
        <div style={{ padding: '4px 10px', background: 'rgba(0,0,0,0.4)', borderRadius: 6, border: `1px solid ${C.border}` }}>
          <div style={{ fontSize: 14, fontFamily: C.mono, fontWeight: 700, color: C.text }}>
            {new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}
          </div>
          <div style={{ fontSize: 7, fontFamily: C.mono, color: C.muted, textAlign: 'center' }}>
            VN {new Date().toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' })}
          </div>
        </div>
      </div>

      {/* MAIN CONTENT */}
      <div style={{
        flex: 1, display: 'grid',
        gridTemplateColumns: '320px 1fr 340px',
        gridTemplateRows: '1fr 280px',
        gap: 8, padding: 8, minHeight: 0, overflow: 'hidden',
        background: `radial-gradient(ellipse at 0% 0%, rgba(212,175,55,0.04) 0%, transparent 50%), radial-gradient(ellipse at 100% 100%, rgba(16,185,129,0.03) 0%, transparent 50%), linear-gradient(180deg, #030508 0%, #020305 100%)`,
      }}>
        {/* LEFT: CONTROL CENTER */}
        <div style={{ gridRow: '1 / 3', minHeight: 0, overflow: 'hidden' }}>
          <Panel title="Control Center" live className="animate-border-glow">
            <div style={{ height: '100%', overflow: 'auto' }}>
              <ControlCenter />
            </div>
          </Panel>
        </div>

        {/* CENTER TOP: POSITIONS & ORDERS */}
        <div style={{ minHeight: 0, overflow: 'hidden' }}>
          <Panel title="Positions & Orders" live>
            <div style={{ display: 'flex', borderBottom: `1px solid ${C.border}`, background: 'rgba(0,0,0,0.2)', flexShrink: 0 }}>
              {(['positions', 'orders', 'history'] as const).map(tab => (
                <button key={tab} onClick={() => setActiveTab(tab)} style={{
                  flex: 1, padding: '8px 12px',
                  background: activeTab === tab ? 'linear-gradient(180deg, rgba(212,175,55,0.15) 0%, rgba(212,175,55,0.05) 100%)' : 'transparent',
                  borderBottom: activeTab === tab ? `2px solid ${C.gold}` : '2px solid transparent',
                  color: activeTab === tab ? C.gold : C.muted,
                  fontSize: 9, fontFamily: C.mono, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', cursor: 'pointer', transition: 'all 0.2s ease',
                }}>
                  {tab === 'positions' ? `POSITIONS (${positions.length})` : tab === 'orders' ? `ORDERS (${pendingOrders.length})` : 'HISTORY'}
                </button>
              ))}
            </div>

            <div style={{ flex: 1, overflow: 'auto', padding: '4px 0' }}>
              {/* POSITIONS TAB */}
              {activeTab === 'positions' && (
                positions.length === 0 ? (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: C.muted, fontSize: 10, fontFamily: C.mono }}>
                    NO OPEN POSITIONS
                  </div>
                ) : (
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 9, fontFamily: C.mono }}>
                    <thead>
                      <tr style={{ background: 'rgba(0,0,0,0.3)', position: 'sticky', top: 0 }}>
                        {['SYMBOL', 'VOL', 'ENTRY', 'S/L', 'T/P', 'P&L', ''].map(h => (
                          <th key={h} style={{ padding: '4px 8px', textAlign: h === 'SYMBOL' || h === '' ? 'left' : 'right', color: C.muted, fontWeight: 600, borderBottom: `1px solid ${C.border}` }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {positions.map((pos, idx) => {
                        const isUp = (pos.profit || 0) >= 0;
                        const isBuy = String(pos.type).toUpperCase() === 'BUY';
                        return (
                          <tr key={idx} style={{ borderBottom: `1px solid ${C.border}`, transition: 'background 0.15s ease' }}
                            onMouseEnter={e => (e.currentTarget as HTMLTableRowElement).style.background = 'rgba(212,175,55,0.05)'}
                            onMouseLeave={e => (e.currentTarget as HTMLTableRowElement).style.background = 'transparent'}>
                            <td style={{ padding: '6px 8px' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <div style={{ width: 4, height: 16, borderRadius: 2, background: isBuy ? C.green : C.red, boxShadow: isBuy ? `0 0 6px ${C.green}` : `0 0 6px ${C.red}` }} />
                                <span style={{ fontWeight: 700, color: C.text }}>{(pos as any).symbol || 'XAUUSD'}</span>
                              </div>
                            </td>
                            <td style={{ padding: '6px 8px', textAlign: 'right', color: C.dim }}>{(pos as any).lot?.toFixed(2) || pos.lot?.toFixed(2) || '0.00'}</td>
                            <td style={{ padding: '6px 8px', textAlign: 'right', color: C.dim }}>{pos.entry?.toFixed(2) || '0.00'}</td>
                            <td style={{ padding: '6px 8px', textAlign: 'right', color: C.red }}>{pos.sl?.toFixed(2) || '-'}</td>
                            <td style={{ padding: '6px 8px', textAlign: 'right', color: C.green }}>{pos.tp?.toFixed(2) || '-'}</td>
                            <td style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 700, color: isUp ? C.green : C.red }}>{isUp ? '+' : ''}{pos.profit?.toFixed(2) || '0.00'}</td>
                            <td style={{ padding: '6px 8px', textAlign: 'right' }}>
                              <button onClick={() => handleClosePosition(pos.ticket)} style={{
                                padding: '2px 6px', background: 'rgba(244,63,94,0.15)', border: `1px solid ${C.red}`, borderRadius: 3, color: C.red, fontSize: 8, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer',
                              }}>CLOSE</button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )
              )}

              {/* ORDERS TAB */}
              {activeTab === 'orders' && (
                pendingOrders.length === 0 ? (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: C.muted, fontSize: 10, fontFamily: C.mono }}>
                    NO PENDING ORDERS
                  </div>
                ) : (
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 9, fontFamily: C.mono }}>
                    <thead>
                      <tr style={{ background: 'rgba(0,0,0,0.3)', position: 'sticky', top: 0 }}>
                        {['SYMBOL', 'TYPE', 'VOL', 'PRICE', 'S/L', 'T/P', ''].map(h => (
                          <th key={h} style={{ padding: '4px 8px', textAlign: h === 'SYMBOL' || h === 'TYPE' || h === '' ? 'left' : 'right', color: C.muted, fontWeight: 600, borderBottom: `1px solid ${C.border}` }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {pendingOrders.map((ord, idx) => (
                        <tr key={idx} style={{ borderBottom: `1px solid ${C.border}` }}>
                          <td style={{ padding: '6px 8px', fontWeight: 700 }}>{ord.symbol}</td>
                          <td style={{ padding: '6px 8px', textAlign: 'left', color: ord.type?.includes('BUY') ? C.green : C.red }}>{ord.type}</td>
                          <td style={{ padding: '6px 8px', textAlign: 'right' }}>{ord.volume?.toFixed(2)}</td>
                          <td style={{ padding: '6px 8px', textAlign: 'right' }}>{ord.price?.toFixed(2)}</td>
                          <td style={{ padding: '6px 8px', textAlign: 'right', color: C.red }}>{ord.sl?.toFixed(2)}</td>
                          <td style={{ padding: '6px 8px', textAlign: 'right', color: C.green }}>{ord.tp?.toFixed(2)}</td>
                          <td style={{ padding: '6px 8px', textAlign: 'right' }}>
                            <button onClick={() => handleCancelOrder(ord.ticket)} style={{
                              padding: '2px 6px', background: 'rgba(245,158,11,0.15)', border: `1px solid ${C.amber}`, borderRadius: 3, color: C.amber, fontSize: 8, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer',
                            }}>CANCEL</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )
              )}

              {/* HISTORY TAB */}
              {activeTab === 'history' && (
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 9, fontFamily: C.mono }}>
                  <thead>
                    <tr style={{ background: 'rgba(0,0,0,0.3)', position: 'sticky', top: 0 }}>
                      {['TIME', 'SYMBOL', 'P&L', 'CLOSE'].map(h => (
                        <th key={h} style={{ padding: '4px 8px', textAlign: h === 'TIME' || h === 'SYMBOL' ? 'left' : 'right', color: C.muted, fontWeight: 600, borderBottom: `1px solid ${C.border}` }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {history.slice(0, 20).map((h, idx) => (
                      <tr key={idx} style={{ borderBottom: `1px solid ${C.border}` }}>
                        <td style={{ padding: '4px 8px', color: C.muted }}>
                          {h.time ? new Date(h.time).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }) : '-'}
                        </td>
                        <td style={{ padding: '4px 8px', fontWeight: 700 }}>{h.symbol}</td>
                        <td style={{ padding: '4px 8px', textAlign: 'right', fontWeight: 700, color: (h.pl || 0) >= 0 ? C.green : C.red }}>
                          {(h.pl || 0) >= 0 ? '+' : ''}{(h.pl || 0).toFixed(2)}
                        </td>
                        <td style={{ padding: '4px 8px', textAlign: 'right', color: C.dim }}>{h.price?.toFixed(2) || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </Panel>
        </div>

        {/* CENTER BOTTOM: AI BRAIN & LOGS */}
        <div style={{ minHeight: 0, overflow: 'hidden' }}>
          <Panel>
            {/* AI Brain Section */}
            <div>
              <button onClick={() => setExpandedSection(prev => prev === 'brain' ? null : 'brain')} style={{
                width: '100%', padding: '8px 14px',
                background: 'linear-gradient(180deg, rgba(212,175,55,0.08) 0%, transparent 100%)',
                border: 'none', borderBottom: `1px solid ${C.border}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ width: 6, height: 6, borderRadius: '50%', background: aiSignal ? C.green : C.muted, boxShadow: aiSignal ? `0 0 8px ${C.green}` : 'none' }} />
                  <span style={{ fontSize: 9, fontFamily: C.mono, fontWeight: 700, color: C.gold, letterSpacing: '0.08em' }}>AI BRAIN MONITOR</span>
                </div>
                <span style={{ color: C.muted, fontSize: 10 }}>{expandedSection === 'brain' ? '−' : '+'}</span>
              </button>

              {expandedSection === 'brain' && (
                <div style={{ padding: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6 }}>
                    <div style={{ background: 'rgba(0,0,0,0.4)', border: `1px solid ${C.border}`, borderRadius: 6, padding: '6px 8px', textAlign: 'center' }}>
                      <div style={{ fontSize: 7, color: C.muted, fontFamily: C.mono, marginBottom: 2 }}>BIAS</div>
                      <div style={{ fontSize: 10, fontFamily: C.mono, fontWeight: 800, color: aiBias === 'BULLISH' ? C.green : aiBias === 'BEARISH' ? C.red : C.amber, textTransform: 'uppercase' }}>{aiBias}</div>
                    </div>
                    <div style={{ background: 'rgba(0,0,0,0.4)', border: `1px solid ${C.border}`, borderRadius: 6, padding: '6px 8px', textAlign: 'center' }}>
                      <div style={{ fontSize: 7, color: C.muted, fontFamily: C.mono, marginBottom: 2 }}>SIGNAL</div>
                      <div style={{ fontSize: 10, fontFamily: C.mono, fontWeight: 800, color: aiSignal === 'BUY' ? C.green : aiSignal === 'SELL' ? C.red : C.muted }}>{aiSignal || 'NONE'}</div>
                    </div>
                    <div style={{ background: 'rgba(0,0,0,0.4)', border: `1px solid ${C.border}`, borderRadius: 6, padding: '6px 8px', textAlign: 'center' }}>
                      <div style={{ fontSize: 7, color: C.muted, fontFamily: C.mono, marginBottom: 2 }}>CONFIDENCE</div>
                      <div style={{ fontSize: 10, fontFamily: C.mono, fontWeight: 800, color: C.cyan }}>{aiConfidence}%</div>
                    </div>
                  </div>

                  {/* Recent Decision */}
                  {brain?.recent_decisions?.[0] && (
                    <div style={{ background: 'linear-gradient(135deg, rgba(16,185,129,0.1) 0%, rgba(0,0,0,0.3) 100%)', border: `1px solid ${C.green}`, borderRadius: 6, padding: '8px 10px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                        <span style={{ fontSize: 8, color: C.muted, fontFamily: C.mono }}>LATEST DECISION</span>
                        <span style={{ fontSize: 10, fontFamily: C.mono, fontWeight: 800, color: brain.recent_decisions[0].action === 'BUY' ? C.green : C.red }}>{brain.recent_decisions[0].action}</span>
                      </div>
                      <div style={{ fontSize: 11, fontFamily: C.mono, color: C.text, fontWeight: 700 }}>
                        {brain.recent_decisions[0].entry ? `@ ${brain.recent_decisions[0].entry.toFixed(2)}` : 'Entry pending'}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Logs */}
            <div ref={logsRef} style={{ flex: 1, overflow: 'auto', padding: '4px 8px', minHeight: 0 }}>
              {logs.slice(0, 50).map((log, idx) => {
                const isError = log.level === 'ERROR' || log.level === 'CRITICAL';
                const isWarning = log.level === 'WARNING' || log.level === 'WARN';
                return (
                  <div key={idx} style={{ fontSize: 8, fontFamily: C.mono, padding: '2px 0', borderBottom: `1px solid rgba(255,255,255,0.02)`, display: 'flex', gap: 8 }}>
                    <span style={{ color: C.faint, flexShrink: 0 }}>{log.ts ? new Date(log.ts).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '-'}</span>
                    <span style={{ color: isError ? C.red : isWarning ? C.amber : C.muted, fontWeight: isError || isWarning ? 700 : 500, flexShrink: 0, width: 50 }}>{log.level}</span>
                    <span style={{ color: C.dim, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{log.message}</span>
                  </div>
                );
              })}
            </div>
          </Panel>
        </div>

        {/* RIGHT: MARKET & COPILOT */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minHeight: 0, overflow: 'hidden' }}>
          {/* Market Overview */}
          <div style={{ flex: 1, minHeight: 0 }}>
            <Panel title="Market Overview" live>
              <div style={{ flex: 1, overflow: 'auto', padding: 8 }}>
                {[
                  { symbol: 'XAUUSD', name: 'Gold', price: market?.indicators ? (market.candles?.[market.candles.length - 1]?.c || 2845.50) : 2845.50, change: 0.85 },
                  { symbol: 'EURUSD', name: 'Euro', price: 1.0845, change: 0.12 },
                  { symbol: 'GBPUSD', name: 'Pound', price: 1.2650, change: -0.05 },
                  { symbol: 'USDJPY', name: 'Yen', price: 149.80, change: 0.15 },
                ].map((sym) => {
                  const isUp = sym.change >= 0;
                  return (
                    <div key={sym.symbol} style={{
                      background: 'linear-gradient(135deg, rgba(5,7,12,0.8) 0%, rgba(3,5,8,0.9) 100%)',
                      border: `1px solid ${C.border}`, borderRadius: 8, padding: '8px 10px', marginBottom: 6,
                      display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer',
                      transition: 'all 0.2s ease',
                    }}
                      onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.borderColor = isUp ? C.green : C.red; }}
                      onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.borderColor = C.border; }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                          <span style={{ fontSize: 10, fontFamily: C.mono, fontWeight: 800, color: C.text }}>{sym.symbol}</span>
                          <span style={{ fontSize: 7, color: C.muted, fontFamily: C.mono }}>{sym.name}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                          <span style={{ fontSize: 14, fontFamily: C.mono, fontWeight: 800, color: C.textBright }}>
                            {sym.price.toLocaleString('en-US', { minimumFractionDigits: sym.price < 10 ? 4 : 2, maximumFractionDigits: sym.price < 10 ? 4 : 2 })}
                          </span>
                          <span style={{ fontSize: 10, fontFamily: C.mono, fontWeight: 700, color: isUp ? C.green : C.red }}>{isUp ? '+' : ''}{sym.change.toFixed(2)}%</span>
                        </div>
                      </div>
                      <MiniChart data={generateMiniData(sym.price * 0.999, 10)} isUp={isUp} />
                    </div>
                  );
                })}
              </div>
            </Panel>
          </div>

          {/* AI Copilot Chat */}
          <div style={{ height: 280, minHeight: 0 }}>
            <Panel title="AI Copilot">
              <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                <div ref={chatRef} style={{ flex: 1, overflow: 'auto', padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 6, minHeight: 0 }}>
                  {chatHistory.length === 0 && (
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: C.muted, fontSize: 9, fontFamily: C.mono, textAlign: 'center', gap: 8 }}>
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke={C.gold} strokeWidth="1.5"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" /></svg>
                      <span>AI Copilot san sang ho tro<br />Phan tich, danh gia, khuyen nghi</span>
                    </div>
                  )}
                  {chatHistory.map((msg, idx) => (
                    <div key={idx} style={{
                      padding: '6px 8px', borderRadius: 6,
                      background: msg.role === 'user' ? 'linear-gradient(135deg, rgba(212,175,55,0.15) 0%, rgba(212,175,55,0.05) 100%)' : 'rgba(0,0,0,0.4)',
                      border: msg.role === 'user' ? `1px solid rgba(212,175,55,0.3)` : `1px solid ${C.border}`,
                      maxWidth: '85%', alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                    }}>
                      <div style={{ fontSize: 8, color: msg.role === 'user' ? C.gold : C.cyan, fontFamily: C.mono, fontWeight: 700, marginBottom: 2 }}>
                        {msg.role === 'user' ? 'OPERATOR' : 'AI COPILOT'}
                      </div>
                      <div style={{ fontSize: 9, color: C.dim, fontFamily: C.sans, lineHeight: 1.4 }}>{msg.content}</div>
                    </div>
                  ))}
                  {copilotTyping && (
                    <div style={{ padding: '6px 8px', borderRadius: 6, background: 'rgba(0,0,0,0.4)', border: `1px solid ${C.border}`, maxWidth: '85%' }}>
                      <div style={{ fontSize: 8, color: C.cyan, fontFamily: C.mono, fontWeight: 700, marginBottom: 4 }}>AI COPILOT</div>
                      <div style={{ display: 'flex', gap: 4 }}>
                        {[0, 1, 2].map(i => <div key={i} style={{ width: 4, height: 4, borderRadius: '50%', background: C.cyan, animation: `livePulse 1s ease-in-out ${i * 0.2}s infinite` }} />)}
                      </div>
                    </div>
                  )}
                </div>

                <div style={{ padding: '8px 10px', borderTop: `1px solid ${C.border}`, background: 'rgba(0,0,0,0.3)', display: 'flex', gap: 8 }}>
                  <input type="text" value={copilotInput} onChange={e => setCopilotInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleCopilot()}
                    placeholder="Ask AI Copilot..." style={{ flex: 1, padding: '6px 10px', background: 'rgba(0,0,0,0.5)', border: `1px solid ${C.border}`, borderRadius: 6, color: C.text, fontSize: 9, fontFamily: C.mono, outline: 'none' }}
                    onFocus={e => e.target.style.borderColor = C.gold} onBlur={e => e.target.style.borderColor = C.border} />
                  <button onClick={handleCopilot} disabled={copilotTyping} style={{
                    padding: '6px 12px', background: 'linear-gradient(135deg, rgba(212,175,55,0.3) 0%, rgba(212,175,55,0.1) 100%)',
                    border: `1px solid ${C.gold}`, borderRadius: 6, color: C.gold, fontSize: 9, fontFamily: C.mono, fontWeight: 700, cursor: copilotTyping ? 'wait' : 'pointer',
                  }}>SEND</button>
                </div>
              </div>
            </Panel>
          </div>
        </div>

        {/* ECONOMIC CALENDAR */}
        <div style={{ minHeight: 0 }}>
          <Panel title="Economic Calendar" live>
            <EconomicCalendar />
          </Panel>
        </div>
      </div>
    </div>
  );
}
