"""Private feedback resources are bounded and uploads require independent cleanup/storage proof.

Provider responses and calls are synthetic; no credentials, cloud mutations or user data are used.
The existing Ops wiring gate covers the owner approval and main-ref boundaries for every -apply.
"""
from __future__ import annotations

import copy
import importlib.util
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("feedback_media_ops", ROOT / "ops/feedback_media/manage.py")
ops = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ops)


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
    def __init__(self):
        self.calls = []
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
        self.channel = {"name": ops.CHANNEL, "type": "email", "enabled": True, "verificationStatus": "VERIFIED",
                        "labels": {"email_address": "PRIVATE_RECIPIENT_SENTINEL@example.invalid"}}
        self.metric = ops.heartbeat_spec()
        self.policies = ops.policy_specs()
        self.heartbeat_seen = True

    def execution(self, args):
        task = copy.deepcopy(self.job["template"]["template"])
        task["containers"][0]["args"] = args.copy()
        return {"template": task, "taskCount": 1, "succeededCount": 1,
                "completionTime": datetime.now(timezone.utc).isoformat()}

    @property
    def writes(self):
        return [call for call in self.calls if call[2] != "GET"]

    def call(self, api, path, *, method="GET", body=None, missing_ok=False):
        self.calls.append((api, path, method, copy.deepcopy(body)))
        if method != "GET":
            if api == "logging" and method == "POST":
                self.metric = copy.deepcopy(body)
                return copy.deepcopy(body)
            if api == "monitoring" and method == "POST":
                self.policies.append(copy.deepcopy(body))
                return copy.deepcopy(body)
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
            return copy.deepcopy(self.buckets[path.rsplit("/", 1)[-1]])
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


def test_provision_runs_cleanup_and_storage_probe_without_changing_the_scheduled_command():
    cloud = CloudFixture()
    ops.provision(cloud, cloud.service)
    runs = [call for call in cloud.writes if call[1].endswith(":run")]
    assert [call[3] for call in runs] == [
        {}, {"overrides": {"containerOverrides": [{"name": "cleanup", "args": ops.PROBE_ARGS}]}},
    ]
    assert cloud.job["template"]["template"]["containers"][0]["args"] == ops.CLEANUP_ARGS
    assert all(call[1] != "v2/" + ops.SERVICE for call in cloud.writes)


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


@pytest.mark.parametrize("defect", ["disabled-channel", "unverified-channel", "wrong-channel-type", "missing-policy",
                                  "wrong-policy-channel", "disabled-policy", "wrong-policy-filter", "foreign-policy",
                                  "metric-filter-drift", "missing-heartbeat"])
def test_enable_requires_live_alert_routing_and_the_normal_cleanup_heartbeat(defect, capsys):
    cloud = CloudFixture()
    if defect == "disabled-channel":
        cloud.channel["enabled"] = False
    elif defect == "unverified-channel":
        cloud.channel["verificationStatus"] = "UNVERIFIED"
    elif defect == "wrong-channel-type":
        cloud.channel["type"] = "webhook_tokenauth"
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
    elif defect == "metric-filter-drift":
        cloud.metric["filter"] = 'resource.type = "cloud_run_job"'
    else:
        cloud.heartbeat_seen = False
    with pytest.raises(ops.OperationError):
        ops.set_enabled(cloud, cloud.service, True)
    assert cloud.writes == []
    assert "PRIVATE_RECIPIENT_SENTINEL" not in capsys.readouterr().out


def test_monitoring_creation_is_feature_scoped_and_reuses_the_verified_channel():
    cloud = CloudFixture()
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
            assert actual["comparison"] == "COMPARISON_GT" and actual["thresholdValue"] == 0
        else:
            assert actual["duration"] == "7200s"
            assert "logging.googleapis.com/user/earningsnerd_feedback_cleanup_success" in actual["filter"]


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
