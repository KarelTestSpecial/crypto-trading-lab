# Capability narrative — CryptoCadence (2 minutes)

## What it is

CryptoCadence is a **transparent AI-driven paper-trading and backtest platform for
crypto**, built to demonstrate a production-shaped quant/automation stack. It is the
crypto counterpart of Cadence (`ai-trading-lab`), with one key upgrade: the AI decision
layer is **Jev**, a calibrated "System One" model, wired in for real.

## The three things that make it credible

1. **Honesty is enforced in code, not promised.**
   `build_report()` refuses to emit a performance report unless a benchmark
   (BTC buy-and-hold) *and* a cost model (fees + slippage) are supplied. Testing is
   walk-forward / out-of-sample. The report lists its own limitations.

2. **The AI is calibrated, not generative.**
   Jev returns *typed* decisions — `choice` (key + probabilities + confidence), `score`
   (ordered scale) and `noul` (yes/no probability) — instead of text. Every judgment
   carries a confidence, and the system measures whether "80% sure" really is right
   ~80% of the time (**Brier/ECE**). That is the difference between a demo and a system
   you can trust in a pipeline.

3. **The track record is tamper-evident.**
   Every decision (snapshot + rationale + outcome) is appended to
   `journal/decisions.jsonl` and committed, so the public git history *is* the audit
   trail.

## Safety by construction

- **Simulation by default.** Paper wallet; no keys, no network, no real money.
- **Live is hard-gated.** Real capital needs three simultaneous gates
  (`TRADING_MODE=live` + `ALLOW_LIVE_TRADING=true` + `confirm_live=True`); the public
  demo can never go live.
- **HITL is a flag.** Paper runs fully autonomously; live defaults to human
  confirmation per order.
- **Hard risk vetoes** (position size, gross exposure, daily loss, drawdown, max
  positions) that the model can never override.

## Honest scope

This is **not** HFT — that is a latency race a cloud agent cannot win. CryptoCadence
operates at a 1h–1d cadence, where the calibrated judgment layer is the edge, not speed.
