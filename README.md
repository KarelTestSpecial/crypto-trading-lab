# CryptoCadence

**Transparent AI-driven paper-trading and backtest platform for crypto.**

CryptoCadence is the crypto counterpart of [`ai-trading-lab` (Cadence)](https://github.com/cadence-trading/ai-trading-lab).
It demonstrates a production-shaped quant/automation stack — data layer, deterministic
feature engine, a **calibrated AI decision layer (Jev)**, hard risk vetoes, an
append-only tamper-evident journal and a dashboard — for liquid crypto pairs.

It is a **capability showcase**: by default it trades a **simulated wallet** (paper)
and moves no real money. Live execution is hard-gated and impossible in public-demo mode.

> **Not investment advice. Simulation only. Past performance — real or simulated — is
> not indicative of future results.** See [DISCLAIMER.md](DISCLAIMER.md) and [RISICO.md](RISICO.md).

**Live dashboard:** https://cadence-trading.github.io/crypto-trading-lab/

## Why this is different from a "trading bot"

- **Honesty enforced in code.** A performance report *cannot* be produced without a
  benchmark (BTC buy-and-hold) **and** a cost model (fees + slippage). Walk-forward /
  out-of-sample, never in-sample tuning.
- **Calibrated AI, not vibes.** The judgment layer uses **Jev** (TypeSafe "System One"),
  a model that returns *typed, calibrated* decisions — `choice`, `score`, `noul`
  (yes/no probability) — instead of generated text. It is measured with **Brier/ECE**,
  so "80% sure" can be checked against reality.
- **Tamper-evident track record.** Every decision (snapshot + rationale + outcome) is
  appended to `journal/decisions.jsonl` and committed, so the public git history is the
  audit trail.
- **Hard risk vetoes.** Deterministic limits (position size, gross exposure, daily loss,
  drawdown, max positions) that the model can never override.
- **Dependency-light.** Pure-Python engine (no pandas/numpy), standard-library HTTP,
  no LLM SDK. The whole stack is auditable and testable offline.

## Status

| Phase | Deliverable | Status |
|---|---|---|
| **0** | Plan + scaffold + guardrails (`Venue` + triple live-gate + HITL) + CI + README + disclaimer | ✅ 12/10/2026 |
| **1** | Data layer (Kraken/Coinbase/CoinGecko + CSV) + feature engine + backtest with costs + BTC benchmark | ⏳ |
| **2** | Baseline rules (arm A) + honest metrics report | ⏳ |
| **3** | **Jev wired as arm C** + calibration (Brier/ECE) | ✅ 12/10/2026 |
| **4** | Hybrid (arm D) + `compare-arms` | ✅ 12/10/2026 |
| **5** | Daily paper loop + journal-in-git + dashboard | ✅ 12/10/2026 |
| **6** | Showcase package + client-facing config/docs | ✅ 12/10/2026 |

## Quick start

```bash
# Requires uv (https://docs.astral.sh/uv/)
uv run --group dev pytest -q        # guardrail + judgment + journal tests
uv run python -m src.cli doctor     # verify config and the safety gates
```

To exercise the Jev judgment layer you need an API key (route re-evaluated periodically,
see [PLAN §11](../PLAN/crypto-trading-lab.md)):

```bash
export JEV_API_KEY=...              # OpenRouter or direct TypeSafe access
uv run python -m src.cli probe      # one sample state -> typed, calibrated judgments
```

## Layout

```
config/     universe.yaml · strategy.yaml · risk.yaml
src/        config.py · data/ · features/ · judgment/ · policy/ · backtest/ · execution/ · journal/ · cli.py
tests/      guardrails · judgment · journal · features
journal/    decisions.jsonl   (append-only, committed = tamper-evident)
docs/       capability-narrative.md
.github/workflows/ci.yml
```

## Safety gates

Live trading (real capital) requires **all three** simultaneously: `TRADING_MODE=live`,
`ALLOW_LIVE_TRADING=true`, and `confirm_live=True` in code. `PUBLIC_DEMO=true` disables
live unconditionally. **HITL** (human confirmation per order) is on by default for live;
paper ignores it because no capital moves. See [ARCHITECTURE.md](ARCHITECTURE.md).

## Licence

MIT — see [LICENSE](LICENSE).
