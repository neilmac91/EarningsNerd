"""Gate: the mail's header and footer line are the brand template's, and the page around them holds.

``docs/brand/templates/email-header.html`` is the editable preview of the header (the lockup, a
hairline, the marked tagline) and the footer line, and ``email_service._wrap_html`` carries its
markup, ported (CLAUDE.md rule 12: a change to one is a change to the other). The two are compared
tag for tag and text for text, plain comments aside, with whitespace counted as a browser renders it:
- in text, a run of spaces, tabs and line breaks is one space, and a form feed, a no-break or an em
  space renders as itself;
- whitespace beside a table's own tags renders nothing, a form feed included, and is dropped;
- in a tag, the whitespace between attributes is one space, and a quoted value is compared as written,
  so a value reflowed in one file is reflowed in the other.

One difference is allowed: the preview's tile is inline SVG in a cell Outlook skips, and the mail's is
the hosted raster the template's note spells (``<img src="{base}/assets/earningsnerd-appicon.png" ...>``),
on ``FRONTEND_URL``. The page carries the header and the footer line once each, the header above the
panel and the footer line below it. Around them, the page:

- puts the body and the footer in the panel's cells, each once and each in a cell of its own, and
  carries one wordmark, the name split by markup into its two styles: the header's;
- carries no inline SVG, which Gmail and Outlook drop, and sets no viewport: it is 600 px wide, and a
  mail view fits a page that sets none to its screen;
- keeps the header at its set size where a phone view enlarges text (``-webkit-text-size-adjust:100%``
  on its table), and leaves every other line to the view, the panel's and the footer line's. Each line
  is read as a client inherits the property: both its names, the last declaration winning, entities
  decoded. The page carries no ``<style>`` block, whose selectors this test does not read.
  ``test_mail_rendered_addresses.py`` holds every page the mail module sends to the same rule;
- lets the panel break a long word, such as a link's token, so its enlarged text cannot widen it past
  the header;
- pads no table through its ``style`` attribute (the shell has no ``<style>`` block), since classic
  Outlook ignores a table's padding and the body would sit against the panel's border, out of line with
  the header.
"""
import html
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from app.config import settings
from app.services import email_service

TEMPLATE = Path(__file__).resolve().parents[3] / "docs" / "brand" / "templates" / "email-header.html"
_PLAIN_COMMENT = re.compile(r"<!--\s(?:(?!-->).)*-->", re.DOTALL)  # an Outlook conditional has no space after <!--
_TILE_IN_NOTE = re.compile(r'<img src="\{base\}[^>]*>', re.DOTALL)
_TABLE_TAG = re.compile(r"</?(?:table|tbody|tr|td)\b")
# Text collapses spaces, tabs and line breaks alone: a form feed, a no-break or an em space renders as
# itself. Between a tag's attributes, a form feed separates too.
_SPACE = " \t\n\r"
_SPACES = re.compile(f"[{_SPACE}]+")
_TAG_SPACES = re.compile(f"[{_SPACE}\f]+")
_QUOTED = re.compile(r"""("[^"]*"|'[^']*')""")
# A wordmark is the name split by markup into its two styles, read as a client shows it: its entities
# decoded and the characters that render as nothing (a soft hyphen, a zero-width space) dropped.
_WORDMARK = re.compile(r"Earnings\s*(?:<[^>]+>\s*)+Nerd", re.IGNORECASE)
_INVISIBLE = re.compile("[\u00ad\u200b-\u200d\u2060\ufeff]")
_VIEWPORT = re.compile(r"""<meta\b[^>]*\bname\s*=\s*["']?viewport\b""", re.IGNORECASE)
_TABLE_PADDING = re.compile(r"""\bstyle\s*=\s*(?:(["'])(?:(?!\1).)*padding|[^\s"'>]*padding)""", re.IGNORECASE | re.DOTALL)


def _tag(piece: str) -> str:
    """A tag with the whitespace between its attributes made one space, its quoted values kept as written."""
    return "".join(part if _QUOTED.fullmatch(part) else _TAG_SPACES.sub(" ", part) for part in _QUOTED.split(piece))


# One property under two names: Blink reads both, and Apple's WebKit, which iOS Mail runs, the prefixed one.
_TEXT_SIZE_NAMES = ("-webkit-text-size-adjust", "text-size-adjust")
_VOID = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"})


def _declared_text_size(style: str) -> tuple[str, bool] | None:
    """The text-size-adjust a style attribute declares last, by either name, and whether a prefixed
    declaration of that value is among its declarations; None when it declares none."""
    found = []
    for declaration in style.split(";"):
        name, colon, value = declaration.partition(":")
        if colon and name.strip().lower() in _TEXT_SIZE_NAMES:
            found.append((name.strip().lower(), value.strip().lower().removesuffix("!important").strip()))
    if not found:
        return None
    value = found[-1][1]
    return value, any(name == _TEXT_SIZE_NAMES[0] and v == value for name, v in found)


class _TextSizes(HTMLParser):
    """Each line of text in a page, whether it sits in the header, and the text-size-adjust it inherits.
    The header is the 600 px table on the page's cream, whatever its style says."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, tuple[str, bool] | None, bool]] = []
        self.lines: list[tuple[str, bool, str, bool]] = []  # (text, in the header, value, prefixed)
        self.styles = 0

    def handle_starttag(self, tag, attrs):
        if tag == "style":
            self.styles += 1
        if tag not in _VOID:
            values = dict(attrs)
            header = tag == "table" and values.get("width") == "600" and (values.get("bgcolor") or "").upper() == "#F4F3EE"
            self.stack.append((tag, _declared_text_size(values.get("style") or ""), header))

    def handle_startendtag(self, tag, attrs):
        if tag == "style":
            self.styles += 1

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if data.strip() and self.lasttag != "style":
            value, prefixed = next((d for _, d, _ in reversed(self.stack) if d is not None), ("auto", False))
            self.lines.append((" ".join(data.split())[:40], any(h for _, _, h in self.stack), value, prefixed))


def text_size_problems(page: str) -> list[str]:
    """Where a page breaks the shell's text-size rule: the header keeps its set size on a phone that
    enlarges text, and every other line is left to the view."""
    parser = _TextSizes()
    parser.feed(page)
    parser.close()
    problems = []
    if parser.styles:
        problems.append("the page carries a <style> block, whose selectors this check does not read: set text-size-adjust inline")
    if not any(in_header for _, in_header, _, _ in parser.lines):
        problems.append("no line of the header was found: the check no longer finds the header's table")
    for text, in_header, value, prefixed in parser.lines:
        if in_header and value != "100%":
            problems.append(f"the header's {text!r} is left to the view ({value}): enlarged, the tagline outgrows the wordmark")
        elif in_header and not prefixed:
            problems.append(f"the header's {text!r} is held by the unprefixed name alone, which iOS does not read: use -webkit-text-size-adjust")
        elif not in_header and value != "auto":
            problems.append(f"{text!r} is held at {value}: leave the text outside the header to the view, which enlarges a long body on a phone")
    return problems


def _tokens(markup: str) -> list[str]:
    """The markup's tags and text, plain comments dropped, spaced as a browser renders them."""
    pieces = [piece for piece in re.split(r"(<[^>]+>)", _PLAIN_COMMENT.sub("", markup)) if piece]
    tokens = []
    for i, piece in enumerate(pieces):
        before, after = pieces[i - 1 : i], pieces[i + 1 : i + 2]
        if piece.startswith("<"):
            tokens.append(_tag(piece))
            continue
        # Beside a table's own tags, whitespace renders nothing, a form feed included: there the parser
        # reads it as whitespace too.
        after_table, before_table = bool(before and _TABLE_TAG.match(before[0])), bool(after and _TABLE_TAG.match(after[0]))
        text = piece.lstrip(_SPACE + "\f") if after_table else piece
        text = text.rstrip(_SPACE + "\f") if before_table else text
        if text.strip(_SPACE):
            tokens.append(_SPACES.sub(" ", text))
        elif text and not (after_table or before_table):
            tokens.append(" ")
    return tokens


def _table(tokens: list[str], opening: str) -> list[str]:
    """The table that opens with ``opening``, through its own closing tag."""
    assert opening in tokens, f"no table opens with {opening}"
    start, depth = tokens.index(opening), 0
    for i in range(start, len(tokens)):
        if tokens[i].startswith("<table"):
            depth += 1
        elif tokens[i] == "</table>":
            depth -= 1
            if depth == 0:
                return tokens[start : i + 1]
    raise AssertionError(f"the table that opens with {opening} never closes")


def _template_tables() -> tuple[list[str], list[str], str]:
    """The template's header and footer-line tables, and the tile its note spells."""
    source = TEMPLATE.read_text(encoding="utf-8")
    tokens = _tokens(source)
    openings = [t for t in tokens if t.startswith('<table role="presentation" width="600"')]
    assert len(openings) == 2, f"the template no longer holds a 600 px header and footer line: {openings}"
    note_tile = _TILE_IN_NOTE.search(source)
    assert note_tile, "the template's note no longer spells the mail's tile"
    return _table(tokens, openings[0]), _table(tokens, openings[1]), " ".join(note_tile.group(0).split())


def test_the_header_and_footer_line_are_the_templates(monkeypatch):
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://frontend.example.test")
    header, footer_line, note_tile = _template_tables()
    open_cell = header.index("<!--[if !mso]>")
    assert header[open_cell + 1] == "<!-->", "the template's tile cell is no longer the one Outlook skips"
    close_cell = header.index("<!--<![endif]-->", open_cell)
    cell = header[open_cell + 2]
    assert cell.startswith("<td") and "<svg" in "".join(header[open_cell:close_cell]), "the template's tile is no longer an SVG in a cell"
    tile = note_tile.replace("{base}", "https://frontend.example.test")
    expected_header = header[:open_cell] + [cell, tile, "</td>"] + header[close_cell + 1 :]

    page = _tokens(email_service._wrap_html("<p>Body</p>"))
    assert _table(page, header[0]) == expected_header, (
        "the mail's header is no longer the template's (docs/brand/templates/email-header.html): change both"
    )
    assert _table(page, footer_line[0]) == footer_line, (
        "the mail's footer line is no longer the template's (docs/brand/templates/email-header.html): change both"
    )
    panel = next(t for t in page if t.startswith("<table") and "border:1px solid #E5E1D8" in t)
    assert page.count(header[0]) == 1 and page.count(footer_line[0]) == 1, "the page carries the header and the footer line once each"
    assert page.index(header[0]) < page.index(panel) < page.index(footer_line[0]), (
        "the header sits above the panel, and the footer line below it"
    )


def test_the_page_holds_its_slots_and_its_shell_rules():
    body = "<p>Hi Tom &amp; Jerry,</p><p>We received a request to reset your password.</p>"
    footer = "<span>The footer slot.</span>"
    page = email_service._wrap_html(body, footer=footer)

    tokens = _tokens(page)
    panel = _table(tokens, next(t for t in tokens if t.startswith("<table") and "border:1px solid #E5E1D8" in t))
    assert page.count(body) == 1 and body in "".join(panel), "the body sits once, in the panel"
    assert page.count(footer) == 1 and footer in "".join(panel), "the footer sits once, in the panel"
    assert "</td>" in page[page.index(body) : page.index(footer)], "the footer has a cell of its own, after the body's"
    shell = page.replace(body, "").replace(footer, "")
    wordmarks = _WORDMARK.findall(_INVISIBLE.sub("", html.unescape(shell)))
    assert len(wordmarks) == 1, "the page carries one wordmark, the header's: the name in prose is no wordmark"

    assert "overflow-wrap:anywhere" in panel[0] and "word-break:break-word" in panel[0], (
        "the panel breaks a long word, such as a link's token, or a view that enlarges its text widens it past the header"
    )
    problems = text_size_problems(page)
    assert not problems, "\n".join(problems)
    assert "<svg" not in page.lower(), "Gmail and Outlook drop inline SVG"
    assert not _VIEWPORT.search(page), "a 600 px page sets no viewport, so a mail view fits it to its screen"
    padded = [t for t in tokens if t.lower().startswith("<table") and _TABLE_PADDING.search(t)]
    assert not padded, f"classic Outlook ignores a table's padding: pad its cells instead: {padded}"


_PLANTED_BODY = "<p>Hi Ada,</p><p>Copy this link: https://www.earningsnerd.io/reset-password?token=abc</p>"
_HELD = "-webkit-text-size-adjust:100%;"
_HEADER_STYLE = 'style="width:600px;max-width:600px;background-color:#F4F3EE;-webkit-text-size-adjust:100%;"'
# Each way a page can break the text-size rule, as an edit of the shell's page, and the look-alikes that hold it.
TEXT_SIZES = [
    # Flagged.
    ("the property back on the body", ('<body style="', f'<body style="{_HELD}'), "outside the header"),
    ("the property on the html element", ('<html lang="en">', f'<html lang="en" style="{_HELD}">'), "outside the header"),
    ("the property on the outer table", ('bgcolor="#F4F3EE" style="background-color:#F4F3EE;">', f'bgcolor="#F4F3EE" style="background-color:#F4F3EE;{_HELD}">'), "outside the header"),
    ("the property on the panel's wrapper cell", ('<td align="center" style="padding:0 12px 24px 12px;">', f'<td align="center" style="padding:0 12px 24px 12px;{_HELD}">'), "outside the header"),
    ("the property on the panel", ("border-radius:16px;", f"border-radius:16px;{_HELD}"), "outside the header"),
    ("none on the panel's body cell", ("border-radius:15px 15px 0 0;", "border-radius:15px 15px 0 0;-webkit-text-size-adjust:none;"), "outside the header"),
    ("the property on a mail's own line", ("<p>Copy this link", f'<p style="{_HELD}">Copy this link'), "outside the header"),
    ("the property's name spelled with an entity", ('<body style="', '<body style="-webkit-text-size-&#97;djust:100%;'), "outside the header"),
    ("a style block's reset", ("</head>", "<style>body,table,td{-webkit-text-size-adjust:100%}</style></head>"), "<style> block"),
    ("the header reopened by a later declaration", (_HEADER_STYLE, _HEADER_STYLE[:-1] + '-webkit-text-size-adjust:auto;"'), "the header's"),
    ("the header reopened by the unprefixed name", (_HEADER_STYLE, _HEADER_STYLE[:-1] + 'text-size-adjust:auto;"'), "the header's"),
    ("auto on the tagline's cell", ("padding:16px 32px 28px 32px;", "padding:16px 32px 28px 32px;-webkit-text-size-adjust:auto;"), "the header's"),
    ("the header held by the unprefixed name alone", (_HEADER_STYLE, _HEADER_STYLE.replace("-webkit-text-size-adjust", "text-size-adjust")), "unprefixed name alone"),
    ("the header's property dropped", (_HEADER_STYLE, _HEADER_STYLE.replace(_HELD, "")), "the header's"),
    ("the header's table no longer found", ('width="600" cellpadding="0" cellspacing="0" border="0" bgcolor="#F4F3EE"', 'width="640" cellpadding="0" cellspacing="0" border="0" bgcolor="#F4F3EE"'), "no line of the header"),
    # Pass.
    ("a space after the colon", (_HEADER_STYLE, _HEADER_STYLE.replace("adjust:100%", "adjust: 100%")), None),
    ("the property's name in capitals", (_HEADER_STYLE, _HEADER_STYLE.replace("-webkit-text-size-adjust", "-WEBKIT-TEXT-SIZE-ADJUST")), None),
    ("the header's value marked important", (_HEADER_STYLE, _HEADER_STYLE.replace("adjust:100%;", "adjust:100% !important;")), None),
    ("the unprefixed name beside the prefixed one", (_HEADER_STYLE, _HEADER_STYLE[:-1] + 'text-size-adjust:100%;"'), None),
    ("auto on the body", ('<body style="', '<body style="-webkit-text-size-adjust:auto;'), None),
    ("auto on the panel", ("border-radius:16px;", "border-radius:16px;-webkit-text-size-adjust:auto;"), None),
    ("the -ms- name on the body, which the engines that enlarge text ignore", ('<body style="', '<body style="-ms-text-size-adjust:100%;'), None),
]


@pytest.mark.parametrize("edit, expected", [case[1:] for case in TEXT_SIZES], ids=[case[0] for case in TEXT_SIZES])
def test_the_text_size_check_scores_every_planted_page(edit, expected):
    page = email_service._wrap_html(_PLANTED_BODY, footer="<span>The footer.</span>")
    old, new = edit
    assert page.count(old) == 1, f"the planted edit no longer finds {old!r} once in the page"
    problems = text_size_problems(page.replace(old, new))
    if expected is None:
        assert not problems, problems
    else:
        assert any(expected in problem for problem in problems), f"expected {expected!r}, got {problems}"
