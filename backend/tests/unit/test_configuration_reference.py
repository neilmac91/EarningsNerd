"""Keep the operator's Settings inventory complete and its declared defaults truthful."""
import json
import re
from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings

REFERENCE = Path(__file__).resolve().parents[3] / "docs/CONFIGURATION.md"


def test_configuration_reference_covers_settings_and_defaults():
    # Only structured inventory rows count: a casual mention or commented-out example
    # must not conceal a missing operator-facing definition.
    rows = re.findall(r"^\| `([A-Z][A-Z0-9_]*)` \| `([^`]+)` \| (.+) \|$", REFERENCE.read_text(), re.MULTILINE)
    counts = Counter(name for name, _, _ in rows)
    fields = Settings.model_fields
    assert set(counts) == set(fields), (
        f"Settings inventory mismatch: missing={sorted(set(fields) - set(counts))}, "
        f"obsolete={sorted(set(counts) - set(fields))}"
    )
    assert all(count == 1 for count in counts.values()), f"Duplicate Settings rows: {counts}"
    for name, documented, guidance in rows:
        field = fields[name]
        expected = "required" if field.is_required() else json.dumps(field.default)
        assert documented == expected, f"{name}: documented default {documented}, code default {expected}"
        assert guidance.strip(), f"{name}: describe the purpose and any override caveats"


@pytest.mark.parametrize("seconds", [120, 121, 180])
def test_usage_reservation_ttl_covers_generation_and_conversion(seconds):
    with pytest.raises(ValidationError, match="USAGE_RESERVATION_TTL_SECONDS"):
        Settings(USAGE_RESERVATION_TTL_SECONDS=seconds, _env_file=None)


@pytest.mark.parametrize("seconds", [181, 300, 3600])
def test_usage_reservation_ttl_accepts_supported_range(seconds):
    assert Settings(USAGE_RESERVATION_TTL_SECONDS=seconds, _env_file=None).USAGE_RESERVATION_TTL_SECONDS == seconds


@pytest.mark.parametrize("value", [-1, 513])
def test_provider_admission_limit_rejects_out_of_range(value):
    with pytest.raises(ValidationError, match="AI_CHAT_MAX_INFLIGHT"):
        Settings(AI_CHAT_MAX_INFLIGHT=value, _env_file=None)


@pytest.mark.parametrize("value", [0, 1, 8, 512])
def test_provider_admission_limit_accepts_supported_range(value):
    assert Settings(AI_CHAT_MAX_INFLIGHT=value, _env_file=None).AI_CHAT_MAX_INFLIGHT == value


@pytest.mark.parametrize("configured", [
    "https://www.earningsnerd.io", "https://www.earningsnerd.io/", "https://www.earningsnerd.io///",
])
def test_frontend_url_loads_as_one_canonical_origin(configured, monkeypatch):
    # E111: every link appends "/path" to FRONTEND_URL, so trailing slashes are removed at load, and only those.
    loaded = Settings(FRONTEND_URL=configured, _env_file=None).FRONTEND_URL
    assert loaded == "https://www.earningsnerd.io"
    assert Settings(_env_file=None).FRONTEND_URL == "https://www.earningsnerd.io"
    assert Settings(FRONTEND_URL="http://localhost:3000/app//", _env_file=None).FRONTEND_URL == "http://localhost:3000/app"

    from app.config import settings
    from app.services import email_service, invite_service, waitlist_service

    monkeypatch.setattr(settings, "FRONTEND_URL", loaded)
    links = [invite_service.build_invite_link("tok-1"), waitlist_service.build_referral_link("ref-1"),
             email_service._filing_url(7, None)]
    assert links == ["https://www.earningsnerd.io/register?invite=tok-1",
                     "https://www.earningsnerd.io/waitlist?ref=ref-1",
                     "https://www.earningsnerd.io/filing/7"]
