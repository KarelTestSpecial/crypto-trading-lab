"""Daily paper-loop tests (offline: fake venue, fixed strategy)."""

from __future__ import annotations

import pytest

from src.execution.venue import Account, PaperVenue, Position
from src.journal.journal import Journal
from src.loop import run_paper_once
from src.policy.risk import RiskLimits
from src.strategy.arms import build_arm
from tests.helpers import make_bars


class FakeVenue:
    def __init__(self, account: Account, positions: dict[str, Position] | None = None):
        self._account = account
        self._positions = positions or {}
        self.submitted = []
        self.marks: dict[str, float] = {}

    def set_marks(self, prices):
        self.marks.update(prices)

    def account(self) -> Account:
        return self._account

    def positions(self) -> dict[str, Position]:
        return self._positions

    def submit(self, order):
        self.submitted.append(order)
        return f"oid-{len(self.submitted)}"


class FixedStrategy:
    def __init__(self, weights: dict[str, float]):
        self.weights = weights

    def target_weights(self, ts, history):
        return self.weights


def _bars():
    return {
        "BTC/USDT": make_bars("BTC/USDT", [100.0] * 60),
        "ETH/USDT": make_bars("ETH/USDT", [50.0] * 60),
    }


def test_loop_submits_planned_orders(tmp_path):
    venue = FakeVenue(Account(100_000, 100_000, 100_000, 100_000))
    journal = Journal(tmp_path / "decisions.jsonl")
    record = run_paper_once(
        strategy=FixedStrategy({"BTC/USDT": 0.1}),
        venue=venue,
        bars_by_symbol=_bars(),
        journal=journal,
        limits=RiskLimits(),
    )
    assert record["submitted"][0]["symbol"] == "BTC/USDT"
    assert venue.submitted[0].qty == pytest.approx(100.0)  # 0.1 * 100000 / 100
    assert journal.path.exists()


def test_dry_run_neither_submits_nor_appends(tmp_path):
    venue = FakeVenue(Account(100_000, 100_000, 100_000, 100_000))
    journal = Journal(tmp_path / "decisions.jsonl")
    run_paper_once(
        strategy=FixedStrategy({"BTC/USDT": 0.1}),
        venue=venue,
        bars_by_symbol=_bars(),
        journal=journal,
        limits=RiskLimits(),
        dry_run=True,
    )
    assert venue.submitted == []
    assert not journal.path.exists()


def test_drawdown_veto_blocks_all_orders(tmp_path):
    journal = Journal(tmp_path / "decisions.jsonl")
    journal.append({"event": "paper_decision", "account_equity": 200_000})
    venue = FakeVenue(Account(100_000, 100_000, 100_000, 100_000))
    record = run_paper_once(
        strategy=FixedStrategy({"BTC/USDT": 0.1}),
        venue=venue,
        bars_by_symbol=_bars(),
        journal=journal,
        limits=RiskLimits(max_drawdown_pct=0.20),
    )
    assert record["submitted"] == []
    assert record["vetoed"]
    assert venue.submitted == []


def test_sell_closes_position(tmp_path):
    venue = FakeVenue(
        Account(100_000, 100_000, 100_000, 100_000),
        {"BTC/USDT": Position("BTC/USDT", qty=10.0, market_value=1000.0, avg_entry_price=90.0)},
    )
    journal = Journal(tmp_path / "decisions.jsonl")
    record = run_paper_once(
        strategy=FixedStrategy({}),  # target: nothing held
        venue=venue,
        bars_by_symbol=_bars(),
        journal=journal,
        limits=RiskLimits(),
    )
    assert record["submitted"][0]["side"] == "sell"
    assert venue.submitted[0].symbol == "BTC/USDT"


def test_trend_arm_orders_clear_the_position_limit(tmp_path):
    """Regression: equal-weight must be capped below max_position_pct so the loop
    can invest instead of vetoing every order."""
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
    bars = {s: make_bars(s, [100.0 + i for i in range(60)]) for s in symbols}
    strategy = build_arm("A", ma_window=5)
    venue = FakeVenue(Account(100_000, 100_000, 100_000, 100_000))
    journal = Journal(tmp_path / "decisions.jsonl")
    record = run_paper_once(
        strategy=strategy,
        venue=venue,
        bars_by_symbol=bars,
        journal=journal,
        limits=RiskLimits(),
    )
    assert record["vetoed"] == []
    assert len(record["submitted"]) == len(symbols)
    assert set(record["target_weights"].values()) == {0.15}
    assert all(abs(order["notional"] - 15_000.0) < 0.01 for order in record["submitted"])


def test_paper_venue_state_persists_across_runs(tmp_path):
    journal = Journal(tmp_path / "decisions.jsonl")
    bars = {"BTC/USDT": make_bars("BTC/USDT", [100.0] * 60)}
    limits = RiskLimits(max_position_pct=1.0)

    first = run_paper_once(
        strategy=FixedStrategy({"BTC/USDT": 0.5}),
        venue=PaperVenue(cash=100_000.0),
        bars_by_symbol=bars,
        journal=journal,
        limits=limits,
    )
    assert first["venue_state"]["positions"]["BTC/USDT"]["qty"] == pytest.approx(500.0)

    # A fresh venue must reconstruct its positions from the journal.
    second = run_paper_once(
        strategy=FixedStrategy({"BTC/USDT": 0.5}),
        venue=PaperVenue(cash=100_000.0),
        bars_by_symbol=bars,
        journal=journal,
        limits=limits,
    )
    assert second["submitted"] == []  # already at target, nothing to do
