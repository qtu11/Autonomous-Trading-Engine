"""
FastAPI Main Application
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi import WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager
import asyncio
import uvicorn
from datetime import datetime
from typing import Optional, Dict, List
import pandas as pd
import numpy as np

from app.core.config import settings
from app.models.data_models import (
    TradingSignal, Position, Trade, Account,
    TimeFrame, TradeDirection, SignalType, ChartData, OHLCV
)
from app.modules.price_action import PriceActionPatterns, CandleCalculator
from app.modules.smc import SMCAnalyzer
from app.modules.ict import ICTAnalyzer
from app.modules.sniper import SniperAnalyzer
from app.services.scoring_engine import SignalGenerator, MarketBiasAnalyzer


# ─── APP SETUP ───
@asynccontextmanager
async def lifespan(app: FastAPI):
    """App startup and shutdown"""
    print(f"Starting {settings.APP_NAME} v{settings.VERSION}")
    print(f"Trading Mode: {settings.TRADING_MODE}")
    yield
    print("Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── GLOBAL INSTANCES ───
pa_analyzer = PriceActionPatterns()
smc_analyzer = SMCAnalyzer()
ict_analyzer = ICTAnalyzer()
sniper_analyzer = SniperAnalyzer()
signal_generator = SignalGenerator()
bias_analyzer = MarketBiasAnalyzer()


# ─── WEBSOCKET CONNECTION MANAGER ───
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass


manager = ConnectionManager()


# ─── MOCK DATA GENERATOR ───
def generate_sample_candles(count: int = 100, timeframe: str = "1h") -> pd.DataFrame:
    """Generate sample OHLCV data for testing"""
    dates = pd.date_range(end=datetime.now(), periods=count, freq=timeframe)
    
    data = {
        'timestamp': dates,
        'open': np.random.uniform(100, 110, count),
        'high': np.zeros(count),
        'low': np.zeros(count),
        'close': np.zeros(count),
        'volume': np.random.uniform(1000, 10000, count)
    }
    
    # Generate realistic price movement
    close = 100.0
    for i in range(count):
        open_price = close
        volatility = np.random.uniform(0.5, 2.0)
        change = np.random.normal(0, volatility)
        close = open_price + change
        
        high = max(open_price, close) + abs(np.random.normal(0, volatility/2))
        low = min(open_price, close) - abs(np.random.normal(0, volatility/2))
        
        data['open'][i] = open_price
        data['high'][i] = high
        data['low'][i] = low
        data['close'][i] = close
    
    df = pd.DataFrame(data)
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)
    
    return df


# ─── ANALYSIS FUNCTION ───
def analyze_symbol(df: pd.DataFrame, symbol: str, timeframe: str) -> dict:
    """Run full analysis on symbol"""
    
    # Calculate all analyses
    pa_data = pa_analyzer.detect_all(df)
    smc_data = smc_analyzer.analyze(df)
    ict_data = ict_analyzer.analyze(df)
    sniper_data = sniper_analyzer.analyze(df)
    
    # Get market bias
    market_bias = bias_analyzer.analyze(smc_data, sniper_data)
    
    # Generate signal
    signal = signal_generator.generate_signal(
        df=df,
        smc_data=smc_data,
        ict_data=ict_data,
        sniper_data=sniper_data,
        pa_data=pa_data,
        htf_data=None,
        symbol=symbol,
        timeframe=timeframe
    )
    
    return {
        'symbol': symbol,
        'timeframe': timeframe,
        'timestamp': datetime.now().isoformat(),
        'current_price': float(df['close'].iloc[-1]),
        'indicators': {
            'ema_9': float(sniper_data.get('ema_9', 0)),
            'ema_21': float(sniper_data.get('ema_21', 0)),
            'vwap': float(sniper_data.get('vwap', 0)),
            'rsi_14': float(sniper_data.get('rsi_14', 50)),
            'adx': float(sniper_data.get('adx', 0)),
            'macd_main': float(sniper_data.get('macd_main', 0)),
            'macd_signal': float(sniper_data.get('macd_signal', 0)),
            'atr': float(sniper_data.get('atr', 0)),
            'ribbon_bull': sniper_data.get('ribbon_bull', False),
            'ribbon_bear': sniper_data.get('ribbon_bear', False),
            'price_above_vwap': sniper_data.get('price_above_vwap', False),
            'price_below_vwap': sniper_data.get('price_below_vwap', False)
        },
        'smc': {
            'bull_fvg': smc_data.get('bull_fvg', False),
            'bear_fvg': smc_data.get('bear_fvg', False),
            'bull_ob': smc_data.get('bull_ob', False),
            'bear_ob': smc_data.get('bear_ob', False),
            'bull_sweep': smc_data.get('bull_sweep', False),
            'bear_sweep': smc_data.get('bear_sweep', False),
            'bull_bos': smc_data.get('bull_bos', False),
            'bear_bos': smc_data.get('bear_bos', False),
            'bull_mss': smc_data.get('bull_mss', False),
            'bear_mss': smc_data.get('bear_mss', False),
            'bull_choch': smc_data.get('bull_choch', False),
            'bear_choch': smc_data.get('bear_choch', False),
            'swing_high': float(smc_data.get('swing_high', 0)),
            'swing_low': float(smc_data.get('swing_low', 0)),
            'in_discount': smc_data.get('in_discount', False),
            'in_premium': smc_data.get('in_premium', False),
            'equilibrium': float(smc_data.get('equilibrium', 0))
        },
        'ict': {
            'in_killzone': ict_data.get('in_killzone', False),
            'active_kz': ict_data.get('active_kz'),
            'in_ote_zone': ict_data.get('in_ote_zone', False),
            'ote_618': float(ict_data.get('ote_618', 0)),
            'ote_786': float(ict_data.get('ote_786', 0)),
            'bullish_judas': ict_data.get('bullish_judas', False),
            'bearish_judas': ict_data.get('bearish_judas', False),
            'bull_po3': ict_data.get('bull_po3', False),
            'bear_po3': ict_data.get('bear_po3', False),
            'pivot': float(ict_data.get('pivot', 0)),
            'r1': float(ict_data.get('r1', 0)),
            's1': float(ict_data.get('s1', 0)),
            'pdh': float(ict_data.get('pdh', 0)),
            'pdl': float(ict_data.get('pdl', 0))
        },
        'patterns': {
            'bullish_pinbar': pa_data.get('bullish_pinbar', False),
            'bearish_pinbar': pa_data.get('bearish_pinbar', False),
            'bullish_engulfing': pa_data.get('bullish_engulfing', False),
            'bearish_engulfing': pa_data.get('bearish_engulfing', False),
            'bullish_displacement': pa_data.get('bullish_displacement', False),
            'bearish_displacement': pa_data.get('bearish_displacement', False),
            'inside_bar': pa_data.get('inside_bar', False),
            'outside_bar': pa_data.get('outside_bar', False),
            'all_patterns': pa_data.get('patterns', [])
        },
        'scores': {
            'smc_buy_score': pa_data.get('smc_buy_score', 0),
            'smc_sell_score': pa_data.get('smc_sell_score', 0),
            'sniper_bull_pct': float(sniper_data.get('sniper_bull_pct', 0)),
            'sniper_bear_pct': float(sniper_data.get('sniper_bear_pct', 0)),
            'pattern_score': pa_data.get('pattern_score', 0)
        },
        'market_bias': {
            'direction': market_bias.direction,
            'strength': market_bias.strength
        },
        'signal': {
            'direction': signal.direction.value if signal else None,
            'signal_type': signal.signal_type.value if signal else None,
            'entry_price': float(signal.entry_price) if signal else None,
            'stop_loss': float(signal.stop_loss) if signal else None,
            'take_profit_1': float(signal.take_profit_1) if signal else None,
            'risk_reward_1': float(signal.risk_reward_1) if signal else None,
            'risk_reward_2': float(signal.risk_reward_2) if signal else None,
            'risk_reward_3': float(signal.risk_reward_3) if signal else None,
            'total_score': signal.total_score if signal else 0,
            'confidence': float(signal.confidence) if signal else 0,
            'reasons': signal.signal_reasons if signal else [],
            'patterns': signal.patterns if signal else []
        } if signal else None
    }


# ─── API ROUTES ───

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "running",
        "trading_mode": settings.TRADING_MODE.value,
        "docs": "/docs"
    }


@app.get("/api/health")
async def health():
    """Health check"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/symbols")
async def get_symbols():
    """Get available symbols"""
    return {
        "symbols": settings.SYMBOLS,
        "timeframes": [tf.value for tf in TimeFrame]
    }


@app.get("/api/analyze/{symbol}")
async def analyze_symbol_endpoint(
    symbol: str,
    timeframe: str = "1h"
):
    """Analyze a symbol and return full analysis"""
    
    # Validate symbol
    if symbol not in settings.SYMBOLS:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
    
    # Generate sample data (in real app, fetch from broker)
    df = generate_sample_candles(100, timeframe)
    
    # Run analysis
    result = analyze_symbol(df, symbol, timeframe)
    
    return result


@app.get("/api/candles/{symbol}")
async def get_candles(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 100
):
    """Get candle data for a symbol"""
    
    if symbol not in settings.SYMBOLS:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
    
    df = generate_sample_candles(limit, timeframe)
    
    candles = []
    for _, row in df.iterrows():
        candles.append({
            'timestamp': row['timestamp'].isoformat(),
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row['volume'])
        })
    
    return {'symbol': symbol, 'timeframe': timeframe, 'candles': candles}


@app.get("/api/signal/{symbol}")
async def get_signal(symbol: str, timeframe: str = "1h"):
    """Get current trading signal for a symbol"""
    
    df = generate_sample_candles(100, timeframe)
    result = analyze_symbol(df, symbol, timeframe)
    
    if result['signal'] is None:
        return {
            'symbol': symbol,
            'signal': None,
            'message': 'No valid signal at this time'
        }
    
    return result


@app.get("/api/dashboard")
async def get_dashboard():
    """Get dashboard data for all symbols"""
    
    results = []
    for symbol in settings.SYMBOLS[:4]:  # Top 4 symbols
        df = generate_sample_candles(100, "1h")
        analysis = analyze_symbol(df, symbol, "1h")
        
        results.append({
            'symbol': symbol,
            'price': analysis['current_price'],
            'bias': analysis['market_bias']['direction'],
            'bias_strength': analysis['market_bias']['strength'],
            'smc_score': max(analysis['scores']['smc_buy_score'], 
                           analysis['scores']['smc_sell_score']),
            'sniper_bull': analysis['scores']['sniper_bull_pct'],
            'sniper_bear': analysis['scores']['sniper_bear_pct'],
            'signal': analysis['signal']
        })
    
    return {
        'timestamp': datetime.now().isoformat(),
        'symbols': results
    }


# ─── WEBSOCKET ENDPOINT ───
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates"""
    await manager.connect(websocket)
    
    try:
        while True:
            # Send analysis update every 5 seconds
            await asyncio.sleep(5)
            
            for symbol in settings.SYMBOLS[:2]:
                df = generate_sample_candles(100, "1h")
                analysis = analyze_symbol(df, symbol, "1h")
                
                await websocket.send_json({
                    'type': 'analysis',
                    'data': analysis
                })
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        manager.disconnect(websocket)


# ─── FRONTEND ROUTES ───
@app.get("/dashboard")
async def dashboard_page():
    """Dashboard HTML page"""
    html = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Qtus SMC-Sniper Trading System</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%);
            color: #fff;
            min-height: 100vh;
        }
        
        .header {
            background: rgba(0, 0, 0, 0.5);
            padding: 20px 40px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header h1 {
            font-size: 24px;
            background: linear-gradient(90deg, #00ff88, #00b4d8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .status {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #00ff88;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .container {
            max-width: 1600px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        
        .card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
        }
        
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .card-title {
            font-size: 16px;
            font-weight: 600;
            color: #888;
        }
        
        .symbol-name {
            font-size: 24px;
            font-weight: bold;
        }
        
        .price {
            font-size: 32px;
            font-weight: bold;
            margin: 10px 0;
        }
        
        .price.up { color: #00ff88; }
        .price.down { color: #ff4444; }
        
        .bias {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
        }
        
        .bias.bull { background: rgba(0, 255, 136, 0.2); color: #00ff88; }
        .bias.bear { background: rgba(255, 68, 68, 0.2); color: #ff4444; }
        .bias.neutral { background: rgba(255, 255, 255, 0.1); color: #888; }
        
        .scores {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            margin-top: 15px;
        }
        
        .score-item {
            background: rgba(0, 0, 0, 0.3);
            padding: 12px;
            border-radius: 8px;
            text-align: center;
        }
        
        .score-label {
            font-size: 11px;
            color: #666;
            text-transform: uppercase;
        }
        
        .score-value {
            font-size: 24px;
            font-weight: bold;
            margin-top: 5px;
        }
        
        .score-value.bull { color: #00ff88; }
        .score-value.bear { color: #ff4444; }
        
        .signal-box {
            background: rgba(0, 0, 0, 0.3);
            padding: 20px;
            border-radius: 12px;
            margin-top: 15px;
            text-align: center;
        }
        
        .signal-direction {
            font-size: 18px;
            font-weight: bold;
            text-transform: uppercase;
            margin-bottom: 10px;
        }
        
        .signal-direction.buy { color: #00ff88; }
        .signal-direction.sell { color: #ff4444; }
        .signal-direction.wait { color: #888; }
        
        .trade-levels {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin-top: 15px;
        }
        
        .level {
            background: rgba(0, 0, 0, 0.3);
            padding: 10px;
            border-radius: 8px;
            text-align: center;
        }
        
        .level-label {
            font-size: 10px;
            color: #666;
            text-transform: uppercase;
        }
        
        .level-value {
            font-size: 16px;
            font-weight: bold;
            margin-top: 5px;
        }
        
        .level-value.entry { color: #00b4d8; }
        .level-value.sl { color: #ff4444; }
        .level-value.tp { color: #00ff88; }
        
        .factors {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 15px;
        }
        
        .factor {
            background: rgba(255, 255, 255, 0.1);
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 11px;
        }
        
        .factor.active { background: rgba(0, 255, 136, 0.3); color: #00ff88; }
        .factor.inactive { background: rgba(255, 255, 255, 0.05); color: #444; }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        
        .loading-spinner {
            width: 40px;
            height: 40px;
            border: 3px solid rgba(255, 255, 255, 0.1);
            border-top-color: #00ff88;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .refresh-btn {
            background: linear-gradient(135deg, #00ff88 0%, #00b4d8 100%);
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            color: #000;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.2s;
        }
        
        .refresh-btn:hover {
            transform: scale(1.05);
        }
        
        .legend {
            display: flex;
            gap: 20px;
            justify-content: center;
            margin-top: 20px;
            padding: 15px;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 8px;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 12px;
            color: #888;
        }
        
        .legend-color {
            width: 12px;
            height: 12px;
            border-radius: 3px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Qtus SMC-Sniper Trading System v2.0</h1>
        <div class="status">
            <div class="status-dot"></div>
            <span>Live Trading</span>
            <button class="refresh-btn" onclick="refreshAll()">Refresh</button>
        </div>
    </div>
    
    <div class="container">
        <div class="legend">
            <div class="legend-item">
                <div class="legend-color" style="background: #00ff88;"></div>
                <span>Bullish</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #ff4444;"></div>
                <span>Bearish</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #00b4d8;"></div>
                <span>Neutral</span>
            </div>
        </div>
        
        <div class="grid" id="symbols-grid">
            <div class="card">
                <div class="loading">
                    <div class="loading-spinner"></div>
                    Loading...
                </div>
            </div>
        </div>
    </div>
    
    <script>
        const API_BASE = '/api';
        
        async function fetchAnalysis(symbol) {
            try {
                const response = await fetch(`${API_BASE}/analyze/${symbol}`);
                return await response.json();
            } catch (error) {
                console.error('Error fetching', symbol, error);
                return null;
            }
        }
        
        function createCard(analysis) {
            if (!analysis) return '<div class="card">Error loading data</div>';
            
            const signal = analysis.signal || {};
            const bias = analysis.market_bias || {};
            const scores = analysis.scores || {};
            const smc = analysis.smc || {};
            const ict = analysis.ict || {};
            const patterns = analysis.patterns || {};
            const indicators = analysis.indicators || {};
            
            const biasClass = bias.direction === 'bull' ? 'bull' : bias.direction === 'bear' ? 'bear' : 'neutral';
            const signalClass = signal.direction === 'long' ? 'buy' : signal.direction === 'short' ? 'sell' : 'wait';
            
            // Collect active factors
            let factors = [];
            if (smc.bull_fvg) factors.push('FVG+');
            if (smc.bear_fvg) factors.push('FVG-');
            if (smc.bull_ob) factors.push('OB+');
            if (smc.bear_ob) factors.push('OB-');
            if (smc.bull_sweep) factors.push('SSL Sweep');
            if (smc.bear_sweep) factors.push('BSL Sweep');
            if (smc.bull_mss) factors.push('MSS+');
            if (smc.bear_mss) factors.push('MSS-');
            if (ict.in_killzone) factors.push(ict.active_kz?.toUpperCase() + ' KZ');
            if (ict.in_ote_zone) factors.push('OTE Zone');
            if (patterns.bullish_pinbar) factors.push('Bull PB');
            if (patterns.bearish_pinbar) factors.push('Bear PB');
            if (patterns.bullish_engulfing) factors.push('Bull Eng');
            if (patterns.bearish_engulfing) factors.push('Bear Eng');
            
            return `
                <div class="card">
                    <div class="card-header">
                        <span class="symbol-name">${analysis.symbol}</span>
                        <span class="bias ${biasClass}">${bias.direction || 'NEUTRAL'} / ${bias.strength || 'WEAK'}</span>
                    </div>
                    
                    <div class="price ${indicators.price_above_vwap ? 'up' : 'down'}">
                        $${analysis.current_price.toFixed(4)}
                    </div>
                    
                    <div style="font-size: 12px; color: #666; margin-bottom: 15px;">
                        EMA9: $${indicators.ema_9?.toFixed(4)} | EMA21: $${indicators.ema_21?.toFixed(4)}<br>
                        VWAP: $${indicators.vwap?.toFixed(4)} | RSI: ${indicators.rsi_14?.toFixed(1)} | ADX: ${indicators.adx?.toFixed(1)}
                    </div>
                    
                    <div class="scores">
                        <div class="score-item">
                            <div class="score-label">SMC Score</div>
                            <div class="score-value ${scores.smc_buy_score > scores.smc_sell_score ? 'bull' : 'bear'}">
                                ${Math.max(scores.smc_buy_score, scores.smc_sell_score)}/13
                            </div>
                        </div>
                        <div class="score-item">
                            <div class="score-label">Pattern Score</div>
                            <div class="score-value">${scores.pattern_score}</div>
                        </div>
                        <div class="score-item">
                            <div class="score-label">Sniper Bull</div>
                            <div class="score-value bull">${scores.sniper_bull_pct?.toFixed(0)}%</div>
                        </div>
                        <div class="score-item">
                            <div class="score-label">Sniper Bear</div>
                            <div class="score-value bear">${scores.sniper_bear_pct?.toFixed(0)}%</div>
                        </div>
                    </div>
                    
                    ${signal.direction ? `
                    <div class="signal-box">
                        <div class="signal-direction ${signalClass}">
                            ${signal.signal_type === 'strong_buy' ? '⚡ SNIPER BUY' : signal.signal_type === 'strong_sell' ? '⚡ SNIPER SELL' : signal.direction === 'long' ? 'BUY' : 'SELL'}
                        </div>
                        <div style="font-size: 12px; color: #888; margin-top: 5px;">
                            Score: ${signal.total_score} | Confidence: ${signal.confidence?.toFixed(0)}%
                        </div>
                        
                        <div class="trade-levels">
                            <div class="level">
                                <div class="level-label">Entry</div>
                                <div class="level-value entry">$${signal.entry_price?.toFixed(4)}</div>
                            </div>
                            <div class="level">
                                <div class="level-label">Stop Loss</div>
                                <div class="level-value sl">$${signal.stop_loss?.toFixed(4)}</div>
                            </div>
                            <div class="level">
                                <div class="level-label">TP1</div>
                                <div class="level-value tp">$${signal.take_profit_1?.toFixed(4)}</div>
                            </div>
                        </div>
                        
                        <div style="font-size: 11px; color: #00ff88; margin-top: 10px;">
                            R:R = 1:${signal.risk_reward_1?.toFixed(1)} / 1:${signal.risk_reward_2?.toFixed(1)} / 1:${signal.risk_reward_3?.toFixed(1)}
                        </div>
                    </div>
                    ` : `
                    <div class="signal-box">
                        <div class="signal-direction wait">WAITING FOR SIGNAL</div>
                    </div>
                    `}
                    
                    ${factors.length > 0 ? `
                    <div class="factors">
                        ${factors.map(f => `<span class="factor active">${f}</span>`).join('')}
                    </div>
                    ` : ''}
                    
                    <div style="margin-top: 15px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.1); font-size: 11px; color: #666;">
                        <strong>ICT Levels:</strong> PDH: $${ict.pdh?.toFixed(4)} | PDL: $${ict.pdl?.toFixed(4)}<br>
                        Pivot: $${ict.pivot?.toFixed(4)} | R1: $${ict.r1?.toFixed(4)} | S1: $${ict.s1?.toFixed(4)}<br>
                        OTE: $${ict.ote_618?.toFixed(4)} - $${ict.ote_786?.toFixed(4)}
                    </div>
                </div>
            `;
        }
        
        async function refreshAll() {
            const grid = document.getElementById('symbols-grid');
            grid.innerHTML = '<div class="card"><div class="loading"><div class="loading-spinner"></div>Loading...</div></div>';
            
            const symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT'];
            let html = '';
            
            for (const symbol of symbols) {
                const analysis = await fetchAnalysis(symbol);
                html += createCard(analysis);
            }
            
            grid.innerHTML = html;
        }
        
        // WebSocket connection
        const ws = new WebSocket('ws://' + window.location.host + '/ws');
        
        ws.onmessage = function(event) {
            const data = JSON.parse(event.data);
            if (data.type === 'analysis') {
                // Update specific symbol card
                console.log('Received update for', data.data.symbol);
            }
        };
        
        // Initial load
        refreshAll();
        
        // Auto refresh every 30 seconds
        setInterval(refreshAll, 30000);
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html)


# ─── START APP ───
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
