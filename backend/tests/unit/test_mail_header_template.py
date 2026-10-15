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
  on its table), and leaves every other line to the view, the panel's and the footer line's;
- breaks no run of a body's for it: a line that prints a run with nowhere to break, such as a link with
  its token or the reader's name, carries the rule that lets it break anywhere, since on the panel the
  rule would reach a body's own table and split a column of amounts;
- pads no table through its ``style`` attribute (the shell has no ``<style>`` block), since classic
  Outlook ignores a table's padding and the body would sit against the panel's border, out of line with
  the header.

``tests/support/mail_styles.py`` reads the two rules as the two engines that enlarge text read a page's
inline styles, and its header names what it does not read. The planted pages below score it, as edits of
a frozen copy of the shell. ``test_mail_rendered_addresses.py`` holds every page the mail module sends to
both.
"""
import html
import re
from pathlib import Path

import pytest

from app.config import settings
from app.services import email_service
from tests.support.mail_styles import LONG_RUN, long_run_problems, long_runs, text_size_problems

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

    problems = text_size_problems(page)
    assert not problems, "\n".join(problems)
    assert long_run_problems(email_service._wrap_html(f"<p>{'x' * LONG_RUN}</p>")), (
        "the shell lets a body's runs break for it: put the rule on the lines that print one, since on the panel it "
        "reaches a body's own table and splits a column of amounts"
    )
    assert "<svg" not in page.lower(), "Gmail and Outlook drop inline SVG"
    assert not _VIEWPORT.search(page), "a 600 px page sets no viewport, so a mail view fits it to its screen"
    padded = [t for t in tokens if t.lower().startswith("<table") and _TABLE_PADDING.search(t)]
    assert not padded, f"classic Outlook ignores a table's padding: pad its cells instead: {padded}"


# The planted pages are edits of a frozen copy of the shell, so a change to the shell moves none of their
# anchors; the checks above read the shell as it is.
_SHELL = (Path(__file__).resolve().parents[1] / "fixtures" / "mail_shell.html").read_text(encoding="utf-8")


def _planted(body: str) -> str:
    return _SHELL.replace("{body}", body).replace("{footer}", "<span>The footer.</span>")


def test_the_frozen_shell_marks_its_two_slots():
    assert _SHELL.count("{body}") == 1 and _SHELL.count("{footer}") == 1, "the frozen shell no longer marks its two slots once each"


_PLANTED_BODY = "<p>Hi Ada,</p><p>Copy this link: https://www.earningsnerd.io/reset-password?token=abc</p>"
_HELD = "-webkit-text-size-adjust:100%;"
_HEADER_STYLE = 'style="width:600px;max-width:600px;background-color:#F4F3EE;-webkit-text-size-adjust:100%;"'
_FOOTER_LINE_TABLE = 'border="0" style="width:600px;max-width:600px;">'
_LEFT = "is not left to the view"
_NOT_HELD = "is not held at 100%"
_TAGLINE_CELL = '<td style="padding:16px 32px 28px 32px;'
# Each way a page can break the text-size rule, as edits of the shell's page, and the look-alikes that hold it.
TEXT_SIZES = [
    # Flagged.
    ("the property back on the body", (('<body style="', f'<body style="{_HELD}'),), _LEFT),
    ("the property on the html element", (('<html lang="en">', f'<html lang="en" style="{_HELD}">'),), _LEFT),
    ("the property on the outer table", (('bgcolor="#F4F3EE" style="background-color:#F4F3EE;">', f'bgcolor="#F4F3EE" style="background-color:#F4F3EE;{_HELD}">'),), _LEFT),
    ("the property on the panel's wrapper cell", (('<td align="center" style="padding:0 12px 24px 12px;">', f'<td align="center" style="padding:0 12px 24px 12px;{_HELD}">'),), _LEFT),
    ("the property on the panel", (("border-radius:16px;", f"border-radius:16px;{_HELD}"),), _LEFT),
    ("the unprefixed name on the panel, which Blink reads", (("border-radius:16px;", "border-radius:16px;text-size-adjust:100%;"),), "Blink reads 100%"),
    ("none on the panel's body cell", (("border-radius:15px 15px 0 0;", "border-radius:15px 15px 0 0;-webkit-text-size-adjust:none;"),), _LEFT),
    ("the property on a mail's own line", (("<p>Copy this link", f'<p style="{_HELD}">Copy this link'),), _LEFT),
    ("the property on a mail's own line after a CSS comment", (("<p>Copy this link", f'<p style="margin:0;/* keep iOS from resizing */{_HELD}">Copy this link'),), _LEFT),
    ("the property's name spelled with an entity", (('<body style="', '<body style="-webkit-text-size-&#97;djust:100%;'),), _LEFT),
    ("the property's name spelled with a CSS escape", (('<body style="', '<body style="-webkit-text-size-\\61 djust:100%;'),), _LEFT),
    ("an important hold over a later auto", (('<body style="', '<body style="-webkit-text-size-adjust:100% !important;-webkit-text-size-adjust:auto;'),), _LEFT),
    ("a hold in the first of two style attributes", (('<body style="', f'<body style="{_HELD}" style="'),), _LEFT),
    ("a hold iOS's WebKit reads alone", (('<body style="', f'<body style="{_HELD}text-size-adjust:auto;'),), "iOS's WebKit 100%"),
    ("a hold on the body, released for Blink alone in the panel and the footer line", (
        ('<body style="', f'<body style="{_HELD}'),
        ("border-radius:16px;", "border-radius:16px;text-size-adjust:auto;"),
        (_FOOTER_LINE_TABLE, 'border="0" style="width:600px;max-width:600px;text-size-adjust:auto;">'),
    ), "iOS's WebKit 100%"),
    ("a self-closing span that opens a hold", (("<p>Copy this link", f'<span style="{_HELD}"/><p>Copy this link'),), _LEFT),
    ("an unclosed b that the parser opens again in the next paragraph", (("<p>Hi Ada,</p>", f'<p>Hi Ada,<b style="{_HELD}"></p>'),), _LEFT),
    ("a style block's reset", (("</head>", "<style>body,table,td{-webkit-text-size-adjust:100%}</style></head>"),), "<style> block"),
    ("a self-closing style block's reset", (("</head>", "<style/>body{-webkit-text-size-adjust:100%}</style></head>"),), "<style> block"),
    ("a linked stylesheet", (("</head>", '<link rel="stylesheet" href="https://e.test/mail.css"></head>'),), "linked stylesheet"),
    ("a hold through calc(), which the check does not resolve", (('<body style="', '<body style="-webkit-text-size-adjust:calc(100%);'),), "takes its value from a function"),
    ("the header reopened by a later declaration", ((_HEADER_STYLE, _HEADER_STYLE[:-1] + '-webkit-text-size-adjust:auto;"'),), _NOT_HELD),
    ("the header reopened by the unprefixed name", ((_HEADER_STYLE, _HEADER_STYLE[:-1] + 'text-size-adjust:auto;"'),), "Blink reads auto"),
    ("the header reopened for iOS's WebKit alone", ((_HEADER_STYLE, _HEADER_STYLE[:-1] + '-webkit-text-size-adjust:auto;text-size-adjust:100%;"'),), "iOS's WebKit auto"),
    ("the header held for Blink alone", ((_HEADER_STYLE, _HEADER_STYLE.replace(_HELD, "-webkit-text-size-adjust:auto;text-size-adjust:100%;")),), "iOS's WebKit auto"),
    ("auto on the tagline's cell", ((_TAGLINE_CELL, _TAGLINE_CELL + "-webkit-text-size-adjust:auto;"),), _NOT_HELD),
    ("initial on the tagline's cell", ((_TAGLINE_CELL, _TAGLINE_CELL + "-webkit-text-size-adjust:initial;"),), _NOT_HELD),
    ("a self-closing span that reopens the tagline", (("The summary that ", '<span style="-webkit-text-size-adjust:auto;"/>The summary that '),), _NOT_HELD),
    ("auto in the first of two style attributes on the tagline's cell", ((_TAGLINE_CELL, '<td style="-webkit-text-size-adjust:auto;" style="'),), _NOT_HELD),
    ("the header held by the unprefixed name alone", ((_HEADER_STYLE, _HEADER_STYLE.replace("-webkit-text-size-adjust", "text-size-adjust")),), "iOS's WebKit auto"),
    ("the header held by none", ((_HEADER_STYLE, _HEADER_STYLE.replace("adjust:100%", "adjust:none")),), "stop a reader's own zoom"),
    ("the header's property dropped", ((_HEADER_STYLE, _HEADER_STYLE.replace(_HELD, "")),), _NOT_HELD),
    ("the header's table no longer found", (('width="600" cellpadding="0" cellspacing="0" border="0" bgcolor="#F4F3EE"', 'width="640" cellpadding="0" cellspacing="0" border="0" bgcolor="#F4F3EE"'),), "0 tables that read as the header"),
    ("a second wordmark, in the body", (("<p>Hi Ada,</p>", "<p>Hi Ada, from Earnings<em>Nerd</em></p>"),), "2 tables that read as the header"),
    ("the footer line held on the header's cream", ((_FOOTER_LINE_TABLE, f'border="0" bgcolor="#F4F3EE" style="width:600px;max-width:600px;{_HELD}">'),), _LEFT),
    # Pass.
    ("a space after the colon", ((_HEADER_STYLE, _HEADER_STYLE.replace("adjust:100%", "adjust: 100%")),), None),
    ("the property's name in capitals", ((_HEADER_STYLE, _HEADER_STYLE.replace("-webkit-text-size-adjust", "-WEBKIT-TEXT-SIZE-ADJUST")),), None),
    ("the header's value marked important", ((_HEADER_STYLE, _HEADER_STYLE.replace("adjust:100%;", "adjust:100% !important;")),), None),
    ("the header's value marked important with a space", ((_HEADER_STYLE, _HEADER_STYLE.replace("adjust:100%;", "adjust:100% ! important;")),), None),
    ("a CSS comment after the header's value", ((_HEADER_STYLE, _HEADER_STYLE.replace("adjust:100%;", "adjust:100% /* iOS */;")),), None),
    ("the unprefixed name beside the prefixed one", ((_HEADER_STYLE, _HEADER_STYLE[:-1] + 'text-size-adjust:100%;"'),), None),
    ("the unprefixed name on a header cell, under the table's prefixed hold", ((_TAGLINE_CELL, _TAGLINE_CELL + "text-size-adjust:100%;"),), None),
    ("inherit on a header cell", ((_TAGLINE_CELL, _TAGLINE_CELL + "-webkit-text-size-adjust:inherit;"),), None),
    ("unset on a header cell", ((_TAGLINE_CELL, _TAGLINE_CELL + "-webkit-text-size-adjust:unset;"),), None),
    ("revert on a header cell", ((_TAGLINE_CELL, _TAGLINE_CELL + "-webkit-text-size-adjust:revert;"),), None),
    ("a zero-width space inside the wordmark", (("Earnings<em ", "Earnings&#8203;<em "),), None),
    ("a later value the property cannot take", ((_HEADER_STYLE, _HEADER_STYLE[:-1] + '-webkit-text-size-adjust:banana;"'),), None),
    ("auto on the body", (('<body style="', '<body style="-webkit-text-size-adjust:auto;'),), None),
    ("auto on the panel", (("border-radius:16px;", "border-radius:16px;-webkit-text-size-adjust:auto;"),), None),
    ("the -ms- name on the body, which the engines that enlarge text ignore", (('<body style="', '<body style="-ms-text-size-adjust:100%;'),), None),
    ("a hold in a CSS comment on the body", (('<body style="', f'<body style="/* {_HELD} */'),), None),
    ("a hold in the second of two style attributes, which HTML drops", (('<body style="', f'<body style="margin:0;" style="{_HELD}'),), None),
    ("the footer line on the header's cream, held by nothing", ((_FOOTER_LINE_TABLE, 'border="0" bgcolor="#F4F3EE" style="width:600px;max-width:600px;">'),), None),
    ("the brand named in the body's prose", (("<p>Hi Ada,</p>", "<p>Hi Ada, from EarningsNerd</p>"),), None),
]


@pytest.mark.parametrize("edits, expected", [case[1:] for case in TEXT_SIZES], ids=[case[0] for case in TEXT_SIZES])
def test_the_text_size_check_scores_every_planted_page(edits, expected):
    page = _planted(_PLANTED_BODY)
    for old, new in edits:
        assert page.count(old) == 1, f"the planted edit no longer finds {old!r} once in the page"
        page = page.replace(old, new)
    problems = text_size_problems(page)
    if expected is None:
        assert not problems, problems
    else:
        assert any(expected in problem for problem in problems), f"expected {expected!r}, got {problems}"


# A link as the reset, verify and invite mails print it: a token as secrets.token_urlsafe(32) draws one,
# 43 characters, here with no hyphen to break at.
_TOKEN = "Qm9va3NhbmRjb2ZmZWVhbmRyZWFkaW5nYWxsZGF5MDE"
_LONG_LINK = f"https://www.earningsnerd.io/reset-password?token={_TOKEN}"
_BREAK = email_service._BREAK_ANYWHERE
_LINE_STYLE = f"margin:0;font-size:12px;color:#6B7280;{_BREAK}"
_COPY_LINE = f'<p style="{_LINE_STYLE}">Can&apos;t click the button? Copy this link:<br>{_LONG_LINK}</p>'
_BODY_CELL = '<td style="padding:32px 32px 0 32px;'
_RESET = "overflow-wrap:normal;word-break:normal;"
# The link split by inline markup into pieces of 15 characters, none long enough to count alone.
_SPLIT_LINK = "".join(f"<b>{_LONG_LINK[i:i + 15]}</b>" if i % 30 else _LONG_LINK[i:i + 15] for i in range(0, len(_LONG_LINK), 15))
_NOWHERE = "has nowhere to break"
_NO_WRAP = "cannot wrap"
# Each way a page can show a long run with nowhere to break, as edits of a page that prints a link, and the
# look-alikes that break it.
LONG_RUNS = [
    # Flagged.
    ("the rule dropped from the line", ((_LINE_STYLE, "margin:0;font-size:12px;color:#6B7280;"),), _NOWHERE),
    ("a later reset in the line's style", ((_LINE_STYLE, _LINE_STYLE + _RESET),), _NOWHERE),
    ("an important reset after the rule", ((_LINE_STYLE, _LINE_STYLE + "overflow-wrap:normal !important;word-break:normal !important;"),), _NOWHERE),
    ("an inner reset around the link", ((f"<br>{_LONG_LINK}", f'<br><span style="{_RESET}">{_LONG_LINK}</span>'),), _NOWHERE),
    ("a self-closing span that opens a reset", ((f"<br>{_LONG_LINK}", f'<br><span style="{_RESET}"/>{_LONG_LINK}'),), _NOWHERE),
    ("the rule in a CSS comment", ((_LINE_STYLE, f"margin:0;font-size:12px;color:#6B7280;/* {_BREAK} */"),), _NOWHERE),
    ("the rule's values misspelled", ((_BREAK, "overflow-wrap:everywhere;word-break:break-everything;"),), _NOWHERE),
    ("overflow-wrap:break-word alone, which leaves a cell its narrowest width", ((_BREAK, "overflow-wrap:break-word;"),), _NOWHERE),
    ("the rule in the second of two style attributes", ((f'<p style="{_LINE_STYLE}">', f'<p style="margin:0;font-size:12px;" style="{_BREAK}">'),), _NOWHERE),
    ("the link split by inline markup into short pieces, the rule dropped", ((_COPY_LINE, f"<p>Copy this link:<br>{_SPLIT_LINK}</p>"),), _NOWHERE),
    ("a run of 24 characters with no rule", ((_COPY_LINE, _COPY_LINE + f"<p>{'x' * 24}</p>"),), _NOWHERE),
    ("a run that inline markup splits into pieces under 24", ((_COPY_LINE, _COPY_LINE + f"<p>{'x' * 20}<b>{'x' * 20}</b></p>"),), _NOWHERE),
    ("a run across an element the reader does not know", ((_COPY_LINE, _COPY_LINE + f"<p>{'x' * 20}<o:p></o:p>{'x' * 20}</p>"),), _NOWHERE),
    ("a run across an acronym and an output", ((_COPY_LINE, _COPY_LINE + f"<p>{'x' * 20}<acronym>{'x' * 10}</acronym><output>{'x' * 10}</output></p>"),), _NOWHERE),
    ("a run across an element the page hides", ((_COPY_LINE, _COPY_LINE + f'<p>{"x" * 20}<span style="display:none">y</span>{"x" * 20}</p>'),), _NOWHERE),
    ("a run across an element the hidden attribute hides", ((_COPY_LINE, _COPY_LINE + f"<p>{'x' * 20}<span hidden>y</span>{'x' * 20}</p>"),), _NOWHERE),
    ("a run across a div set display:initial, which is inline", ((_COPY_LINE, _COPY_LINE + f'<div>{"x" * 20}<div style="display:initial">{"x" * 20}</div></div>'),), _NOWHERE),
    ("a run across a span with a display no engine takes", ((_COPY_LINE, _COPY_LINE + f'<p>{"x" * 20}<span style="display:banana">{"x" * 20}</span></p>'),), _NOWHERE),
    ("a run across a form feed, where no line breaks", ((_COPY_LINE, _COPY_LINE + f"<p>{'x' * 20}\f{'x' * 20}</p>"),), _NOWHERE),
    ("word-wrap:anywhere alone, which an engine may drop under that name", ((_BREAK, "word-wrap:anywhere;"),), _NOWHERE),
    ("the rule through var(), which the check does not resolve", ((_BREAK, "overflow-wrap:var(--wrap);word-break:break-word;"),), "takes its value from a function"),
    ("a style block, which the check does not read", (("</head>", "<style>p{white-space:nowrap}</style></head>"),), "<style> block"),
    ("a nowrap span around the link", ((f"<br>{_LONG_LINK}", f'<br><span style="white-space:nowrap;">{_LONG_LINK}</span>'),), _NO_WRAP),
    ("white-space:pre on the line", ((_LINE_STYLE, _LINE_STYLE + "white-space:pre;"),), _NO_WRAP),
    ("text-wrap-mode:nowrap on the line", ((_LINE_STYLE, _LINE_STYLE + "text-wrap-mode:nowrap;"),), _NO_WRAP),
    ("text-wrap:nowrap on the line", ((_LINE_STYLE, _LINE_STYLE + "text-wrap:nowrap;"),), _NO_WRAP),
    ("text-wrap's two words, nowrap among them", ((_LINE_STYLE, _LINE_STYLE + "text-wrap:nowrap pretty;"),), _NO_WRAP),
    ("a nowrap white-space in its longhands' words", ((_LINE_STYLE, _LINE_STYLE + "white-space:collapse nowrap;"),), _NO_WRAP),
    ("the link in a nobr", ((f"<br>{_LONG_LINK}", f"<br><nobr>{_LONG_LINK}</nobr>"),), _NO_WRAP),
    ("the link in a pre, which closes the line", ((f"<br>{_LONG_LINK}", f"<br><pre>{_LONG_LINK}</pre>"),), _NO_WRAP),
    ("revert on a pre, which keeps its own white-space", ((f"<br>{_LONG_LINK}", f'<br><pre style="white-space:revert;">{_LONG_LINK}</pre>'),), _NO_WRAP),
    ("the body's cell set nowrap", ((_BODY_CELL, '<td nowrap style="padding:32px 32px 0 32px;'),), _NO_WRAP),
    ("a wbr under nowrap, which does not break", ((_COPY_LINE, _COPY_LINE + f'<p style="white-space:nowrap;">{"x" * 20}<wbr>{"x" * 20}</p>'),), _NO_WRAP),
    ("a short phrase kept whole past the threshold", ((_COPY_LINE, _COPY_LINE + '<p style="white-space:nowrap;">Read the AI summary of this filing now</p>'),), _NO_WRAP),
    # Pass.
    ("the line as the mails write it", (), None),
    ("overflow-wrap:anywhere alone", ((_BREAK, "overflow-wrap:anywhere;"),), None),
    ("word-break:break-word alone", ((_BREAK, "word-break:break-word;"),), None),
    ("word-break:break-all alone", ((_BREAK, "word-break:break-all;"),), None),
    ("line-break:anywhere alone", ((_BREAK, "line-break:anywhere;"),), None),
    ("an important rule over a later reset", ((_BREAK, "overflow-wrap:anywhere !important;word-break:break-word !important;" + _RESET),), None),
    ("the rule on the body's cell, which the line inherits", ((_LINE_STYLE, "margin:0;font-size:12px;color:#6B7280;"), (_BODY_CELL, _BODY_CELL + _BREAK)), None),
    ("the link split by inline markup into short pieces, with the rule", ((f"<br>{_LONG_LINK}", f"<br>{_SPLIT_LINK}"),), None),
    ("pre-wrap with the rule", ((_LINE_STYLE, _LINE_STYLE + "white-space:pre-wrap;"),), None),
    ("white-space:inherit on the line", ((_LINE_STYLE, _LINE_STYLE + "white-space:inherit;"),), None),
    ("white-space:initial on the line, in a nowrap cell", ((_LINE_STYLE, _LINE_STYLE + "white-space:initial;"), (_BODY_CELL, '<td nowrap style="padding:32px 32px 0 32px;')), None),
    ("a run of 23 characters with no rule", ((_COPY_LINE, _COPY_LINE + f"<p>{'x' * 23}</p>"),), None),
    ("two blocks side by side, each under 24", ((_COPY_LINE, _COPY_LINE + f"<p>{'x' * 20}</p><p>{'x' * 20}</p>"),), None),
    ("a block opened inside a line, each side under 24", ((_COPY_LINE, _COPY_LINE + f"<div>{'x' * 20}<div>{'x' * 20}</div></div>"),), None),
    ("a long run broken by a thin space", ((_COPY_LINE, _COPY_LINE + f"<p>{'x' * 20}\u2009{'x' * 20}</p>"),), None),
    ("a long run the page hides", ((_COPY_LINE, _COPY_LINE + f'<div style="display:none">{"x" * 60}</div>'),), None),
    ("a long run under the hidden attribute", ((_COPY_LINE, _COPY_LINE + f"<div hidden>{'x' * 60}</div>"),), None),
    ("a long run in the head's title", (("</head>", f"<title>{'x' * 60}</title></head>"),), None),
    ("a long run broken by a wbr", ((_COPY_LINE, _COPY_LINE + f"<p>{'x' * 20}<wbr>{'x' * 20}</p>"),), None),
    ("a long run broken by a zero-width space", ((_COPY_LINE, _COPY_LINE + f"<p>{'x' * 20}\u200b{'x' * 20}</p>"),), None),
    ("a pre whose lines are short", ((_COPY_LINE, _COPY_LINE + f"<pre>{'x' * 20}\n{'x' * 20}</pre>"),), None),
]


@pytest.mark.parametrize("edits, expected", [case[1:] for case in LONG_RUNS], ids=[case[0] for case in LONG_RUNS])
def test_the_long_run_check_scores_every_planted_page(edits, expected):
    page = _planted(f"<p>Hi Ada,</p>{_COPY_LINE}")
    assert any(_TOKEN in run for run in long_runs(page)), "the planted page no longer prints its link as one run"
    for old, new in edits:
        assert page.count(old) == 1, f"the planted edit no longer finds {old!r} once in the page"
        page = page.replace(old, new)
    problems = long_run_problems(page)
    if expected is None:
        assert not problems, problems
    else:
        assert any(expected in problem for problem in problems), f"expected {expected!r}, got {problems}"
