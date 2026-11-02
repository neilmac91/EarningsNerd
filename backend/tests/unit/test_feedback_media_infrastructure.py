"""Private feedback resources are bounded and uploads require independent cleanup/storage proof.

Provider responses and calls are synthetic; no credentials, cloud mutations or user data are used.
The existing Ops wiring gate covers the owner approval and main-ref boundaries for every -apply.
"""
from __future__ import annotations

import copy
import importlib.util
import io
import json
import logging
import re
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError

import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("feedback_media_ops", ROOT / "ops/feedback_media/manage.py")
ops = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ops)


@pytest.fixture(autouse=True)
def live_verification_is_an_independent_prerequisite(monkeypatch):
    # This gate owns bucket/job/monitoring invariants. The isolated verifier gate separately
    # proves the signed receipt and that enablement cannot skip it.
    monkeypatch.setattr(ops, "require_live_verification", lambda *_: None)


def service():
    return {
        "etag": "service-version", "template": {
            "serviceAccount": "runtime@example.invalid",
            "containers": [{"image": "registry.invalid/application:verified", "env": [
                {"name": "DATABASE_URL", "valueSource": {"secretKeyRef": {"secret": "db", "version": "latest"}}},
                {"name": "SECRET_KEY", "valueSource": {"secretKeyRef": {"secret": "signing", "version": "latest"}}},
                {"name": "RESEND_API_KEY", "valueSource": {"secretKeyRef": {"secret": "mail", "version": "latest"}}},
            ], "volumeMounts": [{"name": "sql", "mountPath": "/cloudsql"}]}],
            "volumes": [{"name": "sql", "cloudSqlInstance": {"instances": ["project:region:database"]}}],
        },
    }


def bucket(environment):
    return {"name": ops.BUCKETS[environment], "location": "US-WEST1",
            "labels": {"purpose": "feedback-media", "environment": environment},
            "iamConfiguration": {"uniformBucketLevelAccess": {"enabled": True}, "publicAccessPrevention": "enforced"},
            "versioning": {"enabled": False}, "softDeletePolicy": {"retentionDurationSeconds": "0"}}


class CloudFixture:
    def __init__(self, *, omit_zero_threshold=True, absent=False):
        self.calls = []
        self.steps = []
        self.waits = 0
        self.omit_zero_threshold = omit_zero_threshold
        self.service = service()
        self.job = ops.job_spec(self.service)
        self.job["etag"] = "job-version"
        self.role = {"includedPermissions": ops.PERMISSIONS.copy(), "stage": "GA"}
        self.buckets = {name: bucket(environment) for environment, name in ops.BUCKETS.items()}
        self.bucket_policy = {"version": 3, "etag": "bucket-version", "bindings": [
            {"role": ops.ROLE, "members": ["serviceAccount:runtime@example.invalid"]},
        ]}
        self.job_policy = {"version": 3, "etag": "job-policy-version", "bindings": [
            {"role": "roles/run.invoker", "members": ["serviceAccount:runtime@example.invalid"]},
        ]}
        self.schedule = {"description": "EarningsNerd private feedback media cleanup", "state": "ENABLED",
                         "schedule": "17 * * * *", "timeZone": "Etc/UTC", "httpTarget": {
                             "uri": f"https://run.googleapis.com/v2/{ops.JOB}:run", "httpMethod": "POST", "body": "e30=",
                             "oauthToken": {"serviceAccountEmail": "runtime@example.invalid"}}}
        self.executions = [self.execution(ops.PROBE_ARGS), self.execution(ops.CLEANUP_ARGS)]
        # Real email-channel readback omits the default verificationStatus enum.
        self.channel = {"name": ops.CHANNEL, "type": "email", "enabled": True,
                        "labels": {"email_address": "PRIVATE_RECIPIENT_SENTINEL@example.invalid"}}
        self.metric = ops.heartbeat_spec()
        self.policies = [self.policy_readback(policy) for policy in ops.policy_specs()]
        self.heartbeat_seen = True
        # testIamPermissions answers: every requested project permission, and actAs on the runtime identity.
        self.granted = None
        self.act_as = True
        if absent:
            # A project no provisioning has reached: the state every recorded feedback-media run left.
            self.role, self.job, self.schedule, self.metric = None, None, None, None
            self.buckets, self.policies, self.executions = {}, [], []
            self.bucket_policy = {"version": 3, "etag": "bucket-version", "bindings": []}
            self.job_policy = {"version": 3, "etag": "job-policy-version", "bindings": []}

    def policy_readback(self, policy):
        result = copy.deepcopy(policy)
        # google-cloud-monitoring 2.32.0 / AlertPolicy ProtoJSON roundtrip omits this
        # implicit-presence double's zero default; Duration("0s") retains presence.
        # https://github.com/googleapis/googleapis/blob/master/google/monitoring/v3/alert.proto
        # https://protobuf.dev/programming-guides/json/#presence-and-default-values
        threshold = result["conditions"][0].get("conditionThreshold", {})
        if self.omit_zero_threshold and threshold.get("thresholdValue") == 0:
            del threshold["thresholdValue"]
        return result

    def execution(self, args):
        task = copy.deepcopy(self.job["template"]["template"])
        task["containers"][0]["args"] = args.copy()
        return {"template": task, "taskCount": 1, "succeededCount": 1,
                "completionTime": datetime.now(timezone.utc).isoformat()}

    @property
    def writes(self):
        # testIamPermissions is a POST that reads the caller's own grants; it changes nothing.
        return [call for call in self.calls if call[2] != "GET" and not call[1].endswith(":testIamPermissions")]

    def call(self, api, path, *, method="GET", body=None, missing_ok=False, step=None):
        self.calls.append((api, path, method, copy.deepcopy(body)))
        self.steps.append(step)
        if path.endswith(":testIamPermissions"):
            assert method == "POST" and step == ops.CAPABILITY_READ
            if api == "iam":
                assert body == {"permissions": [ops.ACT_AS]}
                return {"permissions": [ops.ACT_AS] if self.act_as else []}
            assert api == "cloudresourcemanager" and path == f"v1/projects/{ops.PROJECT}:testIamPermissions"
            granted = body["permissions"] if self.granted is None else self.granted
            return {"permissions": [name for name in body["permissions"] if name in granted]}
        if method != "GET":
            if api == "iam" and method == "POST":
                assert self.role is None and path == f"v1/projects/{ops.PROJECT}/roles"
                self.role = {"includedPermissions": body["role"]["includedPermissions"], "stage": body["role"]["stage"]}
                return copy.deepcopy(self.role)
            if api == "storage" and method == "POST":
                environment = body["labels"]["environment"]
                assert body["name"] not in self.buckets and body["name"] == ops.BUCKETS[environment]
                self.buckets[body["name"]] = bucket(environment)
                return copy.deepcopy(self.buckets[body["name"]])
            if api == "storage" and method == "PUT":
                self.bucket_policy = copy.deepcopy(body)
                return copy.deepcopy(body)
            if api == "run" and path.endswith(":setIamPolicy"):
                self.job_policy = copy.deepcopy(body["policy"])
                return copy.deepcopy(body["policy"])
            if api == "run" and "/jobs?jobId=" in path:
                assert self.job is None
                self.job = copy.deepcopy(body)
                return {"done": True, "response": self.job}
            if api == "cloudscheduler" and method == "POST":
                assert self.schedule is None
                self.schedule = {**copy.deepcopy(body), "state": "ENABLED"}
                return copy.deepcopy(self.schedule)
            if api == "logging" and method == "POST":
                self.metric = copy.deepcopy(body)
                return copy.deepcopy(body)
            if api == "monitoring" and method == "POST":
                readback = self.policy_readback(body)
                self.policies.append(readback)
                return copy.deepcopy(readback)
            if api == "run" and path == "v2/" + ops.JOB + ":run":
                args = body.get("overrides", {}).get("containerOverrides", [{}])[0].get("args", ops.CLEANUP_ARGS)
                execution = self.execution(args)
                self.executions.insert(0, execution)
                return {"done": True, "response": execution}
            if api == "run" and path.startswith("v2/" + ops.SERVICE + "?") and method == "PATCH":
                assert path.endswith("?updateMask=template.containers")
                self.service["template"]["containers"] = copy.deepcopy(body["template"]["containers"])
                self.service["latestReadyRevision"] = ops.PARENT + "/revisions/revision-new"
                self.service["trafficStatuses"] = [{"percent": 100, "revision": "revision-new"}]
                return {"done": True, "response": self.service}
            if api == "run" and method == "PATCH":
                assert "updateMask" not in path, "v2 Job.patch has no updateMask query parameter"
                self.job = copy.deepcopy(body)
                return {"done": True, "response": self.job}
            return {}
        if api == "iam":
            return copy.deepcopy(self.role)
        if api == "storage":
            if "/iam?" in path:
                return copy.deepcopy(self.bucket_policy)
            return copy.deepcopy(self.buckets.get(path.rsplit("/", 1)[-1]))
        if api == "cloudscheduler":
            return copy.deepcopy(self.schedule)
        if api == "logging":
            return copy.deepcopy(self.metric)
        if api == "monitoring":
            if "/notificationChannels/" in path:
                return copy.deepcopy(self.channel)
            if "/alertPolicies?" in path:
                return {"alertPolicies": copy.deepcopy(self.policies)}
            if "/timeSeries?" in path:
                return {"timeSeries": [{"points": [{"value": {"int64Value": "1"}}]}]} if self.heartbeat_seen else {}
            raise AssertionError(path)
        if path == "v2/" + ops.SERVICE:
            return copy.deepcopy(self.service)
        if path == "v2/" + ops.JOB:
            return copy.deepcopy(self.job)
        if ":getIamPolicy?" in path:
            return copy.deepcopy(self.job_policy)
        if "/executions?" in path:
            return {"executions": copy.deepcopy(self.executions)}
        raise AssertionError((api, path, method, missing_ok))

    def wait(self, operation):
        # The real wait polls an unfinished operation through ops.OPERATION_READ; the fake's are already done.
        self.waits += 1
        assert operation["done"] and "error" not in operation
        return operation["response"]


def test_inspection_is_read_only_and_requires_both_current_successful_execution_modes():
    cloud = CloudFixture()
    assert ops.inspect(cloud)
    assert cloud.writes == []
    # A successful probe cannot replace the normal cleanup heartbeat; nor can a past success hide
    # a failure of the same mode. Both need the current image, bounded task and a recent timestamp.
    for mode in (ops.CLEANUP_ARGS, ops.PROBE_ARGS):
        for defect in ("failed", "old", "image", "unbounded", "missing"):
            cloud = CloudFixture()
            bad = cloud.execution(mode)
            if defect == "failed":
                bad.update(succeededCount=0, failedCount=1)
            elif defect == "old":
                bad["completionTime"] = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
            elif defect == "image":
                bad["template"]["containers"][0]["image"] = "registry.invalid/application:retired"
            elif defect == "unbounded":
                bad["template"]["containers"][0]["env"].append({"name": "DB_MAX_OVERFLOW", "value": "20"})
            else:
                cloud.executions = [e for e in cloud.executions if e["template"]["containers"][0]["args"] != mode]
            if defect != "missing":
                cloud.executions.insert(0, bad)
            with pytest.raises(ops.OperationError, match="required before enabling"):
                ops.set_enabled(cloud, cloud.service, True)
            assert cloud.writes == [], (mode, defect)


@pytest.mark.parametrize("defect", ["wrong-owner", "public", "soft-delete", "versioning", "retention",
                                  "broader-role", "disabled-role", "extra-runtime-grant", "conditional-runtime-grant",
                                  "missing-invoker", "schedule-overrides"])
def test_upload_enable_refuses_drift_without_repairing_or_weakening_it(defect):
    cloud = CloudFixture()
    actual = cloud.buckets[ops.BUCKETS["production"]]
    if defect == "wrong-owner":
        actual["labels"]["purpose"] = "sql-backups"
    elif defect == "public":
        cloud.bucket_policy["bindings"].append({"role": "roles/storage.objectViewer", "members": ["allUsers"]})
    elif defect == "soft-delete":
        actual["softDeletePolicy"]["retentionDurationSeconds"] = "604800"
    elif defect == "versioning":
        actual["versioning"]["enabled"] = True
    elif defect == "retention":
        actual["retentionPolicy"] = {"retentionPeriod": "31536000"}
    elif defect == "broader-role":
        cloud.role["includedPermissions"].append("storage.objects.list")
    elif defect == "disabled-role":
        cloud.role["stage"] = "DISABLED"
    elif defect == "extra-runtime-grant":
        cloud.bucket_policy["bindings"].append({"role": "roles/storage.objectAdmin", "members": ["serviceAccount:runtime@example.invalid"]})
    elif defect == "conditional-runtime-grant":
        cloud.bucket_policy["bindings"][0]["condition"] = {"expression": "true"}
    elif defect == "missing-invoker":
        cloud.job_policy["bindings"] = []
    else:
        cloud.schedule["httpTarget"]["body"] = "overridden-command"
    with pytest.raises(ops.OperationError):
        ops.set_enabled(cloud, cloud.service, True)
    assert cloud.writes == []


def test_cleanup_spec_copies_only_required_secret_references_and_caps_resources():
    original = service()
    spec = ops.job_spec(original)
    task = spec["template"]["template"]
    container = task["containers"][0]
    assert spec["template"]["taskCount"] == spec["template"]["parallelism"] == 1
    assert task["timeout"] == "600s" and task["maxRetries"] == 1
    assert container["resources"]["limits"] == {"cpu": "1", "memory": "512Mi"}
    env = {item["name"]: item for item in container["env"]}
    assert {key for key, value in env.items() if "valueSource" in value} == {"DATABASE_URL", "SECRET_KEY"}
    assert env["DB_POOL_SIZE"]["value"] == "1" and env["DB_MAX_OVERFLOW"]["value"] == "0"
    assert env["FEEDBACK_MEDIA_ENABLED"]["value"] == "false"
    assert "RESEND_API_KEY" not in env
    original["template"]["containers"][0]["env"][0] = {"name": "DATABASE_URL", "value": "inline-value"}
    with pytest.raises(ops.OperationError, match="secret references"):
        ops.job_spec(original)


@pytest.mark.parametrize("status_fields", [
    {}, {"verificationStatus": "VERIFICATION_STATUS_UNSPECIFIED"}, {"verificationStatus": "VERIFIED"},
], ids=["observed-omitted-default", "explicit-default", "verified"])
def test_provision_runs_cleanup_and_storage_probe_without_changing_the_scheduled_command(status_fields, capsys):
    cloud = CloudFixture()
    cloud.channel.update(status_fields)
    ops.provision(cloud, cloud.service)
    runs = [call for call in cloud.writes if call[1].endswith(":run")]
    assert [call[3] for call in runs] == [
        {}, {"overrides": {"containerOverrides": [{"name": "cleanup", "args": ops.PROBE_ARGS}]}},
    ]
    assert cloud.job["template"]["template"]["containers"][0]["args"] == ops.CLEANUP_ARGS
    assert all(call[1] != "v2/" + ops.SERVICE for call in cloud.writes)
    output = capsys.readouterr().out
    assert "end-to-end delivery unverified" in output
    assert "enabled and verified" not in output
    assert "PRIVATE_RECIPIENT_SENTINEL" not in output


def test_binding_preserves_conditional_grants_and_policy_etag():
    cloud = CloudFixture()
    cloud.bucket_policy["bindings"] = [{"role": "roles/storage.objectViewer", "members": ["user:reviewer@example.invalid"],
                                         "condition": {"title": "bounded", "expression": "request.time < timestamp('2026-01-01T00:00:00Z')"}}]
    ops.bind(cloud, "storage", "storage/v1/b/" + ops.BUCKETS["production"], ops.ROLE,
             "serviceAccount:runtime@example.invalid", storage=True)
    assert "optionsRequestedPolicyVersion=3" in cloud.calls[0][1]
    policy = cloud.writes[0][3]
    assert policy["version"] == 3 and policy["etag"] == "bucket-version"
    assert policy["bindings"][0] == cloud.bucket_policy["bindings"][0]


def test_enable_changes_only_media_configuration_and_disable_does_not_need_storage():
    cloud = CloudFixture()
    before = copy.deepcopy(cloud.service)
    ops.set_enabled(cloud, cloud.service, True)
    assert len(cloud.writes) == 1
    request = cloud.writes[0][3]
    assert request["etag"] == "service-version"
    env = request["template"]["containers"][0]["env"]
    assert env[:-2] == before["template"]["containers"][0]["env"]
    assert env[-2:] == [{"name": "FEEDBACK_MEDIA_BUCKET", "value": ops.BUCKETS["production"]},
                       {"name": "FEEDBACK_MEDIA_ENABLED", "value": "true"}]
    assert cloud.job["template"]["template"]["containers"][0]["args"] == ops.CLEANUP_ARGS
    cloud.calls.clear()
    cloud.role = None
    ops.set_enabled(cloud, cloud.service, False)
    assert len(cloud.writes) == 1
    assert all(call[0] == "run" for call in cloud.calls)
    assert cloud.writes[0][3]["template"]["containers"][0]["env"][-1]["value"] == "false"


@pytest.mark.parametrize("defect", ["disabled-channel", "unverified-channel", "unknown-channel-status",
                                  "null-channel-status", "wrong-channel-type", "wrong-channel-name",
                                  "missing-channel-enabled", "missing-policy",
                                  "wrong-policy-channel", "disabled-policy", "wrong-policy-filter", "foreign-policy",
                                  "nonzero-threshold", "null-threshold", "boolean-threshold", "string-threshold",
                                  "missing-threshold-duration", "extra-threshold-field",
                                  "metric-filter-drift", "missing-heartbeat"])
def test_enable_requires_live_alert_routing_and_the_normal_cleanup_heartbeat(defect, capsys):
    cloud = CloudFixture()
    if defect == "disabled-channel":
        cloud.channel["enabled"] = False
    elif defect == "unverified-channel":
        cloud.channel["verificationStatus"] = "UNVERIFIED"
    elif defect == "unknown-channel-status":
        cloud.channel["verificationStatus"] = "UNKNOWN_FUTURE_STATUS"
    elif defect == "null-channel-status":
        cloud.channel["verificationStatus"] = None
    elif defect == "wrong-channel-type":
        cloud.channel["type"] = "webhook_tokenauth"
    elif defect == "wrong-channel-name":
        cloud.channel["name"] = "projects/example/notificationChannels/unrelated"
    elif defect == "missing-channel-enabled":
        del cloud.channel["enabled"]
    elif defect == "missing-policy":
        cloud.policies.pop()
    elif defect == "wrong-policy-channel":
        cloud.policies[0]["notificationChannels"] = ["projects/example/notificationChannels/unrelated"]
    elif defect == "disabled-policy":
        cloud.policies[0]["enabled"] = False
    elif defect == "wrong-policy-filter":
        cloud.policies[0]["conditions"][0]["conditionThreshold"]["filter"] = 'resource.type = "cloud_run_revision"'
    elif defect == "foreign-policy":
        cloud.policies[0]["userLabels"] = {"component": "unrelated"}
    elif defect in ("nonzero-threshold", "null-threshold", "boolean-threshold", "string-threshold"):
        cloud.policies[0]["conditions"][0]["conditionThreshold"]["thresholdValue"] = {
            "nonzero-threshold": 1, "null-threshold": None, "boolean-threshold": False, "string-threshold": "0",
        }[defect]
    elif defect == "missing-threshold-duration":
        del cloud.policies[0]["conditions"][0]["conditionThreshold"]["duration"]
    elif defect == "extra-threshold-field":
        cloud.policies[0]["conditions"][0]["conditionThreshold"]["evaluationMissingData"] = "EVALUATION_MISSING_DATA_ACTIVE"
    elif defect == "metric-filter-drift":
        cloud.metric["filter"] = 'resource.type = "cloud_run_job"'
    else:
        cloud.heartbeat_seen = False
    if "channel" in defect and defect != "wrong-policy-channel":
        with pytest.raises(ops.OperationError):
            ops.provision(cloud, cloud.service)
        assert cloud.writes == []
    with pytest.raises(ops.OperationError):
        ops.set_enabled(cloud, cloud.service, True)
    assert cloud.writes == []
    assert "PRIVATE_RECIPIENT_SENTINEL" not in capsys.readouterr().out


@pytest.mark.parametrize("omit_zero_threshold", [True, False], ids=["protobuf-default", "explicit-zero"])
def test_monitoring_creation_is_feature_scoped_and_reuses_the_eligible_email_channel(omit_zero_threshold):
    cloud = CloudFixture(omit_zero_threshold=omit_zero_threshold)
    cloud.metric, cloud.policies = None, []
    ops.ensure_monitoring(cloud)
    assert len(cloud.writes) == 3
    assert all("notificationChannels" not in path for _api, path, _method, _body in cloud.writes)
    assert cloud.metric["metricDescriptor"] == {"metricKind": "DELTA", "valueType": "INT64", "unit": "1"}
    assert 'resource.labels.job_name="earningsnerd-feedback-media-cleanup"' in cloud.metric["filter"]
    assert 'resource.labels.location="us-west1"' in cloud.metric["filter"]
    assert ops.HEARTBEAT_MESSAGE in cloud.metric["filter"]
    assert len(cloud.policies) == 2
    for policy in cloud.policies:
        assert policy["notificationChannels"] == [ops.CHANNEL]
        assert policy["userLabels"] == {"component": "feedback-media"}
        condition = policy["conditions"][0]
        actual = condition.get("conditionThreshold") or condition["conditionAbsent"]
        assert 'resource.type = "cloud_run_job"' in actual["filter"]
        assert 'resource.labels.job_name = "earningsnerd-feedback-media-cleanup"' in actual["filter"]
        assert 'resource.labels.location = "us-west1"' in actual["filter"]
        if "conditionThreshold" in condition:
            assert 'metric.label.result = "failed"' in actual["filter"]
            assert actual["comparison"] == "COMPARISON_GT" and actual["duration"] == "0s"
            if omit_zero_threshold:
                assert "thresholdValue" not in actual
            else:
                assert actual["thresholdValue"] == 0
        else:
            assert actual["duration"] == "7200s"
            assert "logging.googleapis.com/user/earningsnerd_feedback_cleanup_success" in actual["filter"]
    # Creation and subsequent list/readback both accept the provider representation.
    # The comparison must not mutate the readback or the approved request's explicit zero.
    policies = copy.deepcopy(cloud.policies)
    assert ops.inspect_monitoring(cloud)
    assert cloud.policies == policies
    assert cloud.writes[1][3]["conditions"][0]["conditionThreshold"]["thresholdValue"] == 0


@pytest.mark.parametrize("mode", ["normal", "probe", "dry-run", "overdue", "ledger-failure"])
def test_only_committed_successful_normal_cleanup_emits_the_monitoring_heartbeat(monkeypatch, caplog, mode):
    from app import database
    from app.services import feedback_media_cleanup_service as cleanup
    from app.services import feedback_storage_worker_service as storage
    from app.services import job_run_service as jobs

    spec = importlib.util.spec_from_file_location("feedback_cleanup_cli", ROOT / "backend/scripts/feedback_media_cleanup.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    stats = {"overdue": int(mode == "overdue"), "errors": 0}

    class Attempt:
        def record(self, _stats):
            pass

    @contextmanager
    def track(_name, *, dry_run):
        yield Attempt()
        if mode == "ledger-failure":
            raise jobs.JobRunFailed("ledger failure")

    monkeypatch.setattr(jobs, "track_job", track)
    monkeypatch.setattr(database, "SessionLocal", object())
    monkeypatch.setattr(storage, "BoundedFeedbackStorage", lambda _bucket: object())
    monkeypatch.setattr(cleanup, "run_feedback_media_cleanup", lambda *_args, **_kwargs: stats)
    monkeypatch.setattr(cleanup, "verify_feedback_media_storage", lambda *_args: stats)
    with caplog.at_level(logging.INFO):
        if mode in {"overdue", "ledger-failure"}:
            with pytest.raises(jobs.JobRunFailed):
                cli._main(dry_run=False, batch_size=1)
        else:
            cli._main(dry_run=mode == "dry-run", batch_size=1, verify_storage=mode == "probe")
    messages = [record.getMessage() for record in caplog.records]
    assert (ops.HEARTBEAT_MESSAGE in messages) is (mode == "normal")


def step_permissions(steps):
    """The IAM permissions named by provider-call labels such as 'Bucket read [storage.buckets.get]'."""
    named = set()
    for label in steps:
        match = re.fullmatch(r".+ \[(.+)\]", label or "")
        if match:
            named.update(match.group(1).split(", "))
    return named


def test_provisioning_preflight_names_exactly_the_permissions_its_steps_use():
    """Rule 12 gate: a provisioning step whose permission the preflight does not test could fail mid-apply.

    Provision from nothing (every create path) and over existing resources (every update path); every provider
    call must carry a step label, and the labels' project permissions must equal PROVISION_PERMISSIONS.
    """
    used = set()
    for absent in (True, False):
        cloud = CloudFixture(absent=absent)
        ops.provision(cloud, cloud.service)
        assert None not in cloud.steps, [call for call, label in zip(cloud.calls, cloud.steps) if label is None]
        used |= step_permissions(cloud.steps)
        if cloud.waits:  # the real wait polls an unfinished operation through this step
            used |= step_permissions([ops.OPERATION_READ])
    assert ops.ACT_AS in used
    assert used - {ops.ACT_AS} == ops.PROVISION_PERMISSIONS, (
        sorted(used - {ops.ACT_AS} - ops.PROVISION_PERMISSIONS), sorted(ops.PROVISION_PERMISSIONS - used))


def test_provision_from_nothing_tests_its_capability_before_its_first_write(capsys):
    cloud = CloudFixture(absent=True)
    ops.provision(cloud, cloud.service)
    first_write = cloud.calls.index(cloud.writes[0])
    capability = [i for i, call in enumerate(cloud.calls) if call[1].endswith(":testIamPermissions")]
    assert len(capability) == 2 and max(capability) < first_write
    assert cloud.role["includedPermissions"] == ops.PERMISSIONS and cloud.job["labels"] == {"purpose": "feedback-media"}
    assert set(cloud.buckets) == set(ops.BUCKETS.values()) and cloud.schedule["state"] == "ENABLED"
    assert cloud.metric == ops.heartbeat_spec() and len(cloud.policies) == 2
    assert any(b["role"] == "roles/run.invoker" for b in cloud.job_policy["bindings"])
    assert "Private storage probe and cleanup succeeded" in capsys.readouterr().out


@pytest.mark.parametrize("missing", ["logging.logMetrics.create", "iam.roles.create", "run.jobs.runWithOverrides",
                                     "act-as", "malformed-answer"])
def test_provision_refuses_before_any_write_when_its_identity_lacks_a_permission(missing):
    cloud = CloudFixture(absent=True)
    if missing == "act-as":
        cloud.act_as = False
        expected = "iam.serviceAccounts.actAs on the API runtime identity"
    elif missing == "malformed-answer":
        cloud.granted = []
        expected = "logging.logMetrics.create"
    else:
        cloud.granted = ops.PROVISION_PERMISSIONS - {missing}
        expected = missing
    with pytest.raises(ops.OperationError, match="lacks required permissions; nothing was changed") as refused:
        ops.provision(cloud, cloud.service)
    assert expected in str(refused.value) and "runtime@example.invalid" not in str(refused.value)
    assert cloud.writes == []


@pytest.mark.parametrize("state", ["absent", "deleted", "disabled", "differs"])
def test_inspection_names_the_role_state_and_still_reports_every_other_component(state, capsys):
    cloud = CloudFixture()
    cloud.buckets.pop(ops.BUCKETS["preview"])
    if state == "absent":
        cloud.role = None
    elif state == "deleted":
        cloud.role["deleted"] = True
    elif state == "disabled":
        cloud.role["stage"] = "DISABLED"
    else:
        cloud.role["includedPermissions"] = ["storage.objects.create", "storage.objects.get", "storage.objects.list",
                                             "resourcemanager.projects.setIamPolicy"]
    if state == "absent":
        assert ops.inspect(cloud) is False  # not yet provisioned is incomplete, not drift
    else:
        with pytest.raises(ops.OperationError, match="prerequisites refused: Feedback object role$"):
            ops.inspect(cloud)
    output = capsys.readouterr().out
    assert {
        "absent": "Feedback object role: absent",
        "deleted": "Feedback object role is deleted",
        "disabled": "Feedback object role stage is DISABLED",
        "differs": "lacks storage.objects.delete; adds storage.objects.list; adds 1 other permission(s)",
    }[state] in output
    assert "resourcemanager" not in output  # an unknown extra permission is counted, never named
    for line in ("production bucket: private retention settings verified", "preview bucket: absent",
                 "Cleanup last execution: succeeded", "Normal-cleanup monitoring heartbeat: observed"):
        assert line in output
    assert cloud.writes == []


def test_inspection_of_an_unprovisioned_project_reports_absence_not_refusal(capsys):
    cloud = CloudFixture(absent=True)
    assert ops.inspect(cloud) is False
    output = capsys.readouterr().out
    for line in ("Feedback object role: absent", "production bucket: absent", "preview bucket: absent",
                 "Cleanup job: absent; hourly schedule: absent",
                 "Feedback cleanup monitoring: absent heartbeat metric, policy 'EarningsNerd feedback media cleanup failed', "
                 "policy 'EarningsNerd feedback media cleanup stale'"):
        assert line in output
    assert "refused" not in output and cloud.writes == []
    with pytest.raises(ops.OperationError, match="required before enabling"):
        ops.set_enabled(cloud, cloud.service, True)
    assert cloud.writes == []


def provider(body, code=403):
    cloud = object.__new__(ops.Cloud)
    cloud.token = "synthetic-token"

    def refuse(request, timeout):
        raise HTTPError(request.full_url, code, "refused", {}, io.BytesIO(body if isinstance(body, bytes) else json.dumps(body).encode()))
    return cloud, refuse


@pytest.mark.parametrize("body, detail", [
    ({"error": {"code": 403, "status": "PERMISSION_DENIED", "message": "Permission denied for PRINCIPAL_SENTINEL@example.invalid",
                "details": [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": "IAM_PERMISSION_DENIED",
                             "domain": "iam.googleapis.com", "metadata": {"permission": "logging.logMetrics.create",
                                                                          "resource": "projects/RESOURCE_SENTINEL"}}]}},
     "; PERMISSION_DENIED; IAM_PERMISSION_DENIED; denied logging.logMetrics.create"),
    ({"error": {"code": 403, "status": "PERMISSION_DENIED", "details": [{"reason": "SERVICE_DISABLED",
                                                                       "metadata": {"consumer": "projects/RESOURCE_SENTINEL"}}]}},
     "; PERMISSION_DENIED; SERVICE_DISABLED"),
    ({"error": {"status": "PRINCIPAL_SENTINEL", "details": [{"reason": "PRINCIPAL_SENTINEL",
                                                             "metadata": {"permission": "PRINCIPAL_SENTINEL.read"}}]}}, ""),
    (b"<html>PRINCIPAL_SENTINEL</html>", ""),
], ids=["iam-denial", "api-disabled", "unknown-values", "not-json"])
def test_a_refused_provider_call_names_its_step_and_closed_error_class_never_its_payload(monkeypatch, body, detail):
    cloud, refuse = provider(body)
    monkeypatch.setattr(ops, "urlopen", refuse)
    with pytest.raises(ops.OperationError) as refused:
        cloud.call("logging", "v2/projects/earnings-nerd/metrics", method="POST", body={}, step=ops.METRIC_CREATE)
    assert str(refused.value) == f"Heartbeat metric create [logging.logMetrics.create] failed (HTTP 403{detail})"
    assert "SENTINEL" not in str(refused.value)
    with pytest.raises(ops.OperationError, match=r"^logging operation failed \(HTTP 403"):
        cloud.call("logging", "v2/projects/earnings-nerd/metrics")  # unlabelled callers keep the old wording
    monkeypatch.setattr(ops, "urlopen", provider(body, code=404)[1])
    assert cloud.call("iam", "v1/" + ops.ROLE, missing_ok=True, step=ops.ROLE_READ) is None


def test_inspection_reports_each_operations_capability_without_writing(capsys):
    cloud = CloudFixture()
    cloud.granted = ops.PROVISION_PERMISSIONS - {"logging.logMetrics.create", "monitoring.alertPolicies.create"}
    ops.report_capabilities(cloud, cloud.service)
    output = capsys.readouterr().out
    assert ("Capability for feedback-media-provision-apply: missing logging.logMetrics.create, "
            "monitoring.alertPolicies.create") in output
    assert "Capability for feedback-media-verify-apply: missing " in output and "resourcemanager.projects.setIamPolicy" in output
    assert cloud.writes == [] and "runtime@example.invalid" not in output

    def unreadable(api, path, **kwargs):
        raise ops.OperationError(kwargs["step"] + " failed (HTTP 403)")
    cloud.call = unreadable
    ops.report_capabilities(cloud, cloud.service)
    assert "Capability for feedback-media-provision-apply: unverified (Capability preflight" in capsys.readouterr().out


@pytest.mark.parametrize("which", ["cleanup", "probe"])
def test_a_reported_execution_failure_stops_provisioning_without_waiting_out_readiness(monkeypatch, which):
    cloud = CloudFixture()
    original = cloud.call

    def call(api, path, **kwargs):
        result = original(api, path, **kwargs)
        is_probe = "overrides" in (kwargs.get("body") or {})
        if path.endswith(":run") and is_probe == (which == "probe"):
            result["response"].update(succeededCount=0, failedCount=1)
        return result
    cloud.call = call
    monkeypatch.setattr(ops.time, "sleep", lambda _seconds: pytest.fail("provisioning waited after a reported failure"))
    label = {"cleanup": "Cleanup execution", "probe": "Storage probe execution"}[which]
    with pytest.raises(ops.OperationError, match=f"^{label} did not succeed"):
        ops.provision(cloud, cloud.service)
