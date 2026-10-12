"""Judgment-layer tests, focused on the Jev (arm C) contract."""

from __future__ import annotations

import pytest
from cadence_core.judgment.base import Judgment
from cadence_core.judgment.jev import (
    JevAdapter,
    JevClient,
    JevError,
    JevUnavailableError,
    choice,
    noul,
    score,
)

from src.config import load_settings


class FakeJevClient:
    """Duck-typed client: returns canned answers keyed by question name."""

    def __init__(self, answers: dict) -> None:
        self.answers = answers
        self.calls: list[tuple] = []

    def decide(self, state, questions):
        self.calls.append((state, questions))
        return self.answers


def test_adapter_is_explicit_stub():
    with pytest.raises(JevUnavailableError):
        JevAdapter().judge({"summary": "x"}, {"direction": choice("d", {"long": "up"})})


def test_adapter_with_predict():
    def predict(snapshot, questions):
        return {"direction": Judgment("direction", "long", 0.8)}

    out = JevAdapter(predict=predict).judge({}, {"direction": choice("d", {"long": "up"})})
    assert out["direction"].value == "long"
    assert out["direction"].confidence == pytest.approx(0.8)


def test_adapter_parses_choice_score_noul():
    questions = {
        "direction": choice("d", {"long": "up", "flat": "no", "short": "down"}),
        "conviction": score("c", ["weak", "strong"]),
        "is_trend": noul("t?"),
    }
    client = FakeJevClient(
        {
            "direction": {"choice": "long", "probabilities": {"long": 0.62}, "confidence": 0.62},
            "conviction": {"score": "strong", "confidence": 0.71},
            "is_trend": {"noul": 0.83},
        }
    )
    out = JevAdapter(client).judge({"summary": "s"}, questions)
    assert out["direction"].value == "long"
    assert out["direction"].confidence == pytest.approx(0.62)
    assert out["conviction"].value == "strong"
    assert out["is_trend"].confidence == pytest.approx(0.83)


def test_client_requires_key():
    settings = load_settings({"JEV_API_KEY": ""})
    with pytest.raises(JevError):
        JevClient(settings).decide({"summary": "x"}, {})


def test_client_posts_to_systemone():
    captured = {}

    def fake_post(url, payload, headers):
        captured["url"] = url
        captured["payload"] = payload
        captured["headers"] = headers
        return {"answers": {"direction": {"choice": "flat", "confidence": 0.5}}}

    settings = load_settings({"JEV_API_KEY": "test-key", "JEV_MODEL": "jev"})
    client = JevClient(settings, post=fake_post)
    out = client.decide({"summary": "x"}, {"direction": choice("d", {"flat": "no"})})
    assert captured["url"].endswith("/v1/systemone")
    assert captured["payload"]["model"] == "jev"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert out["direction"]["choice"] == "flat"
