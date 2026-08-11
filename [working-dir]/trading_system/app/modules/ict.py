"""
ICT (Inner Circle Trader) Module - COMPLETE VERSION
=====================================================
Features:
- Killzones (London, NY, Asia, Midnight-Midnight)
- OTE (Optimal Trade Entry) Fibonacci
- Daily Levels (PDH, PDL, Pivot, R1-R3, S1-S3)
- Fair Value Gap (FVG / BISI / SIBI)
- Order Blocks (Bullish, Bearish)
- Institutional Order Blocks (IOB)
- Auto Anchored VWAP
- 8/8 EMA Line
- Liquidity Sweeps (BSL/SSL Detection)
- Midnight Midnight Range
- Open of the Day (OD)
- Weekly/Monthly Levels
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, time, timedelta
from dataclasses import dataclass


@dataclass
class ICTConfig:
    """ICT Configuration"""
    # Killzone Times (UTC)
    london_kz_start: time = time(8, 0)
    london_kz_end: time = time(11, 0)  # Extended to 11:00
    
    ny_kz_am_start: time = time(13, 30)
    ny_kz_am_end: time = time(16, 0)
    
    ny_kz_pm_start: time = time(17, 0)  # PM session
    ny_kz_pm_end: time = time(21, 0)
    
    asia_kz_start: time = time(0, 0)
    asia_kz_end: time = time(9, 0)
    
    # Midnight-Midnight (for Asian Range)
    midnight_start: time = time(0, 0)
    midnight_end: time = time(8, 0)
    
    # OTE Fibonacci levels
    ote_382: float = 0.382
    ote_618: float = 0.618
    ote_786: float = 0.786
    
    # Swing lookback
    swing_lookback: int = 20
    
    # Displacement threshold
    displacement_threshold: float = 1.5
    
    # Order block body ratio
    ob_min_body_ratio: float = 0.60


class KillzoneDetector:
    """Detect ICT Killzones with Midnight-Midnight Range"""
    
    def __init__(self, config: Optional[ICTConfig] = None):
        self.config = config or ICTConfig()
    
    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Convert to UTC for comparison
        df['hour'] = df['timestamp'].dt.hour
        df['minute'] = df['timestamp'].dt.minute
        df['minute_of_day'] = df['hour'] * 60 + df['minute']
        df['day_of_week'] = df['timestamp'].dt.dayofweek  # 0=Monday
        
        # Midnight-Midnight Range (00:00-08:00 UTC) - Asian Session High/Low
        midnight_start = 0  # 00:00
        midnight_end = 480  # 08:00
        df['in_midnight_range'] = (df['minute_of_day'] >= midnight_start) & (df['minute_of_day'] < midnight_end)
        
        # London Killzone (08:00-11:00 UTC)
        london_start = self.config.london_kz_start.hour * 60
        london_end = self.config.london_kz_end.hour * 60
        df['in_london_kz'] = (df['minute_of_day'] >= london_start) & (df['minute_of_day'] <= london_end)
        
        # NY AM Killzone (13:30-16:00 UTC)
        ny_am_start = self.config.ny_kz_am_start.hour * 60 + self.config.ny_kz_am_start.minute
        ny_am_end = self.config.ny_kz_am_end.hour * 60
        df['in_ny_am_kz'] = (df['minute_of_day'] >= ny_am_start) & (df['minute_of_day'] <= ny_am_end)
        
        # NY PM Killzone (17:00-21:00 UTC)
        ny_pm_start = self.config.ny_kz_pm_start.hour * 60
        ny_pm_end = self.config.ny_kz_pm_end.hour * 60
        df['in_ny_pm_kz'] = (df['minute_of_day'] >= ny_pm_start) & (df['minute_of_day'] <= ny_pm_end)
        
        # Combined NY KZ
        df['in_ny_kz'] = df['in_ny_am_kz'] | df['in_ny_pm_kz']
        
        # Asia Killzone (00:00-09:00 UTC)
        asia_start = self.config.asia_kz_start.hour * 60
        asia_end = self.config.asia_kz_end.hour * 60
        df['in_asia_kz'] = (df['minute_of_day'] >= asia_start) & (df['minute_of_day'] <= asia_end)
        
        # Any Killzone active
        df['in_killzone'] = df['in_london_kz'] | df['in_ny_kz'] | df['in_asia_kz']
        
        # Weekend filter (skip Sat/Sun for some concepts)
        df['is_weekend'] = df['day_of_week'].isin([5, 6])  # Saturday, Sunday
        
        return df
    
    def get_killzone_info(self, df: pd.DataFrame) -> Dict[str, Any]:
        df_calc = self.detect(df)
        last = df_calc.iloc[-1]
        
        # Calculate ranges for each killzone
        london_range = None
        ny_range = None
        asia_range = None
        midnight_range = None
        
        if last.get('in_london_kz') or True:  # Calculate range regardless
            london_data = df_calc[df_calc['in_london_kz']]
            if len(london_data) > 0:
                london_range = {
                    'high': float(london_data['high'].max()),
                    'low': float(london_data['low'].min()),
                    'range': float(london_data['high'].max() - london_data['low'].min())
                }
        
        if last.get('in_ny_kz') or True:
            ny_data = df_calc[df_calc['in_ny_kz']]
            if len(ny_data) > 0:
                ny_range = {
                    'high': float(ny_data['high'].max()),
                    'low': float(ny_data['low'].min()),
                    'range': float(ny_data['high'].max() - ny_data['low'].min())
                }
        
        # Midnight-Midnight range (Asian session high/low)
        midnight_data = df_calc[df_calc['in_midnight_range']]
        if len(midnight_data) > 0:
            midnight_range = {
                'high': float(midnight_data['high'].max()),
                'low': float(midnight_data['low'].min())
            }
        
        # Determine active killzone
        active_kz = None
        if last.get('in_london_kz'):
            active_kz = 'london'
        elif last.get('in_ny_am_kz') or last.get('in_ny_pm_kz'):
            active_kz = 'ny'
        elif last.get('in_asia_kz'):
            active_kz = 'asia'
        
        return {
            'in_london_kz': bool(last.get('in_london_kz', False)),
            'in_ny_kz': bool(last.get('in_ny_kz', False)),
            'in_ny_am_kz': bool(last.get('in_ny_am_kz', False)),
            'in_ny_pm_kz': bool(last.get('in_ny_pm_kz', False)),
            'in_asia_kz': bool(last.get('in_asia_kz', False)),
            'in_midnight_range': bool(last.get('in_midnight_range', False)),
            'in_any_kz': bool(last.get('in_killzone', False)),
            'active_kz': active_kz,
            'is_weekend': bool(last.get('is_weekend', False)),
            'london_range': london_range,
            'ny_range': ny_range,
            'asia_range': asia_range,
            'midnight_range': midnight_range
        }


class OTECalculator:
    """Calculate Optimal Trade Entry (Fibonacci Retracement)"""
    
    def __init__(self, config: Optional[ICTConfig] = None):
        self.config = config or ICTConfig()
    
    def calculate(self, df: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
        df = df.copy()
        
        # Calculate swings
        df['swing_high'] = df['high'].rolling(lookback + 1).max().shift(1)
        df['swing_low'] = df['low'].rolling(lookback + 1).min().shift(1)
        df['swing_range'] = df['swing_high'] - df['swing_low']
        
        # OTE Fibonacci levels
        df['ote_382'] = df['swing_low'] + df['swing_range'] * self.config.ote_382
        df['ote_618'] = df['swing_low'] + df['swing_range'] * self.config.ote_618
        df['ote_786'] = df['swing_low'] + df['swing_range'] * self.config.ote_786
        
        # Extended levels
        df['ote_127'] = df['swing_low'] + df['swing_range'] * 1.27
        df['ote_161'] = df['swing_low'] + df['swing_range'] * 1.61
        
        # In OTE zone (between 61.8% and 78.6%)
        df['in_ote_zone'] = (df['close'] >= df['ote_618']) & (df['close'] <= df['ote_786'])
        
        # At OTE level
        df['at_ote_618'] = abs(df['close'] - df['ote_618']) / df['ote_618'] < 0.001
        df['at_ote_786'] = abs(df['close'] - df['ote_786']) / df['ote_786'] < 0.001
        
        return df
    
    def get_ote_info(self, df: pd.DataFrame, lookback: int = 20) -> Dict[str, Any]:
        df_calc = self.calculate(df, lookback)
        last = df_calc.iloc[-1]
        close = float(last['close'])
        
        def safe_val(key, default=None):
            val = last.get(key)
            if pd.isna(val) if isinstance(val, float) else val is None:
                return default if default is not None else close
            return float(val)
        
        swing_high = safe_val('swing_high')
        swing_low = safe_val('swing_low')
        ote_382 = safe_val('ote_382')
        ote_618 = safe_val('ote_618')
        ote_786 = safe_val('ote_786')
        
        # Determine zone
        zone = "outside_ote"
        if close >= ote_786:
            zone = "above_ote"
        elif close >= ote_618:
            zone = "in_ote_zone"
        elif close >= ote_382:
            zone = "below_ote"
        else:
            zone = "deep_discount"
        
        # Distance from OTE levels
        distance_from_618 = ((close - ote_618) / close * 100) if close > 0 else 0
        distance_from_786 = ((close - ote_786) / close * 100) if close > 0 else 0
        
        return {
            'swing_high': swing_high,
            'swing_low': swing_low,
            'swing_range': float(last.get('swing_range', swing_high - swing_low)),
            'ote_382': ote_382,
            'ote_618': ote_618,
            'ote_786': ote_786,
            'ote_127': safe_val('ote_127'),
            'ote_161': safe_val('ote_161'),
            'current_price': close,
            'in_ote_zone': bool(last.get('in_ote_zone', False)),
            'at_ote_618': bool(last.get('at_ote_618', False)),
            'at_ote_786': bool(last.get('at_ote_786', False)),
            'zone': zone,
            'distance_from_618_pct': distance_from_618,
            'distance_from_786_pct': distance_from_786
        }


class FairValueGapDetector:
    """Detect Fair Value Gaps (BISI/SIBI)"""
    
    def __init__(self, config: Optional[ICTConfig] = None):
        self.config = config or ICTConfig()
        self.gaps: List[Dict] = []
    
    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # Bullish FVG (BISI - Buyside Imbalance Sellside Inefficiency)
        # Low of current candle > High of candle 2 bars ago
        df['bull_fvg'] = df['low'] > df['high'].shift(2)
        
        # Bearish FVG (SIBI - Sellside Imbalance Buyside Inefficiency)
        # High of current candle < Low of candle 2 bars ago
        df['bear_fvg'] = df['high'] < df['low'].shift(2)
        
        # FVG Zone (top and bottom of the gap)
        df['bull_fvg_top'] = df['high'].shift(1)
        df['bull_fvg_bottom'] = df['low']
        df['bull_fvg_mid'] = (df['bull_fvg_top'] + df['bull_fvg_bottom']) / 2
        
        df['bear_fvg_top'] = df['low']
        df['bear_fvg_bottom'] = df['high'].shift(1)
        df['bear_fvg_mid'] = (df['bear_fvg_top'] + df['bear_fvg_bottom']) / 2
        
        # FVG Size
        df['bull_fvg_size'] = df['bull_fvg_top'] - df['bull_fvg_bottom']
        df['bear_fvg_size'] = df['bear_fvg_bottom'] - df['bear_fvg_top']
        
        # Track gaps
        self.gaps = []
        for i in range(2, len(df)):
            if df['bull_fvg'].iloc[i]:
                self.gaps.append({
                    'index': i,
                    'type': 'bull',
                    'top': float(df['bull_fvg_top'].iloc[i]),
                    'bottom': float(df['bull_fvg_bottom'].iloc[i]),
                    'mid': float(df['bull_fvg_mid'].iloc[i]),
                    'size': float(df['bull_fvg_size'].iloc[i]),
                    'timestamp': df['timestamp'].iloc[i] if 'timestamp' in df.columns else None
                })
            if df['bear_fvg'].iloc[i]:
                self.gaps.append({
                    'index': i,
                    'type': 'bear',
                    'top': float(df['bear_fvg_top'].iloc[i]),
                    'bottom': float(df['bear_fvg_bottom'].iloc[i]),
                    'mid': float(df['bear_fvg_mid'].iloc[i]),
                    'size': float(df['bear_fvg_size'].iloc[i]),
                    'timestamp': df['timestamp'].iloc[i] if 'timestamp' in df.columns else None
                })
        
        return df
    
    def get_fvg_info(self, df: pd.DataFrame) -> Dict[str, Any]:
        df_calc = self.detect(df)
        last = df_calc.iloc[-1]
        close = float(last['close'])
        
        # Check if recent FVGs exist
        recent_bull_fvg = df_calc[df_calc['bull_fvg']].tail(5)
        recent_bear_fvg = df_calc[df_calc['bear_fvg']].tail(5)
        
        # Check if FVGs are filled
        bull_fvg_filled = False
        bear_fvg_filled = False
        
        for _, row in recent_bull_fvg.iterrows():
            if close < float(row['bull_fvg_mid']):
                bull_fvg_filled = True
                break
        
        for _, row in recent_bear_fvg.iterrows():
            if close > float(row['bear_fvg_mid']):
                bear_fvg_filled = True
                break
        
        return {
            'bull_fvg': bool(last.get('bull_fvg', False)),
            'bear_fvg': bool(last.get('bear_fvg', False)),
            'bull_fvg_top': float(last.get('bull_fvg_top', 0)),
            'bull_fvg_bottom': float(last.get('bull_fvg_bottom', 0)),
            'bull_fvg_mid': float(last.get('bull_fvg_mid', 0)),
            'bear_fvg_top': float(last.get('bear_fvg_top', 0)),
            'bear_fvg_bottom': float(last.get('bear_fvg_bottom', 0)),
            'bear_fvg_mid': float(last.get('bear_fvg_mid', 0)),
            'bull_fvg_filled': bull_fvg_filled,
            'bear_fvg_filled': bear_fvg_filled,
            'recent_bull_fvg_count': len(recent_bull_fvg),
            'recent_bear_fvg_count': len(recent_bear_fvg),
            'all_gaps': self.gaps[-10:] if self.gaps else []
        }


class OrderBlockDetector:
    """Detect ICT Order Blocks"""
    
    def __init__(self, config: Optional[ICTConfig] = None):
        self.config = config or ICTConfig()
    
    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        lookback = self.config.swing_lookback
        min_body = self.config.ob_min_body_ratio
        
        # Calculate body ratio
        df['body'] = abs(df['close'] - df['open'])
        df['range'] = df['high'] - df['low']
        df['body_ratio'] = df['body'] / df['range'].replace(0, 1)
        
        # Bullish displacement (strong bullish candle)
        df['bull_dpl'] = (df['close'] > df['open']) & (df['body_ratio'] >= min_body)
        
        # Bearish displacement
        df['bear_dpl'] = (df['close'] < df['open']) & (df['body_ratio'] >= min_body)
        
        # Bullish Order Block: Bearish candle BEFORE bullish displacement
        df['bull_ob'] = (
            (df['close'].shift(1) < df['open'].shift(1)) &  # Previous candle was bearish
            df['bull_dpl']  # Current candle has bullish displacement
        )
        
        # Bearish Order Block: Bullish candle BEFORE bearish displacement
        df['bear_ob'] = (
            (df['close'].shift(1) > df['open'].shift(1)) &  # Previous candle was bullish
            df['bear_dpl']  # Current candle has bearish displacement
        )
        
        # OB Zone (for price lines)
        df['bull_ob_top'] = np.where(df['bull_ob'], df['high'].shift(1), np.nan)
        df['bull_ob_bottom'] = np.where(df['bull_ob'], df['low'].shift(1), np.nan)
        
        df['bear_ob_top'] = np.where(df['bear_ob'], df['high'].shift(1), np.nan)
        df['bear_ob_bottom'] = np.where(df['bear_ob'], df['low'].shift(1), np.nan)
        
        # Institutional Order Block (IOB) - 3+ consecutive same-direction candles
        df['bull_iob'] = (
            (df['close'] > df['open']) &
            (df['close'].shift(1) > df['open'].shift(1)) &
            (df['close'].shift(2) > df['open'].shift(2)) &
            df['bull_dpl']
        )
        
        df['bear_iob'] = (
            (df['close'] < df['open']) &
            (df['close'].shift(1) < df['open'].shift(1)) &
            (df['close'].shift(2) < df['open'].shift(2)) &
            df['bear_dpl']
        )
        
        return df
    
    def get_ob_info(self, df: pd.DataFrame) -> Dict[str, Any]:
        df_calc = self.detect(df)
        last = df_calc.iloc[-1]
        
        # Get recent OBs
        recent_bull_ob = df_calc[df_calc['bull_ob']].tail(3)
        recent_bear_ob = df_calc[df_calc['bear_ob']].tail(3)
        
        return {
            'bull_ob': bool(last.get('bull_ob', False)),
            'bear_ob': bool(last.get('bear_ob', False)),
            'bull_iob': bool(last.get('bull_iob', False)),
            'bear_iob': bool(last.get('bear_iob', False)),
            'bull_ob_top': float(last.get('bull_ob_top', 0)) if pd.notna(last.get('bull_ob_top')) else 0,
            'bull_ob_bottom': float(last.get('bull_ob_bottom', 0)) if pd.notna(last.get('bull_ob_bottom')) else 0,
            'bear_ob_top': float(last.get('bear_ob_top', 0)) if pd.notna(last.get('bear_ob_top')) else 0,
            'bear_ob_bottom': float(last.get('bear_ob_bottom', 0)) if pd.notna(last.get('bear_ob_bottom')) else 0,
            'recent_bull_ob_count': len(recent_bull_ob),
            'recent_bear_ob_count': len(recent_bear_ob)
        }


class LiquidityDetector:
    """Detect Liquidity Sweeps (BSL/SSL)"""
    
    def __init__(self, config: Optional[ICTConfig] = None):
        self.config = config or ICTConfig()
    
    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        lookback = self.config.swing_lookback
        
        # Swing levels
        df['swing_high'] = df['high'].rolling(lookback + 1).max().shift(1)
        df['swing_low'] = df['low'].rolling(lookback + 1).min().shift(1)
        
        # Previous swing levels
        df['prev_swing_high'] = df['swing_high'].shift(1)
        df['prev_swing_low'] = df['swing_low'].shift(1)
        
        # Buy Side Liquidity (BSL) - Above swing highs
        df['near_bsl'] = df['high'] >= df['swing_high'] * 0.9999
        
        # Sell Side Liquidity (SSL) - Below swing lows
        df['near_ssl'] = df['low'] <= df['swing_low'] * 1.0001
        
        # Bullish Sweep (SSL Sweep): Price goes below SSL, then closes back above
        df['bull_sweep'] = (
            (df['low'] < df['swing_low']) &
            (df['close'] > df['swing_low'])
        )
        
        # Bearish Sweep (BSL Sweep): Price goes above BSL, then closes back below
        df['bear_sweep'] = (
            (df['high'] > df['swing_high']) &
            (df['close'] < df['swing_high'])
        )
        
        # Equal Highs (Liquidity Pool)
        df['equal_high'] = abs(df['high'] - df['high'].shift(1)) / df['high'].replace(0, 1) < 0.0001
        df['equal_low'] = abs(df['low'] - df['low'].shift(1)) / df['low'].replace(0, 1) < 0.0001
        
        # Institutional Sweep (with displacement after)
        avg_range = df['range'] if 'range' in df.columns else (df['high'] - df['low'])
        df['body_ratio'] = abs(df['close'] - df['open']) / avg_range.replace(0, 1)
        
        df['institutional_bull_sweep'] = (
            df['bull_sweep'] &
            (df['body_ratio'] >= 0.65) &
            (df['close'] > df['open'])
        )
        
        df['institutional_bear_sweep'] = (
            df['bear_sweep'] &
            (df['body_ratio'] >= 0.65) &
            (df['close'] < df['open'])
        )
        
        return df
    
    def get_liquidity_info(self, df: pd.DataFrame) -> Dict[str, Any]:
        df_calc = self.detect(df)
        last = df_calc.iloc[-1]
        
        return {
            'near_bsl': bool(last.get('near_bsl', False)),
            'near_ssl': bool(last.get('near_ssl', False)),
            'bull_sweep': bool(last.get('bull_sweep', False)),
            'bear_sweep': bool(last.get('bear_sweep', False)),
            'institutional_bull_sweep': bool(last.get('institutional_bull_sweep', False)),
            'institutional_bear_sweep': bool(last.get('institutional_bear_sweep', False)),
            'equal_high': bool(last.get('equal_high', False)),
            'equal_low': bool(last.get('equal_low', False)),
            'swing_high': float(last.get('swing_high', 0)) if pd.notna(last.get('swing_high')) else 0,
            'swing_low': float(last.get('swing_low', 0)) if pd.notna(last.get('swing_low')) else 0
        }


class DailyLevelsCalculator:
    """Calculate Daily/Weekly/Monthly Levels"""
    
    def __init__(self):
        pass
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        df['date'] = df['timestamp'].dt.date
        
        # Daily levels
        daily = df.groupby('date').agg({
            'high': 'max', 'low': 'min', 'close': 'last', 'open': 'first'
        }).reset_index()
        
        # Previous day values
        prev_high = daily['high'].shift(1).fillna(daily['high'])
        prev_low = daily['low'].shift(1).fillna(daily['low'])
        prev_close = daily['close'].shift(1).fillna(daily['close'])
        
        # Previous Day High/Low
        daily['pdh'] = prev_high
        daily['pdl'] = prev_low
        
        # Midpoint
        daily['pdm'] = (daily['pdh'] + daily['pdl']) / 2
        
        # Pivot Point
        daily['pivot'] = (daily['pdh'] + daily['pdl'] + prev_close) / 3
        daily['pivot_y'] = (prev_high + prev_low + prev_close) / 3
        
        # Resistance levels
        daily['r1'] = 2 * daily['pivot'] - prev_low
        daily['r2'] = daily['pivot'] + (prev_high - prev_low)
        daily['r3'] = prev_high + 2 * (daily['pivot'] - prev_low)
        
        # Support levels
        daily['s1'] = 2 * daily['pivot'] - prev_high
        daily['s2'] = daily['pivot'] - (prev_high - prev_low)
        daily['s3'] = prev_low - 2 * (prev_high - daily['pivot'])
        
        # Open of the Day
        daily['od'] = daily['open']  # First candle of the day
        
        # Merge back
        cols = ['date', 'pdh', 'pdl', 'pdm', 'pivot', 'pivot_y', 'od', 'r1', 'r2', 'r3', 's1', 's2', 's3']
        df = df.merge(daily[cols], on='date', how='left')
        
        # Forward fill
        for col in cols[1:]:
            df[col] = df[col].ffill().fillna(df['close'])
        
        return df
    
    def get_daily_levels(self, df: pd.DataFrame) -> Dict[str, Any]:
        df_calc = self.calculate(df)
        last = df_calc.iloc[-1]
        close = float(last['close'])
        
        def safe_get(key, default=None):
            val = last.get(key)
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return default if default is not None else close
            return float(val)
        
        return {
            'pivot': safe_get('pivot'),
            'pivot_y': safe_get('pivot_y'),
            'pdh': safe_get('pdh'),  # Previous Day High
            'pdl': safe_get('pdl'),  # Previous Day Low
            'pdm': safe_get('pdm'),  # Previous Day Midpoint
            'od': safe_get('od'),    # Open of the Day
            'r1': safe_get('r1'),
            'r2': safe_get('r2'),
            'r3': safe_get('r3'),
            's1': safe_get('s1'),
            's2': safe_get('s2'),
            's3': safe_get('s3'),
            'above_pivot': close > safe_get('pivot'),
            'above_pdh': close > safe_get('pdh'),
            'below_pdl': close < safe_get('pdl'),
            'in_pdh_pdl_range': safe_get('pdl') < close < safe_get('pdh'),
            'current_price': close
        }


class VWAPCalculator:
    """Auto Anchored VWAP ( ICT Concept )"""
    
    def __init__(self):
        self.anchor_type = 'session'  # 'session', 'swing', 'date'
    
    def calculate(self, df: pd.DataFrame, anchor: str = 'session') -> pd.DataFrame:
        df = df.copy()
        
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        df['date'] = df['timestamp'].dt.date
        
        # Typical Price
        df['typical'] = (df['high'] + df['low'] + df['close']) / 3
        
        # Session VWAP (reset at start of new session)
        # For simplicity, we'll use daily reset
        df['session_id'] = df['date']
        
        # Calculate cumulative values per session
        df['cum_tp_vol'] = df.groupby('session_id')['typical'].transform(
            lambda x: (x * df.loc[x.index, 'volume']).cumsum()
        )
        df['cum_vol'] = df.groupby('session_id')['volume'].transform(lambda x: x.cumsum())
        
        # Handle zero division
        df['vwap'] = df['cum_tp_vol'] / df['cum_vol'].replace(0, np.nan)
        df['vwap'] = df['vwap'].fillna(df['close'])
        
        # VWAP deviation
        df['vwap_deviation'] = df['close'] - df['vwap']
        df['vwap_deviation_pct'] = (df['vwap_deviation'] / df['vwap'] * 100).fillna(0)
        
        # VWAP bands (1, 2, 3 standard deviations)
        df['vwap_std'] = df.groupby('session_id')['close'].transform(
            lambda x: x.rolling(20).std()
        ).fillna(0)
        
        df['vwap_upper_1'] = df['vwap'] + df['vwap_std']
        df['vwap_lower_1'] = df['vwap'] - df['vwap_std']
        df['vwap_upper_2'] = df['vwap'] + 2 * df['vwap_std']
        df['vwap_lower_2'] = df['vwap'] - 2 * df['vwap_std']
        
        return df
    
    def get_vwap_info(self, df: pd.DataFrame) -> Dict[str, Any]:
        df_calc = self.calculate(df)
        last = df_calc.iloc[-1]
        close = float(last['close'])
        
        return {
            'vwap': float(last.get('vwap', close)),
            'vwap_upper_1': float(last.get('vwap_upper_1', close)),
            'vwap_lower_1': float(last.get('vwap_lower_1', close)),
            'vwap_upper_2': float(last.get('vwap_upper_2', close)),
            'vwap_lower_2': float(last.get('vwap_lower_2', close)),
            'vwap_deviation': float(last.get('vwap_deviation', 0)),
            'vwap_deviation_pct': float(last.get('vwap_deviation_pct', 0)),
            'above_vwap': close > float(last.get('vwap', close)),
            'below_vwap': close < float(last.get('vwap', close))
        }


class EMA8Calculator:
    """ICT 8/8 EMA Line"""
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # 8 EMA
        df['ema8'] = df['close'].ewm(span=8, adjust=False).mean()
        
        # 200 EMA for trend
        df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
        
        # Price relative to EMAs
        df['above_ema8'] = df['close'] > df['ema8']
        df['above_ema200'] = df['close'] > df['ema200']
        
        # EMA crossover
        df['ema8_above_ema200'] = df['ema8'] > df['ema200']
        
        return df
    
    def get_ema_info(self, df: pd.DataFrame) -> Dict[str, Any]:
        df_calc = self.calculate(df)
        last = df_calc.iloc[-1]
        close = float(last['close'])
        
        return {
            'ema8': float(last.get('ema8', close)),
            'ema200': float(last.get('ema200', close)),
            'above_ema8': bool(last.get('above_ema8', False)),
            'above_ema200': bool(last.get('above_ema200', False)),
            'ema8_above_ema200': bool(last.get('ema8_above_ema200', False)),
            'bull_trend': bool(last.get('above_ema8', False)) and bool(last.get('above_ema200', False)),
            'bear_trend': not bool(last.get('above_ema8', False)) and not bool(last.get('above_ema200', False))
        }


class JudasSwingDetector:
    """ICT Judas Swing / Swing Failure Pattern"""
    
    def __init__(self, config: Optional[ICTConfig] = None):
        self.config = config or ICTConfig()
    
    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        lookback = self.config.swing_lookback
        
        # Calculate swings
        df['swing_low'] = df['low'].rolling(lookback + 1).min().shift(1).fillna(df['low'])
        df['swing_high'] = df['high'].rolling(lookback + 1).max().shift(1).fillna(df['high'])
        
        # Body ratio
        avg_range = (df['high'] - df['low']).rolling(14).mean().fillna(1).replace(0, 1)
        df['body_ratio'] = abs(df['close'] - df['open']) / avg_range
        
        # Judas Swing: Wick sweeps through level, then closes back
        # Bullish Judas: Low sweeps below swing low, close above
        df['judas_bull'] = (
            (df['low'] < df['swing_low']) &
            (df['close'] > df['swing_low']) &
            (df['body_ratio'] >= 0.65)
        )
        
        # Bearish Judas: High sweeps above swing high, close below
        df['judas_bear'] = (
            (df['high'] > df['swing_high']) &
            (df['close'] < df['swing_high']) &
            (df['body_ratio'] >= 0.65)
        )
        
        # Previous Judas detection
        df['prev_judas_bull'] = df['judas_bull'].shift(1)
        df['prev_judas_bear'] = df['judas_bear'].shift(1)
        
        return df
    
    def get_judas_info(self, df: pd.DataFrame) -> Dict[str, Any]:
        df_calc = self.detect(df)
        last = df_calc.iloc[-1]
        
        return {
            'judas_bull': bool(last.get('judas_bull', False)),
            'judas_bear': bool(last.get('judas_bear', False)),
            'prev_judas_bull': bool(last.get('prev_judas_bull', False)),
            'prev_judas_bear': bool(last.get('prev_judas_bear', False)),
            'swing_low': float(last.get('swing_low', 0)),
            'swing_high': float(last.get('swing_high', 0))
        }


class ICTAnalyzer:
    """
    Complete ICT Analyzer
    Combines all ICT concepts:
    - Killzones
    - OTE Fibonacci
    - Fair Value Gap
    - Order Blocks
    - Liquidity Sweeps
    - Daily Levels
    - VWAP
    - 8/8 EMA
    - Judas Swing
    """
    
    def __init__(self, config: Optional[ICTConfig] = None):
        self.config = config or ICTConfig()
        self.killzones = KillzoneDetector(config)
        self.ote = OTECalculator(config)
        self.fvg = FairValueGapDetector(config)
        self.ob = OrderBlockDetector(config)
        self.liquidity = LiquidityDetector(config)
        self.daily = DailyLevelsCalculator()
        self.vwap = VWAPCalculator()
        self.ema8 = EMA8Calculator()
        self.judas = JudasSwingDetector(config)
    
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Complete ICT analysis"""
        
        # Get close price early
        close = float(df['close'].iloc[-1]) if len(df) > 0 else 0
        
        # Get all component analyses
        kz = self.killzones.get_killzone_info(df)
        ote = self.ote.get_ote_info(df)
        fvg = self.fvg.get_fvg_info(df)
        ob = self.ob.get_ob_info(df)
        liq = self.liquidity.get_liquidity_info(df)
        daily = self.daily.get_daily_levels(df)
        vwap = self.vwap.get_vwap_info(df)
        ema = self.ema8.get_ema_info(df)
        judas = self.judas.get_judas_info(df)
        
        # Calculate ICT score
        score = 0
        factors = []
        
        # Bullish factors
        if kz['active_kz'] == 'london':
            score += 1
            factors.append('IN_LONDON_KZ')
        if kz['active_kz'] == 'ny':
            score += 1
            factors.append('IN_NY_KZ')
        
        if ote['in_ote_zone']:
            score += 1
            factors.append('IN_OTE_ZONE')
        
        if fvg['bull_fvg']:
            score += 1
            factors.append('BULL_FVG')
        
        if ob['bull_ob']:
            score += 2
            factors.append('BULL_OB')
        
        if liq['bull_sweep']:
            score += 1
            factors.append('BULL_SWEEP')
        
        if liq['institutional_bull_sweep']:
            score += 2
            factors.append('INSTITUTIONAL_SWEEP')
        
        if vwap['above_vwap']:
            score += 1
            factors.append('ABOVE_VWAP')
        
        if ema['above_ema8']:
            score += 1
            factors.append('ABOVE_EMA8')
        
        if ema['bull_trend']:
            score += 2
            factors.append('BULL_TREND')
        
        if daily['in_pdh_pdl_range'] and close > daily['pivot']:
            score += 1
            factors.append('ABOVE_PIVOT')
        
        # Bearish factors
        if fvg['bear_fvg']:
            score -= 1
            factors.append('BEAR_FVG')
        
        if ob['bear_ob']:
            score -= 2
            factors.append('BEAR_OB')
        
        if liq['bear_sweep']:
            score -= 1
            factors.append('BEAR_SWEEP')
        
        if not vwap['above_vwap']:
            score -= 1
            factors.append('BELOW_VWAP')
        
        # Determine direction
        direction = 'neutral'
        if score >= 3:
            direction = 'long'
        elif score <= -2:
            direction = 'short'
        
        return {
            # Killzones
            'in_killzone': kz['in_any_kz'],
            'active_kz': kz['active_kz'],
            'in_london_kz': kz['in_london_kz'],
            'in_ny_kz': kz['in_ny_kz'],
            'in_asia_kz': kz['in_asia_kz'],
            'in_midnight_range': kz['in_midnight_range'],
            'london_range': kz['london_range'],
            'ny_range': kz['ny_range'],
            'midnight_range': kz['midnight_range'],
            
            # OTE
            'ote_382': ote['ote_382'],
            'ote_618': ote['ote_618'],
            'ote_786': ote['ote_786'],
            'in_ote_zone': ote['in_ote_zone'],
            'ote_zone': ote['zone'],
            'ote_distance_pct': ote['distance_from_618_pct'],
            
            # FVG
            'bull_fvg': fvg['bull_fvg'],
            'bear_fvg': fvg['bear_fvg'],
            'bull_fvg_filled': fvg['bull_fvg_filled'],
            'bear_fvg_filled': fvg['bear_fvg_filled'],
            'bull_fvg_mid': fvg['bull_fvg_mid'],
            'bear_fvg_mid': fvg['bear_fvg_mid'],
            
            # Order Blocks
            'bull_ob': ob['bull_ob'],
            'bear_ob': ob['bear_ob'],
            'bull_iob': ob['bull_iob'],
            'bear_iob': ob['bear_iob'],
            'bull_ob_top': ob['bull_ob_top'],
            'bull_ob_bottom': ob['bull_ob_bottom'],
            'bear_ob_top': ob['bear_ob_top'],
            'bear_ob_bottom': ob['bear_ob_bottom'],
            
            # Liquidity
            'near_bsl': liq['near_bsl'],
            'near_ssl': liq['near_ssl'],
            'bull_sweep': liq['bull_sweep'],
            'bear_sweep': liq['bear_sweep'],
            'institutional_bull_sweep': liq['institutional_bull_sweep'],
            'institutional_bear_sweep': liq['institutional_bear_sweep'],
            'equal_high': liq['equal_high'],
            'equal_low': liq['equal_low'],
            
            # Daily Levels
            'pivot': daily['pivot'],
            'pdh': daily['pdh'],
            'pdl': daily['pdl'],
            'pdm': daily['pdm'],
            'od': daily['od'],
            'r1': daily['r1'], 'r2': daily['r2'], 'r3': daily['r3'],
            's1': daily['s1'], 's2': daily['s2'], 's3': daily['s3'],
            'above_pivot': daily['above_pivot'],
            'above_pdh': daily['above_pdh'],
            'below_pdl': daily['below_pdl'],
            
            # VWAP
            'vwap': vwap['vwap'],
            'vwap_upper_1': vwap['vwap_upper_1'],
            'vwap_lower_1': vwap['vwap_lower_1'],
            'above_vwap': vwap['above_vwap'],
            'vwap_deviation_pct': vwap['vwap_deviation_pct'],
            
            # EMA
            'ema8': ema['ema8'],
            'ema200': ema['ema200'],
            'above_ema8': ema['above_ema8'],
            'above_ema200': ema['above_ema200'],
            'bull_trend': ema['bull_trend'],
            'bear_trend': ema['bear_trend'],
            
            # Judas Swing
            'judas_bull': judas['judas_bull'],
            'judas_bear': judas['judas_bear'],
            
            # Summary
            'direction': direction,
            'score': score,
            'factors': factors,
            'current_price': close
        }
