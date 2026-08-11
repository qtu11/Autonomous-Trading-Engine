'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import {
  createChart,
  CandlestickSeries,
  IChartApi,
  ISeriesApi,
  CandlestickData,
  Time,
  IPriceLine,
  CrosshairMode,
} from 'lightweight-charts';
import type { Candle, MarkupResponse } from '@/lib/api';

// Color System
const C = {
  bg: '#020305',
  bgDark: '#010102',
  grid: 'rgba(255,255,255,0.03)',
  bullish: '#22d3a0',
  bullishBright: '#10b981',
  bearish: '#f43f5e',
  bearishBright: '#ef4444',
  gold: '#D4B483',
  goldBright: '#F0D5A0',
  blue: '#3b82f6',
  purple: '#a855f7',
  cyan: '#06b6d4',
  amber: '#fbbf24',
  green: '#22c55e',
  red: '#ef4444',
  OB_BULL: 'rgba(34,211,160,0.18)',
  OB_BEAR: 'rgba(244,63,94,0.18)',
  FVG_BULL: 'rgba(59,130,246,0.25)',
  FVG_BEAR: 'rgba(236,72,153,0.25)',
  SR: 'rgba(251,191,36,0.25)',
  BREAKOUT: '#10b981',
  SWING: '#a855f7',
  LIQUIDITY: '#ef4444',
  BOS: '#fbbf24',
  EMA9: '#22c55e',
  EMA21: '#ef4444',
  VWAP: '#06b6d4',
  SNIPER_SIGNAL: '#22d3ee',
  SNIPER_SL: '#ef4444',
  SNIPER_TP: '#22c55e',
  PIVOT: '#fbbf24',
};

interface TradingChartProps {
  symbol?: string;
  timeframe?: string;
  markup?: MarkupResponse | null;
  candles?: Candle[];
  positions?: any[];
  onTimeframeChange?: (tf: string) => void;
}

const TIMEFRAMES = ['M1', 'M5', 'M15', 'H1', 'H4', 'D1'];

// FIX LỖI 1: Proper candle count per timeframe
const TIMEFRAME_CANDLES: Record<string, number> = {
  H4: 300,
  H1: 1200,
  M30: 2400,
  M15: 4800,
  M5: 14400,
  M1: 72000,
};

export default function TradingChart({
  symbol = 'XAUUSD',
  timeframe = 'M15',
  markup,
  candles: propCandles,
  positions = [],
  onTimeframeChange
}: TradingChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const bidLineRef = useRef<IPriceLine | null>(null);
  const askLineRef = useRef<IPriceLine | null>(null);
  const positionLinesRef = useRef<Map<string, IPriceLine[]>>(new Map());
  const markupObjectsRef = useRef<IPriceLine[]>([]);

  const [localTf, setLocalTf] = useState(timeframe);
  const [candles, setCandles] = useState<Candle[]>(propCandles || []);
  const [loading, setLoading] = useState(!propCandles);
  const [markupData, setMarkupData] = useState<MarkupResponse | null>(markup || null);
  const [bidPrice, setBidPrice] = useState<number | null>(null);
  const [askPrice, setAskPrice] = useState<number | null>(null);
  const [crosshairInfo, setCrosshairInfo] = useState<{ time: string; price: number } | null>(null);

  // Convert candle to timestamp
  const toTime = useCallback((candle: Candle): Time => {
    const raw = (candle as any).ts || candle.t;
    if (typeof raw === 'number') return raw as Time;
    const str = String(raw || '');
    if (str.includes('T') || str.includes('-')) {
      const d = new Date(str);
      const sec = Math.floor(d.getTime() / 1000);
      if (!isNaN(sec)) return sec as Time;
    }
    const d = new Date(str);
    const sec = Math.floor(d.getTime() / 1000);
    if (!isNaN(sec)) return sec as Time;
    return Math.floor(Date.now() / 1000) as Time;
  }, []);

  // Clear all markup price lines
  const clearMarkup = useCallback(() => {
    if (!candleSeriesRef.current) return;
    markupObjectsRef.current.forEach(line => {
      try { candleSeriesRef.current!.removePriceLine(line); } catch { }
    });
    markupObjectsRef.current = [];
  }, []);

  // Initialize Chart
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: C.bg },
        textColor: '#94a3b8',
        fontFamily: 'JetBrains Mono',
        fontSize: 10,
      },
      grid: {
        vertLines: { color: C.grid, style: 1 },
        horzLines: { color: C.grid, style: 1 },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: 'rgba(212,175,131,0.5)',
          labelBackgroundColor: C.gold,
          width: 1,
          style: 2,
          labelVisible: true,
        },
        horzLine: {
          color: 'rgba(212,175,131,0.5)',
          labelBackgroundColor: C.gold,
          width: 1,
          style: 2,
          labelVisible: true,
        },
      },
      rightPriceScale: {
        borderColor: 'rgba(255,255,255,0.08)',
        scaleMargins: { top: 0.08, bottom: 0.15 },
        autoScale: true,
      },
      timeScale: {
        borderColor: 'rgba(255,255,255,0.08)',
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 5,
        barSpacing: 6,
        minBarSpacing: 2,
        fixLeftEdge: false,
        fixRightEdge: false,
        rightBarStaysOnScroll: true,
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: true,
      },
      handleScale: {
        axisPressedMouseMove: true,
        mouseWheel: true,
        pinch: true,
      },
      autoSize: true,
    } as any);

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: C.bullish,
      downColor: C.bearish,
      borderUpColor: C.bullish,
      borderDownColor: C.bearish,
      wickUpColor: C.bullish,
      wickDownColor: C.bearish,
      priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;

    // Crosshair handler
    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.point) {
        setCrosshairInfo(null);
        return;
      }
      const price = param.seriesData.get(candleSeries);
      if (price && typeof price === 'object' && 'value' in price) {
        const d = new Date(Number(param.time) * 1000);
        setCrosshairInfo({
          time: d.toISOString(),
          price: (price as any).value,
        });
      }
    });

    // Resize
    const handleResize = () => {
      if (containerRef.current && chart) {
        chart.applyOptions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight
        });
      }
    };
    window.addEventListener('resize', handleResize);
    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(containerRef.current);

    return () => {
      window.removeEventListener('resize', handleResize);
      resizeObserver.disconnect();
      chart.remove();
    };
  }, []);

  // Update candles - FIX LỖI 1: Show all candles, proper zoom
  useEffect(() => {
    if (!candleSeriesRef.current || !candles.length) return;

    // Clear existing markup when candles change
    clearMarkup();

    // Build candle data
    const chartData: CandlestickData<Time>[] = [];
    candles.forEach(c => {
      const t = toTime(c) as number;
      if (!isNaN(t) && t > 0) {
        chartData.push({
          time: t as Time,
          open: Number(c.o),
          high: Number(c.h),
          low: Number(c.l),
          close: Number(c.c),
        });
      }
    });

    if (!chartData.length) return;

    // Sort by time ascending
    chartData.sort((a, b) => (a.time as number) - (b.time as number));

    candleSeriesRef.current.setData(chartData);

    // FIX: Scroll to show latest candles properly
    try {
      const lastIdx = chartData.length - 1;
      const visibleCount = Math.min(200, chartData.length); // Show ~200 candles visible
      const fromIdx = Math.max(0, lastIdx - visibleCount + 1);
      const fromTs = chartData[fromIdx].time as number;
      const toTs = chartData[lastIdx].time as number;
      chartRef.current?.timeScale().setVisibleRange({
        from: fromTs as any,
        to: toTs as any
      });
    } catch {
      chartRef.current?.timeScale().fitContent();
    }
  }, [candles, toTime, clearMarkup]);

  // Update Bid/Ask
  useEffect(() => {
    if (!candleSeriesRef.current) return;

    if (bidLineRef.current) {
      try { candleSeriesRef.current.removePriceLine(bidLineRef.current); } catch { }
      bidLineRef.current = null;
    }
    if (askLineRef.current) {
      try { candleSeriesRef.current.removePriceLine(askLineRef.current); } catch { }
      askLineRef.current = null;
    }

    if (bidPrice !== null) {
      try {
        bidLineRef.current = candleSeriesRef.current.createPriceLine({
          price: bidPrice,
          color: C.cyan,
          lineWidth: 1,
          lineStyle: 0,
          axisLabelVisible: true,
          title: 'BID',
        });
      } catch { }
    }

    if (askPrice !== null) {
      try {
        askLineRef.current = candleSeriesRef.current.createPriceLine({
          price: askPrice,
          color: C.amber,
          lineWidth: 1,
          lineStyle: 0,
          axisLabelVisible: true,
          title: 'ASK',
        });
      } catch { }
    }
  }, [bidPrice, askPrice]);

  // Update positions
  useEffect(() => {
    if (!candleSeriesRef.current) return;
    const series = candleSeriesRef.current;

    positionLinesRef.current.forEach((lines) => {
      lines.forEach(line => {
        try { series.removePriceLine(line); } catch { }
      });
    });
    positionLinesRef.current.clear();

    positions.forEach((pos: any) => {
      const lines: IPriceLine[] = [];
      const isBuy = pos.type === 'BUY' || pos.type === 'buy';

      try {
        lines.push(series.createPriceLine({
          price: pos.openPrice || pos.entry,
          color: isBuy ? C.bullish : C.bearish,
          lineWidth: 2,
          lineStyle: 0,
          axisLabelVisible: true,
          title: `${pos.type} @ ${(pos.openPrice || pos.entry)?.toFixed(2)}`,
        }));
      } catch { }

      if (pos.sl) {
        try {
          lines.push(series.createPriceLine({
            price: pos.sl,
            color: C.red,
            lineWidth: 2,
            lineStyle: 2,
            axisLabelVisible: true,
            title: `SL @ ${pos.sl.toFixed(2)}`,
          }));
        } catch { }
      }

      if (pos.tp) {
        try {
          lines.push(series.createPriceLine({
            price: pos.tp,
            color: C.green,
            lineWidth: 2,
            lineStyle: 2,
            axisLabelVisible: true,
            title: `TP @ ${pos.tp.toFixed(2)}`,
          }));
        } catch { }
      }

      positionLinesRef.current.set(pos.id || pos.ticket, lines);
    });
  }, [positions]);

  // FIX LỖI 2: Proper markup rendering for all method types
  const renderMarkup = useCallback(() => {
    if (!chartRef.current || !candleSeriesRef.current || !markupData?.objects?.length) return;
    clearMarkup();

    const series = candleSeriesRef.current;

    // Zone types that need top+bottom lines
    const zoneTypes = new Set([
      'OB', 'BREAKER', 'MITIGATION', 'REJECTION', 'FVG', 'iFVG', 'OTE', 'ASIAN', 'PD',
      'SUPPLY_DEMAND', 'SUPPORT', 'RESISTANCE', 'SR', 'TRENDLINE', 'UN', 'CHANNEL',
      'RANGE', 'VOLUME_IMBALANCE', 'VOID', 'BPR', 'DEALING_RANGE', 'INDUCEMENT',
      'CHART_PATTERN', 'JUDAS_SWING', 'UNICORN', 'PO3', 'AMD', 'SESSION_HL',
      'PDH_PDL', 'WEEKLY_MONTHLY_HL', 'SMT_DIVERGENCE', 'SILVER_BULLET', 'TURTLE_SOUP',
      'PIVOT', 'PDH', 'PDL', 'KILLZONE', 'EQUILIBRIUM', 'LIQUIDITY_POOL',
    ]);

    // Single-price types
    const singlePriceTypes = new Set([
      'EMA', 'EMA_RIBBON', 'VWAP', 'ADX', 'MACD_LINE', 'RSI_LEVEL',
      'SNIPER_SIGNAL', 'SNIPER_SL', 'SNIPER_TP1', 'SNIPER_TP2', 'SNIPER_TP3',
      'SNIPER_TP4', 'SNIPER_TP5', 'SNIPER_SCORE', 'SNIPER_DASH',
      'BSL', 'SSL', 'EQH', 'EQL', 'LIQUIDITY', 'SWING', 'BOS', 'CHoCH', 'MSS',
      'TREND', 'PULLBACK', 'RETEST', 'BREAKOUT', 'FAKE_BREAKOUT', 'PATTERN',
    ]);

    // Color mapping
    const getColor = (m: any) => {
      const isBullish = m.direction === 'BULLISH';
      switch (m.type) {
        case 'EMA': return m.label === 'EMA9' ? C.EMA9 : C.EMA21;
        case 'VWAP': return C.VWAP;
        case 'SNIPER_SIGNAL': return C.SNIPER_SIGNAL;
        case 'SNIPER_SL': return C.SNIPER_SL;
        case 'SNIPER_TP1': case 'SNIPER_TP2': case 'SNIPER_TP3': case 'SNIPER_TP4': case 'SNIPER_TP5':
          return C.SNIPER_TP;
        case 'BOS': case 'CHoCH': case 'MSS': return C.BOS;
        case 'SWING': return C.SWING;
        case 'LIQUIDITY': case 'LIQUIDITY_POOL': case 'BSL': case 'SSL': case 'EQH': case 'EQL':
          return C.LIQUIDITY;
        case 'KILLZONE': return '#a855f7';
        case 'PIVOT': case 'PDH': case 'PDL': return C.PIVOT;
        case 'SUPPLY_DEMAND': return isBullish ? C.bullish : C.bearish;
        case 'OB': case 'BREAKER': case 'MITIGATION': case 'REJECTION':
          return isBullish ? C.green : C.red;
        case 'FVG': case 'iFVG': return isBullish ? C.blue : C.purple;
        case 'TREND': return isBullish ? C.bullish : C.bearish;
        case 'ASIAN': case 'OTE': case 'PD': return C.amber;
        default: return isBullish ? C.bullish : C.bearish;
      }
    };

    // Render all markup objects
    markupData.objects.forEach((m: any) => {
      try {
        // Zone types: draw top + bottom lines
        if (zoneTypes.has(m.type) && typeof m.top === 'number' && typeof m.bottom === 'number' && m.top !== m.bottom) {
          const color = getColor(m);
          const lo = Math.min(m.top, m.bottom);
          const hi = Math.max(m.top, m.bottom);

          const topLine = series.createPriceLine({
            price: hi,
            color: color,
            lineWidth: 1,
            lineStyle: 2,
            axisLabelVisible: true,
            title: `${m.label || m.type} ▲`,
          });

          const bottomLine = series.createPriceLine({
            price: lo,
            color: color,
            lineWidth: 1,
            lineStyle: 2,
            axisLabelVisible: true,
            title: `${m.label || m.type} ▼`,
          });

          markupObjectsRef.current.push(topLine, bottomLine);
          return;
        }

        // Single price types
        if (singlePriceTypes.has(m.type) && typeof m.price === 'number') {
          const color = getColor(m);
          let lineWidth = 1;
          let lineStyle = 0;

          if (m.type === 'SNIPER_SIGNAL') { lineWidth = 3; lineStyle = 0; }
          if (m.type.includes('SL') || m.type.includes('TP')) { lineStyle = 2; }

          const line = series.createPriceLine({
            price: m.price,
            color,
            lineWidth: lineWidth as 1 | 2 | 3,
            lineStyle: lineStyle as 0 | 1 | 2 | 3 | 4,
            axisLabelVisible: true,
            title: m.label || m.type,
          });
          markupObjectsRef.current.push(line);
        }
      } catch { }
    });
  }, [markupData, clearMarkup]);

  useEffect(() => { renderMarkup(); }, [renderMarkup]);

  // Fetch data with proper candle count - FIX LỖI 1
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const count = TIMEFRAME_CANDLES[localTf] || 4800;
      const res = await fetch(`/api/market?symbol=${encodeURIComponent(symbol)}&tf=${encodeURIComponent(localTf)}&count=${count}`);
      const data = await res.json();
      if (data.candles) setCandles(data.candles);
      if (data.markup) setMarkupData(data.markup);
      if (data.bid) setBidPrice(data.bid);
      if (data.ask) setAskPrice(data.ask);
    } catch (err) {
      console.error('Chart data fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [symbol, localTf]);

  useEffect(() => {
    if (!propCandles) {
      fetchData();
      const interval = setInterval(fetchData, 1000);
      return () => clearInterval(interval);
    }
  }, [symbol, localTf, propCandles, fetchData]);

  // Zoom functions
  const handleZoomIn = useCallback(() => {
    const chart = chartRef.current;
    const timeScale = chart?.timeScale();
    if (!timeScale) return;
    const range = timeScale.getVisibleLogicalRange();
    if (!range) return;
    const logicalRange = (range.to as number) - (range.from as number);
    timeScale.setVisibleLogicalRange({
      from: (range.from as number) + logicalRange * 0.15,
      to: (range.to as number) - logicalRange * 0.15,
    });
  }, []);

  const handleZoomOut = useCallback(() => {
    const chart = chartRef.current;
    const timeScale = chart?.timeScale();
    if (!timeScale) return;
    const range = timeScale.getVisibleLogicalRange();
    if (!range) return;
    const logicalRange = (range.to as number) - (range.from as number);
    timeScale.setVisibleLogicalRange({
      from: Math.max(0, (range.from as number) - logicalRange * 0.3),
      to: (range.to as number) + logicalRange * 0.3,
    });
  }, []);

  const handleZoomFit = useCallback(() => {
    chartRef.current?.timeScale().fitContent();
  }, []);

  const handleShowAll = useCallback(() => {
    if (!chartRef.current || !candles.length) return;
    const chartData: CandlestickData<Time>[] = [];
    candles.forEach(c => {
      const t = toTime(c) as number;
      if (!isNaN(t) && t > 0) {
        chartData.push({
          time: t as Time,
          open: Number(c.o),
          high: Number(c.h),
          low: Number(c.l),
          close: Number(c.c),
        });
      }
    });
    if (chartData.length > 0) {
      const fromTs = chartData[0].time as number;
      const toTs = chartData[chartData.length - 1].time as number;
      chartRef.current?.timeScale().setVisibleRange({ from: fromTs as any, to: toTs as any });
    }
  }, [candles, toTime]);

  const handleTfChange = useCallback((tf: string) => {
    setLocalTf(tf);
    onTimeframeChange?.(tf);
  }, [onTimeframeChange]);

  // Update markup from props
  useEffect(() => {
    if (markup) setMarkupData(markup);
  }, [markup]);

  // Update candles from props
  useEffect(() => {
    if (propCandles) setCandles(propCandles);
  }, [propCandles]);

  // Derived state
  const sniperScore = markupData?.objects?.find((o: any) => o.type === 'SNIPER_SCORE');
  const confluence = (markupData as any)?.confluence;

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      {/* Toolbar */}
      <div style={{
        position: 'absolute', top: 10, left: 10, zIndex: 10,
        display: 'flex', gap: 6, alignItems: 'center',
        background: 'linear-gradient(135deg, rgba(5,7,12,0.95) 0%, rgba(2,3,5,0.98) 100%)',
        padding: '6px 12px', borderRadius: 6,
        fontSize: 10, fontFamily: '"JetBrains Mono", monospace',
        border: '1px solid rgba(255,255,255,0.06)',
        backdropFilter: 'blur(12px)',
        boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
        flexWrap: 'wrap',
      }}>
        <span style={{ color: '#64748b' }}>{localTf}</span>
        <span style={{ color: 'rgba(255,255,255,0.1)' }}>|</span>
        <span style={{ color: '#94a3b8' }}>{markupData?.method || ''}</span>
        <span style={{ color: 'rgba(255,255,255,0.1)' }}>|</span>
        <span style={{ color: C.gold }}>{candles.length} candles</span>

        {bidPrice !== null && <span style={{ color: C.cyan, marginLeft: 4 }}>Bid: {bidPrice.toFixed(2)}</span>}
        {askPrice !== null && <span style={{ color: C.amber, marginLeft: 4 }}>Ask: {askPrice.toFixed(2)}</span>}

        {confluence && (
          <div style={{
            marginLeft: 8, padding: '3px 8px', borderRadius: 4,
            background: confluence.signal === 'BUY' ? 'rgba(34,197,94,0.2)' :
              confluence.signal === 'SELL' ? 'rgba(239,68,68,0.2)' : 'rgba(100,116,139,0.2)',
            border: `1px solid ${confluence.signal === 'BUY' ? C.green :
              confluence.signal === 'SELL' ? C.red : '#64748b'}`,
          }}>
            <span style={{
              color: confluence.signal === 'BUY' ? C.bullishBright :
                confluence.signal === 'SELL' ? C.bearishBright : '#94a3b8',
              fontWeight: 800
            }}>
              {confluence.signal} | score {typeof confluence.score === 'number' ? Math.round(confluence.score * 100) : confluence.score}
            </span>
          </div>
        )}
      </div>

      {/* Sniper Score Dashboard */}
      {sniperScore && (
        <div style={{
          position: 'absolute', top: 10, right: 110, zIndex: 10,
          background: 'linear-gradient(135deg, rgba(5,7,12,0.95) 0%, rgba(2,3,5,0.98) 100%)',
          padding: '8px 12px', borderRadius: 6, fontSize: 9,
          fontFamily: '"JetBrains Mono", monospace', minWidth: 150,
          border: '1px solid rgba(168,85,247,0.3)',
          backdropFilter: 'blur(12px)',
        }}>
          <div style={{ color: C.gold, fontWeight: 800, marginBottom: 6 }}>SNIPER</div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: C.bullishBright }}>BULL</span>
            <span style={{ color: C.bullishBright, fontWeight: 800 }}>{(sniperScore as any).bull_pct}%</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: C.bearishBright }}>BEAR</span>
            <span style={{ color: C.bearishBright, fontWeight: 800 }}>{(sniperScore as any).bear_pct}%</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
            <span style={{ color: '#94a3b8' }}>BIAS</span>
            <span style={{
              color: (sniperScore as any).bias?.includes('BULL') ? C.bullishBright : C.bearishBright,
              fontWeight: 800
            }}>{(sniperScore as any).bias}</span>
          </div>
        </div>
      )}

      {/* Crosshair Info */}
      {crosshairInfo && (
        <div style={{
          position: 'absolute', bottom: 35, left: 10, zIndex: 10,
          background: 'rgba(5,7,12,0.95)', padding: '4px 8px', borderRadius: 4,
          fontSize: 9, fontFamily: '"JetBrains Mono", monospace',
          border: '1px solid rgba(212,175,131,0.3)',
        }}>
          <span style={{ color: C.gold }}>Time:</span> {crosshairInfo.time}
          <span style={{ color: '#64748b', marginLeft: 10 }}>|</span>
          <span style={{ color: C.gold, marginLeft: 10 }}>Price:</span> {crosshairInfo.price.toFixed(2)}
        </div>
      )}

      {/* Timeframe Selector */}
      <div style={{ position: 'absolute', top: 10, right: 10, zIndex: 10, display: 'flex', gap: 3 }}>
        {TIMEFRAMES.map(tf => (
          <button key={tf} onClick={() => handleTfChange(tf)} style={{
            padding: '5px 10px',
            background: localTf === tf ? C.gold : 'rgba(5,7,12,0.9)',
            color: localTf === tf ? '#000' : '#94a3b8',
            border: `1px solid ${localTf === tf ? C.gold : 'rgba(255,255,255,0.1)'}`,
            borderRadius: 4, fontSize: 9,
            fontFamily: '"JetBrains Mono", monospace', fontWeight: 700, cursor: 'pointer',
          }}>
            {tf}
          </button>
        ))}
      </div>

      {/* Zoom Controls */}
      <div style={{
        position: 'absolute', bottom: 10, right: 10, zIndex: 10,
        display: 'flex', flexDirection: 'column', gap: 3,
        background: 'rgba(5,7,12,0.9)', padding: 5, borderRadius: 6,
        border: '1px solid rgba(255,255,255,0.06)',
      }}>
        <button onClick={handleZoomIn} style={zoomBtn} title="Zoom in">+</button>
        <button onClick={handleZoomOut} style={zoomBtn} title="Zoom out">-</button>
        <button onClick={() => {
          const visibleCount = Math.min(200, candles.length);
          const lastIdx = candles.length - 1;
          const chartData: CandlestickData<Time>[] = [];
          candles.forEach(c => {
            const t = toTime(c) as number;
            if (!isNaN(t) && t > 0) chartData.push({ time: t as Time, open: Number(c.o), high: Number(c.h), low: Number(c.l), close: Number(c.c) });
          });
          if (chartData.length > visibleCount) {
            const fromIdx = chartData.length - visibleCount;
            chartRef.current?.timeScale().setVisibleRange({ from: chartData[fromIdx].time as any, to: chartData[chartData.length - 1].time as any });
          }
        }} style={zoomBtn} title="200 last">200</button>
        <button onClick={handleShowAll} style={zoomBtn} title="Show ALL candles">ALL</button>
      </div>

      {/* Loading */}
      {loading && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(2,3,5,0.85)', zIndex: 20
        }}>
          <div style={{
            color: C.gold, fontFamily: '"JetBrains Mono", monospace', fontSize: 11,
            display: 'flex', alignItems: 'center', gap: 10
          }}>
            <div style={{
              width: 8, height: 8, borderRadius: '50%', background: C.gold,
              boxShadow: `0 0 10px ${C.gold}`, animation: 'livePulse 1.5s infinite'
            }} />
            LOADING {candles.length} CANDLES...
          </div>
        </div>
      )}

      {/* Chart */}
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />

      {/* Legend */}
      <div style={{
        position: 'absolute', bottom: 10, left: 10, zIndex: 10,
        display: 'flex', gap: 14, flexWrap: 'wrap',
        background: 'rgba(5,7,12,0.9)', padding: '5px 10px', borderRadius: 5,
        fontSize: 8, fontFamily: '"JetBrains Mono", monospace',
        border: '1px solid rgba(255,255,255,0.06)',
      }}>
        <LegendItem color={C.OB_BULL} label="OB Bull" />
        <LegendItem color={C.OB_BEAR} label="OB Bear" />
        <LegendItem color={C.FVG_BULL} label="FVG Bull" />
        <LegendItem color={C.FVG_BEAR} label="FVG Bear" />
        <LegendItem color={C.SR} label="S/R" />
        <LegendItem color={C.SWING} label="Swing" />
        <LegendItem color={C.BOS} label="BOS" />
        <LegendItem color={C.LIQUIDITY} label="Liq" />
        <LegendItem color={C.cyan} label="Bid" />
        <LegendItem color={C.amber} label="Ask" />
      </div>
    </div>
  );
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
      <span style={{ width: 14, height: 3, background: color, borderRadius: 2 }} />
      <span style={{ color: '#94a3b8' }}>{label}</span>
    </span>
  );
}

const zoomBtn: React.CSSProperties = {
  width: 30, height: 24,
  background: 'transparent',
  color: '#94a3b8',
  border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: 4,
  fontSize: 14,
  fontFamily: '"JetBrains Mono", monospace',
  cursor: 'pointer',
  lineHeight: 1,
};
