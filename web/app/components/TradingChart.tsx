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
import { C } from '@/lib/design-tokens';
import { parseCandleTime } from '@/lib/utils/time';

const TIMEFRAMES = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'];
// BUG FIX: M1 mặc định 40000 (khớp InpCandlesHistory của EA) — trước đây 72000
// khiến server bỏ qua cache EA (chỉ 5000) và rơi vào bridge/stub.
const TIMEFRAME_CANDLES: Record<string, number> = {
  H4: 175, H1: 700, M30: 1350, M15: 2700, M5: 8000, M1: 40000, D1: 365,
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

export default function TradingChart({
  symbol = 'XAUUSD',
  timeframe = 'M15',
  markup,
  candles: propCandles,
  positions = [],
  pendingOrders = [],
  bid,
  ask,
  onTimeframeChange
}: TradingChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const positionLinesRef = useRef<Map<string, IPriceLine[]>>(new Map());
  const pendingLinesRef = useRef<IPriceLine[]>([]);
  const aiSignalLinesRef = useRef<IPriceLine[]>([]);
  const markupObjectsRef = useRef<IPriceLine[]>([]);
  const isMountedRef = useRef(true);

  const [localTf, setLocalTf] = useState(timeframe);
  const [candles, setCandles] = useState<Candle[]>(propCandles || []);
  const [markupData, setMarkupData] = useState<MarkupResponse | null>(markup || null);
  const [bidPrice, setBidPrice] = useState<number | null>(null);
  const [askPrice, setAskPrice] = useState<number | null>(null);
  const [crosshairInfo, setCrosshairInfo] = useState<{ time: string; price: number } | null>(null);

  // Single renderMarkup (memoized) for markup effect
  const clearMarkup = useCallback(() => {
    const series = candleSeriesRef.current;
    if (!series) return;
    markupObjectsRef.current.forEach(line => {
      try { series.removePriceLine(line); } catch { /* */ }
    });
    markupObjectsRef.current = [];
  }, []);

  // PHASE 1.4: Mount guard
  useEffect(() => {
    isMountedRef.current = true;
    return () => { isMountedRef.current = false; };
  }, []);

  // Initialize chart ONCE
  useEffect(() => {
    if (!containerRef.current) return;
    const container = containerRef.current;

    const chart = createChart(container, {
      layout: {
        background: { color: C.bgMain },
        textColor: C.muted,
        fontFamily: 'JetBrains Mono',
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
        vertLines: { color: C.border, style: 1 },
        horzLines: { color: C.border, style: 1 },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: 'rgba(212,175,131,0.5)', labelBackgroundColor: C.gold, width: 1, style: 2, labelVisible: true },
        horzLine: { color: 'rgba(212,175,131,0.5)', labelBackgroundColor: C.gold, width: 1, style: 2, labelVisible: true },
      },
      rightPriceScale: {
        borderColor: C.borderHighlight,
        scaleMargins: { top: 0.08, bottom: 0.15 },
        autoScale: true,
      },
      timeScale: {
        borderColor: C.borderHighlight,
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 5,
        barSpacing: 6,
        minBarSpacing: 2,
        rightBarStaysOnScroll: true,
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: true },
      handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true },
      autoSize: true,
    } as any);

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: C.green, downColor: C.red,
      borderUpColor: C.green, borderDownColor: C.red,
      wickUpColor: C.green, wickDownColor: C.red,
      priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;

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
      chart.applyOptions({
        width: containerRef.current.clientWidth,
        height: containerRef.current.clientHeight,
      });
    };
    window.addEventListener('resize', handleResize);
    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(container);

    return () => {
      isMountedRef.current = false;
      window.removeEventListener('resize', handleResize);
      resizeObserver.disconnect();
      try { chart.remove(); } catch { /* */ }
      chartRef.current = null;
      candleSeriesRef.current = null;
    };
  }, []);

  // Update candles
  const prevChartDataRef = useRef<CandlestickData<Time>[]>([]);
  useEffect(() => {
    if (!candleSeriesRef.current) return;
    const series = candleSeriesRef.current;

    const chartData: CandlestickData<Time>[] = candles
      .map(c => ({
        time: parseCandleTime((c as any).ts || c.t) as Time,
        open: Number(c.o), high: Number(c.h), low: Number(c.l), close: Number(c.c),
      }))
      .filter(d => (d.time as number) > 0 && d.open > 0)
      .sort((a, b) => (a.time as number) - (b.time as number));

    // BUG FIX: khi đổi symbol / chưa có dữ liệu → clear chart thay vì giữ nến của
    // symbol cũ hiển thị sai trên chart mới.
    if (!chartData.length) {
      series.setData([]);
      prevChartDataRef.current = [];
      return;
    }

    // BUG FIX: real-time với 40000 nến M1 — chỉ update nến mới bằng series.update()
    // (O(1)) thay vì setData lại toàn bộ mỗi 2s (giật). lightweight-charts chỉ cho
    // update nến CUỐI hoặc append nến mới hơn — bắt đầu từ nến cuối của dữ liệu cũ.
    const prev = prevChartDataRef.current;
    let incremental = false;
    let appendedNew = false;
    if (prev.length > 0) {
      const diff = chartData.length - prev.length;
      const sameHistory = chartData[0]?.time === prev[0]?.time;
      const prevLastTime = prev[prev.length - 1]?.time as number;
      const lastTime = chartData[prev.length - 1]?.time as number;
      // BUG FIX (review): series.update() chỉ chấp nhận time >= nến cuối hiện tại.
      // Nếu server drop 1 nến (merge lệch) khiến nến cuối đổi time giữa 2 lần poll
      // thì update() sẽ throw và chart treo. Chỉ dùng incremental khi an toàn:
      //  - diff==0: chỉ khi nến cuối CÙNG time (nến đang hình thành đổi giá trị)
      //  - diff>=1: khi time các nến mới tăng dần theo nến cuối cũ.
      // Các trường hợp còn lại (nến mới nhảy cóc / bị drop) → setData redraw lại toàn bộ.
      const safeIncremental =
        sameHistory && diff >= 0 && diff <= 5 &&
        (diff >= 1
          ? lastTime >= prevLastTime
          : lastTime === prevLastTime);
      if (safeIncremental) {
        const startIdx = Math.max(0, prev.length - 1);
        for (let i = startIdx; i < chartData.length; i++) {
          series.update(chartData[i]);
        }
        appendedNew = diff >= 1;
        incremental = true;
      }
    }
    if (!incremental) {
      series.setData(chartData);
      appendedNew = true; // setData = dữ liệu mới (đổi TF/khởi tạo) → cuộn theo
    }
    prevChartDataRef.current = chartData;

    // Chỉ auto-scroll khi CÓ nến mới được thêm hoặc dữ liệu thay thế toàn bộ.
    // Khi chỉ nến cuối đang hình thành đổi giá trị (diff==0), KHÔNG scroll để
    // người dùng có thể tự pan/zoom qua 40000 nến lịch sử mà không bị giật về cuối.
    if (appendedNew) {
      try {
        const lastIdx = chartData.length - 1;
        const visibleCount = Math.min(250, chartData.length);
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

  // BUG FIX: page.tsx poll /api/market mỗi 2s nhưng KHÔNG truyền bid/ask cho chart
  // → nến có real-time nhưng đường BID/ASK không bao giờ hiện. Sync từ props:
  useEffect(() => {
    if (typeof bid === 'number' && isFinite(bid)) setBidPrice(bid);
    if (typeof ask === 'number' && isFinite(ask)) setAskPrice(ask);
  }, [bid, ask]);

  // Bid/Ask
  useEffect(() => {
    if (!candleSeriesRef.current) return;
    const series = candleSeriesRef.current;
    let bidLine: IPriceLine | null = null;
    let askLine: IPriceLine | null = null;
    if (bidPrice !== null) {
      bidLine = series.createPriceLine({ price: bidPrice, color: C.cyan, lineWidth: 1, lineStyle: 0, axisLabelVisible: true, title: 'BID' });
    }
    if (askPrice !== null) {
      askLine = series.createPriceLine({ price: askPrice, color: C.amber, lineWidth: 1, lineStyle: 0, axisLabelVisible: true, title: 'ASK' });
    }
    return () => {
      try { if (bidLine) series.removePriceLine(bidLine); } catch { /* */ }
      try { if (askLine) series.removePriceLine(askLine); } catch { /* */ }
    };
  }, [bidPrice, askPrice]);

  // Positions
  useEffect(() => {
    const series = candleSeriesRef.current;
    if (!series) return;

    // Cleanup old
    positionLinesRef.current.forEach((lines) => {
      lines.forEach(line => { try { series.removePriceLine(line); } catch { /* */ } });
    });
    positionLinesRef.current.clear();

    positions.forEach((pos: any) => {
      const lines: IPriceLine[] = [];
      const isBuy = String(pos.type || '').toUpperCase() === 'BUY';
      // BUG FIX: server lưu price_open, API chuẩn hóa thành entry/openPrice — đọc
      // đủ các tên để đường ENTRY luôn vẽ được (trước đây vẽ undefined → lỗi lặng thầm).
      const entry = Number(pos.price_open ?? pos.entry ?? pos.openPrice ?? pos.price ?? 0);
      if (entry > 0) {
        try {
          lines.push(series.createPriceLine({
            price: entry,
            color: isBuy ? C.green : C.red,
            lineWidth: 2, lineStyle: 0, axisLabelVisible: true,
            title: `${isBuy ? 'BUY' : 'SELL'}${pos.lot ?? pos.volume ? ` ${Number(pos.lot ?? pos.volume ?? 0).toFixed(2)} lot` : ''} @ ${entry.toFixed(2)}`,
          }));
        } catch { /* */ }
      }
      if (Number(pos.sl) > 0) {
        try { lines.push(series.createPriceLine({ price: Number(pos.sl), color: C.red, lineWidth: 2, lineStyle: 2, axisLabelVisible: true, title: `SL @ ${Number(pos.sl).toFixed(2)}` })); } catch { /* */ }
      }
      if (Number(pos.tp) > 0) {
        try { lines.push(series.createPriceLine({ price: Number(pos.tp), color: C.green, lineWidth: 2, lineStyle: 2, axisLabelVisible: true, title: `TP @ ${Number(pos.tp).toFixed(2)}` })); } catch { /* */ }
      }
      positionLinesRef.current.set(String(pos.id ?? pos.ticket ?? pos.positionId ?? 'pos'), lines);
    });
  }, [positions]);

  // Pending orders (BUY_LIMIT/SELL_LIMIT + SL/TP) — BUG FIX: trước đây tab ORD có
  // lệnh chờ nhưng chart không hiển thị. Giờ vẽ đường dashed ở giá entry.
  useEffect(() => {
    const series = candleSeriesRef.current;
    if (!series) return;
    pendingLinesRef.current.forEach(line => { try { series.removePriceLine(line); } catch { /* */ } });
    pendingLinesRef.current = [];

    (pendingOrders || []).forEach((o: any) => {
      const type = String(o.type || '').toUpperCase();
      const isBuy = type.startsWith('BUY');
      const price = Number(o.price ?? o.entry ?? 0);
      const color = isBuy ? C.cyan : C.amber;
      if (price > 0) {
        try {
          pendingLinesRef.current.push(series.createPriceLine({
            price, color, lineWidth: 1, lineStyle: 2, axisLabelVisible: true,
            title: `${type} @ ${price.toFixed(2)}${Number(o.volume ?? 0) > 0 ? ` (${Number(o.volume).toFixed(2)} lot)` : ''}`,
          }));
        } catch { /* */ }
      }
      if (Number(o.sl) > 0) {
        try { pendingLinesRef.current.push(series.createPriceLine({ price: Number(o.sl), color: C.red, lineWidth: 1, lineStyle: 3, axisLabelVisible: true, title: `SL @ ${Number(o.sl).toFixed(2)}` })); } catch { /* */ }
      }
      if (Number(o.tp) > 0) {
        try { pendingLinesRef.current.push(series.createPriceLine({ price: Number(o.tp), color: C.green, lineWidth: 1, lineStyle: 3, axisLabelVisible: true, title: `TP @ ${Number(o.tp).toFixed(2)}` })); } catch { /* */ }
      }
    });
  }, [pendingOrders]);

  // AI active signal preview (entry/SL/TP từ markup confluence) — hiện lệnh AI
  // đề xuất ngay trên chart trước khi auto-trade mở lệnh thật.
  useEffect(() => {
    const series = candleSeriesRef.current;
    if (!series) return;
    aiSignalLinesRef.current.forEach(line => { try { series.removePriceLine(line); } catch { /* */ } });
    aiSignalLinesRef.current = [];

    const cf: any = markupData?.confluence;
    const signal = cf?.signal;
    if (!signal || signal === 'WAIT') return;
    const entry = Number(cf?.entry ?? 0);
    const sl = Number(cf?.sl ?? 0);
    const tp = Number(cf?.tp ?? 0);
    const color = signal === 'BUY' ? C.green : C.red;
    if (entry > 0) {
      try {
        aiSignalLinesRef.current.push(series.createPriceLine({
          price: entry, color, lineWidth: 1, lineStyle: 3, axisLabelVisible: true,
          title: `AI ${signal} @ ${entry.toFixed(2)}`,
        }));
      } catch { /* */ }
    }
    if (sl > 0) {
      try { aiSignalLinesRef.current.push(series.createPriceLine({ price: sl, color: C.red, lineWidth: 1, lineStyle: 4, axisLabelVisible: true, title: `AI SL @ ${sl.toFixed(2)}` })); } catch { /* */ }
    }
    if (tp > 0) {
      try { aiSignalLinesRef.current.push(series.createPriceLine({ price: tp, color: C.green, lineWidth: 1, lineStyle: 4, axisLabelVisible: true, title: `AI TP @ ${tp.toFixed(2)}` })); } catch { /* */ }
    }
  }, [markupData]);

  // PHASE 1.4: Single, memoized renderMarkup
  const renderMarkup = useCallback(() => {
    const series = candleSeriesRef.current;
    if (!series || !markupData?.objects?.length) return;
    clearMarkup();

    const zoneTypes = new Set([
      'OB', 'BREAKER', 'MITIGATION', 'REJECTION', 'FVG', 'iFVG', 'OTE', 'ASIAN', 'PD',
      'SUPPLY_DEMAND', 'SUPPORT', 'RESISTANCE', 'SR', 'TRENDLINE', 'UN', 'CHANNEL', 'RANGE', 'VOLUME_IMBALANCE', 'VOID', 'BPR', 'DEALING_RANGE', 'INDUCEMENT', 'CHART_PATTERN', 'JUDAS_SWING', 'UNICORN', 'PO3', 'AMD', 'SESSION_HL',
      'PDH_PDL', 'WEEKLY_MONTHLY_HL', 'SMT_DIVERGENCE', 'SILVER_BULLET', 'TURTLE_SOUP', 'PIVOT', 'PDH', 'PDL', 'KILLZONE', 'EQUILIBRIUM', 'LIQUIDITY_POOL',
    ]);

    const singlePriceTypes = new Set([
      'EMA', 'EMA_RIBBON', 'VWAP', 'ADX', 'MACD_LINE', 'RSI_LEVEL',
      'SNIPER_SIGNAL', 'SNIPER_SL', 'SNIPER_TP1', 'SNIPER_TP2', 'SNIPER_TP3', 'SNIPER_TP4', 'SNIPER_TP5', 'SNIPER_SCORE', 'SNIPER_DASH',
      'BSL', 'SSL', 'EQH', 'EQL', 'LIQUIDITY', 'SWING', 'BOS', 'CHoCH', 'MSS',
      'TREND', 'PULLBACK', 'RETEST', 'BREAKOUT', 'FAKE_BREAKOUT', 'PATTERN', 'CANDLE_PATTERN',
      // Advanced + ICT objects that carry a single anchor price
      'SR', 'KILLZONE', 'DEALING_RANGE', 'INDUCEMENT', 'TURTLE_SOUP',
      'SMT_DIVERGENCE', 'SILVER_BULLET', 'EQUILIBRIUM', 'NYMO', 'AMD',
    ]);

    const markerTypes = new Set([
      'BOS', 'CHoCH', 'MSS', 'SWING', 'LIQUIDITY', 'SNIPER_SIGNAL', 'CANDLE_PATTERN', 'TREND',
    ]);

    const getColor = (m: any) => {
      const isBullish = m.direction === 'BULLISH';
      switch (m.type) {
        case 'EMA': return m.label === 'EMA9' ? C.green : C.red;
        case 'VWAP': return C.cyan;
        case 'SNIPER_SIGNAL': return C.cyan;
        case 'SNIPER_SL': return C.redBright;
        case 'SNIPER_TP1': case 'SNIPER_TP2': case 'SNIPER_TP3': case 'SNIPER_TP4': case 'SNIPER_TP5':
          return C.green;
        case 'BOS': case 'CHoCH': case 'MSS': return C.amberBright;
        case 'SWING': return C.purple;
        case 'LIQUIDITY': case 'LIQUIDITY_POOL': case 'BSL': case 'SSL': case 'EQH': case 'EQL':
          return C.redBright;
        case 'KILLZONE': return C.purple;
        case 'PIVOT': case 'PDH': case 'PDL': return C.amberBright;
        case 'SUPPLY_DEMAND': return isBullish ? C.green : C.red;
        case 'OB': case 'BREAKER': case 'MITIGATION': case 'REJECTION':
          return isBullish ? C.green : C.red;
        case 'FVG': case 'iFVG': return isBullish ? C.blue : C.purple;
        case 'TREND': return isBullish ? C.green : C.red;
        case 'CANDLE_PATTERN': return isBullish ? C.greenBright : C.redBright;
        case 'ASIAN': case 'OTE': case 'PD': return C.amberBright;
        case 'SR': case 'SUPPORT': case 'RESISTANCE': return C.amberBright;
        case 'BREAKOUT': case 'PULLBACK': case 'RETEST': case 'FAKE_BREAKOUT': return C.cyan;
        case 'PATTERN': case 'CHART_PATTERN': return C.cyan;
        case 'TURTLE_SOUP': case 'SMT_DIVERGENCE': case 'SILVER_BULLET': return C.purple;
        case 'INDUCEMENT': case 'DEALING_RANGE': case 'DEALING_CURVE': return C.amber;
        default: return isBullish ? C.green : C.red;
      }
    };        // Render zone-type objects (OB, FVG, PD, etc.)
    markupData.objects.forEach((m: any) => {
      try {
        if (zoneTypes.has(m.type) && typeof m.top === 'number' && typeof m.bottom === 'number' && m.top !== m.bottom && m.top > 0) {
          const color = getColor(m);
          const lo = Math.min(m.top, m.bottom);
          const hi = Math.max(m.top, m.bottom);
          const topLine = series.createPriceLine({ price: hi, color, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: `${m.label || m.type} \u25B2` });
          const bottomLine = series.createPriceLine({ price: lo, color, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: `${m.label || m.type} \u25BC` });
          markupObjectsRef.current.push(topLine, bottomLine);

          // Add midline for zones (OB, FVG)
          if (['OB', 'FVG', 'iFVG', 'BREAKER', 'MITIGATION'].includes(m.type)) {
            const mid = (hi + lo) / 2;
            const midLine = series.createPriceLine({ price: mid, color: color + '40', lineWidth: 1, lineStyle: 3, axisLabelVisible: false, title: '' });
            markupObjectsRef.current.push(midLine);
          }
          return;
        }

        // Render single-price type objects
        if (singlePriceTypes.has(m.type) && typeof m.price === 'number') {
          const color = getColor(m);
          let lineWidth: 1 | 2 | 3 = 1;
          let lineStyle: 0 | 1 | 2 | 3 | 4 = 0;
          if (m.type === 'SNIPER_SIGNAL') lineWidth = 3;
          if (m.type.includes('SL') || m.type.includes('TP')) lineStyle = 2;

          // Label with direction info
          let title = m.label || m.type;
          if (markerTypes.has(m.type) && m.direction) {
            const dirSymbol = m.direction === 'BULLISH' ? '\u25B2' : m.direction === 'BEARISH' ? '\u25BC' : '';
            title = `${m.type}${dirSymbol} ${m.label || ''}`;
          }

          const line = series.createPriceLine({ price: m.price, color, lineWidth, lineStyle, axisLabelVisible: true, title });
          markupObjectsRef.current.push(line);
        }
      } catch { /* */ }
    });

    // Render BOS/CHoCH/MSS markers with directional labels
    markupData.objects.forEach((m: any) => {
      try {
        if (m.type === 'BOS' || m.type === 'CHoCH' || m.type === 'MSS') {
          if (typeof m.price === 'number' && m.price > 0) {
            const color = getColor(m);
            const dirSymbol = m.direction === 'BULLISH' ? '\u25B2' : m.direction === 'BEARISH' ? '\u25BC' : '';
            const line = series.createPriceLine({
              price: m.price, color, lineWidth: 2, lineStyle: 0,
              axisLabelVisible: true,
              title: `${m.type} ${dirSymbol} ${m.label || ''}`
            });
            markupObjectsRef.current.push(line);
          }
        }

        // Swing labels (HH, HL, LH, LL)
        if (m.type === 'SWING' && m.label) {
          if (typeof m.price === 'number' && m.price > 0) {
            const color = m.label.includes('H') ? C.purple : C.amberBright;
            const line = series.createPriceLine({
              price: m.price, color, lineWidth: 1, lineStyle: 1,
              axisLabelVisible: true,
              title: `${m.label}`
            });
            markupObjectsRef.current.push(line);
          }
        }

        // Candle pattern markers (Pin Bar, Engulfing, etc.)
        if (m.type === 'CANDLE_PATTERN' && m.label) {
          if (typeof m.price === 'number' && m.price > 0) {
            const color = getColor(m);
            const line = series.createPriceLine({
              price: m.price, color, lineWidth: 3, lineStyle: 0,
              axisLabelVisible: true,
              title: `\u2605 ${m.label}`
            });
            markupObjectsRef.current.push(line);
          }
        }
      } catch { /* */ }
    });
  }, [markupData, clearMarkup]);

  // Sync markup prop with markupData state
  useEffect(() => {
    if (markup) setMarkupData(markup);
  }, [markup]);

  // PHASE 1.4: Single effect for markup
  useEffect(() => { renderMarkup(); }, [renderMarkup]);


  // PHASE 1.4: Remove duplicate fetchData (parent already provides candles via prop)
  // Only fetch if no propCandles AND no parent fetch
  useEffect(() => {
    if (propCandles && propCandles.length > 0) {
      setCandles(propCandles);
      return;
    }
    // Fallback: fetch on mount if no parent
    const fetchData = async () => {
      try {
        const count = TIMEFRAME_CANDLES[localTf] || 4800;
        const token = typeof window !== 'undefined' ? localStorage.getItem('quantai_auth_token') || '' : '';
        const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
        const res = await fetch(`/api/market?symbol=${encodeURIComponent(symbol)}&tf=${encodeURIComponent(localTf)}&count=${count}`, { headers, credentials: 'include' });

        const data = await res.json();
        if (data.candles && isMountedRef.current) setCandles(data.candles);
        if (data.markup && isMountedRef.current) setMarkupData(data.markup);
        if (data.bid !== undefined) setBidPrice(data.bid);
        if (data.ask !== undefined) setAskPrice(data.ask);
      } catch {
        // Silent: parent may be polling
      }
    };

    fetchData();
  }, [symbol, localTf, propCandles]);

  // Zoom controls
  const handleZoomIn = useCallback(() => {
    const ts = chartRef.current?.timeScale();
    if (!ts) return;
    const range = ts.getVisibleLogicalRange();
    if (!range) return;
    const lr = (range.to as number) - (range.from as number);
    ts.setVisibleLogicalRange({ from: (range.from as number) + lr * 0.15, to: (range.to as number) - lr * 0.15 });
  }, []);

  const handleZoomOut = useCallback(() => {
    const ts = chartRef.current?.timeScale();
    if (!ts) return;
    const range = ts.getVisibleLogicalRange();
    if (!range) return;
    const lr = (range.to as number) - (range.from as number);
    ts.setVisibleLogicalRange({ from: Math.max(0, (range.from as number) - lr * 0.3), to: (range.to as number) + lr * 0.3 });
  }, []);

  const handleShowAll = useCallback(() => {
    if (!chartRef.current || !candles.length) return;
    const chartData = candles.map(c => ({ time: parseCandleTime((c as any).ts || c.t) as Time })).filter(d => (d.time as number) > 0).sort((a, b) => (a.time as number) - (b.time as number));
    if (chartData.length > 0) {
      chartRef.current.timeScale().setVisibleRange({ from: chartData[0].time as any, to: chartData[chartData.length - 1].time as any });
    }
  }, [candles]);

  const handleTfChange = useCallback((tf: string) => {
    setLocalTf(tf);
    onTimeframeChange?.(tf);
  }, [onTimeframeChange]);

  const sniperScore = markupData?.objects?.find((o: any) => o.type === 'SNIPER_SCORE');
  const confluence = (markupData as any)?.confluence;

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      {/* Toolbar */}
      <div style={{
        position: 'absolute', top: 10, left: 10, zIndex: 10,
        display: 'flex', gap: 6, alignItems: 'center',
        background: C.bgGlass, padding: '6px 12px', borderRadius: 6,
        fontSize: 10, fontFamily: C.mono, border: `1px solid ${C.border}`,
        backdropFilter: 'blur(12px)', boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
        flexWrap: 'wrap',
      }}>
        <span style={{ color: C.muted }}>{localTf}</span>
        <span style={{ color: 'rgba(255,255,255,0.1)' }}>|</span>
        <span style={{ color: C.dim }}>{markupData?.method || ''}</span>
        <span style={{ color: 'rgba(255,255,255,0.1)' }}>|</span>
        <span style={{ color: C.gold }}>{candles.length} candles</span>
        {bidPrice !== null && <span style={{ color: C.cyan, marginLeft: 4 }}>Bid: {bidPrice.toFixed(2)}</span>}
        {askPrice !== null && <span style={{ color: C.amber, marginLeft: 4 }}>Ask: {askPrice.toFixed(2)}</span>}
        {confluence && (
          <div style={{
            marginLeft: 8, padding: '3px 8px', borderRadius: 4,
            background: confluence.signal === 'BUY' ? C.greenDim : confluence.signal === 'SELL' ? C.redDim : 'rgba(100,116,139,0.2)',
            border: `1px solid ${confluence.signal === 'BUY' ? C.green : confluence.signal === 'SELL' ? C.red : C.muted}`,
          }}>
            <span style={{
              color: confluence.signal === 'BUY' ? C.greenBright : confluence.signal === 'SELL' ? C.redBright : C.muted,
              fontWeight: 800
            }}>
              {confluence.signal} | score {typeof confluence.score === 'number' ? Math.round(confluence.score) : confluence.score}
            </span>
          </div>
        )}
      </div>

      {/* Sniper Score */}
      {sniperScore && (
        <div style={{
          position: 'absolute', top: 10, right: 110, zIndex: 10,
          background: C.bgGlass, padding: '8px 12px', borderRadius: 6, fontSize: 9,
          fontFamily: C.mono, minWidth: 150, border: `1px solid ${C.purple}50`,
          backdropFilter: 'blur(12px)',
        }}>
          <div style={{ color: C.gold, fontWeight: 800, marginBottom: 6 }}>SNIPER</div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: C.greenBright }}>BULL</span>
            <span style={{ color: C.greenBright, fontWeight: 800 }}>{(sniperScore as any).bull_pct}%</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: C.redBright }}>BEAR</span>
            <span style={{ color: C.redBright, fontWeight: 800 }}>{(sniperScore as any).bear_pct}%</span>
          </div>
        </div>
      )}

      {/* Crosshair Info */}
      {crosshairInfo && (
        <div style={{
          position: 'absolute', bottom: 35, left: 10, zIndex: 10,
          background: C.bgGlass, padding: '4px 8px', borderRadius: 4,
          fontSize: 9, fontFamily: C.mono, border: `1px solid ${C.gold}50`,
        }}>
          <span style={{ color: C.gold }}>Time:</span> {crosshairInfo.time}
          <span style={{ color: C.muted, marginLeft: 10 }}>|</span>
          <span style={{ color: C.gold, marginLeft: 10 }}>Price:</span> {crosshairInfo.price.toFixed(2)}
        </div>
      )}

      {/* TF Selector */}
      <div style={{ position: 'absolute', top: 10, right: 10, zIndex: 10, display: 'flex', gap: 3 }}>
        {TIMEFRAMES.map(tf => (
          <button key={tf} onClick={() => handleTfChange(tf)} style={{
            padding: '5px 10px',
            background: localTf === tf ? C.gold : C.bgGlass,
            color: localTf === tf ? '#000' : C.muted,
            border: `1px solid ${localTf === tf ? C.gold : C.borderHighlight}`,
            borderRadius: 4, fontSize: 9, fontFamily: C.mono, fontWeight: 700, cursor: 'pointer',
          }}>{tf}</button>
        ))}
      </div>

      {/* Zoom Controls */}
      <div style={{
        position: 'absolute', bottom: 10, right: 10, zIndex: 10,
        display: 'flex', flexDirection: 'column', gap: 3,
        background: C.bgGlass, padding: 5, borderRadius: 6, border: `1px solid ${C.border}`,
      }}>
        <button onClick={handleZoomIn} style={zoomBtn}>+</button>
        <button onClick={handleZoomOut} style={zoomBtn}>-</button>
        <button onClick={() => {
          const chartData = candles.map(c => ({ time: parseCandleTime((c as any).ts || c.t) as Time })).filter(d => (d.time as number) > 0).sort((a, b) => (a.time as number) - (b.time as number));
          if (chartData.length > 200) {
            chartRef.current?.timeScale().setVisibleRange({ from: chartData[chartData.length - 200].time as any, to: chartData[chartData.length - 1].time as any });
          }
        }} style={zoomBtn}>200</button>
        <button onClick={handleShowAll} style={zoomBtn}>ALL</button>
      </div>

      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />

      {/* Legend */}
      <div style={{
        position: 'absolute', bottom: 10, left: 10, zIndex: 10,
        display: 'flex', gap: 14, flexWrap: 'wrap',
        background: C.bgGlass, padding: '5px 10px', borderRadius: 5,
        fontSize: 8, fontFamily: C.mono, border: `1px solid ${C.border}`,
      }}>
        <LegendItem color="rgba(34,211,160,0.18)" label="OB Bull" />
        <LegendItem color="rgba(244,63,94,0.18)" label="OB Bear" />
        <LegendItem color="rgba(56,189,248,0.25)" label="FVG Bull" />
        <LegendItem color="rgba(168,85,247,0.25)" label="FVG Bear" />
        <LegendItem color="rgba(245,158,11,0.25)" label="S/R" />
        <LegendItem color={C.purple} label="Swing" />
        <LegendItem color={C.amberBright} label="BOS" />
        <LegendItem color={C.redBright} label="Liq" />
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
      <span style={{ color: C.muted }}>{label}</span>
    </span>
  );
}

const zoomBtn: React.CSSProperties = {
  width: 30, height: 24, background: 'transparent', color: C.muted,
  border: `1px solid ${C.borderHighlight}`, borderRadius: 4,
  fontSize: 14, fontFamily: C.mono, cursor: 'pointer', lineHeight: 1,
};
