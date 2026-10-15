"""How a mail client reads the styles two of the mail shell's rules turn on, for the gates that hold them.

``tests/unit/test_mail_header_template.py`` states the rules and plants their cases, and
``tests/unit/test_mail_rendered_addresses.py`` holds every page the mail module sends to them:
- ``text_size_problems``: the header keeps its set size where a phone view enlarges small text, and every
  other line is left to the view;
- ``long_run_problems``: a run of characters with nowhere to wrap, such as a link with its token or a
  report's hash, can break anywhere once it is long enough to fill the panel, so a view that enlarges it
  cannot widen the panel past the header.

A page is read as a browser builds it, by ``tinyhtml5``, the WHATWG tree builder that WeasyPrint brings
(``requirements.txt``): an end tag a browser implies is implied, a ``/>`` on an element that is not void
is ignored, the first of two same-named attributes is kept, and text a table cannot hold moves before
it. Each element's ``style`` attribute is read as CSS reads one, by ``tinycss2``: comments and escapes
decoded, a declaration its property cannot take dropped, an important declaration over a normal one, and
among equals the last. The properties read here are inherited: ``inherit`` and ``unset`` take the
parent's value, ``revert`` the element's own default, such as ``<pre>``'s, or the parent's.

Two engines enlarge text, and each reads its own names:
- Blink, which the Gmail app and Android's other mail views run, reads ``text-size-adjust`` and
  ``-webkit-text-size-adjust`` as one property;
- Apple's WebKit, which iOS Mail runs, reads the prefixed name alone: caniuse marks iOS Safari's support
  as prefixed only, through 26.6 (``frontend/node_modules/caniuse-lite``, feature ``text-size-adjust``).

So a line's size is read once per engine, and each reading must hold the rule.

A run ends where a line may wrap: at a space, a tab or a line break where ``white-space`` lets the line
wrap, at ``<wbr>`` or a zero-width space there, at ``<br>`` or a line break ``<pre>`` keeps, and at the
edge of an element that is not inline. A run goes on across an inline element's tags, so a link split by
markup is read whole. Within a run, a character can break where ``overflow-wrap:anywhere`` (or its alias
``word-wrap``), ``word-break:break-word`` or ``word-break:break-all`` reaches it: each lets a word break
and shrinks the narrowest width a table can give its cell, which ``overflow-wrap:break-word`` alone does
not. ``white-space:nowrap`` or ``pre``, ``text-wrap-mode:nowrap`` and ``text-wrap:nowrap`` keep a run on one
line, spaces and all, as do ``<pre>``, ``<nobr>`` and a cell's ``nowrap`` attribute. A ``text-wrap-mode:wrap``
is not read as undoing a ``white-space:nowrap``: an engine that predates it keeps the line whole.

The header is the 600 px table that holds the wordmark, the name split by markup into its two styles,
and a page carries one. What the reader does not resolve, it refuses rather than guesses: a ``<style>``
block or a linked stylesheet, whose selectors it does not match. It reads no text the page does not
show: what ``display:none`` or the ``hidden`` attribute hides, and the head's.
"""
from __future__ import annotations

import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass, replace

import tinycss2
import tinyhtml5

# A run this long, with nowhere to break, can fill the panel's 536 px text column once a phone view
# enlarges it: Chromium's phone view sets the body's 16 px at about 27.7 px, where some 35 characters of
# a link fill the column. Thirty leaves a margin.
LONG_RUN = 30

_GLOBAL = frozenset({"inherit", "initial", "unset", "revert", "revert-layer"})
_KEYWORDS = {
    "overflow-wrap": {"normal", "break-word", "anywhere"},
    "word-wrap": {"normal", "break-word", "anywhere"},
    "word-break": {"normal", "break-all", "keep-all", "break-word", "auto-phrase"},
    "text-wrap-mode": {"wrap", "nowrap"},
    "text-wrap": {"wrap", "nowrap", "balance", "stable", "pretty", "avoid-orphans"},
}
_WHITE_SPACE = {  # each keyword as (keeps line breaks, wraps)
    "normal": (False, True), "nowrap": (False, False), "pre": (True, False),
    "pre-wrap": (True, True), "pre-line": (True, True), "break-spaces": (True, True),
}
# The shorthand's other spelling, its longhands' words: at most one of each pair of sets.
_COLLAPSE_WORDS = {"collapse": False, "preserve": True, "preserve-breaks": True, "preserve-spaces": False, "break-spaces": True}
_MODE_WORDS = {"wrap": True, "nowrap": False}
_OWN_WHITE_SPACE = {"pre": "pre", "listing": "pre", "xmp": "pre", "plaintext": "pre", "textarea": "pre-wrap", "nobr": "nowrap"}
_INLINE = frozenset({
    "a", "abbr", "b", "bdi", "bdo", "big", "cite", "code", "data", "del", "dfn", "em", "font", "i", "ins", "kbd",
    "label", "mark", "nobr", "q", "s", "samp", "small", "span", "strike", "strong", "sub", "sup", "time", "tt",
    "u", "var", "wbr",
})
_UNSHOWN = frozenset({"head", "script", "style", "template", "title"})
_SPACE = " \t\n\r\f"
_ZERO_WIDTH_SPACE = "\u200b"
_INVISIBLE = dict.fromkeys(map(ord, "\u00ad\u200b\u200c\u200d\u2060\ufeff"))  # characters that render as nothing


def _value(name: str, tokens) -> str | None:
    """A declaration's value as the reader compares it, or None when its property cannot take it."""
    parts = [token for token in tokens if token.type not in ("whitespace", "comment")]
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
        return " ".join(words)
    if name == "white-space":
        if len(words) == 1 and words[0] in _WHITE_SPACE:
            return words[0]
        collapse = [word for word in words if word in _COLLAPSE_WORDS]
        mode = [word for word in words if word in _MODE_WORDS]
        if len(collapse) + len(mode) != len(words) or len(collapse) > 1 or len(mode) > 1:
            return None
        keeps, wraps = (_COLLAPSE_WORDS[collapse[0]] if collapse else False), (_MODE_WORDS[mode[0]] if mode else True)
        return next(keyword for keyword, form in _WHITE_SPACE.items() if form == (keeps, wraps))
    return words[0] if len(words) == 1 and words[0] in _KEYWORDS.get(name, ()) else None


def _declarations(style: str | None) -> list[tuple[str, bool, str]]:
    """Each declaration a style attribute makes that its property can take, in order: (name, important, value)."""
    found = []
    for item in tinycss2.parse_blocks_contents(style or "", skip_comments=True, skip_whitespace=True):
        if item.type == "declaration" and (value := _value(item.lower_name, item.value)) is not None:
            found.append((item.lower_name, item.important, value))
    return found


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
        return self.wraps and (self.overflow_wrap == "anywhere" or self.word_break in ("break-word", "break-all"))


@dataclass(frozen=True)
class _Piece:
    text: str
    state: _State


class _Page:
    """The text a page shows, piece by piece and each with what it inherits, read as a browser builds the
    page. A ``None`` among the pieces is the edge of an element that is not inline, where a run ends."""

    def __init__(self, page: str) -> None:
        root = tinyhtml5.parse(page, namespace_html_elements=False)
        self.pieces: list[_Piece | None] = []
        self.headers = _header_tables(root)
        self.stylesheets = 0
        self._walk(root, _State())

    def _state(self, element: ElementTree.Element, parent: _State) -> tuple[_State, bool]:
        """What the element's text inherits, and whether the element is inline."""
        tag, declared = element.tag, _declarations(element.get("style"))
        display = _won(declared, "display")
        own_display = display not in (None, *_GLOBAL)
        shown = parent.shown and tag not in _UNSHOWN and display != "none"
        if element.get("hidden") is not None and not own_display:
            shown = False
        own_space = _OWN_WHITE_SPACE.get(tag) or ("nowrap" if tag in ("td", "th") and element.get("nowrap") is not None else None)
        state = replace(
            parent,
            blink=_take(_won(declared, "text-size-adjust", "-webkit-text-size-adjust"), parent.blink, "auto"),
            webkit=_take(_won(declared, "-webkit-text-size-adjust"), parent.webkit, "auto"),
            overflow_wrap=_take(_won(declared, "overflow-wrap", "word-wrap"), parent.overflow_wrap, "normal"),
            word_break=_take(_won(declared, "word-break"), parent.word_break, "normal"),
            white_space=_take(_won(declared, "white-space"), parent.white_space, "normal", own_space),
            text_wrap_mode=_take(_won(declared, "text-wrap-mode"), parent.text_wrap_mode, "wrap"),
            text_wrap=_take(_won(declared, "text-wrap"), parent.text_wrap, "wrap"),
            in_header=parent.in_header or any(element is header for header in self.headers),
            shown=shown,
        )
        inline = display in ("inline", "inline flow", "contents") if own_display else tag in _INLINE
        return state, inline

    def _text(self, text: str | None, state: _State) -> None:
        if text and state.shown:
            self.pieces.append(_Piece(text, state))

    def _walk(self, element: ElementTree.Element, parent: _State) -> None:
        if not isinstance(element.tag, str):  # a comment, Outlook's conditionals among them: no text
            return
        if element.tag == "style" or (element.tag == "link" and "stylesheet" in (element.get("rel") or "").lower().split()):
            self.stylesheets += 1
        state, inline = self._state(element, parent)
        if element.tag == "wbr":
            self._text(_ZERO_WIDTH_SPACE, state)
            return
        if not inline:
            self.pieces.append(None)
        self._text(element.text, state)
        for child in element:
            self._walk(child, state)
            self._text(child.tail, state)
        if not inline:
            self.pieces.append(None)

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
                if character in _SPACE + _ZERO_WIDTH_SPACE and state.wraps:
                    runs.append([])
                elif character in "\n\r" and state.keeps_breaks:
                    runs.append([])
                elif character in _SPACE:
                    runs[-1].append((" ", state))
                elif character != _ZERO_WIDTH_SPACE:
                    runs[-1].append((character, state))
        return [run for run in runs if run]


def text_size_problems(page: str) -> list[str]:
    """Where a page breaks the shell's text-size rule: the header keeps its set size where a phone view
    enlarges text, in both engines, and every other line is left to the view."""
    parsed = _Page(page)
    problems = []
    if parsed.stylesheets:
        problems.append(
            "the page carries a <style> block or a linked stylesheet, whose selectors this check does not read: set the style inline"
        )
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
    problems = []
    for run in _Page(page).runs():
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
