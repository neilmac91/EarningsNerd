"""Run the fixed paused-caller controller against a stateful cloud boundary.

The boundary records real request bodies and enforces pause-before-secret ordering.
No Google API, provider, SQL database or scheduled business work is invoked.
"""
from __future__ import annotations

import base64
import copy
import importlib.util
import itertools
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
# Independently literal provider forms: do not derive the oracle from the parser.
REVISION_FORMS = (
    "earningsnerd-backend-00001-test",
    "projects/earnings-nerd/locations/us-west1/services/earningsnerd-backend/revisions/earningsnerd-backend-00001-test",
    "projects/123456789012/locations/us-west1/services/earningsnerd-backend/revisions/earningsnerd-backend-00001-test",
)
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
        self.project = {"projectId": "earnings-nerd", "projectNumber": "123456789012"}
        self.alias_metadata = {"name": caller.SECRET_PARENT + "INTERNAL_JOB_TOKEN/versions/3", "state": "ENABLED"}
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
        if api == "cloudresourcemanager":
            assert path == "v1/projects/earnings-nerd" and method == "GET" and body is None
            return copy.deepcopy(self.project)
        if api == "secretmanager":
            if path.endswith("/versions/latest"):
                return copy.deepcopy(self.alias_metadata)
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


@pytest.mark.parametrize("ready,created,routed", tuple(itertools.product(REVISION_FORMS, repeat=3)))
def test_same_revision_forms_produce_one_canonical_approval(ready, created, routed):
    cloud = Cloud()
    expected = plan(cloud)
    cloud.calls.clear()
    cloud.service.update(latestReadyRevision=ready, latestCreatedRevision=created)
    cloud.service["trafficStatuses"][0]["revision"] = routed
    result = plan(cloud)
    assert result == expected
    assert result["manifest"]["snapshot"]["api"]["revision"] == REVISION_FORMS[1]
    assert [row for row in cloud.calls if row[0] == "cloudresourcemanager"] == (
        [("cloudresourcemanager", "v1/projects/earnings-nerd", "GET", None)]
        if REVISION_FORMS[2] in (ready, created, routed) else [])
    assert not mutations(cloud) and not accesses(cloud)


def test_cli_accepts_short_traffic_without_changing_approval_schema(monkeypatch, capsys):
    cloud = Cloud()
    cloud.service["trafficStatuses"][0]["revision"] = "earningsnerd-backend-00001-test"
    monkeypatch.setattr(caller, "Cloud", lambda: cloud)
    assert caller.main(["plan"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["manifest"]["snapshot"]["api"]["revision"] == REVISION_FORMS[1]
    assert "diagnostics" not in result and "diagnostics" not in result["manifest"]
    assert not mutations(cloud) and not accesses(cloud)


def test_apply_accepts_equivalent_representation_but_refuses_real_revision_drift():
    cloud = Cloud()
    manifest = plan(cloud)
    cloud.service.update(latestReadyRevision=REVISION_FORMS[2], latestCreatedRevision=REVISION_FORMS[0])
    cloud.service["trafficStatuses"][0]["revision"] = REVISION_FORMS[0]
    assert apply(cloud, manifest)["api_revision"] == REVISION_FORMS[1]
    cloud = Cloud()
    manifest = plan(cloud)
    different = "earningsnerd-backend-00002-other"
    cloud.service.update(latestReadyRevision=different, latestCreatedRevision=different)
    cloud.service["trafficStatuses"][0]["revision"] = different
    with pytest.raises(caller.Refused, match="plan_configuration_changed"):
        apply(cloud, manifest)
    assert not mutations(cloud) and not accesses(cloud)


BAD_REVISION_REFERENCES = [
    None, 1, True, [], {}, "", "earningsnerd-backend-00002-other", "other-service-00001-test",
    "earningsnerd-backend-", "earningsnerd-backend-" + "a" * 44,
    "earningsnerd-backend-00001-test\n", "earningsnerd-backend-00001_TEST",
    "projects/other-project/locations/us-west1/services/earningsnerd-backend/revisions/earningsnerd-backend-00001-test",
    "projects/999999999999/locations/us-west1/services/earningsnerd-backend/revisions/earningsnerd-backend-00001-test",
    "projects/earnings-nerd/locations/us-east1/services/earningsnerd-backend/revisions/earningsnerd-backend-00001-test",
    "projects/123456789012/locations/us-east1/services/earningsnerd-backend/revisions/earningsnerd-backend-00001-test",
    "projects/earnings-nerd/locations/us-west1/services/other-service/revisions/earningsnerd-backend-00001-test",
    "projects/123456789012/locations/us-west1/services/other-service/revisions/earningsnerd-backend-00001-test",
    "projects/earnings-nerd/locations/us-west1/services/earningsnerd-backend/revisions/other-service-00001-test",
    "projects/earnings-nerd/locations/us-west1/services/earningsnerd-backend/revisions/nested/earningsnerd-backend-00001-test",
    "https://run.googleapis.com/v2/" + REVISION_FORMS[1],
]


@pytest.mark.parametrize("field", ["latestReadyRevision", "latestCreatedRevision", "traffic"])
@pytest.mark.parametrize("value", BAD_REVISION_REFERENCES)
def test_revision_scope_and_drift_fail_before_downstream_reads(field, value):
    cloud = Cloud()
    target = cloud.service["trafficStatuses"][0] if field == "traffic" else cloud.service
    target["revision" if field == "traffic" else field] = value
    with pytest.raises(caller.Refused, match="api_not_stable"):
        plan(cloud)
    assert all(row[0] in {"run", "cloudresourcemanager"} and row[2] == "GET" for row in cloud.calls)
    assert not mutations(cloud) and not accesses(cloud)


@pytest.mark.parametrize("change", [
    {"reconciling": True}, {"reconciling": "false"}, {"reconciling": None},
    {"trafficStatuses": []}, {"trafficStatuses": None}, {"trafficStatuses": {}},
    {"trafficStatuses": [None]}, {"trafficStatuses": ["private"]},
    {"trafficStatuses": [{"revision": REVISION, "percent": 50}, {"revision": REVISION, "percent": 50}]},
    {"trafficStatuses": [{"revision": REVISION, "percent": 99}]},
    {"trafficStatuses": [{"revision": REVISION, "percent": "100"}]},
    {"trafficStatuses": [{"revision": REVISION, "percent": 100, "tag": "live"}]},
])
def test_revision_normalization_preserves_stability_guards(change):
    cloud = Cloud()
    cloud.service.update(change)
    with pytest.raises(caller.Refused, match="api_not_stable"):
        plan(cloud)
    assert cloud.calls == [("run", "v2/" + caller.SERVICE, "GET", None)]


@pytest.mark.parametrize("project", [None, [], {}, {"projectId": "other", "projectNumber": "123456789012"},
                                     {"projectId": "earnings-nerd", "projectNumber": 123456789012},
                                     {"projectId": "earnings-nerd", "projectNumber": "0"},
                                     {"projectId": "earnings-nerd", "projectNumber": "123\n"}])
def test_numeric_scope_requires_verified_fixed_project_metadata(project):
    cloud = Cloud()
    cloud.project = project
    cloud.service["latestReadyRevision"] = REVISION_FORMS[2]
    with pytest.raises(caller.Refused, match="api_project_metadata_unverified"):
        plan(cloud)
    assert [row[0] for row in cloud.calls] == ["run", "cloudresourcemanager"]


def test_numeric_scope_metadata_denial_is_private_and_fails_closed(monkeypatch, capsys):
    cloud = Cloud()
    cloud.service["latestReadyRevision"] = REVISION_FORMS[2]
    real_call = cloud.call

    def denied(api, path, **kwargs):
        if api == "cloudresourcemanager":
            raise caller.OperationError(PRIVATE)
        return real_call(api, path, **kwargs)

    monkeypatch.setattr(cloud, "call", denied)
    monkeypatch.setattr(caller, "Cloud", lambda: cloud)
    assert caller.main(["plan"]) == 1
    output = capsys.readouterr()
    assert not output.err and PRIVATE not in output.out
    result = json.loads(output.out)
    assert result["reason"] == "api_project_metadata_unverified"
    assert result["diagnostics"]["project_number_verified"] is False


@pytest.mark.parametrize("service", [None, [], PRIVATE, {"latestReadyRevision": {"private": PRIVATE},
                                                      "trafficStatuses": PRIVATE, "env": PRIVATE}])
def test_cli_stability_diagnostics_are_closed_and_handle_malformed_service(monkeypatch, capsys, service):
    cloud = Cloud()
    cloud.service = service
    monkeypatch.setattr(caller, "Cloud", lambda: cloud)
    assert caller.main(["plan"]) == 1
    output = capsys.readouterr()
    assert not output.err and PRIVATE not in output.out
    result = json.loads(output.out)
    assert result == {"state": "UNVERIFIED", "reason": "api_not_stable", "diagnostics": {
        "service_shape_valid": isinstance(service, dict),
        "ready_form": "invalid_type" if isinstance(service, dict) else "missing",
        "created_form": "missing", "traffic_revision_form": "missing", "traffic_cardinality": "invalid",
        "traffic_percent_100": False, "traffic_untagged": True, "reconciliation_complete": True,
        "project_number_verified": False, "ready_identity_valid": False,
        "created_matches_ready": False, "traffic_matches_ready": False,
    }}
    assert cloud.calls == [("run", "v2/" + caller.SERVICE, "GET", None)]


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


def floating_binding(cloud, selector="latest", secret="INTERNAL_JOB_TOKEN"):
    ref = cloud.revision["spec"]["containers"][0]["env"][0]["valueFrom"]["secretKeyRef"]
    ref.update(name=secret, key=selector)


def diagnostic_cli(cloud, monkeypatch, capsys):
    monkeypatch.setattr(caller, "Cloud", lambda: cloud)
    assert caller.main(["plan"]) == 1
    captured = capsys.readouterr()
    assert not captured.err and PRIVATE not in captured.out
    result = json.loads(captured.out)
    assert set(result) == {"state", "reason", "diagnostics"}
    assert result["state"] == "UNVERIFIED" and result["reason"] == "internal_token_version_not_pinned"
    assert not accesses(cloud) and not mutations(cloud)
    assert not any(row[0] == "cloudscheduler" for row in cloud.calls)
    return result


@pytest.mark.parametrize("project", ["earnings-nerd", "123456789012"])
@pytest.mark.parametrize("revision", [REVISION_FORMS[0], REVISION_FORMS[2]])
def test_latest_metadata_is_revision_bound_unapproved_refusal_not_a_plan(monkeypatch, capsys, project, revision):
    cloud = Cloud()
    floating_binding(cloud, secret=caller.SECRET_PARENT + "existing-token")
    cloud.service.update(latestReadyRevision=revision, latestCreatedRevision=revision)
    cloud.service["trafficStatuses"][0]["revision"] = revision
    cloud.alias_metadata = {"name": f"projects/{project}/secrets/existing-token/versions/42",
                            "state": "ENABLED", "payload": PRIVATE, "other": PRIVATE}
    result = diagnostic_cli(cloud, monkeypatch, capsys)
    assert result["diagnostics"] == {
        "status": "UNAPPROVED_UNAPPLIED", "selector_form": "latest_alias",
        "api_revision": REVISION, "image_digest": IMAGE,
        "metadata_status": "enabled_numeric_candidate",
        "candidate_secret_version": "projects/earnings-nerd/secrets/existing-token/versions/42",
    }
    assert [row for row in cloud.calls if row[0] == "secretmanager"] == [
        ("secretmanager", "v1/projects/earnings-nerd/secrets/existing-token/versions/latest", "GET", None)]
    assert len([row for row in cloud.calls if row[0] == "cloudresourcemanager"]) == (
        1 if project == "123456789012" or revision == REVISION_FORMS[2] else 0)


@pytest.mark.parametrize("selector,form", [
    (None, "missing"), ("", "missing"), (3, "invalid_type"), (True, "invalid_type"),
    ([], "invalid_type"), ({"private": PRIVATE}, "invalid_type"),
    ("other-alias", "other_string"), ("latest\n", "other_string"), ("LATEST", "other_string"),
    ("0", "other_string"), ("01", "other_string"), ("1234567890", "other_string"),
    ("3/../../latest", "other_string"), (PRIVATE, "other_string"),
])
def test_non_latest_selectors_never_guess_or_request_metadata(monkeypatch, capsys, selector, form):
    cloud = Cloud()
    floating_binding(cloud, selector)
    result = diagnostic_cli(cloud, monkeypatch, capsys)
    assert result["diagnostics"] == {"status": "UNAPPROVED_UNAPPLIED", "selector_form": form,
                                     "api_revision": REVISION, "image_digest": IMAGE,
                                     "metadata_status": "not_requested"}
    assert [row[0] for row in cloud.calls] == ["run", "us-west1-run"]


def test_absent_selector_is_not_defaulted_to_latest(monkeypatch, capsys):
    cloud = Cloud()
    del cloud.revision["spec"]["containers"][0]["env"][0]["valueFrom"]["secretKeyRef"]["key"]
    result = diagnostic_cli(cloud, monkeypatch, capsys)
    assert result["diagnostics"]["selector_form"] == "missing"
    assert result["diagnostics"]["metadata_status"] == "not_requested"
    assert [row[0] for row in cloud.calls] == ["run", "us-west1-run"]


@pytest.mark.parametrize("metadata", [
    None, [], PRIVATE, {}, {"name": PRIVATE, "state": "ENABLED"},
    {"name": caller.SECRET_PARENT + "INTERNAL_JOB_TOKEN/versions/3", "state": "DISABLED"},
    {"name": caller.SECRET_PARENT + "INTERNAL_JOB_TOKEN/versions/3", "state": "DESTROYED"},
    {"name": caller.SECRET_PARENT + "INTERNAL_JOB_TOKEN/versions/3", "state": True},
    {"name": None, "state": "ENABLED"}, {"name": {}, "state": "ENABLED"},
    *({"name": name, "state": "ENABLED"} for name in (
        "projects/other-project/secrets/INTERNAL_JOB_TOKEN/versions/3",
        "projects/999999999999/secrets/INTERNAL_JOB_TOKEN/versions/3",
        "projects/earnings-nerd/secrets/other-secret/versions/3",
        "projects/earnings-nerd/secrets/INTERNAL_JOB_TOKEN/versions/latest",
        "projects/earnings-nerd/secrets/INTERNAL_JOB_TOKEN/versions/0",
        "projects/earnings-nerd/secrets/INTERNAL_JOB_TOKEN/versions/03",
        "projects/earnings-nerd/secrets/INTERNAL_JOB_TOKEN/versions/1234567890",
        "projects/earnings-nerd/secrets/INTERNAL_JOB_TOKEN/versions/3\n",
        "projects/earnings-nerd/secrets/INTERNAL_JOB_TOKEN/versions/3:access",
        "https://secretmanager.googleapis.com/v1/projects/earnings-nerd/secrets/INTERNAL_JOB_TOKEN/versions/3",
    )),
])
def test_unverified_alias_metadata_cannot_supply_candidate(monkeypatch, capsys, metadata):
    cloud = Cloud()
    floating_binding(cloud)
    cloud.alias_metadata = metadata
    result = diagnostic_cli(cloud, monkeypatch, capsys)
    assert result["diagnostics"]["metadata_status"] == "metadata_response_unverified"
    assert "candidate_secret_version" not in result["diagnostics"]
    assert len([row for row in cloud.calls if row[0] == "secretmanager"]) == 1


@pytest.mark.parametrize("project", [None, [], {}, {"projectId": "other", "projectNumber": "123456789012"},
                                     {"projectId": "earnings-nerd", "projectNumber": 123456789012},
                                     {"projectId": "earnings-nerd", "projectNumber": "123456789012\n"}])
def test_alias_numeric_scope_needs_verified_fixed_project(monkeypatch, capsys, project):
    cloud = Cloud()
    floating_binding(cloud)
    cloud.project = project
    cloud.alias_metadata["name"] = "projects/123456789012/secrets/INTERNAL_JOB_TOKEN/versions/3"
    result = diagnostic_cli(cloud, monkeypatch, capsys)
    assert result["diagnostics"]["metadata_status"] == "project_metadata_unverified"
    assert "candidate_secret_version" not in result["diagnostics"]
    assert [row for row in cloud.calls if row[0] == "cloudresourcemanager"] == [
        ("cloudresourcemanager", "v1/projects/earnings-nerd", "GET", None)]


@pytest.mark.parametrize("failed_api,status", [("secretmanager", "metadata_read_unavailable"),
                                              ("cloudresourcemanager", "project_metadata_unverified")])
def test_alias_metadata_denial_withholds_provider_values(monkeypatch, capsys, failed_api, status):
    cloud = Cloud()
    floating_binding(cloud)
    cloud.alias_metadata["name"] = "projects/123456789012/secrets/INTERNAL_JOB_TOKEN/versions/3"
    real_call = cloud.call

    def denied(api, path, **kwargs):
        if api == failed_api:
            raise caller.OperationError(PRIVATE)
        return real_call(api, path, **kwargs)

    monkeypatch.setattr(cloud, "call", denied)
    result = diagnostic_cli(cloud, monkeypatch, capsys)
    assert result["diagnostics"]["metadata_status"] == status
    assert "candidate_secret_version" not in result["diagnostics"]


@pytest.mark.parametrize("boundary", ["revision", "image", "foreign_secret", "invalid_secret"])
def test_alias_diagnostic_never_precedes_existing_source_guards(boundary):
    cloud = Cloud()
    floating_binding(cloud)
    if boundary == "revision":
        cloud.service["latestCreatedRevision"] = "earningsnerd-backend-00002-other"
    elif boundary == "image":
        cloud.revision["status"]["imageDigest"] = PRIVATE
    else:
        floating_binding(cloud, secret=("projects/other/secrets/INTERNAL_JOB_TOKEN"
                                       if boundary == "foreign_secret" else PRIVATE + "/latest"))
    with pytest.raises(caller.Refused):
        plan(cloud)
    assert all(row[0] in {"run", "us-west1-run"} for row in cloud.calls)


@pytest.mark.parametrize("entry", ["snapshot", "api_snapshot", "apply", "database_snapshot"])
def test_alias_diagnostic_is_exclusive_to_refused_recovery_plan(entry):
    cloud = Cloud()
    manifest = plan(cloud)
    floating_binding(cloud)
    cloud.calls.clear()
    with pytest.raises(caller.Refused, match="internal_token_version_not_pinned") as error:
        if entry == "apply":
            apply(cloud, manifest)
        elif entry == "database_snapshot":
            cloud.revision["spec"]["containers"][0]["env"][0]["name"] = "DATABASE_URL"
            caller.api_snapshot(cloud, binding_name="DATABASE_URL", plan_diagnostics=True)
        else:
            getattr(caller, entry)(cloud)
    assert error.value.diagnostics is None
    assert [row[0] for row in cloud.calls] == ["run", "us-west1-run"]


def test_candidate_diagnostic_cannot_be_applied_as_approval(monkeypatch, capsys, tmp_path):
    cloud = Cloud()
    floating_binding(cloud)
    result = diagnostic_cli(cloud, monkeypatch, capsys)
    source = tmp_path / "diagnostic.json"
    source.write_text(json.dumps(result))
    cloud.calls.clear()
    monkeypatch.setattr(caller, "Cloud", lambda: pytest.fail("Diagnostic must refuse before authentication"))
    assert caller.main(["apply-paused", "--plan", str(source), "--expected-plan-sha256", "a" * 64,
                        "--approval-nonce", NONCE]) == 1
    assert json.loads(capsys.readouterr().out) == {"state": "UNVERIFIED", "reason": "invalid_plan"}
    assert not cloud.calls


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
