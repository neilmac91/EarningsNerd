"""Bounded audited disclosures from an already parsed, selected primary document.

These are neutral tax/presentation disclosures, never operating classifications.
Missing supported roots are normal; malformed present roots fail preservation closed.
"""
from __future__ import annotations

from datetime import date
import re
from typing import Any

from .statement_relationship_source import _amount, _cells, _text

_TAX = "us-gaap:IncomeTaxDisclosureTextBlock"
_POLICY = "us-gaap:SignificantAccountingPoliciesTextBlock"
_CONCEPTS = (
    "CurrentFederalTaxExpenseBenefit", "CurrentForeignTaxExpenseBenefit", "CurrentIncomeTaxExpenseBenefit",
    "DeferredFederalIncomeTaxExpenseBenefit", "DeferredForeignIncomeTaxExpenseBenefit",
    "DeferredIncomeTaxExpenseBenefit", "IncomeTaxExpenseBenefit",
)


class _Unavailable(ValueError):
    """The supported source cannot establish a complete disclosure."""


def _tag(node: Any) -> str:
    return node.tag.lower().split(":")[-1] if isinstance(node.tag, str) else ""


def _unique(nodes: list) -> Any:
    if len(nodes) != 1:
        raise _Unavailable("ambiguous or missing source")
    return nodes[0]


def _context(ids: dict, context_id: str, entity: str, end: str) -> dict:
    node = _unique(ids.get(context_id, []))
    if _tag(node) != "context":
        raise _Unavailable("not a context")
    if any(_tag(n) in {"segment", "scenario", "explicitmember", "typedmember"} for n in node.iter()):
        raise _Unavailable("qualified context")
    identifier = _unique([n for n in node.iter() if _tag(n) == "identifier"])
    if _text(identifier) != entity or identifier.get("scheme") != "http://www.sec.gov/CIK":
        raise _Unavailable("entity mismatch")
    start = _text(_unique([n for n in node.iter() if _tag(n) == "startdate"]))
    actual_end = _text(_unique([n for n in node.iter() if _tag(n) == "enddate"]))
    if actual_end != end or not 320 <= (date.fromisoformat(end) - date.fromisoformat(start)).days <= 390:
        raise _Unavailable("period mismatch")
    return {"context_id": context_id, "entity": entity, "period_start": start, "period_end": end}


def _chain(root: Any, ids: dict, incoming: dict) -> list:
    result, seen = [], set()
    node = root
    while node is not None:
        ident = node.get("id")
        if not ident or ident in seen or len(result) >= 512 or len(ids.get(ident, [])) != 1:
            raise _Unavailable("broken continuation")
        seen.add(ident)
        if node.get("xsi:nil") or node.get("nil"):
            raise _Unavailable("nil disclosure")
        result.append(node)
        next_id = node.get("continuedat")
        if next_id:
            if incoming.get(next_id, 0) != 1:
                raise _Unavailable('shared continuation target')
        node = _unique(ids.get(next_id, [])) if next_id else None
        if node is not None and _tag(node) != "continuation":
            raise _Unavailable("invalid continuation target")
    return result


def _rate_note(chain: list, ids: dict, entity: str, report: date) -> dict | None:
    candidates = {n for part in chain for n in part.iter() if _tag(n) in {"div", "p"}
                  and not n.xpath(".//div|.//p|.//table")
                  and "consolidated effective tax rate" in _text(n).casefold()}
    if not candidates:
        return None
    paragraph = _unique(list(candidates))
    text = _text(paragraph)
    if len(text) > 1500 or not text.endswith("."):
        raise _Unavailable("incomplete rate disclosure")
    facts = [n for n in paragraph.iter() if _tag(n) == "nonfraction"]
    if len(facts) != 2:
        raise _Unavailable("incomplete rate facts")
    periods = {report.isoformat(), report.replace(year=report.year - 1).isoformat()}
    rates = []
    for fact in facts:
        if (fact.get("name") != "us-gaap:EffectiveIncomeTaxRateContinuingOperations"
                or fact.get("scale") != "-2" or fact.get("decimals") != "3"
                or fact.get("sign") or fact.get("continuedat") or fact.get("xsi:nil")
                or fact.get("format", "") not in {"", "ixt:num-dot-decimal"}
                or not re.fullmatch(r"\d+\.\d", _text(fact))):
            raise _Unavailable("unsupported rate fact")
        _unique(ids.get(fact.get("id"), []))
        node = _unique(ids.get(fact.get("contextref"), []))
        end = _text(_unique([n for n in node.iter() if _tag(n) == "enddate"]))
        if end not in periods:
            raise _Unavailable("rate period mismatch")
        context = _context(ids, fact.get("contextref"), entity, end)
        unit = _unique(ids.get(fact.get("unitref"), []))
        if _tag(unit) != "unit" or [_text(n) for n in unit.iter() if _tag(n) == "measure"] != ["xbrli:pure"]:
            raise _Unavailable("rate unit mismatch")
        rates.append({"fact_id": fact.get("id"), "concept": fact.get("name"),
                      "percent_lexical": _text(fact), "scale": -2, **context})
    if {r["period_end"] for r in rates} != periods:
        raise _Unavailable("missing comparative rate")
    return {"text": text, "path": paragraph.getroottree().getpath(paragraph), "facts": rates}


def _tax(chain: list, ids: dict, entity: str, report: date) -> dict:
    tables = {n for root in chain for n in root.iter() if _tag(n) == "table"
              and any(x.get("name") == "us-gaap:DeferredIncomeTaxExpenseBenefit" for x in n.iter())}
    table = _unique(list(tables))
    rows = table.xpath("./tr|./tbody/tr")
    matrix = [_cells(row) for row in rows]
    if any(c is None for c in matrix) or table.xpath('.//table'):
        raise _Unavailable("unsupported table")
    # Exact supported header/group layout; no table index or issuer selector.
    labels = [c[0]["text"] if c else "" for c in matrix]
    if len(rows) != 14 or labels[4:] != ["Income Tax:", "Current:", "U.S.", "Non-U.S.", "", "Deferred:", "U.S.", "Non-U.S.", "", "Income tax expense"]:
        raise _Unavailable("incomplete tax groups")
    if [c['text'] for c in matrix[1] if c['text']] != [f"Year Ended {report.strftime('%B')} {report.day},"]:
        raise _Unavailable("missing period header")
    if [c['text'] for c in matrix[3] if c['text']] != ["(In millions)"]:
        raise _Unavailable("missing unit header")
    headers = [c for c in matrix[2] if c['text']]
    if [c['text'] for c in headers] != [str(report.year - i) for i in range(3)]:
        raise _Unavailable("column years")
    width = max(c['column'] + c['colspan'] for row in matrix for c in row)
    numeric_rows = [6, 7, 8, 10, 11, 12, 13]
    all_facts = [n for n in table.iter() if _tag(n) == "nonfraction"]
    if len(all_facts) != 21:
        raise _Unavailable("extra/missing numeric facts")
    columns = []
    for j, header in enumerate(headers):
        year = report.year - j
        end = report.replace(year=year).isoformat()
        first, last = header['column'], headers[j + 1]['column'] if j < 2 else width
        values = []
        for row_index, concept in zip(numeric_rows, _CONCEPTS):
            amount = _amount(matrix[row_index], first, last, 1_000_000)
            if amount is None:
                raise _Unavailable("invalid displayed amount")
            nodes = [n for n in rows[row_index].iter() if _tag(n) == "nonfraction"]
            if len(nodes) != 3:
                raise _Unavailable("missing column fact")
            fact = nodes[j]
            if not fact.get('id') or len(ids.get(fact.get('id'), [])) != 1:
                raise _Unavailable('ambiguous fact identity')
            if fact.get("name") != "us-gaap:" + concept or fact.get("scale") != "6" or fact.get("decimals") != "-6":
                raise _Unavailable("concept or scale mismatch")
            if fact.get("continuedat") or fact.get("xsi:nil") or fact.get("nil") or fact.get("sign", "") not in {"", "-"}:
                raise _Unavailable("unsupported fact")
            if fact.get("format", "") not in {"", "ixt:num-dot-decimal"}:
                raise _Unavailable("unsupported number format")
            lexical = _text(fact)
            if not re.fullmatch(r"\d{1,3}(?:,\d{3})+|\d+", lexical):
                raise _Unavailable("unsupported numeric text")
            value = int(lexical.replace(',', '')) * 1_000_000 * (-1 if fact.get('sign') == '-' else 1)
            if value != amount['value']:
                raise _Unavailable("displayed sign or amount differs")
            # Ensure the tagged fact belongs to this header's actual cell group.
            cells = rows[row_index].xpath('./td|./th')
            owner = next((i for i, c in enumerate(cells) if fact in c.iter()), None)
            if owner is None or not first <= matrix[row_index][owner]['column'] < last:
                raise _Unavailable("fact outside selected column")
            unit = _unique(ids.get(fact.get('unitref'), []))
            if _tag(unit) != 'unit' or [_text(n) for n in unit.iter() if _tag(n) == 'measure'] != ['iso4217:USD'] or any(_tag(n) == 'divide' for n in unit.iter()):
                raise _Unavailable("unknown currency")
            context = _context(ids, fact.get('contextref'), entity, end)
            values.append({"concept": 'us-gaap:' + concept, "value": value,
                           "fact_id": fact.get('id'), "row": row_index, **context})
        amounts = [v['value'] for v in values]
        if amounts[0] + amounts[1] != amounts[2] or amounts[3] + amounts[4] != amounts[5] or amounts[2] + amounts[5] != amounts[6]:
            raise _Unavailable("tax subtotal mismatch")
        if len({v['period_start'] for v in values}) != 1:
            raise _Unavailable("mixed annual durations")
        columns.append({"year": year, "rows": values})
    current = columns[0]['rows']
    def formatted(value: int) -> str:
        number = f"{abs(value) // 1_000_000:,}"
        return f"({number})" if value < 0 else number
    text = (f"Income-tax disclosure, year ended {report.isoformat()} (USD millions): "
            f"current income tax expense/(benefit) {formatted(current[2]['value'])}; "
            f"deferred income tax expense/(benefit) {formatted(current[5]['value'])}; "
            f"income tax expense/(benefit) {formatted(current[6]['value'])}.")
    prior_expense = columns[1]['rows'][6]['value']
    text += f" Prior-year income tax expense/(benefit), {report.year - 1}: {formatted(prior_expense)}."
    rate_note = _rate_note(chain, ids, entity, report)
    if rate_note:
        text += " Filing disclosure: " + rate_note["text"]
    return {"text": text, "rate_note": rate_note,
            "rate_status": "validated" if rate_note else "no_supported_rate_paragraph",
            "table_path": table.getroottree().getpath(table),
            "currency": "USD", "scale": 1_000_000, "columns": columns}


def _presentation(chain: list) -> dict | None:
    headings = [n for root in chain for n in root.iter() if _tag(n) in {'div', 'p'}
                and not n.xpath('.//div|.//p|.//table')
                and re.fullmatch(r'Reclassification of \d{4} results', _text(n))]
    if not headings:
        return None
    heading = _unique(headings)
    # The subsection continues across an inline-XBRL page boundary. Its next
    # block must be the complete recast-table introduction followed by that
    # table; an intervening caveat must never be silently omitted.
    owner = heading.getparent()
    if owner not in chain or chain.index(owner) + 1 >= len(chain):
        raise _Unavailable('missing following continuation boundary')
    following = [n for n in chain[chain.index(owner) + 1] if _text(n)]
    if (len(following) < 2 or following[0].xpath('.//div|.//p|.//table')
            or not _text(following[0]).startswith('The following table, recast for the changes summarized above, ')
            or not _text(following[0]).endswith(':')
            or len(_text(following[0])) > 1000
            or len(following[1].xpath('.//table')) != 1):
        raise _Unavailable('unpreserved cross-continuation disclosure')
    siblings = [n for n in heading.itersiblings() if _text(n)]
    if len(siblings) != 2:
        raise _Unavailable('incomplete presentation subsection')
    paragraphs = [_text(n) for n in siblings]
    if any(_tag(n) not in {'div', 'p'} or n.xpath('.//div|.//p|.//table') for n in siblings):
        raise _Unavailable('nonparagraph disclosure')
    year = re.search(r'\d{4}', _text(heading))[0]
    if (not paragraphs[0].startswith('According to the Accounting Standards Codification')
            or f'{year} results have been reclassified' not in paragraphs[0]
            or not paragraphs[1].startswith('This reclassification did not have an impact on previously reported ')
            or any(not p.endswith('.') for p in paragraphs)
            or sum(map(len, paragraphs)) > 1500):
        raise _Unavailable('unsupported complete disclosure')
    return {'heading': _text(heading), 'paragraphs': paragraphs,
            'paths': [n.getroottree().getpath(n) for n in [heading, *siblings]],
            'text': 'Filing disclosure — ' + _text(heading) + ': ' + ' '.join(paragraphs)}


def extract_statement_disclosures(root: Any, *, accession: str, document_url: str,
                                 report_period: str, source_sha256: str,
                                 entity_identifier: str) -> dict | None:
    """Supplied identity is the caller's validated source binding; never refetch HTML."""
    try:
        report = date.fromisoformat(report_period)
        if (not accession or not document_url or not re.fullmatch(r'[0-9a-f]{64}', source_sha256)
                or not re.fullmatch(r'\d{10}', entity_identifier)):
            return None
        ids: dict[str, list] = {}
        incoming: dict[str, int] = {}
        for node in root.iter():
            if node.get('continuedat'):
                target = node.get('continuedat')
                incoming[target] = incoming.get(target, 0) + 1
            if node.get('id'):
                ids.setdefault(node.get('id'), []).append(node)
        result = {'tax_disclosure': None, 'presentation_disclosure': None,
                  'status': {'tax_disclosure': 'no_supported_root', 'presentation_disclosure': 'no_supported_root'}}
        for concept, key in [(_TAX, 'tax_disclosure'), (_POLICY, 'presentation_disclosure')]:
            matches = [n for n in root.iter() if n.get('name') == concept]
            if not matches:
                continue
            node = _unique(matches)
            context = _context(ids, node.get('contextref'), entity_identifier, report_period)
            chain = _chain(node, ids, incoming)
            # Either the exact audited heading or complete concept vocabulary
            # declares the supported layout. Losing only one signal cannot hide
            # malformed supported content. Other tax layouts stay unavailable.
            def declared_table(table):
                labels = {_text(row[0]) for row in table.xpath('./tr|./tbody/tr') if len(row)}
                concepts = {n.get('name') for n in table.iter()}
                return ({'Income Tax:', 'Current:', 'Deferred:', 'U.S.', 'Non-U.S.'}.issubset(labels)
                        and {'us-gaap:' + c for c in _CONCEPTS}.issubset(concepts))
            supported = (_text(node) == 'INCOME TAXES'
                         or any(declared_table(n) for part in chain for n in part.iter() if _tag(n) == 'table'))
            if key == 'tax_disclosure' and not supported:
                result['status'][key] = 'unsupported_layout'
                continue
            record = _tax(chain, ids, entity_identifier, report) if key == 'tax_disclosure' else _presentation(chain)
            result['status'][key] = 'validated' if record is not None else 'no_supported_subsection'
            if record is not None:
                result[key] = {**record, **context, 'accession': accession, 'document_url': document_url,
                               'source_sha256': source_sha256, 'root_concept': concept,
                               'root_id': node.get('id')}
        return result
    except (ValueError, TypeError, AttributeError, KeyError, StopIteration):
        return None
