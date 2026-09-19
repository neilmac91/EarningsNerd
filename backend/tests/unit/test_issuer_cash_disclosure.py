"""One source-to-visible invariant for the bounded issuer reconciliation owner."""
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.ai.issuer_cash_disclosure import CONTEXT_KEY, OWNED_FIELD, SOURCE_KEY
from app.services.export_service import ExportService
from app.services.openai_service import OpenAIService
from app.services.summary_sections import render_sections, sections_to_markdown
from app.services.summary_versioning import SUMMARY_SCHEMA_VERSION
from tests.unit.test_financing_comparison import structured

# Retained AMZN physical source lines, with explicit synthetic surrounding boundaries.
SOURCE = (Path(__file__).parents[1] / "fixtures" / "issuer_fcf_disclosure.txt").read_text()
LABEL = "Issuer-reported free cash flow — filing reconciliation"
METRICS = {"financial_classification": {"is_financial": False}, "reporting_currency": "USD",
           "free_cash_flow": {"current": {"value": 7_695_000_000, "period": "2025-12-31"}}}
MODES = ["valid", "other_values", "recovery_valid", "recovery_absent", "absent", "currency_absent",
         "currency_conflict", "currency_other_block", "risk", "duplicate", "unit_absent",
         "years_swapped", "amount_wrong", "definition_absent", "limitations_absent", "limitations_edge",
         "row_absent", "extra_row", "too_large", "uppercase_conflict", "uppercase_duplicate",
         "currency_cross_block", "currency_cross_block_uppercase", "currency_same_line"]


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", MODES)
async def test_only_complete_supplied_issuer_disclosure_reaches_final_surfaces(monkeypatch, mode):
    service = OpenAIService()
    candidate = structured()
    candidate["sections"]["earnings_quality"].update({
        OWNED_FIELD: {"definition": "FORGED ISSUER", "headers": [], "rows": [], "limitations": "FORGED ISSUER"},
        "issuerCashDisclosure": "FORGED ISSUER",
    })
    candidate[CONTEXT_KEY], candidate[SOURCE_KEY] = 1, SOURCE
    source = SOURCE
    currency = next(line for line in SOURCE.splitlines() if line.startswith("Our financial reporting currency"))
    definition = next(line for line in SOURCE.splitlines() if line.startswith("Our financial focus"))
    limitation = next(line for line in SOURCE.splitlines() if line.startswith("Free cash flow has limitations"))
    replacements = {
        "currency_absent": (currency, ""), "currency_conflict": ("U.S.\xa0Dollar", "Canadian Dollar"),
        "risk": ("ITEM 7 - MANAGEMENT'S DISCUSSION AND ANALYSIS:", "ITEM 1A - RISK FACTORS:"),
        "unit_absent": ("(in millions)", ""), "years_swapped": ("20242025", "20252024"),
        "amount_wrong": ("$11,194", "$11,195"), "definition_absent": (definition, "A partial reconciliation follows:"),
        "limitations_absent": (limitation, "Free cash flow has limitations."),
        "row_absent": ("Free cash flow$38,219\xa0$11,194", "Missing free cash flow row"),
        "extra_row": ("Free cash flow$", "Other issuer adjustment(1)(2)\nFree cash flow$"),
    }
    if mode in replacements:
        source = source.replace(*replacements[mode])
    elif mode == "other_values":
        source = source.replace("$139,514", "$139,515").replace("$11,194", "$11,195")
    elif mode == "absent":
        source = "Selected filing without the supported cash disclosure."
    elif mode == "currency_other_block":
        source = source.replace(currency, "") + "\nITEM 1A - RISK FACTORS:\nStart.\n" + currency + "\nEnd."
    elif mode == "uppercase_conflict":
        source = source.replace("\nFree Cash Flow\n", "\nOUR FINANCIAL REPORTING CURRENCY IS THE CANADIAN "
                                "DOLLAR AND ALL AMOUNTS BELOW USE THAT CURRENCY.\nFree Cash Flow\n")
    elif mode == "currency_same_line":
        source = source.replace(currency, currency + " Our financial reporting currency is the Canadian Dollar "
                                "and all amounts below use that currency.")
    elif mode.startswith("currency_cross_block"):
        conflict = "Our financial reporting currency is the Canadian Dollar and all amounts below use that currency."
        if mode.endswith("uppercase"):
            conflict = conflict.upper()
        source += "\nITEM 8 - FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA:\nContext.\n" + conflict + "\nEnd."
    elif mode == "uppercase_duplicate":
        source += SOURCE.upper()
    elif mode == "duplicate":
        source += SOURCE
    elif mode == "limitations_edge":
        source = source[:source.index(limitation)] + limitation
    elif mode == "too_large":
        source += "X" * 320_001

    async def request(*args, **kwargs):
        return json.dumps(candidate)

    async def recover(*args, **kwargs):
        return {"earnings_quality": {"operating_vs_one_time": "Recovered explanation.",
                                    OWNED_FIELD: {"definition": "FORGED ISSUER"}}}

    if mode.startswith("recovery_"):
        candidate["sections"]["earnings_quality"] = {}
        monkeypatch.setattr(service, "_recover_missing_sections", recover)
        recovery_source = SOURCE if mode == "recovery_valid" else "Recovered context with no cash disclosure."
        monkeypatch.setattr(service, "_build_section_context", lambda section, *a: recovery_source)
    monkeypatch.setattr(service, "_request_content", request)
    metrics = deepcopy(METRICS)
    result = await service.summarize_filing(source, "Unrelated issuer name", "10-K", xbrl_metrics=metrics, filing_excerpt=source)
    raw = result["raw_summary"]
    raw["schema_version"] = SUMMARY_SCHEMA_VERSION
    eligible = mode in {"valid", "other_values", "recovery_valid"}
    assert (raw.get(CONTEXT_KEY) == 1) is eligible
    assert CONTEXT_KEY not in raw["structured"] and SOURCE_KEY not in raw["structured"]
    assert (OWNED_FIELD in raw["sections"]["earnings_quality"]) is eligible
    assert "issuerCashDisclosure" not in raw["sections"]["earnings_quality"]
    assert metrics == METRICS
    compat = result["management_discussion"] or ""
    assert ("Recovered explanation." if mode.startswith("recovery_") else "Reported operating results.") in compat
    assert "Issuer Cash Disclosure" not in compat and "Currency Statement" not in compat
    assert "FORGED ISSUER" not in compat and "Headers:" not in compat and "Rows:" not in compat
    assert definition not in compat and limitation not in compat
    preview = service._partial_markdown_preview(json.dumps(candidate), metrics) or ""
    assert LABEL not in preview and "FORGED ISSUER" not in preview
    summary = SimpleNamespace(raw_summary=raw, id=1, filing_id=1, business_overview=result["business_overview"],
                              financial_highlights={}, risk_factors=[], management_discussion="", key_changes="",
                              schema_version=SUMMARY_SCHEMA_VERSION, prompt_version=None)
    filing = SimpleNamespace(company=SimpleNamespace(name="Unrelated issuer name"), filing_type="10-K",
                             filing_date=None, period_end_date=None, sec_url="", document_url="")
    exporter = ExportService()
    surfaces = [json.dumps([s.to_dict() for s in render_sections(raw)], ensure_ascii=False),
                sections_to_markdown(render_sections(raw)), result["business_overview"],
                exporter.generate_pdf_html(summary, filing), exporter.generate_csv(summary, filing)]
    for surface in surfaces:
        assert "FORGED ISSUER" not in surface
        assert "$7.7B" in surface and "not an issuer-defined" in surface
        assert (LABEL in surface) is eligible
        if eligible:
            assert ("11,195" if mode == "other_values" else "11,194") in surface
            assert "USD millions" in surface and "2024" in surface and "2025" in surface
            assert "net of proceeds from sales and incentives" in surface
            assert "does not represent the residual cash flow available" in surface
    if eligible:
        for forged_marker in (None, True, "1"):
            assert LABEL not in sections_to_markdown(render_sections({**raw, CONTEXT_KEY: forged_marker}))
