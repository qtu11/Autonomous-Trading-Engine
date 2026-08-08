"""
ICT (Inner Circle Trader) Module
Implements: Killzones, OTE, Judas Swing, PO3/AMD, Daily Levels
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, time
from dataclasses import dataclass


@dataclass
class ICTConfig:
    """ICT Configuration"""
    # Killzones UTC times
    london_kz_start: time = time(8, 0)
    london_kz_end: time = time(9, 0)
    ny_kz_start: time = time(13, 30)
    ny_kz_end: time = time(14, 30)
    asia_kz_start: time = time(0, 0)
    asia_kz_end: time = time(9, 0)
    
    # OTE Fibonacci levels
    ote_382: float = 0.382
    ote_618: float = 0.618
    ote_786: float = 0.786
    
    # Session levels lookback
    session_lookback: int = 50


class KillzoneDetector:
    """
    ICT Killzone Detection
    Implements: London Killzone, NY Killzone, Asia Killzone
    """
    
    def __init__(self, config: Optional[ICTConfig] = None):
        self.config = config or ICTConfig()
    
    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect killzones"""
        df = df.copy()
        
        # Extract time components
        df['hour'] = df['timestamp'].dt.hour
        df['minute'] = df['timestamp'].dt.minute
        df['minute_of_day'] = df['hour'] * 60 + df['minute']
        
        # London Kill Zone (08:00-09:00 UTC)
        london_start_minutes = self.config.london_kz_start.hour * 60 + self.config.london_kz_start.minute
        london_end_minutes = self.config.london_kz_end.hour * 60 + self.config.london_kz_end.minute
        
        df['in_london_kz'] = (
            (df['minute_of_day'] >= london_start_minutes) &
            (df['minute_of_day'] <= london_end_minutes)
        )
        
        # NY Kill Zone (13:30-14:30 UTC-5 = 18:30-19:30 UTC)
        ny_start_minutes = self.config.ny_kz_start.hour * 60 + self.config.ny_kz_start.minute
        ny_end_minutes = self.config.ny_kz_end.hour * 60 + self.config.ny_kz_end.minute
        
        df['in_ny_kz'] = (
            (df['minute_of_day'] >= ny_start_minutes) &
            (df['minute_of_day'] <= ny_end_minutes)
        )
        
        # Asia Kill Zone (00:00-09:00 UTC)
        asia_start_minutes = self.config.asia_kz_start.hour * 60 + self.config.asia_kz_start.minute
        asia_end_minutes = self.config.asia_kz_end.hour * 60 + self.config.asia_kz_end.minute
        
        df['in_asia_kz'] = (
            (df['minute_of_day'] >= asia_start_minutes) &
            (df['minute_of_day'] <= asia_end_minutes)
        )
        
        # Any killzone
        df['in_killzone'] = df['in_london_kz'] | df['in_ny_kz'] | df['in_asia_kz']
        
        return df
    
    def get_killzone_info(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get current killzone status and ranges"""
        df_calc = self.detect(df)
        last = df_calc.iloc[-1]
        
        # Calculate session ranges
        london_range = None
        ny_range = None
        asia_range = None
        
        if last['in_london_kz']:
            recent = df_calc[df_calc['in_london_kz']]
            if len(recent) > 0:
                london_range = {
                    'high': float(recent['high'].max()),
                    'low': float(recent['low'].min()),
                    'high_time': recent.loc[recent['high'].idxmax(), 'timestamp'],
                    'low_time': recent.loc[recent['low'].idxmin(), 'timestamp']
                }
        
        if last['in_ny_kz']:
            recent = df_calc[df_calc['in_ny_kz']]
            if len(recent) > 0:
                ny_range = {
                    'high': float(recent['high'].max()),
                    'low': float(recent['low'].min()),
                    'high_time': recent.loc[recent['high'].idxmax(), 'timestamp'],
                    'low_time': recent.loc[recent['low'].idxmin(), 'timestamp']
                }
        
        if last['in_asia_kz']:
            recent = df_calc[df_calc['in_asia_kz']]
            if len(recent) > 0:
                asia_range = {
                    'high': float(recent['high'].max()),
                    'low': float(recent['low'].min()),
                    'high_time': recent.loc[recent['high'].idxmax(), 'timestamp'],
                    'low_time': recent.loc[recent['low'].idxmin(), 'timestamp']
                }
        
        return {
            'in_london_kz': bool(last['in_london_kz']),
            'in_ny_kz': bool(last['in_ny_kz']),
            'in_asia_kz': bool(last['in_asia_kz']),
            'in_any_kz': bool(last['in_killzone']),
            'active_kz': 'london' if last['in_london_kz'] else 'ny' if last['in_ny_kz'] else 'asia' if last['in_asia_kz'] else None,
            'london_range': london_range,
            'ny_range': ny_range,
            'asia_range': asia_range
        }


class OTECalculator:
    """
    OTE (Optimal Trade Entry) Calculator
    Implements: Fibonacci retracement zones (38.2%, 61.8%, 78.6%)
    """
    
    def __init__(self, config: Optional[ICTConfig] = None):
        self.config = config or ICTConfig()
    
    def calculate_ote(self, df: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
        """Calculate OTE levels"""
        df = df.copy()
        
        # Find swing high and low over lookback
        df['swing_high'] = df['high'].rolling(lookback + 1).max().shift(1)
        df['swing_low'] = df['low'].rolling(lookback + 1).min().shift(1)
        df['swing_range'] = df['swing_high'] - df['swing_low']
        
        # OTE levels
        df['ote_382'] = df['swing_low'] + df['swing_range'] * self.config.ote_382
        df['ote_618'] = df['swing_low'] + df['swing_range'] * self.config.ote_618
        df['ote_786'] = df['swing_low'] + df['swing_range'] * self.config.ote_786
        
        # Check if price is in OTE zone
        df['in_ote_zone'] = (
            (df['close'] >= df['ote_618']) &
            (df['close'] <= df['ote_786'])
        )
        
        return df
    
    def get_ote_info(self, df: pd.DataFrame, lookback: int = 20) -> Dict[str, Any]:
        """Get OTE information"""
        df_calc = self.calculate_ote(df, lookback)
        last = df_calc.iloc[-1]
        
        current_price = last['close']
        ote_382 = float(last['ote_382'])
        ote_618 = float(last['ote_618'])
        ote_786 = float(last['ote_786'])
        swing_high = float(last['swing_high'])
        swing_low = float(last['swing_low'])
        
        # Determine zone
        zone = "below_ote"
        if current_price >= ote_786:
            zone = "above_ote"
        elif current_price >= ote_618:
            zone = "in_ote_zone"
        elif current_price >= ote_382:
            zone = "near_ote"
        
        return {
            'swing_high': swing_high,
            'swing_low': swing_low,
            'swing_range': float(last['swing_range']),
            'ote_382': ote_382,
            'ote_618': ote_618,
            'ote_786': ote_786,
            'current_price': current_price,
            'in_ote_zone': bool(last['in_ote_zone']),
            'zone': zone,
            'ote_distance_pct': ((current_price - ote_618) / ote_618) * 100 if ote_618 > 0 else 0
        }


class JudasSwingDetector:
    """
    Judas Swing Detection
    Bullish Judas: Price extends down, sweeps SSL, then rejects with displacement
    Bearish Judas: Price extends up, sweeps BSL, then rejects with displacement
    """
    
    def __init__(self):
        self.tracking = {
            'bullish': {'swept': False, 'sweep_price': None, 'sweep_time': None},
            'bearish': {'swept': False, 'sweep_price': None, 'sweep_time': None}
        }
    
    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect Judas Swing patterns"""
        df = df.copy()
        lookback = 20
        
        # Swing levels
        df['swing_low'] = df['low'].rolling(lookback + 1).min().shift(1)
        df['swing_high'] = df['high'].rolling(lookback + 1).max().shift(1)
        
        # Calculate displacement for Judas confirmation
        avg_range = (df['high'] - df['low']).rolling(14).mean()
        df['body_ratio'] = abs(df['close'] - df['open']) / (df['high'] - df['low'])
        
        # Bullish Judas Swing: Sweep SSL then bullish displacement
        df['js_bull_sweep'] = (df['low'] < df['swing_low']) & (df['close'] > df['swing_low'])
        df['js_bull_dpl'] = df['body_ratio'] >= 0.65
        df['bullish_judas'] = df['js_bull_sweep'].shift(1) & df['js_bull_dpl']
        
        # Bearish Judas Swing: Sweep BSL then bearish displacement
        df['js_bear_sweep'] = (df['high'] > df['swing_high']) & (df['close'] < df['swing_high'])
        df['js_bear_dpl'] = df['body_ratio'] >= 0.65
        df['bearish_judas'] = df['js_bear_sweep'].shift(1) & df['js_bear_dpl']
        
        return df
    
    def get_judas_info(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get Judas Swing information"""
        df_calc = self.detect(df)
        last = df_calc.iloc[-1]
        
        return {
            'bullish_judas': bool(last.get('bullish_judas', False)),
            'bearish_judas': bool(last.get('bearish_judas', False)),
            'bull_sweep': bool(last.get('js_bull_sweep', False)),
            'bear_sweep': bool(last.get('js_bear_sweep', False)),
            'swing_low': float(last.get('swing_low', 0)),
            'swing_high': float(last.get('swing_high', 0))
        }


class PO3Detector:
    """
    PO3 (Power of Three) / AMD (Accumulation-Manipulation-Distribution) Detector
    
    Bullish PO3:
    - Phase 1: Accumulation - Low volume, tight range
    - Phase 2: Manipulation - Spike down, sweep SSL
    - Phase 3: Distribution - Strong move up with displacement
    
    Bearish PO3:
    - Phase 1: Accumulation
    - Phase 2: Manipulation - Spike up, sweep BSL
    - Phase 3: Distribution - Strong move down with displacement
    """
    
    def __init__(self):
        self.phase = 0  # 0=Normal, 1=Accumulation, 2=Manipulation, 3=Distribution
    
    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect PO3/AMD patterns"""
        df = df.copy()
        
        # Volume analysis
        df['vol_avg'] = df['volume'].rolling(20).mean()
        df['vol_low'] = df['volume'] < df['vol_avg'] * 0.5
        
        # Range analysis
        df['range_avg'] = (df['high'] - df['low']).rolling(20).mean()
        df['range_tight'] = (df['high'] - df['low']) < df['range_avg'] * 0.5
        
        # Displacement
        avg_range = df['range_avg']
        df['body_ratio'] = abs(df['close'] - df['open']) / (df['range_avg'])
        df['bull_dpl'] = (df['body_ratio'] >= 0.65) & (df['close'] > df['open'])
        df['bear_dpl'] = (df['body_ratio'] >= 0.65) & (df['close'] < df['open'])
        
        # Swing levels
        lookback = 20
        df['swing_low'] = df['low'].rolling(lookback + 1).min().shift(1)
        df['swing_high'] = df['high'].rolling(lookback + 1).max().shift(1)
        
        # Manipulation sweep
        df['bull_sweep'] = (df['low'] < df['swing_low']) & (df['close'] > df['swing_low'])
        df['bear_sweep'] = (df['high'] > df['swing_high']) & (df['close'] < df['swing_high'])
        
        return df
    
    def get_po3_info(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get PO3/AMD information"""
        df_calc = self.detect(df)
        last = df_calc.iloc[-1]
        
        return {
            'bull_po3': bool(last.get('bull_dpl', False)) and bool(last.get('bull_sweep', False)),
            'bear_po3': bool(last.get('bear_dpl', False)) and bool(last.get('bear_sweep', False)),
            'accumulation': bool(last.get('vol_low', False)) and bool(last.get('range_tight', False)),
            'manipulation_bull': bool(last.get('bull_sweep', False)),
            'manipulation_bear': bool(last.get('bear_sweep', False)),
            'distribution_bull': bool(last.get('bull_dpl', False)),
            'distribution_bear': bool(last.get('bear_dpl', False))
        }


class DailyLevelsCalculator:
    """
    Daily/Weekly Levels Calculator
    Implements: PDH, PDL, PWH, PWL, R1-R3, S1-S3, Pivot Point
    """
    
    def __init__(self):
        pass
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate daily levels"""
        df = df.copy()
        
        # Get daily data
        df['date'] = df['timestamp'].dt.date
        
        # Group by date
        daily_groups = df.groupby('date').agg({
            'high': 'max',
            'low': 'min',
            'close': 'last'
        })
        
        # Previous day values
        daily_groups['prev_high'] = daily_groups['high'].shift(1)
        daily_groups['prev_low'] = daily_groups['low'].shift(1)
        daily_groups['prev_close'] = daily_groups['close'].shift(1)
        
        # Pivot Point
        daily_groups['pivot'] = (daily_groups['prev_high'] + daily_groups['prev_low'] + daily_groups['prev_close']) / 3
        
        # Support/Resistance
        daily_groups['r1'] = 2 * daily_groups['pivot'] - daily_groups['prev_low']
        daily_groups['s1'] = 2 * daily_groups['pivot'] - daily_groups['prev_high']
        
        daily_groups['r2'] = daily_groups['pivot'] + (daily_groups['prev_high'] - daily_groups['prev_low'])
        daily_groups['s2'] = daily_groups['pivot'] - (daily_groups['prev_high'] - daily_groups['prev_low'])
        
        daily_groups['r3'] = daily_groups['prev_high'] + 2 * (daily_groups['pivot'] - daily_groups['prev_low'])
        daily_groups['s3'] = daily_groups['prev_low'] - 2 * (daily_groups['prev_high'] - daily_groups['pivot'])
        
        # Merge back
        df = df.merge(daily_groups[['pivot', 'r1', 's1', 'r2', 's2', 'r3', 's3', 'high', 'low']], 
                       left_on='date', right_index=True, how='left')
        df = df.ffill()
        
        return df
    
    def get_daily_levels(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get current daily levels"""
        df_calc = self.calculate(df)
        last = df_calc.iloc[-1]
        
        return {
            'pivot': float(last['pivot']),
            'r1': float(last['r1']),
            'r2': float(last['r2']),
            'r3': float(last['r3']),
            's1': float(last['s1']),
            's2': float(last['s2']),
            's3': float(last['s3']),
            'pdh': float(last['high']),
            'pdl': float(last['low']),
            'current_price': float(last['close']),
            
            'above_pivot': float(last['close']) > float(last['pivot']),
            'above_r1': float(last['close']) > float(last['r1']),
            'below_s1': float(last['close']) < float(last['s1'])
        }


class ICTAnalyzer:
    """
    Complete ICT Analysis
    Combines all ICT components
    """
    
    def __init__(self, config: Optional[ICTConfig] = None):
        self.config = config or ICTConfig()
        self.killzones = KillzoneDetector(config)
        self.ote = OTECalculator(config)
        self.judas = JudasSwingDetector()
        self.po3 = PO3Detector()
        self.daily_levels = DailyLevelsCalculator()
    
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Complete ICT analysis"""
        
        # Killzones
        killzone_info = self.killzones.get_killzone_info(df)
        
        # OTE
        ote_info = self.ote.get_ote_info(df)
        
        # Judas Swing
        judas_info = self.judas.get_judas_info(df)
        
        # PO3/AMD
        po3_info = self.po3.get_po3_info(df)
        
        # Daily Levels
        daily_info = self.daily_levels.get_daily_levels(df)
        
        return {
            # Killzones
            'in_killzone': killzone_info['in_any_kz'],
            'active_kz': killzone_info['active_kz'],
            'in_london_kz': killzone_info['in_london_kz'],
            'in_ny_kz': killzone_info['in_ny_kz'],
            'in_asia_kz': killzone_info['in_asia_kz'],
            'kz_london_range': killzone_info['london_range'],
            'kz_ny_range': killzone_info['ny_range'],
            
            # OTE
            'ote_382': ote_info['ote_382'],
            'ote_618': ote_info['ote_618'],
            'ote_786': ote_info['ote_786'],
            'in_ote_zone': ote_info['in_ote_zone'],
            'ote_zone': ote_info['zone'],
            'swing_high': ote_info['swing_high'],
            'swing_low': ote_info['swing_low'],
            
            # Judas Swing
            'bullish_judas': judas_info['bullish_judas'],
            'bearish_judas': judas_info['bearish_judas'],
            'bull_sweep': judas_info['bull_sweep'],
            'bear_sweep': judas_info['bear_sweep'],
            
            # PO3/AMD
            'bull_po3': po3_info['bull_po3'],
            'bear_po3': po3_info['bear_po3'],
            'accumulation': po3_info['accumulation'],
            
            # Daily Levels
            'pivot': daily_info['pivot'],
            'r1': daily_info['r1'],
            'r2': daily_info['r2'],
            'r3': daily_info['r3'],
            's1': daily_info['s1'],
            's2': daily_info['s2'],
            's3': daily_info['s3'],
            'pdh': daily_info['pdh'],
            'pdl': daily_info['pdl'],
            'above_pivot': daily_info['above_pivot'],
            'above_r1': daily_info['above_r1'],
            'below_s1': daily_info['below_s1']
        }
