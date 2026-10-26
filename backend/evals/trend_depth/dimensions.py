"""Revenue and segment-profit disaggregation from 10-K XBRL instances (dimensioned facts).

companyfacts carries only undimensioned facts, so segment and product revenue live only in each filing's
own instance (``sec_inputs.dimensional_facts``). A 10-K tags three years of its disaggregation tables, so
the latest 10-K plus every third one back covers a ten-year window. Where two filings report the same
member and year, the LATER filing's value is used (the basis the current segment structure is reported
on) and the first-reported value is kept beside it.

A member is the full set of (axis, member) pairs on the fact: Regeneron tags EYLEA as product x US
geography and its Dupixent profit share as product x collaboration agreement x income-statement location,
so single-axis reading alone would miss both. Rules:

- ``ConsolidationItemsAxis`` is dropped when its member is the operating-segments member; facts on an
  elimination, reconciling or corporate member are skipped.
- ``IncomeStatementLocationAxis`` keeps a fact only when it lands in a revenue line (collaboration tables
  also tag amounts recognised in R&D or SG&A under revenue concepts).
- Within a group of members sharing the same axes, a member whose value equals the sum of two or three
  others in the same year is a subtotal: kept for display, excluded from coverage sums.
"""
from __future__ import annotations

import re
from datetime import date
from itertools import combinations
from typing import Any

REVENUE_CONCEPTS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "SalesRevenueGoodsNet",
    "RevenueFromCollaborativeArrangementExcludingRevenueFromContractWithCustomer",
)
PROFIT_CONCEPTS = ("OperatingIncomeLoss", "SegmentReportingInformationProfitLoss")
BANK_CONCEPTS = ("InterestIncomeExpenseNet", "NoninterestIncome", "NetIncomeLoss", "NoninterestExpense")

SEGMENT_AXIS = "us-gaap_StatementBusinessSegmentsAxis"
PRODUCT_AXIS = "srt_ProductOrServiceAxis"
GEO_AXIS = "srt_StatementGeographicalAxis"
_CONSOLIDATION_AXIS = "srt_ConsolidationItemsAxis"
_PARENT_ONLY_AXIS = "srt_CondensedFinancialStatementsCaptionsAxis"
_LOCATION_AXIS = "us-gaap_IncomeStatementLocationAxis"
_SKIP_MEMBER_WORDS = ("elimination", "intersegment", "reconcil", "corporate", "unallocated", "consolidat")
_GENERIC_MEMBERS = re.compile(
    r"^[\w-]+:(Product|Service|ProductAndService\w*|ProductAndServiceOther|Other\w*|Royalty|"
    r"Collaboration\w*|License\w*|Technology\w*)Member$",
    re.IGNORECASE,
)


def _annual(start: str, end: str) -> bool:
    days = (date.fromisoformat(end) - date.fromisoformat(start)).days
    return 320 <= days <= 390


def pretty_member(qname: str) -> str:
    local = qname.split(":")[-1]
    for suffix in ("SegmentMember", "Member"):
        if local.endswith(suffix):
            local = local[: -len(suffix)]
            break
    if qname.startswith("country:"):
        return local
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", local)
    return {"Non Us": "Non-US", "Us": "US"}.get(spaced, spaced)


def _normalise_dims(dims: dict[str, str]) -> dict[str, str] | None:
    dims = dict(dims)
    consolidation = dims.pop(_CONSOLIDATION_AXIS, None)
    if consolidation is not None and "operatingsegments" not in consolidation.lower():
        return None
    if any("parentcompany" in member.lower().replace(" ", "") for member in dims.values()) or _PARENT_ONLY_AXIS in dims:
        return None  # parent-only statements are not a slice of consolidated revenue
    location = dims.pop(_LOCATION_AXIS, None)
    if location is not None and "revenue" not in location.lower():
        return None
    if any(any(word in member.lower() for word in _SKIP_MEMBER_WORDS) for member in dims.values()):
        return None
    return dims or None


def _kind(axes: tuple[str, ...]) -> str:
    if SEGMENT_AXIS in axes:
        return "segment"
    if PRODUCT_AXIS in axes:
        return "product"
    if GEO_AXIS in axes:
        return "geography"
    return "other"


def _label(row: dict[str, Any], dims: dict[str, str]) -> str:
    base = row.get("member_label") if isinstance(row.get("member_label"), str) else ""
    base = (base or "").strip()
    squashed = re.sub(r"[^a-z0-9]", "", base.lower())
    extras = []
    for member in dims.values():
        name = pretty_member(member)
        if re.sub(r"[^a-z0-9]", "", name.lower()) not in squashed:
            extras.append(name)
    if not base:
        return " — ".join(extras)
    return base + (f" — {', '.join(extras)}" if extras else "")


def disaggregation(filings: list[tuple[dict[str, Any], list[dict[str, Any]]]]) -> list[dict[str, Any]]:
    """Member series: [{axes, kind, measure, member_key, label, generic, points{end: ...}, subtotal}].

    ``filings`` is [(filing_meta, dimensional_rows)] in any order; filing_meta needs accession, filed.
    """
    cells: dict[tuple[str, tuple[tuple[str, str], ...]], dict[str, Any]] = {}
    for meta, rows in sorted(filings, key=lambda pair: pair[0]["filed"]):
        for row in rows:
            concept = row["concept"]
            if not _annual(row["start"], row["end"]):
                continue
            dims = _normalise_dims(row["dims"])
            if dims is None:
                continue
            axes = tuple(sorted(dims))
            if concept in REVENUE_CONCEPTS:
                measure = "revenue"
            elif concept in PROFIT_CONCEPTS + BANK_CONCEPTS and axes == (SEGMENT_AXIS,):
                measure = concept
            else:
                continue
            member_key = tuple(sorted(dims.items()))
            key = (measure, member_key)
            series = cells.setdefault(key, {
                "axes": axes, "kind": _kind(axes), "measure": measure, "member_key": member_key,
                "member": "|".join(m for _, m in member_key), "label": _label(row, dims),
                "generic": len(dims) == 1 and bool(_GENERIC_MEMBERS.match(next(iter(dims.values())))),
                "concepts": set(), "points": {},
            })
            series["concepts"].add(concept)
            point = series["points"].get(row["end"])
            if point is None:
                series["points"][row["end"]] = {
                    "value": row["value"], "first_value": row["value"],
                    "first_accession": meta["accession"], "accession": meta["accession"], "start": row["start"],
                }
            else:  # a later filing: its value is the current basis, the first report stays recorded
                point["value"] = row["value"]
                point["accession"] = meta["accession"]
            series["label"] = _label(row, dims)  # filings run oldest first: the latest label wins
    out = []
    for series in cells.values():
        series["concepts"] = sorted(series["concepts"])
        series["axis"] = "+".join(series["axes"])
        out.append(series)
    _mark_subtotals(out)
    out.sort(key=lambda s: (s["kind"], s["measure"], len(s["axes"]), -max((p["value"] for p in s["points"].values()), default=0)))
    return out


def _mark_subtotals(series: list[dict[str, Any]]) -> None:
    by_group: dict[tuple[str, tuple[str, ...]], list[dict[str, Any]]] = {}
    for item in series:
        item["subtotal"] = False
        by_group.setdefault((item["measure"], item["axes"]), []).append(item)
    for members in by_group.values():
        if len(members) < 3:
            continue
        for candidate in members:
            hits = checked = 0
            for end, point in candidate["points"].items():
                others = [m["points"][end]["value"] for m in members if m is not candidate and end in m["points"]]
                target = point["value"]
                if not target or len(others) < 2:
                    continue
                checked += 1
                hits += int(any(
                    abs(sum(combo) - target) <= abs(target) * 0.002
                    for size in (2, 3) for combo in combinations(others, size)
                ))
            if checked and hits * 2 >= checked:
                candidate["subtotal"] = True


def coverage(series: list[dict[str, Any]], totals: dict[str, float]) -> list[dict[str, Any]]:
    """Per single-axis group and year: sum of non-subtotal revenue members against consolidated revenue."""
    rows = []
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in series:
        if item["measure"] == "revenue" and not item["subtotal"] and len(item["axes"]) == 1:
            groups.setdefault(item["axis"], []).append(item)
    for axis, members in groups.items():
        specific = [m for m in members if not m["generic"]]
        if len(specific) >= 2:
            members = specific  # category members ("Product", "Other") total the specific ones
        for end, total in sorted(totals.items()):
            values = [m["points"][end]["value"] for m in members if end in m["points"]]
            if len(values) < 2 or not total:
                continue
            rows.append({
                "axis": axis, "kind": _kind((axis,)), "period_end": end, "members": len(values),
                "member_sum": sum(values), "total": total, "ratio": sum(values) / total,
            })
    return rows
