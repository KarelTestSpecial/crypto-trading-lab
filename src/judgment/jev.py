"""Adapter and client for the Jev "System One" model (arm C).

Jev (TypeSafe AI) does not generate text: it returns typed, calibrated decisions
through three primitives — choice, score and noul (yes/no as a probability).
That is exactly this project's `JudgmentModel` contract, which is why the
Brier/ECE calibration machinery can measure it.

The client talks to the standard-library HTTP transport, so it is swappable and
fully unit-testable offline with a fake `post`. Calling the adapter without a
client or an injected `predict` is a hard, explicit error rather than a silent
neutral judgment.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.config import Settings
from src.data.http import http_post_json
from src.judgment.base import Judgment, JudgmentError, JudgmentModel

# Jev's three question primitives.
CHOICE = "choice"
SCORE = "score"
NOUL = "noul"


class JevError(JudgmentError):
    """Raised when the Jev API is unavailable or misconfigured."""


class JevUnavailableError(JudgmentError):
    """Raised when arm C is used before a Jev client/predict is wired in."""


class JevClient:
    """Minimal TypeSafe System One client over the standard-library HTTP."""

    def __init__(self, settings: Settings, *, post: Callable | None = None) -> None:
        self._base = settings.jev_base_url.rstrip("/")
        self._key = settings.jev_api_key
        self._model = settings.jev_model
        self._post = post or (
            lambda url, payload, headers: http_post_json(url, payload, headers=headers)
        )

    def decide(self, state: Any, questions: dict) -> dict:
        """Send `state` + typed `questions`, return the raw answers keyed by name."""
        if not self._key:
            raise JevError("JEV_API_KEY is required to call Jev")
        payload = {"model": self._model, "state": state, "questions": questions}
        data = self._post(
            f"{self._base}/v1/systemone", payload, {"Authorization": f"Bearer {self._key}"}
        )
        if not isinstance(data, dict):
            raise JevError(f"unexpected Jev response: {data!r}")
        return data.get("answers", data)


def choice(instructions: str, criteria: dict[str, str]) -> dict:
    """A choice question: pick one of up to 255 labelled options."""
    return {"type": CHOICE, "instructions": instructions, "criteria": criteria}


def score(instructions: str, levels: list[str]) -> dict:
    """A score question: place the state on an ordered 2–10 level scale."""
    return {"type": SCORE, "instructions": instructions, "levels": levels}


def noul(statement: str) -> dict:
    """A noul question: a calibrated yes/no returned as a probability in [0, 1]."""
    return {"type": NOUL, "statement": statement}


def _clamp(value: Any) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, x))


def _to_judgment(name: str, question: dict, answer: Any) -> Judgment:
    """Tolerant parser: map one Jev answer to a Judgment (value + confidence)."""
    qtype = question.get("type")
    if isinstance(answer, dict):
        if qtype == CHOICE:
            value = answer.get("choice") or answer.get("value") or ""
            probs = answer.get("probabilities") or {}
            confidence = answer.get("confidence", max(probs.values()) if probs else 0.0)
            return Judgment(name=name, value=str(value), confidence=_clamp(confidence))
        if qtype == SCORE:
            value = answer.get("score", answer.get("value"))
            return Judgment(name=name, value=str(value), confidence=_clamp(answer.get("confidence", 0.0)))
        value = answer.get("noul", answer.get("value", 0.0))
        return Judgment(name=name, value=str(value), confidence=_clamp(value))
    # scalar answer (e.g. a bare probability)
    return Judgment(name=name, value=str(answer), confidence=_clamp(answer))


class JevAdapter(JudgmentModel):
    """Arm C: the calibrated Jev decision model feeding the shared policy engine."""

    def __init__(
        self,
        client: JevClient | None = None,
        *,
        predict: Callable[[dict, dict], dict[str, Judgment]] | None = None,
    ) -> None:
        self._client = client
        self._predict = predict

    def judge(self, snapshot: dict, questions: dict) -> dict[str, Judgment]:
        if self._predict is not None:
            return self._predict(snapshot, questions)
        if self._client is None:
            raise JevUnavailableError(
                "arm C requires a Jev client or a predict callable; inject one when available"
            )
        raw = self._client.decide(snapshot, questions)
        return {
            name: _to_judgment(name, question, raw[name])
            for name, question in questions.items()
            if name in raw
        }
