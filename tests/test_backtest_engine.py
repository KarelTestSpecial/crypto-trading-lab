"""Backtest-engine tests: correctness, costs, no look-ahead, weight validation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.backtest.engine import run_backtest
from src.backtest.metrics import CostModel
from tests.helpers import make_bars


class BuyAndHold:
    def target_weights(self, ts, history):
        return {symbol: 1.0 for symbol in history}


class LookaheadProbe:
    """Records the newest bar shown; must never exceed the decision timestamp."""

    def __init__(self):
        self.newest_seen: datetime | None = None

    def target_weights(self, ts, history):
        for bars in history.values():
            for bar in bars:
                if bar.ts > ts:
                    raise AssertionError(f"look-ahead: saw {bar.ts} while deciding on {ts}")
                self.newest_seen = bar.ts
        return {}


class OverLeveraged:
    def target_weights(self, ts, history):
        return {symbol: 1.5 for symbol in history}


def _two_series(closes):
    return make_bars("BTC/USDT", closes), make_bars("BTC/USDT", closes)


def test_buy_and_hold_no_costs():
    btc, bench = _two_series([100.0, 110.0, 121.0])
    result = run_backtest({"BTC/USDT": btc}, bench, BuyAndHold(), CostModel())
    assert result.portfolio_returns == pytest.approx([0.10, 0.10])
    assert result.report["cumulative_return"] == pytest.approx(0.21)
    assert result.report["benchmark_cumulative_return"] == pytest.approx(0.21)
    assert result.report["excess_return"] == pytest.approx(0.0)


def test_costs_reduce_return():
    btc, bench = _two_series([100.0, 110.0, 121.0])
    free = run_backtest({"BTC/USDT": btc}, bench, BuyAndHold(), CostModel())
    costly = run_backtest(
        {"BTC/USDT": btc}, bench, BuyAndHold(), CostModel(fee_bps=5, slippage_bps=5)
    )
    assert costly.report["cumulative_return"] < free.report["cumulative_return"]
    # first-bar turnover is 1.0, so the first net return is gross minus 10 bps.
    assert costly.portfolio_returns[0] == pytest.approx(0.10 - 0.001)


def test_no_lookahead():
    btc, bench = _two_series([100.0, 105.0, 110.0, 115.0])
    probe = LookaheadProbe()
    result = run_backtest({"BTC/USDT": btc}, bench, probe, CostModel())
    assert result.timestamps[-1] == datetime(2024, 1, 4, tzinfo=UTC)
    assert probe.newest_seen is not None


def test_over_leverage_rejected():
    btc, bench = _two_series([100.0, 110.0, 121.0])
    with pytest.raises(ValueError, match="leverage"):
        run_backtest({"BTC/USDT": btc}, bench, OverLeveraged(), CostModel())


def test_needs_two_aligned_bars():
    btc = make_bars("BTC/USDT", [100.0])
    bench = make_bars("BTC/USDT", [100.0])
    with pytest.raises(ValueError):
        run_backtest({"BTC/USDT": btc}, bench, BuyAndHold(), CostModel())


def test_benchmark_is_required_in_report():
    btc, bench = _two_series([100.0, 110.0, 121.0])
    result = run_backtest({"BTC/USDT": btc}, bench, BuyAndHold(), CostModel())
    assert "benchmark_sharpe" in result.report
    assert result.report["cost_model"] == {"fee_bps": 0.0, "slippage_bps": 0.0}
