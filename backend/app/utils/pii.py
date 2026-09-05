"""Log-safe renderings of personal data.

Application logs (Cloud Logging, Sentry breadcrumbs) are retained and readable by anyone with
project log access, so an e-mail address must never reach them verbatim — the AST gate in
``tests/unit/test_no_raw_email_in_logs.py`` fails any logger call that carries one. Where an id
exists (``user.id``, ``invite.id``, Resend's ``email_id``) log THAT instead; where only the
address is known (inbound Resend events) log ``mask_email(address)``.
"""


def mask_email(email: object) -> str:
    """Reduce an e-mail address to a triage-safe form: ``neil@example.com`` -> ``n***@example.com``.

    Keeps the first character of the local part and the whole domain — enough to tell a
    domain-wide delivery problem (every ``@corp.com`` address bouncing) from a one-off, and to
    eyeball that a webhook concerns the account you expect, without writing the address itself.
    Exact correlation goes through the id logged alongside (Resend ``email_id``, invite id), never
    through this string: it is lossy by design and collides across users, so it is only ever log
    text — never a key, never a hash substitute.

    ``None``/blank -> ``"<none>"``; anything without a ``local@domain`` shape -> ``"***"`` (nothing
    recoverable is kept). Non-string input is rendered with ``str()`` first.
    """
    text = "" if email is None else str(email).strip()
    if not text:
        return "<none>"
    local, sep, domain = text.rpartition("@")
    if not sep or not local or not domain:
        return "***"
    return f"{local[0]}***@{domain}"


def mask_recipients(recipients: object) -> str:
    """``mask_email`` over a Resend-style ``to`` field, which is a list of addresses (or one string).

    ``["a@x.com", "b@y.org"]`` -> ``"a***@x.com, b***@y.org"``; an empty list or ``None`` ->
    ``"<none>"``; a bare string is masked as a single address.
    """
    if isinstance(recipients, (list, tuple, set, frozenset)):
        return ", ".join(mask_email(item) for item in recipients) if recipients else "<none>"
    return mask_email(recipients)
