# RISICO.md — honest risks and limitations

This file is deliberately blunt. A credible system states what can go wrong; that
is what makes the rest believable.

## 1. No profitability promise

A backtest that looks good is not evidence of future returns. Most retail
strategies fail after costs. This project's claim is **engineering quality and
honesty**, not returns.

## 2. Known methodological risks

- **Overfitting** — mitigated by walk-forward / out-of-sample testing, never
  in-sample tuning.
- **Cost drag** — fees and slippage can erase an edge; always modelled, never
  omitted. Crypto fees and spreads are often larger than equities'.
- **Survivorship bias** — using today's liquid pairs on historical data inflates
  results; delisted/dead tokens must be considered.
- **Look-ahead bias** — every feature uses only information strictly before the
  decision; enforced by timestamp discipline and logged snapshots.
- **Calibration drift** — if the model says P=0.8, we must verify events tagged
  0.8 actually happen ~80% of the time (Brier/ECE). Vendor calibration is not our
  calibration.

## 3. Market-structure limits

- **This is not HFT.** Crypto HFT is a latency race (colocation, microsecond
  matching). A cloud agent with 70–500 ms decisions and internet RTT cannot win
  it. CryptoCadence operates at a 1h–1d cadence, where latency is irrelevant.
- **On-chain execution is adversarial.** Block times, gas and MEV mean a
  wallet-only strategy is often the prey, not the predator. Live on-chain is out
  of scope until a later phase and always gated.
- **Venue/regulatory drift.** Primary data venues are EU-regulated (MiCA);
  Binance is used only for deep backtest history because its EU status is
  unsettled.

## 4. AI-layer risks

- Public models are available to everyone; a model alone is **not** an edge.
- A model output can be confidently wrong; hence typed judgments + confidence +
  the hard risk veto, never "let the model trade".

## 5. Operational & legal

- **Simulation only by default.** No real money, no advice, no management of
  third-party capital. See [DISCLAIMER.md](DISCLAIMER.md).
- Pointing the project at real accounts raises regulatory (MiCA), KYC and tax
  questions — out of scope here, and gated behind explicit human action.
- No personal data, no PII, no medical/legal context of the author is included in
  this repository.
