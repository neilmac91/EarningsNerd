"""Bounded, explicit-source quarterly EPS acquisition from an SEC earnings exhibit.

This is an operations fallback, not an exhibit crawler. Callers supply a reviewed
CIK/accession/filename and reporting currency. Unsupported statement layouts return
None; no EPS or diluted denominator is estimated. Network I/O remains owned by the
existing SEC attachment transport. The returned evidence belongs in the repair
journal alongside the fact provenance, not in an invented XBRL tag.
"""
from __future__ import annotations

import calendar
import hashlib
import re
from datetime import date
from decimal import Decimal
from typing import Any

from lxml import etree, html

from app.services.edgar.statement_relationship_source import _cells, _text
from app.utils.sec_urls import build_sec_archive_url, normalize_accession, normalize_cik

_TITLE = re.compile(r"(?:CONDENSED )?CONSOLIDATED STATEMENTS OF (?:INCOME|OPERATIONS)", re.I)
_UNITS = re.compile(r"\(In (?:millions|thousands), except (?:for )?per share amounts\)", re.I)
_QUARTER = re.compile(r"Three Months Ended ([A-Za-z]+) (\d{1,2}),?", re.I)
_EPS_LABELS = {
    "earnings per share:",
    "earnings per share attributable to common stockholders:",
    "earnings per share attributable to class a and class b common stockholders:",
}
_NUMBER = re.compile(r"(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{1,4}")
_CURRENCY_SYMBOLS = {"USD": "$", "CAD": "$", "AUD": "$", "EUR": "€", "GBP": "£"}
_MAX_SOURCE_BYTES = 8 * 1024 * 1024
_MAX_TABLES = 100


def _quarter_start(end: date) -> date | None:
    """An exact three-calendar-month caption is required; week-based periods abstain."""
    if end.day != calendar.monthrange(end.year, end.month)[1]:
        return None
    month_index = end.year * 12 + end.month - 3
    return date(month_index // 12, month_index % 12 + 1, 1)


def _headings(table: Any) -> tuple[str, str] | None:
    """Read adjacent statement headings without borrowing across another table."""
    nodes = list(table.itersiblings(preceding=True))[:8]
    if not any(_text(n) for n in nodes) and table.getparent() is not None:
        nodes = list(table.getparent().itersiblings(preceding=True))[:8]
    title, units = [], []
    for node in nodes:
        text = _text(node)
        if node.tag == "table" or node.xpath(".//table"):
            break
        if _TITLE.fullmatch(text):
            title.append(text)
        if _UNITS.fullmatch(text):
            units.append(text)
    # Earnings exhibits also put their statement headings inside full-width
    # table rows. Only complete row-wide headings establish this scope.
    rows = table.xpath("./tr|./tbody/tr|./thead/tr")
    matrix = [_cells(row) for row in rows]
    if any(cells is None for cells in matrix):
        return None
    width = max((c["column"] + c["colspan"] for cells in matrix for c in cells), default=0)
    for cells in matrix[:5]:
        if len(cells) != 1 or cells[0]["column"] != 0 or cells[0]["colspan"] != width:
            continue
        text = cells[0]["text"]
        if _TITLE.fullmatch(text):
            title.append(text)
        if _UNITS.fullmatch(text):
            units.append(text)
    if len(title) != 1 or len(units) != 1:
        return None
    return title[0], units[0]


def _amount(cells: list[dict], start: int, end: int, symbol: str) -> dict | None:
    owned = [c for c in cells if start <= c["column"] and c["column"] + c["colspan"] <= end]
    if any(c["text"] and c not in owned and c["column"] < end
           and c["column"] + c["colspan"] > start for c in cells):
        return None
    tokens = [c["text"] for c in owned if c["text"]]
    lexical = " ".join(tokens)
    # Exactly one numeric lexeme, before whitespace compaction. Adjacent numbers
    # must not become a fabricated decimal, nor may a footnote become its sign.
    numeric = [t for t in tokens if re.search(r"\d", t)]
    if len(numeric) != 1:
        return None
    number = numeric[0]
    decorated = rf"{re.escape(symbol)}?\s*\(?\s*-?{_NUMBER.pattern}\s*\)?"
    if re.fullmatch(decorated, number) is None:
        return None
    if any(t not in {symbol, "(", ")", "-"} for t in tokens if t not in numeric):
        return None
    compact = re.sub(r"\s+", "", lexical)
    if compact.startswith(symbol):
        compact = compact[len(symbol):]
    negative = compact.startswith("(") and compact.endswith(")")
    raw = compact[1:-1] if negative else compact
    if raw.startswith("-"):
        if negative:
            return None
        negative, raw = True, raw[1:]
    if _NUMBER.fullmatch(raw) is None:
        return None
    value = Decimal(raw.replace(",", "")) * (-1 if negative else 1)
    return {"value": value, "lexical": lexical, "cells": owned}


def _extract_table(table: Any, period_end: date, currency: str) -> dict | None:
    headings = _headings(table)
    if headings is None or table.xpath(".//table"):
        return None
    if re.search(r"non[- ]?gaap|adjusted|pro forma|continuing operations|discontinued operations",
                 _text(table), re.I):
        return None
    rows = table.xpath("./tr|./tbody/tr|./thead/tr|./tfoot/tr")
    if not 6 <= len(rows) <= 150:
        return None
    matrix = [_cells(row) for row in rows]
    if any(c is None for c in matrix):
        return None
    labels = [next((c["text"] for c in cells if c["text"]), "") for cells in matrix]
    # One undivided EPS pair: individual share-class blocks, duplicate sections,
    # competing net-income numerators and footnoted EPS row labels abstain.
    groups = [i for i, label in enumerate(labels) if label.lower() in _EPS_LABELS]
    if len(groups) != 1:
        return None
    eps_at = groups[0]
    if any("earnings per share" in label.lower() and i != eps_at
           and not label.lower().startswith("weighted-average shares")
           for i, label in enumerate(labels)):
        return None
    incomes = [label.lower() for label in labels[:eps_at] if "net income" in label.lower()]
    if incomes != ["net income"]:
        return None
    after = [i for i in range(eps_at + 1, len(rows)) if labels[i]][:3]
    if len(after) < 2 or [labels[i].lower() for i in after[:2]] != ["basic", "diluted"]:
        return None
    if len(after) > 2 and not labels[after[2]].lower().startswith("weighted-average shares"):
        return None
    headers = []
    for i, cells in enumerate(matrix[:min(eps_at, 6)]):
        for cell in cells:
            if match := _QUARTER.fullmatch(cell["text"]):
                try:
                    month = list(calendar.month_name).index(match[1].capitalize())
                except ValueError:
                    return None
                if (month, int(match[2])) != (period_end.month, period_end.day):
                    continue
                headers.append((i, cell))
    if len(headers) != 1:
        return None
    header_at, header = headers[0]
    start, end = header["column"], header["column"] + header["colspan"]
    years = []
    for i in range(header_at + 1, min(header_at + 4, eps_at)):
        for cell in matrix[i]:
            if (cell["text"] == str(period_end.year) and start <= cell["column"]
                    and cell["column"] + cell["colspan"] <= end):
                years.append((i, cell))
    if len(years) != 1:
        return None
    year_at, year = years[0]
    # Year headers must explicitly span the selected amount cells. A caption
    # somewhere else in the table does not establish which column is quarterly.
    band_start, band_end = year["column"], year["column"] + year["colspan"]
    tree = table.getroottree()
    result = {}
    for concept, row_at in zip(("eps_basic", "eps_diluted"), after[:2]):
        amount = _amount(matrix[row_at], band_start, band_end, _CURRENCY_SYMBOLS[currency])
        if amount is None:
            return None
        result[concept] = {**amount, "row_path": tree.getpath(rows[row_at]), "label": labels[row_at]}
    return {
        "values": {key: value["value"] for key, value in result.items()},
        "evidence": {
            "title": headings[0], "units_caption": headings[1],
            "period_caption": header["text"], "year": period_end.year,
            "header_row": header_at, "year_row": year_at,
            "column_start": band_start, "column_end": band_end,
            "table_path": tree.getpath(table),
            "table_html": html.tostring(table, encoding="unicode"),
            "rows": {key: {**value, "value": str(value["value"])} for key, value in result.items()},
        },
    }


def extract_reported_quarterly_eps(
    content: bytes, *, cik: str, accession: str, filename: str,
    period_end: date | str, currency: str, source: dict[str, Any],
) -> dict[str, Any] | None:
    """Parse one authenticated attachment representation, or abstain.

    ``currency`` is selected by the caller from the company's reporting currency;
    a dollar symbol alone never distinguishes USD, CAD and AUD. Source metadata
    must be the receipt returned with these bytes by the attachment transport.
    """
    try:
        cik = normalize_cik(cik)
        accession_digits = normalize_accession(accession)
        end = date.fromisoformat(period_end) if isinstance(period_end, str) else period_end
        begin = _quarter_start(end)
        from app.services.edgar.compat import _filing_attachment_url
        url = _filing_attachment_url(cik, accession, filename)
    except (ValueError, TypeError, AttributeError):
        return None
    if (not isinstance(content, bytes) or not 0 < len(content) <= _MAX_SOURCE_BYTES
            or currency not in _CURRENCY_SYMBOLS or begin is None
            or not filename.lower().endswith((".htm", ".html"))
            or source.get("representation") != "httpx_identity_entity_bytes"
            or source.get("cik") != cik or source.get("accession_number") != accession_digits
            or source.get("filename") != filename or source.get("requested_url") != url
            or source.get("final_url") != url or source.get("status_code") != 200
            or source.get("sha256") != hashlib.sha256(content).hexdigest()
            or source.get("bytes") != len(content)):
        return None
    try:
        document = html.fromstring(content, parser=html.HTMLParser(no_network=True))
    except (etree.ParserError, ValueError):
        return None
    tables = document.xpath("//table")
    if len(tables) > _MAX_TABLES:
        return None
    found = [record for table in tables
             if (record := _extract_table(table, end, currency)) is not None]
    if len(found) != 1:
        return None
    selected = found[0]
    return {
        "cik": cik, "accession": accession, "form": "8-K", "source": "reported_eps",
        "raw_tag": None, "unit": f"{currency}/shares",
        "period_start": begin.isoformat(), "period_end": end.isoformat(),
        "source_url": url, "source_sha256": source["sha256"],
        "currency_basis": "caller_selected_reporting_currency",
        "values": selected["values"],
        "source_evidence": {"transport": source, **selected["evidence"]},
    }


async def fetch_reported_quarterly_eps(
    cik: str, accession: str, filename: str, period_end: date | str, *, currency: str,
) -> dict[str, Any] | None:
    """Fetch one manifest-selected source with a single paced SEC attempt.

    No issuer-specific values, URL guessing, filing discovery or database writes.
    Transport failures propagate so the repair command can journal failure and
    avoid treating an unavailable source as a successful empty repair.
    """
    from app.services.edgar.compat import sec_edgar_service

    # Validate before making the request; the transport owns safe filename checks.
    build_sec_archive_url(cik, accession)
    if currency not in _CURRENCY_SYMBOLS:
        raise ValueError("Unsupported explicit reporting currency")
    end = date.fromisoformat(period_end) if isinstance(period_end, str) else period_end
    if _quarter_start(end) is None:
        raise ValueError("Reported EPS requires an exact three-calendar-month period")
    content, source = await sec_edgar_service.get_filing_attachment_bytes(
        cik, accession, filename, timeout=20.0, max_retries=1,
    )
    return extract_reported_quarterly_eps(
        content, cik=cik, accession=accession, filename=filename,
        period_end=end, currency=currency, source=source,
    )
