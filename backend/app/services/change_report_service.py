"""A5 — "What Changed": a deterministic, narrated period-over-period change report for a filing.

Reuses the existing LLM-free diff engine (`dashboard_feed_service.compute_what_changed` and
`_prior_same_form`) for financial deltas and **adds** risk-factor diffing (new / resolved / carried) —
assembled into one report for the filing page. The lead framing is the deterministic
`metrics.headline`; `Summary.key_changes` is deprecated (still written for API compat, no longer
surfaced here — it duplicated the Outlook section verbatim; T1.6 / plan §2.3). Pure where it counts
(risk diffing + report assembly are unit-testable); only the prior-filing/summary lookups touch the DB.

The brand stance (signal over noise): everything here is deterministic and conservative — risk
matching errs toward "carried over" so we don't cry "new risk" on a reworded heading.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import Filing, Summary
# Reuse the tested deterministic delta engine rather than duplicating it (one home for the
# revenue/net-income/EPS invariants and QoQ/YoY logic).
from app.services.dashboard_feed_service import compute_what_changed

_TOKEN_RE = re.compile(r"[a-z0-9]+")
# Generic words that don't help distinguish one risk factor from another.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "with", "our", "we", "us", "may",
    "could", "would", "that", "this", "these", "those", "is", "are", "be", "been", "as", "by", "its",
    "it", "from", "at", "which", "risk", "risks", "factor", "factors", "including", "include", "such",
    "other", "material", "adversely", "affect", "affected", "business", "company", "results",
    "operations",
}
# Two risk factors are "the same risk" when their token sets overlap at least this much (Jaccard).
# Deliberately lenient so reworded headings read as "carried over", not false "new"/"resolved".
_RISK_MATCH_THRESHOLD = 0.4


def _extract_risks(summary: Optional[Summary]) -> list[dict]:
    """Risk factors from a summary — the top-level column, falling back to raw_summary.sections."""
    if summary is None:
        return []
    risks = getattr(summary, "risk_factors", None)
    if not isinstance(risks, list) or not risks:
        raw = getattr(summary, "raw_summary", None)
        if isinstance(raw, dict) and isinstance(raw.get("sections"), dict):
            # v2 rows carry `risks`; legacy v1 rows carry `risk_factors`.
            sec = raw["sections"]
            risks = sec.get("risks") or sec.get("risk_factors")
    return [r for r in risks if isinstance(r, dict)] if isinstance(risks, list) else []


def _risk_text(risk: dict) -> str:
    for field in ("title", "summary", "description"):
        value = risk.get(field)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _risk_label(risk: dict) -> str:
    title = risk.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    text = _risk_text(risk).strip()
    return (text[:117] + "…") if len(text) > 118 else text


def _tokenize(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower()) if len(t) > 2 and t not in _STOPWORDS}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    union = len(a | b)
    return len(a & b) / union if union else 0.0


def diff_risk_factors(
    current_risks: Optional[list],
    prior_risks: Optional[list],
    threshold: float = _RISK_MATCH_THRESHOLD,
) -> dict[str, Any]:
    """Classify risks as new / resolved / carried via token-overlap matching (no LLM).

    Greedy best-match each current risk to an unused prior risk above ``threshold``; unmatched
    current risks are "new", unmatched prior risks are "resolved", matches are "carried over".
    """
    cur = [r for r in (current_risks or []) if isinstance(r, dict) and _risk_text(r)]
    pri = [r for r in (prior_risks or []) if isinstance(r, dict) and _risk_text(r)]
    cur_tokens = [_tokenize(_risk_text(r)) for r in cur]
    pri_tokens = [_tokenize(_risk_text(r)) for r in pri]

    # Global best-first matching: rank ALL candidate pairs (>= threshold) by similarity and assign
    # the strongest first. This is order-independent — a reworded risk won't be mismatched just
    # because an earlier-listed risk greedily grabbed its counterpart.
    candidates: list[tuple[float, int, int]] = []
    for i, tokens in enumerate(cur_tokens):
        for j, ptokens in enumerate(pri_tokens):
            score = _jaccard(tokens, ptokens)
            if score >= threshold:
                candidates.append((score, i, j))
    candidates.sort(key=lambda c: c[0], reverse=True)

    matched_cur: set[int] = set()
    matched_prior: set[int] = set()
    for _score, i, j in candidates:
        if i in matched_cur or j in matched_prior:
            continue
        matched_cur.add(i)
        matched_prior.add(j)

    new = [_risk_label(cur[i]) for i in range(len(cur)) if i not in matched_cur]
    resolved = [_risk_label(pri[j]) for j in range(len(pri)) if j not in matched_prior]
    return {"new": new, "resolved": resolved, "carried_count": len(matched_prior)}


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
    current_filing: Any, prior_filing: Any, current_summary: Any, prior_summary: Any
) -> dict[str, Any]:
    """Pure assembly of the change report from the current/prior filings + summaries."""
    metrics = compute_what_changed(
        getattr(current_filing, "xbrl_data", None),
        getattr(prior_filing, "xbrl_data", None) if prior_filing is not None else None,
    )
    risks = None
    if prior_summary is not None:
        risks = diff_risk_factors(_extract_risks(current_summary), _extract_risks(prior_summary))

    has_risk_changes = bool(risks and (risks["new"] or risks["resolved"]))
    return {
        "has_prior": prior_filing is not None,
        "comparison_basis": _comparison_basis(getattr(current_filing, "filing_type", None)),
        "prior_filing": _filing_ref(prior_filing),
        "metrics": metrics,
        "risks": risks,
        # Deprecated-in-place (T1.6 / plan §2.3): the What-changed lead is now the deterministic
        # metrics.headline, not the summary's own outlook narrative (which duplicated the Outlook
        # section verbatim). Summary.key_changes is still written for API compat; nothing surfaces it.
        "key_changes": None,
        "has_changes": bool(metrics or has_risk_changes),
    }


def _latest_summary(db: Session, filing_id: int) -> Optional[Summary]:
    return (
        db.query(Summary)
        .filter(Summary.filing_id == filing_id)
        .order_by(desc(Summary.updated_at), desc(Summary.created_at))
        .first()
    )


def build_change_report(db: Session, filing: Filing) -> dict[str, Any]:
    """Find the filing's prior comparable filing + both summaries, then assemble the change report.

    The prior is the most recent same-company, same-form filing strictly older than this one
    (10-Q → prior 10-Q = QoQ, 10-K → prior 10-K = YoY) — a single query, xbrl included. We require a
    strictly-earlier reporting PERIOD (not just an earlier filing date) so a later amendment or
    restatement of the SAME period is never differenced against the original — an apples-to-oranges
    comparison that produces spurious deltas.
    """
    prior_q = db.query(Filing).filter(
        Filing.company_id == filing.company_id,
        Filing.filing_type == filing.filing_type,
        Filing.filing_date < filing.filing_date,
    )
    if filing.period_end_date is not None:
        prior_q = prior_q.filter(Filing.period_end_date < filing.period_end_date)
    prior = prior_q.order_by(desc(Filing.filing_date)).first()
    current_summary = _latest_summary(db, filing.id)
    prior_summary = _latest_summary(db, prior.id) if prior is not None else None
    return assemble_report(filing, prior, current_summary, prior_summary)
