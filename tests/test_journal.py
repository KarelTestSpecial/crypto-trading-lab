"""Journal tests: append-only, timestamped, round-trippable."""

from __future__ import annotations

from src.journal.journal import Journal


def test_append_and_read_round_trip(tmp_path):
    journal = Journal(tmp_path / "decisions.jsonl")
    journal.append({"arm": "A", "action": "buy", "symbol": "BTC/USDT"})
    journal.append({"arm": "A", "action": "sell", "symbol": "ETH/USDT"})

    records = list(journal.read())
    assert len(records) == 2
    assert records[0]["symbol"] == "BTC/USDT"
    assert records[1]["symbol"] == "ETH/USDT"
    assert all("ts" in r for r in records)


def test_read_missing_file_is_empty(tmp_path):
    journal = Journal(tmp_path / "nope.jsonl")
    assert list(journal.read()) == []
