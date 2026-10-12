"""Static context provider (tests, offline demos, fixtures).

Returns a fixed list of items, filtered to the requested symbols and date range.
Deterministic, so it is safe to use in tests and reproducible prompts.
"""

from __future__ import annotations

from datetime import date

from src.context.base import ContextItem, ContextProvider


class StaticContextProvider(ContextProvider):
    def __init__(self, items: list[ContextItem]) -> None:
        self._items = list(items)

    def items(self, symbols: list[str], start: date, end: date) -> list[ContextItem]:
        wanted = {s.upper() for s in symbols}
        out: list[ContextItem] = []
        for item in self._items:
            if item.symbol is not None and item.symbol.upper() not in wanted:
                continue
            if item.published is not None and not (start <= item.published <= end):
                continue
            out.append(item)
        return out
