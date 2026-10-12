"""Data provider interface.

Fase 0 defines the contract only. Fase 1 adds the concrete providers:
Kraken (primary, MiCA-approved EU), Coinbase (fallback), CoinGecko/CoinPaprika
(metadata) and CSV (offline backtests). Binance public klines are used only for
deep backtest history (see PLAN §4).

Reliability rules (PLAN §4): one primary source + cross-check, log the exact
snapshot used for each decision, and use venue-adjusted candles.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime


class DataError(RuntimeError):
    """Raised when a data source cannot be reached or returns unusable data."""


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
