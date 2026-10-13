"""Structural gate: ``ENABLE_SECTION_CHANGES`` is set on every process that reads it, or on none.

Four processes read the flag, deployed from three env maps in ``.github/workflows/ci.yml``: the
``earningsnerd-backend`` service serves the Change Report's ``section_changes`` block, the wording
review and the dashboard counts; the ``earningsnerd-filing-scan`` job extracts and stores the Item 1A
text the block is built from and writes the real-time alert's wording line; the
``earningsnerd-filing-digest`` job writes the digest's line (the jobs share one map); and the
``earningsnerd-task-worker`` service runs the scan and the digest when ``DURABLE_TASKS_ENABLED``
routes them there. Set on the service alone, every block stays ``pending`` for want of text and no
alert carries the line; set on the jobs alone, text is fetched from the SEC for a block nobody is
served. ``docs/CONFIGURATION.md`` says "set it on every process that reads it when it flips" and "add
``section-extraction`` to ``JOB_CADENCES`` so ``job_health`` watches the batch"; this test makes both
machine-checked (``lessons/ops-a-flag-several-processes-read-is-set-in-every-env-map.md``).

It reads the three deploy steps the way ``test_prod_flag_visibility.py`` does (the workflow's YAML,
the executable lines of each ``run``, the one ``--update-env-vars=`` map each) and fails when the
flag is on some maps and not the others, when the values differ, or when the jobs carry it on and
``JOB_CADENCES`` has no ``section-extraction`` cadence. A second test fails the flag spelled anywhere
else in the workflows (a space-separated ``--update-env-vars``, a ``--set-env-vars``, an env file, a
step of its own): a flip lands in these three maps or it is not a flip.
"""
import re
from pathlib import Path

import yaml

from app.services.job_run_service import JOB_CADENCES

ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = ROOT / ".github/workflows"
FLAG = "ENABLE_SECTION_CHANGES"
CADENCE = "section-extraction"
# Process (as a failure names it) -> the deploy step whose one env map configures it.
STEPS: dict[str, str] = {
    "the earningsnerd-backend service": "Deploy Cloud Run service",
    "the earningsnerd-task-worker service": "Update configured private task worker",
    "the filing-scan and filing-digest jobs": "Update filing-scan + digest + calendar + alert + notable + retention job images",
}
JOBS = "the filing-scan and filing-digest jobs"
EXPECTED_JOBS = ("earningsnerd-filing-scan", "earningsnerd-filing-digest")
# pydantic's truthy spellings for a bool Settings field.
_ON = frozenset({"1", "true", "t", "yes", "y", "on"})


def _deploy_job() -> dict:
    workflow = yaml.load((ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)
    return workflow["jobs"]["deploy-backend"]


def _executable(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def _step_run(job: dict, name: str) -> str:
    step = next(step for step in job["steps"] if step.get("name") == name)
    return _executable(step["run"])


def env_map(run: str) -> dict[str, str]:
    """The one ``--update-env-vars=`` map of a deploy step's executable lines."""
    values = re.findall(r"--update-env-vars=(\S+)", run)
    assert len(values) == 1, values
    entries = [item.split("=", 1) for item in values[0].split(",")]
    assert all(len(entry) == 2 for entry in entries), entries
    return dict(entries)


def is_on(value: str) -> bool:
    return value.strip().lower() in _ON


def placement_problems(maps: dict[str, dict[str, str]], cadences: dict) -> list[str]:
    """Why the flag's placement across the deploy maps and JOB_CADENCES is wrong."""
    problems: list[str] = []
    carrying = [name for name, env in maps.items() if FLAG in env]
    if carrying and len(carrying) < len(maps):
        missing = [name for name in maps if name not in carrying]
        problems.append(f"{FLAG} is set on {', '.join(carrying)} but not on {', '.join(missing)}; every reader needs it")
    if len({env[FLAG] for env in maps.values() if FLAG in env}) > 1:
        problems.append(f"{FLAG} differs: " + ", ".join(f"{name}={env[FLAG]!r}" for name, env in maps.items() if FLAG in env))
    if is_on(maps.get(JOBS, {}).get(FLAG, "")) and CADENCE not in cadences:
        problems.append(f"the filing-scan job runs the extraction batch but JOB_CADENCES has no {CADENCE!r} cadence")
    return problems


def flag_mentions(workflow_text: str) -> int:
    """How often the flag is spelled in a workflow's executable lines."""
    return _executable(workflow_text).count(FLAG)


def _maps() -> dict[str, dict[str, str]]:
    job = _deploy_job()
    runs = {name: _step_run(job, step) for name, step in STEPS.items()}
    for expected in EXPECTED_JOBS:
        assert expected in runs[JOBS], f"{expected} is no longer updated by this step; move the gate"
    return {name: env_map(run) for name, run in runs.items()}


def test_the_flag_is_set_on_every_reader_or_none_and_the_batch_is_watched_when_on():
    problems = placement_problems(_maps(), JOB_CADENCES)
    assert not problems, "\n".join(problems) + (
        "\nENABLE_SECTION_CHANGES is read by the earningsnerd-backend service, the filing-scan and filing-digest "
        "jobs and the task worker that runs them on the durable path (docs/CONFIGURATION.md): flip it in all three "
        "env maps together, and add the section-extraction cadence to JOB_CADENCES in the same change."
    )


def test_the_flag_is_spelled_nowhere_in_the_workflows_but_the_three_maps():
    in_maps = sum(FLAG in env for env in _maps().values())
    mentions = {path.name: n for path in sorted(WORKFLOWS.glob("*.yml")) if (n := flag_mentions(path.read_text()))}
    assert sum(mentions.values()) == in_maps, (
        f"{FLAG} is spelled {sum(mentions.values())} time(s) in the workflows ({mentions}) but sits in {in_maps} of the "
        "three deploy maps this gate reads. A flip lands in those maps (--update-env-vars=…) or it is not a flip: "
        "a space-separated --update-env-vars, a --set-env-vars, an env file or a step of its own escapes the "
        "placement check above."
    )


def test_placement_check_fails_the_bad_shapes_and_passes_the_good_ones():
    on, off = {FLAG: "true"}, {}
    assert placement_problems({"the service": on, "the worker": off, JOBS: off}, {}) == [
        f"{FLAG} is set on the service but not on the worker, {JOBS}; every reader needs it"
    ]
    assert placement_problems({"the service": off, "the worker": off, JOBS: on}, {CADENCE: object()}) == [
        f"{FLAG} is set on {JOBS} but not on the service, the worker; every reader needs it"
    ]
    assert placement_problems({"the service": on, "the worker": on, JOBS: {FLAG: "false"}}, {}) == [
        f"{FLAG} differs: the service='true', the worker='true', {JOBS}='false'"
    ]
    assert placement_problems({"the service": on, "the worker": on, JOBS: on}, {}) == [
        f"the filing-scan job runs the extraction batch but JOB_CADENCES has no {CADENCE!r} cadence"
    ]
    assert placement_problems({"the service": {FLAG: "1"}, "the worker": {FLAG: "1"}, JOBS: {FLAG: "1"}}, {}) == [
        f"the filing-scan job runs the extraction batch but JOB_CADENCES has no {CADENCE!r} cadence"
    ]
    assert placement_problems({"the service": on, "the worker": on, JOBS: on}, {CADENCE: object()}) == []
    assert placement_problems({"the service": {"OTHER": "x"}, "the worker": {}, JOBS: {"OTHER": "y"}}, {}) == []


def test_env_map_reads_one_map_and_rejects_two():
    assert env_map("gcloud run deploy x --update-env-vars=A=1,B=2 \\\n --quiet") == {"A": "1", "B": "2"}
    try:
        env_map("--update-env-vars=A=1 --update-env-vars=B=2")
    except AssertionError:
        pass
    else:
        raise AssertionError("two maps in one step must fail: the gate would read the wrong one")


def test_flag_mentions_counts_executable_lines_only():
    text = (
        "      # ENABLE_SECTION_CHANGES stays off until the cohort is recruited\n"
        "      run: |\n"
        "        gcloud run services update x --update-env-vars ENABLE_SECTION_CHANGES=true\n"
        "        gcloud run deploy y --set-env-vars=ENABLE_SECTION_CHANGES=true\n"
    )
    assert flag_mentions(text) == 2
