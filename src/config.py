"""Application settings and trading-mode resolution.

All safety-relevant configuration lives here so the guardrails are in one place:
the trading mode, the live-trading gates, the HITL flag and the venue selector.
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from enum import Enum

# python-dotenv is optional: tests run without it and without a .env file.
if importlib.util.find_spec("dotenv") is not None:
    from dotenv import load_dotenv

    load_dotenv()


class TradingMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class VenueKind(str, Enum):
    PAPER = "paper"  # simulated wallet, no keys, no network
    CEX = "cex"  # Kraken/Coinbase API keys
    ONCHAIN = "onchain"  # RPC + signer


class ConfigError(RuntimeError):
    """Raised when the environment contains an invalid or unsafe configuration."""


@dataclass(frozen=True)
class Settings:
    trading_mode: TradingMode
    allow_live_trading: bool
    public_demo: bool
    hitl: bool
    venue: VenueKind
    kraken_api_key: str | None
    kraken_secret_key: str | None
    coinbase_api_key: str | None
    coinbase_secret_key: str | None
    onchain_rpc_url: str | None
    jev_api_key: str | None
    jev_base_url: str
    jev_model: str
    journal_path: str

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env

        raw_mode = (env.get("TRADING_MODE") or "paper").strip().lower()
        try:
            mode = TradingMode(raw_mode)
        except ValueError as exc:
            raise ConfigError(f"TRADING_MODE must be 'paper' or 'live', got {raw_mode!r}") from exc

        raw_venue = (env.get("VENUE") or "paper").strip().lower()
        try:
            venue = VenueKind(raw_venue)
        except ValueError as exc:
            raise ConfigError(
                f"VENUE must be 'paper', 'cex' or 'onchain', got {raw_venue!r}"
            ) from exc

        return cls(
            trading_mode=mode,
            allow_live_trading=_as_bool(env.get("ALLOW_LIVE_TRADING")),
            # Safe default: absent PUBLIC_DEMO is treated as true, so live trading
            # stays impossible unless it is explicitly switched off.
            public_demo=_as_bool(env.get("PUBLIC_DEMO", "true")),
            # Safe default: HITL is ON unless explicitly switched off.
            hitl=_as_bool(env.get("HITL", "true")),
            venue=venue,
            kraken_api_key=env.get("KRAKEN_API_KEY") or None,
            kraken_secret_key=env.get("KRAKEN_SECRET_KEY") or None,
            coinbase_api_key=env.get("COINBASE_API_KEY") or None,
            coinbase_secret_key=env.get("COINBASE_SECRET_KEY") or None,
            onchain_rpc_url=env.get("ONCHAIN_RPC_URL") or None,
            jev_api_key=env.get("JEV_API_KEY") or None,
            jev_base_url=env.get("JEV_BASE_URL") or "https://api.typesafe.ai",
            jev_model=env.get("JEV_MODEL") or "jev",
            # Committed location: the loop appends here and pushes, so the public
            # git history becomes a tamper-evident track record.
            journal_path=env.get("JOURNAL_PATH") or "journal/decisions.jsonl",
        )


def _as_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def load_settings(env: dict[str, str] | None = None) -> Settings:
    return Settings.from_env(env)
