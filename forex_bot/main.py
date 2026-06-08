from __future__ import annotations

import logging
import signal
import sys
import time
from dotenv import load_dotenv

from forex_bot.config import Settings
from forex_bot.logging_setup import configure_logging
from forex_bot.models import Bias
from forex_bot.mt5_client import MT5Client
from forex_bot.news_filter import NewsFilter
from forex_bot.risk import PositionSizer
from forex_bot.strategy import MarketSnapshot, SMCFibonacciStrategy
from forex_bot.time_filters import SessionFilter

LOGGER = logging.getLogger(__name__)
RUNNING = True


def _handle_shutdown(signum, frame) -> None:
    del frame
    global RUNNING
    RUNNING = False
    LOGGER.info("Shutdown signal received: %s", signum)


def main() -> int:
    load_dotenv()
    settings = Settings.from_env()
    configure_logging(settings.log_dir, settings.log_level)
    _validate_settings(settings)

    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    client = MT5Client(settings)
    strategy = SMCFibonacciStrategy(settings)
    sessions = SessionFilter(settings.session_windows_utc)
    news = NewsFilter(settings.news_url, settings.news_currencies, settings.news_pause_minutes)
    sizer = PositionSizer(client.mt5)

    if not client.connect():
        return 1

    try:
        client.select_symbols(settings.symbols)
        while RUNNING:
            try:
                _run_once(settings, client, strategy, sessions, news, sizer)
            except Exception:
                LOGGER.exception("Main loop iteration failed")
            time.sleep(settings.poll_seconds)
    finally:
        client.shutdown()

    return 0


def _run_once(
    settings: Settings,
    client: MT5Client,
    strategy: SMCFibonacciStrategy,
    sessions: SessionFilter,
    news: NewsFilter,
    sizer: PositionSizer,
) -> None:
    if not client.ensure_connected():
        LOGGER.error("Skipping cycle because MT5 reconnect failed")
        return

    client.log_recent_closed_deals()

    if not sessions.is_trading_time():
        LOGGER.info("Outside configured London/New York overlap window; skipping setup scan")
        return

    paused, event = news.should_pause()
    if paused and event is not None:
        LOGGER.info(
            "Trading paused for high-impact news: %s %s at %s UTC",
            event.country,
            event.title,
            event.date.isoformat(),
        )
        return

    balance = client.account_balance()
    for symbol in settings.symbols:
        symbol_cfg = settings.symbol_overrides[symbol]
        try:
            spread = client.spread_points(symbol)
            if spread > symbol_cfg.max_spread_points:
                LOGGER.info(
                    "%s skipped: spread %s points exceeds max %s",
                    symbol,
                    spread,
                    symbol_cfg.max_spread_points,
                )
                continue

            if client.has_open_position(symbol):
                LOGGER.info("%s skipped: bot already has an open position", symbol)
                continue

            tick = client.mt5.symbol_info_tick(symbol)
            info = client.mt5.symbol_info(symbol)
            if tick is None or info is None:
                LOGGER.warning("%s skipped: tick/symbol info unavailable", symbol)
                continue

            snapshot = MarketSnapshot(
                symbol=symbol,
                entry_df=client.rates(symbol, settings.timeframe_entry, settings.entry_bars),
                trend_df=client.rates(symbol, settings.timeframe_trend, settings.trend_bars),
                bid=float(tick.bid),
                ask=float(tick.ask),
                point=float(info.point),
            )
            setup = strategy.analyze(snapshot)
            if setup is None:
                continue

            direction = "buy" if setup.bias == Bias.BULLISH else "sell"
            live_entry = client.current_price(symbol, direction)
            risk_distance = abs(live_entry - setup.stop_loss)
            live_tp = (
                live_entry + risk_distance * settings.rr_ratio
                if direction == "buy"
                else live_entry - risk_distance * settings.rr_ratio
            )
            volume = sizer.calculate_lot_size(
                symbol=symbol,
                balance=balance,
                entry=live_entry,
                stop_loss=setup.stop_loss,
                risk_fraction=settings.risk_per_trade,
                direction=direction,
            )
            LOGGER.info(
                "Executing %s %s: entry=%.5f sl=%.5f tp=%.5f volume=%.2f reason=%s",
                direction,
                symbol,
                live_entry,
                setup.stop_loss,
                live_tp,
                volume,
                setup.reason,
            )
            result = client.place_market_order(
                symbol=symbol,
                direction=direction,
                volume=volume,
                sl=setup.stop_loss,
                tp=live_tp,
            )
            done_codes = {
                getattr(client.mt5, "TRADE_RETCODE_DONE", 10009),
                getattr(client.mt5, "TRADE_RETCODE_PLACED", 10008),
            }
            if result.retcode not in done_codes:
                LOGGER.error(
                    "Order rejected for %s: retcode=%s comment=%s",
                    symbol,
                    result.retcode,
                    result.comment,
                )
        except Exception:
            LOGGER.exception("Failed to process symbol %s", symbol)


def _validate_settings(settings: Settings) -> None:
    if not settings.symbols:
        raise ValueError("BOT_SYMBOLS cannot be empty")
    if not 0 < settings.risk_per_trade <= 0.05:
        raise ValueError("BOT_RISK_PER_TRADE must be between 0 and 0.05")
    if abs(settings.risk_per_trade - 0.01) > 1e-12:
        raise ValueError("Requirement is strict: BOT_RISK_PER_TRADE must be exactly 0.01")
    if settings.rr_ratio != 2.0:
        LOGGER.warning("Requirement says strict 1:2 RR; current BOT_RR_RATIO is %.2f", settings.rr_ratio)


if __name__ == "__main__":
    sys.exit(main())
