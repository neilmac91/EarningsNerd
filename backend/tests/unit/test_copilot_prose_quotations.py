"""Final-prose quotations must be contiguous filing text before publication (decision F, #1029).

Fixtures are verbatim snippets of the retained #1021 qualification sources, with their newlines,
NBSPs and table-cell layout preserved. The composed spans are the retained main-code failures:
"Total net sales 32,667.3" (ASML, runs 36640254449 and 36800236360) and "Revenue ... 996,347" (BABA,
run 36777581481). The check reuses the citation verifier's normalizer and its 24-character floor.

Nested quotations are checked whole and inner. Curly marks carry direction, so the parser can tell
the outer quotation from the inner one. Straight marks cannot: '"x "y" z"' reads as the two quotes
'x ' and ' z', and the inner "y" is never seen. That signature (a straight-marked quotation that
starts or ends with whitespace) fails closed as ``ambiguous_quotation``, even when the nesting was
genuine filing text.
"""
import logging

import pytest

from app.services import copilot_service
from app.services.copilot_service import unsupported_prose_quotations
from app.services.provenance_service import _MIN_VERIFIABLE_LEN, normalize_for_match

SOURCE = normalize_for_match("\n".join([
    # ASML 20-F 0001628280-26-011378: operating-results table rows and an MD&A sentence.
    "Total net sales\n28,262.9\n100.0\n32,667.3\n100.0\n15.6\nCost of s",
    "\nNet income\n7,571.6\n26.8\n9,609.4\n29.4\n26",
    "Net income for \n2025\n \namounted to\n \n€9,609.4 million\n, \nrepresenting\n \n29.4%\n of total net sales",
    # BABA 20-F 0000950170-25-090161: income-statement row and cover-page dot leaders.
    "Revenue\n\n\n5, 24\n\n\n\xa0\n\n\n868,687\n\n\n\xa0\n\n\n941,168\n\n\n\xa0\n\n\n996,347\n\n\n\xa0",
    "Date of event requiring this shell company report...............\nFor the transition period from",
    # BABA 20-F 0001193125-26-231755 and TSLA 10-K 0001628280-25-003063.
    "and further increased by 3% to RMB1,023,670 million (US$148,401 million) in fiscal year 2026.",
    'consolidated balance sheets of Tesla, Inc. and its subsidiaries (the "Company") as of December 31, 2024',
    # AAPL 10-K 0000320193-25-000079: curly-quoted note title and defined term.
    "revenue source was generally consistent for each reportable segment in Note 13, “Segment Information"
    " and Geographic Data” for 2025, 2024 and 2023, except in Greater China",
    "provided to the Company’s chief operating decision maker (“CODM”). In addition, ASU 2023-07 requires"
    " the Company to disclose the title and position of its CODM",
    "As shown in Note [7] to the financial statements, revenue grew.",
]))
NI = "Net income for 2025 amounted to €9,609.4 million, representing 29.4% of total net sales"
NOT_IN, ELIDED = "quotation_not_in_source", "elided_quotation"
AMBIGUOUS, UNBALANCED = "ambiguous_quotation", "unbalanced_quotation"

# Nested controls on the AAPL sentence. The outer quotation's text before and after the inner one is
# filing text, so only the inner span decides; INVENTED is not filing text, INNER is.
PREFIX = "revenue source was generally consistent for each reportable segment in Note 13, "
SUFFIX = " for 2025, 2024 and 2023"
INVENTED = "Segment revenue grew in every geographic region"
INNER = "Segment Information and Geographic Data"
TSLA = "consolidated balance sheets of Tesla, Inc. and its subsidiaries (the {}Company{}) as of December 31, 2024"


@pytest.mark.unit
@pytest.mark.parametrize("answer", [
    f'The filing says "{NI}" [1].',                                       # supported whitespace
    f"The filing says “{NI}” [1].",                             # curly marks
    f'The filing says "{NI}." [1]',                                       # edge punctuation
    '"...amounted to €9,609.4 million, representing 29.4%…" [1]',    # edge ellipses
    f'The filing says "{NI} [1]".',                                       # marker inside
    f'The filing says "{NI} [1]."',                                       # marker, then edge period
    '"Net income for 2025 amounted to €9,609.4 million [1], representing 29.4% of total net sales"',
    'It "further increased by 3% to RMB1,023,670 million (US$148,401 million) in fiscal year 2026" [1].',
    '"Date of event requiring this shell company report............... For the transition period from" [1]',
    '"As shown in Note [7] to the financial statements" [1]',             # source-literal bracket
    'Return on equity ("ROE") and "Adjusted EBITDA margin" are not reported; see "Revenue" [1].',
    "No quotation here ... at all [1].",
])
def test_contiguous_quotations_and_short_terms_publish(answer):
    assert unsupported_prose_quotations(answer, SOURCE) == []


@pytest.mark.unit
@pytest.mark.parametrize("answer,expected", [
    ('showing "Total net sales 32,667.3" and "Net income 9,609.4" for 2025 [3].', [NOT_IN]),
    ('which report "Revenue ... 996,347" for the year [2].', [ELIDED]),
    ('"Net income for 2025 amounted to … 29.4% of total net sales" [1]', [ELIDED]),
    ('"Net income for 2025 was €9,609.4 million" and "Revenue . . . 996,347" [1]', [NOT_IN, ELIDED]),
    ("showing „Total net sales 32,667.3” [3].", [NOT_IN]),
    ('showing "Total net sales [1] 32,667.3." [3]', [NOT_IN]),
    ('The table shows "Total net sales 32,667.3 [1].', [UNBALANCED]),
])
def test_composed_or_unpairable_quotations_are_withheld(answer, expected):
    assert unsupported_prose_quotations(answer, SOURCE) == expected


@pytest.mark.unit
def test_nested_controls_differ_from_the_filing_only_in_the_inner_span():
    """Premise of the nested controls: an all-valid nest would not test an invented inner span."""
    assert normalize_for_match(PREFIX.strip(" ,")) in SOURCE
    assert normalize_for_match(SUFFIX.strip()) in SOURCE
    assert normalize_for_match(f"{PREFIX}“{INNER}”{SUFFIX}") in SOURCE
    assert normalize_for_match(INNER) in SOURCE and len(normalize_for_match(INNER)) >= _MIN_VERIFIABLE_LEN
    assert normalize_for_match(INVENTED) not in SOURCE
    assert len(normalize_for_match(INVENTED)) >= _MIN_VERIFIABLE_LEN


@pytest.mark.unit
@pytest.mark.parametrize("answer,expected", [
    pytest.param(f"The filing says “{PREFIX}“{INVENTED}”{SUFFIX}” [1].", [NOT_IN, NOT_IN],
                 id="a-curly-invented-inner"),
    pytest.param(f'The filing says "{PREFIX}"{INVENTED}"{SUFFIX}" [1].', [AMBIGUOUS, AMBIGUOUS],
                 id="b-straight-invented-inner"),
    pytest.param(f"The filing says “{PREFIX}“{INNER}”{SUFFIX}” [1].", [], id="c-curly-valid-nest"),
    pytest.param(f"The filing says “Revenue rose in every region, per Note 13, “{INNER}”{SUFFIX}” [1].", [NOT_IN],
                 id="invented-outer-around-valid-inner"),
    pytest.param(f'The filing says “{PREFIX}"{INVENTED}"{SUFFIX}” [1].', [NOT_IN, NOT_IN],
                 id="straight-inside-curly-invented-inner"),
    pytest.param('The filing refers to "the Company’s chief operating decision maker (“CODM”). In addition,'
                 ' ASU 2023-07 requires the Company to disclose" [1].', [], id="curly-inside-straight-valid-nest"),
    pytest.param(f"The auditor covered “{TSLA.format('“', '”')}” [1].", [], id="curly-valid-nest-of-straight-source"),
    pytest.param(f'The auditor covered "{TSLA.format(chr(34), chr(34))}" [1].', [AMBIGUOUS],
                 id="straight-valid-nest-fails-closed"),
    pytest.param("showing ”Total net sales 32,667.3“ [3].", [UNBALANCED], id="reversed-curly-marks"),
])
def test_nested_quotations_are_checked_whole_and_inner(answer, expected):
    assert unsupported_prose_quotations(answer, SOURCE) == expected


@pytest.mark.unit
@pytest.mark.parametrize("source", ["", None])
def test_missing_source_text_fails_closed(source):
    assert unsupported_prose_quotations(f'"{NI}" and "Revenue ... 996,347"', source) == [
        "quotation_source_unavailable", "quotation_source_unavailable"]


@pytest.mark.unit
def test_short_stitched_label_and_cell_is_a_known_limit():
    """Pinned limit, not a guarantee: under the 24-character floor a stitched label stays a term."""
    assert unsupported_prose_quotations('showing "Net income 9,609.4" [1].', SOURCE) == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_logs_constant_quotation_reason(monkeypatch, caplog):
    source = "Item 7. Revenue increased to 391.0 billion driven by strong iPhone demand. Margins expanded."
    filing = type("F", (), {"content_cache": type("C", (), {"critical_excerpt": source,
                                                              "markdown_content": None})(),
                            "company": None, "company_id": 1, "accession_number": "a", "xbrl_data": None,
                            "document_url": "https://www.sec.gov/x", "sec_url": None,
                            "filing_type": "10-K", "filing_date": None, "period_of_report": None})()
    good = '[{"n": 1, "excerpt": "Revenue increased to 391.0 billion driven by strong iPhone demand."}]'

    async def stream(*_args, **_kwargs):
        yield 'It said "Revenue increased to 391.0 billion. Margins expanded" [1].\n===CITATIONS===\n' + good

    monkeypatch.setattr(copilot_service.openai_service, "stream_chat_with_tools", stream)
    with caplog.at_level(logging.WARNING, logger=copilot_service.logger.name):
        events = [e async for e in copilot_service.answer_filing_question(filing=filing, question="q")]
    assert events[-1] == {"type": "error", "message": copilot_service._PUBLICATION_ERROR}
    assert "Unsupported prose quotation: quotation_not_in_source" in caplog.text
    assert "Margins expanded" not in caplog.text
