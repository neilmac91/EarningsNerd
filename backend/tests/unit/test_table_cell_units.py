"""Declared table-cell scale restoration for exactly one finite proposition: a complete, source-owned
long-term-debt maturity sequence. The authored bullet must be the supported introduction followed by
five consecutive fiscal-year pairs, "Thereafter" and "Total", each a bare "$N,NNN"; the filing's
inline XBRL must tag each schedule concept (``debt_concepts.DEBT_MATURITY_SEQUENCE``) and the total
on the DEI report period, in a row of that label, in USD, with one 3/6/9 scale, with the six amounts
summing to the total. Every other bare figure stays exactly as written, with a reason.

The WMT fixture (``tests/fixtures/table_units/wmt-20260131-debt-tables.html.gz``) is the DEI period
fact, the referenced contexts and unit definitions plus the five debt tables of the retained
candidate-r WMT 10-K source (wmt-20260131.htm as served on 28 September 2026, SHA-256 f7fcd37e…;
the retained run's provenance hash 60c7be42… differs by ten characters of the 2.3 MB document) and
the retained bullet that dropped the unit. No provider calls, no network.
"""
from copy import deepcopy
import gzip
import json
from pathlib import Path

import pytest

from app.services.ai import source_units
from app.services.ai.source_units import build_table_unit_index, maturity_proposition, restore_table_cell_units
from app.services.edgar.debt_concepts import DEBT_MATURITY_SEQUENCE, DEBT_MATURITY_TOTAL
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
WMT_AMOUNTS = ("3,542", "3,237", "3,389", "2,143", "2,600", "23,255", "38,166")
# The flattened excerpt the model read is NOT a source of ownership: it carries no fact or period.
WMT_EXCERPT = "(Amounts in millions)Annual\n\nFiscal YearMaturities\n\n2027$3,542\xa0\n\n20283,237\xa0\n\nTotal$38,166\xa0"
# The retained WMT standardized metrics carry the noncurrent balance, not any maturity row.
WMT_XBRL = {"long_term_debt": {"current": {"value": 34_624_000_000.0}, "prior": {"value": 33_401_000_000.0}}}
CONTEXT = ('<xbrli:context id="{id}"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">104169'
           '</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>{date}</xbrli:instant>'
           '</xbrli:period></xbrli:context>')


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
        + CONTEXT.format(id="c-1", date=period) + extra_contexts +
        '<xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>'
        '<xbrli:unit id="usdPerShare"><xbrli:measure>iso4217:USD</xbrli:measure>'
        '<xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unit>'
        '</ix:resources></ix:header></div>' + body + '</body></html>'
    )


def _fact(concept: str, digits: str, *, scale: str = "6", unit: str = "usd", context: str = "c-1") -> str:
    return (f'<ix:nonFraction unitRef="{unit}" scale="{scale}" contextRef="{context}" '
            f'name="{concept}">{digits}</ix:nonFraction>')


def _schedule(amounts=WMT_AMOUNTS, *, labels=("2027", "2028", "2029", "2030", "2031", "Thereafter", "Total"),
              scale="6", total_concept=DEBT_MATURITY_TOTAL, skip=(), context="c-1", overrides=None) -> str:
    """The maturities table: one row per schedule concept plus the total, in the source's own layout."""
    concepts = (*DEBT_MATURITY_SEQUENCE, total_concept)
    rows = []
    for index, (concept, label, amount) in enumerate(zip(concepts, labels, amounts)):
        if index in skip:
            continue
        options = {"scale": scale, "context": context, **(overrides or {}).get(index, {})}
        rows.append(f"<tr><td>{label}</td><td>$</td><td>{_fact(concept, amount, **options)}</td></tr>")
    return "<table><tr><td>(Amounts in millions)</td></tr>" + "".join(rows) + "</table>"


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
    assert [(r["figure"], r["unit"]) for r in audit["restored"]] == [("$" + a, "million") for a in WMT_AMOUNTS]
    assert all(r["slot"] == "balance_sheet_liquidity.maturities_covenants[0]" for r in audit["restored"])


def test_the_synthetic_schedule_matches_the_retained_source_shape():
    sections = _sections()
    audit = restore_table_cell_units(sections, build_table_unit_index(_document(_schedule())))
    assert sections["balance_sheet_liquidity"]["maturities_covenants"] == [WMT_RESTORED]
    assert audit["restored_count"] == 7 and audit["unresolved"] == []


@pytest.mark.parametrize("text, expected", [
    (WMT_BULLET, {"years": [2027, 2028, 2029, 2030, 2031], "amounts": list(WMT_AMOUNTS)}),
    ("Maturities of long-term debt are as follows: 2027: $3,542; 2028: $3,237; 2029: $3,389; 2030: $2,143; "
     "2031: $2,600; Thereafter: $23,255; Total: $38,166", {"years": [2027, 2028, 2029, 2030, 2031], "amounts": list(WMT_AMOUNTS)}),
    ("Contractual maturities of our long-term debt over the next five fiscal years and thereafter were as follows: "
     "2027: $3,542; 2028: $3,237; 2029: $3,389; 2030: $2,143; 2031: $2,600; Thereafter: $23,255; Total: $38,166.",
     {"years": [2027, 2028, 2029, 2030, 2031], "amounts": list(WMT_AMOUNTS)}),
    # Root round 6: a year or "Total" label under any other subject is not this proposition.
    ("Expected registration fees by year are as follows: 2027: $3,542; 2028: $3,237.", None),
    ("Registration fees: Total: $38,166.", None),
    # An unsupported qualifier, another subject, a reorder, a partial or already-scaled sequence, or
    # trailing text is not this proposition.
    ("As of January 31, 2026, annual maturities of long-term debt are as follows: 2027: $3,542; 2028: $3,237; "
     "2029: $3,389; 2030: $2,143; 2031: $2,600; Thereafter: $23,255; Total: $38,166.", None),
    ("Maturities of operating lease obligations are as follows: 2027: $3,542; 2028: $3,237; 2029: $3,389; "
     "2030: $2,143; 2031: $2,600; Thereafter: $23,255; Total: $38,166.", None),
    ("Maturities of long-term debt are as follows: 2028: $3,237; 2027: $3,542; 2029: $3,389; 2030: $2,143; "
     "2031: $2,600; Thereafter: $23,255; Total: $38,166.", None),
    ("Maturities of long-term debt are as follows: 2027: $3,542; 2028: $3,237; Thereafter: $23,255; Total: $38,166.", None),
    (WMT_BULLET.replace("2028: $3,237;", "2028: $3,237 million;"), None),
    (WMT_BULLET + " These amounts exclude leases.", None),
    ("The registration fee was $3,237.", None),
])
def test_only_the_complete_maturity_sequence_is_a_proposition(text, expected):
    parsed = maturity_proposition(text)
    if expected is None:
        assert parsed is None
    else:
        assert {"years": parsed["years"], "amounts": parsed["amounts"]} == expected
        assert [text[e - len("$" + a):e] for a, e in zip(parsed["amounts"], parsed["ends"])] == ["$" + a for a in parsed["amounts"]]


@pytest.mark.parametrize("prose, count", [
    # Root round 6: the reproductions that bound debt-maturity facts to unrelated prose.
    ("Expected registration fees by year are as follows: 2027: $3,542; 2028: $3,237.", 2),
    ("Registration fees: Total: $38,166.", 1),
    # Round 5's counterexamples remain outside the proposition.
    ("Registration fee: $3,542.", 1),
    ("The registration fee was $3,237.", 1),
    ("• Registration fee:  $3,237", 1),
    ("Net sales increased $7,189 or 12%.", 1),
    # An unsupported qualifier or a partial / reordered / trailing-text sequence.
    ("As of January 31, 2026, annual maturities of long-term debt are as follows: 2027: $3,542; 2028: $3,237; "
     "2029: $3,389; 2030: $2,143; 2031: $2,600; Thereafter: $23,255; Total: $38,166.", 7),
    ("Maturities of long-term debt are as follows: 2027: $3,542; 2028: $3,237; Thereafter: $23,255; Total: $38,166.", 4),
    (WMT_BULLET + " These amounts exclude leases.", 7),
])
def test_everything_but_the_proposition_stays_as_written(prose, count):
    sections = _sections(prose)
    audit = restore_table_cell_units(sections, build_table_unit_index(WMT_SOURCE))
    assert sections["balance_sheet_liquidity"]["maturities_covenants"] == [prose]
    assert audit["restored"] == [] and audit["unresolved_count"] == count
    assert {u["reason"] for u in audit["unresolved"]} == {"unsupported_proposition"}


@pytest.mark.parametrize("reason, source", [
    # A schedule concept missing on the report period, or the total missing.
    ("missing_fact", _document(_schedule(skip=(2,)))),
    ("missing_fact", _document(_schedule(skip=(6,)))),
    # Two facts for one concept on the period disagree; identical repeats are the same fact.
    ("conflicting_facts", _document(_schedule() + "<table><tr><td>2027</td><td>"
                                    + _fact(DEBT_MATURITY_SEQUENCE[0], "3,552") + "</td></tr></table>")),
    # The source amount differs from the authored one.
    ("amount_mismatch", _document(_schedule(("3,552", "3,237", "3,389", "2,143", "2,600", "23,255", "38,166")))),
    # The fact sits in a row that is not the schedule row of that label.
    ("row_label_mismatch", _document(_schedule(labels=("Fiscal 2027", "2028", "2029", "2030", "2031", "Thereafter", "Total")))),
    # A non-dollar unit, a scale-0 fact, an unsupported scale, or mixed scales.
    ("non_dollar_unit", _document(_schedule(overrides={1: {"unit": "usdPerShare"}}))),
    ("declared_unscaled", _document(_schedule(overrides={1: {"scale": "0"}}))),
    ("unsupported_scale", _document(_schedule(overrides={1: {"scale": "2"}}))),
    ("mixed_scales", _document(_schedule(overrides={1: {"scale": "3"}}))),
    # Facts on another period, and a filing without a validated DEI period.
    ("missing_fact", _document(_schedule(context="c-prior"), extra_contexts=CONTEXT.format(id="c-prior", date="2025-01-31"))),
    ("no_report_period", _schedule()),
    # The authored first year is not the fiscal year after the report period.
    ("year_mismatch", _document(_schedule(labels=("2028", "2029", "2030", "2031", "2032", "Thereafter", "Total")), period="2027-01-31")),
    # The six schedule amounts do not sum to the total the source tags.
    ("sequence_does_not_sum", _document(_schedule(("3,542", "3,237", "3,389", "2,143", "2,600", "23,255", "38,167")))),
    # The flattened excerpt carries no DEI period and no fact at all.
    ("no_report_period", WMT_EXCERPT),
])
def test_the_source_must_own_every_part_of_the_sequence(reason, source):
    bullet = WMT_BULLET
    if reason == "year_mismatch":
        bullet = WMT_BULLET.replace("2027", "2029").replace("2028", "2030").replace("2029: $3,389", "2031: $3,389") \
            .replace("2030: $2,143", "2032: $2,143").replace("2031: $2,600", "2033: $2,600")
    if reason == "sequence_does_not_sum":
        bullet = WMT_BULLET.replace("$38,166", "$38,167")
    sections = _sections(bullet)
    audit = restore_table_cell_units(sections, build_table_unit_index(source))
    assert sections["balance_sheet_liquidity"]["maturities_covenants"] == [bullet]
    assert audit["restored"] == [] and audit["unresolved_count"] == 7
    assert {u["reason"] for u in audit["unresolved"]} == {reason}


def test_repeated_identical_facts_are_one_fact():
    # The retained WMT total (us-gaap:LongTermDebt, 38,166) is tagged in the debt table and again in
    # the schedule; repeats that agree are the same fact and the schedule row still binds.
    repeated = _document(_schedule() + "<table><tr><td>Total debt</td><td>" + _fact(DEBT_MATURITY_TOTAL, "38,166")
                         + "</td></tr></table>")
    sections = _sections()
    audit = restore_table_cell_units(sections, build_table_unit_index(repeated))
    assert sections["balance_sheet_liquidity"]["maturities_covenants"] == [WMT_RESTORED]
    assert audit["restored_count"] == 7


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
    # A standardized XBRL value equal to one literal figure means the bare reading is source-supported.
    sections = _sections()
    literal = {"dividends_paid": {"current": {"value": 3_542.0}}}
    audit = restore_table_cell_units(sections, build_table_unit_index(WMT_SOURCE), xbrl_metrics=literal)
    assert sections["balance_sheet_liquidity"]["maturities_covenants"] == [WMT_BULLET]
    assert {u["reason"] for u in audit["unresolved"]} == {"literal_xbrl_match"} and audit["unresolved_count"] == 7


def test_xbrl_corroboration_is_recorded_when_a_scaled_value_is_standardized():
    sections = _sections()
    corroborating = {"long_term_debt": {"current": {"value": 38_166_000_000.0}}}
    audit = restore_table_cell_units(sections, build_table_unit_index(WMT_SOURCE), xbrl_metrics=corroborating)
    assert sections["balance_sheet_liquidity"]["maturities_covenants"] == [WMT_RESTORED]
    assert [r["xbrl_corroborated"] for r in audit["restored"]] == [False] * 6 + [True]
    assert audit["restored"][-1] == {"slot": "balance_sheet_liquidity.maturities_covenants[0]",
                                     "figure": "$38,166", "unit": "million", "xbrl_corroborated": True}


def test_recovered_sections_verbatim_fields_and_missing_source_are_untouched():
    index = build_table_unit_index(WMT_SOURCE)
    recovered = _sections()
    audit = restore_table_cell_units(recovered, index, recovered={"balance_sheet_liquidity"})
    assert recovered["balance_sheet_liquidity"]["maturities_covenants"] == [WMT_BULLET]
    assert audit["restored"] == [] and {u["reason"] for u in audit["unresolved"]} == {"recovered"}
    # supporting_evidence is a verbatim trace-to-source surface: never rewritten, even beside a
    # proposition slot the owner restores.
    evidence = _sections("Nothing bare here.", notable_footnotes=[
        {"item": "Maturities", "impact": WMT_BULLET, "supporting_evidence": "Total$38,166"}])
    restore_table_cell_units(evidence, index)
    assert evidence["notable_footnotes"][0]["supporting_evidence"] == "Total$38,166"
    assert evidence["notable_footnotes"][0]["impact"] == WMT_RESTORED
    assert build_table_unit_index("") is None
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
    years = [2027, 2028, 2029, 2030, 2031]
    assert index.resolve_maturity_sequence(years, WMT_AMOUNTS) == ("million", "declared")
    assert index.resolve_maturity_sequence(years, WMT_AMOUNTS) == ("million", "declared")  # cached
    assert index.resolve_maturity_sequence(years, ("3,542", "3,237", "3,389", "2,143", "2,600", "23,255", "1")) == (None, "amount_mismatch")
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
        earnings_quality={"operating_vs_one_time": WMT_BULLET},
        value_drivers={"capital_allocation": WMT_BULLET, "highlights": [WMT_BULLET]},
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
    assert final_markdown == result["business_overview"] and final_markdown.count(WMT_RESTORED) == 1
    preview = service._partial_markdown_preview(
        json.dumps(structured), WMT_XBRL, statement_source=_statement_source(),
        unit_index=build_table_unit_index(WMT_SOURCE))
    assert preview and preview.count(WMT_RESTORED) == 1


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
