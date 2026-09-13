"""Request-local primary-statement evidence, never a prompt or transport input."""
from __future__ import annotations

from datetime import datetime, date
import re
from typing import Any

from lxml import html

from .statement_disclosures import extract_statement_disclosures
from .statement_relationship_source import (
    _amount, _cells, _text, extract_operating_to_pretax_source,
)

_EXPENSES = {"Product and technology development", "Sales and marketing",
             "Provision for doubtful accounts", "General and administrative",
             "Other operating income", "Sales and marketing expenses",
             "General and administrative expenses", "Provision for credit losses",
             "Research and development expenses", "Impairment of goodwill"}
_DISCLOSED = {"Provision for doubtful accounts", "Provision for credit losses", "Impairment of goodwill"}
_NOTE_HEADINGS = {"general and administrative expenses", "provision for doubtful accounts"}


def source_report_period(document: Any) -> str | None:
    """Validate the actual inline DEI date and its unqualified context; no year inference."""
    facts = [n for n in document.iter() if isinstance(n.tag, str)
             and n.get("name", "").lower() == "dei:documentperiodenddate"]
    dates = set()
    entities = set()
    for fact in facts:
        if fact.get("continuedat") or fact.get("xsi:nil") or fact.get("nil"):
            return None
        text = re.sub(r"\s+,", ",", _text(fact))
        try:
            if fact.get("format", "").lower() == "ixt:date-monthname-day-year-en":
                value = datetime.strptime(text, "%B %d, %Y").date().isoformat()
            elif not fact.get("format"):
                value = date.fromisoformat(text).isoformat()
            else:
                return None
        except ValueError:
            return None
        contexts = [n for n in document.iter() if n.get("id") == fact.get("contextref")]
        if len(contexts) != 1:
            return None
        context = contexts[0]
        tags = [n.tag.lower().split(":")[-1] for n in context.iter() if isinstance(n.tag, str)]
        ends = [_text(n) for n in context.iter() if isinstance(n.tag, str)
                and n.tag.lower().split(":")[-1] == "enddate"]
        if ends != [value] or any(t in tags for t in ("segment", "scenario", "explicitmember", "typedmember")):
            return None
        identifiers = [n for n in context.iter() if isinstance(n.tag, str)
                       and n.tag.lower().split(":")[-1] == "identifier"]
        if len(identifiers) != 1 or identifiers[0].get("scheme") != "http://www.sec.gov/CIK":
            return None
        entity = _text(identifiers[0])
        if not re.fullmatch(r"\d{1,10}", entity):
            return None
        entities.add(entity)
        dates.add(value)
    return next(iter(dates)) if len(dates) == 1 and len(entities) == 1 else None


def _operating_rows(table: Any, source: dict) -> list[dict] | None:
    rows = table.xpath("./tr|./tbody/tr")
    matrix = [_cells(row) for row in rows]
    labels = [cells[0]["text"] if cells else "" for cells in matrix]
    gross = [i for i, label in enumerate(labels) if label == "Gross profit"]
    heading = [i for i, label in enumerate(labels) if label in {"Operating expenses:", "Operating income (expenses)"}]
    totals = [i for i, label in enumerate(labels) if label == "Total operating expenses"]
    end = source["current"]["operating"]["row"]
    if len(gross) != 1 or len(heading) != 1 or len(totals) != 1 or not gross[0] < heading[0] < totals[0] < end:
        return None
    components = []
    for i in range(gross[0] + 1, end):
        if not any(c["text"] for c in matrix[i]) or i in {heading[0], totals[0]}:
            continue
        if labels[i] not in _EXPENSES:
            return None
        components.append(i)
    if not components or len({labels[i] for i in components}) != len(components):
        return None
    preserved = []
    for column in source["columns"]:
        amounts = {}
        for i in [gross[0], totals[0], *components]:
            amount = _amount(matrix[i], column["column"], column["column_end"], source["scale"])
            if amount is None:
                return None
            amounts[i] = {"row": i, "label": labels[i], **amount}
        if amounts[gross[0]]["value"] + sum(amounts[i]["value"] for i in components) != column["operating"]["value"]:
            return None
        if sum(amounts[i]["value"] for i in components) != amounts[totals[0]]["value"]:
            return None
        preserved.append({"year": column["year"], "period_end": column["period_end"],
                          "rows": [amounts[i] for i in components if labels[i] in _DISCLOSED]})
    return preserved


def _expense_notes(document: Any, table: Any) -> list[dict] | None:
    tree = document.getroottree()
    notes = []
    # Only complete DOM leaf paragraphs beneath exact expense headings before the face table.
    # Matching a topic does not establish a cause: these are attributed source disclosures.
    before = set(table.xpath("preceding::*"))
    for heading in document.xpath("//div|//p"):
        if heading not in before or heading.xpath(".//div|.//p|.//table"):
            continue
        if _text(heading).casefold() not in _NOTE_HEADINGS:
            continue
        for node in list(heading.itersiblings())[:6]:
            text = _text(node)
            if not text:
                continue
            if node.xpath(".//div|.//p|.//table") or node.tag == "table":
                continue
            if re.match(r"(?:Our general and administrative expenses (?:increased|decreased) |For the year ended )", text):
                if not text.endswith(".") or len(text) > 1200:
                    return None
                notes.append({"heading": _text(heading), "path": tree.getpath(node), "text": text})
                break
            # A short heading-like line ends this narrow source block.
            if len(text) < 100 and not text.endswith(('.', ':')):
                break
    unique = {n["path"]: n for n in notes}
    if len(unique) > 4 or sum(len(n["text"]) for n in unique.values()) > 4000:
        return None
    return list(unique.values())


def acquire_statement_context(source_html: str, *, accession: str, document_url: str,
                              form: str, report_period: str | None = None) -> dict | None:
    """Same fresh-source seam for production and eval; unavailable sources remain legacy."""
    if form not in {"10-K", "20-F"} or not source_html:
        return None
    try:
        document = html.fromstring(source_html.encode("utf-8"), parser=html.HTMLParser(no_network=True))
    except (ValueError, TypeError):
        return None
    period = source_report_period(document)
    if period is None or (report_period is not None and period != report_period):
        return None
    source = extract_operating_to_pretax_source(source_html, accession=accession,
                                               document_url=document_url, period_of_report=period)
    if source is None:
        return None
    table = document.xpath(source["table_path"])[0]
    rows = _operating_rows(table, source)
    notes = _expense_notes(document, table)
    if rows is None or notes is None:
        return None
    adjacent = []
    annotated = any("(" in col["label"] for col in source["columns"])
    if annotated:
        siblings = list(table.itersiblings()) + list(table.getparent().itersiblings())
        first = next((n for n in siblings if _text(n)), None)
        if first is None or first.xpath(".//table") or not _text(first).startswith("(1) ") or len(_text(first)) > 1500:
            return None
        adjacent.append({"path": document.getroottree().getpath(first), "text": _text(first)})
    dei = next(n for n in document.iter() if n.get("name", "").lower() == "dei:documentperiodenddate")
    context = next(n for n in document.iter() if n.get("id") == dei.get("contextref"))
    entity = next(_text(n) for n in context.iter() if isinstance(n.tag, str)
                  and n.tag.lower().split(":")[-1] == "identifier")
    disclosures = extract_statement_disclosures(
        document, accession=accession, document_url=document_url, report_period=period,
        source_sha256=source["document_sha256"], entity_identifier=entity,
    )
    if disclosures is None:
        return None
    return {**source, "operating_disclosures": rows, "expense_notes": notes,
            "comparative_notes": adjacent, "additional_disclosures": [r for r in disclosures.values() if r]}
