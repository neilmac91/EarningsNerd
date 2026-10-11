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
- `scripts/deploy_check.py` printed the first 30 characters of every value it checked, secrets included.

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
- A raise or assert message in `app/config.py` reads only constants, ALL_CAPS module constants and
  lengths (`len(v)`), never a parameter, a field or the environment.
- `scripts/deploy_check.py` prints a secret's presence and length, never its characters. The model id and
  the provider base URL are identifiers, not secrets, and are printed by design.
- An agent's ad-hoc probe of application code (`python -c`, a scratch script) runs under
  `env -i PATH=/usr/bin:/bin`, from a directory with no `.env` file (the settings class reads `.env`
  relative to the working directory) or with `Settings(_env_file=None)`. Then neither the environment
  nor a dotenv file can supply a real value.

**Gate.** `backend/tests/unit/test_never_echo_environment_values.py`:
- **The setting.** It pins the setting and proves that both leaking shapes are withheld: a field's own
  failing value, and the missing-field input dict. A control class with pydantic's default shows that the
  same errors echo the value. With the setting removed, those three tests fail.
- **The structured form.** An AST walk over every backend Python file outside `tests/` (the entrypoints,
  the application, its scripts and its evals) fails any `except ... as name` block, whatever it catches,
  that calls `name.errors()` or `name.json()` without `include_input=False`. It reads only the block's
  own direct calls on the bound name. Outside it:
  - an alias (`f = exc.errors`), or `getattr`;
  - a helper the exception is handed to;
  - a FastAPI exception-handler function;
  - an except* group's members.

  None exists today.
- **The repr.** A settings object's `repr()`, its `str()` and Sentry's serialization of it carry no value.
- **Messages.** An AST walk over every function in `app/config.py` fails a raise or assert message that
  reads anything but constants, ALL_CAPS module constants and `len(...)`, directly or through a local
  bound in the function. Local bindings include tuple targets, loop variables, `:=` and
  `append`/`extend`. One sanctioned quotation is allowed: `REGISTRATION_MODE`'s `v`. The test also pins
  the settings class's only base, so a validator cannot move into a mixin unseen.
- **The check.** `deploy_check`'s environment and configuration checks print no secret.

The agent clause is not machine-gated and stays session reading.

**Evidence.** `backend/app/config.py` (`class Config`, `__repr_args__`); `backend/scripts/deploy_check.py`
(`check_environment_variables`); CODE RED records 22 (disclosure 4) and 23 (disclosure 3).
