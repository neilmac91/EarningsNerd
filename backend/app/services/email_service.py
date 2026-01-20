from __future__ import annotations

from app.services.resend_service import send_email


def _wrap_html(body: str) -> str:
    return f"""
    <html>
      <body style="margin:0;padding:0;background:#0b0f14;font-family:Inter,Arial,sans-serif;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0b0f14;padding:32px 12px;">
          <tr>
            <td align="center">
              <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;background:#111827;border-radius:16px;padding:32px;color:#f9fafb;">
                <tr>
                  <td style="font-size:22px;font-weight:700;color:#a7f3d0;">EarningsNerd</td>
                </tr>
                <tr>
                  <td style="padding-top:16px;font-size:16px;line-height:1.6;color:#e5e7eb;">
                    {body}
                  </td>
                </tr>
                <tr>
                  <td style="padding-top:32px;font-size:12px;color:#9ca3af;">
                    You are receiving this email because you joined the EarningsNerd waitlist.
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
      <a href="{referral_link}" style="color:#34d399;">{referral_link}</a>
    </p>
    <p style="margin:0 0 24px;">
      Please verify your email to secure your place:
      <a href="{verification_link}" style="color:#a7f3d0;font-weight:600;">Verify email</a>
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
      <a href="{referral_link}" style="color:#34d399;">{referral_link}</a>
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
