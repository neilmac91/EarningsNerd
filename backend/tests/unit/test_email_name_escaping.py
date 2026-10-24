"""Every outbound template renders a recipient's display name as literal text, never as markup.

The display name is user-supplied (waitlist join, registration, profile), so each template routes
it through ``email_service._greeting`` for its page (HTML-escaped, one line) and through
``_greeting_text`` for its text part (one line, as typed: plain text is never read as markup, so an
escape would print as ``&lt;``). The text part goes to the provider as the mail's ``text``, and the
page hides no copy of it (E110). This proof renders every sender with a markup-shaped name and
checks the page and the text part, and holds its list to every ``send_`` function that takes a name;
the structural gate that keeps new templates on the helpers is
``test_email_name_interpolation_allowlist.py``.
"""
import ast
import asyncio
import html
import inspect
import re
from pathlib import Path

import pytest

from app.services import email_service, legal_readiness_service
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
from tests.unit.test_email_name_interpolation_allowlist import NAME_IDS

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


def _greeting_senders(source: str) -> set[str]:
    """The ``send_`` functions a module defines, coroutines or not, that take a recipient's name by any name the
    interpolation gate reads as one (``NAME_IDS``), however it is passed: every sender that greets its reader."""
    return {
        node.name
        for node in ast.parse(source).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("send_")
        and NAME_IDS & {argument.arg for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)}
    }


_SENDERS_PROBE = """
async def send_greets(*, to_email, name): ...
async def send_greets_positionally(to_email, name): ...
async def send_greets_by_full_name(*, to_email, full_name): ...
def send_greets_synchronously(*, to_email, name): ...
def send_greets_positional_only(name, /, to_email): ...
async def send_no_name(*, to_email): ...
async def send_company_name(*, to_email, company_name): ...
async def render_greets(*, name): ...
"""


def test_the_proof_renders_every_sender_that_greets_by_name():
    # A gate that cannot fail proves nothing: the reader of the module's senders, on a probe.
    assert _greeting_senders(_SENDERS_PROBE) == {
        "send_greets", "send_greets_positionally", "send_greets_by_full_name", "send_greets_synchronously",
        "send_greets_positional_only",
    }
    module = Path(email_service.__file__).read_text(encoding="utf-8")
    listed = {sender.__name__ for sender, _kwargs in SENDERS}
    assert _greeting_senders(module) == listed, (
        "every send_ function that takes a name is rendered here with a markup-shaped one, so a page that greets "
        f"without escaping fails: add {sorted(_greeting_senders(module) - listed)} to SENDERS, drop "
        f"{sorted(listed - _greeting_senders(module))}"
    )


@pytest.fixture
def sent(monkeypatch):
    """Capture the page and the text part each sender hands to Resend."""
    mails: list[tuple[str, str | None]] = []

    async def _record(to, subject, html, *args, **kwargs):
        mails.append((html, kwargs.get("text")))
        return {"id": "msg_test"}

    monkeypatch.setattr(email_service, "send_email", _record)
    # Render dormant promotional templates too; the readiness suite proves they cannot dispatch.
    monkeypatch.setattr(legal_readiness_service, "is_marketing_available", lambda: True)
    return mails


@pytest.mark.parametrize("sender, kwargs", SENDERS, ids=[sender.__name__ for sender, _ in SENDERS])
def test_every_sender_renders_a_markup_shaped_name_as_text(sender, kwargs, sent):
    # The name goes in by the sender's own parameter for it, and a sender that is no coroutine runs as it is.
    parameter = next(name for name in inspect.signature(sender).parameters if name in NAME_IDS)
    result = sender(to_email="recipient@example.com", **{parameter: NAME}, **kwargs)
    if inspect.iscoroutine(result):
        asyncio.run(result)
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
    html_doc, text = render(name="Eve\r\n<b>Bcc</b>:\u2029x", **kwargs)
    assert "<b>" not in html_doc and "Hi Eve &lt;b&gt;Bcc&lt;/b&gt;: x," in html_doc
    # One line: no line separator in the name, a paragraph separator among them, starts a line of its own in the
    # text part.
    assert text.splitlines()[0] == "Hi Eve <b>Bcc</b>: x,"


def test_text_greeting_keeps_the_name_as_typed_collapses_lines_and_falls_back_when_blank():
    assert _greeting_text(None) == "Hi there,"
    assert _greeting_text("") == "Hi there,"
    assert _greeting_text("  \r\n ") == "Hi there,"
    assert _greeting_text("Jane") == "Hi Jane,"
    assert _greeting_text("Eve\r\nBcc: x") == "Hi Eve Bcc: x,"
    # Every line separator str.splitlines knows, the Unicode ones a form lets through among them, each run one space.
    assert _greeting_text("Eve\u2028Bcc:\u2029x\x85y\x1cz\x1dq\x1er\x0bw\x0cv\r\n\u2028u") == "Hi Eve Bcc: x y z q r w v u,"
    # The rest as typed: a run of spaces, a tab, the wide space a Japanese keyboard types between names, a no-break
    # space, none of which breaks a line.
    assert _greeting_text("Jane  Doe\tX") == "Hi Jane  Doe\tX,"
    assert _greeting_text("山田\u3000太郎") == "Hi 山田\u3000太郎,"
    assert _greeting_text("Ann\u00a0Lee\u202fX") == "Hi Ann\u00a0Lee\u202fX,"
    assert _greeting_text('<a href="x">x</a>') == 'Hi <a href="x">x</a>,'
    assert _greeting_text("Tom & Jerry") == "Hi Tom & Jerry,"
    assert _greeting_text("José Ñandú") == "Hi José Ñandú,"


def test_greeting_helper_escapes_collapses_lines_and_falls_back_when_blank():
    assert _greeting(None) == "Hi there,"
    assert _greeting("") == "Hi there,"
    assert _greeting("  \r\n ") == "Hi there,"
    assert _greeting("Jane") == "Hi Jane,"
    assert _greeting("Eve\r\nBcc: x") == "Hi Eve Bcc: x,"
    assert _greeting("Eve\u2028Bcc: x") == "Hi Eve Bcc: x,"
    assert _greeting('<a href="x">x</a>') == "Hi &lt;a href=&quot;x&quot;&gt;x&lt;/a&gt;,"
    assert _greeting("José Ñandú") == "Hi José Ñandú,"


@pytest.mark.parametrize("name", ["Jane", "Jane  Doe", "  Bob\t", "山田\u3000太郎", "Ann\u00a0Lee", "Eve\r\n\r\nBcc", "Tom & <Jerry>", None, ""])
def test_the_page_greets_as_main_did_for_a_name_holding_no_other_line_separator(name):
    # Main collapsed CR and LF alone (``[\r\n]+``) and stripped the ends; E110 adds the other line separators, so
    # a page greets any other name as main did, byte for byte.
    cleaned = re.sub(r"[\r\n]+", " ", name or "").strip()
    assert _greeting(name) == (f"Hi {html.escape(cleaned)}," if cleaned else "Hi there,")
