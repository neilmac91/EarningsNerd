"""One bounded plan from reviewed main; no extraction, execution or provider diagnostics."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import stat
import subprocess
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.support.ops_workflow import BY_NAME, PROXY, selected

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("summary_plan_loader", ROOT / "ops/summary_delivery/load_plan.py")
loader = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(loader)


def zipped(filename, content, *, symlink=False, extra=False):
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w") as archive:
        info = zipfile.ZipInfo(filename)
        if symlink:
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, content)
        if extra:
            archive.writestr("extra.json", "{}")
    return target.getvalue()


@pytest.fixture
def fixture(monkeypatch):
    manifest = {"nonce": "b" * 32, "fixture": "reviewed"}
    sha = hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    content = json.dumps({"manifest": manifest, "sha256": sha}).encode()
    env = {"OP": "summary-delivery-apply", "SUMMARY_PLAN_RUN": "123", "SUMMARY_PLAN_SHA256": sha,
           "SUMMARY_APPROVAL_NONCE": "b" * 32, "GITHUB_SHA": "c" * 40,
           "GITHUB_REPOSITORY": loader.REPOSITORY, "GITHUB_REF": "refs/heads/main"}
    run = {"id": 123, "repository": {"full_name": loader.REPOSITORY}, "head_repository": {"full_name": loader.REPOSITORY},
           "path": ".github/workflows/ops.yml", "event": "workflow_dispatch", "head_branch": "main",
           "head_sha": env["GITHUB_SHA"], "status": "completed", "conclusion": "success", "run_attempt": 1}
    artifact = {"id": 456, "name": "summary-delivery-plan-123", "expired": False, "size_in_bytes": 200}
    state = SimpleNamespace(env=env, run=run, artifact=artifact, content=content, calls=[],
                            listing={"total_count": 1, "artifacts": [artifact]},
                            archive=zipped("summary-delivery-plan.json", content))

    def gh(path, *, binary=False):
        state.calls.append((path, binary))
        assert path.startswith(f"repos/{loader.REPOSITORY}/actions/")
        if path.endswith("/zip"):
            assert path.endswith("/artifacts/456/zip") and binary
            return state.archive
        if path.endswith("/artifacts?per_page=100"):
            return state.listing
        assert path.endswith("/runs/123")
        return state.run
    monkeypatch.setattr(loader, "gh", gh)
    return state


def test_loads_exact_reviewed_plan_without_extracting(fixture):
    assert loader.load(fixture.env) == fixture.content
    assert len(fixture.calls) == 3


@pytest.mark.parametrize("field,value", [
    ("id", 124), ("id", "123"), ("repository", {"full_name": "other/repo"}),
    ("head_repository", {"full_name": "other/repo"}), ("path", ".github/workflows/ci.yml"),
    ("event", "pull_request"), ("head_branch", "feature"), ("head_sha", "d" * 40),
    ("status", "in_progress"), ("conclusion", "failure"), ("run_attempt", 2), ("run_attempt", True),
])
def test_refuses_unreviewed_or_ambiguous_run_before_artifact_read(fixture, field, value):
    fixture.run[field] = value
    with pytest.raises(loader.Refused, match="plan_run_unverified"):
        loader.load(fixture.env)
    assert len(fixture.calls) == 1


def test_cleanup_can_read_original_plan_after_main_moves(fixture):
    fixture.env["OP"] = "summary-delivery-cleanup-apply"
    fixture.env["GITHUB_SHA"] = "d" * 40
    assert loader.load(fixture.env) == fixture.content


def test_recovery_uses_only_its_own_artifact_and_member(fixture):
    fixture.env["OP"] = "summary-recovery-caller-apply"
    with pytest.raises(loader.Refused, match="artifact_identity_unverified"):
        loader.load(fixture.env)
    fixture.artifact["name"] = "summary-recovery-caller-plan-123"
    fixture.archive = zipped("summary-recovery-plan.json", fixture.content)
    assert loader.load(fixture.env) == fixture.content


@pytest.mark.parametrize("field,value", [
    ("OP", "arbitrary"), ("SUMMARY_PLAN_RUN", "123/../456"), ("SUMMARY_PLAN_RUN", "0"),
    ("SUMMARY_PLAN_SHA256", "invalid"), ("SUMMARY_APPROVAL_NONCE", "a\nb"),
    ("GITHUB_SHA", "main"), ("GITHUB_REF", "refs/heads/other"), ("GITHUB_REPOSITORY", "other/repo"),
])
def test_refuses_bad_inputs_before_provider_read(fixture, field, value):
    fixture.env[field] = value
    with pytest.raises(loader.Refused, match="plan_input_refused"):
        loader.load(fixture.env)
    assert fixture.calls == []


@pytest.mark.parametrize("defect", ["truncated", "duplicate", "expired", "size", "id", "wrong_name"])
def test_refuses_ambiguous_artifact_identity(fixture, defect):
    if defect == "truncated":
        fixture.listing["total_count"] = 101
    elif defect == "duplicate":
        fixture.listing["artifacts"].append(fixture.artifact.copy())
        fixture.listing["total_count"] = 2
    else:
        field, value = {"expired": ("expired", True), "size": ("size_in_bytes", loader.ARTIFACT_LIMIT + 1),
                        "id": ("id", "456"), "wrong_name": ("name", "unexpected")}[defect]
        fixture.artifact[field] = value
    with pytest.raises(loader.Refused):
        loader.load(fixture.env)
    assert len(fixture.calls) == 2


@pytest.mark.parametrize("name,content,kwargs", [
    ("../summary-delivery-plan.json", b"{}", {}), ("summary-delivery-plan.json", b"{}", {"symlink": True}),
    ("summary-delivery-plan.json", b"{}", {"extra": True}),
    ("summary-delivery-plan.json", b"x" * (loader.LIMIT + 1), {}),
])
def test_refuses_path_traversal_links_extra_files_and_oversize(fixture, name, content, kwargs):
    fixture.archive = zipped(name, content, **kwargs)
    with pytest.raises(loader.Refused):
        loader.load(fixture.env)


@pytest.mark.parametrize("defect", ["expected_hash", "embedded_hash", "nonce", "manifest", "extra"])
def test_hash_and_nonce_bind_the_approved_content(fixture, defect):
    value = json.loads(fixture.content)
    if defect == "expected_hash":
        fixture.env["SUMMARY_PLAN_SHA256"] = "e" * 64
    elif defect == "embedded_hash":
        value["sha256"] = "e" * 64
    elif defect == "nonce":
        fixture.env["SUMMARY_APPROVAL_NONCE"] = "e" * 32
    elif defect == "manifest":
        value["manifest"]["fixture"] = "changed"
    else:
        value["extra"] = True
    fixture.archive = zipped("summary-delivery-plan.json", json.dumps(value))
    with pytest.raises(loader.Refused):
        loader.load(fixture.env)


def test_cli_withholds_malformed_provider_data_and_never_writes_on_failure(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(loader, "load", lambda env: (_ for _ in ()).throw(ValueError("PRIVATE_SENTINEL")))
    assert loader.main() == 1
    assert not loader.OUTPUT.exists()
    assert "PRIVATE_SENTINEL" not in capsys.readouterr().out


def test_cli_private_exclusive_output(fixture, monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(loader, "load", lambda env: fixture.content)
    assert loader.main() == 0
    assert stat.S_IMODE(loader.OUTPUT.stat().st_mode) == 0o600
    assert loader.OUTPUT.read_bytes() == fixture.content
    assert loader.main() == 1
    assert fixture.content.decode() not in capsys.readouterr().out


def test_provider_command_has_fixed_argv_timeout_private_output(monkeypatch):
    def run(argv, **kwargs):
        assert argv == ["gh", "api", "fixed-path"]
        assert kwargs["stderr"] == subprocess.DEVNULL and kwargs["timeout"] == 40
        kwargs["stdout"].write(b'{"okay":true}')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(loader.subprocess, "run", run)
    assert loader.gh("fixed-path") == {"okay": True}


def test_summary_operations_run_only_fixed_tools_after_plan_and_approval_checks():
    mapping = {
        "Plan isolated summary delivery rehearsal": ("summary-delivery-plan", "manage.py plan"),
        "Run approved isolated summary delivery rehearsal": ("summary-delivery-apply", "manage.py apply"),
        "Clean approved isolated summary delivery resources": ("summary-delivery-cleanup-apply", "manage.py cleanup"),
        "Plan paused summary recovery caller": ("summary-recovery-caller-plan", "recovery_caller.py plan"),
        "Configure approved paused summary recovery caller": ("summary-recovery-caller-apply", "recovery_caller.py apply-paused"),
    }
    loader_at, loader_step = BY_NAME["Load reviewed summary operation plan"]
    guard_at, guard = BY_NAME["Refuse an apply that no one approved in this run"]
    deploy_at, deploy = BY_NAME["Refuse to run while a main push (deploy) is in flight"]
    assert selected(loader_step) == {op for op, _ in mapping.values() if op.endswith("-apply")}
    assert loader_step["run"] == "python3 ops/summary_delivery/load_plan.py"
    assert guard_at < loader_at and deploy_at < loader_at
    for name, (operation, command) in mapping.items():
        at, step = BY_NAME[name]
        assert step["if"] == f"steps.request.outputs.operation == '{operation}'"
        assert step["run"].startswith("python3 ops/summary_delivery/" + command)
        assert "continue-on-error" not in step and 0 < int(step["timeout-minutes"]) <= 40
        assert operation in selected(deploy) and operation not in selected(BY_NAME[PROXY][1])
        if operation.endswith("-apply"):
            assert operation in selected(guard) and loader_at < at
            assert step["env"]["SUMMARY_DELIVERY_APPROVED"] == "true"
            assert '--plan summary-approved-plan.json' in step["run"]
            assert '--expected-plan-sha256 "$SUMMARY_PLAN_SHA256"' in step["run"]
            assert '--approval-nonce "$SUMMARY_APPROVAL_NONCE"' in step["run"]
        else:
            assert "SUMMARY_DELIVERY_APPROVED" not in step.get("env", {})
