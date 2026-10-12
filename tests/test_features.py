"""Feature-engine tests (pure functions)."""

from __future__ import annotations

from src.features.state_engine import distance_from_ma, returns, simple_moving_average, zscore


def test_returns():
    assert returns([100, 110], 1) == 0.1
    assert returns([100], 1) is None


def test_simple_moving_average():
    assert simple_moving_average([1, 2, 3, 4], 2) == 3.5
    assert simple_moving_average([1], 2) is None


def test_distance_from_ma():
    assert distance_from_ma([10, 10, 11], 2) == (11 - 10.5) / 10.5


def test_zscore_none_when_flat():
    assert zscore([5, 5, 5], 3) is None
