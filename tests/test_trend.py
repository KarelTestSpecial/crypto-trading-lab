"""Arm A (trend baseline) sizing: equal weight, capped by the hard position limit."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.strategy.trend import TrendFollowingStrategy
from tests.helpers import make_bars

TS = datetime(2024, 3, 29, tzinfo=UTC)
RISERS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT", "AVAX/USDT", "LINK/USDT"]


def _rising(symbol: str):
    return make_bars(symbol, [100.0 + i for i in range(10)])


def test_equal_weight_below_cap():
    strategy = TrendFollowingStrategy(ma_window=2, max_position_pct=0.5)
    weights = strategy.target_weights(TS, {s: _rising(s) for s in RISERS[:4]})
    assert weights == {s: 0.25 for s in RISERS[:4]}


def test_weights_capped_and_not_renormalised():
    """6 picks with a 15% cap is 90% invested, never 6 x 16.7% (renormalised)."""
    strategy = TrendFollowingStrategy(ma_window=2, max_position_pct=0.15, max_positions=6)
    weights = strategy.target_weights(TS, {s: _rising(s) for s in RISERS})
    assert len(weights) == 6
    assert all(w == pytest.approx(0.15) for w in weights.values())
    assert sum(weights.values()) == pytest.approx(0.90)


def test_no_pick_below_ma_returns_empty():
    strategy = TrendFollowingStrategy(ma_window=2)
    falling = {s: make_bars(s, [100.0 - i for i in range(10)]) for s in RISERS}
    assert strategy.target_weights(TS, falling) == {}


def test_max_positions_still_applies():
    strategy = TrendFollowingStrategy(ma_window=2, max_positions=3, max_position_pct=0.5)
    weights = strategy.target_weights(TS, {s: _rising(s) for s in RISERS})
    assert list(weights) == ["ADA/USDT", "AVAX/USDT", "BNB/USDT"]


def test_invalid_max_position_pct_raises():
    with pytest.raises(ValueError):
        TrendFollowingStrategy(max_position_pct=0.0)
    with pytest.raises(ValueError):
        TrendFollowingStrategy(max_position_pct=1.5)
