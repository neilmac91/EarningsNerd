"""Accession-aware XBRL extraction: debt."""

from typing import Any, Dict, List, Optional

from ..debt_concepts import DEBT_COMPONENT_CONCEPTS, classify_debt_concept
from .core import _currency, _iso_date, _numeric, _text_or_none, logger

# ---------------------------------------------------------------------------
# Source-qualified DEBT COMPONENT observations (debt-scope slice).
#
# The consolidated `long_term_debt` series is first-candidate-wins across concepts whose
# scopes DIFFER (`LongTermDebtNoncurrent` vs `LongTermDebt`), so one winning value can never
# establish how much of the issuer's debt it covers. These helpers retain each ADMISSIBLE debt
# concept independently — the `dividend_component_sum_series` precedent, because disjoint maturity
# bands are not alternative spellings — together with the identity a downstream scope claim needs:
# the exact qualified concept, the selected accession/form, the instant, the currency and unit, the
# original context reference, the reporting entity and the fact's own precision.
#
# They read the SAME already-fetched `xb` instance as every other extraction here: no second SEC
# request path, no companyfacts fallback, no taxonomy download. `long_term_debt` selection,
# ordering and public shape are untouched — this is purely additive evidence.


def _one_undimensioned_instant_fact(
    records: List[Dict[str, Any]],
    period_of_report: str,
    reporting_currency: Optional[str],
) -> Optional[Dict[str, Any]]:
    """The single unambiguous undimensioned instant fact AT ``period_of_report``, or None.

    Facts are filtered to ``reporting_currency`` first, for the same reason the value series are: a
    foreign private issuer tags the SAME balance in its reporting currency AND in a USD
    convenience translation, and treating those two as a conflict would suppress every component
    for exactly the filers whose debt scope is hardest to read. When no reporting currency is
    known, no currency filter applies and the ambiguity check below decides.

    Then stricter than ``_resolve_period_value`` on purpose. That resolver reconciles a filer who
    tags one figure twice at different precision, which is right for a value series; a debt
    COMPONENT that is about to be named, and possibly summed, must fail closed instead:

    * more than one distinct value at the anchor instant -> None (duplicate contexts are not
      rescued by preferring the finest ``decimals``);
    * more than one distinct ``entity_identifier`` -> None (entity ambiguity);
    * an element whose declared period type is not ``instant`` -> None (duration/instant mix-up);
    * a dimensioned fact, a duration fact, a non-anchor instant or a missing currency -> skipped.
    """
    values: Dict[float, Dict[str, Any]] = {}
    entities: set = set()
    for row in records:
        if row.get("is_dimensioned"):
            continue
        if _iso_date(row.get("period_start")) is not None:
            continue  # a duration fact, not a balance
        # Reject only a KNOWN non-instant period type. An absent/NaN column is unknown, not
        # "duration": rejecting on it would drop every fact the moment the column is missing, so
        # the instant-date check below stays the load-bearing guard. (`str(nan)` is "nan", which a
        # naive comparison would treat as a mismatch.)
        period_type = _text_or_none(row.get("element_period_type"))
        if period_type is not None and period_type.lower() != "instant":
            continue
        instant = _iso_date(row.get("period_instant")) or _iso_date(row.get("period_end"))
        if instant != period_of_report:
            continue
        value = _numeric(row.get("numeric_value"))
        if value is None:
            continue
        row_currency = _currency(row)
        if row_currency is None:
            continue  # a monetary balance with no unit cannot carry a currency-qualified claim
        if reporting_currency is not None and row_currency != reporting_currency:
            continue  # a convenience translation, not the issuer's reported balance
        entity = row.get("entity_identifier")
        if entity is not None and str(entity).strip():
            entities.add(str(entity).strip())
        values.setdefault(round(value, 4), row)
    if len(values) != 1 or len(entities) > 1:
        return None
    return next(iter(values.values()))


def debt_component_observations(
    xb: Any,
    period_of_report: str,
    *,
    reporting_currency: Optional[str] = None,
    accession_number: Optional[str] = None,
    form: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Source-qualified debt observations for the filing's OWN balance date, newest concept order.

    One record per admissible concept that resolves to a single unambiguous undimensioned instant
    fact at ``period_of_report``. Each record carries only OBSERVED identity — nothing is inferred,
    defaulted or reconstructed. A concept that does not resolve is simply absent, which downstream
    reads as "not separately reported", never as zero.

    Returns [] for an instance with no admissible debt concept (a genuinely debt-free filer and a
    filer whose debt is tagged under concepts this registry does not admit are both unknown here,
    and are distinguished by the consumer, not by a fabricated value).
    """
    observations: List[Dict[str, Any]] = []
    for qualified_concept in DEBT_COMPONENT_CONCEPTS:
        identity = classify_debt_concept(qualified_concept)
        if identity is None:  # defensive: the registry is the source of both lists
            continue
        try:
            df = xb.facts.query().by_concept(qualified_concept, exact=True).to_dataframe()
        except Exception as exc:  # noqa: BLE001 - any query failure means "no facts"
            logger.debug(f"Debt component query failed for {qualified_concept}: {exc}")
            continue
        if df is None or getattr(df, "empty", True):
            continue
        row = _one_undimensioned_instant_fact(
            df.to_dict("records"), period_of_report, reporting_currency,
        )
        if row is None:
            continue
        observations.append({
            "concept": qualified_concept,
            "scope": identity.scope,
            "basis": identity.basis,
            "value": _numeric(row.get("numeric_value")),
            "instant": period_of_report,
            "currency": _currency(row),
            "unit_ref": _text_or_none(row.get("unit_ref")),
            "context_ref": _text_or_none(row.get("context_ref")),
            "entity_identifier": _text_or_none(row.get("entity_identifier")),
            "entity_scheme": _text_or_none(row.get("entity_scheme")),
            "decimals": _text_or_none(row.get("decimals")),
            "accn": accession_number,
            "form": form,
        })
    return observations
