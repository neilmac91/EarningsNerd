"""A5 — "What Changed": a deterministic, narrated period-over-period change report for a filing.

Reuses the existing LLM-free diff engine (`dashboard_feed_service.compute_what_changed`) for financial
deltas, assembled into one report for the filing page. The lead framing is the deterministic
`metrics.headline`; `Summary.key_changes` is deprecated (still written for API compat, no longer
surfaced here — it duplicated the Outlook section verbatim; T1.6 / plan §2.3). Pure where it counts
(report assembly is unit-testable); only the prior-filing lookup touches the DB.

The brand stance (signal over noise): everything here is deterministic and conservative. Stored risk
labels are model-authored, so the report carries no risk lines (``risks`` stays null).
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import Filing
# Reuse the tested deterministic delta engine rather than duplicating it (one home for the
# revenue/net-income/EPS invariants, the QoQ/YoY logic and the reporting-currency guard).
from app.services.dashboard_feed_service import compute_what_changed, reporting_currency
from app.services.filing_section_service import NO_SECTION_ACCESS, SectionAccess, build_section_changes


def _comparison_basis(filing_type: Optional[str]) -> Optional[str]:
    # Normalize case + amended forms (10-k/a, 20-F/A, 6-K/A) to the uppercase base so they all
    # resolve to a label regardless of how the form string was stored/passed.
    base = (filing_type or "").upper().split("/")[0]
    return {
        "10-Q": "Quarter over quarter",
        "10-K": "Year over year",
        # FPI forms (Phase 4/5): 20-F/40-F are annual (YoY, like a 10-K); 6-K is a semi-annual
        # interim furnished report, so its prior comparable is the prior interim period.
        "20-F": "Year over year",
        "40-F": "Year over year",
        "6-K": "Period over period",
    }.get(base)


def _filing_ref(filing: Any) -> Optional[dict]:
    if filing is None:
        return None
    return {
        "filing_id": filing.id,
        "filing_type": filing.filing_type,
        "filing_date": filing.filing_date.isoformat() if filing.filing_date else None,
        "period_end_date": filing.period_end_date.isoformat() if filing.period_end_date else None,
    }


def assemble_report(
    current_filing: Any,
    prior_filing: Any,
    section_changes: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Pure assembly of the change report from the current/prior filings.

    ``section_changes`` is the filing-text wording diff block (``filing_section_service``), None
    while ENABLE_SECTION_CHANGES is off; the key is always present so the contract is stable.
    """
    prior_ref = _filing_ref(prior_filing)
    metrics = compute_what_changed(
        getattr(current_filing, "xbrl_data", None),
        getattr(prior_filing, "xbrl_data", None) if prior_filing is not None else None,
        # Every line compares the period the basis line prints: "against the 10-Q for the quarter ended <this>".
        prior_period_end=prior_ref["period_end_date"] if prior_ref else None,
        form=getattr(current_filing, "filing_type", None),
    )
    # Stored risk labels are model-authored. Until there is a source-projected cross-period
    # contract, omit this portion of What Changed rather than re-expose them through a side door.
    risks = None
    return {
        "has_prior": prior_filing is not None,
        "comparison_basis": _comparison_basis(getattr(current_filing, "filing_type", None)),
        "prior_filing": prior_ref,
        "metrics": metrics,
        # The currency of every metric item's current/prior amount (additive). Items carry raw XBRL
        # amounts in the filer's own currency, so a client labels them with it and never assumes
        # dollars; None = never resolved, shown without a currency. compute_what_changed never takes
        # a prior amount from a filing in another currency, so this labels both columns.
        "reporting_currency": reporting_currency(getattr(current_filing, "xbrl_data", None)),
        "risks": risks,
        # Deprecated-in-place (T1.6 / plan §2.3): the What-changed lead is now the deterministic
        # metrics.headline, not the summary's own outlook narrative (which duplicated the Outlook
        # section verbatim). Summary.key_changes is still written for API compat; nothing surfaces it.
        "key_changes": None,
        "has_changes": bool(metrics),
        # Deterministic Item 1A wording diff against the prior same-form filing: the filings' own
        # text only, paired paragraph by paragraph (section_diff). Teaser or full per the viewer's
        # entitlement; null until the flag is on.
        "section_changes": section_changes,
    }


def build_change_report(
    db: Session, filing: Filing, *, section_access: SectionAccess = NO_SECTION_ACCESS
) -> dict[str, Any]:
    """Find the filing's prior comparable filing, then assemble the change report.

    ``section_access`` (``filing_section_service.section_changes_access``) is how much of the
    Item 1A wording diff the viewer gets: none, a teaser of so many items, or the full list.

    The prior is the latest earlier report period from the same company and base form,
    preferring its newest amendment filed before the viewed filing
    (10-Q → prior 10-Q = QoQ, 10-K → prior 10-K = YoY) — a single query, xbrl included. We require a
    strictly-earlier reporting PERIOD (not just an earlier filing date) so a later amendment or
    restatement of the SAME period is never differenced against the original — an apples-to-oranges
    comparison that produces spurious deltas.
    """
    base_form = filing.filing_type.removesuffix("/A")
    prior_q = db.query(Filing).filter(
        Filing.company_id == filing.company_id,
        Filing.filing_type.in_((base_form, f"{base_form}/A")),
        Filing.filing_date < filing.filing_date,
    )
    if filing.period_end_date is not None:
        prior_q = prior_q.filter(Filing.period_end_date < filing.period_end_date)
        # Report-period ordering prevents a late amendment of an older year from displacing
        # the immediately preceding period; newest filing then prefers its amendment.
        prior = prior_q.order_by(desc(Filing.period_end_date), desc(Filing.filing_date), desc(Filing.accession_number)).first()
    else:
        # Without the current period we cannot prove that a candidate is a different period.
        prior = None
    section_changes = build_section_changes(db, filing, section_access)
    return assemble_report(filing, prior, section_changes)


def change_report_for_filing(
    db: Session, filing_id: int, *, section_access: SectionAccess = NO_SECTION_ACCESS
) -> Optional[dict[str, Any]]:
    """The filing's change report, or None when the filing does not exist; releases the session
    either way.

    One synchronous unit for the router to run off the event loop: the lookup, the report (the
    wording diff is CPU work) and the close, so the pooled connection is back before the async
    route yields to the sync dependency's finalizer
    (``lessons/ops-release-cached-filing-reads-before-yield.md``).
    """
    try:
        filing = db.query(Filing).filter(Filing.id == filing_id).first()
        if filing is None:
            return None
        return build_change_report(db, filing, section_access=section_access)
    finally:
        db.close()
