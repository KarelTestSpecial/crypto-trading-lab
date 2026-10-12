"""Kraken public OHLC provider (primary; free, no API key).

Kraken is MiCA-approved in the EU and its market-data endpoints are public — no
credentials are needed to *read*. The OHLC response is
`[time, open, high, low, close, vwap, volume, count]`; the last entry is the
current, not-yet-committed candle and is dropped so the backtest never sees a
partial bar.

Docs: https://docs.kraken.com/api/docs/rest-api/get-ohlc-data
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from src.data.base import Bar, DataError, DataProvider
from src.data.http import http_get_json

KRAKEN_OHLC_URL = "https://api.kraken.com/0/public/OHLC"

# Kraken interval in minutes.
_INTERVAL_MINUTES = {"1h": 60, "4h": 240, "1d": 1440, "1w": 10080}


def kraken_pair(symbol: str) -> str:
    """Map a canonical pair to Kraken's altname: BTC/USDT -> XBTUSDT."""
    base, quote = symbol.upper().split("/")
    base = "XBT" if base == "BTC" else base
    return f"{base}{quote}"


def parse_kraken_ohlc(payload: dict, symbol: str, start: date, end: date) -> list[Bar]:
    if payload.get("error"):
        raise DataError(f"Kraken error for {symbol!r}: {payload['error']}")
    result = payload.get("result") or {}
    rows = next(
        (v for k, v in result.items() if k != "last" and isinstance(v, list)),
        None,
    )
    if rows is None:
        raise DataError(f"unexpected Kraken response for {symbol!r}")
    bars: list[Bar] = []
    # Drop the final (uncommitted) candle.
    for row in rows[:-1]:
        try:
            ts = datetime.fromtimestamp(int(row[0]), tz=UTC)
            if not (start <= ts.date() <= end):
                continue
            bars.append(
                Bar(
                    symbol=symbol.upper(),
                    ts=ts,
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[6]),
                )
            )
        except (IndexError, KeyError, ValueError, TypeError) as exc:
            raise DataError(f"malformed Kraken row for {symbol!r}: {row}") from exc
    bars.sort(key=lambda b: b.ts)
    return bars


class KrakenDataProvider(DataProvider):
    def __init__(self, *, timeout: float = 15.0) -> None:
        self.timeout = timeout

    def bars(self, symbol: str, start: date, end: date, timeframe: str = "1d") -> list[Bar]:
        from urllib.parse import urlencode

        interval = _INTERVAL_MINUTES.get(timeframe)
        if interval is None:
            raise DataError(f"Kraken does not support timeframe {timeframe!r}")
        params = {"pair": kraken_pair(symbol), "interval": str(interval)}
        url = f"{KRAKEN_OHLC_URL}?{urlencode(params)}"
        payload = http_get_json(url, timeout=self.timeout)
        return parse_kraken_ohlc(payload, symbol, start, end)
