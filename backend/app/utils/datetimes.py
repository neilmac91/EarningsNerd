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


def iso_z(dt: datetime) -> str:
    """ISO 8601 string with a ``Z`` suffix for a UTC datetime, e.g. ``2026-07-06T10:52:35.123456Z``.

    Use this instead of ``dt.isoformat() + "Z"``: an aware ``dt`` already renders the offset as
    ``+00:00``, so appending ``Z`` doubles the zone (``…+00:00Z``) — malformed, and it round-trips
    to a ``ValueError`` in parsers that strip a trailing ``Z``. Replacing the offset with ``Z``
    reproduces the legacy naive ``datetime.utcnow().isoformat() + "Z"`` wire format (what browsers'
    ``new Date()`` and our cache ``_parse_timestamp`` expect). Pass a tz-aware UTC datetime.
    """
    return dt.isoformat().replace("+00:00", "Z")
