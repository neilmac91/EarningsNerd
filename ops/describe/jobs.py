"""Read and project every fixed Cloud Run job, retaining evidence when another read fails.

Run by ops.yml as ``python3 ops/describe/jobs.py``; stdlib only. Nine sequential reads have
40-second deadlines (at most six minutes of gcloud waits within the ten-minute step).
Only closed error classes leave the gcloud boundary. Failed reads and malformed jobs remain
UNVERIFIED, readable drift remains FAIL, and either makes the whole inventory nonzero.
Command values, arbitrary environment names/values and unexpected image identities are withheld.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ops.describe.summary_configuration import runtime_configuration

expected_pools = {
    "earningsnerd-pregenerate": "3",
    "earningsnerd-filing-scan": "1",
    "earningsnerd-filing-digest": "1",
    "earningsnerd-backfill-facts": "1",
    "earningsnerd-earnings-calendar-refresh": "1",
    "earningsnerd-earnings-day-alerts": "1",
    "earningsnerd-notable-filings": "1",
    "earningsnerd-retention-purge": "1",
    "earningsnerd-feedback-media-cleanup": "1",
}
expected_entrypoints = {
    "earningsnerd-backfill-facts": (["python"], ["scripts/backfill_facts.py", "--only-new"]),
}
GCLOUD_TIMEOUT = 40
MAX_RESPONSE_BYTES = 1_048_576
MAX_ENV_ENTRIES = 256
IMAGE = re.compile(
    r"us-west1-docker\.pkg\.dev/earnings-nerd/earningsnerd/backend"
    r"(?::[0-9a-f]{7,40}|@sha256:[0-9a-f]{64})"
)


def gcloud_json(name: str, region: str) -> tuple[dict | None, str | None]:
    """The only stderr-reading seam; never expose gcloud output or exception messages."""
    try:
        raw = subprocess.check_output(
            ["gcloud", "run", "jobs", "describe", name, "--region=" + region, "--format=json"],
            text=True, stderr=subprocess.PIPE, timeout=GCLOUD_TIMEOUT,
        )
        if len(raw.encode("utf-8")) > MAX_RESPONSE_BYTES:
            return None, "response_too_large"
        value = json.loads(raw)
        return (value, None) if isinstance(value, dict) else (None, "unreadable_response")
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except subprocess.CalledProcessError as exc:
        error = exc.stderr or ""
        if "PERMISSION_DENIED" in error:
            return None, "permission_denied"
        if "NOT_FOUND" in error:
            return None, "not_found"
        if "UNAVAILABLE" in error or "DEADLINE_EXCEEDED" in error:
            return None, "unavailable"
        return None, f"error (gcloud exit {exc.returncode})"
    except OSError:
        return None, "error (gcloud not executable)"
    except (ValueError, RecursionError):
        return None, "unreadable_response"


def pin_state(entry: dict | None) -> tuple[bool, str]:
    """A pin is a literal string 1; only short numeric strings may be shown."""
    if entry is None:
        return False, "<missing>"
    if "valueFrom" in entry or "valueSource" in entry:
        return False, "<secret-ref>"
    value = entry.get("value")
    shown = repr(value) if isinstance(value, str) and re.fullmatch(r"[0-9]{1,6}", value) else "<invalid withheld>"
    return value == "1", shown


def project_job(name: str, job: dict) -> tuple[list[str], list[str], str | None, str | None]:
    """Return safe lines, readable invariant failures, validated image and a closed shape error."""
    try:
        task_spec = job["spec"]["template"]["spec"]
        containers = task_spec["template"]["spec"]["containers"]
        response_name = job["metadata"]["name"]
    except (KeyError, TypeError):
        return [], [], None, "unreadable_response"
    if response_name != name:
        return [], [], None, "response_name_mismatch"
    if not isinstance(containers, list) or len(containers) != 1 or not isinstance(containers[0], dict):
        return [], [], None, "application_container_unresolved"
    container = containers[0]
    entries = container.get("env", [])
    if not isinstance(entries, list) or len(entries) > MAX_ENV_ENTRIES:
        return [], [], None, "environment_shape_unresolved"
    env = {}
    secrets = 0
    for entry in entries:
        if not isinstance(entry, dict):
            return [], [], None, "environment_shape_unresolved"
        key = entry.get("name")
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", key) or key in env:
            return [], [], None, "environment_names_unresolved"
        env[key] = entry
        secrets += int("valueFrom" in entry or "valueSource" in entry)
    image = container.get("image")
    if not isinstance(image, str) or not IMAGE.fullmatch(image):
        return [], [], None, "image_identity_unresolved"

    lines = [f"  image: {image}"]
    failures = []
    task_count = task_spec.get("taskCount")
    valid_count = type(task_count) is int and 0 <= task_count <= 999
    shown_count = task_count if valid_count else "<invalid withheld>"
    lines.append(f"  taskCount: {shown_count}")
    if not valid_count or task_count != 1:
        failures.append(f"{name} taskCount must be 1.")
    for key, expected in (("DB_POOL_SIZE", expected_pools[name]), ("DB_MAX_OVERFLOW", "0")):
        entry = env.get(key)
        plain = entry is not None and "valueFrom" not in entry and "valueSource" not in entry
        value = entry.get("value") if plain else None
        shown = value if isinstance(value, str) and re.fullmatch(r"[0-9]{1,4}", value) else "<unresolved withheld>"
        lines.append(f"  {key}: {shown}")
        if value != expected:
            failures.append(f"{name} must set plain {key}={expected}; observed {shown}.")
    for key in ("SEC_RATE_LIMIT_PER_SECOND", "EDGAR_RATE_LIMIT_PER_SEC"):
        ok, shown = pin_state(env.get(key))
        lines.append(f"  {key}: {shown}")
        if not ok:
            failures.append(f"{name} must pin {key}=1 as a plain value, got {shown}.")
    observed_entrypoint = (container.get("command") or [], container.get("args") or [])
    if name in expected_entrypoints:
        matches = observed_entrypoint == expected_entrypoints[name]
        entrypoint = "matches the committed entrypoint" if matches else "DOES NOT MATCH the committed entrypoint (values withheld; compare ci.yml)"
        if not matches:
            failures.append(f"{name} command/args do not match the committed entrypoint.")
    else:
        entrypoint = "override present (values withheld)" if any(observed_entrypoint) else "image default"
    lines.append(f"  command/args: {entrypoint}")
    lines.append(f"  env: {len(entries) - secrets} plain, {secrets} secret-ref; names and other values withheld")
    lines.append("  Summary/SEC runtime configuration: " + json.dumps(runtime_configuration(entries), sort_keys=True))
    return lines, failures, image, None


def main() -> int:
    region = os.environ.get("REGION", "")
    if region != "us-west1":
        print("describe-jobs: INCOMPLETE (expected region configuration unavailable)")
        return 1
    images = set()
    failures = []
    unreadable = 0
    for name in expected_pools:
        print(f"== {name}", flush=True)
        job, error = gcloud_json(name, region)
        if error is None:
            lines, defects, image, error = project_job(name, job)
        if error is not None:
            unreadable += 1
            print(f"  read: UNVERIFIED ({error})")
            print(f"::warning::Job configuration {name}: UNVERIFIED ({error}); inventory remains incomplete.")
            continue
        images.add(image)
        print("\n".join(lines))
        for defect in defects:
            print(f"::error::Unresolved production configuration: {defect}")
        failures.extend(defects)
    if len(images) > 1:
        message = "readable jobs do not share one release image."
        failures.append(message)
        print("::error::Unresolved production configuration: " + message)
    print(f"Job inventory: expected={len(expected_pools)} projected={len(expected_pools) - unreadable} unverified={unreadable}")
    if failures or unreadable:
        print(f"describe-jobs: {'FAIL' if failures else 'INCOMPLETE'} ({len(failures)} invariant failure(s); {unreadable} unverified job(s))")
        return 1
    print("All expected jobs use one release image with the production pool budget, both SEC pins at 1 and taskCount=1.")
    print("describe-jobs: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
