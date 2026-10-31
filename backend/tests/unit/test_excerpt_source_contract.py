"""The excerpt source contract (E80-C1): what the one excerpt builder records about where its excerpt came from.

``summary_generation_service.get_or_cache_excerpt`` logs at most one ``excerpt_provenance`` record per call and hands
that one to ``on_provenance``, so the Copilot evaluation's preparation can read the builder's own outcome (native
sections or a fallback, and why) instead of re-deriving it. For such a caller its hashes match the preparation
artifacts' own (``evals/copilot_bootstrap.py::_artifact``), which ties the record to the document and sections that
were prepared. Each case below is a fixture of the contract: a native excerpt E80 may accept, and each record it must
not.
"""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.config import settings
from app.services import summary_generation_service as service
from app.services.excerpt_provenance import FALLBACK_REASONS, excerpt_provenance
from evals.copilot_bootstrap import _artifact

ACCESSION = "0000320193-25-000079"
# The document as fetched, its trailing newline included: the hash is of the exact text the builder was given.
HTML = "<html><body>Item 7. Management’s Discussion €</body></html>\n"
NATIVE = "ITEM 7 - MANAGEMENT'S DISCUSSION AND ANALYSIS:\n" + "Net sales rose. " * 700
# The parser's own key order for a 10-K (risk, mda, financials; edgar/xbrl_sections.py) and non-ASCII text, so the
# section hash is pinned to sorted keys and escaped text, as the preparation writes sections.json.
SECTIONS = {"risk": "Risks ’ " * 600, "mda": "Discussion € " * 600, "financials": "Statements " * 600}


def _build(monkeypatch, caplog, *, sections=SECTIONS, native=NATIVE, regex="regex excerpt " * 50, cached=None,
           flag=True, filing_type="10-K", filing_text=HTML, take_record=True):
    """Run the builder against a stubbed filing; return what it returned, the records it logged, and the assembler."""
    cache = SimpleNamespace(critical_excerpt=cached)
    filing = SimpleNamespace(id=7, accession_number=ACCESSION, filing_type=filing_type, content_cache=cache)
    db = MagicMock()
    db.query.return_value.options.return_value.filter.return_value.first.return_value = filing
    assemble = MagicMock(return_value=native)
    monkeypatch.setattr(service.openai_service, "assemble_excerpt_from_sections", assemble)
    monkeypatch.setattr(service.openai_service, "extract_critical_sections", MagicMock(return_value=regex))
    monkeypatch.setattr(settings, "USE_EDGARTOOLS_SECTIONS", flag)
    reported: list[dict] = []
    with caplog.at_level("INFO", logger=service.__name__):
        returned = service.get_or_cache_excerpt(
            db, filing, filing_text, sections=sections, on_provenance=reported.append if take_record else None,
        )
    logged = [json.loads(r.message.removeprefix("Excerpt provenance: "))
              for r in caplog.records if r.message.startswith("Excerpt provenance: ")]
    if take_record:
        assert reported == logged  # the callback receives exactly the record the builder logs
    return returned, logged, assemble


def test_a_native_excerpt_names_its_filing_document_and_sections_by_the_preparation_hashes(monkeypatch, caplog, tmp_path):
    returned, [record], _ = _build(monkeypatch, caplog)
    assert returned == NATIVE
    assert record == {
        "schema_version": 2,
        "accession": ACCESSION,
        "filing_type": "10-K",
        "source": "edgartools",
        "outcome": "native",
        "fallback_reason": None,
        "coverage_status": "observed_partial",
        "excerpt_sha256": _artifact(tmp_path, "excerpt.txt", NATIVE)["sha256"],
        "excerpt_chars": len(NATIVE),
        "document_sha256": _artifact(tmp_path, "filing.html", HTML)["sha256"],
        "sections_sha256": _artifact(tmp_path, "sections.json", SECTIONS)["sha256"],
        "supplied_sections": [{"key": key, "supplied_chars": len(SECTIONS[key])} for key in ("financials", "mda", "risk")],
        "missing_sections": [],
    }


def test_the_pipelines_own_log_hashes_no_inputs(monkeypatch, caplog):
    # With no caller taking the record (the summary pipeline), hashing the whole document stays off its path.
    _, [record], _ = _build(monkeypatch, caplog, take_record=False)
    assert (record["outcome"], record["document_sha256"], record["sections_sha256"]) == ("native", None, None)
    assert record["excerpt_sha256"] is not None


@pytest.mark.parametrize("sections", [
    pytest.param({"financials": SECTIONS["financials"], "mda": SECTIONS["mda"]}, id="no Risk Factors key, as parsed"),
    pytest.param({**SECTIONS, "risk": "  "}, id="a blank Risk Factors section"),
])
def test_a_native_excerpt_without_a_section_names_the_one_it_lacks(monkeypatch, caplog, sections):
    # A 10-Q often has no Risk Factors item: the excerpt is still native, and the record says what it lacks.
    _, [record], _ = _build(monkeypatch, caplog, sections=sections, filing_type="10-q")
    assert (record["outcome"], record["filing_type"], record["missing_sections"]) == ("native", "10-Q", ["risk"])


@pytest.mark.parametrize(
    ("case", "reason", "assembled"),
    [
        # Production parses no sections with the flag off (summary_stages/enrichment.py), so none reach the builder.
        pytest.param({"flag": False, "sections": None}, "native_sections_disabled", False,
                     id="native sections switched off"),
        pytest.param({"flag": False}, "native_sections_disabled", False, id="switched off with sections supplied"),
        pytest.param({"sections": None}, "sections_not_supplied", False, id="no section text reached the builder"),
        pytest.param({"sections": {}}, "sections_not_supplied", False, id="an empty section mapping"),
        pytest.param({"native": "too thin"}, "native_excerpt_thin", True, id="a native assembly under its floor"),
        pytest.param({"native": ""}, "native_excerpt_thin", True, id="an empty native assembly"),
    ],
)
def test_a_fallback_excerpt_says_it_fell_back_and_why(monkeypatch, caplog, case, reason, assembled):
    returned, [record], assemble = _build(monkeypatch, caplog, **case)
    assert returned == "regex excerpt " * 50
    assert (record["source"], record["outcome"], record["fallback_reason"]) == ("regex_fallback", "fallback", reason)
    assert reason in FALLBACK_REASONS
    assert assemble.called is assembled
    supplied = case.get("sections", SECTIONS)
    # A section hash only for section text the builder was given: none for no mapping or an empty one.
    assert (record["sections_sha256"] is not None) is bool(supplied)
    assert record["missing_sections"] == ([] if supplied else ["financials", "mda", "risk"])


def test_no_document_text_hashes_no_document(monkeypatch, caplog):
    # The cache-hit path builds from sections alone: the record claims no document it was not given.
    _, [record], _ = _build(monkeypatch, caplog, filing_text="")
    assert (record["outcome"], record["document_sha256"]) == ("native", None)
    assert record["sections_sha256"] is not None


def test_no_excerpt_at_all_is_unavailable_with_its_reason(monkeypatch, caplog):
    returned, [record], _ = _build(monkeypatch, caplog, sections=None, regex="")
    assert not returned
    assert (record["outcome"], record["fallback_reason"], record["excerpt_chars"]) == (
        "unavailable", "sections_not_supplied", 0)


def test_a_stored_excerpt_claims_no_build_inputs(monkeypatch, caplog):
    # A stored excerpt's build is unknown now: no document or section hash, no section coverage.
    stored = "stored excerpt " * 600
    returned, [record], assemble = _build(monkeypatch, caplog, cached=stored)
    assert returned == stored
    assemble.assert_not_called()
    assert (record["source"], record["outcome"], record["coverage_status"]) == ("legacy_cached_excerpt", "cached", "unknown")
    assert (record["document_sha256"], record["sections_sha256"], record["supplied_sections"], record["missing_sections"],
            record["fallback_reason"]) == (None, None, [], None, None)


def test_a_call_that_returns_early_records_nothing(monkeypatch, caplog):
    # No text and no sections: no excerpt and no record, which a reader takes as no excerpt.
    returned, logged, _ = _build(monkeypatch, caplog, sections=None, filing_text="")
    assert returned is None and logged == []


def test_a_fallback_whose_caller_names_no_reason_says_unrecorded():
    # eval-baseline's runner builds its own records and names no reason: never a native-looking None.
    record = excerpt_provenance("text", accession=ACCESSION, source="raw_filing_fallback")
    assert (record["outcome"], record["fallback_reason"]) == ("fallback", "unrecorded")
    assert "unrecorded" in FALLBACK_REASONS
