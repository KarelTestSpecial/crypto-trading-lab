"""Hybrid arm-D tests."""

from __future__ import annotations

from datetime import UTC, datetime

from src.judgment.rules import RuleBasedJudge
from src.policy.risk import RiskLimits
from src.strategy.hybrid import HybridStrategy
from tests.helpers import make_bars

TS = datetime(2025, 12, 31, tzinfo=UTC)


def test_hybrid_gates_on_trend_then_judges():
    history = {
        "BTC/USDT": make_bars("BTC/USDT", [100.0 * 1.003**i for i in range(260)]),
        "DOGE/USDT": make_bars("DOGE/USDT", [100.0 * 0.997**i for i in range(260)]),
    }
    strategy = HybridStrategy(
        RuleBasedJudge(), RiskLimits(max_positions=10, max_position_pct=1.0), ma_window=50
    )
    weights = strategy.target_weights(TS, history)
    # DOGE is below its MA, so the rule gate excludes it before the judge runs.
    assert set(weights) == {"BTC/USDT"}
    assert set(strategy.last_judgments) == {"BTC/USDT"}
