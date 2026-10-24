"""Normalize SEC companyfacts into reported and derived fiscal-period rows."""
from __future__ import annotations

from datetime import date
from typing import Any, Callable

from app.services.fact_provenance import fact_operand
from app.services.facts.calendar import (
    _fiscal_year_windows, _label_quarters, fiscal_duration_values, fiscal_year_labels,
)
from app.services.facts.concepts import (
    COMPANYFACTS_DURATION_TAGS, COMPANYFACTS_INSTANT_TAGS, NON_NEGATIVE_CONCEPTS,
    _FI_SKIPPED_CONCEPTS, _QUARTER_PERIODS, _VALID_FP, _unit_for,
)
from app.services.facts.currency import admitted_items, companyfacts_currencies
from app.services.facts.derive import derive_same_period_metrics
from app.services.facts.fiscal_naming import reported_fiscal_year, year_ending_on
from app.services.facts.quarterly import (
    QUARTER_WINDOW, derive_cumulative_quarters, derive_quarter_sum_fallback, reported_fact,
)
from app.services.facts.transport import logger


# --- Multi-Period Analysis (M1): SEC companyfacts as a first-class period source ---------------
#
# One companyfacts request (app.utils.sec_urls.companyfacts_url) returns a company's
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

def _collect_companyfacts_values(
    usgaap: dict, tags: tuple[str, ...], unit_key: str, *, instant: bool, foreign: frozenset = frozenset()
) -> dict[tuple[date, str], dict[str, Any]]:
    """Winning item per (period_end, klass) for one concept, across its candidate tags.

    klass is "FY"/"Q" for durations, "I" for instants. Within a tag the LATEST-`filed` item wins a
    period (restatement-aware; `filed` is ISO so lexical compare is safe, and a later list item wins
    ties — companyfacts lists in filing order). Across tags, the FIRST tag with data wins a period
    (priority order), so tag migrations merge into one continuous history without a stale tag
    shadowing a newer one. Each winner also carries the EARLIEST-filed item's `fp`/`fy` — the one
    case where those fields are trustworthy (the original filing that reported the period as its
    own current period), used only as the in-progress-year quarter fallback. An item of a ``foreign``
    accession, one whose own currency is not the series' (``filing_currencies``), is never read.
    """
    claimed: dict[tuple[date, str], dict[str, Any]] = {}
    for tag in tags:
        node = usgaap.get(tag)
        units = node.get("units") if isinstance(node, dict) else None
        items = units.get(unit_key) if isinstance(units, dict) else None
        if not isinstance(items, list):
            continue
        tag_best: dict[tuple[date, str], dict[str, Any]] = {}
        tag_candidates: dict[tuple[date, str], list[dict]] = {}
        for (end, klass), start, value, item in admitted_items(items, instant=instant):
            if item.get("accn") in foreign:
                continue  # its own filing reports in another currency: this is a convenience translation
            filed = str(item.get("filed") or "")
            record = {
                "value": float(value),
                "unit": unit_key,
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
            tag_candidates.setdefault(key, []).append(dict(record))
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
            record["candidates"] = tag_candidates[key]
            claimed.setdefault(key, record)
    return claimed


def normalize_companyfacts(
    company_id: int, companyfacts: Any, *, financial_sic: bool = False
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Classify a raw companyfacts payload into labelled fact dicts (pure; unit-testable).

    Returns ``(facts, meta)`` where meta carries ``unsupported_ifrs`` (an ifrs-full-only filer —
    out of v1 scope). Emits reported FY/quarter rows and compatible cumulative-flow
    calculations with operand provenance. EPS is reported-only. Cumulative slices feed
    calculations but are never stored as quarter facts. Direct rows are
    ``source="companyfacts", reconciled=True`` — this is
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

    duration_values, instant_values = _collect_companyfacts_concepts(usgaap, financial_sic)

    fy_windows = _fiscal_year_windows(duration_values)
    duration_values = fiscal_duration_values(duration_values, fy_windows, meta)
    fy_labels = fiscal_year_labels(duration_values, fy_windows)
    fy_ends = {end for _start, end in fy_windows}
    quarter_labels = _label_quarters(duration_values, fy_windows, fy_labels)

    def _base_fact(concept: str, record: dict[str, Any]) -> dict[str, Any]:
        return reported_fact(company_id, concept, record["unit"], record)

    facts: list[dict[str, Any]] = []
    _append_reported_companyfacts(
        facts, duration_values, instant_values, fy_labels, fy_ends, quarter_labels, _base_fact,
    )

    quarters, exclusions = derive_cumulative_quarters(company_id, facts, duration_values, quarter_labels)
    facts.extend(quarters)
    facts.extend(derive_quarter_sum_fallback(facts, duration_values))
    filled = {(f["concept"], f.get("fiscal_year"), f["fiscal_period"]) for f in facts}
    exclusions = [e for e in exclusions
                  if (e["concept"], e["fiscal_year"], e["fiscal_period"]) not in filled]
    # NON_NEGATIVE hard-reject BEFORE the same-period metrics derive: a rejected negative row
    # (e.g. a derived Q4 revenue gone negative under a recast/vintage mismatch) must not leave
    # behind margins computed from it — margins pass the filter themselves (legitimately
    # negative), so they must never be built on an input the filter is about to drop.
    def _hard_reject_ok(fact: dict[str, Any]) -> bool:
        value = fact.get("value")
        if fact["concept"] in NON_NEGATIVE_CONCEPTS and isinstance(value, (int, float)) and value < 0:
            if fact.get("source") == "derived" and fact.get("fiscal_period") in _QUARTER_PERIODS:
                exclusions.append({"concept": fact["concept"], "fiscal_year": fact["fiscal_year"],
                                   "fiscal_period": fact["fiscal_period"],
                                   "reason": "negative_calculated_value", "inputs": [fact_operand(fact)]})
            logger.warning(
                "companyfacts_reject concept=%s period=%s value=%s reason=negative",
                fact["concept"], fact["period_end"], value,
            )
            return False
        return True

    facts = [fact for fact in facts if _hard_reject_ok(fact)]
    facts.extend(fact for fact in derive_same_period_metrics(facts) if _hard_reject_ok(fact))
    meta.update(quarterly_exclusions=exclusions, quarterly_excluded_count=len(exclusions))

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


def _collect_companyfacts_concepts(usgaap: dict, financial_sic: bool) -> tuple[
    dict[str, dict[tuple[date, str], dict[str, Any]]], dict[str, dict[tuple[date, str], dict[str, Any]]],
]:
    """Collect each concept in the series currency from the filings in it; durations first, registry order."""
    currency, foreign = companyfacts_currencies(usgaap)  # the pick the sync's demotion reads too
    duration_values: dict[str, dict[tuple[date, str], dict[str, Any]]] = {}
    for concept, tags in COMPANYFACTS_DURATION_TAGS.items():
        if financial_sic and concept in _FI_SKIPPED_CONCEPTS:
            continue
        unit_key = _unit_for(concept, currency)  # the series currency, or its per-share unit
        values = _collect_companyfacts_values(usgaap, tags, unit_key, instant=False, foreign=foreign)
        if values:
            duration_values[concept] = values

    instant_values: dict[str, dict[tuple[date, str], dict[str, Any]]] = {}
    for concept, tags in COMPANYFACTS_INSTANT_TAGS.items():
        values = _collect_companyfacts_values(usgaap, tags, currency, instant=True, foreign=foreign)
        if values:
            instant_values[concept] = values
    return duration_values, instant_values


def _append_reported_companyfacts(
    facts: list[dict[str, Any]],
    duration_values: dict[str, dict[tuple[date, str], dict[str, Any]]],
    instant_values: dict[str, dict[tuple[date, str], dict[str, Any]]],
    fy_labels: dict[date, int], fy_ends: set[date], quarter_labels: dict[date, tuple[str, int]],
    _base_fact: Callable[[str, dict[str, Any]], dict[str, Any]],
) -> None:
    """Append labelled duration rows, then instant rows, using the caller's fact closure."""
    for concept, values in duration_values.items():
        for (end, klass), record in values.items():
            if klass == "FY":
                facts.append(
                    {**_base_fact(concept, record), "fiscal_year": fy_labels[end], "fiscal_period": "FY"}
                )
            elif klass == "Q":
                label = quarter_labels.get(end)
                if label is None:
                    continue  # unlabelable quarter — dropped rather than guessed
                fiscal_period, fiscal_year = label
                if fiscal_period != "Q4" and (end - record["period_start"]).days > QUARTER_WINDOW[1]:
                    continue  # Extended 16/17-week quarters require a fiscal year-end anchor.
                facts.append(
                    {
                        **_base_fact(concept, record),
                        "fiscal_year": fiscal_year,
                        "fiscal_period": fiscal_period,
                    }
                )
            # Cumulative YTD6/YTD9 slices are calculation inputs, never quarter rows.

    for concept, values in instant_values.items():
        for (end, _klass), record in values.items():
            # A fiscal-year-end balance sheet IS the Q4 instant: store it once, labelled FY —
            # quarterly readers select instants by period_end, never by label (D2c).
            if end in fy_ends:
                fiscal_period, fiscal_year = "FY", fy_labels[end]
            elif end in quarter_labels:
                fiscal_period, fiscal_year = quarter_labels[end]
            elif record.get("first_fp") == "FY":  # A year-end balance outside every window (an opening balance)
                fiscal_period = "FY"  # closes the year ending on its date, counted back from the next window.
                fiscal_year = year_ending_on(end, fy_labels) or reported_fiscal_year(record, end) or end.year
            elif record.get("first_fp") in _VALID_FP:
                fy = record.get("first_fy")
                fiscal_period = record["first_fp"]
                fiscal_year = fy if isinstance(fy, int) else end.year
            else:
                continue
            facts.append(
                {**_base_fact(concept, record), "fiscal_year": fiscal_year, "fiscal_period": fiscal_period}
            )
