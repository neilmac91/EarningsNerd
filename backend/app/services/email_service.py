from __future__ import annotations

import html
import re

from app.config import settings
from app.services.resend_service import send_email

_LINE_BREAKS = re.compile(r"[\r\n]+")

_DEFAULT_FOOTER = "You are receiving this email because you joined the EarningsNerd waitlist."
# Alert/digest emails are transactional opt-ins, not the waitlist — point recipients at prefs.
_ALERT_FOOTER = (
    "You are receiving this because you track companies on EarningsNerd. "
    f'Manage alerts in your <a href="{settings.FRONTEND_URL}/dashboard/settings" '
    'style="color:#3C6650;">notification settings</a>.'
)


# The mail header's mark, the app tile (D-035), as the raster the frontend serves. Sent mail keeps
# this address for as long as the message is kept, so it is a published URL
# (frontend/public/assets/LOGO_README.md › Published URLs stay put): the path never moves, and it is
# built on FRONTEND_URL, the origin that answers without a redirect. Gates:
# tests/unit/test_mail_rendered_addresses.py reads the mail as it is sent, and
# tests/unit/test_mail_published_assets.py reads the code.
_HEADER_TILE_PATH = "/assets/earningsnerd-appicon.png"


def _wrap_html(body: str, footer: str = _DEFAULT_FOOTER) -> str:
    """The page of every mail this module builds: the brand header, the panel that holds ``body``
    and ``footer``, and the footer line.

    The header (the lockup, a hairline, the marked tagline) and the footer line are
    ``docs/brand/templates/email-header.html``, ported; tests/unit/test_mail_header_template.py
    holds the two to the same markup. That preview draws the tile as inline SVG, which Gmail and
    Outlook drop, so the mail shows the hosted raster in its place, with no Outlook conditional
    around it (Outlook shows a PNG) and an empty ``alt``: the text wordmark beside it names the
    brand, and carries it alone where images are blocked. The apps that darken a light-only message
    recolour its text and leave its images alone, which is why the header carries the tile, on its
    own ground, and not the bare mark.

    The page sets no viewport: it is 600 px wide, and a mail view fits a page that sets none to its
    screen, where one set to the device's width would leave the panel's right side off it. A view
    that fits the page to a phone's screen may enlarge its text to keep it readable. The header and
    the footer line keep the template's ``-webkit-text-size-adjust:100%``, so their lines stay at their
    set size, scaled with the page: enlarged, the tagline would outgrow the wordmark. The panel leaves
    its text to the view, which enlarges a body as it did before the header, so a reset link stays
    readable on a phone. The panel's padding is on its cells, which classic Outlook honours (it
    ignores a table's), so the body lines up under the header there too.
    """
    # A trailing slash is stripped, as the waitlist's links strip it: a doubled slash answers 308.
    tile_url = f"{settings.FRONTEND_URL.rstrip('/')}{_HEADER_TILE_PATH}"
    return f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="color-scheme" content="light">
        <meta name="supported-color-schemes" content="light">
      </head>
      <body style="margin:0;padding:0;background-color:#F4F3EE;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#F4F3EE" style="background-color:#F4F3EE;">
          <tr>
            <td align="center" style="padding:32px 12px 0 12px;">
              <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" bgcolor="#F4F3EE" style="width:600px;max-width:600px;background-color:#F4F3EE;-webkit-text-size-adjust:100%;">
                <tr>
                  <td style="padding:0 32px 20px 32px;">
                    <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td style="vertical-align:middle;padding:0 10px 0 0;line-height:0;">
                          <img src="{tile_url}" width="32" height="32" alt="" style="display:block;border:0;">
                        </td>
                        <td style="vertical-align:middle;font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;font-size:22px;line-height:30px;font-weight:700;letter-spacing:-0.44px;color:#1A1A17;">Earnings<em style="font-style:italic;color:#3C6650;">Nerd</em></td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <tr>
                  <td style="padding:0 32px;">
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                      <tr><td height="1" bgcolor="#E5E7EB" style="height:1px;background-color:#E5E7EB;font-size:1px;line-height:1px;">&nbsp;</td></tr>
                    </table>
                  </td>
                </tr>
                <tr>
                  <td style="padding:16px 32px 28px 32px;font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;font-size:18px;line-height:26px;font-weight:600;letter-spacing:-0.2px;color:#1A1A17;">The summary that <!--[if mso]>shows its work<![endif]--><!--[if !mso]><!--><span style="font-size:5.187px;line-height:0;vertical-align:-1.091px;background-color:#ECF2EE;border-bottom:2px solid #CFE0D6;white-space:nowrap;"><span style="font-size:18px;line-height:0;vertical-align:1.091px;">shows its work</span></span><!--<![endif]-->.</td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td align="center" style="padding:0 12px 24px 12px;">
              <table role="presentation" width="600" cellpadding="0" cellspacing="0" bgcolor="#FBFAF6" style="max-width:600px;background:#FBFAF6;border:1px solid #E5E1D8;border-radius:16px;color:#1A1A17;">
                <tr>
                  <td style="padding:32px 32px 0 32px;border-radius:15px 15px 0 0;font-size:16px;line-height:1.6;color:#1A1A17;">
                    {body}
                  </td>
                </tr>
                <tr>
                  <td style="padding:32px;border-radius:0 0 15px 15px;font-size:12px;color:#6B7280;">
                    {footer}
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td align="center" style="padding:0 12px 32px 12px;">
              <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:600px;max-width:600px;-webkit-text-size-adjust:100%;">
                <tr>
                  <td style="padding:0 32px;">
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                      <tr><td height="1" bgcolor="#E5E7EB" style="height:1px;background-color:#E5E7EB;font-size:1px;line-height:1px;">&nbsp;</td></tr>
                    </table>
                  </td>
                </tr>
                <tr>
                  <td style="padding:14px 32px 0 32px;font-family:-apple-system,BlinkMacSystemFont,Inter,'Segoe UI',Arial,sans-serif;font-size:12px;line-height:18px;color:#374151;">Data sourced from SEC EDGAR. Not investment advice.</td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """


def _greeting(name: str | None) -> str:
    """The salutation line of every template that addresses the recipient by name.

    The display name is user-supplied text, so this is the ONLY place it may enter a template:
    it is collapsed onto one line and HTML-escaped, so it can only ever render as literal text.
    A missing or blank name falls back to the neutral greeting. Gate:
    ``tests/unit/test_email_name_interpolation_allowlist.py``.
    """
    cleaned = _LINE_BREAKS.sub(" ", name or "").strip()
    return f"Hi {html.escape(cleaned)}," if cleaned else "Hi there,"


def _hidden_text(text: str) -> str:
    """The plain-text copy appended to each HTML email (hidden from HTML clients).

    It sits inside the HTML document, so the whole text is escaped as a unit before embedding —
    the same rule as the visible body: user-supplied text never becomes markup.
    """
    return f'<pre style="display:none">{html.escape(text)}</pre>'


def render_welcome_email(
    *,
    name: str | None,
    position: int,
    referral_link: str,
    verification_link: str,
) -> tuple[str, str]:
    greeting = _greeting(name)
    html_body = f"""
    <p style="margin:0 0 16px;">{greeting}</p>
    <p style="margin:0 0 16px;">You're on the EarningsNerd waitlist.</p>
    <p style="margin:0 0 16px;">Your current position: <strong>#{position}</strong></p>
    <p style="margin:0 0 20px;">
      Share your referral link to move up the list. Each successful referral bumps you up <strong>5 spots</strong>.
    </p>
    <p style="margin:0 0 20px;">
      <a href="{referral_link}" style="color:#3C6650;">{referral_link}</a>
    </p>
    <p style="margin:0 0 24px;">
      Please verify your email to secure your place:
      <a href="{verification_link}" style="color:#3C6650;font-weight:600;">Verify email</a>
    </p>
    <p style="margin:0;">We'll keep you posted as we open up access.</p>
    """
    text_body = (
        f"{greeting}\n\n"
        "You're officially on the EarningsNerd waitlist!\n"
        f"Your current position: #{position}\n\n"
        "Share your referral link to move up the list. Each successful referral bumps you up 5 spots.\n"
        f"{referral_link}\n\n"
        f"Verify your email to secure your place: {verification_link}\n\n"
        "We'll keep you posted as we open up access."
    )
    return _wrap_html(html_body), text_body


def render_referral_success_email(
    *,
    name: str | None,
    new_position: int,
    referral_link: str,
) -> tuple[str, str]:
    greeting = _greeting(name)
    html_body = f"""
    <p style="margin:0 0 16px;">{greeting}</p>
    <p style="margin:0 0 16px;">You moved up the EarningsNerd waitlist.</p>
    <p style="margin:0 0 16px;">Your new position: <strong>#{new_position}</strong></p>
    <p style="margin:0 0 20px;">
      Keep sharing your referral link to climb even faster:
      <a href="{referral_link}" style="color:#3C6650;">{referral_link}</a>
    </p>
    <p style="margin:0;">Thanks for spreading the word.</p>
    """
    text_body = (
        f"{greeting}\n\n"
        "You moved up the EarningsNerd waitlist.\n"
        f"Your new position: #{new_position}\n\n"
        "Keep sharing your referral link to climb even faster:\n"
        f"{referral_link}\n\n"
        "Thanks for spreading the word."
    )
    return _wrap_html(html_body), text_body


async def send_waitlist_welcome_email(
    *,
    to_email: str,
    name: str | None,
    position: int,
    referral_link: str,
    verification_link: str,
) -> None:
    html, text = render_welcome_email(
        name=name,
        position=position,
        referral_link=referral_link,
        verification_link=verification_link,
    )
    await send_email(
        to=[to_email],
        subject="You're on the EarningsNerd waitlist",
        html=f"{html}{_hidden_text(text)}",
    )


async def send_referral_success_email(
    *,
    to_email: str,
    name: str | None,
    new_position: int,
    referral_link: str,
) -> None:
    html, text = render_referral_success_email(
        name=name,
        new_position=new_position,
        referral_link=referral_link,
    )
    await send_email(
        to=[to_email],
        subject="You moved up the EarningsNerd waitlist",
        html=f"{html}{_hidden_text(text)}",
    )


async def send_verification_email(
    *,
    to_email: str,
    name: str | None,
    verification_link: str,
) -> None:
    greeting = _greeting(name)
    html_body = f"""
    <p style="margin:0 0 16px;">{greeting}</p>
    <p style="margin:0 0 16px;">Thanks for creating an EarningsNerd account. Verify your email address and you can start reading.</p>
    <p style="margin:0 0 24px;">
      <a href="{verification_link}" style="display:inline-block;background:#4F7A63;color:#ffffff;font-weight:700;font-size:15px;padding:12px 28px;border-radius:12px;text-decoration:none;">Verify my email</a>
    </p>
    <p style="margin:0 0 12px;font-size:14px;color:#6B7280;">This link expires in 24 hours. If you didn&apos;t create an account, you can safely ignore this email.</p>
    <p style="margin:0;font-size:12px;color:#6B7280;">Can&apos;t click the button? Copy this link:<br>{verification_link}</p>
    """
    text_body = (
        f"{greeting}\n\nVerify your email address and you can start reading.\n\n"
        f"{verification_link}\n\nThis link expires in 24 hours."
    )
    await send_email(
        to=[to_email],
        subject="Verify your EarningsNerd email",
        html=f"{_wrap_html(html_body)}{_hidden_text(text_body)}",
    )


async def send_invite_email(
    *,
    to_email: str,
    magic_link: str,
    name: str | None = None,
) -> None:
    """Closed-beta invite: a single-use magic link granting full Pro, no card required."""
    greeting = _greeting(name)
    invite_footer = "You're receiving this because you were invited to the EarningsNerd private beta."
    html_body = f"""
    <p style="margin:0 0 16px;">{greeting}</p>
    <p style="margin:0 0 16px;">You're invited to the EarningsNerd private beta. Full Pro access, on us.</p>
    <p style="margin:0 0 24px;">
      <a href="{magic_link}" style="display:inline-block;background:#4F7A63;color:#ffffff;font-weight:700;font-size:15px;padding:12px 28px;border-radius:12px;text-decoration:none;">Accept your invite</a>
    </p>
    <p style="margin:0 0 12px;font-size:14px;color:#6B7280;">This is a single-use invite link. No credit card required.</p>
    <p style="margin:0;font-size:12px;color:#6B7280;">Can&apos;t click the button? Copy this link:<br>{magic_link}</p>
    """
    text_body = (
        f"{greeting}\n\nYou're invited to the EarningsNerd private beta. Full Pro access, on us.\n\n"
        f"{magic_link}\n\nThis is a single-use invite link. No credit card required."
    )
    await send_email(
        to=[to_email],
        subject="Your EarningsNerd beta invite",
        html=f"{_wrap_html(html_body, invite_footer)}{_hidden_text(text_body)}",
    )


async def send_password_reset_email(
    *,
    to_email: str,
    name: str | None,
    reset_link: str,
) -> None:
    greeting = _greeting(name)
    html_body = f"""
    <p style="margin:0 0 16px;">{greeting}</p>
    <p style="margin:0 0 16px;">We received a request to reset your EarningsNerd password.</p>
    <p style="margin:0 0 24px;">
      <a href="{reset_link}" style="display:inline-block;background:#4F7A63;color:#ffffff;font-weight:700;font-size:15px;padding:12px 28px;border-radius:12px;text-decoration:none;">Reset my password</a>
    </p>
    <p style="margin:0 0 12px;font-size:14px;color:#6B7280;">This link expires in 1 hour and can only be used once. If you didn&apos;t request a reset, no action is needed.</p>
    <p style="margin:0;font-size:12px;color:#6B7280;">Can&apos;t click the button? Copy this link:<br>{reset_link}</p>
    """
    text_body = (
        f"{greeting}\n\nReset your EarningsNerd password:\n\n"
        f"{reset_link}\n\nThis link expires in 1 hour and can only be used once."
    )
    await send_email(
        to=[to_email],
        subject="Reset your EarningsNerd password",
        html=f"{_wrap_html(html_body)}{_hidden_text(text_body)}",
    )


async def send_oauth_linked_email(
    *,
    to_email: str,
    name: str | None,
    provider: str,
) -> None:
    """Sent when a social identity (Google/Apple) is linked to an existing account.

    A security notification: if the account owner didn't initiate it, it gives them a chance to
    react (reset password / contact support) rather than silently merging the identities."""
    greeting = _greeting(name)
    html_body = f"""
    <p style="margin:0 0 16px;">{greeting}</p>
    <p style="margin:0 0 16px;">A <strong>{provider}</strong> sign-in was just linked to your EarningsNerd account.</p>
    <p style="margin:0 0 12px;font-size:14px;color:#6B7280;">If this was you, no action is needed — you can now sign in with {provider}.</p>
    <p style="margin:0;font-size:14px;color:#B91C1C;">If this <strong>wasn&apos;t</strong> you, please reset your password immediately and contact support.</p>
    """
    text_body = (
        f"{greeting}\n\nA {provider} sign-in was just linked to your EarningsNerd account.\n\n"
        f"If this was you, no action is needed. If it wasn't, reset your password immediately "
        f"and contact support."
    )
    await send_email(
        to=[to_email],
        subject=f"A {provider} sign-in was linked to your EarningsNerd account",
        html=f"{_wrap_html(html_body)}{_hidden_text(text_body)}",
    )


async def send_account_exists_email(
    *,
    to_email: str,
    name: str | None,
    login_link: str,
    reset_link: str,
) -> None:
    """Sent when someone tries to register with an already-registered email (anti-enumeration)."""
    greeting = _greeting(name)
    html_body = f"""
    <p style="margin:0 0 16px;">{greeting}</p>
    <p style="margin:0 0 16px;">Someone tried to create an EarningsNerd account using this email address, but you already have one.</p>
    <p style="margin:0 0 8px;">
      <a href="{login_link}" style="display:inline-block;background:#4F7A63;color:#ffffff;font-weight:700;font-size:15px;padding:12px 28px;border-radius:12px;text-decoration:none;">Log in to your account</a>
    </p>
    <p style="margin:16px 0 0;font-size:14px;color:#6B7280;">Forgot your password?
      <a href="{reset_link}" style="color:#3C6650;">Reset it here</a>.
      If this wasn&apos;t you, no action is needed.</p>
    """
    text_body = (
        f"{greeting}\n\nSomeone tried to sign up with your email, but you already have an account.\n\n"
        f"Log in: {login_link}\nReset password: {reset_link}\n\nIf this wasn't you, no action is needed."
    )
    await send_email(
        to=[to_email],
        subject="Someone tried to sign up with your EarningsNerd email",
        html=f"{_wrap_html(html_body)}{_hidden_text(text_body)}",
    )


# --------------------------------------------------------------------------- new-filing alerts
# Content below is PUBLIC EDGAR data only (company, ticker, form type, date, filing URL). The
# recipient's email is the only PII and lives solely in the `to` field — never in the body or logs.

def _filing_url(filing_id: int | None, filing_url: str | None) -> str:
    """Prefer our own filing page (drives the user back into the product); fall back to SEC."""
    if filing_id is not None:
        return f"{settings.FRONTEND_URL}/filing/{filing_id}"
    return filing_url or settings.FRONTEND_URL


def wording_changes_line(wording_changes: dict | None, filing_type: str) -> str | None:
    """The "wording changes in Item 1A" field of a filing alert (tasks/todo.md E27, PR B), from the
    filing's cached comparison summary (``filing_section_service.wording_change_summaries``), or
    None when there is no comparison to report (nothing is written rather than a zero) or the
    filing's own section only points at the annual report. Pro recipients only: the caller
    passes the summary for a plan with ``section_changes``. Plain text; the renderers escape it."""
    if not wording_changes or wording_changes.get("reference_only"):
        return None
    total = int(wording_changes.get("items_total") or 0)
    if wording_changes.get("prior_reference_only"):
        # No count: the comparison's items also count the pointer paragraph(s) the prior lost, so
        # "N paragraphs" would overstate the section (the cards print the same line without one).
        return f"Risk factors restated in full since the prior {filing_type}."
    if wording_changes.get("has_changes") and total:
        return f"Risk factor wording: {total} paragraph{'s' if total != 1 else ''} changed since the prior {filing_type}."
    return f"Risk factor wording: no changes since the prior {filing_type}."


def _wording_html(line: str | None, url: str) -> str:
    if line is None:
        return ""
    return (
        f'<p style="margin:0 0 16px;font-size:14px;">{html.escape(line)} '
        f'<a href="{url}#what-changed" style="color:#3C6650;">Review the changes</a></p>'
    )


def render_new_filing_alert(
    *,
    name: str | None,
    company_name: str,
    ticker: str,
    filing_type: str,
    filing_date: str,
    filing_id: int | None = None,
    filing_url: str | None = None,
    wording_changes: dict | None = None,
) -> tuple[str, str]:
    greeting = _greeting(name)
    url = _filing_url(filing_id, filing_url)
    wording = wording_changes_line(wording_changes, filing_type)
    # SEC EDGAR fields are external data — escape before interpolating into HTML.
    e_company, e_ticker, e_type, e_date = (
        html.escape(company_name), html.escape(ticker), html.escape(filing_type), html.escape(filing_date)
    )
    html_body = f"""
    <p style="margin:0 0 16px;">{greeting}</p>
    <p style="margin:0 0 16px;"><strong>{e_company} ({e_ticker})</strong> just filed a
      <strong>{e_type}</strong> with the SEC ({e_date}).</p>
    {_wording_html(wording, url)}
    <p style="margin:0 0 24px;">
      <a href="{url}" style="display:inline-block;background:#4F7A63;color:#ffffff;font-weight:700;font-size:15px;padding:12px 28px;border-radius:12px;text-decoration:none;">Read the AI summary</a>
    </p>
    <p style="margin:0;font-size:13px;color:#6B7280;">We summarise what changed so you don&apos;t have to read the whole filing.</p>
    """
    text_body = (
        f"{greeting}\n\n{company_name} ({ticker}) just filed a {filing_type} with the SEC "
        f"({filing_date}).\n\n"
        + (f"{wording} Review the changes: {url}#what-changed\n\n" if wording else "")
        + f"Read the AI summary: {url}"
    )
    return _wrap_html(html_body, footer=_ALERT_FOOTER), text_body


def render_daily_digest(
    *,
    name: str | None,
    items: list[dict],
) -> tuple[str, str]:
    """`items`: dicts with company_name, ticker, filing_type, filing_date, and filing_id or filing_url;
    an optional ``wording_changes`` summary adds the Item 1A line (``wording_changes_line``)."""
    greeting = _greeting(name)

    def _row_wording(it: dict) -> str:
        line = wording_changes_line(it.get("wording_changes"), it["filing_type"])
        return f'<br><span style="font-size:14px;">{html.escape(line)}</span>' if line else ""

    # Escape external SEC EDGAR fields before interpolating into HTML.
    rows_html = "".join(
        f"""
        <tr>
          <td style="padding:10px 0;border-bottom:1px solid #E5E1D8;">
            <strong>{html.escape(it['company_name'])} ({html.escape(it['ticker'])})</strong> — {html.escape(it['filing_type'])}
            <span style="color:#6B7280;">· {html.escape(it['filing_date'])}</span>{_row_wording(it)}<br>
            <a href="{_filing_url(it.get('filing_id'), it.get('filing_url'))}" style="color:#3C6650;">Read the summary →</a>
          </td>
        </tr>"""
        for it in items
    )
    html_body = f"""
    <p style="margin:0 0 16px;">{greeting}</p>
    <p style="margin:0 0 16px;">New filings from companies you track:</p>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows_html}</table>
    """
    def _text_wording(it: dict) -> str:
        line = wording_changes_line(it.get("wording_changes"), it["filing_type"])
        return f" {line}" if line else ""

    text_lines = "\n".join(
        f"- {it['company_name']} ({it['ticker']}) — {it['filing_type']} ({it['filing_date']}):{_text_wording(it)} "
        f"{_filing_url(it.get('filing_id'), it.get('filing_url'))}"
        for it in items
    )
    text_body = f"{greeting}\n\nNew filings from companies you track:\n{text_lines}"
    return _wrap_html(html_body, footer=_ALERT_FOOTER), text_body


_DQ_FOOTER = (
    "Automated weekly data-quality report — a recurrence check over the remediation's detections. "
    "Empty detection sections are healthy; missing audit or judge evidence is unavailable."
)


def _dq_section(title: str, rows_html: str, count: int) -> str:
    body = rows_html if count else '<p style="margin:0 0 8px;color:#3C6650;">None — clean ✓</p>'
    return (
        f'<h3 style="margin:20px 0 8px;font-size:15px;color:#1A1A17;">{html.escape(title)} '
        f'<span style="color:#6B7280;font-weight:400;">({count})</span></h3>{body}'
    )


def _dq_rows(items: list[dict], cols) -> str:
    """A borderless HTML table, one row per item; each column callable is escaped before render."""
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:14px;">'
        + "".join(
            '<tr><td style="padding:6px 0;border-bottom:1px solid #E5E1D8;">'
            + " · ".join(html.escape(str(col(it))) for col in cols)
            + "</td></tr>"
            for it in items
        )
        + "</table>"
    )


def render_data_quality_report(report: dict) -> tuple[str, str]:
    """Render the weekly data-quality report (P1-9) into (html, text). External values (tickers,
    reasons) are escaped by `_dq_rows`; every section shows its count so an all-zero report reads
    as 'clean' at a glance."""
    mism = report.get("ticker_mismatches") or []
    notf = report.get("ticker_not_in_file") or []
    gaps = report.get("coverage_gaps") or []
    anom = report.get("filing_anomalies") or []
    partials = report.get("partial_reasons") or []
    coverage = report.get("universe_coverage") or {}
    jobs = report.get("job_health") or []
    coverage_rows = [{"metric": key.replace("_", " "), "value": "unavailable" if value is None else value}
                     for key, value in coverage.items()]
    job_rows = [{**job, "last_success": job["last_success"] or "never observed",
                 "health": "STALE" if job["stale"] else "current"} for job in jobs]
    audits = report.get("summary_audits") or {}
    audit_rows = []
    for name, family in audits.get("families", {}).items():
        counters = "; ".join(f"{key.replace('_', ' ')}={value}" for key, value in family["counts"].items())
        flag_label = {"figure_trace": "snapshots with untraceable figures",
                      "forward_quotes": "snapshots with unverified quotes",
                      "evidence_snap": "snapshots with unrepaired evidence",
                      "machine_sections_only": "machine-only snapshots", "quality": "partial snapshots"}[name]
        flag_rate = "unavailable" if family["flagged_pct"] is None else f"{family['flagged_pct']}% of recorded"
        audit_rows.append({"family": name.replace("_", " "),
            "population": f"recorded {family['recorded']} / snapshots {audits['snapshot_population']}",
            "unavailable": f"unavailable {family['unavailable']} (missing {family['missing']}, malformed {family['malformed']})",
            "counts": f"{flag_label}: {family['flagged']} ({flag_rate}); {counters}" if family["recorded"] else "counts unavailable"})
    if not audit_rows:
        audit_rows = [{"family": "Audits unavailable", "population": "No recorded population",
                       "unavailable": "No family evidence supplied", "counts": "counts unavailable"}]
    audit_note = (
        "Retained summary snapshots, not weekly generation attempts. Each family has its own "
        "recorded denominator. Missing audit may mean legacy data, unavailable grounding or no "
        "eligible content. An empty recorded figure list does not prove grounding was available. "
        "Would snap counts candidates; snapped counts performed replacements."
    )
    readout = report.get("weekly_readout") or {}
    readout_rows = [{"metric": "status", "value": readout.get("status", "unavailable")},
                    {"metric": "reason", "value": (readout.get("reason") or "none") if readout else "No weekly readout supplied"}]
    for key in ("expected", "completed", "scored", "errors", "missing", "negative_judgments",
                "deterministic_vetoes", "generator_model", "judge_model", "judge_backend",
                "source_sha", "cohort_sha256", "golden_set_sha256", "run_url", "artifact_url"):
        value = readout.get(key)
        label = {"generator_model": "configured generator model", "judge_model": "configured judge model"}.get(key, key.replace("_", " "))
        readout_rows.append({"metric": label, "value": "unavailable" if value is None else value})
    for key, value in (readout.get("dimensions") or {}).items():
        readout_rows.append({"metric": key, "value": "unavailable" if value is None else value})
    readout_note = (
        "Weekly generation cohort, separate from stored snapshots. Complete means all expected "
        "judge records were received; negative judgments remain visible. Unavailable or partial "
        "reports do not satisfy the first-readout prerequisite. This report never activates guards."
    )

    html_body = (
        '<p style="margin:0 0 16px;">Automated weekly scan of the data-quality detections.</p>'
        + _dq_section("Persisted summary audit snapshots", _dq_rows(
            audit_rows, [lambda x: x["family"], lambda x: x["population"],
                         lambda x: x["unavailable"], lambda x: x["counts"]]), len(audit_rows))
        + f"<p>{html.escape(audit_note)}</p>"
        + _dq_section("Weekly judged generation readout", _dq_rows(
            readout_rows, [lambda x: x["metric"], lambda x: x["value"]]), len(readout_rows))
        + f"<p>{html.escape(readout_note)}</p>"
        + _dq_section("Universe coverage (any stored summary; stubs have no summary)", _dq_rows(
            coverage_rows, [lambda x: x["metric"], lambda x: x["value"]]), len(coverage_rows))
        + _dq_section("Job health (stale after twice maximum cadence)", _dq_rows(
            job_rows, [lambda x: x["job"], lambda x: x["latest_status"],
                       lambda x: x["last_success"], lambda x: x["health"]]), len(job_rows))
        + _dq_section("Ticker mismatches (stored ≠ SEC primary)", _dq_rows(
            mism, [lambda x: x["ticker"], lambda x: f'→ {x["primary"]}', lambda x: f'CIK {x["cik"]}']), len(mism))
        + _dq_section("Coverage gaps (concept lags total assets ≥2y)", _dq_rows(
            gaps, [lambda x: x["ticker"], lambda x: x["concept"],
                   lambda x: f'last FY {x["last_fy"] or "—"} vs assets {x["last_total_assets_fy"]}']), len(gaps))
        + _dq_section("Filing-count anomalies (deep facts, few 10-Ks)", _dq_rows(
            anom, [lambda x: x["ticker"], lambda x: f'{x["first_fact_fy"]}–{x["last_fact_fy"]}',
                   lambda x: f'{x["stored_10k_rows"]} 10-K rows']), len(anom))
        + _dq_section("Partial-summary reasons by SIC", _dq_rows(
            partials, [lambda x: f'SIC {x["sic_prefix"]}', lambda x: x["reason"], lambda x: f'×{x["count"]}']), len(partials))
        + _dq_section("Tickers not in the SEC file (delisted — informational)", _dq_rows(
            notf, [lambda x: x["ticker"], lambda x: f'CIK {x["cik"]}']), len(notf))
    )

    text_lines = [
        "Persisted summary audit snapshots:",
        *[f"  {r['family']}: {r['population']}; {r['unavailable']}; {r['counts']}" for r in audit_rows],
        audit_note,
        "Weekly judged generation readout:",
        *[f"  {r['metric']}: {r['value']}" for r in readout_rows],
        readout_note,
        "Universe coverage (any stored summary; stubs have no summary):",
        *[f"  {r['metric']}: {r['value']}" for r in coverage_rows],
        "Job health (stale after twice maximum cadence):",
        *[f"  {r['job']}: {r['latest_status']}; last success {r['last_success']}; {r['health']}" for r in job_rows],
        f"Ticker mismatches: {len(mism)}",
        *[f"  {m['ticker']} -> {m['primary']} (CIK {m['cik']})" for m in mism],
        f"Coverage gaps: {len(gaps)}",
        *[f"  {g['ticker']} {g['concept']}: last FY {g['last_fy'] or '-'} vs assets {g['last_total_assets_fy']}" for g in gaps],
        f"Filing anomalies: {len(anom)}",
        *[f"  {a['ticker']} {a['first_fact_fy']}-{a['last_fact_fy']}, {a['stored_10k_rows']} 10-K rows" for a in anom],
        f"Partial reasons: {len(partials)}",
        *[f"  SIC {p['sic_prefix']} | {p['reason']} x{p['count']}" for p in partials],
        f"Not in SEC file (delisted): {len(notf)}",
        *[f"  {n['ticker']} (CIK {n['cik']})" for n in notf],
    ]
    text_body = "EarningsNerd data-quality report\n\n" + "\n".join(text_lines)
    return _wrap_html(html_body, footer=_DQ_FOOTER), text_body


_TIME_LABEL = {"bmo": "before open", "amc": "after close", "dmh": "during market hours"}


def render_earnings_day_alert(
    *,
    name: str | None,
    items: list[dict],
) -> tuple[str, str]:
    """`items`: dicts with ticker, company_name, and optional time (bmo|amc|dmh) + status."""
    greeting = _greeting(name)
    rows_html = ""
    for it in items:
        ticker = html.escape(str(it.get("ticker", "")))
        company = html.escape(str(it.get("company_name") or it.get("ticker") or ""))
        slot = _TIME_LABEL.get((it.get("time") or "").lower())
        when = f'<span style="color:#6B7280;"> · {slot}</span>' if slot else ""
        reported = (it.get("status") == "reported")
        tail = " (results are out)" if reported else ""
        rows_html += f"""
        <tr>
          <td style="padding:10px 0;border-bottom:1px solid #E5E1D8;">
            <strong>{company} ({ticker})</strong> reports today{when}{html.escape(tail)}<br>
            <a href="{settings.FRONTEND_URL}/company/{ticker}" style="color:#3C6650;">View {ticker} →</a>
          </td>
        </tr>"""
    html_body = f"""
    <p style="margin:0 0 16px;">{greeting}</p>
    <p style="margin:0 0 16px;">Companies you follow report earnings today:</p>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows_html}</table>
    <p style="margin:16px 0 0;font-size:13px;color:#6B7280;">We'll have the AI summary ready shortly after they file.</p>
    """
    text_lines = "\n".join(
        f"- {it.get('company_name') or it.get('ticker')} ({it.get('ticker')}) reports today"
        + (f" ({_TIME_LABEL[(it.get('time') or '').lower()]})" if (it.get('time') or '').lower() in _TIME_LABEL else "")
        for it in items
    )
    text_body = f"{greeting}\n\nCompanies you follow report earnings today:\n{text_lines}"
    return _wrap_html(html_body, footer=_ALERT_FOOTER), text_body


async def send_earnings_day_alert(
    *,
    to_email: str,
    name: str | None,
    items: list[dict],
) -> None:
    html_body, text = render_earnings_day_alert(name=name, items=items)
    n = len(items)
    if n == 1:
        subject = f"{items[0].get('ticker')} reports earnings today"
    else:
        subject = f"{n} companies you follow report earnings today"
    await send_email(
        to=[to_email],
        subject=subject,
        html=f"{html_body}{_hidden_text(text)}",
    )


async def send_new_filing_alert(
    *,
    to_email: str,
    name: str | None,
    company_name: str,
    ticker: str,
    filing_type: str,
    filing_date: str,
    filing_id: int | None = None,
    filing_url: str | None = None,
    wording_changes: dict | None = None,
) -> None:
    subject, html = build_new_filing_alert(
        name=name,
        company_name=company_name,
        ticker=ticker,
        filing_type=filing_type,
        filing_date=filing_date,
        filing_id=filing_id,
        filing_url=filing_url,
        wording_changes=wording_changes,
    )
    await send_email(to=[to_email], subject=subject, html=html)


def build_new_filing_alert(
    *,
    name: str | None,
    company_name: str,
    ticker: str,
    filing_type: str,
    filing_date: str,
    filing_id: int | None = None,
    filing_url: str | None = None,
    wording_changes: dict | None = None,
) -> tuple[str, str]:
    """The exact ``(subject, html)`` a new-filing alert sends; frozen on a delivery batch (E11b-1).
    ``wording_changes`` (a Pro recipient's Item 1A comparison summary, when known at selection
    time) adds the wording line; the real-time pass usually precedes the extraction batch, so the
    digest and a rebuilt batch carry it more often than the first alert does."""
    html, text = render_new_filing_alert(
        name=name,
        company_name=company_name,
        ticker=ticker,
        filing_type=filing_type,
        filing_date=filing_date,
        filing_id=filing_id,
        filing_url=filing_url,
        wording_changes=wording_changes,
    )
    return f"{ticker} filed a {filing_type}", f"{html}{_hidden_text(text)}"


async def send_daily_digest(
    *,
    to_email: str,
    name: str | None,
    items: list[dict],
) -> None:
    subject, html = build_daily_digest(name=name, items=items)
    await send_email(to=[to_email], subject=subject, html=html)


def build_daily_digest(*, name: str | None, items: list[dict]) -> tuple[str, str]:
    """The exact ``(subject, html)`` a digest sends; frozen on a delivery batch (E11b-1)."""
    html, text = render_daily_digest(name=name, items=items)
    count = len(items)
    subject = f"{count} new filing{'s' if count != 1 else ''} from your watchlist"
    return subject, f"{html}{_hidden_text(text)}"
