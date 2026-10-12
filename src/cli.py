"""Command-line entry point.

Commands:
  * `doctor`   — verify configuration and the safety gates.
  * `probe`    — send one sample state + typed questions to Jev and print the
                 calibrated judgments (demonstrates arm C). Requires a key.
  * `backtest` — run the backtest over crypto bars and print an honest report
                 (BTC benchmark + costs are mandatory).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import date

from src.backtest.engine import run_backtest
from src.backtest.metrics import CostModel
from src.config import ConfigError, TradingMode, load_settings
from src.config_loader import (
    ConfigLoadError,
    UniverseConfig,
    load_risk,
    load_strategy,
    load_universe,
)
from src.data.base import DataError
from src.data.registry import build_data_provider
from src.execution.venue import LiveTradingDisabledError, get_venue
from src.judgment.jev import JevAdapter, JevClient, JevError, choice, noul, score
from src.strategy.trend import TrendFollowingStrategy


def cmd_doctor(args: argparse.Namespace) -> int:
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"[FAIL] invalid configuration: {exc}")
        return 1

    print("CryptoCadence :: doctor")
    print(f"  TRADING_MODE      = {settings.trading_mode.value}")
    print(f"  ALLOW_LIVE_TRADING= {settings.allow_live_trading}")
    print(f"  PUBLIC_DEMO       = {settings.public_demo}")
    print(f"  HITL              = {settings.hitl}")
    print(f"  VENUE             = {settings.venue.value}")
    print(f"  JOURNAL_PATH      = {settings.journal_path}")
    print(f"  JEV key set       = {bool(settings.jev_api_key)}")

    ok = True
    if settings.trading_mode is TradingMode.LIVE:
        try:
            venue = get_venue(settings, confirm_live=args.confirm_live)
        except LiveTradingDisabledError as exc:
            print(f"[FAIL] live requested but blocked: {exc}")
            ok = False
        else:
            print(
                f"[WARN] LIVE trading would be enabled via {venue.kind.value} "
                f"(HITL={'on' if venue.requires_confirmation else 'off'}). "
                "This must never happen in the demo."
            )
    else:
        venue = get_venue(settings)
        print(f"[OK]   paper mode via {venue.kind.value}; live trading is gated off.")

    return 0 if ok else 1


def cmd_probe(args: argparse.Namespace) -> int:
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"[FAIL] invalid configuration: {exc}")
        return 1

    adapter = JevAdapter(JevClient(settings))
    state = {"summary": args.state}
    questions = {
        "direction": choice(
            "Should the desk be net long, flat or short this pair?",
            {"long": "upward bias", "flat": "no position", "short": "downward bias"},
        ),
        "conviction": score(
            "How strong is the setup?", ["very weak", "weak", "neutral", "strong", "very strong"]
        ),
        "is_trend": noul("Is the pair in a sustained uptrend?"),
    }

    print("CryptoCadence :: probe")
    print(f"  model = {settings.jev_model} @ {settings.jev_base_url}")
    print(f"  state = {args.state}")
    print()
    try:
        judgments = adapter.judge(state, questions)
    except JevError as exc:
        print(f"[FAIL] {exc}")
        return 1

    print(f"  {'question':<12}{'value':<14}{'confidence':>11}")
    print(f"  {'-' * 12}{'-' * 14}{'-' * 11}")
    for name in questions:
        j = judgments.get(name)
        if j is None:
            print(f"  {name:<12}{'n/a':<14}{'n/a':>11}")
        else:
            print(f"  {name:<12}{j.value:<14}{j.confidence:>11.2f}")
    return 0


def _window(args: argparse.Namespace) -> tuple[date, date]:
    start = date.fromisoformat(args.start) if args.start else date(1900, 1, 1)
    end = date.fromisoformat(args.end) if args.end else date(2100, 1, 1)
    return start, end


def _fmt(value, pct: bool = False) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2%}" if pct else f"{value:.3f}"


def _print_report(report: dict, universe: UniverseConfig, n_trades: int, args) -> None:
    print("CryptoCadence :: backtest")
    print(f"  benchmark      = {universe.benchmark}")
    print(f"  bars           = {report['n_periods']}")
    print(f"  costs          = {args.fee_bps} bps fee + {args.slippage_bps} bps slippage (per side)")
    print()
    print(f"  {'metric':<22}{'strategy':>14}{'benchmark':>14}")
    print(f"  {'-' * 22}{'-' * 14}{'-' * 14}")
    print(
        f"  {'cumulative return':<22}"
        f"{_fmt(report['cumulative_return'], pct=True):>14}"
        f"{_fmt(report['benchmark_cumulative_return'], pct=True):>14}"
    )
    print(f"  {'excess return':<22}{_fmt(report['excess_return'], pct=True):>14}{'':>14}")
    print(f"  {'annualized return':<22}{_fmt(report['annualized_return'], pct=True):>14}{'':>14}")
    print(
        f"  {'sharpe':<22}{_fmt(report['sharpe']):>14}{_fmt(report['benchmark_sharpe']):>14}"
    )
    print(
        f"  {'max drawdown':<22}"
        f"{_fmt(report['max_drawdown'], pct=True):>14}"
        f"{_fmt(report['benchmark_max_drawdown'], pct=True):>14}"
    )
    print(f"  {'hit rate':<22}{_fmt(report['hit_rate'], pct=True):>14}{'':>14}")
    print()
    print(f"  trades         = {n_trades}")


def cmd_backtest(args: argparse.Namespace) -> int:
    try:
        universe = load_universe(args.universe)
        load_strategy(args.strategy)
        limits = load_risk()
    except (ConfigError, ConfigLoadError) as exc:
        print(f"[FAIL] configuration error: {exc}")
        return 1

    settings = load_settings()
    if args.provider == "csv" and not args.data_dir:
        print("[FAIL] --provider csv requires --data-dir")
        return 1
    try:
        provider = build_data_provider(settings, name=args.provider, csv_dir=args.data_dir)
    except DataError as exc:
        print(f"[FAIL] data error: {exc}")
        return 1

    start, end = _window(args)
    try:
        bars_by_symbol = {}
        for symbol in universe.symbols:
            bars = provider.bars(symbol, start, end, universe.timeframe)
            if bars:
                bars_by_symbol[symbol] = bars
        benchmark = provider.bars(universe.benchmark, start, end, universe.timeframe)
    except DataError as exc:
        print(f"[FAIL] data error: {exc}")
        return 1
    if not bars_by_symbol or not benchmark:
        print("[FAIL] no bars available")
        return 1

    max_pct = args.max_position_pct if args.max_position_pct is not None else limits.max_position_pct
    strategy = TrendFollowingStrategy(
        ma_window=args.ma_window, max_positions=args.max_positions, max_position_pct=max_pct
    )
    costs = CostModel(fee_bps=args.fee_bps, slippage_bps=args.slippage_bps)
    try:
        result = run_backtest(
            bars_by_symbol, benchmark, strategy, costs, initial_equity=args.equity
        )
    except ValueError as exc:
        print(f"[FAIL] backtest error: {exc}")
        return 1

    _print_report(result.report, universe, len(result.trades), args)
    if args.json:
        print()
        print(json.dumps(result.report, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="crypto-trading-lab")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="verify configuration and safety gates")
    doctor.add_argument(
        "--confirm-live",
        action="store_true",
        help="satisfy the third live-trading gate (for diagnostics only)",
    )
    doctor.set_defaults(func=cmd_doctor)

    probe = sub.add_parser("probe", help="send a sample state + questions to Jev")
    probe.add_argument(
        "--state",
        default="BTC/USDT is 3% above its 50-day average on rising volume.",
        help="the state summary to judge",
    )
    probe.set_defaults(func=cmd_probe)

    backtest = sub.add_parser("backtest", help="run the backtest over crypto bars")
    backtest.add_argument(
        "--provider", default="csv", choices=["csv", "auto", "kraken", "coinbase"]
    )
    backtest.add_argument("--data-dir", default=None, help="required when --provider csv")
    backtest.add_argument("--universe", default=None, help="path to universe.yaml")
    backtest.add_argument("--strategy", default=None, help="path to strategy.yaml")
    backtest.add_argument("--start", default=None, help="ISO start date (inclusive)")
    backtest.add_argument("--end", default=None, help="ISO end date (inclusive)")
    backtest.add_argument("--ma-window", type=int, default=50, help="trend moving-average window")
    backtest.add_argument("--max-positions", type=int, default=6)
    backtest.add_argument("--max-position-pct", type=float, default=None)
    backtest.add_argument("--fee-bps", type=float, default=10.0, help="per-side fee in bps")
    backtest.add_argument("--slippage-bps", type=float, default=10.0, help="per-side slippage in bps")
    backtest.add_argument("--equity", type=float, default=100_000.0, help="initial equity")
    backtest.add_argument("--json", action="store_true", help="also print the raw report JSON")
    backtest.set_defaults(func=cmd_backtest)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
