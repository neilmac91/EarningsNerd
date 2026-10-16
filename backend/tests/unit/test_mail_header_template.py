"""Gate: the mail's header and footer line are the brand template's, and the page around them holds.

``docs/brand/templates/email-header.html`` is the editable preview of the header (the lockup, a
hairline, the marked tagline) and the footer line, and ``email_service._wrap_html`` carries its
markup, ported (CLAUDE.md rule 12: a change to one is a change to the other). The two are compared
cell by cell, each page's outer table's cells, tag for tag and text for text, plain comments aside and
Outlook's conditional comments as written, with whitespace counted as a browser renders it:
- in text, a run of spaces, tabs and line breaks is one space, and a form feed, a no-break or an em
  space renders as itself;
- whitespace beside a table's own tags renders nothing, a form feed included, and is dropped;
- in a tag, the whitespace between attributes is one space, and a quoted value is compared as written,
  so a value reflowed in one file is reflowed in the other.

One difference is allowed: the preview's tile is inline SVG in a cell Outlook skips, and the mail's is
the hosted raster the template's note spells (``<img src="{base}/assets/earningsnerd-appicon.png" ...>``),
on ``FRONTEND_URL``. The template's outer table holds two cells, the header's and the footer line's; the
page's holds three, the header's, the panel's and the footer line's. Around them, the page:

- puts the body and the footer in the panel's cells, each once and each in a cell of its own, and
  carries one wordmark, the name split by markup into its two styles: the header's;
- is fluid: the header, the panel and the footer line each take the screen's width up to 600 px
  (``width="100%"``, ``width:100%;max-width:600px``), and the head sets the template's viewport, once, at the
  phone's own width (``width=device-width, initial-scale=1``), so a phone lays the page out at its width and
  shows the text at its set size. No box a client other than classic Outlook shows is set wider than the
  room its parent gives it on the narrowest phone, and classic Outlook, which reads no ``max-width``, holds
  each column at 600 px through a table only its conditional comments show;
- carries no inline SVG, which Gmail and Outlook drop;
- keeps the header at its set size in a view that enlarges small text, such as one that fits a wider page
  to a phone's screen (``-webkit-text-size-adjust:100%`` on its table), and leaves every other line to the
  view, the panel's and the footer line's;
- breaks no run of a body's for it: a line that prints a run with nowhere to break, such as a link with
  its token or the reader's name, carries the rule that lets it break anywhere, since on the panel the
  rule would reach a body's own table and split a column of amounts; nor does a body lend it to a table;
- names filing data alone in its footer line, "Filing data sourced from SEC EDGAR. Not investment advice.":
  it sits on every mail, the earnings-day alert among them, whose report dates come from a provider (D-043);
- pads no table through its ``style`` attribute (the shell has no ``<style>`` block), since classic
  Outlook ignores a table's padding and the body would sit against the panel's border, out of line with
  the header.

``tests/support/mail_styles.py`` models how Blink and WebKit read a page's inline styles, and its header
names what the model leaves out. The planted pages below score it, as edits of a frozen copy of the shell.
``test_mail_rendered_addresses.py`` holds every page the mail module sends to its rules.
"""
import html
import re
from pathlib import Path

import pytest

from app.config import settings
from app.services import email_service
from tests.support.mail_styles import (
    LONG_RUN,
    WIDEST_FIXED,
    fixed_width_problems,
    lent_runs,
    long_run_problems,
    long_runs,
    outlook_width_problems,
    reach_problems,
    text_size_problems,
    viewports,
)

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
_DEVICE_WIDTH = "width=device-width, initial-scale=1"
_FOOTER_WORDING = "Filing data sourced from SEC EDGAR. Not investment advice."
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


def _outer_cells(tokens: list[str]) -> list[list[str]]:
    """The cells of the page's outermost table, each through its own closing tag. A table in a cell, an
    Outlook table in a conditional comment among them, is the cell's."""
    start = next(i for i, token in enumerate(tokens) if token.startswith("<table"))
    cells, depth, opened = [], 0, None
    for i in range(start, len(tokens)):
        token = tokens[i]
        if token.startswith("<table"):
            depth += 1
        elif token == "</table>":
            depth -= 1
            if depth == 0:
                return cells
        elif depth == 1 and opened is None and (token == "<td>" or token.startswith("<td ")):
            opened = i
        elif depth == 1 and opened is not None and token == "</td>":
            cells.append(tokens[opened : i + 1])
            opened = None
    raise AssertionError("the page's outer table never closes")


def _template_cells() -> tuple[list[str], list[str], str]:
    """The template's header and footer-line cells, and the tile its note spells."""
    source = TEMPLATE.read_text(encoding="utf-8")
    cells = _outer_cells(_tokens(source))
    assert len(cells) == 2, f"the template's outer table no longer holds a cell for the header and one for the footer line: {len(cells)} cells"
    note_tile = _TILE_IN_NOTE.search(source)
    assert note_tile, "the template's note no longer spells the mail's tile"
    return cells[0], cells[1], " ".join(note_tile.group(0).split())


def test_the_header_and_footer_line_are_the_templates(monkeypatch):
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://frontend.example.test")
    header, footer_line, note_tile = _template_cells()
    open_cell = header.index("<!--[if !mso]>")
    assert header[open_cell + 1] == "<!-->", "the template's tile cell is no longer the one Outlook skips"
    close_cell = header.index("<!--<![endif]-->", open_cell)
    cell = header[open_cell + 2]
    assert cell.startswith("<td") and "<svg" in "".join(header[open_cell:close_cell]), "the template's tile is no longer an SVG in a cell"
    tile = note_tile.replace("{base}", "https://frontend.example.test")
    expected_header = header[:open_cell] + [cell, tile, "</td>"] + header[close_cell + 1 :]

    cells = _outer_cells(_tokens(email_service._wrap_html("<p>Body</p>")))
    assert len(cells) == 3, f"the page's outer table holds a cell each for the header, the panel and the footer line: {len(cells)} cells"
    assert cells[0] == expected_header, (
        "the mail's header is no longer the template's (docs/brand/templates/email-header.html): change both"
    )
    assert cells[2] == footer_line, (
        "the mail's footer line is no longer the template's (docs/brand/templates/email-header.html): change both"
    )
    assert any(token.startswith("<table") and "border:1px solid #E5E1D8" in token for token in cells[1]), (
        "the panel sits between the header and the footer line"
    )


def test_the_footer_line_names_filing_data_alone():
    for where, cell in (
        ("the mail", _outer_cells(_tokens(email_service._wrap_html("<p>Body</p>")))[2]),
        ("the template", _template_cells()[1]),
    ):
        text = html.unescape(" ".join(token for token in cell if not token.startswith("<"))).strip()
        assert text == _FOOTER_WORDING, (
            f"{where}'s footer line reads {text!r}: it sits on every mail, the earnings-day alert among them, whose report "
            f"dates and times come from a provider, so it names the filing data EDGAR sources alone ({_FOOTER_WORDING!r}, D-043)"
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

    problems = text_size_problems(page) + fixed_width_problems(page) + outlook_width_problems(page) + reach_problems(page)
    assert not problems, "\n".join(problems)
    plain = email_service._wrap_html(f"<p>{'x' * LONG_RUN}</p>")
    assert long_run_problems(plain) and not lent_runs(plain), (
        "the shell lets a body's runs break for it, in some engine: put the rule on the lines that print one, since on "
        "the panel it reaches a body's own table and splits a column of amounts"
    )
    columns = [t for t in tokens if t.startswith("<table") and "max-width:600px" in t]
    assert len(columns) == 3 and all('width="100%"' in t and "width:100%;max-width:600px;" in t for t in columns), (
        "the header, the panel and the footer line each take the screen's width up to 600 px (width=\"100%\" and "
        f"width:100%;max-width:600px), so a phone lays them out at its own width: {columns}"
    )
    sets, template_sets = viewports(page), viewports(TEMPLATE.read_text(encoding="utf-8"))
    assert sets == template_sets == [_DEVICE_WIDTH], (
        f"the page sets the template's viewport, once, at the phone's own width ({_DEVICE_WIDTH!r}), so a phone lays it out "
        f"at that width: {sets} against the template's {template_sets}"
    )
    assert "<svg" not in page.lower(), "Gmail and Outlook drop inline SVG"
    padded = [t for t in tokens if t.lower().startswith("<table") and _TABLE_PADDING.search(t)]
    assert not padded, f"classic Outlook ignores a table's padding: pad its cells instead: {padded}"


# The planted pages are edits of a frozen copy of the shell, so a change to the shell moves none of their
# anchors; the checks above read the shell as it is.
_SHELL = (Path(__file__).resolve().parents[1] / "fixtures" / "mail_shell.html").read_text(encoding="utf-8")


def _planted(body: str) -> str:
    return _SHELL.replace("{body}", body).replace("{footer}", "<span>The footer.</span>")


def _scored(page: str, edits) -> str:
    for old, new in edits:
        assert page.count(old) == 1, f"the planted edit no longer finds {old!r} once in the page"
        page = page.replace(old, new)
    return page


def test_the_frozen_shell_marks_its_two_slots():
    assert _SHELL.count("{body}") == 1 and _SHELL.count("{footer}") == 1, "the frozen shell no longer marks its two slots once each"


_PLANTED_BODY = "<p>Hi Ada,</p><p>Copy this link: https://www.earningsnerd.io/reset-password?token=abc</p>"
_HELD = "-webkit-text-size-adjust:100%;"
_HEADER_STYLE = 'style="width:100%;max-width:600px;background-color:#F4F3EE;-webkit-text-size-adjust:100%;"'
_FOOTER_LINE_TABLE = 'border="0" style="width:100%;max-width:600px;">'
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
        (_FOOTER_LINE_TABLE, 'border="0" style="width:100%;max-width:600px;text-size-adjust:auto;">'),
    ), "iOS's WebKit 100%"),
    ("a self-closing span that opens a hold", (("<p>Copy this link", f'<span style="{_HELD}"/><p>Copy this link'),), _LEFT),
    ("an unclosed b that the parser opens again in the next paragraph", (("<p>Hi Ada,</p>", f'<p>Hi Ada,<b style="{_HELD}"></p>'),), _LEFT),
    ("a style block's reset", (("</head>", "<style>body,table,td{-webkit-text-size-adjust:100%}</style></head>"),), "<style> block"),
    ("a self-closing style block's reset", (("</head>", "<style/>body{-webkit-text-size-adjust:100%}</style></head>"),), "<style> block"),
    ("an SVG's style block in the body", (("<p>Copy this link", '<svg width="0" height="0"><style>body{-webkit-text-size-adjust:100%}</style></svg><p>Copy this link'),), "<style> block"),
    ("a linked stylesheet", (("</head>", '<link rel="stylesheet" href="https://e.test/mail.css"></head>'),), "linked stylesheet"),
    ("a linked stylesheet named in capitals", (("</head>", '<link rel="StyleSheet" href="https://e.test/mail.css"></head>'),), "linked stylesheet"),
    ("an alternate stylesheet", (("</head>", '<link rel="alternate stylesheet" href="https://e.test/mail.css"></head>'),), "linked stylesheet"),
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
    ("the header's value marked important without its bang, which CSS drops", ((_HEADER_STYLE, _HEADER_STYLE.replace("adjust:100%;", "adjust:100% important;")),), _NOT_HELD),
    ("the header's table no longer found", ((_HEADER_STYLE, _HEADER_STYLE.replace("max-width:600px", "max-width:640px")),), "0 tables that read as the header"),
    ("the header hidden", ((_HEADER_STYLE, _HEADER_STYLE[:-1] + 'display:none;"'),), "shows no line of the header"),
    ("a second wordmark, in the body", (("<p>Hi Ada,</p>", "<p>Hi Ada, from Earnings<em>Nerd</em></p>"),), "2 tables that read as the header"),
    ("the footer line held on the header's cream", ((_FOOTER_LINE_TABLE, f'border="0" bgcolor="#F4F3EE" style="width:100%;max-width:600px;{_HELD}">'),), _LEFT),
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
    ("a hold inside Outlook's conditional comment, which no other client reads", (("<p>Copy this link", f'<!--[if mso]><p style="{_HELD}">x</p><![endif]--><p>Copy this link'),), None),
    ("the footer line on the header's cream, held by nothing", ((_FOOTER_LINE_TABLE, 'border="0" bgcolor="#F4F3EE" style="width:100%;max-width:600px;">'),), None),
    ("the brand named in the body's prose", (("<p>Hi Ada,</p>", "<p>Hi Ada, from EarningsNerd</p>"),), None),
]


@pytest.mark.parametrize("edits, expected", [case[1:] for case in TEXT_SIZES], ids=[case[0] for case in TEXT_SIZES])
def test_the_text_size_check_scores_every_planted_page(edits, expected):
    problems = text_size_problems(_scored(_planted(_PLANTED_BODY), edits))
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
_RESET = "overflow-wrap:normal;word-break:normal;line-break:auto;"  # each property the rule may take its break from
# The link split by inline markup into pieces of 15 characters, none long enough to count alone.
_SPLIT_LINK = "".join(f"<b>{_LONG_LINK[i:i + 15]}</b>" if i % 30 else _LONG_LINK[i:i + 15] for i in range(0, len(_LONG_LINK), 15))
_UNDER = "x" * 15  # a stretch under LONG_RUN, two of which make a run over it
_PHRASE = "Read the AI summary"  # over LONG_RUN with its spaces, under it without them
_NOWHERE = "has nowhere to break"
_NO_WRAP = "cannot wrap"
# Each way a page can show a long run with nowhere to break, as edits of a page that prints a link, and the
# look-alikes that break it.
LONG_RUNS = [
    # Flagged.
    ("the rule dropped from the line", ((_LINE_STYLE, "margin:0;font-size:12px;color:#6B7280;"),), _NOWHERE),
    ("a later reset in the line's style", ((_LINE_STYLE, _LINE_STYLE + _RESET),), _NOWHERE),
    ("an important reset after the rule", ((_LINE_STYLE, _LINE_STYLE + _RESET.replace(";", " !important;")),), _NOWHERE),
    ("word-wrap:normal after overflow-wrap:anywhere, which it resets as its alias", ((_BREAK, "overflow-wrap:anywhere;word-wrap:normal;"),), _NOWHERE),
    ("an inner reset around the link", ((f"<br>{_LONG_LINK}", f'<br><span style="{_RESET}">{_LONG_LINK}</span>'),), _NOWHERE),
    ("a self-closing span that opens a reset", ((f"<br>{_LONG_LINK}", f'<br><span style="{_RESET}"/>{_LONG_LINK}'),), _NOWHERE),
    ("the rule in a CSS comment", ((_LINE_STYLE, f"margin:0;font-size:12px;color:#6B7280;/* {_BREAK} */"),), _NOWHERE),
    ("the rule's values misspelled", ((_BREAK, "overflow-wrap:everywhere;word-break:break-everything;"),), _NOWHERE),
    ("overflow-wrap:break-word alone, which leaves a cell its narrowest width", ((_BREAK, "overflow-wrap:break-word;"),), _NOWHERE),
    ("word-break:keep-all, which breaks nothing", ((_BREAK, "word-break:keep-all;"),), _NOWHERE),
    ("the rule in the second of two style attributes", ((f'<p style="{_LINE_STYLE}">', f'<p style="margin:0;font-size:12px;" style="{_BREAK}">'),), _NOWHERE),
    ("the link split by inline markup into short pieces, the rule dropped", ((_COPY_LINE, f"<p>Copy this link:<br>{_SPLIT_LINK}</p>"),), _NOWHERE),
    ("a run of 18 characters with no rule", ((_COPY_LINE, _COPY_LINE + f"<p>{'x' * 18}</p>"),), _NOWHERE),
    ("a run that inline markup splits into pieces under the threshold", ((_COPY_LINE, _COPY_LINE + f"<p>{_UNDER}<b>{_UNDER}</b></p>"),), _NOWHERE),
    ("a run across a span, a link, a strong, an em and a code", ((_COPY_LINE, _COPY_LINE + "<p>xxxxx<span>xxxxx</span><a href='#'>xxxxx</a><strong>xxxxx</strong><em>xxxxx</em><code>xxxxx</code></p>"),), _NOWHERE),
    ("a run joined by no-break spaces", ((_COPY_LINE, _COPY_LINE + f"<p>{'x' * 10}&nbsp;{'x' * 10}</p>"),), _NOWHERE),
    ("a run joined by a figure space", ((_COPY_LINE, _COPY_LINE + f"<p>{'x' * 10}\u2007{'x' * 10}</p>"),), _NOWHERE),
    ("a run joined by a narrow no-break space", ((_COPY_LINE, _COPY_LINE + f"<p>{'x' * 10}\u202f{'x' * 10}</p>"),), _NOWHERE),
    ("a run across an input of type hidden", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<input type="hidden" value="y">{_UNDER}</p>'),), _NOWHERE),
    ("a run across an audio without its controls", ((_COPY_LINE, _COPY_LINE + f"<p>{_UNDER}<audio></audio>{_UNDER}</p>"),), _NOWHERE),
    ("a run across a div set display:inherit inside a span", ((_COPY_LINE, _COPY_LINE + f'<div><span>{_UNDER}<div style="display:inherit">{_UNDER}</div></span></div>'),), _NOWHERE),
    ("a block set display:inherit inside a block, each side under the threshold", ((_COPY_LINE, _COPY_LINE + f'<div>{_UNDER}<div style="display:inherit">{_UNDER}</div></div>'),), None),
    ("a run across a span set display:run-in, which neither engine takes", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<span style="display:run-in">{_UNDER}</span></p>'),), _NOWHERE),
    ("a run across a span set display:math, inline on an HTML element", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<span style="display:math">{_UNDER}</span></p>'),), _NOWHERE),
    ("a run across an object's fallback", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<object data="x.swf">{_UNDER}</object></p>'),), _NOWHERE),
    ("a run across an embed with no source", ((_COPY_LINE, _COPY_LINE + f"<p>{_UNDER}<embed>{_UNDER}</p>"),), _NOWHERE),
    ("a run across an element the reader does not know", ((_COPY_LINE, _COPY_LINE + f"<p>{_UNDER}<o:p></o:p>{_UNDER}</p>"),), _NOWHERE),
    ("a run across an acronym and an output", ((_COPY_LINE, _COPY_LINE + f"<p>{'x' * 10}<acronym>{'x' * 5}</acronym><output>{'x' * 5}</output></p>"),), _NOWHERE),
    ("a run across an element the page hides", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<span style="display:none">y</span>{_UNDER}</p>'),), _NOWHERE),
    ("a run across an element the hidden attribute hides", ((_COPY_LINE, _COPY_LINE + f"<p>{_UNDER}<span hidden>y</span>{_UNDER}</p>"),), _NOWHERE),
    ("a run across a span the hidden attribute marks and its display shows", ((_COPY_LINE, _COPY_LINE + f'<p>{"x" * 10}<span hidden style="display:inline">{"x" * 10}</span></p>'),), _NOWHERE),
    ("a run across a div set display:initial, which is inline", ((_COPY_LINE, _COPY_LINE + f'<div>{_UNDER}<div style="display:initial">{_UNDER}</div></div>'),), _NOWHERE),
    ("a run across a span with a display no engine takes", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<span style="display:banana">{_UNDER}</span></p>'),), _NOWHERE),
    ("a run across a span set display:block block, a pair no engine takes", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<span style="display:block block">{_UNDER}</span></p>'),), _NOWHERE),
    ("a run across a form feed, where no line breaks", ((_COPY_LINE, _COPY_LINE + f"<p>{_UNDER}\f{_UNDER}</p>"),), _NOWHERE),
    ("a run across a float, whose two sides join in the line", ((_COPY_LINE, _COPY_LINE + f'<div>{_UNDER}<div style="float:left">y</div>{_UNDER}</div>'),), _NOWHERE),
    ("a run across a box positioned absolute", ((_COPY_LINE, _COPY_LINE + f'<div>{_UNDER}<div style="position:absolute">y</div>{_UNDER}</div>'),), _NOWHERE),
    ("a run across a floated image", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<img src="https://e.test/x.png" width="8" alt="" style="float:left">{_UNDER}</p>'),), _NOWHERE),
    ("a run across an image its align floats", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<img src="https://e.test/x.png" width="8" alt="" align="left">{_UNDER}</p>'),), _NOWHERE),
    ("a run across a span set float:inherit, which takes its line's none", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<span style="float:inherit">{_UNDER}</span></p>'),), _NOWHERE),
    ("a run across an input of type hidden set display:block, which a browser hides all the same", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<input type="hidden" style="display:block" value="y">{_UNDER}</p>'),), _NOWHERE),
    ("a run across an audio set display:block, which a browser hides all the same", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<audio style="display:block"></audio>{_UNDER}</p>'),), _NOWHERE),
    ("word-wrap:anywhere alone, which WebKit may drop under that name", ((_BREAK, "word-wrap:anywhere;"),), _NOWHERE),
    ("all:initial after the rule, which resets it", ((_LINE_STYLE, _LINE_STYLE + "all:initial;"),), _NOWHERE),
    ("the rule through var(), which the check does not resolve", ((_BREAK, "overflow-wrap:var(--wrap);word-break:break-word;"),), "takes its value from a function"),
    ("a reset through a var() in brackets, which defers it all the same", ((_LINE_STYLE, _LINE_STYLE + "overflow-wrap:(var(--w));word-break:(var(--w));"),), "takes its value from a function"),
    ("-webkit-line-break:auto after line-break:anywhere, which it resets as its alias", ((_BREAK, "line-break:anywhere;-webkit-line-break:auto;"),), _NOWHERE),
    ("-webkit-line-break:anywhere alone, which Blink drops", ((_BREAK, "-webkit-line-break:anywhere;"),), _NOWHERE),
    ("a style block, which the check does not read", (("</head>", "<style>p{white-space:nowrap}</style></head>"),), "<style> block"),
    ("a nowrap span around the link", ((f"<br>{_LONG_LINK}", f'<br><span style="white-space:nowrap;">{_LONG_LINK}</span>'),), _NO_WRAP),
    ("white-space:pre on the line", ((_LINE_STYLE, _LINE_STYLE + "white-space:pre;"),), _NO_WRAP),
    ("text-wrap-mode:nowrap on the line", ((_LINE_STYLE, _LINE_STYLE + "text-wrap-mode:nowrap;"),), _NO_WRAP),
    ("text-wrap:nowrap on the line", ((_LINE_STYLE, _LINE_STYLE + "text-wrap:nowrap;"),), _NO_WRAP),
    ("text-wrap's two words, nowrap among them", ((_LINE_STYLE, _LINE_STYLE + "text-wrap:nowrap pretty;"),), _NO_WRAP),
    ("a nowrap white-space in its longhands' words", ((_LINE_STYLE, _LINE_STYLE + "white-space:collapse nowrap;"),), _NO_WRAP),
    ("white-space's longhand words, preserve nowrap", ((_LINE_STYLE, _LINE_STYLE + "white-space:preserve nowrap;"),), _NO_WRAP),
    ("text-wrap-mode:wrap after white-space:nowrap, which an older engine ignores", ((_LINE_STYLE, _LINE_STYLE + "white-space:nowrap;text-wrap-mode:wrap;"),), _NO_WRAP),
    ("the link in a nobr", ((f"<br>{_LONG_LINK}", f"<br><nobr>{_LONG_LINK}</nobr>"),), _NO_WRAP),
    ("the link in a pre, which closes the line", ((f"<br>{_LONG_LINK}", f"<br><pre>{_LONG_LINK}</pre>"),), _NO_WRAP),
    ("the link in a listing", ((f"<br>{_LONG_LINK}", f"<br><listing>{_LONG_LINK}</listing>"),), _NO_WRAP),
    ("the link in an xmp", ((f"<br>{_LONG_LINK}", f"<br><xmp>{_LONG_LINK}</xmp>"),), _NO_WRAP),
    ("revert on a pre, which keeps its own white-space", ((f"<br>{_LONG_LINK}", f'<br><pre style="white-space:revert;">{_LONG_LINK}</pre>'),), _NO_WRAP),
    ("the body's cell set nowrap", ((_BODY_CELL, '<td nowrap style="padding:32px 32px 0 32px;'),), _NO_WRAP),
    ("a header cell of the body's set nowrap", ((_COPY_LINE, _COPY_LINE + f"<table><tr><th nowrap>{_PHRASE}</th></tr></table>"),), _NO_WRAP),
    ("a wbr under nowrap, which the reader counts no break at, though Chromium breaks there", ((_COPY_LINE, _COPY_LINE + f'<p style="white-space:nowrap;">{_UNDER}<wbr>{_UNDER}</p>'),), _NO_WRAP),
    ("revert-layer on a nowrap cell's white-space, which keeps the attribute", ((_BODY_CELL, '<td nowrap style="white-space:revert-layer;padding:32px 32px 0 32px;'),), _NO_WRAP),
    ("white-space:preserve-spaces after nowrap, which Chromium refuses", ((_LINE_STYLE, _LINE_STYLE + "white-space:nowrap;white-space:preserve-spaces;"),), _NO_WRAP),
    ("text-wrap:avoid-orphans after text-wrap-mode:nowrap, which Chromium refuses", ((_LINE_STYLE, _LINE_STYLE + "text-wrap-mode:nowrap;text-wrap:avoid-orphans;"),), _NO_WRAP),
    ("a pre's line break collapsed by white-space-collapse, which joins its two halves", ((_COPY_LINE, _COPY_LINE + f'<p style="white-space:pre;white-space-collapse:collapse;">{_UNDER}\n{_UNDER}</p>'),), _NO_WRAP),
    ("the spaces at a pre's start, which it keeps", ((_COPY_LINE, _COPY_LINE + f"<pre>          {'x' * 9}</pre>"),), _NO_WRAP),
    ("a phrase kept whole, past the threshold with its spaces", ((_COPY_LINE, _COPY_LINE + f'<p style="white-space:nowrap;">{_PHRASE}</p>'),), _NO_WRAP),
    ("white-space:collapse wrap after nowrap, which an engine before text-wrap-mode drops", ((_COPY_LINE, _COPY_LINE + f'<p style="white-space:nowrap;white-space:collapse wrap;">{_PHRASE}</p>'),), _NO_WRAP),
    ("a run across a table its align floats", ((_COPY_LINE, _COPY_LINE + f'<div>{_UNDER}<table align="left"><tr><td>y</td></tr></table>{_UNDER}</div>'),), _NOWHERE),
    ("a run across an object its align floats", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<object align="left" width="8" height="8"></object>{_UNDER}</p>'),), _NOWHERE),
    ("a run across an embed its align floats", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<embed src="https://e.test/x.png" type="image/png" align="left" width="8" height="8">{_UNDER}</p>'),), _NOWHERE),
    ("a run across an iframe its align floats", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<iframe align="left" width="8" height="8"></iframe>{_UNDER}</p>'),), _NOWHERE),
    ("a run across an input drawn as an image, its align floating it", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<input type="image" align="left" src="https://e.test/x.png" width="8">{_UNDER}</p>'),), _NOWHERE),
    ("float:revert-layer on an image its align floats, which keeps the attribute", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<img src="https://e.test/x.png" width="8" alt="" align="left" style="float:revert-layer;">{_UNDER}</p>'),), _NOWHERE),
    ("a run across a br set display:contents, which gives it no box", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<br style="display:contents;">{_UNDER}</p>'),), _NOWHERE),
    ("a run across an object's fallback text, its size set", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<object width="8" height="8">y</object>{_UNDER}</p>'),), _NOWHERE),
    ("a run across an object that holds a hidden span, which is fallback all the same", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<object width="8" height="8"><span style="display:none">y</span></object>{_UNDER}</p>'),), _NOWHERE),
    ("a run across an object that holds a comment, which is fallback", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<object width="8" height="8"><!-- c --></object>{_UNDER}</p>'),), _NOWHERE),
    ("a run across an object that holds a no-break space, which is no whitespace", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<object width="8" height="8">&nbsp;</object>{_UNDER}</p>'),), _NOWHERE),
    ("a lone wrap after nowrap, which an engine before text-wrap-mode drops", ((_COPY_LINE, _COPY_LINE + f'<p style="white-space:nowrap;white-space:wrap;">{_PHRASE}</p>'),), _NO_WRAP),
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
    ("white-space:normal after text-wrap-mode:nowrap, which it resets", ((_LINE_STYLE, _LINE_STYLE + "text-wrap-mode:nowrap;white-space:normal;"),), None),
    ("white-space:normal on the line, under a cell set text-wrap-mode:nowrap", ((_LINE_STYLE, _LINE_STYLE + "white-space:normal;"), (_BODY_CELL, _BODY_CELL + "text-wrap-mode:nowrap;")), None),
    ("a nowrap cell whose style reverts the attribute", ((_BODY_CELL, '<td nowrap style="white-space:revert;padding:32px 32px 0 32px;'),), None),
    ("a float beside a line, each under the threshold", ((_COPY_LINE, _COPY_LINE + f'<div><div style="float:left">{_UNDER}</div>{"y" * 10} {"y" * 10}</div>'),), None),
    ("a run of 17 characters with no rule", ((_COPY_LINE, _COPY_LINE + f"<p>{'x' * 17}</p>"),), None),
    ("a 16-character phrase kept whole, with spaces at its ends", ((_COPY_LINE, _COPY_LINE + '<p style="white-space:nowrap;">  Read the summary  </p>'),), None),
    ("two blocks side by side, each under the threshold", ((_COPY_LINE, _COPY_LINE + f"<p>{_UNDER}</p><p>{_UNDER}</p>"),), None),
    ("a block opened inside a line, each side under the threshold", ((_COPY_LINE, _COPY_LINE + f"<div>{_UNDER}<div>{_UNDER}</div></div>"),), None),
    ("a long run broken by a thin space", ((_COPY_LINE, _COPY_LINE + f"<p>{_UNDER}\u2009{_UNDER}</p>"),), None),
    ("a long run broken by an ogham space mark", ((_COPY_LINE, _COPY_LINE + f"<p>{_UNDER}\u1680{_UNDER}</p>"),), None),
    ("all:initial before the rule, which the rule overrides", ((_LINE_STYLE, "all:initial;" + _LINE_STYLE),), None),
    ("a long run the page hides", ((_COPY_LINE, _COPY_LINE + f'<div style="display:none">{"x" * 60}</div>'),), None),
    ("a long run under the hidden attribute", ((_COPY_LINE, _COPY_LINE + f"<div hidden>{'x' * 60}</div>"),), None),
    ("a long run in the head's title", (("</head>", f"<title>{'x' * 60}</title></head>"),), None),
    ("a long run inside Outlook's conditional comment", ((_COPY_LINE, _COPY_LINE + f"<!--[if mso]><p>{'x' * 60}</p><![endif]-->"),), None),
    ("a long run broken by a wbr", ((_COPY_LINE, _COPY_LINE + f"<p>{_UNDER}<wbr>{_UNDER}</p>"),), None),
    ("a long run broken by a zero-width space", ((_COPY_LINE, _COPY_LINE + f"<p>{_UNDER}\u200b{_UNDER}</p>"),), None),
    ("a pre whose lines are short", ((_COPY_LINE, _COPY_LINE + f"<pre>{_UNDER}\n{_UNDER}</pre>"),), None),
    ("a short phrase kept whole, its spaces collapsed", ((_COPY_LINE, _COPY_LINE + '<p style="white-space:nowrap;">Read            now</p>'),), None),
    ("two stretches either side of an inline SVG, which is placed whole", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<svg width="8" height="8"></svg>{_UNDER}</p>'),), None),
    ("two stretches either side of a br set float:left, which still breaks the line", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<br style="float:left">{_UNDER}</p>'),), None),
    ("two stretches either side of an input typed \" hidden\", which a browser shows", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<input type=" hidden" value="y">{_UNDER}</p>'),), None),
    ("two stretches either side of an image whose align is spaced, which no browser floats", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<img src="https://e.test/x.png" width="8" alt="" align=" left">{_UNDER}</p>'),), None),
    ("two stretches either side of a br set display:inline, which still breaks the line", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<br style="display:inline;">{_UNDER}</p>'),), None),
    ("two stretches either side of an object with no fallback, which is placed whole", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<object width="8" height="8"></object>{_UNDER}</p>'),), None),
    ("two stretches either side of an object that holds a param and whitespace alone", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<object width="8" height="8">\n  <param name="a" value="b">\n</object>{_UNDER}</p>'),), None),
    ("two stretches either side of an embed with a type and no source, which is placed whole", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<embed type="image/png" width="8" height="8">{_UNDER}</p>'),), None),
    ("two stretches either side of an embed with an empty source, which is placed whole", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<embed src="" width="8" height="8">{_UNDER}</p>'),), None),
]


@pytest.mark.parametrize("edits, expected", [case[1:] for case in LONG_RUNS], ids=[case[0] for case in LONG_RUNS])
def test_the_long_run_check_scores_every_planted_page(edits, expected):
    page = _planted(f"<p>Hi Ada,</p>{_COPY_LINE}")
    assert any(_TOKEN in run for run in long_runs(page)), "the planted page no longer prints its link as one run"
    problems = long_run_problems(_scored(page, edits))
    if expected is None:
        assert not problems, problems
    else:
        assert any(expected in problem for problem in problems), f"expected {expected!r}, got {problems}"


# A body that prints a plain long run, and each way the shell can lend it the rule in some engine, which on the
# panel would reach a body's own table and split its amounts, and the look-alikes that lend nothing.
_LENT_BODY = f"<p>{'x' * LONG_RUN}</p>"
LENDS = [
    # Lent.
    ("the panel lends overflow-wrap:anywhere", (("border-radius:16px;", "border-radius:16px;overflow-wrap:anywhere;"),), True),
    ("the panel lends word-wrap:anywhere, which Blink takes", (("border-radius:16px;", "border-radius:16px;word-wrap:anywhere;"),), True),
    ("the panel lends -webkit-line-break:anywhere, which WebKit may take (Blink drops it)", (("border-radius:16px;", "border-radius:16px;-webkit-line-break:anywhere;"),), True),
    ("the body's cell lends word-break:break-all", ((_BODY_CELL, _BODY_CELL + "word-break:break-all;"),), True),
    ("the panel's wrapper cell lends line-break:anywhere", (('<td align="center" style="padding:0 12px 24px 12px;">', '<td align="center" style="padding:0 12px 24px 12px;line-break:anywhere;">'),), True),
    ("the body lends word-break:break-word", (('<body style="', '<body style="word-break:break-word;'),), True),
    # Not lent.
    ("the shell as it is built", (), False),
    ("the panel lends overflow-wrap:break-word, which leaves a cell its narrowest width", (("border-radius:16px;", "border-radius:16px;overflow-wrap:break-word;"),), False),
    ("the panel lends word-break:keep-all", (("border-radius:16px;", "border-radius:16px;word-break:keep-all;"),), False),
    ("the panel lends the rule under all:initial, which resets it", (("border-radius:16px;", "border-radius:16px;overflow-wrap:anywhere;all:initial;"),), False),
]


@pytest.mark.parametrize("edits, lent", [case[1:] for case in LENDS], ids=[case[0] for case in LENDS])
def test_the_lent_rule_check_scores_every_planted_shell(edits, lent):
    runs = lent_runs(_scored(_planted(_LENT_BODY), edits))
    assert bool(runs) is lent, f"expected {'a lent rule' if lent else 'none'}, got {runs}"


# The shell's columns as the frozen copy writes them: each opens in Outlook's 600 px table, in a conditional
# comment, and the header, the panel and the footer line take the screen's width up to 600 px.
_OUTLOOK_TABLE = '<!--[if mso]><table role="presentation" width="600" align="center" cellpadding="0" cellspacing="0" border="0"><tr><td><![endif]-->'
_INDENT = "\n" + " " * 14
_HEADER_COLUMN = '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#F4F3EE" style="width:100%;'
_PANEL_COLUMN = '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="#FBFAF6" style="width:100%;'
_FOOTER_COLUMN = '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%;'
_PANEL_STYLE = 'style="width:100%;max-width:600px;background:#FBFAF6;'
_TOO_WIDE = "where its parent gives it"
_SQUEEZED = "squeezes the cell"
_NATURAL = "natural size"
_NO_ROOM = "leave its content no room"
_AT_CAP = "at its max-width"
_FIXED = "a fixed table layout keeps"
_BY_PARENT = "set by its parent, which"
_INSIDE = "phone: set box-sizing:border-box"  # the one remedy an image needs, its padding inside its width
_NOT_RESOLVED = "set by the font, the screen or its parent"
_BY_CONTENT = "set by its content"
_NO_OUTLOOK_TABLE = "sits in no table 600 px wide"
_BODY_LINE = "<p>Copy this link"
_IMAGE = 'src="https://e.test/x.png" alt=""'
_BARE_TABLE = '<table width="100%" cellpadding="0" cellspacing="0"'  # a body table that adds no padding or spacing
_FIXED_TABLE = _BARE_TABLE + ' style="table-layout:fixed;"'
_PNG = 'data="https://e.test/x.png" type="image/png"'
_IN_A_ROW = "in a row in their borders and padding alone"
_OVER_THE_WHOLE = "keep it to 100% or less"
# A body whose own lines fit the narrowest phone, so a planted page that holds fits in Chromium too.
_WIDTH_BODY = "<p>Hi Ada,</p><p>Copy this link to reset your password.</p>"
_PANEL_OUTLOOK = _OUTLOOK_TABLE + _INDENT + _PANEL_COLUMN
# Each way a page can set a box wider than its room on a phone, or leave classic Outlook a column it stretches,
# as edits of the shell's page, and the look-alikes that hold.
WIDTHS = [
    # Flagged.
    ("the panel set 600 px wide in its style", ((_PANEL_STYLE, _PANEL_STYLE.replace("width:100%;", "width:600px;")),), _TOO_WIDE),
    ("the panel's width attribute at 600, its style's width dropped", ((_PANEL_COLUMN, _PANEL_COLUMN.replace('width="100%"', 'width="600"').replace("width:100%;", "")),), _TOO_WIDE),
    ("the header given a min-width of 600 px", ((_HEADER_STYLE, _HEADER_STYLE.replace("max-width:600px;", "max-width:600px;min-width:600px;")),), _TOO_WIDE),
    ("the footer line's Outlook table shown to every client", ((_OUTLOOK_TABLE + _INDENT + _FOOTER_COLUMN, _OUTLOOK_TABLE[len("<!--[if mso]>") : -len("<![endif]-->")] + _INDENT + _FOOTER_COLUMN),), _TOO_WIDE),
    ("a body table 400 px wide", ((_BODY_LINE, '<table width="400"><tr><td>x</td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a width with spaces before its number", ((_BODY_LINE, '<table width=" 400"><tr><td>x</td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a width in points", ((_BODY_LINE, '<table style="width:450pt"><tr><td>x</td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a body image 560 px wide", ((_BODY_LINE, f'<img {_IMAGE} width="560">' + _BODY_LINE),), _TOO_WIDE),
    ("an image a pixel wider than the column", ((_BODY_LINE, f'<img {_IMAGE} width="{WIDEST_FIXED + 1}">' + _BODY_LINE),), _TOO_WIDE),
    ("an image with no width, at its natural size", ((_BODY_LINE, f"<img {_IMAGE}>" + _BODY_LINE),), _NATURAL),
    ("a fixed width an em cap does not hold", ((_BODY_LINE, f'<img {_IMAGE} width="560" style="max-width:30em">' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table a percentage max-width does not hold in a cell", ((_BODY_LINE, '<table width="560" style="max-width:100%;"><tr><td>x</td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed block a percentage max-width does not hold in a cell", ((_BODY_LINE, '<div style="width:560px;max-width:100%;">x</div>' + _BODY_LINE),), _TOO_WIDE),
    ("a table set wider than its room in percent", ((_BODY_LINE, '<table width="150%"><tr><td>x</td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a min-width over its room", ((_BODY_LINE, '<div style="min-width:150%;">x</div>' + _BODY_LINE),), _TOO_WIDE),
    ("a full-width block with side padding", ((_BODY_LINE, '<div style="width:100%;padding:0 40px;">x</div>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed block with side padding", ((_BODY_LINE, '<div style="width:230px;padding:0 16px;">x</div>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table in a padded block", ((_BODY_LINE, '<div style="padding:0 20px;"><table width="220"><tr><td>x</td></tr></table></div>' + _BODY_LINE),), _TOO_WIDE),
    ("an image in a cell its table pads", ((_BODY_LINE, f'<table width="100%" cellpadding="8" cellspacing="0"><tr><td><img {_IMAGE} width="220"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("an image as wide as the column in a cell, which its 1 px padding narrows", ((_BODY_LINE, f'<table width="100%" cellspacing="0"><tr><td><img {_IMAGE} width="{WIDEST_FIXED}"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("an image in a list's indent", ((_BODY_LINE, f'<ul><li><img {_IMAGE} width="220"></li></ul>' + _BODY_LINE),), _TOO_WIDE),
    ("an image in a blockquote's margins", ((_BODY_LINE, f'<blockquote><img {_IMAGE} width="200"></blockquote>' + _BODY_LINE),), _TOO_WIDE),
    ("an image with a side margin", ((_BODY_LINE, f'<img {_IMAGE} width="230" style="margin-left:24px;">' + _BODY_LINE),), _TOO_WIDE),
    ("a margin wider than the column", ((_BODY_LINE, '<div style="margin-left:250px;">x</div>' + _BODY_LINE),), _NO_ROOM),
    ("a negative margin", ((_BODY_LINE, '<div style="margin-right:-40px;">x</div>' + _BODY_LINE),), "is negative"),
    ("an image its max-width holds, padded beside it", ((_BODY_LINE, f'<img {_IMAGE} style="max-width:100%;padding:0 30px;">' + _BODY_LINE),), _INSIDE),
    ("an image its max-width holds, with a side margin", ((_BODY_LINE, f'<img {_IMAGE} style="max-width:100%;margin-left:60px;">' + _BODY_LINE),), _AT_CAP),
    ("an image its max-width holds, with a side margin and padding, which needs both remedies", ((_BODY_LINE, f'<img {_IMAGE} style="max-width:100%;margin-left:60px;padding:0 30px;">' + _BODY_LINE),), "drop its side margins, and set box-sizing"),
    ("an image held to half the room, with a side margin and padding, which either remedy fits", ((_BODY_LINE, f'<img {_IMAGE} style="max-width:50%;margin-left:60px;padding:0 30px;">' + _BODY_LINE),), "drop its side margins, or set box-sizing"),
    ("an image with a width its max-width holds, padded beside it", ((_BODY_LINE, f'<img {_IMAGE} width="600" style="max-width:100%;padding:0 30px;">' + _BODY_LINE),), _INSIDE),
    ("an image's hspace, which sets its side margins", ((_BODY_LINE, f'<img {_IMAGE} width="220" hspace="10">' + _BODY_LINE),), _TOO_WIDE),
    ("an image's border attribute, which draws a border", ((_BODY_LINE, f'<img {_IMAGE} width="226" border="4">' + _BODY_LINE),), _TOO_WIDE),
    ("an object 300 px wide", ((_BODY_LINE, '<object width="300"></object>' + _BODY_LINE),), _TOO_WIDE),
    ("a div set display:table, which adds its padding to its width", ((_BODY_LINE, '<div style="display:table;width:230px;padding:0 10px;">x</div>' + _BODY_LINE),), _TOO_WIDE),
    ("a table whose style reverts its spacing to a browser's 2 px", ((_BODY_LINE, f'<table width="100%" cellspacing="0" style="border-spacing:revert;"><tr><td style="padding:0;"><img {_IMAGE} width="230"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a table's border-spacing taken from its parent, which the check does not resolve", ((_BODY_LINE, '<table width="100%" style="border-spacing:inherit;"><tr><td>x</td></tr></table>' + _BODY_LINE),), _BY_PARENT),
    ("a margin in em, which the font sets", ((_BODY_LINE, '<div style="margin-left:2em;">x</div>' + _BODY_LINE),), _NOT_RESOLVED),
    ("a full-width cell whose padding is wider than its table", ((_BODY_LINE, '<table width="100%" cellpadding="0" cellspacing="0"><tr><td width="100%" style="padding:0 150px;">x</td></tr></table>' + _BODY_LINE),), "padding alone take"),
    ("a cell set over 100% of its table", ((_BODY_LINE, '<table width="100%" cellspacing="0"><tr><td width="150%">x</td></tr></table>' + _BODY_LINE),), "keep it to 100% or less"),
    ("a body cell 300 px wide", ((_BODY_LINE, '<table width="100%"><tr><td width="300">x</td></tr></table>' + _BODY_LINE),), _SQUEEZED),
    ("a body column 300 px wide", ((_BODY_LINE, '<table width="100%"><col width="300"><tr><td>x</td></tr></table>' + _BODY_LINE),), "squeezes the column"),
    ("a cell 300 px wide in a fixed table layout", ((_BODY_LINE, '<table width="100%" style="table-layout:fixed;"><tr><td width="300">x</td></tr></table>' + _BODY_LINE),), _FIXED),
    ("a column 300 px wide in a fixed table layout", ((_BODY_LINE, '<table width="100%" style="table-layout:fixed;"><col width="300"><tr><td>x</td></tr></table>' + _BODY_LINE),), _FIXED),
    ("a cell 300 px wide under table-layout:fixed in a table with no width, which lays out automatically", ((_BODY_LINE, '<table style="table-layout:fixed;"><tr><td width="300">x</td></tr></table>' + _BODY_LINE),), _SQUEEZED),
    ("a width in em, which the font sets", ((_BODY_LINE, '<table style="width:40em"><tr><td>x</td></tr></table>' + _BODY_LINE),), _NOT_RESOLVED),
    ("a width its parent sets", ((_BODY_LINE, '<table style="width:inherit"><tr><td>x</td></tr></table>' + _BODY_LINE),), _NOT_RESOLVED),
    ("a width its content sets", ((_BODY_LINE, '<p style="width:max-content;">x</p>' + _BODY_LINE),), _BY_CONTENT),
    ("a width through calc()", ((_BODY_LINE, '<table style="width:calc(100% + 20px)"><tr><td>x</td></tr></table>' + _BODY_LINE),), "takes its value from a function"),
    ("revert-layer on a table's width, which keeps its attribute", ((_BODY_LINE, '<table width="600" style="width:revert-layer;"><tr><td>x</td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a checkbox as wide as the column, which its own side margins widen", ((_BODY_LINE, '<input type="checkbox" style="width:230px;">' + _BODY_LINE),), _TOO_WIDE),
    ("a radio button a pixel past the column with its own side margins, 5 px and 3 px", ((_BODY_LINE, '<input type="radio" style="width:223px;">' + _BODY_LINE),), _TOO_WIDE),
    ("an iframe whose own 2 px border takes it past the column", ((_BODY_LINE, '<iframe width="228" height="20"></iframe>' + _BODY_LINE),), _TOO_WIDE),
    ("a text input whose width leaves out its padding and border", ((_BODY_LINE, '<input type="text" style="width:230px;padding:0 10px;">' + _BODY_LINE),), _TOO_WIDE),
    ("an image's hspace in percent, a length of the room", ((_BODY_LINE, f'<img {_IMAGE} width="210" hspace="5%">' + _BODY_LINE),), _TOO_WIDE),
    ("an image's border of 5%, which HTML reads as 5 px", ((_BODY_LINE, f'<img {_IMAGE} width="222" border="5%">' + _BODY_LINE),), _TOO_WIDE),
    ("a cellpadding of 5%, which HTML reads as 5 px", ((_BODY_LINE, f'<table width="100%" cellpadding="5%" cellspacing="0"><tr><td><img {_IMAGE} width="225"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("an object's hspace, which sets its side margins", ((_BODY_LINE, '<object width="210" height="10" hspace="11"></object>' + _BODY_LINE),), _TOO_WIDE),
    ("an object's border attribute, which draws a border", ((_BODY_LINE, '<object width="226" height="10" border="4"></object>' + _BODY_LINE),), _TOO_WIDE),
    ("an embed's hspace, which sets its side margins", ((_BODY_LINE, '<embed src="https://e.test/x.png" type="image/png" width="210" height="10" hspace="11">' + _BODY_LINE),), _TOO_WIDE),
    ("an embed with a type and no source, which makes a box", ((_BODY_LINE, '<embed type="image/png" width="300" height="10">' + _BODY_LINE),), _TOO_WIDE),
    ("an embed with an empty source, which makes a box", ((_BODY_LINE, '<embed src="" width="300" height="10">' + _BODY_LINE),), _TOO_WIDE),
    ("an object whose data may load, though it holds fallback", ((_BODY_LINE, f'<object {_PNG} width="300" height="10">fallback</object>' + _BODY_LINE),), _TOO_WIDE),
    ("an object whose type may load, though it holds fallback", ((_BODY_LINE, '<object type="image/png" width="300" height="10">fallback</object>' + _BODY_LINE),), _TOO_WIDE),
    ("an object that holds a param alone, which is no fallback", ((_BODY_LINE, '<object width="300" height="10"><param name="a" value="b"></object>' + _BODY_LINE),), _TOO_WIDE),
    ("an image held at the column by its max-width, its border past it", ((_BODY_LINE, f'<img {_IMAGE} width="230" style="max-width:100%;border:1px solid #ccc;">' + _BODY_LINE),), _TOO_WIDE),
    ("revert-layer on a cell's padding, which keeps its table's cellpadding", ((_BODY_LINE, f'<table width="100%" cellpadding="20" cellspacing="0"><tr><td style="padding:revert-layer;"><img {_IMAGE} width="230"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a cell's min-width past its share", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td width="50%" style="min-width:300px;">x</td><td>y</td></tr></table>' + _BODY_LINE),), "its min-width holds it"),
    ("a table's border-spacing in em, which the font sets", ((_BODY_LINE, '<table width="100%" style="border-spacing:1em;"><tr><td>x</td></tr></table>' + _BODY_LINE),), "border-spacing is set by the font or the screen"),
    ("two cells set in percent whose padding takes the row past the table", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td width="50%" style="padding:0 60px;">a</td><td width="50%" style="padding:0 60px;">b</td></tr></table>' + _BODY_LINE),), _IN_A_ROW),
    ("two cells whose padding takes the row past the table", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td style="padding:0 60px;">a</td><td style="padding:0 60px;">b</td></tr></table>' + _BODY_LINE),), _IN_A_ROW),
    ("two images side by side in cells of half the table", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td width="50%"><img {_IMAGE} width="200"></td><td width="50%"><img {_IMAGE} width="200"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("three cells of 100 px in a fixed table layout", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td width="100">a</td><td width="100">b</td><td width="100">c</td></tr></table>' + _BODY_LINE),), _FIXED),
    ("two columns of 150 px in a fixed table layout", ((_BODY_LINE, f'{_FIXED_TABLE}><col width="150"><col width="150"><tr><td>a</td><td>b</td></tr></table>' + _BODY_LINE),), _FIXED),
    ("a column group of two 150 px columns in a fixed table layout", ((_BODY_LINE, f'{_FIXED_TABLE}><colgroup span="2" width="150"></colgroup><tr><td>a</td><td>b</td></tr></table>' + _BODY_LINE),), _FIXED),
    ("a column spanning two at 150 px in a fixed table layout", ((_BODY_LINE, f'{_FIXED_TABLE}><col span="2" width="150"><tr><td>a</td><td>b</td></tr></table>' + _BODY_LINE),), _FIXED),
    ("two padded cells of 100 px in a fixed table layout, their padding added", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td width="100" style="padding:0 10px;">a</td><td width="100" style="padding:0 10px;">b</td></tr></table>' + _BODY_LINE),), _FIXED),
    ("a column as wide as the table in a fixed table layout, past it with the spacing", ((_BODY_LINE, '<table width="100%" cellpadding="0" style="table-layout:fixed;"><col width="228"><tr><td>a</td></tr></table>' + _BODY_LINE),), _FIXED),
    ("a cell spanning two at 300 px in a fixed table layout", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td colspan="2" width="300">a</td></tr><tr><td>b</td><td>c</td></tr></table>' + _BODY_LINE),), _FIXED),
    ("a fixed table layout's hidden first row, the next setting 300 px", ((_BODY_LINE, f'{_FIXED_TABLE}><tr style="display:none"><td>a</td></tr><tr><td width="300">b</td></tr></table>' + _BODY_LINE),), _FIXED),
    ("a fixed table layout's footer written first, the body's row setting 300 px", ((_BODY_LINE, f'{_FIXED_TABLE}><tfoot><tr><td>f</td></tr></tfoot><tbody><tr><td width="300">b</td></tr></tbody></table>' + _BODY_LINE),), _FIXED),
    ("a fixed table layout's header written last, its row setting 300 px", ((_BODY_LINE, f'{_FIXED_TABLE}><tbody><tr><td>b</td></tr></tbody><thead><tr><td width="300">h</td></tr></thead></table>' + _BODY_LINE),), _FIXED),
    ("a fixed table layout's column of 50 px beside one that sets none, which takes the rest", ((_BODY_LINE, f'{_FIXED_TABLE}><col width="50"><col><tr><td><img {_IMAGE} width="100"></td><td>y</td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's column in percent beside one in px, which takes the room left", ((_BODY_LINE, f'{_FIXED_TABLE}><col width="50"><col width="25%"><tr><td>y</td><td><img {_IMAGE} width="100"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's columns in px sharing the room left by their widths", ((_BODY_LINE, f'{_FIXED_TABLE}><col width="50"><col width="50"><col width="100"><tr><td>a</td><td>b</td><td><img {_IMAGE} width="116"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's percentage, of the table less its spacing", ((_BODY_LINE, f'<table width="100%" cellpadding="0" cellspacing="10" style="table-layout:fixed;"><col width="50%"><col><tr><td><img {_IMAGE} width="101"></td><td>y</td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a cell set over 100% in a fixed table layout", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td width="150%">a</td></tr></table>' + _BODY_LINE),), _OVER_THE_WHOLE),
    ("a column set over 100% in a fixed table layout", ((_BODY_LINE, f'{_FIXED_TABLE}><col style="width:120%;"><tr><td>x</td></tr></table>' + _BODY_LINE),), _OVER_THE_WHOLE),
    ("the panel without its Outlook table", ((_PANEL_OUTLOOK, _PANEL_COLUMN),), _NO_OUTLOOK_TABLE),
    ("the header's Outlook table at 640 px", ((_OUTLOOK_TABLE + _INDENT + _HEADER_COLUMN, _OUTLOOK_TABLE.replace('width="600"', 'width="640"') + _INDENT + _HEADER_COLUMN),), _NO_OUTLOOK_TABLE),
    ("the footer line's Outlook table in a block Outlook skips", ((_OUTLOOK_TABLE + _INDENT + _FOOTER_COLUMN, "<!--[if !mso]><!-->" + _OUTLOOK_TABLE[len("<!--[if mso]>") : -len("<![endif]-->")] + "<!--<![endif]-->" + _INDENT + _FOOTER_COLUMN),), _NO_OUTLOOK_TABLE),
    ("the panel's Outlook table for Outlook before 2007 alone", ((_PANEL_OUTLOOK, _OUTLOOK_TABLE.replace("[if mso]", "[if lt mso 12]") + _INDENT + _PANEL_COLUMN),), _NO_OUTLOOK_TABLE),
    ("the panel's Outlook table for Internet Explorer outside Outlook", ((_PANEL_OUTLOOK, _OUTLOOK_TABLE.replace("[if mso]", "[if (!mso)&(IE)]") + _INDENT + _PANEL_COLUMN),), _NO_OUTLOOK_TABLE),
    ("the panel's Outlook table in a revealed block Outlook skips", ((_PANEL_OUTLOOK, "<![if !mso]>" + _OUTLOOK_TABLE[len("<!--[if mso]>") : -len("<![endif]-->")] + "<![endif]>" + _INDENT + _PANEL_COLUMN),), _NO_OUTLOOK_TABLE),
    ("the panel's Outlook table under a condition the reader cannot parse", ((_PANEL_OUTLOOK, _OUTLOOK_TABLE.replace("[if mso]", "[if mso &]") + _INDENT + _PANEL_COLUMN),), _NO_OUTLOOK_TABLE),
    # Pass.
    ("the shell as it is built", (), None),
    ("a fixed image held to the screen by its max-width", ((_BODY_LINE, f'<img {_IMAGE} width="560" style="max-width:100%;height:auto;">' + _BODY_LINE),), None),
    ("an image with no width held to the screen by its max-width", ((_BODY_LINE, f'<img {_IMAGE} style="max-width:100%;">' + _BODY_LINE),), None),
    ("an image as wide as the narrowest phone's text column", ((_BODY_LINE, f'<img {_IMAGE} width="{WIDEST_FIXED}">' + _BODY_LINE),), None),
    ("an image in a blockquote that fits within its margins", ((_BODY_LINE, f'<blockquote><img {_IMAGE} width="150"></blockquote>' + _BODY_LINE),), None),
    ("a fixed block whose width holds its padding", ((_BODY_LINE, '<div style="box-sizing:border-box;width:230px;padding:0 16px;">x</div>' + _BODY_LINE),), None),
    ("a table set in percent", ((_BODY_LINE, '<table width="80%"><tr><td>x</td></tr></table>' + _BODY_LINE),), None),
    ("a cell set in percent", ((_BODY_LINE, '<table width="100%"><tr><td width="50%">x</td><td>y</td></tr></table>' + _BODY_LINE),), None),
    ("columns set in percent in a fixed table layout", ((_BODY_LINE, '<table width="100%" style="table-layout:fixed;"><col width="50%"><col width="50%"><tr><td>x</td><td>y</td></tr></table>' + _BODY_LINE),), None),
    ("a full-width cell with side padding, which its share of the table holds", ((_BODY_LINE, '<table width="100%" cellpadding="0" cellspacing="0"><tr><td width="100%" style="padding:0 16px;">x</td></tr></table>' + _BODY_LINE),), None),
    ("a full-width cell its table pads", ((_BODY_LINE, '<table width="100%" cellpadding="16" cellspacing="0"><tr><td width="100%">x</td></tr></table>' + _BODY_LINE),), None),
    ("a button whose width holds its padding, as a browser sizes one", ((_BODY_LINE, '<button style="width:230px;padding:0 20px;">x</button>' + _BODY_LINE),), None),
    ("a cell whose style reverts its table's cellpadding", ((_BODY_LINE, f'<table width="100%" cellpadding="20" cellspacing="0"><tr><td style="padding:revert;"><img {_IMAGE} width="230"></td></tr></table>' + _BODY_LINE),), None),
    ("a table whose style sets its spacing to its initial 0 over its cellspacing", ((_BODY_LINE, f'<table width="100%" cellspacing="4" style="border-spacing:initial;"><tr><td style="padding:0;"><img {_IMAGE} width="{WIDEST_FIXED}"></td></tr></table>' + _BODY_LINE),), None),
    ("a border whose colour a function gives", ((_BODY_LINE, '<div style="border:1px solid rgba(0,0,0,0.1);">x</div>' + _BODY_LINE),), None),
    ("a table whose style reverts its width attribute", ((_BODY_LINE, '<table width="600" style="width:revert;"><tr><td>x</td></tr></table>' + _BODY_LINE),), None),
    ("a width attribute on a div, which HTML maps to nothing", ((_BODY_LINE, '<div width="600">x</div>' + _BODY_LINE),), None),
    ("a width on an inline span, which takes none", ((_BODY_LINE, '<span style="width:300px;">x</span>' + _BODY_LINE),), None),
    ("a fixed width inside Outlook's conditional comment", ((_BODY_LINE, '<!--[if mso]><table width="560"><tr><td><![endif]-->x<!--[if mso]></td></tr></table><![endif]-->' + _BODY_LINE),), None),
    ("a fixed width the page hides", ((_BODY_LINE, '<div style="display:none"><table width="600"><tr><td>x</td></tr></table></div>' + _BODY_LINE),), None),
    ("a body table capped at 500 px that takes the screen's width", ((_BODY_LINE, '<table width="100%" style="max-width:500px;"><tr><td>x</td></tr></table>' + _BODY_LINE),), None),
    ("a body table in the shell's own fluid form, inside the panel's Outlook table", ((_BODY_LINE, '<table width="100%" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;"><tr><td>x</td></tr></table>' + _BODY_LINE),), None),
    ("the panel's Outlook table written for Outlook 2000 and later", ((_PANEL_OUTLOOK, _OUTLOOK_TABLE.replace("[if mso]", "[if gte mso 9]") + _INDENT + _PANEL_COLUMN),), None),
    ("the panel's Outlook table for Outlook or Internet Explorer", ((_PANEL_OUTLOOK, _OUTLOOK_TABLE.replace("[if mso]", "[if (gte mso 9)|(IE)]") + _INDENT + _PANEL_COLUMN),), None),
    ("a checkbox that fits with its own side margins", ((_BODY_LINE, '<input type="checkbox" style="width:222px;">' + _BODY_LINE),), None),
    ("a radio button that fits with its own side margins", ((_BODY_LINE, '<input type="radio" style="width:221px;">' + _BODY_LINE),), None),
    ("an iframe that fits with its own 2 px border", ((_BODY_LINE, '<iframe width="226" height="20"></iframe>' + _BODY_LINE),), None),
    ("an iframe's hspace, which sets no margins", ((_BODY_LINE, '<iframe width="210" height="20" hspace="11"></iframe>' + _BODY_LINE),), None),
    ("a colour well whose width holds its padding, as a browser sizes one", ((_BODY_LINE, '<input type="color" style="width:230px;padding:0 10px;">' + _BODY_LINE),), None),
    ("a search field whose width holds its padding, as a browser sizes one", ((_BODY_LINE, '<input type="search" style="width:230px;padding:0 10px;">' + _BODY_LINE),), None),
    ("a select whose width holds its padding, as a browser sizes one", ((_BODY_LINE, '<select style="width:230px;padding:0 10px;"><option>x</option></select>' + _BODY_LINE),), None),
    ("a meter whose width holds its padding, as a browser sizes one", ((_BODY_LINE, '<meter value="0.5" style="width:230px;padding:0 10px;"></meter>' + _BODY_LINE),), None),
    ("a progress bar whose width holds its padding, as a browser sizes one", ((_BODY_LINE, '<progress value="0.5" style="width:230px;padding:0 10px;"></progress>' + _BODY_LINE),), None),
    ("a submit input whose width holds its padding, as a browser sizes one", ((_BODY_LINE, '<input type="submit" value="Go" style="width:230px;padding:0 10px;">' + _BODY_LINE),), None),
    ("a reset input whose width holds its padding, as a browser sizes one", ((_BODY_LINE, '<input type="reset" value="Go" style="width:230px;padding:0 10px;">' + _BODY_LINE),), None),
    ("a button input whose width holds its padding, as a browser sizes one", ((_BODY_LINE, '<input type="button" value="Go" style="width:230px;padding:0 10px;">' + _BODY_LINE),), None),
    ("an embed with neither a source nor a type, which lays out nothing", ((_BODY_LINE, '<embed width="300" height="10">' + _BODY_LINE),), None),
    ("an object with an empty data, which shows its fallback", ((_BODY_LINE, '<object data="" width="300" height="10">fallback</object>' + _BODY_LINE),), None),
    ("an object that holds a comment, which a browser shows as its fallback", ((_BODY_LINE, '<object width="300" height="10"><!-- c --></object>' + _BODY_LINE),), None),
    ("an image's hspace in percent that fits", ((_BODY_LINE, f'<img {_IMAGE} width="200" hspace="5%">' + _BODY_LINE),), None),
    ("an image's border of 5% that fits as 5 px", ((_BODY_LINE, f'<img {_IMAGE} width="220" border="5%">' + _BODY_LINE),), None),
    ("a cellpadding of 5% that fits as 5 px", ((_BODY_LINE, f'<table width="100%" cellpadding="5%" cellspacing="0"><tr><td><img {_IMAGE} width="220"></td></tr></table>' + _BODY_LINE),), None),
    ("a table whose style reverts its box-sizing to a browser's border-box", ((_BODY_LINE, '<table width="100%" style="box-sizing:revert;padding:0 10px;"><tr><td>x</td></tr></table>' + _BODY_LINE),), None),
    ("an image held to the room by its max-width, its padding inside it", ((_BODY_LINE, f'<img {_IMAGE} style="max-width:100%;box-sizing:border-box;padding:0 30px;">' + _BODY_LINE),), None),
    ("three cells of 100 px in an automatic table layout, which narrows them", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td width="100">a</td><td width="100">b</td><td width="100">c</td></tr></table>' + _BODY_LINE),), None),
    ("two cells set in percent whose padding fits the row", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td width="50%" style="padding:0 50px;">a</td><td width="50%" style="padding:0 50px;">b</td></tr></table>' + _BODY_LINE),), None),
    ("a lone cell of half the table, which takes the whole", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td width="50%"><img {_IMAGE} width="200"></td></tr></table>' + _BODY_LINE),), None),
    ("a cell spanning two with side padding, over a row of two", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td colspan="2" width="100%" style="padding:0 16px;">a</td></tr><tr><td>b</td><td>c</td></tr></table>' + _BODY_LINE),), None),
    ("two cells of 112 px whose table's border attribute borders them", ((_BODY_LINE, '<table width="100%" cellpadding="0" cellspacing="0" border="1"><tr><td width="112">a</td><td width="112">b</td></tr></table>' + _BODY_LINE),), None),
    ("a hidden row of padded cells in an automatic table layout", ((_BODY_LINE, f'{_BARE_TABLE}><tr style="display:none"><td style="padding:0 60px;">a</td><td style="padding:0 60px;">b</td></tr><tr><td>c</td><td>d</td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's second row setting 300 px, which it does not read", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td>a</td></tr><tr><td width="300">b</td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's columns holding their padded cells", ((_BODY_LINE, f'{_FIXED_TABLE}><col width="110"><col width="110"><tr><td style="padding:0 10px;">a</td><td style="padding:0 10px;">b</td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's two cells of 100 px and one that sets none", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td width="100">a</td><td width="100">b</td><td>c</td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's two cells of half the table, padded inside their share", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td width="50%" style="padding:0 60px;">a</td><td width="50%" style="padding:0 60px;">b</td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's hidden first row setting 300 px", ((_BODY_LINE, f'{_FIXED_TABLE}><tr style="display:none"><td width="300">a</td></tr><tr><td>b</td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's first row under the hidden attribute, setting 300 px", ((_BODY_LINE, f'{_FIXED_TABLE}><tr hidden><td width="300">a</td></tr><tr><td>b</td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's hidden first body setting 300 px", ((_BODY_LINE, f'{_FIXED_TABLE}><tbody style="display:none"><tr><td width="300">a</td></tr></tbody><tbody><tr><td>b</td></tr></tbody></table>' + _BODY_LINE),), None),
    ("a fixed table layout's hidden column of 300 px", ((_BODY_LINE, f'{_FIXED_TABLE}><col width="300" style="display:none"><tr><td>a</td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's footer written first, setting 300 px", ((_BODY_LINE, f'{_FIXED_TABLE}><tfoot><tr><td width="300">f</td></tr></tfoot><tbody><tr><td>b</td></tr></tbody></table>' + _BODY_LINE),), None),
    ("a fixed table layout's second header setting 300 px, which lays out as a body", ((_BODY_LINE, f'{_FIXED_TABLE}><thead><tr><td>h</td></tr></thead><thead><tr><td width="300">h2</td></tr></thead></table>' + _BODY_LINE),), None),
    ("a fixed table layout's lone column of half the table, which takes the whole", ((_BODY_LINE, f'{_FIXED_TABLE}><col width="50%"><tr><td><img {_IMAGE} width="200"></td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's two columns of 50 px, which share the room left", ((_BODY_LINE, f'{_FIXED_TABLE}><col width="50"><col width="50"><tr><td><img {_IMAGE} width="100"></td><td>y</td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's column in px beside one in percent, which takes the room left", ((_BODY_LINE, f'{_FIXED_TABLE}><col width="50"><col width="25%"><tr><td><img {_IMAGE} width="100"></td><td>y</td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's columns in px that share the room left by their widths", ((_BODY_LINE, f'{_FIXED_TABLE}><col width="50"><col width="50"><col width="100"><tr><td>a</td><td>b</td><td><img {_IMAGE} width="112"></td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's column in percent beside a wide one in px, which gives way", ((_BODY_LINE, f'{_FIXED_TABLE}><col width="50%"><col width="200"><tr><td>a</td><td>b</td></tr></table>' + _BODY_LINE),), None),
]


@pytest.mark.parametrize("edits, expected", [case[1:] for case in WIDTHS], ids=[case[0] for case in WIDTHS])
def test_the_width_checks_score_every_planted_page(edits, expected):
    page = _scored(_planted(_WIDTH_BODY), edits)
    problems = fixed_width_problems(page) + outlook_width_problems(page)
    if expected is None:
        assert not problems, problems
    else:
        assert any(expected in problem for problem in problems), f"expected {expected!r}, got {problems}"


# A body that prints a table of amounts, and each way it can lend the break rule to the table, where it splits the
# amounts in some engine, and the look-alikes that keep the rule to a line or a cell of its own.
_AMOUNTS = '<table width="100%" cellpadding="0" cellspacing="0"><tr><td>Revenue</td><td>$394,328,000,000</td></tr></table>'
REACHES = [
    # Reached.
    ("the rule on a block around the table", ((_BODY_LINE, f'<div style="{_BREAK}">{_AMOUNTS}</div>' + _BODY_LINE),), True),
    ("the rule on the table", ((_BODY_LINE, _AMOUNTS.replace('cellspacing="0">', f'cellspacing="0" style="{_BREAK}">') + _BODY_LINE),), True),
    ("the rule on a row", ((_BODY_LINE, _AMOUNTS.replace("<tr>", f'<tr style="{_BREAK}">') + _BODY_LINE),), True),
    ("the rule on the panel's body cell", ((_BODY_CELL, _BODY_CELL + _BREAK), (_BODY_LINE, _AMOUNTS + _BODY_LINE)), True),
    ("word-wrap:anywhere on a block around the table, which Blink takes", ((_BODY_LINE, f'<div style="word-wrap:anywhere;">{_AMOUNTS}</div>' + _BODY_LINE),), True),
    ("-webkit-line-break:anywhere on a block around the table, which WebKit may take", ((_BODY_LINE, f'<div style="-webkit-line-break:anywhere;">{_AMOUNTS}</div>' + _BODY_LINE),), True),
    # Not reached.
    ("the table as a body prints it", ((_BODY_LINE, _AMOUNTS + _BODY_LINE),), False),
    ("the rule on a line beside the table", ((_BODY_LINE, f'<p style="{_BREAK}">x</p>{_AMOUNTS}' + _BODY_LINE),), False),
    ("the rule on a cell of its own", ((_BODY_LINE, _AMOUNTS.replace("<td>Revenue", f'<td style="{_BREAK}">Revenue') + _BODY_LINE),), False),
    ("a block's rule reset on the table", ((_BODY_LINE, f'<div style="{_BREAK}">' + _AMOUNTS.replace('cellspacing="0">', f'cellspacing="0" style="{_RESET}">') + "</div>" + _BODY_LINE),), False),
]


@pytest.mark.parametrize("edits, reached", [case[1:] for case in REACHES], ids=[case[0] for case in REACHES])
def test_the_reach_check_scores_every_planted_page(edits, reached):
    problems = reach_problems(_scored(_planted(_WIDTH_BODY), edits))
    assert bool(problems) is reached, f"expected {'a table the rule reaches' if reached else 'none'}, got {problems}"


# Each way a page can set a viewport other than the shell's, and the look-alikes that set the same.
_SHELL_VIEWPORT = f'<meta name="viewport" content="{_DEVICE_WIDTH}">'
VIEWPORTS = [
    # Another viewport.
    ("a body's own viewport at 600 px", ((_BODY_LINE, '<meta name="viewport" content="width=600">' + _BODY_LINE),), False),
    ("the shell's viewport at 600 px", ((_SHELL_VIEWPORT, '<meta name="viewport" content="width=600">'),), False),
    ("the shell's viewport dropped", ((_SHELL_VIEWPORT, ""),), False),
    # The shell's.
    ("the shell as it is built", (), True),
    ("the shell's viewport spaced otherwise", ((_SHELL_VIEWPORT, '<meta name="viewport" content="width=device-width,initial-scale=1">'),), True),
    ("the shell's viewport named in capitals", ((_SHELL_VIEWPORT, f'<META NAME="Viewport" CONTENT="{_DEVICE_WIDTH}">'),), True),
]


@pytest.mark.parametrize("edits, shells", [case[1:] for case in VIEWPORTS], ids=[case[0] for case in VIEWPORTS])
def test_the_viewport_check_scores_every_planted_page(edits, shells):
    sets = viewports(_scored(_planted(_WIDTH_BODY), edits))
    assert (sets == [_DEVICE_WIDTH]) is shells, f"expected {'the shell viewport alone' if shells else 'another'}, got {sets}"
