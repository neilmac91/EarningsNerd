"""GET /api/users/export: the GDPR Art. 20 download, characterized over HTTP.

Pins the wire shape (top-level and profile key order, the attachment filename) and that the
``data_exported`` audit row is written only after the payload is built: a build that fails part-way
returns the 500 and leaves no audit row. Every timestamp column the export reads is written as the
instant in UTC with a ``Z`` suffix, or null, whatever representation the database read it in (F19):
SQLite's naive values and the offsets an aware PostgreSQL column carries in a non-UTC session alike,
each nullable column checked both holding a value and holding none, while each array keeps only the
owner's rows, each record its keys in order, and every other field as stored, the stored JSON of a
review's labels and receipt included. The failure is injected inside the request's own session (a
``do_orm_execute`` listener on the billing payments query), not by patching a function, so the test
holds wherever the export code lives.
"""
import re
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

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


# One instant with microseconds and one without, as the database stores them (UTC), and an expiry ahead so the
# attachment stays available.
STAMP = datetime(2026, 7, 6, 10, 52, 35, 123456, tzinfo=timezone.utc)
WHOLE = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
LATER = datetime(2099, 1, 2, 3, 4, 5, 500000, tzinfo=timezone.utc)
STAMP_Z, WHOLE_Z, LATER_Z = "2026-07-06T10:52:35.123456Z", "2026-01-02T03:04:05Z", "2099-01-02T03:04:05.500000Z"
UTC_Z = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d{6})?Z")
# Each record's keys in wire order.
RECORD_KEYS = {
    "searches": ["id", "query", "company_id", "created_at"],
    "saved_summaries": ["id", "summary_id", "notes", "created_at"],
    "watchlist": ["id", "company_id", "created_at"],
    "usage": ["id", "month", "summary_count", "created_at", "updated_at"],
    "billing_payments": [
        "stripe_payment_id", "livemode", "stripe_invoice_id", "source_event_id", "source_api_version", "amount_minor",
        "currency", "payment_type", "paid_at", "observed_at", "subscription_invoice", "user_id", "attribution",
        "stripe_customer_id", "stripe_subscription_id", "is_beta_observed", "invite_cohort_observed", "billing_cycle",
    ],
    "section_reviews": [
        "filing_id", "section", "labels", "engine_version", "completed_at", "receipt", "created_at", "updated_at",
    ],
    "account_agreements": [
        "adult_eligible", "terms_accepted", "terms_version", "eligibility_version", "accepted_at", "source",
    ],
    "feedback": ["id", "type", "message", "page_url", "status", "created_at", "attachments"],
}
ATTACHMENT_KEYS = [
    "id", "content_type", "width", "height", "byte_count", "sha256", "created_at", "expires_at", "status", "download_path",
]
# A completed review's receipt is stored JSON, exported as written: its dates keep the format they were frozen in.
RECEIPT = {"engine": 2, "filing": {"filing_date": "2026-02-15T00:00:00+00:00"}}
# Each account's own values, so a row of the other account in the owner's export is seen.
ACCOUNT_VALUES = {
    "owner": {"month": "2026-07", "count": 3, "section": "risk_factors", "source": "password"},
    "other": {"month": "2026-06", "count": 7, "section": "mdna", "source": "apple"},
}


def _seed_filing(db) -> tuple[int, int, int]:
    """A company, one of its filings and that filing's summary: their ids."""
    digits = str(uuid.uuid4().int)[:10]
    company = Company(cik=digits, ticker="EXPRT", name="Export fixture")
    db.add(company)
    db.flush()
    accession = f"{digits}-26-000001"
    url = build_sec_archive_url(digits, accession)
    filing = Filing(company_id=company.id, accession_number=accession, filing_type="10-K", filing_date=STAMP,
                    document_url=url, sec_url=url)
    db.add(filing)
    db.flush()
    summary = Summary(filing_id=filing.id)
    db.add(summary)
    db.flush()
    return company.id, filing.id, summary.id


def _seed_records(db, user_id: int, ids: tuple[int, int, int], tag: str, *, filled: bool) -> None:
    """One record of each exported kind for ``user_id``; its nullable timestamps hold a value only when ``filled``."""
    company_id, filing_id, summary_id = ids
    values = ACCOUNT_VALUES[tag]
    optional = (lambda value: value) if filled else (lambda value: None)
    db.query(User).filter(User.id == user_id).update({"created_at": STAMP, "updated_at": optional(WHOLE)})
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
        UserUsage(user_id=user_id, month=values["month"], summary_count=values["count"], created_at=STAMP,
                  updated_at=optional(WHOLE)),
        BillingPayment(
            stripe_payment_id=f"pi_{tag}_{uuid.uuid4().hex}", livemode=False, stripe_invoice_id=f"in_{tag}",
            source_event_id=f"evt_{tag}", source_api_version="2026-06-30", amount_minor=1900, currency="usd",
            payment_type="invoice", paid_at=STAMP, observed_at=WHOLE, subscription_invoice=True, user_id=user_id,
            attribution="account", stripe_customer_id=f"cus_{tag}", stripe_subscription_id=f"sub_{tag}",
            is_beta_observed=False, invite_cohort_observed=None, billing_cycle="monthly",
        ),
        SectionReview(
            user_id=user_id, filing_id=filing_id, section=values["section"], labels={"c1": "material"},
            engine_version=2, completed_at=optional(STAMP), receipt=RECEIPT if filled else None, created_at=STAMP,
            updated_at=optional(WHOLE),
        ),
        AccountAgreement(
            user_id=user_id, adult_eligible=True, terms_accepted=True, terms_version="2026-10-23",
            eligibility_version="2026-10-23", accepted_at=WHOLE, source=values["source"],
        ),
        FeedbackAttachment(
            id=attachment_id, submission_id=submission_id, attempt_token=attempt, owner_id=user_id,
            feedback_id=report.id, object_key=f"feedback/{attempt}/{attachment_id}", object_generation="17",
            checksum="b" * 64, content_type="image/png", width=20, height=10, byte_count=100, state="available",
            created_at=STAMP, expires_at=optional(LATER), deletion_due_at=LATER,
        ),
    ])


def _read_with_offset(hours: Optional[int], seen: set):
    """A ``get_db`` whose session hands back every loaded timestamp as an aware value at UTC+``hours``, as an aware
    PostgreSQL column does in a session whose time zone is not UTC (``None``: SQLite's own naive reads). The stored
    instants do not change. ``seen`` collects each (model, column) whose value it read, so the test can tell that the
    representation reached every exported column."""
    zone = timezone(timedelta(hours=hours)) if hours is not None else None

    def represent(session, instance):
        for column in inspect(instance).mapper.columns:
            value = getattr(instance, column.key, None)
            if isinstance(column.type, DateTime) and value is not None:
                seen.add((type(instance).__name__, column.key))
                if zone is not None:
                    set_committed_value(instance, column.key, value.replace(tzinfo=timezone.utc).astimezone(zone))

    def get_offset_db():
        with SessionLocal() as db:
            event.listen(db, "loaded_as_persistent", represent)
            yield db

    return get_offset_db


def _timestamps(node, path: tuple = ()):
    """Every timestamp field of the payload, as (dotted path, value): each key ending in ``_at`` or ``_timestamp``
    outside the stored JSON the export passes through (``labels``, ``receipt``)."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("labels", "receipt"):
                continue
            if key.endswith(("_at", "_timestamp")):
                yield ".".join(path + (key,)), value
            else:
                yield from _timestamps(value, path + (key,))
    elif isinstance(node, list):
        for item in node:
            yield from _timestamps(item, path)


# The (model, column) pairs a filled export reads with a value; the nulls shape reads the same less the nullable ones.
READ_FILLED = {
    ("User", "created_at"), ("User", "updated_at"), ("UserSearch", "created_at"), ("SavedSummary", "created_at"),
    ("Watchlist", "created_at"), ("UserUsage", "created_at"), ("UserUsage", "updated_at"),
    ("BillingPayment", "paid_at"), ("BillingPayment", "observed_at"), ("SectionReview", "completed_at"),
    ("SectionReview", "created_at"), ("SectionReview", "updated_at"), ("AccountAgreement", "accepted_at"),
    ("Feedback", "created_at"), ("FeedbackAttachment", "created_at"), ("FeedbackAttachment", "expires_at"),
}
NULLABLE_READS = {
    ("User", "updated_at"), ("UserUsage", "updated_at"), ("SectionReview", "completed_at"),
    ("SectionReview", "updated_at"), ("FeedbackAttachment", "expires_at"),
}


@pytest.mark.requires_db
@pytest.mark.parametrize("filled", [False, True], ids=["nulls", "filled"])
@pytest.mark.parametrize("read_offset", [None, 2, -5], ids=["naive", "utc+2", "utc-5"])
def test_every_export_timestamp_is_the_instant_in_utc_with_z_and_a_null_stays_null(client, read_offset, filled):
    with _seeded_user() as (other_id, _), _seeded_user() as (uid, _):
        with SessionLocal() as db:
            owner_ids, other_ids = _seed_filing(db), _seed_filing(db)
            _seed_records(db, uid, owner_ids, "owner", filled=filled)
            _seed_records(db, other_id, other_ids, "other", filled=filled)
            db.commit()

        seen: set = set()
        try:
            app.dependency_overrides[get_db] = _read_with_offset(read_offset, seen)
            resp = client.get("/api/users/export")
            assert resp.status_code == 200, resp.text
            payload = resp.json()
            value = (lambda filled_value: filled_value) if filled else (lambda filled_value: None)

            # The representation reached every exported column that holds a value.
            assert READ_FILLED - (set() if filled else NULLABLE_READS) <= seen, sorted(seen)
            # Every timestamp in the payload, whatever section it sits in, is the Z form or null.
            stamps = dict(_timestamps(payload))
            assert all(stamp is None or UTC_Z.fullmatch(stamp) for stamp in stamps.values()), stamps
            assert list(payload) == EXPORT_KEYS and list(payload["profile"]) == PROFILE_KEYS
            for section, keys in RECORD_KEYS.items():
                assert payload[section] and all(list(record) == keys for record in payload[section]), section
            assert (payload["profile"]["created_at"], payload["profile"]["updated_at"]) == (STAMP_Z, value(WHOLE_Z))
            [search] = payload["searches"]
            assert (search["query"], search["company_id"], search["created_at"]) == (
                "search by owner", owner_ids[0], STAMP_Z)
            [saved] = payload["saved_summaries"]
            assert (saved["summary_id"], saved["notes"], saved["created_at"]) == (owner_ids[2], "notes by owner", WHOLE_Z)
            [watched] = payload["watchlist"]
            assert (watched["company_id"], watched["created_at"]) == (owner_ids[0], STAMP_Z)
            [usage] = payload["usage"]
            assert (usage["month"], usage["summary_count"], usage["created_at"], usage["updated_at"]) == (
                "2026-07", 3, STAMP_Z, value(WHOLE_Z))
            [payment] = payload["billing_payments"]
            assert payment["stripe_payment_id"].startswith("pi_owner_")
            assert {key: payment[key] for key in RECORD_KEYS["billing_payments"][1:]} == {
                "livemode": False, "stripe_invoice_id": "in_owner", "source_event_id": "evt_owner",
                "source_api_version": "2026-06-30", "amount_minor": 1900, "currency": "usd", "payment_type": "invoice",
                "paid_at": STAMP_Z, "observed_at": WHOLE_Z, "subscription_invoice": True, "user_id": uid,
                "attribution": "account", "stripe_customer_id": "cus_owner", "stripe_subscription_id": "sub_owner",
                "is_beta_observed": False, "invite_cohort_observed": None, "billing_cycle": "monthly",
            }
            assert payload["section_reviews"] == [{
                "filing_id": owner_ids[1], "section": "risk_factors", "labels": {"c1": "material"}, "engine_version": 2,
                "completed_at": value(STAMP_Z), "receipt": value(RECEIPT), "created_at": STAMP_Z,
                "updated_at": value(WHOLE_Z),
            }]
            assert [(agreement["source"], agreement["accepted_at"]) for agreement in payload["account_agreements"]] == [
                ("password", WHOLE_Z)]
            [report] = payload["feedback"]
            assert (report["message"], report["created_at"]) == ("A report from owner", WHOLE_Z)
            [attachment] = report["attachments"]
            assert list(attachment) == ATTACHMENT_KEYS
            assert (attachment["created_at"], attachment["expires_at"], attachment["status"]) == (
                STAMP_Z, value(LATER_Z), "available")
        finally:
            app.dependency_overrides.pop(get_db, None)
            with SessionLocal() as db:
                owners = (uid, other_id)
                db.query(FeedbackAttachment).filter(FeedbackAttachment.owner_id.in_(owners)).delete()
                db.query(FeedbackSubmission).filter(FeedbackSubmission.owner_id.in_(owners)).delete()
                db.query(Feedback).filter(Feedback.user_id.in_(owners)).delete()
                for model in (SectionReview, BillingPayment, UserUsage, Watchlist, SavedSummary, UserSearch):
                    db.query(model).filter(model.user_id.in_(owners)).delete()
                for company_id, filing_id, summary_id in (owner_ids, other_ids):
                    db.query(Summary).filter(Summary.id == summary_id).delete()
                    db.query(Filing).filter(Filing.id == filing_id).delete()
                    db.query(Company).filter(Company.id == company_id).delete()
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
