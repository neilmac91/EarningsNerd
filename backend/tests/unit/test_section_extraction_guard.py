"""Tests for 10-K section-extraction TOC guard (roadmap S2).

The 10-K extraction path previously accepted the first regex match with no length/TOC guard,
so an Item-8 pattern that hit the table of contents fed the model a sliver. These tests verify
the guard rejects TOC slivers and falls through to the real section.
"""
from app.services.openai_service import openai_service


def test_accept_section_rejects_toc_sliver_and_short():
    assert openai_service._accept_section("x" * 600, 500) is True
    assert openai_service._accept_section("too short", 500) is False
    toc = "ITEM 8. FINANCIAL STATEMENTS ............................... 45"
    assert openai_service._looks_like_toc(toc + " ...." * 6) is True


def test_10k_extraction_skips_toc_and_captures_real_item8():
    toc = (
        "TABLE OF CONTENTS\n"
        "ITEM 8. FINANCIAL STATEMENTS ............................... 45\n"
        "ITEM 9. CONTROLS AND PROCEDURES ............................ 60\n"
    )
    real_marker = "Net sales were $383,285 million for fiscal 2023."
    real = (
        "ITEM 8. FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA\n"
        + (real_marker + " Operating income rose. ") * 40
        + "\nITEM 9. CHANGES IN AND DISAGREEMENTS WITH ACCOUNTANTS\n"
    )
    text = toc + "\nPART II\n" + real

    result = openai_service.extract_critical_sections(text, "10-K")

    # The real Item 8 content is captured, not the empty TOC sliver.
    assert real_marker in result
    assert "ITEM 8 - FINANCIAL STATEMENTS" in result


# ---------------------------------------------------------------------------
# edgartools section assembler (report-quality fix). The regex extractor above
# silently returns ~0 chars on modern element-fragmented 10-K HTML; the product
# now prefers edgartools-parsed sections, assembled by the helper below. These
# guard the assembler's labels, caps, ordering, and empty-input behavior.
# ---------------------------------------------------------------------------


def test_assemble_excerpt_from_sections_10k_labels_and_order():
    sections = {
        "financials": "Net sales were $383,285 million. " * 50,
        "mda": "Gross margin expanded on services mix. " * 50,
        "risk": "Supply concentration could adversely affect results. " * 50,
    }
    out = openai_service.assemble_excerpt_from_sections(sections, "10-K")

    # All three sections are present with the canonical 10-K labels.
    assert "ITEM 8 - FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA" in out
    assert "ITEM 7 - MANAGEMENT'S DISCUSSION AND ANALYSIS" in out
    assert "ITEM 1A - RISK FACTORS" in out
    # Real content (not a sliver) survives.
    assert "Net sales were $383,285 million." in out
    # Financials (Item 8) is emitted before MD&A (Item 7), matching the regex path ordering.
    assert out.index("ITEM 8 -") < out.index("ITEM 7 -") < out.index("ITEM 1A -")


def test_assemble_excerpt_from_sections_10q_labels():
    sections = {
        "financials": "Condensed consolidated statements of operations. " * 30,
        "mda": "Management's discussion of liquidity. " * 30,
        "risk": "Risk factors specific to the quarter. " * 30,
    }
    out = openai_service.assemble_excerpt_from_sections(sections, "10-Q")
    assert "ITEM 1 - FINANCIAL STATEMENTS" in out
    assert "ITEM 2 - MANAGEMENT'S DISCUSSION AND ANALYSIS" in out
    assert "ITEM 1A - RISK FACTORS" in out


def test_assemble_excerpt_caps_each_section():
    # A section far larger than its cap (Item 8 -> 70000) is truncated.
    sections = {"financials": "A" * 200000}
    out = openai_service.assemble_excerpt_from_sections(sections, "10-K")
    body = out.split("ITEM 8 - FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA:\n", 1)[1]
    assert len(body) == 70000


def test_assemble_excerpt_empty_inputs_return_empty():
    assert openai_service.assemble_excerpt_from_sections(None, "10-K") == ""
    assert openai_service.assemble_excerpt_from_sections({}, "10-K") == ""
    # A sub-threshold stub (<200 chars) is dropped, yielding no excerpt.
    assert openai_service.assemble_excerpt_from_sections({"risk": "tiny"}, "10-K") == ""


# ---------------------------------------------------------------------------
# B3: MD&A dense-window backfill. Big financial filers (e.g. JPM) parse a real Item 1A but only a
# stub Item 7 MD&A; the assembler backfills it from the raw document (like it already does for a
# thin Item 8), so the summary keeps its narrative depth instead of discarding the good sections.
# ---------------------------------------------------------------------------


def test_mda_backfill_recovers_a_thin_mda_from_raw_text():
    sections = {
        # Substantive financials (> _FINANCIALS_MIN_CHARS) so ONLY the MD&A path triggers.
        "financials": "Net interest income detail. " * 300,
        "mda": "See Item 7.",  # stub (< _MDA_MIN_CHARS), as JPM parses
        "risk": "Credit losses could adversely affect results. " * 60,
    }
    raw = (
        "Results of operations improved year over year. Net interest income rose on higher rates. "
        "Liquidity and capital resources remained strong; critical accounting estimates unchanged. "
    ) * 400
    out = openai_service.assemble_excerpt_from_sections(sections, "10-K", filing_text=raw)
    assert "MD&A CONTEXT (recovered from filing)" in out
    # Financials were substantive, so that backfill must NOT fire.
    assert "FINANCIAL STATEMENTS CONTEXT (recovered from filing)" not in out
    # The well-parsed risk section is preserved (not discarded in favor of regex).
    assert "ITEM 1A - RISK FACTORS" in out


def test_no_mda_backfill_when_mda_is_substantive():
    sections = {
        "financials": "Net sales $383,285 million. " * 300,
        "mda": "Management's discussion of operations and liquidity. " * 200,  # well over the stub bar
        "risk": "Risk narrative. " * 60,
    }
    raw = "Results of operations and liquidity and capital resources. " * 400
    out = openai_service.assemble_excerpt_from_sections(sections, "10-K", filing_text=raw)
    assert "MD&A CONTEXT (recovered from filing)" not in out


def test_mda_backfill_skipped_without_filing_text():
    # No raw text to recover from → no backfill, but the parsed sections still assemble.
    sections = {"mda": "stub", "risk": "Real risk content. " * 60}
    out = openai_service.assemble_excerpt_from_sections(sections, "10-K")
    assert "MD&A CONTEXT" not in out
    assert "ITEM 1A - RISK FACTORS" in out


def test_mda_backfill_skips_window_overlapping_financials():
    # Both financials and MD&A are stubs, and the raw text is a single keyword-dense region carrying
    # BOTH financial and MD&A markers → the two dense windows coincide. Only one context block should
    # be appended; the near-duplicate MD&A window is skipped so it doesn't waste model context.
    sections = {"financials": "see ref", "mda": "see Item 7", "risk": "Risk content. " * 60}
    raw = (
        "Net income and cash flow from operating activities improved. Results of operations and "
        "liquidity and capital resources were discussed across the period. "
    ) * 300
    out = openai_service.assemble_excerpt_from_sections(sections, "10-K", filing_text=raw)
    assert "FINANCIAL STATEMENTS CONTEXT (recovered from filing)" in out
    assert "MD&A CONTEXT (recovered from filing)" not in out  # deduped — overlaps the financials window
