"""Coverage classification for companies EarningsNerd cannot analyze (FPI Phase 5).

Some well-known foreign issuers trade in the U.S. as unsponsored ADRs and file **no** financial
reports with the SEC (only F-6 depositary-share registrations). They don't resolve to a reporting
CIK, so a bare "Company not found" is misleading for a name users recognize. This module is the
single source of truth for that curated set and the honest message surfaced instead.

Kept as a thin, dependency-free service module so the curated list is unit-testable without
importing the FastAPI router stack. Home-market sourcing (HKEX/SIX/Euronext) for these names is an
explicit non-goal — see tasks/fpi-support-roadmap.md §8.
"""
from __future__ import annotations

from typing import Optional

# Curated unsponsored-ADR tickers that file no SEC financial reports. Multiple ticker spellings map
# to the same issuer (e.g. the OTC pink and F-share lines for Tencent/Nestlé/Roche/LVMH).
UNSUPPORTED_FOREIGN_NAMES: dict[str, str] = {
    "TCEHY": "Tencent Holdings Ltd",
    "TCTZF": "Tencent Holdings Ltd",
    "NSRGY": "Nestlé S.A.",
    "NSRGF": "Nestlé S.A.",
    "RHHBY": "Roche Holding AG",
    "RHHVF": "Roche Holding AG",
    "LVMHF": "LVMH Moët Hennessy Louis Vuitton SE",
    "LVMUY": "LVMH Moët Hennessy Louis Vuitton SE",
}

UNSUPPORTED_FOREIGN_REASON = (
    "This issuer trades in the U.S. as an unsponsored ADR and does not file financial reports with "
    "the SEC, so EarningsNerd has no filings to analyze. Try its U.S.-listed peers instead."
)


def unsupported_foreign_name(ticker: str) -> Optional[str]:
    """Display name if ``ticker`` is a known unsupported foreign issuer, else ``None``.

    Looked up BEFORE any SEC resolution so a recognizable ADR ticker can never fuzzy-match onto an
    unrelated reporting issuer (the TCEHY/Tencent → TME/Tencent Music guard — TME is a real 20-F
    filer at a different CIK and must stay fully supported).
    """
    return UNSUPPORTED_FOREIGN_NAMES.get((ticker or "").upper().strip())
