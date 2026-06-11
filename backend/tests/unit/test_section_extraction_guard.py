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
