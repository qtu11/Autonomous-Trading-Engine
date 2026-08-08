"""
Auto-Trading Bot Service
Continuously monitors and executes trades
"""
import asyncio
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
from app.core.config import settings
from app.services.broker import get_broker, BrokerBase
from app.modules.price_action import PriceActionPatterns
from app.modules.smc import SMCAnalyzer
from app.modules.ict import ICTAnalyzer
from app.modules.sniper import SniperAnalyzer
from app.services.scoring_engine import SignalGenerator, MarketBiasAnalyzer


class TradingBot:
    """
    Auto-Trading Bot
    Monitors symbols and generates/executes trades
    """
    
    def __init__(self, broker: BrokerBase = None):
        self.broker = broker or get_broker('mock', initial_balance=10000)
        self.running = False
        
        # Analyzers
        self.pa = PriceActionPatterns()
        self.smc = SMCAnalyzer()
        self.ict = ICTAnalyzer()
        self.sniper = SniperAnalyzer()
        self.signal_gen = SignalGenerator()
        self.bias = MarketBiasAnalyzer()
        
        # State
        self.positions: List[Dict] = []
        self.trades: List[Dict] = []
        self.signals_history: List[Dict] = []
    
    async def start(self):
        """Start the trading bot"""
        self.running = True
        print(f"[BOT] Starting trading bot...")
        print(f"[BOT] Mode: {settings.TRADING_MODE}")
        print(f"[BOT] Symbols: {settings.SYMBOLS}")
        
        while self.running:
            try:
                # Analyze each symbol
                for symbol in settings.SYMBOLS:
                    await self.analyze_symbol(symbol)
                    await asyncio.sleep(1)  # Rate limiting
                
                # Check existing positions
                await self.check_positions()
                
                # Wait before next iteration
                await asyncio.sleep(60)  # 1 minute
                
            except Exception as e:
                print(f"[BOT] Error in main loop: {e}")
                await asyncio.sleep(10)
    
    async def stop(self):
        """Stop the trading bot"""
        self.running = False
        print("[BOT] Trading bot stopped")
    
    async def analyze_symbol(self, symbol: str):
        """Analyze a single symbol"""
        try:
            # Fetch data
            df = await self.broker.fetch_ohlcv(symbol, settings.DEFAULT_TIMEFRAME, 100)
            
            if df.empty:
                return
            
            # Run all analyses
            pa_data = self.pa.detect_all(df)
            smc_data = self.smc.analyze(df)
            ict_data = self.ict.analyze(df)
            sniper_data = self.sniper.analyze(df)
            
            # Get bias
            bias = self.bias.analyze(smc_data, sniper_data)
            
            # Generate signal
            signal = self.signal_gen.generate_signal(
                df=df,
                smc_data=smc_data,
                ict_data=ict_data,
                sniper_data=sniper_data,
                pa_data=pa_data,
                htf_data=None,
                symbol=symbol,
                timeframe=settings.DEFAULT_TIMEFRAME
            )
            
            # Store in history
            self.signals_history.append({
                'timestamp': datetime.now(),
                'symbol': symbol,
                'signal': signal,
                'bias': bias.direction
            })
            
            # Keep only last 100
            if len(self.signals_history) > 100:
                self.signals_history = self.signals_history[-100:]
            
            # Log
            if signal:
                print(f"[SIGNAL] {symbol} {signal.direction.value.upper()} @ {signal.entry_price:.4f} "
                      f"| Score: {signal.total_score} | Conf: {signal.confidence:.0f}%")
                
                # Execute if in live/paper mode
                if settings.TRADING_MODE in ['live', 'paper']:
                    await self.execute_signal(signal, symbol)
            else:
                print(f"[ANALYSIS] {symbol} | Bias: {bias.direction} | Price: {df['close'].iloc[-1]:.4f}")
                
        except Exception as e:
            print(f"[ERROR] {symbol}: {e}")
    
    async def execute_signal(self, signal, symbol: str):
        """Execute a trading signal"""
        # Check if we can trade
        if len(self.positions) >= settings.MAX_OPEN_TRADES:
            return
        
        # Check if we already have a position for this symbol
        if any(p['symbol'] == symbol and p['status'] == 'open' for p in self.positions):
            return
        
        try:
            # Calculate position size
            balance = await self.broker.get_balance()
            risk_amount = balance * (settings.MAX_RISK_PER_TRADE / 100)
            
            risk_per_unit = abs(signal.entry_price - signal.stop_loss)
            if risk_per_unit > 0:
                position_size = risk_amount / risk_per_unit
            else:
                return
            
            # Execute order
            order_result = await self.broker.place_order(
                symbol=symbol,
                side='buy' if signal.direction.value == 'long' else 'sell',
                amount=position_size,
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit_1
            )
            
            if order_result.get('status') == 'success':
                position = {
                    'id': order_result.get('position', {}).get('id', len(self.positions)),
                    'symbol': symbol,
                    'direction': signal.direction.value,
                    'entry_price': signal.entry_price,
                    'stop_loss': signal.stop_loss,
                    'take_profit_1': signal.take_profit_1,
                    'take_profit_2': signal.take_profit_2,
                    'take_profit_3': signal.take_profit_3,
                    'quantity': position_size,
                    'opened_at': datetime.now(),
                    'signal_score': signal.total_score,
                    'signal_confidence': signal.confidence,
                    'status': 'open',
                    'tp1_hit': False,
                    'tp2_hit': False,
                    'trailing_activated': False
                }
                
                self.positions.append(position)
                
                print(f"[EXECUTE] Opened {signal.direction.value.upper()} position on {symbol}")
                print(f"         Entry: {signal.entry_price:.4f} | SL: {signal.stop_loss:.4f} | TP1: {signal.take_profit_1:.4f}")
            
        except Exception as e:
            print(f"[ERROR] Failed to execute signal: {e}")
    
    async def check_positions(self):
        """Check and manage open positions"""
        try:
            # Get current prices
            for position in self.positions[:]:
                if position['status'] != 'open':
                    continue
                
                symbol = position['symbol']
                
                # Get current candle
                df = await self.broker.fetch_ohlcv(symbol, '1m', 5)
                if df.empty:
                    continue
                
                current_price = df['close'].iloc[-1]
                entry = position['entry_price']
                sl = position['stop_loss']
                tp1 = position['take_profit_1']
                tp2 = position['take_profit_2']
                direction = position['direction']
                
                # Update current price
                position['current_price'] = current_price
                
                # Calculate PnL
                if direction == 'long':
                    pnl = (current_price - entry) * position['quantity']
                    pnl_pct = ((current_price - entry) / entry) * 100
                    
                    # Check SL
                    if current_price <= sl:
                        await self.close_position(position, current_price, 'sl_hit')
                    # Check TP1 - partial close
                    elif current_price >= tp1 and not position['tp1_hit']:
                        position['tp1_hit'] = True
                        close_qty = position['quantity'] * 0.25
                        position['quantity'] -= close_qty
                        print(f"[TP1 HIT] {symbol} - Closed 25% at {current_price:.4f}")
                    # Check TP2
                    elif current_price >= tp2 and not position['tp2_hit']:
                        position['tp2_hit'] = True
                        print(f"[TP2 HIT] {symbol} - All targets reached")
                        await self.close_position(position, current_price, 'tp2_hit')
                else:  # short
                    pnl = (entry - current_price) * position['quantity']
                    pnl_pct = ((entry - current_price) / entry) * 100
                    
                    if current_price >= sl:
                        await self.close_position(position, current_price, 'sl_hit')
                    elif current_price <= tp1 and not position['tp1_hit']:
                        position['tp1_hit'] = True
                        close_qty = position['quantity'] * 0.25
                        position['quantity'] -= close_qty
                        print(f"[TP1 HIT] {symbol} - Closed 25% at {current_price:.4f}")
                    elif current_price <= tp2 and not position['tp2_hit']:
                        position['tp2_hit'] = True
                        await self.close_position(position, current_price, 'tp2_hit')
                
                position['pnl'] = pnl
                position['pnl_pct'] = pnl_pct
                
        except Exception as e:
            print(f"[ERROR] Checking positions: {e}")
    
    async def close_position(self, position: Dict, exit_price: float, reason: str):
        """Close a position"""
        position['status'] = 'closed'
        position['exit_price'] = exit_price
        position['closed_at'] = datetime.now()
        position['exit_reason'] = reason
        
        # Calculate final PnL
        if position['direction'] == 'long':
            pnl = (exit_price - position['entry_price']) * position['quantity']
        else:
            pnl = (position['entry_price'] - exit_price) * position['quantity']
        
        position['pnl'] = pnl
        
        # Add to trades history
        self.trades.append(position.copy())
        
        print(f"[CLOSE] {position['symbol']} | Reason: {reason} | PnL: {pnl:.2f}")
    
    def get_status(self) -> Dict:
        """Get bot status"""
        return {
            'running': self.running,
            'mode': settings.TRADING_MODE,
            'positions_open': len([p for p in self.positions if p['status'] == 'open']),
            'positions_closed': len([p for p in self.positions if p['status'] == 'closed']),
            'total_trades': len(self.trades),
            'winning_trades': len([t for t in self.trades if t.get('pnl', 0) > 0]),
            'losing_trades': len([t for t in self.trades if t.get('pnl', 0) < 0]),
            'total_pnl': sum(t.get('pnl', 0) for t in self.trades),
            'win_rate': len([t for t in self.trades if t.get('pnl', 0) > 0]) / max(len(self.trades), 1) * 100,
            'recent_signals': len(self.signals_history[-10:]) if self.signals_history else 0
        }
    
    async def run_backtest(self, symbol: str, start_date: datetime, end_date: datetime):
        """Run backtest for a symbol"""
        print(f"[BACKTEST] Starting backtest for {symbol}")
        
        # This is a simplified backtest
        # In production, you'd use a proper backtesting library
        df = await self.broker.fetch_ohlcv(symbol, settings.DEFAULT_TIMEFRAME, 1000)
        
        results = []
        
        for i in range(100, len(df)):
            window = df.iloc[:i]
            
            # Analyze
            pa_data = self.pa.detect_all(window)
            smc_data = self.smc.analyze(window)
            ict_data = self.ict.analyze(window)
            sniper_data = self.sniper.analyze(window)
            
            signal = self.signal_gen.generate_signal(
                df=window,
                smc_data=smc_data,
                ict_data=ict_data,
                sniper_data=sniper_data,
                pa_data=pa_data,
                symbol=symbol,
                timeframe=settings.DEFAULT_TIMEFRAME
            )
            
            if signal:
                results.append({
                    'timestamp': window['timestamp'].iloc[-1],
                    'signal': signal,
                    'actual_move': df['close'].iloc[i] - signal.entry_price
                })
        
        # Calculate metrics
        winning = len([r for r in results if r['actual_move'] > 0])
        total = len(results)
        
        print(f"[BACKTEST] Completed | Signals: {total} | Win Rate: {winning/total*100:.1f}%")
        
        return {
            'total_signals': total,
            'winning_signals': winning,
            'win_rate': winning / max(total, 1) * 100
        }


# Global bot instance
bot: Optional[TradingBot] = None


async def start_bot():
    """Start the trading bot"""
    global bot
    bot = TradingBot()
    await bot.start()


async def stop_bot():
    """Stop the trading bot"""
    global bot
    if bot:
        await bot.stop()
