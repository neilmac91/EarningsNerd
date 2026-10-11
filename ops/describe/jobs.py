"""Ops describe-jobs: print image, taskCount, pool values and both SEC pins for every expected Cloud Run job
and fail on drift from the release invariants.

Run by ops.yml's describe-jobs step as `python3 ops/describe/jobs.py`, after the step's shell loop has
written each job's describe JSON to $JOB_DIR/<job>.json with gcloud's stderr discarded; stdlib only. Command
and argument values are withheld (lessons/ops-capacity-projection-withholds-command-values.md). Gates:
backend/tests/unit/test_ops_describe_jobs.py and test_ops_stderr_withheld.py.
"""
import json
import os
import re
from pathlib import Path

expected_pools = {
    "earningsnerd-pregenerate": "3",
    "earningsnerd-filing-scan": "1",
    "earningsnerd-filing-digest": "1",
    "earningsnerd-backfill-facts": "1",
    "earningsnerd-earnings-calendar-refresh": "1",
    "earningsnerd-earnings-day-alerts": "1",
    "earningsnerd-notable-filings": "1",
    "earningsnerd-retention-purge": "1",
}
# ci.yml restores this scheduled entrypoint on every deploy; only match/mismatch is printed.
expected_entrypoints = {
    "earningsnerd-backfill-facts": (["python"], ["scripts/backfill_facts.py", "--only-new"]),
}
images = set()
failures = []
def fail(message):
    # Value drift is announced now and raised once after every block has printed.
    failures.append(message)
    print(f"::error::Unresolved production configuration: {message}")
def pin_state(entry):
    # A pin counts only as the plain string "1"; an echoed value is bounded to a short digit string.
    if entry is None:
        return False, "<missing>"
    if "valueFrom" in entry or "valueSource" in entry:
        return False, "<secret-ref>"
    value = entry.get("value")
    shown = repr(value) if isinstance(value, str) and re.fullmatch(r"[0-9]{1,6}", value) else "<value withheld: not a plain numeric string>"
    return value == "1", shown
for name, expected_pool in expected_pools.items():
    path = Path(os.environ["JOB_DIR"]) / f"{name}.json"
    try:
        job = json.loads(path.read_text())
        task_spec = job["spec"]["template"]["spec"]
        containers = task_spec["template"]["spec"]["containers"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise SystemExit(f"Unresolved production configuration: cannot read {name}: {exc}") from exc
    if job.get("metadata", {}).get("name") not in (None, name):
        raise SystemExit(f"Unresolved production configuration: response name does not match {name}.")
    if len(containers) != 1:
        raise SystemExit(f"Unresolved production configuration: {name} needs one application container.")
    container = containers[0]
    env = {}
    env_kinds = []
    for entry in container.get("env", []):
        env_name = entry.get("name")
        if not env_name or env_name in env:
            raise SystemExit(f"Unresolved production configuration: {name} has a missing or duplicate env name.")
        env[env_name] = entry
        kind = "secret-ref" if ("valueFrom" in entry or "valueSource" in entry) else "plain"
        env_kinds.append(f"{env_name}({kind})")
    values = {}
    for env_name in ("DB_POOL_SIZE", "DB_MAX_OVERFLOW"):
        entry = env.get(env_name)
        if not entry or "valueFrom" in entry or "valueSource" in entry or "value" not in entry:
            raise SystemExit(f"Unresolved production configuration: {name} needs plain {env_name}.")
        values[env_name] = str(entry["value"])
    if values != {"DB_POOL_SIZE": expected_pool, "DB_MAX_OVERFLOW": "0"}:
        fail(f"{name} pool must be {expected_pool}+0, got {values['DB_POOL_SIZE']}+{values['DB_MAX_OVERFLOW']}.")
    # CODE RED D3: both SEC buckets are pinned to exactly 1 as plain values on every job.
    for pin in ("SEC_RATE_LIMIT_PER_SECOND", "EDGAR_RATE_LIMIT_PER_SEC"):
        ok, shown = pin_state(env.get(pin))
        values[pin] = shown
        if not ok:
            fail(f"{name} must pin {pin}=1 as a plain value, got {shown}.")
    task_count = task_spec.get("taskCount")
    if str(task_count) != "1":
        fail(f"{name} taskCount must be 1.")
    image = container.get("image")
    if not isinstance(image, str) or not image:
        raise SystemExit(f"Unresolved production configuration: {name} image is missing.")
    images.add(image)
    # Command/argument values are withheld (lessons/ops-capacity-projection-withholds-command-values.md).
    observed_entrypoint = (container.get("command") or [], container.get("args") or [])
    if name in expected_entrypoints:
        entrypoint = ("matches the committed entrypoint" if observed_entrypoint == expected_entrypoints[name]
                      else "DOES NOT MATCH the committed entrypoint (values withheld; compare ci.yml)")
    else:
        entrypoint = "override present (values withheld)" if any(observed_entrypoint) else "image default"
    print(f"== {name}")
    print("  image:", image)
    print("  taskCount:", task_count)
    print("  DB_POOL_SIZE:", values["DB_POOL_SIZE"])
    print("  DB_MAX_OVERFLOW:", values["DB_MAX_OVERFLOW"])
    print("  SEC_RATE_LIMIT_PER_SECOND:", values["SEC_RATE_LIMIT_PER_SECOND"])
    print("  EDGAR_RATE_LIMIT_PER_SEC:", values["EDGAR_RATE_LIMIT_PER_SEC"])
    print("  command/args:", entrypoint)
    print("  env:", ", ".join(env_kinds) if env_kinds else "(none)")
if len(images) != 1:
    fail("expected jobs do not share one release image.")
if failures:
    print(f"describe-jobs: FAIL ({len(failures)} invariant failure(s))")
    raise SystemExit("Unresolved production configuration: " + "; ".join(failures))
print("All expected jobs use one release image with the production pool budget, both SEC pins at 1 and taskCount=1.")
print("describe-jobs: PASS")
