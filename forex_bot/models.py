from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Bias(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class ZoneKind(str, Enum):
    ORDER_BLOCK = "order_block"
    FAIR_VALUE_GAP = "fair_value_gap"


@dataclass(frozen=True)
class Zone:
    kind: ZoneKind
    low: float
    high: float
    time: datetime
    score: float


@dataclass(frozen=True)
class Setup:
    symbol: str
    bias: Bias
    entry: float
    stop_loss: float
    take_profit: float
    swing_low: float
    swing_high: float
    golden_low: float
    golden_high: float
    zone: Zone
    atr: float
    reason: str
