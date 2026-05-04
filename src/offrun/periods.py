"""Date and event-window helpers."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta

from .io import OffrunError


def parse_date(value: str) -> date:
    """Parse an ISO date string."""

    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise OffrunError(f"Expected ISO date YYYY-MM-DD, got {value!r}") from exc


def month_key(value: str | date) -> str:
    """Return a YYYY-MM month key."""

    parsed = parse_date(value) if isinstance(value, str) else value
    return f"{parsed.year:04d}-{parsed.month:02d}"


def is_business_day(value: date) -> bool:
    """Return True for Monday-Friday dates."""

    return value.weekday() < 5


def add_business_days(anchor: date, offset: int) -> date:
    """Move *offset* business days from *anchor*, skipping weekends."""

    if offset == 0:
        return anchor
    direction = 1 if offset > 0 else -1
    remaining = abs(offset)
    current = anchor
    while remaining:
        current += timedelta(days=direction)
        if is_business_day(current):
            remaining -= 1
    return current


def business_day_window(anchor: date, pre: int, post: int) -> Iterator[tuple[int, date]]:
    """Yield event-day offsets and business dates around *anchor*."""

    for event_day in range(-pre, post + 1):
        yield event_day, add_business_days(anchor, event_day)


def weekly_window(anchor: date, pre: int, post: int) -> Iterator[tuple[int, date]]:
    """Yield weekly offsets around *anchor*."""

    for event_week in range(-pre, post + 1):
        yield event_week, anchor + timedelta(weeks=event_week)
