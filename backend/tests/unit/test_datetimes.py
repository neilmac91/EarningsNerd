"""Unit tests for app.utils.datetimes — the aware utcnow() + iso_z() wire helper.

Regression guard for the aware-migration footgun: an aware ``utcnow().isoformat()`` renders the
offset as ``+00:00``, so the old ``… + "Z"`` produced a malformed ``…+00:00Z`` that round-trips to a
ValueError in parsers that strip a trailing ``Z`` (trending_service._parse_timestamp,
hot_filings router). ``iso_z`` reproduces the legacy naive ``…Z`` wire format instead.
"""
from datetime import datetime, timezone

from app.utils.datetimes import iso_z, utcnow


def test_utcnow_is_timezone_aware_utc():
    now = utcnow()
    assert now.tzinfo is not None
    assert now.utcoffset() == timezone.utc.utcoffset(None)


def test_iso_z_is_z_suffixed_not_offset():
    s = iso_z(utcnow())
    assert s.endswith("Z")
    assert "+00:00" not in s  # the bug was a malformed "+00:00Z"


def test_iso_z_preserves_microseconds():
    dt = datetime(2026, 7, 6, 10, 52, 35, 123456, tzinfo=timezone.utc)
    assert iso_z(dt) == "2026-07-06T10:52:35.123456Z"


def test_iso_z_without_microseconds():
    dt = datetime(2026, 7, 6, 10, 52, 35, tzinfo=timezone.utc)
    assert iso_z(dt) == "2026-07-06T10:52:35Z"


def test_iso_z_round_trips_via_fromisoformat():
    dt = utcnow()
    restored = datetime.fromisoformat(iso_z(dt).replace("Z", "+00:00"))
    assert restored == dt


def test_iso_z_round_trips_through_trending_parse_timestamp():
    # The exact cache round-trip Gemini flagged: a "+00:00Z" value made _parse_timestamp raise.
    from app.services.trending_service import trending_service

    parsed = trending_service._parse_timestamp(iso_z(utcnow()))
    assert isinstance(parsed, datetime)
    assert parsed.tzinfo is not None
