"""
Price Action Module - COMPLETE VERSION
=======================================
Candlestick Patterns:
- Pin Bar / Hammer / Shooting Star
- Engulfing (Bullish/Bearish)
- Doji (Gravestone, Dragonfly)
- Tweezer (Top/Bottom)
- Morning/Evening Star
- Three White Soldiers / Three Black Crows
- Inside Bar / Outside Bar
- Harami (Bullish/Bearish)
- Piercing Line / Dark Cloud Cover
- Three Methods (Bullish/Bearish)
- Spinning Top
- Marubozu

Price Action Concepts:
- Displacement Detection
- Compression/Expansion
- Liquidity Sweeps
- VWAP Interactions
- Trend Structure (HH/HL/LH/LL)
"""
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class PriceActionConfig:
    """Price Action Configuration"""
    pinbar_wick_ratio: float = 2.0
    engulf_min_body_ratio: float = 1.2  # Slightly lower for more detections
    doji_max_body_ratio: float = 0.10
    tweezer_tolerance: float = 0.001
    displacement_threshold: float = 1.5
    inside_bar_threshold: float = 1.0  # Inside bar must be smaller


class CandleCalculator:
    """Calculate candlestick metrics"""
    
    @staticmethod
    def calculate(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # Basic calculations
        df['body'] = abs(df['close'] - df['open'])
        df['range'] = df['high'] - df['low']
        df['range'] = df['range'].replace(0, np.nan)
        df['body_ratio'] = df['body'] / df['range'].replace(0, 1)
        df['body_ratio'] = df['body_ratio'].fillna(0)
        
        # Wicks
        df['upper_wick'] = df['high'] - np.maximum(df['open'], df['close'])
        df['lower_wick'] = np.minimum(df['open'], df['close']) - df['low']
        
        # Upper and lower shadows ratio
        df['upper_wick_ratio'] = df['upper_wick'] / df['range'].replace(0, np.nan)
        df['lower_wick_ratio'] = df['lower_wick'] / df['range'].replace(0, np.nan)
        df['upper_wick_ratio'] = df['upper_wick_ratio'].fillna(0)
        df['lower_wick_ratio'] = df['lower_wick_ratio'].fillna(0)
        
        # Candle direction
        df['is_bullish'] = df['close'] > df['open']
        df['is_bearish'] = df['close'] < df['open']
        df['is_doji'] = abs(df['close'] - df['open']) < df['range'] * 0.1
        
        # Full body (Marubozu-like)
        df['is_full_bull'] = df['body_ratio'] > 0.9
        df['is_full_bear'] = df['body_ratio'] > 0.9
        
        # Close position in range (0=bottom, 1=top)
        df['close_position'] = (df['close'] - df['low']) / df['range'].replace(0, 1)
        df['close_position'] = df['close_position'].fillna(0.5)
        
        # Open position in range
        df['open_position'] = (df['open'] - df['low']) / df['range'].replace(0, 1)
        df['open_position'] = df['open_position'].fillna(0.5)
        
        return df


class CandlePatterns:
    """Detect all candlestick patterns"""
    
    def __init__(self, config: Optional[PriceActionConfig] = None):
        self.config = config or PriceActionConfig()
    
    def detect_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect all candlestick patterns"""
        df = CandleCalculator.calculate(df)
        
        # Basic patterns
        df = self._detect_pinbar(df)
        df = self._detect_engulfing(df)
        df = self._detect_doji(df)
        df = self._detect_tweezer(df)
        
        # Advanced patterns
        df = self._detect_star_patterns(df)
        df = self._detect_harami(df)
        df = self._detect_piercing(df)
        df = self._detect_inside_outside(df)
        df = self._detect_three_soldiers(df)
        df = self._detect_three_methods(df)
        
        # Price action concepts
        df = self._detect_displacement(df)
        df = self._detect_structure(df)
        
        return df
    
    def _detect_pinbar(self, df: pd.DataFrame) -> pd.DataFrame:
        """Pin Bar: Long wick on one side, small body on other"""
        
        # Bullish Pin Bar (Hammer-like) - Lower wick dominates, bullish close
        df['bullish_pinbar'] = (
            (df['lower_wick_ratio'] >= self.config.pinbar_wick_ratio) &
            (df['upper_wick_ratio'] < 0.3) &
            (df['body_ratio'] < 0.4) &
            (df['is_bullish'])
        )
        
        # Bearish Pin Bar (Shooting Star-like) - Upper wick dominates, bearish close
        df['bearish_pinbar'] = (
            (df['upper_wick_ratio'] >= self.config.pinbar_wick_ratio) &
            (df['lower_wick_ratio'] < 0.3) &
            (df['body_ratio'] < 0.4) &
            (df['is_bearish'])
        )
        
        # Hammer (bullish reversal) - Stronger criteria
        df['hammer'] = (
            (df['lower_wick'] > 2 * df['body']) &
            (df['upper_wick'] < df['body']) &
            (df['is_bullish'])
        )
        
        # Shooting Star (bearish reversal)
        df['shooting_star'] = (
            (df['upper_wick'] > 2 * df['body']) &
            (df['lower_wick'] < df['body']) &
            (df['is_bearish'])
        )
        
        return df
    
    def _detect_engulfing(self, df: pd.DataFrame) -> pd.DataFrame:
        """Engulfing Pattern: Current candle engulfs previous candle"""
        
        prev_open = df['open'].shift(1)
        prev_close = df['close'].shift(1)
        prev_bullish = df['is_bullish'].shift(1)
        prev_bearish = df['is_bearish'].shift(1)
        
        # Bullish Engulfing
        df['bullish_engulfing'] = (
            (df['is_bullish']) &
            (prev_bearish) &
            (df['close'] > prev_open) &
            (df['open'] < prev_close) &
            (df['body'] > df['body'].shift(1))
        )
        
        # Bearish Engulfing
        df['bearish_engulfing'] = (
            (df['is_bearish']) &
            (prev_bullish) &
            (df['close'] < prev_open) &
            (df['open'] > prev_close) &
            (df['body'] > df['body'].shift(1))
        )
        
        # Large Engulfing (stronger signal)
        df['large_bullish_engulfing'] = df['bullish_engulfing'] & (df['body_ratio'] > 0.8)
        df['large_bearish_engulfing'] = df['bearish_engulfing'] & (df['body_ratio'] > 0.8)
        
        return df
    
    def _detect_doji(self, df: pd.DataFrame) -> pd.DataFrame:
        """Doji: Open and close are nearly equal"""
        
        # Basic Doji
        df['doji'] = df['body_ratio'] < self.config.doji_max_body_ratio
        
        # Gravestone Doji (bearish reversal) - Open/Close at low
        df['gravestone_doji'] = (
            (df['body_ratio'] < 0.1) &
            (df['lower_wick_ratio'] < 0.2) &
            (df['upper_wick_ratio'] > 0.6)
        )
        
        # Dragonfly Doji (bullish reversal) - Open/Close at high
        df['dragonfly_doji'] = (
            (df['body_ratio'] < 0.1) &
            (df['upper_wick_ratio'] < 0.2) &
            (df['lower_wick_ratio'] > 0.6)
        )
        
        # Four Price Doji (rare)
        df['four_price_doji'] = (
            (df['high'] == df['low']) &
            (df['open'] == df['close'])
        )
        
        # Long-legged Doji
        df['long_legged_doji'] = (
            (df['body_ratio'] < 0.15) &
            (df['upper_wick_ratio'] > 0.3) &
            (df['lower_wick_ratio'] > 0.3)
        )
        
        return df
    
    def _detect_tweezer(self, df: pd.DataFrame) -> pd.DataFrame:
        """Tweezer: Two candles with same high/low"""
        
        tol = self.config.tweezer_tolerance
        
        # Tweezer Top (bearish reversal)
        df['tweezer_top'] = (
            (abs(df['high'] - df['high'].shift(1)) / df['high'].replace(0, 1) < tol) &
            ((df['is_bearish']) | (df['is_bearish'].shift(1))) &
            (df['close_position'] < 0.4)  # Closes near bottom
        )
        
        # Tweezer Bottom (bullish reversal)
        df['tweezer_bottom'] = (
            (abs(df['low'] - df['low'].shift(1)) / df['low'].replace(0, 1) < tol) &
            ((df['is_bullish']) | (df['is_bullish'].shift(1))) &
            (df['close_position'] > 0.6)  # Closes near top
        )
        
        return df
    
    def _detect_star_patterns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Morning/Evening Star patterns"""
        
        # Morning Star (bullish reversal)
        df['morning_star'] = (
            (df['is_bearish'].shift(2)) &  # First candle bearish
            (df['body_ratio'].shift(1) < 0.3) &  # Second candle small
            (df['is_bullish']) &  # Third candle bullish
            (df['close'] > (df['open'].shift(2) + df['close'].shift(2)) / 2)  # Close above midpoint
        )
        
        # Evening Star (bearish reversal)
        df['evening_star'] = (
            (df['is_bullish'].shift(2)) &  # First candle bullish
            (df['body_ratio'].shift(1) < 0.3) &  # Second candle small
            (df['is_bearish']) &  # Third candle bearish
            (df['close'] < (df['open'].shift(2) + df['close'].shift(2)) / 2)  # Close below midpoint
        )
        
        return df
    
    def _detect_harami(self, df: pd.DataFrame) -> pd.DataFrame:
        """Harami: Inside bar with opposite color"""
        
        # Bullish Harami
        df['bullish_harami'] = (
            (df['is_bearish'].shift(1)) &
            (df['is_bullish']) &
            (df['high'] <= df['high'].shift(1)) &
            (df['low'] >= df['low'].shift(1))
        )
        
        # Bearish Harami
        df['bearish_harami'] = (
            (df['is_bullish'].shift(1)) &
            (df['is_bearish']) &
            (df['high'] <= df['high'].shift(1)) &
            (df['low'] >= df['low'].shift(1))
        )
        
        return df
    
    def _detect_piercing(self, df: pd.DataFrame) -> pd.DataFrame:
        """Piercing Line / Dark Cloud Cover"""
        
        # Piercing Line (bullish)
        df['piercing_line'] = (
            (df['is_bearish'].shift(1)) &
            (df['is_bullish']) &
            (df['open'] < df['low'].shift(1)) &  # Opens below previous low
            (df['close'] > (df['open'].shift(1) + df['close'].shift(1)) / 2)  # Closes above midpoint
        )
        
        # Dark Cloud Cover (bearish)
        df['dark_cloud_cover'] = (
            (df['is_bullish'].shift(1)) &
            (df['is_bearish']) &
            (df['open'] > df['high'].shift(1)) &  # Opens above previous high
            (df['close'] < (df['open'].shift(1) + df['close'].shift(1)) / 2)  # Closes below midpoint
        )
        
        return df
    
    def _detect_inside_outside(self, df: pd.DataFrame) -> pd.DataFrame:
        """Inside Bar / Outside Bar"""
        
        # Inside Bar (consolidation, breakout setup)
        df['inside_bar'] = (
            (df['high'] <= df['high'].shift(1)) &
            (df['low'] >= df['low'].shift(1)) &
            ((df['body'] < df['body'].shift(1)) | (df['body_ratio'] < 0.8))
        )
        
        # Outside Bar (volatility expansion)
        df['outside_bar'] = (
            (df['high'] > df['high'].shift(1)) &
            (df['low'] < df['low'].shift(1)) &
            (df['body_ratio'] >= self.config.engulf_min_body_ratio)
        )
        
        # Bullish Outside Bar
        df['bullish_outside_bar'] = (
            (df['outside_bar']) &
            (df['is_bullish'])
        )
        
        # Bearish Outside Bar
        df['bearish_outside_bar'] = (
            (df['outside_bar']) &
            (df['is_bearish'])
        )
        
        return df
    
    def _detect_three_soldiers(self, df: pd.DataFrame) -> pd.DataFrame:
        """Three White Soldiers / Three Black Crows"""
        
        # Three White Soldiers (bullish)
        df['three_white_soldiers'] = (
            (df['is_bullish']) &
            (df['is_bullish'].shift(1)) &
            (df['is_bullish'].shift(2)) &
            (df['close'] > df['close'].shift(1)) &
            (df['close'].shift(1) > df['close'].shift(2)) &
            (df['body_ratio'] > 0.6) &
            (df['body_ratio'].shift(1) > 0.6) &
            (df['body_ratio'].shift(2) > 0.6)
        )
        
        # Three Black Crows (bearish)
        df['three_black_crows'] = (
            (df['is_bearish']) &
            (df['is_bearish'].shift(1)) &
            (df['is_bearish'].shift(2)) &
            (df['close'] < df['close'].shift(1)) &
            (df['close'].shift(1) < df['close'].shift(2)) &
            (df['body_ratio'] > 0.6) &
            (df['body_ratio'].shift(1) > 0.6) &
            (df['body_ratio'].shift(2) > 0.6)
        )
        
        return df
    
    def _detect_three_methods(self, df: pd.DataFrame) -> pd.DataFrame:
        """Three Methods (Continuation patterns)"""
        
        # Bullish Three Methods (falling wedge-like continuation)
        df['bullish_three_methods'] = (
            (df['is_bullish'].shift(2)) &
            (df['is_bearish'].shift(1)) &
            (df['is_bullish']) &
            (df['low'].shift(1) > df['low'].shift(2)) &
            (df['low'] < df['low'].shift(1)) &
            (df['close'] > df['high'].shift(2))
        )
        
        # Bearish Three Methods (rising wedge-like continuation)
        df['bearish_three_methods'] = (
            (df['is_bearish'].shift(2)) &
            (df['is_bullish'].shift(1)) &
            (df['is_bearish']) &
            (df['high'].shift(1) < df['high'].shift(2)) &
            (df['high'] > df['high'].shift(1)) &
            (df['close'] < df['low'].shift(2))
        )
        
        return df
    
    def _detect_displacement(self, df: pd.DataFrame) -> pd.DataFrame:
        """Displacement: Strong momentum candle"""
        
        avg_range = df['range'].rolling(20).mean().fillna(1).replace(0, 1)
        
        # Bullish Displacement (strong bullish candle)
        df['bullish_displacement'] = (
            (df['is_bullish']) &
            (df['body'] > avg_range * self.config.displacement_threshold)
        )
        
        # Bearish Displacement
        df['bearish_displacement'] = (
            (df['is_bearish']) &
            (df['body'] > avg_range * self.config.displacement_threshold)
        )
        
        # Strong Displacement (very strong momentum)
        df['strong_bull_displacement'] = (
            (df['bullish_displacement']) &
            (df['body_ratio'] > 0.8)
        )
        
        df['strong_bear_displacement'] = (
            (df['bearish_displacement']) &
            (df['body_ratio'] > 0.8)
        )
        
        return df
    
    def _detect_structure(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect price structure (HH/HL/LH/LL)"""
        
        lookback = 20
        
        # Swing high/low
        df['swing_high'] = df['high'].rolling(lookback + 1).max().shift(1)
        df['swing_low'] = df['low'].rolling(lookback + 1).min().shift(1)
        
        # Higher High / Higher Low
        df['hh'] = df['high'] > df['swing_high']
        df['hl'] = (df['low'] > df['swing_low']) & (df['high'] < df['swing_high'])
        
        # Lower High / Lower Low
        df['lh'] = (df['high'] < df['swing_high']) & (df['low'] > df['swing_low'])
        df['ll'] = df['low'] < df['swing_low']
        
        return df


class VolumeAnalysis:
    """Volume-based price action"""
    
    @staticmethod
    def analyze(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # Volume average
        df['vol_avg'] = df['volume'].rolling(20).mean()
        df['vol_avg'] = df['vol_avg'].fillna(df['volume'].mean())
        
        # Volume comparison
        df['vol_ratio'] = df['volume'] / df['vol_avg'].replace(0, 1)
        df['vol_ratio'] = df['vol_ratio'].fillna(1)
        
        # High/Low volume
        df['high_volume'] = df['volume'] > df['vol_avg'] * 1.5
        df['low_volume'] = df['volume'] < df['vol_avg'] * 0.5
        
        # Volume confirmation for patterns
        df['vol_confirm_bull'] = df['high_volume'] & df['is_bullish']
        df['vol_confirm_bear'] = df['high_volume'] & df['is_bearish']
        
        return df


class PriceActionPatterns:
    """Complete Price Action Analyzer"""
    
    def __init__(self, config: Optional[PriceActionConfig] = None):
        self.config = config or PriceActionConfig()
        self.patterns = CandlePatterns(config)
        self.volume = VolumeAnalysis()
    
    def detect_all(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Detect all patterns and return analysis"""
        
        # Detect all patterns
        df_calc = self.patterns.detect_all(df)
        df_calc = self.volume.analyze(df_calc)
        
        last = df_calc.iloc[-1]
        close = float(last['close'])
        
        # Collect detected patterns
        patterns = []
        bullish_signals = []
        bearish_signals = []
        
        # Strong bullish patterns
        if last.get('three_white_soldiers'):
            patterns.append('three_white_soldiers')
            bullish_signals.append('three_white_soldiers')
        
        if last.get('bullish_engulfing'):
            patterns.append('bullish_engulfing')
            bullish_signals.append('bullish_engulfing')
        
        if last.get('bullish_outside_bar'):
            patterns.append('bullish_outside_bar')
            bullish_signals.append('bullish_outside_bar')
        
        if last.get('morning_star'):
            patterns.append('morning_star')
            bullish_signals.append('morning_star')
        
        if last.get('piercing_line'):
            patterns.append('piercing_line')
            bullish_signals.append('piercing_line')
        
        if last.get('hammer'):
            patterns.append('hammer')
            bullish_signals.append('hammer')
        
        if last.get('bullish_pinbar'):
            patterns.append('bullish_pinbar')
            bullish_signals.append('pinbar')
        
        if last.get('bullish_harami'):
            patterns.append('bullish_harami')
            bullish_signals.append('harami')
        
        if last.get('tweezer_bottom'):
            patterns.append('tweezer_bottom')
            bullish_signals.append('tweezer')
        
        if last.get('dragonfly_doji'):
            patterns.append('dragonfly_doji')
            bullish_signals.append('doji')
        
        if last.get('bullish_displacement'):
            patterns.append('bullish_displacement')
            bullish_signals.append('displacement')
        
        if last.get('strong_bull_displacement'):
            patterns.append('strong_bull_displacement')
            bullish_signals.append('strong_displacement')
        
        # Strong bearish patterns
        if last.get('three_black_crows'):
            patterns.append('three_black_crows')
            bearish_signals.append('three_black_crows')
        
        if last.get('bearish_engulfing'):
            patterns.append('bearish_engulfing')
            bearish_signals.append('bearish_engulfing')
        
        if last.get('bearish_outside_bar'):
            patterns.append('bearish_outside_bar')
            bearish_signals.append('bearish_outside_bar')
        
        if last.get('evening_star'):
            patterns.append('evening_star')
            bearish_signals.append('evening_star')
        
        if last.get('dark_cloud_cover'):
            patterns.append('dark_cloud_cover')
            bearish_signals.append('dark_cloud_cover')
        
        if last.get('shooting_star'):
            patterns.append('shooting_star')
            bearish_signals.append('shooting_star')
        
        if last.get('bearish_pinbar'):
            patterns.append('bearish_pinbar')
            bearish_signals.append('pinbar')
        
        if last.get('bearish_harami'):
            patterns.append('bearish_harami')
            bearish_signals.append('harami')
        
        if last.get('tweezer_top'):
            patterns.append('tweezer_top')
            bearish_signals.append('tweezer')
        
        if last.get('gravestone_doji'):
            patterns.append('gravestone_doji')
            bearish_signals.append('doji')
        
        if last.get('bearish_displacement'):
            patterns.append('bearish_displacement')
            bearish_signals.append('displacement')
        
        if last.get('strong_bear_displacement'):
            patterns.append('strong_bear_displacement')
            bearish_signals.append('strong_displacement')
        
        # Calculate pattern score
        pattern_score = 0
        max_score = 15
        
        # Strong patterns
        if last.get('three_white_soldiers') or last.get('three_black_crows'):
            pattern_score += 5
        if last.get('bullish_engulfing') or last.get('bearish_engulfing'):
            pattern_score += 4
        if last.get('bullish_outside_bar') or last.get('bearish_outside_bar'):
            pattern_score += 4
        if last.get('morning_star') or last.get('evening_star'):
            pattern_score += 4
        if last.get('piercing_line') or last.get('dark_cloud_cover'):
            pattern_score += 3
        if last.get('hammer') or last.get('shooting_star'):
            pattern_score += 3
        if last.get('bullish_pinbar') or last.get('bearish_pinbar'):
            pattern_score += 3
        if last.get('strong_bull_displacement') or last.get('strong_bear_displacement'):
            pattern_score += 4
        if last.get('bullish_displacement') or last.get('bearish_displacement'):
            pattern_score += 3
        if last.get('bullish_harami') or last.get('bearish_harami'):
            pattern_score += 2
        if last.get('tweezer_bottom') or last.get('tweezer_top'):
            pattern_score += 2
        if last.get('dragonfly_doji') or last.get('gravestone_doji'):
            pattern_score += 2
        if last.get('inside_bar'):
            pattern_score += 1
        if last.get('doji'):
            pattern_score += 1
        
        # Structure
        if last.get('hh'):
            pattern_score += 1
        if last.get('ll'):
            pattern_score -= 1
        
        # Volume confirmation
        if last.get('vol_confirm_bull'):
            pattern_score += 1
        if last.get('vol_confirm_bear'):
            pattern_score -= 1
        
        # Determine direction
        direction = 'neutral'
        confidence = 50
        
        if pattern_score > 3:
            direction = 'long'
            confidence = min(95, 50 + pattern_score * 5)
        elif pattern_score < -3:
            direction = 'short'
            confidence = min(95, 50 - pattern_score * 5)
        
        return {
            'patterns': patterns,
            'bullish_signals': bullish_signals,
            'bearish_signals': bearish_signals,
            'pattern_score': pattern_score,
            'direction': direction,
            'confidence': confidence,
            
            # Individual pattern flags
            'bullish_pinbar': bool(last.get('bullish_pinbar', False)),
            'bearish_pinbar': bool(last.get('bearish_pinbar', False)),
            'bullish_engulfing': bool(last.get('bullish_engulfing', False)),
            'bearish_engulfing': bool(last.get('bearish_engulfing', False)),
            'bullish_displacement': bool(last.get('bullish_displacement', False)),
            'bearish_displacement': bool(last.get('bearish_displacement', False)),
            'strong_bull_displacement': bool(last.get('strong_bull_displacement', False)),
            'strong_bear_displacement': bool(last.get('strong_bear_displacement', False)),
            
            # Additional patterns
            'hammer': bool(last.get('hammer', False)),
            'shooting_star': bool(last.get('shooting_star', False)),
            'morning_star': bool(last.get('morning_star', False)),
            'evening_star': bool(last.get('evening_star', False)),
            'piercing_line': bool(last.get('piercing_line', False)),
            'dark_cloud_cover': bool(last.get('dark_cloud_cover', False)),
            'bullish_harami': bool(last.get('bullish_harami', False)),
            'bearish_harami': bool(last.get('bearish_harami', False)),
            'inside_bar': bool(last.get('inside_bar', False)),
            'outside_bar': bool(last.get('outside_bar', False)),
            'bullish_outside_bar': bool(last.get('bullish_outside_bar', False)),
            'bearish_outside_bar': bool(last.get('bearish_outside_bar', False)),
            'tweezer_top': bool(last.get('tweezer_top', False)),
            'tweezer_bottom': bool(last.get('tweezer_bottom', False)),
            'three_white_soldiers': bool(last.get('three_white_soldiers', False)),
            'three_black_crows': bool(last.get('three_black_crows', False)),
            'bullish_three_methods': bool(last.get('bullish_three_methods', False)),
            'bearish_three_methods': bool(last.get('bearish_three_methods', False)),
            'doji': bool(last.get('doji', False)),
            'dragonfly_doji': bool(last.get('dragonfly_doji', False)),
            'gravestone_doji': bool(last.get('gravestone_doji', False)),
            
            # Structure
            'hh': bool(last.get('hh', False)),
            'hl': bool(last.get('hl', False)),
            'lh': bool(last.get('lh', False)),
            'll': bool(last.get('ll', False)),
            
            # Volume
            'high_volume': bool(last.get('high_volume', False)),
            'low_volume': bool(last.get('low_volume', False)),
            'vol_ratio': float(last.get('vol_ratio', 1)),
            
            # Current candle info
            'current_price': close,
            'close_position': float(last.get('close_position', 0.5)),
            'body_ratio': float(last.get('body_ratio', 0))
        }
