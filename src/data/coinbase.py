"""Coinbase public candles provider (fallback; free, no API key).

Coinbase Exchange exposes public candles with no credentials:
`/products/{product}/candles?granularity=86400`. The response is a list of
`[time, low, high, open, close, volume]` (newest first). At most 300 candles are
returned per request, so the provider paginates.

Docs: https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproductcandles
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from src.data.base import Bar, DataError, DataProvider
from src.data.http import http_get_json

COINBASE_CANDLES_URL = "https://api.exchange.coinbase.com/products/{product}/candles"

_GRANULARITY_SECONDS = {"1h": 3600, "4h": 14400, "1d": 86400}
_MAX_CANDLES = 300


def coinbase_product(symbol: str) -> str:
    """Map a canonical pair to Coinbase's product id: BTC/USDT -> BTC-USDT."""
    return symbol.upper().replace("/", "-")


def parse_coinbase_candles(rows: list, symbol: str, start: date, end: date) -> list[Bar]:
    bars: list[Bar] = []
    for row in rows:
        try:
            ts = datetime.fromtimestamp(int(row[0]), tz=UTC)
            if not (start <= ts.date() <= end):
                continue
            bars.append(
                Bar(
                    symbol=symbol.upper(),
                    ts=ts,
                    open=float(row[3]),
                    high=float(row[2]),
                    low=float(row[1]),
                    close=float(row[4]),
                    volume=float(row[5]),
                )
            )
        except (IndexError, ValueError, TypeError) as exc:
            raise DataError(f"malformed Coinbase candle for {symbol!r}: {row}") from exc
    bars.sort(key=lambda b: b.ts)
    return bars


class CoinbaseDataProvider(DataProvider):
    def __init__(self, *, timeout: float = 15.0) -> None:
        self.timeout = timeout

    def bars(self, symbol: str, start: date, end: date, timeframe: str = "1d") -> list[Bar]:
        granularity = _GRANULARITY_SECONDS.get(timeframe)
        if granularity is None:
            raise DataError(f"Coinbase does not support timeframe {timeframe!r}")
        product = coinbase_product(symbol)
        window = timedelta(seconds=granularity * _MAX_CANDLES)
        bars: list[Bar] = []
        cursor = datetime(start.year, start.month, start.day, tzinfo=UTC)
        end_dt = datetime(end.year, end.month, end.day, tzinfo=UTC) + timedelta(days=1)
        while cursor < end_dt:
            chunk_end = min(cursor + window, end_dt)
            rows = self._fetch(product, granularity, cursor, chunk_end)
            bars.extend(parse_coinbase_candles(rows, symbol, start, end))
            cursor = chunk_end
        return bars

    def _fetch(self, product: str, granularity: int, start: datetime, end: datetime) -> list:
        from urllib.parse import urlencode

        params = {
            "granularity": str(granularity),
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
        url = COINBASE_CANDLES_URL.format(product=product) + "?" + urlencode(params)
        data = http_get_json(url, timeout=self.timeout)
        if not isinstance(data, list):
            raise DataError(f"unexpected Coinbase response for {product!r}: {data!r}")
        return data
