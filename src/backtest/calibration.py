"""Backtest calibration observer.

The calibration math (Brier score, ECE, the `Prediction` record and
`judgment_prob_up`) is owned by cadence-core and imported here. Only the
backtest observer remains: `CalibrationRecorder` hooks into the engine and is
coupled to the strategy contract, so it belongs to this project.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from cadence_core.calibration import Prediction, judgment_prob_up

from src.backtest.engine import Strategy

__all__ = ["CalibrationRecorder"]


class CalibrationRecorder:
    """Backtest observer that captures per-decision (prob_up, outcome) pairs."""

    def __init__(self) -> None:
        self.predictions: list[Prediction] = []

    def __call__(
        self,
        ts: datetime,
        next_ts: datetime,
        strategy: Strategy,
        price: Mapping[str, Mapping[datetime, float]],
    ) -> None:
        judgments = getattr(strategy, "last_judgments", None)
        if not judgments:
            return
        for symbol, symbol_judgments in judgments.items():
            judgment = symbol_judgments.get("direction")
            if judgment is None:
                continue
            prob_up = judgment_prob_up(judgment)
            if prob_up is None:
                continue
            series = price.get(symbol)
            if not series or not series.get(ts) or next_ts not in series:
                continue
            self.predictions.append(
                Prediction(
                    symbol=symbol,
                    ts=ts,
                    prob_up=prob_up,
                    went_up=series[next_ts] > series[ts],
                )
            )
