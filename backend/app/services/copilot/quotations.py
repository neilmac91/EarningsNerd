"""Copilot quotations extracted without changing admission behavior."""
from __future__ import annotations

import html
import re
import unicodedata
from typing import Optional

from markdown_it import MarkdownIt

from app.services.copilot.exceptions import _UnpublishableAnswer
from app.services.provenance_service import normalize_for_match

# Prose quotations (decision F). The marks are the double quotes normalize_for_match folds to '"'
# (straight, “ ” „) plus ‟ (U+201F) and the fullwidth ＂ (U+FF02). Single quotes are left alone
# (apostrophes), and so are ″ (U+2033, far more often an inch or seconds sign), 〝〞〟, ❝❞, 🙶🙷 and ʺ:
# decision F's scope is these double quotes, not every quotation form. This is the one definition of
# the set: the markdown pre-filter below and the section_ref rule (section_label_is_quoted) read it.
_STRAIGHT_QUOTE_MARKS = '"\uff02'
_CLOSING_QUOTE_MARK = "\u201d"
_QUOTE_MARK_RE = re.compile('["\uff02\u201c\u201d\u201e\u201f]')
_QUOTE_EDGE_CHARS = " \t\r\n\u00a0.,;:!?\u2026"
_QUOTE_ELLIPSIS_RE = re.compile(r"\.\s*\.\s*\.|\u2026")
# The shortest quoted text checked against the filing (the founder's decision on PR #1029): shorter
# quoted terms ("ROE", "EBITDA") are labels. Citation excerpts keep the verifier's own floor,
# provenance_service._MIN_VERIFIABLE_LEN (24).
_MIN_QUOTED_LEN = 8
# The work per answer is bounded: an answer that may quote and is longer than this, holds more
# quote marks than this, or whose quotations (nested ones counted again) span more characters than
# this, fails closed unchecked. Realistic answers run to 2-3k characters; the retained evaluation
# answers hold at most 8 marks in 330 characters.
_MAX_QUOTED_ANSWER_CHARS = 8_000
_MAX_QUOTE_MARKS = 64
_MAX_QUOTED_CHARS = 20_000
# Link-label parsing grows with the brackets ('[' runs reach about 100 ms at the character bound);
# an answer that may quote and opens more than this many fails closed. Realistic answers hold a few
# dozen citation markers at most.
_MAX_BRACKETS = 256
# A mark, or a character reference that may name one (a bare "&", as in R&D, is not one).
_QUOTE_HINT_RE = re.compile(
    _QUOTE_MARK_RE.pattern + "|&(?:#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6}|[A-Za-z][A-Za-z0-9]{1,31});")
# Characters that change what a reader sees without being plain visible text: C0 and C1 controls
# other than line breaks (a tab fails closed in the answer below), the Ogham space mark and the line
# and paragraph separators (a space or a break, by reader), the byte-order mark, and the bidi
# controls and right-to-left scripts (whose blocks hold the Arabic letter mark), around which the
# browser reorders marks and text. Text that may quote and holds one fails closed: it is not read,
# and it is not dropped (see _display_may_differ, which adds the astral and unassigned characters).
_FAIL_CLOSED_CHARS_RE = re.compile(
    "[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u1680\u2028\u2029\ufeff\u200e\u200f\u202a-\u202e\u2066-\u2069"
    "\u0590-\u08ff\ufb1d-\ufdff\ufe70-\ufefe]")
# Unicode Default_Ignorable_Code_Point (DerivedCoreProperties, Unicode 17.0; checked against ICU) in
# the Basic Multilingual Plane and assigned in Python's tables, less the bidi controls and U+FEFF:
# never displayed, so dropped before a mark's neighbours are read. The rest fail closed.
_DEFAULT_IGNORABLE_RE = re.compile(
    "[\u00ad\u034f\u115f\u1160\u17b4\u17b5\u180b-\u180f\u200b-\u200d\u2060-\u2064\u206a-\u206f\u3164"
    "\ufe00-\ufe0f\uffa0]")
# Citation markers inside a quotation are not quoted text; anything longer is read as written.
_QUOTED_MARKER_RE = re.compile(r"\[F?\d{1,3}\]")
# The answer is displayed by react-markdown 10 with remark-gfm (micromark). It is read here with
# markdown-it-py, and only within a small subset that both parsers are assumed to read alike:
# paragraphs, headings, thematic breaks, lists, blockquotes, GFM tables, emphasis, code spans, and
# code blocks. An answer that may quote and uses anything else fails closed: link syntax (inline
# links, reference definitions, autolinks) and the raw URL and email literals GFM links by itself,
# raw HTML, images, footnotes, task-list checkboxes, tabs, runs of three or more emphasis delimiters
# or two different delimiters side by side, Unicode spaces at a line's edge, nesting past
# _MAX_MARKDOWN_NESTING, and the forms below on which a fuzz against the display found the parsers
# to differ (lazy lines, stray table rows, some list openings). A URL or address built from
# character references or escapes (www&#46;sec.gov) is linked by the display too, but it shows the
# same text, so it is read as text. Within the subset some guards remain: a delimiter left as text
# may still vanish when displayed, so a mark's direction that one decides is ambiguous; a '*' or
# '_' left as text where there is emphasis, one delimiter run split between two emphasis tokens, a
# tilde beside emphasis, or a backtick left as text may change what the display pairs. That the two
# parsers agree on this subset is the residual assumption; it is not exact parity with the display.


def _markdown_parser() -> MarkdownIt:
    """The shared parser, its rules compiled. markdown-it compiles its rule chains on first use, and
    mdurl fills its encoding and decoding caches on first use, each publishing an empty cache before
    filling it, so a first parse in two worker threads at once could run without them. Link syntax
    never reaches the reading (it fails closed before parsing, so mdurl is not called on one); the
    autolink parsed here fills both mdurl caches, and the inline link is a harmless extra. After this
    one parse the instance is only read."""
    parser = MarkdownIt("commonmark", {"html": False}).enable("table")
    parser.parse("[x](y) <http://z>")
    return parser


_MARKDOWN = _markdown_parser()
# Block ends, and a thematic break, show as line breaks.
_MARKDOWN_BLOCK_ENDS = frozenset({
    "paragraph_close", "heading_close", "blockquote_close", "list_item_close", "bullet_list_close",
    "ordered_list_close", "thead_close", "tbody_close", "tr_close", "th_close", "td_close", "table_close", "hr",
})
_MARKDOWN_BLOCKS = _MARKDOWN_BLOCK_ENDS | {
    "paragraph_open", "heading_open", "blockquote_open", "list_item_open", "bullet_list_open",
    "ordered_list_open", "thead_open", "tbody_open", "tr_open", "th_open", "td_open", "table_open",
    "inline", "fence", "code_block",
}
_MARKDOWN_INLINE = frozenset({
    "text", "softbreak", "hardbreak", "em_open", "em_close", "strong_open", "strong_close", "code_inline",
})
_MARKDOWN_BREAKS = ("softbreak", "hardbreak")
_MARKDOWN_EMPHASIS = ("em_open", "em_close", "strong_open", "strong_close")
_MARKDOWN_CONTAINERS = {"blockquote_open": 1, "blockquote_close": -1, "bullet_list_open": 1,
                        "bullet_list_close": -1, "ordered_list_open": 1, "ordered_list_close": -1}
# Nested blockquotes and lists, together. This keeps every token far below markdown-it's maxNesting
# (20), past which it stops parsing; the display has no such cap.
_MAX_MARKDOWN_NESTING = 4
# Found in the source text before parsing, since each always fails closed: an image, footnote
# syntax, a tab (expanded differently in indentation and table rows), a run of three or more '*' or
# '_' (which the parsers pair differently), two different emphasis or strikethrough delimiters side
# by side (micromark lets a '*' or '_' run beside any other of '*', '_' and GFM's '~' open or close,
# where CommonMark and markdown-it read that neighbour as punctuation), and raw HTML of any kind
# (markdown-it's HTML parsing stays off; it also catches autolinks such as <https://...>).
_OUTSIDE_SUBSET_RE = re.compile(r"!\[|\[\^|\t|\*{3}|_{3}|\*[_~]|_[*~]|~[*_]")
_RAW_HTML_RE = re.compile(r"<[A-Za-z/!?]")
# Link syntax and raw URL and email literals, also found before parsing: an inline link or a
# reference definition (the only markdown here that reaches markdown-it's link normalization, so
# mdurl never runs on a reading), or a literal GFM links by itself: a URL, a www. address, or an
# email address ('@' between two characters, which also finds mailto: and xmpp: addresses and
# '<...@...>' autolinks; '<scheme:...>' autolinks are found as raw HTML). No answer in the retained
# evaluation runs holds one (0 of 576).
_LINK_RE = re.compile(r"\]\(|\]:|www\.|https?://|\S@\S", re.IGNORECASE)
# A Unicode space at a line's edge, also found before parsing (in the answer with its line endings
# normalized, as markdown-it normalizes them). These are the whitespace characters Python's
# str.strip() removes besides those that fail closed anyway (_display_may_differ) and the space,
# tab and line endings: U+00A0, U+2000-U+200A, U+202F, U+205F and U+3000. markdown-it strips them
# from a table row (rules_block/table.py), a paragraph (paragraph.py), a setext heading
# (lheading.py) and an ATX heading's content (heading.py), where micromark trims only spaces and
# tabs, so at a line's edge they can change the blocks the display shows (a table header the
# display does not take as one, a line the display breaks after a trailing backslash). Elsewhere in
# a line the only differences are whitespace at the edge of a table cell, a heading, or a paragraph
# that starts after a blockquote or list marker, and the padding of a code span that holds only
# whitespace; the reading and the shared normalization treat these alike.
_UNICODE_SPACES = "\u00a0\u2000-\u200a\u202f\u205f\u3000"
_LINE_EDGE_SPACE_RE = re.compile(f"(?m)^[ \t]*[{_UNICODE_SPACES}]|[{_UNICODE_SPACES}][ \t]*$")
# A GFM task-list checkbox, which the display draws as a box instead of this text.
_TASK_CHECKBOX_RE = re.compile(r"\[[ \txX]\]")
# Blockquotes and GFM tables are read only outside any container and with every line starting with
# their marker (no lazy continuation lines). Any other line that GFM might take for a table's
# delimiter row (pipes and dashes, perhaps behind container markers) is outside the subset.
_TOP_LEVEL_BLOCKS = {"blockquote_open": re.compile(r" {0,3}>"), "table_open": re.compile(r" {0,3}\|")}
_TABLE_DELIMITER_LIKE_RE = re.compile(r"[ \t>+*0-9.):-]*\|[ \t>+*0-9.):|-]*")
_MAYBE_HIDDEN = "*_~"


def _rendered_text(answer: str) -> Optional[str]:
    """The answer's text as the reader sees it, or None when it uses markdown outside the subset.

    Character references and escapes show their characters, block ends show as line breaks, and code
    is shown verbatim. Used only to decide; never published.
    """
    env: dict = {}
    tokens = _MARKDOWN.parse(answer, env)
    if env.get("references"):
        return None
    lines = re.split(r"\r\n?|\n", answer)
    delimiter_rows = {at for at, line in enumerate(lines) if "-" in line and _TABLE_DELIMITER_LIKE_RE.fullmatch(line)}
    parts: list[str] = []
    depth = 0
    for index, token in enumerate(tokens):
        outer = depth
        depth += _MARKDOWN_CONTAINERS.get(token.type, 0)
        if token.type not in _MARKDOWN_BLOCKS or depth > _MAX_MARKDOWN_NESTING:
            return None
        start, end = token.map or (0, 0)
        if token.type in _TOP_LEVEL_BLOCKS:
            if outer or not all(_TOP_LEVEL_BLOCKS[token.type].match(line) for line in lines[start:end]):
                return None
            if token.type == "table_open":
                delimiter_rows.discard(start + 1)
        if token.type == "code_block" and start and lines[start - 1].strip(" "):
            return None  # indented code right after text, where GFM continues the text instead
        if token.type == "list_item_open" and (tokens[index + 1].type == "list_item_close"
                                               or (tokens[index + 1].map or (start,))[0] > start):
            return None  # an item opening on a blank line, which the display may show as its marker
        number = token.attrGet("start")
        if token.type == "ordered_list_open" and number not in (None, 1) and (
                (index and tokens[index - 1].type == "code_block") or not re.match(f" *0*{number}[.)]", lines[start])):
            return None  # numbered past 1 after a code block or another marker: GFM may show it as text
        if token.type == "inline":
            inline = _rendered_inline(token.children or [])
            if inline is None or _TASK_CHECKBOX_RE.match(token.content):
                return None
            parts.append(inline)
        elif token.type in ("fence", "code_block"):
            parts.append(token.content)
        elif token.type in _MARKDOWN_BLOCK_ENDS:
            parts.append("\n")
    text = "".join(parts)
    # Character references can name what the source text may not hold.
    return None if delimiter_rows or _display_may_differ(text) else text


def _rendered_inline(children: list) -> Optional[str]:
    parts: list[str] = []
    emphasis = any(child.type in _MARKDOWN_EMPHASIS for child in children)
    for index, child in enumerate(children):
        if child.type not in _MARKDOWN_INLINE:
            return None
        if (index and child.type in _MARKDOWN_EMPHASIS and children[index - 1].type in _MARKDOWN_EMPHASIS
                and child.markup[0] == children[index - 1].markup[0]):
            return None  # one delimiter run split between two emphasis tokens: GFM may pair it otherwise
        if child.type in _MARKDOWN_BREAKS:
            parts.append("\n")
        elif child.type == "code_inline":
            parts.append(child.content)
        else:
            text = child.content
            before = children[index - 1].type if index else "softbreak"
            after = children[index + 1].type if index + 1 < len(children) else "softbreak"
            if "`" in text:
                return None  # a backtick left as text may open a code span when displayed
            if text and ((text[0] == "~" and before in _MARKDOWN_EMPHASIS)
                         or (text[-1] == "~" and after in _MARKDOWN_EMPHASIS)):
                return None  # a tilde beside emphasis: GFM may pair the runs otherwise
            if emphasis and _may_delimit(text):
                return None  # a '*' or '_' left as text where there is emphasis: GFM may pair them otherwise
            parts.append(text)
    return "".join(parts)


def _display_may_differ(text: str) -> bool:
    """Whether ``text`` holds a character the display may show differently from this reading: one
    in _FAIL_CLOSED_CHARS_RE, an astral character (micromark classifies those by UTF-16 unit), or
    one unassigned in Python's Unicode tables (the browser's tables may assign it)."""
    return bool(_FAIL_CLOSED_CHARS_RE.search(text)) or any(
        char > "\uffff" or unicodedata.category(char) == "Cn" for char in text if char > "\x7f")


def _may_delimit(text: str) -> bool:
    """Whether a '*' or '_' left as text could open or close emphasis: not one between spaces, nor an
    underscore inside a word."""
    for at, char in enumerate(text):
        if char in "*_":
            before, after = text[at - 1:at], text[at + 1:at + 2]
            if not (before.isspace() and after.isspace()) and not (
                    char == "_" and before.isalnum() and after.isalnum()):
                return True
    return False


def _is_punctuation(char: str) -> bool:
    return unicodedata.category(char)[0] in "PS"


def _beside(text: str, at: int, step: int, maybe_hidden: str) -> set[str]:
    """What a reader may see just before (step -1) or after (step 1) the mark at ``at``.

    Combining marks draw on a neighbour, so they are passed over; text edges read as whitespace. A
    delimiter in ``maybe_hidden`` may still vanish when displayed, so beside one the character beyond
    it is possible too.
    """
    seen: set[str] = set()
    index = at + step
    while True:
        while 0 <= index < len(text) and unicodedata.category(text[index]) in ("Mn", "Me"):
            index += step
        char = text[index] if 0 <= index < len(text) else " "
        seen.add(char)
        if char not in maybe_hidden:
            return seen
        index += step


def _straight_reading(marks: list[tuple[int, str]]) -> tuple[int, list[tuple[int, int]]]:
    """How many balanced readings one stretch of straight marks admits (0, 1, or 2 for two or more),
    and the pairs of the reading when there is exactly one.

    ``layers[k]`` maps each depth reachable after ``k`` marks to the number of readings reaching it,
    capped at 2, so the work is marks times depths rather than the number of readings.
    """
    layers: list[dict[int, int]] = [{0: 1}]
    for _, role in marks:
        layer: dict[int, int] = {}
        for depth, count in layers[-1].items():
            if role != "close":
                layer[depth + 1] = min(2, layer.get(depth + 1, 0) + count)
            if role != "open" and depth:
                layer[depth - 1] = min(2, layer.get(depth - 1, 0) + count)
        layers.append(layer)
    count = layers[-1].get(0, 0)
    if count != 1:
        return count, []
    # Walk the one reading back from its end: each step on it has exactly one predecessor.
    closings: list[bool] = []
    depth = 0
    for index in range(len(marks), 0, -1):
        closing = marks[index - 1][1] != "open" and depth + 1 in layers[index - 1]
        closings.append(closing)
        depth += 1 if closing else -1
    opened: list[int] = []
    pairs: list[tuple[int, int]] = []
    for (at, _), closing in zip(marks, reversed(closings)):
        if closing:
            pairs.append((opened.pop(), at))
        else:
            opened.append(at)
    return 1, pairs


def _quotation_reading(text: str, maybe_hidden: str) -> list[tuple[int, int]] | str:
    """(opening, closing) mark offsets of the one reading the marks admit.

    “ „ ‟ open and ” closes; a straight mark takes its direction from its neighbours, as CommonMark
    reads emphasis. A mark can open when the next character is not whitespace and is not
    punctuation (Unicode P or S) unless whitespace or punctuation precedes the mark; closing
    mirrors this. A straight mark that can do both or neither may do either. Curly marks pair
    with curly marks by glyph; straight marks pair only with straight marks of the same stretch
    between curly marks. So '"x "y" z"' and '"x ("y") z"' read only as nested quotations, and
    every span is checked. Every balanced reading is counted (``_straight_reading``). Returns a
    reason code instead when a curly mark faces the wrong way, when a mark's direction depends on
    whether a delimiter shows, when no balanced reading exists, when more than one does, or when
    there are more than ``_MAX_QUOTE_MARKS`` marks.
    """
    found = list(_QUOTE_MARK_RE.finditer(text))
    if len(found) > _MAX_QUOTE_MARKS:
        return "ambiguous_quotation"
    curly_open: list[int] = []
    stretches: dict[int, list[tuple[int, str]]] = {-1: []}
    pairs: list[tuple[int, int]] = []
    for match in found:
        at, glyph = match.start(), match.group()
        roles: set[str | bool] = set()
        for before in _beside(text, at, -1, maybe_hidden):
            for after in _beside(text, at, 1, maybe_hidden):
                opens = not after.isspace() and (
                    not _is_punctuation(after) or before.isspace() or _is_punctuation(before))
                closes = not before.isspace() and (
                    not _is_punctuation(before) or after.isspace() or _is_punctuation(after))
                if glyph in _STRAIGHT_QUOTE_MARKS:
                    roles.add("either" if opens == closes else "open" if opens else "close")
                else:
                    roles.add(closes if glyph == _CLOSING_QUOTE_MARK else opens)
        if len(roles) > 1 or False in roles:
            return "ambiguous_quotation"
        if glyph in _STRAIGHT_QUOTE_MARKS:
            stretches[curly_open[-1] if curly_open else -1].append((at, roles.pop()))
        elif glyph != _CLOSING_QUOTE_MARK:
            curly_open.append(at)
            stretches[at] = []
        elif curly_open:
            pairs.append((curly_open.pop(), at))
        else:
            return "unbalanced_quotation"
    if curly_open:
        return "unbalanced_quotation"
    counts: list[int] = []
    for marks in stretches.values():
        count, stretch_pairs = _straight_reading(marks)
        counts.append(count)
        pairs += stretch_pairs
    if 0 in counts:
        return "unbalanced_quotation"
    return "ambiguous_quotation" if max(counts) > 1 else sorted(pairs)


def unsupported_prose_quotations(answer: str, normalized_source: str) -> list[str]:
    """Reason codes for double-quoted spans of a markdown answer the filing text cannot show contiguously.

    Only double quotation marks are in scope; single quotes, guillemets, other marks and markdown
    blockquotes are not checked. The answer is read as displayed (``_rendered_text``), for this
    decision only; the published answer is never rewritten. A quotation is in scope when it holds
    at least ``_MIN_QUOTED_LEN`` characters after the shared normalization (the one place this
    floor is read) or an interior ellipsis; shorter quoted terms ("ROE", "EBITDA") are labels, not
    source quotations. An in-scope quotation must occur
    contiguously in ``normalized_source``; citation markers and edge punctuation are not quoted
    text. A nested quotation is checked both whole and inner, and reasons follow the opening
    marks, so an outer quotation's reason precedes its inner one's. Missing source text, marks
    that admit no reading or more than one, markdown outside the read subset, characters the
    display may show otherwise (``_display_may_differ``), and answers past the work bounds fail
    closed. Nothing is repaired or stitched: any reason withholds the whole answer.
    """
    if not _QUOTE_HINT_RE.search(answer):
        return []
    text = None
    if not (len(answer) > _MAX_QUOTED_ANSWER_CHARS or answer.count("[") > _MAX_BRACKETS
            or _display_may_differ(answer) or _OUTSIDE_SUBSET_RE.search(answer) or _LINK_RE.search(answer)
            or _RAW_HTML_RE.search(answer) or _LINE_EDGE_SPACE_RE.search(re.sub(r"\r\n?", "\n", answer))):
        text = _rendered_text(answer)
    if text is None:
        return ["ambiguous_quotation"] if _QUOTE_MARK_RE.search(html.unescape(answer)) else []
    return _displayed_quotation_reasons(_DEFAULT_IGNORABLE_RE.sub("", text), normalized_source, _MAYBE_HIDDEN)


def unsupported_plain_quotations(text: str, normalized_source: str) -> list[str]:
    """``unsupported_prose_quotations`` for prose displayed as plain text, with no markdown: the
    not-disclosed reason and the follow-up questions."""
    if not _QUOTE_MARK_RE.search(text):
        return []
    if len(text) > _MAX_QUOTED_ANSWER_CHARS or _display_may_differ(text):
        return ["ambiguous_quotation"]
    return _displayed_quotation_reasons(_DEFAULT_IGNORABLE_RE.sub("", text), normalized_source, "")


def _displayed_quotation_reasons(text: str, normalized_source: str, maybe_hidden: str) -> list[str]:
    """The reason codes for ``text`` as displayed, where ``maybe_hidden`` delimiters may yet vanish."""
    reading = _quotation_reading(text, maybe_hidden)
    if isinstance(reading, str):
        return [reading]
    if sum(end - start for start, end in reading) > _MAX_QUOTED_CHARS:
        return ["ambiguous_quotation"]
    reasons: list[str] = []
    for start, end in reading:
        raw = text[start + 1:end]
        content = _QUOTED_MARKER_RE.sub(" ", raw).strip(_QUOTE_EDGE_CHARS)
        needle = normalize_for_match(content)
        elided = bool(_QUOTE_ELLIPSIS_RE.search(content))
        if not elided and len(needle) < _MIN_QUOTED_LEN:
            continue
        if not normalized_source:
            reasons.append("quotation_source_unavailable")
        elif (needle not in normalized_source
              and normalize_for_match(raw.strip(_QUOTE_EDGE_CHARS)) not in normalized_source):
            # Literal second: a filing can print "Note [7]".
            reasons.append("elided_quotation" if elided else "quotation_not_in_source")
    return reasons


def _withhold_unsupported_quotations(normalized_source: str, markdown: str, plain: list[str]) -> None:
    """Raise when published prose quotes text the filing cannot show; the log gets only the code.

    ``markdown`` is displayed as markdown (the answer), ``plain`` as plain text (the not-disclosed
    reason, the follow-up questions). Any failure withholds the whole response.
    """
    failures = unsupported_prose_quotations(markdown, normalized_source) if markdown else []
    for text in plain:
        failures = failures or unsupported_plain_quotations(text, normalized_source)
    if failures:
        raise _UnpublishableAnswer(f"Unsupported prose quotation: {failures[0]}")
