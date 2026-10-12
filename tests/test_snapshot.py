"""Snapshot-builder tests (deterministic, JSON-serialisable)."""

from __future__ import annotations

from src.features.snapshot import FeatureParams, build_snapshot
from tests.helpers import make_bars


def test_build_snapshot_keys():
    bars = make_bars("BTC/USDT", [100.0 + i for i in range(30)])
    snap = build_snapshot("BTC/USDT", bars, FeatureParams(ma_windows=(20,), vol_window=5))
    assert snap["symbol"] == "BTC/USDT"
    assert "ts" in snap
    assert snap["close"] == 129.0
    assert snap["ma_distance"]["20"] is not None
    assert snap["realized_vol"] is not None


def test_build_snapshot_empty_raises():
    import pytest

    with pytest.raises(ValueError):
        build_snapshot("BTC/USDT", [])
