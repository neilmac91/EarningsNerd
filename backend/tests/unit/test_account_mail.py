"""F60: forgot-password and resend-verification take one path in the request, whatever the address
holds, and the mail they hand on is sent after the response, at most once per delivery.

The gate (CLAUDE.md rule 12) is ``test_every_address_takes_one_path_in_the_request``. Before F60 each
route looked the account up and, for an eligible one only, issued a token and awaited the provider's
send before answering, so the answer's timing told a caller whether an address had an account. For an
address with an eligible account, one with an ineligible account and one with none, the gate holds each
route, with durable tasks on and off, to: no SQL statement during the request (so no lookup and no
token), no send, the same handoff with the same shape (the Cloud Task the queue receives, only its
transport faked, or the background task the route schedules), and byte-identical answers.

The handler's cases follow: an eligible account gets one token and one send, any other address nothing,
and a task the queue delivers again cannot mail twice, driven through the real worker route as Cloud
Tasks drives it (deliver until 2xx, at most five attempts, the queue's setting in docs/DEPLOYMENT.md): an
attempted send answers 2xx whatever its outcome, and only a failure that sent nothing (before the send,
or a send the provider's client classes as retryable) answers 503 and is delivered again. A failed send
logs the exception's class, never its message, which can quote the token-bearing request body; no log
line carries the address. The process-wide account-mail cap answers every address alike once spent.
"""
import base64
import hashlib
import json
import logging
import time
import uuid
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import BackgroundTasks, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from main import app
from app.config import settings
from app.database import SessionLocal, engine
from app.models import User
from app.routers import auth as auth_module
from app.routers import tasks as task_worker
from app.services import account_mail_service, auth_account_service, background_task_runner
from app.services import durable_tasks as transport
from app.services.durable_tasks import AccountMailTask
from app.services.rate_limiter import RateLimiter
from app.services.resend_service import ResendAmbiguousError, ResendPermanentError, ResendRetryableError
from tests.support.account_agreement import ACCOUNT_AGREEMENT
from tests.support.summary_stream_harness import reset_rate_limiters

FORGOT_OPAQUE = {"message": "If an account exists for that email, a password reset link is on its way."}
RESEND_OPAQUE = {"message": "If that email has an unverified account, a new verification link is on its way."}

# route -> (its mail, its opaque answer, an eligible account, an existing account it does not mail)
ROUTES = {
    "/api/auth/forgot-password": (
        "password_reset", FORGOT_OPAQUE, dict(password=True, verified=False), dict(password=False, verified=True),
    ),
    "/api/auth/resend-verification": (
        "verification", RESEND_OPAQUE, dict(password=True, verified=False), dict(password=True, verified=True),
    ),
}
# mail -> (the sender's name on the mail fixture, its link keyword, the token column, the token issuer)
MAILS = {
    "password_reset": ("reset", "reset_link", "password_reset_token", "issue_password_reset_token"),
    "verification": ("verification", "verification_link", "email_verification_token", "issue_email_verification_token"),
}


@pytest.fixture(scope="module")
def client():
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _fresh(client, monkeypatch):
    reset_rate_limiters()
    monkeypatch.setattr(settings, "REGISTRATION_MODE", "public")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")  # no development link note unless a test asks


@pytest.fixture
def mail(monkeypatch):
    sent = SimpleNamespace(verification=AsyncMock(), reset=AsyncMock())
    monkeypatch.setattr("app.services.email_service.send_verification_email", sent.verification)
    monkeypatch.setattr("app.services.email_service.send_password_reset_email", sent.reset)
    return sent


@pytest.fixture
def account_work(monkeypatch):
    """Every account lookup and token issue, by function name, wherever it is called from."""
    calls: list[str] = []
    for name in ("find_user_by_email", "issue_password_reset_token", "issue_email_verification_token"):
        def spy(*args, _real=getattr(auth_account_service, name), _name=name):
            calls.append(_name)
            return _real(*args)
        monkeypatch.setattr(auth_account_service, name, spy)
    return calls


@pytest.fixture
def cloud_tasks(monkeypatch):
    """Durable tasks on, with Cloud Tasks faked at its HTTP transport: the queue holds a task by its name and
    answers 409 for a name it holds, as Cloud Tasks does. The bucket clock is pinned."""
    for key, value in {
        "DURABLE_TASKS_ENABLED": True, "TASKS_PROJECT_ID": "test-project",
        "TASKS_LOCATION": "us-west1", "TASKS_QUEUE": "background",
        "TASKS_WORKER_URL": "https://worker-xyz-uw.a.run.app",
        "TASKS_INVOKER_EMAIL": "task-worker@test-project.iam.gserviceaccount.com",
    }.items():
        monkeypatch.setattr(settings, key, value)
    queue: dict[str, dict] = {}
    creates: list[dict] = []

    def respond(request: httpx.Request) -> httpx.Response:
        task = json.loads(request.content)["task"]
        creates.append(task)
        if task["name"] in queue:
            return httpx.Response(409, request=request, json={})
        queue[task["name"]] = task
        return httpx.Response(200, request=request, json={})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(transport, "_access_token", AsyncMock(return_value="metadata-only-token"))
    monkeypatch.setattr(
        transport.httpx, "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    monkeypatch.setattr(
        transport, "time", SimpleNamespace(time=lambda: 1_800_000_000.0, monotonic=time.monotonic),
    )
    return SimpleNamespace(queue=queue, creates=creates)


@pytest.fixture
def worker(monkeypatch):
    """The private worker's route, delivered to as Cloud Tasks delivers: until it answers 2xx, at most five
    attempts. Identity is stubbed; the work runs in process through the runner the worker's child runs, so
    the handler returning or raising is the child exiting 0 or 1."""
    worker_app = FastAPI()
    worker_app.include_router(task_worker.router, prefix="/internal")
    monkeypatch.setattr(task_worker, "verify_task_identity", AsyncMock())
    monkeypatch.setattr(task_worker, "run_background_task", background_task_runner.run_background_task)
    with TestClient(worker_app) as worker_client:
        def deliver(payload: dict) -> list[int]:
            codes = []
            for _ in range(5):
                answer = worker_client.post(
                    "/internal/tasks/execute", json={"kind": "account_mail", "payload": payload},
                    headers={"Authorization": "Bearer signed"},
                )
                codes.append(answer.status_code)
                if answer.is_success:
                    break
            return codes

        yield deliver


@contextmanager
def statements():
    """Every SQL statement the app's engine runs inside the block."""
    seen: list[str] = []

    def count(_conn, _cursor, statement, *_rest):
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", count)
    try:
        yield seen
    finally:
        event.remove(engine, "before_cursor_execute", count)


def _address(tag: str) -> str:
    return f"accountmail_{tag}_{uuid.uuid4().hex[:12]}@example.com"


def _seed(email: str, *, password: bool, verified: bool) -> int:
    with SessionLocal() as db:
        user = User(
            email=email, hashed_password="unused-password-hash" if password else None,  # gitleaks:allow
            full_name="Mail Test", email_verified=verified,
        )
        db.add(user)
        db.commit()
        return user.id


def _user(email: str) -> User:
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one()
        db.expunge(user)
        return user


def _token(link: str) -> str:
    return parse_qs(urlparse(link).query)["token"][0]


# ── the gate: one path in the request ─────────────────────────────────────────

@pytest.mark.requires_db
@pytest.mark.parametrize("durable", [True, False], ids=["durable", "flag-off"])
@pytest.mark.parametrize("path", sorted(ROUTES))
def test_every_address_takes_one_path_in_the_request(
    client, monkeypatch, cloud_tasks, mail, account_work, path, durable,
):
    mail_kind, opaque, eligible, ineligible = ROUTES[path]
    addresses = {"eligible": _address("eligible"), "ineligible": _address("ineligible"), "none": _address("none")}
    _seed(addresses["eligible"], **eligible)
    _seed(addresses["ineligible"], **ineligible)
    monkeypatch.setattr(settings, "DURABLE_TASKS_ENABLED", durable)
    scheduled: list[tuple[str, str]] = []

    async def after_response(mail_kind: str, email: str) -> None:  # stands in for the background task
        scheduled.append((mail_kind, email))

    monkeypatch.setattr(account_mail_service, "send_account_mail_after_response", after_response)
    handed: list = []  # what the route hands to run after its response, and with what
    real_add_task = BackgroundTasks.add_task

    def add_task(self, func, *args, **kwargs):
        handed.append((func, args))
        return real_add_task(self, func, *args, **kwargs)

    monkeypatch.setattr(BackgroundTasks, "add_task", add_task)

    answers, handoffs = {}, {}
    for branch, address in addresses.items():
        created, before, handed_before = len(cloud_tasks.creates), len(scheduled), len(handed)
        with statements() as ran:
            answer = client.post(path, json={"email": address}, headers={"X-Correlation-ID": "f60-gate"})
        assert ran == [], f"{branch}: the request ran SQL, so it looked the account up or wrote to it: {ran}"
        answers[branch] = (answer.status_code, answer.headers.multi_items(), answer.content)
        if durable:
            assert scheduled[before:] == [] and handed[handed_before:] == []
            [task] = cloud_tasks.creates[created:]
            body = json.loads(base64.b64decode(task["httpRequest"]["body"]))
            assert body == {"kind": "account_mail", "payload": {"email": address, "mail": mail_kind}}
            # The name hashes the address; everything else the queue receives is the same for every branch.
            handoffs[branch] = {**task, "name": None, "httpRequest": {**task["httpRequest"], "body": None}}
        else:
            assert cloud_tasks.creates[created:] == []
            assert scheduled[before:] == [(mail_kind, address)]
            # Handed to run after the response, not awaited in the request (where it would time the lookup).
            assert handed[handed_before:] == [(after_response, (mail_kind, address))]
            handoffs[branch] = "send_account_mail_after_response"

    assert answers["eligible"][0] == 200 and json.loads(answers["eligible"][2]) == opaque
    assert answers["ineligible"] == answers["eligible"] and answers["none"] == answers["eligible"]
    assert handoffs["ineligible"] == handoffs["eligible"] and handoffs["none"] == handoffs["eligible"]
    assert account_work == []  # no lookup and no token, in the request or after it here
    assert mail.reset.await_count == 0 and mail.verification.await_count == 0
    # Not vacuous: the counter sees the statements an auth route runs through the app's session.
    with statements() as ran:
        client.post("/api/auth/verify-email", json={"token": "not-a-real-token"})
    assert ran, "the statement counter saw nothing from a route that reads the users table"


@pytest.mark.requires_db
@pytest.mark.parametrize("path", sorted(ROUTES))
def test_what_the_route_queues_the_worker_mails_to_the_eligible_account_alone(
    client, cloud_tasks, worker, mail, path,
):
    """End to end: each queued body, as Cloud Tasks would carry it, is acknowledged by the worker on its first
    delivery, and only the eligible account's mails a link."""
    mail_kind, _, eligible, ineligible = ROUTES[path]
    addresses = [_address("eligible"), _address("ineligible"), _address("none")]
    _seed(addresses[0], **eligible)
    _seed(addresses[1], **ineligible)
    for address in addresses:  # in upper case: the schema's normalization is what the worker looks up
        assert client.post(path, json={"email": address.upper()}).status_code == 200
    bodies = [json.loads(base64.b64decode(task["httpRequest"]["body"])) for task in cloud_tasks.creates]
    assert [body["kind"] for body in bodies] == ["account_mail"] * 3

    assert [worker(body["payload"]) for body in bodies] == [[200]] * 3
    sender_name, link_kwarg, column, _ = MAILS[mail_kind]
    sender = getattr(mail, sender_name)
    sender.assert_awaited_once()
    assert sender.await_args.kwargs["to_email"] == addresses[0]
    token = _token(sender.await_args.kwargs[link_kwarg])
    assert getattr(_user(addresses[0]), column) == hashlib.sha256(token.encode()).hexdigest()


@pytest.mark.requires_db
def test_one_address_queues_one_task_per_mail_and_window(client, cloud_tasks, mail, monkeypatch):
    """A double submit names the task already queued, so it queues no second mail; the other mail is its own,
    and a request in the next window queues a new one (a name kept for good would drop every later ask)."""
    address = _address("twice")
    for path in ("/api/auth/forgot-password", "/api/auth/forgot-password", "/api/auth/resend-verification"):
        assert client.post(path, json={"email": address}).status_code == 200
    assert len(cloud_tasks.creates) == 3
    assert sorted(
        json.loads(base64.b64decode(task["httpRequest"]["body"]))["payload"]["mail"]
        for task in cloud_tasks.queue.values()
    ) == ["password_reset", "verification"]
    monkeypatch.setattr(transport, "time", SimpleNamespace(
        time=lambda: 1_800_000_000.0 + account_mail_service.DEDUPE_SECONDS, monotonic=time.monotonic))
    assert client.post("/api/auth/forgot-password", json={"email": address}).status_code == 200
    assert len(cloud_tasks.queue) == 3


@pytest.mark.requires_db
def test_an_unconfirmed_handoff_answers_503_for_every_address(client, cloud_tasks, monkeypatch, mail, account_work):
    """A handoff Cloud Tasks does not confirm claims no mail is on its way, for any address alike."""
    monkeypatch.setattr(transport, "_access_token", AsyncMock(side_effect=httpx.ConnectError("offline")))
    eligible = _address("eligible")
    _seed(eligible, password=True, verified=False)
    answers = [
        client.post("/api/auth/forgot-password", json={"email": email}, headers={"X-Correlation-ID": "f60-gate"})
        for email in (eligible, _address("none"))
    ]
    assert answers[0].status_code == 503
    assert answers[0].json() == {"detail": "Background work could not be queued. Please retry."}
    assert (answers[1].status_code, answers[1].headers.multi_items(), answers[1].content) == (
        answers[0].status_code, answers[0].headers.multi_items(), answers[0].content,
    )
    assert account_work == [] and mail.reset.await_count == 0


@pytest.mark.requires_db
def test_the_account_mail_cap_answers_every_address_alike_once_spent(client, cloud_tasks, monkeypatch, mail):
    """Both routes draw on one process-wide budget (``ACCOUNT_MAIL_LIMITER``); once it is spent the answer is
    the same 429 for an address with an account and one without, and nothing more is queued."""
    monkeypatch.setattr(auth_module, "ACCOUNT_MAIL_LIMITER", RateLimiter(limit=2, window_seconds=3600))
    eligible = _address("capeligible")
    _seed(eligible, password=True, verified=False)
    assert client.post("/api/auth/forgot-password", json={"email": _address("capa")}).status_code == 200
    assert client.post("/api/auth/resend-verification", json={"email": _address("capb")}).status_code == 200
    answers = [client.post("/api/auth/forgot-password", json={"email": email}) for email in (eligible, _address("capnone"))]
    assert [answer.status_code for answer in answers] == [429, 429]
    assert answers[0].json() == answers[1].json() == {"detail": "Too many requests right now. Try again later."}
    assert len(cloud_tasks.creates) == 2


@pytest.mark.requires_db
def test_a_request_its_own_limits_refuse_spends_none_of_the_cap(client, cloud_tasks, monkeypatch, mail):
    """The cap is taken after the per-address and per-IP limits, so requests those refuse leave it whole."""
    monkeypatch.setattr(auth_module, "ACCOUNT_MAIL_LIMITER", RateLimiter(limit=4, window_seconds=3600))
    address = _address("capself")
    codes = [client.post("/api/auth/forgot-password", json={"email": address}).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]  # the fourth is the per-address limit's, 3 an hour
    assert client.post("/api/auth/forgot-password", json={"email": _address("capother")}).status_code == 200


# ── the handler ───────────────────────────────────────────────────────────────

@pytest.mark.requires_db
@pytest.mark.asyncio
@pytest.mark.parametrize("mail_kind", sorted(MAILS))
async def test_an_eligible_account_gets_one_token_and_one_send(mail, account_work, mail_kind):
    sender_name, link_kwarg, column, issuer = MAILS[mail_kind]
    address = _address("eligible")
    _seed(address, password=True, verified=False)

    await account_mail_service.send_account_mail(mail_kind, address)

    sender = getattr(mail, sender_name)
    sender.assert_awaited_once()
    assert sender.await_args.kwargs["to_email"] == address
    token = _token(sender.await_args.kwargs[link_kwarg])
    assert getattr(_user(address), column) == hashlib.sha256(token.encode()).hexdigest()  # its hash alone
    assert account_work == ["find_user_by_email", issuer]


@pytest.mark.requires_db
@pytest.mark.asyncio
@pytest.mark.parametrize("mail_kind, account", [
    ("password_reset", None),
    ("password_reset", dict(password=False, verified=True)),  # social-only: no password to reset
    ("verification", None),
    ("verification", dict(password=True, verified=True)),  # already verified
], ids=["reset-no-account", "reset-social-only", "verification-no-account", "verification-verified"])
async def test_an_address_with_no_eligible_account_gets_nothing(mail, account_work, mail_kind, account):
    address = _address("ineligible")
    if account is not None:
        _seed(address, **account)

    await account_mail_service.send_account_mail(mail_kind, address)

    assert account_work == ["find_user_by_email"]
    assert mail.reset.await_count == 0 and mail.verification.await_count == 0
    if account is not None:
        user = _user(address)
        assert user.password_reset_token is None and user.email_verification_token is None


@pytest.mark.requires_db
@pytest.mark.parametrize("mail_kind", sorted(MAILS))
@pytest.mark.parametrize("failure", [
    ResendAmbiguousError("Resend outcome unknown: ReadTimeout"),
    ResendPermanentError("Resend API error (422)"),
    RuntimeError("an unclassified failure"),
], ids=lambda failure: type(failure).__name__)
def test_an_attempted_send_is_acknowledged_and_never_delivered_again(worker, mail, account_work, mail_kind, failure):
    """A send that may have gone, or that the provider rejected for good, is acknowledged: the worker answers
    2xx, so Cloud Tasks never delivers the task again."""
    sender_name, _, _, issuer = MAILS[mail_kind]
    address = _address("attempted")
    _seed(address, password=True, verified=False)
    getattr(mail, sender_name).side_effect = failure

    assert worker({"email": address, "mail": mail_kind}) == [200]
    assert getattr(mail, sender_name).await_count == 1
    assert account_work == ["find_user_by_email", issuer]


@pytest.mark.requires_db
def test_a_failure_before_the_send_is_delivered_again_and_mails_once(worker, mail, monkeypatch, caplog):
    """The work before the send fails, the worker answers 503, the queue delivers the task again, and the
    second delivery mails the one link that works. The failure's log lines carry no address: a database
    error's text quotes its statement's parameters."""
    address = _address("retried")
    _seed(address, password=True, verified=False)
    issue = auth_account_service.issue_password_reset_token
    failures = [OperationalError("UPDATE users SET password_reset_token=?", {"email": address}, Exception("locked"))]

    def flaky(db, user):
        if failures:
            raise failures.pop()
        return issue(db, user)

    monkeypatch.setattr(auth_account_service, "issue_password_reset_token", flaky)
    with caplog.at_level(logging.INFO):
        assert worker({"email": address, "mail": "password_reset"}) == [503, 200]

    mail.reset.assert_awaited_once()
    token = _token(mail.reset.await_args.kwargs["reset_link"])
    assert _user(address).password_reset_token == hashlib.sha256(token.encode()).hexdigest()
    assert "Account mail (password_reset) not sent: OperationalError" in caplog.text
    assert address not in caplog.text and token not in caplog.text


@pytest.mark.requires_db
@pytest.mark.parametrize("mail_kind", sorted(MAILS))
def test_a_send_that_sent_nothing_is_delivered_again_and_mails_one_working_link(worker, mail, mail_kind, caplog):
    """The provider refuses the send in a way its client classes as sent nothing (a 429, a 5xx, no connection,
    no key): the worker answers 503, the queue delivers the task again, and the second delivery mails a new
    link whose token replaced the first."""
    sender_name, link_kwarg, column, _ = MAILS[mail_kind]
    sender = getattr(mail, sender_name)
    sender.side_effect = [ResendRetryableError("Resend API error (429): rate limited"), None]
    address = _address("unsent")
    _seed(address, password=True, verified=False)

    with caplog.at_level(logging.INFO):
        assert worker({"email": address, "mail": mail_kind}) == [503, 200]

    assert sender.await_count == 2
    first, second = (_token(call.kwargs[link_kwarg]) for call in sender.await_args_list)
    assert first != second
    assert getattr(_user(address), column) == hashlib.sha256(second.encode()).hexdigest()
    assert "ResendRetryableError (nothing sent)" in caplog.text
    assert address not in caplog.text and first not in caplog.text and "rate limited" not in caplog.text


@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_off_the_queue_a_send_that_sent_nothing_is_logged_once_and_dropped(monkeypatch, caplog, mail):
    """The flag-off path and registration's in-request send have nothing to deliver them again: the refusal is
    logged by its class and the request goes on."""
    mail.reset.side_effect = ResendRetryableError("Resend API error (503)")
    address = _address("unsentoff")
    user_id = _seed(address, password=True, verified=False)
    with caplog.at_level(logging.INFO):
        await account_mail_service.send_account_mail_after_response("password_reset", address)
    assert [r.getMessage() for r in caplog.records if "not sent" in r.getMessage()] == [
        f"Reset email not sent to user id={user_id}: ResendRetryableError (nothing sent)"]
    assert mail.reset.await_count == 1 and address not in caplog.text


@pytest.mark.requires_db
def test_a_body_outside_the_task_schema_is_refused_at_the_worker_and_mails_nothing(worker, mail):
    """The worker validates the queued body where it enters (rule 9): another mail kind or another key is refused
    and nothing is looked up or sent; the refusal never quotes the address."""
    address = _address("refused")
    _seed(address, password=True, verified=False)
    for payload in ({"email": address, "mail": "admin"}, {"email": address, "mail": "password_reset", "to": "x"}):
        assert worker(payload) == [422] * 5
    assert mail.reset.await_count == 0 and mail.verification.await_count == 0
    with pytest.raises(ValidationError) as refused:
        AccountMailTask.model_validate({"email": address, "mail": "admin"})
    assert address not in str(refused.value)


@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_the_flag_off_path_logs_a_failure_before_the_send_without_the_address(monkeypatch, caplog, mail):
    """In the API process nothing delivers the work again: the failure is logged, its class alone, and dropped."""
    address = _address("flagoff")

    def unreachable(_db, email):
        raise OperationalError("SELECT users.id FROM users WHERE users.email = ?", {"email_1": email}, Exception("down"))

    monkeypatch.setattr(auth_account_service, "find_user_by_email", unreachable)
    with caplog.at_level(logging.INFO):
        await account_mail_service.send_account_mail_after_response("verification", address)
    assert [r.getMessage() for r in caplog.records if "not sent" in r.getMessage()] == [
        "Account mail (verification) not sent: OperationalError"]
    assert address not in caplog.text
    assert mail.verification.await_count == 0


# ── the send's log line ───────────────────────────────────────────────────────

def _provider_error_quoting_the_link(**kwargs):
    """A provider rejection whose text quotes the request body, the token-bearing link in it."""
    link = kwargs.get("reset_link") or kwargs.get("verification_link")
    raise ResendPermanentError(f'Resend API error (422): {{"html": "<a href=\\"{link}\\">"}}')


def _send_failure_records(caplog) -> list[logging.LogRecord]:
    return [record for record in caplog.records if "email NOT sent" in record.getMessage()]


@pytest.mark.requires_db
@pytest.mark.asyncio
@pytest.mark.parametrize("environment", ["production", "development"])
@pytest.mark.parametrize("mail_kind, label", [("password_reset", "Reset"), ("verification", "Verification")])
async def test_a_failed_send_logs_the_exception_class_not_its_message(
    monkeypatch, caplog, mail, mail_kind, label, environment,
):
    """Rule 12 for item 4 of F60: the line names the class; only local development adds the link."""
    monkeypatch.setattr(settings, "ENVIRONMENT", environment)
    sender_name, link_kwarg, _, _ = MAILS[mail_kind]
    sender = getattr(mail, sender_name)
    sender.side_effect = _provider_error_quoting_the_link
    address = _address("logline")
    user_id = _seed(address, password=True, verified=False)

    with caplog.at_level(logging.INFO):
        await account_mail_service.send_account_mail(mail_kind, address)

    link = sender.await_args.kwargs[link_kwarg]
    [record] = _send_failure_records(caplog)
    note = f"; link: {link}" if environment == "development" else ""
    assert record.levelno == logging.ERROR
    assert record.getMessage() == f"{label} email NOT sent to user id={user_id}: ResendPermanentError{note}"
    assert "Resend API error" not in caplog.text and address not in caplog.text
    if environment == "production":
        assert _token(link) not in caplog.text


@pytest.mark.requires_db
def test_registrations_verification_send_logs_the_exception_class_not_its_message(client, mail, caplog, collection_ready):
    """Registration sends its verification link in its request, through the same send and the same line."""
    mail.verification.side_effect = _provider_error_quoting_the_link
    address = _address("register")
    with caplog.at_level(logging.INFO):
        answer = client.post("/api/auth/register", json={**ACCOUNT_AGREEMENT, "email": address, "password": "Sup3rSecretPassw0rd"})  # gitleaks:allow
    assert answer.status_code == 200, answer.text
    link = mail.verification.await_args.kwargs["verification_link"]
    [record] = _send_failure_records(caplog)
    assert record.getMessage() == f"Verification email NOT sent to user id={_user(address).id}: ResendPermanentError"
    assert "Resend API error" not in caplog.text and _token(link) not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("helper, sender_name, args", [
    ("_send_account_exists_email_safe", "send_account_exists_email", ()),
    ("_send_oauth_linked_email_safe", "send_oauth_linked_email", ("google",)),
])
async def test_the_other_account_mails_log_the_exception_class_not_its_message(
    monkeypatch, caplog, helper, sender_name, args,
):
    """The account-exists and OAuth-linked notices log a failed send as the links' mails do: a provider's text
    can quote the request, the recipient's address among it."""
    address = _address("notice")
    monkeypatch.setattr(
        f"app.services.email_service.{sender_name}",
        AsyncMock(side_effect=ResendPermanentError(f"Resend API error (422): to {address}")),
    )
    with caplog.at_level(logging.INFO):
        await getattr(auth_module, helper)(SimpleNamespace(email=address, full_name="Mail Test"), *args)
    [record] = [r for r in caplog.records if "not sent" in r.getMessage()]
    assert record.getMessage().endswith(": ResendPermanentError")
    assert address not in caplog.text and "Resend API error" not in caplog.text
