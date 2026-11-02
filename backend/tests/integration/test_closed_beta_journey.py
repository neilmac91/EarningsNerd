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

import asyncio
import hashlib
import importlib
import json
import uuid
from dataclasses import fields
from datetime import timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import and_, create_engine, delete, event, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.pool import QueuePool
from stripe import StripeObject

from app import database
from app.config import settings
from app.database import DB_POOL_TIMEOUT, Base, SessionLocal
from app.models import (AccountAgreement, Company, Filing, FilingContentCache, InviteCode, Subscription, Summary, User,
                        UserUsage)
from app.models.feedback import FeedbackAttachment
from app.routers import auth as auth_module
from app.routers import feedback as feedback_router
from app.routers import summaries as summaries_router
from app.services import complimentary_access_service
from app.services.complimentary_access_manifest import email_fingerprint, load_manifest
from app.services.entitlements import _FREE, _PRO, Entitlements
from app.services.feedback_image_service import NormalizedFeedbackImage
from app.services.feedback_media_cleanup_service import run_feedback_media_cleanup
from app.services.legal_readiness_service import COLLECTION_UNAVAILABLE_MESSAGE
from app.services.password_utils import get_password_hash
from app.services.subscription_service import get_current_month
from app.utils.datetimes import utcnow
from main import app
from tests.support.account_agreement import ACCOUNT_AGREEMENT
from tests.support.session_local_binders import SESSION_LOCAL_BINDERS
from tests.support.summary_stream_harness import (CANONICAL_PAYLOAD, reset_inflight, reset_rate_limiters,
                                                  seed_company_filing, stream_boundaries)

pytestmark = [pytest.mark.integration, pytest.mark.requires_db, pytest.mark.usefixtures("collection_ready")]

PASSWORD = "Sup3rSecretPassw0rd"  # test fixture, not a credential  # gitleaks:allow


def _refused_invitation(resp) -> bool:
    """A registration the invitation refused: a client error with a reason. Not the wording or the status the
    refusal uses today, which PB-01 is asked to make specific to each case."""
    return 400 <= resp.status_code < 500 and resp.status_code not in (422, 429) and bool(resp.json().get("detail"))


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
def _leave_no_rows(started):
    """Delete every row a test here created, when it ends. These tests share their worker's database with the
    whole suite, and some suites read whole tables (the filing scan scans every watched company), so a synthetic
    beta account left behind would change what they see. A row is this test's when its primary key was absent
    before the test ran; the database never reuses an id (tests/conftest.py)."""
    before = _primary_keys()
    yield
    created = {name: keys - before.get(name, set()) for name, keys in _primary_keys().items()}
    with SessionLocal() as db:
        for table in reversed(Base.metadata.sorted_tables):
            columns = list(table.primary_key.columns)
            for key in created.get(table.name, ()):
                db.execute(delete(table).where(and_(*(column == value for column, value in zip(columns, key)))))
        db.commit()


def _primary_keys() -> dict[str, set[tuple]]:
    with SessionLocal() as db:
        return {table.name: {tuple(row) for row in db.execute(select(*table.primary_key.columns))}
                for table in Base.metadata.sorted_tables if table.primary_key.columns}


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

    # The redeemed link is spent: the same token, from the address it names, opens nothing more.
    reset_rate_limiters()
    again = _register(browsers(), email, token)
    assert _refused_invitation(again), again.text


def test_every_unusable_invitation_is_refused_and_creates_nothing(browsers, outbox):
    admin = browsers()
    _sign_in(admin, _seed_admin())

    bound_to, other = _address("bound"), _address("other")
    _id, wrong_address_token = _mint_invite(admin, bound_to)
    # Each of these is tried from the address it names, so only its own condition can refuse it.
    revoked_address, expired_address = _address("revoked"), _address("expired")
    revoked_id, revoked_token = _mint_invite(admin, revoked_address)
    assert admin.post(f"/api/admin/invites/{revoked_id}/revoke").status_code == 200
    expired_id, expired_token = _mint_invite(admin, expired_address)
    with SessionLocal() as db:
        db.get(InviteCode, expired_id).expires_at = utcnow() - timedelta(minutes=1)
        db.commit()

    cases = {
        "missing": (_address("missing"), None),
        "unknown": (_address("unknown"), "not-a-minted-token"),
        "another address": (other, wrong_address_token),
        "revoked": (revoked_address, revoked_token),
        "expired": (expired_address, expired_token),
    }
    for name, (email, token) in cases.items():
        reset_rate_limiters()  # every browser here shares the test client's address; throttling is pinned elsewhere
        resp = _register(browsers(), email, token)
        assert _refused_invitation(resp), (name, resp.status_code, resp.text)
        assert _account(email) is None and "earningsnerd_access_token" not in resp.cookies, name
    assert outbox.verification.call_count == 0
    # The address-bound invitation is still there for the address it names.
    reset_rate_limiters()
    assert _register(browsers(), bound_to, wrong_address_token).status_code == 200


# ── complimentary Pro: the grant seam, the capability matrix and its gate ─────

# How an account can hold Pro without paying, as entitlements.get_plan resolves it: the ``is_pro`` mirror of an
# account with no Subscription row, or a granting row kept in lockstep with the mirror, as subscription_sync writes
# them. PB-02's complimentary grant sets the mirror (``_grant_pro``); the matrix below runs on every holder.
PRO_HOLDERS = ("mirror", "active-row", "future-trial-row")


def _grant_pro(email: str, holder: str = "mirror") -> None:
    """The one seam that makes a beta account Pro, so the matrix and the isolation check never depend on how.

    ``mirror`` is PB-02's complimentary grant, run as the operator runs it. The two row holders are a subscriber's
    Pro, which the grant cannot express (it refuses an account with a Subscription row of any status and never
    writes one), so they keep the rows subscription_sync would write.
    """
    if holder == "mirror":
        report = _complimentary_access("grant", email)
        assert report["outcomes"] == {"granted": 1} and not report["refusals"], report
        return
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one()
        user.is_pro = True
        trial_end = utcnow() + timedelta(days=7) if holder == "future-trial-row" else None
        db.add(Subscription(user_id=user.id, plan="pro", status="trialing" if trial_end else "active",
                            trial_end=trial_end))
        db.commit()


def _revoke_pro(email: str) -> None:
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one()
        if user.complimentary_access_grant is None:  # a row holder's Pro, not a grant's: end it as the old seam did
            user.is_pro = False
            db.query(Subscription).filter(Subscription.user_id == user.id).update({"status": "canceled"})
            db.commit()
            return
    report = _complimentary_access("revoke", email)
    assert report["outcomes"] == {"revoked": 1} and not report["refusals"], report


def _complimentary_access(action: str, email: str) -> dict:
    """PB-02's operator procedure (docs/ops/complimentary-access.md) for one account: a manifest naming it by id and
    address fingerprint, signed by an active verified administrator; the dry run; then the apply of the digest that
    dry run reported, on the app's own sessions."""
    operator, account = _account(_seed_admin()), _account(email)
    today = utcnow().date()
    payload = {"action": action, "cohort": "beta-acceptance", "reason": "PB-05 closed-beta acceptance",
               "operator_account_id": operator.id,
               "accounts": [{"account_id": account.id, "email_sha256": email_fingerprint(account.email)}]}
    if action == "grant":
        payload["review_on"] = (today + timedelta(days=90)).isoformat()
    manifest, digest = load_manifest(json.dumps(payload).encode())
    with SessionLocal() as db:
        planned = complimentary_access_service.dry_run(db, manifest, digest, today=today)
        assert planned.stopped is None and not planned.refusals, planned.as_dict()
        return complimentary_access_service.apply(db, manifest, digest, confirm_digest=planned.manifest_sha256,
                                                  today=today, runner="local").as_dict()


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

    # Multi-Period Analysis and its Excel export: the Pro gate admits the Pro tester, whose request reaches the
    # route's own answer for a company with no facts yet, and refuses Free.
    _company_id, ticker = _seed_company()
    window = {"mode": "annual", "start_period": "FY2016", "end_period": "FY2025"}
    for path in (f"/api/analysis/{ticker}/dataset", f"/api/analysis/{ticker}/export/xlsx"):
        admitted = pro.post(path, json=window)
        assert admitted.status_code == 400 and "No data available" in admitted.json()["detail"], (path, admitted.text)
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
        stored = self.objects.pop(key, None)
        assert stored is not None, "the cleanup run reached a screenshot row this test did not create"
        assert generation in (None, stored[0])
        return stored[0]


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


def _attachment_state(attachment_id: str) -> str:
    with SessionLocal() as db:
        return db.get(FeedbackAttachment, attachment_id).state


def _clean_up(bucket: _MemoryBucket) -> None:
    """Run the hourly cleanup job over this test's screenshots alone.

    The job claims every due row in the database, oldest first, up to its batch. Rows another module left due
    are moved out of its reach for the run and put back as they were, so the run claims only this test's rows,
    however many others wait, and leaves no trace on rows this module did not create.
    """
    out_of_reach = utcnow() + timedelta(days=3650)
    with SessionLocal() as db:
        others = {row.id: row.deletion_due_at for row in db.query(FeedbackAttachment).filter(
            FeedbackAttachment.deleted_at.is_(None), FeedbackAttachment.object_key.notin_(list(bucket.objects)))}
        if others:
            db.query(FeedbackAttachment).filter(FeedbackAttachment.id.in_(list(others))).update(
                {"deletion_due_at": out_of_reach}, synchronize_session=False)
            db.commit()
    try:
        run_feedback_media_cleanup(SessionLocal, bucket)
    finally:
        with SessionLocal() as db:
            for row_id, due in others.items():
                db.query(FeedbackAttachment).filter(FeedbackAttachment.id == row_id).update(
                    {"deletion_due_at": due}, synchronize_session=False)
            db.commit()


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
    _clean_up(bucket)
    assert bucket.objects == {}
    assert _attachment_state(attachment_id) == "deleted"
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
    waiting = [_address(f"waiting{n}") for n in range(2)]
    pending = [_mint_invite(admin, address, cohort=cohort) for address in waiting]

    # Pause: revoke every outstanding invitation of the cohort, found the way the operator finds them.
    listed = admin.get("/api/admin/invites")
    assert listed.status_code == 200, listed.text
    outstanding = [row["id"] for row in listed.json()["invites"]
                   if row["cohort"] == cohort and row["status"] == "pending"]
    assert sorted(outstanding) == sorted(invite_id for invite_id, _token in pending)
    for invite_id in outstanding:
        assert admin.post(f"/api/admin/invites/{invite_id}/revoke").status_code == 200

    for address, (_invite_id, token) in zip(waiting, pending):  # from the address each names: only the revoke refuses
        reset_rate_limiters()
        late = _register(browsers(), address, token)
        assert _refused_invitation(late) and _account(address) is None, late.text
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
    _clean_up(bucket)
    assert bucket.objects == {}
    assert _attachment_state(attachment_id) == "deleted"



def test_closing_collection_stops_new_accounts_and_keeps_admitted_testers(browsers, outbox, monkeypatch):
    admin = browsers()
    _sign_in(admin, _seed_admin())
    tester, me = _onboard(browsers, admin, outbox, "kept")
    _grant_pro(me["email"])
    waiting = _address("waiting")
    pending_id, pending_token = _mint_invite(admin, waiting)

    monkeypatch.setattr(settings, "LEGAL_COLLECTION_ENABLED", False)  # the stop-everything lever
    assert browsers().get("/api/legal/readiness").json()["collection_available"] is False
    closed = {"detail": COLLECTION_UNAVAILABLE_MESSAGE}
    minted = admin.post("/api/admin/invites", json={"email": _address("new"), "cohort": "beta-acceptance"})
    assert (minted.status_code, minted.json()) == (503, closed)
    resent = admin.post(f"/api/admin/invites/{pending_id}/resend")
    assert (resent.status_code, resent.json()) == (503, closed)
    reset_rate_limiters()
    refused = _register(browsers(), waiting, pending_token)
    assert refused.status_code == 503 and _account(waiting) is None
    # The waiting invitation is neither spent nor revoked: reopening collection makes it usable again.
    invite = _invite_row(pending_id)
    assert invite.used_at is None and invite.is_revoked is False

    # Admitted testers keep their session, can sign in again, and keep Pro and their data rights.
    assert tester.get("/api/auth/me").status_code == 200
    assert tester.post("/api/auth/logout").status_code == 200
    reset_rate_limiters()
    _sign_in(tester, me["email"])
    assert _plan_views(tester) == (True, True)
    assert tester.get("/api/users/export").status_code == 200


def test_pausing_new_summaries_keeps_stored_ones_and_the_rest_of_the_account(browsers, outbox, monkeypatch):
    admin = browsers()
    _sign_in(admin, _seed_admin())
    tester, me = _onboard(browsers, admin, outbox, "paused")
    _grant_pro(me["email"])
    reset_inflight()
    stored, fresh = seed_company_filing(), seed_company_filing()
    with stream_boundaries():
        assert '"type": "complete"' in _generate(tester, stored)

    monkeypatch.setattr(settings, "SUMMARY_NEW_JOBS_PAUSED", True)  # summary spend or capacity lever
    with stream_boundaries() as summarize:
        refused = _generate(tester, fresh)
        served = _generate(tester, stored)
    assert '"code": "generation_paused"' in refused and '"type": "complete"' not in refused
    assert '"type": "complete"' in served and '"generation_paused"' not in served
    summarize.assert_not_awaited()  # no model call while paused
    assert tester.get(f"/api/summaries/filing/{stored}").status_code == 200
    with SessionLocal() as db:
        assert db.query(Summary).filter(Summary.filing_id == fresh).count() == 0
    # The rest of the account carries on: Pro and its export of a stored summary, feedback, and a fresh sign-in.
    assert _plan_views(tester) == (True, True)
    exported = tester.get(f"/api/summaries/filing/{stored}/export/csv")
    assert exported.status_code == 200 and exported.content, exported.text[:200]
    assert _send_text(tester, me, "Generation is paused but feedback still works.").status_code == 201
    assert tester.post("/api/auth/logout").status_code == 200
    reset_rate_limiters()
    _sign_in(tester, me["email"])
    assert _plan_views(tester) == (True, True)

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


# ── load: account work answers while a beta's worth of summaries generate ─────

@pytest.fixture
def production_pool(monkeypatch):
    """The app's sessions on a pool shaped like the deployed API's: four connections, no overflow, its timeout."""
    pool = create_engine(make_url(settings.DATABASE_URL), connect_args={"check_same_thread": False},
                         poolclass=QueuePool, pool_size=4, max_overflow=0, pool_timeout=DB_POOL_TIMEOUT)
    sessions = sessionmaker(autocommit=False, autoflush=False, bind=pool)
    monkeypatch.setattr(database, "SessionLocal", sessions)
    for name in SESSION_LOCAL_BINDERS:
        monkeypatch.setattr(importlib.import_module(name), "SessionLocal", sessions)
    yield pool
    pool.dispose()


@pytest.mark.asyncio
async def test_account_work_answers_while_summaries_generate_on_a_production_sized_pool(production_pool, monkeypatch,
                                                                                         outbox):
    """Fresh summaries are generated inside the API request (durable generation is not active), in the same process,
    pool and event loop as sign-in, usage, feedback and account mail. The deployed pool is four connections with no
    overflow (docs/OPERATIONS.md, Monitoring Alerts). Here the most generations a process admits are held at the model
    call, the longest phase in production, while a tester signs in, reads usage, sends feedback and asks for a
    password reset: the held generations must leave the pool a connection, and each request must answer before its
    deadline. Then every generation completes.

    In-process and on SQLite with the production pool's shape: it shows the request units give their connections back
    before the model call. It is not evidence of production CPU, provider throughput or PostgreSQL headroom."""
    pool = production_pool
    monkeypatch.setattr(auth_module, "sentry_sdk", None)
    reset_rate_limiters()
    reset_inflight()

    generations = settings.MAX_CONCURRENT_GENERATIONS
    readers = [_address(f"reader{n}") for n in range(generations)]
    member = _address("member")
    with database.SessionLocal() as db:
        db.add_all([User(email=email, is_active=True, email_verified=True, is_pro=True) for email in readers])
        db.add(User(email=member, hashed_password=get_password_hash(PASSWORD), is_active=True, email_verified=True))
        db.commit()
    filings = [seed_company_filing() for _ in readers]

    held: list[int] = []
    release = asyncio.Event()

    async def model_call(*_args, **_kwargs):
        held.append(1)
        await release.wait()
        return CANONICAL_PAYLOAD

    def bearer(email: str) -> dict:
        return {"Authorization": f"Bearer {auth_module.create_access_token({'sub': email})}"}

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
        with stream_boundaries() as summarize:
            summarize.side_effect = model_call
            running = [asyncio.create_task(client.post(f"/api/summaries/filing/{filing}/generate-stream",
                                                       headers=bearer(email)))
                       for email, filing in zip(readers, filings)]
            await asyncio.wait_for(_until(lambda: len(held) == generations), timeout=60)
            in_use_while_held = pool.pool.checkedout()

            member_id = str(_user_id(member))
            answers = await asyncio.wait_for(asyncio.gather(
                client.post("/api/auth/login", json={"email": member, "password": PASSWORD}),
                client.get("/api/auth/me", headers=bearer(member)),
                client.get("/api/subscriptions/usage", headers=bearer(member)),
                client.post("/api/feedback/", headers={**bearer(member), "X-Feedback-User-Id": member_id},
                            json={"type": "general", "message": "Sent while six summaries generate."}),
                client.post("/api/auth/forgot-password", json={"email": member}),
            ), timeout=60)
            assert len(held) == generations and not any(task.done() for task in running)

            release.set()
            streams = await asyncio.wait_for(asyncio.gather(*running), timeout=60)

    assert in_use_while_held < 4, in_use_while_held
    assert [answer.status_code for answer in answers] == [200, 200, 200, 201, 200], [a.text[:120] for a in answers]
    assert outbox.reset.call_count == 1
    assert all(stream.status_code == 200 and '"type": "complete"' in stream.text for stream in streams)
    assert pool.pool.checkedout() == 0


async def _until(condition) -> None:
    while not condition():
        await asyncio.sleep(0.01)


def _user_id(email: str) -> int:
    with database.SessionLocal() as db:
        return db.query(User.id).filter(User.email == email).scalar()
