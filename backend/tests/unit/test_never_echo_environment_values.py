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
- `scripts/deploy_check.py` printed the first 30 characters of every value it checked, and its two
  database checks printed an error message that can quote the database password.

Not covered: the echoes the lesson lists as ungated, such as a secret copied out of the settings object
into another local or a request header, which still reaches Sentry's capture.
"""

import ast
import importlib
import json
import os
import random
import string
import sys
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
    assert (repr(settings), str(settings)) == ("Settings()", "")
    assert serialize({"vars": {"settings": settings}})["vars"]["settings"] == "Settings()"


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


def test_the_walk_reads_every_backend_file_outside_tests():
    # A new directory of backend code joins the walk or fails here. Only tests/, a virtualenv and a hidden
    # directory (a cache, a tool's state) are left out.
    def kept(path: Path) -> bool:
        top = path.relative_to(BACKEND_DIR).parts[0]
        return top.endswith(".py") or (top not in {"tests", "venv"} and not top.startswith("."))

    assert set(_scanned_files()) == {path for path in BACKEND_DIR.rglob("*.py") if kept(path)}


def test_no_caught_exception_is_serialized_with_its_input():
    handled, found = set(), []
    for path in _scanned_files():
        rel = path.relative_to(BACKEND_DIR).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(isinstance(node, ast.ExceptHandler) and node.name for node in ast.walk(tree)):
            handled.add(rel)
        found.extend(f"{rel}:{line}" for line in _structured_calls_with_input(tree))
    # The walk reaches the one handler of a settings error (deploy_check), one of a pydantic ValidationError
    # (tasks.py), an entrypoint (main.py) and the evals.
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
_MUTATORS = {"append", "extend", "insert", "add", "update", "setdefault"}


def _quoted(
    node: ast.AST, assigned: dict[str, list[ast.expr]], local: frozenset[str], seen: frozenset[str] = frozenset()
) -> set[str]:
    """What a message expression reads beyond literals, `len(...)` and names bound only to such expressions.

    Default deny: a name counts through every expression bound to it (see `_quotations`), and a name with no
    expression bound to it counts as read: a parameter such as `v` or `info`, a `with` target, an import
    (`getenv(...)`, `os.environ`), a builtin (`locals()`). An attribute counts unless it belongs to a literal
    (`", ".join`) or to a name that reads nothing. The only calls that read nothing of their own are calls of a
    name that neither the scope nor the module binds and that is an exception class (a CapWords name) or `sorted`.
    """

    def read(child: ast.AST, more: frozenset[str] = frozenset()) -> set[str]:
        return _quoted(child, assigned, local, seen | more)

    if isinstance(node, ast.Constant):
        return set()
    if isinstance(node, ast.Call):
        free = isinstance(node.func, ast.Name) and node.func.id not in local and node.func.id not in assigned
        callee = node.func.id if free else ""
        if callee == "len":
            return set()  # a length, never the value
        called = set() if callee[:1].isupper() or callee == "sorted" else read(node.func)
        return called.union(*(read(arg) for arg in [*node.args, *(keyword.value for keyword in node.keywords)]))
    if isinstance(node, ast.Name):
        if node.id in assigned and node.id not in seen:
            return set().union(*(read(expr, frozenset({node.id})) for expr in assigned[node.id]))
        return {node.id}
    if isinstance(node, ast.Attribute):
        if isinstance(node.value, ast.Constant):
            return set()  # a method of a literal, such as ", ".join
        return {ast.unparse(node)} if read(node.value) or not isinstance(node.value, ast.Name) else set()
    return set().union(*(read(child) for child in ast.iter_child_nodes(node)))


def _assignments(nodes: list[ast.AST]) -> dict[str, list[ast.expr]]:
    """Every expression the nodes bind or add to a name: tuple targets, loop variables, `:=` and mutator calls."""
    assigned: dict[str, list[ast.expr]] = {}

    def bind(target: ast.AST, expr: ast.expr) -> None:
        for name in (node for node in ast.walk(target) if isinstance(node, ast.Name)):
            assigned.setdefault(name.id, []).append(expr)

    for node in nodes:
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
            for arg in [*node.args, *(keyword.value for keyword in node.keywords)]:
                bind(node.func.value, arg)
    return assigned


def _bound(nodes: list[ast.AST]) -> set[str]:
    """Every name the nodes bind: a parameter, a store (an assignment, a loop, `with`, a comprehension, `:=`), an
    `except ... as` or an import."""
    names = set()
    for node in nodes:
        if isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((alias.asname or alias.name).split(".")[0] for alias in node.names)
    return names


def _quotations(tree: ast.Module) -> set[tuple[str, str]]:
    """(scope, what it quotes) for every raise or assert message in the module that reads a value.

    A message inside a function is read in that function's scope; one anywhere else (the module's own statements,
    a class body) in `<module>`'s. A name counts through every expression its scope binds to it or, when the scope
    binds it in no way at all, through every expression the module binds to it: `MIN_SECRET_KEY_LENGTH = 32`
    reads nothing, a module name bound to `os.environ[...]` reads the environment, and an uppercase parameter is a
    value like any other. A raise's `from` cause counts as part of its message: a traceback prints the cause too.
    """
    functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    in_a_function = {id(inner) for function in functions for inner in ast.walk(function)}
    module = [node for node in ast.walk(tree) if id(node) not in in_a_function]
    module_assigned = _assignments(module)
    scopes = [(function.name, list(ast.walk(function))) for function in functions] + [("<module>", module)]
    found = set()
    for scope, nodes in scopes:
        own = _assignments(nodes)
        local = frozenset(_bound(nodes) | set(own))
        assigned = {**{name: exprs for name, exprs in module_assigned.items() if name not in local}, **own}
        for node in nodes:
            if isinstance(node, ast.Raise):
                messages = [node.exc, node.cause]
            elif isinstance(node, ast.Assert):
                messages = [node.msg]
            else:
                continue
            for message in (message for message in messages if message is not None):
                found.update((scope, name) for name in _quoted(message, assigned, local))
    return found


def test_no_settings_message_quotes_a_value():
    # Every validator lives in config.py's one class, whose only base is pydantic-settings' own, and none is
    # attached through Annotated, whose function could live in another module, outside this walk.
    assert Settings.__bases__ == (BaseSettings,)
    tree = ast.parse((BACKEND_DIR / "app" / "config.py").read_text(encoding="utf-8"))
    used = {
        *(node.id for node in ast.walk(tree) if isinstance(node, ast.Name)),
        *(node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)),
        *(alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) for alias in node.names),
    }
    assert not used & {"Annotated", "AfterValidator", "BeforeValidator", "PlainValidator", "WrapValidator"}
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
        (
            "MIN_SECRET_KEY_LENGTH = 32\n" + _CLASS + "    def check(cls, v):\n"
            "        raise ValueError(f'at least {MIN_SECRET_KEY_LENGTH}')\n",
            set(),
        ),
        (
            "MODES = ('public', 'invite_only')\n" + _CLASS + "    def check(cls, v):\n"
            "        raise ValueError(', '.join(sorted(MODES)))\n",
            set(),
        ),
        (_CLASS + "    def check(cls, SECRET):\n        raise ValueError(f'bad {SECRET}')\n", {("check", "SECRET")}),
        (
            _CLASS + "    def check(cls, v):\n        SECRET = v\n        raise ValueError(f'bad {SECRET}')\n",
            {("check", "v")},
        ),
        (
            "MIN = 1\n" + _CLASS + "    def check(cls, MIN):\n        raise ValueError(f'bad {MIN}')\n",
            {("check", "MIN")},
        ),
        (_CLASS + "    def check(cls, v):\n        raise ValueError(f'bad {TOKEN}')\n", {("check", "TOKEN")}),
        (
            "MIN = 1\n" + _CLASS + "    def check(cls, v):\n        with open(v) as MIN:\n"
            "            raise ValueError(f'bad {MIN}')\n",
            {("check", "MIN")},
        ),
        (_CLASS + "    def check(cls, v):\n        raise ValueError(f'bad {locals()}')\n", {("check", "locals")}),
        (
            "from os import getenv\n" + _CLASS + "    def check(self):\n        raise ValueError(f'{getenv(\"K\")}')\n",
            {("check", "getenv")},
        ),
        (_CLASS + "    def check(cls, Wrap):\n        raise ValueError(Wrap())\n", {("check", "Wrap")}),
        (
            _CLASS + "    def check(cls, v):\n        d = {}\n        d.update(key=v)\n        raise ValueError(f'{d}')\n",
            {("check", "v")},
        ),
        (
            _CLASS + "    def check(cls, v):\n        d = {}\n        d.setdefault('key', v)\n"
            "        raise ValueError(f'{d}')\n",
            {("check", "v")},
        ),
        (_CLASS + "    def check(cls, v):\n        raise ValueError('bad') from ValueError(v)\n", {("check", "v")}),
        ("import os\nif os.environ:\n    raise RuntimeError(f'{os.environ}')\n", {("<module>", "os.environ")}),
        (
            "import os\nKEY = os.environ['K']\n" + _CLASS + "    def check(cls, v):\n        raise ValueError(f'bad {KEY}')\n",
            {("check", "os.environ")},
        ),
        (
            "import os\nFetch = os.environ.get\n" + _CLASS + "    def check(cls, v):\n"
            "        raise ValueError(f'bad {Fetch(\"K\")}')\n",
            {("check", "os.environ.get")},
        ),
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
        "uppercase-parameter",
        "uppercase-local",
        "shadowed-constant",
        "undefined-uppercase",
        "with-shadowed-constant",
        "bare-call",
        "bare-environment",
        "parameter-callee",
        "keyword-mutation",
        "setdefault",
        "cause",
        "module-level",
        "module-value",
        "assigned-callee",
        "plain",
    ],
)
def test_the_message_gate_flags_a_quoted_value(source, expected):
    assert _quotations(ast.parse(source)) == expected


def _fabricated(name: str) -> str:
    """A fabricated 40-character secret, the same on every run: drawn at run time, so no literal here looks like one."""
    return "".join(random.Random(name).choices(string.ascii_letters + string.digits, k=40))


def _fragments(secret: str, text: str) -> int:
    """How many of the secret's 4-character windows the text holds: a prefix, a last four or the whole value."""
    return sum(secret[i : i + 4] in text for i in range(len(secret) - 3))


def _deploy_check(monkeypatch):
    monkeypatch.syspath_prepend(str(BACKEND_DIR / "scripts"))
    return importlib.import_module("deploy_check")


def test_the_deploy_check_prints_no_secret(monkeypatch, capsys):
    # The environment and configuration checks print a secret's presence and length only. The model id and the
    # provider base URL are identifiers, not secrets, and are printed by design.
    deploy_check = _deploy_check(monkeypatch)
    names = ("OPENAI_API_KEY", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "SECRET_KEY", "DATABASE_URL")
    secrets = {name: _fabricated(name) for name in names}
    values = {
        "OPENAI_API_KEY": "sk-" + secrets["OPENAI_API_KEY"],
        "STRIPE_SECRET_KEY": "sk_live_" + secrets["STRIPE_SECRET_KEY"],
        "STRIPE_WEBHOOK_SECRET": "whsec_" + secrets["STRIPE_WEBHOOK_SECRET"],
        "SECRET_KEY": secrets["SECRET_KEY"],
        "DATABASE_URL": f"postgresql://app:{secrets['DATABASE_URL']}@db/app",
    }
    for name, value in values.items():
        monkeypatch.setattr(deploy_check.settings, name, value)
    deploy_check.check_environment_variables()
    deploy_check.check_configuration_validation()
    out = capsys.readouterr().out
    assert "✓ Set (" in out  # the set-and-valid branch ran
    assert "Stripe Configuration" in out  # the configuration check ran
    leaked = sum(_fragments(secret, out) for secret in secrets.values())
    assert not leaked, f"{leaked} four-character fragments of a fabricated secret reached the output"


def test_the_deploy_check_database_checks_print_no_secret(monkeypatch, capsys):
    # A URL missing its `@host` puts the password where the port goes, and the int() that parses the port quotes
    # it in the error both database checks catch. app.database is dropped from the module cache, so each check
    # imports it afresh and its create_engine reads this URL; the cache entry and the package attribute are
    # restored afterwards.
    deploy_check = _deploy_check(monkeypatch)
    password = _fabricated("DATABASE_URL password")
    monkeypatch.setattr(deploy_check.settings, "DATABASE_URL", f"postgresql://app:{password}/app")
    app_package = importlib.import_module("app")
    monkeypatch.setattr(app_package, "database", getattr(app_package, "database", None), raising=False)
    monkeypatch.delitem(sys.modules, "app.database", raising=False)
    assert deploy_check.check_database() is False
    deploy_check.check_phase2_alerts()
    out = capsys.readouterr().out
    assert out.count("(message withheld: it can quote DATABASE_URL)") == 2  # both handlers caught the error
    leaked = _fragments(password, out)
    assert not leaked, f"{leaked} four-character fragments of the fabricated password reached the output"
