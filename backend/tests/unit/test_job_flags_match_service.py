"""Structural gate: a scheduled job reads a production flag at the service's value.

``Settings`` defaults are the local values. Production's live in the ``--update-env-vars`` maps of
``.github/workflows/ci.yml``, one per process, and a Cloud Run job reads a flag from its own map, never the
service's. The hourly ``earningsnerd-filing-scan`` job ran without ``ENABLE_FPI_FILINGS`` while the service and
the task worker carried it: the company page listed a foreign issuer's 20-F, 6-K and 40-F, Filing alerts offered
rows for them, and the scan that sends those alerts never fetched the forms
(``lessons/ops-a-flag-several-processes-read-is-set-in-every-env-map.md``).

``JOB_FLAGS`` lists each flag a scheduled job's own pass reads, with the job and the module that holds the read.
For each row the job is one the jobs step updates, the module still reads the flag (so a row cannot outlive its
reader), and the jobs' one map carries the service's value. A flag whose job has to differ from the service is
listed in ``DIFFERENCES`` with why, and must then be absent from the jobs' map or differ there: the list is an
equality (``lessons/test-allowlist-caps-are-equalities.md``), so a pair that starts to agree has to leave it. Where
the service's value is expanded when the deploy runs (``${VAR}``), the gate cannot know it, so a listed flag must
be absent from the jobs' map: any value there might agree.

Not covered: a flag a job's pass starts to read (add its row here; review-checked); ``ENABLE_SECTION_CHANGES``,
which the scan and the digest also read and ``test_section_changes_flag_placement.py`` holds; the summary
rollout's held controls, which ``summary_preparation`` reads beside ``DURABLE_TASKS_ENABLED`` and an ordinary
deploy must not set (``test_summary_rollout_preservation.py``); a flag only the serve path reads, such as
``NOTABLE_FILINGS_ENABLED`` (``get_notable_filings``: the notable-filings job populates without it); a job
executed by hand with ``--args``; and a key set on a job by hand that this map does not list
(``--update-env-vars`` overwrites the keys it lists and keeps the rest).
"""
import ast
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
SERVICE_STEP = "Deploy Cloud Run service"
JOBS_STEP = "Update filing-scan + digest + calendar + alert + notable + retention job images"

# Flag -> (the scheduled job whose pass reads it, the module holding the read).
JOB_FLAGS: dict[str, tuple[str, str]] = {
    "ENABLE_FPI_FILINGS": ("earningsnerd-filing-scan", "app/services/filing_scan_service.py"),
    "CALENDAR_INDEX_FILTER_ENABLED": (
        "earningsnerd-earnings-calendar-refresh", "app/services/index_membership_service.py",
    ),
    "DURABLE_TASKS_ENABLED": ("earningsnerd-filing-scan", "app/services/summary_preparation.py"),
}
# Flag -> why its job does not carry the service's value.
DIFFERENCES: dict[str, str] = {
    "CALENDAR_INDEX_FILTER_ENABLED": (
        "with the filter on, the refresh stores no event for a watched company outside the index "
        "(earnings_calendar_service._ingest_key admits index members only), so the dashboard's upcoming earnings "
        "and the earnings-day alert would lose it; the job takes the service's value once the pass admits watched "
        "companies"
    ),
    "DURABLE_TASKS_ENABLED": (
        "the scan job reads it to decide whether to prepare summaries for the filings it alerts on and to recover "
        "their handoffs (summary_preparation); the jobs' map leaves it unset, so the job prepares none. Turning "
        "that on is the summary rollout's activation, which sets this beside the held controls an ordinary deploy "
        "must not pin (test_summary_rollout_preservation.py)"
    ),
}


def _step_run(name: str) -> str:
    workflow = yaml.load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    step = next(step for step in workflow["jobs"]["deploy-backend"]["steps"] if step.get("name") == name)
    return "\n".join(line for line in step["run"].splitlines() if not line.lstrip().startswith("#"))


def env_map(run: str) -> dict[str, str]:
    """The one ``--update-env-vars=`` map of a deploy step's executable lines."""
    values = re.findall(r"--update-env-vars=(\S+)", run)
    assert len(values) == 1, values
    entries = [item.split("=", 1) for item in values[0].split(",")]
    assert all(len(entry) == 2 for entry in entries), entries
    return dict(entries)


def reads_setting(source: str, flag: str) -> bool:
    """Whether a module's code reads ``settings.<flag>`` (or ``<module>.settings.<flag>``); a mention in a comment
    or a docstring is not a read."""
    def is_settings(node: ast.expr) -> bool:
        return (isinstance(node, ast.Name) and node.id == "settings") or (
            isinstance(node, ast.Attribute) and node.attr == "settings"
        )

    return any(
        isinstance(node, ast.Attribute) and node.attr == flag and is_settings(node.value)
        for node in ast.walk(ast.parse(source))
    )


def problems(
    service: dict[str, str], jobs: dict[str, str], flags: dict[str, tuple[str, str]], differences: dict[str, str],
) -> list[str]:
    """Why the jobs' map does not carry each flag of ``flags`` as its row and ``differences`` say it should."""
    found = []
    for flag, (job, _module) in flags.items():
        if flag not in service:
            found.append(f"{flag} is no longer set on the service; drop its row or restore the pin")
        elif flag in differences:
            if jobs.get(flag) == service[flag]:
                found.append(f"{flag} now agrees with the service ({service[flag]}); remove it from DIFFERENCES")
            elif flag in jobs and service[flag].startswith("$"):
                found.append(f"{flag} is {jobs[flag]} on the jobs, and the service's {service[flag]} is expanded when "
                             "the deploy runs, so the two may agree; a listed difference stays off the jobs' map")
        elif flag not in jobs:
            found.append(f"{flag} is {service[flag]} on the service and absent from the jobs' map, so {job} reads "
                         "the Settings default")
        elif jobs[flag] != service[flag]:
            found.append(f"{flag} is {service[flag]} on the service and {jobs[flag]} on the jobs")
    return found + [f"{flag} is in DIFFERENCES but not in JOB_FLAGS" for flag in differences if flag not in flags]


def test_each_job_flag_carries_the_services_value_or_is_a_listed_difference():
    found = problems(env_map(_step_run(SERVICE_STEP)), env_map(_step_run(JOBS_STEP)), JOB_FLAGS, DIFFERENCES)
    assert not found, (
        "A scheduled job reads a flag from the jobs' own --update-env-vars map in ci.yml. Set it there at the "
        "service's value, or list the flag in DIFFERENCES with why its job differs:\n" + "\n".join(found)
    )


def test_each_row_names_a_job_the_step_updates_and_a_module_that_still_reads_the_flag():
    loop = re.search(r"for job in ((?:earningsnerd-[a-z-]+\s*)+); do", _step_run(JOBS_STEP))
    assert loop, "the jobs step no longer loops over its jobs; move the gate"
    updated = loop.group(1).split()
    for flag, (job, module) in JOB_FLAGS.items():
        assert job in updated, f"{job} is no longer updated by the jobs step, so its map is elsewhere"
        assert reads_setting((BACKEND / module).read_text(encoding="utf-8"), flag), (
            f"{module} no longer reads {flag}; drop or move its row"
        )


def test_the_comparison_finds_each_wrong_placement():
    flag, other = "PINNED_FLAG", "DIFFERING_FLAG"
    flags = {flag: ("a-job", "a/module.py"), other: ("another-job", "another/module.py")}
    service = {flag: "true", other: "true"}
    declared = {other: "why"}
    assert problems(service, {flag: "true"}, flags, declared) == []
    assert "absent from the jobs' map, so a-job reads" in problems(service, {}, flags, declared)[0]
    assert "true on the service and false on the jobs" in problems(service, {flag: "false"}, flags, declared)[0]
    assert "remove it from DIFFERENCES" in problems(service, {flag: "true", other: "true"}, flags, declared)[0]
    assert problems(service, {flag: "true", other: "false"}, flags, declared) == []
    assert "no longer set on the service" in problems({other: "true"}, {flag: "true"}, flags, declared)[0]
    assert "not in JOB_FLAGS" in problems(service, {flag: "true"}, flags, {**declared, "SOME_FLAG": "why"})[0]
    expanded = {flag: "true", other: "${DIFFERING_FLAG}"}
    assert problems(expanded, {flag: "true"}, flags, declared) == []
    assert "the two may agree" in problems(expanded, {flag: "true", other: "true"}, flags, declared)[0]


def test_a_mention_in_a_comment_or_a_docstring_is_not_a_read():
    assert reads_setting("if settings.SOME_FLAG:\n    pass\n", "SOME_FLAG")
    assert reads_setting("value = pipeline.settings.SOME_FLAG\n", "SOME_FLAG")
    assert reads_setting("value = settings.OTHER_FLAG\n", "SOME_FLAG") is False
    assert reads_setting('"""Gated on settings.SOME_FLAG."""\n# settings.SOME_FLAG\nx = 1\n', "SOME_FLAG") is False
