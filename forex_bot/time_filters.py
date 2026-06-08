from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo


class SessionFilter:
    def __init__(self, session_windows_utc: tuple[tuple[str, str], ...]) -> None:
        self._windows = tuple((_parse_time(start), _parse_time(end)) for start, end in session_windows_utc)

    def is_trading_time(self, now: datetime | None = None) -> bool:
        now_utc = (now or datetime.now(tz=ZoneInfo("UTC"))).astimezone(ZoneInfo("UTC"))
        if now_utc.weekday() >= 5:
            return False

        current = now_utc.time().replace(second=0, microsecond=0)
        return any(_inside_window(current, start, end) for start, end in self._windows)


def _parse_time(value: str) -> time:
    hour, minute = value.split(":", maxsplit=1)
    return time(hour=int(hour), minute=int(minute))


def _inside_window(current: time, start: time, end: time) -> bool:
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end
