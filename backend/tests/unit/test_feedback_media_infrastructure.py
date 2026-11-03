"""Private feedback resources are bounded and uploads require independent cleanup/storage proof.

Provider responses and calls are synthetic; no credentials, cloud mutations or user data are used.
The existing Ops wiring gate covers the owner approval and main-ref boundaries for every -apply.
"""
from __future__ import annotations

import copy
import http.client
import importlib.util
import io
import json
import logging
import re
import types
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


API_IMAGE = "us-west1-docker.pkg.dev/earnings-nerd/earningsnerd/backend"


def service():
    return {
        "etag": "service-version", "template": {
            "serviceAccount": "runtime@example.invalid",
            "containers": [{"image": API_IMAGE + ":verified", "env": [
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
    def __init__(self, *, omit_zero_threshold=True, absent=False, pending=False):
        self.calls = []
        self.steps = []
        self.waits = 0
        # pending=True answers each Cloud Run write with an unfinished operation that its first poll finds done,
        # for a test that drives the real Cloud.wait.
        self.pending = pending
        self.operations = {}
        self.omit_zero_threshold = omit_zero_threshold
        self.service = service()
        self.job = ops.job_spec(self.service)
        self.job["etag"] = "job-version"
        self.role = {"includedPermissions": ops.PERMISSIONS.copy(), "stage": "GA"}
        self.buckets = {name: bucket(environment) for environment, name in ops.BUCKETS.items()}
        # One policy per bucket, as GCS keeps them.
        self.bucket_policies = {name: {"version": 3, "etag": "bucket-version", "bindings": [
            {"role": ops.ROLE, "members": ["serviceAccount:runtime@example.invalid"]},
        ]} for name in self.buckets}
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
        # capability_answer replaces the project answer outright (a malformed one); fail_paths refuses a read.
        self.granted = None
        self.act_as = True
        self.image_read = True
        self.capability_answer = None
        self.fail_paths = {}
        if absent:
            # A project no provisioning has reached: the state every recorded feedback-media run left.
            self.role, self.job, self.schedule, self.metric = None, None, None, None
            self.buckets, self.policies, self.executions = {}, [], []
            self.bucket_policies = {}
            self.job_policy = {"version": 3, "etag": "job-policy-version", "bindings": []}

    def policy_of(self, name):
        # A bucket created without a policy of its own starts with no bindings.
        return self.bucket_policies.setdefault(name, {"version": 3, "etag": "bucket-version", "bindings": []})

    @property
    def bucket_policy(self):
        """The production bucket's policy, which the drift cases edit."""
        return self.policy_of(ops.BUCKETS["production"])

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

    def operation(self, response):
        if not self.pending:
            return {"done": True, "response": response}
        name = f"{ops.PARENT}/operations/operation-{len(self.operations)}"
        self.operations["v2/" + name] = {"name": name, "done": True, "response": copy.deepcopy(response)}
        return {"name": name, "done": False}

    @property
    def writes(self):
        # testIamPermissions is a POST that reads the caller's own grants; it changes nothing.
        return [call for call in self.calls if call[2] != "GET" and not call[1].endswith(":testIamPermissions")]

    def call(self, api, path, *, method="GET", body=None, missing_ok=False, step=None):
        self.calls.append((api, path, method, copy.deepcopy(body)))
        self.steps.append(step)
        if path in self.fail_paths:
            raise ops.ProviderError(f"{step} failed (HTTP {self.fail_paths[path]})")
        if path.endswith(":testIamPermissions"):
            assert method == "POST" and step == ops.CAPABILITY_READ
            if api == "iam":
                assert body == {"permissions": [ops.ACT_AS]}
                return {"permissions": [ops.ACT_AS] if self.act_as else []}
            if api == "artifactregistry":
                assert path == f"v1/{ops.IMAGE_REPOSITORY}:testIamPermissions" and body == {"permissions": [ops.IMAGE_READ]}
                return {"permissions": [ops.IMAGE_READ] if self.image_read else []}
            assert api == "cloudresourcemanager" and path == f"v1/projects/{ops.PROJECT}:testIamPermissions"
            if self.capability_answer is not None:
                return copy.deepcopy(self.capability_answer)
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
                self.bucket_policies[body["name"]] = {"version": 3, "etag": "bucket-version", "bindings": []}
                return copy.deepcopy(self.buckets[body["name"]])
            if api == "storage" and method == "PUT":
                assert path.endswith("/iam")
                self.bucket_policies[path.split("/b/", 1)[1].split("/", 1)[0]] = copy.deepcopy(body)
                return copy.deepcopy(body)
            if api == "run" and path.endswith(":setIamPolicy"):
                self.job_policy = copy.deepcopy(body["policy"])
                return copy.deepcopy(body["policy"])
            if api == "run" and "/jobs?jobId=" in path:
                assert self.job is None
                self.job = copy.deepcopy(body)
                return self.operation(self.job)
            if api == "cloudscheduler" and method == "POST":
                assert self.schedule is None
                self.schedule = {**copy.deepcopy(body), "state": "ENABLED"}
                return copy.deepcopy(self.schedule)
            if api == "cloudscheduler" and method == "PATCH":
                self.schedule.update({field: copy.deepcopy(body[field]) for field in path.split("updateMask=", 1)[1].split(",")})
                if self.schedule.get("state") == "UPDATE_FAILED":  # Google's recovery: retry the update until it succeeds
                    self.schedule["state"] = "ENABLED"
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
                return self.operation(execution)
            if api == "run" and path.startswith("v2/" + ops.SERVICE + "?") and method == "PATCH":
                assert path.endswith("?updateMask=template.containers")
                self.service["template"]["containers"] = copy.deepcopy(body["template"]["containers"])
                self.service["latestReadyRevision"] = ops.PARENT + "/revisions/revision-new"
                self.service["trafficStatuses"] = [{"percent": 100, "revision": "revision-new"}]
                return self.operation(self.service)
            if api == "run" and method == "PATCH":
                assert "updateMask" not in path, "v2 Job.patch has no updateMask query parameter"
                self.job = copy.deepcopy(body)
                return self.operation(self.job)
            return {}
        found = self.stored(api, path)
        if found is None:
            # Google answers an absent resource with 404, which Cloud.call returns as None only when the caller allows it.
            if not missing_ok:
                raise ops.ProviderError(f"{step or api + ' operation'} failed (HTTP 404; NOT_FOUND)")
            return None
        return copy.deepcopy(found)

    def stored(self, api, path):
        if api == "iam":
            return self.role
        if api == "storage":
            # An absent bucket's policy read is a 404 too, like the bucket's own.
            name = path.split("/b/", 1)[1].split("/", 1)[0].split("?", 1)[0]
            if name not in self.buckets:
                return None
            return self.policy_of(name) if "/iam?" in path else self.buckets[name]
        if api == "cloudscheduler":
            return self.schedule
        if api == "logging":
            return self.metric
        if api == "monitoring":
            if "/notificationChannels/" in path:
                return self.channel
            if "/alertPolicies?" in path:
                return {"alertPolicies": self.policies}
            if "/timeSeries?" in path:
                return {"timeSeries": [{"points": [{"value": {"int64Value": "1"}}]}]} if self.heartbeat_seen else {}
            raise AssertionError(path)
        if path == "v2/" + ops.SERVICE:
            return self.service
        if path == "v2/" + ops.JOB:
            return self.job
        # An absent job's policy and execution list read as 404, like the job's own.
        if ":getIamPolicy?" in path:
            return self.job_policy if self.job is not None else None
        if "/executions?" in path:
            return {"executions": self.executions} if self.job is not None else None
        if path in self.operations:
            return self.operations[path]
        raise AssertionError((api, path))

    def wait(self, operation, step=None):
        # The real wait polls an unfinished operation through ops.OPERATION_READ; these are already done
        # (the provisioning gate drives the real one with pending=True).
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
                bad["template"]["containers"][0]["image"] = API_IMAGE + ":retired"
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
                                  "missing-invoker", "schedule-overrides", "foreign-schedule", "paused-schedule"])
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
    elif defect == "foreign-schedule":
        cloud.schedule["description"] = "Another team's hourly job"
    elif defect == "paused-schedule":
        cloud.schedule["state"] = "PAUSED"
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
    assert ops.inspect_policies(cloud) and ops.inspect_heartbeat(cloud)
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


LABEL = re.compile(r".+ \[[a-z][\w.]*(?:, [a-z][\w.]*)*\]")
# The permission verbs each HTTP method can need: a read names only reads, and a write names what it changes,
# with actAs beside a create or update that runs as an identity. Whether it is the exact permission stays review-checked.
METHOD_VERBS = {"GET": {"get", "list", "getIamPolicy"}, "PUT": {"setIamPolicy"},
                "PATCH": {"update", "actAs", "downloadArtifacts"},
                "POST": {"create", "run", "runWithOverrides", "setIamPolicy", "actAs", "downloadArtifacts"}}


def label_problems(calls, steps):
    """Calls whose label names no permission, or one its HTTP method cannot need, or that carry the capability label
    off a capability read (or vice versa)."""
    problems = []
    for (api, path, method, _body), label in zip(calls, steps):
        capability = method == "POST" and path.endswith(":testIamPermissions")
        verbs = {name.rsplit(".", 1)[-1] for name in step_permissions([label])}
        fits = bool(verbs - {"actAs", "downloadArtifacts"}) and verbs <= METHOD_VERBS.get(method, set())
        if capability != (label == ops.CAPABILITY_READ) or (not capability and not (LABEL.fullmatch(label or "") and fits)):
            problems.append((api, path, method, label))
    return problems


def test_provisioning_preflight_names_exactly_the_permissions_its_steps_use(monkeypatch):
    """Rule 12 gate: a provisioning step whose permission the preflight does not test could fail mid-apply.

    Provision from nothing (every create path) and over existing resources (every update path), with the real
    Cloud.wait polling each Cloud Run operation. Every provider call must carry a step label naming permissions its
    HTTP method can need, and the labels' project permissions must equal PROVISION_PERMISSIONS.
    """
    # Planted: the forms earlier versions of this gate let through, beside the ones it already caught.
    for call, label in ((("run", "v2/job:run", "POST", {}), "Cleanup execution"),
                        (("run", "v2/job", "GET", None), ops.CAPABILITY_READ),
                        (("cloudresourcemanager", "v1/project:testIamPermissions", "POST", {}), ops.METRIC_READ),
                        (("logging", "v2/metrics", "POST", {}), None),
                        (("iam", "v1/role", "PATCH", {}), ops.ROLE_READ),
                        (("iam", "v1/role", "GET", None), ops.ROLE_CREATE),
                        (("run", "v2/job", "PATCH", {}), ops.JOB_CREATE)):
        assert label_problems([call], [label]) == [(*call[:3], label)], (call, label)
    assert label_problems([("logging", "v2/metric", "GET", None), ("run", "v2/job", "PATCH", {})],
                          [ops.METRIC_READ, ops.JOB_UPDATE]) == []
    monkeypatch.setattr(ops.time, "sleep", lambda _seconds: None)
    used = set()
    for absent in (True, False):
        cloud = CloudFixture(absent=absent, pending=True)
        cloud.wait = types.MethodType(ops.Cloud.wait, cloud)
        ops.provision(cloud, cloud.service)
        assert ops.OPERATION_READ in cloud.steps  # the real poll ran, under its own label
        assert label_problems(cloud.calls, cloud.steps) == []
        used |= step_permissions(cloud.steps)
    # actAs and image read are tested on their own resources (the runtime identity, the image repository).
    resource_scoped = {ops.ACT_AS, ops.IMAGE_READ}
    assert resource_scoped <= used
    assert used - resource_scoped == ops.PROVISION_PERMISSIONS, (
        sorted(used - resource_scoped - ops.PROVISION_PERMISSIONS), sorted(ops.PROVISION_PERMISSIONS - used))


def founder_bootstrapped():
    """The state the founder's one-time owner commands leave: the object role, both buckets and their runtime grants."""
    cloud = CloudFixture(absent=True)
    cloud.role = {"includedPermissions": ops.PERMISSIONS.copy(), "stage": "GA"}
    cloud.buckets = {name: bucket(environment) for environment, name in ops.BUCKETS.items()}
    for name in cloud.buckets:
        cloud.policy_of(name)["bindings"] = [{"role": ops.ROLE, "members": ["serviceAccount:runtime@example.invalid"]}]
    return cloud


def unbound():
    """Existing buckets and job whose runtime grants are still missing: the grant steps run, the creates do not."""
    cloud = CloudFixture()
    for name in cloud.buckets:
        cloud.policy_of(name)["bindings"] = []
    cloud.job_policy["bindings"] = []
    return cloud


def split_bindings():
    """Grants held through a later binding of the same role: present, so neither planned nor written."""
    cloud = CloudFixture()
    other, runtime = "serviceAccount:other@example.invalid", "serviceAccount:runtime@example.invalid"
    for name in cloud.buckets:
        cloud.policy_of(name)["bindings"] = [{"role": ops.ROLE, "members": [other]}, {"role": ops.ROLE, "members": [runtime]}]
    cloud.job_policy["bindings"] = [{"role": "roles/run.invoker", "members": [other]},
                                    {"role": "roles/run.invoker", "members": [runtime]}]
    return cloud


MIXED = ("preview-unbound", "preview-absent", "production-absent", "job-invoker-conditional", "job-runtime-other-role",
         "one-alert-policy-absent")


def mixed(kind):
    """States whose buckets, job grant or alert policies differ from one another, as an interrupted run leaves them."""
    cloud = CloudFixture()
    preview, runtime = ops.BUCKETS["preview"], "serviceAccount:runtime@example.invalid"
    if kind == "preview-unbound":
        cloud.policy_of(preview)["bindings"] = []
    elif kind == "preview-absent":
        del cloud.buckets[preview]
        cloud.bucket_policies.pop(preview)
    elif kind == "production-absent":
        production = ops.BUCKETS["production"]
        del cloud.buckets[production]
        cloud.bucket_policies.pop(production)
    elif kind == "job-invoker-conditional":
        cloud.job_policy["bindings"] = [{"role": "roles/run.invoker", "members": [runtime],
                                         "condition": {"title": "fixture", "expression": "true"}}]
    elif kind == "job-runtime-other-role":
        cloud.job_policy["bindings"] = [{"role": "roles/run.viewer", "members": [runtime]}]
    else:
        cloud.policies = cloud.policies[:1]
    return cloud


@pytest.mark.parametrize("state", ["absent", "existing", "bootstrapped", "unbound", "split-bindings", *MIXED])
def test_provision_tests_exactly_the_writes_its_state_needs(monkeypatch, state):
    """Rule 12 gate: the write set a run tests equals the write permissions its write labels name, for each state."""
    monkeypatch.setattr(ops.time, "sleep", lambda _seconds: None)
    states = {"absent": lambda: CloudFixture(absent=True), "existing": CloudFixture, "bootstrapped": founder_bootstrapped,
              "unbound": unbound, "split-bindings": split_bindings, **{kind: (lambda kind=kind: mixed(kind)) for kind in MIXED}}
    cloud = states[state]()
    ops.provision(cloud, cloud.service)
    project_tests = [body["permissions"] for api, path, _method, body in cloud.calls
                     if api == "cloudresourcemanager" and path.endswith(":testIamPermissions")]
    assert len(project_tests) == 2 and set(project_tests[0]) == ops.PROVISION_READS
    written = step_permissions(label for (_api, _path, method, _body), label in zip(cloud.calls, cloud.steps)
                               if method != "GET" and label != ops.CAPABILITY_READ) - {ops.ACT_AS, ops.IMAGE_READ}
    assert set(project_tests[1]) == written
    if state == "bootstrapped":
        assert not written & {"iam.roles.create", "storage.buckets.create", "storage.buckets.setIamPolicy"}
    if state in ("existing", "split-bindings"):
        assert written == {"run.jobs.update", "cloudscheduler.jobs.update", "run.jobs.run", "run.jobs.runWithOverrides"}
    if state == "unbound":
        assert {"storage.buckets.setIamPolicy", "run.jobs.setIamPolicy"} <= written
        assert not written & {"iam.roles.create", "storage.buckets.create", "run.jobs.create"}
    if state in MIXED:
        expected = {"preview-unbound": {"storage.buckets.setIamPolicy"},
                    "preview-absent": {"storage.buckets.create", "storage.buckets.setIamPolicy"},
                    "production-absent": {"storage.buckets.create", "storage.buckets.setIamPolicy"},
                    "job-invoker-conditional": {"run.jobs.setIamPolicy"}, "job-runtime-other-role": {"run.jobs.setIamPolicy"},
                    "one-alert-policy-absent": {"monitoring.alertPolicies.create"}}[state]
        assert written == expected | {"run.jobs.update", "cloudscheduler.jobs.update", "run.jobs.run", "run.jobs.runWithOverrides"}


def test_a_founder_bootstrap_provisions_without_role_bucket_or_bucket_grant_permissions(monkeypatch):
    monkeypatch.setattr(ops.time, "sleep", lambda _seconds: None)
    cloud = founder_bootstrapped()
    cloud.granted = ops.PROVISION_PERMISSIONS - {"iam.roles.create", "storage.buckets.create", "storage.buckets.setIamPolicy"}
    ops.provision(cloud, cloud.service)
    assert not any(api in ("iam", "storage") and method != "GET" for api, _path, method, _body in cloud.writes)
    # The same grants refuse a project the founder has not bootstrapped, before any write.
    cloud = CloudFixture(absent=True)
    cloud.granted = ops.PROVISION_PERMISSIONS - {"iam.roles.create", "storage.buckets.create", "storage.buckets.setIamPolicy"}
    with pytest.raises(ops.OperationError, match="nothing was changed: iam.roles.create, storage.buckets.create, "
                                                 "storage.buckets.setIamPolicy$"):
        ops.provision(cloud, cloud.service)
    assert cloud.writes == []


DENIED_READS = {
    "channel-denied": "v3/" + ops.CHANNEL, "metric-denied": ops.METRIC_PATH,
    "alert-list-denied": f"v3/projects/{ops.PROJECT}/alertPolicies?pageSize=100",
    "bucket-denied": "storage/v1/b/" + ops.BUCKETS["production"], "job-denied": "v2/" + ops.JOB,
    "job-policy-denied": ops.policy_path("v2/" + ops.JOB), "schedule-denied": "v1/" + ops.SCHEDULE,
}


@pytest.mark.parametrize("read, refusal", [
    ("bucket-policy-members-string", "Resource policy is malformed"),
    ("bucket-policy-bindings-object", "Resource policy is malformed"),
    ("job-policy-condition-string", "Resource policy is malformed"),
    ("bucket-labels-list", "Bucket answer is malformed"),
    ("metric-descriptor-list", "Heartbeat metric answer is malformed"),
    ("job-labels-string", "Cleanup job answer is malformed"),
    ("alert-policy-not-object", "Alert policy answer is malformed"),
    ("bucket-policy-denied", "Bucket policy read [storage.buckets.getIamPolicy] failed (HTTP 403)"),
    ("role-denied", "Object role read [iam.roles.get] failed (HTTP 403)"),
    ("bucket-policy-no-etag", "Resource policy has no etag"),
    ("job-policy-no-etag", "Resource policy has no etag"),
    ("alert-page-not-list", "Alert policy answer is malformed"),
    ("alert-conditions-number", "Alert policy answer is malformed"),
    ("alert-conditions-object", "Alert policy answer is malformed"),
    ("channel-denied", "Alert channel read [monitoring.notificationChannels.get] failed (HTTP 403)"),
    ("metric-denied", "Heartbeat metric read [logging.logMetrics.get] failed (HTTP 403)"),
    ("alert-list-denied", "Alert policy list [monitoring.alertPolicies.list] failed (HTTP 403)"),
    ("bucket-denied", "Bucket read [storage.buckets.get] failed (HTTP 403)"),
    ("job-denied", "Cleanup job read [run.jobs.get] failed (HTTP 403)"),
    ("job-policy-denied", "Cleanup job policy read [run.jobs.getIamPolicy] failed (HTTP 403)"),
    ("schedule-denied", "Cleanup schedule read [cloudscheduler.jobs.get] failed (HTTP 403)"),
])
def test_provision_refuses_a_malformed_or_denied_read_before_any_write_never_planning_it(read, refusal):
    """A denied read is never planned as absent, and a malformed answer never as approved: both refuse first."""
    cloud = founder_bootstrapped() if read.startswith("bucket-") else CloudFixture()
    production = ops.BUCKETS["production"]
    if read == "bucket-policy-members-string":
        # A string would match the runtime by substring and plan no grant.
        cloud.policy_of(production)["bindings"] = [{"role": ops.ROLE, "members": "serviceAccount:runtime@example.invalid"}]
    elif read == "bucket-policy-bindings-object":
        cloud.policy_of(production)["bindings"] = {"role": ops.ROLE, "members": ["serviceAccount:runtime@example.invalid"]}
    elif read == "job-policy-condition-string":
        cloud.job_policy["bindings"][0]["condition"] = "true"
    elif read == "bucket-labels-list":
        cloud.buckets[production]["labels"] = ["purpose", "feedback-media"]
    elif read == "metric-descriptor-list":
        cloud.metric["metricDescriptor"] = []
    elif read == "job-labels-string":
        cloud.job["labels"] = "purpose=feedback-media"
    elif read == "alert-policy-not-object":
        cloud.policies.append("PRIVATE_POLICY_SENTINEL")
    elif read == "bucket-policy-no-etag":
        del cloud.policy_of(production)["etag"]  # its write-back would not be conditional
    elif read == "job-policy-no-etag":
        cloud.job_policy["bindings"] = []  # a grant to add, on a policy whose write-back could not be conditional
        del cloud.job_policy["etag"]
    elif read == "alert-page-not-list":
        cloud.policies = 7
    elif read == "alert-conditions-number":
        cloud.policies[0]["conditions"] = 5
    elif read == "alert-conditions-object":
        cloud.policies[0]["conditions"] = {"name": "PRIVATE_POLICY_SENTINEL"}
    elif read in DENIED_READS:
        cloud.fail_paths[DENIED_READS[read]] = 403
    elif read == "bucket-policy-denied":
        cloud.fail_paths[ops.policy_path("storage/v1/b/" + production, storage=True)] = 403
    else:
        cloud.fail_paths["v1/" + ops.ROLE] = 403
    with pytest.raises(ops.OperationError) as refused:
        ops.provision(cloud, cloud.service)
    assert str(refused.value).startswith(refusal) and "SENTINEL" not in str(refused.value)
    assert cloud.writes == []
    # Planning stopped at the read: the write permissions were never tested.
    assert len([call for call in cloud.calls if call[0] == "cloudresourcemanager"]) == 1


@pytest.mark.parametrize("bindings", [
    "allUsers",
    "",
    {},
    {"role": "roles/storage.objectViewer", "members": ["allUsers"]},
    [["roles/storage.objectViewer", "allUsers"]],
    [{"role": "roles/storage.objectViewer", "members": "allUsers"}],
    [{"role": ["roles/storage.objectViewer"], "members": ["allUsers"]}],
    [{"role": "roles/storage.objectViewer", "members": [{"member": "allUsers"}]}],
    [{"role": "roles/storage.objectViewer", "members": ["allUsers"], "condition": "true"}],
], ids=["string", "empty-string", "empty-object", "object", "binding-not-object", "members-string", "role-list",
        "member-object", "condition-string"])
def test_a_malformed_policy_never_reads_as_private_or_granted(bindings):
    policy = {"version": 3, "etag": "v", "bindings": bindings}
    for check in (ops.check_private_policy, lambda p: ops.bound(p, "roles/storage.objectViewer", "allUsers"),
                  lambda p: ops.check_runtime_bucket_policy(p, "runtime@example.invalid", granted=False)):
        with pytest.raises(ops.OperationError, match="^Resource policy is malformed$"):
            check(policy)


@pytest.mark.parametrize("case", ["second-binding", "no-members", "no-etag"])
def test_bind_writes_exactly_when_the_planners_bound_test_is_false(case):
    """A member already in any unconditional binding of the role is not re-granted, so a plan that read the grant as
    present never meets an untested setIamPolicy; a binding without members still takes one; an etag-less policy is
    refused before any write, since its write-back would not be conditional."""
    cloud = CloudFixture()
    production, member = ops.BUCKETS["production"], "serviceAccount:runtime@example.invalid"
    if case == "second-binding":
        cloud.policy_of(production)["bindings"] = [{"role": ops.ROLE, "members": ["serviceAccount:other@example.invalid"]},
                                                   {"role": ops.ROLE, "members": [member]}]
    elif case == "no-members":
        cloud.policy_of(production)["bindings"] = [{"role": ops.ROLE}]
    else:  # a grant to add, on a policy whose write-back could not be conditional
        cloud.policy_of(production)["bindings"] = []
        del cloud.policy_of(production)["etag"]
    assert ops.bound(cloud.policy_of(production), ops.ROLE, member) is (case == "second-binding")
    if case == "no-etag":
        with pytest.raises(ops.OperationError, match="^Resource policy has no etag$"):
            ops.bind(cloud, "storage", "storage/v1/b/" + production, ops.ROLE, member, storage=True)
        assert cloud.writes == []
        return
    ops.bind(cloud, "storage", "storage/v1/b/" + production, ops.ROLE, member, storage=True)
    assert (len(cloud.writes) == 1) is (case == "no-members")
    assert ops.bound(cloud.policy_of(production), ops.ROLE, member)
    if case == "no-members":
        assert cloud.writes[0][3]["etag"] == "bucket-version"  # the write-back is conditional on the read


def test_provision_reads_are_exactly_the_reads_its_runs_make(monkeypatch):
    """The first stage tests PROVISION_READS on every run, so it must hold reads only, and every read the runs make."""
    monkeypatch.setattr(ops.time, "sleep", lambda _seconds: None)
    read_verbs = METHOD_VERBS["GET"]
    assert all(name.rsplit(".", 1)[-1] in read_verbs for name in ops.PROVISION_READS)
    assert not any(name.rsplit(".", 1)[-1] in read_verbs for name in ops.EVERY_RUN_WRITES | ops.CONDITIONAL_WRITES)
    read = set()
    for make in (lambda: CloudFixture(absent=True), CloudFixture, founder_bootstrapped, unbound):
        cloud = make()
        cloud.pending = True
        cloud.wait = types.MethodType(ops.Cloud.wait, cloud)
        ops.provision(cloud, cloud.service)
        read |= step_permissions(label for (_api, _path, method, _body), label in zip(cloud.calls, cloud.steps)
                                 if method == "GET")
    assert read == ops.PROVISION_READS


@pytest.mark.parametrize("shape", ["template-list", "containers-object"])
def test_inspection_refuses_a_malformed_component_without_a_traceback(capsys, shape):
    cloud = CloudFixture()
    if shape == "template-list":
        cloud.job["template"] = ["not", "an", "object"]
    else:  # one entry, but not a list: reading its first container is a missing index
        cloud.job["template"]["template"]["containers"] = {"name": "cleanup"}
    with pytest.raises(ops.OperationError, match=re.escape("prerequisites refused: Cleanup job") + "$"):
        ops.inspect(cloud)
    output = capsys.readouterr().out
    assert "Cleanup job: refused (answer is malformed)" in output and "Cleanup hourly schedule: verified" in output
    assert cloud.writes == []


def test_provision_from_nothing_tests_its_capability_before_its_first_write(capsys):
    cloud = CloudFixture(absent=True)
    ops.provision(cloud, cloud.service)
    first_write = cloud.calls.index(cloud.writes[0])
    capability = [i for i, call in enumerate(cloud.calls) if call[1].endswith(":testIamPermissions")]
    # Reads, actAs and image read, then the writes this state needs: all before the first write.
    assert len(capability) == 4 and max(capability) < first_write
    assert ("artifactregistry", f"v1/{ops.IMAGE_REPOSITORY}:testIamPermissions") in {call[:2] for call in cloud.calls}
    assert cloud.role["includedPermissions"] == ops.PERMISSIONS and cloud.job["labels"] == {"purpose": "feedback-media"}
    assert set(cloud.buckets) == set(ops.BUCKETS.values()) and cloud.schedule["state"] == "ENABLED"
    assert cloud.metric == ops.heartbeat_spec() and len(cloud.policies) == 2
    assert any(b["role"] == "roles/run.invoker" for b in cloud.job_policy["bindings"])
    assert "Private storage probe and cleanup succeeded" in capsys.readouterr().out


@pytest.mark.parametrize("missing", ["logging.logMetrics.create", "iam.roles.create", "run.jobs.runWithOverrides",
                                     "storage.buckets.getIamPolicy", "act-as", "image-read", "nothing-granted",
                                     "string-answer", "non-string-entries", "no-list"])
def test_provision_refuses_before_any_write_when_its_identity_lacks_a_permission(missing):
    cloud = CloudFixture(absent=True)
    expected = sorted(ops.PROVISION_READS)  # an answer that grants nothing, or cannot be read, stops at the reads
    if missing == "act-as":
        cloud.act_as = False
        expected = ["iam.serviceAccounts.actAs on the API runtime identity"]
    elif missing == "image-read":
        cloud.image_read = False
        expected = ["artifactregistry.repositories.downloadArtifacts on the API image repository"]
    elif missing == "nothing-granted":
        cloud.granted = []
    elif missing == "string-answer":
        cloud.capability_answer = {"permissions": "logging.logMetrics.create"}
    elif missing == "non-string-entries":
        cloud.capability_answer = {"permissions": [None, 7, {"name": "iam.roles.create"}]}
    elif missing == "no-list":
        cloud.capability_answer = {"granted": sorted(ops.PROVISION_PERMISSIONS)}
    else:
        cloud.granted = ops.PROVISION_PERMISSIONS - {missing}
        expected = [missing]
    with pytest.raises(ops.OperationError, match="lacks required permissions; nothing was changed") as refused:
        ops.provision(cloud, cloud.service)
    assert str(refused.value).endswith(": " + ", ".join(expected))
    assert "runtime@example.invalid" not in str(refused.value)
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
                 "Cleanup job: absent", "Cleanup hourly schedule: absent", "Feature alert channel: enabled email",
                 "Feedback cleanup alert policies: absent 'EarningsNerd feedback media cleanup failed', "
                 "'EarningsNerd feedback media cleanup stale'", "Feedback cleanup heartbeat metric: absent"):
        assert line in output
    assert "refused" not in output and cloud.writes == []
    with pytest.raises(ops.OperationError, match="required before enabling"):
        ops.set_enabled(cloud, cloud.service, True)
    assert cloud.writes == []


class CutShortBody(io.RawIOBase):
    """An error body that is cut short while it is read."""

    def readable(self):
        return True

    def read(self, _size=-1):
        raise http.client.IncompleteRead(b"PRINCIPAL_SENTINEL")


def provider(body, code=403):
    cloud = object.__new__(ops.Cloud)
    cloud.token = "synthetic-token"

    def refuse(request, timeout):
        fp = body() if callable(body) else io.BytesIO(body if isinstance(body, bytes) else json.dumps(body).encode())
        raise HTTPError(request.full_url, code, "refused", {}, fp)
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
                                                             "metadata": {"permission": "PRINCIPAL_SENTINEL.read"}}]}},
     "; denied an unlisted permission"),
    (b"<html>PRINCIPAL_SENTINEL</html>", ""),
    ({"error": {"status": ["PERMISSION_DENIED"], "details": [{"reason": ["IAM_PERMISSION_DENIED"]}, {"reason": {"a": 1}},
                                                             {"metadata": {"permission": ["logging.logMetrics.create"]}}]}}, ""),
    ({"error": {"status": "PERMISSION_DENIED", "details": [{"reason": "IAM_PERMISSION_DENIED",
                                                            "metadata": {"permission": "iam.PRINCIPALSENTINEL.read"}}]}},
     "; PERMISSION_DENIED; IAM_PERMISSION_DENIED; denied an unlisted permission"),
    (b'{"error": ' + b"[" * 100000 + b"]" * 100000 + b"}", ""),
    ({"error": "PRINCIPAL_SENTINEL"}, ""),
    (CutShortBody, ""),
], ids=["iam-denial", "api-disabled", "unknown-values", "not-json", "unhashable-values", "unlisted-permission",
        "nested-beyond-recursion", "non-object-error", "body-cut-short"])
def test_a_refused_provider_call_names_its_step_and_closed_error_class_never_its_payload(monkeypatch, body, detail):
    cloud, refuse = provider(body)
    monkeypatch.setattr(ops, "urlopen", refuse)
    with pytest.raises(ops.ProviderError) as refused:
        cloud.call("logging", "v2/projects/earnings-nerd/metrics", method="POST", body={}, step=ops.METRIC_CREATE)
    assert str(refused.value) == f"Heartbeat metric create [logging.logMetrics.create] failed (HTTP 403{detail})"
    assert "SENTINEL" not in str(refused.value)
    with pytest.raises(ops.OperationError, match=r"^logging operation failed \(HTTP 403"):
        cloud.call("logging", "v2/projects/earnings-nerd/metrics")  # unlabelled callers keep the old wording
    monkeypatch.setattr(ops, "urlopen", provider(body, code=404)[1])
    assert cloud.call("iam", "v1/" + ops.ROLE, missing_ok=True, step=ops.ROLE_READ) is None


def test_every_permission_a_step_label_names_can_be_named_in_a_refusal():
    """A refusal names its denied permission only from KNOWN_PERMISSIONS, so that set must hold every label's."""
    named = step_permissions(value for name, value in vars(ops).items() if name.isupper() and isinstance(value, str))
    assert {ops.ACT_AS, ops.IMAGE_READ, "run.services.update"} <= named
    assert named <= ops.KNOWN_PERMISSIONS, sorted(named - ops.KNOWN_PERMISSIONS)


@pytest.mark.parametrize("code", [400, 403, 409, 429, 500])
def test_only_a_404_reads_as_absent(monkeypatch, code):
    """A read that may find its resource absent takes only a 404 as absent: any other refusal stops it, labelled, so a
    denied read is never planned as a create."""
    cloud, refuse = provider({"error": {"code": code, "status": "PERMISSION_DENIED"}}, code=code)
    monkeypatch.setattr(ops, "urlopen", refuse)
    with pytest.raises(ops.ProviderError, match="^" + re.escape(f"Object role read [iam.roles.get] failed (HTTP {code}; ")):
        cloud.call("iam", "v1/" + ops.ROLE, missing_ok=True, step=ops.ROLE_READ)


@pytest.mark.parametrize("change, refusal", [
    ("job-relabelled", "Existing cleanup job is not owned by this feature"),
    ("schedule-foreign", "Existing cleanup schedule is not owned by this feature"),
    ("job-policy-public", "Resource policy includes a public principal"),
    ("bucket-drift", "production bucket differs from approved private retention settings"),
    ("role-disabled", "Feedback object role stage is DISABLED"),
    ("job-etag-moved", None),
])
def test_each_write_step_rechecks_what_it_writes_after_the_plan(monkeypatch, change, refusal):
    """The plan's reads can be stale when a step writes. Each step re-reads what it writes, refuses it if it is no
    longer this feature's, and writes under the etag it reads then: the write-time ownership and etag checks."""
    monkeypatch.setattr(ops.time, "sleep", lambda _seconds: None)
    # The bucket and role checks guard the bucket grants, so those cases start where the grants are still to be made.
    cloud = unbound() if change in ("bucket-drift", "role-disabled") else CloudFixture()
    production, tested = ops.BUCKETS["production"], []
    original = cloud.call

    def call(api, path, **kwargs):
        if api == "cloudresourcemanager" and path.endswith(":testIamPermissions"):
            tested.append(path)
            if len(tested) == 2:  # the plan is complete; the state changes before the first write
                if change == "job-relabelled":
                    cloud.job["labels"]["purpose"] = "sql-backups"
                elif change == "schedule-foreign":
                    cloud.schedule["description"] = "Another team's hourly job"
                elif change == "job-policy-public":
                    cloud.job_policy["bindings"].append({"role": "roles/run.invoker", "members": ["allUsers"]})
                elif change == "bucket-drift":
                    cloud.buckets[production]["versioning"]["enabled"] = True
                elif change == "role-disabled":
                    cloud.role["stage"] = "DISABLED"
                else:
                    cloud.job["etag"] = "job-version-2"
        return original(api, path, **kwargs)
    cloud.call = call
    if refusal is None:
        ops.provision(cloud, cloud.service)
        patches = [body for api, path, method, body in cloud.writes if api == "run" and method == "PATCH"]
        assert len(patches) == 1 and patches[0]["etag"] == "job-version-2"  # read at write time, not at the plan
        return
    with pytest.raises(ops.OperationError, match="^" + re.escape(refusal)):
        ops.provision(cloud, cloud.service)
    written = {(api, method) for api, _path, method, _body in cloud.writes}
    assert {"job-relabelled": ("run", "PATCH"), "schedule-foreign": ("cloudscheduler", "PATCH"),
            "job-policy-public": ("run", "POST"), "bucket-drift": ("storage", "PUT"),
            "role-disabled": ("storage", "PUT")}[change] not in written


def test_inspection_reports_each_operations_capability_without_writing(capsys):
    cloud = CloudFixture(absent=True)
    cloud.granted = ops.PROVISION_PERMISSIONS - {"logging.logMetrics.create", "monitoring.alertPolicies.create"}
    ops.report_capabilities(cloud, cloud.service)
    output = capsys.readouterr().out
    assert ("Capability for feedback-media-provision-apply: missing logging.logMetrics.create, "
            "monitoring.alertPolicies.create") in output
    # The owner-equivalent grant is never a standing requirement: verify-inspect reports it only while it is needed.
    assert "Capability for feedback-media-verify-apply (every run): missing " in output
    assert "resourcemanager.projects.setIamPolicy" not in output
    assert cloud.writes == [] and "runtime@example.invalid" not in output
    # On the existing state those creates are not needed, so the same grants suffice.
    cloud = CloudFixture()
    cloud.granted = ops.PROVISION_PERMISSIONS - {"logging.logMetrics.create", "monitoring.alertPolicies.create"}
    ops.report_capabilities(cloud, cloud.service)
    assert "Capability for feedback-media-provision-apply: all required permissions present" in capsys.readouterr().out
    cloud = CloudFixture()

    def unreadable(api, path, **kwargs):
        raise ops.ProviderError(kwargs["step"] + " failed (HTTP 403)")
    cloud.call = unreadable
    ops.report_capabilities(cloud, cloud.service)
    assert "Capability for feedback-media-provision-apply: UNVERIFIED (Capability preflight" in capsys.readouterr().out
    cloud = CloudFixture()
    del cloud.service["template"]["serviceAccount"]
    ops.report_capabilities(cloud, cloud.service)
    assert ("Capability for feedback-media-provision-apply: UNVERIFIED (API runtime identity unavailable"
            in capsys.readouterr().out)


@pytest.mark.parametrize("which, report", [
    ("cleanup", {"succeededCount": 0, "failedCount": 1}),
    ("probe", {"succeededCount": 0, "failedCount": 1}),
    ("probe", {"succeededCount": 0, "cancelledCount": 1}),
    ("probe", {"succeededCount": 0}),  # completed, with completionTime, yet nothing succeeded
], ids=["cleanup-failed", "probe-failed", "probe-cancelled", "probe-completed-without-success"])
def test_a_reported_execution_failure_stops_provisioning_without_waiting_out_readiness(monkeypatch, which, report):
    cloud = CloudFixture()
    original = cloud.call

    def call(api, path, **kwargs):
        result = original(api, path, **kwargs)
        is_probe = "overrides" in (kwargs.get("body") or {})
        if path.endswith(":run") and is_probe == (which == "probe"):
            assert result["response"]["completionTime"]
            result["response"].update(report)
        return result
    cloud.call = call
    monkeypatch.setattr(ops.time, "sleep", lambda _seconds: pytest.fail("provisioning waited after a reported failure"))
    label = {"cleanup": "Cleanup execution", "probe": "Storage probe execution"}[which]
    with pytest.raises(ops.OperationError, match=f"^{label} did not succeed"):
        ops.provision(cloud, cloud.service)


def test_an_unfinished_execution_report_falls_through_to_the_readiness_check():
    # The run operation may finish before its execution does; only a reported failure stops provisioning early.
    ops.require_execution_success({"succeededCount": 0, "taskCount": 1}, "Storage probe execution")
    ops.require_execution_success({}, "Storage probe execution")


@pytest.mark.parametrize("error, status", [
    ({"code": 7, "message": "PRINCIPAL_SENTINEL"}, "PERMISSION_DENIED"),
    ({"code": 16}, "UNAUTHENTICATED"),
    ({"code": 0}, "unclassified"),
    ({"code": 99}, "unclassified"),
    ({"code": "7"}, "unclassified"),
    ({"code": True}, "unclassified"),
    ("PRINCIPAL_SENTINEL", "unclassified"),
])
def test_a_failed_cloud_run_operation_names_only_its_step_and_closed_status(error, status):
    cloud = object.__new__(ops.Cloud)
    with pytest.raises(ops.ProviderError) as failed:
        cloud.wait({"done": True, "error": error}, ops.PROBE_RUN)
    assert str(failed.value) == (f"Storage probe execution [run.jobs.run, run.jobs.runWithOverrides]: "
                                 f"Cloud Run operation failed ({status}); provider payload withheld")
    with pytest.raises(ops.ProviderError) as failed:
        cloud.wait({"done": True, "error": error})  # unlabelled callers (the verifier's) keep the old wording
    assert str(failed.value) == f"Cloud Run operation failed ({status}); provider payload withheld"


def test_monitoring_with_no_metric_still_refuses_a_drifted_owned_policy(capsys):
    cloud = CloudFixture()
    cloud.metric = None
    cloud.policies[0]["enabled"] = False
    with pytest.raises(ops.OperationError, match="prerequisites refused: Alert policies$"):
        ops.inspect(cloud)
    output = capsys.readouterr().out
    assert "Alert policies: refused (Feedback cleanup alert policies must exactly match" in output
    assert "Feedback cleanup heartbeat metric: absent" in output and cloud.writes == []


@pytest.mark.parametrize("drift", [False, True], ids=["unreadable-only", "unreadable-and-drift"])
def test_an_unreadable_component_is_unverified_and_never_masks_readable_drift(capsys, drift):
    cloud = CloudFixture()
    cloud.fail_paths["storage/v1/b/" + ops.BUCKETS["production"]] = 403
    if drift:
        cloud.role["stage"] = "DISABLED"
    expected = ("prerequisites refused: Feedback object role (also unverified: production bucket)" if drift
                else "prerequisites unverified: production bucket")
    with pytest.raises(ops.OperationError, match=re.escape(expected) + "$"):
        ops.inspect(cloud)
    output = capsys.readouterr().out
    assert "production bucket: UNVERIFIED (Bucket read [storage.buckets.get] failed (HTTP 403))" in output
    for line in ("preview bucket: private retention settings verified", "Cleanup last execution: succeeded",
                 "Normal-cleanup monitoring heartbeat: observed"):
        assert line in output
    assert ("Feedback object role: refused" in output) is drift and cloud.writes == []
    with pytest.raises(ops.OperationError):
        ops.set_enabled(cloud, cloud.service, True)
    assert cloud.writes == []


@pytest.mark.parametrize("unreadable, unverified, refused", [
    ("v1/" + ops.SCHEDULE, "Cleanup schedule", "Cleanup job"),
    ("v3/" + ops.CHANNEL, "Alert channel", "Alert policies"),
    (ops.METRIC_PATH, "Heartbeat metric", "Alert policies"),
], ids=["schedule-unreadable-job-drift", "channel-unreadable-policy-drift", "metric-unreadable-policy-drift"])
def test_a_failed_read_never_stops_another_resources_drift_check(capsys, unreadable, unverified, refused):
    """Each independently readable resource is its own component, so one failed read cannot hide another's drift."""
    cloud = CloudFixture()
    cloud.fail_paths[unreadable] = 403
    if refused == "Cleanup job":
        cloud.job["template"]["template"]["containers"][0]["image"] = API_IMAGE + ":retired"
    else:
        cloud.policies[0]["enabled"] = False
    with pytest.raises(ops.OperationError, match=re.escape(f"refused: {refused} (also unverified: {unverified})") + "$"):
        ops.inspect(cloud)
    output = capsys.readouterr().out
    assert f"{unverified}: UNVERIFIED (" in output and f"{refused}: refused (" in output
    assert cloud.writes == []


@pytest.mark.parametrize("state, refusal", [
    ("role-deleted", "Feedback object role is deleted"),
    ("role-disabled", "Feedback object role stage is DISABLED"),
    ("role-differs", "Feedback object role differs from object create/get/delete: adds storage.objects.list"),
    ("bucket-settings", "production bucket differs from approved private retention settings"),
    ("bucket-public", "Resource policy includes a public principal"),
    ("bucket-other-runtime-grant", "Runtime bucket grants differ from the approved unconditional object role"),
    ("foreign-job", "Existing cleanup job is not owned by this feature"),
    ("job-public", "Resource policy includes a public principal"),
    ("foreign-schedule", "Existing cleanup schedule is not owned by this feature"),
    ("preview-settings-production-absent", "preview bucket differs from approved private retention settings"),
    ("schedule-paused", "Existing cleanup schedule is PAUSED; provisioning does not resume it"),
    ("schedule-disabled", "Existing cleanup schedule is DISABLED; provisioning does not resume it"),
    ("schedule-unrecognized", "Existing cleanup schedule is in an unrecognized state; provisioning does not resume it"),
    ("metric-drift", "Feedback cleanup heartbeat metric is missing, disabled or differs"),
    ("second-policy-drift", "Existing feedback monitoring policy differs from the approved owned definition"),
])
def test_provision_refuses_a_state_it_would_not_repair_before_any_write(state, refusal):
    """Steps create what is absent and converge what this feature owns; anything they would refuse is refused first."""
    cloud = CloudFixture(absent=True)
    production = ops.BUCKETS["production"]
    if state.startswith("role-"):
        cloud.role = {"includedPermissions": ops.PERMISSIONS.copy(), "stage": "GA",
                      **({"deleted": True} if state == "role-deleted" else {})}
        if state == "role-disabled":
            cloud.role["stage"] = "DISABLED"
        elif state == "role-differs":
            cloud.role["includedPermissions"].append("storage.objects.list")
    elif state.startswith("bucket-"):
        cloud.buckets[production] = bucket("production")
        if state == "bucket-settings":
            cloud.buckets[production]["versioning"]["enabled"] = True
        else:
            member, role = (("allUsers", "roles/storage.objectViewer") if state == "bucket-public"
                            else ("serviceAccount:runtime@example.invalid", "roles/storage.objectAdmin"))
            cloud.bucket_policy["bindings"].append({"role": role, "members": [member]})
    elif state in ("foreign-job", "job-public"):
        cloud.job = {"labels": {"purpose": "sql-backups" if state == "foreign-job" else "feedback-media"}, "etag": "v"}
        cloud.job_policy["bindings"].append({"role": "roles/run.invoker", "members": ["allUsers"]})
    elif state == "foreign-schedule":
        cloud.schedule = {"description": "Another team's hourly job"}
    elif state == "preview-settings-production-absent":  # an absent bucket must not end the planner's bucket checks
        preview = ops.BUCKETS["preview"]
        cloud.buckets[preview] = bucket("preview")
        cloud.buckets[preview]["versioning"]["enabled"] = True
    elif state.startswith("schedule-"):
        known = {"schedule-paused": "PAUSED", "schedule-disabled": "DISABLED"}
        cloud.schedule = {"description": ops.SCHEDULE_DESCRIPTION, "state": known.get(state, "PRIVATE_STATE_SENTINEL")}
    elif state == "metric-drift":
        cloud.metric = {**ops.heartbeat_spec(), "filter": 'resource.type="cloud_run_job"'}
    else:  # the first policy is absent; the second exists in another form
        cloud.policies = [cloud.policy_readback(ops.policy_specs()[1])]
        cloud.policies[0]["enabled"] = False
    with pytest.raises(ops.OperationError, match=re.escape(refusal)) as refused:
        ops.provision(cloud, cloud.service)
    assert cloud.writes == []
    assert "PRIVATE_STATE_SENTINEL" not in str(refused.value)


def test_inspection_names_the_state_of_an_owned_schedule_provisioning_will_not_resume(capsys):
    """A paused owned schedule reads as refused, naming its state; one left UPDATE_FAILED, which provisioning's update
    recovers, reads as unverified and names that state."""
    cloud = CloudFixture()
    cloud.schedule["state"] = "PAUSED"
    with pytest.raises(ops.OperationError, match=re.escape("prerequisites refused: Cleanup schedule") + "$"):
        ops.inspect(cloud)
    output = capsys.readouterr().out
    assert "Cleanup schedule: refused (Existing cleanup schedule is PAUSED; provisioning does not resume it)" in output
    cloud.schedule["state"] = "UPDATE_FAILED"
    assert ops.inspect(cloud) is False
    assert "Cleanup hourly schedule: unverified (state UPDATE_FAILED)" in capsys.readouterr().out
    assert cloud.writes == []


def test_provision_still_converges_drift_in_resources_this_feature_owns(monkeypatch):
    monkeypatch.setattr(ops.time, "sleep", lambda _seconds: pytest.fail("provisioning waited for readiness"))
    cloud = CloudFixture()
    cloud.job["template"]["template"]["containers"][0]["image"] = API_IMAGE + ":retired"
    cloud.schedule["httpTarget"]["body"] = "overridden-command"
    cloud.schedule["state"] = "UPDATE_FAILED"
    # An interrupted provision (or a hand-made bucket) leaves a bucket in the approved shape without its runtime grant.
    preview = ops.BUCKETS["preview"]
    cloud.bucket_policies[preview]["bindings"] = []
    ops.provision(cloud, cloud.service)
    assert cloud.job["template"]["template"]["containers"][0]["image"] == API_IMAGE + ":verified"
    assert cloud.schedule["httpTarget"]["body"] == "e30=" and cloud.schedule["state"] == "ENABLED"
    assert cloud.bucket_policies[preview]["bindings"] == [
        {"role": ops.ROLE, "members": ["serviceAccount:runtime@example.invalid"]}]


class Dropped:
    """A response whose body is cut short after the headers arrived."""

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def read(self, _limit):
        raise http.client.IncompleteRead(b"partial")


@pytest.mark.parametrize("failure", [
    http.client.RemoteDisconnected("closed before a response"), ConnectionResetError(104, "reset"),
    TimeoutError("timed out"), None,
], ids=["remote-disconnected", "connection-reset", "timeout", "incomplete-read"])
def test_a_dropped_connection_is_an_unreadable_provider_call_not_a_traceback(monkeypatch, failure):
    cloud = object.__new__(ops.Cloud)
    cloud.token = "synthetic-token"

    def urlopen(_request, timeout):
        if failure is None:
            return Dropped()
        raise failure
    monkeypatch.setattr(ops, "urlopen", urlopen)
    with pytest.raises(ops.ProviderError) as unreadable:
        cloud.call("storage", "storage/v1/b/" + ops.BUCKETS["production"], missing_ok=True, step=ops.BUCKET_READ)
    assert str(unreadable.value) == "Bucket read [storage.buckets.get] unavailable or unreadable"


@pytest.mark.parametrize("operation", ops.OPERATIONS)
def test_only_the_inspect_operation_prints_the_capability_report(monkeypatch, capsys, operation):
    cloud = CloudFixture()
    monkeypatch.setattr(ops, "Cloud", lambda: cloud)
    monkeypatch.setattr(ops.sys, "argv", ["manage.py", operation])
    ops.main()
    output = capsys.readouterr().out
    assert ("Capability for feedback-media-provision-apply: all required permissions present" in output) is (
        operation == "feedback-media-inspect")
    assert ("Capability for" in output) is (operation == "feedback-media-inspect")
    if operation == "feedback-media-disable-apply":
        assert {call[0] for call in cloud.calls} == {"run"}


@pytest.mark.parametrize("image", [
    "registry.invalid/application:verified",  # not Artifact Registry
    "us-west1-docker.pkg.dev/other-project/earningsnerd/backend:verified",  # another project's repository
    "us-west1-docker.pkg.dev/earnings-nerd/other-repository/backend:verified",
    "us-west1-docker.pkg.dev/earnings-nerd/earningsnerd/backend:verified/../x",
    "",
])
def test_provision_refuses_an_api_image_outside_the_tested_repository_before_any_call(image, capsys):
    cloud = CloudFixture(absent=True)
    cloud.service["template"]["containers"][0]["image"] = image
    with pytest.raises(ops.OperationError, match="^API image is outside the approved Artifact Registry repository$"):
        ops.provision(cloud, cloud.service)
    assert cloud.calls == []  # refused before the preflight and every write
    ops.report_capabilities(cloud, cloud.service)
    output = capsys.readouterr().out
    assert ("Capability for feedback-media-provision-apply: UNVERIFIED "
            "(API image is outside the approved Artifact Registry repository)") in output
    assert image == "" or image not in output


def test_inspection_reports_a_missing_image_read_for_both_operations(capsys):
    cloud = CloudFixture()
    cloud.image_read = False
    ops.report_capabilities(cloud, cloud.service)
    output = capsys.readouterr().out
    assert ("Capability for feedback-media-provision-apply: missing "
            "artifactregistry.repositories.downloadArtifacts on the API image repository") in output
    assert "artifactregistry.repositories.downloadArtifacts on the API image repository" in output.split(
        "Capability for feedback-media-verify-apply (every run): ", 1)[1]
    assert cloud.writes == []
