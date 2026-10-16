"""A model of how Blink and WebKit read a mail page's inline styles, for the gates that hold the shell's rules.

``tests/unit/test_mail_header_template.py`` states the rules and plants their cases, and
``tests/unit/test_mail_rendered_addresses.py`` holds every page the mail module sends to them:
- ``text_size_problems``: the header keeps its set size where a phone view enlarges small text, and every
  other line is left to the view;
- ``long_run_problems``: a run of characters with nowhere to wrap, such as a link with its token, a report's
  hash or a name typed as an address, can break anywhere once it is long enough to fill the panel's text
  column on the narrowest phone, so it cannot hold the page wider than the screen;
- ``reach_problems``: that rule reaches no table, where it would split a column of amounts, so it sits on
  the lines that print such a run;
- ``fixed_width_problems``: no box a client other than classic Outlook shows is set wider than the room its
  parent gives it on that phone;
- ``outlook_width_problems``: classic Outlook, which reads no ``max-width``, holds each column capped at
  600 px at 600 px, through a table only its conditional comments show;
- ``viewports``: the viewports a page sets, wherever it sets them.

A page is read as a browser builds it, by ``tinyhtml5``, the WHATWG tree builder (``requirements.in``): an
end tag a browser implies is implied, a ``/>`` on an element that is not void is ignored, the first of two
same-named attributes is kept, a formatting element left open is opened again where the parser opens it,
and text a table cannot hold moves before it. A comment holds no markup, so what Outlook's conditional
comments hold is read only in Outlook's view (``outlook_view``). Each element's ``style`` attribute is read as
CSS reads one, by ``tinycss2``: comments and escapes decoded, a declaration its property cannot take
dropped, an important declaration over a normal one, and among equals the last. The text properties read
here are inherited: ``inherit`` and ``unset`` take the parent's value, ``revert`` the element's own default,
such as ``<pre>``'s, or the parent's. A cell's ``nowrap`` attribute and a table's ``width``, ``border``,
``cellpadding`` and ``cellspacing`` are presentational hints, below every declaration of a ``style``: ``revert``
removes them with the style, and ``revert-layer``, which rolls back to the layer below, keeps them (measured in
Chromium 141).

Two engines enlarge text, and each reads its own names:
- Blink, which Android's mail apps run, reads ``text-size-adjust`` and ``-webkit-text-size-adjust`` as one
  property;
- Apple's WebKit, which every iOS mail app runs, iOS Mail and the Gmail app among them, reads the prefixed
  name alone: caniuse marks iOS Safari's support as prefixed only, from 5 through 26.6
  (``frontend/node_modules/caniuse-lite``, feature ``text-size-adjust``).

So a line's size is read once per engine, and each reading must hold the rule.

A run ends where a line may wrap: at a space, a tab, a line break or one of the Unicode spaces a line may
break after, where the line wraps; at ``<wbr>`` or a zero-width space there; at ``<br>`` or a line break the
line keeps; and at the edge of a block, a table's part or an element placed whole, such as an image or a
button. It goes on across the tags of every other element, an element the reader does not know and one the
page hides alike, so a link split by markup is read whole, and across a float (a ``float`` in its style, its
parent's under ``inherit``, or an image's or a table's ``align`` of left or right) or a box positioned absolute
or fixed, which a browser takes out of the line: the text on either side of one joins, and its own text
forms runs of its own. A ``<br>`` breaks the line however it is styled. Within a run, a character can break where ``overflow-wrap:anywhere``,
``word-break:break-word`` or ``break-all``, or ``line-break:anywhere`` reaches it: each lets a word break and
shrinks the narrowest width a table can give its cell, which ``overflow-wrap:break-word`` alone does not. Two
aliases are read once per engine, since the engines differ on them: ``word-wrap``, read with
``overflow-wrap``, whose ``anywhere`` Blink takes and WebKit may not, and ``-webkit-line-break``, read with
``line-break``, whose ``anywhere`` Blink drops (in Chromium 141 ``CSS.supports`` refuses it, and takes the
alias's other values) and WebKit may take. So a run breaks in every engine only where another of those forms
reaches it, and a page lends the rule wherever either engine may take it (``lent_runs``, ``reach_problems``).
That Blink breaks under each form is measured; that WebKit does is inferred from the specifications it
implements. ``all`` sets every property read here to its keyword, in its place among the declarations.

A line wraps where both kinds of engine wrap it: one that predates ``text-wrap-mode`` reads ``white-space``
alone, in its single keywords (it drops one written in its longhands' words, such as ``collapse wrap``), and one
that reads it takes the last of ``white-space``, ``text-wrap`` and ``text-wrap-mode``, the first two being
shorthands that set it. So ``white-space:nowrap`` or ``pre``, ``text-wrap-mode:nowrap`` and a
``text-wrap`` with ``nowrap`` keep a run on one line, spaces and all, as do ``<pre>``, ``<nobr>`` and a cell's
``nowrap`` attribute, and a ``text-wrap-mode:wrap`` does not undo a ``white-space:nowrap``. A line keeps its
line breaks where both kinds keep them, and its spaces where either does: one that reads
``white-space-collapse`` takes the last of it and ``white-space``, the older one ``white-space`` alone, and
spaces a line keeps count in its runs. A
value Chromium refuses, such as ``white-space:preserve-spaces`` or ``text-wrap:avoid-orphans``, is dropped, as
there.

Each box is held to the room its parent gives it on the narrowest phone: 320 px for the page, less each box's
horizontal margins, borders and padding, as its ``style`` sets them, side by side, shorthand and longhand, in
px or another absolute unit, or a percentage of the room; else as the attributes HTML maps set them: a
cell's padding from its table's ``cellpadding`` (1 px without one), a table's spacing from its ``cellspacing``
and its border from its ``border``, an image's margins from its ``hspace`` and its border from its ``border``;
else as a browser's own style sheet does: a body's 8 px margins, a list's 40 px indent, a blockquote's and a
figure's 40 px margins, a table's 2 px spacing. ``revert`` drops the attributes' values and ``revert-layer``
keeps them (measured in Chromium 141). The shell's own boxes leave a body ``WIDEST_FIXED``. A box's width is
its ``width`` in its ``style``, else its ``width`` attribute where HTML maps one (a table's, a cell's, an
image's, an object's or an embed's): a number is pixels, a number then ``%`` a percentage of the room. A
table, a button, a select, a meter, a progress and an input drawn as a button or a box count their border and
padding in their width, as a browser's own style sheet sets them, and so does a cell set in percent, which
takes its column's share of the table (measured in Chromium 141; that WebKit's table layout does too is
inferred); another box, a ``<div>`` set ``display:table`` among them, adds them. A box set wider than its room
fails, whether a fixed width, a percentage over 100% or a ``min-width`` sets it, and so do margins, borders and
padding that leave a box's content no room. A ``max-width`` in pixels caps a width; one in percent holds an
image or another replaced element alone, since in a table's cell it does not hold the box's own content (CSS
Sizing 3, its cyclic percentages). An image with no width shows at its natural size, which the reader does
not know, so it fails unless a ``max-width`` holds it, and then it may show as wide as that, with its margins,
borders and padding added. A
width set by the font or the screen, such as ``em`` or ``vw``, by the parent (``inherit``), or by the content
(``max-content``) is refused rather than guessed. An inline element's box takes no width. A cell's room is
its table's whole room, so a cell set wider than its table fails: Chromium squeezes it, while CSS 2.1's
automatic table layout reads a cell's width as its minimum, and so does a column (``<col>``); under
``table-layout:fixed`` a table keeps both, and overflows.

Outlook's view is the page as classic Outlook reads its conditional comments, as Outlook 2016 and later
(``mso 16``) take their conditions: ``mso`` and ``vml`` true, a version compared, ``IE`` false, and ``!``,
``&``, ``|`` and brackets as written. What a condition Outlook takes holds shows there, and what one it does not
take holds does not, in a comment or in a revealed block (``<![if !mso]>``); a condition the reader cannot
parse hides what it holds. A column capped at 600 px is held when the nearest table around it set to a fixed
width is 600 px wide.

The reader errs toward asking for the rule: it counts no break a browser may take at a hyphen or after a
question mark, or at a ``<wbr>`` under ``nowrap``, where Chromium breaks, and no width that holds a run in, such
as a fixed table layout or a clipped box, so it may ask for the rule where a browser would fit the run. It
does not measure what a box's content sets, and so may pass it: a table of amounts whose columns cannot
narrow, a widget's own width, a cell's share of its table when the table has more than one column (each cell
is given the table's whole room), images or other boxes kept on one line by ``nowrap`` or ``<nobr>``, a flex
row's items side by side, a box shifted by a relative offset or a
transform, a first line set in by ``text-indent``, the padding an inline box adds to its line, and a run in a
box narrower than the panel's column, which is measured against the column. ``reach_problems`` allows the
break rule on a cell of its own, which must hold no amount: on an amount's cell it splits the amount. The header is the table capped at 600 px (its
``max-width``) that holds the wordmark, the name split by markup into its two styles, and a page carries one.
What the reader does not resolve, it refuses rather than guesses: a ``<style>`` block, an SVG's or MathML's
included, or a linked stylesheet, whose selectors it does not match, and a value one of its properties takes
from a function, such as ``calc()`` or ``var()``. It reads no text the page does not show: what
``display:none`` or the ``hidden`` attribute hides, what a browser's own style sheet hides (the head, and an
input of type hidden and an audio without its controls, whatever display a page gives them), nor an image's
``alt``, which shows only where images are blocked. Text hidden another way, at ``font-size:0`` or in a box
clipped to nothing, it reads as shown.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass, replace

import tinycss2
import tinyhtml5
from tinycss2.ast import Node

# A run this long, with nowhere to break, can fill the panel's text column on the narrowest phone. In
# Chromium's phone view at 320 px, where the mail's font stacks resolve to Inter here, the shortest runs of a
# token that held the page wider than the screen were 22 characters at 16 px and 21 in bold, the panel's
# largest text, and 18 at 20 px. The check takes 18, three under the panel's own, so a run of wide letters, or
# one set up to 20 px, is flagged before it fills the column; a larger font is not held (17 capitals in bold at
# 24 px already fill it), and a phone's own font sets the widths there
# (lessons/test-layout-numbers-are-one-environments-run.md). The check holds the view the shell's viewport sets.
# A view that ignores the viewport, lays the page out wider and enlarges its text, as no mail client is known to,
# widened the panel from about 16 characters of the token at 320 px, fewer of wide letters, and a threshold three
# under that, the margin the check keeps in the view it holds, would take the header's own tagline (15
# characters, "shows its work.") for a long run: the check does not hold that view.
LONG_RUN = 18
# The narrowest phone a mail lays out on, and the room the shell leaves a body there: 320 px, less the page's
# gutters (12 px a side) and the panel's border and padding (33 px a side).
NARROWEST_SCREEN = 320
WIDEST_FIXED = NARROWEST_SCREEN - 2 * 12 - 2 * 33

_GLOBAL = frozenset({"inherit", "initial", "unset", "revert", "revert-layer"})
_KEYWORDS = {  # a one-word value each property can take
    "overflow-wrap": {"normal", "break-word", "anywhere"},
    "word-wrap": {"normal", "break-word", "anywhere"},
    "word-break": {"normal", "break-all", "keep-all", "break-word", "auto-phrase"},
    "line-break": {"auto", "loose", "normal", "strict", "anywhere"},
    "-webkit-line-break": {"auto", "loose", "normal", "strict", "anywhere", "after-white-space"},
    "text-wrap-mode": {"wrap", "nowrap"},
    "white-space-collapse": {"collapse", "preserve", "preserve-breaks", "break-spaces"},
    "box-sizing": {"content-box", "border-box"},
    "float": {"left", "right", "none", "inline-start", "inline-end"},
    "position": {"static", "relative", "absolute", "fixed", "sticky"},
    "border-collapse": {"separate", "collapse"},
    "table-layout": {"auto", "fixed"},
}
_SIZING = frozenset({"min-content", "max-content", "fit-content", "stretch", "-webkit-fill-available"})
_WIDTH_WORDS = {"width": _SIZING | {"auto"}, "min-width": _SIZING | {"auto"}, "max-width": _SIZING | {"none"}}
_ABSOLUTE = {"px": 1.0, "pt": 4 / 3, "pc": 16.0, "in": 96.0, "cm": 96 / 2.54, "mm": 96 / 25.4, "q": 96 / 101.6}
_RELATIVE = frozenset({
    "em", "rem", "ex", "rex", "ch", "rch", "cap", "rcap", "ic", "ric", "lh", "rlh", "vw", "vh", "vi", "vb", "vmin",
    "vmax", "svw", "svh", "svi", "svb", "svmin", "svmax", "lvw", "lvh", "lvi", "lvb", "lvmin", "lvmax", "dvw", "dvh",
    "dvi", "dvb", "dvmin", "dvmax", "cqw", "cqh", "cqi", "cqb", "cqmin", "cqmax",
})
# The box properties read here, each as the sides it sets: a margin, a padding, a border's width or its style,
# on the left and the right, as a line of text runs left to right.
_BOX = {
    **{f"{kind}{suffix}": (kind, sides) for kind in ("margin", "padding") for suffix, sides in (
        ("", "box"), ("-left", "left"), ("-right", "right"), ("-inline", "inline"), ("-inline-start", "left"),
        ("-inline-end", "right"),
    )},
    **{f"border{side}-{part}": (f"border-{part}", sides) for part in ("width", "style") for side, sides in (
        ("", "box"), ("-left", "left"), ("-right", "right"), ("-inline", "inline"), ("-inline-start", "left"),
        ("-inline-end", "right"),
    )},
    **{f"border{side}": ("border", sides) for side, sides in (
        ("", "both"), ("-left", "left"), ("-right", "right"), ("-inline", "both"), ("-inline-start", "left"),
        ("-inline-end", "right"),
    )},
}
_BORDER_STYLES = frozenset({"none", "hidden", "dotted", "dashed", "solid", "double", "groove", "ridge", "inset", "outset"})
_BORDER_WIDTHS = {"thin": "1px", "medium": "3px", "thick": "5px"}
_READ = frozenset({
    *_KEYWORDS, *_WIDTH_WORDS, *_BOX, "border-spacing", "text-size-adjust", "-webkit-text-size-adjust", "white-space",
    "text-wrap", "display", "all",
})
_WHITE_SPACE = {  # each keyword as (keeps line breaks, wraps)
    "normal": (False, True), "nowrap": (False, False), "pre": (True, False),
    "pre-wrap": (True, True), "pre-line": (True, True), "break-spaces": (True, True),
}
_MODE_OF = {keyword: "wrap" if wraps else "nowrap" for keyword, (_, wraps) in _WHITE_SPACE.items()}
_COLLAPSE_OF = {
    "normal": "collapse", "nowrap": "collapse", "pre": "preserve", "pre-wrap": "preserve", "pre-line": "preserve-breaks",
    "break-spaces": "break-spaces",
}
# The shorthands' other spellings, their longhands' words: at most one word from each set. Chromium refuses
# white-space:preserve-spaces and text-wrap:avoid-orphans, which these leave out.
_COLLAPSE_WORDS = {"collapse": False, "preserve": True, "preserve-breaks": True, "break-spaces": True}
_MODE_WORDS = {"wrap": True, "nowrap": False}
_TEXT_WRAP_STYLES = frozenset({"auto", "balance", "stable", "pretty"})
# The display values Blink and WebKit both take: one keyword, or an outer and an inner type with list-item. A
# value either engine drops, such as run-in or ruby-base, leaves the element its own display.
_DISPLAY_ONE = frozenset({
    "block", "inline", "flow", "flow-root", "table", "flex", "grid", "ruby", "math", "list-item", "contents", "none",
    "inline-block", "inline-table", "inline-flex", "inline-grid", "table-row-group", "table-header-group",
    "table-footer-group", "table-row", "table-cell", "table-column-group", "table-column", "table-caption",
    "-webkit-box", "-webkit-inline-box",
})
_DISPLAY_OUTER = frozenset({"block", "inline"})
_DISPLAY_INNER = frozenset({"flow", "flow-root", "table", "flex", "grid", "ruby", "math"})
# The elements a browser's own style sheet gives a white-space, and so a wrap mode.
_OWN_WHITE_SPACE = {"pre": "pre", "listing": "pre", "xmp": "pre", "plaintext": "pre", "textarea": "pre-wrap", "nobr": "nowrap"}
# The elements a run cannot cross: blocks and a table's parts, the elements placed whole, and <br>.
_RUN_EDGES = frozenset({
    "address", "article", "aside", "blockquote", "body", "caption", "center", "col", "colgroup", "dd", "details",
    "dialog", "dir", "div", "dl", "dt", "fieldset", "figcaption", "figure", "footer", "form", "frameset", "h1", "h2",
    "h3", "h4", "h5", "h6", "header", "hgroup", "hr", "html", "legend", "li", "listing", "main", "menu", "nav", "ol",
    "optgroup", "option", "p", "plaintext", "pre", "search", "section", "summary", "table", "tbody", "td", "tfoot",
    "th", "thead", "tr", "ul", "xmp",
    "audio", "button", "canvas", "iframe", "img", "input", "marquee", "math", "meter", "progress", "select", "svg",
    "textarea", "video",
    "br",
})
# The elements a browser's own style sheet hides, and so lays nothing out for, unless a page gives one a display;
# <audio> without its controls and <input type="hidden"> it hides whatever display a page gives them, and a
# <dialog> that is not open it hides too.
_UNSHOWN = frozenset({
    "area", "base", "basefont", "datalist", "head", "link", "meta", "noembed", "noframes", "param", "rp", "script",
    "source", "style", "template", "title", "track",
})
# The box each element makes, as a browser's own style sheet gives it, for the room it takes and leaves.
_TABLE_PARTS = frozenset({"tbody", "thead", "tfoot", "tr"})
_CELLS = frozenset({"td", "th"})
_REPLACED = frozenset({"img", "video", "iframe", "canvas", "svg", "object", "embed"})  # placed whole, at a width of their own
_WIDGETS = frozenset({"audio", "button", "input", "marquee", "meter", "progress", "select", "textarea"})
_WIDTH_HINTED = frozenset({"table", "td", "th", "col", "colgroup", "hr", "img", "iframe", "video", "canvas", "object", "embed"})
# The elements a browser's own style sheet sizes border-box, and the input types it draws as a button or a box.
_UA_BORDER_BOX = frozenset({"table", "button", "select", "meter", "progress"})
_BORDER_BOX_INPUTS = frozenset({"button", "submit", "reset", "checkbox", "radio"})
# The elements whose align of left or right floats them, and whose hspace sets their side margins.
_ALIGN_FLOATS = frozenset({"img", "table", "object", "embed", "iframe"})
_HSPACED = frozenset({"img", "object", "embed", "iframe"})
# The functions that give a colour alone, which a border shorthand may take without setting a width.
_COLOUR_FUNCTIONS = frozenset({"rgb", "rgba", "hsl", "hsla", "hwb", "lab", "lch", "oklab", "oklch", "color", "color-mix", "light-dark"})
_UA_MARGIN = {"body": (8.0, 8.0), "blockquote": (40.0, 40.0), "figure": (40.0, 40.0), "dd": (40.0, 0.0), "fieldset": (2.0, 2.0)}
_UA_PADDING = {"ul": (40.0, 0.0), "ol": (40.0, 0.0), "menu": (40.0, 0.0), "dir": (40.0, 0.0), "fieldset": (12.0, 12.0), "button": (6.0, 6.0)}
_UA_BORDER = {"fieldset": 2.0, "button": 2.0, "hr": 1.0}
_SPACE = " \t\n\r\f"  # HTML's whitespace, which a line of text is stripped of
# Where a line may wrap: ASCII spaces and line breaks, and the Unicode spaces a line may break after. A form
# feed, a no-break space, a figure space and a narrow no-break space are no such place.
_WRAP_SPACES = " \t\n\r\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2008\u2009\u200a\u205f\u3000"
_ZERO_WIDTH_SPACE = "\u200b"
_INVISIBLE = dict.fromkeys(map(ord, "\u00ad\u200b\u200c\u200d\u2060\ufeff"))  # characters that render as nothing
# A conditional comment: its condition, whether a client other than Outlook shows what it holds too, and that.
_CONDITIONAL = re.compile(r"<!--\[if\s+([^\]]+)\]>(<!-->)?(.*?)(?:<!--)?<!\[endif\]-->", re.DOTALL | re.IGNORECASE)
# A revealed block, which every client but the ones its condition excludes shows.
_REVEALED = re.compile(r"<!\[if\s+([^\]]+)\]>(.*?)<!\[endif\]>", re.DOTALL | re.IGNORECASE)
_CONDITION = re.compile(r"\s*(\(|\)|!|&|\||[a-z]+|[0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
# What classic Outlook 2016 and later take in a condition, at their versions; IE, and what else it names, it does not.
_OUTLOOK = {"mso": 16.0, "vml": 1.0}
_COMPARISONS = {"lt": float.__lt__, "lte": float.__le__, "gt": float.__gt__, "gte": float.__ge__}
_SLACK = 0.5  # px, for the sums of widths written in other units


def _number(value: float) -> str:
    """A CSS number as the reader compares it, written out in full."""
    return f"{value:f}".rstrip("0").rstrip(".")


def _px(value: str) -> float:
    """An absolute length as the reader compares it, in px."""
    unit = value.lstrip("0123456789.")
    return float(value[: len(value) - len(unit)]) * _ABSOLUTE[unit]


def _length(token: Node) -> str | None:
    """A margin's, a padding's or a border width's token as the reader compares it: px, a percentage, auto or
    refused, which the font or the screen sets; None when it is none of those."""
    if token.type == "dimension" and token.lower_unit in _ABSOLUTE:
        return _number(token.value * _ABSOLUTE[token.lower_unit]) + "px"
    if token.type == "dimension" and token.lower_unit in _RELATIVE:
        return "refused"
    if token.type == "percentage":
        return _number(token.value) + "%"
    if token.type == "number" and token.value == 0:
        return "0px"
    if token.type == "ident" and token.lower_value == "auto":
        return "auto"
    return None


def _sides(kind: str, sides: str, values: list[str]) -> list[tuple[str, str]] | None:
    """The left and right longhands a box declaration sets, with their values, or None when its values do not
    fit its form."""
    if sides in ("left", "right"):
        return [(f"{kind}-{sides}" if kind in ("margin", "padding") else f"border-{sides}-{kind[7:]}", values[0])] if len(values) == 1 else None
    if sides == "inline" and 1 <= len(values) <= 2:
        left, right = values[0], values[-1]
    elif sides == "box" and 1 <= len(values) <= 4:
        right = values[1] if len(values) > 1 else values[0]
        left, right = (values[3] if len(values) == 4 else right), right
    else:
        return None
    if kind in ("margin", "padding"):
        return [(f"{kind}-left", left), (f"{kind}-right", right)]
    return [(f"border-left-{kind[7:]}", left), (f"border-right-{kind[7:]}", right)]


def _box_values(name: str, tokens: list[Node]) -> list[tuple[str, str]] | None:
    """The longhands a box declaration sets, each with its value, or None when its property cannot take it."""
    kind, sides = _BOX[name]
    parts = [token for token in tokens if token.type != "whitespace"]
    if len(parts) == 1 and parts[0].type == "ident" and parts[0].lower_value in _GLOBAL:
        keyword = parts[0].lower_value
        if kind == "border":
            names = [*(f"border-{side}-{part}" for side in ("left", "right") for part in ("width", "style"))]
            return [(longhand, keyword) for longhand in names if sides == "both" or f"-{sides}-" in longhand]
        found = _sides(kind, "inline" if sides == "box" else sides, [keyword])
        return found
    if kind == "border":  # a width, a style and a colour, in any order; one left out takes its initial value
        width = [_BORDER_WIDTHS.get(part.lower_value) if part.type == "ident" else _length(part) for part in parts]
        widths = [value for value in width if value not in (None, "auto")]
        styles = [part.lower_value for part in parts if part.type == "ident" and part.lower_value in _BORDER_STYLES]
        if len(widths) > 1 or len(styles) > 1 or any(value and value.endswith("%") for value in widths):
            return None
        chosen = (widths or ["3px"])[0], (styles or ["none"])[0]
        found = []
        for side in ("left", "right") if sides == "both" else (sides,):
            found += [(f"border-{side}-width", chosen[0]), (f"border-{side}-style", chosen[1])]
        return found
    if kind == "border-style":
        values = [part.lower_value for part in parts if part.type == "ident" and part.lower_value in _BORDER_STYLES]
    elif kind == "border-width":
        values = [_BORDER_WIDTHS.get(part.lower_value) if part.type == "ident" else _length(part) for part in parts]
        values = [value for value in values if value not in ("auto",)]
        if any(value is None or value.endswith("%") for value in values):
            return None
    else:
        values = [_length(part) for part in parts]
        if any(value is None for value in values) or (kind == "padding" and any(value in ("auto",) or value.startswith("-") for value in values)):
            return None
    if len(values) != len(parts):
        return None
    return _sides(kind, sides, values)


def _value(name: str, tokens: list[Node]) -> str | None:
    """A declaration's value as the reader compares it, or None when its property cannot take it."""
    parts = [token for token in tokens if token.type != "whitespace"]  # tinycss2 has dropped the comments
    if name in ("text-size-adjust", "-webkit-text-size-adjust"):
        if len(parts) == 1 and parts[0].type == "percentage" and parts[0].value >= 0:
            return f"{parts[0].value:g}%"
        if len(parts) == 1 and parts[0].type == "ident" and parts[0].lower_value in _GLOBAL | {"auto", "none"}:
            return parts[0].lower_value
        return None
    if name in _WIDTH_WORDS:
        part = parts[0] if len(parts) == 1 else None
        if part is not None and part.type == "dimension" and part.value >= 0 and part.lower_unit in {*_ABSOLUTE, *_RELATIVE}:
            return _number(part.value) + part.lower_unit
        if part is not None and part.type == "percentage" and part.value >= 0:
            return _number(part.value) + "%"
        if part is not None and part.type == "number" and part.value == 0:
            return "0px"
        if part is not None and part.type == "ident" and part.lower_value in _GLOBAL | _WIDTH_WORDS[name]:
            return part.lower_value
        return None
    if name == "border-spacing":  # the horizontal spacing, in px
        if len(parts) == 1 and parts[0].type == "ident" and parts[0].lower_value in _GLOBAL:
            return parts[0].lower_value
        values = [_length(part) for part in parts]
        if not 1 <= len(values) <= 2 or any(value is None or value in ("auto",) or value.endswith("%") or value.startswith("-") for value in values):
            return None
        return values[0]
    if not parts or any(part.type != "ident" for part in parts):
        return None
    words = [part.lower_value for part in parts]
    if len(words) == 1 and words[0] in _GLOBAL:
        return words[0]
    if name == "display":
        if len(words) == 1:
            return words[0] if words[0] in _DISPLAY_ONE else None
        outer = [word for word in words if word in _DISPLAY_OUTER]
        inner = [word for word in words if word in _DISPLAY_INNER]
        item = [word for word in words if word == "list-item"]
        if len(outer) + len(inner) + len(item) != len(words) or max(len(outer), len(inner), len(item)) > 1:
            return None
        return " ".join(words) if not (item and inner and inner[0] not in ("flow", "flow-root")) else None
    if name == "white-space":
        if len(words) == 1 and words[0] in _WHITE_SPACE:
            return words[0]
        collapse = [word for word in words if word in _COLLAPSE_WORDS]
        mode = [word for word in words if word in _MODE_WORDS]
        if len(collapse) + len(mode) != len(words) or len(collapse) > 1 or len(mode) > 1:
            return None
        keeps, wraps = (_COLLAPSE_WORDS[collapse[0]] if collapse else False), (_MODE_WORDS[mode[0]] if mode else True)
        return next(keyword for keyword, form in _WHITE_SPACE.items() if form == (keeps, wraps))
    if name == "text-wrap":  # its mode, from at most one mode word and one style word
        mode = [word for word in words if word in _MODE_WORDS]
        style = [word for word in words if word in _TEXT_WRAP_STYLES]
        if len(mode) + len(style) != len(words) or len(mode) > 1 or len(style) > 1:
            return None
        return mode[0] if mode else "wrap"
    return words[0] if len(words) == 1 and words[0] in _KEYWORDS.get(name, ()) else None


def _has_function(tokens: list[Node], colours: bool = False) -> bool:
    """Whether a value takes anything from a function, at any depth: a var() inside brackets defers it too. With
    ``colours``, a function that gives a colour alone, such as rgb(), does not count."""
    return any(
        (token.type == "function" and not (colours and token.lower_name in _COLOUR_FUNCTIONS))
        or (token.type in ("() block", "[] block", "{} block") and _has_function(token.content, colours))
        for token in tokens
    )


def _declarations(style: str | None) -> tuple[list[tuple[str, bool, str]], list[str]]:
    """Each declaration a style attribute makes that its property can take, in order (name, important,
    value), a box shorthand as the longhands it sets, and each declaration of a property read here that takes
    its value from a function."""
    found, unread = [], []
    for item in tinycss2.parse_blocks_contents(style or "", skip_comments=True, skip_whitespace=True):
        if item.type != "declaration":
            continue
        if item.lower_name in _READ and _has_function(item.value, colours=_BOX.get(item.lower_name, ("",))[0] == "border"):
            unread.append(f"{item.lower_name}:{tinycss2.serialize(item.value).strip()}")
        elif item.lower_name in _BOX:
            found += [(longhand, item.important, value) for longhand, value in _box_values(item.lower_name, item.value) or ()]
        elif (value := _value(item.lower_name, item.value)) is None:
            continue
        elif item.lower_name == "all":  # a CSS-wide keyword, set on every property read here
            longhands = {longhand for name in _BOX for longhand, _ in _box_values(name, item.value) or ()}
            found += [(name, item.important, value) for name in sorted((_READ - {"all"} - set(_BOX)) | longhands)]
        elif item.lower_name == "white-space" and len([t for t in item.value if t.type != "whitespace"]) > 1:
            found.append(("white-space-words", item.important, value))  # read by an engine that knows the longhands
        else:
            found.append((item.lower_name, item.important, value))
    return found, unread


def _won(declarations: list[tuple[str, bool, str]], *names: str) -> str | None:
    """The value that wins among the declarations of ``names``, which an engine reads as one property: an
    important declaration over a normal one, and among equals the last."""
    won = None
    for name, important, value in declarations:
        if name in names and (won is None or important or not won[0]):
            won = (important, value)
    return won[1] if won else None


def _local(tag: str) -> str:
    """An element's name without its namespace, as an SVG's or MathML's elements carry one."""
    return tag.rsplit("}", 1)[-1]


def _hidden_by_its_element(element: ElementTree.Element) -> bool:
    """Whether a browser's own style sheet hides the element where the page gives it no display: one it always
    hides, and a <dialog> that is not open."""
    name = _local(element.tag)
    return name in _UNSHOWN or (name == "dialog" and element.get("open") is None)


def _hidden_whatever_its_display(element: ElementTree.Element) -> bool:
    """Whether a browser's own style sheet hides the element over any display a page gives it, as it does
    <audio> without its controls and <input type="hidden"> (an important declaration)."""
    name = _local(element.tag)
    return (name == "audio" and element.get("controls") is None) or (
        name == "input" and (element.get("type") or "").lower() == "hidden"
    )


def _inline(display: str) -> bool:
    """Whether a display keeps an element in the line, as an inline box a run goes on across."""
    words = display.split()
    if words in (["contents"], ["ruby"], ["math"]):
        return True  # contents lays out the children in the line; ruby, and math on an HTML element, are inline
    return "inline" in words and set(words) <= {"inline", "flow", "ruby", "math", "list-item"}


def _attribute_width(value: str | None) -> str | None:
    """A ``width`` attribute as HTML maps it to CSS: a number is pixels, a number then ``%`` a percentage."""
    text, digits = (value or "").lstrip(_SPACE), "0123456789"
    end = 0
    while end < len(text) and text[end] in digits:
        end += 1
    if end and text[end : end + 1] == "." and text[end + 1 : end + 2] in tuple(digits):
        end += 1
        while end < len(text) and text[end] in digits:
            end += 1
    if not end:
        return None
    return _number(float(text[:end])) + ("%" if text[end : end + 1] == "%" else "px")


def _attribute_pixels(value: str | None) -> float | None:
    """A ``cellpadding``, ``cellspacing`` or ``border`` attribute as HTML maps it: a number of pixels."""
    width = _attribute_width(value)
    return float(width[:-2]) if width and width.endswith("px") else None


def _capped(element: ElementTree.Element) -> bool:
    """Whether the element's style caps its width at 600 px, as the shell caps its columns."""
    return _won(_declarations(element.get("style"))[0], "max-width") == "600px"


def _header_tables(root: ElementTree.Element) -> list[ElementTree.Element]:
    """The tables capped at 600 px that hold a wordmark: ``Earnings``, then an element that reads ``Nerd``."""
    parents = {child: parent for parent in root.iter() for child in parent}
    found: list[ElementTree.Element] = []
    for parent in root.iter():
        before = parent.text or ""
        for child in parent:
            text = "".join(child.itertext()) if isinstance(child.tag, str) else ""
            name = before.translate(_INVISIBLE).rstrip().lower()
            if text.translate(_INVISIBLE).strip().lower() == "nerd" and name.endswith("earnings"):
                table = parent
                while table is not None and not (table.tag == "table" and _capped(table)):
                    table = parents.get(table)
                if table is not None and table not in found:
                    found.append(table)
            before = text + (child.tail or "")
    return found


def _is_stylesheet(element: ElementTree.Element) -> bool:
    name = _local(element.tag)
    return name == "style" or (name == "link" and "stylesheet" in (element.get("rel") or "").lower().split())


def _take(won: str | None, parent: str, initial: str, own: str | None = None) -> str:
    """An inherited property's value: the winning declaration's; else the element's own default, such as
    ``<pre>``'s, or the parent's."""
    if won in ("inherit", "unset"):
        return parent
    if won is None or won in ("revert", "revert-layer"):
        return own if own is not None else parent
    return initial if won == "initial" else won


def _with_hints(declared: list[tuple[str, bool, str]], hints: list[tuple[str, bool, str]], *names: str) -> str | None:
    """The value that wins among the style's declarations of ``names`` and the hints below them: revert drops
    both, and revert-layer rolls back to the hints."""
    won = _won(declared, *names)
    if won == "revert-layer":
        return _won(hints, *names)
    if won is None:
        return _won(hints, *names)
    return won


@dataclass(frozen=True)
class _State:
    """What an element's text inherits, whether it shows and sits in the header, and the room its content has."""

    blink: str = "auto"  # text-size-adjust, as Blink reads it
    webkit: str = "auto"  # as Apple's WebKit reads it: the prefixed name alone
    overflow_wrap: str = "normal"  # as Blink reads it: word-wrap's anywhere taken
    overflow_wrap_strict: str = "normal"  # word-wrap's anywhere dropped, as WebKit may read it
    word_break: str = "normal"
    line_break: str = "auto"  # as Blink reads it: -webkit-line-break's anywhere dropped
    line_break_loose: str = "auto"  # -webkit-line-break's anywhere taken, as WebKit may read it
    white_space: str = "normal"  # as an engine that predates text-wrap-mode reads it
    wrap_mode: str = "wrap"  # as one that reads it does: the last of white-space, text-wrap and text-wrap-mode
    collapse: str = "collapse"  # as one that reads white-space-collapse does: the last of white-space and it
    in_header: bool = False
    shown: bool = True
    inline: bool = False  # whether the element is an inline box, which display:inherit gives its child
    floating: bool = False  # whether the element floats, which float:inherit gives its child
    room: float = NARROWEST_SCREEN  # px across the content's box on the narrowest phone
    cell_room: float | None = None  # what a table gives each of its cells, for its rows to hand on
    cell_padding: float | None = None  # the table's cellpadding, a hint on its cells' padding
    cell_border: float = 0.0  # the table's border attribute's 1 px border on its cells
    fixed_layout: bool = False  # whether the table lays its columns out fixed, keeping each width it is given

    @property
    def wraps(self) -> bool:
        return _WHITE_SPACE[self.white_space][1] and self.wrap_mode == "wrap"

    @property
    def keeps_breaks(self) -> bool:  # in both kinds of engine
        return _WHITE_SPACE[self.white_space][0] and self.collapse != "collapse"

    @property
    def collapses(self) -> bool:  # a run of spaces shows as one, in both kinds of engine
        return self.white_space in ("normal", "nowrap", "pre-line") and self.collapse in ("collapse", "preserve-breaks")

    @property
    def lends(self) -> bool:  # the rule that lets a run break anywhere, as some engine may take it
        return self.overflow_wrap == "anywhere" or self.word_break in ("break-word", "break-all") or self.line_break_loose == "anywhere"

    @property
    def breaks_anywhere(self) -> bool:  # in every engine
        return self.wraps and (
            self.overflow_wrap_strict == "anywhere" or self.word_break in ("break-word", "break-all") or self.line_break == "anywhere"
        )

    @property
    def breaks_in_some_engine(self) -> bool:
        return self.wraps and self.lends


@dataclass(frozen=True)
class _Piece:
    text: str
    state: _State


class _Page:
    """The text a page shows, piece by piece and each with what it inherits, read as a browser builds the
    page; what its boxes take of the room their parents give them; and the tables the break rule reaches. A
    ``None`` among the pieces is an edge a run cannot cross."""

    def __init__(self, page: str) -> None:
        root = tinyhtml5.parse(page, namespace_html_elements=False)
        self.pieces: list[_Piece | None] = []
        self.out_of_line: list[list[_Piece | None]] = []
        self.box_problems: list[str] = []
        self.reached: list[str] = []
        self.unread: list[str] = []
        self.headers = _header_tables(root)
        # A style block or a stylesheet applies wherever it sits, in the head or in what the page hides.
        self.stylesheets = sum(1 for element in root.iter() if isinstance(element.tag, str) and _is_stylesheet(element))
        self._walk(root, _State())
        for pieces in self.out_of_line:  # a float's or a positioned box's text: runs of its own
            self.pieces += [None, *pieces, None]

    def _state(self, element: ElementTree.Element, parent: _State) -> tuple[_State, bool, list[tuple[str, bool, str]], str | None]:
        """What the element's text inherits, whether a run goes on across its tags, its declarations, and the
        display its style gives it."""
        tag = _local(element.tag)
        declared, unread = _declarations(element.get("style"))
        self.unread += unread
        display = _won(declared, "display")
        if display in ("initial", "unset"):
            display = "inline"  # display's initial value, which unset takes, since display is not inherited
        elif display == "inherit":
            display = "inline" if parent.inline else "block"  # the parent's: as far as a run goes, inline or not
        elif display in _GLOBAL:
            display = None  # revert: the element's own, as a browser's style sheet gives it
        shown = parent.shown and display != "none" and not (display is None and _hidden_by_its_element(element))
        if element.get("hidden") is not None and display is None:
            shown = False
        shown = shown and not _hidden_whatever_its_display(element)
        # A cell's nowrap attribute: white-space:nowrap below every declaration of its style.
        hints = [("white-space", False, "nowrap")] if tag in _CELLS and element.get("nowrap") is not None else []
        own_space = _OWN_WHITE_SPACE.get(tag)
        modes = [
            ("wrap-mode", important, _MODE_OF.get(value, value) if name in ("white-space", "white-space-words") else value)
            for name, important, value in declared
            if name in ("white-space", "white-space-words", "text-wrap", "text-wrap-mode")
        ]
        collapses = [
            ("collapse", important, _COLLAPSE_OF.get(value, value) if name in ("white-space", "white-space-words") else value)
            for name, important, value in declared
            if name in ("white-space", "white-space-words", "white-space-collapse")
        ]
        hint_modes = [("wrap-mode", False, "nowrap")] if hints else []
        hint_collapses = [("collapse", False, "collapse")] if hints else []
        no_alias_anywhere = [d for d in declared if d[0] not in ("word-wrap", "-webkit-line-break") or d[2] != "anywhere"]
        state = replace(
            parent,
            blink=_take(_won(declared, "text-size-adjust", "-webkit-text-size-adjust"), parent.blink, "auto"),
            webkit=_take(_won(declared, "-webkit-text-size-adjust"), parent.webkit, "auto"),
            overflow_wrap=_take(_won(declared, "overflow-wrap", "word-wrap"), parent.overflow_wrap, "normal"),
            overflow_wrap_strict=_take(_won(no_alias_anywhere, "overflow-wrap", "word-wrap"), parent.overflow_wrap_strict, "normal"),
            word_break=_take(_won(declared, "word-break"), parent.word_break, "normal"),
            line_break=_take(_won(no_alias_anywhere, "line-break", "-webkit-line-break"), parent.line_break, "auto"),
            line_break_loose=_take(_won(declared, "line-break", "-webkit-line-break"), parent.line_break_loose, "auto"),
            white_space=_take(_with_hints(declared, hints, "white-space"), parent.white_space, "normal", own_space),
            wrap_mode=_take(_with_hints(modes, hint_modes, "wrap-mode"), parent.wrap_mode, "wrap", _MODE_OF[own_space] if own_space else None),
            collapse=_take(_with_hints(collapses, hint_collapses, "collapse"), parent.collapse, "collapse", _COLLAPSE_OF[own_space] if own_space else None),
            in_header=parent.in_header or any(element is header for header in self.headers),
            shown=shown,
        )
        crossed = _inline(display) if display is not None else tag not in _RUN_EDGES
        return replace(state, inline=crossed), crossed, declared, display

    def _text(self, text: str | None, state: _State) -> None:
        if text and state.shown:
            self.pieces.append(_Piece(text, state))

    def _walk(self, element: ElementTree.Element, parent: _State) -> None:
        if not isinstance(element.tag, str):  # a comment, Outlook's conditionals among them: no text
            return
        state, crossed, declared, display = self._state(element, parent)
        if not state.shown:  # out of the layout: its text is not read, its widths hold nothing, and it ends no run
            return
        tag = _local(element.tag)
        float_set = _won(declared, "float")
        if float_set in (None, "revert-layer"):  # an image's or a table's align, a hint below every declaration
            floats = tag in _ALIGN_FLOATS and (element.get("align") or "").strip().lower() in ("left", "right")
        elif float_set == "inherit":
            floats = parent.floating
        else:
            floats = float_set not in ("none", "initial", "unset", "revert")
        out_of_line = tag != "br" and (floats or _won(declared, "position") in ("absolute", "fixed"))
        state = self._box(element, tag, replace(state, floating=floats), parent, declared, display, out_of_line)
        if tag in ("table", *_TABLE_PARTS) and state.lends and not (tag != "table" and parent.lends):
            self.reached.append(f"<{tag}> that reads {' '.join(''.join(element.itertext()).split())[:40]!r}")
        if tag == "wbr":
            self._text(_ZERO_WIDTH_SPACE, state)
            return
        if out_of_line:  # out of the line: its text forms runs of its own, and the line runs on across it
            outer, self.pieces = self.pieces, []
        if not crossed or out_of_line:
            self.pieces.append(None)
        self._text(element.text, state)
        for child in element:
            self._walk(child, state)
            self._text(child.tail, state)
        if not crossed or out_of_line:
            self.pieces.append(None)
        if out_of_line:
            self.out_of_line.append(self.pieces)
            self.pieces = outer

    def _side(self, declared, name: str, room: float, ua: float, hint: float | None, named: str) -> float:
        """A margin's, a padding's or a border width's px on one side, as its style sets it, else as its hint
        or a browser's own style sheet does."""
        value = _won(declared, name)
        if value == "revert-layer" or value is None:
            return hint if hint is not None else ua
        if value == "revert":
            return ua
        if value in ("initial", "unset", "auto"):
            return 0.0
        if value in ("inherit", "refused"):
            self.box_problems.append(f"{named}'s {name} is set by the font, the screen or its parent, which this check does not resolve: write it in px or %")
            return 0.0
        pixels = float(value[:-1]) / 100 * room if value.endswith("%") else float(value[:-2])
        if pixels < 0:
            self.box_problems.append(f"{named}'s {name} is negative, which this check does not resolve: lay the box out with positive margins")
            return 0.0
        return pixels

    def _border(self, declared, side: str, ua: float, hint: float | None, named: str) -> float:
        """A border's px on one side: none unless its style shows one; then its width, as its style sets it,
        else as the table's border attribute or a browser's own style sheet does, else medium's 3 px."""
        style = _won(declared, f"border-{side}-style")
        if style in (None, "revert-layer"):
            shows = hint is not None or ua > 0
        elif style == "revert":
            shows = ua > 0
        else:
            shows = style not in ("none", "hidden") and style not in _GLOBAL
        return self._side(declared, f"border-{side}-width", 0.0, ua or 3.0, hint, named) if shows else 0.0

    def _box(self, element, tag: str, state: _State, parent: _State, declared, display: str | None, out_of_line: bool) -> _State:
        """The element's box: what it takes of the room its parent gives it, each overrun noted, and the
        state with the room its content has."""
        named = f"<{tag}>"
        if tag in ("col", "colgroup"):  # a column's width, held to the room its table gives a cell
            self._column(element, declared, parent, named)
            return state
        if display is not None and display not in ("none",):
            kind = (
                "inline" if _inline(display)
                else "replaced" if tag in _REPLACED
                else "atomic" if display.startswith("inline") or display == "-webkit-inline-box"
                else "table" if display == "table"
                else "part" if display in ("table-row-group", "table-header-group", "table-footer-group", "table-row")
                else "cell" if display == "table-cell" and tag in _CELLS
                else "block"
            )
        else:
            kind = (
                "replaced" if tag in _REPLACED
                else "table" if tag == "table"
                else "part" if tag in _TABLE_PARTS
                else "cell" if tag in _CELLS
                else "atomic" if tag in _WIDGETS
                else "block" if tag in _RUN_EDGES and tag not in ("br", "col", "colgroup", "math", "caption")
                else "inline"
            )
        if out_of_line and kind in ("inline", "block"):
            kind = "atomic"  # a float or a positioned box shrinks to its content
        if kind == "inline":
            return state
        if kind == "part":
            return replace(state, room=parent.cell_room if parent.cell_room is not None else parent.room)
        room = parent.cell_room if kind == "cell" and parent.cell_room is not None else parent.room
        ua_margin = _UA_MARGIN.get(tag, (0.0, 0.0))
        ua_padding = (0.0, 0.0) if kind == "cell" else _UA_PADDING.get(tag, (0.0, 0.0))
        # A cell's padding is its table's cellpadding, 1 px without one: a hint, which revert drops.
        padding_hint = (parent.cell_padding if parent.cell_padding is not None else 1.0) if kind == "cell" else None
        border_attr = _attribute_pixels(element.get("border")) if tag in ("table", "img", "object") else None
        border_hint = border_attr if border_attr else (parent.cell_border if kind == "cell" and parent.cell_border else None)
        ua_border = _UA_BORDER.get(tag, 0.0)
        margin_hint = _attribute_pixels(element.get("hspace")) if tag in _HSPACED else None
        margins = 0.0 if kind == "cell" else sum(  # a cell takes no margin
            self._side(declared, f"margin-{side}", room, ua, margin_hint, named) for side, ua in zip(("left", "right"), ua_margin)
        )
        padding = sum(self._side(declared, f"padding-{side}", room, ua, padding_hint, named) for side, ua in zip(("left", "right"), ua_padding))
        borders = sum(self._border(declared, side, ua_border, border_hint, named) for side in ("left", "right"))
        extras = padding + borders
        hinted = _attribute_width(element.get("width")) if tag in _WIDTH_HINTED else None
        width = _won(declared, "width")
        if width in (None, "revert-layer"):
            width = hinted
        elif width in ("initial", "unset", "revert"):
            width = None
        sizing = _won(declared, "box-sizing")
        ua_border_box = tag in _UA_BORDER_BOX or (tag == "input" and (element.get("type") or "").lower() in _BORDER_BOX_INPUTS)
        border_box = sizing == "border-box" or (sizing in (None, "revert", "revert-layer") and ua_border_box)
        cap, cap_held = self._cap(declared, room, kind, named)
        least = self._least(declared, room, named)
        content: float
        if width in _SIZING or width == "auto":
            if width == "max-content":
                self.box_problems.append(f"{named}'s width max-content is set by its content, which this check does not measure: give it a width in px or %")
            width = None
        if width == "inherit" or (width and width.lstrip("0123456789.") in _RELATIVE):
            self.box_problems.append(f"{named}'s width {width} is set by the font, the screen or its parent, which this check does not resolve: write it in px or %")
            width = None
        if width is None and kind == "replaced" and not cap_held:
            self.box_problems.append(
                f"{named} has no width, so it shows at its natural size, which this check does not know: give it a width "
                f"that fits the {room:g} px its parent gives it on a {NARROWEST_SCREEN} px phone, or max-width:100%"
            )
        if width is None and kind == "replaced" and cap is not None and margins + cap + (0 if border_box else extras) > room + _SLACK:
            self.box_problems.append(
                f"{named} may take {margins + cap + (0 if border_box else extras):g} px across at its max-width, with its "
                f"borders, padding and margins, where its parent gives it {room:g} px on a {NARROWEST_SCREEN} px phone: drop "
                "its side margins, or set box-sizing:border-box so its padding and borders sit inside the max-width"
            )
        if width is None:
            least_box = (least if border_box else least + extras) if least else 0.0
            if least_box and margins + least_box > room + _SLACK:
                self.box_problems.append(
                    f"{named} takes {margins + least_box:g} px across at its min-width, with its borders, padding and margins, where "
                    f"its parent gives it {room:g} px on a {NARROWEST_SCREEN} px phone: lower the min-width, or set it in %"
                )
            elif room - margins - extras < -_SLACK:
                self.box_problems.append(
                    f"{named}'s margins, borders and padding take {margins + extras:g} px, and leave its content no room in the "
                    f"{room:g} px its parent gives it on a {NARROWEST_SCREEN} px phone"
                )
            box = max(room - margins, least_box)
            if cap is not None:
                box = min(box, cap + (0 if border_box else extras))
            content = max(min(box, room - margins) - extras, 0.0)
        else:
            set_to = float(width[:-1]) / 100 * room if width.endswith("%") else _px(width)
            set_to = max(min(set_to, cap) if cap is not None else set_to, least)
            # A cell set in percent takes its column's share of the table, which holds its padding and borders.
            share = kind == "cell" and width.endswith("%")
            box = max(set_to, extras) if share else set_to if border_box else set_to + extras
            if kind == "cell" and box > room + _SLACK:
                why = (
                    "a fixed table layout keeps a cell's width" if parent.fixed_layout
                    else "Chromium squeezes the cell, but CSS 2.1's automatic table layout reads a cell's width as its least"
                )
                self.box_problems.append(
                    f"{named} takes {box:g} px across, with its borders and padding, where its table gives it {room:g} px on a "
                    f"{NARROWEST_SCREEN} px phone: {why}, so give it a percentage, whose share of the table holds its padding"
                )
            elif kind != "cell" and margins + box > room + _SLACK:
                if kind == "replaced":
                    advice = "hold it to the room with max-width:100%" + (", and drop its side margins" if margins else "")
                elif margins + set_to > room + _SLACK:
                    advice = (
                        f"let it take the room up to a cap (width:100%;max-width:{set_to:g}px), with classic Outlook's "
                        "fixed width in a conditional comment"
                    )
                else:
                    advice = "its borders, padding and margins add to its width: leave the width unset" + (
                        "" if border_box or not extras else ", or set box-sizing:border-box"
                    )
                self.box_problems.append(
                    f"{named} takes {margins + box:g} px across, with its borders, padding and margins, where its parent gives it "
                    f"{room:g} px on a {NARROWEST_SCREEN} px phone: {advice}"
                )
            content = max(min(box, room - margins) - extras, 0.0)
        if kind != "table":
            return replace(state, room=content, cell_room=None, fixed_layout=False)
        hinted_spacing = _attribute_pixels(element.get("cellspacing"))
        declared_spacing = _won(declared, "border-spacing")
        if _won(declared, "border-collapse") == "collapse":
            spacing = 0.0  # collapsed borders leave no spacing between cells
        elif declared_spacing in (None, "revert-layer"):
            spacing = hinted_spacing if hinted_spacing is not None else 2.0
        elif declared_spacing == "revert":
            spacing = 2.0  # a browser's own style sheet's
        elif declared_spacing == "initial":
            spacing = 0.0
        elif declared_spacing in _GLOBAL:  # inherit, unset: inherited from the parent
            self.box_problems.append(f"{named}'s border-spacing {declared_spacing} is set by its parent, which this check does not resolve: write it in px")
            spacing = 2.0
        else:
            spacing = float(declared_spacing[:-2])
        return replace(
            state,
            room=content,
            cell_room=max(content - 2 * spacing, 0.0),
            cell_padding=_attribute_pixels(element.get("cellpadding")),
            cell_border=1.0 if border_attr and tag == "table" else 0.0,
            # A fixed layout needs a width; without one the table lays its columns out automatically.
            fixed_layout=_won(declared, "table-layout") == "fixed" and width is not None,
        )

    def _column(self, element, declared, parent: _State, named: str) -> None:
        """A column's width against the room its table gives a cell, as a cell's is held."""
        width = _won(declared, "width")
        if width in (None, "revert-layer"):
            width = _attribute_width(element.get("width"))
        room = parent.cell_room if parent.cell_room is not None else parent.room
        if width is None or width in _GLOBAL | _SIZING | {"auto"}:
            return
        if width.lstrip("0123456789.") in _RELATIVE:
            self.box_problems.append(f"{named}'s width {width} is set by the font or the screen, which this check does not resolve: write it in px or %")
            return
        set_to = float(width[:-1]) / 100 * room if width.endswith("%") else _px(width)
        if set_to > room + _SLACK:
            why = (
                "a fixed table layout keeps a column's width" if parent.fixed_layout
                else "Chromium squeezes the column, but CSS 2.1's automatic table layout reads a column's width as its least"
            )
            self.box_problems.append(
                f"{named} is set {set_to:g} px wide where its table gives a cell {room:g} px on a {NARROWEST_SCREEN} px phone: "
                f"{why}, so give it a percentage"
            )

    def _cap(self, declared, room: float, kind: str, named: str) -> tuple[float | None, bool]:
        """A max-width as px, and whether it holds a replaced element to the room."""
        value = _won(declared, "max-width")
        if value is None or value in _GLOBAL | _SIZING | {"none"}:
            return None, False
        if value.endswith("%"):
            if kind != "replaced":  # in a table's cell a percentage holds no box's own content
                return None, False
            return float(value[:-1]) / 100 * room, float(value[:-1]) <= 100
        if value.lstrip("0123456789.") in _RELATIVE:
            self.box_problems.append(f"{named}'s max-width {value} is set by the font, the screen or its parent: write it in px or %")
            return None, False
        pixels = _px(value)
        return pixels, pixels <= room

    def _least(self, declared, room: float, named: str) -> float:
        """A min-width as px."""
        value = _won(declared, "min-width")
        if value is None or value in _GLOBAL | {"auto", "min-content", "fit-content", "stretch", "-webkit-fill-available"}:
            return 0.0
        if value == "max-content":
            self.box_problems.append(f"{named}'s min-width max-content is set by its content, which this check does not measure: write it in px or %")
            return 0.0
        if value.endswith("%"):
            return float(value[:-1]) / 100 * room
        if value.lstrip("0123456789.") in _RELATIVE:
            self.box_problems.append(f"{named}'s min-width {value} is set by the font, the screen or its parent, which this check does not resolve: write it in px or %")
            return 0.0
        return _px(value)

    def refusals(self) -> list[str]:
        """What the page asks of the reader that it does not resolve."""
        problems = []
        if self.stylesheets:
            problems.append(
                "the page carries a <style> block or a linked stylesheet, whose selectors this check does not read: set the style inline"
            )
        problems += [f"{declaration!r} takes its value from a function this check does not resolve: write the value out" for declaration in self.unread]
        return problems

    def lines(self) -> list[tuple[str, _State]]:
        """Each piece of text the page shows, spaced as it renders, with what it inherits."""
        return [
            (" ".join(piece.text.split()) or piece.text.strip(_SPACE), piece.state)  # a no-break space shows as itself
            for piece in self.pieces
            if piece and piece.text.strip(_SPACE + _ZERO_WIDTH_SPACE)
        ]

    def runs(self) -> list[list[tuple[str, _State]]]:
        """Each run of characters the page shows with nowhere between them to wrap, each character with
        what it inherits. Spaces a line collapses count once and fall away at a run's ends; spaces it keeps
        count each."""
        runs: list[list[tuple[str, _State]]] = [[]]
        for piece in self.pieces:
            if piece is None:
                runs.append([])
                continue
            state = piece.state
            for character in piece.text:
                if character in _WRAP_SPACES + _ZERO_WIDTH_SPACE and state.wraps:
                    runs.append([])
                elif character in "\n\r" and state.keeps_breaks:
                    runs.append([])
                elif character in _WRAP_SPACES:
                    if not (state.collapses and runs[-1] and runs[-1][-1][0] == " "):
                        runs[-1].append((" ", state))
                elif character != _ZERO_WIDTH_SPACE:
                    runs[-1].append((character, state))
        trimmed = []
        for run in runs:
            start, end = 0, len(run)
            while start < end and run[start][0] == " " and run[start][1].collapses:
                start += 1
            while end > start and run[end - 1][0] == " " and run[end - 1][1].collapses:
                end -= 1
            if start < end:
                trimmed.append(run[start:end])
        return trimmed


def text_size_problems(page: str) -> list[str]:
    """Where a page breaks the shell's text-size rule: the header keeps its set size where a phone view
    enlarges text, in both engines, and every other line is left to the view."""
    parsed = _Page(page)
    problems = parsed.refusals()
    if len(parsed.headers) != 1:
        problems.append(
            f"the page carries {len(parsed.headers)} tables that read as the header, a table capped at 600 px that holds "
            "the wordmark: the check finds the header by it, so a page carries one"
        )
    lines = parsed.lines()
    if not any(state.in_header for _, state in lines):
        problems.append("the page shows no line of the header")
    for text, state in lines:
        engines = f"Blink reads {state.blink}, iOS's WebKit {state.webkit}"
        if state.in_header and not state.blink == state.webkit == "100%":
            why = (
                "none would also stop a reader's own zoom in older desktop WebKit"
                if "none" in (state.blink, state.webkit)
                else "enlarged, the tagline outgrows the wordmark"
            )
            problems.append(f"the header's {text[:40]!r} is not held at 100% ({engines}): {why}")
        elif not state.in_header and not state.blink == state.webkit == "auto":
            problems.append(
                f"{text[:40]!r} is not left to the view ({engines}): text outside the header keeps auto, so a phone view "
                "can enlarge a long body"
            )
    return problems


def long_runs(page: str) -> list[str]:
    """The runs of ``LONG_RUN`` characters or more that a page shows with nowhere to wrap."""
    return ["".join(character for character, _ in run) for run in _Page(page).runs() if len(run) >= LONG_RUN]


def lent_runs(page: str) -> list[str]:
    """The runs of ``LONG_RUN`` characters or more that some engine may break anywhere: for a shell's check that
    it lends the rule to no line, since on the panel it would reach a body's own table and split its amounts."""
    return [
        "".join(character for character, _ in run)
        for run in _Page(page).runs()
        if len(run) >= LONG_RUN and any(state.breaks_in_some_engine for _, state in run)
    ]


def long_run_problems(page: str) -> list[str]:
    """Where a page shows ``LONG_RUN`` characters or more with nowhere to break: on the narrowest phone they
    hold the page wider than the screen."""
    parsed = _Page(page)
    problems = parsed.refusals()
    for run in parsed.runs():
        stretch: list[tuple[str, _State]] = []
        for character, state in [*run, ("", None)]:  # a stretch of characters no break may enter
            if state is not None and not state.breaks_anywhere:
                stretch.append((character, state))
                continue
            if len(stretch) >= LONG_RUN:
                text = "".join(character for character, _ in stretch)[:40]
                if any(not held.wraps for _, held in stretch):
                    problems.append(
                        f"{text!r} cannot wrap: white-space or text-wrap keeps it on one line, so on a "
                        f"{NARROWEST_SCREEN} px phone it holds the page wider than the screen"
                    )
                else:
                    problems.append(
                        f"{text!r} has nowhere to break: give its line overflow-wrap:anywhere;word-break:break-word, or "
                        f"on a {NARROWEST_SCREEN} px phone it holds the page wider than the screen"
                    )
            stretch = []
    return problems


def reach_problems(page: str) -> list[str]:
    """Where the rule that lets a run break anywhere reaches a table, in some engine: there it splits a column
    of amounts, so it sits on the lines that print a run, or on a cell of its own."""
    parsed = _Page(page)
    return parsed.refusals() + [
        f"the rule that lets a run break anywhere reaches the {where}, in some engine: put it on the lines that print "
        "a run, since in a table it splits a column of amounts"
        for where in parsed.reached
    ]


def fixed_width_problems(page: str) -> list[str]:
    """Where a box a client other than classic Outlook shows is set wider than the room its parent gives it on
    the narrowest phone, or leaves its content no room there."""
    parsed = _Page(page)
    return parsed.refusals() + parsed.box_problems


def viewports(page: str) -> list[str]:
    """The content of each viewport ``<meta>`` a page carries, wherever it sits (a browser reads one in the body
    too), its comma-separated settings spaced one way."""
    root = tinyhtml5.parse(page, namespace_html_elements=False)
    return [
        ", ".join(" ".join(part.split()) for part in (element.get("content") or "").split(",") if part.strip())
        for element in root.iter()
        if isinstance(element.tag, str) and _local(element.tag) == "meta" and (element.get("name") or "").strip().lower() == "viewport"
    ]


def _outlook_takes(condition: str) -> bool | None:
    """Whether classic Outlook, 2016 and later (``mso 16``), takes a conditional comment's condition: None when
    the reader cannot parse it."""
    tokens, at = [], 0
    while at < len(condition):
        match = _CONDITION.match(condition, at)
        if not match or not match.group(1):
            if condition[at:].strip():
                return None
            break
        tokens.append(match.group(1).lower())
        at = match.end()
    position = 0

    def peek() -> str | None:
        return tokens[position] if position < len(tokens) else None

    def take() -> str:
        nonlocal position
        position += 1
        return tokens[position - 1]

    def either() -> bool:
        value = both()
        while peek() == "|":
            take()
            value = both() or value
        return value

    def both() -> bool:
        value = one()
        while peek() == "&":
            take()
            value = one() and value
        return value

    def one() -> bool:
        token = take() if peek() is not None else None
        if token == "!":
            return not one()
        if token == "(":
            value = either()
            if take() != ")":
                raise ValueError(condition)
            return value
        compare = _COMPARISONS.get(token or "")
        feature = take() if compare is not None and peek() is not None else token
        if feature is None or not feature.isalpha():
            raise ValueError(condition)
        version = float(take()) if (peek() or "")[:1].isdigit() else None
        if compare is not None and version is None:
            raise ValueError(condition)
        have = _OUTLOOK.get(feature)
        if have is None:
            return False
        if version is None:
            return True
        return compare(have, version) if compare is not None else int(have) == int(version)

    try:
        value = either()
    except (IndexError, ValueError):
        return None
    return value if position == len(tokens) else None


def outlook_view(page: str) -> str:
    """The page as classic Outlook reads its conditional comments: what one whose condition Outlook takes holds
    shows, and what another holds does not, in a comment or a revealed block."""

    def read(match: re.Match[str]) -> str:
        return match.group(3) if _outlook_takes(match.group(1)) else ""

    def revealed(match: re.Match[str]) -> str:
        return match.group(2) if _outlook_takes(match.group(1)) else ""

    return _REVEALED.sub(revealed, _CONDITIONAL.sub(read, page))


def outlook_width_problems(page: str) -> list[str]:
    """Where classic Outlook, which reads no ``max-width``, would not hold a column capped at 600 px at 600 px:
    in its view of the page, the nearest table around each such column that is set to a fixed width is 600 px
    wide."""
    root = tinyhtml5.parse(outlook_view(page), namespace_html_elements=False)
    parents = {child: parent for parent in root.iter() for child in parent}
    problems = []
    for table in (element for element in root.iter() if element.tag == "table" and _capped(element)):
        around, width = parents.get(table), None
        while around is not None:
            if around.tag == "table" and (width := _attribute_width(around.get("width"))) and width.endswith("px"):
                break
            around = parents.get(around)
        if around is None or width != "600px":
            text = " ".join("".join(table.itertext()).split())[:40]
            problems.append(
                f"in classic Outlook, which reads no max-width, the column capped at 600 px that reads {text!r} sits in no "
                "table 600 px wide: give it one in a conditional comment"
            )
    return problems
