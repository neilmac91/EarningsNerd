"""A model of how Blink and WebKit read a mail page's inline styles, for the gates that hold the shell's rules.

``tests/unit/test_mail_header_template.py`` states the rules and plants their cases, and
``tests/unit/test_mail_rendered_addresses.py`` holds every page the mail module sends to them:
- ``text_size_problems``: the header keeps its set size where a phone view enlarges small text, and every
  other line is left to the view;
- ``long_run_problems``: a run of characters with nowhere to wrap, such as a link with its token, a report's
  hash or a name typed as an address, can break anywhere once it is long enough to fill the panel's text
  column on the narrowest phone, so it cannot hold the page wider than the screen;
- ``fixed_width_problems``: the page is fluid down to that phone, so nothing a client other than classic
  Outlook shows sets a width the phone cannot hold;
- ``outlook_width_problems``: classic Outlook, which reads no ``max-width``, holds each column capped at
  600 px at 600 px, through a table only its conditional comments show.

A page is read as a browser builds it, by ``tinyhtml5``, the WHATWG tree builder (``requirements.in``): an
end tag a browser implies is implied, a ``/>`` on an element that is not void is ignored, the first of two
same-named attributes is kept, a formatting element left open is opened again where the parser opens it,
and text a table cannot hold moves before it. A comment holds no markup, so what Outlook's conditional
comments hold is read only in Outlook's view (``outlook_view``). Each element's ``style`` attribute is read as
CSS reads one, by ``tinycss2``: comments and escapes decoded, a declaration its property cannot take
dropped, an important declaration over a normal one, and among equals the last. The text properties read
here are inherited: ``inherit`` and ``unset`` take the parent's value, ``revert`` the element's own default,
such as ``<pre>``'s, or the parent's. A cell's ``nowrap`` attribute is a presentational hint, below every
declaration of its ``style`` and reverted with them.

Two engines enlarge text, and each reads its own names:
- Blink, which Android's mail apps run, reads ``text-size-adjust`` and ``-webkit-text-size-adjust`` as one
  property;
- Apple's WebKit, which every iOS mail app runs, iOS Mail and the Gmail app among them, reads the prefixed
  name alone: caniuse marks iOS Safari's support as prefixed only, from 5 through 26.6
  (``frontend/node_modules/caniuse-lite``, feature ``text-size-adjust``).

So a line's size is read once per engine, and each reading must hold the rule.

A run ends where a line may wrap: at a space, a tab, a line break or one of the Unicode spaces a line may
break after, where the line wraps; at ``<wbr>`` or a zero-width space there; at ``<br>`` or a line break
``<pre>`` keeps; and at the edge of a block, a table's part or an element placed whole, such as an image or
a button. It goes on across the tags of every other element, an element the reader does not know and one
the page hides alike, so a link split by markup is read whole. Within a run, a character can break where
``overflow-wrap:anywhere``, ``word-break:break-word`` or ``break-all``, or ``line-break:anywhere`` reaches it:
each lets a word break and shrinks the narrowest width a table can give its cell, which
``overflow-wrap:break-word`` alone does not. ``word-wrap``, the alias, is read with ``overflow-wrap``: Blink takes
its ``anywhere``, and WebKit may not, so a run breaks in every engine only where another of those forms reaches
it, while a shell lends the rule wherever either engine would take it (``lent_runs``); ``-webkit-line-break`` is read
with ``line-break`` the same way. ``all`` sets every
property read here to its keyword, in its place among the declarations. A line
wraps where both kinds of engine wrap it: one that predates ``text-wrap-mode`` reads ``white-space`` alone,
and one that reads it takes the last of ``white-space``, ``text-wrap`` and ``text-wrap-mode``, the first two
being shorthands that set it. So ``white-space:nowrap`` or ``pre``, ``text-wrap-mode:nowrap`` and a
``text-wrap`` with ``nowrap`` keep a run on one line, spaces and all, as do ``<pre>``, ``<nobr>`` and a cell's
``nowrap`` attribute, and a ``text-wrap-mode:wrap`` does not undo a ``white-space:nowrap``.

A width is an element's ``width`` in its ``style`` where one is declared, else its ``width`` attribute as
HTML maps one: a number is pixels, a number then ``%`` a percentage. A width in pixels, or in another
absolute unit, is fixed; a percentage or a keyword is not; a width set by the font or the screen, such as
``em`` or ``vw``, is refused rather than guessed. A fixed width wider than ``WIDEST_FIXED`` fails unless the
element's ``max-width`` holds it to the screen (a percentage up to 100%, or a fixed width that fits), and a
fixed ``min-width`` wider than that fails outright. Outlook's view is the page as classic Outlook reads its
conditional comments: what one meant for Outlook holds shows, what ``<!--[if !mso]><!-->`` holds does not.

The reader errs toward asking for the rule: it counts no break a browser may take at a hyphen or after a
question mark, and no width that holds a run in, such as a fixed table layout or a clipped box, so it may
ask for the rule where a browser would fit the run. The header is the table capped at 600 px (its
``max-width``) that holds the wordmark, the name split by markup into its two styles, and a page carries one.
What the reader does not resolve, it refuses rather than guesses: a ``<style>`` block, an SVG's or MathML's
included, or a linked stylesheet, whose selectors it does not match, and a value one of its properties takes
from a function, such as ``calc()`` or ``var()``. It reads no text the page does not show (what
``display:none`` or the ``hidden`` attribute hides, and the head's), nor an image's ``alt``, which shows only
where images are blocked; text hidden another way, at ``font-size:0`` or in a box clipped to nothing, it reads
as shown. A float or a positioned box, which a browser takes out of the line, ends a run where it sits.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass, replace

import tinycss2
import tinyhtml5
from tinycss2.ast import Node

# A run this long, with nowhere to break, can fill the panel's text column on the narrowest phone. In
# Chromium's phone view at 320 px, with Arial set as Liberation Sans, the shortest runs of a token that held
# the page wider than the screen were 22 characters at 16 px, 21 in bold and 18 at 20 px; where a view fits a
# wider page to its screen and enlarges its text, they were 26, 25 and 24. The check takes 18, the shortest
# measured, so every run measured is flagged. A run of wide letters fills the column sooner, and a phone's own
# font sets the widths there (lessons/test-layout-numbers-are-one-environments-run.md).
LONG_RUN = 18
# The narrowest phone a mail lays out on, and the widest fixed width a page may set there: 320 px, less the
# page's gutters (12 px a side) and the panel's border and padding (33 px a side).
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
}
_SIZING = frozenset({"min-content", "max-content", "fit-content", "stretch", "-webkit-fill-available"})
_WIDTH_WORDS = {"width": _SIZING | {"auto"}, "min-width": _SIZING | {"auto"}, "max-width": _SIZING | {"none"}}
_ABSOLUTE = {"px": 1.0, "pt": 4 / 3, "pc": 16.0, "in": 96.0, "cm": 96 / 2.54, "mm": 96 / 25.4, "q": 96 / 101.6}
_RELATIVE = frozenset({
    "em", "rem", "ex", "rex", "ch", "rch", "cap", "rcap", "ic", "ric", "lh", "rlh", "vw", "vh", "vi", "vb", "vmin",
    "vmax", "svw", "svh", "svi", "svb", "svmin", "svmax", "lvw", "lvh", "lvi", "lvb", "lvmin", "lvmax", "dvw", "dvh",
    "dvi", "dvb", "dvmin", "dvmax", "cqw", "cqh", "cqi", "cqb", "cqmin", "cqmax",
})
_READ = frozenset({
    *_KEYWORDS, *_WIDTH_WORDS, "text-size-adjust", "-webkit-text-size-adjust", "white-space", "text-wrap", "display", "all",
})
_WHITE_SPACE = {  # each keyword as (keeps line breaks, wraps)
    "normal": (False, True), "nowrap": (False, False), "pre": (True, False),
    "pre-wrap": (True, True), "pre-line": (True, True), "break-spaces": (True, True),
}
_MODE_OF = {keyword: "wrap" if wraps else "nowrap" for keyword, (_, wraps) in _WHITE_SPACE.items()}
# The shorthands' other spellings, their longhands' words: at most one word from each set.
_COLLAPSE_WORDS = {"collapse": False, "preserve": True, "preserve-breaks": True, "preserve-spaces": False, "break-spaces": True}
_MODE_WORDS = {"wrap": True, "nowrap": False}
_TEXT_WRAP_STYLES = frozenset({"auto", "balance", "stable", "pretty", "avoid-orphans"})
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
# The elements a browser's own style sheet hides, and so lays nothing out for; <audio> without its controls,
# <input type="hidden"> and a <dialog> that is not open are hidden too.
_UNSHOWN = frozenset({
    "area", "base", "basefont", "datalist", "head", "link", "meta", "noembed", "noframes", "param", "rp", "script",
    "source", "style", "template", "title", "track",
})
_SPACE = " \t\n\r\f"  # HTML's whitespace, which a line of text is stripped of
# Where a line may wrap: ASCII spaces and line breaks, and the Unicode spaces a line may break after. A form
# feed, a no-break space, a figure space and a narrow no-break space are no such place.
_WRAP_SPACES = " \t\n\r\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2008\u2009\u200a\u205f\u3000"
_ZERO_WIDTH_SPACE = "\u200b"
_INVISIBLE = dict.fromkeys(map(ord, "\u00ad\u200b\u200c\u200d\u2060\ufeff"))  # characters that render as nothing
# A conditional comment: what it holds, and whether a client other than Outlook shows that too.
_CONDITIONAL = re.compile(r"<!--\[if\s+([^\]]+)\]>(<!-->)?(.*?)(?:<!--)?<!\[endif\]-->", re.DOTALL | re.IGNORECASE)


def _number(value: float) -> str:
    """A CSS number as the reader compares it, written out in full."""
    return f"{value:f}".rstrip("0").rstrip(".")


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


def _has_function(tokens: list[Node]) -> bool:
    """Whether a value takes anything from a function, at any depth: a var() inside brackets defers it too."""
    return any(
        token.type == "function" or (token.type in ("() block", "[] block", "{} block") and _has_function(token.content))
        for token in tokens
    )


def _declarations(style: str | None) -> tuple[list[tuple[str, bool, str]], list[str]]:
    """Each declaration a style attribute makes that its property can take, in order (name, important,
    value), and each declaration of a property read here that takes its value from a function."""
    found, unread = [], []
    for item in tinycss2.parse_blocks_contents(style or "", skip_comments=True, skip_whitespace=True):
        if item.type != "declaration":
            continue
        if item.lower_name in _READ and _has_function(item.value):
            unread.append(f"{item.lower_name}:{tinycss2.serialize(item.value).strip()}")
        elif (value := _value(item.lower_name, item.value)) is None:
            continue
        elif item.lower_name == "all":  # a CSS-wide keyword, set on every property read here
            found += [(name, item.important, value) for name in sorted(_READ - {"all"})]
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
    """Whether a browser's own style sheet hides the element: one it always hides, <audio> without its
    controls, <input type="hidden"> and a <dialog> that is not open."""
    name = _local(element.tag)
    return (
        name in _UNSHOWN
        or (name == "audio" and element.get("controls") is None)
        or (name == "input" and (element.get("type") or "").strip().lower() == "hidden")
        or (name == "dialog" and element.get("open") is None)
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


@dataclass(frozen=True)
class _State:
    """What an element's text inherits, and whether it shows and sits in the header."""

    blink: str = "auto"  # text-size-adjust, as Blink reads it
    webkit: str = "auto"  # as Apple's WebKit reads it: the prefixed name alone
    overflow_wrap: str = "normal"  # as Blink reads it, word-wrap's anywhere taken
    overflow_wrap_webkit: str = "normal"  # as WebKit may, word-wrap's anywhere dropped
    word_break: str = "normal"
    line_break: str = "auto"  # as Blink reads it, -webkit-line-break's anywhere taken
    line_break_webkit: str = "auto"  # as WebKit may, the alias's anywhere dropped
    white_space: str = "normal"  # as an engine that predates text-wrap-mode reads it
    wrap_mode: str = "wrap"  # as one that reads it does: the last of white-space, text-wrap and text-wrap-mode
    in_header: bool = False
    shown: bool = True
    inline: bool = False  # whether the element is an inline box, which display:inherit gives its child

    @property
    def wraps(self) -> bool:
        return _WHITE_SPACE[self.white_space][1] and self.wrap_mode == "wrap"

    @property
    def keeps_breaks(self) -> bool:
        return _WHITE_SPACE[self.white_space][0]

    @property
    def collapses(self) -> bool:  # a run of spaces shows as one
        return self.white_space in ("normal", "nowrap", "pre-line")

    @property
    def breaks_anywhere(self) -> bool:  # in every engine
        return self.wraps and (
            self.overflow_wrap_webkit == "anywhere"
            or self.word_break in ("break-word", "break-all")
            or self.line_break_webkit == "anywhere"
        )

    @property
    def breaks_in_some_engine(self) -> bool:
        return self.wraps and (
            self.overflow_wrap == "anywhere" or self.word_break in ("break-word", "break-all") or self.line_break == "anywhere"
        )


@dataclass(frozen=True)
class _Piece:
    text: str
    state: _State


@dataclass(frozen=True)
class _Width:
    """The widths a shown element sets: its ``width`` attribute, and its style's winning ``width``,
    ``min-width`` and ``max-width``."""

    tag: str
    attribute: str | None
    width: str | None
    min_width: str | None
    max_width: str | None


class _Page:
    """The text a page shows, piece by piece and each with what it inherits, read as a browser builds the
    page, and the widths its shown elements set. A ``None`` among the pieces is an edge a run cannot cross."""

    def __init__(self, page: str) -> None:
        root = tinyhtml5.parse(page, namespace_html_elements=False)
        self.pieces: list[_Piece | None] = []
        self.widths: list[_Width] = []
        self.unread: list[str] = []
        self.headers = _header_tables(root)
        # A style block or a stylesheet applies wherever it sits, in the head or in what the page hides.
        self.stylesheets = sum(1 for element in root.iter() if isinstance(element.tag, str) and _is_stylesheet(element))
        self._walk(root, _State())

    def _state(self, element: ElementTree.Element, parent: _State) -> tuple[_State, bool, list[tuple[str, bool, str]]]:
        """What the element's text inherits, whether a run goes on across its tags, and its declarations."""
        tag = element.tag
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
        # A cell's nowrap attribute: white-space:nowrap below every declaration of its style.
        hint = [("white-space", False, "nowrap")] if tag in ("td", "th") and element.get("nowrap") is not None else []
        spacing = hint + declared
        modes = [
            ("wrap-mode", important, _MODE_OF.get(value, value) if name == "white-space" else value)
            for name, important, value in spacing
            if name in ("white-space", "text-wrap", "text-wrap-mode")
        ]
        own_space = _OWN_WHITE_SPACE.get(tag)
        state = replace(
            parent,
            blink=_take(_won(declared, "text-size-adjust", "-webkit-text-size-adjust"), parent.blink, "auto"),
            webkit=_take(_won(declared, "-webkit-text-size-adjust"), parent.webkit, "auto"),
            overflow_wrap=_take(_won(declared, "overflow-wrap", "word-wrap"), parent.overflow_wrap, "normal"),
            overflow_wrap_webkit=_take(
                _won([d for d in declared if d[0] != "word-wrap" or d[2] != "anywhere"], "overflow-wrap", "word-wrap"),
                parent.overflow_wrap_webkit,
                "normal",
            ),
            word_break=_take(_won(declared, "word-break"), parent.word_break, "normal"),
            line_break=_take(_won(declared, "line-break", "-webkit-line-break"), parent.line_break, "auto"),
            line_break_webkit=_take(
                _won([d for d in declared if d[0] != "-webkit-line-break" or d[2] != "anywhere"], "line-break", "-webkit-line-break"),
                parent.line_break_webkit,
                "auto",
            ),
            white_space=_take(_won(spacing, "white-space"), parent.white_space, "normal", own_space),
            wrap_mode=_take(_won(modes, "wrap-mode"), parent.wrap_mode, "wrap", _MODE_OF[own_space] if own_space else None),
            in_header=parent.in_header or any(element is header for header in self.headers),
            shown=shown,
        )
        crossed = _inline(display) if display is not None else _local(tag) not in _RUN_EDGES
        return replace(state, inline=crossed), crossed, declared

    def _text(self, text: str | None, state: _State) -> None:
        if text and state.shown:
            self.pieces.append(_Piece(text, state))

    def _walk(self, element: ElementTree.Element, parent: _State) -> None:
        if not isinstance(element.tag, str):  # a comment, Outlook's conditionals among them: no text
            return
        state, crossed, declared = self._state(element, parent)
        if not state.shown:  # out of the layout: its text is not read, its widths hold nothing, and it ends no run
            return
        self.widths.append(_Width(
            element.tag, element.get("width"), _won(declared, "width"), _won(declared, "min-width"), _won(declared, "max-width"),
        ))
        if element.tag == "wbr":
            self._text(_ZERO_WIDTH_SPACE, state)
            return
        if not crossed:
            self.pieces.append(None)
        self._text(element.text, state)
        for child in element:
            self._walk(child, state)
            self._text(child.tail, state)
        if not crossed:
            self.pieces.append(None)

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
        what it inherits. Spaces a line collapses count once, and a run starts and ends at a character that
        shows."""
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
            while start < end and run[start][0] == " ":
                start += 1
            while end > start and run[end - 1][0] == " ":
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


def _pixels(value: str | None) -> tuple[float | None, bool]:
    """A width as (pixels, refused): pixels where an absolute unit sets it; refused where the font or the
    screen sets it, or the parent's width does (``inherit``); neither for a percentage or a keyword."""
    if value == "inherit":
        return None, True
    if value is None or value.endswith("%") or not value[:1].isdigit():
        return None, False
    unit = value.lstrip("0123456789.")
    if unit in _RELATIVE:
        return None, True
    return float(value[: len(value) - len(unit)]) * _ABSOLUTE[unit], False


def fixed_width_problems(page: str) -> list[str]:
    """Where a page sets a width the narrowest phone cannot hold, in what a client other than classic Outlook
    shows: a fixed width wider than ``WIDEST_FIXED`` that no ``max-width`` holds to the screen, or a fixed
    ``min-width`` wider than that."""
    parsed = _Page(page)
    problems = parsed.refusals()
    for element in parsed.widths:
        named = f"<{_local(element.tag)}>"
        if element.width is None:
            width = _attribute_width(element.attribute)
        else:  # the style's width wins over the attribute, and a global keyword reverts it with the attribute
            width = "auto" if element.width in _GLOBAL - {"inherit"} else element.width
        cap, cap_refused = _pixels(element.max_width)
        held = (element.max_width or "").endswith("%") and float(element.max_width[:-1]) <= 100
        held = held or (cap is not None and cap <= WIDEST_FIXED)
        for name, value in (("width", width), ("min-width", element.min_width)):
            pixels, refused = _pixels(value)
            if refused:
                problems.append(
                    f"{named}'s {name} {value} is set by the font, the screen or its parent, which this check does not "
                    "resolve: write it in px or %"
                )
            elif pixels is not None and pixels > WIDEST_FIXED and not (name == "width" and held):
                problems.append(
                    f"{named}'s {name} is {pixels:g} px, more than a {NARROWEST_SCREEN} px phone holds: let it take the width "
                    f"up to a cap (width:100%;max-width:{pixels:g}px), with classic Outlook's fixed width in a conditional comment"
                )
        if cap_refused:
            problems.append(f"{named}'s max-width {element.max_width} is set by the font, the screen or its parent: write it in px or %")
    return problems


def outlook_view(page: str) -> str:
    """The page as classic Outlook reads its conditional comments: what one meant for Outlook holds shows,
    and what ``<!--[if !mso]><!-->`` holds does not."""

    def read(match: re.Match[str]) -> str:
        condition = match.group(1).strip().lower()
        return match.group(3) if "mso" in condition and not condition.startswith("!") else ""

    return _CONDITIONAL.sub(read, page)


def outlook_width_problems(page: str) -> list[str]:
    """Where classic Outlook, which reads no ``max-width``, would not hold a column capped at 600 px at 600 px:
    in its view of the page, each such table sits in a table 600 px wide."""
    root = tinyhtml5.parse(outlook_view(page), namespace_html_elements=False)
    parents = {child: parent for parent in root.iter() for child in parent}
    problems = []
    for table in (element for element in root.iter() if element.tag == "table" and _capped(element)):
        around = parents.get(table)
        while around is not None and around.tag != "table":
            around = parents.get(around)
        if around is None or _attribute_width(around.get("width")) != "600px":
            text = " ".join("".join(table.itertext()).split())[:40]
            problems.append(
                f"in classic Outlook, which reads no max-width, the column capped at 600 px that reads {text!r} sits in no "
                "table 600 px wide: give it one in a conditional comment"
            )
    return problems
