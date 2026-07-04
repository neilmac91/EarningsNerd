"""Normalize the standardized XBRL metrics we already extract into queryable `financial_fact` rows.

`normalize_standardized_to_facts` is pure (dict in → list[dict] out, unit-testable). `upsert_facts`
writes them while maintaining the restatement-safe `is_latest` flag.

v1 sources only the current period each filing reports, attributed to that filing's accession —
accurate and dependency-free (it reuses `xbrl_service.extract_standardized_metrics`). A
local-invariant reconciliation gate (`reconcile_facts`, no network) runs on write: it hard-rejects
impossible values and flags implausible ones (`reconciled=False`) so the UI can surface them honestly
("reconciled or visibly flagged" — strategy §3.5/§5). The authoritative cross-check vs `data.sec.gov`
and cross-source backfill (companyfacts / FSDS / Frames) remain later waves.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session, joinedload

from app.models import Company, Filing, FinancialFact

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

    db.commit()
    return {"inserted": inserted, "skipped": skipped, "rejected": rejected}


def process_filing_facts(
    db: Session,
    filing,
    *,
    extract=None,
    standardized: Optional[dict] = None,
    authoritative: Optional[dict[tuple[str, date], float]] = None,
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
    result = upsert_facts(
        db,
        facts,
        period_of_report=getattr(filing, "period_of_report", None),
        authoritative=authoritative,
    )
    filing.processed_facts_at = datetime.now(timezone.utc)
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


def _is_financial_sic(sic: Any) -> bool:
    """True when a SIC code falls in the broad financial-services band (6000–6799)."""
    try:
        code = int(str(sic)[:4]) if sic not in (None, "") else None
    except (TypeError, ValueError):
        return False
    return code is not None and 6000 <= code <= 6799


def remediate_industry_facts(
    db: Session,
    *,
    refetch,
    tickers: Optional[list[str]] = None,
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """Re-extract & re-normalize FINANCIAL-INSTITUTION filings so persisted ``xbrl_data`` and
    ``financial_fact`` carry the industry-correct revenue/components (filing 528 / MCB fix).

    Existing bank filings hold a fee-income-only "revenue" subset. Because ``raw_tag`` is not in the
    fact identity key, a plain re-upsert would SKIP the stale rows, so we delete the affected
    concepts for each filing and re-insert from the corrected extraction.

    ``refetch(company, filing) -> Optional[dict]`` returns fresh ``xbrl_data`` (or None to skip) — it
    is injected so this function stays network-free and unit-testable; the CLI wires the real
    (statement-aware) XBRL extractor. Filings are processed **oldest-first per company** so corrected
    current values reconcile against corrected priors (avoiding false magnitude flags), and the
    newest filing wins ``is_latest``. Cross-check is intentionally OFF (authoritative=None): SEC
    companyfacts has no single authoritative tag for a bank's components/total.
    """
    companies_q = db.query(Company)
    if tickers:
        companies_q = companies_q.filter(Company.ticker.in_([t.upper() for t in tickers]))
    companies = [c for c in companies_q.all() if tickers or _is_financial_sic(getattr(c, "sic", None))]

    stats = {"companies": 0, "filings_refetched": 0, "filings_skipped": 0,
             "facts_deleted": 0, "facts_inserted": 0, "errors": 0}
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
                continue
            if not fresh:
                stats["filings_skipped"] += 1
                continue
            processed += 1
            stats["filings_refetched"] += 1
            if dry_run:
                continue
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
            stats["facts_deleted"] += deleted or 0
            db.commit()
            result = process_filing_facts(db, filing)  # cross_check off (authoritative=None)
            if result is not None:
                stats["facts_inserted"] += result["inserted"]
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
