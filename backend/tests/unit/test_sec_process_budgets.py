"""Rule-12 gate for the per-process SEC request budgets the deploy pins (CODE RED decision D3).

Every production process carries TWO independent SEC limiters: the app singleton
(``SEC_RATE_LIMIT_PER_SECOND``, ``app/services/sec_rate_limiter.py``) and edgartools' own
(``EDGAR_RATE_LIMIT_PER_SEC``, read once at import by ``edgar/httpclient.py``). The app bucket
starts full with capacity equal to rate; edgartools' is a pyrate-limiter sliding window that admits at
most its rate per rolling second. SEC's fair-access policy allows 10 requests per second per user
"regardless of the number of machines used", so configured budgets must be summed over every
process that can run at the same time: up to two service instances, the Cloud Run jobs and, when
its rollout is enabled (it is in production), the private task worker (one instance running one
isolated child at a time).

Every process is pinned (CODE RED decision records 16 and 17 staged it: the jobs and the worker
first, the API service once the two request paths that could not fit 1 req/s were removed — the
insider endpoint is off unless ENABLE_INSIDER_ACTIVITY, and company search no longer falls back to
edgartools). The Monday arithmetic assumes the Cloud Scheduler crons docs/DEPLOYMENT.md documents,
which this gate pins.

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
# Scheduled overlaps of SEC-calling jobs with the service (the crons below; filing-scan hourly with a
# 1,800 s timeout, pregenerate Monday 06:00 UTC and backfill-facts Monday 07:30 UTC with 3,600 s, the
# EFTS jobs notable-filings and earnings-calendar-refresh daily). A Monday pregenerate can still be
# running at the 07:00 scan but has ended by 07:30; backfill-facts can meet a scan still running or
# the 08:00 one, never pregenerate.
SCHEDULED_OVERLAPS = {
    "no job running": (),
    "hourly filing-scan window": ("filing-scan",),
    "Monday 06:00 UTC": ("pregenerate", "filing-scan"),
    "Monday 07:00 UTC": ("pregenerate", "filing-scan"),
    "Monday 07:30-08:30 UTC": ("filing-scan", "backfill-facts"),
    "daily EFTS job over a running scan": ("filing-scan", "notable-filings"),
}
# The crons the overlap model assumes, as docs/DEPLOYMENT.md and the runbook create them. Cloud
# Scheduler jobs are created by hand, so this pins the documented schedule, not the live one.
SCHEDULES = {
    ROOT / "docs/DEPLOYMENT.md": {"filing-scan-hourly": "0 * * * *", "backfill-facts-weekly": "30 7 * * 1"},
    ROOT / "tasks/gcp-deploy-runbook.md": {"earningsnerd-pregenerate-weekly": "0 6 * * 1"},
}
OPERATIONS = ROOT / "docs/OPERATIONS.md"
WORKER = "earningsnerd-task-worker"
WORKER_STEP = "Update configured private task worker"  # exits early unless GCP_DURABLE_TASKS_ENABLED
SERVICE_STEP = "Deploy Cloud Run service"
SERVICE = "earningsnerd-backend"
LOOP_STEP = "Update filing-scan + digest + calendar + alert + notable + retention job images"
# Every Cloud Run process update a deploy step can make; the target follows the subcommand. Global
# flags may precede `run` (`gcloud --quiet run ...`), and worker pools count as processes too.
UPDATE = re.compile(
    r"gcloud (?:--[\w-]+(?:=\S+)? )*(?:(?:alpha|beta) )?run "
    r"(?:deploy|(?:services|jobs|worker-pools) (?:create|deploy|replace|update))(?:\s|\\)+(\"?[$\w-]+\"?)"
)
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
            assert env.get(key) == str(PINNED_PER_BUCKET), f"{name} must pin {key}={PINNED_PER_BUCKET}"
    assert _service_instances(service) == 2
    assert _service_instances(_run(WORKER_STEP)) == 1


def test_no_deploy_step_updates_a_process_without_both_pins():
    """A future process step must not escape the inventory above: every update targets an inventoried
    process exactly once and carries both pins. Updates hidden from this reading fail too: a Cloud Run
    deploy action, a local composite action, or a script a deploy step calls that updates Cloud Run."""
    loop_jobs = _loop_jobs(_run(LOOP_STEP))
    targets = []
    for step in _deploy_job()["steps"]:
        uses = step.get("uses", "")
        assert "deploy-cloudrun" not in uses, "Cloud Run updates go through gcloud, where this gate sees them"
        assert not uses.startswith("./"), f"{step.get('name')}: a local action would hide its gcloud calls from this gate"
        if "run" not in step:
            continue
        run = "\n".join(line for line in step["run"].splitlines() if not line.lstrip().startswith("#"))
        for script in re.findall(r"[\w./-]+\.(?:sh|py)\b", run):
            text = (ROOT / script).read_text() if (ROOT / script).is_file() else ""
            assert not UPDATE.search(text) and "gcloud run" not in text, f"{script} updates Cloud Run outside this gate"
        updates = UPDATE.findall(run)
        maps = re.findall(r"--update-env-vars=(\S+)", run)
        assert len(maps) == len(updates), f"{step.get('name')}: every process update carries one env map"
        for target, value in zip(updates, maps):
            env = dict(item.split("=", 1) for item in value.split(","))
            names = loop_jobs if target.strip('"') == "$job" else [target.strip('"')]
            for name in names:
                targets.append(name)
                assert all(env.get(key) == str(PINNED_PER_BUCKET) for key in BUDGET_ENV), name
    assert sorted(targets) == sorted(EXPECTED_JOBS | {SERVICE, WORKER})  # each process updated exactly once


def test_configured_sums_fit_the_published_cap_in_every_scheduled_overlap():
    service, maps = _process_env_maps()
    per_process = {name: sum(int(env[key]) for key in BUDGET_ENV) for name, env in maps.items()}
    steady = _service_instances(service) * per_process["service"]
    assert steady == 4
    windows = {label: steady + sum(per_process[f"earningsnerd-{job}"] for job in jobs)
               for label, jobs in SCHEDULED_OVERLAPS.items()}
    assert windows["hourly filing-scan window"] == 6
    assert max(windows.values()) == 8 and all(total <= SEC_PUBLISHED_CAP_PER_SECOND for total in windows.values())
    all_active = steady + sum(value for name, value in per_process.items() if name not in ("service", WORKER))
    assert all_active == 20 and all_active > SEC_PUBLISHED_CAP_PER_SECOND  # documented, not bounded
    # The task worker (enabled in production) adds one process to every window.
    worker = _service_instances(_run(WORKER_STEP)) * per_process[WORKER]
    assert worker == 2 and steady + worker == 6
    assert max(windows.values()) + worker == SEC_PUBLISHED_CAP_PER_SECOND  # at the cap: no headroom
    # Any one second: a full app bucket at rate R admits up to 2R-1 (capacity equals rate); edgartools' sliding
    # window never exceeds its rate. At the pinned R=1 that is one app request per second, so the ceiling in any
    # second, the first included, equals the sustained sum.
    def ceiling(env):
        return (2 * int(env["SEC_RATE_LIMIT_PER_SECOND"]) - 1) + int(env["EDGAR_RATE_LIMIT_PER_SEC"])

    assert {name: ceiling(env) for name, env in maps.items()} == per_process
    assert 2 * DEFAULTS["SEC_RATE_LIMIT_PER_SECOND"] - 1 == 19  # the defaults' first-second app burst, as documented
    handover = 2 * ceiling(maps[WORKER])  # two fresh task children inside one second
    assert handover == 4 and max(windows.values()) + handover == 12
    doc = " ".join(OPERATIONS.read_text().split())  # Markdown wraps lines; compare on normalized whitespace
    for statement in (
        "4 req/s sustained with no job running",
        "6 in the hourly filing-scan window, and at most 8 req/s in any scheduled overlap",
        "20 req/s if every job ran at once",
        "up to 2R−1 requests in its first second (19 at the default 10)",
        "ceiling is 2 req/s in every second, the first included",
        "6 req/s sustained with no job running and at most 10 req/s in any scheduled overlap, at the cap",
        "briefly admit up to 4 req/s from the worker, 12 req/s in such a second",
        "backfill-facts at `30 7 * * 1`",
    ):
        assert statement in doc, f"docs/OPERATIONS.md must state: {statement}"


def test_the_overlap_model_matches_the_documented_crons():
    for path, crons in SCHEDULES.items():
        text = path.read_text()
        for job, cron in crons.items():
            create = rf'scheduler jobs create http {re.escape(job)}(?:\s|\\)+(?:--[\w-]+=\S+(?:\s|\\)+)*?--schedule="([^"]+)"'
            found = re.findall(create, text)
            assert found == [cron], f"{path.name}: {job} must be scheduled at {cron!r} (found {found})"


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
