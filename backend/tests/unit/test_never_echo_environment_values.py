"""A settings secret never reaches an output (rule 12; CODE RED records 22 and 23; #1281;
lessons/ops-never-echo-environment-values.md).

pydantic appends each failing field's input to its error message (`input_value=...`), and a missing
required field's input is the whole environment-derived settings dict. Without
`hide_input_in_errors`, a settings validation error printed environment values, secrets included,
into whatever output carried it: a service's startup log, CI's public log, or an agent's own tool
output (CODE RED records 22 and 23 each disclose one such echo). Two reviews found the other routes,
each gated here:

- the setting covers the error's rendered text only (`str`, `repr`, so a traceback or a log line);
  its structured form, `errors()` and `json()`, still returns each input unless called with
  `include_input=False`, so every `except` block that calls them must pass it;
- a settings object's repr carried every value;
- a raise or assert message in app/config.py can quote a value (the message walk), and an error a library
  raises inside a validator (a URL or port parse) prints whole: every field is fed values shaped to break
  such a parse;
- `scripts/deploy_check.py`, `scripts/smoke_resend.py` and `scripts/validate_db_performance.py` printed
  characters of the secrets they handled, and a database or Redis URL parser's message can quote the password
  (`app/database.py` at import, the Redis pool);
- an Alpha Vantage HTTP error's message, and httpx's request log in the calendar job and in the service, quote its
  keyed URL, and the client logged the head of a throttle notice, which can quote the key;
- Sentry serialized every captured frame's local variables (a secret copied into a local, every library frame
  holding a request, the database driver's connect arguments), the `X-Internal-Token` header and each outbound
  request's query string, and the exact-name scrubber left a request body's credential keys (a password change's
  passwords, a refresh token, an invite, Apple's form-posted code and id_token); the compare_digest checks raised on a
  non-ASCII value, a 500 whose frame held the secret;
- that scrubber matches key names, so a secret's value quoted inside a value (a message, an exception, a breadcrumb, an
  extra, a tag, a context, a user, a request, a span, a log or a metric) still reached Sentry, a malformed
  DATABASE_URL's digits among them, which the driver quotes as the port: main's hooks withhold each secret setting's
  whole value and each connection URL's password on every channel that carries text (through str's own `replace`,
  which a text subclass cannot override), and a hook that fails sends nothing;
- and, for every route at once, no output call (a print, log, warn or write call, `click.echo`, `pprint`, a Sentry
  message, exception, event, tag or tags, context, extra, user, breadcrumb, or span data or attribute) and no raise or
  assert message in the backend reads a secret directly, from the settings object or the environment, and every
  credential a request body names is scrubbed.

Not covered: the echoes the lesson lists as ungated.
"""

import ast
import asyncio
import importlib
import json
import logging
import os
import random
import re
import string
import sys
import traceback
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from pydantic import ValidationError, field_validator
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


class _Parsing(Settings):
    """The control for the per-field test: validators whose library call quotes its input, as a URL's port parse
    does, one on every value and one only past a scheme check, so the malformed values are shown to reach both calls
    and their messages are shown to print whole."""

    @field_validator("DATABASE_URL")
    @classmethod
    def _port(cls, v):
        urlsplit(v).port
        return v

    @field_validator("REDIS_URL")
    @classmethod
    def _checked_port(cls, v):
        if v.startswith(("redis://", "rediss://")):
            urlsplit(v).port
        return v


# Shaped to break what a validator would parse: the value alone, a URL whose missing `@host` puts the password where
# the port goes, a URL whose every part is the value, and a host:port pair.
_MALFORMED = ("{s}", "postgresql://app:{s}/db", "https://{s}@{s}:{s}/", "{s}:{s}")
# A validator that parses only past a prefix or scheme check is reached only by a value carrying it: the value behind
# every prefix app/config.py checks with `startswith` and every prefix a credential carries, and a URL of every scheme
# a field's default or a connection uses with the value where the port goes.


def _checked_prefixes() -> tuple[set[str], list[str]]:
    """Every prefix app/config.py checks a value's start against, a literal or a module constant bound to literals;
    and each `startswith` argument that is neither, which the harvest cannot read."""
    tree = ast.parse((BACKEND_DIR / "app" / "config.py").read_text(encoding="utf-8"))
    constants = {
        target.id: node.value
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None
        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        if isinstance(target, ast.Name)
    }
    prefixes, unreadable = set(), []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "startswith":
            argument = node.args[0] if node.args else None
            value = constants.get(argument.id) if isinstance(argument, ast.Name) else argument
            items = value.elts if isinstance(value, ast.Tuple) else [value]
            if all(isinstance(item, ast.Constant) and isinstance(item.value, str) for item in items):
                prefixes |= {item.value for item in items}
            else:
                unreadable.append(ast.unparse(node))
    return prefixes, unreadable


_CHECKED_PREFIXES = _checked_prefixes()[0]
_SCHEMES = {
    str(field.default).split("://")[0] for field in Settings.model_fields.values() if "://" in str(field.default)
}
_PREFIXED = tuple(
    sorted(
        {f"{prefix}{{s}}" for prefix in _CHECKED_PREFIXES | {"sk_live_", "whsec_", "re_"}}
        | {f"{prefix}default:{{s}}/0" for prefix in _CHECKED_PREFIXES if prefix.endswith("://")}
        | {f"{scheme}://default:{{s}}/0" for scheme in _SCHEMES | {"postgresql", "postgres", "rediss"}}
    )
)


def _construction_error(model: type[Settings], **values: str) -> str:
    """The full traceback text, chained exceptions included, of building the model from these values; empty if none."""
    try:
        model(_env_file=None, **{"SECRET_KEY": _fabricated("SECRET_KEY"), **values})
    except Exception as exc:  # a ValidationError, or a ValueError raised by __init__
        return "".join(traceback.format_exception(exc))
    return ""


def test_a_validators_library_message_prints_whole():
    # hide_input_in_errors hides the input pydantic appends, not the message of an error raised inside a validator.
    assert SHORT_SENTINEL in _construction_error(_Parsing, DATABASE_URL=_MALFORMED[1].format(s=SHORT_SENTINEL))
    # A parse past a scheme check is reached by a shape carrying the scheme, and by no generic shape.
    quoted = [
        shape
        for shape in (*_MALFORMED, *_PREFIXED)
        if SHORT_SENTINEL in _construction_error(_Parsing, REDIS_URL=shape.format(s=SHORT_SENTINEL))
    ]
    assert quoted == ["redis://default:{s}/0", "rediss://default:{s}/0"]
    assert {"promo_", "sk_live_", "sqlite"} <= _CHECKED_PREFIXES and {"redis", "sqlite", "https"} <= _SCHEMES


def test_the_prefix_harvest_reads_every_startswith():
    # A prefix the harvest cannot read (a call, an attribute, a name bound to anything but literals) would leave a
    # parse behind it unreached; such a check fails here instead.
    assert _checked_prefixes()[1] == []


@pytest.mark.parametrize("field", sorted(set(Settings.model_fields) - {"REGISTRATION_MODE"}))
def test_no_field_error_quotes_a_malformed_value(field):
    # REGISTRATION_MODE quotes its value by design (QUOTES_ITS_VALUE).
    for shape in (*_MALFORMED, *_PREFIXED):
        text = _construction_error(Settings, **{field: shape.format(s=SHORT_SENTINEL)})
        assert SHORT_SENTINEL not in text, f"An error for {field}={shape!r} quotes the value"


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


def _kept(path: Path, root: Path = BACKEND_DIR) -> bool:
    """Whether the walk must read a Python file: all but tests/, a hidden directory (a cache, a tool's state) and a
    virtualenv, whatever its name (a directory holding a pyvenv.cfg)."""
    top = path.relative_to(root).parts[0]
    if top.endswith(".py"):
        return True
    return top not in {"tests", "venv"} and not top.startswith(".") and not (root / top / "pyvenv.cfg").is_file()


def test_the_walk_reads_every_backend_file_outside_tests():
    # A new directory of backend code joins the walk or fails here.
    assert set(_scanned_files()) == {path for path in BACKEND_DIR.rglob("*.py") if _kept(path)}


def test_the_walk_skips_a_virtualenv_by_its_marker(tmp_path):
    for name in ("env/pyvenv.cfg", "env/lib/site.py", "newcode/module.py", "entry.py"):
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text("")
    kept = {path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*.py") if _kept(path, tmp_path)}
    assert kept == {"newcode/module.py", "entry.py"}


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
_CONTAINERS = (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)


def _quoted(
    node: ast.AST, assigned: dict[str, list[ast.expr]], local: frozenset[str], seen: frozenset[str] = frozenset()
) -> set[str]:
    """What a message expression reads beyond literals, `len(...)` and names bound only to such expressions.

    Default deny: a name counts through every expression bound to it (see `_quotations`), and a name with no
    expression bound to it counts as read: a parameter such as `v` or `info`, a builtin (`locals()`), and every name
    an import, a def, a class, `except ... as`, `with ... as` or a match capture binds, which reads itself
    (`getenv(...)`, `os.environ`, `Settings()`). An attribute counts unless it belongs to a literal (`", ".join`) or
    to a name that reads nothing. The only calls that read nothing of their own are calls of a builtin exception
    class (a CapWords name neither the scope nor the module binds) and of `sorted`.
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


def _non_expression_bindings(node: ast.AST) -> list[str]:
    """The names a node binds to something that is not an expression: a parameter, an import, a def, a class,
    `except ... as`, `with ... as`, a match capture. A store into a parameter (`self.cache = 1`, `info.data[k] = 1`,
    `v.append(1)`, `v += ''`) adds to what it holds and never replaces the caller's value."""
    if isinstance(node, ast.arg):
        return [node.arg]
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return [(alias.asname or alias.name).split(".")[0] for alias in node.names]
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [node.name]
    if isinstance(node, ast.withitem) and node.optional_vars is not None:
        return [name.id for name in ast.walk(node.optional_vars) if isinstance(name, ast.Name)]
    if isinstance(node, ast.MatchMapping):
        return [node.rest] if node.rest else []
    if isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)):
        return [node.name] if node.name else []
    return []


def _assignments(nodes: list[ast.AST]) -> dict[str, list[ast.expr]]:
    """Every expression the nodes bind or add to a name: tuple targets, loop variables, `:=` and mutator calls. A
    name bound to something that is not an expression (`_non_expression_bindings`), or to a list, dict or set, is
    bound to itself too, so it reads itself wherever it is read, a call of it included: a container can be filled
    through an alias, a helper it is handed to or a dunder call, none of which the walk follows."""
    assigned: dict[str, list[ast.expr]] = {}

    def bind(target: ast.AST, expr: ast.expr) -> None:
        for name in (node for node in ast.walk(target) if isinstance(node, ast.Name)):
            assigned.setdefault(name.id, []).append(expr)
            if isinstance(expr, _CONTAINERS):  # an alias, a helper or a dunder call can fill it unseen
                assigned[name.id].append(ast.Name(id=name.id, ctx=ast.Load()))

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
        for name in _non_expression_bindings(node):
            assigned.setdefault(name, []).append(ast.Name(id=name, ctx=ast.Load()))
    return assigned


def _bound(nodes: list[ast.AST]) -> set[str]:
    """Every name the nodes bind: a store (an assignment, a loop, `with`, a comprehension, `:=`) and every
    non-expression binding (`_non_expression_bindings`), a parameter included."""
    names = set()
    for node in nodes:
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        names.update(_non_expression_bindings(node))
    return names


def _quotations(tree: ast.Module) -> set[tuple[str, str]]:
    """(scope, what it quotes) for every raise or assert message in the module that reads a value.

    A message inside a function is read in that function's scope; one anywhere else (the module's own statements,
    a class body) in `<module>`'s. A name counts through every expression its scope binds to it or, when the scope
    binds it in no way at all, through every expression the module binds to it: `MIN_SECRET_KEY_LENGTH = 32`
    reads nothing, a module name bound to `os.environ[...]` reads the environment, `settings = Settings()` reads
    the class, and an uppercase parameter is a value like any other. A module name that a function stores into or
    mutates without binding it (a `global` store, `NAME[key] = ...`, `NAME.append(...)`) holds whatever that
    function put there, so it reads itself everywhere. A raise's `from` cause counts as part of its message: a
    traceback prints the cause too. So does, for a raise without `from` in an `except` or `finally` block, the
    exception being handled, which the new one chains implicitly: only `from None` drops it.
    """
    functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    # A def belongs to the scope that holds it, so the module keeps its own defs' names but not their insides.
    in_a_function = {id(inner) for function in functions for inner in ast.walk(function) if inner is not function}
    module = [node for node in ast.walk(tree) if id(node) not in in_a_function]
    module_assigned = _assignments(module)
    for function in functions:
        nodes = list(ast.walk(function))
        declared = {name for node in nodes if isinstance(node, (ast.Global, ast.Nonlocal)) for name in node.names}
        for name in set(_assignments(nodes)) - (_bound(nodes) - declared):
            module_assigned.setdefault(name, []).append(ast.Name(id=name, ctx=ast.Load()))
    scopes = [(function.name, list(ast.walk(function))) for function in functions] + [("<module>", module)]
    found = set()
    for scope, nodes in scopes:
        own = _assignments(nodes)
        local = frozenset(_bound(nodes) | set(own))
        assigned = {**{name: exprs for name, exprs in module_assigned.items() if name not in local}, **own}
        handling = {
            id(inner)
            for node in nodes
            if isinstance(node, (ast.ExceptHandler, ast.Try, ast.TryStar))
            for statement in (node.body if isinstance(node, ast.ExceptHandler) else node.finalbody)
            for inner in ast.walk(statement)
        }
        for node in nodes:
            if isinstance(node, ast.Raise) and node.cause is None and id(node) in handling:
                found.add((scope, "<the exception being handled>"))  # chained implicitly; a traceback prints it
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
            {("check", "parts"), ("check", "v")},
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
            _CLASS
            + "    def check(cls, v):\n        d = {}\n        d.update(key=v)\n        raise ValueError(f'{d}')\n",
            {("check", "d"), ("check", "v")},
        ),
        (
            _CLASS + "    def check(cls, v):\n        d = {}\n        d.setdefault('key', v)\n"
            "        raise ValueError(f'{d}')\n",
            {("check", "d"), ("check", "v")},
        ),
        (_CLASS + "    def check(cls, v):\n        raise ValueError('bad') from ValueError(v)\n", {("check", "v")}),
        ("import os\nif os.environ:\n    raise RuntimeError(f'{os.environ}')\n", {("<module>", "os.environ")}),
        (
            "import os\nKEY = os.environ['K']\n"
            + _CLASS
            + "    def check(cls, v):\n        raise ValueError(f'bad {KEY}')\n",
            {("check", "os.environ")},
        ),
        (
            "import os\nFetch = os.environ.get\n" + _CLASS + "    def check(cls, v):\n"
            "        raise ValueError(f'bad {Fetch(\"K\")}')\n",
            {("check", "os.environ.get")},
        ),
        (
            "_P = []\n" + _CLASS + "    def a(cls, v):\n        _P.append(v)\n"
            "    def b(cls, w):\n        raise ValueError(', '.join(_P))\n",
            {("b", "_P")},
        ),
        (
            "_k = ''\n" + _CLASS + "    def a(self):\n        global _k\n        _k = self.SECRET_KEY\n"
            "    def b(cls, w):\n        raise ValueError(_k)\n",
            {("b", "_k")},
        ),
        (
            "_s = {}\n" + _CLASS + "    def a(self):\n        _s['k'] = self.SECRET_KEY\n"
            "    def b(cls, w):\n        raise ValueError(_s.get('k'))\n",
            {("b", "_s.get")},
        ),
        (
            _CLASS + "    pass\nsettings = Settings()\ndef f():\n    raise ValueError(settings.SECRET_KEY)\n",
            {("f", "settings.SECRET_KEY")},
        ),
        (
            _CLASS + "    pass\nsettings = Settings()\nassert settings, f'{settings.SECRET_KEY}'\n",
            {("<module>", "settings.SECRET_KEY")},
        ),
        (
            "from os import getenv as Env\n" + _CLASS + "    def check(cls, v):\n        raise ValueError(Env('K'))\n",
            {("check", "Env")},
        ),
        (
            "class ConfigError(ValueError):\n    pass\n" + _CLASS + "    def check(cls, v):\n"
            "        raise ConfigError('must be set')\n",
            {("check", "ConfigError")},
        ),
        (
            "def Leak():\n    return 1\n" + _CLASS + "    def check(cls, v):\n        raise ValueError(f'{Leak()}')\n",
            {("check", "Leak")},
        ),
        (
            "try:\n    from dotenv import dotenv_values\nexcept ImportError:\n    dotenv_values = None\n"
            + _CLASS
            + "    def check(cls, v):\n        raise ValueError(dotenv_values('.env'))\n",
            {("check", "dotenv_values")},
        ),
        (
            "_SEEN = []\ndef _keep(bucket, value):\n    bucket.append(value)\n" + _CLASS + "    def a(self):\n"
            "        _keep(_SEEN, self.SECRET_KEY)\n    def b(cls, w):\n        raise ValueError(f'{_SEEN}')\n",
            {("b", "_SEEN")},
        ),
        (
            "_P = []\n" + _CLASS + "    def a(self):\n        alias = _P\n        alias.append(self.SECRET_KEY)\n"
            "    def b(cls, w):\n        raise ValueError(', '.join(_P))\n",
            {("b", "_P")},
        ),
        (
            "_D = {}\n" + _CLASS + "    def a(self):\n        _D.__setitem__('k', self.SECRET_KEY)\n"
            "    def b(cls, w):\n        raise ValueError(f'{_D}')\n",
            {("b", "_D")},
        ),
        (
            _CLASS + "    def __init__(self):\n        try:\n            int(self.DATABASE_URL)\n"
            "        except ValueError:\n            raise ValueError('DATABASE_URL is malformed')\n",
            {("__init__", "<the exception being handled>")},
        ),
        (
            _CLASS
            + "    def check(cls, v):\n        try:\n            int(v)\n        except ValueError:\n            raise\n",
            {("check", "<the exception being handled>")},
        ),
        (
            _CLASS + "    def __init__(self):\n        try:\n            int(self.DATABASE_URL)\n"
            "        except ValueError:\n            raise ValueError('DATABASE_URL is malformed') from None\n",
            set(),
        ),
        (
            _CLASS + "    def check(self):\n        self.cache = 1\n        raise ValueError(f'{self.SECRET_KEY}')\n",
            {("check", "self.SECRET_KEY")},
        ),
        (
            _CLASS + "    def check(cls, v, info):\n        info.data['seen'] = 1\n"
            "        raise ValueError(f\"{info.data['SECRET_KEY']}\")\n",
            {("check", "info.data")},
        ),
        (_CLASS + "    def check(cls, v):\n        v.append(1)\n        raise ValueError(f'{v}')\n", {("check", "v")}),
        (_CLASS + "    def check(cls, v):\n        v += ''\n        raise ValueError(v)\n", {("check", "v")}),
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
        "cross-scope-append",
        "global-rebind",
        "cross-scope-store",
        "singleton-field",
        "singleton-field-module-assert",
        "capwords-import-alias",
        "module-exception-class",
        "module-def-callee",
        "import-with-fallback",
        "helper-fills-module-list",
        "aliased-module-list",
        "dunder-setitem",
        "implicit-chaining",
        "bare-reraise",
        "chaining-suppressed",
        "parameter-attribute-store",
        "parameter-subscript-store",
        "parameter-mutation",
        "parameter-augmented",
        "plain",
    ],
)
def test_the_message_gate_flags_a_quoted_value(source, expected):
    assert _quotations(ast.parse(source)) == expected


def _fabricated(name: str, alphabet: str = string.ascii_letters + string.digits) -> str:
    """A fabricated 40-character secret, the same on every run: drawn at run time, so no literal here looks like one."""
    return "".join(random.Random(name).choices(alphabet, k=40))


def _fragments(secret: str, text: str, width: int = 4) -> int:
    """How many of the secret's `width`-character windows the text holds: a prefix, a last four or the whole value."""
    return sum(secret[i : i + width] in text for i in range(len(secret) - width + 1))


def _deploy_check(monkeypatch):
    monkeypatch.syspath_prepend(str(BACKEND_DIR / "scripts"))
    return importlib.import_module("deploy_check")


@pytest.mark.parametrize(
    ("environment", "length", "stripe_modes", "branches"),
    [
        ("development", 40, ("sk_live_", "pk_live_"), ("✓ Set (", "LIVE key (sk_live_) outside production")),
        ("development", 12, ("", ""), ("is set but invalid", "OPENAI_API_KEY appears too short (length: 15)")),
        (
            "production",
            40,
            ("sk_test_", "pk_live_"),
            ("TEST key (sk_test_) but ENVIRONMENT=production", "different modes"),
        ),
    ],
    ids=["long-keys", "short-keys", "production-test-key"],
)
def test_the_deploy_check_prints_no_secret(monkeypatch, capsys, environment, length, stripe_modes, branches):
    # The environment and configuration checks print a secret's presence and length only, on every branch: a valid
    # key, a key too short, and a key in the wrong mode. The model id and the provider base URL are identifiers, not
    # secrets, and are printed by design.
    deploy_check = _deploy_check(monkeypatch)
    names = ("OPENAI_API_KEY", "STRIPE_SECRET_KEY", "STRIPE_PUBLISHABLE_KEY", "STRIPE_WEBHOOK_SECRET", "SECRET_KEY")
    secrets = {name: _fabricated(name)[:length] for name in (*names, "DATABASE_URL")}
    values = {
        "ENVIRONMENT": environment,
        "OPENAI_API_KEY": "sk-" + secrets["OPENAI_API_KEY"],
        "STRIPE_SECRET_KEY": stripe_modes[0] + secrets["STRIPE_SECRET_KEY"],
        "STRIPE_PUBLISHABLE_KEY": stripe_modes[1] + secrets["STRIPE_PUBLISHABLE_KEY"],
        "STRIPE_WEBHOOK_SECRET": "whsec_" + secrets["STRIPE_WEBHOOK_SECRET"],
        "SECRET_KEY": secrets["SECRET_KEY"],
        "DATABASE_URL": f"postgresql://app:{secrets['DATABASE_URL']}@db/app",
    }
    for name, value in values.items():
        monkeypatch.setattr(deploy_check.settings, name, value)
    deploy_check.check_environment_variables()
    deploy_check.check_configuration_validation()
    out = capsys.readouterr().out
    assert "Stripe Configuration" in out  # the configuration check ran
    for branch in branches:
        assert branch in out  # the branch under test ran
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


@pytest.fixture
def sentry_envelopes():
    # main.py's own options, with a fabricated DSN, a transport that keeps each envelope item instead of sending it (with
    # the envelope's and each item's headers, and each lost item's reason and category as a "lost" item; it reads the
    # DSN as the SDK's own does, so the dynamic sampling context carries its public key), every transaction sampled (a
    # transaction carries the request too), no profiler thread and a fixed release (none would run `git rev-parse`).
    # The integrations stay installed in this process and pass every call through once the client is removed.
    import sentry_sdk
    from sentry_sdk.transport import Transport

    import main

    dsn = "https://fabricated@sentry.invalid/1"

    class Keep(Transport):
        def __init__(self):
            super().__init__({"dsn": dsn})
            self.items = []

        def capture_envelope(self, envelope):
            self.items.append(("headers", envelope.headers))  # the trace header names the transaction
            for item in envelope.items:
                self.items.append(("item_headers", item.headers))
                if item.payload.json:
                    self.items.append((item.type, item.payload.json))
                else:  # an attachment's bytes, which no hook sees, as text the leak checks read
                    self.items.append((item.type, item.payload.get_bytes().decode("utf-8", "replace")))

        def record_lost_event(self, reason, data_category=None, item=None, *, quantity=1):
            self.items.append(("lost", [reason, data_category]))

    options = main._sentry_options()
    assert options["include_local_variables"] is False and options["send_default_pii"] is False
    # data_collection would drop the event scrubber and bring frame variables back whatever the two options above say
    # (sentry_sdk/client.py, _get_options; sentry_sdk/utils.py, serialize_frame).
    assert "data_collection" not in options and "data_collection" not in options.get("_experiments", {})
    # Span streaming (trace_lifecycle="stream") sends request headers as span attributes, unscrubbed.
    assert "trace_lifecycle" not in options and "trace_lifecycle" not in options.get("_experiments", {})
    # Continuous profiling sends profile chunks, which pass no hook either; main samples transaction profiles only.
    assert not {"profile_session_sample_rate", "profile_lifecycle"} & (
        set(options) | set(options.get("_experiments", {}))
    )
    keep = Keep()
    options.update(dsn=dsn, transport=keep, release="gate")
    options.update(traces_sample_rate=1.0, profiles_sample_rate=None)
    sentry_sdk.init(**options)
    try:
        # The serializer runs before before_send and before_send_transaction and would cut each string at
        # max_value_length (main's options or an SDK default): a cut inside a secret leaves a prefix that no hook matches.
        assert sentry_sdk.get_client().options["max_value_length"] is None
        with sentry_sdk.isolation_scope():  # no breadcrumb or tag left by another test
            yield keep.items
    finally:
        sentry_sdk.get_client().close()
        sentry_sdk.get_global_scope().set_client(None)


def _sentry_inits(tree: ast.Module) -> list[str]:
    """Each call of sentry_sdk's `init` in the module, through any import of it: the package or any of its modules
    under any name (`sentry_sdk.init`, `sdk.api.init`, `api.init`), or `init` imported from either under any name."""
    modules, functions = {"sentry_sdk"}, set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules |= {
                alias.asname or alias.name.split(".")[0]
                for alias in node.names
                if alias.name.split(".")[0] == "sentry_sdk"
            }
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "sentry_sdk":
            functions |= {alias.asname or alias.name for alias in node.names if alias.name == "init"}
            modules |= {alias.asname or alias.name for alias in node.names if alias.name != "init"}

    def is_init(function: str) -> bool:
        return function in functions or (function.endswith(".init") and function.split(".")[0] in modules)

    return [
        ast.unparse(node) for node in ast.walk(tree) if isinstance(node, ast.Call) and is_init(ast.unparse(node.func))
    ]


def test_main_passes_sentry_only_its_options():
    # The fixture checks what `_sentry_options` returns; a keyword added at the call itself (`data_collection`, a hook)
    # or a second init anywhere else would escape it, so the backend's one init call is main.py's, and it takes those
    # options and nothing else.
    found = [
        f"{path.relative_to(BACKEND_DIR).as_posix()}: {call}"
        for path in _scanned_files()
        for call in _sentry_inits(ast.parse(path.read_text(encoding="utf-8")))
    ]
    assert found == ["main.py: sentry_sdk.init(**_sentry_options())"]


@pytest.mark.parametrize(
    "source",
    [
        "import sentry_sdk as sdk\nsdk.init(dsn=x)",
        "from sentry_sdk import init as start\nstart(dsn=x)",
        "from sentry_sdk import init\ninit(dsn=x)",
        "from sentry_sdk.api import init as start\nstart(dsn=x)",
        "import sentry_sdk\nsentry_sdk.api.init(dsn=x)",
        "from sentry_sdk import api\napi.init(dsn=x)",
        "import sentry_sdk.api as sdk_api\nsdk_api.init(dsn=x)",
    ],
    ids=[
        "module-alias",
        "function-alias",
        "function",
        "submodule-function",
        "submodule-path",
        "submodule",
        "submodule-alias",
    ],
)
def test_the_sentry_init_scan_follows_imports(source):
    assert _sentry_inits(ast.parse(source)) == [source.splitlines()[1]]


def _of(items: list, kind: str) -> list[dict]:
    return [payload for item_type, payload in items if item_type == kind]


def test_sentry_sends_no_internal_token(monkeypatch, sentry_envelopes):
    # An /internal/ request holds the token in its X-Internal-Token header, which rides on its transaction and on every
    # error captured in its scope, a background job's error logged after the 202 included; and a captured frame
    # holds it in a plain local copied out of `settings` and in every library frame holding the request (its ASGI
    # scope, its headers). Uppercase letters and 8-character windows: no window occurs by chance in a hex id or in a
    # source line Sentry sends.
    import sentry_sdk
    from fastapi.testclient import TestClient

    import main
    from app.routers import internal

    token = _fabricated("INTERNAL_JOB_TOKEN", string.ascii_uppercase)

    async def failing_enqueue(job, arguments=None):
        copied = internal.settings.INTERNAL_JOB_TOKEN  # noqa: F841 — a plain local holding the secret
        raise RuntimeError("queue unavailable")

    async def failing_scan(db):
        raise RuntimeError("scan failed")

    monkeypatch.setattr(internal.settings, "INTERNAL_JOB_TOKEN", token)
    monkeypatch.setattr(internal, "enqueue_internal_job", failing_enqueue)
    monkeypatch.setattr(internal.filing_scan_service, "run_filing_scan", failing_scan)
    client = TestClient(main.app, raise_server_exceptions=False)
    monkeypatch.setattr(internal.settings, "DURABLE_TASKS_ENABLED", True)  # the enqueue fails inside the request
    assert client.post("/internal/jobs/filing-scan", headers={"X-Internal-Token": token}).status_code == 500
    monkeypatch.setattr(internal.settings, "DURABLE_TASKS_ENABLED", False)  # the job fails after the response
    assert client.post("/internal/jobs/filing-scan", headers={"X-Internal-Token": token}).status_code == 202
    # A non-ASCII header (Starlette decodes headers as latin-1) is a wrong token, not a TypeError and a 500.
    assert client.post("/internal/jobs/filing-scan", headers={"X-Internal-Token": b"\xe9"}).status_code == 401
    sentry_sdk.flush()
    events, transactions = _of(sentry_envelopes, "event"), _of(sentry_envelopes, "transaction")
    assert any("queue unavailable" in json.dumps(event) for event in events)  # the 500 was sent, stack and all
    assert any(event.get("logger") == "app.routers.internal" for event in events)  # so was the job's logged error
    assert len(transactions) == 3
    for payload in (*events, *transactions):
        assert payload["request"]["headers"]["x-internal-token"] == "[Filtered]"  # attached, then withheld
    sent = json.dumps(sentry_envelopes)
    assert '"vars"' not in sent  # no frame's local variables
    leaked = _fragments(token, sent, width=8)
    assert not leaked, f"{leaked} eight-character fragments of the fabricated token reached Sentry"


def test_sentry_sends_no_credential_from_a_request_body(sentry_envelopes):
    # The FastAPI integration attaches a request body, JSON or form, to the request's error event and to its sampled
    # transaction, and the scrubber matches exact key names: `password` and `token` were withheld, but a password
    # change's `new_password` and `current_password`, a `refresh_token`, an `invite` or `invite_code`, and Apple's
    # form-posted `code` and `id_token` were not.
    import sentry_sdk
    from fastapi import FastAPI, Form
    from fastapi.testclient import TestClient

    credential = _fabricated("a user's credential", string.ascii_uppercase)
    app = FastAPI()

    @app.post("/reset")
    async def reset(body: dict):
        raise RuntimeError("database down")

    @app.post("/apple")
    async def apple(code: str = Form(None), id_token: str = Form(None), state: str = Form(None)):
        raise RuntimeError("database down")

    names = ("new_password", "current_password", "password", "token", "refresh_token", "invite", "invite_code")
    body = dict.fromkeys(names, credential)
    form = {"code": credential, "id_token": credential}
    client = TestClient(app, raise_server_exceptions=False)
    assert client.post("/reset", json=body).status_code == 500
    assert client.post("/apple", data={**form, "state": "fabricated-state"}).status_code == 500
    sentry_sdk.flush()
    events, transactions = _of(sentry_envelopes, "event"), _of(sentry_envelopes, "transaction")
    assert len(events) == 2 and len(transactions) == 2
    data = [event["request"]["data"] for event in events]
    assert dict.fromkeys(body, "[Filtered]") in data  # the JSON body was attached, then withheld
    assert {**dict.fromkeys(form, "[Filtered]"), "state": "fabricated-state"} in data  # so was the form
    leaked = _fragments(credential, json.dumps(sentry_envelopes), width=8)
    assert not leaked, f"{leaked} eight-character fragments of the fabricated credential reached Sentry"


# Body keys whose names match a credential's but which carry none: a referral code is shared by design.
_NOT_CREDENTIALS = {"referral_code"}


def _body_keys(schema: dict, components: dict, depth: int = 0, seen: frozenset = frozenset()) -> set[tuple[str, int]]:
    """Each property a request body schema names, with its depth below the body's top-level object (a list's items
    count as nested), through references and unions."""
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        if name in seen:
            return set()
        schema, seen = components[name], seen | {name}
    properties = schema.get("properties", {})
    keys = {(name, depth) for name in properties}
    for sub in properties.values():
        keys |= _body_keys(sub, components, depth + 1, seen)
    for sub in (*schema.get("anyOf", []), *schema.get("oneOf", []), *schema.get("allOf", [])):
        keys |= _body_keys(sub, components, depth, seen)
    if "items" in schema:
        keys |= _body_keys(schema["items"], components, depth + 1, seen)
    return keys


def test_every_credential_in_a_request_body_is_withheld():
    # The scrubber matches exact key names at the top of a body only (it is not recursive): a new body key naming a
    # credential (`reset_code`, `api_token`) would reach Sentry with the request's error and its sampled transaction
    # unless the denylist names it, and a nested one would reach it anyway.
    import main

    spec = main.app.openapi()
    components = spec.get("components", {}).get("schemas", {})
    keys = {
        key
        for operations in spec["paths"].values()
        for operation in operations.values()
        for content in operation.get("requestBody", {}).get("content", {}).values()
        for key in _body_keys(content["schema"], components)
    }
    credentials = {
        (name, depth)
        for name, depth in keys
        if re.search("password|token|secret|invite|code|key|otp|nonce|credential", name.lower())
        and name not in _NOT_CREDENTIALS
    }
    assert {("new_password", 0), ("refresh_token", 0), ("invite", 0), ("id_token", 0)} <= credentials  # JSON and form
    denylist = set(main._sentry_options()["event_scrubber"].denylist)
    exposed = sorted(f"{name} (depth {depth})" for name, depth in credentials if depth or name.lower() not in denylist)
    assert not exposed, f"Request body credentials Sentry would receive: {exposed}. Add each to main._sentry_options."


def test_the_body_walk_follows_references_unions_and_lists():
    components = {
        "Login": {"properties": {"password": {}, "profile": {"$ref": "#/components/schemas/Profile"}}},
        "Profile": {"properties": {"api_key": {}, "owner": {"$ref": "#/components/schemas/Login"}}},
    }
    schema = {
        "anyOf": [{"$ref": "#/components/schemas/Login"}, {"type": "array", "items": {"properties": {"otp": {}}}}]
    }
    assert _body_keys(schema, components) == {("password", 0), ("profile", 0), ("api_key", 1), ("owner", 1), ("otp", 1)}


def _alpha_vantage(monkeypatch, status: int, body: str = "", alphabet: str = string.ascii_letters + string.digits):
    """The real client, its key fabricated, its requests answered in-process with this status and body (`{key}` in
    the body stands for the fabricated key)."""
    import httpx

    from app.integrations import alpha_vantage

    key = _fabricated("ALPHA_VANTAGE_API_KEY", alphabet)
    text = body.replace("{key}", key)
    transport = httpx.MockTransport(lambda request: httpx.Response(status, text=text, request=request))
    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real_client(transport=transport, **kwargs))
    return alpha_vantage.AlphaVantageClient(api_key=key), key


def test_sentry_sends_no_outbound_query(monkeypatch, sentry_envelopes):
    # Sentry's httpx integration records each outbound request's query string unsanitized, on its breadcrumb (sent
    # with the next error) and on its span (sent with a sampled transaction), and Alpha Vantage's query carries the key.
    import sentry_sdk

    client, key = _alpha_vantage(monkeypatch, 200, "symbol,reportDate\n", string.ascii_uppercase)
    with sentry_sdk.start_transaction(name="earnings-calendar-refresh"):
        assert asyncio.run(client.fetch_earnings_calendar()) == []
    sentry_sdk.capture_message("after an Alpha Vantage request")
    sentry_sdk.flush()
    (event,), (transaction,) = _of(sentry_envelopes, "event"), _of(sentry_envelopes, "transaction")
    crumbs = [crumb for crumb in event["breadcrumbs"]["values"] if crumb.get("category") == "httplib"]
    spans = [span for span in transaction["spans"] if span.get("op") == "http.client"]
    assert crumbs and spans  # both carriers were sent
    assert all(item["data"]["http.query"] == "[Filtered]" for item in (*crumbs, *spans))
    leaked = _fragments(key, json.dumps(sentry_envelopes), width=8)
    assert not leaked, f"{leaked} eight-character fragments of the fabricated key reached Sentry"


def test_every_sentry_channel_runs_the_value_scrubber(monkeypatch):
    # Each option through which the SDK hands over an item before sending it is the value scrubber's hook for its
    # channel, which keeps its own kind's paths: errors and check-ins (before_send), transactions, logs and metrics. A
    # hook an SDK upgrade adds fails here until it is wired; before_send_span acts only under span streaming, which the
    # fixture refuses (and the SDK warns when it is set alone).
    import inspect

    from sentry_sdk.consts import ClientConstructor

    import main

    parameters = inspect.signature(ClientConstructor.__init__).parameters
    hooks = {name for name in parameters if name.startswith("before_send")}
    channels = {
        "before_send": "event",
        "before_send_transaction": "transaction",
        "before_send_log": "log",
        "before_send_metric": "metric",
    }
    assert sorted(hooks - {"before_send_span"}) == sorted(channels)
    assert set(main._value_scrubber(("x" * 8,))) == set(channels.values())
    built = {channel: object() for channel in channels.values()}
    monkeypatch.setattr(main, "_value_scrubber", lambda secret_values: built)
    options = main._sentry_options()
    assert {hook: options.get(hook) for hook in channels} == {
        hook: built[channel] for hook, channel in channels.items()
    }


def _scrubbing_envelopes(request, monkeypatch, **values: str | None) -> list:
    """The sentry_envelopes fixture, built once these settings values are in place: main's value scrubber reads the
    settings when `_sentry_options()` runs, as main.py's one call does at startup."""
    from app.config import settings

    for name, value in values.items():
        monkeypatch.setattr(settings, name, value)
    return request.getfixturevalue("sentry_envelopes")


_CARRIERS = (
    *("message", "exception", "breadcrumb", "extra", "tag", "context", "user", "request", "span", "log", "metric"),
    "check-in",
)


@pytest.mark.parametrize("carrier", _CARRIERS)
def test_sentry_withholds_a_secret_value_wherever_it_rides(monkeypatch, request, caplog, carrier):
    # The event scrubber matches key names, so a secret's value quoted in a message, an exception or a log line, or held
    # under a key its denylist does not name, reached Sentry. Each carrier quotes the token twice under such a key (a
    # context holds it as a key too, a request in its path, query string, header and body, a span in its transaction's
    # name, which the envelope's trace header repeats, its own name and its data), on an error, a transaction, a log
    # (sent by the SDK's logger whatever enable_logs says), a metric or a cron check-in.
    import sentry_sdk
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sentry_sdk import logger as sentry_logger
    from sentry_sdk.crons import capture_checkin

    token = _fabricated("INTERNAL_JOB_TOKEN", string.ascii_uppercase)
    envelopes = _scrubbing_envelopes(request, monkeypatch, INTERNAL_JOB_TOKEN=token)
    quoted = f"job failed for {token}, retried with {token}"
    if carrier == "message":
        sentry_sdk.capture_message(quoted)
    elif carrier == "exception":
        sentry_sdk.capture_exception(RuntimeError(quoted))
    elif carrier == "request":
        app = FastAPI()

        @app.post("/notes/{note}")
        async def notes(note: str, body: dict):
            raise RuntimeError("database down")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            f"/notes/{token}", params={"q": quoted}, json={"note": quoted}, headers={"X-Note": quoted}
        )
        assert response.status_code == 500
    elif carrier == "span":
        with sentry_sdk.start_transaction(name=quoted), sentry_sdk.start_span(op="job.step", name=quoted) as span:
            span.set_data("detail", quoted)
    elif carrier == "log":
        sentry_logger.warning(quoted)
    elif carrier == "metric":
        sentry_sdk.metrics.count("job.failures", 1, attributes={"detail": quoted})
    elif carrier == "check-in":
        capture_checkin(monitor_slug=quoted, status="error")
    else:
        if carrier == "breadcrumb":
            caplog.set_level(logging.INFO, logger="app.jobs")
            logging.getLogger("app.jobs").info(quoted)  # a log line at INFO and above becomes a breadcrumb
        elif carrier == "extra":
            sentry_sdk.set_extra("detail", quoted)
        elif carrier == "tag":
            sentry_sdk.set_tag("detail", quoted)
        elif carrier == "context":
            sentry_sdk.set_context("job", {"detail": quoted, token: "a key"})
        else:
            sentry_sdk.set_user({"id": quoted})
        sentry_sdk.capture_message("job failed")
    sentry_sdk.flush()
    sent = json.dumps(envelopes)
    assert "job failed for [Filtered], retried with [Filtered]" in sent  # sent, each occurrence withheld where it stood
    if carrier == "span":  # the envelope's trace header repeats the transaction's name
        traces = [headers["trace"] for kind, headers in envelopes if kind == "headers" and "trace" in headers]
        assert [trace.get("transaction") for trace in traces] == ["job failed for [Filtered], retried with [Filtered]"]
    leaked = _fragments(token, sent, width=8)
    assert not leaked, f"{leaked} eight-character fragments of the fabricated token reached Sentry ({carrier})"


def test_sentry_withholds_every_secret_setting_and_connection_password(monkeypatch, request):
    # Every secret field's value (the gate's own SECRET_FIELDS, the oracle of main's copy of the rule), the database
    # password as written (an "@" percent-encoded) and decoded, and the Redis password (an "@" unescaped, which
    # redis-py reads to the last "@"), quoted in one message, each arrive as "[Filtered]" and nothing else changes: a
    # URL quoted whole is withheld whole. The Alpha Vantage key keeps its format's 16 characters, the shortest secret
    # the app holds.
    import sentry_sdk

    values = {name: _fabricated(name, string.ascii_uppercase) for name in SECRET_FIELDS}
    values["ALPHA_VANTAGE_API_KEY"] = values["ALPHA_VANTAGE_API_KEY"][:16]
    database, redis = values["DATABASE_URL"], values["REDIS_URL"]  # each URL's 40-character password
    encoded, redis = f"{database[:20]}%40{database[20:]}", f"{redis[:20]}@{redis[20:]}"
    values["DATABASE_URL"] = f"postgresql://app:{encoded}@/app?host=/cloudsql/x"
    values["REDIS_URL"] = f"redis://:{redis}@cache.invalid:6379/0"
    envelopes = _scrubbing_envelopes(request, monkeypatch, **values)
    quoted = [*values.values(), encoded, encoded.replace("%40", "@"), redis]
    sentry_sdk.capture_message(" | ".join(quoted))
    sentry_sdk.flush()
    (event,) = _of(envelopes, "event")
    assert event["message"] == " | ".join(["[Filtered]"] * len(quoted))
    # The fragment check reads the secrets alone: a URL's scaffolding ("postgres", ":6379/0") can occur elsewhere.
    secrets = [value for name, value in values.items() if name not in ("DATABASE_URL", "REDIS_URL")]
    leaked = sum(_fragments(value, json.dumps(envelopes), width=8) for value in (*secrets, encoded, redis))
    assert not leaked, f"{leaked} eight-character fragments of a fabricated secret reached Sentry"


def test_sentry_withholds_a_password_read_as_the_port(monkeypatch, request):
    # Codex's case on #1281: a DATABASE_URL missing its `@host` puts the password where the port goes, an all-digit
    # password parses (app.database accepts the URL), and the driver's error quotes it. The address is 127.0.0.1 and
    # the port out of range: the driver refuses before it opens any connection.
    import sentry_sdk
    from sqlalchemy import create_engine
    from sqlalchemy.exc import OperationalError

    digits = _fabricated("DATABASE_URL all-digit password", string.digits)
    url = f"postgresql://app:{digits}/app?hostaddr=127.0.0.1"
    envelopes = _scrubbing_envelopes(request, monkeypatch, DATABASE_URL=url)
    with pytest.raises(OperationalError) as info:
        create_engine(url).connect()
    assert digits in str(info.value)  # the driver quotes it
    sentry_sdk.capture_exception(info.value)
    sentry_sdk.flush()
    (event,) = _of(envelopes, "event")
    assert "[Filtered]" in event["exception"]["values"][-1]["value"]  # sent, the digits withheld where they stood
    leaked = _fragments(digits, json.dumps(envelopes), width=8)
    assert not leaked, f"{leaked} eight-character fragments of the fabricated password reached Sentry"


@pytest.mark.parametrize("form", ["query", "query-rendered", "raw-slash"])
def test_sentry_withholds_a_password_wherever_a_driver_reads_one(monkeypatch, request, form):
    # Codex's case on #1297 (49716c9): SQLAlchemy passes a `password` query parameter to the driver and renders it
    # whole even with hide_password (re-sorting the query, so the rendering differs from the setting, and quoting the
    # value as quote_plus does, which the URL may write otherwise: a raw "/"), and redis-py reads one, but the scrubber
    # took a password from the authority only; and SQLAlchemy reads an authority password holding a raw "/" to the
    # first "@" after the user name's ":" (the only "@" app.database accepts), past where the authority ends. Each
    # password, as written and as the driver reads it, and an engine's rendering of its URL arrive "[Filtered]".
    import sentry_sdk
    from redis.connection import parse_url
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url

    database = _fabricated(f"DATABASE_URL {form} password", string.ascii_uppercase)
    redis = _fabricated(f"REDIS_URL {form} password", string.ascii_uppercase)
    if form == "query":
        written = f"{database[:20]}%2B{database[20:]}"  # an encoded "+", read as one
        urls = {
            "DATABASE_URL": f"postgresql://app@db.invalid/app?sslmode=require&password={written}",
            "REDIS_URL": f"redis://cache.invalid:6379/0?password={redis}",
        }
        read = make_url(urls["DATABASE_URL"]).query["password"]
        assert read == f"{database[:20]}+{database[20:]}" and parse_url(urls["REDIS_URL"])["password"] == redis
        rendered = repr(create_engine(urls["DATABASE_URL"]))
        assert written in rendered and urls["DATABASE_URL"] not in rendered  # only the password can withhold it there
        quoted = [written, read, redis, rendered]
    elif form == "query-rendered":  # the round-17 check's R17V-1: SQLAlchemy renders a raw "/" as %2F
        written = read = f"{database[:20]}/{database[20:]}"
        urls = {"DATABASE_URL": f"postgresql://app@db.invalid/app?sslmode=require&password={written}"}
        assert make_url(urls["DATABASE_URL"]).query["password"] == read
        rendered = repr(create_engine(urls["DATABASE_URL"]))
        assert written not in rendered and f"{database[:20]}%2F{database[20:]}" in rendered
        quoted = [written, rendered]
    else:
        written = read = f"{database[:20]}/{database[20:]}"
        urls = {"DATABASE_URL": f"postgresql://app:{written}@db.invalid/app"}
        assert make_url(urls["DATABASE_URL"]).password == read  # SQLAlchemy's rendering hides this one as ***
        quoted = [written]
    envelopes = _scrubbing_envelopes(request, monkeypatch, **urls)
    sentry_sdk.capture_message(" | ".join(quoted))
    sentry_sdk.flush()
    (event,) = _of(envelopes, "event")
    assert all(part.count("[Filtered]") for part in event["message"].split(" | "))
    leaked = sum(_fragments(value, json.dumps(envelopes), width=8) for value in (database, redis))
    assert not leaked, f"{leaked} eight-character fragments of a fabricated password reached Sentry ({form})"


def test_a_url_sqlalchemy_cannot_parse_still_gives_its_password():
    # The passwords SQLAlchemy parses join the URL rules' own, never replace them: a URL SQLAlchemy refuses (a port that
    # is no number) still gives the authority's password and a `password` query parameter, each as written and
    # decoded, and building the values does not fail, which would turn Sentry off. Only here does the query rule alone
    # give a value: in the gate's other query forms SQLAlchemy's reading or its rendering gives the value as written.
    from sqlalchemy.engine import make_url

    import main

    password = _fabricated("DATABASE_URL unparsed password", string.ascii_uppercase)
    query = _fabricated("DATABASE_URL unparsed query password", string.ascii_uppercase)
    written, in_query = f"{password[:20]}%40{password[20:]}", f"{query[:20]}%2B{query[20:]}"
    url = f"postgresql://app:{written}@db.invalid:notaport/app?password={in_query}"
    with pytest.raises(ValueError):
        make_url(url)
    decoded = {f"{password[:20]}@{password[20:]}", f"{query[:20]}+{query[20:]}"}
    assert {written, in_query} | decoded <= main._url_passwords(url)


def test_sentry_withholds_a_secret_stored_with_a_newline(monkeypatch, request):
    # A secret created with `echo` keeps its newline in the environment, and an error can quote it escaped (a header
    # value's repr, `b'Bearer ...\n'`), where the value as held never appears: the value is withheld stripped.
    import sentry_sdk

    key = _fabricated("STRIPE_SECRET_KEY", string.ascii_uppercase)
    envelopes = _scrubbing_envelopes(request, monkeypatch, STRIPE_SECRET_KEY=f"{key}\n")
    sentry_sdk.capture_message(f"Illegal header value {f'Bearer {key}{chr(10)}'.encode()!r}")
    sentry_sdk.flush()
    (event,) = _of(envelopes, "event")
    assert event["message"] == "Illegal header value b'Bearer [Filtered]\\n'"


def test_sentry_withholds_a_new_secret_setting_under_each_suffix(monkeypatch, request):
    # A secret setting added later is withheld without a change to main.py when its name ends in one of the rule's
    # suffixes (the gate's copy, the oracle), `_PASSWORD` included, which no field carries yet.
    import pydantic
    import sentry_sdk

    import main
    from app.config import Settings

    fields = {f"FABRICATED{suffix}": (str, "") for suffix in _SECRET_SUFFIXES}
    values = {name: _fabricated(name, string.ascii_uppercase) for name in fields}
    extended = pydantic.create_model("ExtendedSettings", __base__=Settings, **fields)
    monkeypatch.setattr(main, "settings", extended.model_construct(**main.settings.model_dump(), **values))
    envelopes = request.getfixturevalue("sentry_envelopes")
    sentry_sdk.capture_message(" | ".join(values.values()))
    sentry_sdk.flush()
    (event,) = _of(envelopes, "event")
    assert event["message"] == " | ".join(["[Filtered]"] * len(values))


def test_the_value_scrubber_keeps_numbers_and_withholds_a_secret_in_any_other_value():
    # The walk is total: None, booleans and numbers stay as they are (a metric's value, a measurement, a log's
    # timestamp are read as numbers after the hook), mappings (keys too) and lists are walked, and any other value
    # becomes its repr with the secret withheld there.
    import main

    secret = _fabricated("SECRET_KEY", string.ascii_uppercase)
    node = {"count": 7, "ratio": 1.5, "sent": True, "none": None, secret: [secret], "pair": (secret, 2)}
    node["error"] = RuntimeError(secret)
    assert main._withhold(node, (secret,)) == {
        "count": 7,
        "ratio": 1.5,
        "sent": True,
        "none": None,
        "[Filtered]": ["[Filtered]"],
        "pair": "('[Filtered]', 2)",
        "error": "RuntimeError('[Filtered]')",
    }
    assert [type(main._withhold(value, (secret,))) for value in (7, 1.5, True)] == [int, float, bool]


@pytest.mark.parametrize("switch", ["enable_logs", "capture_sentry_logs"])
def test_sentry_logs_withhold_a_secret_in_a_value_that_is_not_text(monkeypatch, request, caplog, switch):
    # With Sentry logs on (either switch), the logging integration sends a record's `extra` values as they are, and
    # the SDK's logger a body that is not text; the SDK turns each into text after the hook (a repr, a str), where
    # nothing scrubs it. The scrubber walks a mapping and turns any other such value into its repr first, withholding
    # the secret there.
    import sentry_sdk
    from sentry_sdk import logger as sentry_logger
    from sentry_sdk.integrations.logging import LoggingIntegration

    import main

    options = main._sentry_options
    if switch == "enable_logs":
        monkeypatch.setattr(main, "_sentry_options", lambda: {**options(), "enable_logs": True})
    else:
        # The constructor sets the class attribute every LoggingIntegration reads; the original comes back after.
        monkeypatch.setattr(LoggingIntegration, "capture_sentry_logs", LoggingIntegration.capture_sentry_logs)

        def with_logs() -> dict:
            built = options()
            return {**built, "integrations": [*built["integrations"], LoggingIntegration(capture_sentry_logs=True)]}

        monkeypatch.setattr(main, "_sentry_options", with_logs)
    token = _fabricated("INTERNAL_JOB_TOKEN", string.ascii_uppercase)
    envelopes = _scrubbing_envelopes(request, monkeypatch, INTERNAL_JOB_TOKEN=token)
    quoted = f"job failed for {token}, retried with {token}"
    caplog.set_level(logging.INFO, logger="app.jobs")
    logging.getLogger("app.jobs").warning("job failed", extra={"attempts": (quoted, 2), "detail": {"note": quoted}})
    sentry_logger.warning(RuntimeError(quoted))
    sentry_sdk.flush()
    logs = [entry for payload in _of(envelopes, "log") for entry in payload["items"]]
    record = next(entry for entry in logs if entry["attributes"].get("logger.name", {}).get("value") == "app.jobs")
    assert record["attributes"]["attempts"]["value"] == "('job failed for [Filtered], retried with [Filtered]', 2)"
    assert record["attributes"]["detail"]["value"] == "{'note': 'job failed for [Filtered], retried with [Filtered]'}"
    assert "RuntimeError('job failed for [Filtered], retried with [Filtered]')" in [entry["body"] for entry in logs]
    leaked = _fragments(token, json.dumps(envelopes), width=8)
    assert not leaked, f"{leaked} eight-character fragments of the fabricated token reached Sentry ({switch})"


def test_sentry_withholds_no_value_shorter_than_eight_characters(monkeypatch, request):
    # The floor (main._MIN_SECRET_LENGTH): an eight-character value is withheld; a seven-character one, an empty one
    # (most secret settings' default) and a URL's port, which the URL rule reads as a password when a URL has no `@`,
    # are not, so none garbles an event; nor is an IPv6 host's address read as a password, and a setting that holds no
    # text (None) is skipped rather than failing the options, which would turn Sentry off.
    import sentry_sdk

    eight = _fabricated("FMP_API_KEY", string.ascii_uppercase)[:8]
    seven = _fabricated("IP_HASH_SALT", string.ascii_uppercase)[:7]
    urls = {"DATABASE_URL": "postgresql://db.internal:5432/app", "REDIS_URL": "redis://[2001:db8::1]:6379/0"}
    values = {"FMP_API_KEY": eight, "IP_HASH_SALT": seven, "RESEND_API_KEY": "", "TURNSTILE_SECRET_KEY": None, **urls}
    envelopes = _scrubbing_envelopes(request, monkeypatch, **values)
    sentry_sdk.capture_message(f"{eight} {seven} db.internal:5432 [2001:db8::1]:6379 as sent")
    sentry_sdk.flush()
    (event,) = _of(envelopes, "event")
    assert event["message"] == f"[Filtered] {seven} db.internal:5432 [2001:db8::1]:6379 as sent"


def _capture_every_structure(caplog) -> None:
    """One capture of the structures the SDK builds under main's options, on every channel, as far as the design and
    delta checks of #1297 read the SDK (2.71.0): an error with a chained exception (its frames and mechanism), an
    exception group (its mechanism's links), a log record with its thread's stack, breadcrumbs from a log line and by
    hand, a user, a request that continues a trace and a log entry; then, past max_breadcrumbs (the SDK's length note),
    transactions with nested spans, a database query, an outbound HTTP call and an error after it inside the
    transaction heading its trace, a gen-AI span and a response status; check-ins inside the request, inside a span and
    with a monitor config (the SDK's MonitorConfig fields, written out here by hand); a log; a counter and a
    distribution."""
    import sentry_sdk
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sentry_sdk import logger as sentry_logger
    from sentry_sdk.crons import capture_checkin
    import httpx
    from sqlalchemy import create_engine, text

    caplog.set_level(logging.INFO, logger="app.jobs")
    logging.getLogger("app.jobs").info("step %s", "one")  # a log line at INFO and above becomes a breadcrumb
    sentry_sdk.add_breadcrumb(category="job", message="retrying", data={"attempt": 2})
    sentry_sdk.set_user({"id": "1", "username": "reader"})
    try:
        try:
            raise KeyError("note")
        except KeyError as cause:
            raise RuntimeError("job failed") from cause
    except RuntimeError as error:
        sentry_sdk.capture_exception(error)
    try:
        raise ExceptionGroup("jobs failed", [ValueError("one"), TypeError("two")])
    except ExceptionGroup as group:
        sentry_sdk.capture_exception(group)
    logging.getLogger("app.jobs").error("job %s failed", "two")  # an event with a log entry
    logging.getLogger("app.jobs").error("job three failed", stack_info=True)  # an event with its thread's stack
    sentry_sdk.capture_message("job failed again", fingerprint=["job", "nightly"])
    app = FastAPI()

    @app.post("/notes/{note}")
    async def notes(note: str, body: dict):
        capture_checkin(monitor_slug="notes", status="in_progress")  # in a request that continues a trace
        raise RuntimeError("database down")

    # A request that continues a trace: the SDK copies the incoming baggage's items into the dynamic sampling context.
    trace = {"sentry-trace": f"{'a' * 32}-{'b' * 16}-1"}
    trace["baggage"] = f"sentry-trace_id={'a' * 32},sentry-replay_id={'c' * 32},sentry-user_segment=readers"
    TestClient(app, raise_server_exceptions=False).post(
        "/notes/1", params={"q": "x"}, json={"note": "x"}, headers=trace
    )
    for _ in range(101):  # past max_breadcrumbs: a later transaction or check-in carries the SDK's length note
        sentry_sdk.add_breadcrumb(category="job", message="step")
    engine = create_engine("sqlite://")
    with sentry_sdk.start_transaction(name="job", op="task") as transaction:
        transaction.set_http_status(500)
        with sentry_sdk.start_span(op="job.step", name="step"), sentry_sdk.start_span(op="job.query", name="query"):
            with engine.connect() as connection:
                connection.execute(text("select 1"))
            capture_checkin(monitor_slug="nightly", status="in_progress")  # inside a span: its trace context
    with sentry_sdk.start_transaction(name="chat", op="ai"), sentry_sdk.start_span(op="gen_ai.chat", name="chat"):
        pass  # a gen-AI span, which the SDK splits out of its transaction after the hook
    with sentry_sdk.start_transaction(name="fetch", op="fetch"):  # an outbound call: its span and breadcrumb
        httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200))).get("https://api.invalid/x")
        sentry_sdk.capture_message("fetch failed")  # inside the transaction heading its trace, after a call
    capture_checkin(
        monitor_slug="nightly",
        status="ok",
        duration=1.5,
        monitor_config={
            "schedule": {"type": "interval", "value": 1, "unit": "day"},
            "timezone": "UTC",
            "checkin_margin": 5,
            "max_runtime": 30,
            "failure_issue_threshold": 2,
            "recovery_threshold": 2,
            "owner": "jobs",
        },
    )
    sentry_logger.warning("job {name} failed", name="nightly")
    sentry_sdk.metrics.count("job.failures", 1)
    sentry_sdk.metrics.distribution("job.seconds", 1.5, unit="second")
    sentry_sdk.flush()


def test_a_secret_equal_to_a_protocol_word_breaks_no_item(monkeypatch, request, caplog):
    # Codex's cases on #1297: a weak secret equal to a word of Sentry's protocol (IP_HASH_SALT=event_id passes every
    # check) renamed the event's own `event_id`, which the SDK reads after the hook, so the capture raised; one equal to
    # a key below it (parent_span_id) renamed that key in each child span. Every key at one of the protocol's own paths
    # for its item's kind and an item's `type` stay as they are (main._PROTOCOL_PATHS, main._ITEM_TYPES): errors,
    # transactions, check-ins, a log and a metric are each sent, as their own kind and whole, the trace header keeps
    # its sample rate, and a gen-AI span, which the SDK splits out after the hook, keeps its keys.
    words = {
        "IP_HASH_SALT": "event_id",
        "FMP_API_KEY": "trace_id",
        "POSTHOG_API_KEY": "attributes",
        "TURNSTILE_SECRET_KEY": "start_timestamp",
        "ALPHA_VANTAGE_API_KEY": "time_unix_nano",
        "GOOGLE_CLIENT_SECRET": "severity_number",
        "OPENAI_API_KEY": "transaction",
        "AI_FALLBACK_API_KEY": "timestamp",
        "STRIPE_WEBHOOK_SECRET": "check_in",
        "RESEND_API_KEY": "parent_span_id",
        "RESEND_WEBHOOK_SECRET": "category",
        "STRIPE_PUBLISHABLE_KEY": "filename",
        "STRIPE_SECRET_KEY": "schedule",
        "INTERNAL_JOB_TOKEN": "sample_rate",
        "SECRET_KEY": "distribution",
    }
    envelopes = _scrubbing_envelopes(request, monkeypatch, **words)
    _capture_every_structure(caplog)
    assert not [lost for lost in _of(envelopes, "lost") if lost[0] == "callback_error"]
    events, transactions, checkins = (_of(envelopes, kind) for kind in ("event", "transaction", "check_in"))
    assert all("event_id" in event for event in events) and [item["type"] for item in checkins] == ["check_in"] * 3
    frames = [
        frame
        for event in events
        for value in event.get("exception", {}).get("values", [])
        for frame in value.get("stacktrace", {}).get("frames", [])  # an exception never raised has no frames
    ]
    assert frames and all("filename" in frame for frame in frames)
    crumbs = [crumb for event in events for crumb in event.get("breadcrumbs", {}).get("values", [])]
    assert crumbs and all("category" in crumb and "timestamp" in crumb for crumb in crumbs)
    (job,) = [transaction for transaction in transactions if transaction["contexts"]["trace"].get("op") == "task"]
    assert job["type"] == "transaction" and {"event_id", "start_timestamp", "timestamp", "transaction"} <= job.keys()
    assert "trace_id" in job["contexts"]["trace"] and len(job["spans"]) == 3
    assert all({"parent_span_id", "start_timestamp", "timestamp", "trace_id"} <= span.keys() for span in job["spans"])
    (checkin,) = [item for item in checkins if "monitor_config" in item]
    assert {"schedule", "timezone", "checkin_margin"} <= checkin["monitor_config"].keys()
    traces = [headers["trace"] for kind, headers in envelopes if kind == "headers" and "trace" in headers]
    assert traces and all("sample_rate" in trace and "trace_id" in trace for trace in traces)
    (chat,) = [span for payload in _of(envelopes, "span") for span in payload["items"]]  # split out after the hook
    assert {"parent_span_id", "start_timestamp", "trace_id"} <= chat.keys()
    (logs,), (metrics,) = _of(envelopes, "log"), _of(envelopes, "trace_metric")
    assert [entry["body"] for entry in logs["items"]] == ["job nightly failed"]
    assert [(entry["name"], entry["type"]) for entry in metrics["items"]] == [
        ("job.failures", "counter"),
        ("job.seconds", "distribution"),
    ]


# The fields whose mappings hold user data: their keys are the app's data and the SDK's attribute names
# (`sentry.environment`, `thread.id`), at none of the protocol's paths (main._PROTOCOL_PATHS), so the value scrubber
# scrubs them all, a protocol word or not, and the structure cases leave them out (the lesson's over-redaction entry).
_USER_DATA_FIELDS = frozenset(
    {"data", "tags", "extra", "attributes", "headers", "cookies", "env", "vars", "params", "measurements", "modules"}
)


def _structure(node: object, path: tuple = ()) -> set[tuple]:
    """The path of each key in an item outside user data (a user-data field's own key is the protocol's, its keys
    are not walked; the capture sets no context of its own, so every context is the SDK's); a list's items by their
    index, so a key lost in one span or frame shows."""
    paths = set()
    if isinstance(node, dict):
        for key, value in node.items():
            paths.add((*path, key))
            if key not in _USER_DATA_FIELDS:
                paths |= _structure(value, (*path, key))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            paths |= _structure(item, (*path, index))
    return paths


def test_every_key_of_the_protocols_own_survives_a_secret_equal_to_it(monkeypatch, request, caplog):
    # Codex's case on #1297, and the coordination comment's ask for schema-aware coverage: a weak secret equal to a key
    # of Sentry's protocol below an item's top level (IP_HASH_SALT=parent_span_id passes every check) renamed that key
    # in each child span, breadcrumb, frame or monitor config. Every key of 8 characters or more that the SDK's own
    # items carry outside user data (as each hook received them, from one capture of the structures the design checks
    # found the SDK builds, on every channel), each taken as a secret, leaves every item's structure as it was. The keys
    # come from the SDK's items, not from main's list: a key on a structure the capture builds fails here until
    # main._PROTOCOL_PATHS has its path for the item's kind, and an SDK upgrade fails the pin below until the capture is
    # checked again.
    import copy

    import sentry_sdk

    import main

    # The capture reaches the structures the design checks of #1297 found this SDK builds under main's options (not a
    # subprocess span, errno mechanism data or a gauge); an upgrade can add one it does not reach, so it fails here
    # until the capture is checked again.
    assert sentry_sdk.VERSION == "2.71.0"

    received = []
    value_scrubber = main._value_scrubber

    def recording(secret_values):
        hooks = value_scrubber(secret_values)

        def recorder(channel, hook):
            def recorded(item, hint):
                received.append((channel, copy.deepcopy(item)))
                return hook(item, hint)

            return recorded

        return {channel: recorder(channel, hook) for channel, hook in hooks.items()}

    monkeypatch.setattr(main, "_value_scrubber", recording)
    request.getfixturevalue("sentry_envelopes")
    _capture_every_structure(caplog)
    assert {"transaction", "check_in", "counter"} <= {item.get("type") for _, item in received}
    assert any("exception" in item for _, item in received) and any("severity_text" in item for _, item in received)
    # Each key's path from its item's top, a list's items sharing the list's path, by the item's kind: its channel's,
    # and on before_send a check-in's when its type is exactly `check_in`, an error's otherwise.
    paths = {}
    for channel, item in received:
        kind = channel
        if channel == "event":
            kind = "check_in" if type(item.get("type")) is str and item["type"] == "check_in" else "error"
        paths.setdefault(kind, set()).update(
            tuple(step for step in path if not isinstance(step, int))
            for path in _structure(item)
            if isinstance(path[-1], str) and len(path[-1]) >= main._MIN_SECRET_LENGTH
        )
    # Main keeps exactly these paths for each kind: none missing, none dead, each spelled as the SDK spells it. The
    # capture sets no context of its own, so every context in it is the SDK's.
    assert main._PROTOCOL_PATHS == paths, {
        kind: (
            sorted(paths.get(kind, set()) - main._PROTOCOL_PATHS.get(kind, set())),
            sorted(main._PROTOCOL_PATHS.get(kind, set()) - paths.get(kind, set())),
        )
        for kind in sorted(set(paths) | set(main._PROTOCOL_PATHS))
    }
    assert {name for _, item in received for name in item.get("contexts", {})} == {"trace", "runtime", "response"}
    words = sorted({path[-1] for kept in paths.values() for path in kept}, key=lambda word: (-len(word), word))
    hooks = value_scrubber(tuple(words))
    for channel, item in received:
        lost = _structure(item) - _structure(hooks[channel](copy.deepcopy(item), {}))
        assert not lost, f"{sorted('.'.join(map(str, path)) for path in lost)} lost to secrets equal to protocol keys"


def test_a_secret_held_as_a_key_in_user_data_is_withheld(monkeypatch, request):
    # Only a key at one of the protocol's own paths stays (main._PROTOCOL_PATHS): a secret held as a key in an extra, a
    # tag, a context (its name and inside it), a user, a breadcrumb's data, a request's body, a span's data or tags, a
    # log's or a metric's attributes is withheld there, and so is one that follows a protocol word in the same key (a
    # user's, whose own `username` stays: a key is kept only when it is exactly the protocol's).
    import sentry_sdk
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sentry_sdk import logger as sentry_logger

    token = _fabricated("INTERNAL_JOB_TOKEN", string.ascii_uppercase)
    envelopes = _scrubbing_envelopes(request, monkeypatch, INTERNAL_JOB_TOKEN=token)
    sentry_sdk.set_extra(token, "x")
    sentry_sdk.set_tag(token, "x")
    sentry_sdk.set_context(token, {token: "x"})
    sentry_sdk.set_user({"id": "1", token: "x", f"username.{token}": "x"})  # a user's keys are kept by exact name only
    sentry_sdk.add_breadcrumb(message="retrying", data={token: "x"})
    sentry_sdk.capture_message("job failed")
    app = FastAPI()

    @app.post("/notes")
    async def notes(body: dict):
        raise RuntimeError("database down")

    TestClient(app, raise_server_exceptions=False).post("/notes", json={token: "x"})
    with sentry_sdk.start_transaction(name="job"), sentry_sdk.start_span(op="job.step") as span:
        span.set_data(token, "x")
        span.set_data(f"trace_id.{token}", "x")
        span.set_tag(token, "x")
    sentry_logger.warning("job failed", attributes={token: "x"})
    sentry_sdk.metrics.count("job.failures", 1, attributes={token: "x"})
    sentry_sdk.flush()
    leaked = _fragments(token, json.dumps(envelopes), width=8)
    assert not leaked, f"{leaked} eight-character fragments of the fabricated token reached Sentry"
    events = _of(envelopes, "event")
    (event,) = [event for event in events if event.get("message") == "job failed"]
    assert event["extra"]["[Filtered]"] == event["tags"]["[Filtered]"] == event["user"]["[Filtered]"] == "x"
    assert event["user"]["username.[Filtered]"] == "x"
    assert event["contexts"]["[Filtered]"] == {"[Filtered]": "x"}
    assert {"[Filtered]": "x"} in [crumb.get("data") for crumb in event["breadcrumbs"]["values"]]
    assert {"[Filtered]": "x"} in [event.get("request", {}).get("data") for event in events]
    (job,) = [transaction for transaction in _of(envelopes, "transaction") if transaction["transaction"] == "job"]
    ((step,),) = [job["spans"]]
    assert step["data"]["[Filtered]"] == step["data"]["trace_id.[Filtered]"] == step["tags"]["[Filtered]"] == "x"
    (logs,), (metrics,) = _of(envelopes, "log"), _of(envelopes, "trace_metric")
    assert logs["items"][0]["attributes"]["[Filtered]"]["value"] == "x"
    assert metrics["items"][0]["attributes"]["[Filtered]"]["value"] == "x"


def test_a_secret_equal_to_a_protocol_word_is_withheld_as_a_key_in_user_data(monkeypatch, request, caplog):
    # The protocol's words stay only where the protocol puts them (the adversarial design check on #1297): an app that
    # writes one as a key in user data (an extra, a tag, a context of its own, a breadcrumb's data, a span's data and
    # tags, a log's or a metric's attributes, a request's body and headers, a log entry's params) writes its own data,
    # so a weak secret equal to that word (IP_HASH_SALT=username passes every check) is withheld there, while the
    # user's `username`, where the protocol puts it, stays.
    import sentry_sdk
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sentry_sdk import logger as sentry_logger

    word = "username"
    envelopes = _scrubbing_envelopes(request, monkeypatch, IP_HASH_SALT=word)
    sentry_sdk.set_user({"id": "1", word: "reader"})
    sentry_sdk.set_extra(word, "x")
    sentry_sdk.set_tag(word, "x")
    sentry_sdk.set_context("job", {word: "x"})
    sentry_sdk.add_breadcrumb(message="retrying", data={word: "x"})
    caplog.set_level(logging.INFO, logger="app.jobs")
    logging.getLogger("app.jobs").error("job %(name)s failed", {word: "x", "name": "nightly"})
    app = FastAPI()

    @app.post("/notes")
    async def notes(body: dict):
        raise RuntimeError("database down")

    TestClient(app, raise_server_exceptions=False).post("/notes", json={word: "x"}, headers={word: "x"})
    with sentry_sdk.start_transaction(name="job"), sentry_sdk.start_span(op="job.step") as span:
        span.set_data(word, "x")
        span.set_tag(word, "x")
    sentry_logger.warning("job failed", attributes={word: "x"})
    sentry_sdk.metrics.count("job.failures", 1, attributes={word: "x"})
    sentry_sdk.flush()
    events = _of(envelopes, "event")
    assert events and all(event["user"][word] == "reader" for event in events)
    (event,) = [event for event in events if event.get("logentry")]
    assert event["extra"]["[Filtered]"] == event["tags"]["[Filtered]"] == event["contexts"]["job"]["[Filtered]"] == "x"
    assert event["logentry"]["params"] == {"[Filtered]": "x", "name": "nightly"}
    assert {"[Filtered]": "x"} in [crumb.get("data") for crumb in event["breadcrumbs"]["values"]]
    (posted,) = [event for event in events if event.get("request", {}).get("data")]
    assert posted["request"]["data"] == {"[Filtered]": "x"} and posted["request"]["headers"]["[Filtered]"] == "x"
    (job,) = [transaction for transaction in _of(envelopes, "transaction") if transaction["transaction"] == "job"]
    ((step,),) = [job["spans"]]
    assert step["data"]["[Filtered]"] == step["tags"]["[Filtered]"] == "x"
    (logs,), (metrics,) = _of(envelopes, "log"), _of(envelopes, "trace_metric")
    assert logs["items"][0]["attributes"]["[Filtered]"]["value"] == "x"
    assert metrics["items"][0]["attributes"]["[Filtered]"]["value"] == "x"


def test_a_protocol_word_is_kept_only_at_its_own_path(monkeypatch, request):
    # Codex's case on #1297 (ffe85f1): a key equal to a protocol word stays only at the protocol's own path, so a weak
    # secret equal to one (IP_HASH_SALT=trace_id passes every check) written as a user's own key, nested by the app in a
    # trace context, or as a hand-built event's field is withheld there, while the user's `username` and the trace
    # context's `trace_id`, where the protocol puts them, stay.
    import sentry_sdk

    word = "trace_id"
    envelopes = _scrubbing_envelopes(request, monkeypatch, IP_HASH_SALT=word)
    sentry_sdk.set_user({"id": "1", "username": "reader", word: "x"})
    sentry_sdk.capture_message("a user's own key")
    trace = {word: "0" * 32, "span_id": "1" * 16, "custom": {word: "x"}}
    sentry_sdk.capture_event({"message": "nested by hand", "contexts": {"trace": trace}, "custom": {word: "x"}})
    sentry_sdk.flush()
    events = {event["message"]: event for event in _of(envelopes, "event")}
    user = events["a user's own key"]["user"]
    assert user["[Filtered]"] == "x" and user["username"] == "reader" and word not in user
    assert word in events["a user's own key"]["contexts"]["trace"]
    nested = events["nested by hand"]
    assert nested["contexts"]["trace"][word] == "0" * 32
    assert nested["contexts"]["trace"]["custom"] == {"[Filtered]": "x"}
    assert nested["custom"] == {"[Filtered]": "x"}


def test_a_protocol_word_is_kept_only_in_its_own_kind_of_item(monkeypatch, request):
    # Codex's case on #1297 (a87dfd9), which the delta reviewer reproduced: a key stays only at a path the protocol
    # gives its own kind of item, so weak secrets equal to a log's `attributes` and a check-in's `check_in_id`, written
    # into an ordinary error by an event processor, and to a log's top-level `trace_id`, on a hand-built error, are
    # withheld there, while the error's own trace context keeps its `trace_id`; and an event whose `type` only poses as
    # `check_in` keeps no check-in key.
    import sentry_sdk

    import main

    secrets = {"IP_HASH_SALT": "attributes", "FMP_API_KEY": "check_in_id", "POSTHOG_API_KEY": "trace_id"}
    envelopes = _scrubbing_envelopes(request, monkeypatch, **secrets)

    def write(event, hint):
        if event.get("message") == "another kind's keys":
            event.update({"attributes": "x", "check_in_id": "x"})
        return event

    sentry_sdk.get_isolation_scope().add_event_processor(write)
    sentry_sdk.capture_message("another kind's keys")
    sentry_sdk.capture_event({"message": "a log's key by hand", "trace_id": "x"})
    sentry_sdk.flush()
    events = {event["message"]: event for event in _of(envelopes, "event")}
    written, by_hand = events["another kind's keys"], events["a log's key by hand"]
    assert written["[Filtered]"] == "x" and not {"attributes", "check_in_id"} & written.keys()
    assert "trace_id" in written["contexts"]["trace"]  # the error's own path
    assert by_hand["[Filtered]"] == "x" and "trace_id" not in by_hand

    class Posing(str):
        def __eq__(self, other):
            return other == "check_in"

        def __hash__(self):
            return hash("check_in")

    scrubbed = main._value_scrubber(("check_in_id",))["event"]({"type": Posing("event"), "check_in_id": "x"}, {})
    assert scrubbed == {"type": "event", "[Filtered]": "x"} and type(scrubbed["type"]) is str


def test_each_kind_of_event_keeps_only_its_own_kinds_keys(monkeypatch, request):
    # Weak secrets equal to a key only an error's paths hold (`fingerprint`), one only a transaction's hold
    # (`start_timestamp`), one only a check-in's hold (`check_in_id`) and one only a log's and a metric's hold
    # (`attributes`), written where the item lacks them by an event processor (into an error and a transaction; the
    # SDK runs none on a check-in) and by hand (a check-in): each item keeps only its own kind's. A log or a metric
    # has no such case: the SDK builds both with fixed top-level keys and runs no event processor on them before their
    # hooks (the scope fills only their trace_id, span_id and attributes).
    import sentry_sdk

    words = {
        "IP_HASH_SALT": "fingerprint",
        "FMP_API_KEY": "start_timestamp",
        "POSTHOG_API_KEY": "check_in_id",
        "RESEND_API_KEY": "attributes",
    }
    envelopes = _scrubbing_envelopes(request, monkeypatch, **words)

    def write(event, hint):
        for word in words.values():
            event.setdefault(word, "x")
        return event

    sentry_sdk.get_isolation_scope().add_event_processor(write)
    sentry_sdk.capture_message("an error")
    with sentry_sdk.start_transaction(name="job", op="task"):
        pass
    sentry_sdk.capture_event(
        {
            "type": "check_in",
            "monitor_slug": "nightly",
            "status": "ok",
            "check_in_id": "c" * 32,
            **{word: "x" for word in words.values() if word != "check_in_id"},
        }
    )
    sentry_sdk.flush()
    (error,), (transaction,), (checkin,) = (_of(envelopes, kind) for kind in ("event", "transaction", "check_in"))
    for item, own in ((error, "fingerprint"), (transaction, "start_timestamp"), (checkin, "check_in_id")):
        assert [word for word in words.values() if word in item] == [own] and item["[Filtered]"] == "x"


@pytest.mark.parametrize("field", sorted(_USER_DATA_FIELDS))
def test_the_value_scrubber_keeps_a_protocol_word_only_outside_user_data(field):
    # Main keeps a key only at the paths the protocol gives the item's kind (an error's here), none of them below a field
    # of the gate's list, so a weak secret equal to a protocol word is withheld as a key there at any depth (a list's
    # items too, a protocol structure nested there too), and in a context the app set, while the same word stays where
    # the protocol puts it (a user's `username`, the trace context's `trace_id`).
    import main

    word = "username"
    item = {
        "user": {word: "reader"},
        field: {word: "x", "nested": {word: "x"}, "listed": [{word: "x"}], "user": {word: "x"}},
        "contexts": {"trace": {"trace_id": "x"}, "job": {word: "x"}},
    }
    assert main._withhold(item, (word,), main._PROTOCOL_PATHS["error"]) == {
        "user": {word: "reader"},
        field: {
            "[Filtered]": "x",
            "nested": {"[Filtered]": "x"},
            "listed": [{"[Filtered]": "x"}],
            "user": {"[Filtered]": "x"},  # a protocol structure nested in user data keeps nothing
        },
        "contexts": {"trace": {"trace_id": "x"}, "job": {"[Filtered]": "x"}},
    }


def test_a_key_is_kept_as_a_protocol_word_only_when_it_is_text():
    # Log and metric attributes reach the hook unserialized, keys as the app gave them: a str subclass that compares
    # equal to a protocol word while its text is a secret is withheld (a key is kept only when it is exactly text), and
    # any other key equal to one becomes its repr, which the SDK can encode (the adversarial design check on #1297).
    import main

    secret = _fabricated("SECRET_KEY", string.ascii_uppercase)

    class Posing(str):
        def __eq__(self, other):
            return other == "timestamp"

        def __hash__(self):
            return hash("timestamp")

    class Word:
        def __eq__(self, other):
            return other == "timestamp"

        def __hash__(self):
            return hash("timestamp")

        def __repr__(self):
            return "Word()"

    errors = main._PROTOCOL_PATHS["error"]  # `timestamp` is one of an error's own paths
    assert main._withhold({Posing(secret): 1}, (secret,), errors) == {"[Filtered]": 1}
    assert main._withhold({Word(): 2}, (secret,), errors) == {"Word()": 2}
    # Above a protocol path, too: a key that only poses as `contexts` (its text is the word) keeps nothing below it,
    # while the plain word keeps the trace context's `trace_id`; and below a key that is not text, no key stays, a
    # top-level word included (the delta check of a87dfd9).
    item = {"trace": {"trace_id": "x"}}
    assert main._withhold({"contexts": item}, ("trace_id",), errors) == {"contexts": item}
    assert main._withhold({type("Text", (str,), {})("contexts"): item}, ("trace_id",), errors) == {
        "contexts": {"trace": {"[Filtered]": "x"}}
    }
    assert main._withhold({Word(): {"event_id": "x"}}, ("event_id",), errors) == {"Word()": {"[Filtered]": "x"}}


def test_a_type_is_kept_only_when_it_is_text(monkeypatch, request):
    # The delta check of #1297 (D6-1): an item's `type` is kept only when it is exactly text and one of main._ITEM_TYPES.
    # A hand-built event whose `type` is a str subclass posing as `transaction` while its text is a secret is sent as a
    # plain event, its type scrubbed, and no part of the secret reaches Sentry.
    import sentry_sdk

    token = _fabricated("INTERNAL_JOB_TOKEN", string.ascii_uppercase)
    envelopes = _scrubbing_envelopes(request, monkeypatch, INTERNAL_JOB_TOKEN=token)

    class Posing(str):
        def __eq__(self, other):
            return other == "transaction"

        def __hash__(self):
            return hash("transaction")

    sentry_sdk.capture_event({"message": "posed", "type": Posing(token)})
    sentry_sdk.flush()
    assert [event["type"] for event in _of(envelopes, "event")] == ["[Filtered]"] and not _of(envelopes, "transaction")
    leaked = _fragments(token, json.dumps(envelopes), width=8)
    assert not leaked, f"{leaked} eight-character fragments of the fabricated token reached Sentry"


def test_a_text_subclass_cannot_keep_a_secret(monkeypatch, request):
    # Codex's case on #1297's ready head: the SDK keeps a str subclass as it is up to the hooks (its serializer
    # included), and the scrubber called the text's own `replace`, which a subclass can override to keep the secret (a
    # no-op here). It calls str's: such a text written by an event processor as an error's extra, and sent as a log's
    # body, as a log's attribute and its key, and as a metric's attribute, is withheld in each and comes back exactly
    # text.
    import sentry_sdk
    from sentry_sdk import logger as sentry_logger

    import main

    token = _fabricated("INTERNAL_JOB_TOKEN", string.ascii_uppercase)
    envelopes = _scrubbing_envelopes(request, monkeypatch, INTERNAL_JOB_TOKEN=token)

    class Stubborn(str):
        def replace(self, *args, **kwargs):
            return self

    quoted = Stubborn(f"job failed for {token}")

    def write(event, hint):
        event.setdefault("extra", {})["detail"] = quoted
        return event

    sentry_sdk.get_isolation_scope().add_event_processor(write)
    sentry_sdk.capture_message("a subclass")
    sentry_logger.warning(quoted, attributes={"detail": quoted, Stubborn(token): "a key"})
    sentry_sdk.metrics.count("job.failures", 1, attributes={"detail": quoted})
    sentry_sdk.flush()
    (event,) = _of(envelopes, "event")
    assert event["extra"]["detail"] == "job failed for [Filtered]"
    (log,) = [entry for payload in _of(envelopes, "log") for entry in payload["items"]]
    assert log["body"] == "job failed for [Filtered]"
    assert log["attributes"]["detail"]["value"] == "job failed for [Filtered]"
    assert log["attributes"]["[Filtered]"]["value"] == "a key"
    (metric,) = [entry for payload in _of(envelopes, "trace_metric") for entry in payload["items"]]
    assert metric["attributes"]["detail"]["value"] == "job failed for [Filtered]"  # sent, not dropped
    leaked = _fragments(token, json.dumps(envelopes), width=8)
    assert not leaked, f"{leaked} eight-character fragments of the fabricated token reached Sentry"
    scrubbed = main._withhold(quoted, (token,))
    assert scrubbed == "job failed for [Filtered]" and type(scrubbed) is str


def test_a_number_subclass_cannot_carry_a_secret(monkeypatch, request, caplog):
    # The round-14 delta check (R14-A2): the scrubber kept an int or float subclass as it was, and with Sentry logs on
    # the log batcher makes text of a log's body (str) and of a mapping or mixed-list attribute (repr) after the hook,
    # through the subclass's own __str__ and __repr__, where nothing scrubs it. A number comes back exactly a number:
    # such a body and such values in a log record's extra send no part of the secret, and an error's extra keeps the
    # numbers (the envelope encodes a number by its value).
    import sentry_sdk
    from sentry_sdk import logger as sentry_logger

    import main

    options = main._sentry_options
    monkeypatch.setattr(main, "_sentry_options", lambda: {**options(), "enable_logs": True})
    token = _fabricated("INTERNAL_JOB_TOKEN", string.ascii_uppercase)
    envelopes = _scrubbing_envelopes(request, monkeypatch, INTERNAL_JOB_TOKEN=token)

    class Code(int):
        def __str__(self):
            return f"code 5, job failed for {token}"

        __repr__ = __str__

    class Ratio(float):
        def __str__(self):
            return f"ratio, job failed for {token}"

        __repr__ = __str__

    caplog.set_level(logging.INFO, logger="app.jobs")
    sentry_logger.warning(Code(5))
    sentry_logger.warning(Ratio(0.5))
    extra = {"codes": [Code(5), "x"], "detail": {"ratio": Ratio(0.5)}}
    logging.getLogger("app.jobs").warning("job failed", extra=extra)
    sentry_sdk.set_extra("numbers", {"code": Code(5), "ratio": Ratio(0.5)})
    sentry_sdk.capture_message("numbers")
    sentry_sdk.flush()
    logs = [entry for payload in _of(envelopes, "log") for entry in payload["items"]]
    assert ["5", "0.5"] == [entry["body"] for entry in logs if entry["body"] in ("5", "0.5")]
    record = next(entry for entry in logs if entry["attributes"].get("logger.name", {}).get("value") == "app.jobs")
    assert record["attributes"]["codes"]["value"] == "[5, 'x']"
    assert record["attributes"]["detail"]["value"] == "{'ratio': 0.5}"
    (event,) = _of(envelopes, "event")
    assert event["extra"]["numbers"] == {"code": 5, "ratio": 0.5}
    leaked = _fragments(token, json.dumps(envelopes), width=8)
    assert not leaked, f"{leaked} eight-character fragments of the fabricated token reached Sentry"
    assert type(main._withhold(Code(5), (token,))) is int and type(main._withhold(Ratio(0.5), (token,))) is float


def test_nothing_written_before_the_hooks_carries_a_secret_past_them(monkeypatch, request):
    # The hooks keep only the protocol's own keys at its paths for each item's kind and an item's own `type`
    # (main._PROTOCOL_PATHS, main._ITEM_TYPES), never a field whole, and drop a hint's attachments, whose bytes pass no
    # hook, so nothing that runs before them can carry a secret past them, but as the protocol's own key at its own path
    # in its own kind of item: a trace context set by hand; an attachment on the scope; a hand-built event with the
    # secret as its own key, its `type` and an attachment; or an event processor, registered under any name (an
    # assignment alias: Codex's case on #1297), writing it as an event's key, a trace context's key and the `type`, and
    # attaching it (the high-tier review of 2cc3780). A `type` that is not text (hand-built) is walked like any value,
    # and the event is sent.
    import sentry_sdk
    from sentry_sdk.attachments import Attachment

    token = _fabricated("INTERNAL_JOB_TOKEN", string.ascii_uppercase)
    envelopes = _scrubbing_envelopes(request, monkeypatch, INTERNAL_JOB_TOKEN=token)
    sentry_sdk.set_context("trace", {token: token})
    sentry_sdk.get_isolation_scope().add_attachment(bytes=f"token={token}".encode(), filename="scope.txt")
    sentry_sdk.capture_message("traced by hand")
    attached = Attachment(bytes=token.encode(), filename="hint.txt")
    sentry_sdk.capture_event(
        {"message": "built by hand", token: token, "type": token}, hint={"attachments": [attached]}
    )
    sentry_sdk.capture_event({"message": "typed by hand", "type": ["error"]})

    def rewrite(event, hint):
        event[token] = token
        event.setdefault("contexts", {}).setdefault("trace", {})[token] = token
        event["type"] = token
        hint.setdefault("attachments", []).append(Attachment(bytes=token.encode(), filename="processor.txt"))
        return event

    register = sentry_sdk.get_isolation_scope().add_event_processor
    register(rewrite)
    sentry_sdk.capture_message("rewritten")
    sentry_sdk.flush()
    events = _of(envelopes, "event")
    messages = ["built by hand", "rewritten", "traced by hand", "typed by hand"]
    assert sorted(event.get("message") for event in events) == messages
    assert [event.get("type") for event in events if event.get("message") == "typed by hand"] == [["error"]]
    (rewritten,) = [event for event in events if event.get("message") == "rewritten"]
    assert rewritten["type"] == rewritten["[Filtered]"] == "[Filtered]"  # the aliased processor ran, scrubbed
    traced = [event for event in events if event.get("message") == "traced by hand"]
    assert traced and all("[Filtered]" in event["contexts"]["trace"] for event in traced)  # the context set by hand
    assert all(event.get("type") in (None, "[Filtered]", ["error"]) for event in events)
    assert not _of(envelopes, "attachment") and not _of(envelopes, "lost")
    assert "attachment" not in [headers.get("type") for headers in _of(envelopes, "item_headers")]
    leaked = _fragments(token, json.dumps(envelopes), width=8)
    assert not leaked, f"{leaked} eight-character fragments of the fabricated token reached Sentry"


@pytest.mark.parametrize(
    ("overlap", "text", "sent"),
    [
        ("Filtered", "{token} then Filtered", "[Withheld] then [Withheld]"),
        ("Filtered] then", "{token} then Filtered] then", "[Withheld] then [Withheld]"),
        ("a" * 20 + "[Filtered]" + "b" * 20, "a" * 20 + "{token}" + "b" * 20, "a" * 20 + "[Withheld]" + "b" * 20),
        ("c" * 41 + "[", "c" * 41 + "{token}", "c" * 41 + "<Filtered>"),
    ],
    ids=["inside", "right-edge", "around", "left-edge"],
)
def test_no_placeholder_holds_or_forms_a_secret(monkeypatch, request, overlap, text, sent):
    # Codex's case on #1297: a weak secret that overlaps the placeholder rode inside `[Filtered]` (IP_HASH_SALT=Filtered
    # passes every check) or formed where it meets the text beside it. Each of the four ways a secret can overlap one
    # (inside it, across its end, around it, across its start) moves the placeholder to the first that none overlaps,
    # and the secret appears nowhere in the envelope.
    import sentry_sdk

    token = _fabricated("INTERNAL_JOB_TOKEN", string.ascii_uppercase)
    envelopes = _scrubbing_envelopes(request, monkeypatch, INTERNAL_JOB_TOKEN=token, IP_HASH_SALT=overlap)
    sentry_sdk.capture_message(text.format(token=token))
    sentry_sdk.flush()
    (event,) = _of(envelopes, "event")
    assert event["message"] == sent
    assert overlap not in json.dumps(envelopes)


def test_sentry_stays_off_when_every_placeholder_overlaps_a_secret(monkeypatch):
    # Weak secrets that overlap every placeholder fail the options at startup, so main.py's init, which catches the
    # failure, leaves Sentry off rather than send a placeholder that holds one; the error names no value.
    import main
    from app.config import settings

    for name, word in {"IP_HASH_SALT": "Filtered", "FMP_API_KEY": "Withheld", "POSTHOG_API_KEY": "Redacted"}.items():
        monkeypatch.setattr(settings, name, word)
    with pytest.raises(ValueError) as info:
        main._sentry_options()
    assert str(info.value) == "every placeholder overlaps a secret setting's value"
    tree = ast.parse((BACKEND_DIR / "main.py").read_text(encoding="utf-8"))
    guarded = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Try)
        and any(isinstance(handler.type, ast.Name) and handler.type.id == "Exception" for handler in node.handlers)
        and any(
            ast.unparse(call) == "sentry_sdk.init(**_sentry_options())"
            for statement in node.body
            for call in ast.walk(statement)
            if isinstance(call, ast.Call)
        )
    ]
    assert guarded  # main.py's one init catches the failure: Sentry stays off, and the app starts


def test_the_value_scrubber_reads_the_settings_once_at_startup(monkeypatch, request):
    # The values are read when `_sentry_options()` runs, as main.py's one call does at startup, and never again, by
    # any path: not at the first item, not per item, and a value set afterwards is not withheld.
    import sentry_sdk
    from sentry_sdk import logger as sentry_logger

    import main
    from app.config import settings

    reads = []
    read = main._secret_values
    monkeypatch.setattr(main, "_secret_values", lambda: reads.append("read") or read())
    first, later = (_fabricated(f"INTERNAL_JOB_TOKEN {when}", string.ascii_uppercase) for when in ("first", "later"))
    envelopes = _scrubbing_envelopes(request, monkeypatch, INTERNAL_JOB_TOKEN=first)
    assert reads == ["read"]
    monkeypatch.setattr(settings, "INTERNAL_JOB_TOKEN", later)
    sentry_sdk.capture_message(f"{first} {later}")
    sentry_sdk.capture_message("job failed again")
    sentry_logger.warning("job failed")
    sentry_sdk.flush()
    assert [event["message"] for event in _of(envelopes, "event")] == [f"[Filtered] {later}", "job failed again"]
    assert _of(envelopes, "log") and reads == ["read"]


class _Halt(BaseException):
    """An exception that is not an Exception, as KeyboardInterrupt and SystemExit are not."""


@pytest.mark.parametrize("error", [RuntimeError, _Halt])
def test_a_failing_value_scrubber_sends_nothing(monkeypatch, sentry_envelopes, error):
    # The hooks fail closed: an exception inside one drops its item, which the SDK records as lost to a callback error,
    # instead of sending it unscrubbed, on every channel, whatever the exception. The SDK sends a log or a metric on,
    # unscrubbed, after one that is not an Exception, so each hook raises any failure as one (the round-14 delta
    # check's R14-A1). (A global event processor would fail open: the SDK passes the event on when one raises, and it
    # runs before the request is attached.)
    import sentry_sdk
    from sentry_sdk import logger as sentry_logger
    from sentry_sdk.crons import capture_checkin

    import main

    def failing(*arguments):
        raise error("the scrubber failed")

    monkeypatch.setattr(main, "_withhold", failing)
    with sentry_sdk.start_transaction(name="job"):
        sentry_sdk.capture_message("job failed")
    capture_checkin(monitor_slug="nightly", status="error")
    sentry_logger.warning("job failed")
    sentry_sdk.metrics.count("job.failures", 1)
    sentry_sdk.flush()
    sent = [kind for kind, _ in sentry_envelopes if kind in ("event", "check_in", "transaction", "log", "trace_metric")]
    assert not sent
    lost = _of(sentry_envelopes, "lost")
    for category in ("error", "transaction", "log_item", "trace_metric"):
        assert ["callback_error", category] in lost
    assert lost.count(["callback_error", "error"]) == 2  # the message and the check-in


def test_an_alpha_vantage_error_carries_no_key(monkeypatch, caplog):
    # An HTTPStatusError's message quotes the request URL, whose query carries the key; the client logs it, and the
    # daily refresh, which asks for the error raised, logs its traceback.
    import httpx

    client, key = _alpha_vantage(monkeypatch, 503)
    caplog.set_level(logging.INFO, logger="app.integrations.alpha_vantage")
    assert asyncio.run(client.fetch_earnings_calendar()) == []
    with pytest.raises(httpx.HTTPStatusError) as info:
        asyncio.run(client.fetch_earnings_calendar(raise_on_error=True))
    logged = "\n".join(
        record.getMessage() for record in caplog.records if record.name == "app.integrations.alpha_vantage"
    )
    text = logged + "".join(traceback.format_exception(info.value))
    assert "HTTPStatusError: HTTP 503" in logged
    leaked = _fragments(key, text)
    assert not leaked, f"{leaked} four-character fragments of the fabricated key reached the log or the traceback"


_AV_NOTICES = {
    "daily-limit": '{"Information": "We have detected your API key as {key} and our rate limit is 25 per day."}',
    # The key across the logged cut at 160 characters: withheld before the cut, no prefix of it is left.
    "across-the-cut": '{"Note": "' + "x" * 140 + ' {key} is throttled."}',
}


@pytest.mark.parametrize("raise_on_error", [False, True], ids=["degrade", "raise"])
@pytest.mark.parametrize("notice", list(_AV_NOTICES))
def test_an_alpha_vantage_notice_carries_no_key(monkeypatch, caplog, raise_on_error, notice):
    # Alpha Vantage answers a throttled or refused request with 200 and a JSON notice, which the client logs, and its
    # daily-limit notice has quoted the key; in the service the log line also becomes a Sentry breadcrumb.
    client, key = _alpha_vantage(monkeypatch, 200, _AV_NOTICES[notice])
    caplog.set_level(logging.INFO, logger="app.integrations.alpha_vantage")
    if raise_on_error:
        with pytest.raises(ValueError):
            asyncio.run(client.fetch_earnings_calendar(raise_on_error=True))
    else:
        assert asyncio.run(client.fetch_earnings_calendar()) == []
    logged = "\n".join(
        record.getMessage() for record in caplog.records if record.name == "app.integrations.alpha_vantage"
    )
    assert "non-CSV body" in logged and "[Filter" in logged  # the notice was logged, its key withheld
    leaked = _fragments(key, logged)
    assert not leaked, f"{leaked} four-character fragments of the fabricated key reached the log"


@pytest.mark.parametrize("setup", ["calendar-job", "service"])
def test_the_alpha_vantage_url_stays_out_of_the_request_log(monkeypatch, caplog, setup):
    # httpx logs each request's URL at INFO, and Alpha Vantage's query carries the key. Two setups log at INFO and fetch
    # it: the daily calendar job (its own logging setup) and the service and task worker (configure_logging; the
    # durable earnings-calendar task runs there).
    from app.services import logging_service

    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.syspath_prepend(str(BACKEND_DIR / "scripts"))
    monkeypatch.setattr(logging, "basicConfig", lambda **kwargs: None)  # the test's own handlers stay
    root = logging.getLogger()
    handlers, root_level = root.handlers[:], root.level
    quieted = ("httpx", "httpcore", "urllib3", "edgar", "markdown_it")
    levels = {name: logging.getLogger(name).level for name in quieted}  # configure_logging may have set them already
    for name in quieted:
        logging.getLogger(name).setLevel(logging.NOTSET)
    try:
        if setup == "calendar-job":
            importlib.import_module("earnings_calendar_job")._configure_logging()
        else:
            logging_service.configure_logging(level="INFO")
            root.handlers[:] = handlers  # it replaces the root handlers; caplog's comes back
        client, key = _alpha_vantage(monkeypatch, 200, "symbol,reportDate\n")
        with caplog.at_level(logging.INFO):  # restored on exit, before the finally restores the setup's own level
            asyncio.run(client.fetch_earnings_calendar())
    finally:
        root.handlers[:] = handlers
        root.setLevel(root_level)
        for name, level in levels.items():
            logging.getLogger(name).setLevel(level)  # setLevel, not an attribute write: it clears the level cache
    leaked = _fragments(key, caplog.text)
    assert not leaked, f"{leaked} four-character fragments of the fabricated key reached the {setup}'s log"


def test_the_resend_smoke_prints_no_key(monkeypatch, capsys):
    import dotenv

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)  # never a developer's .env
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.syspath_prepend(str(BACKEND_DIR / "scripts"))
    monkeypatch.delitem(sys.modules, "smoke_resend", raising=False)
    smoke = importlib.import_module("smoke_resend")
    key = "re_" + _fabricated("RESEND_API_KEY")

    async def sent(**kwargs):
        return {"id": "fabricated"}

    monkeypatch.setattr(smoke, "send_email", sent)
    monkeypatch.setattr(smoke.settings, "RESEND_API_KEY", key)
    asyncio.run(smoke.smoke_resend())
    out = capsys.readouterr().out
    assert f"RESEND_API_KEY: set ({len(key)} characters)" in out
    leaked = _fragments(key[3:], out)
    assert not leaked, f"{leaked} four-character fragments of the fabricated key were printed"


def test_redis_logs_no_url(monkeypatch, caplog):
    # A valid URL's pool is logged without it; a URL missing its `@host` puts the password where the port goes, and
    # the port parse's message would quote it.
    from app.services import redis_service

    password = _fabricated("REDIS_URL password")
    for name in ("_pool", "_client", "_init_lock", "_init_lock_loop"):
        monkeypatch.setattr(redis_service, name, None)
    monkeypatch.setattr(redis_service.settings, "SKIP_REDIS_INIT", False)
    caplog.set_level(logging.INFO, logger=redis_service.logger.name)
    for url, created in ((f"redis://:{password}@cache.invalid:6379/0", True), (f"redis://default:{password}/0", False)):
        monkeypatch.setattr(redis_service.settings, "REDIS_URL", url)
        monkeypatch.setattr(redis_service, "_pool", None)
        assert (asyncio.run(redis_service.get_redis_pool()) is not None) is created
    assert "pool created" in caplog.text and "REDIS_URL is malformed (ValueError)" in caplog.text
    leaked = _fragments(password, caplog.text)
    assert not leaked, f"{leaked} four-character fragments of the fabricated password were logged"


def _import_database(monkeypatch, url: str):
    """Import a fresh app.database with this DATABASE_URL; the original module comes back at teardown."""
    from app import config

    monkeypatch.setattr(config.settings, "DATABASE_URL", url)
    app_package = importlib.import_module("app")
    monkeypatch.setattr(app_package, "database", getattr(app_package, "database", None), raising=False)
    monkeypatch.delitem(sys.modules, "app.database", raising=False)
    return importlib.import_module("app.database")


@pytest.mark.parametrize(
    ("shape", "reported"),
    [
        ("postgresql://app:{p}/app", "(ValueError"),
        ("postgresql://app:{p}@{p}@db.invalid/app", "(more than one '@'"),
        ("postgresql://app:{p}@{p}/{p}@db.invalid/app", "(more than one '@'"),
        ("postgresql://app:{p}@{p}?{p}@/app?host=/cloudsql/x", "(more than one '@'"),
    ],
    ids=["host-missing", "at-then-host", "at-then-slash", "at-then-query"],
)
def test_a_malformed_database_url_is_not_quoted(monkeypatch, shape, reported):
    # app.database builds its engine at import, before any handler can withhold a message: a URL missing its `@host`
    # put the password into a service's startup traceback (and Sentry, which main.py starts first), and an unescaped
    # "@" in the password parses, its tail becoming the host, the database or a query key, which the driver's
    # connection error quotes at startup.
    password = _fabricated("DATABASE_URL password")
    with pytest.raises(RuntimeError) as info:
        _import_database(monkeypatch, shape.format(p=password))
    text = "".join(traceback.format_exception(info.value))
    assert f"DATABASE_URL could not be parsed {reported}" in text
    leaked = _fragments(password, text)
    assert not leaked, f"{leaked} four-character fragments of the fabricated password reached the traceback"


@pytest.mark.parametrize(
    "shape",
    [
        "postgresql://app:{p}@/app?host=/cloudsql/x",
        "postgresql://app:{p}%40{p}@db.invalid:5432/app",
        "sqlite:///./x.db",
    ],
    ids=["socket-form", "percent-encoded-at", "sqlite"],
)
def test_a_database_url_with_one_at_is_accepted(monkeypatch, shape):
    # The refusal costs nothing the documented URLs need: the Cloud SQL socket form and an encoded "@" parse as before.
    # The app decodes an encoded "@"; the deploy's migration step and the Ops proxy step split the URL themselves and do
    # not, so the production URL keeps percent-encoding out of its user name and password (docs/CONFIGURATION.md).
    password = _fabricated("DATABASE_URL password")
    database = _import_database(monkeypatch, shape.format(p=password))
    assert database.engine.url.password in (password, f"{password}@{password}", None)


def test_the_database_benchmark_prints_no_password(monkeypatch, capsys):
    # The operator's benchmark reads DATABASE_URL itself: a malformed URL stops it with the parse error's type, and a
    # well-formed one is printed masked. 127.0.0.1:1 refuses the connection at once; nothing leaves the machine.
    import dotenv

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)  # never a developer's .env
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.syspath_prepend(str(BACKEND_DIR / "scripts"))
    monkeypatch.delitem(sys.modules, "validate_db_performance", raising=False)
    script = importlib.import_module("validate_db_performance")
    password = _fabricated("benchmark password")
    digits = _fabricated("benchmark all-digit password", string.digits)
    urls = (
        f"postgresql://app:{password}/app",  # the host missing: the password sits where the port goes
        f"postgresql://app:{password}@{password}@127.0.0.1:1/app?hostaddr=127.0.0.1",  # an "@" in the password: its tail
        f"postgresql://app:{password}@127.0.0.1:1/{password}@db.invalid/app",  # becomes the host, or the database
        f"postgresql://app:{password}@127.0.0.1:1/app",  # well-formed
        f"postgresql://127.0.0.1:1/app?user=app&password={password}",  # a password in the query string
        f"postgresql://app:{digits}/app?hostaddr=127.0.0.1",  # the host missing: an all-digit password parses as the port
        f"postgresql://app:{digits}/{password}/app?hostaddr=127.0.0.1",  # its leading digits so, the rest the database
    )
    for url in urls:
        monkeypatch.setenv("DATABASE_URL", url)
        with pytest.raises(SystemExit):
            script.run_validation()
    out = capsys.readouterr().out
    assert "could not be parsed (ValueError" in out  # the host-missing branch ran
    assert out.count("could not be parsed (more than one '@'") == 2  # so did both "@" refusals
    assert out.count("Database: postgresql at 127.0.0.1\n") == 2  # and the two well-formed URLs'
    assert out.count("Database: postgresql at app\n") == 2  # the host-missing ones: no port, no database printed
    assert out.count("FAILED (connection error): OperationalError (message withheld") == 4  # each connect failed
    leaked = _fragments(password, out) + _fragments(digits, out, width=6)
    assert not leaked, f"{leaked} fragments of the fabricated passwords were printed"


# Settings fields that hold a secret, by name: keys, secrets, tokens, salts, passwords and the DSN, and the two
# connection URLs, whose names do not say they carry a password. Every other field is printable.
_SECRET_SUFFIXES = ("_KEY", "_SECRET", "_TOKEN", "_SALT", "_PASSWORD", "_DSN")
SECRET_FIELDS = frozenset(name for name in Settings.model_fields if name.endswith(_SECRET_SUFFIXES)) | {
    "DATABASE_URL",
    "REDIS_URL",
}
_PRINTABLE = frozenset(Settings.model_fields) - SECRET_FIELDS
# Calls that print, log, warn, write or send to Sentry what they are given, by function or method name.
_OUTPUT_CALLS = {"print", "pprint", "echo", "debug", "info", "warning", "warn", "error", "exception", "critical"} | {
    "fatal",
    "log",
    "write",
    "capture_message",
    "capture_exception",
    "capture_event",
    "set_tag",
    "set_tags",
    "set_context",
    "set_extra",
    "set_user",
    "add_breadcrumb",
    "set_data",
    "set_attribute",
    "set_attributes",
}
# Calls the settings object may be handed whole: none reads a value (`repr()` and `str()` print `Settings()` and
# nothing), and `getattr` is judged by the field it names.
_TAKE_SETTINGS = {"repr", "str", "getattr", "hasattr", "isinstance"}


def _outputs(tree: ast.Module) -> list[ast.expr]:
    """What the module prints: an output call's arguments (`print`, a log, warn or write call, `click.echo`,
    `pprint`, a Sentry message, exception, event, tag, context, extra, user, breadcrumb or span data or attribute),
    and every raise or assert message."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and (
            (isinstance(node.func, ast.Name) and node.func.id in _OUTPUT_CALLS)
            or (isinstance(node.func, ast.Attribute) and node.func.attr in _OUTPUT_CALLS)
        ):
            found.extend([*node.args, *(keyword.value for keyword in node.keywords)])
        elif isinstance(node, ast.Raise):
            found.extend(expr for expr in (node.exc, node.cause) if expr is not None)
        elif isinstance(node, ast.Assert) and node.msg is not None:
            found.append(node.msg)
    return found


def _is_settings(node: ast.AST) -> bool:
    """The settings object, by any path: `settings`, `config.settings`, `deploy_check.settings`."""
    return (isinstance(node, ast.Name) and node.id == "settings") or (
        isinstance(node, ast.Attribute) and node.attr == "settings"
    )


def _is_environ(node: ast.AST) -> bool:
    """The process environment, by any path: `os.environ`, `environ`."""
    return (isinstance(node, ast.Name) and node.id == "environ") or (
        isinstance(node, ast.Attribute) and node.attr == "environ"
    )


def _names_a_secret(name: ast.expr | None) -> bool:
    """An environment variable's name, read: a secret field's, a password's, or any an expression computes."""
    if isinstance(name, ast.Constant) and isinstance(name.value, str):
        return name.value in SECRET_FIELDS or name.value.endswith((*_SECRET_SUFFIXES, "PASSWORD"))
    return True


def _secret_reads(node: ast.AST) -> list[str]:
    """Each read an output expression makes of a secret: on the settings object, anything but a printable field (a
    secret field, or what is no field at all: `model_dump()`, `__dict__`), as an attribute or through `getattr`, and
    the object itself handed whole to a call (`dict(settings)`, `vars(settings)`, `"{0.SECRET_KEY}".format(settings)`),
    unpacked or iterated; on `self`, a secret field (the class's own methods); through `getattr` on anything, a secret
    field named as a literal; in the environment, the mapping whole or a variable `_names_a_secret` names. Not a read:
    inside `len()` or `bool()`, a comparison, or a conditional expression's condition, none of which prints the value,
    and the settings object as an output's own argument or inside the calls `_TAKE_SETTINGS` names."""
    if isinstance(node, ast.IfExp):
        return _secret_reads(node.body) + _secret_reads(node.orelse)
    if isinstance(node, ast.Compare):
        return []
    if isinstance(node, ast.Call):
        function = ast.unparse(node.func)
        if function in {"len", "bool"}:
            return []
        if function == "getattr" and len(node.args) > 1:
            name = node.args[1].value if isinstance(node.args[1], ast.Constant) else None
            if name in SECRET_FIELDS or (_is_settings(node.args[0]) and name not in _PRINTABLE):
                return [ast.unparse(node)]
        if function.endswith("getenv") or (function.endswith(".get") and _is_environ(node.func.value)):
            named = [ast.unparse(node)] if _names_a_secret(node.args[0] if node.args else None) else []
            rest = [*node.args[1:], *(keyword.value for keyword in node.keywords)]  # a default is printed too
            return named + [read for argument in rest for read in _secret_reads(argument)]
        arguments = [*node.args, *(keyword.value for keyword in node.keywords)]
        if function not in _TAKE_SETTINGS and any(_is_settings(argument) for argument in arguments):
            return [ast.unparse(node)]
    if isinstance(node, ast.Subscript) and _is_environ(node.value):
        return [ast.unparse(node)] if _names_a_secret(node.slice) else []
    if _is_environ(node) or (isinstance(node, ast.Starred) and _is_settings(node.value)):
        return [ast.unparse(node)]
    if isinstance(node, ast.comprehension) and _is_settings(node.iter):
        return [f"for {ast.unparse(node.target)} in {ast.unparse(node.iter)}"]
    if isinstance(node, ast.Attribute) and (
        (_is_settings(node.value) and node.attr not in _PRINTABLE)
        or (isinstance(node.value, ast.Name) and node.value.id == "self" and node.attr in SECRET_FIELDS)
    ):
        return [ast.unparse(node)]
    return [read for child in ast.iter_child_nodes(node) for read in _secret_reads(child)]


def test_no_output_reads_a_settings_secret():
    # The "never again" half of the echoes this file closes one by one: no print, log, warn or write call and no
    # raise or assert message anywhere in the backend outside tests reads a secret directly.
    assert {"SECRET_KEY", "DATABASE_URL", "REDIS_URL", "INTERNAL_JOB_TOKEN", "ALPHA_VANTAGE_API_KEY"} <= SECRET_FIELDS
    found = [
        f"{path.relative_to(BACKEND_DIR).as_posix()}:{output.lineno}: {read}"
        for path in _scanned_files()
        for output in _outputs(ast.parse(path.read_text(encoding="utf-8")))
        for read in _secret_reads(output)
    ]
    assert not found, (
        f"An output reads a settings secret: {found}. Print or log its presence or its length (`len(...)`), never "
        "its characters, and a connection URL's parse error by its type (lessons/ops-never-echo-environment-values.md)."
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("logger.info(f'pool for {settings.REDIS_URL}')", ["settings.REDIS_URL"]),
        ("print('key', settings.RESEND_API_KEY[-4:])", ["settings.RESEND_API_KEY"]),
        (
            "logging.getLogger('x').warning('%s', getattr(settings, 'OPENAI_API_KEY'))",
            ["getattr(settings, 'OPENAI_API_KEY')"],
        ),
        ("print(getattr(settings, name))", ["getattr(settings, name)"]),
        ("raise ValueError(f'bad {self.STRIPE_SECRET_KEY}')", ["self.STRIPE_SECRET_KEY"]),
        ("assert ok, f'{settings.SECRET_KEY}'", ["settings.SECRET_KEY"]),
        ("warnings.warn(settings.SENTRY_DSN)", ["settings.SENTRY_DSN"]),
        ("sys.stderr.write(settings.INTERNAL_JOB_TOKEN)", ["settings.INTERNAL_JOB_TOKEN"]),
        ("print(settings.model_dump())", ["settings.model_dump"]),
        ("logger.error(config.settings.DATABASE_URL)", ["config.settings.DATABASE_URL"]),
        ("print(f'{len(settings.SECRET_KEY)} characters', bool(settings.STRIPE_WEBHOOK_SECRET))", []),
        ("print(settings.STRIPE_SECRET_KEY.startswith('sk_live_') == True)", []),
        ("logger.info('model %s', settings.AI_DEFAULT_MODEL)", []),
        ("client = Client(settings.OPENAI_API_KEY)", []),
        ("print(f'{len(settings.RESEND_API_KEY)}' if settings.RESEND_API_KEY else 'NOT SET')", []),
        ("print(settings.RESEND_API_KEY if settings.RESEND_API_KEY else 'NOT SET')", ["settings.RESEND_API_KEY"]),
        ("print(settings)", []),
        ("print(repr(settings), str(settings), getattr(settings, 'AI_DEFAULT_MODEL'))", []),
        ("print(dict(settings))", ["dict(settings)"]),
        ("print(vars(settings))", ["vars(settings)"]),
        ("logger.info('%s', list(settings))", ["list(settings)"]),
        ("print('{0.SECRET_KEY}'.format(settings))", ["'{0.SECRET_KEY}'.format(settings)"]),
        ("print(*settings)", ["*settings"]),
        ("print({k: v for k, v in settings})", ["for (k, v) in settings"]),
        ("print(os.environ.get('DATABASE_URL'))", ["os.environ.get('DATABASE_URL')"]),
        ("logger.info(os.environ['OPENAI_API_KEY'])", ["os.environ['OPENAI_API_KEY']"]),
        ("print(os.getenv(name), environ['PGPASSWORD'])", ["os.getenv(name)", "environ['PGPASSWORD']"]),
        ("print(dict(os.environ))", ["os.environ"]),
        ("print(os.environ.get('ENVIRONMENT'), os.environ['PORT'])", []),
        ("print(os.getenv('ENVIRONMENT', settings.SECRET_KEY))", ["settings.SECRET_KEY"]),
        ("console.print(settings.STRIPE_SECRET_KEY)", ["settings.STRIPE_SECRET_KEY"]),
        ("click.echo(settings.RESEND_API_KEY)", ["settings.RESEND_API_KEY"]),
        ("pprint(settings.SECRET_KEY)", ["settings.SECRET_KEY"]),
        ("sentry_sdk.set_tag('token', settings.INTERNAL_JOB_TOKEN)", ["settings.INTERNAL_JOB_TOKEN"]),
        ("sentry_sdk.capture_message(f'url {settings.DATABASE_URL}')", ["settings.DATABASE_URL"]),
        ("sentry_sdk.set_tags({'k': settings.INTERNAL_JOB_TOKEN})", ["settings.INTERNAL_JOB_TOKEN"]),
        ("sentry_sdk.set_user({'id': settings.SECRET_KEY})", ["settings.SECRET_KEY"]),
        ("sentry_sdk.capture_exception(RuntimeError(settings.DATABASE_URL))", ["settings.DATABASE_URL"]),
        ("span.set_data('url', settings.REDIS_URL)", ["settings.REDIS_URL"]),
        ("span.set_attribute('key', settings.RESEND_API_KEY)", ["settings.RESEND_API_KEY"]),
    ],
    ids=[
        "log",
        "print",
        "getattr",
        "computed-getattr",
        "raise",
        "assert",
        "warn",
        "write",
        "dump",
        "module-path",
        "length-and-presence",
        "compare",
        "not-a-secret",
        "not-an-output",
        "condition",
        "conditional-value",
        "repr",
        "repr-str-printable-getattr",
        "dict",
        "vars",
        "list",
        "format",
        "unpacked",
        "iterated",
        "environment-get",
        "environment-subscript",
        "environment-computed-and-password",
        "environment-whole",
        "environment-printable",
        "environment-default",
        "console-print",
        "echo",
        "pprint",
        "sentry-tag",
        "sentry-message",
        "sentry-tags",
        "sentry-user",
        "sentry-exception",
        "span-data",
        "span-attribute",
    ],
)
def test_the_output_gate_flags_a_secret_read(source, expected):
    assert [read for output in _outputs(ast.parse(source)) for read in _secret_reads(output)] == expected


def _compare_digest_calls(tree: ast.Module) -> list[tuple[int, list[ast.expr]]]:
    """Each compare_digest call, by its own name or a name `from hmac|secrets import compare_digest as ...` gives it."""
    names = {"compare_digest"} | {
        alias.asname
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module in {"hmac", "secrets"}
        for alias in node.names
        if alias.name == "compare_digest" and alias.asname
    }
    return [
        (node.lineno, node.args)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (getattr(node.func, "attr", None) == "compare_digest" or getattr(node.func, "id", None) in names)
    ]


def _utf8(call: ast.Call, position: int) -> bool:
    """The call's codec, positional at `position` or `encoding=`, is absent or names UTF-8."""
    codec = next((keyword.value for keyword in call.keywords if keyword.arg == "encoding"), None)
    codec = call.args[position] if len(call.args) > position else codec
    return codec is None or (isinstance(codec, ast.Constant) and str(codec.value).lower().replace("-", "") == "utf8")


def _is_bytes(arg: ast.expr) -> bool:
    """Bytes by its form, for any str: a bytes literal, a `.digest()`, a UTF-8 `.encode(...)` or `bytes(x, ...)`, a
    base64 encoding of bytes or a `token_bytes(...)`; another codec (`ascii`) raises on a non-ASCII value, the same
    500, and so do `b64decode` and `bytes.fromhex` on a malformed caller value, so they stay flagged."""
    if isinstance(arg, ast.Constant):
        return isinstance(arg.value, bytes)
    if not isinstance(arg, ast.Call):
        return False
    name = arg.func.attr if isinstance(arg.func, ast.Attribute) else getattr(arg.func, "id", None)
    if name in {"b64encode", "urlsafe_b64encode", "standard_b64encode"}:
        return len(arg.args) == 1 and _is_bytes(arg.args[0])
    if name == "token_bytes":
        return True
    if isinstance(arg.func, ast.Attribute) and arg.func.attr in {"digest", "encode"}:
        return arg.func.attr == "digest" or _utf8(arg, 0)
    codec_given = len(arg.args) > 1 or any(keyword.arg == "encoding" for keyword in arg.keywords)
    return isinstance(arg.func, ast.Name) and arg.func.id == "bytes" and codec_given and _utf8(arg, 1)


def _not_bytes(args: list[ast.expr]) -> bool:
    """compare_digest raises TypeError on a non-ASCII str: each argument must be bytes by its form."""
    return len(args) != 2 or not all(_is_bytes(arg) for arg in args)


def test_compare_digest_takes_bytes():
    # A caller-supplied str that is not ASCII (a header decodes as latin-1) makes compare_digest raise TypeError: a 500
    # where a 401 belongs, an error event, and a captured frame holding the expected secret.
    found, seen = [], 0
    for path in _scanned_files():
        for line, args in _compare_digest_calls(ast.parse(path.read_text(encoding="utf-8"))):
            seen += 1
            if _not_bytes(args):
                found.append(f"{path.relative_to(BACKEND_DIR).as_posix()}:{line}")
    assert seen >= 5  # internal.py, webhooks.py, auth.py (two), oauth_verify.py
    assert not found, f"compare_digest on a str raises TypeError for a non-ASCII value; pass .encode()d bytes: {found}"


@pytest.mark.parametrize(
    ("source", "flagged"),
    [
        ("hmac.compare_digest(header, expected)", True),
        ("secrets.compare_digest(header.encode(), expected)", True),
        ("compare_digest(header.encode(), expected.encode())", False),
        ("hmac.compare_digest(header.encode('utf-8'), b'x')", False),
        ("from hmac import compare_digest as same\nsame(header, expected.encode())", True),
        ("hmac.compare_digest(mac.digest(), bytes(header, 'utf-8'))", False),
        ("hmac.compare_digest(mac.hexdigest(), header.encode())", True),
        ("hmac.compare_digest(header.encode('ascii'), b'x')", True),
        ("hmac.compare_digest(bytes(header, encoding='ascii'), b'x')", True),
        ("hmac.compare_digest(bytes(header), b'x')", True),
        ("hmac.compare_digest(bytes(header, encoding='utf-8'), b'x')", False),
        ("hmac.compare_digest(base64.b64encode(mac.digest()), header.encode())", False),
        ("hmac.compare_digest(base64.b64encode(header), b'x')", True),
        ("hmac.compare_digest(base64.b64decode(header), mac.digest())", True),
        ("hmac.compare_digest(secrets.token_bytes(16), b'x')", False),
    ],
    ids=[
        "str",
        "one-str",
        "bytes",
        "bytes-literal",
        "aliased-str",
        "digest-and-bytes",
        "hexdigest",
        "ascii",
        "bytes-ascii",
        "bytes-of-a-name",
        "bytes-utf-8-keyword",
        "base64-of-a-digest",
        "base64-of-a-str",
        "base64-decode",
        "token-bytes",
    ],
)
def test_the_compare_digest_gate_flags_a_str(source, flagged):
    ((_, args),) = _compare_digest_calls(ast.parse(source))
    assert _not_bytes(args) is flagged
