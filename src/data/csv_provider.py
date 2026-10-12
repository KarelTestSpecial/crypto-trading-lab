"""CSV market-data provider.

Reads OHLCV bars from `<directory>/<SYMBOL>.csv` with a header of
`ts,open,high,low,close,volume` (case-insensitive, any column order; `date` is
accepted as an alias for `ts`). The symbol is sanitised for the filesystem, so
`BTC/USDT` becomes `BTC-USDT.csv`. This is the offline provider used by tests and
by local backtests on cached data.
"""

from __future__ import annotations

import csv
from datetime import UTC, date, datetime
from pathlib import Path

from src.data.base import Bar, DataError, DataProvider

_REQUIRED = {"open", "high", "low", "close", "volume"}
_TIME_COLUMNS = ("ts", "date", "time", "timestamp")


def sanitize_symbol(symbol: str) -> str:
    """Map a canonical pair to a filesystem-safe name: BTC/USDT -> BTC-USDT."""
    return symbol.upper().replace("/", "-")


def parse_ts(raw: str) -> datetime:
    """Parse an ISO date or datetime (naive treated as UTC) into a UTC datetime."""
    raw = raw.strip()
    if not raw:
        raise ValueError("empty timestamp")
    if "T" in raw or " " in raw:
        text = raw.replace("Z", "+00:00").replace(" ", "T", 1)
        dt = datetime.fromisoformat(text)
    else:
        dt = datetime.fromisoformat(raw + "T00:00:00+00:00")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class CsvDataProvider(DataProvider):
    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)

    def path_for(self, symbol: str) -> Path:
        return self.directory / f"{sanitize_symbol(symbol)}.csv"

    def bars(self, symbol: str, start: date, end: date, timeframe: str = "1d") -> list[Bar]:
        path = self.path_for(symbol)
        if not path.exists():
            raise DataError(f"no CSV for {symbol!r} at {path}")
        bars: list[Bar] = []
        with path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                raise DataError(f"{path} has no header")
            fields = {name.strip().lower(): name for name in reader.fieldnames}
            time_col = next((fields[c] for c in _TIME_COLUMNS if c in fields), None)
            if time_col is None:
                raise DataError(f"{path} is missing a timestamp column (ts/date)")
            missing = _REQUIRED - set(fields)
            if missing:
                raise DataError(f"{path} is missing columns: {sorted(missing)}")
            for row in reader:
                ts = parse_ts(row[time_col])
                if not (start <= ts.date() <= end):
                    continue
                bars.append(
                    Bar(
                        symbol=symbol.upper(),
                        ts=ts,
                        open=float(row[fields["open"]]),
                        high=float(row[fields["high"]]),
                        low=float(row[fields["low"]]),
                        close=float(row[fields["close"]]),
                        volume=float(row[fields["volume"]]),
                    )
                )
        bars.sort(key=lambda b: b.ts)
        return bars
