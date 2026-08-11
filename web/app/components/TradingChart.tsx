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
  CrosshairMode
} from 'lightweight-charts';
import type { Candle, MarkupResponse } from '@/lib/api';

// ── Premium Color System ────────────────────────────────────────────────────────
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
  positions?: Position[];
  onTimeframeChange?: (tf: string) => void;
}

interface Position {
  id: string;
  type: 'BUY' | 'SELL';
  openPrice: number;
  sl: number;
  tp: number;
  lots?: number;
  profit?: number;
}

const TIMEFRAMES = ['M1', 'M5', 'M15', 'H1', 'H4', 'D1'];

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
  const [localTf, setLocalTf] = useState(timeframe);
  const [candles, setCandles] = useState<Candle[]>(propCandles || []);
  const [loading, setLoading] = useState(!propCandles);
  const [markupData, setMarkupData] = useState<MarkupResponse | null>(markup || null);
  const [bidPrice, setBidPrice] = useState<number | null>(null);
  const [askPrice, setAskPrice] = useState<number | null>(null);
  const [crosshairInfo, setCrosshairInfo] = useState<{time: string; price: number} | null>(null);

  const toTime = useCallback((candle: Candle): Time => {
    // Prefer full ISO timestamp (c.ts) over short string (c.t)
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

  // ── Initialize Chart ─────────────────────────────────────────────────────────
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
        rightOffset: 2,
        barSpacing: 4,
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
    });

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

    // Crosshair move handler
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

    // Resize handler
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

  // ── Update Candle Data ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!candleSeriesRef.current || !candles.length) return;
    
    const timeMap = new Map<number, CandlestickData<Time>>();
    candles.forEach(c => {
      const t = toTime(c) as number;
      if (!isNaN(t) && t > 0) {
        timeMap.set(t, {
          time: t as Time,
          open: Number(c.o),
          high: Number(c.h),
          low: Number(c.l),
          close: Number(c.c),
        });
      }
    });

    const chartData = Array.from(timeMap.values()).sort((a, b) => (a.time as number) - (b.time as number));

    if (!chartData.length) return;

    candleSeriesRef.current.setData(chartData);
    try {
      const lastIdx = chartData.length - 1;
      const fromIdx = Math.max(0, lastIdx - 149);
      const fromTs = chartData[fromIdx].time as number;
      const toTs = chartData[lastIdx].time as number;
      chartRef.current?.timeScale().setVisibleRange({ from: fromTs as any, to: toTs as any });
    } catch {
      chartRef.current?.timeScale().fitContent();
    }
  }, [candles, toTime]);

  // ── Update Bid/Ask Lines ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!candleSeriesRef.current) return;

    if (bidLineRef.current) {
      try { candleSeriesRef.current.removePriceLine(bidLineRef.current); } catch {}
      bidLineRef.current = null;
    }
    if (askLineRef.current) {
      try { candleSeriesRef.current.removePriceLine(askLineRef.current); } catch {}
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
      } catch {}
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
      } catch {}
    }
  }, [bidPrice, askPrice]);

  // ── Update Position Lines ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!candleSeriesRef.current) return;
    const series = candleSeriesRef.current;

    positionLinesRef.current.forEach((lines) => {
      lines.forEach(line => {
        try { series.removePriceLine(line); } catch {}
      });
    });
    positionLinesRef.current.clear();

    positions.forEach((pos) => {
      const lines: IPriceLine[] = [];
      const isBuy = pos.type === 'BUY';
      
      try {
        lines.push(series.createPriceLine({
          price: pos.openPrice,
          color: isBuy ? C.bullish : C.bearish,
          lineWidth: 2,
          lineStyle: 0,
          axisLabelVisible: true,
          title: `${pos.type} @ ${pos.openPrice.toFixed(2)}`,
        }));
      } catch {}

      try {
        lines.push(series.createPriceLine({
          price: pos.sl,
          color: C.red,
          lineWidth: 2,
          lineStyle: 2,
          axisLabelVisible: true,
          title: `SL @ ${pos.sl.toFixed(2)}`,
        }));
      } catch {}

      try {
        lines.push(series.createPriceLine({
          price: pos.tp,
          color: C.green,
          lineWidth: 2,
          lineStyle: 2,
          axisLabelVisible: true,
          title: `TP @ ${pos.tp.toFixed(2)}`,
        }));
      } catch {}

      positionLinesRef.current.set(pos.id, lines);
    });
  }, [positions]);

  // ── Render Markup ────────────────────────────────────────────────────────────
  const renderMarkup = useCallback(() => {
    if (!chartRef.current || !candleSeriesRef.current || !markupData?.objects?.length) return;
    
    const series = candleSeriesRef.current;
    const priceLineTypes = [
      'EMA', 'EMA_RIBBON', 'VWAP', 'ADX', 'MACD_LINE', 
      'SNIPER_SIGNAL', 'SNIPER_SL', 'SNIPER_TP1', 'SNIPER_TP2', 'SNIPER_TP3', 
      'SNIPER_TP4', 'SNIPER_TP5', 'OB', 'FVG', 'BSL', 'LIQUIDITY_POOL', 
      'LIQUIDITY', 'SWING', 'BOS', 'CHoCH', 'MSS', 'SUPPLY_DEMAND', 
      'KILLZONE', 'PIVOT', 'PDH', 'PDL', 'SUPPORT', 'RESISTANCE', 'SR', 'TREND'
    ];

    markupData.objects.forEach((m) => {
      if (!m.price || !priceLineTypes.includes(m.type)) return;

      const isBullish = m.direction === 'BULLISH';
      let color = C.gold;
      let lineWidth: 1 | 2 | 3 | 4 = 1;
      let lineStyle: 0 | 1 | 2 | 3 | 4 = 0;
      let title = m.label || m.type.substring(0, 8);

      switch (m.type) {
        case 'EMA': color = m.label === 'EMA9' ? C.EMA9 : C.EMA21; lineWidth = 2; title = m.label || 'EMA'; break;
        case 'VWAP': color = C.VWAP; lineWidth = 2; title = 'VWAP'; break;
        case 'SNIPER_SIGNAL': color = C.SNIPER_SIGNAL; lineWidth = 3; title = `> ${m.label}`; break;
        case 'SNIPER_SL': color = C.SNIPER_SL; lineWidth = 2; lineStyle = 2; title = m.label || 'SL'; break;
        case 'SNIPER_TP1': case 'SNIPER_TP2': case 'SNIPER_TP3': case 'SNIPER_TP4': case 'SNIPER_TP5':
          color = C.SNIPER_TP; lineWidth = m.type === 'SNIPER_TP5' ? 3 : 1; lineStyle = m.type === 'SNIPER_TP5' ? 0 : 2;
          title = m.label || m.type.replace('SNIPER_', 'TP'); break;
        case 'OB': color = isBullish ? C.bullish : C.bearish; break;
        case 'FVG': color = isBullish ? C.blue : '#ec4899'; break;
        case 'BSL': case 'LIQUIDITY_POOL': case 'LIQUIDITY': color = C.LIQUIDITY; lineStyle = 2; title = m.label || 'BSL'; break;
        case 'SWING': color = C.SWING; break;
        case 'BOS': case 'CHoCH': case 'MSS': color = C.BOS; lineWidth = 2; title = m.label || m.type; break;
        case 'SUPPLY_DEMAND': color = isBullish ? C.bullish : C.bearish; lineWidth = 2; title = m.label || (isBullish ? 'DEMAND' : 'SUPPLY'); break;
        case 'KILLZONE': color = '#a855f7'; lineStyle = 3; title = m.label || 'KZ'; break;
        case 'PIVOT': case 'PDH': case 'PDL': color = C.PIVOT; lineStyle = 2; title = m.label || m.type; break;
        case 'SUPPORT': case 'RESISTANCE': case 'SR': color = 'rgba(251,191,36,0.7)'; lineStyle = 2; title = m.label || m.type; break;
        case 'TREND': color = isBullish ? C.bullish : C.bearish; lineWidth = 2; title = isBullish ? 'UP' : 'DOWN'; break;
        default: color = isBullish ? C.bullish : C.bearish;
      }

      try {
        series.createPriceLine({
          price: m.price,
          color: color,
          lineWidth: lineWidth,
          lineStyle: lineStyle,
          axisLabelVisible: true,
          title: title,
        });
      } catch {}
    });
  }, [markupData]);

  useEffect(() => { renderMarkup(); }, [renderMarkup]);

  // ── Fetch Data ──────────────────────────────────────────────────────────────
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/market?symbol=${symbol}&tf=${localTf}`);
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
      const interval = setInterval(fetchData, 5000);
      return () => clearInterval(interval);
    }
  }, [symbol, localTf, propCandles, fetchData]);

  // ── Zoom Functions ──────────────────────────────────────────────────────────
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
    // Fit all candles across viewport - shows full 2000-candle history
    chartRef.current?.timeScale().fitContent();
  }, []);

  const handleFitContent = useCallback(() => {
    chartRef.current?.timeScale().fitContent();
  }, []);

  const handleTfChange = useCallback((tf: string) => {
    setLocalTf(tf);
    onTimeframeChange?.(tf);
  }, [onTimeframeChange]);

  // ── Derived State ────────────────────────────────────────────────────────────
  const legendItems = markupData?.advanced_counts || {};
  const sniperScore = markupData?.objects?.find((o: any) => o.type === 'SNIPER_SCORE');
  const confluence = (markupData as any)?.confluence;
  const sniperSignal = markupData?.objects?.find((o: any) => o.type === 'SNIPER_SIGNAL');

  // ── Render ────────────────────────────────────────────────────────────────
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
      }}>
        <span style={{ color: C.gold, fontWeight: 800 }}>{symbol}</span>
        <span style={{ color: '#64748b' }}>{localTf}</span>
        <span style={{ color: 'rgba(255,255,255,0.1)' }}>|</span>
        <span style={{ color: '#94a3b8' }}>{markupData?.method || ''}</span>
        
        {bidPrice !== null && (
          <span style={{ color: C.cyan, marginLeft: 8 }}>Bid: {bidPrice.toFixed(2)}</span>
        )}
        {askPrice !== null && (
          <span style={{ color: C.amber, marginLeft: 4 }}>Ask: {askPrice.toFixed(2)}</span>
        )}
        
        {confluence && (
          <div style={{
            marginLeft: 10, padding: '3px 8px', borderRadius: 4,
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
              {confluence.signal} | score {confluence.score}
            </span>
          </div>
        )}
      </div>

      {/* Sniper Dashboard */}
      {sniperScore && (
        <div style={{
          position: 'absolute', top: 10, right: 100, zIndex: 10,
          background: 'linear-gradient(135deg, rgba(5,7,12,0.95) 0%, rgba(2,3,5,0.98) 100%)',
          padding: '8px 12px', borderRadius: 6, fontSize: 9,
          fontFamily: '"JetBrains Mono", monospace', minWidth: 150,
          border: '1px solid rgba(168,85,247,0.3)',
          backdropFilter: 'blur(12px)',
          boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
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
        <button onClick={handleFitContent} style={zoomBtn} title="Fit 150 last">150</button>
        <button onClick={handleZoomFit} style={zoomBtn} title="Fit ALL candles">ALL</button>
      </div>

      {/* Loading Overlay */}
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
