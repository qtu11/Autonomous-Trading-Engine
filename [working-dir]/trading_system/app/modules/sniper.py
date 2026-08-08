"""
Sniper Core Module
Implements: EMA Ribbon, VWAP, ADX, RSI, MACD, Score System
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class SniperConfig:
    """Sniper Configuration"""
    # EMA
    ema_9_period: int = 9
    ema_21_period: int = 21
    
    # RSI
    rsi_period: int = 14
    rsi_5m_period: int = 14
    
    # ADX
    adx_period: int = 14
    adx_strong_threshold: float = 25.0
    
    # MACD
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    
    # ATR
    atr_period: int = 14
    
    # Volume
    vol_sma_period: int = 20


class EMARibbon:
    """
    EMA Ribbon Indicator
    EMA 9 and EMA 21 with visual ribbon
    """
    
    def __init__(self, config: Optional[SniperConfig] = None):
        self.config = config or SniperConfig()
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate EMA Ribbon"""
        df = df.copy()
        
        # EMA calculations
        df['ema_9'] = df['close'].ewm(span=self.config.ema_9_period, adjust=False).mean()
        df['ema_21'] = df['close'].ewm(span=self.config.ema_21_period, adjust=False).mean()
        
        # Ribbon direction
        df['ribbon_bull'] = df['ema_9'] > df['ema_21']
        df['ribbon_bear'] = df['ema_9'] < df['ema_21']
        
        # Crossover signals
        df['ema_bull_cross'] = (df['ema_9'] > df['ema_21']) & (df['ema_9'].shift(1) <= df['ema_21'].shift(1))
        df['ema_bear_cross'] = (df['ema_9'] < df['ema_21']) & (df['ema_9'].shift(1) >= df['ema_21'].shift(1))
        
        # Ribbon strength (distance between EMAs)
        df['ribbon_distance'] = abs(df['ema_9'] - df['ema_21'])
        df['ribbon_distance_pct'] = (df['ribbon_distance'] / df['close']) * 100
        
        return df
    
    def get_ribbon_info(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get EMA Ribbon status"""
        df_calc = self.calculate(df)
        last = df_calc.iloc[-1]
        
        return {
            'ema_9': float(last['ema_9']),
            'ema_21': float(last['ema_21']),
            'ribbon_bull': bool(last['ribbon_bull']),
            'ribbon_bear': bool(last['ribbon_bear']),
            'ema_bull_cross': bool(last['ema_bull_cross']),
            'ema_bear_cross': bool(last['ema_bear_cross']),
            'ribbon_distance': float(last['ribbon_distance']),
            'ribbon_distance_pct': float(last['ribbon_distance_pct']),
            'ribbon_strength': 'strong' if last['ribbon_distance_pct'] > 1.0 else 'moderate' if last['ribbon_distance_pct'] > 0.5 else 'weak'
        }


class VWAPIndicator:
    """
    Volume Weighted Average Price (VWAP)
    """
    
    def __init__(self):
        pass
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate VWAP"""
        df = df.copy()
        
        # Typical Price
        df['typical'] = (df['high'] + df['low'] + df['close']) / 3
        
        # Cumulative TP * Volume
        df['cum_tp_vol'] = (df['typical'] * df['volume']).cumsum()
        df['cum_vol'] = df['volume'].cumsum()
        
        # VWAP
        df['vwap'] = df['cum_tp_vol'] / df['cum_vol']
        
        # VWAP deviation
        df['vwap_deviation'] = df['close'] - df['vwap']
        df['vwap_deviation_pct'] = (df['vwap_deviation'] / df['vwap']) * 100
        
        # Distance from VWAP
        df['above_vwap'] = df['close'] > df['vwap']
        df['below_vwap'] = df['close'] < df['vwap']
        
        return df
    
    def get_vwap_info(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get VWAP status"""
        df_calc = self.calculate(df)
        last = df_calc.iloc[-1]
        
        return {
            'vwap': float(last['vwap']),
            'price': float(last['close']),
            'above_vwap': bool(last['above_vwap']),
            'below_vwap': bool(last['below_vwap']),
            'vwap_deviation': float(last['vwap_deviation']),
            'vwap_deviation_pct': float(last['vwap_deviation_pct']),
            'strength': abs(last['vwap_deviation_pct'])
        }


class ADXIndicator:
    """
    Average Directional Index (ADX)
    Trend strength measurement
    """
    
    def __init__(self, config: Optional[SniperConfig] = None):
        self.config = config or SniperConfig()
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate ADX"""
        df = df.copy()
        period = self.config.adx_period
        
        # True Range
        df['prev_close'] = df['close'].shift(1)
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['prev_close'])
        df['tr3'] = abs(df['low'] - df['prev_close'])
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        
        # Directional Movement
        df['up_move'] = df['high'] - df['high'].shift(1)
        df['down_move'] = df['low'].shift(1) - df['low']
        
        df['plus_dm'] = np.where(
            (df['up_move'] > df['down_move']) & (df['up_move'] > 0),
            df['up_move'],
            0
        )
        df['minus_dm'] = np.where(
            (df['down_move'] > df['up_move']) & (df['down_move'] > 0),
            df['down_move'],
            0
        )
        
        # Smoothed values
        df['atr'] = df['tr'].rolling(period).mean()
        df['plus_di'] = 100 * (df['plus_dm'].rolling(period).mean() / df['atr'])
        df['minus_di'] = 100 * (df['minus_dm'].rolling(period).mean() / df['atr'])
        
        # DX and ADX
        df['dx'] = 100 * abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])
        df['adx'] = df['dx'].rolling(period).mean()
        
        # Trend strength interpretation
        df['trend_strong'] = df['adx'] > self.config.adx_strong_threshold
        df['trend_weak'] = df['adx'] <= self.config.adx_strong_threshold
        
        return df
    
    def get_adx_info(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get ADX status"""
        df_calc = self.calculate(df)
        last = df_calc.iloc[-1]
        
        return {
            'adx': float(last['adx']),
            'plus_di': float(last['plus_di']),
            'minus_di': float(last['minus_di']),
            'atr': float(last['atr']),
            'trend_strong': bool(last['trend_strong']),
            'trend_weak': bool(last['trend_weak']),
            'strength_level': 'no_trend' if last['adx'] < 20 else 'weak' if last['adx'] < 25 else 'strong' if last['adx'] < 50 else 'very_strong' if last['adx'] < 75 else 'extreme'
        }


class RSIIndicator:
    """
    Relative Strength Index (RSI)
    Momentum oscillator
    """
    
    def __init__(self, config: Optional[SniperConfig] = None):
        self.config = config or SniperConfig()
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate RSI"""
        df = df.copy()
        
        # RSI 14
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.config.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.config.rsi_period).mean()
        rs = gain / loss
        df['rsi_14'] = 100 - (100 / (1 + rs))
        
        # RSI zones
        df['rsi_overbought'] = df['rsi_14'] >= 70
        df['rsi_oversold'] = df['rsi_14'] <= 30
        df['rsi_neutral'] = (df['rsi_14'] > 30) & (df['rsi_14'] < 70)
        
        # Direction
        df['rsi_bullish'] = df['rsi_14'] > 50
        df['rsi_bearish'] = df['rsi_14'] < 50
        
        return df
    
    def get_rsi_info(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get RSI status"""
        df_calc = self.calculate(df)
        last = df_calc.iloc[-1]
        
        return {
            'rsi_14': float(last['rsi_14']),
            'overbought': bool(last['rsi_overbought']),
            'oversold': bool(last['rsi_oversold']),
            'neutral': bool(last['rsi_neutral']),
            'bullish': bool(last['rsi_bullish']),
            'bearish': bool(last['rsi_bearish']),
            'zone': 'overbought' if last['rsi_overbought'] else 'oversold' if last['rsi_oversold'] else 'neutral'
        }


class MACDIndicator:
    """
    Moving Average Convergence Divergence (MACD)
    Trend-following momentum indicator
    """
    
    def __init__(self, config: Optional[SniperConfig] = None):
        self.config = config or SniperConfig()
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate MACD"""
        df = df.copy()
        
        # MACD Line
        ema_fast = df['close'].ewm(span=self.config.macd_fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=self.config.macd_slow, adjust=False).mean()
        df['macd_main'] = ema_fast - ema_slow
        
        # Signal Line
        df['macd_signal'] = df['macd_main'].ewm(span=self.config.macd_signal, adjust=False).mean()
        
        # Histogram
        df['macd_histogram'] = df['macd_main'] - df['macd_signal']
        
        # Direction
        df['macd_bullish'] = df['macd_main'] > df['macd_signal']
        df['macd_bearish'] = df['macd_main'] < df['macd_signal']
        
        # Crossover
        df['macd_bull_cross'] = (df['macd_main'] > df['macd_signal']) & (df['macd_main'].shift(1) <= df['macd_signal'].shift(1))
        df['macd_bear_cross'] = (df['macd_main'] < df['macd_signal']) & (df['macd_main'].shift(1) >= df['macd_signal'].shift(1))
        
        return df
    
    def get_macd_info(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get MACD status"""
        df_calc = self.calculate(df)
        last = df_calc.iloc[-1]
        
        return {
            'macd_main': float(last['macd_main']),
            'macd_signal': float(last['macd_signal']),
            'macd_histogram': float(last['macd_histogram']),
            'bullish': bool(last['macd_bullish']),
            'bearish': bool(last['macd_bearish']),
            'bull_cross': bool(last['macd_bull_cross']),
            'bear_cross': bool(last['macd_bear_cross']),
            'histogram_positive': last['macd_histogram'] > 0,
            'momentum': 'strong_bull' if last['macd_bullish'] and last['macd_histogram'] > 0 else 'strong_bear' if last['macd_bearish'] and last['macd_histogram'] < 0 else 'weak'
        }


class VolumeAnalyzer:
    """
    Volume Analysis
    Average volume and volume spikes
    """
    
    def __init__(self, config: Optional[SniperConfig] = None):
        self.config = config or SniperConfig()
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate volume indicators"""
        df = df.copy()
        
        # SMA
        df['vol_sma'] = df['volume'].rolling(self.config.vol_sma_period).mean()
        
        # Volume comparison
        df['vol_above_avg'] = df['volume'] > df['vol_sma']
        df['vol_below_avg'] = df['volume'] <= df['vol_sma']
        
        # Volume ratio
        df['vol_ratio'] = df['volume'] / df['vol_sma']
        
        # High volume spikes
        df['vol_spike'] = df['volume'] > df['vol_sma'] * 1.5
        df['vol_drop'] = df['volume'] < df['vol_sma'] * 0.5
        
        return df
    
    def get_volume_info(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get volume status"""
        df_calc = self.calculate(df)
        last = df_calc.iloc[-1]
        
        return {
            'volume': float(last['volume']),
            'vol_avg': float(last['vol_sma']),
            'vol_ratio': float(last['vol_ratio']),
            'above_average': bool(last['vol_above_avg']),
            'below_average': bool(last['vol_below_avg']),
            'spike': bool(last['vol_spike']),
            'drop': bool(last['vol_drop']),
            'level': 'high' if last['vol_spike'] else 'low' if last['vol_drop'] else 'normal'
        }


class SniperScorer:
    """
    Sniper Dual Score System
    Scores from 0-100% for both bull and bear
    """
    
    def __init__(self):
        pass
    
    def calculate_scores(self, indicators: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate sniper scores"""
        
        bull_score = 0.0
        bear_score = 0.0
        max_score = 7.0
        
        # Factor 1: Price vs VWAP
        if indicators.get('price_above_vwap', False):
            bull_score += 1
        if indicators.get('price_below_vwap', False):
            bear_score += 1
        
        # Factor 2: RSI(14)
        if indicators.get('rsi_14', 50) > 50:
            bull_score += 1
        if indicators.get('rsi_14', 50) < 50:
            bear_score += 1
        
        # Factor 3: MACD
        if indicators.get('macd_bullish', False):
            bull_score += 1
        if indicators.get('macd_bearish', False):
            bear_score += 1
        
        # Factor 4: EMA Cross
        if indicators.get('ribbon_bull', False):
            bull_score += 1
        if indicators.get('ribbon_bear', False):
            bear_score += 1
        
        # Factor 5: ADX Filter
        if indicators.get('adx_strong', False) and indicators.get('price_above_ema9', False):
            bull_score += 1
        if indicators.get('adx_strong', False) and indicators.get('price_below_ema9', False):
            bear_score += 1
        
        # Factor 6: Volume
        if indicators.get('vol_above_avg', False) and indicators.get('is_bullish', False):
            bull_score += 1
        if indicators.get('vol_above_avg', False) and indicators.get('is_bearish', False):
            bear_score += 1
        
        # Factor 7: RSI 5m (if available)
        if indicators.get('rsi_5m', 50) > 50:
            bull_score += 1
        if indicators.get('rsi_5m', 50) < 50:
            bear_score += 1
        
        # Convert to percentage
        bull_pct = (bull_score / max_score) * 100
        bear_pct = (bear_score / max_score) * 100
        
        return {
            'bull_score': bull_score,
            'bear_score': bear_score,
            'bull_pct': bull_pct,
            'bear_pct': bear_pct,
            'score_diff': bull_pct - bear_pct,
            'bull_strong': bull_pct >= 70,
            'bear_strong': bear_pct >= 70
        }


class SniperAnalyzer:
    """
    Complete Sniper Analysis
    Combines all Sniper indicators
    """
    
    def __init__(self, config: Optional[SniperConfig] = None):
        self.config = config or SniperConfig()
        self.ema = EMARibbon(config)
        self.vwap = VWAPIndicator()
        self.adx = ADXIndicator(config)
        self.rsi = RSIIndicator(config)
        self.macd = MACDIndicator(config)
        self.volume = VolumeAnalyzer(config)
        self.scorer = SniperScorer()
    
    def analyze(self, df: pd.DataFrame, rsi_5m: float = 50) -> Dict[str, Any]:
        """Complete Sniper analysis"""
        
        # Calculate all indicators
        df_ema = self.ema.calculate(df)
        df_vwap = self.vwap.calculate(df)
        df_adx = self.adx.calculate(df)
        df_rsi = self.rsi.calculate(df)
        df_macd = self.macd.calculate(df)
        df_vol = self.volume.calculate(df)
        
        # Get individual statuses
        ema_info = self.ema.get_ribbon_info(df)
        vwap_info = self.vwap.get_vwap_info(df)
        adx_info = self.adx.get_adx_info(df)
        rsi_info = self.rsi.get_rsi_info(df)
        macd_info = self.macd.get_macd_info(df)
        vol_info = self.volume.get_volume_info(df)
        
        # Build indicators dict for scoring
        indicators = {
            'price_above_vwap': vwap_info['above_vwap'],
            'price_below_vwap': vwap_info['below_vwap'],
            'rsi_14': rsi_info['rsi_14'],
            'macd_bullish': macd_info['bullish'],
            'macd_bearish': macd_info['bearish'],
            'ribbon_bull': ema_info['ribbon_bull'],
            'ribbon_bear': ema_info['ribbon_bear'],
            'adx_strong': adx_info['trend_strong'],
            'price_above_ema9': df_ema['close'].iloc[-1] > ema_info['ema_9'],
            'price_below_ema9': df_ema['close'].iloc[-1] < ema_info['ema_9'],
            'vol_above_avg': vol_info['above_average'],
            'is_bullish': df['close'].iloc[-1] > df['open'].iloc[-1],
            'is_bearish': df['close'].iloc[-1] < df['open'].iloc[-1],
            'rsi_5m': rsi_5m
        }
        
        # Calculate scores
        scores = self.scorer.calculate_scores(indicators)
        
        return {
            # EMA
            'ema_9': ema_info['ema_9'],
            'ema_21': ema_info['ema_21'],
            'ribbon_bull': ema_info['ribbon_bull'],
            'ribbon_bear': ema_info['ribbon_bear'],
            'ema_bull_cross': ema_info['ema_bull_cross'],
            'ema_bear_cross': ema_info['ema_bear_cross'],
            'ribbon_strength': ema_info['ribbon_strength'],
            
            # VWAP
            'vwap': vwap_info['vwap'],
            'price_above_vwap': vwap_info['above_vwap'],
            'price_below_vwap': vwap_info['below_vwap'],
            'vwap_deviation_pct': vwap_info['vwap_deviation_pct'],
            
            # ADX
            'adx': adx_info['adx'],
            'adx_strong': adx_info['trend_strong'],
            'adx_level': adx_info['strength_level'],
            
            # RSI
            'rsi_14': rsi_info['rsi_14'],
            'rsi_bullish': rsi_info['bullish'],
            'rsi_bearish': rsi_info['bearish'],
            'rsi_zone': rsi_info['zone'],
            
            # MACD
            'macd_main': macd_info['macd_main'],
            'macd_signal': macd_info['macd_signal'],
            'macd_histogram': macd_info['macd_histogram'],
            'macd_bullish': macd_info['bullish'],
            'macd_bearish': macd_info['bearish'],
            'macd_momentum': macd_info['momentum'],
            
            # Volume
            'volume': vol_info['volume'],
            'vol_avg': vol_info['vol_avg'],
            'vol_high': vol_info['above_average'],
            'vol_spike': vol_info['spike'],
            
            # ATR
            'atr': adx_info['atr'],
            
            # Scores
            'sniper_bull_score': scores['bull_score'],
            'sniper_bear_score': scores['bear_score'],
            'sniper_bull_pct': scores['bull_pct'],
            'sniper_bear_pct': scores['bear_pct'],
            'sniper_score_diff': scores['score_diff'],
            'sniper_bull_strong': scores['bull_strong'],
            'sniper_bear_strong': scores['bear_strong']
        }
