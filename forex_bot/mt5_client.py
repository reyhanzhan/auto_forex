from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from forex_bot.indicators import prepare_rates_frame

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class OrderResult:
    symbol: str
    ticket: int | None
    retcode: int
    comment: str
    volume: float
    price: float
    stop_loss: float
    take_profit: float


class MT5Client:
    def __init__(self, settings, mt5_module=None) -> None:
        if mt5_module is None:
            import MetaTrader5 as mt5_module

        self.mt5 = mt5_module
        self.settings = settings
        self._connected = False
        self._last_closed_deal_time: datetime | None = None

    def connect(self) -> bool:
        kwargs = {}
        if self.settings.mt5_path:
            kwargs["path"] = self.settings.mt5_path
        if self.settings.mt5_login is not None:
            kwargs["login"] = self.settings.mt5_login
        if self.settings.mt5_password:
            kwargs["password"] = self.settings.mt5_password
        if self.settings.mt5_server:
            kwargs["server"] = self.settings.mt5_server
        kwargs["timeout"] = self.settings.mt5_init_timeout_ms

        if self.mt5.initialize(**kwargs):
            self._connected = True
            account = self.mt5.account_info()
            LOGGER.info(
                "Connected to MT5 terminal. account=%s server=%s balance=%s",
                getattr(account, "login", None),
                getattr(account, "server", None),
                getattr(account, "balance", None),
            )
            return True

        LOGGER.error("MT5 initialize failed: %s", self.mt5.last_error())
        self._connected = False
        return False

    def shutdown(self) -> None:
        try:
            self.mt5.shutdown()
        finally:
            self._connected = False
            LOGGER.info("MT5 connection closed")

    def ensure_connected(self) -> bool:
        terminal = self.mt5.terminal_info()
        if self._connected and terminal is not None and getattr(terminal, "connected", False):
            return True
        LOGGER.warning("MT5 connection lost; attempting reconnect")
        self.shutdown()
        return self.connect()

    def select_symbols(self, symbols: tuple[str, ...]) -> None:
        for symbol in symbols:
            if not self.mt5.symbol_select(symbol, True):
                raise RuntimeError(f"Unable to select symbol {symbol}: {self.mt5.last_error()}")
            LOGGER.info("Symbol selected: %s", symbol)

    def rates(self, symbol: str, timeframe: int, count: int) -> pd.DataFrame:
        raw = self.mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        if raw is None:
            raise RuntimeError(f"copy_rates_from_pos failed for {symbol}: {self.mt5.last_error()}")
        return prepare_rates_frame(raw)

    def account_balance(self) -> float:
        account = self.mt5.account_info()
        if account is None:
            raise RuntimeError(f"Account info unavailable: {self.mt5.last_error()}")
        return float(account.balance)

    def current_price(self, symbol: str, direction: str) -> float:
        tick = self.mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"Tick unavailable for {symbol}: {self.mt5.last_error()}")
        return float(tick.ask if direction == "buy" else tick.bid)

    def spread_points(self, symbol: str) -> int:
        info = self.mt5.symbol_info(symbol)
        tick = self.mt5.symbol_info_tick(symbol)
        if info is None or tick is None:
            raise RuntimeError(f"Symbol/tick info unavailable for {symbol}")
        return int(round((float(tick.ask) - float(tick.bid)) / float(info.point)))

    def has_open_position(self, symbol: str) -> bool:
        positions = self.mt5.positions_get(symbol=symbol)
        if positions is None:
            LOGGER.warning("positions_get failed for %s: %s", symbol, self.mt5.last_error())
            return False
        return any(getattr(position, "magic", None) == self.settings.magic for position in positions)

    def place_market_order(self, symbol: str, direction: str, volume: float, sl: float, tp: float) -> OrderResult:
        tick = self.mt5.symbol_info_tick(symbol)
        info = self.mt5.symbol_info(symbol)
        if tick is None or info is None:
            raise RuntimeError(f"Cannot place order; tick/info unavailable for {symbol}")

        order_type = self.mt5.ORDER_TYPE_BUY if direction == "buy" else self.mt5.ORDER_TYPE_SELL
        price = float(tick.ask if direction == "buy" else tick.bid)
        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": _round_price(price, info.digits),
            "sl": _round_price(sl, info.digits),
            "tp": _round_price(tp, info.digits),
            "deviation": self.settings.deviation,
            "magic": self.settings.magic,
            "comment": "SMC_FIB_AUTO",
            "type_time": self.mt5.ORDER_TIME_GTC,
        }
        result = None
        for filling_mode in _candidate_filling_modes(self.mt5):
            request["type_filling"] = filling_mode
            result = self.mt5.order_send(request)
            if result is None:
                continue
            invalid_fill = getattr(self.mt5, "TRADE_RETCODE_INVALID_FILL", 10030)
            if result.retcode != invalid_fill:
                break
        if result is None:
            raise RuntimeError(f"order_send returned None for {symbol}: {self.mt5.last_error()}")

        LOGGER.info(
            "Order result for %s: retcode=%s ticket=%s comment=%s volume=%.2f price=%.5f sl=%.5f tp=%.5f",
            symbol,
            result.retcode,
            getattr(result, "order", None),
            result.comment,
            volume,
            price,
            sl,
            tp,
        )
        return OrderResult(
            symbol=symbol,
            ticket=getattr(result, "order", None),
            retcode=int(result.retcode),
            comment=str(result.comment),
            volume=volume,
            price=price,
            stop_loss=sl,
            take_profit=tp,
        )

    def log_recent_closed_deals(self) -> None:
        now = datetime.now(tz=ZoneInfo("UTC"))
        start = self._last_closed_deal_time or now.replace(hour=0, minute=0, second=0, microsecond=0)
        deals = self.mt5.history_deals_get(start, now)
        if deals is None:
            LOGGER.debug("history_deals_get returned no data: %s", self.mt5.last_error())
            return
        for deal in deals:
            if getattr(deal, "magic", None) != self.settings.magic:
                continue
            entry_out = getattr(self.mt5, "DEAL_ENTRY_OUT", 1)
            if getattr(deal, "entry", None) != entry_out:
                continue
            reason = _deal_reason_name(self.mt5, getattr(deal, "reason", None))
            LOGGER.info(
                "Closed deal: symbol=%s ticket=%s reason=%s profit=%.2f price=%.5f",
                getattr(deal, "symbol", None),
                getattr(deal, "ticket", None),
                reason,
                float(getattr(deal, "profit", 0.0)),
                float(getattr(deal, "price", 0.0)),
            )
        self._last_closed_deal_time = now


def _round_price(price: float, digits: int) -> float:
    return round(float(price), int(digits))


def _candidate_filling_modes(mt5) -> list[int]:
    modes = [
        getattr(mt5, "ORDER_FILLING_IOC", None),
        getattr(mt5, "ORDER_FILLING_FOK", None),
        getattr(mt5, "ORDER_FILLING_RETURN", None),
    ]
    return [int(mode) for mode in modes if mode is not None]


def _deal_reason_name(mt5, reason: int | None) -> str:
    names = {
        getattr(mt5, "DEAL_REASON_SL", object()): "stop_loss",
        getattr(mt5, "DEAL_REASON_TP", object()): "take_profit",
        getattr(mt5, "DEAL_REASON_CLIENT", object()): "client",
        getattr(mt5, "DEAL_REASON_EXPERT", object()): "expert",
    }
    return names.get(reason, str(reason))
