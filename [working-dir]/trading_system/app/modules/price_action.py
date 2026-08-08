"""
Candlestick Price Action Patterns
Based on the comprehensive specification
"""
import numpy as np
import pandas as pd
from typing import List, Tuple, Optional
from dataclasses import dataclass
from app.models.data_models import PatternType, CandleMetrics


@dataclass
class PriceActionConfig:
    """Price Action configuration"""
    pinbar_wick_ratio: float = 2.0
    engulf_min_body_ratio: float = 1.5
    doji_max_body_ratio: float = 0.10
    tweezer_tolerance: float = 0.001


class CandleCalculator:
    """Calculate candlestick metrics"""
    
    @staticmethod
    def calculate(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all candlestick metrics"""
        df = df.copy()
        
        # Basic OHLCV
        df['body'] = abs(df['close'] - df['open'])
        df['range'] = df['high'] - df['low']
        df['upper_wick'] = df['high'] - np.maximum(df['open'], df['close'])
        df['lower_wick'] = np.minimum(df['open'], df['close']) - df['low']
        
        # Ratios
        df['body_ratio'] = np.where(df['range'] > 0, df['body'] / df['range'], 0)
        df['upper_wick_ratio'] = np.where(df['range'] > 0, df['upper_wick'] / df['range'], 0)
        df['lower_wick_ratio'] = np.where(df['range'] > 0, df['lower_wick'] / df['range'], 0)
        
        # Direction
        df['is_bullish'] = df['close'] > df['open']
        df['is_bearish'] = df['close'] < df['open']
        
        # Special candles
        df['is_doji'] = df['body'] <= df['range'] * 0.10
        df['is_strong_bull'] = df['is_bullish'] & (df['body_ratio'] >= 0.60) & (df['close'] > df['high'] - df['range'] * 0.10)
        df['is_strong_bear'] = df['is_bearish'] & (df['body_ratio'] >= 0.60) & (df['close'] < df['low'] + df['range'] * 0.10)
        
        # Hammer / Shooting Star
        df['is_hammer'] = (df['lower_wick_ratio'] >= 2 * df['body_ratio']) & (df['upper_wick_ratio'] <= df['body_ratio'] * 0.5)
        df['is_shooting_star'] = (df['upper_wick_ratio'] >= 2 * df['body_ratio']) & (df['lower_wick_ratio'] <= df['body_ratio'] * 0.5)
        
        return df
    
    @staticmethod
    def get_metrics(row: pd.Series) -> CandleMetrics:
        """Get CandleMetrics from row"""
        return CandleMetrics(
            body=row.get('body', 0),
            range_cand=row.get('range', 0),
            upper_wick=row.get('upper_wick', 0),
            lower_wick=row.get('lower_wick', 0),
            body_ratio=row.get('body_ratio', 0),
            upper_wick_ratio=row.get('upper_wick_ratio', 0),
            lower_wick_ratio=row.get('lower_wick_ratio', 0),
            is_bullish=row.get('is_bullish', False),
            is_bearish=row.get('is_bearish', False),
            is_doji=row.get('is_doji', False),
            is_strong_bull=row.get('is_strong_bull', False),
            is_strong_bear=row.get('is_strong_bear', False),
            is_hammer=row.get('is_hammer', False),
            is_shooting_star=row.get('is_shooting_star', False)
        )


class PriceActionPatterns:
    """
    Price Action Pattern Detection
    
    Implements:
    - Pin Bar / Rejection
    - Engulfing
    - Inside Bar / Outside Bar
    - Tweezer
    - Morning/Evening Star
    - Three White Soldiers / Black Crows
    - Displacement Candles
    """
    
    def __init__(self, config: Optional[PriceActionConfig] = None):
        self.config = config or PriceActionConfig()
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all price action patterns"""
        df = df.copy()
        df = CandleCalculator.calculate(df)
        
        # ─── PIN BAR / REJECTION ───
        df['bullish_pinbar'] = (
            (df['lower_wick_ratio'] >= self.config.pinbar_wick_ratio * df['body_ratio']) &
            (df['upper_wick_ratio'] <= df['body_ratio'] * 0.5) &
            df['is_bullish']
        )
        df['bearish_pinbar'] = (
            (df['upper_wick_ratio'] >= self.config.pinbar_wick_ratio * df['body_ratio']) &
            (df['lower_wick_ratio'] <= df['body_ratio'] * 0.5) &
            df['is_bearish']
        )
        
        # Rejection (not pin bar but long wick)
        df['bullish_rejection'] = (
            (df['lower_wick_ratio'] > df['upper_wick_ratio']) &
            df['is_bullish'] &
            (df['close'] > df['low'] + df['range'] * 0.65)
        )
        df['bearish_rejection'] = (
            (df['upper_wick_ratio'] > df['lower_wick_ratio']) &
            df['is_bearish'] &
            (df['close'] < df['high'] - df['range'] * 0.65)
        )
        
        # ─── ENGULFING ───
        avg_range = df['range'].rolling(10).mean()
        df['bullish_engulfing'] = (
            df['is_bearish'].shift(1) &
            df['is_bullish'] &
            (df['open'] <= df['close'].shift(1)) &
            (df['close'] >= df['open'].shift(1)) &
            (df['body'] > avg_range * self.config.engulf_min_body_ratio)
        )
        df['bearish_engulfing'] = (
            df['is_bullish'].shift(1) &
            df['is_bearish'] &
            (df['open'] >= df['close'].shift(1)) &
            (df['close'] <= df['open'].shift(1)) &
            (df['body'] > avg_range * self.config.engulf_min_body_ratio)
        )
        
        # ─── INSIDE BAR ───
        df['inside_bar'] = (df['high'] < df['high'].shift(1)) & (df['low'] > df['low'].shift(1))
        df['inside_bull_break'] = df['inside_bar'] & (df['close'] > df['high'].shift(1))
        df['inside_bear_break'] = df['inside_bar'] & (df['close'] < df['low'].shift(1))
        
        # ─── OUTSIDE BAR ───
        df['outside_bar'] = (df['high'] > df['high'].shift(1)) & (df['low'] < df['low'].shift(1))
        df['obar_bullish'] = df['outside_bar'] & df['is_bullish']
        df['obar_bearish'] = df['outside_bar'] & df['is_bearish']
        
        # Tweezer
        tolerance = self.config.tweezer_tolerance
        df['tweezer_top'] = (
            (abs(df['high'] - df['high'].shift(1)) <= tolerance) &
            df['is_bearish'] &
            ~df['is_bullish'].shift(1)
        )
        df['tweezer_bottom'] = (
            (abs(df['low'] - df['low'].shift(1)) <= tolerance) &
            df['is_bullish'] &
            ~df['is_bearish'].shift(1)
        )
        
        # ─── MORNING / EVENING STAR ───
        df['morning_star'] = (
            df['is_bearish'].shift(2) &
            (abs(df['close'].shift(1) - df['open'].shift(1)) < df['range'].shift(2) * 0.30) &
            df['is_bullish'] &
            (df['close'] > df['open'].shift(2) + df['range'].shift(2) * 0.50)
        )
        df['evening_star'] = (
            df['is_bullish'].shift(2) &
            (abs(df['close'].shift(1) - df['open'].shift(1)) < df['range'].shift(2) * 0.30) &
            df['is_bearish'] &
            (df['close'] < df['open'].shift(2) - df['range'].shift(2) * 0.50)
        )
        
        # ─── THREE WHITE SOLDIERS / BLACK CROWS ───
        df['three_white_soldiers'] = (
            df['is_bullish'].shift(2) &
            df['is_bullish'].shift(1) &
            df['is_bullish'] &
            (df['close'] > df['close'].shift(1)) &
            (df['close'].shift(1) > df['close'].shift(2)) &
            (df['close'] > df['high'].shift(2) - df['range'].shift(2) * 0.10)
        )
        df['three_black_crows'] = (
            df['is_bearish'].shift(2) &
            df['is_bearish'].shift(1) &
            df['is_bearish'] &
            (df['close'] < df['close'].shift(1)) &
            (df['close'].shift(1) < df['close'].shift(2)) &
            (df['close'] < df['low'].shift(2) + df['range'].shift(2) * 0.10)
        )
        
        # ─── DISPLACEMENT CANDLES ───
        avg_r = df['range'].rolling(14).mean()
        df['bullish_displacement'] = (
            df['is_bullish'] &
            (df['body_ratio'] >= 0.65) &
            (df['range'] > avg_r) &
            (df['close'] > df['high'] - df['range'] * 0.15)
        )
        df['bearish_displacement'] = (
            df['is_bearish'] &
            (df['body_ratio'] >= 0.65) &
            (df['range'] > avg_r) &
            (df['close'] < df['low'] + df['range'] * 0.15)
        )
        
        return df
    
    def detect_all(self, df: pd.DataFrame) -> dict:
        """Detect all patterns for current candle"""
        df_calc = self.calculate(df)
        last = df_calc.iloc[-1]
        
        patterns = []
        pattern_scores = []
        
        # Bullish patterns
        if last['bullish_pinbar']:
            patterns.append(PatternType.BULLISH_PINBAR)
            pattern_scores.append(1)
        if last['bullish_engulfing']:
            patterns.append(PatternType.BULLISH_ENGULFING)
            pattern_scores.append(1)
        if last['bullish_rejection']:
            patterns.append(PatternType.BULLISH_REJECTION)
            pattern_scores.append(1)
        if last['is_hammer']:
            patterns.append(PatternType.HAMMER)
            pattern_scores.append(1)
        if last['morning_star']:
            patterns.append(PatternType.MORNING_STAR)
            pattern_scores.append(1)
        if last['tweezer_bottom']:
            patterns.append(PatternType.TWEEZER_BOTTOM)
            pattern_scores.append(1)
        if last['three_white_soldiers']:
            patterns.append(PatternType.THREE_WHITE_SOLDIERS)
            pattern_scores.append(2)  # Stronger pattern
        if last['inside_bull_break']:
            patterns.append(PatternType.INSIDE_BULL_BREAK)
            pattern_scores.append(1)
        if last['bullish_displacement']:
            pattern_scores.append(2)
            
        # Bearish patterns
        if last['bearish_pinbar']:
            patterns.append(PatternType.BEARISH_PINBAR)
            pattern_scores.append(1)
        if last['bearish_engulfing']:
            patterns.append(PatternType.BEARISH_ENGULFING)
            pattern_scores.append(1)
        if last['bearish_rejection']:
            patterns.append(PatternType.BEARISH_REJECTION)
            pattern_scores.append(1)
        if last['is_shooting_star']:
            patterns.append(PatternType.SHOOTING_STAR)
            pattern_scores.append(1)
        if last['evening_star']:
            patterns.append(PatternType.EVENING_STAR)
            pattern_scores.append(1)
        if last['tweezer_top']:
            patterns.append(PatternType.TWEEZER_TOP)
            pattern_scores.append(1)
        if last['three_black_crows']:
            patterns.append(PatternType.THREE_BLACK_CROWS)
            pattern_scores.append(2)
        if last['inside_bear_break']:
            patterns.append(PatternType.INSIDE_BEAR_BREAK)
            pattern_scores.append(1)
        if last['bearish_displacement']:
            pattern_scores.append(2)
        
        return {
            'patterns': [p.value for p in patterns],
            'pattern_score': sum(pattern_scores),
            'bullish_patterns': [p.value for p in patterns if 'bullish' in p.value or 'bull' in p.value],
            'bearish_patterns': [p.value for p in patterns if 'bearish' in p.value or 'bear' in p.value],
            'bullish_score': sum(s for i, s in enumerate(pattern_scores) if i < len([p for p in patterns if 'bullish' in p.value or 'bull' in p.value])),
            'bearish_score': sum(s for i, s in enumerate(pattern_scores) if i >= len([p for p in patterns if 'bullish' in p.value or 'bull' in p.value])),
            'bullish_pinbar': last['bullish_pinbar'],
            'bearish_pinbar': last['bearish_pinbar'],
            'bullish_engulfing': last['bullish_engulfing'],
            'bearish_engulfing': last['bearish_engulfing'],
            'bullish_rejection': last['bullish_rejection'],
            'bearish_rejection': last['bearish_rejection'],
            'bullish_displacement': last['bullish_displacement'],
            'bearish_displacement': last['bearish_displacement'],
            'inside_bar': last['inside_bar'],
            'outside_bar': last['outside_bar'],
            'tweezer_top': last['tweezer_top'],
            'tweezer_bottom': last['tweezer_bottom'],
            'morning_star': last['morning_star'],
            'evening_star': last['evening_star'],
            'three_white_soldiers': last['three_white_soldiers'],
            'three_black_crows': last['three_black_crows']
        }
    
    def get_bullish_signals(self, df: pd.DataFrame) -> List[str]:
        """Get list of bullish signals"""
        detection = self.detect_all(df)
        return [p for p in detection['patterns'] if 'bullish' in p or 'bull' in p]
    
    def get_bearish_signals(self, df: pd.DataFrame) -> List[str]:
        """Get list of bearish signals"""
        detection = self.detect_all(df)
        return [p for p in detection['patterns'] if 'bearish' in p or 'bear' in p]
