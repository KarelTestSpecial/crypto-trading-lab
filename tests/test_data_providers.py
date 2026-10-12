"""Data-provider tests (offline: parsing + fallback, no network)."""

from __future__ import annotations

from datetime import date

import pytest

from src.data.base import DataError
from src.data.coinbase import coinbase_product, parse_coinbase_candles
from src.data.csv_provider import CsvDataProvider, sanitize_symbol
from src.data.kraken import kraken_pair, parse_kraken_ohlc
from src.data.registry import FallbackDataProvider
from tests.helpers import make_bars

START = date(2024, 1, 1)
END = date(2024, 12, 31)


def test_symbol_mapping():
    assert sanitize_symbol("BTC/USDT") == "BTC-USDT"
    assert kraken_pair("BTC/USDT") == "XBTUSDT"
    assert kraken_pair("ETH/USDT") == "ETHUSDT"
    assert coinbase_product("BTC/USDT") == "BTC-USDT"


def test_csv_provider_reads_and_filters(tmp_path):
    (tmp_path / "BTC-USDT.csv").write_text(
        "ts,open,high,low,close,volume\n"
        "2024-01-02T00:00:00+00:00,100,105,99,104,1000000\n"
        "2024-01-03T00:00:00+00:00,104,108,103,107,1200000\n"
        "2025-06-01T00:00:00+00:00,1,1,1,1,1\n"
    )
    bars = CsvDataProvider(tmp_path).bars("BTC/USDT", START, END)
    assert [b.ts.date().isoformat() for b in bars] == ["2024-01-02", "2024-01-03"]
    assert bars[0].close == 104.0
    assert bars[0].symbol == "BTC/USDT"


def test_csv_provider_missing_file(tmp_path):
    with pytest.raises(DataError):
        CsvDataProvider(tmp_path).bars("ETH/USDT", START, END)


def test_csv_provider_missing_column(tmp_path):
    (tmp_path / "BTC-USDT.csv").write_text("ts,close\n2024-01-02T00:00:00+00:00,104\n")
    with pytest.raises(DataError):
        CsvDataProvider(tmp_path).bars("BTC/USDT", START, END)


def test_parse_kraken_ohlc_drops_uncommitted_last_candle():
    payload = {
        "error": [],
        "result": {
            "XBTUSDT": [
                [1704153600, "100", "105", "99", "104", "101", "1000000", "50"],
                [1704240000, "104", "108", "103", "107", "105", "1200000", "60"],
            ],
            "last": 1704240000,
        },
    }
    bars = parse_kraken_ohlc(payload, "BTC/USDT", START, END)
    assert len(bars) == 1
    assert bars[0].close == 104.0
    assert bars[0].ts.date().isoformat() == "2024-01-02"


def test_parse_kraken_rejects_error():
    with pytest.raises(DataError):
        parse_kraken_ohlc({"error": ["EQuery:Unknown asset pair"]}, "BTC/USDT", START, END)


def test_parse_coinbase_candles():
    rows = [[1704153600, 99, 105, 100, 104, 1000000]]
    bars = parse_coinbase_candles(rows, "BTC/USDT", START, END)
    assert len(bars) == 1
    assert bars[0].open == 100.0
    assert bars[0].high == 105.0
    assert bars[0].low == 99.0
    assert bars[0].close == 104.0


class _FailingProvider:
    def bars(self, symbol, start, end, timeframe="1d"):
        raise DataError("boom")


class _WorkingProvider:
    def __init__(self):
        self.calls = 0

    def bars(self, symbol, start, end, timeframe="1d"):
        self.calls += 1
        return make_bars(symbol, [100.0, 101.0])


def test_fallback_provider_uses_next_source():
    working = _WorkingProvider()
    provider = FallbackDataProvider([_FailingProvider(), working])
    bars = provider.bars("BTC/USDT", START, END)
    assert len(bars) == 2
    assert provider.last_source == "_WorkingProvider"
    assert working.calls == 1


def test_fallback_provider_all_fail():
    provider = FallbackDataProvider([_FailingProvider(), _FailingProvider()])
    with pytest.raises(DataError):
        provider.bars("BTC/USDT", START, END)
