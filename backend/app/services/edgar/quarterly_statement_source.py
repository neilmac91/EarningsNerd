"""Match a finite quarterly claim to tagged amounts; never authorize financial prose.

This descriptor is used only to withhold a complete ambiguous component claim.
Its issuer, dates, units and rows identify matching operands. They do not establish
assertion scope, a realized component amount or a cause. Governing qualifications
can exist outside the selected table. No quarterly financial statement is rendered
from this descriptor.
"""
from __future__ import annotations

import calendar
import hashlib
import re
from datetime import date
from typing import Any

from app.services.edgar.statement_relationship_source import _amount, _cells, _text
from app.utils.sec_urls import build_sec_archive_url

KIND = "tagged_quarterly_component_match"
_ROWS = (
    ("operating", "us-gaap:OperatingIncomeLoss", {"Income from operations", "Operating income"}),
    ("interest", "us-gaap:InvestmentIncomeInterest", {"Interest income"}),
    ("other", "us-gaap:OtherNonoperatingIncomeExpense", {"Other income (expense), net"}),
    ("pretax", "us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
     {"Income before provision for income taxes"}),
    ("tax", "us-gaap:IncomeTaxExpenseBenefit", {"Provision for income taxes"}),
    ("net", "us-gaap:ProfitLoss", {"Net income"}),
)
_DIGITS = re.compile(r"(?:\d{1,3}(?:,\d{3})+|\d+)")
_BEFORE_BRIDGE = ["Revenue", "Cost of revenue", "Gross profit", "Operating expenses:",
                  "Sales and marketing", "Research and development", "General and administrative",
                  "Total operating expenses"]
_AFTER_BRIDGE = ["Less: Net income attributable to noncontrolling interests",
                 "Net income attributable to common stockholders",
                 "Earnings per share attributable to common stockholders, basic",
                 "Earnings per share attributable to common stockholders, diluted",
                 "Weighted-average shares of common stock outstanding used in computing earnings per share "
                 "attributable to common stockholders, basic",
                 "Weighted-average shares of common stock outstanding used in computing earnings per share "
                 "attributable to common stockholders, diluted"]


def _tag(node: Any) -> str:
    return node.tag.lower() if isinstance(node.tag, str) else ""


def _duration(node: Any, issuer: str) -> tuple[str, str] | None:
    """Keep both duration dates locally; do not change the existing instant owner API."""
    from app.services.edgar.statement_context import source_context_identity

    children = list(node)
    if ([ _tag(n) for n in children] != ["xbrli:entity", "xbrli:period"]
            or [_tag(n) for n in children[0]] != ["xbrli:identifier"]
            or [_tag(n) for n in children[1]] != ["xbrli:startdate", "xbrli:enddate"]):
        return None
    identity = source_context_identity(node)
    if identity is None or identity[0] != issuer or identity[1] != "duration" or identity[3]:
        return None
    starts = [_text(n) for n in node.iter() if _tag(n).split(":")[-1] == "startdate"]
    try:
        start, end = date.fromisoformat(starts[0]), date.fromisoformat(identity[2])
    except (ValueError, IndexError):
        return None
    if start > end:
        return None
    return start.isoformat(), end.isoformat()


def _single_dei(document: Any, name: str, contexts: dict, report_period: str) -> str | None:
    facts = [n for n in document.iter() if n.get("name") == name]
    if (len(facts) != 1 or _tag(facts[0]) != "ix:nonnumeric" or facts[0].get("continuedat")
            or facts[0].get("nil") or facts[0].get("xsi:nil")):
        return None
    duration = contexts.get(facts[0].get("contextref"))
    return _text(facts[0]) if duration and duration[1] == report_period else None


def _fact_value(fact: Any, units: dict) -> tuple[int, int] | None:
    if (_tag(fact) != "ix:nonfraction" or fact.get("continuedat") or fact.get("nil")
            or fact.get("xsi:nil") or fact.get("format") not in {None, "ixt:num-dot-decimal"}
            or fact.get("sign") not in {None, "-"} or fact.get("scale") not in {"3", "6"}
            or units.get(fact.get("unitref")) != "USD" or not _DIGITS.fullmatch(_text(fact))
            or fact.xpath("ancestor::*[name()='ix:hidden']")):
        return None
    scale = 10 ** int(fact.get("scale"))
    try:
        value = int(_text(fact).replace(",", "")) * scale
        str(value)  # The scaled integer must also survive the descriptor's JSON encoding.
    except ValueError:  # Input or scaled output may exceed Python's integer digit limit.
        return None
    return (-value if fact.get("sign") == "-" else value), scale


def _table(table: Any, *, document: Any, report: date, issuer_name: str,
           contexts: dict, units: dict, ids: dict) -> dict | None:
    # A finite layout for matching operands, not a complete assertion-scope owner.
    # Unknown content within this layout abstains; content outside it may govern
    # the statement and cannot authorize an unconditional financial replacement.
    wrapper = table.getparent()
    heading = wrapper.getprevious()
    if heading is None or table.xpath("./caption") or len(wrapper.xpath("./table")) != 1:
        return None
    outside = " ".join([wrapper.text or "", *(str(t) for n in wrapper if n is not table
                                             for t in n.itertext()), *(n.tail or "" for n in wrapper)])
    if outside.strip():
        return None
    heading_text = _text(heading)
    expected = (rf"(?:Table of contents )?{re.escape(issuer_name)} "
                r"Condensed Consolidated Statements of Operations "
                r"\(in (thousands|millions), except per share amounts\) \(unaudited\)")
    title = re.fullmatch(expected, heading_text)
    if title is None:
        return None
    scale = 1000 if title[1] == "thousands" else 1000000
    rows = table.xpath("./tr|./tbody/tr")
    matrix = [_cells(row) for row in rows]
    if len(matrix) < 3 or any(cells is None for cells in matrix):
        return None
    labels = [cells[0]["text"] if cells else "" for cells in matrix]
    # The entire demonstrated face-table grammar is closed. Prose before or after
    # the bridge, unknown rows, footnote markers and text outside cells abstain.
    if (_text(table) != " ".join(c["text"] for cells in matrix for c in cells if c["text"])
            or any(c["text"] and re.fullmatch(r"[\d,$.()\s—–-]+", c["text"]) is None
                   for cells in matrix[3:] for c in cells[1:])):
        return None
    period = f"Three Months Ended {report.strftime('%B')} {report.day},"
    if [c["text"] for row in matrix[:3] for c in row if c["text"]] != [period, str(report.year), str(report.year - 1)]:
        return None
    year_cells = [c for c in matrix[2] if c["text"]]
    if len(year_cells) != 2:
        return None
    positions = [[i for i, label in enumerate(labels) if label in permitted] for _, _, permitted in _ROWS]
    if any(len(found) != 1 for found in positions):
        return None
    selected = [found[0] for found in positions]
    if selected != list(range(selected[0], selected[0] + len(_ROWS))):
        return None  # an extra row, footnote or component cannot disappear into the bridge
    if labels != ["", "", "", *_BEFORE_BRIDGE, *(labels[i] for i in selected), *_AFTER_BRIDGE]:
        return None
    width = max(c["column"] + c["colspan"] for cells in matrix for c in cells)
    output = []
    tree = document.getroottree()
    for i, year in enumerate((report.year, report.year - 1)):
        start_col = year_cells[i]["column"]
        end_col = year_cells[i + 1]["column"] if i == 0 else width
        facts_out, durations = {}, set()
        for (key, concept, _), row_index in zip(_ROWS, selected):
            cells = matrix[row_index]
            # Exactly one directly tagged fact per year band, with no borrowed tag.
            row_cells = rows[row_index].xpath("./td|./th")
            found = []
            for cell, position in zip(row_cells, cells):
                if start_col <= position["column"] and position["column"] + position["colspan"] <= end_col:
                    found.extend(n for n in cell.iter() if _tag(n) == "ix:nonfraction")
            if len(found) != 1:
                return None
            fact = found[0]
            duration = contexts.get(fact.get("contextref"))
            value = _fact_value(fact, units)
            if value is None:
                return None  # Do not reparse an invalid fact through the visible-amount owner.
            visible = _amount(cells, start_col, end_col, scale)
            if (fact.get("name") != concept or not fact.get("id") or ids.get(fact.get("id")) is not fact
                    or duration is None or value[1] != scale
                    or visible is None or visible["value"] != value[0]):
                return None
            durations.add(duration)
            facts_out[key] = {"concept": concept, "label": labels[row_index], "value": value[0],
                              "row_path": tree.getpath(rows[row_index]), "fact_id": fact.get("id"),
                              "context_id": fact.get("contextref"), "unit_id": fact.get("unitref")}
        if len(durations) != 1:
            return None
        start, end = next(iter(durations))
        begin, finish = date.fromisoformat(start), date.fromisoformat(end)
        if ((finish.year, finish.month, finish.day) != (year, report.month, report.day) or begin.day != 1
                or finish.day != calendar.monthrange(year, finish.month)[1]
                or (finish.year * 12 + finish.month) - (begin.year * 12 + begin.month) != 2):
            return None
        values = {key: fact["value"] for key, fact in facts_out.items()}
        if (values["operating"] + values["interest"] + values["other"] != values["pretax"]
                or values["pretax"] - values["tax"] != values["net"]):
            return None
        # Repeated facts for this same reported duration must agree, including unit and sign.
        for key, concept, _ in _ROWS:
            repeats = [f for f in document.iter() if f.get("name") == concept
                       and contexts.get(f.get("contextref")) == (start, end)]
            if any(_fact_value(f, units) != (values[key], scale) for f in repeats):
                return None
        output.append({"start": start, "end": end, "rows": facts_out})
    return {"kind": KIND, "table_path": tree.getpath(table), "heading_path": tree.getpath(heading),
            "title": heading_text, "currency": "USD", "scale": scale,
            "current": output[0], "prior": output[1]}


def extract_quarterly_statement(document: Any, source_html: str, *, accession: str,
                                document_url: str, report_period: str) -> dict | None:
    """Match one direct fact sequence for claim withholding; no semantic authority."""
    from app.services.edgar.statement_context import source_report_identity

    namespaces = {"ix": r"http://www\.xbrl\.org/2013/inlineXBRL",
                  "xbrli": r"http://www\.xbrl\.org/2003/instance",
                  "iso4217": r"http://www\.xbrl\.org/2003/iso4217",
                  "us-gaap": r"http://fasb\.org/us-gaap/\d{4}",
                  "dei": r"http://xbrl\.sec\.gov/dei/\d{4}"}
    for prefix, pattern in namespaces.items():
        attribute = f"xmlns:{prefix}"
        namespace = document.get(attribute, "")
        if (re.fullmatch(pattern, namespace) is None
                or any(n.get(attribute) not in {None, namespace} for n in document.iter())):
            return None
    identity = source_report_identity(document)
    if identity is None or identity[0] != report_period:
        return None
    report = date.fromisoformat(report_period)
    try:
        if not document_url.startswith(build_sec_archive_url(identity[1], accession)):
            return None
    except ValueError:
        return None
    ids: dict[str, Any] = {}
    for node in document.iter():
        identifier = node.get("id")
        if identifier:
            ids[identifier] = None if identifier in ids else node
    contexts, units = {}, {}
    for identifier, node in ids.items():
        if node is None:
            continue
        if _tag(node) == "xbrli:context":
            contexts[identifier] = _duration(node, identity[1])
        elif _tag(node) == "xbrli:unit":
            children = list(node)
            units[identifier] = "USD" if (len(children) == 1 and _tag(children[0]) == "xbrli:measure"
                                          and _text(children[0]) == "iso4217:USD") else None
    issuer_name = _single_dei(document, "dei:EntityRegistrantName", contexts, report_period)
    if not issuer_name or _single_dei(document, "dei:DocumentType", contexts, report_period) != "10-Q":
        return None
    candidates = [record for table in document.xpath("//table")
                  if (record := _table(table, document=document, report=report, issuer_name=issuer_name,
                                       contexts=contexts, units=units, ids=ids)) is not None]
    if len(candidates) != 1:
        return None
    current = candidates[0]["current"]
    # An explicit same-period component operand makes the narrow withholder
    # decline to classify this as an unverified aggregate/component substitution.
    # This is an exclusion from removal, never permission to reconstruct a claim.
    component_amounts = []
    for fact in document.iter():
        if (fact.get("name") != "us-gaap:GainLossOnSaleOfInvestments"
                or not fact.get("id") or ids.get(fact.get("id")) is not fact
                or contexts.get(fact.get("contextref")) != (current["start"], current["end"])):
            continue
        value = _fact_value(fact, units)
        if value is not None:
            component_amounts.append({"concept": fact.get("name"), "value": value[0],
                                      "fact_id": fact.get("id"), "context_id": fact.get("contextref"),
                                      "unit_id": fact.get("unitref")})
    return {"version": 1, "accession": accession, "document_url": document_url,
            "document_sha256": hashlib.sha256(source_html.encode()).hexdigest(),
            "issuer_cik": identity[1], "issuer_name": issuer_name, "period_of_report": report_period,
            "assertion_scope": "not_established", "use": "operand_match_for_withholding_only",
            "separate_investment_component_amounts": component_amounts,
            **candidates[0]}
