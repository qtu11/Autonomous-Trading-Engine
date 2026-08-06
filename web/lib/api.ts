export interface Candle {
  t: string;
  o: number;
  h: number;
  l: number;
  c: number;
  v: number;
}

export interface TechnicalIndicators {
  data_status?: 'LIVE_VERIFIED' | 'UNAVAILABLE';
  rsi: number;
  atr: number;
  macd: string;
  stoch: string;
  ema20: number;
  ema50: number;
  ema200: number;
  volume: number;
  vol_ratio: string;
  pivot: number;
  r1: number;
  r2: number;
  s1: number;
  s2: number;
}

export interface EquityPoint {
  i: number;
  v: number;
}

export interface AccountPerformance {
  data_status?: 'LIVE_VERIFIED' | 'NO_CLOSED_TRADES' | 'UNAVAILABLE';
  sample_size?: number;
  period_days?: number;
  win_rate: string | number | null;
  profit_factor: string | number | null;
  max_drawdown: string | number | null;
  recovery_factor: string | number | null;
  best_trade: string | number | null;
  worst_trade: string | number | null;
  equity_curve?: EquityPoint[];
}

export interface AISignalData {
  primary_signal: 'BUY' | 'SELL' | 'NO_TRADE';
  confidence: string;
  win_prob?: string;
  rr_ratio?: string;
  suggested_lot?: string;
  entry_zone?: string;
  stop_loss?: string;
  take_profit?: string;
  rec_sl_pips?: string;
  rec_tp_pips?: string;
  reason_codes?: string[];
  data_status?: 'LIVE_VERIFIED' | 'STALE' | 'UNAVAILABLE';
}

export interface NewsItem {
  id?: string;
  day?: string;
  date?: string;
  time: string;
  currency?: string;
  title: string;
  impact: 'HIGH' | 'MED' | 'LOW';
  actual?: string;
  forecast?: string;
  previous?: string;
  status?: string;
  countdown?: string;
}

export interface Position {
  id: string;
  ticket?: number;
  type: 'BUY' | 'SELL';
  lot: number;
  entry: number;
  sl: number;
  tp: number;
  profit: number;
  pips: number;
}

export interface TradeHistory {
  time: string;
  type: 'BUY' | 'SELL';
  lot: number;
  symbol: string;
  price: number;
  sl: number;
  tp: number;
  pl: number;
  reason: string;
}

export interface PendingOrder {
  ticket: number;
  symbol: string;
  type: 'BUY_LIMIT' | 'SELL_LIMIT' | 'BUY_STOP' | 'SELL_STOP' | string;
  price: number;
  sl: number;
  tp: number;
  volume: number;
  expiration: string;
}

export interface LogEntry {
  ts: string;
  level: string;
  event: string;
  component: string;
  message: string;
}

export interface TodayPerformance {
  realized_pl: number;
  trades_today: number;
  wins: number;
  losses: number;
  best_trade_today: number;
  worst_trade_today: number;
}

export interface ChatMsg {
  role: 'ai' | 'user';
  text: string;
  time: string;
}

export interface SystemStatus {
  data_status?: 'LIVE_VERIFIED' | 'UNAVAILABLE';
  generated_at?: string;
  server?: string;
  mt5_connected: boolean;
  balance: number;
  equity: number;
  margin: number;
  margin_free: number;
  floating_pnl: number;
  open_positions: number;
  current_ask: number;
  current_bid: number;
  current_spread: number;
  ai_score: number;
  cpu: number;
  ram: string;
  account_id: number;
  currency: string;
  leverage: number;
  broker: string;
  margin_level: number;
  latency_ms: number;
  today_performance?: TodayPerformance;
  indicators?: TechnicalIndicators;
  performance?: AccountPerformance;
  ai_signal?: AISignalData;
  news?: NewsItem[];
}

export interface ControlCenterStatus {
  generated_at: string;
  status: 'READY' | 'BLOCKED';
  execution: { mode: string; browser_execution_enabled: boolean; execution_locked: boolean; symbol: string; magic: number; command_ttl_seconds: number };
  safeguards: { kill_switch_active: boolean; demo_armed: boolean; live_armed?: boolean; trading_enabled?: boolean; ai_auto_loop?: boolean; bridge_auth_configured: boolean; operator_auth_configured: boolean; risk_policy_execution_enabled: boolean };
  readiness: { ready: boolean; reason_code: string };
  account: { mt5_connected: boolean; trade_mode: string; identity_matches_expected: boolean; login?: number; server?: string; balance?: number; equity?: number; leverage?: number; currency?: string };
  bridge: { status: string; mt5_connected: boolean };
  risk: { profile_found: boolean; policy_version: string; risk_per_trade_fraction: number; max_daily_loss_fraction: number; max_open_positions: number; max_spread: number | null };
  command_ledger: { available: boolean; counts: Record<string, number>; last_command: { state: string; created_at: string; claimed_at: string | null; executed_at: string | null; retcode: number | null } | null };
  data_sources: { mt5: string; ai_signal: string; performance: string };
  realtime?: { ws_clients: number; ea_online: boolean; ea_last_heartbeat: string | null; calendar_status: string };
  telegram?: { bot_token: string; chat_id: string; enabled: boolean };
}

const API_BASE = process.env.NEXT_PUBLIC_ATE_API_ORIGIN || process.env.NEXT_PUBLIC_QUANTAI_API_ORIGIN || '';

export type RequestOptions = { signal?: AbortSignal };

async function readJson<T>(url: string, options?: RequestOptions): Promise<T | null> {
  try {
    const res = await fetch(url, { cache: 'no-store', signal: options?.signal });
    if (!res.ok) return null;
    return await res.json() as T;
  } catch (error) {
    return null;
  }
}

export function fetchStatus(options?: RequestOptions): Promise<SystemStatus | null> {
  return readJson<SystemStatus>(`${API_BASE}/api/status`, options);
}

export function fetchControlCenterStatus(options?: RequestOptions): Promise<ControlCenterStatus | null> {
  return readJson<ControlCenterStatus>(`${API_BASE}/api/control-center/status`, options);
}

export async function fetchMarket(symbol = 'XAUUSD', tf = 'M15', options?: RequestOptions): Promise<{ candles: Candle[]; indicators?: TechnicalIndicators } | null> {
  const data = await readJson<{ candles?: Candle[]; indicators?: TechnicalIndicators }>(
    `${API_BASE}/api/market?symbol=${encodeURIComponent(symbol)}&tf=${encodeURIComponent(tf)}`,
    options,
  );
  if (!data || !Array.isArray(data.candles)) return null;
  return { candles: data.candles, indicators: data.indicators };
}

export async function fetchPositions(options?: RequestOptions): Promise<Position[] | null> {
  const data = await readJson<unknown>(`${API_BASE}/api/positions`, options);
  if (!Array.isArray(data)) return data === null ? null : [];
  return data.map((value) => {
    const p = value as Record<string, unknown>;
    return {
      id: `#${String(p.ticket ?? p.id ?? 'unknown')}`,
      ticket: typeof p.ticket === 'number' ? p.ticket : undefined,
      type: p.type === 0 || p.type === 'BUY' ? 'BUY' : 'SELL',
      lot: Number(p.volume ?? p.lot ?? 0),
      entry: Number(p.price_open ?? p.entry ?? 0),
      sl: Number(p.sl ?? 0),
      tp: Number(p.tp ?? 0),
      profit: Number(p.pnl ?? p.profit ?? 0),
      pips: Number(p.pips ?? 0),
    };
  });
}

export async function fetchHistory(options?: RequestOptions): Promise<TradeHistory[] | null> {
  const data = await readJson<unknown>(`${API_BASE}/api/history`, options);
  return Array.isArray(data) ? data as TradeHistory[] : null;
}

export async function fetchPendingOrders(options?: RequestOptions): Promise<PendingOrder[] | null> {
  const data = await readJson<unknown>(`${API_BASE}/api/pending-orders`, options);
  return Array.isArray(data) ? data as PendingOrder[] : null;
}

export async function fetchLogs(options?: RequestOptions): Promise<LogEntry[] | null> {
  const data = await readJson<unknown>(`${API_BASE}/api/logs`, options);
  return Array.isArray(data) ? data as LogEntry[] : null;
}

export interface BrainDecision {
  decision_id: string;
  ts: string;
  strategy_version: string;
  action: string;
  confidence: number;
  entry: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  volume: number | null;
  reason_codes: string[];
  context?: Record<string, unknown>;
  status: string;
  order_ticket: number | null;
  decision_detail?: string;
}

export interface BrainEvaluation {
  decision_id: string;
  order_ticket: number;
  closed_at: string;
  exit_price: number;
  net_profit: number;
  r_multiple: number;
  outcome: string;
  exit_reason: string;
  lesson?: string;
  action?: string;
  strategy_version?: string;
}

export interface StrategyStat {
  strategy_version: string;
  status: string;
  sample_size: number;
  wins: number;
  losses: number;
  breakevens: number;
  win_rate: number | null;
  profit_factor: number | null;
  total_pnl: number;
  avg_r: number | null;
  updated_at: string;
  notes?: string;
}

export interface BrainState {
  strategies: StrategyStat[];
  recent_decisions: BrainDecision[];
  recent_evaluations: BrainEvaluation[];
  adjustments: Array<Record<string, unknown>>;
}

export function fetchBrain(options?: RequestOptions): Promise<BrainState | null> {
  return readJson<BrainState>(`${API_BASE}/api/brain`, options);
}

export interface BrainAdjustment {
  adjustment_id: string;
  decision_id: string;
  strategy_version: string;
  kind: string;
  params: Record<string, unknown>;
  reason: string;
  status: string;
  created_at: string;
  applied_at: string | null;
  result: string | null;
}

export function fetchAdjustments(options?: RequestOptions): Promise<BrainAdjustment[] | null> {
  return readJson<BrainAdjustment[]>(`${API_BASE}/api/brain/adjustments`, options);
}

export function patchAdjustment(adjustmentId: string, action: string, reason?: string): Promise<{ status: string; adjustment_id: string; action: string } | null> {
  return patchJson<{ status: string; adjustment_id: string; action: string }>(
    `${API_BASE}/api/brain/adjustments/${adjustmentId}`,
    { action, reason },
  );
}

export function executeCloseProfit(): Promise<ExecutionResponse> {
  return executeOrder('/api/orders/close-profitable');
}

export function executeCloseLosing(): Promise<ExecutionResponse> {
  return executeOrder('/api/orders/close-losing');
}

export async function fetchAIModels(options?: RequestOptions): Promise<{ models: Array<{ id: string; name: string; model: string; active: boolean }>; default: string } | null> {
  return readJson(`${API_BASE}/api/copilot/models`, options);
}

export async function sendCopilotChat(message: string, symbol = 'XAUUSD', timeframe = 'M15', modelId = 'auto'): Promise<ChatMsg | null> {
  try {
    const res = await fetch(`${API_BASE}/api/copilot/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, symbol, timeframe, model_id: modelId }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return {
      role: 'ai',
      text: data.text || 'Đã xử lý yêu cầu phân tích.',
      time: data.time || new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }),
    };
  } catch (err) {
    return null;
  }
}

export interface ExecutionResponse {
  status: 'SUCCESS' | 'ANALYSIS_ONLY' | 'REJECTED' | 'ERROR';
  message: string;
  detail?: { code?: string; execution_mode?: string; message?: string };
}

async function executeOrder(path: string, body?: Record<string, unknown>): Promise<ExecutionResponse> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      return {
        status: 'REJECTED',
        message: data?.detail?.message || data?.message || `Yêu cầu bị từ chối (${res.status}).`,
        detail: data?.detail,
      };
    }
    return data as ExecutionResponse;
  } catch {
    return { status: 'ERROR', message: 'Không thể kết nối API; không có lệnh nào được xác nhận thực thi.' };
  }
}

async function patchJson<T>(path: string, body?: Record<string, unknown>, options?: RequestOptions): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
      signal: options?.signal,
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export function executeOrderBuy(volume = 0.10): Promise<ExecutionResponse> {
  return executeOrder('/api/order/buy', { symbol: 'XAUUSD', volume });
}

export function executeOrderSell(volume = 0.10): Promise<ExecutionResponse> {
  return executeOrder('/api/order/sell', { symbol: 'XAUUSD', volume });
}

export function executeOrderCloseAll(): Promise<ExecutionResponse> {
  return executeOrder('/api/order/close_all');
}

export function executeOrderModifyTPSL(): Promise<ExecutionResponse> {
  return executeOrder('/api/order/modify_tpsl');
}

export async function triggerAIScanNow(): Promise<any> {
  try {
    const res = await fetch(`${API_BASE}/api/ai_scan_now`, { cache: 'no-store' });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    return null;
  }
}
export async function updateControlMode(mode: string): Promise<{ status: string; execution_mode?: string } | null> {
  try {
    const res = await fetch(`${API_BASE}/api/control-center/mode`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function updateControlKillSwitch(active: boolean): Promise<{ status: string; kill_switch_active?: boolean } | null> {
  try {
    const res = await fetch(`${API_BASE}/api/control-center/kill-switch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ active }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function updateControlDemoArm(armed: boolean): Promise<{ status: string; demo_armed?: boolean } | null> {
  try {
    const res = await fetch(`${API_BASE}/api/control-center/demo-arm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ armed }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function loginMT5Account(login: number, password: string, server: string): Promise<{ status: string; message?: string; account?: any; detail?: any }> {
  try {
    const res = await fetch(`${API_BASE}/api/control-center/login-mt5`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ login, password, server }),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      return { status: 'ERROR', message: data?.detail?.message || data?.message || 'Không thể đăng nhập tài khoản MT5.' };
    }
    return data;
  } catch {
    return { status: 'ERROR', message: 'Lỗi kết nối API Server khi đăng nhập MT5.' };
  }
}

export async function updateControlRisk(risk_per_trade_fraction: number, max_open_positions: number, max_spread: number): Promise<{ status: string } | null> {
  try {
    const res = await fetch(`${API_BASE}/api/control-center/risk`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ risk_per_trade_fraction, max_open_positions, max_spread }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

// ── Full trade actions ────────────────────────────────────────────────────────
export function executeOrderModifyTPSLReal(ticket: number, stopLoss: number, takeProfit: number): Promise<ExecutionResponse> {
  return executeOrder('/api/order/modify_tpsl', { ticket, stop_loss: stopLoss, take_profit: takeProfit });
}

export function executeOrderClosePosition(ticket: number): Promise<ExecutionResponse> {
  return executeOrder('/api/order/close', { ticket });
}

export function executeOrderCancelPending(orderTicket: number): Promise<ExecutionResponse> {
  return executeOrder('/api/order/cancel_pending', { order_ticket: orderTicket });
}

export async function updateAiAutoLoop(armed: boolean): Promise<{ status: string; ai_auto_loop?: boolean } | null> {
  try {
    const res = await fetch(`${API_BASE}/api/control-center/ai-loop`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ armed }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchChatHistory(): Promise<ChatMsg[] | null> {
  try {
    const res = await fetch(`${API_BASE}/api/copilot/chat/history`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

// ── Realtime WebSocket stream ─────────────────────────────────────────────────
export type StreamEvent =
  | { type: 'telemetry'; data: SystemStatus }
  | { type: 'command_update'; data: { command_id: string; action: string; state: string; retcode: number | null; order_ticket: number | null } }
  | { type: 'ai_signal'; data: { status: string; reason_codes?: string[]; command: boolean } }
  | { type: 'log'; data: Record<string, unknown> };

export interface StreamSocketHandle {
  close: () => void;
}

/**
 * Subscribe to the backend realtime stream with automatic reconnect + backoff.
 * onEvent fires for every server push; onStateChange reports connectivity.
 */
export function createStreamSocket(
  onEvent: (event: StreamEvent) => void,
  onStateChange?: (connected: boolean) => void,
): StreamSocketHandle {
  const wsBase = API_BASE.replace(/^http/, 'ws');
  const url = `${wsBase}/ws/stream`;
  let socket: WebSocket | null = null;
  let closedByUser = false;
  let attempt = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  const connect = () => {
    if (closedByUser) return;
    try {
      socket = new WebSocket(url);
    } catch {
      scheduleReconnect();
      return;
    }
    socket.onopen = () => {
      attempt = 0;
      onStateChange?.(true);
    };
    socket.onmessage = (msg) => {
      try {
        const parsed = JSON.parse(msg.data) as StreamEvent;
        onEvent(parsed);
      } catch {
        /* ignore malformed frames */
      }
    };
    socket.onclose = () => {
      onStateChange?.(false);
      scheduleReconnect();
    };
    socket.onerror = () => {
      socket?.close();
    };
  };

  const scheduleReconnect = () => {
    if (closedByUser || reconnectTimer) return;
    attempt += 1;
    const delay = Math.min(30000, 1000 * Math.pow(2, Math.min(attempt, 5)));
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, delay);
  };

  connect();

  return {
    close: () => {
      closedByUser = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      socket?.close();
    },
  };
}

export async function updateTelegramConfig(botToken: string, chatId: string, enabled = true): Promise<{ status: string; message: string } | null> {
  try {
    const res = await fetch(`${API_BASE}/api/control-center/telegram`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bot_token: botToken, chat_id: chatId, enabled }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export interface NewsAnalysisResponse {
  status: string;
  title: string;
  analysis: string;
  recommendation: 'BUY' | 'SELL' | 'HOLD';
}

export async function analyzeNewsEvent(newsItem: {
  title: string;
  impact?: string;
  actual?: string;
  forecast?: string;
  previous?: string;
  date?: string;
  time?: string;
}): Promise<NewsAnalysisResponse | null> {
  try {
    const res = await fetch(`${API_BASE}/api/news/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newsItem),
    });
    if (!res.ok) return null;
    return (await res.json()) as NewsAnalysisResponse;
  } catch {
    return null;
  }
}

export interface EconomicEvent {
  id: string;
  title: string;
  country: string;
  currency: string;
  impact: "LOW" | "MEDIUM" | "HIGH";
  datetime: string;
  forecast: string;
  previous: string;
  actual: string | null;
  unit: string;
  source: string;
  description: string;
  category: string;
  status: "upcoming" | "live" | "released";
}

export async function fetchEconomicCalendar(days = 7, country?: string, impact?: string): Promise<EconomicEvent[] | null> {
  try {
    const params = new URLSearchParams({ days: String(days) });
    if (country) params.set("country", country);
    if (impact) params.set("impact", impact);
    const res = await fetch(`${API_BASE}/api/economic-calendar?${params.toString()}`);
    if (!res.ok) return null;
    return (await res.json()) as EconomicEvent[];
  } catch {
    return null;
  }
}

export interface AIAnalysisResponse {
  status: string;
  event: {
    title: string;
    country: string;
    currency: string;
    impact: string;
    releaseTime: string;
    forecast: string;
    previous: string;
    actual: string | null;
  };
  aiExplanation: {
    whatIsIt: string;
    whyItMatters: string;
    impactOnUSD: string;
    impactOnGold: string;
  };
  historicalImpact: {
    averageGoldMove: number;
    averageDollarMove: number;
    volatility: number;
    largestSpike: number;
    winRate: number;
    sampleSize: number;
  };
  aiPrediction: {
    usdDirection: "Bullish" | "Bearish" | "Neutral";
    usdConfidence: number;
    goldDirection: "Bullish" | "Bearish" | "Neutral";
    goldConfidence: number;
  };
  tradingRecommendation: {
    recommendation: string;
    reason: string;
    pair: string;
    direction: "BUY" | "SELL" | "HOLD";
    target: string;
    stopLoss: string;
  };
  riskScore: {
    marketVolatility: number;
    liquidity: string;
    spreadExpansion: string;
    falseBreakout: string;
    newsRisk: string;
  };
  tradingStrategy: {
    beforeNews: string;
    afterRelease: string;
    entryCondition: string;
    target: string;
    stop: string;
  };
  expectedMarketReaction: {
    ifAboveForecast: string;
    ifBelowForecast: string;
    ifInLine: string;
  };
  aiConfidence: {
    predictionConfidence: number;
    dataQuality: string;
    historicalSimilarity: number;
  };
  relatedNews: string[];
  symbolImpact: Record<string, string>;
  timeline: Array<{ time: string; label: string; value?: string }>;
  aiInsight: string;
}

export async function fetchEconomicEventAnalysis(eventId: string): Promise<AIAnalysisResponse | null> {
  try {
    const res = await fetch(`${API_BASE}/api/news/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: eventId, impact: "HIGH", actual: "", forecast: "", previous: "", date: "", time: "" }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export interface AIConfig {
  active_model: string;
  custom_model_id?: string;
  gemini_api_key?: string;
  claude_api_key?: string;
  deepseek_api_key?: string;
  openai_api_key?: string;
  zplay_api_key?: string;
  grok_api_key?: string;
  qwen_api_key?: string;
  gateway_url?: string;
  gateway_key?: string;
  has_gemini_key?: boolean;
  has_claude_key?: boolean;
  has_deepseek_key?: boolean;
  has_openai_key?: boolean;
  has_zplay_key?: boolean;
  has_grok_key?: boolean;
  has_qwen_key?: boolean;
  has_gateway?: boolean;
  available_models?: Array<{ id: string; name: string; provider: string; key_type: string }>;
}

export async function fetchAIConfig(): Promise<AIConfig | null> {
  try {
    const res = await fetch(`${API_BASE}/api/control-center/ai-config`);
    if (!res.ok) return null;
    return (await res.json()) as AIConfig;
  } catch {
    return null;
  }
}

export async function updateAIConfig(payload: {
  active_model: string;
  custom_model_id?: string;
  gemini_api_key?: string;
  claude_api_key?: string;
  deepseek_api_key?: string;
  openai_api_key?: string;
  zplay_api_key?: string;
  grok_api_key?: string;
  qwen_api_key?: string;
  gateway_url?: string;
  gateway_key?: string;
}): Promise<{ status: string; message: string; active_model: string } | null> {
  try {
    const res = await fetch(`${API_BASE}/api/control-center/ai-config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}



