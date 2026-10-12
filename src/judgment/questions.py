"""The shared judgment questions (typed for the Jev primitives).

One question set serves every judgment model: the offline `RuleBasedJudge` keys on
the question *names*, while `JevAdapter` sends the typed `choice`/`score`/`noul`
objects to Jev. The policy engine only consumes `direction`, whose options are
`up` / `flat` / `down` (see `src.policy.policy`).
"""

from __future__ import annotations

from src.judgment.jev import choice, noul, score

DEFAULT_QUESTIONS: dict[str, dict] = {
    "direction": choice(
        "Over the next bar, will this pair be net up, down or flat?",
        {"up": "higher close", "flat": "broadly unchanged", "down": "lower close"},
    ),
    "conviction": score(
        "How strong is the directional setup?",
        ["very weak", "weak", "neutral", "strong", "very strong"],
    ),
    "is_trend": noul("Is the pair in a sustained uptrend?"),
}
