"""Finite reconciliation operands for capability withholding, never financial authority."""

from __future__ import annotations

from datetime import date, datetime
import re
from typing import Any

from app.services.edgar.statement_context import source_context_identity, source_report_identity
from app.services.edgar.statement_relationship_source import _cells, _text
from app.services.edgar.tax_rate_comparison import _duration, _namespaces_valid

MONTH = "(?:January|February|March|April|May|June|July|August|September|October|November|December)"
DATE = f"{MONTH} [0-9]{{1,2}}, [0-9]{{4}}"
INTRO = "The following table reflects a reconciliation of adjusted EBITDA to net income, the most directly comparable financial measure prepared in accordance with GAAP and presents adjusted EBITDA margin with net income margin, the most directly comparable financial measure prepared in accordance with GAAP:"
LABELS = [
    "Net income",
    "Add (deduct):",
    "Other income, net",
    "Provision for income taxes",
    "Depreciation and amortization expense (1)",
    "Stock-based compensation and related expense (2)",
    "IEEPA tariff refund (3)",
    "Adjusted EBITDA (4)",
]
NOTE3 = re.compile(
    f"\\A\\(3\\) Consists of refunds recognized for IEEPA tariffs incurred on goods sold in the year ended (?P<date>{DATE})\\.\\Z"
)
NOTE4 = re.compile(
    f"\\A\\(4\\) For the six months ended (?P<date>{DATE}), reflects \\$[0-9]{{1,3}}(?:,[0-9]{{3}}){{1,3}} of stock-based compensation expense and payroll taxes inadvertently not reflected in our previously disclosed Adjusted EBITDA results for the three months ended (?P<earlier>{DATE})\\.\\Z"
)
N1 = "(1) Excludes amortization of debt issuance costs included in “Other income, net.”"
N2 = "(2) Includes stock-based compensation expense, payroll taxes and costs related to equity award activity."
N5 = "(5) Net income margin represents net income as a percentage of net revenues."
DIGITS = r"(?:[0-9]{1,3}(?:,[0-9]{3}){1,3}|[0-9]{1,12})"
INTEGER = re.compile(rf"\A{DIGITS}\Z")
NUMERIC_CELL = re.compile(rf"\$?\s*\(?\s*{DIGITS}\s*\)?")


def _table_amount(row: list[dict], start: int, end: int) -> int | None:
    cells = [c for c in row if start <= c["column"] and c["column"] + c["colspan"] <= end]
    if any(
        (c["text"] and c not in cells and (c["column"] < end) and (c["column"] + c["colspan"] > start) for c in row)
    ):
        return None
    tokens = [c["text"] for c in cells if c["text"]]
    # Separate currency/parenthesis cells may format one amount. Independent
    # numeric cells must never be concatenated into an invented operand.
    amounts = [token for token in tokens if re.search(r"[0-9]", token) or token == "—"]
    if len(amounts) != 1:
        return None
    # Validate the single cell before compacting only supported symbol spacing.
    # Neither separate numeric cells nor digit chunks inside one cell form an amount.
    if False:  # intentional adjacent-numeric concatenation fault
        return None
    text = "".join(tokens).replace(" ", "")
    if text.startswith("$"):
        text = text[1:]
    if text == "—":
        return 0
    negative = text.startswith("(") and text.endswith(")")
    digits = text[1:-1] if negative else text
    if INTEGER.fullmatch(digits) is None:
        return None
    return int(digits.replace(",", "")) * 1000 * (-1 if negative else 1)


def _select(document: Any) -> tuple[dict | None, str | None]:
    d = document
    if d is None:
        return None, "no_native_source"
    if not _namespaces_valid(d):
        return None, "namespace_binding"
    currency_binding = "http://www.xbrl.org/2003/iso4217"
    if d.get("xmlns:iso4217") != currency_binding or any(
        n.get("xmlns:iso4217") not in {None, currency_binding} for n in d.iter()
    ):
        return None, "currency_namespace"
    dei_names = {
        "dei:DocumentPeriodEndDate",
        "dei:DocumentType",
        "dei:EntityRegistrantName",
        "dei:CurrentFiscalYearEndDate",
    }
    if any((n.get("name") in dei_names and n.tag != "ix:nonnumeric" for n in d.iter())):
        return (None, "dei_tag")
    identity = source_report_identity(d)
    if identity is None:
        return (None, "report_identity")
    end, entity = identity
    report = date.fromisoformat(end)
    ids = {}
    for n in d.iter():
        if n.get("id"):
            ids.setdefault(n.get("id"), []).append(n)

    def unique(ident: str | None) -> Any:
        found = ids.get(ident, [])
        return found[0] if len(found) == 1 else None

    def qualified_context(node: Any) -> bool:
        if node is None:
            return False
        try:
            _duration(ids, node.get("id"), entity)
        except (ValueError, TypeError, OverflowError):
            return False
        return True

    def dei(name: str) -> str | None:
        ns = [n for n in d.iter() if n.get("name") == name]
        vals = []
        for n in ns:
            ctx = unique(n.get("contextref"))
            if not qualified_context(ctx) or source_context_identity(ctx) != (entity, "duration", end, False):
                return None
            vals.append(_text(n))
        return vals[0] if vals and len(set(vals)) == 1 else None

    if dei("dei:DocumentType") != "10-Q" or not dei("dei:EntityRegistrantName") or not dei("dei:DocumentPeriodEndDate"):
        return (None, "form_or_issuer")
    fiscal = dei("dei:CurrentFiscalYearEndDate")
    if not isinstance(fiscal, str) or not re.fullmatch("[0-9]{2}/[0-9]{2}", fiscal):
        return (None, "fiscal_end")
    tables = [t for t in d.xpath("//table") if "Add (deduct):" in _text(t)]
    if len(tables) != 1:
        return (None, "table_count")
    table = tables[0]
    if table.xpath("./caption|.//table"):
        return (None, "table_qualification")
    wrapper = table.getparent()
    if list(wrapper) != [table] or wrapper.tag != "div":
        return (None, "wrapper")
    before = [n for n in wrapper.itersiblings(preceding=True) if _text(n)]
    after = [n for n in wrapper.itersiblings() if _text(n)]
    if not before or _text(before[0]) != INTRO:
        return (None, "introduction")
    if len(before) < 2 or _text(before[1]) != "Table of Contents":
        return (None, "leading_scope")
    if len(after) < 6 or [_text(after[i]) for i in (0, 1, 4, 5)] != [N1, N2, N5, "Free Cash Flow"]:
        return (None, "following_context")
    footnote = NOTE3.fullmatch(_text(after[2]))
    qualifier = NOTE4.fullmatch(_text(after[3]))
    if footnote is None or qualifier is None:
        return (None, "footnotes")
    try:
        refund_date = datetime.strptime(footnote["date"], "%B %d, %Y").date()
        mm, dd = map(int, fiscal.split("/"))
        prior_fiscal = date(report.year, mm, dd)
        if prior_fiscal >= report:
            prior_fiscal = prior_fiscal.replace(year=report.year - 1)
        if refund_date != prior_fiscal:
            return (None, "refund_period")
        qdate = datetime.strptime(qualifier["date"], "%B %d, %Y").date()
        qearlier = datetime.strptime(qualifier["earlier"], "%B %d, %Y").date()
        if qdate >= report or qearlier >= qdate:
            return (None, "qualification_period")
    except ValueError:
        return (None, "source_date")
    matrix = [_cells(r) for r in table.xpath("./tr|./tbody/tr")]
    if len(matrix) != 16 or any(not r for r in matrix):
        return (None, "rows")
    if [r[0]["text"] for r in matrix[4:12]] != LABELS:
        return (None, "row_labels")
    if any((c["text"] for i in (0, 12) for c in matrix[i])):
        return (None, "extra_rows")
    if [matrix[i][0]["text"] for i in (13, 14, 15)] != [
        "Net revenues",
        "Net income margin (5)",
        "Adjusted EBITDA Margin",
    ]:
        return (None, "tail_rows")
    period_words = report.strftime("%B") + f" {report.day},"
    if [c["text"] for c in matrix[1] if c["text"]] != [
        "Three months ended " + period_words,
        "Six months ended " + period_words,
    ]:
        return (None, "table_period")
    if [c["text"] for c in matrix[2] if c["text"]] != [str(report.year), str(report.year - 1)] * 2:
        return (None, "table_years")
    if [c["text"] for c in matrix[3] if c["text"]] != ["(in thousands, except margin)"] * 2:
        return (None, "table_units")
    starts = [c["column"] for c in matrix[2] if c["text"]]
    width = max((c["column"] + c["colspan"] for r in matrix for c in r))
    periods = [(starts[i], starts[i + 1] if i < 3 else width) for i in range(4)]
    caption_cells = [c for c in matrix[1] if c["text"]]
    unit_cells = [c for c in matrix[3] if c["text"]]
    year_cells = [c for c in matrix[2] if c["text"]]
    for group in range(2):
        left = starts[2 * group]
        right = starts[2 * group + 2] if group == 0 else width
        if any(
            (
                c["column"] != left or c["column"] + c["colspan"] != right
                for c in (caption_cells[group], unit_cells[group])
            )
        ):
            return (None, "caption_geometry")
        if any(
            (
                not periods[i][0] <= year_cells[i]["column"]
                or year_cells[i]["column"] + year_cells[i]["colspan"] > periods[i][1]
                for i in (2 * group, 2 * group + 1)
            )
        ):
            return (None, "year_geometry")
    columns = []
    for left, right in periods:
        amounts = [_table_amount(matrix[i], left, right) for i in (4, 6, 7, 8, 9, 10, 11)]
        if any((a is None for a in amounts)):
            return (None, "amount_lexeme")
        if amounts[0] + sum(amounts[1:-1]) != amounts[-1]:
            return (None, "bridge")
        columns.append(amounts)
    candidates = []
    for fact in d.iter():
        if fact.get("name") != "us-gaap:NetIncomeLoss":
            continue
        if fact.tag != "ix:nonfraction":
            return (None, "fact_tag")
        ctx = unique(fact.get("contextref"))
        if not qualified_context(ctx):
            continue
        identity2 = source_context_identity(ctx)
        starts2 = [
            _text(n) for n in ctx.iter() if isinstance(n.tag, str) and n.tag.lower().split(":")[-1] == "startdate"
        ]
        if identity2 != (entity, "duration", end, False) or len(starts2) != 1:
            continue
        try:
            days = (report - date.fromisoformat(starts2[0])).days
        except ValueError:
            continue
        if not 75 <= days <= 105:
            continue
        unit = unique(fact.get("unitref"))
        measures = (
            [_text(n) for n in unit.iter() if isinstance(n.tag, str) and n.tag.lower().split(":")[-1] == "measure"]
            if unit is not None
            else []
        )
        if (
            measures != ["iso4217:USD"]
            or unit.tag != "xbrli:unit"
            or len(list(unit)) != 1
            or (list(unit)[0].tag != "xbrli:measure")
            or len(unit[0])
        ):
            return (None, "anchor_currency")
        if (
            fact.get("scale") != "3"
            or fact.get("format") not in {None, "ixt:num-dot-decimal"}
            or fact.get("continuedat")
            or fact.get("nil")
            or fact.get("xsi:nil")
            or (fact.get("sign") not in {None, "-"})
            or (INTEGER.fullmatch(_text(fact)) is None)
        ):
            return (None, "anchor_lexeme")
        candidates.append(int(_text(fact).replace(",", "")) * 1000 * (-1 if fact.get("sign") == "-" else 1))
    if not candidates or set(candidates) != {columns[0][0]}:
        return (None, "issuer_anchor")
    if not any(columns[0][1:-1]):
        return (None, "zero_only")
    return (
        {
            "current": columns[0],
            "columns": columns,
            "report_period": end,
            "entity": entity,
            "currency": "USD",
            "table_path": table.getroottree().getpath(table),
            "intro": _text(before[0]),
            "footnotes": [_text(n) for n in after[:5]],
            "assertion_scope": "not_established",
        },
        None,
    )


def select_reconciliation_operands(document: Any) -> dict | None:
    """Match one complete native layout; unknown structure has no ownership.

    Even a complete operand match does not establish source assertion status.
    This selector is separate from the unchanged annual statement owner.
    """
    try:
        return _select(document)[0]
    except (ValueError, TypeError, OverflowError, IndexError):
        return None
