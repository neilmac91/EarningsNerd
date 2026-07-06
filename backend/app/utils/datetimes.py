"""Shared datetime helpers.

`utcnow()` is the source of the current time for the backend: a timezone-AWARE UTC instant.
Prefer it over the stdlib tz-naive `datetime.utcnow()` classmethod everywhere the value is
ephemeral (logging, metrics, elapsed math) or is written to / compared against a
`DateTime(timezone=True)` column — which is nearly every column in the schema.

DELIBERATE EXCEPTION — do NOT route these through `utcnow()`: the three naive `DateTime`
columns `OAuthState.expires_at` and `RefreshToken.expires_at`/`revoked_at` store naive UTC on
purpose and are written/compared with the stdlib `datetime.utcnow()` in `routers/auth.py` and
`services/refresh_token_service.py`. Mixing an aware value with those naive columns raises
"can't compare offset-naive and offset-aware datetimes" (Postgres returns tz-aware, SQLite
returns naive). Keep both the column and its comparisons naive — see those models' docstrings.
"""
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)
