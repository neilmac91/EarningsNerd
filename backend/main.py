from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
import asyncio
import re
import threading
from functools import lru_cache
from typing import Any, Callable
from urllib.parse import quote_plus, unquote, unquote_plus
from dotenv import load_dotenv
from sqlalchemy.engine import make_url

# Load environment variables early (Settings reads .env itself; the pre-Settings bootstrap
# constants in database.py / redis_service.py / edgar/config.py read os.environ directly).
load_dotenv()

from app.config import settings, APP_VERSION

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


_Hook = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


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
    own path in its own kind of item. They also drop the hint's attachments, whose bytes would reach Sentry through no
    hook: the backend sends none."""

    _placeholder(secret_values)  # every placeholder overlapped fails here, at startup, not on the first item

    def hook(paths: Callable[[dict[str, Any]], frozenset[tuple[str, ...]]], types: frozenset[str]) -> _Hook:
        def withhold_secret_values(item: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any]:
            hint.pop("attachments", None)  # the SDK sends what is left there after the hook, unscrubbed
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


# Initialize Sentry for error tracking (must be done before FastAPI app creation)
try:
    import sentry_sdk
except ImportError:
    print("Sentry SDK not available - install sentry-sdk for error tracking")
else:
    if settings.SENTRY_DSN:
        try:
            sentry_sdk.init(**_sentry_options())
            print("✓ Sentry error tracking initialized")
        except Exception as e:
            # A malformed DSN or init failure must never block application startup
            print(f"⚠️  Sentry initialization failed ({e}) - error tracking disabled")
    else:
        print("⚠️  SENTRY_DSN not configured - error tracking disabled")

from app.database import engine, Base, get_db, ensure_additive_columns
from app.services.event_loop import set_app_loop
from app.services.logging_service import (
    configure_logging,
    CorrelationIdMiddleware,
    get_logger,
)

# Initialize logger for startup messages
logger = get_logger(__name__)
from app.routers import (
    analysis,
    companies,
    filings,
    summaries,
    auth,
    users,
    subscriptions,
    saved_summaries,
    watchlist,
    sitemap,
    notable_filings,
    reporting_this_week,
    email,
    contact,
    feedback,
    webhooks,
    admin,
    internal,
    dashboard,
    search,
    peers,
    insiders,
    calendar,
)

def _run_on_daemon_thread(loop: asyncio.AbstractEventLoop, name: str, step) -> asyncio.Future:
    """Run a blocking startup step on a daemon thread and resolve a loop future with its outcome.

    Unlike ``loop.run_in_executor`` the thread is never joined at loop shutdown, so a step that
    hangs past its deadline cannot pin the process after startup has already failed.
    """
    future = loop.create_future()

    def settle(setter, value) -> None:
        if not future.done():
            setter(value)

    def worker() -> None:
        try:
            result = step()
        except BaseException as exc:  # noqa: BLE001 — surfaced to the awaiting lifespan
            outcome, setter = exc, future.set_exception
        else:
            outcome, setter = result, future.set_result
        try:
            loop.call_soon_threadsafe(settle, setter, outcome)
        except RuntimeError:
            pass  # the loop is already closed: startup failed on the deadline and the process is exiting

    threading.Thread(target=worker, name=f"startup-{name}", daemon=True).start()
    return future


# Create database tables
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - run sync DB operation in thread pool to avoid blocking event loop
    loop = asyncio.get_running_loop()
    # Sync bridges (BackgroundTask bodies, threadpool work) hand coroutines to THIS loop via
    # run_coroutine_threadsafe instead of spinning private loops — see app/services/event_loop.py.
    set_app_loop(loop)

    async def bounded_startup_step(name: str, step) -> None:
        # E12b: a schema step that hangs (lock contention with the draining revision, a slow
        # database) must fail the start within a known deadline, so Cloud Run keeps serving the
        # last healthy revision instead of waiting out its own startup timeout. The step runs on
        # a DAEMON thread rather than the default executor: a hung executor thread would be
        # joined at loop shutdown and keep the failed container alive after the error.
        try:
            await asyncio.wait_for(
                _run_on_daemon_thread(loop, name, step), timeout=settings.STARTUP_SCHEMA_DEADLINE_SECONDS
            )
        except asyncio.TimeoutError:
            logger.critical(
                "%s did not finish within STARTUP_SCHEMA_DEADLINE_SECONDS=%s",
                name, settings.STARTUP_SCHEMA_DEADLINE_SECONDS,
            )
            raise RuntimeError(f"Cannot start application: {name} timed out") from None

    await bounded_startup_step("create_all", lambda: Base.metadata.create_all(bind=engine))
    # create_all() never ALTERs existing tables, so self-apply small additive columns that post-date
    # a table's original CREATE (e.g. the FPI alert prefs) — keeps deployed code + schema in sync
    # without a manual migration step. Idempotent + non-fatal per column (see
    # database.ensure_additive_columns); only exceeding the step deadline fails the start.
    await bounded_startup_step("ensure_additive_columns", ensure_additive_columns)

    # Validate database connection at startup
    from sqlalchemy import text

    def _validate_db_connection():
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            return True

    try:
        await asyncio.wait_for(
            loop.run_in_executor(None, _validate_db_connection),
            timeout=5.0
        )
        logger.info("Database connection validated successfully")
    except asyncio.TimeoutError:
        logger.critical("Database connection validation timed out")
        raise RuntimeError("Cannot start application: database connection timed out")
    except Exception as e:
        logger.critical(f"Database connection failed: {e}")
        raise RuntimeError(f"Cannot start application: database unreachable - {e}")

    # Validate the AI provider configuration (OpenAI-compatible client; DeepSeek, ADR-0008)
    is_valid, warnings = settings.validate_openai_config()

    if warnings:
        logger.warning("AI provider configuration warnings:")
        for warning in warnings:
            logger.warning(f"  - {warning}")
    if is_valid:
        logger.info(f"AI provider configured: base_url={settings.OPENAI_BASE_URL}, model={settings.AI_DEFAULT_MODEL}")
    else:
        logger.error("AI provider configuration is invalid. AI summaries may not work.")

    # Validate Stripe configuration
    stripe_valid, stripe_warnings = settings.validate_stripe_config()
    if stripe_warnings:
        logger.warning("Stripe Configuration Warnings:")
        for warning in stripe_warnings:
            logger.warning(f"  - {warning}")
    if stripe_valid:
        logger.info("Stripe configured: API key present")
        if settings.STRIPE_WEBHOOK_SECRET:
            logger.info("Stripe webhook secret configured: subscription events will be processed")
        else:
            logger.warning("Stripe webhook secret not configured: subscription events will fail")
    else:
        logger.error("Stripe configuration is invalid. Subscription features will be disabled.")

    # Validate outbound email (Resend) — email is on the verify-first signup path, so a wrong
    # sender silently breaks registration. Log the effective From so it's verifiable from the logs.
    resend_valid, resend_warnings = settings.validate_resend_config()
    if resend_warnings:
        logger.warning("Email (Resend) configuration warnings:")
        for warning in resend_warnings:
            logger.warning(f"  - {warning}")
    if resend_valid:
        logger.info(f"Email configured: sending from {settings.RESEND_FROM_EMAIL}")
    else:
        logger.error(
            "Email (Resend) configuration is invalid. Outbound email (verification, "
            "password reset) will fail."
        )

    # Initialize Redis connection pool (with timeout to prevent hanging in CI/test)
    from app.services.redis_service import get_redis_pool, check_redis_health, close_redis

    if not settings.SKIP_REDIS_INIT:
        REDIS_INIT_TIMEOUT = 3.0  # Fast fail for CI environments
        try:
            await asyncio.wait_for(get_redis_pool(), timeout=REDIS_INIT_TIMEOUT)
            redis_health = await check_redis_health()
            if redis_health.get("healthy"):
                logger.info(f"Redis connected: latency={redis_health.get('latency_ms', 'N/A')}ms")
            else:
                logger.warning(f"Redis not available: {redis_health.get('error', 'unknown error')} (caching degraded)")
        except asyncio.TimeoutError:
            logger.warning("Redis initialization timed out (caching degraded)")
        except Exception as e:
            logger.warning(f"Redis initialization failed: {e} (caching degraded)")
    else:
        logger.info("Redis initialization skipped (SKIP_REDIS_INIT=true)")

    yield

    # Shutdown
    set_app_loop(None)
    await close_redis()
    logger.info("Redis connections closed")

    # Shutdown EdgarTools thread pool
    from app.services.edgar.async_executor import shutdown_executor
    shutdown_executor(wait=True)
    logger.info("EdgarTools thread pool shut down")

app = FastAPI(
    title="EarningsNerd API",
    description="AI-powered SEC filing analysis and summarization",
    version=APP_VERSION,
    lifespan=lifespan
)

# Configure structured logging
configure_logging(
    level="DEBUG" if settings.ENVIRONMENT == "development" else "INFO",
    json_format=settings.ENVIRONMENT == "production",
)

# Correlation ID middleware (adds X-Correlation-ID to all requests)
app.add_middleware(CorrelationIdMiddleware)

# CORS middleware
# More restrictive in production, flexible in development
_cors_config = {
    "allow_origins": settings.CORS_ORIGINS,
    "allow_credentials": True,
    # Explicit methods instead of wildcard for security
    "allow_methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    # Explicit headers for security - include common auth and content headers
    "allow_headers": [
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "X-Requested-With",
        "X-Correlation-ID",
        # Cloudflare Turnstile token headers the auth/contact/waitlist forms attach
        # (see app/services/turnstile.py:_TOKEN_HEADERS). Without these the browser
        # preflight is rejected with "Disallowed CORS headers" the moment Turnstile is
        # enabled, surfacing as "Unable to connect to the server" on the client.
        "cf-turnstile-response",
        "x-turnstile-token",
    ],
    "expose_headers": ["X-Correlation-ID"],
}

# Only allow localhost regex in development (for various dev server ports)
if settings.ENVIRONMENT != "production":
    _cors_config["allow_origin_regex"] = r"http://localhost:\d+"

app.add_middleware(CORSMiddleware, **_cors_config)


def _error_response_cors_headers(request: Request) -> dict[str, str]:
    """CORS headers for hand-built error responses (exception handlers).

    Starlette runs the generic-``Exception`` handler inside ServerErrorMiddleware, which sits
    OUTSIDE CORSMiddleware — so a 500 it produces never gets ``Access-Control-Allow-Origin``.
    The browser then blocks the cross-origin response and the client sees an opaque network
    error ("Unable to connect to the server") instead of the real status/detail, masking every
    server error as connectivity loss. Re-apply the same origin allow-list the middleware uses
    so error responses stay readable cross-origin.
    """
    origin = request.headers.get("origin")
    if not isinstance(origin, str):
        return {}
    allowed = origin in settings.CORS_ORIGINS or (
        settings.ENVIRONMENT != "production"
        and re.fullmatch(r"http://localhost:\d+", origin) is not None
    )
    if not allowed:
        return {}
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
        "Vary": "Origin",
    }

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    if settings.ENVIRONMENT == "production":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'")
    return response


# Request timeout middleware
# Configurable timeouts per endpoint pattern
REQUEST_TIMEOUT_SECONDS = {
    "default": 30.0,
    "/api/summaries/": 120.0,  # Summary generation needs more time
    "/api/filings/": 60.0,     # Filing fetches from SEC EDGAR
    "/health": 5.0,            # Health checks should be fast
}

# Suffix-matched timeouts for routes where a variable segment precedes the action
# (e.g. /api/companies/{ticker}/insiders), which a prefix match can't reach.
# Checked after the prefix table. Keep these above the corresponding service-level
# timeout so the inner timeout fires first with a specific error.
REQUEST_TIMEOUT_SUFFIXES = {
    "/insiders": 75.0,  # live Form 4 fan-out across many filings (fetch caps at 60s)
}


def get_timeout_for_path(path: str) -> float:
    """Get the appropriate timeout for a request path."""
    for pattern, timeout in REQUEST_TIMEOUT_SECONDS.items():
        if pattern != "default" and path.startswith(pattern):
            return timeout
    for suffix, timeout in REQUEST_TIMEOUT_SUFFIXES.items():
        if path.endswith(suffix):
            return timeout
    return REQUEST_TIMEOUT_SECONDS["default"]


@app.middleware("http")
async def request_timeout_middleware(request: Request, call_next):
    """
    Apply request-level timeouts to prevent hung connections.

    Excludes streaming endpoints (SSE) which manage their own timeouts.
    """
    path = request.url.path

    # Skip timeout for streaming endpoints (they have their own timeout handling)
    if "stream" in path.lower() or path.endswith("/progress"):
        return await call_next(request)

    timeout = get_timeout_for_path(path)

    try:
        return await asyncio.wait_for(call_next(request), timeout=timeout)
    except asyncio.TimeoutError:
        from fastapi.responses import JSONResponse
        # Re-apply the CORS allow-origin headers: this middleware sits OUTSIDE CORSMiddleware, so a
        # 504 it synthesizes never passes back through CORSMiddleware. Without them the browser
        # blocks the cross-origin 504 and the client sees an opaque "Unable to connect to the
        # server" instead of the real timeout — the same masking the 503/500 handlers already guard
        # against (see _error_response_cors_headers).
        return JSONResponse(
            status_code=504,
            content={
                "detail": f"Request timed out after {timeout}s",
                "path": path,
                "timeout_seconds": timeout
            },
            headers=_error_response_cors_headers(request),
        )

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(companies.router, prefix="/api/companies", tags=["Companies"])
app.include_router(peers.router, prefix="/api/companies", tags=["Peers"])
app.include_router(insiders.router, prefix="/api/companies", tags=["Insiders"])
app.include_router(filings.router, prefix="/api/filings", tags=["Filings"])
app.include_router(summaries.router, prefix="/api/summaries", tags=["Summaries"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(subscriptions.router, prefix="/api/subscriptions", tags=["Subscriptions"])
app.include_router(saved_summaries.router, prefix="/api/saved-summaries", tags=["Saved Summaries"])
app.include_router(watchlist.router, prefix="/api/watchlist", tags=["Watchlist"])
app.include_router(watchlist.waitlist_router, prefix="/api/waitlist", tags=["Waitlist"])
app.include_router(sitemap.router, tags=["SEO"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"])
app.include_router(notable_filings.router, prefix="/api", tags=["Notable Filings"])
app.include_router(reporting_this_week.router, prefix="/api", tags=["Reporting This Week"])
app.include_router(search.router, prefix="/api/search", tags=["Search"])
app.include_router(email.router, prefix="/api/email", tags=["Email"])
app.include_router(contact.router, prefix="/api/contact", tags=["Contact"])
app.include_router(feedback.router, prefix="/api/feedback", tags=["Feedback"])
app.include_router(webhooks.router, prefix="/api", tags=["Webhooks"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(internal.router, prefix="/internal", tags=["Internal"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(calendar.router, prefix="/api/calendar", tags=["Calendar"])


# SEC EDGAR circuit-breaker handler: when the breaker is open we are deliberately
# failing fast to protect a struggling upstream. Surface that as a friendly, retryable
# 503 instead of a generic 500 (CircuitOpenError does not subclass EdgarError, so the
# routers' `except SECEdgarServiceError` handlers would otherwise miss it).
from app.services.edgar.circuit_breaker import CircuitOpenError


@app.exception_handler(CircuitOpenError)
async def circuit_open_exception_handler(request: Request, exc: CircuitOpenError):
    from fastapi.responses import JSONResponse

    retry_after = int(exc.time_until_recovery) if exc.time_until_recovery else 30
    logger.warning(
        f"Circuit '{exc.circuit_name}' open on {request.method} {request.url.path}; "
        f"returning 503 (retry in ~{retry_after}s)"
    )
    return JSONResponse(
        status_code=503,
        headers={"Retry-After": str(retry_after), **_error_response_cors_headers(request)},
        content={
            "detail": "SEC EDGAR is temporarily unavailable. Please retry shortly.",
            "retry_after_seconds": retry_after,
        },
    )


# Global exception handler for unhandled errors
from app.services.durable_tasks import TaskUnavailable


@app.exception_handler(TaskUnavailable)
async def task_handoff_exception_handler(request: Request, exc: TaskUnavailable):
    from fastapi.responses import JSONResponse
    logger.error("Durable task handoff unavailable path=%s", request.url.path)
    return JSONResponse(
        status_code=503, headers=_error_response_cors_headers(request),
        content={"detail": "Background work could not be queued. Please retry."},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch-all exception handler for unhandled errors.
    Provides consistent error response format and logs the error.
    """
    from fastapi.responses import JSONResponse

    # Log the error with full context
    logger.exception(
        f"Unhandled exception on {request.method} {request.url.path}: {exc}"
    )

    # Report to Sentry if available
    try:
        import sentry_sdk
        sentry_sdk.capture_exception(exc)
    except ImportError:
        pass

    # Return a generic error response (don't leak internal details in production)
    error_detail = str(exc) if settings.ENVIRONMENT != "production" else "An unexpected error occurred"

    return JSONResponse(
        status_code=500,
        content={
            "detail": error_detail,
            "type": "internal_server_error",
        },
        headers=_error_response_cors_headers(request),
    )


@app.get("/")
async def root():
    return {
        "message": "EarningsNerd API",
        "version": APP_VERSION,
        "status": "operational"
    }

@app.get("/health")
async def health_check():
    """Basic health check for load balancer."""
    return {"status": "healthy"}


@app.get("/health/detailed")
async def health_check_detailed():
    """
    Detailed health check with dependency verification.

    Checks:
    - Database connectivity
    - Redis connectivity (if configured)

    Returns degraded status if any non-critical dependency is unhealthy.
    Returns unhealthy status if critical dependencies (database) are down.
    """
    import time
    from sqlalchemy import text
    from app.database import SessionLocal
    from app.services.redis_service import check_redis_health

    health_status = {
        "status": "healthy",
        "checks": {},
        "timestamp": time.time()
    }

    # The complete probe owns its session in one worker; a slow pool/driver must not
    # block the event loop or move a live session between threads.
    def check_database() -> dict:
        start = time.perf_counter()
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            return {
                "healthy": True,
                "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            }

    try:
        health_status["checks"]["database"] = await run_in_threadpool(check_database)
    except Exception as e:
        # This endpoint is unauthenticated, so never surface raw exception text (a driver error can
        # embed the connection string / host). Log the detail server-side; report only a coarse flag.
        logger.error("health/detailed: database check failed: %s", e, exc_info=True)
        health_status["checks"]["database"] = {
            "healthy": False,
        }
        health_status["status"] = "unhealthy"

    # Check Redis connectivity
    redis_health = await check_redis_health()
    health_status["checks"]["redis"] = redis_health

    # Redis is non-critical - degrade but don't fail
    if not redis_health.get("healthy"):
        if health_status["status"] == "healthy":
            health_status["status"] = "degraded"

    # Check circuit breaker status
    from app.services.edgar.circuit_breaker import edgar_circuit_breaker
    cb_status = edgar_circuit_breaker.get_status()
    health_status["checks"]["sec_edgar_circuit"] = {
        "state": cb_status["state"],
        "healthy": cb_status["state"] != "open",
        "stats": {
            "total_requests": cb_status["stats"]["total_requests"],
            "success_rate": round(cb_status["stats"]["success_rate"], 1),
            "rejected_requests": cb_status["stats"]["rejected_requests"],
        }
    }

    # Circuit breaker open is degraded (not unhealthy - we have fallbacks)
    if cb_status["state"] == "open":
        if health_status["status"] == "healthy":
            health_status["status"] = "degraded"

    # Return appropriate HTTP status
    from fastapi.responses import JSONResponse
    if health_status["status"] == "unhealthy":
        return JSONResponse(status_code=503, content=health_status)
    elif health_status["status"] == "degraded":
        return JSONResponse(status_code=200, content=health_status)

    return health_status


@app.get("/robots.txt", include_in_schema=False)
async def robots_txt():
    """Serve robots.txt for the API host: disallow everything.

    This host serves JSON (plus /sitemap.xml, which exists only for the frontend's proxy) —
    there is nothing here worth indexing, and the old partial allow left /sitemap.xml (an
    uncached-at-the-time DB scan) and every non-/api/ path open to crawler traffic. The
    crawlable site and its sitemap live at https://www.earningsnerd.io.
    """
    from fastapi.responses import PlainTextResponse
    content = """# EarningsNerd API - robots.txt
# This host serves the JSON API only; nothing here should be crawled or indexed.
# The website (and its sitemap) is at https://www.earningsnerd.io

User-agent: *
Disallow: /
"""
    return PlainTextResponse(content=content, media_type="text/plain")


@app.get("/metrics", tags=["Monitoring"])
async def get_metrics(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
    db=Depends(get_db),
):
    """Application metrics — admin only."""
    from app.routers.auth import get_current_user
    user = await get_current_user(request, credentials, db)
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    from app.services.metrics_service import get_all_metrics
    return await get_all_metrics()
