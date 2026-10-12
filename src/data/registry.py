"""Data-provider registry and fallback chain.

PLAN §4: one primary source plus a fallback. `FallbackDataProvider` tries each
provider in order and only accepts a non-empty result, recording which provider
answered so the snapshot's provenance is always known.

Reading crypto market data needs **no credentials**: Kraken and Coinbase expose
public OHLC/candle endpoints.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from src.config import Settings
from src.data.base import Bar, DataError, DataProvider
from src.data.coinbase import CoinbaseDataProvider
from src.data.csv_provider import CsvDataProvider
from src.data.kraken import KrakenDataProvider


class FallbackDataProvider(DataProvider):
    def __init__(self, providers: list[DataProvider]) -> None:
        if not providers:
            raise ValueError("at least one provider is required")
        self.providers = providers
        self.last_source: str | None = None

    def bars(self, symbol: str, start: date, end: date, timeframe: str = "1d") -> list[Bar]:
        problems: list[str] = []
        for provider in self.providers:
            try:
                bars = provider.bars(symbol, start, end, timeframe)
            except DataError as exc:
                problems.append(f"{type(provider).__name__}: {exc}")
                continue
            if bars:
                self.last_source = type(provider).__name__
                return bars
            problems.append(f"{type(provider).__name__}: empty result")
        raise DataError(f"all providers failed for {symbol!r}: {'; '.join(problems)}")


def build_data_provider(
    settings: Settings,
    *,
    name: str = "auto",
    csv_dir: str | Path | None = None,
) -> DataProvider:
    """Construct a data provider.

    name: "auto" (Kraken then Coinbase, both keyless), "kraken", "coinbase", "csv".
    """
    if name == "csv":
        if csv_dir is None:
            raise DataError("csv provider requires a directory")
        return CsvDataProvider(csv_dir)
    if name == "kraken":
        return KrakenDataProvider()
    if name == "coinbase":
        return CoinbaseDataProvider()

    return FallbackDataProvider([KrakenDataProvider(), CoinbaseDataProvider()])
