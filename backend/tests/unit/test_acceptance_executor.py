"""Offline E7 controller contracts; never launch a worker process or provider."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

from evals import acceptance_executor as executor


_MANIFEST = Path(__file__).resolve().parents[3] / "tasks/review-evidence/acceptance-2026-09-19/candidate-manifest.json"


def _write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_approved_manifest_plans_exact_candidate_and_comparator_slots() -> None:
    slots = executor.planned_slots(executor.read_json(_MANIFEST))
    identities = [(row["filing"]["accession_number"], row["arm"], row["draw"]) for row in slots]
    assert len(slots) == len(set(identities)) == 120
    assert Counter(row["arm"] for row in slots) == {"candidate": 90, "comparator": 30}
    assert {row["filing"]["holdout_id"] for row in slots if row["arm"] == "comparator"} == executor.COMPARATOR_SLOTS
    assert {row["draw"] for row in slots} == {1, 2, 3}


def test_child_environment_uses_only_isolated_database_and_explicit_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://production.invalid/forbidden")
    monkeypatch.setenv("OPENAI_API_KEY", "ambient-key-must-not-cross")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "ambient-stripe-must-not-cross")
    invocation = tmp_path / "slot" / "attempt-1"
    config = {"effective_settings": {"OPENAI_BASE_URL": "https://api.deepseek.com/v1"},
              "effective_flags": {"AI_EVIDENCE_SNAP": True}}
    env = executor.child_environment(invocation, config, "explicit-fixture-key")
    assert env["DATABASE_URL"] == "sqlite:///" + str(invocation / "invocation.sqlite3")
    assert env["OPENAI_API_KEY"] == "explicit-fixture-key"
    assert env["STRIPE_SECRET_KEY"] == ""
    assert env["AI_EVIDENCE_SNAP"] == "true"
    assert "production.invalid" not in json.dumps(env)
    assert "ambient-key-must-not-cross" not in json.dumps(env)
    assert "ambient-stripe-must-not-cross" not in json.dumps(env)


def test_slot_meter_retains_anomaly_and_stops_after_settlement_failure(tmp_path: Path) -> None:
    class Ledger:
        def reserve(self, *_):
            return 7

        def settle(self, *_):
            raise ValueError("observed model differs from priced model")

        def snapshot(self):
            return {"requests": 1, "pending": 1}

    stop = tmp_path / "STOP"
    meter = executor.SlotMeter(Ledger(), "H01-candidate-1", tmp_path, stop)
    identity = meter.reserve({"model": "deepseek-flash"}, "summary_primary", "https://api.deepseek.com/v1")
    with pytest.raises(ValueError, match="observed model"):
        meter.settle(identity, {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
                     "unexpected-model", "success")
    accounting = executor.read_json(tmp_path / "provider_accounting.json")
    assert accounting["records"][0]["actual_model"] == "unexpected-model"
    assert accounting["records"][0]["usage"]["completion_tokens"] == 2
    assert accounting["records"][0]["status"] == "settlement_started"
    assert stop.is_file() and meter.failed
    with pytest.raises(executor.BudgetStopped):
        meter.reserve({"model": "deepseek-flash"}, "summary_primary", "https://api.deepseek.com/v1")


def test_missing_human_readiness_never_dispatches(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(executor, "inspect_readiness", lambda *_: {
        "issues": [{"code": "reference_brief_coverage", "detail": "one missing"}]})

    def forbidden(*_, **__):
        raise AssertionError("paid dispatch or frozen checkout reached before human readiness")

    monkeypatch.setattr(executor.subprocess, "run", forbidden)
    monkeypatch.setattr(executor, "frozen_checkout", forbidden)
    args = SimpleNamespace(command="run-slot", manifest=str(tmp_path / "manifest.json"),
                           prerequisites=str(tmp_path / "prerequisites.json"), archive=tmp_path,
                           slot="H01-candidate-1", programme=tmp_path / "programme")
    with pytest.raises(ValueError, match="readiness is incomplete"):
        executor.run_slot(args)


def test_interrupted_slot_refuses_controller_redraw(tmp_path: Path, monkeypatch) -> None:
    filing = {"holdout_id": "H02", "accession_number": "0000000001-26-000001"}
    manifest = _write(tmp_path / "manifest.json", {"filings": [filing]})
    config = _write(tmp_path / "config.json", {"source_commit": "a" * 40})
    pricing = _write(tmp_path / "pricing.json", {
        "uncached_input_per_million": "0.01", "max_output_per_million": "0.02"})
    prerequisites = _write(tmp_path / "prerequisites.json", {
        "candidate_config": {"path": config.name}, "pricing": {"path": pricing.name},
        "budget_control": {"full_run_worst_case_usd": "10"}})
    monkeypatch.setattr(executor, "inspect_readiness", lambda *_: {
        "issues": [], "config_sha256": {"candidate": executor.sha(config)}})
    monkeypatch.setattr(executor, "frozen_checkout", lambda *_: tmp_path)
    monkeypatch.setenv("E7_GENERATOR_API_KEY", "offline-fixture-only")
    monkeypatch.setattr(executor, "BudgetLedger", lambda *_: SimpleNamespace(
        snapshot=lambda: {"pending": 0, "stop_reason": None}))

    def forbidden(*_, **__):
        raise AssertionError("interrupted slot attempted to relaunch worker")

    monkeypatch.setattr(executor.subprocess, "run", forbidden)
    programme = tmp_path / "programme"
    programme.mkdir()
    with sqlite3.connect(programme / "budget.sqlite3") as db:
        db.execute("CREATE TABLE reservations (slot_id TEXT)")
        db.execute("INSERT INTO reservations VALUES ('development-smoke')")
        db.execute("CREATE TABLE slots (id TEXT PRIMARY KEY, config_sha TEXT, status TEXT)")
        db.execute("INSERT INTO slots VALUES ('H02-candidate-1', ?, 'running')", (executor.sha(config),))
    args = SimpleNamespace(command="run-slot", manifest=str(manifest), prerequisites=str(prerequisites),
                           archive=tmp_path, slot="H02-candidate-1", programme=programme)
    with pytest.raises(executor.BudgetStopped, match="failed or interrupted slot"):
        executor.run_slot(args)


@pytest.mark.asyncio
async def test_worker_request_cannot_reenter_claimed_slot(tmp_path: Path, monkeypatch) -> None:
    """A retained request is evidence, not a second authorization to generate."""
    from evals import acceptance_worker

    config = _write(tmp_path / "config.json", {"source_commit": "a" * 40})
    ledger = tmp_path / "budget.sqlite3"
    invocation = tmp_path / "attempt-1"
    invocation.mkdir()
    request = _write(tmp_path / "request.json", {
        "manifest": str(tmp_path / "manifest.json"), "archive": str(tmp_path),
        "prerequisites": str(tmp_path / "prerequisites.json"), "config_path": str(config),
        "config_sha256": executor.sha(config), "slot_id": "H01-candidate-1",
        "ledger": str(ledger), "pricing": {}, "stop_file": str(tmp_path / "STOP"),
        "invocation_dir": str(invocation), "filing": {}, "config": {}, "smoke_mode": False})
    with sqlite3.connect(ledger) as db:
        db.execute("CREATE TABLE slots (id TEXT PRIMARY KEY, config_sha TEXT, status TEXT, request_sha TEXT)")
        db.execute("INSERT INTO slots VALUES ('H01-candidate-1', ?, 'running', ?)",
                   (executor.sha(config), executor.sha(request)))
    monkeypatch.setattr(executor, "inspect_readiness", lambda *_: {"issues": []})
    monkeypatch.setattr(executor, "BudgetLedger", lambda *_: object())
    calls = []

    async def fake_invocation(*_):
        calls.append("generated")
        return {"status": "complete"}

    monkeypatch.setattr(acceptance_worker, "run_invocation", fake_invocation)
    await executor.worker(SimpleNamespace(request=str(request)))
    with pytest.raises((ValueError, executor.BudgetStopped), match="claim|slot"):
        await executor.worker(SimpleNamespace(request=str(request)))
    assert calls == ["generated"]


def test_tampered_worker_request_cannot_take_durable_claim(tmp_path: Path) -> None:
    ledger = tmp_path / "budget.sqlite3"
    request = _write(tmp_path / "request.json", {
        "ledger": str(ledger), "slot_id": "H01-candidate-1", "config_sha256": "a" * 64})
    original_hash = executor.sha(request)
    with sqlite3.connect(ledger) as db:
        db.execute("CREATE TABLE slots (id TEXT PRIMARY KEY, config_sha TEXT, status TEXT, request_sha TEXT)")
        db.execute("INSERT INTO slots VALUES ('H01-candidate-1', ?, 'running', ?)",
                   ("a" * 64, original_hash))
    tampered = dict(executor.read_json(request), slot_id="H01-candidate-1", extra_provider_call=True)
    _write(request, tampered)
    with pytest.raises(executor.BudgetStopped, match="claim|identity"):
        executor.claim_worker(request, tampered)
    with sqlite3.connect(ledger) as db:
        assert db.execute("SELECT status FROM slots").fetchone() == ("running",)
