from __future__ import annotations

import html

from app.config import settings
from app.services.resend_service import send_email

_DEFAULT_FOOTER = "You are receiving this email because you joined the EarningsNerd waitlist."
# Alert/digest emails are transactional opt-ins, not the waitlist — point recipients at prefs.
_ALERT_FOOTER = (
    "You are receiving this because you track companies on EarningsNerd. "
    f'Manage alerts in your <a href="{settings.FRONTEND_URL}/dashboard/settings" '
    'style="color:#3C6650;">notification settings</a>.'
)


def _wrap_html(body: str, footer: str = _DEFAULT_FOOTER) -> str:
    return f"""
    <html>
      <body style="margin:0;padding:0;background:#F4F3EE;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F4F3EE;padding:32px 12px;">
          <tr>
            <td align="center">
              <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;background:#FBFAF6;border:1px solid #E5E1D8;border-radius:16px;padding:32px;color:#1A1A17;">
                <tr>
                  <td style="font-size:22px;font-weight:700;color:#1A1A17;">Earnings<em style="color:#3C6650;font-style:italic;">Nerd</em></td>
                </tr>
                <tr>
                  <td style="padding-top:16px;font-size:16px;line-height:1.6;color:#1A1A17;">
                    {body}
                  </td>
                </tr>
                <tr>
                  <td style="padding-top:32px;font-size:12px;color:#6B7280;">
                    {footer}
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """


def render_welcome_email(
    *,
    name: str | None,
    position: int,
    referral_link: str,
    verification_link: str,
) -> tuple[str, str]:
    greeting = f"Hi {name}," if name else "Hi there,"
    html_body = f"""
    <p style="margin:0 0 16px;">{greeting}</p>
    <p style="margin:0 0 16px;">You're officially on the EarningsNerd waitlist! 🎉</p>
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
    greeting = f"Hi {name}," if name else "Hi there,"
    html_body = f"""
    <p style="margin:0 0 16px;">{greeting}</p>
    <p style="margin:0 0 16px;">You just moved up the EarningsNerd waitlist!</p>
    <p style="margin:0 0 16px;">Your new position: <strong>#{new_position}</strong></p>
    <p style="margin:0 0 20px;">
      Keep sharing your referral link to climb even faster:
      <a href="{referral_link}" style="color:#3C6650;">{referral_link}</a>
    </p>
    <p style="margin:0;">Thanks for spreading the word.</p>
    """
    text_body = (
        f"{greeting}\n\n"
        "You just moved up the EarningsNerd waitlist!\n"
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
        subject="You're on the EarningsNerd waitlist! 🎉",
        html=f"{html}<pre style=\"display:none\">{text}</pre>",
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
        subject="You just moved up the EarningsNerd waitlist!",
        html=f"{html}<pre style=\"display:none\">{text}</pre>",
    )


async def send_verification_email(
    *,
    to_email: str,
    name: str | None,
    verification_link: str,
) -> None:
    greeting = f"Hi {name}," if name else "Hi there,"
    html_body = f"""
    <p style="margin:0 0 16px;">{greeting}</p>
    <p style="margin:0 0 16px;">Thanks for creating an EarningsNerd account. Please verify your email address to unlock AI-powered SEC filing summaries.</p>
    <p style="margin:0 0 24px;">
      <a href="{verification_link}" style="display:inline-block;background:#4F7A63;color:#ffffff;font-weight:700;font-size:15px;padding:12px 28px;border-radius:12px;text-decoration:none;">Verify my email</a>
    </p>
    <p style="margin:0 0 12px;font-size:14px;color:#6B7280;">This link expires in 24 hours. If you didn&apos;t create an account, you can safely ignore this email.</p>
    <p style="margin:0;font-size:12px;color:#6B7280;">Can&apos;t click the button? Copy this link:<br>{verification_link}</p>
    """
    text_body = (
        f"{greeting}\n\nPlease verify your email address to unlock EarningsNerd.\n\n"
        f"{verification_link}\n\nThis link expires in 24 hours."
    )
    await send_email(
        to=[to_email],
        subject="Verify your EarningsNerd email",
        html=f"{_wrap_html(html_body)}<pre style=\"display:none\">{text_body}</pre>",
    )


async def send_invite_email(
    *,
    to_email: str,
    magic_link: str,
    name: str | None = None,
) -> None:
    """Closed-beta invite: a single-use magic link granting full Pro, no card required."""
    greeting = f"Hi {name}," if name else "Hi there,"
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
        html=f"{_wrap_html(html_body, invite_footer)}<pre style=\"display:none\">{text_body}</pre>",
    )


async def send_password_reset_email(
    *,
    to_email: str,
    name: str | None,
    reset_link: str,
) -> None:
    greeting = f"Hi {name}," if name else "Hi there,"
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
        html=f"{_wrap_html(html_body)}<pre style=\"display:none\">{text_body}</pre>",
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
    greeting = f"Hi {name}," if name else "Hi there,"
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
        html=f"{_wrap_html(html_body)}<pre style=\"display:none\">{text_body}</pre>",
    )


async def send_account_exists_email(
    *,
    to_email: str,
    name: str | None,
    login_link: str,
    reset_link: str,
) -> None:
    """Sent when someone tries to register with an already-registered email (anti-enumeration)."""
    greeting = f"Hi {name}," if name else "Hi there,"
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
        html=f"{_wrap_html(html_body)}<pre style=\"display:none\">{text_body}</pre>",
    )


# --------------------------------------------------------------------------- new-filing alerts
# Content below is PUBLIC EDGAR data only (company, ticker, form type, date, filing URL). The
# recipient's email is the only PII and lives solely in the `to` field — never in the body or logs.

def _filing_url(filing_id: int | None, filing_url: str | None) -> str:
    """Prefer our own filing page (drives the user back into the product); fall back to SEC."""
    if filing_id is not None:
        return f"{settings.FRONTEND_URL}/filing/{filing_id}"
    return filing_url or settings.FRONTEND_URL


def render_new_filing_alert(
    *,
    name: str | None,
    company_name: str,
    ticker: str,
    filing_type: str,
    filing_date: str,
    filing_id: int | None = None,
    filing_url: str | None = None,
) -> tuple[str, str]:
    greeting = f"Hi {html.escape(name)}," if name else "Hi there,"
    url = _filing_url(filing_id, filing_url)
    # SEC EDGAR fields are external data — escape before interpolating into HTML.
    e_company, e_ticker, e_type, e_date = (
        html.escape(company_name), html.escape(ticker), html.escape(filing_type), html.escape(filing_date)
    )
    html_body = f"""
    <p style="margin:0 0 16px;">{greeting}</p>
    <p style="margin:0 0 16px;"><strong>{e_company} ({e_ticker})</strong> just filed a
      <strong>{e_type}</strong> with the SEC ({e_date}).</p>
    <p style="margin:0 0 24px;">
      <a href="{url}" style="display:inline-block;background:#4F7A63;color:#ffffff;font-weight:700;font-size:15px;padding:12px 28px;border-radius:12px;text-decoration:none;">Read the AI summary</a>
    </p>
    <p style="margin:0;font-size:13px;color:#6B7280;">We summarise what changed so you don&apos;t have to read the whole filing.</p>
    """
    text_body = (
        f"{greeting}\n\n{company_name} ({ticker}) just filed a {filing_type} with the SEC "
        f"({filing_date}).\n\nRead the AI summary: {url}"
    )
    return _wrap_html(html_body, footer=_ALERT_FOOTER), text_body


def render_daily_digest(
    *,
    name: str | None,
    items: list[dict],
) -> tuple[str, str]:
    """`items`: dicts with company_name, ticker, filing_type, filing_date, and filing_id or filing_url."""
    greeting = f"Hi {html.escape(name)}," if name else "Hi there,"
    # Escape external SEC EDGAR fields before interpolating into HTML.
    rows_html = "".join(
        f"""
        <tr>
          <td style="padding:10px 0;border-bottom:1px solid #E5E1D8;">
            <strong>{html.escape(it['company_name'])} ({html.escape(it['ticker'])})</strong> — {html.escape(it['filing_type'])}
            <span style="color:#6B7280;">· {html.escape(it['filing_date'])}</span><br>
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
    text_lines = "\n".join(
        f"- {it['company_name']} ({it['ticker']}) — {it['filing_type']} ({it['filing_date']}): "
        f"{_filing_url(it.get('filing_id'), it.get('filing_url'))}"
        for it in items
    )
    text_body = f"{greeting}\n\nNew filings from companies you track:\n{text_lines}"
    return _wrap_html(html_body, footer=_ALERT_FOOTER), text_body


_TIME_LABEL = {"bmo": "before open", "amc": "after close", "dmh": "during market hours"}


def render_earnings_day_alert(
    *,
    name: str | None,
    items: list[dict],
) -> tuple[str, str]:
    """`items`: dicts with ticker, company_name, and optional time (bmo|amc|dmh) + status."""
    greeting = f"Hi {html.escape(name)}," if name else "Hi there,"
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
        html=f"{html_body}<pre style=\"display:none\">{text}</pre>",
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
) -> None:
    html, text = render_new_filing_alert(
        name=name,
        company_name=company_name,
        ticker=ticker,
        filing_type=filing_type,
        filing_date=filing_date,
        filing_id=filing_id,
        filing_url=filing_url,
    )
    await send_email(
        to=[to_email],
        subject=f"{ticker} filed a {filing_type}",
        html=f"{html}<pre style=\"display:none\">{text}</pre>",
    )


async def send_daily_digest(
    *,
    to_email: str,
    name: str | None,
    items: list[dict],
) -> None:
    html, text = render_daily_digest(name=name, items=items)
    count = len(items)
    subject = f"{count} new filing{'s' if count != 1 else ''} from your watchlist"
    await send_email(
        to=[to_email],
        subject=subject,
        html=f"{html}<pre style=\"display:none\">{text}</pre>",
    )
