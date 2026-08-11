"""
Auto-Trading Bot Service
Standalone version - no external dependencies
"""
import asyncio
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class BotConfig:
    """Bot configuration"""
    symbols: List[str] = None
    timeframe: str = "1h"
    check_interval: int = 60  # seconds
    max_positions: int = 5
    risk_per_trade: float = 2.0  # percent of balance
    
    def __post_init__(self):
        if self.symbols is None:
            self.symbols = ['BTCUSDT', 'ETHUSDT']


@dataclass
class BotState:
    """Bot state tracking"""
    running: bool = False
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    last_analysis: Optional[datetime] = None
    signals_generated: int = 0
    trades_executed: int = 0
    
    errors: List[str] = field(default_factory=list)
    last_error: Optional[str] = None


class TradingBot:
    """
    Auto-Trading Bot
    Monitors symbols and generates/executes trades
    """
    
    def __init__(self, broker=None, config: BotConfig = None):
        self.broker = broker
        self.config = config or BotConfig()
        self.state = BotState()
        
        # Import analyzers
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        from app.modules.price_action import PriceActionPatterns
        from app.modules.smc import SMCAnalyzer
        from app.modules.ict import ICTAnalyzer
        from app.modules.sniper import SniperAnalyzer
        from app.services.scoring_engine import SignalGenerator, MarketBiasAnalyzer
        
        # Initialize analyzers
        self.pa = PriceActionPatterns()
        self.smc = SMCAnalyzer()
        self.ict = ICTAnalyzer()
        self.sniper = SniperAnalyzer()
        self.signal_gen = SignalGenerator()
        self.bias = MarketBiasAnalyzer()
        
        # State tracking
        self.positions: List[Dict] = []
        self.trades: List[Dict] = []
        self.signals_history: List[Dict] = []
    
    async def start(self):
        """Start the trading bot"""
        self.state.running = True
        print(f"[BOT] Starting trading bot...")
        print(f"[BOT] Symbols: {self.config.symbols}")
        print(f"[BOT] Timeframe: {self.config.timeframe}")
        
        while self.state.running:
            try:
                # Analyze each symbol
                for symbol in self.config.symbols:
                    await self.analyze_symbol(symbol)
                    await asyncio.sleep(1)  # Rate limiting
                
                # Check existing positions
                await self.check_positions()
                
                # Update state
                self.state.last_analysis = datetime.now()
                
                # Wait before next iteration
                await asyncio.sleep(self.config.check_interval)
                
            except Exception as e:
                error_msg = f"Error in main loop: {e}"
                print(f"[BOT] {error_msg}")
                self.state.errors.append(error_msg)
                self.state.last_error = error_msg
                await asyncio.sleep(10)
    
    async def stop(self):
        """Stop the trading bot"""
        self.state.running = False
        print("[BOT] Trading bot stopped")
    
    async def analyze_symbol(self, symbol: str):
        """Analyze a single symbol"""
        try:
            # Fetch data
            if self.broker:
                df = self.broker.get_market_data(symbol, self.config.timeframe, 200)
            else:
                df = self._generate_sample_data()
            
            if df.empty or len(df) < 50:
                print(f"[BOT] {symbol}: Insufficient data")
                return
            
            # Run all analyses
            pa_data = self.pa.detect_all(df)
            smc_data = self.smc.analyze(df)
            ict_data = self.ict.analyze(df)
            sniper_data = self.sniper.analyze(df)
            
            # Generate signal
            signal = self.signal_gen.generate_signal(
                df, smc_data, ict_data, sniper_data, pa_data, symbol, self.config.timeframe
            )
            
            # Update signals history
            if signal:
                self.signals_history.append({
                    'timestamp': datetime.now(),
                    'symbol': symbol,
                    'direction': signal.direction,
                    'score': signal.total_score,
                    'confidence': signal.confidence
                })
                self.state.signals_generated += 1
                print(f"[BOT] {symbol}: SIGNAL {signal.direction} @ {signal.entry_price:.2f} (score={signal.total_score:.0f})")
                
                # Check if we should execute
                if self._should_execute(signal):
                    await self.execute_signal(signal)
            else:
                print(f"[BOT] {symbol}: No signal (market neutral)")
            
        except Exception as e:
            error_msg = f"Error analyzing {symbol}: {e}"
            print(f"[BOT] {error_msg}")
            self.state.errors.append(error_msg)
            self.state.last_error = error_msg
    
    def _generate_sample_data(self) -> pd.DataFrame:
        """Generate sample data for testing"""
        import numpy as np
        
        dates = pd.date_range(end=datetime.now(), periods=200, freq='1h')
        base_price = 65000
        volatility = 500
        
        prices = [base_price]
        for _ in range(199):
            change = np.random.normal(0, volatility)
            prices.append(prices[-1] + change)
        
        data = []
        for i, date in enumerate(dates):
            if i >= len(prices):
                break
            open_p = prices[i]
            close_p = prices[i + 1] if i < len(prices) - 1 else prices[i]
            high = max(open_p, close_p) + abs(np.random.normal(0, volatility * 0.5))
            low = min(open_p, close_p) - abs(np.random.normal(0, volatility * 0.5))
            volume = np.random.uniform(100, 1000)
            
            data.append({
                'timestamp': date,
                'open': open_p,
                'high': high,
                'low': low,
                'close': close_p,
                'volume': volume
            })
        
        return pd.DataFrame(data)
    
    def _should_execute(self, signal) -> bool:
        """Check if signal should be executed"""
        # Don't exceed max positions
        if len(self.positions) >= self.config.max_positions:
            return False
        
        # Require minimum confidence
        if signal.confidence < 60:
            return False
        
        # Require minimum score
        if signal.total_score < 5:
            return False
        
        # Require confluence
        if signal.confluence_count < 1:
            return False
        
        return True
    
    async def execute_signal(self, signal):
        """Execute a trading signal"""
        try:
            if not self.broker:
                print(f"[BOT] No broker configured - would execute {signal.direction} on {signal.symbol}")
                self.state.trades_executed += 1
                return
            
            # Calculate position size
            account = self.broker.get_account_info()
            risk_amount = account['balance'] * (self.config.risk_per_trade / 100)
            risk_per_unit = abs(signal.entry_price - signal.stop_loss)
            quantity = risk_amount / risk_per_unit if risk_per_unit > 0 else 0
            
            # Place order
            order = self.broker.place_order(
                symbol=signal.symbol,
                direction=signal.direction,
                quantity=quantity,
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit_1
            )
            
            self.positions.append(order)
            self.state.trades_executed += 1
            
            print(f"[BOT] EXECUTED: {signal.direction} {signal.symbol} @ {signal.entry_price:.2f}")
            
        except Exception as e:
            error_msg = f"Error executing signal: {e}"
            print(f"[BOT] {error_msg}")
            self.state.errors.append(error_msg)
            self.state.last_error = error_msg
    
    async def check_positions(self):
        """Check and manage open positions"""
        if not self.broker or not self.positions:
            return
        
        try:
            # Update positions
            self.broker.update_positions()
            current_positions = self.broker.get_positions()
            
            # Check for closed positions
            for pos in current_positions:
                if pos.get('sl_hit') or pos.get('tp_hit'):
                    self._record_trade(pos)
            
        except Exception as e:
            error_msg = f"Error checking positions: {e}"
            print(f"[BOT] {error_msg}")
            self.state.errors.append(error_msg)
    
    def _record_trade(self, position: Dict):
        """Record a completed trade"""
        self.state.total_trades += 1
        
        if position.get('unrealized_pnl', 0) > 0:
            self.state.winning_trades += 1
        else:
            self.state.losing_trades += 1
        
        self.state.total_pnl += position.get('unrealized_pnl', 0)
        
        # Remove from active positions
        self.positions = [p for p in self.positions if p.get('position_id') != position.get('position_id')]
    
    def get_status(self) -> Dict:
        """Get bot status"""
        return {
            'running': self.state.running,
            'positions': len(self.positions),
            'total_trades': self.state.total_trades,
            'win_rate': (self.state.winning_trades / self.state.total_trades * 100) if self.state.total_trades > 0 else 0,
            'total_pnl': self.state.total_pnl,
            'signals_generated': self.state.signals_generated,
            'trades_executed': self.state.trades_executed,
            'last_error': self.state.last_error
        }
