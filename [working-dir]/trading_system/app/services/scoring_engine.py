"""
Scoring Engine & Signal Generator
Standalone version - no external dependencies
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field
import uuid


class TradeDirection:
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class SignalType:
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


@dataclass
class ScoreBreakdown:
    """Score breakdown for a signal"""
    smc_buy_score: int = 0
    smc_sell_score: int = 0
    sniper_bull_pct: float = 0.0
    sniper_bear_pct: float = 0.0
    
    # SMC factors
    htf_bullish: bool = False
    htf_bearish: bool = False
    discount_zone: bool = False
    premium_zone: bool = False
    ssl_sweep: bool = False
    bsl_sweep: bool = False
    bull_engulfing: bool = False
    bear_engulfing: bool = False
    bull_pinbar: bool = False
    bear_pinbar: bool = False
    bull_displacement: bool = False
    bear_displacement: bool = False
    bull_choch: bool = False
    bear_choch: bool = False
    bull_mss: bool = False
    bear_mss: bool = False
    bull_bos: bool = False
    bear_bos: bool = False
    bull_fvg: bool = False
    bear_fvg: bool = False
    bull_ob: bool = False
    bear_ob: bool = False
    
    # Pattern
    pattern_score: int = 0
    patterns_found: List[str] = field(default_factory=list)
    
    # Killzone
    in_killzone: bool = False
    killzone_name: Optional[str] = None
    
    # OTE
    in_ote_zone: bool = False
    ote_level: Optional[float] = None


@dataclass
class TradingSignal:
    """Complete trading signal"""
    signal_id: str
    timestamp: datetime
    symbol: str
    timeframe: str
    direction: str
    signal_type: str
    
    current_price: float
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    
    risk_amount: float
    risk_reward_1: float
    risk_reward_2: float
    risk_reward_3: float
    
    score_breakdown: ScoreBreakdown
    total_score: int
    confluence_count: int
    
    patterns: List[str] = field(default_factory=list)
    signal_reasons: List[str] = field(default_factory=list)
    
    is_active: bool = True
    triggered_at: Optional[datetime] = None
    confidence: float = 0.0


@dataclass
class MarketBiasResult:
    """Market bias result"""
    direction: str
    strength: str
    score: float


class ScoringEngine:
    """Scoring Engine - combines all modules"""
    
    def __init__(self):
        pass
    
    def calculate_smc_score(self, smc_data: Dict) -> Dict[str, int]:
        """Calculate SMC score (0-13 points)"""
        buy_score = 0
        sell_score = 0
        
        # Market structure
        if smc_data.get('bull_structure', False):
            buy_score += 1
        if smc_data.get('bear_structure', False):
            sell_score += 1
        
        # FVG
        if smc_data.get('bull_fvg', False):
            buy_score += 1
        if smc_data.get('bear_fvg', False):
            sell_score += 1
        
        # Order blocks
        if smc_data.get('bull_order_block', False):
            buy_score += 1
        if smc_data.get('bear_order_block', False):
            sell_score += 1
        
        # MSS
        if smc_data.get('bull_mss', False):
            buy_score += 2
        if smc_data.get('bear_mss', False):
            sell_score += 2
        
        # Higher highs/lows
        if smc_data.get('hh', False):
            buy_score += 1
        if smc_data.get('ll', False):
            sell_score += 1
        
        return {'buy_score': buy_score, 'sell_score': sell_score}
    
    def calculate_pattern_score(self, pa_data: Dict) -> int:
        """Calculate pattern score"""
        score = 0
        score += pa_data.get('pattern_score', 0)
        return max(-10, min(10, score))
    
    def calculate_sniper_score(self, sniper_data: Dict) -> Dict[str, float]:
        """Calculate sniper score"""
        bull_pct = sniper_data.get('sniper_bull_pct', 0)
        bear_pct = sniper_data.get('sniper_bear_pct', 0)
        
        bull_score = bull_pct
        bear_score = bear_pct
        
        return {'bull_score': bull_score, 'bear_score': bear_score}


class SignalGenerator:
    """Signal Generator - creates trading signals"""
    
    def __init__(self):
        self.scoring = ScoringEngine()
    
    def generate_signal(
        self,
        df: pd.DataFrame,
        smc_data: Dict,
        ict_data: Dict,
        sniper_data: Dict,
        pa_data: Dict,
        symbol: str = "BTCUSDT",
        timeframe: str = "1h"
    ) -> Optional[TradingSignal]:
        """Generate trading signal from all modules"""
        
        # Calculate scores
        smc_scores = self.scoring.calculate_smc_score(smc_data)
        pa_score = self.scoring.calculate_pattern_score(pa_data)
        sniper_scores = self.scoring.calculate_sniper_score(sniper_data)
        
        # Total scores
        bull_total = smc_scores['buy_score'] + sniper_scores['bull_score'] + max(0, pa_score)
        bear_total = smc_scores['sell_score'] + sniper_scores['bear_score'] + max(0, -pa_score)
        
        # Determine direction
        if bull_total < 3 and bear_total < 3:
            return None  # No signal
        
        direction = TradeDirection.LONG if bull_total > bear_total else TradeDirection.SHORT
        signal_type = SignalType.STRONG_BUY if bull_total > 8 else SignalType.BUY if bull_total > bear_total else SignalType.SELL if bear_total > 8 else SignalType.NEUTRAL
        
        # Calculate confluence
        confluence = 0
        reasons = []
        
        # SMC confluence
        if smc_data.get('bull_mss', False) and direction == TradeDirection.LONG:
            confluence += 1
            reasons.append("Bullish MSS confirmed")
        if smc_data.get('bear_mss', False) and direction == TradeDirection.SHORT:
            confluence += 1
            reasons.append("Bearish MSS confirmed")
        
        # ICT confluence
        if ict_data.get('in_killzone', False):
            confluence += 1
            reasons.append(f"In {ict_data.get('active_kz', 'killzone')} killzone")
        
        if ict_data.get('in_ote_zone', False):
            confluence += 1
            reasons.append(f"In OTE zone: {ict_data.get('ote_zone', 'unknown')}")
        
        # Sniper confluence
        if sniper_data.get('rsi_14', 50) < 30 and direction == TradeDirection.LONG:
            confluence += 1
            reasons.append("RSI oversold")
        if sniper_data.get('rsi_14', 50) > 70 and direction == TradeDirection.SHORT:
            confluence += 1
            reasons.append("RSI overbought")
        
        # Price Action
        if pa_data.get('bullish_engulfing', False) and direction == TradeDirection.LONG:
            confluence += 1
            reasons.append("Bullish engulfing pattern")
        if pa_data.get('bearish_engulfing', False) and direction == TradeDirection.SHORT:
            confluence += 1
            reasons.append("Bearish engulfing pattern")
        
        # Calculate entry and risk levels
        current_price = float(df['close'].iloc[-1])
        atr = float(sniper_data.get('atr', 0.5))
        atr = max(atr, 0.0001)  # Prevent zero ATR
        
        if direction == TradeDirection.LONG:
            entry_price = current_price
            stop_loss = current_price - (atr * 1.5)
            take_profit_1 = current_price + (atr * 2)
            take_profit_2 = current_price + (atr * 3)
            take_profit_3 = current_price + (atr * 4)
        else:
            entry_price = current_price
            stop_loss = current_price + (atr * 1.5)
            take_profit_1 = current_price - (atr * 2)
            take_profit_2 = current_price - (atr * 3)
            take_profit_3 = current_price - (atr * 4)
        
        # Risk calculation
        risk = abs(entry_price - stop_loss)
        rr1 = abs(take_profit_1 - entry_price) / risk if risk > 0 else 0
        rr2 = abs(take_profit_2 - entry_price) / risk if risk > 0 else 0
        rr3 = abs(take_profit_3 - entry_price) / risk if risk > 0 else 0
        
        # Confidence
        max_score = max(bull_total, bear_total, 1)
        confidence = min(95, max(30, (max_score / 15) * 100 + confluence * 5))
        
        # Create score breakdown
        breakdown = ScoreBreakdown(
            smc_buy_score=smc_scores['buy_score'],
            smc_sell_score=smc_scores['sell_score'],
            sniper_bull_pct=sniper_scores['bull_score'],
            sniper_bear_pct=sniper_scores['bear_score'],
            discount_zone=smc_data.get('in_discount', False),
            premium_zone=smc_data.get('in_premium', False),
            bull_fvg=smc_data.get('bull_fvg', False),
            bear_fvg=smc_data.get('bear_fvg', False),
            bull_ob=smc_data.get('bull_order_block', False),
            bear_ob=smc_data.get('bear_order_block', False),
            bull_mss=smc_data.get('bull_mss', False),
            bear_mss=smc_data.get('bear_mss', False),
            bull_pinbar=pa_data.get('bullish_pinbar', False),
            bear_pinbar=pa_data.get('bearish_pinbar', False),
            bull_engulfing=pa_data.get('bullish_engulfing', False),
            bear_engulfing=pa_data.get('bearish_engulfing', False),
            bull_displacement=pa_data.get('bullish_displacement', False),
            bear_displacement=pa_data.get('bearish_displacement', False),
            pattern_score=pa_score,
            in_killzone=ict_data.get('in_killzone', False),
            killzone_name=ict_data.get('active_kz'),
            in_ote_zone=ict_data.get('in_ote_zone', False),
            ote_level=ict_data.get('ote_618')
        )
        
        return TradingSignal(
            signal_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            signal_type=signal_type,
            current_price=current_price,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            take_profit_3=take_profit_3,
            risk_amount=risk,
            risk_reward_1=rr1,
            risk_reward_2=rr2,
            risk_reward_3=rr3,
            score_breakdown=breakdown,
            total_score=max(bull_total, bear_total),
            confluence_count=confluence,
            patterns=pa_data.get('patterns', []),
            signal_reasons=reasons[:5],
            confidence=confidence
        )


class MarketBiasAnalyzer:
    """Analyze market bias"""
    
    def analyze(self, smc_data: Dict, sniper_data: Dict) -> MarketBiasResult:
        """Determine market bias"""
        score = 0
        factors = []
        
        # SMC factors
        if smc_data.get('bull_structure', False):
            score += 1
            factors.append("Bull structure")
        if smc_data.get('bear_structure', False):
            score -= 1
            factors.append("Bear structure")
        if smc_data.get('bull_mss', False):
            score += 2
            factors.append("Bull MSS")
        if smc_data.get('bear_mss', False):
            score -= 2
            factors.append("Bear MSS")
        
        # Sniper factors
        price = sniper_data.get('price', 0)
        vwap = sniper_data.get('vwap', price)
        if price > vwap:
            score += 1
        elif price < vwap:
            score -= 1
        
        rsi = sniper_data.get('rsi_14', 50)
        if rsi < 30:
            score += 1
        elif rsi > 70:
            score -= 1
        
        # Determine direction and strength
        if score >= 3:
            direction = "bull"
            strength = "strong"
        elif score >= 1:
            direction = "bull"
            strength = "mild"
        elif score <= -3:
            direction = "bear"
            strength = "strong"
        elif score <= -1:
            direction = "bear"
            strength = "mild"
        else:
            direction = "neutral"
            strength = "weak"
        
        return MarketBiasResult(direction=direction, strength=strength, score=score)
