"""Public role addresses shared with the frontend; no internal account identities."""
from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict, cast


class PublicEmailAddresses(TypedDict):
    support: str
    billing: str
    privacy: str
    security: str


PUBLIC_EMAIL_ADDRESSES = cast(
    PublicEmailAddresses,
    json.loads(Path(__file__).with_suffix(".json").read_text(encoding="utf-8")),
)
SUPPORT_EMAIL = PUBLIC_EMAIL_ADDRESSES["support"]
BILLING_EMAIL = PUBLIC_EMAIL_ADDRESSES["billing"]
PRIVACY_EMAIL = PUBLIC_EMAIL_ADDRESSES["privacy"]
SECURITY_EMAIL = PUBLIC_EMAIL_ADDRESSES["security"]
