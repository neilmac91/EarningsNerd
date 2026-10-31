"""Personalised dashboard feed — the Phase 3 "what changed" engine.

`compose_feed` returns the NEWEST eligible filing (10-K/10-Q, plus 20-F/40-F behind
ENABLE_FPI_FILINGS) for EACH of a user's watched companies — one card per company, companies ordered
by that filing's date, newest first (DB-only, N+1-free). Each is annotated with a **deterministic**
"what changed vs the prior filing" headline derived from the filing's stored ``xbrl_data`` (no LLM,
no network). The richer narrative diff stays on-demand (the summary), per the cost-aware plan.

`compute_what_changed` is a pure function (unit-testable on dicts) that enforces hard invariants so
corrupt/misaligned XBRL never produces a misleading headline:
  * revenue must be finite and ≥ 0;
  * sign(EPS) must match sign(net income) for the period (basic EPS where the filing reports it);
otherwise the offending metric is dropped (never the whole row) and ``data_quality`` is "partial".
When nothing usable remains the headline is ``None`` and the card falls back to a neutral line.
Every line compares the filing's own period with ONE comparison period (``_comparison_period``): the
prior filing's period of report, the period the change report's basis line names. Each line's prior
side is this filing's own figure for that period where it reports one (restated or split-adjusted
since, as a 10-K reports its prior year), else the prior filing's; a line with neither is withheld,
never compared with another period (a 10-Q's own comparative is the year-ago quarter). EPS is one
line, diluted where both sides of the pair carry it and basic otherwise, each side from the same key
(``_eps_line``), and is never differenced across a share split (invariant 3).
"""
from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any, NamedTuple, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session, defer, joinedload

from app.models import Filing, Summary, SummaryGenerationProgress, Watchlist
from app.services import metric_delta_service
from app.services.copilot_tools import canonical_unit
from app.services.edgar.models import MetricChange
from app.services.facts.fiscal_naming import ANNUAL_FORMS, DRIFT_DAYS, years_back
from app.services.filing_section_service import (
    ACCESS_FULL,
    ACCESS_NONE,
    NO_SECTION_ACCESS,
    SectionAccess,
    wording_change_summaries,
)
from app.services.section_review_service import review_progress
from app.services.summary_generation_service import progress_read_status
from app.services.summary_placeholders import is_stored_summary_ready

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

# (xbrl_data key, human label) in headline priority order, each label /analysis's name for the key
# (trend_analysis/periods.py _CONCEPT_LABELS), one entry to a line: frontend/tests/unit/metricLabelParity.spec.ts
# reads this list as text and holds every label to /analysis's.
# The financial-institution component keys are self-gating: a bank's xbrl_data carries
# net/noninterest income (not "revenue"), while a non-financial filer carries "revenue" (not the
# components), so only the applicable rows render. The two EPS keys are one line: _eps_line picks one
# of them per pair, so a report never shows both.
_DELTA_METRICS = [
    ("revenue", "Revenue"),
    ("net_interest_income", "Net interest income"),
    ("noninterest_income", "Noninterest income"),
    ("net_income", "Net income"),
    ("eps_diluted", "EPS (diluted)"),
    ("earnings_per_share", "EPS (basic)"),
]
# The EPS line's keys, in preference order: diluted, the figure investors quote (P1.5), then basic.
_EPS_METRICS = ("eps_diluted", "earnings_per_share")
_BASIC_EPS = "earnings_per_share"

_DIRECTION_WORD = {"increase": "up", "decrease": "down", "unchanged": "flat"}

# Invariant 3: a share split moves EPS by its ratio while net income stays; a quarter's buybacks or issuance move the
# implied share count by a few percent. 1.4, not 1.5, so a 3-for-2 split (exactly 1.5) is caught. EPS is stated to
# the cent, so each side's implied count is bounded by half a cent of EPS either way.
_SPLIT_RATIO = 1.4
_EPS_HALF_CENT = 0.005


# --------------------------------------------------------------------------- pure delta

class _Point(NamedTuple):
    """One stored figure: its period end, value and XBRL concept, and its start where the extractor kept one."""

    period: str
    value: float
    tag: Optional[str]
    start: Optional[str]


def _series_desc(xbrl: Optional[dict], metric: str) -> list[_Point]:
    """A metric's usable figures in a filing's XBRL, newest period first.

    ``tag`` (``raw_tag``) is the underlying XBRL concept the value came from (None for legacy/pre-fix series); it
    lets the caller detect a concept that flips between filings (the apples-to-oranges delta bug). ``start``
    (``period_start``) is the source fact's own start where the extractor kept one: None for a statement-derived
    bank line or an older blob.
    """
    out: list[_Point] = []
    series = (xbrl or {}).get(metric) if isinstance(xbrl, dict) else None
    if isinstance(series, list):
        for entry in series:
            if not isinstance(entry, dict):
                continue
            period, value, start = entry.get("period"), entry.get("value"), entry.get("period_start")
            if period is None or not isinstance(value, (int, float)) or isinstance(value, bool):
                continue
            out.append(_Point(str(period), float(value), entry.get("raw_tag"), start if isinstance(start, str) else None))
    out.sort(key=lambda point: point.period, reverse=True)
    return out


def _value_at(xbrl: Optional[dict], metric: str, period: Optional[str]) -> Optional[tuple[float, Optional[str]]]:
    """The metric's (value, raw_tag) for exactly ``period`` in a filing's XBRL, or None."""
    point = next((point for point in _series_desc(xbrl, metric) if point.period == period), None)
    return (point.value, point.tag) if point is not None else None


def _newest_period(xbrl: Optional[dict], before: Optional[str] = None) -> Optional[str]:
    """The newest period a filing's XBRL reports for any of What changed's metrics, before ``before`` when
    given: for a filing's own blob, its own period; for a prior filing's, the period the prior filing reported."""
    newest: Optional[str] = None
    for metric, _label in _DELTA_METRICS:
        period = next((p.period for p in _series_desc(xbrl, metric) if before is None or p.period < before), None)
        if period is not None and (newest is None or period > newest):
            newest = period
    return newest


def _day(value: Any) -> Optional[date]:
    """A period end as a date, from an ISO string, a date or a datetime (``Filing.period_end_date``), else None."""
    try:
        return date.fromisoformat(str(value)[:10]) if value is not None else None
    except ValueError:
        return None


def _comparison_period(
    current_xbrl: Optional[dict], prior_xbrl: Optional[dict], own_period: Optional[str],
    prior_period_end: Any, form: Optional[str],
) -> Optional[date]:
    """The one period every line's prior side is for, or None when the report compares nothing.

    It is the prior filing's period of report, the date the change report's basis line prints ("against the 10-Q
    for the quarter ended ..."). Without one (no prior filing, or a feed pair whose prior row has no period end) it
    is the newest period the prior filing's XBRL reports before this filing's; without that either, the period one
    fiscal year before this filing's (``years_back``, a 52/53-week year's drift allowed) for a report whose basis
    reads "Year over year" (``ANNUAL_FORMS``, the forms ``change_report_service._comparison_basis`` labels so), and
    nothing for any other: a 10-Q's own comparative is the year-ago quarter, never the quarter its basis names.
    A period within ``DRIFT_DAYS`` of this filing's own, or after it, is no prior period.
    """
    own = _day(own_period)
    target = _day(prior_period_end)
    if target is None and prior_xbrl is not None:
        target = _day(_newest_period(prior_xbrl, before=own_period))
    if target is None and own is not None and (form or "").upper().split("/")[0] in ANNUAL_FORMS:
        own_days = {_day(p.period) for metric, _label in _DELTA_METRICS for p in _series_desc(current_xbrl, metric)}
        target = max((day for day in own_days if day is not None and years_back(day, own) == 1), default=None)
    if own is None or target is None or (own - target).days <= DRIFT_DAYS:
        return None
    return target


def _span(point: _Point) -> Optional[int]:
    """A figure's length in days, or None without a start."""
    start, end = _day(point.start), _day(point.period)
    return (end - start).days if start is not None and end is not None else None


def _point_for(xbrl: Optional[dict], metric: str, target: date, current: _Point) -> Optional[_Point]:
    """The metric's figure in ``xbrl`` for the comparison period: its end within ``DRIFT_DAYS`` of ``target`` (a
    period of report and an XBRL context can name one period end a few days apart, facts/filing_scope.py), and its
    length the current figure's where both carry a start (a 16-week quarter is not a 12-week one, nor a quarter a
    year)."""
    for point in _series_desc(xbrl, metric):
        day = _day(point.period)
        if day is None or abs((day - target).days) > DRIFT_DAYS:
            continue
        spans = (_span(point), _span(current))
        if None in spans or abs(spans[0] - spans[1]) <= DRIFT_DAYS:
            return point
    return None


class _Line(NamedTuple):
    """One of What changed's lines, and the filing and period each side came from (invariants 2 and 3)."""

    metric: str
    current: float
    current_period: str
    current_tag: Optional[str]
    prior: Optional[float] = None
    prior_period: Optional[str] = None
    prior_tag: Optional[str] = None
    prior_xbrl: Optional[dict] = None


def _line(
    metric: str, current_xbrl: Optional[dict], prior_xbrl: Optional[dict], own_period: str, target: date,
) -> Optional[_Line]:
    """A metric's line: its figure for exactly this filing's own period (a series that stops before it never
    stands for it), against its figure for the comparison period, this filing's own where it reports that period,
    else the prior filing's; no prior side when neither does, and the line is not shown."""
    current = next((point for point in _series_desc(current_xbrl, metric) if point.period == own_period), None)
    if current is None:
        return None
    line = _Line(metric, current.value, own_period, current.tag)
    for source in (current_xbrl, prior_xbrl):
        hit = _point_for(source, metric, target, current)
        if hit is not None:
            return line._replace(prior=hit.value, prior_period=hit.period, prior_tag=hit.tag, prior_xbrl=source)
    return line


def _eps_line(
    current_xbrl: Optional[dict], prior_xbrl: Optional[dict], own_period: str, target: date,
) -> Optional[_Line]:
    """What changed's one EPS line, or None when the filing reports no EPS for its own period.

    Both sides come from ONE key, the first of ``_EPS_METRICS`` whose pair is complete, each side as every line takes
    it (``_line``). A blob stored before P1.5 (2026-06-14) or by the companyfacts fallback carries no
    ``eps_diluted``, so a pair that needs it from such a blob takes the basic line, though a 10-K's own restated
    prior year still completes the diluted pair. (``earnings_per_share`` itself can hold a diluted figure, on either
    side, where a filer tagged no basic EPS: E260.)

    A diluted pair is not used where either side's diluted figure exceeds its filing's basic EPS for the same
    period (the check facts/reconcile.py makes): the line falls to basic. When no key completes a pair, the first
    key with a current figure comes back without a prior: no EPS line shows, but invariant 2 still checks net
    income's current sign against it.
    """
    guard_only: Optional[_Line] = None
    for metric in _EPS_METRICS:
        line = _line(metric, current_xbrl, prior_xbrl, own_period, target)
        if line is None:
            continue
        if line.prior is not None and _diluted_within_basic(line, current_xbrl):
            return line
        if guard_only is None:
            guard_only = _Line(line.metric, line.current, line.current_period, line.current_tag)
    return guard_only


def _diluted_within_basic(line: _Line, current_xbrl: Optional[dict]) -> bool:
    """False where a diluted line's figure, on either side, exceeds its filing's basic EPS for that period."""
    if line.metric != "eps_diluted":
        return True
    for xbrl, period, value in ((current_xbrl, line.current_period, line.current), (line.prior_xbrl, line.prior_period, line.prior)):
        basic = _value_at(xbrl, _BASIC_EPS, period)
        if basic is not None and value is not None and value > basic[0] + 1e-9:
            return False
    return True


def _sign_eps(xbrl: Optional[dict], period: Optional[str], shown: float) -> float:
    """The EPS figure invariant 2 holds net income's sign to: the filing's basic EPS for the period where it
    reports one, as facts/reconcile.py checks, else the figure shown. A diluted figure can fall below zero while
    basic EPS and net income stay above it (a gain the diluted numerator leaves out, such as a warrant
    liability's fair-value gain), so basic EPS is the like-for-like figure."""
    basic = _value_at(xbrl, _BASIC_EPS, period)
    return basic[0] if basic is not None else shown


def _share_basis_moved(line: _Line, current_xbrl: Optional[dict]) -> bool:
    """Whether a share split falls between the EPS line's sides. Checked only where the prior side is the prior
    filing's own figure (this filing's figure for a period is on its own share basis; sequential 10-Qs share no
    period, so a 10-Q restates no prior quarter): true where the implied share counts, each side's net income over
    its filing's EPS for that period (basic where reported, ``_sign_eps``), differ by more than ``_SPLIT_RATIO`` even
    at the ends of each EPS figure's rounding. A side without net income, or with EPS within rounding of zero,
    proves nothing."""
    if line.prior is None or line.prior_xbrl is current_xbrl:
        return False
    counts = []
    for xbrl, period, shown in ((current_xbrl, line.current_period, line.current), (line.prior_xbrl, line.prior_period, line.prior)):
        eps, net_income = abs(_sign_eps(xbrl, period, shown)), _value_at(xbrl, "net_income", period)
        if net_income is None or net_income[0] == 0 or eps <= _EPS_HALF_CENT:
            return False
        counts.append((abs(net_income[0]) / (eps + _EPS_HALF_CENT), abs(net_income[0]) / (eps - _EPS_HALF_CENT)))
    (current_low, current_high), (prior_low, prior_high) = counts
    return current_low > prior_high * _SPLIT_RATIO or current_high * _SPLIT_RATIO < prior_low


def reporting_currency(xbrl: Optional[dict]) -> Optional[str]:
    """A filing's as-filed reporting currency from its stored XBRL, as an ISO 4217 code ("USD",
    "CNY"). None when the extraction never resolved one."""
    unit = canonical_unit(xbrl.get("reporting_currency")) if isinstance(xbrl, dict) else None
    return unit if unit and re.fullmatch(r"[A-Z]{3}", unit) else None


def compute_what_changed(
    current_xbrl: Optional[dict], prior_xbrl: Optional[dict], *, prior_period_end: Any = None, form: Optional[str] = None,
) -> Optional[dict]:
    """Deterministic period-over-period headline from stored XBRL. None if nothing usable.

    ``prior_period_end`` is the prior filing's period of report (``Filing.period_end_date``), None without a prior
    filing; ``form`` is this filing's form type. Both callers hold them (``compose_feed``,
    ``change_report_service.assemble_report``); ``_comparison_period`` chooses the one period compared from them.
    """
    # Never difference amounts across reporting currencies. An issuer that changes its reporting
    # currency restates its comparatives in the new one, so only this filing's own figure for the
    # comparison period can stand in (a 10-K's restated year; a 10-Q restates no prior quarter, so
    # its lines are withheld). An unknown currency on either side proves no change, so the prior
    # filing is used as before.
    current_currency, prior_currency = reporting_currency(current_xbrl), reporting_currency(prior_xbrl)
    if current_currency and prior_currency and current_currency != prior_currency:
        prior_xbrl = None

    own_period = _newest_period(current_xbrl)
    target = _comparison_period(current_xbrl, prior_xbrl, own_period, prior_period_end, form)
    if own_period is None or target is None:
        return None
    data: dict[str, tuple[float, Optional[float]]] = {}
    tags: dict[str, tuple[Optional[str], Optional[str]]] = {}
    eps_line = _eps_line(current_xbrl, prior_xbrl, own_period, target)
    lines = [_line(metric, current_xbrl, prior_xbrl, own_period, target)
             for metric, _label in _DELTA_METRICS if metric not in _EPS_METRICS]  # one EPS line, chosen above
    for line in (*lines, eps_line):
        if line is not None:
            data[line.metric] = (line.current, line.prior)
            tags[line.metric] = (line.current_tag, line.prior_tag)
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

    # Invariant 2: sign(EPS) must match sign(net income) — checked for current AND prior periods. The EPS
    # figure is each side's basic EPS for its period where its filing reports one, else the line shown
    # (_sign_eps), and the prior side's net income is that same filing's for that period where it reports
    # one, so a year this filing restates is held to its restated net income. Disagreement in either period
    # ⇒ distrust both metrics: the EPS line and net income.
    if eps_line is not None and eps_line.metric in data and "net_income" in data:
        eps = _sign_eps(current_xbrl, eps_line.current_period, eps_line.current)
        prior_eps = (
            _sign_eps(eps_line.prior_xbrl, eps_line.prior_period, eps_line.prior)
            if eps_line.prior is not None else None
        )
        net_income, prior_net_income = data["net_income"]
        same_filing = _value_at(eps_line.prior_xbrl, "net_income", eps_line.prior_period)
        if eps_line.prior is not None and same_filing is not None:
            prior_net_income = same_filing[0]
        mismatch_current = eps != 0 and net_income != 0 and (eps > 0) != (net_income > 0)
        mismatch_prior = (
            prior_eps is not None and prior_net_income is not None
            and prior_eps != 0 and prior_net_income != 0
            and (prior_eps > 0) != (prior_net_income > 0)
        )
        if mismatch_current or mismatch_prior:
            del data[eps_line.metric]
            del data["net_income"]
            data_quality = "partial"

    # Invariant 3: never difference EPS across a share split (_share_basis_moved); net income stands.
    if eps_line is not None and eps_line.metric in data and _share_basis_moved(eps_line, current_xbrl):
        del data[eps_line.metric]
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

def _summary_status(summary: Optional[Summary], progress: Optional[SummaryGenerationProgress]) -> dict:
    """Mirror the watchlist-insights status taxonomy (ready/placeholder/generating/error/missing).
    ``progress`` is the filing's generation-progress row, consulted only without a summary, through the
    insights' own reading of it (``progress_read_status``)."""
    if summary is not None:
        ready = is_stored_summary_ready(summary)
        return {"summary_id": summary.id, "summary_status": "ready" if ready else "placeholder"}

    status, _snapshot = progress_read_status(progress)
    return {"summary_id": None, "summary_status": status}


def _prior_same_form(company_filings_desc: list[Filing], current: Filing) -> Optional[Filing]:
    """Previous filing of the SAME form type (10-Q→prior 10-Q = QoQ, 10-K→prior 10-K = YoY)."""
    same = [f for f in company_filings_desc if f.filing_type == current.filing_type]
    for i, f in enumerate(same):
        if f.id == current.id:
            return same[i + 1] if i + 1 < len(same) else None
    return None


# --------------------------------------------------------------------------- composition

def _wording_changes(
    db: Session, user_id: int, filings: list[Filing], access: SectionAccess
) -> dict[int, Optional[dict]]:
    """Per head filing, the Item 1A wording-change counts the card shows (from the cached
    comparison summary; nothing when the filing has no comparison yet) and, for a viewer who gets
    the full change list, the progress of their review of it, reconciled against the live
    comparison exactly as the review endpoint reports it (``section_review_service.review_progress``:
    a re-extraction that retired ids or the receipt reopens the review here too). Nothing at all
    while the feature is off or the viewer has no access."""
    if access.level == ACCESS_NONE or not filings:
        return {}
    summaries = wording_change_summaries(db, [f.id for f in filings])
    progress: dict[int, dict] = {}
    if access.level == ACCESS_FULL and summaries:
        progress = review_progress(db, user_id, [f for f in filings if f.id in summaries])
    out: dict[int, Optional[dict]] = {}
    for filing_id, summary in summaries.items():
        review = progress.get(filing_id, {"labeled": 0, "completed_at": None}) if access.level == ACCESS_FULL else None
        out[filing_id] = {**summary, "review": review}
    return out


def compose_feed(
    db: Session, user_id: int, limit: int = 20, *, section_access: SectionAccess = NO_SECTION_ACCESS
) -> list[dict]:
    """Each watched company's NEWEST eligible filing (10-K/10-Q, plus 20-F/40-F behind
    ENABLE_FPI_FILINGS) — one item per company, companies ordered by that filing's date, newest
    first. ``limit`` caps the number of COMPANIES shown (not filings). Each item carries a
    deterministic "what changed" headline + summary status and, when ``section_access`` grants the
    viewer the Item 1A wording diff, its change counts (``wording_changes``, with the viewer's
    review progress for full access). DB-only; no live EDGAR on render."""
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

    # Generation progress for the heads without a summary, read in this session. A helper that opens
    # its own session per filing would need a second pooled connection while this one is held, and
    # four such requests deadlock the four-slot pool (lessons/ops-one-connection-per-request-unit.md).
    pending_ids = [fid for fid in filing_ids if fid not in summary_by_filing]
    progress_by_filing: dict[int, SummaryGenerationProgress] = {}
    if pending_ids:
        progress_by_filing = {
            progress.filing_id: progress
            for progress in db.query(SummaryGenerationProgress)
            .filter(SummaryGenerationProgress.filing_id.in_(pending_ids))
            .all()
        }

    wording_by_filing = _wording_changes(db, user_id, heads, section_access)

    items: list[dict] = []
    for f in heads:
        company = f.company
        if company is None:
            continue
        prior = prior_by_filing.get(f.id)
        prior_xbrl = prior_xbrl_by_id.get(prior.id) if prior else None
        what_changed = compute_what_changed(
            f.xbrl_data, prior_xbrl, prior_period_end=prior.period_end_date if prior else None, form=f.filing_type,
        )
        status = _summary_status(summary_by_filing.get(f.id), progress_by_filing.get(f.id))
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
            "wording_changes": wording_by_filing.get(f.id),
        })
    return items
