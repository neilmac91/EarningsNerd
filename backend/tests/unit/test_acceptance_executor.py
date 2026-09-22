"""Offline E7 controller contracts; never launch a worker process or provider."""

from __future__ import annotations

import json
import sqlite3
import subprocess
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

from evals import acceptance_executor as executor


_MANIFEST = Path(__file__).resolve().parents[3] / "tasks/review-evidence/acceptance-2026-09-19/candidate-manifest.json"


def _write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _git(root: Path, *arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=root, text=True).strip()


def _complete_frozen_config() -> dict:
    from evals.acceptance_worker import REQUIRED_FROZEN_SETTINGS
    settings = {key: "" for key in REQUIRED_FROZEN_SETTINGS if key != "AI_EVIDENCE_SNAP"}
    settings["OPENAI_BASE_URL"] = "https://api.deepseek.com/v1"
    settings["AI_DEFAULT_MODEL"] = "deepseek-chat"
    settings["RECOVERY_MAX_CONCURRENCY"] = 3
    settings["AI_SUMMARY_THINKING_MAX_TOKENS"] = 24000
    return {"base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat",
            "effective_settings": settings, "effective_flags": {"AI_EVIDENCE_SNAP": True}}


def test_frozen_checkout_requires_reviewed_meter_bytes_in_both_trees(tmp_path: Path, monkeypatch) -> None:
    checkout, executing = tmp_path / "checkout", tmp_path / "executing"
    checkout.mkdir()
    _git(checkout, "init", "-q")
    for relative in executor.MEASUREMENT_FILES[:-1]:
        path = checkout / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"reviewed {relative}", encoding="utf-8")
    requirements = checkout / "backend/requirements.txt"
    requirements.write_text("synthetic dependency lock\n", encoding="utf-8")

    def commit(message: str) -> str:
        _git(checkout, "add", ".")
        _git(checkout, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
             "commit", "-qm", message)
        return _git(checkout, "rev-parse", "HEAD")

    missing_commit = commit("missing provider hook")
    hook = checkout / executor.MEASUREMENT_FILES[-1]
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("reviewed provider hook", encoding="utf-8")
    reviewed_commit = commit("complete reviewed instrumentation")
    for relative in executor.MEASUREMENT_FILES:
        destination = executing / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((checkout / relative).read_bytes())
    monkeypatch.setattr(executor, "__file__", str(executing / "backend/evals/acceptance_executor.py"))
    config = {"checkout_path": str(checkout), "source_commit": reviewed_commit,
              "dependency_lock_sha256": executor.sha(requirements)}
    assert executor.frozen_checkout(config, reviewed_commit) == checkout
    with pytest.raises(ValueError, match="reviewed instrumentation lacks"):
        executor.frozen_checkout(config, missing_commit)

    (executing / executor.MEASUREMENT_FILES[0]).write_text("unreviewed controller", encoding="utf-8")
    with pytest.raises(ValueError, match="executing controller differs"):
        executor.frozen_checkout(config, reviewed_commit)
    (executing / executor.MEASUREMENT_FILES[0]).write_bytes(
        (checkout / executor.MEASUREMENT_FILES[0]).read_bytes())
    hook.write_text("drifted provider hook", encoding="utf-8")
    config["source_commit"] = commit("candidate checkout meter drift")
    with pytest.raises(ValueError, match="frozen checkout differs"):
        executor.frozen_checkout(config, reviewed_commit)


def test_verified_runtime_rejects_mismatched_or_unsupported_lock(tmp_path: Path, monkeypatch) -> None:
    lock = tmp_path / "requirements.txt"
    lock.write_text("alpha-package==1.2.3\nbeta_pkg==4.5\n", encoding="utf-8")
    distributions = [SimpleNamespace(metadata={"Name": "Alpha_Package"}, version="1.2.3"),
                     SimpleNamespace(metadata={"Name": "beta-pkg"}, version="4.5")]
    monkeypatch.setattr(executor.metadata, "distributions", lambda: distributions)
    receipt = executor.verified_runtime(lock)
    assert receipt["interpreter"] == executor.sys.executable
    assert receipt["python_version"] == executor.platform.python_version()
    assert receipt["dependency_lock_sha256"] == executor.sha(lock)
    assert len(receipt["distributions_sha256"]) == 64
    assert receipt["pinned_distribution_count"] == 2

    distributions[1] = SimpleNamespace(metadata={"Name": "beta-pkg"}, version="4.6")
    with pytest.raises(ValueError, match="installed distributions differ"):
        executor.verified_runtime(lock)
    distributions.pop()
    with pytest.raises(ValueError, match="installed distributions differ"):
        executor.verified_runtime(lock)
    lock.write_text("alpha-package==1.2.3\n-r other.txt\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported dependency lock entry"):
        executor.verified_runtime(lock)


def test_verified_runtime_requires_compiled_python_version(tmp_path: Path, monkeypatch) -> None:
    lock = tmp_path / "requirements.txt"
    lock.write_text("# This file is autogenerated by pip-compile with Python 0.0\nalpha==1.0\n",
                    encoding="utf-8")
    monkeypatch.setattr(executor.metadata, "distributions", lambda: [])
    with pytest.raises(ValueError, match="differs from dependency lock Python"):
        executor.verified_runtime(lock)


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
    config = _complete_frozen_config()
    env = executor.child_environment(invocation, config, "explicit-fixture-key")
    assert env["DATABASE_URL"] == "sqlite:///" + str(invocation / "invocation.sqlite3")
    assert env["OPENAI_API_KEY"] == "explicit-fixture-key"
    assert env["STRIPE_SECRET_KEY"] == ""
    assert env["AI_EVIDENCE_SNAP"] == "true"
    assert env["RECOVERY_MAX_CONCURRENCY"] == "3"
    assert "production.invalid" not in json.dumps(env)
    assert "ambient-key-must-not-cross" not in json.dumps(env)
    assert "ambient-stripe-must-not-cross" not in json.dumps(env)
    for key in ("PYTHONPATH", "PYTHONHOME", "PATH", "DYLD_INSERT_LIBRARIES"):
        contaminated = dict(config, effective_flags={**config["effective_flags"], key: "/untrusted"})
        with pytest.raises(ValueError, match="unsupported process"):
            executor.child_environment(invocation, contaminated, "explicit-fixture-key")


@pytest.mark.parametrize("fault, message", [
    ("missing", "missing required frozen settings"),
    ("unsupported", "unsupported process or credential control"),
    ("shape", "non-empty objects"),
    ("base_url", "provider base URL differs"),
    ("primary_model", "primary model differs"),
    ("recovery_model", "recovery/verifier model differs"),
    ("fast_model", "recovery/verifier model differs"),
    ("fallback_model", "fallback provider route must be blank"),
    ("fallback_base_url", "fallback provider route must be blank"),
    ("fallback_whitespace", "fallback provider route must be blank"),
    ("recovery_concurrency", "recovery concurrency must be a positive integer"),
    ("arm_concurrency", "recovery concurrency differs between acceptance arms"),
    ("thinking", "thinking mode is unsupported"),
    ("thinking_ceiling", "thinking token ceiling must match"),
    ("schema_bool", "fail the application Settings schema"),
])
def test_invalid_frozen_settings_stop_before_programme_state(
    tmp_path: Path, monkeypatch, fault: str, message: str
) -> None:
    filing = {"holdout_id": "H02", "accession_number": "0000000001-26-000001"}
    manifest = _write(tmp_path / "manifest.json", {"filings": [filing]})
    config = _complete_frozen_config()
    if fault == "schema_bool":
        from app.config import settings
        from evals.acceptance_worker import REQUIRED_FROZEN_SETTINGS
        config["effective_settings"].update({
            key: getattr(settings, key) for key in REQUIRED_FROZEN_SETTINGS
            if key not in config["effective_flags"]
        })
        config["effective_settings"].update(
            OPENAI_BASE_URL=config["base_url"], AI_DEFAULT_MODEL=config["model"],
            AI_FALLBACK_MODEL="", AI_FALLBACK_BASE_URL="",
            AI_FAST_MODEL="", AI_SECTION_RECOVERY_MODEL="",
            AI_SUMMARY_THINKING_EFFORT="",
        )
        executor.preflight_frozen_settings(config, Path(__file__).resolve().parents[3])
        config["effective_settings"]["USE_STRUCTURED_OUTPUT"] = "definitely-not-a-bool"
    if fault == "missing":
        del config["effective_settings"]["OPENAI_BASE_URL"]
    elif fault == "unsupported":
        config["effective_flags"]["PYTHONPATH"] = "/untrusted"
    elif fault == "shape":
        config["effective_flags"] = []
    elif fault == "base_url":
        config["effective_settings"]["OPENAI_BASE_URL"] = "https://other.invalid/v1"
    elif fault == "primary_model":
        config["effective_settings"]["AI_DEFAULT_MODEL"] = "unpriced-model"
    elif fault == "recovery_model":
        config["effective_settings"]["AI_SECTION_RECOVERY_MODEL"] = " unpriced-model "
    elif fault == "fast_model":
        config["effective_settings"]["AI_FAST_MODEL"] = " unpriced-model "
    elif fault == "fallback_model":
        config["effective_settings"]["AI_FALLBACK_MODEL"] = "unpriced-model"
    elif fault == "fallback_whitespace":
        config["effective_settings"]["AI_FALLBACK_MODEL"] = " "
    elif fault == "recovery_concurrency":
        config["effective_settings"]["RECOVERY_MAX_CONCURRENCY"] = 0
    elif fault == "thinking":
        config["effective_settings"]["AI_SUMMARY_THINKING_EFFORT"] = "high"
    elif fault == "thinking_ceiling":
        config["effective_settings"]["AI_SUMMARY_THINKING_MAX_TOKENS"] = 240000
    elif fault in {"arm_concurrency", "schema_bool"}:
        pass
    else:
        config["effective_settings"]["AI_FALLBACK_BASE_URL"] = "https://other.invalid/v1"
    config_path = _write(tmp_path / "config.json", config)
    comparator = _complete_frozen_config()
    if fault == "arm_concurrency":
        comparator["effective_settings"]["RECOVERY_MAX_CONCURRENCY"] = 2
    comparator_path = _write(tmp_path / "comparator.json", comparator)
    prerequisites = _write(tmp_path / "prerequisites.json", {
        "candidate_config": {"path": config_path.name},
        "comparator_config": {"path": comparator_path.name},
        "budget_control": {"reviewed_commit": "unused-in-offline-test"}})
    monkeypatch.setattr(executor, "inspect_readiness", lambda *_: {"issues": []})

    def forbidden(*_, **__):
        raise AssertionError("invalid frozen config reached checkout, ledger or child dispatch")

    if fault == "schema_bool":
        monkeypatch.setattr(executor, "frozen_checkout", lambda *_: Path(__file__).resolve().parents[3])
        monkeypatch.setattr(executor, "verified_runtime", lambda *_: {})
    else:
        monkeypatch.setattr(executor, "frozen_checkout", forbidden)
    monkeypatch.setattr(executor, "BudgetLedger", forbidden)
    if fault != "schema_bool":
        monkeypatch.setattr(executor.subprocess, "run", forbidden)
    programme = tmp_path / "programme"
    args = SimpleNamespace(command="run-slot", manifest=str(manifest),
                           prerequisites=str(prerequisites), archive=tmp_path,
                           slot="H02-candidate-1", programme=programme)
    with pytest.raises(ValueError, match=message):
        executor.run_slot(args)
    assert not programme.exists()
    assert not (programme / "budget.sqlite3").exists()
    assert not (programme / "H02-candidate-1").exists()


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
    config = _write(tmp_path / "config.json", {"source_commit": "a" * 40,
                                               **_complete_frozen_config()})
    pricing = _write(tmp_path / "pricing.json", {
        "uncached_input_per_million": "0.01", "max_output_per_million": "0.02"})
    prerequisites = _write(tmp_path / "prerequisites.json", {
        "candidate_config": {"path": config.name}, "comparator_config": {"path": config.name},
        "pricing": {"path": pricing.name},
        "budget_control": {"full_run_worst_case_usd": "10", "reviewed_commit": "a" * 40}})
    monkeypatch.setattr(executor, "inspect_readiness", lambda *_: {
        "issues": [], "config_sha256": {"candidate": executor.sha(config)}})
    monkeypatch.setattr(executor, "frozen_checkout", lambda *_: tmp_path)
    monkeypatch.setattr(executor, "verified_runtime", lambda *_: {"distributions_sha256": "fixture"})
    monkeypatch.setattr(executor, "preflight_frozen_settings", lambda *_: None)
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
    # A legacy completed ledger cannot be resumed and retroactively sealed either.
    with sqlite3.connect(programme / "budget.sqlite3") as db:
        db.execute("UPDATE slots SET status='completed'")
    with pytest.raises(executor.BudgetStopped, match="lacks durable completion seals"):
        executor.run_slot(args)
    assert not (programme / "H02-candidate-1").exists()


@pytest.mark.asyncio
async def test_worker_request_cannot_reenter_claimed_slot(tmp_path: Path, monkeypatch) -> None:
    """A retained request is evidence, not a second authorization to generate."""
    from evals import acceptance_worker

    config = _write(tmp_path / "config.json", {"source_commit": "a" * 40})
    ledger = tmp_path / "budget.sqlite3"
    prerequisites = _write(tmp_path / "prerequisites.json", {
        "budget_control": {"reviewed_commit": "a" * 40}})
    invocation = tmp_path / "attempt-1"
    invocation.mkdir()
    request = _write(tmp_path / "request.json", {
        "manifest": str(tmp_path / "manifest.json"), "archive": str(tmp_path),
        "prerequisites": str(prerequisites), "config_path": str(config),
        "config_sha256": executor.sha(config), "slot_id": "H01-candidate-1",
        "ledger": str(ledger), "pricing": {}, "stop_file": str(tmp_path / "STOP"),
        "invocation_dir": str(invocation), "filing": {}, "config": {}, "smoke_mode": False,
        "runtime": {"distributions_sha256": "fixture"}})
    with sqlite3.connect(ledger) as db:
        db.execute("CREATE TABLE slots (id TEXT PRIMARY KEY, config_sha TEXT, status TEXT, request_sha TEXT)")
        db.execute("INSERT INTO slots VALUES ('H01-candidate-1', ?, 'running', ?)",
                   (executor.sha(config), executor.sha(request)))
    monkeypatch.setattr(executor, "inspect_readiness", lambda *_: {"issues": []})
    monkeypatch.setattr(executor, "BudgetLedger", lambda *_: object())
    monkeypatch.setattr(executor, "frozen_checkout", lambda *_: tmp_path)
    monkeypatch.setattr(executor, "verified_runtime", lambda *_: {"distributions_sha256": "drifted"})
    calls = []

    async def fake_invocation(*_):
        calls.append("generated")
        return {"status": "complete"}

    monkeypatch.setattr(acceptance_worker, "run_invocation", fake_invocation)
    with pytest.raises(ValueError, match="installed distributions changed"):
        await executor.worker(SimpleNamespace(request=str(request)))
    with sqlite3.connect(ledger) as db:
        assert db.execute("SELECT status FROM slots").fetchone() == ("running",)
    assert not calls
    monkeypatch.setattr(executor, "verified_runtime", lambda *_: {"distributions_sha256": "fixture"})
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
