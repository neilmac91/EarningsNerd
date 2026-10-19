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
- ``viewports``: the viewports a page sets, wherever it sets them;
- ``colour_problems``: every colour a page writes, in a style's declarations or an attribute HTML maps to a colour
  (and VML's ``fillcolor``, ``strokecolor`` and ``color2``, which classic Outlook paints), in its own view and in
  classic Outlook's, is a design token's (``DESIGN.md``'s frontmatter, which
  ``frontend/tests/unit/designSnapshotParity.spec.ts`` holds to the frontend's token sources), written as
  six-digit hex, as the mail module writes every colour: a name, a colour function (``rgb()``, ``color-mix()``), a
  value read through ``attr()``, a short hex or a hex no token holds fails, and so does a colour the browser
  supplies: one of its own by name (``-webkit-link``, or a system colour such as ``LinkText``, ``CanvasText`` or a
  deprecated one, ``WindowText``), ``initial`` as ``color`` (black), ``revert`` or ``revert-layer`` (a link's
  blue; elsewhere they take the parent's colour, which the rule fails all the same), and a link that sets no
  colour a browser takes, none or one it drops (``#fffff``, a misspelt name, a ``light-dark()`` holding a CSS-wide
  keyword, or a ``var()``, which Gmail drops, inferred), which a client paints ``#0000EE``; in classic Outlook's
  view a ``light-dark()`` sets none, since its Word engine predates it (inferred). ``transparent`` and
  ``currentcolor`` write no colour of their own, nor do ``inherit`` and ``unset``, in either view, though that
  engine may predate ``currentcolor`` and ``unset`` too and paint a link so set its blue (inferred, and passed);
  and a font's name or a property's (``transition``'s ``background``, ``will-change``'s, under a vendor's prefix
  too) is none. Unread: a ``<style>`` block, which the other rules refuse in either view; an SVG's presentation
  attributes (``fill``) and VML's ``colors``, a gradient's stops; the colours a browser's own style sheet gives
  what a page leaves unstyled (an ``<hr>``'s grey, a ``<mark>``'s yellow, a form control's and a fieldset's
  border, a bordered table's grey, the keywords ``all`` sets, ``all:initial``'s black and a link's blue under
  ``all:revert``); and a URL printed as text, which Gmail and Apple Mail turn into a link in their own colour
  (inferred). A link whose text sits in a child of a token's colour, under ``text-decoration:none``, shows no
  blue, and fails all the same, and a word that names a colour where another property takes a name of its own,
  such as an animation's, is read as that colour (asking);
- ``hidden_text_problems``: every text a page holds and does not show its reader, in a browser's view, as rspamd
  reads it or in classic Outlook's view, and each declaration, attribute or element that can hide text in a way the
  reader does not model or resolve, any property or element it has not been taught among them (E110); the gate
  sets the preheader aside, the one text a page may hide;
- ``shown_text``: the text a page shows below its header, a line for each block, which a mail's text part says too;
- ``spamassassin_contrast_problems``: no text a page holds is one SpamAssassin 4.0 reads in an ink too like its
  ground, as its own HTML parser reads a text's colours (a port of it, on the tags the standard library's parser
  reads, not on ``tinyhtml5``'s tree), and each part of a page the port does not read as it does (E125).

A page is read as a browser builds it, by ``tinyhtml5``, the WHATWG tree builder (``requirements.in``): an end tag
a browser implies is implied, a ``/>`` on an element that is not void is ignored, the first of two same-named
attributes is kept, a formatting element left open is opened again where the parser opens it, and text a table
cannot hold moves before it. rspamd's HTML parser builds a tree of its own off the same tags (html.cxx): it
implies no end tag, closes a tag written with a closing /, reads a noscript, a script and a style alone as text,
to an end tag of any name it takes for one, and decodes a character reference in a tag's or an attribute's name,
so ``hidden_text_problems``, which reads rspamd's view on a browser's tree, refuses a page whose two trees part,
one that holds such raw text or such a name, and one a browser reads with any parse error but a character's or a
second attribute's. A comment holds no markup, so what Outlook's conditional comments hold is read only in
Outlook's view (``outlook_view``). Each element's ``style`` attribute is read as CSS reads one, by ``tinycss2``:
comments and escapes decoded, a declaration its property cannot take dropped, an important declaration over a
normal one, and among equals the last. The text properties read here are inherited: ``inherit`` and ``unset`` take
the parent's value, ``revert`` the element's own default, such as ``<pre>``'s, or the parent's. A cell's
``nowrap`` attribute and a table's ``width``, ``border``, ``cellpadding`` and ``cellspacing`` are presentational
hints, below every declaration of a ``style``: ``revert`` removes them with the style, and ``revert-layer``, which
rolls back to the layer below, keeps them (measured in Chromium 141).

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
field's 2 px border and 2 px padding (a date or a time field's 1 px at its start), a text area's 1 px border and 2
px padding, a range slider's 2 px margins and a legend's 2 px padding, an input of a type HTML does not know being
a text field (measured in Chromium 141). ``revert`` drops the attributes' values and ``revert-layer`` keeps them
(measured in Chromium 141). The shell's own boxes leave a body ``WIDEST_FIXED``. A box's width is its ``width`` in
its ``style``, else its ``width`` attribute where HTML maps one (a table's, a cell's, a column's, a rule's, an
image's, an input drawn as an image's or another replaced element's): a number is pixels, a number then ``%`` a
percentage of the room, save that a table's or a cell's zero sets none (HTML's nonzero dimension), nor does a
column's relative length such as ``3*``. An ``<svg>``'s is a presentation attribute, which CSS reads as it reads
``width``, a number with no unit being px and a CSS-wide keyword setting none, so ``30em`` is a length the font
sets; and a length past Chromium's longest, 2^25 px, is held to it, as Chromium clamps it (measured in Chromium
141). A
table, a button, a select, a meter, a progress and an input drawn as a button, a box, a colour well or a search
field count their border and padding in their width, as a browser's own style sheet sets them; another box, a
``<div>`` set ``display:table`` among them, adds them, and so does one of those a page sets ``content-box``: a
button's and a button input's 6 px padding and 2 px border, a colour well's 2 px padding and 1 px border and a
select's 1 px border (measured in Chromium 141). A box set wider than its room fails, whether a fixed width, a
percentage over 100% or a ``min-width`` sets it, and so do margins, borders and padding that leave a box's content
no room. A ``max-width`` in pixels caps a width; one in percent holds an image or another replaced element alone,
since in a table's cell it does not hold the box's own content (CSS Sizing 3, its cyclic percentages). An image or
another replaced element with no width shows at its natural size, which the reader does not know, so it fails
unless a ``max-width`` holds it, and then it may show as wide as that, with its margins, borders and padding
added. An ``<object>`` whose ``data`` or ``type`` asks for content is held as a replaced element even where it
holds fallback, since the content may load. A width set by the font or the screen, such as ``em`` or ``vw``, by
the parent (``inherit``), or by the content (``max-content``) is refused rather than guessed, and so is a margin,
a padding or a table's spacing set that way. An inline element's box takes no width, save an image, another
replaced element or a form control, which a browser places whole, as one box, whatever display a page gives it, a
table's or a table part's among them, save a marquee, which Chromium lays out as the table part a page makes it.

A table's cells and columns are read as its layout reads them, without the rows, sections, cells and columns the
page hides: its first header group (a ``<thead>``, or a section its display makes one) first and its first footer
group last, wherever the source puts them, and each row's cells after the columns a cell above still spans, within
its section. A cell's room is its table's, less the spacing beside its columns (a cell across columns holds the
spacing between them), and a percentage is of that room. A lone column takes the whole table in either layout,
whatever share its cell asks. In an automatic layout, where a cell set in px narrows, a cell set in percent takes
its share, its padding and borders inside it, and its content is held to the share; a column that no cell starts
in and no ``<col>`` keeps is laid out as part of the column before it, its spacing dropped, past the last cell's
columns as well as between them. A ``<col>`` keeps its column with a width, in px or in percent: its own, or where
it sets none (``auto``, a sizing keyword or a CSS-wide keyword), its ``<colgroup>``'s in px (``inherit`` takes the
colgroup's percentage too), a ``<colgroup>``'s ``inherit`` taking its table's width; a min-width keeps none. Each
column is held to its widest lone cell's borders, padding and min-width (a lone cell spans one column) and to its
``<col>``'s min-width; a column laid out as part of another adds its ``<col>``'s min-width to the table's least
width, past what that one holds, save past every column kept, where Chromium drops it. The cells across columns
follow, as Chromium takes them, those across the fewest first, then from the left, whatever their rows: one whose
columns are all laid out as one widens that one, which a cell taken after it may use, and each other set of
columns adds the most one of its cells needs past the widths so far. Chromium spreads that excess over the columns
by their content, which the reader does not measure, and a ``<col>``'s min-width under it takes it or adds to it
as the spread falls, so each set adds its excess in full, past the min-widths: exact where such sets share no
column, no ``<col>``'s min-width sits under one and no cell across columns laid out as one is taken after a set
over its column, and never short of Chromium otherwise (measured in Chromium 141). The columns, a lone column
included, with the spacing beside them, are held to the table's room, and a cell or a column (``<col>``) set wider
than its table fails: Chromium squeezes it, while CSS 2.1's automatic table layout reads its width as its minimum.
A column's min-width past its table fails in either layout, save one in percent under ``table-layout:fixed``,
which Chromium ignores, and so do the columns' together. Under ``table-layout:fixed``, which needs a width, every
column is kept, with the widths its ``<col>`` elements set (a ``<col>``'s 0% none, its ``inherit`` its
``<colgroup>``'s, a ``<colgroup>``'s own ``inherit`` its table's, and a ``<colgroup>``'s width over its other
``<col>`` elements unread), their cells' padding inside, else the widths the first row (the first a browser lays
out) sets, in px or in percent; where a ``<col>`` and a lone first-row cell both set one in percent, the cell's
when it is the larger, with its padding, else the ``<col>``'s, the padding inside, and a first-row cell across
columns leaves a ``<col>``'s. A max-width caps a width in its own unit: a cell's in px, before its padding and
above its min-width in px, or in percent; a ``<col>``'s in percent alone. Each cell's padding is added unless its
box-sizing holds it, and then a width in px holds at least the padding, one in percent not; a cell across columns
gives them its width less the spacing between them, save one set in percent, whose share splits over them, its
padding and their spacing aside. A ``<col>``'s min-width in px holds the table's least width, and the column too
where a ``<col>``, a lone cell or a percentage across columns sets its width, save under a first-row cell across
columns set in px, where it holds neither; the other rows' widths go unread, as do a first-row cell's min-width
save under its max-width, a max-width in another unit than its width, and a ``<col>``'s min-width in percent
(measured in Chromium 141). Columns set in percent take what those set in px leave, down to none, so the columns
set in px, with the spacing between them, are held to the table; the room the columns a width sets leave goes to
the columns that set none, alike, whatever their min-widths, else to those set in px, by their held widths, else
to those set in percent; and each cell is given its columns' width. A share over 100% fails in either layout,
though Chromium holds it to the table, and a fixed layout's percentages over 100% in all are refused, which
Chromium scales in ways the reader does not resolve (measured in Chromium 141; that WebKit's table layout does the
same is inferred).

Outlook's view is the page as classic Outlook reads its conditional comments, as Outlook 2016 and later
(``mso 16``) take their conditions: ``mso`` and ``vml`` true, a version compared, ``IE`` false, and ``!``,
``&``, ``|`` and brackets as written. What a condition Outlook takes holds shows there, and what one it does not
take holds does not, in a comment or in a revealed block (``<![if !mso]>``); a condition the reader cannot
parse hides what it holds. A column capped at 600 px is held when the nearest table around it set to a fixed
width is 600 px wide, and a ``<style>`` block or a linked stylesheet in Outlook's view is refused there, as it is
in the page's own.

The reader errs toward asking for the rule: it counts no break a browser may take at a hyphen or after a question
mark, or at a ``<wbr>`` under ``nowrap``, where Chromium breaks, and no width that holds a run in, such as a fixed
table layout or a clipped box, so it may ask for the rule where a browser would fit the run; it holds a percentage
cell's content to its share, and a cell's set in px in an automatic layout to its width, where Chromium may widen
the column at the others' cost; it counts in full the excess of each set of columns that cells span, past the
``<col>`` min-widths under it, where Chromium may share it with another set or let a min-width take it, and it
widens a column by a cell across columns laid out as one past what the cells taken before it set, not what they
spread there, which Chromium may let it take; it holds a ``<col>``'s min-width on a column no cell starts in, past
every column kept, against its table, where Chromium drops it; it keeps a column a ``<col>`` sets 0 wide or
collapses (``visibility:collapse``), which Chromium lays out as part of the one before it, a 0 that no min-width
holds; it holds an automatic layout's column to its ``<col>``'s min-width in percent, which Chromium ignores; it
holds a fixed layout's ``<col>`` min-width in px against its table under a first-row cell across columns set in
px, which Chromium ignores there; it scales a fixed layout's columns set in percent against the widths set in px
before their ``<col>`` min-widths hold them, where Chromium scales against the held widths; it reads a fixed
layout's first-row cell's min-width as any box's, though the layout ignores it; it holds a marquee set to a table
part's display as one box; and it reads an object that asks for content both ways, its fallback in the line and
its box held. It does not measure what a box's content sets, and so may pass it: a table of amounts whose columns
cannot narrow, a widget's own width, what an automatic layout's cells hold beside one another (its columns are
held to their cells' borders, padding and min-widths, and each cell's content to the table's room alone), images
or other boxes kept on one line by ``nowrap`` or ``<nobr>``, a flex row's items side by side, a box shifted by a
relative offset or a transform, a first line set in by ``text-indent``, the padding an inline box adds to its
line, and a run in a box narrower than the panel's column, which is measured against the column.
``reach_problems`` allows the break rule on a cell of its own, which must hold no amount: on an amount's cell it
splits the amount. The header is the table capped at 600 px (its ``max-width``) that holds the wordmark, the name
split by markup into its two styles, and a page carries one. What the reader does not resolve, it refuses rather
than guesses: a ``<style>`` block, an SVG's or MathML's included, or a linked stylesheet, whose selectors it does
not match, and a value one of its properties takes from a function, such as ``calc()`` or ``var()``. It reads no
text the page does not show: what ``display:none`` or the ``hidden`` attribute hides (a presentational hint, which
``display:revert`` drops and ``revert-layer`` keeps; ``hidden="until-found"`` hides none, its box laid out and its
content skipped, which the reader reads, and a hidden ``<embed>`` is laid out at a width of 0 unless the page sets
one), what a browser's own style sheet hides (the head, a popover that sets no display, which no script opens, and
an input of type hidden and an audio without its controls, whatever display a page gives them), nor an image's
``alt``, which shows only where images are blocked.
Text hidden another way, at ``font-size:0`` or in a box clipped to nothing, it reads as shown, and
``hidden_text_problems`` fails it."""
from __future__ import annotations

import math
import re
import struct
import xml.etree.ElementTree as ElementTree
from bisect import bisect_right
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from functools import cache
from html.entities import html5, name2codepoint
from html.parser import HTMLParser
from pathlib import Path

import tinycss2
import tinyhtml5
from tinycss2.ast import Node
from tinycss2.color4 import parse_color
from tinyhtml5.constants import Token
from tinyhtml5.tokenizer import HTMLTokenizer

# A run this long, with nowhere to break, can fill the panel's text column on the narrowest phone. In
# Chromium's phone view at 320 px, where the mail's font stacks resolve to Inter here, the shortest runs of a
# token that held the page wider than the screen were 22 characters at 16 px and 21 in bold, the panel's
# largest text, and 18 at 20 px. The check takes 18, three under the panel's own, so a run of wide letters, or
# one set up to 20 px, is flagged before it fills the column; a larger font is not held (17 capitals in bold at
# 24 px already fill it), nor a letter spacing above normal, which widens every character, and a phone's own font
# sets the widths there
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
_LONGEST = 2.0**25  # Chromium's longest layout length, in px, to which it clamps a longer one (measured in Chromium 141)
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
_UA_BORDER = {"fieldset": 2.0, "button": 2.0, "hr": 1.0, "iframe": 2.0, "textarea": 1.0, "select": 1.0}
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
_BUTTONS = frozenset({"button", "submit", "reset"})
_INPUT_PADDING = {
    **dict.fromkeys(_FIELDS, (2.0, 2.0)), **dict.fromkeys(_CLOCKS, (1.0, 0.0)), **dict.fromkeys(_BUTTONS, (6.0, 6.0)), "color": (2.0, 2.0),
}
_INPUT_BORDER = {**dict.fromkeys(_FIELDS | _CLOCKS | _BUTTONS, 2.0), "color": 1.0}
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
    """A CSS number as the reader compares it, written out in full, held to Chromium's largest layout length, to
    which it clamps a longer one (``1e999px``)."""
    return f"{min(value, _LONGEST):f}".rstrip("0").rstrip(".")


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
    hides, a <dialog> that is not open, and a popover, which no script opens (measured in Chromium 141)."""
    name = _local(element.tag)
    return name in _UNSHOWN or (name == "dialog" and element.get("open") is None) or element.get("popover") is not None


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
    hidden = element.get("hidden") is not None and element.get("hidden").lower() != "until-found" and _local(element.tag) != "embed"
    return display is not None or not (_hidden_by_its_element(element) or (hidden and not reverted))


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
    dimension), and a column's a relative length such as ``3*`` (measured in Chromium 141). An ``<svg>``'s is a
    presentation attribute, which CSS reads as it reads ``width``, a number with no unit being px and a CSS-wide
    keyword setting none: ``30em`` is a length the font sets, where HTML reads an image's as 30 px (measured in
    Chromium 141)."""
    value, tag = element.get("width"), _local(element.tag)
    if tag == "svg":
        parts = [token for token in tinycss2.parse_component_value_list(value or "", skip_comments=True) if token.type != "whitespace"]
        if len(parts) == 1 and parts[0].type == "number" and parts[0].value >= 0:
            return _number(parts[0].value) + "px"
        width = _value("width", parts)
        return None if width in _GLOBAL else width  # a CSS-wide keyword sets no width there (Chromium 141 lays it out as unset)
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


def _set_width(element: ElementTree.Element) -> str | None:
    """The width an element's style sets, else the one its ``width`` attribute maps (``revert-layer`` keeping it)."""
    width = _won(_declarations(element.get("style"))[0], "width")
    return _width_hint(element) if width in (None, "revert-layer") else width


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
        self._span_rooms: dict[int, float] = {}  # a cell across columns -> its room, the spacing between them included
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
                else "block" if tag in _WIDGETS  # a control is one box, a table's or a table part's display aside
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
                else "block" if tag in _RUN_EDGES and tag not in ("br", "col", "colgroup", "math")  # a caption is a block, its padding inside the table
                else "inline"
            )
        if out_of_line and kind in ("inline", "block"):
            kind = "atomic"  # a float or a positioned box shrinks to its content
        if kind == "inline":
            return state
        if kind == "part":
            return replace(state, room=parent.cell_room if parent.cell_room is not None else parent.room)
        room = self._span_rooms.get(id(element), parent.cell_room) if kind == "cell" and parent.cell_room is not None else parent.room
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
        if tag == "embed" and element.get("hidden") is not None and (width == "revert" or (width in (None, "revert-layer") and hinted is None)):
            width = "0px"  # a hidden embed is laid out, its own style sheet's width 0 below the page's (HTML's rendering)
        elif width in (None, "revert-layer"):
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
        """A table's rows and columns side by side, against the room it gives them, as a browser lays them out: without
        the parts the page hides, the first header group first and the first footer group last (a ``<thead>`` or a
        ``<tfoot>``, or a section its display makes one), and each row's cells after the columns a cell above still
        spans. Under ``table-layout:fixed`` every column is kept, with the width its ``<col>`` sets (its 0% none, its
        ``inherit`` its ``<colgroup>``'s, a ``<colgroup>``'s ``inherit`` its table's), its cells' padding inside, else
        the width the first row's cell sets (a lone cell's larger percentage over a ``<col>``'s, with its padding), a
        ``<col>``'s percentage capped by a max-width in percent and a cell's width by one in its own unit, a cell's
        padding added unless its box-sizing holds it (a width in px then holding at least the padding), and a cell
        across columns giving them its width less the spacing between them (a percentage's share splits over them, its
        padding and their spacing aside); percentages over 100% in all are refused; a ``<col>``'s min-width in px holds
        the table's least width, and a column a width sets, save under a first-row cell across columns set in px, where
        it holds neither; the other rows' widths go unread; those set in percent take what those set in px leave, the
        room left is shared out, and each cell is given its columns' width. In an automatic layout a column no cell
        starts in and no ``<col>`` keeps (with a width, its own or its ``<colgroup>``'s, a ``<colgroup>``'s ``inherit``
        its table's) is laid out as part of the one before it; a cell set in px narrows, so each column is held to its
        widest lone cell's borders, padding and min-width (a lone cell spans one column) and to its ``<col>``'s
        min-width, and the min-widths of the columns laid out as part of it add to the table's least width past that,
        save past every column kept; the cells across columns follow, those across the fewest first, then from the
        left, one whose columns are laid out as one widening that one and each other set of columns adding the most one
        of its cells needs past the widths so far; and the columns, a lone one included, are held to the table with the
        spacing beside them; a lone column takes the table. Returns the number of columns laid out."""
        sections: list[list[ElementTree.Element]] = []
        cols: list[ElementTree.Element] = []
        around: dict[int, ElementTree.Element] = {}  # each <col> -> the <colgroup> it sits in
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
        # tinyhtml5 holds a table's rows in a <tbody> and its columns in a <colgroup>, as a browser's parser does.
        for part in [head] * (head is not None) + [part for part in parts if part is not head and part is not foot] + [foot] * (foot is not None):
            name = _local(part.tag)
            if name in ("tbody", "thead", "tfoot"):
                sections.append([row for row in _children(part) if _local(row.tag) == "tr" and _laid_out_alone(row)])
            elif name == "colgroup":
                held = [col for col in _children(part) if _local(col.tag) == "col"]
                cols += [col for col in held if _laid_out_alone(col)] if held else [part]
                around.update((id(col), part) for col in held)
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
        cells = [cell for here in placed for cell in here]
        # An automatic layout keeps a column that a <col> sets a width on, in px or in percent: its own, or where it sets
        # none, its <colgroup>'s in px (inherit takes the colgroup's percentage too), a <colgroup>'s inherit taking its
        # table's width (measured in Chromium 141).
        def width_of(part: ElementTree.Element) -> str | None:
            width = _set_width(part)
            return _set_width(table) if width == "inherit" and _local(part.tag) == "colgroup" else width

        kept, at = [False] * count, 0
        for col in cols:
            span, width = _span(col.get("span")), width_of(col)
            if width in _GLOBAL | _SIZING | {"auto", None} and id(col) in around:
                given = width_of(around[id(col)])
                width = given if width == "inherit" or not (given or "%").endswith("%") else None
            if width is not None and width not in _GLOBAL | _SIZING | {"auto"}:
                kept[at : at + span] = [True] * len(kept[at : at + span])
            at += span
        # An automatic layout lays a column that no cell starts in and no <col> keeps out as part of the column before it,
        # its spacing dropped, whatever the <col>'s min-width; a fixed layout keeps every column (measured in Chromium 141).
        begun = {at for _, at in cells}
        starts = list(range(count)) if fixed else sorted(begun | {k for k in range(count) if kept[k]})
        lane = [bisect_right(starts, k) - 1 for k in range(count)]  # each column -> the one it is laid out as
        lanes = len(starts)
        gaps = (lanes + 1) * spacing
        room = max(content - gaps, 0.0)  # what the columns share, and what a percentage is of
        for (cell, span, *_), at in cells:
            if span > 1:  # a cell across columns holds the spacing between them
                self._span_rooms[id(cell)] = room + (lane[at + span - 1] - lane[at]) * spacing
        floors, at = [0.0] * count, 0  # each column's least width, as its <col> sets it, against what the columns share
        saved, self.box_problems = self.box_problems, []  # a column's refusals are noted where the walk reads it
        try:
            for col in cols:
                declared = _declarations(col.get("style"))[0]
                span, floor = _span(col.get("span")), self._least(declared, room, named)
                if fixed and (_won(declared, "min-width") or "").endswith("%"):
                    floor = 0.0  # a fixed layout ignores a <col>'s min-width in percent (measured in Chromium 141)
                for k in range(at, at + span):
                    floors[k] = max(floors[k], floor)
                at += span
        finally:
            self.box_problems = saved
        if not fixed:
            # Each column holds its widest lone cell's borders, padding and min-width (a lone cell spans one column),
            # and its <col>'s min-width; a column laid out as part of another adds its <col>'s min-width to the table's
            # least width, past what that one holds, save past every column kept, where Chromium drops it, under a cell
            # across columns or not. Chromium takes the cells across columns after the lone ones, those across the
            # fewest first, then from the left, whatever their rows: one whose columns are all laid out as one widens
            # that one, which a cell taken after it may use, and each other set of columns adds the most one of its
            # cells needs past the widths so far. Chromium spreads that excess over the columns by their content, which
            # this check does not measure, and a <col>'s min-width under it takes it or adds to it as the spread falls,
            # so each set adds its excess in full, past the min-widths: exact where such sets share no column, no
            # <col>'s min-width sits under one and no cell across columns laid out as one is taken after a set over
            # its column, and never short of Chromium otherwise (measured in Chromium 141).
            kept_columns = set(starts)
            # The min-widths of the columns laid out as part of another, each with a column kept after it.
            added = sum(floors[k] for k in range(count) if k not in kept_columns and lane[k] < lanes - 1)
            lone = [0.0] * lanes  # each column's widest lone cell, then the widest cell across columns it lays out alone
            across: list[tuple[int, int, int, int, float]] = []  # each cell across columns: span, column, first, last, need
            for (_, span, extras, _, border_box, least), at in cells:
                need = max(extras, least) if border_box else extras + least  # a min-width holds the content box
                if span == 1:
                    lone[lane[at]] = max(lone[lane[at]], need)
                else:
                    across.append((span, at, lane[at], lane[at + span - 1], need))
            excess: dict[tuple[int, int], float] = {}  # a set of columns, by its first and its last -> its excess
            for _, _, first, last, need in sorted(across, key=lambda cell: cell[:2]):
                if first == last:
                    lone[first] = max(lone[first], need)
                else:
                    past = need - sum(lone[first : last + 1]) - (last - first) * spacing
                    excess[first, last] = max(excess.get((first, last), 0.0), past)
            least = sum(max(cell, floors[starts[k]]) for k, cell in enumerate(lone)) + added + sum(excess.values()) + gaps
            if least > content + _SLACK:
                self.box_problems.append(
                    f"{named}'s columns take {least:g} px across in their cells' borders, padding and min-widths alone, "
                    f"with the spacing between them, where it gives them {content:g} px on a {NARROWEST_SCREEN} px phone: "
                    "narrow their padding, or lower their min-widths"
                )
            if lanes == 1:  # a lone column takes the table, whatever share its cell asks
                for (cell, _, extras, _, _, _), _ in cells:
                    self._cell_rooms[id(cell)] = max(room - extras, 0.0)
            return lanes
        widths: list[float | None] = [None] * count
        shares: list[bool] = [False] * count  # set in percent, which the table holds to its width together
        holds = [True] * count  # whether a <col>'s min-width holds the column: not where a cell across columns sets it in px
        asked = [0.0] * count  # each column's percentage, in px of the room, its padding aside
        at = 0
        for col in cols:
            declared = _declarations(col.get("style"))[0]
            span, width = _span(col.get("span")), width_of(col)
            if width == "inherit" and id(col) in around:
                width = width_of(around[id(col)])  # a <col>'s inherit takes its <colgroup>'s width (measured in Chromium 141)
            if width is not None and width.endswith("%") and not float(width[:-1]):
                width = None  # a <col>'s 0% sets no width, where its 0 px sets 0 (measured in Chromium 141)
            if (px := _as_px(width, room)) is not None:
                cap = _won(declared, "max-width")
                if width.endswith("%") and (cap or "").endswith("%") and (limit := _as_px(cap, room)) is not None:
                    px = min(px, limit)  # a <col>'s max-width in percent caps a width in percent, and no other (measured)
                for k in range(at, at + span):
                    widths[k], shares[k], asked[k] = px, width.endswith("%"), px if width.endswith("%") else 0.0
            at += span
        for (cell, span, extras, width, border_box, _), at in placed[0] if placed else ():
            if (px := _as_px(width, room)) is None:
                continue
            declared, percent = _declarations(cell.get("style"))[0], width.endswith("%")
            cap = _won(declared, "max-width")
            if cap is not None and cap.endswith("%") == percent and (limit := _as_px(cap, room)) is not None:
                low = _won(declared, "min-width") or ""
                floor = _as_px(low, room) if not percent and not low.endswith("%") else None
                px = min(px, max(limit, floor or 0.0))  # a max-width caps a width in its own unit, its padding aside, and
                # a min-width in px holds a cap in px (measured in Chromium 141)
            if percent and span > 1:
                share = px / span  # a percentage across columns splits over them, its padding and their spacing aside
            else:
                # A lone cell's percentage sets its content, as px do; a border-box width in px holds at least the cell's
                # padding and borders, and one in percent does not (measured in Chromium 141).
                box = (px if percent else max(px, extras)) if border_box else px + extras
                share = max(box - (span - 1) * spacing, 0.0) / span  # less the spacing between its columns
            for k in range(at, at + span):
                if widths[k] is None:
                    widths[k], shares[k], holds[k], asked[k] = share, percent, percent or span == 1, px / span if percent else 0.0
                elif shares[k] and percent and span == 1 and px > asked[k]:
                    # A <col>'s percentage gives way to a larger one in a lone first-row cell, which brings its padding;
                    # an equal or smaller one, or one across columns, leaves the <col>'s, its padding inside (measured in
                    # Chromium 141).
                    widths[k], asked[k] = share, px
        if sum(asked) > room + _SLACK:
            self.box_problems.append(
                f"{named}'s columns set in percent ask for {sum(asked):g} px under table-layout:fixed, more than the {room:g} "
                f"px it gives them on a {NARROWEST_SCREEN} px phone: Chromium scales them in ways this check does not resolve, "
                "so keep their shares to 100% or less in all"
            )
        in_px = sum(w for w, share in zip(widths, shares) if w is not None and not share)
        in_percent = sum(w for w, share in zip(widths, shares) if w is not None and share)
        if in_percent and in_percent > room - in_px:  # columns set in percent take what those set in px leave, down to none
            scale = max(room - in_px, 0.0) / in_percent
            widths = [w * scale if share and w is not None else w for w, share in zip(widths, shares)]
        # A <col>'s min-width holds the table's least width, and a column a width sets, save under a first-row cell
        # across columns set in px, where it holds neither (measured in Chromium 141).
        held = [max(w, floor) if w is not None and hold else w for w, floor, hold in zip(widths, floors, holds)]
        total = sum(max(w or 0.0, floor) if hold else w or 0.0 for w, floor, hold in zip(widths, floors, holds)) + gaps
        if total > content + _SLACK:
            self.box_problems.append(
                f"{named}'s columns take {total:g} px across under table-layout:fixed, with the spacing between them, where it "
                f"gives them {content:g} px on a {NARROWEST_SCREEN} px phone: a fixed table layout keeps each column's width, "
                "so set them in percent"
            )
        # The room the columns a width sets leave goes to those that set none, alike, whatever their min-widths;
        # else to those set in px, by their held widths; else to those set in percent, by theirs (measured in
        # Chromium 141).
        left = max(content - sum(w for w in held if w is not None) - gaps, 0.0)
        unset = [k for k, w in enumerate(held) if w is None]
        if unset:
            columns = [left / len(unset) if w is None else w for w in held]
        else:
            in_px = sum(w for w, share in zip(held, shares) if not share)
            takers, weight = ([not share for share in shares], in_px) if in_px else (shares, sum(held))
            columns = [w + left * w / weight if takes and weight else w for w, takes in zip(held, takers)]
        for (cell, span, extras, _, _, _), at in cells:
            taken = sum(columns[at : at + span]) + (span - 1) * spacing
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
        # In either layout a min-width widens the table, save one in percent under table-layout:fixed, which Chromium
        # ignores (measured in Chromium 141).
        ignored = parent.fixed_layout and (_won(declared, "min-width") or "").endswith("%")
        if (least := 0.0 if ignored else self._least(declared, room, named)) > room + _SLACK:
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


# The design tokens' colours, which a page may write: DESIGN.md's frontmatter.
DESIGN = Path(__file__).resolve().parents[3] / "DESIGN.md"
# The attributes HTML maps to a colour, by its rules for parsing a legacy colour value, which turn any word into one
# save "transparent", which sets none.
_COLOUR_ATTRIBUTES = frozenset({"bgcolor", "color", "text", "link", "vlink", "alink", "bordercolor", "fillcolor", "strokecolor", "color2"})
# The words a colour may take that write no colour of their own.
_NO_COLOUR = frozenset({"transparent", "currentcolor"})
# The browser's own colours, by name, which no token holds: WebKit's link and focus colours and text (Chromium 141
# takes -webkit-link and -webkit-activelink and drops the other two; WebKit takes all four, inferred), and CSS's
# system colours, the deprecated ones among them, which Chromium 141 paints too (black, white, grey).
_BROWSER_COLOURS = frozenset({
    "-webkit-link", "-webkit-activelink", "-webkit-focus-ring-color", "-webkit-text", "canvas", "canvastext",
    "linktext", "visitedtext", "activetext", "buttonface", "buttontext", "buttonborder", "field", "fieldtext",
    "highlight", "highlighttext", "selecteditem", "selecteditemtext", "mark", "marktext", "graytext", "accentcolor",
    "accentcolortext", "activeborder", "activecaption", "appworkspace", "background", "buttonhighlight",
    "buttonshadow", "captiontext", "inactiveborder", "inactivecaption", "inactivecaptiontext", "infobackground",
    "infotext", "menu", "menutext", "scrollbar", "threeddarkshadow", "threedface", "threedhighlight",
    "threedlightshadow", "threedshadow", "window", "windowframe", "windowtext",
})
# The keywords that leave color to the browser's own style sheet: black at its initial value; under revert, a link's
# blue (elsewhere the parent's colour, which the rule fails all the same).
_BROWSER_DEFAULTS = frozenset({"initial", "revert", "revert-layer"})
_CSS_WIDE = frozenset({"inherit", "unset"}) | _BROWSER_DEFAULTS
# The properties whose words name fonts or other properties, not colours ("Red Hat Text" is no red, nor a transition's
# background the system colour Background), under a vendor's prefix too (-webkit-transition).
_NAMING = frozenset({"font", "font-family", "transition", "transition-property", "will-change"})
_VENDOR = re.compile(r"^-(?:webkit|moz|ms|o)-")


@cache
def token_colours() -> frozenset[str]:
    """Every colour DESIGN.md's frontmatter names, as ``#RRGGBB`` in capitals."""
    front = DESIGN.read_text(encoding="utf-8").split("---", 2)[1]
    return frozenset(value.upper() for value in re.findall(r'"(#[0-9A-Fa-f]{6})"', front))


def _colour_tokens(tokens) -> list[Node]:
    """The tokens of a declaration's value that write a colour: a hex, a name, one of the browser's own colours by
    name, and a colour function or ``attr()`` read whole, since one such as ``color-mix()`` or ``rgb(from …)`` writes
    a colour its arguments do not hold, and ``attr()`` one the page holds elsewhere; and those in any other
    function's arguments, such as a gradient's, or ``light-dark()``'s, which writes one of its two."""
    found = []
    for token in tokens:
        if token.type == "ident" and token.lower_value in _NO_COLOUR:
            continue
        if token.type == "function" and (token.lower_name == "light-dark" or token.lower_name not in _COLOUR_FUNCTIONS | {"attr"}):
            found += _colour_tokens(token.arguments)
        elif token.type == "function" or parse_color(token) is not None:
            found.append(token)  # a colour function, attr(), which reads a colour the page holds elsewhere, or a name
        elif token.type == "ident" and token.lower_value in _BROWSER_COLOURS:
            found.append(token)
    return found


def _sets_colour(value: list[Node], outlook: bool = False, inside: bool = False) -> bool:
    """Whether a declaration's value is one a browser takes as a colour: a hex of a length it reads, a name, a
    keyword, a colour function, or ``light-dark()`` of two such, neither a CSS-wide keyword, which a value takes only
    whole. A browser drops any other, a misspelt name or a hex one digit short, and a link then keeps its blue
    (measured in Chromium 141). In classic Outlook's view no ``light-dark()`` sets one: its Word engine predates it
    (inferred)."""
    words = [token for token in value if token.type not in ("whitespace", "comment")]
    if len(words) != 1:
        return False
    word = words[0]
    if word.type == "function" and word.lower_name == "light-dark":
        parts: list[list[Node]] = [[]]
        for token in word.arguments:
            if token.type == "literal" and token.value == ",":
                parts.append([])
            else:
                parts[-1].append(token)
        return not outlook and len(parts) == 2 and all(_sets_colour(part, inside=True) for part in parts)
    if word.type == "function":
        return word.lower_name in _COLOUR_FUNCTIONS
    if word.type == "ident" and word.lower_value in _CSS_WIDE:
        return not inside
    if word.type == "ident" and word.lower_value in _BROWSER_COLOURS:
        return True
    return word.type in ("hash", "ident") and parse_color(word) is not None


def colour_problems(page: str) -> list[str]:
    """Each colour a page writes or leaves to the browser that no design token holds, in the page's own view and in
    classic Outlook's: in an attribute or a style, a browser's own colour by name or as ``color``'s keyword, and a
    link that sets no colour a browser takes (in Outlook's view, none by ``light-dark()``)."""
    tokens, problems = token_colours(), set()
    for outlook, view in ((False, page), (True, outlook_view(page))):
        for element in tinyhtml5.parse(view, namespace_html_elements=False).iter():
            if not isinstance(element.tag, str):
                continue
            named = f"<{_local(element.tag)}>"
            for name, value in element.attrib.items():
                value = value.strip(_SPACE)
                if name.lower() in _COLOUR_ATTRIBUTES and value and value.lower() != "transparent" and value.upper() not in tokens:
                    problems.add(f"{named}'s {name} is {value!r}, no design token's colour (DESIGN.md): write a token's, as six-digit hex")
            declarations = [
                item
                for item in tinycss2.parse_declaration_list(element.get("style") or "", skip_comments=True, skip_whitespace=True)
                if item.type == "declaration"
            ]
            if named == "<a>" and element.get("href") is not None and not any(
                item.lower_name == "color" and _sets_colour(item.value, outlook) for item in declarations
            ):
                problems.add(
                    "<a> sets no colour of its own that a browser takes, so a client paints it the browser's link blue "
                    "(#0000EE), no design token's colour (DESIGN.md): set its color to a token's, as six-digit hex"
                )
            for item in declarations:
                if _VENDOR.sub("", item.lower_name, count=1) in _NAMING:
                    continue
                words = [token for token in item.value if token.type != "whitespace"]
                if item.lower_name == "color" and len(words) == 1 and words[0].type == "ident" and words[0].lower_value in _BROWSER_DEFAULTS:
                    problems.add(
                        f"{named}'s color is {words[0].lower_value}, the browser's own colour (black, or a link's blue), no design "
                        "token's colour (DESIGN.md): write a token's, as six-digit hex"
                    )
                for token in _colour_tokens(item.value):
                    if not (token.type == "hash" and f"#{token.value}".upper() in tokens):
                        problems.add(
                            f"{named}'s {item.lower_name} is {token.serialize()}, no design token's colour (DESIGN.md): write a "
                            "token's, as six-digit hex"
                        )
    return sorted(problems)


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
    wide. A ``<style>`` block or a linked stylesheet in that view is refused, as the page's own view refuses
    one."""
    root = tinyhtml5.parse(outlook_view(page), namespace_html_elements=False)
    parents = {child: parent for parent in root.iter() for child in parent}
    problems = []
    if any(isinstance(element.tag, str) and _is_stylesheet(element) for element in root.iter()):
        problems.append(  # one a conditional comment holds is Outlook's alone, which the page's own view never reads
            "in classic Outlook's view the page carries a <style> block or a linked stylesheet, whose selectors this check "
            "does not read: set the style inline"
        )
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


# --------------------------------------------------------------------------- text a page holds and does not show

# What rspamd's HIDDEN_TEXT does not count (rules/html.lua, 4.2): ASCII whitespace, the Unicode separators (Zs, Zl
# and Zp) and the invisible characters that pad an inbox preview. It counts the other controls, U+0085 and U+001C to
# U+001F among them (measured with rspamd 4.2.2). A hidden run with nothing else in it, a hairline cell's no-break
# space or a preheader's fill, hides nothing a reader or a filter counts.
_UNCOUNTED = re.compile(
    "[\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\u00ad\u034f\u200b-\u200d\u2060\ufeff]"
)
# Under 4 px no text reads: rspamd keeps a box's font size in whole px and hides one of 3 or less (html_block.hxx),
# so 3.9px hides, and the reader holds a browser's size to the same floor; a box that clips its overflow under it
# shows no line.
_LEGIBLE_PX = 4.0
# rspamd's floors: an opacity under 0.1 hides a box and all it holds (css_rule.cxx), and a colour shows at an alpha
# of 10 in 255 or more and at a weighted distance of 0.1 or more from the ground behind it (html_block.hxx). A
# browser's opacities multiply down the tree, and a colour's alpha with them: the reader holds the opacity a text's ink
# is painted at, a colour's alpha alone among them, to the same floor of 0.1, under which a text is a ghost of itself
# (dark ink at 0.05 lies 11 in 255 off a light ground, a distance of 0.13, whether a box or its colour sets the 0.05:
# stricter than rspamd's 10 in 255 for a colour), and paints a text's colour over its ground at it before it measures
# the distance.
_OPAQUE = 0.1
_SHOWN_ALPHA = 10 / 255
_DISTINCT = 0.1
_FONT_KEYWORDS = {
    "xx-small": 9.0, "x-small": 10.0, "small": 13.0, "medium": 16.0, "large": 18.0, "x-large": 24.0, "xx-large": 32.0,
    "xxx-large": 48.0,
}
_FONT_SIZE_ATTRIBUTE = {"1": 10.0, "2": 13.0, "3": 16.0, "4": 18.0, "5": 24.0, "6": 32.0, "7": 48.0}  # <font size>
# The sizes a browser's own sheet gives the elements it sizes, as factors of the parent's (an <rt>'s half only in a
# <ruby>, ``_ua_font_px``), and a form control's 13.333 px whatever its parent's (measured in Chromium); rspamd reads
# none of them, so its size stays the parent's.
_UA_FONT_FACTORS = {
    "small": 1 / 1.2, "sub": 1 / 1.2, "sup": 1 / 1.2, "big": 1.2, "h1": 2.0, "h2": 1.5, "h3": 1.17, "h5": 0.83,
    "h6": 0.67,
}
_CONTROLS = frozenset({"button", "input", "select", "textarea"})
# A number as CSS writes one, in ASCII digits (a browser drops 16.px, and a number in any other digits), and a
# dimension in it.
_CSS_NUMBER = r"[+-]?(?:[0-9]*\.[0-9]+|[0-9]+)"
_DIMENSION = re.compile(rf"({_CSS_NUMBER})([a-z]*|%)")
# A length in px. In a browser, an absolute unit at its rate, em against the box's font size and rem against the root
# element's (the html element's, 16 px where it sets none); ex and ch hang on the face's own letters and the viewport
# units on the screen, which the reader does not know. As rspamd reads it, each unit at a fixed rate, em and rem at
# 16 px, ex at 8 and the viewport units at a fixed screen's (css_tokeniser.cxx).
_ABSOLUTE_PX = {"px": 1.0, "pt": 4 / 3, "pc": 16.0, "in": 96.0, "cm": 96 / 2.54, "mm": 96 / 25.4, "q": 96 / 101.6}
_LENGTH_UNITS = frozenset({*_ABSOLUTE_PX, "em", "rem", "ex", "ch", "vw", "vh", "vmin", "vmax"})
_RSPAMD_PX = {
    "px": 1.0, "em": 16.0, "rem": 16.0, "ex": 8.0, "vw": 8.0, "vh": 6.0, "vmax": 8.0, "vmin": 6.0, "pt": 4 / 3,
    "pc": 16.0, "in": 96.0, "cm": 96 / 2.54, "mm": 96 / 25.4,
}
# The words a font shorthand takes before its size, each kind once and normal for any (CSS Fonts 4, as Chromium 141
# parses it, measured with CSS.supports): a style, a variant, a weight as a keyword or a number from 1 to 1000, and a
# stretch; and the generic families CSS Fonts 4 names, and Chromium's -webkit-body, after which the reader takes no
# word of a family's name: Chromium 141 drops a name that goes on after eight of them, and takes one after emoji,
# fangsong and the ui- families, which the reader refuses (fail closed).
_FONT_STYLES = frozenset({"italic", "oblique"})
_FONT_WEIGHTS = frozenset({"bold", "bolder", "lighter"})
_FONT_STRETCHES = frozenset({
    "ultra-condensed", "extra-condensed", "condensed", "semi-condensed", "semi-expanded", "expanded", "extra-expanded",
    "ultra-expanded",
})
_GENERIC_FAMILIES = frozenset({
    "serif", "sans-serif", "cursive", "fantasy", "monospace", "system-ui", "emoji", "math", "fangsong", "ui-serif",
    "ui-sans-serif", "ui-monospace", "ui-rounded", "-webkit-body",
})
_COLUMN_DISPLAYS = ("table-column", "table-column-group")
_INERT = frozenset({"initial", "unset", "revert", "revert-layer"})
_MARGINS = frozenset({
    "margin", "margin-top", "margin-right", "margin-bottom", "margin-left", "margin-block", "margin-block-start",
    "margin-block-end", "margin-inline", "margin-inline-start", "margin-inline-end",
})
# A box's size, its max and its min on each axis, the logical names beside the physical ones; the words that set no
# length it clips at (``inherit`` takes the parent's, which the reader does not resolve); and the elements whose width
# or height attribute HTML maps to a size.
_AXIS_SIZES = {
    "x": (("width", "inline-size"), ("max-width", "max-inline-size"), ("min-width", "min-inline-size")),
    "y": (("height", "block-size"), ("max-height", "max-block-size"), ("min-height", "min-block-size")),
}
_SIZE_WORDS = frozenset({"auto", "none", "fit-content", "min-content", "max-content", "stretch", "-webkit-fill-available", *_INERT})
_SIZE_HINTED = {"x": frozenset({"table", "td", "th", "col", "colgroup"}), "y": frozenset({"table", "tr", "td", "th"})}
# The properties the hidden-text reader reads, each with the values it takes where it takes only some (None: every
# value its reading resolves, the others refused there). A page that sets any other property is refused, and so is one
# of these at a value it does not take, so no property the reader has not been taught hides a text unseen (fail
# closed): a property is taught here, with the reason it hides no text, or a model of how it does.
_SIDE_NAMES = ("", "-top", "-right", "-bottom", "-left", "-block", "-block-start", "-block-end", "-inline", "-inline-start", "-inline-end")
_READS: dict[str, frozenset[str] | None] = {
    # What hides or shows a text, which the walk models (``_seen_below``, ``_ground``, ``_clipped_to``): a margin as
    # plain lengths alone, ``background`` as a colour alone and ``text-decoration`` with no thickness, which can lay its
    # line over the text.
    **dict.fromkeys((
        "display", "visibility", "opacity", "color", "background-color", "background", "font", "font-size", "overflow",
        "overflow-x", "overflow-y", "letter-spacing", "word-spacing", "text-decoration", "mso-hide",
        *(name for sizes in _AXIS_SIZES.values() for pair in sizes for name in pair), *_MARGINS,
    )),
    # A box's content shown, or skipped (hidden); auto contains the box's paint, which clips its content to the box as
    # overflow:clip does (measured in Chromium 141), and is refused.
    "content-visibility": frozenset({"visible", "hidden", *_INERT}),
    # Those that move, clip, scale, mask, filter, cover or repaint a text at any value but these, and a colour scheme,
    # under which a browser paints its own colours, at any but the light one.
    **{name: frozenset({*values, *_INERT}) for name, values in (
        ("position", {"static"}), ("transform", {"none"}), ("translate", {"none"}), ("rotate", {"none"}), ("scale", {"none"}),
        ("zoom", {"normal", "1", "100%", "reset"}), ("clip", {"auto"}), ("clip-path", {"none"}), ("mask", {"none"}),
        ("mask-image", {"none"}), ("-webkit-mask", {"none"}), ("-webkit-mask-image", {"none"}), ("filter", {"none"}),
        ("mix-blend-mode", {"normal"}), ("contain", {"none"}), ("line-clamp", {"none"}), ("-webkit-line-clamp", {"none"}),
        ("-webkit-text-fill-color", {"currentcolor", "inherit"}), ("background-image", {"none"}), ("text-indent", {"0", "0px"}),
        ("outline", {"none", "0", "0px"}), ("outline-style", {"none"}), ("box-shadow", {"none"}), ("text-shadow", {"none"}),
        ("overflow-clip-margin", {"0", "0px"}), ("text-decoration-thickness", {"auto", "from-font"}),
        ("text-underline-offset", {"auto"}), ("color-scheme", {"normal", "light", "only light", "light only"}),
    )},
    # Those that clip, mask or repaint no text at any value, and move one only along the page, where its reader scrolls
    # to it: a font's face, weight, style and figures, a line's height (lines it sets too low overlap, and each paints)
    # and its vertical alignment, a text's alignment, wraps and breaks, a decoration's line, style and colour, a box's
    # padding, borders and corners (the width rules hold a box to the screen's width), its sizing and its float, beside
    # which the lines wrap, a table's layout, and the text size a phone's view sets, which the text-size rule holds. A
    # box set too low to hold its text, a float among them, leaves the text where a box placed after it can paint over
    # it, which the reader does not read (``hidden_text_problems``).
    **dict.fromkeys((
        "font-family", "font-weight", "font-style", "font-variant", "font-variant-numeric", "font-feature-settings",
        "text-transform", "-webkit-font-smoothing", "-moz-osx-font-smoothing", "line-height", "text-align", "vertical-align",
        "white-space", "white-space-collapse", "text-wrap", "text-wrap-mode", "text-wrap-style", "overflow-wrap",
        "word-wrap", "word-break", "line-break", "-webkit-line-break", "hyphens", "text-decoration-line",
        "text-decoration-style", "text-decoration-color", *(f"padding{side}" for side in _SIDE_NAMES),
        *(f"border{side}{part}" for side in _SIDE_NAMES for part in ("", "-width", "-style", "-color")),
        *(f"border{corner}-radius" for corner in (
            "", "-top-left", "-top-right", "-bottom-left", "-bottom-right", "-start-start", "-start-end", "-end-start", "-end-end",
        )),
        "box-sizing", "float", "clear", "border-collapse", "border-spacing", "table-layout", "text-size-adjust",
        "-webkit-text-size-adjust", "-ms-text-size-adjust",
    )),
}
_UNRESOLVED = re.compile(r"\b(?:var|env|attr)\(")
# The elements whose text a browser lays out as text, as the walk reads it. Text in any other element, and in what it
# holds, is refused: a media or embedded element's fallback, a form control's (a closed select's other options, a
# field's scrolled text), a meter's or a progress bar's, which a browser never shows, a marquee's, scrolled through its
# box, an SVG's, a formula's (a MathML annotation's is never shown), a noscript's, and that of an element the reader
# does not know (a fencedframe's is never shown).
_TEXT_ELEMENTS = frozenset({
    "html", "body", "a", "abbr", "address", "article", "aside", "b", "bdi", "bdo", "big", "blockquote", "button", "caption",
    "center", "cite", "code", "data", "dd", "del", "details", "dfn", "dir", "div", "dl", "dt", "em", "fieldset",
    "figcaption", "figure", "font", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hgroup", "i", "ins",
    "kbd", "label", "legend", "li", "listing", "main", "mark", "menu", "nav", "nobr", "ol", "p", "plaintext", "pre", "q",
    "rb", "rt", "rtc", "ruby", "s", "samp", "search", "section", "small", "span", "strike", "strong", "sub", "summary",
    "sup", "table", "tbody", "td", "tfoot", "th", "thead", "time", "tr", "tt", "u", "ul", "var", "xmp",
})
# The overflow values that clip a box's content to its size, and those that leave it whole.
_CLIPPING = frozenset({"hidden", "clip", "auto", "scroll", "overlay"})
_WHOLE = frozenset({"visible", *_INERT})
# The elements HTML maps a bgcolor and a background attribute onto, as hints to the style (rspamd reads a bgcolor on
# any element, over the style).
_BGCOLOR_HINTED = frozenset({"body", "table", "thead", "tbody", "tfoot", "tr", "td", "th"})
_BLOCKS = frozenset({
    "address", "article", "aside", "blockquote", "br", "caption", "dd", "div", "dl", "dt", "figcaption", "figure",
    "footer", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li", "main", "nav", "ol", "p", "pre", "section",
    "table", "tbody", "td", "tfoot", "th", "thead", "tr", "ul",
})
# rspamd 4.2.2's reading of a style attribute (css_parser.cxx's parse_css_declaration, css_tokeniser.cxx, css_rule.cxx,
# css_value.cxx, css_property.cxx; ``_rspamd_style``), which shares no step with a browser's: it lowercases the
# attribute's bytes, ASCII alone, reads them as one run of tokens, groups the tokens into component values, and reads
# its declarations off those by a state machine of its own. A number is the longest run of a sign, digits with one dot
# and an exponent that a digit or a sign follows, read as strtod reads its longest prefix and held as a C float (so
# 16.px is 16, 2.5.px a unitless 2.5 and 5e-2 0.05), then a percent sign, a unit it scales to px (``_RSPAMD_PX``), or
# a name it does not take as a unit, which leaves the number unscaled and is read on as a name; a number past a float's
# range is a delimiter. A name runs on through letters, digits, "-", "_" and any byte past ASCII, and a hash is "#" and
# two or more of those. The properties it knows, under the names it reads them by (bgcolor, which no browser knows, is
# background-color), and the kinds of value each takes (css_property.hxx); the colour functions it reads, each with
# its count of arguments; the bytes it reads as space; the tokens it reads, counting each it reads again, before it
# reads the rest as the end; and how deep it nests before it stops.
_RSPAMD_PROPERTIES = {
    "font": "font", "font-color": "font-color", "font-size": "font-size", "color": "color", "bgcolor": "background-color",
    "background-color": "background-color", "background": "background", "height": "height", "width": "width",
    "max-height": "max-height", "max-width": "max-width", "display": "display", "visibility": "visibility",
    "opacity": "opacity", "overflow": "overflow", "position": "position", "left": "left", "top": "top",
    "text-indent": "text-indent", "clip": "clip", "clip-path": "clip-path",
}
_RSPAMD_COLOURED = frozenset({"color", "font-color", "background-color", "background", "font"})
_RSPAMD_SIZED = frozenset({"height", "width", "max-height", "max-width", "left", "top", "text-indent", "font-size", "font"})
_RSPAMD_FUNCTIONS = {"rgb": 3, "rgba": 4, "hsl": 3, "hsla": 4}
_RSPAMD_PREFIX = re.compile(r"[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_RSPAMD_FLOAT_MAX = 3.4028234663852886e38
_RSPAMD_SPACE = b" \t\n\f\r"  # GLib's g_ascii_isspace, which a vertical tab is not
_RSPAMD_MAX_TOKENS = 1 << 17
_RSPAMD_MAX_NESTING = 20
# The values rspamd reads as a display, on display and on visibility alike (css_value.cxx), and those that hide;
# visibility:visible is none of them.
_RSPAMD_DISPLAYS = frozenset({
    "hidden", "collapse", "none", "inline", "block", "content", "flex", "grid", "inline-block", "inline-flex",
    "inline-grid", "inline-table", "list-item", "run-in", "table", "table-caption", "table-column-group",
    "table-header-group", "table-footer-group", "table-row-group", "table-cell", "table-column", "table-row", "initial",
})
_RSPAMD_HIDING = frozenset({"hidden", "collapse", "none"})
# The table and its parts, to which rspamd hands no height or width from the box above, since their content sizes
# them (html.cxx's html_tag_bounded_by_parent); and how far left or up a box goes, or its text indents, before rspamd
# reads it as off the page.
_RSPAMD_UNBOUNDED = frozenset({"table", "caption", "col", "colgroup", "thead", "tbody", "tfoot", "tr", "td", "th"})
_RSPAMD_OFF_PAGE = -1000.0
# The colours rspamd names (css_colors_list.hxx, X11's list): CSS's names, each at CSS's value but these five, at X11's;
# and names CSS does not know, at values the reader does not hold, which it refuses: a CSS name, lightgoldenrod or
# violetred with a digit from 1 to 4 after it, gray and grey with a number from 0 to 100, and these.
_RSPAMD_X11 = {
    "gray": (190, 190, 190), "grey": (190, 190, 190), "green": (0, 255, 0), "maroon": (176, 48, 96),
    "purple": (160, 32, 240),
}
_RSPAMD_ONLY_COLOURS = frozenset({
    "lightgoldenrod", "lightslateblue", "navyblue", "violetred", "webgray", "webgreen", "webgrey", "webmaroon",
    "webpurple", "x11gray", "x11green", "x11grey", "x11maroon", "x11purple", "activeborder", "activecaption",
    "appworkspace", "background", "buttonhighlight", "buttonshadow", "captiontext", "inactiveborder", "inactivecaption",
    "inactivecaptiontext", "infobackground", "infotext", "menu", "menutext", "scrollbar", "threeddarkshadow",
    "threedface", "threedhighlight", "threedlightshadow", "threedshadow", "window", "windowframe", "windowtext",
})
# What the port of rspamd's reading does not follow: a backslash, an escape rspamd unescapes on terms of its own
# (css_util.cxx), and U+FFFD, which the page's parser writes for a NUL that rspamd may read otherwise; and the table
# that lowercases ASCII alone.
_UNPORTED = re.compile(r"[\\\ufffd]")
# A start tag as a page's source writes it, read from each "<" and a letter (a tag a quoted value or a comment holds
# among them, as rspamd reads one inside a comment Outlook opens), and each of its attributes as a browser's tokenizer
# reads one: a "/" before a name read as a space, a name, which a first "=" begins where it stands alone, and after an
# "=" a value, quoted or unquoted. A name and an unquoted value end where both parsers end them, at a tab, a newline,
# a form feed, a carriage return or a space: Python's \s takes a vertical tab, a no-break space and more, inside an
# unquoted value for both, before an ampersand it would hide.
_HTML_SPACE = r"\t\n\f\r "
_START_TAG = re.compile(rf"<[A-Za-z][^{_HTML_SPACE}/>]*")
_ATTRIBUTE = re.compile(
    rf"""[{_HTML_SPACE}/]*(=?[^{_HTML_SPACE}/>=]*)(?:[{_HTML_SPACE}]*=[{_HTML_SPACE}]*("[^"]*"|'[^']*'|[^{_HTML_SPACE}>]*))?"""
)
# The attributes rspamd reads a box's look off (html.cxx, which decodes every attribute's value), and the character
# references in a value that rspamd's HTML parser and a browser's decode alike, a name HTML defines or a code point it
# neither maps nor replaces, each closed with ";" (rspamd decodes any other by heuristics of its own,
# html_entities.cxx).
_READ_ATTRIBUTES = frozenset({"style", "color", "bgcolor"})
_REFERENCE = re.compile(r"&(?:#([0-9]+);|#[xX]([0-9a-fA-F]+);|([A-Za-z][A-Za-z0-9]*;))?")


def _referenced_attributes(page: str) -> Iterator[tuple[str, str]]:
    """Each attribute of each tag a page's source writes (``_START_TAG``, ``_ATTRIBUTE``) that rspamd reads a box's look
    off (``_READ_ATTRIBUTES``, its name in any case), whose value as written holds an ampersand: its name, lowercased,
    and that value."""
    for tag in _START_TAG.finditer(page):
        position = tag.end()
        while (attribute := _ATTRIBUTE.match(page, position)).group(1):
            name, value = attribute.group(1).translate(_ASCII_LOWER), attribute.group(2) or ""
            if name in _READ_ATTRIBUTES and "&" in value:
                yield name, value
            position = attribute.end()


def _decoded_alike(written: str) -> bool:
    """Whether each character reference an attribute's value holds, as the page's source writes it, is one rspamd's HTML
    parser decodes as a browser's does (``_REFERENCE``)."""
    for match in _REFERENCE.finditer(written):
        decimal, hexadecimal, name = match.groups()
        if name is not None:
            if name not in html5:
                return False
        elif decimal is None and hexadecimal is None:
            return False
        elif not (0 < (code := int(decimal or hexadecimal, 10 if decimal else 16)) < 0x80 or 0xA0 <= code < 0xD800 or 0xE000 <= code <= 0x10FFFF):
            return False
    return True
_ASCII_LOWER = {code: code + 32 for code in range(0x41, 0x5B)}
_BLACK, _WHITE, _LINK_BLUE = (0.0, 0.0, 0.0, 1.0), (1.0, 1.0, 1.0, 1.0), (0.0, 0.0, 238 / 255, 1.0)
_BLOCK_EDGE = "\x1e"  # marks a block's edge among a page's texts; a page's own text holds no record separator


class _Unread(ValueError):
    """A value the reader does not resolve on a property it reads: ``var()``, ``calc()``, ``min()``, an exponent, a
    viewport unit, a gradient. The walk refuses the declaration rather than guess what it paints."""


def _all_declared(style: str | None) -> list[tuple[str, bool, str]]:
    """Every declaration a style attribute makes, in order (name, important, value), comments dropped and names
    and values lowercased, ASCII alone, as CSS matches a keyword (a Kelvin sign stays one, never a "k"). ``_declarations``
    reads only the properties the other rules read."""
    return [
        (item.lower_name, item.important, tinycss2.serialize(item.value).strip().translate(_ASCII_LOWER))
        for item in tinycss2.parse_blocks_contents(style or "", skip_comments=True, skip_whitespace=True)
        if item.type == "declaration"
    ]


def _winner(declared: list[tuple[str, bool, str]], *names: str) -> tuple[str, str] | None:
    """The declaration that wins among those of ``names``, which set one property, as (name, value): an important
    declaration over a normal one, and among equals the last, so a shorthand and its longhand read in order."""
    won = None
    for name, important, value in declared:
        if name in names and (won is None or important or not won[0]):
            won = (important, name, value)
    return (won[1], won[2]) if won else None


def _rgba(value: str | None) -> tuple[float, float, float, float] | None:
    """A colour as a browser reads it, as sRGB and alpha, each from 0 to 1, or None for a value that is no colour
    (``currentcolor``, a CSS-wide keyword, ``var()``, ``light-dark()``, ``color-mix()``)."""
    colour = parse_color(value) if value else None
    if colour is None or isinstance(colour, str):
        return None
    try:
        srgb = colour.to("srgb")
        red, green, blue = (min(1.0, max(0.0, channel)) for channel in srgb.coordinates)
    except (NotImplementedError, ArithmeticError, ValueError):
        return None  # a colour space tinycss2 does not convert (lab(), oklch(), display-p3), which the walk refuses
    return (red, green, blue, float(srgb.alpha))


def _f32(number: float) -> float:
    """A number as a C float holds it, rounded to 32 bits, or an infinity past the float's range."""
    try:
        return struct.unpack("<f", struct.pack("<f", number))[0]
    except OverflowError:
        return math.copysign(math.inf, number)


def _c_int(number: float) -> int:
    """A number cut to a C int as x86 cuts one, the least int for one past an int's range (an infinity among them)."""
    return int(number) if -2**31 <= number < 2**31 else -2**31


@dataclass(frozen=True)
class _RspamdToken:
    """A token rspamd reads off a style (css_tokeniser.cxx): its kind ("ident", "function", "url", "at", "hash",
    "number", "string", "delim", "space", "cdo", "cdc", "end", or one of ``()[]{},;:``); its value, a name or a hash's
    digits (its bytes, a character each), a delimiter's character or a number, in px under a unit rspamd knows; a
    number's unit ("" for none, "%", the unit it knows, or "?" for a name it does not take as one, the number then left
    unscaled); and the bytes it spans."""

    kind: str
    value: object = None
    unit: str = ""
    start: int = 0
    end: int = 0


def _rspamd_starts_name(byte: int) -> bool:
    """Whether rspamd starts a name with a byte: a letter, "_" or a byte past ASCII."""
    return byte >= 0x80 or byte == 0x5F or chr(byte).isalpha()


def _rspamd_in_name(byte: int) -> bool:
    """Whether rspamd reads a byte on in a name: one that starts one, a digit or "-"."""
    return _rspamd_starts_name(byte) or byte == 0x2D or 0x30 <= byte <= 0x39


def _rspamd_name(data: bytes, offset: int, digits: bool = False) -> _RspamdToken:
    """The name rspamd reads at ``offset`` (css_tokeniser.cxx's consume_ident): one or two "-", a byte that starts a
    name (any a name holds, after a hash: ``digits``), then any it holds. Where "(" follows, a function's name, which
    leaves the "(" to read, or a url() whole, to its ")" or the end, where no quote opens it. A backslash ends a name:
    the walk refuses a style that holds one, which rspamd unescapes on terms of its own."""
    i, size, inside = offset, len(data), digits
    if data[i] == 0x2D:
        i += 1
        if i < size and data[i] == 0x2D:
            i, inside = i + 1, True
    while i < size and (_rspamd_in_name(data[i]) if inside else _rspamd_starts_name(data[i])):
        i, inside = i + 1, True
    if i < size and data[i] == 0x28:
        after = i + 1
        while after < size and data[after] in _RSPAMD_SPACE:
            after += 1
        if size - offset > 3 and data.startswith(b"url", offset) and not (after < size and data[after] in b"\"'"):
            close = data.find(b")", after)
            return _RspamdToken("url", start=offset, end=size if close < 0 else close + 1)
        return _RspamdToken("function", data[offset:i].decode("latin-1"), start=offset, end=i)
    return _RspamdToken("ident", data[offset:i].decode("latin-1"), start=offset, end=i)


def _rspamd_number(data: bytes, offset: int) -> _RspamdToken:
    """The number rspamd reads at ``offset`` (css_tokeniser.cxx's consume_number): a sign, digits with one dot, and an
    "e" that a digit or a sign follows with digits after it, a dot after the "e" ending it; read as strtod reads the
    longest number its first 127 bytes start with, held as a C float, a delimiter where that is past a float's range.
    Then a "%", or a name: a unit it knows scales the number to px, and a name it does not leaves the number unscaled
    and is read again on its own; a function's name or a url() there is read and lost."""
    i, size, dot, exponent = offset, len(data), False, False
    if data[i] in b"+-":
        i += 1
    if i < size and data[i] == 0x2E:
        i, dot = i + 1, True
    while i < size:
        byte = data[i]
        if byte == 0x2E and not dot:
            dot = True
        elif byte in b"eE" and not exponent:
            if i + 1 < size and data[i + 1] in b"+-":
                i += 1
            elif not (i + 1 < size and 0x30 <= data[i + 1] <= 0x39):
                break
            dot = exponent = True
        elif not 0x30 <= byte <= 0x39:
            break
        i += 1
    prefix = _RSPAMD_PREFIX.match(data[offset:i][:127].decode("ascii"))
    number = float(prefix.group()) if prefix else 0.0
    if abs(number) >= _RSPAMD_FLOAT_MAX:
        return _RspamdToken("delim", chr(data[i - 1]), start=offset, end=i)
    value = _f32(number)
    if i < size and data[i] == 0x25:
        return _RspamdToken("number", value, "%", offset, i + 1)
    if i < size and _rspamd_starts_name(data[i]):
        unit = _rspamd_name(data, i)
        if unit.kind != "ident":
            return _RspamdToken("number", value, "", offset, unit.end)
        if unit.value in _RSPAMD_PX:
            return _RspamdToken("number", _f32(value * _RSPAMD_PX[unit.value]), unit.value, offset, unit.end)
        return _RspamdToken("number", value, "?", offset, i)
    return _RspamdToken("number", value, "", offset, i)


def _rspamd_comment_end(data: bytes, i: int) -> int:
    """Where rspamd reads on after a comment whose "/*" ends at ``i`` (css_tokeniser.cxx's consume_comment): after its
    "*/", the comments nested in it counted, or at the last byte where it is left open."""
    nested = 0
    while i < len(data) - 1:
        if data[i] == 0x2A and data[i + 1] == 0x2F:
            if nested == 0:
                return i + 2
            nested, i = nested - 1, i + 2
        elif data[i] == 0x2F and data[i + 1] == 0x2A:
            nested, i = nested + 1, i + 2
        else:
            i += 1
    return i


def _rspamd_lex(data: bytes) -> list[_RspamdToken]:
    """The tokens rspamd reads off a style's bytes (css_tokeniser.cxx's next_token), in order. A comment sets none; a
    quote reads a string to the same quote or the end; "<!--" reads as one token, and its last "-" is read again; a
    sign or a dot before a digit starts a number, as a digit does (``_rspamd_number``), and a byte that starts a name
    starts a name (``_rspamd_name``); "#" reads a hash and "@" an at-keyword where two and three bytes a name holds
    follow; any other byte is a delimiter of its own, "-" and "\\" among them."""
    tokens: list[_RspamdToken] = []
    i, size = 0, len(data)
    while i < size:
        byte, after = data[i], data[i + 1] if i + 1 < size else -1
        if byte == 0x2F and after == 0x2A:
            i = _rspamd_comment_end(data, i + 2)
            continue
        if byte in _RSPAMD_SPACE:
            end = i
            while end < size and data[end] in _RSPAMD_SPACE:
                end += 1
            token = _RspamdToken("space", start=i, end=end)
        elif byte in b"\"'" and after >= 0:
            close = data.find(data[i:i + 1], i + 1)
            token = _RspamdToken("string", start=i, end=size if close < 0 else close + 1)
        elif byte in b"()[]{},;:":
            token = _RspamdToken(chr(byte), start=i, end=i + 1)
        elif byte == 0x3C and data.startswith(b"!--", i + 1):
            token = _RspamdToken("cdo", start=i, end=i + 3)
        elif byte == 0x2D and data.startswith(b"->", i + 1):
            token = _RspamdToken("cdc", start=i, end=i + 3)
        elif 0x30 <= byte <= 0x39 or (byte in b"+-." and 0x30 <= after <= 0x39):
            token = _rspamd_number(data, i)
        elif byte == 0x40 and i + 3 < size and _rspamd_starts_name(data[i + 1]) and all(map(_rspamd_in_name, data[i + 2:i + 4])):
            token = _rspamd_name(data, i + 1)
            token = replace(token, kind="at") if token.kind == "ident" else token
        elif byte == 0x23 and i + 2 < size and all(map(_rspamd_in_name, data[i + 1:i + 3])):
            token = _rspamd_name(data, i + 1, digits=True)
            token = replace(token, kind="hash") if token.kind == "ident" else token
        elif _rspamd_starts_name(byte):
            token = _rspamd_name(data, i)
        else:
            token = _RspamdToken("delim", chr(byte), start=i, end=i + 1)
        tokens.append(token)
        i = token.end
    return tokens


def _rspamd_blocks(tokens: list[_RspamdToken]) -> list[tuple]:
    """The component values rspamd groups a style's tokens into at its top level (css_parser.cxx's consume_css_rule),
    spaces aside: ``("token", token)``; ``("function", token, arguments)``, whose arguments end at its first ")", each
    token but a space, a comma, a delimiter and a "(" one, a ";", a bracket and a function's name among them; and
    ``("block",)`` for a run in brackets, to its own closing bracket or the end, holding component values of its own.
    It reads 1 << 17 tokens at most, counting each it reads again, then reads the end; where it nests past 20 levels
    it stops, keeping what it read before."""
    position, backlog, count, level, done = 0, [], 0, 0, False

    def read() -> _RspamdToken:
        nonlocal position, count
        count += 1
        if count > _RSPAMD_MAX_TOKENS:
            return _RspamdToken("end")
        if backlog:
            return backlog.pop()
        position += 1
        return tokens[position - 1] if position <= len(tokens) else _RspamdToken("end")

    def component(into: list) -> bool:
        nonlocal level, done
        level += 1
        if level > _RSPAMD_MAX_NESTING:
            return False
        held, block = True, None
        while held and block is None and not done:
            token = read()
            if token.kind == "end":
                done = True
            elif token.kind in ("(", "[", "{"):
                block = ("block",)
                held = bracketed({"(": ")", "[": "]", "{": "}"}[token.kind])
            elif token.kind == "function":
                block = ("function", token, [])
                held = arguments(block[2])
            elif token.kind != "space":
                block = ("token", token)
        if held and block is not None:
            into.append(block)
        level -= 1
        return held

    def bracketed(closer: str) -> bool:
        nonlocal done
        held, inside = True, []
        while held and not done:
            token = read()
            if token.kind == closer:
                break
            if token.kind == "end":
                done = True
            elif token.kind != "space":
                backlog.append(token)
                held = component(inside)
        return held

    def arguments(into: list) -> bool:
        nonlocal level, done
        level += 1
        if level > _RSPAMD_MAX_NESTING:
            return False
        while not done:
            token = read()
            if token.kind == "end":
                done = True
            elif token.kind == ")":
                break
            elif token.kind not in ("space", ",", "delim", "("):
                into.append(token)
        level -= 1
        return True

    blocks: list[tuple] = []
    held = True
    while held and not done:
        token = read()
        if token.kind == "end":
            done = True
        elif token.kind != "space":
            backlog.append(token)
            held = component(blocks)
    return blocks


def _rspamd_hex(digits: str) -> tuple[float, float, float, float] | None:
    """A colour off a hash's digits as rspamd reads one (css_value.cxx), each a byte: six as RGB, three each doubled,
    eight as RGBA, none for any other count; a byte that is no hex digit reads as 0."""
    if len(digits) not in (3, 6, 8):
        return None
    if len(digits) == 3:
        pairs = [digit * 2 for digit in digits]
    else:
        pairs = [digits[at:at + 2] for at in range(0, len(digits), 2)]
    channels = [
        sum(int(char, 16) * weight if char in "0123456789abcdefABCDEF" else 0 for char, weight in zip(pair, (16, 1)))
        for pair in pairs
    ]
    return (channels[0] / 255, channels[1] / 255, channels[2] / 255, channels[3] / 255 if len(channels) == 4 else 1.0)


def _rspamd_name_rgba(name: str) -> tuple[float, float, float, float] | None:
    """A colour off a name as rspamd reads one: a name CSS knows, at CSS's value but the five X11 gives its own
    (``_RSPAMD_X11``); None for any other name, a name only X11 knows among them (``_rspamd_only_colour``)."""
    if name in _RSPAMD_X11:
        red, green, blue = _RSPAMD_X11[name]
        return (red / 255, green / 255, blue / 255, 1.0)
    return _rgba(name) if re.fullmatch("[a-z]+", name) else None


def _rspamd_only_colour(name: str) -> bool:
    """Whether rspamd reads a name as a colour CSS does not know, off X11's list (css_colors_list.hxx), at a value the
    reader does not hold."""
    base = (variant := re.fullmatch("([a-z]+)[1-4]", name)) and variant.group(1)
    numbered = bool(base) and (base in ("lightgoldenrod", "violetred") or _rgba(base) is not None)
    return name in _RSPAMD_ONLY_COLOURS or re.fullmatch("gr[ae]y(?:100|[1-9]?[0-9])", name) is not None or numbered


def _rspamd_function_rgba(name: str, arguments: list[_RspamdToken]) -> tuple[float, float, float, float] | None:
    """A colour off a colour function as rspamd reads one (css_value.cxx): rgb() and hsl() of three arguments, rgba()
    and hsla() of four, each argument a token, so ``rgb(26 26 23 / 0.5)`` is none and a hue in a unit it does not know
    (``60deg``) counts two; a channel a number to 255 or a percentage of it, an alpha a fraction or a percentage, a hue
    in degrees, a saturation and a lightness a fraction or a percentage, each cut to a byte, and an argument that is no
    number 0 (an alpha 1). A grey hsl() (no saturation) sets each channel to its lightness cut to a byte: 0, or 1 at
    full lightness, black to the eye."""
    if len(arguments) != _RSPAMD_FUNCTIONS.get(name):
        return None

    def number(token: _RspamdToken, kind: str) -> float:
        if token.kind != "number":
            return 1.0 if kind == "alpha" else 0.0
        value, percent = token.value, token.unit == "%"
        if percent and kind != "fraction":
            value = min(100.0, max(0.0, value)) / 100
            return int(value * 255) if kind == "channel" else value
        if kind == "channel":
            return int(min(255.0, max(0.0, value)))
        if kind == "hue":
            return _c_int(value) % 360 / 360  # whole degrees, wrapped to a turn
        return min(1.0, max(0.0, _f32(value / 100) if percent else value))  # an alpha, a saturation or a lightness

    alpha = int(number(arguments[3], "alpha") * 255) / 255 if len(arguments) == 4 else 1.0
    if name.startswith("rgb"):
        red, green, blue = (number(argument, "channel") for argument in arguments[:3])
        return (red / 255, green / 255, blue / 255, alpha)
    hue = number(arguments[0], "hue")
    saturation, lightness = (number(token, "fraction") for token in arguments[1:3])
    if saturation == 0:
        return (int(lightness) / 255, int(lightness) / 255, int(lightness) / 255, alpha)
    q = lightness * (1 + saturation) if lightness <= 0.5 else lightness + saturation - lightness * saturation
    p = 2 * lightness - q

    def channel(t: float) -> int:
        t = t + 1 if t < 0 else t - 1 if t > 1 else t
        if t * 6 < 1:
            return int((p + (q - p) * 6 * t) * 255)
        if t * 2 < 1:
            return int(q * 255)
        return int((p + (q - p) * (2 / 3 - t) * 6) * 255) if t * 3 < 2 else int(p * 255)

    return (channel(hue + 1 / 3) / 255, channel(hue) / 255, channel(hue - 1 / 3) / 255, alpha)


def _rspamd_clips(name: str, arguments: list[_RspamdToken]) -> bool:
    """Whether rspamd reads a clip function as clipping a box to nothing (css_rule.cxx's clip_function_hides): rect()
    with a number and none past 1 either way, inset() whose first number is a percentage of 50 or more, and circle()
    or ellipse() whose first number is 0 or less."""
    numbers = [(token.value, token.unit == "%") for token in arguments if token.kind == "number"]
    if name == "rect":
        return bool(numbers) and all(abs(value) <= 1.0 for value, _percent in numbers)
    if name == "inset":
        return bool(numbers) and numbers[0][1] and numbers[0][0] >= 50.0
    return name in ("circle", "ellipse") and bool(numbers) and numbers[0][0] <= 0.0


def _rspamd_value(name: str, block: tuple) -> tuple[str, object] | None:
    """The value rspamd adds to a rule of ``name`` off one component value (css_rule.cxx's allowed_property_value), as
    (kind, read), or None. Where the property takes colours, a colour off a hash, a name or a colour function, a name
    only X11 knows read as None, at a value the reader does not hold, and any other hash, name or function read as
    nothing; where it takes sizes, a size, (number, whether a percentage), off a number in a unit it knows or none, the
    font shorthand taking a unitless number at 0 alone; for display and visibility, a name it reads as a display; for
    overflow, any name; and a number: an opacity off any number, scaled by a unit it knows and unscaled under one it
    does not, a percentage as a fraction (rspamd cuts it to 0 to 1, which moves none across 0.1, so the port does
    not); for position, 1 for absolute or fixed and 0 for another name;
    for clip and clip-path, 1 off a function that clips to nothing (``_rspamd_clips``), 0 off any other function or
    token."""
    token = block[1] if block[0] == "token" else None
    if name in _RSPAMD_COLOURED:
        if token is not None and token.kind == "hash":
            colour = _rspamd_hex(token.value)
            return None if colour is None else ("colour", colour)
        if token is not None and token.kind == "ident":
            if _rspamd_only_colour(token.value):
                return ("colour", None)
            colour = _rspamd_name_rgba(token.value)
            return None if colour is None else ("colour", colour)
        if block[0] == "function":
            colour = _rspamd_function_rgba(block[1].value, block[2])
            return None if colour is None else ("colour", colour)
    if token is None:
        if name in ("clip", "clip-path") and block[0] == "function":
            return ("number", 1.0 if _rspamd_clips(block[1].value, block[2]) else 0.0)
        return None
    if name in _RSPAMD_SIZED and token.kind == "number":
        if token.unit == "?" or (name == "font" and token.unit == "" and token.value != 0):
            return None
        return ("size", (token.value, token.unit == "%"))
    if name in ("display", "visibility") and token.kind == "ident":
        return ("display", token.value) if token.value in _RSPAMD_DISPLAYS else None
    if name == "opacity" and token.kind == "number":
        return ("number", _f32(token.value / 100) if token.unit == "%" else token.value)
    if name == "overflow" and token.kind == "ident":
        return ("display", token.value)
    if name == "position" and token.kind == "ident":
        return ("number", 1.0 if token.value in ("absolute", "fixed") else 0.0)
    if name in ("clip", "clip-path"):
        return ("number", 0.0)
    return None


def _rspamd_rules(style: str | None) -> tuple[dict[str, list[tuple[str, object, str]]], list[tuple[str, str]]]:
    """The rules rspamd keeps off a style attribute (css_parser.cxx's parse_css_declaration, css_rule.cxx's
    process_declaration_tokens and add_rule): for each property it knows, in the order it first holds one, the values
    its declarations add (``_rspamd_value``), each as (kind, read, the declaration's value as written); and each
    declaration, as (property, value), in which it reads a name only X11 knows as a colour. It reads a property's name,
    a ":", then component values to a ";" or the end, "important" read as nothing; where it looks for a name, a
    function is read as nothing, and a property it does not know, a ";" or any other token skips to the next ";", as a
    name with no ":" after it does; and a block in brackets at the top level ends its reading, the declaration it was in
    unread. A declaration that adds no value adds no rule; each value a later one adds stands in for every value of its
    kind its rule holds, and a kind new to the rule joins it at its end, importance aside (rspamd sets the flag on a
    copy of the property its rule no longer reads)."""
    data = (style or "").encode("utf-8", "surrogatepass").lower()
    blocks = _rspamd_blocks(_rspamd_lex(data)) + [("end",)]
    rules: dict[str, list[tuple[str, object, str]]] = {}
    unheld: list[tuple[str, str]] = []

    def add(end: int) -> None:
        written = re.sub(r"\s*!\s*important\s*$", "", data[start:end].decode("utf-8", "surrogatepass")).strip()
        added = [(kind, read, written) for kind, read in values]
        kept = rules.get(name, [])
        kinds = {kind for kind, _read, _written in kept}
        for kind, read, said in added:
            if kind in kinds:
                kept = [(held, read, said) if held == kind else (held, old, was) for held, old, was in kept]
        if added:
            rules[name] = kept + [value for value in added if value[0] not in kinds]
        if x11:
            unheld.append((named, written))

    state, named, name, values, start, x11, index = "name", "", "", [], 0, False, 0
    while True:
        block = blocks[min(index, len(blocks) - 1)]
        index += 1
        token = block[1] if block[0] == "token" else None
        if block[0] in ("end", "block"):
            if block[0] == "end" and state == "value":
                add(len(data))
            return rules, unheld
        if block[0] == "function":
            if state == "value" and (value := _rspamd_value(name, block)) is not None:
                values.append(value)
        elif state == "name":
            known = token.kind == "ident" and token.value in _RSPAMD_PROPERTIES
            colon = blocks[min(index, len(blocks) - 1)] if known else None
            index += known
            if colon is not None and colon[0] == "token" and colon[1].kind == ":":
                state, named, name, values, start, x11 = "value", token.value, _RSPAMD_PROPERTIES[token.value], [], colon[1].end, False
            else:
                state = "skip"
        elif state == "value" and token.kind == ";":
            add(token.start)
            state = "name"
        elif state == "value" and not (token.kind == "ident" and token.value == "important"):
            x11 = x11 or (name in _RSPAMD_COLOURED and token.kind == "ident" and _rspamd_only_colour(token.value))
            if (value := _rspamd_value(name, block)) is not None:
                values.append(value)
        elif state == "skip" and token.kind == ";":
            state = "name"


@dataclass(frozen=True)
class _RspamdStyle:
    """What rspamd reads off one element's style attribute (css_rule.cxx's compile_into), before the element's
    attributes and the boxes above it are read: the display it applies last, from display or visibility, as (property,
    name); the opacity it reads, and the value as written; why it reads the box as off the page (absolute or fixed
    with a left or a top of -1000 px or less, a text indent there, or a clip or a clip path that clips to nothing); its
    font size, height and width, each as (number, whether a percentage, as written), a height and a width the least of
    it and its max; the colour and the ground it sets, None where it sets none or one off a name only X11 knows; its
    overflow's name; and each declaration in which it reads a name only X11 knows as a colour, as (property, value)."""

    display: tuple[str, str] | None = None
    opacity: tuple[float, str] | None = None
    off_page: str | None = None
    font_size: tuple[float, bool, str] | None = None
    height: tuple[float, bool, str] | None = None
    width: tuple[float, bool, str] | None = None
    colour: tuple[float, float, float, float] | None = None
    ground: tuple[float, float, float, float] | None = None
    overflow: str | None = None
    unheld: tuple[tuple[str, str], ...] = ()


@cache
def _rspamd_style(style: str | None) -> _RspamdStyle:
    """What rspamd reads off a style attribute (``_RspamdStyle``), from the last value of each rule it keeps
    (``_rspamd_rules``), in the rules' order: the later of display and visibility, and of color and font-color, over the
    earlier; the font shorthand's last colour where no color or font-color is set, and its first size where no
    font-size is; the background shorthand's last colour where no background-color is set."""
    rules, unheld = _rspamd_rules(style)
    last = {name: values[-1] for name, values in rules.items()}
    display, colour, ground, sets_colour = None, None, None, False
    for name, (_kind, read, _written) in last.items():
        if name in ("display", "visibility"):
            display = (name, read)
        elif name in ("color", "font-color"):
            colour, sets_colour = read, True
        elif name == "background-color":
            ground = read
    if not sets_colour:
        colour = next((read for kind, read, _written in reversed(rules.get("font", [])) if kind == "colour"), None)
    if "background-color" not in last:
        ground = next((read for kind, read, _written in reversed(rules.get("background", [])) if kind == "colour"), None)

    def size(name: str) -> tuple[float, bool, str] | None:
        return (*last[name][1], last[name][2]) if name in last else None

    def least(own: tuple[float, bool, str] | None, most: tuple[float, bool, str] | None) -> tuple[float, bool, str] | None:
        if own and most and own[1] == most[1]:
            return most if most[0] < own[0] else own
        if own and most:
            return most if most[0] == 0 else own
        return own or most

    def off(name: str) -> bool:
        return (found := size(name)) is not None and not found[1] and found[0] <= _RSPAMD_OFF_PAGE

    clipped = [f"{name}:{last[name][2]}" for name in ("clip", "clip-path") if name in last and last[name][1] > 0.5]
    if "position" in last and last["position"][1] > 0.5 and (off("left") or off("top")):
        off_page = f"position:{last['position'][2]};" + ";".join(f"{name}:{last[name][2]}" for name in ("left", "top") if off(name))
    else:
        off_page = f"text-indent:{last['text-indent'][2]}" if off("text-indent") else (clipped or [None])[0]
    font = next(((*read, written) for kind, read, written in rules.get("font", []) if kind == "size"), None)
    return _RspamdStyle(
        display=display,
        opacity=(last["opacity"][1], last["opacity"][2]) if "opacity" in last else None,
        off_page=off_page,
        font_size=size("font-size") or font,
        height=least(size("height"), size("max-height")),
        width=least(size("width"), size("max-width")),
        colour=colour,
        ground=ground,
        overflow=last["overflow"][1] if "overflow" in last else None,
        unheld=tuple(unheld),
    )


def _rspamd_attribute_rgba(value: str | None) -> tuple[float, float, float, float] | None:
    """A ``color`` or ``bgcolor`` attribute as rspamd reads it, on any element and over its style, or None where it reads
    none: the value as written, its bytes untrimmed, ``#`` and its digits as a hash's (``_rspamd_hex``, so ``" #1A1A17"``
    is none and ``#zzz`` black), or a colour's name in lower case (``BLACK`` is none), never ``rgb()`` (measured with
    rspamd 4.2.2)."""
    if value is None:
        return None
    data = value.encode("utf-8", "surrogatepass").decode("latin-1")
    return _rspamd_hex(data[1:]) if len(data) > 1 and data.startswith("#") else _rspamd_name_rgba(data)


def _legacy_rgba(value: str | None) -> tuple[float, float, float, float] | None:
    """A colour attribute (``color``, ``bgcolor``, ``text``, ``link``) as HTML parses one, the rules for parsing a
    legacy colour value: a named colour, ``#rgb``, else the value's hex digits read as three equal parts, so ``FBFAF6``
    without its ``#`` is ``#FBFAF6``; None for an empty value or ``transparent``."""
    text = (value or "").strip(" \t\n\f\r")
    if not text or text.lower() == "transparent":
        return None
    if re.fullmatch(r"[A-Za-z]+", text) and (named := _rgba(text.lower())) is not None:
        return named
    if re.fullmatch(r"#[0-9A-Fa-f]{3}", text):
        return _rgba(text.lower())
    digits = "".join("00" if ord(char) > 0xFFFF else char for char in text)[:128].removeprefix("#")
    digits = "".join(char if char in "0123456789abcdefABCDEF" else "0" for char in digits)
    while not digits or len(digits) % 3:
        digits += "0"
    size = len(digits) // 3
    parts = [digits[index * size:(index + 1) * size][-8:] for index in range(3)]
    while len(parts[0]) > 2 and all(part.startswith("0") for part in parts):
        parts = [part[1:] for part in parts]
    return (*(int(part[:2], 16) / 255 for part in parts), 1.0)


def _too_alike(colour: tuple[float, ...], ground: tuple[float, ...]) -> bool:
    """Whether a colour is too like the ground behind it to read, by rspamd's weighted distance in sRGB."""
    dr, dg, db = (((a - b) * 255) ** 2 for a, b in zip(colour[:3], ground[:3]))
    mean_red = (colour[0] + ground[0]) * 255 / 2
    return max(0.0, 2 * dr + 4 * dg + 3 * db + mean_red * (dr - db) / 256) ** 0.5 / 256 < _DISTINCT


def _painted(colour: tuple[float, ...], ground: tuple[float, ...], opacity: float) -> tuple[float, ...]:
    """The colour a browser paints a text in over its ground, its alpha times the opacity its boxes multiply to."""
    alpha = colour[3] * opacity
    return (*(c * alpha + g * (1 - alpha) for c, g in zip(colour[:3], ground[:3])), 1.0)


def _length_px(value: str, font: float, root: float) -> float:
    """A length in px as a browser computes it, em against ``font`` and rem against ``root``, the root element's size;
    0 in a unit of length the reader knows is 0. Raises ``_Unread`` for one the reader does not resolve or a browser
    drops: a percentage, a unit that is no length's (0deg) or that the reader does not know (0lh), ex and ch, which the
    face's letters set, a viewport unit, a function, an exponent, a number CSS does not write (16.px)."""
    match = _DIMENSION.fullmatch(value)
    if not match or (match.group(2) and match.group(2) not in _LENGTH_UNITS):
        raise _Unread(value)  # a percentage, of a box whose size the reader does not know, or a unit it does not read
    number, unit = float(match.group(1)), match.group(2)
    if number == 0:
        return 0.0
    if unit in _ABSOLUTE_PX:
        return number * _ABSOLUTE_PX[unit]
    if unit in ("em", "rem"):
        return number * (font if unit == "em" else root)
    raise _Unread(value)


def _ua_font_px(tag: str, parent: float, parent_tag: str) -> float:
    """The font size a browser's own sheet gives an element under its parent's: the parent's for most, and an <rt>'s
    half only where its parent is a <ruby> (``ruby > rt``, measured in Chromium)."""
    if tag == "rt":
        return parent / 2 if parent_tag == "ruby" else parent
    return 40 / 3 if tag in _CONTROLS else parent * _UA_FONT_FACTORS.get(tag, 1.0)


def _font_px(value: str, parent: float, reverted: float, root: float) -> float:
    """A font size as a browser computes it against its parent's, in px, ``revert`` taking the size the browser's
    own sheet gives the element (``reverted``) and rem the root element's (``root``). Raises ``_Unread`` for a value it
    does not resolve, and for a negative one, which a browser drops."""
    if value in ("inherit", "unset"):
        return parent
    if value in ("revert", "revert-layer"):
        return reverted
    if value == "initial":
        return 16.0
    if value in _FONT_KEYWORDS:
        return _FONT_KEYWORDS[value]
    if value in ("smaller", "larger"):
        return parent / 1.2 if value == "smaller" else parent * 1.2
    match = _DIMENSION.fullmatch(value)
    size = parent * float(match.group(1)) / 100 if match and match.group(2) == "%" else _length_px(value, parent, root)
    if size < 0:
        raise _Unread(value)
    return size


def _font_kind(token: tinycss2.ast.Node) -> str | None:
    """The kind of word a font shorthand takes before its size that ``token`` is, or None for one it does not take."""
    word = token.lower_value if token.type == "ident" else ""
    if word == "normal":
        return "normal"
    if word in _FONT_STYLES:
        return "style"
    if word == "small-caps":
        return "variant"
    if word in _FONT_WEIGHTS or (token.type == "number" and 1 <= token.value <= 1000):
        return "weight"
    return "stretch" if word in _FONT_STRETCHES else None


def _line_height_taken(token: tinycss2.ast.Node) -> bool:
    """Whether a font shorthand's line height is one a browser takes and the reader reads: normal, or a number, a
    percentage or a length in a unit it knows, none of them negative."""
    if token.type == "ident":
        return token.lower_value == "normal"
    if token.type in ("number", "percentage"):
        return token.value >= 0
    return token.type == "dimension" and token.value >= 0 and token.lower_unit in _LENGTH_UNITS


def _family_taken(tokens: list[tinycss2.ast.Node]) -> bool:
    """Whether a font shorthand's family, between its commas, is one a browser takes: a string alone, or names, of
    which one alone is no CSS-wide keyword nor ``default``, and of which the first of two or more is no generic
    family."""
    if len(tokens) == 1 and tokens[0].type == "string":
        return True
    if not tokens or any(token.type != "ident" for token in tokens):
        return False
    if len(tokens) == 1:
        return tokens[0].lower_value not in (*_GLOBAL, "default")
    return tokens[0].lower_value not in _GENERIC_FAMILIES


def _shorthand_font_px(value: str, parent: float, reverted: float, root: float) -> float:
    """The size a ``font`` shorthand sets, where a browser takes the shorthand, or a CSS-wide keyword's. A browser takes
    up to four words of style, variant, weight and stretch, each kind once and normal for any, then a size, a line
    height after a ``/``, and families separated by commas (``_family_taken``), and drops any other shorthand, so a size
    set before it stands (CSS Fonts 4, measured in Chromium 141 with CSS.supports). Raises ``_Unread`` for one it drops,
    and for one that sets a size or a line height the reader does not resolve (a system font such as caption, an
    oblique's angle, ``calc()``, a unit it does not know)."""
    if value in _GLOBAL:
        return _font_px(value, parent, reverted, root)
    tokens = [
        token for token in tinycss2.parse_component_value_list(value) if token.type not in ("whitespace", "comment")
    ]
    kinds: set[str] = set()
    index = 0
    while index < min(4, len(tokens)) and (kind := _font_kind(tokens[index])) is not None and kind not in kinds:
        kinds |= {kind} - {"normal"}
        index += 1
    if index == len(tokens) or (word := tinycss2.serialize([tokens[index]])) in _GLOBAL:
        raise _Unread(value)
    size = _font_px(word, parent, reverted, root)  # raises _Unread for a size a browser drops or the reader does not resolve
    index += 1
    if index < len(tokens) and tokens[index].type == "literal" and tokens[index].value == "/":
        if index + 1 == len(tokens) or not _line_height_taken(tokens[index + 1]):
            raise _Unread(value)
        index += 2
    families: list[list[tinycss2.ast.Node]] = [[]]
    for token in tokens[index:]:
        if token.type == "literal" and token.value == ",":
            families.append([])
        else:
            families[-1].append(token)
    if not all(_family_taken(family) for family in families):
        raise _Unread(value)
    return size


def _ground(element: ElementTree.Element, declared: list[tuple[str, bool, str]]) -> tuple[float, ...] | None:
    """The colour an element paints behind its text in a browser, which the walk lays over the ground below it: its
    background's colour, from ``background-color`` or a ``background`` shorthand that sets a colour alone (``none``
    setting it transparent), or the ``bgcolor`` hint of a body or a table's part below either; None for a CSS-wide
    keyword, which paints the ground below again. Raises ``_Unread`` for a ground the reader cannot compare: a value it
    does not resolve, and a shorthand that sets more than a colour, such as an image, a gradient or a clip to the text,
    which Chromium takes there and which paints the ground inside the letters alone (measured in Chromium 141)."""
    won = _winner(declared, "background-color", "background")
    if won is None:
        return _legacy_rgba(element.get("bgcolor")) if _local(element.tag) in _BGCOLOR_HINTED else None
    name, value = won
    if value in _GLOBAL:
        return None
    if name == "background" and value == "none":
        return (0.0, 0.0, 0.0, 0.0)
    if (colour := _rgba(value)) is None:
        raise _Unread(value)
    return colour


def _words(value: str) -> list[str]:
    """A value's component values as written, a function and its arguments one word."""
    return [tinycss2.serialize([token]) for token in tinycss2.parse_component_value_list(value) if token.type != "whitespace"]


def _opacity(value: str) -> float:
    """An opacity as a number from 0 to 1, a percentage read as a fraction. Raises ``_Unread`` otherwise."""
    match = re.fullmatch(rf"({_CSS_NUMBER})(%?)", value)
    if not match:
        raise _Unread(value)
    return min(1.0, max(0.0, float(match.group(1)) / (100 if match.group(2) else 1)))


def _plain_lengths(value: str) -> bool:
    """Whether a value is plain lengths a margin cannot move text off the page with: each word ``auto``, a CSS-wide
    keyword or a length or percentage of 0 or more, no ``calc()`` among them."""
    for word in _words(value):
        match = _DIMENSION.fullmatch(word)
        if word not in ("auto", *_GLOBAL) and not (match and float(match.group(1)) >= 0):
            return False
    return True


def _box_size(element: ElementTree.Element, declared: list[tuple[str, bool, str]], axis: str, font: float,
              root: float) -> tuple[float, str] | None:
    """The size a box clips at on an axis, in px, and what set it, where the reader can tell: its size capped by its
    max and raised to its min, from the style or, where the style sets no size, the width or height attribute HTML maps
    to one; None where it sets neither a size nor a max, and so takes its content's or its container's, or where a
    value the reader does not resolve may bear on it (a percentage, ``inherit``, ``calc()``)."""
    names, maximum, minimum = _AXIS_SIZES[axis]

    def read(pair: tuple[str, str]) -> tuple[float, str] | None:
        won = _winner(declared, *pair)
        if won is None or won[1] in _SIZE_WORDS:
            return None
        return _length_px(won[1], font, root), f"{won[0]}:{won[1]}"  # raises _Unread for a value it does not resolve

    capped = []
    for pair in (names, maximum):
        try:
            if (found := read(pair)) is not None:
                capped.append(found)
        except _Unread:
            continue  # the other may still cap it
    attribute = "width" if axis == "x" else "height"
    hint = (element.get(attribute) or "").strip()
    if _winner(declared, *names) is None and _local(element.tag) in _SIZE_HINTED[axis] and re.fullmatch(r"\d+(?:\.\d+)?", hint):
        capped.append((float(hint), f'{attribute}="{hint}"'))
    try:
        floor = read(minimum)
    except _Unread:
        return None
    if not capped:
        return None
    used = min(capped)
    return floor if floor is not None and floor[0] > used[0] else used


def _overflow_axes(declared: list[tuple[str, bool, str]],
                   refuse: Callable[[str, str], None]) -> tuple[str, str, list[tuple[str, str]]]:
    """The overflow a box uses on each axis, x then y, as a browser computes it, and the declarations that set one that
    clips: the overflow shorthand's one value or its two (x, then y) or each axis's longhand, whichever wins; a CSS-wide
    keyword but ``inherit`` as visible; and visible beside an axis that is neither visible nor clip read as auto, clip
    beside one as hidden (CSS Overflow 3). A value the reader does not read, ``inherit`` among them, is refused and
    leaves its axis visible."""
    axes: list[str] = []
    setters: list[tuple[str, str]] = []
    for index, axis in enumerate(("x", "y")):
        won, value = _winner(declared, "overflow", f"overflow-{axis}"), "visible"
        if won is not None:
            words = won[1].split() if won[0] == "overflow" else [won[1]]
            word = words[min(index, len(words) - 1)] if words else ""
            if word in _CLIPPING:
                value = word
                setters.append(won)
            elif word not in _WHOLE:
                refuse(*won)
        axes.append(value)
    if not set(axes) <= {"visible", "clip"}:
        axes = [{"visible": "auto", "clip": "hidden"}.get(value, value) for value in axes]
    return axes[0], axes[1], setters


def _visible(value: str, parent: bool) -> bool:
    """Whether a browser shows a box's text under ``visibility:value``, a value that inherits the parent's."""
    if value in ("inherit", "unset", "revert", "revert-layer"):
        return parent
    if value in ("hidden", "collapse", "visible", "initial"):
        return value in ("visible", "initial")
    raise _Unread(value)


def _colour(value: str, parent: tuple[float, ...], link: tuple[float, ...] | None) -> tuple[float, ...]:
    """A box's text colour as a browser computes it: the parent's for a value that inherits it, the link colour (the
    browser's blue, or the body's ``link`` attribute) for ``revert`` on a link, black for ``initial``, else the colour
    written."""
    if value in ("inherit", "unset", "currentcolor", "revert", "revert-layer"):
        return link if link is not None and value.startswith("revert") else parent
    if value == "initial":
        return _BLACK
    if (colour := _rgba(value)) is None:
        raise _Unread(value)
    return colour


def _own_opacity(value: str, parent: float) -> float:
    """The opacity a box sets, ``inherit`` taking its parent's own (which the walk multiplies in again)."""
    if value == "inherit":
        return parent
    return 1.0 if value in _INERT else _opacity(value)


def _rspamd_px(own: tuple[float, bool, str] | None, parent: int | None, base: int, least: int, name: str,
               refuse: Callable[[str, str], None]) -> int | None:
    """A size rspamd keeps for a box, in whole px (html_block.hxx): ``own``, a number or a percentage, stored in 16
    bits with a percentage negated (``least`` for one past their range), so a negative number reads as a percentage
    too, which it takes of ``parent`` (the box above's, or ``base`` where it hands down none) and cuts to a whole
    number; else the parent's. A percentage it takes past 16 bits, where C++ leaves the conversion undefined, is refused
    (``refuse(name, value)``) and read as none."""
    if own is None:
        return parent
    number, percent, written = own
    stored = -number if percent else number
    stored = least if stored < -32768 else 32767 if stored > 32767 else int(stored)
    if stored >= 0:
        return stored
    taken = (base if parent is None else parent) * (-stored / 100.0)
    if not -32768 <= taken < 32768:
        refuse(name, written)
        return parent
    return int(taken)


@dataclass(frozen=True)
class _Seen:
    """What a text inherits on the way down a page, as a browser reads it and as rspamd does: whether a browser shows
    it, and why it hides all a box holds under ``visibility:collapse``, which no box below shows again; its size, and
    the root element's, which rem takes; its colour and the ground behind it, the opacity its boxes multiply to, the
    opacity its own box sets (which ``opacity:inherit`` takes), a link's colour (the body's ``link`` attribute or the
    browser's blue) and its box's element, which sizes an <rt>; why rspamd hides all a box holds (a hidden box above
    it), the size rspamd reads in whole px (None where no box sets one), rspamd's colour and ground, and the height and
    width rspamd hands down; and whether it sits in the header."""

    visible: bool = True
    collapsed: str | None = None
    size: float = 16.0
    root: float = 16.0
    colour: tuple[float, ...] = _BLACK
    ground: tuple[float, ...] = _WHITE
    opacity: float = 1.0
    own_opacity: float = 1.0
    link_colour: tuple[float, ...] = _LINK_BLUE
    tag: str = ""
    rspamd_hidden: str | None = None
    rspamd_size: int | None = None
    rspamd_colour: tuple[float, ...] = _BLACK
    rspamd_ground: tuple[float, ...] = _WHITE
    rspamd_height: float | None = None
    rspamd_width: float | None = None
    header: bool = False


def _seen_below(seen: _Seen, element: ElementTree.Element, declared: list[tuple[str, bool, str]], header: bool,
                refuse: Callable[[str, str], None]) -> _Seen:
    """What the element's text and its children inherit from it, each declaration the reader cannot resolve refused
    (``refuse(name, value)``), the element then read as if it set none."""
    tag = _local(element.tag)

    def resolved(names: tuple[str, ...], read: Callable[[str, str], object], kept: object) -> object:
        won = _winner(declared, *names)
        if won is None:
            return kept
        try:
            return read(*won)
        except _Unread:
            refuse(*won)
            return kept

    visible = resolved(("visibility",), lambda name, value: _visible(value, seen.visible), seen.visible)
    # visibility:collapse removes a table's row, row group or column whole, whatever a box below sets, where on a box of
    # another kind it hides as hidden does (measured in Chromium 141); the reader reads it so on a box of any kind.
    collapsing = _winner(declared, "visibility")
    collapsed = seen.collapsed or (
        f"<{tag}> is visibility:collapse, which hides all it holds whatever a box below sets, as a browser removes a "
        "table's row whole" if collapsing and collapsing[1] == "collapse" else None
    )
    own_size = _ua_font_px(tag, seen.size, seen.tag)
    size = resolved(
        ("font-size", "font"),
        lambda name, value: (_font_px if name == "font-size" else _shorthand_font_px)(value, seen.size, own_size, seen.root),
        _FONT_SIZE_ATTRIBUTE.get(element.get("size") or "", own_size) if tag == "font" else own_size,
    )
    link = seen.link_colour if tag == "a" and element.get("href") is not None else None
    # Below the style: a <font color> and the body's text attribute are hints (a value HTML parses as a legacy
    # colour), and a browser's own sheet colours a link that sets none.
    hinted = _legacy_rgba(element.get("color")) if tag == "font" else _legacy_rgba(element.get("text")) if tag == "body" else None
    colour = resolved(("color",), lambda name, value: _colour(value, seen.colour, link), hinted or link or seen.colour)
    try:
        ground = _ground(element, declared)
    except _Unread:
        refuse(*(_winner(declared, "background-color", "background") or ("background", "")))
        ground = None
    own_opacity = resolved(("opacity",), lambda name, value: _own_opacity(value, seen.own_opacity), 1.0)

    # rspamd's reading (``_rspamd_style``): the display its display and visibility set, and the hidden attribute over
    # any display, a hidden box hiding all it holds (an opacity under 0.1 and a box off the page the walk reads at the
    # box); its font size, height and width (``_rspamd_px``), each handed down to a box that sets none, but a height and
    # a width to a table or its parts, which their content sizes; its colour and its ground, a color and a bgcolor
    # attribute, as written, over the style's, on any element (measured with rspamd 4.2.2).
    style = _rspamd_style(element.get("style"))
    rspamd_hidden = seen.rspamd_hidden
    if rspamd_hidden is None and style.display and style.display[1] in _RSPAMD_HIDING:
        rspamd_hidden = f"rspamd reads <{tag}> as {style.display[0]}:{style.display[1]}, which hides all it holds"
    elif rspamd_hidden is None and element.get("hidden") is not None:
        rspamd_hidden = f"<{tag}> carries the hidden attribute, which rspamd reads as hiding it over any display"
    bounded = tag not in _RSPAMD_UNBOUNDED
    rspamd_colour = _rspamd_attribute_rgba(element.get("color")) or style.colour
    rspamd_ground = _rspamd_attribute_rgba(element.get("bgcolor")) or style.ground
    return _Seen(
        visible=visible,
        collapsed=collapsed,
        size=size,
        root=size if tag == "html" else seen.root,
        colour=colour,
        ground=seen.ground if ground is None else _painted(ground, seen.ground, 1.0),
        opacity=seen.opacity * own_opacity,
        own_opacity=own_opacity,
        link_colour=(_legacy_rgba(element.get("link")) or seen.link_colour) if tag == "body" else seen.link_colour,
        tag=tag,
        rspamd_hidden=rspamd_hidden,
        rspamd_size=_rspamd_px(style.font_size, seen.rspamd_size, 16, -32768, "font-size", refuse),
        rspamd_colour=seen.rspamd_colour if rspamd_colour is None else rspamd_colour,
        rspamd_ground=seen.rspamd_ground if rspamd_ground is None else rspamd_ground,
        rspamd_height=_rspamd_px(style.height, seen.rspamd_height if bounded else None, 800, -100, "height", refuse),
        rspamd_width=_rspamd_px(style.width, seen.rspamd_width if bounded else None, 1024, -32768, "width", refuse),
        header=header,
    )


def _column(element: ElementTree.Element) -> bool:
    """Whether the reader reads an element as a table's column: a <col>, a <colgroup>, or a box laid out as either (the
    display a browser keeps, a later one it drops aside), wherever it sits, though a browser lays one out as a column
    only in a table or under a column group (fail closed)."""
    display = _won(_declarations(element.get("style"))[0], "display")
    return _local(element.tag) in ("col", "colgroup") or display in _COLUMN_DISPLAYS


def _clipped_to(element: ElementTree.Element, declared: list[tuple[str, bool, str]], below: _Seen,
                refuse: Callable[[str, str], None]) -> str | None:
    """Where a box that holds text clips its overflow so that the text does not show, the reason; else None. In a
    browser a box clips on each axis whose overflow is not visible (``_overflow_axes``): at a size it sets under 4 px on
    one, as ``height:0`` or ``max-height:0`` clip a preheader, it shows nothing; at any other size, its own, its
    content's or its container's, it can cut the text it holds where the reader does not lay the text out, so the
    reader refuses the box (fail closed). As rspamd reads a page, a box hides all it holds where its overflow
    (``_rspamd_style``) is hidden or clip and the height or the width it keeps, its own or one handed down, is under
    1 px (measured with rspamd 4.2.2)."""
    x, y, setters = _overflow_axes(declared, refuse)
    for axis, overflow in (("x", x), ("y", y)):
        if overflow != "visible" and (size := _box_size(element, declared, axis, below.size, below.root)) is not None and size[0] < _LEGIBLE_PX:
            return f"{size[1]} under overflow-{axis}:{overflow}"
    for setter in setters:
        refuse(*setter)
    if (overflow := _rspamd_style(element.get("style")).overflow) in ("hidden", "clip"):
        for axis, kept in (("height", below.rspamd_height), ("width", below.rspamd_width)):
            if kept == 0:
                return f"rspamd reads {axis} as 0 under overflow:{overflow}"
    return None


def _hidden_because(text: str | None, seen: _Seen) -> str | None:
    """Why a text inheriting ``seen`` does not show, in a browser or as rspamd reads it, or None where it shows."""
    if not text or not _UNCOUNTED.sub("", text):
        return None
    if seen.collapsed:
        return seen.collapsed
    if not seen.visible:
        return "it is visibility:hidden"
    if seen.size < _LEGIBLE_PX:
        return f"its font size is {seen.size:g}px, under {_LEGIBLE_PX:g} px"
    if seen.colour[3] < _SHOWN_ALPHA:
        return "its colour is transparent"
    if (ink := seen.opacity * seen.colour[3]) < _OPAQUE:
        floor = f"under {_OPAQUE:g}, rspamd's floor for an opacity"
        if seen.opacity == 1:
            return f"its colour's alpha paints its ink at {ink:.3g}, {floor}"
        if seen.colour[3] < 1:
            return f"its colour's alpha and its boxes' opacities paint its ink at {ink:.3g}, {floor}"
        return f"its boxes' opacities multiply to {ink:.3g}, {floor}"
    if _too_alike(_painted(seen.colour, seen.ground, seen.opacity), seen.ground):
        if seen.opacity < 1:
            return f"its colour, painted at the opacity of {seen.opacity:.3g} its boxes multiply to, is too like the ground behind it"
        return "its colour is too like the ground behind it"
    if seen.rspamd_hidden:
        return seen.rspamd_hidden
    if seen.rspamd_size is not None and int(seen.rspamd_size) <= 3:
        return f"rspamd reads its font size as {int(seen.rspamd_size)}px, 3 or less"
    if seen.rspamd_colour[3] < _SHOWN_ALPHA:
        return "rspamd reads its colour as transparent"
    if seen.rspamd_ground[3] > _SHOWN_ALPHA and _too_alike(seen.rspamd_colour, seen.rspamd_ground):
        return "rspamd reads its colour as too like the ground behind it"
    return None


def _texts(page: str, outlook: bool) -> tuple[list[tuple[str | None, str, bool]], list[str]]:
    """Each text of the page's body in one view, a browser's (with rspamd's reading of the same page) or classic
    Outlook's, in order, as (why it does not show or None, text, in the header), ``_BLOCK_EDGE`` marking each
    block's edge; and each declaration and element the reader refuses."""
    root = tinyhtml5.parse(outlook_view(page) if outlook else page, namespace_html_elements=False)
    headers = set(_header_tables(root))
    body = next((element for element in root.iter() if element.tag == "body"), root)
    first = root if root.tag == "html" else body  # the walk reads the html element's style, then its body alone
    texts: list[tuple[str | None, str, bool]] = []
    refused: list[str] = []
    for meta in (element for element in root.iter() if isinstance(element.tag, str) and _local(element.tag) == "meta"):
        scheme, content = (meta.get("name") or "").strip().lower(), " ".join((meta.get("content") or "").lower().split())
        if scheme in ("color-scheme", "supported-color-schemes") and "dark" in content.split():
            refused.append(
                f"<meta> sets {scheme}:{content}, a dark colour scheme, under which a browser paints the text a page "
                "leaves uncoloured in a light colour of its own (measured in Chromium 141): this reader reads the light "
                "scheme alone, so ask for light"
            )

    def refuse_column(column: ElementTree.Element) -> None:
        """Refuse what a column, a <col>, a <colgroup> or a box laid out as either, paints behind its cells or
        collapses them with: its ground, and visibility:collapse, where hidden leaves them shown (measured in Chromium
        141). The walk reads a cell under its row and its table, not its column."""
        declared = _all_declared(column.get("style"))
        painted = [f"{won[0]}:{won[1]}" for name in ("background", "background-color", "visibility")
                   if (won := _winner(declared, name)) and won[1] not in ("none", "transparent", "visible", "hidden", *_GLOBAL)]
        for what in painted + ["bgcolor"] * (column.get("bgcolor") is not None):
            refused.append(
                f"<{_local(column.tag)}> sets {what}, which a column paints behind its cells or collapses them with, "
                "where this reader reads a cell under its row: set it on the cells"
            )

    def own_text(element: ElementTree.Element) -> bool:
        """Whether the element holds a counted character of its own, in its text or after a child."""
        return bool(_UNCOUNTED.sub("", (element.text or "") + "".join(child.tail or "" for child in element)))

    def refusal(tag: str, name: str, value: str) -> str:
        return (
            f"<{tag}> sets {name}:{value}, which can hide text in a way this reader does not model or resolve: "
            "write a value it reads, or teach the reader (tests/support/mail_styles.py)"
        )

    def refuse_declared(element: ElementTree.Element) -> None:
        """Refuse what an element's own style and attributes set that the reader does not read: a property it does not
        read, a value it does not resolve, a background image an attribute sets, and a colour rspamd reads off a name
        only X11 knows, at a value the reader does not hold (``_rspamd_only_colour``), and a style rspamd reads on terms
        of its own, which the port of its reading does not follow (``_UNPORTED``)."""
        declared = _all_declared(element.get("style"))
        tag = _local(element.tag)
        for name, _important, value in declared:
            if name not in _READS:
                refused.append(
                    f"<{tag}> sets {name}:{value}, a property this reader does not read, which may hide text: drop it, "
                    "or teach the reader that it cannot, or how it does (tests/support/mail_styles.py)"
                )
            elif _UNRESOLVED.search(value) or (name in _MARGINS and not _plain_lengths(value)):
                refused.append(refusal(tag, name, value))
            elif name == "text-decoration" and any(
                token.type != "ident" and _rgba(tinycss2.serialize([token])) is None
                for token in tinycss2.parse_component_value_list(value) if token.type not in ("whitespace", "comment")
            ):
                refused.append(refusal(tag, name, value))  # a thickness, which can lay the line over the text
        for name in dict.fromkeys(name for name, _important, _value in declared if _READS.get(name) is not None):
            if (won := _winner(declared, name)) and won[1] not in _READS[name]:
                refused.append(refusal(tag, *won))
        for name, value in _rspamd_style(element.get("style")).unheld:
            refused.append(refusal(tag, name, value))  # a colour rspamd reads off a name only X11 knows
        if _UNPORTED.search(element.get("style") or ""):
            refused.append(
                f"<{tag}> sets a style that holds a backslash or U+FFFD, which rspamd reads on terms of its own (an "
                "escape it unescapes otherwise than a browser does, a NUL the page's parser has replaced): write the "
                "style without either"
            )
        # The attributes that paint an image behind a text (HTML maps a background onto a body and a table's parts, and
        # the reader refuses one anywhere), and those that colour it off a name only X11 knows, as rspamd reads them.
        if element.get("background") is not None:
            refused.append(
                f"<{tag}> sets the background attribute, an image behind its text whose colours this reader cannot "
                "compare the text's with: set a bgcolor or a background-color"
            )
        for name in ("color", "bgcolor"):
            if _rspamd_only_colour(element.get(name) or ""):
                refused.append(
                    f'<{tag}> sets {name}="{element.get(name)}", a colour rspamd reads off a name only X11 knows, at a '
                    "value this reader does not hold: write the colour as a hex"
                )

    def walk(element: ElementTree.Element, seen: _Seen, holder: str | None) -> None:
        declared = _all_declared(element.get("style"))
        tag = _local(element.tag)
        header = seen.header or element in headers

        def refuse(name: str, value: str) -> None:
            refused.append(refusal(tag, name, value))

        refuse_declared(element)
        # The attributes that colour a link as the reader does not, place a box over the page or show a template in
        # place of its parent's content.
        for name in ("vlink", "alink"):
            if element.get(name) is not None:
                refused.append(
                    f"<{tag}> sets {name}, the colour of a visited or an active link, which this reader does not read: "
                    "colour each link in its own style"
                )
        placed = (tag == "dialog" and element.get("open") is not None) or element.get("popover") is not None
        if placed and _laid_out_alone(element):
            refused.append(
                f"<{tag}> sits over the page, where a browser's own style sheet places an open <dialog> or a popover a "
                "page gives a display (position:absolute or fixed), and can cover text there: this reader does not model "
                "it, so lay the text out as the page's own"
            )
        display = _won(_declarations(element.get("style"))[0], "display") or ""
        if _column(element):
            refuse_column(element)
        if tag == "template" and element.get("shadowrootmode") is not None:
            refused.append(
                "<template> sets shadowrootmode, which shows it in place of its parent's own content, a declarative "
                "shadow root (measured in Chromium 141): this reader does not model it, so lay the text out as the "
                "page's own"
            )
        if holder is None and tag not in _TEXT_ELEMENTS:
            holder = f"<{tag}>, which a browser lays out as something other than text, or does not know"
        closed = tag == "details" and element.get("open") is None
        below = _seen_below(seen, element, declared, header, refuse)
        for name in ("letter-spacing", "word-spacing"):
            # Spacing a tenth of an em or more below normal stacks the letters or the words on one another.
            if (won := _winner(declared, name)) and won[1] not in ("normal", *_GLOBAL):
                try:
                    if _length_px(won[1], below.size, below.root) < -0.1 * below.size:
                        refuse(*won)
                except _Unread:
                    refuse(*won)
        holds_text = bool(_UNCOUNTED.sub("", "".join((body if tag == "html" else element).itertext())))
        hidden = None
        if not _laid_out_alone(element):
            hidden = f"<{tag}> is laid out nowhere (display:none, the hidden attribute or a browser's own style sheet)"
        elif display in _COLUMN_DISPLAYS:
            hidden = f"<{tag}> is display:{display}, a table's column, whose content a browser does not render"
        elif (element.get("hidden") or "").lower() == "until-found" or (_winner(declared, "content-visibility") or ("", ""))[1] == "hidden":
            hidden = f"<{tag}> skips its content (hidden=until-found or content-visibility:hidden), which shows only when found"
        elif outlook and (_winner(declared, "mso-hide") or ("", ""))[1] == "all":
            hidden = f"<{tag}> is mso-hide:all, which classic Outlook hides"
        elif (faded := _rspamd_style(element.get("style")).opacity) and faded[0] < _OPAQUE:
            hidden = f"<{tag}> is opacity:{faded[1]}, under {_OPAQUE:g}, which rspamd reads as hiding all it holds"
        elif off_page := _rspamd_style(element.get("style")).off_page:
            hidden = f"<{tag}> is {off_page}, which rspamd reads as off the page, hiding all it holds"
        elif holds_text and (clip := _clipped_to(element, declared, below, refuse)):
            hidden = f"<{tag}> clips its overflow to nothing ({clip})"
        if hidden is not None:
            texts.append((hidden, "".join((body if tag == "html" else element).itertext()), header))
            if _laid_out_alone(element):
                # A box the walk goes no further into that a browser still lays out may hold a table's columns, which
                # paint and collapse its cells there: a column group laid out as one, or one whose content-visibility
                # or opacity, which a browser does not apply to a column group, the walk reads as hiding it. Each is
                # held to what the walk holds a column it reaches to: its own style and attributes, and its ground.
                for column in element.iter():
                    if column is not element and isinstance(column.tag, str) and _column(column):
                        refuse_declared(column)
                        refuse_column(column)
            return
        folded = "a closed <details>, outside its first summary, which a browser shows only once it is opened"
        held = holder or (folded if closed else None)
        if held and own_text(element):
            refused.append(
                f"<{tag}> holds text in {held}: set the text as the page's own, in an element HTML lays out as text, "
                "or teach the reader (tests/support/mail_styles.py)"
            )
        block = tag in _BLOCKS
        if block:
            texts.append((None, _BLOCK_EDGE, header))
        texts.append((_hidden_because(element.text, below), element.text or "", header))
        summarised = False  # a closed details shows its first summary alone
        for child in element:
            if tag == "html" and child is not body:
                continue  # the head, and a stray outside the body, a browser lays out nowhere
            if isinstance(child.tag, str):
                inner = held if closed and not (_local(child.tag) == "summary" and not summarised) else holder
                summarised = summarised or (closed and _local(child.tag) == "summary")
                walk(child, below, inner)
            texts.append((_hidden_because(child.tail, below), child.tail or "", header))
        if block:
            texts.append((None, _BLOCK_EDGE, header))

    walk(first, _Seen(), None)
    return texts, refused


# rspamd's HTML parser builds a tree of its own off a page's tags (html.cxx), where the walk reads rspamd's view on a
# browser's tree: the reader refuses a page whose two trees part.
_RSPAMD_EMPTY = frozenset({
    "area", "base", "basefont", "br", "col", "embed", "frame", "hr", "img", "input", "isindex", "keygen", "link", "meta",
    "nextid", "param", "source", "track", "wbr",
})  # the tags it closes as it opens them (html_tag_defs.hxx's CM_EMPTY)
_RSPAMD_RAW = ("noscript", "script", "style")  # the tags whose content it reads as text, to the next end tag of any name
_NAME_CLOSED = re.compile(r"<[^ \t\n\f\r/>]+/")  # a / right after a tag's name, which closes it for rspamd, as one before its > does
_RSPAMD_ATTRIBUTES = 128  # the attributes it reads off a tag, the rest dropped (html.cxx's max_attrs_per_tag)
_SHAPELESS = frozenset({"html", "head", "body"})  # read as their content, as a browser adds each a page leaves out
_ADDED = frozenset({"tbody", "colgroup"})  # what a browser adds around a row or a column a page writes bare
# The parse errors a browser recovers from as rspamd does, the tree left as it is: a character it replaces or reads on
# terms of its own, and a second attribute of a name, which both drop.
_CHARACTER_ERRORS = frozenset({
    "invalid-codepoint", "illegal-codepoint-for-numeric-entity", "named-entity-without-semicolon",
    "numeric-entity-without-semicolon", "expected-numeric-entity", "expected-named-entity", "duplicate-attribute",
})


def _mark_text(marks: list[str], text: str | None) -> None:
    """Mark in a tree's shape a run of text that holds a counted character, once for a run a comment splits."""
    if _UNCOUNTED.sub("", text or "") and marks[-1:] != ["t"]:
        marks.append("t")


def _browser_shape(root: ElementTree.Element) -> list[str]:
    """The shape of a browser's tree: each element's name where it opens and "/" where it closes, and "t" where a run of
    text that holds a counted character stands; a comment read as nothing, and the html, head and body elements as
    their content."""
    marks: list[str] = []

    def walk(element: ElementTree.Element) -> None:
        if not isinstance(element.tag, str):
            return
        name = _local(element.tag).lower()
        if name not in _SHAPELESS:
            marks.append(name)
        _mark_text(marks, element.text)
        for child in element:
            walk(child)
            _mark_text(marks, child.tail)
        if name not in _SHAPELESS:
            marks.append("/")

    walk(root)
    return marks


class _RspamdShape(HTMLParser):
    """The shape (``_browser_shape``) of the tree rspamd's HTML parser builds off a page's tags (html.cxx), each tag as
    the standard library's parser reads it: a start tag opens an element in the innermost one still open, closed at
    once where rspamd holds the tag empty (``_RSPAMD_EMPTY``) or it is written closed (``_NAME_CLOSED``, or ``/>``,
    an unquoted value's / among them); an end tag closes each element open up to the innermost of its name, and is
    read as nothing where none is open; no end tag is implied, a <p>'s before a block or an <li>'s before the next;
    and a noscript, a script or a style holds text. Held aside: each tag that holds raw text so (``raw``), which rspamd
    ends at an end tag of any name it takes for one (html.cxx: a ">" in the 29 bytes after "</" and a letter, with no
    comma before it and no byte under a newline, a tab or, read as a signed char, any byte past ASCII), each tag or
    attribute whose name is written with a character reference (``referenced``), which rspamd decodes and a browser
    does not, and each tag of more attributes than rspamd reads (``crowded``, ``_RSPAMD_ATTRIBUTES``)."""

    CDATA_CONTENT_ELEMENTS = _RSPAMD_RAW

    def __init__(self, page: str) -> None:
        super().__init__(convert_charrefs=True)
        self.marks: list[str] = []
        self.open: list[str] = []
        self.raw: list[str] = []
        self.referenced: list[str] = []
        self.crowded: list[str] = []
        self.feed(page)
        self.close()
        while self.open:
            self._close(self.open.pop())

    def set_cdata_mode(self, elem: str, **kwargs: object) -> None:
        if elem in _RSPAMD_RAW:  # a browser's other raw texts, a textarea's and a title's among them, are rspamd's markup
            super().set_cdata_mode(elem, **kwargs)

    def _close(self, name: str) -> None:
        if name not in _SHAPELESS:
            self.marks.append("/")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.raw += [tag] if tag in _RSPAMD_RAW else []
        self.referenced += [name for name in (tag, *(name for name, _value in attrs)) if "&" in name]
        if len(attrs) > _RSPAMD_ATTRIBUTES:
            self.crowded.append(tag)
        if tag not in _SHAPELESS:
            self.marks.append(tag)
        written = self.get_starttag_text() or ""
        if tag in _RSPAMD_EMPTY or _NAME_CLOSED.match(written) or written.endswith("/>"):
            self._close(tag)
        else:
            self.open.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag in self.open:
            while (name := self.open.pop()) != tag:
                self._close(name)
            self._close(tag)

    def handle_data(self, data: str) -> None:
        _mark_text(self.marks, data)


def _tree_problems(page: str) -> list[str]:
    """Where a browser builds the page otherwise than rspamd's HTML parser does, on whose tree the walk would read
    rspamd's view: each parse error a browser recovers from but a character's (``_CHARACTER_ERRORS``), the first of its
    kind; each tag that holds raw text, each name written with a character reference and each tag of more attributes
    than rspamd reads (``_RspamdShape``); and the first mark at which the shapes of the two trees part
    (``_browser_shape``), a row group or a column group a browser adds around a bare row or column aside."""
    parser = tinyhtml5.parser.HTMLParser(namespace_html_elements=False)
    browser = _browser_shape(parser.parse(page))
    first: dict[str, tuple[int, int]] = {}
    for position, code, _data in parser.errors:
        first.setdefault(code, position)
    problems = [
        f"a browser reads the page with a parse error ({code}, line {line}, column {column}) and recovers from it on "
        "terms of its own, which this reader does not model and rspamd's HTML parser does not share: write the markup "
        "without it"
        for code, (line, column) in first.items() if code not in _CHARACTER_ERRORS
    ]
    shape = _RspamdShape(page)
    problems += [
        f"<{tag}> holds raw text, which rspamd's HTML parser ends at an end tag of any name it takes for one (html.cxx: "
        "a > in the 29 bytes after </ and a letter, with no comma, no byte under a newline and, read as a signed char, no "
        "byte past ASCII before it), where a browser ends it at its own alone: leave it out of the page"
        for tag in dict.fromkeys(shape.raw)
    ]
    problems += [
        f"a name is written with a character reference ({name}), which rspamd's HTML parser decodes in a tag's or an "
        "attribute's name (html.cxx) where a browser does not: write the name without it"
        for name in dict.fromkeys(shape.referenced)
    ]
    problems += [
        f"<{tag}> carries more than {_RSPAMD_ATTRIBUTES} attributes, past which rspamd's HTML parser reads none (html.cxx), "
        "where a browser reads them all: carry fewer"
        for tag in dict.fromkeys(shape.crowded)
    ]
    rspamd = shape.marks

    def said(mark: str | None, top: str) -> str:
        return {None: "ends the page", "t": "holds text", "/": f"closes the <{top}>"}.get(mark, f"opens a <{mark}>")

    held: list[tuple[str, bool]] = []  # each element a browser holds open, and whether it is one rspamd's tree lacks
    i = j = 0
    while i < len(browser) or j < len(rspamd):
        mark, theirs = (browser[i] if i < len(browser) else None), (rspamd[j] if j < len(rspamd) else None)
        if mark == "/" and held[-1][1]:
            held.pop()
            i += 1
        elif mark == theirs:
            if mark == "/":
                held.pop()
            elif mark != "t":
                held.append((mark, False))
            i, j = i + 1, j + 1
        elif mark in _ADDED:
            held.append((mark, True))
            i += 1
        else:
            shared = [name for name, added in held if not added]
            where = " > ".join(f"<{name}>" for name in shared[-3:]) or "the page"
            problems.append(
                f"a browser builds the page's tree otherwise than rspamd's HTML parser does (html.cxx), and the reader "
                f"reads rspamd's view on a browser's tree: in {where}, a browser {said(mark, held[-1][0] if held else '')} "
                f"where rspamd {said(theirs, shared[-1] if shared else '')} (rspamd implies no end tag, neither a <p>'s "
                "before a block nor an <li>'s before the next, closes a tag written with a / after its name or before its "
                ">, and reads a noscript, a script or a style alone as text): close each element explicitly, in order"
            )
            break
    return problems


def hidden_text_problems(page: str) -> list[str]:
    """Where a page holds text it does not show its reader, in a browser's view, as rspamd reads it, or in classic
    Outlook's view; and each declaration, attribute or element that can hide text in a way the reader does not model or
    resolve. The walk reads the html element's style, then its body's.

    In a browser, a text is hidden where an element is laid out nowhere (``display:none``, the ``hidden`` attribute, one
    a browser's own style sheet hides, a popover no script opens) or as a table's column (``display:table-column`` or
    ``table-column-group``, whose content a browser does not render), skips its content (``hidden="until-found"``,
    ``content-visibility:hidden``) or clips its overflow at a size under 4 px (``_clipped_to``: on an axis whose
    overflow is not visible, a visible axis beside a clipping one clipping as auto); or where the text is
    ``visibility:hidden``, or under a box that is ``visibility:collapse``, which no box below shows again; set under 4
    px (``font-size:0``, ``font:0/0 a``, a rem of a root element set small, and the sizes a browser's own sheet gives
    ``<small>``, ``<sub>``, ``<sup>``, the headings, a form control and an ``<rt>`` in a ``<ruby>`` count) or in a
    colour that is transparent or, painted at the opacity its boxes multiply to, too like the ground behind it (each
    translucent ground laid over the one below, a ``<font color>``, a body's ``text`` and ``link`` and a cell's
    ``bgcolor`` parsed as HTML parses a legacy colour), by rspamd's measures, or whose ink its alpha and that opacity
    paint at under 0.1, rspamd's floor for an opacity. rspamd's reading (``_rspamd_style``, a port of rspamd 4.2.2's
    own reading of a style attribute, which shares no step with a browser's: a block in brackets ends it, and a second
    ";" or a property with no ":" skips the declaration after it; ``html_block.hxx``; measured with rspamd 4.2.2),
    importance aside, hides it too where a box sets an opacity under 0.1 or sits off the page (absolute or fixed at a
    left or a top of -1000 px or less, a text indent there, a clip or a clip path to nothing); a box above it is
    ``display:none`` or ``visibility:hidden`` as rspamd reads them, or carries the ``hidden`` attribute over any
    display; rspamd reads its size as 3 px or less (each box's size in whole px, em and rem at 16 px, ex at 8, a
    percentage of the size above cut to a whole number, a ``font-size`` over a ``font`` shorthand, a keyword and ``<font
    size>`` not at all); its box's overflow ends in hidden or clip over a height or a width under 1 px, one a box above
    hands down among them, but to a table or its parts; or rspamd reads its colour (a ``color`` attribute, as written,
    over the style's ``color`` or ``font-color``, and a ``font`` shorthand's colour where neither is set) and its ground
    (a ``bgcolor`` attribute on any element, as written, over the style's ``background-color`` or ``bgcolor``, and a
    ``background`` shorthand's last colour where neither is set) as transparent or too like each other. In classic
    Outlook's view it is hidden under ``mso-hide:all``. A run counts where it holds a character rspamd counts:
    whitespace and the characters that pad a preview do not (``rules/html.lua``), so a hairline's no-break space hides
    nothing.

    The reader fails closed. It reads the properties ``_READS`` names, at the values it names for each, and refuses any
    other property or value: a vendor's alias such as ``-webkit-transform``, ``font-size-adjust``, a text stroke,
    ``-webkit-text-security``, ``content``, ``background-clip:text``, ``offset-path``, a logical overflow, ``all``, a
    flex layout's direction, a text shadow, a decoration's thickness or offset (a length, ``calc()`` or an exponent in
    the shorthand alike), ``content-visibility:auto``, which clips its box as ``overflow:clip`` does, a dark colour
    scheme, an Outlook property but ``mso-hide``. It reads text in the elements ``_TEXT_ELEMENTS`` names, and refuses
    text in any other (a media element's fallback, a form control, a meter, a progress bar, a marquee, an SVG, a
    formula, a noscript, an element it does not know) and in a closed ``<details>`` outside its first summary. It
    refuses a value it does not resolve on a property it reads (``calc()``, an exponent, a viewport unit, ex and ch,
    which the face's letters set, a unit that is no length's, a number CSS does not write (``16.px``), a ``background``
    that sets more than a colour, a negative font size, a ``font`` shorthand a browser drops, which leaves a size set
    before it standing, a colour tinycss2 does not convert), any value from ``var()``, ``env()`` or ``attr()``, a margin
    that is not plain lengths, letter or word spacing a tenth of an em or more below normal, a box that clips text at a
    size it cannot tell is under 4 px (its own of 4 px or more, its content's or its container's, which the reader does
    not lay out), a background image an attribute sets, a body's ``vlink`` or ``alink``, a column's ground or
    ``visibility:collapse`` (a ``<col>``, a ``<colgroup>`` or a box laid out as either, a column group's own columns
    among them), which a browser paints behind its cells or collapses them with where the walk reads a cell under its
    row, an open ``<dialog>`` or a popover a page lays out, which a browser places over the page, a declarative shadow
    root, a colour rspamd reads off a name only X11 knows (``navyblue``, ``red3``, ``gray50``), at a value the reader
    does not hold, a style that holds a backslash or U+FFFD, which rspamd reads on terms the port of its reading does
    not follow (an escape it unescapes otherwise than a browser does, a NUL the page's parser has replaced), a style,
    color or bgcolor attribute, any of a tag's, written with a character reference that rspamd's HTML parser decodes
    on terms of its own (one not closed with ";", a name HTML does not define, a code point HTML maps or replaces), a
    page whose tree a browser builds otherwise than rspamd's HTML parser does, on which the walk would read rspamd's view
    (``_tree_problems``: an end tag a browser implies, a tag written closed, a noscript, a script or a style, whose
    raw text rspamd ends on terms of its own, a tag's or an attribute's name written with a character reference,
    which rspamd decodes, a tag of more attributes than rspamd reads), and one a browser reads with a parse error but
    a character's or a second attribute's, from which it recovers on terms of its own, and a ``<meta>`` that asks for
    a dark colour scheme.

    Read stricter than a browser: a box in the line, whose size and overflow a browser ignores, a table's or a cell's
    size, which grows with its content, and the body's or the root's overflow, which a browser hands to the viewport,
    each read as a box that clips at its size; ``visibility:collapse`` read as hiding all a box holds, whatever a box
    below sets, as a browser removes a table's row, row group or column whole, where on a box of another kind a box
    below can show again; a box's padding, inside which a clip keeps its text, unread; and the 6 px least size Chromium
    gives a text that keywords alone size not applied. Unread: a ``<style>`` block (the page rules refuse one), text
    outside the ``<body>``, text painted over by a box in the line's padding or border, or by an image or another box
    placed whole after a box set too low to hold it, a text moved far along the page (a margin, a vertical alignment, a
    padding), which its reader can still scroll to, a line wider than the screen that a client cuts (the width rules
    hold a run to it at normal letter spacing and up to 20 px, and the ``dir`` attribute can push such a line off the
    page's start), a face that draws letters as pictures (Wingdings), the 13 px a browser gives monospace text under no
    size set as a length, and rspamd's budget of 65536 attributes across a mail's HTML parts, past which it reads
    none."""
    found, refused = set(), []
    for name, written in _referenced_attributes(page):
        if not _decoded_alike(written):
            refused.append(
                f"a {name} attribute is written with a character reference ({written[:60]}) that rspamd's HTML "
                "parser decodes on terms of its own (html_entities.cxx): write the characters themselves, or a reference "
                "closed with ;"
            )
    refused += _tree_problems(page)
    for outlook in (False, True):
        texts, refusals = _texts(page, outlook)
        found.update((reason, " ".join(text.split())) for reason, text, _header in texts if reason and _UNCOUNTED.sub("", text))
        refused += refusals
    hides = [f"the page hides {text[:60]!r}: {reason}" for reason, text in sorted(found)]
    return hides + sorted(set(refused))


def shown_text(page: str) -> str:
    """The text a page shows its reader below its header, in a browser's view, a line for each block that holds any,
    each line's spaces collapsed as a browser collapses them: what a mail's text part says too (E110). The header,
    the hidden preheader and every text ``hidden_text_problems`` finds are left out."""
    texts, _refused = _texts(page, outlook=False)
    joined = "".join(text for reason, text, header in texts if reason is None and not header)
    return "\n".join(line for line in (" ".join(part.split()) for part in joined.split(_BLOCK_EDGE)) if line)


# SpamAssassin 4.0's HTML parser (Mail::SpamAssassin::HTML: text_style, close_table_tag, close_tag, html_text and
# html_font_invisible) reads a text's colours off a stack of the elements whose tags change them, and these are they, a
# <th> read as a <td>. It reads a style's colours on a table, a row, a cell, a span, a p, a div and a link alone, and an
# ink off these attributes; a ground nowhere else. The bgcolor attribute it takes in on a table, a row, a cell and a
# body sets nothing, and it reads no tag of a marquee, whose attributes it lists all the same (measured with
# SpamAssassin 4.0.0, E125).
_SPAMASSASSIN_STACKED = frozenset({"body", "font", "basefont", "table", "tr", "td", "big", "small", "span", "p", "div", "a"})
_SPAMASSASSIN_STYLED = frozenset({"table", "tr", "td", "span", "p", "div", "a"})
_SPAMASSASSIN_INKS = {"body": "text", "font": "color", "basefont": "color"}
# A declaration of a style split at each ";" that sets a text's ink, or after "background-" its ground: the colon right
# after the name, in any case. The reader matches it in ASCII and refuses a style past ASCII (``_SpamAssassinColours``).
# The values that keep the colour below, and the colours below them all.
_SPAMASSASSIN_COLOUR = re.compile(r"\s*(background-)?color:\s*(.+?)\s*$", re.IGNORECASE | re.ASCII)
_SPAMASSASSIN_KEEPS = frozenset({"inherit", "!important"})
_SPAMASSASSIN_DEFAULT = ("default", "#000000", "#ffffff")
# What it takes out of a text before it asks whether the text holds a character (html_text): ASCII whitespace, and the
# two characters its pattern for UTF-8's no-break space matches in a mail's text, which it reads decoded to characters
# (Message::Node::rendered, under normalize_charset's default): a capital A with a circumflex (U+00C2), then a no-break
# space. A no-break space alone is a character; "&nbsp;" it reads as a space before it parses the page.
_SPAMASSASSIN_BLANK = re.compile("[ \t\n\r\f\x0b]|\u00c2\u00a0")
# The names HTML::Parser decodes in a text (HTML::Entities' table, HTML 4's and "apos"); any other stays text.
_SPAMASSASSIN_ENTITIES = {**name2codepoint, "apos": 0x27}
# The elements whose content it (HTML::Parser) or the standard library's parser, in one Python release or another,
# reads as raw text, each on terms of its own.
_SPAMASSASSIN_RAW = frozenset({
    "script", "style", "title", "textarea", "xmp", "plaintext", "listing", "iframe", "noembed", "noframes",
})
_SIX_DIGITS = re.compile(r"#[0-9a-f]{6}")


def _spamassassin_too_alike(ink: str, ground: str) -> bool:
    """Whether SpamAssassin reads an ink as too like its ground (html_font_invisible): the same six digits, or a distance
    under 12 between them, each channel's difference weighted by its share of brightness, computed as it computes it."""
    if ink[-6:] == ground[-6:]:
        return True
    (r1, g1, b1), (r2, g2, b2) = ((int(colour[1:3], 16), int(colour[3:5], 16), int(colour[5:7], 16)) for colour in (ink, ground))
    return ((0.2126 * (r1 - r2)) ** 2 + (0.7152 * (g1 - g2)) ** 2 + (0.0722 * (b1 - b2)) ** 2) ** 0.5 < 12


def _token_errors(page: str) -> list[str]:
    """Each parse error a browser's tokenizer reports on a page (tinyhtml5's), once, but two attributes of one name,
    which SpamAssassin's parser reads as a browser does (the first)."""
    errors = (token["data"] for token in HTMLTokenizer(page) if token["type"] is Token.PARSE_ERROR)
    return list(dict.fromkeys(error for error in errors if error != "duplicate-attribute"))


class _SpamAssassinColours(HTMLParser):
    """The colours SpamAssassin's HTML parser reads each text of a page in, on the tags the standard library's parser
    reads off it (``spamassassin_contrast_problems``): ``too_alike`` holds each text it reads too like its ground, with
    the ink and the ground it reads, and ``refused`` each part of the page the reader does not read as it does."""

    def __init__(self, page: str) -> None:
        super().__init__(convert_charrefs=False)
        self.stack = [_SPAMASSASSIN_DEFAULT]
        self.text: list[str] = []
        self.too_alike: list[tuple[str, str, str]] = []
        self.refused: list[str] = []
        # SpamAssassin reads "&nbsp;" as a space and a curly double quote as a straight one before it parses a page.
        self.feed(page.replace("&nbsp;", " ").replace("\u201c", '"').replace("\u201d", '"'))
        self.close()
        self._read_text()

    def set_cdata_mode(self, elem: str, **kwargs: object) -> None:
        pass  # every element whose content a parser reads as raw text is refused, so the reader reads none so

    def _read_text(self) -> None:
        """Read the text since the last tag, comment or declaration as SpamAssassin reads a text: one it asks about
        where anything is left once its blanks are taken out."""
        text, self.text = "".join(self.text), []
        if _SPAMASSASSIN_BLANK.sub("", text):
            _tag, ink, ground = self.stack[-1]
            if _spamassassin_too_alike(ink, ground):
                self.too_alike.append((" ".join(text.split()), ink, ground))

    def handle_data(self, data: str) -> None:
        self.text.append(data)

    def handle_entityref(self, name: str) -> None:
        code = _SPAMASSASSIN_ENTITIES.get(name)
        self.text.append(f"&{name};" if code is None else chr(code))

    def handle_charref(self, name: str) -> None:
        digits, base = (name[1:], 16) if name[:1] in "xX" else (name, 10)
        digits = digits.lstrip("0") or "0"
        # Past Unicode's last code point (seven digits hold every one in either base) a browser's tokenizer reads an
        # error, which refuses the page, and a browser reads the replacement character, as the reader does to read on.
        code = int(digits, base) if len(digits) <= 7 else 0x110000
        self.text.append(chr(code) if code <= 0x10FFFF else "\ufffd")

    def handle_comment(self, data: str) -> None:
        self._read_text()

    def handle_decl(self, decl: str) -> None:
        self._read_text()

    def handle_pi(self, data: str) -> None:
        self._read_text()

    def unknown_decl(self, data: str) -> None:
        self._read_text()
        self.refused.append(
            f"a marked section (<![{data[:20]}) holds what SpamAssassin's HTML parser reads on terms of its own (a CDATA "
            "section's markup as text): leave it out of the page"
        )

    def _ascii_name(self, tag: str) -> None:
        """Refuse a tag whose name, as the standard library's parser reads it, holds a character past ASCII."""
        if not tag.isascii():
            self.refused.append(
                f"a tag's name, {tag!r}, holds a character past ASCII, which SpamAssassin, reading a mail's text as "
                "characters, reads on terms of its own (before the \"/\" that closes a start tag, a no-break space as a "
                "space, so it holds the tag open): write the tag's name in ASCII"
            )

    def _colour(self, tag: str, where: str, value: str, keeps: bool) -> str | None:
        """The colour SpamAssassin reads off ``value``, as six-digit hex in small letters: None where it keeps the colour
        below (``keeps``, in a style alone) or where the reader refuses the value."""
        value = value.strip(" \t\n\r\f\v").translate(_ASCII_LOWER)
        if keeps and value in _SPAMASSASSIN_KEEPS:
            return None
        if _SIX_DIGITS.fullmatch(value):
            return value
        self.refused.append(
            f"<{tag}>'s {where} is {value!r}, which the reader does not read as SpamAssassin reads it (a name, a short hex "
            "and rgb() as colours of its own, a value with !important after it as an invalid colour): write it as "
            "six-digit hex, as colour_problems asks"
        )
        return None

    def _referenced(self, names: set[str]) -> list[str]:
        """The attributes of ``names`` that the start tag being read writes with an ampersand, the first of each name."""
        written, seen, found = self.get_starttag_text() or "", set(), []
        position = _START_TAG.match(written).end()
        while (attribute := _ATTRIBUTE.match(written, position)).group(1):
            name = attribute.group(1).translate(_ASCII_LOWER)
            if name in names and name not in seen and "&" in (attribute.group(2) or ""):
                found.append(name)
            seen.add(name)
            position = attribute.end()
        return found

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._read_text()
        self._ascii_name(tag)
        if tag in _SPAMASSASSIN_RAW:
            self.refused.append(
                f"<{tag}> holds what a parser reads as raw text, SpamAssassin's (HTML::Parser) and the standard library's, "
                "in one Python release or another, each on terms of its own: leave it out of the page"
            )
        tag = "td" if tag == "th" else tag
        if tag not in _SPAMASSASSIN_STACKED:
            return
        first: dict[str, str] = {}
        for name, value in attrs:
            first.setdefault(name, value or "")  # HTML::Parser keeps the first of two same-named attributes, as a browser does
        ink_from, styled = _SPAMASSASSIN_INKS.get(tag), tag in _SPAMASSASSIN_STYLED
        for name in self._referenced({ink_from or "", "style" if styled else "", "size" if tag == "basefont" else ""} - {""}):
            self.refused.append(
                f"<{tag}>'s {name} attribute is written with a character reference, which SpamAssassin's HTML parser "
                "(HTML::Parser) decodes on terms of its own: write the characters themselves"
            )
        style = first.get("style", "") if styled else ""
        if not style.isascii():
            self.refused.append(
                f"<{tag}>'s style holds a character past ASCII, and SpamAssassin, which reads a mail's text as characters, "
                "matches a colour's declaration in Unicode (a no-break space as a space, a Kelvin sign as a k): write the "
                "style in ASCII"
            )
        size = first.get("size", "") if tag == "basefont" else ""
        if not size.isascii():
            self.refused.append(
                "<basefont>'s size holds a character past ASCII, and SpamAssassin, which reads a mail's text as "
                "characters, matches its digits and spaces in Unicode (a digit of another script as a digit, a no-break "
                "space as a space): write the size in ASCII"
            )
        if re.match(r"\s*\d", size, re.ASCII):
            return  # it reads a basefont's size alone where the basefont sets one
        if tag in ("td", "tr") and any(entry[0] == tag for entry in self.stack):
            closing = ("font", "td") if tag == "td" else ("font", "td", "tr")
            while self.stack[-1][0] in closing:
                self.stack.pop()
        ink, ground = self.stack[-1][1:]
        if tag not in ("big", "small"):
            if ink_from in first:
                ink = self._colour(tag, f"{ink_from} attribute", first[ink_from], keeps=False) or ink
            for part in style.split(";"):
                if declared := _SPAMASSASSIN_COLOUR.match(part):
                    name = "background-color" if declared.group(1) else "color"
                    colour = self._colour(tag, f"style's {name}", declared.group(2), keeps=True)
                    ink, ground = (ink, colour or ground) if declared.group(1) else (colour or ink, ground)
        self.stack.append((tag, ink, ground))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)  # SpamAssassin holds a tag written closed open, its "/" read as nothing

    def handle_endtag(self, tag: str) -> None:
        self._read_text()
        self._ascii_name(tag)
        tag = "td" if tag == "th" else tag
        if tag in _SPAMASSASSIN_STACKED and tag != "body" and any(entry[0] == tag for entry in self.stack):
            while self.stack.pop()[0] != tag:
                pass


def spamassassin_contrast_problems(page: str) -> list[str]:
    """Each text of a page that SpamAssassin 4.0 reads in an ink too like its ground, which it scores as hidden text
    (HTML_FONT_LOW_CONTRAST: 0.713 where a receiver runs neither network tests nor Bayes, 0.786 with Bayes alone, 0.001
    wherever it runs network tests, and two of its published metas build on it), and each part of the page the reader
    does not read as it does (E125).

    The reader is a port of SpamAssassin's own reading as it reads a mail (Mail::SpamAssassin::HTML: text_style,
    close_table_tag, close_tag, html_text and html_font_invisible, on a mail's text decoded to characters, as
    Message::Node::rendered hands it over under normalize_charset's default; measured with SpamAssassin 4.0.0), on the
    tags the standard library's parser reads off the page once "&nbsp;" is a space and a curly double quote a straight
    one, as SpamAssassin reads them. It keeps a stack of the elements whose tags change a text's colours
    (``_SPAMASSASSIN_STACKED``), black on white below them all, each opening on the colours of the one below it: it
    reads a text's ink off a body's ``text``, a font's or a basefont's ``color``, and the style of a table, a row, a cell
    (a ``<th>`` read as a ``<td>``), a span, a p, a div or a link, and its ground off that style alone. A style is split
    at each ";", and a declaration sets a colour where it reads ``color:`` or ``background-color:``, in any case, the
    colon right after the name: the last in a style is read, and ``inherit`` or ``!important`` alone keeps the colour
    below. So it reads no ``bgcolor`` attribute, though it takes one in on a table, a row, a cell and a body, no
    ``background`` shorthand, no style on a body, a heading, an ``<em>`` or any element but those, and no ``color :``
    spaced before its colon; it reads no tag of a marquee, a basefont that sets a size sets no colour, and a big or a
    small reads no attribute. A cell's start tag first closes the cells and fonts open at the top of the stack where a
    cell is open, and a row's the rows too, but nothing past them, so a span left open in a cell outlasts the cell, where
    a browser closes it; an end tag closes every element open above the innermost of its name, and nothing where none is
    open; a body's end tag closes nothing; a tag written closed is held open; and of two same-named attributes the first
    is read. A text runs to the next tag, comment or declaration, and counts where it holds anything but ASCII
    whitespace and a capital A with a circumflex followed by a no-break space (``_SPAMASSASSIN_BLANK``): a no-break space
    alone counts, and so does a zero-width space. A name HTML 4 defines it decodes in a text, and any other
    (``&Tab;``) it reads as written. A comment holds no text, so what classic Outlook's conditional comments hold is
    unread. Too alike is the same six digits, or a distance under 12, each channel's difference weighted by its share of
    brightness (0.2126, 0.7152 and 0.0722).

    The reader fails closed. It reads markup a browser's tokenizer reads without error, two attributes of one name aside
    (``_token_errors``), and refuses any other: a comment closed by ``-- >``, where HTML::Parser ends it, or by ``--!>``,
    an end tag holding an attribute, a ``/`` or a control character between a tag's name and its attributes, a bare
    ``&`` or a reference left unclosed, which the parsers tokenize each on terms of its own. It reads a colour as
    six-digit hex alone, which ``colour_problems`` holds every page to, and refuses any other value SpamAssassin reads
    as a text's ink or ground; a style or a basefont's size past ASCII, which SpamAssassin matches in Unicode; a tag's
    name past ASCII, since SpamAssassin reads a no-break space before the "/" that closes a start tag as a space and
    holds the tag open, where the standard library's parser reads the space into the name; an attribute it reads (a
    style, an ink, a basefont's size) that is written with a character reference, which HTML::Parser decodes on terms
    of its own; an element whose content one parser or the other reads as raw text (a script, a style, a title, a
    textarea, an xmp, a plaintext, a listing, an iframe, a noembed, a noframes); and a marked section, a CDATA
    section's markup among them, which SpamAssassin reads as text."""
    colours = _SpamAssassinColours(page)
    too_alike = [
        f"SpamAssassin reads {text[:60]!r} in {ink} on {ground}, too like its ground, and scores it as hidden text "
        "(HTML_FONT_LOW_CONTRAST): set the text's ground as background-color, the colon right after the name, in the "
        "style of the link, span, p, div, cell, row or table that holds it, and its ink as color there; SpamAssassin "
        "reads no background shorthand, no bgcolor and no style on another element, and reads white where nothing around "
        "a text sets a ground it reads"
        for text, ink, ground in dict.fromkeys(colours.too_alike)
    ]
    refused = [
        f"a browser's tokenizer reads the page's markup with an error ({error}), and SpamAssassin's HTML parser "
        "(HTML::Parser) and the standard library's, in one Python release or another, tokenize such markup each on terms "
        "of its own: write the markup without it (a bare & as &amp;)"
        for error in _token_errors(page)
    ]
    return too_alike + sorted(set(colours.refused + refused))
