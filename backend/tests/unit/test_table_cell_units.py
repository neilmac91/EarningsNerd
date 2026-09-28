"""Declared table-cell scale restoration: a bare model dollar figure copied from a scaled source
table carries the scale the filing's own source document declares for it; every other bare figure
stays exactly as written.

Ownership is source-bound: an inline-XBRL fact's ``scale``/unit, or a ``<td>`` holding exactly the
amount inside a ``<table>`` that declares its own scale. The WMT fixture
(``tests/fixtures/table_units/wmt-20260131-debt-tables.html.gz``) is the iXBRL unit definitions plus
the five debt tables of the retained candidate-r WMT 10-K source (wmt-20260131.htm as served on
28 September 2026, SHA-256 f7fcd37e…; the retained run's provenance hash 60c7be42… differs by ten
characters of the 2.3 MB document, the tables are byte-identical) and the retained bullet that
dropped the unit. No provider calls, no network.
"""
from copy import deepcopy
import gzip
import json
from pathlib import Path

import pytest

from app.services.ai import source_units
from app.services.ai.source_units import build_table_unit_index, restore_table_cell_units
from app.services.openai_service import OpenAIService
from app.services.summary_sections import render_sections, sections_to_markdown
from app.services.summary_versioning import SUMMARY_SCHEMA_VERSION

WMT_SOURCE = gzip.open(
    Path(__file__).parents[1] / "fixtures" / "table_units" / "wmt-20260131-debt-tables.html.gz", "rt",
    encoding="utf-8",
).read()
WMT_BULLET = ("Annual maturities of long-term debt during the next five years and thereafter are as "
              "follows: 2027: $3,542; 2028: $3,237; 2029: $3,389; 2030: $2,143; 2031: $2,600; "
              "Thereafter: $23,255; Total: $38,166.")
WMT_RESTORED = ("Annual maturities of long-term debt during the next five years and thereafter are as "
                "follows: 2027: $3,542 million; 2028: $3,237 million; 2029: $3,389 million; "
                "2030: $2,143 million; 2031: $2,600 million; Thereafter: $23,255 million; "
                "Total: $38,166 million.")
# The flattened excerpt the model read is NOT a source of ownership: it carries no table boundary.
WMT_EXCERPT = "(Amounts in millions)Annual\n\nFiscal YearMaturities\n\n2027$3,542\xa0\n\n20283,237\xa0\n\nTotal$38,166\xa0"
# The retained WMT standardized metrics carry the noncurrent balance, not any maturity row.
WMT_XBRL = {"long_term_debt": {"current": {"value": 34_624_000_000.0}, "prior": {"value": 33_401_000_000.0}}}
UNITS = ('<div style="display:none"><xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>'
         '<xbrli:unit id="usdPerShare"><xbrli:measure>iso4217:USD</xbrli:measure>'
         '<xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unit></div>')
MILLIONS_TABLE = "<table><tr><td>(Amounts in millions)</td></tr><tr><td>Debt</td><td>9,000</td></tr></table>"


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


def test_the_flattened_excerpt_never_owns_a_figure():
    # A cached-excerpt generation has no source document: the owner has nothing to bind and the
    # bullet stays as written. The excerpt's own banner lines are text, never cells.
    assert build_table_unit_index("") is None
    sections = _sections()
    audit = restore_table_cell_units(sections, build_table_unit_index(WMT_EXCERPT))
    assert sections["balance_sheet_liquidity"]["maturities_covenants"] == [WMT_BULLET]
    assert audit["restored"] == [] and audit["unresolved_count"] == 7
    reasons = {u["figure"]: u["reason"] for u in audit["unresolved"]}
    assert reasons["$3,542"] == reasons["$3,237"] == reasons["$38,166"] == "prose_occurrence"
    assert reasons["$3,389"] == "no_occurrence"


@pytest.mark.parametrize("figure, reason, source", [
    # The issuer's own prose writes the figure bare and untagged (retained COST MD&A convention).
    ("$7,189", "prose_occurrence",
     MILLIONS_TABLE + "<p>Net sales increased $7,189 or 12% during the third quarter.</p>"),
    # A tagged cell plus an untagged prose mention (retained COST $1,359): prose wins, abstain.
    ("$1,359", "prose_occurrence",
     UNITS + '<table><tr><td>(In millions)</td></tr><tr><td>Remaining</td><td>'
     '<ix:nonFraction unitRef="usd" scale="6" name="x:Y">1,359</ix:nonFraction></td></tr></table>'
     "<p>The remaining authorization was $1,359.</p>"),
    # Not in the source document at all (the retained BYND salary figure in a document without it).
    ("$130,000", "no_occurrence", WMT_SOURCE),
    # Same digits under a millions table and a thousands table.
    ("$3,542", "mixed_scales",
     WMT_SOURCE.replace("</body>", "<table><tr><td>(in thousands)</td></tr><tr><td>Other</td><td>3,542</td></tr></table></body>")),
    # A percentage cell is not a dollar amount, whether the sign is in the cell or the next one.
    ("$38,802", "percent_occurrence",
     "<table><tr><td>(Amounts in millions)</td></tr><tr><td>Mix</td><td>38,802%</td></tr></table>"),
    ("$38,802", "percent_occurrence",
     "<table><tr><td>(Amounts in millions)</td></tr><tr><td>Mix</td><td>38,802</td><td>%</td></tr></table>"),
    # A table declares dollars only when the declaration is in dollars; an unrecognised form is no
    # declaration at all.
    ("$3,237", "non_dollar_banner",
     "<table><tr><td>(In millions of euros)</td></tr><tr><td>Revenue</td><td>3,237</td></tr></table>"),
    ("$3,237", "no_governing_banner",
     "<table><tr><td>(RMB in millions)</td></tr><tr><td>Revenue</td><td>3,237</td></tr></table>"),
    # A table without any declaration of its own is not governed by a table before it.
    ("$3,237", "no_governing_banner",
     MILLIONS_TABLE + "<table><tr><td>Other</td><td>3,237</td></tr></table>"),
    # A declaration node before the table governs only when it is the node immediately before it.
    ("$3,237", "no_governing_banner",
     "<p>(In millions)</p><p>Schedule of other amounts</p><table><tr><td>Other</td><td>3,237</td></tr></table>"),
    # Rows a "(… except per share data)" declaration excludes: per-share and share-count rows.
    ("$8,022", "unscaled_row",
     "<table><tr><td>(Amounts in millions, except per share data)</td></tr>"
     "<tr><td>Diluted shares</td><td>8,022</td></tr></table>"),
    # A column headed "Shares" is not scaled dollars even inside an "(In millions)" table.
    ("$3,237", "unscaled_column",
     "<table><tr><td colspan='3'>(In millions)</td></tr><tr><td></td><td>Shares</td><td>Amount</td></tr>"
     "<tr><td>Issued</td><td>3,237</td><td>9,000</td></tr></table>"),
    # A value with no label to its left has no row to own it.
    ("$3,237", "no_row_label",
     "<table><tr><td>(In millions)</td></tr><tr><td>3,237</td><td>2,598</td></tr></table>"),
    # An inline-XBRL fact declaring scale 0 says the bare reading is right (retained BYND $130,000).
    ("$130,000", "declared_unscaled",
     UNITS + '<p>Base salary of $<ix:nonFraction unitRef="usd" scale="0" name="b:Salary">130,000</ix:nonFraction>.</p>'),
    # A fact in a per-share (or any non-USD) unit is not a scaled dollar amount.
    ("$3,237", "non_dollar_unit",
     UNITS + '<table><tr><td>(In millions)</td></tr><tr><td>Dividends</td><td>'
     '<ix:nonFraction unitRef="usdPerShare" scale="0" name="x:D">3,237</ix:nonFraction></td></tr></table>'),
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


@pytest.mark.parametrize("figure, reason, source, prose", [
    # Review round 1: a short sentence after a bannered table is prose, not a row.
    ("$3,237", "prose_occurrence", MILLIONS_TABLE + "<p>Registration fee was $3,237.</p>",
     "The registration fee was $3,237."),
    # Review round 4: list items and a colon-labelled line after a bannered table are not cells.
    ("$3,237", "prose_occurrence", MILLIONS_TABLE + "<p>• Registration fee:  $3,237</p>",
     "The registration fee was $3,237."),
    ("$3,237", "prose_occurrence", MILLIONS_TABLE + "<p>1. Registration fee:  $3,237</p>",
     "The registration fee was $3,237."),
    ("$3,237", "prose_occurrence", MILLIONS_TABLE + "<div>Registration fee:  $3,237</div>",
     "The registration fee was $3,237."),
    # Review round 1: a per-share row whose label sits on the row above its value.
    ("$3,237", "no_row_label",
     "<table><tr><td>(Amounts in millions, except per share data)</td></tr><tr><td>Revenue</td><td>9,000</td></tr>"
     "<tr><td>Dividends per share</td></tr><tr><td></td><td>3,237</td></tr></table>",
     "Dividends per share were $3,237."),
    # Review round 1: a column headed with its own unit token never takes the table's scale.
    ("$3,237", "unscaled_column",
     "<table><tr><td colspan='2'>(Amounts in millions)</td></tr><tr><td>Name</td><td>Fee ($)</td></tr>"
     "<tr><td>Smith</td><td>3,237</td></tr></table>",
     "Smith paid $3,237."),
    # Review round 4: the all-capitals director-compensation transition, and a bare adjacent table.
    ("$3,237", "no_governing_banner",
     MILLIONS_TABLE + "<p>DIRECTOR COMPENSATION</p><table><tr><td>Name</td><td>Fee</td></tr>"
     "<tr><td>Smith</td><td>3,237</td></tr></table>",
     "Smith paid $3,237."),
    ("$3,237", "no_governing_banner",
     MILLIONS_TABLE + "<table><tr><td>Name</td><td>Fee</td></tr><tr><td>Smith</td><td>3,237</td></tr></table>",
     "Smith paid $3,237."),
    # Flattened text with the renderer's two-space delimiters has no cells at all.
    ("$3,237", "prose_occurrence", "(Amounts in millions)\n\nDebt  9,000\n\n2027  3,237",
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


@pytest.mark.parametrize("source", [
    # The declaration is the whole text of the node immediately before the table.
    "<p>(In millions, except per share data)</p><table><tr><td>Debt</td><td>3,237</td></tr></table>",
    # The declaration shares a header cell with other words (retained WMT market-risk table).
    "<table><tr><td>Expected Maturity Date (Amounts in millions)</td></tr><tr><td>Fixed rate</td><td>$</td><td>3,237</td></tr></table>",
    # A parenthesised negative cell and an "Amount" column beside a "Shares" column.
    "<table><tr><td colspan='3'>(In millions)</td></tr><tr><td></td><td>Shares</td><td>Amount</td></tr>"
    "<tr><td>Repurchased</td><td>12</td><td>( 3,237 )</td></tr></table>",
])
def test_table_declarations_own_their_own_cells(source):
    sections = _sections("Debt of $3,237 was repaid.")
    audit = restore_table_cell_units(sections, build_table_unit_index(source))
    assert sections["balance_sheet_liquidity"]["maturities_covenants"] == ["Debt of $3,237 million was repaid."]
    assert audit["unresolved"] == []


def test_an_inline_xbrl_fact_owns_its_own_scale_even_in_prose():
    # The retained BA prose wrote "$10,550" bare; the issuer tagged that number scale 6 in USD, so
    # the fact itself declares millions. Without the tag the same prose abstains.
    tagged = UNITS + '<p>proceeds of $<ix:nonFraction unitRef="usd" scale="6" name="b:P">10,550</ix:nonFraction>.</p>'
    sections = _sections("Proceeds were $10,550.")
    audit = restore_table_cell_units(sections, build_table_unit_index(tagged))
    assert sections["balance_sheet_liquidity"]["maturities_covenants"] == ["Proceeds were $10,550 million."]
    assert audit["restored"][0]["unit"] == "million"
    untagged = _sections("Proceeds were $10,550.")
    audit = restore_table_cell_units(untagged, build_table_unit_index("<p>proceeds of $10,550.</p>"))
    assert untagged["balance_sheet_liquidity"]["maturities_covenants"] == ["Proceeds were $10,550."]
    assert audit["unresolved"][0]["reason"] == "prose_occurrence"


def test_repeat_application_is_a_no_op():
    # A restored slot is unit-bound, so a second pass (read-time re-render, cron regeneration of
    # the same output) finds no bare figure and reports nothing.
    sections = _sections()
    index = build_table_unit_index(WMT_SOURCE)
    first = restore_table_cell_units(sections, index, xbrl_metrics=WMT_XBRL)
    assert first["restored_count"] == 7 and first["unresolved_count"] == 0
    restored = sections["balance_sheet_liquidity"]["maturities_covenants"][0]
    assert restore_table_cell_units(sections, index, xbrl_metrics=WMT_XBRL) is None
    assert sections["balance_sheet_liquidity"]["maturities_covenants"] == [restored]


def test_plural_scale_words_are_already_unit_bound():
    # Review P2: "$3,237 millions" is unit-bound prose, never a candidate, whatever the source says.
    text = "Debt was $3,237 millions and fees were $1,200 Thousands; other debt $9,000 billions."
    sections = _sections(text)
    assert restore_table_cell_units(sections, build_table_unit_index(WMT_SOURCE)) is None
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


def test_the_source_document_is_parsed_once_and_only_on_demand():
    index = build_table_unit_index(WMT_SOURCE)
    assert index._parsed is False  # holding the document costs nothing until a bare figure appears
    assert index.resolve("3,542") == ("million", "declared")
    assert index.resolve("3,542") == ("million", "declared")  # cached answer is identical
    assert index.resolve("999,999") == (None, "no_occurrence")
    assert index._parsed is True
    assert source_units._AUDIT_CAP >= 7


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
                                            filing_excerpt=WMT_EXCERPT, statement_source=_statement_source())
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


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["final", "preview", "recovered", "cached_excerpt"])
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
    # A cached-excerpt generation supplies no source document: nothing is owned, nothing is audited.
    source = "" if case == "cached_excerpt" else WMT_SOURCE
    result = await service.summarize_filing(source, "Walmart", "10-K", xbrl_metrics=WMT_XBRL,
                                            filing_excerpt=WMT_EXCERPT)
    raw = result["raw_summary"]
    bullets = raw["sections"]["balance_sheet_liquidity"]["maturities_covenants"]
    markdown = sections_to_markdown(render_sections({**raw, "schema_version": SUMMARY_SCHEMA_VERSION}))
    assert markdown == result["business_overview"]
    if case == "cached_excerpt":
        assert bullets == [WMT_BULLET] and WMT_BULLET in markdown
        assert "table_cell_unit_audit" not in raw
        return
    if case == "recovered":
        assert bullets == [WMT_BULLET] and WMT_BULLET in markdown
        assert raw["table_cell_unit_audit"]["restored"] == []
        return
    assert bullets == [WMT_RESTORED] and WMT_RESTORED in markdown
    assert len(raw["table_cell_unit_audit"]["restored"]) == 7 and raw["table_cell_unit_audit"]["unresolved"] == []
