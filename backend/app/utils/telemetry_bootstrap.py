"""Sentry's start for each backend process, and the scrubbing every item passes through (moved from main.py).

Importing it loads app.config, the standard library and sqlalchemy.engine's URL parser, nothing else: never
sentry_sdk (each function imports what it needs, so a failure there is caught with init's own), main, the database,
a model, a router or a service. So the API (main.py) can start Sentry before it imports the app.
"""
import logging
import re
from functools import lru_cache
from typing import Any, Callable, Literal, NamedTuple
from urllib.parse import quote_plus, unquote, unquote_plus

from sqlalchemy.engine import make_url

from app.config import settings
from app.utils.feedback_privacy import withhold_feedback_event

# Settings that hold a secret, by name: keys, secrets, tokens, salts, passwords and the DSN, and the two connection
# URLs, whose names do not say they carry a password. The gate keeps its own copy of this rule, the oracle its tests
# read.
_SECRET_SUFFIXES = ("_KEY", "_SECRET", "_TOKEN", "_SALT", "_PASSWORD", "_DSN")
_CONNECTION_URLS = ("DATABASE_URL", "REDIS_URL")
# The shortest text Sentry's value scrubber withholds. Settings bound no secret's length but SECRET_KEY's (32), and the
# shortest real secret, the Alpha Vantage key, has 16 characters; a shorter text is no credential (a port, which the URL
# rule below reads as a password when a URL has no `@`, has at most 5 digits) and would garble ids, timestamps and SQL
# wherever it occurred by chance, and an empty one (most secret settings' default) would match everywhere.
_MIN_SECRET_LENGTH = 8


def _url_passwords(url: str) -> set[str]:
    """A connection URL's password wherever a driver reads one, as written and percent-decoded: what follows the user
    name's `:` up to the last `@` of the URL's authority (its text before the first `/`, `?` or `#`) or, in a URL
    missing its `@host`, up to the authority's end, where a parser reads the port and a driver's error quotes it as
    one; each `password` query parameter, also plus-decoded and as SQLAlchemy renders it (quote_plus), which
    SQLAlchemy passes to the driver (and renders whole, hide_password or not) and redis-py reads; and the password
    SQLAlchemy parses, decoded, which may hold a raw `/`, `?` or `#` that ends the authority. A bracketed (IPv6) host
    without an `@` holds no password."""
    authority = re.split("[/?#]", url.partition("://")[2], maxsplit=1)[0]
    userinfo, at, host = authority.rpartition("@")
    password = (userinfo if at else "" if host.startswith("[") else host).partition(":")[2]
    passwords = {password, unquote(password)}
    for pair in url.partition("?")[2].partition("#")[0].split("&"):
        key, _, value = pair.partition("=")
        if unquote_plus(key) == "password":
            passwords |= {value, unquote(value), unquote_plus(value)}
    try:
        parsed = make_url(url)
    except Exception:  # a URL SQLAlchemy cannot parse reaches no engine; the rules above still apply
        return passwords
    query = parsed.query.get("password", ())
    read = set((query,) if isinstance(query, str) else query)
    rendered = {quote_plus(value, errors="replace") for value in read}  # a lone surrogate must not fail Sentry's init
    return passwords | {parsed.password or ""} | read | rendered


def _secret_values() -> tuple[str, ...]:
    """Each secret setting's value and each connection URL's password, longest first (a URL is withheld whole before its
    password is looked for), none shorter than _MIN_SECRET_LENGTH. A value is stripped: an echo of it as held contains
    the stripped text, and so does one that escapes a stored newline (a header value's repr). A setting that holds no
    text (None) is skipped."""
    values: set[str] = set()
    for name in type(settings).model_fields:
        value = getattr(settings, name)
        if isinstance(value, str) and (name.endswith(_SECRET_SUFFIXES) or name in _CONNECTION_URLS):
            value = value.strip()
            values |= {value} | (_url_passwords(value) if name in _CONNECTION_URLS else set())
    return tuple(sorted((value for value in values if len(value) >= _MIN_SECRET_LENGTH), key=lambda v: (-len(v), v)))


# Where the protocol puts its own keys, by item kind: the path of each key of _MIN_SECRET_LENGTH characters or more,
# from an item's top through the keys above it (a list's items share the list's path), as the SDK builds each kind under
# main's options: an error (its exceptions, their mechanisms and frames, its threads' frames, breadcrumbs and the
# serializer's `_meta` note on them, log entry, request and user, and the dynamic sampling context of the trace it is
# captured in, which names the transaction heading that trace), a transaction (its spans, request, user and response
# context), a check-in (its monitor config, and the trace context of a span it is captured in), a log and a metric, each
# with the SDK info, the trace context's keys and its dynamic sampling context's where it carries them, and the names
# the SDK fills from its API or a request's incoming trace (an event's `fingerprint`; the replay fields an incoming
# baggage header carries into the dynamic sampling context); a transaction or a check-in captured once its scope has
# dropped breadcrumbs past `max_breadcrumbs` also carries `breadcrumbs` with an empty `values` list and the serializer's
# `_meta` note on it. The value scrubber keeps a key only at one of its item kind's paths, so a weak secret equal to one
# of their words (or inside one) leaves the item's structure whole and the SDK finds the keys it reads after the hook
# (an event's `event_id`, a log's `attributes`, a profile's `contexts.trace.trace_id`), while the same word anywhere
# else (in user data, in a context the app set, as a user's own key, in a structure the app nested in the protocol's, at
# another kind's path: a log's `attributes` written into an error) is scrubbed like any key. A shorter key needs no
# entry (no secret fits in it), so the lists are complete for that floor, on the structures the gate's capture builds;
# the gate derives each kind's paths from the SDK's items there and fails on a missing one there or a dead one.
# Continuous profiling, which main does not configure, would add `contexts.profile.profiler_id`.
_PROTOCOL_PATHS = {
    kind: frozenset(tuple(path.split(".")) for path in paths.split())
    for kind, paths in {
        "error": """
        _meta.breadcrumbs breadcrumbs breadcrumbs.values.category breadcrumbs.values.timestamp contexts
        contexts.trace.description contexts.trace.dynamic_sampling_context
        contexts.trace.dynamic_sampling_context.environment contexts.trace.dynamic_sampling_context.public_key
        contexts.trace.dynamic_sampling_context.replay_id contexts.trace.dynamic_sampling_context.sample_rand
        contexts.trace.dynamic_sampling_context.sample_rate contexts.trace.dynamic_sampling_context.trace_id
        contexts.trace.dynamic_sampling_context.transaction contexts.trace.dynamic_sampling_context.user_segment
        contexts.trace.parent_span_id contexts.trace.trace_id environment event_id exception exception.values.mechanism
        exception.values.mechanism.exception_id exception.values.mechanism.is_exception_group
        exception.values.mechanism.parent_id exception.values.stacktrace exception.values.stacktrace.frames.abs_path
        exception.values.stacktrace.frames.context_line exception.values.stacktrace.frames.filename
        exception.values.stacktrace.frames.function exception.values.stacktrace.frames.post_context
        exception.values.stacktrace.frames.pre_context fingerprint logentry logentry.formatted platform
        request.query_string sdk.integrations sdk.packages server_name threads.values.stacktrace
        threads.values.stacktrace.frames.abs_path threads.values.stacktrace.frames.context_line
        threads.values.stacktrace.frames.filename threads.values.stacktrace.frames.function
        threads.values.stacktrace.frames.post_context threads.values.stacktrace.frames.pre_context timestamp transaction
        transaction_info user.username
        """,
        "transaction": """
        _meta.breadcrumbs breadcrumbs contexts contexts.response contexts.response.status_code
        contexts.trace.description contexts.trace.dynamic_sampling_context
        contexts.trace.dynamic_sampling_context.environment contexts.trace.dynamic_sampling_context.public_key
        contexts.trace.dynamic_sampling_context.replay_id contexts.trace.dynamic_sampling_context.sample_rand
        contexts.trace.dynamic_sampling_context.sample_rate contexts.trace.dynamic_sampling_context.trace_id
        contexts.trace.dynamic_sampling_context.transaction contexts.trace.dynamic_sampling_context.user_segment
        contexts.trace.parent_span_id contexts.trace.trace_id environment event_id measurements platform
        request.query_string sdk.integrations sdk.packages server_name spans.description spans.parent_span_id
        spans.same_process_as_parent spans.start_timestamp spans.timestamp spans.trace_id start_timestamp timestamp
        transaction transaction_info user.username
        """,
        "check_in": """
        _meta.breadcrumbs breadcrumbs check_in_id contexts contexts.trace.description
        contexts.trace.dynamic_sampling_context contexts.trace.dynamic_sampling_context.environment
        contexts.trace.dynamic_sampling_context.public_key contexts.trace.dynamic_sampling_context.replay_id
        contexts.trace.dynamic_sampling_context.sample_rand contexts.trace.dynamic_sampling_context.sample_rate
        contexts.trace.dynamic_sampling_context.trace_id contexts.trace.dynamic_sampling_context.transaction
        contexts.trace.dynamic_sampling_context.user_segment contexts.trace.parent_span_id contexts.trace.trace_id
        duration environment event_id monitor_config monitor_config.checkin_margin
        monitor_config.failure_issue_threshold monitor_config.max_runtime monitor_config.recovery_threshold
        monitor_config.schedule monitor_config.timezone monitor_slug platform sdk.integrations sdk.packages server_name
        timestamp
        """,
        "log": """
        attributes severity_number severity_text time_unix_nano trace_id
        """,
        "metric": """
        attributes timestamp trace_id
        """,
    }.items()
}
# The `type` the SDK gives each kind of item, which it reads after the hook: before_send's check-in, a transaction's,
# a metric's kinds (an error and a log carry none). Each hook keeps an item's `type` only when it is one of its own
# kind's, so another kind's word written there is withheld like any value (Codex's case on #1297).
_ITEM_TYPES = {
    "event": frozenset({"check_in"}),
    "transaction": frozenset({"transaction"}),
    "log": frozenset(),
    "metric": frozenset({"counter", "gauge", "distribution"}),
}

# The placeholder of the SDK's own scrubber, then others: a secret value that overlaps one (a weak salt equal to
# `Filtered`, or one that starts with `Filtered]`) would ride inside it, or form where it meets the text around it.
_PLACEHOLDERS = ("[Filtered]", "[Withheld]", "[Redacted]", "<Filtered>", "<Withheld>", "<Redacted>")


def _overlaps(secret: str, placeholder: str) -> bool:
    """Whether a secret can occur in a text once a placeholder stands in it: inside the placeholder, around it, or
    across either of its edges (the secret ending in the placeholder's start, or starting with its end)."""
    edges = range(1, len(placeholder))
    return (
        secret in placeholder
        or placeholder in secret
        or any(secret.endswith(placeholder[:i]) or secret.startswith(placeholder[i:]) for i in edges)
    )


@lru_cache(maxsize=8)
def _placeholder(secret_values: tuple[str, ...]) -> str:
    """The first placeholder no secret value overlaps, the SDK's own `[Filtered]` unless a weak secret does: no
    placeholder can then hold a secret or form one with the text beside it, however often the text is replaced. If
    every placeholder overlaps one, this raises, and main's startup turns Sentry off rather than send one."""
    for placeholder in _PLACEHOLDERS:
        if not any(_overlaps(secret, placeholder) for secret in secret_values):
            return placeholder
    raise ValueError("every placeholder overlaps a secret setting's value")


def _withhold(
    node: Any,
    secret_values: tuple[str, ...],
    kept: frozenset[tuple[str, ...]] = frozenset(),
    path: tuple[str, ...] | None = (),
) -> Any:
    """The node with each occurrence of each secret value, in any text at any depth, keys too, replaced by the
    placeholder (`_placeholder`: the SDK's own `[Filtered]` unless a secret overlaps it). A key stays as it is only at
    one of `kept`, the paths the protocol gives the item's kind (`_PROTOCOL_PATHS`; none by default): `path` is the keys
    above the node, a list's items sharing the list's, and None below a key that is not exactly text (a str subclass
    could pose as one), where no key stays.
    Mappings and lists are walked; None and booleans stay as they are; a number comes back as int's or float's own
    value, exactly a number, and a text is scrubbed by str's own `replace`, which returns exactly text: the SDK keeps a
    subclass of either as it is up to the hooks, the log batcher makes text of a number through its own `__str__` or
    `__repr__` after the hook (a log's body, a value in a mapping or mixed-list attribute), and a subclass's `replace`
    could keep the secret. Any other value becomes its repr first, scrubbed: the SDK would turn it into text after the
    hook (a log record's `extra` value, a log's body that is not text), where nothing scrubs it."""
    if node is None or type(node) is bool:
        return node
    if isinstance(node, int):
        return int.__index__(node)
    if isinstance(node, float):
        return float.__float__(node)
    if isinstance(node, dict):
        withheld: dict[Any, Any] = {}
        for key, value in node.items():
            here = (*path, key) if path is not None and type(key) is str else None
            name = key if here in kept else _withhold(key, secret_values)
            withheld[name] = _withhold(value, secret_values, kept, here)
        return withheld
    if isinstance(node, list):
        return [_withhold(item, secret_values, kept, path) for item in node]
    if not isinstance(node, str):
        from sentry_sdk.utils import safe_repr

        node = safe_repr(node)
    placeholder = _placeholder(secret_values)
    for secret in secret_values:
        node = str.replace(node, secret, placeholder)  # str's own: a subclass's replace could keep the secret
    return node


_Hook = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any] | None]


def _value_scrubber(secret_values: tuple[str, ...]) -> dict[str, _Hook]:
    """Sentry's hooks on every channel that carries text, one per channel: an error or a check-in (`event`, set as
    before_send), a transaction with its spans (`transaction`, before_send_transaction), a log (`log`, before_send_log)
    and a metric (`metric`, before_send_metric). A hook that raises drops its item (the SDK records a callback error),
    so a failure here never sends one unscrubbed: each hook raises any failure as an Exception, since the SDK sends a
    log or a metric on after one that is not. Each keeps only the protocol's own keys where the protocol puts them in
    its item's kind, never a field whole: a key at one of that kind's `_PROTOCOL_PATHS` (`_withhold`; before_send tells
    a check-in by its `type`, exactly text) and an item's `type` when it is one of that kind's `_ITEM_TYPES`. So a weak
    secret equal to one of their words breaks no item, and nothing that runs before the hooks (an event processor, a
    hand-built event, a trace context set by hand) can carry a secret past them, but as the protocol's own key at its
    own path in its own kind of item, or, through an item's `type` that is a text subclass, scrubbed by its channel's
    paths and sent as its text says, at another kind's (the SDK writes every type as plain text). They also drop the
    hint's attachments, whose bytes would reach Sentry through no hook: the backend sends none."""

    _placeholder(secret_values)  # every placeholder overlapped fails here, at startup, not on the first item

    def hook(paths: Callable[[dict[str, Any]], frozenset[tuple[str, ...]]], types: frozenset[str]) -> _Hook:
        def withhold_secret_values(item: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
            hint.pop("attachments", None)  # the SDK sends what is left there after the hook, unscrubbed
            if withhold_feedback_event(item):
                # Private text, pasted URLs, SQL parameters and parser details can appear in
                # multiple SDK fields. Withhold these requests entirely instead of guessing
                # which event field contains user evidence. Content-free outcome analytics
                # remain in the feedback router, independent of error reporting.
                return None
            try:
                scrubbed = _withhold(item, secret_values, paths(item))
            except BaseException as error:  # the SDK sends a log or a metric on after any failure but an Exception
                raise RuntimeError("the value scrubber failed") from error
            kind = item.get("type")
            if type(kind) is str and kind in types:  # exactly text: a subclass could pose as one
                scrubbed["type"] = kind
            return scrubbed

        return withhold_secret_values

    def event_paths(item: dict[str, Any]) -> frozenset[tuple[str, ...]]:
        kind = item.get("type")
        return _PROTOCOL_PATHS["check_in" if type(kind) is str and kind == "check_in" else "error"]

    return {
        "event": hook(event_paths, _ITEM_TYPES["event"]),
        "transaction": hook(lambda item: _PROTOCOL_PATHS["transaction"], _ITEM_TYPES["transaction"]),
        "log": hook(lambda item: _PROTOCOL_PATHS["log"], _ITEM_TYPES["log"]),
        "metric": hook(lambda item: _PROTOCOL_PATHS["metric"], _ITEM_TYPES["metric"]),
    }


def _sentry_options() -> dict:
    """sentry_sdk.init's options; the gate builds a capturing client from them (tests/unit/
    test_never_echo_environment_values.py). The integrations are imported here, so a failure among them is caught
    with init's own and never blocks startup."""
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    from sentry_sdk.scrubber import DEFAULT_DENYLIST, EventScrubber

    # The event scrubber below matches key names; these hooks match values. They read the settings once, here at
    # startup: nothing changes them afterwards.
    hooks = _value_scrubber(_secret_values())
    return {
        "dsn": settings.SENTRY_DSN,
        "environment": settings.ENVIRONMENT,
        # Release = deployed git SHA (CI sets SENTRY_RELEASE=$GITHUB_SHA on Cloud Run), so
        # errors are attributable to an exact revision. None → Sentry's default detection.
        "release": settings.SENTRY_RELEASE or None,
        "traces_sample_rate": 0.1,  # 10% of transactions for performance monitoring
        "profiles_sample_rate": 0.1,  # 10% of sampled transactions for profiling
        "integrations": [FastApiIntegration(transaction_style="endpoint"), SqlalchemyIntegration()],
        # Don't send PII
        "send_default_pii": False,
        # No frame's local variables: a secret copied into a local, every library frame holding the request (its
        # ASGI scope, its headers) and the database driver's connect frames (the decoded password) would otherwise
        # ride on each captured error, and so would a user's password in an auth request's frames. The exception and
        # its chain, each frame's file, function, line and source lines, breadcrumbs, the request and tags stay.
        "include_local_variables": False,
        # The scrubber matches exact key names, and the SDK withholds only its own short list of headers: the
        # internal-job header carries INTERNAL_JOB_TOKEN, an outbound request's query string (on breadcrumbs and
        # spans) carries Alpha Vantage's key, and request bodies (on errors and sampled transactions) carry users'
        # credentials: a password change's passwords, a refresh token, an invite, Apple's form-posted code and
        # id_token. Never pass `data_collection`: it drops this scrubber and brings frame variables back.
        "event_scrubber": EventScrubber(
            denylist=[
                *DEFAULT_DENYLIST,
                "x-internal-token",
                "http.query",
                "new_password",
                "current_password",
                "refresh_token",
                "invite",
                "invite_code",
                "code",
                "id_token",
            ]
        ),
        # Each secret setting's value and each connection URL's password, wherever an item holds it (the protocol's own
        # keys and item types aside: `_value_scrubber`), on every channel that carries text; `before_send` and
        # `before_send_transaction` run after the event scrubber and the serializer, and the log and metric hooks get
        # their items unserialized. Never set `max_value_length`: the serializer would cut a string inside a secret and
        # leave a prefix no hook matches. `before_send_span` acts only under span streaming (`trace_lifecycle`), which
        # stays off.
        "before_send": hooks["event"],
        "before_send_transaction": hooks["transaction"],
        "before_send_log": hooks["log"],
        "before_send_metric": hooks["metric"],
    }




# What an event from the task worker or a task child keeps: what failed and where, never what it failed on. Everything
# else is dropped before the API's value scrubber runs: an exception's value and notes (a pydantic error quotes the
# payload, a RuntimeError its job's counts), a log record's message and arguments (an f-string template can hold data),
# breadcrumbs, the request (a task's body is its envelope: an account mail's address), extra (sys.argv), user, modules,
# threads, every context but the trace's ids, the dynamic sampling context (and with it the envelope's trace header)
# and every tag but task.kind. An allowlist: a key the SDK adds later stays out until it is named here.
_TASK_EVENT_KEYS = frozenset(
    {"event_id", "timestamp", "level", "platform", "logger", "release", "environment", "server_name", "sdk"}
    | {"exception", "contexts", "tags"}
)
_TASK_EXCEPTION_KEYS = frozenset({"type", "module", "mechanism", "stacktrace"})
_TASK_MECHANISM_KEYS = frozenset({"type", "handled", "exception_id", "parent_id", "source", "is_exception_group"})
_TASK_FRAME_KEYS = frozenset(
    {"filename", "abs_path", "module", "function", "lineno", "colno", "in_app", "context_line"}
    | {"pre_context", "post_context"}
)
_TASK_TRACE_KEYS = frozenset({"trace_id", "span_id", "parent_span_id", "op", "status"})
_TASK_KIND = re.compile(r"[a-z_]{1,32}")
# The one wait a failed task child spends sending its event: the SDK's own shutdown_timeout. A failure answers 503
# whether the child exits 1 after it or the worker kills it at its deadline during it, so the wait changes no result.
TASK_FLUSH_SECONDS = 2.0


def _pick(node: Any, keys: frozenset[str]) -> dict[str, Any]:
    return {key: node[key] for key in keys & node.keys()} if isinstance(node, dict) else {}


def _task_event(event: dict[str, Any]) -> dict[str, Any] | None:
    """The part of an error a task process may send (`_TASK_EVENT_KEYS`), or None for any other kind (a check-in)."""
    if event.get("type") is not None:
        return None
    kept = _pick(event, _TASK_EVENT_KEYS)
    values = []
    for entry in (kept.pop("exception", None) or {}).get("values") or []:
        exception = _pick(entry, _TASK_EXCEPTION_KEYS)
        if "mechanism" in exception:
            exception["mechanism"] = _pick(exception["mechanism"], _TASK_MECHANISM_KEYS)
        if "stacktrace" in exception:
            frames = (exception["stacktrace"] or {}).get("frames") or []
            exception["stacktrace"] = {"frames": [_pick(frame, _TASK_FRAME_KEYS) for frame in frames]}
        values.append(exception)
    if values:
        kept["exception"] = {"values": values}
    trace = (kept.pop("contexts", None) or {}).get("trace")
    if isinstance(trace, dict):
        kept["contexts"] = {"trace": _pick(trace, _TASK_TRACE_KEYS)}
    tags = kept.pop("tags", None)
    kind = tags.get("task.kind") if isinstance(tags, dict) else None
    if type(kind) is str and _TASK_KIND.fullmatch(kind):
        kept["tags"] = {"task.kind": kind}
    return kept


def _task_hooks(event_hook: _Hook) -> dict[str, Callable[[dict[str, Any], dict[str, Any]], Any]]:
    """A task process's hooks: before_send keeps `_task_event`'s part of an error, then runs the API's own event hook
    (the value scrubber) on it, last; the others send nothing. Each fails closed: a raise drops the item."""

    def send_error_identity(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
        hint.pop("attachments", None)  # the SDK sends what is left there after the hook, unscrubbed
        try:
            kept = _task_event(event)
        except BaseException as error:  # the SDK sends an item on after any failure but an Exception
            raise RuntimeError("the task event filter failed") from error
        return None if kept is None else event_hook(kept, hint)

    def send_nothing(item: dict[str, Any], hint: dict[str, Any]) -> None:
        hint.pop("attachments", None)
        return None

    return {"event": send_error_identity, "transaction": send_nothing, "log": send_nothing, "metric": send_nothing}


def _task_sentry_options() -> dict:
    """The task worker's and the task child's options: the API's (`_sentry_options()`: its DSN, release, environment,
    event scrubber, no frame variables, no PII), with only an ERROR log line becoming an event (no breadcrumbs, no ASGI
    or SQL instrumentation, no auto-enabled integration), no transactions or profiles, no request body, and hooks
    that send an error's type and stack only (`_task_hooks`), the API's value scrubber last."""
    from sentry_sdk.integrations.atexit import AtexitIntegration
    from sentry_sdk.integrations.dedupe import DedupeIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    options = _sentry_options()
    hooks = _task_hooks(options["before_send"])
    options.update(
        default_integrations=False,
        integrations=[
            LoggingIntegration(level=None, event_level=logging.ERROR, sentry_logs_level=None),
            AtexitIntegration(),
            DedupeIntegration(),
        ],
        traces_sample_rate=None,
        profiles_sample_rate=None,
        max_request_body_size="never",
        before_send=hooks["event"],
        before_send_transaction=hooks["transaction"],
        before_send_log=hooks["log"],
        before_send_metric=hooks["metric"],
    )
    return options


class SentryStart(NamedTuple):
    """How a process's Sentry start went, from a closed set, and an init failure's text (the API prints it)."""

    status: str  # initialized, already, unconfigured, unavailable or failed
    error: str = ""


_started: str | None = None  # the process whose client this module started


def init_sentry(process: Literal["api", "worker", "task"]) -> SentryStart:
    """Start Sentry once in this process: the API with `_sentry_options()`, any other with `_task_sentry_options()`.
    The backend's one init; never raises and prints nothing."""
    global _started
    try:
        import sentry_sdk
    except ImportError:
        return SentryStart("unavailable")
    if not settings.SENTRY_DSN:
        return SentryStart("unconfigured")
    if _started is not None or sentry_sdk.is_initialized():
        return SentryStart("already")  # a second init would replace the first client and abandon its queue
    try:
        sentry_sdk.init(**(_sentry_options() if process == "api" else _task_sentry_options()))
    except Exception as error:
        # A malformed DSN or init failure must never block application startup
        return SentryStart("failed", str(error))
    _started = process
    return SentryStart("initialized")


def report_task_failure(error: BaseException, kind: str | None) -> None:
    """Send a failed task child's exception (its type and stack: `_task_event`) with its validated kind, waiting at most
    TASK_FLUSH_SECONDS, and close the client, so nothing waits again at exit. Sentry starts here, on failure only: a
    task that succeeds never loads the SDK. Never raises: the child exits 1 whatever telemetry does."""
    try:
        init_sentry("task")
        if _started != "task":
            return  # no DSN, no SDK, a failed start, or a client this module did not start for a task
        import sentry_sdk

        with sentry_sdk.new_scope() as scope:
            if kind is not None:
                scope.set_tag("task.kind", kind)
            scope.capture_exception(error)
        sentry_sdk.get_client().close(timeout=TASK_FLUSH_SECONDS)
    except BaseException:  # noqa: BLE001 — telemetry never changes a task's result
        pass
