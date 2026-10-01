"""Structural gate for ``lessons/ops-prove-the-permission-route-before-a-gated-session.md`` (rule 12).

The 22 September 2026 E8 judging session stopped at its first gated command: the auto-mode
permission classifier denied ``restore_e8_session.py`` although ``.claude/settings.json`` carried
an allow rule for it. Two defects in the launch kit made that undetectable before any state
existed: every gated command was written with shell variables (``"$REPIN"``, ``"$PYTHON_BIN"``)
that no ``Bash(prefix:*)`` rule can ever match, and nothing proved the permission route before
step 1. Receipt: ``tasks/review-evidence/e8-repin-restore-2026-09-22/receipt.md``.

``kit_problems`` reads the committed launch kit (``tasks/fable-e8-launch-kit.md``) and the project
permission rules and reports every disagreement. ``Bash(<pattern>)`` rules are matched under
Claude Code's own semantics (code.claude.com/docs/en/permissions.md): ``prefix:*`` or ``prefix *``
covers the prefix alone or followed by a space and anything; any other ``*`` matches any text, so
``Bash(*)`` is the blanket rule; a pattern without ``*`` matches only itself. The gate fails when:

- the allow set is not exactly the seven pinned narrow rules (so a blanket ``Bash(*)`` or any
  wildcard beyond a trailing ``:*`` fails), an allow rule contains a shell variable, or an allow
  rule names a repository script that does not exist;
- any command in one of the kit's ``sh`` blocks is not covered by an allow rule, is covered by a
  deny or ask rule, or carries a variable, a command separator (``&``, ``;``, ``|``), a
  redirection (``<``, ``>``) or a backtick, any of which takes it outside its rule
  (separators per the same docs page);
- a fenced block uses an info string other than ``sh``, ``text`` or ``json``, or an interpreter
  or the CLI is invoked anywhere outside an ``sh`` block, or the token ``date`` appears there in
  any form, where the operator check would not see it (the kit takes timestamps from files the
  tools wrote, not from a command, and has no other use for the word);
- the kit's first command is not the zero-effect probe
  ``python3 tasks/fable-e8-repin-2026-09-22/restore_e8_session.py --help``, or the kit's ``sh``
  blocks do not hold exactly the seven pinned commands in order (probe, restore, inspection, the
  two one-time setup commands, execute, export), so a changed setup value such as the prior
  count, which would initialize the guard irreversibly with a value ``attest()`` then refuses,
  fails here rather than in the session;
- the attestation template (the kit's one ``json`` block) does not have exactly the key set, the
  prior count and the four sealed hashes that ``tools/e8_resume.py::attest`` requires (read from
  the sealed file with ``ast``, never imported), the three affirmatives true, or the guard state
  path of the execute command's guard;
- the attachment hash table differs from ``restore_e8_session.py::KIT_ATTACHMENTS``, which the
  restore enforces before it writes anything;
- the launch paragraph does not name the permission mode (``MODE_SENTENCE``): in Plan the auto-mode
  classifier reviews shell commands by default, and in Auto it denied the kit's commands twice
  (the lesson's "the kit names the session's permission mode explicitly").

A deny or ask rule that sets a Bash input parameter (``Bash(run_in_background:true)``, documented
under "Match by input parameter") shadows every gated command, step 6's background execute
included, and fails the gate.

Only the three named placeholders (``<session-uploads-dir>``, ``<UTC stamp>``, ``<post-run
stamp>``) are removed before the operator check; any other ``<…>`` span is shell syntax, and each
placeholder must appear exactly once across the kit's commands, in the one command that carries
it (the uploads directory in the restore, the pre-run stamp in the execute command's attestation
path, the post-run stamp in the export destination), and that command must equal the exact
string the gate pins, so the stamp ordering the kit prescribes is enforced, not just described,
and cannot be removed by hard-coding a value, dropping an argument, or appending a second
occurrence of a single-value option (argparse keeps the last one, so an unanchored check would
certify an attestation path the tool never reads). The evasion cases at the bottom lock each of
these behaviours against in-memory copies of the kit and rules.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SETTINGS = REPO_ROOT / ".claude" / "settings.json"
KIT = REPO_ROOT / "tasks" / "fable-e8-launch-kit.md"

# The repository root as the judging container mounts it; absolute rule paths under it map to REPO_ROOT.
CONTAINER_REPO = "/home/user/EarningsNerd"
# The permission route is these seven narrow rules and nothing else (handover section 4). A wider
# allow set, such as a blanket Bash(*), would let the gate certify unrestricted shell execution.
EXPECTED_ALLOW_RULES = (
    "Bash(python3 tasks/fable-e8-repin-2026-09-22/build_repin.py:*)",
    "Bash(python3 tasks/fable-e8-repin-2026-09-22/restore_e8_session.py:*)",
    "Bash(python3 tasks/fable-e8-repin-2026-09-22/export_e8_state.py:*)",
    "Bash(/home/user/fable-judging/venv/bin/python /home/user/EarningsNerd/tasks/fable-e8-repin-2026-09-22/tools/guard_setup.py:*)",
    "Bash(/home/user/fable-judging/venv/bin/python /home/user/EarningsNerd/tasks/fable-e8-repin-2026-09-22/tools/e8_resume.py:*)",
    "Bash(/home/user/fable-judging/venv/bin/python /home/user/EarningsNerd/tasks/fable-e8-repin-2026-09-22/tools/readout.py:*)",
    "Bash(/home/user/fable-judging/venv/bin/python -m unittest:*)",
)
PROBE = "python3 tasks/fable-e8-repin-2026-09-22/restore_e8_session.py --help"
PACKAGE = REPO_ROOT / "tasks" / "fable-e8-repin-2026-09-22"
GUARD_DIR = "/home/user/fable-judging/fable-resume-corrected-2026-09-20/e8/guard"
# The launch paragraph names the only mode in which the route is neither the classifier nor a plan gate.
MODE_SENTENCE = "select **Accept edits** in the permission-mode menu"
# Fence info strings the kit may use: sh blocks are commands, the others are data. Anything else fails.
ALLOWED_FENCES = {"sh", "text", "json"}
# Operator-substituted values. Any other text between < and > is shell syntax.
PLACEHOLDERS = re.compile(r"<(?:session-uploads-dir|UTC stamp|post-run stamp)>")
# Each placeholder is valid in exactly one command (the kit's stamp rules): the uploads directory only as the
# restore's --uploads value, the pre-run stamp only in the attestation path the execute command names, and the
# post-run stamp only in the export destination, which is the only command formed after execution. The gate pins
# each of those commands whole: argparse keeps the last occurrence of a single-value option, so a check anchored
# only at the placeholder would certify an execute command that goes on to name a different attestation file.
RESTORE = "python3 tasks/fable-e8-repin-2026-09-22/restore_e8_session.py --uploads /root/.claude/uploads/<session-uploads-dir>"
EXECUTE = (
    f"/home/user/fable-judging/venv/bin/python {CONTAINER_REPO}/tasks/fable-e8-repin-2026-09-22/tools/e8_resume.py"
    " --bundle /home/user/fable-judging/fable-resume-corrected-2026-09-20"
    f" --supplement {CONTAINER_REPO}/tasks/fable-e8-repin-2026-09-22"
    " --repo /home/user/earningsnerd-fable-frozen"
    " --python /home/user/fable-judging/venv/bin/python"
    " --cli /opt/claude-code/bin/claude"
    " --guard-dir /home/user/fable-judging/fable-resume-corrected-2026-09-20/e8/guard"
    " --attestation /home/user/fable-judging/receipts/e8-attestation-<UTC stamp>.json"
    " --max-new 160 --execute"
)
EXPORT = (
    "python3 tasks/fable-e8-repin-2026-09-22/export_e8_state.py"
    " --bundle /home/user/fable-judging/fable-resume-corrected-2026-09-20"
    " --receipts /home/user/fable-judging/receipts"
    " --out tasks/review-evidence/e8-fable-state-<post-run stamp>"
)


def sealed_constants() -> dict:
    """Module-level constants of the sealed tools/e8_resume.py, read with ast (it is never imported)."""
    tree = ast.parse((PACKAGE / "tools" / "e8_resume.py").read_text())
    constants = {
        node.targets[0].id: node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant)
    }
    attest = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "attest")
    for node in ast.walk(attest):
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == "expected_keys":
            constants["expected_keys"] = {element.value for element in node.value.elts}
    return constants


SEALED = sealed_constants()
INSPECT = (
    f"/home/user/fable-judging/venv/bin/python {CONTAINER_REPO}/tasks/fable-e8-repin-2026-09-22/tools/e8_resume.py"
    " --bundle /home/user/fable-judging/fable-resume-corrected-2026-09-20"
    f" --supplement {CONTAINER_REPO}/tasks/fable-e8-repin-2026-09-22"
    " --repo /home/user/earningsnerd-fable-frozen"
)
SETUP = (
    f"/home/user/fable-judging/venv/bin/python {CONTAINER_REPO}/tasks/fable-e8-repin-2026-09-22/tools/guard_setup.py"
    f" --guard-dir {GUARD_DIR} --real-cli /opt/claude-code/bin/claude"
)
CONFIGURE = SETUP + " --configure-template"
INITIALIZE = SETUP + f" --prior-count {SEALED['MIN_PRIOR']}"
KIT_COMMANDS = (PROBE, RESTORE, INSPECT, CONFIGURE, INITIALIZE, EXECUTE, EXPORT)
PLACEHOLDER_COMMANDS = {
    "<session-uploads-dir>": ("the restore command", RESTORE),
    "<UTC stamp>": ("the execute command", EXECUTE),
    "<post-run stamp>": ("the export command", EXPORT),
}
# Variables, the command separators Claude Code recognises (& covers &&, |& and &>; | covers ||),
# redirections and backticks: each takes a command outside its rule.
FORBIDDEN_SHELL = ("$", "&", ";", "|", ">", "<", "`")
# An interpreter or the CLI followed by an argument, anywhere outside an sh block, is a command the gate would
# not see; so is the token `date` in any form (bare, backticked, path-qualified, with or without arguments),
# because the kit's timestamps come from files the tools wrote, never from a command, and the kit has no other
# use for the word.
INVOCATION = re.compile(
    r"(?:^|[\s`\"'(])(?:python3?|/home/user/fable-judging/venv/bin/python|/opt/claude-code/bin/claude)\s+\S"
    r"|(?<![\w-])(?:/usr/bin/|/bin/)?date(?![\w-])"
)

_BASH_ENTRY = re.compile(r"^Bash\((.+)\)$")
# Bash tool input fields a `Bash(<field>:<value>)` deny or ask rule can match (permissions.md,
# "Match by input parameter"); any other `name:value` pattern is the legacy `prefix:*` command form.
BASH_PARAMETERS = ("run_in_background", "timeout", "description", "dangerouslyDisableSandbox")
# Whitespace around the colon is ignored (permissions.md), so the gate ignores it too.
_PARAMETER_RULE = re.compile(r"^\s*(?:%s)\s*:" % "|".join(BASH_PARAMETERS))
_FENCE = re.compile(r"^(`{3,}|~{3,})\s*(\S*)$")


def _rule_regex(pattern: str) -> re.Pattern[str]:
    """The matcher for one Bash(<pattern>) rule under Claude Code's semantics (module docstring).

    A trailing ``:*`` or `` *`` also matches the bare prefix only when it is the rule's only
    wildcard: ``Bash(* --help *)`` covers ``npm --help x`` but not ``npm --help`` (permissions.md).
    """
    if pattern.endswith((":*", " *")):
        body = pattern[:-2]
        if "*" in body:
            return re.compile(".*".join(re.escape(part) for part in body.split("*")) + r" .*", re.DOTALL)
        return re.compile(re.escape(body) + r"(?: .*)?", re.DOTALL)
    return re.compile(".*".join(re.escape(part) for part in pattern.split("*")), re.DOTALL)


def _bash_rules(entries: list[str]) -> list[tuple[str, re.Pattern[str]]]:
    """(pattern, matcher) for every Bash(...) entry; entries for other tools are ignored."""
    return [(m.group(1), _rule_regex(m.group(1))) for entry in entries if (m := _BASH_ENTRY.fullmatch(entry))]


def _covered(command: str, rules: list[tuple[str, re.Pattern[str]]]) -> bool:
    return any(matcher.fullmatch(command) for _, matcher in rules)


def _script_path(pattern: str) -> Path | None:
    """The repository script a rule names literally, or None when it names no repository path."""
    literal = pattern[:-2] if pattern.endswith((":*", " *")) else pattern
    for token in literal.split():
        if "*" in token:
            continue
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
    """Every way the allow rules are unfit: not the pinned set, variables, wildcards, or missing scripts."""
    allow = settings.get("permissions", {}).get("allow", [])
    problems = [f"allow entry is not one of the pinned launch-kit rules: {entry}" for entry in allow if entry not in EXPECTED_ALLOW_RULES]
    problems += [f"pinned launch-kit allow rule is missing: {entry}" for entry in EXPECTED_ALLOW_RULES if entry not in allow]
    for pattern, _ in _bash_rules(allow):
        if "$" in pattern:
            problems.append(f"allow rule carries a shell variable, which can never match: {pattern}")
        if "*" in (pattern[:-2] if pattern.endswith((":*", " *")) else pattern):
            problems.append(f"allow rule is overbroad; only a trailing :* is allowed: {pattern}")
        path = _script_path(pattern)
        if path is not None and not path.is_file():
            problems.append(f"allow rule names a script that does not exist: {pattern} -> {path}")
    return problems


def kit_problems(markdown: str, settings: dict) -> list[str]:
    """Every way the kit text and the permission rules disagree; empty when the gate passes."""
    permissions = settings.get("permissions", {})
    allowed = _bash_rules(permissions.get("allow", []))
    blocked = _bash_rules(permissions.get("deny", []) + permissions.get("ask", []))
    problems: list[str] = [
        f"a deny or ask rule on a Bash input parameter shadows every gated command, step 6's background run included: {pattern}"
        for pattern, _ in blocked if _PARAMETER_RULE.match(pattern)
    ]
    # A bare tool name is the whole-tool rule (the same as Bash(*)) and shadows every gated command.
    problems += [f"a whole-tool {entry!r} deny or ask rule shadows every gated command"
                 for entry in permissions.get("deny", []) + permissions.get("ask", []) if entry.strip() == "Bash"]
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
        if not _covered(command, allowed):
            problems.append(f"no allow rule covers: {command}")
        if _covered(command, blocked):
            problems.append(f"a deny or ask rule covers: {command}")
        bare = PLACEHOLDERS.sub("", command)
        for token in FORBIDDEN_SHELL:
            if token in bare:
                problems.append(f"contains {token!r}, which takes it outside its rule: {command}")
        for placeholder in sorted(set(PLACEHOLDERS.findall(command))):
            role, expected = PLACEHOLDER_COMMANDS[placeholder]
            if command != expected:
                problems.append(f"placeholder {placeholder} is valid only in {role}, pinned whole as {expected!r}: {command}")
    if commands and commands[0] != PROBE:
        problems.append(f"the first command must be the zero-effect probe {PROBE!r}; found {commands[0]!r}")
    if commands != list(KIT_COMMANDS):
        problems.append("the kit's sh blocks must hold exactly the seven pinned commands in order: "
                        f"expected {list(KIT_COMMANDS)!r}, found {commands!r}")
    for placeholder, (role, _) in PLACEHOLDER_COMMANDS.items():
        occurrences = sum(command.count(placeholder) for command in commands)
        if occurrences != 1:
            problems.append(
                f"placeholder {placeholder} must appear exactly once across the kit's commands, as {role}; found {occurrences}"
            )
    return problems


def attestation_problems(markdown: str) -> list[str]:
    """The kit's attestation template against the sealed attest() contract."""
    blocks = ["\n".join(lines) for info, _, lines in _segments(markdown) if info == "json"]
    if len(blocks) != 1:
        return [f"the kit must carry exactly one json block (the attestation template); found {len(blocks)}"]
    try:
        template = json.loads(blocks[0])
    except ValueError as exc:
        return [f"the attestation template is not JSON: {exc}"]
    expected = {
        "schema": "fable-e8-accounting-attestation-v1",
        "prior_count": SEALED["MIN_PRIOR"],
        "prior_evidence_sha256": SEALED["PRIOR_EVIDENCE_SHA256"],
        "founder_statement_sha256": SEALED["FOUNDER_STATEMENT_SHA256"],
        "original_manifest_sha256": SEALED["ORIGINAL_MANIFEST_SHA256"],
        "e3_supplement_manifest_sha256": SEALED["E3_SUPPLEMENT_MANIFEST_SHA256"],
        "guard_state_path": GUARD_DIR + "/state.json",
        "no_untracked_e8_or_probe_calls": True,
        "sole_persistent_guard": True,
        "exclusive_e8_dispatch_during_continuation": True,
    }
    problems = []
    if set(template) != SEALED["expected_keys"]:
        problems.append(f"attestation keys {sorted(template)} != attest() keys {sorted(SEALED['expected_keys'])}")
    for key, value in expected.items():
        if template.get(key) != value or type(template.get(key)) is not type(value):
            problems.append(f"attestation template {key} is {template.get(key)!r}, attest() requires {value!r}")
    return problems


TABLE_ROW = re.compile(r"^\| (\S+) \| ([0-9a-f]{64}) \|$")


def restore_pins() -> dict:
    spec = importlib.util.spec_from_file_location("restore_e8_session_pins", PACKAGE / "restore_e8_session.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.KIT_ATTACHMENTS


def table_problems(markdown: str) -> list[str]:
    """The kit's attachment table against the hashes the restore refuses on."""
    rows = [m.groups() for line in markdown.splitlines() if (m := TABLE_ROW.match(line.strip()))]
    pins = restore_pins()
    if sorted(rows) != sorted(pins.items()):
        return [f"attachment table rows {rows} != restore_e8_session.KIT_ATTACHMENTS {pins} (one row per attachment)"]
    return []


def mode_problems(markdown: str) -> list[str]:
    launch = markdown.split("## Message 1", 1)[0]
    if MODE_SENTENCE not in launch:
        return [f"the launch paragraph must name the permission mode: {MODE_SENTENCE!r}"]
    return []


def all_problems(markdown: str, settings: dict) -> list[str]:
    return kit_problems(markdown, settings) + attestation_problems(markdown) + table_problems(markdown) + mode_problems(markdown)


def _settings() -> dict:
    return json.loads(SETTINGS.read_text())


def test_allow_rules_are_the_pinned_narrow_set_and_name_existing_scripts() -> None:
    assert rule_problems(_settings()) == []


def test_script_path_resolves_repository_paths_in_every_rule_form() -> None:
    absent = REPO_ROOT / "tasks/fable-e8-repin-2026-09-22/absent.py"
    assert _script_path("python3 tasks/fable-e8-repin-2026-09-22/absent.py:*") == absent
    assert _script_path(f"/x/venv/bin/python {CONTAINER_REPO}/tasks/fable-e8-repin-2026-09-22/absent.py:*") == absent
    assert _script_path("/x/venv/bin/python -m unittest:*") is None
    assert not absent.exists()


def test_every_kit_command_is_covered_by_an_allow_rule_and_the_probe_comes_first() -> None:
    problems = all_problems(KIT.read_text(), _settings())
    assert problems == [], (
        "tasks/fable-e8-launch-kit.md must issue every command as the literal prefix of an allow rule in "
        ".claude/settings.json, starting with the --help probe "
        "(lessons/ops-prove-the-permission-route-before-a-gated-session.md):\n  " + "\n  ".join(problems)
    )


RULE_SEMANTICS = [
    ("exact matches itself only", "Bash(ls -la)", "ls -la", "ls -la /tmp"),
    ("colon-star matches the prefix alone or followed by a space", "Bash(ls:*)", "ls", "lsblk"),
    ("colon-star matches the prefix followed by anything after a space", "Bash(ls:*)", "ls -la /tmp", "ls-la"),
    ("space-star is the colon-star form", "Bash(ls *)", "ls -la", "lsblk"),
    ("a wildcard inside the pattern matches any text", "Bash(git * main)", "git checkout main", "git checkout dev"),
    ("the blanket rule matches everything", "Bash(*)", "anything at all", None),
    ("a trailing space-star after another wildcard needs an argument", "Bash(* --help *)", "npm --help x", "npm --help"),
    ("a trailing colon-star after another wildcard needs an argument", "Bash(python3 * --out:*)", "python3 x --out y", "python3 x --out"),
]


@pytest.mark.parametrize(("name", "entry", "covered", "uncovered"), RULE_SEMANTICS, ids=[r[0] for r in RULE_SEMANTICS])
def test_bash_rule_matching_follows_the_documented_semantics(name: str, entry: str, covered: str, uncovered) -> None:
    rules = _bash_rules([entry])
    assert _covered(covered, rules), f"{name}: {entry} should cover {covered!r}"
    if uncovered is not None:
        assert not _covered(uncovered, rules), f"{name}: {entry} should not cover {uncovered!r}"


# Each evasion mutates an in-memory copy of the real kit or rules; the gate must reject every one.
STEP_1 = RESTORE
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
    ("shell timestamp in prose", lambda kit: kit + "\nTake the stamp from `date -u +%Y%m%dT%H%M%SZ`.\n"),
    ("shell timestamp without flags in prose", lambda kit: kit + "\nTake the stamp from `date +%Y%m%dT%H%M%SZ`.\n"),
    ("bare backticked shell timestamp in prose", lambda kit: kit + "\nRun `date` now.\n"),
    ("bare unquoted shell timestamp in prose", lambda kit: kit + "\nRun date now.\n"),
    ("path-qualified shell timestamp in prose", lambda kit: kit + "\nRun /bin/date -u first.\n"),
    ("bare path-qualified shell timestamp in prose", lambda kit: kit + "\nRun /usr/bin/date now.\n"),
    ("shell timestamp in an sh block", lambda kit: kit + "\n```sh\ndate -u +%Y%m%dT%H%M%SZ\n```\n"),
    ("bare shell timestamp in an sh block", lambda kit: kit + "\n```sh\ndate\n```\n"),
    ("unlisted tool in an sh block", lambda kit: kit + "\n```sh\npython3 tasks/fable-e8-repin-2026-09-22/tools/resume.py\n```\n"),
    ("the CLI itself", lambda kit: kit + "\n```sh\n/opt/claude-code/bin/claude -p hi\n```\n"),
    ("prefix without a space", lambda kit: kit.replace(PROBE, PROBE.replace(".py --help", ".pyx --help"))),
    ("post-run stamp in the attestation path", lambda kit: kit.replace("e8-attestation-<UTC stamp>.json --max-new", "e8-attestation-<post-run stamp>.json --max-new")),
    ("pre-run stamp in the export destination", lambda kit: kit.replace("e8-fable-state-<post-run stamp>", "e8-fable-state-<UTC stamp>")),
    ("uploads placeholder in the export destination", lambda kit: kit.replace("e8-fable-state-<post-run stamp>", "e8-fable-state-<session-uploads-dir>")),
    ("stamp placeholder in the restore command", lambda kit: kit.replace("/root/.claude/uploads/<session-uploads-dir>", "/root/.claude/uploads/<UTC stamp>")),
    ("hard-coded attestation stamp", lambda kit: kit.replace("e8-attestation-<UTC stamp>.json --max-new", "e8-attestation-20260922T220300Z.json --max-new")),
    ("attestation argument removed", lambda kit: kit.replace(" --attestation /home/user/fable-judging/receipts/e8-attestation-<UTC stamp>.json", "")),
    ("hard-coded export stamp", lambda kit: kit.replace("e8-fable-state-<post-run stamp>", "e8-fable-state-20260922T220300Z")),
    ("hard-coded uploads directory", lambda kit: kit.replace("/root/.claude/uploads/<session-uploads-dir>", "/root/.claude/uploads/a714ff2c")),
    ("second attestation after --execute", lambda kit: kit.replace(EXECUTE, EXECUTE + " --attestation /tmp/hardcoded.json")),
    ("second attestation in equals form", lambda kit: kit.replace("--max-new 160 --execute", "--attestation=/tmp/hardcoded.json --max-new 160 --execute")),
    ("second uploads directory on the restore", lambda kit: kit.replace(STEP_1, STEP_1 + " --uploads /tmp/other")),
    ("second export destination", lambda kit: kit.replace(EXPORT, EXPORT + " --out /tmp/other")),
    ("execute ceiling altered", lambda kit: kit.replace("--max-new 160 --execute", "--max-new 161 --execute")),
    ("setup prior count altered", lambda kit: kit.replace("--prior-count 287", "--prior-count 300")),
    ("setup command removed", lambda kit: kit.replace(CONFIGURE + "\n", "")),
    ("setup commands swapped", lambda kit: kit.replace(CONFIGURE + "\n" + INITIALIZE, INITIALIZE + "\n" + CONFIGURE)),
    ("setup real CLI altered", lambda kit: kit.replace(CONFIGURE, CONFIGURE.replace("/opt/claude-code/bin/claude", "/opt/node22/bin/claude"))),
    ("inspection bundle altered", lambda kit: kit.replace(INSPECT + "\n", INSPECT.replace("2026-09-20 --supplement", "2026-09-21 --supplement") + "\n")),
    ("setup repeated", lambda kit: kit.replace(INITIALIZE, INITIALIZE + "\n" + INITIALIZE)),
    ("attestation prior count altered", lambda kit: kit.replace('"prior_count": 287', '"prior_count": 288')),
    ("attestation prior count as a string", lambda kit: kit.replace('"prior_count": 287', '"prior_count": "287"')),
    ("attestation supplement hash reverted to the sealed original", lambda kit: kit.replace(
        '"e3_supplement_manifest_sha256": "1ef772b3', '"e3_supplement_manifest_sha256": "8e43ac91')),
    ("attestation affirmative false", lambda kit: kit.replace('"sole_persistent_guard": true', '"sole_persistent_guard": false')),
    ("attestation key dropped", lambda kit: kit.replace('  "exclusive_e8_dispatch_during_continuation": true\n', '').replace('"sole_persistent_guard": true,', '"sole_persistent_guard": true')),
    ("attestation guard path altered", lambda kit: kit.replace('"guard_state_path": "/home/user/fable-judging', '"guard_state_path": "/tmp/fable-judging')),
    ("attachment table row altered", lambda kit: kit.replace("| 5298a21e818c", "| 5298a21e818d")),
    ("attachment table row removed", lambda kit: "\n".join(line for line in kit.splitlines() if not line.startswith("| transport-manifest.json"))),
    ("permission mode not named", lambda kit: kit.replace(MODE_SENTENCE, "select a mode")),
    ("stale duplicate table row before the right one", lambda kit: kit.replace(
        "| fable-e8-continuation-2026-09-22.zip | 5298a21e", "| fable-e8-continuation-2026-09-22.zip | " + "0" * 64
        + " |\n| fable-e8-continuation-2026-09-22.zip | 5298a21e")),
]


@pytest.mark.parametrize(("name", "mutate"), KIT_EVASIONS, ids=[name for name, _ in KIT_EVASIONS])
def test_gate_rejects_kit_evasion(name: str, mutate) -> None:
    original = KIT.read_text()
    mutated = mutate(original)
    assert mutated != original, f"evasion {name!r} did not change the kit text"
    assert all_problems(mutated, _settings()), f"the gate accepted the {name!r} evasion"


RULE_EVASIONS = [
    ("allow entry with a shell variable", "allow", 'Bash(python3 "$REPIN/restore_e8_session.py" --help)'),
    ("allow rule naming a missing script", "allow", "Bash(python3 tasks/fable-e8-repin-2026-09-22/absent.py:*)"),
    ("wildcard deny shadowing the probe", "deny", "Bash(python3 tasks/fable-e8-repin-2026-09-22/restore_e8_session.py:*)"),
    ("exact deny shadowing the probe", "deny", f"Bash({PROBE})"),
    ("exact ask shadowing the probe", "ask", f"Bash({PROBE})"),
    ("wildcard ask shadowing step 2", "ask", "Bash(/home/user/fable-judging/venv/bin/python:*)"),
    ("blanket deny", "deny", "Bash(*)"),
    ("blanket ask", "ask", "Bash(*)"),
    ("space-star deny shadowing the probe", "deny", "Bash(python3 tasks/fable-e8-repin-2026-09-22/restore_e8_session.py *)"),
    ("mid-pattern wildcard deny", "deny", "Bash(python3 * --help)"),
    ("blanket allow", "allow", "Bash(*)"),
    ("overbroad allow", "allow", "Bash(python3 *)"),
    ("unpinned narrow allow", "allow", "Bash(ls:*)"),
    ("leading-wildcard ask shadowing the restore", "ask", "Bash(* --uploads *)"),
    ("leading-wildcard deny shadowing the execute", "deny", "Bash(* --attestation *)"),
    ("mid-pattern ask shadowing the export", "ask", "Bash(python3 * --out *)"),
    ("parameter ask on background runs", "ask", "Bash(run_in_background:true)"),
    ("parameter deny on timeouts", "deny", "Bash(timeout:*)"),
    ("parameter deny with a spaced colon", "deny", "Bash(run_in_background : true)"),
    ("whole-tool deny", "deny", "Bash"),
    ("whole-tool ask", "ask", "Bash"),
]


@pytest.mark.parametrize(("name", "key", "entry"), RULE_EVASIONS, ids=[name for name, _, _ in RULE_EVASIONS])
def test_gate_rejects_rule_evasion(name: str, key: str, entry: str) -> None:
    settings = _settings()
    settings["permissions"].setdefault(key, []).append(entry)
    assert rule_problems(settings) or kit_problems(KIT.read_text(), settings), f"the gate accepted {name!r}"


def test_gate_rejects_a_missing_pinned_allow_rule_and_a_blanket_replacement() -> None:
    settings = _settings()
    settings["permissions"]["allow"].remove(EXPECTED_ALLOW_RULES[2])
    assert rule_problems(settings) and kit_problems(KIT.read_text(), settings)
    settings["permissions"]["allow"] = ["Bash(*)"]
    assert rule_problems(settings), "a blanket allow set covering every command was accepted"
