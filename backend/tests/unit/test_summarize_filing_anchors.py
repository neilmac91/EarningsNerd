"""Wave 0 anchors (O0) for the openai_service.py refactor (tasks/refactor-plan-2026-10.md, M4).

Characterization pins at the two seams the refactor cuts: O1 moves ``summarize_filing``'s post-provider
phases into ``ai/summary_finalize.py`` (A2-A6) and O2 moves the primary prompt assembly into
``ai/summary_prompt.py`` (A1). They pin what the code does TODAY, so neither move can silently change the
provider request or the returned shape. No provider call is made: each test builds a fresh
``OpenAIService`` (never the ``openai_service`` singleton) and fakes its boundary per instance — a fake
client, or ``_request_content`` / ``generate_structured_summary`` replaced on that instance — and every
setting that decides what they observe is pinned on the shared ``settings`` object. Nothing is patched on
the façade module's namespace, so no anchor here needs a re-point when O1/O2 move code.

A1 is the eval tripwire for O2 and for every later prompt rider. Its fixtures under
``tests/fixtures/summarize_filing_anchors/`` hold each case's full ``create_kwargs`` (every message's
content split into lines, so a diff shows the changed prompt line) plus the shape of the
``_request_content`` call. A byte change there is a RUNBOOK event (backend/evals/RUNBOOK.md, "Re-pinning
the baseline", :530-535): it never rides a refactor PR. The default run only READS the fixtures. After a
deliberate prompt or model change, regenerate them with this one-off command:

    cd backend && SUMMARIZE_FILING_ANCHORS_REGENERATE=1 python -m pytest tests/unit/test_summarize_filing_anchors.py -k test_a1 -p no:cacheprovider

Each A1 case then rewrites its own file and FAILS by design, so a regeneration run can never pass: re-run
without the variable, review ``git diff backend/tests/fixtures/summarize_filing_anchors/``, and commit the
files with the eval evidence the RUNBOOK asks for. The snapshot does not depend on the environment or the
clock: the model and every flag are pinned below, and nothing on the assembly path reads the clock (the
prompt embeds no date today; a rider that adds one must freeze it here).
"""
import copy
import difflib
import gzip
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config import settings
from app.services.ai.source_units import TableUnitIndex
from app.services.openai_service import OpenAIService

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
_A1_DIR = _FIXTURES / "summarize_filing_anchors"
_REGENERATE = "SUMMARIZE_FILING_ANCHORS_REGENERATE"
_REGENERATE_COMMAND = (f"cd backend && {_REGENERATE}=1 python -m pytest "
                       "tests/unit/test_summarize_filing_anchors.py -k test_a1 -p no:cacheprovider")

# Code defaults for the settings that decide what these anchors observe (openai_service.py:120-137, 170, 396,
# 656, 799, 813, 852-853; provider_requests.py:150, 248), with the model pinned to an explicit name, so a
# developer .env or another test cannot move a pin.
_PINNED_SETTINGS = {
    "AI_DEFAULT_MODEL": "anchor-pinned-model", "AI_FAST_MODEL": "", "AI_SECTION_RECOVERY_MODEL": "",
    "AI_FALLBACK_MODEL": "", "AI_FALLBACK_BASE_URL": "", "AI_FALLBACK_API_KEY": "",
    "AI_SUMMARY_THINKING_EFFORT": "", "USE_STRUCTURED_OUTPUT": False, "AI_FORWARD_QUOTE_GATE": False,
    "AI_ATTRIBUTION_VERIFY": False, "AI_ATTRIBUTION_GATE": False, "AI_EVIDENCE_SNAP": False,
    "EVIDENCE_SNAP_MIN_SCORE": 72.0,
}


@pytest.fixture(autouse=True)
def _pinned_settings(monkeypatch):
    for name, value in _PINNED_SETTINGS.items():
        monkeypatch.setattr(settings, name, value)


async def _receive(_frame):
    return None


def _streaming_service(monkeypatch, payload, recovered=None):
    """A fresh service whose fake client streams ``payload`` as one chunk (test_sixk_variant_wiring.py:13-22)."""
    service = OpenAIService()
    encoded = json.dumps(payload)

    async def chunks():
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=encoded))])

    service.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=AsyncMock(return_value=chunks()))))
    service.fallback_client = None
    monkeypatch.setattr(service, "_recover_missing_sections", AsyncMock(return_value=recovered or {}))
    return service


def _injected_service(monkeypatch, structured):
    """A fresh service whose primary extraction returns ``structured`` as-is (no assembly, no fallbacks)."""
    service = OpenAIService()
    service.fallback_client = None
    monkeypatch.setattr(service, "generate_structured_summary", AsyncMock(return_value=copy.deepcopy(structured)))
    return service


def _model_sections():
    """A complete v2 payload as the model writes it: seven sections survive the post-provider owners."""
    return {
        "the_print": {"headline": "Revenue rose 13.6% to $1.25B.", "key_takeaways": ["Revenue rose 13.6%."],
                      "what_changed": "Revenue increased.", "tone": "positive", "source_section_ref": "Item 7"},
        "results_that_matter": {"table": [{
            "metric": "Revenue", "current_period": "$1.25B", "prior_period": "$1.10B", "change": "+13.6%",
            "commentary": "Higher cloud demand.", "supporting_evidence": ""}], "source_section_ref": "Item 8"},
        "earnings_quality": {"operating_vs_one_time": "Operating results drove earnings.", "red_flags": [],
                             "source_section_ref": "Item 8"},
        "value_drivers": {"capital_allocation": {"filing_statements": []}, "highlights": [],
                          "source_section_ref": "Item 7"},
        "forward_signals": {"guidance": "Not given.", "known_trends": ["Cloud demand."], "subsequent_events": [],
                            "quotes": [], "tone": "neutral", "source_section_ref": "Item 7"},
        "risks": [],
        "segments": [{"segment": "Cloud", "commentary": "Grew."}],
        "balance_sheet_liquidity": {"leverage": "Low debt.", "liquidity": "Ample cash.", "working_capital": "Stable.",
                                    "maturities_covenants": [], "source_section_ref": "Liquidity"},
        "notable_footnotes": [{"item": "Leases", "impact": "Minor.", "supporting_evidence": "",
                               "source_section_ref": "Note 7"}],
    }


# ---------------------------------------------------------------------------------------------------------
# A1 — provider-request snapshot
# ---------------------------------------------------------------------------------------------------------

# Every EXTRACTED FINANCIAL SIGNALS line is populated, with more values than each slice keeps, and no two
# values of one signal tie (extract_financial_data de-duplicates through a set, so a tie would order by hash).
_A1_EXCERPT = (
    "ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS\n"
    "Total revenue of $1,250.4 million increased 13.6% from $1,100.2 million in 2024.\n"
    "Subscription revenue of $812.7 million and services revenue of $437.7 million both grew.\n"
    "Net income of $210.5 million compared with net income of $180.3 million.\n"
    "Cash flow from operations $320.9 million; free cash flow $255.1 million.\n"
    "Americas net sales $700.6 million; Europe net sales $549.8 million.\n"
    "We expect fiscal 2026 revenue of $1,400.0 million and reaffirm guidance of $4.15 per share "
    "and guidance for $2.90 of dividends.\n"
    "ITEM 1A. RISK FACTORS\n"
    "A small number of customers account for a large share of our revenue.\n"
)
# A 6-K exhibit with no extractable signal and no XBRL: the "Not observed" and no-grounding-block branches.
_A1_SPARSE_EXCERPT = (
    "Exhibit 99.1\n"
    "Anchor Holdings plc announces the results of its annual general meeting.\n"
    "All resolutions proposed at the meeting were passed by shareholders.\n"
)
_A1_XBRL = {
    "revenue": {"current": {"value": 1_250_400_000, "period": "2025-12-31"},
                "prior": {"value": 1_100_200_000, "period": "2024-12-31"}},
    "net_income": {"current": {"value": 210_500_000, "period": "2025-12-31"},
                   "prior": {"value": 180_300_000, "period": "2024-12-31"}},
    "operating_cash_flow": {"current": {"value": 320_900_000, "period": "2025-12-31"}},
}
# The full source document, kept distinct from every excerpt, as summary_pipeline.py:1015-1021 passes them: the
# prompt reads only the excerpt, while the unit index reads only the document. A swap of either provenance changes
# the snapshot (the sentinel line enters the prompt, or a keyword names the other argument).
_A1_RAW_DOCUMENT = ("<html><body><p>RAW SOURCE DOCUMENT SENTINEL: this line reaches the provider request only if "
                    "the raw document replaces the excerpt.</p></body></html>")
_A1_CASES = [(form, sixk_class, structured)
             for form, sixk_class in (("10-K", None), ("10-Q", None), ("20-F", None), ("6-K", "governance"))
             for structured in (False, True)]


def _a1_case_id(form, sixk_class, structured):
    return f"{form}{'-' + sixk_class if sixk_class else ''}-structured-{'on' if structured else 'off'}"


def _a1_readable(create_kwargs):
    """``create_kwargs`` with each message's content as a list of lines (lossless: split/join on newline)."""
    view = copy.deepcopy(create_kwargs)
    for message in view["messages"]:
        if isinstance(message.get("content"), str):
            message["content_lines"] = message.pop("content").split("\n")
    return view


def _a1_describe(value, excerpt, xbrl):
    if isinstance(value, str) and value == _A1_RAW_DOCUMENT:
        return "<filing_text argument>"
    if isinstance(value, str) and value == excerpt:
        return "<filing_excerpt argument>"
    if isinstance(value, TableUnitIndex):  # named by the source it holds: its provenance is the pin
        return f"<TableUnitIndex over {_a1_describe(value._html, excerpt, xbrl)}>"
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict) and value == xbrl:
        return "<xbrl_metrics argument>"
    return f"<{type(value).__name__}>"


@pytest.mark.asyncio
@pytest.mark.parametrize(("form", "sixk_class", "structured"), _A1_CASES,
                         ids=[_a1_case_id(*case) for case in _A1_CASES])
async def test_a1_primary_provider_request_matches_snapshot(monkeypatch, tmp_path, form, sixk_class, structured):
    """A1 — pins backend/app/services/openai_service.py:261-456 (prompt assembly and the full create_kwargs:
    messages, model, temperature, max_tokens, response_format) and :458-469 (the ``_request_content`` call),
    for 10-K, 10-Q, 20-F and a classified 6-K under USE_STRUCTURED_OUTPUT off and on (:396-399, :453).
    Strict: a one-byte change anywhere in the request fails. Existing coverage is substring-only
    (test_structured_output_flag.py:36-76, test_xbrl_narrative_section.py:359-400,
    test_sixk_variant_wiring.py:26-47)."""
    case_id = _a1_case_id(form, sixk_class, structured)
    monkeypatch.setattr(settings, "USE_STRUCTURED_OUTPUT", structured)
    service = OpenAIService()
    request = AsyncMock(return_value="{}")
    monkeypatch.setattr(service, "_request_content", request)
    monkeypatch.setattr(service, "_assemble_structured_summary", AsyncMock(return_value={}))
    excerpt, xbrl = (_A1_SPARSE_EXCERPT, None) if form == "6-K" else (_A1_EXCERPT, copy.deepcopy(_A1_XBRL))
    await service.generate_structured_summary(_A1_RAW_DOCUMENT, "Anchor Holdings Inc.", form, xbrl,
                                              filing_excerpt=excerpt,
                                              **({"sixk_class": sixk_class} if sixk_class else {}))
    request.assert_awaited_once()
    call = request.await_args
    document = {
        "note": ("Generated by backend/tests/unit/test_summarize_filing_anchors.py (A1); never hand-edit. A byte "
                 "change is a RUNBOOK event (backend/evals/RUNBOOK.md). Regenerate: " + _REGENERATE_COMMAND),
        "case": {"filing_type": form, "sixk_class": sixk_class, "use_structured_output": structured},
        "create_kwargs": _a1_readable(call.args[0]),
        "request_content_call": {
            "positional_args": len(call.args),
            "keywords": {key: _a1_describe(value, excerpt, xbrl) for key, value in call.kwargs.items()},
        },
    }
    actual = json.dumps(document, indent=1, ensure_ascii=False, sort_keys=True) + "\n"
    fixture = _A1_DIR / f"{case_id}.json"
    if os.environ.get(_REGENERATE) == "1":
        fixture.write_text(actual, encoding="utf-8")
        pytest.fail(f"A1 fixture regenerated at {fixture}; this run fails by design. Re-run without {_REGENERATE}, "
                    "review the git diff, and commit it only with the RUNBOOK's eval evidence.")
    if not fixture.is_file():
        pytest.fail(f"A1 fixture missing: {fixture}. Generate it deliberately with: {_REGENERATE_COMMAND}")
    expected = fixture.read_text(encoding="utf-8")
    if actual != expected:
        dump = tmp_path / f"{case_id}.actual.json"
        dump.write_text(actual, encoding="utf-8")
        diff = "".join(list(difflib.unified_diff(expected.splitlines(True), actual.splitlines(True),
                                                 str(fixture), str(dump), n=1))[:80])
        pytest.fail(
            f"A1 provider-request snapshot changed for {case_id}. The primary summary request "
            "(messages, model, temperature, max_tokens, response_format) must be byte-identical across a "
            "refactor; a byte change is a RUNBOOK event (backend/evals/RUNBOOK.md, 'Re-pinning the baseline') "
            f"and never rides a refactor PR. If the change is deliberate, regenerate with: {_REGENERATE_COMMAND}\n"
            f"Actual request written to: {dump}\n{diff}"
        )


def test_a1_fixture_directory_holds_exactly_the_snapshot_cases():
    """A1 — no stale or unclaimed snapshot: the fixture directory is exactly one file per A1 case."""
    assert sorted(p.name for p in _A1_DIR.iterdir()) == sorted(f"{_a1_case_id(*case)}.json" for case in _A1_CASES)


# ---------------------------------------------------------------------------------------------------------
# A2 — return shape
# ---------------------------------------------------------------------------------------------------------

_RESULT_KEYS = {"summary_title", "sections", "insights", "status", "business_overview", "financial_highlights",
                "risk_factors", "management_discussion", "key_changes", "raw_summary",
                "_risk_source_candidates", "_risk_source_grounding"}
# Always present in raw_summary, with their versions (openai_service.py:1006-1009, :1011-1013).
_RAW_ALWAYS = {"source_unit_context_version": 1, "capital_allocation_context_version": 1,
               "metric_delta_context_version": 1, "risk_source_context_version": 1}
_RAW_STRUCTURAL = {"structured", "sections", "section_coverage"}
_RAW_VERSIONED = {"acquisition_period_context_version", "statement_relationship_context_version",
                  "issuer_cash_disclosure_context_version"}
_SIXK_AUDIT = {"class": "earnings", "earnings_cues": 4, "governance_cues": 0, "money_tokens": 6,
               "regulatory_return": False}
_A2_EXCERPT = (
    "Item 2. Management's Discussion and Analysis\n"
    "Revenue increased to $1,250 million, driven by higher cloud subscriptions.\n"
    "Our chief executive officer said, \"We expect demand for our platform to remain durable through 2026.\"\n"
    "Item 1A. Risk Factors\n"
    "Customer concentration could reduce our revenue if a large customer leaves.\n"
)


def _a2_bare():
    return {"form": "10-K", "text": "Selected filing text.", "sections": _model_sections()}


def _a2_partial():
    sections = _model_sections()
    return {"form": "10-K", "text": "Selected filing text.",
            "sections": {key: sections[key] for key in ("the_print", "results_that_matter")}}


def _a2_measured_6k(audit):
    """A 6-K whose excerpt grounds a quote, a causal clause and an evidence span, plus one bare dollar figure."""
    sections = _model_sections()
    sections["the_print"].update(headline="Revenue reached $1,250 in the period.",
                                 what_changed="Revenue increased due to higher cloud subscriptions.")
    sections["results_that_matter"]["table"][0]["supporting_evidence"] = (
        "Revenue increased to $1,250 million, driven by higher cloud subscriptions.")
    sections["forward_signals"]["quotes"] = [{
        "speaker": "CEO", "quote": "We expect demand for our platform to remain durable through 2026.",
        "context": "MD&A"}]
    return {"form": "6-K", "text": _A2_EXCERPT, "excerpt": _A2_EXCERPT, "sections": sections,
            "sixk_class": "earnings", **({"sixk_class_audit": audit} if audit else {})}


def _a2_issuer_cash():
    """The retained issuer free-cash-flow reconciliation (test_issuer_cash_disclosure.py's source)."""
    source = (_FIXTURES / "issuer_fcf_disclosure.txt").read_text(encoding="utf-8")
    return {"form": "10-K", "text": source, "excerpt": source, "sections": _model_sections()}


def _a2_acquisition_and_statement():
    """The retained acquisition-period target note and source (acquisition_period_cases.py) plus a real
    annual operating-to-pretax statement source (test_statement_relationship_integration.py:451-454)."""
    from app.services.edgar.statement_context import acquire_statement_context

    data = json.loads(gzip.decompress((_FIXTURES / "acquisition_period" / "boundary-controls.json.gz").read_bytes()))
    sections = _model_sections()
    sections["notable_footnotes"] = [next(c for c in data["controls"] if c["name"] == "retained_target")["note"]]
    meli = gzip.decompress((_FIXTURES / "operating_pretax" / "meli-2025.html.gz").read_bytes()).decode()
    statement = acquire_statement_context(meli, accession="0001099590-26-000006",
                                          document_url="https://example.test/primary.htm", form="10-K",
                                          report_period="2025-12-31")
    assert statement is not None
    return {"form": "10-K", "text": data["base_source"], "excerpt": data["base_source"], "xbrl": data["base_metrics"],
            "statement_source": statement, "sections": sections}


def _a2_tax_and_reconciliation():
    """The retained FIGS 10-Q native source with its tax-rate note and reconciliation target, as
    test_statement_relationship_integration.py:55-176 and :242-367 drive them."""
    tax = json.loads((_FIXTURES / "tax_rate_comparison" / "retained-output.json").read_text(encoding="utf-8"))
    native = gzip.decompress((_FIXTURES / "tax_rate_comparison" / "figs-20260630.html.gz").read_bytes()).decode()
    controls = json.loads((_FIXTURES / "reconciliation_directions" / "retained-controls.json").read_text(encoding="utf-8"))
    sections = controls["raw_sections"]
    sections["earnings_quality"].pop("operating_vs_one_time", None)
    sections["earnings_quality"].update(next(c for c in controls["controls"] if c["name"] == "retained_target")["authored"])
    tax_note = next(n for n in tax["raw_sections"]["notable_footnotes"] if n["item"] == "Income Taxes")
    sections["notable_footnotes"] = [n for n in sections.get("notable_footnotes", []) if n.get("item") != "Income Taxes"]
    sections["notable_footnotes"].append(tax_note)
    return {"form": "10-Q", "text": native, "excerpt": tax["grounding_excerpt"], "sections": sections}


# (case, builder, message expected, raw_summary keys beyond the always-present ones). Each conditional key of
# openai_service.py:1003-1037 is absent in "bare" and present in at least one case; the dead writer keys
# (:964-966 are constant None, :1027-1032) are absent everywhere.
_A2_CASES = [
    ("bare", _a2_bare, False, set()),
    ("partial", _a2_partial, True, set()),
    ("measured-6-K", lambda: _a2_measured_6k(copy.deepcopy(_SIXK_AUDIT)), False,
     {"forward_quote_audit", "attribution_audit", "evidence_snap_audit", "table_cell_unit_audit", "sixk_class",
      "sixk_class_audit"}),
    ("6-K-class-without-audit", lambda: _a2_measured_6k(None), False,
     {"forward_quote_audit", "attribution_audit", "evidence_snap_audit", "table_cell_unit_audit", "sixk_class"}),
    ("issuer-cash", _a2_issuer_cash, False, {"issuer_cash_disclosure_context_version"}),
    ("acquisition-and-statement", _a2_acquisition_and_statement, False,
     {"acquisition_period_context_version", "statement_relationship_context_version", "evidence_snap_audit"}),
    ("tax-and-reconciliation", _a2_tax_and_reconciliation, False,
     {"tax_rate_explanation_audit", "reconciliation_direction_audit", "attribution_audit", "evidence_snap_audit",
      "forward_quote_audit"}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("builder", "expect_message", "raw_extra"), [case[1:] for case in _A2_CASES],
                         ids=[case[0] for case in _A2_CASES])
async def test_a2_result_and_raw_summary_key_sets(monkeypatch, builder, expect_message, raw_extra):
    """A2 — pins the exact key sets of summarize_filing's result, backend/app/services/openai_service.py:1210-1233
    (``message`` only when set, :1229-1231), and of its raw_summary, :1003-1037, including every conditional
    context/audit key reachable from the inputs (both branches across the cases), plus the insights
    (:1137-1141) and section_coverage (:902-912) shapes. Driven end to end through a fake streamed client."""
    case = builder()
    payload = {"metadata": {}, "sections": case["sections"]}
    service = _streaming_service(monkeypatch, payload)
    optional = {key: case[key] for key in ("xbrl", "statement_source", "sixk_class", "sixk_class_audit") if key in case}
    if "xbrl" in optional:
        optional["xbrl_metrics"] = optional.pop("xbrl")
    result = await service.summarize_filing(case["text"], "Anchor Co", case["form"], filing_excerpt=case.get("excerpt"),
                                            stream_cb=_receive, **optional)
    assert set(result) == _RESULT_KEYS | ({"message"} if expect_message else set())
    assert set(result["insights"]) == {"sentiment", "growth_drivers", "risk_signals"}
    raw = result["raw_summary"]
    assert set(raw) == set(_RAW_ALWAYS) | _RAW_STRUCTURAL | raw_extra
    assert {key: raw[key] for key in _RAW_ALWAYS} == _RAW_ALWAYS
    assert {key: raw[key] for key in _RAW_VERSIONED & raw_extra} == dict.fromkeys(_RAW_VERSIONED & raw_extra, 1)
    if "sixk_class" in raw_extra:
        assert raw["sixk_class"] == "earnings"
    if "sixk_class_audit" in raw_extra:
        assert raw["sixk_class_audit"] == _SIXK_AUDIT
    assert set(raw["section_coverage"]) == {"per_section", "covered", "missing", "covered_count", "total_count",
                                            "coverage_ratio", "not_applicable"}
    assert sorted(raw["section_coverage"]["per_section"]) == sorted(
        ("the_print", "results_that_matter", "earnings_quality", "value_drivers", "forward_signals", "risks",
         "segments", "balance_sheet_liquidity", "notable_footnotes"))


# ---------------------------------------------------------------------------------------------------------
# A3 — error envelope
# ---------------------------------------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize(("filing_type", "label"), [("20-f", "20-F"), (None, "10-K")])
async def test_a3_non_timeout_extraction_failure_error_envelope(filing_type, label):
    """A3 — pins the whole error envelope of backend/app/services/openai_service.py:714-734 for a
    non-timeout provider failure: message, the upper-cased summary_title, ``sections == []``, the neutral
    insights, the legacy keys and the 500-character detail cap. (Status/code/detail are also pinned by
    test_eval_attempt_diagnostics.py:291-323; timeout propagation, :711-713, is pinned elsewhere.)"""
    service = OpenAIService()
    failure = "anchor provider failure: " + "x" * 600
    service.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=AsyncMock(side_effect=RuntimeError(failure)))))
    service.fallback_client = None
    result = await service.summarize_filing("Selected filing text.", "Anchor Co", filing_type)
    assert result == {
        "status": "error",
        "message": "We couldn't generate this summary just now. Please try again shortly.",
        "summary_title": f"Anchor Co {label} Filing Summary",
        "sections": [],
        "insights": {"sentiment": "Neutral", "growth_drivers": [], "risk_signals": []},
        "business_overview": "Unable to retrieve this filing at the moment — please try again shortly.",
        "financial_highlights": {},
        "risk_factors": [],
        "management_discussion": "",
        "key_changes": "",
        "raw_summary": {"error": "structured_extraction_failed", "detail": failure[:500]},
    }


# ---------------------------------------------------------------------------------------------------------
# A4 — status and message thresholds
# ---------------------------------------------------------------------------------------------------------

_PRINT = {"headline": "Revenue rose 13.6% to $1.25B.", "tone": "neutral"}
_RESULTS = {"table": [{"metric": "Revenue", "current_period": "$1.25B", "prior_period": "$1.10B", "change": "+13.6%"}]}
_QUALITY = {"operating_vs_one_time": "Operating results drove earnings."}
_FORWARD = {"guidance": "Not given.", "known_trends": ["Cloud demand."], "tone": "neutral"}
_DRIVERS = {"source_section_ref": "Item 7. MD&A"}  # capital_allocation/highlights are source-owned (dropped here)
_SEGMENTS = [{"segment": "Cloud", "commentary": "Grew."}]
_LIQUIDITY = {"liquidity": "Cash covers maturities."}
_NOTES = [{"item": "Leases", "impact": "Lease costs were minor."}]
_CARDS = ["Financial Overview", "Management Commentary", "Strategic Developments"]
_PARTIAL = "Some sections may not have loaded fully."
_ERROR = "Unable to retrieve this filing at the moment — please try again shortly."
_A4_CASES = [
    # (case, sections, covered of 9, legacy card titles, status, message)
    ("0-covered-no-cards", {}, 0, [], "error", _ERROR),
    ("0-covered-one-card", {"earnings_quality": {"operating_vs_one_time": "Not disclosed"}}, 0,
     ["Management Commentary"], "partial",
     _PARTIAL + " Missing sections: balance_sheet_liquidity, earnings_quality, forward_signals"),
    ("1-covered-no-cards", {"the_print": _PRINT}, 1, [], "partial",
     _PARTIAL + " Missing sections: balance_sheet_liquidity, earnings_quality, forward_signals"),
    ("4-covered-below-0.5", {"the_print": _PRINT, "value_drivers": _DRIVERS, "balance_sheet_liquidity": _LIQUIDITY,
                             "notable_footnotes": _NOTES}, 4, [], "partial",
     _PARTIAL + " Missing sections: earnings_quality, forward_signals, results_that_matter"),
    ("5-covered-above-0.5-no-cards", {"the_print": _PRINT, "value_drivers": _DRIVERS, "segments": _SEGMENTS,
                                      "balance_sheet_liquidity": _LIQUIDITY, "notable_footnotes": _NOTES},
     5, [], "complete", None),
    ("5-covered-cards-below-0.7", {"the_print": _PRINT, "results_that_matter": _RESULTS, "earnings_quality": _QUALITY,
                                   "forward_signals": _FORWARD, "value_drivers": _DRIVERS}, 5, _CARDS, "partial", _PARTIAL),
    ("6-covered-cards-below-0.7", {"the_print": _PRINT, "results_that_matter": _RESULTS, "earnings_quality": _QUALITY,
                                   "forward_signals": _FORWARD, "value_drivers": _DRIVERS,
                                   "balance_sheet_liquidity": _LIQUIDITY}, 6, _CARDS, "partial", _PARTIAL),
    ("7-covered-cards-above-0.7", {"the_print": _PRINT, "results_that_matter": _RESULTS, "earnings_quality": _QUALITY,
                                   "forward_signals": _FORWARD, "value_drivers": _DRIVERS,
                                   "balance_sheet_liquidity": _LIQUIDITY, "notable_footnotes": _NOTES},
     7, _CARDS, "complete", None),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("sections", "covered", "cards", "status", "message"), [case[1:] for case in _A4_CASES],
                         ids=[case[0] for case in _A4_CASES])
async def test_a4_status_and_message_thresholds(monkeypatch, sections, covered, cards, status, message):
    """A4 — pins backend/app/services/openai_service.py:1182-1207 on both sides of each boundary (of nine
    tracked sections: 4|5 covered around ``< 0.5`` at :1190, 6|7 around ``< 0.7`` at :1204, and both conjuncts
    of the "error" rule at :1199). The structured summary is injected past the provider: through the real
    assembly the_print is always backfilled (markdown_render.py:320-334), so ``covered == 0`` is reachable
    only this way."""
    service = _injected_service(monkeypatch, {"metadata": {}, "sections": sections})
    result = await service.summarize_filing("Selected filing text.", "Anchor Co", "10-K")
    coverage = result["raw_summary"]["section_coverage"]
    assert (coverage["covered_count"], coverage["total_count"]) == (covered, 9)
    assert [card["title"] for card in result["sections"]] == cards
    assert result["status"] == status
    assert result.get("message") == message and ("message" in result) == (message is not None)


# ---------------------------------------------------------------------------------------------------------
# A5 — title derivation
# ---------------------------------------------------------------------------------------------------------

_A5_CASES = [
    # (case, filing_type argument, model metadata, summary_title)
    ("metadata-overrides-and-annual-date", "10-K", {"company_name": "Meta Name Inc.", "filing_type": "Form 10-K",
                                                     "reporting_period": "FY2025", "filing_date": "2026-02-15"},
     "Meta Name Inc. Form 10-K Filing Summary (FY2026)"),
    ("20-F-annual-date", "20-F", {"filing_date": "2026-04-30"}, "Anchor Co 20-F Filing Summary (FY2026)"),
    ("10-Q-march-is-Q1", "10-Q", {"filing_date": "2025-03-31"}, "Anchor Co 10-Q Filing Summary (Q1 2025)"),
    ("10-Q-april-is-Q2", "10-Q", {"filing_date": "2025-04-01"}, "Anchor Co 10-Q Filing Summary (Q2 2025)"),
    ("10-Q-december-zulu-is-Q4", "10-Q", {"filing_date": "2025-12-31T00:00:00Z"},
     "Anchor Co 10-Q Filing Summary (Q4 2025)"),
    ("unparseable-date-keeps-period", "10-Q", {"reporting_period": "Q3 2025", "filing_date": "September 2025"},
     "Anchor Co 10-Q Filing Summary (Q3 2025)"),
    ("6-K-keeps-period", "6-K", {"reporting_period": "H1 2025", "filing_date": "2025-09-30"},
     "Anchor Co 6-K Filing Summary (H1 2025)"),
    ("amendment-keeps-period", "10-K/A", {"reporting_period": "FY2025", "filing_date": "2026-03-01"},
     "Anchor Co 10-K/A Filing Summary (FY2025)"),
    ("lowercase-form-no-metadata", "10-q", {}, "Anchor Co 10-Q Filing Summary"),
    ("no-form-empty-period", None, {"reporting_period": ""}, "Anchor Co 10-K Filing Summary"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("filing_type", "metadata", "title"), [case[1:] for case in _A5_CASES],
                         ids=[case[0] for case in _A5_CASES])
async def test_a5_summary_title_derivation(monkeypatch, filing_type, metadata, title):
    """A5 — pins backend/app/services/openai_service.py:1039-1061: metadata company/label override the
    arguments, a parsed filing_date replaces the reporting period with FY<year> (10-K, 20-F only) or
    Q<n> <year> (10-Q, quarter boundaries and a trailing Z), an unparseable date keeps the period, and
    other forms (6-K, 10-K/A) keep the period."""
    service = _injected_service(monkeypatch, {"metadata": metadata, "sections": {"the_print": _PRINT}})
    result = await service.summarize_filing("Selected filing text.", "Anchor Co", filing_type)
    assert result["summary_title"] == title


# ---------------------------------------------------------------------------------------------------------
# A6 — aliasing invariant
# ---------------------------------------------------------------------------------------------------------

# Model-supplied top-level keys: the ones discarded by name (:977-985) and two that are not discarded today.
_A6_FORGED = {"source_unit_context_version": 1, "capital_allocation_context_version": 1,
              "issuer_cash_disclosure_context_version": 1, "statement_relationship_context_version": 1,
              "acquisition_period_context_version": 1, "primary_excerpt": "FORGED", "risk_source_context_version": 1,
              "_risk_source_candidates": ["FORGED"], "_risk_source_candidate_count": 9,
              "metric_delta_context_version": 7, "_model_note": "FORGED"}


@pytest.mark.asyncio
@pytest.mark.parametrize(("extra", "structured_keys"), [
    ({}, ["metadata", "schema_version", "sections"]),
    (_A6_FORGED, ["_model_note", "metadata", "metric_delta_context_version", "schema_version", "sections"]),
], ids=["clean-model-payload", "model-supplied-top-level-keys"])
async def test_a6_sections_aliasing_and_private_keys(monkeypatch, extra, structured_keys):
    """A6 — pins the aliasing invariant of backend/app/services/openai_service.py: one sections object is
    shared by raw_summary["structured"], raw_summary["sections"] (:749, :1011-1012) and the legacy
    financial_highlights/risk_factors (:760, :781, :1217-1218), which the in-place owners rely on
    (:754-755, :787-790, :875-882); and the application's own private keys, present when assembly hands over
    (_assemble_structured_summary :521-526, :550), are popped (:765, :832, :869, :873) so none reaches the
    top level of raw_summary["structured"]. The nested sections["_risk_source_projection"] (:782) is the
    sanctioned exception. Today a model-supplied top-level ``_`` key and metric_delta_context_version are
    NOT discarded (only the named keys at :765, :832, :869, :873 and :977-985 are); the second case pins that."""
    sections = _model_sections()
    sections["value_drivers"] = {}  # empty, so recovery runs and assembly records _recovered_sections
    service = _streaming_service(monkeypatch, {"metadata": {}, "sections": sections, **copy.deepcopy(extra)},
                                 recovered={"value_drivers": {"source_section_ref": "Item 7. MD&A"}})
    assembled = []
    real_assemble = service._assemble_structured_summary

    async def spy(*args, **kwargs):
        summary = await real_assemble(*args, **kwargs)
        assembled.append(sorted(summary))
        return summary

    monkeypatch.setattr(service, "_assemble_structured_summary", spy)
    result = await service.summarize_filing("Selected filing text.", "Anchor Co", "10-K", stream_cb=_receive)
    assert assembled == [sorted({"_capital_allocation_grounding", "_issuer_cash_disclosure_grounding",
                                 "_recovered_sections", "_risk_source_grounding", "metadata", "sections", *extra})]
    raw = result["raw_summary"]
    assert raw["sections"] is raw["structured"]["sections"]
    assert result["financial_highlights"] is raw["sections"]["results_that_matter"]
    assert result["risk_factors"] is raw["sections"]["risks"]
    assert sorted(raw["structured"]) == structured_keys
    # No application-private key survives; only a model-supplied one does (second case).
    assert sorted(k for k in raw["structured"] if k.startswith("_")) == ([] if not extra else ["_model_note"])
    assert raw["structured"]["schema_version"] == 2
    assert [key for key in raw["sections"] if key.startswith("_")] == ["_risk_source_projection"]
