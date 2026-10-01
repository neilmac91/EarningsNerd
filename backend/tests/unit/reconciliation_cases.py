"""Frozen assessment inputs reused by the existing consumer-boundary gate."""

from copy import deepcopy
import json
from pathlib import Path

from lxml import html, etree

from app.services.edgar.statement_relationship_source import _cells, _text

RETAINED = json.loads(
    (Path(__file__).parents[1] / "fixtures/reconciliation_directions/retained-controls.json").read_text()
)
CONTROLS = {case["name"]: case for case in RETAINED["controls"]}


def mutate_source(text, kind):
    d = html.fromstring(text.encode(), parser=html.HTMLParser(no_network=True, encoding="utf-8"))
    t = [t for t in d.xpath("//table") if "Add (deduct):" in _text(t)][0]
    w = t.getparent()
    before = next((n for n in w.itersiblings(preceding=True) if _text(n)))
    after = [n for n in w.itersiblings() if _text(n)]

    def plain(node, text):
        for child in list(node):
            node.remove(child)
        node.text = text

    if kind.startswith("scope_"):
        rows = t.xpath("./tr|./tbody/tr")
        qualifier = "All adjustments below exclude amounts already included in net income."
        if kind == "scope_whitespace":
            before.tail = w.tail = after[0].tail = " \n\t"
        elif kind == "scope_after_heading":
            after[5].tail = qualifier
        elif kind == "scope_row5":
            plain(rows[5][1], qualifier)
        elif kind in {"scope_revenue_spacer", "scope_income_margin_spacer", "scope_ebitda_margin_spacer"}:
            row = rows[{"scope_revenue_spacer": 13, "scope_income_margin_spacer": 14,
                        "scope_ebitda_margin_spacer": 15}[kind]]
            plain(next(c for c in row if not _text(c)), qualifier)
        elif kind in {"scope_revenue_number", "scope_margin_number"}:
            plain(rows[13][2] if kind == "scope_revenue_number" else rows[14][1], qualifier)
        elif kind == "scope_label_gap":
            rows[7][0].set("colspan", "2")
            cell = html.Element("td", colspan="1")
            cell.text = qualifier
            rows[7].insert(1, cell)
        elif kind in {"scope_table_text", "scope_row_text", "scope_wrapper_text"}:
            node = {"scope_table_text": t, "scope_row_text": rows[5], "scope_wrapper_text": w}[kind]
            node.text = qualifier
        elif kind == "scope_blank_sibling_tail":
            node = html.Element("span")
            node.tail = qualifier
            w.addnext(node)
        else:
            node = {"scope_cell_tail": rows[5][0], "scope_table_tail": t, "scope_wrapper_tail": w,
                    "scope_intro_tail": before, "scope_note_tail": after[0],
                    "scope_toc_tail": next(n for n in before.itersiblings(preceding=True) if _text(n))}[kind]
            node.tail = qualifier
    elif kind in {"period_early", "period_late", "period_range_early", "period_range_late", "period_outside"}:
        start = {"period_early": "2026-03-31", "period_late": "2026-04-02",
                 "period_range_early": "2026-03-17", "period_range_late": "2026-04-15",
                 "period_outside": "2026-02-01"}[kind]
        context = next(n for n in d.iter() if n.get("id") == "c-10")
        next(n for n in context.iter() if n.tag == "xbrli:startdate").text = start
    elif kind in {"misparented_context", "nested_measure"}:
        if kind == "misparented_context":
            ctx = next((n for n in d.iter() if n.get("id") == "c-10"))
            ctx[0].append(ctx[1][0])
        else:
            unit = next((n for n in d.iter() if n.get("id") == "usd"))
            measure = unit[0]
            text = measure.text
            measure.text = None
            child = html.Element("span")
            child.text = text
            measure.append(child)
    elif kind.startswith(("root_", "local_")) or kind.startswith("unqualified_"):
        facts = [n for n in d.iter() if n.get("name") == "us-gaap:NetIncomeLoss"]
        dei = next((n for n in d.iter() if n.get("name") == "dei:DocumentPeriodEndDate"))
        ctx = next((n for n in d.iter() if n.get("id") == "c-10"))
        unit = next((n for n in d.iter() if n.get("id") == "usd"))
        prefix = kind.split("_", 1)[1]
        prefix = {"usgaap": "us-gaap", "currency": "iso4217", "transform": "ixt"}.get(prefix, prefix)
        if kind.startswith("root_"):
            d.set("xmlns:" + prefix, "urn:counterexample")
        elif kind.startswith("local_"):
            node = {"dei": dei, "us-gaap": facts[0], "ix": facts[0], "xbrli": ctx, "iso4217": unit, "ixt": facts[0]}[
                prefix
            ]
            node.set("xmlns:" + prefix, "urn:counterexample")
        elif kind == "unqualified_dei":
            dei.tag = "span"
        elif kind == "unqualified_fact":
            for n in facts:
                n.tag = "span"
        elif kind == "unqualified_context":
            ctx.tag = "context"
        elif kind == "unqualified_measure":
            for n in unit:
                n.tag = "measure"
    elif kind in {"rowspan", "amount_colspan"}:
        cell = next((c for c in t.xpath("./tr|./tbody/tr")[7].xpath("./td|./th") if _text(c) == "8,502"))
        cell.set("rowspan" if kind == "rowspan" else "colspan", "2" if kind == "rowspan" else "9")
    elif kind in {"hypothetical", "withdrawn", "denied", "foreign_entity", "foreign_currency"}:
        prefix = {
            "hypothetical": "Assume for illustration that ",
            "withdrawn": "Management withdrew the following disclosure: ",
            "denied": "It is false that ",
            "foreign_entity": "The Canadian subsidiary states: ",
            "foreign_currency": "The following amounts are in euros. ",
        }[kind]
        plain(before, prefix + _text(before))
    elif kind == "own_caption":
        c = html.Element("caption")
        c.text = "Withdrawn reconciliation; not reliable."
        t.insert(0, c)
    elif kind == "governing_predecessor":
        p = html.Element("p")
        p.text = "All figures in the following table belong to another entity."
        before.addprevious(p)
    elif kind == "global_hypothetical":
        p = html.Element("p")
        p.text = "Assume all of this document is an illustrative scenario."
        d.xpath("//body")[0].insert(0, p)
    elif kind == "global_withdrawn":
        p = html.Element("p")
        p.text = "The issuer subsequently withdrew this document in full."
        d.xpath("//body")[0].insert(0, p)
    elif kind == "duplicate_table":
        w.addnext(deepcopy(w))
    elif kind == "footer_condition":
        plain(after[2], _text(after[2])[:-1] + " only if subsequently approved.")
    elif kind == "extra_footnote":
        p = html.Element("p")
        p.text = "(6) All amounts are conditional estimates."
        after[4].addnext(p)
    elif kind == "unknown_descriptor":
        row = t.xpath("./tr|./tbody/tr")[7]
        plain(row.xpath("./td|./th")[0], "Provision for property taxes")
    elif kind in {"period_caption_geometry", "unit_caption_geometry"}:
        index = 1 if kind == "period_caption_geometry" else 3
        cell = next((c for c in t.xpath("./tr|./tbody/tr")[index].xpath("./td|./th") if _text(c)))
        cell.set("colspan", "3")
    elif kind == "ambiguous_period":
        for index, old, new in ((4, "7,099", "23,958"), (11, "19,727", "36,586")):
            for cell in t.xpath("./tr|./tbody/tr")[index].xpath("./td|./th"):
                if _text(cell) == old:
                    plain(cell, new)
    elif kind == "wrong_table_period":
        for cell in t.xpath("./tr|./tbody/tr")[1].xpath("./td|./th"):
            if _text(cell):
                plain(cell, _text(cell).replace("June", "March"))
    elif kind == "wrong_table_currency":
        for cell in t.xpath("./tr|./tbody/tr")[3].xpath("./td|./th"):
            if _text(cell):
                plain(cell, "(in thousands of euros, except margin)")
    elif kind == "anchor_currency":
        for n in d.iter():
            if isinstance(n.tag, str) and n.tag.lower().split(":")[-1] == "measure" and (_text(n) == "iso4217:USD"):
                plain(n, "iso4217:EUR")
    elif kind == "anchor_entity":
        for n in d.iter():
            if n.get("id") == "c-10":
                for item in n.iter():
                    if isinstance(item.tag, str) and item.tag.lower().split(":")[-1] == "identifier":
                        plain(item, "9999999")
    elif kind == "conflicting_anchor":
        facts = [n for n in d.iter() if n.get("name") == "us-gaap:NetIncomeLoss" and n.get("contextref") == "c-10"]
        plain(facts[0], "28,380")
    elif kind == "wrong_refund_period":
        plain(after[2], _text(after[2]).replace("2025", "2024"))
    elif kind == "bad_arithmetic":
        cell = next((c for c in t.xpath("./tr|./tbody/tr")[7].xpath("./td|./th") if _text(c) == "8,502"))
        plain(cell, "8,503")
    elif kind in {"all_zero", "mixed_zero"}:
        matrix = [_cells(r) for r in t.xpath("./tr|./tbody/tr")]
        rows = t.xpath("./tr|./tbody/tr")
        indices = (6, 7, 8, 9, 10) if kind == "all_zero" else (6,)
        for i in indices:
            for cell, desc in zip(rows[i].xpath("./td|./th"), matrix[i]):
                if 3 <= desc["column"] < 9 and _text(cell) not in {"", "$"}:
                    plain(cell, "0")
        total = "28,379" if kind == "all_zero" else "38,205"
        for cell in rows[11].xpath("./td|./th"):
            if _text(cell) == "36,586":
                plain(cell, total)
    elif kind == "synthetic_new_amounts":
        for fact in d.iter():
            if fact.get("name") == "us-gaap:NetIncomeLoss" and _text(fact) == "28,379":
                plain(fact, "28,380")
        for i, old, new in ((4, "28,379", "28,380"), (11, "36,586", "36,587")):
            for cell in t.xpath("./tr|./tbody/tr")[i].xpath("./td|./th"):
                if _text(cell) == old:
                    plain(cell, new)
    else:
        raise AssertionError(kind)
    return etree.tostring(d, encoding="unicode")
