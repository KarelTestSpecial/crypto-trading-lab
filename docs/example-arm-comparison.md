# CryptoCadence — arm comparison

Same universe, same period, same costs — only the arm changes. This is a **simulation**; not investment advice.

## Configuration

| field | value |
|---|---|
| universe | ADA/USDT, AVAX/USDT, BNB/USDT, BTC/USDT, DOGE/USDT, DOT/USDT, ETH/USDT, LINK/USDT, SOL/USDT, XRP/USDT |
| benchmark | BTC/USDT |
| data source | CSV (var/sample_bars) |
| costs | 10 bps fee + 10 bps slippage (per side) |

## Arms

| arm | what | cum. return | excess | sharpe | max DD | brier | ECE |
|---|---|---|---|---|---|---|---|
| A | Deterministic trend baseline: equal-weight the pairs above their MA, capped by the hard position limit. | +53.64% | -139.97% | 1.456 | -16.70% | n/a | n/a |
| B | Context + judgment layer (offline rule-based comparator) feeding the shared policy engine. (offline rule-based judge) | +17.66% | -175.95% | 0.621 | -23.80% | 0.274 | 0.119 |
| C | Calibrated decision model (Jev adapter) feeding the shared policy engine. | — | — | — | — | — | — |
| D | Hybrid: trend rule gates the universe, judgment sizes within it (Fase 4). (offline rule-based judge) | +40.76% | -152.85% | 1.233 | -20.89% | 0.282 | 0.132 |

### Arms that could not run

- **C**: JEV_API_KEY is required to call Jev

## Calibration (P(up) vs realised)

### Arm B — n=4800, Brier=0.274, ECE=0.119

| bin | count | avg prob | empirical |
|---|---|---|---|
| 0.0–0.1 | 1 | 0.09 | 1.00 |
| 0.1–0.2 | 34 | 0.18 | 0.68 |
| 0.2–0.3 | 274 | 0.26 | 0.48 |
| 0.3–0.4 | 676 | 0.36 | 0.49 |
| 0.4–0.5 | 1215 | 0.45 | 0.51 |
| 0.5–0.6 | 1206 | 0.55 | 0.52 |
| 0.6–0.7 | 765 | 0.64 | 0.50 |
| 0.7–0.8 | 398 | 0.74 | 0.50 |
| 0.8–0.9 | 167 | 0.84 | 0.49 |
| 0.9–1.0 | 64 | 0.93 | 0.47 |

### Arm D — n=2359, Brier=0.282, ECE=0.132

| bin | count | avg prob | empirical |
|---|---|---|---|
| 0.3–0.4 | 6 | 0.39 | 0.67 |
| 0.4–0.5 | 235 | 0.47 | 0.48 |
| 0.5–0.6 | 796 | 0.56 | 0.53 |
| 0.6–0.7 | 698 | 0.65 | 0.50 |
| 0.7–0.8 | 393 | 0.74 | 0.50 |
| 0.8–0.9 | 167 | 0.84 | 0.49 |
| 0.9–1.0 | 64 | 0.93 | 0.47 |

## Limitations

- ⚠️ **Synthetic data.** These numbers come from generated prices; they validate the pipeline, not any edge.
- **Simulation only** — no real money, not investment advice.
- **Survivorship bias:** the universe is today's liquid pairs; dead/delisted tokens are absent.
- **Not HFT** — a 1h–1d cadence; latency-sensitive microstructure is out of scope.
- **No live track record yet** (the paper loop is Fase 5).
- Calibration of a deterministic judge is expected to be poor; the point is that the machinery measures it honestly (Jev should do better).

## Disclaimer

See [DISCLAIMER.md](../DISCLAIMER.md) in the repository root.
