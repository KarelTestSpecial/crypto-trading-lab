# journal/

`decisions.jsonl` is the **append-only** decision journal. Each line is one decision:
the input snapshot, the rationale and the outcome.

- **Never mutated** — only appended.
- **Committed** — the daily loop appends and pushes, so the public git history is a
  tamper-evident track record.
- It is also the **calibration data** (Brier/ECE): predictions + confidences vs. outcomes.

The file is intentionally tracked even though `.gitignore` excludes `*.jsonl`
(see the `!journal/decisions.jsonl` exception).
