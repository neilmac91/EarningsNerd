"""Rule-12 gate for the per-process SEC request budgets the deploy pins (CODE RED decision D3).

Every production process carries TWO independent SEC limiters: the app singleton
(``SEC_RATE_LIMIT_PER_SECOND``, ``app/services/sec_rate_limiter.py``) and edgartools' own
(``EDGAR_RATE_LIMIT_PER_SEC``, read once at import by ``edgar/httpclient.py``). The app bucket
starts full with capacity equal to rate; edgartools' is a pyrate-limiter sliding window that admits at
most its rate per rolling second. SEC's fair-access policy allows 10 requests per second per user
"regardless of the number of machines used", so configured budgets must be summed over every
process that can run at the same time: up to two service instances, the Cloud Run jobs and, once
its rollout is enabled, the private task worker (one instance running one isolated child at a time).

The pins are staged (CODE RED decision record 16). Every job and the task worker are pinned now. The
API service is pinned in a second stage, once the insider endpoint's cold fetch (one submissions document
and up to 60 Form 4 filings through edgartools) fits a 1 req/s budget; until then the service carries
no budget key and runs at the code and library defaults. This gate holds both halves: stage 2 must
change it on purpose, and the arithmetic below is asserted for the fully pinned fleet.

This gate asserts the configured values and the arithmetic ``docs/OPERATIONS.md`` states. It does
NOT prove a fleet guarantee: rollout-overlap instances, manual job executions and operator
one-shots, handovers between task children inside one second, and any request outside both
limiters are not bounded by configuration.
"""
import inspect
import re
from pathlib import Path

import pytest
import yaml

from app.config import Settings
from app.services.sec_rate_limiter import SECRateLimiter

ROOT = Path(__file__).resolve().parents[3]
SEC_PUBLISHED_CAP_PER_SECOND = 10
BUDGET_ENV = ("SEC_RATE_LIMIT_PER_SECOND", "EDGAR_RATE_LIMIT_PER_SEC")
PINNED_PER_BUCKET = 1
EXPECTED_JOBS = {
    "earningsnerd-pregenerate", "earningsnerd-filing-scan", "earningsnerd-filing-digest",
    "earningsnerd-backfill-facts", "earningsnerd-earnings-calendar-refresh",
    "earningsnerd-earnings-day-alerts", "earningsnerd-notable-filings", "earningsnerd-retention-purge",
}
# Scheduled overlaps of SEC-calling jobs with the service (cron schedules in docs/DEPLOYMENT.md;
# filing-scan is hourly, pregenerate Monday 06:00 UTC, backfill-facts Monday 07:00 UTC, the EFTS
# jobs notable-filings and earnings-calendar-refresh daily). Job timeouts reach 3600 s, so a
# Monday pregenerate can still be running when backfill-facts and the 07:00 scan start.
SCHEDULED_OVERLAPS = {
    "no job running": (),
    "hourly filing-scan window": ("filing-scan",),
    "Monday 06:00 UTC": ("pregenerate", "filing-scan"),
    "Monday 07:00 UTC": ("pregenerate", "filing-scan", "backfill-facts"),
    "daily EFTS job over a running scan": ("filing-scan", "notable-filings"),
}
OPERATIONS = ROOT / "docs/OPERATIONS.md"
WORKER = "earningsnerd-task-worker"
WORKER_STEP = "Update configured private task worker"  # exits early unless GCP_DURABLE_TASKS_ENABLED
SERVICE_STEP = "Deploy Cloud Run service"
SERVICE = "earningsnerd-backend"
LOOP_STEP = "Update filing-scan + digest + calendar + alert + notable + retention job images"
# Every Cloud Run process update a deploy step can make; the target follows the subcommand.
UPDATE = re.compile(r"gcloud (?:(?:alpha|beta) )?run (?:deploy|(?:services|jobs) (?:create|deploy|replace|update))(?:\s|\\)+(\"?[$\w-]+\"?)")
STAGED_UNPINNED = {"service"}  # pinned in stage 2, once the insider endpoint fits the budget
DEFAULTS = {"SEC_RATE_LIMIT_PER_SECOND": 10, "EDGAR_RATE_LIMIT_PER_SEC": 9}  # code and library defaults


def _deploy_job():
    workflow = yaml.load((ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)
    return workflow["jobs"]["deploy-backend"]


def _run(step_name):
    step = next(step for step in _deploy_job()["steps"] if step.get("name") == step_name)
    return "\n".join(line for line in step["run"].splitlines() if not line.lstrip().startswith("#"))


def _env_map(run):
    values = re.findall(r"--update-env-vars=(\S+)", run)
    assert len(values) == 1, "each deploy step must carry exactly one explicit env map"
    entries = dict(item.split("=", 1) for item in values[0].split(","))
    return entries


def _process_env_maps():
    """Name → env map for every production process the deploy configures."""
    service = _run(SERVICE_STEP)
    loop = _run(LOOP_STEP)
    loop_jobs = _loop_jobs(loop)
    maps = {"service": _env_map(service),
            "earningsnerd-pregenerate": _env_map(_run("Update pregenerate job image")),
            "earningsnerd-backfill-facts": _env_map(_run("Update backfill-facts job image and scheduled entrypoint")),
            WORKER: _env_map(_run(WORKER_STEP))}
    maps.update({job: _env_map(loop) for job in loop_jobs})
    return service, maps


def _loop_jobs(loop_run):
    return re.search(r"for job in ((?:earningsnerd-[a-z-]+\s*)+); do", loop_run).group(1).split()


def _service_instances(service_run):
    joined = service_run.replace("\\\n", " ")
    return int(re.search(r"--max-instances=(\d+)", joined).group(1))


def _budget(env, key):
    return int(env.get(key, DEFAULTS[key]))


def test_every_production_process_pins_both_sec_buckets_to_one():
    service, maps = _process_env_maps()
    assert set(maps) - {"service", WORKER} == EXPECTED_JOBS
    for name, env in maps.items():
        for key in BUDGET_ENV:
            if name in STAGED_UNPINNED:
                assert key not in env, f"{name} is pinned in stage 2: update STAGED_UNPINNED with it"
            else:
                assert env.get(key) == str(PINNED_PER_BUCKET), f"{name} must pin {key}={PINNED_PER_BUCKET}"
    assert _service_instances(service) == 2
    assert _service_instances(_run(WORKER_STEP)) == 1


def test_no_deploy_step_updates_a_process_without_both_pins():
    """A future process step must not escape the inventory above: every update targets an inventoried
    process exactly once, every update carries both pins, and only the staged service goes without them."""
    loop_jobs = _loop_jobs(_run(LOOP_STEP))
    targets = []
    for step in _deploy_job()["steps"]:
        assert "deploy-cloudrun" not in step.get("uses", ""), "Cloud Run updates go through gcloud, where this gate sees them"
        if "run" not in step:
            continue
        run = "\n".join(line for line in step["run"].splitlines() if not line.lstrip().startswith("#"))
        updates = UPDATE.findall(run)
        maps = re.findall(r"--update-env-vars=(\S+)", run)
        assert len(maps) == len(updates), f"{step.get('name')}: every process update carries one env map"
        for target, value in zip(updates, maps):
            env = dict(item.split("=", 1) for item in value.split(","))
            names = loop_jobs if target.strip('"') == "$job" else [target.strip('"')]
            for name in names:
                targets.append(name)
                if name == SERVICE:  # staged: pinned in stage 2, together with STAGED_UNPINNED
                    assert not any(key in env for key in BUDGET_ENV), "the service is pinned in stage 2"
                    continue
                assert all(env.get(key) == str(PINNED_PER_BUCKET) for key in BUDGET_ENV), name
    assert sorted(targets) == sorted(EXPECTED_JOBS | {SERVICE, WORKER})  # each process updated exactly once


def test_configured_sums_fit_the_published_cap_in_every_scheduled_overlap():
    service, maps = _process_env_maps()
    per_process = {name: sum(_budget(env, key) for key in BUDGET_ENV) for name, env in maps.items()}
    # Stage 1: the service still runs at the defaults, so no window is bounded by configuration.
    assert per_process["service"] == 19 and _service_instances(service) * per_process["service"] == 38
    # The fully pinned fleet (after stage 2), which the arithmetic below states.
    maps = {name: (dict(env, **{key: str(PINNED_PER_BUCKET) for key in BUDGET_ENV}) if name in STAGED_UNPINNED else env)
            for name, env in maps.items()}
    per_process = {name: sum(int(env[key]) for key in BUDGET_ENV) for name, env in maps.items()}
    steady = _service_instances(service) * per_process["service"]
    assert steady == 4
    for label, jobs in SCHEDULED_OVERLAPS.items():
        total = steady + sum(per_process[f"earningsnerd-{job}"] for job in jobs)
        assert total <= SEC_PUBLISHED_CAP_PER_SECOND, f"{label}: {total} req/s configured"
    monday = steady + sum(per_process[f"earningsnerd-{job}"] for job in SCHEDULED_OVERLAPS["Monday 07:00 UTC"])
    assert monday == SEC_PUBLISHED_CAP_PER_SECOND  # exactly at the cap: no headroom
    all_active = steady + sum(value for name, value in per_process.items() if name not in ("service", WORKER))
    assert all_active == 20 and all_active > SEC_PUBLISHED_CAP_PER_SECOND  # documented, not bounded
    # The optional task worker adds one process to every window once its rollout is enabled.
    worker = _service_instances(_run(WORKER_STEP)) * per_process[WORKER]
    assert worker == 2 and steady + worker == 6
    assert monday + worker == 12 and monday + worker > SEC_PUBLISHED_CAP_PER_SECOND  # documented, not bounded
    # Any one second: a full app bucket at rate R admits up to 2R-1 (capacity equals rate); edgartools' sliding
    # window never exceeds its rate. At the pinned R=1 that is one app request per second, so the ceiling in any
    # second, the first included, equals the sustained sum.
    def ceiling(env):
        return (2 * int(env["SEC_RATE_LIMIT_PER_SECOND"]) - 1) + int(env["EDGAR_RATE_LIMIT_PER_SEC"])

    assert {name: ceiling(env) for name, env in maps.items()} == per_process
    assert 2 * DEFAULTS["SEC_RATE_LIMIT_PER_SECOND"] - 1 == 19  # the defaults' first-second app burst, as documented
    monday_ceiling = (_service_instances(service) * ceiling(maps["service"])
                      + sum(ceiling(maps[f"earningsnerd-{job}"]) for job in SCHEDULED_OVERLAPS["Monday 07:00 UTC"]))
    assert monday_ceiling == SEC_PUBLISHED_CAP_PER_SECOND
    assert 2 * ceiling(maps[WORKER]) == 4  # a handover between two fresh task children inside one second
    doc = " ".join(OPERATIONS.read_text().split())  # Markdown wraps lines; compare on normalized whitespace
    for statement in (
        "two service instances run at the defaults, 38 req/s configured",
        "4 req/s sustained with no job running",
        "10 req/s in the Monday 07:00 UTC overlap",
        "20 req/s if every job ran at once",
        "up to 2R−1 requests in its first second (19 at the default 10)",
        "ceiling is 2 req/s in every second, the first included",
        "Monday 07:00 UTC overlap's ceiling in any second is 10 req/s",
        "6 req/s sustained with no job running and 12 req/s in the Monday 07:00 UTC overlap",
        "briefly admit up to 4 req/s from the worker",
    ):
        assert statement in doc, f"docs/OPERATIONS.md must state: {statement}"


def test_dev_default_and_limiter_accept_the_pinned_budget():
    assert Settings.model_fields["SEC_RATE_LIMIT_PER_SECOND"].default == 10  # local/dev unchanged
    assert Settings(SEC_RATE_LIMIT_PER_SECOND="1", _env_file=None).SEC_RATE_LIMIT_PER_SECOND == 1
    limiter = SECRateLimiter(requests_per_second=1)
    assert limiter.requests_per_second == 1 and limiter._tokens == 1.0  # bucket capacity equals rate


def test_pinned_edgartools_reads_the_second_bucket_from_the_env_name_we_pin():
    httpclient = pytest.importorskip("edgar.httpclient")  # installed in CI from requirements.txt
    source = inspect.getsource(httpclient.get_edgar_rate_limit_per_sec)
    assert '"EDGAR_RATE_LIMIT_PER_SEC"' in source
    assert f'"{DEFAULTS["EDGAR_RATE_LIMIT_PER_SEC"]}"' in source  # the library default the staged sums use
