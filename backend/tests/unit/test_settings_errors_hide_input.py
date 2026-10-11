"""A settings validation error carries no input value (rule 12; CODE RED record 23, plan item 3).

pydantic appends each failing field's input to its error message (`input_value=...`), and a missing
required field's input is the whole environment-derived settings dict. Without
`hide_input_in_errors`, a settings validation error printed environment values, secrets included,
into whatever output carried it: a service's startup log, CI's public log, or an agent's own tool
output (CODE RED records 22 and 23 each disclose one such echo). These tests pin the setting and the
two shapes that leaked: a field's own failing value, and the missing-field dict.
"""

import pytest
from pydantic import ValidationError

from app.config import Settings

SENTINEL = "PRIVATE_SETTINGS_SENTINEL_7c1e"  # 30 characters: a SECRET_KEY too short to pass
SHORT_SENTINEL = "PRIVATE_DB_7c1e"  # short enough that the echoed input is never shortened


def _error_text(exc: ValidationError) -> str:
    return f"{exc}\n{exc!r}"


def test_settings_hide_input_in_errors():
    assert Settings.model_config.get("hide_input_in_errors") is True


def test_a_failing_value_is_not_echoed():
    # The SECRET_KEY validator rejects a short key; the error would otherwise append the key itself.
    with pytest.raises(ValidationError) as info:
        Settings(SECRET_KEY=SENTINEL, _env_file=None)
    assert "SECRET_KEY" in str(info.value)
    assert SENTINEL not in _error_text(info.value)


def test_the_missing_field_dict_is_not_echoed(monkeypatch):
    # A missing required field's input is the whole environment-derived dict (a production DATABASE_URL
    # carries the database password). pydantic shortens a long input to its two ends, so the environment
    # is cleared to one short entry that the error would otherwise print whole.
    for name in Settings.model_fields:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DATABASE_URL", SHORT_SENTINEL)
    with pytest.raises(ValidationError) as info:
        Settings(_env_file=None)
    assert "SECRET_KEY" in str(info.value)
    assert SHORT_SENTINEL not in _error_text(info.value)
