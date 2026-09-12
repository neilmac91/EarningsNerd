"""Source descriptors for the already selected financing cash-flow operands.

No transport, alternate selection or arithmetic lives here. Parsed SDK dimensions are incomplete
for scenario contexts, so eligibility also requires the original, already cached instance XML.
"""
from datetime import date
import math
from typing import Any

from lxml import etree

_X = "{http://www.xbrl.org/2003/instance}"
_ISO_CURRENCY = "http://www.xbrl.org/2003/iso4217"
_CIK_SCHEME = "http://www.sec.gov/CIK"
_FINANCING_CONCEPTS = {
    "us-gaap:NetCashProvidedByUsedInFinancingActivities",
    "us-gaap:NetCashProvidedByUsedInFinancingActivitiesContinuingOperations",
    "ifrs-full:CashFlowsFromUsedInFinancingActivities",
}


def _cached_instance(filing: Any) -> str | None:
    """Use only objects populated by the preceding filing.xbrl() call; never lazy-download."""
    sgml = getattr(filing, "__dict__", {}).get("_sgml")
    attachments = getattr(sgml, "__dict__", {}).get("attachments")
    if attachments is None:
        return None
    selected = None
    for attachment in attachments.data_files or []:
        if (attachment.document_type not in {"XML", "EX-101.INS"}
                or not attachment.extension.endswith((".xml", ".XML"))):
            continue
        document = getattr(attachment, "sgml_document", None)
        if document is None:
            return None  # Attachment.content's other branch would download.
        content = document.content
        # Match the installed SDK's instance attachment selection, including last-match wins.
        if isinstance(content, str) and "<xbrl" in content[:2000]:
            selected = content
    return selected


def _unique_elements(root: Any, tag: str) -> dict[str, Any]:
    indexed: dict[str, Any] = {}
    for element in root.findall(f"{_X}{tag}"):
        key = element.get("id")
        if not key or key in indexed:
            raise ValueError("missing or duplicate source identity")
        indexed[key] = element
    return indexed


def _point(source: dict, contexts: dict, units: dict, cik: str) -> dict | None:
    value, currency, concept = source["value"], source["currency"], source["raw_tag"]
    start, end = source["period_start"], source["period_end"]
    if (isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value)
            or concept not in _FINANCING_CONCEPTS or not isinstance(currency, str)
            or len(currency) != 3 or not currency.isalpha() or currency != currency.upper()
            or not isinstance(start, str) or not isinstance(end, str)
            or date.fromisoformat(start) >= date.fromisoformat(end)):
        return None
    refs = set()
    entities = set()
    if not source["rows"]:
        return None
    for row in source["rows"]:
        ref = row.get("context_ref")
        context = contexts.get(ref)
        unit = units.get(row.get("unit_ref"))
        if context is None or unit is None:
            return None
        # No scenario or segment (including non-dimensional qualifiers), and no unknown children.
        if sorted(child.tag for child in context) != sorted([f"{_X}entity", f"{_X}period"]):
            return None
        entity, period = context.find(f"{_X}entity"), context.find(f"{_X}period")
        if [child.tag for child in entity] != [f"{_X}identifier"]:
            return None
        identifier = entity[0]
        entity_id, scheme = identifier.text, identifier.get("scheme")
        if (scheme != _CIK_SCHEME or not isinstance(entity_id, str) or not entity_id.isdigit()
                or not cik.isdigit() or int(entity_id) != int(cik)
                or row.get("entity_identifier") != entity_id or row.get("entity_scheme") != scheme):
            return None
        if sorted(child.tag for child in period) != sorted([f"{_X}startDate", f"{_X}endDate"]):
            return None
        if (period.findtext(f"{_X}startDate") != start or period.findtext(f"{_X}endDate") != end
                or str(row.get("period_start"))[:10] != start
                or str(row.get("period_end"))[:10] != end
                or row.get("concept") != concept or row.get("currency") != currency):
            return None
        if len(unit) != 1 or unit[0].tag != f"{_X}measure":
            return None
        measure = unit[0]
        prefix, separator, local = (measure.text or "").partition(":")
        if not separator or measure.nsmap.get(prefix) != _ISO_CURRENCY or local != currency:
            return None
        refs.add(ref)
        entities.add((entity_id, scheme))
    if len(entities) != 1:
        return None
    entity_id, scheme = next(iter(entities))
    return {"value": value, "period_start": start, "period_end": end, "currency": currency,
            "raw_tag": concept, "entity_identifier": entity_id, "entity_scheme": scheme,
            "context_refs": sorted(refs), "scope": "issuer_undimensioned"}


def financing_comparison_source(filing: Any, selected: list[dict], *, accession: str,
                                form: str, period_of_report: str, cik: str) -> dict | None:
    """Certify current and immediate selected prior, or leave this relationship unavailable."""
    if len(selected) < 2:
        return None
    try:
        content = _cached_instance(filing)
        if content is None:
            return None
        root = etree.fromstring(content.encode(), parser=etree.XMLParser(
            resolve_entities=False, no_network=True, load_dtd=False))
        if root.tag != f"{_X}xbrl" or root.getroottree().docinfo.doctype:
            return None
        contexts, units = _unique_elements(root, "context"), _unique_elements(root, "unit")
        current, prior = [_point(source, contexts, units, cik) for source in [selected[0], selected[-1]]]
        if current is None or prior is None:
            return None
        if (current["period_end"] != period_of_report
                or prior["period_end"] >= current["period_start"]
                or any(current[key] != prior[key] for key in
                       ("currency", "raw_tag", "entity_identifier", "entity_scheme", "scope"))):
            return None
        return {"accession": accession, "form": form, "period_of_report": period_of_report,
                "current": current, "prior": prior}
    except (AttributeError, KeyError, TypeError, ValueError, etree.LxmlError):
        return None
