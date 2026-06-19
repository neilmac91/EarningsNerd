"""A5 — "What Changed": a deterministic, narrated period-over-period change report for a filing.

Reuses the existing LLM-free diff engine (`dashboard_feed_service.compute_what_changed` and
`_prior_same_form`) for financial deltas, **adds** risk-factor diffing (new / resolved / carried), and
surfaces the otherwise-unrendered `Summary.key_changes` narrative — assembled into one report for the
filing page. Pure where it counts (risk diffing + report assembly are unit-testable); only the
prior-filing/summary lookups touch the DB.

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
_PLACEHOLDER_TOKENS = (
    "not available", "unavailable", "requires", "pending", "generating", "retry", "n/a",
    "being processed", "processing", "preliminary", "placeholder", "taking longer",
)


def _extract_risks(summary: Optional[Summary]) -> list[dict]:
    """Risk factors from a summary — the top-level column, falling back to raw_summary.sections."""
    if summary is None:
        return []
    risks = getattr(summary, "risk_factors", None)
    if not isinstance(risks, list) or not risks:
        raw = getattr(summary, "raw_summary", None)
        if isinstance(raw, dict) and isinstance(raw.get("sections"), dict):
            risks = raw["sections"].get("risk_factors")
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

    matched_prior: set[int] = set()
    new: list[str] = []
    for risk, tokens in zip(cur, cur_tokens):
        best_j, best_score = -1, 0.0
        for j, ptokens in enumerate(pri_tokens):
            if j in matched_prior:
                continue
            score = _jaccard(tokens, ptokens)
            if score > best_score:
                best_score, best_j = score, j
        if best_j >= 0 and best_score >= threshold:
            matched_prior.add(best_j)
        else:
            new.append(_risk_label(risk))

    resolved = [_risk_label(pri[j]) for j in range(len(pri)) if j not in matched_prior]
    return {"new": new, "resolved": resolved, "carried_count": len(matched_prior)}


def _clean_key_changes(text: Optional[str]) -> Optional[str]:
    """Surface the Summary.key_changes narrative, dropping placeholder/degraded text."""
    if not isinstance(text, str):
        return None
    stripped = text.strip()
    if not stripped:
        return None
    low = stripped.lower()
    if any(token in low for token in _PLACEHOLDER_TOKENS):
        return None
    return stripped


def _comparison_basis(filing_type: Optional[str]) -> Optional[str]:
    return {"10-Q": "Quarter over quarter", "10-K": "Year over year"}.get(filing_type or "")


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

    key_changes = _clean_key_changes(getattr(current_summary, "key_changes", None))
    has_risk_changes = bool(risks and (risks["new"] or risks["resolved"]))
    return {
        "has_prior": prior_filing is not None,
        "comparison_basis": _comparison_basis(getattr(current_filing, "filing_type", None)),
        "prior_filing": _filing_ref(prior_filing),
        "metrics": metrics,
        "risks": risks,
        "key_changes": key_changes,
        "has_changes": bool(metrics or has_risk_changes or key_changes),
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
    (10-Q → prior 10-Q = QoQ, 10-K → prior 10-K = YoY) — a single query, xbrl included.
    """
    prior = (
        db.query(Filing)
        .filter(
            Filing.company_id == filing.company_id,
            Filing.filing_type == filing.filing_type,
            Filing.filing_date < filing.filing_date,
        )
        .order_by(desc(Filing.filing_date))
        .first()
    )
    current_summary = _latest_summary(db, filing.id)
    prior_summary = _latest_summary(db, prior.id) if prior is not None else None
    return assemble_report(filing, prior, current_summary, prior_summary)
