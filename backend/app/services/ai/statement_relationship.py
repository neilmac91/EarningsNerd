"""One application-owned earnings-quality projection for preview, final and exports."""
from __future__ import annotations

CONTEXT_KEY = "statement_relationship_context_version"
CONTEXT_VERSION = 1
OWNED_FIELD = "reported_statement_relationship"


def statement_paragraphs(source: dict) -> list[str]:
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


def bind_statement_relationship(sections: dict, source: dict | None) -> None:
    section = sections.get("earnings_quality")
    if not isinstance(section, dict):
        return
    section.pop(OWNED_FIELD, None)  # the model cannot supply a trusted source channel
    if source is None:
        return
    section.pop("operating_vs_one_time", None)
    section.pop("operatingVsOneTime", None)
    section[OWNED_FIELD] = {"paragraphs": statement_paragraphs(source), "source": source}
