"""The daily paper-trading loop.

One run = fetch data -> build a snapshot per pair -> judge -> policy weights ->
plan orders -> hard risk vetoes -> submit to the venue -> append to the
append-only journal. The journal is the artefact that turns this into a
tamper-evident public track record (committed by the GitHub Action).

The simulated wallet has no remote account, so its state (cash + positions) is
reconstructed from the last journal record; real venues carry their own state.

Nothing here talks to a vendor directly; the venue, provider and strategy are
injected, so the whole loop is unit-tested offline.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import datetime

from src.execution.orders import PlannedOrder, plan_orders
from src.execution.venue import Order, Venue
from src.journal.journal import Journal
from src.policy.risk import RiskLimits, RiskState, veto_reason


def _peak_equity(journal: Journal, current: float) -> float:
    peak = current
    for record in journal.read():
        value = record.get("account_equity")
        if isinstance(value, (int, float)):
            peak = max(peak, float(value))
    return peak


def _last_venue_state(journal: Journal) -> dict | None:
    last = None
    for record in journal.read():
        if record.get("venue_state"):
            last = record["venue_state"]
    return last


def _serialise_judgments(strategy) -> dict:
    judgments = getattr(strategy, "last_judgments", None) or {}
    return {
        symbol: {name: asdict(judgment) for name, judgment in symbol_judgments.items()}
        for symbol, symbol_judgments in judgments.items()
    }


def run_paper_once(
    *,
    strategy,
    venue: Venue,
    bars_by_symbol: Mapping[str, Sequence],
    journal: Journal,
    limits: RiskLimits,
    as_of: datetime | None = None,
    dry_run: bool = False,
) -> dict:
    stamps = sorted({bar.ts for bars in bars_by_symbol.values() for bar in bars})
    if not stamps:
        raise ValueError("no bars available for the paper loop")
    as_of = as_of or stamps[-1]

    history = {
        symbol: [bar for bar in bars if bar.ts <= as_of]
        for symbol, bars in bars_by_symbol.items()
    }
    history = {symbol: bars for symbol, bars in history.items() if bars}
    prices = {symbol: bars[-1].close for symbol, bars in history.items()}

    # Restore the simulated wallet from the journal (real venues keep their own state).
    if hasattr(venue, "load_state"):
        state = _last_venue_state(journal)
        if state:
            venue.load_state(state)
    venue.set_marks(prices)

    account = venue.account()
    positions = venue.positions()
    current_qty = {symbol: position.qty for symbol, position in positions.items()}
    current_gross = sum(abs(position.market_value) for position in positions.values())

    target_weights = strategy.target_weights(as_of, history)

    peak = _peak_equity(journal, account.equity)
    drawdown_pct = 0.0 if peak <= 0 else max(0.0, 1.0 - account.equity / peak)

    planned = plan_orders(target_weights, account.equity, current_qty, prices)

    submitted: list[dict] = []
    vetoed: list[dict] = []
    for order in planned:
        sign = 1.0 if order.side == "buy" else -1.0
        held_value = abs(positions[order.symbol].market_value) if order.symbol in positions else 0.0
        resulting_position = max(0.0, held_value + sign * order.notional)
        resulting_gross = max(0.0, current_gross + sign * order.notional)
        state = RiskState(
            portfolio_value=account.equity,
            position_value=resulting_position,
            gross_exposure_pct=resulting_gross / account.equity if account.equity > 0 else 0.0,
            daily_pnl_pct=account.daily_pnl_pct,
            drawdown_pct=drawdown_pct,
            open_positions=len(positions),
        )
        reason = veto_reason(state, limits)
        if reason is not None:
            vetoed.append(_order_record(order, reason))
            continue
        order_id = None
        if not dry_run:
            order_id = venue.submit(Order(symbol=order.symbol, qty=order.qty, side=order.side))
        submitted.append(_order_record(order, None, order_id))

    record = {
        "event": "paper_decision",
        "as_of": as_of.isoformat(),
        "dry_run": dry_run,
        "strategy": type(strategy).__name__,
        "account_equity": account.equity,
        "cash": account.cash,
        "daily_pnl_pct": account.daily_pnl_pct,
        "drawdown_pct": drawdown_pct,
        "target_weights": target_weights,
        "submitted": submitted,
        "vetoed": vetoed,
        "snapshots": getattr(strategy, "last_snapshots", None) or {},
        "judgments": _serialise_judgments(strategy),
    }
    if hasattr(venue, "state"):
        record["venue_state"] = venue.state()
    if not dry_run:
        journal.append(record)
    return record


def _order_record(order: PlannedOrder, reason: str | None, order_id: str | None = None) -> dict:
    record = {
        "symbol": order.symbol,
        "side": order.side,
        "qty": order.qty,
        "notional": order.notional,
    }
    if order_id is not None:
        record["order_id"] = order_id
    if reason is not None:
        record["veto_reason"] = reason
    return record
