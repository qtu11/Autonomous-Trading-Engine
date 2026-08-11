// API client for ATE Trading Desk

const API_BASE = '';

function adminHeaders(): Record<string, string> {
  try {
    const token = localStorage.getItem('quantai_auth_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch { return {}; }
}

// Types
export interface Candle { t: string; o: number; h: number; l: number; c: number; v: number; }
export interface Position { id: string; ticket?: number; type: 'BUY' | 'SELL' | string; lot: number; entry: number; sl: number; tp: number; profit: number; pips: number; }
export interface TradeHistory { time?: string; type: 'BUY' | 'SELL' | string; lot: number; symbol: string; price?: number; sl: number; tp: number; pl: number; reason: string; }
export interface PendingOrder { ticket: number; symbol: string; type: string; price: number; sl: number; tp: number; volume: number; expiration: string; }
export interface LogEntry { ts?: string; level: string; event?: string; component?: string; message: string; }
export interface ChatMsg { role: 'ai' | 'user'; text: string; time: string; }
export interface TechnicalIndicators { rsi: number; atr: number; macd: string; stoch: string; ema20: number; ema50: number; ema200: number; volume: number; }
export interface ControlCenterStatus { generated_at: string; execution: { mode: string; browser_execution_enabled: boolean; symbol: string; }; safeguards: { kill_switch_active: boolean; demo_armed: boolean; ai_auto_loop?: boolean; trading_method?: string; }; account: { mt5_connected: boolean; login?: number; balance?: number; equity?: number; }; bridge: { mt5_connected: boolean; status: string; }; risk: { risk_per_trade_fraction: number; max_open_positions: number; }; }
export interface BrainState { strategies: Array<{ strategy_version: string; status: string; wins: number; losses: number; win_rate: number | null; total_pnl: number; }>; recent_decisions: Array<{ decision_id: string; ts: string; action: string; confidence: number; entry: number | null; stop_loss: number | null; take_profit: number | null; volume: number | null; reason_codes: string[]; status: string; order_ticket: number | null; }>; recent_evaluations: Array<{ decision_id: string; order_ticket: number; closed_at: string; exit_price: number; net_profit: number; r_multiple: number; outcome: string; exit_reason: string; }>; }
export interface BrainAdjustment { adjustment_id: string; decision_id: string; strategy_version: string; kind: string; params: Record<string, unknown>; reason: string; status: string; created_at: string; applied_at: string | null; }
export interface MarkupItem {
  label?: string; type: string; direction?: 'BULLISH' | 'BEARISH' | 'NEUTRAL'; top?: number; bottom?: number; price?: number; }
export interface MarkupResponse {
  advanced_counts?: Record<string, number>; symbol?: string; method?: string; objects: MarkupItem[]; confluence?: { score: number; direction: 'BULLISH' | 'BEARISH' | 'NEUTRAL'; signal: 'BUY' | 'SELL' | 'WAIT'; factors: Array<{ reason: string; direction: string; weight: number }>; rrr?: number | null; entry?: number | null; sl?: number | null; tp?: number | null; }; }
export interface EconomicEvent { id: string; title: string; country: string; currency: string; impact: 'LOW' | 'MEDIUM' | 'HIGH'; datetime: string; forecast: string; previous: string; actual: string | null; unit: string; source: string; description: string; category: string; status: 'upcoming' | 'live' | 'released'; }
export interface NewsAnalysisResponse { status: string; title: string; analysis: string; recommendation: 'BUY' | 'SELL' | 'HOLD'; }
export interface AIConfig { active_model: string; trading_method?: string; available_models?: Array<{ id: string; name: string; provider: string; }>; }

// HTTP helpers
async function getJson<T>(url: string): Promise<T | null> {
  try {
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) return null;
    return await res.json() as T;
  } catch { return null; }
}

async function postJson<T>(url: string, body?: Record<string, unknown>): Promise<T | null> {
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...adminHeaders() },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) return null;
    return await res.json() as T;
  } catch { return null; }
}

// API Functions
export function fetchStatus() { return getJson<any>(`${API_BASE}/api/status`); }
export function fetchControlCenterStatus() { return getJson<ControlCenterStatus>(`${API_BASE}/api/control-center/status`); }

export async function fetchMarket(symbol = 'XAUUSD', tf = 'M15') {
  const data = await getJson<{ candles?: Candle[]; markup?: MarkupResponse }>(`${API_BASE}/api/market?symbol=${encodeURIComponent(symbol)}&tf=${encodeURIComponent(tf)}`);
  if (!data || !Array.isArray(data.candles)) return null;
  return data;
}

export async function fetchPositions() {
  const data = await getJson<any[]>(`${API_BASE}/api/positions`);
  if (!Array.isArray(data)) return [];
  return data.map(p => ({
    id: `#${p.ticket || p.id || 'unknown'}`,
    ticket: typeof p.ticket === 'number' ? p.ticket : undefined,
    type: p.type === 0 || p.type === 'BUY' ? 'BUY' : 'SELL',
    lot: Number(p.volume ?? p.lot ?? 0),
    entry: Number(p.price_open ?? p.entry ?? 0),
    sl: Number(p.sl ?? 0),
    tp: Number(p.tp ?? 0),
    profit: Number(p.pnl ?? p.profit ?? 0),
    pips: Number(p.pips ?? 0),
  }));
}

export async function fetchHistory() { return getJson<TradeHistory[]>(`${API_BASE}/api/history`) || []; }
export async function fetchPendingOrders() { return getJson<PendingOrder[]>(`${API_BASE}/api/pending-orders`) || []; }
export async function fetchLogs(_?: any) { return getJson<LogEntry[]>(`${API_BASE}/api/logs`) || []; }
export function fetchBrain() { return getJson<BrainState>(`${API_BASE}/api/brain`); }
export function fetchAdjustments() { return getJson<BrainAdjustment[]>(`${API_BASE}/api/brain/adjustments`); }
export function fetchAIConfig() { return getJson<AIConfig>(`${API_BASE}/api/control-center/ai-config`); }
export function fetchEconomicCalendar(days = 7) { return getJson<EconomicEvent[]>(`${API_BASE}/api/economic-calendar?days=${days}`); }

export async function sendCopilotChat(message: string, symbol = 'XAUUSD', timeframe = 'M15') {
  return postJson<ChatMsg>(`${API_BASE}/api/copilot/chat`, { message, symbol, timeframe });
}

export async function analyzeNewsEvent(news: { title: string; impact?: string; actual?: string; forecast?: string; previous?: string; date?: string; time?: string; }) {
  return postJson<NewsAnalysisResponse>(`${API_BASE}/api/news/analyze`, news);
}

// Control actions
export async function updateControlMode(mode: string) { return postJson<{ status: string }>(`${API_BASE}/api/control-center/mode`, { mode }); }
export async function updateControlKillSwitch(active: boolean) { return postJson<{ status: string }>(`${API_BASE}/api/control-center/kill-switch`, { active }); }
export async function updateControlDemoArm(armed: boolean) { return postJson<{ status: string }>(`${API_BASE}/api/control-center/demo-arm`, { armed }); }
export async function updateAiAutoLoop(armed: boolean) { return postJson<{ status: string }>(`${API_BASE}/api/control-center/ai-loop`, { armed }); }
export async function updateTradingMethod(method: string) { return postJson<{ status: string; trading_method: string }>(`${API_BASE}/api/control-center/trading-method`, { trading_method: method }); }

export async function loginMT5Account(login: number, password: string, server: string) {
  return postJson<{ status: string; message?: string }>(`${API_BASE}/api/control-center/login-mt5`, { login, password, server });
}

export async function testAIConnection(payload: { key_type: string; model: string; api_key?: string }) {
  return postJson<{ status: string; result: { ok: boolean; message: string } }>(`${API_BASE}/api/ai/test`, payload);
}
