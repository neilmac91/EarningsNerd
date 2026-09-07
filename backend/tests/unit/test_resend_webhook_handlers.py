"""The Resend event handlers log the masked recipient plus Resend's ``email_id`` — never the address.

Behavioural companion to the AST gate in ``test_no_raw_email_in_logs.py``: the gate proves no log
call *references* an address expression; this proves what actually lands in the log record.
"""
import asyncio
import logging

import pytest

from app.routers import webhooks


@pytest.fixture(autouse=True)
def _tables():
    # handle_email_clicked resolves the provider id against the delivery ledger (E11c); the
    # hermetic SQLite file needs the schema so an unknown id is a clean miss, not a warning.
    from app.database import Base, engine

    Base.metadata.create_all(bind=engine)

RAW_ADDRESS = "neilmacaogain@example.com"
EMAIL_ID = "em_0123456789"

HANDLERS = [
    webhooks.handle_email_sent,
    webhooks.handle_email_delivered,
    webhooks.handle_email_delayed,
    webhooks.handle_email_bounced,
    webhooks.handle_email_complained,
    webhooks.handle_email_opened,
    webhooks.handle_email_clicked,
]


@pytest.mark.parametrize("handler", HANDLERS, ids=lambda h: h.__name__)
def test_handler_logs_masked_recipient_and_email_id(handler, caplog):
    caplog.set_level(logging.DEBUG, logger="app.routers.webhooks")
    # Resend's ``to`` is a list; the other keys are the superset any handler reads.
    data = {
        "email_id": EMAIL_ID,
        "to": [RAW_ADDRESS],
        "subject": "Your EarningsNerd invite",
        "bounce_type": "hard",
        "link": "https://earningsnerd.io/register",
    }

    asyncio.run(handler(data))

    # Scope to this module's logger: when the root logger is at DEBUG (an earlier test in the
    # suite leaves it there) caplog also captures asyncio's "Using selector" record.
    records = [record for record in caplog.records if record.name == webhooks.logger.name]
    assert len(records) == 1
    message = records[0].getMessage()
    assert RAW_ADDRESS not in caplog.text
    assert "neilmacaogain" not in caplog.text
    assert "n***@example.com" in message
    assert EMAIL_ID in message


def test_handler_tolerates_a_missing_recipient(caplog):
    caplog.set_level(logging.DEBUG, logger="app.routers.webhooks")
    asyncio.run(webhooks.handle_email_delivered({"email_id": EMAIL_ID}))
    records = [record for record in caplog.records if record.name == webhooks.logger.name]
    assert len(records) == 1
    assert "<none>" in records[0].getMessage()
    assert EMAIL_ID in records[0].getMessage()


def _seed_batch(provider_email_id: str, *, kind: str = "alert"):
    import uuid
    from datetime import timedelta

    from app.database import SessionLocal
    from app.models import User
    from app.models.notification_delivery import STATUS_ACCEPTED, DeliveryBatch
    from app.utils.datetimes import utcnow

    now = utcnow()
    with SessionLocal() as db:
        user = User(email=f"click-{uuid.uuid4().hex[:8]}@example.com")
        db.add(user)
        db.flush()
        batch = DeliveryBatch(
            kind=kind, user_id=user.id, channel="email", to_email=RAW_ADDRESS, from_email="alerts@example.com",
            expected_item_count=1, subject="s", body_html="<p>b</p>", payload_sha256="0" * 64,
            idempotency_key=f"key-{provider_email_id}", status=STATUS_ACCEPTED, attempts=1,
            first_dispatch_at=now - timedelta(hours=3), provider_email_id=provider_email_id,
            created_at=now, updated_at=now,
        )
        db.add(batch)
        db.commit()
        return user.id, batch.id


def _first_click(batch_id: int):
    from app.database import SessionLocal
    from app.models.notification_delivery import DeliveryBatch

    with SessionLocal() as db:
        return db.get(DeliveryBatch, batch_id).first_click_at


def test_first_click_on_an_alert_email_is_stamped_once_and_reported_without_the_address(monkeypatch, caplog):
    """E11c: the click webhook is the alert-to-return signal. The first click stamps the batch and
    emits one analytics event keyed by the user id with the alert kind, the batch id, hours since
    dispatch and the link PATH only; a second click (or a webhook retry) changes nothing."""
    caplog.set_level(logging.DEBUG, logger="app.routers.webhooks")
    events: list[tuple] = []
    monkeypatch.setattr("app.services.posthog_client.capture_event", lambda *a, **k: events.append((a, k)))
    user_id, batch_id = _seed_batch("em_click_1")
    data = {"email_id": "em_click_1", "to": [RAW_ADDRESS], "link": "https://www.earningsnerd.io/filing/42?utm=x"}

    asyncio.run(webhooks.handle_email_clicked(data))
    stamped = _first_click(batch_id)
    assert stamped is not None
    assert len(events) == 1
    args, _kwargs = events[0]
    distinct_id, event, props = args
    assert (distinct_id, event) == (str(user_id), "alert_email_clicked")
    assert props["kind"] == "alert" and props["batch_id"] == batch_id and props["link_path"] == "/filing/42"
    assert 2.9 < props["hours_to_first_click"] < 3.1
    assert RAW_ADDRESS not in repr(props) and RAW_ADDRESS not in caplog.text
    assert "Could not record" not in caplog.text

    asyncio.run(webhooks.handle_email_clicked(data))  # retry / second click
    assert _first_click(batch_id) == stamped
    assert len(events) == 1


def test_click_on_unknown_or_blank_email_id_is_a_clean_miss(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG, logger="app.routers.webhooks")
    events: list = []
    monkeypatch.setattr("app.services.posthog_client.capture_event", lambda *a, **k: events.append(a))
    asyncio.run(webhooks.handle_email_clicked({"email_id": "em_unknown", "to": [RAW_ADDRESS], "link": "https://x/y"}))
    asyncio.run(webhooks.handle_email_clicked({"email_id": "  ", "to": [RAW_ADDRESS]}))
    assert events == []
    assert "Could not record" not in caplog.text
