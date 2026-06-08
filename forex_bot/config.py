from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


def _split_csv(value: str) -> list[str]:
    return [item.strip().upper() for item in value.split(",") if item.strip()]


def _parse_session_windows(value: str) -> list[tuple[str, str]]:
    windows: list[tuple[str, str]] = []
    for raw_window in value.split(","):
        raw_window = raw_window.strip()
        if not raw_window:
            continue
        start, end = raw_window.split("-", maxsplit=1)
        windows.append((start.strip(), end.strip()))
    return windows


@dataclass(frozen=True)
class SymbolConfig:
    name: str
    max_spread_points: int
    atr_sl_buffer_multiplier: float
    fib_sl_buffer_points: int


@dataclass(frozen=True)
class Settings:
    mt5_login: int | None
    mt5_password: str | None
    mt5_server: str | None
    mt5_path: str | None
    symbols: tuple[str, ...]
    risk_per_trade: float
    magic: int
    deviation: int
    timeframe_entry: int
    timeframe_trend: int
    entry_bars: int
    trend_bars: int
    swing_lookback: int
    swing_window: int
    ema_fast: int
    ema_slow: int
    atr_period: int
    fib_golden_low: float
    fib_golden_high: float
    fib_sl_level: float
    rr_ratio: float
    min_zone_overlap: float
    poll_seconds: int
    timezone: str
    session_windows_utc: tuple[tuple[str, str], ...]
    news_url: str
    news_currencies: tuple[str, ...]
    news_pause_minutes: int
    log_dir: Path
    log_level: str
    symbol_overrides: dict[str, SymbolConfig] = field(default_factory=dict)

    @staticmethod
    def from_env() -> "Settings":
        try:
            import MetaTrader5 as mt5
        except ImportError:
            mt5 = None

        symbols = tuple(_split_csv(os.getenv("BOT_SYMBOLS", "EURUSD,GBPUSD,XAUUSD")))
        news_currencies = tuple(_split_csv(os.getenv("BOT_NEWS_CURRENCIES", "USD,EUR,GBP")))
        session_windows = tuple(
            _parse_session_windows(os.getenv("BOT_SESSION_WINDOWS_UTC", "12:00-16:00"))
        )

        return Settings(
            mt5_login=_optional_int(os.getenv("MT5_LOGIN")),
            mt5_password=os.getenv("MT5_PASSWORD") or None,
            mt5_server=os.getenv("MT5_SERVER") or None,
            mt5_path=os.getenv("MT5_PATH") or None,
            symbols=symbols,
            risk_per_trade=float(os.getenv("BOT_RISK_PER_TRADE", "0.01")),
            magic=int(os.getenv("BOT_MAGIC", "240515")),
            deviation=int(os.getenv("BOT_DEVIATION", "20")),
            timeframe_entry=_timeframe_value(os.getenv("BOT_TIMEFRAME_ENTRY", "M15"), mt5),
            timeframe_trend=_timeframe_value(os.getenv("BOT_TIMEFRAME_TREND", "H4"), mt5),
            entry_bars=int(os.getenv("BOT_ENTRY_BARS", "350")),
            trend_bars=int(os.getenv("BOT_TREND_BARS", "300")),
            swing_lookback=int(os.getenv("BOT_SWING_LOOKBACK", "150")),
            swing_window=int(os.getenv("BOT_SWING_WINDOW", "3")),
            ema_fast=int(os.getenv("BOT_EMA_FAST", "50")),
            ema_slow=int(os.getenv("BOT_EMA_SLOW", "200")),
            atr_period=int(os.getenv("BOT_ATR_PERIOD", "14")),
            fib_golden_low=float(os.getenv("BOT_FIB_GOLDEN_LOW", "0.5")),
            fib_golden_high=float(os.getenv("BOT_FIB_GOLDEN_HIGH", "0.618")),
            fib_sl_level=float(os.getenv("BOT_FIB_SL_LEVEL", "0.786")),
            rr_ratio=float(os.getenv("BOT_RR_RATIO", "2.0")),
            min_zone_overlap=float(os.getenv("BOT_MIN_ZONE_OVERLAP", "0.6")),
            poll_seconds=int(os.getenv("BOT_POLL_SECONDS", "60")),
            timezone=os.getenv("BOT_TIMEZONE", "UTC"),
            session_windows_utc=session_windows,
            news_url=os.getenv(
                "BOT_NEWS_URL",
                "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
            ),
            news_currencies=news_currencies,
            news_pause_minutes=int(os.getenv("BOT_NEWS_PAUSE_MINUTES", "30")),
            log_dir=Path(os.getenv("BOT_LOG_DIR", "logs")),
            log_level=os.getenv("BOT_LOG_LEVEL", "INFO").upper(),
            symbol_overrides=_symbol_overrides(symbols),
        )


def _optional_int(value: str | None) -> int | None:
    if value is None or value.strip() == "":
        return None
    return int(value)


def _timeframe_value(value: str, mt5) -> int:
    raw = value.strip().upper()
    if raw.isdigit():
        return int(raw)
    fallback = {
        "M1": 1,
        "M2": 2,
        "M3": 3,
        "M4": 4,
        "M5": 5,
        "M6": 6,
        "M10": 10,
        "M12": 12,
        "M15": 15,
        "M20": 20,
        "M30": 30,
        "H1": 16385,
        "H2": 16386,
        "H3": 16387,
        "H4": 16388,
        "H6": 16390,
        "H8": 16392,
        "H12": 16396,
        "D1": 16408,
    }
    attr = f"TIMEFRAME_{raw}"
    if mt5 is not None and hasattr(mt5, attr):
        return int(getattr(mt5, attr))
    if raw in fallback:
        return fallback[raw]
    raise ValueError(f"Unsupported timeframe: {value}")


def _symbol_overrides(symbols: Iterable[str]) -> dict[str, SymbolConfig]:
    overrides: dict[str, SymbolConfig] = {}
    for symbol in symbols:
        is_gold = symbol.upper().startswith("XAU")
        overrides[symbol.upper()] = SymbolConfig(
            name=symbol.upper(),
            max_spread_points=int(
                os.getenv(
                    f"BOT_{symbol.upper()}_MAX_SPREAD_POINTS",
                    "400" if is_gold else "30",
                )
            ),
            atr_sl_buffer_multiplier=float(
                os.getenv(
                    f"BOT_{symbol.upper()}_ATR_SL_BUFFER_MULTIPLIER",
                    "0.35" if is_gold else "0.10",
                )
            ),
            fib_sl_buffer_points=int(
                os.getenv(
                    f"BOT_{symbol.upper()}_FIB_SL_BUFFER_POINTS",
                    "150" if is_gold else "20",
                )
            ),
        )
    return overrides
