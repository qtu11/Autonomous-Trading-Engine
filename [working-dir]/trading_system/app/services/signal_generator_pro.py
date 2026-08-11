"""
Signal Generator PRO - Optimized for High R:R Trading
Target: 20$ → 2000$ in 1 month (100x)
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class EntryCriteria:
    """Entry criteria for high-probability trades"""
    min_confluence_score: int = 7  # Minimum 7/13 confluence
    require_htf_bias: bool = True
    require_displacement: bool = True
    require_momentum_confirmation: bool = True
    max_entry_distance_pct: float = 0.5  # Max 0.5% from key level


@dataclass
class RiskManagement:
    """Risk management parameters"""
    stop_loss_atr_multiplier: float = 1.0  # Tighter SL: 1 ATR instead of 1.5
    tp1_risk_multiplier: float = 1.5  # TP1: 1.5R
    tp2_risk_multiplier: float = 2.5  # TP2: 2.5R
    tp3_risk_multiplier: float = 4.0  # TP3: 4R
    partial_tp1_pct: float = 0.30  # Close 30% at TP1
    partial_tp2_pct: float = 0.30  # Close 30% at TP2
    trailing_start_r: float = 2.0  # Start trailing at 2R
    trailing_distance_r: float = 1.0  # Trail by 1R


@dataclass
class TradeSetup:
    """Trade setup with entry/exit levels"""
    signal_id: str
    timestamp: datetime
    symbol: str
    direction: str  # 'long' or 'short'
    
    # Entry levels
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    
    # Risk metrics
    risk_amount: float
    risk_reward_1: float
    risk_reward_2: float
    risk_reward_3: float
    
    # Quality metrics
    confluence_score: int
    signal_strength: str
    entry_reasons: List[str] = field(default_factory=list)
    confidence: float = 0.0
    
    # Optimal entry zone
    optimal_entry_zone: str = ""
    key_level: float = 0.0
    distance_from_level_pct: float = 0.0


class SignalGeneratorPro:
    """
    Signal Generator PRO
    Optimized for high R:R trading (target 1:3 to 1:5)
    
    Key improvements over basic version:
    1. Tighter stop loss (1 ATR vs 1.5 ATR)
    2. Higher R:R targets (1:1.5, 1:2.5, 1:4)
    3. Better entry timing with key level retests
    4. Confluence scoring (7+ required)
    5. Partial TP management
    6. Trailing stop for locked profits
    """

    def __init__(
        self,
        entry_criteria: EntryCriteria = None,
        risk_mgmt: RiskManagement = None
    ):
        self.entry_criteria = entry_criteria or EntryCriteria()
        self.risk_mgmt = risk_mgmt or RiskManagement()

    def generate_signal(
        self,
        df: pd.DataFrame,
        smc_data: Dict,
        ict_data: Dict,
        sniper_data: Dict,
        pa_data: Dict,
        symbol: str = "BTCUSDT",
        timeframe: str = "1h"
    ) -> Optional[TradeSetup]:
        """
        Generate high-probability trading signal
        """

        # Calculate confluence
        confluence = self._calculate_confluence(smc_data, ict_data, sniper_data, pa_data)
        
        # Check entry criteria
        if not self._check_entry_criteria(confluence, smc_data, sniper_data):
            return None

        # Determine direction
        direction = 'long' if confluence['bull_score'] > confluence['bear_score'] else 'short'
        
        # Calculate entry, SL, TP levels
        levels = self._calculate_levels(df, sniper_data, direction, smc_data)
        
        if levels is None:
            return None

        # Generate entry reasons
        reasons = self._generate_entry_reasons(confluence, smc_data, ict_data, sniper_data)
        
        # Calculate confidence
        confidence = self._calculate_confidence(confluence, smc_data, sniper_data)

        return TradeSetup(
            signal_id=f"{symbol}_{timeframe}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            timestamp=datetime.now(),
            symbol=symbol,
            direction=direction,
            entry_price=levels['entry'],
            stop_loss=levels['sl'],
            take_profit_1=levels['tp1'],
            take_profit_2=levels['tp2'],
            take_profit_3=levels['tp3'],
            risk_amount=levels['risk'],
            risk_reward_1=self.risk_mgmt.tp1_risk_multiplier,
            risk_reward_2=self.risk_mgmt.tp2_risk_multiplier,
            risk_reward_3=self.risk_mgmt.tp3_risk_multiplier,
            confluence_score=confluence['total'],
            signal_strength=confluence['strength'],
            entry_reasons=reasons,
            confidence=confidence,
            optimal_entry_zone=confluence.get('entry_zone', 'mid_range'),
            key_level=levels.get('key_level', 0),
            distance_from_level_pct=levels.get('distance_pct', 0)
        )

    def _calculate_confluence(
        self,
        smc_data: Dict,
        ict_data: Dict,
        sniper_data: Dict,
        pa_data: Dict
    ) -> Dict:
        """
        Calculate total confluence score (0-20+)
        Combines SMC, ICT, Sniper, and Price Action signals
        """
        bull_score = 0
        bear_score = 0
        factors = {'bull': [], 'bear': []}

        # ===== HTF BIAS (Most Important) =====
        if smc_data.get('htf_bullish'):
            bull_score += 2
            factors['bull'].append('HTF Bullish')
        if smc_data.get('htf_bearish'):
            bear_score += 2
            factors['bear'].append('HTF Bearish')

        # ===== PREMIUM/DISCOUNT (Important) =====
        if smc_data.get('in_discount'):
            bull_score += 2
            factors['bull'].append('Discount Zone')
        if smc_data.get('in_premium'):
            bear_score += 2
            factors['bear'].append('Premium Zone')

        # ===== MSS/CHoCH (Critical) =====
        if smc_data.get('bull_mss'):
            bull_score += 3
            factors['bull'].append('Bullish MSS')
        if smc_data.get('bear_mss'):
            bear_score += 3
            factors['bear'].append('Bearish MSS')
            
        if smc_data.get('bull_choch'):
            bull_score += 2
            factors['bull'].append('Bullish CHoCH')
        if smc_data.get('bear_choch'):
            bear_score += 2
            factors['bear'].append('Bearish CHoCH')

        # ===== LIQUIDITY SWEEP =====
        if smc_data.get('bull_sweep'):
            bull_score += 2
            factors['bull'].append('SSL Sweep')
        if smc_data.get('bear_sweep'):
            bear_score += 2
            factors['bear'].append('BSL Sweep')

        # ===== BOS =====
        if smc_data.get('bull_bos'):
            bull_score += 2
            factors['bull'].append('Bullish BOS')
        if smc_data.get('bear_bos'):
            bear_score += 2
            factors['bear'].append('Bearish BOS')

        # ===== DISPLACEMENT (Critical for momentum) =====
        if smc_data.get('bullish_displacement'):
            bull_score += 2
            factors['bull'].append('Bull DPL')
        if smc_data.get('bearish_displacement'):
            bear_score += 2
            factors['bear'].append('Bear DPL')

        # ===== ORDER BLOCKS =====
        if smc_data.get('bull_ob'):
            bull_score += 1
            factors['bull'].append('Bull OB')
        if smc_data.get('bear_ob'):
            bear_score += 1
            factors['bear'].append('Bear OB')

        # ===== FVG =====
        if smc_data.get('bull_fvg'):
            bull_score += 1
            factors['bull'].append('Bull FVG')
        if smc_data.get('bear_fvg'):
            bear_score += 1
            factors['bear'].append('Bear FVG')

        # ===== SNIPER INDICATORS =====
        rsi = sniper_data.get('rsi_14', 50)
        if rsi < 30 and bull_score > bear_score:
            bull_score += 2
            factors['bull'].append('RSI Oversold')
        if rsi > 70 and bear_score > bull_score:
            bear_score += 2
            factors['bear'].append('RSI Overbought')

        # MACD confirmation
        if sniper_data.get('macd_bullish') and bull_score > bear_score:
            bull_score += 1
            factors['bull'].append('MACD Bull')
        if sniper_data.get('macd_bearish') and bear_score > bull_score:
            bear_score += 1
            factors['bear'].append('MACD Bear')

        # VWAP confirmation
        if sniper_data.get('price_above_vwap') and bull_score > bear_score:
            bull_score += 1
            factors['bull'].append('Above VWAP')
        if sniper_data.get('price_below_vwap') and bear_score > bull_score:
            bear_score += 1
            factors['bear'].append('Below VWAP')

        # ===== KILLZONE =====
        if ict_data.get('in_killzone'):
            if bull_score > bear_score:
                bull_score += 1
                factors['bull'].append(f"Killzone ({ict_data.get('active_kz')})")
            else:
                bear_score += 1
                factors['bear'].append(f"Killzone ({ict_data.get('active_kz')})")

        # ===== OTE ZONE =====
        if ict_data.get('in_ote_zone') and bull_score > bear_score:
            bull_score += 1
            factors['bull'].append('OTE Zone')
        if ict_data.get('in_ote_zone') and bear_score > bull_score:
            bear_score += 1
            factors['bear'].append('OTE Zone')

        # ===== PRICE ACTION =====
        if pa_data.get('bullish_engulfing'):
            bull_score += 2
            factors['bull'].append('Bull Engulfing')
        if pa_data.get('bearish_engulfing'):
            bear_score += 2
            factors['bear'].append('Bear Engulfing')

        if pa_data.get('bullish_pinbar'):
            bull_score += 1
            factors['bull'].append('Bull Pinbar')
        if pa_data.get('bearish_pinbar'):
            bear_score += 1
            factors['bear'].append('Bear Pinbar')

        total = bull_score + bear_score

        # Determine strength
        if total >= 12:
            strength = 'STRONG'
        elif total >= 8:
            strength = 'VALID'
        elif total >= 5:
            strength = 'WEAK'
        else:
            strength = 'NO_TRADE'

        # Entry zone
        entry_zone = 'unknown'
        if smc_data.get('in_discount') and bull_score > bear_score:
            entry_zone = 'discount_retrace'
        elif smc_data.get('in_premium') and bear_score > bull_score:
            entry_zone = 'premium_retrace'

        return {
            'bull_score': bull_score,
            'bear_score': bear_score,
            'total': total,
            'strength': strength,
            'factors': factors,
            'entry_zone': entry_zone
        }

    def _check_entry_criteria(
        self,
        confluence: Dict,
        smc_data: Dict,
        sniper_data: Dict
    ) -> bool:
        """Check if entry criteria are met"""

        # Minimum confluence
        if confluence['total'] < self.entry_criteria.min_confluence_score:
            return False

        # Require HTF bias
        if self.entry_criteria.require_htf_bias:
            if not smc_data.get('htf_bullish') and not smc_data.get('htf_bearish'):
                # Allow if confluence is very strong
                if confluence['total'] < 10:
                    return False

        # Require displacement
        if self.entry_criteria.require_displacement:
            direction = 'bull' if confluence['bull_score'] > confluence['bear_score'] else 'bear'
            if direction == 'bull' and not smc_data.get('bullish_displacement'):
                if confluence['total'] < 10:
                    return False
            if direction == 'bear' and not smc_data.get('bearish_displacement'):
                if confluence['total'] < 10:
                    return False

        # Momentum confirmation
        if self.entry_criteria.require_momentum_confirmation:
            if confluence['bull_score'] > confluence['bear_score']:
                # Bullish: RSI should not be overbought, MACD should be bullish
                if sniper_data.get('rsi_14', 50) > 80:
                    return False
            else:
                # Bearish: RSI should not be oversold, MACD should be bearish
                if sniper_data.get('rsi_14', 50) < 20:
                    return False

        return True

    def _calculate_levels(
        self,
        df: pd.DataFrame,
        sniper_data: Dict,
        direction: str,
        smc_data: Dict
    ) -> Optional[Dict]:
        """Calculate entry, stop loss, and take profit levels"""

        current_price = float(df['close'].iloc[-1])
        atr = float(sniper_data.get('atr', current_price * 0.01))
        atr = max(atr, current_price * 0.001)  # Min 0.1%

        # Optimal entry is at key level retest
        key_level = self._find_key_level(df, smc_data, direction)
        
        # Entry price
        if key_level > 0:
            entry = key_level
        else:
            entry = current_price

        # Stop loss (1 ATR for tighter risk)
        if direction == 'long':
            sl = entry - (atr * self.risk_mgmt.stop_loss_atr_multiplier)
        else:
            sl = entry + (atr * self.risk_mgmt.stop_loss_atr_multiplier)

        # Take profits
        if direction == 'long':
            tp1 = entry + (atr * self.risk_mgmt.tp1_risk_multiplier)
            tp2 = entry + (atr * self.risk_mgmt.tp2_risk_multiplier)
            tp3 = entry + (atr * self.risk_mgmt.tp3_risk_multiplier)
        else:
            tp1 = entry - (atr * self.risk_mgmt.tp1_risk_multiplier)
            tp2 = entry - (atr * self.risk_mgmt.tp2_risk_multiplier)
            tp3 = entry - (atr * self.risk_mgmt.tp3_risk_multiplier)

        risk = abs(entry - sl)
        
        # Distance from key level
        distance_pct = 0
        if key_level > 0:
            distance_pct = abs(entry - key_level) / key_level * 100

        return {
            'entry': entry,
            'sl': sl,
            'tp1': tp1,
            'tp2': tp2,
            'tp3': tp3,
            'risk': risk,
            'key_level': key_level,
            'distance_pct': distance_pct
        }

    def _find_key_level(
        self,
        df: pd.DataFrame,
        smc_data: Dict,
        direction: str
    ) -> float:
        """
        Find optimal key level for entry
        Priority: FVG > OB > Equilibrium Retest > Current Price
        """
        last = df.iloc[-1]
        current = float(last['close'])

        # Check for FVG retest
        if direction == 'long' and smc_data.get('bull_fvg'):
            # Bullish FVG: entry at bottom of FVG
            fvg_bottom = float(last.get('low', current))
            return fvg_bottom if fvg_bottom > 0 else current

        if direction == 'short' and smc_data.get('bear_fvg'):
            # Bearish FVG: entry at top of FVG
            fvg_top = float(last.get('high', current))
            return fvg_top if fvg_top > 0 else current

        # Check for Order Block retest
        if direction == 'long' and smc_data.get('bull_ob'):
            ob_bottom = float(smc_data.get('swing_low', current))
            return ob_bottom if ob_bottom > 0 else current

        if direction == 'short' and smc_data.get('bear_ob'):
            ob_top = float(smc_data.get('swing_high', current))
            return ob_top if ob_top > 0 else current

        # Equilibrium retest
        eq = float(smc_data.get('equilibrium', 0))
        if eq > 0:
            # In discount, look for EQ buy
            if direction == 'long' and current < eq:
                return eq
            # In premium, look for EQ sell
            if direction == 'short' and current > eq:
                return eq

        return current

    def _generate_entry_reasons(
        self,
        confluence: Dict,
        smc_data: Dict,
        ict_data: Dict,
        sniper_data: Dict
    ) -> List[str]:
        """Generate list of entry reasons"""
        reasons = []

        # Top factors
        factors = confluence['factors']
        if confluence['bull_score'] > confluence['bear_score']:
            reasons.extend(factors['bull'][:5])  # Top 5 bull factors
        else:
            reasons.extend(factors['bear'][:5])  # Top 5 bear factors

        return reasons[:5]  # Max 5 reasons

    def _calculate_confidence(
        self,
        confluence: Dict,
        smc_data: Dict,
        sniper_data: Dict
    ) -> float:
        """Calculate trade confidence percentage"""

        # Base confidence from confluence
        base = min(90, confluence['total'] * 5)

        # Adjustments
        if smc_data.get('htf_bullish') or smc_data.get('htf_bearish'):
            base += 5

        if smc_data.get('bull_mss') or smc_data.get('bear_mss'):
            base += 5

        # RSI zone adjustment
        rsi = sniper_data.get('rsi_14', 50)
        if (rsi < 35 or rsi > 65) and confluence['total'] > 8:
            base += 3

        return min(95, max(40, base))


class PositionManager:
    """
    Position Manager for Trade Execution
    Handles partial TP, trailing stop, and risk management
    """

    def __init__(self, risk_mgmt: RiskManagement = None):
        self.risk_mgmt = risk_mgmt or RiskManagement()
        self.positions: Dict[str, Dict] = {}

    def open_position(self, setup: TradeSetup) -> Dict:
        """Open a new position"""
        position = {
            'setup': setup,
            'entry_price': setup.entry_price,
            'stop_loss': setup.stop_loss,
            'tp1': setup.take_profit_1,
            'tp2': setup.take_profit_2,
            'tp3': setup.take_profit_3,
            'partial_tp1_hit': False,
            'partial_tp2_hit': False,
            'trailing_activated': False,
            'highest_price': setup.entry_price if setup.direction == 'long' else 0,
            'lowest_price': setup.entry_price if setup.direction == 'short' else float('inf'),
            'r_achieved': 0,
            'status': 'open'
        }

        self.positions[setup.signal_id] = position
        return position

    def update_position(self, signal_id: str, current_price: float) -> Dict:
        """Update position status"""
        if signal_id not in self.positions:
            return {}

        pos = self.positions[signal_id]
        setup = pos['setup']

        if pos['status'] != 'open':
            return pos

        entry = pos['entry_price']
        sl = pos['stop_loss']
        risk = abs(entry - sl)

        if setup.direction == 'long':
            # Update highest price
            pos['highest_price'] = max(pos['highest_price'], current_price)
            
            # Calculate R achieved
            if risk > 0:
                pos['r_achieved'] = (current_price - entry) / risk

            # Check SL
            if current_price <= sl:
                pos['status'] = 'sl_hit'
                return pos

            # Check TP1 (partial)
            if not pos['partial_tp1_hit'] and current_price >= pos['tp1']:
                pos['partial_tp1_hit'] = True

            # Check TP2 (partial)
            if not pos['partial_tp2_hit'] and current_price >= pos['tp2']:
                pos['partial_tp2_hit'] = True

            # Check TP3 (full close)
            if current_price >= pos['tp3']:
                pos['status'] = 'tp3_hit'

            # Trailing stop
            if pos['r_achieved'] >= self.risk_mgmt.trailing_start_r:
                pos['trailing_activated'] = True
                new_sl = pos['highest_price'] - (risk * self.risk_mgmt.trailing_distance_r)
                pos['stop_loss'] = max(pos['stop_loss'], new_sl)

        else:  # Short
            # Update lowest price
            pos['lowest_price'] = min(pos['lowest_price'], current_price)
            
            if risk > 0:
                pos['r_achieved'] = (entry - current_price) / risk

            # Check SL
            if current_price >= sl:
                pos['status'] = 'sl_hit'
                return pos

            # Check TPs
            if not pos['partial_tp1_hit'] and current_price <= pos['tp1']:
                pos['partial_tp1_hit'] = True

            if not pos['partial_tp2_hit'] and current_price <= pos['tp2']:
                pos['partial_tp2_hit'] = True

            if current_price <= pos['tp3']:
                pos['status'] = 'tp3_hit'

            # Trailing stop
            if pos['r_achieved'] >= self.risk_mgmt.trailing_start_r:
                pos['trailing_activated'] = True
                new_sl = pos['lowest_price'] + (risk * self.risk_mgmt.trailing_distance_r)
                pos['stop_loss'] = min(pos['stop_loss'], new_sl)

        return pos

    def close_position(self, signal_id: str, reason: str = 'manual') -> Dict:
        """Close a position"""
        if signal_id not in self.positions:
            return {}

        pos = self.positions[signal_id]
        pos['status'] = f'closed_{reason}'
        return pos
