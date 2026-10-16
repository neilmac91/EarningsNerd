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

A run ends where a line may wrap: at a space, a tab, a line break or one of the Unicode spaces a line may break
after, where the line wraps; at ``<wbr>`` or a zero-width space there; at ``<br>`` or a line break the line keeps;
and at the edge of a block, a table's part or an element placed whole whatever its display, such as an image, a
form control, or an ``<object>`` that holds no fallback content (any child but a ``<param>`` or whitespace, a
comment among them), since a line may wrap before and after each (CSS Text 3). It goes on across the tags of every
other element, an element the reader does not know and one the page hides alike, so a link split by markup is read
whole; across an ``<object>``'s fallback, which a browser lays out in the line unless the content its ``data`` or
``type`` asks for loads, which the reader does not know; across an ``<embed>`` with neither a ``src`` nor a
``type``, which lays out nothing; and across a float (a ``float`` in its style, its parent's under ``inherit``, or
an ``align`` of left or right, as written, on an image, a table, an object, an embed, an iframe or an input drawn
as an image, which ``float:revert-layer`` keeps) or a box positioned absolute or fixed, which a browser takes out
of the line: the text on either side of one joins, and its own text forms runs of its own. A ``<br>`` breaks the
line whatever its float, position or display, unless the page lays it out nowhere: ``display:none``, the
``hidden`` attribute, or ``display:contents``, which computes to none on a ``<br>`` and a ``<wbr>``, a replaced
element, a form control that draws itself, an ``<svg>`` and a ``<math>`` (CSS Display 3, its unusual elements;
measured in Chromium 141). Within a run, a character can break where ``overflow-wrap:anywhere``,
``word-break:break-word`` or ``break-all``, or ``line-break:anywhere`` reaches it: each lets a word break and
shrinks the narrowest width a table can give its cell, which ``overflow-wrap:break-word`` alone does not. Two
aliases are read once per engine, since the engines differ on them: ``word-wrap``, read with ``overflow-wrap``,
whose ``anywhere`` Blink takes and WebKit may not, and ``-webkit-line-break``, read with ``line-break``, whose
``anywhere`` Blink drops (in Chromium 141 ``CSS.supports`` refuses it, and takes the alias's other values) and
WebKit may take. So a run breaks in every engine only where another of those forms reaches it, and a page lends
the rule wherever either engine may take it (``lent_runs``, ``reach_problems``). That Blink breaks under each form
is measured; that WebKit does is inferred from the specifications it implements. ``all`` sets every property read
here to its keyword, in its place among the declarations.

A line wraps where both kinds of engine wrap it: one that predates ``text-wrap-mode`` reads ``white-space`` alone,
in its single keywords (it drops one written in its longhands' words, such as ``collapse wrap`` or a lone
``wrap``), and one that reads it takes the last of ``white-space``, ``text-wrap`` and ``text-wrap-mode``, the
first two being shorthands that set it. So ``white-space:nowrap`` or ``pre``, ``text-wrap-mode:nowrap`` and a
``text-wrap`` with ``nowrap`` keep a run on one line, spaces and all, as do ``<pre>``, ``<nobr>`` and a cell's
``nowrap`` attribute, and a ``text-wrap-mode:wrap`` does not undo a ``white-space:nowrap``. A line keeps its line
breaks where both kinds keep them, and its spaces where either does: one that reads ``white-space-collapse`` takes
the last of it and ``white-space``, the older one ``white-space`` alone, and spaces a line keeps count in its
runs. A value Chromium refuses, such as ``white-space:preserve-spaces`` or ``text-wrap:avoid-orphans``, is
dropped, as there.

Each box is held to the room its parent gives it on the narrowest phone: 320 px for the page, less each box's
horizontal margins, borders and padding, as its ``style`` sets them, side by side, shorthand and longhand, in px
or another absolute unit, or a percentage of the room; else as the attributes HTML maps set them, read as HTML
parses them: a cell's padding from its table's ``cellpadding`` (1 px without one) and its border from the table's
``border`` (1 px), a table's spacing from its ``cellspacing`` and its border from its ``border``, an image's or an
object's border from its ``border``, each a whole number, so ``5%`` is 5 px, and an image's, an object's or an
embed's margins from its ``hspace``, a length in px or a percentage of the room (an iframe's sets none); else as a
browser's own style sheet does: a body's 8 px margins, a list's 40 px indent, a blockquote's and a figure's 40 px
margins, a checkbox's and a radio button's side margins, an iframe's 2 px border, a table's 2 px spacing, a text
field's 2 px border and 2 px padding (a date or a time field's 1 px), a text area's 1 px border and 2 px padding,
a range slider's 2 px margins and a legend's 2 px padding, an input of a type HTML does not know being a text
field (measured in Chromium 141). ``revert`` drops the attributes' values and ``revert-layer`` keeps them
(measured in Chromium 141). The shell's own boxes leave a body ``WIDEST_FIXED``. A box's width is its ``width`` in
its ``style``, else its ``width`` attribute where HTML maps one (a table's, a cell's, a column's, a rule's, an
image's, an ``<svg>``'s, an input drawn as an image's or another replaced element's): a number is pixels, a number
then ``%`` a percentage of the room, save that a table's or a cell's zero sets none (HTML's nonzero dimension),
nor does a column's relative length such as ``3*`` (measured in Chromium 141). A table, a button, a select, a
meter, a progress and an input drawn as a button, a box, a colour well or a search field count their border and
padding in their width, as a browser's own style sheet sets them; another box, a ``<div>`` set ``display:table``
among them, adds them. A box set wider than its room fails, whether a fixed width, a percentage over 100% or a
``min-width`` sets it, and so do margins, borders and padding that leave a box's content no room. A ``max-width``
in pixels caps a width; one in percent holds an image or another replaced element alone, since in a table's cell
it does not hold the box's own content (CSS Sizing 3, its cyclic percentages). An image or another replaced
element with no width shows at its natural size, which the reader does not know, so it fails unless a
``max-width`` holds it, and then it may show as wide as that, with its margins, borders and padding added. An
``<object>`` whose ``data`` or ``type`` asks for content is held as a replaced element even where it holds
fallback, since the content may load. A width set by the font or the screen, such as ``em`` or ``vw``, by the
parent (``inherit``), or by the content (``max-content``) is refused rather than guessed, and so is a margin, a
padding or a table's spacing set that way. An inline element's box takes no width, save an image, another replaced
element or a form control, which a browser places whole, as one box, whatever display a page gives it.

A table's cells and columns are read as its layout reads them, without the rows, sections, cells and columns the
page hides: its first header group (a ``<thead>``, or a section its display makes one) first and its first footer
group last, wherever the source puts them, and each row's cells after the columns a cell above still spans, within
its section. A cell's room is its table's, less the spacing beside its columns, and a percentage is of that room.
A lone column takes the whole table in either layout, whatever share its cell asks. In an automatic layout, where
a cell set in px narrows, a cell set in percent takes its share, its padding and borders inside it, and its
content is held to the share; each column is held to its widest cell's borders, padding and min-width, a cell
across columns spreading what exceeds the columns it spans over them alike, and the columns, with the spacing
between them, to the table's room; and a cell or a column (``<col>``) set wider than its table fails: Chromium
squeezes it, while CSS 2.1's automatic table layout reads its width as its minimum. A column's min-width past its
table fails in either layout. Under ``table-layout:fixed``, which needs a width, the columns keep the widths their
``<col>`` elements set, their cells' padding inside, else the widths the first row (the first a browser lays out)
sets, in px or in percent, each cell's padding added unless its box-sizing holds it, and a cell across columns
giving them its width less the spacing between them; the other rows' widths go unread. Columns set in percent take
what those set in px leave, down to none, so the columns set in px, with the spacing between them, are held to the
table; the room left goes to the columns that set no width, alike, else to those set in px, by their widths, else
to those set in percent; and each cell is given its columns' width. A share over 100% fails in either layout,
though Chromium holds it to the table (measured in Chromium 141; that WebKit's table layout does the same is
inferred).

Outlook's view is the page as classic Outlook reads its conditional comments, as Outlook 2016 and later
(``mso 16``) take their conditions: ``mso`` and ``vml`` true, a version compared, ``IE`` false, and ``!``,
``&``, ``|`` and brackets as written. What a condition Outlook takes holds shows there, and what one it does not
take holds does not, in a comment or in a revealed block (``<![if !mso]>``); a condition the reader cannot
parse hides what it holds. A column capped at 600 px is held when the nearest table around it set to a fixed
width is 600 px wide.

The reader errs toward asking for the rule: it counts no break a browser may take at a hyphen or after a question
mark, or at a ``<wbr>`` under ``nowrap``, where Chromium breaks, and no width that holds a run in, such as a fixed
table layout or a clipped box, so it may ask for the rule where a browser would fit the run; it holds a percentage
cell's content to its share, and a cell's set in px in an automatic layout to its width, where Chromium may widen
the column at the others' cost; it counts the spacing beside columns only a ``<col>`` defines; it reads a fixed
layout's first-row cell's min-width and max-width as any box's, though the layout gives the cell its column; and
it reads an object that asks for content both ways, its fallback in the line and its box held. It does not measure
what a box's content sets, and so may pass it: a table of amounts whose columns cannot narrow, a widget's own
width, what an automatic layout's cells hold beside one another (its columns are held to their cells' borders,
padding and min-widths, and each cell's content to the table's room alone), images or other boxes kept on one line
by ``nowrap`` or ``<nobr>``, a flex row's items side by side, a box shifted by a relative offset or a transform, a
first line set in by ``text-indent``, the padding an inline box adds to its line, and a run in a box narrower than
the panel's column, which is measured against the column. ``reach_problems`` allows the break rule on a cell of
its own, which must hold no amount: on an amount's cell it splits the amount. The header is the table capped at
600 px (its ``max-width``) that holds the wordmark, the name split by markup into its two styles, and a page
carries one. What the reader does not resolve, it refuses rather than guesses: a ``<style>`` block, an SVG's or
MathML's included, or a linked stylesheet, whose selectors it does not match, and a value one of its properties
takes from a function, such as ``calc()`` or ``var()``. It reads no text the page does not show: what
``display:none`` or the ``hidden`` attribute hides (a presentational hint, which ``display:revert`` drops and
``revert-layer`` keeps), what a browser's own style sheet hides (the head, and an input of type hidden and an
audio without its controls, whatever display a page gives them), nor an image's ``alt``, which shows only where
images are blocked. Text hidden another way, at ``font-size:0`` or in a box clipped to nothing, it reads as shown."""
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
# CSS Display 3's unusual elements (its Appendix B), on which display:contents computes to none: no box, no text.
_CONTENTS_IS_NONE = frozenset({
    "audio", "br", "canvas", "embed", "frame", "frameset", "iframe", "img", "input", "math", "meter", "object",
    "progress", "select", "svg", "textarea", "video", "wbr",
})
_WIDTH_HINTED = frozenset({"table", "td", "th", "col", "colgroup", "hr", "img", "iframe", "video", "canvas", "object", "embed", "svg"})
# The elements a browser's own style sheet sizes border-box, and the input types it draws as a button or a box.
_UA_BORDER_BOX = frozenset({"table", "button", "select", "meter", "progress"})
_BORDER_BOX_INPUTS = frozenset({"button", "submit", "reset", "checkbox", "radio", "color", "search"})
# The elements whose align of left or right floats them (an input drawn as an image too), and whose hspace sets
# their side margins (an iframe's sets none in Chromium 141).
_ALIGN_FLOATS = frozenset({"img", "table", "object", "embed", "iframe"})
_HSPACED = frozenset({"img", "object", "embed"})
# The functions that give a colour alone, which a border shorthand may take without setting a width.
_COLOUR_FUNCTIONS = frozenset({"rgb", "rgba", "hsl", "hsla", "hwb", "lab", "lch", "oklab", "oklch", "color", "color-mix", "light-dark"})
_UA_MARGIN = {"body": (8.0, 8.0), "blockquote": (40.0, 40.0), "figure": (40.0, 40.0), "dd": (40.0, 0.0), "fieldset": (2.0, 2.0)}
_UA_PADDING = {
    "ul": (40.0, 0.0), "ol": (40.0, 0.0), "menu": (40.0, 0.0), "dir": (40.0, 0.0), "fieldset": (12.0, 12.0), "button": (6.0, 6.0),
    "legend": (2.0, 2.0), "textarea": (2.0, 2.0),
}
_UA_BORDER = {"fieldset": 2.0, "button": 2.0, "hr": 1.0, "iframe": 2.0, "textarea": 1.0}
# An input's own side margins, padding and border, by its type, as Chromium 141's style sheet sets them, where they
# add to its width (a border-box input's hold no content the check reads): a type HTML does not know, or none, is a
# text field.
_INPUT_TYPES = frozenset({
    "button", "checkbox", "color", "date", "datetime-local", "email", "file", "hidden", "image", "month", "number",
    "password", "radio", "range", "reset", "search", "submit", "tel", "text", "time", "url", "week",
})
_FIELDS = frozenset({"text", "search", "tel", "url", "email", "password", "number"})
_CLOCKS = frozenset({"date", "time", "datetime-local", "month", "week"})
_INPUT_MARGIN = {"checkbox": (4.0, 3.0), "radio": (5.0, 3.0), "range": (2.0, 2.0)}
_INPUT_PADDING = {**dict.fromkeys(_FIELDS, (2.0, 2.0)), **dict.fromkeys(_CLOCKS, (1.0, 0.0))}
_INPUT_BORDER = dict.fromkeys(_FIELDS | _CLOCKS, 2.0)
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
        elif item.lower_name == "white-space" and not (
            len(words := [t for t in item.value if t.type != "whitespace"]) == 1 and words[0].lower_value in {*_WHITE_SPACE, *_GLOBAL}
        ):
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
        name == "input" and _input_type(element) == "hidden"
    )


def _laid_out(element: ElementTree.Element, display: str | None, reverted: bool = False) -> bool:
    """Whether a browser lays the element out where it lays out its parent, given the display its style gives it
    (None for its own, ``reverted`` when ``revert`` gives it): not ``display:none``, nor hidden by a browser's own
    style sheet, nor by the ``hidden`` attribute, a presentational hint, where its style gives it no display (which
    ``revert`` drops and ``revert-layer`` keeps, measured in Chromium 141)."""
    if display == "none" or _hidden_whatever_its_display(element):
        return False
    return display is not None or not (_hidden_by_its_element(element) or (element.get("hidden") is not None and not reverted))


def _laid_out_alone(element: ElementTree.Element) -> bool:
    """``_laid_out`` as the element's own style sets its display, for a table's rows, cells and columns, which a
    table reads before the walk reaches them."""
    display = _won(_declarations(element.get("style"))[0], "display")
    return _laid_out(element, None if display in ("revert", "revert-layer") else display, display == "revert")


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


def _input_type(element: ElementTree.Element) -> str:
    """An input's type as HTML reads it, case aside: a type it does not know, or none, is a text field."""
    kind = (element.get("type") or "").lower()
    return kind if kind in _INPUT_TYPES else "text"


def _width_hint(element: ElementTree.Element) -> str | None:
    """The width an element's ``width`` attribute maps: a table's or a cell's ignores a zero (HTML's nonzero
    dimension), and a column's a relative length such as ``3*`` (measured in Chromium 141)."""
    value, tag = element.get("width"), _local(element.tag)
    if tag in ("col", "colgroup") and "*" in (value or ""):
        return None
    width = _attribute_width(value)
    if tag in ("table", "td", "th") and width is not None and not float(width.rstrip("px%")):
        return None
    return width


def _rowspan(value: str | None) -> int:
    """A cell's ``rowspan``: the rows it takes, 1 unless the attribute gives a whole number; 0 takes the rest of its
    section, and HTML holds it to 65534."""
    count = _attribute_pixels(value)
    if count is None:
        return 1
    return min(int(count), 65534) if count else 65534


def _attribute_pixels(value: str | None) -> float | None:
    """A ``cellpadding``, ``cellspacing``, ``border`` or ``span`` attribute as HTML reads it: the whole number its
    digits start, by the rules for parsing non-negative integers, so ``5%`` is 5."""
    text = (value or "").lstrip(_SPACE)
    text = text[1:] if text.startswith("+") else text
    digits = len(text) - len(text.lstrip("0123456789"))
    return float(text[:digits]) if digits else None


def _span(value: str | None) -> int:
    """A ``colspan`` or a column's ``span``: 1 unless the attribute gives a whole number from 1 to 1000."""
    count = _attribute_pixels(value)
    return min(max(int(count), 1), 1000) if count else 1


def _as_px(width: str | None, room: float) -> float | None:
    """A width in px or in percent of ``room``, else None."""
    if width is None:
        return None
    if width.endswith("%"):
        return float(width[:-1]) / 100 * room
    return _px(width) if width.lstrip("0123456789.") in _ABSOLUTE else None


def _children(element: ElementTree.Element) -> list[ElementTree.Element]:
    return [child for child in element if isinstance(child.tag, str)]


def _has_fallback(element: ElementTree.Element) -> bool:
    """Whether an <object> holds fallback content, as Chromium reads it: any child but a <param> or text of
    whitespace alone, a comment among them. A browser lays it out in the line in the object's place; an object
    that holds none is placed whole, 300 px wide where it sets no width (measured in Chromium 141)."""
    return bool((element.text or "").strip(_SPACE)) or any(
        not (isinstance(child.tag, str) and _local(child.tag) == "param") or (child.tail or "").strip(_SPACE) for child in element
    )


def _may_load(element: ElementTree.Element) -> bool:
    """Whether an <object> asks for content, by a ``data`` or a ``type``: a browser places it whole where the
    content loads, as an image does, and shows its fallback where it does not, as a plugin's does."""
    return any((element.get(name) or "").strip(_SPACE) for name in ("data", "type"))


def _empty_embed(element: ElementTree.Element) -> bool:
    """Whether an <embed> lays out nothing, as one with neither a ``src`` nor a ``type`` does."""
    return element.get("src") is None and element.get("type") is None


def _image_remedy(shown: float, held: bool, margins: float, padding: float, room: float) -> str:
    """What would bring an image back inside its room: the width it shows at, whether a max-width already holds
    it there, its side margins, and the padding and borders its width leaves out. Each remedy that would do it
    alone, else all of them, so the advice names nothing the image already does."""
    remedies = []
    if shown > room + _SLACK:
        remedies.append(("lower its min-width" if held else "hold it to the room with max-width:100%", margins + room + padding))
    if margins:
        remedies.append(("drop its side margins", shown + padding))
    if padding:
        remedies.append(("set box-sizing:border-box so its width holds its padding and borders", margins + shown))
    alone = [remedy for remedy, takes in remedies if takes <= room + _SLACK]
    return ", or ".join(alone) if alone else ", and ".join(remedy for remedy, _ in remedies)


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
        self._cell_rooms: dict[int, float] = {}  # a cell -> the room its column gives its content, where the row sets it
        self._fixed_cells: set[int] = set()  # the cells of a fixed layout, whose own widths the columns replace
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
        reverted = display == "revert"
        if display in ("initial", "unset"):
            display = "inline"  # display's initial value, which unset takes, since display is not inherited
        elif display == "inherit":
            display = "inline" if parent.inline else "block"  # the parent's: as far as a run goes, inline or not
        elif display in _GLOBAL:
            display = None  # revert: the element's own, as a browser's style sheet gives it
        if display == "contents" and tag in _CONTENTS_IS_NONE:
            display = "none"
        shown = parent.shown and _laid_out(element, display, reverted)
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
        if tag == "br":
            crossed = False  # a line break whatever its float, position or display
        elif tag == "object":  # its fallback in the line, which a browser shows unless its content loads
            crossed = _has_fallback(element) and (display is None or _inline(display))
        elif tag == "embed":
            crossed = _empty_embed(element)
        elif display is not None:  # an element placed whole ends a run whatever its display: a line may wrap around it
            crossed = _inline(display) and (display == "contents" or tag not in _REPLACED and tag not in _WIDGETS)
        else:
            crossed = tag not in _RUN_EDGES
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
        if float_set in (None, "revert-layer"):  # an align of left or right, a hint below every declaration
            floats = (
                tag in _ALIGN_FLOATS or (tag == "input" and _input_type(element) == "image")
            ) and (element.get("align") or "").lower() in ("left", "right")
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
        if tag == "embed" and _empty_embed(element):
            return state  # with neither a src nor a type it lays out nothing, whatever its display
        drawn = tag == "input" and _input_type(element) == "image"  # an input drawn as an image is one
        if (tag in _REPLACED or drawn) and not (tag == "object" and _has_fallback(element) and not _may_load(element)):
            kind = "replaced"  # placed whole whatever its display; an object that may load is held, fallback or not
        elif display is not None and display not in ("none",):
            kind = (
                "atomic" if tag in _WIDGETS and display != "contents" and _inline(display)  # a control is one box in the line
                else "inline" if _inline(display)
                else "atomic" if display.startswith("inline") or display == "-webkit-inline-box"
                else "table" if display == "table"
                else "part" if display in ("table-row-group", "table-header-group", "table-footer-group", "table-row")
                else "cell" if display == "table-cell" and tag in _CELLS
                else "block"
            )
        else:  # an object showing its fallback lays it out in the line
            kind = (
                "table" if tag == "table"
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
        typed = _input_type(element) if tag == "input" else None
        ua_margin = _INPUT_MARGIN.get(typed, (0.0, 0.0)) if typed else _UA_MARGIN.get(tag, (0.0, 0.0))
        ua_padding = (0.0, 0.0) if kind == "cell" else _INPUT_PADDING.get(typed, (0.0, 0.0)) if typed else _UA_PADDING.get(tag, (0.0, 0.0))
        # A cell's padding is its table's cellpadding, 1 px without one: a hint, which revert drops.
        padding_hint = (parent.cell_padding if parent.cell_padding is not None else 1.0) if kind == "cell" else None
        border_attr = _attribute_pixels(element.get("border")) if tag in ("table", "img", "object") else None
        border_hint = border_attr if border_attr else (parent.cell_border if kind == "cell" and parent.cell_border else None)
        ua_border = _INPUT_BORDER.get(typed, 0.0) if typed else _UA_BORDER.get(tag, 0.0)
        hspace = _attribute_width(element.get("hspace")) if tag in _HSPACED else None  # a dimension: px or %
        margin_hint = _as_px(hspace, room)
        margins = 0.0 if kind == "cell" else sum(  # a cell takes no margin
            self._side(declared, f"margin-{side}", room, ua, margin_hint, named) for side, ua in zip(("left", "right"), ua_margin)
        )
        padding = sum(self._side(declared, f"padding-{side}", room, ua, padding_hint, named) for side, ua in zip(("left", "right"), ua_padding))
        borders = sum(self._border(declared, side, ua_border, border_hint, named) for side in ("left", "right"))
        extras = padding + borders
        hinted = _width_hint(element) if tag in _WIDTH_HINTED or drawn else None
        width = _won(declared, "width")
        if width in (None, "revert-layer"):
            width = hinted
        elif width in ("initial", "unset", "revert"):
            width = None
        sizing = _won(declared, "box-sizing")
        ua_border_box = tag in _UA_BORDER_BOX or typed in _BORDER_BOX_INPUTS
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
                f"borders, padding and margins, where its parent gives it {room:g} px on a {NARROWEST_SCREEN} px phone: "
                + _image_remedy(cap, cap_held, margins, 0.0 if border_box else extras, room)
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
            asked = min(set_to, cap) if cap is not None else set_to
            set_to = max(asked, least)
            # A cell set in percent takes its column's share of the table, which holds its padding and borders.
            share = kind == "cell" and width.endswith("%")
            over = share and float(width[:-1]) > 100  # a share past the whole table, whatever its layout
            box = max(set_to, extras) if share else set_to if border_box else set_to + extras
            # A fixed layout's columns replace its cells' own widths, and the table holds them together (_rows).
            if kind == "cell" and (over or box > room + _SLACK and id(element) not in self._fixed_cells):
                if over:
                    advice = "Chromium holds the cell to its table, but a share over 100% asks for more than the table has: keep it to 100% or less"
                elif least and least > (float(width[:-1]) / 100 * room if share else _px(width)):
                    advice = f"its min-width holds it at {least:g} px: lower the min-width, or set it in %"
                elif share:
                    advice = f"its borders and padding alone take {extras:g} px, more than its share: narrow them"
                else:
                    advice = (
                        "Chromium squeezes the cell, but CSS 2.1's automatic table layout reads a cell's width as its least, so "
                        "give it a percentage, whose share of the table holds its padding"
                    )
                self.box_problems.append(
                    f"{named} takes {box:g} px across, with its borders and padding, where its table gives it {room:g} px on a "
                    f"{NARROWEST_SCREEN} px phone: {advice}"
                )
            elif kind != "cell" and margins + box > room + _SLACK:
                if kind == "replaced":
                    advice = _image_remedy(set_to, cap_held, margins, 0.0 if border_box else extras, room)
                elif least > asked:
                    advice = f"its min-width holds it at {least:g} px: lower the min-width, or set it in %"
                elif margins + set_to > room + _SLACK:
                    advice = (
                        f"let it take the room up to a cap (width:100%;max-width:{set_to:g}px), with classic Outlook's "
                        "fixed width in a conditional comment"
                    ) + (f", and set its side margins to 0 (they take {margins:g} px)" if margins else "")
                else:
                    advice = "its borders, padding and margins add to its width: leave the width unset" + (
                        "" if border_box or not extras else ", or set box-sizing:border-box"
                    )
                self.box_problems.append(
                    f"{named} takes {margins + box:g} px across, with its borders, padding and margins, where its parent gives it "
                    f"{room:g} px on a {NARROWEST_SCREEN} px phone: {advice}"
                )
            content = max(min(box, room - margins) - extras, 0.0)
        if kind == "cell" and id(element) in self._cell_rooms:
            content = self._cell_rooms[id(element)]  # its column's width, which a fixed layout or a lone column sets
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
        elif declared_spacing == "refused":
            self.box_problems.append(f"{named}'s border-spacing is set by the font or the screen, which this check does not resolve: write it in px")
            spacing = 2.0
        else:
            spacing = float(declared_spacing[:-2])
        # A fixed layout needs a width; without one the table lays its columns out automatically.
        fixed = _won(declared, "table-layout") == "fixed" and width is not None
        cell_padding, cell_border = _attribute_pixels(element.get("cellpadding")), 1.0 if border_attr and tag == "table" else 0.0
        columns = self._rows(element, content, spacing, fixed, cell_padding, cell_border, named)
        return replace(
            state,
            room=content,
            cell_room=max(content - (max(columns, 1) + 1) * spacing, 0.0),  # less the spacing beside its columns
            cell_padding=cell_padding,
            cell_border=cell_border,
            fixed_layout=fixed,
        )

    def _rows(self, table, content: float, spacing: float, fixed: bool, padding: float | None, border: float, named: str) -> int:
        """A table's rows and columns side by side, against the room it gives them, as a browser lays them out:
        without the parts the page hides, the first header group first and the first footer group last (a
        ``<thead>`` or a ``<tfoot>``, or a section its display makes one), and each row's cells after the columns a
        cell above still spans. Under ``table-layout:fixed`` the columns keep the widths the ``<col>`` elements set,
        their cells' padding inside them, else the widths the first row's cells set, their padding added unless
        their box-sizing holds it, a cell across columns giving them its width less the spacing between them, and
        the other rows' widths go unread; those set in percent take what those set in px leave, the room left is
        shared out, and each cell is given its columns' width. In an automatic layout a cell set in px narrows, so
        each column is held to its widest cell's borders and padding and the columns to the table, with the
        spacing between them, and a lone column takes the table. Returns the number of columns."""
        sections: list[list[ElementTree.Element]] = []
        cols: list[ElementTree.Element] = []
        parts = [part for part in _children(table) if _laid_out_alone(part)]

        def group(part: ElementTree.Element) -> str | None:
            display = _won(_declarations(part.get("style"))[0], "display")
            if display in ("table-header-group", "table-footer-group", "table-row-group"):
                return display
            return {"thead": "table-header-group", "tfoot": "table-footer-group"}.get(_local(part.tag))

        # A table lays its first header group out first and its first footer group last, wherever the source puts them.
        groups = [part for part in parts if _local(part.tag) in ("tbody", "thead", "tfoot")]
        head = next((part for part in groups if group(part) == "table-header-group"), None)
        foot = next((part for part in groups if group(part) == "table-footer-group"), None)
        loose: list[ElementTree.Element] | None = None  # rows straight in the table: a section of their own
        for part in [head] * (head is not None) + [part for part in parts if part is not head and part is not foot] + [foot] * (foot is not None):
            name = _local(part.tag)
            if name == "tr":
                if loose is None:
                    loose = []
                    sections.append(loose)
                loose.append(part)
                continue
            loose = None
            if name in ("tbody", "thead", "tfoot"):
                sections.append([row for row in _children(part) if _local(row.tag) == "tr" and _laid_out_alone(row)])
            elif name == "colgroup":
                held = [col for col in _children(part) if _local(col.tag) == "col"]
                cols += [col for col in held if _laid_out_alone(col)] if held else [part]
            elif name == "col":
                cols.append(part)
        saved, self.box_problems = self.box_problems, []  # a cell's refusals are noted where its own box is read
        try:
            grid = [[[self._cell(cell, content, padding, border, named) for cell in _children(row) if _local(cell.tag) in _CELLS] for row in rows] for rows in sections]
        finally:
            self.box_problems = saved
        # Each row's cells with the column each starts in: a cell skips the columns a cell above still spans, within
        # its section.
        placed: list[list[tuple[tuple, int]]] = []
        for rows in grid:
            busy: dict[int, int] = {}  # a column -> the rows below that a cell above still takes in it
            for row in rows:
                at, here = 0, []
                for item in (cell for cell in row if cell is not None):
                    while busy.get(at):
                        at += 1
                    here.append((item, at))
                    at += item[1]
                busy = {k: left - 1 for k, left in busy.items() if left > 1}
                for item, start in here:
                    for k in range(start, start + item[1]):
                        busy[k] = max(busy.get(k, 0), _rowspan(item[0].get("rowspan")) - 1)
                placed.append(here)
        count = max([start + item[1] for here in placed for item, start in here] + [sum(_span(col.get("span")) for col in cols)], default=0)
        if not count:
            return 0
        gaps = (count + 1) * spacing
        room = max(content - gaps, 0.0)  # what the columns share, and what a percentage is of
        cells = [cell for here in placed for cell in here]
        if not fixed:
            if count > 1:
                # Each column's widest cell's borders and padding, a cell across columns spreading what its own exceed
                # over them alike (measured in Chromium 141).
                widest = [0.0] * count
                for (_, span, extras, _, border_box, least), at in sorted(cells, key=lambda cell: cell[0][1]):
                    need = max(extras, least) if border_box else extras + least  # a min-width holds the content box
                    reach = min(span, count - at)
                    inside = sum(widest[at : at + reach]) + (reach - 1) * spacing
                    for k in range(at, at + reach) if need > inside else ():
                        widest[k] += (need - inside) / reach
                least = sum(widest) + gaps
                if least > content + _SLACK:
                    self.box_problems.append(
                        f"{named}'s columns take {least:g} px across in their cells' borders, padding and min-widths alone, "
                        f"with the spacing between them, where it gives them {content:g} px on a {NARROWEST_SCREEN} px phone: "
                        "narrow their padding, or lower their min-widths"
                    )
            else:  # a lone column takes the table, whatever share its cell asks
                for (cell, _, extras, _, _, _), _ in cells:
                    self._cell_rooms[id(cell)] = max(room - extras, 0.0)
            return count
        widths: list[float | None] = [None] * count
        shares: list[bool] = [False] * count  # set in percent, which the table holds to its width together
        at = 0
        for col in cols:
            span, width = _span(col.get("span")), _won(_declarations(col.get("style"))[0], "width")
            if width in (None, "revert-layer"):
                width = _width_hint(col)
            for k in range(at, min(at + span, count)):
                if (px := _as_px(width, room)) is not None:
                    widths[k], shares[k] = px, width.endswith("%")
            at += span
        for (_, span, extras, width, border_box, _), at in placed[0] if placed else ():
            if (px := _as_px(width, room)) is not None:
                box = px if border_box else px + extras  # a percentage of the room sets the cell's content, as px do
                for k in range(at, min(at + span, count)):
                    if widths[k] is None:
                        widths[k] = max(box - (span - 1) * spacing, 0.0) / span  # less the spacing between its columns
                        shares[k] = width.endswith("%")
        in_px = sum(w for w, share in zip(widths, shares) if w is not None and not share)
        in_percent = sum(w for w, share in zip(widths, shares) if w is not None and share)
        if in_percent and in_percent > room - in_px:  # columns set in percent take what those set in px leave, down to none
            scale = max(room - in_px, 0.0) / in_percent
            widths = [w * scale if share and w is not None else w for w, share in zip(widths, shares)]
            in_percent *= scale
        total = in_px + in_percent + gaps
        if total > content + _SLACK:
            self.box_problems.append(
                f"{named}'s columns take {total:g} px across under table-layout:fixed, with the spacing between them, where it "
                f"gives them {content:g} px on a {NARROWEST_SCREEN} px phone: a fixed table layout keeps each column's width, "
                "so set them in percent"
            )
        # The room the columns leave goes to those that set no width, alike; else to those set in px, by their
        # widths; else to those set in percent, by theirs (measured in Chromium 141).
        left, unset = max(content - total, 0.0), [k for k, w in enumerate(widths) if w is None]
        if unset:
            columns = [left / len(unset) if w is None else w for w in widths]
        else:
            takers, weight = ([not share for share in shares], in_px) if in_px else (shares, in_percent)
            columns = [w + left * w / weight if takes and weight else w for w, takes in zip(widths, takers)]
        for (cell, span, extras, _, _, _), at in cells:
            taken = sum(columns[at : at + span]) + (min(span, count - at) - 1) * spacing
            self._cell_rooms[id(cell)] = max(taken - extras, 0.0)
            self._fixed_cells.add(id(cell))
        return count

    def _cell(self, cell, content: float, padding: float | None, border: float, named: str):
        """A cell as its row lays it out: the element, its span, its borders and padding, its width, whether its
        width holds them, and its min-width; None for a cell the page hides."""
        if not _laid_out_alone(cell):
            return None
        declared = _declarations(cell.get("style"))[0]
        extras = sum(self._side(declared, f"padding-{side}", content, 0.0, padding if padding is not None else 1.0, named) for side in ("left", "right"))
        extras += sum(self._border(declared, side, 0.0, border or None, named) for side in ("left", "right"))
        width = _won(declared, "width")
        if width in (None, "revert-layer"):
            width = _width_hint(cell)
        elif width in _GLOBAL:
            width = None
        return cell, _span(cell.get("colspan")), extras, width, _won(declared, "box-sizing") == "border-box", self._least(declared, content, named)

    def _column(self, element, declared, parent: _State, named: str) -> None:
        """A column's width and min-width against the room its table gives a cell, as a cell's are held."""
        width = _won(declared, "width")
        if width in (None, "revert-layer"):
            width = _width_hint(element)
        room = parent.cell_room if parent.cell_room is not None else parent.room
        if (least := self._least(declared, room, named)) > room + _SLACK:  # in either layout it widens the table
            self.box_problems.append(
                f"{named}'s min-width holds it at {least:g} px where its table gives a cell {room:g} px on a {NARROWEST_SCREEN} "
                "px phone: lower the min-width, or set it in %"
            )
        if width is None or width in _GLOBAL | _SIZING | {"auto"}:
            return
        if width.lstrip("0123456789.") in _RELATIVE:
            self.box_problems.append(f"{named}'s width {width} is set by the font or the screen, which this check does not resolve: write it in px or %")
            return
        set_to = float(width[:-1]) / 100 * room if width.endswith("%") else _px(width)
        if width.endswith("%") and float(width[:-1]) > 100:
            self.box_problems.append(
                f"{named} is set to {width} of its table, where its table gives a cell {room:g} px on a {NARROWEST_SCREEN} px "
                "phone: Chromium holds the column to its table, but a share over 100% asks for more than the table has: keep "
                "it to 100% or less"
            )
        elif set_to > room + _SLACK and not parent.fixed_layout:  # a fixed layout's columns are held together, at the table
            self.box_problems.append(
                f"{named} is set {set_to:g} px wide where its table gives a cell {room:g} px on a {NARROWEST_SCREEN} px phone: "
                "Chromium squeezes the column, but CSS 2.1's automatic table layout reads a column's width as its least, so "
                "give it a percentage"
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
