"""Normalize the standardized XBRL metrics we already extract into queryable `financial_fact` rows.

`normalize_standardized_to_facts` is pure (dict in → list[dict] out, unit-testable). `upsert_facts`
writes them while maintaining the restatement-safe `is_latest` flag.

Per-filing facts reuse `xbrl_service.extract_standardized_metrics`. The local reconciliation
gate rejects impossible values and records warnings for implausible ones. Companyfacts supplies
FY and fiscal quarters, with compatible cumulative-flow calculations and reported-only EPS.
Both paths retain calculation operands and source-check evidence.
"""
from __future__ import annotations

import asyncio
import logging  # noqa: F401 - preserve the facade import surface
import math
from concurrent.futures import TimeoutError as FuturesTimeoutError  # noqa: F401 - preserve the facade import surface
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Optional

from app.services.event_loop import get_app_loop  # noqa: F401 - preserve the facade import surface
from app.services.fact_provenance import fact_operand, provenance_for_fact, published_value  # noqa: F401 - preserve the facade import surface
from app.services.facts.calendar import (
    _fiscal_year_windows, _label_quarters, fiscal_duration_values, fiscal_year_labels, reported_fiscal_year,  # noqa: F401 - preserve the facade import surface
)
from app.services.facts.lineage import (
    annotate_filing_calculations, authoritative_reconciliation, local_reconciliation,
)
from app.services.facts.quarterly import (
    FINAL_QUARTER_WINDOW, QUARTER_WINDOW, derive_cumulative_quarters, derive_quarter_sum_fallback,  # noqa: F401 - preserve the facade import surface
    reported_fact, same_period_provenance, same_scope,  # noqa: F401 - preserve the facade import surface
)

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_

from app.models import Company, Filing, FinancialFact, Watchlist

from app.services.facts.concepts import (
    AFFECTED_FINANCIAL_CONCEPTS,
    COMPANYFACTS_DURATION_TAGS,
    COMPANYFACTS_INFLIGHT_WAIT_SECONDS,
    COMPANYFACTS_INSTANT_TAGS,
    COMPANYFACTS_SYNC_TIMEOUT_SECONDS,
    CROSS_CHECK_TOLERANCE,
    HEADLINE_GAAP_TAGS,
    NON_NEGATIVE_CONCEPTS,
    _CF_ANNUAL_WINDOW,
    _CF_QUARTER_WINDOW,
    _CF_YTD6_WINDOW,
    _CF_YTD9_WINDOW,
    _CONCEPT_UNITS,
    _FI_SKIPPED_CONCEPTS,
    _INSTANT_HEADLINE,
    _MAGNITUDE_TOLERANCE,
    _QUARTER_PERIODS,
    _VALID_FP,
    _classify_duration,
    _duration_start,
    _fiscal_period,
    _is_financial_sic,
    _parse_date,
    _unit_for,
)
from app.services.facts.companyfacts import _collect_companyfacts_values, normalize_companyfacts
from app.services.facts.derive import derive_q4_facts, derive_same_period_metrics
from app.services.facts.transport import (
    _fetch_companyfacts_async,
    _fetch_companyfacts_sync,
    _running_loop_in_this_thread,
    logger,
)

__all__ = [
    'AFFECTED_FINANCIAL_CONCEPTS',
    'COMPANYFACTS_DURATION_TAGS',
    'COMPANYFACTS_INFLIGHT_WAIT_SECONDS',
    'COMPANYFACTS_INSTANT_TAGS',
    'COMPANYFACTS_SYNC_TIMEOUT_SECONDS',
    'CROSS_CHECK_TOLERANCE',
    'HEADLINE_GAAP_TAGS',
    'NON_NEGATIVE_CONCEPTS',
    '_CF_ANNUAL_WINDOW',
    '_CF_QUARTER_WINDOW',
    '_CF_YTD6_WINDOW',
    '_CF_YTD9_WINDOW',
    '_CONCEPT_UNITS',
    '_FI_SKIPPED_CONCEPTS',
    '_INSTANT_HEADLINE',
    '_MAGNITUDE_TOLERANCE',
    '_QUARTER_PERIODS',
    '_VALID_FP',
    '_classify_duration',
    '_collect_companyfacts_values',
    '_companyfacts_fresh_result',
    '_duration_start',
    '_fetch_companyfacts_async',
    '_fetch_companyfacts_sync',
    '_fiscal_period',
    '_fiscal_year_windows',
    '_fundamentals_payload',
    '_inflight_syncs',
    '_is_financial_sic',
    '_label_quarters',
    '_lock_fact_companies',
    '_parse_date',
    '_persist_companyfacts_payload',
    '_prior_values',
    '_running_loop_in_this_thread',
    '_unit_for',
    'backfill_company_sic',
    'backfill_facts',
    'cross_check_facts',
    'derive_q4_facts',
    'derive_same_period_metrics',
    'extract_authoritative_values',
    'get_filing_fundamentals',
    'ingest_companyfacts',
    'ingest_companyfacts_by_id',
    'logger',
    'normalize_companyfacts',
    'normalize_standardized_to_facts',
    'process_filing_facts',
    'reconcile_facts',
    'remediate_industry_facts',
    'sync_companyfacts_batch',
    'upsert_facts',
    'upsert_facts_bulk',
]


def normalize_standardized_to_facts(
    company_id: int,
    filing_id: Optional[int],
    accession: Optional[str],
    form: Optional[str],
    standardized: Optional[dict],
) -> list[dict[str, Any]]:
    """Turn standardized metrics into fact dicts — one row per concept *per reported period*.

    A 10-K's XBRL carries the current year plus comparative prior years, so each concept's
    ``series`` (from ``extract_standardized_metrics``) yields several periods. We emit a row for
    every period point, attributed to this filing's accession; the identity key includes
    ``period_end`` so they're distinct, and the restatement-safe ``is_latest`` logic in
    ``upsert_facts`` keeps the newest filing's value current when periods overlap across filings.
    Falls back to the single ``current`` entry when no ``series`` is present. Tolerant of
    missing/malformed entries (skipped, never raised).
    """
    if not accession or not isinstance(standardized, dict):
        return []
    facts: list[dict[str, Any]] = []
    for concept, entry in standardized.items():
        if not isinstance(entry, dict):
            continue
        points = entry.get("series")
        if not isinstance(points, list) or not points:
            current = entry.get("current")
            points = [current] if isinstance(current, dict) else []
        for point in points:
            if not isinstance(point, dict):
                continue
            value = point.get("value")
            # Exclude bool (a subclass of int) and non-numeric values.
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                continue
            period_end = _parse_date(point.get("period"))
            if period_end is None:
                continue
            # Each point may carry the form that reported it; fall back to the filing's form.
            point_form = point.get("form") or form
            facts.append(
                {
                    "company_id": company_id,
                    "filing_id": filing_id,
                    "concept": concept,
                    # The underlying XBRL tag this value came from (e.g. "us-gaap:InterestIncomeExpenseNet").
                    # Recorded for audit + so a concept that flips between filings can be detected.
                    "raw_tag": point.get("raw_tag"),
                    # Derived monetary metrics (e.g. free_cash_flow, computed from OCF − capex)
                    # don't carry a per-point currency, so fall back to the filing's overall
                    # reporting currency rather than silently defaulting to USD.
                    "unit": _unit_for(concept, point.get("currency") or standardized.get("reporting_currency")),
                    # The source fact's own reported start, when extraction preserved one. Absent
                    # for instant facts, computed aggregates, and any period whose equal-valued
                    # source facts disagreed — readers must treat NULL as "duration unknown" and
                    # stay conservative, never infer a year from the form or the fiscal label.
                    # Forward-only: existing rows keep their NULL, since `upsert_facts` skips an
                    # identity that already exists.
                    "period_start": _duration_start(point.get("period_start"), period_end),
                    "period_end": period_end,
                    "fiscal_year": point.get("fiscal_year") or period_end.year,
                    "fiscal_period": point.get("fiscal_period") or _fiscal_period(point_form),
                    "value": float(value),
                    "form": point_form,
                    "accession": accession,
                    "source": "edgar_xbrl",
                }
            )
    return annotate_filing_calculations(facts, initialize_reported=True)


def reconcile_facts(
    facts: list[dict[str, Any]],
    *,
    prior_values: Optional[dict[str, float]] = None,
    period_of_report: Optional[date] = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Local-invariant reconciliation gate (pure, no network — strategy §3.5).

    Operates on one filing's batch of normalized facts. Returns ``(accepted, rejected)``:

    * **rejected** — physically impossible values (negative on a non-negative concept). Dropped,
      never stored, logged as ``fact_reconciliation_reject``.
    * **accepted** — every other fact, each annotated with a ``reconciled`` bool: ``True`` if it
      passed all soft checks, ``False`` if any flagged it. Flagged facts are still stored so the UI
      can show them with a quality badge ("reconciled or visibly flagged"), never silently trusted.

    Soft checks: zero where the prior period was non-zero; >1 order-of-magnitude swing vs prior
    (scale bug); sign(EPS) != sign(net_income) (the MU class); diluted EPS > basic EPS; and
    ``period_end`` != ``period_of_report`` for the current period (the ADI class).

    **Period-aware.** Facts are grouped by ``period_end`` and processed oldest→newest so that
    cross-concept checks (EPS vs net income) only ever compare like-period values, and each period's
    "prior" is its immediate predecessor — seeded from the DB value before the earliest period
    (``prior_values``) then chained across in-batch periods (so a multi-period backfill compares a
    year against the year before it, even when both arrive in the same batch). A single-filing v1
    batch is one group, so this reduces to the obvious behaviour. The period-correctness check
    applies only to the latest (current) period; comparative prior periods legitimately differ.
    """

    def _num(v: Any) -> Optional[float]:
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None

    # Group by reporting period, oldest first (None-period facts last — they carry no position).
    groups: dict[Any, list[dict[str, Any]]] = {}
    for fact in facts:
        groups.setdefault(fact.get("period_end"), []).append(fact)
    ordered_periods = sorted(groups, key=lambda pe: (pe is None, pe))
    dated = [pe for pe in ordered_periods if pe is not None]
    latest_period = dated[-1] if dated else None

    running_prior: dict[str, Optional[float]] = dict(prior_values or {})
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for pe in ordered_periods:
        group = groups[pe]
        by_concept = {f["concept"]: _num(f.get("value")) for f in group}
        net_income = by_concept.get("net_income")
        eps_basic = by_concept.get("earnings_per_share")
        eps_diluted = by_concept.get("eps_diluted")
        eps_sign_mismatch = (
            net_income not in (None, 0)
            and eps_basic not in (None, 0)
            and (net_income > 0) != (eps_basic > 0)
        )
        diluted_exceeds_basic = (
            eps_basic is not None and eps_diluted is not None and eps_diluted > eps_basic + 1e-9
        )

        period_values: dict[str, float] = {}
        for fact in group:
            concept = fact["concept"]
            value = _num(fact.get("value"))

            if concept in NON_NEGATIVE_CONCEPTS and value is not None and value < 0:
                rejected.append(fact)
                logger.warning(
                    "fact_reconciliation_reject concept=%s value=%s reason=negative",
                    concept,
                    fact.get("value"),
                )
                continue

            prior = _num(running_prior.get(concept))
            reasons: list[str] = []

            if value == 0 and prior not in (None, 0):
                reasons.append("zero_where_prior_nonzero")
            if value not in (None, 0) and prior not in (None, 0):
                ratio = abs(value) / abs(prior)
                if ratio > _MAGNITUDE_TOLERANCE or ratio < 1.0 / _MAGNITUDE_TOLERANCE:
                    reasons.append("magnitude_vs_prior")
            if concept in ("earnings_per_share", "eps_diluted") and eps_sign_mismatch:
                reasons.append("eps_sign_vs_net_income")
            if concept == "eps_diluted" and diluted_exceeds_basic:
                reasons.append("diluted_gt_basic")
            if (
                period_of_report is not None
                and pe is not None
                and pe == latest_period
                and pe != period_of_report
            ):
                reasons.append("period_mismatch")

            if reasons:
                logger.info(
                    "fact_reconciliation_flag concept=%s value=%s reasons=%s",
                    concept,
                    fact.get("value"),
                    ",".join(reasons),
                )
            accepted.append(local_reconciliation(fact, reasons))
            if value is not None:
                period_values[concept] = value

        # This period's values become the prior for the next (newer) period in the batch.
        running_prior.update(period_values)

    return annotate_filing_calculations(accepted), rejected


def _prior_values(
    db: Session, company_id: int, concepts: set[str], before: Optional[date]
) -> dict[str, float]:
    """Most-recent ``is_latest`` value per concept strictly before ``before`` (period_end).

    Feeds the gate's zero-vs-prior and magnitude checks. One query for the whole batch.
    """
    if not concepts or before is None:
        return {}
    rows = (
        db.query(FinancialFact.concept, FinancialFact.value)
        .filter(
            FinancialFact.company_id == company_id,
            FinancialFact.concept.in_(list(concepts)),
            FinancialFact.is_latest.is_(True),
            FinancialFact.period_end < before,
        )
        .order_by(FinancialFact.concept.asc(), FinancialFact.period_end.desc())
        .all()
    )
    out: dict[str, float] = {}
    for concept, value in rows:
        if concept not in out and value is not None:  # first row per concept = most recent prior
            out[concept] = float(value)
    return out


# --- Authoritative cross-check (strategy §3.5 step 2) ---------------------------------------
# Compare headline figures against SEC's own structured companyfacts API and prefer it on
# mismatch. Runs in the backfill (not the request path); best-effort — if companyfacts is
# unavailable, the invariant-gate result stands.

def extract_authoritative_values(companyfacts: Any) -> dict[tuple[str, date], float]:
    """Map ``(headline concept, period_end) -> authoritative annual USD value`` from companyfacts.

    Reads ``facts."us-gaap".<tag>.units.USD[]``. For duration concepts (revenue, net income)
    only the ~annual duration is kept (the FY value our facts carry); for the instant concept
    (total assets) the period-end value is taken. Pure/defensive — ``{}`` for anything malformed.
    """
    out: dict[tuple[str, date], float] = {}
    if not isinstance(companyfacts, dict):
        return out
    facts_root = companyfacts.get("facts")
    usgaap = facts_root.get("us-gaap") if isinstance(facts_root, dict) else None
    if not isinstance(usgaap, dict):
        return out

    for concept, tags in HEADLINE_GAAP_TAGS.items():
        instant = concept in _INSTANT_HEADLINE
        for tag in tags:
            node = usgaap.get(tag)
            units = node.get("units") if isinstance(node, dict) else None
            items = units.get("USD") if isinstance(units, dict) else None
            if not isinstance(items, list):
                continue
            best: dict[date, tuple[int, float]] = {}  # period_end -> (duration penalty, value)
            for item in items:
                if not isinstance(item, dict):
                    continue
                value = item.get("val")
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    continue
                period_end = _parse_date(item.get("end"))
                if period_end is None:
                    continue
                if instant:
                    penalty = 0
                else:
                    start = _parse_date(item.get("start"))
                    if start is None:
                        continue
                    penalty = abs((period_end - start).days - 365)
                    # Tight band: 52/53-week fiscal years stay within ~15 days of 365, but a
                    # 9-month YTD (~273d, penalty ~92) or 6-month (~181d) must NOT pass as annual.
                    if penalty > 30:
                        continue
                prev = best.get(period_end)
                # companyfacts lists facts in filing order, so a later item with an equal penalty
                # is a newer restatement — let it win the tie (<=, not <).
                if prev is None or penalty <= prev[0]:
                    best[period_end] = (penalty, float(value))
            for period_end, (_penalty, value) in best.items():
                out.setdefault((concept, period_end), value)  # first tag with data wins
    return out


def cross_check_facts(
    facts: list[dict[str, Any]], authoritative: dict[tuple[str, date], float]
) -> list[dict[str, Any]]:
    """Reconcile headline facts against authoritative companyfacts values.

    For a headline fact with an authoritative value for its period: within tolerance → confirm
    (``reconciled=True``, clearing any heuristic flag); beyond tolerance → replace the value with
    the authoritative one (``source='companyfacts'``, ``reconciled=True``) and log a mismatch.
    Non-headline facts and those without an authoritative reference are returned unchanged.
    """
    if not authoritative:
        return facts
    out: list[dict[str, Any]] = []
    for fact in facts:
        concept = fact.get("concept")
        period_end = fact.get("period_end")
        # The authoritative companyfacts map is USD-only. Never cross-check (or overwrite) a fact
        # reported in a non-USD currency against it — that would replace a native CNY/EUR value with
        # a USD convenience figure (a ~7x distortion for an RMB filer like Alibaba).
        unit = fact.get("unit")
        if unit and unit != "USD":
            out.append(fact)
            continue
        auth = authoritative.get((concept, period_end)) if concept in HEADLINE_GAAP_TAGS else None
        if auth is None:
            out.append(fact)
            continue
        original = fact
        fact = dict(fact)
        value = fact.get("value")
        numeric = value if isinstance(value, (int, float)) and not isinstance(value, bool) else None
        if numeric is not None and abs(numeric - auth) / (abs(auth) or 1.0) <= CROSS_CHECK_TOLERANCE:
            fact["reconciled"] = True  # authoritative confirms → clear any heuristic flag
        else:
            if numeric is not None:
                logger.info(
                    "fact_reconciliation_mismatch concept=%s period=%s parsed=%s authoritative=%s",
                    concept, period_end, value, auth,
                )
            fact["value"] = auth
            fact["source"] = "companyfacts"
            fact["reconciled"] = True
        out.append(authoritative_reconciliation(fact, original, auth))
    return annotate_filing_calculations(out)


def _lock_fact_companies(db: Session, facts: list[dict[str, Any]]) -> None:
    """Serialize both fact writers; non-key locks stay compatible with child-row FK checks."""
    if facts:
        with db.no_autoflush:
            db.query(Company.id).filter(Company.id.in_({f["company_id"] for f in facts})).order_by(
                Company.id
            ).with_for_update(key_share=True).all()


def upsert_facts(
    db: Session,
    facts: list[dict[str, Any]],
    *,
    period_of_report: Optional[date] = None,
    reconcile: bool = True,
    authoritative: Optional[dict[tuple[str, date], float]] = None,
    commit: bool = True,
    refresh_flags: bool = False,
    flags_only: bool = False,
) -> dict[str, int]:
    """Insert fact rows, maintaining ``is_latest`` and the reconciliation flag.

    Runs the local-invariant gate (``reconcile`` on by default) over the batch first: impossible
    facts are dropped, the rest are written with their computed ``reconciled`` value. When an
    ``authoritative`` map (from ``extract_authoritative_values``) is supplied, headline figures are
    then cross-checked against it (§3.5 step 2) — confirmed or corrected to the SEC value.
    Idempotent on the full identity key — if a row with the same (company, concept, period_end,
    fiscal_period, unit, accession) already exists it is skipped; otherwise any current ``is_latest``
    row for the same (company, concept, period_end, fiscal_period, unit) is demoted unless its
    accession is known to be newer. Untied companyfacts rows are preserved conservatively because
    their filing dates are not stored here. Older own-filing facts remain queryable by filing ID.

    ``refresh_flags`` (opt-in; the reconciliation-flag audit) re-evaluates the stored ``reconciled``
    flag of a skipped identity against the freshly computed verdict — and ONLY the flag: a row
    whose ``source`` or ``value`` differs from the incoming fact (a bulk companyfacts row occupying
    the same identity, an authoritative override, a changed extraction) is counted as a
    ``value_mismatch`` and left untouched, so an authoritative ``True`` is never overwritten by a
    heuristic verdict. ``is_latest`` is restatement state and is never touched. The result then
    also carries ``flags_refreshed`` / ``value_mismatch``; the default result shape is unchanged.

    ``flags_only`` (opt-in; the audit's write mode) confines the batch to flag columns: an identity
    that is not stored yet is counted as ``unstored`` and never inserted, so no row is added and no
    current ``is_latest`` row is demoted. Storing those identities is the full backfill re-pass's
    job (``scripts/backfill_facts.py`` without ``--only-new``), not the audit's.
    """
    _lock_fact_companies(db, facts)
    rejected = 0
    if reconcile and facts:
        company_id = facts[0]["company_id"]
        concepts = {f["concept"] for f in facts}
        period_ends = [f["period_end"] for f in facts if f.get("period_end")]
        # Seed the gate with each concept's value from before the EARLIEST batch period;
        # reconcile_facts groups by period and chains in-batch priors forward from there, so a
        # multi-period batch compares each year against the one before it (DB or in-batch).
        prior = _prior_values(db, company_id, concepts, min(period_ends) if period_ends else None)
        facts, dropped = reconcile_facts(
            facts, prior_values=prior, period_of_report=period_of_report
        )
        rejected = len(dropped)
        if authoritative:
            facts = cross_check_facts(facts, authoritative)

    inserted = 0
    skipped = 0
    flags_refreshed = 0
    value_mismatch = 0
    unstored = 0
    filing_dates = dict(db.query(Filing.accession_number, Filing.filing_date).filter(
        Filing.accession_number.in_({f["accession"] for f in facts})
    ).all()) if facts else {}
    for fact in facts:
        fact = dict(fact)
        reconciled = fact.pop("reconciled", False)
        hit = (
            db.query(FinancialFact.id)
            .filter_by(
                company_id=fact["company_id"],
                concept=fact["concept"],
                period_end=fact["period_end"],
                fiscal_period=fact["fiscal_period"],
                unit=fact["unit"],
                accession=fact["accession"],
            )
            .first()
        )
        if hit:
            skipped += 1
            if refresh_flags:
                existing = db.get(FinancialFact, hit[0])
                same = existing.source == fact.get("source") and math.isclose(
                    float(existing.value), float(fact["value"]), rel_tol=1e-9, abs_tol=0.0
                )
                if not same:
                    value_mismatch += 1
                elif bool(existing.reconciled) != bool(reconciled):
                    existing.reconciled = reconciled
                    flags_refreshed += 1
            continue
        if flags_only:
            unstored += 1  # flag columns only: never insert, never demote a current row
            continue

        # A labelled quarter also replaces its legacy unlabelled twin; otherwise deriving a
        # period would leave two current rows for the same reported figure.
        period_filter = FinancialFact.fiscal_period == fact["fiscal_period"]
        if fact["fiscal_period"] in ("Q1", "Q2", "Q3", "Q4"):
            period_filter = or_(period_filter, FinancialFact.fiscal_period.is_(None))
        current = db.query(FinancialFact).filter_by(
            company_id=fact["company_id"],
            concept=fact["concept"],
            period_end=fact["period_end"],
            unit=fact["unit"],
            is_latest=True,
        ).filter(period_filter)
        incoming_date = filing_dates.get(fact["accession"])
        newer_filing = Filing.id.isnot(None) if incoming_date is None else or_(
            Filing.filing_date > incoming_date,
            and_(Filing.filing_date == incoming_date, Filing.accession_number > fact["accession"]),
        )
        newer = current.outerjoin(Filing, FinancialFact.accession == Filing.accession_number).filter(
            FinancialFact.accession != fact["accession"],
            or_(newer_filing, and_(FinancialFact.source == "companyfacts", Filing.id.is_(None))),
        ).first() is not None
        if not newer:
            current.update({"is_latest": False})

        db.add(FinancialFact(**fact, is_latest=not newer, reconciled=reconciled))
        inserted += 1

    if commit:  # commit=False lets a caller fold this into one per-filing transaction (remediation)
        db.commit()
    result = {"inserted": inserted, "skipped": skipped, "rejected": rejected}
    if refresh_flags:
        result["flags_refreshed"] = flags_refreshed
        result["value_mismatch"] = value_mismatch
    if flags_only:
        result["unstored"] = unstored
    return result


def process_filing_facts(
    db: Session,
    filing,
    *,
    extract=None,
    standardized: Optional[dict] = None,
    authoritative: Optional[dict[tuple[str, date], float]] = None,
    commit: bool = True,
    refresh_flags: bool = False,
    flags_only: bool = False,
) -> Optional[dict[str, int]]:
    """Normalize ONE filing's stored ``xbrl_data`` into ``financial_fact`` (extract → normalize →
    upsert → stamp ``processed_facts_at``). The per-filing core shared by ``backfill_facts`` (the
    loop) and the post-summary event hook, so a freshly-summarized filing populates its own facts
    without waiting for a batch run.

    No network here: a supplied pre-fetched ``authoritative`` map enables the optional companyfacts
    cross-check; the backfill caller owns that fetch. The local-invariant gate runs regardless. Pass ``standardized`` to reuse metrics the caller already
    extracted (the SSE path) and skip re-extraction. Returns the upsert result, or ``None`` when the
    filing has no ``xbrl_data`` to process. The persisted ``period_end_date`` supplies the local
    current-period check. Existing fact identities are skipped, including their stored flags,
    unless ``refresh_flags`` (the reconciliation-flag audit, which re-evaluates ONLY the flag of a
    value/source-identical row — see ``upsert_facts``). Authoritative cross-checks retain their
    existing override policy. The ``processed_facts_at`` stamp is unconditional except under
    ``flags_only`` (the audit's write mode, see ``upsert_facts``): flag columns only, so unstored
    identities are counted rather than inserted and the stamp is left as it is.
    """
    if standardized is None:
        if getattr(filing, "xbrl_data", None) is None:
            return None
        if extract is None:
            from app.services.edgar.compat import xbrl_service

            extract = xbrl_service.extract_standardized_metrics
        standardized = extract(filing.xbrl_data)

    facts = normalize_standardized_to_facts(
        filing.company_id, filing.id, filing.accession_number, filing.filing_type, standardized
    )
    # upsert never commits here — this function owns the single commit so the fact rows and the
    # ``processed_facts_at`` stamp land together (and a caller can defer it with commit=False for a
    # larger per-filing transaction, e.g. remediation's xbrl_data write + delete + re-insert).
    # Reporting periods are calendar dates, not instants to shift into another timezone.
    report_date = getattr(filing, "period_end_date", None)
    if isinstance(report_date, datetime):
        report_date = report_date.date()
    result = upsert_facts(
        db,
        facts,
        period_of_report=report_date,
        authoritative=authoritative,
        commit=False,
        refresh_flags=refresh_flags,
        flags_only=flags_only,
    )
    if not flags_only:
        filing.processed_facts_at = datetime.now(timezone.utc)
    if commit:
        db.commit()
    return result


def backfill_facts(
    db: Session,
    extract=None,
    limit: Optional[int] = None,
    *,
    only_unprocessed: bool = False,
    cross_check: bool = True,
    companyfacts_fetcher=None,
    refresh_flags: bool = False,
    flags_only: bool = False,
    tickers: Optional[list[str]] = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """Populate ``financial_fact`` from filings that already carry ``xbrl_data``.

    Reuses the standardized-metrics extractor + the pure normalizer + the writer. Idempotent
    (``upsert_facts`` skips rows that already exist, including their stored reconciliation flags).
    A default pass does not repair historical flags; ``refresh_flags=True`` (the
    ``reconciliation-flag-audit`` script) re-evaluates ONLY the flag of value/source-identical
    existing rows and adds ``flags_refreshed`` / ``value_mismatch`` to the stats, logging one line
    per filing that would change. ``flags_only=True`` (the audit's write mode) confines the pass to
    flag columns: identities not stored yet are counted as ``facts_unstored``, never inserted, no
    current row is demoted and the stamp is not touched. ``tickers`` restricts the pass to those
    companies (uppercased). ``dry_run=True`` rolls back each filing's transaction instead of committing it (fact rows,
    flag flips AND the ``processed_facts_at`` stamp) — note that the rollback expires the loaded
    objects, so a caller must ``db.refresh()`` before reading them. Filings are processed oldest-first so the
    newest reported value wins ``is_latest``, and each is stamped with ``processed_facts_at`` so we
    can tell which filings have been normalized. ``extract`` is injectable for tests.

    ``only_unprocessed=True`` skips filings already stamped — the incremental mode for the scheduled
    cron (process just the newly-arrived filings). The default reprocesses everything (a full,
    idempotent pass), which is what a manual re-run wants.

    When ``cross_check`` is on, headline figures are reconciled against SEC's companyfacts API
    (§3.5 step 2): one fetch per company (cached for the run), best-effort. ``companyfacts_fetcher``
    is injectable for tests; pass ``cross_check=False`` (or run with no network) to skip.
    """
    if extract is None:
        from app.services.edgar.compat import xbrl_service

        extract = xbrl_service.extract_standardized_metrics

    fetch_companyfacts = companyfacts_fetcher or _fetch_companyfacts_sync
    auth_by_company: dict[int, dict[tuple[str, date], float]] = {}

    # Eager-load company so the per-filing cik lookup for the cross-check isn't an N+1.
    query = (
        db.query(Filing)
        .options(joinedload(Filing.company))
        .filter(Filing.xbrl_data.isnot(None))
    )
    if only_unprocessed:
        query = query.filter(Filing.processed_facts_at.is_(None))
    if tickers:
        query = query.filter(Filing.company_id.in_(
            db.query(Company.id).filter(Company.ticker.in_([t.upper() for t in tickers]))
        ))
    query = query.order_by(Filing.filing_date.asc())
    if limit:
        query = query.limit(limit)

    processed = 0
    inserted = 0
    skipped = 0
    rejected = 0
    errors = 0
    flags_refreshed = 0
    value_mismatch = 0
    unstored = 0
    companyfacts_unavailable = 0
    unauthorized_companies: set[int] = set()
    for filing in query.all():
        try:
            standardized = extract(filing.xbrl_data)
        except Exception:
            logger.exception("facts backfill: extract failed for filing %s", filing.id)
            errors += 1
            continue

        # Cross-check headline figures against companyfacts (one fetch per company, cached).
        authoritative: Optional[dict[tuple[str, date], float]] = None
        refresh_this_filing = refresh_flags
        if cross_check:
            if filing.company_id not in auth_by_company:
                cik = getattr(filing.company, "cik", None)
                fetched = fetch_companyfacts(cik) if cik else None
                auth_by_company[filing.company_id] = (
                    extract_authoritative_values(fetched) if fetched else {}
                )
                if not fetched:
                    companyfacts_unavailable += 1
                    unauthorized_companies.add(filing.company_id)
            authoritative = auth_by_company[filing.company_id]
            # The audit's verdicts are only trustworthy under the same authority the stored flags
            # were computed with: a row confirmed by companyfacts within tolerance keeps its
            # `edgar_xbrl` source, so without the fetch the local gate would demote it. Count the
            # miss (it fails the audit run) and leave that company's flags alone.
            if filing.company_id in unauthorized_companies:
                refresh_this_filing = False

        # Shared processing uses Filing.period_end_date for the local current-period check.
        # Reprocessing skips existing identities; only the opt-in ``refresh_flags`` audit
        # re-evaluates their stored reconciliation flag (value/source-identical rows only).
        result = process_filing_facts(
            db, filing, standardized=standardized, authoritative=authoritative,
            refresh_flags=refresh_this_filing, flags_only=flags_only, commit=not dry_run,
        )
        if dry_run:
            db.rollback()  # preview only: discard rows, flag flips and the stamp for this filing
        # result is None only when there's nothing to process (no xbrl_data) — can't happen here
        # since the query filters `xbrl_data IS NOT NULL`, but guard it (the return type is Optional).
        if result is not None:
            inserted += result["inserted"]
            skipped += result["skipped"]
            rejected += result.get("rejected", 0)
            unstored += result.get("unstored", 0)
            processed += 1
            if refresh_this_filing:
                flags_refreshed += result["flags_refreshed"]
                value_mismatch += result["value_mismatch"]
                if (result["inserted"] or result["flags_refreshed"] or result["value_mismatch"]
                        or result.get("unstored")):
                    logger.info(
                        "reconciliation_flag_audit filing_id=%s accession=%s inserted=%s "
                        "unstored=%s flags_refreshed=%s value_mismatch=%s dry_run=%s",
                        filing.id, filing.accession_number, result["inserted"],
                        result.get("unstored", 0), result["flags_refreshed"],
                        result["value_mismatch"], dry_run,
                    )

    stats = {
        "filings_processed": processed,
        "facts_inserted": inserted,
        "facts_skipped": skipped,
        "facts_rejected": rejected,
        "extract_errors": errors,
    }
    if refresh_flags:
        stats["flags_refreshed"] = flags_refreshed
        stats["value_mismatch"] = value_mismatch
        stats["companyfacts_unavailable"] = companyfacts_unavailable
    if flags_only:
        stats["facts_unstored"] = unstored
    return stats


def remediate_industry_facts(
    db: Session,
    *,
    refetch,
    tickers: Optional[list[str]] = None,
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Re-extract & re-normalize FINANCIAL-INSTITUTION filings so persisted ``xbrl_data`` and
    ``financial_fact`` carry the industry-correct revenue/components (filing 528 / MCB fix).

    Existing bank filings hold a fee-income-only "revenue" subset. Because ``raw_tag`` is not in the
    fact identity key, a plain re-upsert would SKIP the stale rows, so we delete the affected
    concepts for each filing and re-insert from the corrected extraction.

    ``refetch(company, filing) -> Optional[dict]`` returns fresh ``xbrl_data`` (or None to skip) — it
    is injected so this function stays network-free and unit-testable; the CLI wires the real
    (statement-aware) XBRL extractor. Filings are processed **oldest-first per company** so corrected
    current values reconcile against corrected priors (avoiding false magnitude flags), and the
    newest filing wins ``is_latest`` — this holds only when EVERY filing that reports an overlapping
    period is remediated, so each filing is **atomic** (xbrl_data write + fact delete + re-insert in
    one transaction, rolled back on failure) and any skip is surfaced (``skipped_ids``) rather than
    silently left stale. Cross-check is intentionally OFF (authoritative=None): SEC companyfacts has
    no single authoritative tag for a bank's components/total.

    Returns stats including ``remediated_ids`` (for the regeneration companion) and ``skipped_ids``.

    Coverage note: the default cohort is the financial-services SIC band (6000–6799) in SQL. A
    blank/NULL-SIC financial filer (e.g. some BDCs) is NOT auto-selected — the edgartools
    ``is_financial_institution()`` probe the extractor uses isn't available at the DB layer — so pass
    such filers explicitly via ``tickers``.
    """
    companies_q = db.query(Company)
    if tickers:
        companies_q = companies_q.filter(Company.ticker.in_([t.upper() for t in tickers]))
    else:
        # `Company.sic` is a String column of 4-digit codes, so a lexical BETWEEN is correct here.
        companies_q = companies_q.filter(Company.sic.between("6000", "6799"))
    companies = companies_q.all()

    stats: dict[str, Any] = {
        "companies": 0, "filings_refetched": 0, "filings_skipped": 0,
        "facts_deleted": 0, "facts_inserted": 0, "errors": 0,
        "remediated_ids": [], "skipped_ids": [],
    }
    processed = 0
    for company in companies:
        filings = (
            db.query(Filing)
            .filter(Filing.company_id == company.id, Filing.xbrl_data.isnot(None))
            .order_by(Filing.filing_date.asc())
            .all()
        )
        if not filings:
            continue
        stats["companies"] += 1
        for filing in filings:
            if limit is not None and processed >= limit:
                return stats
            try:
                fresh = refetch(company, filing)
            except Exception:
                logger.exception("remediate: refetch failed for filing %s", filing.id)
                stats["errors"] += 1
                stats["skipped_ids"].append(filing.id)
                continue
            if not fresh:
                stats["filings_skipped"] += 1
                stats["skipped_ids"].append(filing.id)
                continue
            stats["filings_refetched"] += 1
            processed += 1
            if dry_run:
                continue
            # One atomic transaction per filing: overwrite the blob, delete the stale affected-concept
            # rows (raw_tag isn't in the identity, so a plain re-upsert would skip them), re-insert the
            # corrected facts, then commit. On any failure roll back so we never leave xbrl_data
            # updated with facts deleted-but-not-reinserted.
            try:
                filing.xbrl_data = fresh
                deleted = (
                    db.query(FinancialFact)
                    .filter(
                        FinancialFact.company_id == company.id,
                        FinancialFact.accession == filing.accession_number,
                        FinancialFact.concept.in_(AFFECTED_FINANCIAL_CONCEPTS),
                    )
                    .delete(synchronize_session=False)
                )
                result = process_filing_facts(db, filing, commit=False)  # cross_check off
                db.commit()
            except Exception:
                db.rollback()
                logger.exception("remediate: write failed for filing %s", filing.id)
                stats["errors"] += 1
                stats["skipped_ids"].append(filing.id)
                continue
            stats["facts_deleted"] += deleted or 0
            if result is not None:
                stats["facts_inserted"] += result["inserted"]
            stats["remediated_ids"].append(filing.id)
    return stats


def backfill_company_sic(
    db: Session,
    *,
    fetch_sic,
    tickers: Optional[list[str]] = None,
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Populate ``Company.sic`` (+ ``industry``) for companies missing it.

    No ingestion path wrote ``Company.sic`` (the transformer used non-existent ``sic_code`` columns),
    so it is NULL in prod — which collapses the Peers cohort (``peers_service`` falls back to the
    subject alone) and makes the financial-remediation SIC-band selection match nothing. This fills
    the blanks.

    ``fetch_sic(company) -> (sic, industry) | None`` is injected so the core stays network-free and
    unit-testable; the CLI wires an EdgarTools lookup. Idempotent + resumable: by default only
    companies with a NULL/empty ``sic`` are selected, so it can be re-run (and scheduled) to catch
    newly-ingested rows. Pass ``tickers`` to (re)fill a specific set. Returns counts +
    ``updated_ids``/``skipped_ids``.
    """
    companies_q = db.query(Company)
    if tickers:
        companies_q = companies_q.filter(Company.ticker.in_([t.upper() for t in tickers]))
    else:
        companies_q = companies_q.filter((Company.sic.is_(None)) | (Company.sic == ""))
    if limit is not None:
        companies_q = companies_q.limit(limit)

    stats: dict[str, Any] = {
        "scanned": 0, "updated": 0, "skipped": 0, "errors": 0,
        "updated_ids": [], "skipped_ids": [],
    }
    # Commit in small batches so a mid-run crash of this long, SEC-rate-limited pass loses only the
    # uncommitted tail (it's resumable — re-running only re-selects still-blank rows). Disable
    # expire-on-commit for the loop so each batch commit doesn't expire the pending Company rows and
    # force an N+1 reload of ``company.cik`` on the next ``fetch_sic``; restore the prior setting after.
    prior_expire_on_commit = db.expire_on_commit
    db.expire_on_commit = False
    pending = 0
    try:
        for company in companies_q.all():
            stats["scanned"] += 1
            try:
                result = fetch_sic(company)
            except Exception:
                logger.exception("backfill_company_sic: fetch failed for company %s", company.id)
                stats["errors"] += 1
                continue
            sic = result[0] if result else None
            industry = result[1] if result and len(result) > 1 else None
            if not sic:  # EdgarTools returned no SIC (e.g. some BDCs) — leave as-is, surface it
                stats["skipped"] += 1
                stats["skipped_ids"].append(company.id)
                continue
            stats["updated"] += 1
            stats["updated_ids"].append(company.id)
            if dry_run:
                continue
            company.sic = str(sic)
            if industry:
                company.industry = industry
            pending += 1
            if pending >= 100:  # commit in small batches
                db.commit()
                pending = 0
        if not dry_run and pending:
            db.commit()
    finally:
        db.expire_on_commit = prior_expire_on_commit
    return stats


def _fundamentals_payload(ticker: str, company_name: str, rows, cik: str | None = None) -> dict[str, Any]:
    """Group flat ``FinancialFact`` rows into the FundamentalsResponse shape (per-concept series, in
    the order queried — oldest→newest). Shared by the company- and filing-scoped readers."""
    series: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        series.setdefault(row.concept, []).append(
            {
                "period_end": row.period_end.isoformat() if row.period_end else None,
                "fiscal_year": row.fiscal_year,
                "fiscal_period": row.fiscal_period,
                "value": published_value(row),
                "unit": row.unit,
                "form": row.form,
                "accession": row.accession,
                "reconciled": bool(row.reconciled),
                "provenance": provenance_for_fact(row, cik),
            }
        )
    return {
        "ticker": ticker,
        "company_name": company_name,
        "concepts": [
            {"concept": concept, "unit": points[0]["unit"], "points": points}
            for concept, points in series.items()
        ],
    }


def get_filing_fundamentals(db: Session, filing_id: int) -> Optional[dict[str, Any]]:
    """Annual (FY) facts **as reported in a single filing**, grouped into per-concept time-series.

    Filing-scoped (roadmap B): keyed by ``filing_id`` with **no** ``is_latest`` filter, so the chart
    shows the multi-year figures *this specific filing* disclosed (its comparative years) — an
    immutable snapshot faithful to the document, even if a later filing restated a period. Restricted
    to ``fiscal_period == "FY"`` (the annual-report periods — 10-K / 20-F / 40-F; see
    ``_fiscal_period``): the backfill ingests every XBRL-bearing filing, so a company that has filed
    10-Qs also carries quarterly facts (``fiscal_period`` is ``None``), and without this filter a
    3-month quarterly value would surface alongside the full-year value for the same ``fiscal_year`` —
    a quarterly bar masquerading as an annual one under the chart's "Annual figures" label. Returns
    ``None`` when the filing doesn't exist.
    """
    filing = (
        db.query(Filing).options(joinedload(Filing.company)).filter(Filing.id == filing_id).first()
    )
    if filing is None:
        return None

    rows = (
        db.query(FinancialFact)
        .filter(
            FinancialFact.filing_id == filing_id,
            FinancialFact.fiscal_period == "FY",
        )
        .order_by(FinancialFact.concept.asc(), FinancialFact.period_end.asc())
        .all()
    )

    company = filing.company
    return _fundamentals_payload(
        (company.ticker if company else "") or "",
        (company.name if company else "") or "",
        rows,
        cik=company.cik if company else None,
    )


def upsert_facts_bulk(
    db: Session, facts: list[dict[str, Any]], *, commit: bool = True
) -> dict[str, int]:
    """Batched writer for latest-filed winners from a full-history companyfacts payload.

    A full ingest is ~23 concepts × up to ~50 periods — the per-row two-query loop in
    ``upsert_facts`` would be thousands of round trips. This prefetches the company's existing
    rows once, then applies the same rules in memory: identity skip (idempotent), ``is_latest``
    demotion per (concept, period_end, fiscal_period, unit), plus the D1 rule — a labelled
    Q1..Q4 row demotes the legacy NULL-``fiscal_period`` twin for the same period so a quarter
    never has two current rows. Facts must already carry ``reconciled`` (no gate runs here —
    see ``normalize_companyfacts``). Known Filing dates also protect an already-stored newer
    accession from a delayed SEC response; rows without local Filing metadata retain the
    normalizer's latest-filed ordering within that response.
    """
    if not facts:
        return {"inserted": 0, "skipped": 0, "demoted": 0}
    _lock_fact_companies(db, facts)
    company_id = facts[0]["company_id"]
    concepts = {f["concept"] for f in facts}
    rows = (
        db.query(FinancialFact)
        .filter(FinancialFact.company_id == company_id, FinancialFact.concept.in_(list(concepts)))
        .all()
    )
    accessions = {f["accession"] for f in facts} | {row.accession for row in rows}
    filing_dates = dict(db.query(Filing.accession_number, Filing.filing_date).filter(
        Filing.accession_number.in_(accessions)
    ).all())
    existing_identity: set[tuple] = set()
    latest_by_key: dict[tuple, list[FinancialFact]] = {}
    null_fp_latest: dict[tuple, list[FinancialFact]] = {}
    for row in rows:
        existing_identity.add(
            (row.concept, row.period_end, row.fiscal_period, row.unit, row.accession)
        )
        if row.is_latest:
            latest_by_key.setdefault(
                (row.concept, row.period_end, row.fiscal_period, row.unit), []
            ).append(row)
            if row.fiscal_period is None:
                null_fp_latest.setdefault((row.concept, row.period_end, row.unit), []).append(row)

    inserted = skipped = demoted = 0
    for fact in facts:
        fact = dict(fact)
        reconciled = bool(fact.pop("reconciled", False))
        identity = (
            fact["concept"], fact["period_end"], fact["fiscal_period"], fact["unit"], fact["accession"]
        )
        if identity in existing_identity:
            skipped += 1
            continue
        existing_identity.add(identity)

        key = (fact["concept"], fact["period_end"], fact["fiscal_period"], fact["unit"])
        null_key = (fact["concept"], fact["period_end"], fact["unit"])
        current = list(latest_by_key.get(key, []))
        if fact["fiscal_period"] in _QUARTER_PERIODS:
            current.extend(null_fp_latest.get(null_key, []))
        incoming_date = filing_dates.get(fact["accession"])
        newer = any(
            row.is_latest and row.accession != fact["accession"]
            and filing_dates.get(row.accession) is not None
            and (incoming_date is None or
                 (filing_dates[row.accession], row.accession) > (incoming_date, fact["accession"]))
            for row in current
        )
        if not newer:
            for row in current:
                if row.is_latest:
                    row.is_latest = False
                    demoted += 1
        inserted_row = FinancialFact(**fact, is_latest=not newer, reconciled=reconciled)
        db.add(inserted_row)
        if not newer:
            latest_by_key[key] = [inserted_row]
            if fact["fiscal_period"] is None:
                null_fp_latest[null_key] = [inserted_row]
        inserted += 1

    if commit:
        db.commit()
    return {"inserted": inserted, "skipped": skipped, "demoted": demoted}


# Per-company in-flight sync dedup (the summary_pipeline._claim_inflight pattern): concurrent
# coverage requests for the same company collapse into one SEC fetch. Process-local is the right
# scope — prod is a single Cloud Run instance with Redis off.
_inflight_syncs: dict[int, asyncio.Event] = {}


def _companyfacts_fresh_result(
    db: Session, company: Company, *, force: bool
) -> Optional[dict[str, Any]]:
    """Return the unchanged TTL result, or ``None`` when this company needs a fetch."""
    synced_at = company.facts_synced_at
    if synced_at is not None and synced_at.tzinfo is None:
        synced_at = synced_at.replace(tzinfo=timezone.utc)  # SQLite returns naive datetimes
    if force or synced_at is None:
        return None

    from app.config import settings

    if datetime.now(timezone.utc) - synced_at >= timedelta(
        hours=settings.COMPANYFACTS_SYNC_TTL_HOURS
    ):
        return None
    newer_filing = (
        db.query(Filing.id)
        .filter(Filing.company_id == company.id, Filing.filing_date > synced_at)
        .first()
    )
    if newer_filing is not None:
        return None
    return {
        "synced": True, "refreshed": False, "inserted": 0, "skipped": 0,
        "demoted": 0, "unsupported_ifrs": False,
    }


def _persist_companyfacts_payload(
    db: Session, company: Company, payload: dict[str, Any]
) -> dict[str, Any]:
    """Normalize and persist one already-fetched payload in the caller's short transaction."""
    facts, meta = normalize_companyfacts(
        company.id, payload, financial_sic=_is_financial_sic(company.sic)
    )
    result = (
        upsert_facts_bulk(db, facts, commit=False)
        if facts
        else {"inserted": 0, "skipped": 0, "demoted": 0}
    )
    company.facts_synced_at = datetime.now(timezone.utc)
    db.commit()
    logger.info(
        "companyfacts_sync company=%s inserted=%s skipped=%s demoted=%s ifrs=%s",
        company.id, result["inserted"], result["skipped"], result["demoted"],
        meta["unsupported_ifrs"],
    )
    return {
        "synced": True, "refreshed": True, **result,
        "unsupported_ifrs": meta["unsupported_ifrs"],
    }


async def ingest_companyfacts(
    db: Session,
    company: Company,
    *,
    force: bool = False,
    fetcher: Optional[Callable[[str], Any]] = None,
) -> dict[str, Any]:
    """Sync one company's companyfacts history into ``financial_fact`` (TTL-guarded, deduped).

    Freshness: a sync newer than ``COMPANYFACTS_SYNC_TTL_HOURS`` is a no-op UNLESS a Filing row
    newer than the stamp exists (a fresh filing shouldn't wait out the TTL) or ``force`` is set.
    ``facts_synced_at`` is stamped even for empty/IFRS-only results so unsupported filers aren't
    refetched hourly; a FAILED fetch does not stamp (retry on next touch). ``fetcher`` is
    injectable for tests (async ``cik -> dict | None``).
    """
    fresh = _companyfacts_fresh_result(db, company, force=force)
    if fresh is not None:
        return fresh

    inflight = _inflight_syncs.get(company.id)
    if inflight is not None:
        try:
            await asyncio.wait_for(inflight.wait(), timeout=COMPANYFACTS_INFLIGHT_WAIT_SECONDS)
        except asyncio.TimeoutError:
            pass
        db.expire(company)  # pick up the leader's facts_synced_at
        return {"synced": company.facts_synced_at is not None, "refreshed": False, "inserted": 0,
                "skipped": 0, "demoted": 0, "unsupported_ifrs": False, "waited": True}

    event = asyncio.Event()
    _inflight_syncs[company.id] = event
    try:
        fetch = fetcher or _fetch_companyfacts_async
        payload = await fetch(company.cik)
        if payload is None:
            return {"synced": False, "refreshed": False, "inserted": 0, "skipped": 0, "demoted": 0,
                    "unsupported_ifrs": False, "error": "fetch_failed"}
        return _persist_companyfacts_payload(db, company, payload)
    finally:
        if _inflight_syncs.get(company.id) is event:
            _inflight_syncs.pop(company.id, None)
        event.set()


async def ingest_companyfacts_by_id(
    company_id: int,
    *,
    session_factory: Callable[[], Session],
    force: bool = False,
    fetcher: Optional[Callable[[str], Any]] = None,
) -> dict[str, Any]:
    """Sync coverage facts without retaining a database connection during external waits.

    The coverage route can outlive its request while the SEC fetch continues in the background.
    Keep its database ownership to two short units: a freshness/snapshot read, then (for the
    leader) persistence after the fetch.  A same-company follower waits on the process-local event
    with no session of its own.  The caller-owned ``ingest_companyfacts`` contract remains intact
    for batch jobs and tests that deliberately manage a larger transaction.
    """
    with session_factory() as db:
        company = db.get(Company, company_id)
        if company is None:
            return {"synced": False}

        fresh = _companyfacts_fresh_result(db, company, force=force)
        if fresh is not None:
            return fresh

        cik = company.cik

    inflight = _inflight_syncs.get(company_id)
    if inflight is not None:
        try:
            await asyncio.wait_for(inflight.wait(), timeout=COMPANYFACTS_INFLIGHT_WAIT_SECONDS)
        except asyncio.TimeoutError:
            pass
        with session_factory() as db:
            synced_at = db.query(Company.facts_synced_at).filter(Company.id == company_id).scalar()
        return {
            "synced": synced_at is not None, "refreshed": False, "inserted": 0, "skipped": 0,
            "demoted": 0, "unsupported_ifrs": False, "waited": True,
        }

    event = asyncio.Event()
    _inflight_syncs[company_id] = event
    try:
        fetch = fetcher or _fetch_companyfacts_async
        payload = await fetch(cik)
        if payload is None:
            return {
                "synced": False, "refreshed": False, "inserted": 0, "skipped": 0,
                "demoted": 0, "unsupported_ifrs": False, "error": "fetch_failed",
            }
        with session_factory() as db:
            company = db.get(Company, company_id)
            if company is None:
                return {"synced": False}
            return _persist_companyfacts_payload(db, company, payload)
    finally:
        if _inflight_syncs.get(company_id) is event:
            _inflight_syncs.pop(company_id, None)
        event.set()


async def sync_companyfacts_batch(
    db: Session,
    *,
    tickers: Optional[list[str]] = None,
    watchlist_only: bool = False,
    limit: Optional[int] = None,
    force: bool = False,
    fetcher: Optional[Callable[[str], Any]] = None,
) -> dict[str, Any]:
    """Warm the companyfacts cache for a cohort (ops path: internal job / CLI script).

    Cohort: explicit ``tickers`` > ``watchlist_only`` (every company on any user's watchlist) >
    all companies. Serial on purpose — the rate limiter paces the fetches; a company's failure
    never stops the walk.
    """
    query = db.query(Company)
    if tickers:
        query = query.filter(Company.ticker.in_([t.upper() for t in tickers]))
    elif watchlist_only:
        watched_ids = db.query(Watchlist.company_id).distinct()
        query = query.filter(Company.id.in_(watched_ids))
    query = query.order_by(Company.id.asc())
    if limit is not None:
        query = query.limit(limit)

    stats: dict[str, Any] = {"companies": 0, "refreshed": 0, "fresh": 0, "failed": 0,
                             "unsupported_ifrs": 0, "inserted": 0}
    # Each per-company ingest commits; with the default expire-on-commit every loaded Company
    # would then lazy-reload on the next iteration's attribute access (N+1). Disable it for the
    # loop and restore after — the backfill_company_sic pattern.
    prior_expire_on_commit = db.expire_on_commit
    db.expire_on_commit = False
    try:
        for company in query.all():
            stats["companies"] += 1
            try:
                result = await ingest_companyfacts(db, company, force=force, fetcher=fetcher)
            except Exception:  # noqa: BLE001 - one bad company must not stop the walk
                logger.exception("companyfacts sync failed for company %s", company.id)
                db.rollback()
                stats["failed"] += 1
                continue
            if not result.get("synced"):
                stats["failed"] += 1
            elif result.get("refreshed"):
                stats["refreshed"] += 1
                stats["inserted"] += result.get("inserted", 0)
            else:
                stats["fresh"] += 1
            if result.get("unsupported_ifrs"):
                stats["unsupported_ifrs"] += 1
    finally:
        db.expire_on_commit = prior_expire_on_commit
    return stats
