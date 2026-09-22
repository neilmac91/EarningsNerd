"""Structural gate for ``lessons/ops-prove-the-permission-route-before-a-gated-session.md`` (rule 12).

The 22 September 2026 E8 judging session stopped at its first gated command: the auto-mode
permission classifier denied ``restore_e8_session.py`` although ``.claude/settings.json`` carried
an allow rule for it. Two defects in the launch kit made that undetectable before any state
existed: every gated command was written with shell variables (``"$REPIN"``, ``"$PYTHON_BIN"``)
that no ``Bash(prefix:*)`` rule can ever match, and nothing proved the permission route before
step 1. Receipt: ``tasks/review-evidence/e8-repin-restore-2026-09-22/receipt.md``.

``kit_problems`` reads the committed launch kit (``tasks/fable-e8-launch-kit.md``) and the project
permission rules and reports every disagreement. The gate fails when:

- an allow entry contains a shell variable, or a ``Bash(prefix:*)`` rule names a repository script
  that does not exist;
- any command in one of the kit's ``sh`` blocks is not the literal prefix of an allow rule, is
  covered by a deny or ask rule, or carries a variable, a command separator (``&``, ``;``, ``|``),
  a redirection (``<``, ``>``) or a backtick, any of which takes it outside the rule
  (separators per code.claude.com/docs/en/permissions.md);
- a fenced block uses an info string other than ``sh``, ``text`` or ``json``, or an interpreter or
  the CLI is invoked anywhere outside an ``sh`` block, where the operator check would not see it;
- the kit's first command is not the zero-effect probe
  ``python3 tasks/fable-e8-repin-2026-09-22/restore_e8_session.py --help``.

Only the two named placeholders (``<session-uploads-dir>``, ``<UTC stamp>``) are removed before
the operator check; any other ``<…>`` span is shell syntax. The evasion cases at the bottom lock
each of these behaviours against in-memory copies of the kit and rules.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SETTINGS = REPO_ROOT / ".claude" / "settings.json"
KIT = REPO_ROOT / "tasks" / "fable-e8-launch-kit.md"

# The repository root as the judging container mounts it; absolute rule paths under it map to REPO_ROOT.
CONTAINER_REPO = "/home/user/EarningsNerd"
PROBE = "python3 tasks/fable-e8-repin-2026-09-22/restore_e8_session.py --help"
# Fence info strings the kit may use: sh blocks are commands, the others are data. Anything else fails.
ALLOWED_FENCES = {"sh", "text", "json"}
# Operator-substituted values. Any other text between < and > is shell syntax.
PLACEHOLDERS = re.compile(r"<(?:session-uploads-dir|UTC stamp)>")
# Variables, the command separators Claude Code recognises (& covers &&, |& and &>; | covers ||),
# redirections and backticks: each takes a command outside a Bash(prefix:*) rule.
FORBIDDEN_SHELL = ("$", "&", ";", "|", ">", "<", "`")
# An interpreter or the CLI followed by an argument, outside an sh block, is a command the gate would not see.
INVOCATION = re.compile(
    r"(?:^|[\s`\"'(])(?:python3?|/home/user/fable-judging/venv/bin/python|/opt/claude-code/bin/claude)\s+\S"
)

_RULE = re.compile(r"^Bash\((.+?)(:\*)?\)$")
_FENCE = re.compile(r"^(`{3,}|~{3,})\s*(\S*)$")


def _bash_prefixes(entries: list[str]) -> list[str]:
    """The prefix of every Bash(prefix:*) entry."""
    return [m.group(1) for entry in entries if (m := _RULE.fullmatch(entry)) and m.group(2)]


def _covers(prefix: str, command: str) -> bool:
    """Bash(prefix:*) matches the prefix alone or the prefix followed by a space (the docs' trailing-* form)."""
    return command == prefix or command.startswith(prefix + " ")


def _script_path(prefix: str) -> Path | None:
    """The repository script an allow-rule prefix names, or None when it names no repository path."""
    for token in prefix.split():
        if token.startswith(CONTAINER_REPO + "/"):
            return REPO_ROOT / token[len(CONTAINER_REPO) + 1 :]
        if token.startswith("tasks/"):
            return REPO_ROOT / token
    return None


def _segments(markdown: str) -> list[tuple[str, int, list[str]]]:
    """(info string, first line number, lines) for prose and every fenced block, in order.

    A fence opens on three or more backticks or tildes and closes on the same run; prose segments
    carry the info string ``prose``. An unterminated fence is an error.
    """
    segments: list[tuple[str, int, list[str]]] = [("prose", 1, [])]
    opener: str | None = None
    for number, raw in enumerate(markdown.splitlines(), start=1):
        stripped = raw.strip()
        if opener is None:
            if match := _FENCE.match(stripped):
                opener = match.group(1)
                segments.append((match.group(2), number, []))
                continue
        elif stripped == opener:
            opener = None
            segments.append(("prose", number + 1, []))
            continue
        segments[-1][2].append(raw)
    if opener is not None:
        raise AssertionError("the kit has an unterminated fenced block")
    return segments


def _sh_commands(lines: list[str]) -> list[str]:
    """Commands in an sh block: backslash continuations joined, blank and comment lines dropped."""
    commands: list[str] = []
    pending = ""
    for raw in lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.endswith("\\"):
            pending += stripped[:-1].rstrip() + " "
            continue
        commands.append((pending + stripped).strip())
        pending = ""
    if pending:
        commands.append(pending.strip())
    return commands


def rule_problems(settings: dict) -> list[str]:
    """Every way the permission rules themselves are unfit: variables, or scripts that do not exist."""
    permissions = settings.get("permissions", {})
    problems = [
        f"allow entry carries a shell variable, which can never match: {entry}"
        for entry in permissions.get("allow", [])
        if "$" in entry
    ]
    prefixes = _bash_prefixes(permissions.get("allow", []))
    if not prefixes:
        problems.append("no Bash(prefix:*) allow rules")
    for prefix in prefixes:
        path = _script_path(prefix)
        if path is not None and not path.is_file():
            problems.append(f"allow rule names a script that does not exist: {prefix} -> {path}")
    return problems


def kit_problems(markdown: str, settings: dict) -> list[str]:
    """Every way the kit text and the permission rules disagree; empty when the gate passes."""
    permissions = settings.get("permissions", {})
    allowed = _bash_prefixes(permissions.get("allow", []))
    blocked = _bash_prefixes(permissions.get("deny", []) + permissions.get("ask", []))
    problems: list[str] = []
    commands: list[str] = []
    for info, first_line, lines in _segments(markdown):
        if info == "sh":
            commands.extend(_sh_commands(lines))
            continue
        if info != "prose" and info not in ALLOWED_FENCES:
            problems.append(f"fence ```{info} at kit line {first_line}: only sh, text and json fences are allowed")
        for offset, raw in enumerate(lines):
            if INVOCATION.search(raw):
                problems.append(f"command outside an sh block at kit line {first_line + offset}: {raw.strip()}")
    if not commands:
        problems.append("the kit has no commands in sh blocks")
    for command in commands:
        if not any(_covers(prefix, command) for prefix in allowed):
            problems.append(f"no allow rule covers: {command}")
        if any(_covers(prefix, command) for prefix in blocked):
            problems.append(f"a deny or ask rule covers: {command}")
        bare = PLACEHOLDERS.sub("", command)
        for token in FORBIDDEN_SHELL:
            if token in bare:
                problems.append(f"contains {token!r}, which takes it outside its rule: {command}")
    if commands and commands[0] != PROBE:
        problems.append(f"the first command must be the zero-effect probe {PROBE!r}; found {commands[0]!r}")
    return problems


def _settings() -> dict:
    return json.loads(SETTINGS.read_text())


def test_allow_rules_are_literal_and_name_existing_scripts() -> None:
    assert rule_problems(_settings()) == []


def test_every_kit_command_is_a_literal_allow_rule_prefix_and_the_probe_comes_first() -> None:
    problems = kit_problems(KIT.read_text(), _settings())
    assert problems == [], (
        "tasks/fable-e8-launch-kit.md must issue every command as the literal prefix of an allow rule in "
        ".claude/settings.json, starting with the --help probe "
        "(lessons/ops-prove-the-permission-route-before-a-gated-session.md):\n  " + "\n  ".join(problems)
    )


# Each evasion mutates an in-memory copy of the real kit or rules; the gate must reject every one.
STEP_1 = "python3 tasks/fable-e8-repin-2026-09-22/restore_e8_session.py --uploads /root/.claude/uploads/<session-uploads-dir>"
EXPORT_FENCE = "```sh\npython3 tasks/fable-e8-repin-2026-09-22/export_e8_state.py"
KIT_EVASIONS = [
    ("variable form", lambda kit: kit.replace(STEP_1, 'python3 "$REPIN/restore_e8_session.py" --uploads x')),
    ("log redirect", lambda kit: kit.replace(STEP_1, STEP_1 + " > /tmp/restore.log 2>&1")),
    ("input redirect", lambda kit: kit.replace(STEP_1, STEP_1 + " < /dev/null")),
    ("semicolon", lambda kit: kit.replace(STEP_1, STEP_1 + "; echo done")),
    ("background ampersand", lambda kit: kit.replace(STEP_1, STEP_1 + " & true")),
    ("pipe", lambda kit: kit.replace(STEP_1, STEP_1 + " | tee out")),
    ("shell inside a placeholder", lambda kit: kit.replace("<session-uploads-dir>", "<a; rm -rf /x; cat >b>")),
    ("unknown placeholder", lambda kit: kit.replace("<session-uploads-dir>", "<$REPIN>")),
    ("probe removed", lambda kit: kit.replace(PROBE + "\n", "")),
    ("probe after step 1", lambda kit: kit.replace(PROBE + "\n", "") + "\n```sh\n" + PROBE + "\n```\n"),
    ("bash fence", lambda kit: kit.replace(EXPORT_FENCE, EXPORT_FENCE.replace("```sh", "```bash"))),
    ("tilde fence", lambda kit: kit.replace(EXPORT_FENCE, EXPORT_FENCE.replace("```sh", "~~~shell")) + "\n~~~\n"),
    ("command in prose", lambda kit: kit + "\nRun `python3 tasks/fable-e8-repin-2026-09-22/tools/resume.py --execute` now.\n"),
    ("unlisted tool in an sh block", lambda kit: kit + "\n```sh\npython3 tasks/fable-e8-repin-2026-09-22/tools/resume.py\n```\n"),
    ("the CLI itself", lambda kit: kit + "\n```sh\n/opt/claude-code/bin/claude -p hi\n```\n"),
    ("prefix without a space", lambda kit: kit.replace(PROBE, PROBE.replace(".py --help", ".pyx --help"))),
]


@pytest.mark.parametrize(("name", "mutate"), KIT_EVASIONS, ids=[name for name, _ in KIT_EVASIONS])
def test_gate_rejects_kit_evasion(name: str, mutate) -> None:
    original = KIT.read_text()
    mutated = mutate(original)
    assert mutated != original, f"evasion {name!r} did not change the kit text"
    assert kit_problems(mutated, _settings()), f"the gate accepted the {name!r} evasion"


def test_gate_rejects_rule_evasions() -> None:
    settings = _settings()
    with_variable = json.loads(json.dumps(settings))
    with_variable["permissions"]["allow"].append('Bash(python3 "$REPIN/restore_e8_session.py" --help)')
    assert rule_problems(with_variable), "an allow entry with a shell variable was accepted"

    missing_script = json.loads(json.dumps(settings))
    missing_script["permissions"]["allow"].append("Bash(python3 tasks/fable-e8-repin-2026-09-22/absent.py:*)")
    assert rule_problems(missing_script), "an allow rule naming a missing script was accepted"

    shadowed = json.loads(json.dumps(settings))
    shadowed["permissions"]["deny"] = ["Bash(python3 tasks/fable-e8-repin-2026-09-22/restore_e8_session.py:*)"]
    assert kit_problems(KIT.read_text(), shadowed), "a deny rule shadowing the probe was accepted"
