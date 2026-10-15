"""Gate: the mail's header and footer line are the brand template's, and the page around them holds.

``docs/brand/templates/email-header.html`` is the editable preview of the header (the lockup, a
hairline, the marked tagline) and the footer line, and ``email_service._wrap_html`` carries its
markup, ported (CLAUDE.md rule 12: a change to one is a change to the other). The two are compared
tag for tag and text for text, plain comments aside, with whitespace counted as a browser renders it:
- a run of ASCII whitespace is one space, and a no-break or an em space renders as itself;
- whitespace beside a table's own tags renders nothing, and is dropped;
- a quoted attribute value is compared as written.

One difference is allowed: the preview's tile is inline SVG in a cell Outlook skips, and the mail's is
the hosted raster the template's note spells (``<img src="{base}/assets/earningsnerd-appicon.png" ...>``),
on ``FRONTEND_URL``. The page carries the header and the footer line once each, the header above the
panel and the footer line below it. Around them, the page:

- puts the body and the footer in the panel's cells, each once and each in a cell of its own, and
  carries one wordmark in its text, the header's;
- carries no inline SVG, which Gmail and Outlook drop, and sets no viewport: it is 600 px wide, and a
  mail view fits a page that sets none to its screen;
- pads no table, since classic Outlook ignores a table's padding and the body would sit against the
  panel's border, out of line with the header.
"""
import re
from pathlib import Path

from app.config import settings
from app.services import email_service

TEMPLATE = Path(__file__).resolve().parents[3] / "docs" / "brand" / "templates" / "email-header.html"
_PLAIN_COMMENT = re.compile(r"<!--\s(?:(?!-->).)*-->", re.DOTALL)  # an Outlook conditional has no space after <!--
_TILE_IN_NOTE = re.compile(r'<img src="\{base\}[^>]*>', re.DOTALL)
_TABLE_TAG = re.compile(r"</?(?:table|tbody|tr|td)\b")
# HTML collapses ASCII whitespace alone: a no-break or an em space renders as itself.
_SPACE = " \t\n\r\f"
_SPACES = re.compile(f"[{_SPACE}]+")
_QUOTED = re.compile(r"""("[^"]*"|'[^']*')""")


def _tag(piece: str) -> str:
    """A tag with the whitespace between its attributes made one space, its quoted values kept as written."""
    return "".join(part if _QUOTED.fullmatch(part) else _SPACES.sub(" ", part) for part in _QUOTED.split(piece))


def _tokens(markup: str) -> list[str]:
    """The markup's tags and text, plain comments dropped, spaced as a browser renders them."""
    pieces = [piece for piece in re.split(r"(<[^>]+>)", _PLAIN_COMMENT.sub("", markup)) if piece]
    tokens = []
    for i, piece in enumerate(pieces):
        before, after = pieces[i - 1 : i], pieces[i + 1 : i + 2]
        if piece.startswith("<"):
            tokens.append(_tag(piece))
        elif piece.strip(_SPACE):
            text = _SPACES.sub(" ", piece)
            text = text.lstrip(_SPACE) if before and _TABLE_TAG.match(before[0]) else text
            tokens.append(text.rstrip(_SPACE) if after and _TABLE_TAG.match(after[0]) else text)
        elif not any(_TABLE_TAG.match(near) for near in before + after):
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
    text = re.sub(r"<[^>]+>", "", shell)
    assert len(re.findall(r"Earnings\s*Nerd", text, re.IGNORECASE)) == 1, "the page carries one wordmark, the header's"

    assert "<svg" not in page.lower(), "Gmail and Outlook drop inline SVG"
    assert 'name="viewport"' not in page, "a 600 px page sets no viewport, so a mail view fits it to its screen"
    padded = [
        t for t in tokens if t.lower().startswith("<table") and re.search(r"""style\s*=\s*(["'])(?:(?!\1).)*padding""", t, re.IGNORECASE)
    ]
    assert not padded, f"classic Outlook ignores a table's padding: pad its cells instead: {padded}"
