"""Acquire a reported operating-to-pretax bridge from already-provided primary HTML.

No transport or prose classification: statement position supplies the relationship;
complete signed arithmetic corroborates it. Unsupported layouts abstain.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Any

from lxml import etree, html

_TITLE = re.compile(r"Consolidated Statements of (?:Income|Operations)", re.I)
_UNIT = re.compile(
    r"\((?:In|Amounts expressed in) (millions|thousands) of (?:U\.S\.|US) dollars"
    r"(?:, except for share data| [\(“\"]*\$[\)”\"]*)?\)", re.I,
)
_PERIOD = re.compile(r"(?:For the )?Year[s]? Ended ([A-Za-z]+) (\d{1,2}),?", re.I)
_YEAR = re.compile(r"(\d{4})(?:\s*(\(\d+\)))?(?:\s*\$)?")
_START = {"Income from operations", "Operating income"}
_END = {"Net income before income tax expense and equity in earnings of unconsolidated entity",
        "Income before income tax and share of results of equity investees"}
_COMPONENTS = {
    "Interest income", "Interest income and other financial gains, net",
    "Interest expense", "Interest expense and other financial losses",
    "Foreign currency losses, net", "Foreign exchange gain (loss)",
    "Net investment loss", "Gain on debt extinguishment", "Net gain on debt extinguishment",
}
_HEADINGS = {"Other income (expenses):"}


def _text(node: Any) -> str:
    return " ".join(" ".join(node.itertext()).split())


def _nearby(table: Any) -> list[Any]:
    # The two supported layouts put headings immediately before the table, or its wrapper.
    nodes = list(table.itersiblings(preceding=True))[:8]
    if not any(_text(node) for node in nodes):
        nodes = list(table.getparent().itersiblings(preceding=True))[:8]
    bounded = []
    for node in nodes:
        if node.tag == "table" or node.xpath(".//table"):
            break  # never borrow a heading or unit across another table
        bounded.append(node)
    return bounded


def _cells(row: Any) -> list[dict] | None:
    result, column = [], 0
    for cell in row.xpath("./td|./th"):
        try:
            span = int(cell.get("colspan", "1"))
            rowspan = int(cell.get("rowspan", "1"))
        except ValueError:
            return None
        if not 1 <= span <= 100 or rowspan != 1:
            return None
        result.append({"column": column, "colspan": span, "text": _text(cell)})
        column += span
    return result


def _amount(cells: list[dict], start: int, end: int, scale: int) -> dict | None:
    owned = [c for c in cells if c["column"] >= start and c["column"] + c["colspan"] <= end]
    if any(c["text"] and c not in owned and c["column"] < end and c["column"] + c["colspan"] > start for c in cells):
        return None
    lexical = " ".join(c["text"] for c in owned if c["text"])
    compact = re.sub(r"\s+", "", lexical)
    if compact.startswith("$"):
        compact = compact[1:]
    if compact in {"—", "–", "-"}:
        value = 0
    else:
        negative = compact.startswith("(") and compact.endswith(")")
        digits = compact[1:-1] if negative else compact
        if not re.fullmatch(r"(?:\d{1,3}(?:,\d{3})+|\d+)", digits):
            return None  # unmatched/extra sign cells and decimal/percentage layouts abstain
        value = int(digits.replace(",", "")) * (-1 if negative else 1)
    return {"value": value * scale, "lexical": lexical, "cells": owned}


def _table_source(table: Any, report: date) -> dict | None:
    preceding = _nearby(table)
    titles = [n for n in preceding if _TITLE.fullmatch(_text(n))]
    units = [(n, _UNIT.fullmatch(_text(n))) for n in preceding]
    units = [(n, match) for n, match in units if match]
    if len(titles) != 1 or len(units) != 1:
        return None
    unit_node, unit_match = units[0]
    scale = 1_000_000 if unit_match[1].lower() == "millions" else 1000
    rows = table.xpath("./tr|./tbody/tr")
    matrix = [_cells(row) for row in rows]
    if any(cells is None for cells in matrix):
        return None
    period_headers, years = [], []
    year_row = None
    for index, cells in enumerate(matrix[:5]):
        for cell in cells:
            match = _PERIOD.fullmatch(cell["text"])
            if match:
                period_headers.append(match)
        found = [(c, _YEAR.fullmatch(c["text"])) for c in cells if _YEAR.fullmatch(c["text"])]
        other = [c["text"] for c in cells if c["text"] and not _YEAR.fullmatch(c["text"])]
        if len(found) >= 2 and all(text == "Note" for text in other):
            if year_row is not None:
                return None
            year_row = index
            years = [{"year": int(match[1]), "label": cell["text"], "column": cell["column"]}
                     for cell, match in found]
    if len(period_headers) != 1 or not years or len({y["year"] for y in years}) != len(years):
        return None
    # A note-number header is allowed before year groups, but never mistaken for a year.
    try:
        month = date.fromisoformat(f"2000-{report.month:02d}-{report.day:02d}").strftime("%B")
        if period_headers[0][1].lower() != month.lower() or int(period_headers[0][2]) != report.day:
            return None
    except ValueError:
        return None
    labels = [cells[0]["text"] if cells else "" for cells in matrix]
    starts = [i for i, label in enumerate(labels) if label in _START]
    ends = [i for i, label in enumerate(labels) if label in _END]
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0] or year_row >= starts[0]:
        return None
    first, last = starts[0], ends[0]
    component_rows = []
    for index in range(first + 1, last):
        label, cells = labels[index], matrix[index]
        if not any(c["text"] for c in cells):
            continue
        if label in _HEADINGS and not any(c["text"] for c in cells[1:]):
            continue
        if label not in _COMPONENTS:
            return None
        component_rows.append(index)
    if not component_rows or len({labels[i] for i in component_rows}) != len(component_rows):
        return None
    width = max(c["column"] + c["colspan"] for cells in matrix for c in cells)
    columns = []
    for index, year in enumerate(years):
        start, end = year["column"], years[index + 1]["column"] if index + 1 < len(years) else width
        records = []
        for row in [first, *component_rows, last]:
            if any(c["text"] for c in matrix[row][1:] if c["column"] < years[0]["column"]):
                return None
            amount = _amount(matrix[row], start, end, scale)
            if amount is None:
                return None
            records.append({"row": row, "label": labels[row], **amount})
        if records[0]["value"] + sum(r["value"] for r in records[1:-1]) != records[-1]["value"]:
            return None
        columns.append({**year, "column_end": end,
                        "period_end": f"{year['year']:04d}-{report.month:02d}-{report.day:02d}",
                        "operating": records[0], "components": records[1:-1], "pretax": records[-1]})
    current = [c for c in columns if c["period_end"] == report.isoformat()]
    prior = [c for c in columns if c["year"] == report.year - 1]
    if len(current) != 1 or len(prior) != 1:
        return None
    tree = table.getroottree()
    return {"table_path": tree.getpath(table), "title": _text(titles[0]),
            "title_path": tree.getpath(titles[0]), "unit_text": _text(unit_node),
            "unit_path": tree.getpath(unit_node), "currency": "USD", "scale": scale,
            "relationship": "reported_between_operating_and_pretax", "columns": columns,
            "current": current[0], "prior": prior[0]}


def extract_operating_to_pretax_source(source_html: str | bytes, *, accession: str,
                                      document_url: str, period_of_report: str) -> dict | None:
    """Return one complete source-qualified relationship, or None; never fetch anything."""
    if not source_html or not accession or not document_url:
        return None
    try:
        report = date.fromisoformat(period_of_report)
        raw = source_html.encode("utf-8") if isinstance(source_html, str) else source_html
        document = html.fromstring(raw, parser=html.HTMLParser(no_network=True))
    except (ValueError, TypeError, etree.ParserError):
        return None
    candidates = [source for table in document.xpath("//table") if (source := _table_source(table, report))]
    if len(candidates) != 1:
        return None
    return {"version": 1, "accession": accession, "document_url": document_url,
            "document_sha256": hashlib.sha256(raw).hexdigest(), "period_of_report": report.isoformat(),
            **candidates[0]}
