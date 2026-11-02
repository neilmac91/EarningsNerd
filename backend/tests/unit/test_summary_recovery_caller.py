"""Run the fixed paused-caller controller against a stateful cloud boundary.

The boundary records real request bodies and enforces pause-before-secret ordering.
No Google API, provider, SQL database or scheduled business work is invoked.
"""
from __future__ import annotations

import base64
import copy
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("summary_recovery_caller", ROOT / "ops/summary_delivery/recovery_caller.py")
caller = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(caller)
NOW = datetime(2026, 11, 2, 6, 0, tzinfo=timezone.utc)
NONCE = "a" * 32
# A synthetic privacy sentinel, not a credential. Never sent outside this fixture.
PRIVATE = "PRIVATE_RECOVERY_HEADER_SENTINEL_" * 2
REVISION = caller.SERVICE + "/revisions/earningsnerd-backend-00001-test"
URL = "https://earningsnerd-backend-fixed.us-west1.run.app"
IMAGE = "us-west1-docker.pkg.dev/earnings-nerd/earningsnerd/backend@sha256:" + "a" * 64


@pytest.fixture(autouse=True)
def protected_apply(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    monkeypatch.setenv("SUMMARY_DELIVERY_APPROVED", "true")


class Cloud:
    def __init__(self):
        self.calls = []
        self.job = None
        self.secret = PRIVATE
        self.fail_at = None
        self.omit_zeros = False
        self.service = {"uri": URL, "latestReadyRevision": REVISION, "latestCreatedRevision": REVISION,
                        "trafficStatuses": [{"revision": REVISION, "percent": 100}]}
        self.revision = {"status": {"imageDigest": IMAGE}, "spec": {"containers": [{"env": [
            {"name": "INTERNAL_JOB_TOKEN", "valueFrom": {"secretKeyRef": {"name": "INTERNAL_JOB_TOKEN", "key": "3"}}},
        ]}]}}

    def call(self, api, path, *, method="GET", body=None, missing_ok=False):
        self.calls.append((api, path, method, copy.deepcopy(body)))
        if self.fail_at == "pause" and path.endswith(":pause"):
            raise caller.OperationError(PRIVATE)
        if api == "run":
            return copy.deepcopy(self.service)
        if api == "us-west1-run":
            return copy.deepcopy(self.revision)
        if api == "secretmanager":
            if path.endswith(":access"):
                assert self.job and self.job["state"] == "PAUSED", "secret access before pause"
                return {"name": path[3:-7], "payload": {"data": base64.b64encode(self.secret.encode()).decode()}}
            return {"name": path[3:], "state": "ENABLED"}
        assert api == "cloudscheduler"
        if method == "GET":
            if self.job is None:
                assert missing_ok
                return None
            return copy.deepcopy(self.job)
        if path.endswith(":pause"):
            self.job["state"] = "PAUSED"
        elif method == "POST":
            assert self.job is None
            assert "X-Internal-Token" not in body["httpTarget"]["headers"]
            self.job = {**copy.deepcopy(body), "state": "ENABLED"}
            if self.fail_at == "create_ambiguous":
                raise caller.OperationError(PRIVATE)
        elif method == "PATCH":
            assert self.job["state"] == "PAUSED", "authenticated patch while enabled"
            self.job.update(copy.deepcopy(body))
            if self.omit_zeros:
                for key in ("retryCount", "maxDoublings"):
                    self.job["retryConfig"].pop(key)
        else:
            raise AssertionError("Unexpected mutation")
        return copy.deepcopy(self.job)


def plan(cloud):
    return caller.make_plan(cloud, now=NOW, nonce=NONCE)


def apply(cloud, manifest, **kwargs):
    options = {"expected_sha": manifest["sha256"], "approval_nonce": NONCE, "now": NOW}
    options.update(kwargs)
    return caller.apply_plan(cloud, manifest, **options)


def mutations(cloud):
    return [row for row in cloud.calls if row[2] != "GET"]


def accesses(cloud):
    return [row for row in cloud.calls if row[1].endswith(":access")]


def test_plan_only_reads_metadata_and_emits_no_secret():
    cloud = Cloud()
    result = plan(cloud)
    assert result["manifest"]["desired_state"] == "PAUSED"
    assert result["manifest"]["snapshot"]["api"]["secret_version"].endswith("/versions/3")
    assert result["manifest"]["bootstrap_schedule"] == "0 6 9 11 *"
    assert not mutations(cloud) and not accesses(cloud)
    assert PRIVATE not in json.dumps(result)


def test_new_caller_is_paused_before_access_or_authentication():
    cloud = Cloud()
    manifest = plan(cloud)
    result = apply(cloud, manifest)
    assert result["state"] == "PAUSED" and result["activation_performed"] is False
    assert PRIVATE not in json.dumps(result)
    rows = mutations(cloud)
    assert [(row[2], row[1].split("?")[0].rsplit("/", 1)[-1]) for row in rows] == [
        ("POST", "jobs"), ("POST", "summary-recovery-minute:pause"), ("PATCH", "summary-recovery-minute")]
    assert "X-Internal-Token" not in rows[0][3]["httpTarget"]["headers"]
    assert rows[2][3]["httpTarget"]["headers"]["X-Internal-Token"] == PRIVATE
    assert cloud.job["state"] == "PAUSED" and cloud.job["schedule"] == "* * * * *"
    assert all(not row[1].endswith((":run", ":resume")) for row in cloud.calls)


@pytest.mark.parametrize("failure", ["pause", "create_ambiguous"])
def test_bootstrap_failures_never_install_or_access_token(failure):
    cloud = Cloud()
    manifest = plan(cloud)
    cloud.fail_at = failure
    with pytest.raises(caller.OperationError):
        apply(cloud, manifest)
    assert not accesses(cloud)
    assert "X-Internal-Token" not in cloud.job["httpTarget"]["headers"]


def test_existing_owned_paused_resource_rotates_to_pinned_value_without_resuming():
    cloud = Cloud()
    manifest = plan(cloud)
    apply(cloud, manifest)
    cloud.secret = "NEXT_SYNTHETIC_HEADER_SENTINEL_VALUE"
    cloud.calls.clear()
    changed = plan(cloud)
    result = apply(cloud, changed)
    assert result["state"] == "PAUSED"
    assert [row[2] for row in mutations(cloud)] == ["PATCH"]
    assert cloud.job["httpTarget"]["headers"]["X-Internal-Token"] == cloud.secret


@pytest.mark.parametrize("key,value", [
    ("state", "ENABLED"), ("description", "someone else's schedule"), ("name", caller.JOB + "-other"),
    ("timeZone", "Europe/Zurich"), ("schedule", PRIVATE), ("attemptDeadline", PRIVATE),
    ("retryConfig", {"private": PRIVATE}), ("retryConfig", {**caller.RETRY, "retryCount": 1}),
])
def test_existing_unowned_or_active_resource_is_not_adopted(key, value):
    cloud = Cloud()
    cloud.job = {**caller.bootstrap_spec(plan(cloud)["manifest"]), "state": "PAUSED"}
    cloud.job[key] = value
    cloud.calls.clear()
    with pytest.raises(caller.Refused, match="existing_caller_not_owned_and_paused"):
        plan(cloud)
    assert not mutations(cloud) and not accesses(cloud)


@pytest.mark.parametrize("change", [
    {"uri": "https://outside.example/recover"}, {"oauthToken": {"serviceAccountEmail": "private@example"}},
    {"oidcToken": {"audience": "private"}}, {"body": "cHJpdmF0ZQ=="}, {"httpMethod": "GET"},
    {"headers": {"Authorization": PRIVATE}},
])
def test_existing_drifted_target_is_refused(change):
    cloud = Cloud()
    cloud.job = {**caller.bootstrap_spec(plan(cloud)["manifest"]), "state": "PAUSED"}
    cloud.job["httpTarget"].update(change)
    cloud.calls.clear()
    with pytest.raises(caller.Refused):
        plan(cloud)
    assert not mutations(cloud) and not accesses(cloud)


@pytest.mark.parametrize("version", ["latest", "0", "secret-value", "3/../../4", "1\n", 3])
def test_floating_or_malformed_secret_version_cannot_plan(version):
    cloud = Cloud()
    cloud.revision["spec"]["containers"][0]["env"][0]["valueFrom"]["secretKeyRef"]["key"] = version
    with pytest.raises(caller.Refused, match="internal_token_version_not_pinned"):
        plan(cloud)
    assert not accesses(cloud) and not mutations(cloud)


@pytest.mark.parametrize("binding", [
    [], [{"name": "INTERNAL_JOB_TOKEN", "value": PRIVATE}],
    [{"name": "INTERNAL_JOB_TOKEN", "valueFrom": {"secretKeyRef": {
        "name": "projects/other-project/secrets/INTERNAL_JOB_TOKEN", "key": "3"}}}],
])
def test_missing_literal_or_unapproved_secret_binding_is_not_exposed(binding):
    cloud = Cloud()
    cloud.revision["spec"]["containers"][0]["env"] = binding
    with pytest.raises(caller.Refused) as error:
        plan(cloud)
    assert PRIVATE not in str(error.value)
    assert not accesses(cloud) and not mutations(cloud)


@pytest.mark.parametrize("selector", ["existing-internal-token", caller.SECRET_PARENT + "existing-internal-token"])
def test_existing_same_project_selector_is_consumed_without_creating_a_secret(selector):
    cloud = Cloud()
    cloud.revision["spec"]["containers"][0]["env"][0]["valueFrom"]["secretKeyRef"]["name"] = selector
    result = plan(cloud)
    assert result["manifest"]["snapshot"]["api"]["secret_version"] == (
        caller.SECRET_PARENT + "existing-internal-token/versions/3")
    assert not accesses(cloud) and not mutations(cloud)


@pytest.mark.parametrize("kwargs", [
    {"approval_nonce": "b" * 32}, {"expected_sha": "b" * 64},
    {"now": NOW + timedelta(seconds=caller.PLAN_LIFETIME_SECONDS + 1)}, {"now": NOW - timedelta(seconds=1)},
])
def test_approval_and_time_mismatch_stop_before_cloud_reads(kwargs):
    cloud = Cloud()
    manifest = plan(cloud)
    cloud.calls.clear()
    with pytest.raises(caller.Refused):
        apply(cloud, manifest, **kwargs)
    assert cloud.calls == []


@pytest.mark.parametrize("key,value", [("GITHUB_ACTIONS", "false"), ("GITHUB_RUN_ATTEMPT", "2"),
                                       ("SUMMARY_DELIVERY_APPROVED", "false"), ("SUMMARY_DELIVERY_APPROVED", "")])
def test_unprotected_apply_cannot_read_cloud_or_access_token(monkeypatch, key, value):
    cloud = Cloud()
    manifest = plan(cloud)
    cloud.calls.clear()
    monkeypatch.setenv(key, value)
    with pytest.raises(caller.Refused, match="protected_approval_required"):
        apply(cloud, manifest)
    assert cloud.calls == []


def test_readable_api_drift_after_approval_stops_before_any_mutation():
    cloud = Cloud()
    manifest = plan(cloud)
    cloud.service["uri"] = "https://new-fixed.us-west1.run.app"
    with pytest.raises(caller.Refused, match="plan_configuration_changed"):
        apply(cloud, manifest)
    assert not mutations(cloud) and not accesses(cloud)


@pytest.mark.parametrize("token", ["short", "x" * 513, "x" * 32 + "\r\nInjected: yes", "x" * 32 + "é"])
def test_invalid_header_secret_is_withheld_and_caller_stays_paused(token):
    cloud = Cloud()
    manifest = plan(cloud)
    cloud.secret = token
    with pytest.raises(caller.Refused, match="internal_token_value_unavailable"):
        apply(cloud, manifest)
    assert cloud.job["state"] == "PAUSED"
    assert all(row[2] != "PATCH" for row in mutations(cloud))


def test_protobuf_omitted_zero_fields_still_verify_explicit_zero_retry_target():
    cloud = Cloud()
    cloud.omit_zeros = True
    result = apply(cloud, plan(cloud))
    assert result["state"] == "PAUSED"


def test_cli_withholds_provider_exception_body(monkeypatch, capsys):
    def refused():
        raise caller.OperationError(PRIVATE)
    monkeypatch.setattr(caller, "Cloud", refused)
    assert caller.main(["plan"]) == 1
    captured = capsys.readouterr()
    assert PRIVATE not in captured.out + captured.err
    assert json.loads(captured.out) == {"state": "UNVERIFIED", "reason": "recovery_caller_operation_refused"}


def test_cli_invalid_approval_never_authenticates(monkeypatch, capsys, tmp_path):
    source = tmp_path / "plan.json"
    source.write_text(json.dumps(plan(Cloud())))
    monkeypatch.setattr(caller, "Cloud", lambda: pytest.fail("Cloud access before approval validation"))
    assert caller.main(["apply-paused", "--plan", str(source)]) == 1
    assert json.loads(capsys.readouterr().out)["state"] == "UNVERIFIED"


def test_credential_free_bootstrap_is_denied_by_real_recovery_endpoint(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.config import settings
    from app.routers import internal
    from app.services import summary_jobs

    async def unexpected(*args, **kwargs):
        pytest.fail("Credential-free schedule reached recovery work")

    monkeypatch.setattr(settings, "INTERNAL_JOB_TOKEN", PRIVATE)
    monkeypatch.setattr(settings, "SUMMARY_DURABLE_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "DURABLE_TASKS_ENABLED", True)
    monkeypatch.setattr(summary_jobs, "recover_due_jobs", unexpected)
    app = FastAPI()
    app.include_router(internal.router, prefix="/internal")
    with TestClient(app) as client:
        response = client.post("/internal/jobs/summary-recovery", headers={"Content-Type": "application/json"})
    assert response.status_code == 401
