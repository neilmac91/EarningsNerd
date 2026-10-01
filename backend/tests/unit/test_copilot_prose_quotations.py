"""Published prose quotations must be contiguous filing text (decision F, #1029).

Filing fixtures are verbatim snippets of the retained #1021 qualification sources (newlines, NBSPs
and table-cell layout as retained); the synthetic lines are labelled as such. The composed spans are
the retained main-code failures: "Total net sales 32,667.3" (ASML, runs 36640254449 and 36800236360)
and "Revenue ... 996,347" (BABA, run 36777581481). The check reuses the citation verifier's
normalizer and its 24-character floor.

Each published text is read as it is displayed. The answer is markdown (react-markdown 10 +
remark-gfm), read here with markdown-it-py within a small subset both parsers read alike: a link
shows its text, escapes and character references show their characters, emphasis and code-span
delimiters do not show, and default-ignorable code points are dropped; controls, separators, the
byte-order mark, bidi controls and right-to-left scripts fail closed. A quoting answer that uses
markdown outside the subset (raw HTML, images, link titles, reference definitions, footnotes, deep
nesting and the other forms pinned below) is ``ambiguous_quotation``; so is a mark whose direction
a delimiter left as text decides. That the parsers agree on the subset is the residual assumption,
not exact parity. The not-disclosed reason and the follow-up chips are displayed as plain text and
read as such. A mark's direction comes from its glyph (“ „ ‟ open, ” closes) or, for a straight
mark, from its neighbours as CommonMark reads emphasis, so '"x "y" z"' and '"x ("y") z"' read as
nesting and "y" is checked too. Curly marks pair only with curly marks, straight marks only with
straight marks between the same curly marks. Exactly one balanced reading is checked; none is
``unbalanced_quotation``; more than one, a curly mark facing the wrong way, or work past the bounds
is ``ambiguous_quotation``. The reading decides only whether to withhold: published text is never
rewritten. Only double quotation marks are in scope (see the pinned limits below); this is not
exhaustive verification of every quotation form.
"""
import importlib.util
import json
import logging
import sys
import threading
import time
import unicodedata

import pytest

from app.services import copilot_service
from app.services.copilot_service import (
    _MAX_QUOTE_MARKS,
    _MAX_QUOTED_ANSWER_CHARS,
    _MAX_QUOTED_CHARS,
    unsupported_plain_quotations,
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
# One sample per range of the default-ignorable code points dropped as invisible.
INVISIBLE = ("\u00ad", "\u034f", "\u115f", "\u1160", "\u17b4", "\u17b5", "\u180e", "\u200b", "\u2063", "\u206b", "\u3164",
             "\ufe0f", "\uffa0", "\ufff3", "\U0001bca1", "\U0001d175", "\U000e0041")
# A realistic EDGAR document URL: the underscore in it is not emphasis.
EDGAR = "https://www.sec.gov/Archives/edgar/data/789019/000095017024087843/msft-10k_20240630.htm"


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
    f'- The filing says "{NI}."\n- Revenue grew [1].',                    # a list item's end is a break
    f'The filing says "{NI}."\nRevenue grew [1].',                         # so is a soft line break
    f'See the [10-K]({EDGAR}): "{NI}" [1].',                               # a link destination is not shown
    f'See <{EDGAR}>: "{NI}" [1].',                                          # an autolink is not HTML
    f'See [{EDGAR}]({EDGAR}): "{NI}" [1].',                                 # a URL as link text
    f'The filing says "{NI}" [1].\n\n---\n\nThat is all.',                   # a thematic break
    f'- Revenue grew [1].\n---\nThe filing says "{NI}" [1].',               # a break after a list
    f'Net income\n---\nThe filing says "{NI}" [1].',                        # a setext heading underline
    f'**Net income** above; the filing says "{NI}" [1].',                    # emphasis, no stray delimiter
    f'**Revenue** is tagged us-gaap_Revenues; the filing says "{NI}" [1].',  # an underscore inside a word
    f'**Margin** is 5 * 3; the filing says "{NI}" [1].',                     # an asterisk between spaces
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
    pytest.param(f'The filing calls it "label&quot;{INV}](www.x.com)&quot;here" [1].', [AMBIGUOUS],
                 id="www-url-character-reference"),
    pytest.param('Margins rose "~5%" and ~2 points [1].', [], id="tilde-that-decides-nothing"),
    pytest.param(f'See https://www.sec.gov/a_b_c and [Note 13](https://www.sec.gov/x): "{NI}" [1].', [],
                 id="urls-shown-verbatim"),
    pytest.param('The tag `&quot;` is code, and the filing says "ROE" [1].', [], id="code-span-shows-a-reference"),
    # Fail-closed cost: quoted text is matched as written here, tildes included, though GFM may strike
    # through and hide them.
    pytest.param('"Net income for 2025 amounted to ~€9,609.4 million~" [1]', [NOT_IN],
                 id="tilde-inside-quotation-matched-as-written"),
    # Invisible code points next to the marks and inside a quotation: every Default_Ignorable_Code_Point
    # but the bidi controls and U+FEFF (which fail closed) is dropped, one sample per range here, and
    # combining marks are skipped.
    *[pytest.param(f'The filing calls it "label {mark}"*{INV}*"{mark} here" [1].', [NOT_IN, NOT_IN],
                   id=f"invisible-u{ord(mark):04x}-emphasis") for mark in INVISIBLE],
    *[pytest.param(f'The filing says "Net income{mark} for 2025 amounted to €9,609.4 million" [1].', [],
                   id=f"invisible-u{ord(mark):04x}-inside-a-supported-quotation") for mark in INVISIBLE],
    pytest.param(f'"The policy names the approved label \u200b"*{INV}*"\u200b and describes the release procedure."',
                 [NOT_IN, NOT_IN], id="invisible-u200b-long-form"),
    pytest.param(f'The filing calls it "label \u200b"({INV})"\u200b here" [1].', [NOT_IN, NOT_IN],
                 id="format-character-without-markup"),
    pytest.param(f'The filing calls it "label \u034f"({INV})"\u034f here" [1].', [NOT_IN, NOT_IN],
                 id="grapheme-joiner-without-markup"),
    pytest.param(f'The filing calls it "label \u0301"({INV})"\u0301 here" [1].', [NOT_IN, NOT_IN],
                 id="combining-mark-without-markup"),
    pytest.param(f'The filing calls it "label \u3164"({INV})"\u3164 here" [1].', [NOT_IN, NOT_IN],
                 id="hangul-filler-without-markup"),
    pytest.param(f'The filing calls it "label \uffa0"({INV})"\uffa0 here" [1].', [NOT_IN, NOT_IN],
                 id="halfwidth-hangul-filler-without-markup"),
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
def test_quotations_are_read_as_displayed(answer, expected):
    assert unsupported_prose_quotations(answer, SOURCE) == expected


@pytest.mark.unit
@pytest.mark.parametrize("answer,expected", [
    pytest.param(')_`(€".]&quot;`.[1]', [UNBALANCED], id="code-span-keeps-a-reference"),
    pytest.param('\\" **"~~***label', [AMBIGUOUS], id="emphasis-markdown-it-leaves-as-text"),
    pytest.param('  \n[\\"&quot;`and describes the release procedurehere`*`(and describes the release procedure)_'
                 'Invented text missing from the source', [AMBIGUOUS], id="code-span-markdown-it-leaves-as-text"),
    pytest.param(' \\`](https://x)`- )<[1]&quot;[1]`~', [AMBIGUOUS], id="bare-url-swallows-a-backtick"),
    pytest.param('* ~https://x.com/`<[[[&quot;`#. > <.', [AMBIGUOUS], id="bare-url-swallows-a-code-span"),
    # GFM shows the email address with its underscores, so the mark cannot open; markdown-it reads
    # them as emphasis.
    pytest.param('The filing calls it label"_Investor Relations_@apple.com" [1].', [AMBIGUOUS],
                 id="email-address-keeps-its-underscores"),
    # GFM shows an autolink as written; markdown-it decodes %22 into a mark that closes the quotation.
    pytest.param('The filing says "ROE <https://sec.gov/%22> [1].', [AMBIGUOUS], id="autolink-decodes-a-mark"),
    # Block forms the parsers read differently. Displayed, each quotation below holds text markdown-it
    # does not show: a stray delimiter row hides a table split, the rest show list markers as text.
    pytest.param('The filing calls it x"*label\n|-|\nhere*"y [1].', [AMBIGUOUS], id="table-without-a-pipe-header"),
    pytest.param(f'   - It reports "ROE" and\n    > &quot;{INV} [1].', [AMBIGUOUS], id="quote-marker-indented-as-code"),
    pytest.param('The filing says "Net income for 2025\n- 1.\namounted to €9,609.4 million" [1].', [AMBIGUOUS],
                 id="empty-list-item"),
    pytest.param('The filing says "Net income\n\n    for 2025\n1.\n   amounted to €9,609.4 million" [1].', [AMBIGUOUS],
                 id="list-item-opening-on-a-blank-line"),
    pytest.param('The filing says "Net income\n\n    for 2025\n\n2) amounted to €9,609.4 million" [1].', [AMBIGUOUS],
                 id="numbered-past-one-after-a-code-block"),
    pytest.param('The filing says "Net income for 2025\n- 2) amounted to €9,609.4 million" [1].', [AMBIGUOUS],
                 id="numbered-past-one-behind-another-marker"),
    pytest.param('> x"*label\n> |-|\n> here*"y [1]', [AMBIGUOUS], id="delimiter-row-in-a-blockquote"),
    # A literal shown twice but written once (the round-5 review's case), and a '*' left as text in a
    # paragraph without emphasis, which the display pairs and hides.
    pytest.param('See https://x)"here" and the filing calls it "label&quot;Invented text missing from the'
                 ' source](https://x)&quot;here" [1].', [AMBIGUOUS], id="literal-counted-once"),
    pytest.param('  ,Invented text missing from the source*__Invented text missing from the source*"([1]"', [AMBIGUOUS],
                 id="star-left-as-text-may-vanish"),
    # Emphasis runs the parsers pair differently (the round-5 reviews' cases, and a fuzz finding):
    # runs of three or more delimiters, and a delimiter left as text where there is emphasis.
    pytest.param('".x******ROE (*"* Invented text missing from the source ****" here**"******.*', [AMBIGUOUS],
                 id="emphasis-run-review-repro"),
    pytest.param(f'The filing says "{NI}" [1]. ***?* t*x*', [AMBIGUOUS], id="emphasis-run-of-three"),
    pytest.param(f'The filing says "{NI}" [1]. *-_*e*_', [AMBIGUOUS], id="emphasis-mixed-delimiters"),
    pytest.param('xThe policy names the approved labelROE*_ (__"*?*!*The policy names the approved label,"*',
                 [AMBIGUOUS], id="emphasis-pairs-differently-around-a-mark"),
    pytest.param('__**ROEt*"The policy names the approved label*__"(', [AMBIGUOUS], id="emphasis-run-split-in-two"),
])
def test_display_divergences_fail_closed(answer, expected):
    """Markdown on which markdown-it and the displayed remark-gfm text disagree, from a seeded fuzz
    or built on one of its findings. The display withholds each one, and each one published under
    the mutation that removes its guard."""
    assert unsupported_prose_quotations(answer, SOURCE) == expected


@pytest.mark.unit
@pytest.mark.parametrize("answer", [
    # Raw HTML of any kind (the round-5 review repros): the display shows it as text, links and
    # titles inside it included; it is found in the source text, not parsed.
    pytest.param(f'<p>The filing names it [here](https://www.sec.gov/x "{INV}") [1].</p>', id="html-paragraph"),
    pytest.param(f'Revenue rose [1].\n\n<br>\nThe filing names it [here](https://www.sec.gov/x "{INV}").',
                 id="html-break"),
    pytest.param(f'See <!-- [x](https://www.sec.gov "{INV}") --> here [1].', id="html-comment"),
    pytest.param('The filing calls it "label <!-- [x](https://www.sec.gov/"Invented-text-missing-from-the-source") -->'
                 ' here" [1].', id="html-comment-without-a-title"),
    pytest.param('<div>\n"Invented text&#34; &#34;missing from the source" [1]\n</div>', id="html-block-references"),
    pytest.param(f'<div>\nSee [the note](https://www.sec.gov/x "{INV} here") [1].\n</div>', id="html-block-link-title"),
    # Footnote syntax anywhere, reference definitions, link titles and images.
    pytest.param(f'The filing says it [^1].\n\n> [^1]: https://www.sec.gov "{INV}"', id="footnote-in-a-blockquote"),
    pytest.param(f'The filing says it [^1].\n\n- [^1]: https://www.sec.gov "{INV}"', id="footnote-in-a-list"),
    # Displayed, the call shows as "1" between the marks (two readings) and the definition moves.
    pytest.param('The filing calls it "label"[^1]"here" [1].\n\n> [^1]: The note.', id="footnote-call"),
    pytest.param(f'The filing calls it [the note][1] [1].\n\n[1]: https://www.sec.gov "{INV}"', id="reference-definition"),
    pytest.param(f'The filing says "{NI}" [1].\n\n[note]: https://www.sec.gov "{INV}"', id="unused-reference-definition"),
    pytest.param(f'The filing names it [here](https://www.sec.gov/x "{INV}") [1].', id="link-title"),
    pytest.param(f'!["{INV}"](https://www.sec.gov/x)', id="image-alt-text"),
    pytest.param(f'The filing says "{NI}" [1].\n\n![chart](https://www.sec.gov/x.png)', id="image-beside-a-quotation"),
    # Nesting past the cap; markdown-it itself stops reading at 20 levels, the display does not.
    pytest.param(">" * 21 + f' "{INV}" [1]', id="blockquotes-21-deep"),
    pytest.param("".join("  " * level + "- x\n" for level in range(9)) + "  " * 9 + f'- "{INV}" [1]',
                 id="lists-10-deep"),
    pytest.param(f'> > > > > - - - - - - - - "{INV}" [1]', id="blockquotes-and-lists-13-deep"),
    pytest.param("".join("  " * level + "- Net income\n" for level in range(4)) + "  " * 4 + f'- It says "{NI}" [1].',
                 id="lists-5-deep-past-the-cap"),
    pytest.param("".join("   " * level + "1. Net income\n" for level in range(4)) + "   " * 4 + f'1. It says "{NI}" [1].',
                 id="ordered-lists-5-deep-past-the-cap"),
])
def test_markdown_outside_the_read_subset_fails_closed(answer):
    assert unsupported_prose_quotations(answer, SOURCE) == [AMBIGUOUS]


@pytest.mark.unit
@pytest.mark.parametrize("answer,expected", [
    pytest.param(f'The filing says:\n\n```\n"{INV}"\n```\n', [NOT_IN], id="fenced-invented"),
    pytest.param(f'The filing says:\n\n    "{INV}"\n', [NOT_IN], id="indented-invented"),
    pytest.param(f'The filing says:\n\n```\n"{NI}"\n```\n', [], id="fenced-in-source"),
    pytest.param(f'The filing says:\n\n    "{NI}"\n', [], id="indented-in-source"),
])
def test_code_blocks_are_read_verbatim(answer, expected):
    assert unsupported_prose_quotations(answer, SOURCE) == expected


TABLE = "| Line | Text |\n| --- | --- |\n| Net income | {} |\n| | {} |"


@pytest.mark.unit
@pytest.mark.parametrize("answer,expected", [
    pytest.param(TABLE.format('"Net income for 2025', 'amounted to €9,609.4 million" [1]'), [], id="in-source"),
    pytest.param(TABLE.format('"Invented text missing', 'from the source" [1]'), [NOT_IN], id="invented"),
])
def test_quotation_across_table_cells_is_pinned(answer, expected):
    """Pinned behaviour: table cells are read in display order, each ending a line, so a quotation
    may span cells and is checked as one span."""
    assert unsupported_prose_quotations(answer, SOURCE) == expected


@pytest.mark.unit
@pytest.mark.parametrize("answer", [
    pytest.param(f'***Net income:*** the filing says "{NI}" [1].', id="bold-italic-run"),
    pytest.param(f'The filing says ***"{NI}"*** [1].', id="bold-italic-quotation"),
    pytest.param(f'___Note___: the filing says "{NI}" [1].', id="underscore-run"),
    pytest.param(f'Net income doubled![1] The filing says "{NI}" [1].', id="exclamation-before-a-marker"),
    pytest.param(f'See **https://www.sec.gov/x**; the filing says "{NI}" [1].', id="emphasised-url"),
    pytest.param(f'Use the `us-gaap tag; the filing says "{NI}" [1].', id="unclosed-backtick"),
    pytest.param(f'The *margin* is 5*3; the filing says "{NI}" [1].', id="asterisk-beside-emphasis"),
    pytest.param(f'- Net income\n\n  > The filing says "{NI}" [1].', id="blockquote-in-a-list"),
    pytest.param(f'> The filing says "{NI}" [1].\n>\n> > It adds nothing else.', id="nested-blockquote"),
    pytest.param(f'> The filing says "{NI}"\nwhich is lazily continued [1].', id="lazy-blockquote-line"),
    pytest.param(f'- [x] The filing says "{NI}" [1].', id="task-list"),
    pytest.param(f'The filing says "{NI}" [1].<br>That is all.', id="html-break"),
    pytest.param(f'The cell tag `<td>` holds it; the filing says "{NI}" [1].', id="tag-in-a-code-span"),
    pytest.param(f'The filing says "{NI}" ([Note 13](https://www.sec.gov/x "Note 13")) [1].', id="link-title"),
    pytest.param(f'- Net income:\n\tthe filing says "{NI}" [1].', id="tab-indentation"),
    pytest.param(f'**Net income**~€9.6 billion; the filing says "{NI}" [1].', id="tilde-beside-bold"),
    pytest.param(f'Net income was **€9.6 billion*; the filing says "{NI}" [1].', id="unpaired-emphasis-run"),
])
def test_benign_markdown_outside_the_subset_is_a_fail_closed_cost(answer):
    """Pinned costs of the allowlist, listed rather than widened: realistic answers that quote the
    filing correctly but use markdown outside the read subset are withheld."""
    assert unsupported_prose_quotations(answer, SOURCE) == [AMBIGUOUS]


@pytest.mark.unit
def test_inch_mark_is_a_fail_closed_cost():
    """Pinned cost, not a guarantee: a straight inch mark reads as an unbalanced quotation."""
    assert unsupported_prose_quotations('The iPhone 16 has a 6.1" display [1].', SOURCE) == [UNBALANCED]


REASON = "Segment margins are not broken out"


@pytest.mark.unit
@pytest.mark.parametrize("text,expected", [
    # The not-disclosed reason and the follow-up chips are shown as plain text: markdown syntax,
    # character references and fences show as written, so their quote marks are read as written.
    pytest.param(f'{REASON} [see Item 7](https://www.sec.gov/x "{INV}").', [NOT_IN], id="link-title-shown"),
    pytest.param(f'{REASON}; the filing only says !["{INV}"](x).', [NOT_IN], id="image-syntax-shown"),
    pytest.param(f'{REASON}; the filing only says "Invented text&#34; &#34;missing from the source".', [NOT_IN],
                 id="character-references-shown"),
    pytest.param(f'```"{INV}"\n{REASON}.\n```', [NOT_IN], id="fence-shown"),
    pytest.param(f'Why does the filing say "{INV}"?', [NOT_IN], id="chip"),
    pytest.param(f'It says "label"*{INV}*"here".', [], id="asterisks-shown"),
    pytest.param(f'It says "label \u3164"({INV})"\u3164 here".', [NOT_IN, NOT_IN], id="default-ignorable-dropped"),
    pytest.param(f'What does "{NI}" cover?', [], id="chip-quoting-the-filing"),
    pytest.param("What are the risks?", [], id="chip-without-quotation"),
])
def test_plain_text_is_read_as_written(text, expected):
    assert unsupported_plain_quotations(text, SOURCE) == expected


# Characters that change what a reader sees without being plain visible text fail closed on every
# published surface (the round-6 reviews' repros): controls, separators, the byte-order mark, bidi
# controls and right-to-left scripts. The bidi repro reads, displayed, as a quotation of the source's
# "missing from the source" text reversed around the invented text.
BIDI = 'Invented text\u2067\u202e"ecruos eht morf gnissim \u202c\u2069'
NESTED = '"The policy names the approved label ("{0}Invented text missing from the source{0}") and describes the release procedure."'
GATED = ("\x00", "\x08", "\x0b", "\x0c", "\x0e", "\x1c", "\x1d", "\x1e", "\x1f", "\x7f", "\x85", "\x9f", "\u1680", "\u2028",
         "\u2029", "\ufeff", "\u061c", "\u200e", "\u200f", "\u202a", "\u202e", "\u2066", "\u2069", "\u05d0", "\u0627",
         "\ufb1d", "\ufe70", "\U00010800", "\U0001e800")


@pytest.mark.unit
@pytest.mark.parametrize("answer", [
    pytest.param(f'The filing says "{BIDI} [1].', id="bidi-reordered-quotation"),
    pytest.param('The filing says "Invented text&#x2067;&#x202E;"ecruos eht morf gnissim &#x202C;&#x2069; [1].',
                 id="bidi-by-character-reference"),
    pytest.param(f'The filing says "{NI}"&#x5D0; [1].', id="right-to-left-letter-by-character-reference"),
    *[pytest.param(NESTED.format(char) + " [1]", id=f"nested-u{ord(char):04x}")
      for char in ("\x1c", "\x0b", "\x0c", "\x1d", "\x1e", "\x1f", "\x85", "\u1680")],
    *[pytest.param('"The policy names the approved label ("{0}{1} {2} {1}{0}") and describes the release procedure." [1]'
                   .format(delimiter, char, INV), id=f"emphasis-{len(delimiter)}{delimiter[0]}-u{ord(char):04x}")
      for char in ("\ufeff", "\u2028", "\u2029") for delimiter in ("*", "**", "***", "_", "__")],
    *[pytest.param(f'"ROE {url}{char}abc&quot;.def {INV} {url}{char}abc.&quot;def here" [1]', id=f"url-{url[:3]}-u{ord(char):04x}")
      for url in ("https://x.co/", "www.x.co/") for char in ("\x1c", "\x85")],
    *[pytest.param(f'The filing says "{NI}"{char} [1].', id=f"beside-a-supported-quote-u{ord(char):04x}") for char in GATED],
])
def test_characters_that_change_the_display_fail_closed_in_the_answer(answer):
    assert unsupported_prose_quotations(answer, SOURCE) == [AMBIGUOUS]


@pytest.mark.unit
@pytest.mark.parametrize("text", [
    pytest.param(f'{REASON}; the filing only says "{BIDI}.', id="reason-bidi"),
    pytest.param(f'Why does the filing say "{BIDI}?', id="chip-bidi"),
    *[pytest.param(NESTED.format(char), id=f"nested-u{ord(char):04x}")
      for char in ("\x1c", "\x0b", "\x0c", "\x1d", "\x1e", "\x1f", "\x85", "\u1680", "\ufeff", "\u2028", "\u2029")],
    *[pytest.param(f'What does "{NI}"{char} cover?', id=f"beside-a-supported-quote-u{ord(char):04x}") for char in GATED],
])
def test_characters_that_change_the_display_fail_closed_in_plain_text(text):
    assert unsupported_plain_quotations(text, SOURCE) == [AMBIGUOUS]


@pytest.mark.unit
def test_whitespace_read_beside_marks_is_the_display_whitespace():
    """Outside the characters that fail closed, str.isspace (used to read a mark's neighbours) holds
    exactly for CommonMark's whitespace: Unicode Zs, tab, line feed and carriage return."""
    gate = copilot_service._FAIL_CLOSED_CHARS_RE
    python = {code for code in range(sys.maxunicode + 1) if chr(code).isspace() and not gate.match(chr(code))}
    commonmark = {code for code in range(sys.maxunicode + 1)
                  if (unicodedata.category(chr(code)) == "Zs" or chr(code) in "\t\n\r") and not gate.match(chr(code))}
    assert python == commonmark


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
    # Decided bound: text that may quote and runs past 8,000 characters is withheld unchecked.
    assert unsupported_prose_quotations(('"ROE" ' + "x" * 8_000)[:8_001], SOURCE) == [AMBIGUOUS]
    assert unsupported_prose_quotations(('"ROE" ' + "x" * 8_000)[:8_000], SOURCE) == []
    assert unsupported_prose_quotations("No quotation " + "x" * _MAX_QUOTED_ANSWER_CHARS, SOURCE) == []
    assert unsupported_plain_quotations('"ROE" ' + "x" * _MAX_QUOTED_ANSWER_CHARS, SOURCE) == [AMBIGUOUS]
    assert unsupported_plain_quotations("No quotation " + "x" * _MAX_QUOTED_ANSWER_CHARS, SOURCE) == []
    # Decided bound: an answer that may quote and opens more than 256 brackets is withheld unchecked.
    assert unsupported_prose_quotations(f'The filing says "{NI}" ' + "[1]" * 256, SOURCE) == []
    assert unsupported_prose_quotations(f'The filing says "{NI}" ' + "[1]" * 257, SOURCE) == [AMBIGUOUS]
    at_cap = " ".join(['"ROE"'] * (_MAX_QUOTE_MARKS // 2)) + " [1]."
    assert unsupported_prose_quotations(at_cap, SOURCE) == []
    assert unsupported_prose_quotations(at_cap + ' "ROA"', SOURCE) == [AMBIGUOUS]
    long = ("net income for 2025 " * (_MAX_QUOTED_CHARS // 80 + 1)).strip()   # just over a quarter of the bound
    assert unsupported_prose_quotations(f"“{long}” [1]", SOURCE) == [NOT_IN]
    assert unsupported_prose_quotations(f"“““{long}””” [1]", SOURCE) == [NOT_IN] * 3
    assert unsupported_prose_quotations(f"““““{long}”””” [1]", SOURCE) == [AMBIGUOUS]


def _adversarial_answers():
    """The round-4 reviews' slow inputs on c69504d7 (33.5 s, 145.8 s, 2.6 s, 0.94 s and 8.1 s there),
    deep nesting, the worst shapes under each bound, and the slowest markdown shapes found at the
    character bound: delimiter, link-title, line, heading, table and image-bracket runs."""
    yield "x " + '.".' * 12 + "“”" * 3330 + " “x"
    yield "x " + "“x" * 12 + " " + '.".' * 12 + " " + "“”" * 3300
    yield '.".' * 11 + " “x”" * 2000
    yield '"ROE" ' * 312 + '"R"'
    yield '"ROE" ' * 1162 + '"R"'
    yield "“" * 2500 + "x" * 5000 + "”" * 2500
    yield "“" * (_MAX_QUOTE_MARKS // 2) + "net income for 2025 " * 390 + "”" * (_MAX_QUOTE_MARKS // 2)
    yield '.".' * _MAX_QUOTE_MARKS
    yield "“" + ("net income for 2025 " * (_MAX_QUOTED_ANSWER_CHARS // 20 - 1)).strip() + "”"
    yield "![" * 5000 + '"x"'
    yield "[" * 10_000 + '"x"'
    for shape in ('[a](b "', '"x"\n', '# "x"\n', "&#", '\\"', "` ", '"ROE" ' * 32 + "x" * _MAX_QUOTED_ANSWER_CHARS):
        yield (shape * _MAX_QUOTED_ANSWER_CHARS)[:_MAX_QUOTED_ANSWER_CHARS]
    for run in ("*", "~", "*_", "*a_", "\u0301", "\u200b"):
        yield ('"' + run * _MAX_QUOTED_ANSWER_CHARS)[:_MAX_QUOTED_ANSWER_CHARS - 1] + '"'
    yield ("|" + "a|" * 100 + "\n|" + "-|" * 100 + "\n" + ("|" + '"x"|' * 100 + "\n") * 40)[:_MAX_QUOTED_ANSWER_CHARS]
    # The round-6 review's slow shape (123-304 ms before image markup was found in the source text).
    for mark in ('"', "\u201c"):
        yield (mark + "![_" * _MAX_QUOTED_ANSWER_CHARS)[:_MAX_QUOTED_ANSWER_CHARS]
        yield (mark + "[_" * _MAX_QUOTED_ANSWER_CHARS)[:_MAX_QUOTED_ANSWER_CHARS]


@pytest.mark.unit
def test_quotation_work_is_bounded(monkeypatch):
    """The work per text is bounded by the character and mark caps, not by its readings or marks."""
    normalized = []
    normalize = copilot_service.normalize_for_match
    monkeypatch.setattr(copilot_service, "normalize_for_match",
                        lambda text: normalized.append(len(text)) or normalize(text))
    for answer in _adversarial_answers():
        for check in (unsupported_prose_quotations, unsupported_plain_quotations):
            elapsed = []
            for _ in range(3):
                normalized.clear()
                started = time.perf_counter()
                check(answer, SOURCE)
                elapsed.append(time.perf_counter() - started)
                # Deterministic: at most two normalized texts per quotation (the needle, then its
                # literal form), within the quoted-text bound.
                assert len(normalized) <= 2 * (_MAX_QUOTE_MARKS // 2) and sum(normalized) <= 2 * _MAX_QUOTED_CHARS
            # Realistic wall clock at the character bound (about 40 ms locally; markdown parsing of
            # delimiter runs is the slowest step). The best of three runs, so a busy host's
            # scheduling noise is not mistaken for work.
            assert min(elapsed) < 0.25


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
    f"The filing calls it \u301d{INV}\u301e [1].",
    f"The filing calls it \u301d{INV}\u301f [1].",
    f"The filing calls it \u275d{INV}\u275e [1].",
    f"The filing calls it \U0001f676{INV}\U0001f677 [1].",
    f"The filing calls it \u02ba{INV}\u02ba [1].",
    f"The filing calls it ''{INV}'' [1].",
    f"The filing calls it \u2033{INV}\u2033 [1].",
    f"The filing calls it \u02ee{INV}\u02ee [1].",
    f"The filing calls it \u05f4{INV}\u05f4 [1].",
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


ND_SOURCE = "Net income for 2025 amounted to €9,609.4 million, representing 29.4% of total net sales."
ND_ANSWER = 'The filing says "Net income for 2025 amounted to €9,609.4 million" [1].'
ND_CITATIONS = '[{"n": 1, "excerpt": "Net income for 2025 amounted to €9,609.4 million"}]'
WITHHELD_CHIPS = [f'Why does the filing say "{INV}"?', "What are the risks?"]


def _stream_of(text):
    async def stream(*_args, **_kwargs):
        yield text
    return stream


def _reply(path, chips, reason=f"{REASON}; the filing gives no segment breakdown."):
    if path == "answer":
        return f"{ND_ANSWER}\n===CITATIONS===\n{ND_CITATIONS}\n===FOLLOWUPS===\n{json.dumps(chips)}"
    return f"===NOT_DISCLOSED===\n{reason}\n===FOLLOWUPS===\n{json.dumps(chips)}"


def _assert_withheld(events, caplog, *private):
    """Only progress may precede the error: no answer-bearing event, and no candidate text leaks."""
    assert events[-1] == {"type": "error", "message": copilot_service._PUBLICATION_ERROR}
    assert all(event["type"] == "progress" for event in events[:-1])
    assert "Unsupported prose quotation: quotation_not_in_source" in caplog.text
    for text in private:
        assert text not in json.dumps(events, ensure_ascii=False) and text not in caplog.text


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("reason", [
    pytest.param(f'{REASON} [see Item 7](https://www.sec.gov/x "{INV}").', id="link-title"),
    pytest.param(f'{REASON}; the filing only says !["{INV}"](x).', id="image"),
    pytest.param(f'{REASON}; the filing only says "Invented text&#34; &#34;missing from the source".',
                 id="character-references"),
    pytest.param(f'```"{INV}"\n{REASON}.\n```', id="fence"),
])
async def test_not_disclosed_reason_is_read_as_plain_text(monkeypatch, caplog, reason):
    """The reason is displayed as plain text, so its markdown syntax shows: these quote invented text."""
    monkeypatch.setattr(copilot_service.openai_service, "stream_chat_with_tools",
                        _stream_of(_reply("not_disclosed", ["What changed?", "What are the risks?"], reason)))
    with caplog.at_level(logging.WARNING, logger=copilot_service.logger.name):
        events = [e async for e in copilot_service.answer_filing_question(filing=_filing(ND_SOURCE), question="q")]
    _assert_withheld(events, caplog, "Invented text", REASON)


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["answer", "not_disclosed"])
async def test_a_failing_follow_up_chip_withholds_the_whole_response(monkeypatch, caplog, path):
    monkeypatch.setattr(copilot_service.openai_service, "stream_chat_with_tools", _stream_of(_reply(path, WITHHELD_CHIPS)))
    with caplog.at_level(logging.WARNING, logger=copilot_service.logger.name):
        events = [e async for e in copilot_service.answer_filing_question(filing=_filing(ND_SOURCE), question="q")]
    _assert_withheld(events, caplog, "Invented text", "What are the risks?", "Net income for 2025", REASON)


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["answer", "not_disclosed"])
@pytest.mark.parametrize("chips", [
    pytest.param([f'What does "{NI}" cover?', "What are the risks?"], id="chip-quoting-the-filing"),
    pytest.param(['Why is "ROE" not reported?', "What are the risks?", "How did margins move?"], id="short-term-chips"),
])
async def test_supported_follow_up_chips_publish_unchanged(monkeypatch, path, chips):
    monkeypatch.setattr(copilot_service.openai_service, "stream_chat_with_tools", _stream_of(_reply(path, chips)))
    source = f"{ND_SOURCE} {NI}."
    events = [e async for e in copilot_service.answer_filing_question(filing=_filing(source), question="q")]
    assert events[-1]["type"] == "complete" and events[-1]["kind"] == path
    assert events[-1]["followups"] == chips


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["answer", "not_disclosed"])
async def test_the_check_runs_off_the_event_loop(monkeypatch, path):
    """Markdown parsing is CPU work: it runs in a worker thread, not on the event loop."""
    seen = []
    check = copilot_service._withhold_unsupported_quotations
    monkeypatch.setattr(copilot_service, "_withhold_unsupported_quotations",
                        lambda *args: seen.append(threading.get_ident()) or check(*args))
    monkeypatch.setattr(copilot_service.openai_service, "stream_chat_with_tools",
                        _stream_of(_reply(path, ["What changed?", "What are the risks?"])))
    events = [e async for e in copilot_service.answer_filing_question(filing=_filing(ND_SOURCE), question="q")]
    assert events[-1]["type"] == "complete"
    assert len(seen) == 1 and seen[0] != threading.get_ident()


@pytest.mark.unit
def test_markdown_parser_debug_logs_stay_quiet():
    """At a DEBUG root (development), markdown-it-py would log every block rule it tries."""
    from app.services.logging_service import configure_logging

    root = logging.getLogger()
    names = ("httpx", "httpcore", "urllib3", "edgar", "markdown_it")
    levels, handlers = {name: logging.getLogger(name).level for name in names}, list(root.handlers)
    level = root.level
    try:
        configure_logging("DEBUG")
        assert not logging.getLogger("markdown_it").isEnabledFor(logging.DEBUG)
    finally:
        root.setLevel(level)
        root.handlers[:] = handlers
        for name, saved in levels.items():
            logging.getLogger(name).setLevel(saved)


@pytest.mark.unit
def test_long_bracketed_digits_inside_a_quotation_are_quoted_text():
    """Only plausible citation markers ([1], [F12]) are stripped from a quotation; this is text."""
    answer = 'The filing says "Net income for 2025 [12345678901234567890123456] amounted to €9,609.4 million" [1].'
    assert unsupported_prose_quotations(answer, SOURCE) == [NOT_IN]


@pytest.mark.unit
def test_a_bare_ampersand_is_not_a_quote_hint():
    """A long answer that cannot quote (R&D, S&P) is not withheld for its length."""
    assert unsupported_prose_quotations("R&D and S&P " + "x" * _MAX_QUOTED_ANSWER_CHARS, SOURCE) == []
    assert unsupported_prose_quotations("R&amp;D " + "x" * _MAX_QUOTED_ANSWER_CHARS, SOURCE) == []
    assert unsupported_prose_quotations("&quot;ROE&quot; " + "x" * _MAX_QUOTED_ANSWER_CHARS, SOURCE) == [AMBIGUOUS]


@pytest.mark.unit
@pytest.mark.parametrize("answer", [
    pytest.param(f'"{NI}" ' + "x" * _MAX_QUOTED_ANSWER_CHARS, id="past-the-character-bound"),
    pytest.param(f'"{NI}" ' + "[1]" * 257, id="past-the-bracket-bound"),
    pytest.param(f'"{NI}" \x1c', id="control-character"),
    pytest.param(f'"{NI}" ![chart](x)', id="image"),
    pytest.param(f'"{NI}" [^1]', id="footnote"),
    pytest.param(f'"{NI}" \t', id="tab"),
    pytest.param(f'"{NI}" ***x***', id="delimiter-run-of-stars"),
    pytest.param(f'"{NI}" ___x___', id="delimiter-run-of-underscores"),
    pytest.param(f'"{NI}" <br>', id="raw-html"),
])
def test_what_always_fails_closed_is_found_before_parsing(monkeypatch, answer):
    """Cheap source-text checks answer before the markdown parse, which bounds the slow shapes."""
    def parse(_answer):
        raise AssertionError("parsed")

    monkeypatch.setattr(copilot_service, "_rendered_text", parse)
    assert unsupported_prose_quotations(answer, SOURCE) == [AMBIGUOUS]


@pytest.mark.unit
def test_block_tokens_outside_the_allowlist_fail_closed(monkeypatch):
    """Every block token markdown-it emits here is read today; one outside the allowlist (here, a
    thematic break taken out of it) makes the answer fail closed rather than read it."""
    answer = f'The filing says "{NI}" [1].\n\n---\n\nThat is all.'
    assert copilot_service._rendered_text(answer) is not None
    monkeypatch.setattr(copilot_service, "_MARKDOWN_BLOCKS", copilot_service._MARKDOWN_BLOCKS - {"hr"})
    assert copilot_service._rendered_text(answer) is None


@pytest.mark.unit
def test_images_are_outside_the_read_subset():
    """The parser-level allowlist, behind the source-text check for image markup."""
    assert copilot_service._rendered_text("![chart](https://www.sec.gov/x.png) Net income rose.") is None
    assert copilot_service._rendered_text("Net income rose.") == "Net income rose.\n"


def _fresh_service_module():
    spec = importlib.util.spec_from_file_location("copilot_service_fresh", copilot_service.__file__)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
def test_parser_rules_are_compiled_at_import():
    """markdown-it compiles its rule chains lazily and not thread-safely; the module compiles them."""
    module = _fresh_service_module()
    for ruler in (module._MARKDOWN.core.ruler, module._MARKDOWN.block.ruler, module._MARKDOWN.inline.ruler,
                  module._MARKDOWN.inline.ruler2):
        assert ruler.__cache__ is not None


@pytest.mark.unit
def test_first_parses_in_concurrent_threads_agree(monkeypatch):
    """Fresh parsers raced by eight threads at a tiny switch interval read as one thread does. Before
    the rules were compiled up front, about 3% of first parses ran with missing rules."""
    answer = "The filing calls it &ldquo;Invented text missing from the source&rdquo; [1]."
    expected = copilot_service._rendered_text(answer)
    interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        results = []
        for _ in range(60):
            monkeypatch.setattr(copilot_service, "_MARKDOWN", copilot_service._markdown_parser())
            barrier = threading.Barrier(8)

            def parse():
                barrier.wait()
                results.append(copilot_service._rendered_text(answer))

            threads = [threading.Thread(target=parse) for _ in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
    finally:
        sys.setswitchinterval(interval)
    assert results == [expected] * len(results) and len(results) == 480


CROSSING = ("Within the results of operations discussion for fiscal 2025, why does the filing describe it as "
            f'"{NI}"?')
PAST_THE_TRIM = "x" * 141 + f' "{INV}"?'


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["answer", "not_disclosed"])
@pytest.mark.parametrize("chip,published", [
    pytest.param(CROSSING, False, id="closing-mark-cut-by-the-trim"),
    pytest.param(PAST_THE_TRIM, True, id="invented-quote-past-the-trim"),
])
async def test_chips_are_checked_as_published_after_the_trim(monkeypatch, caplog, path, chip, published):
    """A chip is published cut to 140 characters, and is checked as cut."""
    assert len(CROSSING) == 186 and CROSSING.rfind('"') == 184
    monkeypatch.setattr(copilot_service.openai_service, "stream_chat_with_tools",
                        _stream_of(_reply(path, [chip, "What are the risks?"])))
    with caplog.at_level(logging.WARNING, logger=copilot_service.logger.name):
        events = [e async for e in copilot_service.answer_filing_question(filing=_filing(ND_SOURCE), question="q")]
    if published:
        assert events[-1]["type"] == "complete" and events[-1]["followups"][0] == chip[:140]
    else:
        assert events[-1] == {"type": "error", "message": copilot_service._PUBLICATION_ERROR}
        assert "Unsupported prose quotation: unbalanced_quotation" in caplog.text


@pytest.mark.unit
@pytest.mark.asyncio
async def test_the_answer_is_read_as_markdown_through_the_service(monkeypatch, caplog):
    """References show their marks only as markdown: the plain-text reading would see no quotation."""
    answer = f"The filing calls it &ldquo;{INV}&rdquo; [1]."
    monkeypatch.setattr(copilot_service.openai_service, "stream_chat_with_tools",
                        _stream_of(f"{answer}\n===CITATIONS===\n{ND_CITATIONS}"))
    with caplog.at_level(logging.WARNING, logger=copilot_service.logger.name):
        events = [e async for e in copilot_service.answer_filing_question(filing=_filing(ND_SOURCE), question="q")]
    _assert_withheld(events, caplog, "Invented text")


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["answer", "reason", "chip"])
async def test_bidi_reordered_quotation_is_withheld_on_every_surface(monkeypatch, caplog, surface):
    if surface == "answer":
        reply = f'The filing says "{BIDI} [1].\n===CITATIONS===\n{ND_CITATIONS}'
    elif surface == "reason":
        reply = _reply("not_disclosed", ["What changed?", "What are the risks?"], f'{REASON}; the filing only says "{BIDI}.')
    else:
        reply = _reply("answer", [f'Why does the filing say "{BIDI}?', "What are the risks?"])
    monkeypatch.setattr(copilot_service.openai_service, "stream_chat_with_tools", _stream_of(reply))
    with caplog.at_level(logging.WARNING, logger=copilot_service.logger.name):
        events = [e async for e in copilot_service.answer_filing_question(filing=_filing(ND_SOURCE), question="q")]
    assert events[-1] == {"type": "error", "message": copilot_service._PUBLICATION_ERROR}
    assert all(event["type"] == "progress" for event in events[:-1])
    assert "Unsupported prose quotation: ambiguous_quotation" in caplog.text
    assert "Invented text" not in json.dumps(events, ensure_ascii=False) and "Invented text" not in caplog.text
