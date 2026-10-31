"""The Resend webhook verifies a delivery as Svix signs it (todo E20).

Resend signs through Svix: an HMAC-SHA256 keyed with the base64-decoded text after the secret's
``whsec_`` prefix, over ``{svix-id}.{svix-timestamp}.{raw body}``, sent in ``svix-signature`` as
space-separated ``v1,<base64 digest>`` entries; Svix's libraries refuse a timestamp more than five
minutes from the receiver's clock. Until E20 the handler keyed the HMAC with the raw secret and
compared hex, so it refused every genuine delivery. The vector is the example on Svix's manual
verification page (https://docs.svix.com/receiving/verifying-payloads/how-manual, read 2026-10-16).
"""
import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.routers import webhooks
from main import app

SECRET = "whsec_plJ3nmyCDGBKInavdOK15jsl"  # gitleaks:allow (the public example on Svix's verification page)
MSG_ID = "msg_loFOjxBNrRLzqYUf"
TIMESTAMP = "1731705121"
BODY = b'{"event_type":"ping","data":{"success":true}}'
SIGNATURE = "v1,rAvfW3dJ/X/qxhsaXPOyyCGmRKsaKWcsNccKXlIktD0="
OTHER_SECRET = "whsec_" + base64.b64encode(b"another endpoint's key").decode()


def _sign(secret: str, msg_id: str, timestamp: str, body: bytes) -> str:
    """Svix's scheme as its page states it; the first test ties it to the published signature."""
    encoded = secret.removeprefix("whsec_")
    key = base64.b64decode(encoded + "=" * (-len(encoded) % 4))
    digest = hmac.new(key, f"{msg_id}.{timestamp}.".encode() + body, hashlib.sha256).digest()
    return "v1," + base64.b64encode(digest).decode()


@pytest.fixture(autouse=True)
def _clock_at_the_vector(monkeypatch):
    _clock(monkeypatch, int(TIMESTAMP))


def _clock(monkeypatch, seconds: float) -> None:
    monkeypatch.setattr(webhooks, "utcnow", lambda: datetime.fromtimestamp(seconds, tz=timezone.utc))


def _verify(signature=SIGNATURE, secret=SECRET, msg_id=MSG_ID, timestamp=TIMESTAMP, body=BODY) -> bool:
    return webhooks.verify_webhook_signature(body, signature, secret, msg_id, timestamp)


def test_the_published_svix_example_verifies():
    assert _sign(SECRET, MSG_ID, TIMESTAMP, BODY) == SIGNATURE
    assert _verify()


@pytest.mark.parametrize("genuine_first", [True, False], ids=["genuine-first", "genuine-last"])
def test_one_matching_entry_among_several_verifies(genuine_first):
    # Svix sends one entry per active secret while a secret rotates, in no promised order.
    entries = [f"v1,{base64.b64encode(b'x' * 32).decode()}", SIGNATURE]
    assert _verify(signature=" ".join(entries[::-1] if genuine_first else entries))


@pytest.mark.parametrize(
    "case",
    [
        dict(body=BODY.replace(b"true", b"false")),
        dict(msg_id="msg_loFOjxBNrRLzqYUg"),
        dict(signature=_sign(SECRET, MSG_ID, str(int(TIMESTAMP) - 1), BODY), timestamp=TIMESTAMP),
        dict(secret=OTHER_SECRET),
        # The scheme this handler used until E20: the raw secret as the key, a hex digest.
        dict(signature="v1," + hmac.new(SECRET.encode(), f"{MSG_ID}.{TIMESTAMP}.".encode() + BODY, hashlib.sha256).hexdigest()),
        dict(signature=SIGNATURE.replace("v1,", "v2,")),
        dict(signature=SIGNATURE.replace("v1,", "v1a,")),
        dict(signature=SIGNATURE.removeprefix("v1,")),
        dict(signature=SIGNATURE[:-2]),
        dict(signature=""),
        dict(signature=SIGNATURE + "é"),
        dict(signature="v1," + base64.b64encode(base64.b64decode(SIGNATURE[3:])[:-1]).decode()),
    ],
    ids=[
        "tampered-body", "other-id", "signed-for-another-timestamp", "other-secret", "pre-E20-hex",
        "v2-entry", "v1a-entry", "no-version", "truncated", "empty-header", "non-ascii-header", "short-digest",
    ],
)
def test_a_delivery_that_does_not_match_is_refused(case):
    assert not _verify(**case)


# The libraries' boundary: 300 s either side passes, and a fraction past it fails on both sides.
@pytest.mark.parametrize(
    ("offset", "accepted"), [(-300, True), (300, True), (-300.5, False), (300.5, False), (-301, False), (301, False)]
)
def test_the_timestamp_must_be_within_five_minutes_of_the_clock(monkeypatch, offset, accepted):
    _clock(monkeypatch, int(TIMESTAMP) + offset)
    assert _verify() is accepted


@pytest.mark.parametrize("timestamp", ["", "abc", "1731705121.0", "9" * 400, "9" * 5000])
def test_a_timestamp_that_is_not_a_nearby_whole_second_is_refused_without_an_error(timestamp):
    assert not _verify(signature=_sign(SECRET, MSG_ID, timestamp, BODY), timestamp=timestamp)


def test_a_secret_stored_with_a_newline_or_without_its_prefix_or_padding_verifies():
    unpadded = base64.b64encode(b"a key of 31 bytes, not 3n bytes").decode().rstrip("=")
    assert unpadded != base64.b64encode(b"a key of 31 bytes, not 3n bytes").decode()
    assert _verify(secret=SECRET + "\n")
    assert _verify(secret=SECRET.removeprefix("whsec_"))
    assert _verify(signature=_sign(unpadded, MSG_ID, TIMESTAMP, BODY), secret="whsec_" + unpadded)


@pytest.mark.parametrize(
    "secret",
    # A stray character inside the real key: a decoder that skips it would verify with the real key.
    ["whsec_", "whsec_!!!!", "whsec_plJ3nmyCDGBKInavdOK15jsé", "whsec_a", "whsec_plJ3nmyCDGBK!InavdOK15jsl"],
    ids=["empty-key", "not-base64", "non-ascii", "bad-length", "stray-character"],
)
def test_a_malformed_secret_fails_closed_with_a_fixed_message(secret, caplog):
    caplog.set_level(logging.WARNING, logger=webhooks.logger.name)
    assert not _verify(secret=secret)
    # A fixed message: the secret's value never reaches the log.
    assert [record.getMessage() for record in caplog.records if record.name == webhooks.logger.name] == [
        "RESEND_WEBHOOK_SECRET is not a Svix signing secret (whsec_ and base64). Webhook verification failed."
    ]


def test_an_empty_key_refuses_a_signature_made_with_an_empty_key():
    # HMAC accepts an empty key, and anybody can sign with it.
    assert not _verify(signature=_sign("whsec_", MSG_ID, TIMESTAMP, BODY), secret="whsec_")


@pytest.fixture
def client():
    return TestClient(app)


def _delivery(client, secret: str, signature=None):
    # Compact, as Resend sends it: the signature covers these bytes, not any re-serialised JSON.
    body = json.dumps({"type": "email.delivered", "data": {"email_id": "em_1", "to": ["n@example.com"]}},
                      separators=(",", ":")).encode()
    assert json.dumps(json.loads(body)).encode() != body
    headers = {
        "svix-id": MSG_ID,
        "svix-timestamp": TIMESTAMP,
        "svix-signature": signature or _sign(secret or SECRET, MSG_ID, TIMESTAMP, body),
        "content-type": "application/json",
    }
    return client.post("/api/webhooks/resend", content=body, headers=headers)


def test_the_endpoint_accepts_a_genuine_delivery_and_refuses_a_forged_one(client, monkeypatch):
    monkeypatch.setattr(settings, "RESEND_WEBHOOK_SECRET", SECRET)
    accepted = _delivery(client, SECRET)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json() == {"status": "ok", "event": "email.delivered"}
    assert _delivery(client, SECRET, signature=_sign(OTHER_SECRET, MSG_ID, TIMESTAMP, b"{}")).status_code == 401


@pytest.mark.parametrize(("environment", "status_code"), [("production", 401), ("development", 200)])
def test_without_a_secret_production_refuses_and_development_skips(client, monkeypatch, environment, status_code):
    monkeypatch.setattr(settings, "RESEND_WEBHOOK_SECRET", "")
    monkeypatch.setattr(settings, "ENVIRONMENT", environment)
    assert _delivery(client, "").status_code == status_code


@pytest.mark.parametrize(
    "case",
    [dict(), dict(signature=SIGNATURE[:-2]), dict(timestamp="abc"), dict(timestamp=str(int(TIMESTAMP) - 301)),
     dict(secret="whsec_!!!!")],
    ids=["genuine", "forged", "bad-timestamp", "stale", "malformed-secret"],
)
def test_no_path_logs_the_secret_or_its_key(case, caplog):
    caplog.set_level(logging.DEBUG, logger=webhooks.logger.name)
    _verify(**case)
    logged = " ".join(record.getMessage() for record in caplog.records)
    secret = case.get("secret", SECRET)
    assert secret.removeprefix("whsec_") not in logged
    assert repr(base64.b64decode(SECRET.removeprefix("whsec_"))) not in logged
