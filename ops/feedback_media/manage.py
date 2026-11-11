"""Provision and inspect dedicated feedback media resources through the protected Ops workflow.

Only fixed resources in earnings-nerd/us-west1 are addressable. API errors print a closed
status, never response bodies, access tokens, service configuration or user data. Every mutation
is an explicit -apply operation, protected by ops.yml's owner approval and first-attempt gate.
Each provider call names its step and the IAM permission it needs. Before its first write, provisioning
tests its reads, reads every existing resource, refuses one it would not repair, and then tests only the
writes that state needs, so a run that cannot finish changes nothing and a founder-made resource or grant in
the approved shape needs no create or set-policy permission.
"""
from __future__ import annotations

import argparse
import copy
import functools
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError
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
METRIC_PATH = f"v2/projects/{PROJECT}/metrics/{HEARTBEAT_METRIC}"
SCHEDULE_DESCRIPTION = "EarningsNerd private feedback media cleanup"
# Cloud Scheduler's job states; a refusal names only these.
SCHEDULE_STATES = ("ENABLED", "PAUSED", "DISABLED", "UPDATE_FAILED", "STATE_UNSPECIFIED")
MONITORING_OWNER = {"component": "feedback-media"}
POLICY_DRIFT = "Existing feedback monitoring policy differs from the approved owned definition"
OPERATIONS = (
    "feedback-media-inspect", "feedback-media-provision-apply",
    "feedback-media-enable-apply", "feedback-media-disable-apply",
)
ACT_AS = "iam.serviceAccounts.actAs"
# The deploying caller, not only the Cloud Run service agent, needs image read on the repository of every image it
# deploys to a job or service (Artifact Registry Reader on the repository). The API image must come from the one
# repository ci.yml's deploy pushes to; a repository grant is invisible to project testIamPermissions, so it is
# tested on the repository itself.
IMAGE_READ = "artifactregistry.repositories.downloadArtifacts"
IMAGE_REPOSITORY = f"projects/{PROJECT}/locations/{REGION}/repositories/earningsnerd"
API_IMAGE = re.compile(rf"{REGION}-docker\.pkg\.dev/{PROJECT}/earningsnerd/backend"
                       r"(?::[A-Za-z0-9_][A-Za-z0-9_.-]{0,127})?(?:@sha256:[0-9a-f]{64})?")
# The same shape with its parts named: a job execution records its image by digest (live read-back, 11 November).
IMAGE_PARTS = re.compile(rf"{REGION}-docker\.pkg\.dev/{PROJECT}/earningsnerd/backend"
                         r"(?::(?P<tag>[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}))?(?:@(?P<digest>sha256:[0-9a-f]{64}))?")


def step(name: str, *permissions: str) -> str:
    """A provider call's label: its step and the IAM permissions it needs, as fixed code literals."""
    return f"{name} [{', '.join(permissions)}]"


SERVICE_READ = step("API service read", "run.services.get")
SERVICE_UPDATE = step("API service update", "run.services.update", ACT_AS, IMAGE_READ)
REVISION_READ = step("Serving revision read", "run.revisions.get")
ROLE_READ = step("Object role read", "iam.roles.get")
ROLE_CREATE = step("Object role create", "iam.roles.create")
BUCKET_READ = step("Bucket read", "storage.buckets.get")
BUCKET_CREATE = step("Bucket create", "storage.buckets.create")
BUCKET_POLICY_READ = step("Bucket policy read", "storage.buckets.getIamPolicy")
BUCKET_POLICY_WRITE = step("Bucket policy write", "storage.buckets.setIamPolicy")
CHANNEL_READ = step("Alert channel read", "monitoring.notificationChannels.get")
METRIC_READ = step("Heartbeat metric read", "logging.logMetrics.get")
METRIC_CREATE = step("Heartbeat metric create", "logging.logMetrics.create")
POLICY_LIST = step("Alert policy list", "monitoring.alertPolicies.list")
POLICY_CREATE = step("Alert policy create", "monitoring.alertPolicies.create")
SERIES_READ = step("Heartbeat series read", "monitoring.timeSeries.list")
JOB_READ = step("Cleanup job read", "run.jobs.get")
JOB_CREATE = step("Cleanup job create", "run.jobs.create", ACT_AS, IMAGE_READ)
JOB_UPDATE = step("Cleanup job update", "run.jobs.update", ACT_AS, IMAGE_READ)
JOB_POLICY_READ = step("Cleanup job policy read", "run.jobs.getIamPolicy")
JOB_POLICY_WRITE = step("Cleanup job policy write", "run.jobs.setIamPolicy")
EXECUTIONS_READ = step("Cleanup execution list", "run.executions.list")
CLEANUP_RUN = step("Cleanup execution", "run.jobs.run")
PROBE_RUN = step("Storage probe execution", "run.jobs.run", "run.jobs.runWithOverrides")
OPERATION_READ = step("Cloud Run operation poll", "run.operations.get")
SCHEDULE_READ = step("Cleanup schedule read", "cloudscheduler.jobs.get")
SCHEDULE_CREATE = step("Cleanup schedule create", "cloudscheduler.jobs.create", ACT_AS)
SCHEDULE_UPDATE = step("Cleanup schedule update", "cloudscheduler.jobs.update", ACT_AS)
CAPABILITY_READ = "Capability preflight (needs no permission)"
# The reads every provisioning run makes before or between its writes, and the writes every run makes. The other
# writes create what is absent, add a missing grant, or update what exists, so a run tests each only when the state
# it read needs it (provision_writes): a founder-made role, bucket or grant in the approved shape needs no create or
# setIamPolicy permission.
PROVISION_READS = frozenset({
    "run.services.get", "monitoring.notificationChannels.get", "logging.logMetrics.get", "monitoring.alertPolicies.list",
    "monitoring.timeSeries.list", "iam.roles.get", "storage.buckets.get", "storage.buckets.getIamPolicy", "run.jobs.get",
    "run.jobs.getIamPolicy", "run.executions.list", "run.operations.get", "cloudscheduler.jobs.get", "run.revisions.get",
})
EVERY_RUN_WRITES = frozenset({"run.jobs.run", "run.jobs.runWithOverrides"})
CONDITIONAL_WRITES = frozenset({
    "logging.logMetrics.create", "monitoring.alertPolicies.create", "iam.roles.create", "storage.buckets.create",
    "storage.buckets.setIamPolicy", "run.jobs.create", "run.jobs.update", "run.jobs.setIamPolicy",
    "cloudscheduler.jobs.create", "cloudscheduler.jobs.update",
})
# Every project permission a provisioning step names. actAs and image read are tested on their own resources (the
# runtime identity, the image repository), where those grants are visible. A test holds this set equal to the
# steps provisioning performs.
PROVISION_PERMISSIONS = PROVISION_READS | EVERY_RUN_WRITES | CONDITIONAL_WRITES
# Google's error envelope: only these closed values are ever printed, with a denied permission in the shape below.
# Messages, resources and principals in the body are withheld.
GRPC_STATUSES = ("OK", "CANCELLED", "UNKNOWN", "INVALID_ARGUMENT", "DEADLINE_EXCEEDED", "NOT_FOUND", "ALREADY_EXISTS",
                 "PERMISSION_DENIED", "RESOURCE_EXHAUSTED", "FAILED_PRECONDITION", "ABORTED", "OUT_OF_RANGE",
                 "UNIMPLEMENTED", "INTERNAL", "UNAVAILABLE", "DATA_LOSS", "UNAUTHENTICATED")
ERROR_REASONS = frozenset({
    "IAM_PERMISSION_DENIED", "SERVICE_DISABLED", "BILLING_DISABLED", "ACCESS_TOKEN_SCOPE_INSUFFICIENT",
    "ACCESS_TOKEN_EXPIRED", "CREDENTIALS_MISSING", "RATE_LIMIT_EXCEEDED", "RESOURCE_QUOTA_EXCEEDED",
    "SECURITY_POLICY_VIOLATED", "ORG_RESTRICTION_VIOLATION", "LOCATION_POLICY_VIOLATED", "USER_PROJECT_DENIED",
    "CONSUMER_INVALID", "SERVICE_NOT_VISIBLE", "RESOURCE_PROJECT_INVALID",
})
# A denied permission is named only when it is one these operations' steps name; any other reads as unlisted.
KNOWN_PERMISSIONS = PROVISION_PERMISSIONS | {ACT_AS, IMAGE_READ, "run.services.update"}
# A BadRequest names the request fields it refuses. A field path is schema, not data, so it is named only in a closed
# shape: dotted lowercase words in snake or camel case, each with at most a three-digit index. That shape cannot carry
# an address, a URL, a number beyond an index, a separator, or a hyphenated or uppercase-led name; FIELD_NAMES below
# masks any word that is not a Cloud Run field name. At most three are named.
BAD_REQUEST = "type.googleapis.com/google.rpc.BadRequest"
FIELD_SEGMENT = r"[a-z]{1,24}(?:_[a-z]{1,24}|[A-Z][a-z]{1,24}){0,6}(?:\[[0-9]{1,3}\])?"
FIELD_PATH = re.compile(rf"{FIELD_SEGMENT}(?:\.{FIELD_SEGMENT}){{0,11}}")
# Cloud Run v2 writes the field as "Violation in <request type>.<path>", for example "Violation in
# CreateJobRequest.job.template.template.volumes[0].name"; the path after a request type of this shape is named.
REQUEST_FIELD = re.compile(r"Violation in (?:[A-Z][a-z]{1,24}){2,4}Request\.(.+)")
NAMED_FIELDS = 3
# The words a named path may hold: the Cloud Run v2 request fields and the field names of its job and service
# resources, from its API discovery document, in snake case (camel case is matched as snake). The shape alone admits
# a value shaped like a field name ("invite_only"), so any other word is printed as "?", and a path with no word from
# this list is not named at all.
FIELD_NAMES = frozenset("""
    job service execution worker_pool job_id service_id parent update_mask allow_missing validate_only
    accelerator annotations args base_image_uri binary_authorization breakglass_justification bucket build_config
    build_id build_info clear_args client client_version cloud_sql_instance cloud_storage_source command
    concurrency_utilization conditions connector container_overrides container_port containers cpu_idle
    cpu_utilization create_time creator custom_audiences default_mode default_uri_disabled delay_execution delete_time
    depends_on description egress empty_dir encryption_key encryption_key_revocation_action
    encryption_key_shutdown_duration env etag execution_count execution_environment expire_time failure_threshold
    function_target gcs generation gpu_zonal_redundancy_disabled grpc health_check_disabled http_get http_headers
    iap_enabled image ingress initial_delay_seconds inlined_source instances invoker_iam_disabled items labels
    last_modifier latest_created_execution latest_created_revision latest_ready_revision launch_stage limits
    liveness_probe manual_instance_count max_instance_count max_instance_request_concurrency max_retries medium mesh
    min_instance_count mode mount_options mount_path multi_region_settings name network network_interfaces nfs
    node_selector observed_generation overrides parallelism path percent period_seconds policy port ports
    priority_tier read_only readiness_probe reconciling resources revision run_execution_token satisfies_pzs scaling
    scaling_mode secret secret_key_ref server service_account service_mesh session_affinity size_limit source_code
    source_location start_execution_token startup_cpu_boost startup_probe sub_path subnetwork tag tags task_count
    tcp_socket template terminal_condition threat_detection_enabled timeout timeout_seconds traffic traffic_statuses
    type uid update_time uri urls use_default value value_source version volume_mounts volumes vpc_access working_dir
""".split())


def field_path(field: str) -> str | None:
    """A refused field's path in its closed shape with each word from FIELD_NAMES (any other as "?"), or None: never
    any other text the provider wrote."""
    if len(field) > 256:
        return None
    request = REQUEST_FIELD.fullmatch(field)
    path = request[1] if request else field
    if not FIELD_PATH.fullmatch(path):
        return None
    segments = [re.fullmatch(r"([A-Za-z_]+)(\[[0-9]{1,3}\])?", segment).groups("") for segment in path.split(".")]
    known = [re.sub(r"(?<!^)(?=[A-Z])", "_", word).lower() in FIELD_NAMES for word, _ in segments]
    if not any(known):
        return None
    return ".".join((word if named else "?") + index for (word, index), named in zip(segments, known))


class OperationError(RuntimeError):
    """An operational failure safe to display without provider payloads."""


class ProviderError(OperationError):
    """A provider call that failed or could not be read: its closed label and class, never its payload.

    Inspection reports such a component UNVERIFIED rather than refused (lessons/ops-denied-reads-report-unverified.md).
    """


def error_class(raw: bytes) -> str:
    """Reduce a provider error body to closed values: its status, ErrorInfo reasons, a known denied permission and
    the closed-shape paths of the request fields a BadRequest refuses."""
    try:
        error = json.loads(raw)["error"]
        details = [item for item in error.get("details", []) if isinstance(item, dict)]
        status = error.get("status")
        values = [status] if isinstance(status, str) and status in GRPC_STATUSES else []
        values += sorted({item["reason"] for item in details
                          if isinstance(item.get("reason"), str) and item["reason"] in ERROR_REASONS})
        named = {item["metadata"]["permission"] for item in details
                 if isinstance(item.get("metadata"), dict) and isinstance(item["metadata"].get("permission"), str)}
        values += sorted({f"denied {name}" if name in KNOWN_PERMISSIONS else "denied an unlisted permission"
                          for name in named})
        refused = {field_path(row["field"]) for item in details
                   if item.get("@type") == BAD_REQUEST and isinstance(item.get("fieldViolations"), list)
                   for row in item["fieldViolations"] if isinstance(row, dict) and isinstance(row.get("field"), str)}
        values += [f"field {path}" for path in sorted(refused - {None})[:NAMED_FIELDS]]
    except Exception:  # a malformed body yields no class; the labelled refusal itself stands
        return ""
    return "".join(f"; {value}" for value in values)


READ_ATTEMPTS = 3


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
             missing_ok: bool = False, step: str | None = None) -> dict | None:
        payload = None if body is None else json.dumps(body).encode()
        request = Request(f"https://{api}.googleapis.com/{path}", data=payload, method=method,
                          headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
        label = step or f"{api} operation"
        # A read retries a 503, which Google calls transient (AIP-194) and which once stopped a live read here; a
        # write is never retried, so it is sent at most once.
        attempts = READ_ATTEMPTS if method == "GET" else 1
        for attempt in range(1, attempts + 1):
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
                if exc.code == 503 and attempt < attempts:
                    time.sleep(2 ** attempt)
                    continue
                try:
                    detail = error_class(exc.read(64 * 1024))
                except Exception:  # an unreadable error body yields no class; the labelled refusal itself stands
                    detail = ""
                raise ProviderError(f"{label} failed (HTTP {exc.code}{detail})") from None
            # URLError and timeouts are OSErrors; so is a connection dropped before a response, which urllib raises
            # outside its URLError wrapper. HTTPException covers a response cut short.
            except (OSError, ValueError, HTTPException):
                raise ProviderError(f"{label} unavailable or unreadable") from None
        raise AssertionError("unreachable: the last attempt returns or raises")

    def wait(self, operation: dict, step: str | None = None) -> dict:
        """Poll a long-running operation; a failure names the step that started it (unlabelled callers keep the old wording)."""
        prefix = f"{step}: " if step else ""
        deadline = time.monotonic() + 180
        while not operation.get("done"):
            if time.monotonic() >= deadline:
                raise OperationError(f"{prefix}Cloud Run operation still pending; inspect before retrying")
            time.sleep(2)
            operation = self.call("run", "v2/" + operation["name"], step=OPERATION_READ)
        if operation.get("error"):
            code = operation["error"].get("code") if isinstance(operation["error"], dict) else None
            status = GRPC_STATUSES[code] if type(code) is int and 0 < code < len(GRPC_STATUSES) else "unclassified"
            raise ProviderError(f"{prefix}Cloud Run operation failed ({status}); provider payload withheld")
        return operation.get("response", {})


# What reading a provider answer of another shape raises: no answer of the documented shape raises these.
SHAPE_ERRORS = (AttributeError, TypeError, KeyError, IndexError)


def closed_shape(resource: str):
    """A check reads a provider answer by its documented shape; an answer of another shape is refused, closed.

    The check's own comparisons refuse drift; this refuses what they cannot compare (an object where a list
    belongs, a list where an object belongs, a missing index), so a malformed answer is never read as approved or
    absent, nor ends in a traceback.
    """
    def wrap(check):
        @functools.wraps(check)
        def checked(*args, **kwargs):
            try:
                return check(*args, **kwargs)
            except SHAPE_ERRORS:
                raise OperationError(f"{resource} answer is malformed") from None
        return checked
    return wrap


@closed_shape("Bucket")
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


def policy_bindings(policy: dict) -> list[dict]:
    """An IAM policy's bindings, refused unless each is a role, a list of member strings and an optional condition.

    A member list read as a string would match by substring, so a malformed policy could read as granted or private.
    """
    bindings = policy.get("bindings", []) if isinstance(policy, dict) else None
    if not isinstance(bindings, list) or not all(
            isinstance(binding, dict) and isinstance(binding.get("role"), str)
            and isinstance(binding.get("members", []), list)
            and all(isinstance(member, str) for member in binding.get("members", []))
            and isinstance(binding.get("condition", {}), dict) for binding in bindings):
        raise OperationError("Resource policy is malformed")
    return bindings


def check_private_policy(policy: dict) -> None:
    if any(member in ("allUsers", "allAuthenticatedUsers")
           for binding in policy_bindings(policy) for member in binding.get("members", [])):
        raise OperationError("Resource policy includes a public principal")


def check_runtime_bucket_policy(policy: dict, runtime: str, *, granted: bool = True) -> None:
    """Refuse a public principal, and any runtime grant but the unconditional object role (required unless not `granted` yet)."""
    check_private_policy(policy)
    member = "serviceAccount:" + runtime
    grants = [binding for binding in policy_bindings(policy) if member in binding.get("members", [])]
    if (granted and not grants) or any(binding.get("role") != ROLE or binding.get("condition") for binding in grants):
        raise OperationError("Runtime bucket grants differ from the approved unconditional object role")


def bound(policy: dict, role: str, member: str) -> bool:
    """Whether the policy already holds this member in an unconditional binding of the role.

    bind() writes exactly when this is false, so a planner that reads it as true never meets an untested write.
    """
    return any(binding.get("role") == role and not binding.get("condition") and member in binding.get("members", [])
               for binding in policy_bindings(policy))


def policy_etag(policy: dict) -> str:
    """A read policy's etag. Its write-back is conditional on it, so a policy without one is refused, never written."""
    etag = policy.get("etag") if isinstance(policy, dict) else None
    if not isinstance(etag, str) or not etag:
        raise OperationError("Resource policy has no etag")
    return etag


@closed_shape("Cleanup job")
def check_owned_job(job: dict) -> None:
    if job.get("labels", {}).get("purpose") != "feedback-media":
        raise OperationError("Existing cleanup job is not owned by this feature")


@closed_shape("Cleanup schedule")
def check_owned_schedule(schedule: dict) -> None:
    """Refuse a schedule this feature does not own, or an owned one in a state provisioning's update cannot leave.

    An update cannot resume a schedule (only :resume leaves PAUSED, and the system sets DISABLED), so a paused,
    disabled or unknown one would be written and then never read as ready. Retrying an update is Google's documented
    recovery from UPDATE_FAILED, so that state converges. Only a state from the fixed list is named.
    """
    if schedule.get("description") != SCHEDULE_DESCRIPTION:
        raise OperationError("Existing cleanup schedule is not owned by this feature")
    state = schedule.get("state")
    if state not in ("ENABLED", "UPDATE_FAILED"):
        shown = state if isinstance(state, str) and state in SCHEDULE_STATES else "in an unrecognized state"
        raise OperationError(f"Existing cleanup schedule is {shown}; provisioning does not resume it")


def policy_path(path: str, *, storage: bool = False) -> str:
    # Request policy v3 so read/modify/write preserves conditional grants and their etag.
    return path + ("/iam?optionsRequestedPolicyVersion=3" if storage
                   else ":getIamPolicy?options.requestedPolicyVersion=3")


STORAGE_PERMISSION = re.compile(r"storage\.(?:buckets|objects|managedFolders|multipartUploads)\.[A-Za-z]{1,40}")


@closed_shape("Object role")
def check_role(role: dict | None) -> None:
    """Refuse anything but the active create/get/delete role, naming which state it is in.

    Only closed values reach the message: the approved permission names it lacks and extra storage
    permission names (any other extra permission is counted, never named).
    """
    if role is None:
        raise OperationError("Feedback object role is absent")
    if role.get("deleted"):
        raise OperationError("Feedback object role is deleted; undeleting it or a new role ID is a separate approved change")
    if role.get("stage") == "DISABLED":
        raise OperationError("Feedback object role stage is DISABLED")
    granted = role.get("includedPermissions", [])
    if not isinstance(granted, list) or not all(isinstance(name, str) for name in granted):
        raise OperationError("Feedback object role permissions are unreadable")
    if set(granted) != set(PERMISSIONS):
        missing = sorted(set(PERMISSIONS) - set(granted))
        extra = set(granted) - set(PERMISSIONS)
        named = sorted(name for name in extra if STORAGE_PERMISSION.fullmatch(name))
        parts = ([f"lacks {', '.join(missing)}"] if missing else []) + ([f"adds {', '.join(named)}"] if named else []) + (
            [f"adds {len(extra) - len(named)} other permission(s)"] if len(extra) > len(named) else [])
        raise OperationError("Feedback object role differs from object create/get/delete: " + "; ".join(parts))


def bind(cloud: Cloud, api: str, path: str, role: str, member: str, *, storage: bool = False,
         read_step: str | None = None, write_step: str | None = None) -> None:
    policy = cloud.call(api, policy_path(path, storage=storage), step=read_step)
    check_private_policy(policy)
    policy_etag(policy)  # the write-back carries it, so a concurrent change fails the write rather than being lost
    if bound(policy, role, member):
        return
    bindings = policy.setdefault("bindings", [])
    binding = next((b for b in bindings if b.get("role") == role and not b.get("condition")), None)
    if binding is None:
        binding = {"role": role, "members": []}
        bindings.append(binding)
    binding.setdefault("members", []).append(member)
    cloud.call(api, path + ("/iam" if storage else ":setIamPolicy"),
               method="PUT" if storage else "POST", body=policy if storage else {"policy": policy}, step=write_step)


def ensure_buckets(cloud: Cloud, runtime: str) -> None:
    role = cloud.call("iam", "v1/" + ROLE, missing_ok=True, step=ROLE_READ)
    if role is None:
        role = cloud.call("iam", f"v1/projects/{PROJECT}/roles", method="POST", step=ROLE_CREATE, body={
            "roleId": "earningsnerdFeedbackObjects", "role": {
                "title": "EarningsNerd feedback objects", "description": "Known-key private feedback images",
                "includedPermissions": PERMISSIONS, "stage": "GA",
            },
        })
    check_role(role)
    for environment, name in BUCKETS.items():
        bucket = cloud.call("storage", "storage/v1/b/" + name, missing_ok=True, step=BUCKET_READ)
        if bucket is None:
            bucket = cloud.call("storage", f"storage/v1/b?project={PROJECT}", method="POST", step=BUCKET_CREATE, body={
                "name": name, "location": REGION, "storageClass": "STANDARD",
                "labels": {"purpose": "feedback-media", "environment": environment},
                "iamConfiguration": {"uniformBucketLevelAccess": {"enabled": True}, "publicAccessPrevention": "enforced"},
                "versioning": {"enabled": False}, "softDeletePolicy": {"retentionDurationSeconds": "0"},
            })
        # Never weaken or adopt an unrelated pre-existing bucket with this name.
        check_bucket(bucket, environment)
        bind(cloud, "storage", "storage/v1/b/" + name, ROLE, "serviceAccount:" + runtime, storage=True,
             read_step=BUCKET_POLICY_READ, write_step=BUCKET_POLICY_WRITE)
        check_runtime_bucket_policy(cloud.call("storage", policy_path("storage/v1/b/" + name, storage=True),
                                               step=BUCKET_POLICY_READ), runtime)
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


@closed_shape("Alert channel")
def check_channel(cloud: Cloud) -> None:
    channel = cloud.call("monitoring", "v3/" + CHANNEL, step=CHANNEL_READ)
    # Monitoring omits the protobuf default for channels that need no verification or
    # have a legacy exemption. That is distinct from an explicit UNVERIFIED status.
    # https://docs.cloud.google.com/monitoring/api/ref_v3/rest/v3/projects.notificationChannels
    verification = channel.get("verificationStatus", "VERIFICATION_STATUS_UNSPECIFIED")
    if (channel.get("name") != CHANNEL or channel.get("type") != "email" or channel.get("enabled") is not True
            or verification not in ("VERIFIED", "VERIFICATION_STATUS_UNSPECIFIED")):
        raise OperationError("Existing monitoring channel must be the enabled email channel with no verification pending")
    # Channel labels contain its recipient. Neither labels nor any provider payload is printed.


@closed_shape("Heartbeat metric")
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
    expected_condition = expected["conditions"][0]
    if expected_condition.get("conditionThreshold", {}).get("thresholdValue") == 0:
        threshold = condition.get("conditionThreshold")
        if not isinstance(threshold, dict) or type(threshold.get("thresholdValue", 0)) not in (int, float):
            return False
        # threshold_value is an implicit-presence double: canonical ProtoJSON omits zero.
        # https://protobuf.dev/programming-guides/json/#presence-and-default-values
        condition["conditionThreshold"] = {"thresholdValue": 0, **threshold}
    return condition == expected_condition


@closed_shape("Alert policy")
def monitoring_policies(cloud: Cloud) -> list[dict]:
    policies, page_token = [], None
    for _ in range(10):
        query = urlencode({"pageSize": 100, **({"pageToken": page_token} if page_token else {})})
        page = cloud.call("monitoring", f"v3/projects/{PROJECT}/alertPolicies?{query}", step=POLICY_LIST)
        policies.extend(page.get("alertPolicies", []))
        page_token = page.get("nextPageToken")
        if not page_token:
            return policies
    raise OperationError("Monitoring policy inventory exceeds the bounded inspection size")


@closed_shape("Alert policy")
def missing_policies(policies: list[dict], drift: str) -> list[dict]:
    """The owned alert policies not yet created; one present in any other form, or more than once, is refused."""
    missing = []
    for expected in policy_specs():
        matching = [policy for policy in policies if policy.get("displayName") == expected["displayName"]]
        if not matching:
            missing.append(expected)
        elif len(matching) != 1 or not policy_matches(matching[0], expected):
            raise OperationError(drift)
    return missing


def ensure_monitoring(cloud: Cloud) -> None:
    check_channel(cloud)
    metric = cloud.call("logging", METRIC_PATH, missing_ok=True, step=METRIC_READ)
    if metric is None:
        metric = cloud.call("logging", f"v2/projects/{PROJECT}/metrics", method="POST", body=heartbeat_spec(),
                            step=METRIC_CREATE)
    check_heartbeat_metric(metric)
    for expected in missing_policies(monitoring_policies(cloud), POLICY_DRIFT):
        created = cloud.call("monitoring", f"v3/projects/{PROJECT}/alertPolicies", method="POST", body=expected,
                             step=POLICY_CREATE)
        if not policy_matches(created, expected):
            raise OperationError(POLICY_DRIFT)
    print("Feedback cleanup failure and stale-heartbeat alert routing configured; delivery not exercised")


def inspect_channel(cloud: Cloud) -> bool:
    check_channel(cloud)
    print("Feature alert channel: enabled email with no verification pending; end-to-end delivery unverified")
    return True


def inspect_policies(cloud: Cloud) -> bool:
    missing = missing_policies(monitoring_policies(cloud),
                               "Feedback cleanup alert policies must exactly match the enabled, owned definitions")
    if missing:
        # Not yet provisioned is incomplete, not drift: provisioning creates exactly these.
        print("Feedback cleanup alert policies: absent " + ", ".join(f"'{spec['displayName']}'" for spec in missing))
        return False
    print("Feedback cleanup alert policies: enabled, owned and routed to the feature channel")
    return True


def inspect_heartbeat(cloud: Cloud) -> bool:
    metric = cloud.call("logging", METRIC_PATH, missing_ok=True, step=METRIC_READ)
    if metric is None:
        print("Feedback cleanup heartbeat metric: absent")
        return False
    check_heartbeat_metric(metric)
    now = datetime.now(timezone.utc)
    query = urlencode({
        "filter": policy_specs()[1]["conditions"][0]["conditionAbsent"]["filter"],
        "interval.startTime": (now - timedelta(hours=2)).isoformat(), "interval.endTime": now.isoformat(), "pageSize": 100,
    })
    series = cloud.call("monitoring", f"v3/projects/{PROJECT}/timeSeries?{query}", step=SERIES_READ).get("timeSeries", [])
    values = [point.get("value", {}).get("int64Value") for row in series for point in row.get("points", [])]
    heartbeat_seen = any(isinstance(value, str) and 1 <= len(value) <= 20 and value.isascii()
                         and value.isdecimal() and int(value) > 0 for value in values)
    print("Normal-cleanup monitoring heartbeat: " + ("observed" if heartbeat_seen else "not yet observed"))
    return heartbeat_seen


def create_body(spec: dict) -> dict:
    """The body of a Cloud Run v2 create. The create's jobId or serviceId names the resource, and Cloud Run refuses
    a body that names it ("job.name must be empty on CreateJobRequest"); an update keeps the name."""
    return {key: value for key, value in spec.items() if key != "name"}


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


def capability_gaps(cloud: Cloud, permissions: frozenset[str], runtime: str | None) -> list[str]:
    """Return the fixed permission names the acting identity lacks, without changing anything.

    Project testIamPermissions needs no permission and covers grants inherited from above the project; a grant
    on a single resource is invisible to it, so actAs is tested on the runtime identity itself and image read on
    the API image's repository (both operations deploy that image). Only names from the fixed lists are returned;
    the provider's answer is used for membership alone.
    """
    missing = sorted(permissions - held(cloud, "cloudresourcemanager", f"v1/projects/{PROJECT}", sorted(permissions)))
    if runtime is not None and ACT_AS not in held(cloud, "iam", f"v1/projects/-/serviceAccounts/{runtime}", [ACT_AS]):
        missing.append(ACT_AS + " on the API runtime identity")
    if IMAGE_READ not in held(cloud, "artifactregistry", "v1/" + IMAGE_REPOSITORY, [IMAGE_READ]):
        missing.append(IMAGE_READ + " on the API image repository")
    return missing


def held(cloud: Cloud, api: str, resource: str, wanted: list[str]) -> set[str]:
    """The fixed names the acting identity holds on one resource, inherited grants included; membership use only.

    A malformed answer grants nothing.
    """
    if not wanted:
        return set()
    answer = cloud.call(api, resource + ":testIamPermissions", method="POST", body={"permissions": wanted},
                        step=CAPABILITY_READ)
    granted = answer.get("permissions", []) if isinstance(answer, dict) else []
    return {name for name in granted if isinstance(name, str)} if isinstance(granted, list) else set()


def require_approved_image(service: dict) -> None:
    """Refuse an API image outside the repository whose read the capability preflight tests (no parsing of others)."""
    containers = service.get("template", {}).get("containers", [])
    image = containers[0].get("image", "") if len(containers) == 1 and isinstance(containers[0], dict) else ""
    if not isinstance(image, str) or not API_IMAGE.fullmatch(image):
        raise OperationError("API image is outside the approved Artifact Registry repository")


def require_execution_success(execution: dict, label: str) -> None:
    # The run operation reports its execution; a reported failure must not wait out the readiness deadline.
    if not isinstance(execution, dict):
        return
    if (execution.get("failedCount", 0) or execution.get("cancelledCount", 0)
            or (execution.get("completionTime") and execution.get("succeededCount") != 1)):
        raise OperationError(f"{label} did not succeed; inspect its counts-only job ledger before a fresh approved run")


def provision_writes(cloud: Cloud, runtime: str) -> frozenset[str]:
    """Refuse, read-only and before provisioning's first write, every existing resource a step would refuse, and
    return the write permissions this run's steps will use on the state it read.

    Provisioning creates what is absent and converges what it owns; these states it refuses instead. Each step
    still checks what it reaches, so this only moves the refusals ahead of the writes. Only a read that finds a
    resource absent (404) plans its create; a denied read stops here with its label, and a malformed answer or
    drift is refused, so neither is planned as absent or as already approved; a policy without an etag is refused
    too, because its write-back would not be conditional. A resource or grant the founder made by hand in the
    approved shape needs no create or setIamPolicy permission.
    """
    writes, member = set(EVERY_RUN_WRITES), "serviceAccount:" + runtime
    check_channel(cloud)
    metric = cloud.call("logging", METRIC_PATH, missing_ok=True, step=METRIC_READ)
    if metric is None:
        writes.add("logging.logMetrics.create")
    else:
        check_heartbeat_metric(metric)
    if missing_policies(monitoring_policies(cloud), POLICY_DRIFT):
        writes.add("monitoring.alertPolicies.create")
    role = cloud.call("iam", "v1/" + ROLE, missing_ok=True, step=ROLE_READ)
    if role is None:
        writes.add("iam.roles.create")
    else:
        check_role(role)
    for environment, name in BUCKETS.items():
        bucket = cloud.call("storage", "storage/v1/b/" + name, missing_ok=True, step=BUCKET_READ)
        if bucket is None:
            writes |= {"storage.buckets.create", "storage.buckets.setIamPolicy"}
            continue
        check_bucket(bucket, environment)
        policy = cloud.call("storage", policy_path("storage/v1/b/" + name, storage=True), step=BUCKET_POLICY_READ)
        check_runtime_bucket_policy(policy, runtime, granted=False)
        policy_etag(policy)
        if not bound(policy, ROLE, member):
            writes.add("storage.buckets.setIamPolicy")
    job = cloud.call("run", "v2/" + JOB, missing_ok=True, step=JOB_READ)
    if job is None:
        writes |= {"run.jobs.create", "run.jobs.setIamPolicy"}
    else:
        check_owned_job(job)
        policy = cloud.call("run", policy_path("v2/" + JOB), step=JOB_POLICY_READ)
        check_private_policy(policy)
        policy_etag(policy)
        writes.add("run.jobs.update")  # the job's specification is always converged
        if not bound(policy, "roles/run.invoker", member):
            writes.add("run.jobs.setIamPolicy")
    schedule = cloud.call("cloudscheduler", "v1/" + SCHEDULE, missing_ok=True, step=SCHEDULE_READ)
    if schedule is None:
        writes.add("cloudscheduler.jobs.create")
    else:
        check_owned_schedule(schedule)
        writes.add("cloudscheduler.jobs.update")
    return frozenset(writes)


def provision_gaps(cloud: Cloud, runtime: str) -> list[str]:
    """The permissions this run lacks: its reads, actAs and image read first, then only the writes its state needs."""
    missing = capability_gaps(cloud, PROVISION_READS, runtime)
    if missing:
        return missing
    writes = provision_writes(cloud, runtime)
    return sorted(writes - held(cloud, "cloudresourcemanager", f"v1/projects/{PROJECT}", sorted(writes)))


def provision(cloud: Cloud, service: dict) -> None:
    spec = job_spec(service)  # validate required identity/secret references before any mutation
    require_approved_image(service)
    runtime = spec["template"]["template"]["serviceAccount"]
    missing = provision_gaps(cloud, runtime)
    if missing:
        raise OperationError("Provisioning identity lacks required permissions; nothing was changed: " + ", ".join(missing))
    ensure_monitoring(cloud)  # create the success metric before the first genuine cleanup heartbeat
    ensure_buckets(cloud, runtime)
    current = cloud.call("run", "v2/" + JOB, missing_ok=True, step=JOB_READ)
    if current is None:
        cloud.wait(cloud.call("run", f"v2/{PARENT}/jobs?jobId=earningsnerd-feedback-media-cleanup", method="POST",
                              body=create_body(spec), step=JOB_CREATE), JOB_CREATE)
    else:
        check_owned_job(current)
        spec["etag"] = current["etag"]
        # Cloud Run v2 Job.patch replaces its editable specification; it has no updateMask.
        cloud.wait(cloud.call("run", f"v2/{JOB}", method="PATCH", body=spec, step=JOB_UPDATE), JOB_UPDATE)
    bind(cloud, "run", "v2/" + JOB, "roles/run.invoker", "serviceAccount:" + runtime,
         read_step=JOB_POLICY_READ, write_step=JOB_POLICY_WRITE)
    schedule = {"name": SCHEDULE, "description": SCHEDULE_DESCRIPTION,
                "schedule": "17 * * * *", "timeZone": "Etc/UTC", "attemptDeadline": "60s",
                "retryConfig": {"retryCount": 0}, "httpTarget": {
                    "uri": f"https://run.googleapis.com/v2/{JOB}:run", "httpMethod": "POST",
                    "headers": {"Content-Type": "application/json"}, "body": "e30=",
                    "oauthToken": {"serviceAccountEmail": runtime, "scope": "https://www.googleapis.com/auth/cloud-platform"}}}
    current_schedule = cloud.call("cloudscheduler", "v1/" + SCHEDULE, missing_ok=True, step=SCHEDULE_READ)
    if current_schedule is None:
        cloud.call("cloudscheduler", f"v1/{PARENT}/jobs", method="POST", body=schedule, step=SCHEDULE_CREATE)
    else:
        check_owned_schedule(current_schedule)
        cloud.call("cloudscheduler", f"v1/{SCHEDULE}?updateMask=schedule,timeZone,attemptDeadline,retryConfig,httpTarget",
                   method="PATCH", body=schedule, step=SCHEDULE_UPDATE)
    # Cleanup can succeed with no rows without contacting GCS. A separate manifest-backed probe
    # proves object create/read/conditional-delete using the runtime identity, without user data.
    require_execution_success(cloud.wait(cloud.call("run", "v2/" + JOB + ":run", method="POST", body={},
                                                    step=CLEANUP_RUN), CLEANUP_RUN), "Cleanup execution")
    require_execution_success(cloud.wait(cloud.call("run", "v2/" + JOB + ":run", method="POST", step=PROBE_RUN, body={
        "overrides": {"containerOverrides": [{"name": "cleanup", "args": PROBE_ARGS}]},
    }), PROBE_RUN), "Storage probe execution")
    # A new log metric may take several minutes to publish its first time series. No new writes
    # occur while waiting, and a timeout leaves the rollout disabled rather than claiming monitoring.
    deadline = time.monotonic() + 300
    while not inspect(cloud):
        if time.monotonic() >= deadline:
            raise OperationError("Resources provisioned; readiness not yet observable (the component lines above name what is pending)")
        time.sleep(10)
    print("Private storage probe and cleanup succeeded; uploads remain unchanged")


def environment_differences(env: list, wanted: dict[str, dict]) -> list[str]:
    """Name each approved variable that is missing or differs, and count any other names; never print a value.

    The approved names are fixed in job_spec, so naming them shows nothing a reader of this file cannot; a name
    outside them is only counted.
    """
    def without_version(entry: dict) -> dict | None:
        reference = entry.get("valueSource", {}).get("secretKeyRef")
        if not isinstance(reference, dict):
            return None
        return {**entry, "valueSource": {**entry["valueSource"], "secretKeyRef": {**reference, "version": None}}}

    actual = {item.get("name"): item for item in env}
    differences = ["environment repeats a name"] if len(actual) != len(env) else []
    for name, item in wanted.items():
        if name not in actual:
            differences.append(f"environment {name} missing")
        elif actual[name] != item:
            # Only the version differs exactly when the two are equal once both versions are set aside.
            stripped = without_version(actual[name])
            version_only = stripped is not None and stripped == without_version(item)
            differences.append(f"environment {name} " + ("secret version" if version_only else "value"))
    others = len(set(actual) - set(wanted))
    if others:
        differences.append(f"environment has {others} other name" + ("s" if others > 1 else ""))
    return differences


def task_differences(task: dict, expected: dict, args: list[str]) -> list[str]:
    """Name, from a closed set, each field of a task that differs from the approved task; none when it matches.

    Ops logs are public, so a difference is named and never shown: the field, and for an image whether the
    provider recorded it by digest. A provider answer of another shape still raises (closed_shape, inspect).
    """
    containers = task.get("containers", [])
    if len(containers) != 1:
        return ["container count"]
    container = containers[0]
    wanted = expected["containers"][0]
    differences = [name for name, same in (
        ("service account", task.get("serviceAccount") == expected["serviceAccount"]),
        ("timeout", task.get("timeout") == expected["timeout"]),
        ("retries", task.get("maxRetries") == expected["maxRetries"]),
        ("volumes", task.get("volumes", []) == expected.get("volumes", [])),
        ("network access", task.get("vpcAccess") == expected.get("vpcAccess")),
        ("container name", container.get("name") == "cleanup"),
        ("command", container.get("command") == ["python"]),
        ("arguments", container.get("args") == args),
        ("volume mounts", container.get("volumeMounts", []) == wanted.get("volumeMounts", [])),
        ("resource limits", container.get("resources", {}).get("limits") == wanted["resources"]["limits"]),
    ) if not same]
    image = container.get("image")
    if image != wanted["image"]:
        differences.append("image recorded by digest" if isinstance(image, str) and "@sha256:" in image else "image")
    return differences + environment_differences(container.get("env", []),
                                                 {item["name"]: item for item in wanted["env"]})


def matches_task(task: dict, expected: dict, args: list[str]) -> bool:
    return not task_differences(task, expected, args)


def serving_digest(cloud: Cloud, service: dict) -> str | None:
    """The image digest Cloud Run resolved for production's revision, or None unless one revision serves all traffic.

    The cleanup job runs the API's own image reference (job_spec), and a job execution records the digest that
    reference resolved to, not the reference (live read-back, 11 November). So an execution ran the release
    production serves exactly when it records this digest.
    """
    revision = service.get("latestReadyRevision", "").rsplit("/", 1)[-1]
    traffic = [row for row in service.get("trafficStatuses", []) if row.get("percent", 0)]
    if (not revision or service.get("reconciling") or len(traffic) != 1 or traffic[0].get("percent") != 100
            or traffic[0].get("revision", "").rsplit("/", 1)[-1] != revision
            or any(row.get("tag") for row in service.get("trafficStatuses", []))):
        return None
    resolved = cloud.call(f"{REGION}-run", f"apis/serving.knative.dev/v1/namespaces/{PROJECT}/revisions/{revision}",
                          step=REVISION_READ)
    parts = IMAGE_PARTS.fullmatch(resolved.get("status", {}).get("imageDigest", ""))
    return parts["digest"] if parts and parts["digest"] and parts["tag"] is None else None


def recorded_digest(task: dict, expected: dict) -> str | None:
    """The digest an execution's task records, if it names the approved repository and no tag but the approved one."""
    recorded = IMAGE_PARTS.fullmatch(task["containers"][0]["image"])
    approved = IMAGE_PARTS.fullmatch(expected["containers"][0]["image"])
    if not recorded or not approved or not recorded["digest"]:
        return None
    return recorded["digest"] if recorded["tag"] in (None, approved["tag"]) else None


# An execution is Cloud Run's own record of the task it ran, and it differs from the job's in two ways that do not
# change what ran (live read-back, 11 November): it pins the image by digest, and it does not repeat the job's Cloud
# SQL volume and mount as the job states them. A run's overrides carry only arguments, environment, task count and
# timeout, so an execution cannot differ from its job in either; inspect_job holds the job itself to both, and an
# execution's digest must be the one production serves.
EXECUTION_RECORD_FIELDS = ("volumes", "volume mounts")


def execution_gaps(execution: dict | None, expected: dict, args: list[str], digest: str | None = None) -> list[str]:
    """Name each reason an execution is not recent, successful evidence of the approved task; none when it is.

    digest is the image digest production serves (serving_digest); without it, an image recorded by digest is a gap.
    """
    if not execution:
        return ["no execution with these arguments among the newest read"]
    gaps = []
    if (execution.get("succeededCount") != 1 or execution.get("failedCount", 0)
            or execution.get("cancelledCount", 0)):
        gaps.append("not succeeded")
    if execution.get("taskCount") != 1:
        gaps.append("task count")
    task = execution.get("template", {})
    differences = [name for name in task_differences(task, expected, args) if name not in EXECUTION_RECORD_FIELDS]
    if ("image recorded by digest" in differences and digest is not None
            and recorded_digest(task, expected) == digest):
        differences.remove("image recorded by digest")
    gaps += differences
    try:
        completed = datetime.fromisoformat(execution["completionTime"].replace("Z", "+00:00"))
        if not timedelta(0) <= datetime.now(timezone.utc) - completed <= timedelta(hours=2):
            gaps.append("not completed within two hours")
    except (KeyError, ValueError, TypeError):
        gaps.append("no completion time")
    return gaps


def recent_success(execution: dict | None, expected: dict, args: list[str]) -> bool:
    return not execution_gaps(execution, expected, args)


def inspect_role(cloud: Cloud) -> bool:
    role = cloud.call("iam", "v1/" + ROLE, missing_ok=True, step=ROLE_READ)
    if role is None:
        print("Feedback object role: absent")
        return False
    check_role(role)
    print("Feedback object role: active with object create/get/delete only")
    return True


def inspect_bucket(cloud: Cloud, environment: str, runtime: str) -> bool:
    name = BUCKETS[environment]
    bucket = cloud.call("storage", "storage/v1/b/" + name, missing_ok=True, step=BUCKET_READ)
    if bucket is None:
        print(f"{environment} bucket: absent")
        return False
    check_bucket(bucket, environment)
    policy = cloud.call("storage", policy_path("storage/v1/b/" + name, storage=True), step=BUCKET_POLICY_READ)
    check_runtime_bucket_policy(policy, runtime)
    print(f"{environment} bucket: private retention settings verified")
    return True


def inspect(cloud: Cloud) -> bool:
    """Read every prerequisite and print its state; raise after all of them if any was refused or unreadable.

    Each component is one independently readable resource with its own sub-resources, so a failed read never
    stops another resource's checks. Absent resources are incomplete (False). A component whose provider read
    fails is UNVERIFIED and readable drift is refused; both raise only once every component has been read, so
    one inspection shows the whole state before a retry, and an unverified component never masks a refused one.
    """
    service = cloud.call("run", "v2/" + SERVICE, step=SERVICE_READ)
    runtime = service.get("template", {}).get("serviceAccount")
    if not runtime:
        raise OperationError("API runtime identity unavailable")
    components = [("Feedback object role", lambda: inspect_role(cloud))]
    components += [(f"{environment} bucket", lambda environment=environment: inspect_bucket(cloud, environment, runtime))
                   for environment in BUCKETS]
    components += [("Cleanup job", lambda: inspect_job(cloud, service, runtime)),
                   ("Cleanup schedule", lambda: inspect_schedule(cloud, runtime)),
                   ("Alert channel", lambda: inspect_channel(cloud)),
                   ("Alert policies", lambda: inspect_policies(cloud)),
                   ("Heartbeat metric", lambda: inspect_heartbeat(cloud))]
    ready, refused, unverified = True, [], []
    for name, check in components:
        try:
            ready = check() and ready
        except ProviderError as exc:
            print(f"{name}: UNVERIFIED ({exc})")
            unverified.append(name)
        except OperationError as exc:
            print(f"{name}: refused ({exc})")
            refused.append(name)
        except SHAPE_ERRORS:  # an answer of another shape than the checks read
            print(f"{name}: refused (answer is malformed)")
            refused.append(name)
    if refused:
        raise OperationError("Feedback media prerequisites refused: " + ", ".join(refused)
                             + (f" (also unverified: {', '.join(unverified)})" if unverified else ""))
    if unverified:
        raise OperationError("Feedback media prerequisites unverified: " + ", ".join(unverified))
    return ready


def inspect_job(cloud: Cloud, service: dict, runtime: str) -> bool:
    job = cloud.call("run", "v2/" + JOB, missing_ok=True, step=JOB_READ)
    if job is None:
        print("Cleanup job: absent")
        return False
    expected = job_spec(service)["template"]["template"]
    task = job.get("template", {}).get("template", {})
    differences = task_differences(task, expected, CLEANUP_ARGS)
    if (job.get("labels", {}).get("purpose") != "feedback-media"
            or job.get("template", {}).get("taskCount") != 1
            or job.get("template", {}).get("parallelism") != 1 or differences):
        raise OperationError("Cleanup job differs from the approved runtime, image or bounded configuration"
                             + (f" ({', '.join(differences)})" if differences else ""))
    job_policy = cloud.call("run", policy_path("v2/" + JOB), step=JOB_POLICY_READ)
    check_private_policy(job_policy)
    if not bound(job_policy, "roles/run.invoker", "serviceAccount:" + runtime):  # the test the planner and bind() use
        raise OperationError("Cleanup scheduler's job invocation grant is missing")
    # API sorts creation time descending. Keep the latest attempt for each mode, including failures;
    # an older success must not hide a failed current attempt. Fifty bounds a noisy retry history.
    executions = cloud.call("run", f"v2/{JOB}/executions?pageSize=50", step=EXECUTIONS_READ).get("executions", [])
    latest, newest = {}, None
    seen = {"cleanup": 0, "probe": 0, "other arguments": 0, "no arguments": 0, "no single container": 0,
            "still running": 0}
    for execution in executions:
        if not (execution.get("completionTime") or execution.get("failedCount") or execution.get("cancelledCount")):
            # A run in progress has no result yet, so the newest finished attempt of its mode stands until it ends: a
            # scheduled cleanup running at :17 must not refuse an enable. A run reporting a failed or cancelled task has
            # its result even before its completion time is recorded, and a finished failure still counts, below.
            seen["still running"] += 1
            continue
        if newest is None:
            newest = execution
        containers = execution.get("template", {}).get("containers", [])
        if len(containers) != 1:
            seen["no single container"] += 1
            continue
        args = containers[0].get("args")
        mode = "cleanup" if args == CLEANUP_ARGS else "probe" if args == PROBE_ARGS else None
        seen[mode or ("other arguments" if args else "no arguments")] += 1
        if mode is not None:
            latest.setdefault(mode, execution)
    digest = serving_digest(cloud, service) if executions else None
    cleanup_gaps = execution_gaps(latest.get("cleanup"), expected, CLEANUP_ARGS, digest)
    probe_gaps = execution_gaps(latest.get("probe"), expected, PROBE_ARGS, digest)
    succeeded, probe_succeeded = not cleanup_gaps, not probe_gaps
    # Counts and closed field names only (Ops logs are public): why no execution of a mode is current evidence.
    print(f"Cleanup job executions read: {len(executions)}; by arguments: "
          + ", ".join(f"{count} {kind}" for kind, count in seen.items()))
    if executions and digest is None:
        print("Serving image digest: unverified (production is not one stable revision serving all traffic, "
              "or its revision reports no digest)")
    print("Cleanup last execution: " + ("succeeded" if succeeded else f"unverified ({', '.join(cleanup_gaps)})"))
    print("Private storage probe: " + ("succeeded" if probe_succeeded else f"unverified ({', '.join(probe_gaps)})"))
    if newest is not None and not succeeded:
        # Never empty here: a newest finished execution with no gap against the job's own task is the current cleanup
        # evidence. A run still in progress is not described; it has no result yet.
        print("Cleanup job newest finished execution, against the job's own task: "
              + ", ".join(execution_gaps(newest, expected, CLEANUP_ARGS, digest)))
    # The probe refuses missing create/get/delete and records broader storage access, without refusing it, while the
    # backend identity holds broader storage access than the feature needs (founder, 10 November; the follow-up recorded on #2027).
    print("Runtime storage permission audit: " + ("create/get/delete verified by the successful probe; broader access "
                                                  "is reported in its permissions_excess counter, not refused"
                                                  if probe_succeeded else "unverified"))
    return succeeded and probe_succeeded


def inspect_schedule(cloud: Cloud, runtime: str) -> bool:
    schedule = cloud.call("cloudscheduler", "v1/" + SCHEDULE, missing_ok=True, step=SCHEDULE_READ)
    if schedule is None:
        print("Cleanup hourly schedule: absent")
        return False
    check_owned_schedule(schedule)
    ready = (schedule.get("state") == "ENABLED" and schedule.get("schedule") == "17 * * * *"
             and schedule.get("timeZone") == "Etc/UTC"
             and schedule.get("httpTarget", {}).get("uri") == f"https://run.googleapis.com/v2/{JOB}:run"
             and schedule.get("httpTarget", {}).get("httpMethod") == "POST"
             and schedule.get("httpTarget", {}).get("body") == "e30="
             and schedule.get("httpTarget", {}).get("oauthToken", {}).get("serviceAccountEmail") == runtime)
    pending = " (state UPDATE_FAILED)" if schedule.get("state") == "UPDATE_FAILED" else ""
    print("Cleanup hourly schedule: " + ("verified" if ready else "unverified" + pending))
    return ready


def checkout_on_path() -> None:
    # The optional verifier is an Ops dependency only; production request handlers never import
    # it or connect to its isolated database. Resolve the reviewed checkout for direct CLI use.
    root = str(Path(__file__).resolve().parents[2])
    if root not in sys.path:
        sys.path.insert(0, root)


def require_live_verification(cloud: Cloud, service: dict) -> None:
    checkout_on_path()
    from ops.feedback_media.verify_manage import require_receipt
    require_receipt(cloud, service)


def verification_permissions() -> frozenset[str]:
    checkout_on_path()
    from ops.feedback_media.verify_manage import PROJECT_PERMISSIONS
    return frozenset(PROJECT_PERMISSIONS)


def report_capabilities(cloud: Cloud, service: dict) -> None:
    """Print, read-only, the fixed permissions each provisioning operation's identity would lack.

    This is the check provision-apply runs before its first write, on the state it reads now, and the set
    verify-apply tests on every run (feedback-media-verify-inspect prints the writes its state still needs; enable
    and disable each make one write and run none). It reports, never refuses: the inspection's own verdict stays
    the resource state below it.
    """
    runtime = service.get("template", {}).get("serviceAccount") or None
    for label, gaps in (
            ("feedback-media-provision-apply", lambda: provision_gaps(cloud, runtime)),
            ("feedback-media-verify-apply (every run)", lambda: capability_gaps(cloud, verification_permissions(), None))):
        if label == "feedback-media-provision-apply" and runtime is None:
            print(f"Capability for {label}: UNVERIFIED (API runtime identity unavailable, so actAs cannot be tested)")
            continue
        try:
            if label == "feedback-media-provision-apply":
                require_approved_image(service)
            missing = gaps()
        except OperationError as exc:
            print(f"Capability for {label}: UNVERIFIED ({exc})")
            continue
        print(f"Capability for {label}: " + ("all required permissions present" if not missing
                                              else "missing " + ", ".join(missing)))


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
    cloud.wait(cloud.call("run", f"v2/{SERVICE}?updateMask=template.containers", method="PATCH", step=SERVICE_UPDATE,
                          body={"name": SERVICE, "etag": service["etag"], "template": {"containers": containers}}),
               SERVICE_UPDATE)
    current = cloud.call("run", "v2/" + SERVICE, step=SERVICE_READ)
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
    service = cloud.call("run", "v2/" + SERVICE, step=SERVICE_READ)
    if operation == "feedback-media-inspect":
        report_capabilities(cloud, service)
        if not inspect(cloud):
            raise OperationError("Feedback media prerequisites are incomplete")
        return
    if operation == "feedback-media-provision-apply":
        provision(cloud, service)
    else:
        set_enabled(cloud, service, operation == "feedback-media-enable-apply")


if __name__ == "__main__":
    # ops.yml runs this file by path, as __main__, and the verifier imports it as ops.feedback_media.manage: one
    # module under both names keeps one OperationError, so a verifier refusal exits on one line, not a traceback.
    sys.modules["ops.feedback_media.manage"] = sys.modules[__name__]
    try:
        main()
    except OperationError as exc:
        raise SystemExit(str(exc)) from None
