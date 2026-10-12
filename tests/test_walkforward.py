"""Walk-forward evaluation tests."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta

import pytest

from src.backtest.metrics import CostModel
from src.backtest.walkforward import make_folds, run_walk_forward
from src.strategy.arms import build_arm
from tests.helpers import make_bars


def _stamps(n: int) -> list[datetime]:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    return [start + timedelta(days=i) for i in range(n)]


def test_make_folds_structure():
    stamps = _stamps(100)
    folds = make_folds(stamps, n_folds=5, initial_train_frac=0.4)
    assert len(folds) == 5
    assert folds[0].train == stamps[:40]
    assert folds[0].test == stamps[40:52]
    assert folds[-1].test == stamps[88:100]


def test_make_folds_are_contiguous_and_disjoint():
    stamps = _stamps(100)
    folds = make_folds(stamps, n_folds=5, initial_train_frac=0.4)
    for fold in folds:
        assert fold.train[-1] < fold.test[0]
    for earlier, later in itertools.pairwise(folds):
        assert earlier.test[-1] < later.test[0]


def test_make_folds_rejects_too_few_bars():
    with pytest.raises(ValueError):
        make_folds(_stamps(5), n_folds=5, initial_train_frac=0.4)


def test_run_walk_forward_reports_and_is_deterministic():
    closes = [100.0 * (1.0 + 0.001) ** i for i in range(300)]
    bars = {"BTC/USDT": make_bars("BTC/USDT", closes), "ETH/USDT": make_bars("ETH/USDT", closes[::-1])}
    benchmark = make_bars("BTC/USDT", closes)
    costs = CostModel(fee_bps=10, slippage_bps=10)

    def factory(ma_window: float):
        return build_arm("A", ma_window=int(ma_window), max_positions=6)

    first = run_walk_forward(
        bars, benchmark, factory, costs, param_grid=[20, 50], n_folds=3, initial_train_frac=0.4
    )
    second = run_walk_forward(
        bars, benchmark, factory, costs, param_grid=[20, 50], n_folds=3, initial_train_frac=0.4
    )
    assert len(first.folds) == 3
    assert "benchmark_sharpe" in first.report
    for fold in first.folds:
        assert fold["chosen_param"] in (20, 50)
    assert [f["chosen_param"] for f in first.folds] == [f["chosen_param"] for f in second.folds]
    assert first.portfolio_returns == pytest.approx(second.portfolio_returns)


def test_run_walk_forward_requires_grid():
    bars = {"BTC/USDT": make_bars("BTC/USDT", [100.0 + i for i in range(300)])}
    benchmark = make_bars("BTC/USDT", [100.0 + i for i in range(300)])
    with pytest.raises(ValueError):
        run_walk_forward(
            bars, benchmark, lambda w: build_arm("A", ma_window=50), CostModel(), param_grid=[]
        )
