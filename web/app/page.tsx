'use client';

import { useState, useEffect, useRef, useCallback, type CSSProperties } from 'react';
import { useRouter } from 'next/navigation';
import {
  fetchStatus, fetchControlCenterStatus, fetchPositions, fetchMarket,
  fetchHistory, fetchPendingOrders, fetchLogs, fetchBrain,
  sendCopilotChat,
  type Candle, type Position, type TradeHistory,
  type ChatMsg, type ControlCenterStatus, type PendingOrder,
  type LogEntry, type BrainState,
  type MarkupResponse,
} from '../lib/api';
import ControlCenter from './components/ControlCenter';
import EconomicCalendar from './components/EconomicCalendar';
import TradingChart from './components/TradingChart';
import RiskCalculator from './components/RiskCalculator';
import Watchlist from './components/Watchlist';
import EquityCurve from './components/EquityCurve';
import PerformanceCharts from './components/PerformanceCharts';
import PatternAlert from './components/PatternAlert';
import SentimentGauge from './components/SentimentGauge';
import TradeJournal from './components/TradeJournal';
import QuickTradePanel from './components/QuickTradePanel';

// Design System
const C = {
  bgMain: '#020305',
  panelBg: 'rgba(8, 12, 22, 0.92)',
  border: 'rgba(255, 255, 255, 0.06)',
  gold: '#D4B483',
  goldDim: 'rgba(212, 175, 55, 0.12)',
  green: '#22d3a0',
  greenDim: 'rgba(34, 211, 160, 0.15)',
  red: '#f43f5e',
  redDim: 'rgba(244, 63, 94, 0.15)',
  blue: '#38bdf8',
  blueDim: 'rgba(56, 189, 248, 0.12)',
  cyan: '#06b6d4',
  amber: '#f59e0b',
  amberDim: 'rgba(245, 158, 11, 0.15)',
  text: '#f8fafc',
  dim: '#cbd5e1',
  muted: '#64748b',
  mono: '"JetBrains Mono", monospace',
  sans: '"Inter", -apple-system, sans-serif',
};

// Panel Component
function Panel({ children, title, live, style, className }: {
  children: React.ReactNode;
  title?: string;
  live?: boolean;
  style?: CSSProperties;
  className?: string;
}) {
  return (
    <div className={className} style={{
      background: C.panelBg, backdropFilter: 'blur(20px)',
      borderRadius: 10, overflow: 'hidden', display: 'flex', flexDirection: 'column', ...style,
    }}>
      {title && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', borderBottom: `1px solid ${C.border}`,
          background: 'linear-gradient(180deg, rgba(255,255,255,0.02) 0%, transparent 100%)',
        }}>
          {live && <div style={{ width: 6, height: 6, borderRadius: '50%', background: C.green, boxShadow: `0 0 8px ${C.green}`, animation: 'pulse 2s infinite' }} />}
          <span style={{ fontSize: 9, fontFamily: C.mono, fontWeight: 700, color: C.gold, letterSpacing: '0.1em', textTransform: 'uppercase' }}>{title}</span>
        </div>
      )}
      <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>{children}</div>
    </div>
  );
}

function StatusBadge({ status, label }: { status: 'online' | 'offline' | 'warning'; label: string }) {
  const colors = { online: { bg: C.greenDim, color: C.green }, offline: { bg: C.redDim, color: C.red }, warning: { bg: C.amberDim, color: C.amber } };
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '3px 8px', background: colors[status].bg, border: `1px solid ${colors[status].color}`, borderRadius: 4 }}>
      <div style={{ width: 5, height: 5, borderRadius: '50%', background: colors[status].color, boxShadow: status === 'online' ? `0 0 6px ${colors[status].color}` : 'none' }} />
      <span style={{ fontSize: 9, fontFamily: C.mono, fontWeight: 700, color: colors[status].color }}>{label}</span>
    </div>
  );
}

interface ChatMessage { role: 'user' | 'ai'; content: string; timestamp: string; }

export default function DashboardPage() {
  const router = useRouter();
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [activeTab, setActiveTab] = useState<'positions' | 'orders' | 'history' | 'journal'>('positions');
  const [chartTf, setChartTf] = useState('M15');
  const [showChart, setShowChart] = useState(true);
  const [showCompact, setShowCompact] = useState(false);
  const [showQuickTrade, setShowQuickTrade] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [copilotInput, setCopilotInput] = useState('');
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [copilotTyping, setCopilotTyping] = useState(false);
  const [notifications, setNotifications] = useState<Array<{ id: number; message: string; type: 'info' | 'success' | 'warning' | 'error' }>>([]);
  const [selectedSymbol, setSelectedSymbol] = useState('XAUUSD');

  const [status, setStatus] = useState<any>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [market, setMarket] = useState<{ candles?: Candle[]; markup?: MarkupResponse } | null>(null);
  const [history, setHistory] = useState<TradeHistory[]>([]);
  const [pendingOrders, setPendingOrders] = useState<PendingOrder[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [brain, setBrain] = useState<BrainState | null>(null);
  const [ccStatus, setCcStatus] = useState<ControlCenterStatus | null>(null);

  const chatRef = useRef<HTMLDivElement>(null);
  const logsRef = useRef<HTMLDivElement>(null);
  const notifId = useRef(0);

  // Auth check
  useEffect(() => {
    const token = localStorage.getItem('quantai_auth_token');
    if (!token) { router.replace('/login'); return; }
    setIsAuthenticated(true);
  }, [router]);

  // Add notification
  const addNotif = useCallback((message: string, type: 'info' | 'success' | 'warning' | 'error' = 'info') => {
    const id = ++notifId.current;
    setNotifications(prev => [...prev, { id, message, type }]);
    setTimeout(() => setNotifications(prev => prev.filter(n => n.id !== id)), 5000);
  }, []);

  // Data polling
  useEffect(() => {
    if (!isAuthenticated) return;
    const loadAll = async () => {
      try {
        const [s, ps, m, h, po, l, b, cc] = await Promise.all([
          fetchStatus().catch(() => null),
          fetchPositions().catch(() => []),
          fetchMarket(selectedSymbol, chartTf).catch(() => null),
          fetchHistory().catch(() => []),
          fetchPendingOrders().catch(() => []),
          fetchLogs({}).catch(() => []),
          fetchBrain().catch(() => null),
          fetchControlCenterStatus().catch(() => null),
        ]);
        setStatus(s); setPositions(ps || []); setMarket(m); setHistory(h || []);
        setPendingOrders(po || []); setLogs(l || []); setBrain(b); setCcStatus(cc);
      } catch { /* silent */ }
    };
    loadAll();
    const interval = setInterval(loadAll, 3000);
    return () => clearInterval(interval);
  }, [isAuthenticated, chartTf, selectedSymbol]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      switch (e.key.toLowerCase()) {
        case 'c': handleClosePosition(positions[0]?.ticket); break;
        case 'a': toggleAiLoop(); break;
        case 'k': toggleKillSwitch(); break;
        case 'e': setShowChart(v => !v); break;
        case 'm': setShowCompact(v => !v); break;
        case 'q': setShowQuickTrade(v => !v); break;
        case '?': setShowShortcuts(v => !v); break;
        case 'escape': setShowShortcuts(false); setShowQuickTrade(false); break;
        case '1': setChartTf('M1'); break;
        case '2': setChartTf('M5'); break;
        case '3': setChartTf('M15'); break;
        case '4': setChartTf('H1'); break;
        case '5': setChartTf('H4'); break;
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [positions]);

  // Auto-scroll
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
      setChatHistory(prev => [...prev, { role: 'ai', content: res?.text || 'Da xu ly.', timestamp: new Date().toISOString() }]);
    } catch { setChatHistory(prev => [...prev, { role: 'ai', content: 'Loi. Thu lai.', timestamp: new Date().toISOString() }]); }
    finally { setCopilotTyping(false); }
  };

  // Metrics
  const openPnl = positions.reduce((s, p) => s + (p.profit || 0), 0);
  const realizedPnl = status?.today_performance?.realized_pl || 0;
  const totalPnl = openPnl + realizedPnl;
  const balance = status?.balance || 10000;
  const equity = balance + totalPnl;
  const marginUsed = positions.reduce((s, p) => s + ((p as any).margin || 0), 0);
  const marginLevel = equity > 0 && marginUsed > 0 ? (equity / marginUsed) * 100 : 999;
  const todayPerf = status?.today_performance;
  const winRate = todayPerf?.trades_today ? ((todayPerf.wins / todayPerf.trades_today) * 100).toFixed(0) : '65';

  // AI Brain
  const aiSignal = brain?.recent_decisions?.[0];
  const aiBias = aiSignal?.action === 'BUY' ? 'BULLISH' : aiSignal?.action === 'SELL' ? 'BEARISH' : 'NEUTRAL';
  const aiConfidence = aiSignal?.confidence ? Math.round(aiSignal.confidence * 100) : 0;

  // Actions
  const handleClosePosition = async (ticket?: number) => {
    if (!ticket) return;
    try { await fetch('/api/order/close', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ticket }) }); setPositions(prev => prev.filter(p => p.ticket !== ticket)); addNotif('Position closed', 'success'); }
    catch { addNotif('Failed to close', 'error'); }
  };
  const handleCancelOrder = async (ticket?: number) => {
    if (!ticket) return;
    try { await fetch('/api/order/cancel_pending', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ order_ticket: ticket }) }); setPendingOrders(prev => prev.filter(o => o.ticket !== ticket)); addNotif('Order cancelled', 'success'); }
    catch { addNotif('Failed to cancel', 'error'); }
  };
  const toggleAiLoop = () => addNotif('AI Loop toggled', 'info');
  const toggleKillSwitch = () => addNotif('Kill switch toggled', 'warning');
  const handleQuickTrade = (order: any) => { addNotif(`Order ${order.type} sent`, 'success'); };

  if (!isAuthenticated) return null;

  const notifColors = { info: C.blue, success: C.green, warning: C.amber, error: C.red };

  return (
    <div style={{ height: '100vh', width: '100vw', background: C.bgMain, display: 'flex', flexDirection: 'column', overflow: 'hidden', fontFamily: C.sans }}>
      {/* TOP BAR */}
      <div style={{ height: 52, background: 'linear-gradient(180deg, rgba(10,14,24,0.98) 0%, rgba(5,7,12,0.95) 100%)', borderBottom: `1px solid ${C.border}`, display: 'flex', alignItems: 'center', padding: '0 16px', gap: 16, flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: 'linear-gradient(135deg, rgba(212,175,55,0.3) 0%, rgba(10,15,28,0.9) 100%)', border: '1px solid rgba(212,175,55,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={C.gold} strokeWidth="2"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" /></svg>
          </div>
          <div>
            <div style={{ fontSize: 12, fontFamily: C.mono, fontWeight: 800, color: C.gold }}>ATE DESK</div>
            <div style={{ fontSize: 7, fontFamily: C.mono, color: C.muted }}>INSTITUTIONAL TERMINAL</div>
          </div>
        </div>

        <div style={{ width: 1, height: 28, background: C.border }} />

        <div style={{ display: 'flex', gap: 12 }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 7, color: C.muted, fontFamily: C.mono }}>EQUITY</div>
            <div style={{ fontSize: 16, fontFamily: C.mono, fontWeight: 800, color: totalPnl >= 0 ? C.green : C.red }}>${equity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
          </div>
          <div style={{ width: 1, background: C.border }} />
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 7, color: C.muted, fontFamily: C.mono }}>P&L</div>
            <div style={{ fontSize: 16, fontFamily: C.mono, fontWeight: 800, color: totalPnl >= 0 ? C.green : C.red }}>{totalPnl >= 0 ? '+' : ''}{totalPnl.toFixed(2)}</div>
          </div>
          <div style={{ width: 1, background: C.border }} />
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 7, color: C.muted, fontFamily: C.mono }}>WIN RATE</div>
            <div style={{ fontSize: 16, fontFamily: C.mono, fontWeight: 800, color: C.cyan }}>{winRate}%</div>
          </div>
          <div style={{ width: 1, background: C.border }} />
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 7, color: C.muted, fontFamily: C.mono }}>MARGIN</div>
            <div style={{ fontSize: 14, fontFamily: C.mono, fontWeight: 800, color: marginLevel < 150 ? C.amber : C.dim }}>{marginLevel.toFixed(0)}%</div>
          </div>
        </div>

        <div style={{ flex: 1 }} />

        {/* Toggles */}
        <button onClick={() => setShowChart(v => !v)} style={{ padding: '6px 10px', background: showChart ? C.goldDim : 'transparent', border: `1px solid ${showChart ? C.gold : C.border}`, borderRadius: 6, color: showChart ? C.gold : C.muted, fontSize: 9, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer' }}>CHART</button>
        <button onClick={() => setShowCompact(v => !v)} style={{ padding: '6px 10px', background: showCompact ? C.goldDim : 'transparent', border: `1px solid ${showCompact ? C.gold : C.border}`, borderRadius: 6, color: showCompact ? C.gold : C.muted, fontSize: 9, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer' }}>{showCompact ? 'EXPAND' : 'COMPACT'}</button>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <StatusBadge status={ccStatus?.account?.mt5_connected ? 'online' : 'offline'} label="MT5" />
          <StatusBadge status={ccStatus?.safeguards?.ai_auto_loop ? 'online' : 'offline'} label="AI" />
          <StatusBadge status={positions.length > 0 ? 'online' : 'offline'} label={`POS ${positions.length}`} />
        </div>

        <button onClick={() => setShowShortcuts(v => !v)} style={{ padding: '6px 8px', background: 'transparent', border: `1px solid ${C.border}`, borderRadius: 6, color: C.muted, fontSize: 10, cursor: 'pointer' }}>?</button>

        <div style={{ padding: '4px 12px', background: 'rgba(0,0,0,0.4)', borderRadius: 6, border: `1px solid ${C.border}`, textAlign: 'center' }}>
          <div style={{ fontSize: 14, fontFamily: C.mono, fontWeight: 700, color: C.text }}>{new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}</div>
          <div style={{ fontSize: 7, fontFamily: C.mono, color: C.muted }}>VN {new Date().toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' })}</div>
        </div>
      </div>

      {/* KEYBOARD SHORTCUTS MODAL */}
      {showShortcuts && (
        <div onClick={() => setShowShortcuts(false)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div onClick={e => e.stopPropagation()} style={{ background: C.panelBg, border: `1px solid ${C.gold}`, borderRadius: 12, padding: 24, minWidth: 300 }}>
            <div style={{ fontSize: 12, fontFamily: C.mono, fontWeight: 800, color: C.gold, marginBottom: 16, textAlign: 'center' }}>KEYBOARD SHORTCUTS</div>
            {[
              ['C', 'Close position', ''],
              ['A', 'Toggle AI Loop', ''],
              ['K', 'Kill Switch', '⚠️'],
              ['E', 'Toggle Chart', ''],
              ['M', 'Toggle Compact', ''],
              ['Q', 'Quick Trade Panel', ''],
              ['1-5', 'Switch Timeframe', ''],
              ['?', 'Show shortcuts', ''],
              ['Esc', 'Close modal', ''],
            ].map(([key, desc, warn]) => (
              <div key={key} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: `1px solid ${C.border}` }}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span style={{ fontSize: 10, fontFamily: C.mono, fontWeight: 700, color: C.gold, background: C.goldDim, padding: '2px 8px', borderRadius: 4 }}>{key}</span>
                  <span style={{ fontSize: 10, fontFamily: C.mono, color: C.dim }}>{desc}</span>
                </div>
                {warn && <span style={{ fontSize: 9, color: C.amber }}>{warn}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* MAIN CONTENT */}
      <div style={{
        flex: 1, display: 'grid',
        gridTemplateColumns: showCompact ? '240px 1fr 280px' : '300px 1fr 320px',
        gridTemplateRows: showCompact ? '1fr' : '1fr 220px',
        gap: 8, padding: 8, minHeight: 0, overflow: 'hidden',
        background: `radial-gradient(ellipse at 0% 0%, rgba(212,175,55,0.04) 0%, transparent 50%), radial-gradient(ellipse at 100% 100%, rgba(34,211,160,0.03) 0%, transparent 50%), ${C.bgMain}`,
      }}>
        {/* LEFT COLUMN */}
        <div style={{ gridRow: showCompact ? '1' : '1 / 3', minHeight: 0, overflow: 'hidden' }}>
          <Panel title="Control Center" live style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <div style={{ flex: 1, overflow: 'auto' }}>
              <ControlCenter />
            </div>
            {!showCompact && (
              <div style={{ borderTop: `1px solid ${C.border}` }}>
                <EquityCurve currentEquity={equity} initialBalance={balance} />
                <RiskCalculator accountBalance={balance} onQuickTrade={handleQuickTrade} />
              </div>
            )}
          </Panel>
        </div>

        {/* CENTER COLUMN */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minHeight: 0, overflow: 'hidden' }}>
          {showChart && (
            <div style={{ flex: showCompact ? 1 : 0.6, minHeight: 0 }}>
              <Panel title={`${selectedSymbol} ${chartTf}`} live style={{ height: '100%', position: 'relative' }}>
                <div style={{ position: 'absolute', top: 8, right: 8, zIndex: 10, display: 'flex', gap: 4 }}>
                  {['M1', 'M5', 'M15', 'H1', 'H4', 'D1'].map(tf => (
                    <button key={tf} onClick={() => setChartTf(tf)} style={{ padding: '4px 8px', background: chartTf === tf ? C.goldDim : 'rgba(0,0,0,0.5)', border: `1px solid ${chartTf === tf ? C.gold : C.border}`, borderRadius: 4, color: chartTf === tf ? C.gold : C.muted, fontSize: 8, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer' }}>{tf}</button>
                  ))}
                </div>
                <TradingChart symbol={selectedSymbol} timeframe={chartTf} candles={market?.candles} markup={market?.markup} positions={positions as any} />
              </Panel>
            </div>
          )}

          {/* Positions/Orders/Journal */}
          <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
            <Panel title="Positions" live style={{ height: '100%' }}>
              <div style={{ display: 'flex', borderBottom: `1px solid ${C.border}` }}>
                {(['positions', 'orders', 'history', 'journal'] as const).map(tab => (
                  <button key={tab} onClick={() => setActiveTab(tab)} style={{ flex: 1, padding: '6px', background: activeTab === tab ? C.goldDim : 'transparent', borderBottom: activeTab === tab ? `2px solid ${C.gold}` : '2px solid transparent', color: activeTab === tab ? C.gold : C.muted, fontSize: 8, fontFamily: C.mono, fontWeight: 700, textTransform: 'uppercase', cursor: 'pointer' }}>
                    {tab === 'positions' ? `POS (${positions.length})` : tab === 'orders' ? `ORD (${pendingOrders.length})` : tab === 'history' ? 'HIST' : 'JOURNAL'}
                  </button>
                ))}
              </div>
              <div style={{ flex: 1, overflow: 'auto' }}>
                {activeTab === 'journal' ? (
                  <TradeJournal />
                ) : activeTab === 'positions' && positions.length === 0 ? (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: C.muted, fontSize: 9, fontFamily: C.mono }}>NO POSITIONS</div>
                ) : activeTab === 'orders' && pendingOrders.length === 0 ? (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: C.muted, fontSize: 9, fontFamily: C.mono }}>NO PENDING ORDERS</div>
                ) : (
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 8, fontFamily: C.mono }}>
                    <thead><tr style={{ background: 'rgba(0,0,0,0.3)' }}>
                      {['SYMBOL', 'DIR', 'VOL', 'ENTRY', 'S/L', 'T/P', 'P&L', ''].map(h => (
                        <th key={h} style={{ padding: '4px 6px', textAlign: h === 'SYMBOL' || h === 'DIR' || h === '' ? 'left' : 'right', color: C.muted, borderBottom: `1px solid ${C.border}` }}>{h}</th>
                      ))}
                    </tr></thead>
                    <tbody>
                      {(activeTab === 'positions' ? positions : activeTab === 'orders' ? pendingOrders.map(o => ({ ...o, profit: 0, ticket: o.ticket })) : history.map(h => ({ ...h, ticket: 0, profit: h.pl, type: h.type, lot: h.lot }))).slice(0, activeTab === 'history' ? 10 : 20).map((item: any, idx) => {
                        const isUp = (item.profit || 0) >= 0;
                        const isBuy = item.type === 'BUY';
                        return (
                          <tr key={idx} style={{ borderBottom: `1px solid ${C.border}` }}>
                            <td style={{ padding: '4px 6px', fontWeight: 700 }}>{item.symbol || 'XAUUSD'}</td>
                            <td style={{ padding: '4px 6px', color: isBuy ? C.green : C.red, fontWeight: 700 }}>{isBuy ? '▲' : '▼'}</td>
                            <td style={{ padding: '4px 6px', textAlign: 'right', color: C.dim }}>{item.lot?.toFixed(2) || item.volume?.toFixed(2) || '-'}</td>
                            <td style={{ padding: '4px 6px', textAlign: 'right', color: C.dim }}>{item.entry?.toFixed(2) || item.price?.toFixed(2) || '-'}</td>
                            <td style={{ padding: '4px 6px', textAlign: 'right', color: C.red }}>{item.sl?.toFixed(2) || '-'}</td>
                            <td style={{ padding: '4px 6px', textAlign: 'right', color: C.green }}>{item.tp?.toFixed(2) || '-'}</td>
                            <td style={{ padding: '4px 6px', textAlign: 'right', fontWeight: 700, color: isUp ? C.green : C.red }}>{isUp ? '+' : ''}{(item.profit || 0).toFixed(2)}</td>
                            <td style={{ padding: '4px 6px', textAlign: 'right' }}>
                              {item.ticket ? (
                                <button onClick={() => activeTab === 'positions' ? handleClosePosition(item.ticket) : handleCancelOrder(item.ticket)} style={{ padding: '2px 6px', background: activeTab === 'positions' ? C.redDim : C.amberDim, border: `1px solid ${activeTab === 'positions' ? C.red : C.amber}`, borderRadius: 3, color: activeTab === 'positions' ? C.red : C.amber, fontSize: 7, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer' }}>
                                  {activeTab === 'positions' ? 'CLOSE' : 'CANCEL'}
                                </button>
                              ) : null}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            </Panel>
          </div>
        </div>

        {/* RIGHT COLUMN */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minHeight: 0, overflow: 'hidden' }}>
          {/* Watchlist */}
          <div style={{ flex: 0.5, minHeight: 0 }}>
            <Panel title="Watchlist" live style={{ height: '100%' }}>
              <Watchlist onSymbolSelect={setSelectedSymbol} selectedSymbol={selectedSymbol} />
            </Panel>
          </div>

          {/* AI Brain + Performance */}
          <div style={{ flex: 1, minHeight: 0 }}>
            <Panel title="AI Brain" live style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
              <div style={{ flex: 1, overflow: 'auto', padding: 8 }}>
                {/* Sentiment */}
                <SentimentGauge bullishPercent={aiConfidence || 65} label="MARKET SENTIMENT" />

                {/* AI Metrics */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6, margin: '12px 0' }}>
                  <div style={{ padding: '8px', background: 'rgba(0,0,0,0.3)', borderRadius: 6, border: `1px solid ${C.border}`, textAlign: 'center' }}>
                    <div style={{ fontSize: 7, color: C.muted, marginBottom: 2 }}>BIAS</div>
                    <div style={{ fontSize: 10, fontWeight: 800, color: aiBias === 'BULLISH' ? C.green : aiBias === 'BEARISH' ? C.red : C.amber }}>{aiBias}</div>
                  </div>
                  <div style={{ padding: '8px', background: 'rgba(0,0,0,0.3)', borderRadius: 6, border: `1px solid ${C.border}`, textAlign: 'center' }}>
                    <div style={{ fontSize: 7, color: C.muted, marginBottom: 2 }}>SIGNAL</div>
                    <div style={{ fontSize: 10, fontWeight: 800, color: aiSignal?.action === 'BUY' ? C.green : aiSignal?.action === 'SELL' ? C.red : C.muted }}>{aiSignal?.action || 'NONE'}</div>
                  </div>
                  <div style={{ padding: '8px', background: 'rgba(0,0,0,0.3)', borderRadius: 6, border: `1px solid ${C.border}`, textAlign: 'center' }}>
                    <div style={{ fontSize: 7, color: C.muted, marginBottom: 2 }}>CONFIDENCE</div>
                    <div style={{ fontSize: 10, fontWeight: 800, color: C.cyan }}>{aiConfidence}%</div>
                  </div>
                </div>

                {/* Active Signal */}
                {aiSignal && (
                  <div style={{ background: 'linear-gradient(135deg, rgba(34,211,160,0.1) 0%, rgba(0,0,0,0.3) 100%)', border: `1px solid ${C.green}`, borderRadius: 8, padding: 10, marginBottom: 8 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ fontSize: 8, color: C.muted }}>ACTIVE SIGNAL</span>
                      <span style={{ fontSize: 10, fontWeight: 800, color: aiSignal.action === 'BUY' ? C.green : C.red }}>{aiSignal.action} @ {aiSignal.entry?.toFixed(2) || 'Pending'}</span>
                    </div>
                    <div style={{ display: 'flex', gap: 12, fontSize: 8, fontFamily: C.mono }}>
                      <span>SL: <span style={{ color: C.red }}>{aiSignal.stop_loss?.toFixed(2) || '-'}</span></span>
                      <span>TP: <span style={{ color: C.green }}>{aiSignal.take_profit?.toFixed(2) || '-'}</span></span>
                    </div>
                  </div>
                )}

                {/* Performance Charts */}
                <PerformanceCharts />
              </div>
            </Panel>
          </div>

          {/* AI Copilot */}
          {!showCompact && (
            <div style={{ height: 200 }}>
              <Panel title="AI Copilot" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                <div ref={chatRef} style={{ flex: 1, overflow: 'auto', padding: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {chatHistory.length === 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: C.muted, fontSize: 8, fontFamily: C.mono, textAlign: 'center' }}>
                      AI Copilot san sang ho tro
                    </div>
                  )}
                  {chatHistory.map((msg, idx) => (
                    <div key={idx} style={{ padding: '6px 8px', borderRadius: 6, background: msg.role === 'user' ? C.goldDim : 'rgba(0,0,0,0.4)', border: msg.role === 'user' ? `1px solid ${C.gold}` : `1px solid ${C.border}`, maxWidth: '85%', alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
                      <div style={{ fontSize: 7, fontFamily: C.mono, fontWeight: 700, color: msg.role === 'user' ? C.gold : C.cyan, marginBottom: 2 }}>{msg.role === 'user' ? 'YOU' : 'AI'}</div>
                      <div style={{ fontSize: 9, color: C.dim }}>{msg.content}</div>
                    </div>
                  ))}
                  {copilotTyping && (
                    <div style={{ padding: '6px 8px', borderRadius: 6, background: 'rgba(0,0,0,0.4)', border: `1px solid ${C.border}`, maxWidth: '85%' }}>
                      <div style={{ display: 'flex', gap: 4 }}>{[0, 1, 2].map(i => <div key={i} style={{ width: 4, height: 4, borderRadius: '50%', background: C.cyan, animation: `pulse 1s ease-in-out ${i * 0.2}s infinite` }} />)}</div>
                    </div>
                  )}
                </div>
                <div style={{ padding: 8, borderTop: `1px solid ${C.border}`, display: 'flex', gap: 6 }}>
                  <input type="text" value={copilotInput} onChange={e => setCopilotInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleCopilot()} placeholder="Ask AI..." style={{ flex: 1, padding: '6px 10px', background: 'rgba(0,0,0,0.5)', border: `1px solid ${C.border}`, borderRadius: 6, color: C.text, fontSize: 9, fontFamily: C.mono, outline: 'none' }} />
                  <button onClick={handleCopilot} disabled={copilotTyping} style={{ padding: '6px 12px', background: C.goldDim, border: `1px solid ${C.gold}`, borderRadius: 6, color: C.gold, fontSize: 9, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer' }}>GO</button>
                </div>
              </Panel>
            </div>
          )}
        </div>

        {/* ECONOMIC CALENDAR (bottom center) */}
        {!showCompact && (
          <div style={{ minHeight: 0 }}>
            <Panel title="Economic Calendar" live style={{ height: '100%' }}>
              <EconomicCalendar />
            </Panel>
          </div>
        )}
      </div>

      {/* QUICK TRADE FLOATING BUTTON */}
      <button onClick={() => setShowQuickTrade(true)} style={{
        position: 'fixed', bottom: 20, right: showCompact ? 20 : 340,
        width: 56, height: 56, borderRadius: '50%',
        background: `linear-gradient(135deg, ${C.gold} 0%, rgba(153,101,21,0.8) 100%)`,
        border: '2px solid rgba(255,255,255,0.2)',
        boxShadow: `0 8px 24px rgba(0,0,0,0.5), 0 0 20px ${C.gold}40`,
        cursor: 'pointer', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center',
        transition: 'all 0.2s ease',
      }}>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#000" strokeWidth="2.5"><path d="M12 5v14M5 12h14" /></svg>
      </button>

      {/* QUICK TRADE PANEL */}
      <QuickTradePanel isOpen={showQuickTrade} onClose={() => setShowQuickTrade(false)} onExecute={handleQuickTrade} currentPrice={2850} />

      {/* PATTERN ALERTS */}
      <PatternAlert onViewChart={(p) => { setSelectedSymbol(p.symbol); setShowChart(true); }} />
    </div>
  );
}
