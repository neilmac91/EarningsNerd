"""The public signup names are bounded and control-free before they reach storage or an email.

``WaitlistJoinRequest.name`` / ``.source`` (POST /api/waitlist/join) and ``UserCreate.full_name``
(POST /api/auth/register) share one contract, mirroring ``users.ProfileUpdate``: trimmed, empty
clears to ``None``, at most 100 characters, and no control characters (Unicode category Cc).
"""
import pytest
from pydantic import ValidationError

from app.routers.auth import UserCreate
from app.routers.watchlist import WaitlistJoinRequest
from app.utils.text import has_control_characters

VALID_PASSWORD = "Sup3rSecretPassw0rd"  # >=12 chars, upper+lower+digit; test fixture, not a credential  # gitleaks:allow


def _waitlist_name(value):
    return WaitlistJoinRequest(email="a@example.com", name=value).name


def _waitlist_source(value):
    return WaitlistJoinRequest(email="a@example.com", source=value).source


def _user_full_name(value):
    return UserCreate(email="a@example.com", password=VALID_PASSWORD, full_name=value).full_name


FIELDS = [
    pytest.param(_waitlist_name, id="waitlist.name"),
    pytest.param(_waitlist_source, id="waitlist.source"),
    pytest.param(_user_full_name, id="register.full_name"),
]


@pytest.mark.parametrize("parse", FIELDS)
def test_trims_and_clears_blank_values(parse):
    assert parse(None) is None
    assert parse("") is None
    assert parse("   ") is None
    assert parse("  Jane Doe  ") == "Jane Doe"


@pytest.mark.parametrize("parse", FIELDS)
def test_accepts_any_script_up_to_100_characters(parse):
    assert parse("José Ñandú 李雷 Ælfric O'Brien-Smith") == "José Ñandú 李雷 Ælfric O'Brien-Smith"
    assert parse("x" * 100) == "x" * 100


@pytest.mark.parametrize("parse", FIELDS)
def test_rejects_more_than_100_characters(parse):
    with pytest.raises(ValidationError) as exc:
        parse("x" * 101)
    assert exc.value.errors()[0]["type"] == "string_too_long"


@pytest.mark.parametrize("parse", FIELDS)
@pytest.mark.parametrize("bad", ["Jane\x00Doe", "Eve\r\nBcc: x", "tab\there", "del\x7fete", "c1\x85nel"])
def test_rejects_control_characters(parse, bad):
    with pytest.raises(ValidationError) as exc:
        parse(bad)
    assert "control characters" in str(exc.value)


def test_has_control_characters_is_category_cc_only():
    assert has_control_characters("\n") and has_control_characters("\x00") and has_control_characters("\x9f")
    assert not has_control_characters("plain text, with punctuation!")
    assert not has_control_characters("non breaking space and zero‌width non-joiner")  # Zs / Cf pass
