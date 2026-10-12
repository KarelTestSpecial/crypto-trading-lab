"""Venue abstraction with a hard live-trading gate and HITL.

Design rule (see PLAN §6): paper <-> live is a *configuration* difference
(backend + keys), never a code rewrite. Switching to live requires ALL THREE
gates simultaneously:

    1. TRADING_MODE=live
    2. ALLOW_LIVE_TRADING=true
    3. confirm_live=True passed explicitly in code

Additionally, PUBLIC_DEMO=true makes live trading impossible, unconditionally.

HITL (human-in-the-loop) is orthogonal: paper ignores it because no capital
moves; live venues expose `requires_confirmation = settings.hitl` so the order
layer can queue a proposal instead of submitting.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from itertools import count

from src.config import Settings, TradingMode, VenueKind


class VenueError(RuntimeError):
    """Raised when a venue rejects a request or is misconfigured."""


class LiveTradingDisabledError(RuntimeError):
    """Raised when live trading is attempted without satisfying the safety gates."""


@dataclass(frozen=True)
class Order:
    symbol: str
    qty: float
    side: str  # "buy" | "sell"

    def __post_init__(self) -> None:
        if self.side not in {"buy", "sell"}:
            raise ValueError(f"side must be 'buy' or 'sell', got {self.side!r}")
        if self.qty <= 0:
            raise ValueError("qty must be positive")


@dataclass(frozen=True)
class Position:
    symbol: str
    qty: float
    market_value: float
    avg_entry_price: float


@dataclass(frozen=True)
class Account:
    equity: float
    cash: float
    buying_power: float
    last_equity: float

    @property
    def daily_pnl_pct(self) -> float:
        if self.last_equity <= 0:
            return 0.0
        return self.equity / self.last_equity - 1.0


class Venue(ABC):
    """Common interface for paper and live execution backends."""

    mode: TradingMode
    kind: VenueKind
    requires_confirmation: bool = False

    @abstractmethod
    def submit(self, order: Order) -> str:
        """Submit an order and return a venue order id."""

    @abstractmethod
    def positions(self) -> dict[str, Position]:
        """Return current positions keyed by symbol."""

    @abstractmethod
    def account(self) -> Account:
        """Return the account snapshot (equity, cash, ...)."""

    def set_marks(self, prices: dict[str, float]) -> None:
        """Set mark prices. No-op by default; PaperVenue overrides."""


class PaperVenue(Venue):
    """Simulated wallet: no keys, no network, fills at the supplied mark price."""

    mode = TradingMode.PAPER
    kind = VenueKind.PAPER
    requires_confirmation = False

    def __init__(self, *, cash: float = 100_000.0, marks: dict[str, float] | None = None) -> None:
        self._initial_cash = cash
        self._cash = cash
        self._marks = dict(marks or {})
        self._qty: dict[str, float] = {}
        self._basis: dict[str, float] = {}
        self._ids = count(1)

    def set_marks(self, marks: dict[str, float]) -> None:
        self._marks.update(marks)

    def _mark(self, symbol: str) -> float:
        price = self._marks.get(symbol)
        if price is None or price <= 0:
            raise VenueError(f"no mark price for {symbol}")
        return price

    def submit(self, order: Order) -> str:
        price = self._mark(order.symbol)
        notional = price * order.qty
        if order.side == "buy":
            if notional > self._cash + 1e-9:
                raise VenueError("insufficient cash")
            self._cash -= notional
        else:
            held = self._qty.get(order.symbol, 0.0)
            if order.qty > held + 1e-9:
                raise VenueError("insufficient position")
            self._cash += notional

        signed = order.qty if order.side == "buy" else -order.qty
        new_qty = self._qty.get(order.symbol, 0.0) + signed
        if abs(new_qty) < 1e-12:
            self._qty.pop(order.symbol, None)
            self._basis.pop(order.symbol, None)
        else:
            self._qty[order.symbol] = new_qty
            self._basis[order.symbol] = price
        return f"paper-{next(self._ids)}"

    def positions(self) -> dict[str, Position]:
        positions: dict[str, Position] = {}
        for symbol, qty in self._qty.items():
            price = self._marks.get(symbol, self._basis.get(symbol, 0.0))
            positions[symbol] = Position(symbol, qty, qty * price, self._basis.get(symbol, 0.0))
        return positions

    def account(self) -> Account:
        equity = self._cash + sum(p.market_value for p in self.positions().values())
        return Account(
            equity=equity, cash=self._cash, buying_power=self._cash, last_equity=self._initial_cash
        )

    def state(self) -> dict:
        """Serialise the simulated wallet so the daily loop can persist it."""
        return {
            "initial_cash": self._initial_cash,
            "cash": self._cash,
            "positions": {
                symbol: {"qty": qty, "basis": self._basis.get(symbol, 0.0)}
                for symbol, qty in self._qty.items()
            },
        }

    def load_state(self, state: dict) -> None:
        """Restore a simulated wallet from a previous run (journal-backed)."""
        self._initial_cash = float(state.get("initial_cash", self._initial_cash))
        self._cash = float(state.get("cash", self._cash))
        positions = state.get("positions") or {}
        self._qty = {s: float(p["qty"]) for s, p in positions.items()}
        self._basis = {s: float(p.get("basis", 0.0)) for s, p in positions.items()}


class CexVenue(Venue):
    """Live CEX execution (Kraken/Coinbase). Gated; lands in a later phase."""

    mode = TradingMode.LIVE
    kind = VenueKind.CEX

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.requires_confirmation = settings.hitl

    def submit(self, order: Order) -> str:
        raise VenueError("CEX live venue is not implemented yet (Fase 5+)")

    def positions(self) -> dict[str, Position]:
        raise VenueError("CEX live venue is not implemented yet (Fase 5+)")

    def account(self) -> Account:
        raise VenueError("CEX live venue is not implemented yet (Fase 5+)")


class OnchainVenue(Venue):
    """Live on-chain execution (RPC + signer). Gated; lands in a later phase."""

    mode = TradingMode.LIVE
    kind = VenueKind.ONCHAIN

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.requires_confirmation = settings.hitl

    def submit(self, order: Order) -> str:
        raise VenueError("on-chain live venue is not implemented yet (Fase 5+)")

    def positions(self) -> dict[str, Position]:
        raise VenueError("on-chain live venue is not implemented yet (Fase 5+)")

    def account(self) -> Account:
        raise VenueError("on-chain live venue is not implemented yet (Fase 5+)")


def get_venue(settings: Settings, *, confirm_live: bool = False) -> Venue:
    """Return the correct venue, enforcing the live-trading safety gates."""
    if settings.trading_mode is TradingMode.LIVE:
        if settings.public_demo:
            raise LiveTradingDisabledError(
                "PUBLIC_DEMO=true: live trading is disabled for the public demo."
            )
        if not settings.allow_live_trading:
            raise LiveTradingDisabledError("Live trading requires ALLOW_LIVE_TRADING=true.")
        if not confirm_live:
            raise LiveTradingDisabledError(
                "Live trading requires confirm_live=True passed explicitly in code."
            )
        if settings.venue is VenueKind.CEX:
            return CexVenue(settings)
        if settings.venue is VenueKind.ONCHAIN:
            return OnchainVenue(settings)
        raise LiveTradingDisabledError(
            "live mode requires VENUE=cex or VENUE=onchain (paper venues cannot go live)."
        )

    return PaperVenue()
