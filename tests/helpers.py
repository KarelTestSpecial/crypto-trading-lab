"""Shared test helpers."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from src.data.base import Bar


def make_bars(
    symbol: str, closes: list[float], start: date = date(2024, 1, 1)
) -> list[Bar]:
    """Build daily bars on consecutive calendar days (crypto trades 24/7)."""
    bars: list[Bar] = []
    day = start
    for close in closes:
        ts = datetime(day.year, day.month, day.day, tzinfo=UTC)
        bars.append(Bar(symbol, ts, close, close, close, close, 1_000_000.0))
        day += timedelta(days=1)
    return bars
