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

- opens ``<body>`` with the mail's preheader, once, hidden from the view and from classic Outlook's, so an
  inbox lists the mail by its own line and not by the header's words (``test_mail_rendered_addresses.py``
  holds every page sent to the line's rules);
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
  view, the panel's and the footer line's (a text zoom scales every line, the header's too: F26);
- breaks no run of a body's for it: a line that prints a run with nowhere to break, such as a link with
  its token or the reader's name, carries the rule that lets it break anywhere, since on the panel the
  rule would reach a body's own table and split a column of amounts; nor does a body lend it to a table;
- names filing data alone in its footer line, "Filing data sourced from SEC EDGAR. Not investment advice.":
  it sits on every mail, the earnings-day alert among them, whose report dates come from a provider (D-043);
- pads no table through its ``style`` attribute (the shell has no ``<style>`` block), since classic
  Outlook ignores a table's padding and the body would sit against the panel's border, out of line with
  the header;
- writes every colour as a design token's, six-digit hex (``DESIGN.md``'s frontmatter): the panel's border
  and the rows' rules are ``border-light``, the header's hairlines' grey.

``tests/support/mail_styles.py`` models how Blink and WebKit read a page's inline styles, and its header
names what the model leaves out. The planted pages below score it, as edits of a frozen copy of the shell, and
each list's counts are held equal.
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
    colour_problems,
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
_LINE = "The mail's own line."  # a preheader, as each mail hands one to _wrap_html
_FIRST_IN_BODY = re.compile(r"<body\b[^>]*>\s*(<div\b[^>]*>)", re.IGNORECASE)
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

    cells = _outer_cells(_tokens(email_service._wrap_html("<p>Body</p>", preheader=_LINE)))
    assert len(cells) == 3, f"the page's outer table holds a cell each for the header, the panel and the footer line: {len(cells)} cells"
    assert cells[0] == expected_header, (
        "the mail's header is no longer the template's (docs/brand/templates/email-header.html): change both"
    )
    assert cells[2] == footer_line, (
        "the mail's footer line is no longer the template's (docs/brand/templates/email-header.html): change both"
    )
    assert any(token.startswith("<table") and "border:1px solid #E5E7EB" in token for token in cells[1]), (
        "the panel sits between the header and the footer line"
    )


def test_the_footer_line_names_filing_data_alone():
    for where, cell in (
        ("the mail", _outer_cells(_tokens(email_service._wrap_html("<p>Body</p>", preheader=_LINE)))[2]),
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
    page = email_service._wrap_html(body, footer=footer, preheader=_LINE)

    opening = _FIRST_IN_BODY.search(page)
    hides = re.sub(r"\s", "", opening.group(1)).lower() if opening else ""
    assert "display:none" in hides and "mso-hide:all" in hides, (
        "the page opens <body> with the mail's preheader, hidden from the view and from classic Outlook's, so an inbox "
        "lists the mail by its own line and not by the header's words"
    )
    assert page.count(html.escape(_LINE)) == 1, "the preheader sits once, first in <body>"
    tokens = _tokens(page)
    panel = _table(tokens, next(t for t in tokens if t.startswith("<table") and "border:1px solid #E5E7EB" in t))
    assert page.count(body) == 1 and body in "".join(panel), "the body sits once, in the panel"
    assert page.count(footer) == 1 and footer in "".join(panel), "the footer sits once, in the panel"
    assert "</td>" in page[page.index(body) : page.index(footer)], "the footer has a cell of its own, after the body's"
    shell = page.replace(body, "").replace(footer, "")
    wordmarks = _WORDMARK.findall(_INVISIBLE.sub("", html.unescape(shell)))
    assert len(wordmarks) == 1, "the page carries one wordmark, the header's: the name in prose is no wordmark"

    problems = text_size_problems(page) + fixed_width_problems(page) + outlook_width_problems(page) + reach_problems(page)
    assert not problems, "\n".join(problems)
    plain = email_service._wrap_html(f"<p>{'x' * LONG_RUN}</p>", preheader=_LINE)
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
_TOKEN = "Qm9va3NhbmRjb2ZmZWVhbmRyZWFkaW5nYWxsZGF5MDE"  # a made-up token, not a credential  # gitleaks:allow
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
    ("a run across an image set display:contents, which makes no box", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<img src="https://e.test/x.png" width="8" alt="" style="display:contents;">{_UNDER}</p>'),), _NOWHERE),
    ("a run across a button set display:contents, whose label lays out in the line", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<button style="display:contents;">{_UNDER}</button></p>'),), _NOWHERE),
    ("a run across an image its align floats right", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<img src="https://e.test/x.png" width="8" alt="" align="right">{_UNDER}</p>'),), _NOWHERE),
    ("a run across an image whose align is written in capitals, which HTML reads in any case", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<img src="https://e.test/x.png" width="8" alt="" align="LEFT">{_UNDER}</p>'),), _NOWHERE),
    ("a run across an object's fallback text after a param", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<object width="8" height="8"><param name="a" value="b">{_UNDER}</object></p>'),), _NOWHERE),
    ("a run across an object's fallback set display:inline, which lays its fallback out in the line", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<object width="8" height="8" style="display:inline;">{_UNDER}</object></p>'),), _NOWHERE),
    ("a run across an embed with no source set display:inline, which lays out nothing", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<embed style="display:inline;">{_UNDER}</p>'),), _NOWHERE),
    ("a run across a wbr set display:contents, which computes to none", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<wbr style="display:contents;">{_UNDER}</p>'),), _NOWHERE),
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
    ("two stretches either side of an image set display:inline, which is placed whole", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<img src="https://e.test/x.png" width="8" alt="" style="display:inline;">{_UNDER}</p>'),), None),
    ("two stretches either side of a button set display:inline, which is placed whole", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<button style="display:inline;">b</button>{_UNDER}</p>'),), None),
    ("two stretches either side of an image whose float:revert-layer finds no align, which stays in the line", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<img src="https://e.test/x.png" width="8" alt="" style="float:revert-layer;">{_UNDER}</p>'),), None),
    ("two stretches either side of an object whose fallback is set display:block, which ends the line", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<object width="8" height="8" style="display:block;">y</object>{_UNDER}</p>'),), None),
    ("a stretch beside a select set display:contents, which computes to none", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<select style="display:contents;"><option>{_UNDER}</option></select></p>'),), None),
    ("a stretch beside a text area set display:contents, which computes to none", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<textarea style="display:contents;">{_UNDER}</textarea></p>'),), None),
    ("a stretch beside a meter set display:contents, which computes to none", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<meter value="0.5" style="display:contents;">{_UNDER}</meter></p>'),), None),
    ("a stretch beside a progress bar set display:contents, which computes to none", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<progress value="0.5" style="display:contents;">{_UNDER}</progress></p>'),), None),
    ("a stretch beside an audio with controls set display:contents, which computes to none", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<audio controls style="display:contents;">{_UNDER}</audio></p>'),), None),
    ("a stretch beside a math element set display:contents, which computes to none", ((_COPY_LINE, _COPY_LINE + f'<p>{_UNDER}<math style="display:contents;"><mi>{_UNDER}</mi></math></p>'),), None),
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
_SPACED_TABLE = '<table width="100%" cellpadding="0" cellspacing="20"'  # a body table that spaces its columns 20 px apart
_PNG = 'data="https://e.test/x.png" type="image/png"'
_PADDING_ALONE = "in their cells' borders, padding and min-widths alone"
_PERCENT_OVER = "set in percent ask for"
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
    ("the header given a min-width of 600 px", ((_HEADER_STYLE, _HEADER_STYLE.replace("max-width:600px;", "max-width:600px;min-width:600px;")),), "min-width holds it at"),
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
    ("a checkbox as wide as the column, which its own side margins widen", ((_BODY_LINE, '<input type="checkbox" style="width:230px;">' + _BODY_LINE),), "set its side margins to 0"),
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
    ("two cells set in percent whose padding takes the row past the table", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td width="50%" style="padding:0 60px;">a</td><td width="50%" style="padding:0 60px;">b</td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("two cells whose padding takes the row past the table", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td style="padding:0 60px;">a</td><td style="padding:0 60px;">b</td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("two images side by side in cells of half the table", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td width="50%"><img {_IMAGE} width="200"></td><td width="50%"><img {_IMAGE} width="200"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("three cells of 100 px in a fixed table layout", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td width="100">a</td><td width="100">b</td><td width="100">c</td></tr></table>' + _BODY_LINE),), _FIXED),
    ("two columns of 150 px in a fixed table layout", ((_BODY_LINE, f'{_FIXED_TABLE}><col width="150"><col width="150"><tr><td>a</td><td>b</td></tr></table>' + _BODY_LINE),), _FIXED),
    ("a column group of two 150 px columns in a fixed table layout", ((_BODY_LINE, f'{_FIXED_TABLE}><colgroup span="2" width="150"></colgroup><tr><td>a</td><td>b</td></tr></table>' + _BODY_LINE),), _FIXED),
    ("two <col>s that inherit their <colgroup>'s 150 px in a fixed table layout", ((_BODY_LINE, f'{_FIXED_TABLE}><colgroup style="width:150px;"><col style="width:inherit;"><col style="width:inherit;"></colgroup><tr><td>a</td><td>b</td></tr></table>' + _BODY_LINE),), _FIXED),
    ("two <col>s that inherit a <colgroup> that inherits its table's 230 px, in a fixed table layout", ((_BODY_LINE, '<table width="230" cellpadding="0" cellspacing="0" style="table-layout:fixed;"><colgroup style="width:inherit;"><col style="width:inherit;"><col style="width:inherit;"></colgroup><tr><td>a</td><td>b</td></tr></table>' + _BODY_LINE),), _FIXED),
    ("a <colgroup> across two columns that holds no <col>, its width inherit, which takes its table's 230 px for each, in a fixed table layout", ((_BODY_LINE, '<table width="230" cellpadding="0" cellspacing="0" style="table-layout:fixed;"><colgroup span="2" style="width:inherit;"></colgroup><tr><td>a</td><td>b</td></tr></table>' + _BODY_LINE),), _FIXED),
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
    ("an image set display:inline, which a browser still places whole", ((_BODY_LINE, f'<img {_IMAGE} width="600" style="display:inline;">' + _BODY_LINE),), _TOO_WIDE),
    ("an image with no width set display:inline, at its natural size", ((_BODY_LINE, f'<img {_IMAGE} style="display:inline;">' + _BODY_LINE),), _NATURAL),
    ("an image set display:inline flow, placed whole", ((_BODY_LINE, f'<img {_IMAGE} width="600" style="display:inline flow;">' + _BODY_LINE),), _TOO_WIDE),
    ("an image set display:ruby, placed whole", ((_BODY_LINE, f'<img {_IMAGE} width="600" style="display:ruby;">' + _BODY_LINE),), _TOO_WIDE),
    ("an image set display:inline list-item, placed whole", ((_BODY_LINE, f'<img {_IMAGE} width="600" style="display:inline list-item;">' + _BODY_LINE),), _TOO_WIDE),
    ("a button set display:inline, which a browser draws as one box", ((_BODY_LINE, '<button style="display:inline;width:300px;">x</button>' + _BODY_LINE),), _TOO_WIDE),
    ("a text field set display:inline, one box", ((_BODY_LINE, '<input style="display:inline;width:300px;">' + _BODY_LINE),), _TOO_WIDE),
    ("a select set display:inline, one box", ((_BODY_LINE, '<select style="display:inline;width:300px;"><option>x</option></select>' + _BODY_LINE),), _TOO_WIDE),
    ("an iframe set display:inline, placed whole", ((_BODY_LINE, '<iframe width="300" height="20" style="display:inline;"></iframe>' + _BODY_LINE),), _TOO_WIDE),
    ("a video set display:inline, placed whole", ((_BODY_LINE, '<video width="300" style="display:inline;"></video>' + _BODY_LINE),), _TOO_WIDE),
    ("an object whose data may load, set display:inline and held", ((_BODY_LINE, f'<object {_PNG} width="300" height="10" style="display:inline;">fallback</object>' + _BODY_LINE),), _TOO_WIDE),
    ("an object whose data alone may load, though it holds fallback", ((_BODY_LINE, '<object data="https://e.test/x.png" width="300" height="10">fallback</object>' + _BODY_LINE),), _TOO_WIDE),
    ("a text field a pixel past the column with its own border and padding", ((_BODY_LINE, '<input type="text" style="width:223px;">' + _BODY_LINE),), _TOO_WIDE),
    ("a field with no type, a text field, its own border and padding past the column", ((_BODY_LINE, '<input style="width:230px;">' + _BODY_LINE),), _TOO_WIDE),
    ("a field of a type HTML does not know, a text field", ((_BODY_LINE, '<input type="bogus" style="width:230px;">' + _BODY_LINE),), _TOO_WIDE),
    ("a date field a pixel past the column with its own border and padding", ((_BODY_LINE, '<input type="date" style="width:226px;">' + _BODY_LINE),), _TOO_WIDE),
    ("a text area a pixel past the column with its own border and padding", ((_BODY_LINE, '<textarea style="width:225px;"></textarea>' + _BODY_LINE),), _TOO_WIDE),
    ("a range slider a pixel past the column with its own side margins", ((_BODY_LINE, '<input type="range" style="width:227px;">' + _BODY_LINE),), _TOO_WIDE),
    ("a checkbox a pixel past the column with its own side margins, 4 px and 3 px", ((_BODY_LINE, '<input type="checkbox" style="width:224px;">' + _BODY_LINE),), _TOO_WIDE),
    ("an input drawn as an image 300 px wide", ((_BODY_LINE, f'<input type="image" {_IMAGE} width="300">' + _BODY_LINE),), _TOO_WIDE),
    ("an input drawn as an image with no width, at its natural size", ((_BODY_LINE, f'<input type="image" {_IMAGE}>' + _BODY_LINE),), _NATURAL),
    ("a figure's own side margins, 40 px each", ((_BODY_LINE, f'<figure style="margin-top:0;"><img {_IMAGE} width="160"></figure>' + _BODY_LINE),), _TOO_WIDE),
    ("a definition's own 40 px indent", ((_BODY_LINE, f'<dl><dd><img {_IMAGE} width="200"></dd></dl>' + _BODY_LINE),), _TOO_WIDE),
    ("an ordered list's own 40 px indent", ((_BODY_LINE, f'<ol><li><img {_IMAGE} width="200"></li></ol>' + _BODY_LINE),), _TOO_WIDE),
    ("a fieldset's own margins, border and padding", ((_BODY_LINE, f'<fieldset><img {_IMAGE} width="200"></fieldset>' + _BODY_LINE),), _TOO_WIDE),
    ("a rule as wide as the column, which its own border widens", ((_BODY_LINE, '<hr style="width:230px;">' + _BODY_LINE),), _TOO_WIDE),
    ("an image in a button, past its own padding and border", ((_BODY_LINE, f'<button><img {_IMAGE} width="230"></button>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's cell of half the table, its padding added, beside an image a pixel too wide", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td width="50%" style="padding:0 20px;">a</td><td><img {_IMAGE} width="76"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's cellpadding added to a cell of half the table", ((_BODY_LINE, f'<table width="100%" cellpadding="20" cellspacing="0" style="table-layout:fixed;"><tr><td width="50%">a</td><td><img {_IMAGE} width="50"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's cell across two columns, its width less the spacing between them", ((_BODY_LINE, f'<table width="100%" cellpadding="0" cellspacing="10" style="table-layout:fixed;"><tr><td colspan="2" width="100"><img {_IMAGE} width="105"></td><td>c</td></tr><tr><td>d</td><td>e</td><td>f</td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's cell across two columns, which share its width", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td>a</td><td colspan="2" width="200">b</td></tr><tr><td>c</td><td><img {_IMAGE} width="150"></td><td>e</td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's row below a cell that spans two rows", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td rowspan="2">a</td><td width="50">b</td></tr><tr><td><img {_IMAGE} width="100"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's cell of width 0, which HTML ignores", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td width="0">a</td><td><img {_IMAGE} width="150"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's header cell of width 0, which HTML ignores", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><th width="0">a</th><td><img {_IMAGE} width="150"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's column a width sets, held at its min-width, which narrows the column beside it past its image", ((_BODY_LINE, f'{_FIXED_TABLE}><col width="50" style="min-width:100px;"><col width="50"><tr><td>a</td><td><img {_IMAGE} width="85"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's column set in percent, held at its min-width, which narrows the column beside it past its image", ((_BODY_LINE, f'{_FIXED_TABLE}><col width="20%" style="min-width:100px;"><col width="20%"><tr><td>a</td><td><img {_IMAGE} width="85"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's first row setting the widths, a column's min-width holding the first, past the second's image", ((_BODY_LINE, f'{_FIXED_TABLE}><col style="min-width:100px;"><col><tr><td width="50">a</td><td width="50"><img {_IMAGE} width="85"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's first-row cell whose max-width caps its width, which narrows its column past its image", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td width="50" style="max-width:30px;"><img {_IMAGE} width="100"></td><td width="50">b</td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a hidden embed set 400 wide by its attribute, which Chromium lays out", ((_BODY_LINE, '<embed hidden src="https://e.test/x.png" type="image/png" width="400">' + _BODY_LINE),), _TOO_WIDE),
    ("a box set 1e999px wide, which Chromium clamps to its longest length", ((_BODY_LINE, '<div style="width:1e999px;"></div>' + _BODY_LINE),), _TOO_WIDE),
    ("an embed with a source and no width, which shows at its natural size", ((_BODY_LINE, '<embed src="https://e.test/x.png" type="image/png">' + _BODY_LINE),), _NATURAL),
    ("a cell across two columns at a spacing of 20, whose image passes its room by a pixel", ((_BODY_LINE, f'<table width="100%" cellpadding="0" cellspacing="20"><tr><td colspan="2"><img {_IMAGE} width="191"></td></tr><tr><td></td><td></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a cell across the first two columns padded 100 px a side, beside a lone cell padded 50 px a side", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td colspan="2" style="padding:0 100px;"></td><td style="padding:0 50px;"></td></tr><tr><td></td><td></td><td></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a cell across the first two columns padded 60 px a side at a spacing of 20, beside a lone cell padded 26 px a side", ((_BODY_LINE, '<table width="100%" cellpadding="0" cellspacing="20"><tr><td colspan="2" style="padding:0 60px;"></td><td style="padding:0 26px;"></td></tr><tr><td></td><td></td><td></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a caption padded 120 px a side, whose padding leaves its text no room", ((_BODY_LINE, f'{_BARE_TABLE}><caption style="padding:0 120px;">x</caption><tr><td>a</td></tr></table>' + _BODY_LINE),), _NO_ROOM),
    ("a cell across two columns padded 60 px a side, over a column no cell starts in that a <col>'s min-width holds at 120 px, which Chromium adds to it", ((_BODY_LINE, f'{_BARE_TABLE}><col><col style="min-width:120px;"><col><tr><td colspan="2" style="padding:0 60px;"></td><td></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("cells across the same two columns, the widest padded 116 px a side between two padded 115", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td colspan="2" style="padding:0 115px;"></td></tr><tr><td colspan="2" style="padding:0 116px;"></td></tr><tr><td colspan="2" style="padding:0 115px;"></td></tr><tr><td></td><td></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("two cells across three columns each, overlapping over a column no cell starts in that a <col>'s min-width holds, which Chromium adds to it, as the check counts, 310 px", ((_BODY_LINE, f'{_BARE_TABLE}><col><col><col style="min-width:100px;"><col><tr><td colspan="3" style="padding:0 60px;"></td><td></td></tr><tr><td style="padding:0 40px;"></td><td colspan="3" style="padding:0 45px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("two cells across three columns each at a spacing of 20, sharing a column no cell starts in, which Chromium lays out as one", ((_BODY_LINE, '<table width="100%" cellpadding="0" cellspacing="20"><tr><td colspan="3" style="padding:0 60px;"></td><td></td></tr><tr><td style="padding:0 40px;"></td><td colspan="3" style="padding:0 45px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a fixed table layout's column set in percent whose min-width in percent holds nothing, past its image", ((_BODY_LINE, f'{_FIXED_TABLE}><col style="width:10%;min-width:50%;"><col><tr><td><img {_IMAGE} width="100"></td><td>b</td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's column under a first-row cell across columns set in px, which its <col>'s min-width does not hold, past its image", ((_BODY_LINE, f'{_FIXED_TABLE}><col><col style="min-width:100px;"><tr><td colspan="2" width="100">a</td></tr><tr><td>b</td><td><img {_IMAGE} width="150"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's first-row cell set in percent whose max-width in percent caps it, past its image", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td width="50%" style="max-width:20%;"><img {_IMAGE} width="100"></td><td>b</td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's column set in percent whose max-width in percent caps it, past its image", ((_BODY_LINE, f'{_FIXED_TABLE}><col style="width:50%;max-width:10%;"><col><tr><td><img {_IMAGE} width="100"></td><td>b</td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's first-row cell capped in px above its min-width, which narrows the column beside it past its image", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td width="100" style="max-width:20px;min-width:80px;">a</td><td width="100"><img {_IMAGE} width="180"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's first-row cell capped in percent, a min-width in px no hold on it, past its image", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td width="50%" style="max-width:20%;min-width:60px;"><img {_IMAGE} width="50"></td><td>b</td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's column in percent beside a larger first-row percent, which takes it, past the other column's image", ((_BODY_LINE, f'{_FIXED_TABLE}><col width="10%"><col><tr><td width="40%">a</td><td><img {_IMAGE} width="200"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's border-box first-row cell set narrower than its padding, which holds it, past the other column's image", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td width="20" style="padding:0 30px;box-sizing:border-box;">a</td><td><img {_IMAGE} width="200"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's first-row cell whose max-width above its width sets nothing, its image past the column", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td width="50" style="max-width:150px;"><img {_IMAGE} width="140"></td><td width="50">b</td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a header row's cell across two columns over two cells padded 60 px a side, the most of the set's cells", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td colspan="2" style="padding:0 60px;">a</td></tr><tr><td colspan="2" style="padding:0 60px;"></td></tr><tr><td style="padding:0 60px;"></td><td style="padding:0 60px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a cell across two columns whose min-width holds its content box, padded 20 px a side, beside a lone cell padded 25", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td colspan="2" style="min-width:150px;padding:0 20px;"></td><td style="padding:0 25px;"></td></tr><tr><td></td><td></td><td></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a style block in Outlook's view alone, whose selectors no rule reads", (("</head>", "<!--[if mso]><style>td{color:#123456 !important}</style><![endif]--></head>"),), "in classic Outlook's view the page carries a <style> block"),
    ("a linked stylesheet in Outlook's view alone, whose selectors no rule reads", (("</head>", '<!--[if mso]><link rel="stylesheet" href="https://e.test/mail.css"><![endif]--></head>'),), "in classic Outlook's view the page carries a <style> block or a linked stylesheet"),
    ("a column no cell starts in that a <col> sets a width on, which keeps it and its spacing, beside a lone cell padded 80 px a side at a spacing of 20", ((_BODY_LINE, '<table width="100%" cellpadding="0" cellspacing="20"><col><col style="width:1px;"><col><tr><td colspan="2"></td><td style="padding:0 80px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a column no cell starts in that a <col>'s width attribute sets, which keeps it and its spacing, beside a lone cell padded 80 px a side at a spacing of 20", ((_BODY_LINE, '<table width="100%" cellpadding="0" cellspacing="20"><col><col width="1"><col><tr><td colspan="2"></td><td style="padding:0 80px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a cell across three columns that start no other cell, at a spacing of 20, its image past the room they share as one", ((_BODY_LINE, f'<table width="100%" cellpadding="0" cellspacing="20"><tr><td></td><td colspan="3"><img {_IMAGE} width="180"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a lone column at a spacing of 120, whose spacing alone outgrows its table", ((_BODY_LINE, '<table width="100%" cellpadding="0" cellspacing="120"><tr><td></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a fixed table layout's first-row cell across two columns set in percent, which leaves their <col>s' percentages, past the first column's image", ((_BODY_LINE, f'{_FIXED_TABLE}><col width="15%"><col width="60%"><tr><td colspan="2" width="60%">a</td></tr><tr><td><img {_IMAGE} width="60"></td><td>b</td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's column in percent beside an equal first-row percent, which keeps the column's, its padding inside, past its image", ((_BODY_LINE, f'{_FIXED_TABLE}><col width="20%"><col><tr><td width="20%" style="padding:0 30px;"><img {_IMAGE} width="40"></td><td>b</td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's two cells of 60%, whose percentages ask for more than the table, which this check refuses though Chromium scales them", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td width="60%">a</td><td width="60%">b</td></tr></table>' + _BODY_LINE),), _PERCENT_OVER),
    ("a fixed table layout's cell of width 0%, which HTML ignores", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td width="0%">a</td><td><img {_IMAGE} width="150"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's columns in relative lengths, which Chromium ignores", ((_BODY_LINE, f'{_FIXED_TABLE}><col width="3*"><col width="1*"><tr><td><img {_IMAGE} width="150"></td><td>b</td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's columns set in their style", ((_BODY_LINE, f'{_FIXED_TABLE}><col style="width:150px;"><col style="width:150px;"><tr><td>a</td><td>b</td></tr></table>' + _BODY_LINE),), _FIXED),
    ("a fixed table layout's columns past its one cell", ((_BODY_LINE, f'{_FIXED_TABLE}><col width="50"><col width="50"><col width="200"><tr><td>a</td></tr></table>' + _BODY_LINE),), _FIXED),
    ("a column's min-width past its table", ((_BODY_LINE, f'{_FIXED_TABLE}><col style="min-width:300px;"><tr><td>a</td></tr></table>' + _BODY_LINE),), "min-width holds it at"),
    ("two cells' padding in two rows, which their columns add", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td style="padding:0 60px;">a</td><td>b</td></tr><tr><td>c</td><td style="padding:0 60px;">d</td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("two cells' min-widths side by side in an automatic table layout", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td style="min-width:150px;">a</td><td style="min-width:150px;">b</td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("two padded cells and the spacing between them in an automatic table layout", ((_BODY_LINE, '<table width="100%" cellpadding="0" cellspacing="10"><tr><td style="padding:0 55px;">a</td><td style="padding:0 55px;">b</td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a cell's room less the spacing beside its columns", ((_BODY_LINE, f'<table width="100%" cellpadding="0" cellspacing="10"><tr><td><img {_IMAGE} width="205"></td><td>y</td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's body set as its header group, its row setting 300 px", ((_BODY_LINE, f'{_FIXED_TABLE}><tbody><tr><td>b</td></tr></tbody><tbody style="display:table-header-group;"><tr><td width="300">h</td></tr></tbody></table>' + _BODY_LINE),), _FIXED),
    ("a cellpadding written with a plus sign, which HTML reads", ((_BODY_LINE, f'<table width="100%" cellpadding="+5" cellspacing="0"><tr><td><img {_IMAGE} width="225"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a table's border attribute bordering its cells, a pixel each side", ((_BODY_LINE, f'<table width="100%" cellpadding="0" cellspacing="0" border="1"><tr><td><img {_IMAGE} width="227"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's hidden first row, which the revert of its display shows, setting 300 px", ((_BODY_LINE, f'{_FIXED_TABLE}><tr hidden style="display:revert;"><td width="300">a</td></tr><tr><td>b</td></tr></table>' + _BODY_LINE),), _FIXED),
    ("a hidden block the revert of its display shows", ((_BODY_LINE, '<div hidden style="display:revert;"><table width="400"><tr><td>x</td></tr></table></div>' + _BODY_LINE),), _TOO_WIDE),
    ("an image in a cell its table pads, beside another cell", ((_BODY_LINE, f'<table width="100%" cellpadding="20" cellspacing="0"><tr><td><img {_IMAGE} width="200"></td><td>y</td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("an image as wide as the column in a cell beside another, which its 1 px padding narrows", ((_BODY_LINE, f'<table width="100%" cellspacing="0"><tr><td><img {_IMAGE} width="{WIDEST_FIXED}"></td><td></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("an object that holds whitespace alone, which is no fallback", ((_BODY_LINE, '<object width="300" height="10">\n  \n</object>' + _BODY_LINE),), _TOO_WIDE),
    ("an image in a legend, past its own padding", ((_BODY_LINE, f'<fieldset><legend><img {_IMAGE} width="196"></legend></fieldset>' + _BODY_LINE),), _TOO_WIDE),
    ("two cells across two columns each, overlapping, padded 78 px a side, the column they share widened to 156 px", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td colspan="2" style="padding:0 78px;"></td><td></td></tr><tr><td></td><td colspan="2" style="padding:0 78px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a fixed table layout's third row below a cell that spans the rest of its section (rowspan 0)", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td rowspan="0">a</td><td width="50">b</td></tr><tr><td>c</td></tr><tr><td><img {_IMAGE} width="100"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("two cells across two columns each, overlapping, padded 76 px a side, whose excess the check counts in full, where Chromium shares their middle column", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td colspan="2" style="padding:0 76px;"></td><td></td></tr><tr><td></td><td colspan="2" style="padding:0 76px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("two cells across two columns each, overlapping, padded 60 px a side, beside a column of wrapping text, which takes one's excess whole", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td colspan="2" style="padding:0 60px;"></td><td></td></tr><tr><td></td><td colspan="2" style="padding:0 60px;"></td></tr><tr><td>{"a " * 59}a</td><td></td><td></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a cell across the last two columns above one across the first two, which Chromium widens column by column", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td></td><td colspan="2" style="padding:0 100px;"></td></tr><tr><td colspan="2" style="padding:0 50px;"></td><td></td></tr><tr><td></td><td></td><td></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a cell across the first two columns padded 80 px a side, above one across the second and a column no cell starts in, which Chromium widens after the first", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td colspan="2" style="padding:0 80px;"></td></tr><tr><td></td><td colspan="2" style="padding:0 80px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a cell across the second column and a column no cell starts in, padded 80 px a side, above one across the first two, which Chromium widens first, from the left, whatever their rows", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td></td><td colspan="2" style="padding:0 80px;"></td></tr><tr><td colspan="2" style="padding:0 80px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a cell across the third column and two no cell starts in, padded 60 px a side at a spacing of 20, above one across the second and third, which Chromium widens first, across fewer columns", ((_BODY_LINE, f'{_SPACED_TABLE}><tr><td></td><td></td><td colspan="3" style="padding:0 60px;"></td></tr><tr><td></td><td colspan="2" style="padding:0 60px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a lone cell padded 120 px a side, above a cell across its column and a column no cell starts in, padded 10 px a side, which narrows it not", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td style="padding:0 120px;"></td></tr><tr><td colspan="2" style="padding:0 10px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a lone cell padded 75 px a side, under a cell across its column and one no cell starts in, padded 5 px a side, beside a lone cell padded 50 px a side, which narrows it not", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td colspan="2" style="padding:0 5px;"></td><td style="padding:0 50px;"></td></tr><tr><td style="padding:0 75px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a cell across a column and one no cell starts in, padded 50 px a side, beside a lone cell padded 36 px a side at a spacing of 20, whose columns laid out as one drop the spacing between them and narrow it not", ((_BODY_LINE, f'{_SPACED_TABLE}><tr><td colspan="2" style="padding:0 50px;"></td><td style="padding:0 36px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a cell across a column and one no cell starts in, padded 50 px a side, beside a lone cell padded 36 px a side at a spacing of 20, its three columns laid out as one, which drop the spacing between them and narrow it not", ((_BODY_LINE, f'{_SPACED_TABLE}><tr><td colspan="3" style="padding:0 50px;"></td><td style="padding:0 36px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("two cells each across a column and one no cell starts in, the second padded 60 px a side, beside a lone cell padded 60 px a side, which widens the second's own column, not the one its first column's place names", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td colspan="2" style="padding:0 5px;"></td><td colspan="2" style="padding:0 60px;"></td><td style="padding:0 60px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a cell across a column and one no cell starts in, padded 60 px a side, above a lone cell padded 10 px a side in its column and beside one padded 56 px a side, which takes the column past the lone cell's width", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td colspan="2" style="padding:0 60px;"></td><td style="padding:0 56px;"></td></tr><tr><td style="padding:0 10px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("an SVG 30em wide, a length its font sets, as CSS reads an SVG's width", ((_BODY_LINE, '<svg width="30em" height="10"></svg>' + _BODY_LINE),), _NOT_RESOLVED),
    ("an SVG 3in wide, 288 px, as CSS reads an SVG's width", ((_BODY_LINE, '<svg width="3in" height="10"></svg>' + _BODY_LINE),), _TOO_WIDE),
    ("an SVG 2.5e2 wide, 250 px, as CSS reads a number", ((_BODY_LINE, '<svg width="2.5e2" height="10"></svg>' + _BODY_LINE),), _TOO_WIDE),
    ("an SVG 100vw wide, a length the screen sets", ((_BODY_LINE, '<svg width="100vw" height="10"></svg>' + _BODY_LINE),), _NOT_RESOLVED),
    ("a fixed table layout's cell across two columns in percent, which splits over them, beside an image past the third", ((_BODY_LINE, f'<table width="100%" cellpadding="0" cellspacing="10" style="table-layout:fixed;"><tr><td colspan="2" width="50%">a</td><td><img {_IMAGE} width="96"></td></tr><tr><td>d</td><td>e</td><td>f</td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("two columns whose min-widths, 116 px each, pass the table together", ((_BODY_LINE, f'{_BARE_TABLE}><col style="min-width:116px;"><col style="min-width:116px;"><tr><td></td><td></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a fixed table layout's two columns whose min-widths, 120 px each, pass the table together", ((_BODY_LINE, f'{_FIXED_TABLE}><col style="min-width:120px;"><col style="min-width:120px;"><tr><td></td><td></td></tr></table>' + _BODY_LINE),), _FIXED),
    ("a column's min-width beside a cell padded 60 px a side", ((_BODY_LINE, f'{_BARE_TABLE}><col style="min-width:120px;"><col><tr><td></td><td style="padding:0 60px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a submit input set content-box, past the column with its own padding and border", ((_BODY_LINE, '<input type="submit" value="Go" style="box-sizing:content-box;width:215px;">' + _BODY_LINE),), _TOO_WIDE),
    ("a reset input set content-box, its own padding and border", ((_BODY_LINE, '<input type="reset" value="Go" style="box-sizing:content-box;width:215px;">' + _BODY_LINE),), _TOO_WIDE),
    ("a button input set content-box, its own padding and border", ((_BODY_LINE, '<input type="button" value="Go" style="box-sizing:content-box;width:215px;">' + _BODY_LINE),), _TOO_WIDE),
    ("a colour well set content-box, its own padding and border", ((_BODY_LINE, '<input type="color" style="box-sizing:content-box;width:225px;">' + _BODY_LINE),), _TOO_WIDE),
    ("a select set content-box, its own border", ((_BODY_LINE, '<select style="box-sizing:content-box;width:229px;"><option>x</option></select>' + _BODY_LINE),), _TOO_WIDE),
    ("a button set content-box, its own padding and border", ((_BODY_LINE, '<button style="box-sizing:content-box;width:215px;">x</button>' + _BODY_LINE),), _TOO_WIDE),
    ("a block hidden until found, which Chromium lays out", ((_BODY_LINE, '<div hidden="until-found" style="width:400px;"></div>' + _BODY_LINE),), _TOO_WIDE),
    ("a table hidden until found, laid out", ((_BODY_LINE, '<table hidden="until-found" width="400"><tr><td>x</td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a block hidden UNTIL-FOUND, which HTML reads in any case", ((_BODY_LINE, '<div hidden="UNTIL-FOUND" style="width:400px;"></div>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's column whose min-width holds the table, not its share, past its image", ((_BODY_LINE, f'{_FIXED_TABLE}><col style="min-width:150px;"><col><tr><td><img {_IMAGE} width="120"></td><td></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a column spanning two whose min-width holds each, past the table together", ((_BODY_LINE, f'{_BARE_TABLE}><col span="2" style="min-width:116px;"><tr><td></td><td></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a hidden embed given a width in its style, which Chromium lays out", ((_BODY_LINE, '<embed hidden src="https://e.test/x.png" type="image/png" style="width:400px;">' + _BODY_LINE),), _TOO_WIDE),
    ("a text field set display:table-row, still one box", ((_BODY_LINE, '<input style="display:table-row;width:300px;">' + _BODY_LINE),), _TOO_WIDE),
    ("a select set display:table-row-group, one box", ((_BODY_LINE, '<select style="display:table-row-group;width:300px;"><option>x</option></select>' + _BODY_LINE),), _TOO_WIDE),
    ("a text area set display:table-header-group, one box", ((_BODY_LINE, '<textarea style="display:table-header-group;width:300px;"></textarea>' + _BODY_LINE),), _TOO_WIDE),
    ("a meter set display:table-footer-group, one box", ((_BODY_LINE, '<meter value="0.5" style="display:table-footer-group;width:300px;"></meter>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's row below a cell across two columns and two rows, which keeps both columns", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td colspan="2" rowspan="2">a</td><td width="30">b</td></tr><tr><td><img {_IMAGE} width="50"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's column beside a cell across two, past the rest", ((_BODY_LINE, f'<table width="100%" cellpadding="0" cellspacing="10" style="table-layout:fixed;"><tr><td colspan="2" width="100">a</td><td><img {_IMAGE} width="105"></td></tr><tr><td>d</td><td>e</td><td>f</td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's column set to 0, which Chromium keeps", ((_BODY_LINE, f'{_FIXED_TABLE}><col width="0"><col><tr><td><img {_IMAGE} width="50"></td><td>b</td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's column over its first row's cell, which the column's width sets", ((_BODY_LINE, f'{_FIXED_TABLE}><col width="200"><col><tr><td width="50">a</td><td><img {_IMAGE} width="100"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's second footer, laid out where it is written, its row setting 300 px", ((_BODY_LINE, f'{_FIXED_TABLE}><tfoot><tr><td>f1</td></tr></tfoot><tfoot><tr><td width="300">f2</td></tr></tfoot></table>' + _BODY_LINE),), _FIXED),
    ("a fieldset set display:contents, whose content lays out in its place", ((_BODY_LINE, f'<fieldset style="display:contents;"><img {_IMAGE} width="300"></fieldset>' + _BODY_LINE),), _TOO_WIDE),
    ("a legend set display:contents, whose content lays out in its place", ((_BODY_LINE, f'<fieldset style="margin:0;padding:0;border:0;"><legend style="display:contents;"><img {_IMAGE} width="300"></legend></fieldset>' + _BODY_LINE),), _TOO_WIDE),
    ("a marquee set display:contents, whose content lays out in its place", ((_BODY_LINE, f'<marquee style="display:contents;"><img {_IMAGE} width="300"></marquee>' + _BODY_LINE),), _TOO_WIDE),
    ("a button set display:contents, whose content lays out in its place", ((_BODY_LINE, f'<button style="display:contents;"><img {_IMAGE} width="300"></button>' + _BODY_LINE),), _TOO_WIDE),
    ("an email field a pixel past the column with its own border and padding", ((_BODY_LINE, '<input type="email" style="width:223px;">' + _BODY_LINE),), _TOO_WIDE),
    ("a password field a pixel past the column with its own border and padding", ((_BODY_LINE, '<input type="password" style="width:223px;">' + _BODY_LINE),), _TOO_WIDE),
    ("a phone number field a pixel past the column with its own border and padding", ((_BODY_LINE, '<input type="tel" style="width:223px;">' + _BODY_LINE),), _TOO_WIDE),
    ("an address field a pixel past the column with its own border and padding", ((_BODY_LINE, '<input type="url" style="width:223px;">' + _BODY_LINE),), _TOO_WIDE),
    ("a number field a pixel past the column with its own border and padding", ((_BODY_LINE, '<input type="number" style="width:223px;">' + _BODY_LINE),), _TOO_WIDE),
    ("a time field a pixel past the column with its own border and padding", ((_BODY_LINE, '<input type="time" style="width:226px;">' + _BODY_LINE),), _TOO_WIDE),
    ("a local date and time field a pixel past the column with its own border and padding", ((_BODY_LINE, '<input type="datetime-local" style="width:226px;">' + _BODY_LINE),), _TOO_WIDE),
    ("a month field a pixel past the column with its own border and padding", ((_BODY_LINE, '<input type="month" style="width:226px;">' + _BODY_LINE),), _TOO_WIDE),
    ("a week field a pixel past the column with its own border and padding", ((_BODY_LINE, '<input type="week" style="width:226px;">' + _BODY_LINE),), _TOO_WIDE),
    ("an input drawn as an image, its type in capitals", ((_BODY_LINE, f'<input type="IMAGE" {_IMAGE} width="300">' + _BODY_LINE),), _TOO_WIDE),
    ("a column no cell starts in under a <colgroup> set 10 px wide in its style, which keeps it and its spacing, beside a lone cell padded 90 px a side at a spacing of 20", ((_BODY_LINE, f'{_SPACED_TABLE}><colgroup style="width:10px;"><col><col></colgroup><tr><td style="padding:0 90px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a column no cell starts in under a <colgroup> whose width attribute sets 10 px, which keeps it and its spacing, beside a lone cell padded 90 px a side at a spacing of 20", ((_BODY_LINE, f'{_SPACED_TABLE}><colgroup width="10"><col><col></colgroup><tr><td style="padding:0 90px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a column no cell starts in whose <col> width is auto, under a <colgroup> set 10 px wide, which gives it its width, beside a lone cell padded 90 px a side at a spacing of 20", ((_BODY_LINE, f'{_SPACED_TABLE}><colgroup style="width:10px;"><col><col style="width:auto;"></colgroup><tr><td style="padding:0 90px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a column no cell starts in whose <col> width is initial, under a <colgroup> set 10 px wide, which gives it its width, beside a lone cell padded 90 px a side at a spacing of 20", ((_BODY_LINE, f'{_SPACED_TABLE}><colgroup style="width:10px;"><col><col style="width:initial;"></colgroup><tr><td style="padding:0 90px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a column no cell starts in whose <col> width is fit-content, under a <colgroup> set 10 px wide, which gives it its width, beside a lone cell padded 90 px a side at a spacing of 20", ((_BODY_LINE, f'{_SPACED_TABLE}><colgroup style="width:10px;"><col><col style="width:fit-content;"></colgroup><tr><td style="padding:0 90px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a column no cell starts in whose <col> sets 1 px of its own, under a <colgroup> set 10% wide, which keeps it and its spacing, beside a lone cell padded 90 px a side at a spacing of 20", ((_BODY_LINE, f'{_SPACED_TABLE}><colgroup style="width:10%;"><col><col style="width:1px;"></colgroup><tr><td style="padding:0 90px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a column no cell starts in whose <col> inherits its <colgroup>'s 10%, which keeps it and its spacing, beside a lone cell padded 90 px a side at a spacing of 20", ((_BODY_LINE, f'{_SPACED_TABLE}><colgroup style="width:10%;"><col><col style="width:inherit;"></colgroup><tr><td style="padding:0 90px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a column no cell starts in, under one <col> across it and the column before in a <colgroup> set 10 px wide, which keeps it and its spacing, beside a lone cell padded 90 px a side at a spacing of 20", ((_BODY_LINE, f'{_SPACED_TABLE}><colgroup style="width:10px;"><col span="2"></colgroup><tr><td style="padding:0 90px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a cell across the two columns of a <colgroup> set 10 px wide, which keeps the second and its spacing, beside a lone cell padded 80 px a side at a spacing of 20", ((_BODY_LINE, f'{_SPACED_TABLE}><colgroup style="width:10px;"><col><col></colgroup><col><tr><td colspan="2"></td><td style="padding:0 80px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a column no cell starts in, its <col> alone in a <colgroup> whose width attribute is 1, between two others, which keeps it and its spacing, beside a lone cell padded 80 px a side at a spacing of 20", ((_BODY_LINE, f'{_SPACED_TABLE}><col><colgroup width="1"><col></colgroup><col><tr><td colspan="2"></td><td style="padding:0 80px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a column no cell starts in under a <colgroup> whose width is inherit, which takes its table's 230 px and keeps it and its spacing, beside a lone cell padded 90 px a side at a spacing of 20", ((_BODY_LINE, '<table width="230" cellpadding="0" cellspacing="20"><colgroup style="width:inherit;"><col><col></colgroup><tr><td style="padding:0 90px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a <colgroup> across two columns that holds no <col>, its width inherit, which takes its table's 230 px and keeps the second column and its spacing, beside a lone cell padded 90 px a side at a spacing of 20", ((_BODY_LINE, '<table width="230" cellpadding="0" cellspacing="20"><colgroup span="2" style="width:inherit;"></colgroup><tr><td style="padding:0 90px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a <colgroup> across two columns that holds no <col>, its width inherit, which takes its table's 100% and keeps the second column and its spacing, beside a lone cell padded 90 px a side at a spacing of 20", ((_BODY_LINE, f'{_SPACED_TABLE}><colgroup span="2" style="width:inherit;"></colgroup><tr><td style="padding:0 90px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a column no cell starts in under a <colgroup> whose width is inherit, which takes its table's 230 px set in its style and keeps it and its spacing, beside a lone cell padded 90 px a side at a spacing of 20", ((_BODY_LINE, '<table style="width:230px;" cellpadding="0" cellspacing="20"><colgroup style="width:inherit;"><col><col></colgroup><tr><td style="padding:0 90px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a column no cell starts in under a <colgroup> set 10pt wide, a length in px, which keeps it and its spacing, beside a lone cell padded 90 px a side at a spacing of 20", ((_BODY_LINE, f'{_SPACED_TABLE}><colgroup style="width:10pt;"><col><col></colgroup><tr><td style="padding:0 90px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a column no cell starts in under a <colgroup> whose width revert-layer leaves its width attribute's 10 px, which keeps it and its spacing, beside a lone cell padded 90 px a side at a spacing of 20", ((_BODY_LINE, f'{_SPACED_TABLE}><colgroup width="10" style="width:revert-layer;"><col><col></colgroup><tr><td style="padding:0 90px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a column no cell starts in that a <col>'s min-width holds at 100 px, before a column a <col> sets 40 px wide, which Chromium adds to the column before it, beside a lone cell padded 70 px a side", ((_BODY_LINE, f'{_BARE_TABLE}><col><col style="min-width:100px;"><col style="width:40px;"><tr><td style="padding:0 70px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("two columns no cell starts in, their <col>s' min-widths 60 px each, before a column a <col> keeps, which Chromium adds both of, beside a lone cell padded 70 px a side", ((_BODY_LINE, f'{_BARE_TABLE}><col><col style="min-width:60px;"><col style="min-width:60px;"><col style="width:1px;"><tr><td style="padding:0 70px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a column no cell starts in that a <col>'s min-width holds at 100 px, laid out with a column whose own min-width is 50 px, which Chromium adds to the larger of that and its cell padded 70 px a side", ((_BODY_LINE, f'{_BARE_TABLE}><col style="min-width:50px;"><col style="min-width:100px;"><col style="width:1px;"><tr><td style="padding:0 70px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a column no cell starts in that a <col>'s min-width holds at 100 px, before a column its <colgroup> keeps, which Chromium adds to the column before it, beside a lone cell padded 70 px a side", ((_BODY_LINE, f'{_BARE_TABLE}><col><col style="min-width:100px;"><colgroup style="width:10px;"><col></colgroup><tr><td style="padding:0 70px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a cell across two columns padded 50 px a side, the second no cell starts in, beside a column a <col>'s min-width holds at 150 px", ((_BODY_LINE, f'{_BARE_TABLE}><col><col><col style="min-width:150px;"><tr><td colspan="2" style="padding:0 50px;"></td><td></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("two columns no cell starts in that one <col> across both sets 1 px wide, which keeps both and their spacing, beside a lone cell padded 70 px a side at a spacing of 20", ((_BODY_LINE, f'{_SPACED_TABLE}><col><col span="2" width="1"><col><tr><td colspan="3"></td><td style="padding:0 70px;"></td></tr></table>' + _BODY_LINE),), _PADDING_ALONE),
    ("a fixed table layout's column under a first-row cell across two columns set in percent, which its <col>'s min-width holds, past the first column's image", ((_BODY_LINE, f'{_FIXED_TABLE}><col><col style="min-width:150px;"><tr><td colspan="2" width="40%">a</td></tr><tr><td><img {_IMAGE} width="100"></td><td>c</td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's column set 200 px wide whose max-width in percent sets nothing, past the other column's image", ((_BODY_LINE, f'{_FIXED_TABLE}><col style="width:200px;max-width:10%;"><col><tr><td>a</td><td><img {_IMAGE} width="150"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's first-row cell capped in px over a min-width in percent, which does not hold the cap, past its image", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td width="100" style="max-width:20px;min-width:50%;"><img {_IMAGE} width="100"></td><td width="100">b</td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's column set in px under a first-row cell set in percent, which keeps the column's, past its image", ((_BODY_LINE, f'{_FIXED_TABLE}><col width="50"><col><tr><td width="80%"><img {_IMAGE} width="150"></td><td>b</td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
    ("a fixed table layout's <col>s of 20% and 60% under a first-row cell of 70%, which takes the first, asking 130% in all, which this check refuses", ((_BODY_LINE, f'{_FIXED_TABLE}><col width="20%"><col width="60%"><tr><td width="70%" style="padding:0 40px;">a</td><td><img {_IMAGE} width="82"></td></tr></table>' + _BODY_LINE),), _PERCENT_OVER),
    ("a fixed table layout's cells of 60% and 45% at a spacing of 10, which ask for more than the room the spacing leaves, which this check refuses", ((_BODY_LINE, f'<table width="100%" cellpadding="0" cellspacing="10" style="table-layout:fixed;"><tr><td width="60%" style="padding:0 40px;">a</td><td width="45%"><img {_IMAGE} width="62"></td></tr></table>' + _BODY_LINE),), _PERCENT_OVER),
    ("a fixed table layout's column set 0%, which sets no width, so the columns share the table, past the other column's image", ((_BODY_LINE, f'{_FIXED_TABLE}><col style="width:0%;"><col><tr><td>a</td><td><img {_IMAGE} width="200"></td></tr></table>' + _BODY_LINE),), _TOO_WIDE),
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
    ("a checkbox that fits with its own side margins", ((_BODY_LINE, '<input type="checkbox" style="width:223px;">' + _BODY_LINE),), None),
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
    ("an image set display:inline that fits", ((_BODY_LINE, f'<img {_IMAGE} width="200" style="display:inline;">' + _BODY_LINE),), None),
    ("an image set display:contents, which makes no box", ((_BODY_LINE, f'<img {_IMAGE} width="600" style="display:contents;">' + _BODY_LINE),), None),
    ("a text field set display:contents, which makes no box", ((_BODY_LINE, '<input style="display:contents;width:600px;">' + _BODY_LINE),), None),
    ("a button set display:contents, which lays its label out in the line", ((_BODY_LINE, '<button style="display:contents;width:600px;">x</button>' + _BODY_LINE),), None),
    ("a search field as wide as the column, which holds its border and padding", ((_BODY_LINE, '<input type="search" style="width:230px;">' + _BODY_LINE),), None),
    ("a text field that fits with its own border and padding", ((_BODY_LINE, '<input type="text" style="width:222px;">' + _BODY_LINE),), None),
    ("a date field that fits with its own border and padding", ((_BODY_LINE, '<input type="date" style="width:225px;">' + _BODY_LINE),), None),
    ("a text area that fits with its own border and padding", ((_BODY_LINE, '<textarea style="width:224px;"></textarea>' + _BODY_LINE),), None),
    ("a range slider that fits with its own side margins", ((_BODY_LINE, '<input type="range" style="width:226px;">' + _BODY_LINE),), None),
    ("a checkbox whose width holds its padding, as a browser sizes one", ((_BODY_LINE, '<input type="checkbox" style="width:222px;padding:0 10px;">' + _BODY_LINE),), None),
    ("a radio button whose width holds its padding, as a browser sizes one", ((_BODY_LINE, '<input type="radio" style="width:221px;padding:0 10px;">' + _BODY_LINE),), None),
    ("an input drawn as an image that fits", ((_BODY_LINE, f'<input type="image" {_IMAGE} width="200">' + _BODY_LINE),), None),
    ("an SVG whose width attribute fits", ((_BODY_LINE, '<svg width="100" height="10"></svg>' + _BODY_LINE),), None),
    ("a fixed table layout's cell of half the table, its padding added, holding an image that fits", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td width="50%" style="padding:0 20px;"><img {_IMAGE} width="80"></td><td>b</td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's column beside a cell across two, which takes the rest", ((_BODY_LINE, f'<table width="100%" cellpadding="0" cellspacing="10" style="table-layout:fixed;"><tr><td colspan="2" width="100">a</td><td><img {_IMAGE} width="95"></td></tr><tr><td>d</td><td>e</td><td>f</td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's cell spanning two rows, whose column the next row skips", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td rowspan="2" width="50">a</td><td>b</td></tr><tr><td><img {_IMAGE} width="100"></td></tr></table>' + _BODY_LINE),), None),
    ("an automatic table layout's cell of width 0, which HTML ignores", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td width="0"><img {_IMAGE} width="50"></td><td>b</td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's header set as a body, which lays out in its place", ((_BODY_LINE, f'{_FIXED_TABLE}><tbody><tr><td>b</td></tr></tbody><thead style="display:table-row-group;"><tr><td width="300">h</td></tr></thead></table>' + _BODY_LINE),), None),
    ("a fixed table layout's hidden cell, which takes no column", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td width="200" style="display:none;">a</td><td><img {_IMAGE} width="200"></td></tr></table>' + _BODY_LINE),), None),
    ("two padded cells in two rows that their columns hold", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td style="padding:0 50px;">a</td><td>b</td></tr><tr><td>c</td><td style="padding:0 50px;">d</td></tr></table>' + _BODY_LINE),), None),
    ("an image inside the borders a table's border attribute gives its cell", ((_BODY_LINE, f'<table width="100%" cellpadding="0" cellspacing="0" border="1"><tr><td><img {_IMAGE} width="226"></td></tr></table>' + _BODY_LINE),), None),
    ("a hidden block revert-layer keeps hidden", ((_BODY_LINE, '<div hidden style="display:revert-layer;"><table width="400"><tr><td>x</td></tr></table></div>' + _BODY_LINE),), None),
    ("a cell whose style reverts its table's cellpadding, beside an empty cell", ((_BODY_LINE, f'<table width="100%" cellpadding="20" cellspacing="0"><tr><td style="padding:revert;"><img {_IMAGE} width="229"></td><td style="padding:revert;"></td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's hidden first row under revert-layer, which keeps it hidden", ((_BODY_LINE, f'{_FIXED_TABLE}><tr hidden style="display:revert-layer;"><td width="300">a</td></tr><tr><td>b</td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's column of 50 px beside one that sets none, whose image the rest holds", ((_BODY_LINE, f'{_FIXED_TABLE}><col width="50"><col><tr><td>a</td><td><img {_IMAGE} width="150"></td></tr></table>' + _BODY_LINE),), None),
    ("two padded cells in one column, which the column holds once", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td style="padding:0 60px;">a</td><td>b</td></tr><tr><td style="padding:0 60px;">c</td><td>d</td></tr></table>' + _BODY_LINE),), None),
    ("an SVG 2in wide, 192 px", ((_BODY_LINE, '<svg width="2in" height="10"></svg>' + _BODY_LINE),), None),
    ("two cells across two columns each, side by side, padded 55 px a side, whose columns they share with no other", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td colspan="2" style="padding:0 55px;"></td><td colspan="2" style="padding:0 55px;"></td></tr><tr><td></td><td></td><td></td><td></td></tr></table>' + _BODY_LINE),), None),
    ("a cell across two padded 100 px a side, over a column's padded cell, whose width its excess counts on", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td colspan="2" style="padding:0 100px;"></td></tr><tr><td style="padding:0 75px;"></td><td></td></tr></table>' + _BODY_LINE),), None),
    ("a cell across two padded 90 px a side, which the spacing between its columns holds", ((_BODY_LINE, '<table width="100%" cellpadding="0" cellspacing="20"><tr><td colspan="2" style="padding:0 90px;"></td></tr><tr><td></td><td></td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's padded cell across two columns in percent, whose padding the split leaves out", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td colspan="2" width="50%" style="padding:0 30px;">a</td><td><img {_IMAGE} width="115"></td></tr><tr><td>d</td><td>e</td><td>f</td></tr></table>' + _BODY_LINE),), None),
    ("two columns whose min-widths, 115 px each, fit the table together", ((_BODY_LINE, f'{_BARE_TABLE}><col style="min-width:115px;"><col style="min-width:115px;"><tr><td></td><td></td></tr></table>' + _BODY_LINE),), None),
    ("two columns whose min-widths in percent, 50% each, fit beside the spacing, which Chromium's automatic layout ignores", ((_BODY_LINE, '<table width="100%" cellpadding="0" cellspacing="20"><col style="min-width:50%;"><col style="min-width:50%;"><tr><td></td><td></td></tr></table>' + _BODY_LINE),), None),
    ("a submit input set content-box that fits with its own padding and border", ((_BODY_LINE, '<input type="submit" value="Go" style="box-sizing:content-box;width:214px;">' + _BODY_LINE),), None),
    ("a button set content-box that fits with its own padding and border", ((_BODY_LINE, '<button style="box-sizing:content-box;width:214px;">x</button>' + _BODY_LINE),), None),
    ("a hidden embed with no width, which its own style sheet sets to 0", ((_BODY_LINE, '<embed hidden src="https://e.test/x.png" type="image/png">' + _BODY_LINE),), None),
    ("a block whose hidden attribute names until-found after a space, which hides it", ((_BODY_LINE, '<div hidden=" until-found" style="width:400px;"></div>' + _BODY_LINE),), None),
    ("a fixed table layout's first-row cell whose width holds its padding, beside an image that fits", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td width="100" style="box-sizing:border-box;padding:0 40px;">a</td><td><img {_IMAGE} width="125"></td></tr></table>' + _BODY_LINE),), None),
    ("a span whose float is reverted, which sets it no width", ((_BODY_LINE, '<span style="float:revert;width:400px;">x</span>' + _BODY_LINE),), None),
    ("a fixed table layout's next body below a cell that spans two rows, which the span stops short of", ((_BODY_LINE, f'{_FIXED_TABLE}><tbody><tr><td rowspan="2">a</td><td width="50">b</td></tr></tbody><tbody><tr><td><img {_IMAGE} width="100"></td></tr></tbody></table>' + _BODY_LINE),), None),
    ("a fixed table layout's cell across two columns, which holds the spacing between them", ((_BODY_LINE, f'<table width="100%" cellpadding="0" cellspacing="10" style="table-layout:fixed;"><tr><td colspan="2" width="100"><img {_IMAGE} width="100"></td><td>c</td></tr><tr><td>d</td><td>e</td><td>f</td></tr></table>' + _BODY_LINE),), None),
    ("a table set 0 wide, which sets none", ((_BODY_LINE, f'<table width="0" cellpadding="0" cellspacing="0"><tr><td><img {_IMAGE} width="200"></td></tr></table>' + _BODY_LINE),), None),
    ("a header cell set 0 wide, which sets none", ((_BODY_LINE, f'{_BARE_TABLE}><tr><th width="0"><img {_IMAGE} width="200"></th></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's column that sets no width beside one that does, taking what it leaves whatever its min-width", ((_BODY_LINE, f'{_FIXED_TABLE}><col style="min-width:150px;"><col width="50"><tr><td><img {_IMAGE} width="170"></td><td>b</td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's two columns that set no width, sharing the table alike whatever their min-widths", ((_BODY_LINE, f'{_FIXED_TABLE}><col style="min-width:150px;"><col><tr><td>a</td><td><img {_IMAGE} width="110"></td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's first-row cell set in percent, whose max-width in px sets nothing", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td width="50%" style="max-width:30px;"><img {_IMAGE} width="110"></td><td width="50%">b</td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's first-row cell whose max-width in percent sets nothing", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td width="100" style="max-width:20%;"><img {_IMAGE} width="110"></td><td width="100">b</td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's first-row cell whose max-width caps its width before its padding", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td width="50" style="max-width:30px;padding:0 5px;"><img {_IMAGE} width="90"></td><td width="50">b</td></tr></table>' + _BODY_LINE),), None),
    ("a hidden embed whose width reverts to its own style sheet's 0", ((_BODY_LINE, '<embed hidden src="https://e.test/x.png" type="image/png" width="400" style="width:revert;">' + _BODY_LINE),), None),
    ("an svg whose width is a CSS-wide keyword, which sets none, held by its max-width", ((_BODY_LINE, '<svg width="initial" height="10" style="max-width:100%;"></svg>' + _BODY_LINE),), None),
    ("an svg set 1e999 wide, which Chromium clamps, held by its max-width", ((_BODY_LINE, '<svg width="1e999" height="10" style="max-width:100%;"></svg>' + _BODY_LINE),), None),
    ("a cell across two padded 100 px a side, beside a column whose lone cell is padded 70 px a side, which Chromium fits", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td colspan="2" style="padding:0 100px;"></td></tr><tr><td></td><td style="padding:0 70px;"></td></tr></table>' + _BODY_LINE),), None),
    ("a cell across the first two columns padded 60 px a side at a spacing of 20, beside a lone cell padded 25 px a side, which fit", ((_BODY_LINE, '<table width="100%" cellpadding="0" cellspacing="20"><tr><td colspan="2" style="padding:0 60px;"></td><td style="padding:0 25px;"></td></tr><tr><td></td><td></td><td></td></tr></table>' + _BODY_LINE),), None),
    ("a caption padded 10 px a side, which fits", ((_BODY_LINE, f'{_BARE_TABLE}><caption style="padding:0 10px;">x</caption><tr><td>a</td></tr></table>' + _BODY_LINE),), None),
    ("a header row and eight rows each a cell across both columns padded 16 px a side, which count once", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td>Company</td><td>Filed</td></tr>' + '<tr><td colspan="2" style="padding:0 16px;">a</td></tr>' * 8 + '</table>' + _BODY_LINE),), None),
    ("a cell across three columns padded 60 px a side, over a column a <col>'s min-width holds that starts a cell of its own, which fit", ((_BODY_LINE, f'{_BARE_TABLE}><col><col style="min-width:100px;"><col><tr><td colspan="3" style="padding:0 60px;"></td></tr><tr><td></td><td></td><td></td></tr></table>' + _BODY_LINE),), None),
    ("a cell across three columns that start no other cell, at a spacing of 20, laid out as one beside a cell padded 85 px a side", ((_BODY_LINE, '<table width="100%" cellpadding="0" cellspacing="20"><tr><td style="padding:0 85px;"></td><td colspan="3"></td></tr></table>' + _BODY_LINE),), None),
    ("two cells across three columns each at a spacing of 20, over a column no cell starts in that a <col> sets 100 px wide, which keeps it", ((_BODY_LINE, '<table width="100%" cellpadding="0" cellspacing="20"><col><col><col style="width:100px;"><col><tr><td colspan="3" style="padding:0 60px;"></td><td></td></tr><tr><td style="padding:0 40px;"></td><td colspan="3" style="padding:0 45px;"></td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's column set in percent whose min-width in percent holds nothing, its image within it", ((_BODY_LINE, f'{_FIXED_TABLE}><col style="width:10%;min-width:50%;"><col><tr><td><img {_IMAGE} width="20"></td><td>b</td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's column under a first-row cell across columns set in px, which its <col>'s min-width does not hold, its image within it", ((_BODY_LINE, f'{_FIXED_TABLE}><col><col style="min-width:100px;"><tr><td colspan="2" width="100">a</td></tr><tr><td>b</td><td><img {_IMAGE} width="110"></td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's first-row cell set in percent whose max-width in percent caps it, its image within it", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td width="50%" style="max-width:20%;"><img {_IMAGE} width="44"></td><td>b</td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's column set in px whose max-width in px sets nothing", ((_BODY_LINE, f'{_FIXED_TABLE}><col style="width:100px;max-width:30px;"><col style="width:100px;"><tr><td><img {_IMAGE} width="110"></td><td>b</td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's column in percent beside a smaller first-row percent, which keeps its own", ((_BODY_LINE, f'{_FIXED_TABLE}><col width="50%"><col><tr><td width="10%"><img {_IMAGE} width="110"></td><td>b</td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's first-row cell capped in px above its min-width, the column beside it holding its image", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td width="100" style="max-width:20px;min-width:80px;">a</td><td width="100"><img {_IMAGE} width="125"></td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's border-box first-row cell set narrower than its padding, the other column holding its image", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td width="20" style="padding:0 30px;box-sizing:border-box;">a</td><td><img {_IMAGE} width="165"></td></tr></table>' + _BODY_LINE),), None),
    ("a column a <col>'s min-width holds at 120 px beside a lone cell padded 60 px a side, and another padded 55, which fit", ((_BODY_LINE, f'{_BARE_TABLE}><col style="min-width:120px;"><col><tr><td style="padding:0 60px;"></td><td style="padding:0 55px;"></td></tr></table>' + _BODY_LINE),), None),
    ("an svg whose width is unset, which sets none, held by its max-width", ((_BODY_LINE, '<svg width="unset" height="10" style="max-width:100%;"></svg>' + _BODY_LINE),), None),
    ("a hidden embed whose width rolls back a layer to its own style sheet's 0", ((_BODY_LINE, '<embed hidden src="https://e.test/x.png" type="image/png" style="width:revert-layer;">' + _BODY_LINE),), None),
    ("a style block in a comment no client reads", (("</head>", "<!--[if !mso]><style>td{color:#123456}</style><![endif]--></head>"),), None),
    ("a fixed table layout's column group in a relative length, which Chromium ignores", ((_BODY_LINE, f'{_FIXED_TABLE}><colgroup width="3*"></colgroup><col><tr><td><img {_IMAGE} width="100"></td><td>b</td></tr></table>' + _BODY_LINE),), None),
    ("two <col>s that inherit a <colgroup> setting no width in a fixed table layout, which share the table, the first's image within its half", ((_BODY_LINE, f'{_FIXED_TABLE}><colgroup><col style="width:inherit;"><col style="width:inherit;"></colgroup><tr><td><img {_IMAGE} width="100"></td><td>b</td></tr></table>' + _BODY_LINE),), None),
    ("an image in a legend that fits within its own padding", ((_BODY_LINE, f'<fieldset><legend><img {_IMAGE} width="194"></legend></fieldset>' + _BODY_LINE),), None),
    ("a video set display:contents, none", ((_BODY_LINE, '<video width="600" style="display:contents;"></video>' + _BODY_LINE),), None),
    ("a frame set display:contents, none", ((_BODY_LINE, '<iframe width="600" style="display:contents;"></iframe>' + _BODY_LINE),), None),
    ("a canvas set display:contents, none", ((_BODY_LINE, '<canvas width="600" style="display:contents;"></canvas>' + _BODY_LINE),), None),
    ("an SVG set display:contents, none", ((_BODY_LINE, '<svg width="600" height="10" style="display:contents;"></svg>' + _BODY_LINE),), None),
    ("an object that may load, set display:contents, none", ((_BODY_LINE, f'<object {_PNG} width="600" style="display:contents;"></object>' + _BODY_LINE),), None),
    ("an embed set display:contents, none", ((_BODY_LINE, '<embed src="https://e.test/x.png" type="image/png" width="600" style="display:contents;">' + _BODY_LINE),), None),
    ("a file input that fits with no border or padding of its own", ((_BODY_LINE, '<input type="file" style="width:228px;">' + _BODY_LINE),), None),
    ("a time field that fits with its own border and padding", ((_BODY_LINE, '<input type="time" style="width:225px;">' + _BODY_LINE),), None),
    ("a local date and time field that fits with its own border and padding", ((_BODY_LINE, '<input type="datetime-local" style="width:225px;">' + _BODY_LINE),), None),
    ("a month field that fits with its own border and padding", ((_BODY_LINE, '<input type="month" style="width:225px;">' + _BODY_LINE),), None),
    ("a week field that fits with its own border and padding", ((_BODY_LINE, '<input type="week" style="width:225px;">' + _BODY_LINE),), None),
    ("a column no cell starts in whose <col> width is auto, laid out as one with the column before it, beside a lone cell padded 80 px a side at a spacing of 20", ((_BODY_LINE, '<table width="100%" cellpadding="0" cellspacing="20"><col><col style="width:auto;"><col><tr><td colspan="2"></td><td style="padding:0 80px;"></td></tr></table>' + _BODY_LINE),), None),
    ("a column no cell starts in whose <col> sets a min-width alone, laid out as one with the column before it, beside a lone cell padded 80 px a side at a spacing of 20", ((_BODY_LINE, '<table width="100%" cellpadding="0" cellspacing="20"><col><col style="min-width:0;"><col><tr><td colspan="2"></td><td style="padding:0 80px;"></td></tr></table>' + _BODY_LINE),), None),
    ("a cell across three columns padded 100 px a side, above one across the third and a column no cell starts in, padded 60, which Chromium widens first, across fewer columns, so the wider cell takes its width", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td colspan="3" style="padding:0 100px;"></td></tr><tr><td></td><td></td><td colspan="2" style="padding:0 60px;"></td></tr></table>' + _BODY_LINE),), None),
    ("two cells across the second column and the columns after it that no cell starts in, padded 100 px a side, which Chromium lays out as one column, each widening it, not added", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td></td><td colspan="2" style="padding:0 100px;"></td></tr><tr><td></td><td colspan="3" style="padding:0 100px;"></td></tr></table>' + _BODY_LINE),), None),
    ("a cell across three columns that start no other cell, at a spacing of 20, its image within the room they share as one", ((_BODY_LINE, f'<table width="100%" cellpadding="0" cellspacing="20"><tr><td></td><td colspan="3"><img {_IMAGE} width="170"></td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's first-row cell across two columns set in percent, which leaves their <col>s' percentages, the first column's image within it", ((_BODY_LINE, f'{_FIXED_TABLE}><col width="15%"><col width="60%"><tr><td colspan="2" width="60%">a</td></tr><tr><td><img {_IMAGE} width="40"></td><td>b</td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's column in percent beside a larger first-row percent, which brings its padding, its image within it", ((_BODY_LINE, f'{_FIXED_TABLE}><col width="10%"><col><tr><td width="20%" style="padding:0 30px;"><img {_IMAGE} width="40"></td><td>b</td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's border-box first-row cell set in percent below its padding, which keeps its share, the other column holding its image", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td width="20%" style="padding:0 30px;box-sizing:border-box;">a</td><td><img {_IMAGE} width="180"></td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's column under a first-row cell across columns set in px, whose <col>'s min-width of 200 px holds neither it nor the table", ((_BODY_LINE, f'{_FIXED_TABLE}><col><col style="min-width:200px;"><tr><td colspan="2" width="100">a</td></tr><tr><td>b</td><td>c</td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's column whose min-width in percent asks for more than the table, which Chromium ignores", ((_BODY_LINE, f'{_FIXED_TABLE}><col style="width:10%;min-width:150%;"><col><tr><td>a</td><td>b</td></tr></table>' + _BODY_LINE),), None),
    ("a cell across two columns whose border-box min-width holds its padding, padded 20 px a side, beside a lone cell padded 25", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td colspan="2" style="min-width:150px;padding:0 20px;box-sizing:border-box;"></td><td style="padding:0 25px;"></td></tr><tr><td></td><td></td><td></td></tr></table>' + _BODY_LINE),), None),
    ("a cell across two columns padded 60 px a side, over a column no cell starts in that a <col>'s min-width holds at 110 px, which Chromium adds to it, and fits", ((_BODY_LINE, f'{_BARE_TABLE}><col><col style="min-width:110px;"><col><tr><td colspan="2" style="padding:0 60px;"></td><td></td></tr></table>' + _BODY_LINE),), None),
    ("a column no cell starts in under a <colgroup> set 10% wide, which passes no width to it, laid out as one with the column before it, beside a lone cell padded 90 px a side at a spacing of 20", ((_BODY_LINE, f'{_SPACED_TABLE}><colgroup style="width:10%;"><col><col></colgroup><tr><td style="padding:0 90px;"></td></tr></table>' + _BODY_LINE),), None),
    ("a column no cell starts in under a <colgroup> set auto wide, which passes no width to it, laid out as one with the column before it, beside a lone cell padded 90 px a side at a spacing of 20", ((_BODY_LINE, f'{_SPACED_TABLE}><colgroup style="width:auto;"><col><col></colgroup><tr><td style="padding:0 90px;"></td></tr></table>' + _BODY_LINE),), None),
    ("a column no cell starts in whose <col> width is inherit, under a <colgroup> that sets none in a table set 230 px wide, which passes no width to it, laid out as one with the column before it, beside a lone cell padded 90 px a side at a spacing of 20", ((_BODY_LINE, '<table width="230" cellpadding="0" cellspacing="20"><colgroup><col><col style="width:inherit;"></colgroup><tr><td style="padding:0 90px;"></td></tr></table>' + _BODY_LINE),), None),
    ("a column no cell starts in under a <colgroup> whose width inherits its table's 100%, which passes no width to a <col> that sets none, laid out as one with the column before it, beside a lone cell padded 90 px a side at a spacing of 20", ((_BODY_LINE, f'{_SPACED_TABLE}><colgroup style="width:inherit;"><col><col></colgroup><tr><td style="padding:0 90px;"></td></tr></table>' + _BODY_LINE),), None),
    ("a column no cell starts in that a <col>'s min-width holds at 100 px, past every column kept, which Chromium drops, beside a lone cell padded 70 px a side", ((_BODY_LINE, f'{_BARE_TABLE}><col><col style="min-width:100px;"><tr><td style="padding:0 70px;"></td></tr></table>' + _BODY_LINE),), None),
    ("a column no cell starts in that a <col>'s min-width holds at 100 px, after a column a <col> sets 1 px wide, past every column kept, which Chromium drops, beside a lone cell padded 70 px a side", ((_BODY_LINE, f'{_BARE_TABLE}><col><col style="width:1px;"><col style="min-width:100px;"><tr><td style="padding:0 70px;"></td></tr></table>' + _BODY_LINE),), None),
    ("a cell across two columns padded 60 px a side, over a column no cell starts in that a <col>'s min-width holds at 120 px, past every column kept, which Chromium drops", ((_BODY_LINE, f'{_BARE_TABLE}><col><col style="min-width:120px;"><tr><td colspan="2" style="padding:0 60px;"></td></tr></table>' + _BODY_LINE),), None),
    ("a cell of 50% across two columns that start no other cell, its image within the table they take as one", ((_BODY_LINE, f'{_BARE_TABLE}><tr><td colspan="2" width="50%"><img {_IMAGE} width="200"></td></tr></table>' + _BODY_LINE),), None),
    ("a fixed table layout's first-row cell of 60% across two columns, which splits over them", ((_BODY_LINE, f'{_FIXED_TABLE}><tr><td colspan="2" width="60%">a</td></tr><tr><td>b</td><td>c</td></tr></table>' + _BODY_LINE),), None),
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


_PANEL_BORDER = "border:1px solid #E5E7EB;border-radius:16px"
_NO_TOKEN = "no design token's colour"
# A link in a token's hex that classic Outlook alone sees, beside the link it does not, so the page's own view alone
# reads the planted link's colour (classic Outlook's view takes no light-dark()).
_OUTLOOK_HEX_LINK = '<!--[if mso]><a href="https://e.test/" style="color:#1A1A17;">x</a><![endif]-->'


def _page_view_alone(link: str) -> str:
    return f"<!--[if !mso]><!-->{link}<!--<![endif]-->{_OUTLOOK_HEX_LINK}"


# Each way a page can write a colour no design token holds, and the look-alikes that write a token's.
COLOURS = [
    # Flagged.
    ("the panel's border in main's grey, which no token holds", ((_PANEL_BORDER, _PANEL_BORDER.replace("#E5E7EB", "#E5E1D8")),), "border is #E5E1D8"),
    ("a body line in a named colour", ((_BODY_LINE, '<p style="color:red;">x</p>' + _BODY_LINE),), "color is red"),
    ("a body line in a short hex", ((_BODY_LINE, '<p style="color:#fff;">x</p>' + _BODY_LINE),), "color is #fff"),
    ("a token's colour written as rgb()", ((_BODY_LINE, '<p style="color:rgb(26,26,23);">x</p>' + _BODY_LINE),), "color is rgb(26,26,23)"),
    ("a gradient's stop no token holds", ((_BODY_LINE, '<p style="background:linear-gradient(#F4F3EE,#000000);">x</p>' + _BODY_LINE),), "background is #000000"),
    ("a shadow's colour, read whatever the property", ((_BODY_LINE, '<p style="box-shadow:0 0 2px #123456;">x</p>' + _BODY_LINE),), "box-shadow is #123456"),
    ("a cell's bgcolor no token holds", ((_BODY_LINE, '<table><tr><td bgcolor="#FFFFFE">x</td></tr></table>' + _BODY_LINE),), "bgcolor is '#FFFFFE'"),
    ("a bgcolor in a word, which HTML turns into a colour", ((_BODY_LINE, '<table><tr><td bgcolor="sage">x</td></tr></table>' + _BODY_LINE),), "bgcolor is 'sage'"),
    ("a font's color attribute no token holds", ((_BODY_LINE, '<font color="#123456">x</font>' + _BODY_LINE),), "color is '#123456'"),
    ("a colour in Outlook's view alone", ((_BODY_LINE, '<!--[if mso]><p style="color:#000000;">x</p><![endif]-->' + _BODY_LINE),), "color is #000000"),
    ("a colour mixed from two tokens' colours, which no token holds", ((_BODY_LINE, '<p style="color:color-mix(in srgb,#3C6650 50%,#FFFFFF);">x</p>' + _BODY_LINE),), "color is color-mix("),
    ("a token's colour made translucent", ((_BODY_LINE, '<p style="color:rgb(from #3C6650 r g b / 50%);">x</p>' + _BODY_LINE),), "color is rgb(from"),
    ("light-dark()'s dark colour no token holds", ((_BODY_LINE, '<p style="color:light-dark(#1A1A17,#123456);">x</p>' + _BODY_LINE),), "color is #123456"),
    ("a body's text colour no token holds", (("<body", '<body text="#123456"'),), "text is '#123456'"),
    ("a body's link colour no token holds", (("<body", '<body link="#123456"'),), "link is '#123456'"),
    ("a body's visited-link colour no token holds", (("<body", '<body vlink="#123456"'),), "vlink is '#123456'"),
    ("a body's active-link colour no token holds", (("<body", '<body alink="#123456"'),), "alink is '#123456'"),
    ("a table's border colour no token holds", ((_BODY_LINE, '<table bordercolor="#123456"><tr><td>x</td></tr></table>' + _BODY_LINE),), "bordercolor is '#123456'"),
    ("VML's fill colour, which classic Outlook paints", ((_BODY_LINE, '<!--[if mso]><v:roundrect fillcolor="#123456"></v:roundrect><![endif]-->' + _BODY_LINE),), "fillcolor is '#123456'"),
    ("VML's stroke colour, which classic Outlook paints", ((_BODY_LINE, '<!--[if mso]><v:roundrect strokecolor="#123456"></v:roundrect><![endif]-->' + _BODY_LINE),), "strokecolor is '#123456'"),
    ("VML's second fill colour, which classic Outlook paints", ((_BODY_LINE, '<!--[if mso]><v:roundrect><v:fill color2="#123456"></v:fill></v:roundrect><![endif]-->' + _BODY_LINE),), "color2 is '#123456'"),
    ("a colour left at its initial value, the browser's black", ((_BODY_LINE, '<p style="color:initial;">x</p>' + _BODY_LINE),), "color is initial"),
    ("a link's colour reverted to the browser's blue", ((_BODY_LINE, '<a href="https://e.test/" style="color:revert;">x</a>' + _BODY_LINE),), "color is revert"),
    ("a link's colour rolled back a layer, to the browser's blue", ((_BODY_LINE, '<a href="https://e.test/" style="color:revert-layer;">x</a>' + _BODY_LINE),), "color is revert-layer"),
    ("the browser's link colour by its name", ((_BODY_LINE, '<p style="color:-webkit-link;">x</p>' + _BODY_LINE),), "color is -webkit-link"),
    ("a colour read from an attribute through attr()", ((_BODY_LINE, '<p data-c="#123456" style="color:attr(data-c type(<color>));">x</p>' + _BODY_LINE),), "color is attr("),
    ("a link that sets no colour of its own, which a client paints the browser's blue", ((_BODY_LINE, '<a href="https://e.test/">x</a>' + _BODY_LINE),), "<a> sets no colour of its own"),
    ("a link whose colour is left empty, which a client drops", ((_BODY_LINE, '<a href="https://e.test/" style="color:;">x</a>' + _BODY_LINE),), "<a> sets no colour of its own"),
    ("a colour written as hsl()", ((_BODY_LINE, '<p style="color:hsl(150 20% 30%);">x</p>' + _BODY_LINE),), "color is hsl("),
    ("a colour written as hsla()", ((_BODY_LINE, '<p style="color:hsla(150,20%,30%,1);">x</p>' + _BODY_LINE),), "color is hsla("),
    ("a colour written as hwb()", ((_BODY_LINE, '<p style="color:hwb(150 20% 30%);">x</p>' + _BODY_LINE),), "color is hwb("),
    ("a colour written as lab()", ((_BODY_LINE, '<p style="color:lab(40% -20 10);">x</p>' + _BODY_LINE),), "color is lab("),
    ("a colour written as lch()", ((_BODY_LINE, '<p style="color:lch(40% 20 150);">x</p>' + _BODY_LINE),), "color is lch("),
    ("a colour written as oklab()", ((_BODY_LINE, '<p style="color:oklab(0.5 -0.1 0.05);">x</p>' + _BODY_LINE),), "color is oklab("),
    ("a colour written as oklch()", ((_BODY_LINE, '<p style="color:oklch(0.5 0.1 150);">x</p>' + _BODY_LINE),), "color is oklch("),
    ("a colour written as color()", ((_BODY_LINE, '<p style="color:color(srgb 0.2 0.4 0.3);">x</p>' + _BODY_LINE),), "color is color("),
    ("a link whose hex is a digit short, which a browser drops", ((_BODY_LINE, '<a href="https://e.test/" style="color:#3C665;">x</a>' + _BODY_LINE),), "<a> sets no colour of its own"),
    ("a link whose hex has no #, which a browser drops", ((_BODY_LINE, '<a href="https://e.test/" style="color:3C6650;">x</a>' + _BODY_LINE),), "<a> sets no colour of its own"),
    ("a link whose colour is a misspelt name, which a browser drops", ((_BODY_LINE, '<a href="https://e.test/" style="color:gren;">x</a>' + _BODY_LINE),), "<a> sets no colour of its own"),
    ("a link whose colour is two values, which a browser drops", ((_BODY_LINE, '<a href="https://e.test/" style="color:#3C6650 #3C6650;">x</a>' + _BODY_LINE),), "<a> sets no colour of its own"),
    ("a link whose colour is a function no browser takes as one", ((_BODY_LINE, '<a href="https://e.test/" style="color:contrast-color(#3C6650);">x</a>' + _BODY_LINE),), "<a> sets no colour of its own"),
    ("a link coloured light-dark() of one colour, which a browser drops, as the page shows it", ((_BODY_LINE, _page_view_alone('<a href="https://e.test/" style="color:light-dark(#3C6650);">x</a>') + _BODY_LINE),), "<a> sets no colour of its own"),
    ("a link that sets its background alone", ((_BODY_LINE, '<a href="https://e.test/" style="background-color:#4F7A63;">x</a>' + _BODY_LINE),), "<a> sets no colour of its own"),
    ("a link with an empty href, still a link", ((_BODY_LINE, '<a href="">x</a>' + _BODY_LINE),), "<a> sets no colour of its own"),
    ("a link in Outlook's view alone that sets no colour of its own", ((_BODY_LINE, '<!--[if mso]><a href="https://e.test/">x</a><![endif]-->' + _BODY_LINE),), "<a> sets no colour of its own"),
    ("the mail's button link with its white a digit short, its label then link blue on the button", ((_BODY_LINE, '<a href="https://e.test/" style="display:inline-block;background-color:#4F7A63;color:#fffff;">Go</a>' + _BODY_LINE),), "<a> sets no colour of its own"),
    ("WebKit's active link colour by its name", ((_BODY_LINE, '<p style="color:-webkit-activelink;">x</p>' + _BODY_LINE),), "color is -webkit-activelink"),
    ("WebKit's focus ring colour by its name", ((_BODY_LINE, '<p style="color:-webkit-focus-ring-color;">x</p>' + _BODY_LINE),), "color is -webkit-focus-ring-color"),
    ("WebKit's text colour by its name", ((_BODY_LINE, '<p style="color:-webkit-text;">x</p>' + _BODY_LINE),), "color is -webkit-text"),
    ("a link whose colour carries a misspelt !important, which a browser drops", ((_BODY_LINE, '<a href="https://e.test/" style="color:#3C6650 !importnt;">x</a>' + _BODY_LINE),), "<a> sets no colour of its own"),
    ("a link whose hex ends in an escape, which a browser drops", ((_BODY_LINE, '<a href="https://e.test/" style="color:#3C6650\\9;">x</a>' + _BODY_LINE),), "<a> sets no colour of its own"),
    ("a link coloured light-dark() with a misspelt second colour, which a browser drops, as the page shows it", ((_BODY_LINE, _page_view_alone('<a href="https://e.test/" style="color:light-dark(#3C6650,gren);">x</a>') + _BODY_LINE),), "<a> sets no colour of its own"),
    ("the mail's button link with its white given as light-dark(inherit, white), which a browser drops, a CSS-wide keyword being a whole value alone, as the page shows it", ((_BODY_LINE, _page_view_alone('<a href="https://e.test/" style="display:inline-block;background-color:#4F7A63;color:light-dark(inherit,#FFFFFF);">Go</a>') + _BODY_LINE),), "<a> sets no colour of its own"),
    ("the mail's button link with its white given as light-dark(white, unset), which a browser drops, as the page shows it", ((_BODY_LINE, _page_view_alone('<a href="https://e.test/" style="display:inline-block;background-color:#4F7A63;color:light-dark(#FFFFFF,unset);">Go</a>') + _BODY_LINE),), "<a> sets no colour of its own"),
    ("the mail's button link with its white given as light-dark(initial, white), which a browser drops, as the page shows it", ((_BODY_LINE, _page_view_alone('<a href="https://e.test/" style="display:inline-block;background-color:#4F7A63;color:light-dark(initial,#FFFFFF);">Go</a>') + _BODY_LINE),), "<a> sets no colour of its own"),
    ("the mail's button link with its white given as light-dark(white, revert), which a browser drops, as the page shows it", ((_BODY_LINE, _page_view_alone('<a href="https://e.test/" style="display:inline-block;background-color:#4F7A63;color:light-dark(#FFFFFF,revert);">Go</a>') + _BODY_LINE),), "<a> sets no colour of its own"),
    ("the mail's button link with its white given as light-dark(revert-layer, white), which a browser drops, as the page shows it", ((_BODY_LINE, _page_view_alone('<a href="https://e.test/" style="display:inline-block;background-color:#4F7A63;color:light-dark(revert-layer,#FFFFFF);">Go</a>') + _BODY_LINE),), "<a> sets no colour of its own"),
    ("a link coloured light-dark(inherit, inherit), which a browser drops, as the page shows it", ((_BODY_LINE, _page_view_alone('<a href="https://e.test/" style="color:light-dark(inherit,inherit);">x</a>') + _BODY_LINE),), "<a> sets no colour of its own"),
    ("a link coloured light-dark() of three colours, which a browser drops, as the page shows it", ((_BODY_LINE, _page_view_alone('<a href="https://e.test/" style="color:light-dark(#3C6650,#3C6650,#3C6650);">x</a>') + _BODY_LINE),), "<a> sets no colour of its own"),
    ("a link coloured through var(), which Gmail drops (inferred)", ((_BODY_LINE, '<a href="https://e.test/" style="color:var(--brand,#3C6650);">x</a>' + _BODY_LINE),), "<a> sets no colour of its own"),
    ("a link coloured light-dark() of two tokens' colours, which classic Outlook's Word engine predates (inferred)", ((_BODY_LINE, '<a href="https://e.test/" style="color:light-dark(#1A1A17,#D7DADC);">x</a>' + _BODY_LINE),), "<a> sets no colour of its own"),
    # Pass.
    ("the shell as it is built", (), None),
    ("a body line in a token's colour", ((_BODY_LINE, '<p style="color:#3C6650;">x</p>' + _BODY_LINE),), None),
    ("a token's colour in small letters", ((_BODY_LINE, '<p style="color:#3c6650;">x</p>' + _BODY_LINE),), None),
    ("a colour in a comment, which no client reads", ((_BODY_LINE, '<!-- color:#123456 -->' + _BODY_LINE),), None),
    ("a colour in text, which is no style", ((_BODY_LINE, '<p>#123456 is a hex code.</p>' + _BODY_LINE),), None),
    ("a border with no colour", ((_BODY_LINE, '<p style="border:0;">x</p>' + _BODY_LINE),), None),
    ("no colour of its own, in a word: none, and the text's", ((_BODY_LINE, '<p style="background:transparent;border:1px solid currentcolor;">x</p>' + _BODY_LINE),), None),
    ("a bgcolor of transparent, which sets none", ((_BODY_LINE, '<table><tr><td bgcolor="transparent">x</td></tr></table>' + _BODY_LINE),), None),
    ("a bgcolor of a token's colour in small letters, spaces around it", ((_BODY_LINE, '<table><tr><td bgcolor=" #fbfaf6 ">x</td></tr></table>' + _BODY_LINE),), None),
    ("fonts named like colours", ((_BODY_LINE, '<p style="font:16px Gold,serif;font-family:Red Hat Text,sans-serif;">x</p>' + _BODY_LINE),), None),
    ("light-dark() of two tokens' colours", ((_BODY_LINE, '<p style="color:light-dark(#1A1A17,#D7DADC);">x</p>' + _BODY_LINE),), None),
    ("a link that takes its parent's colour", ((_BODY_LINE, '<a href="https://e.test/" style="color:inherit;">x</a>' + _BODY_LINE),), None),
    ("an anchor with no href, which a client paints as its text", ((_BODY_LINE, '<a name="x">x</a>' + _BODY_LINE),), None),
    ("VML in tokens' colours", ((_BODY_LINE, '<!--[if mso]><v:roundrect fillcolor="#3C6650" strokecolor="#3C6650"><v:fill color2="#FBFAF6"></v:fill></v:roundrect><![endif]-->' + _BODY_LINE),), None),
    ("a property named for the text, in a token's colour", ((_BODY_LINE, '<p style="-webkit-text-fill-color:#3C6650;">x</p>' + _BODY_LINE),), None),
    ("a colour unset, which takes the parent's", ((_BODY_LINE, '<p style="color:unset;">x</p>' + _BODY_LINE),), None),
    ("an empty bgcolor, which sets none", ((_BODY_LINE, '<table><tr><td bgcolor="">x</td></tr></table>' + _BODY_LINE),), None),
    ("a link coloured currentcolor, which takes its parent's", ((_BODY_LINE, '<a href="https://e.test/" style="color:currentcolor;">x</a>' + _BODY_LINE),), None),
    ("a link whose token colour holds beside a misspelt one, which a browser drops", ((_BODY_LINE, '<a href="https://e.test/" style="color:#3C6650;color:gren;">x</a>' + _BODY_LINE),), None),
    ("a link coloured light-dark() of two tokens' colours that classic Outlook does not see, beside one in a token's hex that it alone sees", ((_BODY_LINE, _page_view_alone('<a href="https://e.test/" style="color:light-dark(#1A1A17,#D7DADC);">x</a>') + _BODY_LINE),), None),
    ("a link coloured unset, which takes its parent's", ((_BODY_LINE, '<a href="https://e.test/" style="color:unset;">x</a>' + _BODY_LINE),), None),
    ("a transition of the background, a property's name and no system colour", ((_BODY_LINE, '<p style="transition:background 0.2s;">x</p>' + _BODY_LINE),), None),
    ("a transition's property, the background, a property's name and no system colour", ((_BODY_LINE, '<p style="transition-property:background;">x</p>' + _BODY_LINE),), None),
    ("a change the page signals to the background, a property's name and no system colour", ((_BODY_LINE, '<p style="will-change:background;">x</p>' + _BODY_LINE),), None),
    ("a text fill colour under WebKit's prefix, a hex no token holds, which Blink and WebKit paint", ((_BODY_LINE, '<p style="-webkit-text-fill-color:#123456;">x</p>' + _BODY_LINE),), _NO_TOKEN),
    ("a transition of the background under WebKit's prefix, a property's name and no system colour", ((_BODY_LINE, '<p style="-webkit-transition:background 0.2s;">x</p>' + _BODY_LINE),), None),
    ("a transition's property written in capitals, the background, a property's name and no system colour", ((_BODY_LINE, '<p style="TRANSITION-PROPERTY:background;">x</p>' + _BODY_LINE),), None),
]
# One page for each system colour a browser paints by its name, written out so narrowing the reader fails a case.
COLOURS += [
    (f"the system colour {name} by its name", ((_BODY_LINE, f'<p style="color:{name};">x</p>' + _BODY_LINE),), f"color is {name}")
    for name in (
        "Canvas", "CanvasText", "LinkText", "VisitedText", "ActiveText", "ButtonFace", "ButtonText", "ButtonBorder", "Field",
        "FieldText", "Highlight", "HighlightText", "SelectedItem", "SelectedItemText", "Mark", "MarkText", "GrayText",
        "AccentColor", "AccentColorText",
        # CSS Color 4's deprecated system colours, which Chromium 141 paints all the same
        "ActiveBorder", "ActiveCaption", "AppWorkspace", "Background", "ButtonHighlight", "ButtonShadow", "CaptionText",
        "InactiveBorder", "InactiveCaption", "InactiveCaptionText", "InfoBackground", "InfoText", "Menu", "MenuText",
        "Scrollbar", "ThreeDDarkShadow", "ThreeDFace", "ThreeDHighlight", "ThreeDLightShadow", "ThreeDShadow", "Window",
        "WindowFrame", "WindowText",
    )
]


@pytest.mark.parametrize("edits, expected", [case[1:] for case in COLOURS], ids=[case[0] for case in COLOURS])
def test_the_colour_check_scores_every_planted_page(edits, expected):
    problems = colour_problems(_scored(_planted(_WIDTH_BODY), edits))
    if expected is None:
        assert not problems, problems
    else:
        assert any(expected in problem and _NO_TOKEN in problem for problem in problems), f"expected {expected!r}, got {problems}"


def test_the_planted_lists_keep_their_counts():
    """Each list's pages that must fail and that must pass. Equalities, not floors, so a page dropped after one
    is added still fails (lessons/test-allowlist-caps-are-equalities.md): change a count in the diff that adds or
    drops a page, and say why one goes."""
    counts = {
        "TEXT_SIZES": (sum(isinstance(c[-1], str) for c in TEXT_SIZES), sum(c[-1] is None for c in TEXT_SIZES)),
        "LONG_RUNS": (sum(isinstance(c[-1], str) for c in LONG_RUNS), sum(c[-1] is None for c in LONG_RUNS)),
        "WIDTHS": (sum(isinstance(c[-1], str) for c in WIDTHS), sum(c[-1] is None for c in WIDTHS)),
        "LENDS": (sum(c[-1] is True for c in LENDS), sum(c[-1] is False for c in LENDS)),
        "REACHES": (sum(c[-1] is True for c in REACHES), sum(c[-1] is False for c in REACHES)),
        "VIEWPORTS": (sum(c[-1] is False for c in VIEWPORTS), sum(c[-1] is True for c in VIEWPORTS)),
        "COLOURS": (sum(isinstance(c[-1], str) for c in COLOURS), sum(c[-1] is None for c in COLOURS)),
    }
    assert counts == {
        "TEXT_SIZES": (40, 20),
        "LONG_RUNS": (91, 50),
        "WIDTHS": (270, 169),
        "LENDS": (6, 4),
        "REACHES": (6, 4),
        "VIEWPORTS": (3, 3),
        "COLOURS": (104, 26),
    }, "a planted page was added or dropped: keep these counts equal to the lists in the same diff"
    for name, cases in (("TEXT_SIZES", TEXT_SIZES), ("LONG_RUNS", LONG_RUNS), ("WIDTHS", WIDTHS), ("LENDS", LENDS), ("REACHES", REACHES), ("VIEWPORTS", VIEWPORTS), ("COLOURS", COLOURS)):
        labels = [case[0] for case in cases]
        assert len(set(labels)) == len(labels), f"each page {name} plants has a name of its own"
