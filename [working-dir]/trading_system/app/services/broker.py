"""
Broker Service - Mock implementation for testing
Standalone version - no external dependencies
"""
import pandas as pd
import numpy as np
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field


@dataclass
class Position:
    """Open position"""
    position_id: str
    symbol: str
    direction: str  # "long" or "short"
    entry_price: float
    quantity: float
    stop_loss: float
    take_profit: float
    opened_at: datetime
    leverage: int = 1
    
    unrealized_pnl: float = 0.0
    tp1_hit: bool = False
    tp2_hit: bool = False
    sl_hit: bool = False


class MockBroker:
    """
    Mock Broker for testing
    Simulates trading without real exchange
    """
    
    def __init__(self, initial_balance: float = 10000.0):
        self.balance = initial_balance
        self.initial_balance = initial_balance
        self.positions: Dict[str, Position] = {}
        self.trades: List[Dict] = []
        self.closed_trades: List[Dict] = []
        self._position_counter = 0
        
        # Cache for market data
        self._market_cache: Dict[str, pd.DataFrame] = {}
        
        # Generate sample market data
        self._generate_sample_data()
    
    def _generate_sample_data(self):
        """Generate sample market data for testing"""
        for symbol in ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']:
            dates = pd.date_range(end=datetime.now(), periods=500, freq='1h')
            
            if symbol == 'BTCUSDT':
                base_price = 65000
                volatility = 500
            elif symbol == 'ETHUSDT':
                base_price = 3500
                volatility = 50
            else:
                base_price = 600
                volatility = 10
            
            prices = [base_price]
            for _ in range(499):
                change = np.random.normal(0, volatility)
                prices.append(prices[-1] + change)
            
            data = []
            for i, date in enumerate(dates):
                open_p = prices[i]
                close_p = prices[i + 1] if i < 499 else prices[i]
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
            
            self._market_cache[symbol] = pd.DataFrame(data)
    
    def get_account_info(self) -> Dict[str, Any]:
        """Get account information"""
        equity = self.balance
        for pos in self.positions.values():
            equity += pos.unrealized_pnl
        
        return {
            'balance': self.balance,
            'equity': equity,
            'available_balance': self.balance,
            'open_positions_count': len(self.positions),
            'total_pnl': equity - self.initial_balance,
            'total_pnl_pct': ((equity - self.initial_balance) / self.initial_balance) * 100,
            'win_rate': self._calculate_win_rate(),
            'total_trades': len(self.closed_trades)
        }
    
    def _calculate_win_rate(self) -> float:
        """Calculate win rate"""
        if not self.closed_trades:
            return 0.0
        wins = sum(1 for t in self.closed_trades if t.get('pnl', 0) > 0)
        return (wins / len(self.closed_trades)) * 100
    
    def get_market_data(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> pd.DataFrame:
        """Get market data"""
        if symbol not in self._market_cache:
            self._generate_sample_data()
        
        df = self._market_cache.get(symbol, pd.DataFrame())
        if len(df) > limit:
            df = df.tail(limit).reset_index(drop=True)
        
        return df
    
    def place_order(
        self,
        symbol: str,
        direction: str,
        quantity: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float = None,
        leverage: int = 1
    ) -> Dict[str, Any]:
        """Place an order"""
        self._position_counter += 1
        position_id = f"POS_{self._position_counter:04d}"
        
        position = Position(
            position_id=position_id,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            quantity=quantity,
            stop_loss=stop_loss,
            take_profit=take_profit or entry_price,
            opened_at=datetime.now(),
            leverage=leverage
        )
        
        self.positions[position_id] = position
        
        return {
            'position_id': position_id,
            'symbol': symbol,
            'direction': direction,
            'entry_price': entry_price,
            'quantity': quantity,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'opened_at': position.opened_at,
            'status': 'open'
        }
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions"""
        return [
            {
                'position_id': pos.position_id,
                'symbol': pos.symbol,
                'direction': pos.direction,
                'entry_price': pos.entry_price,
                'quantity': pos.quantity,
                'stop_loss': pos.stop_loss,
                'take_profit': pos.take_profit,
                'unrealized_pnl': pos.unrealized_pnl,
                'opened_at': pos.opened_at
            }
            for pos in self.positions.values()
        ]
    
    def close_position(self, position_id: str, exit_price: float = None, reason: str = 'manual') -> Dict[str, Any]:
        """Close a position"""
        if position_id not in self.positions:
            return {'status': 'error', 'message': 'Position not found'}
        
        position = self.positions[position_id]
        
        if exit_price is None:
            df = self.get_market_data(position.symbol)
            exit_price = df['close'].iloc[-1]
        
        # Calculate PnL
        if position.direction == 'long':
            pnl = (exit_price - position.entry_price) * position.quantity * position.leverage
        else:
            pnl = (position.entry_price - exit_price) * position.quantity * position.leverage
        
        # Update balance
        self.balance += pnl
        
        # Record trade
        trade = {
            'position_id': position_id,
            'symbol': position.symbol,
            'direction': position.direction,
            'entry_price': position.entry_price,
            'exit_price': exit_price,
            'quantity': position.quantity,
            'pnl': pnl,
            'pnl_pct': (pnl / (position.entry_price * position.quantity)) * 100 if position.entry_price * position.quantity > 0 else 0,
            'exit_reason': reason,
            'opened_at': position.opened_at,
            'closed_at': datetime.now()
        }
        
        self.closed_trades.append(trade)
        
        # Remove position
        del self.positions[position_id]
        
        return {
            'status': 'success',
            'pnl': pnl,
            'exit_price': exit_price,
            'trade': trade
        }
    
    def update_positions(self) -> None:
        """Update unrealized PnL for all positions"""
        for position in self.positions.values():
            df = self.get_market_data(position.symbol)
            current_price = df['close'].iloc[-1]
            
            if position.direction == 'long':
                position.unrealized_pnl = (current_price - position.entry_price) * position.quantity * position.leverage
            else:
                position.unrealized_pnl = (position.entry_price - current_price) * position.quantity * position.leverage
    
    def get_trade_history(self, limit: int = 50) -> List[Dict]:
        """Get closed trade history"""
        return self.closed_trades[-limit:]
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        if not self.closed_trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'best_trade': 0.0,
                'worst_trade': 0.0
            }
        
        wins = [t['pnl'] for t in self.closed_trades if t['pnl'] > 0]
        losses = [t['pnl'] for t in self.closed_trades if t['pnl'] <= 0]
        
        return {
            'total_trades': len(self.closed_trades),
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'win_rate': (len(wins) / len(self.closed_trades)) * 100,
            'total_pnl': sum(t['pnl'] for t in self.closed_trades),
            'avg_win': sum(wins) / len(wins) if wins else 0,
            'avg_loss': sum(losses) / len(losses) if losses else 0,
            'best_trade': max(t['pnl'] for t in self.closed_trades),
            'worst_trade': min(t['pnl'] for t in self.closed_trades)
        }
