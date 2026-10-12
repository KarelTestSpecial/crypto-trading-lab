# ARCHITECTURE

CryptoCadence is the crypto counterpart of Cadence (`ai-trading-lab`). Same design
principles, a different market and a real calibrated model (Jev) instead of a stub.

```
loop (cron: GitHub Action, €0)
  → Data layer        (Kraken + Coinbase + CoinGecko + CSV offline)
  → Feature/State     (deterministic, pure functions — no model)
  → Context (optional)
  → Judgment layer     (Jev = arm C, calibrated; rule-based offline comparator)
  → Policy + HARD RISK VETO
  → Execution → Venue abstraction (paper now / cex or onchain later, hard-gated)
  → append-only journal.jsonl → commit → static dashboard rebuild
```

## 1. Design rules

- **Arithmetic stays in code.** The model only answers *fuzzy* questions; every weight,
  threshold and veto is deterministic and lives in `src/`.
- **The judgment layer is pluggable.** It never talks to a vendor directly; it talks to
  `JevClient`, which uses the standard-library HTTP transport and is injectable, so the
  whole layer is unit-tested offline with a fake `post`/`client`.
- **No silent fallback.** A missing key or an unwired model fails loudly
  (`JevUnavailableError`), never as a neutral judgment.
- **Dependency-light.** No pandas/numpy, no LLM SDK; only `pyyaml` (+ optional
  `python-dotenv`) at runtime.

## 2. Jev = arm C (the calibrated core)

Jev is a TypeSafe "System One" model: it does **not** generate text, it returns typed
decisions via three primitives — `choice` (key + probabilities + confidence), `score`
(2–10 scale + distribution + confidence) and `noul` (yes/no as a probability). That maps
1:1 to `JudgmentModel.judge(state, questions) -> {name: Judgment(value, confidence)}`.

Because Jev is trained for **calibration** (RLCD), the project's Brier/ECE machinery can
measure it honestly — which is the whole point of arm C.

## 3. Honesty invariant (enforced in code)

`build_report()` raises unless both a **benchmark series** (BTC buy-and-hold) and a
**cost model** (fees + slippage) are supplied. You cannot show returns without showing
what you are compared against and what it cost.

## 4. Venue abstraction + live gate

`Venue` has `PaperVenue` (simulated wallet, no keys, no network), `CexVenue`
(Kraken/Coinbase keys) and `OnchainVenue` (RPC + signer). Paper ↔ live is a *configuration*
difference, never a code rewrite.

**Live trading requires ALL THREE gates simultaneously:**

1. `TRADING_MODE=live`
2. `ALLOW_LIVE_TRADING=true`
3. `confirm_live=True` passed explicitly in code

`PUBLIC_DEMO=true` makes live trading impossible, unconditionally.

## 5. HITL (human-in-the-loop)

HITL is orthogonal to the live gate and is a **configuration flag** (`HITL`, default on):

- **Paper:** ignored — no capital moves, so the loop may run fully autonomously.
- **Live:** enforced — with `HITL=true` every order is a *proposal* that needs explicit
  human confirmation before submission. The flag can be switched off, but the live gate
  above still applies.

## 6. Secrets

Never in the repo. Live credentials (CEX keys, RPC) come from GitHub Actions secrets or a
local secrets store outside the repo. An on-chain signer is **never** a plaintext private key on a
VPS — use a dedicated hot wallet with minimal funds or a KMS/hardware signer.
