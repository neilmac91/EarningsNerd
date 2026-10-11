"""Reconcile normalized facts against local invariants and authoritative values."""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import FinancialFact
from app.services.facts.concepts import (
    CROSS_CHECK_TOLERANCE, HEADLINE_GAAP_TAGS, NON_NEGATIVE_CONCEPTS,
    _INSTANT_HEADLINE, _MAGNITUDE_TOLERANCE, _parse_date,
)
from app.services.facts.lineage import (
    annotate_filing_calculations, authoritative_reconciliation, local_reconciliation,
)
from app.services.facts.transport import logger


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
