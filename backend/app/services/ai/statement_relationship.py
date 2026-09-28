"""One application-owned earnings-quality projection for preview, final and exports."""
from __future__ import annotations

import re

from app.services.edgar.quarterly_statement_source import KIND as QUARTERLY_KIND

CONTEXT_KEY = "statement_relationship_context_version"
CONTEXT_VERSION = 1
OWNED_FIELD = "reported_statement_relationship"

_MONEY = r"\$(?:\d{1,3}(?:,\d{3})*|\(\d{1,3}(?:,\d{3})*\))"
# A whole proposition, plus one separately preserved, finite continuation. No
# arbitrary prefix, suffix, entity, qualification or independent predicate can
# disappear into a regex capture. This grammar does not certify the continuation.
_AGGREGATE_CLAIM = re.compile(
    rf"\ANet income of (?P<net>{_MONEY}) (?P<unit>thousand|million) includes "
    r"a realized (?P<component>gain|loss) on (?P<asset>privately-held|publicly-held) equity securities "
    rf"recorded in other income \(expense\), net of (?P<other>{_MONEY}) (?P=unit), "
    rf"compared with other expense, net of (?P<prior>{_MONEY}) (?P=unit) in the prior-year period\."
    r"(?P<suffix> Stock-based compensation expense was "
    rf"{_MONEY} (?P=unit), and adjusted income from operations, which excludes "
    r"stock-based compensation and related employer payroll taxes, was "
    rf"{_MONEY} (?P=unit)\.)?\Z"
)


def _claim_amount(text: str, scale: int) -> int:
    amount = text[1:]
    return int(amount.strip("()").replace(",", "")) * scale * (-1 if amount.startswith("(") else 1)


def _quarterly_claim(text: str, source: dict) -> re.Match | None:
    match = _AGGREGATE_CLAIM.fullmatch(text)
    if match is None:
        return None
    scale = {"thousand": 1000, "million": 1000000}[match["unit"]]
    current, prior = source["current"]["rows"], source["prior"]["rows"]
    if (_claim_amount(match["net"], scale) != current["net"]["value"]
            or _claim_amount(match["other"], scale) != current["other"]["value"]
            or _claim_amount(match["prior"], scale) != prior["other"]["value"]):
        return None
    # Preserve the accepted authored form when an explicit separate current-period
    # investment component can carry this amount. We do not render or certify that
    # component; unsupported disclosure formats remain outside this exclusion.
    component_sign = 1 if match["component"] == "gain" else -1
    if any(item["value"] == current["other"]["value"]
           and item["value"] * component_sign > 0
           for item in source.get("separate_investment_component_amounts", [])):
        return None
    return match


def display_statement_paragraphs(owned: dict) -> list[str]:
    """Render application paragraphs and an unchanged authored continuation."""
    paragraphs = list(owned.get("paragraphs", []))
    suffix = owned.get("preserved_authored_suffix")
    if suffix:
        paragraphs.append(suffix)
    return paragraphs


COMPONENT_LIMITATION = (
    "This summary could not independently verify the stated component breakdown "
    "or its contribution to net income."
)


def statement_paragraphs(source: dict) -> list[str]:
    if source.get("kind") == QUARTERLY_KIND:
        return [COMPONENT_LIMITATION]
    scale = source["scale"]
    denomination = "millions" if scale == 1000000 else "thousands"
    current, prior = source["current"], source["prior"]
    paragraphs = [f"Reported consolidated statement, years ended {current['period_end']} and "
                  f"{prior['period_end']} (USD {denomination})."]
    by_year = {x["year"]: x for x in source["operating_disclosures"]}
    previous = {r["label"]: r for r in by_year[prior["year"]]["rows"]}
    for row in by_year[current["year"]]["rows"]:
        prior_row = previous[row["label"]]
        paragraphs.append(f"Reported before operating income: {row['label']} "
                          f"{row['value'] // scale:,} in {current['year']} and "
                          f"{prior_row['value'] // scale:,} in {prior['year']}.")
    for column in (current, prior):
        components = "; ".join(f"{r['label']}: {r['value'] // scale:+,}" for r in column["components"])
        paragraphs.append(f"{column['year']}: {column['operating']['label']} of "
                          f"{column['operating']['value'] // scale:,} reconciles to "
                          f"{column['pretax']['label']} of {column['pretax']['value'] // scale:,} "
                          f"through these subsequently reported rows: {components}.")
    paragraphs.append("Statement position does not establish that these items are one-time or recurring.")
    for note in (*source["expense_notes"], *source["comparative_notes"], *source["additional_disclosures"]):
        paragraphs.append(f"Filing disclosure: {note['text']}")
    return paragraphs


def bind_statement_relationship(sections: dict, source: dict | None) -> bool:
    section = sections.get("earnings_quality")
    if not isinstance(section, dict):
        return False
    section.pop(OWNED_FIELD, None)  # the model cannot supply a trusted source channel
    if source is None:
        return False
    suffix = None
    if source.get("kind") == QUARTERLY_KIND:
        authored = section.get("operating_vs_one_time")
        alternate = section.get("operatingVsOneTime")
        if alternate is not None and alternate != authored:
            return False
        if not isinstance(authored, str) or (match := _quarterly_claim(authored, source)) is None:
            return False
        suffix = match["suffix"]
    section.pop("operating_vs_one_time", None)
    section.pop("operatingVsOneTime", None)
    section[OWNED_FIELD] = {"paragraphs": statement_paragraphs(source), "source": source}
    if source.get("kind") == QUARTERLY_KIND:
        section[OWNED_FIELD]["kind"] = "unverified_component_breakdown"
    if suffix:
        # Retained text has its own channel and is never labelled as source-owned evidence.
        section[OWNED_FIELD]["preserved_authored_suffix"] = suffix
    return True
