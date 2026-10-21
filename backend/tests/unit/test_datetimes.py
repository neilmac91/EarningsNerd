"""Unit tests for app.utils.datetimes — the aware utcnow(), the iso_z() wire helper and utc_from_iso().

Regression guard for the aware-migration footgun: an aware ``utcnow().isoformat()`` renders the
offset as ``+00:00``, so the old ``… + "Z"`` produced a malformed ``…+00:00Z`` that round-trips to a
ValueError in parsers that strip a trailing ``Z``. ``iso_z`` reproduces the legacy naive ``…Z``
wire format instead.

``test_app_never_hand_appends_z`` is rule 7's gate for that footgun: no app/ code glues a literal
``Z`` onto an ``isoformat()`` result, by ``+`` or in an f-string.
"""
import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.utils.datetimes import iso_z, utc_from_iso, utcnow

APP_DIR = Path(__file__).resolve().parents[2] / "app"


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


@pytest.mark.parametrize("text, expected", [
    ("2026-01-15", datetime(2026, 1, 15, tzinfo=timezone.utc)),  # an SEC listing's bare date: UTC midnight
    ("2026-01-15T09:30:00", datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc)),
    ("2026-01-15T20:00:00-05:00", datetime(2026, 1, 16, 1, 0, tzinfo=timezone.utc)),
])
def test_utc_from_iso_is_aware_utc(text, expected):
    parsed = utc_from_iso(text)
    assert parsed == expected
    assert parsed.utcoffset() == timedelta(0)


def test_utc_from_iso_raises_what_fromisoformat_raises():
    """The filing scan skips a malformed listing row on ``ValueError``."""
    with pytest.raises(ValueError):
        utc_from_iso("2026-13-01")


def _is_isoformat_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "isoformat"


def _ends_with_isoformat_call(node: ast.AST) -> bool:
    """``x.isoformat()``, or a ``+`` chain whose last operand is one (``"at " + x.isoformat()``)."""
    while isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        node = node.right
    return _is_isoformat_call(node)


def _starts_with_z(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith("Z")


def _hand_appended_z(source: str) -> list[int]:
    """Lines where a literal ``Z`` follows an ``isoformat()`` call: ``x.isoformat() + "Z"`` or
    ``f"{x.isoformat()}Z"``. Docstrings and comments never match. A ``Z`` glued onto a variable that
    holds an earlier ``isoformat()`` result is out of reach; no app/ code builds one."""
    lines = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            if _ends_with_isoformat_call(node.left) and _starts_with_z(node.right):
                lines.append(node.lineno)
        elif isinstance(node, ast.JoinedStr):
            lines.extend(node.lineno for part, after in zip(node.values, node.values[1:])
                         if isinstance(part, ast.FormattedValue) and _is_isoformat_call(part.value)
                         and _starts_with_z(after))
    return lines


def test_app_never_hand_appends_z():
    found = [f"{path.relative_to(APP_DIR).as_posix()}:{line}"
             for path in sorted(APP_DIR.rglob("*.py"))
             for line in _hand_appended_z(path.read_text(encoding="utf-8"))]
    assert not found, (
        f"a literal Z glued onto isoformat() at {found}. An aware datetime already renders +00:00, so "
        "this writes a malformed ...+00:00Z. Serialize with app.utils.datetimes.iso_z(dt), or "
        "iso_z(ensure_utc(dt)) for a value loaded from the database (SQLite returns it naive)."
    )


@pytest.mark.parametrize(("source", "expected"), [
    ('def f(dt):\n    return dt.isoformat() + "Z"\n', [2]),
    ('def f():\n    return utcnow().isoformat(timespec="seconds") + "Z"\n', [2]),
    ('def f(dt):\n    return "at " + dt.isoformat() + "Z"\n', [2]),
    ('def f(dt):\n    return f"{dt.isoformat()}Z"\n', [2]),
    ('def f(dt):\n    return f"at {dt.isoformat()}Z, done"\n', [2]),
    ("def f(dt):\n    return iso_z(dt)\n", []),
    ("def f(dt):\n    return dt.isoformat()\n", []),
    ('def f(s):\n    return s.replace("Z", "+00:00")\n', []),
    ('def f(dt):\n    return f"{dt.isoformat()} UTC"\n', []),
    ('def f(dt):\n    return dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"\n', []),
    ('def f():\n    """Never dt.isoformat() + "Z"."""\n', []),
], ids=["plus", "plus with timespec", "plus chain", "f-string", "f-string mid-text", "iso_z", "bare isoformat",
        "parsing a Z", "other suffix", "other method", "docstring"])
def test_hand_appended_z_finder(source, expected):
    assert _hand_appended_z(source) == expected
