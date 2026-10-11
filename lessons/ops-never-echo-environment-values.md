# Never let a settings error or an ad-hoc config import print environment values

Date: 2026-10-11 · Area: ops / secrets

**Context.** On two consecutive days a review agent imported `app.config` outside the test harness to
probe a detail (CODE RED records 22 and 23). In the container's real environment the settings class failed
validation, and pydantic's error appended its input: the environment-derived settings dict, shortened to
its two ends. A fragment of a real AI-provider key and a base URL reached the agent's own tool output. The
same error shape prints a too-short `SECRET_KEY` whole, or a production `DATABASE_URL` with its password
when it is the dict's last or only entry, into a service's startup log or CI's public log.

**Rule.** The settings class sets `hide_input_in_errors`, so a validation error names the failing field
and its reason, never its value. A validator's own message must not interpolate a secret's value
(`REGISTRATION_MODE`'s message quotes its value by design; it holds no secret). Never import the
application's config, construct `Settings` or print a settings object (its repr carries every value)
outside the test harness, whose conftest supplies a hermetic environment; run an ad-hoc probe under
`env -i PATH=/usr/bin:/bin` so no real environment value can reach it.

**Gate.** `backend/tests/unit/test_settings_errors_hide_input.py` pins the setting and proves that both
leaking shapes are withheld: a field's own failing value, and the missing-field input dict. With the
setting removed, all three tests fail. The agent clause (no ad-hoc import; `env -i`) is not machine-gated
and stays session reading.

**Evidence.** `backend/app/config.py` (`class Config`); CODE RED records 22 (disclosure 4) and 23
(disclosure 3).
