"""Every outbound template renders a recipient's display name as literal text, never as markup.

The display name is user-supplied (waitlist join, registration, profile), so each template routes
it through ``email_service._greeting`` (HTML-escaped, one line) and embeds its hidden plain-text
copy through ``_hidden_text`` (escaped as a unit). This proof renders every sender with a
markup-shaped name and checks both the visible body and the hidden copy; the structural gate that
keeps new templates on the helpers is ``test_email_name_interpolation_allowlist.py``.
"""
import asyncio
import html

import pytest

from app.services import email_service
from app.services.email_service import (
    _greeting,
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
HIDDEN_OPEN = '<pre style="display:none">'

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
    """Capture the ``html`` document each sender hands to Resend."""
    documents: list[str] = []

    async def _record(to, subject, html, *args, **kwargs):
        documents.append(html)
        return {"id": "msg_test"}

    monkeypatch.setattr(email_service, "send_email", _record)
    return documents


def _split(document: str) -> tuple[str, str]:
    """(visible body, hidden plain-text copy) — every document carries exactly one hidden copy."""
    assert document.count(HIDDEN_OPEN) == 1, document
    visible, hidden = document.split(HIDDEN_OPEN)
    assert hidden.endswith("</pre>"), hidden[-40:]
    return visible, hidden[: -len("</pre>")]


@pytest.mark.parametrize("sender, kwargs", SENDERS, ids=[sender.__name__ for sender, _ in SENDERS])
def test_every_sender_renders_a_markup_shaped_name_as_text(sender, kwargs, sent):
    asyncio.run(sender(to_email="recipient@example.com", name=NAME, **kwargs))
    assert len(sent) == 1
    visible, hidden = _split(sent[0])

    # The payload never survives as markup — neither the whole tag nor its attribute.
    assert NAME not in sent[0]
    assert 'href="x"' not in sent[0]
    # The visible body greets the recipient with the escaped name.
    assert f"Hi {ESCAPED_NAME}," in visible
    # The hidden copy is escaped as a unit: it contains no tag characters at all.
    assert "<" not in hidden and ">" not in hidden
    assert "x" in hidden  # the name's text is still there, as text


@pytest.mark.parametrize(
    "render, kwargs",
    [
        (render_welcome_email, dict(position=1, referral_link="https://e.test/r", verification_link="https://e.test/v")),
        (render_referral_success_email, dict(new_position=1, referral_link="https://e.test/r")),
    ],
    ids=["welcome", "referral_success"],
)
def test_render_functions_keep_the_name_on_one_escaped_line(render, kwargs):
    html_doc, text = render(name="Eve\r\n<b>Bcc</b>: x", **kwargs)
    assert "<b>" not in html_doc and "<b>" not in text
    assert text.splitlines()[0] == "Hi Eve &lt;b&gt;Bcc&lt;/b&gt;: x,"


def test_greeting_helper_escapes_collapses_lines_and_falls_back_when_blank():
    assert _greeting(None) == "Hi there,"
    assert _greeting("") == "Hi there,"
    assert _greeting("  \r\n ") == "Hi there,"
    assert _greeting("Jane") == "Hi Jane,"
    assert _greeting("Eve\r\nBcc: x") == "Hi Eve Bcc: x,"
    assert _greeting('<a href="x">x</a>') == "Hi &lt;a href=&quot;x&quot;&gt;x&lt;/a&gt;,"
    assert _greeting("José Ñandú") == "Hi José Ñandú,"
