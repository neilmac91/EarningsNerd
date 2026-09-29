"""Complete tagged tax-note operands, with no assertion or causal authority.

This selector is separate from the annual audited-disclosure contract. A complete
inline chain does not establish whether its prose is affirmative or withdrawn.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date
import re
from typing import Any

from .statement_context import source_context_identity, source_report_identity
from .statement_disclosures import _chain, _tag, _Unavailable, _unique
from .statement_relationship_source import _text

RATE_LEXEME = r"[0-9]{1,3}\.[0-9]"


def _duration(ids: dict, ident: str, issuer: str) -> tuple[date, date]:
    context = _unique(ids.get(ident, []))
    identity = source_context_identity(context)
    if _tag(context) != "context" or identity is None or identity[0] != issuer or identity[1] != "duration" or identity[3]:
        raise _Unavailable("unqualified same-issuer duration required")
    start, end = [date.fromisoformat(_text(_unique([n for n in context.iter() if _tag(n) == tag])))
                  for tag in ("startdate", "enddate")]
    if not 0 < (end - start).days <= 366:
        raise _Unavailable("invalid complete duration")
    return start, end


def quarter_start(end: date) -> date:
    """Exact three-calendar-month duration; no inference from a fiscal label."""
    if end.day != monthrange(end.year, end.month)[1]:
        raise _Unavailable("unsupported period end")
    month = end.year * 12 + end.month - 3
    year, month_zero = divmod(month, 12)
    return date(year, month_zero + 1, 1)


def select_tax_rate_comparison(document: Any) -> dict | None:
    """Return source selectors only, or None for unsupported/ambiguous structure."""
    if document is None:
        return None
    try:
        identity = source_report_identity(document)
        if identity is None:
            return None
        report_text, issuer = identity
        report = date.fromisoformat(report_text)
        prior = report.replace(year=report.year - 1)
        expected = {(quarter_start(end), end) for end in (report, prior)}
        ids: dict[str, list] = {}
        incoming: dict[str, int] = {}
        roots = []
        for node in document.iter():
            if node.get("id"):
                ids.setdefault(node.get("id"), []).append(node)
            if node.get("continuedat"):
                target = node.get("continuedat")
                incoming[target] = incoming.get(target, 0) + 1
            if node.get("name") == "us-gaap:IncomeTaxDisclosureTextBlock":
                roots.append(node)
        # Check complete DEI durations as well as its identity helper's period shape.
        for node in document.iter():
            if (node.get("name") or "").lower() == "dei:documentperiodenddate":
                if _duration(ids, node.get("contextref"), issuer)[1] != report:
                    raise _Unavailable("DEI duration mismatch")
        root = _unique(roots)
        if _tag(root) != "nonnumeric" or _duration(ids, root.get("contextref"), issuer)[1] != report:
            raise _Unavailable("tax-root identity mismatch")
        chain = _chain(root, ids, incoming)
        if any(_tag(n) in {"exclude", "table"} for part in chain for n in part.iter()):
            raise _Unavailable("unsupported note layout")
        rates = []
        for part in chain:
            for fact in part.iter():
                if fact.get("name") != "us-gaap:EffectiveIncomeTaxRateContinuingOperations":
                    continue
                if (_tag(fact) != "nonfraction" or not fact.get("id")
                        or len(ids.get(fact.get("id"), [])) != 1
                        or fact.get("scale") != "-2" or fact.get("decimals") != "3"
                        or any(fact.get(key) for key in ("sign", "continuedat", "xsi:nil", "nil"))
                        or fact.get("format", "") not in {"", "ixt:num-dot-decimal"}
                        or not re.fullmatch(RATE_LEXEME, _text(fact))):
                    raise _Unavailable("unsupported rate fact")
                duration = _duration(ids, fact.get("contextref"), issuer)
                unit = _unique(ids.get(fact.get("unitref"), []))
                if (_tag(unit) != "unit" or [_tag(n) for n in unit if isinstance(n.tag, str)] != ["measure"]
                        or _text(unit[0]) != "xbrli:pure" or len(unit[0])):
                    raise _Unavailable("rate unit mismatch")
                if duration in expected:
                    rates.append({"fact_id": fact.get("id"), "context_id": fact.get("contextref"),
                                  "period_start": duration[0].isoformat(), "period_end": duration[1].isoformat(),
                                  "percent_lexical": _text(fact)})
        if len(rates) != 2 or {r["period_end"] for r in rates} != {report_text, prior.isoformat()}:
            raise _Unavailable("ambiguous or missing quarterly operands")
        paragraphs = [_text(n) for part in chain for n in part.iter()
                      if _tag(n) in {"div", "p"} and not n.xpath(".//div|.//p|.//table")]
        return {"assertion_scope": "not_established", "issuer": issuer, "report_end": report_text,
                "root_id": root.get("id"), "chain_ids": [part.get("id") for part in chain],
                "text": " ".join(_text(part) for part in chain), "paragraphs": paragraphs, "rates": rates}
    except (ValueError, TypeError, OverflowError):
        return None
