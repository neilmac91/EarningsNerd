"""``export_e8_state.py`` preserves every stop as evidence and says whether it is a checkpoint.

The judging container is ephemeral, so the committed export is the only durable record of the
E8 guard (README.md, sole-guard recovery). These tests build synthetic guards in each lifecycle
stage and check the behaviours the 23 September readiness review found missing: a partial setup
or unmatched receipt is exported rather than refused (a refusal lost the evidence, and the kit
forbids retrying a refused step), a readback that records the absent ``active`` key as null is
read as "no owners" only when the live key is absent, the copy is verified against its source,
empty ``.pending-*`` markers are listed, and ``git add`` keeps the per-slot ``run.log`` files.
Nothing here touches a real guard, bundle or CLI.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "tasks" / "fable-e8-repin-2026-09-22" / "export_e8_state.py"


@pytest.fixture
def export(monkeypatch):
    spec = importlib.util.spec_from_file_location("export_e8_state_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value if isinstance(value, str) else json.dumps(value, indent=2) + "\n")


def make_bundle(root: Path, stage: str = "pristine", *, active: dict | None = None) -> Path:
    """A bundle whose guard is pristine, template-configured or initialized (count 287)."""
    bundle = root.resolve() / "bundle"
    guard = bundle / "e8" / "guard"
    initialized = stage == "initialized"
    state = {"accounting_reconciled": initialized, "real_cli_invocations": 287 if initialized else 0,
             "stop_reason": None, "completed": []}
    if active is not None:
        state["active"] = active
    _write(guard / "state.json", state)
    _write(guard / "config.json", {"enabled": initialized, "real_cli": "/opt/claude-code/bin/claude",
                                   "state_path": str(guard / "state.json"), "ceiling": 601})
    _write(guard / "TEMPLATE.json", {"never_initialized": True})
    _write(guard / "sha256.txt", "0" * 64 + "  claude\n")
    if stage in ("template-configured", "initialized"):
        _write(guard / "template-configuration.json", {"status": "complete"})
    if initialized:
        _write(guard / "initialization.json", {"status": "complete", "prior_count": 287,
                                               "state_path": str(guard / "state.json")})
    _write(bundle / "stages" / "e8" / "index.json", {"packets": []})
    return bundle


def attestation(export, guard: Path) -> dict:
    return {"schema": export.ATTESTATION_SCHEMA, "operator": "test operator",
            "observed_at_utc": "2026-09-23T13:21:22+00:00", "prior_count": 287,
            **export.SEALED_HASHES, "guard_state_path": str(guard / "state.json"),
            "no_untracked_e8_or_probe_calls": True, "sole_persistent_guard": True,
            "exclusive_e8_dispatch_during_continuation": True}


def readback(guard: Path, *, active=None, completed=None) -> dict:
    """The launch kit's readback.json for an initialized guard with no E8 call yet."""
    state = json.loads((guard / "state.json").read_text())
    return {"observed_at_utc": "2026-09-23T13:30:00Z", "guard_dir": str(guard), "config_enabled": True,
            "state_accounting_reconciled": True, "state_real_cli_invocations": state["real_cli_invocations"],
            "state_stop_reason": None, "state_active": {} if active is None else active,
            "state_completed": [] if completed is None else completed,
            "initialization_json_present": True, "template_configuration_json_present": True,
            "template_marker_never_initialized": True, "cli_version_observed": "2.1.280 (Claude Code)"}


def run(export, monkeypatch, bundle: Path, out: Path, receipts: Path | None = None) -> tuple[int, dict]:
    argv = ["export_e8_state.py", "--bundle", str(bundle), "--out", str(out)]
    if receipts is not None:
        argv += ["--receipts", str(receipts)]
    monkeypatch.setattr(sys, "argv", argv)
    code = export.main()
    return code, json.loads((out / "export-summary.json").read_text())


def test_a_pristine_guard_exports_as_evidence_not_as_a_checkpoint(export, monkeypatch, tmp_path) -> None:
    bundle = make_bundle(tmp_path)
    code, summary = run(export, monkeypatch, bundle, tmp_path / "out")
    assert code == 0
    assert summary["guard_stage"] == "pristine" and summary["recovery_eligible"] is False
    assert any("never initialized" in b for b in summary["recovery_blockers"])
    assert sorted(p.name for p in (tmp_path / "out" / "e8" / "guard").iterdir()) == [
        "TEMPLATE.json", "config.json", "sha256.txt", "state.json"]


def test_a_template_configured_stop_is_exported_not_refused(export, monkeypatch, tmp_path) -> None:
    """--configure-template succeeded, --prior-count refused: the kit says stop, README says export."""
    bundle = make_bundle(tmp_path, "template-configured")
    code, summary = run(export, monkeypatch, bundle, tmp_path / "out")
    assert code == 0
    assert summary["guard_stage"] == "template-configured"
    assert (tmp_path / "out" / "e8" / "guard" / "template-configuration.json").is_file()
    assert "guard file missing for a template-configured guard: initialization.json" in summary["recovery_blockers"]
    assert summary["recovery_eligible"] is False


def test_an_initialized_guard_with_matching_receipts_is_an_eligible_checkpoint(export, monkeypatch, tmp_path) -> None:
    bundle = make_bundle(tmp_path, "initialized")
    guard = bundle / "e8" / "guard"
    receipts = tmp_path / "receipts"
    _write(receipts / "e8-attestation-20260923T132122Z.json", attestation(export, guard))
    _write(receipts / "readback-post-run.json", readback(guard))
    out = tmp_path / "out"
    code, summary = run(export, monkeypatch, bundle, out, receipts)
    assert code == 0
    assert summary["recovery_blockers"] == [] and summary["recovery_eligible"] is True
    assert summary["destination_verified"] is True and summary["source_unchanged"] is True
    assert summary["inventory_sha256"] == hashlib.sha256((out / "sha256-inventory.json").read_bytes()).hexdigest()
    inventory = json.loads((out / "sha256-inventory.json").read_text())
    assert {k for k in inventory if k.startswith("e8/guard/")} == {f"e8/guard/{n}" for n in export.GUARD_FILES}
    for rel, entry in inventory.items():
        assert hashlib.sha256((out / rel).read_bytes()).hexdigest() == entry["sha256"]
        assert (out / rel).stat().st_size == entry["bytes"]


def test_an_initialized_guard_without_receipts_is_exported_with_named_blockers(export, monkeypatch, tmp_path) -> None:
    bundle = make_bundle(tmp_path, "initialized")
    receipts = tmp_path / "receipts"
    receipts.mkdir()
    code, summary = run(export, monkeypatch, bundle, tmp_path / "out", receipts)
    assert code == 0 and summary["recovery_eligible"] is False
    assert "receipts lack a valid attestation bound to the live guard" in summary["recovery_blockers"]
    assert "receipts lack a valid readback bound to the live guard" in summary["recovery_blockers"]


def test_a_null_active_readback_counts_as_no_owners_only_when_the_live_key_is_absent(export, tmp_path) -> None:
    bundle = make_bundle(tmp_path, "initialized")
    guard = bundle / "e8" / "guard"
    observation = export.guard_observation(guard)
    assert export.valid_readback(readback(guard, active=None) | {"state_active": None}, guard, observation)
    assert export.valid_readback(readback(guard, active={}), guard, observation)

    owned = make_bundle(tmp_path / "owned", "initialized", active={"123": {"pid": 123}})
    owned_guard = owned / "e8" / "guard"
    owned_observation = export.guard_observation(owned_guard)
    assert not export.valid_readback(readback(owned_guard) | {"state_active": None}, owned_guard, owned_observation)
    assert export.valid_readback(readback(owned_guard, active={"123": {"pid": 123}}), owned_guard, owned_observation)


def test_terminal_markers_are_listed_and_block_recovery(export, monkeypatch, tmp_path) -> None:
    bundle = make_bundle(tmp_path, "initialized")
    guard = bundle / "e8" / "guard"
    stages = bundle / "stages" / "e8"
    (stages / ".pending-001-KO-1-Q-run0-abc").mkdir()  # killed between mkdir and owner.json
    _write(stages / "STOP.supplement.json", {"failure": "Harness nonzero exit"})
    _write(stages / "failed" / ".pending-002-KO-2-Q-run0-def" / "run.log", "STDOUT\n")
    receipts = tmp_path / "receipts"
    _write(receipts / "attestation.json", attestation(export, guard))
    _write(receipts / "readback.json", readback(guard))
    out = tmp_path / "out"
    code, summary = run(export, monkeypatch, bundle, out, receipts)
    assert code == 0
    assert summary["pending_markers"] == [{"name": ".pending-001-KO-1-Q-run0-abc", "empty": True}]
    assert ".pending-001-KO-1-Q-run0-abc" in summary["directories"]
    assert summary["stop_files"] == ["STOP.supplement.json"]
    assert summary["failed_entries"] == [".pending-002-KO-2-Q-run0-def"]
    assert summary["recovery_eligible"] is False
    assert (out / "stages" / "e8" / "failed" / ".pending-002-KO-2-Q-run0-def" / "run.log").is_file()


def test_a_copy_that_differs_from_its_source_keeps_the_evidence_and_fails(export, monkeypatch, tmp_path) -> None:
    bundle = make_bundle(tmp_path, "initialized")
    real_copy = export.shutil.copy2

    def corrupting_copy(src, dst, *args, **kwargs):
        result = real_copy(src, dst, *args, **kwargs)
        if Path(src).name == "index.json":
            Path(dst).write_text("{}")
        return result

    monkeypatch.setattr(export.shutil, "copy2", corrupting_copy)
    out = tmp_path / "out"
    code, summary = run(export, monkeypatch, bundle, out)
    assert code == 1 and out.is_dir()
    assert summary["destination_verified"] is False
    assert [m["path"] for m in summary["mismatches"]] == ["stages/e8/index.json"]
    assert "copied files differ from their source (see mismatches)" in summary["recovery_blockers"]


def test_a_source_that_changes_during_export_is_recorded(export, monkeypatch, tmp_path) -> None:
    bundle = make_bundle(tmp_path, "initialized")
    real_tree = export.copy_tree

    def writer_during_export(src, *args, **kwargs):
        real_tree(src, *args, **kwargs)
        if src.name == "e8":
            _write(src / "execution-ledger.supplement.jsonl", '{"slot": "late"}\n')

    monkeypatch.setattr(export, "copy_tree", writer_during_export)
    code, summary = run(export, monkeypatch, bundle, tmp_path / "out")
    assert code == 1
    assert summary["source_unchanged"] is False
    assert summary["source_changes"] == ["stages/e8/execution-ledger.supplement.jsonl"]


def test_only_structural_problems_refuse(export, monkeypatch, tmp_path) -> None:
    bundle = make_bundle(tmp_path)
    (tmp_path / "exists").mkdir()
    monkeypatch.setattr(sys, "argv", ["x", "--bundle", str(bundle), "--out", str(tmp_path / "exists")])
    with pytest.raises(SystemExit, match="output directory exists"):
        export.main()
    (bundle / "stages" / "e8" / "index.json").unlink()
    monkeypatch.setattr(sys, "argv", ["x", "--bundle", str(bundle), "--out", str(tmp_path / "new")])
    with pytest.raises(SystemExit, match="no index.json"):
        export.main()
    assert not (tmp_path / "new").exists()


EXPORTED_LOGS = (
    "tasks/review-evidence/e8-fable-state-20260923T160000Z/stages/e8/slots/001-KO-1-Q-run0/run.log",
    "tasks/review-evidence/e8-fable-state-20260923T160000Z/stages/e8/failed/.pending-002-x-abc/run.log",
    "tasks/review-evidence/e8-fable-state-20260923T160000Z/receipts/e8-execute-20260923T160000Z.log",
)


@pytest.mark.parametrize("path", EXPORTED_LOGS)
def test_git_keeps_the_exported_logs(path: str) -> None:
    """The repository ignores *.log; a silent `git add` drop would leave the inventory unmatched."""
    # Exit status 1 means "not ignored"; -v would also report a matching negation as a hit.
    result = subprocess.run(["git", "-C", str(REPO_ROOT), "check-ignore", "--no-index", "-q", path])
    assert result.returncode == 1, f"{path} would be dropped by `git add` (git check-ignore exit {result.returncode})"


def test_the_log_exception_is_limited_to_committed_evidence() -> None:
    result = subprocess.run(["git", "-C", str(REPO_ROOT), "check-ignore", "--no-index", "-q", "backend/server.log"])
    assert result.returncode == 0, "the *.log ignore rule must still cover logs outside tasks/review-evidence"


def matching_readback(guard: Path) -> dict:
    """A post-run readback equal to the live guard, so only the case under test can block."""
    state = json.loads((guard / "state.json").read_text())
    config = json.loads((guard / "config.json").read_text())
    return {"observed_at_utc": "2026-09-23T18:00:00Z", "guard_dir": str(guard),
            "config_enabled": config.get("enabled"), "state_accounting_reconciled": state.get("accounting_reconciled"),
            "state_real_cli_invocations": state.get("real_cli_invocations"), "state_stop_reason": state.get("stop_reason"),
            "state_active": state.get("active", {}), "state_completed": state.get("completed", []),
            "initialization_json_present": (guard / "initialization.json").is_file(),
            "template_configuration_json_present": (guard / "template-configuration.json").is_file(),
            "template_marker_never_initialized": True, "cli_version_observed": "2.1.280 (Claude Code)"}


GUARD_REFUSALS = [
    ("ceiling exhausted", {"real_cli_invocations": 601, "completed": [{"invocation": n} for n in range(288, 602)]},
     {}, "outside 287..600"),
    ("quota latch on a completed call", {"real_cli_invocations": 288, "completed": [{"invocation": 288, "quota": True}]},
     {}, "quota or owner-loss latch on invocations [288]"),
    ("owner loss on a completed call", {"real_cli_invocations": 288, "completed": [{"invocation": 288, "owner_lost": True}]},
     {}, "quota or owner-loss latch on invocations [288]"),
    ("empty stop latch", {"stop_reason": ""}, {}, "guard stop latch set: ''"),
    ("malformed owner records", {"active": []}, {}, "active or malformed owner records"),
    ("initialization recorded but guard left disabled", {}, {"enabled": False}, "not enabled and reconciled"),
]


@pytest.mark.parametrize(("name", "state_change", "config_change", "blocker"), GUARD_REFUSALS,
                         ids=[case[0] for case in GUARD_REFUSALS])
def test_a_guard_the_sealed_tools_would_refuse_is_never_an_eligible_checkpoint(
        export, monkeypatch, tmp_path, name, state_change, config_change, blocker) -> None:
    """Mirrors guard_setup.validate_guard, e8_resume's quota/owner-loss latch and README condition 6."""
    bundle = make_bundle(tmp_path, "initialized")
    guard = bundle / "e8" / "guard"
    for file_name, change in (("state.json", state_change), ("config.json", config_change)):
        _write(guard / file_name, {**json.loads((guard / file_name).read_text()), **change})
    receipts = tmp_path / "receipts"
    _write(receipts / "attestation.json", attestation(export, guard))
    _write(receipts / "readback.json", matching_readback(guard))
    code, summary = run(export, monkeypatch, bundle, tmp_path / "out", receipts)
    assert code == 0 and summary["receipt_classes"] == {"attestation": True, "readback": True}
    assert summary["recovery_eligible"] is False
    assert any(blocker in b for b in summary["recovery_blockers"]), summary["recovery_blockers"]


def test_a_file_that_vanishes_during_export_is_recorded_not_a_crash(export, monkeypatch, tmp_path) -> None:
    """A finishing slot renames its .pending-* directory: the export still writes its summary."""
    bundle = make_bundle(tmp_path, "initialized")
    owner = bundle / "stages" / "e8" / ".pending-001-KO-1-Q-run0-abc" / "owner.json"
    _write(owner, {"slot": "001"})
    real_copy = export.shutil.copy2

    def vanishing_copy(src, dst, *args, **kwargs):
        if Path(src) == owner:
            owner.unlink()
        return real_copy(src, dst, *args, **kwargs)

    monkeypatch.setattr(export.shutil, "copy2", vanishing_copy)
    code, summary = run(export, monkeypatch, bundle, tmp_path / "out")
    assert code == 1
    assert [m["path"] for m in summary["mismatches"]] == ["stages/e8/.pending-001-KO-1-Q-run0-abc/owner.json"]
    assert "stages/e8/.pending-001-KO-1-Q-run0-abc/owner.json" in summary["source_changes"]
    assert (tmp_path / "out" / "sha256-inventory.json").is_file()
