"""Structural gate for ``lessons/ops-prove-the-permission-route-before-a-gated-session.md`` (rule 12).

The 22 September 2026 E8 judging session stopped at its first gated command: the auto-mode
permission classifier denied ``restore_e8_session.py`` although ``.claude/settings.json`` carried
an allow rule for it. Two defects in the launch kit made that undetectable before any state
existed: every gated command was written with shell variables (``"$REPIN"``, ``"$PYTHON_BIN"``)
that no ``Bash(prefix:*)`` rule can ever match, and nothing proved the permission route before
step 1. Receipt: ``tasks/review-evidence/e8-repin-restore-2026-09-22/receipt.md``.

This test reads the committed launch kit (``tasks/fable-e8-launch-kit.md``) and the project allow
rules and fails when:

- an allow rule contains a shell variable, or names a repository script that does not exist;
- a gated command in one of the kit's ``sh`` blocks (a command that invokes a tool the rules
  cover) does not start with an allow-rule prefix, or carries a variable, redirect, pipe, ``;``,
  ``&&``, ``||`` or a backtick, any of which takes it outside the rule;
- the kit's first gated command is not the zero-effect probe
  ``python3 tasks/fable-e8-repin-2026-09-22/restore_e8_session.py --help``.

``<placeholder>`` tokens such as ``<UTC stamp>`` are operator-substituted values, not shell syntax,
and are removed before the operator check.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SETTINGS = REPO_ROOT / ".claude" / "settings.json"
KIT = REPO_ROOT / "tasks" / "fable-e8-launch-kit.md"

# The repository root as the judging container mounts it; absolute rule paths under it map to REPO_ROOT.
CONTAINER_REPO = "/home/user/EarningsNerd"
PROBE = "python3 tasks/fable-e8-repin-2026-09-22/restore_e8_session.py --help"
# Any command mentioning one of these is gated: it must be issued as the literal prefix of an allow rule.
GATED_TOOLS = (
    "restore_e8_session.py",
    "export_e8_state.py",
    "build_repin.py",
    "guard_setup.py",
    "e8_resume.py",
    "readout.py",
    "-m unittest",
)
# Shell syntax that takes a command outside a Bash(prefix:*) rule or that a session cannot rely on.
FORBIDDEN_SHELL = ("$", ";", "&&", "||", "|", ">", "<", "`")

_RULE = re.compile(r"^Bash\((.+):\*\)$")
_PLACEHOLDER = re.compile(r"<[^<>]+>")


def _allow_prefixes() -> list[str]:
    rules = json.loads(SETTINGS.read_text())["permissions"]["allow"]
    prefixes = [m.group(1) for rule in rules if (m := _RULE.fullmatch(rule))]
    assert prefixes, f"{SETTINGS} has no Bash(prefix:*) allow rules"
    return prefixes


def _script_path(prefix: str) -> Path | None:
    """The repository script an allow-rule prefix names, or None when it names no repository path."""
    for token in prefix.split():
        if token.startswith(CONTAINER_REPO + "/"):
            return REPO_ROOT / token[len(CONTAINER_REPO) + 1 :]
        if token.startswith("tasks/"):
            return REPO_ROOT / token
    return None


def _sh_commands(markdown: str) -> list[str]:
    """Commands from the kit's ```sh blocks: continuations joined, blank and comment lines dropped."""
    commands: list[str] = []
    in_block = False
    pending = ""
    for raw in markdown.splitlines():
        stripped = raw.strip()
        if not in_block:
            in_block = stripped == "```sh"
            continue
        if stripped == "```":
            in_block = False
            continue
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.endswith("\\"):
            pending += stripped[:-1].rstrip() + " "
            continue
        commands.append((pending + stripped).strip())
        pending = ""
    return commands


def _gated_commands() -> list[str]:
    commands = [c for c in _sh_commands(KIT.read_text()) if any(tool in c for tool in GATED_TOOLS)]
    assert commands, f"{KIT} has no gated commands in its sh blocks"
    return commands


def test_allow_rules_are_literal_and_name_existing_scripts() -> None:
    for prefix in _allow_prefixes():
        assert "$" not in prefix, f"allow rule carries a shell variable, which can never match: {prefix}"
        path = _script_path(prefix)
        if path is not None:
            assert path.is_file(), f"allow rule names a script that does not exist: {prefix} -> {path}"


def test_every_gated_kit_command_is_a_literal_allow_rule_prefix() -> None:
    prefixes = _allow_prefixes()
    problems: list[str] = []
    for command in _gated_commands():
        if not any(command.startswith(prefix) for prefix in prefixes):
            problems.append(f"no allow rule covers: {command}")
        bare = _PLACEHOLDER.sub("", command)
        for token in FORBIDDEN_SHELL:
            if token in bare:
                problems.append(f"contains {token!r}, which takes it outside its rule: {command}")
    assert not problems, (
        "gated commands in tasks/fable-e8-launch-kit.md must be the literal prefix of an allow rule in "
        ".claude/settings.json (lessons/ops-prove-the-permission-route-before-a-gated-session.md):\n  "
        + "\n  ".join(problems)
    )


def test_kit_first_gated_command_is_the_zero_effect_probe() -> None:
    first = _gated_commands()[0]
    assert first == PROBE, (
        f"the kit's first gated command must prove the permission route with {PROBE!r} "
        f"before any state exists; found {first!r}"
    )
