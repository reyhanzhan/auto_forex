from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class NewsEvent:
    title: str
    country: str
    impact: str
    date: datetime


class NewsFilter:
    def __init__(
        self,
        url: str,
        currencies: tuple[str, ...],
        pause_minutes: int,
        cache_ttl_minutes: int = 30,
    ) -> None:
        self._url = url
        self._currencies = set(currencies)
        self._pause_delta = timedelta(minutes=pause_minutes)
        self._cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self._events: list[NewsEvent] = []
        self._last_refresh: datetime | None = None

    def should_pause(self, now: datetime | None = None) -> tuple[bool, NewsEvent | None]:
        now_utc = (now or datetime.now(tz=ZoneInfo("UTC"))).astimezone(ZoneInfo("UTC"))
        self.refresh_if_needed(now_utc)
        for event in self._events:
            if event.date - self._pause_delta <= now_utc <= event.date + self._pause_delta:
                return True, event
        return False, None

    def refresh_if_needed(self, now_utc: datetime | None = None) -> None:
        now_utc = now_utc or datetime.now(tz=ZoneInfo("UTC"))
        if self._last_refresh and now_utc - self._last_refresh < self._cache_ttl:
            return
        self.refresh(now_utc)

    def refresh(self, now_utc: datetime | None = None) -> None:
        now_utc = now_utc or datetime.now(tz=ZoneInfo("UTC"))
        try:
            response = requests.get(self._url, timeout=15, headers={"User-Agent": "auto-forex-bot/0.1"})
            response.raise_for_status()
            payload = response.json()
        except Exception:
            LOGGER.exception("Failed to refresh economic calendar; keeping previous cache")
            self._last_refresh = now_utc
            return

        events: list[NewsEvent] = []
        for row in payload:
            country = str(row.get("country", "")).upper()
            impact = str(row.get("impact", ""))
            if country not in self._currencies or impact.lower() != "high":
                continue
            try:
                event_time = datetime.fromisoformat(str(row["date"])).astimezone(ZoneInfo("UTC"))
            except Exception:
                LOGGER.warning("Skipping news event with invalid date: %s", row)
                continue
            events.append(
                NewsEvent(
                    title=str(row.get("title", "Unknown")),
                    country=country,
                    impact=impact,
                    date=event_time,
                )
            )

        self._events = sorted(events, key=lambda event: event.date)
        self._last_refresh = now_utc
        LOGGER.info("Economic calendar refreshed: %d high-impact events cached", len(self._events))
