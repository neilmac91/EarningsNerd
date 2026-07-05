"""T3 — the guest daily-summary cap enforced AT THE ROUTE (not just the service).

``tests/unit/test_security_audit_remediation.py`` already pins the SERVICE
(``guest_quota.check_and_increment_guest_quota`` called directly). What this file pins is that the
user-facing generate endpoint — ``POST /api/summaries/filing/{id}/generate-stream`` — actually WIRES
that cap in for an anonymous client:

  * with ``ENABLE_GUEST_DAILY_QUOTA=true`` an unauthenticated caller is served up to
    ``GUEST_DAILY_SUMMARY_LIMIT`` generations, then the next one is blocked with HTTP 429 and the
    route's quota message (``summaries.py`` raises this at the gate, BEFORE any generation runs);
  * an authenticated user bypasses the cap entirely (the gate is ``if current_user is None``);
  * the cap self-resets on a new UTC day (route-level mirror of the service test).

IMPORTANT enforcement-shape detail this test encodes: the guest gate sits AFTER the "summary already
exists → return cached" early-return. So a *second* request for the SAME filing short-circuits before
the gate and never increments the counter. Each request below therefore targets a DISTINCT freshly
seeded filing, which is how the per-IP counter actually advances in production.

Hermetic: the SEC/XBRL/AI/excerpt boundaries are mocked in ``summary_pipeline``'s namespace exactly as
the committed stream anchors do (``test_summary_stream_contract`` / ``test_stream_latency``), so the
"allowed" requests run the real route + real guest-quota DB writes offline and instantly.
"""
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from main import app
from app.config import settings
from app.database import SessionLocal, engine
from app.models import (
    Base,
    Company,
    Filing,
    GuestDailyUsage,
    Summary,
    SummaryGenerationProgress,
    User,
    UserUsage,
)
from app.routers.auth import get_current_user_optional
from app.services import guest_quota, summary_pipeline

GENERATE_URL = "/api/summaries/filing/{fid}/generate-stream"

# Payload the mocked ``summarize_filing`` returns — a completed summary (copied from the T1 anchor).
_PAYLOAD = {
    "status": "complete",
    "business_overview": "# Summary\n\nAcme Corp designs and sells widgets worldwide.",
    "financial_highlights": {"revenue": "1B", "notes": "Revenue increased 12% year over year."},
    "risk_factors": [{"summary": "Supply-chain risk.", "supporting_evidence": "Item 1A."}],
    "management_discussion": "MD&A covers results of operations and financial condition.",
    "key_changes": "Higher R&D investment.",
    "raw_summary": {
        "sections": {"business_overview": "Acme Corp designs and sells widgets."},
        "section_coverage": {"covered_count": 5, "total_count": 7},
    },
}


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def _tables():
    # The ``with TestClient(app)`` lifespan already runs create_all; this is a defensive belt so the
    # guest_daily_usage table is guaranteed present regardless of lifespan ordering.
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _reset_inflight():
    """A leaked in-flight slot would reroute the next generation down the dedup (join) path."""
    summary_pipeline._inflight_generations.clear()
    yield
    summary_pipeline._inflight_generations.clear()


@pytest.fixture(autouse=True)
def _clear_overrides():
    """Safety net: a leaked get_current_user_optional override would make the anon tests see a user
    and silently skip the guest gate. Always clear it after every test."""
    yield
    app.dependency_overrides.pop(get_current_user_optional, None)


# ── helpers ───────────────────────────────────────────────────────────────────

def _unique_ip() -> str:
    """A unique client-IP token per test.

    ``get_client_ip`` returns the trusted ``X-Forwarded-For`` entry VERBATIM (no IP-format
    validation) and ``guest_quota`` only rejects the literals unknown/""/none — so a unique token
    gives each test its own fresh per-IP quota bucket, keeping the shared file DB hermetic across
    reruns (no leftover row can pre-exhaust the cap).
    """
    return f"guest-ip-{uuid.uuid4().hex}"


def _mock_boundaries(monkeypatch):
    """Mock the generation boundaries so an ALLOWED request runs the real route offline + instantly
    (same seams the committed stream anchors patch)."""
    monkeypatch.setattr(summary_pipeline.sec_edgar_service, "get_filing_document",
                        AsyncMock(return_value="FILING DOCUMENT TEXT " * 40))
    monkeypatch.setattr(summary_pipeline.xbrl_service, "get_xbrl_data", AsyncMock(return_value=None))
    monkeypatch.setattr(summary_pipeline.xbrl_service, "get_filing_sections", AsyncMock(return_value=None))
    monkeypatch.setattr(summary_pipeline, "get_or_cache_excerpt", lambda *a, **k: "EXCERPT")
    monkeypatch.setattr(summary_pipeline, "check_usage_limit", lambda user, session: (True, 0, None))
    monkeypatch.setattr(summary_pipeline.openai_service, "summarize_filing", AsyncMock(return_value=_PAYLOAD))
    # instant fake ⇒ no heartbeat frames ⇒ the stream terminates immediately
    monkeypatch.setattr(summary_pipeline.settings, "STREAM_HEARTBEAT_INTERVAL", 999)


def _enable_guest_cap(monkeypatch, limit: int):
    monkeypatch.setattr(settings, "ENABLE_GUEST_DAILY_QUOTA", True)
    monkeypatch.setattr(settings, "GUEST_DAILY_SUMMARY_LIMIT", limit)
    # Trust the single hop TestClient's X-Forwarded-For represents, so the cap keys on our per-test
    # IP (not the constant "testclient" socket peer) — matching the documented Cloud Run deployment.
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)


def _generate(client, filing_id: int, ip: str, auth: bool = False):
    headers = {"X-Forwarded-For": ip}
    if auth:
        # Any bearer value: the authed path is driven by the get_current_user_optional override, not
        # by real token decode. Present so the request also reads as authenticated on the wire.
        headers["Authorization"] = "Bearer test-token"
    return client.post(GENERATE_URL.format(fid=filing_id), headers=headers)


def _guest_row(ip: str):
    db = SessionLocal()
    try:
        return (
            db.query(GuestDailyUsage)
            .filter(GuestDailyUsage.ip_hash == guest_quota._ip_hash(ip))
            .first()
        )
    finally:
        db.close()


class _Seed:
    """Seeds distinct Company+Filing rows on demand and tears everything down afterward."""

    def __init__(self):
        self.company_ids: list[int] = []
        self.filing_ids: list[int] = []
        self.ips: list[str] = []
        self.user_ids: list[int] = []

    def filing(self) -> int:
        db = SessionLocal()
        try:
            suffix = uuid.uuid4().hex[:10]
            company = Company(cik=f"cik{suffix}", ticker=f"GQ{suffix[:4].upper()}", name="Guest Quota Co")
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
            self.company_ids.append(company.id)
            self.filing_ids.append(filing.id)
            return filing.id
        finally:
            db.close()

    def user(self) -> int:
        db = SessionLocal()
        try:
            user = User(email=f"gq-{uuid.uuid4().hex}@example.com", hashed_password="x",
                        email_verified=True, is_active=True, is_pro=False)
            db.add(user)
            db.commit()
            db.refresh(user)
            self.user_ids.append(user.id)
            return user.id
        finally:
            db.close()

    def note_ip(self, ip: str) -> str:
        self.ips.append(ip)
        return ip

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
            for ip in self.ips:
                db.query(GuestDailyUsage).filter(
                    GuestDailyUsage.ip_hash == guest_quota._ip_hash(ip)
                ).delete()
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


# ── tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.requires_db
def test_guest_served_up_to_limit_then_blocked(client, monkeypatch, seed):
    """Anonymous caller: served ``limit`` generations, then the next is blocked 429 at the route."""
    _mock_boundaries(monkeypatch)
    _enable_guest_cap(monkeypatch, limit=2)
    ip = seed.note_ip(_unique_ip())

    # First two requests (each a DISTINCT filing, so each reaches the gate) are served.
    for _ in range(2):
        resp = _generate(client, seed.filing(), ip)
        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert "complete" in resp.text  # the stream actually ran to a terminal event

    # The third request is over the cap → blocked before any generation runs.
    blocked = _generate(client, seed.filing(), ip)
    assert blocked.status_code == 429
    detail = blocked.json()["detail"]
    assert "today's free limit of 2 summaries" in detail
    assert "free account" in detail
    # Not the sliding-window rate-limiter's message — this is specifically the daily quota gate.
    assert "Too many summary requests" not in detail

    # All three requests incremented the per-IP counter (the blocked one still counted).
    row = _guest_row(ip)
    assert row is not None and row.count == 3


@pytest.mark.requires_db
def test_authenticated_user_bypasses_guest_cap(client, monkeypatch, seed):
    """An authenticated user is served even when that IP's guest bucket is already exhausted."""
    _mock_boundaries(monkeypatch)
    _enable_guest_cap(monkeypatch, limit=1)
    ip = seed.note_ip(_unique_ip())

    # Pre-exhaust the guest bucket for this IP: a GUEST would now be blocked (count already at limit).
    db = SessionLocal()
    try:
        db.add(GuestDailyUsage(ip_hash=guest_quota._ip_hash(ip),
                               usage_date=datetime.now(timezone.utc).date(), count=1))
        db.commit()
    finally:
        db.close()

    # Authenticate: the route's optional-auth dependency returns our stand-in user.
    uid = seed.user()
    stand_in = SimpleNamespace(id=uid, is_pro=False, subscription=None,
                               email="authed@example.com", is_active=True)
    app.dependency_overrides[get_current_user_optional] = lambda: stand_in

    resp = _generate(client, seed.filing(), ip, auth=True)

    assert resp.status_code == 200, resp.text  # served despite the exhausted guest bucket
    assert resp.headers["content-type"].startswith("text/event-stream")
    # The guest gate (if current_user is None) was skipped entirely — the bucket is untouched.
    row = _guest_row(ip)
    assert row is not None and row.count == 1


@pytest.mark.requires_db
def test_guest_cap_resets_on_new_utc_day(client, monkeypatch, seed):
    """Route-level mirror of the service reset test: a blocked IP is served again the next UTC day."""
    _mock_boundaries(monkeypatch)
    _enable_guest_cap(monkeypatch, limit=1)
    ip = seed.note_ip(_unique_ip())

    # Exhaust today's single-summary budget, then confirm the next request is blocked.
    assert _generate(client, seed.filing(), ip).status_code == 200
    assert _generate(client, seed.filing(), ip).status_code == 429

    # Backdate the row to yesterday → the next request is the first hit of a new UTC day.
    db = SessionLocal()
    try:
        row = (
            db.query(GuestDailyUsage)
            .filter(GuestDailyUsage.ip_hash == guest_quota._ip_hash(ip))
            .one()
        )
        row.usage_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()
        db.commit()
    finally:
        db.close()

    # New UTC day → counter resets to 1 → served again.
    assert _generate(client, seed.filing(), ip).status_code == 200
    row = _guest_row(ip)
    assert row is not None and row.count == 1
    assert row.usage_date == datetime.now(timezone.utc).date()
