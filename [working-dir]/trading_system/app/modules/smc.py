"""
Smart Money Concepts (SMC) Module
Standalone version - no external dependencies
FIXED: Division by zero, NaN handling, circular reference
"""
import numpy as np
import pandas as pd
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class SMCConfig:
    """SMC Configuration"""
    swing_lookback: int = 20
    fvg_lookback: int = 3
    equal_tolerance: float = 0.001
    ob_min_body_ratio: float = 0.60
    atr_period: int = 14


def ta_highest(series: pd.Series, period: int) -> pd.Series:
    """Calculate highest over period"""
    return series.rolling(period + 1).max().shift(1)


def ta_lowest(series: pd.Series, period: int) -> pd.Series:
    """Calculate lowest over period"""
    return series.rolling(period + 1).min().shift(1)


class MarketStructure:
    """Market Structure Detection: HH, HL, LH, LL, BOS, CHoCH, MSS"""
    
    def __init__(self, config: Optional[SMCConfig] = None):
        self.config = config or SMCConfig()
    
    def detect_swings(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        lookback = self.config.swing_lookback
        
        df['swing_high'] = df['high'].rolling(lookback + 1).max().shift(1)
        df['is_swing_high'] = (df['high'] == df['swing_high']) & (df['high'] > df['high'].shift(1)) & (df['high'] > df['high'].shift(-1))
        
        df['swing_low'] = df['low'].rolling(lookback + 1).min().shift(1)
        df['is_swing_low'] = (df['low'] == df['swing_low']) & (df['low'] < df['low'].shift(1)) & (df['low'] < df['low'].shift(-1))
        
        df['swing_high_price'] = np.where(df['is_swing_high'], df['high'], np.nan)
        df['swing_low_price'] = np.where(df['is_swing_low'], df['low'], np.nan)
        
        return df
    
    def calculate_structure(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self.detect_swings(df)
        
        df['prev_swing_high'] = df['swing_high'].shift(1)
        df['prev_swing_low'] = df['swing_low'].shift(1)
        df['current_swing_high'] = df['swing_high_price']
        df['current_swing_low'] = df['swing_low_price']
        
        df['hh'] = df['high'] > df['prev_swing_high']
        df['hl'] = (df['low'] > df['prev_swing_low']) & (df['high'] < df['prev_swing_high'])
        df['lh'] = (df['high'] < df['prev_swing_high']) & (df['low'] < df['prev_swing_low'])
        df['ll'] = df['low'] < df['prev_swing_low']
        
        df['bull_structure'] = df['hh'] | df['hl']
        df['bear_structure'] = df['lh'] | df['ll']
        
        return df
    
    def get_structure(self, df: pd.DataFrame) -> dict:
        df_calc = self.calculate_structure(df)
        last = df_calc.iloc[-1]
        
        def safe_val(key, default=None):
            val = last.get(key)
            if val is None or pd.isna(val):
                return default
            return float(val)
        
        return {
            'swing_high': safe_val('swing_high'),
            'swing_low': safe_val('swing_low'),
            'prev_swing_high': safe_val('prev_swing_high', 0),
            'prev_swing_low': safe_val('prev_swing_low', 0),
            'hh': bool(last.get('hh', False)),
            'hl': bool(last.get('hl', False)),
            'lh': bool(last.get('lh', False)),
            'll': bool(last.get('ll', False)),
            'bull_structure': bool(last.get('bull_structure', False)),
            'bear_structure': bool(last.get('bear_structure', False)),
            'is_swing_high': bool(last.get('is_swing_high', False)),
            'is_swing_low': bool(last.get('is_swing_low', False))
        }


class FVGDetector:
    """Fair Value Gap Detection"""
    
    def __init__(self, config: Optional[SMCConfig] = None):
        self.config = config or SMCConfig()
        self.fvg_zones: List[Dict] = []
    
    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        lookback = self.config.fvg_lookback
        
        df['mid1'] = df['high'].shift(1)
        df['mid2'] = df['low'].shift(1)
        
        df['gap_up'] = df['low'] > df['high'].shift(2)
        df['gap_down'] = df['high'] < df['low'].shift(2)
        
        df['bull_fvg'] = df['gap_up']
        df['bear_fvg'] = df['gap_down']
        
        df['fvg_mid_bull'] = (df['high'].shift(2) + df['low']) / 2
        df['fvg_mid_bear'] = (df['low'].shift(2) + df['high']) / 2
        
        self.fvg_zones = []
        for i in range(2, len(df)):
            if df['bull_fvg'].iloc[i]:
                zone = {
                    'index': i, 'type': 'bull',
                    'top': float(df['high'].iloc[i-1]),
                    'bottom': float(df['low'].iloc[i]),
                    'mid': float((df['high'].iloc[i-1] + df['low'].iloc[i]) / 2)
                }
                self.fvg_zones.append(zone)
            if df['bear_fvg'].iloc[i]:
                zone = {
                    'index': i, 'type': 'bear',
                    'top': float(df['low'].iloc[i-1]),
                    'bottom': float(df['high'].iloc[i]),
                    'mid': float((df['low'].iloc[i-1] + df['high'].iloc[i]) / 2)
                }
                self.fvg_zones.append(zone)
        
        return df
    
    def get_fvg_info(self, df: pd.DataFrame) -> dict:
        df_calc = self.detect(df)
        last = df_calc.iloc[-1]
        
        recent_bull = df_calc[df_calc['bull_fvg']].tail(3)
        recent_bear = df_calc[df_calc['bear_fvg']].tail(3)
        
        bull_filled = bear_filled = False
        for _, row in recent_bull.iterrows():
            if last['close'] >= row['fvg_mid_bull']:
                bull_filled = True
        for _, row in recent_bear.iterrows():
            if last['close'] <= row['fvg_mid_bear']:
                bear_filled = True
        
        return {
            'bull_fvg': bool(last.get('bull_fvg', False)),
            'bear_fvg': bool(last.get('bear_fvg', False)),
            'recent_bull_fvg': len(recent_bull) > 0,
            'recent_bear_fvg': len(recent_bear) > 0,
            'fvg_filled': {'bull': bull_filled, 'bear': bear_filled},
            'fvg_zones': self.fvg_zones[-5:] if self.fvg_zones else []
        }


class OrderBlockDetector:
    """Order Block Detection"""
    
    def __init__(self, config: Optional[SMCConfig] = None):
        self.config = config or SMCConfig()
    
    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        lookback = 5
        
        avg_range = (df['high'] - df['low']).rolling(14).mean().fillna(1).replace(0, 1)
        df['body_ratio'] = abs(df['close'] - df['open']) / avg_range
        
        df['bullish_bar'] = (df['close'] > df['open']) & (df['body_ratio'] >= self.config.ob_min_body_ratio)
        df['bearish_bar'] = (df['close'] < df['open']) & (df['body_ratio'] >= self.config.ob_min_body_ratio)
        
        df['bull_ob'] = df['bullish_bar'] & df['low'].rolling(lookback).min().shift(1).notna()
        df['bear_ob'] = df['bearish_bar'] & df['high'].rolling(lookback).max().shift(1).notna()
        
        return df
    
    def get_ob_info(self, df: pd.DataFrame) -> dict:
        df_calc = self.detect(df)
        last = df_calc.iloc[-1]
        
        recent_bull_ob = df_calc[df_calc['bull_ob']].tail(3)
        recent_bear_ob = df_calc[df_calc['bear_ob']].tail(3)
        
        return {
            'bull_order_block': bool(last.get('bull_ob', False)),
            'bear_order_block': bool(last.get('bear_ob', False)),
            'recent_bull_ob': len(recent_bull_ob) > 0,
            'recent_bear_ob': len(recent_bear_ob) > 0
        }


class LiquidityZones:
    """Liquidity Zone Detection"""
    
    def __init__(self):
        self.zones = []
    
    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        lookback = 20
        
        df['swing_high'] = df['high'].rolling(lookback + 1).max().shift(1)
        df['swing_low'] = df['low'].rolling(lookback + 1).min().shift(1)
        
        df['near_swing_high'] = df['high'] >= df['swing_high'] * 0.999
        df['near_swing_low'] = df['low'] <= df['swing_low'] * 1.001
        
        return df
    
    def get_liquidity_info(self, df: pd.DataFrame) -> dict:
        df_calc = self.detect(df)
        last = df_calc.iloc[-1]
        
        return {
            'near_swing_high': bool(last.get('near_swing_high', False)),
            'near_swing_low': bool(last.get('near_swing_low', False)),
            'swing_high': float(last.get('swing_high', 0)) if pd.notna(last.get('swing_high')) else 0,
            'swing_low': float(last.get('swing_low', 0)) if pd.notna(last.get('swing_low')) else 0
        }


class MSSDetector:
    """Market Structure Shift Detection"""
    
    def __init__(self):
        self.trend = 'neutral'
        self.last_swing = None
    
    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        lookback = 20
        
        df['swing_high'] = df['high'].rolling(lookback + 1).max().shift(1)
        df['swing_low'] = df['low'].rolling(lookback + 1).min().shift(1)
        
        df['prev_swing_high'] = df['swing_high'].shift(1)
        df['prev_swing_low'] = df['swing_low'].shift(1)
        
        df['mss_bull'] = (df['close'] > df['prev_swing_high']) & (df['close'] > df['swing_high'].shift(1))
        df['mss_bear'] = (df['close'] < df['prev_swing_low']) & (df['close'] < df['swing_low'].shift(1))
        
        return df
    
    def get_mss_info(self, df: pd.DataFrame) -> dict:
        df_calc = self.detect(df)
        last = df_calc.iloc[-1]
        
        return {
            'bull_mss': bool(last.get('mss_bull', False)),
            'bear_mss': bool(last.get('mss_bear', False))
        }


class SMCAnalyzer:
    """Main SMC Analyzer combining all components"""
    
    def __init__(self, config: Optional[SMCConfig] = None):
        self.config = config or SMCConfig()
        self.structure = MarketStructure(config)
        self.fvg = FVGDetector(config)
        self.ob = OrderBlockDetector(config)
        self.liquidity = LiquidityZones()
        self.mss = MSSDetector()
    
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        struct = self.structure.get_structure(df)
        fvg_info = self.fvg.get_fvg_info(df)
        ob_info = self.ob.get_ob_info(df)
        liq_info = self.liquidity.get_liquidity_info(df)
        mss_info = self.mss.get_mss_info(df)
        
        return {
            'swing_high': struct['swing_high'],
            'swing_low': struct['swing_low'],
            'bull_structure': struct['bull_structure'],
            'bear_structure': struct['bear_structure'],
            'hh': struct['hh'], 'hl': struct['hl'],
            'lh': struct['lh'], 'll': struct['ll'],
            'bull_fvg': fvg_info['bull_fvg'],
            'bear_fvg': fvg_info['bear_fvg'],
            'fvg_filled': fvg_info['fvg_filled'],
            'bull_order_block': ob_info['bull_order_block'],
            'bear_order_block': ob_info['bear_order_block'],
            'near_swing_high': liq_info['near_swing_high'],
            'near_swing_low': liq_info['near_swing_low'],
            'bull_mss': mss_info['bull_mss'],
            'bear_mss': mss_info['bear_mss'],
            'is_swing_high': struct['is_swing_high'],
            'is_swing_low': struct['is_swing_low']
        }
