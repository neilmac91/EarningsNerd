# Never let a settings error, an output or Sentry carry a secret

Date: 2026-10-11 (follow-ups 2026-10-12, #1281; value scrubber 2026-10-13, todo E19) · Area: ops / secrets

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

The follow-up review (#1281) found the rest:
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
  signature and the Google state checks had the same shape (the Apple nonce check compared a `str` too, but its
  caller turns any error into the `apple_invalid` redirect);
- an Alpha Vantage HTTP error's message quotes the request URL with the key, the client logged the first 160
  characters of a throttle notice, which can quote the key ("We have detected your API key as ..."), and the daily
  calendar job, which logs at INFO with the key mounted, let httpx log every request URL;
- `app/database.py` parses `DATABASE_URL` at import, so a URL missing its `@host` put the password into a
  service's startup traceback (and into Sentry, which `main.py` starts first), and an unescaped `@` in the password
  parsed, its tail becoming the host, the database or a query key, which the driver's connection error quotes at
  startup; `redis_service` logged `REDIS_URL` whole and its parse error's message; `scripts/smoke_resend.py`
  printed the key's last four characters; `scripts/validate_db_performance.py` printed a URL without an `@` whole,
  and its hand-rolled mask kept a password passed in the URL's query string and an unescaped `@`'s tail.

Codex's review of #1281 found the last: Sentry's scrubber matches key names, so a secret's value quoted in a message,
an exception or a log line (a breadcrumb), or held under any key its denylist does not name (an extra, a tag, a
context, a request, a span's data), still reached Sentry; a `DATABASE_URL` missing its `@host` with an all-digit
password parses, and the driver's connection error quotes the digits as the port. Building the value scrubber showed
one more channel: the SDK's own logger and metrics API send logs and metrics past `before_send` and the event
scrubber, whatever `enable_logs` says. Its review found where text is still made after the hooks: the SDK builds the
repr of a log record's `extra` value (anything but text, a number or a list of one such type; a mapping and a mixed
list included) and the str of a log's body that is not text only after `before_send_log` returns.

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
- Sentry sends no frame's local variables (`include_local_variables=False` in `main._sentry_options`), and its event
  scrubber withholds the `X-Internal-Token` header, every outbound request's `http.query` and a request body's
  `new_password`, `current_password`, `refresh_token`, `invite`, `invite_code`, `code` and `id_token` (beside the
  SDK's own `password` and `token`), on errors and transactions alike; every request body key in the API that names a
  credential is in that list and at the body's top level, where the scrubber looks. Never configure `data_collection`
  (nor `_experiments.data_collection`): the SDK then drops the event scrubber and brings frame variables back,
  whatever `include_local_variables` says. Never set `trace_lifecycle` either: span streaming sends request headers as
  span attributes, which the scrubber never reads. What an event still carries: the exception type, message and chain;
  every frame's file, function, line and five source lines either side; breadcrumbs (log lines at INFO and above, SQL
  statements, HTTP calls without their query string); the request's method, URL and query string, other headers and
  body; the user id, tags, release and environment.
- Sentry withholds values too: `before_send`, `before_send_transaction`, `before_send_log` and `before_send_metric` are
  one hook (`main._value_scrubber`) that turns each occurrence, in any string of an error or check-in, a transaction
  with its spans, a log or a metric (keys included), of each secret setting's value (stripped, so a value stored with a
  newline is found where an error quotes it escaped) and of each connection URL's password, as written and
  percent-decoded, into a placeholder; in a URL missing its `@host` the password is the text a parser reads as the
  port. The placeholder is the SDK's own `[Filtered]` unless a weak secret overlaps it (equals `Filtered`, say, or
  starts with `Filtered]`), then the first of `[Withheld]`, `[Redacted]`, `<Filtered>`, `<Withheld>` and `<Redacted>`
  that none overlaps, so no placeholder can hold a secret or form one with the text beside it; if every one is
  overlapped, the options fail at startup and Sentry stays off.
  The walk is total: mappings and lists are walked, None, booleans and numbers kept, and any other value becomes its
  repr first and is scrubbed there, so no text the SDK builds after the hook can hold a secret, and turning Sentry
  logs on (`enable_logs`, or the logging integration's `capture_sentry_logs`) sends none either. The hook keeps only
  the protocol's own words, never a field whole: a key that is exactly one of `main._PROTOCOL_KEYS` (an error's, a
  transaction's, a check-in's, a log's and a metric's own; a child span's, a breadcrumb's, an exception's, its
  mechanism's and its frames', a request's, a user's, the SDK info's; the trace context's, its dynamic sampling
  context's, the response context's; a monitor config's), wherever it occurs, and an item's `type` when it is one the
  SDK gives (`main._ITEM_TYPES`: a transaction, a check-in, a metric's kind). The SDK reads some of them after the hook
  (an event's `event_id` and `type`, a log's `attributes`, a profile's `contexts.trace.trace_id`), so a weak secret
  equal to one of those words, or inside one, breaks no item, and keeping them reveals nothing: the items Sentry
  receives all spell those words. Every other key is user data and is scrubbed, whoever wrote it, so nothing that runs
  before the hook (an event processor, under any name; a hand-built event; a trace context set by hand) can carry a
  secret past it, and no scan of the backend for such writers is needed.
  A secret setting is named by the output walk's rule (below), which main.py copies. The values are read once, when
  `main._sentry_options()` runs at startup, and matched longest first, so a URL quoted whole goes whole. A text under 8
  characters is left: settings bound no secret's length but `SECRET_KEY`'s, the shortest real secret (the Alpha Vantage
  key) has 16, a port has at most 5 digits, and a shorter text would garble ids, timestamps and SQL wherever it occurred
  by chance. The hooks see each item after the event scrubber and the serializer, so never set `max_value_length`: the
  serializer would cut a string inside a secret and leave a prefix no hook matches. A hook that raises drops its item
  (`callback_error`), so a failure sends nothing; never move the scrubber into an event processor: one that raises
  passes the event on, and a global one runs before the request is attached. `before_send_span` acts only under span
  streaming, which stays off.
- Nothing prints or logs a secret. An output reports a secret's presence and length, never a character; a
  connection URL's parse error is reported by its type, and an HTTP error from a keyed URL by its status, never
  their messages; a database URL holding more than one `@` is refused; httpx's request log stays at WARNING
  where a key travels in a query string. No output call (a print, log, warn or write call, `click.echo`, `pprint`, a
  Sentry message, exception, event, tag or tags, context, extra, user, breadcrumb, or span data or attribute) and no
  raise or assert message reads a secret field directly, the settings object beyond a printable field
  (`model_dump()`, `__dict__`) or whole (`dict(settings)`, `vars(settings)`, `str.format`, unpacking, iteration), or a
  secret's environment variable.
- `hmac.compare_digest` and `secrets.compare_digest` compare bytes (`.encode()` both sides, or a `.digest()`). A value
  the caller sends encoded (a base64 signature header) is compared in its encoded form,
  `compare_digest(base64.b64encode(mac.digest()), signature.encode())`, which cannot raise on a header's value
  (headers decode as latin-1); never decode the caller's value first: `b64decode` and `bytes.fromhex` raise on a
  malformed one, and a decoded value held in a name is never bytes by its form, so the gate rejects it.
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
- **Library messages.** Every settings field but `REGISTRATION_MODE` is built from four values shaped to break a parse
  (the value alone, a URL missing its `@host`, a URL whose every part is the value, a `host:port` pair), and from one
  value per prefix a validator might check before it parses: each prefix `app/config.py` checks with `startswith` (a
  literal or a module constant bound to literals; a check the harvest cannot read fails the gate), the `sk_live_`,
  `whsec_` and `re_` credential prefixes, and a URL of each such `://` prefix and of each scheme a field's default or
  a connection uses, with the value where the port goes. Each carries a sentinel; no error's full traceback, chained
  exceptions included, may hold it. A control class whose validators parse a port, one on every value and one only
  past a `redis://` check, shows the shapes reach both calls (the second only through its scheme's shape) and that
  pydantic prints the message.
- **The checks.** `deploy_check`'s environment and configuration checks print no 4-character fragment of a
  fabricated secret on any branch: long keys, 12-character keys (the "appears too short" warnings), and
  production with a `sk_test_` secret key and a `pk_live_` publishable key (the mode warnings); each case
  asserts its branch ran. Its two database checks, fed a URL that puts a fabricated password where the port
  goes, print the error's type and no fragment.
- **Outputs.** `smoke_resend` prints the key's length; `redis_service` builds a pool from a URL holding a password and
  refuses a URL missing its `@host`; importing `app.database` with such a URL, or with more than one `@` (its tail in
  the host, the database or a query key), raises a `RuntimeError`, while the Cloud SQL socket form and a
  percent-encoded `@` parse; the database benchmark stops on each, prints a well-formed URL's backend and host only (a
  query-string password, and passwords whose digits land in the port and the rest in the database, included in the
  test) and its errors by type; an Alpha Vantage 503 is logged and raised as `HTTP 503`, and its throttle notice is
  logged with the key `[Filtered]`, whether the caller degrades or raises; the calendar job's logging setup and the
  service's `configure_logging` keep httpx's request log off. None prints or logs a 4-character fragment of the
  fabricated secret. An AST walk over every backend file outside `tests/` fails an output call's argument (a print,
  log, warn or write call, `echo`, `pprint`, a Sentry message, exception, event, tag, context, extra, user, breadcrumb
  or span data or attribute, by function or method name), or a raise or assert message, that reads `settings.X` or
  `getattr(settings, ...)` for anything but a printable field, hands the settings object whole to a call other than
  `repr`, `str`, `getattr`, `hasattr` and `isinstance` or unpacks or iterates it, reads `self.X` or `getattr(obj,
  "X")` for a secret field, or reads the environment whole or a variable that a secret field, a secret suffix or
  `PASSWORD` names or that an expression computes; all outside `len()`, `bool()`, a comparison and a conditional
  expression's condition. A secret field is one whose name ends in `_KEY`, `_SECRET`, `_TOKEN`, `_SALT`, `_PASSWORD` or
  `_DSN`, and the two connection URLs.
- **Sentry.** Built from `main._sentry_options()` with a fabricated DSN and a transport that keeps each envelope item
  and each lost item's reason, a fixture fails if the options turn local variables back on, send PII, or pass
  `data_collection` or `trace_lifecycle`, or if the built client cuts strings (`max_value_length`).
  An `/internal/` request whose enqueue fails (a 500 whose frames hold the token in a copied local and in every
  framework frame) and one whose background job fails after the 202 send their errors and three transactions with the
  header `[Filtered]`, no `vars` and no 8-character fragment of the token; a non-ASCII header is a 401. An Alpha
  Vantage request's breadcrumb and span carry `http.query` as `[Filtered]` and no fragment of the key. Routes that
  fail on a JSON body and on a form body holding a fabricated credential under each withheld key send each as
  `[Filtered]`, on the errors and the transactions. A walk of the API's request body schemas (JSON and form, through
  references, unions and lists) fails a key that names a credential (`password`, `token`, `secret`, `invite`, `code`,
  `key`, `otp`, `nonce`, `credential`; `referral_code` is shared by design) unless the denylist holds it and it sits
  at the body's top level. The match is by substring, so a future key that names such a word but carries no credential
  (`country_code`, `max_tokens`) goes into the test's `_NOT_CREDENTIALS` with its reason. The backend's one
  `sentry_sdk.init` call, through any import of the package or its modules, is main.py's, and it takes
  `_sentry_options()` and nothing else.
- **Sentry values.** Every `before_send*` option the SDK's `ClientConstructor` declares, `before_send_span` apart, is
  the one value scrubber, so a hook an upgrade adds fails the gate. With the settings fabricated before the client is
  built: a token quoted twice in a message, an exception, a log line's breadcrumb, an extra, a tag, a context (as a
  value and as a key), a user, a request (its path, query string, header and body), a transaction's name (which the
  envelope's trace header repeats) and a span's name and data, a log sent through the SDK's logger, a metric's
  attribute and a cron check-in's monitor slug arrives `[Filtered]` at each place it stood, with no 8-character
  fragment anywhere, envelope and item headers included; with Sentry logs on, through either switch, a log record's
  tuple and mapping `extra` values and an SDK log whose body is an exception arrive as their repr with the token
  `[Filtered]`; a setting added under each of the rule's suffixes (a fabricated settings class, `_PASSWORD` included)
  is withheld with no change to main.py; one message quoting every secret field's value (the gate's own
  `SECRET_FIELDS`, so main's copy of the rule cannot narrow unseen; the Alpha Vantage key at its 16 characters), each
  URL whole, the database password as written (an `@` percent-encoded) and decoded, and the Redis password (an `@`
  unescaped, read to the last `@` as redis-py reads it) arrives as `[Filtered]` for each, nothing else changed; the
  driver's own error for a URL missing its `@host` with an all-digit password, which quotes the digits as the port,
  arrives with them `[Filtered]`; a value stored with a trailing newline is withheld where an error quotes it escaped;
  an 8-character value is withheld while a 7-character one, an empty one, a URL's port and an IPv6 host are not, and a
  setting holding `None` is skipped, not a failure that would turn Sentry off; the values are read once, when the
  options are built, never at an item, by any path (a value set afterwards is not withheld); the trace header names the
  transaction with the secret withheld; secrets equal to protocol words (`event_id`, `trace_id`, `attributes`,
  `start_timestamp`, `time_unix_nano`, `severity_number`, `transaction`, `timestamp`, `check_in`, `parent_span_id`,
  `category`, `filename`, `schedule`, `sample_rate`) break no item: errors, transactions, the check-in, the log and the
  metric are each sent, as their own kind and whole, their child spans, breadcrumbs, frames, monitor config and trace
  header with their keys; every key of 8 characters or more that the SDK's own items carry outside user data, read from
  what each hook received in one capture of every structure on every channel and each taken as a secret, leaves every
  item's structure as it was, so a key an SDK upgrade adds fails until `_PROTOCOL_KEYS` has it; a secret held as a key
  in user data (an extra, a tag, a context's name and contents, a user, a breadcrumb's data, a request body, a span's
  data and tags, a log's and a metric's attributes) is withheld there, and so is one that follows a protocol word in the
  same key; a trace context set by hand, a hand-built event with the secret as its own key and its `type`, and an event
  processor registered under an assignment alias that writes it as an event's key, a trace context's key and the `type`
  each send it nowhere; a secret overlapping `[Filtered]` in each of the four ways (inside it, across its end, around
  it, across its start) moves the placeholder to the first that none overlaps and appears nowhere in the envelope, and
  weak secrets that overlap every placeholder fail the options with an error that names no value, inside main.py's `try`
  around its one init, so Sentry stays off and the app starts; and a scrubber that raises sends nothing: the error, the
  check-in, the transaction, the log and the metric are each lost to `callback_error`.
- **compare_digest.** An AST walk fails any `compare_digest` call in the backend, by its name or a name
  `from hmac|secrets import compare_digest as ...` gives it, whose two arguments are not both bytes by their
  form: a UTF-8 `.encode(...)` or `bytes(x, ...)`, a `.digest()`, a bytes literal, a base64 encoding of bytes or a
  `token_bytes(...)`. Another codec, `ascii`, raises on a non-ASCII value too, and so do `b64decode` and
  `bytes.fromhex` on a malformed caller value; a value decoded first and held in a name is not bytes by its form
  either. Compare in the encoded form instead: `compare_digest(base64.b64encode(mac.digest()), signature.encode())`.

The agent clause is not machine-gated and stays session reading.

**Known ungated echoes.** Two are open follow-ups in `tasks/todo.md` (E17, E18); the rest are accepted limits,
each with its reason:
- `scripts/refresh_index_membership.py --source fmp` logs an HTTP error's message (the FMP URL with its key) and
  lets httpx log each request URL at INFO; the monthly workflow uses the keyless Wikipedia source (todo E17);
- a provider's own error text can quote a masked key's last four characters (Stripe's and the AI providers'
  invalid-key messages): callers log it, and `app/routers/subscriptions.py` returns Stripe's message as the
  checkout and portal error detail (todo E18);
- an incoming request's URL reaches Sentry unscrubbed: the Google OAuth callback's single-use `code` in its query
  string and the waitlist verification token in its path (a user's, not a settings secret);
- the request-body walk reads the API's OpenAPI schemas: the Stripe and Resend webhooks read their bodies by hand
  and are outside it, and the scrubber reads a body's top-level keys only, so a credential nested in a provider's
  event would reach Sentry with that handler's error;
- `main.py`'s startup schema step (`create_all`, whose error the startup traceback and Sentry carry), its startup
  database check and `/health/detailed` log a driver's connection error, which names the host, port, user and
  database; it carries no password once the URL holds a single `@`, except in a URL missing its `@host`: a password
  whose text before its first `/` or `?` is all digits parses as the port and the rest as the database or a query
  key, and the connection error (the database driver's, or Redis's) can quote the port or such a query key. Sentry
  withholds the port's text when it has 8 characters or more (its value scrubber reads it as the password), not the
  rest, and the log line keeps both. The documented production password is hex (`openssl rand -hex 24`) in the
  Cloud SQL socket form, which keeps its `@`;
- `main.py`'s Sentry init-failure line prints a malformed DSN's parse message (its scheme, its project path, or
  the port segment of a legacy key pair without a host); the DSN's key is public by Sentry's design;
- Sentry's value scrubber matches each value whole, stripped, as the settings held it at startup. A part of one passes
  (a prefix, a provider's masked last four (todo E18), a password's text past a raw `/`, `?` or `#`, where the URL
  rule stops), and so does another form of it (repr- or JSON-escaped, percent-encoded other than as the URL holds it,
  base64, hex, a case change: the documented secrets are hex or alphanumeric with `_` and `-`, which no such escape
  changes), a value under 8 characters, a password given in a URL's query string (`?password=`, withheld only inside
  the whole URL), a secret that is no settings field (a user's credential, a token a provider returns), a new secret
  setting whose name ends in none of the rule's suffixes (the output walk misses it too), and a secret held as a
  number, which the walk keeps as it is (no setting is one; an all-digit password is text in its URL). Profiles
  (code locations), sessions (release-health counts) and attachments (none sent) pass no hook; the envelope's trace
  header is taken from the scrubbed event. Frame variables stay off whatever the scrubber does: a frame holds values
  in forms it cannot match. Over-redaction is accepted: a secret that equals ordinary text (a weak salt equal to the
  domain) withholds that text; one equal to a protocol word, which leaves every key of the protocol's own, replaces
  that word in values, the protocol's own included (a check-in's `in_progress`, a span's `op`), and in user data's
  keys (a log attribute named `sentry.environment` under a secret `environment`), so Sentry may drop such a check-in
  or lose that attribute, though no capture fails; and the public-by-design values the rule names
  (`STRIPE_PUBLISHABLE_KEY`, `POSTHOG_API_KEY`, `SENTRY_DSN`) are withheld too;
- the output walk sees only a direct read in a call it names as an output, not an alias (`url = settings.REDIS_URL`),
  a helper the value is handed to or an object holding it (`stripe.api_key`), and the message walk reads
  `app/config.py` only and does not follow `globals()`, `setattr` or `sys.modules`;
- the library-message test drives its shapes one field at a time, as constructor arguments: a parse behind a
  check other than `startswith` or a known prefix, one that fails only on other input, on two fields together
  or only from the environment is not exercised.

**Evidence.** `backend/app/config.py` (`class Config`, `__repr_args__`); `backend/main.py` (`_sentry_options`,
`_value_scrubber`, `_withhold`, `_secret_values`, `_url_passwords`, `_MIN_SECRET_LENGTH`);
`backend/app/routers/internal.py` (`_require_internal_token`); `backend/app/database.py` (`_database_url`);
`backend/app/services/redis_service.py` (`get_redis_pool`); `backend/app/integrations/alpha_vantage.py`
(`fetch_earnings_calendar`); `backend/scripts/earnings_calendar_job.py` (`_configure_logging`);
`backend/scripts/deploy_check.py`; `backend/scripts/smoke_resend.py`; `backend/scripts/validate_db_performance.py`;
sentry-sdk 2.71.0: `client.py` (`_get_options`: `data_collection` drops `event_scrubber`, and `before_send_span`
without span streaming warns; `_prepare_event`: the scrubber, then `serialize` with `max_value_length` (none by
default), then `before_send` for every event but a transaction and `before_send_transaction` for a transaction, a
hook that raises dropping the event as `callback_error`; `capture_event`: the trace header comes from the hooked
event; `_capture_telemetry`: logs and metrics reach only `before_send_log` and `before_send_metric`, a raise
dropping the item; the log batcher exists whatever `enable_logs` says), `logger.py` and `metrics.py` (the SDK's
logger and metrics API, ungated by `enable_logs`; a log's body is its template as given), `_log_batcher.py`
(`_to_transport_format`: the body's `str` and each attribute's `serialize_attribute`, after the hook),
`integrations/logging.py` (`_extra_from_record`: a record's `extra` values as they are; `capture_sentry_logs`, a
class attribute each constructor sets), `scope.py` (`apply_to_event`: breadcrumbs ride on errors only;
`run_event_processors`: global processors run before the request's, and one that raises passes the event on),
`consts.py` (`ClientConstructor`, `DEFAULT_MAX_VALUE_LENGTH = None`), `utils.py` (`serialize_frame`,
`walk_exception_chain` honours `__suppress_context__`, `serialize_attribute` and `format_attribute` fall back to
`safe_repr`), `data_collection.py` (`stack_frame_variables` follows
`include_local_variables` only without `data_collection`), `integrations/httpx.py` (`parse_url(...,
sanitize=False)`), `integrations/_wsgi_common.py` (`SENSITIVE_HEADERS`), `scrubber.py` (`DEFAULT_DENYLIST`, exact
key matches); CODE RED records 22 (disclosure 4) and 23 (disclosure 3).
