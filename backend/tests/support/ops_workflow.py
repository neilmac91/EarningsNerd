"""Readers for `.github/workflows/ops.yml`, shared by the gates that read it as GitHub and Postgres do.

`selected` reads a step's or a job's `if:` as GitHub evaluates it: `contains()` on a string is a
substring test, and both it and `==` compare strings without regard to case; a job reads the
operation as `inputs.operation` and may open with the main-ref check. `pg_settings` and `setting_ms` read a
PGOPTIONS string as the Postgres backend parses it: split on unescaped spaces; `-c name=value`,
`-cname=value` or `--name=value`; a name's `-` reads as `_` and its case does not count; the last
setting wins; a bare number is milliseconds. A form either reader does not know fails the calling
gate rather than being skipped. `cloud_sql_reach` lists the steps that can reach Cloud SQL, from
their position and selection rather than their command text.
"""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
OPS_TEXT = (ROOT / ".github/workflows/ops.yml").read_text(encoding="utf-8")
OPS = yaml.load(OPS_TEXT, Loader=yaml.BaseLoader)  # strings only: `on` stays a key, versions stay text
STEPS = OPS["jobs"]["ops"]["steps"]
INPUTS = OPS["on"]["workflow_dispatch"]["inputs"]
OPTIONS = INPUTS["operation"]["options"]
BY_NAME = {step.get("name"): (index, step) for index, step in enumerate(STEPS)}
RESOLVE, PROXY, DEPS = ("Resolve requested operation", "Start Cloud SQL proxy and export connection env",
                        "Install backend dependencies")
RELABEL = "Run fiscal-year relabel script"
QUARTERLY = "Run quarterly fact repair script"
LINEAGE = "Run filing lineage backfill script"
OPERAND = r"(?:steps\.request\.outputs|inputs)\.operation"  # a step's resolved operation, or a job's input
NO_DATABASE = {DEPS}  # runs after the proxy for its operations, but opens no database session
UNIT_MS = {"ms": 1, "s": 1_000, "min": 60_000, "h": 3_600_000, "d": 86_400_000}


def selected(step) -> set[str]:
    """The operations whose dispatch runs this step or job, read as GitHub evaluates its `if:`."""
    condition = step.get("if")
    if condition is None:
        return set(OPTIONS)
    condition = re.sub(r"^\$\{\{\s*(.*?)\s*\}\}$", r"\1", condition.strip())
    condition = re.sub(r"^(?:always\(\)|github\.ref == 'refs/heads/main') && ", "", condition)
    operand = OPERAND if "steps" in step else r"steps\.request\.outputs\.operation"  # a step reads the resolved one
    if match := re.fullmatch(rf"(!?)contains\('([^']*)', {operand}\)", condition):
        hit = {op for op in OPTIONS if op in match.group(2).lower()}
        return set(OPTIONS) - hit if match.group(1) else hit
    if match := re.fullmatch(rf"{operand} == '([^']*)'", condition):
        return {match.group(1).lower()} & set(OPTIONS)
    raise AssertionError(f"{step.get('name')!r}: teach selected() this if: form rather than skip it: {condition!r}")


def pg_settings(options: str) -> list[tuple[str, str]]:
    """PGOPTIONS as the backend splits it (a backslash escapes a space) and reads it (getopt over
    `-c name=value`, `-cname=value` and `--name=value`), each name folded as Postgres folds it."""
    tokens, found, at = re.findall(r"(?:\\.|\S)+", options), [], 0
    while at < len(tokens):
        token = tokens[at]
        if token.startswith("--"):
            body = token[2:]
        elif token == "-c" and at + 1 < len(tokens):
            at += 1
            body = tokens[at]
        elif token.startswith("-c") and token != "-c":
            body = token[2:]
        else:
            raise AssertionError(f"teach pg_settings() this PGOPTIONS switch rather than skip it: {token!r} in {options!r}")
        name, sep, value = body.partition("=")
        assert sep, f"{token!r} sets no value in {options!r}"
        found.append((name.replace("-", "_").lower(), value))
        at += 1
    return found


def setting_ms(options: str, name: str) -> int | None:
    """The value Postgres applies from PGOPTIONS for a time setting, in milliseconds: the last setting
    of the name wins, and a bare number is milliseconds."""
    values = [value for key, value in pg_settings(options) if key == name]
    if not values:
        return None
    match = re.fullmatch(r"(\d+)(ms|s|min|h|d)?", values[-1])
    assert match, f"unreadable {name}={values[-1]!r}: teach setting_ms() this form rather than pass it"
    return int(match.group(1)) * UNIT_MS[match.group(2) or "ms"]


def shown(ms: int) -> str:
    """A time setting as Postgres shows it: in the largest unit that holds it exactly."""
    for unit in ("d", "h", "min", "s"):
        if ms and ms % UNIT_MS[unit] == 0:
            return f"{ms // UNIT_MS[unit]}{unit}"
    return f"{ms}ms" if ms else "0"


def cloud_sql_reach() -> list[tuple[int, dict]]:
    """Every `run:` step after the proxy step for an operation the proxy starts for, except the steps
    named in NO_DATABASE: each can reach Cloud SQL, whatever its command looks like."""
    proxy_at, proxy = BY_NAME[PROXY]
    return [(at, step) for at, step in enumerate(STEPS) if at > proxy_at and step.get("run")
            and selected(step) & selected(proxy) and step.get("name") not in NO_DATABASE]
