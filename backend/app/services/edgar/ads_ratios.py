"""Curated American Depositary Share (ADS) ratio table + per-ADS EPS helpers (item A).

WHY THIS EXISTS
---------------
EdgarTools / XBRL report a foreign issuer's earnings per *ordinary share*, in the home
currency. ADR investors hold ADSs, not ordinary shares, so the figure they actually care
about is **per-ADS** (= per-ordinary-share x ordinary-shares-per-ADS). The ADS ratio is NOT
in XBRL, EdgarTools does not normalize it, and general-purpose chatbots routinely miss it —
so per-ADS EPS is the single most credibility-sensitive number on an ADR report. Because the
product's pitch is verifiable accuracy, the per-ADS figure must be shown WITH its ratio and
arithmetic so a reader can audit it.

CAVEATS
-------
- Ratios are **curated and dated** (source-and-locked against each issuer's deposit agreement /
  20-F cover). They are not machine-derivable from XBRL and they ROT on splits / restructurings /
  ratio changes — re-verify on the ``as_of`` cadence.
- Only issuers whose ratio != 1 appear here. A 1:1 ADR (per-ADS == per-share) or a domestic
  filer is intentionally absent: ``ads_ratio_for_cik`` returns ``None`` and no normalization is
  applied. (The eval golden set mirrors these ratios in ``backend/evals/golden_set.json``.)

Dependency-light on purpose (stdlib only): unit-tested in isolation and safe to import from the
extraction path without pulling app config.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ADSRatio:
    """One issuer's locked ADS ratio. ``ordinary_per_ads`` = ordinary shares per one ADS."""

    ordinary_per_ads: float
    as_of: str  # ISO date the ratio was last verified against the source
    source: str  # where it was verified (deposit agreement / 20-F cover)
    ticker: str

    def as_dict(self) -> Dict[str, Any]:
        """Plain-dict form, so it can ride along in the (JSON-cacheable) xbrl_data payload."""
        return {
            "ordinary_per_ads": self.ordinary_per_ads,
            "as_of": self.as_of,
            "source": self.source,
            "ticker": self.ticker,
        }


# Keyed by CIK (leading zeros insignificant — normalized in the lookup). Only ratio != 1 issuers.
# Verified 2026-06-28 against each issuer's 20-F cover / deposit agreement; the same ratios are
# mirrored in the eval golden set (backend/evals/golden_set.json `ads_ratio`).
_ADS_RATIOS: Dict[str, ADSRatio] = {
    "1577552": ADSRatio(8, "2026-06-28", "Alibaba 20-F cover / deposit agreement — 1 ADS = 8 ordinary shares", "BABA"),
    "1046179": ADSRatio(5, "2026-06-28", "TSMC 20-F cover / deposit agreement — 1 ADS = 5 common shares", "TSM"),
    "1549802": ADSRatio(2, "2026-06-28", "JD.com 20-F cover / deposit agreement — 1 ADS = 2 Class A ordinary shares", "JD"),
    "1737806": ADSRatio(4, "2026-06-28", "PDD Holdings 20-F cover / deposit agreement — 1 ADS = 4 ordinary shares", "PDD"),
}


def _normalize_cik(cik: Any) -> Optional[str]:
    """CIK as an unpadded digit string ('0001577552' / 1577552 -> '1577552'), or None."""
    if cik is None:
        return None
    text = str(cik).strip().lstrip("0")
    return text if text.isdigit() else None


def ads_ratio_for_cik(cik: Any) -> Optional[ADSRatio]:
    """The locked ADS ratio for a CIK, or None when the issuer is 1:1 / domestic / unknown."""
    key = _normalize_cik(cik)
    return _ADS_RATIOS.get(key) if key else None


def _round_money(value: float) -> float:
    """Match the extractor's 4-dp rounding so float noise (5.7*8 = 45.5999…) renders cleanly."""
    return round(value, 4)


def build_per_ads_eps(
    per_share_value: Optional[float],
    ads_info: Dict[str, Any],
    currency: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Build the additive per-ADS EPS entry from a per-ordinary-share EPS value.

    ``ads_info`` is the plain-dict form of an :class:`ADSRatio` (see :meth:`ADSRatio.as_dict`),
    so this works on the JSON-cacheable xbrl_data payload without importing the dataclass.
    ``currency`` is the issuer's *reporting* currency (per-share facts carry no currency of their
    own, so the caller passes the filing-level reporting currency, e.g. "CNY").

    Returns ``None`` when there is no per-share value or no usable ratio — never a wrong number.
    The result carries the ratio + an auditable arithmetic string so the figure can be verified.
    """
    if per_share_value is None:
        return None
    try:
        ratio = float(ads_info.get("ordinary_per_ads"))
    except (TypeError, ValueError):
        return None
    if ratio <= 0:
        return None

    value = _round_money(per_share_value * ratio)
    prefix = f"{currency} " if currency else ""
    arithmetic = (
        f"{prefix}{per_share_value:g} per ordinary share × {ratio:g} "
        f"= {prefix}{value:g} per ADS"
    )
    return {
        "value": value,
        "ordinary_per_ads": ratio,
        "currency": currency,
        "as_of": ads_info.get("as_of"),
        "source": ads_info.get("source"),
        "arithmetic": arithmetic,
    }
