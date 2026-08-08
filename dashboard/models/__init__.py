from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd

@dataclass
class Candle:
    index: int
    time: pd.Timestamp
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)

    @property
    def range_size(self) -> float:
        return self.high - self.low

    @property
    def body_ratio(self) -> float:
        if self.range_size == 0:
            return 0.0
        return self.body_size / self.range_size

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low

    @property
    def upper_wick_ratio(self) -> float:
        if self.range_size == 0:
            return 0.0
        return self.upper_wick / self.range_size

    @property
    def lower_wick_ratio(self) -> float:
        if self.range_size == 0:
            return 0.0
        return self.lower_wick / self.range_size

    @property
    def mid(self) -> float:
        return (self.high + self.low) / 2.0

    @property
    def close_position(self) -> float:
        """Position of close within the range: 0.0 (low) -> 1.0 (high)."""
        if self.range_size == 0:
            return 0.5
        return (self.close - self.low) / self.range_size


def df_to_candles(df: pd.DataFrame) -> list[Candle]:
    candles: list[Candle] = []
    for i, row in df.iterrows():
        candles.append(
            Candle(
                index=i,
                time=pd.to_datetime(row["time"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row.get("tick_volume", row.get("real_volume", 0.0))),
            )
        )
    return candles


class Direction(Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class BoxType(Enum):
    ORDER_BLOCK = "OB"
    FVG = "FVG"
    BREAKER_BLOCK = "BREAKER"
    MITIGATION_BLOCK = "MITIGATION"
    REJECTION_BLOCK = "REJECTION"
    LIQUIDITY_VOID = "VOID"
    INVERSION_FVG = "iFVG"
    BPR = "BPR"
    VOLUME_IMBALANCE = "VOLUME_IMBALANCE"


@dataclass
class PDBox:
    type: BoxType
    direction: Direction
    top: float
    bottom: float
    start_index: int
    start_time: pd.Timestamp
    end_index: int | None = None
    mitigated: bool = False
    mitigated_at_index: int | None = None
    meta: dict = field(default_factory=dict)

    @property
    def mid(self) -> float:
        return (self.top + self.bottom) / 2.0

    def overlaps(self, other: PDBox) -> tuple[float, float] | None:
        """Returns the overlap range (top, bottom) if there is an overlap, else None."""
        max_bottom = max(self.bottom, other.bottom)
        min_top = min(self.top, other.top)
        if min_top > max_bottom:
            return min_top, max_bottom
        return None


class LevelType(Enum):
    BSL = "BSL"
    SSL = "SSL"
    EQH = "EQH"
    EQL = "EQL"
    SUPPORT = "SUPPORT"
    RESISTANCE = "RESISTANCE"


@dataclass
class PriceLevel:
    type: LevelType
    price: float
    formed_at_index: int
    formed_at_time: pd.Timestamp
    swept: bool = False
    swept_at_index: int | None = None
    label: str = ""
    touch_count: int = 1


@dataclass
class StructureEvent:
    type: str  # "BOS" | "CHOCH" | "MSS"
    direction: Direction
    index: int
    time: pd.Timestamp
    price: float
    broken_swing_index: int


@dataclass
class PatternMarker:
    type: str
    direction: Direction
    index: int
    time: pd.Timestamp
    price: float
    meta: dict = field(default_factory=dict)
