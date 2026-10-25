"""The account mails sent after a request's response: the password-reset and verification links (F60).

``POST /api/auth/forgot-password`` and ``/resend-verification`` used to look the account up and, for
an eligible one only, issue a token and await the provider's send before answering, so the answer's
timing told a caller whether an address had an account. Now every request that passes the route's
rate limits hands the same work, the address and which mail, to one after-response path and answers
without touching the database (``routers/auth.py::_queue_account_mail``): a durable ``account_mail``
task when ``DURABLE_TASKS_ENABLED`` (Cloud Tasks delivers it to the private worker, as #1122 moved the
other post-response work), else a background task in the API process after the response (local,
development and tests, and a flag-off deployment, which CI keeps on always-allocated CPU). The lookup,
the token and the send happen there, and an address with no eligible account gets nothing: a reset
goes only to an account with a password, a verification only to an unverified account.

A task body holds the address and the mail kind, nothing else (``durable_tasks.AccountMailTask``).
Nothing here logs the address or a token: a failed send logs the exception's class alone, since a
provider's error text can quote the request body and so the token-bearing link, and a failure that
sent nothing raises ``AccountMailNotSent``, whose message names only the failure's class, since a
database error's text quotes its statement's parameters, the address among them. Registration's own
verification mail, sent in its request, shares the send and its log line (``send_verification_link``).
With durable tasks these lines are logged in a task child, so their text reaches Cloud Logging only: a child
reports a failed task to Sentry by its exception's type and stack alone (F50, ``app/utils/telemetry_bootstrap.py``),
and a send that failed after sending is not a failed task (``docs/OPERATIONS.md``, "Account mail (F60)").
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import User
from app.services import auth_account_service, email_service
from app.services.durable_tasks import AccountMail, AccountMailTask, enqueue_task
from app.services.request_work import run_owned_sync
from app.services.resend_service import ResendRetryableError

logger = logging.getLogger(__name__)

# Requests for one address and one mail inside one window name one task, so a double submit, or a
# retry of a handoff Cloud Tasks did not confirm, queues one mail. Short, so a person who asks again a
# few minutes later gets a new link: a failed send is acknowledged, not retried.
DEDUPE_SECONDS = 60


class AccountMailNotSent(RuntimeError):
    """Nothing was sent: the work before the send failed, or the provider refused the send in a way its
    client classes as sent nothing (``ResendRetryableError``). So a retried delivery cannot mail twice. The
    message names only the failure's class, and the original is not chained, so neither the worker's
    traceback nor a log line carries a database error's parameters, the address among them."""


@dataclass(frozen=True)
class _Link:
    """What the send needs, read before the token's commit expires the account's row."""

    user_id: int
    to_email: str
    name: str | None
    raw_token: str


async def queue_account_mail(mail: AccountMail, email: str) -> None:
    """Queue ``mail`` for ``email`` on the durable queue, or raise ``TaskUnavailable`` when Cloud Tasks
    does not confirm it, so the route never claims a mail is on its way that was not queued.

    The body is the address the request schema validated and normalized and the fixed mail vocabulary,
    so one address names one task per mail and window (``DEDUPE_SECONDS``). It carries the caller's
    address, which the durable-task rule otherwise refuses
    (``lessons/arch-caller-input-never-names-a-durable-task.md``), because both branches of each route
    must queue it before any lookup; the routes' per-IP and per-address limits bound how many a caller
    can queue (the gate lists this site in ``EXEMPT``).
    """
    await enqueue_task(
        "account_mail", {"email": email, "mail": mail},
        dedupe_key=f"account_mail:{mail}:{email}", dedupe_seconds=DEDUPE_SECONDS,
    )


def _issue_link(mail: AccountMail, email: str) -> _Link | None:
    """The unit before the send, on a session of its own: the account, whether this mail is for it, and a
    new token, committed. None, with nothing written, for an address with no account, a social-only
    account asking for a reset (it has no password to reset) or a verified one asking for a
    verification. The token replaces the account's earlier one of its kind, so only the newest link
    works. No lock, as the route took none: the write touches only the token's two columns, so two
    issues racing end as two in a row do."""
    with SessionLocal() as db:
        user = auth_account_service.find_user_by_email(db, email)
        if user is None:
            return None
        if mail == "password_reset" and not user.hashed_password:
            return None
        if mail == "verification" and user.email_verified:
            return None
        user_id, to_email, name = user.id, user.email, user.full_name
        if mail == "password_reset":
            raw_token = auth_account_service.issue_password_reset_token(db, user)
        else:
            raw_token = auth_account_service.issue_email_verification_token(db, user)
    return _Link(user_id=user_id, to_email=to_email, name=name, raw_token=raw_token)


async def _send_link(mail: AccountMail, link: _Link, *, retry_unsent: bool = False) -> None:
    """Email the link once. A failure is logged with the exception's class alone and not raised: the
    send was attempted, and a retry could mail twice. With ``retry_unsent`` (the task path), a failure
    ``resend_service`` classes as retryable (no connection, a 429, a 5xx, a concurrent-request conflict,
    or no API key) raises ``AccountMailNotSent`` instead, so Cloud Tasks delivers the mail again."""
    if mail == "password_reset":
        label, url = "Reset", f"{settings.FRONTEND_URL}/reset-password?token={link.raw_token}"
    else:
        label, url = "Verification", f"{settings.FRONTEND_URL}/verify-email?token={link.raw_token}"
    try:
        if mail == "password_reset":
            await email_service.send_password_reset_email(to_email=link.to_email, name=link.name, reset_link=url)
        else:
            await email_service.send_verification_email(
                to_email=link.to_email, name=link.name, verification_link=url,
            )
    except ResendRetryableError as exc:
        if retry_unsent:
            raise AccountMailNotSent(
                f"{label} email not sent to user id={link.user_id}: {exc.__class__.__name__} (nothing sent)"
            ) from None
        _log_failed_send(label, link.user_id, exc, url)
    except Exception as exc:  # noqa: BLE001 - any other outcome of an attempted send is final
        _log_failed_send(label, link.user_id, exc, url)


def _log_failed_send(label: str, user_id: int, exc: Exception, url: str) -> None:
    """The class alone: a provider's error text can quote the request body, the token-bearing link in it.
    Only local development logs the link (log access is account takeover otherwise)."""
    link_note = f"; link: {url}" if settings.ENVIRONMENT == "development" else ""
    logger.error("%s email NOT sent to user id=%s: %s%s", label, user_id, exc.__class__.__name__, link_note)


async def send_account_mail(mail: AccountMail, email: str) -> None:
    """The ``account_mail`` task's handler: look the account up, issue a token and send the link, or do
    nothing for an address with no eligible account.

    Idempotence: Cloud Tasks delivers a task again only when the worker answers other than 2xx or runs
    past its deadline. This handler raises ``AccountMailNotSent``, so the worker answers 503, only when
    nothing was sent: the work before the send failed, or the provider refused it in a way
    ``resend_service`` classes as retryable (``ResendRetryableError``). The retry then sends once; a
    token issued before that failure replaced the account's earlier one and was never mailed, and the
    retry's token replaces it in turn. Any other failed send (rejected, or of unknown outcome) is logged
    and acknowledged, never retried, so no retry follows a send that may have gone. One retryable class
    can still have gone out: a 5xx after the provider queued the mail. Its retry then mails a second
    link, and the second token replaces the first, so only the newer link works. The send is bounded far
    inside the worker's deadline (the Resend client's 10-second timeouts against
    ``TASKS_WORK_TIMEOUT_SECONDS``, at most 480), so the deadline cannot cut a send off into a retry.
    What remains is the transport's own at-least-once delivery: a worker lost between the send and its
    answer, or Cloud Tasks' rare duplicate delivery, can mail twice. The second token then replaces the
    first, as when a person asks twice, so only the newest link works: each kind of token is one column
    (``auth_account_service.issue_password_reset_token`` and ``issue_email_verification_token``), and
    no delivery leaves two working links. A per-task dedupe record would close that too, at the cost of
    the task's name reaching the handler (a Cloud Tasks header the worker does not pass on) and a table
    of sends; the queue already folds one address's requests for one mail within ``DEDUPE_SECONDS``
    into one task.
    """
    try:
        link = await run_owned_sync(_issue_link, mail, email)
    except Exception as exc:
        raise AccountMailNotSent(f"Account mail ({mail}) not sent: {exc.__class__.__name__}") from None
    if link is not None:
        await _send_link(mail, link, retry_unsent=True)


async def run_account_mail_task(payload: dict) -> None:
    """The worker's entry: validate the queued body at the worker boundary, then send. A failure that sent
    nothing propagates, so the worker answers 503 and Cloud Tasks delivers the task again."""
    task = AccountMailTask.model_validate(payload)
    await send_account_mail(task.mail, task.email)


async def send_account_mail_after_response(mail: AccountMail, email: str) -> None:
    """The flag-off path: ``send_account_mail`` as a background task in the API process. Nothing delivers
    it again, so a failure that sent nothing is logged, its class alone, and dropped, as a failed send is."""
    try:
        await send_account_mail(mail, email)
    except AccountMailNotSent as exc:
        logger.error("%s", exc)


async def send_verification_link(db: Session, user: User) -> None:
    """Registration's verification mail, sent in its request: issue a token on the request's session and
    email the link, a failed send logged as the task's is."""
    user_id, to_email, name = user.id, user.email, user.full_name
    raw_token = auth_account_service.issue_email_verification_token(db, user)
    await _send_link("verification", _Link(user_id=user_id, to_email=to_email, name=name, raw_token=raw_token))
