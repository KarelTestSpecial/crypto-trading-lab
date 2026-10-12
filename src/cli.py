"""Command-line entry point.

Commands:
  * `doctor`   — verify configuration and the safety gates.
  * `probe`    — send one sample state + typed questions to Jev and print the
                 calibrated judgments (demonstrates arm C). Requires a key.
  * `backtest` — run the backtest over crypto bars and print an honest report
                 (BTC benchmark + costs are mandatory).
  * `report`   — run the backtest and write a publishable Markdown report
                 (walk-forward by default).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from src.backtest.calibration import (
    CalibrationRecorder,
    brier_score,
    calibration_table,
    expected_calibration_error,
)
from src.backtest.compare import ArmSpec, ComparisonContext, compare_arms, render_comparison
from src.backtest.engine import run_backtest
from src.backtest.metrics import CostModel
from src.backtest.report import ReportContext, render_markdown
from src.backtest.walkforward import run_walk_forward
from src.config import ConfigError, TradingMode, load_settings
from src.config_loader import (
    ConfigLoadError,
    UniverseConfig,
    load_risk,
    load_strategy,
    load_universe,
)
from src.data.base import Bar, DataError
from src.data.registry import build_data_provider
from src.execution.venue import LiveTradingDisabledError, get_venue
from src.judgment.factory import build_judge
from src.judgment.jev import JevAdapter, JevClient, JevError, choice, noul, score
from src.judgment.rules import RuleBasedJudge
from src.strategy.arms import ARM_DESCRIPTIONS, build_arm
from src.strategy.judgment import JudgmentStrategy


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


def _load_bars(provider, universe: UniverseConfig, args):
    start, end = _window(args)
    bars_by_symbol: dict[str, list[Bar]] = {}
    for symbol in universe.symbols:
        bars = provider.bars(symbol, start, end, universe.timeframe)
        if bars:
            bars_by_symbol[symbol] = bars
    benchmark = provider.bars(universe.benchmark, start, end, universe.timeframe)
    return bars_by_symbol, benchmark


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
    print(f"  {'sharpe':<22}{_fmt(report['sharpe']):>14}{_fmt(report['benchmark_sharpe']):>14}")
    print(
        f"  {'max drawdown':<22}"
        f"{_fmt(report['max_drawdown'], pct=True):>14}"
        f"{_fmt(report['benchmark_max_drawdown'], pct=True):>14}"
    )
    print(f"  {'hit rate':<22}{_fmt(report['hit_rate'], pct=True):>14}{'':>14}")
    print()
    print(f"  trades         = {n_trades}")


def _build_provider(settings, args):
    if args.provider == "csv" and not args.data_dir:
        raise DataError("--provider csv requires --data-dir")
    return build_data_provider(settings, name=args.provider, csv_dir=args.data_dir)


def cmd_backtest(args: argparse.Namespace) -> int:
    try:
        universe = load_universe(args.universe)
        load_strategy(args.strategy)
        limits = load_risk()
    except (ConfigError, ConfigLoadError) as exc:
        print(f"[FAIL] configuration error: {exc}")
        return 1

    settings = load_settings()
    try:
        provider = _build_provider(settings, args)
        bars_by_symbol, benchmark = _load_bars(provider, universe, args)
    except DataError as exc:
        print(f"[FAIL] data error: {exc}")
        return 1
    if not bars_by_symbol or not benchmark:
        print("[FAIL] no bars available")
        return 1

    strategy = build_arm(
        "A", limits=limits, ma_window=args.ma_window, max_positions=args.max_positions
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


def _parse_grid(raw: str) -> list[float]:
    grid = [float(part) for part in raw.split(",") if part.strip()]
    if not grid:
        raise ValueError("--ma-grid must contain at least one number")
    return grid


def cmd_report(args: argparse.Namespace) -> int:
    try:
        universe = load_universe(args.universe)
        load_strategy(args.strategy)
        limits = load_risk()
        grid = _parse_grid(args.ma_grid)
    except (ConfigError, ConfigLoadError, ValueError) as exc:
        print(f"[FAIL] configuration error: {exc}")
        return 1

    settings = load_settings()
    try:
        provider = _build_provider(settings, args)
        bars_by_symbol, benchmark = _load_bars(provider, universe, args)
    except DataError as exc:
        print(f"[FAIL] data error: {exc}")
        return 1
    if not bars_by_symbol or not benchmark:
        print("[FAIL] no bars available")
        return 1

    def arm_factory(ma_window: float):
        return build_arm(
            "A", limits=limits, ma_window=int(ma_window), max_positions=args.max_positions
        )

    costs = CostModel(fee_bps=args.fee_bps, slippage_bps=args.slippage_bps)
    try:
        if args.no_walk_forward:
            result = run_backtest(
                bars_by_symbol, benchmark, arm_factory(grid[0]), costs, initial_equity=args.equity
            )
            report = result.report
            folds: list[dict] = []
        else:
            wf = run_walk_forward(
                bars_by_symbol,
                benchmark,
                arm_factory,
                costs,
                param_grid=grid,
                n_folds=args.folds,
                initial_train_frac=args.train_frac,
                initial_equity=args.equity,
            )
            report = wf.report
            folds = wf.folds
    except ValueError as exc:
        print(f"[FAIL] backtest error: {exc}")
        return 1

    context = ReportContext(
        title=args.title,
        symbols=tuple(sorted(bars_by_symbol)),
        benchmark=universe.benchmark,
        strategy=f"arm A — {ARM_DESCRIPTIONS.get('A', '')}",
        data_source=f"CSV ({args.data_dir})" if args.provider == "csv" else f"{args.provider} (live)",
        data_is_synthetic=args.synthetic,
        walk_forward=not args.no_walk_forward,
        start=date.fromisoformat(args.start) if args.start else None,
        end=date.fromisoformat(args.end) if args.end else None,
        folds=folds,
    )
    markdown = render_markdown(report, context)

    out = Path(args.out) if args.out else Path("var/reports") / f"{date.today():%Y%m%d}_backtest.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    print(f"wrote {out}")
    if args.json:
        json_path = out.with_suffix(".json")
        json_path.write_text(
            json.dumps({"report": report, "folds": folds}, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        print(f"wrote {json_path}")
    return 0


def cmd_judge(args: argparse.Namespace) -> int:
    try:
        universe = load_universe(args.universe)
        params = load_strategy(args.strategy)
        limits = load_risk()
    except (ConfigError, ConfigLoadError) as exc:
        print(f"[FAIL] configuration error: {exc}")
        return 1

    settings = load_settings()
    try:
        provider = _build_provider(settings, args)
        bars_by_symbol, _ = _load_bars(provider, universe, args)
    except DataError as exc:
        print(f"[FAIL] data error: {exc}")
        return 1
    if args.symbols:
        wanted = {s.strip().upper() for s in args.symbols.split(",") if s.strip()}
        bars_by_symbol = {s: b for s, b in bars_by_symbol.items() if s in wanted}
    if not bars_by_symbol:
        print("[FAIL] no bars to judge")
        return 1

    strategy = JudgmentStrategy(build_judge(args.judge, settings), limits, params=params)
    ts = max(bar.ts for bars in bars_by_symbol.values() for bar in bars)
    history = {s: [b for b in bars if b.ts <= ts] for s, bars in bars_by_symbol.items()}
    try:
        weights = strategy.target_weights(ts, history)
    except (JevError, ValueError) as exc:
        print(f"[FAIL] judgment error: {exc}")
        return 1

    print("CryptoCadence :: judge")
    print(f"  ts      = {ts.isoformat()}")
    print(f"  judge   = {args.judge}")
    print(f"  limits  = max {limits.max_positions} positions, {limits.max_position_pct:.0%} each")
    print()
    print(f"  {'symbol':<12}{'direction':>11}{'confidence':>12}{'weight':>10}")
    print(f"  {'-' * 12}{'-' * 11}{'-' * 12}{'-' * 10}")
    for symbol in sorted(bars_by_symbol):
        j = strategy.last_judgments.get(symbol, {}).get("direction")
        value = j.value if j else "n/a"
        conf = f"{j.confidence:.2f}" if j else "n/a"
        print(f"  {symbol:<12}{value:>11}{conf:>12}{weights.get(symbol, 0.0):>10.2%}")
    print()
    print(f"  gross exposure = {sum(weights.values()):.2%}")
    return 0


def cmd_calibrate(args: argparse.Namespace) -> int:
    try:
        universe = load_universe(args.universe)
        params = load_strategy(args.strategy)
        limits = load_risk()
    except (ConfigError, ConfigLoadError) as exc:
        print(f"[FAIL] configuration error: {exc}")
        return 1

    settings = load_settings()
    try:
        provider = _build_provider(settings, args)
        bars_by_symbol, benchmark = _load_bars(provider, universe, args)
    except DataError as exc:
        print(f"[FAIL] data error: {exc}")
        return 1
    if not bars_by_symbol or not benchmark:
        print("[FAIL] no bars available")
        return 1

    strategy = JudgmentStrategy(build_judge(args.judge, settings), limits, params=params)
    recorder = CalibrationRecorder()
    costs = CostModel(fee_bps=args.fee_bps, slippage_bps=args.slippage_bps)
    try:
        result = run_backtest(
            bars_by_symbol,
            benchmark,
            strategy,
            costs,
            initial_equity=args.equity,
            on_decision=recorder,
        )
    except (JevError, ValueError) as exc:
        print(f"[FAIL] backtest error: {exc}")
        return 1

    brier = brier_score(recorder.predictions)
    ece = expected_calibration_error(recorder.predictions)
    print("CryptoCadence :: calibrate")
    print(f"  judge   = {args.judge}")
    print(f"  cum ret = {result.report['cumulative_return']:+.2%}")
    print(f"  n preds = {len(recorder.predictions)}")
    print(f"  brier   = {'n/a' if brier is None else f'{brier:.3f}'}")
    print(f"  ECE     = {'n/a' if ece is None else f'{ece:.3f}'}")
    print()
    print(f"  {'bin':<14}{'count':>7}{'avg prob':>11}{'empirical':>11}")
    print(f"  {'-' * 14}{'-' * 7}{'-' * 11}{'-' * 11}")
    for row in calibration_table(recorder.predictions):
        print(
            f"  {row['bin_lower']:.1f}-{row['bin_upper']:.1f}"
            f"{row['count']:>11}{row['avg_prob']:>11.2f}{row['empirical']:>11.2f}"
        )
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    try:
        universe = load_universe(args.universe)
        params = load_strategy(args.strategy)
        limits = load_risk()
    except (ConfigError, ConfigLoadError) as exc:
        print(f"[FAIL] configuration error: {exc}")
        return 1

    settings = load_settings()
    try:
        provider = _build_provider(settings, args)
        bars_by_symbol, benchmark = _load_bars(provider, universe, args)
    except DataError as exc:
        print(f"[FAIL] data error: {exc}")
        return 1
    if not bars_by_symbol or not benchmark:
        print("[FAIL] no bars available")
        return 1

    costs = CostModel(fee_bps=args.fee_bps, slippage_bps=args.slippage_bps)
    specs: list[ArmSpec] = []
    for key in [k.strip().upper() for k in args.arms.split(",") if k.strip()]:
        judge = None
        description = ARM_DESCRIPTIONS.get(key, "")
        if key in {"B", "D"}:
            judge = RuleBasedJudge()
            description += " (offline rule-based judge)"
        elif key == "C":
            judge = build_judge("jev", settings)
        try:
            strategy = build_arm(
                key,
                judge=judge,
                limits=limits,
                params=params,
                ma_window=args.ma_window,
                max_positions=args.max_positions,
            )
        except ValueError as exc:
            print(f"[FAIL] {exc}")
            return 1
        specs.append(ArmSpec(key=key, description=description, strategy=strategy))

    results = compare_arms(specs, bars_by_symbol, benchmark, costs, initial_equity=args.equity)

    print("CryptoCadence :: compare")
    for result in results:
        if result.report is None:
            print(f"  arm {result.key}: error: {result.error}")
            continue
        brier = result.calibration["brier"] if result.calibration else None
        print(
            f"  arm {result.key}: cum {result.report['cumulative_return']:+.2%} "
            f"excess {result.report['excess_return']:+.2%} "
            f"sharpe {result.report['sharpe']:.3f} "
            f"brier {'n/a' if brier is None else f'{brier:.3f}'}"
        )

    context = ComparisonContext(
        title=args.title,
        symbols=tuple(sorted(bars_by_symbol)),
        benchmark=universe.benchmark,
        data_source=f"CSV ({args.data_dir})" if args.provider == "csv" else f"{args.provider} (live)",
        costs=costs,
        data_is_synthetic=args.synthetic,
    )
    markdown = render_comparison(results, context)
    out = Path(args.out) if args.out else Path("var/reports") / f"{date.today():%Y%m%d}_compare.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    print(f"wrote {out}")
    return 0


def _add_data_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--provider", default="csv", choices=["csv", "auto", "kraken", "coinbase"])
    p.add_argument("--data-dir", default=None, help="required when --provider csv")
    p.add_argument("--universe", default=None, help="path to universe.yaml")
    p.add_argument("--strategy", default=None, help="path to strategy.yaml")
    p.add_argument("--start", default=None, help="ISO start date (inclusive)")
    p.add_argument("--end", default=None, help="ISO end date (inclusive)")
    p.add_argument("--ma-window", type=int, default=50, help="trend moving-average window")
    p.add_argument("--max-positions", type=int, default=None)
    p.add_argument("--fee-bps", type=float, default=10.0, help="per-side fee in bps")
    p.add_argument("--slippage-bps", type=float, default=10.0, help="per-side slippage in bps")
    p.add_argument("--equity", type=float, default=100_000.0, help="initial equity")


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
    _add_data_args(backtest)
    backtest.add_argument("--json", action="store_true", help="also print the raw report JSON")
    backtest.set_defaults(func=cmd_backtest)

    report = sub.add_parser("report", help="write a publishable Markdown backtest report")
    _add_data_args(report)
    report.add_argument("--out", default=None, help="output markdown path")
    report.add_argument("--title", default="CryptoCadence — backtest report")
    report.add_argument("--json", action="store_true", help="also write the raw report JSON")
    report.add_argument("--synthetic", action="store_true", help="mark data as synthetic")
    report.add_argument("--no-walk-forward", action="store_true", help="use a single window")
    report.add_argument("--ma-grid", default="20,50,100", help="comma-separated MA candidates")
    report.add_argument("--folds", type=int, default=5, help="number of walk-forward folds")
    report.add_argument("--train-frac", type=float, default=0.4, help="initial in-sample fraction")
    report.set_defaults(func=cmd_report)

    judge = sub.add_parser("judge", help="run the judgment pipeline for the latest bar")
    _add_data_args(judge)
    judge.add_argument("--judge", default="rules", choices=["rules", "jev"])
    judge.add_argument("--symbols", default=None, help="comma-separated subset of symbols")
    judge.set_defaults(func=cmd_judge)

    calibrate = sub.add_parser("calibrate", help="backtest + Brier/ECE calibration of the judgments")
    _add_data_args(calibrate)
    calibrate.add_argument("--judge", default="rules", choices=["rules", "jev"])
    calibrate.set_defaults(func=cmd_calibrate)

    compare = sub.add_parser("compare", help="compare experiment arms on the same data")
    _add_data_args(compare)
    compare.add_argument("--arms", default="A,B,D", help="comma-separated arms (A,B,C,D)")
    compare.add_argument("--out", default=None, help="output markdown path")
    compare.add_argument("--title", default="CryptoCadence — arm comparison")
    compare.add_argument("--synthetic", action="store_true", help="mark data as synthetic")
    compare.set_defaults(func=cmd_compare)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
