"""``restore_e8_session.py`` checks what it can before it writes anything.

The launch kit's step 1 has one attempt: a refused step is never retried. The 23 September
readiness review found that the restore resolved three of its nine attachments only after the
bundle was assembled and extracted, never checked six of the kit table's hashes, crashed with a
KeyError on a transport-manifest schema mismatch, ran the CLI drift check (the 22 September
failure mode) last, logged no frozen commit although the kit says the receipt shows it, and
lost its log on a refusal. These tests use synthetic attachments, a fake CLI and a throwaway git
repository; no real upload, bundle, guard or CLI is touched.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "tasks" / "fable-e8-repin-2026-09-22" / "restore_e8_session.py"
PARTS = [f"fable-upload-0{n}-of-05.zip" for n in range(1, 6)]
SEALED_ZIPS = ["fable-reconciliation-2026-09-22.zip", "fable-e8-continuation-2026-09-22.zip",
               "fable-judging-e3-complete-2026-09-22.zip"]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def restore(monkeypatch, tmp_path):
    """The script as a module, with every fixed container path moved under tmp_path."""
    spec = importlib.util.spec_from_file_location("restore_e8_session_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    judging = tmp_path / "fable-judging"
    for name, path in {"ASSEMBLY": tmp_path / "fable-assembly", "JUDGING": judging,
                       "BUNDLE": judging / "fable-resume-corrected-2026-09-20",
                       "SUPPLEMENT": judging / "fable-reconciliation-2026-09-22",
                       "ADDON": judging / "fable-e8-continuation-2026-09-22",
                       "DELIVERABLE": tmp_path / "fable-e3-deliverable",
                       "FROZEN_REPO": tmp_path / "earningsnerd-fable-frozen",
                       "VENV": judging / "venv", "RECEIPTS": judging / "receipts"}.items():
        monkeypatch.setattr(module, name, path)
    return module


def _zip(path: Path, members: dict[str, bytes]) -> bytes:
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return path.read_bytes()


def make_uploads(restore, monkeypatch, root: Path, prefix: str = "4ec603f3-") -> tuple[Path, dict]:
    """Nine id-prefixed attachments whose hashes the (patched) kit table pins, plus their manifest."""
    uploads = root / "uploads"
    uploads.mkdir()
    payload = (b"synthetic corrected bundle " * 40)[:1000]
    chunks = [payload[i * 200:(i + 1) * 200] for i in range(5)]
    table, parts = {}, []
    for name, chunk in zip(PARTS, chunks):
        member = name.replace(".zip", ".bin")
        table[name] = _sha(_zip(uploads / (prefix + name), {member: chunk}))
        parts.append({"attachment": name, "attachment_sha256": table[name], "member": member,
                      "payload_bytes": len(chunk), "payload_sha256": _sha(chunk)})
    for name in SEALED_ZIPS:
        table[name] = _sha(_zip(uploads / (prefix + name), {name.replace(".zip", "") + "/x.txt": b"x"}))
    manifest = {"original_sha256": _sha(payload), "original_bytes": len(payload), "parts": parts}
    (uploads / (prefix + restore.TRANSPORT_MANIFEST)).write_text(json.dumps(manifest))
    table[restore.TRANSPORT_MANIFEST] = _sha((uploads / (prefix + restore.TRANSPORT_MANIFEST)).read_bytes())
    monkeypatch.setattr(restore, "KIT_ATTACHMENTS", table)
    monkeypatch.setattr(restore, "BUNDLE_ZIP_SHA256", _sha(payload))
    monkeypatch.setattr(restore, "BUNDLE_ZIP_BYTES", len(payload))
    return uploads, manifest


def _rewrite_manifest(restore, monkeypatch, uploads: Path, manifest: dict) -> None:
    path = next(uploads.glob("*-" + restore.TRANSPORT_MANIFEST))
    path.write_text(json.dumps(manifest))
    monkeypatch.setitem(restore.KIT_ATTACHMENTS, restore.TRANSPORT_MANIFEST, _sha(path.read_bytes()))


def test_all_nine_attachments_are_resolved_and_recorded(restore, monkeypatch, tmp_path) -> None:
    uploads, _ = make_uploads(restore, monkeypatch, tmp_path)
    log: dict = {}
    paths, manifest = restore.resolve_attachments(uploads, log)
    assert set(paths) == set(restore.KIT_ATTACHMENTS) and len(paths) == 9
    assert log["uploads_dir"] == str(uploads)
    for name, seen in log["attachments"].items():
        assert seen["upload"] == "4ec603f3-" + name
        assert seen["sha256"] == restore.KIT_ATTACHMENTS[name] == _sha(paths[name].read_bytes())
        assert seen["bytes"] == paths[name].stat().st_size


def test_a_changed_attachment_refuses_before_anything_is_written(restore, monkeypatch, tmp_path) -> None:
    uploads, _ = make_uploads(restore, monkeypatch, tmp_path)
    target = next(uploads.glob("*-fable-e8-continuation-2026-09-22.zip"))
    target.write_bytes(target.read_bytes() + b"\0")
    with pytest.raises(SystemExit, match="fable-e8-continuation-2026-09-22.zip"):
        restore.resolve_attachments(uploads, {})
    assert not restore.ASSEMBLY.exists() and not restore.JUDGING.exists()


@pytest.mark.parametrize("change", ["missing", "duplicate"])
def test_a_missing_or_duplicated_attachment_refuses(restore, monkeypatch, tmp_path, change: str) -> None:
    uploads, _ = make_uploads(restore, monkeypatch, tmp_path)
    source = next(uploads.glob("*-fable-judging-e3-complete-2026-09-22.zip"))
    if change == "missing":
        source.unlink()
    else:
        (uploads / ("99999999-" + source.name.split("-", 1)[1])).write_bytes(source.read_bytes())
    with pytest.raises(SystemExit, match="expected exactly one upload named fable-judging-e3-complete"):
        restore.resolve_attachments(uploads, {})


@pytest.mark.parametrize(("mutate", "message"), [
    (lambda m: m.pop("parts"), r"lacks \['parts'\]"),
    (lambda m: m.pop("original_bytes"), r"lacks \['original_bytes'\]"),
    (lambda m: m["parts"][2].pop("member"), r"part 3 lacks \['member'\]"),
    (lambda m: m["parts"].pop(), "are not the five kit uploads"),
    (lambda m: m["parts"][0].update(attachment_sha256="0" * 64), "disagree with the launch kit table"),
])
def test_a_transport_manifest_schema_problem_is_a_clean_refusal(restore, monkeypatch, tmp_path, mutate, message) -> None:
    uploads, manifest = make_uploads(restore, monkeypatch, tmp_path)
    mutate(manifest)
    _rewrite_manifest(restore, monkeypatch, uploads, manifest)
    with pytest.raises(SystemExit, match=message):
        restore.resolve_attachments(uploads, {})


def test_resolved_attachments_reassemble_the_pinned_bundle(restore, monkeypatch, tmp_path) -> None:
    uploads, _ = make_uploads(restore, monkeypatch, tmp_path)
    log: dict = {}
    paths, manifest = restore.resolve_attachments(uploads, log)
    out = restore.step_assemble(paths, manifest, log)
    assert _sha(out.read_bytes()) == restore.BUNDLE_ZIP_SHA256
    assert restore.step_assemble(paths, manifest, log) == out and log["assemble"] == "already present and verified"


def _fake_cli(root: Path, version: str) -> Path:
    cli = root / "fake-claude"
    auth = json.dumps({"loggedIn": True, "authMethod": "oauth_token", "apiProvider": "firstParty"})
    cli.write_text(f"#!/bin/sh\nif [ \"$1\" = \"--version\" ]; then echo '{version}'; else echo '{auth}'; fi\n")
    cli.chmod(0o755)
    return cli


def test_a_cli_drift_refuses_before_any_state_and_prints_the_log(restore, monkeypatch, tmp_path, capsys) -> None:
    uploads, _ = make_uploads(restore, monkeypatch, tmp_path)
    monkeypatch.setattr(restore, "REAL_CLI", _fake_cli(tmp_path, "2.1.281 (Claude Code)"))
    monkeypatch.setattr(sys, "argv", ["restore_e8_session.py", "--uploads", str(uploads)])
    with pytest.raises(SystemExit, match="2.1.281"):
        restore.main()
    printed = json.loads(capsys.readouterr().out)
    assert "CLI reports '2.1.281 (Claude Code)'" in printed["refused"]
    assert len(printed["attachments"]) == 9 and printed["cli"]["version_stdout"] == "2.1.281 (Claude Code)"
    assert not restore.ASSEMBLY.exists() and not restore.JUDGING.exists()


def test_the_pinned_cli_passes_the_read_only_checks(restore, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(restore, "REAL_CLI", _fake_cli(tmp_path, restore.EXPECTED_CLI_VERSION))
    log: dict = {}
    restore.step_cli(log)
    assert log["cli"]["auth"] == {"loggedIn": True, "authMethod": "oauth_token", "apiProvider": "firstParty"}


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
                          cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def test_the_receipt_names_the_frozen_commit_on_create_and_on_reuse(restore, monkeypatch, tmp_path) -> None:
    origin = tmp_path / "origin"
    (origin / "backend" / "evals").mkdir(parents=True)
    pinned = {}
    for name in ("judge.py", "judge_report.py"):
        (origin / "backend" / "evals" / name).write_text(f"# frozen {name}\n")
        pinned[name] = _sha((origin / "backend" / "evals" / name).read_bytes())
    _git("init", "-q", cwd=origin)
    _git("add", ".", cwd=origin)
    _git("commit", "-q", "-m", "frozen", cwd=origin)
    frozen = _git("rev-parse", "HEAD", cwd=origin)
    subprocess.run(["git", "clone", "-q", str(origin), str(tmp_path / "engineering")], check=True)
    monkeypatch.setattr(restore, "FROZEN_COMMIT", frozen)
    monkeypatch.setattr(restore, "PINNED_EVAL_FILES", pinned)

    created: dict = {}
    restore.step_worktree(tmp_path / "engineering", created)
    reused: dict = {}
    restore.step_worktree(tmp_path / "engineering", reused)
    assert created["frozen_commit"] == reused["frozen_commit"] == frozen
    assert reused["worktree"] == "already present at the frozen commit and clean"

    monkeypatch.setattr(restore, "FROZEN_COMMIT", "0" * 40)
    with pytest.raises(SystemExit, match="not 0000"):
        restore.step_worktree(tmp_path / "engineering", {})


def test_the_overlay_restores_the_shim_mode_and_logs_it_as_the_kit_writes_it(restore, monkeypatch) -> None:
    """Kit step 1 says the receipt shows overlay.shim_mode `0755`; extraction leaves the shim 0644."""
    bundle, deliverable = restore.BUNDLE, restore.DELIVERABLE
    sealed = bundle / "sealed.txt"
    sealed.parent.mkdir(parents=True)
    sealed.write_text("immutable\n")
    (bundle / "immutable-sha256.json").write_text(json.dumps({"sealed.txt": _sha(sealed.read_bytes())}))
    shim = bundle / "e8" / "guard" / "claude"
    shim.parent.mkdir(parents=True)
    shim.write_text("#!/bin/sh\n")
    shim.chmod(0o644)
    inventory = {}
    for stage in ("ko-corrected", "e3-candidate1", "e3-candidate2"):
        record = deliverable / "bundle-stage-records" / stage / "slots" / "001" / "judged.json"
        record.parent.mkdir(parents=True)
        record.write_text("{}\n")
        inventory[str(record.relative_to(deliverable))] = {"sha256": _sha(record.read_bytes())}
    (deliverable / "records").mkdir()
    (deliverable / "records" / "sha256-inventory-e3.json").write_text(json.dumps(inventory))
    monkeypatch.setattr(restore, "IMMUTABLE_MANIFEST_SHA256", _sha((bundle / "immutable-sha256.json").read_bytes()))
    monkeypatch.setattr(restore, "SHIM_SHA256", _sha(shim.read_bytes()))
    monkeypatch.setattr(restore, "EXPECTED_SLOT_DIRS", {"ko-corrected": 1, "e3-candidate1": 1, "e3-candidate2": 1})
    log: dict = {}
    restore.step_overlay(log)
    assert log["overlay"]["shim_mode"] == "0755" and shim.stat().st_mode & 0o777 == 0o755
    assert log["overlay"]["slot_dirs"] == {"ko-corrected": 1, "e3-candidate1": 1, "e3-candidate2": 1}
