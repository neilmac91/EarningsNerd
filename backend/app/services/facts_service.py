"""Normalize the standardized XBRL metrics we already extract into queryable `financial_fact` rows.

`normalize_standardized_to_facts` is pure (dict in → list[dict] out, unit-testable). `upsert_facts`
writes them while maintaining the restatement-safe `is_latest` flag.

The per-filing path sources the current period each filing reports, attributed to that filing's
accession — accurate and dependency-free (it reuses `xbrl_service.extract_standardized_metrics`).
A local-invariant reconciliation gate (`reconcile_facts`, no network) runs on write: it
hard-rejects impossible values and flags implausible ones (`reconciled=False`) so the UI can
surface them honestly ("reconciled or visibly flagged" — strategy §3.5/§5). The companyfacts
ingest (`normalize_companyfacts` → `ingest_companyfacts`) is the multi-period source: FY +
positionally-labelled quarters, cross-checked against the per-filing rows, plus the Q4
derivations (YTD9-preferred flows, shares-based EPS) and same-period computed metrics. FSDS /
Frames backfill remains a later wave.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session, joinedload

from app.models import Company, Filing, FinancialFact, Watchlist

logger = logging.getLogger(__name__)

# Financial-institution revenue concepts affected by the as-reported-statement fix (filing 528).
# When remediating, the stale rows under these concepts (e.g. a bank's fee-income-only "revenue")
# are deleted and re-inserted from the corrected extraction — raw_tag is NOT in the identity key,
# so a plain re-upsert would skip them.
AFFECTED_FINANCIAL_CONCEPTS: tuple[str, ...] = (
    "revenue", "net_interest_income", "noninterest_income",
    "premiums_earned", "net_investment_income",
)

# Standardized concept (from xbrl_service.extract_standardized_metrics) → DEFAULT unit, used only
# when the fact carries no reporting currency (domestic US filers). When a fact carries a currency
# (e.g. CNY/EUR for a foreign private issuer), `_unit_for` substitutes it so the value is never
# implied-USD. Margins are ratios ("pure"); per-share metrics are <ccy>/shares.
_CONCEPT_UNITS: dict[str, str] = {
    "revenue": "USD",
    "net_income": "USD",
    "gross_profit": "USD",
    "operating_income": "USD",
    "total_assets": "USD",
    "cash_and_equivalents": "USD",
    "operating_cash_flow": "USD",
    "capital_expenditures": "USD",
    "free_cash_flow": "USD",
    "shareholders_equity": "USD",
    "long_term_debt": "USD",
    "earnings_per_share": "USD/shares",
    "eps_diluted": "USD/shares",
    "net_margin": "pure",
    "gross_margin": "pure",
    "operating_margin": "pure",
    # Financial-institution revenue components/totals (filing 528 / MCB fix). All monetary totals;
    # deliberately NOT in NON_NEGATIVE_CONCEPTS (net interest income / net investment income can be
    # negative), and NOT in HEADLINE_GAAP_TAGS so the companyfacts cross-check leaves them alone.
    "net_interest_income": "USD",
    "noninterest_income": "USD",
    "premiums_earned": "USD",
    "net_investment_income": "USD",
    # Roadmap 2.6: full cash-flow statement + working-capital lines (flag-gated extraction).
    "investing_cash_flow": "USD",
    "financing_cash_flow": "USD",
    "current_assets": "USD",
    "current_liabilities": "USD",
    "working_capital": "USD",
    "current_ratio": "pure",
}

# Concepts that are physically impossible below zero — a negative value is a parse error,
# not a legitimate datum (a loss lives in net_income/operating_income, never in revenue or
# total_assets). These hard-reject; everything else can legitimately be negative.
NON_NEGATIVE_CONCEPTS: frozenset[str] = frozenset(
    {"revenue", "total_assets", "cash_and_equivalents", "long_term_debt",
     # Roadmap 2.6: balance-sheet totals + the current ratio can't be negative (working_capital CAN
     # be, and the investing/financing cash flows routinely are — so those stay out of this set).
     "current_assets", "current_liabilities", "current_ratio"}
)

# A period-over-period swing beyond this factor (either direction) is treated as a likely
# scale bug (the ABNB "$ in millions" → 1, XOM EPS 0.00 class), flagged not rejected.
_MAGNITUDE_TOLERANCE = 10.0


def _parse_date(value: Any) -> Optional[date]:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _fiscal_period(form: Optional[str]) -> Optional[str]:
    # Annual reports report the full fiscal year: 10-K (domestic) and 20-F / 40-F (foreign private
    # issuers). For a 10-Q the quarter can't be inferred from the period alone, and a 6-K is
    # free-form, so both are left unset rather than guessed.
    return "FY" if (form or "").upper().replace("-", "").startswith(("10K", "20F", "40F")) else None


def _unit_for(concept: str, currency: Optional[str]) -> str:
    """Resolve the stored unit for a fact, substituting the as-filed reporting currency.

    Domestic filers carry no currency → the USD/USD-shares/pure defaults stand. A foreign issuer's
    fact carries its reporting currency (e.g. "CNY"), which replaces the USD assumption so a CNY
    value is never stored/labelled as USD: monetary → "CNY", per-share → "CNY/shares", ratios stay
    "pure".
    """
    base = _CONCEPT_UNITS.get(concept, "USD")
    if base == "pure" or not currency:
        return base
    return f"{currency}/shares" if base.endswith("/shares") else currency


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
                    "period_end": period_end,
                    "fiscal_year": period_end.year,
                    "fiscal_period": _fiscal_period(point_form),
                    "value": float(value),
                    "form": point_form,
                    "accession": accession,
                    "source": "edgar_xbrl",
                }
            )
    return facts


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
            accepted.append({**fact, "reconciled": not reasons})
            if value is not None:
                period_values[concept] = value

        # This period's values become the prior for the next (newer) period in the batch.
        running_prior.update(period_values)

    return accepted, rejected


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

# Standardized concept -> candidate us-gaap tags (tried in priority order, filled per period).
HEADLINE_GAAP_TAGS: dict[str, tuple[str, ...]] = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
    ),
    "net_income": ("NetIncomeLoss", "ProfitLoss"),
    "total_assets": ("Assets",),
}
_INSTANT_HEADLINE = frozenset({"total_assets"})  # balance-sheet (instant) vs duration concepts
# Relative gap above which the parsed value is treated as wrong and replaced by companyfacts.
CROSS_CHECK_TOLERANCE = 0.01


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
        out.append(fact)
    return out


def _fetch_companyfacts_sync(cik: str) -> Optional[dict]:
    """Best-effort sync fetch of the companyfacts JSON for a CIK (used by the backfill job).

    Returns ``None`` on any failure — the cross-check is optional and must never break the
    backfill. A short sleep keeps this under SEC's limit when the backfill walks many companies
    (it runs as the single cron worker; see strategy §3.4).
    """
    import time as _time

    import httpx

    from app.config import settings

    cik_padded = str(cik).lstrip("0").zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
    headers = {"User-Agent": settings.SEC_USER_AGENT, "Accept": "application/json"}
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
        return data if isinstance(data, dict) else None
    except Exception as exc:  # noqa: BLE001 - best-effort, never break the backfill
        logger.warning("companyfacts fetch failed for CIK %s: %s", cik, exc)
        return None
    finally:
        _time.sleep(0.2)  # gentle self-throttle for the multi-company walk


def upsert_facts(
    db: Session,
    facts: list[dict[str, Any]],
    *,
    period_of_report: Optional[date] = None,
    reconcile: bool = True,
    authoritative: Optional[dict[tuple[str, date], float]] = None,
    commit: bool = True,
) -> dict[str, int]:
    """Insert fact rows, maintaining ``is_latest`` and the reconciliation flag.

    Runs the local-invariant gate (``reconcile`` on by default) over the batch first: impossible
    facts are dropped, the rest are written with their computed ``reconciled`` value. When an
    ``authoritative`` map (from ``extract_authoritative_values``) is supplied, headline figures are
    then cross-checked against it (§3.5 step 2) — confirmed or corrected to the SEC value.
    Idempotent on the full identity key — if a row with the same (company, concept, period_end,
    fiscal_period, unit, accession) already exists it is skipped; otherwise any current ``is_latest``
    row for the same (company, concept, period_end, fiscal_period, unit) is demoted and this one
    inserted as latest. Callers should upsert in chronological order so the newest value wins.
    """
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
    for fact in facts:
        fact = dict(fact)
        reconciled = fact.pop("reconciled", False)
        if (
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
        ):
            skipped += 1
            continue

        # Demote the prior current value for this (company, concept, period, fiscal_period, unit).
        db.query(FinancialFact).filter_by(
            company_id=fact["company_id"],
            concept=fact["concept"],
            period_end=fact["period_end"],
            fiscal_period=fact["fiscal_period"],
            unit=fact["unit"],
            is_latest=True,
        ).update({"is_latest": False})

        db.add(FinancialFact(**fact, is_latest=True, reconciled=reconciled))
        inserted += 1

    if commit:  # commit=False lets a caller fold this into one per-filing transaction (remediation)
        db.commit()
    return {"inserted": inserted, "skipped": skipped, "rejected": rejected}


def process_filing_facts(
    db: Session,
    filing,
    *,
    extract=None,
    standardized: Optional[dict] = None,
    authoritative: Optional[dict[tuple[str, date], float]] = None,
    commit: bool = True,
) -> Optional[dict[str, int]]:
    """Normalize ONE filing's stored ``xbrl_data`` into ``financial_fact`` (extract → normalize →
    upsert → stamp ``processed_facts_at``). The per-filing core shared by ``backfill_facts`` (the
    loop) and the post-summary event hook, so a freshly-summarized filing populates its own facts
    without waiting for a batch run.

    No network unless ``authoritative`` (a companyfacts map) is supplied — the local-invariant gate
    in ``upsert_facts`` runs regardless. Pass ``standardized`` to reuse metrics the caller already
    extracted (the SSE path) and skip re-extraction. Returns the upsert result, or ``None`` when the
    filing has no ``xbrl_data`` to process.
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
    result = upsert_facts(
        db,
        facts,
        period_of_report=getattr(filing, "period_of_report", None),
        authoritative=authoritative,
        commit=False,
    )
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
) -> dict[str, int]:
    """Populate ``financial_fact`` from filings that already carry ``xbrl_data``.

    Reuses the standardized-metrics extractor + the pure normalizer + the writer. Idempotent
    (``upsert_facts`` skips rows that already exist). Filings are processed oldest-first so the
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
    query = query.order_by(Filing.filing_date.asc())
    if limit:
        query = query.limit(limit)

    processed = 0
    inserted = 0
    skipped = 0
    rejected = 0
    errors = 0
    for filing in query.all():
        try:
            standardized = extract(filing.xbrl_data)
        except Exception:
            logger.exception("facts backfill: extract failed for filing %s", filing.id)
            errors += 1
            continue

        # Cross-check headline figures against companyfacts (one fetch per company, cached).
        authoritative: Optional[dict[tuple[str, date], float]] = None
        if cross_check:
            if filing.company_id not in auth_by_company:
                cik = getattr(filing.company, "cik", None)
                fetched = fetch_companyfacts(cik) if cik else None
                auth_by_company[filing.company_id] = (
                    extract_authoritative_values(fetched) if fetched else {}
                )
            authoritative = auth_by_company[filing.company_id]

        # Per-filing normalize → upsert → stamp (shared with the post-summary hook). `period_of_report`
        # isn't a Filing column today; process_filing_facts reads it defensively.
        result = process_filing_facts(
            db, filing, standardized=standardized, authoritative=authoritative
        )
        # result is None only when there's nothing to process (no xbrl_data) — can't happen here
        # since the query filters `xbrl_data IS NOT NULL`, but guard it (the return type is Optional).
        if result is not None:
            inserted += result["inserted"]
            skipped += result["skipped"]
            rejected += result.get("rejected", 0)
            processed += 1

    return {
        "filings_processed": processed,
        "facts_inserted": inserted,
        "facts_skipped": skipped,
        "facts_rejected": rejected,
        "extract_errors": errors,
    }


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


def _fundamentals_payload(ticker: str, company_name: str, rows) -> dict[str, Any]:
    """Group flat ``FinancialFact`` rows into the FundamentalsResponse shape (per-concept series, in
    the order queried — oldest→newest). Shared by the company- and filing-scoped readers."""
    series: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        series.setdefault(row.concept, []).append(
            {
                "period_end": row.period_end.isoformat() if row.period_end else None,
                "fiscal_year": row.fiscal_year,
                "fiscal_period": row.fiscal_period,
                "value": float(row.value) if row.value is not None else None,
                "unit": row.unit,
                "form": row.form,
                "accession": row.accession,
                "reconciled": bool(row.reconciled),
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
    )


# --- Multi-Period Analysis (M1): SEC companyfacts as a first-class period source ---------------
#
# One request to https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json returns a company's
# ENTIRE fact history (every year and quarter for every tag it ever filed) — the only viable way to
# serve 10 fiscal years + 12 quarters per company without N per-filing XBRL parses (thread pool of
# 4, ~5-15s each). The functions below classify that history into properly-labelled FY / Q1..Q4
# rows and upsert them into `financial_fact` alongside the per-filing `edgar_xbrl` rows.
#
# CRITICAL companyfacts semantics (verified against tests/fixtures/companyfacts_sample.json): each
# item's `fy`/`fp` label the REPORTING FILING, not the fact's own period — the FY2022 comparative
# revenue inside the FY2023 10-K carries fy=2023/fp="FY". Labels are therefore derived from the
# period itself (duration windows + fiscal-year-window containment), never trusted from `fp` —
# except for one safe case: a quarter not yet inside any completed FY window (the in-progress
# fiscal year), whose EARLIEST-filed item is the original 10-Q that reported it as its own current
# period.

# Duration windows shared with the per-filing extractor (instance_extractor.DURATION_WINDOWS):
# 52/53-week fiscal years run 364-371 days, fiscal quarters 84-98 (incl. 14-week quarters).
# A 39-week YTD slice (~273 days; up to 40 weeks with one 14-week quarter) is classified "YTD9"
# for the Q4 derivation ONLY (Q4 = FY − YTD9, two vintages instead of four) — never stored as a
# fact row. Anything else (26-week half) is the wrong slice and is dropped.
_CF_ANNUAL_WINDOW = (320, 390)
_CF_QUARTER_WINDOW = (75, 105)
_CF_YTD9_WINDOW = (250, 295)

_QUARTER_PERIODS = ("Q1", "Q2", "Q3", "Q4")

# us-gaap tag candidates per standardized concept, in priority order. Ordering follows
# HEADLINE_GAAP_TAGS for the shared concepts (companyfacts context: the ASC-606 revenue tag first).
# Periods are merged ACROSS tags (first tag with data wins per period), so a filer that migrated
# tags (SalesRevenueNet → RevenueFromContractWithCustomer...) keeps its full history. us-gaap only:
# IFRS filers (ifrs-full) are detected and reported unsupported (v1 scope).
COMPANYFACTS_DURATION_TAGS: dict[str, tuple[str, ...]] = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
        "NetSales",
    ),
    "net_income": ("NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"),
    "gross_profit": ("GrossProfit",),
    "operating_income": ("OperatingIncomeLoss",),
    "operating_cash_flow": (
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ),
    "capital_expenditures": (
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ),
    "investing_cash_flow": (
        "NetCashProvidedByUsedInInvestingActivities",
        "NetCashProvidedByUsedInInvestingActivitiesContinuingOperations",
    ),
    "financing_cash_flow": (
        "NetCashProvidedByUsedInFinancingActivities",
        "NetCashProvidedByUsedInFinancingActivitiesContinuingOperations",
    ),
    "earnings_per_share": ("EarningsPerShareBasic", "EarningsPerShareBasicAndDiluted"),
    "eps_diluted": ("EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"),
    # Financial-institution components/totals — exact tags, safe for banks/insurers (unlike the
    # generic revenue tags, which resolve to the ASC-606 fee-income subset for a bank — the
    # filing 528 / MCB bug — hence the `financial_sic` guard in normalize_companyfacts).
    "net_interest_income": ("InterestIncomeExpenseNet",),
    "noninterest_income": ("NoninterestIncome",),
    "premiums_earned": ("PremiumsEarnedNet",),
    "net_investment_income": ("NetInvestmentIncome",),
}

COMPANYFACTS_INSTANT_TAGS: dict[str, tuple[str, ...]] = {
    "total_assets": ("Assets",),
    "cash_and_equivalents": (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsAndShortTermInvestments",
        "Cash",
    ),
    "shareholders_equity": (
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ),
    "long_term_debt": ("LongTermDebtNoncurrent", "LongTermDebt"),
    "current_assets": ("AssetsCurrent",),
    "current_liabilities": ("LiabilitiesCurrent",),
}

# Generic revenue tags are WRONG for banks/insurers (fee-income subset — the MCB fix would be
# undone by re-ingesting them); the exact FI component tags above carry their top line instead.
_FI_SKIPPED_CONCEPTS: frozenset[str] = frozenset({"revenue"})


def _classify_duration(start: date, end: date) -> Optional[str]:
    """"FY" annual slice, "Q" discrete quarter, "YTD9" nine-month YTD (kept ONLY as a Q4
    derivation input — never emitted as a fact row), None for anything else (26-week half)."""
    days = (end - start).days
    if _CF_ANNUAL_WINDOW[0] <= days <= _CF_ANNUAL_WINDOW[1]:
        return "FY"
    if _CF_QUARTER_WINDOW[0] <= days <= _CF_QUARTER_WINDOW[1]:
        return "Q"
    if _CF_YTD9_WINDOW[0] <= days <= _CF_YTD9_WINDOW[1]:
        return "YTD9"
    return None


def _collect_companyfacts_values(
    usgaap: dict, tags: tuple[str, ...], unit_key: str, *, instant: bool
) -> dict[tuple[date, str], dict[str, Any]]:
    """Winning item per (period_end, klass) for one concept, across its candidate tags.

    klass is "FY"/"Q" for durations, "I" for instants. Within a tag the LATEST-`filed` item wins a
    period (restatement-aware; `filed` is ISO so lexical compare is safe, and a later list item wins
    ties — companyfacts lists in filing order). Across tags, the FIRST tag with data wins a period
    (priority order), so tag migrations merge into one continuous history without a stale tag
    shadowing a newer one. Each winner also carries the EARLIEST-filed item's `fp`/`fy` — the one
    case where those fields are trustworthy (the original filing that reported the period as its
    own current period), used only as the in-progress-year quarter fallback.
    """
    claimed: dict[tuple[date, str], dict[str, Any]] = {}
    for tag in tags:
        node = usgaap.get(tag)
        units = node.get("units") if isinstance(node, dict) else None
        items = units.get(unit_key) if isinstance(units, dict) else None
        if not isinstance(items, list):
            continue
        tag_best: dict[tuple[date, str], dict[str, Any]] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            value = item.get("val")
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                continue
            end = _parse_date(item.get("end"))
            if end is None:
                continue
            start: Optional[date] = None
            if instant:
                klass = "I"
            else:
                start = _parse_date(item.get("start"))
                if start is None:
                    continue
                klass = _classify_duration(start, end)
                if klass is None:
                    continue
            filed = str(item.get("filed") or "")
            record = {
                "value": float(value),
                "period_start": start,
                "period_end": end,
                "accession": item.get("accn"),
                "form": item.get("form"),
                "filed": filed,
                "raw_tag": f"us-gaap:{tag}",
                "fp": item.get("fp"),
                "fy": item.get("fy"),
            }
            key = (end, klass)
            best = tag_best.get(key)
            if best is None:
                record["first_fp"] = record["fp"]
                record["first_fy"] = record["fy"]
                record["first_filed"] = filed
                tag_best[key] = record
                continue
            # Track the earliest filer's fp/fy on whatever record ends up winning.
            if filed < best["first_filed"]:
                first_fp, first_fy, first_filed = record["fp"], record["fy"], filed
            else:
                first_fp, first_fy, first_filed = (
                    best["first_fp"], best["first_fy"], best["first_filed"]
                )
            winner = record if filed >= best["filed"] else best
            winner.update(first_fp=first_fp, first_fy=first_fy, first_filed=first_filed)
            tag_best[key] = winner
        for key, record in tag_best.items():
            claimed.setdefault(key, record)
    return claimed


def _fiscal_year_windows(
    duration_values: dict[str, dict[tuple[date, str], dict[str, Any]]]
) -> list[tuple[date, date]]:
    """Distinct completed fiscal-year [start, end] windows across all concepts' FY-class facts.

    Per end date the widest observed start wins (tags occasionally disagree by a day). Sorted by
    end ascending.
    """
    by_end: dict[date, date] = {}
    for per_concept in duration_values.values():
        for (end, klass), record in per_concept.items():
            if klass != "FY" or record["period_start"] is None:
                continue
            start = record["period_start"]
            if end not in by_end or start < by_end[end]:
                by_end[end] = start
    return [(start, end) for end, start in sorted(by_end.items())]


_VALID_FP = frozenset(_QUARTER_PERIODS)


def _label_quarters(
    duration_values: dict[str, dict[tuple[date, str], dict[str, Any]]],
    fy_windows: list[tuple[date, date]],
) -> dict[date, tuple[str, int]]:
    """period_end -> (Q1..Q4, fiscal_year) for every discrete-quarter period.

    Calendar-agnostic AND gap-tolerant: a quarter belongs to the FY window containing it, and its
    number comes from its distance to the window END (~91.3 days per quarter back from fiscal year
    end), so a missing sibling quarter (IPO year, edge of companyfacts history) can never shift the
    label the way a sorted-position scheme would. A discrete Q4 ends AT the window end (distance 0
    → Q4). fiscal_year = the window end's year, so Jan-FYE filers group Q rows with the right FY
    rows. Quarters outside any completed window (the in-progress fiscal year) fall back to the
    earliest filer's `fp`/`fy` — the original 10-Q, the one place those fields are reliable (a
    LATER filer's fp/fy describe its own filing, not this period). Unlabelable quarters are
    dropped rather than guessed.
    """
    q_records: dict[date, dict[str, Any]] = {}
    for per_concept in duration_values.values():
        for (end, klass), record in per_concept.items():
            if klass != "Q":
                continue
            existing = q_records.get(end)
            # Keep the record with the earliest original filer for the fp/fy fallback.
            if existing is None or record["first_filed"] < existing["first_filed"]:
                q_records[end] = record

    labels: dict[date, tuple[str, int]] = {}
    for end, record in q_records.items():
        window = next(((ws, we) for ws, we in fy_windows if ws <= end <= we), None)
        if window is not None:
            window_end = window[1]
            index = 4 - round((window_end - end).days / 91.3)
            if 1 <= index <= 4:
                labels[end] = (f"Q{index}", window_end.year)
                continue
            logger.debug("companyfacts: quarter end %s at odd offset in FY window %s", end, window_end)
        fp = record.get("first_fp")
        if fp in _VALID_FP:
            fy = record.get("first_fy")
            labels[end] = (fp, fy if isinstance(fy, int) else end.year)
    return labels


def normalize_companyfacts(
    company_id: int, companyfacts: Any, *, financial_sic: bool = False
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Classify a raw companyfacts payload into labelled fact dicts (pure; unit-testable).

    Returns ``(facts, meta)`` where meta carries ``unsupported_ifrs`` (an ifrs-full-only filer —
    out of v1 scope) . Emits FY rows, positionally-labelled Q1..Q4 rows, derived Q4 rows
    (``derive_q4_facts`` — YTD9-preferred, ΣQ fallback), derived Q4 EPS
    (``derive_q4_eps_facts`` — shares-based) and same-period derived metrics
    (``derive_same_period_metrics``); YTD slices and weighted share counts feed the derivations
    but are never stored. Direct rows are ``source="companyfacts", reconciled=True`` — this is
    SEC's own structured data, the same authority `cross_check_facts` treats as ground truth — with
    only the NON_NEGATIVE hard-reject applied (a negative revenue/assets is corrupt regardless of
    source). ``financial_sic`` skips the generic revenue concept (fee-income subset for banks — the
    filing 528 / MCB class); the exact FI component tags still ingest.
    """
    meta: dict[str, Any] = {"unsupported_ifrs": False}
    facts_root = companyfacts.get("facts") if isinstance(companyfacts, dict) else None
    usgaap = facts_root.get("us-gaap") if isinstance(facts_root, dict) else None
    if not isinstance(usgaap, dict) or not usgaap:
        if isinstance(facts_root, dict) and isinstance(facts_root.get("ifrs-full"), dict):
            meta["unsupported_ifrs"] = True
        return [], meta

    duration_values: dict[str, dict[tuple[date, str], dict[str, Any]]] = {}
    for concept, tags in COMPANYFACTS_DURATION_TAGS.items():
        if financial_sic and concept in _FI_SKIPPED_CONCEPTS:
            continue
        unit_key = "USD/shares" if _CONCEPT_UNITS.get(concept, "USD").endswith("/shares") else "USD"
        values = _collect_companyfacts_values(usgaap, tags, unit_key, instant=False)
        if values:
            duration_values[concept] = values

    instant_values: dict[str, dict[tuple[date, str], dict[str, Any]]] = {}
    for concept, tags in COMPANYFACTS_INSTANT_TAGS.items():
        values = _collect_companyfacts_values(usgaap, tags, "USD", instant=True)
        if values:
            instant_values[concept] = values

    fy_windows = _fiscal_year_windows(duration_values)
    fy_ends = {end for _start, end in fy_windows}
    quarter_labels = _label_quarters(duration_values, fy_windows)

    def _base_fact(concept: str, record: dict[str, Any]) -> dict[str, Any]:
        return {
            "company_id": company_id,
            "filing_id": None,  # companyfacts rows may precede any Filing row for that accession
            "concept": concept,
            "raw_tag": record["raw_tag"],
            "unit": _CONCEPT_UNITS.get(concept, "USD"),
            "period_start": record["period_start"],
            "period_end": record["period_end"],
            "value": record["value"],
            "form": record["form"],
            "accession": record["accession"] or "companyfacts",
            "source": "companyfacts",
            "reconciled": True,
        }

    facts: list[dict[str, Any]] = []
    for concept, values in duration_values.items():
        for (end, klass), record in values.items():
            if klass == "FY":
                facts.append(
                    {**_base_fact(concept, record), "fiscal_year": end.year, "fiscal_period": "FY"}
                )
            elif klass == "Q":
                label = quarter_labels.get(end)
                if label is None:
                    continue  # unlabelable quarter — dropped rather than guessed
                fiscal_period, fiscal_year = label
                facts.append(
                    {
                        **_base_fact(concept, record),
                        "fiscal_year": fiscal_year,
                        "fiscal_period": fiscal_period,
                    }
                )
            # klass == "YTD9": a Q4-derivation input only (see derive_q4_facts) — a YTD9 slice
            # ends at the SAME date as Q3, so letting it fall through to the quarter-label path
            # would emit the nine-month value as a Q3 row. Never stored.

    for concept, values in instant_values.items():
        for (end, _klass), record in values.items():
            # A fiscal-year-end balance sheet IS the Q4 instant: store it once, labelled FY —
            # quarterly readers select instants by period_end, never by label (D2c).
            if end in fy_ends:
                fiscal_period, fiscal_year = "FY", end.year
            elif end in quarter_labels:
                fiscal_period, fiscal_year = quarter_labels[end]
            elif record.get("first_fp") == "FY":
                # FY-end balance sheet older than the earliest FY duration window; the original
                # 10-K reported it as its own year end. end.year keeps the FY-row convention.
                fiscal_period, fiscal_year = "FY", end.year
            elif record.get("first_fp") in _VALID_FP:
                fy = record.get("first_fy")
                fiscal_period = record["first_fp"]
                fiscal_year = fy if isinstance(fy, int) else end.year
            else:
                continue
            facts.append(
                {**_base_fact(concept, record), "fiscal_year": fiscal_year, "fiscal_period": fiscal_period}
            )

    facts.extend(derive_q4_facts(facts, duration_values))

    # Weighted shares (transient — never stored) labelled with the same quarter/FY scheme as the
    # facts, backing the shares-based Q4 EPS derivation. Runs after derive_q4_facts so the Q4 net
    # income it divides is available.
    shares_by_eps_concept: dict[str, dict[tuple[int, str], float]] = {}
    for eps_concept, share_tags in _EPS_SHARES_TAGS.items():
        share_values = _collect_companyfacts_values(usgaap, share_tags, "shares", instant=False)
        labelled: dict[tuple[int, str], float] = {}
        for (end, klass), record in share_values.items():
            if klass == "FY":
                labelled[(end.year, "FY")] = record["value"]
            elif klass == "Q":
                label = quarter_labels.get(end)
                if label is not None:
                    fiscal_period, fiscal_year = label
                    labelled[(fiscal_year, fiscal_period)] = record["value"]
        if labelled:
            shares_by_eps_concept[eps_concept] = labelled
    if shares_by_eps_concept:
        facts.extend(derive_q4_eps_facts(facts, shares_by_eps_concept))

    # NON_NEGATIVE hard-reject BEFORE the same-period metrics derive: a rejected negative row
    # (e.g. a derived Q4 revenue gone negative under a recast/vintage mismatch) must not leave
    # behind margins computed from it — margins pass the filter themselves (legitimately
    # negative), so they must never be built on an input the filter is about to drop.
    def _hard_reject_ok(fact: dict[str, Any]) -> bool:
        value = fact.get("value")
        if fact["concept"] in NON_NEGATIVE_CONCEPTS and isinstance(value, (int, float)) and value < 0:
            logger.warning(
                "companyfacts_reject concept=%s period=%s value=%s reason=negative",
                fact["concept"], fact["period_end"], value,
            )
            return False
        return True

    facts = [fact for fact in facts if _hard_reject_ok(fact)]
    facts.extend(fact for fact in derive_same_period_metrics(facts) if _hard_reject_ok(fact))

    # In-batch identity dedup.
    kept: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for fact in facts:
        identity = (
            fact["concept"], fact["period_end"], fact["fiscal_period"], fact["unit"], fact["accession"]
        )
        if identity in seen:
            continue
        seen.add(identity)
        kept.append(fact)
    return kept, meta


def _matching_ytd9(
    fy_fact: dict[str, Any],
    concept_values: Optional[dict[tuple[date, str], dict[str, Any]]],
) -> Optional[dict[str, Any]]:
    """The nine-month YTD slice belonging to a FY fact's fiscal year, or None.

    Match rule: the YTD9 comes from the SAME us-gaap tag as the FY fact (tags within one concept
    can carry different accounting scopes — total vs continuing-operations cash flow — and
    subtracting across scopes would put nine months of the difference into Q4), starts where the
    fiscal year starts (±3 days — tags occasionally disagree by a day), AND leaves a
    quarter-length residual (FY end − YTD9 end), so FY − YTD9 is guaranteed to describe exactly
    one discrete Q4 in one scope. No same-tag YTD9 → the caller falls back to ΣQ1–3.
    """
    if not concept_values:
        return None
    fy_start, fy_end = fy_fact["period_start"], fy_fact["period_end"]
    if fy_start is None:
        return None
    for (end, klass), record in concept_values.items():
        if klass != "YTD9" or record["period_start"] is None:
            continue
        if record.get("raw_tag") != fy_fact.get("raw_tag"):
            continue
        starts_together = abs((record["period_start"] - fy_start).days) <= 3
        residual_days = (fy_end - end).days
        if starts_together and _CF_QUARTER_WINDOW[0] <= residual_days <= _CF_QUARTER_WINDOW[1]:
            return record
    return None


def derive_q4_facts(
    facts: list[dict[str, Any]],
    duration_values: Optional[dict[str, dict[tuple[date, str], dict[str, Any]]]] = None,
) -> list[dict[str, Any]]:
    """Q4 for flow (duration, monetary) concepts where no discrete Q4 exists.

    Companies report Q4 only inside the 10-K's full-year figure, so quarterly mode would
    otherwise always miss the fourth bar. Preferred derivation: **Q4 = FY − YTD9** (the
    nine-month slice from the Q3 10-Q — two vintages instead of four, and it survives a missing
    Q1/Q2 10-Q at the edge of companyfacts history). Fallback: FY − (Q1+Q2+Q3), all three
    required. Derived rows mix vintages and are marked ``source="derived", reconciled=False`` so
    the UI badges them. Per-share/ratio units are never derived HERE — plain subtraction is
    wrong for a ratio — quarterly EPS gets its own shares-based derivation
    (``derive_q4_eps_facts``).

    NOTE: a previously ingested ΣQ-derived row keeps its stored value — the upsert identity
    (concept, period_end, fiscal_period, unit, accession) excludes ``value``, so the YTD9
    preference applies to newly ingested periods. Accepted: the two derivations agree by
    construction (mismatches >1% are logged below), and rewriting history through the
    idempotent writer would trade that residual for core-write-path churn.
    """
    groups: dict[tuple[str, Any], dict[str, dict[str, Any]]] = {}
    for fact in facts:
        if fact.get("unit") != "USD" or fact.get("period_start") is None:
            continue  # flows only: monetary durations
        groups.setdefault((fact["concept"], fact.get("fiscal_year")), {})[fact["fiscal_period"]] = fact

    derived: list[dict[str, Any]] = []
    for (concept, _fy), by_period in groups.items():
        fy_fact = by_period.get("FY")
        if fy_fact is None or "Q4" in by_period:
            continue
        quarters = [by_period.get(q) for q in ("Q1", "Q2", "Q3")]
        ytd9 = _matching_ytd9(fy_fact, (duration_values or {}).get(concept))
        if ytd9 is not None:
            value = fy_fact["value"] - ytd9["value"]
            period_start = ytd9["period_end"] + timedelta(days=1)
            if all(q is not None for q in quarters):
                # Observability for the dual-path window: the two derivations should agree
                # (ΣQ1–3 ≈ YTD9); a real gap means a restatement landed in one path only.
                sum_q = sum(q["value"] for q in quarters)
                if abs(sum_q - ytd9["value"]) > max(abs(fy_fact["value"]) * 0.01, 1.0):
                    logger.warning(
                        "companyfacts_q4_derivation_mismatch concept=%s fy=%s ytd9=%s sum_q=%s",
                        concept, fy_fact.get("fiscal_year"), ytd9["value"], sum_q,
                    )
        else:
            if any(q is None for q in quarters):
                continue
            value = fy_fact["value"] - sum(q["value"] for q in quarters)
            period_start = quarters[2]["period_end"] + timedelta(days=1)
        derived.append(
            {
                **fy_fact,
                "value": value,
                "period_start": period_start,
                "fiscal_period": "Q4",
                "source": "derived",
                "reconciled": False,
            }
        )
    return derived


# Weighted-average share-count tags backing each EPS concept — collected transiently for the Q4
# EPS derivation only; share counts are never stored as fact rows.
_EPS_SHARES_TAGS: dict[str, tuple[str, ...]] = {
    "earnings_per_share": (
        "WeightedAverageNumberOfSharesOutstandingBasic",
        "WeightedAverageNumberOfSharesOutstanding",
    ),
    "eps_diluted": ("WeightedAverageNumberOfDilutedSharesOutstanding",),
}

# EPS ≈ NI ÷ weighted shares must hold for every REPORTED period before Q4 EPS is derived —
# relative 5%, or one cent absolute (filed EPS is rounded to 2 decimals, so tiny EPS values
# carry large relative rounding). A failure means the share counts and the (restated) EPS
# history disagree — classically a mid-year split — and deriving would produce garbage.
_EPS_VALIDATION_REL_TOL = 0.05
_EPS_VALIDATION_ABS_TOL = 0.011


def derive_q4_eps_facts(
    facts: list[dict[str, Any]],
    shares_by_eps_concept: dict[str, dict[tuple[int, str], float]],
) -> list[dict[str, Any]]:
    """Derived Q4 EPS = Q4 net income ÷ Q4 weighted shares (the EdgarTools quarterization idea).

    Plain FY − ΣQ subtraction is wrong for EPS (weighted-average shares move between quarters),
    so Q4 EPS re-derives from first principles: Q4 shares = 4×FY − (Q1+Q2+Q3) (a weighted
    average over the year is the mean of the four quarterly averages), then Q4 NI ÷ Q4 shares.
    Requires the fiscal year's FY EPS, a Q4 net income (usually itself derived), and all four
    share counts; every reported period must pass the EPS ≈ NI ÷ shares consistency check
    (``_EPS_VALIDATION_*``) or the year is skipped. Derived rows are ``source="derived",
    reconciled=False`` — same badging as the flow derivation.
    """
    by_key: dict[tuple[str, Any, str], dict[str, Any]] = {
        (f["concept"], f.get("fiscal_year"), f["fiscal_period"]): f for f in facts
    }

    def _consistent(eps_concept: str, fy: Any, fp: str, shares: Optional[float]) -> bool:
        eps_fact = by_key.get((eps_concept, fy, fp))
        ni_fact = by_key.get(("net_income", fy, fp))
        if eps_fact is None or ni_fact is None or not shares:
            return True  # nothing reported to validate against
        expected = ni_fact["value"] / shares
        return abs(eps_fact["value"] - expected) <= max(
            abs(expected) * _EPS_VALIDATION_REL_TOL, _EPS_VALIDATION_ABS_TOL
        )

    derived: list[dict[str, Any]] = []
    for eps_concept, shares in shares_by_eps_concept.items():
        fiscal_years = {
            f.get("fiscal_year")
            for f in facts
            if f["concept"] == eps_concept and f["fiscal_period"] == "FY"
        }
        for fy in fiscal_years:
            if (eps_concept, fy, "Q4") in by_key:
                continue  # a rare discrete Q4 EPS is real — never overwrite it
            fy_eps = by_key.get((eps_concept, fy, "FY"))
            q4_ni = by_key.get(("net_income", fy, "Q4"))
            if fy_eps is None or q4_ni is None:
                continue
            fy_shares = shares.get((fy, "FY"))
            quarter_shares = [shares.get((fy, q)) for q in ("Q1", "Q2", "Q3")]
            if not fy_shares or any(not s or s <= 0 for s in quarter_shares) or fy_shares <= 0:
                continue
            q4_shares = 4.0 * fy_shares - sum(quarter_shares)  # type: ignore[arg-type]
            if q4_shares <= 0:
                continue
            # Split-basis guard: weighted counts drift single-digit percentages through
            # buybacks/issuance; a 1.5× spread across the four inputs means mixed pre-/post-
            # split bases (a mid-year split whose earlier 10-Qs were never restated — each
            # period can still pass the per-period gate because its EPS is on the same stale
            # basis). Deriving across bases would be garbage.
            all_counts = [fy_shares, *quarter_shares]
            if max(all_counts) / min(all_counts) > 1.5:  # type: ignore[type-var]
                logger.warning(
                    "companyfacts_q4_eps_skipped concept=%s fy=%s reason=share_basis_spread",
                    eps_concept, fy,
                )
                continue
            checks = [("FY", fy_shares), ("Q1", quarter_shares[0]),
                      ("Q2", quarter_shares[1]), ("Q3", quarter_shares[2])]
            if not all(_consistent(eps_concept, fy, fp, sh) for fp, sh in checks):
                logger.warning(
                    "companyfacts_q4_eps_skipped concept=%s fy=%s reason=eps_ni_shares_inconsistent",
                    eps_concept, fy,
                )
                continue
            # Numerator-wedge guard: FY EPS × FY shares should reproduce FY net income. The gap
            # is the part of the EPS numerator NOT in consolidated NI (preferred dividends,
            # noncontrolling interests — EPS divides income AVAILABLE TO COMMON), and on the
            # derived quarter that whole annual wedge lands in one number. Require it to be
            # small RELATIVE TO Q4 NI (not FY NI — the error concentrates where NI is small),
            # with a one-cent-per-share floor for filed-EPS rounding.
            fy_ni = by_key.get(("net_income", fy, "FY"))
            if fy_ni is None:
                continue
            wedge = abs(fy_eps["value"] * fy_shares - fy_ni["value"])
            if wedge > max(0.05 * abs(q4_ni["value"]), _EPS_VALIDATION_ABS_TOL * fy_shares):
                logger.warning(
                    "companyfacts_q4_eps_skipped concept=%s fy=%s reason=fy_numerator_wedge",
                    eps_concept, fy,
                )
                continue
            derived.append(
                {
                    **fy_eps,
                    "value": q4_ni["value"] / q4_shares,
                    "period_start": q4_ni["period_start"],
                    "period_end": q4_ni["period_end"],
                    "fiscal_period": "Q4",
                    "source": "derived",
                    "reconciled": False,
                }
            )
    return derived


def derive_same_period_metrics(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Same-period derived metrics per (fiscal_year, fiscal_period) group.

    Margins ×100 (unit "pure"), free_cash_flow = OCF − |capex|, working_capital = CA − CL,
    current_ratio = CA ÷ CL — the exact formulas the per-filing extractor uses
    (xbrl_service.extract_standardized_metrics), so companyfacts- and filing-sourced rows agree.
    Same-period arithmetic on SEC values is ``reconciled=True`` unless an input was itself
    unreconciled (a derived Q4 chain propagates its badge). Skipped when the group already carries
    the concept.

    DUAL-WRITER NOTE: these computed metrics are written by TWO paths with different ``source``
    values — here as ``"derived"`` and by the per-filing pipeline (which emits the same
    computations from ``extract_standardized_metrics``) as ``"edgar_xbrl"``. Which row holds
    ``is_latest`` for a period is last-writer-wins and therefore ingest-order dependent. That is
    accepted (audit decision D4): values converge across the paths by construction, and readers
    must never infer meaning from ``source == "derived"`` alone — "computed Q4" semantics are
    ``source == "derived" AND fiscal_period == "Q4"`` (see trend_analysis_service.build_dataset).
    """
    groups: dict[tuple[Any, Any], dict[str, dict[str, Any]]] = {}
    for fact in facts:
        key = (fact.get("fiscal_year"), fact.get("fiscal_period"))
        groups.setdefault(key, {})[fact["concept"]] = fact

    def _make(
        concept: str, value: float, template: dict[str, Any], inputs: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return {
            **template,
            "concept": concept,
            "raw_tag": None,
            "unit": _CONCEPT_UNITS.get(concept, "USD"),
            "value": value,
            "source": "derived",
            "reconciled": all(f.get("reconciled", False) for f in inputs),
        }

    derived: list[dict[str, Any]] = []
    for by_concept in groups.values():
        revenue = by_concept.get("revenue")
        if revenue and revenue["value"]:
            for margin_key, numerator_key in (
                ("net_margin", "net_income"),
                ("gross_margin", "gross_profit"),
                ("operating_margin", "operating_income"),
            ):
                numerator = by_concept.get(numerator_key)
                if (
                    margin_key not in by_concept
                    and numerator is not None
                    and numerator["period_end"] == revenue["period_end"]
                ):
                    derived.append(
                        _make(
                            margin_key,
                            (numerator["value"] / revenue["value"]) * 100,
                            revenue,
                            [revenue, numerator],
                        )
                    )

        ocf, capex = by_concept.get("operating_cash_flow"), by_concept.get("capital_expenditures")
        if (
            "free_cash_flow" not in by_concept
            and ocf is not None
            and capex is not None
            and ocf["period_end"] == capex["period_end"]
        ):
            derived.append(
                _make("free_cash_flow", ocf["value"] - abs(capex["value"]), ocf, [ocf, capex])
            )

        ca, cl = by_concept.get("current_assets"), by_concept.get("current_liabilities")
        if (
            ca is not None
            and cl is not None
            and ca["period_end"] == cl["period_end"]
            and ca["value"] >= 0
            and cl["value"] >= 0
        ):
            if "working_capital" not in by_concept:
                derived.append(_make("working_capital", ca["value"] - cl["value"], ca, [ca, cl]))
            if "current_ratio" not in by_concept and cl["value"] > 0:
                derived.append(_make("current_ratio", ca["value"] / cl["value"], ca, [ca, cl]))
    return derived


def upsert_facts_bulk(
    db: Session, facts: list[dict[str, Any]], *, commit: bool = True
) -> dict[str, int]:
    """Batched writer with ``upsert_facts`` semantics for a full-history companyfacts batch.

    A full ingest is ~23 concepts × up to ~50 periods — the per-row two-query loop in
    ``upsert_facts`` would be thousands of round trips. This prefetches the company's existing
    rows once, then applies the same rules in memory: identity skip (idempotent), ``is_latest``
    demotion per (concept, period_end, fiscal_period, unit), plus the D1 rule — a labelled
    Q1..Q4 row demotes the legacy NULL-``fiscal_period`` twin for the same period so a quarter
    never has two current rows. Facts must already carry ``reconciled`` (no gate runs here —
    see ``normalize_companyfacts``).
    """
    if not facts:
        return {"inserted": 0, "skipped": 0, "demoted": 0}
    company_id = facts[0]["company_id"]
    concepts = {f["concept"] for f in facts}
    rows = (
        db.query(FinancialFact)
        .filter(FinancialFact.company_id == company_id, FinancialFact.concept.in_(list(concepts)))
        .all()
    )
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

        for row in latest_by_key.pop(
            (fact["concept"], fact["period_end"], fact["fiscal_period"], fact["unit"]), []
        ):
            if row.is_latest:
                row.is_latest = False
                demoted += 1
        if fact["fiscal_period"] in _QUARTER_PERIODS:
            for row in null_fp_latest.pop((fact["concept"], fact["period_end"], fact["unit"]), []):
                if row.is_latest:
                    row.is_latest = False
                    demoted += 1

        db.add(FinancialFact(**fact, is_latest=True, reconciled=reconciled))
        inserted += 1

    if commit:
        db.commit()
    return {"inserted": inserted, "skipped": skipped, "demoted": demoted}


async def _fetch_companyfacts_async(cik: str) -> Optional[dict]:
    """Async companyfacts fetch through the SEC rate limiter (the REQUEST-PATH fetcher).

    Unlike the backfill's ``_fetch_companyfacts_sync`` (single cron worker, self-throttled sleep),
    this one is user-triggerable via the coverage endpoint, so it MUST share the token bucket +
    exponential backoff in ``sec_rate_limiter``. Returns ``None`` on any failure.
    """
    import httpx

    from app.config import settings
    from app.services.sec_rate_limiter import sec_rate_limiter

    cik_padded = str(cik).lstrip("0").zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
    headers = {"User-Agent": settings.SEC_USER_AGENT, "Accept": "application/json"}

    async def _get() -> Any:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()

    try:
        data = await sec_rate_limiter.execute_with_backoff(_get)
        return data if isinstance(data, dict) else None
    except Exception as exc:  # noqa: BLE001 - the caller degrades gracefully (no stamp, retry later)
        logger.warning("companyfacts async fetch failed for CIK %s: %s", cik, exc)
        return None


def _is_financial_sic(sic: Optional[str]) -> bool:
    """Financial-services SIC band (6000-6799) — lexical compare on the 4-digit String column,
    same convention as ``remediate_industry_facts``."""
    return bool(sic) and "6000" <= str(sic) <= "6799"


# Per-company in-flight sync dedup (the summary_pipeline._claim_inflight pattern): concurrent
# coverage requests for the same company collapse into one SEC fetch. Process-local is the right
# scope — prod is a single Cloud Run instance with Redis off.
_inflight_syncs: dict[int, asyncio.Event] = {}
COMPANYFACTS_INFLIGHT_WAIT_SECONDS = 25.0


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
    synced_at = company.facts_synced_at
    if synced_at is not None and synced_at.tzinfo is None:
        synced_at = synced_at.replace(tzinfo=timezone.utc)  # SQLite returns naive datetimes
    if not force and synced_at is not None:
        from app.config import settings

        if datetime.now(timezone.utc) - synced_at < timedelta(
            hours=settings.COMPANYFACTS_SYNC_TTL_HOURS
        ):
            newer_filing = (
                db.query(Filing.id)
                .filter(Filing.company_id == company.id, Filing.filing_date > synced_at)
                .first()
            )
            if newer_filing is None:
                return {"synced": True, "refreshed": False, "inserted": 0, "skipped": 0,
                        "demoted": 0, "unsupported_ifrs": False}

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
        return {"synced": True, "refreshed": True, **result,
                "unsupported_ifrs": meta["unsupported_ifrs"]}
    finally:
        if _inflight_syncs.get(company.id) is event:
            _inflight_syncs.pop(company.id, None)
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
