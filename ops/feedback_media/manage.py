"""Provision and inspect dedicated feedback media resources through the protected Ops workflow.

Only fixed resources in earnings-nerd/us-west1 are addressable. API errors print a closed
status, never response bodies, access tokens, service configuration or user data. Every mutation
is an explicit -apply operation, protected by ops.yml's owner approval and first-attempt gate.
"""
from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PROJECT = "earnings-nerd"
REGION = "us-west1"
PARENT = f"projects/{PROJECT}/locations/{REGION}"
SERVICE = f"{PARENT}/services/earningsnerd-backend"
JOB = f"{PARENT}/jobs/earningsnerd-feedback-media-cleanup"
SCHEDULE = f"{PARENT}/jobs/feedback-media-cleanup-hourly"
BUCKETS = {"production": "earnings-nerd-feedback-media-prod", "preview": "earnings-nerd-feedback-media-preview"}
ROLE = f"projects/{PROJECT}/roles/earningsnerdFeedbackObjects"
PERMISSIONS = ["storage.objects.create", "storage.objects.get", "storage.objects.delete"]
CLEANUP_ARGS = ["scripts/feedback_media_cleanup.py"]
PROBE_ARGS = [*CLEANUP_ARGS, "--verify-storage"]
CHANNEL = f"projects/{PROJECT}/notificationChannels/2698479126467110226"
HEARTBEAT_METRIC = "earningsnerd_feedback_cleanup_success"
HEARTBEAT_MESSAGE = "Feedback media scheduled cleanup succeeded"
MONITORING_OWNER = {"component": "feedback-media"}
OPERATIONS = (
    "feedback-media-inspect", "feedback-media-provision-apply",
    "feedback-media-enable-apply", "feedback-media-disable-apply",
)


class OperationError(RuntimeError):
    """An operational failure safe to display without provider payloads."""


class Cloud:
    def __init__(self) -> None:
        try:
            result = subprocess.run(
                ["gcloud", "auth", "print-access-token", "--quiet"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=30, check=True,
            )
            self.token = result.stdout.strip()
        except (subprocess.SubprocessError, OSError):
            raise OperationError("Cloud authentication unavailable") from None
        if not self.token:
            raise OperationError("Cloud authentication unavailable")

    def call(self, api: str, path: str, *, method: str = "GET", body: dict | None = None,
             missing_ok: bool = False) -> dict | None:
        payload = None if body is None else json.dumps(body).encode()
        request = Request(f"https://{api}.googleapis.com/{path}", data=payload, method=method,
                          headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=60) as response:  # fixed Google APIs, TLS/proxy defaults preserved
                content = response.read(2 * 1024 * 1024)
            decoded = json.loads(content) if content else {}
            if not isinstance(decoded, dict):
                raise ValueError("Expected an API object")
            return decoded
        except HTTPError as exc:
            if exc.code == 404 and missing_ok:
                return None
            raise OperationError(f"{api} operation failed (HTTP {exc.code})") from None
        except (URLError, TimeoutError, ValueError):
            raise OperationError(f"{api} operation unavailable or unreadable") from None

    def wait(self, operation: dict) -> dict:
        deadline = time.monotonic() + 180
        while not operation.get("done"):
            if time.monotonic() >= deadline:
                raise OperationError("Cloud Run operation still pending; inspect before retrying")
            time.sleep(2)
            operation = self.call("run", "v2/" + operation["name"])
        if operation.get("error"):
            raise OperationError("Cloud Run operation failed; provider payload withheld")
        return operation.get("response", {})


def check_bucket(bucket: dict, environment: str) -> None:
    labels = bucket.get("labels", {})
    iam = bucket.get("iamConfiguration", {})
    if (bucket.get("name") != BUCKETS[environment]
            or bucket.get("location", "").lower() != REGION
            or labels.get("purpose") != "feedback-media"
            or labels.get("environment") != environment
            or not iam.get("uniformBucketLevelAccess", {}).get("enabled")
            or iam.get("publicAccessPrevention") != "enforced"
            or bucket.get("versioning", {}).get("enabled", False)
            or str(bucket.get("softDeletePolicy", {}).get("retentionDurationSeconds", "0")) != "0"
            or bucket.get("softDeletePolicy", {}).get("hardDeletePause", {}).get("enabled", False)
            or bucket.get("retentionPolicy")):
        raise OperationError(f"{environment} bucket differs from approved private retention settings")


def check_private_policy(policy: dict) -> None:
    if any(member in ("allUsers", "allAuthenticatedUsers")
           for binding in policy.get("bindings", []) for member in binding.get("members", [])):
        raise OperationError("Resource policy includes a public principal")


def check_runtime_bucket_policy(policy: dict, runtime: str) -> None:
    check_private_policy(policy)
    member = "serviceAccount:" + runtime
    grants = [binding for binding in policy.get("bindings", []) if member in binding.get("members", [])]
    if not grants or any(binding.get("role") != ROLE or binding.get("condition") for binding in grants):
        raise OperationError("Runtime bucket grants differ from the approved unconditional object role")


def policy_path(path: str, *, storage: bool = False) -> str:
    # Request policy v3 so read/modify/write preserves conditional grants and their etag.
    return path + ("/iam?optionsRequestedPolicyVersion=3" if storage
                   else ":getIamPolicy?options.requestedPolicyVersion=3")


def check_role(role: dict | None) -> None:
    if (role is None or set(role.get("includedPermissions", [])) != set(PERMISSIONS)
            or role.get("deleted") or role.get("stage") == "DISABLED"):
        raise OperationError("Feedback object role differs from the approved active permissions")


def bind(cloud: Cloud, api: str, path: str, role: str, member: str, *, storage: bool = False) -> None:
    policy = cloud.call(api, policy_path(path, storage=storage))
    check_private_policy(policy)
    bindings = policy.setdefault("bindings", [])
    binding = next((b for b in bindings if b.get("role") == role and not b.get("condition")), None)
    if binding is None:
        binding = {"role": role, "members": []}
        bindings.append(binding)
    if member in binding["members"]:
        return
    binding["members"].append(member)
    cloud.call(api, path + ("/iam" if storage else ":setIamPolicy"),
               method="PUT" if storage else "POST", body=policy if storage else {"policy": policy})


def ensure_buckets(cloud: Cloud, runtime: str) -> None:
    role = cloud.call("iam", "v1/" + ROLE, missing_ok=True)
    if role is None:
        role = cloud.call("iam", f"v1/projects/{PROJECT}/roles", method="POST", body={
            "roleId": "earningsnerdFeedbackObjects", "role": {
                "title": "EarningsNerd feedback objects", "description": "Known-key private feedback images",
                "includedPermissions": PERMISSIONS, "stage": "GA",
            },
        })
    check_role(role)
    for environment, name in BUCKETS.items():
        bucket = cloud.call("storage", "storage/v1/b/" + name, missing_ok=True)
        if bucket is None:
            bucket = cloud.call("storage", f"storage/v1/b?project={PROJECT}", method="POST", body={
                "name": name, "location": REGION, "storageClass": "STANDARD",
                "labels": {"purpose": "feedback-media", "environment": environment},
                "iamConfiguration": {"uniformBucketLevelAccess": {"enabled": True}, "publicAccessPrevention": "enforced"},
                "versioning": {"enabled": False}, "softDeletePolicy": {"retentionDurationSeconds": "0"},
            })
        # Never weaken or adopt an unrelated pre-existing bucket with this name.
        check_bucket(bucket, environment)
        bind(cloud, "storage", "storage/v1/b/" + name, ROLE, "serviceAccount:" + runtime, storage=True)
        check_runtime_bucket_policy(cloud.call("storage", policy_path("storage/v1/b/" + name, storage=True)), runtime)
        print(f"{environment} bucket: private, uniform access, no versioning or soft delete")


def heartbeat_spec() -> dict:
    return {
        "name": HEARTBEAT_METRIC,
        "description": "Successful normal feedback media cleanup; excludes storage probes and dry runs.",
        "filter": (f'resource.type="cloud_run_job" AND resource.labels.job_name="{JOB.rsplit("/", 1)[-1]}" '
                   f'AND resource.labels.location="{REGION}" '
                   f'AND (textPayload:"{HEARTBEAT_MESSAGE}" OR jsonPayload.message="{HEARTBEAT_MESSAGE}")'),
        "metricDescriptor": {"metricKind": "DELTA", "valueType": "INT64", "unit": "1"},
    }


def policy_specs() -> list[dict]:
    resource = (f'resource.type = "cloud_run_job" AND resource.labels.job_name = "{JOB.rsplit("/", 1)[-1]}" '
                f'AND resource.labels.location = "{REGION}"')
    common = {"combiner": "OR", "enabled": True, "notificationChannels": [CHANNEL], "userLabels": MONITORING_OWNER}
    return [
        {**common, "displayName": "EarningsNerd feedback media cleanup failed", "documentation": {
            "mimeType": "text/markdown",
            "content": "The private screenshot cleanup job failed. Inspect its counts-only ledger and execution; overdue objects also fail the job. Do not assume screenshots were erased.",
        }, "conditions": [{"displayName": "Feedback cleanup execution failed", "conditionThreshold": {
            "filter": resource + ' AND metric.type = "run.googleapis.com/job/completed_execution_count" AND metric.label.result = "failed"',
            "comparison": "COMPARISON_GT", "thresholdValue": 0, "duration": "0s", "trigger": {"count": 1},
            "aggregations": [{"alignmentPeriod": "60s", "perSeriesAligner": "ALIGN_SUM"}],
        }}]},
        {**common, "displayName": "EarningsNerd feedback media cleanup stale", "documentation": {
            "mimeType": "text/markdown",
            "content": "No successful normal private screenshot cleanup heartbeat has arrived for two hours. Check the hourly schedule, runtime and job ledger. Storage probes and dry runs do not refresh this heartbeat.",
        }, "conditions": [{"displayName": "Feedback cleanup success absent for two hours", "conditionAbsent": {
            "filter": resource + f' AND metric.type = "logging.googleapis.com/user/{HEARTBEAT_METRIC}"',
            "duration": "7200s", "trigger": {"count": 1},
            "aggregations": [{"alignmentPeriod": "60s", "perSeriesAligner": "ALIGN_SUM"}],
        }}]},
    ]


def check_channel(cloud: Cloud) -> None:
    channel = cloud.call("monitoring", "v3/" + CHANNEL)
    if (channel.get("name") != CHANNEL or channel.get("type") != "email" or channel.get("enabled") is not True
            or channel.get("verificationStatus") != "VERIFIED"):
        raise OperationError("Existing monitoring channel must be enabled, verified and of the expected email type")
    # Channel labels contain its recipient. Neither labels nor any provider payload is printed.


def check_heartbeat_metric(metric: dict | None) -> None:
    expected = heartbeat_spec()
    if (metric is None or metric.get("name") != HEARTBEAT_METRIC or metric.get("disabled", False)
            or metric.get("filter") != expected["filter"]
            or metric.get("description") != expected["description"]
            or any(metric.get("metricDescriptor", {}).get(key) != value
                   for key, value in expected["metricDescriptor"].items())):
        raise OperationError("Feedback cleanup heartbeat metric is missing, disabled or differs from the approved filter")


def policy_matches(policy: dict, expected: dict) -> bool:
    if any(policy.get(key) != expected[key] for key in ("displayName", "combiner", "enabled", "notificationChannels", "userLabels")):
        return False
    if policy.get("documentation", {}).get("content") != expected["documentation"]["content"]:
        return False
    conditions = policy.get("conditions", [])
    if len(conditions) != 1:
        return False
    condition = {key: value for key, value in conditions[0].items() if key != "name"}
    return condition == expected["conditions"][0]


def monitoring_policies(cloud: Cloud) -> list[dict]:
    policies, page_token = [], None
    for _ in range(10):
        query = urlencode({"pageSize": 100, **({"pageToken": page_token} if page_token else {})})
        page = cloud.call("monitoring", f"v3/projects/{PROJECT}/alertPolicies?{query}")
        policies.extend(page.get("alertPolicies", []))
        page_token = page.get("nextPageToken")
        if not page_token:
            return policies
    raise OperationError("Monitoring policy inventory exceeds the bounded inspection size")


def ensure_monitoring(cloud: Cloud) -> None:
    check_channel(cloud)
    metric_path = f"v2/projects/{PROJECT}/metrics/{HEARTBEAT_METRIC}"
    metric = cloud.call("logging", metric_path, missing_ok=True)
    if metric is None:
        metric = cloud.call("logging", f"v2/projects/{PROJECT}/metrics", method="POST", body=heartbeat_spec())
    check_heartbeat_metric(metric)
    policies = monitoring_policies(cloud)
    for expected in policy_specs():
        matching = [policy for policy in policies if policy.get("displayName") == expected["displayName"]]
        if not matching:
            created = cloud.call("monitoring", f"v3/projects/{PROJECT}/alertPolicies", method="POST", body=expected)
            matching = [created]
        if len(matching) != 1 or not policy_matches(matching[0], expected):
            raise OperationError("Existing feedback monitoring policy differs from the approved owned definition")
    print("Feedback cleanup failure and stale-heartbeat alert routing configured; delivery not exercised")


def inspect_monitoring(cloud: Cloud) -> bool:
    check_channel(cloud)
    check_heartbeat_metric(cloud.call("logging", f"v2/projects/{PROJECT}/metrics/{HEARTBEAT_METRIC}", missing_ok=True))
    policies = monitoring_policies(cloud)
    for expected in policy_specs():
        matching = [policy for policy in policies if policy.get("displayName") == expected["displayName"]]
        if len(matching) != 1 or not policy_matches(matching[0], expected):
            raise OperationError("Feedback cleanup alert policies must exactly match the enabled, owned definitions")
    now = datetime.now(timezone.utc)
    query = urlencode({
        "filter": policy_specs()[1]["conditions"][0]["conditionAbsent"]["filter"],
        "interval.startTime": (now - timedelta(hours=2)).isoformat(), "interval.endTime": now.isoformat(), "pageSize": 100,
    })
    series = cloud.call("monitoring", f"v3/projects/{PROJECT}/timeSeries?{query}").get("timeSeries", [])
    values = [point.get("value", {}).get("int64Value") for row in series for point in row.get("points", [])]
    heartbeat_seen = any(isinstance(value, str) and 1 <= len(value) <= 20 and value.isascii()
                         and value.isdecimal() and int(value) > 0 for value in values)
    print("Normal-cleanup monitoring heartbeat: " + ("observed" if heartbeat_seen else "not yet observed"))
    print("Feature alert channel: enabled and verified; end-to-end delivery unverified")
    return heartbeat_seen


def job_spec(service: dict) -> dict:
    template = service["template"]
    containers = template.get("containers", [])
    if len(containers) != 1 or not template.get("serviceAccount"):
        raise OperationError("API runtime identity or single-container configuration is unavailable")
    container = containers[0]
    env = [copy.deepcopy(item) for item in container.get("env", []) if item.get("name") in {"DATABASE_URL", "SECRET_KEY"}]
    if len(env) != 2 or {item["name"] for item in env} != {"DATABASE_URL", "SECRET_KEY"}:
        raise OperationError("API database and signing-key secret references are required for the cleanup job")
    if any("secretKeyRef" not in item.get("valueSource", {}) for item in env):
        raise OperationError("Cleanup job configuration requires secret references, not copied secret values")
    env += [{"name": name, "value": value} for name, value in {
        "ENVIRONMENT": "production", "SKIP_REDIS_INIT": "true", "DB_POOL_SIZE": "1", "DB_MAX_OVERFLOW": "0",
        "SEC_RATE_LIMIT_PER_SECOND": "1", "EDGAR_RATE_LIMIT_PER_SEC": "1",
        "FEEDBACK_MEDIA_BUCKET": BUCKETS["production"], "FEEDBACK_MEDIA_ENABLED": "false",
    }.items()]
    volumes = [v for v in template.get("volumes", []) if "cloudSqlInstance" in v]
    mounts = [m for m in container.get("volumeMounts", []) if m.get("name") in {v["name"] for v in volumes}]
    task = {"serviceAccount": template["serviceAccount"], "timeout": "600s", "maxRetries": 1, "volumes": volumes,
            "containers": [{"name": "cleanup", "image": container["image"], "command": ["python"],
                            "args": CLEANUP_ARGS, "env": env, "volumeMounts": mounts,
                            "resources": {"limits": {"cpu": "1", "memory": "512Mi"}}}]}
    if template.get("vpcAccess"):
        task["vpcAccess"] = template["vpcAccess"]
    return {"name": JOB, "labels": {"purpose": "feedback-media"},
            "template": {"taskCount": 1, "parallelism": 1, "template": task}}


def provision(cloud: Cloud, service: dict) -> None:
    spec = job_spec(service)  # validate required identity/secret references before any mutation
    runtime = spec["template"]["template"]["serviceAccount"]
    ensure_monitoring(cloud)  # create the success metric before the first genuine cleanup heartbeat
    ensure_buckets(cloud, runtime)
    current = cloud.call("run", "v2/" + JOB, missing_ok=True)
    if current is not None and current.get("labels", {}).get("purpose") != "feedback-media":
        raise OperationError("Existing cleanup job is not owned by this feature")
    if current is None:
        cloud.wait(cloud.call("run", f"v2/{PARENT}/jobs?jobId=earningsnerd-feedback-media-cleanup", method="POST", body=spec))
    else:
        spec["etag"] = current["etag"]
        # Cloud Run v2 Job.patch replaces its editable specification; it has no updateMask.
        cloud.wait(cloud.call("run", f"v2/{JOB}", method="PATCH", body=spec))
    bind(cloud, "run", "v2/" + JOB, "roles/run.invoker", "serviceAccount:" + runtime)
    schedule = {"name": SCHEDULE, "description": "EarningsNerd private feedback media cleanup",
                "schedule": "17 * * * *", "timeZone": "Etc/UTC", "attemptDeadline": "60s",
                "retryConfig": {"retryCount": 0}, "httpTarget": {
                    "uri": f"https://run.googleapis.com/v2/{JOB}:run", "httpMethod": "POST",
                    "headers": {"Content-Type": "application/json"}, "body": "e30=",
                    "oauthToken": {"serviceAccountEmail": runtime, "scope": "https://www.googleapis.com/auth/cloud-platform"}}}
    current_schedule = cloud.call("cloudscheduler", "v1/" + SCHEDULE, missing_ok=True)
    if current_schedule is None:
        cloud.call("cloudscheduler", f"v1/{PARENT}/jobs", method="POST", body=schedule)
    elif current_schedule.get("description") == schedule["description"]:
        cloud.call("cloudscheduler", f"v1/{SCHEDULE}?updateMask=schedule,timeZone,attemptDeadline,retryConfig,httpTarget",
                   method="PATCH", body=schedule)
    else:
        raise OperationError("Existing cleanup schedule is not owned by this feature")
    # Cleanup can succeed with no rows without contacting GCS. A separate manifest-backed probe
    # proves object create/read/conditional-delete using the runtime identity, without user data.
    cloud.wait(cloud.call("run", "v2/" + JOB + ":run", method="POST", body={}))
    cloud.wait(cloud.call("run", "v2/" + JOB + ":run", method="POST", body={
        "overrides": {"containerOverrides": [{"name": "cleanup", "args": PROBE_ARGS}]},
    }))
    # A new log metric may take several minutes to publish its first time series. No new writes
    # occur while waiting, and a timeout leaves the rollout disabled rather than claiming monitoring.
    deadline = time.monotonic() + 300
    while not inspect(cloud):
        if time.monotonic() >= deadline:
            raise OperationError("Resources provisioned; monitoring heartbeat is not yet observable")
        time.sleep(10)
    print("Private storage probe and cleanup succeeded; uploads remain unchanged")


def matches_task(task: dict, expected: dict, args: list[str]) -> bool:
    containers = task.get("containers", [])
    if len(containers) != 1:
        return False
    container = containers[0]
    wanted = expected["containers"][0]
    env = container.get("env", [])
    wanted_env = {item["name"]: item for item in wanted["env"]}
    return (task.get("serviceAccount") == expected["serviceAccount"]
            and task.get("timeout") == expected["timeout"] and task.get("maxRetries") == expected["maxRetries"]
            and task.get("volumes", []) == expected.get("volumes", [])
            and task.get("vpcAccess") == expected.get("vpcAccess")
            and container.get("name") == "cleanup" and container.get("image") == wanted["image"]
            and container.get("command") == ["python"] and container.get("args") == args
            and container.get("volumeMounts", []) == wanted.get("volumeMounts", [])
            and container.get("resources", {}).get("limits") == wanted["resources"]["limits"]
            and len(env) == len(wanted_env) and {item.get("name"): item for item in env} == wanted_env)


def recent_success(execution: dict | None, expected: dict, args: list[str]) -> bool:
    if (not execution or execution.get("succeededCount") != 1 or execution.get("failedCount", 0)
            or execution.get("cancelledCount", 0) or execution.get("taskCount") != 1
            or not matches_task(execution.get("template", {}), expected, args)):
        return False
    try:
        completed = datetime.fromisoformat(execution["completionTime"].replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - completed
        return timedelta(0) <= age <= timedelta(hours=2)
    except (KeyError, ValueError, TypeError):
        return False


def inspect(cloud: Cloud) -> bool:
    ready = True
    service = cloud.call("run", "v2/" + SERVICE)
    runtime = service.get("template", {}).get("serviceAccount")
    if not runtime:
        raise OperationError("API runtime identity unavailable")
    check_role(cloud.call("iam", "v1/" + ROLE, missing_ok=True))
    for environment, name in BUCKETS.items():
        bucket = cloud.call("storage", "storage/v1/b/" + name, missing_ok=True)
        if bucket is None:
            print(f"{environment} bucket: absent")
            ready = False
            continue
        check_bucket(bucket, environment)
        policy = cloud.call("storage", policy_path("storage/v1/b/" + name, storage=True))
        check_runtime_bucket_policy(policy, runtime)
        print(f"{environment} bucket: private retention settings verified")
    job = cloud.call("run", "v2/" + JOB, missing_ok=True)
    schedule = cloud.call("cloudscheduler", "v1/" + SCHEDULE, missing_ok=True)
    if job is None or schedule is None:
        print("Cleanup job/schedule: incomplete")
        return False
    expected = job_spec(service)["template"]["template"]
    task = job.get("template", {}).get("template", {})
    if (job.get("labels", {}).get("purpose") != "feedback-media"
            or job.get("template", {}).get("taskCount") != 1
            or job.get("template", {}).get("parallelism") != 1
            or not matches_task(task, expected, CLEANUP_ARGS)):
        raise OperationError("Cleanup job differs from the approved runtime, image or bounded configuration")
    job_policy = cloud.call("run", policy_path("v2/" + JOB))
    check_private_policy(job_policy)
    if not any(b.get("role") == "roles/run.invoker" and not b.get("condition")
               and "serviceAccount:" + runtime in b.get("members", []) for b in job_policy.get("bindings", [])):
        raise OperationError("Cleanup scheduler's job invocation grant is missing")
    # API sorts creation time descending. Keep the latest attempt for each mode, including failures;
    # an older success must not hide a failed current attempt. Fifty bounds a noisy retry history.
    executions = cloud.call("run", f"v2/{JOB}/executions?pageSize=50").get("executions", [])
    latest = {}
    for execution in executions:
        containers = execution.get("template", {}).get("containers", [])
        if len(containers) == 1:
            args = containers[0].get("args")
            mode = "cleanup" if args == CLEANUP_ARGS else "probe" if args == PROBE_ARGS else None
            if mode is not None:
                latest.setdefault(mode, execution)
    succeeded = recent_success(latest.get("cleanup"), expected, CLEANUP_ARGS)
    probe_succeeded = recent_success(latest.get("probe"), expected, PROBE_ARGS)
    schedule_ready = (schedule.get("state") == "ENABLED" and schedule.get("schedule") == "17 * * * *"
                      and schedule.get("timeZone") == "Etc/UTC"
                      and schedule.get("httpTarget", {}).get("uri") == f"https://run.googleapis.com/v2/{JOB}:run"
                      and schedule.get("httpTarget", {}).get("httpMethod") == "POST"
                      and schedule.get("httpTarget", {}).get("body") == "e30="
                      and schedule.get("httpTarget", {}).get("oauthToken", {}).get("serviceAccountEmail") == runtime)
    print("Cleanup last execution: " + ("succeeded" if succeeded else "unverified"))
    print("Private storage probe: " + ("succeeded" if probe_succeeded else "unverified"))
    print("Runtime enumerated storage permission audit: " + ("verified by the successful probe" if probe_succeeded else "unverified"))
    print("Cleanup hourly schedule: " + ("verified" if schedule_ready else "unverified"))
    monitoring_ready = inspect_monitoring(cloud)
    return ready and succeeded and probe_succeeded and schedule_ready and monitoring_ready


def require_live_verification(cloud: Cloud, service: dict) -> None:
    # The optional verifier is an Ops dependency only; production request handlers never import
    # it or connect to its isolated database. Resolve the reviewed checkout for direct CLI use.
    root = str(Path(__file__).resolve().parents[2])
    if root not in sys.path:
        sys.path.insert(0, root)
    from ops.feedback_media.verify_manage import require_receipt
    require_receipt(cloud, service)


def set_enabled(cloud: Cloud, service: dict, enabled: bool) -> None:
    if enabled and not inspect(cloud):
        raise OperationError("Private storage and successful scheduled cleanup are required before enabling")
    if enabled:
        require_live_verification(cloud, service)
    containers = copy.deepcopy(service["template"]["containers"])
    if len(containers) != 1:
        raise OperationError("Expected one API container")
    env = containers[0].setdefault("env", [])
    env[:] = [item for item in env if item.get("name") not in {"FEEDBACK_MEDIA_BUCKET", "FEEDBACK_MEDIA_ENABLED"}]
    env += [{"name": "FEEDBACK_MEDIA_BUCKET", "value": BUCKETS["production"]},
            {"name": "FEEDBACK_MEDIA_ENABLED", "value": str(enabled).lower()}]
    cloud.wait(cloud.call("run", f"v2/{SERVICE}?updateMask=template.containers", method="PATCH",
                          body={"name": SERVICE, "etag": service["etag"], "template": {"containers": containers}}))
    current = cloud.call("run", "v2/" + SERVICE)
    traffic = [entry for entry in current.get("trafficStatuses", []) if entry.get("percent", 0) > 0]
    latest = current.get("latestReadyRevision", "").rsplit("/", 1)[-1]
    if (len(traffic) != 1 or traffic[0].get("percent") != 100
            or not latest or traffic[0].get("revision", "").rsplit("/", 1)[-1] != latest
            or current.get("reconciling") or any(entry.get("tag") for entry in current.get("trafficStatuses", []))):
        raise OperationError("API configuration changed but latest revision is not serving all traffic; inspect deployment")
    print("Feedback image uploads: " + ("enabled" if enabled else "disabled; existing media reads and cleanup retained"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=OPERATIONS)
    operation = parser.parse_args().operation
    cloud = Cloud()
    if operation == "feedback-media-inspect":
        if not inspect(cloud):
            raise OperationError("Feedback media prerequisites are incomplete")
        return
    service = cloud.call("run", "v2/" + SERVICE)
    if operation == "feedback-media-provision-apply":
        provision(cloud, service)
    else:
        set_enabled(cloud, service, operation == "feedback-media-enable-apply")


if __name__ == "__main__":
    try:
        main()
    except OperationError as exc:
        raise SystemExit(str(exc)) from None
