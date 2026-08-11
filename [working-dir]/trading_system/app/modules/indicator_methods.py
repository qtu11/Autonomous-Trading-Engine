"""
4 PHƯƠNG PHÁP TRADING - TÍCH HỢP ĐẦY ĐỦ
===========================================
1. Indicator-Based (EMA/RSI/ATR/Pivot)
2. SMC (Smart Money Concepts + Indicators)
3. ICT (Killzone/OTE/Pivot)
4. Ultra Confluence Matrix (Hybrid)

Theo spec: LOGIC 4 PHUONG PHAP.md
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass


# ============================================================
# METHOD 1: INDICATOR-BASED TRADING
# EMA/RSI/ATR/Pivot
# ============================================================

@dataclass
class IndicatorConfig:
    """Indicator Configuration"""
    # EMA
    ema_fast: int = 20
    ema_medium: int = 50
    ema_slow: int = 200
    
    # RSI
    rsi_period: int = 14
    
    # ATR
    atr_period: int = 14
    
    # Volume
    vol_ma_period: int = 20


class IndicatorMethod:
    """
    Method 1: Indicator-Based Trading
    Triết lý: Dùng chỉ báo kỹ thuật cổ điển
    - EMA xác định xu hướng (stacking)
    - RSI lọc vùng quá mua/quá bán
    - ATR đo biến động, tính SL/TP
    - Pivot Points vùng S/R trong ngày
    """

    def __init__(self, config: IndicatorConfig = None):
        self.config = config or IndicatorConfig()

    def calculate_ema(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate EMA Stack"""
        df = df.copy()
        df['ema_fast'] = df['close'].ewm(span=self.config.ema_fast, adjust=False).mean()
        df['ema_medium'] = df['close'].ewm(span=self.config.ema_medium, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=self.config.ema_slow, adjust=False).mean()
        
        # EMA Stacking (xu hướng mạnh khi tất cả cùng hướng)
        df['ema_bull_stack'] = (df['ema_fast'] > df['ema_medium']) & (df['ema_medium'] > df['ema_slow'])
        df['ema_bear_stack'] = (df['ema_fast'] < df['ema_medium']) & (df['ema_medium'] < df['ema_slow'])
        
        return df

    def calculate_rsi(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate RSI with Wilder's smoothing"""
        df = df.copy()
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        # Wilder's smoothing
        period = self.config.rsi_period
        avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
        
        rs = avg_gain / avg_loss.replace(0, np.nan)
        df['rsi'] = 100 - (100 / (1 + rs))
        df['rsi'] = df['rsi'].fillna(50)
        
        # RSI Zones
        df['rsi_overbought'] = df['rsi'] >= 70
        df['rsi_oversold'] = df['rsi'] <= 30
        df['rsi_neutral'] = (df['rsi'] > 30) & (df['rsi'] < 70)
        
        return df

    def calculate_atr(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate ATR with Wilder's smoothing"""
        df = df.copy()
        period = self.config.atr_period
        
        # True Range
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['close'].shift(1))
        df['tr3'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        
        # ATR with Wilder's
        df['atr'] = df['tr'].ewm(alpha=1/period, adjust=False).mean()
        df['atr'] = df['atr'].fillna(df['tr'])
        
        return df

    def calculate_pivot(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Daily Pivot Points"""
        df = df.copy()
        
        # Get daily data
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].dt.date
        
        # Calculate daily OHLC
        daily = df.groupby('date').agg({
            'high': 'max', 'low': 'min', 'close': 'last'
        }).reset_index()
        
        # Previous day values
        prev_high = daily['high'].shift(1).fillna(daily['high'])
        prev_low = daily['low'].shift(1).fillna(daily['low'])
        prev_close = daily['close'].shift(1).fillna(daily['close'])
        
        # Pivot
        daily['pivot'] = (prev_high + prev_low + prev_close) / 3
        daily['r1'] = 2 * daily['pivot'] - prev_low
        daily['s1'] = 2 * daily['pivot'] - prev_high
        daily['r2'] = daily['pivot'] + (prev_high - prev_low)
        daily['s2'] = daily['pivot'] - (prev_high - prev_low)
        daily['r3'] = prev_high + 2 * (daily['pivot'] - prev_low)
        daily['s3'] = prev_low - 2 * (prev_high - daily['pivot'])
        
        # Merge back
        df = df.merge(daily[['date', 'pivot', 'r1', 'r2', 'r3', 's1', 's2', 's3']], on='date', how='left')
        
        # Forward fill
        for col in ['pivot', 'r1', 'r2', 'r3', 's1', 's2', 's3']:
            df[col] = df[col].ffill()
            df[col] = df[col].fillna(df['close'])
        
        return df

    def calculate_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all indicator method indicators"""
        df = self.calculate_ema(df)
        df = self.calculate_rsi(df)
        df = self.calculate_atr(df)
        df = self.calculate_pivot(df)
        
        # Volume
        df['vol_ma'] = df['volume'].rolling(self.config.vol_ma_period).mean()
        df['vol_ma'] = df['vol_ma'].fillna(df['volume'].mean())
        df['vol_ratio'] = df['volume'] / df['vol_ma'].replace(0, 1)
        
        return df

    def get_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get Indicator-Based signal"""
        df_calc = self.calculate_all(df)
        last = df_calc.iloc[-1]
        prev = df_calc.iloc[-2] if len(df_calc) > 1 else last
        
        # BUY conditions
        buy_conditions = [
            last['close'] > last['ema_fast'],
            last['ema_bull_stack'],
            50 <= last['rsi'] <= 70,
            last['atr'] > 0
        ]
        
        # SELL conditions
        sell_conditions = [
            last['close'] < last['ema_fast'],
            last['ema_bear_stack'],
            30 <= last['rsi'] <= 50,
            last['atr'] > 0
        ]
        
        buy_score = sum(buy_conditions)
        sell_score = sum(sell_conditions)
        
        direction = 'neutral'
        if buy_score >= 3:
            direction = 'long'
        elif sell_score >= 3:
            direction = 'short'
        
        # Current price vs pivot
        pivot = float(last['pivot'])
        price = float(last['close'])
        
        return {
            'method': 'indicator_based',
            'direction': direction,
            'confidence': max(buy_score, sell_score) / 4 * 100,
            
            # EMA
            'ema_fast': float(last['ema_fast']),
            'ema_medium': float(last['ema_medium']),
            'ema_slow': float(last['ema_slow']),
            'ema_bull_stack': bool(last['ema_bull_stack']),
            'ema_bear_stack': bool(last['ema_bear_stack']),
            
            # RSI
            'rsi': float(last['rsi']),
            'rsi_zone': 'overbought' if last['rsi'] >= 70 else 'oversold' if last['rsi'] <= 30 else 'neutral',
            
            # ATR
            'atr': float(last['atr']),
            
            # Pivot
            'pivot': pivot,
            'r1': float(last['r1']),
            'r2': float(last['r2']),
            'r3': float(last['r3']),
            's1': float(last['s1']),
            's2': float(last['s2']),
            's3': float(last['s3']),
            
            # Price action
            'above_pivot': price > pivot,
            'below_pivot': price < pivot,
            
            # Conditions
            'buy_score': buy_score,
            'sell_score': sell_score
        }


# ============================================================
# METHOD 2: SMC + INDICATORS
# Smart Money Concepts với EMA/RSI/ATR lọc
# ============================================================

class SMCWithIndicators:
    """
    Method 2: SMC với Indicator Confluence
    Triết lý: SMC structure + Indicator xác nhận
    - EMA xác định trend (stacking)
    - RSI xác nhận momentum
    - ATR tính SL/TP
    - Equilibrium/Fibonacci zones
    """

    def __init__(self):
        self.indicator_method = IndicatorMethod()

    def detect_swing_points(self, df: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
        """Detect Swing High/Low với fractal logic"""
        df = df.copy()
        
        # Swing High
        df['swing_high'] = df['high'].rolling(lookback + 1).max().shift(1)
        df['is_swing_high'] = (
            (df['high'] == df['swing_high']) &
            (df['high'] > df['high'].shift(1)) &
            (df['high'] > df['high'].shift(-1))
        )
        
        # Swing Low
        df['swing_low'] = df['low'].rolling(lookback + 1).min().shift(1)
        df['is_swing_low'] = (
            (df['low'] == df['swing_low']) &
            (df['low'] < df['low'].shift(1)) &
            (df['low'] < df['low'].shift(-1))
        )
        
        return df

    def detect_structure(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect Market Structure: HH, HL, LH, LL"""
        df = self.detect_swing_points(df)
        
        df['prev_swing_high'] = df['swing_high'].shift(1)
        df['prev_swing_low'] = df['swing_low'].shift(1)
        
        # Higher High / Higher Low
        df['hh'] = df['high'] > df['prev_swing_high']
        df['hl'] = (df['low'] > df['prev_swing_low']) & (df['high'] < df['prev_swing_high'])
        
        # Lower High / Lower Low
        df['lh'] = (df['high'] < df['prev_swing_high']) & (df['low'] > df['prev_swing_low'])
        df['ll'] = df['low'] < df['prev_swing_low']
        
        # Structure direction
        df['bull_structure'] = df['hh'] | df['hl']
        df['bear_structure'] = df['lh'] | df['ll']
        
        return df

    def detect_bos_choch(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect BOS và CHoCH"""
        df = self.detect_structure(df)
        
        # BOS - Break of Structure (tiếp diễn)
        df['bull_bos'] = df['close'] > df['swing_high']  # Vượt đỉnh cũ = uptrend tiếp diễn
        df['bear_bos'] = df['close'] < df['swing_low']   # Vượt đáy cũ = downtrend tiếp diễn
        
        # CHoCH - Change of Character (đảo chiều)
        # Trong uptrend: giá phá vỡ HL = potential reversal
        # Trong downtrend: giá phá vỡ LH = potential reversal
        df['bull_choch'] = (df['close'] > df['swing_high']) & (df['bull_structure'])
        df['bear_choch'] = (df['close'] < df['swing_low']) & (df['bear_structure'])
        
        return df

    def detect_mss(self, df: pd.DataFrame) -> pd.DataFrame:
        """Market Structure Shift - Sweep + Break"""
        df = self.detect_bos_choch(df)
        
        # Bullish MSS: Sweep SSL + Close > Swing High
        df['bull_mss'] = (
            (df['low'] < df['swing_low']) &  # Sweep below SSL
            (df['close'] > df['swing_low']) &  # Close back above
            (df['close'] > df['swing_high'])   # Break of structure
        )
        
        # Bearish MSS: Sweep BSL + Close < Swing Low
        df['bear_mss'] = (
            (df['high'] > df['swing_high']) &  # Sweep above BSL
            (df['close'] < df['swing_high']) &  # Close back below
            (df['close'] < df['swing_low'])    # Break of structure
        )
        
        return df

    def detect_liquidity(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect Liquidity Sweeps (BSL/SSL)"""
        df = self.detect_mss(df)
        
        # Sweep thresholds (0.1% tolerance)
        df['bsl_threshold'] = df['swing_high'] * 1.001
        df['ssl_threshold'] = df['swing_low'] * 0.999
        
        # Bullish Sweep: Low < SSL, Close > SSL
        df['bull_sweep'] = (
            (df['low'] < df['ssl_threshold']) &
            (df['close'] > df['swing_low'])
        )
        
        # Bearish Sweep: High > BSL, Close < BSL
        df['bear_sweep'] = (
            (df['high'] > df['bsl_threshold']) &
            (df['close'] < df['swing_high'])
        )
        
        return df

    def detect_fvg(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect Fair Value Gap (BISI/SIBI)"""
        df = self.detect_liquidity(df)
        
        # Bullish FVG (BISI): Low > High 2 bars ago
        df['bull_fvg'] = df['low'] > df['high'].shift(2)
        
        # Bearish FVG (SIBI): High < Low 2 bars ago
        df['bear_fvg'] = df['high'] < df['low'].shift(2)
        
        # FVG Midpoints (CE - Consequent Encroachment)
        df['bull_fvg_mid'] = (df['high'].shift(1) + df['low']) / 2
        df['bear_fvg_mid'] = (df['low'].shift(1) + df['high']) / 2
        
        return df

    def detect_order_block(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect Order Block"""
        df = self.detect_fvg(df)
        
        # Body ratio for displacement detection
        df['body'] = abs(df['close'] - df['open'])
        df['range'] = df['high'] - df['low']
        df['body_ratio'] = df['body'] / df['range'].replace(0, 1)
        
        # Displacement: Strong candle body > 60% of range
        df['bull_dpl'] = (df['close'] > df['open']) & (df['body_ratio'] >= 0.6)
        df['bear_dpl'] = (df['close'] < df['open']) & (df['body_ratio'] >= 0.6)
        
        # Bullish OB: Bearish candle cuối trước displacement
        df['prev_bear'] = (df['close'].shift(1) < df['open'].shift(1))
        df['bull_ob'] = df['prev_bear'] & df['bull_dpl']
        
        # Bearish OB: Bullish candle cuối trước displacement
        df['prev_bull'] = (df['close'].shift(1) > df['open'].shift(1))
        df['bear_ob'] = df['prev_bull'] & df['bear_dpl']
        
        return df

    def detect_equilibrium(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect Equilibrium và Premium/Discount zones"""
        df = self.detect_order_block(df)
        
        lookback = 20
        df['dr_high'] = df['high'].rolling(lookback).max()
        df['dr_low'] = df['low'].rolling(lookback).min()
        
        # Equilibrium = 50% Fib
        df['equilibrium'] = (df['dr_high'] + df['dr_low']) / 2
        
        # Premium/Discount zones
        df['in_premium'] = df['close'] > df['equilibrium']
        df['in_discount'] = df['close'] < df['equilibrium']
        
        # Fibonacci levels
        df_range = df['dr_high'] - df['dr_low']
        df['fib_382'] = df['dr_low'] + df_range * 0.382
        df['fib_618'] = df['dr_low'] + df_range * 0.618
        df['fib_786'] = df['dr_low'] + df_range * 0.786
        
        return df

    def detect_ifc(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect IFC - Institutional Funded Candle"""
        df = self.detect_equilibrium(df)
        
        # IFC Bullish: Wick sweeps SSL + Close in upper 30% of range
        df['ifc_bull'] = (
            (df['low'] < df['swing_low'] * 0.999) &
            (df['close'] > df['open']) &
            ((df['close'] - df['low']) / df['range'] >= 0.7)
        )
        
        # IFC Bearish: Wick sweeps BSL + Close in lower 30% of range
        df['ifc_bear'] = (
            (df['high'] > df['swing_high'] * 1.001) &
            (df['close'] < df['open']) &
            ((df['high'] - df['close']) / df['range'] >= 0.7)
        )
        
        return df

    def calculate_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all SMC + Indicator data"""
        df = self.detect_ifc(df)
        
        # Add indicators from Method 1
        df = self.indicator_method.calculate_ema(df)
        df = self.indicator_method.calculate_rsi(df)
        df = self.indicator_method.calculate_atr(df)
        
        return df

    def get_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get SMC + Indicator signal"""
        df_calc = self.calculate_all(df)
        last = df_calc.iloc[-1]
        
        # Calculate confluence score
        score = 0
        factors = []
        
        # EMA confirmation
        if last.get('ema_bull_stack', False):
            score += 2
            factors.append('EMA_BULL_STACK')
        if last.get('ema_bear_stack', False):
            score -= 2
            factors.append('EMA_BEAR_STACK')
        
        # RSI confirmation
        rsi = float(last.get('rsi', 50))
        if rsi < 40:
            score += 1
            factors.append('RSI_BULL')
        if rsi > 60:
            score -= 1
            factors.append('RSI_BEAR')
        
        # Structure
        if last.get('bull_structure', False):
            score += 1
            factors.append('BULL_STRUCTURE')
        if last.get('bear_structure', False):
            score -= 1
            factors.append('BEAR_STRUCTURE')
        
        # MSS (quan trọng nhất)
        if last.get('bull_mss', False):
            score += 3
            factors.append('BULL_MSS')
        if last.get('bear_mss', False):
            score -= 3
            factors.append('BEAR_MSS')
        
        # CHoCH
        if last.get('bull_choch', False):
            score += 2
            factors.append('BULL_CHOCH')
        if last.get('bear_choch', False):
            score -= 2
            factors.append('BEAR_CHOCH')
        
        # Liquidity Sweep
        if last.get('bull_sweep', False):
            score += 1
            factors.append('BULL_SWEEP')
        if last.get('bear_sweep', False):
            score -= 1
            factors.append('BEAR_SWEEP')
        
        # FVG
        if last.get('bull_fvg', False):
            score += 1
            factors.append('BULL_FVG')
        if last.get('bear_fvg', False):
            score -= 1
            factors.append('BEAR_FVG')
        
        # IFC
        if last.get('ifc_bull', False):
            score += 2
            factors.append('BULL_IFC')
        if last.get('ifc_bear', False):
            score -= 2
            factors.append('BEAR_IFC')
        
        # Premium/Discount
        if last.get('in_discount', False):
            score += 1
            factors.append('DISCOUNT_ZONE')
        if last.get('in_premium', False):
            score -= 1
            factors.append('PREMIUM_ZONE')
        
        # Order Blocks
        if last.get('bull_ob', False):
            score += 1
            factors.append('BULL_OB')
        if last.get('bear_ob', False):
            score -= 1
            factors.append('BEAR_OB')
        
        direction = 'neutral'
        confidence = abs(score) / 13 * 100
        
        if score >= 5:
            direction = 'long'
        elif score <= -5:
            direction = 'short'
        
        return {
            'method': 'smc_with_indicators',
            'direction': direction,
            'confidence': min(confidence, 100),
            'score': score,
            'factors': factors,
            
            # Structure
            'swing_high': float(last.get('swing_high', 0)),
            'swing_low': float(last.get('swing_low', 0)),
            'hh': bool(last.get('hh', False)),
            'hl': bool(last.get('hl', False)),
            'lh': bool(last.get('lh', False)),
            'll': bool(last.get('ll', False)),
            
            # BOS/CHoCH/MSS
            'bull_bos': bool(last.get('bull_bos', False)),
            'bear_bos': bool(last.get('bear_bos', False)),
            'bull_choch': bool(last.get('bull_choch', False)),
            'bear_choch': bool(last.get('bear_choch', False)),
            'bull_mss': bool(last.get('bull_mss', False)),
            'bear_mss': bool(last.get('bear_mss', False)),
            
            # Liquidity
            'bull_sweep': bool(last.get('bull_sweep', False)),
            'bear_sweep': bool(last.get('bear_sweep', False)),
            'ifc_bull': bool(last.get('ifc_bull', False)),
            'ifc_bear': bool(last.get('ifc_bear', False)),
            
            # FVG
            'bull_fvg': bool(last.get('bull_fvg', False)),
            'bear_fvg': bool(last.get('bear_fvg', False)),
            
            # Order Blocks
            'bull_ob': bool(last.get('bull_ob', False)),
            'bear_ob': bool(last.get('bear_ob', False)),
            
            # Equilibrium
            'equilibrium': float(last.get('equilibrium', 0)),
            'in_premium': bool(last.get('in_premium', False)),
            'in_discount': bool(last.get('in_discount', False)),
            'fib_618': float(last.get('fib_618', 0)),
            
            # Indicators
            'ema_bull_stack': bool(last.get('ema_bull_stack', False)),
            'ema_bear_stack': bool(last.get('ema_bear_stack', False)),
            'rsi': rsi,
            'atr': float(last.get('atr', 0))
        }


# ============================================================
# METHOD 3: ICT CONCEPTS
# Killzone, OTE, Daily Levels
# ============================================================

class ICTMethod:
    """
    Method 3: ICT Concepts
    Triết lý: Thời gian + Cấu trúc
    - Killzone: London, NY, Asia
    - OTE: Fibonacci retracement
    - Daily Levels: PDH, PDL, Pivot
    """

    def __init__(self):
        pass

    def detect_killzone(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect Killzones"""
        df = df.copy()
        
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        df['hour'] = df['timestamp'].dt.hour
        df['minute'] = df['timestamp'].dt.minute
        df['minute_of_day'] = df['hour'] * 60 + df['minute']
        
        # London Killzone: 08:00 - 09:00 UTC
        df['london_kz'] = (df['minute_of_day'] >= 480) & (df['minute_of_day'] <= 540)
        
        # NY Killzone: 13:30 - 14:30 UTC
        df['ny_kz'] = (df['minute_of_day'] >= 810) & (df['minute_of_day'] <= 870)
        
        # Asia Killzone: 00:00 - 09:00 UTC
        df['asia_kz'] = (df['minute_of_day'] >= 0) & (df['minute_of_day'] <= 540)
        
        df['in_killzone'] = df['london_kz'] | df['ny_kz'] | df['asia_kz']
        
        return df

    def detect_ote(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate OTE - Optimal Trade Entry (Fibonacci)"""
        df = df.copy()
        lookback = 20
        
        # Swing high/low
        df['swing_high'] = df['high'].rolling(lookback + 1).max().shift(1)
        df['swing_low'] = df['low'].rolling(lookback + 1).min().shift(1)
        df['swing_range'] = df['swing_high'] - df['swing_low']
        
        # OTE levels
        df['ote_382'] = df['swing_low'] + df['swing_range'] * 0.382
        df['ote_618'] = df['swing_low'] + df['swing_range'] * 0.618
        df['ote_786'] = df['swing_low'] + df['swing_range'] * 0.786
        
        # In OTE zone
        df['in_ote_zone'] = (df['close'] >= df['ote_618']) & (df['close'] <= df['ote_786'])
        
        return df

    def detect_daily_levels(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Daily Levels: PDH, PDL, Pivot"""
        df = df.copy()
        
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].dt.date
        
        # Daily OHLC
        daily = df.groupby('date').agg({
            'high': 'max', 'low': 'min', 'close': 'last'
        }).reset_index()
        
        # Previous day values
        daily['pdh'] = daily['high'].shift(1)
        daily['pdl'] = daily['low'].shift(1)
        
        # Pivot
        prev_close = daily['close'].shift(1)
        daily['pivot'] = (daily['pdh'] + daily['pdl'] + prev_close) / 3
        daily['r1'] = 2 * daily['pivot'] - daily['pdl']
        daily['s1'] = 2 * daily['pivot'] - daily['pdh']
        
        # Merge
        df = df.merge(daily[['date', 'pdh', 'pdl', 'pivot', 'r1', 's1']], on='date', how='left')
        
        for col in ['pdh', 'pdl', 'pivot', 'r1', 's1']:
            df[col] = df[col].ffill()
            df[col] = df[col].fillna(df['close'])
        
        return df

    def detect_midday_bias(self, df: pd.DataFrame) -> pd.DataFrame:
        """Midday/PM session bias (ICT concept)"""
        df = df.copy()
        
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        df['hour'] = df['timestamp'].dt.hour
        
        # PM bias window: 12:00 - 15:00 UTC
        df['pm_bias_window'] = (df['hour'] >= 12) & (df['hour'] <= 15)
        
        return df

    def calculate_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all ICT indicators"""
        df = self.detect_killzone(df)
        df = self.detect_ote(df)
        df = self.detect_daily_levels(df)
        df = self.detect_midday_bias(df)
        return df

    def get_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get ICT signal"""
        df_calc = self.calculate_all(df)
        last = df_calc.iloc[-1]
        
        active_kz = None
        if last.get('london_kz', False):
            active_kz = 'london'
        elif last.get('ny_kz', False):
            active_kz = 'ny'
        elif last.get('asia_kz', False):
            active_kz = 'asia'
        
        # Killzone bias
        score = 0
        factors = []
        
        if last.get('in_killzone', False):
            score += 2
            factors.append(f'IN_{active_kz.upper()}_KZ')
        
        if last.get('in_ote_zone', False):
            score += 1
            factors.append('IN_OTE_ZONE')
        
        # Price vs daily levels
        close = float(last['close'])
        pdh = float(last['pdh'])
        pdl = float(last['pdl'])
        
        if close > pdh:
            score += 1
            factors.append('ABOVE_PDH')
        if close < pdl:
            score -= 1
            factors.append('BELOW_PDL')
        
        direction = 'neutral'
        if score >= 2:
            direction = 'long'
        elif score <= -1:
            direction = 'short'
        
        return {
            'method': 'ict',
            'direction': direction,
            'score': score,
            'factors': factors,
            
            # Killzone
            'in_killzone': bool(last.get('in_killzone', False)),
            'active_kz': active_kz,
            'in_london_kz': bool(last.get('london_kz', False)),
            'in_ny_kz': bool(last.get('ny_kz', False)),
            'in_asia_kz': bool(last.get('asia_kz', False)),
            
            # OTE
            'ote_382': float(last.get('ote_382', 0)),
            'ote_618': float(last.get('ote_618', 0)),
            'ote_786': float(last.get('ote_786', 0)),
            'in_ote_zone': bool(last.get('in_ote_zone', False)),
            
            # Daily Levels
            'pdh': pdh,
            'pdl': pdl,
            'pivot': float(last.get('pivot', 0)),
            'r1': float(last.get('r1', 0)),
            's1': float(last.get('s1', 0)),
            'above_pdh': close > pdh,
            'below_pdl': close < pdl
        }


# ============================================================
# METHOD 4: ULTRA CONF LUENCE MATRIX
# Hybrid - Kết hợp tất cả 3 phương pháp
# ============================================================

class UltraConfluenceMatrix:
    """
    Method 4: Ultra Confluence Matrix
    Triết lý: Kết hợp đa lớp 3 phương pháp
    - Lớp 1: PD Array Zone Filter (Premium/Discount)
    - Lớp 2: Structure Confirmation (SMC)
    - Lớp 3: Indicator Confirmation (EMA/RSI)
    - Lớp 4: Timing Filter (ICT Killzone)
    """

    def __init__(self):
        self.indicator = IndicatorMethod()
        self.smc = SMCWithIndicators()
        self.ict = ICTMethod()

    def get_confluence(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate Ultra Confluence Matrix"""
        
        # Get signals from each method
        ind_signal = self.indicator.get_signal(df)
        smc_signal = self.smc.get_signal(df)
        ict_signal = self.ict.get_signal(df)
        
        # Count confluences
        buy_confluence = 0
        sell_confluence = 0
        layers = {}
        
        # Layer 1: PD Zone Filter (from SMC)
        if smc_signal.get('in_discount', False):
            buy_confluence += 2
            layers['pd_zone'] = {'bull': True, 'bear': False}
        elif smc_signal.get('in_premium', False):
            sell_confluence += 2
            layers['pd_zone'] = {'bull': False, 'bear': True}
        else:
            layers['pd_zone'] = {'bull': False, 'bear': False}
        
        # Layer 2: Structure Confirmation (from SMC)
        if smc_signal.get('bull_mss', False):
            buy_confluence += 3
        if smc_signal.get('bull_choch', False):
            buy_confluence += 2
        if smc_signal.get('bull_sweep', False):
            buy_confluence += 1
            
        if smc_signal.get('bear_mss', False):
            sell_confluence += 3
        if smc_signal.get('bear_choch', False):
            sell_confluence += 2
        if smc_signal.get('bear_sweep', False):
            sell_confluence += 1
        
        layers['structure'] = {
            'bull': smc_signal.get('bull_mss', False) or smc_signal.get('bull_choch', False),
            'bear': smc_signal.get('bear_mss', False) or smc_signal.get('bear_choch', False)
        }
        
        # Layer 3: Indicator Confirmation
        if ind_signal.get('ema_bull_stack', False):
            buy_confluence += 2
        if ind_signal.get('ema_bear_stack', False):
            sell_confluence += 2
            
        rsi = ind_signal.get('rsi', 50)
        if rsi < 40:
            buy_confluence += 1
        if rsi > 60:
            sell_confluence += 1
        
        layers['indicators'] = {
            'ema_bull': ind_signal.get('ema_bull_stack', False),
            'ema_bear': ind_signal.get('ema_bear_stack', False),
            'rsi': rsi
        }
        
        # Layer 4: Timing Filter (ICT)
        if ict_signal.get('in_killzone', False):
            if buy_confluence > sell_confluence:
                buy_confluence += 1
            elif sell_confluence > buy_confluence:
                sell_confluence += 1
        
        layers['timing'] = {
            'in_killzone': ict_signal.get('in_killzone', False),
            'active_kz': ict_signal.get('active_kz')
        }
        
        # Determine signal
        total_confluence = buy_confluence + sell_confluence
        
        if total_confluence < 4:
            strength = 'NO_TRADE'
            direction = 'neutral'
        elif total_confluence < 7:
            strength = 'WEAK'
            direction = 'long' if buy_confluence > sell_confluence else 'short'
        elif total_confluence < 10:
            strength = 'VALID'
            direction = 'long' if buy_confluence > sell_confluence else 'short'
        else:
            strength = 'STRONG'
            direction = 'long' if buy_confluence > sell_confluence else 'short'
        
        # Calculate confidence
        max_possible = 8  # 2 + 3 + 2 + 1
        confidence = total_confluence / max_possible * 100
        
        return {
            'method': 'ultra_confluence',
            'direction': direction,
            'strength': strength,
            'confidence': min(confidence, 100),
            
            'buy_confluence': buy_confluence,
            'sell_confluence': sell_confluence,
            'total_confluence': total_confluence,
            
            'layers': layers,
            
            # All method signals
            'indicator': ind_signal,
            'smc': smc_signal,
            'ict': ict_signal,
            
            # Entry levels
            'entry_price': float(df['close'].iloc[-1]),
            'atr': ind_signal.get('atr', 0),
            'equilibrium': smc_signal.get('equilibrium', 0),
            'swing_high': smc_signal.get('swing_high', 0),
            'swing_low': smc_signal.get('swing_low', 0)
        }


# ============================================================
# MAIN SIGNAL ENGINE
# ============================================================

class SignalEngine:
    """
    Main Signal Engine - Combines all 4 methods
    """

    def __init__(self):
        self.indicator = IndicatorMethod()
        self.smc = SMCWithIndicators()
        self.ict = ICTMethod()
        self.ultra = UltraConfluenceMatrix()

    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Complete analysis from all 4 methods"""
        
        # Get individual method signals
        ind = self.indicator.get_signal(df)
        smc = self.smc.get_signal(df)
        ict = self.ict.get_signal(df)
        ultra = self.ultra.get_confluence(df)
        
        return {
            'timestamp': pd.Timestamp.now().isoformat(),
            'symbol': 'XAUUSD',
            
            # Method 1: Indicator-Based
            'method1_indicator': ind,
            
            # Method 2: SMC + Indicators
            'method2_smc': smc,
            
            # Method 3: ICT
            'method3_ict': ict,
            
            # Method 4: Ultra Confluence
            'method4_ultra': ultra,
            
            # Best signal recommendation
            'recommended_signal': {
                'direction': ultra['direction'],
                'strength': ultra['strength'],
                'confidence': ultra['confidence'],
                'entry_price': ultra['entry_price'],
                'atr': ultra['atr'],
                'stop_loss_long': ultra['entry_price'] - (ultra['atr'] * 1.5),
                'stop_loss_short': ultra['entry_price'] + (ultra['atr'] * 1.5),
                'tp_long': ultra['entry_price'] + (ultra['atr'] * 3),
                'tp_short': ultra['entry_price'] - (ultra['atr'] * 3)
            }
        }
