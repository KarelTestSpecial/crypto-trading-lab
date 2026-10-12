"""Guardrail tests: the safety invariants of PLAN §3 and §6 must hold."""

from __future__ import annotations

import pytest

from src.backtest.metrics import CostModel, IncompleteReportError, build_report
from src.config import Settings, TradingMode, load_settings
from src.execution.venue import (
    CexVenue,
    LiveTradingDisabledError,
    PaperVenue,
    get_venue,
)
from src.policy.risk import RiskLimits, RiskState, veto_reason


def _settings(**overrides) -> Settings:
    base = {
        "TRADING_MODE": "paper",
        "ALLOW_LIVE_TRADING": "false",
        "PUBLIC_DEMO": "true",
        "VENUE": "paper",
    }
    base.update(overrides)
    return load_settings(base)


# --- live-trading gate -------------------------------------------------------

def test_default_is_paper():
    venue = get_venue(_settings())
    assert isinstance(venue, PaperVenue)
    assert venue.mode is TradingMode.PAPER


def test_live_blocked_by_default():
    with pytest.raises(LiveTradingDisabledError):
        get_venue(_settings(TRADING_MODE="live", VENUE="cex"))


def test_live_blocked_without_allow_flag():
    with pytest.raises(LiveTradingDisabledError):
        get_venue(_settings(TRADING_MODE="live", VENUE="cex", PUBLIC_DEMO="false"), confirm_live=True)


def test_live_blocked_without_confirm():
    with pytest.raises(LiveTradingDisabledError):
        get_venue(
            _settings(
                TRADING_MODE="live", VENUE="cex", ALLOW_LIVE_TRADING="true", PUBLIC_DEMO="false"
            ),
            confirm_live=False,
        )


def test_public_demo_never_goes_live_even_with_all_gates():
    with pytest.raises(LiveTradingDisabledError):
        get_venue(
            _settings(
                TRADING_MODE="live", VENUE="cex", ALLOW_LIVE_TRADING="true", PUBLIC_DEMO="true"
            ),
            confirm_live=True,
        )


def test_live_requires_all_three_gates():
    venue = get_venue(
        _settings(
            TRADING_MODE="live", VENUE="cex", ALLOW_LIVE_TRADING="true", PUBLIC_DEMO="false"
        ),
        confirm_live=True,
    )
    assert isinstance(venue, CexVenue)


# --- HITL --------------------------------------------------------------------

def test_paper_ignores_hitl():
    venue = get_venue(_settings(HITL="true"))
    assert venue.requires_confirmation is False


def test_live_honours_hitl_on():
    venue = get_venue(
        _settings(
            TRADING_MODE="live",
            VENUE="cex",
            ALLOW_LIVE_TRADING="true",
            PUBLIC_DEMO="false",
            HITL="true",
        ),
        confirm_live=True,
    )
    assert venue.requires_confirmation is True


def test_live_hitl_can_be_switched_off():
    venue = get_venue(
        _settings(
            TRADING_MODE="live",
            VENUE="cex",
            ALLOW_LIVE_TRADING="true",
            PUBLIC_DEMO="false",
            HITL="false",
        ),
        confirm_live=True,
    )
    assert venue.requires_confirmation is False


def test_hitl_defaults_on():
    assert load_settings({"TRADING_MODE": "paper"}).hitl is True


# --- honesty invariant -------------------------------------------------------

def test_report_requires_benchmark():
    with pytest.raises(IncompleteReportError):
        build_report([0.01, 0.02], benchmark_returns=None, costs=CostModel())


def test_report_requires_costs():
    with pytest.raises(IncompleteReportError):
        build_report([0.01, 0.02], benchmark_returns=[0.0, 0.01], costs=None)


def test_report_with_benchmark_and_costs():
    report = build_report(
        [0.01, -0.02, 0.03],
        benchmark_returns=[0.005, -0.01, 0.02],
        costs=CostModel(fee_bps=5, slippage_bps=5),
    )
    assert report["cost_model"] == {"fee_bps": 5, "slippage_bps": 5}
    assert "benchmark_sharpe" in report


# --- risk vetoes -------------------------------------------------------------

def test_risk_veto_drawdown():
    limits = RiskLimits(max_drawdown_pct=0.25)
    state = RiskState(100_000, 5_000, 0.05, 0.0, 0.30, 1)
    assert "drawdown" in (veto_reason(state, limits) or "")


def test_risk_veto_gross_exposure():
    limits = RiskLimits(max_gross_exposure_pct=0.90)
    state = RiskState(100_000, 5_000, 0.95, 0.0, 0.0, 1)
    assert "gross exposure" in (veto_reason(state, limits) or "")


def test_no_veto_when_healthy():
    limits = RiskLimits()
    state = RiskState(100_000, 5_000, 0.40, 0.01, 0.02, 3)
    assert veto_reason(state, limits) is None
