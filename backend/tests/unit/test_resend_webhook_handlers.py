"""The Resend event handlers log the masked recipient plus Resend's ``email_id`` — never the address.

Behavioural companion to the AST gate in ``test_no_raw_email_in_logs.py``: the gate proves no log
call *references* an address expression; this proves what actually lands in the log record.
"""
import asyncio
import logging

import pytest

from app.routers import webhooks

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
