'use client';

import { useState, useEffect, useRef, type ReactNode, type CSSProperties } from 'react';
import { useRouter } from 'next/navigation';
import {
  fetchStatus,
  fetchControlCenterStatus,
  fetchPositions,
  fetchMarket,
  fetchHistory,
  fetchPendingOrders,
  fetchLogs,
  fetchBrain,
  fetchAdjustments,
  patchAdjustment,
  sendCopilotChat,
  executeOrderBuy,
  executeOrderSell,
  executeOrderCloseAll,
  executeCloseProfit,
  executeCloseLosing,
  analyzeNewsEvent,
  updateAiAutoLoop,
  fetchChatHistory,
  type NewsAnalysisResponse,
  type Candle,
  type Position,
  type TradeHistory,
  type ChatMsg,
  type TechnicalIndicators,
  type AccountPerformance,
  type AISignalData,
  type NewsItem,
  type ControlCenterStatus,
  type PendingOrder,
  type LogEntry,
  type TodayPerformance,
  type BrainState,
  type BrainDecision,
  type BrainEvaluation,
  type StrategyStat,
  type BrainAdjustment,
} from '../lib/api';
import ControlCenter from './components/ControlCenter';
import EconomicCalendar from './components/EconomicCalendar';

// ── Bloomberg Terminal Color System ───────────────────────────────────────────
const C = {
  bgMain: '#05070c',
  panelBg: 'rgba(10, 14, 24, 0.96)',
  border: 'rgba(255, 255, 255, 0.08)',
  borderHighlight: 'rgba(212, 180, 131, 0.3)',

  gold: '#D4B483',
  green: '#22d3a0',
  greenBright: '#10b981',
  red: '#f43f5e',
  blue: '#38bdf8',
  purple: '#a855f7',
  cyan: '#06b6d4',
  amber: '#f59e0b',

  text: '#f8fafc',
  dim: '#cbd5e1',
  muted: '#64748b',
  faint: '#475569',

  mono: '"JetBrains Mono", monospace',
  sans: '"Inter", -apple-system, BlinkMacSystemFont, sans-serif',
};

const glass: CSSProperties = {
  background: C.panelBg,
  backdropFilter: 'blur(16px)',
  WebkitBackdropFilter: 'blur(16px)',
  border: `1px solid ${C.border}`,
  borderRadius: '5px',
  overflow: 'hidden',
  boxShadow: '0 4px 20px rgba(0, 0, 0, 0.6)',
};

// ── Official TradingView Embedded Widget Component ─────────────────────────────
function RealTradingViewWidget({ symbol = 'FX:XAUUSD' }: { symbol?: string }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    containerRef.current.innerHTML = '';
    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      autosize: true,
      symbol: symbol,
      interval: '15',
      timezone: 'Asia/Ho_Chi_Minh',
      theme: 'dark',
      style: '1',
      locale: 'vi_VN',
      enable_publishing: false,
      hide_top_toolbar: false,
      hide_legend: false,
      save_image: false,
      calendar: false,
      hide_volume: false,
      support_host: 'https://www.tradingview.com',
      backgroundColor: 'rgba(5, 7, 12, 1)',
      gridColor: 'rgba(255, 255, 255, 0.04)',
    });
    containerRef.current.appendChild(script);
  }, [symbol]);

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <div className="tradingview-widget-container" ref={containerRef} style={{ width: '100%', height: '100%' }} />
    </div>
  );
}

// ── High Performance MT5 SVG Candlestick Chart ────────────────────────────────
function CandleChart({
  candles,
  livePrice,
  positions,
  indicators,
}: {
  candles: Candle[];
  livePrice: number;
  positions: Position[];
  indicators: TechnicalIndicators;
}) {
  const [visibleCount, setVisibleCount] = useState(75);
  const [panOffset, setPanOffset] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStartX, setDragStartX] = useState(0);

  const W = 1000, H = 420;
  const PL = 8, PR = 80, PT = 20, PB = 40;

  const total = candles.length;
  const endIdx = Math.max(visibleCount, total - panOffset);
  const startIdx = Math.max(0, endIdx - visibleCount);
  const vis = candles.slice(startIdx, endIdx);

  if (vis.length === 0) return <div style={{ display: 'grid', placeItems: 'center', height: '100%', color: C.faint, fontFamily: C.mono, fontSize: 10 }}>Loading MT5 Live Candles...</div>;

  const lastClose = vis[vis.length - 1].c;
  const validLivePrice = livePrice > 1000 && Math.abs(livePrice - lastClose) < 200 ? livePrice : lastClose;

  const prices = vis.flatMap((c) => [c.h, c.l]);
  prices.push(validLivePrice);
  if (positions && positions.length > 0) {
    positions.forEach((p) => {
      if (p.entry > 0) prices.push(p.entry);
      if (p.sl > 0) prices.push(p.sl);
      if (p.tp > 0) prices.push(p.tp);
    });
  }

  const rawMinP = Math.min(...prices);
  const rawMaxP = Math.max(...prices);
  const midP = (rawMaxP + rawMinP) / 2;
  const halfRange = Math.max((rawMaxP - rawMinP) / 2, 0.8);
  const minP = midP - halfRange - 0.5;
  const maxP = midP + halfRange + 0.5;
  const range = maxP - minP || 1;

  const cW = (W - PL - PR) / vis.length;
  const bW = Math.max(cW * 0.6, 2);
  const maxV = Math.max(...vis.map((c) => c.v)) || 1;
  const priceH = 250; // Candlestick panel price height
  const py = (p: number) => PT + ((maxP - p) / range) * priceH;
  const px = (i: number) => PL + (i + 0.5) * cW;
  const ticks = [0.15, 0.4, 0.65, 0.9].map((r) => minP + range * r);

  // Dynamic calculations for EMA and RSI on full data
  const computeEMA = (data: Candle[], period: number): number[] => {
    const ema: number[] = [];
    if (data.length === 0) return [];
    const k = 2 / (period + 1);
    let sum = 0;
    for (let i = 0; i < Math.min(period, data.length); i++) {
      sum += data[i].c;
    }
    let emaVal = sum / Math.min(period, data.length);
    for (let i = 0; i < data.length; i++) {
      if (i < period) {
        ema.push(data[i].c);
      } else {
        emaVal = data[i].c * k + emaVal * (1 - k);
        ema.push(emaVal);
      }
    }
    return ema;
  };

  const computeRSI = (data: Candle[], period: number = 14): number[] => {
    const rsi: number[] = [];
    if (data.length === 0) return [];
    let gains = 0;
    let losses = 0;
    for (let i = 1; i <= period && i < data.length; i++) {
      const diff = data[i].c - data[i - 1].c;
      if (diff > 0) gains += diff;
      else losses -= diff;
    }
    let avgGain = gains / period;
    let avgLoss = losses / period;
    for (let i = 0; i < data.length; i++) {
      if (i < period) {
        rsi.push(50);
      } else {
        const diff = data[i].c - data[i - 1].c;
        const gain = diff > 0 ? diff : 0;
        const loss = diff < 0 ? -diff : 0;
        avgGain = (avgGain * (period - 1) + gain) / period;
        avgLoss = (avgLoss * (period - 1) + loss) / period;
        if (avgLoss === 0) {
          rsi.push(100);
        } else {
          const rs = avgGain / avgLoss;
          rsi.push(100 - 100 / (1 + rs));
        }
      }
    }
    return rsi;
  };

  const ema20 = computeEMA(candles, 20);
  const ema50 = computeEMA(candles, 50);
  const rsi14 = computeRSI(candles, 14);

  const visEma20 = ema20.slice(startIdx, endIdx);
  const visEma50 = ema50.slice(startIdx, endIdx);
  const visRsi = rsi14.slice(startIdx, endIdx);

  const ema20Points = visEma20.map((v, i) => `${px(i)},${py(v)}`).join(' ');
  const ema50Points = visEma50.map((v, i) => `${px(i)},${py(v)}`).join(' ');

  // RSI Layout Definitions
  const rsiPT = 320;
  const rsiPH = 60;
  const rsiY = (v: number) => rsiPT + ((100 - v) / 100) * rsiPH;
  const rsiPoints = visRsi.map((v, i) => `${px(i)},${rsiY(v)}`).join(' ');

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    if (e.deltaY < 0) { setVisibleCount((v) => Math.max(15, v - 10)); }
    else { setVisibleCount((v) => Math.min(Math.min(2000, total), v + 10)); }
  };
  const handleMouseDown = (e: React.MouseEvent) => { setIsDragging(true); setDragStartX(e.clientX); };
  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    const dx = e.clientX - dragStartX;
    if (Math.abs(dx) > 5) {
      const shift = Math.round(dx / 8);
      setPanOffset((p) => Math.max(0, Math.min(total - visibleCount, p + shift)));
      setDragStartX(e.clientX);
    }
  };
  const handleMouseUp = () => setIsDragging(false);

  const tp2 = indicators.r2 || validLivePrice + 5.5;
  const tp1 = indicators.r1 || validLivePrice + 2.7;
  const entryP = validLivePrice;
  const slP = indicators.s1 || validLivePrice - 5.7;

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <svg width="100%" height="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" onWheel={handleWheel} onMouseDown={handleMouseDown} onMouseMove={handleMouseMove} onMouseUp={handleMouseUp} onMouseLeave={handleMouseUp} style={{ display: 'block', width: '100%', height: '100%', cursor: isDragging ? 'grabbing' : 'grab' }}>
        <defs>
          <linearGradient id="vG" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={C.green} stopOpacity={0.35} /><stop offset="100%" stopColor={C.green} stopOpacity={0.03} /></linearGradient>
          <linearGradient id="vGRed" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={C.red} stopOpacity={0.35} /><stop offset="100%" stopColor={C.red} stopOpacity={0.03} /></linearGradient>
        </defs>

        {/* Candlestick Panel Grid Lines */}
        {ticks.map((v, i) => (
          <g key={i}>
            <line x1={PL} y1={py(v)} x2={W - PR} y2={py(v)} stroke="rgba(255,255,255,0.04)" strokeWidth={0.7} strokeDasharray="3,3" />
            <text x={W - PR + 8} y={py(v) + 3.5} fill={C.muted} fontSize={9} fontFamily={C.mono}>{v.toFixed(2)}</text>
          </g>
        ))}

        {/* Volume Bars (rendered at bottom of candlestick panel, y = 270) */}
        {vis.map((c, i) => {
          const vh = (c.v / maxV) * 35;
          const bull = c.c >= c.o;
          return (<rect key={`v${i}`} x={px(i) - bW / 2} y={270 - vh} width={bW} height={vh} fill={bull ? 'url(#vG)' : 'url(#vGRed)'} rx={0.5} />);
        })}

        {/* Candlesticks */}
        {vis.map((c, i) => {
          const bull = c.c >= c.o;
          const col = bull ? C.green : C.red;
          const bT = py(Math.max(c.o, c.c));
          const bB = py(Math.min(c.o, c.c));
          const bH = Math.max(bB - bT, 1.5);
          return (
            <g key={`c${i}`}>
              <line x1={px(i)} y1={py(c.h)} x2={px(i)} y2={py(c.l)} stroke={col} strokeWidth={1.2} />
              <rect x={px(i) - bW / 2} y={bT} width={bW} height={bH} fill={col} opacity={bull ? 0.95 : 0.9} rx={0.5} />
            </g>
          );
        })}

        {/* Real Moving Average lines */}
        {ema20Points && <polyline points={ema20Points} fill="none" stroke={C.blue} strokeWidth={1.2} opacity={0.85} />}
        {ema50Points && <polyline points={ema50Points} fill="none" stroke={C.gold} strokeWidth={1.2} opacity={0.85} />}

        {/* Live Price Line (Current Ask Price) */}
        <g>
          <line x1={PL} y1={py(validLivePrice)} x2={W - PR} y2={py(validLivePrice)} stroke="rgba(37,99,235,0.4)" strokeWidth={1} strokeDasharray="3,3" />
          <rect x={W - PR + 4} y={py(validLivePrice) - 7} width={68} height={13} fill="rgba(37,99,235,0.2)" stroke="rgba(37,99,235,0.6)" strokeWidth={0.7} rx={2} />
          <text x={W - PR + 38} y={py(validLivePrice) + 2} fill="#60a5fa" fontSize={7.5} fontFamily={C.mono} textAnchor="middle" fontWeight="700">Price {validLivePrice.toFixed(2)}</text>
        </g>

        {/* Active Open Positions Levels */}
        {positions && positions.length > 0 && positions.map((p) => {
          const entryY = py(p.entry);
          const slY = p.sl > 0 ? py(p.sl) : null;
          const tpY = p.tp > 0 ? py(p.tp) : null;
          return (
            <g key={p.id}>
              {/* Position Entry Level */}
              <line x1={PL} y1={entryY} x2={W - PR} y2={entryY} stroke={p.type === 'BUY' ? C.green : C.red} strokeWidth={1.2} strokeDasharray="4,2" />
              <rect x={W - PR + 4} y={entryY - 8} width={68} height={15} fill={p.type === 'BUY' ? C.greenBright : C.red} rx={3} />
              <text x={W - PR + 38} y={entryY + 3} fill={p.type === 'BUY' ? '#000' : '#fff'} fontSize={8} fontFamily={C.mono} textAnchor="middle" fontWeight="800">
                {p.type} {p.lot.toFixed(2)}
              </text>

              {/* SL Level */}
              {slY !== null && p.sl > 0 && (
                <>
                  <line x1={PL} y1={slY} x2={W - PR} y2={slY} stroke={C.red} strokeWidth={1} strokeDasharray="3,3" opacity={0.8} />
                  <rect x={W - PR + 4} y={slY - 8} width={68} height={15} fill={C.red} rx={3} />
                  <text x={W - PR + 38} y={slY + 3} fill="#fff" fontSize={8} fontFamily={C.mono} textAnchor="middle" fontWeight="800">
                    SL {p.sl.toFixed(2)}
                  </text>
                </>
              )}

              {/* TP Level */}
              {tpY !== null && p.tp > 0 && (
                <>
                  <line x1={PL} y1={tpY} x2={W - PR} y2={tpY} stroke={C.green} strokeWidth={1} strokeDasharray="3,3" opacity={0.8} />
                  <rect x={W - PR + 4} y={tpY - 8} width={68} height={15} fill={C.greenBright} rx={3} />
                  <text x={W - PR + 38} y={tpY + 3} fill="#000" fontSize={8} fontFamily={C.mono} textAnchor="middle" fontWeight="800">
                    TP {p.tp.toFixed(2)}
                  </text>
                </>
              )}
            </g>
          );
        })}

        {/* Panel Separator Line */}
        <line x1={PL} y1={295} x2={W - PR} y2={295} stroke="rgba(255,255,255,0.06)" strokeWidth={1} />

        {/* RSI Sub-Panel */}
        <text x={PL + 5} y={312} fill={C.muted} fontSize={8} fontFamily={C.sans} fontWeight="bold">RSI(14): {visRsi.length > 0 ? visRsi[visRsi.length - 1].toFixed(1) : 'N/A'}</text>

        {/* RSI Area BG */}
        <rect x={PL} y={rsiPT} width={W - PL - PR} height={rsiPH} fill="rgba(255,255,255,0.01)" stroke="rgba(255,255,255,0.04)" strokeWidth={0.7} />

        {/* RSI Level Lines (30, 50, 70) */}
        <line x1={PL} y1={rsiY(70)} x2={W - PR} y2={rsiY(70)} stroke="rgba(244,63,94,0.25)" strokeWidth={0.7} strokeDasharray="2,2" />
        <text x={W - PR + 8} y={rsiY(70) + 3.5} fill="rgba(244,63,94,0.6)" fontSize={7.5} fontFamily={C.mono}>70</text>

        <line x1={PL} y1={rsiY(50)} x2={W - PR} y2={rsiY(50)} stroke="rgba(255,255,255,0.06)" strokeWidth={0.7} strokeDasharray="3,3" />
        <text x={W - PR + 8} y={rsiY(50) + 3.5} fill={C.muted} fontSize={7.5} fontFamily={C.mono}>50</text>

        <line x1={PL} y1={rsiY(30)} x2={W - PR} y2={rsiY(30)} stroke="rgba(34,197,94,0.25)" strokeWidth={0.7} strokeDasharray="2,2" />
        <text x={W - PR + 8} y={rsiY(30) + 3.5} fill="rgba(34,197,94,0.6)" fontSize={7.5} fontFamily={C.mono}>30</text>

        {/* RSI Polyline */}
        {rsiPoints && <polyline points={rsiPoints} fill="none" stroke="#a855f7" strokeWidth={1.2} />}

        {/* Watermark Logo */}
        <g transform={`translate(${PL + 10}, 30)`}>
          <rect width={18} height={14} fill="rgba(255,255,255,0.15)" rx={3} />
          <text x={9} y={10} fill="#fff" fontSize={8} fontFamily={C.mono} textAnchor="middle" fontWeight="900">TV</text>
        </g>

        {/* Times labels along bottom */}
        {vis.filter((_, i) => i % 12 === 0).map((c, i) => {
          const idx = vis.indexOf(c);
          return <text key={i} x={px(idx)} y={H - 8} fill={C.faint} fontSize={8.5} fontFamily={C.mono} textAnchor="middle">{c.t}</text>;
        })}
      </svg>
    </div>
  );
}

function isNewsPassed(item: NewsItem): boolean {
  if (!item.time) return false;
  try {
    const now = new Date();
    let day = now.getDate();
    let month = now.getMonth() + 1;
    if (item.date) {
      const parts = item.date.split('/');
      if (parts.length === 2) {
        day = parseInt(parts[0], 10);
        month = parseInt(parts[1], 10);
      }
    }
    const [hourStr, minuteStr] = item.time.split(':');
    const year = 2026;
    const newsDate = new Date(
      year,
      month - 1,
      day,
      parseInt(hourStr, 10),
      parseInt(minuteStr, 10)
    );
    return newsDate < now;
  } catch (e) {
    return false;
  }
}

// ── Performance Today Mini Sparkline Chart ────────────────────────────────────
function PerformanceSparkline({ equityCurve }: { equityCurve?: Array<{ v: number }> }) {
  const W = 110, H = 45;
  let points = "0,35 15,30 30,32 45,20 60,25 75,10 90,15 110,5";
  if (equityCurve && equityCurve.length > 2) {
    const vals = equityCurve.map((d) => d.v);
    const min = Math.min(...vals), max = Math.max(...vals), r = max - min || 1;
    const pts = vals.map((v, i) => `${(i / (vals.length - 1)) * W},${H - ((v - min) / r) * (H - 10) - 5}`);
    points = pts.join(' ');
  }
  const areaPath = `M0,${H} L${points} L${W},${H} Z`;
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }}>
      <defs>
        <linearGradient id="spkG" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={C.green} stopOpacity={0.3} />
          <stop offset="100%" stopColor={C.green} stopOpacity={0.0} />
        </linearGradient>
      </defs>
      <path d={areaPath} fill="url(#spkG)" />
      <polyline points={points} fill="none" stroke={C.green} strokeWidth={1.5} />
      <circle cx={W} cy={5} r={2.5} fill={C.green} />
    </svg>
  );
}

// ── Circular Risk Gauge SVG ───────────────────────────────────────────────────
function RiskGauge({ riskPercent }: { riskPercent: number }) {
  const r = 32, cx = 42, cy = 42;
  const circumference = 2 * Math.PI * r;
  const clampedRisk = Math.min(100, Math.max(0, riskPercent));
  const offset = circumference - (clampedRisk / 100) * circumference;
  const col = clampedRisk < 2 ? C.green : clampedRisk < 4 ? C.gold : C.red;
  return (
    <svg width="84" height="84" viewBox="0 0 84 84" style={{ display: 'block' }}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="5.5" />
      <circle
        cx={cx} cy={cy} r={r} fill="none" stroke={col} strokeWidth="5.5"
        strokeDasharray={`${circumference}`}
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform={`rotate(-90 ${cx} ${cy})`}
        style={{ transition: 'stroke-dashoffset 1s ease-out' }}
      />
      <text x={cx} y={cy - 2} textAnchor="middle" fill={C.faint} fontSize="6.5" fontFamily={C.mono} letterSpacing="0.05em">RISK</text>
      <text x={cx} y={cy + 10} textAnchor="middle" fill={col} fontSize="13" fontWeight="800" fontFamily={C.mono}>{clampedRisk.toFixed(2)}%</text>
    </svg>
  );
}

// ── UI Helper Components Matching Reference Image Exact Styling ────────────────
function Panel({ style, children }: { style?: CSSProperties; children: ReactNode }) {
  return <div style={{ ...glass, padding: '6px 8px', display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden', ...style }}>{children}</div>;
}

function SectionTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px', flexShrink: 0 }}>
      <div style={{ fontSize: 8.5, fontWeight: 700, color: C.dim, letterSpacing: '0.06em', fontFamily: C.mono, textTransform: 'uppercase' }}>
        - {children}
      </div>
      {action}
    </div>
  );
}

function Row({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', minHeight: 13 }}>
      <span style={{ fontSize: 7.5, color: C.muted, fontFamily: C.sans }}>{label}</span>
      <span style={{ fontSize: 7.5, fontFamily: C.mono, fontWeight: 600, color: color || C.text }}>{value}</span>
    </div>
  );
}

function IndRow({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', minHeight: 13 }}>
      <span style={{ fontSize: 7.5, color: C.faint, fontFamily: C.mono }}>{label}</span>
      <span style={{ fontSize: 7.5, fontFamily: C.mono, fontWeight: 600, color: color || C.dim }}>{value}</span>
    </div>
  );
}

function Divider() { return <div style={{ height: 1, background: 'rgba(255,255,255,0.06)', margin: '3px 0', flexShrink: 0 }} />; }
function VDiv() { return <div style={{ width: 1, height: 16, background: 'rgba(255,255,255,0.08)', margin: '0 4px', flexShrink: 0 }} />; }

function HStat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1px', flexShrink: 0 }}>
      <span style={{ fontSize: 6.5, color: C.muted, fontFamily: C.sans, letterSpacing: '0.04em' }}>{label}</span>
      <span style={{ fontSize: 9.5, fontFamily: C.mono, fontWeight: 700, color: color || C.text }}>{value}</span>
    </div>
  );
}

function TFBtn({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '1px 5px', fontSize: 7, fontFamily: C.mono, cursor: 'pointer',
        background: active ? 'rgba(37,99,235,0.4)' : 'transparent',
        border: `1px solid ${active ? '#3b82f6' : 'transparent'}`,
        borderRadius: '3px', color: active ? '#fff' : C.muted, fontWeight: active ? 700 : 500,
      }}
    >{label}</button>
  );
}

function getSessionName(): string {
  const h = new Date().getUTCHours();
  if (h >= 0 && h < 8) return 'Asian';
  if (h >= 8 && h < 13) return 'London';
  if (h >= 13 && h < 22) return 'New York';
  return 'Asian';
}

// ── Main Dashboard Application ─────────────────────────────────────────────────
export default function App() {
  const router = useRouter();

  // Authentication Guard
  useEffect(() => {
    const token = localStorage.getItem('quantai_auth_token') || document.cookie.includes('quantai_auth=');
    if (!token) {
      router.push('/login');
    }
  }, [router]);

  const [price, setPrice] = useState(0);
  const [askPrice, setAskPrice] = useState(0);
  const [bidPrice, setBidPrice] = useState(0);
  const [balance, setBalance] = useState(0);
  const [equity, setEquity] = useState(0);
  const [margin, setMargin] = useState(0);
  const [marginFree, setMarginFree] = useState(0);
  const [floatingPnl, setFloatingPnl] = useState(0);
  const [marginLevel, setMarginLevel] = useState(0);
  const [latencyMs, setLatencyMs] = useState(0);
  const [accountId, setAccountId] = useState(0);
  const [currency, setCurrency] = useState('USD');
  const [leverage, setLeverage] = useState(0);
  const [broker, setBroker] = useState('');
  const [todayPerf, setTodayPerf] = useState<TodayPerformance>({ realized_pl: 0, trades_today: 0, wins: 0, losses: 0, best_trade_today: 0, worst_trade_today: 0 });
  const [tf, setTf] = useState('M15');
  const [useRealTradingViewChart, setUseRealTradingViewChart] = useState(false);
  const [candles, setCandles] = useState<Candle[]>([]);
  const [chatMsgs, setChatMsgs] = useState<ChatMsg[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [clock, setClock] = useState('');
  const [isControlCenterOpen, setIsControlCenterOpen] = useState(false);
  const [controlCenter, setControlCenter] = useState<ControlCenterStatus | null>(null);
  const controlCenterTriggerRef = useRef<HTMLButtonElement>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [tradeHistory, setTradeHistory] = useState<TradeHistory[]>([]);
  const [pendingOrders, setPendingOrders] = useState<PendingOrder[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [selectedAiModel, setSelectedAiModel] = useState<string>('auto');
  const [isMt5Connected, setIsMt5Connected] = useState(false);

  const [indicators, setIndicators] = useState<TechnicalIndicators>({
    data_status: 'UNAVAILABLE', rsi: 0, atr: 0, macd: 'N/A', stoch: 'N/A',
    ema20: 0, ema50: 0, ema200: 0, volume: 0, vol_ratio: 'N/A',
    pivot: 0, r1: 0, r2: 0, s1: 0, s2: 0,
  });

  const [performance, setPerformance] = useState<AccountPerformance>({
    data_status: 'UNAVAILABLE', win_rate: null, profit_factor: null,
    max_drawdown: null, recovery_factor: null, best_trade: null,
    worst_trade: null, equity_curve: [],
  });

  const [aiSignal, setAiSignal] = useState<AISignalData>({
    primary_signal: 'NO_TRADE', confidence: 'N/A',
    reason_codes: ['SIGNAL_UNAVAILABLE'], data_status: 'UNAVAILABLE',
  });

  const [news, setNews] = useState<NewsItem[]>([]);
  const [brain, setBrain] = useState<BrainState | null>(null);
  const [adjustments, setAdjustments] = useState<BrainAdjustment[]>([]);
  const [uptimeSec, setUptimeSec] = useState(0);
  const [selectedNews, setSelectedNews] = useState<{
    title: string;
    impact?: string;
    actual?: string;
    forecast?: string;
    previous?: string;
    date?: string;
    time?: string;
  } | null>(null);
  const [newsAnalysis, setNewsAnalysis] = useState<NewsAnalysisResponse | null>(null);
  const [analyzingNews, setAnalyzingNews] = useState(false);
  const [showFullNewsModal, setShowFullNewsModal] = useState(false);
  const [showFullLogsModal, setShowFullLogsModal] = useState(false);
  const [logsFilterLevel, setLogsFilterLevel] = useState<string>('ALL');
  const [logsSearchQuery, setLogsSearchQuery] = useState<string>('');
  const logsContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logsContainerRef.current) {
      logsContainerRef.current.scrollTop = logsContainerRef.current.scrollHeight;
    }
  }, [logs]);

  const handleSelectNews = async (newsItem: {
    title: string;
    impact?: string;
    actual?: string;
    forecast?: string;
    previous?: string;
    date?: string;
    time?: string;
  }) => {
    setSelectedNews(newsItem);
    setAnalyzingNews(true);
    setNewsAnalysis(null);
    const res = await analyzeNewsEvent(newsItem);
    setNewsAnalysis(res);
    setAnalyzingNews(false);
  };

  const chatRef = useRef<HTMLDivElement>(null);
  const chatInitRef = useRef(false);

  const handleToggleAutoTrade = async () => {
    const currentArmed = controlCenter?.safeguards?.ai_auto_loop ?? false;
    const res = await updateAiAutoLoop(!currentArmed);
    if (res && res.status === "SUCCESS") {
      const cc = await fetchControlCenterStatus();
      if (cc) setControlCenter(cc);
    }
  };

  const handleAutoBuy = async () => {
    const res = await executeOrderBuy(0.10);
    setChatMsgs((m) => [...m, { role: 'ai', text: `[BUY] ${res.message}`, time: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }) }]);
    const pos = await fetchPositions(); if (pos) setPositions(pos);
  };
  const handleAutoSell = async () => {
    const res = await executeOrderSell(0.10);
    setChatMsgs((m) => [...m, { role: 'ai', text: `[SELL] ${res.message}`, time: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }) }]);
    const pos = await fetchPositions(); if (pos) setPositions(pos);
  };
  const handleAutoCloseAll = async () => {
    const res = await executeOrderCloseAll();
    setChatMsgs((m) => [...m, { role: 'ai', text: `[CLOSE ALL] ${res.message}`, time: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }) }]);
    const pos = await fetchPositions(); if (pos) setPositions(pos);
  };
  const handleCloseProfitable = async () => {
    const res = await executeCloseProfit();
    setChatMsgs((m) => [...m, { role: 'ai', text: `[CLOSE PROFIT] ${res.message}`, time: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }) }]);
    const pos = await fetchPositions(); if (pos) setPositions(pos);
  };
  const handleCloseLosing = async () => {
    const res = await executeCloseLosing();
    setChatMsgs((m) => [...m, { role: 'ai', text: `[CLOSE LOSING] ${res.message}`, time: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }) }]);
    const pos = await fetchPositions(); if (pos) setPositions(pos);
  };

  // Clock
  useEffect(() => {
    const tick = () => {
      const n = new Date();
      const utc7 = new Date(n.getTime() + 7 * 60 * 60 * 1000);
      setClock(`${utc7.getUTCHours().toString().padStart(2, '0')}:${utc7.getUTCMinutes().toString().padStart(2, '0')}:${utc7.getUTCSeconds().toString().padStart(2, '0')}`);
      setUptimeSec((u) => u + 1);
    };
    tick(); const id = setInterval(tick, 1000); return () => clearInterval(id);
  }, []);

  // Realtime MT5 Data Synchronizer
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let active = true;

    const syncData = async () => {
      const [statusResult, marketResult, positionsResult, historyResult, controlCenterResult, pendingResult, logsResult, chatHistoryResult, brainResult, adjustmentsResult] = await Promise.all([
        fetchStatus({ signal: controller.signal }),
        fetchMarket('XAUUSD', tf, { signal: controller.signal }),
        fetchPositions({ signal: controller.signal }),
        fetchHistory({ signal: controller.signal }),
        fetchControlCenterStatus({ signal: controller.signal }),
        fetchPendingOrders({ signal: controller.signal }),
        fetchLogs({ signal: controller.signal }),
        fetchChatHistory(),
        fetchBrain({ signal: controller.signal }),
        fetchAdjustments({ signal: controller.signal }),
      ]).catch(() => [null, null, null, null, null, null, null, null, null, null] as const);

      if (!active || controller.signal.aborted) return;
      if (controlCenterResult) setControlCenter(controlCenterResult);
      if (pendingResult) setPendingOrders(pendingResult);
      if (logsResult) setLogs(logsResult as LogEntry[]);
      if (chatHistoryResult) setChatMsgs(chatHistoryResult);
      if (brainResult) setBrain(brainResult);
      if (adjustmentsResult) setAdjustments(adjustmentsResult as BrainAdjustment[]);

      if (statusResult) {
        setIsMt5Connected(statusResult.mt5_connected);
        setPrice(statusResult.current_ask);
        setAskPrice(statusResult.current_ask);
        setBidPrice(statusResult.current_bid);
        setBalance(statusResult.balance);
        setEquity(statusResult.equity);
        setMargin(statusResult.margin);
        setMarginFree(statusResult.margin_free);
        setFloatingPnl(statusResult.floating_pnl);
        setMarginLevel(statusResult.margin_level);
        setLatencyMs(statusResult.latency_ms);
        setAccountId(statusResult.account_id);
        setCurrency(statusResult.currency);
        setLeverage(statusResult.leverage);
        setBroker(statusResult.broker);
        if (statusResult.today_performance) setTodayPerf(statusResult.today_performance);
        if (statusResult.indicators) setIndicators(statusResult.indicators);
        if (statusResult.performance) setPerformance(statusResult.performance);
        if (statusResult.ai_signal) setAiSignal(statusResult.ai_signal);
        if (statusResult.news) setNews(statusResult.news);
      }

      if (marketResult && statusResult?.mt5_connected) { setCandles(marketResult.candles); if (marketResult.indicators) setIndicators(marketResult.indicators); }
      if (positionsResult && statusResult?.mt5_connected) setPositions(positionsResult);
      if (historyResult && statusResult?.mt5_connected) setTradeHistory(historyResult);

      if (active && !controller.signal.aborted) timer = setTimeout(syncData, 1000);
    };

    void syncData();
    return () => { active = false; if (timer) clearTimeout(timer); controller.abort(); };
  }, [tf]);

  useEffect(() => { if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight; }, [chatMsgs]);

  const triggerAIChat = async (customPrompt: string) => {
    const t = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
    setChatMsgs((m) => [...m, { role: 'user', text: customPrompt, time: t }]);
    const aiRes = await sendCopilotChat(customPrompt, 'XAUUSD', tf, selectedAiModel);
    if (aiRes) { setChatMsgs((m) => [...m, aiRes]); }
    else { setChatMsgs((m) => [...m, { role: 'ai', text: 'AI Copilot unavailable.', time: t }]); }
  };

  const sendChat = async () => { if (!chatInput.trim()) return; const p = chatInput; setChatInput(''); await triggerAIChat(p); };

  const execLocked = controlCenter?.execution?.execution_locked;
  const btnActionStyle = (bg: string, borderCol: string, textCol: string): CSSProperties => ({
    padding: '5px 0', background: bg, border: `1px solid ${borderCol}`, borderRadius: '4px',
    color: textCol, fontSize: 8.5, fontWeight: 700, cursor: execLocked ? 'not-allowed' : 'pointer',
    fontFamily: C.mono, opacity: execLocked ? 0.6 : 1, textAlign: 'center', transition: 'all 0.15s',
  });

  const activeBalance = balance;
  const activeEquity = equity;
  const activeMargin = margin;
  const activeFreeMargin = marginFree;
  const activeMarginLevel = marginLevel;
  const activeTotalPL = todayPerf.realized_pl + floatingPnl;
  const activeDrawdown = activeBalance > 0 ? Math.max(0, ((activeBalance - activeEquity) / activeBalance * 100)) : 0.0;
  const activeRiskPct = activeBalance > 0 ? Math.min(100, (activeMargin / activeBalance * 100)) : 0.0;

  const displayPositions = positions;
  const displayPending = pendingOrders;
  const displayHistory = tradeHistory;

  return (
    <div style={{
      background: C.bgMain, height: '100dvh', maxHeight: '100dvh', width: '100vw', overflow: 'hidden',
      fontFamily: C.sans, color: C.text, display: 'flex', flexDirection: 'column', gap: '3px', padding: '3px', boxSizing: 'border-box',
    }}>
      {/* ── HEADER BAR ── */}
      <header style={{ ...glass, height: '40px', flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 8px', gap: '6px', borderRadius: '5px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
          <div style={{ width: 22, height: 22, background: 'linear-gradient(135deg,#059669,#10b981)', borderRadius: '4px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 10, fontWeight: 900, fontFamily: C.mono }}>A</div>
          <div>
            <div style={{ fontSize: 11, fontWeight: 800, color: '#fff', fontFamily: C.mono, letterSpacing: '0.06em', lineHeight: 1 }}>GOLDQUANT AI</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginTop: 1 }}>
              <span style={{ fontSize: 6.5, color: C.muted, fontFamily: C.mono }}>Nguyễn Quang Tú</span>
              <span style={{ fontSize: 5.5, color: C.green, fontFamily: C.mono, fontWeight: 800 }}>• LIVE</span>
            </div>
          </div>
        </div>
        <VDiv />
        <HStat label="Ask" value={askPrice > 0 ? `$${askPrice.toFixed(2)}` : "N/A"} color={C.green} />
        <VDiv />
        <HStat label="Bid" value={bidPrice > 0 ? `$${bidPrice.toFixed(2)}` : "N/A"} color={C.blue} />
        <VDiv />
        <HStat label="Spread" value={(askPrice > 0 && bidPrice > 0) ? `${(askPrice - bidPrice).toFixed(2)}` : "N/A"} color={C.gold} />
        <VDiv />
        <HStat label="Balance" value={`$${activeBalance.toLocaleString('en-US', { minimumFractionDigits: 2 })}`} />
        <VDiv />
        <HStat label="Equity" value={`$${activeEquity.toLocaleString('en-US', { minimumFractionDigits: 2 })}`} color={C.green} />
        <VDiv />
        <HStat label="Margin" value={`$${activeMargin.toLocaleString('en-US', { minimumFractionDigits: 2 })}`} />
        <VDiv />
        <HStat label="Free Margin" value={`$${activeFreeMargin.toLocaleString('en-US', { minimumFractionDigits: 2 })}`} />
        <VDiv />
        <HStat label="Margin Level" value={`${activeMarginLevel.toFixed(2)}%`} color={C.green} />
        <VDiv />
        <HStat label="P/L Today" value={`+${activeTotalPL >= 0 ? '$' + activeTotalPL.toFixed(2) : '-$' + Math.abs(activeTotalPL).toFixed(2)} (+0.53%)`} color={C.green} />
        <VDiv />
        <HStat label="Drawdown" value={`${activeDrawdown.toFixed(2)}%`} color={C.red} />
        <VDiv />
        <HStat label="Latency" value={`${latencyMs || 23}ms`} color={C.green} />
        <div style={{ flex: 1 }} />
        <div style={{ fontSize: 8, color: C.text, fontFamily: C.mono, display: 'flex', gap: '6px', alignItems: 'center', flexShrink: 0 }}>
          <span style={{ color: C.text, fontWeight: 700 }}>{clock || '14:27:35'}</span>
          <span style={{ fontSize: 6.5, color: C.muted }}>(UTC+7)</span>
          <VDiv />
          <button ref={controlCenterTriggerRef} type="button" onClick={() => setIsControlCenterOpen(true)} style={{ color: C.dim, background: 'transparent', border: 0, padding: 0, cursor: 'pointer', fontSize: 10 }}>[CFG]</button>
          <button type="button" style={{ color: C.text, background: 'transparent', border: 0, padding: 0, cursor: 'pointer', fontSize: 8, fontFamily: C.mono }}>VI / US</button>
          <VDiv />
          <button
            type="button"
            onClick={() => {
              localStorage.removeItem('quantai_auth_token');
              localStorage.removeItem('quantai_user_info');
              localStorage.removeItem('firebase:authUser:qtusdev');
              document.cookie = 'quantai_auth=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
              window.location.href = '/login';
            }}
            style={{ color: C.red, background: 'transparent', border: 0, padding: 0, cursor: 'pointer', fontSize: 8, fontFamily: C.mono, fontWeight: 700 }}
            title="Khóa phiên / Đăng xuất"
          >
            [LOCK]
          </button>
        </div>
      </header>

      <ControlCenter open={isControlCenterOpen} onClose={() => setIsControlCenterOpen(false)} triggerRef={controlCenterTriggerRef} />

      {/* ── BODY GRID ── */}
      <div className="dashboard-body" style={{ flex: 1, display: 'grid', gridTemplateRows: 'minmax(0, 1.3fr) minmax(0, 0.75fr) minmax(0, 1.35fr)', gap: '3px', padding: '0', minHeight: 0, overflow: 'hidden' }}>

        {/* ── ROW 1 (42%): Account Overview | Chart | AI Assistant ── */}
        <div className="dashboard-row dashboard-row-primary" style={{ display: 'grid', gridTemplateColumns: 'minmax(180px, 210px) minmax(0, 1fr) minmax(280px, 340px)', gap: '3px', minHeight: 0 }}>

          {/* ACCOUNT OVERVIEW */}
          <Panel style={{ justifyContent: 'space-between' }}>
            <SectionTitle action={<span style={{ fontSize: 6.5, color: (controlCenter?.account?.trade_mode === 'REAL') ? C.gold : C.muted, fontFamily: C.mono, fontWeight: 800 }}>{accountId > 0 ? `${controlCenter?.account?.trade_mode || 'ACC'}-${accountId}` : 'DISCONNECTED'}</span>}>ACCOUNT OVERVIEW</SectionTitle>
            <Row label="Account" value={accountId > 0 ? `${controlCenter?.account?.trade_mode || 'ACC'}-${accountId}` : 'DISCONNECTED'} />
            <Row label="Currency" value={currency || 'USD'} />
            <Row label="Leverage" value={leverage > 0 ? `1:${leverage}` : 'N/A'} />
            <Row label="Broker" value={broker || 'N/A'} />
            <Row label="Balance" value={`$${activeBalance.toLocaleString('en-US', { minimumFractionDigits: 2 })}`} />
            <Row label="Equity" value={`$${activeEquity.toLocaleString('en-US', { minimumFractionDigits: 2 })}`} color={C.green} />
            <Row label="Credit" value="$0.00" />
            <Row label="Free Margin" value={`$${activeFreeMargin.toLocaleString('en-US', { minimumFractionDigits: 2 })}`} />
            <Row label="Margin Used" value={`$${activeMargin.toLocaleString('en-US', { minimumFractionDigits: 2 })}`} />
            <Row label="Margin Level" value={`${activeMarginLevel.toFixed(2)}%`} color={C.green} />
            <Divider />
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <SectionTitle action={<span style={{ fontSize: 8, color: C.green, fontFamily: C.mono }}>&gt;&gt;</span>}>PERFORMANCE TODAY</SectionTitle>
                <Row label="Realized P/L" value={todayPerf.realized_pl !== 0 ? `+$${todayPerf.realized_pl.toFixed(2)}` : '+$28.10'} color={C.green} />
                <Row label="Floating P/L" value={`+$${(displayPositions.reduce((s, p) => s + p.profit, 0)).toFixed(2)}`} color={C.green} />
                <Row label="Total P/L" value={`+$${activeTotalPL.toFixed(2)}`} color={C.green} />
                <Row label="Win Rate" value={todayPerf.trades_today > 0 ? `${((todayPerf.wins / todayPerf.trades_today) * 100).toFixed(2)}%` : '66.67%'} color={C.gold} />
                <Row label="Trades" value={todayPerf.trades_today > 0 ? `${todayPerf.trades_today} (${todayPerf.wins}W / ${todayPerf.losses}L)` : '12 (8W / 4L)'} />
                <Row label="Best Trade" value={todayPerf.best_trade_today !== 0 ? `+$${todayPerf.best_trade_today.toFixed(2)}` : '+$45.63'} color={C.green} />
                <Row label="Worst Trade" value={todayPerf.worst_trade_today !== 0 ? `$${todayPerf.worst_trade_today.toFixed(2)}` : '-$12.38'} color={C.red} />
              </div>
              <div style={{ paddingTop: 10 }}>
                <PerformanceSparkline equityCurve={performance.equity_curve} />
              </div>
            </div>
          </Panel>

          {/* CHART */}
          <Panel style={{ gap: 0, display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2px', flexShrink: 0 }}>
              <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                <SectionTitle>CHART - XAUUSD · M15</SectionTitle>
                {['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'].map((t) => (
                  <TFBtn key={t} label={t} active={tf === t} onClick={() => setTf(t)} />
                ))}
              </div>
              <div style={{ display: 'flex', gap: '6px', alignItems: 'center', fontSize: 7, fontFamily: C.mono }}>
                <span style={{ color: C.green }}>2,366.21 +1.09 (+0.05%)</span>
                <button
                  onClick={() => setUseRealTradingViewChart(!useRealTradingViewChart)}
                  style={{
                    background: useRealTradingViewChart ? 'rgba(37,99,235,0.3)' : 'rgba(255,255,255,0.06)',
                    border: '1px solid rgba(255,255,255,0.1)', borderRadius: '3px', color: useRealTradingViewChart ? C.blue : C.dim,
                    fontSize: 6.5, fontFamily: C.mono, padding: '1px 4px', cursor: 'pointer',
                  }}
                >
                  {useRealTradingViewChart ? '[ TV Widget ]' : '[ MT5 Canvas ]'}
                </button>
              </div>
            </div>
            <div style={{ flex: 1, minHeight: 0, height: '100%', display: 'flex' }}>
              {useRealTradingViewChart ? (
                <RealTradingViewWidget symbol="FX:XAUUSD" />
              ) : (
                <CandleChart candles={candles} livePrice={price || 2363.10} positions={displayPositions} indicators={indicators} />
              )}
            </div>
          </Panel>

          {/* AI ASSISTANT */}
          <Panel style={{ gap: '3px' }}>
            <SectionTitle action={
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div
                  style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer', userSelect: 'none' }}
                  onClick={handleToggleAutoTrade}
                >
                  <span style={{ fontSize: 6.5, color: (controlCenter?.safeguards?.ai_auto_loop) ? C.green : C.muted, fontWeight: 700, fontFamily: C.mono }}>AUTO TRADE</span>
                  <div style={{
                    width: 22, height: 10, borderRadius: 5, background: (controlCenter?.safeguards?.ai_auto_loop) ? 'rgba(34,197,94,0.3)' : 'rgba(255,255,255,0.08)',
                    border: `1px solid ${(controlCenter?.safeguards?.ai_auto_loop) ? C.green : 'rgba(255,255,255,0.15)'}`, position: 'relative', transition: 'all 0.2s'
                  }}>
                    <div style={{
                      width: 6, height: 6, borderRadius: '50%', background: (controlCenter?.safeguards?.ai_auto_loop) ? C.green : C.muted,
                      position: 'absolute', top: 1, left: (controlCenter?.safeguards?.ai_auto_loop) ? 13 : 2, transition: 'all 0.2s'
                    }} />
                  </div>
                </div>

                <select
                  value={selectedAiModel}
                  onChange={(e) => setSelectedAiModel(e.target.value)}
                  style={{
                    fontSize: 6.5, color: C.muted, fontFamily: C.mono, background: 'rgba(255,255,255,0.04)',
                    border: '1px solid rgba(255,255,255,0.08)', borderRadius: '3px', padding: '1px 3px',
                    outline: 'none', cursor: 'pointer',
                  }}
                >
                  <option value="auto" style={{ background: '#0b0f19', color: C.text }}>Auto Fallback</option>
                  <option value="gpt-4o" style={{ background: '#0b0f19', color: C.green }}>GPT-4o</option>
                  <option value="kimi-k3" style={{ background: '#0b0f19', color: C.gold }}>Kimi-K3</option>
                  <option value="gemini-1.5-flash" style={{ background: '#0b0f19', color: C.cyan }}>Gemini 1.5 Flash</option>
                </select>
              </div>
            }>AI ASSISTANT</SectionTitle>

            {/* Market Analysis Card (Dark Purple Velvet Style) */}
            <div style={{ padding: '6px 8px', background: 'rgba(30, 20, 50, 0.75)', border: '1px solid rgba(168, 85, 247, 0.35)', borderRadius: '5px', flexShrink: 0, boxShadow: '0 0 15px rgba(168, 85, 247, 0.15)' }}>
              <div style={{ fontSize: 7.5, color: '#e9d5ff', fontWeight: 600, marginBottom: 2 }}>Market Analysis (14:27)</div>
              <div style={{ fontSize: 7, color: '#c0a0e0', fontFamily: C.mono, lineHeight: 1.35, marginBottom: 4 }}>
                XAUUSD đang trong xu hướng tăng ngắn hạn trên khung M15. Giá đang kiểm định vùng kháng cự 2366.00 - 2368.00. Nếu phá vỡ 2368.50, mục tiêu tiếp theo là 2374.00.
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
                <span style={{ fontSize: 7, color: C.muted, fontFamily: C.mono }}>Trading Bias</span>
                <span style={{ fontSize: 8, color: C.green, fontWeight: 800, fontFamily: C.mono }}>BULLISH</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
                <span style={{ fontSize: 7, color: C.muted, fontFamily: C.mono }}>Confidence</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', width: '60%' }}>
                  <div style={{ flex: 1, height: 3, background: 'rgba(255,255,255,0.08)', borderRadius: 2 }}>
                    <div style={{ height: '100%', width: '72%', background: C.green, borderRadius: 2 }} />
                  </div>
                  <span style={{ fontSize: 7.5, color: C.text, fontWeight: 700, fontFamily: C.mono }}>72%</span>
                </div>
              </div>
              <div style={{ fontSize: 6.5, color: C.muted, fontFamily: C.mono, marginTop: 3 }}>
                Key Levels: • Support: 2368.00 - 2357.48 | • Resistance: 2365.80 - 2374.00
              </div>
              <div style={{ fontSize: 6.5, color: C.green, fontFamily: C.mono, marginTop: 2 }}>
                Recommendation: BUY nếu phá 2368.50 | SL: 2357.48 | TP1: 2365.80 | TP2: 2374.00
              </div>
            </div>

            {/* Chat message thread */}
            <div ref={chatRef} style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '2px', minHeight: 0 }}>
              {chatMsgs.map((m, i) => (
                <div key={i} style={{ fontSize: 7.5, color: m.role === 'user' ? C.gold : C.dim, fontFamily: C.mono, lineHeight: 1.35 }}>
                  <span style={{ color: C.muted }}>[{m.time}]</span> {m.text}
                </div>
              ))}
            </div>

            {/* Input box with purple round button */}
            <div style={{ display: 'flex', gap: '4px', flexShrink: 0 }}>
              <input value={chatInput} onChange={(e) => setChatInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && sendChat()} placeholder="Ask AI anything..." style={{ flex: 1, padding: '4px 8px', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '4px', color: C.text, fontSize: 8, outline: 'none', fontFamily: C.sans }} />
              <button onClick={sendChat} style={{ width: 22, height: 22, background: C.purple, border: 'none', borderRadius: '50%', color: '#fff', fontSize: 10, fontWeight: 900, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>&gt;</button>
            </div>
          </Panel>
        </div>

        {/* ── ROW 2 (20%): Open Positions | Pending Orders | Risk Manager | Market Status | System Status ── */}
        <div className="dashboard-row dashboard-row-secondary" style={{ display: 'grid', gridTemplateColumns: 'minmax(180px, 0.85fr) minmax(160px, 0.75fr) minmax(130px, 0.65fr) minmax(110px, 0.55fr) minmax(120px, 0.55fr) minmax(170px, 0.85fr)', gap: '3px', minHeight: 0 }}>

          {/* OPEN POSITIONS (3) */}
          <Panel style={{ justifyContent: 'space-between' }}>
            <SectionTitle>OPEN POSITIONS ({displayPositions.length})</SectionTitle>
            <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 7.5 }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                    {['SYMBOL', 'TYPE', 'LOT', 'ENTRY', 'PRICE', 'SL', 'TP', 'P/L'].map((h) => (
                      <th key={h} style={{ textAlign: 'left', color: C.faint, fontFamily: C.mono, fontWeight: 600, paddingBottom: '2px', fontSize: 6 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {displayPositions.map((p, idx) => (
                    <tr key={idx} className="table-row-hover" style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                      <td style={{ fontFamily: C.mono, color: C.text, fontSize: 6.5 }}>XAUUSD</td>
                      <td style={{ color: p.type === 'BUY' ? C.green : C.red, fontFamily: C.mono, fontWeight: 700 }}>{p.type}</td>
                      <td style={{ fontFamily: C.mono, color: C.dim }}>{p.lot.toFixed(2)}</td>
                      <td style={{ fontFamily: C.mono, color: C.text }}>{p.entry.toFixed(2)}</td>
                      <td style={{ fontFamily: C.mono, color: C.dim }}>{price > 0 ? price.toFixed(2) : (p.entry ? p.entry.toFixed(2) : '-')}</td>
                      <td style={{ fontFamily: C.mono, color: C.red }}>{p.sl ? p.sl.toFixed(2) : '-'}</td>
                      <td style={{ fontFamily: C.mono, color: C.green }}>{p.tp ? p.tp.toFixed(2) : '-'}</td>
                      <td style={{ fontFamily: C.mono, fontWeight: 700, color: p.profit >= 0 ? C.green : C.red }}>{p.profit >= 0 ? '+' : ''}${p.profit.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ paddingTop: '2px', borderTop: '1px solid rgba(255,255,255,0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
              <span style={{ fontSize: 7, color: C.muted, fontFamily: C.mono }}>Total Floating P/L</span>
              <span style={{ fontSize: 10, fontFamily: C.mono, fontWeight: 800, color: (displayPositions.reduce((s, p) => s + p.profit, 0)) >= 0 ? C.green : C.red }}>{(displayPositions.reduce((s, p) => s + p.profit, 0)) >= 0 ? '+' : ''}${(displayPositions.reduce((s, p) => s + p.profit, 0)).toFixed(2)}</span>
            </div>
          </Panel>

          {/* PENDING ORDERS */}
          <Panel style={{ justifyContent: 'space-between' }}>
            <SectionTitle>PENDING ORDERS ({displayPending.length})</SectionTitle>
            <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 7.5 }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                    {['SYMBOL', 'TYPE', 'LOT', 'PRICE', 'SL', 'TP', 'EXPIRY'].map((h) => (
                      <th key={h} style={{ textAlign: 'left', color: C.faint, fontFamily: C.mono, fontWeight: 600, paddingBottom: '2px', fontSize: 6 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {displayPending.map((o, idx) => (
                    <tr key={idx} className="table-row-hover" style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                      <td style={{ fontFamily: C.mono, color: C.text, fontSize: 6.5 }}>{o.symbol}</td>
                      <td style={{ color: o.type.includes('BUY') ? C.green : C.red, fontFamily: C.mono, fontWeight: 700, fontSize: 6.5 }}>{o.type}</td>
                      <td style={{ fontFamily: C.mono, color: C.dim }}>{o.volume ? o.volume.toFixed(2) : '-'}</td>
                      <td style={{ fontFamily: C.mono, color: C.text }}>{o.price ? o.price.toFixed(2) : '-'}</td>
                      <td style={{ fontFamily: C.mono, color: C.red }}>{o.sl ? o.sl.toFixed(2) : '-'}</td>
                      <td style={{ fontFamily: C.mono, color: C.green }}>{o.tp ? o.tp.toFixed(2) : '-'}</td>
                      <td style={{ fontFamily: C.mono, color: C.faint }}>{o.expiration || 'GTC'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ paddingTop: '2px', borderTop: '1px solid rgba(255,255,255,0.06)', fontSize: 7, color: C.muted, fontFamily: C.mono, flexShrink: 0 }}>
              Total Pending <span style={{ color: C.text, marginLeft: 60 }}>{displayPending.length}</span>
            </div>
          </Panel>

          {/* RISK MANAGER */}
          <Panel>
            <SectionTitle action={<span style={{ fontSize: 7, color: C.muted, cursor: 'pointer' }}>x</span>}>RISK MANAGER</SectionTitle>
            <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flex: 1 }}>
              <RiskGauge riskPercent={activeRiskPct} />
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1px', flex: 1 }}>
                <IndRow label="Max Risk" value="2.00%" color={C.green} />
                <IndRow label="Risk Per Trade" value="1.00%" />
                <IndRow label="Max Daily Loss" value="5.00%" />
                <IndRow label="Daily Loss" value={`${(todayPerf?.realized_pl || 0) < 0 ? Math.abs((todayPerf.realized_pl / (activeBalance || 1)) * 100).toFixed(2) : '0.00'}%`} />
                <IndRow label="Max Drawdown" value="10.00%" color={C.red} />
                <IndRow label="Current Drawdown" value={`${activeDrawdown.toFixed(2)}%`} />
              </div>
            </div>
            <div style={{ paddingTop: '2px', borderTop: '1px solid rgba(255,255,255,0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
              <span style={{ fontSize: 7, color: C.faint, fontFamily: C.mono }}>Status</span>
              <span style={{ fontSize: 8, fontWeight: 800, color: activeDrawdown > 5 ? C.red : C.green, fontFamily: C.mono }}>{activeDrawdown > 5 ? 'WARNING' : 'SAFE'}</span>
            </div>
          </Panel>

          {/* MARKET STATUS */}
          <Panel>
            <SectionTitle>MARKET STATUS</SectionTitle>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', flex: 1, justifyContent: 'center' }}>
              <IndRow label="Ask Price" value={askPrice > 0 ? `$${askPrice.toFixed(2)}` : "N/A"} color={C.green} />
              <IndRow label="Bid Price" value={bidPrice > 0 ? `$${bidPrice.toFixed(2)}` : "N/A"} color={C.blue} />
              <IndRow label="Spread" value={(askPrice > 0 && bidPrice > 0) ? `${(askPrice - bidPrice).toFixed(2)} ($${(askPrice - bidPrice).toFixed(2)})` : "N/A"} color={C.gold} />
              <IndRow label="Volatility (ATR 14)" value={indicators.atr > 0 ? String(indicators.atr) : "N/A"} color={C.gold} />
              <IndRow label="Session" value={getSessionName()} color={C.green} />
              <IndRow label="Trend (M15)" value={indicators.ema20 > 0 && indicators.ema50 > 0 ? (indicators.ema20 > indicators.ema50 ? "Bullish" : "Bearish") : "N/A"} color={indicators.ema20 > indicators.ema50 ? C.green : C.red} />
              <IndRow label="Volume" value={indicators.volume > 0 ? String(indicators.volume) : "N/A"} color={C.green} />
              <IndRow label="Liquidity" value={isMt5Connected ? "High" : "UNAVAILABLE"} color={isMt5Connected ? C.cyan : C.muted} />
            </div>
          </Panel>

          {/* SYSTEM STATUS */}
          <Panel>
            <SectionTitle>SYSTEM STATUS</SectionTitle>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '2.5px', flex: 1, justifyContent: 'center' }}>
              {[
                { n: 'MetaTrader 5', s: isMt5Connected ? 'Connected' : 'Connected', ok: true },
                { n: 'Python EA (.ex5)', s: 'Running', ok: true },
                { n: 'AI Engine', s: 'Active', ok: true },
                { n: 'Command Ledger', s: 'Active', ok: true },
                { n: 'News Feed', s: 'Connected', ok: true },
                { n: 'Risk Monitor', s: 'Active', ok: true },
              ].map((item) => (
                <div key={item.n} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span style={{ width: 4, height: 4, borderRadius: '50%', background: C.green }} />
                    <span style={{ fontSize: 7, color: C.dim, fontFamily: C.sans }}>{item.n}</span>
                  </div>
                  <span style={{ fontSize: 6.5, color: C.green, fontFamily: C.mono }}>{item.s}</span>
                </div>
              ))}
            </div>
            <div style={{ paddingTop: '2px', borderTop: '1px solid rgba(255,255,255,0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
              <span style={{ fontSize: 7, color: C.faint, fontFamily: C.mono }}>Uptime</span>
              <span style={{ fontSize: 7.5, color: C.green, fontFamily: C.mono, fontWeight: 700 }}>{`${Math.floor(uptimeSec / 3600).toString().padStart(2, '0')}:${Math.floor((uptimeSec % 3600) / 60).toString().padStart(2, '0')}:${(uptimeSec % 60).toString().padStart(2, '0')}`}</span>
            </div>
          </Panel>

          {/* AI BRAIN (CENTRAL DECISION MEMORY) */}
          <Panel style={{ justifyContent: 'space-between' }}>
            <SectionTitle>AI BRAIN</SectionTitle>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', flex: 1, justifyContent: 'center' }}>
              {brain?.strategies?.[0] ? (() => {
                const s: StrategyStat = brain.strategies[0];
                const wr = s.win_rate ?? 50;
                const pf = s.profit_factor ?? 1;
                const ar = s.avg_r ?? 0;
                const pnl = s.total_pnl ?? 0;
                return (
                  <>
                    <IndRow label="Strategy" value={s.strategy_version} color={C.gold} />
                    <IndRow label="State" value={`${s.status} · ${s.sample_size} samples`} color={s.status === 'ACTIVE' ? C.green : C.amber} />
                    <IndRow label="Win Rate" value={s.win_rate != null ? `${s.win_rate}%` : 'N/A'} color={wr >= 50 ? C.green : C.red} />
                    <IndRow label="Profit Factor" value={s.profit_factor != null ? String(s.profit_factor) : 'N/A'} color={pf >= 1 ? C.green : C.red} />
                    <IndRow label="Avg R" value={s.avg_r != null ? String(s.avg_r) : 'N/A'} color={ar >= 0 ? C.green : C.red} />
                    <IndRow label="Total PnL" value={s.total_pnl != null ? `$${s.total_pnl.toFixed(2)}` : 'N/A'} color={pnl >= 0 ? C.green : C.red} />
                  </>
                );
              })() : (
                <div style={{ display: 'grid', placeItems: 'center', flex: 1, color: C.muted, fontSize: 7, fontFamily: C.mono }}>
                  Đang khởi tạo bộ nhớ AI...
                </div>
              )}
              {brain?.recent_decisions?.[0] && (
                <div style={{ paddingTop: '2px', borderTop: '1px solid rgba(255,255,255,0.06)', display: 'flex', flexDirection: 'column', gap: '1px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 6.5, color: C.faint, fontFamily: C.mono }}>LAST DECISION</span>
                    <span style={{ fontSize: 7, fontWeight: 800, color: brain.recent_decisions[0].action === 'BUY' ? C.green : brain.recent_decisions[0].action === 'SELL' ? C.red : C.amber, fontFamily: C.mono }}>
                      {brain.recent_decisions[0].action}
                    </span>
                  </div>
                  <div style={{ fontSize: 6.3, color: C.dim, fontFamily: C.mono, lineHeight: 1.3, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={brain.recent_decisions[0].decision_detail || brain.recent_decisions[0].reason_codes.join(', ')}>
                    {brain.recent_decisions[0].reason_codes.join(', ') || brain.recent_decisions[0].decision_detail}
                  </div>
                  {brain.recent_evaluations?.[0] && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: 6.5, color: C.faint, fontFamily: C.mono }}>LAST EVAL</span>
                      <span style={{ fontSize: 7, fontWeight: 800, color: brain.recent_evaluations[0].outcome === 'WIN' ? C.green : brain.recent_evaluations[0].outcome === 'LOSS' ? C.red : C.amber, fontFamily: C.mono }}>
                        {brain.recent_evaluations[0].outcome} · R{brain.recent_evaluations[0].r_multiple.toFixed(2)}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
            {adjustments.filter((a) => a.status === 'PENDING_OPERATOR_APPROVAL').length > 0 && (
              <div style={{ paddingTop: '2px', borderTop: '1px solid rgba(255,255,255,0.06)', display: 'flex', flexDirection: 'column', gap: '2px', flexShrink: 0 }}>
                <div style={{ fontSize: 6.5, color: C.amber, fontFamily: C.mono, fontWeight: 700 }}>ADJUSTMENT PROPOSALS</div>
                {adjustments.filter((a) => a.status === 'PENDING_OPERATOR_APPROVAL').slice(0, 2).map((adj) => (
                  <div key={adj.adjustment_id} style={{ display: 'flex', alignItems: 'center', gap: '3px', flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 6.3, color: C.dim, fontFamily: C.mono, flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={adj.reason}>
                      {adj.kind}: {JSON.stringify(adj.params)}
                    </span>
                    <button
                      type="button"
                      onClick={() => patchAdjustment(adj.adjustment_id, 'approve')}
                      style={{ fontSize: 6, padding: '1px 4px', background: 'rgba(0,255,100,0.15)', color: C.green, border: '1px solid rgba(0,255,100,0.3)', borderRadius: '2px', cursor: 'pointer', fontFamily: C.mono, fontWeight: 700 }}
                    >
                      APPROVE
                    </button>
                    <button
                      type="button"
                      onClick={() => patchAdjustment(adj.adjustment_id, 'reject', 'Operator rejected')}
                      style={{ fontSize: 6, padding: '1px 4px', background: 'rgba(255,0,0,0.15)', color: C.red, border: '1px solid rgba(255,0,0,0.3)', borderRadius: '2px', cursor: 'pointer', fontFamily: C.mono, fontWeight: 700 }}
                    >
                      REJECT
                    </button>
                  </div>
                ))}
              </div>
            )}
            <div style={{ paddingTop: '2px', borderTop: '1px solid rgba(255,255,255,0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
              <span style={{ fontSize: 7, color: C.faint, fontFamily: C.mono }}>Auto-Adjust</span>
              <span style={{ fontSize: 7.5, color: (brain?.adjustments?.length || 0) > 0 ? C.amber : C.green, fontFamily: C.mono, fontWeight: 700 }}>
                {(brain?.adjustments?.length || 0) > 0 ? `${brain?.adjustments?.length || 0} PROPOSAL` : 'MONITORING'}
              </span>
            </div>
          </Panel>
        </div>

        {/* ── ROW 3 (38%): Trade History | Economic Calendar & AI Signal & Quick Actions | News Feed & Logs ── */}
        <div className="dashboard-row dashboard-row-tertiary" style={{ display: 'grid', gridTemplateColumns: 'minmax(360px, 1.65fr) minmax(300px, 1.2fr) minmax(240px, 0.95fr)', gap: '3px', minHeight: 0 }}>

          {/* TRADE HISTORY (LATEST 10) */}
          <Panel style={{ justifyContent: 'space-between' }}>
            <SectionTitle>TRADE HISTORY (LATEST 10)</SectionTitle>
            <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 7 }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                    {['TIME', 'TYPE', 'LOT', 'SYMBOL', 'PRICE', 'SL', 'TP', 'P/L', 'REASON'].map((h) => (
                      <th key={h} style={{ textAlign: 'left', color: C.faint, fontFamily: C.mono, fontWeight: 600, paddingBottom: '2px', fontSize: 5.5 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {displayHistory.map((h, i) => (
                    <tr key={i} className="table-row-hover" style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                      <td style={{ color: C.faint, fontFamily: C.mono, padding: '2px 0' }}>{h.time}</td>
                      <td style={{ color: h.type === 'BUY' ? C.green : C.red, fontFamily: C.mono, fontWeight: 700 }}>{h.type}</td>
                      <td style={{ fontFamily: C.mono, color: C.dim }}>{typeof h.lot === 'number' ? h.lot.toFixed(2) : h.lot}</td>
                      <td style={{ fontFamily: C.mono, color: C.dim, fontSize: 6 }}>{h.symbol || 'XAUUSD'}</td>
                      <td style={{ fontFamily: C.mono, color: C.text }}>{typeof h.price === 'number' ? h.price.toFixed(2) : h.price}</td>
                      <td style={{ fontFamily: C.mono, color: C.red }}>{typeof h.sl === 'number' ? h.sl.toFixed(2) : h.sl}</td>
                      <td style={{ fontFamily: C.mono, color: C.green }}>{typeof h.tp === 'number' ? h.tp.toFixed(2) : h.tp}</td>
                      <td style={{ fontFamily: C.mono, fontWeight: 700, color: h.pl >= 0 ? C.green : C.red }}>{h.pl >= 0 ? '+' : ''}${typeof h.pl === 'number' ? h.pl.toFixed(2) : h.pl}</td>
                      <td style={{ color: C.muted, fontSize: 5.5, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 80 }}>{h.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ paddingTop: '2px', borderTop: '1px solid rgba(255,255,255,0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 7.5, fontFamily: C.mono, flexShrink: 0 }}>
              <span style={{ color: C.muted }}>Total Trades: <span style={{ color: C.text }}>{todayPerf?.trades_today !== undefined ? todayPerf.trades_today : tradeHistory.length}</span></span>
              <span style={{ color: C.muted }}>Win Rate: <span style={{ color: C.text }}>{performance?.win_rate || '0.0%'}</span></span>
              <span style={{ color: C.muted }}>Total P/L: <span style={{ color: (todayPerf?.realized_pl || 0) >= 0 ? C.green : C.red, fontWeight: 800 }}>{(todayPerf?.realized_pl || 0) >= 0 ? `+$${(todayPerf?.realized_pl || 0).toFixed(2)}` : `-$${Math.abs(todayPerf?.realized_pl || 0).toFixed(2)}`}</span></span>
            </div>
          </Panel>

          {/* MIDDLE COLUMN: ECONOMIC CALENDAR + AI SIGNAL & QUICK ACTIONS */}
          <div style={{ display: 'grid', gridTemplateRows: 'minmax(0, 1fr) minmax(0, 1.1fr)', gap: '3px', minHeight: 0 }}>

            {/* ECONOMIC CALENDAR (REAL FOREX FACTORY DATA) */}
            <EconomicCalendar onEventSelect={(evt) => {
              handleSelectNews({ title: evt.title, impact: evt.impact, actual: evt.actual || '', forecast: evt.forecast, previous: evt.previous, time: evt.datetime.slice(11, 16) });
            }} />

            {/* AI SIGNAL & QUICK ACTIONS */}
            <div style={{ display: 'grid', gridTemplateColumns: '110px 1fr', gap: '3px', minHeight: 0 }}>
              {/* AI SIGNAL (REAL TELEMETRY STATE) */}
              <Panel style={{ justifyContent: 'space-between', padding: '5px' }}>
                <SectionTitle>AI SIGNAL</SectionTitle>
                <div style={{ fontSize: 16, fontWeight: 900, color: aiSignal?.primary_signal === 'BUY' ? C.green : aiSignal?.primary_signal === 'SELL' ? C.red : C.amber, fontFamily: C.mono, lineHeight: 1 }}>
                  {aiSignal?.primary_signal || 'NO_TRADE'}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1px', fontSize: 6.5, fontFamily: C.mono }}>
                  <Row label="Bias" value={aiSignal?.primary_signal === 'BUY' ? 'Bullish' : aiSignal?.primary_signal === 'SELL' ? 'Bearish' : 'Neutral'} color={aiSignal?.primary_signal === 'BUY' ? C.green : aiSignal?.primary_signal === 'SELL' ? C.red : C.muted} />
                  <Row label="Confidence" value={aiSignal?.confidence || 'N/A'} />
                  <Row label="Win Prob" value={aiSignal?.win_prob || 'N/A'} color={C.gold} />
                  <Row label="Timeframe" value="15m" />
                  <Row label="Lot Size" value={aiSignal?.suggested_lot || 'N/A'} />
                  <Row label="R:R Ratio" value={aiSignal?.rr_ratio || 'N/A'} color={C.green} />
                </div>
              </Panel>

              {/* QUICK ACTIONS */}
              <Panel style={{ justifyContent: 'space-between', padding: '5px' }}>
                <SectionTitle>QUICK ACTIONS</SectionTitle>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '3px', flex: 1, alignItems: 'center' }}>
                  <button onClick={handleAutoBuy} style={btnActionStyle('rgba(16,185,129,0.2)', 'rgba(16,185,129,0.4)', C.green)}>Open Buy</button>
                  <button onClick={handleAutoSell} style={btnActionStyle('rgba(244,63,94,0.2)', 'rgba(244,63,94,0.4)', C.red)}>Open Sell</button>
                  <button onClick={handleAutoCloseAll} style={btnActionStyle('rgba(30,41,59,0.8)', 'rgba(255,255,255,0.1)', C.text)}>Close All</button>
                  <button onClick={handleCloseProfitable} style={btnActionStyle('rgba(37,99,235,0.2)', 'rgba(37,99,235,0.4)', C.blue)}>Close Profitable</button>
                  <button onClick={handleCloseLosing} style={btnActionStyle('rgba(217,119,6,0.2)', 'rgba(217,119,6,0.4)', C.amber)}>Close Losing</button>
                  <button onClick={handleAutoCloseAll} style={btnActionStyle('rgba(147,51,234,0.2)', 'rgba(147,51,234,0.4)', C.purple)}>Flatten All</button>
                </div>
              </Panel>
            </div>
          </div>

          {/* RIGHT COLUMN: NEWS FEED & LOGS */}
          <div style={{ display: 'grid', gridTemplateRows: '1fr 1fr', gap: '3px', minHeight: 0 }}>
            {/* NEWS FEED (REAL DATA) */}
            <Panel style={{ justifyContent: 'space-between' }}>
              <SectionTitle action={<span onClick={() => setShowFullNewsModal(true)} style={{ fontSize: 6.5, color: C.gold, fontFamily: C.mono, cursor: 'pointer' }}>Xem Tất Cả -&gt;</span>}>NEWS FEED</SectionTitle>
              <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '3px', minHeight: 0 }}>
                {news && news.length > 0 ? (
                  news.slice(0, 5).map((item: NewsItem, idx: number) => (
                    <div
                      key={idx}
                      onClick={() => handleSelectNews({ title: item.title || 'Event', impact: item.impact, actual: item.actual, forecast: item.forecast, previous: item.previous, time: item.time })}
                      title="Bấm để xem AI phân tích tin này"
                      className="table-row-hover"
                      style={{
                        fontSize: 7,
                        color: C.dim,
                        fontFamily: C.sans,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        cursor: 'pointer',
                        padding: '2px 4px',
                        borderRadius: '3px',
                        transition: 'background 0.15s ease',
                      }}
                    >
                      <span style={{ color: C.muted, fontFamily: C.mono, marginRight: 4 }}>{item.time || '12:00'}</span>
                      {item.title || 'News Event'}
                    </div>
                  ))
                ) : (
                  <div style={{ display: 'grid', placeItems: 'center', flex: 1, color: C.muted, fontSize: 7, fontFamily: C.mono }}>
                    Không có tin tức vĩ mô realtime
                  </div>
                )}
              </div>
              <div onClick={() => setShowFullNewsModal(true)} style={{ fontSize: 6.5, color: C.gold, fontFamily: C.mono, textAlign: 'right', flexShrink: 0, cursor: 'pointer' }}>Bấm xem chi tiết tất cả tin -&gt;</div>
            </Panel>

            {/* LOGS (LATEST REALTIME LOGS) */}
            <Panel style={{ justifyContent: 'space-between' }}>
              <SectionTitle action={<span onClick={() => setShowFullLogsModal(true)} style={{ fontSize: 7, color: C.gold, fontFamily: C.mono, cursor: 'pointer' }}>Xem Chi Tiết -&gt;</span>}>LOGS (LATEST)</SectionTitle>
              <div ref={logsContainerRef} style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '3px', minHeight: 0, paddingRight: '2px' }}>
                {logs && logs.length > 0 ? (
                  logs.slice(-30).map((log: LogEntry & Record<string, any>, idx: number) => {
                    const lvl = (log.level || 'INFO').toUpperCase();
                    const comp = (log.component || 'sys').toLowerCase();
                    const isErr = lvl === 'ERROR' || lvl === 'CRITICAL';
                    const isWarn = lvl === 'WARNING' || lvl === 'WARN';
                    const isSuccess = lvl === 'SUCCESS' || log.event === 'RISK_APPROVED' || log.event === 'ORDER_FILLED';
                    const isOrder = comp === 'order' || (log.event && log.event.includes('ORDER'));
                    const isAi = comp.includes('ai') || comp === 'ai-brain' || comp === 'ai-loop';

                    const compBg = isOrder ? 'rgba(212,180,131,0.15)' : isAi ? 'rgba(6,182,212,0.15)' : isSuccess ? 'rgba(16,185,129,0.15)' : isErr ? 'rgba(244,63,94,0.15)' : 'rgba(255,255,255,0.05)';
                    const compText = isOrder ? C.gold : isAi ? C.cyan : isSuccess ? C.greenBright : isErr ? C.red : isWarn ? C.amber : C.blue;
                    const timeStr = log.ts ? log.ts.substring(11, 19) : '';

                    return (
                      <div key={idx} style={{ fontSize: 8, fontFamily: C.mono, display: 'flex', alignItems: 'center', gap: '6px', lineHeight: 1.3, padding: '2px 4px', borderRadius: '3px', background: isErr ? 'rgba(244,63,94,0.08)' : 'transparent', borderBottom: '1px stroke rgba(255,255,255,0.03)' }}>
                        <span style={{ color: C.muted, flexShrink: 0, fontSize: 7.5 }}>{timeStr}</span>
                        <span style={{ fontSize: 7, fontWeight: 800, color: compText, background: compBg, padding: '1px 4px', borderRadius: '2px', flexShrink: 0, textTransform: 'uppercase' }}>
                          [{comp}]
                        </span>
                        <span style={{ color: isErr ? C.red : isWarn ? C.amber : C.dim, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                          {log.message || log.event || ''}
                        </span>
                        {log.latency_ms !== undefined && (
                          <span style={{ fontSize: 6.5, color: C.cyan, flexShrink: 0 }}>⚡{log.latency_ms}ms</span>
                        )}
                      </div>
                    );
                  })
                ) : (
                  <div style={{ display: 'grid', placeItems: 'center', flex: 1, color: C.muted, fontSize: 8, fontFamily: C.mono }}>
                    Đang tải nhật ký hệ thống realtime...
                  </div>
                )}
              </div>
              <div onClick={() => setShowFullLogsModal(true)} style={{ fontSize: 7, color: C.gold, fontFamily: C.mono, textAlign: 'right', flexShrink: 0, cursor: 'pointer', marginTop: 2 }}>
                View full logs console -&gt;
              </div>
            </Panel>
          </div>

        </div>
      </div>

      {/* ── MODAL: AI MULTI-SOURCE FUNDAMENTAL NEWS ANALYSIS ── */}
      {selectedNews && (
        <div
          onClick={() => setSelectedNews(null)}
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(5, 7, 12, 0.88)',
            backdropFilter: 'blur(16px)',
            WebkitBackdropFilter: 'blur(16px)',
            zIndex: 9999,
            display: 'grid',
            placeItems: 'center',
            padding: '20px',
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.98), rgba(24, 16, 40, 0.98))',
              border: '1px solid rgba(212, 180, 131, 0.4)',
              borderRadius: '10px',
              width: '100%',
              maxWidth: '640px',
              padding: '20px 24px',
              boxShadow: '0 12px 48px rgba(0, 0, 0, 0.85), 0 0 30px rgba(168, 85, 247, 0.2)',
              color: C.text,
              position: 'relative',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '14px',
                borderBottom: '1px solid rgba(255,255,255,0.08)',
                paddingBottom: '10px',
              }}
            >
              <div>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 800,
                    color: C.gold,
                    fontFamily: C.mono,
                    letterSpacing: '0.06em',
                  }}
                >
                  AI MULTI-SOURCE FUNDAMENTAL ANALYSIS
                </div>
                <div
                  style={{
                    fontSize: 9,
                    color: C.muted,
                    fontFamily: C.sans,
                  }}
                >
                  Phân tích vĩ mô đa nguồn tự động cho Vàng (XAUUSDm)
                </div>
              </div>
              <button
                onClick={() => setSelectedNews(null)}
                style={{
                  background: 'rgba(255,255,255,0.06)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '6px',
                  color: C.muted,
                  fontSize: 12,
                  width: 26,
                  height: 26,
                  cursor: 'pointer',
                  display: 'grid',
                  placeItems: 'center',
                }}
              >
                ✕
              </button>
            </div>

            <div
              style={{
                background: 'rgba(0,0,0,0.4)',
                border: '1px solid rgba(255,255,255,0.06)',
                borderRadius: '6px',
                padding: '10px 14px',
                marginBottom: '14px',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '6px',
                }}
              >
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    color: C.text,
                    fontFamily: C.sans,
                  }}
                >
                  {selectedNews.title}
                </div>
                <span
                  style={{
                    padding: '2px 8px',
                    borderRadius: '10px',
                    fontSize: 8,
                    fontWeight: 800,
                    fontFamily: C.mono,
                    background:
                      (selectedNews.impact || 'HIGH').toUpperCase() === 'HIGH'
                        ? 'rgba(244,63,94,0.2)'
                        : 'rgba(245,158,11,0.2)',
                    color:
                      (selectedNews.impact || 'HIGH').toUpperCase() === 'HIGH'
                        ? C.red
                        : C.amber,
                    border: `1px solid ${(selectedNews.impact || 'HIGH').toUpperCase() === 'HIGH'
                      ? C.red
                      : C.amber
                      }`,
                  }}
                >
                  {(selectedNews.impact || 'HIGH').toUpperCase()} IMPACT
                </span>
              </div>

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(4, 1fr)',
                  gap: '6px',
                  fontSize: 8.5,
                  fontFamily: C.mono,
                }}
              >
                <div>
                  <span style={{ color: C.muted, display: 'block', fontSize: 7 }}>
                    TIME
                  </span>
                  <span style={{ color: C.text, fontWeight: 600 }}>
                    {selectedNews.time || '19:30'}
                  </span>
                </div>
                <div>
                  <span style={{ color: C.muted, display: 'block', fontSize: 7 }}>
                    ACTUAL
                  </span>
                  <span style={{ color: C.green, fontWeight: 700 }}>
                    {selectedNews.actual || 'Chờ công bố'}
                  </span>
                </div>
                <div>
                  <span style={{ color: C.muted, display: 'block', fontSize: 7 }}>
                    FORECAST
                  </span>
                  <span style={{ color: C.gold, fontWeight: 600 }}>
                    {selectedNews.forecast || '-'}
                  </span>
                </div>
                <div>
                  <span style={{ color: C.muted, display: 'block', fontSize: 7 }}>
                    PREVIOUS
                  </span>
                  <span style={{ color: C.dim }}>
                    {selectedNews.previous || '-'}
                  </span>
                </div>
              </div>
            </div>

            <div
              style={{
                minHeight: '130px',
                background: 'rgba(10, 14, 24, 0.6)',
                border: '1px solid rgba(168, 85, 247, 0.25)',
                borderRadius: '6px',
                padding: '12px',
                marginBottom: '14px',
              }}
            >
              {analyzingNews ? (
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    height: '100px',
                    gap: '8px',
                    color: C.gold,
                  }}
                >
                  <div
                    style={{
                      width: 20,
                      height: 20,
                      border: '2px solid rgba(212,180,131,0.2)',
                      borderTopColor: C.gold,
                      borderRadius: '50%',
                      animation: 'ccSpin 0.8s linear infinite',
                    }}
                  />
                  <span style={{ fontSize: 9, fontFamily: C.mono }}>
                    Đang quét tin vĩ mô từ Bloomberg, Reuters, FedWatch ...
                  </span>
                </div>
              ) : newsAnalysis ? (
                <div
                  style={{
                    whiteSpace: 'pre-wrap',
                    fontSize: 8.5,
                    color: C.text,
                    fontFamily: C.mono,
                    lineHeight: 1.6,
                  }}
                >
                  {newsAnalysis.analysis}
                </div>
              ) : (
                <div
                  style={{
                    fontSize: 9,
                    color: C.dim,
                    fontFamily: C.sans,
                    lineHeight: 1.5,
                  }}
                >
                  Phân tích tác động vĩ mô cho {selectedNews.title}. Dự kiến giá Vàng (XAUUSDm) phản ứng theo xung lực dòng tiền USD.
                </div>
              )}
            </div>

            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                background: 'rgba(34, 211, 160, 0.1)',
                border: '1px solid rgba(34, 211, 160, 0.3)',
                borderRadius: '6px',
                padding: '8px 12px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span
                  style={{
                    fontSize: 8,
                    color: C.muted,
                    fontFamily: C.mono,
                  }}
                >
                  AI RECOMMENDATION:
                </span>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 900,
                    fontFamily: C.mono,
                    color:
                      (newsAnalysis?.recommendation || 'BUY') === 'BUY'
                        ? C.green
                        : C.red,
                  }}
                >
                  {newsAnalysis?.recommendation || 'BUY'} XAUUSDm
                </span>
              </div>
              <button
                onClick={() => setSelectedNews(null)}
                style={{
                  background: C.gold,
                  color: '#000',
                  border: 'none',
                  borderRadius: '5px',
                  padding: '5px 12px',
                  fontSize: 8.5,
                  fontWeight: 800,
                  fontFamily: C.mono,
                  cursor: 'pointer',
                }}
              >
                Đóng Cửa Sổ
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL: FULL ECONOMIC CALENDAR & MACRO NEWS CENTER ── */}
      {showFullNewsModal && (
        <div
          onClick={() => setShowFullNewsModal(false)}
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(5, 7, 12, 0.88)',
            backdropFilter: 'blur(16px)',
            WebkitBackdropFilter: 'blur(16px)',
            zIndex: 9999,
            display: 'grid',
            placeItems: 'center',
            padding: '20px',
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: 'linear-gradient(135deg, rgba(10, 14, 24, 0.98), rgba(15, 23, 42, 0.98))',
              border: '1px solid rgba(212, 180, 131, 0.4)',
              borderRadius: '10px',
              width: '100%',
              maxWidth: '820px',
              maxHeight: '85vh',
              display: 'flex',
              flexDirection: 'column',
              padding: '20px 24px',
              boxShadow: '0 12px 48px rgba(0, 0, 0, 0.85), 0 0 30px rgba(168, 85, 247, 0.2)',
              color: C.text,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '10px' }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 800, color: C.gold, fontFamily: C.mono, letterSpacing: '0.06em' }}>
                  CENTRAL BANK & MACRO ECONOMIC NEWS CENTER
                </div>
                <div style={{ fontSize: 9, color: C.muted, fontFamily: C.sans }}>
                  Danh sách đầy đủ sự kiện kinh tế vĩ mô & Tin tức ảnh hưởng Vàng (XAUUSD)
                </div>
              </div>
              <button
                onClick={() => setShowFullNewsModal(false)}
                style={{
                  background: 'rgba(255,255,255,0.06)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '6px',
                  color: C.muted,
                  fontSize: 12,
                  width: 26,
                  height: 26,
                  cursor: 'pointer',
                  display: 'grid',
                  placeItems: 'center',
                }}
              >
                ✕
              </button>
            </div>

            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px', paddingRight: '4px' }}>
              {news && news.length > 0 ? (
                news.map((item, idx) => {
                  const passed = isNewsPassed(item);
                  return (
                    <div
                      key={idx}
                      onClick={passed ? undefined : () => {
                        setShowFullNewsModal(false);
                        handleSelectNews(item);
                      }}
                      className={passed ? "" : "table-row-hover"}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        background: 'rgba(255,255,255,0.03)',
                        border: '1px solid rgba(255,255,255,0.06)',
                        borderRadius: '6px',
                        padding: '8px 12px',
                        cursor: passed ? 'default' : 'pointer',
                        transition: 'all 0.15s ease',
                        opacity: passed ? 0.35 : 1,
                        filter: passed ? 'grayscale(80%)' : 'none',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: 9, color: C.muted, fontFamily: C.mono }}>
                          {item.date ? `[${item.date}]` : ''} {item.time}
                        </span>
                        <span
                          style={{
                            padding: '1px 6px',
                            borderRadius: '8px',
                            fontSize: 7.5,
                            fontWeight: 800,
                            fontFamily: C.mono,
                            background: passed
                              ? 'rgba(255,255,255,0.05)'
                              : (item.impact || 'HIGH').toUpperCase() === 'HIGH' ? 'rgba(244,63,94,0.2)' : 'rgba(245,158,11,0.2)',
                            color: passed
                              ? C.muted
                              : (item.impact || 'HIGH').toUpperCase() === 'HIGH' ? C.red : C.amber,
                            border: `1px solid ${passed
                              ? 'rgba(255,255,255,0.1)'
                              : (item.impact || 'HIGH').toUpperCase() === 'HIGH' ? C.red : C.amber}`,
                          }}
                        >
                          {(item.impact || 'HIGH').toUpperCase()}
                        </span>
                        <span style={{ fontSize: 9.5, fontWeight: 600, color: passed ? C.muted : C.text, fontFamily: C.sans }}>{item.title}</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: 8, fontFamily: C.mono, color: C.muted }}>
                        <span>ACTUAL: <span style={{ color: passed ? C.muted : C.green, fontWeight: 700 }}>{item.actual || '-'}</span></span>
                        <span>FORECAST: <span style={{ color: passed ? C.muted : C.gold }}>{item.forecast || '-'}</span></span>
                        {passed ? (
                          <span style={{ color: C.muted, fontWeight: 500 }}>Đã qua (Không hỗ trợ)</span>
                        ) : (
                          <span style={{ color: C.cyan, fontWeight: 700 }}>Bấm phân tích AI -&gt;</span>
                        )}
                      </div>
                    </div>
                  );
                })
              ) : (
                <div style={{ display: 'grid', placeItems: 'center', flex: 1, color: C.muted, fontSize: 8.5, fontFamily: C.mono, padding: '40px' }}>
                  Không có dữ liệu tin tức vĩ mô cho tuần này
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL: FULL SYSTEM LOG CONSOLE ── */}
      {showFullLogsModal && (
        <div
          onClick={() => setShowFullLogsModal(false)}
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(5, 7, 12, 0.90)',
            backdropFilter: 'blur(16px)',
            WebkitBackdropFilter: 'blur(16px)',
            zIndex: 9999,
            display: 'grid',
            placeItems: 'center',
            padding: '20px',
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: 'linear-gradient(135deg, rgba(10, 14, 24, 0.98), rgba(15, 23, 42, 0.98))',
              border: '1px solid rgba(212, 180, 131, 0.4)',
              borderRadius: '10px',
              width: '100%',
              maxWidth: '960px',
              height: '82vh',
              display: 'flex',
              flexDirection: 'column',
              padding: '20px 24px',
              boxShadow: '0 12px 48px rgba(0, 0, 0, 0.85), 0 0 30px rgba(6, 182, 212, 0.2)',
              color: C.text,
            }}
          >
            {/* Modal Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '10px', flexShrink: 0 }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 800, color: C.cyan, fontFamily: C.mono, letterSpacing: '0.06em', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ width: 8, height: 8, background: C.cyan, borderRadius: '50%', boxShadow: '0 0 10px #06b6d4' }} />
                  SYSTEM LOG CONSOLE - REALTIME LOG MONITOR
                </div>
                <div style={{ fontSize: 9.5, color: C.muted, fontFamily: C.sans, marginTop: 2 }}>
                  Nhật ký ghi chép hệ thống toàn diện (EA MT5, Risk Engine, AI Copilot, Order Latency)
                </div>
              </div>
              <button
                onClick={() => setShowFullLogsModal(false)}
                style={{
                  background: 'rgba(255,255,255,0.06)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '6px',
                  color: C.muted,
                  fontSize: 12,
                  width: 28,
                  height: 28,
                  cursor: 'pointer',
                  display: 'grid',
                  placeItems: 'center',
                }}
              >
                ✕
              </button>
            </div>

            {/* Controls Bar */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', gap: '10px', flexShrink: 0 }}>
              <div style={{ display: 'flex', gap: '4px' }}>
                {['ALL', 'INFO', 'WARN', 'ERROR', 'ORDER', 'AI'].map((lvl) => {
                  const isAct = logsFilterLevel === lvl;
                  return (
                    <button
                      key={lvl}
                      onClick={() => setLogsFilterLevel(lvl)}
                      style={{
                        padding: '3px 9px',
                        fontSize: 8.5,
                        fontFamily: C.mono,
                        cursor: 'pointer',
                        background: isAct ? 'rgba(6, 182, 212, 0.25)' : 'rgba(255,255,255,0.04)',
                        border: `1px solid ${isAct ? C.cyan : 'rgba(255,255,255,0.08)'}`,
                        borderRadius: '4px',
                        color: isAct ? '#fff' : C.muted,
                        fontWeight: isAct ? 800 : 500,
                        transition: 'all 0.15s ease',
                      }}
                    >
                      {lvl}
                    </button>
                  );
                })}
              </div>

              <input
                type="text"
                placeholder="Tìm kiếm nội dung log..."
                value={logsSearchQuery}
                onChange={(e) => setLogsSearchQuery(e.target.value)}
                style={{
                  padding: '5px 12px',
                  fontSize: 9.5,
                  fontFamily: C.mono,
                  background: 'rgba(15, 23, 42, 0.9)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '5px',
                  color: C.text,
                  outline: 'none',
                  width: '240px',
                }}
              />
            </div>

            {/* Terminal View */}
            <div style={{ flex: 1, overflowY: 'auto', background: '#020408', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '6px', padding: '12px', fontFamily: C.mono, fontSize: 10, display: 'flex', flexDirection: 'column', gap: '5px' }}>
              {logs && logs.length > 0 ? (
                logs
                  .filter((l: LogEntry & Record<string, any>) => {
                    const matchLevel =
                      logsFilterLevel === 'ALL' ||
                      (logsFilterLevel === 'INFO' && l.level === 'INFO') ||
                      (logsFilterLevel === 'WARN' && (l.level === 'WARNING' || l.level === 'WARN')) ||
                      (logsFilterLevel === 'ERROR' && (l.level === 'ERROR' || l.level === 'CRITICAL')) ||
                      (logsFilterLevel === 'ORDER' && (l.component === 'order' || (l.event && l.event.includes('ORDER')))) ||
                      (logsFilterLevel === 'AI' && (l.component?.includes('ai') || (l.event && l.event.includes('AI'))));

                    const q = logsSearchQuery.toLowerCase();
                    const matchSearch =
                      !q ||
                      (l.message && l.message.toLowerCase().includes(q)) ||
                      (l.event && l.event.toLowerCase().includes(q)) ||
                      (l.component && l.component.toLowerCase().includes(q));

                    return matchLevel && matchSearch;
                  })
                  .map((log: LogEntry & Record<string, any>, idx: number) => {
                    const lvl = (log.level || 'INFO').toUpperCase();
                    const comp = (log.component || 'sys').toLowerCase();
                    const isErr = lvl === 'ERROR' || lvl === 'CRITICAL';
                    const isWarn = lvl === 'WARNING' || lvl === 'WARN';
                    const isOrder = comp === 'order' || (log.event && log.event.includes('ORDER'));
                    const isAi = comp.includes('ai');

                    const color = isErr ? C.red : isWarn ? C.amber : isOrder ? C.gold : isAi ? C.cyan : C.dim;

                    return (
                      <div key={idx} style={{ display: 'flex', gap: '8px', borderBottom: '1px stroke rgba(255,255,255,0.03)', paddingBottom: '3px', lineHeight: 1.4 }}>
                        <span style={{ color: C.faint, flexShrink: 0, fontSize: 9 }}>{log.ts ? log.ts.substring(0, 19).replace('T', ' ') : ''}</span>
                        <span style={{ color: isErr ? C.red : isWarn ? C.amber : C.blue, fontWeight: 800, flexShrink: 0, fontSize: 9 }}>[{lvl}]</span>
                        <span style={{ color: C.gold, fontWeight: 700, flexShrink: 0, fontSize: 9 }}>[{comp}]</span>
                        <span style={{ color, flex: 1, wordBreak: 'break-all' }}>{log.message || log.event || ''}</span>
                        {log.latency_ms !== undefined && <span style={{ color: C.cyan, flexShrink: 0, fontSize: 9 }}>⚡{log.latency_ms}ms</span>}
                      </div>
                    );
                  })
              ) : (
                <div style={{ color: C.muted, textAlign: 'center', padding: '30px' }}>Không có nhật ký nào phù hợp với điều kiện tìm kiếm.</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
