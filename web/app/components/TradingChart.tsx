'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { createChart, CandlestickSeries, LineSeries, IChartApi, ISeriesApi, CandlestickData, Time } from 'lightweight-charts';
import type { Candle, MarkupResponse } from '@/lib/api';

// ── Color Palette ──────────────────────────────────────────────────────────────
const C = {
  bg: '#05070c',
  grid: 'rgba(255,255,255,0.03)',
  bullish: '#22d3a0',
  bearish: '#f43f5e',
  gold: '#D4B483',

  // Pattern colors
  OB_BULL: 'rgba(34,211,160,0.15)',
  OB_BEAR: 'rgba(244,63,94,0.15)',
  FVG_BULL: 'rgba(59,130,246,0.25)',
  FVG_BEAR: 'rgba(236,72,153,0.25)',
  SR: 'rgba(251,191,36,0.2)',
  BREAKOUT: '#10b981',
  PATTERN_BULL: '#22d3a0',
  PATTERN_BEAR: '#f43f5e',
  SWING: '#a855f7',
  LIQUIDITY: '#ef4444',
  KILLZONE: 'rgba(168,85,247,0.1)',
  BOS: '#fbbf24',
  // Sniper / ICT / PA palette
  EMA9: '#22c55e',
  EMA21: '#ef4444',
  VWAP: '#06b6d4',
  SNIPER_SIGNAL: '#22d3ee',
  SNIPER_SL: '#ef4444',
  SNIPER_TP: '#22c55e',
  RIBBON_BULL: 'rgba(34,197,94,0.18)',
  RIBBON_BEAR: 'rgba(239,68,68,0.18)',
  PD_PREM: 'rgba(244,63,94,0.10)',
  PD_DISC: 'rgba(34,211,160,0.10)',
  OTE_BULL: 'rgba(34,197,94,0.20)',
  ASIAN_BAND: 'rgba(168,85,247,0.08)',
  PIVOT: 'rgba(251,191,36,0.6)',
  CANDLE_BULL: '#22d3a0',
  CANDLE_BEAR: '#f43f5e',
  CHART_PATTERN: '#fbbf24',
};

interface TradingChartProps {
  symbol?: string;
  timeframe?: string;
  markup?: MarkupResponse | null;
  candles?: Candle[];
  onTimeframeChange?: (tf: string) => void;
}

const TIMEFRAMES = ['M1', 'M5', 'M15', 'H1', 'H4', 'D1'];

export default function TradingChart({
  symbol = 'XAUUSD',
  timeframe = 'M15',
  markup,
  candles: propCandles,
  onTimeframeChange
}: TradingChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const priceLinesRef = useRef<any[]>([]);
  const [localTf, setLocalTf] = useState(timeframe);
  const [candles, setCandles] = useState<Candle[]>(propCandles || []);
  const [loading, setLoading] = useState(!propCandles);
  const [markupData, setMarkupData] = useState<MarkupResponse | null>(markup || null);

  // Parse ISO timestamp to chart Time
  const toTime = useCallback((ts: string): Time => {
    const d = new Date(ts);
    return Math.floor(d.getTime() / 1000) as Time;
  }, []);

  // Initialize chart
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: C.bg },
        textColor: '#94a3b8',
      },
      grid: {
        vertLines: { color: C.grid },
        horzLines: { color: C.grid },
      },
      crosshair: {
        mode: 1,
        vertLine: { color: 'rgba(212,180,131,0.4)', labelBackgroundColor: '#D4B483' },
        horzLine: { color: 'rgba(212,180,131,0.4)', labelBackgroundColor: '#D4B483' },
      },
      rightPriceScale: {
        borderColor: 'rgba(255,255,255,0.1)',
        scaleMargins: { top: 0.1, bottom: 0.2 },
      },
      timeScale: {
        borderColor: 'rgba(255,255,255,0.1)',
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: true,
      handleScale: true,
    });

    // v5 API: use addSeries with series definition
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: C.bullish,
      downColor: C.bearish,
      borderUpColor: C.bullish,
      borderDownColor: C.bearish,
      wickUpColor: C.bullish,
      wickDownColor: C.bearish,
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;

    // Handle resize
    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);
    handleResize();

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, []);

  // Update candles
  useEffect(() => {
    if (!candleSeriesRef.current || !candles.length) return;

    const chartData: CandlestickData<Time>[] = candles.map(c => ({
      time: toTime(c.t),
      open: c.o,
      high: c.h,
      low: c.l,
      close: c.c,
    }));

    candleSeriesRef.current.setData(chartData);
    chartRef.current?.timeScale().fitContent();
  }, [candles, toTime]);

  // Render all patterns from markup
  const renderMarkup = useCallback(() => {
    if (!chartRef.current || !candleSeriesRef.current || !markupData?.objects?.length) return;

    const series = candleSeriesRef.current;

    // Clear existing price lines
    priceLinesRef.current.forEach(line => {
      try { series.removePriceLine(line); } catch {}
    });
    priceLinesRef.current = [];

    const objects = markupData.objects;

    objects.forEach((m) => {
      if (!m.price && !['EMA', 'EMA_RIBBON', 'VWAP', 'ADX', 'MACD_LINE', 'SNIPER_DASH'].includes(m.type)) return;

      const isBullish = m.direction === 'BULLISH';
      let color = C.gold;
      let lineWidth: 1 | 2 | 3 | 4 = 1;
      let lineStyle: 0 | 1 | 2 | 3 | 4 = 0;
      let title = m.label || m.type.substring(0, 3);
      let showLabel = true;

      switch (m.type) {
        // ── SNIPER overlays ──
        case 'EMA':
          color = m.label === 'EMA9' ? C.EMA9 : C.EMA21;
          lineWidth = 2;
          title = m.label || 'EMA';
          break;
        case 'EMA_RIBBON':
          // Rendered as line + filled area via series; render top boundary here.
          color = isBullish ? C.RIBBON_BULL : C.RIBBON_BEAR;
          lineWidth = 1;
          title = `RIBBON ${m.direction}`;
          showLabel = false;
          break;
        case 'VWAP':
          color = C.VWAP;
          lineWidth = 2;
          title = 'VWAP';
          break;
        case 'ADX':
          color = '#94a3b8';
          lineStyle = 3;
          title = `ADX ${(m as any).adx?.toFixed(1) ?? ''}`;
          showLabel = true;
          break;
        case 'MACD_LINE':
          color = m.direction === 'BULLISH' ? '#22d3a0' : '#f43f5e';
          lineStyle = 3;
          title = 'MACD';
          break;
        case 'RSI_LEVEL':
          // RSI reference levels; skip drawing
          return;
        case 'SNIPER_SIGNAL':
          color = C.SNIPER_SIGNAL;
          lineWidth = 3;
          title = `▶ ${m.label}`;
          break;
        case 'SNIPER_SL':
          color = C.SNIPER_SL;
          lineWidth = 2;
          lineStyle = 2;
          title = m.label || 'SL';
          break;
        case 'SNIPER_TP1':
        case 'SNIPER_TP2':
        case 'SNIPER_TP3':
        case 'SNIPER_TP4':
        case 'SNIPER_TP5':
          color = C.SNIPER_TP;
          lineWidth = m.type === 'SNIPER_TP5' ? 3 : 1;
          lineStyle = m.type === 'SNIPER_TP5' ? 0 : 2;
          title = m.label || m.type.replace('SNIPER_', '');
          break;
        case 'SNIPER_SCORE':
        case 'SNIPER_DASH':
          // Rendered as overlay panel (below), not as price line.
          return;
        // ── SMC overlays ──
        case 'OB':
          color = isBullish ? C.bullish : C.bearish;
          break;
        case 'FVG':
          color = isBullish ? '#3b82f6' : '#ec4899';
          break;
        case 'BREAKER':
        case 'MITIGATION':
        case 'REJECTION':
          color = isBullish ? C.bullish : C.bearish;
          lineStyle = 3;
          break;
        case 'BSL':
        case 'LIQUIDITY_POOL':
          color = C.LIQUIDITY;
          lineStyle = 2;
          title = m.label || 'BSL';
          break;
        case 'SSL':
          color = '#10b981';
          lineStyle = 2;
          title = m.label || 'SSL';
          break;
        case 'EQH':
        case 'EQL':
          color = C.LIQUIDITY;
          lineStyle = 2;
          title = m.label || '';
          break;
        case 'SWING':
          color = C.SWING;
          break;
        case 'BOS':
        case 'CHoCH':
        case 'MSS':
          color = C.BOS;
          lineWidth = 2;
          title = m.label || m.type;
          break;
        case 'SFP':
          color = '#fbbf24';
          lineWidth = 2;
          lineStyle = 2;
          title = m.label || 'SFP';
          break;
        case 'INDUCEMENT':
          color = '#a78bfa';
          lineStyle = 3;
          title = 'IDM';
          break;
        case 'SUPPLY_DEMAND':
          color = isBullish ? '#22d3a0' : '#f43f5e';
          lineWidth = 2;
          title = m.label || (isBullish ? 'DEMAND' : 'SUPPLY');
          break;
        case 'LIQUIDITY':
          color = C.LIQUIDITY;
          break;
        // ── ICT overlays ──
        case 'ASIAN':
          color = '#a78bfa';
          lineStyle = 2;
          title = 'ASIAN';
          break;
        case 'KILLZONE':
          color = '#a855f7';
          lineStyle = 3;
          title = m.label || 'KZ';
          break;
        case 'OTE':
          color = C.OTE_BULL;
          lineWidth = 2;
          title = m.label || 'OTE';
          break;
        case 'PD':
          color = m.label === 'PREMIUM' ? C.PD_PREM : C.PD_DISC;
          lineStyle = 2;
          title = m.label || 'PD';
          showLabel = false;
          break;
        case 'JUDAS_SWING':
          color = '#fbbf24';
          lineWidth = 2;
          lineStyle = 2;
          title = m.label || 'JUDAS';
          break;
        case 'PO3':
          color = '#fb923c';
          lineWidth = 2;
          title = m.label || 'PO3';
          break;
        case 'SILVER_BULLET':
          color = '#c084fc';
          lineStyle = 3;
          title = 'SB';
          return;
        case 'UNICORN':
          color = '#22d3ee';
          lineWidth = 3;
          title = m.label || 'UNICORN';
          break;
        case 'NYMO':
          color = '#94a3b8';
          lineStyle = 3;
          title = 'NYMO';
          break;
        // ── Price Action overlays ──
        case 'CANDLE_PATTERN':
          color = isBullish ? C.CANDLE_BULL : C.CANDLE_BEAR;
          lineWidth = 2;
          lineStyle = 2;
          title = m.label || 'PATTERN';
          break;
        case 'PIVOT':
          color = C.PIVOT;
          lineStyle = 2;
          title = m.label || 'PIVOT';
          break;
        case 'PDH':
          color = C.PIVOT;
          lineWidth = 2;
          title = 'PDH';
          break;
        case 'PDL':
          color = C.PIVOT;
          lineWidth = 2;
          title = 'PDL';
          break;
        case 'SUPPORT':
        case 'RESISTANCE':
        case 'SR':
          color = 'rgba(251,191,36,0.7)';
          lineStyle = 2;
          title = m.label || m.type;
          break;
        case 'CHART_PATTERN':
          color = C.CHART_PATTERN;
          lineWidth = 2;
          lineStyle = 2;
          title = m.label || 'PATTERN';
          break;
        case 'TRENDLINE':
          color = m.direction === 'BULLISH' ? '#22d3a0' : '#f43f5e';
          lineStyle = 3;
          title = m.label || 'TL';
          break;
        case 'TREND':
          color = m.direction === 'BULLISH' ? '#22d3a0' : '#f43f5e';
          lineWidth = 2;
          title = m.direction === 'BULLISH' ? 'UP' : 'DOWN';
          break;
        // ── Legacy / fallback ──
        case 'LIQUIDITY':
          color = C.LIQUIDITY;
          break;
        case 'BREAKOUT':
          color = C.BREAKOUT;
          break;
        case 'PATTERN':
          color = isBullish ? C.PATTERN_BULL : C.PATTERN_BEAR;
          break;
        case 'PULLBACK':
        case 'RETEST':
          color = isBullish ? C.bullish : C.bearish;
          break;
        default:
          color = isBullish ? C.bullish : C.bearish;
      }

      if (m.price) {
        try {
          const line = series.createPriceLine({
            price: m.price,
            color: color,
            lineWidth: lineWidth,
            lineStyle: lineStyle,
            axisLabelVisible: showLabel,
            title: title,
          });
          priceLinesRef.current.push(line);
        } catch {}
      }
    });

  }, [markupData]);

  // Render markup when data changes
  useEffect(() => {
    renderMarkup();
  }, [renderMarkup]);

  // Fetch data
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/market?symbol=${symbol}&tf=${localTf}`);
        const data = await res.json();
        if (data.candles) setCandles(data.candles);
        if (data.markup) setMarkupData(data.markup);
      } catch (err) {
        console.error('Chart data fetch error:', err);
      } finally {
        setLoading(false);
      }
    };

    if (!propCandles) {
      fetchData();
      const interval = setInterval(fetchData, 30000);
      return () => clearInterval(interval);
    }
  }, [symbol, localTf, propCandles]);

  const handleTfChange = (tf: string) => {
    setLocalTf(tf);
    onTimeframeChange?.(tf);
  };

  // Legend data
  const legendItems = markupData?.advanced_counts || {};
  const sniperScore = markupData?.objects?.find((o: any) => o.type === 'SNIPER_SCORE');
  const confluence = (markupData as any)?.confluence;
  const sniperSignal = markupData?.objects?.find((o: any) => o.type === 'SNIPER_SIGNAL');

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      {/* Toolbar */}
      <div style={{
        position: 'absolute', top: 8, left: 8, zIndex: 10,
        display: 'flex', gap: 4, alignItems: 'center',
        background: 'rgba(5,7,12,0.9)', padding: '4px 8px', borderRadius: 4,
        fontSize: 11, fontFamily: 'JetBrains Mono, monospace',
      }}>
        <span style={{ color: C.gold, fontWeight: 600 }}>{symbol}</span>
        <span style={{ color: '#64748b' }}>{localTf}</span>
        <span style={{ color: '#64748b' }}>·</span>
        <span style={{ color: '#94a3b8' }}>{markupData?.method || ''}</span>
        {confluence && (
          <span style={{
            marginLeft: 12, padding: '2px 6px', borderRadius: 3,
            background: confluence.signal === 'BUY' ? 'rgba(34,197,94,0.25)' :
                       confluence.signal === 'SELL' ? 'rgba(239,68,68,0.25)' :
                       'rgba(100,116,139,0.25)',
            color: confluence.signal === 'BUY' ? '#22c55e' :
                   confluence.signal === 'SELL' ? '#ef4444' : '#94a3b8',
            fontWeight: 700,
          }}>
            {confluence.signal} · score {confluence.score}
            {confluence.rrr ? ` · RRR ${confluence.rrr}` : ''}
          </span>
        )}
        {Object.entries(legendItems).slice(0, 6).map(([key, val]) => (
          <span key={key} style={{ color: '#94a3b8', marginLeft: 8 }}>
            <span style={{ color: C.gold }}>{key}:</span> {val}
          </span>
        ))}
      </div>

      {/* Sniper score dashboard (top-right) — visible when SNIPER / ULTRA_CONFLUENCE method */}
      {sniperScore && (
        <div style={{
          position: 'absolute', top: 8, right: 96, zIndex: 10,
          background: 'rgba(5,7,12,0.92)', padding: '8px 10px', borderRadius: 4,
          fontSize: 10, fontFamily: 'JetBrains Mono, monospace',
          minWidth: 160, border: '1px solid rgba(168,85,247,0.3)',
        }}>
          <div style={{ color: C.gold, fontWeight: 700, marginBottom: 4 }}>SNIPER DASH</div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#22c55e' }}>BULL</span>
            <span style={{ color: '#22c55e', fontWeight: 700 }}>{(sniperScore as any).bull_pct}%</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#ef4444' }}>BEAR</span>
            <span style={{ color: '#ef4444', fontWeight: 700 }}>{(sniperScore as any).bear_pct}%</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
            <span style={{ color: '#94a3b8' }}>BIAS</span>
            <span style={{
              color: (sniperScore as any).bias?.includes('BULL') ? '#22c55e' : '#ef4444',
              fontWeight: 700,
            }}>{(sniperScore as any).bias}</span>
          </div>
          {sniperSignal && (
            <div style={{
              marginTop: 6, paddingTop: 6, borderTop: '1px solid rgba(168,85,247,0.3)',
              color: sniperSignal.direction === 'BULLISH' ? '#22d3ee' : '#fbbf24',
              fontWeight: 700,
            }}>
              ▶ {sniperSignal.label} @ {(sniperSignal.price as number)?.toFixed(2)}
            </div>
          )}
        </div>
      )}

      {/* Timeframe selector */}
      <div style={{
        position: 'absolute', top: 8, right: 8, zIndex: 10,
        display: 'flex', gap: 2,
      }}>
        {TIMEFRAMES.map(tf => (
          <button
            key={tf}
            onClick={() => handleTfChange(tf)}
            style={{
              padding: '4px 8px',
              background: localTf === tf ? C.gold : 'transparent',
              color: localTf === tf ? '#000' : '#94a3b8',
              border: '1px solid',
              borderColor: localTf === tf ? C.gold : 'rgba(255,255,255,0.1)',
              borderRadius: 3,
              fontSize: 10,
              fontFamily: 'JetBrains Mono, monospace',
              cursor: 'pointer',
            }}
          >
            {tf}
          </button>
        ))}
      </div>

      {/* Loading overlay */}
      {loading && (
        <div style={{
          position: 'absolute', inset: 0, display: 'flex',
          alignItems: 'center', justifyContent: 'center',
          background: 'rgba(5,7,12,0.8)', zIndex: 20,
        }}>
          <span style={{ color: C.gold, fontFamily: 'JetBrains Mono' }}>LOADING...</span>
        </div>
      )}

      {/* Chart container */}
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />

      {/* Legend */}
      <div style={{
        position: 'absolute', bottom: 8, left: 8, zIndex: 10,
        display: 'flex', gap: 12, flexWrap: 'wrap',
        background: 'rgba(5,7,12,0.85)', padding: '4px 8px', borderRadius: 4,
        fontSize: 9, fontFamily: 'JetBrains Mono',
      }}>
        <LegendItem color={C.OB_BULL} label="OB Bull" />
        <LegendItem color={C.OB_BEAR} label="OB Bear" />
        <LegendItem color={C.FVG_BULL} label="FVG Bull" />
        <LegendItem color={C.FVG_BEAR} label="FVG Bear" />
        <LegendItem color={C.SR} label="S/R" />
        <LegendItem color={C.SWING} label="Swing" />
        <LegendItem color={C.LIQUIDITY} label="Liq" />
        <LegendItem color={C.BOS} label="BOS" />
        <LegendItem color={C.BREAKOUT} label="Break" />
      </div>
    </div>
  );
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      <span style={{ width: 12, height: 12, background: color, borderRadius: 2 }} />
      <span style={{ color: '#94a3b8' }}>{label}</span>
    </span>
  );
}
