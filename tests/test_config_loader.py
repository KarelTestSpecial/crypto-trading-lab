"""Config-loader tests against the shipped YAML files."""

from __future__ import annotations

import pytest

from src.config_loader import ConfigLoadError, load_risk, load_strategy, load_universe
from src.features.snapshot import FeatureParams
from src.policy.risk import RiskLimits


def test_load_universe():
    universe = load_universe()
    assert universe.benchmark == "BTC/USDT"
    assert "BTC/USDT" in universe.symbols
    assert universe.timeframe == "1d"


def test_load_strategy_returns_feature_params():
    params = load_strategy()
    assert isinstance(params, FeatureParams)
    assert 20 in params.ma_windows


def test_load_risk_matches_yaml():
    limits = load_risk()
    assert isinstance(limits, RiskLimits)
    assert limits.max_position_pct == pytest.approx(0.15)
    assert limits.max_gross_exposure_pct == pytest.approx(0.90)


def test_missing_file_raises():
    with pytest.raises(ConfigLoadError):
        load_universe("/nonexistent/universe.yaml")
