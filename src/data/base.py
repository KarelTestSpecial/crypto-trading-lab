"""Crypto market-data primitives.

`DataError` is owned by cadence-core (single source of truth for the data-layer
error type) and re-exported here so the venue providers import one local module.
The OHLCV `Bar` and the `DataProvider` contract are venue-specific and live here —
cadence-core is asset-agnostic on purpose and defines no bar type.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime

from cadence_core.data.base import DataError

__all__ = ["Bar", "DataError", "DataProvider"]


@dataclass(frozen=True)
class Bar:
    symbol: str
    ts: datetime  # UTC open time of the bar
    open: float
    high: float
    low: float
    close: float
    volume: float


class DataProvider(ABC):
    """Contract for market-data sources."""

    @abstractmethod
    def bars(
        self, symbol: str, start: date, end: date, timeframe: str = "1d"
    ) -> list[Bar]:
        """Return OHLCV bars for a symbol over [start, end] at `timeframe`."""
