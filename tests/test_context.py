"""Context-layer tests (offline): static provider + deterministic digest."""

from __future__ import annotations

from datetime import date

from src.context.base import ContextItem
from src.context.digest import build_digest
from src.context.static import StaticContextProvider


def test_static_provider_filters_by_symbol():
    provider = StaticContextProvider(
        [
            ContextItem("feed", "BTC headline", "text", symbol="BTC/USDT"),
            ContextItem("feed", "ETH headline", "text", symbol="ETH/USDT"),
        ]
    )
    items = provider.items(["BTC/USDT"], date(2025, 1, 1), date(2025, 1, 1))
    assert [i.title for i in items] == ["BTC headline"]


def test_digest_is_grouped_and_deterministic():
    items = [
        ContextItem("feed", "BTC headline", "some text", symbol="BTC/USDT"),
        ContextItem("feed", "market note", "macro text", symbol=None),
    ]
    digest = build_digest(items)
    assert "[BTC/USDT]" in digest
    assert "[MARKET]" in digest
    assert digest == build_digest(items)


def test_digest_truncates():
    items = [ContextItem("feed", f"h{i}", "x" * 500, symbol="BTC/USDT") for i in range(50)]
    assert len(build_digest(items, max_chars=200)) <= 202
