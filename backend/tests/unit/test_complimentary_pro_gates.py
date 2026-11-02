"""PB-02 acceptance: a complimentary grant's Pro is the Pro every protected route enforces, and a revoke takes it back.

The Pro source is the real grant: an invited tester who verified their address and confirmed their own signup, granted
by the operator's apply (``complimentary_access_service``), with no Subscription row and no Stripe id. Its Free control
is the same kind of invited tester the manifest does not name, so ``is_beta`` alone gives nothing. Each case drives the
app over HTTP with a real access token (no dependency override), fakes only the AI, SEC and mail boundaries, and asserts
what the route does, not a badge: the sixth summary of the month generates, the fourth Copilot question answers, the
Multi-Period Analysis dataset and its generation run (and meter), the summary PDF and CSV and the analysis workbook
download, real-time and 8-K alerts are kept and an 8-K is delivered, earnings alerts pass the Free cap, saved summaries
work. The revoke case then takes the gates back on the same token, with no Stripe call.
"""
import asyncio
import json
import sys
import types
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models import (
    AccountAgreement, AuditLog, Company, ComplimentaryAccessGrant, Filing, FilingContentCache, InviteCode,
    NotificationLog, NotificationPreferences, SavedSummary, Summary, User, UserUsage, Watchlist,
)
from app.routers import analysis as analysis_router
from app.routers import summaries as summaries_router
from app.routers.auth import create_access_token
from app.services import complimentary_access_service as access
from app.services.complimentary_access_manifest import email_fingerprint, load_manifest
from app.services.entitlements import ANALYSIS_MONTHLY_CAP, FREE_TIER_SUMMARY_LIMIT
from app.services.filing_scan_service import run_filing_scan
from app.services.legal_readiness_service import ELIGIBILITY_VERSION, TERMS_VERSION
from app.services import subscription_service, summary_generation_service, summary_pipeline
from main import app
from tests.support.summary_stream_harness import reset_inflight, seed_company_filing, stream_boundaries

TODAY = datetime.now(timezone.utc).date()  # the apply checks its review window against the UTC day
INVITED = datetime(2030, 5, 1, 12, tzinfo=timezone.utc)
# The filing scan's clock (test_filing_scan.py's): a watch from June 1 sees a June 16 filing on June 17.
SCAN_NOW = datetime(2026, 6, 17, tzinfo=timezone.utc)
WATCH_SINCE = datetime(2026, 6, 1, tzinfo=timezone.utc)
# The usage month every case seeds and every route reads: one the clock never returns, so the seed and the request
# meet in one bucket at any hour, and a reader of the month this module forgot to pin fails at once instead of on the
# 1st (lessons/test-fixture-months-are-never-the-wall-clock-month.md).
MONTH = "2000-01"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _isolated():
    app.dependency_overrides.clear()
    reset_inflight()
    yield
    app.dependency_overrides.clear()
    reset_inflight()


@pytest.fixture(autouse=True)
def _pinned_month(monkeypatch):
    """Every module that reads the month under its own name (``subscription_service.get_current_month``, the one
    clock, imported into each)."""
    from app.routers import subscriptions as subscriptions_router

    for module in (subscription_service, summary_pipeline, summary_generation_service, summaries_router,
                   subscriptions_router, analysis_router):
        monkeypatch.setattr(module, "get_current_month", lambda: MONTH)


def _headers(email: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': email})}"}


def _manifest(action: str, operator_id: int, accounts) -> tuple:
    payload = {"action": action, "cohort": "private-beta-2026-11", "reason": "Private beta tester",
               "operator_account_id": operator_id,
               "accounts": [{"account_id": a.id, "email_sha256": email_fingerprint(a.email)} for a in accounts]}
    if action == "grant":
        payload["review_on"] = (TODAY + timedelta(days=60)).isoformat()
    return load_manifest(json.dumps(payload).encode())


@pytest.fixture
def cohort():
    """An operator, a granted tester and a Free control, all invited; everything naming them is removed after."""
    db = SessionLocal()
    db.query(ComplimentaryAccessGrant).delete(synchronize_session=False)
    db.commit()
    ids: list[int] = []
    companies: list[int] = []

    def account(*, tester: bool, **fields) -> SimpleNamespace:
        email = f"cpro-{uuid.uuid4().hex[:12]}@example.com"
        defaults = {"email_verified": True, "is_active": True, "is_beta": tester, "is_admin": not tester,
                    "hashed_password": "x"}
        user = User(email=email, **{**defaults, **fields})
        db.add(user)
        db.flush()
        if tester:
            db.add(InviteCode(code_hash=uuid.uuid4().hex * 2, cohort="pb02-invites", email=email, user_id=user.id,
                              used_at=INVITED, expires_at=INVITED + timedelta(days=7)))
            db.add(AccountAgreement(user_id=user.id, adult_eligible=True, terms_accepted=True,
                                    terms_version=TERMS_VERSION, eligibility_version=ELIGIBILITY_VERSION,
                                    accepted_at=INVITED, source="password"))
        db.commit()
        ids.append(user.id)
        return SimpleNamespace(id=user.id, email=email, headers=_headers(email))

    operator = account(tester=False)
    granted = account(tester=True, copilot_free_taste_used=3)
    free = account(tester=True, copilot_free_taste_used=3)
    grant = _manifest("grant", operator.id, [granted])
    report = access.apply(db, *grant, confirm_digest=grant[1], today=TODAY)
    assert report.outcomes == {"granted": 1}

    def revoke():
        manifest = _manifest("revoke", operator.id, [granted])
        assert access.apply(db, *manifest, confirm_digest=manifest[1], today=TODAY).outcomes == {"revoked": 1}

    try:
        yield SimpleNamespace(granted=granted, free=free, operator=operator, revoke=revoke, companies=companies)
    finally:
        db.rollback()
        keys = [str(i) for i in ids]
        db.query(AuditLog).filter(AuditLog.entity_id.in_(keys) | AuditLog.user_id.in_(keys)).delete(
            synchronize_session=False)
        for model in (ComplimentaryAccessGrant, InviteCode, AccountAgreement, UserUsage, SavedSummary,
                      NotificationLog, NotificationPreferences, Watchlist):
            db.query(model).filter(model.user_id.in_(ids)).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
        db.close()


def _usage(user_id: int, **counts) -> None:
    with SessionLocal() as db:
        db.add(UserUsage(user_id=user_id, month=MONTH, **counts))
        db.commit()


def _counts(user_id: int) -> SimpleNamespace:
    with SessionLocal() as db:
        row = db.query(UserUsage).filter_by(user_id=user_id, month=MONTH).one_or_none()
        user = db.get(User, user_id)
        return SimpleNamespace(summaries=row.summary_count if row else 0, questions=row.qa_count if row else 0,
                               analyses=row.analysis_count if row else 0, taste=user.copilot_free_taste_used)


def _summarised_filing() -> int:
    """A filing with its content cache and a stored summary, ready to export and to save."""
    filing_id = seed_company_filing()
    with SessionLocal() as db:
        db.add(FilingContentCache(filing_id=filing_id, critical_excerpt="Revenue rose 10% on higher volumes."))
        db.add(Summary(filing_id=filing_id, business_overview="Overview", raw_summary={"sections": {
            "executive_snapshot": {"headline": "Revenue rose 10%.", "key_points": ["Volumes grew"]}}}))
        db.commit()
    return filing_id


def _summary_of(filing_id: int) -> int:
    with SessionLocal() as db:
        return db.query(Summary.id).filter(Summary.filing_id == filing_id).scalar()


# --------------------------------------------------------------------------- plan state


def test_the_plan_reads_pro_in_me_status_and_usage_and_free_for_the_control(cohort, client):
    me = client.get("/api/auth/me", headers=cohort.granted.headers).json()
    status = client.get("/api/subscriptions/subscription", headers=cohort.granted.headers).json()
    usage = client.get("/api/subscriptions/usage", headers=cohort.granted.headers).json()

    assert (me["is_pro"], me["is_beta"]) == (True, True)
    assert status == {"is_pro": True, "plan": "pro", "complimentary": True, "status": None,
                      "subscription_status": None, "stripe_customer_id": None, "stripe_subscription_id": None,
                      "trial_end": None, "current_period_end": None, "cancel_at_period_end": False}
    assert (usage["is_pro"], usage["summaries_limit"], usage["copilot_free_taste_total"]) == (True, None, 0)
    assert usage["analysis_limit"] == ANALYSIS_MONTHLY_CAP

    me = client.get("/api/auth/me", headers=cohort.free.headers).json()
    status = client.get("/api/subscriptions/subscription", headers=cohort.free.headers).json()
    usage = client.get("/api/subscriptions/usage", headers=cohort.free.headers).json()
    assert (me["is_pro"], me["is_beta"]) == (False, True)
    assert (status["plan"], status["complimentary"]) == ("free", False)
    assert (usage["summaries_limit"], usage["copilot_free_taste_total"]) == (FREE_TIER_SUMMARY_LIMIT, 3)


# --------------------------------------------------------------------------- summaries and the Copilot


def test_the_sixth_summary_of_the_month_generates_for_the_grant(cohort, client):
    for tester in (cohort.granted, cohort.free):
        _usage(tester.id, summary_count=FREE_TIER_SUMMARY_LIMIT)
    granted_filing, free_filing = seed_company_filing(), seed_company_filing()

    with stream_boundaries(patch_usage_limit=False) as summarize:
        granted = client.post(f"/api/summaries/filing/{granted_filing}/generate-stream", headers=cohort.granted.headers)
        free = client.post(f"/api/summaries/filing/{free_filing}/generate-stream", headers=cohort.free.headers)

    assert granted.status_code == 200 and '"type": "complete"' in granted.text, granted.text
    assert summarize.await_count == 1  # the grant's summary was generated; the control's never reached the model
    assert _counts(cohort.granted.id).summaries == FREE_TIER_SUMMARY_LIMIT + 1
    assert free.status_code == 200 and '"type": "error"' in free.text
    assert f"{FREE_TIER_SUMMARY_LIMIT} free summaries" in free.text and '"type": "complete"' not in free.text


async def _answer(*, filing, question, history=None):
    yield {"type": "complete", "answer": "ok", "citations": [], "grounded": 0, "kind": "answer"}


def test_the_fourth_copilot_question_answers_for_the_grant(cohort, client, monkeypatch):
    # Both testers spent the Free allowance's three questions before; the grant's Pro never reads it.
    monkeypatch.setattr(summaries_router, "answer_filing_question", _answer)
    filing_id = _summarised_filing()

    granted = client.post(f"/api/summaries/filing/{filing_id}/ask-stream", json={"question": "What changed?"},
                          headers=cohort.granted.headers)
    free = client.post(f"/api/summaries/filing/{filing_id}/ask-stream", json={"question": "What changed?"},
                       headers=cohort.free.headers)

    assert granted.status_code == 200 and '"type": "complete"' in granted.text, granted.text
    assert (_counts(cohort.granted.id).questions, _counts(cohort.granted.id).taste) == (1, 3)
    assert free.status_code == 403 and "You've used your 3 free questions" in free.json()["detail"]


# --------------------------------------------------------------------------- Multi-Period Analysis


@contextmanager
def _analysis_company(cohort):
    suffix = uuid.uuid4().hex[:6].upper()
    with SessionLocal() as db:
        company = Company(cik=f"cpro{suffix}", ticker=f"CP{suffix}", name="Complimentary Co")
        db.add(company)
        db.commit()
        ticker, company_id = company.ticker, company.id
    try:
        yield ticker
    finally:
        with SessionLocal() as db:
            db.query(Company).filter(Company.id == company_id).delete(synchronize_session=False)
            db.commit()


def _analysis_boundaries(monkeypatch):
    dataset = {"period_key": "FY2022..FY2024", "rows": []}

    async def narrative(**_kwargs):
        yield {"type": "complete", "kind": "analysis", "cached": False, "usage": {}}

    monkeypatch.setattr(analysis_router.trend_analysis_service, "build_dataset", lambda *a, **k: dataset)
    monkeypatch.setattr(analysis_router.trend_analysis_service, "stream_trend_narrative", narrative)
    monkeypatch.setattr(analysis_router.trend_analysis_service, "has_cached_analysis", lambda *a, **k: False)
    monkeypatch.setattr(analysis_router, "_emit_analysis_cost_best_effort", lambda *a, **k: None)


def test_multi_period_analysis_builds_its_dataset_and_generates_for_the_grant(cohort, client, monkeypatch):
    _analysis_boundaries(monkeypatch)
    body = {"mode": "annual", "start_period": "FY2022", "end_period": "FY2024"}
    with _analysis_company(cohort) as ticker:
        dataset = client.post(f"/api/analysis/{ticker}/dataset", json=body, headers=cohort.granted.headers)
        stream = client.post(f"/api/analysis/{ticker}/stream", json=body, headers=cohort.granted.headers)
        refused = [client.post(f"/api/analysis/{ticker}/{route}", json=body, headers=cohort.free.headers)
                   for route in ("dataset", "stream")]

    assert dataset.status_code == 200 and dataset.json()["period_key"] == "FY2022..FY2024"
    assert stream.status_code == 200 and '"kind": "analysis"' in stream.text, stream.text
    assert _counts(cohort.granted.id).analyses == 1  # a fresh generation meters once, against the Pro cap
    for response in refused:
        assert response.status_code == 403 and "Multi-Period Analysis is a Pro feature" in response.json()["detail"]


# --------------------------------------------------------------------------- exports


def _fake_weasyprint(monkeypatch) -> None:
    """WeasyPrint's HTML(string=...).write_pdf() as a stub, so the export's own HTML build runs offline and fast."""
    module = types.ModuleType("weasyprint")

    class HTML:
        def __init__(self, *, string: str) -> None:
            self.markup = string

        def write_pdf(self, **_options) -> bytes:
            return b"%PDF-test"

    module.HTML = HTML
    monkeypatch.setitem(sys.modules, "weasyprint", module)


def test_the_pdf_csv_and_excel_exports_download_for_the_grant(cohort, client, monkeypatch):
    _fake_weasyprint(monkeypatch)
    _analysis_boundaries(monkeypatch)
    from app.services import excel_export_service

    monkeypatch.setattr(excel_export_service, "build_analysis_workbook", lambda dataset: b"PK-workbook")
    filing_id = _summarised_filing()
    body = {"mode": "annual", "start_period": "FY2022", "end_period": "FY2024"}

    with _analysis_company(cohort) as ticker:
        for tester, allowed in ((cohort.granted, True), (cohort.free, False)):
            pdf = client.get(f"/api/summaries/filing/{filing_id}/export/pdf", headers=tester.headers)
            csv = client.get(f"/api/summaries/filing/{filing_id}/export/csv", headers=tester.headers)
            xlsx = client.post(f"/api/analysis/{ticker}/export/xlsx", json=body, headers=tester.headers)
            analysis_pdf = client.get("/api/analysis/export/999999999/pdf", headers=tester.headers)
            if allowed:
                assert pdf.status_code == 200 and pdf.content == b"%PDF-test", pdf.text
                assert csv.status_code == 200 and "Revenue rose 10%" in csv.text, csv.text
                assert xlsx.status_code == 200 and xlsx.content == b"PK-workbook", xlsx.text
                # Past the gate: the analysis PDF route looks the analysis up (an unknown id).
                assert analysis_pdf.status_code == 404
            else:
                for refused in (pdf, csv, xlsx, analysis_pdf):
                    assert refused.status_code == 403, refused.text


# --------------------------------------------------------------------------- alerts and saved summaries


def test_realtime_and_8k_alerts_are_kept_and_an_8k_is_delivered_for_the_grant(cohort, client):
    wanted = {"realtime": True, "notify_8k": True}
    granted = client.put("/api/users/me/notification-preferences", json=wanted, headers=cohort.granted.headers)
    free = client.put("/api/users/me/notification-preferences", json=wanted, headers=cohort.free.headers)
    assert granted.status_code == 200 and (granted.json()["realtime"], granted.json()["notify_8k"]) == (True, True)
    assert free.status_code == 200 and (free.json()["realtime"], free.json()["notify_8k"]) == (False, False)

    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        company = Company(cik=f"cik{suffix}", ticker=f"S{suffix[:4].upper()}", name=f"Scan {suffix}")
        db.add(company)
        db.commit()
        company_id = company.id
        for tester in (cohort.granted, cohort.free):
            db.add(Watchlist(user_id=tester.id, company_id=company_id, created_at=WATCH_SINCE))
            # The control's stored choice as a Free account would hold it had it opted in before: the scan still
            # reads the plan at delivery.
            db.query(NotificationPreferences).filter_by(user_id=tester.id).update(wanted)
        db.commit()
    eightk = {"accession_number": f"acc-{suffix}", "filing_type": "8-K", "filing_date": "2026-06-16",
              "report_date": None, "document_url": f"https://sec.example/{suffix}/doc.htm",
              "sec_url": f"https://sec.example/{suffix}/", "cik": "x"}

    async def fetch(cik, filing_types=None, limit=None):
        return [eightk]

    send = AsyncMock()
    try:
        with SessionLocal() as db:
            asyncio.run(run_filing_scan(db, fetch_filings=fetch, send_alert=send, now=SCAN_NOW, cadence_minutes=0))
        # One real-time 8-K alert, to the grant's address: the plan read at delivery keeps the control's choices inert.
        assert [(call.kwargs["to_email"], call.kwargs["filing_type"]) for call in send.await_args_list] == [
            (cohort.granted.email, "8-K")]
    finally:
        with SessionLocal() as db:
            db.query(Filing).filter(Filing.company_id == company_id).delete(synchronize_session=False)
            db.query(Watchlist).filter(Watchlist.company_id == company_id).delete(synchronize_session=False)
            db.query(Company).filter(Company.id == company_id).delete(synchronize_session=False)
            db.commit()


def test_earnings_alerts_pass_the_free_cap_for_the_grant(cohort, client):
    suffix = uuid.uuid4().hex[:5].upper()
    tickers = [f"E{n}{suffix}" for n in range(4)]
    with SessionLocal() as db:
        for ticker in tickers:
            db.add(Company(cik=f"cpro-ea-{ticker}", ticker=ticker, name=f"{ticker} Inc"))
        db.commit()
    try:
        granted = [client.post(f"/api/watchlist/{t}/earnings-alert", headers=cohort.granted.headers) for t in tickers]
        free = [client.post(f"/api/watchlist/{t}/earnings-alert", headers=cohort.free.headers) for t in tickers]
        assert [r.status_code for r in granted] == [200, 200, 200, 200]
        assert [r.status_code for r in free] == [200, 200, 200, 403]
        assert free[3].json().get("code") == "earnings_alert_limit"
    finally:
        with SessionLocal() as db:
            company_ids = [row.id for row in db.query(Company.id).filter(Company.ticker.in_(tickers))]
            db.query(Watchlist).filter(Watchlist.company_id.in_(company_ids)).delete(synchronize_session=False)
            db.query(Company).filter(Company.id.in_(company_ids)).delete(synchronize_session=False)
            db.commit()


def test_saved_summaries_work_for_the_grant(cohort, client):
    summary_id = _summary_of(_summarised_filing())

    saved = client.post("/api/saved-summaries", json={"summary_id": summary_id}, headers=cohort.granted.headers)
    listed = client.get("/api/saved-summaries", headers=cohort.granted.headers)

    assert saved.status_code == 200, saved.text
    assert listed.status_code == 200 and [row["summary_id"] for row in listed.json()] == [summary_id]


# --------------------------------------------------------------------------- revoke


def test_a_revoke_takes_each_gate_back_on_the_same_token(cohort, client, monkeypatch):
    monkeypatch.setattr(summaries_router, "answer_filing_question", _answer)
    _analysis_boundaries(monkeypatch)
    filing_id = _summarised_filing()
    headers = cohort.granted.headers
    assert client.get(f"/api/summaries/filing/{filing_id}/export/csv", headers=headers).status_code == 200

    cohort.revoke()

    status = client.get("/api/subscriptions/subscription", headers=headers).json()
    usage = client.get("/api/subscriptions/usage", headers=headers).json()
    assert (status["plan"], status["is_pro"], status["complimentary"]) == ("free", False, False)
    assert (usage["summaries_limit"], usage["copilot_free_taste_total"]) == (FREE_TIER_SUMMARY_LIMIT, 3)
    assert client.get("/api/auth/me", headers=headers).json()["is_pro"] is False
    assert client.get(f"/api/summaries/filing/{filing_id}/export/csv", headers=headers).status_code == 403
    ask = client.post(f"/api/summaries/filing/{filing_id}/ask-stream", json={"question": "Again?"}, headers=headers)
    assert ask.status_code == 403  # the Free allowance it spent before the grant is spent still
    with _analysis_company(cohort) as ticker:
        body = {"mode": "annual", "start_period": "FY2022", "end_period": "FY2024"}
        assert client.post(f"/api/analysis/{ticker}/dataset", json=body, headers=headers).status_code == 403
