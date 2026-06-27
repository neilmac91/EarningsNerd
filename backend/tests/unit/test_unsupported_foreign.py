"""Phase 5: honest "coverage unavailable" state for unsupported foreign issuers (unsponsored ADRs).

Pure-function tests for the curated-name guard (``app.services.company_coverage``) — no DB / no SEC
/ no router import. Covers the TCEHY/Tencent → TME/Tencent Music binding guard the roadmap calls out.
"""
from app.services.company_coverage import (
    UNSUPPORTED_FOREIGN_NAMES,
    unsupported_foreign_name,
)


def test_known_unsupported_name_resolves_case_insensitively():
    assert unsupported_foreign_name("tcehy") == "Tencent Holdings Ltd"
    assert unsupported_foreign_name("  NSRGY  ") == "Nestlé S.A."


def test_supported_tickers_fall_through():
    # A domestic filer (or any non-curated ticker) must fall through to normal resolution.
    assert unsupported_foreign_name("AAPL") is None
    # BABA is a real 20-F filer — it must NOT be intercepted by the unsupported guard.
    assert unsupported_foreign_name("BABA") is None
    assert unsupported_foreign_name("") is None


def test_tcehy_does_not_bind_to_tme():
    """The TCEHY/Tencent guard: TCEHY resolves to the honest unsupported state for Tencent
    Holdings, never to TME (Tencent Music, a real 20-F filer at a different CIK)."""
    assert "TME" not in UNSUPPORTED_FOREIGN_NAMES  # TME is supported, not on the deny list
    name = unsupported_foreign_name("TCEHY")
    assert name == "Tencent Holdings Ltd"
    assert "Music" not in name  # Tencent Holdings, not Tencent Music
