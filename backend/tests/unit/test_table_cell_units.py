"""Declared table-cell scale restoration: a bare model dollar figure whose authored proposition
("label: $figure") one inline-XBRL fact of the filing owns carries that fact's declared scale;
every other bare figure stays exactly as written.

Ownership is a row/period/amount mapping: the authored label must be the leftmost text cell of the
fact's own table row, the fact's context must end on the filing's DEI report period, its unit must
be USD alone and its ``scale`` attribute declares the multiplier. The WMT fixture
(``tests/fixtures/table_units/wmt-20260131-debt-tables.html.gz``) is the DEI period fact, the
referenced contexts and unit definitions plus the five debt tables of the retained candidate-r WMT
10-K source (wmt-20260131.htm as served on 28 September 2026, SHA-256 f7fcd37e…; the retained run's
provenance hash 60c7be42… differs by ten characters of the 2.3 MB document) and the retained bullet
that dropped the unit. No provider calls, no network.
"""
from copy import deepcopy
import gzip
import json
from pathlib import Path

import pytest

from app.services.ai import source_units
from app.services.ai.source_units import authored_label, build_table_unit_index, restore_table_cell_units
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
# The flattened excerpt the model read is NOT a source of ownership: it carries no fact, row or period.
WMT_EXCERPT = "(Amounts in millions)Annual\n\nFiscal YearMaturities\n\n2027$3,542\xa0\n\n20283,237\xa0\n\nTotal$38,166\xa0"
# The retained WMT standardized metrics carry the noncurrent balance, not any maturity row.
WMT_XBRL = {"long_term_debt": {"current": {"value": 34_624_000_000.0}, "prior": {"value": 33_401_000_000.0}}}


def _document(body: str, *, period: str = "2026-01-31", extra_contexts: str = "") -> str:
    """A minimal inline-XBRL filing: the DEI period on a duration context, one current instant
    context ``c-1`` for facts, units, then ``body``."""
    return (
        '<html><body><div style="display:none"><ix:header>'
        '<ix:nonNumeric contextRef="c-dei" name="dei:DocumentPeriodEndDate">' + period + '</ix:nonNumeric>'
        '<ix:resources>'
        '<xbrli:context id="c-dei"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">104169'
        '</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2025-02-01</xbrli:startDate>'
        '<xbrli:endDate>' + period + '</xbrli:endDate></xbrli:period></xbrli:context>'
        '<xbrli:context id="c-1"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">104169'
        '</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>' + period + '</xbrli:instant>'
        '</xbrli:period></xbrli:context>' + extra_contexts +
        '<xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>'
        '<xbrli:unit id="usdPerShare"><xbrli:measure>iso4217:USD</xbrli:measure>'
        '<xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unit>'
        '</ix:resources></ix:header></div>' + body + '</body></html>'
    )


def _fact(digits: str, *, scale: str = "6", unit: str = "usd", context: str = "c-1") -> str:
    return (f'<ix:nonFraction unitRef="{unit}" scale="{scale}" contextRef="{context}" '
            f'name="us-gaap:Test">{digits}</ix:nonFraction>')


def _row(label: str, cell: str) -> str:
    return f"<table><tr><td>{label}</td><td>$</td><td>{cell}</td></tr></table>"


PRIOR_CONTEXT = ('<xbrli:context id="c-prior"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">'
                 '104169</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2025-01-31'
                 '</xbrli:instant></xbrli:period></xbrli:context>')


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


@pytest.mark.parametrize("text, label", [
    ("as follows: 2027: $3,542; 2028: $3,237", "2027"),
    ("Thereafter: $23,255; Total: $38,166.", "Thereafter"),
    ("(Registration fee: $3,237)", "Registration fee"),
    ("Diluted EPS:  $3,237", "Diluted EPS"),
    # No colon pairs the figure with a label: the statement is not a proposition this owner reads.
    ("Debt of $3,237 was repaid.", None),
    ("The registration fee was $3,237.", None),
    ("Net sales increased $7,189 or 12%.", None),
    ("• Registration fee $3,237", None),
])
def test_authored_label_is_the_text_paired_with_the_figure_by_a_colon(text, label):
    assert authored_label(text, text.index("$")) == label


def test_the_flattened_excerpt_never_owns_a_figure():
    # A cached-excerpt generation has no source document: the owner has nothing to bind and the
    # bullet stays as written. The excerpt's own banner lines carry no fact, row or period.
    assert build_table_unit_index("") is None
    sections = _sections()
    audit = restore_table_cell_units(sections, build_table_unit_index(WMT_EXCERPT))
    assert sections["balance_sheet_liquidity"]["maturities_covenants"] == [WMT_BULLET]
    assert audit["restored"] == [] and audit["unresolved_count"] == 7
    assert {u["reason"] for u in audit["unresolved"]} == {"no_tagged_fact"}


@pytest.mark.parametrize("figure, reason, source, prose", [
    # Root round 5: a later declaration row inside the same table, an untagged explicit-dollar cell.
    ("$3,237", "no_tagged_fact",
     _document('<table><tr><td>Registration fee</td><td>$3,237</td></tr>'
               '<tr><td colspan="2">(Amounts in millions)</td></tr><tr><td>Debt</td><td>9,000</td></tr></table>'),
     "Registration fee: $3,237."),
    # Root round 5: per-share scope under a full-width "Per Share Data" heading, a rowspan header
    # row, or a tfoot row — the fact's own unit decides, never the banner or the header geometry.
    ("$3,237", "non_dollar_unit",
     _document('<table><tr><td colspan="3">(Amounts in millions, except per share data)</td></tr>'
               '<tr><td colspan="3">Per Share Data</td></tr><tr><td>Diluted EPS</td><td>$</td><td>'
               + _fact("3,237", scale="0", unit="usdPerShare") + '</td></tr></table>'),
     "Diluted EPS: $3,237."),
    ("$3,237", "non_dollar_unit",
     _document('<table><thead><tr><th rowspan="2">Per Share</th><th>2026</th></tr><tr><th>2025</th></tr></thead>'
               '<tfoot><tr><td>Diluted EPS</td><td>' + _fact("3,237", scale="0", unit="usdPerShare")
               + '</td></tr></tfoot></table>'),
     "Diluted EPS: $3,237."),
    ("$3,237", "no_tagged_fact",
     _document('<table><tr><td colspan="2">(Amounts in millions, except per share data)</td></tr>'
               '<tr><td>Diluted EPS</td><td>3,237</td></tr></table>'),
     "Diluted EPS: $3,237."),
    # Root round 5: an unknown banner exception is never read; the fact declares the bare reading.
    ("$3,237", "declared_unscaled",
     _document('<table><tr><td colspan="2">(Amounts in millions, except registration fees which are in dollars)'
               '</td></tr><tr><td>Registration fee</td><td>' + _fact("3,237", scale="0") + '</td></tr></table>'),
     "Registration fee: $3,237."),
    # Root round 5: source-to-proposition ownership. A "Revenue" row never scales a registration fee.
    ("$3,237", "no_matching_row", _document(_row("Revenue", _fact("3,237"))), "Registration fee: $3,237."),
    # A statement that pairs no label with the figure is not a proposition this owner reads.
    ("$3,237", "no_authored_label", _document(_row("Debt", _fact("3,237"))), "Debt of $3,237 was repaid."),
    # A bullet item pairs "• Registration fee" with the figure; no row carries that label.
    ("$3,237", "no_matching_row", _document(_row("Debt", _fact("3,237"))), "• Registration fee:  $3,237 was paid"),
    # A fact bound to another period (the prior-year column) is not the current-period claim.
    ("$3,237", "period_mismatch",
     _document(_row("Debt", _fact("3,237", context="c-prior")), extra_contexts=PRIOR_CONTEXT), "Debt: $3,237."),
    # A fact whose context is unknown, or a filing without a validated DEI period, abstains.
    ("$3,237", "period_mismatch", _document(_row("Debt", _fact("3,237", context="c-unknown"))), "Debt: $3,237."),
    ("$3,237", "no_report_period", _row("Debt", _fact("3,237")), "Debt: $3,237."),
    # Same label and amount declared at two scales.
    ("$3,237", "mixed_scales",
     _document(_row("Debt", _fact("3,237")) + _row("Debt", _fact("3,237", scale="3"))), "Debt: $3,237."),
    # A fact in prose has no row and cannot bind a label; an unsupported scale abstains.
    ("$3,237", "no_matching_row", _document("<p>Debt: $" + _fact("3,237") + " was repaid.</p>"), "Debt: $3,237."),
    ("$3,237", "unsupported_scale", _document(_row("Debt", _fact("3,237", scale="2"))), "Debt: $3,237."),
    # The digits are not tagged anywhere in the document (retained COST prose, BYND salary).
    ("$7,189", "no_tagged_fact", _document("<p>Net sales increased $7,189 or 12%.</p>"), "Net sales: $7,189."),
    ("$130,000", "no_tagged_fact", WMT_SOURCE, "Salary: $130,000."),
    # A label that is not the leftmost text cell of the fact's row (value-first rows) does not bind.
    ("$3,237", "no_matching_row",
     _document("<table><tr><td>" + _fact("3,237") + "</td><td>Debt</td></tr></table>"), "Debt: $3,237."),
])
def test_bare_figures_the_source_does_not_own_stay_as_written(figure, reason, source, prose):
    sections = _sections(prose)
    audit = restore_table_cell_units(sections, build_table_unit_index(source))
    assert sections["balance_sheet_liquidity"]["maturities_covenants"] == [prose]
    assert audit["restored"] == []
    assert audit["unresolved"] == [
        {"slot": "balance_sheet_liquidity.maturities_covenants[0]", "figure": figure, "reason": reason},
    ]


@pytest.mark.parametrize("source, prose, restored", [
    # The retained BYND salary is the issuer's own scale-0 fact: the bare reading is right.
    (_document(_row("Base salary", _fact("130,000", scale="0"))), "Base salary: $130,000.", None),
    # A thousands fact restores "thousand"; label matching ignores case, spacing and a trailing colon.
    (_document(_row("Total  Debt:", _fact("3,237", scale="3"))), "total debt: $3,237.", "total debt: $3,237 thousand."),
    # Two rows with the same label, amount and scale agree.
    (_document(_row("Debt", _fact("3,237")) + _row("Debt", _fact("3,237"))), "Debt: $3,237.", "Debt: $3,237 million."),
])
def test_one_bound_fact_owns_the_proposition(source, prose, restored):
    sections = _sections(prose)
    audit = restore_table_cell_units(sections, build_table_unit_index(source))
    assert sections["balance_sheet_liquidity"]["maturities_covenants"] == [restored or prose]
    if restored is None:
        assert audit["unresolved"][0]["reason"] == "declared_unscaled"
    else:
        assert audit["unresolved"] == [] and audit["restored_count"] == 1


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
    text = "2028: $3,237 millions and fees were $1,200 Thousands; other debt $9,000 billions."
    sections = _sections(text)
    assert restore_table_cell_units(sections, build_table_unit_index(WMT_SOURCE)) is None
    assert sections["balance_sheet_liquidity"]["maturities_covenants"] == [text]


def test_scaled_decimal_currency_prefixed_and_percent_figures_are_not_bare():
    # Already-unit-bound or non-dollar forms are never candidates, however the source reads.
    text = ("Proceeds: $10,550M and a gain of $9,566 million; US$996.3M of notes; NT$129,663,077,605 "
            "in dividends; $1,985.3 million of income; margin: $3,542%.")
    sections = _sections(text)
    assert restore_table_cell_units(sections, build_table_unit_index(WMT_SOURCE)) is None
    assert sections["balance_sheet_liquidity"]["maturities_covenants"] == [text]


def test_literal_reading_supported_by_xbrl_abstains():
    # A standardized XBRL value equal to the literal figure means the bare reading is source-supported.
    sections = _sections("Maturities: 2027: $3,542.")
    literal = {"dividends_paid": {"current": {"value": 3_542.0}}}
    audit = restore_table_cell_units(sections, build_table_unit_index(WMT_SOURCE), xbrl_metrics=literal)
    assert sections["balance_sheet_liquidity"]["maturities_covenants"] == ["Maturities: 2027: $3,542."]
    assert audit["unresolved"][0]["reason"] == "literal_xbrl_match"


def test_xbrl_corroboration_is_recorded_when_the_scaled_value_is_standardized():
    sections = _sections("Long-term debt including current maturities; Total: $38,166.")
    corroborating = {"long_term_debt": {"current": {"value": 38_166_000_000.0}}}
    audit = restore_table_cell_units(sections, build_table_unit_index(WMT_SOURCE), xbrl_metrics=corroborating)
    assert sections["balance_sheet_liquidity"]["maturities_covenants"] == [
        "Long-term debt including current maturities; Total: $38,166 million."]
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
        {"item": "Maturities", "impact": "Maturities; Total: $38,166.", "supporting_evidence": "Total$38,166"}])
    restore_table_cell_units(evidence, index)
    assert evidence["notable_footnotes"][0]["supporting_evidence"] == "Total$38,166"
    assert evidence["notable_footnotes"][0]["impact"] == "Maturities; Total: $38,166 million."
    untouched = _sections()
    assert restore_table_cell_units(untouched, None) is None
    assert untouched["balance_sheet_liquidity"]["maturities_covenants"] == [WMT_BULLET]


def test_audit_totals_are_exact_while_detail_lists_are_capped():
    figures = " ".join(f"${1_000 + i:,}" for i in range(source_units._AUDIT_CAP + 5))
    sections = _sections(f"Fees: {figures}.")
    audit = restore_table_cell_units(sections, build_table_unit_index(WMT_SOURCE))
    assert audit["unresolved_count"] == source_units._AUDIT_CAP + 5
    assert len(audit["unresolved"]) == source_units._AUDIT_CAP
    assert audit["restored_count"] == 0 and audit["restored"] == []


def test_the_source_document_is_parsed_once_and_only_on_demand():
    index = build_table_unit_index(WMT_SOURCE)
    assert index._parsed is False  # holding the document costs nothing until a bare figure appears
    assert index.resolve("3,542", "2027") == ("million", "declared")
    assert index.resolve("3,542", "2027") == ("million", "declared")  # cached answer is identical
    assert index.resolve("3,542", "Registration fee") == (None, "no_matching_row")
    assert index.resolve("999,999", "Total") == (None, "no_tagged_fact")
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
        earnings_quality={"operating_vs_one_time": "Reclassified; 2027: $3,542."},
        value_drivers={"capital_allocation": "Buybacks; Total: $38,166.", "highlights": ["Repaid; 2028: $3,237."]},
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
    assert "2027: $3,542 million." not in preview.replace(WMT_RESTORED, "")
    assert "Total: $38,166 million." not in preview.replace(WMT_RESTORED, "")
    assert "Reclassified; 2027: $3,542 million" not in final_markdown


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
