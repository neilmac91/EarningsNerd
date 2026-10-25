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
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
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
        print(f"{environment} bucket: private, uniform access, no versioning or soft delete")


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
    if not inspect(cloud):
        raise OperationError("Resources provisioned; cleanup or storage verification is incomplete")
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
        check_private_policy(policy)
        if not any(b.get("role") == ROLE and not b.get("condition")
                   and "serviceAccount:" + runtime in b.get("members", []) for b in policy.get("bindings", [])):
            raise OperationError(f"{environment} bucket runtime object grant is missing")
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
    print("Cleanup hourly schedule: " + ("verified" if schedule_ready else "unverified"))
    return ready and succeeded and probe_succeeded and schedule_ready


def set_enabled(cloud: Cloud, service: dict, enabled: bool) -> None:
    if enabled and not inspect(cloud):
        raise OperationError("Private storage and successful scheduled cleanup are required before enabling")
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
