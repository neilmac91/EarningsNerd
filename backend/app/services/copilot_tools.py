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
queries, and closes it in a ``finally``. Callers bind company, accession and native currency
(captured eagerly from the snapshot) via a closure.

Everything here is tolerant: ``run_tool`` never raises — unknown/absent data and unexpected errors
become ``{"error": ...}`` dicts so the streaming loop stays well-formed.
"""
from __future__ import annotations

import logging
import math
import re
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
                "and fiscal periods are available in THIS filing and its own comparative XBRL data. Call this "
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
                "Fetch the exact, as-reported value of a single financial concept in this filing "
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
        "unit": canonical_unit(fact.unit),
        "period_start": fact.period_start.isoformat() if fact.period_start else None,
        "period_end": fact.period_end.isoformat() if fact.period_end else None,
        "fiscal_year": fact.fiscal_year,
        "fiscal_period": fact.fiscal_period,
        "raw_tag": fact.raw_tag,
        "accession": fact.accession,
    }


def canonical_unit(unit: str | None) -> str | None:
    """Canonicalize explicit currency/unit aliases without converting values or dimensions."""
    if not isinstance(unit, str):
        return None
    text = unit.strip().upper().replace("_PER_SHARE", "/SHARES").replace(" PER SHARE", "/SHARES")
    if text in {"PURE", "SHARES"}:
        return text.lower()
    match = re.fullmatch(r"([A-Z]{3})(/SHARES?)?", text)
    if not match:
        return None
    currency = "CNY" if match[1] == "RMB" else match[1]
    return currency + ("/shares" if match[2] else "")


class _Unavailable(Exception):
    """Expected ambiguity or missing evidence, represented as a tool error."""


def _scope(db: Any, company_id: int, accession: str) -> Any:
    # Scope lives in one query constructor shared by every direct/list/arithmetic path.
    # Historical own-filing facts remain valid even after a newer filing demotes is_latest.
    return db.query(FinancialFact).filter(
        FinancialFact.company_id == company_id,
        FinancialFact.accession == accession,
    )


def _bounded_rows(query: Any) -> list[FinancialFact]:
    rows = query.limit(257).all()
    if len(rows) > 256:
        raise _Unavailable("too_many_candidates")
    return rows


def _select_fact(rows: list[FinancialFact], reporting_currency: str | None) -> FinancialFact | None:
    currency = canonical_unit(reporting_currency)
    if currency and "/" not in currency and currency not in {"pure", "shares"}:
        rows = [r for r in rows if canonical_unit(r.unit) in {currency, f"{currency}/shares", "pure", "shares"}]
    if not rows:
        return None
    latest = max(r.period_end for r in rows)
    rows = [r for r in rows if r.period_end == latest]
    # Multiple units, fiscal bases, or alias rows are ambiguous; never pick insertion order.
    if len(rows) != 1:
        raise _Unavailable("ambiguous_fact")
    fact = rows[0]
    if canonical_unit(fact.unit) is None or not math.isfinite(float(fact.value)):
        raise _Unavailable("invalid_fact")
    return fact


def _query_fact(
    db: Any, company_id: int, accession: str, concept: str,
    fiscal_year: Optional[int] = None, fiscal_period: Optional[str] = None,
    *, reporting_currency: str | None = None, period_end: Any = None,
) -> Optional[FinancialFact]:
    query = _scope(db, company_id, accession).filter(FinancialFact.concept == concept)
    if fiscal_year is not None:
        query = query.filter(FinancialFact.fiscal_year == fiscal_year)
    if fiscal_period is not None:
        query = query.filter(FinancialFact.fiscal_period == fiscal_period)
    if period_end is not None:
        query = query.filter(FinancialFact.period_end == period_end)
    return _select_fact(_bounded_rows(query.order_by(desc(FinancialFact.period_end))), reporting_currency)


def _run_list_available_concepts(db: Any, company_id: int, accession: str) -> dict[str, Any]:
    rows = _bounded_rows(_scope(db, company_id, accession))
    return {
        "concepts": sorted({r.concept for r in rows if r.concept}),
        "fiscal_periods": sorted({r.fiscal_period for r in rows if r.fiscal_period}),
    }


def _missing(db: Any, company_id: int, accession: str, error: str) -> dict[str, Any]:
    return {"error": error, "available_concepts": _run_list_available_concepts(db, company_id, accession)["concepts"]}


def _run_get_financial_fact(
    db: Any, company_id: int, accession: str, args: dict, currency: str | None,
) -> dict[str, Any]:
    concept = args.get("concept")
    if not isinstance(concept, str) or not concept:
        return _missing(db, company_id, accession, "missing_concept")
    fact = _query_fact(db, company_id, accession, concept, args.get("fiscal_year"),
                       args.get("fiscal_period"), reporting_currency=currency)
    if fact is None:
        return _missing(db, company_id, accession, "not_disclosed")
    return _fact_provenance(fact)


def _has_duration(fact: FinancialFact) -> bool:
    # FY can be inferred from form by the writer; it cannot prove an actual duration.
    return fact.period_start is not None and fact.period_start < fact.period_end


def _prior_comparable(current: FinancialFact, prior: FinancialFact) -> bool:
    if not _has_duration(prior):
        return False
    # Calendar years and 52/53-week fiscal years shift corresponding endpoints by 357–373
    # days. Requiring BOTH endpoints excludes annual-versus-quarter/YTD substitutions.
    return (
        357 <= (current.period_start - prior.period_start).days <= 373
        and 357 <= (current.period_end - prior.period_end).days <= 373
        and abs((current.period_end - current.period_start).days - (prior.period_end - prior.period_start).days) <= 8
    )


def _run_compute_metric(
    db: Any, company_id: int, accession: str, args: dict, currency: str | None,
) -> dict[str, Any]:
    kind, concept = args.get("kind"), args.get("concept")
    if not isinstance(concept, str) or not concept:
        return _missing(db, company_id, accession, "missing_concept")
    if kind not in {"yoy_growth", "margin"}:
        return {"error": "unknown_metric_kind", "kind": kind}
    current = _query_fact(db, company_id, accession, concept, args.get("fiscal_year"),
                          args.get("fiscal_period"), reporting_currency=currency)
    if current is None:
        return _missing(db, company_id, accession, "not_disclosed")
    if not _has_duration(current):
        return {"error": "basis_unavailable", "concept": concept}
    if kind == "yoy_growth":
        rows = _bounded_rows(_scope(db, company_id, accession).filter(
            FinancialFact.concept == concept, FinancialFact.period_end < current.period_end,
        ))
        comparable = [r for r in rows if _prior_comparable(current, r)]
        prior = _select_fact(comparable, currency)
        if prior is None:
            return {"error": "basis_unavailable" if any(not _has_duration(r) for r in rows) else "no_prior_period", "concept": concept}
        if canonical_unit(current.unit) != canonical_unit(prior.unit):
            return {"error": "incompatible_units", "concept": concept}
        if float(prior.value) == 0:
            return {"error": "prior_period_zero", "concept": concept}
        result = _fact_provenance(current)
        result.update({
            "kind": kind, "value": (float(current.value) - float(prior.value)) / abs(float(prior.value)),
            "unit": "pure", "current_value": float(current.value), "prior_value": float(prior.value),
            "prior_period_end": prior.period_end.isoformat(), "prior_fiscal_year": prior.fiscal_year,
            "source_facts": [_fact_provenance(current), _fact_provenance(prior)],
        })
        return result
    denominator_concept = args.get("denominator_concept") or _DEFAULT_MARGIN_DENOMINATORS.get(concept, "revenue")
    denominator = _query_fact(db, company_id, accession, denominator_concept,
                              reporting_currency=currency, period_end=current.period_end)
    if denominator is None:
        return {"error": "denominator_not_disclosed", "denominator_concept": denominator_concept}
    if not _has_duration(denominator) or current.period_start != denominator.period_start:
        return {"error": "basis_unavailable", "concept": concept}
    if canonical_unit(current.unit) != canonical_unit(denominator.unit):
        return {"error": "incompatible_units", "concept": concept}
    if float(denominator.value) == 0:
        return {"error": "denominator_zero", "denominator_concept": denominator_concept}
    result = _fact_provenance(current)
    result.update({
        "kind": kind, "value": float(current.value) / float(denominator.value), "unit": "pure",
        "numerator_value": float(current.value), "denominator_concept": denominator_concept,
        "denominator_value": float(denominator.value),
        "source_facts": [_fact_provenance(current), _fact_provenance(denominator)],
    })
    return result


def run_tool(
    name: str, args: dict, company_id: int, *, accession_number: str | None = None,
    reporting_currency: str | None = None,
) -> dict[str, Any]:
    """Execute against trusted viewed-filing scope in an independently closed DB session.

    Neither accession nor currency is accepted from model arguments. Missing trusted scope
    fails closed, including for concept discovery. No other filing supplies missing data.
    """
    if not isinstance(accession_number, str) or not re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accession_number):
        return {"error": "filing_scope_unavailable"}
    db = None
    try:
        db = SessionLocal()
        if name == "list_available_concepts":
            return _run_list_available_concepts(db, company_id, accession_number)
        if not isinstance(args, dict):
            return {"error": "invalid_arguments"}
        if name == "get_financial_fact":
            return _run_get_financial_fact(db, company_id, accession_number, args, reporting_currency)
        if name == "compute_metric":
            return _run_compute_metric(db, company_id, accession_number, args, reporting_currency)
        return {"error": "unknown_tool", "name": name}
    except _Unavailable as exc:
        return {"error": str(exc)}
    except Exception:  # noqa: BLE001 — no DB/provider details in model-visible errors
        logger.warning("copilot tool failed", exc_info=False)
        return {"error": "tool_failed"}
    finally:
        if db is not None:
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
        **{key: fact_dict.get(key) for key in (
            "accession", "unit", "period_start", "period_end", "fiscal_year", "fiscal_period",
            "raw_tag", "source_facts", "denominator_concept",
        )},
    }
