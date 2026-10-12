# Capability narrative

A 2-minute read for a technical evaluator (a hiring manager, a client, a peer).

## One-liner

A public, transparent **AI trading and backtesting platform for crypto**
(daily/swing): the engine, the data layer, a **calibrated AI decision layer
(Jev)** and the daily paper loop are all built from scratch in dependency-light
Python, with honesty and safety enforced in code rather than promised in a README.

## What I built

A complete pipeline, not a script:

```
Data → Features → Context → Judgment (Jev) → Policy → Risk veto → Execution → Journal
```

- **Data layer** — Kraken (primary, MiCA-approved EU) + Coinbase (fallback) public
  endpoints, keyless to read; CSV offline; one standard-library HTTP client, no
  vendor SDK. Binance is used only for deep backtest history.
- **Feature engine** — deterministic snapshots (returns, MA distances, z-scores,
  volatility). No black boxes.
- **Backtest engine** — walk-forward, look-ahead-free, costs on turnover, **BTC
  buy-and-hold benchmark mandatory**.
- **AI layer** — a pluggable judgment model. **Jev** (TypeSafe "System One")
  returns *typed, calibrated* decisions — `choice`, `score`, `noul` — instead of
  text; a deterministic offline judge is the comparator.
- **Policy + hard risk vetoes** — weights live in code; drawdown, daily-loss,
  gross-exposure, position-count and position-size limits have absolute veto power.
- **Paper loop** — a daily GitHub Action reads public crypto data, places
  simulated orders (the wallet's state is persisted in the journal) and commits an
  append-only journal, so the track record is tamper-evident. **No secrets required.**
- **Dashboard** — a static site (Vite + TypeScript, no chart libraries) that
  renders the committed journal.

## Key engineering decisions

1. **Code computes, the model judges.** All arithmetic is deterministic; the model
   only supplies fuzzy judgments with calibrated confidence.
2. **Calibration is measured, not claimed.** Jev is built for calibration (RLCD);
   every confidence is scored against realised outcomes (Brier/ECE), so "80% sure"
   can be checked.
3. **Honesty enforced in code.** A performance report *cannot* be produced without
   a benchmark and a cost model; the report always states its own limitations.
4. **No silent fallback.** A missing key, an unwired model, or a malformed answer
   fails loudly — a judgment never quietly becomes a trade.
5. **Live trading is hard-gated; HITL is a flag.** Three independent live gates plus
   a public-demo switch that makes live impossible; paper runs fully autonomously,
   live defaults to human confirmation per order.
6. **Dependency-light by design.** No pandas/numpy, no LLM SDK, no HTTP client
   library — the whole system is auditable and runs offline in tests.

## What I deliberately did not do

- **No HFT.** Crypto HFT is a latency race a cloud agent cannot win; this operates
  at a 1h–1d cadence, where the calibrated judgment layer is the edge.
- No proprietary-feed reverse-engineering, no live trading, no profitability claims.
- No fabricated track record: the dashboard shows the real journal, not seeded numbers.

## How to verify it yourself

```bash
uv run --group dev pytest -q                 # 90+ tests, offline
uv run python -m src.cli doctor              # safety gates
uv run python scripts/make_sample_data.py --out var/sample_bars
uv run python -m src.cli backtest --provider csv --data-dir var/sample_bars
uv run python -m src.cli report   --provider csv --data-dir var/sample_bars --synthetic
uv run python -m src.cli compare  --provider csv --data-dir var/sample_bars --synthetic --arms A,B,C,D
uv run python -m src.cli calibrate --provider csv --data-dir var/sample_bars --judge rules
uv run python -m src.cli paper-run --provider csv --data-dir var/sample_bars --arm A --dry-run
```

Then read `ARCHITECTURE.md`, `RISICO.md`, the generated reports, and the
`journal/decisions.jsonl` git history.
