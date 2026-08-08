"""
Scoring Engine & Signal Generator
Combines SMC, ICT, Price Action, and Sniper modules
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass
import uuid

from app.models.data_models import (
    TradingSignal, ScoreBreakdown, TradeDirection, SignalType,
    FVGZone, OrderBlock, LiquidityZone, MarketBias
)


@dataclass
class SignalConfig:
    """Signal generation configuration"""
    # Score thresholds
    smc_score_min_strong: int = 10
    smc_score_min_valid: int = 7
    sniper_pct_threshold: int = 40
    
    # Filters
    require_htf_confluence: bool = True
    require_adx: bool = True
    require_volume: bool = True
    require_pattern: bool = True


class ScoringEngine:
    """
    Complete Scoring Engine
    Combines all modules and calculates total scores
    """
    
    def __init__(self, config: Optional[SignalConfig] = None):
        self.config = config or SignalConfig()
    
    def calculate_smc_score(self, smc_data: Dict, htf_data: Dict = None) -> Dict[str, Any]:
        """
        Calculate SMC Score (0-13 points)
        
        BUY Factors:
        +1 HTF Bullish Bias
        +1 Discount Zone
        +1 SSL Sweep
        +1 Equal Lows
        +1 Bullish Engulfing
        +1 Bullish Pin Bar
        +1 Bullish Rejection
        +1 Bullish Displacement
        +1 Bullish CHoCH
        +1 Bullish MSS
        +1 Bullish BOS
        +1 Bullish FVG
        +1 Bullish OB
        """
        
        buy_score = 0
        sell_score = 0
        
        # HTF Bias
        if htf_data:
            if htf_data.get('bullish', False):
                buy_score += 1
            if htf_data.get('bearish', False):
                sell_score += 1
        
        # Discount/Premium Zone
        if smc_data.get('in_discount', False):
            buy_score += 1
        if smc_data.get('in_premium', False):
            sell_score += 1
        
        # Liquidity Sweep
        if smc_data.get('bull_sweep', False):
            buy_score += 1
        if smc_data.get('bear_sweep', False):
            sell_score += 1
        
        # Equal Lows/Highs
        if smc_data.get('equal_lows', []):
            buy_score += 1
        if smc_data.get('equal_highs', []):
            sell_score += 1
        
        # Order Blocks
        if smc_data.get('bull_ob', False):
            buy_score += 1
        if smc_data.get('bear_ob', False):
            sell_score += 1
        
        # Displacement
        if smc_data.get('bull_displacement', False):
            buy_score += 1
        if smc_data.get('bear_displacement', False):
            sell_score += 1
        
        # CHoCH
        if smc_data.get('bull_choch', False):
            buy_score += 1
        if smc_data.get('bear_choch', False):
            sell_score += 1
        
        # MSS
        if smc_data.get('bull_mss', False):
            buy_score += 1
        if smc_data.get('bear_mss', False):
            sell_score += 1
        
        # BOS
        if smc_data.get('bull_bos', False):
            buy_score += 1
        if smc_data.get('bear_bos', False):
            sell_score += 1
        
        # FVG
        if smc_data.get('bull_fvg', False):
            buy_score += 1
        if smc_data.get('bear_fvg', False):
            sell_score += 1
        
        return {
            'smc_buy_score': buy_score,
            'smc_sell_score': sell_score,
            'htf_bullish': htf_data.get('bullish', False) if htf_data else False,
            'htf_bearish': htf_data.get('bearish', False) if htf_data else False,
            'discount_zone': smc_data.get('in_discount', False),
            'premium_zone': smc_data.get('in_premium', False),
            'ssl_sweep': smc_data.get('bull_sweep', False),
            'bsl_sweep': smc_data.get('bear_sweep', False),
            'bull_ob': smc_data.get('bull_ob', False),
            'bear_ob': smc_data.get('bear_ob', False),
            'bull_displacement': smc_data.get('bull_displacement', False),
            'bear_displacement': smc_data.get('bear_displacement', False),
            'bull_choch': smc_data.get('bull_choch', False),
            'bear_choch': smc_data.get('bear_choch', False),
            'bull_mss': smc_data.get('bull_mss', False),
            'bear_mss': smc_data.get('bear_mss', False),
            'bull_bos': smc_data.get('bull_bos', False),
            'bear_bos': smc_data.get('bear_bos', False),
            'bull_fvg': smc_data.get('bull_fvg', False),
            'bear_fvg': smc_data.get('bear_fvg', False)
        }
    
    def calculate_combined_score(self, 
                                 smc_scores: Dict,
                                 sniper_scores: Dict,
                                 pa_scores: Dict,
                                 ict_data: Dict) -> Dict[str, Any]:
        """Calculate combined total score"""
        
        # SMC scores
        smc_buy = smc_scores['smc_buy_score']
        smc_sell = smc_scores['smc_sell_score']
        
        # Sniper scores (0-7)
        sniper_buy = sniper_scores.get('sniper_bull_score', 0)
        sniper_sell = sniper_scores.get('sniper_bear_score', 0)
        
        # Price Action scores
        pa_buy = pa_scores.get('bullish_score', 0)
        pa_sell = pa_scores.get('bearish_score', 0)
        
        # ICT factors
        ict_buy = 0
        ict_sell = 0
        if ict_data.get('in_killzone', False):
            ict_buy += 0.5 if ict_data.get('active_kz') in ['london', 'ny'] else 0
            ict_sell += 0.5 if ict_data.get('active_kz') in ['london', 'ny'] else 0
        if ict_data.get('in_ote_zone', False):
            ict_buy += 1
            ict_sell += 1
        if ict_data.get('bullish_judas', False):
            ict_buy += 2
        if ict_data.get('bearish_judas', False):
            ict_sell += 2
        if ict_data.get('bull_po3', False):
            ict_buy += 2
        if ict_data.get('bear_po3', False):
            ict_sell += 2
        
        # Total scores
        total_buy = smc_buy + sniper_buy + pa_buy + int(ict_buy)
        total_sell = smc_sell + sniper_sell + pa_sell + int(ict_sell)
        
        # Determine signal type
        if total_buy >= 15:
            signal_type = SignalType.STRONG_BUY
        elif total_buy >= 10:
            signal_type = SignalType.BUY
        elif total_sell >= 15:
            signal_type = SignalType.STRONG_SELL
        elif total_sell >= 10:
            signal_type = SignalType.SELL
        else:
            signal_type = SignalType.NEUTRAL
        
        return {
            'total_buy_score': total_buy,
            'total_sell_score': total_sell,
            'smc_score': smc_buy if total_buy >= total_sell else smc_sell,
            'sniper_score': sniper_buy if total_buy >= total_sell else sniper_sell,
            'pa_score': pa_buy if total_buy >= total_sell else pa_sell,
            'signal_type': signal_type,
            'bullish_confidence': (total_buy / 20) * 100,
            'bearish_confidence': (total_sell / 20) * 100
        }


class SignalGenerator:
    """
    Trading Signal Generator
    Combines all analysis to generate actionable signals
    """
    
    def __init__(self, config: Optional[SignalConfig] = None):
        self.config = config or SignalConfig()
        self.scoring_engine = ScoringEngine(config)
    
    def generate_signal(self,
                       df: pd.DataFrame,
                       smc_data: Dict,
                       ict_data: Dict,
                       sniper_data: Dict,
                       pa_data: Dict,
                       htf_data: Dict = None,
                       symbol: str = "UNKNOWN",
                       timeframe: str = "1h") -> Optional[TradingSignal]:
        """
        Generate complete trading signal
        """
        
        current_price = float(df['close'].iloc[-1])
        atr = float(sniper_data.get('atr', df['high'].iloc[-1] - df['low'].iloc[-1]))
        
        # Calculate scores
        smc_scores = self.scoring_engine.calculate_smc_score(smc_data, htf_data)
        combined_scores = self.scoring_engine.calculate_combined_score(
            smc_scores, sniper_data, pa_data, ict_data
        )
        
        # Determine direction
        direction = TradeDirection.FLAT
        signal_type = combined_scores['signal_type']
        
        if signal_type in [SignalType.STRONG_BUY, SignalType.BUY]:
            direction = TradeDirection.LONG
        elif signal_type in [SignalType.STRONG_SELL, SignalType.SELL]:
            direction = TradeDirection.SHORT
        
        # Check filters
        filters_passed = True
        
        if self.config.require_adx:
            if sniper_data.get('adx', 0) < 25:
                filters_passed = False
        
        if self.config.require_volume:
            if not sniper_data.get('vol_high', False):
                filters_passed = False
        
        if self.config.require_htf_confluence and htf_data:
            if direction == TradeDirection.LONG and not htf_data.get('bullish', False):
                filters_passed = False
            if direction == TradeDirection.SHORT and not htf_data.get('bearish', False):
                filters_passed = False
        
        if self.config.require_pattern:
            if pa_data.get('pattern_score', 0) < 1:
                filters_passed = False
        
        if not filters_passed:
            return None
        
        # Calculate entry, SL, TP
        risk = atr * 1.5
        
        if direction == TradeDirection.LONG:
            entry = current_price
            sl = entry - risk
            tp1 = entry + risk * 0.5
            tp2 = entry + risk * 1.0
            tp3 = entry + risk * 2.0
            tp4 = entry + risk * 3.0
            tp5 = entry + risk * 5.0
        elif direction == TradeDirection.SHORT:
            entry = current_price
            sl = entry + risk
            tp1 = entry - risk * 0.5
            tp2 = entry - risk * 1.0
            tp3 = entry - risk * 2.0
            tp4 = entry - risk * 3.0
            tp5 = entry - risk * 5.0
        else:
            return None
        
        # Build reasons list
        reasons = []
        
        # SMC reasons
        if smc_scores.get('htf_bullish'):
            reasons.append("HTF Bullish")
        if smc_scores.get('discount_zone'):
            reasons.append("Discount Zone")
        if smc_scores.get('ssl_sweep'):
            reasons.append("SSL Sweep")
        if smc_scores.get('bull_fvg'):
            reasons.append("Bullish FVG")
        if smc_scores.get('bull_ob'):
            reasons.append("Bullish OB")
        if smc_scores.get('bull_mss'):
            reasons.append("MSS Confirmed")
        if smc_scores.get('bull_bos'):
            reasons.append("BOS Confirmed")
        
        # Sniper reasons
        if sniper_data.get('ema_bull_cross'):
            reasons.append("EMA Bull Cross")
        if sniper_data.get('vwap') and current_price > sniper_data['vwap']:
            reasons.append("Above VWAP")
        if sniper_data.get('adx_strong'):
            reasons.append("ADX Strong")
        if sniper_data.get('macd_bullish'):
            reasons.append("MACD Bullish")
        
        # ICT reasons
        if ict_data.get('in_killzone'):
            reasons.append(f"in {ict_data.get('active_kz', 'KZ').upper()} Killzone")
        if ict_data.get('in_ote_zone'):
            reasons.append("OTE Zone")
        if ict_data.get('bullish_judas'):
            reasons.append("Judas Swing Bull")
        
        # Price Action reasons
        for pattern in pa_data.get('bullish_patterns', []):
            reasons.append(pattern.upper())
        
        # Build score breakdown
        score_breakdown = ScoreBreakdown(
            smc_buy_score=smc_scores['smc_buy_score'],
            smc_sell_score=smc_scores['smc_sell_score'],
            sniper_bull_pct=sniper_data.get('sniper_bull_pct', 0),
            sniper_bear_pct=sniper_data.get('sniper_bear_pct', 0),
            **smc_scores,
            pattern_score=pa_data.get('pattern_score', 0),
            patterns_found=pa_data.get('patterns', []),
            in_killzone=ict_data.get('in_killzone', False),
            killzone_name=ict_data.get('active_kz'),
            in_ote_zone=ict_data.get('in_ote_zone', False)
        )
        
        # Build signal
        signal = TradingSignal(
            signal_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            signal_type=signal_type,
            current_price=current_price,
            entry_price=entry,
            stop_loss=sl,
            take_profit_1=tp1,
            take_profit_2=tp2,
            take_profit_3=tp3,
            take_profit_4=tp4,
            take_profit_5=tp5,
            risk_amount=risk,
            risk_reward_1=0.5,
            risk_reward_2=1.0,
            risk_reward_3=2.0,
            score_breakdown=score_breakdown,
            total_score=combined_scores['total_buy_score'] if direction == TradeDirection.LONG else combined_scores['total_sell_score'],
            confluence_count=len(reasons),
            patterns=pa_data.get('patterns', []),
            signal_reasons=reasons,
            confidence=combined_scores['bullish_confidence'] if direction == TradeDirection.LONG else combined_scores['bearish_confidence']
        )
        
        return signal
    
    def validate_signal(self, signal: TradingSignal) -> Dict[str, Any]:
        """
        Validate signal before trading
        Check all confluence factors
        """
        
        validation = {
            'valid': True,
            'warnings': [],
            'errors': []
        }
        
        # Check minimum score
        if signal.total_score < self.config.smc_score_min_valid:
            validation['valid'] = False
            validation['errors'].append(f"Score too low: {signal.total_score}")
        
        # Check confidence
        if signal.confidence < 50:
            validation['warnings'].append("Low confidence")
        
        # Check RRR
        if signal.risk_reward_1 < 1.0:
            validation['warnings'].append("RR1 below 1:1")
        
        # Check patterns
        if not signal.patterns:
            validation['warnings'].append("No price action pattern")
        
        return validation


class MarketBiasAnalyzer:
    """
    Market Bias Analyzer
    Determines overall market bias for a symbol
    """
    
    def __init__(self):
        pass
    
    def analyze(self, 
                smc_data: Dict,
                sniper_data: Dict,
                htf_data: Dict = None) -> MarketBias:
        """Analyze market bias"""
        
        bull_factors = 0
        bear_factors = 0
        
        # HTF
        if htf_data:
            if htf_data.get('bullish'):
                bull_factors += 2
            if htf_data.get('bearish'):
                bear_factors += 2
        
        # Sniper
        if sniper_data.get('sniper_bull_pct', 0) > 60:
            bull_factors += 1
        if sniper_data.get('sniper_bear_pct', 0) > 60:
            bear_factors += 1
        
        if sniper_data.get('ribbon_bull'):
            bull_factors += 1
        if sniper_data.get('ribbon_bear'):
            bear_factors += 1
        
        if sniper_data.get('price_above_vwap'):
            bull_factors += 1
        if sniper_data.get('price_below_vwap'):
            bear_factors += 1
        
        # SMC
        if smc_data.get('in_discount'):
            bull_factors += 1
        if smc_data.get('in_premium'):
            bear_factors += 1
        
        if smc_data.get('bull_trend'):
            bull_factors += 2
        if smc_data.get('bear_trend'):
            bear_factors += 2
        
        if smc_data.get('bull_mss'):
            bull_factors += 2
        if smc_data.get('bear_mss'):
            bear_factors += 2
        
        # Determine bias
        diff = bull_factors - bear_factors
        
        if diff >= 3:
            direction = "bull"
            strength = "strong"
        elif diff > 0:
            direction = "bull"
            strength = "mild"
        elif diff <= -3:
            direction = "bear"
            strength = "strong"
        elif diff < 0:
            direction = "bear"
            strength = "mild"
        else:
            direction = "neutral"
            strength = "weak"
        
        return MarketBias(
            direction=direction,
            strength=strength,
            htf_bullish=htf_data.get('bullish', False) if htf_data else False,
            htf_bearish=htf_data.get('bearish', False) if htf_data else False,
            in_discount=smc_data.get('in_discount', False),
            in_premium=smc_data.get('in_premium', False)
        )
