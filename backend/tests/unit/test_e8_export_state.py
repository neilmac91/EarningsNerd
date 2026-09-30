"""``export_e8_state.py`` preserves every stop as evidence and says whether it is a checkpoint.

The judging container is ephemeral, so the committed export is the only durable record of the
E8 guard (README.md, sole-guard recovery). These tests build synthetic guards in each lifecycle
stage and check the behaviours the 23 September readiness review found missing: a partial setup
or unmatched receipt is exported rather than refused (a refusal lost the evidence, and the kit
forbids retrying a refused step), a readback that records the absent ``active`` key as null is
read as "no owners" only when the live key is absent, the copy is verified against its source,
empty ``.pending-*`` markers are listed, and ``git add`` keeps the per-slot ``run.log`` files.
Eligibility rests only on the read-only inspection the export runs itself (Codex P1 on #952: a
restored old success receipt outvoted a current refusal): these tests replace that subprocess
with a stand-in whose verdict is derived from the bundle's current bytes, and one test runs a
real stub interpreter. Nothing here touches a real guard, bundle, venv or CLI.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE = REPO_ROOT / "tasks" / "fable-e8-repin-2026-09-22"
SCRIPT = PACKAGE / "export_e8_state.py"
KIT = REPO_ROOT / "tasks" / "fable-e8-launch-kit.md"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def raw_export(tmp_path):
    """The export with its real subprocess runner, reading a copy of the package and a fake frozen checkout."""
    module = _load("export_e8_state_under_test", SCRIPT)
    module.PACKAGE = tmp_path / "package"
    shutil.copytree(PACKAGE, module.PACKAGE, ignore=shutil.ignore_patterns("__pycache__"))
    module.FROZEN_REPO = tmp_path / "frozen"
    for name in module.FROZEN_EVAL_FILES:
        _write(module.FROZEN_REPO / "backend" / "evals" / name, f"frozen {name}\n")
    return module


@pytest.fixture
def export(raw_export):
    """The export with the step 2 inspection replaced by ``SealedInspection``, which accepts an unchanged bundle."""
    raw_export.run_inspection = SealedInspection()
    return raw_export


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value if isinstance(value, str) else json.dumps(value, indent=2) + "\n")


def make_bundle(root: Path, stage: str = "pristine", *, active: dict | None = None) -> Path:
    """A bundle whose guard is pristine, template-configured or initialized (count 287).

    Like a restored bundle it carries the sealed shim beside the guard files (never exported) and,
    once setup has run, the ``state.lock`` guard_setup creates; an immutable manifest listing one
    file; the E3 candidate 2 prerequisite index; and the E8 index's reused control slots.
    """
    bundle = root.resolve() / "bundle"
    guard = bundle / "e8" / "guard"
    initialized = stage == "initialized"
    _write(guard / "claude", "#!/bin/sh\n# frozen shim\n")
    if stage != "pristine":
        _write(guard / "state.lock", "")
    _write(bundle / "preserved" / "e2" / "judged.json", {"results": []})
    _write(bundle / "immutable-sha256.json",
           {"preserved/e2/judged.json": hashlib.sha256((bundle / "preserved/e2/judged.json").read_bytes()).hexdigest()})
    _write(bundle / "stages" / "e3-candidate2" / "index.json", PREREQUISITE_INDEX)
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
                                               "state_path": str(guard / "state.json"),
                                               "real_cli": "/opt/claude-code/bin/claude"})
    _write(bundle / "stages" / "e8" / "index.json", {"programme": "e8", "packets": PACKETS, "reused_main_slots": REUSED})
    return bundle


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# The frozen 160-slot panel, with the packet bindings a ledger row must repeat.
PACKETS = [{"slot": f"{n:03d}", "packet_sha256": _digest(f"packet {n}"), "request_sha256": _digest(f"request {n}"),
            "row_sha256": _digest(f"row {n}")} for n in range(1, 161)]
REUSED = [{"slot": f"c{n:03d}", "slot_kind": "main", "condition": "o"} for n in range(1, 141)]
PREREQUISITE_INDEX = {"programme": "e3-candidate2", "packets": []}
# What the sealed admission pins, as the stand-in below checks it: the prerequisite's bytes and the reused panel.
PINNED_PREREQUISITE = _digest(json.dumps(PREREQUISITE_INDEX, indent=2) + "\n")
PINNED_REUSED = _digest(json.dumps(REUSED, sort_keys=True))


def inspection(bundle: Path) -> dict:
    """What the read-only inspection prints for this bundle once the sealed admission accepts it."""
    slots = bundle / "stages" / "e8" / "slots"
    done = {p.name for p in slots.iterdir() if (p / "judged.json").is_file()} if slots.is_dir() else set()
    missing = [p["slot"] for p in PACKETS if p["slot"] not in done]
    return {"stage": "e8", "reused_control_mains": 140, "new_planned": 160, "new_complete": len(done),
            "new_missing": len(missing), "missing_slots": missing}


def _refused(argv: list[str], message: str) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(argv, 2, "", message + "\n")


class SealedInspection:
    """Stands in for ``tools/e8_resume.py`` without ``--execute``: its verdict comes from the bytes under --bundle.

    It refuses as the sealed admission does when the E3 candidate 2 prerequisite or the E8 index's
    reused control panel differs from its pinned value, and otherwise prints the inspection JSON for
    the slots actually present. Every call is recorded.
    """

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str]) -> subprocess.CompletedProcess:
        self.calls.append(list(argv))
        bundle = Path(argv[argv.index("--bundle") + 1])
        prerequisite = bundle / "stages" / "e3-candidate2" / "index.json"
        if not prerequisite.is_file() or hashlib.sha256(prerequisite.read_bytes()).hexdigest() != PINNED_PREREQUISITE:
            return _refused(argv, "ValueError: E3 candidate 2 is incomplete")
        index = json.loads((bundle / "stages" / "e8" / "index.json").read_text())
        if _digest(json.dumps(index.get("reused_main_slots"), sort_keys=True)) != PINNED_REUSED:
            return _refused(argv, "ValueError: E8 reused controls changed")
        return subprocess.CompletedProcess(argv, 0, json.dumps(inspection(bundle), indent=2) + "\n", "")


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
    _write(receipts / "inspection-post-run.json", inspection(bundle))
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


TERMINAL_MARKERS = [
    ("STOP alone", lambda s: _write(s / "STOP.supplement.json", {"failure": "Uncertain accounting"}),
     "STOP present: STOP.supplement.json"),
    ("original STOP", lambda s: _write(s / "STOP.json", {}), "STOP present: STOP.json"),
    ("pending directory alone", lambda s: _write(s / ".pending-003-x-abc" / "owner.json", {}),
     "pending invocation marker: .pending-003-x-abc"),
    ("pending file", lambda s: _write(s / ".pending-004-x-def", "partial"), "pending invocation marker: .pending-004-x-def"),
    ("failed entry alone", lambda s: _write(s / "failed" / ".pending-005-x-ghi" / "run.log", "STDOUT\n"),
     "failed invocations: ['.pending-005-x-ghi']"),
]


@pytest.mark.parametrize(("name", "make_marker", "blocker"), TERMINAL_MARKERS, ids=[case[0] for case in TERMINAL_MARKERS])
def test_each_terminal_marker_blocks_recovery_on_its_own(export, monkeypatch, tmp_path, name, make_marker, blocker) -> None:
    bundle = make_bundle(tmp_path, "initialized")
    guard = bundle / "e8" / "guard"
    make_marker(bundle / "stages" / "e8")
    receipts = tmp_path / "receipts"
    _write(receipts / "attestation.json", attestation(export, guard))
    _write(receipts / "readback.json", readback(guard))
    _write(receipts / "inspection-post-run.json", inspection(bundle))
    code, summary = run(export, monkeypatch, bundle, tmp_path / "out", receipts)
    assert code == 0
    assert summary["recovery_blockers"] == [blocker]


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
     {}, {}, "outside 287..600"),
    ("quota latch on a completed call", {"real_cli_invocations": 288, "completed": [{"invocation": 288, "quota": True}]},
     {}, {}, "quota or owner-loss latch on invocations [288]"),
    ("owner loss on a completed call", {"real_cli_invocations": 288, "completed": [{"invocation": 288, "owner_lost": True}]},
     {}, {}, "quota or owner-loss latch on invocations [288]"),
    ("empty stop latch", {"stop_reason": ""}, {}, {}, "guard stop latch set: ''"),
    ("malformed owner records", {"active": []}, {}, {}, "active or malformed owner records"),
    ("scalar owner count", {"active": 1}, {}, {}, "active or malformed owner records"),
    ("owner flag", {"active": True}, {}, {}, "active or malformed owner records"),
    ("scalar completed history", {"completed": 3}, {}, {}, "completed history is not a list"),
    ("initialization recorded but guard left disabled", {}, {"enabled": False}, {}, "not enabled and reconciled"),
    ("initialized with the wrong prior count", {"real_cli_invocations": 300}, {}, {"prior_count": 300},
     "prior_count 300 is not the attested 287"),
    ("counter below its recorded prior count", {"real_cli_invocations": 287}, {}, {"prior_count": 290},
     "fell below its initialization prior_count"),
    ("ceiling changed in config", {}, {"ceiling": 700}, {}, "state_path/ceiling"),
    ("state path elsewhere in config", {}, {"state_path": "/tmp/other/state.json"}, {}, "state_path/ceiling"),
    ("initialization bound to another CLI", {}, {}, {"real_cli": "/usr/local/bin/claude"}, "state_path/real_cli differ"),
]


@pytest.mark.parametrize(("name", "state_change", "config_change", "init_change", "blocker"), GUARD_REFUSALS,
                         ids=[case[0] for case in GUARD_REFUSALS])
def test_a_guard_the_sealed_tools_would_refuse_is_never_an_eligible_checkpoint(
        export, monkeypatch, tmp_path, name, state_change, config_change, init_change, blocker) -> None:
    """Mirrors guard_setup.validate_guard, attest()'s prior count, e8_resume's quota/owner-loss latch and
    README condition 6; corrupt values are reported, never a crash before the summary is written."""
    bundle = make_bundle(tmp_path, "initialized")
    guard = bundle / "e8" / "guard"
    for file_name, change in (("state.json", state_change), ("config.json", config_change),
                              ("initialization.json", init_change)):
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


def _ledger_bundle(tmp_path: Path) -> Path:
    """An initialized guard after two slots: 001 used one call (288), 005 used two (289, 290)."""
    bundle = make_bundle(tmp_path, "initialized")
    stages = bundle / "stages" / "e8"
    for slot in ("001", "005"):
        _write(stages / "slots" / slot / "judged.json", {"results": [], "slot": slot})

    def row(slot: str, before: int, after: int) -> dict:
        packet = next(p for p in PACKETS if p["slot"] == slot)
        return {"slot": slot, "complete": True, "failure": None, **{k: packet[k] for k in ("packet_sha256", "request_sha256", "row_sha256")},
                "judged_json_sha256": hashlib.sha256((stages / "slots" / slot / "judged.json").read_bytes()).hexdigest(),
                "guard_before": {"real_cli_invocations": before}, "guard_after": {"real_cli_invocations": after}}

    rows = [row("001", 287, 288), row("005", 288, 290)]
    _write(stages / "execution-ledger.supplement.jsonl", "".join(json.dumps(r) + "\n" for r in rows))
    state_path = bundle / "e8" / "guard" / "state.json"
    _write(state_path, {**json.loads(state_path.read_text()), "real_cli_invocations": 290,
                        "completed": [{"invocation": n} for n in (288, 289, 290)]})
    return bundle


def _run_with_receipts(export, monkeypatch, tmp_path: Path, bundle: Path, with_inspection=True) -> dict:
    guard = bundle / "e8" / "guard"
    receipts = tmp_path / "receipts"
    _write(receipts / "attestation.json", attestation(export, guard))
    _write(receipts / "readback.json", matching_readback(guard))
    if with_inspection:
        _write(receipts / "inspection-post-run.json", inspection(bundle) if with_inspection is True else with_inspection)
    code, summary = run(export, monkeypatch, bundle, tmp_path / "out", receipts)
    assert code == 0 and summary["receipt_classes"] == {"attestation": True, "readback": True}
    return summary


def test_a_consistent_ledger_after_real_calls_is_an_eligible_checkpoint(export, monkeypatch, tmp_path) -> None:
    summary = _run_with_receipts(export, monkeypatch, tmp_path, _ledger_bundle(tmp_path))
    assert summary["recovery_blockers"] == [] and summary["recovery_eligible"] is True


def _edit_json(path: Path, **changes) -> None:
    _write(path, {**json.loads(path.read_text()), **changes})


def _rewrite_rows(stages: Path, edit) -> None:
    path = stages / "execution-ledger.supplement.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    edit(rows)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


LEDGER_REFUSALS = [
    ("a call the ledger never recorded",
     lambda b: _edit_json(b / "e8/guard/state.json", real_cli_invocations=291,
                          completed=[{"invocation": n} for n in (288, 289, 290, 291)]),
     "differs from the ledger total 290"),
    ("a gap in the completed history",
     lambda b: _edit_json(b / "e8/guard/state.json", completed=[{"invocation": n} for n in (288, 290)]),
     "completion history is not the sequence 288..290"),
    ("a slot that charged three calls",
     lambda b: _rewrite_rows(b / "stages/e8", lambda rows: rows[1]["guard_after"].update(real_cli_invocations=291)),
     "delta invalid at slot '005'"),
    ("a row that does not start where the last ended",
     lambda b: _rewrite_rows(b / "stages/e8", lambda rows: rows[1]["guard_before"].update(real_cli_invocations=289)),
     "continuity broken before slot '005'"),
    ("an incomplete row", lambda b: _rewrite_rows(b / "stages/e8", lambda rows: rows[0].update(complete=False)),
     "has an unresolved execution"),
    ("a row with a failure", lambda b: _rewrite_rows(b / "stages/e8", lambda rows: rows[0].update(failure="x")),
     "has an unresolved execution"),
    ("a repeated slot", lambda b: _rewrite_rows(b / "stages/e8", lambda rows: rows[1].update(slot="001")),
     "repeats a slot"),
    ("the original ledger", lambda b: _write(b / "stages/e8/execution-ledger.jsonl", ""),
     "unexpected original E8 ledger"),
    ("a slot directory without output", lambda b: _write(b / "stages/e8/slots/009/run.log", "STDOUT\n"),
     "slot directory without judged.json: 009"),
    ("a completed row without its output",
     lambda b: (b / "stages/e8/slots/005/judged.json").unlink(), "slot directory without judged.json: 005"),
    ("a ledger that is not JSON lines", lambda b: _write(b / "stages/e8/execution-ledger.supplement.jsonl", "{\n"),
     "is not JSON lines"),
    ("a slot name that is not a string", lambda b: _rewrite_rows(b / "stages/e8", lambda rows: rows[0].update(slot=["001"])),
     "slot is not a name"),
    ("a slot outside the frozen index",
     lambda b: (_rewrite_rows(b / "stages/e8", lambda rows: rows[1].update(slot="161")),
                (b / "stages/e8/slots/005").rename(b / "stages/e8/slots/161")),
     "references slots outside the frozen index: ['161']"),
    ("a stray file in slots/", lambda b: _write(b / "stages/e8/slots/notes.txt", "x"), "slots/ entry is not a directory: notes.txt"),
    ("an output the ledger does not bind", lambda b: _write(b / "stages/e8/slots/005/judged.json", {"results": ["edited"]}),
     "ledger row for 005 does not bind its judged.json"),
    ("a row bound to another packet",
     lambda b: _rewrite_rows(b / "stages/e8", lambda rows: rows[0].update(request_sha256="0" * 64)),
     "ledger row for 001 does not match its indexed packet"),
    ("an index that is not the frozen panel",
     lambda b: _write(b / "stages/e8/index.json", {"programme": "e8", "packets": PACKETS[:159]}),
     "is not the frozen 160-slot E8 index"),
]


@pytest.mark.parametrize(("name", "break_it", "blocker"), LEDGER_REFUSALS, ids=[case[0] for case in LEDGER_REFUSALS])
def test_broken_accounting_continuity_is_never_an_eligible_checkpoint(
        export, monkeypatch, tmp_path, name, break_it, blocker) -> None:
    """attest() and inspect_e8 refuse each of these before any slot, so the export must say so too."""
    bundle = _ledger_bundle(tmp_path)
    break_it(bundle)
    summary = _run_with_receipts(export, monkeypatch, tmp_path, bundle)
    assert summary["recovery_eligible"] is False
    assert any(blocker in b for b in summary["recovery_blockers"]), summary["recovery_blockers"]


def _wrong_counts(bundle: Path) -> dict:
    value = inspection(bundle)
    return {**value, "new_complete": value["new_complete"] - 1, "new_missing": value["new_missing"] + 1}


def _pre_run(bundle: Path) -> dict:
    """The step 2 inspection taken before any slot ran: 0 complete, 160 missing."""
    return {"stage": "e8", "reused_control_mains": 140, "new_planned": 160, "new_complete": 0, "new_missing": 160,
            "missing_slots": [p["slot"] for p in PACKETS]}


def _other_slots(bundle: Path) -> dict:
    """Right counts, wrong slots: an inspection of a different checkpoint of the same size."""
    value = inspection(bundle)
    return {**value, "missing_slots": ["001"] + [slot for slot in value["missing_slots"] if slot != "002"]}


INSPECTION_RECORD_KEYS = {"argv", "timeout_seconds", "started_at_utc", "finished_at_utc", "exit_status", "error",
                          "stdout", "stderr", "inputs_before_sha256", "inputs_after_sha256", "inputs_changed"}


def assert_evidence_exported(export, out: Path, code: int, summary: dict) -> None:
    """A5: a refused state is exported in full, with its failure evidence, and is never eligible."""
    assert code == 0 and summary["recovery_eligible"] is False and summary["recovery_blockers"]
    assert (out / "export-summary.json").is_file() and (out / "sha256-inventory.json").is_file()
    inputs_bytes = (out / "admission-inputs.json").read_bytes()
    assert summary["admission_inputs_sha256"] == hashlib.sha256(inputs_bytes).hexdigest()
    assert set(json.loads(inputs_bytes)) == {"before", "after"}
    assert set(summary["current_inspection"]) == INSPECTION_RECORD_KEYS
    assert summary["current_inspection"]["argv"] == export.inspection_argv(Path(summary["bundle"]))
    inventory = json.loads((out / "sha256-inventory.json").read_text())
    assert {"stages/e8/index.json", "e8/guard/state.json", "receipts/attestation.json"} <= set(inventory)


def test_a_historical_success_receipt_never_outvotes_a_current_refusal(export, monkeypatch, tmp_path) -> None:
    """A1 (Codex P1 r4085294704): the restored success has this export's exact slots and counts; the run refuses."""
    bundle = _ledger_bundle(tmp_path)
    _write(tmp_path / "receipts" / "inspection-post-run.json", inspection(bundle))
    monkeypatch.setattr(export, "run_inspection",
                        lambda argv: _refused(argv, "ValueError: E8 unknown or incomplete slot directory"))
    summary = _run_with_receipts(export, monkeypatch, tmp_path, bundle, with_inspection=False)
    assert summary["recovery_blockers"] == [
        "current read-only inspection refused (exit 2): ValueError: E8 unknown or incomplete slot directory"]
    assert summary["current_inspection"]["exit_status"] == 2
    assert "receipts/inspection-post-run.json" in json.loads((tmp_path / "out" / "sha256-inventory.json").read_text())
    assert_evidence_exported(export, tmp_path / "out", 0, summary)


def _edit_reused_panel(bundle: Path) -> None:
    _edit_json(bundle / "stages/e8/index.json", reused_main_slots=REUSED[:-1] + [{**REUSED[-1], "condition": "n"}])


def _edit_prerequisite(bundle: Path) -> None:
    _write(bundle / "stages/e3-candidate2/index.json", {**PREREQUISITE_INDEX, "packets": [{"slot": "x"}]})


CURRENT_STATE_REFUSALS = [
    ("E8 reused control panel edited", _edit_reused_panel, "ValueError: E8 reused controls changed"),
    ("E3 prerequisite changed", _edit_prerequisite, "ValueError: E3 candidate 2 is incomplete"),
]


@pytest.mark.parametrize(("name", "edit", "refusal"), CURRENT_STATE_REFUSALS, ids=[c[0] for c in CURRENT_STATE_REFUSALS])
def test_the_verdict_is_taken_on_the_current_bytes_not_on_matching_counts(
        export, monkeypatch, tmp_path, name, edit, refusal) -> None:
    """A2a: counts and slots are unchanged and a historical success sits in the receipts; only a run on the
    current bundle sees the change, and the export makes exactly one such run."""
    bundle = _ledger_bundle(tmp_path)
    historical = inspection(bundle)
    edit(bundle)
    assert inspection(bundle) == historical
    _write(tmp_path / "receipts" / "inspection-post-run.json", historical)
    summary = _run_with_receipts(export, monkeypatch, tmp_path, bundle, with_inspection=False)
    assert export.run_inspection.calls == [export.inspection_argv(bundle)]
    assert export.run_inspection.calls[0][export.run_inspection.calls[0].index("--bundle") + 1] == str(bundle)
    assert summary["recovery_blockers"] == [f"current read-only inspection refused (exit 2): {refusal}"]
    assert_evidence_exported(export, tmp_path / "out", 0, summary)


def _append(path: Path) -> None:
    with path.open("a") as stream:
        stream.write("\n")


# Admission inputs inside and outside stages/e8, the package and the frozen checkout, and the shim, which
# is hashed as an input but never exported.
INPUTS_EDITED_DURING_THE_RUN = [
    "bundle/stages/e8/index.json",
    "bundle/stages/e3-candidate2/index.json",
    "bundle/preserved/e2/judged.json",
    "bundle/e8/guard/claude",
    "frozen/backend/evals/golden_set.json",
    "package/tools/e8_resume.py",
]


@pytest.mark.parametrize("label", INPUTS_EDITED_DURING_THE_RUN)
def test_inputs_that_change_while_the_inspection_runs_void_its_verdict(export, monkeypatch, tmp_path, label) -> None:
    """A2b: the run printed a valid success, but on inputs that are no longer the ones it read."""
    bundle = _ledger_bundle(tmp_path)
    kind, rel = label.split("/", 1)
    target = {"bundle": bundle, "frozen": export.FROZEN_REPO, "package": export.PACKAGE}[kind] / rel
    accepting = export.run_inspection

    def racing(argv):
        result = accepting(argv)
        _append(target)
        return result

    monkeypatch.setattr(export, "run_inspection", racing)
    summary = _run_with_receipts(export, monkeypatch, tmp_path, bundle)
    assert summary["current_inspection"]["exit_status"] == 0
    assert summary["current_inspection"]["inputs_changed"] == [label]
    assert summary["recovery_blockers"] == [f"admission inputs changed during the current inspection: ['{label}']"]
    inputs = json.loads((tmp_path / "out" / "admission-inputs.json").read_text())
    assert inputs["before"][label] != inputs["after"][label]
    assert_evidence_exported(export, tmp_path / "out", 0, summary)


EDITED_BEFORE_THE_COPY = [
    ("stages/e8/index.json", lambda b: _append(b / "stages/e8/index.json")),
    ("e8/guard/state.json", lambda b: _append(b / "e8/guard/state.json")),
    ("stages/e8/notes.txt", lambda b: _write(b / "stages/e8/notes.txt", "written after the inspection")),
]


@pytest.mark.parametrize(("rel", "edit"), EDITED_BEFORE_THE_COPY, ids=[c[0] for c in EDITED_BEFORE_THE_COPY])
def test_the_exported_bytes_must_be_the_inspected_bytes(export, monkeypatch, tmp_path, rel, edit) -> None:
    """A2c: the source is quiescent during the copy, but it is not the state the inspection accepted."""
    bundle = _ledger_bundle(tmp_path)
    real_listing = export.source_listing
    edited = []

    def edit_then_list(*args):
        if not edited:
            edited.append(edit(bundle))
        return real_listing(*args)

    monkeypatch.setattr(export, "source_listing", edit_then_list)
    summary = _run_with_receipts(export, monkeypatch, tmp_path, bundle)
    assert summary["source_unchanged"] is True and summary["current_inspection"]["inputs_changed"] == []
    assert summary["recovery_blockers"] == [f"exported state differs from the inspected admission inputs: ['{rel}']"]
    assert_evidence_exported(export, tmp_path / "out", 0, summary)


def test_a_current_success_on_unchanged_inputs_is_an_eligible_checkpoint(export, monkeypatch, tmp_path) -> None:
    """A3: no refusal record is present; a stale pre-run success receipt is evidence and changes nothing."""
    bundle = _ledger_bundle(tmp_path)
    _write(tmp_path / "receipts" / "inspection-pre-run.json", _pre_run(bundle))
    summary = _run_with_receipts(export, monkeypatch, tmp_path, bundle, with_inspection=False)
    assert summary["recovery_blockers"] == [] and summary["recovery_eligible"] is True
    record = summary["current_inspection"]
    assert record["exit_status"] == 0 and record["error"] is None and record["inputs_changed"] == []
    assert json.loads(record["stdout"]) == inspection(bundle)
    assert record["inputs_before_sha256"] == record["inputs_after_sha256"]
    assert summary["inspection_refusal_records"] == []
    inputs_bytes = (tmp_path / "out" / "admission-inputs.json").read_bytes()
    assert summary["admission_inputs_sha256"] == hashlib.sha256(inputs_bytes).hexdigest()
    after = json.loads(inputs_bytes)["after"]
    assert {"package/code-sha256.json", "package/supplement-sha256.json", "package/tools/e8_resume.py",
            "bundle/immutable-sha256.json", "bundle/preserved/e2/judged.json", "bundle/stages/e3-candidate2/index.json",
            "bundle/stages/e8/index.json", "bundle/e8/guard/claude", "bundle/e8/guard/state.lock",
            "frozen/backend/evals/golden_set.json"} <= set(after)
    # The shim and state.lock are inputs, not exports: the guard comparison covers only the copied files.
    inventory = json.loads((tmp_path / "out" / "sha256-inventory.json").read_text())
    assert not {"e8/guard/claude", "e8/guard/state.lock"} & set(inventory)


REFUSAL_RECORDS = [
    ("a saved refusal", "inspection-post-run.txt", "ValueError: E8 ledger has an unresolved execution\n"),
    ("a saved non-verdict JSON", "inspection-post-run.json", {"error": "ValueError: E8 frozen order changed"}),
    ("a nested restored refusal", "restored/inspection-post-run.txt", "ValueError: E8 frozen order changed\n"),
]


@pytest.mark.parametrize(("name", "rel", "content"), REFUSAL_RECORDS, ids=[c[0] for c in REFUSAL_RECORDS])
def test_a_restored_refusal_record_remains_a_stop(export, monkeypatch, tmp_path, name, rel, content) -> None:
    """A3b: README condition 6, a prior stop remains a stop: a current success cannot clear it."""
    bundle = _ledger_bundle(tmp_path)
    _write(tmp_path / "receipts" / rel, content)
    summary = _run_with_receipts(export, monkeypatch, tmp_path, bundle, with_inspection=False)
    assert summary["current_inspection"]["exit_status"] == 0
    assert summary["inspection_refusal_records"] == [rel]
    assert summary["recovery_blockers"] == [
        f"receipts hold a refusal record of an earlier inspection, and a prior stop remains a stop (README condition 6): {rel}"]
    assert_evidence_exported(export, tmp_path / "out", 0, summary)


def _prints(make, code: int = 0, stderr: str = ""):
    """A stand-in run that prints ``make(bundle)`` (a dict is printed as the sealed tool prints it)."""
    def run(argv):
        value = make(Path(argv[argv.index("--bundle") + 1]))
        stdout = value if isinstance(value, str) else json.dumps(value, indent=2) + "\n"
        return subprocess.CompletedProcess(argv, code, stdout, stderr)
    return run


def _raises(exc: BaseException):
    def run(argv):
        raise exc
    return run


_KEYS = sorted(["stage", "reused_control_mains", "new_planned", "new_complete", "new_missing", "missing_slots"])
_NO_VERDICT = "current read-only inspection printed no single JSON verdict object"
_COUNTS = "current read-only inspection counts ({!r} complete, {!r} missing) differ from this export (2 complete, 158 missing)"
_SLOTS = "current read-only inspection missing slots differ from this export"
_VENV = "/home/user/fable-judging/venv/bin/python"

VERDICT_REFUSALS = [
    ("interpreter missing", _raises(FileNotFoundError(2, "No such file or directory", _VENV)),
     [f"current read-only inspection did not run: FileNotFoundError: [Errno 2] No such file or directory: '{_VENV}'"]),
    ("timed out", _raises(subprocess.TimeoutExpired([_VENV], 540, output=b'{"stage": "e8"', stderr=b"")),
     ["current read-only inspection did not run: TimeoutExpired: no verdict within 540 s"]),
    ("exit 2 with a success JSON on stdout", _prints(inspection, code=2), ["current read-only inspection refused (exit 2): (no stderr)"]),
    ("killed by a signal", _prints(inspection, code=-9), ["current read-only inspection refused (exit -9): (no stderr)"]),
    ("empty stdout", _prints(lambda b: ""), [_NO_VERDICT]),
    ("truncated JSON", _prints(lambda b: json.dumps(inspection(b))[:40]), [_NO_VERDICT]),
    ("two JSON objects", _prints(lambda b: json.dumps(inspection(b)) + "\n" + json.dumps(inspection(b)) + "\n"), [_NO_VERDICT]),
    ("a JSON list", _prints(lambda b: "[]\n"), [_NO_VERDICT]),
    ("an extra key", _prints(lambda b: {**inspection(b), "note": "x"}),
     [f"current read-only inspection verdict has keys {sorted([*_KEYS, 'note'])}, not {_KEYS}"]),
    ("another panel", _prints(lambda b: {**inspection(b), "reused_control_mains": 139}),
     ["current read-only inspection verdict is not for the frozen E8 panel (140 reused, 160 planned)"]),
    ("the pre-run counts", _prints(_pre_run), [_COUNTS.format(0, 160), _SLOTS]),
    ("other counts", _prints(_wrong_counts), [_COUNTS.format(1, 159)]),
    ("a float count", _prints(lambda b: {**inspection(b), "new_complete": 2.0}), [_COUNTS.format(2.0, 158)]),
    ("other slots", _prints(_other_slots), [_SLOTS]),
]


@pytest.mark.parametrize(("name", "run_it", "blockers"), VERDICT_REFUSALS, ids=[c[0] for c in VERDICT_REFUSALS])
def test_a_missing_malformed_or_ambiguous_current_verdict_is_a_named_blocker(
        export, monkeypatch, tmp_path, name, run_it, blockers) -> None:
    """A4 and A5: each is exported in full with its evidence, never a crash and never eligible."""
    bundle = _ledger_bundle(tmp_path)
    monkeypatch.setattr(export, "run_inspection", run_it)
    summary = _run_with_receipts(export, monkeypatch, tmp_path, bundle)
    assert summary["recovery_blockers"] == blockers
    assert_evidence_exported(export, tmp_path / "out", 0, summary)
    record = summary["current_inspection"]
    if name == "timed out":
        assert record["stdout"] == '{"stage": "e8"' and record["exit_status"] is None
    elif record["error"] is None:
        assert record["stdout"] == run_it(export.inspection_argv(bundle)).stdout


def _kit_step_2() -> list[str]:
    """The launch kit's step 2 command: its only sh-block line running e8_resume.py without --execute."""
    lines, inside = [], False
    for raw in KIT.read_text().splitlines():
        if raw.startswith("```"):
            inside = raw.strip() == "```sh"
            continue
        if inside and "tools/e8_resume.py" in raw and "--execute" not in raw:
            lines.append(raw.strip())
    assert len(lines) == 1, lines
    return lines[0].split(" ")


def test_the_inspection_is_exactly_the_kit_step_2_command(raw_export, monkeypatch) -> None:
    """A6: the export runs the kit's own step 2 argv, at the kit's and the restore script's fixed paths."""
    restore = _load("restore_e8_session_for_export_test", PACKAGE / "restore_e8_session.py")
    fresh = _load("export_e8_state_defaults", SCRIPT)
    assert fresh.PACKAGE == PACKAGE.resolve()
    assert fresh.VENV_PYTHON == restore.VENV / "bin" / "python"
    assert fresh.FROZEN_REPO == restore.FROZEN_REPO
    assert fresh.INSPECTION_TIMEOUT < 600  # inside the Bash tool's 600000 ms limit, with room to finish
    monkeypatch.setattr(fresh, "PACKAGE", Path("/home/user/EarningsNerd/tasks/fable-e8-repin-2026-09-22"))
    assert fresh.inspection_argv(restore.BUNDLE) == _kit_step_2()


STUBS = [
    ("refusal", "import sys; print('partial'); print('ValueError: E8 frozen order changed', file=sys.stderr); sys.exit(2)",
     2, "partial\n", ["current read-only inspection refused (exit 2): ValueError: E8 frozen order changed"]),
    ("success", "import sys; sys.stdout.write(open(sys.argv[1]).read())", 0, None, []),
]


@pytest.mark.parametrize(("name", "code", "status", "stdout", "blockers"), STUBS, ids=[c[0] for c in STUBS])
def test_the_real_runner_records_a_real_process(raw_export, monkeypatch, tmp_path, name, code, status, stdout, blockers) -> None:
    """A7: the unpatched subprocess runner, with a stub interpreter in place of the sealed tool."""
    bundle = _ledger_bundle(tmp_path)
    verdict = tmp_path / "verdict.json"
    verdict.write_text(json.dumps(inspection(bundle), indent=2) + "\n")
    monkeypatch.setattr(raw_export, "inspection_argv", lambda b: [sys.executable, "-c", code, str(verdict)])
    summary = _run_with_receipts(raw_export, monkeypatch, tmp_path, bundle, with_inspection=False)
    record = summary["current_inspection"]
    assert record["exit_status"] == status and record["error"] is None
    assert record["stdout"] == (verdict.read_text() if stdout is None else stdout)
    assert summary["recovery_blockers"] == blockers


def test_the_real_runner_turns_a_timeout_into_a_named_blocker(raw_export, monkeypatch, tmp_path) -> None:
    """A7: a hung inspection is killed at the timeout and recorded; the export is still written."""
    bundle = _ledger_bundle(tmp_path)
    monkeypatch.setattr(raw_export, "INSPECTION_TIMEOUT", 0.5)
    monkeypatch.setattr(raw_export, "inspection_argv",
                        lambda b: [sys.executable, "-c", "import sys, time; print('started', flush=True); time.sleep(30)"])
    summary = _run_with_receipts(raw_export, monkeypatch, tmp_path, bundle, with_inspection=False)
    assert summary["recovery_blockers"] == ["current read-only inspection did not run: TimeoutExpired: no verdict within 0.5 s"]
    assert summary["current_inspection"]["stdout"] == "started\n"
