"""Plan and provision one PAUSED recovery caller; never resume or invoke it.

The plan reads metadata only. An apply belongs behind Ops' founder-owned approval
gate and requires the exact plan hash and nonce. Scheduler's state is output-only:
create a credential-free shell first, pause and read it back, then install the
authenticated target. A failed or ambiguous bootstrap never carries the token.
The tool does not rotate the API's secret binding or activate summary generation.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ops.feedback_media.manage import Cloud, OperationError  # noqa: E402

PROJECT = "earnings-nerd"
REGION = "us-west1"
PARENT = f"projects/{PROJECT}/locations/{REGION}"
SERVICE = f"{PARENT}/services/earningsnerd-backend"
JOB = f"{PARENT}/jobs/summary-recovery-minute"
SECRET_PARENT = f"projects/{PROJECT}/secrets/"
PURPOSE = "EarningsNerd summary recovery caller v1; activation is a separate operation"
PLAN_KIND = "summary-recovery-caller-paused-v1"
IMAGE = re.compile(r"us-west1-docker\.pkg\.dev/earnings-nerd/earningsnerd/backend@sha256:[0-9a-f]{64}")
NONCE = re.compile(r"[0-9a-f]{32}")
RETRY = {"retryCount": 0, "maxRetryDuration": "0s", "minBackoffDuration": "5s",
         "maxBackoffDuration": "5s", "maxDoublings": 0}
PLAN_LIFETIME_SECONDS = 7200


class Refused(OperationError):
    """Closed local reason code; never initialized from a provider's payload."""


def fail(reason: str) -> None:
    raise Refused(reason) from None


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def instant(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        fail("invalid_plan_time")
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        fail("invalid_plan_time")
    return parsed


def origin(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".run.app")
            or not re.fullmatch(r"[a-z0-9.-]{1,253}", parsed.hostname)
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment
            or parsed.username or parsed.password or parsed.port not in (None, 443)):
        fail("api_origin_unverified")
    return "https://" + parsed.hostname


def api_snapshot(cloud: Cloud, *, binding_name: str = "INTERNAL_JOB_TOKEN") -> dict:
    if binding_name not in {"INTERNAL_JOB_TOKEN", "DATABASE_URL"}:
        fail("api_binding_unverified")
    service = cloud.call("run", "v2/" + SERVICE)
    ready = service.get("latestReadyRevision", "")
    created = service.get("latestCreatedRevision", "")
    traffic = service.get("trafficStatuses", [])
    if (service.get("reconciling") or not ready.startswith(SERVICE + "/revisions/")
            or created != ready or len(traffic) != 1 or traffic[0].get("percent") != 100
            or traffic[0].get("tag") or traffic[0].get("revision") != ready
            or not re.fullmatch(r"[a-z0-9-]{1,63}", ready.rsplit("/", 1)[-1])):
        fail("api_not_stable")
    url = origin(service.get("uri", ""))
    name = ready.rsplit("/", 1)[-1]
    revision = cloud.call(f"{REGION}-run", f"apis/serving.knative.dev/v1/namespaces/{PROJECT}/revisions/{name}")
    image = revision.get("status", {}).get("imageDigest", "")
    if not IMAGE.fullmatch(image):
        fail("api_image_unverified")
    containers = revision.get("spec", {}).get("containers", [])
    if len(containers) != 1:
        fail("api_container_unverified")
    bindings = [row for row in containers[0].get("env", []) if row.get("name") == binding_name]
    if len(bindings) != 1 or "value" in bindings[0]:
        fail("internal_token_binding_unverified")
    ref = bindings[0].get("valueFrom", {}).get("secretKeyRef", {})
    selector = ref.get("name", "")
    if not isinstance(selector, str):
        fail("internal_token_secret_unverified")
    secret_name = selector.removeprefix(SECRET_PARENT)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,255}", secret_name):
        fail("internal_token_secret_unverified")
    version = ref.get("key", "")
    if not isinstance(version, str) or not re.fullmatch(r"[1-9][0-9]{0,8}", version):
        fail("internal_token_version_not_pinned")
    version_name = f"{SECRET_PARENT}{secret_name}/versions/{version}"
    metadata = cloud.call("secretmanager", "v1/" + version_name)
    if metadata.get("name") != version_name or metadata.get("state") != "ENABLED":
        fail("internal_token_version_unavailable")
    return {"revision": ready, "image_digest": image, "origin": url,
            "secret_version": version_name}


def scheduler_snapshot(job: dict | None, target: str) -> dict:
    """Project only safe configuration; no header values or hashes leave this reader."""
    if job is None:
        return {"state": "ABSENT"}
    http = job.get("httpTarget", {})
    headers = http.get("headers", {})
    lowered = {str(key).lower(): value for key, value in headers.items()}
    schedule = job.get("schedule")
    if (job.get("name") != JOB or job.get("description") != PURPOSE
            or job.get("state") != "PAUSED" or job.get("timeZone") != "Etc/UTC"
            or not valid_schedule(schedule) or job.get("attemptDeadline") != "180s"
            or not retry_matches(job.get("retryConfig", {}))
            or http.get("uri") != target or http.get("httpMethod") != "POST"
            or http.get("body") or http.get("oauthToken") or http.get("oidcToken")
            or set(lowered) - {"content-type", "x-internal-token", "user-agent"}
            or len(lowered) != len(headers)):
        fail("existing_caller_not_owned_and_paused")
    return {"state": "PAUSED", "schedule": schedule, "time_zone": "Etc/UTC",
            "attempt_deadline": "180s", "retry_config": dict(RETRY),
            "internal_token_header_present": bool(lowered.get("x-internal-token"))}


def snapshot(cloud: Cloud) -> dict:
    api = api_snapshot(cloud)
    caller = cloud.call("cloudscheduler", "v1/" + JOB, missing_ok=True)
    return {"api": api, "caller": scheduler_snapshot(caller, api["origin"] + "/internal/jobs/summary-recovery")}


def make_plan(cloud: Cloud, *, now: datetime | None = None, nonce: str | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    now = instant(now.isoformat())
    nonce = secrets.token_hex(16) if nonce is None else nonce
    if not NONCE.fullmatch(nonce):
        fail("invalid_nonce")
    bootstrap = now + timedelta(days=7)
    manifest = {"kind": PLAN_KIND, "nonce": nonce, "issued_at": now.isoformat(),
                "expires_at": (now + timedelta(seconds=PLAN_LIFETIME_SECONDS)).isoformat(),
                "resource": JOB, "snapshot": snapshot(cloud),
                "bootstrap_schedule": f"{bootstrap.minute} {bootstrap.hour} {bootstrap.day} {bootstrap.month} *",
                "desired_schedule": "* * * * *", "desired_state": "PAUSED"}
    return {"manifest": manifest, "sha256": sha(manifest)}


def validate_plan(plan: dict, expected_sha: str, approval_nonce: str, now: datetime) -> dict:
    if (os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("GITHUB_RUN_ATTEMPT") != "1"
            or os.environ.get("SUMMARY_DELIVERY_APPROVED") != "true"):
        fail("protected_approval_required")
    if set(plan) != {"manifest", "sha256"} or not isinstance(plan["manifest"], dict):
        fail("invalid_plan")
    manifest = plan["manifest"]
    if (set(manifest) != {"kind", "nonce", "issued_at", "expires_at", "resource", "snapshot",
                         "bootstrap_schedule", "desired_schedule", "desired_state"}
            or manifest.get("kind") != PLAN_KIND or manifest.get("resource") != JOB
            or manifest.get("desired_schedule") != "* * * * *" or manifest.get("desired_state") != "PAUSED"
            or not isinstance(approval_nonce, str) or not NONCE.fullmatch(approval_nonce)
            or not hmac.compare_digest(manifest.get("nonce", ""), approval_nonce)
            or not re.fullmatch(r"[0-9a-f]{64}", expected_sha)
            or not hmac.compare_digest(sha(manifest), expected_sha)
            or not hmac.compare_digest(plan.get("sha256", ""), expected_sha)):
        fail("plan_approval_mismatch")
    issued, expires = instant(manifest["issued_at"]), instant(manifest["expires_at"])
    if not issued <= now <= expires or (expires - issued).total_seconds() != PLAN_LIFETIME_SECONDS:
        fail("plan_expired_or_invalid")
    bootstrap = issued + timedelta(days=7)
    if manifest["bootstrap_schedule"] != f"{bootstrap.minute} {bootstrap.hour} {bootstrap.day} {bootstrap.month} *":
        fail("invalid_bootstrap_schedule")
    return manifest


def bootstrap_spec(manifest: dict) -> dict:
    return {"name": JOB, "description": PURPOSE, "schedule": manifest["bootstrap_schedule"],
            "timeZone": "Etc/UTC", "attemptDeadline": "180s", "retryConfig": dict(RETRY),
            "httpTarget": {"uri": manifest["snapshot"]["api"]["origin"] + "/internal/jobs/summary-recovery",
                           "httpMethod": "POST", "headers": {"Content-Type": "application/json"}}}


def require_shell(job: dict, spec: dict) -> None:
    observed = dict(job)
    observed["state"] = "PAUSED"
    scheduler_snapshot(observed, spec["httpTarget"]["uri"])
    headers = {key.lower(): value for key, value in job.get("httpTarget", {}).get("headers", {}).items()}
    if (job.get("state") not in {"ENABLED", "PAUSED"} or job.get("schedule") != spec["schedule"]
            or headers.get("x-internal-token") or job.get("attemptDeadline") != "180s"):
        fail("bootstrap_readback_mismatch")


def secret_value(cloud: Cloud, version: str) -> str:
    response = cloud.call("secretmanager", "v1/" + version + ":access")
    try:
        encoded = response["payload"]["data"]
        if response.get("name") != version or not isinstance(encoded, str) or len(encoded) > 2048:
            fail("internal_token_value_unavailable")
        value = base64.b64decode(encoded, validate=True).decode("ascii")
        if not 32 <= len(value) <= 512 or any(ord(char) < 33 or ord(char) > 126 for char in value):
            fail("internal_token_value_unavailable")
    except (KeyError, TypeError, ValueError, UnicodeError):
        fail("internal_token_value_unavailable")
    return value


def retry_matches(config: dict) -> bool:
    # Protobuf JSON omits explicit numeric zero values. The retained target
    # carries these zeros; compare their decoded values, not spelling presence.
    return (isinstance(config, dict) and not set(config) - set(RETRY)
            and type(config.get("retryCount", 0)) is int and config.get("retryCount", 0) == 0
            and config.get("maxRetryDuration", "0s") == "0s"
            and config.get("minBackoffDuration") == "5s" and config.get("maxBackoffDuration") == "5s"
            and type(config.get("maxDoublings", 0)) is int and config.get("maxDoublings", 0) == 0)


def valid_schedule(value: object) -> bool:
    if value == "* * * * *":
        return True
    if not isinstance(value, str):
        return False
    match = re.fullmatch(r"([0-9]{1,2}) ([0-9]{1,2}) ([0-9]{1,2}) ([0-9]{1,2}) \*", value)
    if not match:
        return False
    minute, hour, day, month = map(int, match.groups())
    return 0 <= minute <= 59 and 0 <= hour <= 23 and 1 <= day <= 31 and 1 <= month <= 12


def apply_plan(cloud: Cloud, plan: dict, *, expected_sha: str, approval_nonce: str,
               now: datetime | None = None) -> dict:
    manifest = validate_plan(plan, expected_sha, approval_nonce, now or datetime.now(timezone.utc))
    if snapshot(cloud) != manifest["snapshot"]:
        fail("plan_configuration_changed")
    if manifest["snapshot"]["caller"]["state"] == "ABSENT":
        shell = bootstrap_spec(manifest)
        cloud.call("cloudscheduler", "v1/" + PARENT + "/jobs", method="POST", body=shell)
        created = cloud.call("cloudscheduler", "v1/" + JOB)
        require_shell(created, shell)
        if created["state"] == "ENABLED":
            cloud.call("cloudscheduler", "v1/" + JOB + ":pause", method="POST", body={})
    # This read precedes secret access, including recovery from a prior interrupted
    # credential-free create/pause. There is no run or resume operation in this tool.
    target = manifest["snapshot"]["api"]["origin"] + "/internal/jobs/summary-recovery"
    paused = cloud.call("cloudscheduler", "v1/" + JOB)
    scheduler_snapshot(paused, target)
    token = secret_value(cloud, manifest["snapshot"]["api"]["secret_version"])
    configured = {**bootstrap_spec(manifest), "schedule": "* * * * *"}
    configured["httpTarget"]["headers"]["X-Internal-Token"] = token
    cloud.call("cloudscheduler", "v1/" + JOB + "?updateMask=description,schedule,timeZone,attemptDeadline,retryConfig,httpTarget",
               method="PATCH", body=configured)
    readback = cloud.call("cloudscheduler", "v1/" + JOB)
    projected = scheduler_snapshot(readback, target)
    headers = {key.lower(): value for key, value in readback.get("httpTarget", {}).get("headers", {}).items()}
    if (projected["schedule"] != "* * * * *" or projected["attempt_deadline"] != "180s"
            or not retry_matches(projected["retry_config"])
            or not hmac.compare_digest(headers.get("x-internal-token", ""), token)
            or api_snapshot(cloud) != manifest["snapshot"]["api"]):
        fail("paused_caller_readback_unverified")
    return {"state": "PAUSED", "resource": JOB, "plan_sha256": expected_sha,
            "api_revision": manifest["snapshot"]["api"]["revision"], "schedule": "* * * * *",
            "internal_token_header_present": True, "activation_performed": False,
            "scope": "Configuration only; no endpoint invocation or successful recovery delivery is established."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("plan", "apply-paused"))
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--expected-plan-sha256", default="")
    parser.add_argument("--approval-nonce", default="")
    args = parser.parse_args(argv)
    try:
        if args.operation == "plan":
            result = make_plan(Cloud())
        else:
            if args.plan is None:
                fail("bounded_plan_required")
            with args.plan.open("rb") as handle:
                content = handle.read(16385)
            if len(content) > 16384:
                fail("bounded_plan_required")
            plan = json.loads(content)
            # Validate before obtaining any cloud credential or issuing a read.
            validate_plan(plan, args.expected_plan_sha256, args.approval_nonce, datetime.now(timezone.utc))
            result = apply_plan(Cloud(), plan, expected_sha=args.expected_plan_sha256,
                                approval_nonce=args.approval_nonce)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Refused as exc:
        print(json.dumps({"state": "UNVERIFIED", "reason": str(exc)}))
        return 1
    except Exception:
        # Provider errors can include headers or secret data. Only the closed final
        # status leaves the CLI; callers retain no exception repr/traceback.
        print(json.dumps({"state": "UNVERIFIED", "reason": "recovery_caller_operation_refused"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
