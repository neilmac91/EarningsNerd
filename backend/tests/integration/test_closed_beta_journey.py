"""Closed-beta acceptance journey, end to end through the real API, on synthetic accounts.

Each step below is pinned on its own somewhere in the suite; this module chains them on the accounts a closed
beta creates, so a change that breaks the composition fails here while every unit test stays green. An
administrator mints an address-bound invitation (manual link, as invitation mail is held); the invitee registers
with it and their own current agreement, or through Google; the verification mail's link verifies them; they sign
in. Pro is granted through one seam (``_grant_pro``), and every capability the pricing page sells as Pro answers
the Pro tester through its own route and stays shut for a Free control tester, for each way an account can hold
Pro. A grant and its revocation, and Stripe events for other accounts, reach no account but the one they name.
Text and screenshot feedback reach the operator's triage and nobody else; the export carries what the tester gave;
deletion ends the session and the cleanup job removes the screenshot object. Sign-out, reset and sign-in again
work, and each rollback lever stops one thing while keeping sign-in, Pro rights and data rights. The operator
runbook (docs/ops/closed-beta-acceptance.md) names these tests for each check.

Boundaries, so a pass is never read as more than it is: the app's SQLite test database, not PostgreSQL; mail
captured where ``app.services.email_service`` sends it, so no provider delivery or inbox receipt; SEC, model,
Google, Stripe, object storage and image processing faked at the seams their own suites fake; every persona a
separate ``TestClient`` (its own cookie jar, as one browser each). A pass proves the API composes for a beta
account. It is not evidence of production delivery, configuration or capacity.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import fields
from datetime import timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm.attributes import set_committed_value
from stripe import StripeObject

from app.config import settings
from app.database import SessionLocal
from app.models import (AccountAgreement, Company, Filing, FilingContentCache, InviteCode, Subscription, Summary, User,
                        UserUsage)
from app.routers import auth as auth_module
from app.routers import feedback as feedback_router
from app.routers import summaries as summaries_router
from app.services.entitlements import _FREE, _PRO, Entitlements
from app.services.feedback_image_service import NormalizedFeedbackImage
from app.services.feedback_media_cleanup_service import run_feedback_media_cleanup
from app.services.password_utils import get_password_hash
from app.services.subscription_service import get_current_month
from app.utils.datetimes import utcnow
from main import app
from tests.support.account_agreement import ACCOUNT_AGREEMENT
from tests.support.summary_stream_harness import reset_inflight, reset_rate_limiters, seed_company_filing, stream_boundaries

pytestmark = [pytest.mark.integration, pytest.mark.requires_db, pytest.mark.usefixtures("collection_ready")]

PASSWORD = "Sup3rSecretPassw0rd"  # test fixture, not a credential  # gitleaks:allow
INVITE_REFUSED = {"detail": "A valid invite is required to register."}


@pytest.fixture(scope="module")
def started():
    """Run the app's lifespan once for the module; each persona's browser shares the started app."""
    with TestClient(app, base_url="https://testserver") as client:
        yield client


@pytest.fixture
def browsers(started):
    """A fresh browser (cookie jar) per persona, closed when the test ends."""
    opened: list[TestClient] = []

    def open_browser() -> TestClient:
        browser = TestClient(app, base_url="https://testserver")
        opened.append(browser)
        return browser

    yield open_browser
    for browser in opened:
        browser.close()


@pytest.fixture(autouse=True)
def _invite_only(monkeypatch):
    reset_rate_limiters()
    monkeypatch.setattr(settings, "REGISTRATION_MODE", "invite_only")
    monkeypatch.setattr(settings, "REVERSE_TRIAL_ENABLED", False)


@pytest.fixture(autouse=True)
def _postgres_shaped_expiries():
    """Load the token-expiry columns tz-aware, as PostgreSQL returns them (SQLite drops the zone), as the
    auth suite does (tests/unit/test_auth_token_flows.py)."""
    def _aware(target, *_args):
        for name in ("email_verification_expires", "password_reset_expires"):
            value = target.__dict__.get(name)
            if value is not None and value.tzinfo is None:
                set_committed_value(target, name, value.replace(tzinfo=timezone.utc))

    event.listen(User, "load", _aware)
    event.listen(User, "refresh", _aware)
    yield
    event.remove(User, "load", _aware)
    event.remove(User, "refresh", _aware)


@pytest.fixture
def outbox(monkeypatch):
    """Account mail, captured where the services send it (they look the senders up at call time)."""
    sent = SimpleNamespace(verification=AsyncMock(), reset=AsyncMock(), exists=AsyncMock())
    monkeypatch.setattr("app.services.email_service.send_verification_email", sent.verification)
    monkeypatch.setattr("app.services.email_service.send_password_reset_email", sent.reset)
    monkeypatch.setattr("app.services.email_service.send_account_exists_email", sent.exists)
    return sent


# ── personas and steps ────────────────────────────────────────────────────────

def _address(role: str) -> str:
    return f"beta-{role}-{uuid.uuid4().hex[:12]}@example.com"


def _seed_admin() -> str:
    """The operator's account. Administrators are never created through the API (it refuses direct creation)."""
    email = _address("admin")
    with SessionLocal() as db:
        db.add(User(email=email, hashed_password=get_password_hash(PASSWORD), is_admin=True,
                    is_active=True, email_verified=True))
        db.commit()
    return email


def _sign_in(browser: TestClient, email: str, password: str = PASSWORD) -> dict:
    resp = browser.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    me = browser.get("/api/auth/me")
    assert me.status_code == 200, me.text
    assert me.json()["email"] == email
    return me.json()


def _mint_invite(admin: TestClient, email: str | None, **fields) -> tuple[int, str]:
    """Mint an invitation the way the operator does while invitation mail is held: no send, link handed over."""
    resp = admin.post("/api/admin/invites", json={"email": email, "cohort": "beta-acceptance", **fields})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["emailed"] is False
    link = urlparse(body["invite_link"])
    assert link.path == "/register"
    return body["id"], parse_qs(link.query)["invite"][0]


def _register(browser: TestClient, email: str, token: str | None, agreement: dict = ACCOUNT_AGREEMENT):
    return browser.post("/api/auth/register",
                        json={**agreement, "email": email, "password": PASSWORD, "invite_code": token})


def _verification_token(outbox, email: str) -> str:
    calls = [call for call in outbox.verification.call_args_list if call.kwargs["to_email"] == email]
    assert len(calls) == 1, f"expected one verification mail to {email}, got {len(calls)}"
    return parse_qs(urlparse(calls[0].kwargs["verification_link"]).query)["token"][0]


def _onboard(browsers, admin: TestClient, outbox, role: str) -> tuple[TestClient, dict]:
    """Invite → register with the tester's own agreement → verify → sign in. Returns (browser, /me)."""
    email = _address(role)
    _invite_id, token = _mint_invite(admin, email)
    tester = browsers()
    resp = _register(tester, email, token)
    assert resp.status_code == 200, resp.text
    verified = tester.post("/api/auth/verify-email", json={"token": _verification_token(outbox, email)})
    assert verified.status_code == 200, verified.text
    return tester, _sign_in(tester, email)


def _invite_row(invite_id: int) -> InviteCode:
    with SessionLocal() as db:
        invite = db.get(InviteCode, invite_id)
        db.expunge(invite)
        return invite


def _account(email: str) -> User | None:
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one_or_none()
        if user is not None:
            db.expunge(user)
        return user


# ── onboarding ────────────────────────────────────────────────────────────────

def test_an_invited_tester_registers_verifies_and_signs_in(browsers, outbox):
    admin = browsers()
    _sign_in(admin, _seed_admin())
    email = _address("tester")
    invite_id, token = _mint_invite(admin, email)

    tester = browsers()
    resp = _register(tester, email, token)
    assert resp.status_code == 200, resp.text
    assert "earningsnerd_access_token" not in tester.cookies  # registration never signs anyone in

    account = _account(email)
    assert account is not None and account.is_beta is True and account.email_verified is False
    invite = _invite_row(invite_id)
    assert invite.used_at is not None and invite.user_id == account.id and invite.cohort == "beta-acceptance"
    with SessionLocal() as db:
        agreement = db.query(AccountAgreement).filter(AccountAgreement.user_id == account.id).one()
        assert (agreement.terms_version, agreement.eligibility_version) == (
            ACCOUNT_AGREEMENT["terms_version"], ACCOUNT_AGREEMENT["eligibility_version"])

    verified = tester.post("/api/auth/verify-email", json={"token": _verification_token(outbox, email)})
    assert verified.status_code == 200, verified.text
    me = _sign_in(tester, email)
    assert me["is_beta"] is True and me["email_verified"] is True and me["is_admin"] is False

    # The redeemed link is spent: the same token cannot open a second account.
    again = _register(browsers(), _address("second"), token)
    assert again.status_code == 403 and again.json() == INVITE_REFUSED


def test_every_unusable_invitation_gets_one_answer_and_creates_nothing(browsers, outbox):
    admin = browsers()
    _sign_in(admin, _seed_admin())

    bound_to, other = _address("bound"), _address("other")
    _id, wrong_address_token = _mint_invite(admin, bound_to)
    revoked_id, revoked_token = _mint_invite(admin, _address("revoked"))
    assert admin.post(f"/api/admin/invites/{revoked_id}/revoke").status_code == 200
    expired_id, expired_token = _mint_invite(admin, _address("expired"))
    with SessionLocal() as db:
        db.get(InviteCode, expired_id).expires_at = utcnow() - timedelta(minutes=1)
        db.commit()

    cases = {
        "missing": (_address("missing"), None),
        "unknown": (_address("unknown"), "not-a-minted-token"),
        "another address": (other, wrong_address_token),
        "revoked": (_address("revoked-try"), revoked_token),
        "expired": (_address("expired-try"), expired_token),
    }
    for name, (email, token) in cases.items():
        reset_rate_limiters()  # every browser here shares the test client's address; throttling is pinned elsewhere
        resp = _register(browsers(), email, token)
        assert (resp.status_code, resp.json()) == (403, INVITE_REFUSED), name
        assert _account(email) is None, name
    assert outbox.verification.call_count == 0
    # The address-bound invitation is still there for the address it names.
    reset_rate_limiters()
    assert _register(browsers(), bound_to, wrong_address_token).status_code == 200


# ── complimentary Pro: the grant seam, the capability matrix and its gate ─────

# How an account can hold Pro without paying, as entitlements.get_plan resolves it: the ``is_pro`` mirror of an
# account with no Subscription row, or a granting row kept in lockstep with the mirror, as subscription_sync writes
# them. The complimentary grant is not built yet; whichever shape it takes, the matrix below already runs on it.
PRO_HOLDERS = ("mirror", "active-row", "future-trial-row")


def _grant_pro(email: str, holder: str = "mirror") -> None:
    """The one seam that makes a beta account Pro, so the matrix and the isolation check never depend on how.

    No operation grants Pro without payment yet, and checkout is closed in code. When the complimentary grant
    lands, this body (and ``_revoke_pro``'s) calls it, and every test here must pass unchanged.
    """
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one()
        user.is_pro = True
        if holder != "mirror":
            trial_end = utcnow() + timedelta(days=7) if holder == "future-trial-row" else None
            db.add(Subscription(user_id=user.id, plan="pro", status="trialing" if trial_end else "active",
                                trial_end=trial_end))
        db.commit()


def _revoke_pro(email: str) -> None:
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one()
        user.is_pro = False
        db.query(Subscription).filter(Subscription.user_id == user.id).update({"status": "canceled"})
        db.commit()


def _account_state(email: str) -> tuple:
    """What a grant or a billing event could change on an account: its plan inputs and its other flags."""
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one()
        row = db.query(Subscription).filter(Subscription.user_id == user.id).one_or_none()
        return (user.is_pro, user.is_beta, user.is_admin, user.is_active, user.email_verified,
                user.stripe_customer_id, user.copilot_free_taste_used,
                None if row is None else (row.plan, row.status, row.stripe_customer_id, row.stripe_subscription_id))


def _plan_views(browser: TestClient) -> tuple[bool, bool]:
    """(what /api/auth/me says, what the usage endpoint's entitlement resolution says) about Pro."""
    me = browser.get("/api/auth/me")
    usage = browser.get("/api/subscriptions/usage")
    assert me.status_code == usage.status_code == 200, (me.text, usage.text)
    return me.json()["is_pro"], usage.json()["is_pro"]


def _seed_company(ticker_prefix: str = "BT") -> tuple[int, str]:
    with SessionLocal() as db:
        suffix = uuid.uuid4().hex[:8]
        company = Company(cik=f"9{int(suffix, 16) % 10**9:09d}", ticker=f"{ticker_prefix}{suffix[:4].upper()}",
                          name=f"Beta Acceptance {suffix}")
        db.add(company)
        db.commit()
        return company.id, company.ticker


def _seed_readable_filing() -> int:
    """A filing with a cached excerpt, so the Copilot route can load it (as tests/unit/test_expired_trial_gating.py)."""
    company_id, _ticker = _seed_company()
    with SessionLocal() as db:
        suffix = uuid.uuid4().hex[:10]
        filing = Filing(company_id=company_id, accession_number=f"acc-{suffix}", filing_type="10-K",
                        filing_date=utcnow() - timedelta(days=30),
                        document_url=f"https://sec.example/{suffix}/d.htm", sec_url=f"https://sec.example/{suffix}/")
        db.add(filing)
        db.commit()
        db.add(FilingContentCache(filing_id=filing.id, critical_excerpt="Item 7. Revenue increased 12%."))
        db.commit()
        return filing.id


def _use_this_month(email: str, *, summaries: int = 0) -> None:
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one()
        db.add(UserUsage(user_id=user.id, month=get_current_month(), summary_count=summaries))
        db.commit()


def _spend_copilot_taste(email: str) -> None:
    with SessionLocal() as db:
        db.query(User).filter(User.email == email).one().copilot_free_taste_used = FREE_TASTE
        db.commit()


async def _fake_answer(*, filing, question, history=None):
    yield {"type": "complete", "answer": "ok", "citations": [], "grounded": 0, "kind": "answer"}


def _generate(browser: TestClient, filing_id: int) -> str:
    resp = browser.post(f"/api/summaries/filing/{filing_id}/generate-stream")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")
    return resp.text


def _refused_as_pro_only(resp) -> bool:
    return resp.status_code == 403 and "Upgrade to Pro" in resp.json()["detail"]


FREE_TASTE = _FREE.copilot_free_taste

# Every entitlement in which Pro differs from Free, and how this module accepts it for a beta tester: the
# test that drives it through its route, or why no test should (not on the pricing page, nothing enforces
# it, or a dormant flag that stays off absent its own acceptance). The gate below holds this table to
# app/services/entitlements.py, so a new Pro capability cannot ship without a beta acceptance answer.
CAPABILITY_MATRIX = {
    "monthly_summary_limit": "test_pro_capabilities_answer_a_pro_tester_and_stay_shut_for_free",
    "can_export": "test_pro_capabilities_answer_a_pro_tester_and_stay_shut_for_free",
    "copilot": "test_pro_capabilities_answer_a_pro_tester_and_stay_shut_for_free",
    "copilot_free_taste": "test_pro_capabilities_answer_a_pro_tester_and_stay_shut_for_free",
    "can_analyze_trends": "test_pro_capabilities_answer_a_pro_tester_and_stay_shut_for_free",
    "earnings_alert_limit": "test_pro_capabilities_answer_a_pro_tester_and_stay_shut_for_free",
    "realtime_alerts": "test_pro_capabilities_answer_a_pro_tester_and_stay_shut_for_free",
    "eightk_coverage": "test_pro_capabilities_answer_a_pro_tester_and_stay_shut_for_free",
    "plan": "test_a_grant_and_its_revocation_reach_only_the_account_they_name",
    "history_retention_days": "not enforced and not advertised (entitlements.py: forward-looking)",
    "priority_model": "not enforced and not advertised (entitlements.py: forward-looking)",
    "section_changes": "dormant: ENABLE_SECTION_CHANGES is off and the pricing page lists the report for both plans",
    "section_changes_items": "dormant: ENABLE_SECTION_CHANGES is off and the pricing page lists the report for both plans",
}


def test_every_pro_entitlement_has_a_beta_acceptance_answer():
    differing = {f.name for f in fields(Entitlements) if getattr(_PRO, f.name) != getattr(_FREE, f.name)}
    assert set(CAPABILITY_MATRIX) == differing, (
        f"unanswered: {sorted(differing - set(CAPABILITY_MATRIX))}; stale: {sorted(set(CAPABILITY_MATRIX) - differing)}")
    for name, answer in CAPABILITY_MATRIX.items():
        if answer.startswith("test_"):
            assert callable(globals().get(answer)), f"{name} names {answer}, which this module does not define"


@pytest.mark.parametrize("holder", PRO_HOLDERS)
def test_pro_capabilities_answer_a_pro_tester_and_stay_shut_for_free(browsers, outbox, monkeypatch, holder):
    admin = browsers()
    _sign_in(admin, _seed_admin())
    pro, pro_me = _onboard(browsers, admin, outbox, "pro")
    free, free_me = _onboard(browsers, admin, outbox, "free")
    _grant_pro(pro_me["email"], holder)

    # One plan, wherever the account reads it: the badge's source (/me) and the enforced plan (usage) agree.
    assert _plan_views(pro) == (True, True)
    assert _plan_views(free) == (False, False)

    # Summaries: Free stops at its monthly allowance; Pro generates past it.
    for email in (pro_me["email"], free_me["email"]):
        _use_this_month(email, summaries=_FREE.monthly_summary_limit)
    reset_inflight()
    pro_filing, free_filing = seed_company_filing(), seed_company_filing()
    with stream_boundaries(patch_usage_limit=False):
        pro_run = _generate(pro, pro_filing)
        free_run = _generate(free, free_filing)
    assert '"type": "complete"' in pro_run and "Upgrade to Pro" not in pro_run
    assert '"type": "error"' in free_run and "Upgrade to Pro" in free_run and '"type": "complete"' not in free_run
    with SessionLocal() as db:
        assert db.query(Summary).filter(Summary.filing_id == pro_filing).count() == 1
        assert db.query(Summary).filter(Summary.filing_id == free_filing).count() == 0

    # The generated summary is then a cached read for anyone, and Pro's exports of it work; Free's are refused.
    cached = free.get(f"/api/summaries/filing/{pro_filing}")
    assert cached.status_code == 200, cached.text
    for kind, media_type in (("csv", "text/csv"), ("pdf", "application/pdf")):
        ok = pro.get(f"/api/summaries/filing/{pro_filing}/export/{kind}")
        assert ok.status_code == 200 and ok.headers["content-type"].startswith(media_type), (kind, ok.text[:200])
        assert ok.content, kind
        refused = free.get(f"/api/summaries/filing/{pro_filing}/export/{kind}")
        assert refused.status_code == 403 and refused.json()["code"] == "plan_required", (kind, refused.text)

    # Ask this Filing beyond the free taste: Pro answers, Free is told the taste is spent.
    monkeypatch.setattr(summaries_router, "answer_filing_question", _fake_answer)
    readable = _seed_readable_filing()
    for email in (pro_me["email"], free_me["email"]):
        _spend_copilot_taste(email)
    answered = pro.post(f"/api/summaries/filing/{readable}/ask-stream", json={"question": "What drove revenue?"})
    assert answered.status_code == 200 and '"type": "complete"' in answered.text, answered.text
    assert _refused_as_pro_only(free.post(f"/api/summaries/filing/{readable}/ask-stream",
                                          json={"question": "What drove revenue?"}))

    # Multi-Period Analysis and its Excel export: the Pro gate admits the Pro tester, refuses Free.
    _company_id, ticker = _seed_company()
    window = {"mode": "annual", "start_period": "FY2016", "end_period": "FY2025"}
    for path in (f"/api/analysis/{ticker}/dataset", f"/api/analysis/{ticker}/export/xlsx"):
        assert not _refused_as_pro_only(pro.post(path, json=window)), path
        assert _refused_as_pro_only(free.post(path, json=window)), path

    # Alerts: Free's earnings-day alerts stop at its cap and Pro's do not; hourly filing and 8-K alerts stay
    # on for Pro and are switched off for Free.
    tickers = [_seed_company("AL")[1] for _ in range(_FREE.earnings_alert_limit + 1)]
    for browser, plan in ((pro, "pro"), (free, "free")):
        answers = [browser.post(f"/api/watchlist/{ticker}/earnings-alert") for ticker in tickers]
        assert [a.status_code for a in answers[:-1]] == [200] * _FREE.earnings_alert_limit, plan
        last = answers[-1]
        if plan == "pro":
            assert last.status_code == 200, last.text
        else:
            assert last.status_code == 403 and last.json()["code"] == "earnings_alert_limit", last.text
        prefs = browser.put("/api/users/me/notification-preferences", json={"realtime": True, "notify_8k": True})
        assert prefs.status_code == 200, prefs.text
        expected = plan == "pro"
        body = prefs.json()
        assert (body["realtime"], body["notify_8k"], body["realtime_available"], body["eightk_available"]) == (
            expected, expected, expected, expected), (plan, body)

    # Complimentary access never opens checkout: it stays closed in code for every beta account.
    for browser in (pro, free):
        closed = browser.post("/api/subscriptions/create-checkout-session", params={"price_id": "price_beta_probe"})
        assert closed.status_code == 503 and "not available" in closed.json()["detail"], closed.text


def test_a_grant_and_its_revocation_reach_only_the_account_they_name(browsers, outbox):
    admin = browsers()
    _sign_in(admin, _seed_admin())
    target, target_me = _onboard(browsers, admin, outbox, "target")
    bystander, bystander_me = _onboard(browsers, admin, outbox, "bystander")
    holder, holder_me = _onboard(browsers, admin, outbox, "holder")
    _grant_pro(holder_me["email"])

    untouched = {email: _account_state(email) for email in (bystander_me["email"], holder_me["email"])}

    _grant_pro(target_me["email"])
    assert _plan_views(target) == (True, True)
    assert _plan_views(bystander) == (False, False)
    assert _plan_views(holder) == (True, True)
    assert {email: _account_state(email) for email in untouched} == untouched

    _revoke_pro(target_me["email"])
    assert _plan_views(target) == (False, False)
    assert {email: _account_state(email) for email in untouched} == untouched
    assert _plan_views(holder) == (True, True)
    # Revocation takes the Pro surfaces away at once and nothing else: the account, its session and beta tag stay.
    readable = _seed_readable_filing()
    assert target.get(f"/api/summaries/filing/{readable}/export/csv").json()["code"] == "plan_required"
    me = target.get("/api/auth/me").json()
    assert me["is_beta"] is True and me["email"] == target_me["email"]


# ── feedback, triage and the tester's data rights ─────────────────────────────

class _MemoryBucket:
    """Private object storage as the screenshot paths use it: the router's upload/download calls and the
    cleanup job's ``FeedbackStorage.delete``. Generations are strings, as the provider's are."""

    def __init__(self) -> None:
        self.objects: dict[str, tuple[str, bytes]] = {}
        self._generation = 0

    async def operate(self, _bucket, operation, key, *, data=None, generation=None):
        if operation == "upload":
            self._generation += 1
            self.objects[key] = (str(self._generation), data)
            return str(self._generation)
        assert operation == "download"
        stored_generation, stored = self.objects[key]
        assert stored_generation == generation
        return stored

    def verify_permissions(self) -> None:
        return None

    def delete(self, key, generation):
        stored_generation, _ = self.objects.pop(key)
        assert generation in (None, stored_generation)
        return stored_generation


@pytest.fixture
def bucket(monkeypatch):
    """Screenshots on, against a memory bucket; image normalization and the operator notice faked as the
    feedback media suite fakes them (tests/unit/test_feedback_media.py)."""
    store = _MemoryBucket()
    notices: list[tuple] = []

    async def normalize(data):
        return NormalizedFeedbackImage(data, 2, 2, hashlib.sha256(data).hexdigest())

    async def notify(*args):
        notices.append(args)

    monkeypatch.setattr(settings, "FEEDBACK_MEDIA_ENABLED", True)
    monkeypatch.setattr(settings, "FEEDBACK_MEDIA_BUCKET", "beta-acceptance-bucket")
    monkeypatch.setattr(feedback_router, "normalize_feedback_image", normalize)
    monkeypatch.setattr(feedback_router, "run_feedback_storage_operation", store.operate)
    monkeypatch.setattr(feedback_router, "_notify_admin", notify)
    feedback_router.FEEDBACK_LIMITER._hits.clear()
    feedback_router.MEDIA_INGRESS_LIMITER._hits.clear()
    store.notices = notices
    return store


def _feedback_headers(me: dict) -> dict:
    return {"Origin": settings.CORS_ORIGINS[0], "X-Requested-With": "XMLHttpRequest",
            "X-Feedback-User-Id": str(me["id"]), "Idempotency-Key": str(uuid.uuid4())}


def _send_text(browser: TestClient, me: dict, message: str):
    return browser.post("/api/feedback/", headers=_feedback_headers(me),
                        json={"type": "general", "message": message, "page_url": "/dashboard"})


def _send_screenshot(browser: TestClient, me: dict, message: str, image: bytes, headers: dict | None = None):
    return browser.post("/api/feedback/with-attachments", headers=headers or _feedback_headers(me),
                        data={"type": "bug", "message": message, "page_url": "/company/BETA"},
                        files=[("files", ("screen.png", image, "image/png"))])


def _triage_row(admin: TestClient, feedback_id: int) -> dict:
    listed = admin.get("/api/admin/feedback")
    assert listed.status_code == 200, listed.text
    rows = {row["id"]: row for row in listed.json()["feedback"]}
    assert feedback_id in rows, feedback_id
    return rows[feedback_id]


def test_feedback_reaches_triage_and_the_testers_data_leaves_with_them(browsers, outbox, bucket):
    admin = browsers()
    _sign_in(admin, _seed_admin())
    tester, me = _onboard(browsers, admin, outbox, "reporter")
    other, other_me = _onboard(browsers, admin, outbox, "neighbour")

    # Text feedback and a screenshot report, each acknowledged to the tester and noticed to the operator.
    text = _send_text(tester, me, "The dashboard took a while to load this morning.")
    assert text.status_code == 201, text.text
    image = b"beta acceptance screenshot bytes"
    shot = _send_screenshot(tester, me, "The revenue chart clipped its last bar.", image)
    assert shot.status_code == 201, shot.text
    assert len(bucket.objects) == 1 and len(bucket.notices) == 2
    neighbour_text = _send_text(other, other_me, "Search found the company on the second try.")
    assert neighbour_text.status_code == 201, neighbour_text.text

    # The operator triages both reports and can open the screenshot.
    text_row, shot_row = _triage_row(admin, text.json()["id"]), _triage_row(admin, shot.json()["id"])
    assert text_row["user_email"] == shot_row["user_email"] == me["email"]
    assert shot_row["attachment_count"] == 1 and text_row["attachment_count"] == 0
    attachment_id = shot_row["attachments"][0]["id"]
    assert admin.get(f"/api/feedback/attachments/{attachment_id}").content == image
    patched = admin.patch(f"/api/admin/feedback/{shot.json()['id']}", json={"status": "triaged"})
    assert patched.status_code == 200 and patched.json()["status"] == "triaged", patched.text
    # Triage is the operator's alone.
    assert tester.patch(f"/api/admin/feedback/{shot.json()['id']}", json={"status": "resolved"}).status_code == 403
    assert tester.get("/api/admin/feedback").status_code == 403

    # The screenshot is the reporter's and the operator's: another tester cannot read it, and a tab still
    # showing a different account is stopped before it sends.
    assert tester.get(f"/api/feedback/attachments/{attachment_id}").content == image
    assert other.get(f"/api/feedback/attachments/{attachment_id}").status_code == 404
    stale = _send_screenshot(other, other_me, "Sent from a tab that showed someone else.", b"x" * 8,
                             headers={**_feedback_headers(other_me), "X-Feedback-User-Id": str(me["id"])})
    assert stale.status_code == 409, stale.text

    # The tester's export carries their agreement and both reports, the screenshot as a private manifest entry.
    export = tester.get("/api/users/export")
    assert export.status_code == 200, export.text
    exported = export.json()
    reports = {report["id"]: report for report in exported["feedback"]}
    assert set(reports) == {text.json()["id"], shot.json()["id"]}
    manifest = reports[shot.json()["id"]]["attachments"]
    assert [entry["id"] for entry in manifest] == [attachment_id]
    assert manifest[0]["download_path"] == f"/api/feedback/attachments/{attachment_id}"
    assert "object_key" not in str(exported) and image.decode() not in str(exported)
    assert exported_agreement_versions(exported) == {
        (ACCOUNT_AGREEMENT["terms_version"], ACCOUNT_AGREEMENT["eligibility_version"])}

    # Deletion: the session ends, the screenshot stops being readable at once and the cleanup job removes
    # its object; the text reports stay for the operator without the account; the neighbour keeps theirs.
    deleted = tester.delete("/api/users/me")
    assert deleted.status_code == 200, deleted.text
    assert _account(me["email"]) is None
    assert tester.get("/api/auth/me").status_code == 401
    assert admin.get(f"/api/feedback/attachments/{attachment_id}").status_code in (404, 410)
    stats = run_feedback_media_cleanup(SessionLocal, bucket)
    assert stats["deleted"] == 1 and stats["errors"] == 0, stats
    assert bucket.objects == {}
    assert _triage_row(admin, text.json()["id"])["user_id"] is None
    assert _triage_row(admin, neighbour_text.json()["id"])["user_email"] == other_me["email"]
    assert other.get("/api/auth/me").status_code == 200


def exported_agreement_versions(exported: dict) -> set[tuple[str, str]]:
    """The (terms, eligibility) versions an export states, wherever its agreement section keeps them."""
    found: set[tuple[str, str]] = set()

    def walk(node):
        if isinstance(node, dict):
            if "terms_version" in node and "eligibility_version" in node:
                found.add((node["terms_version"], node["eligibility_version"]))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(exported)
    return found


# ── sessions and account boundaries ───────────────────────────────────────────

def test_a_tester_signs_out_resets_their_password_and_signs_back_in(browsers, outbox):
    admin = browsers()
    _sign_in(admin, _seed_admin())
    tester, me = _onboard(browsers, admin, outbox, "returning")
    second_device = browsers()
    _sign_in(second_device, me["email"])

    assert tester.post("/api/auth/logout").status_code == 200
    assert tester.get("/api/auth/me").status_code == 401
    assert second_device.get("/api/auth/me").status_code == 200  # signing out one browser leaves the other

    reset_rate_limiters()
    asked = tester.post("/api/auth/forgot-password", json={"email": me["email"]})
    assert asked.status_code == 200, asked.text
    assert outbox.reset.call_count == 1 and outbox.reset.call_args.kwargs["to_email"] == me["email"]
    token = parse_qs(urlparse(outbox.reset.call_args.kwargs["reset_link"]).query)["token"][0]
    new_password = PASSWORD + "9z"  # gitleaks:allow
    reset = tester.post("/api/auth/reset-password", json={"token": token, "new_password": new_password})
    assert reset.status_code == 200, reset.text

    # The reset ends every session; the old password no longer works and the new one does.
    second_device.cookies.delete("earningsnerd_access_token")
    assert second_device.post("/api/auth/refresh").status_code == 401
    reset_rate_limiters()
    assert tester.post("/api/auth/login", json={"email": me["email"], "password": PASSWORD}).status_code == 401
    _sign_in(tester, me["email"], new_password)
    assert tester.post("/api/auth/reset-password", json={"token": token, "new_password": PASSWORD + "x1"}
                       ).status_code == 400  # the link is single-use


def test_one_testers_session_never_reaches_anothers_records(browsers, outbox):
    admin = browsers()
    _sign_in(admin, _seed_admin())
    owner, owner_me = _onboard(browsers, admin, outbox, "owner")
    intruder, _intruder_me = _onboard(browsers, admin, outbox, "intruder")

    # Watchlist: the owner's company never shows in, or leaves through, the other tester's list.
    _company_id, ticker = _seed_company("WL")
    assert owner.post(f"/api/watchlist/{ticker}").status_code == 200
    assert ticker not in {row["company"]["ticker"] for row in intruder.get("/api/watchlist/").json()}
    assert intruder.delete(f"/api/watchlist/{ticker}").status_code == 404
    assert ticker in {row["company"]["ticker"] for row in owner.get("/api/watchlist/").json()}

    # Saved summaries: the other tester can neither edit nor delete the owner's bookmark.
    reset_inflight()
    filing_id = seed_company_filing()
    with stream_boundaries():
        assert '"type": "complete"' in _generate(owner, filing_id)
    with SessionLocal() as db:
        summary_id = db.query(Summary.id).filter(Summary.filing_id == filing_id).scalar()
    saved = owner.post("/api/saved-summaries/", json={"summary_id": summary_id, "notes": "beta note"})
    assert saved.status_code == 200, saved.text
    saved_id = saved.json()["id"]
    assert intruder.put(f"/api/saved-summaries/{saved_id}", params={"notes": "changed"}).status_code == 404
    assert intruder.delete(f"/api/saved-summaries/{saved_id}").status_code == 404
    assert intruder.get(f"/api/saved-summaries/status/{summary_id}").json() == {"is_saved": False}
    kept = owner.get("/api/saved-summaries/").json()
    assert [(row["id"], row["notes"]) for row in kept] == [(saved_id, "beta note")]

    # Feedback receipts are the sender's.
    key = str(uuid.uuid4())
    sent = owner.post("/api/feedback/", headers={**_feedback_headers(owner_me), "Idempotency-Key": key},
                      json={"type": "general", "message": "A receipt only its sender may read."})
    assert sent.status_code == 201, sent.text
    assert owner.get(f"/api/feedback/submissions/{key}").json()["state"] == "submitted"
    assert intruder.get(f"/api/feedback/submissions/{key}").status_code == 404

    # The export is the caller's own, never another tester's.
    assert intruder.get("/api/users/export").json()["feedback"] == []


# ── rollback drills: each lever stops one thing and keeps the rest ────────────

def test_pausing_invitations_keeps_existing_testers_signed_in_and_their_rights(browsers, outbox):
    admin = browsers()
    _sign_in(admin, _seed_admin())
    tester, me = _onboard(browsers, admin, outbox, "admitted")
    _grant_pro(me["email"])
    cohort = f"beta-wave-{uuid.uuid4().hex[:8]}"
    pending = [_mint_invite(admin, _address(f"waiting{n}"), cohort=cohort) for n in range(2)]

    # Pause: revoke every outstanding invitation of the cohort, found the way the operator finds them.
    listed = admin.get("/api/admin/invites")
    assert listed.status_code == 200, listed.text
    outstanding = [row["id"] for row in listed.json()["invites"]
                   if row["cohort"] == cohort and row["status"] == "pending"]
    assert sorted(outstanding) == sorted(invite_id for invite_id, _token in pending)
    for invite_id in outstanding:
        assert admin.post(f"/api/admin/invites/{invite_id}/revoke").status_code == 200

    for _invite_id, token in pending:
        reset_rate_limiters()
        assert _register(browsers(), _address("late"), token).json() == INVITE_REFUSED
    # Admitted testers keep their session, their Pro rights and their data rights.
    assert tester.get("/api/auth/me").status_code == 200
    assert _plan_views(tester) == (True, True)
    assert tester.get("/api/users/export").status_code == 200


def test_switching_screenshots_off_keeps_text_feedback_and_cleanup(browsers, outbox, bucket, monkeypatch):
    admin = browsers()
    _sign_in(admin, _seed_admin())
    tester, me = _onboard(browsers, admin, outbox, "screens")
    shot = _send_screenshot(tester, me, "Sent while screenshots were on.", b"kept screenshot")
    assert shot.status_code == 201, shot.text

    monkeypatch.setattr(settings, "FEEDBACK_MEDIA_ENABLED", False)
    capabilities = tester.get("/api/feedback/capabilities")
    assert capabilities.status_code == 200 and capabilities.json()["attachments_enabled"] is False
    refused = _send_screenshot(tester, me, "Sent after screenshots went off.", b"refused screenshot")
    assert refused.status_code == 503 and "draft" in refused.json()["detail"], refused.text
    assert _send_text(tester, me, "Text feedback still arrives.").status_code == 201
    # The screenshot already sent stays readable to its owner, and deleting the account still cleans it up.
    attachment_id = _triage_row(admin, shot.json()["id"])["attachments"][0]["id"]
    assert tester.get(f"/api/feedback/attachments/{attachment_id}").content == b"kept screenshot"
    assert tester.delete("/api/users/me").status_code == 200
    assert run_feedback_media_cleanup(SessionLocal, bucket)["deleted"] == 1
    assert bucket.objects == {}


# ── the social path: an invited Google sign-up, then a returning sign-in ──────

class _FakeTokenResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"id_token": "stub"}


class _FakeGoogleExchange:
    """httpx.AsyncClient for the callback's code exchange, as tests/unit/test_oauth_invite_gate.py fakes it."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    async def post(self, *args, **kwargs) -> _FakeTokenResponse:
        return _FakeTokenResponse()


def _google_round_trip(browser: TestClient, monkeypatch, claims: dict, invite: str | None = None):
    started = browser.post("/api/auth/google/start", json={**ACCOUNT_AGREEMENT, "invite": invite})
    assert started.status_code == 200, started.text
    state = parse_qs(urlparse(started.json()["url"]).query)["state"][0]
    monkeypatch.setattr(auth_module, "httpx", SimpleNamespace(AsyncClient=_FakeGoogleExchange))
    monkeypatch.setattr(auth_module, "_verify_google_id_token", AsyncMock(return_value=claims))
    return browser.get("/api/auth/google/callback", params={"code": "code", "state": state}, follow_redirects=False)


def test_an_invited_tester_signs_up_with_google_and_signs_back_in(browsers, outbox, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "beta-acceptance-google-client")
    auth_module.OAUTH_START_LIMITER._hits.clear()
    admin = browsers()
    _sign_in(admin, _seed_admin())
    email = _address("social")
    invite_id, token = _mint_invite(admin, email)
    claims = {"sub": f"google_{uuid.uuid4().hex}", "email": email, "email_verified": True}

    tester = browsers()
    landed = _google_round_trip(tester, monkeypatch, claims, invite=token)
    assert landed.status_code == 302 and "error=" not in landed.headers["location"], landed.headers.get("location")
    me = tester.get("/api/auth/me").json()
    assert me["email"] == email and me["is_beta"] is True and me["email_verified"] is True
    assert _invite_row(invite_id).user_id == me["id"]
    with SessionLocal() as db:
        agreement = db.query(AccountAgreement).filter(AccountAgreement.user_id == me["id"]).one()
        assert agreement.source == "google" and agreement.terms_version == ACCOUNT_AGREEMENT["terms_version"]
    assert outbox.verification.call_count == 0  # the provider verified the address

    _grant_pro(email)
    assert _plan_views(tester) == (True, True)

    # Signing out and back in with Google needs no invite and keeps the account, its beta tag and its Pro.
    assert tester.post("/api/auth/logout").status_code == 200
    assert tester.get("/api/auth/me").status_code == 401
    auth_module.OAUTH_START_LIMITER._hits.clear()
    again = _google_round_trip(tester, monkeypatch, claims)
    assert again.status_code == 302 and "error=" not in again.headers["location"], again.headers.get("location")
    assert tester.get("/api/auth/me").json()["id"] == me["id"]
    assert _plan_views(tester) == (True, True)
    # A social-only account has no password to reset: the opaque answer sends nothing (its way back is Google).
    reset_rate_limiters()
    assert tester.post("/api/auth/forgot-password", json={"email": email}).status_code == 200
    assert outbox.reset.call_count == 0


# ── billing never reaches a complimentary tester through someone else's events ─

def _post_stripe_event(browser: TestClient, event: dict):
    """Deliver a verified Stripe event, as tests/unit/test_subscription_webhook_sync.py does: only the signature
    check and the subscription read-back are faked; the handler and the sync run for real."""
    with patch("app.routers.subscriptions.stripe.Webhook.construct_event",
               return_value=StripeObject.construct_from(event, "sk_test")), \
         patch("app.services.subscription_webhook_service.retrieve_subscription_snapshot",
               return_value=event["data"]["object"]):
        return browser.post("/api/subscriptions/webhook", content=json.dumps(event).encode(),
                            headers={"stripe-signature": "t=1,v1=deadbeef"})


def _stripe_event(kind: str, obj: dict) -> dict:
    return {"id": f"evt_{uuid.uuid4().hex}", "type": kind, "data": {"object": obj}}


def test_billing_events_for_other_accounts_never_reach_a_complimentary_tester(browsers, outbox):
    admin = browsers()
    _sign_in(admin, _seed_admin())
    tester, me = _onboard(browsers, admin, outbox, "complimentary")
    _grant_pro(me["email"])
    before = _account_state(me["email"])
    with SessionLocal() as db:
        payer = User(email=_address("payer"), hashed_password="x", email_verified=True, is_active=True)
        db.add(payer)
        db.commit()
        payer_id = payer.id
    sub_id, customer_id = f"sub_{uuid.uuid4().hex[:12]}", f"cus_{uuid.uuid4().hex[:12]}"
    subscription = {"id": sub_id, "customer": customer_id, "cancel_at_period_end": False,
                    "items": {"data": [{"price": {"id": "price_x"}}]}}
    events = [
        _stripe_event("checkout.session.completed", {"subscription": sub_id, "customer": customer_id, "metadata": {
            "user_id": str(payer_id), "plan": "pro", "price_id": "price_x"}}),
        _stripe_event("customer.subscription.updated", {**subscription, "status": "past_due"}),
        _stripe_event("customer.subscription.deleted", {**subscription, "status": "canceled"}),
        _stripe_event("customer.subscription.deleted", {"id": "sub_unknown_beta", "customer": "cus_unknown_beta",
                                                         "status": "canceled"}),
    ]
    stripe_sender = browsers()
    for stripe_event in events:
        assert _post_stripe_event(stripe_sender, stripe_event).status_code == 200, stripe_event["type"]
        assert _account_state(me["email"]) == before, stripe_event["type"]
        assert _plan_views(tester) == (True, True), stripe_event["type"]
    with SessionLocal() as db:  # the events did reach the account they name
        assert db.query(Subscription).filter(Subscription.user_id == payer_id).one().status == "canceled"
