from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from forex_bot.config import Settings, SymbolConfig
from forex_bot.indicators import atr, ema, pivot_highs, pivot_lows
from forex_bot.models import Bias, Setup, Zone, ZoneKind

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    entry_df: pd.DataFrame
    trend_df: pd.DataFrame
    bid: float
    ask: float
    point: float


class SMCFibonacciStrategy:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def analyze(self, snapshot: MarketSnapshot) -> Setup | None:
        entry_df = snapshot.entry_df.copy()
        trend_df = snapshot.trend_df.copy()
        if len(entry_df) < self.settings.swing_lookback or len(trend_df) < self.settings.ema_slow + 5:
            LOGGER.info("%s skipped: insufficient bars", snapshot.symbol)
            return None

        bias = self._trend_bias(trend_df)
        if bias == Bias.NEUTRAL:
            LOGGER.info("%s skipped: neutral H4 EMA bias", snapshot.symbol)
            return None

        entry_df["atr"] = atr(entry_df, self.settings.atr_period)
        current_atr = float(entry_df["atr"].dropna().iloc[-1])

        swing = self._recent_swing(entry_df.tail(self.settings.swing_lookback), bias)
        if swing is None:
            LOGGER.info("%s skipped: no valid recent swing", snapshot.symbol)
            return None
        swing_low, swing_high = swing

        golden_low, golden_high = self._golden_zone(swing_low, swing_high, bias)
        zones = self._candidate_zones(entry_df, bias, current_atr)
        zone = self._best_aligned_zone(zones, golden_low, golden_high)
        if zone is None:
            LOGGER.info(
                "%s skipped: no OB/FVG overlap with golden zone %.5f-%.5f",
                snapshot.symbol,
                golden_low,
                golden_high,
            )
            return None

        direction = "buy" if bias == Bias.BULLISH else "sell"
        entry = snapshot.ask if direction == "buy" else snapshot.bid
        if not _price_inside(entry, golden_low, golden_high) or not _price_inside(entry, zone.low, zone.high):
            LOGGER.info(
                "%s setup tracked but not triggered: price=%.5f golden=%.5f-%.5f zone=%.5f-%.5f",
                snapshot.symbol,
                entry,
                golden_low,
                golden_high,
                zone.low,
                zone.high,
            )
            return None

        symbol_cfg = self.settings.symbol_overrides[snapshot.symbol]
        stop_loss = self._stop_loss(
            bias=bias,
            swing_low=swing_low,
            swing_high=swing_high,
            atr_value=current_atr,
            point=snapshot.point,
            symbol_cfg=symbol_cfg,
        )
        risk_distance = abs(entry - stop_loss)
        if risk_distance <= 0:
            LOGGER.warning("%s skipped: invalid risk distance", snapshot.symbol)
            return None

        take_profit = entry + risk_distance * self.settings.rr_ratio if direction == "buy" else entry - risk_distance * self.settings.rr_ratio

        return Setup(
            symbol=snapshot.symbol,
            bias=bias,
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            swing_low=swing_low,
            swing_high=swing_high,
            golden_low=golden_low,
            golden_high=golden_high,
            zone=zone,
            atr=current_atr,
            reason=(
                f"{bias.value} H4 EMA trend, {zone.kind.value} overlaps fib "
                f"golden zone with score {zone.score:.2f}"
            ),
        )

    def _trend_bias(self, df: pd.DataFrame) -> Bias:
        fast = ema(df["close"], self.settings.ema_fast)
        slow = ema(df["close"], self.settings.ema_slow)
        close = float(df["close"].iloc[-1])
        fast_last = float(fast.iloc[-1])
        slow_last = float(slow.iloc[-1])
        if close > fast_last > slow_last:
            return Bias.BULLISH
        if close < fast_last < slow_last:
            return Bias.BEARISH
        return Bias.NEUTRAL

    def _recent_swing(self, df: pd.DataFrame, bias: Bias) -> tuple[float, float] | None:
        highs = pivot_highs(df, self.settings.swing_window).dropna()
        lows = pivot_lows(df, self.settings.swing_window).dropna()
        if highs.empty or lows.empty:
            return None

        if bias == Bias.BULLISH:
            high_idx = highs.index[-1]
            prior_lows = lows[lows.index < high_idx]
            if prior_lows.empty:
                return None
            return float(prior_lows.iloc[-1]), float(highs.iloc[-1])

        low_idx = lows.index[-1]
        prior_highs = highs[highs.index < low_idx]
        if prior_highs.empty:
            return None
        return float(lows.iloc[-1]), float(prior_highs.iloc[-1])

    def _golden_zone(self, swing_low: float, swing_high: float, bias: Bias) -> tuple[float, float]:
        swing_range = swing_high - swing_low
        if bias == Bias.BULLISH:
            level_05 = swing_high - swing_range * self.settings.fib_golden_low
            level_0618 = swing_high - swing_range * self.settings.fib_golden_high
        else:
            level_05 = swing_low + swing_range * self.settings.fib_golden_low
            level_0618 = swing_low + swing_range * self.settings.fib_golden_high
        return min(level_05, level_0618), max(level_05, level_0618)

    def _candidate_zones(self, df: pd.DataFrame, bias: Bias, atr_value: float) -> list[Zone]:
        zones = self._order_blocks(df, bias, atr_value)
        zones.extend(self._fvgs(df, bias))
        return sorted(zones, key=lambda zone: zone.time, reverse=True)

    def _order_blocks(self, df: pd.DataFrame, bias: Bias, atr_value: float) -> list[Zone]:
        zones: list[Zone] = []
        lookback = df.tail(120).copy()
        for i in range(2, len(lookback) - 4):
            candle = lookback.iloc[i]
            next_close = float(lookback.iloc[i + 3]["close"])
            displacement = abs(next_close - float(candle["close"]))
            if displacement < atr_value * 1.2:
                continue
            if bias == Bias.BULLISH and candle["close"] < candle["open"] and next_close > candle["high"]:
                zones.append(
                    Zone(
                        kind=ZoneKind.ORDER_BLOCK,
                        low=float(candle["low"]),
                        high=float(candle["open"]),
                        time=candle["time"].to_pydatetime(),
                        score=0.0,
                    )
                )
            elif bias == Bias.BEARISH and candle["close"] > candle["open"] and next_close < candle["low"]:
                zones.append(
                    Zone(
                        kind=ZoneKind.ORDER_BLOCK,
                        low=float(candle["open"]),
                        high=float(candle["high"]),
                        time=candle["time"].to_pydatetime(),
                        score=0.0,
                    )
                )
        return zones

    def _fvgs(self, df: pd.DataFrame, bias: Bias) -> list[Zone]:
        zones: list[Zone] = []
        lookback = df.tail(120).copy()
        for i in range(0, len(lookback) - 2):
            first = lookback.iloc[i]
            third = lookback.iloc[i + 2]
            if bias == Bias.BULLISH and float(third["low"]) > float(first["high"]):
                zones.append(
                    Zone(
                        kind=ZoneKind.FAIR_VALUE_GAP,
                        low=float(first["high"]),
                        high=float(third["low"]),
                        time=third["time"].to_pydatetime(),
                        score=0.0,
                    )
                )
            elif bias == Bias.BEARISH and float(third["high"]) < float(first["low"]):
                zones.append(
                    Zone(
                        kind=ZoneKind.FAIR_VALUE_GAP,
                        low=float(third["high"]),
                        high=float(first["low"]),
                        time=third["time"].to_pydatetime(),
                        score=0.0,
                    )
                )
        return zones

    def _best_aligned_zone(self, zones: list[Zone], golden_low: float, golden_high: float) -> Zone | None:
        best: Zone | None = None
        best_score = 0.0
        for zone in zones:
            score = _overlap_score(zone.low, zone.high, golden_low, golden_high)
            if score >= self.settings.min_zone_overlap and score > best_score:
                best = Zone(zone.kind, zone.low, zone.high, zone.time, score)
                best_score = score
        return best

    def _stop_loss(
        self,
        bias: Bias,
        swing_low: float,
        swing_high: float,
        atr_value: float,
        point: float,
        symbol_cfg: SymbolConfig,
    ) -> float:
        swing_range = swing_high - swing_low
        buffer_value = max(
            symbol_cfg.fib_sl_buffer_points * point,
            atr_value * symbol_cfg.atr_sl_buffer_multiplier,
        )
        if bias == Bias.BULLISH:
            fib_0786 = swing_high - swing_range * self.settings.fib_sl_level
            return min(fib_0786, swing_low) - buffer_value
        fib_0786 = swing_low + swing_range * self.settings.fib_sl_level
        return max(fib_0786, swing_high) + buffer_value


def _price_inside(price: float, low: float, high: float) -> bool:
    return low <= price <= high


def _overlap_score(low_a: float, high_a: float, low_b: float, high_b: float) -> float:
    overlap = max(0.0, min(high_a, high_b) - max(low_a, low_b))
    zone_width = max(high_a - low_a, 1e-12)
    fib_width = max(high_b - low_b, 1e-12)
    return overlap / min(zone_width, fib_width)
