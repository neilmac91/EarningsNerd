"""T3 — summary generation requires an account, enforced AT THE ROUTE (rule #12 gate).

Replaces the retired guest daily-quota anchor (``test_guest_quota_route.py``): anonymous generation
was removed outright, so the machine-enforced rules are now:

  * ``POST /api/summaries/filing/{id}/generate-stream`` returns HTTP 401 for an unauthenticated
    caller — BEFORE any filing lookup, cached short-circuit, or generation runs (the auth
    dependency rejects at the boundary);
  * that includes filings that already HAVE a summary: the cached short-circuit inside
    generate-stream sits behind auth. Anonymous cached reads belong to the public GET;
  * ``GET /api/summaries/filing/{id}`` stays PUBLIC — already-generated summaries remain readable
    logged-out (the deliberate SEO/marketing surface; owner decision 2026-07-09). Gating it would
    be a product regression, so this anchor pins it;
  * an authenticated user is served the SSE stream end-to-end (the required-auth dependency didn't
    break the happy path).

The free-tier monthly cap (5/month via entitlements) is pinned separately in
``test_expired_trial_gating.py`` (in-band SSE paywall error at the cap).

Hermetic: the SEC/XBRL/AI/excerpt boundaries are mocked in ``summary_pipeline``'s namespace via the
shared ``tests.support.summary_stream_harness`` (the ONE seam set the stream anchors + the
frames-regen script also use).
"""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from main import app
from app.database import SessionLocal, engine
from app.models import (
    Base,
    Company,
    Filing,
    Summary,
    SummaryGenerationProgress,
    User,
    UserUsage,
)
from app.routers.auth import get_current_user

GENERATE_URL = "/api/summaries/filing/{fid}/generate-stream"
SUMMARY_URL = "/api/summaries/filing/{fid}"


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def _tables():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _reset_inflight():
    """A leaked in-flight slot would reroute the next generation down the dedup (join) path."""
    from tests.support.summary_stream_harness import reset_inflight

    reset_inflight()
    yield
    reset_inflight()


@pytest.fixture(autouse=True)
def _clear_overrides():
    """Safety net: a leaked get_current_user override would make the anonymous tests see a user
    and silently pass the auth gate. Always clear it after every test."""
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def boundaries():
    """Mock the SEC/XBRL/AI/excerpt seams (in ``summary_pipeline``'s namespace) via the shared
    harness, so a served request runs the real route offline + instantly. ``check_usage_limit`` is
    left patched-open (default) — this file pins the AUTH gate, not the usage gate."""
    from tests.support.summary_stream_harness import stream_boundaries

    with stream_boundaries() as summarize:
        yield summarize


class _Seed:
    """Seeds Company/Filing/Summary/User rows on demand and tears everything down afterward."""

    def __init__(self):
        self.company_ids: list[int] = []
        self.filing_ids: list[int] = []
        self.user_ids: list[int] = []

    def filing(self, *, with_summary: str | None = None) -> int:
        db = SessionLocal()
        try:
            suffix = uuid.uuid4().hex[:10]
            company = Company(cik=f"cik{suffix}", ticker=f"AG{suffix[:4].upper()}", name="Auth Gate Co")
            db.add(company)
            db.commit()
            db.refresh(company)
            filing = Filing(
                company_id=company.id, accession_number=f"acc-{suffix}", filing_type="10-K",
                filing_date=datetime(2026, 1, 15, tzinfo=timezone.utc),
                document_url=f"https://sec.example/{suffix}/d.htm",
                sec_url=f"https://sec.example/{suffix}/",
            )
            db.add(filing)
            db.commit()
            db.refresh(filing)
            if with_summary is not None:
                db.add(Summary(filing_id=filing.id, business_overview=with_summary))
                db.commit()
            self.company_ids.append(company.id)
            self.filing_ids.append(filing.id)
            return filing.id
        finally:
            db.close()

    def user(self) -> int:
        db = SessionLocal()
        try:
            user = User(email=f"ag-{uuid.uuid4().hex}@example.com", hashed_password="x",
                        email_verified=True, is_active=True, is_pro=False)
            db.add(user)
            db.commit()
            db.refresh(user)
            self.user_ids.append(user.id)
            return user.id
        finally:
            db.close()

    def cleanup(self):
        db = SessionLocal()
        try:
            for fid in self.filing_ids:
                db.query(Summary).filter(Summary.filing_id == fid).delete()
                db.query(SummaryGenerationProgress).filter(
                    SummaryGenerationProgress.filing_id == fid
                ).delete()
                db.query(Filing).filter(Filing.id == fid).delete()
            for cid in self.company_ids:
                db.query(Company).filter(Company.id == cid).delete()
            for uid in self.user_ids:
                db.query(UserUsage).filter(UserUsage.user_id == uid).delete()
                db.query(User).filter(User.id == uid).delete()
            db.commit()
        finally:
            db.close()


@pytest.fixture
def seed():
    s = _Seed()
    try:
        yield s
    finally:
        s.cleanup()


def _summary_count(fid: int) -> int:
    db = SessionLocal()
    try:
        return db.query(Summary).filter(Summary.filing_id == fid).count()
    finally:
        db.close()


# ── tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.requires_db
def test_anonymous_generate_stream_is_401(client, seed, boundaries):
    """An unauthenticated POST is rejected at the boundary: 401, Bearer challenge, and no
    generation ran (no Summary row appeared, the mocked AI seam was never called)."""
    fid = seed.filing()

    resp = client.post(GENERATE_URL.format(fid=fid))

    assert resp.status_code == 401, resp.text
    assert "www-authenticate" in {k.lower() for k in resp.headers}
    assert _summary_count(fid) == 0
    boundaries.assert_not_called()


@pytest.mark.requires_db
def test_anonymous_generate_stream_is_401_even_when_summary_cached(client, seed, boundaries):
    """The cached short-circuit inside generate-stream sits BEHIND auth: an anonymous caller gets
    401 even for a filing whose summary already exists. Anonymous cached reads use the public GET
    (pinned below), so this loses guests nothing."""
    fid = seed.filing(with_summary="# Cached\n\nAlready generated.")

    resp = client.post(GENERATE_URL.format(fid=fid))

    assert resp.status_code == 401, resp.text


@pytest.mark.requires_db
def test_cached_summary_stays_publicly_readable(client, seed):
    """Already-generated summaries remain readable WITHOUT an account (SEO/marketing surface).
    Only fresh generation requires signing up — gating this GET is a product regression."""
    fid = seed.filing(with_summary="# Cached\n\nAlready generated.")

    resp = client.get(SUMMARY_URL.format(fid=fid))

    assert resp.status_code == 200, resp.text
    assert resp.json()["business_overview"] == "# Cached\n\nAlready generated."


@pytest.mark.requires_db
def test_authenticated_user_is_served(client, seed, boundaries):
    """A signed-in (Free) user is served the SSE stream end-to-end to its terminal ``complete`` —
    requiring auth didn't break the happy path."""
    uid = seed.user()
    stand_in = SimpleNamespace(id=uid, is_pro=False, subscription=None,
                               email="authed@example.com", is_active=True)
    app.dependency_overrides[get_current_user] = lambda: stand_in

    resp = client.post(GENERATE_URL.format(fid=seed.filing()))

    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert '"type": "complete"' in resp.text  # streamed through to the terminal event
