"""T5 — expired-trial gating is enforced AT THE ROUTE LEVEL, not only in the resolver.

``test_entitlements.py::test_trialing_subscription_with_expired_trial_is_free`` pins the *resolver*
truth: a ``Subscription`` with ``status="trialing"`` whose ``trial_end`` is in the past resolves to
``Plan.FREE``. This module pins the *consequence at the HTTP boundary*: such a user is treated as
Free by the real Pro-gated routes and rejected, exactly as if they had no subscription.

Unlike ``test_entitlements.py`` (which hands the resolver a ``SimpleNamespace``) and
``test_copilot.py`` (which overrides auth with an ``is_pro`` stand-in), this seeds a **real
Subscription row** in SQLite and drives the route-level entitlement decision off it — so the whole
chain (``get_current_user`` → ``get_entitlements`` → ``_subscription_grants_pro`` → route gate) is
exercised end to end.

How expired-trial → FREE is decided:
``app/services/entitlements.py::_subscription_grants_pro`` (lines 138-140) — a ``trialing`` row with
a non-null ``trial_end`` grants Pro only if ``_is_in_future(trial_end)`` (lines 111-118); an elapsed
trial returns ``False`` → ``get_plan`` returns ``Plan.FREE`` (line 147).

Two routes are covered:
* Copilot ``POST /api/summaries/filing/{id}/ask-stream`` (dep ``require_copilot_or_taste``). NB this
  is NOT a pure Pro gate: a Free user still gets a 3-question lifetime "free taste" (roadmap 2.2), so
  an expired-trial user is only rejected here once that taste is spent. Holding the taste spent and
  flipping ``trial_end`` past→future flips 403→200 — isolating the trial expiry as the gating cause.
* Export ``GET /api/summaries/filing/{id}/export/pdf`` — a *pure* ``can_export`` Pro gate: an
  expired-trial user is rejected outright; a future-trial user clears the gate (then 404s on the
  absent summary), proving the gate — not the route — is what the expiry moves.
"""
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import joinedload

from main import app
from app.routers.auth import get_current_user, get_current_user_optional
from app.dependencies import _resolve_current_user

_FAKE_SOURCE = "Item 7 — MD&A. Revenue increased to 391.0 billion driven by strong iPhone demand."


def _past() -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=1)


def _future() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=3)


@pytest.fixture(scope="module")
def client():
    # Entering the TestClient runs the app lifespan, which creates the schema (Base.metadata.
    # create_all) — so the direct-SessionLocal seeding below has tables to write to.
    with TestClient(app) as test_client:
        yield test_client


@contextmanager
def _as_trial_user(trial_end, *, taste_used=0):
    """Seed a real User + a real ``Subscription(status='trialing', trial_end=...)`` and override the
    auth dependencies to return that (real, detached) user.

    The user is reloaded with the subscription eagerly populated, then expunged (not committed) so
    the entitlements resolver can read ``user.subscription.{status,trial_end}`` after this session
    closes — no lazy load, no ``DetachedInstanceError``. ``copilot_free_taste_used`` seeds the
    lifetime Copilot free-taste counter so the copilot route's taste allowance can be exercised.
    """
    from app.database import SessionLocal
    from app.models import Subscription, User, UserUsage

    db = SessionLocal()
    user = User(
        email=f"trial-{uuid.uuid4().hex}@example.com", hashed_password="x",
        email_verified=True, is_active=True, is_pro=False, copilot_free_taste_used=taste_used,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    uid = user.id
    db.add(Subscription(user_id=uid, plan="pro", status="trialing", trial_end=trial_end))
    db.commit()
    user = (
        db.query(User).options(joinedload(User.subscription)).filter(User.id == uid).first()
    )
    _ = user.subscription.status, user.subscription.trial_end  # force-populate __dict__
    db.expunge_all()
    db.close()

    # Override every auth entry point a Pro-gated route might inject: require_copilot_or_taste
    # resolves through _resolve_current_user; the export routes use get_current_user_optional.
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[_resolve_current_user] = lambda: user
    app.dependency_overrides[get_current_user_optional] = lambda: user
    try:
        yield uid
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(_resolve_current_user, None)
        app.dependency_overrides.pop(get_current_user_optional, None)
        db = SessionLocal()
        db.query(UserUsage).filter(UserUsage.user_id == uid).delete()
        db.query(Subscription).filter(Subscription.user_id == uid).delete()
        db.query(User).filter(User.id == uid).delete()
        db.commit()
        db.close()


@contextmanager
def _seed_filing():
    """Insert a Company + Filing (+ content cache) so a route body that clears the gate can load a
    real filing. Mirrors ``test_copilot._seed_filing``."""
    from app.database import SessionLocal
    from app.models import Company, Filing, FilingContentCache

    db = SessionLocal()
    suffix = uuid.uuid4().hex[:10]
    company = Company(cik=f"cik{suffix}", ticker=f"T{suffix[:4]}", name="Test Co")
    db.add(company)
    db.commit()
    db.refresh(company)
    filing = Filing(
        company_id=company.id,
        accession_number=f"acc-{suffix}",
        filing_type="10-K",
        filing_date=datetime(2026, 1, 1),
        document_url="https://www.sec.gov/Archives/edgar/data/1/x/doc.htm",
        sec_url="https://www.sec.gov/Archives/edgar/data/1/x/",
    )
    db.add(filing)
    db.commit()
    db.refresh(filing)
    db.add(FilingContentCache(filing_id=filing.id, critical_excerpt=_FAKE_SOURCE))
    db.commit()
    fid, cid = filing.id, company.id
    db.close()
    try:
        yield fid
    finally:
        db = SessionLocal()
        db.query(FilingContentCache).filter(FilingContentCache.filing_id == fid).delete()
        db.query(Filing).filter(Filing.id == fid).delete()
        db.query(Company).filter(Company.id == cid).delete()
        db.commit()
        db.close()


async def _fake_answer(*, filing, question, history=None):
    yield {"type": "complete", "answer": "ok", "citations": [], "grounded": 0, "kind": "answer"}


# --- Copilot route (require_copilot_or_taste) --------------------------------------------------

@pytest.mark.requires_db
def test_copilot_route_gates_expired_trial_when_taste_spent(client):
    """Expired trial → treated as FREE; with the free taste already spent, the copilot route 403s.

    This is the route-level echo of the resolver's expired-trial downgrade.
    """
    with _as_trial_user(_past(), taste_used=3), _seed_filing() as fid:
        resp = client.post(f"/api/summaries/filing/{fid}/ask-stream", json={"question": "Hi?"})

    assert resp.status_code == 403
    # Exact upsell body from require_copilot_or_taste (dependencies.py) for a spent free taste.
    assert resp.json()["detail"] == (
        "You've used your 3 free Copilot questions. Upgrade to Pro to access this feature."
    )


@pytest.mark.requires_db
def test_copilot_route_allows_future_trial_despite_spent_taste(client, monkeypatch):
    """Contrast: the SAME setup (taste spent) but ``trial_end`` in the FUTURE is still Pro, so the
    copilot route streams a 200 — the free-taste counter is irrelevant to a Pro user. Only the trial
    expiry moved 403→200, proving it's the expiry (not merely being 'trialing') that gates."""
    import app.routers.summaries as summaries_router
    monkeypatch.setattr(summaries_router, "answer_filing_question", _fake_answer)

    with _as_trial_user(_future(), taste_used=3), _seed_filing() as fid:
        resp = client.post(f"/api/summaries/filing/{fid}/ask-stream", json={"question": "Hi?"})

    assert resp.status_code == 200
    assert '"type": "complete"' in resp.text


@pytest.mark.requires_db
def test_copilot_route_allows_expired_trial_while_taste_remains(client, monkeypatch):
    """Honest caveat (ACTUAL behavior): the copilot route is NOT a pure Pro gate. An expired-trial
    user IS downgraded to FREE, but a FREE user still gets a lifetime free taste — so with taste
    unspent the expired-trial user is ALLOWED here. The gate only bites once the taste is spent
    (see the test above); the pure Pro gate is the export route below."""
    import app.routers.summaries as summaries_router
    monkeypatch.setattr(summaries_router, "answer_filing_question", _fake_answer)

    with _as_trial_user(_past(), taste_used=0), _seed_filing() as fid:
        resp = client.post(f"/api/summaries/filing/{fid}/ask-stream", json={"question": "Hi?"})

    assert resp.status_code == 200
    assert '"type": "complete"' in resp.text


# --- Export route (pure can_export Pro gate) ---------------------------------------------------

@pytest.mark.requires_db
def test_export_pdf_gates_expired_trial(client):
    """Expired trial → FREE → the PDF-export Pro gate (``can_export``) rejects with 403. A pure Pro
    gate (no free-taste escape hatch), so the rejection needs no extra setup."""
    with _as_trial_user(_past()):
        # filing_id is arbitrary: the can_export gate rejects before any filing/summary lookup.
        resp = client.get("/api/summaries/filing/999999/export/pdf")

    assert resp.status_code == 403
    assert resp.json()["detail"] == (
        "PDF export is a Pro feature. Upgrade to Pro to access this feature."
    )


@pytest.mark.requires_db
def test_export_pdf_allows_future_trial(client):
    """Contrast: a future-trial (still Pro) user clears the ``can_export`` gate and falls through to
    the summary lookup — 404 'Summary not found', NOT 403. The flip from 403→404 proves the expiry
    (not the route) is what closes the gate."""
    with _as_trial_user(_future()):
        resp = client.get("/api/summaries/filing/999999/export/pdf")

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Summary not found"
