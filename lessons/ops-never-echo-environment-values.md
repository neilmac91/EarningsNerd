# Never let a settings error, an output or Sentry carry a secret

Date: 2026-10-11 (follow-ups 2026-10-12, todo E16) · Area: ops / secrets

**Context.** On two consecutive days a review agent imported `app.config` outside the test harness to
probe a detail, and environment values reached its own tool output (CODE RED records 22 and 23). The
second time, the settings class failed validation in the container's real environment, and pydantic's
error appended its input: the environment-derived settings dict, shortened to its two ends, carrying a
fragment of a real AI-provider key and a base URL. The same error shape prints a too-short `SECRET_KEY`
whole, or a production `DATABASE_URL` with its password when it is the dict's last or only entry, into a
service's startup log or CI's public log. Review of the fix found four more paths:
- the error's structured form keeps the input;
- a settings object's repr carried every value, which Sentry's default local-variable capture sends with a
  captured error from any frame that holds `settings`;
- a validator's own message can quote a value, which no pydantic setting hides;
- `scripts/deploy_check.py` printed the first 30 characters of every value it checked, secrets included, and
  its two database checks printed an error message that can quote the database password.

The follow-up review (todo E16) found the rest:
- an error a library raises inside a validator (a URL or port parse) prints whole: `hide_input_in_errors` hides
  the input pydantic appends, not the message of an error raised inside a validator;
- Sentry serialized every captured frame's local variables. A secret copied out of `settings` into a local
  rode along; so did every library frame holding an `/internal/` request (its ASGI scope, its headers), the
  database driver's connect frames on a connection failure (SQLAlchemy's `cparams`, psycopg2's `dsn`: the
  decoded password), and a user's password in an auth request's frames. Sentry also sent the `X-Internal-Token`
  header (its own header filter and its default scrubber match exact names only), on transactions too, each
  outbound request's query string, unsanitized, where the Alpha Vantage key travels, and a request body, JSON or
  form, on the error and on every sampled transaction, where the scrubber withheld `password` and `token` but not a
  password change's `new_password` and `current_password`, a `refresh_token`, an `invite` or `invite_code`, or
  Apple's form-posted `code` and `id_token`;
- `hmac.compare_digest` raises `TypeError` on a non-ASCII `str`, and Starlette decodes headers as latin-1: a
  non-ASCII `X-Internal-Token` was a 500 whose captured frame held the token, and the Resend webhook's
  signature, the Google state and the Apple nonce checks had the same shape;
- an Alpha Vantage HTTP error's message quotes the request URL with the key, and the daily calendar job, which
  logs at INFO with the key mounted, let httpx log every request URL;
- `app/database.py` parses `DATABASE_URL` at import, so a URL missing its `@host` put the password into a
  service's startup traceback (and into Sentry, which `main.py` starts first), and an unescaped `@` in the password
  parsed, its tail becoming the host that the driver's connection error quotes at startup; `redis_service` logged
  `REDIS_URL` whole and its parse error's message; `scripts/smoke_resend.py` printed the key's last four
  characters; `scripts/validate_db_performance.py` printed a URL without an `@` whole, and a password passed in the URL's
  query string survived SQLAlchemy's masked rendering.

**Rule.**
- The settings class sets `hide_input_in_errors`, so a validation error's text (`str`, `repr`, and so a
  traceback or a log line) names the failing field and its reason, never its value. The one exception is
  `REGISTRATION_MODE`'s validator, which quotes its value by design: the field holds no secret.
- The setting does not reach the error's structured form: `errors()` and `json()` return every input,
  whole, unless called with `include_input=False`. An `except` block that calls either on its caught
  exception passes it.
- The setting does not reach a validator's own message either. A raise or assert message in `app/config.py`
  reads only literals, lengths (`len(v)`) and module constants bound to immutable literals; a raise inside an
  `except` or `finally` block says `from None`, or its traceback prints the error it handled. A validator never
  lets a library's error (`urlsplit(v).port`, `int(v)`) escape with its message.
- A settings object prints no value: the class overrides `__repr_args__`, so `repr()` is `Settings()` and
  `str()` is empty.
- Sentry sends no frame's local variables (`include_local_variables=False` in `main._sentry_options`), and its
  event scrubber withholds the `X-Internal-Token` header, every outbound request's `http.query` and a request body's
  `new_password`, `current_password`, `refresh_token`, `invite`, `invite_code`, `code` and `id_token` (beside the SDK's
  own `password` and `token`), on errors and transactions alike. Never configure
  `data_collection` (nor `_experiments.data_collection`): the SDK then drops the event scrubber and brings frame
  variables back, whatever `include_local_variables` says. What an event still carries: the exception type,
  message and chain; every frame's file, function, line and five source lines either side; breadcrumbs (log
  lines at INFO and above, SQL statements, HTTP calls without their query string); the request's method, URL
  and query string, other headers and body; the user id, tags, release and environment.
- Nothing prints or logs a secret. An output reports a secret's presence and length, never a character; a
  connection URL's parse error is reported by its type, and an HTTP error from a keyed URL by its status, never
  their messages; a database URL whose host holds an `@` is refused; httpx's request log stays at WARNING where a
  key travels in a query string. No print, log,
  warn or write call and no raise or assert message reads a secret field, or the settings object beyond a
  printable field (`model_dump()`, `__dict__`), directly.
- `hmac.compare_digest` and `secrets.compare_digest` compare bytes (`.encode()` both sides).
- `scripts/deploy_check.py` prints a secret's presence and length, never its characters, and a database
  error's type, never its message. The model id and the provider base URL are identifiers, not secrets, and
  are printed by design.
- An agent's ad-hoc probe of application code (`python -c`, a scratch script) runs under
  `env -i PATH=/usr/bin:/bin` in a copy with no `.env` file at any level (a `git archive` export, not a
  checkout). Importing `app.config` builds the module-level `settings` from the working directory's `.env`,
  whatever a later `Settings(_env_file=None)` does. `main.py`'s `load_dotenv()`, like
  `scripts/smoke_resend.py`'s and `scripts/validate_db_performance.py`'s, loads the `.env` it finds above
  its own file into the environment.

**Gate.** `backend/tests/unit/test_never_echo_environment_values.py`:
- **The setting.** It pins the setting and proves that both leaking shapes are withheld: a field's own
  failing value, and the missing-field input dict. A control class with pydantic's default shows that the
  same errors echo the value.
- **The structured form.** An AST walk over every backend Python file outside `tests/` (the entrypoints,
  the application, its scripts and its evals) fails any `except ... as name` block, whatever it catches,
  that calls `name.errors()` or `name.json()` without `include_input=False`; a pin fails when a new
  directory of backend code is left out of the walk (a top-level virtualenv is skipped by its `pyvenv.cfg`,
  whatever its name). It reads only the block's own direct calls on the bound name. Outside it: an alias
  (`f = exc.errors`), or `getattr`; a helper the exception is handed to; a FastAPI exception-handler function;
  an except* group's members. None exists today.
- **The repr.** A settings object's `repr()` is `Settings()`, its `str()` is empty, and Sentry's
  serialization of it is `Settings()`.
- **Messages.** An AST walk over `app/config.py` fails a raise or assert message, in a function or at module
  level, that reads anything but literals and `len(...)`, directly, through a name or through a raise's
  `from` cause. It denies by default:
  - a name counts through every expression its scope binds to it (tuple targets, loop variables, `:=` and
    mutator calls: `append`, `extend`, `insert`, `add`, `update`, `setdefault`, keyword arguments
    included). When the scope binds it in no way at all, the name counts through every expression the
    module binds to it. So `MIN_SECRET_KEY_LENGTH = 32` reads nothing and a module name bound to
    `os.environ[...]` reads the environment;
  - a name reads itself, whatever is stored into it, when a parameter, an import, a def, a class,
    `except ... as`, `with ... as` or a match capture binds it (so `settings = Settings()` reads the class, a
    call of a module function counts, and `self.cache = 1` leaves `self.SECRET_KEY` a read), when a function
    stores into or mutates a module name, and when it is bound to a list, dict or set literal (an alias, a
    helper or a dunder call can fill it unseen);
  - every call counts except a call of a builtin exception class (a CapWords name neither the scope nor the
    module binds) or `sorted`;
  - a raise without `from` inside an `except` or `finally` block counts as quoting the exception being
    handled, which a traceback prints; `from None` drops it.

  One sanctioned quotation is allowed: `REGISTRATION_MODE`'s `v`. The test also pins the settings class's
  only base and the absence of an `Annotated` validator, so a validator cannot move out of the walk unseen.
- **Library messages.** Every settings field but `REGISTRATION_MODE` is built from four values shaped to break a
  parse (the value alone, a URL missing its `@host`, a URL whose every part is the value, a `host:port` pair),
  each carrying a sentinel; no error's full traceback, chained exceptions included, may hold it. A control
  class whose validator parses a port shows the shapes reach such a call and that pydantic prints its message.
- **The checks.** `deploy_check`'s environment and configuration checks print no 4-character fragment of a
  fabricated secret on any branch: long keys, 12-character keys (the "appears too short" warnings), and
  production with a `sk_test_` secret key and a `pk_live_` publishable key (the mode warnings); each case
  asserts its branch ran. Its two database checks, fed a URL that puts a fabricated password where the port
  goes, print the error's type and no fragment.
- **Outputs.** `smoke_resend` prints the key's length; `redis_service` builds a pool from a URL holding a
  password and refuses a URL missing its `@host`; importing `app.database` with such a URL, or with an `@`
  in its host, raises a `RuntimeError`; the database benchmark stops on both, prints a well-formed URL's backend,
  host and database only (a query-string password included in the test) and its errors by type; an Alpha Vantage 503 is
  logged and raised as `HTTP 503`; the calendar job's logging setup and the service's `configure_logging` keep httpx's request log off. None prints
  or logs a 4-character fragment of the fabricated secret. An AST walk over every backend file outside `tests/`
  fails a print, log, warn or write call's argument, or a raise or assert message, that reads `settings.X` or
  `getattr(settings, ...)` for anything but a printable field, `self.X` for a secret field, or
  `getattr(obj, "X")` for a secret field, outside `len()`, `bool()`, a comparison and a conditional
  expression's condition. A secret field is one whose name ends in `_KEY`, `_SECRET`, `_TOKEN`, `_SALT` or
  `_DSN`, and the two connection URLs.
- **Sentry.** Built from `main._sentry_options()` with a fabricated DSN and a transport that keeps each
  envelope, a fixture fails if the options turn local variables back on, send PII or pass `data_collection`.
  An `/internal/` request whose enqueue fails (a 500 whose frames hold the token in a copied local and in every
  framework frame) and one whose background job fails after the 202 send their errors and three transactions
  with the header `[Filtered]`, no `vars` and no 8-character fragment of the token; a non-ASCII header is a
  401. An Alpha Vantage request's breadcrumb and span carry `http.query` as `[Filtered]` and no fragment of the
  key. Routes that fail on a JSON body and on a form body holding a fabricated credential under each withheld key
  send each as `[Filtered]`, on the errors and the transactions. main.py's one init call takes `_sentry_options()`
  and nothing else.
- **compare_digest.** An AST walk fails any `compare_digest` call in the backend whose two arguments are not
  both `.encode(...)` calls or bytes literals.

The agent clause is not machine-gated and stays session reading.

**Known ungated echoes**, each a follow-up:
- `scripts/refresh_index_membership.py --source fmp` logs an HTTP error's message (the FMP URL with its key) and
  lets httpx log each request URL at INFO; the monthly workflow uses the keyless Wikipedia source (todo E17);
- a provider's own error text can quote a masked key's last four characters (Stripe's and the AI providers'
  invalid-key messages): callers log it, and `app/routers/subscriptions.py` returns Stripe's message as the
  checkout and portal error detail (todo E18);
- an incoming request's query string reaches Sentry unscrubbed: the Google OAuth callback's single-use `code`
  (a user's, not a settings secret);
- `main.py`'s startup database check and `/health/detailed` log a driver's connection error, which names the host,
  port, user and database; it carries no password once the URL parses with a clean host;
- `main.py`'s Sentry init-failure line prints a malformed DSN's parse message (its scheme, its project path, or
  the port segment of a legacy key pair without a host); the DSN's key is public by Sentry's design;
- Sentry scrubs keys, not values: a secret in a log message (a breadcrumb), an exception message or an extra is
  kept out only at its source. The output walk sees only a direct read, not an alias
  (`url = settings.REDIS_URL`), a helper the value is handed to or an object holding it (`stripe.api_key`), and
  the message walk reads `app/config.py` only and does not follow `globals()`, `setattr` or `sys.modules`;
- the library-message test drives four shapes, one field at a time, as constructor arguments: a parse that
  fails only on other input, on two fields together or only from the environment is not exercised.

**Evidence.** `backend/app/config.py` (`class Config`, `__repr_args__`); `backend/main.py` (`_sentry_options`);
`backend/app/routers/internal.py` (`_require_internal_token`); `backend/app/database.py` (`_database_url`);
`backend/app/services/redis_service.py` (`get_redis_pool`); `backend/app/integrations/alpha_vantage.py`
(`fetch_earnings_calendar`); `backend/scripts/earnings_calendar_job.py` (`_configure_logging`);
`backend/scripts/deploy_check.py`; `backend/scripts/smoke_resend.py`; `backend/scripts/validate_db_performance.py`;
sentry-sdk 2.71.0: `client.py` (`_get_options`: `data_collection` drops `event_scrubber`; `_prepare_event`: the
scrubber, then `serialize` with `max_value_length`, then `before_send`), `utils.py` (`serialize_frame`,
`walk_exception_chain` honours `__suppress_context__`), `data_collection.py` (`stack_frame_variables` follows
`include_local_variables` only without `data_collection`), `integrations/httpx.py` (`parse_url(...,
sanitize=False)`), `integrations/_wsgi_common.py` (`SENSITIVE_HEADERS`), `scrubber.py` (`DEFAULT_DENYLIST`, exact
key matches); CODE RED records 22 (disclosure 4) and 23 (disclosure 3).
