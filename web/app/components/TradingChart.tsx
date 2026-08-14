'use client';

import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  IChartApi,
  ISeriesApi,
  Time,
  IPriceLine,
  CrosshairMode,
  SeriesMarker,
  createSeriesMarkers,
  type CandlestickData,
} from 'lightweight-charts';
import type { Candle, MarkupResponse } from '@/lib/api';
import { C } from '@/lib/design-tokens';
import { parseCandleTime } from '@/lib/utils/time';

const TIMEFRAMES = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'];
const TIMEFRAME_CANDLES: Record<string, number> = {
  H4: 175,
  H1: 700,
  M30: 1350,
  M15: 2700,
  M5: 8000,
  M1: 40000,
  D1: 365,
};

interface TradingChartProps {
  symbol?: string;
  timeframe?: string;
  markup?: MarkupResponse | null;
  candles?: Candle[];
  positions?: any[];
  pendingOrders?: any[];
  bid?: number;
  ask?: number;
  onTimeframeChange?: (tf: string) => void;
}

interface SvgBox {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  fill: string;
  stroke: string;
  label: string;
  direction: 'BULLISH' | 'BEARISH';
  originWidth?: number;
  originFill?: string;
  volumeLabel?: string;
  dottedLineX2?: number;
}

interface SvgSegment {
  id: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  color: string;
  label: string;
  level?: string;
}

interface SvgFibLevel {
  id: string;
  y: number;
  color: string;
  label: string;
  price: number;
}

export default function TradingChart({
  symbol = 'XAUUSD',
  timeframe = 'M15',
  markup,
  candles: propCandles,
  positions = [],
  pendingOrders = [],
  bid,
  ask,
  onTimeframeChange,
}: TradingChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const ema9SeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const ema21SeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const vwapSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);

  const positionLinesRef = useRef<Map<string, IPriceLine[]>>(new Map());
  const pendingLinesRef = useRef<IPriceLine[]>([]);
  const markersPluginRef = useRef<any>(null);
  const isMountedRef = useRef(true);

  const [localTf, setLocalTf] = useState(timeframe);
  const [candles, setCandles] = useState<Candle[]>(propCandles || []);
  const [markupData, setMarkupData] = useState<MarkupResponse | null>(
    markup || null
  );
  const [bidPrice, setBidPrice] = useState<number | null>(null);
  const [askPrice, setAskPrice] = useState<number | null>(null);
  const [crosshairInfo, setCrosshairInfo] = useState<{
    time: string;
    price: number;
  } | null>(null);

  // SVG Overlay Elements calculated on pan/zoom
  const [svgBoxes, setSvgBoxes] = useState<SvgBox[]>([]);
  const [svgSegments, setSvgSegments] = useState<SvgSegment[]>([]);
  const [svgFibs, setSvgFibs] = useState<SvgFibLevel[]>([]);
  const [chartWidth, setChartWidth] = useState<number>(800);

  // Mount guard
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // 1. Initialize Lightweight-Charts
  useEffect(() => {
    if (!containerRef.current) return;
    const container = containerRef.current;

    const chart = createChart(container, {
      layout: {
        background: { color: C.bgMain },
        textColor: C.muted,
        fontFamily: 'JetBrains Mono, monospace',
        fontSize: 10,
      },
      localization: {
        locale: 'en-US',
        dateFormat: 'yyyy-MM-dd',
        timeFormatter: (time: number) => {
          const d = new Date(time * 1000);
          const day = String(d.getDate()).padStart(2, '0');
          const month = String(d.getMonth() + 1).padStart(2, '0');
          const hours = String(d.getHours()).padStart(2, '0');
          const mins = String(d.getMinutes()).padStart(2, '0');
          return `${day}/${month} ${hours}:${mins}`;
        },
      },
      grid: {
        vertLines: { color: 'rgba(255, 255, 255, 0.04)', style: 1 },
        horzLines: { color: 'rgba(255, 255, 255, 0.04)', style: 1 },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: 'rgba(212, 175, 131, 0.4)',
          labelBackgroundColor: C.gold,
          width: 1,
          style: 2,
          labelVisible: true,
        },
        horzLine: {
          color: 'rgba(212, 175, 131, 0.4)',
          labelBackgroundColor: C.gold,
          width: 1,
          style: 2,
          labelVisible: true,
        },
      },
      rightPriceScale: {
        borderColor: C.borderHighlight,
        scaleMargins: { top: 0.08, bottom: 0.12 },
        autoScale: true,
      },
      timeScale: {
        borderColor: C.borderHighlight,
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 6,
        barSpacing: 7,
        minBarSpacing: 2,
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

    // Candles Series
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#14D990',
      downColor: '#F24968',
      borderUpColor: '#14D990',
      borderDownColor: '#F24968',
      wickUpColor: '#14D990',
      wickDownColor: '#F24968',
      priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
    });

    // Fast Moving Average / Indicators Series (Clean Ribbon)
    const ema9 = chart.addSeries(LineSeries, {
      color: 'rgba(20, 217, 144, 0.65)',
      lineWidth: 1,
      crosshairMarkerVisible: false,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    const ema21 = chart.addSeries(LineSeries, {
      color: 'rgba(242, 73, 104, 0.65)',
      lineWidth: 1,
      crosshairMarkerVisible: false,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    const vwap = chart.addSeries(LineSeries, {
      color: 'rgba(0, 188, 212, 0.5)',
      lineWidth: 1,
      lineStyle: 2,
      crosshairMarkerVisible: false,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    ema9SeriesRef.current = ema9;
    ema21SeriesRef.current = ema21;
    vwapSeriesRef.current = vwap;

    setChartWidth(container.clientWidth);

    // Crosshair inspection
    chart.subscribeCrosshairMove((param) => {
      if (!isMountedRef.current) return;
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

    const handleResize = () => {
      if (!containerRef.current) return;
      const w = containerRef.current.clientWidth;
      const h = containerRef.current.clientHeight;
      chart.applyOptions({ width: w, height: h });
      setChartWidth(w);
    };

    window.addEventListener('resize', handleResize);
    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(container);

    return () => {
      isMountedRef.current = false;
      window.removeEventListener('resize', handleResize);
      resizeObserver.disconnect();
      try {
        chart.remove();
      } catch {
        /* */
      }
      chartRef.current = null;
      candleSeriesRef.current = null;
    };
  }, []);

  // 2. Sync prop candles into state
  useEffect(() => {
    if (propCandles && propCandles.length > 0) {
      setCandles(propCandles);
    }
  }, [propCandles]);

  // 3. Update Candlestick Data in Lightweight-Charts
  const prevChartDataRef = useRef<CandlestickData<Time>[]>([]);

  useEffect(() => {
    if (!candleSeriesRef.current || !candles.length) return;
    const series = candleSeriesRef.current;

    const chartData: CandlestickData<Time>[] = candles
      .map((c) => {
        const ts = parseCandleTime((c as any).ts || (c as any).timestamp || c.t);
        return {
          time: ts as Time,
          open: Number(c.o || (c as any).open),
          high: Number(c.h || (c as any).high),
          low: Number(c.l || (c as any).low),
          close: Number(c.c || (c as any).close),
        };
      })
      .filter((d) => (d.time as number) > 0 && isFinite(d.close))
      .sort((a, b) => (a.time as number) - (b.time as number));

    if (!chartData.length) return;

    const prev = prevChartDataRef.current;
    let incremental = false;
    let appendedNew = false;

    if (prev.length > 0 && chartData.length >= prev.length) {
      const diff = chartData.length - prev.length;
      if (diff === 0) {
        // Update forming candle
        const last = chartData[chartData.length - 1];
        series.update(last);
        incremental = true;
      } else if (diff === 1) {
        // New candle completed
        const last = chartData[chartData.length - 1];
        series.update(last);
        incremental = true;
        appendedNew = true;
      }
    }

    if (!incremental) {
      series.setData(chartData);
      appendedNew = true;
    }
    prevChartDataRef.current = chartData;

    if (appendedNew) {
      try {
        const lastIdx = chartData.length - 1;
        const visibleCount = Math.min(180, chartData.length);
        const fromIdx = Math.max(0, lastIdx - visibleCount + 1);
        chartRef.current?.timeScale().setVisibleRange({
          from: chartData[fromIdx].time as any,
          to: chartData[lastIdx].time as any,
        });
      } catch {
        chartRef.current?.timeScale().fitContent();
      }
    }
  }, [candles]);

  // 4. Update Indicators (EMA9, EMA21, VWAP)
  useEffect(() => {
    const aether = (markupData as any)?.aether;
    const ind = aether?.indicators;
    if (!ind) return;

    if (ema9SeriesRef.current && ind.ema9?.length) {
      try {
        ema9SeriesRef.current.setData(
          ind.ema9.map((p: any) => ({ time: p.time as Time, value: p.value }))
        );
      } catch {
        /* */
      }
    }
    if (ema21SeriesRef.current && ind.ema21?.length) {
      try {
        ema21SeriesRef.current.setData(
          ind.ema21.map((p: any) => ({ time: p.time as Time, value: p.value }))
        );
      } catch {
        /* */
      }
    }
    if (vwapSeriesRef.current && ind.vwap?.length) {
      try {
        vwapSeriesRef.current.setData(
          ind.vwap.map((p: any) => ({ time: p.time as Time, value: p.value }))
        );
      } catch {
        /* */
      }
    }
  }, [markupData]);

  // 5. Update BID & ASK Lines (Clean, single price line)
  useEffect(() => {
    if (typeof bid === 'number' && isFinite(bid)) setBidPrice(bid);
    if (typeof ask === 'number' && isFinite(ask)) setAskPrice(ask);
  }, [bid, ask]);

  useEffect(() => {
    const series = candleSeriesRef.current;
    if (!series) return;
    let bidLine: IPriceLine | null = null;
    let askLine: IPriceLine | null = null;

    if (bidPrice !== null && isFinite(bidPrice) && bidPrice > 0) {
      bidLine = series.createPriceLine({
        price: bidPrice,
        color: '#00e5ff',
        lineWidth: 1,
        lineStyle: 0,
        axisLabelVisible: true,
        title: 'BID',
      });
    }
    if (askPrice !== null && isFinite(askPrice) && askPrice > 0) {
      askLine = series.createPriceLine({
        price: askPrice,
        color: '#ffb300',
        lineWidth: 1,
        lineStyle: 0,
        axisLabelVisible: true,
        title: 'ASK',
      });
    }
    return () => {
      try {
        if (bidLine) series.removePriceLine(bidLine);
      } catch {
        /* */
      }
      try {
        if (askLine) series.removePriceLine(askLine);
      } catch {
        /* */
      }
    };
  }, [bidPrice, askPrice]);

  // 6. Open Positions & Real Pending Orders Price Lines
  useEffect(() => {
    const series = candleSeriesRef.current;
    if (!series) return;

    positionLinesRef.current.forEach((lines) => {
      lines.forEach((line) => {
        try {
          series.removePriceLine(line);
        } catch {
          /* */
        }
      });
    });
    positionLinesRef.current.clear();

    positions.forEach((pos: any) => {
      const lines: IPriceLine[] = [];
      const isBuy = String(pos.type || '').toUpperCase() === 'BUY';
      const entry = Number(
        pos.price_open ?? pos.entry ?? pos.openPrice ?? pos.price ?? 0
      );
      if (entry > 0) {
        try {
          lines.push(
            series.createPriceLine({
              price: entry,
              color: isBuy ? '#14D990' : '#F24968',
              lineWidth: 2,
              lineStyle: 0,
              axisLabelVisible: true,
              title: `${isBuy ? 'BUY' : 'SELL'}${
                pos.lot ?? pos.volume
                  ? ` ${Number(pos.lot ?? pos.volume ?? 0).toFixed(2)}`
                  : ''
              } @ ${entry.toFixed(2)}`,
            })
          );
        } catch {
          /* */
        }
      }
      if (Number(pos.sl) > 0) {
        try {
          lines.push(
            series.createPriceLine({
              price: Number(pos.sl),
              color: '#F24968',
              lineWidth: 1,
              lineStyle: 2,
              axisLabelVisible: true,
              title: `SL @ ${Number(pos.sl).toFixed(2)}`,
            })
          );
        } catch {
          /* */
        }
      }
      if (Number(pos.tp) > 0) {
        try {
          lines.push(
            series.createPriceLine({
              price: Number(pos.tp),
              color: '#14D990',
              lineWidth: 1,
              lineStyle: 2,
              axisLabelVisible: true,
              title: `TP @ ${Number(pos.tp).toFixed(2)}`,
            })
          );
        } catch {
          /* */
        }
      }
      positionLinesRef.current.set(
        String(pos.id ?? pos.ticket ?? pos.positionId ?? 'pos'),
        lines
      );
    });
  }, [positions]);

  // 7. Markers for Swings (HH, HL, LH, LL) & Buy/Sell Signals
  useEffect(() => {
    const series = candleSeriesRef.current;
    if (!series) return;

    const markers: SeriesMarker<Time>[] = [];
    const aether = (markupData as any)?.aether;

    // Aether Swings
    if (aether?.swings?.length) {
      aether.swings.forEach((s: any) => {
        if (!s.timestamp) return;
        const isHigh = s.type === 'SWING_HIGH';
        markers.push({
          time: s.timestamp as Time,
          position: isHigh ? 'aboveBar' : 'belowBar',
          color: isHigh ? '#F24968' : '#14D990',
          shape: isHigh ? 'arrowDown' : 'arrowUp',
          text: s.label || (isHigh ? 'SH' : 'SL'),
          size: 0.8,
        });
      });
    }

    // Aether UT Bot / Momentum Signals
    if (aether?.ut_signals?.length) {
      aether.ut_signals.forEach((sig: any) => {
        if (!sig.timestamp) return;
        const isBuy = sig.action === 'BUY';
        markers.push({
          time: sig.timestamp as Time,
          position: isBuy ? 'belowBar' : 'aboveBar',
          color: isBuy ? '#00e676' : '#ff1744',
          shape: isBuy ? 'arrowUp' : 'arrowDown',
          text: isBuy ? 'BUY' : 'SELL',
          size: 1.2,
        });
      });
    }

    // ICT Turtle Soup Setup Marker
    const ts = aether?.ict?.turtle_soup;
    if (ts && ts.entry) {
      const isBuy = ts.direction === 'BULLISH';
      const lastCandle = candles[candles.length - 1];
      const tsTime = lastCandle
        ? parseCandleTime(
            (lastCandle as any).ts ||
              (lastCandle as any).timestamp ||
              lastCandle.t
          )
        : null;
      if (tsTime) {
        markers.push({
          time: tsTime as Time,
          position: isBuy ? 'belowBar' : 'aboveBar',
          color: '#FFD700',
          shape: isBuy ? 'arrowUp' : 'arrowDown',
          text: `SOUP ${isBuy ? 'BUY' : 'SELL'}`,
          size: 1.4,
        });
      }
    }

    // Price Action Patterns
    if (aether?.price_action?.length) {
      aether.price_action.forEach((pa: any) => {
        if (!pa.timestamp) return;
        const isBull = pa.direction === 'BULLISH';
        markers.push({
          time: pa.timestamp as Time,
          position: isBull ? 'belowBar' : 'aboveBar',
          color: isBull ? '#00e5ff' : '#ff4081',
          shape: 'circle',
          text: pa.label,
          size: 0.6,
        });
      });
    }

    // Sort markers chronologically
    markers.sort((a, b) => (a.time as number) - (b.time as number));

    try {
      if (!markersPluginRef.current) {
        markersPluginRef.current = createSeriesMarkers(series, markers);
      } else {
        markersPluginRef.current.setMarkers(markers);
      }
    } catch {
      /* */
    }
  }, [markupData]);

  // 8. SVG Overlay Canvas Engine (Order Blocks, FVGs, BoS/CHoCH segments, Auto Fibs)
  const updateSvgOverlay = useCallback(() => {
    const chart = chartRef.current;
    const series = candleSeriesRef.current;
    if (!chart || !series) return;

    const timeScale = chart.timeScale();
    const aether = (markupData as any)?.aether;
    const w = containerRef.current?.clientWidth || 800;
    setChartWidth(w);

    const boxes: SvgBox[] = [];
    const segments: SvgSegment[] = [];
    const fibs: SvgFibLevel[] = [];

    // A. Render Order Blocks (BigBeluga / LuxAlgo Dual Box + Dotted Ray + Volume %)
    if (aether?.order_blocks?.length) {
      aether.order_blocks.forEach((ob: any, idx: number) => {
        const x1 = timeScale.timeToCoordinate(ob.ts_start as any);
        const x2 = ob.ts_end
          ? timeScale.timeToCoordinate(ob.ts_end as any)
          : w - 55;
        const yTop = series.priceToCoordinate(ob.top);
        const yBottom = series.priceToCoordinate(ob.bottom);

        if (yTop !== null && yBottom !== null) {
          const startX = x1 !== null ? x1 : 0;
          const endX = x2 !== null ? x2 : w - 55;
          const left = Math.min(startX, endX);
          const boxW = Math.max(20, Math.abs(endX - startX));
          const top = Math.min(yTop, yBottom);
          const boxH = Math.max(4, Math.abs(yBottom - yTop));
          const isBull = ob.direction === 'BULLISH';
          const originW = Math.min(40, Math.max(14, boxW * 0.25));

          boxes.push({
            id: `ob-${idx}`,
            x: left,
            y: top,
            width: boxW,
            height: boxH,
            fill: isBull ? 'rgba(20, 217, 144, 0.12)' : 'rgba(242, 73, 104, 0.12)',
            stroke: isBull ? '#14D990' : '#F24968',
            label: isBull ? 'OB Demand' : 'OB Supply',
            direction: ob.direction,
            originWidth: originW,
            originFill: isBull ? 'rgba(20, 217, 144, 0.42)' : 'rgba(242, 73, 104, 0.42)',
            volumeLabel: ob.volume_label || (ob.volume ? `${(ob.volume / 1000).toFixed(1)}K` : undefined),
            dottedLineX2: w - 10,
          });
        }
      });
    }

    // B. Render Fair Value Gaps (LuxAlgo FVGs)
    if (aether?.fvgs?.length) {
      aether.fvgs.forEach((fvg: any, idx: number) => {
        const x1 = timeScale.timeToCoordinate(fvg.ts_start as any);
        const x2 = fvg.ts_end
          ? timeScale.timeToCoordinate(fvg.ts_end as any)
          : w - 55;
        const yTop = series.priceToCoordinate(fvg.top);
        const yBottom = series.priceToCoordinate(fvg.bottom);

        if (yTop !== null && yBottom !== null) {
          const startX = x1 !== null ? x1 : 0;
          const endX = x2 !== null ? x2 : w - 55;
          const left = Math.min(startX, endX);
          const boxW = Math.max(20, Math.abs(endX - startX));
          const top = Math.min(yTop, yBottom);
          const boxH = Math.max(3, Math.abs(yBottom - yTop));
          const isBull = fvg.direction === 'BULLISH';

          boxes.push({
            id: `fvg-${idx}`,
            x: left,
            y: top,
            width: boxW,
            height: boxH,
            fill: isBull ? 'rgba(0, 188, 212, 0.12)' : 'rgba(233, 30, 99, 0.12)',
            stroke: isBull ? 'rgba(0, 188, 212, 0.6)' : 'rgba(233, 30, 99, 0.6)',
            label: isBull ? 'FVG Bull' : 'FVG Bear',
            direction: fvg.direction,
          });
        }
      });
    }

    // C. Render BoS / CHoCH Break Segments (TradingView Dotted Line + Badge)
    if (aether?.segments?.length) {
      aether.segments.forEach((seg: any, idx: number) => {
        const x1 = timeScale.timeToCoordinate(seg.ts1 as any);
        const x2 = timeScale.timeToCoordinate(seg.ts2 as any);
        const y = series.priceToCoordinate(seg.price);

        if (x1 !== null && x2 !== null && y !== null) {
          segments.push({
            id: `seg-${idx}`,
            x1,
            y1: y,
            x2,
            y2: y,
            color: seg.color || (seg.direction === 'BULLISH' ? '#14D990' : '#F24968'),
            label: seg.label || seg.type,
            level: seg.level || 'EXTERNAL',
          });
        }
      });
    }

    // D. Render ICT OTE Fibonacci Retracement & Auto Fibs
    if (aether?.auto_fibs?.levels?.length) {
      aether.auto_fibs.levels.forEach((lvl: any, idx: number) => {
        const y = series.priceToCoordinate(lvl.price);
        if (y !== null && y > 0 && y < 2000) {
          fibs.push({
            id: `fib-${idx}`,
            y,
            color: lvl.color || '#A0A5B9',
            label: lvl.label,
            price: lvl.price,
          });
        }
      });
    }

    // E. Render ICT OTE Box Zone (0.618 - 0.786 Sweet Spot)
    const ote = aether?.ict?.ote;
    if (ote && ote.ote_top && ote.ote_bottom) {
      const yTop = series.priceToCoordinate(ote.ote_top);
      const yBottom = series.priceToCoordinate(ote.ote_bottom);
      if (yTop !== null && yBottom !== null) {
        boxes.push({
          id: 'ict-ote-zone',
          x: w - 240,
          y: Math.min(yTop, yBottom),
          width: 185,
          height: Math.max(4, Math.abs(yBottom - yTop)),
          fill: 'rgba(255, 165, 0, 0.12)',
          stroke: '#FFA500',
          label: `ICT OTE (${ote.ote_sweet_spot || ''})`,
          direction: 'BULLISH',
        });
      }
    }

    setSvgBoxes(boxes);
    setSvgSegments(segments);
    setSvgFibs(fibs);
  }, [markupData]);

  // Subscribe chart pan/zoom/scroll to update SVG overlay coordinates dynamically
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    updateSvgOverlay();
    chart.timeScale().subscribeVisibleLogicalRangeChange(updateSvgOverlay);
    chart.subscribeCrosshairMove(updateSvgOverlay);

    return () => {
      try {
        chart.timeScale().unsubscribeVisibleLogicalRangeChange(updateSvgOverlay);
        chart.unsubscribeCrosshairMove(updateSvgOverlay);
      } catch {
        /* */
      }
    };
  }, [updateSvgOverlay]);

  // Sync markup prop
  useEffect(() => {
    if (markup) setMarkupData(markup);
  }, [markup]);

  // Zoom controls
  const handleZoomIn = useCallback(() => {
    const ts = chartRef.current?.timeScale();
    if (!ts) return;
    const range = ts.getVisibleLogicalRange();
    if (!range) return;
    const lr = (range.to as number) - (range.from as number);
    ts.setVisibleLogicalRange({
      from: (range.from as number) + lr * 0.15,
      to: (range.to as number) - lr * 0.15,
    });
  }, []);

  const handleZoomOut = useCallback(() => {
    const ts = chartRef.current?.timeScale();
    if (!ts) return;
    const range = ts.getVisibleLogicalRange();
    if (!range) return;
    const lr = (range.to as number) - (range.from as number);
    ts.setVisibleLogicalRange({
      from: Math.max(0, (range.from as number) - lr * 0.3),
      to: (range.to as number) + lr * 0.3,
    });
  }, []);

  const handleShowAll = useCallback(() => {
    if (!chartRef.current || !candles.length) return;
    const chartData = candles
      .map((c) => ({
        time: parseCandleTime((c as any).ts || (c as any).timestamp || c.t) as Time,
      }))
      .filter((d) => (d.time as number) > 0)
      .sort((a, b) => (a.time as number) - (b.time as number));
    if (chartData.length > 0) {
      chartRef.current.timeScale().setVisibleRange({
        from: chartData[0].time as any,
        to: chartData[chartData.length - 1].time as any,
      });
    }
  }, [candles]);

  const handleTfChange = useCallback(
    (tf: string) => {
      setLocalTf(tf);
      onTimeframeChange?.(tf);
    },
    [onTimeframeChange]
  );

  const sniper = (markupData as any)?.aether?.sniper;
  const confluence = (markupData as any)?.confluence;

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}>
      {/* Top Left Toolbar */}
      <div
        style={{
          position: 'absolute',
          top: 10,
          left: 10,
          zIndex: 10,
          display: 'flex',
          gap: 6,
          alignItems: 'center',
          background: 'rgba(15, 23, 42, 0.85)',
          padding: '6px 12px',
          borderRadius: 6,
          fontSize: 10,
          fontFamily: C.mono,
          border: `1px solid ${C.border}`,
          backdropFilter: 'blur(12px)',
          boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
          flexWrap: 'wrap',
        }}
      >
        <span style={{ color: C.gold, fontWeight: 700 }}>{symbol}</span>
        <span style={{ color: 'rgba(255,255,255,0.2)' }}>|</span>
        <span style={{ color: C.muted }}>{localTf}</span>
        <span style={{ color: 'rgba(255,255,255,0.2)' }}>|</span>
        <span style={{ color: '#00e5ff' }}>AETHER SMC</span>
        <span style={{ color: 'rgba(255,255,255,0.2)' }}>|</span>
        <span style={{ color: C.muted }}>{candles.length} bars</span>
        {bidPrice !== null && (
          <span style={{ color: '#00e5ff', marginLeft: 4 }}>
            BID: {bidPrice.toFixed(2)}
          </span>
        )}
        {askPrice !== null && (
          <span style={{ color: '#ffb300', marginLeft: 4 }}>
            ASK: {askPrice.toFixed(2)}
          </span>
        )}
        {confluence && (
          <div
            style={{
              marginLeft: 8,
              padding: '2px 8px',
              borderRadius: 4,
              background:
                confluence.signal === 'BUY'
                  ? 'rgba(20, 217, 144, 0.2)'
                  : confluence.signal === 'SELL'
                  ? 'rgba(242, 73, 104, 0.2)'
                  : 'rgba(100,116,139,0.2)',
              border: `1px solid ${
                confluence.signal === 'BUY'
                  ? '#14D990'
                  : confluence.signal === 'SELL'
                  ? '#F24968'
                  : C.muted
              }`,
            }}
          >
            <span
              style={{
                color:
                  confluence.signal === 'BUY'
                    ? '#14D990'
                    : confluence.signal === 'SELL'
                    ? '#F24968'
                    : C.muted,
                fontWeight: 800,
              }}
            >
              {confluence.signal} | score{' '}
              {typeof confluence.score === 'number'
                ? Math.round(confluence.score)
                : confluence.score}
            </span>
          </div>
        )}
      </div>

      {/* Sniper 7-Factor HUD */}
      {sniper && sniper.bull_pct !== undefined && (
        <div
          style={{
            position: 'absolute',
            top: 10,
            right: 120,
            zIndex: 10,
            background: 'rgba(15, 23, 42, 0.85)',
            padding: '6px 12px',
            borderRadius: 6,
            fontSize: 9,
            fontFamily: C.mono,
            minWidth: 140,
            border: `1px solid rgba(168, 85, 247, 0.3)`,
            backdropFilter: 'blur(12px)',
          }}
        >
          <div
            style={{
              color: '#d4af83',
              fontWeight: 800,
              marginBottom: 4,
              display: 'flex',
              justifyContent: 'space-between',
            }}
          >
            <span>SNIPER DUAL</span>
            <span
              style={{
                color:
                  sniper.bias?.includes('BULL')
                    ? '#14D990'
                    : sniper.bias?.includes('BEAR')
                    ? '#F24968'
                    : C.muted,
              }}
            >
              {sniper.bias}
            </span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#14D990' }}>BULL</span>
            <span style={{ color: '#14D990', fontWeight: 800 }}>
              {sniper.bull_pct}%
            </span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#F24968' }}>BEAR</span>
            <span style={{ color: '#F24968', fontWeight: 800 }}>
              {sniper.bear_pct}%
            </span>
          </div>
        </div>
      )}

      {/* Crosshair Tooltip */}
      {crosshairInfo && (
        <div
          style={{
            position: 'absolute',
            bottom: 35,
            left: 10,
            zIndex: 10,
            background: 'rgba(15, 23, 42, 0.85)',
            padding: '4px 8px',
            borderRadius: 4,
            fontSize: 9,
            fontFamily: C.mono,
            border: `1px solid rgba(212, 175, 131, 0.4)`,
          }}
        >
          <span style={{ color: C.gold }}>Time:</span> {crosshairInfo.time}
          <span style={{ color: C.muted, marginLeft: 10 }}>|</span>
          <span style={{ color: C.gold, marginLeft: 10 }}>Price:</span>{' '}
          {crosshairInfo.price.toFixed(2)}
        </div>
      )}

      {/* Timeframe Selector */}
      <div
        style={{
          position: 'absolute',
          top: 10,
          right: 10,
          zIndex: 10,
          display: 'flex',
          gap: 3,
        }}
      >
        {TIMEFRAMES.map((tf) => (
          <button
            key={tf}
            onClick={() => handleTfChange(tf)}
            style={{
              padding: '5px 9px',
              background: localTf === tf ? C.gold : 'rgba(15, 23, 42, 0.85)',
              color: localTf === tf ? '#000' : C.muted,
              border: `1px solid ${
                localTf === tf ? C.gold : C.borderHighlight
              }`,
              borderRadius: 4,
              fontSize: 9,
              fontFamily: C.mono,
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            {tf}
          </button>
        ))}
      </div>

      {/* Zoom Controls */}
      <div
        style={{
          position: 'absolute',
          bottom: 10,
          right: 10,
          zIndex: 10,
          display: 'flex',
          flexDirection: 'column',
          gap: 3,
          background: 'rgba(15, 23, 42, 0.85)',
          padding: 4,
          borderRadius: 6,
          border: `1px solid ${C.border}`,
        }}
      >
        <button onClick={handleZoomIn} style={zoomBtn}>
          +
        </button>
        <button onClick={handleZoomOut} style={zoomBtn}>
          -
        </button>
        <button
          onClick={() => {
            const chartData = candles
              .map((c) => ({
                time: parseCandleTime(
                  (c as any).ts || (c as any).timestamp || c.t
                ) as Time,
              }))
              .filter((d) => (d.time as number) > 0)
              .sort((a, b) => (a.time as number) - (b.time as number));
            if (chartData.length > 150) {
              chartRef.current?.timeScale().setVisibleRange({
                from: chartData[chartData.length - 150].time as any,
                to: chartData[chartData.length - 1].time as any,
              });
            }
          }}
          style={zoomBtn}
        >
          150
        </button>
        <button onClick={handleShowAll} style={zoomBtn}>
          ALL
        </button>
      </div>

      {/* ── SVG CANVAS OVERLAY (TradingView LuxAlgo OB, FVG, BoS/CHoCH, Auto Fibs) ── */}
      <svg
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          pointerEvents: 'none',
          zIndex: 2,
        }}
      >
        {/* Order Blocks & FVGs Boxes (BigBeluga / LuxAlgo Institutional Styling) */}
        {svgBoxes.map((box) => {
          const isOB = box.id.startsWith('ob-');
          const isBull = box.direction === 'BULLISH';
          const primaryCol = isBull ? '#14D990' : '#F24968';

          return (
            <g key={box.id}>
              {/* 1. Extended Projection Box */}
              <rect
                x={box.x}
                y={box.y}
                width={box.width}
                height={box.height}
                fill={box.fill}
                stroke="none"
                rx="2"
              />

              {/* 2. Solid Origin Box (BigBeluga Origin Candlestick Box) */}
              {isOB && box.originWidth && (
                <rect
                  x={box.x}
                  y={box.y}
                  width={box.originWidth}
                  height={box.height}
                  fill={box.originFill || (isBull ? 'rgba(20, 217, 144, 0.45)' : 'rgba(242, 73, 104, 0.45)')}
                  stroke={primaryCol}
                  strokeWidth="1"
                  rx="2"
                />
              )}

              {/* 3. Top/Bottom Boundary Border Line */}
              <line
                x1={box.x}
                y1={box.y}
                x2={box.x + box.width}
                y2={box.y}
                stroke={primaryCol}
                strokeWidth="1"
                strokeOpacity="0.75"
              />
              <line
                x1={box.x}
                y1={box.y + box.height}
                x2={box.x + box.width}
                y2={box.y + box.height}
                stroke={primaryCol}
                strokeWidth="1"
                strokeOpacity="0.75"
              />

              {/* 4. Dotted Projection Line to Right Edge */}
              {isOB && box.dottedLineX2 && box.dottedLineX2 > (box.x + box.width) && (
                <line
                  x1={box.x + box.width}
                  y1={box.y + box.height / 2}
                  x2={box.dottedLineX2}
                  y2={box.y + box.height / 2}
                  stroke={primaryCol}
                  strokeWidth="1"
                  strokeDasharray="2 3"
                  strokeOpacity="0.6"
                />
              )}

              {/* 5. Volume & Percentage Label on the Right (e.g. 15.155K (38%)) */}
              {isOB && box.volumeLabel && (
                <text
                  x={box.x + box.width + 6}
                  y={box.y + box.height / 2 + 3.5}
                  fill={primaryCol}
                  fontSize="8.5"
                  fontFamily="JetBrains Mono, monospace"
                  fontWeight="600"
                  opacity="0.85"
                >
                  {box.volumeLabel}
                </text>
              )}

              {/* Label inside the origin block if space permits */}
              {!isOB && (
                <text
                  x={box.x + 6}
                  y={box.y + Math.min(box.height - 2, 11)}
                  fill={primaryCol}
                  fontSize="8.5"
                  fontFamily="JetBrains Mono, monospace"
                  fontWeight="bold"
                >
                  {box.label}
                </text>
              )}
            </g>
          );
        })}

        {/* BoS & CHoCH Break Segments (TradingView BigBeluga Circular Badge + Dotted Line) */}
        {svgSegments.map((seg) => {
          const isBull = seg.color.includes('14D990') || seg.color.includes('green') || seg.color.includes('Lime');
          const badgeBg = isBull ? 'rgba(20, 217, 144, 0.15)' : 'rgba(242, 73, 104, 0.15)';

          return (
            <g key={seg.id}>
              {/* Dotted Connection Line from Break Point */}
              <line
                x1={seg.x1}
                y1={seg.y1}
                x2={seg.x2}
                y2={seg.y2}
                stroke={seg.color}
                strokeWidth="1"
                strokeDasharray="3 3"
                strokeOpacity="0.8"
              />
              {/* Circular Badge Marker at the Breakout Coordinate */}
              <circle
                cx={seg.x2}
                cy={seg.y2}
                r="7"
                fill={badgeBg}
                stroke={seg.color}
                strokeWidth="1"
              />
              <text
                x={seg.x2}
                y={seg.y2 + 2.5}
                textAnchor="middle"
                fill={seg.color}
                fontSize="6.5"
                fontFamily="JetBrains Mono, monospace"
                fontWeight="bold"
              >
                {seg.label === 'CHoCH' ? 'CH' : 'BOS'}
              </text>
            </g>
          );
        })}

        {/* Auto Fibs Retracement */}
        {svgFibs.map((fib) => (
          <g key={fib.id}>
            <line
              x1={chartWidth - 220}
              y1={fib.y}
              x2={chartWidth - 55}
              y2={fib.y}
              stroke={fib.color}
              strokeWidth="1"
              strokeDasharray="2 2"
              opacity="0.8"
            />
            <text
              x={chartWidth - 50}
              y={fib.y + 3}
              fill={fib.color}
              fontSize="8.5"
              fontFamily="JetBrains Mono, monospace"
            >
              {fib.label} ({fib.price.toFixed(2)})
            </text>
          </g>
        ))}
      </svg>

      {/* Lightweight-Charts Container */}
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />

      {/* Bottom Left Legend */}
      <div
        style={{
          position: 'absolute',
          bottom: 10,
          left: 10,
          zIndex: 10,
          display: 'flex',
          gap: 12,
          flexWrap: 'wrap',
          background: 'rgba(15, 23, 42, 0.85)',
          padding: '4px 10px',
          borderRadius: 5,
          fontSize: 8,
          fontFamily: C.mono,
          border: `1px solid ${C.border}`,
          backdropFilter: 'blur(8px)',
        }}
      >
        <LegendItem color="rgba(20, 217, 144, 0.7)" label="OB Bull" />
        <LegendItem color="rgba(242, 73, 104, 0.7)" label="OB Bear" />
        <LegendItem color="rgba(0, 188, 212, 0.7)" label="FVG Bull" />
        <LegendItem color="rgba(233, 30, 99, 0.7)" label="FVG Bear" />
        <LegendItem color="#14D990" label="BoS" />
        <LegendItem color="#F24968" label="CHoCH" />
        <LegendItem color="#00e5ff" label="EMA 9/21 Ribbon" />
        <LegendItem color="#ffb300" label="Auto Fibs" />
      </div>
    </div>
  );
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      <span
        style={{ width: 12, height: 3, background: color, borderRadius: 2 }}
      />
      <span style={{ color: C.muted }}>{label}</span>
    </span>
  );
}

const zoomBtn: React.CSSProperties = {
  width: 28,
  height: 22,
  background: 'transparent',
  color: C.muted,
  border: `1px solid ${C.borderHighlight}`,
  borderRadius: 4,
  fontSize: 13,
  fontFamily: C.mono,
  cursor: 'pointer',
  lineHeight: 1,
};
