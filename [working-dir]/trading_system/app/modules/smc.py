"""
Smart Money Concepts (SMC) Module
Implements: Market Structure, FVG, OB, Liquidity, BOS/CHoCH/MSS
"""
import numpy as np
import pandas as pd
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from app.models.data_models import FVGZone, OrderBlock, LiquidityZone, SwingLevels


@dataclass
class SMCConfig:
    """SMC Configuration"""
    swing_lookback: int = 20
    fvg_lookback: int = 3
    equal_tolerance: float = 0.001
    ob_min_body_ratio: float = 0.60
    atr_period: int = 14


class MarketStructure:
    """
    Market Structure Detection
    Implements: HH, HL, LH, LL, BOS, CHoCH, MSS
    """
    
    def __init__(self, config: Optional[SMCConfig] = None):
        self.config = config or SMCConfig()
    
    def detect_swings(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect swing highs and lows"""
        df = df.copy()
        lookback = self.config.swing_lookback
        
        # Swing Highs
        df['swing_high'] = df['high'].rolling(lookback + 1).max().shift(1)
        df['is_swing_high'] = (df['high'] == df['swing_high']) & (df['high'] > df['high'].shift(1)) & (df['high'] > df['high'].shift(-1))
        
        # Swing Lows
        df['swing_low'] = df['low'].rolling(lookback + 1).min().shift(1)
        df['is_swing_low'] = (df['low'] == df['swing_low']) & (df['low'] < df['low'].shift(1)) & (df['low'] < df['low'].shift(-1))
        
        # Store swing levels for tracking
        swing_highs = []
        swing_lows = []
        swing_high_bars = []
        swing_low_bars = []
        
        for i in range(len(df)):
            if df['is_swing_high'].iloc[i]:
                swing_highs.append(df['high'].iloc[i])
                swing_high_bars.append(i)
            if df['is_swing_low'].iloc[i]:
                swing_lows.append(df['low'].iloc[i])
                swing_low_bars.append(i)
        
        df['swing_high_price'] = np.nan
        df['swing_low_price'] = np.nan
        
        return df
    
    def calculate_structure(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate market structure"""
        df = self.detect_swings(df)
        
        # Get previous swing levels
        df['prev_swing_high'] = df['swing_high'].shift(1)
        df['prev_swing_low'] = df['swing_low'].shift(1)
        
        # Current swing
        df['current_swing_high'] = df['swing_high_price']
        df['current_swing_low'] = df['swing_low_price']
        
        # Higher High / Higher Low / Lower High / Lower Low
        df['hh'] = df['high'] > df['prev_swing_high']
        df['hl'] = (df['low'] > df['prev_swing_low']) & (df['high'] < df['prev_swing_high'])
        df['lh'] = (df['high'] < df['prev_swing_high']) & (df['low'] < df['prev_swing_low'])
        df['ll'] = df['low'] < df['prev_swing_low']
        
        # Bullish Structure: HH > HL > HH > HL
        df['bull_structure'] = df['hh'] | df['hl']
        
        # Bearish Structure: LH > LL > LH > LL
        df['bear_structure'] = df['lh'] | df['ll']
        
        return df
    
    def get_structure(self, df: pd.DataFrame) -> dict:
        """Get current market structure"""
        df_calc = self.calculate_structure(df)
        last = df_calc.iloc[-1]
        
        return {
            'swing_high': last.get('swing_high', None),
            'swing_low': last.get('swing_low', None),
            'prev_swing_high': last.get('prev_swing_high', None),
            'prev_swing_low': last.get('prev_swing_low', None),
            'hh': bool(last.get('hh', False)),
            'hl': bool(last.get('hl', False)),
            'lh': bool(last.get('lh', False)),
            'll': bool(last.get('ll', False)),
            'bull_structure': bool(last.get('bull_structure', False)),
            'bear_structure': bool(last.get('bear_structure', False)),
            'bull_trend': last.get('hh', False) and last.get('hl', False),
            'bear_trend': last.get('lh', False) and last.get('ll', False)
        }


class FVGDetector:
    """
    Fair Value Gap Detection
    
    Bullish FVG: Low[0] > High[2]
    Bearish FVG: High[0] < Low[2]
    """
    
    def __init__(self, config: Optional[SMCConfig] = None):
        self.config = config or SMCConfig()
        self.fvgs: List[FVGZone] = []
    
    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect FVG zones"""
        df = df.copy()
        
        # Bullish FVG: Gap between candle 2 and candle 0
        df['bullish_fvg'] = df['low'] > df['high'].shift(2)
        df['bull_fvg_top'] = df['low']
        df['bull_fvg_bottom'] = df['high'].shift(2)
        
        # Bearish FVG: Gap between candle 2 and candle 0
        df['bearish_fvg'] = df['high'] < df['low'].shift(2)
        df['bear_fvg_top'] = df['low'].shift(2)
        df['bear_fvg_bottom'] = df['high']
        
        return df
    
    def get_fvgs(self, df: pd.DataFrame) -> Dict[str, List[dict]]:
        """Get all active FVG zones"""
        df_calc = self.detect(df)
        last = df_calc.iloc[-1]
        
        bull_fvgs = []
        bear_fvgs = []
        
        # Check last 10 candles for FVG
        for i in range(-1, -min(11, len(df_calc)), -1):
            row = df_calc.iloc[i]
            
            if row['bullish_fvg']:
                fvg = FVGZone(
                    type="bullish",
                    top=float(row['bull_fvg_top']),
                    bottom=float(row['bull_fvg_bottom']),
                    mid=float((row['bull_fvg_top'] + row['bull_fvg_bottom']) / 2),
                    start_time=df_calc['timestamp'].iloc[i],
                    end_time=df_calc['timestamp'].iloc[i - 2] if i - 2 >= 0 else df_calc['timestamp'].iloc[0],
                    is_active=True,
                    is_filled=False
                )
                bull_fvgs.append(fvg.model_dump())
                self.fvgs.append(fvg)
            
            if row['bearish_fvg']:
                fvg = FVGZone(
                    type="bearish",
                    top=float(row['bear_fvg_top']),
                    bottom=float(row['bear_fvg_bottom']),
                    mid=float((row['bear_fvg_top'] + row['bear_fvg_bottom']) / 2),
                    start_time=df_calc['timestamp'].iloc[i],
                    end_time=df_calc['timestamp'].iloc[i - 2] if i - 2 >= 0 else df_calc['timestamp'].iloc[0],
                    is_active=True,
                    is_filled=False
                )
                bear_fvgs.append(fvg.model_dump())
                self.fvgs.append(fvg)
        
        return {
            'bullish': bull_fvgs,
            'bearish': bear_fvgs
        }
    
    def is_in_fvg(self, df: pd.DataFrame) -> Tuple[bool, bool]:
        """Check if current price is inside any FVG"""
        bull_fvgs = []
        bear_fvgs = []
        
        for i in range(-1, -min(11, len(df)), -1):
            row = df.iloc[i]
            if row['low'] > df['high'].shift(2).iloc[i]:
                bull_fvgs.append({
                    'top': float(row['low']),
                    'bottom': float(df['high'].shift(2).iloc[i])
                })
            if row['high'] < df['low'].shift(2).iloc[i]:
                bear_fvgs.append({
                    'top': float(df['low'].shift(2).iloc[i]),
                    'bottom': float(row['high'])
                })
        
        current_price = df['close'].iloc[-1]
        
        bull_in_fvg = any(f['top'] >= current_price >= f['bottom'] for f in bull_fvgs)
        bear_in_fvg = any(f['top'] >= current_price >= f['bottom'] for f in bear_fvgs)
        
        return bull_in_fvg, bear_in_fvg


class OrderBlockDetector:
    """
    Order Block Detection
    
    Bullish OB: Bearish candle before bullish displacement
    Bearish OB: Bullish candle before bearish displacement
    """
    
    def __init__(self, config: Optional[SMCConfig] = None):
        self.config = config or SMCConfig()
        self.order_blocks: List[OrderBlock] = []
    
    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect Order Blocks"""
        df = df.copy()
        
        # Bullish OB: Bearish candle before bullish DPL
        df['bullish_ob'] = (
            (df['close'] < df['open']).shift(1) &  # Previous candle bearish
            (df['close'] > df['open']) &  # Current candle bullish
            (df['high'] > df['high'].shift(1))  # Breaks previous high
        )
        
        # Bearish OB: Bullish candle before bearish DPL
        df['bearish_ob'] = (
            (df['close'] > df['open']).shift(1) &  # Previous candle bullish
            (df['close'] < df['open']) &  # Current candle bearish
            (df['low'] < df['low'].shift(1))  # Breaks previous low
        )
        
        # OB zones
        df['bull_ob_top'] = df['open'].shift(1)
        df['bull_ob_bottom'] = df['low'].shift(1)
        
        df['bear_ob_top'] = df['high'].shift(1)
        df['bear_ob_bottom'] = df['open'].shift(1)
        
        return df
    
    def get_order_blocks(self, df: pd.DataFrame) -> Dict[str, List[dict]]:
        """Get all active Order Blocks"""
        df_calc = self.detect(df)
        last = df_calc.iloc[-1]
        
        bull_obs = []
        bear_obs = []
        
        for i in range(-1, -min(11, len(df_calc)), -1):
            row = df_calc.iloc[i]
            
            if row['bullish_ob']:
                ob = OrderBlock(
                    type="bullish",
                    top=float(row['bull_ob_top']),
                    bottom=float(row['bull_ob_bottom']),
                    start_time=df_calc['timestamp'].iloc[i - 1] if i - 1 >= 0 else df_calc['timestamp'].iloc[0],
                    end_time=df_calc['timestamp'].iloc[i],
                    trigger_candle_time=df_calc['timestamp'].iloc[i],
                    is_active=True,
                    is_broken=False
                )
                bull_obs.append(ob.model_dump())
                self.order_blocks.append(ob)
            
            if row['bearish_ob']:
                ob = OrderBlock(
                    type="bearish",
                    top=float(row['bear_ob_top']),
                    bottom=float(row['bear_ob_bottom']),
                    start_time=df_calc['timestamp'].iloc[i - 1] if i - 1 >= 0 else df_calc['timestamp'].iloc[0],
                    end_time=df_calc['timestamp'].iloc[i],
                    trigger_candle_time=df_calc['timestamp'].iloc[i],
                    is_active=True,
                    is_broken=False
                )
                bear_obs.append(ob.model_dump())
                self.order_blocks.append(ob)
        
        return {
            'bullish': bull_obs,
            'bearish': bear_obs
        }


class LiquidityDetector:
    """
    Liquidity Detection
    Implements: BSL, SSL, Equal Highs/Lows, Liquidity Sweep
    """
    
    def __init__(self, config: Optional[SMCConfig] = None):
        self.config = config or SMCConfig()
        self.liquidity_zones: List[LiquidityZone] = []
    
    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect liquidity zones"""
        df = df.copy()
        lookback = self.config.swing_lookback
        tolerance = self.config.equal_tolerance
        
        # Get swing levels
        df['swing_high'] = df['high'].rolling(lookback + 1).max().shift(1)
        df['swing_low'] = df['low'].rolling(lookback + 1).min().shift(1)
        
        # Equal Highs (BSL candidates)
        df['is_equal_high'] = abs(df['high'] - df['high'].shift(1)) <= tolerance
        
        # Equal Lows (SSL candidates)
        df['is_equal_low'] = abs(df['low'] - df['low'].shift(1)) <= tolerance
        
        # Liquidity Sweep - Bullish
        df['bull_liquidity_sweep'] = (
            (df['low'] < df['swing_low']) &
            (df['close'] > df['swing_low'])
        )
        
        # Liquidity Sweep - Bearish
        df['bear_liquidity_sweep'] = (
            (df['high'] > df['swing_high']) &
            (df['close'] < df['swing_high'])
        )
        
        return df
    
    def get_liquidity(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get liquidity information"""
        df_calc = self.detect(df)
        last = df_calc.iloc[-1]
        
        equal_highs = []
        equal_lows = []
        
        for i in range(-1, -min(21, len(df_calc)), -1):
            if df_calc['is_equal_high'].iloc[i]:
                equal_highs.append(float(df_calc['high'].iloc[i]))
            if df_calc['is_equal_low'].iloc[i]:
                equal_lows.append(float(df_calc['low'].iloc[i]))
        
        return {
            'equal_highs': equal_highs[:5],
            'equal_lows': equal_lows[:5],
            'bsl': max(equal_highs) if equal_highs else float(last.get('swing_high', 0)),
            'ssl': min(equal_lows) if equal_lows else float(last.get('swing_low', 0)),
            'bull_sweep': bool(last.get('bull_liquidity_sweep', False)),
            'bear_sweep': bool(last.get('bear_liquidity_sweep', False)),
            'swing_high': float(last.get('swing_high', 0)),
            'swing_low': float(last.get('swing_low', 0))
        }


class BOSCHoCHDetector:
    """
    BOS and CHoCH Detection
    
    Bullish BOS: Close > Previous Swing High
    Bearish BOS: Close < Previous Swing Low
    
    Bullish CHoCH: LL → LH → Close > LH
    Bearish CHoCH: HH → HL → Close < HL
    """
    
    def __init__(self):
        self.last_bos_type = None
        self.last_choch_type = None
    
    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect BOS and CHoCH"""
        df = df.copy()
        lookback = 20
        
        # Get swing levels
        df['swing_high'] = ta_highest(df['high'], lookback)
        df['swing_low'] = ta_lowest(df['low'], lookback)
        df['prev_swing_high'] = df['swing_high'].shift(lookback)
        df['prev_swing_low'] = df['swing_low'].shift(lookback)
        
        # Bullish BOS
        df['bull_bos'] = df['close'] > df['prev_swing_high']
        
        # Bearish BOS
        df['bear_bos'] = df['close'] < df['prev_swing_low']
        
        # CHoCH Detection (simplified)
        # Check if price broke a recent low then made a higher low
        df['hl'] = (df['low'] > df['low'].shift(1)) & (df['low'] < df['low'].shift(2))
        df['lh'] = (df['high'] < df['high'].shift(1)) & (df['high'] > df['high'].shift(2))
        
        df['bull_choch'] = df['hl'].shift(1) & (df['close'] > df['high'].shift(1))
        df['bear_choch'] = df['lh'].shift(1) & (df['close'] < df['low'].shift(1))
        
        return df
    
    def get_bos_choch(self, df: pd.DataFrame) -> Dict[str, bool]:
        """Get BOS/CHoCH status"""
        df_calc = self.detect(df)
        last = df_calc.iloc[-1]
        
        return {
            'bull_bos': bool(last.get('bull_bos', False)),
            'bear_bos': bool(last.get('bear_bos', False)),
            'bull_choch': bool(last.get('bull_choch', False)),
            'bear_choch': bool(last.get('bear_choch', False)),
            'bull_mss': bool(last.get('bull_bos', False)) or bool(last.get('bull_choch', False)),
            'bear_mss': bool(last.get('bear_bos', False)) or bool(last.get('bear_choch', False))
        }


# Helper functions
def ta_highest(series: pd.Series, period: int) -> pd.Series:
    """Calculate highest over period"""
    return series.rolling(period + 1).max().shift(1)

def ta_lowest(series: pd.Series, period: int) -> pd.Series:
    """Calculate lowest over period"""
    return series.rolling(period + 1).min().shift(1)


class SMCAnalyzer:
    """
    Complete SMC Analysis
    Combines all SMC components
    """
    
    def __init__(self, config: Optional[SMCConfig] = None):
        self.config = config or SMCConfig()
        self.structure = MarketStructure(config)
        self.fvg = FVGDetector(config)
        self.ob = OrderBlockDetector(config)
        self.liquidity = LiquidityDetector(config)
        self.bos_choch = BOSCHoCHDetector()
    
    def analyze(self, df: pd.DataFrame, displacement_bull: pd.Series = None, displacement_bear: pd.Series = None) -> Dict[str, Any]:
        """Complete SMC analysis"""
        
        # Calculate structure
        structure = self.structure.get_structure(df)
        
        # Get FVG zones
        fvgs = self.fvg.get_fvgs(df)
        
        # Get Order Blocks
        obs = self.ob.get_order_blocks(df)
        
        # Get Liquidity
        liquidity = self.liquidity.get_liquidity(df)
        
        # Get BOS/CHoCH
        bos_choch = self.bos_choch.get_bos_choch(df)
        
        # Calculate FVG detection
        df_calc = self.fvg.detect(df)
        bull_fvg = bool(df_calc['bullish_fvg'].iloc[-1])
        bear_fvg = bool(df_calc['bearish_fvg'].iloc[-1])
        
        # Calculate displacement
        avg_r = df['high'] - df['low']
        avg_r_14 = avg_r.rolling(14).mean()
        
        bull_dpl = (
            (df['close'] > df['open']) &
            ((abs(df['close'] - df['open'])) / df_calc['range'] >= 0.65) &
            (df_calc['range'] > avg_r_14)
        ).iloc[-1]
        
        bear_dpl = (
            (df['close'] < df['open']) &
            ((abs(df['close'] - df['open'])) / df_calc['range'] >= 0.65) &
            (df_calc['range'] > avg_r_14)
        ).iloc[-1]
        
        return {
            # Structure
            'swing_high': structure['swing_high'],
            'swing_low': structure['swing_low'],
            'hh': structure['hh'],
            'hl': structure['hl'],
            'lh': structure['lh'],
            'll': structure['ll'],
            'bull_trend': structure['bull_trend'],
            'bear_trend': structure['bear_trend'],
            
            # FVG
            'bull_fvg': bull_fvg,
            'bear_fvg': bear_fvg,
            'bull_fvgs': fvgs['bullish'],
            'bear_fvgs': fvgs['bearish'],
            
            # Order Blocks
            'bull_ob': len(obs['bullish']) > 0,
            'bear_ob': len(obs['bearish']) > 0,
            'bull_obs': obs['bullish'],
            'bear_obs': obs['bearish'],
            
            # Liquidity
            'bsl': liquidity['bsl'],
            'ssl': liquidity['ssl'],
            'bull_sweep': liquidity['bull_sweep'],
            'bear_sweep': liquidity['bear_sweep'],
            'equal_highs': liquidity['equal_highs'],
            'equal_lows': liquidity['equal_lows'],
            
            # BOS/CHoCH/MSS
            **bos_choch,
            
            # Displacement
            'bull_displacement': bull_dpl,
            'bear_displacement': bear_dpl,
            
            # Discount/Premium
            'equilibrium': (structure['swing_high'] + structure['swing_low']) / 2 if structure['swing_high'] and structure['swing_low'] else 0,
            'in_discount': df['close'].iloc[-1] < ((structure['swing_high'] + structure['swing_low']) / 2) if structure['swing_high'] and structure['swing_low'] else False,
            'in_premium': df['close'].iloc[-1] > ((structure['swing_high'] + structure['swing_low']) / 2) if structure['swing_high'] and structure['swing_low'] else False
        }
