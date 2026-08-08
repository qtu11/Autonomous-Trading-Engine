"""
Broker Service - Connect to exchanges
Supports: Binance, Binance Futures
"""
import pandas as pd
import numpy as np
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
import ccxt


class BrokerBase(ABC):
    """Base broker class"""
    
    @abstractmethod
    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        pass
    
    @abstractmethod
    async def get_balance(self) -> float:
        pass
    
    @abstractmethod
    async def place_order(self, symbol: str, side: str, amount: float, 
                         entry_price: float, stop_loss: float, take_profit: float) -> dict:
        pass


class BinanceBroker(BrokerBase):
    """
    Binance Broker
    Supports spot and futures trading
    """
    
    def __init__(self, api_key: str = None, api_secret: str = None, testnet: bool = True):
        self.testnet = testnet
        
        if testnet:
            self.exchange = ccxt.binance({
                'apiKey': api_key or 'test_key',
                'secret': api_secret or 'test_secret',
                'options': {'defaultType': 'spot'}
            })
            # Use testnet
            self.exchange.set_sandbox_mode(True)
        else:
            self.exchange = ccxt.binance({
                'apiKey': api_key,
                'secret': api_secret
            })
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> pd.DataFrame:
        """Fetch OHLCV data"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            return df
        except Exception as e:
            print(f"Error fetching OHLCV: {e}")
            return pd.DataFrame()
    
    async def get_balance(self) -> float:
        """Get account balance"""
        try:
            balance = self.exchange.fetch_balance()
            return float(balance.get('USDT', {}).get('free', 0))
        except Exception as e:
            print(f"Error fetching balance: {e}")
            return 0.0
    
    async def place_order(self, symbol: str, side: str, amount: float,
                        entry_price: float, stop_loss: float, take_profit: float) -> dict:
        """Place a complete trade with SL and TP"""
        try:
            # Place entry order
            entry_order = self.exchange.create_order(
                symbol=symbol,
                type='limit',
                side=side,
                amount=amount,
                price=entry_price
            )
            
            # Place stop loss
            sl_order = self.exchange.create_order(
                symbol=symbol,
                type='stop-loss',
                side='sell' if side == 'buy' else 'buy',
                amount=amount,
                price=stop_loss
            )
            
            # Place take profit
            tp_order = self.exchange.create_order(
                symbol=symbol,
                type='take-profit',
                side='sell' if side == 'buy' else 'buy',
                amount=amount,
                price=take_profit
            )
            
            return {
                'entry_order': entry_order,
                'sl_order': sl_order,
                'tp_order': tp_order,
                'status': 'success'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    
    async def get_open_positions(self) -> List[dict]:
        """Get open positions"""
        try:
            positions = self.exchange.fetch_positions()
            return [p for p in positions if p.get('contracts', 0) > 0]
        except Exception as e:
            print(f"Error fetching positions: {e}")
            return []
    
    async def cancel_order(self, order_id: str, symbol: str) -> dict:
        """Cancel an order"""
        try:
            return self.exchange.cancel_order(order_id, symbol)
        except Exception as e:
            return {'status': 'error', 'message': str(e)}


class MockBroker(BrokerBase):
    """
    Mock Broker for paper trading / testing
    Generates realistic price data
    """
    
    def __init__(self, initial_balance: float = 10000):
        self.balance = initial_balance
        self.positions = []
        self.orders = []
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> pd.DataFrame:
        """Generate mock OHLCV data"""
        dates = pd.date_range(end=datetime.now(), periods=limit, freq=timeframe)
        
        # Base prices for different symbols
        base_prices = {
            'BTCUSDT': 105000,
            'ETHUSDT': 3500,
            'BNBUSDT': 600,
            'SOLUSDT': 180,
            'ADAUSDT': 0.6,
            'XRPUSDT': 0.7
        }
        
        base = base_prices.get(symbol, 100)
        volatility = base * 0.02  # 2% volatility
        
        data = {
            'timestamp': dates,
            'open': np.zeros(limit),
            'high': np.zeros(limit),
            'low': np.zeros(limit),
            'close': np.zeros(limit),
            'volume': np.random.uniform(1000, 10000, limit)
        }
        
        close = base
        for i in range(limit):
            open_price = close
            change = np.random.normal(0, volatility)
            close = open_price + change
            
            high = max(open_price, close) + abs(np.random.normal(0, volatility/2))
            low = min(open_price, close) - abs(np.random.normal(0, volatility/2))
            
            data['open'][i] = open_price
            data['high'][i] = high
            data['low'][i] = low
            data['close'][i] = close
        
        return pd.DataFrame(data)
    
    async def get_balance(self) -> float:
        """Get current balance"""
        return self.balance
    
    async def place_order(self, symbol: str, side: str, amount: float,
                        entry_price: float, stop_loss: float, take_profit: float) -> dict:
        """Simulate order placement"""
        position = {
            'id': len(self.orders) + 1,
            'symbol': symbol,
            'side': side,
            'amount': amount,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'opened_at': datetime.now(),
            'status': 'open'
        }
        
        self.positions.append(position)
        
        return {
            'status': 'success',
            'position': position,
            'message': f'{side.upper()} {amount} {symbol} @ {entry_price}'
        }
    
    async def get_open_positions(self) -> List[dict]:
        """Get open positions"""
        return [p for p in self.positions if p['status'] == 'open']
    
    async def close_position(self, position_id: int, exit_price: float, reason: str) -> dict:
        """Close a position"""
        for p in self.positions:
            if p['id'] == position_id:
                p['status'] = 'closed'
                p['exit_price'] = exit_price
                p['closed_at'] = datetime.now()
                p['exit_reason'] = reason
                
                # Calculate PnL
                if p['side'] == 'buy':
                    pnl = (exit_price - p['entry_price']) * p['amount']
                else:
                    pnl = (p['entry_price'] - exit_price) * p['amount']
                
                p['pnl'] = pnl
                self.balance += pnl
                
                return {'status': 'success', 'position': p, 'pnl': pnl}
        
        return {'status': 'error', 'message': 'Position not found'}


# Broker Factory
def get_broker(broker_type: str = 'mock', **kwargs) -> BrokerBase:
    """Get broker instance"""
    if broker_type == 'binance':
        return BinanceBroker(**kwargs)
    elif broker_type == 'binance_futures':
        broker = BinanceBroker(**kwargs)
        broker.exchange.options['defaultType'] = 'swap'
        return broker
    else:
        return MockBroker(**kwargs)
