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
  the hooks of `main._value_scrubber`, one per channel, each of which turns each occurrence, in any string of an error
  or check-in, a transaction with its spans, a log or a metric (keys included), of each secret setting's value
  (stripped, so a value stored with a newline is found where an error quotes it escaped) and of each connection URL's
  password, as written and percent-decoded, wherever a driver reads one, into a placeholder: in the authority (in a URL
  missing its `@host`, the text a parser reads as the port), in a `password` query parameter, also plus-decoded and as
  SQLAlchemy renders it, which SQLAlchemy passes to the driver and renders whole even with `hide_password` (re-sorting
  the query and quoting the value as `quote_plus` does, so the rendering differs from the setting) and redis-py reads,
  and as SQLAlchemy parses it, decoded, a raw `/`, `?` or `#` in it included (Codex's case on #1297). The placeholder is
  the SDK's own `[Filtered]` unless a weak secret overlaps it (equals `Filtered`, say, or starts with `Filtered]`), then
  the first of `[Withheld]`, `[Redacted]`, `<Filtered>`, `<Withheld>` and `<Redacted>` that none overlaps, so no
  placeholder can hold a secret or form one with the text beside it; if every one is overlapped, the options fail at
  startup and Sentry stays off. The walk is total: mappings and lists are walked, None and booleans kept, a number made
  exactly a number (int's or float's own value: the log batcher makes text of a number subclass through its own
  `__str__` or `__repr__` after the hook), every text scrubbed through str's own `replace` (the SDK keeps a str subclass
  as it is up to the hooks, and a subclass's `replace` could keep the secret: Codex's case on #1297's ready head), and
  any other value becomes its repr first and is scrubbed there, so no text the SDK builds after the hook can hold a
  secret, and turning Sentry logs on (`enable_logs`, or the logging integration's `capture_sentry_logs`) sends none
  either. Each hook keeps only the protocol's own keys where the protocol puts them, never a field whole: a key stays as
  it is only at one of the paths `main._PROTOCOL_PATHS` gives its item's kind, one set each for an error, a transaction
  with its spans, a check-in, a log and a metric (before_send tells a check-in by its `type`, exactly text): the path of
  each key of 8 characters or more from an item's top (a list's items sharing the list's path) as the SDK builds that
  kind under main's options (an item's own keys; a child span's, a breadcrumb's, an exception's, its mechanism's and its
  frames', a thread's frames'; a log entry's, a request's, a user's, the SDK info's; the trace context's, its dynamic
  sampling context's, the response context's; a monitor config's; the serializer's `_meta` note on breadcrumbs, which an
  error carries and a transaction or a check-in carries once its scope has dropped breadcrumbs past `max_breadcrumbs`;
  and the names the SDK fills from its API or a request's incoming trace, an event's `fingerprint` and the replay fields
  an incoming baggage header carries; with continuous profiling, which main does not configure,
  `contexts.profile.profiler_id` would join them), and only when it and every key above it is exactly text, and an
  item's `type` when it is exactly text and one the SDK gives that kind (`main._ITEM_TYPES`: before_send's check-in, a
  transaction's, a metric's kinds; an error and a log carry none, so another kind's word written there is withheld:
  Codex's case on #1297). The SDK reads some of them after the hook (an event's `event_id` and `type`, a log's
  `attributes`, a profile's `contexts.trace.trace_id`), so a weak secret equal to one of those words, or inside one,
  breaks no item. Every other key is scrubbed, whoever wrote it, a protocol word or not: in user data (an event's extra
  and tags, a span's or a breadcrumb's data, a request's body, headers, cookies and env, a log's or a metric's
  attributes, a frame's variables, a log entry's params, measurements, the modules), in a context the app set, as a
  user's own key, in a structure the app nested in the protocol's (a protocol word at a path that is not its own) and at
  a path the protocol gives another kind of item (a log's `attributes` written into an error): Codex's cases on #1297.
  So an app that writes a protocol word as a key sends no secret equal to it, and nothing that runs before the hook (an
  event processor, under any name; a hand-built event; a trace context set by hand) can carry a secret past it, but as
  the protocol's own key at its own path in its own kind of item, a word the SDK itself writes there, so a secret equal
  to it is public text (an item whose `type` is a text subclass is scrubbed by its channel's paths and sent as its text
  says, so it can carry another kind's such word: the SDK writes every type as plain text, and the backend writes none;
  the round-20 check's R20D-2); no scan of the backend for such writers is needed. A `type` that is not text (only a
  hand-built event has one) is walked like any value, and the item is sent. A secret setting is named by the output
  walk's rule (below), which main.py copies. The values are read once, when `main._sentry_options()` runs at startup,
  and matched longest first, so a URL quoted whole goes whole. A text under 8 characters is left: settings bound no
  secret's length but `SECRET_KEY`'s, the shortest real secret (the Alpha Vantage key) has 16, a port has at most 5
  digits, and a shorter text would garble ids, timestamps and SQL wherever it occurred by chance. `before_send` and
  `before_send_transaction` see each item after the event scrubber and the serializer (the log and metric hooks get
  theirs unserialized), so never set `max_value_length`: the serializer would cut a string inside a secret and leave a
  prefix no hook matches. A hook that raises drops its item (`callback_error`), so a failure sends nothing: each hook
  raises any failure as an Exception, since the SDK sends a log or a metric on, unscrubbed, after one that is not; never
  move the scrubber into an event processor: one that raises passes the event on, and a global one runs before the
  request is attached. `before_send_span` acts only under span streaming, which stays off.
- Nothing prints or logs a secret. An output reports a secret's presence and length, never a character; a
  connection URL's parse error is reported by its type, and an HTTP error from a keyed URL by its status, never
  their messages; a database URL holding more than one `@` is refused, advising a user name and password of characters
  that need no percent-encoding and never encoding (the deploy's migration step and the Ops proxy step hand both to
  `psql` undecoded); httpx's request log stays at WARNING
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
  percent-encoded `@` parse (the app decodes it, the deploy does not); both refusals of more than one `@`, pinned
  whole, give one reason, which advises characters that need no percent-encoding and no encoding in any form; the
  database benchmark stops on each, prints a well-formed URL's backend and host only (a
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
  and each lost item's reason, a fixture fails if the options turn local variables back on, send PII, pass
  `data_collection` or `trace_lifecycle` or configure continuous profiling (`profile_session_sample_rate` or
  `profile_lifecycle`, at the top level or in `_experiments`), or if the built client cuts strings (`max_value_length`).
  An `/internal/` request whose enqueue fails (a 500 whose frames hold the token in a copied local and in every
  framework frame) and one whose background job fails after the 202 send their errors and three transactions with the
  header `[Filtered]`, no `vars` and no 8-character fragment of the token; a non-ASCII header is a 401. An Alpha Vantage
  request's breadcrumb and span carry `http.query` as `[Filtered]` and no fragment of the key. Routes that fail on a
  JSON body and on a form body holding a fabricated credential under each withheld key send each as `[Filtered]`, on the
  errors and the transactions. A walk of the API's request body schemas (JSON and form, through references, unions and
  lists) fails a key that names a credential (`password`, `token`, `secret`, `invite`, `code`, `key`, `otp`, `nonce`,
  `credential`; `referral_code` is shared by design) unless the denylist holds it and it sits at the body's top level.
  The match is by substring, so a future key that names such a word but carries no credential (`country_code`,
  `max_tokens`) goes into the test's `_NOT_CREDENTIALS` with its reason. The backend's one `sentry_sdk.init` call,
  through any import of the package or its modules, is main.py's, and it takes `_sentry_options()` and nothing else.
- **Sentry values.** Every `before_send*` option the SDK's `ClientConstructor` declares, `before_send_span` apart, is
  the value scrubber's hook for its channel (errors and check-ins, transactions, logs, metrics), so a hook an upgrade
  adds fails the gate. With the settings fabricated before the client is built: a token quoted twice in a message, an
  exception, a log line's breadcrumb, an extra, a tag, a context (as a value and as a key), a user, a request (its path,
  query string, header and body), a transaction's name (which the envelope's trace header repeats) and a span's name and
  data, a log sent through the SDK's logger, a metric's attribute and a cron check-in's monitor slug arrives
  `[Filtered]` at each place it stood, with no 8-character fragment anywhere, envelope and item headers included; with
  Sentry logs on, through either switch, a log record's tuple and mapping `extra` values and an SDK log whose body is an
  exception arrive as their repr with the token `[Filtered]`; a setting added under each of the rule's suffixes (a
  fabricated settings class, `_PASSWORD` included) is withheld with no change to main.py; one message quoting every
  secret field's value (the gate's own `SECRET_FIELDS`, so main's copy of the rule cannot narrow unseen; the Alpha
  Vantage key at its 16 characters), each URL whole, the database password as written (an `@` percent-encoded) and
  decoded, and the Redis password (an `@` unescaped, read to the last `@` as redis-py reads it) arrives as `[Filtered]`
  for each, nothing else changed; the driver's own error for a URL missing its `@host` with an all-digit password, which
  quotes the digits as the port, arrives with them `[Filtered]`; a `password` query parameter (the database's, with an
  encoded `+`, or a raw `/` and an encoded space, which an engine renders `%2F` and `+`, and the Redis one) and an
  authority password holding a raw `/`, each as written and as the driver reads it, and an engine's rendering of such a
  URL, arrive `[Filtered]`, a URL SQLAlchemy refuses still gives the authority's password and a `password` query
  parameter, each as written and decoded, and a query password holding a lone surrogate (an environment byte that is not
  UTF-8) still gives the values, whose failure would turn Sentry off; a value stored with a trailing newline is withheld
  where an error quotes it escaped; an 8-character value is withheld while a 7-character one, an empty one, a URL's port
  and an IPv6 host are not, and a setting holding `None` is skipped, not a failure that would turn Sentry off; the
  values are read once, when the options are built, never at an item, by any path (a value set afterwards is not
  withheld); the trace header names the transaction with the secret withheld; secrets equal to protocol words
  (`event_id`, `trace_id`, `attributes`, `start_timestamp`, `time_unix_nano`, `severity_number`, `transaction`,
  `timestamp`, `check_in`, `parent_span_id`, `category`, `filename`, `schedule`, `sample_rate`, `distribution`) break no
  item: errors, transactions, the check-ins, the log and the metrics are each sent, as their own kind and whole, their
  child spans, breadcrumbs, frames, monitor config, trace header and the gen-AI span the SDK splits out after the hook
  with their keys, and a distribution keeps its kind; every key of 8 characters or more that the SDK's own items carry
  outside user data, read from what each hook received in one capture of the structures the design and delta checks
  found the SDK builds under main's options (on every channel, with breadcrumbs past `max_breadcrumbs` and check-ins
  inside a request and a span; the capture builds no subprocess span, errno mechanism data or gauge) and each taken as a
  secret, leaves every item's structure as it was, each list's items compared by index (a key lost in one span or frame
  shows), so a key on a structure the capture builds fails until `_PROTOCOL_PATHS` has its path for the item's kind, and
  main keeps exactly the paths each kind's items carry (none missing, none dead or misspelled; the capture sets no
  context of its own), on the SDK version the capture was checked against (pinned: an upgrade fails until the capture is
  checked against it again); a weak secret equal to a protocol word (`username`) written by the app as a key in each
  kind of user data (an extra, a tag, a context of its own, a breadcrumb's data, a span's data and tags, a log's and a
  metric's attributes, a request's body and headers, a log entry's params) is withheld there while the user's own
  `username` stays, each field of the gate's copy of the user-data fields holds user data in main (an error's paths),
  one equal to `trace_id` written as a user's own key, nested by the app in a trace context or as a hand-built event's
  field is withheld there while the trace context's own `trace_id` stays, and weak secrets equal to a log's
  `attributes`, a check-in's `check_in_id` and a log's top-level `trace_id`, written into an ordinary error by an event
  processor or by hand, are withheld there while the error's own trace context keeps its `trace_id` (Codex's cases on
  #1297), an event whose `type` only poses as `check_in` keeps no check-in key, and a metric's kind written as an
  ordinary error's `type`, by an event processor or by hand, under a secret equal to it, is withheld there while a
  metric keeps its own; weak secrets equal to a word that only one kind's paths hold (`fingerprint`, `start_timestamp`,
  `check_in_id`, `attributes`), written into an error and a transaction by an event processor and into a check-in by
  hand, are withheld in every kind of event but their own; an int and a float subclass whose `__str__` and `__repr__`
  quote the secret, sent as a log's body and in a log record's extra with Sentry logs on, send no part of it (and an
  error's extra keeps them as numbers); a text subclass whose `replace` keeps the secret, written as an error's extra by
  an event processor and sent as a log's body, attribute and attribute key and a metric's attribute, is withheld in
  each; a key that only poses as a protocol word (a text subclass, any other object) is withheld or turned into its
  repr, one that poses as a key above a protocol path keeps nothing below it, and below a key that is not text no key
  stays, a top-level word included; a secret held as a key in user data (an extra, a tag, a context's name and contents,
  a user, a breadcrumb's data, a request body, a span's data and tags, a log's and a metric's attributes) is withheld
  there, and so is one that follows a protocol word in the same key; a trace context set by hand, an attachment on the
  scope, a hand-built event with the secret as its own key, its `type` and an attachment, and an event processor
  registered under an assignment alias that writes it as an event's key, a trace context's key and the `type` and
  attaches it each send it nowhere (no attachment item is sent, by payload or item header; the aliased processor and the
  hand-set context are shown to have run), and a hand-built event whose `type` is a list is sent, while one whose `type`
  is a text subclass posing as `check_in` is sent as an event with that type scrubbed; a secret overlapping `[Filtered]`
  in each of the four ways (inside it, across its end, around it, across its start) moves the placeholder to the first
  that none overlaps and appears nowhere in the envelope, and weak secrets that overlap every placeholder fail the
  options with an error that names no value, inside main.py's `try` around its one init, so Sentry stays off and the app
  starts; and a scrubber that raises sends nothing, whatever it raises (an Exception or one that is not): the error, the
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
  (a prefix, a provider's masked last four (todo E18)), and so does another form of it (repr- or JSON-escaped,
  percent-encoded other than as the URL holds it (a `password` query parameter as SQLAlchemy renders it aside), base64,
  hex, a case change: the documented secrets are hex or alphanumeric with `_` and `-`, which no such escape changes), a
  value under 8 characters once stripped (one that reaches 8 only with its surrounding whitespace holds a secret of 7
  characters or fewer, which the floor leaves as it leaves any: Codex's P2 on `a81a911`, for the founder's call), a
  password libpq reads under another query key (`sslpassword`, a `dsn` parameter, a key padded with whitespace: the
  round-17 check's R17U-3), withheld only inside the whole URL, a password holding a raw `/`, `?` or `#` in two forms no
  driver reads (the round-17 check), as the URL writes it when it also holds a percent-escape (SQLAlchemy's parse gives
  it decoded, which is withheld, and the authority rule stops at the raw character) and in a URL SQLAlchemy refuses (a
  port that is no number, which `app.database` refuses at startup), where only its text before the raw character is
  withheld (nothing in the backend quotes a URL's user info on its own, and an engine's rendering hides it as `***`), a
  secret that is no settings field (a user's credential, a token a provider returns), another kind's protocol word as a
  key in an item whose `type` is a text subclass (the SDK writes every type as plain text, and no backend code writes
  one: the round-20 check's R20D-2), a new secret setting whose name ends in none of the rule's suffixes (the output
  walk misses it too), and a secret held as a number, which the walk keeps as it is (no setting is one; an all-digit
  password is text in its URL), and one holding JSON syntax that re-forms where the SDK serializes an item, across a key
  and its value or from an escaped character (Codex's `message":"`, from an event's `message` key and its value: Codex's
  P2 on `b7de8cb`): such a secret forms only from texts side by side in the item, so only one made of public text, which
  such items spell anyway, or one whose parts code holding it writes side by side does. Profiles and sessions pass no
  hook. The SDK builds a sampled transaction's profile (`profiles_sample_rate`) after its hook, from each sampled
  frame's file, module, function and line, every live thread's name (the app's `request_` and `edgar_` pool prefixes and
  `startup-` steps, its libraries', Python's `MainThread`), the host's platform strings and the scrubbed transaction's
  id, name, trace id, environment, release and start (Codex's P2 on `53016f2`). Code or the host fixes each text, the
  same whatever a secret is, so a secret shows there only when it equals or sits inside one; a thread named from data,
  code compiled from data, or continuous profiling (whose chunks pass no hook either; the gate pins main's options to
  configure none) would change that, and the gate runs with profiles off. A session carries release-health counts and
  the options' release and environment, which config fixes, so a secret shows there only when it equals or sits inside
  one of them. Each hook drops a hint's attachments, whose bytes would pass none (the backend sends none); the
  envelope's trace header is taken from the scrubbed event. Frame variables stay off whatever the scrubber does: a frame
  holds values in forms it cannot match. Over-redaction is accepted: a secret that equals ordinary text (a weak salt
  equal to the domain) withholds that text; one equal to a protocol word, which leaves every key at its kind's own
  paths, replaces that word in values, the protocol's own included (a check-in's `in_progress`, a span's `op`), and in
  every other key (a log attribute named `sentry.environment` under a secret `environment`), so Sentry may drop such a
  check-in or lose that attribute, though no capture fails, and a secret equal to or inside `exception` or `stacktrace`
  renames the serializer's `_meta` note on a stack the SDK drops past 2,000 traceback entries (`MAX_STACK_FRAMES`), so
  Sentry loses the reason the stack is missing (each raise adds one traceback entry for each frame it unwinds, and
  Python's default recursion limit of 1,000 keeps one raise to about 1,000 entries, so only a traceback grown past one
  call stack reaches it: for example one exception instance raised again and again (three times from 667 frames deep,
  about 1,000 times from a callee its caller catches, about 2,000 times where it is caught, or 667 reads of a failed
  `concurrent.futures` future), or a traceback carried on to a new exception (`with_traceback`) or built by hand
  (`types.TracebackType`); nothing in the backend grows a traceback that way or raises the limit: Codex's P2 on
  `d725600`, the round-19, round-21 and round-22 checks); and the public-by-design values the rule names
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
without span streaming warns; `_prepare_event`: the scrubber, then, once a scope has dropped breadcrumbs past
`max_breadcrumbs`, a length note on the breadcrumbs of every event it captures (on a transaction or a check-in, an
empty `values` list), then `serialize` with `max_value_length` (none by default), which writes that note into
`_meta`, then `before_send` for every event but a transaction and `before_send_transaction` for a transaction, a
hook that raises an Exception dropping the event as `callback_error` (any other exception drops it too, recorded as
`before_send`); `capture_event`: the trace header comes from the hooked event; `_capture_telemetry`: logs and
metrics reach only `before_send_log` and `before_send_metric`, a raise of an Exception dropping the item and any
other exception passing the item on, unscrubbed (`capture_internal_exceptions` swallows it); the log batcher exists
whatever `enable_logs` says), `logger.py` and `metrics.py` (the SDK's logger and metrics API, ungated by
`enable_logs`; a log's body is its template as given), `_log_batcher.py` (`_to_transport_format`: the body's `str`
and each attribute's `serialize_attribute`, after the hook), `integrations/logging.py` (`_extra_from_record`: a
record's `extra` values as they are; `capture_sentry_logs`, a class attribute each constructor sets), `scope.py`
(`apply_to_event`: the scope's breadcrumbs ride on errors only; `run_event_processors`: global processors run
before the request's, and one that raises passes the event on), `consts.py` (`ClientConstructor`,
`DEFAULT_MAX_VALUE_LENGTH = None`), `serializer.py` (`_serialize_node_impl` keeps a `str`, a subclass included, as
it is: `strip_string` returns it whole without `max_value_length`), `utils.py` (`serialize_frame`,
`walk_exception_chain` honours `__suppress_context__`, `format_attribute` keeps a `str` or a number as it is, and
it and `serialize_attribute` fall back to `safe_repr`), `data_collection.py` (`stack_frame_variables` follows
`include_local_variables` only without `data_collection`), `integrations/httpx.py` (`parse_url(...,
sanitize=False)`), `integrations/_wsgi_common.py` (`SENSITIVE_HEADERS`), `scrubber.py` (`DEFAULT_DENYLIST`, exact
key matches); CODE RED records 22 (disclosure 4) and 23 (disclosure 3).
