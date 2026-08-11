'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  fetchStatus, fetchControlCenterStatus, fetchPositions, fetchMarket,
  fetchHistory, fetchPendingOrders, fetchLogs, fetchBrain,
  sendCopilotChat,
  updateAiAutoLoop, fetchSettings,
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
import SettingsModal from './components/SettingsModal';

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
  style?: React.CSSProperties;
  className?: string;
}) {
  return (
    <div className={className} style={{
      background: C.panelBg, backdropFilter: 'blur(20px)',
      borderRadius: 10, overflow: 'hidden', display: 'flex', flexDirection: 'column',
      position: 'relative', ...style,
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
  const [showSettings, setShowSettings] = useState(false);
  const [copilotTab, setCopilotTab] = useState<'chat' | 'log'>('log');
  const [copilotEvents, setCopilotEvents] = useState<Array<{ id: string; ts: string; level: string; action: string; symbol: string; details: any }>>([]);
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
  const loadAll = useCallback(async () => {
    if (!isAuthenticated) return;
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
      setStatus(s); setPositions(ps || []);
      if (m) setMarket(m);
      setHistory(h || []);
      setPendingOrders(po || []); setLogs(l || []); setBrain(b); setCcStatus(cc);
    } catch { /* silent */ }
  }, [isAuthenticated, selectedSymbol, chartTf]);

  useEffect(() => {
    if (!isAuthenticated) return;
    loadAll();
    const interval = setInterval(loadAll, 2000);
    return () => clearInterval(interval);
  }, [isAuthenticated, loadAll]);

  // Re-fetch market IMMEDIATELY when trading method changes
  useEffect(() => {
    if (!isAuthenticated) return;
    const tm = ccStatus?.safeguards?.trading_method;
    if (!tm) return;
    let cancelled = false;
    fetchMarket(selectedSymbol, chartTf).then(m => { if (!cancelled && m) setMarket(m); }).catch(() => {});
    return () => { cancelled = true; };
  }, [isAuthenticated, ccStatus?.safeguards?.trading_method, selectedSymbol, chartTf]);

  // FIX LỖI 7: Keyboard shortcuts with Shift modifier
  useEffect(() => {
    const handleKey = async (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      // Shift + Key combos - all require Shift
      if (e.shiftKey) {
        switch (e.key.toUpperCase()) {
          case 'C':
            e.preventDefault();
            handleClosePosition(positions[0]?.ticket);
            break;
          case 'A':
            e.preventDefault();
            try {
              const next = !(ccStatus?.safeguards?.ai_auto_loop ?? false);
              await updateAiAutoLoop(next);
              const cc = await fetchControlCenterStatus();
              if (cc) setCcStatus(cc);
              addNotif(`AI Auto Loop ${next ? 'ENABLED' : 'DISABLED'}`, next ? 'success' : 'info');
            } catch { addNotif('AI Loop toggle failed', 'error'); }
            break;
          case 'K':
            e.preventDefault();
            addNotif('Kill Switch: Use Control Center button', 'warning');
            break;
          case 'E':
            e.preventDefault();
            setShowChart(v => !v);
            break;
          case 'M':
            e.preventDefault();
            setShowCompact(v => !v);
            break;
          case 'Q':
            e.preventDefault();
            setShowQuickTrade(v => !v);
            break;
          case '/':
            e.preventDefault();
            setShowShortcuts(v => !v);
            break;
          case '1': setChartTf('M1'); break;
          case '2': setChartTf('M5'); break;
          case '3': setChartTf('M15'); break;
          case '4': setChartTf('H1'); break;
          case '5': setChartTf('H4'); break;
        }
        return;
      }

      // Normal keys without shift
      switch (e.key.toLowerCase()) {
        case 'escape':
          setShowShortcuts(false);
          setShowQuickTrade(false);
          setShowSettings(false);
          break;
        case '?':
          setShowShortcuts(v => !v);
          break;
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [positions, ccStatus, addNotif]);

  // Auto-scroll
  useEffect(() => { if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight; }, [chatHistory]);
  useEffect(() => { if (logsRef.current) logsRef.current.scrollTop = logsRef.current.scrollHeight; }, [logs]);

  // FIX LỖI 8: SSE stream for AI Copilot
  useEffect(() => {
    if (!isAuthenticated) return;
    let es: EventSource | null = null;
    let retryTimeout: ReturnType<typeof setTimeout>;

    const connect = () => {
      try {
        es = new EventSource('/api/copilot/stream');

        es.onmessage = (ev) => {
          try {
            const raw = ev.data;
            if (!raw || raw === ': keepalive') return;
            const data = JSON.parse(raw);
            if (!data || !data.id) return;
            setCopilotEvents(prev => {
              const next = [...prev, data];
              return next.length > 200 ? next.slice(-200) : next;
            });
          } catch { /* keepalive */ }
        };

        es.onerror = () => {
          es?.close();
          retryTimeout = setTimeout(connect, 3000);
        };
      } catch { /* SSR or unavailable */ }
    };

    connect();
    return () => {
      clearTimeout(retryTimeout);
      try { es?.close(); } catch {}
    };
  }, [isAuthenticated]);

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
    } catch {
      setChatHistory(prev => [...prev, { role: 'ai', content: 'Loi. Thu lai.', timestamp: new Date().toISOString() }]);
    }
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

  // FIX LỖI 3: AI Brain - Real sentiment from confluence score
  const aiSignal = brain?.recent_decisions?.[0];
  const aiBias = aiSignal?.action === 'BUY' ? 'BULLISH' : aiSignal?.action === 'SELL' ? 'BEARISH' : 'NEUTRAL';

  // Real sentiment computed from confluence score (priority: markup.confluence > brain.confidence > strategy.win_rate)
  const realSentiment = (() => {
    const confluenceScore = market?.markup?.confluence?.score;
    if (typeof confluenceScore === 'number' && confluenceScore > 0) {
      return Math.round(Math.min(100, Math.max(0, confluenceScore * 100)));
    }
    const brainConf = aiSignal?.confidence ?? 0;
    if (brainConf > 0) {
      const conf = brainConf > 1 ? brainConf : brainConf * 100;
      return Math.round(Math.min(100, Math.max(0, conf)));
    }
    const wr = brain?.strategies?.[0]?.win_rate;
    if (typeof wr === 'number') return Math.round(wr);
    return 50;
  })();

  // Actions
  const handleClosePosition = async (ticket?: number) => {
    if (!ticket) return;
    try {
      await fetch('/api/order/close', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ticket }) });
      setPositions(prev => prev.filter(p => p.ticket !== ticket));
      addNotif('Position closed', 'success');
    }
    catch { addNotif('Failed to close', 'error'); }
  };
  const handleCancelOrder = async (ticket?: number) => {
    if (!ticket) return;
    try {
      await fetch('/api/order/cancel_pending', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ order_ticket: ticket }) });
      setPendingOrders(prev => prev.filter(o => o.ticket !== ticket));
      addNotif('Order cancelled', 'success');
    }
    catch { addNotif('Failed to cancel', 'error'); }
  };
  const handleQuickTrade = (order: any) => { addNotif(`Order ${order.type} sent`, 'success'); };

  // FIX LỖI 4: Symbol change handler
  const handleSymbolChange = useCallback((sym: string) => {
    setSelectedSymbol(sym);
    setMarket(null); // Clear to force re-fetch
  }, []);

  // AI Auto state
  const aiAutoEnabled = ccStatus?.safeguards?.ai_auto_loop ?? false;

  if (!isAuthenticated) return null;

  const notifColors = { info: C.blue, success: C.green, warning: C.amber, error: C.red };

  // Grid template - FIX LỖI 8: Proper layout for COMPACT vs EXPAND
  const gridCols = showCompact ? '240px 1fr 280px' : '280px 1fr 280px';

  return (
    <div style={{ height: '100vh', width: '100vw', background: C.bgMain, display: 'flex', flexDirection: 'column', overflow: 'hidden', fontFamily: C.sans }}>
      {/* KEYBOARD SHORTCUTS MODAL */}
      {showShortcuts && (
        <div onClick={() => setShowShortcuts(false)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div onClick={e => e.stopPropagation()} style={{ background: C.panelBg, border: `1px solid ${C.gold}`, borderRadius: 12, padding: 24, minWidth: 320 }}>
            <div style={{ fontSize: 12, fontFamily: C.mono, fontWeight: 800, color: C.gold, marginBottom: 16, textAlign: 'center' }}>KEYBOARD SHORTCUTS</div>
            {[
              ['Shift + C', 'Close position'],
              ['Shift + A', 'Toggle AI Auto Loop'],
              ['Shift + K', 'Kill Switch info'],
              ['Shift + E', 'Toggle Chart'],
              ['Shift + M', 'Toggle Compact Mode'],
              ['Shift + Q', 'Quick Trade Panel'],
              ['Shift + 1-5', 'Switch Timeframe (M1/M5/M15/H1/H4)'],
              ['Shift + /', 'Show shortcuts'],
              ['Esc', 'Close modal'],
            ].map(([key, desc]) => (
              <div key={key} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: `1px solid ${C.border}` }}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span style={{ fontSize: 10, fontFamily: C.mono, fontWeight: 700, color: C.gold, background: C.goldDim, padding: '2px 8px', borderRadius: 4 }}>{key}</span>
                  <span style={{ fontSize: 10, fontFamily: C.mono, color: C.dim }}>{desc}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* NOTIFICATIONS */}
      <div style={{ position: 'fixed', top: 60, right: 16, zIndex: 999, display: 'flex', flexDirection: 'column', gap: 6 }}>
        {notifications.map(n => (
          <div key={n.id} style={{
            padding: '8px 16px', background: C.panelBg, border: `1px solid ${notifColors[n.type]}`,
            borderRadius: 8, color: notifColors[n.type], fontSize: 9, fontFamily: C.mono, fontWeight: 700,
            boxShadow: `0 4px 16px rgba(0,0,0,0.5)`,
          }}>
            {n.message}
          </div>
        ))}
      </div>

      {/* TOP BAR */}
      <div style={{ height: 52, background: 'linear-gradient(180deg, rgba(10,14,24,0.98) 0%, rgba(5,7,12,0.95) 100%)', borderBottom: `1px solid ${C.border}`, display: 'flex', alignItems: 'center', padding: '0 16px', gap: 12, flexShrink: 0 }}>
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

        {/* FIX LỖI 6: AI Auto dot indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{
            width: 10, height: 10, borderRadius: '50%',
            background: aiAutoEnabled ? C.green : C.muted,
            boxShadow: aiAutoEnabled ? `0 0 12px ${C.green}` : 'none',
            animation: aiAutoEnabled ? 'pulse 2s infinite' : 'none',
            cursor: 'pointer',
          }} />
          <span style={{ fontSize: 8, fontFamily: C.mono, color: aiAutoEnabled ? C.green : C.muted, fontWeight: 700 }}>
            AI {aiAutoEnabled ? 'ON' : 'OFF'}
          </span>
        </div>

        <button onClick={() => setShowChart(v => !v)} style={{ padding: '6px 10px', background: showChart ? C.goldDim : 'transparent', border: `1px solid ${showChart ? C.gold : C.border}`, borderRadius: 6, color: showChart ? C.gold : C.muted, fontSize: 9, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer' }}>CHART</button>
        <button onClick={() => setShowCompact(v => !v)} style={{ padding: '6px 10px', background: showCompact ? C.goldDim : 'transparent', border: `1px solid ${showCompact ? C.gold : C.border}`, borderRadius: 6, color: showCompact ? C.gold : C.muted, fontSize: 9, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer' }}>{showCompact ? 'EXPAND' : 'COMPACT'}</button>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <StatusBadge status={ccStatus?.account?.mt5_connected ? 'online' : 'offline'} label="MT5" />
          <StatusBadge status={positions.length > 0 ? 'online' : 'offline'} label={`POS ${positions.length}`} />
        </div>

        <button onClick={() => setShowShortcuts(v => !v)} style={{ padding: '6px 8px', background: 'transparent', border: `1px solid ${C.border}`, borderRadius: 6, color: C.muted, fontSize: 10, cursor: 'pointer' }}>?</button>

        <div style={{ padding: '4px 12px', background: 'rgba(0,0,0,0.4)', borderRadius: 6, border: `1px solid ${C.border}`, textAlign: 'center' }}>
          <div style={{ fontSize: 14, fontFamily: C.mono, fontWeight: 700, color: C.text }}>{new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}</div>
          <div style={{ fontSize: 7, fontFamily: C.mono, color: C.muted }}>VN {new Date().toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' })}</div>
        </div>
      </div>

      {/* MAIN CONTENT - FIX LỖI 8: Proper 3-column grid */}
      <div style={{
        flex: 1, display: 'grid',
        gridTemplateColumns: gridCols,
        gap: 8, padding: 8, minHeight: 0, overflow: 'hidden',
        background: `radial-gradient(ellipse at 0% 0%, rgba(212,175,55,0.04) 0%, transparent 50%), radial-gradient(ellipse at 100% 100%, rgba(34,211,160,0.03) 0%, transparent 50%), ${C.bgMain}`,
      }}>
        {/* LEFT COLUMN */}
        <div style={{ minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <Panel live style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '10px 14px', borderBottom: `1px solid ${C.border}`,
              background: 'linear-gradient(180deg, rgba(255,255,255,0.02) 0%, transparent 100%)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: C.green, boxShadow: `0 0 8px ${C.green}`, animation: 'pulse 2s infinite' }} />
                <span style={{ fontSize: 9, fontFamily: C.mono, fontWeight: 700, color: C.gold, letterSpacing: '0.1em', textTransform: 'uppercase' }}>Control Center</span>
              </div>
              {/* FIX LỖI 9: Gear icon opens Settings Modal */}
              <button
                onClick={() => setShowSettings(true)}
                title="Settings"
                style={{
                  background: 'transparent', border: `1px solid ${C.border}`, color: C.muted,
                  width: 24, height: 24, borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  cursor: 'pointer', transition: 'all 0.15s ease',
                }}
                onMouseEnter={e => { (e.currentTarget as any).style.color = C.gold; (e.currentTarget as any).style.borderColor = C.gold; }}
                onMouseLeave={e => { (e.currentTarget as any).style.color = C.muted; (e.currentTarget as any).style.borderColor = C.border; }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="3" />
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
                </svg>
              </button>
            </div>
            <div style={{ flex: 1, overflow: 'auto' }}>
              <ControlCenter />
            </div>
          </Panel>

          {/* Equity Curve - only in EXPAND */}
          {!showCompact && (
            <div style={{ height: 160, flexShrink: 0 }}>
              <EquityCurve currentEquity={equity} initialBalance={balance} />
            </div>
          )}
        </div>

        {/* CENTER COLUMN */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minHeight: 0, overflow: 'hidden' }}>
          {showChart && (
            <div style={{ flex: showCompact ? 1 : '0 1 auto', minHeight: 0 }}>
              <Panel title={`${selectedSymbol} ${chartTf}`} live style={{ height: '100%', position: 'relative' }}>
                <div style={{ position: 'absolute', top: 8, right: 80, zIndex: 10, display: 'flex', gap: 4 }}>
                  {['M1', 'M5', 'M15', 'H1', 'H4', 'D1'].map(tf => (
                    <button key={tf} onClick={() => setChartTf(tf)} style={{ padding: '4px 8px', background: chartTf === tf ? C.goldDim : 'rgba(0,0,0,0.5)', border: `1px solid ${chartTf === tf ? C.gold : C.border}`, borderRadius: 4, color: chartTf === tf ? C.gold : C.muted, fontSize: 8, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer' }}>{tf}</button>
                  ))}
                </div>
                <TradingChart symbol={selectedSymbol} timeframe={chartTf} candles={market?.candles} markup={market?.markup} positions={positions as any} />
              </Panel>
            </div>
          )}

          {/* Positions - FIX LỖI 8: Always visible in EXPAND */}
          {!showCompact && (
            <div style={{ flex: '0 0 180px', overflow: 'hidden' }}>
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
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 80, color: C.muted, fontSize: 9, fontFamily: C.mono }}>NO POSITIONS</div>
                  ) : activeTab === 'orders' && pendingOrders.length === 0 ? (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 80, color: C.muted, fontSize: 9, fontFamily: C.mono }}>NO PENDING ORDERS</div>
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
          )}
        </div>

        {/* RIGHT COLUMN */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minHeight: 0, overflow: 'hidden' }}>
          {/* Watchlist - FIX LỖI 4: Click to change chart symbol */}
          <div style={{ flexShrink: 0, maxHeight: showCompact ? 200 : 220 }}>
            <Panel title="Watchlist" live style={{ height: '100%' }}>
              <Watchlist onSymbolSelect={handleSymbolChange} selectedSymbol={selectedSymbol} />
            </Panel>
          </div>

          {/* AI Brain */}
          <div style={{ flex: showCompact ? 1 : 1, minHeight: 0, overflow: 'hidden' }}>
            <Panel title="AI Brain" live style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
              <div style={{ flex: 1, overflow: 'auto', padding: 8 }}>
                {/* FIX LỖI 3: Sentiment from real confluence data */}
                <SentimentGauge bullishPercent={realSentiment} label="MARKET SENTIMENT" />

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
                    <div style={{ fontSize: 10, fontWeight: 800, color: C.cyan }}>{realSentiment}%</div>
                  </div>
                </div>

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

                <PerformanceCharts liveStats={history ? (() => { const wins = history.filter(h => (h.pl || 0) > 0).length; const losses = history.filter(h => (h.pl || 0) < 0).length; const total_pl = history.reduce((s, h) => s + (h.pl || 0), 0); const best = Math.max(0, ...history.map(h => h.pl || 0)); const worst = Math.min(0, ...history.map(h => h.pl || 0)); return { wins, losses, total_pl, best_trade: best, max_drawdown: worst }; })() : null} />
              </div>
            </Panel>
          </div>

          {/* Pattern Alerts - FIX LỖI 8: Always visible in EXPAND */}
          {!showCompact && (
            <div style={{ flexShrink: 0, maxHeight: 160 }}>
              <Panel title="Alerts" live style={{ height: '100%' }}>
                <PatternAlert onViewChart={(p) => { setSelectedSymbol(p.symbol); setShowChart(true); }} />
              </Panel>
            </div>
          )}

          {/* AI Copilot - FIX LỖI 8: Always visible in EXPAND */}
          {!showCompact && (
            <div style={{ flexShrink: 0, height: 260, display: 'flex', flexDirection: 'column' }}>
              <Panel style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', borderBottom: `1px solid ${C.border}` }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ width: 6, height: 6, borderRadius: '50%', background: C.cyan, boxShadow: `0 0 8px ${C.cyan}`, animation: 'pulse 2s infinite' }} />
                    <span style={{ fontSize: 9, fontFamily: C.mono, fontWeight: 700, color: C.gold, letterSpacing: '0.1em' }}>AI COPILOT</span>
                  </div>
                  <div style={{ display: 'flex', gap: 2 }}>
                    <button onClick={() => setCopilotTab('chat')} style={{ padding: '3px 8px', background: copilotTab === 'chat' ? C.cyan + '20' : 'transparent', border: `1px solid ${copilotTab === 'chat' ? C.cyan : C.border}`, borderRadius: 3, color: copilotTab === 'chat' ? C.cyan : C.muted, fontSize: 8, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer' }}>CHAT</button>
                    <button onClick={() => setCopilotTab('log')} style={{ padding: '3px 8px', background: copilotTab === 'log' ? C.goldDim : 'transparent', border: `1px solid ${copilotTab === 'log' ? C.gold : C.border}`, borderRadius: 3, color: copilotTab === 'log' ? C.gold : C.muted, fontSize: 8, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer' }}>
                      LOG {copilotEvents.length > 0 && <span style={{ color: C.green }}>·{copilotEvents.length}</span>}
                    </button>
                  </div>
                </div>
                {copilotTab === 'chat' ? (
                  <>
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
                  </>
                ) : (
                  <div ref={logsRef} style={{ flex: 1, overflow: 'auto', padding: 6, display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {copilotEvents.length === 0 ? (
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: C.muted, fontSize: 8, fontFamily: C.mono }}>AI events will appear here in real-time</div>
                    ) : (
                      copilotEvents.slice().reverse().map(ev => {
                        const isTrade = ev.level === 'TRADE';
                        const isBuy = ev.action === 'BUY';
                        const isClose = ev.action === 'CLOSE';
                        const isBE = ev.action === 'BREAK_EVEN';
                        const accent = isTrade && isClose ? C.amber
                          : isTrade && isBE ? C.green
                          : isTrade && isBuy ? C.green
                          : isTrade && ev.action === 'SELL' ? C.red
                          : ev.level === 'INFO' ? C.cyan : C.muted;
                        const sym = ev.symbol || selectedSymbol;
                        const ts = new Date(ev.ts).toLocaleTimeString('en-US', { hour12: false });
                        return (
                          <div key={ev.id} style={{ padding: '5px 8px', background: 'rgba(0,0,0,0.4)', border: `1px solid ${C.border}`, borderLeft: `2px solid ${accent}`, borderRadius: 4, fontFamily: C.mono }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 8 }}>
                              <span style={{ color: accent, fontWeight: 700 }}>{ev.action}</span>
                              <span style={{ color: C.muted }}>{ts} · {sym}</span>
                            </div>
                            {ev.details && (
                              <div style={{ fontSize: 8, color: C.dim, marginTop: 2 }}>
                                {ev.details.entry !== undefined && <>entry: {Number(ev.details.entry).toFixed(2)} </>}
                                {ev.details.sl !== undefined && <span style={{ color: C.red }}>sl: {Number(ev.details.sl).toFixed(2)} </span>}
                                {ev.details.tp !== undefined && <span style={{ color: C.green }}>tp: {Number(ev.details.tp).toFixed(2)} </span>}
                                {ev.details.pnl !== undefined && <span style={{ color: ev.details.pnl >= 0 ? C.green : C.red }}>pnl: {Number(ev.details.pnl).toFixed(2)} </span>}
                                {ev.details.score !== undefined && <span style={{ color: C.gold }}>score: {ev.details.score} </span>}
                                {ev.details.reason && <span>· {ev.details.reason}</span>}
                              </div>
                            )}
                          </div>
                        );
                      })
                    )}
                  </div>
                )}
              </Panel>
            </div>
          )}
        </div>
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

      <QuickTradePanel isOpen={showQuickTrade} onClose={() => setShowQuickTrade(false)} onExecute={handleQuickTrade} currentPrice={market?.candles?.[market.candles.length - 1]?.c || 2845} />

      {/* SETTINGS MODAL - FIX LỖI 9: Full settings with gear icon */}
      <SettingsModal open={showSettings} onClose={() => setShowSettings(false)} onUpdated={loadAll} />

      {/* Risk Calculator in COMPACT */}
      {showCompact && (
        <div style={{ position: 'fixed', bottom: 90, right: showCompact ? 20 : 340, zIndex: 50 }}>
          <RiskCalculator accountBalance={balance} onQuickTrade={handleQuickTrade} />
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
        @keyframes slideIn {
          from { transform: translateX(20px); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
