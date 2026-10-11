# Never let a settings error, a settings object or a config check print a secret

Date: 2026-10-11 · Area: ops / secrets

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

**Rule.**
- The settings class sets `hide_input_in_errors`, so a validation error's text (`str`, `repr`, and so a
  traceback or a log line) names the failing field and its reason, never its value. The one exception is
  `REGISTRATION_MODE`'s validator, which quotes its value by design: the field holds no secret.
- The setting does not reach the error's structured form: `errors()` and `json()` return every input,
  whole, unless called with `include_input=False`. An `except` block that calls either on its caught
  exception passes it.
- A settings object prints no value: the class overrides `__repr_args__`, so `repr()` is `Settings()` and
  `str()` is empty. That covers the object only: a secret copied into another local, or a request
  header, still reaches Sentry's capture.
- A raise or assert message in `app/config.py` reads only literals, lengths (`len(v)`) and module
  constants bound to literals, never a parameter, a field or the environment.
- `scripts/deploy_check.py` prints a secret's presence and length, never its characters, and a database
  error's type, never its message. The message can quote `DATABASE_URL`: a URL missing its `@host` puts the
  password where the port goes, and the `int()` that parses the port quotes it. The model id and the
  provider base URL are identifiers, not secrets, and are printed by design.
- An agent's ad-hoc probe of application code (`python -c`, a scratch script) runs under
  `env -i PATH=/usr/bin:/bin` in a copy with no `.env` file at any level (a `git archive` export, not a
  checkout). Importing `app.config` builds the module-level `settings` from the working directory's `.env`,
  whatever a later `Settings(_env_file=None)` does. `main.py`'s `load_dotenv()`, like
  `scripts/smoke_resend.py`'s and `scripts/validate_db_performance.py`'s, loads the `.env` it finds above
  its own file into the environment.

**Gate.** `backend/tests/unit/test_never_echo_environment_values.py`:
- **The setting.** It pins the setting and proves that both leaking shapes are withheld: a field's own
  failing value, and the missing-field input dict. A control class with pydantic's default shows that the
  same errors echo the value. With the setting removed, those three tests fail.
- **The structured form.** An AST walk over every backend Python file outside `tests/` (the entrypoints,
  the application, its scripts and its evals) fails any `except ... as name` block, whatever it catches,
  that calls `name.errors()` or `name.json()` without `include_input=False`; a pin fails when a new
  directory of backend code is left out of the walk. It reads only the block's own direct calls on the
  bound name. Outside it:
  - an alias (`f = exc.errors`), or `getattr`;
  - a helper the exception is handed to;
  - a FastAPI exception-handler function;
  - an except* group's members.

  None exists today.
- **The repr.** A settings object's `repr()` is `Settings()`, its `str()` is empty, and Sentry's
  serialization of it is `Settings()`.
- **Messages.** An AST walk over `app/config.py` fails a raise or assert message, in a function or at module
  level, that reads anything but literals and `len(...)`, directly, through a name or through a raise's
  `from` cause. It denies by default:
  - a name counts through every expression its scope binds to it (tuple targets, loop variables, `:=` and
    mutator calls: `append`, `extend`, `insert`, `add`, `update`, `setdefault`, keyword arguments
    included). When the scope binds it in no way at all, the name counts through every expression the
    module binds to it. So `MIN_SECRET_KEY_LENGTH = 32` reads nothing, a module name bound to
    `os.environ[...]` reads the environment, and a parameter is a value whatever its case;
  - a name with no expression bound to it counts as read: a parameter, a `with` target, an import
    (`getenv(...)`, `os.environ`), a builtin (`locals()`);
  - every call counts except a call of an exception class (a CapWords name) or `sorted` that neither the
    scope nor the module binds.

  One sanctioned quotation is allowed: `REGISTRATION_MODE`'s `v`. The test also pins the settings class's
  only base and the absence of an `Annotated` validator, so a validator cannot move out of the walk unseen.
- **The check.** `deploy_check`'s environment and configuration checks print no 4-character fragment of a
  fabricated secret. Its two database checks, fed a URL that puts a fabricated password where the port
  goes, print the error's type and no fragment of the password.

The agent clause is not machine-gated and stays session reading.

**Known ungated echoes**, each a follow-up:
- `scripts/smoke_resend.py` prints the last four characters of `RESEND_API_KEY`;
- `app/services/redis_service.py` logs `REDIS_URL` whole;
- `INTERNAL_JOB_TOKEN` reaches Sentry's capture, as a frame local and as the `x-internal-token` header;
- `app/database.py` calls `create_engine` at import, so the same malformed-URL error puts the password in a
  service's startup log.

**Evidence.** `backend/app/config.py` (`class Config`, `__repr_args__`); `backend/scripts/deploy_check.py`
(`check_environment_variables`, `check_database`, `check_phase2_alerts`); CODE RED records 22
(disclosure 4) and 23 (disclosure 3).
