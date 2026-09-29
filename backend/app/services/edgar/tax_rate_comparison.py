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
_NAMESPACES = {
    "ix": r"http://www\.xbrl\.org/2013/inlineXBRL",
    "xbrli": r"http://www\.xbrl\.org/2003/instance",
    "us-gaap": r"http://fasb\.org/us-gaap/[0-9]{4}",
    "dei": r"http://xbrl\.sec\.gov/dei/[0-9]{4}",
    "ixt": r"http://www\.xbrl\.org/inlineXBRL/transformation/2020-02-12",
}


def _qualified_tag(node: Any) -> str:
    return node.tag.lower() if isinstance(node.tag, str) else ""


def _namespaces_valid(document: Any) -> bool:
    # HTML parsing retains lexical prefixes rather than expanded XML QNames.
    # Validate their bindings before interpreting those names, including local rebindings.
    for prefix, pattern in _NAMESPACES.items():
        attribute = f"xmlns:{prefix}"
        namespace = document.get(attribute, "")
        if (re.fullmatch(pattern, namespace) is None
                or any(n.get(attribute) not in {None, namespace} for n in document.iter())):
            return False
    return True


def _duration(ids: dict, ident: str, issuer: str) -> tuple[date, date]:
    context = _unique(ids.get(ident, []))
    children = list(context)
    if (_qualified_tag(context) != "xbrli:context"
            or [_qualified_tag(n) for n in children] != ["xbrli:entity", "xbrli:period"]
            or [_qualified_tag(n) for n in children[0]] != ["xbrli:identifier"]
            or [_qualified_tag(n) for n in children[1]] != ["xbrli:startdate", "xbrli:enddate"]
            or any(len(n) for n in [children[0][0], *children[1]])):
        raise _Unavailable("unsupported qualified context structure")
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


def prior_year_period_end(end: date) -> date:
    """Preserve the calendar month-end convention across either leap boundary."""
    return date(end.year - 1, end.month, monthrange(end.year - 1, end.month)[1])


def select_tax_rate_comparison(document: Any) -> dict | None:
    """Return source selectors only, or None for unsupported/ambiguous structure."""
    if document is None or not _namespaces_valid(document):
        return None
    try:
        identity = source_report_identity(document)
        if identity is None:
            return None
        report_text, issuer = identity
        report = date.fromisoformat(report_text)
        prior = prior_year_period_end(report)
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
                if _qualified_tag(node) != "ix:nonnumeric" or _duration(ids, node.get("contextref"), issuer)[1] != report:
                    raise _Unavailable("DEI duration mismatch")
        root = _unique(roots)
        if _qualified_tag(root) != "ix:nonnumeric" or _duration(ids, root.get("contextref"), issuer)[1] != report:
            raise _Unavailable("tax-root identity mismatch")
        if incoming.get(root.get("id"), 0):
            raise _Unavailable("tax root is a continuation target")
        chain = _chain(root, ids, incoming)
        if any(_qualified_tag(part) != "ix:continuation" for part in chain[1:]):
            raise _Unavailable("unsupported continuation namespace")
        if any(_tag(n) in {"exclude", "table"} for part in chain for n in part.iter()):
            raise _Unavailable("unsupported note layout")
        rates = []
        for part in chain:
            for fact in part.iter():
                if fact.get("name") != "us-gaap:EffectiveIncomeTaxRateContinuingOperations":
                    continue
                if (_qualified_tag(fact) != "ix:nonfraction" or not fact.get("id")
                        or len(ids.get(fact.get("id"), [])) != 1
                        or fact.get("scale") != "-2" or fact.get("decimals") != "3"
                        or any(fact.get(key) for key in ("sign", "continuedat", "xsi:nil", "nil"))
                        or fact.get("format", "") not in {"", "ixt:num-dot-decimal"}
                        or not re.fullmatch(RATE_LEXEME, _text(fact))):
                    raise _Unavailable("unsupported rate fact")
                duration = _duration(ids, fact.get("contextref"), issuer)
                unit = _unique(ids.get(fact.get("unitref"), []))
                if (_qualified_tag(unit) != "xbrli:unit"
                        or [_qualified_tag(n) for n in unit] != ["xbrli:measure"]
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
