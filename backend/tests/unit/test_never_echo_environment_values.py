"""A settings secret never reaches an output through five gated paths (rule 12; CODE RED record 23, plan item 3;
lessons/ops-never-echo-environment-values.md).

pydantic appends each failing field's input to its error message (`input_value=...`), and a missing
required field's input is the whole environment-derived settings dict. Without
`hide_input_in_errors`, a settings validation error printed environment values, secrets included,
into whatever output carried it: a service's startup log, CI's public log, or an agent's own tool
output (CODE RED records 22 and 23 each disclose one such echo). That is the first path. Review of
the fix found four more, each gated here:

- the setting covers the error's rendered text only (`str`, `repr`, so a traceback or a log line);
  its structured form, `errors()` and `json()`, still returns each input unless called with
  `include_input=False`, so every `except` block that calls them must pass it;
- a settings object's repr carried every value, and Sentry's default local-variable capture
  serializes the repr of every frame local, so a captured error would have sent every secret;
- a validator's own message can quote a value, which no pydantic setting hides;
- `scripts/deploy_check.py` printed the first 30 characters of every value it checked.

Not covered: a secret copied out of the settings object into another local or a request header still
reaches Sentry's capture (a separate follow-up).
"""

import ast
import importlib
import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config import MIN_SECRET_KEY_LENGTH, Settings

BACKEND_DIR = Path(__file__).resolve().parents[2]
SENTINEL = "PRIVATE_SETTINGS_SENTINEL_" + "x" * (MIN_SECRET_KEY_LENGTH - 27)  # one character too short to pass
SHORT_SENTINEL = "PRIVATE_DB_7c1e"  # short enough that an echoed input is never shortened


class _Echoing(Settings):
    """The control: the same class with pydantic's default, so the echo the tests rule out is shown to exist."""

    model_config = SettingsConfigDict(hide_input_in_errors=False)


def _error_text(model: type[Settings], **values: str) -> str:
    with pytest.raises(ValidationError) as info:
        model(_env_file=None, **values)
    return f"{info.value}\n{info.value!r}"


def test_settings_hide_input_in_errors():
    # A diagnostic pin: the two tests below fail without the setting too, but this one names the cause.
    assert Settings.model_config.get("hide_input_in_errors") is True


def test_a_failing_value_is_not_echoed():
    # The SECRET_KEY validator rejects a short key; the error would otherwise append the key itself.
    assert SENTINEL in _error_text(_Echoing, SECRET_KEY=SENTINEL)
    text = _error_text(Settings, SECRET_KEY=SENTINEL)
    assert "SECRET_KEY" in text
    assert SENTINEL not in text
    assert "input_value" not in text


def test_the_missing_field_dict_is_not_echoed(monkeypatch):
    # A missing required field's input is the whole environment-derived dict (a production DATABASE_URL
    # carries the database password). pydantic shortens a long input to its two ends, so the environment
    # is cleared to one short entry that the error would otherwise print whole. The class reads names
    # case-insensitively, so every case variant of a field name is cleared.
    names = {name.lower() for name in Settings.model_fields}
    for key in list(os.environ):
        if key.lower() in names:
            monkeypatch.delenv(key)
    monkeypatch.setenv("DATABASE_URL", SHORT_SENTINEL)
    assert SHORT_SENTINEL in _error_text(_Echoing)
    text = _error_text(Settings)
    assert "SECRET_KEY" in text
    assert SHORT_SENTINEL not in text
    assert "input_value" not in text


def test_a_settings_object_prints_no_value():
    # Imported here, not at module level: sentry-sdk's serializer is an internal module, and a rename in an
    # upgrade should fail this test alone.
    from sentry_sdk.serializer import serialize

    secret = "PRIVATE_SIGNING_KEY_7c1e_" + "x" * MIN_SECRET_KEY_LENGTH  # fabricated sentinel  # gitleaks:allow
    database = "postgresql://app:PRIVATE_DB_PASSWORD_7c1e@db/app"
    stripe = "sk_live_PRIVATE_STRIPE_7c1e"
    settings = Settings(SECRET_KEY=secret, DATABASE_URL=database, STRIPE_SECRET_KEY=stripe, _env_file=None)
    assert (settings.SECRET_KEY, settings.DATABASE_URL, settings.STRIPE_SECRET_KEY) == (secret, database, stripe)
    # Sentry's serializer is the channel: a frame local is sent as the repr this checks.
    sent = json.dumps(serialize({"vars": {"settings": settings}}), default=str)
    for text in (repr(settings), str(settings), f"{settings!r}", f"{settings}", sent):
        assert "PRIVATE_" not in text


def _hides_input(call: ast.Call) -> bool:
    return any(
        keyword.arg == "include_input" and isinstance(keyword.value, ast.Constant) and keyword.value.value is False
        for keyword in call.keywords
    )


def _structured_calls_with_input(tree: ast.Module) -> list[int]:
    """Lines where an `except ... as name` handler calls `name.errors()` or `name.json()` without include_input=False.

    Every handler counts, whatever it catches: pydantic's ValidationError subclasses ValueError, and the one place a
    settings error is caught today (scripts/deploy_check.py) catches Exception. Another object's `.json()` inside the
    handler (`exc.response.json()`, `response.json()`) is not the caught exception's, so it is not matched. Only the
    handler's own direct calls on its bound name are read: an alias (`f = exc.errors`), `getattr`, a helper the
    exception is handed to, a FastAPI exception-handler function and an except* group's members are not.
    """
    lines = set()
    for handler in ast.walk(tree):
        if not isinstance(handler, ast.ExceptHandler) or not handler.name:
            continue
        for node in (inner for statement in handler.body for inner in ast.walk(statement)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"errors", "json"}
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == handler.name
                and not _hides_input(node)
            ):
                lines.add(node.lineno)
    return sorted(lines)


def _scanned_files() -> list[Path]:
    """Every backend Python file outside tests/: the entrypoints, the application, its scripts and its evals."""
    return [
        *sorted(BACKEND_DIR.glob("*.py")),
        *(path for root in ("app", "scripts", "evals") for path in sorted((BACKEND_DIR / root).rglob("*.py"))),
    ]


def test_no_caught_exception_is_serialized_with_its_input():
    handled, found = set(), []
    for path in _scanned_files():
        rel = path.relative_to(BACKEND_DIR).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(isinstance(node, ast.ExceptHandler) and node.name for node in ast.walk(tree)):
            handled.add(rel)
        found.extend(f"{rel}:{line}" for line in _structured_calls_with_input(tree))
    # The walk reaches the one handler of a settings error, the one of a pydantic ValidationError, both
    # entrypoints' neighbours and the evals.
    assert {"scripts/deploy_check.py", "app/routers/tasks.py", "main.py"} <= handled
    assert any(rel.startswith("evals/") for rel in handled)
    assert not found, (
        f"A caught exception is serialized with its input: {found}. A pydantic error's `errors()` and `json()` return "
        "each failing value (for the settings class, environment values and secrets) unless called with "
        "include_input=False; pass it, or log the error's rendered text."
    )


_TRY = "try:\n    f()\n"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (_TRY + "except ValidationError as exc:\n    log(exc.errors())\n", [4]),
        (_TRY + "except ValidationError as exc:\n    log(exc.json(indent=2))\n", [4]),
        (_TRY + "except ValidationError as exc:\n    log(exc.errors(include_input=True))\n", [4]),
        (_TRY + "except ValidationError as exc:\n    log(exc.errors(**options))\n", [4]),
        (_TRY + "except Exception as exc:\n    print(exc.errors())\n", [4]),
        (_TRY + "except (KeyError, ValueError) as exc:\n    log(exc.json())\n", [4]),
        (
            _TRY
            + "except ValidationError as exc:\n    def report():\n        return exc.errors()\n    log(report())\n",
            [5],
        ),
        (_TRY + "except ValidationError as exc:\n    log(exc.errors(include_input=False))\n", []),
        (_TRY + "except Exception as exc:\n    log(exc.json(include_input=False))\n", []),
        (_TRY + "except httpx.HTTPStatusError as exc:\n    log(exc.response.json(), response.json(), str(exc))\n", []),
        (_TRY + "except ValueError:\n    log(errors())\n", []),
    ],
    ids=[
        "errors",
        "json",
        "include-input-true",
        "keyword-splat",
        "catch-all",
        "tuple",
        "nested-function",
        "errors-hidden",
        "json-hidden",
        "other-objects",
        "unnamed-handler",
    ],
)
def test_the_structured_form_gate_flags_input(source, expected):
    assert _structured_calls_with_input(ast.parse(source)) == expected


# The one sanctioned quotation: REGISTRATION_MODE holds no secret, and a typo there must be visible.
QUOTES_ITS_VALUE = {("_normalize_registration_mode", "v")}
_MUTATORS = {"append", "extend", "insert", "add", "update"}


def _quoted(node: ast.AST, assigned: dict[str, list[ast.expr]], seen: frozenset[str] = frozenset()) -> set[str]:
    """What a message expression reads beyond constants, ALL_CAPS module constants and `len(...)`.

    Default deny: every other name or attribute counts (a parameter such as `v` or `info`, `self.FIELD`,
    `os.environ`, `os.getenv(...)`); a local counts through every expression assigned to it in the function.
    """
    if isinstance(node, ast.Constant):
        return set()
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id == "len":
            return set()  # a length, never the value
        called = set() if isinstance(node.func, ast.Name) else _quoted(node.func, assigned, seen)
        return called.union(*(_quoted(arg, assigned, seen) for arg in [*node.args, *(k.value for k in node.keywords)]))
    if isinstance(node, ast.Name):
        if node.id.isupper():
            return set()  # a module constant such as MIN_SECRET_KEY_LENGTH
        if node.id in assigned and node.id not in seen:
            return set().union(*(_quoted(expr, assigned, seen | {node.id}) for expr in assigned[node.id]))
        return {node.id}
    if isinstance(node, ast.Attribute):
        if isinstance(node.value, ast.Constant):
            return set()  # a method of a literal, such as ", ".join
        return (
            {ast.unparse(node)}
            if _quoted(node.value, assigned, seen) or not isinstance(node.value, ast.Name)
            else set()
        )
    return set().union(*(_quoted(child, assigned, seen) for child in ast.iter_child_nodes(node)))


def _assignments(function: ast.AST) -> dict[str, list[ast.expr]]:
    """Every expression the function binds or appends to a local name, tuple targets and loop variables included."""
    assigned: dict[str, list[ast.expr]] = {}

    def bind(target: ast.AST, expr: ast.expr) -> None:
        for name in (node for node in ast.walk(target) if isinstance(node, ast.Name)):
            assigned.setdefault(name.id, []).append(expr)

    for node in ast.walk(function):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                bind(target, node.value)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)) and node.value is not None:
            bind(node.target, node.value)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            bind(node.target, node.iter)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _MUTATORS
            and isinstance(node.func.value, ast.Name)
        ):
            for arg in node.args:
                bind(node.func.value, arg)
    return assigned


def _quotations(tree: ast.Module) -> set[tuple[str, str]]:
    """(function, what it quotes) for every raise or assert message in the module that reads a value."""
    found = set()
    for function in (node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
        assigned = _assignments(function)
        for node in ast.walk(function):
            message = node.exc if isinstance(node, ast.Raise) else node.msg if isinstance(node, ast.Assert) else None
            if message is not None:
                found.update((function.name, name) for name in _quoted(message, assigned))
    return found


def test_no_settings_message_quotes_a_value():
    # Every validator lives in config.py's one class, whose only base is pydantic-settings' own.
    assert Settings.__bases__ == (BaseSettings,)
    tree = ast.parse((BACKEND_DIR / "app" / "config.py").read_text(encoding="utf-8"))
    assert _quotations(tree) == QUOTES_ITS_VALUE, (
        "A raise or assert message in app/config.py reads a value (a parameter, a field, the environment), and no "
        "pydantic setting hides a validator's own message. Report the field and the reason, or a length (`len(v)`); "
        "add to QUOTES_ITS_VALUE only a quotation of a field that holds no secret."
    )


_CLASS = "class Settings:\n"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (_CLASS + "    def check(cls, v):\n        raise ValueError(f'bad {v!r}')\n", {("check", "v")}),
        (_CLASS + "    def check(cls, v):\n        raise ValueError('bad %s' % v)\n", {("check", "v")}),
        (_CLASS + "    def check(cls, v):\n        raise ValueError('bad {}'.format(v))\n", {("check", "v")}),
        (
            _CLASS + "    def check(self):\n        raise ValueError(f'bad {self.STRIPE_SECRET_KEY}')\n",
            {("check", "self.STRIPE_SECRET_KEY")},
        ),
        (
            _CLASS + "    def check(cls, v, info):\n        raise ValueError(f\"clash {info.data['SECRET_KEY']}\")\n",
            {("check", "info.data")},
        ),
        (
            _CLASS + "    def __init__(self):\n        key = os.getenv('K')\n        raise ValueError(f'bad {key}')\n",
            {("__init__", "os.getenv")},
        ),
        (
            _CLASS + "    def check(cls, v):\n        msg = f'bad {v!r}'\n        raise ValueError(msg)\n",
            {("check", "v")},
        ),
        (
            _CLASS + "    def check(cls, v):\n        parts = []\n        parts.append(v)\n"
            "        raise ValueError(', '.join(parts))\n",
            {("check", "v")},
        ),
        (
            _CLASS + "    def check(cls, v):\n        if (s := v.strip()):\n            raise ValueError(f'bad {s}')\n",
            {("check", "v.strip")},
        ),
        (_CLASS + "    def check(cls, v):\n        a, b = v, 1\n        raise ValueError(f'{a}')\n", {("check", "v")}),
        (_CLASS + "    def check(cls, v):\n        assert v.startswith('p'), f'bad {v}'\n", {("check", "v")}),
        ("def _check(v):\n    raise ValueError(f'bad {v}')\n", {("_check", "v")}),
        (_CLASS + "    async def check(cls, v):\n        raise ValueError(f'bad {v}')\n", {("check", "v")}),
        (_CLASS + "    def check(cls, v):\n        raise ValueError(f'got {len(v.strip())} characters')\n", set()),
        (
            _CLASS + "    def check(cls, v):\n        n = len(v)\n        raise ValueError(f'got {n} characters')\n",
            set(),
        ),
        (_CLASS + "    def check(cls, v):\n        raise ValueError(f'at least {MIN_SECRET_KEY_LENGTH}')\n", set()),
        (_CLASS + "    def check(cls, v):\n        raise ValueError(', '.join(sorted(MODES)))\n", set()),
        (_CLASS + "    def check(cls, v):\n        raise ValueError('must be set')\n", set()),
    ],
    ids=[
        "f-string",
        "percent",
        "format",
        "self-field",
        "validation-info",
        "environment",
        "two-step",
        "mutation",
        "walrus",
        "tuple-unpacking",
        "assert",
        "module-function",
        "async",
        "length",
        "two-step-length",
        "module-constant",
        "constant-join",
        "plain",
    ],
)
def test_the_message_gate_flags_a_quoted_value(source, expected):
    assert _quotations(ast.parse(source)) == expected


def test_the_deploy_check_prints_no_secret(monkeypatch, capsys):
    # The environment and configuration checks print a secret's presence and length only. The model id and the
    # provider base URL are identifiers, not secrets, and are printed by design.
    monkeypatch.syspath_prepend(str(BACKEND_DIR / "scripts"))
    deploy_check = importlib.import_module("deploy_check")
    values = {
        "OPENAI_API_KEY": "sk-PRIVATE_OPENAI_7c1e_" + "x" * 30,
        "STRIPE_SECRET_KEY": "sk_live_PRIVATE_STRIPE_7c1e_" + "x" * 20,
        "STRIPE_WEBHOOK_SECRET": "whsec_PRIVATE_HOOK_7c1e",
        "SECRET_KEY": "PRIVATE_SIGNING_7c1e_" + "x" * MIN_SECRET_KEY_LENGTH,  # fabricated sentinel  # gitleaks:allow
        "DATABASE_URL": "postgresql://app:PRIVATE_DB_7c1e@db/app",
    }
    for name, value in values.items():
        monkeypatch.setattr(deploy_check.settings, name, value)
    deploy_check.check_environment_variables()
    deploy_check.check_configuration_validation()
    out = capsys.readouterr().out
    assert "✓ Set (" in out  # the set-and-valid branch ran
    assert "Stripe Configuration" in out  # the configuration check ran
    assert "PRIVATE_" not in out
