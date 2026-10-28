"""GET /api/users/export: the GDPR Art. 20 download, characterized over HTTP.

Pins the wire shape (top-level and profile key order, the attachment filename) and that the
``data_exported`` audit row is written only after the payload is built: a build that fails part-way
returns the 500 and leaves no audit row. Every timestamp is the instant in UTC with a ``Z`` suffix, or
null, whatever representation the database read it in (F19): SQLite's naive values and the offsets an
aware PostgreSQL column carries in a non-UTC session alike, while each array keeps only the owner's rows
and every other field as stored. The failure is injected inside the request's own session
(a ``do_orm_execute`` listener on the last query of the build), not by patching a function, so the
test holds wherever the export code lives.
"""
import re
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import DateTime, event, inspect
from sqlalchemy.orm.attributes import set_committed_value

from main import app
from app.database import SessionLocal, get_db
from app.models import (
    AccountAgreement, AuditLog, BillingPayment, Company, Filing, SavedSummary, SectionReview, Summary, User,
    UserSearch, UserUsage, Watchlist,
)
from app.models.feedback import Feedback, FeedbackAttachment, FeedbackSubmission
from app.routers.auth import get_current_user
from app.utils.sec_urls import build_sec_archive_url

EXPORT_KEYS = [
    "profile", "searches", "saved_summaries", "watchlist", "usage", "billing_payments",
    "section_reviews", "account_agreements", "feedback", "export_timestamp",
]
PROFILE_KEYS = [
    "user_id", "email", "full_name", "is_active", "is_pro", "stripe_customer_id",
    "stripe_subscription_id", "created_at", "updated_at",
]
FAILED_DETAIL = "We could not export your data. Try again in a moment."


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@contextmanager
def _seeded_user():
    """A real user row, authenticated through the request's own ``get_db`` session."""
    email = f"export-{uuid.uuid4().hex}@example.com"
    db = SessionLocal()
    user = User(email=email, hashed_password=None, full_name="Export Owner",
                email_verified=True, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    uid = user.id
    db.close()

    def _fetch_current_user(db=Depends(get_db)):
        return db.query(User).filter(User.id == uid).first()

    app.dependency_overrides[get_current_user] = _fetch_current_user
    try:
        yield uid, email
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)
        db = SessionLocal()
        db.query(AuditLog).filter(AuditLog.user_email == email).delete()
        db.query(AccountAgreement).filter(AccountAgreement.user_id == uid).delete()
        db.query(User).filter(User.id == uid).delete()
        db.commit()
        db.close()


def _audit_rows(email: str) -> list[tuple[str, str, str]]:
    db = SessionLocal()
    try:
        rows = db.query(AuditLog).filter(AuditLog.user_email == email).order_by(AuditLog.id).all()
        return [(row.action, row.entity_id, row.status) for row in rows]
    finally:
        db.close()


@pytest.mark.requires_db
def test_export_key_order_filename_and_audit_row(client):
    with _seeded_user() as (uid, email):
        resp = client.get("/api/users/export")

        assert resp.status_code == 200
        assert re.fullmatch(
            rf'attachment; filename="earningsnerd_data_export_{uid}_\d{{8}}_\d{{6}}\.json"',
            resp.headers["content-disposition"],
        )
        payload = resp.json()
        assert list(payload) == EXPORT_KEYS
        assert list(payload["profile"]) == PROFILE_KEYS
        assert payload["profile"]["user_id"] == uid
        assert payload["profile"]["email"] == email
        assert payload["profile"]["full_name"] == "Export Owner"
        for key in ("searches", "saved_summaries", "watchlist", "usage", "billing_payments", "section_reviews", "account_agreements", "feedback"):
            assert payload[key] == []
        assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d{6})?Z", payload["export_timestamp"])
        assert datetime.fromisoformat(payload["export_timestamp"]).utcoffset() == timedelta(0)
        assert _audit_rows(email) == [("data_exported", str(uid), "success")]


# One instant with microseconds and one without, as the database stores them (UTC).
STAMP = datetime(2026, 7, 6, 10, 52, 35, 123456, tzinfo=timezone.utc)
WHOLE = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
STAMP_Z, WHOLE_Z = "2026-07-06T10:52:35.123456Z", "2026-01-02T03:04:05Z"


def _seed_records(db, user_id: int, company_id: int, filing_id: int, summary_id: int, tag: str) -> None:
    """One record of each exported kind for ``user_id``, its nullable timestamps left null where the column allows."""
    db.query(User).filter(User.id == user_id).update({"created_at": STAMP, "updated_at": None})
    report = Feedback(user_id=user_id, message=f"A report from {tag}", created_at=WHOLE)
    db.add(report)
    db.flush()
    submission_id, attempt, attachment_id = (str(uuid.uuid4()) for _ in range(3))
    db.add(FeedbackSubmission(
        id=submission_id, owner_id=user_id, submission_key=str(uuid.uuid4()), fingerprint="a" * 64,
        state="submitted", attempt_token=attempt, lease_expires_at=STAMP, feedback_id=report.id,
        created_at=STAMP, updated_at=STAMP,
    ))
    db.flush()
    db.add_all([
        UserSearch(user_id=user_id, query=f"search by {tag}", company_id=company_id, created_at=STAMP),
        SavedSummary(user_id=user_id, summary_id=summary_id, notes=f"notes by {tag}", created_at=WHOLE),
        Watchlist(user_id=user_id, company_id=company_id, created_at=STAMP),
        UserUsage(user_id=user_id, month="2026-07", summary_count=3, created_at=STAMP, updated_at=None),
        BillingPayment(
            stripe_payment_id=f"pi_{tag}_{uuid.uuid4().hex}", livemode=False, stripe_invoice_id=f"in_{tag}",
            source_event_id=f"evt_{tag}", source_api_version="2026-06-30", amount_minor=1900, currency="usd",
            payment_type="invoice", paid_at=STAMP, observed_at=WHOLE, subscription_invoice=True, user_id=user_id,
            attribution="account", stripe_customer_id=f"cus_{tag}", stripe_subscription_id=f"sub_{tag}",
            is_beta_observed=False, invite_cohort_observed=None, billing_cycle="monthly",
        ),
        SectionReview(
            user_id=user_id, filing_id=filing_id, section="risk_factors", labels={"c1": "material"},
            engine_version=2, completed_at=None, receipt={"engine": 2}, created_at=STAMP, updated_at=None,
        ),
        AccountAgreement(
            user_id=user_id, adult_eligible=True, terms_accepted=True, terms_version="2026-10-23",
            eligibility_version="2026-10-23", accepted_at=WHOLE, source="password",
        ),
        FeedbackAttachment(
            id=attachment_id, submission_id=submission_id, attempt_token=attempt, owner_id=user_id,
            feedback_id=report.id, object_key=f"feedback/{attempt}/{attachment_id}", object_generation="17",
            checksum="b" * 64, content_type="image/png", width=20, height=10, byte_count=100, state="available",
            created_at=STAMP, expires_at=None, deletion_due_at=STAMP,
        ),
    ])


def _read_with_offset(hours: int):
    """A ``get_db`` whose session hands back every loaded timestamp as an aware value at UTC+``hours``, as an aware
    PostgreSQL column does in a session whose time zone is not UTC. The stored instants do not change."""
    zone = timezone(timedelta(hours=hours))

    def represent(session, instance):
        for column in inspect(instance).mapper.columns:
            value = getattr(instance, column.key, None)
            if isinstance(column.type, DateTime) and value is not None:
                set_committed_value(instance, column.key, value.replace(tzinfo=timezone.utc).astimezone(zone))

    def get_offset_db():
        with SessionLocal() as db:
            event.listen(db, "loaded_as_persistent", represent)
            yield db

    return get_offset_db


@pytest.mark.requires_db
@pytest.mark.parametrize("read_offset", [None, 2, -5], ids=["naive", "utc+2", "utc-5"])
def test_every_export_timestamp_is_the_instant_in_utc_with_z_and_a_null_stays_null(client, read_offset):
    with _seeded_user() as (other_id, _), _seeded_user() as (uid, _):
        with SessionLocal() as db:
            digits = str(uuid.uuid4().int)[:10]
            company = Company(cik=digits, ticker="EXPRT", name="Export fixture")
            db.add(company)
            db.flush()
            accession = f"{digits}-26-000001"
            filing = Filing(
                company_id=company.id, accession_number=accession, filing_type="10-K", filing_date=STAMP,
                document_url=build_sec_archive_url(digits, accession), sec_url=build_sec_archive_url(digits, accession),
            )
            db.add(filing)
            db.flush()
            summary = Summary(filing_id=filing.id)
            db.add(summary)
            db.flush()
            ids = (company.id, filing.id, summary.id)
            for user_id, tag in ((uid, "owner"), (other_id, "other")):
                _seed_records(db, user_id, *ids, tag)
            db.commit()

        try:
            if read_offset is not None:
                app.dependency_overrides[get_db] = _read_with_offset(read_offset)
            resp = client.get("/api/users/export")
            assert resp.status_code == 200, resp.text
            payload = resp.json()

            assert list(payload) == EXPORT_KEYS and list(payload["profile"]) == PROFILE_KEYS
            assert (payload["profile"]["created_at"], payload["profile"]["updated_at"]) == (STAMP_Z, None)
            [search] = payload["searches"]
            assert (search["query"], search["created_at"]) == ("search by owner", STAMP_Z)
            [saved] = payload["saved_summaries"]
            assert (saved["summary_id"], saved["notes"], saved["created_at"]) == (ids[2], "notes by owner", WHOLE_Z)
            [watched] = payload["watchlist"]
            assert (watched["company_id"], watched["created_at"]) == (ids[0], STAMP_Z)
            [usage] = payload["usage"]
            assert (usage["summary_count"], usage["created_at"], usage["updated_at"]) == (3, STAMP_Z, None)
            [payment] = payload["billing_payments"]
            assert payment["stripe_payment_id"].startswith("pi_owner_")
            assert {key: payment[key] for key in (
                "livemode", "stripe_invoice_id", "source_event_id", "source_api_version", "amount_minor", "currency",
                "payment_type", "paid_at", "observed_at", "subscription_invoice", "user_id", "attribution",
                "stripe_customer_id", "stripe_subscription_id", "is_beta_observed", "invite_cohort_observed",
                "billing_cycle",
            )} == {
                "livemode": False, "stripe_invoice_id": "in_owner", "source_event_id": "evt_owner",
                "source_api_version": "2026-06-30", "amount_minor": 1900, "currency": "usd", "payment_type": "invoice",
                "paid_at": STAMP_Z, "observed_at": WHOLE_Z, "subscription_invoice": True, "user_id": uid,
                "attribution": "account", "stripe_customer_id": "cus_owner", "stripe_subscription_id": "sub_owner",
                "is_beta_observed": False, "invite_cohort_observed": None, "billing_cycle": "monthly",
            }
            assert payload["section_reviews"] == [{
                "filing_id": ids[1], "section": "risk_factors", "labels": {"c1": "material"}, "engine_version": 2,
                "completed_at": None, "receipt": {"engine": 2}, "created_at": STAMP_Z, "updated_at": None,
            }]
            assert [(agreement["source"], agreement["accepted_at"]) for agreement in payload["account_agreements"]] == [
                ("password", WHOLE_Z)]
            [report] = payload["feedback"]
            assert (report["message"], report["created_at"]) == ("A report from owner", WHOLE_Z)
            [attachment] = report["attachments"]
            assert (attachment["created_at"], attachment["expires_at"]) == (STAMP_Z, None)
        finally:
            app.dependency_overrides.pop(get_db, None)
            with SessionLocal() as db:
                owners = (uid, other_id)
                db.query(FeedbackAttachment).filter(FeedbackAttachment.owner_id.in_(owners)).delete()
                db.query(FeedbackSubmission).filter(FeedbackSubmission.owner_id.in_(owners)).delete()
                db.query(Feedback).filter(Feedback.user_id.in_(owners)).delete()
                for model in (SectionReview, BillingPayment, UserUsage, Watchlist, SavedSummary, UserSearch):
                    db.query(model).filter(model.user_id.in_(owners)).delete()
                db.query(Summary).filter(Summary.id == ids[2]).delete()
                db.query(Filing).filter(Filing.id == ids[1]).delete()
                db.query(Company).filter(Company.id == ids[0]).delete()
                db.commit()


@pytest.mark.requires_db
def test_export_includes_only_the_owners_recorded_agreement(client):
    accepted_at = datetime(2026, 10, 23, 12, 34, 56, tzinfo=timezone.utc)
    with _seeded_user() as (other_id, _):
        with _seeded_user() as (uid, _):
            with SessionLocal() as db:
                for user_id, source in ((uid, "password"), (other_id, "apple")):
                    db.add(AccountAgreement(
                        user_id=user_id, adult_eligible=True, terms_accepted=True,
                        terms_version="2026-10-23", eligibility_version="2026-10-23",
                        accepted_at=accepted_at, source=source,
                    ))
                db.commit()

            response = client.get("/api/users/export")

            assert response.status_code == 200
            assert response.json()["account_agreements"] == [{
                "adult_eligible": True, "terms_accepted": True,
                "terms_version": "2026-10-23", "eligibility_version": "2026-10-23",
                "accepted_at": "2026-10-23T12:34:56Z", "source": "password",
            }]


@pytest.mark.requires_db
def test_failed_export_build_returns_500_and_writes_no_audit_row(client):
    with _seeded_user() as (uid, email):
        refused: list[str] = []

        def _refuse_payments_query(orm_execute_state):
            mapper = orm_execute_state.bind_mapper
            if orm_execute_state.is_select and mapper is not None and mapper.class_ is BillingPayment:
                refused.append("billing_payments")
                raise RuntimeError("injected export-build failure")

        def _failing_db():
            db = SessionLocal()
            event.listen(db, "do_orm_execute", _refuse_payments_query)
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _failing_db
        resp = client.get("/api/users/export")

        assert refused == ["billing_payments"]
        assert resp.status_code == 500
        assert resp.json() == {"detail": FAILED_DETAIL}
        assert "content-disposition" not in resp.headers
        assert _audit_rows(email) == []
