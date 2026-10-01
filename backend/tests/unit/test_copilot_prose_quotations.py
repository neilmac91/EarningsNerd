"""Final-prose quotations must be contiguous filing text before publication (decision F, #1029).

Filing fixtures are verbatim snippets of the retained #1021 qualification sources (newlines, NBSPs
and table-cell layout as retained); the synthetic lines are labelled as such. The composed spans are
the retained main-code failures: "Total net sales 32,667.3" (ASML, runs 36640254449 and 36800236360)
and "Revenue ... 996,347" (BABA, run 36777581481). The check reuses the citation verifier's
normalizer and its 24-character floor.

The answer is read as rendered (react-markdown 10 + remark-gfm, parsed here with markdown-it-py): a
link shows its text, escapes and character references show their characters, emphasis and
code-span delimiters do not show, and neither do format characters (Unicode Cf). Where the display
may differ the check fails closed: a direction that a delimiter left as text decides (tildes stay
text here), a footnote definition, a bare URL GFM would show verbatim. A mark's direction comes from its
glyph (“ „ ‟ open, ” closes) or, for a straight mark, from its neighbours as CommonMark reads
emphasis, so '"x "y" z"' and '"x ("y") z"' read as nesting and "y" is checked too. Curly marks
pair only with curly marks, straight marks only with straight marks between the same curly marks.
Exactly one balanced reading is checked; none is ``unbalanced_quotation``; more than one, a curly
mark facing the wrong way, or work past the bounds is ``ambiguous_quotation``. The reading decides only whether to withhold: a published answer is never
rewritten. Only double quotation marks are in scope (see the pinned limits below); this is not
exhaustive verification of every quotation form.
"""
import logging
import time

import pytest

from app.services import copilot_service
from app.services.copilot_service import (
    _MAX_QUOTE_MARKS,
    _MAX_QUOTED_ANSWER_CHARS,
    _MAX_QUOTED_CHARS,
    unsupported_prose_quotations,
)
from app.services.provenance_service import _MIN_VERIFIABLE_LEN, normalize_for_match

SOURCE = normalize_for_match("\n".join([
    # ASML 20-F 0001628280-26-011378: operating-results table rows and an MD&A sentence.
    "Total net sales\n28,262.9\n100.0\n32,667.3\n100.0\n15.6\nCost of s",
    "\nNet income\n7,571.6\n26.8\n9,609.4\n29.4\n26",
    "Net income for \n2025\n \namounted to\n \n€9,609.4 million\n, \nrepresenting\n \n29.4%\n of total net sales",
    # BABA 20-F 0000950170-25-090161: income-statement row and cover-page dot leaders.
    "Revenue\n\n\n5, 24\n\n\n\xa0\n\n\n\xa0\n\n\n868,687\n\n\n\xa0\n\n\n\xa0\n\n\n\xa0\n\n\n941,168\n\n\n\xa0\n\n\n"
    "\xa0\n\n\n\xa0\n\n\n996,347\n\n\n\xa0",
    "Date of event requiring this shell company report...............\nFor the transition period from",
    # BABA 20-F 0001193125-26-231755 and TSLA 10-K 0001628280-25-003063.
    "and further increased by 3% to RMB1,023,670 million (US$148,401 million) in fiscal year 2026.",
    'consolidated balance sheets of Tesla, Inc. and its subsidiaries (the "Company") as of December 31, 2024',
    # AAPL 10-K 0000320193-25-000079: curly-quoted note title and defined term.
    "revenue source was generally consistent for each reportable segment in Note 13, “Segment Information"
    " and Geographic Data” for 2025, 2024 and 2023, except in Greater China",
    "provided to the Company’s chief operating decision maker (“CODM”). In addition, ASU 2023-07 requires"
    " the Company to disclose the title and position of its CODM",
    # Synthetic, not filing text: a source-literal bracket; the reviewers' sources (PR #1029: Codex
    # comment 5932067928, the round-4 reviews) with an em-dash twin; and two MD&A-style sentences.
    "As shown in Note [7] to the financial statements, revenue grew.",
    "The policy names the approved label (Original) and describes the release procedure.",
    "Net sales were 32,667.3 million.",
    "The policy names the approved label—Original—and describes the release procedure.",
    'The policy names the approved label "Original" in one section. A later section says the "Original"'
    " and describes the release procedure.",
    "Gross margin percentage was 46.2% in 2025, compared to 44.1% in 2024.",
    "Total net sales increased 2% or $8.0 billion during 2025.",
]))
NI = "Net income for 2025 amounted to €9,609.4 million, representing 29.4% of total net sales"
NOT_IN, ELIDED = "quotation_not_in_source", "elided_quotation"
AMBIGUOUS, UNBALANCED = "ambiguous_quotation", "unbalanced_quotation"
INV = "Invented text missing from the source"

# Nested controls on the AAPL sentence. The outer quotation's text before and after the inner one is
# filing text, so only the inner span decides; INVENTED is not filing text, INNER is.
PREFIX = "revenue source was generally consistent for each reportable segment in Note 13, "
SUFFIX = " for 2025, 2024 and 2023"
INVENTED = "Segment revenue grew in every geographic region"
INNER = "Segment Information and Geographic Data"
TSLA = "consolidated balance sheets of Tesla, Inc. and its subsidiaries (the {}Company{}) as of December 31, 2024"
# The two residual-limit probes of the first F commit; both published before the edge signature.
PROBE = "an invented record-breaking statement here"
# Starts and ends with markup, which may sit outside either mark: only the inside edges show nesting.
MARKED = "*€9.9 billion of invented record revenue.*"


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
    '"Net income for 2025 amounted to €9,609.4 million"\n"Total net sales" [1]',   # any Unicode space
    'The filing never says "…Adjusted EBITDA…" [1].',                    # edge ellipses are not elision
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
    (f"The filing calls it ‟{INV}” [1].", [NOT_IN]),
    (f"The filing calls it ＂{INV}＂ [1].", [NOT_IN]),
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
    # Each sequential half of the straight-nesting controls is filing text of at least 24 characters.
    for half in ("The policy names the approved label (", ") and describes the release procedure",
                 "The policy names the approved label—", "—and describes the release procedure",
                 "Tesla, Inc. and its subsidiaries (", ") as of December 31, 2024",
                 'The policy names the approved label "Original', 'Original" and describes the release procedure'):
        assert normalize_for_match(half) in SOURCE and len(normalize_for_match(half)) >= _MIN_VERIFIABLE_LEN
    for inner in (INV, PROBE, MARKED.strip("*.")):
        assert normalize_for_match(inner) not in SOURCE


@pytest.mark.unit
@pytest.mark.parametrize("answer,expected", [
    # Curly nesting: direction from the glyphs.
    pytest.param(f"The filing says “{PREFIX}“{INVENTED}”{SUFFIX}” [1].", [NOT_IN, NOT_IN],
                 id="a-curly-invented-inner"),
    pytest.param(f"The filing says “{PREFIX}“{INNER}”{SUFFIX}” [1].", [], id="c-curly-valid-nest"),
    pytest.param(f"The filing says “Revenue rose in every region, per Note 13, “{INNER}”{SUFFIX}” [1].", [NOT_IN],
                 id="invented-outer-around-valid-inner"),
    pytest.param(f'The filing says “{PREFIX}"{INVENTED}"{SUFFIX}” [1].', [NOT_IN, NOT_IN],
                 id="straight-inside-curly-invented-inner"),
    pytest.param('The filing refers to "the Company’s chief operating decision maker (“CODM”). In addition,'
                 ' ASU 2023-07 requires the Company to disclose" [1].', [], id="curly-inside-straight-valid-nest"),
    pytest.param(f"The auditor covered “{TSLA.format('“', '”')}” [1].", [], id="curly-valid-nest-of-straight-source"),
    # Straight nesting: direction from the neighbours, so the one reading is the nest.
    pytest.param(f'The filing says "{PREFIX}"{INVENTED}"{SUFFIX}" [1].', [NOT_IN, NOT_IN],
                 id="b-straight-invented-inner"),
    # Codex's counterexample, verbatim: both sequential halves are >= 24 characters, are filing text and
    # have no boundary whitespace.
    pytest.param('"The policy names the approved label ("Invented text missing from the source") and describes'
                 ' the release procedure."', [NOT_IN, NOT_IN], id="codex-straight-bracket-nest"),
    pytest.param(f'"Tesla, Inc. and its subsidiaries ("{PROBE}") as of December 31, 2024" [1]', [NOT_IN, NOT_IN],
                 id="straight-bracket-nest-first-commit-probe"),
    pytest.param('"The policy names the approved label—"Invented text missing from the *source*"—and describes'
                 ' the release procedure." [1]', [NOT_IN, NOT_IN], id="straight-dash-nest-markup-end"),
    pytest.param('"The policy names the approved label—"*Invented* text missing from the source"—and describes'
                 ' the release procedure." [1]', [NOT_IN, NOT_IN], id="straight-dash-nest-markup-start"),
    pytest.param(f'The auditor covered "{TSLA.format(chr(34), chr(34))}" [1].', [], id="straight-valid-nest"),
    # Round-4 review: a first-in-first-out pairing stitches the two in-source halves into a quote the
    # filing never prints; the last-in-first-out reading checks the outer quotation as written.
    pytest.param('"The policy names the approved label "Original" and describes the release procedure." [1]',
                 [NOT_IN], id="nest-pairs-last-in-first-out"),
    # Review of 6f85b6e6: straight marks between punctuation on both sides. Rendered, the bold and
    # underscore forms lose their delimiters and read as a nest; the dash form has two balanced
    # readings, sequential and nested.
    pytest.param('The filing calls it "label **"*Invented text missing from the source*"** here".', [NOT_IN, NOT_IN],
                 id="punctuation-flanked-bold"),
    pytest.param('The filing calls it "label —"—Invented text missing from the source—"— here".', [AMBIGUOUS],
                 id="punctuation-flanked-dash"),
    pytest.param('The filing calls it "label _"_Invented text missing from the source_"_ here".', [NOT_IN, NOT_IN],
                 id="punctuation-flanked-underscore"),
    pytest.param(f'"Tesla, Inc. and its subsidiaries ("{MARKED}") as of December 31, 2024" [1]', [AMBIGUOUS],
                 id="punctuation-flanked-bracket-markup"),
    pytest.param('"The policy names the approved label—"€9.9 billion of invented record revenue."—and describes'
                 ' the release procedure." [1]', [AMBIGUOUS], id="punctuation-flanked-dash-symbol"),
    # A curly mark facing the wrong way: its glyph cannot be trusted.
    pytest.param("showing ”Total net sales 32,667.3“ [3].", [AMBIGUOUS], id="reversed-curly-marks"),
    pytest.param(f"“revenue source was generally consistent for each reportable segment in Note 13, ”{PROBE}“"
                 " for 2025, 2024 and 2023” [1]", [AMBIGUOUS], id="reversed-curly-first-commit-probe"),
    pytest.param(f"“Tesla, Inc. and its subsidiaries (”{PROBE}“) as of December 31, 2024” [1]", [AMBIGUOUS],
                 id="reversed-curly-bracket"),
    pytest.param(f"“{PREFIX}”{MARKED}“{SUFFIX}” [1]", [AMBIGUOUS], id="reversed-curly-markup-inner"),
    # Round-4 review: a curly quotation around straight marks that cannot balance inside it. Curly marks
    # pair only with curly marks, so the visible “…” is never split by a straight mark.
    pytest.param(f'The filing calls it “label"—{INV}—"here” [1].', [UNBALANCED], id="curly-around-straight-dash"),
    pytest.param(f'The filing calls it “label"({INV})"here” [1].', [UNBALANCED], id="curly-around-straight-bracket"),
    pytest.param(f'The filing calls it „label"*{INV}*"here” [1].', [NOT_IN, NOT_IN], id="low-curly-around-straight"),
    pytest.param(f'“The policy names the approved label—" {INV} "—and describes the release procedure.” [1]',
                 [UNBALANCED], id="curly-around-interrupted-straight"),
    pytest.param('The filing says "net income “rose" sharply” [1].', [UNBALANCED], id="crossing-straight-and-curly"),
    pytest.param("“Segment Information and Geographic Data\" [1].", [UNBALANCED],
                 id="mixed-curly-open-straight-close-fails-closed"),
    # Well-formed marks that must keep publishing.
    pytest.param('It reports **"Net sales"** [1].', [], id="bold-quotation"),
    pytest.param('It reports ("Net sales") [1].', [], id="parenthesised-quotation"),
    pytest.param('It uses "x"/"y" [1].', [], id="slash-separated-quotations"),
    pytest.param('It says "x."[1]', [], id="citation-after-closing-mark"),
    pytest.param('It says "*x*" [1].', [], id="emphasis-inside-quotation"),
    pytest.param('It reports "ROE" and "Revenue" and "Net sales" [1].', [], id="sequential-quotations"),
    pytest.param('Amounts are shown "(in millions)" in the table [1].', [], id="balanced-parenthetical"),
    pytest.param("Note 13 is titled “Segment Information and Geographic Data” [1].", [],
                 id="well-formed-curly-internal-spaces"),
    pytest.param('**"Net income for 2025 amounted to €9,609.4 million"**[1]; the "ROE"/"Revenue" lines and the'
                 ' "Company"\'s "Adjusted EBITDA margin" [1].', [], id="tight-sequential-quotes-and-markup"),
    pytest.param(f'It said,"{NI}" [1].', [], id="quotation-tight-to-a-comma"),
    pytest.param(f'The "{NI}"s figure is cited [1].', [], id="quotation-tight-to-a-letter"),
    # Both-flanking straight marks with only one balanced reading: a literal "both-flanking is
    # ambiguous" rule would withhold these.
    pytest.param('Revenue ("$391.0 billion") rose [1].', [], id="both-flanking-opening-mark"),
    pytest.param('The margin was "29.4%".', [], id="both-flanking-closing-mark"),
    pytest.param('Amounts are "(in millions)".', [], id="both-flanking-after-parenthetical"),
    pytest.param('It says "Net sales increased."[1] and "Revenue" [2].', [], id="both-flanking-before-citation"),
])
def test_nested_quotations_are_checked_whole_and_inner(answer, expected):
    assert unsupported_prose_quotations(answer, SOURCE) == expected


@pytest.mark.unit
@pytest.mark.parametrize("answer,expected", [
    # Character references and escapes render as the marks they name.
    pytest.param(f"The filing calls it &quot;{INV}&quot; [1].", [NOT_IN], id="entity-quot"),
    pytest.param(f"The filing calls it &ldquo;{INV}&rdquo; [1].", [NOT_IN], id="entity-ldquo"),
    pytest.param(f"The filing calls it &#34;{INV}&#34; [1].", [NOT_IN], id="entity-decimal"),
    pytest.param(f"The filing calls it &#8220;{INV}&#8221; [1].", [NOT_IN], id="entity-decimal-curly"),
    pytest.param(f'The filing calls it \\"{INV}\\" [1].', [NOT_IN], id="escaped-straight-marks"),
    # Delimiters that vanish when rendered leave "label"INV"here", two balanced readings.
    pytest.param(f'The filing calls it "label"*{INV}*"here" [1].', [AMBIGUOUS], id="emphasis-between-quotes"),
    pytest.param(f'The filing calls it "label"**{INV}**"here" [1].', [AMBIGUOUS], id="strong-between-quotes"),
    pytest.param(f'The filing calls it "label"_{INV}_"here" [1].', [AMBIGUOUS], id="underscore-between-quotes"),
    pytest.param(f'The filing calls it "label"`{INV}`"here" [1].', [AMBIGUOUS], id="code-span-between-quotes"),
    pytest.param(f'The filing calls it "label"~~{INV}~~"here" [1].', [AMBIGUOUS], id="strikethrough-between-quotes"),
    pytest.param(f'The filing calls it "label"[{INV}](https://example.com)"here" [1].', [AMBIGUOUS],
                 id="link-between-quotes"),
    # GFM differences from CommonMark fail closed: a single tilde may vanish into strikethrough, a
    # footnote definition shows its text (markdown-it would hide this one as a link definition), and
    # a bare URL shows its text verbatim (markdown-it would decode the second character reference).
    pytest.param(f"The filing calls it “label”~{INV}~“~here” [1].", [AMBIGUOUS], id="tilde-decides-a-direction"),
    pytest.param(f'The filing says "ROE" [1].\n\n[^1]: https://www.sec.gov "{INV}"', [AMBIGUOUS],
                 id="footnote-definition"),
    pytest.param(f'The filing calls it "label&quot;{INV}](https://x)&quot;here" [1].', [AMBIGUOUS],
                 id="bare-url-character-reference"),
    pytest.param('Margins rose "~5%" and ~2 points [1].', [], id="tilde-that-decides-nothing"),
    pytest.param(f'See https://www.sec.gov/a_b_c and [Note 13](https://www.sec.gov/x): "{NI}" [1].', [],
                 id="urls-shown-verbatim"),
    pytest.param('The tag `&quot;` is code, and the filing says "ROE" [1].', [], id="code-span-shows-a-reference"),
    # Fail-closed cost: quoted text is matched as written here, tildes included, though GFM may strike
    # through and hide them.
    pytest.param('"Net income for 2025 amounted to ~€9,609.4 million~" [1]', [NOT_IN],
                 id="tilde-inside-quotation-matched-as-written"),
    # Invisible code points next to the marks: format characters are dropped, combining marks skipped.
    *[pytest.param(f'The filing calls it "label {mark}"*{INV}*"{mark} here" [1].', [NOT_IN, NOT_IN],
                   id=f"invisible-u{ord(mark):04x}-emphasis")
      for mark in ("​", "⁠", "﻿", "‌", "­", "‎", "͏", "️")],
    pytest.param(f'"The policy names the approved label ​"*{INV}*"​ and describes the release procedure."',
                 [NOT_IN, NOT_IN], id="invisible-u200b-long-form"),
    pytest.param(f'The filing calls it "label ​"({INV})"​ here" [1].', [NOT_IN, NOT_IN],
                 id="format-character-without-markup"),
    pytest.param(f'The filing calls it "label ͏"({INV})"͏ here" [1].', [NOT_IN, NOT_IN],
                 id="combining-mark-without-markup"),
    # Rendered formatting is not quoted text: these quote the filing.
    pytest.param('MD&A says "Gross margin percentage was **46.2%** in 2025, compared to 44.1% in 2024" [1].', [],
                 id="strong-inside-quotation"),
    pytest.param('It says "*Total net sales increased 2% or $8.0 billion during 2025*" [1].', [],
                 id="emphasised-quotation"),
    pytest.param(f'"*{NI}*" [1]', [], id="emphasised-long-quotation"),
    pytest.param("The MD&amp;A notes &ldquo;Segment Information and Geographic Data&rdquo; [1].", [],
                 id="character-references-in-a-supported-quote"),
    pytest.param(f'See [Note 13](https://www.sec.gov/x): "{NI}" [1].', [], id="link-beside-a-supported-quote"),
])
def test_quotations_are_read_as_rendered(answer, expected):
    assert unsupported_prose_quotations(answer, SOURCE) == expected


@pytest.mark.unit
@pytest.mark.parametrize("answer,expected", [
    pytest.param(')_`(€".]&quot;`.[1]', [UNBALANCED], id="code-span-keeps-a-reference"),
    pytest.param('\\" **"~~***label', [AMBIGUOUS], id="emphasis-markdown-it-leaves-as-text"),
    pytest.param('  \n[\\"&quot;`and describes the release procedurehere`*`(and describes the release procedure)_'
                 'Invented text missing from the source', [AMBIGUOUS], id="code-span-markdown-it-leaves-as-text"),
    pytest.param(' \\`](https://x)`- )<[1]&quot;[1]`~', [AMBIGUOUS], id="bare-url-swallows-a-backtick"),
    pytest.param('* ~https://x.com/`<[[[&quot;`#. > <.', [AMBIGUOUS], id="bare-url-swallows-a-code-span"),
])
def test_display_divergences_fail_closed(answer, expected):
    """Degenerate markdown from a seeded token fuzz on which markdown-it and the displayed
    remark-gfm text disagree. The display withholds each one, and each one published under the
    mutation that removes its guard."""
    assert unsupported_prose_quotations(answer, SOURCE) == expected


@pytest.mark.unit
def test_an_outer_quotation_reason_precedes_its_inner_one():
    answer = f"“Net income for 2025 … the filing calls it “{INVENTED}” here” [1]"
    assert unsupported_prose_quotations(answer, SOURCE) == [ELIDED, NOT_IN]


@pytest.mark.unit
def test_interrupted_straight_quotation_is_a_known_limit():
    """Pinned limit, not a guarantee: whitespace just inside both inner marks reads, as typography
    does, as two quotations around unquoted prose, so the middle is not checked."""
    answer = f'"The policy names the approved label—" {INV} "—and describes the release procedure." [1]'
    assert unsupported_prose_quotations(answer, SOURCE) == []


@pytest.mark.unit
def test_work_past_the_bounds_fails_closed():
    assert unsupported_prose_quotations('"ROE" ' + "x" * _MAX_QUOTED_ANSWER_CHARS, SOURCE) == [AMBIGUOUS]
    assert unsupported_prose_quotations("No quotation " + "x" * _MAX_QUOTED_ANSWER_CHARS, SOURCE) == []
    at_cap = " ".join(['"ROE"'] * (_MAX_QUOTE_MARKS // 2)) + " [1]."
    assert unsupported_prose_quotations(at_cap, SOURCE) == []
    assert unsupported_prose_quotations(at_cap + ' "ROA"', SOURCE) == [AMBIGUOUS]
    long = ("net income for 2025 " * (_MAX_QUOTED_CHARS // 40 + 1)).strip()   # just over half the bound
    assert unsupported_prose_quotations(f"“{long}” [1]", SOURCE) == [NOT_IN]
    assert unsupported_prose_quotations(f"““{long}”” [1]", SOURCE) == [AMBIGUOUS]


def _adversarial_answers():
    """The round-4 reviews' slow inputs on c69504d7 (33.5 s, 145.8 s, 2.6 s, 0.94 s and 8.1 s there),
    deep nesting, the worst shapes under both bounds, and long link-like and delimiter runs."""
    yield "x " + '.".' * 12 + "“”" * 3330 + " “x"
    yield "x " + "“x" * 12 + " " + '.".' * 12 + " " + "“”" * 3300
    yield '.".' * 11 + " “x”" * 2000
    yield '"ROE" ' * 312 + '"R"'
    yield '"ROE" ' * 1162 + '"R"'
    yield "“" * 2500 + "x" * 5000 + "”" * 2500
    yield "“" * (_MAX_QUOTE_MARKS // 2) + "net income for 2025 " * 500 + "”" * (_MAX_QUOTE_MARKS // 2)
    yield '.".' * _MAX_QUOTE_MARKS
    yield "“" + ("net income for 2025 " * (_MAX_QUOTED_CHARS // 20 - 1)).strip() + "”"
    yield '[a](b "' * 2000 + '"x"'
    yield '"' + "*" * 9_000 + '"x' + "_" * 9_000 + '"'
    yield "![" * 5000 + '"x"'
    yield "[" * 10_000 + '"x"'
    yield '"ROE" ' + "x" * _MAX_QUOTED_ANSWER_CHARS


@pytest.mark.unit
def test_quotation_work_is_bounded(monkeypatch):
    """The work per answer is bounded by the mark cap, not by the number of readings or marks."""
    normalized = []
    normalize = copilot_service.normalize_for_match
    monkeypatch.setattr(copilot_service, "normalize_for_match",
                        lambda text: normalized.append(len(text)) or normalize(text))
    for answer in _adversarial_answers():
        normalized.clear()
        started = time.perf_counter()
        unsupported_prose_quotations(answer, SOURCE)
        # Generous wall-clock bound against a slow CI host (markdown parsing of the bracket runs is
        # the slowest step); the characters normalized are the deterministic bound: at most five
        # candidate texts per quotation, within the quoted-text bound.
        assert time.perf_counter() - started < 2.0
        assert len(normalized) <= 5 * (_MAX_QUOTE_MARKS // 2) and sum(normalized) <= 5 * _MAX_QUOTED_CHARS


@pytest.mark.unit
@pytest.mark.parametrize("answer", [
    f"Net income for 2025 amounted to €9,609.4 million [F1], which the filing describes as \"{NI}\" [1].",
    '**Revenue:** RMB996,347 million [F1]. The cover page lists the "Date of event requiring this shell company'
    ' report" [2].',
    "- Revenue grew to RMB1,023,670 million [F1].\n- The filing says it \"further increased by 3% to RMB1,023,670"
    ' million (US$148,401 million) in fiscal year 2026" [2].',
    "| Metric | Note |\n| --- | --- |\n| Segments | see Note 13, “Segment Information and Geographic Data” [1] |",
    '### What the audit covered\n\nThe "consolidated balance sheets of Tesla, Inc. and its subsidiaries" [1].',
    'The filing\'s "ROE", "ROA" and "EBITDA" labels are not defined; "Revenue" is [1].',
    f'_"{NI}"_ [1]',
    'The tag `us-gaap:Revenues` is used, and the filing says "Total net sales" [1].',
    "See [Note 13](https://www.sec.gov/x) — “Segment Information and Geographic Data” [1].",
    "The MD&amp;A notes &ldquo;Segment Information and Geographic Data&rdquo; [1].",
    'Net income rose—"Net income for 2025 amounted to €9,609.4 million"—per the MD&A [1].',
    'The company ("Tesla") reported revenue [F1].',
    f"The filing says “{PREFIX}“{INNER}”{SUFFIX}” [1].",
    '"...amounted to €9,609.4 million, representing 29.4%..." [1]',
    f'> "{NI}" [1]',
    'Gross margin was "46.2%" and the increase "$8.0 billion" [1].',
    '**Answer:** The filing says "Total net sales increased 2% or $8.0 billion during 2025" [1].',
    '"Gross margin percentage was 46.2% in 2025, compared to 44.1% in 2024" [1].\n\nIt also says "Total net sales'
    ' increased 2% or $8.0 billion during 2025" [2].',
    'It states "Net income for 2025 amounted to €9,609.4 million."[1]',
    'This filing does not disclose "adjusted EBITDA"; it reports "Net income" [1].',
    "The company’s auditor covered “consolidated balance sheets of Tesla, Inc. and its subsidiaries” [1].",
])
def test_analyst_style_answers_publish(answer):
    assert unsupported_prose_quotations(answer, SOURCE) == []


@pytest.mark.unit
@pytest.mark.parametrize("answer", [
    f"The filing calls it '{INV}' [1].",
    f"The filing calls it ‘{INV}’ [1].",
    f"The filing calls it «{INV}» [1].",
    f"The filing calls it 「{INV}」 [1].",
    f"> {INV} [1].",
])
def test_other_quotation_forms_are_a_decided_limit(answer):
    """Known, decided limit (PR #1029, follow-up (iii)), not a guarantee and not exhaustive
    verification: decision F checks double quotation marks only, so these forms publish unchecked."""
    assert unsupported_prose_quotations(answer, SOURCE) == []


@pytest.mark.unit
@pytest.mark.parametrize("source", ["", None])
def test_missing_source_text_fails_closed(source):
    assert unsupported_prose_quotations(f'"{NI}" and "Revenue ... 996,347"', source) == [
        "quotation_source_unavailable", "quotation_source_unavailable"]


@pytest.mark.unit
def test_short_stitched_label_and_cell_is_a_known_limit():
    """Pinned limit, not a guarantee: under the 24-character floor a stitched label stays a term."""
    assert unsupported_prose_quotations('showing "Net income 9,609.4" [1].', SOURCE) == []


def _filing(source):
    return type("F", (), {"content_cache": type("C", (), {"critical_excerpt": source, "markdown_content": None})(),
                          "company": None, "company_id": 1, "accession_number": "a", "xbrl_data": None,
                          "document_url": "https://www.sec.gov/x", "sec_url": None,
                          "filing_type": "10-K", "filing_date": None, "period_of_report": None})()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_logs_constant_quotation_reason(monkeypatch, caplog):
    source = "Item 7. Revenue increased to 391.0 billion driven by strong iPhone demand. Margins expanded."
    good = '[{"n": 1, "excerpt": "Revenue increased to 391.0 billion driven by strong iPhone demand."}]'

    async def stream(*_args, **_kwargs):
        yield 'It said "Revenue increased to 391.0 billion. Margins expanded" [1].\n===CITATIONS===\n' + good

    monkeypatch.setattr(copilot_service.openai_service, "stream_chat_with_tools", stream)
    with caplog.at_level(logging.WARNING, logger=copilot_service.logger.name):
        events = [e async for e in copilot_service.answer_filing_question(filing=_filing(source), question="q")]
    assert events[-1] == {"type": "error", "message": copilot_service._PUBLICATION_ERROR}
    assert "Unsupported prose quotation: quotation_not_in_source" in caplog.text
    assert "Margins expanded" not in caplog.text


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("reason,published", [
    (f'Segment margins are not broken out; the filing only says "{INV} and nothing more".', False),
    ('Segment margins are not broken out; the filing only says "Net income for 2025 amounted to €9,609.4'
     ' million".', True),
    ('Segment margins are not broken out; the filing names no "segment margin" measure.', True),
])
async def test_not_disclosed_reason_quotations_are_checked(monkeypatch, caplog, reason, published):
    """The not-disclosed verdict is published prose too: its quotations take the same check."""
    source = "Net income for 2025 amounted to €9,609.4 million, representing 29.4% of total net sales."

    async def stream(*_args, **_kwargs):
        yield f'===NOT_DISCLOSED===\n{reason}\n===FOLLOWUPS===\n["What changed in margins?", "What are the risks?"]'

    monkeypatch.setattr(copilot_service.openai_service, "stream_chat_with_tools", stream)
    with caplog.at_level(logging.WARNING, logger=copilot_service.logger.name):
        events = [e async for e in copilot_service.answer_filing_question(filing=_filing(source), question="q")]
    if published:
        assert events[-1]["type"] == "complete" and events[-1]["kind"] == "not_disclosed"
        assert events[-1]["answer"] == reason
    else:
        assert events[-1] == {"type": "error", "message": copilot_service._PUBLICATION_ERROR}
        assert all(event["type"] != "not_disclosed" for event in events)
        assert "Unsupported prose quotation: quotation_not_in_source" in caplog.text
        assert "nothing more" not in caplog.text


@pytest.mark.unit
@pytest.mark.asyncio
async def test_published_answer_is_not_rewritten_by_the_reading(monkeypatch):
    """The rendered reading only decides whether to withhold; a published answer stays byte-identical."""
    source = "Net income for 2025 amounted to €9,609.4 million, representing 29.4% of total net sales."
    answer = ('The MD&amp;A says **"Net income for 2025 amounted to €9,609.4 million"** and &ldquo;representing'
              ' 29.4% of total net sales&rdquo; [link](https://www.sec.gov/x), with *emphasis*\u200b kept.')

    async def stream(*_args, **_kwargs):
        yield answer + "\n===CITATIONS===\n[]"

    monkeypatch.setattr(copilot_service.openai_service, "stream_chat_with_tools", stream)
    events = [e async for e in copilot_service.answer_filing_question(filing=_filing(source), question="q")]
    assert events[-1]["type"] == "complete" and events[-1]["answer"] == answer
