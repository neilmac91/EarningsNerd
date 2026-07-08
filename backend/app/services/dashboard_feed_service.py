"""Personalised dashboard feed — the Phase 3 "what changed" engine.

`compose_feed` returns the NEWEST eligible filing (10-K/10-Q, plus 20-F/40-F behind
ENABLE_FPI_FILINGS) for EACH of a user's watched companies — one card per company, companies ordered
by that filing's date, newest first (DB-only, N+1-free). Each is annotated with a **deterministic**
"what changed vs the prior filing" headline derived from the filing's stored ``xbrl_data`` (no LLM,
no network). The richer narrative diff stays on-demand (the summary), per the cost-aware plan.

`compute_what_changed` is a pure function (unit-testable on dicts) that enforces hard invariants so
corrupt/misaligned XBRL never produces a misleading headline:
  * revenue must be finite and ≥ 0;
  * sign(EPS) must match sign(net income) for the period;
otherwise the offending metric is dropped (never the whole row) and ``data_quality`` is "partial".
When nothing usable remains the headline is ``None`` and the card falls back to a neutral line.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session, defer, joinedload

from app.models import Filing, Summary, Watchlist
from app.services import metric_delta_service
from app.services.edgar.models import MetricChange
from app.services.summary_generation_service import get_generation_progress_snapshot
from app.services.summary_placeholders import is_summary_placeholder

logger = logging.getLogger(__name__)

# The feed centres on filings that carry XBRL financials (the "what changed" signal). 8-Ks have no
# XBRL, so v1 shows 10-K/10-Q only. When ENABLE_FPI_FILINGS is on we also include FPI ANNUAL reports
# (20-F/40-F) — they now carry XBRL (Phase 3) and pair year-over-year via _prior_same_form. 6-K is
# deliberately EXCLUDED: it's free-form / often XBRL-less, so it would yield neutral/None headlines.
FEED_FORM_TYPES = ("10-K", "10-Q")
FEED_FPI_ANNUAL_FORM_TYPES = ("20-F", "40-F")


def _feed_form_types() -> tuple[str, ...]:
    """Form types included in the dashboard feed — FPI annual reports added only behind the flag."""
    from app.config import settings

    if settings.ENABLE_FPI_FILINGS:
        return FEED_FORM_TYPES + FEED_FPI_ANNUAL_FORM_TYPES
    return FEED_FORM_TYPES

# (xbrl_data key, human label) in headline priority order. The financial-institution component keys
# are self-gating: a bank's xbrl_data carries net/non-interest income (not "revenue"), while a
# non-financial filer carries "revenue" (not the components), so only the applicable rows render.
_DELTA_METRICS = [
    ("revenue", "Revenue"),
    ("net_interest_income", "Net interest income"),
    ("noninterest_income", "Non-interest income"),
    ("net_income", "Net income"),
    ("earnings_per_share", "EPS"),
]

_DIRECTION_WORD = {"increase": "up", "decrease": "down", "unchanged": "flat"}


# --------------------------------------------------------------------------- pure delta

def _series_desc(xbrl: Optional[dict], metric: str) -> list[tuple[str, float, Optional[str]]]:
    """Return [(period, value, raw_tag)] for a metric, newest period first, skipping unusable entries.

    ``raw_tag`` is the underlying XBRL concept the value came from (None for legacy/pre-fix series);
    it lets the caller detect a concept that flips between filings (the apples-to-oranges delta bug).
    """
    out: list[tuple[str, float, Optional[str]]] = []
    series = (xbrl or {}).get(metric) if isinstance(xbrl, dict) else None
    if isinstance(series, list):
        for entry in series:
            if not isinstance(entry, dict):
                continue
            period, value = entry.get("period"), entry.get("value")
            if period is None or not isinstance(value, (int, float)) or isinstance(value, bool):
                continue
            out.append((str(period), float(value), entry.get("raw_tag")))
    out.sort(key=lambda pv: pv[0], reverse=True)
    return out


def _current_and_prior(
    current_xbrl: Optional[dict], prior_xbrl: Optional[dict], metric: str
) -> tuple[Optional[float], Optional[str], Optional[float], Optional[str], Optional[str]]:
    """(current_value, current_period, prior_value, current_raw_tag, prior_raw_tag) for a metric.

    Prior prefers the prior filing's series; falls back to the current filing's own in-instance
    comparative (a strictly-older period in the same series). Only periods strictly older than the
    current one are accepted as "prior".
    """
    current = _series_desc(current_xbrl, metric)
    if not current:
        return None, None, None, None, None
    cur_period, cur_value, cur_tag = current[0]

    prior_value: Optional[float] = None
    prior_tag: Optional[str] = None
    for period, value, tag in _series_desc(prior_xbrl, metric):
        if period < cur_period:
            prior_value, prior_tag = value, tag
            break
    if prior_value is None:  # fallback: same filing's comparative period
        for period, value, tag in current[1:]:
            if period < cur_period:
                prior_value, prior_tag = value, tag
                break
    return cur_value, cur_period, prior_value, cur_tag, prior_tag


def compute_what_changed(current_xbrl: Optional[dict], prior_xbrl: Optional[dict]) -> Optional[dict]:
    """Deterministic period-over-period headline from stored XBRL. None if nothing usable."""
    data: dict[str, tuple[float, Optional[float]]] = {}
    tags: dict[str, tuple[Optional[str], Optional[str]]] = {}
    for metric, _label in _DELTA_METRICS:
        cur, _period, prior, cur_tag, prior_tag = _current_and_prior(current_xbrl, prior_xbrl, metric)
        if cur is not None:
            data[metric] = (cur, prior)
            tags[metric] = (cur_tag, prior_tag)
    if not data:
        return None

    data_quality = "ok"

    # Invariant 0 (concept-flip guard): never difference two periods whose values came from DIFFERENT
    # XBRL concepts (e.g. a bank whose current filing resolved fee income and prior resolved a total)
    # — that apples-to-oranges delta is the −53.8% class of bug. Only fires when BOTH sides carry a
    # raw_tag and they disagree, so legacy series (no tag) are unaffected.
    for metric in list(data):
        cur_tag, prior_tag = tags.get(metric, (None, None))
        if cur_tag and prior_tag and cur_tag != prior_tag:
            del data[metric]
            data_quality = "partial"

    # Invariant 1: revenue must be ≥ 0 — in BOTH periods (a negative prior corrupts the delta too).
    if "revenue" in data:
        cur_rev, prior_rev = data["revenue"]
        if cur_rev < 0 or (prior_rev is not None and prior_rev < 0):
            del data["revenue"]
            data_quality = "partial"

    # Invariant 2: sign(EPS) must match sign(net income) — checked for current AND prior periods.
    # Disagreement in either period ⇒ distrust both metrics.
    if "earnings_per_share" in data and "net_income" in data:
        eps, prior_eps = data["earnings_per_share"]
        net_income, prior_net_income = data["net_income"]
        mismatch_current = eps != 0 and net_income != 0 and (eps > 0) != (net_income > 0)
        mismatch_prior = (
            prior_eps is not None and prior_net_income is not None
            and prior_eps != 0 and prior_net_income != 0
            and (prior_eps > 0) != (prior_net_income > 0)
        )
        if mismatch_current or mismatch_prior:
            del data["earnings_per_share"]
            del data["net_income"]
            data_quality = "partial"

    items: list[dict] = []
    for metric, label in _DELTA_METRICS:
        if metric not in data:
            continue
        cur, prior = data[metric]
        change = MetricChange.compute(cur, prior)
        if change.direction is None:  # no comparable prior → can't say what changed
            continue
        # Single delta policy: the display string + tone come from metric_delta_service so the chips
        # stop formatting on the client (every _DELTA_METRICS entry is a monetary amount / EPS).
        delta = metric_delta_service.compute(cur, prior, is_ratio=False)
        items.append({
            "metric": metric,
            "label": label,
            "direction": _DIRECTION_WORD.get(change.direction, "flat"),
            "pct": abs(change.percentage) if change.percentage is not None else None,
            "current": cur,
            "prior": prior,
            "display": delta.display,
            "tone": delta.tone,
        })

    if not items:
        return None

    parts = []
    for it in items[:2]:
        if it["pct"] is not None and it["direction"] != "flat":
            parts.append(f"{it['label']} {it['direction']} {it['pct']:.1f}%")
        else:
            parts.append(f"{it['label']} {it['direction']}")
    return {"headline": "; ".join(parts), "items": items, "data_quality": data_quality}


# --------------------------------------------------------------------------- summary status

def _summary_status(summary: Optional[Summary], filing_id: int) -> dict:
    """Mirror the watchlist-insights status taxonomy (ready/placeholder/generating/error/missing)."""
    if summary is not None:
        placeholder = is_summary_placeholder(summary.business_overview)
        return {"summary_id": summary.id, "summary_status": "placeholder" if placeholder else "ready"}

    progress = get_generation_progress_snapshot(filing_id)
    if progress:
        stage = progress.get("stage", "generating")
        return {
            "summary_id": None,
            "summary_status": "error" if stage == "error" else f"generating:{stage}",
        }
    return {"summary_id": None, "summary_status": "missing"}


def _prior_same_form(company_filings_desc: list[Filing], current: Filing) -> Optional[Filing]:
    """Previous filing of the SAME form type (10-Q→prior 10-Q = QoQ, 10-K→prior 10-K = YoY)."""
    same = [f for f in company_filings_desc if f.filing_type == current.filing_type]
    for i, f in enumerate(same):
        if f.id == current.id:
            return same[i + 1] if i + 1 < len(same) else None
    return None


# --------------------------------------------------------------------------- composition

def compose_feed(db: Session, user_id: int, limit: int = 20) -> list[dict]:
    """Each watched company's NEWEST eligible filing (10-K/10-Q, plus 20-F/40-F behind
    ENABLE_FPI_FILINGS) — one item per company, companies ordered by that filing's date, newest
    first. ``limit`` caps the number of COMPANIES shown (not filings). Each item carries a
    deterministic "what changed" headline + summary status. DB-only; no live EDGAR on render."""
    company_ids = [
        row[0]
        for row in db.query(Watchlist.company_id).filter(Watchlist.user_id == user_id).distinct().all()
    ]
    if not company_ids:
        return []

    form_types = _feed_form_types()

    # One metadata scan over EVERY watched company's eligible-form history (xbrl deferred, riding the
    # ix_filings_company_type_date covering index), newest first per company with a deterministic
    # tie-break. This single scan does double duty: each company's newest filing is its first row
    # (the feed head), and the full per-company history backs the prior-same-form comparison — so no
    # separate "latest per company" SQL is needed. Scan width is every watched company rather than
    # one page's worth; fine at beta watchlist sizes. Escape hatch if a pathological watchlist ever
    # makes it slow: a func.max pre-pass to shortlist the top-`limit` companies before the scan.
    by_company: dict[int, list[Filing]] = {}
    for f in (
        db.query(Filing)
        .options(defer(Filing.xbrl_data))
        .filter(Filing.company_id.in_(company_ids), Filing.filing_type.in_(form_types))
        .order_by(Filing.company_id, desc(Filing.filing_date), desc(Filing.id))
        .all()
    ):
        by_company.setdefault(f.company_id, []).append(f)
    if not by_company:
        return []

    # Each company's newest eligible filing is its scan's first row. Order companies by that filing's
    # date (newest first); tie-break on id desc so a same-day 10-K + 10-Q is deterministic. Then cap
    # to `limit` companies. filing_date is NOT NULL (models/__init__.py), so the tuple sort needs no
    # None guard — widen with a sentinel (f.filing_date or datetime.min) only if the scan ever
    # includes a nullable-date form.
    heads = [rows[0] for rows in by_company.values()]
    heads.sort(key=lambda f: (f.filing_date, f.id), reverse=True)
    heads = heads[:limit]

    # Rehydrate the (≤ limit) heads with their xbrl_data + company in ONE query (the scan deferred
    # both), preserving head order via an id→position map.
    head_ids = [f.id for f in heads]
    position = {fid: i for i, fid in enumerate(head_ids)}
    heads = sorted(
        db.query(Filing).options(joinedload(Filing.company)).filter(Filing.id.in_(head_ids)).all(),
        key=lambda f: position[f.id],
    )

    prior_by_filing: dict[int, Optional[Filing]] = {
        f.id: _prior_same_form(by_company.get(f.company_id, []), f) for f in heads
    }
    prior_ids = {p.id for p in prior_by_filing.values() if p is not None}
    prior_xbrl_by_id: dict[int, Any] = {}
    if prior_ids:
        prior_xbrl_by_id = dict(
            db.query(Filing.id, Filing.xbrl_data).filter(Filing.id.in_(prior_ids)).all()
        )

    # Batch summary existence/status (newest per filing).
    filing_ids = [f.id for f in heads]
    summary_by_filing: dict[int, Summary] = {}
    for s in (
        db.query(Summary)
        .filter(Summary.filing_id.in_(filing_ids))
        .order_by(desc(Summary.updated_at), desc(Summary.created_at))
        .all()
    ):
        summary_by_filing.setdefault(s.filing_id, s)

    items: list[dict] = []
    for f in heads:
        company = f.company
        if company is None:
            continue
        prior = prior_by_filing.get(f.id)
        prior_xbrl = prior_xbrl_by_id.get(prior.id) if prior else None
        what_changed = compute_what_changed(f.xbrl_data, prior_xbrl)
        status = _summary_status(summary_by_filing.get(f.id), f.id)
        items.append({
            "filing_id": f.id,
            "accession_number": f.accession_number,
            "company": {"id": company.id, "ticker": company.ticker, "name": company.name},
            "filing_type": f.filing_type,
            "filing_date": f.filing_date.isoformat() if f.filing_date else None,
            "period_end_date": f.period_end_date.isoformat() if f.period_end_date else None,
            "summary_id": status["summary_id"],
            "summary_status": status["summary_status"],
            "what_changed": what_changed,
        })
    return items
