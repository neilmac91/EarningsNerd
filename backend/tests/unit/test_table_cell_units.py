"""Declared table-cell scale restoration: a bare model dollar figure copied from a scaled source
table carries the table's declared unit; every other bare figure stays exactly as written.

Fixtures are exact lines of the retained candidate-r WMT 10-K packet (report SHA-256
deaa1b52c85bbab1bbcd19b7e55ab483b58ec465d6523272931cbd67e6c7f80b, run 1, source lines 214 and
254-258, 946-1012 and 1689-1702) and the retained bullet that dropped the unit. No provider calls.
"""
from copy import deepcopy
import json

import pytest

from app.services.ai import source_units
from app.services.ai.source_units import build_table_unit_index, restore_table_cell_units
from app.services.openai_service import OpenAIService
from app.services.summary_sections import render_sections, sections_to_markdown
from app.services.summary_versioning import SUMMARY_SCHEMA_VERSION

NB = "\xa0"
# Three tables from the retained excerpt, each under its own "(Amounts in millions)" banner, plus the
# footnote and lead-in prose that separate them. The maturities table glues each fiscal-year label to
# its cell ("20283,237") exactly as the flattened source does.
WMT_SOURCE = "\n\n".join([
    "(Amounts in millions)20262025",
    "Accrued income taxes596" + NB + "608" + NB,
    "Long-term debt due within one year3,542" + NB + "2,598" + NB,
    "Operating lease obligations due within one year1,631" + NB + "1,499" + NB,
    "(Amounts in millions)Maturity" + NB + "DatesBy Fiscal YearAmountAverage Rate(1)",
    "AmountAverage Rate(1)",
    "Unsecured debt",
    "2028388" + NB + "0.5%389" + NB + "0.5%",
    "Total unsecured debt38,802" + NB + "36,846" + NB,
    "(636)(847)",
    "Total debt38,166" + NB + "35,999" + NB,
    "Less amounts due within one year(3,542)(2,598)",
    "Long-term debt$34,624" + NB + "$33,401" + NB,
    "(1)The average rate represents the weighted-average stated rate for each corresponding debt "
    "category, based on year-end balances and year-end interest rates. ",
    "(2)Includes deferred loan costs, discounts, fair value hedges, foreign-held debt and secured debt. ",
    "Annual maturities of long-term debt during the next five years and thereafter are as follows:",
    "(Amounts in millions)Annual",
    "Fiscal YearMaturities",
    "2027$3,542" + NB,
    "20283,237" + NB,
    "20293,389" + NB,
    "20302,143" + NB,
    "20312,600" + NB,
    "Thereafter23,255" + NB,
    "Total$38,166" + NB,
    "Debt Issuances",
    "Information on significant issuances of long-term debt during fiscal 2026, for general corporate "
    "purposes, is as follows:",
    "(Amounts in millions)Long-term debt due within one yearLong-term debtTotal",
    "Balances as of February 1, 2025$2,598" + NB + "$33,401" + NB + "$35,999" + NB,
    "Balances as of January 31, 2026$3,542" + NB + "$34,624" + NB + "$38,166" + NB,
])
WMT_BULLET = ("Annual maturities of long-term debt during the next five years and thereafter are as "
              "follows: 2027: $3,542; 2028: $3,237; 2029: $3,389; 2030: $2,143; 2031: $2,600; "
              "Thereafter: $23,255; Total: $38,166.")
WMT_RESTORED = ("Annual maturities of long-term debt during the next five years and thereafter are as "
                "follows: 2027: $3,542 million; 2028: $3,237 million; 2029: $3,389 million; "
                "2030: $2,143 million; 2031: $2,600 million; Thereafter: $23,255 million; "
                "Total: $38,166 million.")
# The issuer's own prose writes the figure bare (retained BA and COST packets): the model may be
# copying a section convention this owner cannot certify, so nothing is inserted.
PROSE_SOURCE = ("On October 31, 2025, we closed on the sale of portions of our BGS segment’s Digital "
                "Aviation Solutions business (Digital Aviation Solutions Divestiture) to Thoma Bravo "
                "for proceeds of $10,550. The sale included Jeppesen, ForeFlight, AerData and OzRunways.")
# The retained WMT standardized metrics carry the noncurrent balance, not any maturity row.
WMT_XBRL = {"long_term_debt": {"current": {"value": 34_624_000_000.0}, "prior": {"value": 33_401_000_000.0}}}


def _sections(bullet: str = WMT_BULLET, **extra):
    base = {"balance_sheet_liquidity": {"liquidity": "Cash was $10.7B.", "maturities_covenants": [bullet]}}
    base.update(extra)
    return base


def test_retained_wmt_maturities_bullet_regains_the_declared_millions():
    sections = _sections()
    audit = restore_table_cell_units(sections, build_table_unit_index(WMT_SOURCE), xbrl_metrics=WMT_XBRL)
    assert sections["balance_sheet_liquidity"]["maturities_covenants"] == [WMT_RESTORED]
    assert sections["balance_sheet_liquidity"]["liquidity"] == "Cash was $10.7B."
    assert audit["unresolved"] == []
    assert {(r["figure"], r["unit"]) for r in audit["restored"]} == {
        ("$3,542", "million"), ("$3,237", "million"), ("$3,389", "million"), ("$2,143", "million"),
        ("$2,600", "million"), ("$23,255", "million"), ("$38,166", "million"),
    }
    assert all(r["slot"] == "balance_sheet_liquidity.maturities_covenants[0]" for r in audit["restored"])


@pytest.mark.parametrize("figure, reason, source", [
    # The source's own prose uses the bare figure.
    ("$10,550", "prose_occurrence", PROSE_SOURCE),
    # Not in the offered excerpt at all (the retained BYND salary figure).
    ("$130,000", "no_occurrence", WMT_SOURCE),
    # Same digits under a millions table and a thousands table.
    ("$3,542", "mixed_scales", WMT_SOURCE + "\n\n(in thousands)\n\nOther3,542" + NB),
    # A percentage cell is not a dollar amount.
    ("$38,802", "percent_occurrence", "(Amounts in millions)20262025\n\nMix38,802%"),
    # A banner scales dollars only when the banner is in dollars.
    ("$3,237", "no_governing_banner", "(RMB in millions)20262025\n\nRevenue3,237" + NB),
    # A cell whose only banner is above a prose sentence is not governed by that banner.
    ("$3,237", "no_governing_banner",
     "(Amounts in millions)\n\nThe Company reports the following amounts in its annual filing.\n\nOther3,237" + NB),
    # Rows a banner excludes from the scale: share counts and per-share amounts.
    ("$8,022", "unscaled_row", "(Amounts in millions, except per share data)\n\nDiluted shares8,022" + NB),
])
def test_bare_figures_the_source_does_not_own_stay_as_written(figure, reason, source):
    text = f"The filing reports {figure} for the period."
    sections = _sections(text)
    audit = restore_table_cell_units(sections, build_table_unit_index(source))
    assert sections["balance_sheet_liquidity"]["maturities_covenants"] == [text]
    assert audit["restored"] == []
    assert audit["unresolved"] == [
        {"slot": "balance_sheet_liquidity.maturities_covenants[0]", "figure": figure, "reason": reason},
    ]


@pytest.mark.parametrize("source", [
    # One string per line (BeautifulSoup separator path): the cell stands alone on its line.
    "(Amounts in millions)\n\nTotal debt\n\n38,166\n\n35,999\n\nLess amounts due within one year\n\n(3,542)",
    # Cells joined by two spaces (edgartools fast table renderer): the cell ends the line.
    "(Amounts in millions)\n\nTotal debt  38,166  35,999\n\nLess amounts due within one year  (3,542)  (2,598)",
])
def test_other_table_flattenings_own_a_cell_at_either_end_of_its_line(source):
    sections = _sections("Total debt was $38,166 and the current portion $3,542.")
    audit = restore_table_cell_units(sections, build_table_unit_index(source))
    assert sections["balance_sheet_liquidity"]["maturities_covenants"] == [
        "Total debt was $38,166 million and the current portion $3,542 million."]
    assert audit["unresolved"] == []


@pytest.mark.parametrize("figure, reason, source, prose", [
    # Review P1: a short sentence under a banner is prose, not a row, even when it ends the block.
    ("$3,237", "prose_occurrence",
     "(Amounts in millions)\n\nDebt  9,000\n\nThe registration fee was $3,237.",
     "The registration fee was $3,237."),
    # A figure with no cell separator around it is not a demonstrated cell, sentence or not.
    ("$3,237", "undelimited_cell",
     "(Amounts in millions)\n\nDebt  9,000\n\nRegistration fee was $3,237.",
     "The registration fee was $3,237."),
    # Review P1: a per-share row whose label is detached on the line above (one value per line).
    ("$3,237", "unscaled_row",
     "(Amounts in millions, except per share data)\n\nRevenue\n\n9,000\n\nDividends per share\n\n3,237",
     "Dividends per share were $3,237."),
    # Review P1: a new table whose header carries its own unit token never inherits the banner above.
    ("$3,237", "no_governing_banner",
     "(Amounts in millions)\n\nDebt  9,000\n\nOther fees\n\nName  Fee ($)\n\nSmith  3,237",
     "Smith paid $3,237."),
    # A run of headings longer than a header block separates a row from the banner.
    ("$3,237", "no_governing_banner",
     "(Amounts in millions)\n\nDebt  9,000\n\nPart II\n\nItem 5\n\nMarket information\n\nOther matters\n\nSmith  3,237",
     "Smith paid $3,237."),
])
def test_review_adverse_sources_abstain(figure, reason, source, prose):
    sections = _sections(prose)
    audit = restore_table_cell_units(sections, build_table_unit_index(source))
    assert sections["balance_sheet_liquidity"]["maturities_covenants"] == [prose]
    assert audit["restored"] == []
    assert audit["unresolved"] == [
        {"slot": "balance_sheet_liquidity.maturities_covenants[0]", "figure": figure, "reason": reason},
    ]


def test_plural_scale_words_are_already_unit_bound():
    # Review P2: "$3,237 millions" is unit-bound prose, never a candidate, whatever the source says.
    text = "Debt was $3,237 millions and fees were $1,200 Thousands; other debt $9,000 billions."
    sections = _sections(text)
    assert restore_table_cell_units(sections, build_table_unit_index("(Amounts in millions)\n\nDebt  3,237\n\nFees  1,200\n\nOther  9,000")) is None
    assert sections["balance_sheet_liquidity"]["maturities_covenants"] == [text]


def test_scaled_decimal_currency_prefixed_and_percent_figures_are_not_bare():
    # Already-unit-bound or non-dollar forms are never candidates, however the source reads.
    text = ("Proceeds of $10,550M and a gain of $9,566 million; US$996.3M of notes; NT$129,663,077,605 "
            "in dividends; $1,985.3 million of income; margin of $3,542%.")
    sections = _sections(text)
    assert restore_table_cell_units(sections, build_table_unit_index(WMT_SOURCE)) is None
    assert sections["balance_sheet_liquidity"]["maturities_covenants"] == [text]


def test_literal_reading_supported_by_xbrl_abstains():
    # A standardized XBRL value equal to the literal figure means the bare reading is source-supported.
    sections = _sections("Dividends declared totalled $3,542.")
    literal = {"dividends_paid": {"current": {"value": 3_542.0}}}
    audit = restore_table_cell_units(sections, build_table_unit_index(WMT_SOURCE), xbrl_metrics=literal)
    assert sections["balance_sheet_liquidity"]["maturities_covenants"] == ["Dividends declared totalled $3,542."]
    assert audit["unresolved"][0]["reason"] == "literal_xbrl_match"


def test_xbrl_corroboration_is_recorded_when_the_scaled_value_is_standardized():
    sections = _sections("Total long-term debt including current maturities was $38,166.")
    corroborating = {"long_term_debt": {"current": {"value": 38_166_000_000.0}}}
    audit = restore_table_cell_units(sections, build_table_unit_index(WMT_SOURCE), xbrl_metrics=corroborating)
    assert sections["balance_sheet_liquidity"]["maturities_covenants"] == [
        "Total long-term debt including current maturities was $38,166 million."]
    assert audit["restored"] == [{"slot": "balance_sheet_liquidity.maturities_covenants[0]",
                                  "figure": "$38,166", "unit": "million", "xbrl_corroborated": True}]


def test_recovered_sections_verbatim_fields_and_missing_source_are_untouched():
    index = build_table_unit_index(WMT_SOURCE)
    recovered = _sections()
    audit = restore_table_cell_units(recovered, index, recovered={"balance_sheet_liquidity"})
    assert recovered["balance_sheet_liquidity"]["maturities_covenants"] == [WMT_BULLET]
    assert audit["restored"] == [] and {u["reason"] for u in audit["unresolved"]} == {"recovered"}
    # supporting_evidence is a verbatim trace-to-source surface: never rewritten.
    evidence = _sections("Nothing bare here.", notable_footnotes=[
        {"item": "Maturities", "impact": "Maturities total $38,166.", "supporting_evidence": "Total$38,166"}])
    restore_table_cell_units(evidence, index)
    assert evidence["notable_footnotes"][0]["supporting_evidence"] == "Total$38,166"
    assert evidence["notable_footnotes"][0]["impact"] == "Maturities total $38,166 million."
    assert build_table_unit_index("") is None
    untouched = _sections()
    assert restore_table_cell_units(untouched, None) is None
    assert untouched["balance_sheet_liquidity"]["maturities_covenants"] == [WMT_BULLET]


def test_audit_totals_are_exact_while_detail_lists_are_capped():
    figures = " ".join(f"${1_000 + i:,}" for i in range(source_units._AUDIT_CAP + 5))
    sections = _sections(f"Fees were {figures}.")
    audit = restore_table_cell_units(sections, build_table_unit_index(WMT_SOURCE))
    assert audit["unresolved_count"] == source_units._AUDIT_CAP + 5
    assert len(audit["unresolved"]) == source_units._AUDIT_CAP
    assert audit["restored_count"] == 0 and audit["restored"] == []


def _statement_source():
    """The smallest statement source the earnings-quality binder accepts."""
    def column(year, end):
        return {"year": year, "period_end": end,
                "operating": {"label": "Operating income", "value": 100_000_000},
                "pretax": {"label": "Income before income taxes", "value": 90_000_000},
                "components": [{"label": "Interest expense", "value": -10_000_000}]}
    return {"scale": 1_000_000, "current": column(2026, "2026-01-31"), "prior": column(2025, "2025-01-31"),
            "operating_disclosures": [{"year": 2026, "rows": []}, {"year": 2025, "rows": []}],
            "expense_notes": [], "comparative_notes": [], "additional_disclosures": []}


@pytest.mark.asyncio
async def test_owner_runs_after_the_source_binders_on_final_and_preview(monkeypatch):
    # Slots the binders replace or remove (operating_vs_one_time under a statement source;
    # capital_allocation and highlights always) must never appear in the audit, while the surviving
    # maturities bullet is restored identically on the final and preview paths.
    service = OpenAIService()
    sections = _sections(
        earnings_quality={"operating_vs_one_time": "Debt of $3,542 was reclassified."},
        value_drivers={"capital_allocation": "Buybacks of $38,166 were funded.", "highlights": ["Repaid $3,237."]},
    )
    structured = {"schema_version": SUMMARY_SCHEMA_VERSION, "sections": deepcopy(sections), "metadata": {}}

    async def generated(*args, **kwargs):
        return deepcopy(structured)

    monkeypatch.setattr(service, "generate_structured_summary", generated)
    result = await service.summarize_filing(WMT_SOURCE, "Walmart", "10-K", xbrl_metrics=WMT_XBRL,
                                            filing_excerpt=WMT_SOURCE, statement_source=_statement_source())
    raw = result["raw_summary"]
    audit = raw["table_cell_unit_audit"]
    assert {r["slot"] for r in audit["restored"]} == {"balance_sheet_liquidity.maturities_covenants[0]"}
    assert audit["restored_count"] == 7 and audit["unresolved_count"] == 0
    assert "operating_vs_one_time" not in raw["sections"]["earnings_quality"]
    assert "capital_allocation" not in raw["sections"]["value_drivers"]
    assert "highlights" not in raw["sections"]["value_drivers"]
    final_markdown = sections_to_markdown(render_sections({**raw, "schema_version": SUMMARY_SCHEMA_VERSION}))
    assert final_markdown == result["business_overview"] and WMT_RESTORED in final_markdown
    preview = service._partial_markdown_preview(
        json.dumps(structured), WMT_XBRL, statement_source=_statement_source(),
        unit_index=build_table_unit_index(WMT_SOURCE))
    assert preview and WMT_RESTORED in preview
    assert "$3,542 million was reclassified" not in preview and "$38,166 million were funded" not in preview
    assert "$3,542 million was reclassified" not in final_markdown


def test_audit_reasons_are_the_documented_vocabulary():
    assert source_units._AUDIT_CAP >= 7
    index = build_table_unit_index(WMT_SOURCE)
    assert index.resolve("3,542") == ("million", "declared")
    assert index.resolve("3,542") == ("million", "declared")  # cached answer is identical
    assert index.resolve("999,999") == (None, "no_occurrence")


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["final", "preview", "recovered"])
async def test_actual_consumer_restores_once_and_renders_the_same_text(monkeypatch, case):
    service = OpenAIService()
    sections = _sections()
    structured = {"schema_version": SUMMARY_SCHEMA_VERSION, "sections": deepcopy(sections), "metadata": {}}
    if case == "recovered":
        structured["_recovered_sections"] = ["balance_sheet_liquidity"]

    async def generated(*args, **kwargs):
        return deepcopy(structured)

    monkeypatch.setattr(service, "generate_structured_summary", generated)
    if case == "preview":
        with_index = service._partial_markdown_preview(
            json.dumps(structured), WMT_XBRL, unit_index=build_table_unit_index(WMT_SOURCE))
        without = service._partial_markdown_preview(json.dumps(structured), WMT_XBRL)
        assert with_index and WMT_RESTORED in with_index
        assert without and WMT_BULLET in without and WMT_RESTORED not in without
        return
    result = await service.summarize_filing(WMT_SOURCE, "Walmart", "10-K", xbrl_metrics=WMT_XBRL,
                                            filing_excerpt=WMT_SOURCE)
    raw = result["raw_summary"]
    bullets = raw["sections"]["balance_sheet_liquidity"]["maturities_covenants"]
    markdown = sections_to_markdown(render_sections({**raw, "schema_version": SUMMARY_SCHEMA_VERSION}))
    assert markdown == result["business_overview"]
    if case == "recovered":
        assert bullets == [WMT_BULLET] and WMT_BULLET in markdown
        assert raw["table_cell_unit_audit"]["restored"] == []
        return
    assert bullets == [WMT_RESTORED] and WMT_RESTORED in markdown
    assert len(raw["table_cell_unit_audit"]["restored"]) == 7 and raw["table_cell_unit_audit"]["unresolved"] == []
