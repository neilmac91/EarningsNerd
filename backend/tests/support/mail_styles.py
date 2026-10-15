"""How a mail client reads the styles two of the mail shell's rules turn on, for the gates that hold them.

``tests/unit/test_mail_header_template.py`` states the rules and plants their cases, and
``tests/unit/test_mail_rendered_addresses.py`` holds every page the mail module sends to them:
- ``text_size_problems``: the header keeps its set size where a phone view enlarges small text, and every
  other line is left to the view;
- ``long_run_problems``: a run of characters with nowhere to wrap, such as a link with its token, a report's
  hash or a name typed as an address, can break anywhere once it is long enough to fill the panel, so a
  view that enlarges it cannot widen the panel past the header.

A page is read as a browser builds it, by ``tinyhtml5``, the WHATWG tree builder (``requirements.in``): an
end tag a browser implies is implied, a ``/>`` on an element that is not void is ignored, the first of two
same-named attributes is kept, a formatting element left open is opened again where the parser opens it,
and text a table cannot hold moves before it. Each element's ``style`` attribute is read as CSS reads one,
by ``tinycss2``: comments and escapes decoded, a declaration its property cannot take dropped, an important
declaration over a normal one, and among equals the last. Every property read here but ``display`` is
inherited: ``inherit`` and ``unset`` take the parent's value, ``revert`` the element's own default, such as
``<pre>``'s, or the parent's.

Two engines enlarge text, and each reads its own names:
- Blink, which Android's mail apps run, reads ``text-size-adjust`` and ``-webkit-text-size-adjust`` as one
  property;
- Apple's WebKit, which every iOS mail app runs, iOS Mail and the Gmail app among them, reads the prefixed
  name alone: caniuse marks iOS Safari's support as prefixed only, from 8 through 26.6
  (``frontend/node_modules/caniuse-lite``, feature ``text-size-adjust``).

So a line's size is read once per engine, and each reading must hold the rule.

A run ends where a line may wrap: at a space, a tab, a line break or one of the Unicode spaces a line may
break after, where ``white-space`` lets the line wrap; at ``<wbr>`` or a zero-width space there; at ``<br>``
or a line break ``<pre>`` keeps; and at the edge of a block, a table's part or an element placed whole, such
as an image or a button. It goes on across the tags of every other element, an element the reader does not
know and one the page hides alike, so a link split by markup is read whole. Within a run, a character can
break where ``overflow-wrap:anywhere``, ``word-break:break-word`` or ``break-all``, or ``line-break:anywhere``
reaches it: each lets a word break and shrinks the narrowest width a table can give its cell, which
``overflow-wrap:break-word`` alone does not. ``word-wrap``, the alias, is read with ``overflow-wrap``, but its
``anywhere`` is dropped, since an engine may take only ``normal`` and ``break-word`` under that name.
``white-space:nowrap`` or ``pre``, ``text-wrap-mode:nowrap`` and a ``text-wrap`` with ``nowrap`` keep a run on
one line, spaces and all, as do ``<pre>``, ``<nobr>`` and a cell's ``nowrap`` attribute; a
``text-wrap-mode:wrap`` is not read as undoing a ``white-space:nowrap``, since an engine that predates it
keeps the line whole.

The reader errs toward asking for the rule: it counts no break a browser may take at a hyphen or after a
question mark, and no width that holds a run in, such as a fixed table layout or a clipped box, so it may
ask for the rule where a browser would fit the run. The header is the 600 px table that holds the wordmark,
the name split by markup into its two styles, and a page carries one. What the reader does not resolve, it
refuses rather than guesses: a ``<style>`` block or a linked stylesheet, whose selectors it does not match,
and a value one of its properties takes from a function, such as ``calc()`` or ``var()``. It reads no text
the page does not show (what ``display:none`` or the ``hidden`` attribute hides, and the head's), nor an
image's ``alt``, which shows only where images are blocked.
"""
from __future__ import annotations

import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass, replace

import tinycss2
import tinyhtml5
from tinycss2.ast import Node

# A run this long, with nowhere to break, can fill the panel's 534 px text column once a phone view
# enlarges it. In Chromium's phone view at 320 px, the narrowest phone, the shortest runs that widened the
# panel were 26 characters of a token at 16 px, 25 in bold, and 24 at 20 px; a mail's text is 16 px or
# smaller, so 24 sits under every run measured.
LONG_RUN = 24

_GLOBAL = frozenset({"inherit", "initial", "unset", "revert", "revert-layer"})
_KEYWORDS = {  # a one-word value each property can take
    "overflow-wrap": {"normal", "break-word", "anywhere"},
    "word-wrap": {"normal", "break-word"},
    "word-break": {"normal", "break-all", "keep-all", "break-word", "auto-phrase"},
    "line-break": {"auto", "loose", "normal", "strict", "anywhere"},
    "text-wrap-mode": {"wrap", "nowrap"},
}
_READ = frozenset({*_KEYWORDS, "text-size-adjust", "-webkit-text-size-adjust", "white-space", "text-wrap", "display"})
_WHITE_SPACE = {  # each keyword as (keeps line breaks, wraps)
    "normal": (False, True), "nowrap": (False, False), "pre": (True, False),
    "pre-wrap": (True, True), "pre-line": (True, True), "break-spaces": (True, True),
}
# The shorthands' other spellings, their longhands' words: at most one word from each set.
_COLLAPSE_WORDS = {"collapse": False, "preserve": True, "preserve-breaks": True, "preserve-spaces": False, "break-spaces": True}
_MODE_WORDS = {"wrap": True, "nowrap": False}
_TEXT_WRAP_STYLES = frozenset({"auto", "balance", "stable", "pretty", "avoid-orphans"})
_DISPLAY_WORDS = frozenset({
    "block", "inline", "run-in", "flow", "flow-root", "table", "flex", "grid", "ruby", "list-item", "contents", "none",
    "inline-block", "inline-table", "inline-flex", "inline-grid", "table-row-group", "table-header-group",
    "table-footer-group", "table-row", "table-cell", "table-column-group", "table-column", "table-caption",
    "ruby-base", "ruby-text", "ruby-base-container", "ruby-text-container", "math", "-webkit-box", "-webkit-inline-box",
})
_DISPLAY_INLINE = frozenset({"inline", "inline flow", "flow inline", "contents", "ruby", "inline ruby", "ruby inline"})
_OWN_WHITE_SPACE = {"pre": "pre", "listing": "pre", "xmp": "pre", "plaintext": "pre", "textarea": "pre-wrap", "nobr": "nowrap"}
# The elements a run cannot cross: blocks and a table's parts, the elements placed whole, and <br>.
_RUN_EDGES = frozenset({
    "address", "article", "aside", "blockquote", "body", "caption", "center", "col", "colgroup", "dd", "details",
    "dialog", "dir", "div", "dl", "dt", "fieldset", "figcaption", "figure", "footer", "form", "frameset", "h1", "h2",
    "h3", "h4", "h5", "h6", "header", "hgroup", "hr", "html", "legend", "li", "listing", "main", "menu", "nav", "ol",
    "optgroup", "option", "p", "plaintext", "pre", "search", "section", "summary", "table", "tbody", "td", "tfoot",
    "th", "thead", "tr", "ul", "xmp",
    "audio", "button", "canvas", "embed", "iframe", "img", "input", "marquee", "math", "meter", "object", "progress",
    "select", "svg", "textarea", "video",
    "br",
})
_UNSHOWN = frozenset({"head", "script", "style", "template", "title"})
_SPACE = " \t\n\r\f"  # HTML's whitespace, which a line of text is stripped of
# Where a line may wrap: ASCII spaces and line breaks, and the Unicode spaces a line may break after. A form
# feed, a no-break space, a figure space and a narrow no-break space are no such place.
_WRAP_SPACES = " \t\n\r\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2008\u2009\u200a\u205f\u3000"
_ZERO_WIDTH_SPACE = "\u200b"
_INVISIBLE = dict.fromkeys(map(ord, "\u00ad\u200b\u200c\u200d\u2060\ufeff"))  # characters that render as nothing


def _value(name: str, tokens: list[Node]) -> str | None:
    """A declaration's value as the reader compares it, or None when its property cannot take it."""
    parts = [token for token in tokens if token.type != "whitespace"]  # tinycss2 has dropped the comments
    if name in ("text-size-adjust", "-webkit-text-size-adjust"):
        if len(parts) == 1 and parts[0].type == "percentage" and parts[0].value >= 0:
            return f"{parts[0].value:g}%"
        if len(parts) == 1 and parts[0].type == "ident" and parts[0].lower_value in _GLOBAL | {"auto", "none"}:
            return parts[0].lower_value
        return None
    if not parts or any(part.type != "ident" for part in parts):
        return None
    words = [part.lower_value for part in parts]
    if len(words) == 1 and words[0] in _GLOBAL:
        return words[0]
    if name == "display":
        return " ".join(words) if set(words) <= _DISPLAY_WORDS and len(words) <= 3 else None
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


def _declarations(style: str | None) -> tuple[list[tuple[str, bool, str]], list[str]]:
    """Each declaration a style attribute makes that its property can take, in order (name, important,
    value), and each declaration of a property read here that takes its value from a function."""
    found, unread = [], []
    for item in tinycss2.parse_blocks_contents(style or "", skip_comments=True, skip_whitespace=True):
        if item.type != "declaration":
            continue
        if item.lower_name in _READ and any(token.type == "function" for token in item.value):
            unread.append(f"{item.lower_name}:{tinycss2.serialize(item.value).strip()}")
        elif (value := _value(item.lower_name, item.value)) is not None:
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


def _header_tables(root: ElementTree.Element) -> list[ElementTree.Element]:
    """The 600 px tables that hold a wordmark: ``Earnings``, then an element that reads ``Nerd``."""
    parents = {child: parent for parent in root.iter() for child in parent}
    found: list[ElementTree.Element] = []
    for parent in root.iter():
        before = parent.text or ""
        for child in parent:
            text = "".join(child.itertext()) if isinstance(child.tag, str) else ""
            name = before.translate(_INVISIBLE).rstrip().lower()
            if text.translate(_INVISIBLE).strip().lower() == "nerd" and name.endswith("earnings"):
                table = parent
                while table is not None and not (table.tag == "table" and table.get("width") == "600"):
                    table = parents.get(table)
                if table is not None and table not in found:
                    found.append(table)
            before = text + (child.tail or "")
    return found


def _is_stylesheet(element: ElementTree.Element) -> bool:
    return element.tag == "style" or (element.tag == "link" and "stylesheet" in (element.get("rel") or "").lower().split())


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
    overflow_wrap: str = "normal"
    word_break: str = "normal"
    line_break: str = "auto"
    white_space: str = "normal"
    text_wrap_mode: str = "wrap"
    text_wrap: str = "wrap"
    in_header: bool = False
    shown: bool = True

    @property
    def wraps(self) -> bool:
        return _WHITE_SPACE[self.white_space][1] and "nowrap" not in (self.text_wrap_mode, self.text_wrap)

    @property
    def keeps_breaks(self) -> bool:
        return _WHITE_SPACE[self.white_space][0]

    @property
    def breaks_anywhere(self) -> bool:
        return self.wraps and (
            self.overflow_wrap == "anywhere" or self.word_break in ("break-word", "break-all") or self.line_break == "anywhere"
        )


@dataclass(frozen=True)
class _Piece:
    text: str
    state: _State


class _Page:
    """The text a page shows, piece by piece and each with what it inherits, read as a browser builds the
    page. A ``None`` among the pieces is an edge a run cannot cross."""

    def __init__(self, page: str) -> None:
        root = tinyhtml5.parse(page, namespace_html_elements=False)
        self.pieces: list[_Piece | None] = []
        self.unread: list[str] = []
        self.headers = _header_tables(root)
        # A style block or a stylesheet applies wherever it sits, in the head or in what the page hides.
        self.stylesheets = sum(1 for element in root.iter() if isinstance(element.tag, str) and _is_stylesheet(element))
        self._walk(root, _State())

    def _state(self, element: ElementTree.Element, parent: _State) -> tuple[_State, bool]:
        """What the element's text inherits, and whether a run goes on across its tags."""
        tag = element.tag
        declared, unread = _declarations(element.get("style"))
        self.unread += unread
        display = _won(declared, "display")
        if display in ("initial", "unset"):
            display = "inline"  # display's initial value, which unset takes, since display is not inherited
        elif display in _GLOBAL:
            display = None  # inherit or revert: the element's own, as a browser's style sheet gives it
        shown = parent.shown and tag not in _UNSHOWN and display != "none"
        if element.get("hidden") is not None and display is None:
            shown = False
        own_space = _OWN_WHITE_SPACE.get(tag) or ("nowrap" if tag in ("td", "th") and element.get("nowrap") is not None else None)
        state = replace(
            parent,
            blink=_take(_won(declared, "text-size-adjust", "-webkit-text-size-adjust"), parent.blink, "auto"),
            webkit=_take(_won(declared, "-webkit-text-size-adjust"), parent.webkit, "auto"),
            overflow_wrap=_take(_won(declared, "overflow-wrap", "word-wrap"), parent.overflow_wrap, "normal"),
            word_break=_take(_won(declared, "word-break"), parent.word_break, "normal"),
            line_break=_take(_won(declared, "line-break"), parent.line_break, "auto"),
            white_space=_take(_won(declared, "white-space"), parent.white_space, "normal", own_space),
            text_wrap_mode=_take(_won(declared, "text-wrap-mode"), parent.text_wrap_mode, "wrap"),
            text_wrap=_take(_won(declared, "text-wrap"), parent.text_wrap, "wrap"),
            in_header=parent.in_header or any(element is header for header in self.headers),
            shown=shown,
        )
        crossed = display in _DISPLAY_INLINE if display is not None else tag not in _RUN_EDGES
        return state, crossed

    def _text(self, text: str | None, state: _State) -> None:
        if text and state.shown:
            self.pieces.append(_Piece(text, state))

    def _walk(self, element: ElementTree.Element, parent: _State) -> None:
        if not isinstance(element.tag, str):  # a comment, Outlook's conditionals among them: no text
            return
        state, crossed = self._state(element, parent)
        if not state.shown:  # out of the layout: its text is not read, and it ends no run
            return
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
        what it inherits."""
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
                    runs[-1].append((" ", state))
                elif character != _ZERO_WIDTH_SPACE:
                    runs[-1].append((character, state))
        return [run for run in runs if run]


def text_size_problems(page: str) -> list[str]:
    """Where a page breaks the shell's text-size rule: the header keeps its set size where a phone view
    enlarges text, in both engines, and every other line is left to the view."""
    parsed = _Page(page)
    problems = parsed.refusals()
    if len(parsed.headers) != 1:
        problems.append(
            f"the page carries {len(parsed.headers)} tables that read as the header, a 600 px table that holds the wordmark: "
            "the check finds the header by it, so a page carries one"
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


def long_run_problems(page: str) -> list[str]:
    """Where a page shows ``LONG_RUN`` characters or more with nowhere to break: a view that enlarges them
    widens the panel past the header."""
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
                        f"{text!r} cannot wrap: white-space or text-wrap keeps it on one line, so once enlarged it widens "
                        "the panel past the header"
                    )
                else:
                    problems.append(
                        f"{text!r} has nowhere to break: give its line overflow-wrap:anywhere;word-break:break-word, or once "
                        "enlarged it widens the panel past the header"
                    )
            stretch = []
    return problems
