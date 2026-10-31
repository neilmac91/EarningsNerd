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
flag is on some maps and not the others, when the values differ, when a value is neither a bool spelling
``Settings`` reads nor a ``${VAR}`` the deploy expands, or when the jobs carry it on, or shell-sourced and so
possibly on, and ``JOB_CADENCES`` has no ``section-extraction`` cadence. A second test fails the flag spelled anywhere
else in the workflows (a space-separated ``--update-env-vars``, a ``--set-env-vars``, an env file, a
step of its own): a flip lands in these three maps or it is not a flip. A shell-sourced value
(``${VAR}``, the shape ``DURABLE_TASKS_ENABLED`` takes) is allowed its reads and the line that defines
the variable from a ``${{ … }}`` expression, nothing else.
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
# pydantic's spellings for a bool Settings field, and the shell forms a deploy step expands at run time
# (ci.yml sources DURABLE_TASKS_ENABLED and the model env this way), whose value the gate cannot know.
_ON = frozenset({"1", "true", "t", "yes", "y", "on"})
_OFF = frozenset({"0", "false", "f", "no", "n", "off"})
_DYNAMIC = re.compile(r"^\$(\{\{.*\}\}|\{[A-Za-z_]\w*\}|[A-Za-z_]\w*)$")
# A read of the flag's shell variable (`${FLAG}`, `$FLAG`), a GitHub expression (the flag's name inside `${{ … }}`,
# `vars.GCP_FLAG` included), and a line that defines the variable a read expands from such an expression
# (`FLAG: ${{ vars.GCP_FLAG || 'false' }}` in an env block, the shape ci.yml gives DURABLE_TASKS_ENABLED;
# `FLAG="${{ … }}"` in a run).
_SHELL_READ = re.compile(r"\$\{" + FLAG + r"\}|\$" + FLAG + r"\b")
_EXPRESSION = re.compile(r"\$\{\{[^}]*\}\}")
_SOURCE = re.compile(r"^\s*" + FLAG + r"\s*[:=]\s*[\"']?\$\{\{", re.MULTILINE)


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


def flag_state(value: str) -> str:
    """``on`` / ``off`` for a spelling Settings reads as that bool; ``dynamic`` for a ``$VAR``, ``${VAR}`` or
    ``${{ … }}`` the deploy expands (possibly to on, so the gate treats it as on where on is the demanding
    side); ``unreadable`` for anything else (Settings would refuse it at startup)."""
    literal = value.strip()
    if literal.lower() in _ON:
        return "on"
    if literal.lower() in _OFF:
        return "off"
    if _DYNAMIC.match(literal):
        return "dynamic"
    return "unreadable"


def placement_problems(maps: dict[str, dict[str, str]], cadences: dict) -> list[str]:
    """Why the flag's placement across the deploy maps and JOB_CADENCES is wrong."""
    problems: list[str] = []
    carrying = [name for name, env in maps.items() if FLAG in env]
    if carrying and len(carrying) < len(maps):
        missing = [name for name in maps if name not in carrying]
        problems.append(f"{FLAG} is set on {', '.join(carrying)} but not on {', '.join(missing)}; every reader needs it")
    if len({env[FLAG] for env in maps.values() if FLAG in env}) > 1:
        problems.append(f"{FLAG} differs: " + ", ".join(f"{name}={env[FLAG]!r}" for name, env in maps.items() if FLAG in env))
    for name, env in maps.items():
        if FLAG in env and flag_state(env[FLAG]) == "unreadable":
            problems.append(f"{FLAG}={env[FLAG]!r} on {name} is neither a bool spelling Settings reads nor a ${{VAR}} the deploy expands")
    jobs_value = maps.get(JOBS, {}).get(FLAG)
    if jobs_value is not None and CADENCE not in cadences:
        state = flag_state(jobs_value)
        if state == "on":
            problems.append(f"the filing-scan job runs the extraction batch but JOB_CADENCES has no {CADENCE!r} cadence")
        elif state == "dynamic":
            problems.append(
                f"{FLAG}={jobs_value!r} on {JOBS} is expanded at deploy time and may be on, but JOB_CADENCES has no "
                f"{CADENCE!r} cadence; the cadence lands before the flag can"
            )
    return problems


def flag_mentions(workflow_text: str) -> dict[str, int]:
    """How the flag is spelled in a workflow's executable lines: ``set`` (a key, or any spelling that is not one
    of the other two), ``read`` (``${FLAG}``, ``$FLAG``, the name inside a ``${{ … }}`` expression) and ``source``
    (a line defining the variable a read expands, from a ``${{ … }}`` expression)."""
    text = _executable(workflow_text)
    reads = len(_SHELL_READ.findall(text)) + sum(expression.count(FLAG) for expression in _EXPRESSION.findall(text))
    sources = len(_SOURCE.findall(text))
    return {"set": text.count(FLAG) - reads - sources, "read": reads, "source": sources}


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
    maps = _maps()
    in_maps = sum(FLAG in env for env in maps.values())
    dynamic = sum(flag_state(env[FLAG]) == "dynamic" for env in maps.values() if FLAG in env)
    mentions = {path.name: m for path in sorted(WORKFLOWS.glob("*.yml")) if any((m := flag_mentions(path.read_text())).values())}
    sets = sum(m["set"] for m in mentions.values())
    assert sets == in_maps, (
        f"{FLAG} is spelled {sets} time(s) in the workflows as a key or a bare name ({mentions}) but sits in {in_maps} of "
        "the three deploy maps this gate reads. A flip lands in those maps (--update-env-vars=…) or it is not a flip: "
        "a space-separated --update-env-vars, a --set-env-vars, an env file or a step of its own escapes the "
        "placement check above."
    )
    sources = sum(m["source"] for m in mentions.values())
    assert (sources > 0) == (dynamic > 0), (
        f"{sources} line(s) define {FLAG} from a GitHub expression while {dynamic} map(s) read it as a shell value "
        f"({mentions}): a shell-sourced flip has its source line(s) and its map reads; a literal flip has no source line."
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
    # A shell-sourced value the deploy expands (the shape ci.yml gives DURABLE_TASKS_ENABLED) may be on: the cadence is due.
    sourced = {FLAG: "${ENABLE_SECTION_CHANGES}"}
    assert placement_problems({"the service": sourced, "the worker": sourced, JOBS: sourced}, {}) == [
        f"{FLAG}='${{ENABLE_SECTION_CHANGES}}' on {JOBS} is expanded at deploy time and may be on, but JOB_CADENCES has no "
        f"{CADENCE!r} cadence; the cadence lands before the flag can"
    ]
    assert placement_problems({"the service": sourced, "the worker": sourced, JOBS: sourced}, {CADENCE: object()}) == []
    off_literal = {FLAG: "false"}
    assert placement_problems({"the service": off_literal, "the worker": off_literal, JOBS: off_literal}, {}) == []
    odd = {FLAG: "enabled"}
    assert placement_problems({"the service": odd, "the worker": odd, JOBS: odd}, {CADENCE: object()}) == [
        f"{FLAG}='enabled' on {name} is neither a bool spelling Settings reads nor a ${{VAR}} the deploy expands"
        for name in ("the service", "the worker", JOBS)
    ]


def test_flag_state_reads_the_bool_spellings_and_treats_a_shell_sourced_value_as_possibly_on():
    assert [flag_state(value) for value in ("true", "1", "YES", " on ")] == ["on"] * 4
    assert [flag_state(value) for value in ("false", "0", "No", "off")] == ["off"] * 4
    assert [flag_state(value) for value in ("${ENABLE_SECTION_CHANGES}", "$FLAG", "${{ vars.FLAG }}")] == ["dynamic"] * 3
    assert [flag_state(value) for value in ("enabled", "", "maybe")] == ["unreadable"] * 3


def test_env_map_reads_one_map_and_rejects_two():
    assert env_map("gcloud run deploy x --update-env-vars=A=1,B=2 \\\n --quiet") == {"A": "1", "B": "2"}
    try:
        env_map("--update-env-vars=A=1 --update-env-vars=B=2")
    except AssertionError:
        pass
    else:
        raise AssertionError("two maps in one step must fail: the gate would read the wrong one")


def test_flag_mentions_counts_executable_lines_and_tells_a_key_from_a_read_and_a_source():
    text = (
        "      # ENABLE_SECTION_CHANGES stays off until the cohort is recruited\n"
        "      run: |\n"
        "        gcloud run services update x --update-env-vars ENABLE_SECTION_CHANGES=true\n"
        "        gcloud run deploy y --set-env-vars=ENABLE_SECTION_CHANGES=true\n"
    )
    assert flag_mentions(text) == {"set": 2, "read": 0, "source": 0}
    sourced = (
        "    env:\n"
        "      ENABLE_SECTION_CHANGES: ${{ vars.GCP_ENABLE_SECTION_CHANGES || 'false' }}\n"
        "    run: |\n"
        '      FLIP="${{ vars.ENABLE_SECTION_CHANGES }}"\n'
        "      gcloud run deploy x --update-env-vars=A=1,ENABLE_SECTION_CHANGES=${ENABLE_SECTION_CHANGES} \\\n"
        "        --quiet && echo $ENABLE_SECTION_CHANGES\n"
    )
    assert flag_mentions(sourced) == {"set": 1, "read": 4, "source": 1}
