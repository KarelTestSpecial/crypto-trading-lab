"""Build a judgment model from a name and settings (shared by CLI and loop)."""

from __future__ import annotations

from src.config import Settings
from src.judgment.base import JudgmentError, JudgmentModel
from src.judgment.jev import JevAdapter, JevClient
from src.judgment.rules import RuleBasedJudge


def build_judge(name: str, settings: Settings) -> JudgmentModel:
    key = name.strip().lower()
    if key == "rules":
        return RuleBasedJudge()
    if key == "jev":
        return JevAdapter(JevClient(settings))
    raise JudgmentError(f"unknown judge {name!r}; choose rules or jev")
