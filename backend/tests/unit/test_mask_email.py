"""Unit tests for the log-safe e-mail renderers in ``app.utils.pii``.

These strings are the ONLY form in which an address may appear in application logs (gate:
``test_no_raw_email_in_logs.py``), so the contract is pinned exactly: first local-part character,
``***``, the whole domain — and nothing recoverable when the input has no ``local@domain`` shape.
"""
import pytest

from app.utils.pii import mask_email, mask_recipients


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("neil@example.com", "n***@example.com"),
        ("a@b", "a***@b"),                              # one-character local part
        ("  Neil@Example.COM  ", "N***@Example.COM"),   # trimmed, case preserved (it is log text)
        ("first.last+tag@sub.example.co.uk", "f***@sub.example.co.uk"),
        ('"odd@quoted"@example.com', '"***@example.com'),  # last '@' splits local/domain
        ("@example.com", "***"),                        # empty local part: nothing to keep
        ("neil@", "***"),                               # empty domain: nothing to keep
        ("not-an-address", "***"),
        ("", "<none>"),
        ("   ", "<none>"),
        (None, "<none>"),
        (42, "***"),                                    # non-string input never raises
    ],
)
def test_mask_email(raw, expected):
    assert mask_email(raw) == expected


def test_mask_email_never_contains_the_local_part():
    masked = mask_email("neilmacaogain@example.com")
    assert "neilmacaogain" not in masked
    assert masked == "n***@example.com"


@pytest.mark.parametrize(
    "recipients, expected",
    [
        (["a@x.com", "b@y.org"], "a***@x.com, b***@y.org"),  # Resend's ``to`` is a list
        (("a@x.com",), "a***@x.com"),
        (["a@x.com", None, "junk"], "a***@x.com, <none>, ***"),
        ([], "<none>"),
        (None, "<none>"),
        ("solo@x.com", "s***@x.com"),                          # a bare string still works
    ],
)
def test_mask_recipients(recipients, expected):
    assert mask_recipients(recipients) == expected
