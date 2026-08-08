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
      if (!m.price) return;

      const isBullish = m.direction === 'BULLISH';
      let color = C.gold;

      switch (m.type) {
        case 'OB':
          color = isBullish ? C.bullish : C.bearish;
          break;
        case 'FVG':
          color = isBullish ? '#3b82f6' : '#ec4899';
          break;
        case 'SR':
          color = 'rgba(251,191,36,0.7)';
          break;
        case 'SWING':
          color = C.SWING;
          break;
        case 'BOS':
        case 'CHoCH':
          color = C.BOS;
          break;
        case 'LIQUIDITY':
        case 'LIQUIDITY_POOL':
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
        case 'KILLZONE':
          color = '#a855f7';
          break;
        default:
          color = isBullish ? C.bullish : C.bearish;
      }

      if (m.price) {
        try {
          const line = series.createPriceLine({
            price: m.price,
            color: color,
            lineWidth: 1,
            lineStyle: m.type === 'SR' || m.type === 'LIQUIDITY' ? 2 : 0,
            axisLabelVisible: true,
            title: m.label || m.type.substring(0, 3),
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
        {Object.entries(legendItems).slice(0, 6).map(([key, val]) => (
          <span key={key} style={{ color: '#94a3b8', marginLeft: 8 }}>
            <span style={{ color: C.gold }}>{key}:</span> {val}
          </span>
        ))}
      </div>

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
