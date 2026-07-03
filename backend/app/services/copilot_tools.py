"""Numeric XBRL tool-use for the "Ask this Filing" Copilot (P5).

The Copilot must never answer a numeric question (revenue, margins, YoY, EPS …) from prose recall or
by computing the number itself — those are exactly the figures users come to verify. Instead it calls
the function-calling tools defined here, which read the *exact* values from the normalized
:class:`~app.models.financial_fact.FinancialFact` table and let the **server** do all arithmetic. Each
successful tool result carries the provenance needed to render it as a verified citation (reusing the
existing citation shape, so the frontend renders it as-is).

Session lifetime is the subtle part. The Copilot's SSE generator runs *after* the request DB session
may already be gone (the same reason P1 added ``snapshot_filing``), so a tool **must not** touch the
request ``db``. Every :func:`run_tool` call therefore opens its own short-lived ``SessionLocal()``,
queries, and closes it in a ``finally``. Callers bind ``company_id`` (captured eagerly from the
snapshot) via a closure.

Everything here is tolerant: ``run_tool`` never raises — unknown/absent data and unexpected errors
become ``{"error": ...}`` dicts so the streaming loop stays well-formed.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import desc

from app.database import SessionLocal
from app.models.financial_fact import FinancialFact

logger = logging.getLogger(__name__)

# Human-readable labels for the standardized concepts, used in the citation excerpt. Unknown concepts
# fall back to a title-cased version of the raw key, so this never has to be exhaustive.
_CONCEPT_LABELS = {
    "revenue": "Revenue",
    "net_income": "Net income",
    "gross_profit": "Gross profit",
    "operating_income": "Operating income",
    "total_assets": "Total assets",
    "total_liabilities": "Total liabilities",
    "stockholders_equity": "Stockholders' equity",
    "cash_and_equivalents": "Cash & equivalents",
    "eps_basic": "EPS (basic)",
    "eps_diluted": "EPS (diluted)",
    "shares_outstanding": "Shares outstanding",
}

# Default denominators for the "margin" derived metric, so the model can ask for e.g. a gross margin
# without having to know that the denominator is revenue.
_DEFAULT_MARGIN_DENOMINATORS = {
    "gross_profit": "revenue",
    "operating_income": "revenue",
    "net_income": "revenue",
}

# OpenAI-format function-calling tool schemas (the wire contract handed to the model).
TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_available_concepts",
            "description": (
                "List which standardized financial concepts (e.g. revenue, net_income, gross_profit) "
                "and fiscal periods are available for THIS company from its XBRL data. Call this "
                "first when you are unsure whether a figure is disclosed."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_financial_fact",
            "description": (
                "Fetch the exact, as-reported value of a single financial concept for this company "
                "from XBRL. Returns the authoritative number plus provenance. Use this for ANY "
                "specific financial figure — never state a number from memory."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "concept": {
                        "type": "string",
                        "description": (
                            "Standardized concept key, e.g. 'revenue', 'net_income', 'gross_profit'. "
                            "Use list_available_concepts to discover valid keys."
                        ),
                    },
                    "fiscal_year": {
                        "type": "integer",
                        "description": "Optional fiscal year (e.g. 2024). Omit for the most recent.",
                    },
                    "fiscal_period": {
                        "type": "string",
                        "description": "Optional fiscal period: 'FY' or 'Q1'..'Q4'. Omit for the most recent.",
                    },
                },
                "required": ["concept"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compute_metric",
            "description": (
                "Compute a derived metric on the SERVER from exact XBRL values. 'yoy_growth' returns "
                "the year-over-year growth of a concept; 'margin' returns numerator/denominator (e.g. "
                "gross_profit / revenue). The server performs the arithmetic — never compute it yourself."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["yoy_growth", "margin"],
                        "description": "The derived metric to compute.",
                    },
                    "concept": {
                        "type": "string",
                        "description": "Concept for yoy_growth, or the numerator concept for margin.",
                    },
                    "denominator_concept": {
                        "type": "string",
                        "description": (
                            "Denominator concept for 'margin' (defaults to 'revenue' for common "
                            "profitability concepts). Ignored for 'yoy_growth'."
                        ),
                    },
                    "fiscal_year": {
                        "type": "integer",
                        "description": "Optional fiscal year of the (current) period. Omit for most recent.",
                    },
                    "fiscal_period": {
                        "type": "string",
                        "description": "Optional fiscal period: 'FY' or 'Q1'..'Q4'. Omit for most recent.",
                    },
                },
                "required": ["kind", "concept"],
            },
        },
    },
]


def _concept_label(concept: str) -> str:
    """Human-readable label for a concept key (falls back to a title-cased form)."""
    return _CONCEPT_LABELS.get(concept, concept.replace("_", " ").title())


def describe_tool_call(name: str, args: Optional[dict] = None) -> str:
    """A short, present-tense label for a tool call, for the live "show the work" ticker.

    e.g. ``("get_financial_fact", {"concept": "revenue"})`` → ``"Looking up revenue"``. Never raises;
    falls back to a generic label for unknown tools / missing args.
    """
    args = args if isinstance(args, dict) else {}
    concept = args.get("concept")
    concept_label = _concept_label(concept).lower() if isinstance(concept, str) and concept else None

    if name == "list_available_concepts":
        return "Scanning available financials"
    if name == "get_financial_fact":
        return f"Looking up {concept_label}" if concept_label else "Looking up a financial figure"
    if name == "compute_metric":
        target = concept_label or "a metric"
        kind = args.get("kind")
        if kind == "yoy_growth":
            return f"Computing {target} YoY growth"
        if kind == "margin":
            return f"Computing {target} margin"
        return f"Computing {target}"
    return f"Running {name}"


def _format_value(value: float, unit: str) -> str:
    """Format a numeric value for display in a citation excerpt.

    USD amounts get $ + thousands separators (scaled to B/M when large); shares get plain separators;
    per-share / pure / ratio values keep a couple of decimals.
    """
    unit_lower = (unit or "").lower()
    if unit_lower == "usd":
        magnitude = abs(value)
        if magnitude >= 1_000_000_000:
            return f"${value / 1_000_000_000:,.2f}B"
        if magnitude >= 1_000_000:
            return f"${value / 1_000_000:,.2f}M"
        return f"${value:,.0f}"
    if unit_lower == "shares":
        return f"{value:,.0f}"
    if unit_lower in ("usd/shares", "pure"):
        return f"{value:,.2f}"
    return f"{value:,.2f}"


def _fact_provenance(fact: FinancialFact) -> dict[str, Any]:
    """Project the provenance + value fields of a ``FinancialFact`` into a JSON-serializable dict."""
    return {
        "concept": fact.concept,
        "value": float(fact.value),
        "unit": fact.unit,
        "period_end": fact.period_end.isoformat() if fact.period_end else None,
        "fiscal_year": fact.fiscal_year,
        "fiscal_period": fact.fiscal_period,
        "raw_tag": fact.raw_tag,
        "accession": fact.accession,
    }


def _query_fact(
    db: Any,
    company_id: int,
    concept: str,
    fiscal_year: Optional[int] = None,
    fiscal_period: Optional[str] = None,
) -> Optional[FinancialFact]:
    """Return the matching latest fact, or None.

    Always scoped to ``company_id`` and ``is_latest == True``. When ``fiscal_year``/``fiscal_period``
    are given they filter exactly; otherwise the most recent period (by ``period_end``) wins.
    """
    query = db.query(FinancialFact).filter(
        FinancialFact.company_id == company_id,
        FinancialFact.concept == concept,
        FinancialFact.is_latest.is_(True),
    )
    if fiscal_year is not None:
        query = query.filter(FinancialFact.fiscal_year == fiscal_year)
    if fiscal_period is not None:
        query = query.filter(FinancialFact.fiscal_period == fiscal_period)
    return query.order_by(desc(FinancialFact.period_end)).first()


def _available_concepts(db: Any, company_id: int) -> list[str]:
    """Distinct concept keys this company has latest facts for (for not_disclosed hints)."""
    rows = (
        db.query(FinancialFact.concept)
        .filter(
            FinancialFact.company_id == company_id,
            FinancialFact.is_latest.is_(True),
        )
        .distinct()
        .all()
    )
    return sorted({row[0] for row in rows if row[0]})


def _run_list_available_concepts(db: Any, company_id: int) -> dict[str, Any]:
    """Tool body for ``list_available_concepts``."""
    rows = (
        db.query(FinancialFact.concept, FinancialFact.fiscal_period)
        .filter(
            FinancialFact.company_id == company_id,
            FinancialFact.is_latest.is_(True),
        )
        .distinct()
        .all()
    )
    concepts = sorted({row[0] for row in rows if row[0]})
    fiscal_periods = sorted({row[1] for row in rows if row[1]})
    return {"concepts": concepts, "fiscal_periods": fiscal_periods}


def _run_get_financial_fact(db: Any, company_id: int, args: dict) -> dict[str, Any]:
    """Tool body for ``get_financial_fact``."""
    concept = args.get("concept")
    if not concept or not isinstance(concept, str):
        return {"error": "missing_concept", "available_concepts": _available_concepts(db, company_id)}
    fact = _query_fact(
        db,
        company_id,
        concept,
        fiscal_year=args.get("fiscal_year"),
        fiscal_period=args.get("fiscal_period"),
    )
    if fact is None:
        return {"error": "not_disclosed", "available_concepts": _available_concepts(db, company_id)}
    return _fact_provenance(fact)


def _run_compute_metric(db: Any, company_id: int, args: dict) -> dict[str, Any]:
    """Tool body for ``compute_metric`` — the server performs all arithmetic on exact values."""
    kind = args.get("kind")
    concept = args.get("concept")
    if not concept or not isinstance(concept, str):
        return {"error": "missing_concept", "available_concepts": _available_concepts(db, company_id)}
    fiscal_year = args.get("fiscal_year")
    fiscal_period = args.get("fiscal_period")

    if kind == "yoy_growth":
        current = _query_fact(db, company_id, concept, fiscal_year, fiscal_period)
        if current is None:
            return {"error": "not_disclosed", "available_concepts": _available_concepts(db, company_id)}
        # The prior-year comparable is the same concept/period one fiscal year earlier. Match on
        # fiscal_year-1 when known; otherwise fall back to the second-most-recent matching period.
        prior: Optional[FinancialFact] = None
        if current.fiscal_year is not None:
            prior = _query_fact(
                db,
                company_id,
                concept,
                fiscal_year=current.fiscal_year - 1,
                fiscal_period=current.fiscal_period,
            )
        if prior is None:
            prior = (
                db.query(FinancialFact)
                .filter(
                    FinancialFact.company_id == company_id,
                    FinancialFact.concept == concept,
                    FinancialFact.is_latest.is_(True),
                    FinancialFact.period_end < current.period_end,
                )
                .order_by(desc(FinancialFact.period_end))
                .first()
            )
        if prior is None:
            return {"error": "no_prior_period", "concept": concept}
        prior_value = float(prior.value)
        if prior_value == 0:
            return {"error": "prior_period_zero", "concept": concept}
        current_value = float(current.value)
        growth = (current_value - prior_value) / abs(prior_value)
        result = _fact_provenance(current)
        result.update(
            {
                "kind": "yoy_growth",
                "value": growth,
                "unit": "pure",
                "current_value": current_value,
                "prior_value": prior_value,
                "prior_period_end": prior.period_end.isoformat() if prior.period_end else None,
                "prior_fiscal_year": prior.fiscal_year,
            }
        )
        return result

    if kind == "margin":
        denominator_concept = args.get("denominator_concept") or _DEFAULT_MARGIN_DENOMINATORS.get(
            concept, "revenue"
        )
        numerator = _query_fact(db, company_id, concept, fiscal_year, fiscal_period)
        if numerator is None:
            return {"error": "not_disclosed", "available_concepts": _available_concepts(db, company_id)}
        # Match the denominator to the numerator's EXACT period_end (a non-nullable Date) so the
        # ratio is internally consistent even when fiscal_year/fiscal_period are null on a fact.
        denominator = (
            db.query(FinancialFact)
            .filter(
                FinancialFact.company_id == company_id,
                FinancialFact.concept == denominator_concept,
                FinancialFact.period_end == numerator.period_end,
                FinancialFact.is_latest.is_(True),
            )
            .first()
        )
        if denominator is None:
            return {"error": "denominator_not_disclosed", "denominator_concept": denominator_concept}
        denominator_value = float(denominator.value)
        if denominator_value == 0:
            return {"error": "denominator_zero", "denominator_concept": denominator_concept}
        numerator_value = float(numerator.value)
        margin = numerator_value / denominator_value
        result = _fact_provenance(numerator)
        result.update(
            {
                "kind": "margin",
                "value": margin,
                "unit": "pure",
                "numerator_value": numerator_value,
                "denominator_concept": denominator_concept,
                "denominator_value": denominator_value,
            }
        )
        return result

    return {"error": "unknown_metric_kind", "kind": kind}


def run_tool(name: str, args: dict, company_id: int) -> dict[str, Any]:
    """Execute a Copilot tool by name and return a JSON-serializable result dict.

    Opens its **own** ``SessionLocal()`` (the SSE generator runs after the request session may be
    gone), dispatches to the tool body, and always closes the session in ``finally``. Tolerant: any
    unexpected failure becomes ``{"error": ...}`` rather than raising, so the streaming tool-call loop
    never breaks.

    Args:
        name: Tool name (one of the functions declared in :data:`TOOLS`).
        args: Decoded JSON arguments for the tool (may be empty).
        company_id: The filing's company id, bound by the caller's closure.

    Returns:
        A JSON-serializable dict — either a successful result (with provenance) or ``{"error": ...}``.
    """
    db = SessionLocal()
    try:
        if name == "list_available_concepts":
            return _run_list_available_concepts(db, company_id)
        if name == "get_financial_fact":
            return _run_get_financial_fact(db, company_id, args or {})
        if name == "compute_metric":
            return _run_compute_metric(db, company_id, args or {})
        return {"error": "unknown_tool", "name": name}
    except Exception as e:  # noqa: BLE001 — tolerant: tools never raise into the stream loop
        logger.warning("copilot tool %s failed: %s", name, str(e)[:200])
        return {"error": "tool_failed", "message": str(e)[:200]}
    finally:
        db.close()


def fact_to_citation(fact_dict: dict[str, Any]) -> dict[str, Any]:
    """Render a successful tool fact result as a citation dict (existing citation shape, minus ``n``).

    Reuses the same ``{excerpt, section_ref, verified, fragment_url}`` shape as text citations so the
    frontend renders an XBRL fact in the Sources list / chips with a Verified badge — no frontend
    change. ``n`` is assigned by the caller's unified citation-resolution pass (one continuous
    sequence across text and fact citations, in first-appearance order — see
    ``copilot_service._resolve_citations``). ``fragment_url`` is the filing document URL when known
    (XBRL facts have no in-text fragment), populated by the caller.
    """
    concept = fact_dict.get("concept") or "value"
    label = _concept_label(concept)
    kind = fact_dict.get("kind")
    value = fact_dict.get("value")
    unit = fact_dict.get("unit") or ""
    fy = fact_dict.get("fiscal_year")
    period = fact_dict.get("fiscal_period")
    period_label = f"FY{fy}/{period}" if fy and period else (f"FY{fy}" if fy else (period or ""))

    if kind == "yoy_growth" and isinstance(value, (int, float)):
        excerpt = f"{label} YoY growth = {value * 100:,.1f}%"
    elif kind == "margin" and isinstance(value, (int, float)):
        excerpt = f"{label} margin = {value * 100:,.1f}%"
    elif isinstance(value, (int, float)):
        excerpt = f"{label} = {_format_value(float(value), unit)} {unit}".rstrip()
    else:
        excerpt = label
    if period_label:
        excerpt = f"{excerpt} ({period_label})"

    raw_tag = fact_dict.get("raw_tag") or concept
    return {
        "excerpt": excerpt,
        "section_ref": f"XBRL · {raw_tag}",
        "verified": True,
        "fragment_url": None,
        # Machine-readable value + concept the chip vouches for (the excerpt only carries the
        # display rendering) — lets the eval harness re-verify value AND concept adjacency on
        # the final answer without parsing formatted strings. The frontend ignores the extra keys.
        "value": float(value) if isinstance(value, (int, float)) else None,
        "value_kind": kind,
        "concept": concept,
    }
