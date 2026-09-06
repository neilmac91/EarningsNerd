"""E11b-1 durable delivery: state machine, frozen payloads, retries and transport classification.

Runs the real scan/digest services and ``notification_delivery_service`` on a disposable SQLite
database with an injected transport; no SEC, Resend or network. PostgreSQL claim concurrency and
FK cascades live in tests/integration/test_notification_delivery_transactions.py. The locked
filing-scan anchor (tests/unit/test_filing_scan.py) stays byte-identical and covers the
compatibility surface (one alert per watcher, sequential re-run sends nothing).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Base, Company, Filing, NotificationLog, NotificationPreferences, User, Watchlist
from app.models.notification_delivery import (
    KIND_FILING_DIGEST,
    KIND_FILING_REALTIME,
    STATUS_ACCEPTED,
    STATUS_AMBIGUOUS,
    STATUS_CLAIMED,
    STATUS_RETRYABLE,
    STATUS_SENDING,
    STATUS_SUPPRESSED,
    DeliveryBatch,
    DeliveryItem,
)
from app.services import notification_delivery_service as delivery
from app.services import resend_service
from app.services.filing_scan_service import run_daily_digest, run_filing_scan

NOW = datetime(2026, 6, 17, 12, tzinfo=timezone.utc)
WATCH_SINCE = NOW - timedelta(days=10)


@pytest.fixture
def engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def _sec(accession, form, date):
    return {"accession_number": accession, "filing_type": form, "filing_date": date.strftime("%Y-%m-%d"),
            "report_date": None, "document_url": f"https://sec.example/{accession}/doc.htm",
            "sec_url": f"https://sec.example/{accession}/", "cik": "x"}


def _seed(db: Session, *, is_pro: bool, realtime: bool, notify_10q: bool = True) -> tuple[int, int]:
    company = Company(id=1, cik="1", ticker="T1", name="Company One")
    user = User(id=1, email="durable@example.com", hashed_password="x", full_name="Dee", is_active=True, is_pro=is_pro)
    db.add_all([company, user])
    db.flush()
    db.add_all([
        Watchlist(user_id=1, company_id=1, created_at=WATCH_SINCE),
        NotificationPreferences(user_id=1, notify_10q=notify_10q, notify_10k=True, realtime=realtime),
    ])
    db.commit()
    return user.id, company.id


def _batches(db: Session) -> list[DeliveryBatch]:
    db.expire_all()
    return db.query(DeliveryBatch).order_by(DeliveryBatch.id).all()


def _log_count(db: Session) -> int:
    return db.query(NotificationLog).count()


def _watermark(db: Session):
    db.expire_all()
    return db.query(Watchlist).filter_by(user_id=1).one().last_alerted_accession


async def _fetch(*args, **kwargs):
    return [_sec("new-10q", "10-Q", NOW - timedelta(hours=2))]


def _recorder(outcome=None):
    """A transport that records what it was asked to send and the session state at that moment."""
    calls: list[dict] = []

    async def send(prepared):
        calls.append({"key": prepared.idempotency_key, "subject": prepared.subject, "html": prepared.html,
                      "items": [i["filing_id"] for i in prepared.items], "to": prepared.to_email})
        if isinstance(outcome, BaseException):
            raise outcome
        return "email_123"

    send.calls = calls
    return send


# --------------------------------------------------------------------------- persistence + session discipline

@pytest.mark.asyncio
async def test_batch_is_durable_and_sending_is_committed_before_the_provider_call(engine):
    with Session(engine) as db:
        _seed(db, is_pro=True, realtime=True)
        observed = {}

        async def send(prepared):
            # No transaction may be open on the worker's session during the network call, and the
            # dispatch authorisation must already be visible to any other session.
            observed["in_transaction"] = db.in_transaction()
            with Session(engine) as other:
                row = other.get(DeliveryBatch, prepared.batch_id)
                observed["status"] = row.status
                observed["attempts"] = row.attempts
                observed["first_dispatch_at"] = row.first_dispatch_at
                observed["log_rows"] = other.query(NotificationLog).count()
                observed["watermark"] = other.query(Watchlist).one().last_alerted_accession
            return "email_1"

        stats = await run_filing_scan(db, fetch_filings=_fetch, send_alert=None, now=NOW, cadence_minutes=0) \
            if False else await _scan_with_transport(db, send)
        assert observed == {"in_transaction": False, "status": STATUS_SENDING, "attempts": 1,
                            "first_dispatch_at": NOW.replace(tzinfo=None), "log_rows": 0, "watermark": None}
        (batch,) = _batches(db)
        assert batch.status == STATUS_ACCEPTED and batch.provider_email_id == "email_1"
        assert batch.payload_sha256 == delivery.payload_digest(batch.subject, batch.body_html, to_email=batch.to_email, from_email=batch.from_email)
        assert [i.filing_id for i in batch.items] == [db.query(Filing).one().id]
        assert stats["alerts_sent"] == 1 and stats["delivery_accepted"] == 1
        assert _log_count(db) == 1 and _watermark(db) == "new-10q"


async def _scan_with_transport(db, send, *, now=NOW):
    """Drive the real scan with a raw transport (not the legacy keyword sender)."""
    from app.services import filing_scan_service

    original = filing_scan_service._alert_transport
    filing_scan_service._alert_transport = lambda _legacy: send
    try:
        return await run_filing_scan(db, fetch_filings=_fetch, send_alert=None, now=now, cadence_minutes=0)
    finally:
        filing_scan_service._alert_transport = original


# --------------------------------------------------------------------------- retries and identity

@pytest.mark.asyncio
async def test_retry_replays_the_same_key_and_bytes_and_counts_only_on_acceptance(engine, monkeypatch):
    monkeypatch.setattr(settings, "DELIVERY_RETRY_BACKOFF_SECONDS", 300)
    with Session(engine) as db:
        _seed(db, is_pro=True, realtime=True)
        first = _recorder(resend_service.ResendRetryableError("429"))
        stats = await _scan_with_transport(db, first)
        (batch,) = _batches(db)
        assert batch.status == STATUS_RETRYABLE and batch.attempts == 1 and batch.owner_token is None
        assert batch.next_attempt_at.replace(tzinfo=timezone.utc) == NOW + timedelta(seconds=300)
        assert stats["alerts_failed"] == 1 and stats["delivery_retryable"] == 1
        assert _log_count(db) == 0 and _watermark(db) is None  # nothing counted until acceptance

        too_early = _recorder()
        await delivery.drain(db, kind=KIND_FILING_REALTIME, send=too_early, now=NOW + timedelta(seconds=299))
        assert too_early.calls == []  # not due yet

        second = _recorder()
        drained = await delivery.drain(db, kind=KIND_FILING_REALTIME, send=second, now=NOW + timedelta(seconds=300))
        assert drained.accepted == 1
        assert second.calls[0]["key"] == first.calls[0]["key"] == batch.idempotency_key
        assert (second.calls[0]["subject"], second.calls[0]["html"]) == (first.calls[0]["subject"], first.calls[0]["html"])
        (batch,) = _batches(db)
        assert batch.status == STATUS_ACCEPTED and batch.attempts == 2
        assert batch.first_dispatch_at.replace(tzinfo=timezone.utc) == NOW  # anchored on the first attempt
        assert _log_count(db) == 1 and _watermark(db) == "new-10q"


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [resend_service.ResendAmbiguousError("read timeout"), RuntimeError("provider down")])
async def test_ambiguous_outcome_is_never_dispatched_again(engine, error):
    with Session(engine) as db:
        _seed(db, is_pro=True, realtime=True)
        stats = await _scan_with_transport(db, _recorder(error))
        (batch,) = _batches(db)
        assert batch.status == STATUS_AMBIGUOUS and batch.last_error_kind == delivery.ERROR_PROVIDER_AMBIGUOUS
        assert stats["alerts_failed"] == 1 and stats["delivery_ambiguous"] == 1
        later = _recorder()
        await delivery.drain(db, kind=KIND_FILING_REALTIME, send=later, now=NOW + timedelta(days=1))
        assert later.calls == [] and _log_count(db) == 0
        # And the filing stays owned: a re-scan neither re-selects nor re-sends it.
        again = await _scan_with_transport(db, later, now=NOW + timedelta(hours=1))
        assert later.calls == [] and again["alerts_sent"] == 0 and len(_batches(db)) == 1


@pytest.mark.asyncio
async def test_provider_rejection_is_terminal_and_a_failure(engine):
    with Session(engine) as db:
        _seed(db, is_pro=True, realtime=True)
        stats = await _scan_with_transport(db, _recorder(resend_service.ResendPermanentError("422")))
        (batch,) = _batches(db)
        assert batch.status == STATUS_SUPPRESSED and batch.last_error_kind == delivery.ERROR_PROVIDER_REJECTED
        assert stats["alerts_failed"] == 1 and stats["delivery_rejected"] == 1 and _log_count(db) == 0


@pytest.mark.asyncio
async def test_closed_replay_window_and_exhausted_attempts_park_the_batch(engine, monkeypatch):
    monkeypatch.setattr(settings, "DELIVERY_RETRY_BACKOFF_SECONDS", 1)
    monkeypatch.setattr(settings, "DELIVERY_REPLAY_WINDOW_SECONDS", 3600)
    monkeypatch.setattr(settings, "DELIVERY_MAX_ATTEMPTS", 2)
    with Session(engine) as db:
        _seed(db, is_pro=True, realtime=True)
        await _scan_with_transport(db, _recorder(resend_service.ResendRetryableError("503")))
        # Window closed: the due selector parks it before any claim.
        late = _recorder()
        await delivery.drain(db, kind=KIND_FILING_REALTIME, send=late, now=NOW + timedelta(seconds=3600))
        (batch,) = _batches(db)
        assert late.calls == [] and batch.status == STATUS_AMBIGUOUS
        assert batch.last_error_kind == delivery.ERROR_WINDOW_EXPIRED

        # Attempts exhausted: second failure spends the budget, the third drain never sends.
        db.execute(delete(DeliveryBatch))
        db.execute(delete(DeliveryItem))
        db.commit()
        await _scan_with_transport(db, _recorder(resend_service.ResendRetryableError("503")), now=NOW)
        await delivery.drain(db, kind=KIND_FILING_REALTIME, send=_recorder(resend_service.ResendRetryableError("503")),
                             now=NOW + timedelta(seconds=2))
        third = _recorder()
        await delivery.drain(db, kind=KIND_FILING_REALTIME, send=third, now=NOW + timedelta(seconds=10))
        (batch,) = _batches(db)
        assert third.calls == [] and batch.attempts == 2
        assert batch.status == STATUS_AMBIGUOUS and batch.last_error_kind == delivery.ERROR_ATTEMPTS_EXHAUSTED


@pytest.mark.asyncio
async def test_expired_preparation_claim_is_reclaimed_but_expired_sending_lease_is_ambiguous(engine):
    with Session(engine) as db:
        _seed(db, is_pro=True, realtime=True)
        never = _recorder()
        # Persist without dispatching: a worker that died mid-preparation, and one that died mid-send.
        await _scan_with_transport(db, never, now=NOW)  # accepted; make two more batches by hand
        base = _batches(db)[0]
        for i, (status, lease) in enumerate([(STATUS_CLAIMED, NOW - timedelta(seconds=1)), (STATUS_SENDING, NOW - timedelta(seconds=1))]):
            db.add(DeliveryBatch(kind=KIND_FILING_REALTIME, user_id=1, channel="email", subject=base.subject,
                                 to_email=base.to_email, from_email=base.from_email, expected_item_count=1,
                                 body_html=base.body_html, payload_sha256=base.payload_sha256,
                                 idempotency_key=f"k{i}", status=status, owner_token="dead-worker",
                                 lease_expires_at=lease, first_dispatch_at=NOW if status == STATUS_SENDING else None,
                                 attempts=1 if status == STATUS_SENDING else 0, created_at=NOW, updated_at=NOW))
            db.flush()
            db.add(DeliveryItem(batch_id=db.query(DeliveryBatch).order_by(DeliveryBatch.id.desc()).first().id,
                                user_id=1, filing_id=1, channel="email" + str(i), position=0))
        db.commit()
        send = _recorder()
        drained = await delivery.drain(db, kind=KIND_FILING_REALTIME, send=send, now=NOW + timedelta(seconds=5))
        _, claimed, sending = _batches(db)
        assert claimed.status == STATUS_ACCEPTED and [c["key"] for c in send.calls] == ["k0"]  # reclaimed and sent
        assert sending.status == STATUS_AMBIGUOUS and sending.last_error_kind == delivery.ERROR_LEASE_EXPIRED
        assert drained.accepted == 1


def test_stale_owner_cannot_authorize_or_finalize(engine):
    with Session(engine) as db:
        _seed(db, is_pro=True, realtime=True)
        db.add(Filing(id=1, company_id=1, accession_number="a1", filing_type="10-Q", filing_date=NOW,
                      sec_url="https://sec.example/a1/", document_url="https://sec.example/a1/doc.htm"))
        db.commit()
        batch = delivery.create_batch(db, kind=KIND_FILING_REALTIME, user_id=1, subject="s", html="h", filing_ids=[1], now=NOW)
        assert delivery.claim(db, batch.id, "worker-a", NOW) is True
        assert delivery.claim(db, batch.id, "worker-b", NOW) is False          # already claimed
        assert delivery.authorize_send(db, batch.id, "worker-b", NOW) is False  # wrong owner
        assert delivery.authorize_send(db, batch.id, "worker-a", NOW) is True
        assert delivery.finalize_accepted(db, db.get(DeliveryBatch, batch.id), "worker-b", "x", NOW) is False
        assert _log_count(db) == 0
        assert delivery.finalize_accepted(db, db.get(DeliveryBatch, batch.id), "worker-a", "x", NOW) is True
        assert _log_count(db) == 1 and db.get(DeliveryBatch, batch.id).status == STATUS_ACCEPTED


def test_payload_drift_is_detected_before_dispatch(engine):
    with Session(engine) as db:
        _seed(db, is_pro=True, realtime=True)
        db.add(Filing(id=1, company_id=1, accession_number="a1", filing_type="10-Q", filing_date=NOW,
                      sec_url="https://sec.example/a1/", document_url="https://sec.example/a1/doc.htm"))
        db.commit()
        batch = delivery.create_batch(db, kind=KIND_FILING_REALTIME, user_id=1, subject="s", html="h", filing_ids=[1], now=NOW)
        batch.body_html = "edited"
        db.commit()
        send = _recorder()
        import asyncio
        asyncio.run(delivery.drain(db, kind=KIND_FILING_REALTIME, send=send, now=NOW))
        assert send.calls == []
        (batch,) = _batches(db)
        assert batch.status == STATUS_AMBIGUOUS and batch.last_error_kind == delivery.ERROR_PAYLOAD_DRIFT


# --------------------------------------------------------------------------- digest membership + watermark independence

@pytest.mark.asyncio
async def test_digest_membership_and_payload_are_frozen_across_a_retry(engine, monkeypatch):
    monkeypatch.setattr(settings, "DELIVERY_RETRY_BACKOFF_SECONDS", 60)
    with Session(engine) as db:
        _seed(db, is_pro=False, realtime=False)
        db.add_all([Filing(id=i, company_id=1, accession_number=f"d{i}", filing_type="10-Q",
                           filing_date=NOW - timedelta(hours=i), sec_url=f"https://sec.example/d{i}/",
                           document_url=f"https://sec.example/d{i}/doc.htm") for i in (1, 2)])
        db.commit()
        first = AsyncMock(side_effect=resend_service.ResendRetryableError("503"))
        stats = await run_daily_digest(db, send_digest=first, now=NOW)
        assert stats["digests_failed"] == 1 and [i["filing_id"] for i in first.await_args.kwargs["items"]] == [1, 2]
        (batch,) = _batches(db)
        frozen_html = batch.body_html
        # A newer filing lands and the watch's watermark moves on before the retry.
        db.add(Filing(id=3, company_id=1, accession_number="d3", filing_type="10-Q", filing_date=NOW,
                      sec_url="https://sec.example/d3/", document_url="https://sec.example/d3/doc.htm"))
        watch = db.query(Watchlist).one()
        watch.last_alerted_at, watch.last_alerted_accession = NOW, "d3"
        db.commit()
        second = AsyncMock()
        stats = await run_daily_digest(db, send_digest=second, now=NOW + timedelta(seconds=60))
        # The retry replays the frozen membership (not d3), the same bytes, despite the newer watermark.
        assert second.await_count == 1
        assert [i["filing_id"] for i in second.await_args.kwargs["items"]] == [1, 2]
        assert stats["digests_sent"] == 1 and stats["filings_included"] == 2
        batches = _batches(db)
        assert batches[0].status == STATUS_ACCEPTED and batches[0].body_html == frozen_html
        assert _log_count(db) == 2
        # d3 is not part of that batch; a later digest may own it separately.
        assert [i.filing_id for i in batches[0].items] == [1, 2]


# --------------------------------------------------------------------------- eligibility and deletion

@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["preference", "watch_removed", "deactivated"])
async def test_changed_eligibility_suppresses_before_dispatch(engine, change):
    with Session(engine) as db:
        _seed(db, is_pro=True, realtime=True)
        db.add(Filing(id=1, company_id=1, accession_number="a1", filing_type="10-Q", filing_date=NOW,
                      sec_url="https://sec.example/a1/", document_url="https://sec.example/a1/doc.htm"))
        db.commit()
        delivery.create_batch(db, kind=KIND_FILING_REALTIME, user_id=1, subject="s", html="h", filing_ids=[1], now=NOW)
        if change == "preference":
            db.query(NotificationPreferences).one().notify_10q = False
        elif change == "watch_removed":
            db.execute(delete(Watchlist))
        else:
            db.get(User, 1).is_active = False
        db.commit()
        send = _recorder()
        drained = await delivery.drain(db, kind=KIND_FILING_REALTIME, send=send, now=NOW)
        (batch,) = _batches(db)
        assert send.calls == [] and drained.suppressed == 1
        assert batch.status == STATUS_SUPPRESSED and batch.last_error_kind == delivery.ERROR_ELIGIBILITY_CHANGED
        assert _log_count(db) == 0


def test_account_deletion_takes_batches_and_items_with_it(engine):
    with Session(engine) as db:
        _seed(db, is_pro=True, realtime=True)
        db.add(Filing(id=1, company_id=1, accession_number="a1", filing_type="10-Q", filing_date=NOW,
                      sec_url="https://sec.example/a1/", document_url="https://sec.example/a1/doc.htm"))
        db.commit()
        delivery.create_batch(db, kind=KIND_FILING_REALTIME, user_id=1, subject="s", html="h", filing_ids=[1], now=NOW)
        db.delete(db.get(User, 1))  # the ORM deletion DELETE /api/users/me performs
        db.commit()
        assert db.query(DeliveryBatch).count() == 0 and db.query(DeliveryItem).count() == 0


def test_create_batch_refuses_a_filing_another_batch_owns(engine):
    with Session(engine) as db:
        _seed(db, is_pro=True, realtime=True)
        db.add_all([Filing(id=i, company_id=1, accession_number=f"a{i}", filing_type="10-Q", filing_date=NOW,
                           sec_url=f"https://sec.example/a{i}/", document_url=f"https://sec.example/a{i}/doc.htm") for i in (1, 2)])
        db.commit()
        assert delivery.create_batch(db, kind=KIND_FILING_REALTIME, user_id=1, subject="s", html="h", filing_ids=[1], now=NOW)
        assert delivery.create_batch(db, kind=KIND_FILING_DIGEST, user_id=1, subject="s", html="h", filing_ids=[2, 1], now=NOW) is None
        assert db.query(DeliveryBatch).count() == 1 and db.query(DeliveryItem).count() == 1
        assert delivery.already_owned(db, 1, 1) and not delivery.already_owned(db, 1, 2)


# --------------------------------------------------------------------------- transport classification

_REAL_CLIENT = httpx.AsyncClient


def _client_factory(handler):
    def factory(**kwargs):
        return _REAL_CLIENT(transport=httpx.MockTransport(handler), **kwargs)
    return factory


@pytest.mark.asyncio
async def test_transport_sends_the_idempotency_key_and_classifies_outcomes(monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test")
    monkeypatch.setattr(settings, "RESEND_FROM_EMAIL", "EarningsNerd <hello@example.com>")
    seen = {}

    def ok(request):
        seen["key"] = request.headers.get("Idempotency-Key")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "email_1"})

    monkeypatch.setattr(resend_service.httpx, "AsyncClient", _client_factory(ok))
    assert (await resend_service.send_email(["a@example.com"], "s", "<p>h</p>", idempotency_key="key-1"))["id"] == "email_1"
    assert seen["key"] == "key-1" and seen["body"]["subject"] == "s"

    cases = [
        (lambda r: httpx.Response(429, json={"name": "rate_limit_exceeded"}), resend_service.ResendRetryableError),
        (lambda r: httpx.Response(500, json={"name": "server_error"}), resend_service.ResendRetryableError),
        (lambda r: httpx.Response(500, text="boom"), resend_service.ResendAmbiguousError),
        (lambda r: httpx.Response(500, json=[]), resend_service.ResendAmbiguousError),
        (lambda r: httpx.Response(200, json={}), resend_service.ResendAmbiguousError),
        (lambda r: httpx.Response(200, json=[]), resend_service.ResendAmbiguousError),
        (lambda r: httpx.Response(200, json={"id": 1}), resend_service.ResendAmbiguousError),
        (lambda r: httpx.Response(200, json={"id": " "}), resend_service.ResendAmbiguousError),
        (lambda r: httpx.Response(302, json={"id": "email_1"}), resend_service.ResendAmbiguousError),
        (lambda r: httpx.Response(409, json={"name": "concurrent_idempotent_requests"}), resend_service.ResendRetryableError),
        (lambda r: httpx.Response(409, json={"name": "invalid_idempotent_request"}), resend_service.ResendAmbiguousError),
        (lambda r: httpx.Response(422, json={"name": "validation_error"}), resend_service.ResendPermanentError),
        (lambda r: httpx.Response(200, text="not json"), resend_service.ResendAmbiguousError),
        (lambda r: (_ for _ in ()).throw(httpx.ConnectError("refused")), resend_service.ResendRetryableError),
        (lambda r: (_ for _ in ()).throw(httpx.ReadTimeout("slow")), resend_service.ResendAmbiguousError),
        (lambda r: (_ for _ in ()).throw(httpx.RemoteProtocolError("dropped")), resend_service.ResendAmbiguousError),
    ]
    for handler, expected in cases:
        monkeypatch.setattr(resend_service.httpx, "AsyncClient", _client_factory(handler))
        with pytest.raises(expected):
            await resend_service.send_email(["a@example.com"], "s", "h", idempotency_key="key-1")
        assert issubclass(expected, resend_service.ResendError)  # existing callers keep catching the base class


@pytest.mark.asyncio
async def test_delivery_clock_refreshes_between_attempts_and_after_provider(engine, monkeypatch):
    with Session(engine) as db:
        _seed(db, is_pro=True, realtime=True)
        db.add_all([Filing(id=i, company_id=1, accession_number=f"clock{i}", filing_type="10-Q",
                           filing_date=NOW, sec_url=f"https://sec.example/{i}/",
                           document_url=f"https://sec.example/{i}/doc.htm") for i in (1, 2)])
        db.commit()
        for i in (1, 2):
            delivery.create_batch(db, kind=KIND_FILING_REALTIME, user_id=1, subject="s", html="h",
                                  filing_ids=[i], now=NOW)
        current = NOW + timedelta(minutes=5)
        observed = []

        async def send(prepared):
            nonlocal current
            with Session(engine) as other:
                row = other.get(DeliveryBatch, prepared.batch_id)
                observed.append(row.first_dispatch_at.replace(tzinfo=timezone.utc))
                assert row.lease_expires_at.replace(tzinfo=timezone.utc) > current
            current += timedelta(minutes=3)
            return "id"

        result = await delivery.drain(db, kind=KIND_FILING_REALTIME, send=send, clock=lambda: current)
        assert result.accepted == 2
        assert observed == [NOW + timedelta(minutes=5), NOW + timedelta(minutes=8)]
        assert _batches(db)[-1].updated_at.replace(tzinfo=timezone.utc) == current


def test_authorization_requires_live_claim_and_replay_window(engine, monkeypatch):
    monkeypatch.setattr(settings, "DELIVERY_CLAIM_TTL_SECONDS", 60)
    monkeypatch.setattr(settings, "DELIVERY_REPLAY_WINDOW_SECONDS", 3600)
    with Session(engine) as db:
        _seed(db, is_pro=True, realtime=True)
        db.add(Filing(id=1, company_id=1, accession_number="clock", filing_type="10-Q", filing_date=NOW,
                      sec_url="https://sec.example/clock/", document_url="https://sec.example/clock/doc.htm"))
        db.commit()
        batch = delivery.create_batch(db, kind=KIND_FILING_REALTIME, user_id=1, subject="s", html="h", filing_ids=[1], now=NOW)
        assert delivery.claim(db, batch.id, "owner", NOW)
        assert not delivery.authorize_send(db, batch.id, "owner", NOW + timedelta(seconds=60))
        batch = db.get(DeliveryBatch, batch.id)
        batch.first_dispatch_at = NOW - timedelta(seconds=3599)
        db.commit()
        assert not delivery.authorize_send(db, batch.id, "owner", NOW + timedelta(seconds=1))
        assert delivery.authorize_send(db, batch.id, "owner", NOW)


@pytest.mark.asyncio
async def test_retry_freezes_complete_envelope_and_rejects_changed_recipient(engine, monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test")
    monkeypatch.setattr(settings, "RESEND_FROM_EMAIL", "original@example.com")
    requests = []

    def transport(request):
        requests.append((request.headers["Idempotency-Key"], request.content))
        return httpx.Response(429, json={"name": "rate_limit_exceeded"})

    monkeypatch.setattr(resend_service.httpx, "AsyncClient", _client_factory(transport))
    with Session(engine) as db:
        _seed(db, is_pro=True, realtime=True)
        await run_filing_scan(db, fetch_filings=_fetch, now=NOW, cadence_minutes=0)
        monkeypatch.setattr(settings, "RESEND_FROM_EMAIL", "changed@example.com")
        await delivery.drain(db, kind=KIND_FILING_REALTIME, now=NOW + timedelta(minutes=5))
        assert len(requests) == 2 and requests[0] == requests[1]
        db.get(User, 1).email = "changed-recipient@example.com"
        db.commit()
        result = await delivery.drain(db, kind=KIND_FILING_REALTIME, now=NOW + timedelta(minutes=20))
        assert len(requests) == 2 and result.suppressed == 1
        assert _batches(db)[0].last_error_kind == delivery.ERROR_ELIGIBILITY_CHANGED
        assert _log_count(db) == 0 and _watermark(db) is None


@pytest.mark.asyncio
async def test_expired_ambiguity_is_reported_once_for_its_own_kind(engine):
    with Session(engine) as db:
        _seed(db, is_pro=True, realtime=True)
        await _scan_with_transport(db, _recorder(resend_service.ResendRetryableError("429")))
        batch = _batches(db)[0]
        batch.status = STATUS_SENDING
        batch.owner_token = "dead"
        batch.lease_expires_at = NOW
        db.commit()
        other = await delivery.drain(db, kind=KIND_FILING_DIGEST, now=NOW + timedelta(seconds=1))
        assert other.ambiguous == 0 and _batches(db)[0].status == STATUS_SENDING
        result = await _scan_with_transport(db, _recorder(), now=NOW + timedelta(seconds=1))
        assert result["delivery_ambiguous"] == 1 and result["alerts_failed"] == 1
        again = await _scan_with_transport(db, _recorder(), now=NOW + timedelta(seconds=2))
        assert again["delivery_ambiguous"] == 0 and again["alerts_failed"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", [KIND_FILING_REALTIME, KIND_FILING_DIGEST])
async def test_production_entrypoints_do_not_use_selection_time_for_delivery(engine, monkeypatch, kind):
    from app.services import filing_scan_service

    class SelectionDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    monkeypatch.setattr(filing_scan_service, "datetime", SelectionDateTime)
    monkeypatch.setattr(delivery, "utcnow", lambda: NOW + timedelta(minutes=5))
    monkeypatch.setattr(delivery, "send_prepared", _recorder())
    with Session(engine) as db:
        _seed(db, is_pro=True, realtime=True)
        if kind == KIND_FILING_REALTIME:
            await run_filing_scan(db, fetch_filings=_fetch, cadence_minutes=0)
        else:
            db.add(Filing(company_id=1, accession_number="digest-clock", filing_type="10-Q",
                          filing_date=NOW - timedelta(hours=1), sec_url="https://sec.example/d/",
                          document_url="https://sec.example/d/doc.htm"))
            db.commit()
            await run_daily_digest(db)
        batch = _batches(db)[0]
        assert batch.created_at.replace(tzinfo=timezone.utc) == NOW
        assert batch.first_dispatch_at.replace(tzinfo=timezone.utc) == NOW + timedelta(minutes=5)
