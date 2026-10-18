"""Every outbound template renders a recipient's display name as literal text, never as markup.

The display name is user-supplied (waitlist join, registration, profile), so each template routes
it through ``email_service._greeting`` for its page (HTML-escaped, one line) and through
``_greeting_text`` for its text part (one line, as typed: plain text is never read as markup, so an
escape would print as ``&lt;``). The text part goes to the provider as the mail's ``text``, and the
page hides no copy of it (E110). This proof renders every sender with a markup-shaped name and
checks the page and the text part; the structural gate that keeps new templates on the helpers is
``test_email_name_interpolation_allowlist.py``.
"""
import asyncio
import html

import pytest

from app.services import email_service
from app.services.email_service import (
    _greeting,
    _greeting_text,
    render_referral_success_email,
    render_welcome_email,
    send_account_exists_email,
    send_daily_digest,
    send_earnings_day_alert,
    send_invite_email,
    send_new_filing_alert,
    send_oauth_linked_email,
    send_password_reset_email,
    send_referral_success_email,
    send_verification_email,
    send_waitlist_welcome_email,
)

NAME = '<a href="x">x</a>'
ESCAPED_NAME = html.escape(NAME)

SENDERS = [
    (send_waitlist_welcome_email, dict(position=3, referral_link="https://e.test/r/abc", verification_link="https://e.test/v/t")),
    (send_referral_success_email, dict(new_position=2, referral_link="https://e.test/r/abc")),
    (send_verification_email, dict(verification_link="https://e.test/v/t")),
    (send_invite_email, dict(magic_link="https://e.test/i/t")),
    (send_password_reset_email, dict(reset_link="https://e.test/p/t")),
    (send_oauth_linked_email, dict(provider="Google")),
    (send_account_exists_email, dict(login_link="https://e.test/login", reset_link="https://e.test/forgot")),
    (send_earnings_day_alert, dict(items=[{"ticker": "ACME", "company_name": "Acme Corp"}])),
    (send_new_filing_alert, dict(company_name="Acme Corp", ticker="ACME", filing_type="10-K", filing_date="2026-01-01", filing_id=1)),
    (send_daily_digest, dict(items=[{"company_name": "Acme Corp", "ticker": "ACME", "filing_type": "10-K", "filing_date": "2026-01-01", "filing_id": 1}])),
]


@pytest.fixture
def sent(monkeypatch):
    """Capture the page and the text part each sender hands to Resend."""
    mails: list[tuple[str, str | None]] = []

    async def _record(to, subject, html, *args, **kwargs):
        mails.append((html, kwargs.get("text")))
        return {"id": "msg_test"}

    monkeypatch.setattr(email_service, "send_email", _record)
    return mails


@pytest.mark.parametrize("sender, kwargs", SENDERS, ids=[sender.__name__ for sender, _ in SENDERS])
def test_every_sender_renders_a_markup_shaped_name_as_text(sender, kwargs, sent):
    asyncio.run(sender(to_email="recipient@example.com", name=NAME, **kwargs))
    assert len(sent) == 1
    page, text = sent[0]

    # The name never survives in the page as markup, neither the whole tag nor its attribute; the page greets the
    # recipient with the escaped name and hides no copy of the text part.
    assert NAME not in page and 'href="x"' not in page
    assert f"Hi {ESCAPED_NAME}," in page
    assert "<pre" not in page
    # The text part greets the recipient with the name as typed, on its first line: plain text shows it as written.
    assert isinstance(text, str) and text.splitlines()[0] == f"Hi {NAME},"
    assert ESCAPED_NAME not in text


@pytest.mark.parametrize(
    "render, kwargs",
    [
        (render_welcome_email, dict(position=1, referral_link="https://e.test/r", verification_link="https://e.test/v")),
        (render_referral_success_email, dict(new_position=1, referral_link="https://e.test/r")),
    ],
    ids=["welcome", "referral_success"],
)
def test_render_functions_keep_the_name_on_one_line_escaped_in_the_page_and_as_typed_in_the_text(render, kwargs):
    html_doc, text = render(name="Eve\r\n<b>Bcc</b>: x", **kwargs)
    assert "<b>" not in html_doc and "Hi Eve &lt;b&gt;Bcc&lt;/b&gt;: x," in html_doc
    # One line: a line break in the name cannot start a line of its own in the text part.
    assert text.splitlines()[0] == "Hi Eve <b>Bcc</b>: x,"


def test_text_greeting_keeps_the_name_as_typed_collapses_lines_and_falls_back_when_blank():
    assert _greeting_text(None) == "Hi there,"
    assert _greeting_text("") == "Hi there,"
    assert _greeting_text("  \r\n ") == "Hi there,"
    assert _greeting_text("Jane") == "Hi Jane,"
    assert _greeting_text("Eve\r\nBcc: x") == "Hi Eve Bcc: x,"
    assert _greeting_text('<a href="x">x</a>') == 'Hi <a href="x">x</a>,'
    assert _greeting_text("Tom & Jerry") == "Hi Tom & Jerry,"
    assert _greeting_text("José Ñandú") == "Hi José Ñandú,"


def test_greeting_helper_escapes_collapses_lines_and_falls_back_when_blank():
    assert _greeting(None) == "Hi there,"
    assert _greeting("") == "Hi there,"
    assert _greeting("  \r\n ") == "Hi there,"
    assert _greeting("Jane") == "Hi Jane,"
    assert _greeting("Eve\r\nBcc: x") == "Hi Eve Bcc: x,"
    assert _greeting('<a href="x">x</a>') == "Hi &lt;a href=&quot;x&quot;&gt;x&lt;/a&gt;,"
    assert _greeting("José Ñandú") == "Hi José Ñandú,"
