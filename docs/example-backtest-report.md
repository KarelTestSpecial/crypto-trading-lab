# CryptoCadence — backtest report

_Generated 2026-10-12 13:54 UTC._

This is a **simulation** produced by the `crypto-trading-lab` backtest engine. It does not trade real money and is not investment advice.

## Configuration

| field | value |
|---|---|
| strategy | arm A — Deterministic trend baseline: equal-weight the pairs above their MA, capped by the hard position limit. |
| universe | ADA/USDT, AVAX/USDT, BNB/USDT, BTC/USDT, DOGE/USDT, DOT/USDT, ETH/USDT, LINK/USDT, SOL/USDT, XRP/USDT |
| benchmark | BTC/USDT |
| period | 295 bars |
| data source | CSV (var/sample_bars) |
| costs | 10 bps fee + 10 bps slippage (per side) |
| evaluation | walk-forward (out-of-sample) |

## Results (295 periods)

| metric | strategy | benchmark |
|---|---|---|
| cumulative return | -0.18% | +92.09% |
| annualized return | -0.22% | n/a |
| sharpe | 0.108 | 1.512 |
| sortino | 0.154 | n/a |
| max drawdown | -16.70% | -38.62% |
| hit rate | +48.14% | n/a |
| **excess return** | **-92.27%** | |

## Walk-forward folds

| fold | train | test | chosen MA | train ret | test ret | benchmark test ret |
|---|---|---|---|---|---|---|
| 0 | 2025-05-31 → 2025-12-16 | 2025-12-17 → 2026-02-14 | 100 | +40.62% | +4.69% | +30.25% |
| 1 | 2025-05-31 → 2026-02-14 | 2026-02-15 → 2026-04-15 | 50 | +58.05% | -1.96% | -14.74% |
| 2 | 2025-05-31 → 2026-04-15 | 2026-04-16 → 2026-06-14 | 50 | +56.87% | +8.08% | +35.66% |
| 3 | 2025-05-31 → 2026-06-14 | 2026-06-15 → 2026-08-13 | 50 | +66.11% | +6.52% | +12.76% |
| 4 | 2025-05-31 → 2026-08-13 | 2026-08-14 → 2026-10-12 | 50 | +80.09% | -15.53% | +13.08% |

## Limitations

- ⚠️ **Synthetic data.** These numbers come from generated prices, not real markets. They validate the engine, not any strategy edge.
- **Simulation only.** No real money is traded; this is not investment advice.
- **Past performance is not indicative of future results.**
- **Survivorship bias:** the universe is today's liquid pairs; using it historically overstates returns because dead/delisted tokens are absent.
- **Walk-forward** chooses parameters on in-sample windows only and scores the next unseen window; the per-fold choices are shown above so the selection cannot be hidden.
- **Costs** are modelled as a flat per-side fee + slippage on turnover; real fills, spreads and market impact (and gas/MEV on-chain) differ.
- **Not HFT.** This operates at a 1h–1d cadence; latency-sensitive microstructure effects are out of scope.
- **No live track record yet.** The paper loop (Fase 5) is what turns this into tamper-evident evidence; a backtest alone is not.

## Disclaimer

See [DISCLAIMER.md](../DISCLAIMER.md) in the repository root.
