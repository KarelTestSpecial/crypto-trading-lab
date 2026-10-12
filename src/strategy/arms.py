"""Experiment arms (PLAN §3).

The arms experiment compares, on identical data and costs:
  * A — deterministic baseline rules
  * B — LLM context + judgment (Fase 3)
  * C — calibrated decision model / Jev adapter (Fase 3)
  * D — hybrid (Fase 4)

`build_arm` is the single entry point so every arm is constructed the same way
and compared fairly. AI arms require an injected `judge`; that is deliberate, so
an arm can never silently run without the model it claims to use.
"""

from __future__ import annotations

from src.backtest.engine import Strategy
from src.policy.risk import RiskLimits
from src.strategy.trend import TrendFollowingStrategy

ARMS = ("A", "B", "C", "D")

ARM_DESCRIPTIONS = {
    "A": "Deterministic trend baseline: equal-weight the pairs above their MA, capped by the hard position limit.",
    "B": "Context + judgment layer feeding the shared policy engine (Fase 3).",
    "C": "Calibrated decision model (Jev adapter) feeding the shared policy engine (Fase 3).",
    "D": "Hybrid: trend rule gates the universe, judgment sizes within it (Fase 4).",
}


def build_arm(
    name: str,
    *,
    limits: RiskLimits | None = None,
    ma_window: int = 50,
    max_positions: int | None = None,
) -> Strategy:
    key = name.strip().upper()
    effective_limits = limits or RiskLimits()
    positions = effective_limits.max_positions if max_positions is None else max_positions
    if key == "A":
        return TrendFollowingStrategy(
            ma_window=ma_window,
            max_positions=positions,
            max_position_pct=effective_limits.max_position_pct,
        )
    if key in {"B", "C", "D"}:
        raise ValueError(f"arm {key} is not available yet (arrives in Fase 3/4).")
    raise ValueError(f"unknown arm {name!r}; available: {', '.join(ARMS)}")
