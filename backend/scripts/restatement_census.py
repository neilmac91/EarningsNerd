#!/usr/bin/env python3
"""Census: how often a later SEC filing reports a different annual value than the year's own report.

WP5 §5(a), before the restatement note is built. The analysis shows each fiscal year's value from the
newest filing (``is_latest``), so a figure a later 10-K re-reports in its comparatives replaces what the
year's own annual report said (REGN revenue: FY2018 6,710.8M in its own 10-K, 5,145.6M in the FY2020
10-K). This measures how often that happens, and by how much, so the note's tolerance and rules rest on
data.

For each company it fetches the companyfacts payload ONLY through ``app.services.facts.transport`` (the
shared SEC rate limiter and backoff, the Settings SEC identity; CLAUDE.md rule 5), then runs the same
collection and fiscal-year windowing as ``normalize_companyfacts``. For every concept x fiscal year (FY
durations and FY-end instants, the newest ``--years`` fiscal years) it compares:

- the winner: the value ingest stores (the latest-filed item of the first tag with data);
- the own value: the item from the year's own annual report (an ``ANNUAL_FORMS`` filing whose own
  period end, per ``own_period_ends``, is this period; the earliest filed, preferring a non-amended
  form), looked up within the winning tag and, separately, across all of the concept's tags (the own
  filing's value under the highest-priority tag it used).

It prints a Markdown report to stdout: cells and companies where own differs from winner at several
relative tolerances, by concept; a histogram of small relative gaps; how often the own value sits under
another tag; and the largest gaps with both tags, accessions, filed dates and values, plus evidence for
reading their cause (whether either filing carries the other's value under another us-gaap tag, and a
split-like ratio for per-share values).

READ-ONLY: it writes nothing (no database, no files, no cache). Payloads stay in memory and are
dropped after each company. It stops early, and says so, if SEC answers 403 or 429 repeatedly.

Requirements: backend dependencies, outbound HTTPS to data.sec.gov, and a Settings that loads
(SECRET_KEY set; nothing is signed, so any throwaway value works locally). No database.

Usage (from backend/):
  SKIP_REDIS_INIT=true python scripts/restatement_census.py --sic-json PATH > census.md
  SKIP_REDIS_INIT=true python scripts/restatement_census.py --tickers REGN,AAPL --sic-json PATH

``--sic-json`` maps tickers to ``{"cik": ..., "sic": ...}``. The SIC decides ``financial_sic`` exactly as
ingest does (6000-6799 skips the generic revenue tags). A ticker absent from it is resolved through the
app's exact ticker resolution (``sec_edgar_service.resolve_ticker``); its SIC is then unknown and it is
read as non-financial, which the coverage table states.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import os
import sys
from collections import Counter, defaultdict
from datetime import date
from typing import Any, Optional

# Make the backend root importable as `app.*` when run directly (see sync_companyfacts.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger("restatement_census")

SAMPLE = (
    "REGN AAPL MSFT AMZN JPM BAC XOM CVX JNJ PFE LLY MRK ABBV KO PEP PG WMT COST HD NKE MCD DIS NFLX "
    "GOOGL META NVDA INTC AMD CSCO ORCL IBM CAT DE GE HON BA LMT UNH CVS T VZ UPS FDX NEE DUK SPG PLD GS "
    "MS AXP V MA TSLA F GM SBUX TGT LOW ADBE CRM"
).split()
TOLERANCES = (0.001, 0.005, 0.01, 0.02, 0.05)
# Histogram bin upper edges (relative gap); 0 is its own bin, the last bin is open.
HIST_EDGES = (1e-5, 1e-4, 5e-4, 1e-3, 2e-3, 5e-3, 1e-2, 2e-2, 5e-2)
EVIDENCE_FLOOR = 0.001  # cells above this relative gap carry cause evidence
MATCH_TOLERANCE = 5e-4  # "the same value" when reading another tag in a filing
PER_SHARE = frozenset({"earnings_per_share", "eps_diluted"})
# Lines named first when a later filing changed them; the rest are counted, not named.
HEADLINE_TAGS = (
    "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "CostOfRevenue",
    "OperatingIncomeLoss", "IncomeLossFromContinuingOperations", "NetIncomeLoss", "Assets", "Liabilities",
    "StockholdersEquity", "NetCashProvidedByUsedInOperatingActivities",
)
ISOLATED_MAX_OTHER_LINES = 2  # a change touching at most this many other currency lines is "isolated"
STOP_AFTER_BLOCKED = 2  # consecutive fetches refused with 403/429
STOP_AFTER_RATE_LIMIT_HITS = 3  # 429 backoffs across the run


class _SecFailureLog(logging.Handler):
    """Collects the transport's and the limiter's warnings, so a 403/429 can stop the run."""

    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def _blocked(messages: list[str]) -> bool:
    return any("403" in m or "429" in m or "rate limit" in m.lower() for m in messages)


def _rel_gap(winner: float, own: float) -> float:
    if own == 0:
        return 0.0 if winner == 0 else math.inf
    return abs(winner - own) / abs(own)


def _granularity(value: float, cap: float) -> float:
    """The coarsest power of ten ``value`` is a whole multiple of, at most ``cap`` (a round 5,000M is not
    evidence of billion rounding)."""
    scaled = round(abs(value) * 10_000)
    if scaled == 0:
        return 0.0
    exponent = 0
    while scaled % 10 == 0 and exponent < 20:
        scaled //= 10
        exponent += 1
    return min(10 ** exponent / 10_000, cap)


def _rounding_only(concept: str, winner: float, own: float) -> bool:
    """A gap no larger than half the coarser value's rounding unit: one figure is the other, rounded."""
    cap = 0.01 if concept in PER_SHARE else 1e6
    unit = max(_granularity(winner, cap), _granularity(own, cap))
    return 0 < abs(winner - own) <= unit / 2 * (1 + 1e-9)


def _item(candidate: dict[str, Any]) -> dict[str, Any]:
    start = candidate.get("period_start")
    return {
        "value": candidate["value"], "tag": candidate.get("raw_tag"), "accession": candidate.get("accession"),
        "form": candidate.get("form"), "filed": candidate.get("filed"),
        "start": start.isoformat() if isinstance(start, date) else None,
    }


def _own_key(candidate: dict[str, Any], start: Optional[date]) -> tuple:
    """Earliest filed, preferring a non-amended form; then a start matching the winner's."""
    return (str(candidate.get("form") or "").endswith("/A"), candidate.get("filed") or "",
            candidate.get("period_start") != start)


def _is_own(candidate: dict[str, Any], end: date, own_ends: dict[str, date]) -> bool:
    from app.services.facts.fiscal_naming import ANNUAL_FORMS

    accession = candidate.get("accession")
    return candidate.get("form") in ANNUAL_FORMS and bool(accession) and own_ends.get(accession) == end


def _own_within(record: dict[str, Any], end: date, own_ends: dict[str, date]) -> Optional[dict[str, Any]]:
    owns = [c for c in record.get("candidates") or [record] if _is_own(c, end, own_ends)]
    return min(owns, key=lambda c: _own_key(c, record.get("period_start")), default=None)


def _own_across(
    per_tag: dict[str, dict], tags: tuple[str, ...], key: tuple[date, str], start: Optional[date],
    own_ends: dict[str, date],
) -> Optional[dict[str, Any]]:
    """The earliest own report under any of the concept's tags, read by its highest-priority tag."""
    owns = []
    for priority, tag in enumerate(tags):
        record = per_tag[tag].get(key)
        for candidate in (record or {}).get("candidates") or ():
            if _is_own(candidate, key[0], own_ends):
                form_amended, filed, start_differs = _own_key(candidate, start)
                owns.append(((form_amended, filed, priority, start_differs), candidate))
    return min(owns, key=lambda pair: pair[0])[1] if owns else None


def _tag_collections(usgaap: dict, financial_sic: bool) -> dict[str, tuple[tuple[str, ...], str, dict, bool]]:
    """Per concept: its tags, its unit list (``series_unit``), the collector run on each tag alone, and
    whether it is an instant."""
    from app.services.facts.companyfacts import _collect_companyfacts_values
    from app.services.facts.concepts import (
        COMPANYFACTS_DURATION_TAGS, COMPANYFACTS_INSTANT_TAGS, _CONCEPT_UNITS, _FI_SKIPPED_CONCEPTS,
    )
    from app.services.facts.currency import series_unit

    out: dict[str, tuple[tuple[str, ...], str, dict, bool]] = {}
    for instant, registry in ((False, COMPANYFACTS_DURATION_TAGS), (True, COMPANYFACTS_INSTANT_TAGS)):
        for concept, tags in registry.items():
            if not instant and financial_sic and concept in _FI_SKIPPED_CONCEPTS:
                continue
            default = "USD" if instant else _CONCEPT_UNITS.get(concept, "USD")
            unit = series_unit(usgaap, tags, default, instant=instant)
            per_tag = {tag: _collect_companyfacts_values(usgaap, (tag,), unit, instant=instant) for tag in tags}
            out[concept] = (tags, unit, per_tag, instant)
    return out


def _accession_index(usgaap: dict, accessions: set[str]) -> dict[str, list[tuple]]:
    """Every us-gaap item the given filings carry: accession -> [(tag, unit, start, end, value)]."""
    index: dict[str, list[tuple]] = defaultdict(list)
    for tag, node in usgaap.items():
        units = node.get("units") if isinstance(node, dict) else None
        for unit, items in units.items() if isinstance(units, dict) else ():
            for item in items if isinstance(items, list) else ():
                if isinstance(item, dict) and item.get("accn") in accessions:
                    index[item["accn"]].append((tag, unit, item.get("start"), item.get("end"), item.get("val")))
    return index


def _tags_carrying(
    index: dict, accession: str, unit: str, starts: set[Optional[str]], end: str, value: float,
) -> list[str]:
    """Tags under which ``accession`` reports ``value`` for this period (an instant's start is None)."""
    found: set[str] = set()
    if value == 0:
        return []  # a zero matches too many unrelated lines to say anything
    for tag, item_unit, item_start, item_end, item_value in index.get(accession, ()):
        if (item_unit == unit and item_end == end and item_start in starts
                and isinstance(item_value, (int, float))
                and _rel_gap(float(item_value), value) <= MATCH_TOLERANCE):
            found.add(tag)
    return sorted(found)


def _statement_values(index: dict, accession: str, end: str) -> dict[tuple, set[float]]:
    """The filing's us-gaap items for this fiscal year: FY-length durations ending on ``end`` and instants at it."""
    out: dict[tuple, set[float]] = defaultdict(set)
    end_date = date.fromisoformat(end)
    for tag, unit, start, item_end, value in index.get(accession, ()):
        if item_end != end or not isinstance(value, (int, float)):
            continue
        if start is not None:
            try:
                days = (end_date - date.fromisoformat(start)).days
            except ValueError:
                continue
            if not 320 <= days <= 390:
                continue
        out[(tag, unit, start is None)].add(float(value))
    return out


def _statement_drift(index: dict, own: str, later: str, end: str) -> dict[str, Any]:
    """Which currency lines both filings report for this fiscal year changed, and net income.

    Per-share, share-count and ratio lines are left out, so a split does not read as a recast."""
    from app.services.facts.currency import is_amount_unit

    before, after = _statement_values(index, own, end), _statement_values(index, later, end)
    shared = {key for key in before.keys() & after.keys() if is_amount_unit(key[1])}
    changed = {key[0] for key in shared if not any(
        _rel_gap(b, a) <= MATCH_TOLERANCE for a in before[key] for b in after[key])}
    net = [key for key in shared if key[0] == "NetIncomeLoss" and not key[2]]
    return {
        "shared": len(shared), "changed": sorted(changed),
        "net_income": "absent" if not net else ("changed" if "NetIncomeLoss" in changed else "unchanged"),
        "headline": [tag for tag in HEADLINE_TAGS if tag in changed],
        "discontinued": sorted(tag for tag in changed if "DiscontinuedOperation" in tag),
    }


def _split_ratio(concept: str, winner: float, own: float) -> Optional[int]:
    if concept not in PER_SHARE or not winner or not own or (winner > 0) != (own > 0):
        return None
    ratio = max(abs(own / winner), abs(winner / own))
    n = round(ratio)
    return n if n >= 2 and abs(ratio - n) / n < 0.02 else None


def measure_company(
    ticker: str, payload: dict, financial_sic: bool, years: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The census cells for one company, grouped exactly as ``normalize_companyfacts`` groups them."""
    from app.services.facts.calendar import (
        _fiscal_year_windows, _label_quarters, fiscal_duration_values, fiscal_year_labels,
    )
    from app.services.facts.companyfacts import _append_reported_companyfacts, _collect_companyfacts_concepts
    from app.services.facts.concepts import NON_NEGATIVE_CONCEPTS
    from app.services.facts.fiscal_naming import ANNUAL_FORMS, own_period_ends

    info: dict[str, Any] = {"entity": payload.get("entityName"), "note": ""}
    usgaap = (payload.get("facts") or {}).get("us-gaap")
    if not isinstance(usgaap, dict) or not usgaap:
        info["note"] = "no us-gaap facts (IFRS or empty): skipped"
        return [], info

    # normalize_companyfacts, step for step, up to the reported rows.
    duration_values, instant_values = _collect_companyfacts_concepts(usgaap, financial_sic)
    fy_windows = _fiscal_year_windows(duration_values)
    duration_values = fiscal_duration_values(duration_values, fy_windows, {})
    fy_labels = fiscal_year_labels(duration_values, fy_windows)
    fy_ends = {end for _start, end in fy_windows}
    quarter_labels = _label_quarters(duration_values, fy_windows, fy_labels)
    rows: list[dict[str, Any]] = []
    _append_reported_companyfacts(
        rows, duration_values, instant_values, fy_labels, fy_ends, quarter_labels,
        lambda concept, record: {"concept": concept, "record": record},
    )
    own_ends = own_period_ends(duration_values)

    # The same windows over every tag on its own, for the across-tag lookup.
    collections = _tag_collections(usgaap, financial_sic)
    flat = {f"{concept}|{tag}": per_tag[tag] for concept, (tags, _unit, per_tag, instant) in collections.items()
            if not instant for tag in tags}
    all_ends = own_period_ends(fiscal_duration_values(flat, fy_windows, {}))
    info["own_end_disagreements"] = sum(1 for acc, end in own_ends.items() if all_ends.get(acc) != end)
    report_year = {acc: fy_labels.get(end) for acc, end in all_ends.items()}

    newest = set(sorted(set(fy_labels.values()))[-years:])
    info["years"] = (min(newest), max(newest)) if newest else None
    cells: list[dict[str, Any]] = []
    for row in rows:
        if row["fiscal_period"] != "FY" or row["fiscal_year"] not in newest:
            continue
        concept, record = row["concept"], row["record"]
        if concept in NON_NEGATIVE_CONCEPTS and record["value"] < 0:
            continue  # ingest's hard reject drops it
        end = record["period_end"]
        instant = concept not in duration_values
        key = (end, "I" if instant else "FY")
        tags, unit, per_tag, _instant = collections[concept]
        within = _own_within(record, end, own_ends)
        across = _own_across(per_tag, tags, key, record.get("period_start"), all_ends)
        winner = _item(record)
        cell = {
            "ticker": ticker, "concept": concept, "fy": row["fiscal_year"], "end": end.isoformat(),
            "unit": unit, "instant": instant, "winner": winner, "concept_tags": tags,
            "winner_report_fy": report_year.get(winner["accession"]),
            "within": _item(within) if within else None, "across": _item(across) if across else None,
        }
        for which in ("within", "across"):
            own = cell[which]
            cell[f"{which}_later"] = bool(own) and own["accession"] != winner["accession"]
            cell[f"{which}_gap"] = _rel_gap(winner["value"], own["value"]) if cell[f"{which}_later"] else 0.0
            cell[f"{which}_rounding"] = bool(own) and _rounding_only(concept, winner["value"], own["value"])
        if max(cell["within_gap"], cell["across_gap"]) > EVIDENCE_FLOOR:
            timeline = set()
            for tag in tags:
                for c in (per_tag[tag].get(key) or {}).get("candidates") or ():
                    if c.get("form") in ANNUAL_FORMS or not str(c.get("form") or "").startswith("10-Q") \
                            or c.get("accession") == winner["accession"]:
                        timeline.add((c.get("filed"), c.get("form"), c.get("accession"), tag, c["value"]))
            cell["timeline"] = sorted(timeline)
        cells.append(cell)

    gap_cells = [c for c in cells if c.get("timeline")]
    index = _accession_index(usgaap, {(c[which] or {}).get("accession") for c in gap_cells
                                      for which in ("winner", "within", "across")} - {None})
    for cell in gap_cells:
        own = cell["across"] or cell["within"]
        winner = cell["winner"]
        starts = {None} if cell["instant"] else {winner["start"], own["start"]}
        cell["later_carries_own"] = _tags_carrying(index, winner["accession"], cell["unit"], starts,
                                                   cell["end"], own["value"])
        cell["own_carries_later"] = _tags_carrying(index, own["accession"], cell["unit"], starts,
                                                   cell["end"], winner["value"])
        cell["split"] = _split_ratio(cell["concept"], winner["value"], own["value"])
        cell["drift"] = _statement_drift(index, own["accession"], winner["accession"], cell["end"])
        if own["tag"] != winner["tag"]:
            values = sorted({v for t, u, st, en, v in index.get(winner["accession"], ())
                             if f"us-gaap:{t}" == own["tag"] and u == cell["unit"] and en == cell["end"]
                             and st in starts and isinstance(v, (int, float))})
            cell["later_under_own_tag"] = ", ".join(_fmt(float(v), cell["unit"]) for v in values)
    info["cells"] = len(cells)
    return cells, info


# --- report -----------------------------------------------------------------------------------------

def _fmt(value: float, unit: str) -> str:
    if unit.endswith("/shares"):
        return f"{value:,.2f} {unit}"
    if abs(value) >= 1e6:
        return f"{value / 1e6:,.1f}M {unit}"
    return f"{value:,.0f} {unit}"


def _pct(gap: float) -> str:
    return "own=0" if math.isinf(gap) else f"{gap * 100:.2f}%"


def _short(tag: Optional[str]) -> str:
    return (tag or "").removeprefix("us-gaap:")


def _hint(cell: dict[str, Any]) -> str:
    """Mechanical evidence only; the cause is the reader's call."""
    parts = []
    own, winner = cell["across"], cell["winner"]
    if own["tag"] != winner["tag"]:
        parts.append(f"tag changed {_short(own['tag'])} -> {_short(winner['tag'])}")
    if cell.get("split"):
        parts.append(f"split-like ratio x{cell['split']}")
    if (own["value"] > 0) != (winner["value"] > 0):
        parts.append("sign differs")
    later = [t for t in cell.get("later_carries_own") or () if f"us-gaap:{t}" != winner["tag"]]
    if later:
        parts.append("the own value also appears in the later filing as " + ", ".join(later)
                     + ("" if set(later) & set(cell["concept_tags"]) else " (not a tag of this concept: "
                        "may be coincidence)"))
    earlier = [t for t in cell.get("own_carries_later") or () if f"us-gaap:{t}" != own["tag"]]
    if earlier:
        parts.append("the later value also appears in the own filing as " + ", ".join(earlier)
                     + ("" if set(earlier) & set(cell["concept_tags"]) else " (not a tag of this concept: "
                        "may be coincidence)"))
    if not later and not earlier and not cell.get("split"):
        parts.append("no us-gaap tag in either filing carries the other's value")
    if cell["winner_report_fy"] == cell["fy"]:
        parts.append("shown value is the own year's amended report")
    drift = cell.get("drift")
    if drift:
        parts.append(f"{len(drift['changed'])}/{drift['shared']} shared same-year currency lines changed, "
                     f"net income {drift['net_income']}")
        if drift["headline"]:
            parts.append("headline lines changed: " + ", ".join(drift["headline"]))
        if drift["discontinued"]:
            parts.append(f"{len(drift['discontinued'])} discontinued-operations lines changed")
    parts.append("bucket: " + _bucket(cell))
    return "; ".join(parts)


BUCKETS = (
    "shown value from a proxy statement", "scale factor of 1000^n", "exact sign flip", "per-share split", "own year's amended report", "same figure re-tagged in the later filing",
    "own value under another tag of the concept", "isolated line change", "discontinued-operations recast",
    "broad recast, net income changed", "broad recast, net income unchanged", "no same-year lines to compare",
)


def _bucket(cell: dict[str, Any]) -> str:
    """A mechanical first reading of a gap's cause, from the evidence alone (first match wins)."""
    own, winner, drift = cell["across"], cell["winner"], cell.get("drift")
    ratio = abs(winner["value"] / own["value"]) if own["value"] and winner["value"] else None
    if _proxy(winner["form"]):
        return BUCKETS[0]
    if ratio and any(math.isclose(ratio, factor, rel_tol=1e-3) for factor in (1e3, 1e6, 1e-3, 1e-6)):
        return BUCKETS[1]
    if own["value"] and math.isclose(winner["value"], -own["value"], rel_tol=1e-9):
        return BUCKETS[2]
    if cell.get("split"):
        return BUCKETS[3]
    if cell["winner_report_fy"] == cell["fy"]:
        return BUCKETS[4]
    if any(f"us-gaap:{t}" != winner["tag"] for t in cell.get("later_carries_own") or ()
           if t in cell["concept_tags"]):
        return BUCKETS[5]
    if own["tag"] != winner["tag"]:
        return BUCKETS[6]
    if not drift or not drift["shared"]:
        return BUCKETS[11]
    others = set(drift["changed"]) - {_short(own["tag"]), _short(winner["tag"])}
    if len(others) <= ISOLATED_MAX_OTHER_LINES:
        return BUCKETS[7]
    if drift["discontinued"]:
        return BUCKETS[8]
    return BUCKETS[9] if drift["net_income"] == "changed" else BUCKETS[10]


def _proxy(form: Optional[str]) -> bool:
    """A proxy statement (pay-versus-performance tables tag net income, often without scale)."""
    return str(form or "").upper().replace(" ", "").startswith(("DEF14", "DEFA14", "PRE14", "DEFM14", "PREM14"))


def _size_table(cells: list[dict[str, Any]], which: str) -> list[str]:
    concepts = sorted({c["concept"] for c in cells})
    head = "| concept | measured | own found | later filing | " + " | ".join(
        f"> {t * 100:g}%" for t in TOLERANCES) + " |"
    lines = [head, "|" + "---|" * (4 + len(TOLERANCES))]
    for concept in [*concepts, None]:
        group = [c for c in cells if concept is None or c["concept"] == concept]
        found = [c for c in group if c[which]]
        later = [c for c in found if c[f"{which}_later"]]
        cols = []
        for tol in TOLERANCES:
            hits = [c for c in later if c[f"{which}_gap"] > tol]
            cols.append(f"{len(hits)} ({len({c['ticker'] for c in hits})})")
        name = f"**all ({len({c['ticker'] for c in group})} cos)**" if concept is None else concept
        lines.append(f"| {name} | {len(group)} | {len(found)} | {len(later)} | " + " | ".join(cols) + " |")
    return lines


def _histogram(cells: list[dict[str, Any]], which: str) -> list[str]:
    later = [(c[f"{which}_gap"], c[f"{which}_rounding"], c["concept"] in PER_SHARE)
             for c in cells if c[f"{which}_later"]]
    bins: Counter = Counter()
    rounding: Counter = Counter()
    per_share: Counter = Counter()
    for gap, rounded, share in later:
        if gap == 0:
            label = "0 (identical)"
        else:
            low = 0.0
            for edge in HIST_EDGES:
                if gap <= edge:
                    label = f"({low * 100:g}%, {edge * 100:g}%]"
                    break
                low = edge
            else:
                label = f"> {HIST_EDGES[-1] * 100:g}%"
        bins[label] += 1
        rounding[label] += rounded
        per_share[label] += share
    labels = ["0 (identical)"]
    low = 0.0
    for edge in HIST_EDGES:
        labels.append(f"({low * 100:g}%, {edge * 100:g}%]")
        low = edge
    labels.append(f"> {HIST_EDGES[-1] * 100:g}%")
    lines = ["| relative gap | cells | share | cumulative | rounding only | per-share |", "|---|---|---|---|---|---|"]
    running = 0
    for label in labels:
        running += bins[label]
        share = bins[label] / len(later) if later else 0
        cum = running / len(later) if later else 0
        lines.append(f"| {label} | {bins[label]} | {share:.1%} | {cum:.1%} | {rounding[label]} | "
                     f"{per_share[label]} |")
    return lines


def _case_lines(rank: int, cell: dict[str, Any]) -> list[str]:
    own, winner, unit = cell["across"], cell["winner"], cell["unit"]
    lines = [
        f"{rank}. **{cell['ticker']} {cell['concept']} FY{cell['fy']}** (period end {cell['end']}), "
        f"gap {_pct(cell['across_gap'])}",
        f"   - own: {_fmt(own['value'], unit)}, {_short(own['tag'])}, {own['form']} {own['accession']} "
        f"filed {own['filed']}",
        f"   - shown: {_fmt(winner['value'], unit)}, {_short(winner['tag'])}, {winner['form']} "
        f"{winner['accession']} filed {winner['filed']}"
        + (f" (FY{cell['winner_report_fy']} report)" if cell["winner_report_fy"] else ""),
        f"   - evidence: {_hint(cell)}",
        "   - changed same-year currency lines: " + (", ".join(cell["drift"]["changed"][:15]) + (
            f" +{len(cell['drift']['changed']) - 15} more" if len(cell["drift"]["changed"]) > 15 else "")
            if cell.get("drift") else "n/a"),
        "   - filings (10-Qs left out): " + "; ".join(
            f"{filed} {form} {_short(tag)} {_fmt(value, unit)}" for filed, form, _acc, tag, value
            in cell.get("timeline") or ()),
    ]
    return lines


def _ranked(cells: list[dict[str, Any]], per_share: bool, per_company: Optional[int]) -> list[dict[str, Any]]:
    pool = [c for c in cells if c["across_later"] and c["across_gap"] > 0
            and (per_share or c["concept"] not in PER_SHARE)]
    ranked = sorted(pool, key=lambda c: (c["across_gap"], abs(c["winner"]["value"] - c["across"]["value"])),
                    reverse=True)
    if per_company is None:
        return ranked
    taken: Counter = Counter()
    capped = []
    for cell in ranked:
        if taken[cell["ticker"]] < per_company:
            taken[cell["ticker"]] += 1
            capped.append(cell)
    return capped


def _bucket_table(cells: list[dict[str, Any]]) -> list[str]:
    lines = ["| bucket | " + " | ".join(f"> {t * 100:g}% cells (cos)" for t in TOLERANCES[1:]) + " |",
             "|---|" + "---|" * len(TOLERANCES[1:])]
    for bucket in BUCKETS:
        cols = []
        for tol in TOLERANCES[1:]:
            hits = [c for c in cells if c["across_later"] and c["across_gap"] > tol and _bucket(c) == bucket]
            cols.append(f"{len(hits)} ({len({c['ticker'] for c in hits})})")
        lines.append(f"| {bucket} | " + " | ".join(cols) + " |")
    return lines


def render(cells: list[dict[str, Any]], coverage: list[dict[str, Any]], args: argparse.Namespace,
           stopped: Optional[str], started: str) -> str:
    out: list[str] = ["# Restatement census (WP5 §5a)", ""]
    measured = [row for row in coverage if row.get("cells")]
    out.append(f"Run {started}. Companyfacts through `app.services.facts.transport` (shared limiter, "
               f"Settings SEC identity). {len(coverage)} tickers requested, {len(measured)} measured, "
               f"{len(cells)} cells (company x concept x fiscal year, newest {args.years} fiscal years, "
               "FY durations and FY-end instants).")
    if stopped:
        out += ["", f"**STOPPED EARLY: {stopped}**"]
    out += ["", "Definitions: *winner* = the value ingest stores (latest-filed item of the first tag with "
            "data). *own* = the item from the year's own annual report (ANNUAL_FORMS, `own_period_ends` == "
            "this period end; earliest filed, non-amended first). *within* = own looked up in the winning "
            "tag only; *across* = own looked up in all the concept's tags (the own filing's value under its "
            "highest-priority tag). *later filing* = own found and its accession differs from the winner's. "
            "Gap = |winner - own| / |own|.", ""]

    out += ["## Coverage", "", "| ticker | CIK | entity | financial SIC | fiscal years | cells | note |",
            "|---|---|---|---|---|---|---|"]
    for row in coverage:
        years = row.get("years")
        out.append(f"| {row['ticker']} | {row.get('cik') or ''} | {row.get('entity') or ''} | "
                   f"{row.get('financial')} | {f'{years[0]}-{years[1]}' if years else ''} | "
                   f"{row.get('cells', 0)} | {row.get('note', '')} |")

    forms_all = Counter(c["winner"]["form"] for c in cells)
    forms_gap = Counter(c["winner"]["form"] for c in cells if c["across_later"] and c["across_gap"] > 0.01)
    out += ["", "## Forms the shown value comes from", "", "| form | cells | cells with a gap > 1% |", "|---|---|---|"]
    for form, count in forms_all.most_common():
        out.append(f"| {form} | {count} | {forms_gap[form]} |")
    proxies = sorted((c for c in cells if _proxy(c["winner"]["form"])), key=lambda c: (c["ticker"], c["fy"]))
    out += ["", f"Cells whose shown value comes from a proxy statement ({len(proxies)}):", ""]
    for c in proxies:
        own = c["across"] or c["within"]
        out.append(f"- {c['ticker']} {c['concept']} FY{c['fy']}: shown {_fmt(c['winner']['value'], c['unit'])} "
                   f"({c['winner']['form']} {c['winner']['accession']} filed {c['winner']['filed']}); own "
                   + (f"{_fmt(own['value'], c['unit'])} ({own['form']} {own['accession']})" if own else "not found"))

    for which, title in (("across", "own looked up across all the concept's tags"),
                         ("within", "own looked up within the winning tag only")):
        out += ["", f"## Size: own differs from winner ({title})", "",
                "Each tolerance column: cells (companies) whose gap exceeds it.", ""]
        out += _size_table(cells, which)

    for which in ("across", "within"):
        out += ["", f"## Rounding noise: relative-gap histogram ({which}, later-filing cells only)", ""]
        out += _histogram(cells, which)

    later = [c for c in cells if c["across_later"]]
    retagged = [c for c in later if c["across"]["tag"] != c["winner"]["tag"]]
    no_within = [c for c in later if not c["within"]]
    both = [c for c in later if c["within"]]
    disagree = [c for c in both if c["within"]["accession"] != c["across"]["accession"]
                or _rel_gap(c["within"]["value"], c["across"]["value"]) > 0]
    out += ["", "## Tag changes", "",
            f"- later-filing cells (across): {len(later)}",
            f"- own value under a different tag than the winner's: {len(retagged)} "
            f"({len(retagged) / len(later):.1%})" if later else "- no later-filing cells",
            f"- own report absent from the winning tag (only an across-tag lookup finds it): {len(no_within)}",
            f"- own found in both lookups but they disagree (another accession or value): {len(disagree)}",
            f"- accessions whose own period end differs between the winning-tag and all-tag maps: "
            f"{sum(row.get('own_end_disagreements', 0) for row in coverage)}", "",
            "| tolerance | cells > tol (across) | of which own under another tag | within-tag lookup misses "
            "(no own in winning tag) | within-tag lookup finds the gap |", "|---|---|---|---|---|"]
    for tol in TOLERANCES:
        hits = [c for c in later if c["across_gap"] > tol]
        other = [c for c in hits if c["across"]["tag"] != c["winner"]["tag"]]
        missed = [c for c in hits if not c["within"]]
        found = [c for c in hits if c["within_later"] and c["within_gap"] > tol]
        out.append(f"| {tol * 100:g}% | {len(hits)} | {len(other)} | {len(missed)} | {len(found)} |")
    out += ["", "Within-tag gaps the across-tag lookup does not report (own filing used a higher-priority tag "
            "for another line, or another accession was picked):", ""]
    only_within = [c for c in cells if c["within_later"] and c["within_gap"] > 0.01
                   and not (c["across_later"] and c["across_gap"] > 0.01)]
    out.append(f"- {len(only_within)} cells > 1% within but not across: " + ", ".join(
        f"{c['ticker']} {c['concept']} FY{c['fy']}" for c in only_within[:20]))

    out += ["", "## Cause evidence, mechanically bucketed (across-tag own; first match wins)", "",
            "A first reading from the evidence alone, not a verdict: *proxy statement* = the shown value is "
            "from a DEF 14A (pay-versus-performance) filed after the reports; *scale factor* = one value is the "
            "other times 1,000 or 1,000,000 (an XBRL scale error on one side); *exact sign flip* = one value is "
            "the other negated (an XBRL sign error on one side); *per-share split* = a per-share value "
            "off by a whole-number ratio; *re-tagged* = the later filing still reports the own value under "
            "another of the concept's tags; *isolated* = at most "
            f"{ISOLATED_MAX_OTHER_LINES} other same-year currency lines the two filings share changed; "
            "*discontinued-operations recast* = changed lines include discontinued-operations tags; *broad "
            "recast* = more lines changed, split by whether net income moved (a restatement or a "
            "retrospective accounting change moves it; a reclassification does not).", ""]
    out += _bucket_table(cells)
    out += ["", "Net income for the same fiscal year in the two filings (gap cells, per-share splits left out):", "",
            "| tolerance | net income unchanged | net income changed | not comparable |", "|---|---|---|---|"]
    for tol in TOLERANCES[1:]:
        status = Counter((c.get("drift") or {}).get("net_income", "absent") for c in cells
                         if c["across_later"] and c["across_gap"] > tol and not c.get("split"))
        out.append(f"| > {tol * 100:g}% | {status['unchanged']} | {status['changed']} | {status['absent']} |")

    other_tag = sorted((c for c in cells if c["across_later"] and c["across_gap"] > 0.01
                        and c["across"]["tag"] != c["winner"]["tag"]),
                       key=lambda c: (c["ticker"], c["concept"], c["fy"]))
    out += ["", f"## Gaps over 1% whose own value sits under another tag ({len(other_tag)})", "",
            "| ticker | concept | FY | gap | own value (tag) | shown value (tag) | the later filing's value under "
            "the own tag |", "|---|---|---|---|---|---|---|"]
    for c in other_tag:
        out.append(f"| {c['ticker']} | {c['concept']} | {c['fy']} | {_pct(c['across_gap'])} | "
                   f"{_fmt(c['across']['value'], c['unit'])} ({_short(c['across']['tag'])}) | "
                   f"{_fmt(c['winner']['value'], c['unit'])} ({_short(c['winner']['tag'])}) | "
                   f"{c.get('later_under_own_tag') or 'not reported'} |")

    for title, per_share, cap in (("all concepts", True, None),
                                  ("amounts only, per-share excluded, at most two per company", False, 2)):
        ranked = _ranked(cells, per_share, cap)[:args.top]
        out += ["", f"## The {args.top} largest relative gaps ({title}, across-tag own)", "",
                "| # | ticker | concept | FY | gap | own value | own tag | own accession (filed) | shown value | "
                "shown tag | shown accession (filed) | evidence |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for rank, cell in enumerate(ranked, 1):
            own, winner, unit = cell["across"], cell["winner"], cell["unit"]
            out.append(
                f"| {rank} | {cell['ticker']} | {cell['concept']} | {cell['fy']} | {_pct(cell['across_gap'])} | "
                f"{_fmt(own['value'], unit)} | {_short(own['tag'])} | {own['form']} {own['accession']} "
                f"({own['filed']}) | {_fmt(winner['value'], unit)} | {_short(winner['tag'])} | {winner['form']} "
                f"{winner['accession']} ({winner['filed']}) | {_hint(cell)} |")
        out += ["", "Detail:", ""]
        for rank, cell in enumerate(ranked, 1):
            out += _case_lines(rank, cell)

    out += ["", "## Companies with the most cells over 1% (across)", "", "| ticker | cells > 1% | concepts |",
            "|---|---|---|"]
    by_company: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cell in later:
        if cell["across_gap"] > 0.01:
            by_company[cell["ticker"]].append(cell)
    for ticker, group in sorted(by_company.items(), key=lambda kv: -len(kv[1])):
        counts = Counter(c["concept"] for c in group)
        out.append(f"| {ticker} | {len(group)} | " + ", ".join(f"{k} {v}" for k, v in counts.most_common()) + " |")

    out += ["", "## Worked case: REGN revenue", ""]
    for cell in cells:
        if cell["ticker"] == "REGN" and cell["concept"] == "revenue" and cell["across_later"]:
            out += _case_lines(0, cell) if cell.get("timeline") else [
                f"- REGN revenue FY{cell['fy']}: own = shown ({_fmt(cell['winner']['value'], cell['unit'])})"]
    return "\n".join(out) + "\n"


# --- run --------------------------------------------------------------------------------------------

async def _run(args: argparse.Namespace, sic_map: dict[str, dict]) -> tuple[list, list, Optional[str]]:
    from app.services.edgar.compat import sec_edgar_service
    from app.services.facts.concepts import _is_financial_sic
    from app.services.facts.transport import _fetch_companyfacts_async

    failures = _SecFailureLog()
    for name in ("app.services.facts_service", "app.services.sec_rate_limiter", "app.services.edgar.compat"):
        logging.getLogger(name).addHandler(failures)

    cells: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    blocked_in_a_row = 0
    for ticker in args.tickers:
        row: dict[str, Any] = {"ticker": ticker}
        coverage.append(row)
        entry = sic_map.get(ticker) or {}
        cik, sic = entry.get("cik"), entry.get("sic")
        if not cik:
            resolved = await sec_edgar_service.resolve_ticker(ticker)
            cik = (resolved or {}).get("cik")
            row["note"] = "CIK via resolve_ticker; SIC unknown, read as non-financial. "
        if not cik:
            row["note"] = row.get("note", "") + "unresolved: skipped"
            continue
        row["cik"], row["financial"] = cik, _is_financial_sic(sic)
        seen = len(failures.messages)
        payload = await _fetch_companyfacts_async(str(cik))
        fresh = failures.messages[seen:]
        rate_hits = sum("rate limit hit" in m.lower() for m in failures.messages)
        if payload is None:
            row["note"] = row.get("note", "") + "fetch failed: " + "; ".join(fresh)[:160]
            blocked_in_a_row = blocked_in_a_row + 1 if _blocked(fresh) else 0
            if blocked_in_a_row >= STOP_AFTER_BLOCKED:
                return cells, coverage, f"SEC refused {blocked_in_a_row} fetches in a row (403/429) at {ticker}"
            continue
        blocked_in_a_row = 0
        company_cells, info = measure_company(ticker, payload, row["financial"], args.years)
        del payload
        row.update(entity=info["entity"], years=info.get("years"), cells=info.get("cells", 0),
                   own_end_disagreements=info.get("own_end_disagreements", 0))
        row["note"] = row.get("note", "") + info["note"]
        cells.extend(company_cells)
        logger.info("%s: %d cells, %d later-filing gaps > 1%%", ticker, len(company_cells),
                    sum(1 for c in company_cells if c["across_later"] and c["across_gap"] > 0.01))
        if rate_hits >= STOP_AFTER_RATE_LIMIT_HITS:
            return cells, coverage, f"SEC answered 429 {rate_hits} times (stopped after {ticker})"
    return cells, coverage, None


def main() -> None:
    os.environ.setdefault("SKIP_REDIS_INIT", "true")
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tickers", type=lambda s: [t.strip().upper() for t in s.split(",") if t.strip()],
                        default=list(SAMPLE), help="Comma-separated tickers (default: the 60-company sample).")
    parser.add_argument("--sic-json", default=None, help='JSON {ticker: {"cik": ..., "sic": ...}} (read only).')
    parser.add_argument("--years", type=int, default=10, help="Newest fiscal years per company (default 10).")
    parser.add_argument("--top", type=int, default=25, help="Largest cases to list (default 25).")
    args = parser.parse_args()
    sic_map: dict[str, dict] = {}
    if args.sic_json:
        with open(args.sic_json, encoding="utf-8") as handle:
            sic_map = {str(k).upper(): v for k, v in json.load(handle).items()}

    from app.utils.datetimes import iso_z, utcnow

    started = iso_z(utcnow())
    cells, coverage, stopped = asyncio.run(_run(args, sic_map))
    sys.stdout.write(render(cells, coverage, args, stopped, started))


if __name__ == "__main__":
    main()
