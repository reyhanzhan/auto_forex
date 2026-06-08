from __future__ import annotations

import logging
import math

LOGGER = logging.getLogger(__name__)


class PositionSizer:
    def __init__(self, mt5_module) -> None:
        self._mt5 = mt5_module

    def calculate_lot_size(
        self,
        symbol: str,
        balance: float,
        entry: float,
        stop_loss: float,
        risk_fraction: float,
        direction: str,
    ) -> float:
        info = self._mt5.symbol_info(symbol)
        if info is None:
            raise ValueError(f"Symbol info unavailable for {symbol}")

        risk_amount = balance * risk_fraction
        loss_per_lot = self._loss_per_lot(symbol, entry, stop_loss, direction, info)
        if loss_per_lot <= 0:
            raise ValueError(f"Invalid loss per lot for {symbol}: {loss_per_lot}")

        raw_volume = risk_amount / loss_per_lot
        volume = self._normalize_volume(raw_volume, info.volume_min, info.volume_max, info.volume_step)
        actual_risk = volume * loss_per_lot

        if volume < info.volume_min:
            raise ValueError(
                f"Calculated volume {volume} is below minimum {info.volume_min} for {symbol}"
            )

        LOGGER.info(
            "Position size for %s: balance=%.2f risk=%.2f loss_per_lot=%.2f volume=%.2f actual_risk=%.2f",
            symbol,
            balance,
            risk_amount,
            loss_per_lot,
            volume,
            actual_risk,
        )
        return volume

    def _loss_per_lot(self, symbol: str, entry: float, stop_loss: float, direction: str, info) -> float:
        order_type = self._mt5.ORDER_TYPE_BUY if direction == "buy" else self._mt5.ORDER_TYPE_SELL
        calculated = self._mt5.order_calc_profit(order_type, symbol, 1.0, entry, stop_loss)
        if calculated is not None and calculated != 0:
            return abs(float(calculated))

        tick_size = float(getattr(info, "trade_tick_size", 0.0) or getattr(info, "point", 0.0))
        tick_value = float(
            getattr(info, "trade_tick_value_loss", 0.0)
            or getattr(info, "trade_tick_value", 0.0)
            or getattr(info, "trade_contract_size", 0.0) * tick_size
        )
        if tick_size <= 0 or tick_value <= 0:
            raise ValueError(f"Cannot calculate tick-based loss for {symbol}")
        return abs(entry - stop_loss) / tick_size * tick_value

    @staticmethod
    def _normalize_volume(raw_volume: float, volume_min: float, volume_max: float, volume_step: float) -> float:
        if volume_step <= 0:
            return max(volume_min, min(raw_volume, volume_max))
        steps = math.floor(raw_volume / volume_step)
        normalized = steps * volume_step
        decimals = max(0, int(round(-math.log10(volume_step)))) if volume_step < 1 else 0
        return round(max(volume_min, min(normalized, volume_max)), decimals)
